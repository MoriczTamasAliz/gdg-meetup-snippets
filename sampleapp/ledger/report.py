"""Trial balance reporting.

Still imports the legacy float-backed `money`; see EVAL-001.
"""

from .accounts import ChartOfAccounts
from .entry import Transaction
from .money import Money


def trial_balance(
    transactions: "list[Transaction]", chart: ChartOfAccounts
) -> "dict[str, Money]":
    balances = {code: Money() for code in chart.codes()}
    for transaction in transactions:
        transaction.validate()
        for posting in transaction.postings:
            if posting.account_code not in chart:
                raise KeyError(posting.account_code)
            balances[posting.account_code] += posting.signed()
    return balances


def is_balanced(balances: "dict[str, Money]") -> bool:
    total = Money()
    for amount in balances.values():
        total = total + amount
    return total.is_zero()


def format_trial_balance(balances: "dict[str, Money]", chart: ChartOfAccounts) -> str:
    lines = []
    for code in sorted(balances):
        account = chart.get(code)
        lines.append(f"{code:<8} {account.name:<28} {balances[code].amount:>12.2f}")
    return "\n".join(lines)
