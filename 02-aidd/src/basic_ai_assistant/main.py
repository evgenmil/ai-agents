import asyncio
import logging

from basic_ai_assistant.config import Config, load_env_file
from basic_ai_assistant.dialog.dialog_manager import DialogManager
from basic_ai_assistant.logging_config import setup_logging
from basic_ai_assistant.llm.llm_client import LlmClient
from basic_ai_assistant.telegram_bot.bot_app import BotApp


logger = logging.getLogger(__name__)


def main() -> None:
    """Точка входа приложения."""
    load_env_file()
    setup_logging()
    logger.info("Старт приложения basic-ai-assistant")

    config = Config.from_env()
    llm_client = LlmClient(config=config)
    dialog_manager = DialogManager(
        llm_client=llm_client,
        system_prompt=config.system_prompt,
    )
    app = BotApp(config=config, dialog_manager=dialog_manager)

    asyncio.run(app.run())


if __name__ == "__main__":
    main()

