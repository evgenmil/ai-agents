import asyncio
import logging

from basic_ai_assistant.config import Config, load_env_file
from basic_ai_assistant.finance.finance_manager import FinanceManager
from basic_ai_assistant.finance.ledger import Ledger
from basic_ai_assistant.logging_config import setup_logging
from basic_ai_assistant.llm.llm_client import LlmClient
from basic_ai_assistant.llm.llm_trace_logger import LlmTraceLogger
from basic_ai_assistant.telegram_bot.bot_app import BotApp


logger = logging.getLogger(__name__)


def main() -> None:
    """Точка входа приложения."""
    load_env_file()
    setup_logging()
    logger.info("Старт приложения basic-ai-assistant")

    config = Config.from_env()
    llm_trace = LlmTraceLogger(
        enabled=config.llm_trace_enabled,
        trace_dir=config.llm_trace_dir,
    )
    llm_client = LlmClient(config=config, trace=llm_trace)
    ledger = Ledger()
    finance_manager = FinanceManager(
        llm_client=llm_client,
        ledger=ledger,
        system_prompt=config.system_prompt,
    )
    app = BotApp(config=config, finance_manager=finance_manager)

    asyncio.run(app.run())


if __name__ == "__main__":
    main()

