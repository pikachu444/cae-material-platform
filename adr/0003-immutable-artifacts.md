# ADR-003: Content-addressed immutable artifact

## 먼저 읽기

- **무엇을 정했나요?** 원본 시험 파일과 큰 curve·table, solver 결과, release package는 내용의
  SHA-256으로 주소를 정해 object storage에 보관하며, raw와 최종 release 파일은 덮어쓰지 않습니다.
- **왜 중요한가요?** 같은 내용인지 checksum으로 확인할 수 있고, 원본이나 이미 배포한 결과가 나중에
  조용히 바뀌는 일을 막으면서 큰 파일을 database 밖에서 효율적으로 다룰 수 있습니다.
- **언제 읽나요?** upload·download, Artifact, object key, 파일 형식, 보관 정책을 바꾸거나 새 대용량
  결과를 저장할 때 읽습니다.
- **용어를 쉽게 말하면:** `content-addressed`는 파일 이름 대신 내용의 hash를 주소로 쓰는 방식입니다.
  `Artifact`는 보존하고 추적해야 하는 파일이나 결과물이고, `manifest`는 그 파일의 종류·크기·digest와
  관련 상태를 설명하는 기록입니다.
- **상태 표기는?** `Accepted`는 이 결정을 채택했다는 뜻입니다. 관련 기능이 모두 구현됐거나 현재
  환경에서 검증을 마쳤다는 뜻은 아닙니다.

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

