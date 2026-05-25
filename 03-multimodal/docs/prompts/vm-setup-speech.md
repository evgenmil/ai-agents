# Промпт: подготовка GPU-ВМ для транскрибации голосовых

Используй этот текст целиком как задание для агента с доступом к серверу (Cursor Agent, SSH и т.п.).

---

## Задача: подготовить GPU-ВМ для локальной транскрибации голосовых (Telegram-бот basic-ai-assistant)

### Контекст

На этой машине уже работает **Ollama** (LLM для текста и vision). Для **голосовых сообщений** нужен отдельный стек — **не Ollama**:

- STT: библиотека **faster-whisper** (Python), модель Whisper **`large-v3`** на **CUDA**
- Конвертация аудио: **ffmpeg** (Telegram присылает OGG Opus → WAV)
- Документация проекта: `docs/vision.md` §6.4, итерация 15 в `docs/tasklist.md`

**Не делать:** `ollama pull whisper`, поиск whisper-моделей в Ollama — для STT они не используются.

### Окружение (ожидаемое)

- ОС: Ubuntu с CUDA (образ UBUNTU CUDA BIOS)
- GPU: NVIDIA RTX 4090
- Диск: ≥60 GB
- Ollama: уже установлена и слушает (обычно `http://127.0.0.1:11434`)

### Деплой: бот и STT на разных машинах

На **этой GPU‑ВМ** поднимается только **STT‑сервер** (и уже работает Ollama для LLM). Telegram‑бот крутится **у пользователя** (Windows/Docker) и ходит по HTTP:

- LLM: `OPENROUTER_BASE_URL=http://<IP_GPU>:11434/v1` (в `.env` **бота**)
- STT: `SPEECH_API_URL=http://<IP_GPU>:11435` (в `.env` **бота**)

### Целевые переменные на GPU‑ВМ (STT‑сервер)

```env
SPEECH_MODEL=large-v3
SPEECH_DEVICE=cuda
SPEECH_COMPUTE_TYPE=float16
SPEECH_LANGUAGE=ru
SPEECH_HOST=0.0.0.0:11435
SPEECH_API_KEY=...   # опционально, тот же секрет в .env бота
```

Ollama на этой ВМ **не менять** (`http://127.0.0.1:11434`).

После итерации 15 в коде: открыть порт **11435** в firewall (immers.cloud), **порт 22 оставить открытым**.

### Что нужно сделать

#### 1. Проверить GPU и CUDA

```bash
nvidia-smi
```

Ожидание: видна RTX 4090, драйвер без ошибок. Если команда недоступна — зафиксировать проблему, STT на CUDA не поднимать.

#### 2. Установить системные зависимости

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
ffmpeg -version
which ffmpeg
```

#### 3. Подготовить Python 3.11 и uv (если ещё нет)

```bash
python3 --version   # нужен ≥3.11
# uv: https://docs.astral.sh/uv/getting-started/installation/
```

#### 4. Клонировать/обновить проект и зависимости

Путь к репозиторию уточни у пользователя (например `~/basic-ai-assistant` или `03-multimodal`).

```bash
cd <ПУТЬ_К_ПРОЕКТУ>
git pull   # если репозиторий уже есть

# После мержа итерации 15 в коде:
uv sync
# Если faster-whisper ещё не в pyproject.toml — временно:
uv pip install faster-whisper
```

#### 5. Скачать и прогреть модель Whisper large-v3 на GPU

Модель качается с Hugging Face при первом `WhisperModel("large-v3", ...)`. Выполни одноразовый прогрев (от пользователя, не root):

```bash
cd <ПУТЬ_К_ПРОЕКТУ>
uv run python - <<'EOF'
from faster_whisper import WhisperModel
import time

print("Loading large-v3 on CUDA...")
t0 = time.time()
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
print(f"Loaded in {time.time() - t0:.1f}s")

# Короткий smoke-test: при наличии тестового wav раскомментируй:
# segments, info = model.transcribe("/tmp/test_ru.wav", language="ru")
# print("".join(s.text for s in segments))
print("OK: model ready")
EOF
```

Ожидание:

- Первая загрузка: скачивание ~2–3 GB в кэш Hugging Face (`~/.cache/huggingface/` или `HF_HOME`)
- Повторный запуск: быстрая загрузка с диска
- VRAM: порядка 3–5 GB на 4090

При ошибке CUDA/cuDNN — вывести полный traceback и версии:

```bash
uv run python -c "import ctranslate2; print(ctranslate2.__version__)"
```

#### 6. (Опционально) Зафиксировать каталог кэша моделей

Если системный диск маленький:

```bash
export HF_HOME=/data/huggingface   # примонтированный большой диск
mkdir -p "$HF_HOME"
```

Повторить шаг 5 с этим `HF_HOME`.

#### 7. Проверка ffmpeg + whisper (если есть sample)

```bash
uv run python - <<'EOF'
from faster_whisper import WhisperModel
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
# segments, _ = model.transcribe("test.wav", language="ru")
print("transcribe API OK")
EOF
```

#### 8. (После появления `speech_server` в репозитории) Запуск STT-сервиса

```bash
cd ~/03-multimodal
# .env с SPEECH_* как выше
uv run python -m basic_ai_assistant.speech.speech_server
```

Проверка с любой машины:

```bash
curl -X POST "http://<IP_GPU>:11435/v1/transcribe" \
  -F "file=@test.ogg" -H "Authorization: Bearer <SPEECH_API_KEY>"
```

#### 9. Не трогать без запроса

- Конфигурацию Ollama и уже скачанные LLM-модели
- Порт 22 SSH
- `.env` бота на Windows (только STT-сервер на ВМ)
- Секреты в логах

### Критерии готовности (отчёт агенту)

В конце выдай краткий отчёт:

1. `nvidia-smi` — модель GPU, версия драйвера
2. `ffmpeg -version` — первая строка
3. Размер кэша Whisper (`du -sh ~/.cache/huggingface` или `$HF_HOME`)
4. Время загрузки `large-v3` на CUDA (секунды)
5. Версии: `faster-whisper`, `ctranslate2`, Python
6. Список проблем (если были) и что осталось для деплоя бота (итерация 15 в коде)

### Ограничения

- KISS: не поднимать отдельный Docker для Whisper, если не попросили
- Не использовать облачный OpenAI Whisper API на этой задаче
- Модель для продакшена: **large-v3**, не `tiny`/`base`, unless GPU недоступен

---

## Справка: Ollama vs STT

| Сервис | Назначение | Установка |
|--------|------------|-----------|
| **Ollama** | `MODEL_TEXT`, `MODEL_IMAGE` | `ollama pull …` |
| **faster-whisper** | голосовые → текст | `WhisperModel("large-v3", device="cuda")` |
