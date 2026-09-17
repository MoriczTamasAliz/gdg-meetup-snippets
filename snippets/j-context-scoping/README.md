# J — The same project, before and after

```bash
python measure.py
```

Install `anthropic` for exact token counts; without it the script estimates and
says so clearly. The estimate is fine for seeing the shape and useless for
anything else.

## What changed

Nothing was deleted. Everything moved to where it belongs.

```
                                     tokens               when it loads
-----------------------------------------------------------------------
before/CLAUDE.md                       1810               every session
-----------------------------------------------------------------------
after/CLAUDE.md                         304               every session
  skill: ledger-domain                  690           only when invoked
  skill: release                        273           only when invoked
  subagent: test-runner                 213          in its own context
-----------------------------------------------------------------------
```

`before/CLAUDE.md` is what a context file looks like after eighteen months of
incidents: every line added by someone who had just been burned, nothing ever
removed, all of it loaded into every session including the ones where none of it
applies.

## The test for where a line goes

- True in **every** session → `CLAUDE.md`
- True in **some** sessions → a skill
- Output **nobody needs to read** → a subagent

## Why it is worth doing twice over

Anthropic's own guidance is to keep `CLAUDE.md` under 200 lines. Two independent
reasons.

**Cost.** The conversation is re-sent every turn, and every batch of tool results
starts another request carrying it again. A 60-turn session pays for the
always-loaded part sixty times.

**Quality.** Chroma tested 18 production models across contexts from 10k to 500k
tokens and every one degraded as input grew — it is a property of attention, not
a gap training closes. Salesforce, running Claude Code across their whole
engineering org, put it in one line: *"Over-contexting degrades quality, not just
budget."* Their auto-compaction change alone cut all-engineering spend 24.8%.

This is the rare case with no trade-off to manage. The same edit buys both.
