from datetime import date

import pytest

from ledger.accounts import Account, AccountType, ChartOfAccounts
from ledger.entry import Posting, Transaction
from ledger.money import Money


@pytest.fixture
def chart() -> ChartOfAccounts:
    return ChartOfAccounts(
        [
            Account("1000", "Cash", AccountType.ASSET),
            Account("1100", "Accounts Receivable", AccountType.ASSET),
            Account("2000", "Accounts Payable", AccountType.LIABILITY),
            Account("4000", "Sales", AccountType.INCOME),
            Account("5000", "Office Supplies", AccountType.EXPENSE),
        ]
    )


@pytest.fixture
def sale() -> Transaction:
    return Transaction(
        date=date(2026, 1, 15),
        description="Invoice 001",
        postings=[
            Posting("1100", debit=Money(250.00)),
            Posting("4000", credit=Money(250.00)),
        ],
    )


@pytest.fixture
def purchase() -> Transaction:
    return Transaction(
        date=date(2026, 1, 16),
        description="Printer paper",
        postings=[
            Posting("5000", debit=Money(40.00)),
            Posting("1000", credit=Money(40.00)),
        ],
    )
