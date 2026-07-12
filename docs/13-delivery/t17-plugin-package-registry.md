# T-17 Plugin manifest/package/schema registry 구현 기록

## 1. 추적성

- Task: `T-17`
- Requirements: `FR-PLG-001`, `FR-PLG-002`, `FR-PLG-003`, `FR-PLG-005`,
  `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-005`, `NFR-SEC-006`, `NFR-MOD-002`,
  `NFR-COMP-001`, `NFR-COMP-002`, `NFR-DOC-001`
- ADR: `ADR-001`, `ADR-002`, `ADR-003`, `ADR-004`
- 선행 구현: T-02 Manifest 1.0/JSON Schema 계약, T-03 request security context,
  T-04 authorization/RLS, T-06 immutability trigger, T-15 generic Job 경계

T-17은 plugin package의 identity, contract, supply-chain artifact reference, 검증 상태와
project 활성화 사실만 관리한다. plugin implementation을 API process에 import하거나 실행하지 않으며,
Material, 시험 importer, fitting, solver exporter 기능을 구현하지 않는다.

## 2. 결정과 권장 가정

구현 전에 다음 아키텍처 질문을 확인했고, T-17을 중단하지 않는 보수적 가정을 적용했다.

1. **T-10 이전 artifact 연결**: package, signature, SBOM은 non-zero artifact UUID, SHA-256,
   size, media type으로 고정한다. T-10의 authoritative artifact table이 아직 없으므로 FK와 실제 byte
   검증을 만들지 않는다. T-10에서 소유 table과 transfer/commit 검증을 추가한다.
2. **활성화 scope**: 현재 authorization context와 RLS가 organization/project를 항상 선택하므로
   Definition, Package, Activation을 project-scoped로 둔다. 다른 project의 package ID를 알아도 조회나
   활성화할 수 없다. 향후 organization-wide package 공유가 필요하면 별도 ADR과 read model이 필요하다.
3. **책임 분리**: `Plugin Maintainer`는 `plugin.submit`으로 등록만 한다. `Org Admin`의
   `plugin.activate`가 검증, 활성화, 폐기를 수행한다. Maintainer의 self-activation은 허용하지 않는다.
4. **검증 의미**: 등록 직후 상태는 `contract_validated`다. JSON Schema 검증만으로 signature,
   SBOM, malware scan, TCK 통과를 가장하지 않는다. 운영자가 외부 evidence 확인 후 `:verify`를 호출해야
   `eligible`이 되고, 그 뒤에만 `:activate`가 가능하다.
5. **계약 버전**: public Manifest 1.0과 runner contract `1.0` 지원 범위를 사용한다. package마다
   별도 JSON Schema 2020-12 문서를 등록하고 각 extension에 하나 이상의 schema와 capability를 요구한다.

## 3. 모듈 경계

| 계층 | 책임 |
| --- | --- |
| Domain | Manifest canonicalization, ID/version/digest, extension/capability, artifact reference, state transition |
| Application | authorization decision 일치, schema coverage, submission digest, register/read/verify/activate/revoke use case |
| Contract adapter | packaged Manifest 1.0과 등록 schema의 JSON Schema 2020-12 검증 |
| Persistence adapter | 단일 PostgreSQL transaction, natural identity 충돌, append-only event, projection serialization, RLS binding |
| API adapter | versioned request/response/problem, idempotency header, sanitized tenant-scoped 404 |

Core는 manifest의 extension type, entrypoint, capability 문자열을 저장할 뿐 entrypoint를 import하거나
호출하지 않는다. API/worker composition root에도 production plugin implementation dependency가 없다.

## 4. PostgreSQL migration

Migration head는 `20260711_005_t17`이며 module-owned schema는 `plugin`이다.

### `plugin.definition`

- organization/project/classification, stable opaque UUID, stable `plugin_id`
- `(organization_id, project_id, plugin_id)` unique
- 생성 actor/time immutable

같은 project의 같은 `plugin_id`는 version이 추가되어도 Definition UUID를 재사용한다.

### `plugin.package`

- Definition FK와 immutable Package UUID
- exact semantic version, package/manifest digest, canonical Manifest JSONB
- contract API range, network deny, CPU/memory/GPU/timeout projection
- package/signature/SBOM artifact UUID/digest/size/media type
- idempotency key, canonical submission digest, actor/request/trace/time
- Definition+version, package digest, idempotency key의 project-scoped unique constraint

JSONB는 versioned Manifest 문서 하나에만 쓰며 identity, version, digest, resources, artifact reference,
state, tenant를 generic key/value로 저장하지 않는다. package insert trigger가 Manifest `plugin_id`와 stable
Definition을 대조한다. 동일 ID/version에 다른 digest를 넣으면 unique natural identity와 repository
conflict 처리로 거부한다.

### `plugin.extension`, `plugin.capability`, `plugin.schema`, `plugin.artifact_role`

- extension ordinal/type/entrypoint를 명시적 relation으로 저장
- capability를 extension별 typed row로 저장하고 빈 capability를 거부
- schema UUID, role, stable `$id`, JSON Schema document, document digest를 저장
- read/write artifact role을 방향이 있는 명시적 row로 저장
- 모든 child FK는 organization/project/classification/package identity를 함께 전달

Manifest와 schema document 외 JSONB 또는 EAV table은 없다. 활성화 trigger는 Manifest의 extension,
capability, artifact role과 normalized row를 다시 대조하며 모든 extension의 schema coverage를 확인한다.

### 상태와 활성화

- `plugin.package_state_event`: sequence가 있는 append-only 상태/actor/reason/request/trace event
- `plugin.package_state_projection`: 현재 state와 마지막 event를 가리키는 serialized projection
- `plugin.activation`: eligible package에 대한 project-scoped immutable activation fact

상태 전이는 다음과 같다.

```text
contract_validated -> eligible -> unavailable -> revoked
                  \-> rejected
                  \-> revoked
eligible -----------------------> revoked
```

Event insert trigger는 현재 projection을 잠그고 from/to state와 sequence를 검증한다. Projection trigger는
새 값이 정확히 해당 event를 가리키는지 확인한다. Activation trigger는 projection을 잠근 뒤 `eligible`,
Manifest/Definition 일치, extension/capability/schema/artifact-role 완전성을 모두 재검증한다. Definition,
Package, normalized contract row, event, activation은 UPDATE/DELETE 불가다. Deferred constraint trigger는
Package와 initial projection, event와 matching projection이 같은 transaction에서 함께 commit되도록 하며,
initial projection이 생긴 뒤에는 normalized contract child row 추가도 seal trigger가 차단한다.

### RLS

모든 table에 `ENABLE ROW LEVEL SECURITY`와 `FORCE ROW LEVEL SECURITY`를 적용한다.

- read: `plugin.read`
- Definition/Package/contract insert: `plugin.submit`, 생성 actor 일치
- initial event/projection: `plugin.submit`
- verification/revocation event와 projection update: `plugin.activate`
- activation insert: `plugin.activate`, 활성화 actor 일치

모든 policy는 `access_control.can_access_row(organization_id, project_id, classification, ...)`를
사용한다. application transaction은 T-04 AuthorizationDecision을 transaction-local RLS context로 bind한다.

## 5. API 계약

- `POST /api/v1/plugins/packages`: `Idempotency-Key` 필수, Manifest/artifact/schema bundle 등록,
  `201 Created`, `Location`, `Idempotent-Replay`
- `GET /api/v1/plugins/packages/{package_id}`: immutable Manifest, normalized contract, artifact references,
  submission provenance, state history, activation 조회
- `POST /api/v1/plugins/packages/{package_id}:verify`: 외부 supply-chain/policy evidence 확인을
  append-only `eligible` event로 기록
- `POST /api/v1/plugins/packages/{package_id}:activate`: eligible package의 project allowlist fact append
- `POST /api/v1/plugins/packages/{package_id}:revoke`: package/history를 삭제하지 않고 terminal revoke append

Public OpenAPI 0.6.0과 registration/resource/problem JSON Schema를 추가했다. Runtime Manifest validator가
사용하는 packaged schema는 public `plugin-manifest.schema.json`과 byte-equivalent JSON 내용이다.

## 6. 검증 범위

- Unit: Manifest/schema/version range, canonical immutability, digest substitution, schema coverage,
  state transition, authorization decision binding
- API: 201/Location/idempotency, stable Definition와 Package 분리, state provenance, validation problem,
  Maintainer/Admin permission 분리, sanitized 404
- Migration: explicit table/constraint/index/trigger/RLS 렌더링, Manifest/schema 외 JSONB 및 EAV 부재
- PostgreSQL: register replay, stable Definition reuse, ID/version digest substitution rejection,
  verify/activate history, immutable package/event, revoke, cross-project RLS, schema/capability 누락 활성화 차단,
  clean downgrade
- Regression: T-03/T-04/T-06/T-15 API, worker, migration, PostgreSQL suite

## 7. 미결정 및 후속 경계

- T-10: artifact table FK, byte digest/size 검증, object commit 및 availability/reconciliation
- T-18(완료): isolated subprocess/OCI-ready runner, SDK, TCK, active package execution lookup.
  Signature/SBOM·malware/vulnerability 자동 검증은 별도 supply-chain policy adapter로 남는다.
- T-05/T-13: tamper-evident audit chain과 표준 provenance Entity/Activity/Agent relation
- organization-wide package 공유/activation inheritance가 필요한지 여부
- signature format/trust root, SBOM profile, vulnerability/license policy, TCK evidence schema
- runner contract minor-version 지원 window와 additive compatibility automation

현재 schema는 이 결정을 추측해 허위 verification 사실을 만들지 않는다. 후속 task가 evidence와 artifact
소유권을 확정하면 immutable Package/Event identity를 유지한 채 별도 typed relation과 adapter로 확장한다.
