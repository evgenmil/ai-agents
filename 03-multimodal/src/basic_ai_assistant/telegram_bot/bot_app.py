from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from basic_ai_assistant.config import Config
from basic_ai_assistant.finance.finance_manager import FinanceManager


logger = logging.getLogger(__name__)


class BotApp:
    """
    Класс, инкапсулирующий настройку aiogram и запуск polling.

    Бот принимает текстовые сообщения и передаёт их в FinanceManager.
    """

    def __init__(self, config: Config, finance_manager: FinanceManager) -> None:
        self._config = config
        self._finance_manager = finance_manager
        self._bot = Bot(token=self._config.telegram_bot_token)
        self._dp = Dispatcher()

        self._register_handlers()

    def _register_handlers(self) -> None:
        self._dp.message.register(self.handle_start, CommandStart())
        self._dp.message.register(self.handle_balance, Command("balance"))
        self._dp.message.register(self.handle_text_message, F.text)

    async def handle_start(self, message: Message) -> None:
        user_id = message.from_user.id if message.from_user else 0
        logger.info("Получена команда /start от пользователя %s", user_id)
        try:
            await message.answer(
                "Привет! Я твой финансовый советник.\n"
                "Расскажи о трате или доходе — например: «кофе 350».\n"
                "Я запишу операцию и подтвержу детали.\n"
                "Баланс: команда /balance или спроси «какой баланс?»."
            )
        except Exception:
            logger.exception("Ошибка при отправке ответа на /start пользователю %s", user_id)

    async def handle_balance(self, message: Message) -> None:
        user_id = message.from_user.id if message.from_user else 0
        logger.info("Получена команда /balance от пользователя %s", user_id)
        try:
            reply = self._finance_manager.get_balance_reply(user_id)
            await message.answer(reply)
        except Exception:
            logger.exception("Ошибка при обработке /balance пользователя %s", user_id)
            try:
                await message.answer("Произошла неожиданная ошибка. Пожалуйста, попробуйте позже.")
            except Exception:
                logger.exception("Ошибка при отправке ответа на /balance пользователю %s", user_id)

    async def handle_text_message(self, message: Message) -> None:
        if not message.text:
            return

        user_id = message.from_user.id if message.from_user else 0
        logger.info(
            "Сообщение от пользователя %s: %s",
            user_id,
            message.text,
        )

        await self._bot.send_chat_action(chat_id=message.chat.id, action="typing")

        try:
            reply = await self._finance_manager.handle_user_message(
                user_id=user_id,
                text=message.text,
            )
        except Exception:
            logger.exception("Ошибка при обработке сообщения пользователя %s", user_id)
            try:
                await message.answer("Произошла неожиданная ошибка. Пожалуйста, попробуйте позже.")
            except Exception:
                logger.exception("Ошибка при отправке сообщения об ошибке пользователю %s", user_id)
            return

        try:
            await message.answer(reply)
            logger.info("Ответ отправлен пользователю %s", user_id)
        except Exception:
            logger.exception("Ошибка при отправке ответа пользователю %s", user_id)

    async def run(self) -> None:
        logger.info("Запуск polling Telegram‑бота")
        await self._dp.start_polling(self._bot)

