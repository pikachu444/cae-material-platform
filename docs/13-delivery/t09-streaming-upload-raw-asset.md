# T-09 Streaming multipart upload와 Raw Asset 구현 기록

## 1. 추적성

- Task: `T-09`
- Requirements: `FR-ING-001`, `FR-ING-002`, `FR-ING-003`, `FR-ING-004`,
  `NFR-INT-001`, `NFR-PERF-004`, `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-004`,
  `NFR-SEC-006`, `NFR-MOD-001`
- ADR: `ADR-002`, `ADR-003`
- 선행 구현: T-03 principal, T-04 authorization/RLS, T-06 immutable-row와 tenant primitive

T-09은 대용량 원본 byte를 재개 가능한 multipart stream으로 받고, 기대 SHA-256과 크기를
검증한 뒤 immutable Raw Asset과 append-only Ingestion Event를 기록하는 범위다. Parser,
normalization, Material, 시험 유형, fitting, solver exporter는 구현하지 않는다.

## 2. 아키텍처 질문과 권장 가정

구현을 중단할 질문은 없었고 다음 보수적 가정을 적용했다.

1. **T-09/T-10 원자성 경계**: T-09 성공은 random staging key의 byte가 manifest와 일치하고
   Raw Asset이 `staged_verified`로 기록됐다는 뜻이다. Content-addressed final key, `available`
   Artifact, download token, outbox와 integrity reconciler는 T-10에서 구현한다.
2. **Object-store adapter**: application은 multipart port만 소유한다. 개발·통합 검증에는 실제
   stream/file semantics를 가진 filesystem adapter를 사용하되 production에서는 이를 구성하지
   않는다. S3-compatible TLS, 저장 암호화, object lock 구현은 배포 adapter 선택 사항이다.
3. **Test Run 참조**: T-08 table이 아직 없으므로 `test_run_revision_id`는 optional non-zero UUID로
   보존하되 존재하지 않는 table을 향한 FK를 만들지 않는다. T-08이 organization/project가 포함된
   composite FK를 추가한다.
4. **Upload capability**: bearer authorization과 별도로 session, organization, project, 생성 actor,
   만료에 묶인 HMAC capability를 요구한다. capability 원문은 DB에 저장하거나 log에 기록하지 않는다.
5. **크기 acceptance**: 기본 최대값은 2 GiB이고 배포 설정으로 조정한다. CI에서는 같은 streaming
   경로로 환경 최대 2 MiB fixture를 32개 part로 검증해 메모리/시간을 유한하게 유지한다.
6. **Dedup 범위**: content identity는 같은 organization/project/classification 안의 SHA-256과
   size로 결정한다. 중복 byte는 Raw Asset을 재사용하지만 새 ingestion 의미는 별도 event로 남긴다.

## 3. 모듈 경계와 불변조건

| 계층 | 책임 |
| --- | --- |
| Domain | upload state, immutable part/Raw Asset/Ingestion Event, digest·size·identity invariant |
| Application | authorization decision 확인, capability, idempotency, multipart orchestration, dedup commit |
| Persistence | PostgreSQL explicit typed table, transaction, lock, RLS-bound query와 guarded transition |
| Storage | domain-neutral multipart initiate/upload/complete/abort/discard port와 개발 filesystem adapter |
| API | upload session/part/complete/cancel/Raw Asset resource, sanitized problem response |

`upload_session`은 stable orchestration identity와 immutable request manifest를 가진다. 진행 상태만
`open → completing → completed|failed|cancelled`로 제한적으로 바뀐다. `upload_part`, `raw_asset`,
`ingestion_event`는 생성 후 UPDATE/DELETE할 수 없다. 실패나 correction은 원본을 덮어쓰지 않고 새
upload와 새 ingestion fact로 표현한다.

Part는 순서와 무관하게 전송할 수 있지만 part number, 기대 크기, 관측 SHA-256, storage ETag는 한 번
기록되면 바꿀 수 없다. Completion은 모든 번호가 연속적으로 존재하고 전체 byte의 SHA-256/size가
요청 manifest와 정확히 일치할 때만 Raw Asset을 만든다. Object-store 성공 후 DB 응답이 유실되어도
동일 complete 요청은 같은 object와 committed event를 반환한다.

## 4. PostgreSQL migration

Migration `20260712_006_t09`는 `artifact` schema에 다음 table을 만든다.

| Table | 역할 | 핵심 제약 |
| --- | --- | --- |
| `upload_session` | upload identity와 state projection | tenant idempotency, staging/upload key uniqueness, manifest checks, state trigger |
| `upload_part` | immutable numbered part manifest | tenant/classification composite FK, exact size insert guard, immutable trigger |
| `raw_asset` | 검증된 원본 content identity | tenant/classification/digest/size uniqueness, completing upload insert guard, immutable trigger |
| `ingestion_event` | 수집 actor/request/source context | upload당 1 event, Raw Asset/upload composite FK, consistency guard, immutable trigger |

모든 PK와 bounded reference는 `organization_id`, `project_id`를 선두에 둔다. Raw Asset dedup은
classification까지 포함해 더 높은 등급 byte가 낮은 등급 resource로 합쳐지지 않게 한다. 상태/만료,
digest, Raw Asset ingestion, optional Test Run 조회용 index를 명시했다.

네 table 모두 `ENABLE/FORCE ROW LEVEL SECURITY`를 사용한다. 읽기와 쓰기는 각각
`artifact.read`, `artifact.write`와 T-04 classification clearance를 확인하고, write actor는 transaction의
principal과 같아야 한다. Runtime role은 table owner, superuser, `BYPASSRLS`일 수 없다.

Core 속성을 JSON/EAV로 저장하지 않으며 generic Artifact table도 만들지 않는다. Trigger 내부의 row
비교 표현은 schema column mutation을 검사하기 위한 PostgreSQL 연산일 뿐 persisted JSON content가 아니다.

## 5. API 계약

- `POST /api/v1/uploads`: immutable manifest와 `Idempotency-Key`로 session/capability 생성
- `GET /api/v1/uploads/{upload_id}`: tenant-visible session과 수신 part manifest 조회
- `PUT /api/v1/uploads/{upload_id}/parts/{part_number}`: request body를 전체 buffering하지 않고 전송
- `POST /api/v1/uploads/{upload_id}:complete`: 전체 digest/size 검증과 Raw Asset/Ingestion Event commit
- `POST /api/v1/uploads/{upload_id}:cancel`: terminal cancellation과 staging cleanup 시도
- `GET /api/v1/raw-assets/{raw_asset_id}`: immutable Raw Asset metadata 조회

Part, complete, cancel은 `Upload-Capability` header를 추가로 요구한다. 모든 route는 bearer security와
service authorization을 먼저 적용한다. 알려지지 않았거나 다른 project에 속한 UUID는 같은 404로 숨기고,
capability scope/expiry, invalid manifest, state conflict, object-store failure는 bounded problem contract로
분리한다. Public response와 OpenAPI/JSON Schema에는 staging object key나 multipart upload ID가 없다.

## 6. Storage와 비원자성 처리

Filesystem adapter는 non-production reference implementation이다. 각 part를 fresh temporary file에
streaming하며 기대 크기를 넘는 순간 중단하고, fsync 후 hard-link no-overwrite로 번호를 고정한다.
Completion은 모든 part file을 재해시하고 하나의 fresh object로 이어 붙인 뒤 다시 no-overwrite commit한다.
절대경로, `..`, backslash, NUL, root escape, symlink, 다른 byte로 같은 part/key를 덮어쓰는 요청을 거부한다.

Object-store complete와 PostgreSQL은 하나의 transaction이 아니다. Store completion이 먼저 성공한 뒤
DB commit을 시도하며, retry 시 이미 완성된 staging object를 재검증해 이어간다. Digest mismatch는 session을
`failed`로 terminal 처리하고 staging object를 제거한다. 중복 content가 이미 있으면 새 staging copy를
제거하고 기존 Raw Asset에 새 Ingestion Event를 연결한다. Pending/final object reconciliation은 T-10/T-16
경계다.

## 7. 검증 범위

- Unit: size/part/count/TTL policy, capability signature·actor·tenant·expiry, stream/no-overwrite/path injection
- API integration: bearer/permission, safe filename, raw request streaming, complete/Raw Asset response,
  internal storage identifier 비노출
- PostgreSQL integration: 실제 migration과 non-owner forced RLS, out-of-order/resume/part replay,
  complete replay, immutable DB row, digest mismatch, cancel, cross-project UUID, tampered capability
- Dedup regression: 같은 content에 Raw Asset 1개와 Ingestion Event 2개, duplicate staging 제거
- Capacity fixture: 설정된 2 MiB 최대 object를 64 KiB part 32개와 더 작은 stream chunk로 전송
- Migration/architecture/contract: upgrade/downgrade, trigger/policy/constraint rendering, no EAV/JSONB/business
  schema, OpenAPI operation/security와 storage-key 비노출

## 8. 미결정 및 후속 경계

- T-10 content-addressed final Artifact, available state, scoped download token, copy/commit과 integrity reconciler
- Production S3-compatible adapter, TLS/KMS/object-lock/versioning/retention과 deployment credential rotation
- T-08 Test Run Revision table 생성 후 tenant-qualified FK
- T-05 audit trail과 T-13 typed provenance relation, T-16 outbox/reconciliation
- 실제 production infrastructure에서 2 GiB 이상 load/soak/fault-injection acceptance

이 항목은 T-09 성공으로 가장하지 않으며 현재 API에 mutable placeholder나 vendor-specific 계약을 넣지 않았다.
