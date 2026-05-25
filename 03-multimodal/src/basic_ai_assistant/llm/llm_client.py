from __future__ import annotations

import logging
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from basic_ai_assistant.config import Config


logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


class LlmClientError(Exception):
    """Базовое исключение для ошибок при обращении к LLM."""


class LlmClient:
    """
    Клиент для работы с LLM через OpenAI-совместимый API (OpenRouter, Ollama).

    Поддерживает обычный chat completion и structured output через Pydantic-схемы.
    """

    def __init__(self, config: Config) -> None:
        self._client = AsyncOpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.openrouter_api_key,
        )
        self._model = config.model_text

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

    @staticmethod
    def _extract_json_content(content: str) -> str:
        text = content.strip()
        if not text.startswith("```"):
            return text

        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _parse_structured_content(
        self,
        content: str,
        response_model: type[TModel],
    ) -> TModel:
        normalized = self._extract_json_content(content)
        try:
            return response_model.model_validate_json(normalized)
        except ValidationError as exc:
            logger.error(
                "Не удалось разобрать structured-ответ (обрезан): %s",
                normalized[:200],
            )
            raise LlmClientError("Invalid structured response") from exc

    async def _request_structured_completion(
        self,
        messages: list[dict],
        response_model: type[TModel],
    ) -> TModel:
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=messages,
            response_format=response_model,
        )

        if not completion.choices:
            logger.error("LLM вернула ответ без choices")
            raise LlmClientError("No choices in structured response")

        message = completion.choices[0].message
        if message.parsed is not None:
            return message.parsed

        content = message.content or ""
        if not content:
            logger.error("LLM вернула пустой structured-ответ")
            raise LlmClientError("Empty structured response")

        return self._parse_structured_content(content, response_model)

    async def generate_structured_reply(
        self,
        messages: list[dict],
        response_model: type[TModel],
    ) -> TModel:
        """Structured completion: ответ модели в виде Pydantic-модели."""
        try:
            parsed = await self._request_structured_completion(
                messages,
                response_model,
            )
        except LlmClientError:
            raise
        except Exception as exc:
            logger.exception("Ошибка structured-запроса к LLM: %s", exc)
            raise LlmClientError("LLM structured request failed") from exc

        logger.info(
            "Structured-ответ от LLM: %s",
            parsed.model_dump_json()[:300],
        )
        return parsed

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
