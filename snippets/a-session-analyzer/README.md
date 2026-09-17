# A — What your sessions actually cost

```bash
python analyze.py                    # recent sessions
python analyze.py --session a5c505bb # one session in detail
python analyze.py --json             # for piping somewhere
```

Reads `~/.claude/projects/**/*.jsonl`. No API key, no network, nothing leaves the
machine. Prices live in `pricing.json`; they are dated and you should check them.

## What it is for

Three things are hard to believe until you see them on your own data.

**Spend is input-dominated.** One session here: 12,880 input tokens against
753 million cache reads. You are not paying for generated code, you are paying to
re-send the conversation on every turn.

**Cache TTL decides the bill.** The report splits cache writes by TTL because the
lifetime is one hour on a subscription and five minutes on API billing. A break
longer than the TTL reprocesses the whole context at full rate.

**Subagent spend is invisible by default.** Subagents write their own transcripts,
nested a directory below the parent session:

```
projects/<project>/<session>.jsonl                          main thread
projects/<project>/<session>/subagents/agent-*.jsonl        subagent
projects/<project>/<session>/subagents/workflows/*/*.jsonl  workflow agent
```

On the machine this was written on, 471 of 541 transcripts were nested, and one
session had 99% of its $554 cost in 54 subagent transcripts. A top-level scan
would have called it $7.

## The prompt-growth plot

`--session` prints prompt size per turn:

```
  ▁▁▁▁▁▁▁▁▁▁▁▂▂▂▂▂▂▂▂▂▂▂▂▃▃▃▃▃▃▃▃▃▃▄▄▄▄▄▄▄▅▅▅▅▅▅▅▆▆▆▆▆▆▆▆▆▆▇▇▇▇▇▇▇█████
  first turn 35k  ->  peak 365k  ->  last turn 365k
```

That curve is the argument for `/clear`. Every turn after the growth sets in pays
for all of it.
