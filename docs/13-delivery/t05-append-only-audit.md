# T-05 append-only audit와 tamper evidence 구현 기록

Status: `complete`

## 1. 범위와 추적성

- Task: `T-05`
- Requirements: `NFR-AUD-001`, `NFR-AUD-002`, `NFR-SEC-003`, `NFR-SEC-006`
- Decisions: `ADR-001`, `ADR-002`
- 선행 구현: `T-03`, `T-04`, `T-06`

보안·업무 command 결과를 domain provenance와 분리된 audit bounded module에 기록한다.
이번 범위는 PostgreSQL append-only event/hash chain, periodic segment root, T-06 revision
transaction hook, auditor query/export/integrity API다. 외부 SIEM/WORM/KMS connector와
Material/Test/fitting/solver 전용 action은 포함하지 않는다.

## 2. PostgreSQL 구조

Migration: `20260713_012_T05_append_only_audit.py`

| Relation | 책임 | 변경 규칙 |
| --- | --- | --- |
| `audit.event` | actor/action/target/outcome/request/trace/reason과 hash-linked fact | insert-only |
| `audit.segment_root` | 연속 event 구간의 주기적 root와 이전 root 연결 | insert-only |

chain scope는 `(organization_id, project_id)`다. event append trigger가 tenant별 advisory
transaction lock을 잡고 `sequence_no`, `previous_hash`, `recorded_at`, `event_hash`를 강제로
계산한다. caller가 sequence/hash를 덮어쓸 수 없다. segment trigger도 직전 sealed range 다음
sequence부터 최대 10,000개인 연속 구간만 허용하고 root hash를 DB에서 계산한다.

두 relation 모두 `ENABLE/FORCE ROW LEVEL SECURITY`를 사용한다. `audit.append`는 이미
인가된 modifying command에서만 파생되는 내부 DB capability이고 public role permission이
아니다. `audit.read`는 Auditor query용이며, `audit.seal`은 배포 worker가 root를 만들 때 쓰는
내부 capability다. update/delete는 RLS와 immutable trigger로 차단한다. 운영 grant는
`SELECT, INSERT`만 부여한다.

## 3. Canonical hash와 redaction

event hash는 `cmp-audit-event-v1`, segment root hash는 `cmp-audit-segment-v1` prefix를 사용한다.
각 명시적 field를 UTF-8 byte 길이로 framing하고 SHA-256을 계산한다. Python verifier와
PostgreSQL 함수는 같은 timestamp/UUID/null 표현을 사용하며 실제 PostgreSQL test에서 byte
동등성을 확인한다.

audit table에는 JSONB payload, generic attribute/value, secret, storage key를 두지 않는다.
`ip_or_client`는 persistence 전에 항상 `policy-redacted`로 바뀌며 DB constraint도 원문 저장을
거부한다. reason은 길이가 제한된 업무 설명만 허용한다.

## 4. Transaction hook과 API

`SqlAlchemyRevisionAuditHook`은 T-06 `RevisionCreated`를 generic action/target으로 변환하고
revision insert/head advance/provenance/lifecycle hook과 같은 caller transaction에서 audit를
append한다. audit append 실패 또는 뒤의 hook 실패는 전체 command를 rollback한다. 특정
재료, 시험, 모델, solver vocabulary는 사용하지 않는다.

public API는 모두 `audit.read`가 필요한 read-only endpoint다.

- `GET /api/v1/audit/events`: sequence pagination과 action/actor/target/outcome/time filter
- `GET /api/v1/audit/integrity`: 전체 visible chain과 segment root 재검증
- `GET /api/v1/audit/export`: 최대 10,000 event, 시작 anchor, 겹치는 roots, integrity report

public write/seal endpoint는 없다. export contract도 raw payload, secret, object key를 허용하지
않는다.

## 5. 검증

- unit: canonical framing/SHA-256, client redaction, valid chain/root, mutation/reorder/delete
- contract/API: auditor-only 세 endpoint, bounded export, sanitized problem, raw-payload negative
  fixture, read-only OpenAPI
- migration: explicit table/constraint/index/trigger/RLS/capability, JSONB/EAV 부재
- PostgreSQL 16.14: revision hook atomic commit/rollback, DB/application hash parity, segment seal,
  project isolation, update/delete 차단, 관리자 mutation/reorder/delete 탐지, 실제
  upgrade/downgrade/re-upgrade

## 6. 배포 미결정 사항

hash chain만으로 `NFR-AUD-002`를 충족하며 periodic root도 보관한다. root의 외부 KMS 서명,
WORM retention, SIEM 전달, 보존 기간, 법적 hold 정책은 배포·Security/Auditor 결정이다. 이
connector를 추가하더라도 PostgreSQL event/root를 authoritative source로 유지하고 기존 row를
수정하지 않는다.
