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
    llm_trace_enabled: bool = False
    llm_trace_dir: str = "logs"
    speech_api_url: str | None = None
    speech_api_key: str | None = None

    @staticmethod
    def _parse_bool_env(name: str, default: bool = False) -> bool:
        value = (os.environ.get(name) or "").strip().lower()
        if not value:
            return default
        return value in ("1", "true", "yes", "on")

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

        llm_trace_enabled = cls._parse_bool_env("LLM_TRACE_ENABLED")
        llm_trace_dir = (os.environ.get("LLM_TRACE_DIR") or "logs").strip() or "logs"

        speech_api_url = (os.environ.get("SPEECH_API_URL") or "").strip() or None
        speech_api_key = (os.environ.get("SPEECH_API_KEY") or "").strip() or None

        logger.info("MODEL_TEXT: %s", model_text)
        logger.info("MODEL_IMAGE: %s", model_image)
        if llm_trace_enabled:
            logger.info("LLM trace включён, каталог: %s", llm_trace_dir)
        else:
            logger.info("LLM trace выключен (LLM_TRACE_ENABLED не задан)")
        if speech_api_url:
            logger.info("STT API: %s", speech_api_url)
        else:
            logger.info("SPEECH_API_URL не задан — голосовые сообщения отключены")

        return cls(
            telegram_bot_token=telegram_bot_token,
            openrouter_api_key=openrouter_api_key,
            openrouter_base_url=openrouter_base_url,
            model_text=model_text,
            model_image=model_image,
            system_prompt=system_prompt,
            llm_trace_enabled=llm_trace_enabled,
            llm_trace_dir=llm_trace_dir,
            speech_api_url=speech_api_url,
            speech_api_key=speech_api_key,
        )


@dataclass
class SpeechServerConfig:
    """Конфигурация HTTP STT-сервера на GPU-ВМ."""

    model: str
    device: str
    compute_type: str
    language: str
    host: str
    port: int
    api_key: str | None = None

    @staticmethod
    def _parse_host_port(raw: str) -> tuple[str, int]:
        value = raw.strip()
        if not value:
            return "0.0.0.0", 11435
        if ":" in value:
            host_part, port_part = value.rsplit(":", 1)
            return host_part or "0.0.0.0", int(port_part)
        return value, 11435

    @classmethod
    def from_env(cls) -> "SpeechServerConfig":
        model = (os.environ.get("SPEECH_MODEL") or "large-v3").strip()
        device = (os.environ.get("SPEECH_DEVICE") or "cuda").strip()
        compute_type = (os.environ.get("SPEECH_COMPUTE_TYPE") or "float16").strip()
        language = (os.environ.get("SPEECH_LANGUAGE") or "ru").strip()
        host_raw = (os.environ.get("SPEECH_HOST") or "0.0.0.0:11435").strip()
        host, port = cls._parse_host_port(host_raw)
        api_key = (os.environ.get("SPEECH_API_KEY") or "").strip() or None

        return cls(
            model=model,
            device=device,
            compute_type=compute_type,
            language=language,
            host=host,
            port=port,
            api_key=api_key,
        )
