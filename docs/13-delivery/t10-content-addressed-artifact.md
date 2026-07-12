# T-10 Content-addressed Artifact와 integrity reconciler 구현 기록

## 1. 추적성

- Task: `T-10`
- Requirements: `FR-ING-002`, `FR-DAT-008`, `NFR-INT-001`, `NFR-INT-002`,
  `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-004`, `NFR-SEC-006`, `NFR-MOD-001`
- ADR: `ADR-002`, `ADR-003`
- 선행 구현: T-03 principal, T-04 authorization/RLS, T-06 immutable primitive,
  T-09 verified staging Raw Asset, T-15 durable Job kernel

T-10은 검증된 staging byte를 deterministic content key로 승격하고, immutable Artifact manifest와
append-only integrity fact를 기록하며, DB/object-store 불일치를 탐지·복구하는 범위다. Material,
시험 importer, dataset normalization, fitting, solver exporter와 장기 archive vendor는 구현하지 않는다.

## 2. 아키텍처 질문과 권장 가정

1. **Content key 격리**: 전역 digest key는 교차 tenant dedup, retention, encryption 경계를 섞을 수 있다.
   `organization/project/classification/sha256`를 key scope로 포함해 같은 scope 안에서만 물리 byte를
   공유한다.
2. **Raw Asset 불변성**: T-09 `raw_asset`의 staging key/state를 final key로 바꾸지 않는다. 별도 immutable
   Artifact가 `source_raw_asset_id`로 원본 fact를 참조한다. 동일 Raw Asset의 재승격은 같은 Artifact를
   반환한다.
3. **Manifest와 integrity 분리**: Artifact의 digest, size, media/schema/role, content key는 생성 후
   변경하지 않는다. 이후 missing/corrupt 판정은 immutable observation과 제한된 current projection에
   기록한다.
4. **T-10/T-16 경계**: T-10은 동기 finalization/reconciliation use case와 issue persistence를 소유한다.
   주기적 durable scheduling, transactional outbox, delivery dedup, retention cleanup은 T-16에서 T-15와
   결합한다. Plugin 전용 Job Spec 1.0에 가짜 reconciliation extension을 넣지 않는다.
5. **Object-store adapter**: 개발·통합에는 실제 stream/copy/link/list/rehash를 수행하는 filesystem
   adapter를 쓴다. Production에서는 S3-compatible TLS, encryption, object lock/versioning adapter가
   주입되지 않으면 구성하지 않는다.
6. **Download access**: object key나 presigned vendor URL을 public contract에 넣지 않는다. Bearer
   authorization과 actor, tenant, artifact ID, digest, expiry에 묶인 canonical HMAC transfer token을
   함께 요구하는 streaming endpoint를 사용한다.

## 3. Domain/application 경계

| 계층 | 책임 |
| --- | --- |
| Domain | content key, pending/Artifact/integrity/issue 불변조건과 state vocabulary |
| Application | prepare→promote→commit, retry, Raw Asset 승격, token, download, reconciliation |
| Persistence | explicit PostgreSQL table, lock, transition, append-only fact, RLS-bound query |
| Storage | inspect, no-overwrite promote, discard staging, final listing, protected stream |
| API | Artifact metadata, short-lived transfer grant, byte stream, sanitized problem |

Finalization state는 다음과 같다.

```text
pending|retryable → promoting → available
                            ├→ retryable
                            └→ rejected
```

Manifest와 reserved Artifact ID는 prepare 시 고정된다. `promoting` 진입마다 attempt count가 정확히
1 증가한다. `available`과 `rejected`는 terminal이며 어떤 UPDATE/DELETE도 허용하지 않는다. Transient
object-store 실패는 `retryable`, digest/size 또는 기존 final key byte 불일치는 `rejected`다.

## 4. PostgreSQL migration

Migration `20260712_007_t10`은 다음 explicit relation을 추가한다.

| Table/function | 역할 | 핵심 제약 |
| --- | --- | --- |
| `content_object_key(...)` | tenant/classification-scoped SHA-256 key | immutable/strict deterministic function |
| `artifact_pending` | staging→final orchestration projection | immutable manifest, idempotency, raw source FK, guarded transition |
| `artifact` | available immutable file manifest | exact pending insert guard, content-key check, immutable trigger |
| `integrity_observation` | 실제 object check fact | expected manifest 일치 guard, append-only |
| `integrity_projection` | 현재 verified/missing/corrupt | 반드시 새 observation을 가리키는 guarded projection |
| `reconciliation_issue` | orphan/pending mismatch fact | typed issue, append-only, optional pending FK |

모든 resource PK/FK/index는 organization/project를 선두에 두고 classification을 bounded reference에
포함한다. 모든 table에 `ENABLE/FORCE ROW LEVEL SECURITY`를 적용하고 `artifact.read`와
`artifact.write`를 분리한다. Reconciler도 전역 bypass가 아니라 선택한 tenant의 service principal
context로 실행한다.

Artifact manifest는 `artifact_kind`, `artifact_role`, optional `schema_ref`, MIME, size, SHA-256,
encryption profile과 source identity를 명시적 column으로 저장한다. JSONB/EAV content, Material,
시험, dataset, solver table은 추가하지 않는다. Trigger의 `to_jsonb`는 row column mutation 비교에만
사용되며 persisted JSON payload가 아니다.

## 5. Object-store와 비원자성

Filesystem reference adapter는 다음을 실제 byte I/O로 검증한다.

- staging/final object를 1 MiB 이하 chunk로 재해시
- source SHA-256/size 확인 후 fresh temporary copy와 fsync
- hard-link no-overwrite commit; 기존 final key는 byte가 완전히 같을 때만 idempotent replay
- final prefix listing과 각 object 재해시
- symlink, path escape, unsafe key, 다른 byte로 같은 content key 대체 거부
- public API가 아닌 test-only fault hook으로 missing/corrupt fixture 재현

Object copy가 성공하고 DB commit 전에 process/DB가 실패하면 pending은 `promoting`으로 남는다.
Reconciler는 final object가 manifest와 같음을 확인한 뒤 Artifact/initial observation/projection을 같은 DB
transaction에서 복구한다. DB가 available인데 object가 사라지거나 변하면 새 observation으로
`missing`/`corrupt`를 기록한다. DB가 모르는 canonical final object는 orphan issue가 된다.

Artifact와 initial `verified` observation, integrity projection, pending `available` 전환은 한 PostgreSQL
transaction이다. 성공 후 staging cleanup 실패는 available 결과를 되돌리지 않고 T-16 retention cleanup
대상으로 남긴다.

## 6. Raw Asset와 duplicate content

T-10 service가 구성된 upload completion은 T-09 Raw Asset commit 직후 `raw:{raw_asset_id}` server-side
idempotency key로 finalization을 수행한다. Completion response는 `available_artifact_id`를 반환한다.
Raw Asset row는 수정하지 않는다.

다른 actor가 동일 byte를 다시 ingest하면 T-09는 기존 Raw Asset을 재사용하고 새 Ingestion Event를
남긴다. Raw Asset 기반 finalization은 actor가 달라도 기존 available Artifact를 안전하게 반환한다.
사용자가 지정하는 일반 idempotency key는 계속 actor scope 충돌을 거부한다.

## 7. API와 transfer token

- `GET /api/v1/artifacts/{artifact_id}`: immutable metadata와 current integrity status
- `POST /api/v1/artifacts/{artifact_id}:download-token`: 짧은 수명의 transfer capability 발급
- `GET /api/v1/artifacts/{artifact_id}/content`: bearer와 `Artifact-Transfer-Token`으로 byte stream

Token은 canonical JSON과 URL-safe Base64로 인코딩하며 non-canonical padding 표현도 거부한다. Token은
artifact ID, organization, project, actor, SHA-256, expiry에 서명된다. 발급과 stream 직전에 object
digest/size를 확인하고 projection이 `verified`가 아니면 전송하지 않는다. Response에는 Content-Length와
`X-Content-SHA256`을 제공하지만 staging/final storage key는 metadata, grant, problem 어느 계약에도 없다.

## 8. Reconciliation

Tenant-scoped reconciliation pass는 다음 순서로 동작한다.

1. visible Artifact object를 inspect하고 verified/missing/corrupt observation을 append한다.
2. unfinished pending의 final object가 이미 맞으면 DB commit gap을 복구한다.
3. final이 없고 staging이 맞으면 promotion을 재시도한다.
4. missing/corrupt staging 또는 corrupt final은 typed issue와 필요 시 rejected state를 기록한다.
5. tenant final prefix를 list해 Artifact/pending이 모르는 canonical object를 orphan으로 기록한다.

Artifact/Raw Asset을 고치거나 삭제하지 않으며, transient object-store 접근 실패를 missing으로 오판하지
않고 run 자체를 실패시켜 재시도 가능하게 한다.

## 9. 검증 범위

- Unit: canonical key/parse와 tenant/classification 차이, transfer scope/expiry/tamper/canonical Base64,
  filesystem promote/replay/list/stream/corrupt overwrite 거부
- API integration: metadata→grant→stream, unknown/tampered/missing token, SHA header, storage-key 비노출
- PostgreSQL integration: non-owner RLS role, Raw Asset 자동 승격과 cross-actor dedup, duplicate finalize,
  immutable Artifact/pending/observation, cross-project opaque 404
- Failure integration: transient copy retry, object success/DB response loss 복구, missing/corrupt final,
  orphan final, missing staging, download 차단
- Migration/contract/architecture: real upgrade/downgrade, triggers/constraints/indexes/policies, no JSONB/EAV
  or business schema, OpenAPI security와 object-key 비노출

## 10. 미결정 및 후속 경계

- Production S3-compatible adapter, KMS/encryption profile realization, object lock/versioning/replication
- T-16 durable reconciliation schedule, outbox/inbox, issue dedup/resolution lifecycle, staging retention GC
- T-13 typed Entity/Activity/Agent provenance와 finalization/reconciliation association
- T-17 package reference의 authoritative Artifact admission과 T-18 materializer/committer deployment wiring
- release-specific retention/legal hold와 T-36 backup/restore drill

이 항목은 현재 Artifact manifest에 vendor credential, mutable placeholder, 가짜 plugin Job 또는
domain-specific schema를 넣어 완료된 것처럼 표시하지 않는다.
