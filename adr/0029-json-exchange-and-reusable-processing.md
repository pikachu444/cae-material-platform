# ADR-0029: JSON exchange, mapping profiles and reusable processing recipes

## 먼저 읽기

- **무엇을 정했나요?** `cmp.test-data`를 사람과 도구가 교환할 표준 JSON으로 두고, exact Mapping Profile과
  versioned Processing Recipe를 고정한 committed Run·Batch를 만듭니다. 큰 묶음은 manifest가 있는 ZIP을
  사용합니다.
- **왜 중요한가요?** CSV·XLSX 같은 입력 형식과 내부 저장 방식을 분리하면서, 어떤 channel mapping과
  method version으로 결과가 만들어졌는지 반복 실행할 수 있게 하기 위해서입니다.
- **언제 읽나요?** test data import/export, Mapping Profile, reusable Recipe·Batch, neutral material JSON,
  package 크기나 solver card 전달 형식을 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `canonical exchange`는 서로 다른 adapter가 공통으로 주고받는 표준 표현이고,
  `Mapping Profile`은 record·channel을 계산 물리량에 연결한 revision입니다. `Recipe`는 순서가 있는
  처리 단계의 불변 버전이며, preview는 저장된 실행 결과가 아닙니다.
- **상태 표기는?** `Accepted`는 이 교환·재사용 계약을 채택했다는 뜻입니다. JSON이 database 권위가
  되거나 모든 importer·processing method가 production 검증됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0003, ADR-0007 through ADR-0012, ADR-0027; T-52 through T-58

## Context

The platform currently preserves raw files and canonical columnar artifacts and exposes several
bounded processing/calibration workflows. Users also need a documented exchange format and a
general way to save a configured processing method, apply it again and execute it over a selection.

## Decision

1. `cmp.test-data` JSON is the canonical user exchange document for test metadata, channel
   semantics, original/normalized units and column-oriented observations. CSV/TSV/XLSX importers
   adapt into this contract; the original source remains immutable.
2. `Mapping Profile` is a revisioned mapping from configurable record attributes and test channels
   to calculation quantities. Calculations pin one exact profile revision.
3. `Processing Recipe` is a stable identity with immutable revisions. A revision contains ordered
   steps, exact method versions, JSON-Schema-validated options, input/output contracts and
   applicability predicates.
4. Preview is non-authoritative. A committed run pins Dataset, Mapping Profile and Recipe revisions.
   A batch pins an ordered input selection, performs compatibility preflight and records each member
   result without overwriting inputs or prior runs.
5. `cmp.neutral-material` JSON carries source digests, mapping and recipe revisions, intermediate
   curve stages, candidates, selected IR, applicability and solver mapping evidence. It can be
   validated, imported and exported.
6. A single document up to 25 MiB is delivered as JSON. Larger or multi-document transfers use a
   deterministic JSON+ZIP package with manifest and SHA-256 checksums. PostgreSQL and Parquet remain
   internal storage formats.
7. Solver cards remain solver-native ASCII files; they are not embedded as card strings in the
   neutral JSON.

## Consequences

- A user can exchange human-readable canonical data without making large JSON arrays the database
  execution format.
- Existing tabular and Bundle implementations become adapters and package infrastructure rather
  than being discarded.
- Method version and compatibility checks make saved and batch processing reproducible.

