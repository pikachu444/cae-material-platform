# Desktop Engineering UI Delivery Backlog

Status: proposed execution order for the desktop engineering UI program

Authoritative interaction contract: `docs/01-product/desktop-engineering-ui-product-spec.md`

## Program goal

Move the current Search-first web implementation from a visually inconsistent SaaS-style surface to a coherent desktop engineering workspace while preserving all database, modeling, revision/provenance and solver-mapping behavior.

The program is complete only when the actual task flows work in the new workspace grammar. A typography or CSS-only pass is not sufficient.

## DUI-01 — Application shell, command bar and status bar — P0

Implementation status: complete. PR #112 was approved and merged on 2026-07-22. Browser verification
is recorded in `docs/15-demo/evidence/dui-01-application-shell.md`.

### User outcome

The user enters a compact engineering application rather than a branded web landing page.

### Scope

- reduce authenticated global bar to 44–48 px;
- remove product subtitle and authenticated hero sections;
- introduce a workspace command bar and application status bar;
- define command ownership and keyboard focus order;
- preserve Materials, Modeling and Activity navigation;
- show connectivity, active context, draft/review state and long-running job status in the status bar.

### Acceptance

- no authenticated route begins with a marketing/introductory hero;
- workspace starts within 88 px below the browser top, excluding browser chrome;
- `F6` cycles application bar, navigator/main/inspector and status regions;
- status bar reports selected object/session and warning/job state;
- all current routes still resolve.

## DUI-02 — Resizable Materials workspace and in-place datasheet — P0

Implementation status: implemented on 2026-07-22. Live flow, responsive measurements, external-skill
audits and reference scoring are recorded in
`docs/15-demo/evidence/dui-02-materials-workspace.md`.

### User outcome

Search, Browse Tree, results, datasheet and related context operate as one stable workspace.

### Scope

- resizable Navigator and Context panes;
- persisted pane sizes and collapsed state;
- independently scrollable panes;
- single-click row selection updates Context;
- Enter/double-click opens datasheet in the center region without removing Navigator;
- in-workspace back stack for results/datasheet/Related Record navigation;
- restore query, filters, sort, selection, scroll and pane state on back/forward.

### Acceptance

- 1366 px defaults Context closed before compressing the main grid;
- center region is at least 720 px when the viewport allows;
- selecting a result does not blank or remount the full page;
- exact Record links preserve revision context;
- Tree, Table, Attribute, Layout, Subset and Link Type behavior is unchanged;
- Playwright covers Search → Datasheet → Related Record → Back.

## DUI-03 — Contextual solver-card delivery — P0

### User outcome

A known Material can be assessed and downloaded without navigating through implementation objects.

### Scope

- Context pane chooses Download, Preview, Create Card or Start Modeling according to available evidence;
- native card preview uses a two-pane text/property-sheet workspace;
- exact mappings download directly;
- approximations are acknowledged adjacent to the warning;
- unsupported mappings expose the blocking field and disable generation;
- recent use/download is recorded in Activity.

### Acceptance

- direct native-card download is no more than three primary actions after search;
- exact mapping has no redundant confirmation dialog;
- no normal-path UUID/hash/Mapping Profile/Recipe input;
- missing-card states never show an inactive or misleading Download command;
- downloaded artifact and mapping report regressions remain unchanged.

## DUI-04 — Persistent Modeling session and task inspector — P0

### User outcome

Data, Process, Fit and Export feel like stages of one engineering session rather than separate pages.

### Scope

- persistent graph and curve/process navigator;
- optional docked Task Inspector;
- resizable panes with graph minimum width protection;
- draft/preview/committed/reviewed/exported session states;
- autosave non-numerical UI state;
- one unsaved-change decision on exit;
- stale revision conflict resolution;
- stage-specific command bar and status information.

### Acceptance

- stage switch does not remount the graph or lose selected curves/view;
- 1440 px Fit graph remains at least 70% of workspace width with Inspector open where possible;
- Preview and Committed output cannot be confused;
- interrupted session resumes from Activity with selected stage/curves/candidate;
- JSON editing is unnecessary for the normal upload-to-card path.

## DUI-05 — Data intake and processing workflow — P0

### User outcome

CSV/TSV/XLSX/JSON becomes usable curve data through a clear mapping and preview process.

### Scope

- Library source and local file source in one Data-stage chooser;
- worksheet/test-type/channel/unit detection;
- mapping data grid with uncertain/invalid rows highlighted;
- graph preview before confirmation;
- direct graph range/point commands in Process;
- processing preview and explicit commit.

### Acceptance

- valid detected mappings need no manual confirmation per field;
- uncertain mappings are the only items requiring attention;
- source and processed curves remain distinguishable;
- no hidden conversion, smoothing, resampling or exclusion;
- original/normalized unit evidence is preserved.

## DUI-06 — Fit and Export decision workflow — P0

### User outcome

Candidate comparison, model review and card export follow a visible decision chain.

### Scope

- compact candidate data grid;
- response/residual/tangent views in the same plot;
- observed/extrapolated boundary;
- optional parameter/bounds property sheet;
- selected-candidate reason;
- target solver/version/unit selection;
- mapping preflight, approximation acknowledgement, preview and download;
- save/link result to Material Library.

### Acceptance

- candidate status/error/applicability/warning are comparable without opening multiple cards;
- selected model and extrapolation domain remain visible in Export;
- unsupported mapping blocks output;
- generated card appears in the Material datasheet and search context;
- existing metal/polymer/elastomer calculations remain numerically unchanged.

## DUI-07 — Administration object navigator and property editor — P1

### User outcome

Administrators configure schema and links through compact data tools rather than a card gallery.

### Scope

- object navigator + list/data grid + property editor/preview;
- Table and Attribute Definition editing;
- unit/quantity/value semantics;
- Layout placement and real Record preview;
- Subset and Link Type editing;
- dirty state, field validation, Save and Publish commands.

### Acceptance

- complete Table → Attribute → Layout → Record preview flow;
- complete Link Type → Related Record navigation flow;
- draft changes do not silently publish;
- no schema-object card grid or large introductory blocks;
- migration-free configurable database behavior remains intact.

## DUI-08 — Activity resume and job attention model — P1

### User outcome

Activity answers “what needs my attention?” and resumes the exact working context.

### Scope

- recent Modeling sessions;
- review requests;
- failed/blocked jobs;
- recent downloads/releases;
- advanced Recipe/Batch/bulk diagnostics disclosure;
- exact resume links.

### Acceptance

- default view prioritizes user action, not technical job history;
- selecting an item returns to its exact Material/session/stage/revision;
- failed jobs include recovery commands;
- low-level attempts remain accessible under Advanced.

## DUI-09 — Component workbench and legacy CSS removal — P1

### User outcome

All routes use one visual and interaction grammar.

### Scope

- introduce Storybook;
- add stories for shell, command bar, split pane, Tree, data grid, property sheet, tabs, status bar, plot, inspector and card preview;
- move active routes off legacy `page-heading`, `content-card`, hero and module-card classes;
- remove or isolate unused legacy CSS;
- add component and screen visual regression.

### Acceptance

- no active user route depends on legacy card-heavy layout classes;
- Storybook covers default/hover/focus/selected/disabled/loading/warning/error states;
- Playwright detects unintended pane, typography, wrapping, overflow and plot-size changes;
- production bundle budget remains satisfied.

## Cross-program gates

Every slice must preserve:

- immutable raw/released artifacts;
- stable identity and exact revision distinction;
- original and normalized units and quantity semantics;
- retained outliers and scoped exclusions;
- provenance for derived entities;
- Material Model IR and solver mapping rules;
- authorization boundaries;
- current clean demo and native download verification.

## Recommended PR order

1. DUI-01 shell/status foundation;
2. DUI-02 Materials split workspace;
3. DUI-03 card delivery;
4. DUI-04 Modeling session shell;
5. DUI-05 Data/Process;
6. DUI-06 Fit/Export;
7. DUI-07 Administration;
8. DUI-08 Activity;
9. DUI-09 Storybook and final legacy cleanup.

Do not merge multiple P0 slices into a single unreviewable frontend rewrite. Each PR must include the actual user task, before/after screenshots and state-continuity evidence.
