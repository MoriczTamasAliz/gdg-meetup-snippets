# AI Stories from the Trenches — working examples

Companion repository for a talk on staying in control of coding agents, measuring
what they cost, and choosing how much to delegate.

Everything here runs. The numbers in the talk came from running it.

## What's inside

```
sampleapp/                  a small double-entry ledger — the thing agents modify
snippets/
  a-session-analyzer/       what your agent sessions actually cost, from local transcripts
  b-eval-harness/           five golden tasks scored against your own repo
  c-guardrails/             a PreToolUse hook that refuses what instructions cannot prevent
  d-change-report/          a Stop hook that writes a review artifact from the transcript
  f-otel/                   telemetry wiring, two paths, no code
  g-cost-per-pr/            joining agent spend to merged pull requests
  j-context-scoping/        the same project context, before and after
.claude/                    live hooks and permissions — c and d are switched on
```

## Requirements

Python 3.10 or later and Claude Code. Nothing else: the sample app and every
snippet run on the standard library alone.

```bash
uv sync                          # or: python -m pytest sampleapp/tests -q
python -m pytest -q              # 40 tests, all green on a fresh clone
```

Snippet A works offline on transcripts you already have. Snippet B spends real
money — about $2 for the full set.

## Start here

**`snippets/a-session-analyzer`** reads the JSONL files Claude Code already wrote
to `~/.claude/projects` and tells you what your own sessions cost. No API key, no
setup, and the answer is usually surprising:

```
$ python analyze.py --session a5c505bb

turns        6440 (6401 in 54 subagent transcripts)
input              12,880
cache read    753,080,890  (98% of prompt)
cost               553.66 USD
  of which         546.22 USD in subagents (99%)
```

Two things that session shows. Spend is input-dominated and cache-served, not
paid for generated code. And subagent transcripts are nested one directory down,
so a scan of the top level would have reported about $7 for a $554 session.

## Talk section → snippet

| Section | Snippets |
|---|---|
| Staying in control of your agents | `c-guardrails`, `d-change-report` |
| Assessing agentic cost and performance | `a-session-analyzer`, `b-eval-harness`, `f-otel`, `g-cost-per-pr` |
| Finding the right level of abstraction | `j-context-scoping` |

## The eval harness, in one paragraph

Public coding benchmarks stopped being useful signal during 2026 — OpenAI
retired SWE-bench Verified in February after finding test-design flaws in 59% of
the hard tasks it audited, and Databricks built an internal benchmark instead
because public tasks leak into training data and say nothing about your codebase.
`snippets/b-eval-harness` is the small version of what Databricks did: five tasks
drawn from this repo, scored by executing tests that were held back from the
agent, plus a rubric judge where no mechanical oracle exists. A real run:

```
task                      oracle     score  regress  turns   secs     cost
--------------------------------------------------------------------------
001-decimal-migration     tests       1.00       ok     24     52    0.249
002-multi-currency        tests       1.00       ok      9     28    0.170
003-error-messages        rubric      1.00       ok     16     55    0.381
004-document-invariant    rubric      0.86       ok      4     56    0.404
005-make-it-faster        rubric      0.17       ok     34    160    0.744
--------------------------------------------------------------------------
4/5 passed · $1.95 total
```

Task 005 is designed to fail. It asks the agent to make the ledger faster with no
benchmark, no profile and no evidence anything is slow; the correct answer is to
say so and ask. The agent rewrote two hot paths instead, and it was the most
expensive task in the set. An all-green eval teaches nothing.

## Provenance

Figures quoted in the snippet docstrings and comments come from named public
sources — METR, Databricks, LangChain, LinearB, GitClear, the Cloud Security
Alliance, and Anthropic's own documentation. Where a claim is one this repository
could not verify, it says so rather than rounding it into a fact.
