# DUI-02 — Resizable Materials workspace evidence

Status: implemented and browser-verified on 2026-07-22  
Task: `DUI-02`  
Requirements: `FR-NAV-002`, `FR-LNK-002`, `FR-CAT-001`  
Architecture: `ADR-0034` product-experience boundary

## Scope and contract disposition

This slice changes only the Materials presentation and client-side location state. It adds a public
resizable split-pane primitive, keyboard-resizable result columns, an in-workspace Material
datasheet, and an exact Catalog Record revision datasheet. No API, OpenAPI, database, domain model,
unit conversion, provenance, IR, solver mapping, or released-artifact behavior changed.

The exact Record route is
`/materials/records/:recordId/revisions/:revisionId`. It loads the requested revision from the
existing revision-list contract and fails visibly when that ID is absent; it never substitutes the
record head. Number values display original value/unit beside normalized value/unit and quantity
semantics. Existing `/database`, `/catalog/explorer`, `/materials/:materialId`, card-preview and
legacy contextual routes remain addressable.

## Installed quality skills

The repository-owned `.codex/skills/desktop-engineering-ui/SKILL.md` was installed into the user
Codex skill directory from the latest `main`; the source and installed contents compare equal (the
byte hash differs only because the installer normalized LF/CRLF). The mandatory project-local
helpers were installed from the repository root:

- `.agents/skills/frontend-ui-engineering`
- `.agents/skills/web-design-guidelines`
- `.agents/skills/webapp-testing`

The implementation audit found and corrected: explicit keyboard/pointer resize affordances, visible
focus replacements, URL-backed query state on same-path history changes, inline loading/error/retry,
input name/autocomplete, an ellipsis placeholder, `aria-busy`, and drag-time text-selection
suppression. Button-driven navigation remains the established application-shell command contract;
no material-domain link was converted to an ungoverned URL.

## Official reference comparison

Every image in `docs/00-research/images/gui-reference/README.md` and the five curated gallery images
was opened directly. The closest structural references for this bounded slice were:

- `granta-profile.png` and `granta-contents-tree.png`: stable Database/Profile/Table/Folder/Record
  navigator, compact hierarchy, independent scrolling;
- `granta-list-results.png`: dense rows, sortable/resizable columns, restrained result header;
- `granta-datasheet-embedded.png` and `granta-datasheet-full.png`: result-to-datasheet continuity,
  flat compact property sections, no nested card stack;
- `granta-record-links-1.png` and `granta-record-links-2.png`: related-record labels and exact record
  navigation beside the datasheet.

Modeler, solver-card preview, and Administration references were reviewed for regression only and
remain owned by later DUI slices. The resulting topology is
`Application/Command → Navigator | dominant Results or Datasheet | optional Context → Status`.

## Live user-flow proof

The rebuilt Docker demo and real synthetic APIs were exercised in the in-app Chromium browser:

1. `/materials` loaded 3 governed Materials and selected one without remounting the page.
2. Clicking DP780 updated Context; pressing Enter on its result row opened
   `/materials/0e916d48-2ab1-42be-ac23-4ec967b26e76` with the Browse Tree still mounted.
3. The Related button opened exact Record revision
   `/materials/records/8ee15167-06fb-4a95-bc94-129324ab9ab5/revisions/73321f29-dbea-4a17-b52d-eedc6732a5b7`.
4. `← Results` restored the DP780 selection. A second run submitted `q=DP780`, opened by keyboard,
   then used browser Back; URL, search box and selected row all restored.
5. `Resize filters` moved from 248 px to the 320 px limit with the keyboard and remained 319 px
   after reload. Pointer drag moved Context from 280 px to 305 px. Column separators support the
   same pointer/Arrow-key contract.
6. Browser error logs were checked after the final container restart; application interactions and
   exact-revision navigation completed without a runtime error.

## Responsive measurements

| Metric | 1366×768 | 1440×900 | 1920×1080 |
| --- | ---: | ---: | ---: |
| Application + command bars | 84 px | 84 px | 84 px |
| Workspace outer margin | 8 px | 8 px | 8 px |
| Navigator default | 244 px | 248 px | 280 px |
| Main region | 1,094 px | 884 px | 1,312 px |
| Context default | collapsed | 280 px | 300 px |
| Normal pane padding | 8 px | 8 px | 8 px |
| Result row height | 34 px | 34 px | 34 px |
| Body/data font | 13–14 px | 13–14 px | 13–14 px |
| Filled primary commands in result context | 1 | 1 | 1 |
| Nested persistent cards | 0 | 0 | 0 |
| Page horizontal overflow | 0 px | 0 px | 0 px |

At 1440, the Material datasheet center is 884 px. Its overview uses a measured 529/300 px split and
the curve/state subregion collapses to one column, eliminating the overlap found in the first live
review. Navigator, main content, and Context each retain independent scrolling.

## Visual acceptance

The authoritative 16-criterion matrix scored each route from 0–2. Materials Results scored `30/32`
(`93.75/100`), Material Datasheet `29/32` (`90.63/100`), and exact Record revision `29/32`
(`90.63/100`). No topology, dominant-area, divider grammar, density, selection, keyboard,
horizontal-overflow, nested-card, or legacy-selector hard gate scored 0.

The two one-point deductions on datasheets are restrained hierarchy/copy opportunities that do not
change topology. The active Materials route uses none of `page-stack`, `page-heading`, `content-card`,
`module-material-card`, `hero-actions`, `eyebrow`, `status-badge`, or `count-chip`. Remaining matches
in `layout.css` are scoped to Modeling, Administration, governed import, Test JSON, or legacy
Database routes and are outside DUI-02.

## Captures

- `docs/15-demo/images/desktop-engineering-ui/dui-02/materials-results-1366x768.png`
- `docs/15-demo/images/desktop-engineering-ui/dui-02/materials-results-1440x900.png`
- `docs/15-demo/images/desktop-engineering-ui/dui-02/materials-results-1920x1080.png`
- `docs/15-demo/images/desktop-engineering-ui/dui-02/material-datasheet-1440x900.png`
- `docs/15-demo/images/desktop-engineering-ui/dui-02/exact-record-revision-1440x900.png`

The current user-guide copies are registered in `docs/user-guide/screenshot-manifest.yaml`.

## Automated regression

- Web unit/integration: 40 files, 100 tests passed.
- Web production build: passed; the largest entry remained below its 300 kB budget and the
  Material Library chunk remained below its 120 kB budget.
- Guided Playwright demo: 3 scenarios passed, including the DP780 result → datasheet → exact
  revision → browser-back restoration flow.
- Backend/default suite: 789 passed, 76 PostgreSQL-only tests skipped as expected.
- PostgreSQL integration profile: 76 passed, 123 non-PostgreSQL tests deselected.
- Contract lint, OpenAPI compatibility, architecture boundary, demo fixture verification,
  user-guide validation, and worktree documentation-impact validation: passed.
- `npm audit --audit-level=high`: 0 vulnerabilities.

Repository-wide Ruff and mypy remain red on pre-existing, untouched files: Ruff reports findings
in existing documentation utilities plus the newly installed upstream `webapp-testing` example
scripts; mypy reports three existing errors in
`backend/src/cmp/modules/datasets/domain/governed_tabular.py`. No Python production source changed
in DUI-02, and the complete functional/contract suites above pass.
