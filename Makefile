.PHONY: help install dev-install up down logs db-shell test test-unit test-integration lint format type-check clean download-filings seed reset-db

help:
	@echo "AuditChain — Available commands:"
	@echo ""
	@echo "  Setup:"
	@echo "    install              Install runtime dependencies"
	@echo "    dev-install          Install with dev dependencies"
	@echo ""
	@echo "  Infrastructure:"
	@echo "    up                   Start Postgres and Langfuse via docker-compose"
	@echo "    down                 Stop all containers"
	@echo "    logs                 Tail container logs"
	@echo "    db-shell             Open psql shell"
	@echo "    reset-db             Drop and recreate the database (destructive)"
	@echo ""
	@echo "  Data:"
	@echo "    download-filings     Download SEC filings for benchmark companies"
	@echo "    seed                 Seed companies table with known fraud cases"
	@echo ""
	@echo "  Quality:"
	@echo "    test                 Run all tests"
	@echo "    test-unit            Run unit tests only (fast)"
	@echo "    test-integration     Run integration tests (requires DB)"
	@echo "    lint                 Lint with ruff"
	@echo "    format               Auto-format with ruff"
	@echo "    type-check           Static type check with mypy"
	@echo ""
	@echo "  Misc:"
	@echo "    clean                Remove caches and build artifacts"

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"
	pre-commit install

up:
	docker compose -f infra/docker/docker-compose.yml up -d
	@echo "Waiting for Postgres to be ready..."
	@sleep 3
	@echo "Done. Postgres on :5432, Langfuse on :3000"

down:
	docker compose -f infra/docker/docker-compose.yml down

logs:
	docker compose -f infra/docker/docker-compose.yml logs -f

db-shell:
	docker exec -it auditchain-postgres psql -U auditchain -d auditchain

reset-db:
	docker compose -f infra/docker/docker-compose.yml down -v
	$(MAKE) up

download-filings:
	python -m auditchain.scripts.download_filings

seed:
	python -m auditchain.scripts.seed_companies

test:
	pytest

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix src tests

type-check:
	mypy src

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist *.egg-info
