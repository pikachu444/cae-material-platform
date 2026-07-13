#!/usr/bin/env bash
# Keep this script LF-normalized so `make ci` also works from Windows/WSL checkouts.
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/cmp-uv-cache}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${TMPDIR:-/tmp}/cmp-cae-material-platform-venv}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

uv sync --all-groups --locked
uv run ruff check .
uv run mypy
uv run cmp-check-architecture --root backend/src
uv run cmp-check-contracts lint --root .
uv run cmp-check-contracts compat \
  --baseline contracts/http/openapi.baseline.yaml \
  --current contracts/http/openapi.yaml
uv run pytest
npm ci --workspaces --include-workspace-root
npm run check
