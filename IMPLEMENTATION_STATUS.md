# Implementation Status

Date: `2026-07-11`
Foundation version: `0.3.0`

## Completed

- `T-01`: modular-monolith repository skeleton, bounded-module namespaces, deployable API and
  worker shells, developer commands, architecture rules and regression fixtures
- `T-02`: OpenAPI/AsyncAPI baseline, JSON Schema registry, positive/negative contract examples,
  deterministic minimal client generation, compatibility detector and validation pipeline
- `T-03`: strict OIDC JWT access-token validation, user/service principal resolution, immutable
  external identity projection, request security context, `/api/v1/me`, and development test IdP
- `T-06`: framework-free aggregate revision kernel, explicit typed-table SQLAlchemy adapter,
  PostgreSQL/Alembic immutability and tenant primitives, initial lifecycle event/projection,
  strong ETag and revision metadata contracts

## Runtime proof

- FastAPI health endpoint: `GET /api/v1/health`
- Empty worker verification: `cmp-worker --once --json`
- Generated client calls a live Uvicorn process in integration tests
- Worker starts in a separate subprocess and exits successfully in one-cycle mode
- OIDC validation uses exact issuer/audience, explicit asymmetric algorithms, configured JWKS,
  access-token type checking, required organization/project context, and sanitized failures
- PostgreSQL principal persistence keeps `(issuer, subject)` immutable, produces opaque UUIDv4 IDs,
  and serializes concurrent JIT provisioning without duplicate actors
- Revision writes use concrete UUID bases, canonical SHA-256, transaction-local fail-closed hooks,
  and PostgreSQL compare-and-swap head advancement
- PostgreSQL integration uses a migration-managed explicit typed fixture; no generic EAV/content
  table exists

## Validation result

Commands: `make ci` and `make test-postgresql` with an ephemeral PostgreSQL 16-compatible server

```text
Ruff: passed
mypy strict: passed (68 source/test files)
Architecture rules: passed
Contract lint: passed
OpenAPI compatibility: passed
make ci: 64 passed, 10 PostgreSQL-gated tests skipped without CMP_TEST_POSTGRES_DSN
Full suite with ephemeral PostgreSQL: 74 passed
```

## Intentionally absent

- RBAC/ABAC, tenant role binding, and application-role RLS enforcement (`T-04`)
- Material, test, dataset, typed provenance, audit-chain, or job implementations
- Production plugins
- Constitutive equations, fitting algorithms, solver cards, or validation thresholds
- Frontend application

## Next gate

Per the repository blueprint, the next task is `T-04`: deny-by-default RBAC/ABAC and PostgreSQL RLS
session enforcement using the T-03 principal/request context. Audit (`T-05`), catalog (`T-07`), and
provenance (`T-13`) remain separate tasks; none is implied complete by the T-03/T-06 interfaces.

