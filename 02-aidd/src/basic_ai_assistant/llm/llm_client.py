from __future__ import annotations

import logging

from openai import AsyncOpenAI

from basic_ai_assistant.config import Config


logger = logging.getLogger(__name__)


class LlmClientError(Exception):
    """Базовое исключение для ошибок при обращении к LLM."""


class LlmClient:
    """
    Клиент для работы с LLM через OpenRouter.

    На этапе итерации 2:
    - формирует простой запрос к модели в формате chat completion;
    - возвращает только текст ответа без дополнительной логики.
    """

    def __init__(self, config: Config) -> None:
        self._client = AsyncOpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.openrouter_api_key,
        )
        self._model = config.llm_model

    async def generate_chat_reply(self, messages: list[dict]) -> str:
        """
        Сформировать ответ модели на основе списка сообщений.

        Ожидается формат сообщений, совместимый с OpenAI Chat API.
        """
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except Exception as exc:  # Ошибки внешнего сервиса
            logger.exception("Ошибка при обращении к LLM: %s", exc)
            raise LlmClientError("LLM request failed") from exc

        message = resp.choices[0].message
        content = message.content or ""

        logger.info("Получен ответ от LLM (обрезан для логов): %s", content[:200])
        return content

    async def generate_reply(self, user_message: str) -> str:
        """
        Упрощённый вариант вызова модели для одного пользовательского сообщения.
        """
        messages = [
            {
                "role": "system",
                "content": "You are a helpful and concise assistant.",
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]
        return await self.generate_chat_reply(messages)

