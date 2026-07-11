# ADR-003: Content-addressed immutable artifact

- 상태: Accepted
- 기준일: 2026-07-11

## Context

원본 시험 파일, curve, solver deck/result, release package는 크고 DB transaction과 수명이 다르다. 원본 불변성과 integrity가 필요하다.

## Decision

대형 file/array는 S3-compatible object storage에 SHA-256 content-addressed key로 저장한다. Raw와 release final key는 overwrite하지 않는다. Normalized curve/table은 Arrow schema와 Parquet을 기본으로 한다. DB는 manifest, digest, relation, state를 관리한다.

## Consequences

- dedup, integrity, large streaming이 가능하다.
- DB/object store 비원자성을 staging/finalize/reconciler로 처리해야 한다.
- object lock/versioning과 backup 정책이 필요하다.

## Revisit trigger

실제 workload benchmark가 Parquet/S3 contract를 충족하지 못하고 다른 형식이 명백히 우수할 때. Raw original format은 항상 그대로 보존한다.

