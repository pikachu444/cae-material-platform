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
| W-01 session; W-02 stage; W-03 context; W-04 action | Establish exact family/Material/State/Test Data pins, use the v3 clearable session reducer, and change Data/Process/Fit/Validate/Review-Release/Export without graph remount. The compact stepper reports Complete/Blocked/Warning/Stale with a reason; Validate and Review/Release are blocked-prerequisite placeholders until UXC-05. | Global output fallback, a stale current pointer, Fit as new-session default, “reviewed”/“released” labels without event; UXC-02 current. |
| D-01–07 source/library/file/identity/mapping/plot/save | Choose exact library/local/JSON source, map channel/unit/provenance, validate uncertainty, preview and save Test Data revision. Mapping change invalidates processing onward; retain source mapping for recovery. | Normal JSON editing, hidden conversion, saved data called reviewed; current. |
| P-01–08 rail/replicate/palette/pipeline/inspector/plot/save | Select curve/replicate, define ordered processing operation/range, preview before/after and commit immutable Processing Output. Operation change invalidates Fit onward; source curve remains recoverable. | Manual curve edit, outlier deletion, implicit smoothing/resample; current. |
| F-01–07 rail/workflow/model/bounds/range/run/plot | Select compatible processed data, model/bounds/range, run candidate and show response/residual/tangent plus observed/extrapolated domain. Input change invalidates decision onward. | Opaque score or hidden extrapolation; current. |
| F-08–11 comparison/selection/blend/save | Compare error/status/applicability/warnings; engineer selects one candidate or named two-law ratio blend and reason, then saves decision/snapshot. Recommendation never mutates it. | Auto-selection or blend represented as one law; UXC-04 target. |
| V-01–04 plan/run/result | **Target:** configure approved reference/plan, run validation and retain immutable result; failure preserves candidate and offers retry/revise plan. | Validated without Validation Run; UXC-05 pending. |
| R-01–04 package/submit/approve/release | **Target:** package exact lineage, submit, request changes/approve, then release under role/policy; each event is auditable. | Approval/release without policy, permission or event; UXC-05 pending. |
| E-01–08 prerequisites/pin/lineage/target/preflight/preview/deliver/evidence | Pin current allowed exact model, select solver/version/unit, expose mapping/acknowledgement, preview and deliver immutable lineage artifact. Source/target change invalidates preview/delivery pointer; retain preflight for recovery. | Artifact UI without exact source, silent approximation, preview labelled delivered; UXC-06 target. |
| A-01–03 queue/item/job | **Target:** show Needs attention/In progress/Recent outcomes, resume exact context and provide job error/retry with Advanced diagnostics. | Placeholder dashboard or generic job history as default; DUI-08 pending. |

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
