"""Transactions and the double-entry invariant."""

from dataclasses import dataclass, field
from datetime import date

from .money import Money


@dataclass(frozen=True)
class Posting:
    account_code: str
    debit: Money = field(default_factory=Money)
    credit: Money = field(default_factory=Money)

    def __post_init__(self) -> None:
        if not self.debit.is_zero() and not self.credit.is_zero():
            raise ValueError("a posting carries either a debit or a credit, not both")
        if self.debit.amount < 0 or self.credit.amount < 0:
            raise ValueError("posting amounts must not be negative")

    def signed(self) -> Money:
        return self.debit - self.credit


@dataclass
class Transaction:
    date: date
    description: str
    postings: "list[Posting]"

    def total_debits(self) -> Money:
        total = Money()
        for posting in self.postings:
            total = total + posting.debit
        return total

    def total_credits(self) -> Money:
        total = Money()
        for posting in self.postings:
            total = total + posting.credit
        return total

    def is_balanced(self) -> bool:
        return (self.total_debits() - self.total_credits()).is_zero()

    def validate(self) -> None:
        if len(self.postings) < 2:
            raise ValueError("a transaction needs at least two postings")
        if not self.is_balanced():
            raise ValueError("unbalanced transaction")
