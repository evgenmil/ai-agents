.PHONY: install run docker-build docker-run

install:
	uv sync

run:
	PYTHONPATH=src uv run -m basic_ai_assistant.main

docker-build:
	docker build -t basic-ai-assistant .

docker-run:
	docker run --rm --env-file .env -v "$(CURDIR)/prompts:/app/prompts:ro" basic-ai-assistant