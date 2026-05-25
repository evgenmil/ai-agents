from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from basic_ai_assistant.finance.category import Category
from basic_ai_assistant.finance.transaction_type import TransactionType


MessageIntent = Literal["record_transaction", "balance_query", "chat"]


class ExtractedTransaction(BaseModel):
    """Транзакция, извлечённая LLM из текста пользователя."""

    direction: Literal["income", "expense"]
    amount: Decimal = Field(gt=0, description="Сумма в рублях")
    type: TransactionType
    category: Category
    description: str = Field(min_length=1)
    datetime: str | None = Field(
        default=None,
        description="ISO 8601, если указано в сообщении; иначе null",
    )


class ParsedTextMessage(BaseModel):
    """Structured output для текстового сообщения."""

    intent: MessageIntent
    transaction: ExtractedTransaction | None = None
    reply: str = Field(min_length=1)
