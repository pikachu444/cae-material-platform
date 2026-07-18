# T-51 Dual Explorer and Record Link evidence

Verified on 2026-07-18 against the Docker Compose demo and PostgreSQL migration head
`20260827_061_t51`.

## Demonstrated workflow

1. The Catalog Explorer lazily expanded `Engineering Materials → Metals → Sheet metals`.
2. `DP600 dual-phase steel` current revision 2 opened through an exact-revision deep link.
3. The workflow graph showed `DP600 tensile test` revision 1 through the administrator-defined
   `Material test evidence` Link Type.
4. The forward label was `has tensile test`; opening the target displayed the reverse label
   `is tensile test for` and linked back to DP600 revision 2.
5. API responses retained both endpoint revision UUIDs and the exact Link Type revision UUID.

## Evidence

- `t51-catalog-workflow-explorer.png`: lazy tree, exact workflow nodes and forward link.
- `t51-reverse-record-link.png`: reverse traversal from the test record to the material revision.
- PostgreSQL integration regression covers endpoint compatibility, current-head independence,
  cardinality and append-only deactivation.
- API/contract/React tests cover protected endpoints, UUID-only revision parameters and lazy UI.

Actual solver execution is outside T-51 and remains explicitly excluded from this roadmap.
