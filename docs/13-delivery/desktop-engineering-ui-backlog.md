# Desktop Engineering UI Delivery Backlog

Status: active program; DUI-01~06 are complete, including PR #124/DUI-06 merged on 2026-07-24.
UXC-01~06 are corrective work required before DUI-07~09, which remain pending. Issue #119 remains
an explicit opt-in independent-review gate; automatic LLM review remains disabled.

Authoritative interaction contract: `docs/01-product/desktop-engineering-ui-product-spec.md`

## Program goal

Move the current Search-first web implementation from a visually inconsistent SaaS-style surface to a coherent desktop engineering workspace while preserving all database, modeling, revision/provenance and solver-mapping behavior.

The program is complete only when the actual task flows work in the new workspace grammar. A typography or CSS-only pass is not sufficient.

## DUI-01 — Application shell, command bar and status bar — P0

Implementation status: complete. PR #112 was approved and merged on 2026-07-22. Browser verification
is recorded in `docs/17-evidence/reports/dui-01-application-shell.md`.

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

Implementation status: complete. PR #114 was approved and merged as `5fe6d63` on 2026-07-22. The
refinement removes duplicate Search/Browse/Subsets controls, moves pane visibility to the dividers,
and gates captures on completed async enrichment. Live flow, responsive measurements, external-skill
audits and reference scoring are recorded in
`docs/17-evidence/reports/dui-02-materials-workspace.md`.

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

Implementation status: complete. PR #122 was merged as `436ad76` on 2026-07-23. The bounded
implementation and reference comparison are recorded in
[`dui-03-contextual-solver-card-delivery.md`](../17-evidence/reports/dui-03-contextual-solver-card-delivery.md).
It reuses existing Solver Card and Neutral Solver Card contracts; no backend, database or OpenAPI
change is included.

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

Implementation status: complete. PR #115 was approved and merged as `f89cc50` on 2026-07-22. Live
flow, pane measurements, state continuity, reference scoring and captures are
recorded in `docs/17-evidence/reports/dui-04-modeling-workspace.md`.

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

Implementation status: complete. PR #123 was merged as `117551a` on 2026-07-23. The bounded change
reuses T-41, T-52 and T-54 contracts and adds no production test standard, vendor parser, processing
algorithm or persistence schema.

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

Implementation status: complete. PR #124 merged the bounded implementation on 2026-07-24. The
implementation and measurements are recorded in
[`dui-06-fit-export-decision.md`](../17-evidence/reports/dui-06-fit-export-decision.md). It reuses
the existing synthetic Processing Output, Material Model IR, Neutral Material, mapping-report and
solver-card contracts; it does not select a production material model, solver policy or threshold.

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

1. DUI-01 shell/status foundation — complete in PR #112;
2. DUI-02 Materials split workspace — complete in PR #114;
3. DUI-04 Modeling session shell — complete in PR #115 by explicit product-owner ordering;
4. DUI-03 card delivery — complete in PR #122;
5. DUI-05 Data/Process — complete in PR #123;
6. DUI-06 Fit/Export — complete in PR #124;
7. UXC-00 documentation convergence and latest-main baseline — complete only with current captures;
8. UXC-01 Materials query/facet/result correctness — partial vertical slice complete: server-scoped
   text/class/sort/page rows and total, Material class facet/page metadata, no row enrichment N+1, exact
   supported-family Modeling pin, and current viewport evidence. Provider/evidence-source,
   validation/solver readiness and condition-aware property/Yield projections remain blocked by
   absent governed server contracts;
9. UXC-02 Modeling session state and stage shell — complete: v3 clearable reducer/event persistence,
   v2 migration, exact Material/State/Test Data pins, invalidation dispositions, Data-first new
   session, resume view state, six-stage status shell, and fail-closed Export prerequisite surface.
   Validate and Review/Release remain explicit blocked placeholders pending UXC-05; API Processing
   Output does not expose a Material/State pin, so the normal Export surface does not claim an
   independent cross-resource provenance proof and blocks absent current session pins;
10. UXC-03 Data and Process domain components — complete in PR #128 with raw source/mapping/provenance evidence, Process curve rail, contextual workup, deterministic tests and current viewport evidence;
11. UXC-04 explicit Fit decision and model identity — implemented in the UXC-04 branch: null-by-default selection, separate recommendation and engineer selection, typed immutable Fit Decision, single/blend identity, actual server Prony term identity and exact downstream provenance. Final status requires current captures, reviewer sign-off and PR merge;
12. UXC-05 Validate, Review and Release — current: normal Modeling can pin existing synthetic
    reference validation inputs and run/evaluate the supported non-production OpenRadioss path only
    when selection evidence plus session IR/Card exact revisions match. Common Processing Output
    candidates without that adapter are explicitly `Not supported`. Review
    package production and release-policy input remain explicit `Not configured`; Submit, Request changes,
    Approve and Release are separately represented and never infer a state from Fit or Validation;
13. UXC-06 exact Export and traceable delivery — UXC-06A fail-closed prerequisites and UXC-06B
    governed exact-source projection complete; persistent delivery remains blocked on the
    pre-delivery-preview/receipt contract below;
14. DUI-07 Administration — pending;
15. DUI-08 Activity — pending;
16. DUI-09 Storybook and final legacy cleanup — pending.

## UXC corrective sequence

UXC-00 is the documentation-only convergence baseline. UXC-01~06 retain the completed DUI-01~06
surfaces while correcting query truth, session invalidation, explicit engineer decisions, validation/
review/release, and exact delivery. No UXC task chooses a production material model, solver policy,
validation threshold, or approval policy without the corresponding domain decision.

### UXC-01 current constraint

The Material query now owns rows, total, sort and pagination in the server response and does not
filter the first 50 client-side or call detail/graph/card APIs per row. The current Material domain
does not project provider, evidence source, validation availability, solver readiness, form/condition
or a condition-aware quantity definition. These remain distinct unavailable states; `Yield` is hidden
instead of inferred from the first property set. A later UXC-01 follow-up needs the governing query
projection (definition, condition, unit and source revision) before a metal Yield range can be added.

### UXC-02 current constraint

The browser-local session reducer can safely clear or mark current pointers stale/regenerate, and
the common Modeling shell no longer auto-selects a first Test Data revision after a new session or
Material/State context change. Current Export requires a session-local exact Material, Material State,
Test Data and Processing Output pin; it never renders a global/legacy output fallback. The existing
Processing Output API projects exact source Test Data and Mapping Profile but not Material or Material
State identity. UXC-02 records that gap and does not represent its guard as a completed cross-resource
provenance validation; UXC-06 needs an API-supported proof before delivery can claim it.

### UXC-06 current constraint

Normal Modeling Export now renders the exact-source checklist and required
`Processing Output → Material Model IR → Neutral → target preflight → native card` lineage, but it
does not render native artifact, adapter, Preview, or Deliver controls while any prerequisite is
absent. The browser compares current session pins only with the server projection; it never creates
proof. Existing Materials CAE Card reuse remains a separate released-card route.

UXC-06B adds the contracts-first source proof. A governed local-file save submits exact Material,
Material State and Test Run revisions; the server verifies Test Run→Specimen→State→Material through
Catalog/Testing application services and stores the projection in immutable Canonical Test Data
content. Common Processing Output copies it from the exact source revision. Historical and JSON-only
rows remain `null`, readable and blocked without backfill. Changing or omitting the source creates a
new unqualified revision rather than mutating history.

The remaining UXC-06C constraint is target delivery. Existing card `/preview` resources read
already-persisted immutable cards and are not an ephemeral pre-delivery producer. Until a separate
target preview, Deliver command and immutable receipt exist, `exportArtifact`, Activity delivery and
Material CAE Card links are not written from Normal Modeling.

Do not merge multiple P0 slices into a single unreviewable frontend rewrite. Each PR must include the actual user task, before/after screenshots and state-continuity evidence.
