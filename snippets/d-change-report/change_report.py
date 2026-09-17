"""Stop hook: write a review artifact derived from the transcript.

The obvious way to get a change summary is to ask the agent what it did. That
produces a fluent account of work that may not have happened, which is the one
failure mode an LLM is best at and a reviewer reading the summary instead of
the diff will not catch.

So this reads the transcript instead. Every line below is a fact about what
was executed: which files were edited and how often, which commands ran, which
calls failed, and which files were read but never changed. The agent's own
narrative appears once, clearly labelled, at the end.

Wire it up in .claude/settings.json:

    {"hooks": {"Stop": [{"hooks": [{"type": "command",
      "command": "python3 $CLAUDE_PROJECT_DIR/snippets/d-change-report/change_report.py"}]}]}}
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
READ_TOOLS = {"Read", "NotebookRead"}
TEST_MARKERS = ("pytest", "unittest", "npm test", "go test", "cargo test")


class Trajectory:
    def __init__(self) -> None:
        self.edits: Counter[str] = Counter()
        self.reads: Counter[str] = Counter()
        self.commands: list[tuple[str, bool]] = []
        self.tools: Counter[str] = Counter()
        self.failures: list[tuple[str, str]] = []
        self.blocked: list[str] = []
        self.turns = 0
        self.first_seen: datetime | None = None
        self.last_seen: datetime | None = None
        self.final_message = ""

    @property
    def wall_minutes(self) -> float:
        if not self.first_seen or not self.last_seen:
            return 0.0
        return (self.last_seen - self.first_seen).total_seconds() / 60

    @property
    def touched_but_not_changed(self) -> list[str]:
        return sorted(set(self.reads) - set(self.edits))

    @property
    def test_runs(self) -> list[tuple[str, bool]]:
        """Match only the invocation line, so a heredoc body cannot look like a test run."""
        return [(c, ok) for c, ok in self.commands if any(m in c for m in TEST_MARKERS)]


def parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_trajectory(transcript_path: Path, project_dir: Path) -> Trajectory:
    trajectory = Trajectory()
    pending: dict[str, tuple[str, str]] = {}
    results: dict[str, bool] = {}
    records = []

    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    for record in records:
        for block in (record.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                results[block.get("tool_use_id", "")] = not block.get("is_error", False)

    for record in records:
        kind = record.get("type")
        if kind != "assistant":
            continue

        message = record.get("message") or {}
        if message.get("model") == "<synthetic>":
            continue
        trajectory.turns += 1

        timestamp = parse_timestamp(record.get("timestamp"))
        if timestamp:
            trajectory.first_seen = min(trajectory.first_seen or timestamp, timestamp)
            trajectory.last_seen = max(trajectory.last_seen or timestamp, timestamp)

        for block in message.get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                trajectory.final_message = block["text"].strip()
            if block.get("type") != "tool_use":
                continue

            name = block.get("name", "unknown")
            tool_input = block.get("input") or {}
            trajectory.tools[name] += 1
            succeeded = results.get(block.get("id", ""), True)

            if name in EDIT_TOOLS:
                trajectory.edits[relative(tool_input.get("file_path"), project_dir)] += 1
            elif name in READ_TOOLS:
                trajectory.reads[relative(tool_input.get("file_path"), project_dir)] += 1
            elif name == "Bash":
                trajectory.commands.append((invocation(tool_input.get("command")), succeeded))

            if not succeeded:
                detail = tool_input.get("command") or tool_input.get("file_path") or ""
                trajectory.failures.append((name, str(detail)[:120]))

    return trajectory


def invocation(command: str | None, limit: int = 120) -> str:
    """The first line of a command, which is what was actually invoked.

    Multi-line commands are usually a heredoc writing a file; the body is data,
    not something a reviewer needs, and it would otherwise flood the report.
    """
    first_line = (command or "").strip().splitlines()
    if not first_line:
        return ""
    text = first_line[0].strip()
    suffix = " …" if len(first_line) > 1 or len(text) > limit else ""
    return text[:limit] + suffix


def relative(path_text: str | None, project_dir: Path) -> str:
    if not path_text:
        return "(unknown)"
    try:
        return str(Path(path_text).resolve().relative_to(project_dir.resolve()))
    except (ValueError, OSError):
        return str(path_text)


def render(trajectory: Trajectory, session_id: str) -> str:
    out: list[str] = []
    add = out.append

    add(f"# Change report — session `{session_id[:12]}`")
    add("")
    add(f"_Derived from the session transcript, not from the agent's account of its work._")
    add("")
    add(f"- {trajectory.turns} turns over {trajectory.wall_minutes:.0f} minutes")
    add(f"- {len(trajectory.edits)} files changed, {sum(trajectory.edits.values())} edits")
    add(f"- {len(trajectory.commands)} commands run, {sum(1 for _, ok in trajectory.commands if not ok)} failed")
    add("")

    if trajectory.edits:
        add("## Files changed")
        add("")
        for path, count in trajectory.edits.most_common():
            churn = "  ← edited repeatedly, worth a closer look" if count >= 4 else ""
            add(f"- `{path}` ({count} edits){churn}")
        add("")

    tests = trajectory.test_runs
    add("## Verification")
    add("")
    if not tests:
        add("- **No test command was run in this session.**")
    else:
        for command, ok in tests:
            add(f"- {'PASS' if ok else 'FAIL'} `{command}`")
    add("")

    if trajectory.failures:
        add("## What did not succeed")
        add("")
        add("Calls that returned an error. These are the parts the agent worked around,")
        add("and they are where its summary is least likely to be complete.")
        add("")
        for name, detail in trajectory.failures[:15]:
            add(f"- `{name}` — {detail}")
        add("")

    if trajectory.touched_but_not_changed:
        add("## Read but not changed")
        add("")
        add("Files the agent inspected and left alone. If a change was expected in one")
        add("of these, that is a gap worth asking about.")
        add("")
        for path in trajectory.touched_but_not_changed[:15]:
            add(f"- `{path}`")
        add("")

    if trajectory.commands:
        add("## Commands")
        add("")
        add("```")
        for command, ok in trajectory.commands[:20]:
            add(f"{'' if ok else '# failed: '}{command}")
        add("```")
        add("")

    if trajectory.final_message:
        add("## The agent's own summary")
        add("")
        add("Unverified. Read it against the sections above rather than instead of them.")
        add("")
        for line in trajectory.final_message.splitlines()[:12]:
            add(f"> {line}")
        add("")

    return "\n".join(out)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    transcript_path = Path(event.get("transcript_path", ""))
    if not transcript_path.is_file():
        return

    project_dir = Path(event.get("cwd") or ".")
    session_id = event.get("session_id", transcript_path.stem)

    trajectory = read_trajectory(transcript_path, project_dir)
    report = render(trajectory, session_id)

    output_dir = project_dir / ".claude" / "change-reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{session_id[:12]}.md"
    destination.write_text(report, encoding="utf-8")

    print(json.dumps({"systemMessage": f"Change report written to {destination}"}))


if __name__ == "__main__":
    main()
