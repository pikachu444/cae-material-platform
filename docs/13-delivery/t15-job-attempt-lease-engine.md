# T-15 PostgreSQL Job/Attempt/Lease engine 구현 기록

## 1. 추적성

- Task: `T-15`
- Requirements: `FR-API-002`, `FR-PLG-004`, `NFR-DR-002`, `NFR-PERF-006`,
  `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-006`
- ADR: `ADR-001`, `ADR-002`
- 선행 구현: T-02 Job Spec/Result Manifest 계약, T-03 service principal/request context,
  T-04 authorization/RLS

T-15는 Material, 시험 importer, fitting, solver exporter 또는 plugin 실행 환경을 구현하지
않는다. core는 `job_type`을 안정적인 범용 식별자로만 취급하며 extension payload를 해석하지
않는다.

## 2. 확정한 경계와 권장 가정

1. `Job`은 안정 identity와 현재 운영 상태 projection이다. 각 실행은 별도 `Job Attempt`이며,
   Attempt마다 완전한 immutable Job Spec과 SHA-256 digest를 가진다.
2. 문서에서 `failed`/`timed_out`은 terminal이지만 retry API는 새 Attempt를 요구한다. 따라서
   terminal은 해당 Attempt에 대해 절대적이며, Job projection만 명시적 retry 명령에서
   `failed|timed_out -> queued`로 전환할 수 있다.
3. 기존 Job Spec 1.0이 `job_id`와 `attempt_id`를 요구하므로 T-15의 직접 submit API는 두 UUID를
   포함한 완전한 Spec을 받는다. 이후 도메인별 submit endpoint는 같은 application service를
   호출하면서 서버에서 UUID를 만들 수 있다.
4. Runner는 MVP에서 project-scoped로 제한한다. 조직 공용 또는 여러 project를 횡단하는 runner는
   별도 authorization/운영 결정 전까지 허용하지 않는다.
5. failure taxonomy와 자동 retry 범위는 Domain 최종 승인 전 `ASSUMPTION`이다. 보수적인 기본값은
   아래 표와 같다.

| Failure category | 기본 retry | 근거 |
| --- | --- | --- |
| `transient_infrastructure` | 자동 | 일시적 process/network/lease 장애 |
| `resource_exhausted` | 자동 | 제한된 attempt 수 안에서 다른 가용 자원 기대 |
| `external_unavailable` | 자동 | 외부 endpoint의 일시 장애 |
| `internal_error` | 자동 | 제한된 attempt 수로 복구 가능성 확인 |
| `policy_denied` | 수동만 | 정책 변경 확인 없이 반복하지 않음 |
| `output_invalid` | 수동만 | invalid output을 자동 재생산하지 않음 |
| `deadline_exceeded` | 수동만 | 새 deadline/resource 판단이 필요함 |
| `domain_invalid` | 금지 | 동일한 immutable input 재실행은 의미가 없음 |

## 3. PostgreSQL 구조

Migration head는 `20260711_004_t15`이다.

### `jobs.runner`

- organization/project/classification과 opaque runner UUID
- `active|draining|offline` 상태
- `max_concurrency`, CPU millicore, memory MiB, GPU capacity
- 등록 actor/time과 operational heartbeat
- project-scoped composite PK와 classification-aware RLS

### `jobs.runner_job_type`

- runner와 허용된 generic `job_type`의 정규화된 다대다 관계
- capability를 JSON/EAV로 저장하지 않음
- runner와 tenant/classification을 포함한 composite FK

### `jobs.job`

- organization/project/classification, stable UUID, generic `job_type`
- state, priority, submit actor/time/request/trace
- tenant-scoped idempotency key와 canonical submission digest
- deadline과 명시적 CPU/memory/GPU/max-attempt resource policy
- current Attempt pointer, attempt count, cancel tuple, terminal manifest/failure tuple
- optimistic `row_version`

Job identity, tenant, submission, idempotency digest, deadline, resource policy는 trigger에서
immutable이다. 상태와 현재 Attempt pointer는 허용된 상태 전이에서만 바뀐다. Job과 현재 Attempt는
deferred composite FK로 연결되어 retry transaction이 중간 dangling reference를 노출하지 않는다.

### `jobs.job_attempt`

- tenant/classification, attempt UUID, owning Job, monotonic attempt number
- `initial|automatic|manual|lease_recovery`와 reason/actor/time
- Job Spec 1.0 JSONB와 canonical SHA-256 digest
- runner, lease fencing token, expiry, heartbeat, claim/start/end time
- best-effort progress와 terminal Result Manifest/failure reference

JSONB는 generic EAV가 아니라 공개된 immutable Job Spec 1.0 문서 한 곳에만 사용한다. 상태, lease,
resource, failure, result, tenant는 모두 전용 typed column이다. Spec의 `job_id`/`attempt_id`는 DB
constraint로 owning row와 일치시킨다.

Attempt terminal 전환 후에는 어떤 column도 수정할 수 없다. terminal 이전에도 Spec/digest/retry
facts/tenant/identity는 trigger가 차단하며, progress·heartbeat·lease expiry는 뒤로 이동할 수 없다.

## 4. Claim, lease와 복구

1. Worker는 `job_runner` service role과 `job.execute`만 사용한다.
2. claim transaction은 runner row를 잠가 max concurrency를 직렬화한다.
3. runner capability와 개별 resource capacity를 만족하는 queued Job을 priority/FIFO 순서로
   `FOR UPDATE SKIP LOCKED` claim한다.
4. Attempt에 opaque lease token, owner, expiry, heartbeat를 원자적으로 기록한다.
5. start/heartbeat/finalize는 Attempt UUID와 lease token을 모두 제시해야 하며, 현재 Attempt가
   아니거나 expiry가 지났으면 `LeaseLost`로 거부한다.
6. reaper는 만료 Attempt를 `timed_out`으로 보존한 뒤 제한과 deadline이 허용하면 새 Attempt와
   새 Job Spec digest를 append한다. 같은 Attempt를 재개하지 않는다.
7. terminal finalize 재호출은 outcome/manifest digest/failure가 완전히 같을 때만 idempotent하다.
   다른 digest 또는 stale token은 기존 commit을 덮어쓸 수 없다.

구현은 PostgreSQL이 queue-like table에서 권고하는 `SKIP LOCKED` row locking을 사용한다.
[PostgreSQL SELECT locking 문서](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)

## 5. API 계약

- `POST /api/v1/jobs`: `Idempotency-Key` 필수, immutable Job Spec/resource policy 제출,
  `202 Accepted`, `Location`, `Idempotent-Replay`
- `GET /api/v1/jobs/{job_id}`: Job, 모든 Attempt, best-effort progress, terminal manifest/problem
- `POST /api/v1/jobs/{job_id}:cancel`: queued work는 원자적으로 cancel, 실행 중이면 cooperative
  `cancel_requested`
- `POST /api/v1/jobs/{job_id}:retry`: reason 필수, 새 Attempt/Spec append

각 route는 T-03 authentication 뒤 T-04의 `job.read|submit|control`을 명시적으로 요구한다. 존재하지
않거나 다른 tenant에 있는 opaque UUID는 같은 sanitized 404 응답을 사용한다. DB transaction에는
동일한 security/authorization decision을 transaction-local RLS context로 bind한다.

Result Manifest는 T-15에서 UUID와 digest 참조만 저장한다. artifact commit/reconciliation은
T-10/T-16, provenance generation relation은 T-13의 소유 범위다.

## 6. Worker 경계

`DurableJobWorker`는 generic handler registry와 authorized queue port만 안다. 한 cycle에서
claim→start→heartbeat→cooperative cancel→finalize를 수행한다. handler exception은 sanitized
`internal_error/handler_exception`으로 terminal 처리한다.

T-18이 runner 인증과 격리 실행을 제공하기 전에는 CLI가 환경 변수로 service identity를
위조하지 않는다. queue/handler가 주입되지 않은 process는 deployment smoke test를 위해 안전하게
idle 상태를 반환한다.

## 7. 검증 범위

- Domain unit: 상태 전이, retry taxonomy, immutable canonical Spec, resource limits
- Contract/API: Job Spec runtime/public schema 동일성, 202/Location/idempotency, authorization/404
- Migration: explicit table/check/FK/index/trigger/RLS, Job Spec 외 JSONB/EAV 부재
- PostgreSQL integration: concurrent atomic claim, runner concurrency, crash/lease expiry/new Attempt,
  stale heartbeat fencing, cooperative cancel, duplicate/different finalize, transient auto retry,
  invalid-input retry 차단, cross-project RLS, terminal Spec mutation 차단, clean downgrade
- Regression: T-03 principal, T-04 authorization/RLS, T-06 revision/CAS/immutability, worker/API startup

## 8. 미결정 사항

- failure taxonomy와 자동 retry 허용 범위의 Domain 승인
- organization-wide/cross-project runner가 필요한지와 그 경우의 RLS claim 모델
- resource 합산 scheduling, organization/job-class quota의 최종 운영 정책
- runner credential 발급·회전과 isolated package execution(T-18)
- outbox/event와 artifact reconciliation(T-16), provenance activity 연결(T-13)

이 항목들은 현재 schema의 immutable execution facts를 재작성하지 않고 후속 migration/adapter로
확장할 수 있다.
