.PHONY: install run run-speech-server docker-build docker-run

install:
	uv sync

run:
	PYTHONPATH=src uv run -m basic_ai_assistant.main

run-speech-server:
	PYTHONPATH=src uv run -m basic_ai_assistant.speech.speech_server

docker-build:
	docker build -t basic-ai-assistant .

docker-run:
	docker run --rm --env-file .env -v "$(CURDIR)/prompts:/app/prompts:ro" basic-ai-assistant