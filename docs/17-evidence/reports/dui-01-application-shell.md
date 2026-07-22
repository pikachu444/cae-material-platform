# DUI-01 application shell evidence

Date: 2026-07-22

Requirement: DUI-01

Review state: **Draft PR #112; product-owner acceptance pending; DUI-02 blocked**

Fixtures: deterministic synthetic local demo data only

## Outcome and review rule

The authenticated 61 px web header and route-level introductory headers are replaced by a 46 px
application bar, a 38 px workspace command bar and a 24 px status bar. `Materials | Modeling |
Activity` remains the global navigation. Administration remains role-gated in the user menu. The
application and workspace commands are left aligned like a desktop tool frame rather than centred
like a SaaS site header.

This revision was compared directly with every image in
[`gui-reference`](../../00-research/images/gui-reference/README.md), not only the earlier UX gallery.
The structural scores below are a self-audit, not owner approval and not permission to start DUI-02.

The shell does not alter Database/Profile/Table/Folder/Record navigation,
Table/Attribute/Layout/Subset/Link Type configuration, exact-revision links, immutable revision and
provenance rules, original/normalised units, Material Model IR, or solver mapping classifications.

## Problem, command placement and implementation inventory

Before DUI-01, authenticated routes began with a 61 px web header and repeated route title,
description and local navigation. Materials repeated Search/Browse/Subsets in two places; Material
Detail repeated its five datasheet tabs; Modeling repeated stage navigation and placed generic Open
data/Undo/Redo beside current-task commands. First task data therefore appeared as low as y=270.2.

The application bar now owns product identity, `Materials | Modeling | Activity` and the user menu.
The command bar owns only current-workspace commands: Search/Browse Tree/Subsets/Compare/New material,
Back to results, or Data/Process/Fit/Export. Activity and Administration expose their local commands
inside the workspace rather than duplicating them in the shell. The bottom status bar owns persistent
selection, revision/stage, job, warning and connection state.

Added in the original DUI-01 slice: `design/application-shell.tsx`, its test, and
`design/shell.css`. Revised in this reference pass: `app.tsx`, `material-library.tsx`,
`common-processing-workbench.tsx`, `configurable-catalog-admin.tsx`, shell/layout CSS and shell tests.
Removed or migrated: duplicate Detail/Modeling/Activity/Admin shell commands, left-pane mode tabs,
generic “Connected” state, and 169 lines of duplicate Modeling selectors from `styles.css` into the
canonical `design/layout.css` implementation.

## Direct official-reference inspection

### Granta MI reference set

| Reference opened | Relevant desktop grammar | DUI-01 application | Not yet implemented and owner |
| --- | --- | --- | --- |
| [`granta-profile.png`](../../00-research/images/gui-reference/granta-profile.png) | Profile is a persistent working context, not a landing-page card. | Database/Profile/Table remain in the Browse navigator and current selection/revision is persistent in status. | Rich profile switching is a Materials workspace task in DUI-02. |
| [`granta-contents-tree.png`](../../00-research/images/gui-reference/granta-contents-tree.png) | Compact disclosure rows, ordinary text and dense hierarchy. | Browse uses 12.5 px regular/medium labels, 26 px rows, one-line ellipsis, keyboard navigation and `Find in tree`; duplicate mode tabs were removed. | Split-pane resizing and larger data-volume validation belong to DUI-02. |
| [`granta-list-results.png`](../../00-research/images/gui-reference/granta-list-results.png) | Tree and record list share one program frame; selected row drives adjacent context. | At 1440 px the 248 px navigator, 879 px results and optional 280 px context are continuous divider-separated panes. Results use 34 px rows and six readable columns. | Column resize/sticky-column behaviour belongs to DUI-03. |
| [`granta-datasheet-embedded.png`](../../00-research/images/gui-reference/granta-datasheet-embedded.png) | Datasheet is adjacent to selection and organised by typographic sections. | Material Detail starts at y=84 and uses flat property rows and tabs; shell no longer repeats the five datasheet tabs. | Result-to-embedded-datasheet split behaviour belongs to DUI-02/03. |
| [`granta-datasheet-full.png`](../../00-research/images/gui-reference/granta-datasheet-full.png) | Full record identity is compact; data occupies the viewport. | Record identity, grade, release state and direct CAE actions fit in a 48.4 px strip; data tabs start at y=132.4. | Layout selector and denser property sheet belong to DUI-03. |
| [`granta-curves-view.png`](../../00-research/images/gui-reference/granta-curves-view.png) | Curve data is treated as a working view, not a decorative card. | Material curves remain a datasheet tab; Modeling places curve names in a narrow ordinary-text navigator beside a dominant graph. | Material Detail curve toolbar is DUI-03; graph tools are DUI-04/06. |
| [`granta-functional-edit.png`](../../00-research/images/gui-reference/granta-functional-edit.png) | Current edit controls remain near the data and advanced detail is disclosed. | Modeling step settings are a shallow graph-adjacent ribbon rather than a permanent third column. | Full operation editing/undo history is DUI-05. |
| [`granta-admin-schema-tool.png`](../../00-research/images/gui-reference/granta-admin-schema-tool.png) | Administration is a specialised desktop workspace. | The shared shell is compact and status publishes the actual selected Table/revision/loading/error state. | Admin editor topology is intentionally DUI-07. |
| [`granta-admin-tables.png`](../../00-research/images/gui-reference/granta-admin-tables.png) | Tables are managed in a dense list/tree with local commands. | Shell-level duplicated Overview/Database/Access commands were removed; the existing local admin navigation remains authoritative. | Dense Table/Attribute master-detail redesign is DUI-07. |
| [`granta-admin-layout.png`](../../00-research/images/gui-reference/granta-admin-layout.png) | Layout construction is local to the schema tool and preserves field ordering. | Existing Layout editor and domain behaviour are preserved without being promoted into the global command bar. | Layout editor visual redesign is DUI-07. |
| [`granta-record-links-datasheet.png`](../../00-research/images/gui-reference/granta-record-links-datasheet.png) | Links appear in the record/datasheet context. | Existing Related/Workflow/Evidence routes and exact revision status remain intact. | Embedded link browsing is DUI-03. |
| [`granta-record-links-edit.png`](../../00-research/images/gui-reference/granta-record-links-edit.png) | Link editing is a contextual record operation. | Link Type and exact-revision contracts were not flattened into shell commands or strings. | Link editing surface is DUI-07. |
| [`granta-record-links-explore.png`](../../00-research/images/gui-reference/granta-record-links-explore.png) | Relationship exploration is progressive, separate from primary discovery. | Relationship/provenance content remains in Evidence/Administration, not the first Materials viewport. | Relationship explorer is outside DUI-01 and scheduled with DUI-03/07. |

### Material Modeler reference set

| Reference opened | Relevant desktop grammar | DUI-01 application | Not yet implemented and owner |
| --- | --- | --- | --- |
| [`modeler-start-data.png`](../../00-research/images/gui-reference/modeler-start-data.png) | Current task, compact data navigator and work surface share one frame. | Data/Process/Fit/Export are the only Modeling command-bar stages; duplicate route header/stage tabs were removed. | Data ingestion details are DUI-04. |
| [`modeler-youngs-auto.png`](../../00-research/images/gui-reference/modeler-youngs-auto.png) | A small task control group supports a large graph. | Step controls use a 124 px horizontal ribbon and never form a third inspector column. | Automatic-selection behaviour is DUI-05. |
| [`modeler-youngs-manual.png`](../../00-research/images/gui-reference/modeler-youngs-manual.png) | Manual controls stay adjacent to the plotted response. | Current-step controls are graph-adjacent and can be disclosed; the graph remains 86.2–89.4% of the graph workspace width. | Direct point manipulation is DUI-05/06. |
| [`modeler-necking-point.png`](../../00-research/images/gui-reference/modeler-necking-point.png) | Curve selection uses compact ordinary text; graph is dominant. | Curve rows are 27 px, show `Curve 01` etc. as one-line normal strings, and keep exact IDs in the title instead of large unit blocks. | Domain-specific necking control is deliberately not chosen while the domain item is TBD. |
| [`modeler-fit-extrapolation.png`](../../00-research/images/gui-reference/modeler-fit-extrapolation.png) | Response, residual and extrapolation are graph modes with nearby controls. | Fit retains one persistent graph and publishes the active Test Data revision and last-operation state to status. | Full graph toolbar, residual/extrapolation interactions are DUI-06. |
| [`modeler-create-cae-card.png`](../../00-research/images/gui-reference/modeler-create-cae-card.png) | CAE creation is a visible current-task action, not buried navigation. | Export remains a first-level Modeling command; Material Detail keeps direct solver preview/download in the first viewport. | Export workflow refinements are DUI-06. |
| [`modeler-cae-card-details.png`](../../00-research/images/gui-reference/modeler-cae-card-details.png) | Native card detail and delivery are associated with the selected model. | Existing native preview/download and mapping contracts remain mounted; shell status keeps selection and revision context. | Rich mapping/detail inspector belongs to DUI-06. |

No logo, brand colour, proprietary product name, pixel coordinates or inferred proprietary workflow
was copied. What is copied deliberately is the program grammar: compact menu/command/status strips,
ordinary-text tree rows, continuous master-detail panes, data-first typography and graph dominance.

## Screen-by-screen review disposition

| DUI screen | References used | Applied in this PR | DUI-01 issue corrected after first review | Deferred with reason |
| --- | --- | --- | --- | --- |
| Materials Search | `granta-profile`, `granta-list-results`, `granta-datasheet-embedded` | Left-aligned shell; one Search/Browse/Subsets command set; filter/result/context continuity; 34 px data rows. | Removed duplicated left-pane mode tabs, centred web navigation, excess 16–24 px pane padding and nested property blocks. | Resizable panes and embedded datasheet are DUI-02/03 behaviours. |
| Browse Tree | `granta-contents-tree`, `granta-profile`, `granta-list-results` | 26 px ordinary-text rows, searchable tree, keyboard hierarchy, record selection linked to result/context. | Removed the second `Filters/Browse/Subsets` strip and restored tree as a persistent navigator rather than a feature card. | High-volume virtualisation and pane resizing are DUI-02. |
| Material Detail | `granta-datasheet-embedded`, `granta-datasheet-full`, `granta-curves-view`, record-link references | 48.4 px identity/action strip; one body-owned tab set; flat data rows; Preview/Download in first viewport. | Removed duplicate command-bar datasheet tabs and redundant shell title copy. | Property/curve/link work surface details are DUI-03. |
| Modeling Fit | all seven Modeler images plus `granta-functional-edit` | 184–200 px curve/process rail, 27 px ordinary-text curve rows, 124 px settings ribbon, 86.2–89.4% graph share. | Removed redundant Open data/Undo/Redo shell commands, oversized curve labels, card framing and duplicated stage navigation. | Stateful operations are DUI-04/05; graph toolbar and export detail are DUI-06. |
| Activity | `granta-list-results` only for density; no official Activity analogue exists in the supplied set | One compact shell and flat 56.1 px activity rows; no repeated shell commands; actual no-job status. | Removed duplicate cross-workspace commands and decorative “jobs ready” status. | Queue hierarchy and job actions are DUI-08; claiming closer official parity would be unsupported. |
| Administration | `granta-admin-schema-tool`, `granta-admin-tables`, `granta-admin-layout`, link-edit references | Compact shared shell; local admin navigation owns commands; actual Table/revision/save/error status. | Removed global/local command duplication and generic shell status. | Internal card/form grammar remains visibly legacy and is explicitly DUI-07. |

## Before/after measurements

The immutable initial DUI implementation baseline is commit `8990171`; its `before/` images preserve
the pre-DUI screen. Raw current values are in
[`after-measurements.json`](../images/desktop-engineering-ui/dui-01/after-measurements.json) and
browser interaction results are in
[`browser-scenarios.json`](../images/desktop-engineering-ui/dui-01/browser-scenarios.json).

| 1440×900 screen | First task data y before→after | Current navigator / main / context width | Current row or key strip | Horizontal overflow |
| --- | ---: | ---: | ---: | ---: |
| Materials Search | 235.3→131 | 248 / 879 / 280 | result row 34 | 0 |
| Browse Tree | 235.3→131 | 248 / 879 / 280 | tree row 26 | 0 |
| Material Detail | 237→84 | — / 1409 / — | identity 48.4; tabs start 132.4 | 0 |
| Modeling Fit | 270.2→84 | 190.1 / 1218.9 / none | curve row 27; settings 124 | 0 |
| Activity | 189.6→84 | — / 1409 / — | first activity row 56.1 | 0 |
| Administration | 61→84 | 220 / 1205 / none | shell starts at 84 | 0 |

The Administration y value increases because the old page began directly below a 61 px header; the
new 84 px total contains both an application and a local command strip and removes route-level shell
duplication. Internal Administration density is not claimed as complete.

| Viewport | Materials navigator / result / context | Modeling navigator / graph | Graph share | Outer margin left/right |
| --- | ---: | ---: | ---: | ---: |
| 1366×768 | 244 / 1089 / closed | 184 / 1151 | 86.2% | 8 / 23 |
| 1440×900 | 248 / 879 / 280 | 190.1 / 1218.9 | 86.5% | 8 / 23 |
| 1920×1080 | 280 / 1307 / 300 | 200 / 1689 | 89.4% | 8 / 23 |

The 15 px difference on the right is the browser scrollbar. App/command/status heights are exactly
46/38/24 px at all three viewports. Materials table headers visible without document overflow are
Compare, Material, Family, Source, Yield and CAE cards. Long material and curve names remain one line
with ellipsis/title instead of wrapping every few characters.

## Typography, surfaces and legacy CSS migration

- Command labels are 12.5 px; tree/curve metadata are 12.5 px regular/medium; result data are 14 px;
  browser body remains 16 px. Page titles are compact command-strip labels, not hero typography.
- Materials and Modeling use 8 px application margins. Pane hierarchy uses alignment, whitespace and
  1 px dividers before backgrounds, borders, radii or shadows.
- Materials has no visible nested card, page-heading or content-card structure. Detail properties and
  Modeling statistics are flat divider rows.
- Modeling shell/grid/rail/plot selectors were migrated from the 169-line duplicate legacy block in
  `styles.css` to `design/layout.css`; this is not an appended override layer.
- Activity shell rows were flattened. Administration still exposes three internal `content-card`
  instances and four internal eyebrow labels; they are evidence for DUI-07, not hidden by a false
  DUI-01 completion claim.

## Status bar semantics

The 24 px status bar is not decorative:

- Materials publishes selected Material/code, `r1 · draft`, job count, warnings and API state.
- Material Detail publishes the loaded record and revision rather than the shell placeholder.
- Modeling publishes selected Test Data, active `fit` stage and `Last operation completed`.
- Administration publishes selected Table, governed configuration revision, validation/loading/save
  state and API availability.
- Browser offline is `Offline`; an API failure while the browser remains online is
  `Service unavailable`; healthy service state is `Online`.

## Structural similarity self-audit

This rubric judges reference structure, not colour similarity. A score does not close the task.

| Screen | Structure /20 | Density /20 | Data dominance /20 | Command grammar /20 | Progressive disclosure /20 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Materials Search | 19 | 18 | 18 | 18 | 18 | 91 |
| Browse Tree | 19 | 19 | 18 | 18 | 18 | 92 |
| Material Detail | 18 | 18 | 18 | 18 | 18 | 90 |
| Modeling Fit | 18 | 18 | 19 | 17 | 17 | 89 |
| Activity shell | 17 | 18 | 17 | 17 | 17 | 86 |
| Administration shell | 17 | 17 | 17 | 18 | 18 | 87 |

No screen has a topology, dominant-area or nested-card hard-gate failure in the **DUI-01 shell
scope**. The full Administration screen still has legacy internal cards and is not accepted as a
DUI-07 result. Product-owner review remains the completion gate.

## Screenshots

Each link is a new live-browser capture from the same Docker demo after the reference correction.

| Screen | 1366×768 after | 1440×900 before → after | 1920×1080 after |
| --- | --- | --- | --- |
| Materials | [after](../images/desktop-engineering-ui/dui-01/after/materials-search-1366x768.jpg) | [before](../images/desktop-engineering-ui/dui-01/before/materials-search-1440x900.jpg) → [after](../images/desktop-engineering-ui/dui-01/after/materials-search-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/materials-search-1920x1080.jpg) |
| Browse Tree | [after](../images/desktop-engineering-ui/dui-01/after/browse-tree-1366x768.jpg) | [before](../images/desktop-engineering-ui/dui-01/before/browse-tree-1440x900.jpg) → [after](../images/desktop-engineering-ui/dui-01/after/browse-tree-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/browse-tree-1920x1080.jpg) |
| Material Detail | [after](../images/desktop-engineering-ui/dui-01/after/material-detail-1366x768.jpg) | [before](../images/desktop-engineering-ui/dui-01/before/material-detail-1440x900.jpg) → [after](../images/desktop-engineering-ui/dui-01/after/material-detail-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/material-detail-1920x1080.jpg) |
| Modeling Fit | [after](../images/desktop-engineering-ui/dui-01/after/modeling-fit-1366x768.jpg) | [before](../images/desktop-engineering-ui/dui-01/before/modeling-fit-1440x900.jpg) → [after](../images/desktop-engineering-ui/dui-01/after/modeling-fit-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/modeling-fit-1920x1080.jpg) |
| Activity | [after](../images/desktop-engineering-ui/dui-01/after/activity-1366x768.jpg) | [before](../images/desktop-engineering-ui/dui-01/before/activity-1440x900.jpg) → [after](../images/desktop-engineering-ui/dui-01/after/activity-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/activity-1920x1080.jpg) |
| Administration | [after](../images/desktop-engineering-ui/dui-01/after/administration-1366x768.jpg) | [before](../images/desktop-engineering-ui/dui-01/before/administration-1440x900.jpg) → [after](../images/desktop-engineering-ui/dui-01/after/administration-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/administration-1920x1080.jpg) |

## Verification and remaining work

- Live 1440×900 browser: `Ctrl+K` focuses `Search materials`; F6 cycles status → application →
  commands → workspace; disabled Compare exposes its reason; Browse exposes one `Find in tree`
  textbox and an eight-level selected Record path; Material Detail exposes OpenRadioss preview and
  `.rad` download; Fit retains exactly one graph; all target routes have 0 px document overflow.
- Web unit/integration: 37 files, 96 tests passed, including offline/restored and API-degraded status.
- TypeScript/Vite/bundle build passed; largest entry chunk 252,871 bytes against 300,000 bytes.
- Backend regression: 788 passed; 76 PostgreSQL-DSN-dependent cases skipped as designed.
- Documentation gates: user-guide check passed for 20 guides, 23 captures, 3 navigation items and
  188 classified Markdown files; documentation-impact check passed for 70 changed files and 12
  visual sources.
- Docker demo: API and PostgreSQL healthy; web, worker and telemetry collector running during the
  final browser session.
- DUI-02 remains blocked until product-owner acceptance of this Draft. It will own resizable Materials
  panes and in-place datasheet navigation. DUI-04/05/06 own Modeling internals and graph tools;
  DUI-07 owns Administration internals; DUI-08 owns Activity internals.
