"""Held out during the run, patched in afterwards. The agent never sees this."""

import pytest

from ledger.money_v2 import Money


def test_defaults_to_eur():
    assert Money("1.00").currency == "EUR"


def test_carries_an_explicit_currency():
    assert Money("1.00", currency="USD").currency == "USD"


def test_same_currency_arithmetic_still_works():
    assert Money("1.00", currency="USD") + Money("2.50", currency="USD") == Money(
        "3.50", currency="USD"
    )


def test_mixed_currency_addition_is_rejected():
    with pytest.raises(ValueError):
        Money("1.00", currency="USD") + Money("1.00", currency="EUR")


def test_mixed_currency_subtraction_is_rejected():
    with pytest.raises(ValueError):
        Money("1.00", currency="USD") - Money("1.00", currency="EUR")


def test_equality_accounts_for_currency():
    assert Money("1.00", currency="USD") != Money("1.00", currency="EUR")
