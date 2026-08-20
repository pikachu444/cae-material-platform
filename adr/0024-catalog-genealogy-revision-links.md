# ADR-0024: typed Catalog genealogy pins exact revisions

## 먼저 읽기

- **무엇을 정했나요?** Process Definition, Material Lot, State Genealogy를 각자 stable identity와 불변
  revision으로 관리하고, Material State에 `latest`가 아닌 정확한 Process·Lot revision을 연결합니다.
- **왜 중요한가요?** free-text 제조 이력만으로는 검색·검증이 어렵고, 과거 State에 mutable link를
  붙이면 이미 기록된 의미가 바뀌기 때문입니다.
- **언제 읽나요?** 제조·열처리 Process, Lot/Batch, Material State genealogy, record link 또는 기존
  free-text 이력의 호환성을 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `genealogy`는 재료가 어떤 Process와 Lot을 거쳐 현재 State가 됐는지 보여
  주는 계보입니다. `stable identity`는 같은 대상을 계속 가리키는 ID이고, `revision`은 그 대상의
  특정 시점 내용입니다. link는 항상 특정 revision을 고정합니다.
- **상태 표기는?** `Accepted`는 bounded typed genealogy 경계를 채택했다는 뜻입니다. lot split·merge,
  ERP 연결이나 production genealogy qualification이 구현됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-16
- Scope: T-07 bounded product vertical

## Context

Material State revisions already preserve legacy free-text manufacturing route, heat-treatment,
and Lot/Batch labels. Those fields are useful source metadata but cannot represent a governed,
queryable genealogy graph. Adding mutable foreign keys to old State rows would also change the
meaning of already recorded revisions.

The Catalog therefore needs Granta-style linked records without importing a proprietary schema:
stable identities must remain distinct from immutable revisions, organization/project isolation
must be enforced in PostgreSQL, and every link used by downstream testing or modeling must resolve
to a concrete revision rather than `latest`.

## Decision

1. Add stable `Process Definition`, `Material Lot`, and `State Genealogy` identities. Each identity
   has append-only typed revisions and a guarded current-head pointer.
2. A Process revision has an explicit code, name, and kind (`manufacturing`, `heat_treatment`,
   `conditioning`, or `other`). A Lot revision has an explicit Lot/Batch kind and pins one concrete
   Material revision.
3. One State Genealogy identity belongs to one Material State identity. Each Genealogy revision
   pins a concrete State revision and optionally one manufacturing Process revision, one
   heat-treatment Process revision, and one Lot revision. At least one typed link is required.
4. The service rejects process-role mismatches, cross-scope links, and a Lot whose Material
   identity or revision differs from the pinned State revision.
5. Existing Material State free-text fields remain unchanged for backward compatibility and source
   provenance. They are not automatically promoted into governed Process or Lot records.
6. PostgreSQL composite tenant/classification foreign keys, forced RLS, immutable-row triggers,
   indexes, and explicit check constraints enforce the same model below the API boundary.
7. No generic relation table, EAV structure, arbitrary JSON property bag, or moving `latest` alias
   is introduced.

## Consequences

- Users can create/select governed Process and Lot records in the Material State screen and see the
  exact revision numbers that are linked.
- Correcting a Process, Lot, or genealogy link appends a new revision; prior links remain
  reproducible.
- Full process-run input/output graphs, lot split/merge, multi-lot acceptance, ERP connectors, and
  production genealogy qualification remain explicit T-07 follow-up work.
