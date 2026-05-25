"""Транскрибация голосовых: HTTP-клиент (бот) и HTTP-сервер (GPU-ВМ)."""

from basic_ai_assistant.speech.speech_client import SpeechClient, SpeechClientError

__all__ = ["SpeechClient", "SpeechClientError"]
