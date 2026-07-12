# T-16 transactional outbox 구현 기록

Status: `complete`

## 1. 범위와 추적성

- Task: `T-16`
- Requirements: `FR-API-003`, `FR-API-004`, `NFR-INT-002`
- Decisions: `ADR-001`, `ADR-003`
- 선행 구현: `T-02`, `T-04`, `T-10`, `T-15`

첫 단위는 DB domain commit과 CloudEvent 누락/유령을 막는 transactional outbox, broker-neutral
at-least-once publisher, consumer inbox dedup을 구현한다. 실제 producer로 T-10 ArtifactAvailable
event를 같은 Artifact transaction에 연결한다. Kafka/NATS/RabbitMQ를 필수 도입하거나
Material/Test/fitting/solver event를 가정하지 않는다.

두 번째 단위는 기존 T-10 reconciler를 durable tenant schedule/run에 연결하고 terminal pending의
남은 staging object만 retention cleanup한다. final/raw/release object 삭제는 범위 밖이다.

## 2. PostgreSQL 구조

Migration: `20260713_010_T16_transactional_outbox.py`

| Relation | 책임 | 변경 규칙 |
| --- | --- | --- |
| `events.outbox_event` | immutable CloudEvent source fact | append-only |
| `events.outbox_delivery` | claim/retry/published/poison lease projection | guarded state transition |
| `events.consumer_inbox` | consumer/event dedup receipt | append-only |

`outbox_event`는 organization/project/classification, event/aggregate UUID, aggregate sequence,
versioned event type, source/subject/dataschema, schema-validated data JSON object와 SHA-256,
actor/request/trace, occurrence/recording time, producer deduplication key를 명시한다. JSONB는 이
이름 있는 CloudEvent data 계약에만 사용하며 generic EAV attribute/value 구조가 아니다.

aggregate별 advisory transaction lock과 unique sequence constraint가 동시 append 순서를
직렬화한다. deduplication key replay는 모든 immutable field와 data digest가 같을 때만 허용한다.
세 table 모두 forced RLS를 사용하며 owning command는 `events.publish`, Job Runner는
`events.dispatch`/`events.consume` 내부 capability만 얻는다.

## 3. 전달·중복·poison 규칙

- publisher claim은 `FOR UPDATE SKIP LOCKED`, lease expiry, UUID fencing token을 사용한다.
- broker가 event를 받은 뒤 DB published 확인 전에 process가 죽으면 같은 event가 다시 전달될 수
  있다. 이는 at-least-once의 정상 상태다.
- consumer는 side effect transaction 안에서 `(tenant, consumer_name, event_id)` inbox receipt를
  먼저 insert하고 duplicate conflict면 side effect를 생략한다.
- 같은 aggregate의 앞 sequence가 `published`가 아니면 뒤 sequence를 claim하지 않는다.
- bounded retry를 초과한 event는 immutable payload를 바꾸지 않고 delivery를 `poison`으로
  격리한다. 해당 aggregate의 뒤 event도 자동으로 건너뛰지 않는다.

## 4. ArtifactAvailable 계약

Event type: `io.cmp.artifact.available.v1`

Artifact, initial integrity observation/projection, pending available 전환, outbox event/delivery가
한 PostgreSQL transaction에 들어간다. event schema는 Artifact/pending UUID, kind/role/schema,
MIME, size, SHA-256, optional Raw Asset UUID, 생성 시간을 포함한다. storage key, staging key,
credential, vendor URL은 포함하지 않는다.

Runtime hook은 packaged JSON Schema 2020-12 사본으로 완성된 CloudEvent envelope를 검증한다.
public schema와 packaged schema의 byte-equivalent JSON document를 contract test로 고정한다.

## 5. 검증

- unit: CloudEvent URI/type/canonical data, tenant extension, publisher success/retry/poison
- contract: AsyncAPI 3 channel/message, positive ArtifactAvailable, storage-key negative fixture,
  runtime/public schema 동일성
- PostgreSQL: Artifact+event atomic commit/rollback, exact replay, aggregate sequence, out-of-order
  차단, crash lease reclaim, stale fencing, poison, inbox duplicate, cross-project RLS
- migration: 세 explicit relation, constraints/indexes/triggers, forced RLS, 실제 upgrade/downgrade,
  JSONB의 schema-identified event data 한정

외부 broker adapter와 운영 credential은 deployment composition이다. phase 1은 transport port와
authoritative delivery state를 제공하며 특정 broker를 core dependency로 만들지 않는다.

## 6. Durable reconciliation과 retention

`20260713_011_T16_reconciliation_schedule.py`는 tenant별 schedule, append되는 run history,
staging cleanup receipt를 추가한다. schedule claim은 `FOR UPDATE SKIP LOCKED`와 UUID lease token을
사용한다. worker crash로 lease가 만료되면 기존 running run을 `timed_out`으로 끝내고 새 run/token을
발급한다. terminal run의 identity/result는 수정할 수 없다.

Maintenance coordinator는 기존 T-10 `reconcile`을 먼저 실행한 뒤 retention window를 지난
`available|rejected` pending 중 `staging_object_key != final_object_key`이고 cleanup receipt가 없는
항목만 discard한다. discard 성공 후 같은 transaction scope의 run을 참조하는 immutable receipt를
남긴다. retry 시 이미 없는 staging discard와 receipt conflict는 idempotent하다. Artifact storage key,
Raw Asset staging fact, release/final object는 candidate query에 포함되지 않는다.
