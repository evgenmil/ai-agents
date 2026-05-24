# Базовый образ по docs/vision.md
FROM python:3.11-slim

# Установка uv из официального образа
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Копирование проекта (исключения в .dockerignore)
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY docs ./docs
COPY prompts ./prompts

# Установка зависимостей (uv.lock опционален для первой сборки)
ENV UV_NO_DEV=1
RUN uv sync --locked

# Запуск бота — переменные окружения передаются при docker run (--env-file .env)
ENV PYTHONPATH=/app/src
CMD ["uv", "run", "-m", "basic_ai_assistant.main"]
