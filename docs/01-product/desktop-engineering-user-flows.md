# Desktop Engineering User Flow Specification

Status: authoritative product and interaction specification

## UXC workflow-state and recovery contract

State names describe actual auditable events, not convenient labels. A Modeling session may be
`new → draft → previewing → committed output → selected candidate → validation run → in review →
approved → released → delivered`; unavailable policy remains `not run`, `blocked`, or `ready for
review`, never validated, approved, released, or delivered. Preview is ephemeral; saved inputs and
processing outputs are immutable revisions. Running a fit produces candidates; selecting a candidate
or blend with a reason is an explicit engineer decision. A recommendation never becomes a selection.

On an API, job, mapping, or permission error, preserve selected Material/Test Data revision,
unit/condition, curve inclusion, plot view, candidate and unsaved draft. Say what failed, whether
work was preserved, and provide one safe recovery command: retry, revise input, choose a supported
target, reload current, keep draft as a new revision, or cancel. Upstream Material/Test Data/mapping/
processing/fit changes invalidate downstream current pointers in order; they never rewrite immutable
outputs. The browser session aggregate is v3: its reducer distinguishes an explicit current-pointer
clear from an omitted field, and a v2 session is migrated safely before resume. New sessions begin
at Data, never Fit.

The decision-to-delivery flow is: confirm exact data and mapping; preview then commit processing;
run and compare candidates; explicitly select a law or blend and record the reason; save it; run
validation/review/release only where policy exists; pin the exact allowed source; select solver,
version and units; resolve mapping blocks; acknowledge approximations; preview, then deliver. Never
substitute a global or another-session output when the current exact source is absent.

## Exact command vocabulary

| Command | Actual output | Never imply |
| --- | --- | --- |
| Preview / Generate preview | ephemeral calculation or card preview | saved, selected, reviewed, released, delivered |
| Save dataset / Save processed curves | immutable Test Data / Processed Dataset revision | reviewed or validated |
| Run fit | Fit Run and candidates | engineer selection |
| Select candidate / Save candidate | Engineer Decision draft / saved snapshot | reviewed or released |
| Run validation | Validation Run | approval |
| Submit for review / Request changes / Approve | review queue/change/approval event | release |
| Release | immutable Released Model under policy | solver artifact |
| Deliver card | immutable Solver Artifact with lineage | source-model mutation |

Forbidden labels: `Commit reviewed fit` without review, `Validated` without Validation Run,
`Approved` without approval, `Released` without release, and `Delivered` for preview-only output.

## Downstream invalidation matrix

| Changed input | Mark stale / clear current pointers | Preserve and recover |
| --- | --- | --- |
| Material revision, Material State/condition or physical family | clear Test Data through Export; mark prior review/release stale | immutable prior revisions; choose exact context and Test Data again |
| Test Data or axis/unit mapping | retain new input pin; clear Process through Export; mark review/release stale | immutable prior revisions and mapping; recompute Process/Fit |
| Operation, curve inclusion, range or recipe | retain source; clear Process output through Export; mark review/release stale | source curve/draft; preview or commit a new output |
| Fit model, bounds, range or evidence inclusion | clear candidates/selection through Export; mark review/release stale | prior run/decision; rerun and explicitly select |
| Candidate selection/reason or warning acknowledgement | retain Process/Fit evidence; clear validation/IR/Neutral/export and mark review/release stale | candidate grid/graph; save selected decision |
| Validation plan/reference/result | clear validation and export; mark review/release stale | candidate/plan; rerun or revise plan |
| Solver/version/unit or mapping profile target | retain source model; mark target validation stale and require IR/Neutral/export regeneration | pinned model/preflight; select supported target or acknowledge |

## 1. Purpose

This document defines how an engineer actually completes work in the CAE Material Platform. It is not a visual-style guide. The desktop engineering UI specification defines appearance and component grammar; this document defines user intent, workspace state, commands, state transitions, failure recovery and completion evidence.

The redesign is accepted only when both are true:

1. the interface uses a coherent desktop engineering application grammar; and
2. the priority engineering tasks are shorter, understandable and recoverable without exposing internal platform objects unnecessarily.

## 2. Priority user jobs

The product is optimized in this order.

1. Find an existing material, judge whether it is applicable, and download a native solver card.
2. Browse a governed material database when the exact material name is not known.
3. Compare candidate materials and their conditions, curves and solver availability.
4. Create a missing solver card from an existing reviewed neutral model.
5. Upload test data, process curves, fit a material model and create solver cards.
6. Resume or inspect long-running work, review decisions and failed jobs.
7. Configure Tables, Attributes, Layouts, Subsets and Link Types without weakening revision or provenance contracts.

Recipe, Batch, exact revision identifiers, mapping profiles and audit detail support these jobs. They are not independent primary destinations for normal users.

## 3. User roles and default landing

| Role | Default landing | Primary jobs |
| --- | --- | --- |
| Material Data Consumer / CAE Analyst | Materials | search, inspect, compare, preview and download cards |
| Material Modeler | Modeling or last active session | import, process, fit, export and save |
| Test Engineer / Data Steward | Modeling Data | upload, mapping, unit confirmation and data quality correction |
| Reviewer / Approver | Activity | review evidence, requested changes and release readiness |
| Administrator | Materials, with Administration in the application menu | Table, Attribute, Layout, Subset, Link Type and access configuration |

A role changes default commands and access. It must not produce a different visual product shell.

## 4. Shared workspace behavior

### 4.1 Persistent application frame

Every primary route uses the same frame:

```text
Application menu / workspace switcher
Context command bar
Main split workspace
Status bar
```

- The application frame does not introduce a marketing header or page hero.
- Route changes preserve the selected material, tree location, search query, filters and active work session where relevant.
- The status bar reports selection, record count, unit system, current stage, save state and background-job state.
- A page title may exist in the command bar, but it must not create a separate vertical section before the workspace.

### 4.2 Selection owns context

The currently selected object determines the available commands.

Examples:

- selecting a Material enables Open, Compare, Show in Tree and available Card commands;
- selecting a solver card enables Preview, Download and Mapping Evidence;
- selecting a curve enables Include/Exclude, Range, Crop and current-stage processing commands;
- selecting a Table or Attribute enables edit, revise, place in Layout and link constraints.

Commands that do not apply remain hidden or disabled with a concise reason. The interface must not show every possible command at all times.

### 4.3 Context continuity

The following state is restorable from URL and session state:

- Materials query, filters, sort and selected result;
- Browse Tree mode, expanded ancestors, selected Record and Subset;
- Material Detail tab and selected solver card;
- Modeling Material/State, active stage, selected curve/candidate and panel widths;
- Administration Table, selected Attribute and active editor.

Back navigation returns to the exact prior context, not to a default landing screen.

## 5. Flow A — known material to solver card

### Goal

A user who knows the material name, grade or code can inspect applicability and download a native card without understanding database revisions or mapping-profile objects.

### Entry state

- Route: `/materials`
- Search command has keyboard focus when no prior context exists.
- Recent query and selection are restored when returning from Material Detail.
- Results area remains visible while filters or context panes open and close.

### Main path

1. User enters material name, grade or code.
2. Results update and show material name, family, source, relevant property, condition summary and solver-card availability.
3. User selects a result. Selection updates the context pane without a full page transition.
4. Context pane shows key properties, applicability, validation/release state and available solver cards.
5. User either:
   - downloads an exact supported native card directly; or
   - opens Material Detail for curves, evidence or multiple card choices.
6. Download completion is shown in the status bar with filename, solver and revision summary. Full identifiers remain in Evidence.

### Command behavior

| Selection | Primary command | Secondary commands |
| --- | --- | --- |
| Material with exact native card | Download preferred card | Preview, Open Detail, Compare, Show in Tree |
| Material with several native cards | Open card selector | Preview, Download selected, Open Detail |
| Material with approximated mapping | Preview and review approximation | Download after acknowledgement, Mapping Evidence |
| Material with unsupported mapping | Create/Download disabled | Open Modeling, inspect unsupported fields |
| Material with no model/card | Start Modeling | Open Detail, Show in Tree |

### Acceptance

- Search to direct exact-card download: no more than three primary actions after entering the query.
- No UUID, SHA, Mapping Profile, Recipe or classification field appears on the normal path.
- Applicability and solver availability are visible before download.
- Unsupported output cannot be downloaded silently.

## 6. Flow B — browse, compare and inspect linked records

### Goal

A user who does not know the exact material name can navigate the governed database hierarchy and compare candidates without losing context.

### Workspace topology

```text
Navigator Tree | Record/Material grid | Selected datasheet or context
```

- Pane widths are resizable and stored per user.
- At 1366 px the optional context pane may collapse, but Tree and grid remain usable.
- Tree, result grid and datasheet are not separate dashboard pages.

### Main path

1. User switches the left navigator from Filters to Browse.
2. Tree opens at restored Database/Profile/Table/Folder position.
3. User expands nodes or uses Tree-local search.
4. Selecting a Record updates the center result/grid selection and right datasheet context.
5. Related Records and Workflow links are available in the selected context without replacing the Tree.
6. User selects up to three Materials or Records for comparison.
7. Comparison opens as a grid with aligned Attributes, units, missing values, conditions and card availability.
8. Closing comparison returns to the same Tree and selection.

### Tree rules

- Database, Profile, Table, Folder, Record and Subset remain visually distinct but compact.
- Search keeps matching Records and required ancestors visible.
- `ArrowLeft/Right`, `ArrowUp/Down`, `Home`, `End` and type-ahead navigation work.
- Double click or Enter opens the full datasheet; single click only selects.
- Tree search is scoped and does not replace global Material search.

### Related/link rules

- Links use administrator-defined forward and reverse names.
- Record links show relationship, target Record, type and revision.
- Workflow view shows Material → State → Test Data → Dataset → Processing Output → IR → Neutral → Card.
- The user can follow a link and navigate back without losing the previous selected Record and expanded ancestors.

## 7. Flow C — create a missing solver card from an existing model

### Goal

A material with a reviewed Neutral Material or Material Model IR but no target card can enter Export directly, without repeating data import and fitting.

### Main path

1. User selects a Material and sees that the requested solver card is missing.
2. User chooses `Create solver card`.
3. Modeling opens in Export with the Material, State and latest reviewed compatible IR/Neutral revision pinned.
4. User selects solver, solver version, law and unit system.
5. Mapping preflight displays exact, transformed, approximated, ignored and unsupported outcomes.
6. Unsupported output blocks generation.
7. Approximation requires explicit acknowledgement and records the decision.
8. User previews native ASCII and downloads the card.
9. Generated card appears immediately in the Material Detail CAE Cards tab and Browse workflow.

### Recovery

- If no reviewed compatible model exists, the system explains the missing prerequisite and opens Fit with the available processed data.
- If the selected model became stale, the user is offered the latest compatible reviewed revision and a comparison, not silently switched.

## 8. Flow D — test data to material model and cards

### Goal

A user can upload experimental data, understand every transformation, fit a model and create solver cards while the graph remains the principal evidence surface.

### Stage 1: Data

#### Entry

- New Modeling session, existing Material/State, or `Start Modeling` from a Material.
- Accepted sources: canonical JSON, CSV, TSV and XLSX.

#### Path

1. User drops or selects files.
2. System detects workbook/sheet, delimiter, header row, test type, likely channel quantities and units.
3. A compact mapping grid shows source column, sample values, quantity, original unit, normalized unit and confidence.
4. Only ambiguous or invalid mappings require user action.
5. Curve preview updates while mapping changes.
6. User confirms import.
7. Platform preserves raw bytes and creates explicit normalized Dataset revisions; no hidden mutation occurs.

#### Failure handling

- Missing unit: block commit for required channels and offer known unit choices.
- Unsupported workbook relationship or unsafe path: reject file with a concrete diagnostic.
- Duplicate specimen identity: offer link to existing specimen, create new revision, or cancel.
- Partial valid data: show accepted and rejected rows before commit.

### Stage 2: Process

#### Persistent topology

```text
Curve navigator | Persistent engineering graph
                 Settings ribbon for the selected operation
```

1. User includes/excludes specimen curves for the current analysis only.
2. User selects a range directly on the graph.
3. Crop, shift/scale, resample, smooth and replicate statistics are previewed.
4. Raw, preview and committed output remain visually distinct.
5. User commits a processing result with the input revisions and operations recorded.

Rules:

- Excluding a curve never deletes source data.
- Smoothing or resampling never occurs without a visible preview and explicit commit.
- Undo returns to the preceding preview; revision history handles committed results.

### Stage 3: Fit

1. User selects eligible processed curves and calibration/holdout roles.
2. Candidate models are run or restored.
3. Observed curves, candidate responses, residuals and extrapolation boundary share the persistent plot.
4. Candidate table shows fit metric, parameter summary, bounds, stability and applicability.
5. Selecting a candidate updates plot and property inspector without changing workspace topology.
6. User records selection reason and promotes the reviewed result to Material Model IR/Neutral Material.

Rules:

- Numeric convergence is not displayed as approval.
- Unobserved extrapolation is visually differentiated and labelled.
- Parameter, residual and stability detail is available without replacing the graph.

### Stage 4: Export

1. Reviewed model is pinned.
2. User chooses solver/law/unit system.
3. Preflight reports mapping states.
4. User resolves required values and approximation acknowledgement.
5. Native card preview appears beside compact delivery properties.
6. User downloads one or more native cards.
7. User saves the resulting package to the Material Library.
8. Status bar provides `Open Material`, `Show in Tree` and `View Activity` commands.

### Acceptance

- Data, Process, Fit, Validate, Review / Release and Export retain the same shell and selected session.
- Graph does not disappear during Process/Fit stage changes.
- Validate and Review / Release state their blocked policy prerequisite until UXC-05; they do not
  relabel fit evidence as validation or approval.
- Export has no global-output fallback. It remains blocked when the current session lacks an exact
  Material, State, Test Data or Processing Output pin.
- JSON editing is not required for the normal path.
- A completed card is searchable from Materials and linked in the workflow.

## 9. Flow E — resume work and review background activity

### Goal

Users can leave a long operation and return without hunting through technical job tables.

### Activity primary view

- Recent Modeling sessions
- Running/failed processing or fitting jobs
- Items requiring review or acknowledgement
- Recently generated cards and packages

Each row shows human-readable Material, task, state, owner, updated time and next action.

### Progressive advanced view

Recipe revision, Batch member attempts, job IDs, runner detail, mapping reports and audit evidence appear under Advanced or Evidence.

### Recovery commands

- Resume session
- Retry failed members only
- Open diagnostic
- Open produced Material/Card
- Cancel queued work when policy allows

The activity page must not become the old Jobs/Reviews dashboard under a new label.

## 10. Flow F — configure the material database

### Goal

An administrator can evolve the configurable catalog using compact editors and preview the result in the same workspace.

### Workspace topology

```text
Object navigator | Data grid/list | Property editor / live preview
```

### Table and Attribute path

1. Select or create Table.
2. Data grid lists Attributes with type, quantity semantics, unit constraints, required state and usage count.
3. Select an Attribute to edit in the property editor.
4. Save creates a new immutable definition revision.
5. Affected Layouts, Subsets and Links are shown before commit.

### Layout path

1. Select Table and Layout.
2. Ordered Attribute placement appears as compact rows.
3. Reorder, group, label and visibility changes update a live Datasheet preview.
4. Publish creates a Layout revision.
5. `Open sample Record` verifies the projection without leaving the selected Layout context.

### Link Type path

1. Select source and target Tables.
2. Define forward/reverse labels, cardinality and allowed direction.
3. Preview shows how Related Records will appear in the Datasheet.
4. Save creates the Link Type revision.
5. Existing links are validated; incompatible changes are blocked or require a migration plan.

### Subset path

1. Build filters using typed Attributes and normalized quantities.
2. Preview matching Record count and sample rows.
3. Save as Subset revision.
4. Subset becomes available in Materials Browse without exposing query JSON.

### Rules

- Administration never uses a card gallery for schema objects.
- Editing and preview remain adjacent.
- Forms are property sheets, not long isolated pages.
- Full identifiers and audit detail are available under Evidence.

## 11. Cross-flow command model

### Global commands

- Materials
- Modeling
- Activity
- Back / Forward
- Global search or command palette
- User/workspace menu

### Context commands

- Open / Preview / Download
- Compare
- Show in Tree
- Start or Resume Modeling
- Include/Exclude
- Apply range / Commit output
- Review / Approve / Request change
- Create revision / Publish

### Keyboard minimum

- `Ctrl/Cmd+K`: command palette/global object search
- `Ctrl/Cmd+F`: local grid/tree search
- `Enter`: open or apply selected command
- `Space`: toggle selection/include state
- `Esc`: close overlay or cancel current transient tool
- Arrow keys: grid/tree/tab navigation
- `Ctrl/Cmd+S`: commit current editable draft when valid

Shortcuts must be discoverable in menus and must not override critical browser/OS behavior unexpectedly.

## 12. Status and feedback model

The status bar is the preferred location for persistent low-priority feedback.

It can show:

- selected object and revision shorthand;
- result/record/curve count;
- normalized unit system;
- current Modeling stage and save state;
- preview versus committed state;
- background job progress;
- warnings requiring action.

Use banners only for blocking errors or major state changes. Do not use toast messages as the sole record of an important engineering decision.

## 13. Required edge cases

Every primary flow must specify and test:

- no search results;
- very long material, source, record and card names;
- missing properties or curves;
- more columns than fit in the current grid;
- missing or ambiguous units;
- mixed-validity imported rows;
- no solver card;
- approximated or unsupported solver mapping;
- stale selected revision;
- network interruption and retry;
- failed asynchronous operation;
- permission denied;
- unsaved editable changes during navigation.

## 14. Quantitative flow acceptance

| Flow | Target |
| --- | --- |
| Known material search to exact card download | ≤ 3 primary actions after query entry |
| Search result selection feedback | visible within 150 ms after local response data is available |
| Return from Material Detail | restores exact query/filter/sort/selection |
| Browse Tree record selection | updates context without full route reload |
| Missing card from reviewed model | enters Export directly with compatible model pinned |
| File import | ambiguous fields only require intervention |
| Process/Fit stage change | graph and selected curves remain mounted |
| Completed Export | card visible in Material Detail and Browse workflow |
| Administration save | creates revision and retains selected object/editor context |

## 15. Implementation order

1. Shared application frame, command bar, split panes and status bar.
2. Materials Search/Browse selection continuity and context commands.
3. Material Detail and card delivery command model.
4. Modeling persistent session and Data/Process/Fit/Export state transitions.
5. Activity resume/recovery flows.
6. Administration property editor and live preview flows.
7. Legacy routes and CSS removal after the corresponding flow passes acceptance.

A screen is not complete because it resembles a reference image. It is complete when the intended engineering task, state continuity, evidence visibility, error recovery and visual acceptance all pass together.
