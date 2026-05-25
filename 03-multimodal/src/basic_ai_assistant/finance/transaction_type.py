from enum import Enum


class TransactionType(str, Enum):
    """Тип транзакции — определяется LLM по контексту сообщения."""

    EVERYDAY = "everyday"
    PERIODIC = "periodic"
    ONE_TIME = "one_time"
