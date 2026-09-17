# F — Telemetry wiring

Claude Code emits OpenTelemetry metrics, events and (in beta) traces to any OTLP
endpoint. Everything below is configuration; there is no code to run.

Two paths are given. Pick one.

## What you get either way

| Metric | Unit | Attributes that matter |
|---|---|---|
| `claude_code.cost.usage` | USD | `model`, `query_source` (main/subagent/auxiliary), `agent.name`, `skill.name`, `mcp_server.name` |
| `claude_code.token.usage` | tokens | `type` (input/output/cacheRead/cacheCreation) + all of the above |
| `claude_code.code_edit_tool.decision` | count | `decision` (accept/reject), `language` |
| `claude_code.lines_of_code.count` | count | `type` (added/removed) |
| `claude_code.commit.count`, `claude_code.pull_request.count` | count | — |
| `claude_code.active_time.total` | seconds | `type` (user/cli) |

Because cost and tokens carry `agent.name`, `skill.name` and `mcp_server.name`,
spend is attributable to individual subagents, skills and MCP servers. That turns
"is this skill worth its context?" into a query.

The event stream adds `claude_code.tool_decision`, carrying `decision_source`
with values including `hook`. That is how you measure how often the guardrail in
snippet C actually blocked something — GitLab calls this metric "guardrail
interventions", and it is the one risk metric in their framework that is
directly instrumentable.

## Path 1 — no infrastructure (AWS CloudWatch)

AWS published this in June 2026. Metrics go straight from each developer's
machine to CloudWatch over OTLP; there is no collector and no sidecar. For 200
developers at 20 sessions a day they report ingestion at roughly $0.14/month,
free PromQL, free 15-month retention — under $15/month all in.

See `cloudwatch.env`.

## Path 2 — local stack (collector + Prometheus + Grafana)

`docker compose -f local-stack.yml up -d`, then `source local.env`. Grafana on
http://localhost:3000. Use this to see the data before deciding where it should
live permanently.

## Privacy, which is usually the blocker

Off by default, and redacted to `<REDACTED>` in the payload: prompt content,
assistant responses, tool parameters, tool output, raw API bodies. User-authored
skill, plugin and MCP server names are replaced with `custom`. What ships by
default is metadata — counts, durations, costs, decisions.

The flags that change this are listed in `content-logging.env`, switched off,
with a warning. They are how a team accidentally ships pasted credentials to its
observability backend.
