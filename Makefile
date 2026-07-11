UV ?= uv
export UV_CACHE_DIR ?= /tmp/cmp-uv-cache
export UV_PROJECT_ENVIRONMENT ?= /tmp/cmp-cae-material-platform-venv
export UV_LINK_MODE ?= copy

.PHONY: bootstrap lint typecheck check-architecture check-contracts generate-client \
	test-unit test-contract test-integration test run-api run-worker run-worker-once ci

bootstrap:
	$(UV) sync --all-groups

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy

check-architecture:
	$(UV) run cmp-check-architecture --root backend/src

check-contracts:
	$(UV) run cmp-check-contracts lint --root .
	$(UV) run cmp-check-contracts compat --baseline contracts/http/openapi.baseline.yaml --current contracts/http/openapi.yaml

generate-client:
	$(UV) run cmp-generate-client --contract contracts/http/openapi.yaml --output generated/python/cmp_api_client/client.py

test-unit:
	$(UV) run pytest backend/tests/unit tests/architecture

test-contract:
	$(UV) run pytest tests/contracts

test-integration:
	$(UV) run pytest backend/tests/integration tests/integration

test:
	$(UV) run pytest

run-api:
	$(UV) run uvicorn cmp.apps.api:app --host 127.0.0.1 --port 8000

run-worker:
	$(UV) run cmp-worker

run-worker-once:
	$(UV) run cmp-worker --once --json

ci:
	bash scripts/ci.sh
