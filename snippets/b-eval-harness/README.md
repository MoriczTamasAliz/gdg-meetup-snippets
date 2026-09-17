# B — Five golden tasks, scored against your own repo

```bash
python run_eval.py --dry-run     # the plan, costs nothing
python run_eval.py               # the whole set, about $2
python run_eval.py --task 001    # one task
python run_eval.py --keep        # leave the working directories behind
```

Needs Claude Code on PATH. Each run copies `sampleapp/` to a temporary directory,
drives the agent headlessly, then scores the result.

`sample-report.json` is a committed real run, so you can see the output shape
without spending anything.

## Why not a public benchmark

OpenAI stopped reporting SWE-bench Verified in February 2026: an audit of 138
hard tasks found 59.4% had flaws in the test design, and models were solving
"nearly impossible" problems using answers absent from the problem statement.
Anything trained on GitHub after mid-2024 has plausibly seen the questions and
the answers.

Databricks reached the same conclusion from the other direction and built an
internal benchmark, because public results "weren't representative for our
codebase". They scored by executing held-out tests rather than by judging, and
blocked agents from reading git history to recover the implementation. This is
that, small enough to read in one sitting.

## Task structure

Four parts each, following Terminal-Bench: an instruction, an environment, a
programmatic verification, and a reference for what good looks like.

| Task | Oracle | What it tests |
|---|---|---|
| 001-decimal-migration | held-out tests | a real migration with a dependency chain |
| 002-multi-currency | held-out tests | adding behaviour without breaking existing tests |
| 003-error-messages | rubric | judgement, where no mechanical oracle exists |
| 004-document-invariant | rubric | explaining a domain rule to a newcomer |
| 005-make-it-faster | rubric | **designed to fail** |

Held-out tests live in `tasks/*/verify/` and are patched in only after the agent
has finished. They are excluded from this repo's own `pytest` run because they
are supposed to fail against the unmodified app.

## The task that is supposed to fail

005 asks the agent to make the ledger faster. There is no benchmark, no profile,
and no evidence anything is slow. The correct behaviour is to notice that and ask.

In the committed run the agent rewrote two hot paths instead, scored 0.17, and
was the most expensive task in the set at $0.744 and 34 turns — more money and
more turns than either real migration. That is the point of including it. An
all-green eval report teaches nothing, and the failure mode worth catching is not
bad code, it is confident action on an underspecified request.

Google's harness-engineering write-up calls this class of check a **behavioural
evaluation**: assert on what the agent does — whether it asks a clarifying
question, whether it verifies before declaring completion — rather than only on
the final artifact.

## Honest limitations

- **Nondeterministic.** The same task varied between 9 and 43 turns across runs
  here. A single run is an anecdote; gate on batches, not on one result.
- **Held-out tests only cover what tests can express.** They say nothing about
  whether the design is good.
- **The judge is a model.** Validate it against your own reading before trusting
  a score, and keep the rubrics specific enough that disagreement is visible.
