# ADR-002: PostgreSQL authoritative store와 typed provenance

- 상태: Accepted
- 기준일: 2026-07-11

## Context

Lineage는 graph-shaped지만 MVP query는 upstream/downstream/impact처럼 알려져 있다. Domain FK, revision, approval, RLS와 provenance의 일관성이 중요하다.

## Decision

PostgreSQL을 metadata와 provenance source of truth로 사용한다. Entity/Activity/Agent와 usage/generation/derivation/revision/association을 typed relation table로 저장한다. Recursive CTE와 index로 lineage를 조회한다.

## Consequences

- domain write와 provenance가 한 transaction에 들어간다.
- graph DB 운영과 eventual consistency가 없다.
- 임의 graph analytics는 불편할 수 있다.
- 필요 시 outbox로 read-only graph projection을 만들 수 있다.

## Revisit trigger

수억 edge, 임의 5~20 hop interactive query, graph analytics가 핵심 가치가 되고 closure cache로 SLO를 충족하지 못할 때.

