"""Legacy money representation.

Float-backed and scheduled for removal. `money_v2` is the replacement; `report`
is the last module that still depends on this one.
"""


class Money:
    __slots__ = ("amount",)

    def __init__(self, amount: float = 0.0) -> None:
        self.amount = float(amount)

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - other.amount)

    def __neg__(self) -> "Money":
        return Money(-self.amount)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return abs(self.amount - other.amount) < 1e-9

    def __lt__(self, other: "Money") -> bool:
        return self.amount < other.amount

    def __hash__(self) -> int:
        return hash(round(self.amount, 9))

    def __repr__(self) -> str:
        return f"Money({self.amount:.2f})"

    def is_zero(self) -> bool:
        return abs(self.amount) < 1e-9

    def cents(self) -> int:
        return round(self.amount * 100)

    @classmethod
    def from_cents(cls, cents: int) -> "Money":
        return cls(cents / 100.0)
