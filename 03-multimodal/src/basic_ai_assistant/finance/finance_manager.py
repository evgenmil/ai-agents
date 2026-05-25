from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict

from basic_ai_assistant.dialog.models import Message, UserSession
from basic_ai_assistant.finance.ledger import Ledger
from basic_ai_assistant.finance.transaction import Direction, Transaction
from basic_ai_assistant.llm.llm_client import LlmClient, LlmClientError
from basic_ai_assistant.llm.schemas import (
    ExtractedTransaction,
    MessageIntent,
    ParsedReceiptImage,
    ParsedTextMessage,
)


logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "Ты — персональный финансовый советник в Telegram. "
    "Помогаешь вести учёт доходов и расходов в рублях."
)

STRUCTURED_OUTPUT_INSTRUCTION = """
Ты анализируешь сообщение пользователя и возвращаешь структурированный ответ.

Правила intent (поле intent обязательно):
- record_transaction — новая трата или доход; достаточно данных (есть сумма); в т.ч. дополнение к ранее обсуждённому.
- balance_query — вопрос о балансе; transaction=null.
- chat — уточнение без новой записи, комментарий, обсуждение уже записанного; transaction=null.

При intent=record_transaction заполни transaction:
- direction: income или expense
- amount: сумма в рублях (число)
- type: everyday (повседневная), periodic (периодическая), one_time (разовая)
- category: products, restaurants, taxi, transport, education, travel, health, entertainment, utilities, salary, freelance, other
- description: подробности операции
- datetime: ISO 8601, если дата/время указаны в сообщении; иначе null

Поле reply — текст ответа пользователю на русском: подтверждение записи, уточняющий вопрос или ответ в диалоге.

Важно: всегда возвращай только JSON по схеме, без обычного текста вне JSON. Предыдущие ответы ассистента в истории тоже в формате JSON.
"""

RECEIPT_VISION_INSTRUCTION = """
Извлеки из фото чека транзакцию расхода или дохода в рублях.

Заполни transaction:
- direction: income или expense (чеки обычно expense)
- amount: итоговая сумма в рублях
- type: everyday, periodic или one_time
- category: products, restaurants, taxi, transport, education, travel, health, entertainment, utilities, salary, freelance, other
- description: магазин, товары/услуги и другие детали с чека
- datetime: ISO 8601, если дата/время видны на чеке; иначе null

reply — подтверждение записи на русском или просьба отправить фото повторно / описать трату текстом.
transaction=null, если не удалось прочитать сумму.

Важно: возвращай только JSON по схеме.
"""


class FinanceManager:
    """Ядро финансового советника: диалог, structured output, учёт транзакций."""

    def __init__(
        self,
        llm_client: LlmClient,
        ledger: Ledger,
        system_prompt: str | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._ledger = ledger
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._sessions: Dict[int, UserSession] = {}

    def _get_session(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    def _build_system_prompt(self) -> str:
        return f"{self._system_prompt.strip()}\n\n{STRUCTURED_OUTPUT_INSTRUCTION.strip()}"

    def _build_messages_payload(self, session: UserSession) -> list[dict]:
        messages_payload = [{"role": "system", "content": self._build_system_prompt()}]
        for msg in session.messages:
            messages_payload.append({"role": msg.role, "content": msg.text})
        return messages_payload

    @staticmethod
    def _to_history_json(parsed: ParsedTextMessage | ParsedReceiptImage) -> str:
        """Единый формат JSON в истории — всегда ParsedTextMessage с intent."""
        if isinstance(parsed, ParsedTextMessage):
            return parsed.model_dump_json()

        intent: MessageIntent = (
            "record_transaction" if parsed.transaction is not None else "chat"
        )
        entry = ParsedTextMessage(
            intent=intent,
            transaction=parsed.transaction,
            reply=parsed.reply,
        )
        return entry.model_dump_json()

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Не удалось разобрать datetime из LLM: %s", value)
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _to_transaction(data: ExtractedTransaction) -> Transaction:
        direction = (
            Direction.INCOME if data.direction == "income" else Direction.EXPENSE
        )
        return Transaction(
            datetime=FinanceManager._parse_datetime(data.datetime),
            direction=direction,
            amount=data.amount,
            type=data.type,
            category=data.category,
            description=data.description,
        )

    @staticmethod
    def format_balance(balance: Decimal) -> str:
        amount = balance.quantize(Decimal("1"))
        formatted = f"{abs(amount):,}".replace(",", " ")
        if amount > 0:
            return f"Ваш баланс: +{formatted} ₽"
        if amount < 0:
            return f"Ваш баланс: -{formatted} ₽"
        return "Ваш баланс: 0 ₽"

    def get_balance_reply(self, user_id: int) -> str:
        balance = self._ledger.get_balance(user_id)
        reply = self.format_balance(balance)
        logger.info("Баланс пользователя %s: %s", user_id, balance)
        return reply

    @staticmethod
    def _is_balance_query(text: str) -> bool:
        """Fallback: только явный запрос баланса, без эвристик вроде «сколько»."""
        return "баланс" in text.lower()

    @staticmethod
    def _resolve_intent(parsed: ParsedTextMessage, user_text: str) -> MessageIntent:
        if parsed.intent != "chat":
            return parsed.intent
        if FinanceManager._is_balance_query(user_text):
            return "balance_query"
        if parsed.transaction is not None:
            return "record_transaction"
        return "chat"

    async def handle_user_message(self, user_id: int, text: str) -> str:
        session = self._get_session(user_id)
        now = datetime.now(timezone.utc)

        session.messages.append(Message(role="user", text=text, created_at=now))
        messages_payload = self._build_messages_payload(session)

        logger.info(
            "Structured-запрос к LLM для пользователя %s (%d сообщений истории)",
            user_id,
            len(session.messages),
        )

        try:
            parsed = await self._llm_client.generate_structured_reply(
                messages_payload,
                ParsedTextMessage,
                user_id=user_id,
            )
        except LlmClientError:
            logger.exception(
                "Ошибка LLM при обработке сообщения пользователя %s", user_id
            )
            session.messages.pop()
            return (
                "Сервис генерации ответов временно недоступен, "
                "пожалуйста, попробуйте позже."
            )

        intent = self._resolve_intent(parsed, text)
        parsed = parsed.model_copy(update={"intent": intent})

        if intent == "record_transaction" and parsed.transaction is not None:
            transaction = self._to_transaction(parsed.transaction)
            self._ledger.add(user_id, transaction)
            logger.info(
                "Транзакция сохранена для пользователя %s: %s %s ₽, %s",
                user_id,
                transaction.direction.value,
                transaction.amount,
                transaction.category.value,
            )

        if intent == "balance_query":
            reply = self.get_balance_reply(user_id)
            parsed = parsed.model_copy(update={"reply": reply, "transaction": None})
        else:
            reply = parsed.reply

        # В историю — единый JSON (ParsedTextMessage), чтобы модель не путала схемы.
        session.messages.append(
            Message(
                role="assistant",
                text=self._to_history_json(parsed),
                created_at=now,
            )
        )
        return reply

    async def handle_receipt_photo(
        self,
        user_id: int,
        image_bytes: bytes,
        image_mime: str = "image/jpeg",
        caption: str | None = None,
    ) -> str:
        session = self._get_session(user_id)
        now = datetime.now(timezone.utc)

        user_note = "[фото чека]"
        if caption:
            user_note = f"[фото чека] {caption.strip()}"
        session.messages.append(Message(role="user", text=user_note, created_at=now))

        system_prompt = (
            f"{self._system_prompt.strip()}\n\n{RECEIPT_VISION_INSTRUCTION.strip()}"
        )
        user_text = "Извлеки данные о трате или доходе с этого чека."
        if caption:
            user_text += f" Подпись пользователя: {caption.strip()}"

        logger.info("Vision-запрос к LLM для пользователя %s", user_id)

        try:
            parsed = await self._llm_client.generate_vision_structured_reply(
                system_prompt=system_prompt,
                image_bytes=image_bytes,
                image_mime=image_mime,
                response_model=ParsedReceiptImage,
                user_text=user_text,
                user_id=user_id,
            )
        except LlmClientError:
            logger.exception(
                "Ошибка LLM при обработке фото чека пользователя %s", user_id
            )
            session.messages.pop()
            return (
                "Сервис распознавания чеков временно недоступен, "
                "пожалуйста, попробуйте позже."
            )

        if parsed.transaction is not None:
            transaction = self._to_transaction(parsed.transaction)
            self._ledger.add(user_id, transaction)
            logger.info(
                "Транзакция из чека сохранена для пользователя %s: %s %s ₽, %s",
                user_id,
                transaction.direction.value,
                transaction.amount,
                transaction.category.value,
            )

        session.messages.append(
            Message(
                role="assistant",
                text=self._to_history_json(parsed),
                created_at=now,
            )
        )
        return parsed.reply
