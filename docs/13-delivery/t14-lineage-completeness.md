# T-14 lineage·completeness 구현 기록

Status: `complete`

## 1. 범위와 추적성

- Task: `T-14`
- Requirements: `FR-DAT-007`, `FR-WF-003`, `NFR-REP-002`, `NFR-PERF-003`
- Decisions: `ADR-002`
- 선행 구현: `T-04`, `T-13`

이 단위는 T-13의 typed provenance relation을 사용해 Entity 기준 upstream/downstream
lineage, downstream impact, provenance completeness report를 제공한다. organization/project와
classification 경계를 넘지 않으며 arbitrary graph analytics, graph write, Material/Test/
Dataset/fitting/solver 기능은 추가하지 않는다.

T-30 Release가 아직 없으므로 release 생성 API나 required evidence/review/mapping policy를
가정하지 않는다. 대신 T-30이 조합할 수 있는 generic Entity-root completeness gate를
제공한다. `complete`인 report만 `eligible=true`이고, 누락은 `incomplete`, 탐색 한계 도달은
`indeterminate`로 닫힌다.

## 2. 권장 가정과 한계

- 기본 탐색 깊이 10, 최대 깊이 20
- graph당 최대 10,000 node
- 기본 page 100, 최대 page 1,000
- cursor는 root, direction, depth, target Entity type, 마지막 위치에 결합된 canonical
  URL-safe payload
- cursor는 권한 토큰이 아니며 매 요청마다 bearer authorization과 PostgreSQL RLS를 다시
  적용
- 10-hop 또는 10,000-edge fixture query는 2초 미만을 검증

한계에 닿은 graph는 일부 node가 정상이어도 완전하다고 판정하지 않는다. 일반 lineage
응답은 `graph_truncated=true`, completeness는 `graph_limit_exceeded` issue와
`indeterminate` 상태를 반환한다.

## 3. PostgreSQL read model

Migration: `20260713_009_T14_lineage_read_model.py`

| View | 원본 typed relation | 책임 |
| --- | --- | --- |
| `provenance.dependency_edge` | derivation, usage+generation, revision | 고정된 세 relation family의 child→parent edge |
| `provenance.entity_completeness` | entity, generation | primary generation 존재 여부 |
| `provenance.activity_completeness` | activity, usage, association, generation | declared input/agent/output 충족 여부 |

세 view는 `security_invoker=true`, `security_barrier=true`이며 underlying table의 강제 RLS를
호출자에게 그대로 적용한다. 저장된 generic edge/closure/EAV table은 만들지 않는다.

Repository는 recursive CTE의 정렬된 frontier/visited UUID array로 level을 확장하며
10,001번째 후보를 sentinel로 사용해 탐색 자체를 10,000 node 안에서 중단한다. 발견된
UUID와 depth를 Entity/generation typed query로 별도 materialize하므로 RLS security view와
Entity를 하나의 큰 recursive plan에서 중복 조인하지 않고 10,000-edge fan-out에서도
안정적인 plan을 유지한다. 반환 node 내부 edge와 depth boundary의 미발견 edge를 별도로
확인해 node/depth truncation을 구분 없이 fail closed한다.

## 4. Application 계약

- diamond처럼 같은 Entity로 가는 경로가 여러 개여도 node는 한 번만 반환한다.
- canonical shortest path는 `(depth, Entity UUID, relation)` 순서로 결정되어 반복 조회가
  동일하다.
- upstream은 child에서 parent로, downstream/impact는 parent에서 child로 탐색한다.
- impact의 optional `target_entity_type`은 namespaced stable token만 허용한다.
- cursor를 다른 root/direction/depth/filter에 재사용하면 요청을 거부한다.
- cycle 검사는 recursion 없는 Kahn algorithm으로 최대 graph에서도 stack overflow 없이
  종료한다.

Completeness issue는 `missing_primary_generation`, `missing_activity_input`,
`missing_activity_agent`, `missing_activity_output`, `missing_source_path`,
`dependency_cycle`, `graph_limit_exceeded`로 제한한다. 특정 시험법, Material Model, CAE
solver의 의미는 포함하지 않는다.

## 5. Public API

```text
GET /api/v1/provenance/entities/{entity_id}/lineage
GET /api/v1/provenance/entities/{entity_id}/impact
GET /api/v1/provenance/entities/{entity_id}/completeness
```

`lineage`는 `direction`, `max_depth`, `limit`, `cursor`, `target_entity_type`을 받는다.
`impact`는 direction을 downstream으로 고정한다. 세 endpoint 모두 bearer authentication과
`provenance.read`가 필요하며 404/409/422 응답에 DB table, SQL, hidden UUID를 노출하지 않는다.

## 6. 검증

- unit: diamond canonical path, duplicate 제거, cursor binding, impact filter, completeness
  state, cycle, depth/page/node policy
- contract/API: 세 read-only endpoint, Entity hypermedia link, positive/negative JSON Schema,
  sanitized problem, additive OpenAPI compatibility
- PostgreSQL integration: 양방향 known DAG, pagination, 10-hop chain, 10,000-edge fan-out,
  orphan/incomplete Activity/cycle, cross-project와 above-clearance RLS
- migration/architecture: 세 explicit security-invoker view, 실제 upgrade/downgrade, no EAV/
  business schema

Synthetic Entity/Activity fixture는 test-only이며 Release, Material, 시험 importer, fitting,
solver exporter를 구현하거나 암시하지 않는다.
