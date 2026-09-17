"""Measure what a project's context discipline costs per session.

Everything in CLAUDE.md is re-sent on every request of every session, whether or
not it is relevant. Skills load only when invoked, and a subagent's output never
reaches the main thread at all. So the question for any given line is not "is
this true?" but "is this true in every session?".

    python measure.py

Token counts use the Anthropic SDK's count_tokens when it is available, which is
the only accurate way to count for Claude. Without it the script falls back to a
rough estimate and says so; the estimate is fine for seeing the shape of the
difference and useless for anything else.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5"


def count_tokens_exact(text: str) -> int | None:
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        response = client.messages.count_tokens(
            model=MODEL, messages=[{"role": "user", "content": text}]
        )
        return response.input_tokens
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    return round(len(text) / 3.6)


def measure(text: str) -> tuple[int, bool]:
    exact = count_tokens_exact(text)
    return (exact, True) if exact is not None else (estimate_tokens(text), False)


def read(*parts: str) -> str:
    path = HERE.joinpath(*parts)
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> None:
    before = read("before", "CLAUDE.md")
    after = read("after", "CLAUDE.md")
    domain_skill = read("after", ".claude", "skills", "ledger-domain", "SKILL.md")
    release_skill = read("after", ".claude", "skills", "release", "SKILL.md")
    subagent = read("after", ".claude", "agents", "test-runner.md")

    before_tokens, exact = measure(before)
    after_tokens, _ = measure(after)
    domain_tokens, _ = measure(domain_skill)
    release_tokens, _ = measure(release_skill)
    subagent_tokens, _ = measure(subagent)

    method = "counted with the Anthropic API" if exact else "ESTIMATED — install `anthropic` for real counts"

    print(f"Token counts {method}\n")
    print(f"{'':<34}{'tokens':>9}{'when it loads':>28}")
    print("-" * 71)
    print(f"{'before/CLAUDE.md':<34}{before_tokens:>9}{'every session':>28}")
    print("-" * 71)
    print(f"{'after/CLAUDE.md':<34}{after_tokens:>9}{'every session':>28}")
    print(f"{'  skill: ledger-domain':<34}{domain_tokens:>9}{'only when invoked':>28}")
    print(f"{'  skill: release':<34}{release_tokens:>9}{'only when invoked':>28}")
    print(f"{'  subagent: test-runner':<34}{subagent_tokens:>9}{'in its own context':>28}")
    print("-" * 71)

    saved = before_tokens - after_tokens
    share = saved / before_tokens if before_tokens else 0
    print(f"\nAlways-loaded context: {before_tokens} -> {after_tokens} tokens ({share:.0%} smaller)")
    print(f"Nothing was deleted. {domain_tokens + release_tokens + subagent_tokens} tokens moved "
          f"to load on demand instead of always.")

    print("\nWhy it compounds:")
    print("  The whole conversation is re-sent every turn, and every tool result")
    print("  starts another request carrying it again. A 60-turn session pays for")
    print(f"  the always-loaded part {60}x — {saved * 60:,} tokens of difference,")
    print("  most of it at the cached rate, all of it competing for attention with")
    print("  the thing you actually asked for.")

    print("\nThe test that decides where a line goes:")
    print("  Is this true in EVERY session? -> CLAUDE.md")
    print("  Is this true in SOME sessions? -> a skill")
    print("  Is this output nobody needs to read? -> a subagent")


if __name__ == "__main__":
    main()
