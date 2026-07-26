# Desktop Engineering UI Specification

Status: authoritative implementation specification

## Canonical visible-field contract

This document is the single source for component-level field behavior. Each visible engineering
component or field must record: `purpose` (the user decision), `placement` (why it is adjacent to
its evidence), `visible_when` (family, workflow, permission and data state), `source` (including
revision, unit and condition), `requires`, `invalidates`, `states`, and `error_recovery`. The
implementation may add `action_output`, validation, and forbidden representations where needed.

Use this contract as follows: Materials search scope, facets and result count share a server-scoped
query source; a condition-aware Yield control is visible only for compatible metal results. Modeling
recommendations, explicit engineer selections, saved snapshots, validation, review, release and
delivery are separate states. An upstream input change clears downstream *current pointers* and
marks UI state stale, but never rewrites immutable revisions. In a blocked or error state, preserve
the source, selected curves/candidate and plot context, name the unmet requirement, and offer the
next safe recovery action. UUIDs, hashes, raw JSON and plugin keys remain Advanced/Evidence fields.

## Canonical component registry

This authoritative annex retains the component-specific contract. Each compact row states
**purpose/placement**; **visible when, source, requires**; **output, state, invalidates, recovery**.
`Target` is pending work, not a claim about the current product.

| Components | Contract | Not allowed / status |
| --- | --- | --- |
| G-01 navigation; G-02 identity header | Move among Materials/Modeling/Activity in the shell; show human Material/session name, form/condition, version and state from exact context. | Internal module hub, UUID/hash as title, duplicated headings; current. |
| G-03 primary action; G-04 Evidence | One next task action in header/footer with prerequisite and calculating/blocked/error state; disclose IDs, JSON and checksums only on demand. | Multiple equal primaries, silent disabled action, technical default fields; current. |
| M-01 scope; M-02 search; M-03 tree | Establish governed scope, find known material, or browse Database→Profile→Table→Folder→Record; exact selection updates workspace. | Fake sole-scope selector, client subset presented as complete, tree as form; search correction is UXC-01 target. |
| M-04–07 facets/filter/header | Refine the same server query; show condition/unit/source, active restrictions, total/sort/page and loading/empty/error state. | Facet counts/rows/totals from different sources; UXC-01 target. |
| M-05 Yield | Show only for compatible metal property definition with condition/unit/source. | Yield filter/column for polymer or elastomer; UXC-01 target. |
| M-08–12 grid/layout/compare/inspector/start | Compare/select/open dense rows; select allowed Layout; pin Material/Test Data into Modeling; preserve selection and result context. | Truncated identity, auto-compare, unpinned latest start, blanking main pane; current. |
| M-13–18 detail/property/curve/cards/relations | Display identity, Layout value, original/normalized units, curve, target card/mapping and exact relation evidence in purpose tabs. | Long generic accordion, ambiguous Preview/fake Download, hidden mapping; current. |
| W-01 session; W-02 stage; W-03 context; W-04 action | Establish exact family/Material/State/Test Data pins, use the v3 clearable session reducer, and change Data/Process/Fit/Validate/Review-Release/Export without graph remount. The compact stepper reports Complete/Blocked/Warning/Stale with a reason. Validate uses only explicitly selected exact reference artifacts; Review/Release state a missing package/policy rather than borrowing Fit or Validation state. | Global output fallback, a stale current pointer, Fit as new-session default, “reviewed”/“released” labels without event; UXC-05 current. |
| D-01 source; D-02 library; D-03 raw inspector | Select a permitted exact Test Data revision or inspect CSV/TSV/XLSX parser output. The inspector stays beside source selection because sheet/header/decimal, raw sample rows and immutable raw checksum are the evidence for the next decision. | Visible until a source is saved; source is the permitted revision or immutable Raw Asset; requires a supported parser result; empty/inspecting/blocked/error preserve file and parser choices for retry. |
| D-04 provenance; D-05 axis/unit mapping; D-06 plot; D-07 save | Record Test Run/specimen/condition provenance and show each source column, quantity/axis semantics, raw unit, normalized unit and mapping state before preview. A manual mapping requires source column, unit and reason; changing it creates the next Test Data revision and clears Process→Export current pointers. `Save dataset` is the only Data primary action and never implies review. | Raw bytes and raw-unit text are never mutated; hidden conversion, internal semantic keys, or `reviewed data` labels are forbidden. Save failure retains source, mapping and plot for retry. |
| P-01 rail; P-02 replicate; P-03–05 operation; P-06 workup; P-07 plot; P-08 save | The Process rail keeps `Include in processing/fit` separate from `Show on plot`, and identifies specimen/revision. Replicate analysis is a secondary disclosure only with two compatible included curves. Purpose-grouped operations form an ordered recipe; the contextual inspector keeps the selected operation, source and before/after plot together. Metal elastoplastic exposes manual Young’s modulus and selected necking-boundary workup only when they affect the executed method. Each requires a value, explicit unit/quantity semantics and reason, then is retained as typed `workup_overrides` with original and canonical values in the immutable Processing Output revision and Artifact. Yield remains curve-derived proof stress at the selected offset; direct manual yield is unavailable until its production definition is approved. A draft operation/order/scope/workup change dispatches `CHANGE_PROCESS` even without a saved Recipe pin, stales downstream current pointers, and `Save processed curves` creates the immutable output revision. | Process and non-metal Fit never show a universal Yield field; direct manual yield, manual curve edits, outlier deletion, implicit smoothing/resample, duplicate commit actions and review language are forbidden. Preview/save failures retain draft, selection and plot for retry. |
| F-01–07 rail/workflow/model/bounds/range/run/plot | Select compatible processed data, model/bounds/range, run candidate and show response/residual/tangent plus observed/extrapolated domain. Input change invalidates decision onward. | Opaque score or hidden extrapolation; current. |
| F-08–11 comparison/selection/blend/save | Compare error/status/applicability/warnings; engineer selects one candidate or named two-law ratio blend and reason, then saves an immutable decision snapshot. Recommendation never mutates it. | Auto-selection, reason-only selection or blend represented as one law; UXC-04 current. |
| V-01–04 plan/run/result | When the current selection, Material Model IR calibration evidence and Solver Card exact revisions match, pin an existing synthetic reference Template and Dataset Selection, submit/evaluate the non-production runner and retain its immutable result separately from Fit evidence. A normal Processing Output without that adapter is `Not supported`. | Validated without a Validation Run, same-State model substitution, first-item/latest fallback, or a result reused as Fit evidence; UXC-05 current. |
| R-01–04 package/submit/approve/release | Display Submit, Request changes, Approve and Release as distinct command/state contracts. Until an immutable candidate-package producer and release-policy input exist, each unavailable command is explicitly `Not configured`/`Not run`; exact context may open Activity or the governed reference harness. | Approval/release without policy, permission, event or an authoritative package digest; UXC-05 current boundary. |
| E-01–08 prerequisites/pin/lineage/target/preflight/preview/deliver/evidence | Pin current allowed exact model, select solver/version/unit, expose mapping/acknowledgement, preview and deliver immutable lineage artifact. Source/target change invalidates preview/delivery pointer; retain preflight for recovery. Until a server proves the Processing Output→Material/State chain and provides an ephemeral target preview, show the prerequisite/lineage recovery surface only; browser pin comparison is not proof. | Artifact UI without server-proven exact source, silent approximation, preview labelled delivered; UXC-06 constrained. |

### Export component and field contract (`E-01`–`E-08`)

| ID / component | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `E-01–04` exact source checklist and lineage | Make every required current pin and the Processing Output → IR → Neutral → target preflight → native card chain inspectable before an artifact action. | Export graph dock, replacing artifact controls when proof is absent. | Export stage. | Session refs plus the loaded Processing Output response. | Matching current refs; server Material/State provenance before delivery. | Upstream and target changes retain history but clear/regenerate downstream pointers. | current, missing, stale, not-supported. | Name the missing pin or API proof; preserve session context and offer the owning stage. |
| `E-05–08` target, preflight, preview, deliver and receipt | Select a target, disclose all mapping states, create an ephemeral preview, then persist one immutable Solver Card with its receipt. | Export dock after server proof is available. | Only after `E-01–04` server proof. | Governed server verifier and target-preview/delivery contracts. | Exact output/model/neutral source, target mapping result and acknowledgement where required. | Target tuple change regenerates target-only preflight/preview/artifact. | blocked, preflight, preview, delivered, stale, failed. | Current API does not provide this contract: controls remain absent, never simulated in the browser. |
| A-01–03 queue/item/job | **Target:** show Needs attention/In progress/Recent outcomes, resume exact context and provide job error/retry with Advanced diagnostics. | Placeholder dashboard or generic job history as default; DUI-08 pending. |

### Fit component and field contracts (`F-01`–`F-11`)

| ID / component or field | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `F-01` processed-curve rail | Choose the exact curves included in candidate calculation independently from plot visibility. | Left of the persistent graph so scope and response remain visible together. | Fit with a compatible saved Processing Output/Test Data context. | Exact Test Data/Processing Output revisions and session inclusion state. | Current Material, State, Test Data and Mapping Profile pins. | Inclusion change dispatches `CHANGE_SELECTION` and clears fit-decision, validation, review, release and delivery current pointers. | empty, compatible, selected, stale, blocked. | Preserve the rail and graph; identify the missing/incompatible exact revision and return to Data/Process. |
| `F-02` Fit task and primary action | Run/re-run candidates for the current input intent without implying a decision. | Compact stage strip and graph-adjacent ribbon. | Fit stage and write permission. | Session stage plus current Recipe step options. | Compatible processed input and one supported synthetic reference fit method. | Run-intent change clears the current selection and downstream pointers; immutable outputs remain. | blocked, ready, calculating, warning, error. | Keep inputs and prior graph; show the failed method and offer Update candidates. |
| `F-03` model/law intent | Declare which bounded candidate families or Prony term-count policy the server should evaluate. | Current-step ribbon beside the comparison it controls. | Metal hardening or polymer Prony Fit respectively. | Versioned processing method registry and Recipe draft options. | Supported family/method capability; no production TBD default. | Change invalidates candidate preview and every downstream current pointer. | default intent, edited, unsupported, stale. | Restore last draft option or choose a supported synthetic reference option, then re-run. |
| `F-04` parameter and bound inspector | Inspect fitted parameter value, unit, lower and upper bounds before selecting. | Contextual disclosure beside the selected candidate, never a permanent third column. | Recomputed stage exposes parameter scalars for the focused candidate. | Server `scalar_results`; exact method/version and quantity unit. | Successful candidate computation. | Inspector viewing changes nothing; changing an input bound invalidates preview onward. | collapsed, available, bound-warning, missing-evidence. | Keep candidate focus; name the missing scalar and require re-run instead of inventing a fallback. |
| `F-05` fit/extrapolation range | Distinguish observed fit domain from unobserved bounded extension. | Candidate row and graph boundary, adjacent to response evidence. | Metal Fit; polymer shows measured grid and `observed_only`. | Executed step options plus recomputed stage domain. | Finite ordered range; metal extension acknowledgement when warning applies. | Range change invalidates preview, selection and all downstream pointers. | observed, extrapolated-warning, observed-only, invalid. | Preserve values and graph; correct the ordered range and re-run. |
| `F-06` Update candidates | Produce deterministic candidate evidence, not a saved selection. | Only primary run action in the Fit header. | Fit prerequisites are satisfied. | Exact input revisions, method/version and current options. | Server preview endpoint and supported method. | New successful preview clears any selection made against an older preview. | ready, calculating, succeeded, failed, superseded. | Cancel/supersede older requests; retain current draft and offer retry. |
| `F-07` persistent response plot | Compare observed, candidate, residual/tangent and extrapolated response without remounting the workspace. | Dominant center region (at least 72% at 1440 px). | Data is loaded; overlays vary by current stage/view. | Server preview stages and exact source series. | Matching quantity semantics and explicit units. | Plot-view/zoom changes do not invalidate engineering state; graph range edits follow `F-05`. | loading, response, residual, tangent, empty, error. | Preserve plot controls and last good context; identify unavailable overlay and retry preview. |
| `F-08` candidate comparison table | Compare model identity, recommendation, metric, range, stability, compatibility and warning on one row. | Graph-adjacent ribbon so row evidence and curve response can be read together. | Successful Fit preview. | Recomputed `scalar_results` and method capability; recommendation is calculated evidence only. | Complete metrics for the row; missing diagnostics are explicit warnings. | Recommendation changes never mutate engineer selection or downstream snapshots. | calculated, recommended, selected, incomplete, warning. | Keep all rows; show missing diagnostics and require re-run rather than ranking a fallback. |
| `F-09` engineer selection, reason and acknowledgement | Make one explicit engineering decision after comparison. | Directly below the candidate table. | A selectable recomputed candidate row is clicked. | User event plus exact active preview identity; reason and warning acknowledgement are user inputs. | Selected row, non-empty reason, and acknowledgement only when that row has a warning. | `CHANGE_SELECTION` clears saved-current output, validation, review, release and delivery pointers. | null, selected-unsaved, reason-missing, acknowledgement-required, stale. | Preserve row/graph/reason on save error; refocus the missing requirement. Reason text alone never selects a row. |
| `F-10` single/blend identity | Preserve one law or both named laws and primary ratio consistently in UI, graph, API, model projection and Neutral evidence. | Candidate rows, selected-candidate evidence and saved evidence. | Metal with at least two compatible laws exposes the exact calculated preview blend as its own selectable row; polymer is single actual server result only. | Explicit row choice; fitted parameter sets for every selected law. | Distinct blend laws, ratio strictly inside `(0,1)`, both parameter sets and bounds. A preview law/ratio change must be recalculated before the blend can be selected. | Preview option change dispatches `CHANGE_PROCESS`; row choice dispatches `CHANGE_SELECTION`; either invalidates saved-current and downstream pointers. | preview-blend, selected-single, selected-blend, stale. | Keep candidate evidence; update candidates after a preview identity change, then explicitly select and re-save. Never label preview as selected or collapse a blend to its primary law. |
| `F-11` Save selected candidate | Commit the exact selected decision as an immutable Processing Output revision for model promotion. | Sole Fit primary save action in the current-step ribbon. | `F-09` is ready and the current server preview matches the selection. | Exact source/Profile revisions, executed steps, recomputed scalars and typed `fit_decision`. | Explicit row selection; valid identity/range/metric/parameters/reason/acknowledgement. Polymer requires `prony:{actual_term_count}` from the server result. | Successful save advances the current output pointer and leaves validation/review/release/delivery unset; later upstream change clears only current pointers. | disabled, ready, saving, saved, stale, failed. | Preflight before Artifact/revision creation; on failure create neither, retain selection and graph, show the mismatch and offer re-run/retry. |

### Validation and review component contracts (`V-01`–`R-04`)

| ID / component or field | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `V-01` selected candidate / Fit metric ledger | Keep a saved candidate and its fit metric visibly distinct from validation. | Top ledger of Validate and Review / Release, adjacent to governed state. | Any Modeling Validate or Review / Release stage. | Exact session Processing Output and selection refs; server Fit evidence. | Explicit saved candidate. | Candidate/process/material context change clears validation and all downstream current pointers. | not configured, fit-evidence-only, stale. | Preserve immutable candidate history and return to Fit to make a new selection. |
| `V-02` pinned validation inputs | Select Template and Dataset Selection revisions for one non-production OpenRadioss plan without substituting a model/card from another candidate. | Compact Validate control area under the ledger. | Metal session whose selection ID matches the server model's calibration-candidate evidence and whose IR/card refs match exact revisions. | Existing API list responses, model calibration evidence and session exact refs; no default item. | Saved candidate; exact candidate-linked Material Model IR and Solver Card; explicit Template and Dataset Selection choices. | New plan dispatches `CHANGE_VALIDATION_TARGET`; later source change clears validation/review/release pointers. | blocked, ready, pinning, pinned, not supported, error. | Retain each selected artifact and name the unavailable adapter/service/input; retry after correction. Never substitute another model from the same State. |
| `V-03` validation job and result | Submit and evaluate a supported reference runner, then expose the result verdict and holdout-independence separately from fit. | Beside the pinned plan rather than in Fit or Export. | A pinned reference plan exists. | Separate exact `validationPlan` and `validation` result session refs plus immutable plan/run/result API records. | Pinned plan; supported reference runner. | Changing validation target clears current plan/result and stales review; no historical run is mutated. | not run, queued, running, passed, failed, not evaluated, not supported. | Restore both plan and result by exact IDs after remount; keep run evidence and collect, evaluate, retry or revise the plan as the returned state allows. |
| `R-01` review/release command ledger | State Submit, Request changes, Approve and Release independently and prevent any inferred governance event. | Below validation ledger in the shared governed stage. | Validate or Review / Release stage. | Session stale state and authoritative review-package/release-policy capability. | Immutable candidate package for Submit; submitted request for decision; passed result and approved package for Release. | Source change stales review and clears release current pointer without changing immutable history. | not configured, not run, in review, changes requested, approved, released, stale. | Link exact available context to Activity/governed harness; do not fabricate digest, policy or fallback command. |

## 1. Product character

The product is a desktop-first CAE material engineering application delivered through a browser. It must visually and behaviorally resemble a professional engineering tool rather than a marketing site, content portal or card-based SaaS dashboard.

Reference character:

- Granta MI: persistent hierarchy, compact record list, datasheet, typed links and configurable schema tools.
- Material Data Center: stable filters, comparable results, selected material context and direct CAE delivery.
- Material Modeler: persistent engineering plot, compact curve navigator, task-specific controls and direct card export.

The product must not copy commercial branding, exact colors, icons or proprietary geometry.

## 2. Global shell

### 2.1 Vertical structure

```text
Application frame
├─ Menu bar                  28 px
├─ Command bar               36 px
├─ Workspace                 remaining height
└─ Status bar                24 px
```

The current 60 px brand-centric header is retired.

### 2.2 Menu bar

Content:

```text
File | Materials | Modeling | View | Tools | Help
```

Right side:

- workspace name;
- current user;
- connection state.

The product logo is limited to a compact 20–24 px mark. No subtitle or marketing description is shown.

### 2.3 Command bar

The command bar changes with the active workspace.

Examples:

Materials:

```text
Search field | Search | Browse | Compare | Columns | Refresh
```

Modeling:

```text
Open data | Save session | Undo | Redo | Fit | Export | Advanced
```

Commands use compact icon-plus-label controls. Only the task-primary command uses a filled accent treatment.

### 2.4 Status bar

Always visible. Shows:

- current selection;
- record count or selected curve count;
- unit system;
- active revision or `Draft` state when relevant;
- background job state;
- warnings/errors count.

Technical identifiers remain available through a status-bar disclosure or Evidence, not as default body text.

## 3. Shared dimensional system

### 3.1 Typography

| Role | Size | Weight | Use |
| --- | ---: | ---: | --- |
| Application/menu | 12.5 px | 500 | menu and command labels |
| Data/body | 13 px | 400 | tables, forms, descriptions |
| Metadata | 11.5–12 px | 400 | units, source, secondary state |
| Pane title | 13.5–14 px | 600 | navigator and inspector headings |
| Page/workspace title | 16 px | 600 | one title per workspace |
| Dialog title | 16 px | 600 | modal only |

Weight 650 or above is not used for ordinary rows, buttons or explanatory text.

### 3.2 Spacing

Base scale:

```text
2, 4, 6, 8, 12, 16, 24 px
```

Rules:

- default pane padding: 8 px;
- dense form/group padding: 6–8 px;
- workspace outer margin: 0–8 px;
- section gap: 8–12 px;
- 24 px is reserved for dialogs or empty states;
- 32 px and 48 px are not used in normal engineering workspaces.

### 3.3 Shape and surface

- persistent panes: no radius;
- tables and property sheets: no radius;
- splitter: 4 px hit area, 1 px visual divider;
- inputs and compact controls: 2–3 px radius;
- popovers/dialogs: 4 px radius;
- shadows: overlays only;
- no gradients;
- no nested persistent cards;
- selection uses a flat background plus a 2–3 px accent edge.

## 4. Materials workspace

### 4.1 Layout

At 1440 px:

```text
Navigator 260 px | Result grid flexible | Inspector 300 px
```

At 1366 px:

```text
Navigator 240 px | Result grid flexible | Inspector collapsed
```

At 1920 px:

```text
Navigator 280 px | Result grid flexible | Inspector 340 px
```

Navigator and inspector are resizable. Minimum and maximum widths:

- navigator: 210–380 px;
- inspector: 260–480 px.

### 4.2 Navigator

Tabbed modes:

```text
Search | Browse | Subsets
```

Search mode contains filters without introductory prose.

Browse mode contains:

- Database/Profile/Table selectors;
- local tree search;
- compact 24–26 px rows;
- node glyph, disclosure, label;
- full keyboard navigation;
- independent scroll.

Subsets mode displays saved subsets as compact rows, not cards.

### 4.3 Result grid

The result grid is the dominant area.

Default columns:

- Material/Grade
- Family
- Source/Manufacturer
- State/Condition summary
- Yield or family-specific key property
- CAE Cards
- Status

Behavior:

- resizable columns;
- sortable headers;
- sticky header;
- row height 32–36 px;
- single click selects;
- double click opens datasheet;
- context menu supports Open, Compare, Show in Tree and Download Card;
- column chooser stores user preference.

No explanatory banner is displayed above the grid. Search state and result count appear in the command/status bars.

### 4.4 Inspector

The selected-material inspector contains:

- identity and grade;
- 4–6 key properties;
- application condition summary;
- card availability;
- primary command: Open Datasheet or Download preferred card.

Descriptions are capped at two lines. Related technical data is not expanded by default.

## 5. Material Datasheet workspace

### 5.1 Layout

```text
Optional Tree/List 240–320 px | Datasheet flexible
```

The selected Record stays in context. Opening a record does not replace the entire application shell.

### 5.2 Datasheet tabs

```text
Overview | Properties | Curves | CAE Cards | Related | Evidence
```

`Related` is a first-class tab rather than being hidden inside Evidence.

### 5.3 Property sheet

Properties are presented as a compact property grid:

```text
Property | Value | Unit | Condition | Source
```

- row height 30–34 px;
- groups use collapsible headers;
- editable values use in-cell or right-side property editor;
- original and normalized unit/value can be toggled;
- administrator-defined Layout order is preserved.

### 5.4 Related and workflow

The Related tab contains two synchronized views:

- typed link list;
- optional workflow/relationship graph.

Selecting a relation changes the adjacent context without navigating away. Forward/reverse labels, target type and exact revision are visible in the detail row.

## 6. Modeling workspace

### 6.1 Stable layout

```text
Curve/process navigator 190–260 px | Plot flexible | Optional inspector 280–360 px
```

The plot must remain visible through Data, Process, Fit and Export. The right inspector is hidden unless the current task requires it. Validate and Review / Release use a compact prerequisite placeholder rather than a permanent third column.

### 6.2 Task strip

The six stages appear as a compact stateful strip:

```text
Data | Process | Fit | Validate | Review / Release | Export
```

They are not large buttons or cards. Every stage shows Complete, Blocked, Warning, or Stale plus a concise reason. New session starts at Data; resume restores the last saved stage and graph-view state.

### 6.3 Navigator

Rows are 24–26 px and support:

- visibility checkbox;
- curve-type glyph;
- short label;
- state marker;
- context menu.

Source paths, UUIDs and detailed metadata appear in a properties inspector, not inside each row.

### 6.4 Plot

Plot requirements:

- minimum 72% of workspace width at 1440 px;
- legend can be docked, overlaid or hidden;
- direct range/point selection;
- observed, processed, fitted and extrapolated styling is consistent;
- response, residual and derivative/tangent views use plot tabs;
- cursor coordinates and selected point/range appear in status bar;
- toolbar supports Zoom, Pan, Fit view, Select range and Export image.

### 6.5 Current-task inspector

Only current-task controls are shown.

Process examples:

- include/exclude;
- crop range;
- smoothing;
- resampling;
- mean/band.

Fit examples:

- candidate model;
- parameter values/bounds;
- objective and residual summary;
- extrapolation limit;
- Apply selected model.

Controls use property-editor rows, not independent cards.

### 6.6 Export

Export uses a two-pane layout:

```text
Solver/law/unit/mapping options 300–360 px | Native card preview flexible
```

Download is the task-primary command. Mapping warnings remain visible. Detailed mapping JSON and revision IDs are under Advanced Evidence.

## 7. Administration workspace

### 7.1 Layout

```text
Object navigator 220–280 px | Object list 280–420 px | Property editor flexible
```

Objects:

- Databases
- Profiles
- Tables
- Attributes
- Layouts
- Subsets
- Link Types

Administration must resemble a schema/property editor, not a landing page with task cards.

### 7.2 Editing contracts

- Table selection updates Attribute/Layout/Link lists in context;
- Add/Edit/Duplicate/Delete are command-bar actions;
- Attribute editor is a structured property sheet;
- Layout editor supports ordered rows and drag/reorder commands;
- Link Type editor displays source table, target table, direction labels, cardinality and revision binding;
- preview opens the real datasheet alongside the editor.

## 8. Activity workspace

Default view is a compact work queue:

```text
Status | Task | Material | Owner | Updated | Action
```

Reviews, jobs and releases are tabs or saved views. No dashboard cards or large summary tiles in the normal view.

## 9. Legacy removal contract

The following visual patterns are prohibited in active product routes:

- `.page-stack` as a normal workspace shell;
- `.page-heading` with marketing-style description;
- `.content-card` for ordinary sections;
- `.module-material-card` and task-card grids;
- persistent `.eyebrow` copy above every heading;
- pill badges for ordinary metadata;
- repeated large empty-state cards;
- nested bordered panels;
- large primary buttons for secondary navigation.

Existing legacy routes may retain compatibility redirects but must render canonical workspaces.

## 10. Acceptance gates

A route passes only when all are true:

1. The first viewport contains the main data/plot area, not introduction copy.
2. Persistent panes are flat and resizable where required.
3. No normal body text is larger than 13.5 px.
4. No normal workspace uses 24–32 px internal padding around every section.
5. There is at most one filled primary command per task context.
6. The route has no nested persistent cards.
7. Keyboard navigation covers menu, command bar, navigator, grid and tabs.
8. The status bar reports current selection and state.
9. 1366, 1440 and 1920 layouts pass without page-level horizontal overflow.
10. Tree, Attribute/Layout/Subset/Link Type, revisions, provenance and solver-mapping contracts remain intact.
