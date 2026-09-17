from decimal import Decimal

from ledger.money_v2 import Money


def test_addition_is_exact_over_many_terms():
    total = Money()
    for _ in range(1000):
        total = total + Money("0.01")
    assert total.amount == Decimal("10.00")


def test_quantises_to_cents():
    assert Money("1.005").amount == Decimal("1.00")
    assert Money("1.015").amount == Decimal("1.02")


def test_accepts_int_str_and_decimal():
    assert Money(5).amount == Decimal("5.00")
    assert Money("5").amount == Decimal("5.00")
    assert Money(Decimal("5")).amount == Decimal("5.00")


def test_cents_roundtrip():
    assert Money("12.34").cents() == 1234
    assert Money.from_cents(1234) == Money("12.34")


def test_repr():
    assert repr(Money("3.5")) == "Money(3.50)"
