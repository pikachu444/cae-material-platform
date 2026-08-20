# ADR-015: Immutable review lifecycle for candidate revisions

## 먼저 읽기

- **무엇을 정했나요?** Review Request는 정확한 candidate revision과 manifest digest를 고정하고,
  작성자와 다른 reviewer가 한 번의 불변 결정을 내립니다. 오래된 request는 승인할 수 없습니다.
- **왜 중요한가요?** 수치 결과를 곧바로 사람의 승인으로 취급하지 않고, 검토 뒤 수정이 필요해도
  거절된 revision과 판단 이력을 그대로 남기기 위해서입니다.
- **언제 읽나요?** review request·decision, reviewer 권한, changes requested 재제출, lifecycle 상태 또는
  승인된 Record publication을 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `manifest digest`는 검토 대상 증거 묶음의 내용 hash이고, `lifecycle
  projection`은 event 이력에서 계산한 현재 상태입니다. `separation of duties`는 요청자와 승인자를
  분리하는 원칙입니다.
- **상태 표기는?** `accepted`는 이 불변 review 경계를 채택했다는 뜻입니다. configurable 승인 행렬,
  법적 서명, production release 전체가 구현됐다는 뜻은 아닙니다.

Status: accepted

## Context

T-28 produces reference validation evidence, but a numerical verdict is not a human acceptance or
release decision. The platform needs a tenant-scoped review boundary that can consume any bounded
candidate manifest without importing Material, Dataset, solver, or calibration internals.

## Decision

1. A Review Request pins `aggregate_type`, stable `aggregate_id`, exact `revision_id`, and a
   lowercase SHA-256 `manifest_sha256`. The request is accepted only while that revision's
   lifecycle projection is `draft`.
2. The request transition is `draft -> review`. A decision is an immutable row and a lifecycle
   event in the same PostgreSQL transaction. `approved` transitions to `approved`;
   `changes_requested` transitions to `changes_requested`.
3. A request has one decision. A request author cannot decide their own request, and only a
   `domain_reviewer` authorization role may record a decision. The required role is fixed for this
   MVP; a configurable approval matrix is a later product decision.
4. A decision must present the exact request manifest digest. If a newer revision was created for
   the same aggregate after the request, the old request is stale and cannot be approved.
5. `changes_requested` never mutates the rejected revision. Resubmission is possible only through
   the new immutable revision's initial `draft` lifecycle projection.
6. Review requests and decisions use explicit PostgreSQL tables, composite tenant keys, forced
   RLS, immutable triggers, and no generic EAV or opaque business payload. A registered subject is
   resolved server-side into a closed evidence snapshot containing schema, validation, artifact,
   exact input, and affected Materials Record references; clients may provide only expected hints.
7. An approved request is projected atomically into an immutable publication projection and the
   Catalog publication marker. The projection requires the exact affected Record revision to remain
   current and rejects stale bindings; no direct catalog publish bypasses review evidence.

## Consequences

- Review state is queryable through the existing lifecycle projection and event history.
- Candidate domain modules remain independent of governance storage and APIs.
- T-30 can consume approved requests and verify the exact digest before composing a Release.
- Comments, evidence attachments, legal signatures, configurable multi-role approvals, and full
  Release package composition remain outside T-29. Issue #160 owns the evidence-backed Record
  publication projection, exact selected-model download, and Activity recovery surface.

