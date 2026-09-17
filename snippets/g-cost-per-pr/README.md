# G — Joining spend to delivered work

```bash
python cost_per_pr.py --repo ~/work/service
python cost_per_pr.py --repo . --by-branch     # no merge commits needed
python -m pytest test_cost_per_pr.py -q        # 4 tests, on a fixture repo
```

## Why this is a snippet and not a product

Everyone agrees cost per merged PR is the metric that matters. Faros put it first
in their staged ladder of agentic metrics — and then put first-pass success rate,
agent-PR survival and defect escape rate one stage further out, gated behind
"session-to-PR linking". Nothing ships that link.

This is the link, and it is about 200 lines. Claude Code writes `cwd` and
`gitBranch` into every transcript turn, so session spend attributes to a branch,
and `git log --merges` maps a branch to the commit that landed it.

## What the numbers mean

Spend is attributed to a branch by the working directory the agent ran in. That
is an association, not a causal claim that the money produced the diff — a human
wrote some of it, and some sessions produced nothing that merged.

The report says how many merges it could not attribute, and why:

```
12 merges, 7 with attributable agent spend, $84.31
5 merges had no matching session. Agent work done on a differently-named local
branch, or before transcripts were retained, is invisible here.
```

Reporting the gap matters more than the headline. A cost-per-PR figure that
silently ignores a third of the merges is worse than no figure.

## Counting subagents

Subagent transcripts are nested under the parent session. Skipping them is not a
rounding error — on the machine this was written on, one session's subagents were
99% of its cost. There is a test for it.
