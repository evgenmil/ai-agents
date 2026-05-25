from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from basic_ai_assistant.finance.category import Category
from basic_ai_assistant.finance.transaction_type import TransactionType


class Direction(str, Enum):
    """Направление транзакции: доход или расход."""

    INCOME = "income"
    EXPENSE = "expense"


@dataclass
class Transaction:
    """Одна запись в таблице учёта."""

    datetime: datetime
    direction: Direction
    amount: Decimal
    type: TransactionType
    category: Category
    description: str
