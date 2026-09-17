import pytest

from ledger.accounts import Account, AccountType, ChartOfAccounts


def test_debit_positive_types():
    assert Account("1000", "Cash", AccountType.ASSET).increases_with_debit
    assert Account("5000", "Rent", AccountType.EXPENSE).increases_with_debit
    assert not Account("4000", "Sales", AccountType.INCOME).increases_with_debit


def test_empty_code_rejected():
    with pytest.raises(ValueError):
        Account("", "Nameless", AccountType.ASSET)


def test_duplicate_code_rejected(chart):
    with pytest.raises(ValueError):
        chart.add(Account("1000", "Cash Again", AccountType.ASSET))


def test_lookup_and_membership(chart):
    assert chart.get("1000").name == "Cash"
    assert "1000" in chart
    assert "9999" not in chart
    assert len(chart) == 5


def test_missing_code_raises(chart):
    with pytest.raises(KeyError):
        chart.get("9999")
