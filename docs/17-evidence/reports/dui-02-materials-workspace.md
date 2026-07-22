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

Draft PR #114 review then removed the repeated Navigator Search/Browse/Subsets tab row. The command
bar is now the only mode hierarchy, while a query submit is labeled `Find`. The 30 px
Hide/Show control row was removed; 15×26 px buttons sit on the 5 px pane dividers. Sort state moved
from the header's inner button to the semantic `th[aria-sort]`.

## Official reference comparison

Every image in `docs/00-research/images/gui-reference/README.md` and the five curated gallery images
was opened directly. The closest structural references for this bounded slice were:

- `granta-profile.png` and `granta-contents-tree.png`: stable Database/Profile/Table/Folder/Record
  navigator, compact hierarchy, independent scrolling;
- `granta-list-results.png`: dense rows, sortable/resizable columns, restrained result header;
- `granta-datasheet-embedded.png` and `granta-datasheet-full.png`: result-to-datasheet continuity,
  flat compact property sections, no nested card stack;
- `granta-record-links-datasheet.png`, `granta-record-links-explore.png`, and
  `granta-record-links-edit.png`: related-record labels and exact record navigation beside the
  datasheet.

The review comparison changed three measurable choices. Like `granta-profile.png`, mode selection is
owned by one upper control level and the Navigator contains only the selected tool. Like
`granta-list-results.png`, column headers own sorting and resize affordances, result rows are 32 px,
and no secondary toolbar separates the query from the grid. Like `granta-datasheet-embedded.png`,
thin dividers carry compact pane controls and the dominant center grows before either side pane.

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
5. The command bar changed Search → Browse Tree → Search with exactly one mode control at each step;
   the active state and URL mode remained synchronized.
6. Divider controls collapsed Context from 264 px to 0 and expanded it back to 264 px. Pointer and
   Arrow-key resizing remain available on the same dividers and on column separators.
7. Every result capture waited for `aria-busy=false`, 3 result rows, 0 `Checking…` rows, and 0 px
   horizontal overflow.
8. Browser error logs were checked after the final container restart; application interactions and
   exact-revision navigation completed without a runtime error.

## Responsive measurements

| Metric | 1366×768 | 1440×900 | 1920×1080 |
| --- | ---: | ---: | ---: |
| Application + command bars | 84 px | 84 px | 84 px |
| Workspace outer margin | 8 px | 8 px | 8 px |
| Navigator default | 232 px | 240 px | 272 px |
| Main region | 1,106 px | 908 px | 1,332 px |
| Context default | collapsed | 264 px | 288 px |
| Normal pane padding | 8 px | 8 px | 8 px |
| Result row height | 32 px | 32 px | 32 px |
| Dedicated pane-control row | 0 px | 0 px | 0 px |
| Mode-control locations | 1 | 1 | 1 |
| `Checking…` rows at capture | 0 | 0 | 0 |
| Body/data font | 13–14 px | 13–14 px | 13–14 px |
| Filled primary commands in result context | 1 | 1 | 1 |
| Nested persistent cards | 0 | 0 | 0 |
| Page horizontal overflow | 0 px | 0 px | 0 px |

At 1440, the Material datasheet center is 908 px, 24 px wider than the initial Draft PR capture. At
1920 the center receives 70.4% of pane content width; Navigator and Context stay compact at 14.4%
and 15.2%. At 1366 the collapsed Context gives the center 82.7% of pane content width. Navigator,
main content, and Context each retain independent scrolling.

## Visual acceptance

The authoritative 16-criterion matrix was rerun after the PR review. Materials Results scored
`31/32` (`96.88/100`), Material Datasheet `30/32` (`93.75/100`), and exact Record revision `30/32`
(`93.75/100`). No topology, dominant-area, divider grammar, density, selection, keyboard,
horizontal-overflow, nested-card, or legacy-selector hard gate scored 0.

The remaining one-point deductions are restrained copy/disclosure opportunities that do not change
topology. The active Materials route uses none of `page-stack`, `page-heading`, `content-card`,
`module-material-card`, `hero-actions`, `eyebrow`, `status-badge`, or `count-chip`. Remaining matches
in `layout.css` are scoped to Modeling, Administration, governed import, Test JSON, or legacy
Database routes and are outside DUI-02.

## Captures

- `docs/17-evidence/images/desktop-engineering-ui/dui-02/materials-results-1366x768.png`
- `docs/17-evidence/images/desktop-engineering-ui/dui-02/materials-results-1440x900.png`
- `docs/17-evidence/images/desktop-engineering-ui/dui-02/materials-results-1920x1080.png`
- `docs/17-evidence/images/desktop-engineering-ui/dui-02/material-datasheet-1440x900.png`
- `docs/17-evidence/images/desktop-engineering-ui/dui-02/exact-record-revision-1440x900.png`

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
