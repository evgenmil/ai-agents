from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)

_SEPARATOR = "=" * 80


class LlmTraceLogger:
    """Запись запросов/ответов LLM в текстовые файлы per user_id (инкрементально)."""

    _SYSTEM_HEADER = "--- SYSTEM PROMPT (один раз) ---"

    def __init__(self, enabled: bool, trace_dir: str) -> None:
        self._enabled = enabled
        self._trace_dir = Path(trace_dir)
        self._system_written: set[int] = set()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _trace_path(self, user_id: int) -> Path:
        return self._trace_dir / f"llm_trace_{user_id}.txt"

    def log_exchange(
        self,
        user_id: int,
        kind: str,
        model: str,
        messages: list[dict],
        response_text: str,
    ) -> None:
        if not self._enabled:
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        path = self._trace_path(user_id)
        api_message_count = len(messages)

        system_block = self._format_system_once(user_id, path, messages)
        turn_messages = self._latest_user_turn(messages)
        request_body = self._format_messages(turn_messages)

        block = (
            f"{_SEPARATOR}\n"
            f"{timestamp} | {kind} | model={model} | "
            f"api_messages={api_message_count}\n"
            f"--- REQUEST (новое сообщение) ---\n"
            f"{request_body}\n"
            f"--- RESPONSE ---\n"
            f"{response_text.rstrip()}\n"
            f"{_SEPARATOR}\n"
        )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                if system_block:
                    file.write(system_block)
                file.write(block)
        except OSError as exc:
            logger.warning("Не удалось записать LLM trace в %s: %s", path, exc)

    def _format_system_once(
        self,
        user_id: int,
        path: Path,
        messages: list[dict],
    ) -> str:
        if user_id in self._system_written:
            return ""

        if not messages or messages[0].get("role") != "system":
            return ""

        if path.exists() and path.stat().st_size > 0:
            if self._file_has_system_header(path):
                self._system_written.add(user_id)
                return ""

        system_text = self._format_content(messages[0].get("content", ""))
        self._system_written.add(user_id)
        return (
            f"{self._SYSTEM_HEADER}\n"
            f"{system_text}\n\n"
        )

    @staticmethod
    def _file_has_system_header(path: Path) -> bool:
        try:
            with path.open(encoding="utf-8") as file:
                head = file.read(4096)
        except OSError:
            return False
        return LlmTraceLogger._SYSTEM_HEADER in head

    @staticmethod
    def _latest_user_turn(messages: list[dict]) -> list[dict]:
        """Только последнее user-сообщение (остальная история уже в файле)."""
        dialog = messages
        if messages and messages[0].get("role") == "system":
            dialog = messages[1:]

        for message in reversed(dialog):
            if message.get("role") == "user":
                return [message]

        return dialog[-1:] if dialog else []

    def _format_messages(self, messages: list[dict]) -> str:
        parts: list[str] = []
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            parts.append(f"[{role}]\n{self._format_content(content)}")
        return "\n\n".join(parts)

    def _format_content(self, content: object) -> str:
        if isinstance(content, str):
            return content

        if not isinstance(content, list):
            return str(content)

        lines: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                lines.append(str(part))
                continue

            part_type = part.get("type")
            if part_type == "text":
                lines.append(str(part.get("text", "")))
                continue

            if part_type == "image_url":
                lines.append(self._format_image_part(part))
                continue

            lines.append(str(part))

        return "\n".join(lines)

    @staticmethod
    def _format_image_part(part: dict) -> str:
        image_url = part.get("image_url")
        if not isinstance(image_url, dict):
            return "[image: unknown]"

        url = image_url.get("url", "")
        if not isinstance(url, str) or not url.startswith("data:"):
            return f"[image: {url[:80]}...]" if len(url) > 80 else f"[image: {url}]"

        header, _, payload = url.partition(",")
        mime = "unknown"
        if header.startswith("data:") and ";" in header:
            mime = header[5:].split(";", 1)[0]
        byte_count = len(payload.encode("ascii")) * 3 // 4 if payload else 0
        return f"[image: {mime}, {byte_count} bytes]"
