#!/usr/bin/env bash
# Keep this script LF-normalized so `make ci` also works from Windows/WSL checkouts.
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/cmp-uv-cache}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${TMPDIR:-/tmp}/cmp-cae-material-platform-venv}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

uv sync --all-groups --locked
uv run ruff check .
# Windows and WSL may share the checkout but use different Python/typeshed builds.
# Never consume another platform's incremental cache in the authoritative CI gate.
uv run mypy --no-incremental
uv run cmp-check-architecture --root backend/src
uv run cmp-check-contracts lint --root .
uv run cmp-check-contracts compat \
  --baseline contracts/http/openapi.baseline.yaml \
  --current contracts/http/openapi.yaml
uv run cmp-check-user-guide --root .
uv run pytest
npm ci --workspaces --include-workspace-root
npm run check
