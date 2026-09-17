"""Chart of accounts."""

from dataclasses import dataclass
from enum import Enum


class AccountType(Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


DEBIT_POSITIVE = frozenset({AccountType.ASSET, AccountType.EXPENSE})


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    type: AccountType

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("account code must not be empty")

    @property
    def increases_with_debit(self) -> bool:
        return self.type in DEBIT_POSITIVE


class ChartOfAccounts:
    def __init__(self, accounts: "list[Account] | None" = None) -> None:
        self._by_code: dict[str, Account] = {}
        for account in accounts or []:
            self.add(account)

    def add(self, account: Account) -> None:
        if account.code in self._by_code:
            raise ValueError(f"duplicate account code: {account.code}")
        self._by_code[account.code] = account

    def get(self, code: str) -> Account:
        try:
            return self._by_code[code]
        except KeyError:
            raise KeyError(code) from None

    def codes(self) -> "list[str]":
        return sorted(self._by_code)

    def __len__(self) -> int:
        return len(self._by_code)

    def __contains__(self, code: object) -> bool:
        return code in self._by_code
