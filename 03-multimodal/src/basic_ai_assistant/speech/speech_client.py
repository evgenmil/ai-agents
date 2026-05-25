from __future__ import annotations

import logging

import httpx


logger = logging.getLogger(__name__)


class SpeechClientError(Exception):
    """Ошибка при обращении к удалённому STT-сервису."""


class SpeechClient:
    """HTTP-клиент к STT-сервису на GPU-ВМ (faster-whisper за reverse proxy не нужен)."""

    def __init__(
        self,
        api_url: str,
        api_key: str | None = None,
        timeout_sec: float = 120.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = (api_key or "").strip() or None
        self._timeout_sec = timeout_sec

    async def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """
        Отправить OGG/Opus с Telegram на STT-сервер и получить расшифровку.

        :raises SpeechClientError: сеть, HTTP-ошибка, пустой ответ.
        """
        if not audio_bytes:
            raise SpeechClientError("Пустой аудиофайл")

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        url = f"{self._api_url}/v1/transcribe"
        files = {"file": (filename, audio_bytes, "audio/ogg")}

        try:
            async with httpx.AsyncClient(timeout=self._timeout_sec) as client:
                response = await client.post(url, files=files, headers=headers)
        except httpx.TimeoutException as exc:
            logger.exception("Таймаут STT-запроса к %s", url)
            raise SpeechClientError("STT request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("Сетевая ошибка STT-запроса к %s", url)
            raise SpeechClientError("STT request failed") from exc

        if response.status_code == 401:
            raise SpeechClientError("STT unauthorized")
        if response.status_code >= 400:
            logger.error(
                "STT вернул HTTP %s: %s",
                response.status_code,
                (response.text or "")[:300],
            )
            raise SpeechClientError(f"STT HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SpeechClientError("Invalid STT response") from exc

        text = (payload.get("text") or "").strip()
        if not text:
            raise SpeechClientError("Empty transcription")

        logger.info("STT-расшифровка получена (%d символов)", len(text))
        return text
