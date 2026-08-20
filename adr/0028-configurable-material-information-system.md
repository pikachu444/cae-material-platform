# ADR-0028: configurable material information system and dual explorer

## 먼저 읽기

- **무엇을 정했나요?** 관리자가 versioned Table·Attribute·Layout·Link를 정의하고 typed value로 Record를
  구성하며, Catalog tree와 Material workflow를 별도 explorer로 봅니다. Bundle apply는 서버가 다시
  plan한 exact 변경을 한 transaction으로 적용합니다.
- **왜 중요한가요?** 새 속성마다 database migration을 만들지 않으면서도 untyped EAV·opaque JSON을
  피하고, stale plan이나 부분 적용이 Catalog를 망가뜨리지 않게 하기 위해서입니다.
- **언제 읽나요?** configurable Catalog schema, Record value·search, explorer, Link Type, Definition Bundle
  plan/apply/export 또는 schema administrator 권한을 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `Attribute Definition`은 값의 type·unit·표시 규칙을 정한 버전이고,
  `Link Type`은 어떤 Table끼리 어떤 방향·개수로 연결할지 정합니다. `plan_fingerprint`는 검토한 plan과
  실행 시점 plan이 같은지 확인하는 hash이며, stale하면 전체 apply를 막습니다.
- **상태 표기는?** `Accepted`는 typed configurable catalog와 atomic Bundle apply 경계를 채택했다는
  뜻입니다. 모든 enterprise schema·migration·connector 요구가 완성됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0006, ADR-0024, ADR-0025; T-48 through T-51; Issues #204, #207

## Context

The fixed Material/State/Property vertical proves storage and card delivery, but it does not provide
the configurable tables, attributes, layouts, folders, subsets and record links expected from a
material information system. The existing flat routes and State genealogy are useful bounded views;
they are not a Catalog Contents Tree or a general cross-domain relationship model.

## Decision

1. Add administrator-defined Table, typed Attribute Definition, Layout, Subset and Link Type
   revisions. Adding an attribute must not require a database migration.
2. Store values in type-specific relations for scalar number, integer, text, boolean, date,
   discrete, file/artifact, curve/table and record reference. Do not use one untyped value column or
   one opaque record JSON document as the data authority.
3. Preserve original numeric value/unit text, normalized value/unit and quantity semantics together.
4. Add a Catalog Explorer projection `Workspace -> Table -> Folder -> Record` and a separate
   Material Workflow Explorer projection from exact revision links. Existing flat routes remain.
5. General links pin both endpoint revisions. Link Type declares allowed source/target Tables,
   direction labels and cardinality. Cross-scope links and `latest` aliases are rejected.
6. Fixed Material/State/Property APIs remain compatibility projections while configurable records
   are introduced. Existing identities and revisions are not rewritten.
7. A Schema Definition Bundle is an adapter-owned projection input, not a new Catalog aggregate
   model. Planning and apply both derive Database/Profile/Table/Attribute/Layout/placement/Link Type
   actions on the server. Apply accepts only exact Artifact ID, Artifact SHA-256, the existing
   `plan_fingerprint`, `delete_missing=false`, and an idempotency key; client-returned actions or
   projected content are never execution authority.
8. Apply re-runs the planner against the current RLS-scoped Catalog while holding a project lock and
   conflicting Catalog table locks. The whole revision set, exact publication markers, source
   provenance, immutable application/bindings, audit and outbox event commit in one PostgreSQL
   transaction. A stale fingerprint, current Record conflict or any write failure rolls everything
   back.
9. Bundle apply is the explicit Schema Administrator approval boundary and publishes its exact
   projected revisions atomically. The general single-revision direct-publication endpoint remains
   disabled and governed review behavior is unchanged.
10. Stable bundle identity and semantic versions are explicit normalized rows. A semantic version
    cannot be rebound to different canonical JSON. Applications and object bindings are immutable;
    export reads the exact source Artifact only while every bound Catalog head and publication marker
    still matches. Missing bundle members are never deletion authority.

## Consequences

- Users can create new record attributes and relationships without a deployment.
- Typed indexes and unit-aware search remain possible without a generic EAV value bucket.
- A record may be reached through a stable current-record route, but every relationship and
  calculation continues to pin an immutable revision.
- Bundle retries are replay-safe by tenant-scoped idempotency key, and an export can be uploaded and
  planned again as a semantic no-op. Changes that would strand current Records are reported as
  migration-required; no user migration code runs inside the adapter.

