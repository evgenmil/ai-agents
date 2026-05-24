from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from basic_ai_assistant.config import Config
from basic_ai_assistant.dialog.dialog_manager import DialogManager


logger = logging.getLogger(__name__)


class BotApp:
    """
    Класс, инкапсулирующий настройку aiogram и запуск polling.

    На этапе итерации 3 бот умеет:
    - отвечать на команду /start приветственным сообщением;
    - отправлять ответ, сгенерированный LLM, на любое текстовое сообщение
      с учётом нескольких последних реплик в диалоге.
    """

    def __init__(self, config: Config, dialog_manager: DialogManager) -> None:
        self._config = config
        self._dialog_manager = dialog_manager
        self._bot = Bot(token=self._config.telegram_bot_token)
        self._dp = Dispatcher()

        self._register_handlers()

    def _register_handlers(self) -> None:
        self._dp.message.register(self.handle_start, CommandStart())
        # Обрабатываем любые текстовые сообщения через диалоговый менеджер.
        self._dp.message.register(self.handle_llm_message, F.text)

    async def handle_start(self, message: Message) -> None:
        user_id = message.from_user.id if message.from_user else 0
        logger.info("Получена команда /start от пользователя %s", user_id)
        try:
            await message.answer(
                "Привет! Я базовый Telegram‑бот.\n"
                "Теперь я отвечаю с помощью LLM и помню контекст диалога."
            )
        except Exception:
            logger.exception("Ошибка при отправке ответа на /start пользователю %s", user_id)

    async def handle_llm_message(self, message: Message) -> None:
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
            reply = await self._dialog_manager.handle_user_message(user_id=user_id, text=message.text)
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

