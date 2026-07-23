UV ?= uv
export UV_CACHE_DIR ?= /tmp/cmp-uv-cache
export UV_PROJECT_ENVIRONMENT ?= /tmp/cmp-cae-material-platform-venv
export UV_LINK_MODE ?= copy

.PHONY: bootstrap demo demo-verify demo-e2e demo-down lint typecheck check-architecture check-contracts docs-capture docs-screenshots docs-impact install-hooks verify-hooks pre-publish pre-publish-review generate-client release-quality performance-acceptance performance-fixture performance-production-scale soak-fault-acceptance governed-storage-acceptance product-pilot-acceptance \
	migrate test-unit test-contract test-migration test-integration test-postgresql test \
	web-build web-test run-api run-worker run-worker-once ci

bootstrap:
	$(UV) sync --all-groups

demo:
	docker compose -f deploy/compose/docker-compose.demo.yml up --build

demo-verify:
	docker compose -f deploy/compose/docker-compose.demo.yml run --rm --no-deps seed \
		python scripts/verify_full_demo.py --api-base-url http://api:8000/api/v1

demo-e2e:
	npx playwright install chromium
	npm run test:e2e --workspace @cmp/web

demo-down:
	docker compose -f deploy/compose/docker-compose.demo.yml down -v

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy --no-incremental

check-architecture:
	$(UV) run cmp-check-architecture --root backend/src

check-contracts:
	$(UV) run cmp-check-contracts lint --root .
	$(UV) run cmp-check-contracts compat --baseline contracts/http/openapi.baseline.yaml --current contracts/http/openapi.yaml

docs-capture:
	$(UV) run --with playwright python scripts/capture_current_product.py

docs-screenshots:
	$(UV) run cmp-check-user-guide --root .

docs-impact:
	$(UV) run cmp-check-doc-impact --root . --mode worktree

install-hooks:
	$(UV) run python scripts/install_git_hooks.py --root .

verify-hooks:
	$(UV) run python scripts/install_git_hooks.py --root . --check

pre-publish:
	$(UV) run cmp-pre-publish --root . --trigger manual

pre-publish-review:
	$(UV) run cmp-pre-publish --root . --trigger manual --independent-review

generate-client:
	$(UV) run cmp-generate-client --contract contracts/http/openapi.yaml --output generated/python/cmp_api_client/client.py

release-quality:
	$(UV) run cmp-release-quality generate --root . --ephemeral-local-key

performance-acceptance:
	$(UV) run cmp-performance-acceptance --acknowledge-immutable-demo-write

performance-fixture:
	@test -n "$(CMP_PERFORMANCE_POSTGRES_DSN)" || (echo "CMP_PERFORMANCE_POSTGRES_DSN is required" && exit 1)
	$(UV) run cmp-performance-fixture --postgres-dsn "$(CMP_PERFORMANCE_POSTGRES_DSN)" --acknowledge-immutable-synthetic-write

performance-production-scale:
	$(UV) run cmp-performance-acceptance --base-url http://127.0.0.1:18000/api/v1 --http-timeout-seconds 900 --upload-bytes 2147483648 --upload-part-bytes 67108864 --upload-maximum-python-memory-mib 192 --acknowledge-immutable-demo-write --require-production-scale

soak-fault-acceptance:
	$(UV) run cmp-soak-fault-acceptance --acknowledge-service-disruption

governed-storage-acceptance:
	$(UV) run cmp-governed-storage-acceptance --acknowledge-retained-test-object

product-pilot-acceptance:
	@test -n "$(CMP_PRODUCT_PILOT_POSTGRES_DSN)" || (echo "CMP_PRODUCT_PILOT_POSTGRES_DSN is required" && exit 2)
	$(UV) run cmp-product-pilot-acceptance --postgres-dsn "$(CMP_PRODUCT_PILOT_POSTGRES_DSN)"

migrate:
	@test -n "$(CMP_DATABASE_URL)" || (echo "CMP_DATABASE_URL is required" && exit 2)
	$(UV) run alembic -c alembic.ini upgrade head

test-unit:
	$(UV) run pytest backend/tests/unit tests/architecture

test-contract:
	$(UV) run pytest tests/contracts

test-migration:
	$(UV) run pytest tests/migrations

test-integration:
	$(UV) run pytest tests/integration

test-postgresql:
	@test -n "$(CMP_TEST_POSTGRES_DSN)" || (echo "CMP_TEST_POSTGRES_DSN is required" && exit 2)
	$(UV) run pytest -m postgresql tests/integration

test:
	$(UV) run pytest

web-build:
	npm run build --workspace @cmp/web

web-test:
	npm run test:web

run-api:
	$(UV) run uvicorn cmp.apps.api:app --host 127.0.0.1 --port 8000

run-worker:
	$(UV) run cmp-worker

run-worker-once:
	$(UV) run cmp-worker --once --json

ci:
	bash scripts/ci.sh
