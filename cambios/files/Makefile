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

# Multi-node topology (docs/SCALING.md): nginx + N web replicas +
# single indexer worker + redis. Scale reads with REPLICAS=n.
REPLICAS ?= 2
docker-up-multinode:
	docker compose -f docker-compose.multinode.yml up -d --scale app=$(REPLICAS)

docker-down-multinode:
	docker compose -f docker-compose.multinode.yml down

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app
