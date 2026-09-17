"""Held out during the run, patched in afterwards. The agent never sees this."""

from datetime import date
from decimal import Decimal

from ledger.accounts import Account, AccountType, ChartOfAccounts
from ledger.entry import Posting, Transaction
from ledger.money_v2 import Money
from ledger.report import trial_balance


def build_chart() -> ChartOfAccounts:
    return ChartOfAccounts(
        [
            Account("1000", "Cash", AccountType.ASSET),
            Account("4000", "Sales", AccountType.INCOME),
        ]
    )


def penny_transactions(count: int) -> list[Transaction]:
    return [
        Transaction(
            date=date(2026, 1, 1),
            description=f"penny {index}",
            postings=[
                Posting("1000", debit=Money("0.01")),
                Posting("4000", credit=Money("0.01")),
            ],
        )
        for index in range(count)
    ]


def test_repeated_addition_is_exact():
    balances = trial_balance(penny_transactions(1000), build_chart())
    assert balances["1000"].amount == Decimal("10.00")
    assert balances["4000"].amount == Decimal("-10.00")


def test_balances_are_decimal_backed():
    balances = trial_balance(penny_transactions(3), build_chart())
    assert isinstance(balances["1000"].amount, Decimal)
