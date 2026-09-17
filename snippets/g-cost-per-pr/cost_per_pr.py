"""Join agent spend to delivered work.

Everyone agrees cost per merged PR is the metric that matters. Faros puts it
first in their staged ladder — and then puts first-pass success and defect
escape rate one stage further out, behind "session-to-PR linking", because
nothing ships that join.

This is the join. Claude Code writes `cwd` and `gitBranch` into every transcript
turn, so session spend can be attributed to a branch, and a branch can be
matched to the merge commit that landed it.

    python cost_per_pr.py --repo ~/work/service
    python cost_per_pr.py --repo . --since 2026-08-01

Subagent transcripts are nested under the parent session and are counted here.
Skipping them is not a rounding error: on the machine this was written on, one
session's subagents accounted for 99% of its cost.

The numbers are honest about what they are: spend attributed to a branch by the
working directory the agent ran in, not a causal claim that the money produced
the diff.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MERGE_SUBJECT = re.compile(r"Merge pull request #(\d+) from [^/]+/(\S+)")
PRICING_PATH = Path(__file__).parents[1] / "a-session-analyzer" / "pricing.json"


@dataclass
class BranchSpend:
    branch: str
    cost_usd: float = 0.0
    sessions: set[str] = field(default_factory=set)
    turns: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


@dataclass
class Merge:
    sha: str
    pr_number: str | None
    branch: str
    subject: str
    merged_at: datetime
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


def load_pricing() -> dict:
    return json.loads(PRICING_PATH.read_text(encoding="utf-8"))


def turn_cost(usage: dict, model: str, pricing: dict) -> float:
    rates = pricing["models"].get(model)
    if rates is None:
        return 0.0
    multipliers = pricing["cache_multipliers"]
    per_in = rates["input"] / 1_000_000
    per_out = rates["output"] / 1_000_000
    creation = usage.get("cache_creation") or {}
    return (
        usage.get("input_tokens", 0) * per_in
        + usage.get("output_tokens", 0) * per_out
        + usage.get("cache_read_input_tokens", 0) * per_in * multipliers["read"]
        + creation.get("ephemeral_5m_input_tokens", 0) * per_in * multipliers["write_5m"]
        + creation.get("ephemeral_1h_input_tokens", 0) * per_in * multipliers["write_1h"]
    )


def parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def collect_branch_spend(projects_dir: Path, repo: Path, pricing: dict) -> dict[str, BranchSpend]:
    repo = repo.resolve()
    spend: dict[str, BranchSpend] = {}

    # rglob, not glob: subagent transcripts are nested under the parent session
    # directory, and on a machine using subagents heavily they are most of the spend.
    for transcript in projects_dir.rglob("*.jsonl"):
        with transcript.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") != "assistant":
                    continue

                cwd = record.get("cwd")
                if not cwd or not _within(Path(cwd), repo):
                    continue

                branch = record.get("gitBranch") or "(detached)"
                message = record.get("message") or {}
                model = message.get("model")
                if model in {"<synthetic>", None}:
                    continue

                entry = spend.setdefault(branch, BranchSpend(branch=branch))
                entry.cost_usd += turn_cost(message.get("usage") or {}, model, pricing)
                entry.sessions.add(transcript.stem)
                entry.turns += 1

                timestamp = parse_timestamp(record.get("timestamp"))
                if timestamp:
                    entry.first_seen = min(entry.first_seen or timestamp, timestamp)
                    entry.last_seen = max(entry.last_seen or timestamp, timestamp)

    return spend


def _within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return result.stdout


def collect_merges(repo: Path, since: str | None) -> list[Merge]:
    args = ["log", "--merges", "--date=iso-strict", "--format=%H%x1f%ad%x1f%s"]
    if since:
        args.append(f"--since={since}")

    merges: list[Merge] = []
    for line in git(repo, *args).splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, raw_date, subject = parts
        merged_at = parse_timestamp(raw_date)
        if merged_at is None:
            continue
        match = MERGE_SUBJECT.search(subject)
        pr_number, branch = (match.group(1), match.group(2)) if match else (None, subject)
        merge = Merge(sha=sha, pr_number=pr_number, branch=branch,
                      subject=subject, merged_at=merged_at)
        _attach_diffstat(repo, merge)
        merges.append(merge)
    return merges


def _attach_diffstat(repo: Path, merge: Merge) -> None:
    stat = git(repo, "show", "--shortstat", "--format=", merge.sha).strip()
    files = re.search(r"(\d+) files? changed", stat)
    added = re.search(r"(\d+) insertions?", stat)
    removed = re.search(r"(\d+) deletions?", stat)
    merge.files_changed = int(files.group(1)) if files else 0
    merge.insertions = int(added.group(1)) if added else 0
    merge.deletions = int(removed.group(1)) if removed else 0


def report_by_pr(merges: list[Merge], spend: dict[str, BranchSpend]) -> None:
    header = f"{'pr':<8}{'branch':<34}{'cost':>9}{'turns':>7}{'files':>7}{'+/-':>12}{'$/100 LOC':>11}"
    print(header)
    print("-" * len(header))
    matched = 0
    for merge in merges:
        entry = spend.get(merge.branch)
        cost = entry.cost_usd if entry else 0.0
        turns = entry.turns if entry else 0
        if entry:
            matched += 1
        churn = merge.insertions + merge.deletions
        per_loc = f"{cost / churn * 100:.2f}" if churn and cost else "-"
        print(
            f"{('#' + merge.pr_number) if merge.pr_number else '-':<8}"
            f"{merge.branch[:32]:<34}{cost:>9.2f}{turns:>7}{merge.files_changed:>7}"
            f"{('+%d/-%d' % (merge.insertions, merge.deletions)):>12}{per_loc:>11}"
        )
    print("-" * len(header))
    total = sum(spend.get(m.branch, BranchSpend('')).cost_usd for m in merges)
    print(f"{len(merges)} merges, {matched} with attributable agent spend, ${total:.2f}")
    if matched < len(merges):
        print(
            f"{len(merges) - matched} merges had no matching session. Agent work done on a "
            "differently-named local branch, or before transcripts were retained, is invisible here."
        )


def report_by_branch(spend: dict[str, BranchSpend]) -> None:
    header = f"{'branch':<38}{'cost':>9}{'sessions':>10}{'turns':>7}{'days':>7}"
    print(header)
    print("-" * len(header))
    for entry in sorted(spend.values(), key=lambda e: e.cost_usd, reverse=True):
        days = 0.0
        if entry.first_seen and entry.last_seen:
            days = (entry.last_seen - entry.first_seen).total_seconds() / 86400
        print(
            f"{entry.branch[:36]:<38}{entry.cost_usd:>9.2f}"
            f"{len(entry.sessions):>10}{entry.turns:>7}{days:>7.1f}"
        )
    print("-" * len(header))
    print(f"${sum(e.cost_usd for e in spend.values()):.2f} across {len(spend)} branches")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--projects-dir", type=Path, default=DEFAULT_PROJECTS_DIR)
    parser.add_argument("--since", help="git --since expression, e.g. 2026-08-01")
    parser.add_argument("--by-branch", action="store_true",
                        help="skip the merge join and report branches directly")
    args = parser.parse_args()

    if not (args.repo / ".git").exists():
        raise SystemExit(f"{args.repo} is not a git repository")

    spend = collect_branch_spend(args.projects_dir, args.repo, load_pricing())
    if not spend:
        raise SystemExit(f"no agent sessions found with a working directory inside {args.repo}")

    if args.by_branch:
        report_by_branch(spend)
        return

    merges = collect_merges(args.repo, args.since)
    if not merges:
        print("No merge commits found, so there are no PRs to join to. Branch view instead:\n")
        report_by_branch(spend)
        return

    report_by_pr(merges, spend)


if __name__ == "__main__":
    main()
