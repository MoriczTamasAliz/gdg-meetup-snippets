# Ledger service

This file is what a project context file looks like after eighteen months of
incidents. Every line was added by someone who had just been burned. Nothing was
ever removed. All of it loads into every session, including the ones where none
of it applies.

## Build and test

- Run tests with `python -m pytest tests -q` from the `sampleapp` directory.
- Never run the full suite with `-x`; we want the whole failure list.
- Coverage must not drop below 92%. Check with `pytest --cov=ledger`.
- If a test is flaky, quarantine it with `@pytest.mark.flaky` and open a ticket.
- Do not add `time.sleep` to tests. Use freezegun.
- Integration tests live in `tests/integration` and need the docker compose stack.
- The compose stack takes about 40 seconds to become healthy. Wait for it.
- If the compose stack fails to start, check whether port 5432 is already bound.
- On macOS the port is often taken by a stray Postgres from Homebrew.
- `brew services stop postgresql` fixes it.
- Windows developers should use WSL2; native Windows is not supported.
- The test database is recreated per run. Do not rely on state between tests.

## Git conventions

- Conventional Commits. `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Subject line lowercase, imperative, under 72 characters.
- No period at the end of the subject line.
- Body explains why, not what. The diff already says what.
- Reference the ticket as `Refs: LED-1234` in the footer.
- Squash merge only. We do not keep merge commits.
- Branch names are `type/LED-1234-short-description`.
- Never force-push to `main` or `release/*`.
- Rebase feature branches, do not merge main into them.
- Tags are `v<major>.<minor>.<patch>` and are created by CI, never by hand.

## Accounting domain rules

- Every transaction must balance: total debits equal total credits, exactly.
- Debits increase assets and expenses. Credits increase liabilities, equity and income.
- A posting carries either a debit or a credit. Never both. This is enforced in `Posting`.
- Amounts are never negative on a posting. Direction is expressed by which side it is on.
- Account codes are strings, not integers. `0100` is not `100`.
- The 1000 range is assets, 2000 liabilities, 3000 equity, 4000 income, 5000 expenses.
- Never invent an account code. If one is missing, ask.
- The trial balance must sum to zero across all accounts. If it does not, something is wrong.
- Rounding is banker's rounding, ROUND_HALF_EVEN, at two decimal places.
- Never use float for money. We had an incident. See the 2025-11 postmortem.
- Currency conversion happens at the boundary, never inside the ledger core.
- Fiscal year starts 1 April. Period 1 is April.
- Closing entries zero the income and expense accounts into retained earnings.
- Reversing entries are dated the first day of the following period.
- Accruals are reversed automatically; prepayments are not.
- VAT is posted to 2100 and is never netted against income.
- Intercompany balances must eliminate. If they do not, the consolidation is wrong.
- A journal that has been posted is immutable. Corrections are new journals.
- Never delete a transaction. Reverse it.
- The audit trail is append-only and is a compliance requirement, not a preference.

## Code style

- Python 3.11 or later.
- Type hints on every public function. Private helpers may omit them.
- Prefer dataclasses over dicts for structured data.
- Frozen dataclasses for value objects.
- `__slots__` on hot-path classes.
- No mutable default arguments. Use `field(default_factory=...)`.
- Imports: stdlib, third party, local. Blank line between groups.
- No wildcard imports.
- Line length 100. Enforced by ruff.
- Docstrings on modules and public classes. Not on obvious one-line functions.
- Comments explain why, never what.
- No commented-out code. Git remembers.
- Prefer early returns over nested conditionals.
- Avoid inheritance for code reuse. Compose.
- No metaclasses without a written justification in the PR.
- f-strings, not `%` or `.format()`.
- `pathlib.Path`, not `os.path`.
- Never catch bare `Exception` outside a top-level handler.
- Re-raise with `raise ... from` to keep the chain.

## Deployment

- Deploys go out Tuesday and Thursday, 10:00 CET. Never Friday.
- The release branch is cut Monday afternoon.
- A deploy needs two approvals, one from the on-call engineer.
- Run the migration dry-run against a production snapshot first.
- Migrations must be backwards compatible for one release.
- Never drop a column in the same release that stops writing to it.
- Feature flags default to off. Remove the flag within two releases.
- Canary is 5% for 30 minutes, then 50% for 30 minutes, then full.
- Roll back with `make rollback VERSION=<previous>`. Do not hand-edit.
- Post in #ledger-deploys before and after.
- The runbook is in Confluence under Ledger / Operations / Runbook.

## Incident history, kept because people forget

- 2025-04: float rounding produced a 0.03 discrepancy across 40,000 transactions.
  We now use Decimal everywhere. Do not undo this.
- 2025-07: a migration dropped an index and the month-end close took 14 hours.
  Always check query plans on migrations touching `postings`.
- 2025-09: a retry loop double-posted 1,200 journals. Idempotency keys are now
  mandatory on every write path.
- 2025-11: the float incident. See above. Read the postmortem before touching money.
- 2026-01: a feature flag left on for five months changed the VAT treatment silently.
  Flags are now removed within two releases, enforced in CI.
- 2026-03: an agent refactored `report.py` and quietly changed rounding direction.
  Any change to rounding needs an explicit test and a human sign-off.

## Review expectations

- PRs under 400 lines. Larger ones need a written reason in the description.
- Every PR states what was tested and what was not.
- Reviewers check the tests before the implementation.
- Domain logic changes need a second reviewer from the finance-platform group.
- Do not approve a PR you do not understand. Ask.
- A green build is necessary, not sufficient.

## Things agents specifically get wrong here

- Do not "simplify" the double-entry validation. It looks redundant. It is not.
- Do not add a caching layer to the trial balance without a benchmark.
- Do not convert `Posting` to a mutable dataclass to make a test easier.
- Do not add a dependency to solve something the stdlib does.
- Do not reformat files you did not otherwise change.
- Do not update the changelog; it is generated.
