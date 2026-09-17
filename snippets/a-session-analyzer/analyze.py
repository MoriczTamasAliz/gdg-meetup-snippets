"""Turn local Claude Code session transcripts into cost and context reports.

Reads the JSONL files Claude Code already writes to ~/.claude/projects and
reports, per session: spend by token class, prompt-cache hit rate, how much
of the cache was written at each TTL, tool usage, how much went to subagents,
and how the prompt grew turn by turn.

Subagents write their own transcripts, nested under the parent session:

    projects/<project>/<session>.jsonl                          main thread
    projects/<project>/<session>/subagents/agent-*.jsonl        subagent
    projects/<project>/<session>/subagents/workflows/*/*.jsonl  workflow agent

A naive scan of the top level finds only the first of those. On this machine
that would have missed 471 of 541 transcripts, so subagent spend is invisible
unless you go looking for it.

Nothing leaves the machine and no API key is needed.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PRICING_PATH = Path(__file__).with_name("pricing.json")
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Locally generated turns that were never billed.
UNBILLED_MODELS = {"<synthetic>", None}


@dataclass
class Session:
    session_id: str
    path: Path
    subagent_files: int = 0
    subagent_cost_usd: float = 0.0
    subagent_turns: int = 0
    models: Counter = field(default_factory=Counter)
    tools: Counter = field(default_factory=Counter)
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    turns: int = 0
    sidechain_turns: int = 0
    prompt_sizes: list[int] = field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    cost_usd: float = 0.0

    @property
    def cache_write_tokens(self) -> int:
        return self.cache_write_5m + self.cache_write_1h

    @property
    def total_prompt_tokens(self) -> int:
        """Claude Code bills input, cache reads and cache writes separately."""
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def cache_hit_rate(self) -> float:
        if not self.total_prompt_tokens:
            return 0.0
        return self.cache_read_tokens / self.total_prompt_tokens

    @property
    def wall_minutes(self) -> float:
        if not self.first_seen or not self.last_seen:
            return 0.0
        return (self.last_seen - self.first_seen).total_seconds() / 60

    @property
    def primary_model(self) -> str:
        return self.models.most_common(1)[0][0] if self.models else "unknown"

    @property
    def subagent_cost_share(self) -> float:
        return self.subagent_cost_usd / self.cost_usd if self.cost_usd else 0.0


def load_pricing(path: Path = PRICING_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def turn_cost(usage: dict, model: str, pricing: dict) -> float:
    rates = pricing["models"].get(model)
    if rates is None:
        return 0.0
    multipliers = pricing["cache_multipliers"]
    per_token_in = rates["input"] / 1_000_000
    per_token_out = rates["output"] / 1_000_000
    creation = usage.get("cache_creation") or {}
    return (
        usage.get("input_tokens", 0) * per_token_in
        + usage.get("output_tokens", 0) * per_token_out
        + usage.get("cache_read_input_tokens", 0) * per_token_in * multipliers["read"]
        + creation.get("ephemeral_5m_input_tokens", 0) * per_token_in * multipliers["write_5m"]
        + creation.get("ephemeral_1h_input_tokens", 0) * per_token_in * multipliers["write_1h"]
    )


def parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_session(session_id: str, paths: list[Path], pricing: dict) -> Session:
    session = Session(session_id=session_id, path=paths[0])
    for path in paths:
        is_subagent = "subagents" in path.parts
        if is_subagent:
            session.subagent_files += 1
        _accumulate(session, path, pricing, is_subagent)
    return session


def _accumulate(session: Session, path: Path, pricing: dict, is_subagent: bool) -> None:
    with path.open(encoding="utf-8", errors="replace") as handle:
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

            message = record.get("message") or {}
            model = message.get("model")
            if model in UNBILLED_MODELS:
                continue

            session.turns += 1
            session.models[model] += 1
            if is_subagent or record.get("isSidechain"):
                session.sidechain_turns += 1
                if is_subagent:
                    session.subagent_turns += 1

            timestamp = parse_timestamp(record.get("timestamp"))
            if timestamp:
                session.first_seen = min(session.first_seen or timestamp, timestamp)
                session.last_seen = max(session.last_seen or timestamp, timestamp)

            for block in message.get("content") or []:
                if block.get("type") == "tool_use":
                    session.tools[block.get("name", "unknown")] += 1

            usage = message.get("usage") or {}
            creation = usage.get("cache_creation") or {}
            session.input_tokens += usage.get("input_tokens", 0)
            session.output_tokens += usage.get("output_tokens", 0)
            session.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
            session.cache_write_5m += creation.get("ephemeral_5m_input_tokens", 0)
            session.cache_write_1h += creation.get("ephemeral_1h_input_tokens", 0)
            session.thinking_tokens += (usage.get("output_tokens_details") or {}).get(
                "thinking_tokens", 0
            )
            if not is_subagent:
                session.prompt_sizes.append(
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )

            cost = turn_cost(usage, model, pricing)
            session.cost_usd += cost
            if is_subagent:
                session.subagent_cost_usd += cost


def session_id_for(path: Path, projects_dir: Path) -> str:
    """The session a transcript belongs to, whether it is the main thread or a subagent."""
    parts = path.relative_to(projects_dir).parts
    # <project>/<session>.jsonl  ->  the stem; anything deeper  ->  the directory.
    return Path(parts[1]).stem if len(parts) == 2 else parts[1]


def discover_sessions(projects_dir: Path) -> dict[str, list[Path]]:
    """Group every transcript, including nested subagent ones, by parent session."""
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in projects_dir.rglob("*.jsonl"):
        try:
            grouped[session_id_for(path, projects_dir)].append(path)
        except (ValueError, IndexError):
            continue
    for paths in grouped.values():
        paths.sort(key=lambda p: ("subagents" in p.parts, p.name))
    return dict(
        sorted(
            grouped.items(),
            key=lambda item: max(p.stat().st_mtime for p in item[1]),
            reverse=True,
        )
    )


def format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.0f}k"
    return str(count)


def print_summary(sessions: list[Session]) -> None:
    header = (
        f"{'session':<14}{'model':<18}{'turns':>6}{'prompt':>9}{'out':>8}"
        f"{'cache hit':>11}{'subagent':>10}{'mins':>7}{'cost':>9}"
    )
    print(header)
    print("-" * len(header))
    for session in sessions:
        print(
            f"{session.session_id[:12]:<14}"
            f"{session.primary_model[:16]:<18}"
            f"{session.turns:>6}"
            f"{format_tokens(session.total_prompt_tokens):>9}"
            f"{format_tokens(session.output_tokens):>8}"
            f"{session.cache_hit_rate:>10.0%}"
            f"{(f'{session.subagent_cost_share:.0%}' if session.subagent_files else '-'):>10}"
            f"{session.wall_minutes:>7.0f}"
            f"{session.cost_usd:>9.2f}"
        )
    print("-" * len(header))
    total = sum(s.cost_usd for s in sessions)
    tokens = sum(s.total_prompt_tokens for s in sessions)
    print(f"{len(sessions)} sessions · {format_tokens(tokens)} prompt tokens · ${total:.2f}")


def print_detail(session: Session) -> None:
    print(f"session      {session.session_id}")
    print(f"file         {session.path}")
    print(f"model        {', '.join(f'{m} x{n}' for m, n in session.models.most_common())}")
    print(f"turns        {session.turns} ({session.subagent_turns} in "
          f"{session.subagent_files} subagent transcripts)")
    print(f"wall time    {session.wall_minutes:.0f} min")
    print()
    print(f"input        {session.input_tokens:>12,}")
    print(f"cache read   {session.cache_read_tokens:>12,}  ({session.cache_hit_rate:.0%} of prompt)")
    print(f"cache write  {session.cache_write_tokens:>12,}  "
          f"({session.cache_write_5m:,} at 5m, {session.cache_write_1h:,} at 1h)")
    print(f"output       {session.output_tokens:>12,}  ({session.thinking_tokens:,} thinking)")
    print(f"cost         {session.cost_usd:>12.2f} USD")
    if session.subagent_files:
        print(f"  of which   {session.subagent_cost_usd:>12.2f} USD in subagents "
              f"({session.subagent_cost_share:.0%})")
    print()

    if session.tools:
        print("tool calls")
        for name, count in session.tools.most_common(10):
            print(f"  {name:<24}{count:>5}")
        print()

    if len(session.prompt_sizes) > 1:
        print("prompt size per turn")
        print_sparkline(session.prompt_sizes)


def print_sparkline(values: list[int], width: int = 60, height: int = 8) -> None:
    bucket_size = max(1, len(values) // width)
    buckets = [
        max(values[i : i + bucket_size])
        for i in range(0, len(values), bucket_size)
    ]
    peak = max(buckets) or 1
    blocks = " ▁▂▃▄▅▆▇█"
    line = "".join(blocks[min(len(blocks) - 1, round(v / peak * height))] for v in buckets)
    print(f"  {line}")
    print(f"  first turn {format_tokens(buckets[0])}  ->  peak {format_tokens(peak)}"
          f"  ->  last turn {format_tokens(buckets[-1])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects-dir", type=Path, default=DEFAULT_PROJECTS_DIR)
    parser.add_argument("--top", type=int, default=15, help="sessions to show")
    parser.add_argument("--session", help="show detail for one session id prefix")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    args = parser.parse_args()

    if not args.projects_dir.exists():
        raise SystemExit(f"no transcripts at {args.projects_dir}")

    pricing = load_pricing()
    grouped = discover_sessions(args.projects_dir)
    if args.session:
        grouped = {k: v for k, v in grouped.items() if k.startswith(args.session)}
        if not grouped:
            raise SystemExit(f"no session matching {args.session!r}")

    selected = list(grouped.items())[: args.top]
    sessions = [read_session(sid, paths, pricing) for sid, paths in selected]
    sessions = [s for s in sessions if s.turns]

    if args.json:
        print(json.dumps([
            {
                "session_id": s.session_id,
                "model": s.primary_model,
                "turns": s.turns,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "cache_read_tokens": s.cache_read_tokens,
                "cache_write_5m": s.cache_write_5m,
                "cache_write_1h": s.cache_write_1h,
                "cache_hit_rate": round(s.cache_hit_rate, 4),
                "subagent_transcripts": s.subagent_files,
                "subagent_cost_usd": round(s.subagent_cost_usd, 4),
                "wall_minutes": round(s.wall_minutes, 1),
                "cost_usd": round(s.cost_usd, 4),
                "tools": dict(s.tools),
            }
            for s in sessions
        ], indent=2))
    elif args.session:
        print_detail(sessions[0])
    else:
        print_summary(sessions)


if __name__ == "__main__":
    main()
