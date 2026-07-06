.PHONY: install test lint format docker-build docker-up docker-down docker-logs

install:
	pip install -e ".[dev]"

test:
	pytest tests/unit tests/integration -v

lint:
	ruff check app tests
	mypy app

format:
	ruff format app tests

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-up-full:
	docker compose --profile with-grobid up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app
