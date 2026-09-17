"""Evaluate a coding agent on this repository, not on a public benchmark.

Public benchmarks stopped being useful signal during 2026: the tasks are in the
training data and they say nothing about your codebase. Databricks built their
own for exactly that reason, scored it by executing tests that were held out
from the agent, and blocked the agent from reading git history to recover the
answer. This is the same shape, small enough to read in one sitting.

Each task follows the four-part structure Terminal-Bench uses: an instruction,
an environment, a programmatic verification, and a reference for what good
looks like. Verification is a held-out test suite where a mechanical oracle
exists, and a rubric judged by a model where one does not.

    python run_eval.py --dry-run          # show the plan, spend nothing
    python run_eval.py                    # run every task
    python run_eval.py --task 001         # run one
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
TASKS_DIR = HARNESS_DIR / "tasks"
SAMPLE_APP = HARNESS_DIR.parents[1] / "sampleapp"

AGENT_MODEL = "claude-sonnet-5"
JUDGE_MODEL = "claude-opus-5"

JUDGE_PROMPT = """You are grading one change made by a coding agent.

Return only a JSON object, no prose around it, of this exact shape:
{{"criteria": [{{"n": 1, "met": true, "why": "one sentence"}}], "score": 0.0, "summary": "one sentence"}}

`score` is the fraction of criteria met, between 0 and 1.
Judge only what the diff and response actually show. Absence of evidence is not
met. Be strict: a criterion that is partially addressed is not met.

## Rubric

{rubric}

## What the agent said

{response}

## The diff it produced

{diff}
"""


@dataclass
class Task:
    id: str
    title: str
    oracle: str
    prompt: str
    directory: Path
    held_out_tests: list[str] = field(default_factory=list)
    regression_tests: list[str] = field(default_factory=list)
    rubric: str | None = None
    timeout_seconds: int = 600
    expected_outcome: str | None = None

    @classmethod
    def load(cls, directory: Path) -> "Task":
        data = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        return cls(
            id=data["id"],
            title=data["title"],
            oracle=data["oracle"],
            prompt=data["prompt"],
            directory=directory,
            held_out_tests=data.get("held_out_tests", []),
            regression_tests=data.get("regression_tests", []),
            rubric=data.get("rubric"),
            timeout_seconds=data.get("timeout_seconds", 600),
            expected_outcome=data.get("expected_outcome"),
        )


@dataclass
class Result:
    task_id: str
    title: str
    oracle: str
    passed: bool = False
    score: float = 0.0
    cost_usd: float = 0.0
    judge_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    turns: int = 0
    regression_ok: bool = False
    held_out_ok: bool = False
    detail: str = ""
    agent_error: str | None = None

    @property
    def total_cost_usd(self) -> float:
        return self.cost_usd + self.judge_cost_usd


def run_claude(prompt: str, cwd: Path, model: str, timeout: int) -> dict:
    """Invoke Claude Code headlessly and return its JSON result envelope."""
    try:
        completed = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--model", model,
                "--permission-mode", "acceptEdits",
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"is_error": True, "result": f"timed out after {timeout}s", "total_cost_usd": 0.0}
    except FileNotFoundError:
        raise SystemExit("claude was not found on PATH; this harness drives the Claude Code CLI")

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "is_error": True,
            "result": (completed.stderr or completed.stdout)[:500],
            "total_cost_usd": 0.0,
        }


def run_pytest(workdir: Path, target: str) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-header"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    tail = (completed.stdout or completed.stderr).strip().splitlines()
    return completed.returncode == 0, tail[-1] if tail else "no output"


def diff_against_baseline(baseline: Path, workdir: Path, limit: int = 20000) -> str:
    import difflib

    chunks: list[str] = []
    for current in sorted(workdir.rglob("*.py")):
        relative = current.relative_to(workdir)
        if "__pycache__" in relative.parts:
            continue
        original_path = baseline / relative
        original = (
            original_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if original_path.is_file()
            else []
        )
        updated = current.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        patch = list(
            difflib.unified_diff(original, updated, f"a/{relative}", f"b/{relative}", n=3)
        )
        if patch:
            chunks.append("".join(patch))
    diff = "".join(chunks)
    return diff[:limit] or "(no files changed)"


def judge(task: Task, response: str, diff: str) -> tuple[float, str, float]:
    rubric = (task.directory / task.rubric).read_text(encoding="utf-8")
    prompt = JUDGE_PROMPT.format(rubric=rubric, response=response[:4000], diff=diff)
    envelope = run_claude(prompt, cwd=HARNESS_DIR, model=JUDGE_MODEL, timeout=300)
    cost = float(envelope.get("total_cost_usd") or 0.0)

    raw = envelope.get("result", "")
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return 0.0, "judge returned no JSON", cost
    try:
        verdict = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return 0.0, "judge returned malformed JSON", cost

    met = sum(1 for c in verdict.get("criteria", []) if c.get("met"))
    total = len(verdict.get("criteria", [])) or 1
    score = float(verdict.get("score", met / total))
    return score, verdict.get("summary", ""), cost


def evaluate(task: Task, keep: bool) -> Result:
    result = Result(task_id=task.id, title=task.title, oracle=task.oracle)
    started = datetime.now(timezone.utc)

    workdir = Path(tempfile.mkdtemp(prefix=f"eval-{task.id}-"))
    shutil.copytree(SAMPLE_APP, workdir, dirs_exist_ok=True)

    envelope = run_claude(task.prompt, workdir, AGENT_MODEL, task.timeout_seconds)
    result.cost_usd = float(envelope.get("total_cost_usd") or 0.0)
    result.turns = int(envelope.get("num_turns") or 0)
    response = envelope.get("result", "") or ""
    if envelope.get("is_error"):
        result.agent_error = response[:200]

    for target in task.regression_tests:
        result.regression_ok, detail = run_pytest(workdir, target)
        if not result.regression_ok:
            result.detail = f"regression: {detail}"
            break
    else:
        result.regression_ok = result.regression_ok or not task.regression_tests

    if task.oracle == "tests":
        for relative in task.held_out_tests:
            source = task.directory / relative
            shutil.copy(source, workdir / "tests" / source.name)
        result.held_out_ok, detail = run_pytest(workdir, "tests")
        result.detail = result.detail or f"held-out: {detail}"
        result.score = 1.0 if result.held_out_ok else 0.0
        result.passed = result.held_out_ok
    else:
        diff = diff_against_baseline(SAMPLE_APP, workdir)
        result.score, summary, result.judge_cost_usd = judge(task, response, diff)
        result.detail = summary
        result.passed = result.score >= 0.8 and result.regression_ok

    result.duration_seconds = (datetime.now(timezone.utc) - started).total_seconds()

    if keep:
        result.detail += f"  [workdir {workdir}]"
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    return result


def print_report(results: list[Result]) -> None:
    header = f"{'task':<26}{'oracle':<9}{'score':>7}{'regress':>9}{'turns':>7}{'secs':>7}{'cost':>9}"
    print()
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.task_id[:24]:<26}{r.oracle:<9}{r.score:>7.2f}"
            f"{'ok' if r.regression_ok else 'FAIL':>9}{r.turns:>7}"
            f"{r.duration_seconds:>7.0f}{r.total_cost_usd:>9.3f}"
        )
    print("-" * len(header))
    passed = sum(1 for r in results if r.passed)
    total_cost = sum(r.total_cost_usd for r in results)
    print(f"{passed}/{len(results)} passed · ${total_cost:.2f} total")
    print()
    for r in results:
        if r.detail:
            print(f"  {r.task_id}: {r.detail}")
        if r.agent_error:
            print(f"  {r.task_id}: agent error — {r.agent_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", help="run only tasks whose id starts with this")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, spend nothing")
    parser.add_argument("--keep", action="store_true", help="leave working directories in place")
    parser.add_argument("--report", type=Path, default=HARNESS_DIR / "report.json")
    args = parser.parse_args()

    directories = sorted(d for d in TASKS_DIR.iterdir() if (d / "task.json").is_file())
    if args.task:
        directories = [d for d in directories if d.name.startswith(args.task)]
    if not directories:
        raise SystemExit("no matching tasks")

    tasks = [Task.load(d) for d in directories]

    if args.dry_run:
        print(f"{len(tasks)} tasks against {SAMPLE_APP}\n")
        for task in tasks:
            verification = (
                ", ".join(task.held_out_tests) if task.oracle == "tests" else task.rubric
            )
            print(f"  {task.id}")
            print(f"    oracle       {task.oracle} ({verification})")
            print(f"    regression   {', '.join(task.regression_tests) or 'none'}")
            if task.expected_outcome:
                print(f"    expects      {task.expected_outcome}")
            print(f"    prompt       {task.prompt[:96]}...")
            print()
        return

    results = [evaluate(task, args.keep) for task in tasks]
    print_report(results)

    args.report.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "agent_model": AGENT_MODEL,
                "judge_model": JUDGE_MODEL,
                "results": [r.__dict__ for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"report written to {args.report}")


if __name__ == "__main__":
    main()
