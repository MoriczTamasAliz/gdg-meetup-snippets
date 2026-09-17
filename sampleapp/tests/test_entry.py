from datetime import date

import pytest

from ledger.entry import Posting, Transaction
from ledger.money import Money


def test_posting_rejects_both_sides():
    with pytest.raises(ValueError):
        Posting("1000", debit=Money(1.00), credit=Money(1.00))


def test_posting_rejects_negative_amounts():
    with pytest.raises(ValueError):
        Posting("1000", debit=Money(-1.00))


def test_signed_value():
    assert Posting("1000", debit=Money(5.00)).signed() == Money(5.00)
    assert Posting("1000", credit=Money(5.00)).signed() == Money(-5.00)


def test_balanced_transaction_validates(sale):
    assert sale.is_balanced()
    sale.validate()


def test_unbalanced_transaction_rejected():
    transaction = Transaction(
        date=date(2026, 1, 1),
        description="Wrong",
        postings=[
            Posting("1100", debit=Money(100.00)),
            Posting("4000", credit=Money(90.00)),
        ],
    )
    assert not transaction.is_balanced()
    with pytest.raises(ValueError):
        transaction.validate()


def test_single_posting_rejected():
    transaction = Transaction(
        date=date(2026, 1, 1),
        description="Lonely",
        postings=[Posting("1000", debit=Money(0.00))],
    )
    with pytest.raises(ValueError):
        transaction.validate()
