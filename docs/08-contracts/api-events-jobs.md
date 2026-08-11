# API, 이벤트, 비동기 작업 계약

## 1. 계약 원칙

- REST API는 command/query와 resource lifecycle을 표현한다.
- 계산·solver 실행은 Job resource로 표현하고 HTTP request에서 직접 수행하지 않는다.
- domain event는 이미 commit된 사실의 알림이며 source of truth가 아니다.
- 대형 data는 API JSON에 넣지 않고 immutable artifact reference를 사용한다.
- 모든 contract는 organization/project authorization을 적용한다.
- 모든 ID는 opaque UUID다. 이름·revision number·object key를 identity로 쓰지 않는다.

## 2. API 기본 규약

| 항목 | 규약 |
| --- | --- |
| Base path | `/api/v1` |
| Content type | `application/json`; problem은 `application/problem+json` |
| Time | UTC RFC 3339 |
| Numeric | locale-neutral JSON number; NaN/Infinity 금지 |
| Pagination | opaque cursor, stable sort key |
| Concurrency | ETag + `If-Match` 또는 `expected_revision_id` |
| Idempotency | create/command에 `Idempotency-Key` |
| Trace | W3C `traceparent`, response request ID |
| Long operation | `202 Accepted`, `Location: /api/v1/jobs/{id}` |
| Deletion | domain delete 대신 archive/withdraw/tombstone command |

### 2.1 인증과 request security context

- `GET /api/v1/health`는 공개 endpoint다.
- 보호 endpoint는 RFC 6750 bearer access token을 사용한다. ID token은 API credential로 받지
  않는다.
- API는 운영자가 설정한 issuer, audience, JWKS URL, 비대칭 서명 알고리즘 allowlist를 정확히
  검증한다. Token header나 claim에서 discovery/JWKS URL을 선택하지 않는다.
- 검증된 token의 `(issuer, subject)`는 stable principal로 resolve한다. user와 service principal을
  구분하고 client-credentials service token은 `subject == client_id`여야 한다.
- `organization_id`와 `project_id`는 선택된 request context로 반드시 존재해야 한다. 이 값이
  membership/role 권한을 증명하는 것은 아니며 T-04가 별도로 검증한다.
- `GET /api/v1/me`는 principal UUID/type/display name, 선택된 organization/project, group/scope,
  request/trace ID를 반환한다.
- 인증 오류는 token, claim, key, stack trace를 노출하지 않는 `application/problem+json`으로
  반환하고 모든 응답에 correlation용 `X-Request-ID`를 둔다.

### 2.2 T-04 authorization contract

- 인증된 context는 권한이 아니다. 보호 endpoint는 하나의 명시적 `Permission`으로 service-layer
  authorization을 먼저 수행한다.
- 허용 decision은 해당 action에 필요한 DB permission과 그 action을 부여한 binding들의
  classification clearance만 포함한다. 다른 role binding의 clearance를 합성하지 않는다.
- 같은 decision을 PostgreSQL transaction-local context로 bind한 뒤 repository query/command를
  실행한다. 다른 organization/project/request decision으로 재bind할 수 없다.
- 권한이 없으면 403, role-binding store 또는 RLS context를 사용할 수 없으면 503으로 fail
  closed한다. Token, role-binding row, 다른 tenant resource의 존재는 problem detail에 넣지 않는다.
- `/me`는 identity와 선택 context만 반환한다. Role/permission 관리 API는 아직 public contract가
  아니며 추가할 때 별도 versioned schema를 만든다.

## 3. 주요 REST resource

### 3.1 Catalog·testing

| Method/path | 목적 |
| --- | --- |
| `POST /materials` | Material identity와 첫 revision 생성 |
| `GET /materials/{id}` | head 및 요약 조회 |
| `GET /materials/{id}/revisions` | revision 목록 |
| `POST /materials/{id}/revisions` | 새 immutable revision 생성 |
| `POST /material-states` | state identity/revision 생성 |
| `POST /lots`, `POST /batches` | lot/batch 생성 |
| `POST /process-runs` | 실제 공정 실행 기록 |
| `POST /specimens` | specimen 등록 |
| `POST /test-methods` | plugin schema를 참조하는 method 생성 |
| `POST /test-campaigns` | campaign 생성 |
| `POST /test-runs` | specimen test run 생성 |
| `POST /test-runs/{id}/corrections` | 원본 event를 보존한 correction revision |
| `POST /catalog/schema-definition-bundles:plan` | exact immutable Artifact의 bundle-local schema를 검증하고 현재 Catalog 대비 no-write plan 반환 |

#### 3.1.1 Catalog Schema Definition Bundle v1

요청은 `artifact_id`와 lowercase `artifact_sha256`을 함께 고정한다. 서버는 RLS 범위에서 그 exact
Artifact를 읽고 원본 media type, byte count와 digest를 다시 검증한다. 허용 media type은
`application/json`, `application/schema+json`,
`application/vnd.cmp.catalog-schema-definition-bundle+json`이며 parameter를 제거해 판정하되 응답에는
저장된 원문을 그대로 반환한다.
응답의 `source_artifact`와 bundle summary는 organization/project/classification을 포함한다. Bundle
scope가 immutable Artifact scope 또는 인증 문맥과 다르면 `CMP-SCHEMA-BUNDLE-0004`다.

Bundle과 plan의 독립 계약 버전은 모두 `1.0.0`이다. Bundle은 하나 이상의 임의 개수
`record_schemas`를 허용하고 각 record의 stable key, canonical schema SHA-256과 draft 2020-12 `$id`를
고정한다. 지원 확장은 `x-business-key`, `x-reference`, `x-curve`, `x-unit`, `x-indexed`,
`x-searchable`뿐이다. `$ref`는 같은 record의 fragment 또는 bundle에 선언된 exact record `$id`와
fragment만 허용한다. Stable key는 기존 configurable Catalog runtime과 같은 1..64자
lower_snake_case이며 `_`로 끝날 수 없다. leaf description은 Attribute help/Link Type의 기존
2,000자 한도를 넘으면 손실 없는 projection 오류다. 외부 URL·파일·네트워크 resolver와 임의
실행은 없다.

성공한 transport는 semantic validation 오류도 HTTP 200으로 반환한다. `valid`, ordered
`create | update | no-op | conflict | error` actions, 위치·조치가 있는 diagnostics, source Artifact
identity, Catalog snapshot fingerprint와 plan fingerprint를 함께 제공한다. 같은 exact Artifact와 같은
Catalog snapshot의 반복 응답은 byte/semantic-equivalent다. 입력에서 사라진 기존 객체는 action이나
delete 대상이 아니며 `mutations_applied=false`, `delete_missing=false`, `write_set=[]`가 고정된다.
내용이 같더라도 기존 Catalog 객체가 의존 객체의 현재 revision이 아닌 과거 revision을 pin하면
`dependency_revision_changes` 사유의 `update`이며, append-only placement 이력은 논리
Profile/Table key별 하나의 현재 상태로 비교한다.
같은 stable key의 기존 identity가 다른 immutable classification을 가지면
`classification_conflict`이며 자동 인수하지 않는다.
요청 형식은 422, 인증/권한은 401/403, 숨겨진 Artifact는 404, exact digest·media·integrity·scope
충돌은 409, 필수 backend 미구성은 503이다.

| Diagnostic code | 의미 |
| --- | --- |
| `CMP-SCHEMA-BUNDLE-0001` | UTF-8 또는 strict JSON 오류 |
| `CMP-SCHEMA-BUNDLE-0002` | v1 구조, stable key 또는 keyword 값 오류 |
| `CMP-SCHEMA-BUNDLE-0003` | bundle contract 또는 JSON Schema draft version 미지원 |
| `CMP-SCHEMA-BUNDLE-0004` | tenant/project/classification scope 불일치 |
| `CMP-SCHEMA-BUNDLE-0005` | canonical record schema checksum 불일치 |
| `CMP-SCHEMA-BUNDLE-0006` | JSON member, record key/ID, flattened key 또는 Link key 중복 |
| `CMP-SCHEMA-BUNDLE-0007` | 외부 URL·파일·네트워크 `$ref` 차단 |
| `CMP-SCHEMA-BUNDLE-0008` | bundle 내부 record `$id` 누락 |
| `CMP-SCHEMA-BUNDLE-0009` | JSON Pointer가 schema object로 resolve되지 않음 |
| `CMP-SCHEMA-BUNDLE-0010` | 지원하지 않는 JSON Schema/`x-*` keyword |
| `CMP-SCHEMA-BUNDLE-0011` | record dependency 또는 재귀 reference cycle |
| `CMP-SCHEMA-BUNDLE-0012` | 기존 typed Catalog로 손실 없이 projection 불가 |
| `CMP-SCHEMA-BUNDLE-0013` | 기존 stable identity/immutable type/endpoint/소유권 충돌 |

### 3.2 Upload·artifact·dataset

| Method/path | 목적 |
| --- | --- |
| `POST /uploads` | upload session 생성 |
| `POST /uploads/{id}/parts` | multipart/chunk 정보 등록 또는 발급 |
| `POST /uploads/{id}:complete` | size/digest 검증과 Raw Asset 생성 |
| `GET /artifacts/{id}` | metadata와 integrity 상태 조회 |
| `POST /artifacts/{id}:download-token` | 권한 검사 후 short-lived access 발급 |
| `POST /imports:detect` | Importer detect job 제출 |
| `POST /import-mappings` | 승인 mapping revision 생성 |
| `POST /imports` | normalization/import job 제출 |
| `GET /datasets/{id}/revisions/{rev}` | dataset manifest 조회 |
| `POST /selections` | immutable selection revision 생성 |
| `POST /datasets/{id}/views` | UI용 downsampled view job 제출 |

### 3.3 Analysis·model·export·validation

| Method/path | 목적 |
| --- | --- |
| `POST /processing-recipes` | recipe revision 생성 |
| `POST /processing-runs` | processing job 제출 |
| `POST /statistical-plans` | grouping/method/QC plan 생성 |
| `POST /statistical-runs` | statistics job 제출 |
| `POST /outlier-assessments` | candidate 판정 추가 |
| `POST /calibration-plans` | model/calibrator/input/config 고정 |
| `POST /calibration-runs` | calibration job 제출 |
| `POST /material-models/{id}/revisions` | approved result로 IR revision 생성 |
| `POST /exports:preflight` | mapping report job 제출 |
| `POST /solver-cards` | approved report 기반 export job 제출 |
| `POST /export-selections` | exact Dataset/IR/Card/Artifact revision과 representation 고정 |
| `POST /export-jobs` | immutable Bulk Export Bundle assembly job 제출 |
| `GET /export-bundles/{id}` | manifest, archive Artifact와 integrity 상태 조회 |
| `POST /validation-plans` | template/card/runner/metric 고정 |
| `POST /validation-runs` | managed 또는 external validation 실행 |
| `POST /validation-runs/{id}:attach-external-result` | 수동 실행 Result Manifest 반입 |

Bulk Export Job 응답은 외부 worker 작업에 대해 nullable `heartbeat_at`과 `lease_expires_at`을
제공한다. `lease_token`은 worker fencing credential이므로 API와 event payload에 노출하지 않는다.
만료된 active Job의 재선점은 같은 Job identity에서 `attempt_count`를 증가시키며 Selection, output
commit 또는 Bundle revision을 덮어쓰지 않는다.

### 3.4 Review·release·lineage·plugin

| Method/path | 목적 |
| --- | --- |
| `POST /review-requests` | candidate manifest 제출 |
| `POST /review-requests/{id}/decisions` | approve/reject/request-change |
| `POST /releases` | 승인된 candidate 발행 |
| `POST /releases/{id}:supersede` | 새 release로 대체 |
| `POST /releases/{id}:withdraw` | 사용 중지 event |
| `GET /lineage/entities/{id}/upstream` | upstream graph query |
| `GET /lineage/entities/{id}/downstream` | impact query |
| `GET /lineage/releases/{id}` | release provenance subgraph |
| `POST /plugins/packages` | package 등록·검증 job |
| `POST /plugins/packages/{id}:activate` | policy 승인 후 활성화 |
| `GET /jobs/{id}` | job 상태·attempt·result 조회 |
| `POST /jobs/{id}:cancel` | cooperative cancel 요청 |
| `POST /jobs/{id}:retry` | 새 attempt 생성; reason 필수 |

## 4. Revision create 예시

```http
POST /api/v1/materials/8e.../revisions
If-Match: "revision:3:sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
Idempotency-Key: 5b...
Content-Type: application/json
```

```json
{
  "based_on_revision_id": "uuid-rev-3",
  "change_reason": "supplier designation corrected",
  "content": {
    "display_name": "...",
    "classification": "...",
    "extensions": {}
  }
}
```

성공 시 `201 Created`, 새 resource URL, ETag를 반환한다. head가 달라졌다면 `409 Conflict` 또는 `412 Precondition Failed`와 current revision ref를 반환한다.

`T-06`은 아직 Material endpoint를 만들지 않고 위 endpoint들이 재사용할 strong ETag와
content-free `RevisionMetadata` component만 구현한다. Weak/wildcard/multiple ETag와 `latest`
alias는 허용하지 않는다. Concrete Material API와 typed content schema는 `T-07`에서 추가한다.

## 5. Job resource

### 5.1 상태

| 상태 | 의미 | terminal |
| --- | --- | --- |
| `planned` | input/config 검증 중 | 아니오 |
| `needs_input` | 사용자 mapping/승인 필요 | 아니오 |
| `queued` | 실행 대기 | 아니오 |
| `claimed` | runner lease 획득 | 아니오 |
| `running` | 실행 중 | 아니오 |
| `waiting_external` | HPC/외부 결과 대기 | 아니오 |
| `cancel_requested` | cancel 전달됨 | 아니오 |
| `succeeded` | 검증된 output commit | 예 |
| `failed` | 실행 또는 output validation 실패 | 예 |
| `cancelled` | 취소 확인 | 예 |
| `timed_out` | deadline/lease 정책 종료 | 예 |

### 5.2 Job response

```json
{
  "job_id": "uuid",
  "job_type": "calibration",
  "state": "running",
  "organization_id": "uuid",
  "project_id": "uuid",
  "submitted_at": "RFC3339",
  "submitted_by": "uuid",
  "plan_revision_id": "uuid",
  "current_attempt": 2,
  "progress": {
    "fraction": 0.42,
    "phase": "multi-start 3/8",
    "updated_at": "RFC3339"
  },
  "links": {
    "self": "/api/v1/jobs/uuid",
    "logs": "/api/v1/jobs/uuid/logs"
  }
}
```

`progress`는 best-effort이며 scientific result가 아니다. terminal state에서 `result_manifest_id` 또는 problem detail을 제공한다.

### 5.3 Claim/lease

- worker는 조건에 맞는 job을 DB에서 atomic claim한다.
- `lease_owner`, `lease_expires_at`, `heartbeat_at`를 기록한다.
- heartbeat 상실 시 같은 attempt를 재개한다고 가정하지 않고 새 attempt를 만든다.
- 이미 commit된 output digest가 있으면 idempotent finalize를 수행한다.
- retry policy는 error category별로 다르며 domain-invalid input은 자동 retry하지 않는다.

## 6. Error contract

```json
{
  "type": "urn:cmp:problem:unit-mapping-unresolved",
  "title": "Unit mapping requires confirmation",
  "status": 422,
  "detail": "Two source columns have ambiguous unit text.",
  "instance": "/api/v1/imports/uuid",
  "code": "CMP-ING-0042",
  "trace_id": "hex",
  "errors": [
    {"path": "/columns/3/unit", "reason": "ambiguous", "candidates": ["MPa", "mPa"]}
  ]
}
```

Plugin의 raw exception/stack trace는 사용자 response에 노출하지 않는다. structured diagnostic code와 sanitized detail을 반환하고 상세 log는 권한 있는 operator에게만 제공한다.

## 7. Domain event envelope

CloudEvents 1.0 JSON 형식을 사용한다. CloudEvents는 transport가 아니라 공통 event metadata 형식이다. [CloudEvents specification](https://github.com/cloudevents/spec)

```json
{
  "specversion": "1.0",
  "id": "uuid",
  "source": "/cmp/organizations/org-id/projects/project-id",
  "type": "com.cmp.material-model.revision.created.v1",
  "subject": "material-models/model-id/revisions/revision-id",
  "time": "RFC3339",
  "datacontenttype": "application/json",
  "dataschema": "urn:cmp:event-schema:material-model-revision-created:v1",
  "traceparent": "...",
  "data": {
    "organization_id": "uuid",
    "project_id": "uuid",
    "aggregate_id": "uuid",
    "revision_id": "uuid",
    "revision_no": 2,
    "content_hash": "hex"
  }
}
```

### 7.1 핵심 event catalog

| Event type | 발생 시점 |
| --- | --- |
| `raw-asset.ingested.v1` | final object와 metadata commit |
| `dataset.revision.created.v1` | dataset artifact/schema/provenance commit |
| `qc.run.completed.v1` | QC observations commit |
| `statistics.run.completed.v1` | statistical results commit |
| `processing.run.completed.v1` | processed dataset commit |
| `calibration.run.completed.v1` | result/diagnostics commit |
| `material-model.revision.created.v1` | IR revision commit |
| `solver-card.generated.v1` | card + mapping report commit |
| `validation.run.completed.v1` | result + verdict commit |
| `review.decision.recorded.v1` | append-only decision commit |
| `release.published.v1` | immutable release manifest commit |
| `release.superseded.v1` | lifecycle transition commit |
| `plugin.package.activated.v1` | activation policy commit |

`completed`는 성공만 뜻하지 않는다. payload에 terminal outcome을 넣거나 성공/실패 event를 분리하는 정책 중 하나를 event별 schema에서 고정한다. MVP 권고는 `job.completed`에는 outcome을 포함하고, domain artifact event는 성공 commit에만 발행하는 방식이다.

## 8. Delivery semantics

- DB write와 outbox insert를 하나의 transaction으로 수행한다.
- publisher가 outbox를 broker/webhook에 at-least-once 전달한다.
- event ID는 전역 unique하고 consumer는 inbox/dedup을 사용한다.
- aggregate별 `sequence_no`를 payload metadata에 두어 순서 역전을 감지한다.
- 전역 순서를 보장하지 않는다.
- consumer failure가 원 transaction을 rollback하지 않는다.
- event payload에 대형 curve/card content를 넣지 않고 authorized API reference와 digest만 넣는다.
- data classification에 따라 외부 subscription을 제한한다.

## 9. AsyncAPI 문서

event channel, operation, payload schema, delivery/security policy는 AsyncAPI로 관리한다. AsyncAPI는 message-driven API를 machine-readable하게 기술한다. [AsyncAPI specification](https://www.asyncapi.com/docs/reference/specification/latest)

Repository 기준 파일:

```text
contracts/events/asyncapi.yaml
contracts/events/schemas/*.json
contracts/http/openapi.yaml
contracts/jobs/job-spec.schema.json
contracts/jobs/result-manifest.schema.json
```

## 10. External solver callback/polling

`SolverRunnerAdapter`는 공통 operation을 구현한다.

```text
submit(plan, staged_inputs) -> external_job_ref
poll(external_job_ref) -> status/progress
cancel(external_job_ref) -> cancellation_result
collect(external_job_ref) -> ResultManifest
```

- callback을 지원하는 scheduler는 signed callback token과 replay protection을 사용한다.
- callback이 없어도 poll로 동작해야 한다.
- platform job ID와 external scheduler ID를 함께 기록한다.
- license queue, scheduler queue, solver execution 시간을 분리해 metric을 기록한다.
- 외부 결과 수동 반입도 동일 Result Manifest schema와 digest verification을 통과한다.

## 11. API·event versioning

- REST breaking change는 `/api/v2` 또는 negotiated media type으로 분리한다.
- additive field는 optional로 추가하고 client가 unknown field를 허용하도록 한다.
- event type에 major schema version suffix를 둔다.
- enum 추가가 consumer에 breaking인지 contract test로 관리한다.
- deprecated field는 telemetry로 사용량을 확인한 뒤 제거한다.
- plugin/job/IR schema는 REST version과 독립적으로 versioning한다.

## 12. Contract test 필수 항목

- OpenAPI/JSON Schema validation
- idempotency replay와 key/body conflict
- ETag stale update
- organization/project authorization과 search count leak
- job lease loss/retry/cancel
- duplicate/out-of-order event
- missing/corrupt artifact
- plugin output schema mismatch
- external runner callback replay
- release event에 draft artifact가 포함되지 않음

