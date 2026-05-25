from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict

from basic_ai_assistant.dialog.models import Message, UserSession
from basic_ai_assistant.llm.llm_client import LlmClient, LlmClientError


logger = logging.getLogger(__name__)

# Запасной промпт, если SYSTEM_PROMPT_PATH / SYSTEM_PROMPT не заданы.
DEFAULT_SYSTEM_PROMPT = (
    "Ты — персональный финансовый советник в Telegram. "
    "Помогаешь вести учёт доходов и расходов в рублях: "
    "принимаешь записи, уточняешь неоднозначности, отвечаешь на вопросы о балансе. "
    "Отвечай на русском, кратко и по делу."
)


class DialogManager:
    """
    Простое ядро диалога с хранением истории в памяти процесса.

    Для каждого пользователя поддерживается своя сессия с ограниченным числом последних сообщений.
    """

    def __init__(
        self,
        llm_client: LlmClient,
        max_history_messages: int = 10,
        system_prompt: str | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._max_history_messages = max_history_messages
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._sessions: Dict[int, UserSession] = {}

    def _get_session(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    async def handle_user_message(self, user_id: int, text: str) -> str:
        """
        Обработать сообщение пользователя с учётом контекста диалога.
        """
        session = self._get_session(user_id)

        now = datetime.now(timezone.utc)
        user_message = Message(role="user", text=text, created_at=now)
        session.add_message(user_message, max_history=self._max_history_messages)

        # Формируем список сообщений для LLM: системный промпт + история диалога.
        messages_payload = [
            {"role": "system", "content": self._system_prompt},
        ]

        for msg in session.messages:
            messages_payload.append(
                {
                    "role": msg.role,
                    "content": msg.text,
                }
            )

        logger.info("Формируем запрос к LLM для пользователя %s с %d сообщениями истории", user_id, len(session.messages))

        try:
            reply_text = await self._llm_client.generate_chat_reply(messages_payload)
        except LlmClientError:
            logger.exception("Ошибка LLM при обработке сообщения пользователя %s", user_id)
            return "Сервис генерации ответов временно недоступен, пожалуйста, попробуйте позже."

        assistant_message = Message(role="assistant", text=reply_text, created_at=now)
        session.add_message(assistant_message, max_history=self._max_history_messages)

        return reply_text

