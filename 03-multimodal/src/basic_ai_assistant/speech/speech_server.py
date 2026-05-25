from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
import uvicorn

from basic_ai_assistant.config import SpeechServerConfig, load_env_file
from basic_ai_assistant.logging_config import setup_logging
from basic_ai_assistant.speech.audio_converter import (
    AudioConverterError,
    cleanup_temp_files,
    ogg_bytes_to_wav_file,
)


if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

_whisper_model: WhisperModel | None = None
_server_config: SpeechServerConfig | None = None


class TranscribeResponse(BaseModel):
    text: str


def _get_whisper_model() -> WhisperModel:
    if _whisper_model is None:
        raise RuntimeError("Whisper model is not loaded")
    return _whisper_model


def _verify_api_key(authorization: str | None = Header(default=None)) -> None:
    cfg = _server_config
    if cfg is None or not cfg.api_key:
        return
    expected = f"Bearer {cfg.api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _whisper_model, _server_config
    _server_config = SpeechServerConfig.from_env()
    logger.info(
        "Загрузка Whisper %s на %s (%s)...",
        _server_config.model,
        _server_config.device,
        _server_config.compute_type,
    )
    from faster_whisper import WhisperModel

    _whisper_model = WhisperModel(
        _server_config.model,
        device=_server_config.device,
        compute_type=_server_config.compute_type,
    )
    logger.info("Whisper готов к приёму запросов")
    yield
    _whisper_model = None
    _server_config = None


app = FastAPI(title="basic-ai-assistant STT", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    _: None = Depends(_verify_api_key),
) -> TranscribeResponse:
    cfg = _server_config
    if cfg is None:
        raise HTTPException(status_code=503, detail="Server not ready")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    temp_paths: list = []
    try:
        wav_path, temp_paths = ogg_bytes_to_wav_file(audio_bytes)
        model = _get_whisper_model()
        segments, _info = model.transcribe(
            str(wav_path),
            language=cfg.language,
        )
        text = "".join(segment.text for segment in segments).strip()
    except AudioConverterError:
        logger.exception("Ошибка ffmpeg при транскрибации")
        raise HTTPException(
            status_code=500,
            detail="Audio conversion failed",
        ) from None
    except Exception:
        logger.exception("Ошибка Whisper при транскрибации")
        raise HTTPException(
            status_code=500,
            detail="Transcription failed",
        ) from None
    finally:
        cleanup_temp_files(temp_paths)

    if not text:
        raise HTTPException(status_code=422, detail="Empty transcription")

    logger.info("Транскрибация: %d символов", len(text))
    return TranscribeResponse(text=text)


def main() -> None:
    load_env_file()
    setup_logging()
    cfg = SpeechServerConfig.from_env()
    logger.info("Старт STT-сервера на %s:%s", cfg.host, cfg.port)
    uvicorn.run(
        "basic_ai_assistant.speech.speech_server:app",
        host=cfg.host,
        port=cfg.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
