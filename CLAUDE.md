# Agentic talk snippets

Working examples for a talk. Two rules that matter here:

- The sample app and every snippet run on the standard library alone. Do not add
  a dependency; if something needs one, say so rather than installing it.
- These files get read off a slide. Prefer the clear version over the clever one.

`sampleapp/` is a small double-entry ledger, and it is the thing agents modify in
the demos. Run its tests with `python -m pytest sampleapp/tests -q`.

The hooks in `.claude/settings.json` are live. `snippets/c-guardrails/guard.py`
will refuse tool calls that read credentials or reach unexpected hosts — that is
the demo, not a misconfiguration.
