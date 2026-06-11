.PHONY: install run run-mcp-bank dataset dataset-upload

install:
	uv sync
	cd mcp/mcp-bank-agent && uv sync

run:
	uv run python src/bot.py

run-mcp-bank:
	cd mcp/mcp-bank-agent && uv run python server.py

dataset:
	uv run python src/dataset_synthesizer.py --create

dataset-upload:
	uv run python src/dataset_synthesizer.py --upload
