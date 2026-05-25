from dataclasses import dataclass
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env_file() -> None:
    """
    Подгрузить переменные из `.env` в корне проекта.

    Уже заданные в окружении переменные не перезаписываются (удобно для Docker и CI).
    """
    env_path = _PROJECT_ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path)


@dataclass
class Config:
    """
    Конфигурация приложения.

    - Токен Telegram-бота, настройки OpenRouter (ключ, URL, модели).
    - Опционально: системный промпт из файла (SYSTEM_PROMPT_PATH) или переменной SYSTEM_PROMPT.
    """

    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_base_url: str
    model_text: str
    model_image: str
    system_prompt: str | None = None

    @staticmethod
    def _load_system_prompt() -> str | None:
        """
        Загрузить системный промпт.

        Приоритет: SYSTEM_PROMPT_PATH (файл) → SYSTEM_PROMPT (строка в окружении).
        Относительный путь к файлу разрешается от корня проекта.
        """
        path_value = (os.environ.get("SYSTEM_PROMPT_PATH") or "").strip()
        if path_value:
            prompt_path = Path(path_value)
            if not prompt_path.is_absolute():
                prompt_path = _PROJECT_ROOT / prompt_path
            if not prompt_path.is_file():
                raise RuntimeError(
                    f"Файл системного промпта не найден: {prompt_path}"
                )
            text = prompt_path.read_text(encoding="utf-8").strip()
            if not text:
                raise RuntimeError(f"Файл системного промпта пуст: {prompt_path}")
            logger.info(
                "Системный промпт загружен из файла %s (%d символов)",
                prompt_path,
                len(text),
            )
            return text

        inline = os.environ.get("SYSTEM_PROMPT")
        if inline is None:
            logger.info(
                "Системный промпт не задан — используется встроенный по умолчанию"
            )
            return None

        text = inline.strip()
        if not text:
            logger.info(
                "SYSTEM_PROMPT пуст — используется встроенный по умолчанию"
            )
            return None

        logger.info(
            "Системный промпт задан через SYSTEM_PROMPT (%d символов)", len(text)
        )
        return text

    @classmethod
    def from_env(cls) -> "Config":
        """Создать конфигурацию, читая значения из переменных окружения."""
        telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not telegram_bot_token:
            raise RuntimeError(
                "Переменная окружения TELEGRAM_BOT_TOKEN не установлена."
            )

        openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise RuntimeError(
                "Переменная окружения OPENROUTER_API_KEY не установлена."
            )

        openrouter_base_url = os.environ.get(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        )

        model_text = os.environ.get("MODEL_TEXT")
        if not model_text:
            raise RuntimeError("Переменная окружения MODEL_TEXT не установлена.")

        model_image = os.environ.get("MODEL_IMAGE")
        if not model_image:
            raise RuntimeError("Переменная окружения MODEL_IMAGE не установлена.")

        system_prompt = cls._load_system_prompt()

        logger.info("MODEL_TEXT: %s", model_text)
        logger.info("MODEL_IMAGE: %s", model_image)

        return cls(
            telegram_bot_token=telegram_bot_token,
            openrouter_api_key=openrouter_api_key,
            openrouter_base_url=openrouter_base_url,
            model_text=model_text,
            model_image=model_image,
            system_prompt=system_prompt,
        )
