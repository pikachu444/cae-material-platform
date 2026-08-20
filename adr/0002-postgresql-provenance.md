# ADR-002: PostgreSQL authoritative store와 typed provenance

## 먼저 읽기

- **무엇을 정했나요?** metadata와 provenance의 공식 원본을 PostgreSQL에 두고, 데이터가 무엇을
  사용해 어떻게 만들어졌는지 관계 종류가 분명한 table로 저장합니다.
- **왜 중요한가요?** 업무 데이터와 추적 정보를 같은 transaction에서 저장하면 서로 어긋나지 않고,
  권한과 revision 규칙도 같은 database 제약으로 지킬 수 있습니다.
- **언제 읽나요?** 새 파생 데이터나 실행 기록을 추가할 때, upstream·downstream 조회를 만들 때,
  또는 별도 graph database가 필요한지 검토할 때 읽습니다.
- **용어를 쉽게 말하면:** `provenance`는 결과가 어떤 입력과 작업, 담당자에게서 나왔는지 보여 주는
  이력입니다. `typed relation`은 `사용함`, `생성함`, `개정함`처럼 관계의 뜻을 명시해 저장하는
  방식이고, `RLS`는 database 행 단위로 접근을 제한하는 규칙입니다.
- **상태 표기는?** `Accepted`는 이 결정을 채택했다는 뜻입니다. 관련 기능이 모두 구현됐거나 현재
  환경에서 검증을 마쳤다는 뜻은 아닙니다.

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

