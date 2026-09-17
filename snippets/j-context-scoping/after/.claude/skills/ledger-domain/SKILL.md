---
name: ledger-domain
description: Accounting rules for the ledger service — the double-entry invariant, the chart of accounts, rounding, period handling, and the incidents that produced each rule. Load when changing ledger logic, money handling, reporting or anything touching postings.
---

# Ledger domain rules

## The invariant

Every transaction balances: total debits equal total credits, exactly. Debits
increase assets and expenses; credits increase liabilities, equity and income. A
posting carries either a debit or a credit, never both, and amounts are never
negative — direction is expressed by which side the posting is on.

## Chart of accounts

Account codes are strings, not integers: `0100` is not `100`.

| Range | Type |
|---|---|
| 1000 | Assets |
| 2000 | Liabilities |
| 3000 | Equity |
| 4000 | Income |
| 5000 | Expenses |

Never invent a code. If one is missing, ask.

## Money

`Decimal`, quantised to two places with ROUND_HALF_EVEN. Never `float`.

Currency conversion happens at the boundary, never inside the ledger core.

## Periods

Fiscal year starts 1 April; period 1 is April. Closing entries zero income and
expense accounts into retained earnings. Reversing entries are dated the first
day of the following period. Accruals reverse automatically; prepayments do not.
VAT posts to 2100 and is never netted against income. Intercompany balances must
eliminate.

## Immutability

A posted journal cannot be edited. Reverse it with a new journal. The audit trail
is append-only and that is a compliance requirement, not a preference.

## Why these rules exist

- **2025-04** — float rounding produced a 0.03 discrepancy across 40,000
  transactions. Hence Decimal everywhere.
- **2025-07** — a migration dropped an index and month-end close took 14 hours.
  Check query plans on anything touching `postings`.
- **2025-09** — a retry loop double-posted 1,200 journals. Idempotency keys are
  mandatory on every write path.
- **2026-01** — a feature flag left on for five months silently changed VAT
  treatment. Flags are removed within two releases, enforced in CI.
- **2026-03** — an agent refactored `report.py` and quietly changed rounding
  direction. Any rounding change needs an explicit test and human sign-off.

## What gets changed by mistake

The double-entry validation looks redundant. It is not. Do not simplify it, do
not make `Posting` mutable to make a test easier, and do not add a cache to the
trial balance without a benchmark.
