# Issue #204 — Schema Definition Bundle contract and dry-run planner

## Disposition

- 상태: **`INDEPENDENT_AUDIT_PASSED; FINAL_EVIDENCE_SHA_REAUDIT_PENDING`**
- 시작 기준선: `main@a8189656a79058df000de1fb28c4dfda111e4bd9`
- 작업 branch: `agent/issue-204-schema-bundle-dry-run`
- managed worktree: `C:\SourceCodes\cae-material-platform-issue204`
- PR: [#233](https://github.com/pikachu444/cae-material-platform/pull/233) (draft)
- merge: pending
- independent review: correction SHA `3e30bb55c67869f70a079d2396a530b7d4fdcdd6` PASS; 이 결과를
  포함한 final evidence-only SHA 확인 예정
- 계약: Schema Definition Bundle `1.0.0`, dry-run plan `1.0.0`, HTTP `0.33.0`

## 시작 시 구현 분류

| 분류 | 시작 `main` 상태 |
| --- | --- |
| 완료 | configurable Database/Profile/Table/Attribute/Layout/placement/Link Type의 stable identity·immutable revision·RLS·publication, immutable Artifact byte/digest/integrity read, provenance/audit/outbox 기반 |
| 부분 구현 | runtime Database/Profile/publication API가 있었으나 manual OpenAPI의 해당 경로가 누락됨 |
| 미구현 | versioned arbitrary-cardinality Bundle/plan 계약, strict local-only resolver, Catalog projection, deterministic compare, exact Artifact-bound plan API, PostgreSQL no-write evidence와 synthetic fixtures |

Database migration, generic EAV/opaque JSON authority, apply/publish/rollback, Unit Profile,
Administration UI, 재료 모델과 외부 resolver는 추가하지 않았다.

기존 configurable machine contract의 key pattern은 `_` 종결도 구조상 허용하지만 runtime
`CatalogDatabaseContent`, `CatalogProfileContent`, `CatalogTableContent`와 Attribute는 이를 거부한다.
#204 Bundle은 적용 불가능한 plan을 만들지 않도록 실제 runtime 제약의 교집합(1..64자
lower_snake_case, `_` 종결 불가)으로 fail closed하며 이 기존 계약 불일치를 확장하지 않는다.

기존 `20260925_094_issue160` downgrade는 이전
`ck_product_access_role`(`administrator | reviewer | user`)을 복원하지 않아 configurable Catalog의
기존 downgrade→upgrade 회귀 setup이 latest main에서 실패했다. 새 migration이나 upgrade schema를
추가하지 않고 predecessor constraint를 downgrade에서 복원하는 bounded 가역성 수정만 포함했다.

## Primary user journey와 acceptance

1. 관리자는 synthetic/non-production Bundle JSON을 기존 Artifact 경계로 저장해 exact immutable
   Artifact ID와 SHA-256을 얻는다. Artifact와 bundle의 organization/project/classification도
   정확히 일치해야 한다.
2. `POST /api/v1/catalog/schema-definition-bundles:plan`에 두 값을 함께 보내면 서버가 저장된 원본
   bytes, media type, size와 digest를 검증한다.
3. strict JSON과 draft 2020-12 subset을 검증하고 local fragment 또는 bundle에 선언된 exact record
   `$id`만 resolve한다. 외부 URL·파일·네트워크와 알 수 없는 keyword는 위치·조치가 있는 오류다.
4. 임의 개수의 record 정의를 기존 configurable Catalog 객체로 투영하고 dependency order에 따라
   현재 snapshot과 비교해 `create/update/no-op/conflict/error` action을 반환한다.
5. 사용자는 diagnostic을 고친 새 immutable Artifact로 같은 endpoint를 재시도한다. 같은 exact
   Artifact와 같은 snapshot은 동일한 plan fingerprint와 byte/semantic-equivalent 응답을 만든다.
6. 호출 전후 Catalog revision/current pointer, publication, Artifact, governance, provenance, audit와
   outbox 상태가 같고, 입력에서 사라진 기존 `legacy_records`는 action/delete/ownership 대상이 아니다.

Recovery는 source Artifact를 수정하지 않고 새 Artifact로 재시도하는 것이다. plan 저장 테이블이나
apply side effect가 없으므로 실패한 dry-run을 rollback할 상태도 없다.

## Contract와 fixture

- `contracts/catalog/schema-definition-bundle.schema.json`: record schema 1..N, draft 2020-12,
  closed supported keyword set, exact scope/version/key/schema checksum.
- `contracts/catalog/schema-definition-plan.schema.json`: exact source Artifact, snapshot/plan
  fingerprints, ordered actions/diagnostics와 고정된 no-write fields.
- positive fixture 두 개는 서로 다른 cardinality(1, 3)와 3-record dependency chain을 제공한다.
  domain 회귀는 같은 규칙으로 17-record bundle과 3-record의 모든 6개 입력 순열도 검증한다.
- negative fixture는 unsupported bundle version과 nested `$id` resolver scope를 public contract에서
  거부한다. Domain/API 회귀는 checksum/key/duplicate member/duplicate projected key,
  URL·Windows/relative/file path, nested `$id`/`$schema`, missing record, bad pointer, cycle, unknown
  extension, unsafe type와 depth를 모두 synthetic 변형으로 검증한다.
- fixture의 이름과 개수는 제품 계약이 아니며 모두 synthetic/non-production이다.

## PostgreSQL no-write evidence

실행 명령:

```powershell
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres"
uv run pytest tests/integration/test_schema_bundle_planner_postgresql.py -vv -s -ra
```

격리된 임시 database와 `NOSUPERUSER`, `NOBYPASSRLS` application role을 migration head에서 만들었다.
Bundle Artifact와 기존 legacy Database/Profile/Table/Attribute/Layout/publication을 먼저 commit해
outbox, governance, provenance와 audit에도 실제 행을 만든 뒤 baseline을 잡았다. 이후 성공한 plan을
두 번 호출하고 cross-project RLS 실패를 확인했다. 별도 synthetic Database는 동일 content의 새
revision을 append해 Profile의 pin만 과거 revision으로 만든 뒤, Database `no-op`과 Profile
`update(dependency_revision_changes)`가 함께 나오는 것도 실제 persistence snapshot에서 검증했다.

| 관찰 | 결과 |
| --- | --- |
| 대상 | `artifact`, `audit`, `catalog`, `events`, `governance`, `provenance`의 base table 87개, baseline 91행 |
| before digest | `9532abdea53313867e589357d77a15fd6796c5d4ecb2635fbc0c4269352858e8` |
| first plan 뒤 digest | `9532abdea53313867e589357d77a15fd6796c5d4ecb2635fbc0c4269352858e8` |
| second plan/RLS negative 뒤 digest | `9532abdea53313867e589357d77a15fd6796c5d4ecb2635fbc0c4269352858e8` |
| PostgreSQL access mode | 두 snapshot 모두 `transaction_read_only=on` |
| source Artifact SHA-256 | `392491cfe718a0a672043f225b3f83348a265d5a088b22c7caebaaed44fbdf6f` |
| repeated plan fingerprint | `1b6e3c06dd9d7880754f77a1ec7f51e4aa4542beaf0c83c707573b7a3b27a92c` |
| 결과 | PASS — current pointer/publication/Artifact/provenance/audit/outbox 포함 전후 byte-equivalent state |

Artifact UUID와 row UUID는 격리 실행마다 새로 생성되므로 위 run의 identity는 PR test log에 남기고,
acceptance는 전체 table content digest의 전/중간/후 동일성과 read-only mode로 판정한다.

## 검증 상태

| 검사 | 결과 |
| --- | --- |
| Bundle domain/parser/projection/determinism | PASS — 20 test functions |
| Contract/API/configurable Catalog targeted regression | PASS — 92 tests |
| PostgreSQL configurable Catalog + exact Artifact/RLS/no-write | PASS — 2 tests, zero skip |
| contract lint/OpenAPI compatibility/architecture | PASS |
| changed-source Ruff/Mypy | PASS — Ruff, 5 core source files Mypy |
| database migration | N/A — 필요성이 없고 추가하지 않음 |
| frontend/browser/viewport | N/A — backend/contract/API 범위, UI 변경 없음 |
| canonical Compose | PASS — managed worktree에서 `--profile test --build --force-recreate`; API container health `200`, version `0.33.0`, PostgreSQL test 재실행 PASS |
| documentation impact/user-guide/diff | PASS — docs impact 31 changed files, visual source 없음; user-guide와 `git diff --check` PASS |
| pre-publish | PASS — correction head manual `7c67669123aec639091fa28bd22a71e8f475bd90240c8534a6802741fd358166`; git pre-push `33b187d05e4272dd9ce1f2bcc5ac31981891f17b25a2bbb3b45916f4cb966aa6` |
| independent Balanced audit | initial SHA `8ff133093fa343b1251f489a551b4637623067d1`: CHANGES_REQUESTED — nested `$id`/`$schema` machine contract/runtime parity major 1건. Root/nested contract 분리와 negative fixture·parity 회귀 후 correction SHA `3e30bb55c67869f70a079d2396a530b7d4fdcdd6`: PASS — no findings, blocker/unresolved major 없음. 이 기록을 포함한 evidence-only final SHA 확인 예정 |

비범위 전체 `tests/contracts` 탐색 실행에서는 기준 `origin/main`과 동일한 3건(현재 8 KiB를 넘는
root `AGENTS.md`, 과거 backlog 문구를 기대하는 cold-start test, 다른 worktree 절대경로를 가진
#184 crop manifest)이 실패하고 나머지 325건이 통과했다. 실패 파일과 자료는 이 branch에서
변경하지 않았으며, #204가 추가한 machine contract는 전체 contract lint와 위 91-test 영향 범위에서
통과했다. 저장소 pre-publish의 실제 deterministic 경로는 별도로 최종 실행한다.

## Scope handoff

- #205: 공통 dimension/unit service와 Unit Profile. #204는 `x-unit` 문자를 기존 Attribute field로
  손실 없이 전달할 수 있는지만 계획하고 conversion/profile을 결정하지 않는다.
- #207: approved plan의 atomic apply, publication/rollback/export, bundle ownership과 exact
  source-to-created-revision provenance.
- #208: Administration upload/plan/apply UI와 browser/viewport acceptance.
- #184/#223 carryover, 나머지 issue 순서와 #195/#196은 변경하지 않는다.
