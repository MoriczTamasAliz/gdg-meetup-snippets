# Ledger service

Python 3.11. Zero runtime dependencies — keep it that way.

## Working here

- Tests: `python -m pytest tests -q` from `sampleapp/`. Run the whole suite, not `-x`.
- Money is `Decimal`, never `float`. This is not a style preference; see the
  `ledger-domain` skill for why.
- A posted journal is immutable. Corrections are new journals, never edits.
- Ask before inventing an account code.

## Conventions

- Conventional Commits, lowercase imperative subject under 72 characters.
- Line length 100, enforced by ruff. Type hints on public functions.
- Comments explain why. The diff already says what.

## Before you change behaviour

- PRs over 400 lines need a stated reason.
- Changes to rounding, validation or the audit trail need an explicit test.
- No new dependencies without asking.

## Where the rest lives

- Accounting rules, the chart of accounts and the incident history that explains
  them: the `ledger-domain` skill.
- Release process, canary steps and rollback: the `release` skill.
- Running the suite and summarising failures: the `test-runner` subagent.
