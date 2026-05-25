from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path


logger = logging.getLogger(__name__)


class AudioConverterError(Exception):
    """Ошибка конвертации аудио через ffmpeg."""


def ogg_bytes_to_wav_file(ogg_bytes: bytes) -> tuple[Path, list[Path]]:
    """
    Сохранить OGG во временный файл и сконвертировать в WAV 16 kHz mono.

    Возвращает путь к WAV и список временных файлов для удаления вызывающим кодом.
    """
    if not ogg_bytes:
        raise AudioConverterError("Пустой аудиофайл")

    temp_paths: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
            ogg_file.write(ogg_bytes)
            ogg_path = Path(ogg_file.name)
        temp_paths.append(ogg_path)

        wav_path = ogg_path.with_suffix(".wav")
        temp_paths.append(wav_path)

        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(ogg_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(wav_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(
                "ffmpeg завершился с кодом %s: %s",
                result.returncode,
                (result.stderr or "")[:500],
            )
            raise AudioConverterError("Не удалось конвертировать аудио в WAV")

        if not wav_path.is_file() or wav_path.stat().st_size == 0:
            raise AudioConverterError("WAV-файл не создан или пуст")

        return wav_path, temp_paths
    except AudioConverterError:
        for path in temp_paths:
            path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        for path in temp_paths:
            path.unlink(missing_ok=True)
        raise AudioConverterError("Ошибка работы с временными файлами") from exc


def cleanup_temp_files(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)
