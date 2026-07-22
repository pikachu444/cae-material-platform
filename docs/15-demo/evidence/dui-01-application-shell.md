# DUI-01 application shell evidence

Date: 2026-07-22

Requirement: DUI-01

Fixtures: deterministic synthetic local demo data only

## Outcome

The authenticated 61 px product header and route-level introductory headers were replaced by a
46 px application bar, a 38 px workspace command bar and a 24 px status bar. `Materials | Modeling |
Activity` remains global navigation. Administration remains role-gated in the user menu, and all
existing deep routes continue through the same router.

The shell does not alter database or engineering contracts. Database/Profile/Table/Folder/Record,
Table/Attribute/Layout/Subset/Link Type, exact revision/provenance, original and normalized units,
Material Model IR and exact/transformed/approximated/unsupported solver mappings remain mounted in
their existing workspaces.

## Reference comparison

| Directly inspected reference | Applied interaction principle | DUI-01 result |
| --- | --- | --- |
| `granta-mi-favourites-list.png` | Shallow global/command strips let dense rows start near the top; hierarchy uses dividers rather than cards. | Application + command bars total 84 px; Materials data starts at y=135 px after the compact query row. |
| `material-data-center-search-detail.png` | Search, result list and selected detail remain one continuous selection context. | Materials keeps 264/830/280 px navigator/result/context at 1440 px and publishes the selected Material/revision to status. |
| `material-data-center-cae-model.png` | Delivery commands remain adjacent to the selected engineering record. | Material Detail retains visible Preview and Download while record identity/revision also appears in status. |
| `material-modeler-curve-fitting.png` | Stage commands use a shallow strip and the plot consumes the remaining width. | Data/Process/Fit/Export moved to the command bar; the 1440 px plot region is 1186 px (86.2% of the 1376 px workspace). |
| `material-modeler-hyperelastic-fitting.jpg` | Session state and warnings remain persistent while advanced controls disclose separately. | selection, Test Data revision/stage, running calculation and warnings are persistent in the 24 px status bar. |

No logo, brand color, proprietary label or pixel-level commercial layout was copied.

## Before and after measurements

All values are CSS pixels from the same live in-app browser session. Raw measurements are stored in
`../images/desktop-engineering-ui/dui-01/before-measurements.json` and
`../images/desktop-engineering-ui/dui-01/after-measurements.json`.

| 1440×900 route | App bar before→after | Command/status before→after | First task data y before→after | Main region before→after |
| --- | ---: | ---: | ---: | ---: |
| Materials Search | 61→46 | 0/0→38/24 | 235.3→135 | results 830.1→830.1 |
| Browse Tree | 61→46 | 0/0→38/24 | 235.3→135 | tree 263; results 830.1 |
| Material Detail | 61→46 | 0/0→38/24 | tabs 237→136.4 | header 176→52.4 |
| Modeling Fit | 61→46 | 0/0→38/24 | workspace 270.2→196.8 | plot 1186→1186 |
| Activity | 61→46 | 0/0→38/24 | 189.6→84 | content 1377→1377 |
| Administration | 61→46 | 0/0→38/24 | 61→84 | content 1205→1205 |

The Materials and Modeling y values above include the compact query/context and active-task control
rows. The application workspace itself begins at y=84 on every route. At 1366, 1440 and 1920 the
document-level horizontal overflow was 0 px.

| Metric | 1366×768 | 1440×900 | 1920×1080 |
| --- | ---: | ---: | ---: |
| Menu + command height | 84 | 84 | 84 |
| Status height | 24 | 24 | 24 |
| Materials outer margin, each side | 24.2 | 25.5 | 33 |
| Materials navigator | 244 | 264 | 280 |
| Materials main result | 1058.6 | 830.1 | 1259 |
| Optional context | closed | 280 | 300 |
| Modeling curve explorer | 180.3 | 190.1 | 196 |
| Modeling plot region | 1124.3 | 1186 | 1645 |
| Page horizontal overflow | 0 | 0 | 0 |

At 1366 the optional Materials context closes, leaving 1058.6 px for results. Modeling settings are a
124 px shallow ribbon above the graph, not a permanent third column; the plot keeps 86.2% of the
workspace width at 1440.

## Copy and legacy shell reduction

- Across the six 1440×900 routes, introductory paragraphs before task data changed from `8→1`
  (`-7`). Buttons at least 36 px high before task data changed from `40→39`; this deliberately keeps
  task actions while moving seven route/mode commands into the compact 38 px command bar instead of
  claiming that every engineering action should disappear.
- Materials: introductory paragraphs before data `1→0`; data starts 103 px earlier after the final
  visually-hidden label adjustment.
- Material Detail: route header `176→52.4 px`; two introductory paragraphs before tabs removed.
- Modeling: 108.2 px route header and duplicate stage tabs removed; one 39.8 px context strip remains.
- Activity: 128.6 px introductory header removed; task content starts at y=84.
- Removed authenticated `.app-header`, `.app-shell`, `.modeling-app-header`,
  `.modeling-session-heading`, `.modeling-flow-nav` and `--ux-header-height` dependencies.
- Materials, Browse, Detail and Activity have zero visible `page-stack`, `page-heading`, `content-card`,
  `module-material-card`, `hero-actions`, `eyebrow`, `status-badge` and `count-chip` occurrences.
- Modeling method internals still contain `eyebrow`; Administration editors still contain legacy
  `content-card`, `eyebrow` and status classes. They are explicitly deferred to DUI-04 and DUI-07;
  their shell/header classes are migrated in DUI-01 and their panels remain flat in current CSS.

## Structural acceptance score

The 16 criteria in `docs/01-product/visual-acceptance-matrix.md` were scored 0–2. No hard gate is 0.

| Screen | Score | Partial criteria | Hard-gate result |
| --- | ---: | --- | --- |
| Materials Search | 30/32 | V-05 resize deferred to DUI-02; V-09 Search and selected-row action are separate contexts | pass |
| Browse Tree | 29/32 | V-05 resizing/datasheet adjacency deferred to DUI-02; Tree behavior itself is unchanged | pass |
| Material Detail | 30/32 | in-workspace navigator/back stack deferred to DUI-02 | pass |
| Modeling Fit | 29/32 | V-06/V-16 method-internal typography and legacy labels continue in DUI-04 | pass |
| Activity | 27/32 | work-queue data grid and attention model continue in DUI-08 | pass |
| Administration | 26/32 | object navigator/property editor and remaining editor classes continue in DUI-07 | pass |

## Screenshots

Before and after captures exist for all six routes at 1366×768, 1440×900 and 1920×1080 under
`../images/desktop-engineering-ui/dui-01/`. Current 1440×900 PNGs registered in the user-guide
manifest are under `../images/ux-redesign-v2/dui-01-*.png`.

| Route | Before | After |
| --- | --- | --- |
| Materials | [before](../images/desktop-engineering-ui/dui-01/before/materials-search-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/materials-search-1440x900.jpg) |
| Browse Tree | [before](../images/desktop-engineering-ui/dui-01/before/browse-tree-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/browse-tree-1440x900.jpg) |
| Material Detail | [before](../images/desktop-engineering-ui/dui-01/before/material-detail-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/material-detail-1440x900.jpg) |
| Modeling Fit | [before](../images/desktop-engineering-ui/dui-01/before/modeling-fit-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/modeling-fit-1440x900.jpg) |
| Activity | [before](../images/desktop-engineering-ui/dui-01/before/activity-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/activity-1440x900.jpg) |
| Administration | [before](../images/desktop-engineering-ui/dui-01/before/administration-1440x900.jpg) | [after](../images/desktop-engineering-ui/dui-01/after/administration-1440x900.jpg) |

## Verification and remaining work

- Live 1440×900 browser checks confirmed `Ctrl+K` focuses `Search materials`; F6 cycles status →
  application → commands → workspace; disabled Compare exposes `Select at least two material rows to
  compare.`; Browse Tree exposes one tree-search input; Data/Fit commands switch the Modeling task;
  all target routes render all three shell regions. Raw results are in
  `../images/desktop-engineering-ui/dui-01/browser-scenarios.json`.
- The six routes have 0 px document-level horizontal overflow at 1366, 1440 and 1920 px. The Docker
  clean demo reports healthy API/PostgreSQL services and completed migrate/seed/reference-plugin jobs.
- `npx vitest run --pool=threads --no-file-parallelism --maxWorkers=1`: 37 files, 95 tests passed.
- `npm run build --workspace @cmp/web`: TypeScript/Vite build and bundle budget passed; largest entry
  chunk 253,749 bytes against the 300,000-byte limit.
- `uv run pytest -q`: 788 passed, 76 PostgreSQL-DSN-dependent tests skipped.
- `uv run cmp-check-user-guide --root .`: 20 current guide documents, 23 captures, 3 navigation
  items and 188 classified Markdown files passed.
- `uv run cmp-check-doc-impact --root . --mode worktree`: passed.
- DUI-02 continues resizable Materials panes and in-place datasheet navigation. DUI-04 continues
  persistent Modeling state/inspector behavior. DUI-07 and DUI-08 migrate the remaining internal
  Administration and Activity work surfaces.
