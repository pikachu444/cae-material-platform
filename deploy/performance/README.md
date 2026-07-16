# Performance and security acceptance

This runbook exercises real product paths against the explicit local Docker demo and writes
canonical, digest-pinned JSON evidence. It has two explicit modes: a bounded laptop/CI regression
gate and an opt-in production-scale acceptance gate. A bounded pass is never promoted into a
production-scale claim.

## Bounded run

Start the demo and confirm it contains at least one completed Bulk Export Bundle. Then run:

```powershell
uv run cmp-performance-acceptance --acknowledge-immutable-demo-write
```

The acknowledgement is mandatory because every run exercises the actual multipart API and appends
an immutable Ingestion Event. Content-addressed Raw Asset bytes may deduplicate, but the historical
ingestion fact is never deleted. Do not point this command at production or a shared environment.

The command verifies and records:

- authenticated Catalog metadata latency with 5 warmups and 30 measured requests;
- unauthenticated and malformed-bearer rejection plus unsafe upload filename rejection;
- a real 2 MiB upload split into 32 64-KiB parts, a tampered capability rejection, terminal Raw
  Asset SHA-256/size and measured throughput;
- short-lived authorization followed by repeated streaming download of the largest visible Bundle,
  with archive SHA-256 and size verification;
- the real deterministic Bundle builder assembling the complete 64-MiB inline domain limit,
  checksum coverage, elapsed time and incremental Python allocation peak.

Evidence is stored under `.cache/performance-acceptance/<UTC timestamp>/report.json` with a separate
`report.sha256`. The command refuses a dirty working tree so `source_commit` cannot silently refer to
different code. `verify_report` rejects byte substitution and non-canonical JSON.

## Production-scale run

Use an isolated demo database/object volume. The fixture command only appends deterministic
synthetic Material identities and immutable revisions; it never deletes or updates existing
revisions. It refuses a maintenance database and, unless explicitly overridden, any non-loopback
database host.

```powershell
docker compose `
  -f deploy/compose/docker-compose.demo.yml `
  -f deploy/performance/docker-compose.production-scale.yml `
  up -d --build postgres api worker web

$env:DATABASE_URL = "postgresql://cmp_owner:cmp_owner@127.0.0.1:54329/cmp"
uv run cmp-performance-fixture --acknowledge-immutable-demo-write --target-materials 10000

uv run cmp-performance-acceptance `
  --base-url http://127.0.0.1:18000/api/v1 `
  --http-timeout-seconds 900 `
  --upload-bytes 2147483648 `
  --upload-part-bytes 67108864 `
  --upload-maximum-python-memory-mib 192 `
  --acknowledge-immutable-demo-write `
  --require-production-scale
```

The override exposes the API at `127.0.0.1:18000`, permits a 2-GiB upload and uses 64-MiB parts.
The harness generates deterministic bytes without holding the complete object in memory, verifies
the server-side digest and size, and fails when its measured Python allocation exceeds the declared
limit. `--require-production-scale` also requires the RLS-filtered Catalog response to report at
least 10,000 visible Materials and its p95 latency to remain below the production threshold.

## Claims and thresholds

The bounded local gate enforces:

- Catalog p95 below 500 ms and p99 below 1.5 s;
- upload throughput of at least 1 MiB/s for the 2-MiB CI fixture;
- exact upload/download digests and all three negative security responses;
- 64-MiB inline Bundle assembly within 30 seconds.

These thresholds catch regressions in the laptop/reference composition. `NFR-PERF-002` requires at
least 10,000 visible Materials before the search result can be marked evaluated, while
`NFR-PERF-004` requires a 2-GiB streaming fixture in the production-scale composition. Until both
are exercised, the report must retain:

```json
{"bounded_local_gate_passed":true,"production_scale_accepted":false}
```

Use `--require-production-scale` in the production-scale environment; it makes either missing scale
condition fail the command. Increasing a threshold or reducing a fixture requires explicit review,
an updated NFR decision and new baseline evidence.

## 2026-07-16 local evidence

Commit `9d5c1476d13d5508311c02d6c574135ff49dad06` produced report SHA-256
`3a2464dbf27f5359f19dfc865e0254b68dc55a3040f665a85eb84491b7bbdaa7`. Catalog p95/p99 were
44.292/45.978 ms over 4 visible Materials; upload throughput was 1.266 MiB/s over 32 parts; Bundle
download p95 was 21.894 ms; and 64-MiB inline assembly took 1.950184 seconds with 70,112,942 bytes
incremental Python peak. The bounded gate passed and production scale remained explicitly false.

## 2026-07-16 production-scale evidence

Commit `b506f6415f49774fb32692cf680ed56c866e9902` produced report SHA-256
`96d75ca787695ad5848b0b65562554a93f8aa63dd204b82d92e159f723cef481`. The isolated PostgreSQL
fixture contained exactly 10,000 visible Materials. Catalog p95/p99 were 182.128/187.088 ms over 30
requests. The API accepted and finalized exactly 2,147,483,648 bytes in 32 64-MiB parts at
22.999 MiB/s; server-side digest and size matched, the largest generated chunk was 64 MiB and peak
incremental Python allocation was 67,164,359 bytes under the 192-MiB gate. Bundle download,
64-MiB inline assembly and auth/capability/path negative checks also passed. The report records
`production_scale_accepted=true`.

This result closes the 10,000-Material search and 2-GiB streaming gates only. Long-running soak,
broad fault injection, object-lock/KMS/retention and production identity/token rotation remain
separate release conditions.

## Mixed-workload soak and fault drill

The local composition fault gate deliberately interrupts services. It accepts only loopback API/web
URLs and repository-owned Compose files, operates on the allow-listed `postgres`, `api`, `worker`
and `web` services, and always attempts pending recoveries in reverse order. Run it only on the
isolated production-scale demo:

```powershell
uv run cmp-soak-fault-acceptance `
  --base-url http://127.0.0.1:18000/api/v1 `
  --web-url http://127.0.0.1:5173 `
  --soak-seconds 300 `
  --fault-hold-seconds 5 `
  --minimum-materials 10000 `
  --acknowledge-service-disruption
```

Three concurrent workers execute Catalog, Bundle-list and health requests before, during and after
the fault sequence. Expected failures are counted only while a fault/recovery window is open. A
window closes after every relevant operation remains continuously stable, not after the first
successful response. Acceptance requires zero failures outside those windows, ordinary p95 below
2 seconds, recovery below 60 seconds, per-service memory growth below 512 MiB, unchanged authorized
Material cardinality and a byte-identical immutable Bundle download.

The 2026-07-16 five-minute production-pilot run used source commit
`4563bd68c4e36fe743099e9e62733979b85e54bd` and produced canonical report SHA-256
`d68253e7ce75528a0f807b945f98019e37f55052b2f8457d54076ff6e85f535c`. Total elapsed time was
373.361256 seconds with 3,243 samples and zero ordinary failures. Catalog/Bundle/health p95 were
223.419/45.849/23.423 ms. PostgreSQL, API, worker and web recovered in
2.809797/8.362320/3.200068/2.665459 seconds. All memory-growth gates passed, the Catalog remained
10,000 and Bundle SHA-256 remained
`04f6aeca5f0f0ff48448dcb0f3c2e4d3e361b890027869b7f3943562d27097ab`.

The demo uses a shared local filesystem volume, not an independently managed object-storage
service. Therefore this report does not claim production object-storage outage, object lock, KMS,
retention, cross-node failover or an overnight endurance run. Those remain separate gates.

## Final product-pilot acceptance

After the normal demo seed and worker have completed, verify the actual PostgreSQL-backed product
workflow rather than only infrastructure throughput:

```powershell
$env:CMP_PRODUCT_PILOT_POSTGRES_DSN = `
  "postgresql://cmp_owner:cmp_owner_development_only@127.0.0.1:54329/cmp"
uv run cmp-product-pilot-acceptance
```

The read-only gate requires a clean Git tree. It authenticates through the explicit local-demo
issuer and verifies the exact Steel, Polymer and Elastomer Material/State/Property/Test/Model
identities. It downloads the promoted cards and checks persisted SHA-256 values and solver keyword
markers. It then downloads a complete 22-component Bundle, independently verifies `manifest.json`,
`checksums.sha256`, every component byte digest and all required raw/Dataset/IR/schema/mapping/card
representations. Finally it uses a read-only PostgreSQL transaction to confirm the same Material,
Material Model and Bundle identities are durable rows. Canonical evidence is written under
`.cache/product-pilot-acceptance/<UTC timestamp>/`.
