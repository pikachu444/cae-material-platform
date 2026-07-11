# CAE Material Platform

Status: foundation only (`T-01` + `T-02`)  
Version: `0.1.0`

This repository is the implementation workspace for the CAE material-data platform defined in
`docs/`. The current scope deliberately contains no material, test, fitting, solver-card, or
database business implementation.

## Implemented foundation

- Modular-monolith Python package and bounded-module namespaces
- FastAPI `GET /api/v1/health` endpoint
- Empty durable-worker process shell with a one-cycle verification mode
- Architecture dependency checker
- OpenAPI 3.1 and AsyncAPI baseline contracts
- JSON Schema baselines for jobs, plugin packages, and Material Model IR envelope
- Contract linter and minimal generated health client
- Unit, architecture, contract, and live-process integration tests

## Prerequisites

- Python 3.12+
- `uv`
- `make`

## Start

```bash
make bootstrap
make test
make run-api
```

In another terminal:

```bash
curl http://127.0.0.1:8000/api/v1/health
make run-worker-once
```

## Development commands

```bash
make lint
make typecheck
make check-architecture
make check-contracts
make test-unit
make test-contract
make test-integration
make test
make ci
```

## Scope guard

Read `AGENTS.md` before changing this repository. Production tensile standards, material models,
calibration choices, solver cards, and validation criteria remain `TBD`. Do not add business tables
or production-looking reference implementations before the corresponding decision gates.

## Traceability

- Tasks: `T-01`, `T-02`
- Requirements: `NFR-MOD-001`, `NFR-COMP-001`, `NFR-COMP-002`, `NFR-DOC-001`
- Decisions: `ADR-001` through `ADR-005`

