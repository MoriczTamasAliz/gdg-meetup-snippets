from ledger.money import Money


def test_addition_and_subtraction():
    assert Money(10.00) + Money(2.50) == Money(12.50)
    assert Money(10.00) - Money(2.50) == Money(7.50)


def test_negation():
    assert -Money(5.00) == Money(-5.00)


def test_is_zero():
    assert Money(0.0).is_zero()
    assert not Money(0.01).is_zero()


def test_cents_roundtrip():
    assert Money(12.34).cents() == 1234
    assert Money.from_cents(1234) == Money(12.34)


def test_ordering():
    assert Money(1.00) < Money(2.00)


def test_repr():
    assert repr(Money(3.5)) == "Money(3.50)"
