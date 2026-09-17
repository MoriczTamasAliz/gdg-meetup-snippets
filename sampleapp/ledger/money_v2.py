"""Decimal-backed money. The migration target for `money`.

Amounts are quantised to two places using banker's rounding, so repeated
addition of small amounts stays exact.
"""

from decimal import Decimal, ROUND_HALF_EVEN

CENTS = Decimal("0.01")


class Money:
    __slots__ = ("amount",)

    def __init__(self, amount: "Decimal | int | str | float" = 0) -> None:
        self.amount = Decimal(str(amount)).quantize(CENTS, rounding=ROUND_HALF_EVEN)

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - other.amount)

    def __neg__(self) -> "Money":
        return Money(-self.amount)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount

    def __lt__(self, other: "Money") -> bool:
        return self.amount < other.amount

    def __hash__(self) -> int:
        return hash(self.amount)

    def __repr__(self) -> str:
        return f"Money({self.amount})"

    def is_zero(self) -> bool:
        return self.amount == 0

    def cents(self) -> int:
        return int(self.amount * 100)

    @classmethod
    def from_cents(cls, cents: int) -> "Money":
        return cls(Decimal(cents) / 100)
