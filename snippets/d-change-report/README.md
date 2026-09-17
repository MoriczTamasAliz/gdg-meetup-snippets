# D — A review artifact the agent cannot flatter itself with

Already wired up as a `Stop` hook in `.claude/settings.json`. After a session it
writes `.claude/change-reports/<session>.md`.

## The idea, and the honest caveat

The intuition is obvious: don't hand a reviewer 400 lines, hand them the
decisions. What changed, what was assumed, what was tried and rejected, what was
deliberately not done.

**I could not find a study showing this reduces reviewer effort.** It is the
right shape and nobody has measured it. Treat it as a practice with a good
argument behind it, not as an evidence-backed one.

## The part that is actually a contribution

*Where the summary comes from.*

Ask the agent what it did and you get a fluent account of work that may not have
happened — the one failure mode LLMs are best at, and exactly the one a reviewer
reading the summary instead of the diff will not catch. Tian Pan's write-up of
the "rationale gap" puts it well: the agent discards the ticket, the failed
attempts and the rejected approaches, then writes *"Fixes the bug in module X."*

So this reads the transcript instead. Every section is a fact about what was
executed:

- files changed, with edit counts — four or more edits to one file gets flagged,
  because that usually means the agent was struggling
- commands run, and which failed
- whether any test command ran at all
- **what did not succeed** — calls that returned an error, which is the factual
  version of "what I didn't do"
- **read but not changed** — files inspected and left alone, where an expected
  change might be missing

The agent's own summary appears once, at the end, labelled unverified.

## Known limitation

File writes made through shell redirection (`cat > file <<'EOF'`) are counted as
commands, not as file changes, because the transcript records them as `Bash`.
A session that writes files that way will report "0 files changed" and list the
redirects under commands. That is honest about what the transcript contains, but
it is a gap worth knowing about before you trust the file count.
