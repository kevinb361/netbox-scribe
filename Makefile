.PHONY: format format-check lint type test public-check ci

format:
	uv run black .
	uv run ruff check --fix .

format-check:
	uv run black --check .

lint:
	uv run ruff check .

type:
	uv run mypy

test:
	uv run pytest -n auto

public-check:
	uv run python scripts/check_public_readiness.py

ci: format-check lint type test public-check
