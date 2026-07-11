# T-06 Aggregate Revision Kernel 구현 기록

## 1. 추적성

- Task: `T-06`
- Requirements: `FR-CAT-001`, `FR-DAT-001`, `FR-DAT-006`, `FR-API-001`,
  `NFR-INT-001`, `NFR-SEC-003`, `NFR-SEC-006`, `NFR-MOD-001`
- ADR: `ADR-001`, `ADR-002`, `ADR-003`

## 2. 구현 경계

Kernel은 안정 aggregate identity, 현재 head, immutable revision metadata, canonical content
digest, optimistic concurrency, 초기 lifecycle projection을 제공한다. Material, 시험,
Dataset, provenance graph, audit chain, review transition은 만들지 않는다.

공통 저장소는 content를 저장하지 않는다. 각 bounded module은 자기 schema에 안정 identity
table과 typed revision table을 명시적으로 만들고, typed content를 column으로 mapping한다.
따라서 kernel은 generic EAV 또는 generic JSON revision table이 아니다.

## 3. 계층

| 계층 | 구현 |
| --- | --- |
| Domain | canonical JSON v1, SHA-256, tenant scope, revision/ref/event value object |
| Application | create/revise command, transaction/store port, fail-closed hook coordination |
| Persistence | explicit table pair를 받는 SQLAlchemy repository와 PostgreSQL CAS |
| Governance adapter | 새 revision의 초기 lifecycle event/projection을 같은 transaction에 기록 |
| HTTP contract | strong ETag parser, `If-Match` precondition, content-free revision metadata |

Domain/application은 FastAPI와 SQLAlchemy를 import하지 않는다.

## 4. Write transaction

### 최초 생성

1. typed content를 명시적 codec으로 canonical JSON value에 mapping한다.
2. CMP canonical JSON v1 bytes의 SHA-256을 계산한다.
3. stable identity가 첫 revision ID를 head로 가리키게 insert한다.
4. typed revision row를 `revision_no = 1`, `based_on_revision_id = NULL`로 insert한다.
5. 등록된 lifecycle/provenance/audit hook을 실행한다.
6. 하나라도 실패하면 전체 transaction을 rollback한다.

Identity와 첫 revision의 순환 FK는 `DEFERRABLE INITIALLY DEFERRED` constraint로 commit 시점에
검증한다.

### Revision 추가

1. `based_on_revision_id`와 `expected_current_revision_id`가 같은 concrete UUID인지 검증한다.
2. tenant와 aggregate에 속한 expected revision number를 읽는다.
3. identity head를 `WHERE current_revision_id = :expected` 조건으로 compare-and-swap한다.
4. 영향 row가 정확히 하나일 때만 `revision_no + 1` typed row를 insert한다.
5. stale transaction은 current concrete revision ref가 있는 `RevisionConflict`로 실패한다.

새 revision FK가 insert되기 전에 head를 CAS하므로 동시 writer는 identity row에서 직렬화되고,
패자는 revision row를 만들기 전에 실패한다. head와 revision FK는 deferred constraint가 같은
transaction의 원자성을 검사한다.

## 5. PostgreSQL migration

`20260711_001_T06_revision_kernel.py`는 다음만 생성한다.

- `revisioning`: RLS tenant context와 immutable/head-only trigger functions
- `governance.lifecycle_event`: append-only event
- `governance.lifecycle_projection`: event를 가리키는 current-state projection
- organization/project 복합 FK, tenant-first index, forced RLS policy

Application transaction은 다음 local setting을 설정한다.

```sql
select set_config('cmp.organization_id', :organization_id, true);
select set_config('cmp.project_id', :project_id, true);
```

설정이 없으면 RLS helper가 `NULL`을 반환하므로 policy는 fail closed다. Application role은
superuser/table owner/`BYPASSRLS`이면 안 된다. 실제 principal/role/classification ABAC는 T-04가
완성한다.

Future typed table은 최소 다음을 강제한다.

- identity: tenant scope, `id`, `current_revision_id`, creation/update metadata
- revision: tenant scope, `id`, aggregate FK, unique monotonic `revision_no`, same-aggregate base FK,
  schema ID/version, SHA-256, actor/reason/request/trace, typed content columns
- revision row의 `UPDATE`/`DELETE` trigger 차단
- identity row는 head와 `updated_at` 외 update 및 delete 차단
- head/base/identity FK에 organization/project를 포함하여 cross-project relation 차단

## 6. API contract

T-06은 concrete business endpoint를 만들지 않는다. 향후 `POST .../{id}/revisions`가 공통으로
사용할 component만 제공한다.

```text
ETag: "revision:<positive revision_no>:sha256:<64 lowercase hex>"
If-Match: 동일한 strong ETag 한 개
```

Weak ETag, wildcard, 복수 ETag, `latest` alias는 허용하지 않는다. `If-Match`가 current head와
다르면 endpoint adapter는 `412 Precondition Failed`를 사용한다. Body의
`expected_revision_id`를 사용하는 command라면 stale head는 `409 Conflict`를 사용할 수 있다.
두 경우 모두 current concrete revision ref를 problem detail에 제공하되 다른 tenant의 존재는
노출하지 않는다.

`RevisionMetadata`는 공통 metadata만 가지며 domain content는 각 resource schema가 정의한다.

## 7. 후속 hook

Application port의 `stage(RevisionCreated)`는 같은 transaction에서 fail closed로 실행된다.
현재 T-06은 initial lifecycle hook만 제공한다.

- T-05: append-only audit hook
- T-13: typed `wasRevisionOf` provenance hook
- T-16: transactional outbox hook
- T-29: lifecycle transition validation, review/approval event

## 8. 검증

- Unit: canonicalization/hash, concrete UUID, numbering, stale base, frozen record, hook rollback,
  tenant scoping, ETag
- Contract: positive/negative revision metadata, generic content 부재, runtime/source OpenAPI
- Migration: PostgreSQL offline DDL에 table/constraint/index/trigger/RLS 포함
- PostgreSQL integration: clean upgrade/downgrade, typed fixture, concurrent CAS, lifecycle atomicity,
  update/delete 차단, organization/project RLS 누출 차단

PostgreSQL integration은 `CMP_TEST_POSTGRES_DSN`이 있을 때 실행한다. 일반 CI에서는 offline
migration test가 항상 실행된다.
