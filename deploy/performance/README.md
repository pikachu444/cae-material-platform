# Performance and security acceptance

This runbook exercises real product paths against the explicit local Docker demo and writes
canonical, digest-pinned JSON evidence. It is a bounded pilot gate, not a production-scale claim.

## Run

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

## Claims and thresholds

The bounded local gate currently enforces:

- Catalog p95 below 500 ms and p99 below 1.5 s;
- upload throughput of at least 1 MiB/s for the 2-MiB CI fixture;
- exact upload/download digests and all three negative security responses;
- 64-MiB inline Bundle assembly within 30 seconds.

These thresholds catch regressions in the laptop/reference composition. They do not replace
production acceptance. `NFR-PERF-002` requires at least 10,000 visible Materials before the search
result can be marked evaluated, while `NFR-PERF-004` requires a 2-GiB streaming fixture in production
infrastructure. Until both are exercised, the report must retain:

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
