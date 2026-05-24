import logging
import os


def setup_logging() -> None:
    """
    Настроить базовое логирование для приложения.

    Уровень логирования берётся из переменной окружения LOG_LEVEL,
    по умолчанию используется INFO.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

