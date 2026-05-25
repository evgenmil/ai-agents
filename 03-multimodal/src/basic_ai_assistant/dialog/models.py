from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, List


MessageRole = Literal["system", "user", "assistant"]


@dataclass
class Message:
    """Сообщение в диалоге."""

    role: MessageRole
    text: str
    created_at: datetime | None = None


@dataclass
class UserSession:
    """
    Сессия диалога для одного пользователя.

    Хранит последние сообщения диалога в оперативной памяти.
    """

    user_id: int
    messages: List[Message] = field(default_factory=list)

    def add_message(self, message: Message, max_history: int) -> None:
        """
        Добавить сообщение в историю, ограничивая её длину max_history.
        """
        self.messages.append(message)
        if len(self.messages) > max_history:
            # Оставляем только последние max_history сообщений.
            self.messages = self.messages[-max_history:]

