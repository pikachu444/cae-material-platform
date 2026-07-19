# T-76 hierarchical Material Database evidence

Captured on 2026-07-19 from the Docker Compose demo at
`http://127.0.0.1:5173/database`.

The product Material Database now uses a persistent three-pane workspace instead of the previous
developer-oriented flat Catalog screen:

- the left **Contents Tree** expands Database → Profile → Table → nested Folder → Record lazily from
  PostgreSQL;
- the center **Workflow Tree** projects the selected exact Record revision through typed links from
  Material and Material State to Test Data, Processing Output, Material Model IR, Neutral Material
  and Abaqus/OpenRadioss cards;
- the right **Related Data** pane shows only links directly incident to the selected exact revision;
- a governed workflow node opens its existing workbench by exact domain identity/revision, while an
  unbound node opens its exact configurable Record route.

The screenshot uses public synthetic DP780 demo data. It is product navigation evidence, not a
claim that T-77 Layout Datasheet, AMDC-style facets and comparison are complete.

![Hierarchical Material Database Contents and Workflow Trees](../images/t76-material-database-tree.png)

The persistence contract was corrected as part of the vertical slice. A stable Catalog Record can
append a new revision and bind that new exact Record revision to the same exact governed revision;
a different stable Catalog Record cannot claim that target. A stable Record Link can likewise
append a revision that advances its exact endpoint pins without rewriting historical link
revisions. Migration 082 backfills and enforces the stable identity mapping explicitly.

Verification:

- focused Vitest: nested lazy Folder expansion and exact workflow selection, 2 tests passed;
- live PostgreSQL: same-record rebinding, cross-record conflict, link pin advance/deactivation and
  depth-eight workflow graph passed as part of the isolated 76-test PostgreSQL suite;
- migration/architecture regression: Migration 082 upgrade, downgrade and schema guard passed;
- clean demo seed/reseed: 8 current Record heads remained unchanged and the graph returned 8 nodes
  with 7 typed links;
- live browser: nested Metals → Steels → DP780 selection, Test Data workbench navigation and browser
  return to the expanded Material Database were verified.
- CI command body: Ruff, mypy over 651 files, architecture, contracts/OpenAPI, 775 Python tests,
  64 frontend tests, production bundle limit and the 19-document/57-capture guide gate passed. The
  default Python run's 76 isolated-PostgreSQL skips were all exercised separately and passed.
