# Observability deployment

The demo Compose stack sends OpenTelemetry traces and metrics from `cmp-api` and `cmp-worker` to a
vendor-neutral Collector over OTLP/HTTP. The Collector exposes Prometheus-format metrics on
`http://127.0.0.1:8889/metrics` and writes bounded trace summaries to its own container log. This is
development evidence, not a production retention backend or alert manager.

Application logs are structured JSON on stdout. The formatter accepts only documented operational
fields, removes bearer/JWT/DSN/password/secret patterns, and never serializes request URLs, query
strings, headers, bodies, raw test data, arbitrary log extras, or exception messages. A production
deployment must ingest stdout through its approved log agent and preserve the emitted `trace_id`.

The authenticated Governance operations panel calls
`GET /api/v1/operations/observability`. It is an auditor-protected, per-API-process snapshot for
quick diagnosis; it is deliberately not a cross-replica metrics database. Series use HTTP method,
FastAPI route template, and status family only. Unmatched/high-cardinality values collapse to
bounded labels.

## Local inspection

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml up -d --build
docker compose -f deploy/compose/docker-compose.demo.yml logs otel-collector
Invoke-WebRequest http://127.0.0.1:8889/metrics
```

## Restore drill

Run an isolated metadata and filesystem-object restore without replacing the demo database:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile operations run --rm restore-drill
```

The command uses a server-major-matched PostgreSQL 16 custom-format `pg_dump`, restores to a randomly named temporary PostgreSQL
database, copies immutable objects to a distinct snapshot directory, then compares relation counts,
sample object SHA-256/size, Release Artifact bytes, and provenance usage/generation references. It
drops only the generated temporary database and retains the JSON report under
`.cache/restore-drill/`. A passing laptop drill is evidence that the mechanism works; production
RPO/RTO acceptance still requires scheduled backups, versioned object storage, KMS access and an
operator-approved environment.

References: [OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/),
[HTTP metric semantic conventions](https://opentelemetry.io/docs/specs/semconv/http/http-metrics/),
and [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html).

