# T-13 typed provenance 구현 기록

Status: `complete`

## 1. 범위와 추적성

- Task: `T-13`
- Requirements: `FR-DAT-005`, `FR-DAT-006`, `NFR-REP-002`, `NFR-SEC-003`,
  `NFR-SEC-006`
- Decisions: `ADR-001`, `ADR-002`, `ADR-003`
- 선행 구현: `T-03`, `T-04`, `T-06`, `T-09`, `T-10`

이 단위는 W3C PROV 의미를 따르는 Entity/Activity/Agent와 usage, generation,
derivation, association, revision, attribution 관계를 PostgreSQL typed relation으로
구현한다. RDF/OWL, graph DB, unrestricted edge table, Material/Dataset/Test domain table은
추가하지 않는다.

T-14가 소유하는 recursive upstream/downstream/impact endpoint, graph pagination, 10-hop/10k
edge 성능 gate는 이 단위에서 구현하지 않는다. T-13 public API는 immutable Entity lookup과
해당 Entity의 generation completeness 상태까지만 제공한다.

## 2. 권장 가정

Dataset Revision 등 후속 owner table은 아직 존재하지 않는다. 따라서 provenance core가
이를 미리 만들거나 임의 조회하지 않고 `ProvenanceReferenceResolver` 포트를 사용한다.

- Raw Asset과 Artifact는 기존 T-09/T-10 immutable facts로 검증한다.
- revision reference는 owning typed module이 UUID, digest, tenant/classification을 검증해
  attestation한다.
- `aggregate.head`, `aggregate.latest` 같은 moving alias는 domain과 contract에서 거부한다.
- Raw Asset만 primary generation 없이 source Entity로 등록할 수 있다.
- Artifact와 revision Entity는 같은 transaction 안에서 primary generation 하나를 가져야
  한다.
- production composition에는 owner-module resolver가 명시적으로 주입되어야 한다. resolver가
  없으면 write service는 fail closed하며 read service만 구성된다.

## 3. PostgreSQL 구조

Migration: `20260713_008_T13_typed_provenance.py`

| Relation | 책임 | 변경 규칙 |
| --- | --- | --- |
| `provenance.entity` | immutable content reference와 digest | append-only |
| `provenance.activity` | terminal run/revision commit fact | append-only |
| `provenance.agent` | user/service/plugin/org 책임 주체 | append-only |
| `provenance.usage` | Activity input Entity와 role/ordinal | append-only |
| `provenance.generation` | Entity의 유일한 primary Activity | append-only, Entity당 1개 |
| `provenance.derivation` | generated→used 의미적 파생 | append-only, DAG |
| `provenance.association` | Activity 책임 Agent와 optional plan | append-only |
| `provenance.revision` | newer→prior content revision | append-only, DAG |
| `provenance.attribution` | Entity 작성 책임 Agent | append-only |

모든 relation은 organization/project/classification을 반복해 composite foreign key로 scope를
고정한다. 핵심 relation에 JSONB/EAV payload나 자유로운 `edge_type`을 사용하지 않는다.

### DB invariant

- reference kind는 `raw_asset | artifact | revision`만 허용한다.
- Raw Asset/Artifact reference의 tenant, classification, UUID, digest는 source row와 일치해야
  한다.
- user/service Agent는 활성 principal type과 일치해야 하고 Plugin Package Agent는 동일
  tenant/classification package를 참조해야 한다.
- primary generation이 필요한 Entity는 deferred constraint trigger로 transaction 종료 전에
  generation 하나를 요구한다.
- input/output requirement와 책임 Agent가 없는 Activity는 commit되지 않는다.
- usage-generation, derivation, revision edge는 recursive dependency 검사로 cycle을 거부한다.
- revision은 같은 reference type의 두 revision만 연결하며 newer generation Activity가 prior를
  실제로 사용해야 한다.
- 모든 node/relation update/delete는 immutable-row trigger로 거부한다.
- 모든 table에 `ENABLE/FORCE ROW LEVEL SECURITY`와 classification-aware policy를 적용한다.

## 4. Application 경계

`ProvenanceService.commit_activity`는 public graph-write endpoint가 아닌 owner-module 내부
commit service다.

1. 기존 command authorization이 파생한 transaction-local `provenance.read/write` capability를
   확인한다.
2. owner resolver가 input/output Entity와 Agent reference를 검증한다.
3. activity manifest를 canonical JSON으로 digest한다.
4. Entity/Agent를 immutable reference 기준으로 재사용하거나 삽입한다.
5. Activity, usage, association, generation, derivation을 하나의 transaction에 기록한다.
6. 동일 domain run과 동일 digest는 replay하고, 다른 graph는 conflict로 거부한다.

`SqlAlchemyRevisionProvenanceHook`는 T-06의 `SqlRevisionHook` 계약을 구현한다. caller가 연
typed revision transaction 안에서 새 revision Entity, revision-commit Activity, author Agent,
generation/attribution, `wasRevisionOf`를 함께 기록한다. prior revision provenance가 없으면
fail closed한다.

## 5. Public API

```text
GET /api/v1/provenance/entities/{entity_id}
```

응답은 Entity UUID, tenant/classification, entity/reference type, immutable UUID/digest,
generation requirement/activity, completeness, recorded actor/time을 반환한다. polymorphic DB
table 이름, object storage key, raw payload는 반환하지 않는다. bearer authentication과
`provenance.read` 권한이 모두 필요하다.

## 6. 검증

- unit: moving head, input/agent/output requirement, derivation membership, owner scope,
  completeness state
- contract/API: positive revision Entity, moving-head negative fixture, read-only operation,
  sanitized 404/422, DB/storage detail 비노출
- PostgreSQL integration: Raw Asset→synthetic revision Activity, exact replay, typed relation,
  duplicate generation, reverse cycle, orphan Entity, incomplete Activity, cross-project RLS,
  immutable mutation, T-06 revision hook
- migration: nine explicit tables, recursive cycle guard, deferred completeness trigger,
  forced RLS, no JSONB/EAV/business schema, real upgrade/downgrade

Synthetic revision resolver는 test-only이며 production Dataset, importer, processing, Material,
fitting, solver 기능을 구현하거나 암시하지 않는다.
