from __future__ import annotations

from decimal import Decimal

from basic_ai_assistant.finance.transaction import Direction, Transaction


class Ledger:
    """In-memory хранилище транзакций: отдельный список на каждого пользователя."""

    def __init__(self) -> None:
        self._transactions: dict[int, list[Transaction]] = {}

    def add(self, user_id: int, transaction: Transaction) -> None:
        if user_id not in self._transactions:
            self._transactions[user_id] = []
        self._transactions[user_id].append(transaction)

    def get_transactions(self, user_id: int) -> list[Transaction]:
        return list(self._transactions.get(user_id, []))

    def get_balance(self, user_id: int) -> Decimal:
        balance = Decimal("0")
        for transaction in self._transactions.get(user_id, []):
            if transaction.direction == Direction.INCOME:
                balance += transaction.amount
            else:
                balance -= transaction.amount
        return balance
