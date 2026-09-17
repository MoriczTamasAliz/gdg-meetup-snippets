import pytest

from ledger.money import Money
from ledger.report import format_trial_balance, is_balanced, trial_balance


def test_trial_balance_sums_postings(chart, sale, purchase):
    balances = trial_balance([sale, purchase], chart)
    assert balances["1100"] == Money(250.00)
    assert balances["4000"] == Money(-250.00)
    assert balances["5000"] == Money(40.00)
    assert balances["1000"] == Money(-40.00)


def test_trial_balance_is_balanced(chart, sale, purchase):
    assert is_balanced(trial_balance([sale, purchase], chart))


def test_unknown_account_rejected(chart, sale):
    sale.postings[0] = type(sale.postings[0])("9999", debit=Money(250.00))
    with pytest.raises(KeyError):
        trial_balance([sale], chart)


def test_format_includes_every_account(chart, sale, purchase):
    output = format_trial_balance(trial_balance([sale, purchase], chart), chart)
    assert len(output.splitlines()) == len(chart)
    assert "Cash" in output
