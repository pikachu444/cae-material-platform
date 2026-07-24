# Desktop Engineering UI Skill

Use this skill for any task that changes the CAE Material Platform frontend layout, navigation, typography, CSS, components, screenshots or visual acceptance.

## Authoritative inputs

Read before editing:

1. `AGENTS.md`
2. `docs/01-product/desktop-engineering-ui-product-spec.md`
3. `docs/01-product/desktop-engineering-ui-tooling.md`
4. `docs/01-product/visual-acceptance-matrix.md`
5. `docs/00-research/ux-reference-gallery/README.md`
6. `docs/00-research/images/gui-reference/README.md` and every relevant local image in that manifest
7. the relevant screen section in `docs/01-product/desktop-engineering-ui-spec.md`
8. current route entries in `docs/user-guide/screenshot-manifest.yaml` and their registered PNGs in
   `docs/user-guide/images/current/` (historical screenshots under `docs/17-evidence` are not the
   current product baseline)

## Objective

Build a browser-delivered desktop CAE engineering application. Do not produce a marketing site, content portal or generic card-based SaaS dashboard.

## Required workflow

### 1. Inspect before changing

- open the current route at 1366×768 and 1440×900;
- inspect relevant reference images directly;
- compare against the detailed official GUI references, not only the curated gallery descriptions;
- identify the dominant user task;
- record current header, pane, padding, font, row, plot and button measurements;
- identify legacy classes and components used by the route.

### 2. Apply the screen blueprint

Use the exact workspace blueprint in `desktop-engineering-ui-spec.md`.

Do not invent a new page topology when an approved blueprint exists.

### 3. Preserve domain capabilities

Never remove or weaken:

- Database/Profile/Table/Folder/Record hierarchy;
- Table, Attribute Definition, Layout, Subset and Link Type configuration;
- typed forward/reverse links and exact revisions;
- original/normalized units and quantity semantics;
- revision/provenance;
- processing/calibration engines;
- Neutral Material and solver mapping states;
- native card preview/download.

Simplify the facade, not the contracts.

### 4. Desktop grammar rules

- use menu bar, command bar, split panes, data grid, property sheet, tab strip, inspector and status bar;
- use flat panes and dividers;
- use compact rows and controls;
- keep one filled primary command per task;
- update selection in place rather than creating a new dashboard page;
- keep the engineering plot persistent through Modeling tasks;
- use context actions for row-specific commands;
- use Advanced/Evidence for technical identifiers.

### 5. Prohibited patterns

Do not add or retain on active routes:

- hero sections;
- marketing copy;
- card grids for normal navigation;
- nested persistent cards;
- repeated eyebrow labels;
- large explanatory text blocks;
- pill badges for ordinary metadata;
- rounded panels and shadows throughout the workspace;
- a 60 px brand-centric header;
- `max-width` centered application shells;
- full-size buttons for every secondary command.

### 6. Component-first implementation

Before page changes, identify the required primitives:

- ApplicationShell
- MenuBar
- CommandBar
- SplitPane
- NavigatorTree
- DataGrid
- PropertySheet
- TabStrip
- PlotFrame
- InspectorPanel
- StatusBar

Reuse or create primitives rather than writing route-specific styling patches.

### 7. Legacy CSS control

- list all legacy selectors used by the route;
- move canonical styling into `apps/web/src/design/`;
- avoid adding another override layer;
- delete unused selectors after route migration;
- fail the task if a migrated route still depends on `.page-stack`, `.page-heading`, `.content-card` or task-card grids without an explicit approved exception.

### 8. Verification

Required for every visual PR:

- current and target screenshots at required viewports;
- measurement table for header height, outer margin, pane widths, padding, row height and font sizes;
- Playwright task scenario;
- keyboard navigation check;
- no page-level horizontal overflow;
- legacy selector report;
- reference comparison using the visual acceptance matrix;
- per-screen evidence naming the directly opened reference, applied principle, missing element,
  current-task correction and reason for every deferral;
- documentation and screenshot manifest update.

## Completion language

Do not claim `modern`, `polished`, `enterprise-grade` or `reference-like` without measurements and screenshots.

Report:

1. user task improved;
2. blueprint applied;
3. components changed;
4. legacy patterns removed;
5. measurements before/after;
6. screenshots;
7. tests;
8. remaining exceptions.
