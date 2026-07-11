# CAE Material Platform

Status: revision-kernel foundation (`T-01` + `T-02` + `T-06`)

Version: `0.2.0`

This repository is the implementation workspace for the CAE material-data platform defined in
`docs/`. The current scope deliberately contains no material, test, fitting, or solver-card
business implementation. Database support is limited to the domain-neutral T-06 revision kernel.

## Implemented foundation

- Modular-monolith Python package and bounded-module namespaces
- FastAPI `GET /api/v1/health` endpoint
- Empty durable-worker process shell with a one-cycle verification mode
- Architecture dependency checker
- OpenAPI 3.1 and AsyncAPI baseline contracts
- JSON Schema baselines for jobs, plugin packages, and Material Model IR envelope
- Contract linter and minimal generated health client
- Unit, architecture, contract, and live-process integration tests
- Framework-free canonical hashing and typed aggregate revision application service
- SQLAlchemy adapter for explicit stable-identity/typed-revision table pairs
- Alembic/PostgreSQL immutability guards, tenant RLS helpers, and lifecycle projection
- Strong revision ETag and common content-free revision metadata contracts

## Prerequisites

- Python 3.12+
- `uv`
- `make`
- PostgreSQL 16+ for migration and persistence integration tests

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
make test-migration
make test-integration
make test
make ci
```

Apply the production migration to an explicitly selected database:

```bash
CMP_DATABASE_URL=postgresql+psycopg://... make migrate
```

The PostgreSQL integration suite creates and removes its own temporary database. Point it only at
an isolated PostgreSQL admin database:

```bash
CMP_TEST_POSTGRES_DSN=postgresql+psycopg://... make test-postgresql
```

## Scope guard

Read `AGENTS.md` before changing this repository. Production tensile standards, material models,
calibration choices, solver cards, and validation criteria remain `TBD`. T-06 provides a typed-table
pattern and never a generic revision/EAV content store. Do not add business tables or
production-looking reference implementations before the corresponding decision gates.

## Traceability

- Tasks: `T-01`, `T-02`, `T-06`
- Requirements: `FR-CAT-001`, `FR-DAT-001`, `FR-DAT-006`, `FR-API-001`, `NFR-INT-001`,
  `NFR-SEC-003`, `NFR-SEC-006`, `NFR-MOD-001`, `NFR-COMP-001`, `NFR-COMP-002`, `NFR-DOC-001`
- Decisions: `ADR-001`, `ADR-002`, `ADR-003` (with `ADR-004` and `ADR-005` scope guards)

