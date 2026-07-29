# Desktop Engineering UI Product and Interaction Specification

Status: authoritative product and interaction specification

## 1. Objective

The product must behave as a desktop engineering application delivered through a browser. The redesign is not a visual reskin. It must reduce the time and cognitive work required to complete two primary jobs while preserving the existing configurable Material Database, revision/provenance and solver-card contracts.

Primary job:

```text
Find a material → assess applicability → inspect evidence → preview/download a native solver card
```

Secondary job:

```text
Select or upload test data → map units/channels → process curves → fit a model → review mapping → create/download cards → save to the Material Library
```

The user must remain in a stable workspace. Selection changes the working context; it must not repeatedly replace the application with unrelated page layouts.

## 2. Confirmed product facts

- The platform already supports Material, Material State, typed properties, configurable Table/Attribute/Layout/Subset/Link Type, exact Record links, Test Data, processing, fitting, Material Model IR, Neutral Material and native solver cards.
- Database/Profile/Table/Folder/Record hierarchy, revision/provenance, original and normalized units and explicit solver mapping states must be preserved.
- Materials is the default entry point.
- Modeling uses Data, Process, Fit and Export as the user-facing stages.
- Advanced technical objects remain available, but are not the primary navigation model.

## 3. Product modes

The application has four modes. These are workspaces, not separate mini-products with different visual grammars.

| Mode | Primary user job | Persistent context |
| --- | --- | --- |
| Materials | Search, browse, compare and download | navigator, selected Record, result state |
| Modeling | Convert test data into a selected model/card | session, curves, active stage, selected output |
| Activity | Current compact resume/review action queue; job recovery and release projections remain follow-up | current user, item context |
| Administration | Current: PR #143의 3-pane object navigator/list/property editor로 database/access를 관리; 남은 product-level refinement는 #160/#161에서 별도 검토 | selected schema object, draft changes |

## 4. Global desktop shell

### 4.1 Regions

```text
┌ Menu / workspace tabs (44–48 px) ──────────────────────────────────────┐
├ workspace-specific content and controls                                 ┤
│                                                                         │
│                         active workspace                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Dimensions

- Global application bar: 44–48 px.
- Workspace controls are workspace-specific. Materials, Activity, and Administration do not claim a
  permanent generic command/status band when their current route does not render one.
- Modeling uses compact context/stage controls and a graph-adjacent shallow ribbon; generic command
  or status bars must not consume persistent graph space.
- No marketing hero or product subtitle inside an authenticated workspace.
- Outer workspace margin: 0–8 px.
- Persistent pane padding: 8–12 px.
- Standard data row: 26–30 px.
- Page/pane title: 14–18 px depending on hierarchy.
- Data/control text: 13–13.5 px.
- Metadata: 11.5–12 px.

### 4.3 Command hierarchy

Commands are rendered according to scope.

| Scope | UI form | Examples |
| --- | --- | --- |
| Global workspace | menu/tab | Materials, Modeling, Activity |
| Current task | command bar | Search, New session, Save, Preview, Download |
| Selected row/object | row action or context menu | Open, Compare, Show related, Add to batch |
| Rare configuration | property sheet/disclosure | revision IDs, JSON, mapping evidence |
| Destructive/irreversible | dialog | discard draft, publish revision, delete draft-only object |

A large bordered button is not the default representation for every action.

## 5. Materials workspace

### 5.1 Topology

```text
┌ Search / Browse / Subsets | query | filter chips | Compare | Download ┐
├ Navigator  ⇆  Result or Datasheet  ⇆  Context                         ┤
│ 240–320       remaining width          280–420 optional                │
│ Filter/Tree   table / datasheet         properties/cards/related       │
├ selected count · result count · exact/latest context · job status ─────┤
```

- Navigator and Context panes are resizable and independently scrollable.
- An overflowing tree or result region has a reserved, visibly distinguishable scroll rail and
  thumb in the required reference captures. Computed overflow or an operating-system scrollbar that
  disappears in the captured pixels is not sufficient visual evidence. The rail must not cover row
  text, and it must operate by pointer, wheel and keyboard.
- Splitter positions persist per user and viewport class.
- At 1366 px, Context defaults closed before the result region is compressed.
- Main result/datasheet region must remain at least 720 px when possible.

### 5.2 Search interaction

1. Focus starts in the search field.
2. Enter applies the query; filters update the URL state.
3. Result rows appear in a dense sortable grid.
4. Single-click selects a row and updates Context without full navigation.
5. Enter or double-click opens the selected Material datasheet in the main region.
6. Escape returns from datasheet to the previous result state.
7. Back/forward restores query, filters, sort, selected row, pane widths and scroll position.

### 5.3 Browse Tree interaction

- Search, Browse and Subsets are modes of the same Navigator pane.
- Browse displays Database → Profile → Table → Folder → Record.
- Tree search retains ancestors and highlights matching Records.
- Selecting a Record updates the main datasheet region in place.
- Related links open the linked Record while maintaining an in-workspace back stack.
- Breadcrumbs show hierarchy but do not replace the Tree.
- Record selection must preserve exact revision context when opened from Evidence or a governed link.
- A tree row shows the concise stored object identity. Database/Profile/Table/Folder/Record type is
  conveyed by one aligned disclosure/glyph grammar; explanatory or qualification prose belongs in
  adjacent context or a tooltip, not appended to every node name.
- A genuinely long stored identity remains one line and is reachable with a local horizontal
  scrollbar that appears only when the tree actually overflows. The vertical scrollbar appears when
  more rows exist than the local viewport can show. Both use reserved rails outside the text area.

### 5.4 Result grid columns

Default Material result columns:

1. compare selector;
2. material name and grade/code;
3. family/class;
4. manufacturer/source;
5. key condition or yield value;
6. available solver cards;
7. status when relevant.

Column behavior:

- material name is the primary flexible column;
- numeric columns use tabular numerals and unit-aware formatting;
- headers are sticky;
- optional columns are configurable, but P0 does not require a general grid designer;
- truncation must expose the full value through title/tooltip and never hide the row identity;
- horizontal scroll is allowed only when required columns cannot fit after optional Context is closed.

### 5.5 Selected Material context

The Context pane shows, in this order:

1. identity: name, grade, family;
2. applicability summary;
3. four key properties;
4. native solver-card availability;
5. primary task command;
6. related/evidence disclosure.

The primary command is contextual:

- `Download .rad` or `Download .inp` when a preferred released card exists;
- `Preview card` when review is required;
- `Create card` when a Neutral model exists but the target card does not;
- `Start Modeling` when no suitable model/card exists.

### 5.6 Material datasheet

The navigator remains visible while the center region changes from results to datasheet.

Datasheet tabs:

```text
Overview | Properties | Curves | CAE Cards | Evidence
```

- Overview is a compact property/condition summary, not a landing page.
- Properties is a property sheet/data grid, including original and normalized values when required.
- Curves uses the engineering plot component and a compact curve list.
- CAE Cards contains solver, law, version, unit system, mapping state and preview/download commands.
- Evidence contains Related Records, workflow, revisions, provenance and technical identifiers.

## 6. Known Material to card flow

### 6.1 Happy path

```text
Search query
→ select Material row
→ Context shows applicable card
→ Preview or direct Download
→ download result and recent-use entry
```

Acceptance target:

- after query submission, direct download requires no more than three primary actions;
- no UUID, content hash, Mapping Profile or Recipe input;
- no confirmation for an exact released mapping;
- approximation requires explicit acknowledgement adjacent to the mapping warning;
- unsupported mapping disables generation and explains the blocking field.

### 6.2 Card preview

The preview workspace uses two regions:

```text
native text preview  ⇆  delivery/property sheet
```

The delivery sheet shows solver, law, units, revision status and mapping summary. Technical IDs and the full mapping report are disclosed separately.

### 6.3 Missing card decisions

| Existing evidence | Offered command |
| --- | --- |
| released native card | Preview / Download |
| Neutral model supports target solver | Generate target card |
| reviewed Processing Output, no Neutral model | Promote/review in Modeling |
| test data only | Open Modeling at Process/Fit as appropriate |
| unsupported mapping | Explain block; no fake download command |

## 7. Modeling workspace

### 7.1 Topology

```text
┌ Session / Save / Undo / Redo | Data | Process | Fit | Export | Advanced ┐
├ Curve/process navigator ⇆ Persistent graph                           ┤
│ 184–210 px              remaining width; shallow graph-adjacent band │
├ selection · points · units · preview/committed · warnings/jobs ┤

```

The graph is persistent across Data, Process, Fit and Export. Stage changes update commands and
overlays; they do not remount an unrelated page. Candidate parameters appear on demand in a drawer or
disclosure, never a permanent third column. Validation and review/release remain distinct governed
Advanced or Activity actions and are not normal-stage tiles. The approved visual reference is the
lower proposal in `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`.

The Modeling navigator is not a copy of the Materials catalog tree, but both belong to one desktop
engineering grammar. Modeling therefore uses the same flat pane heading, regular 12–13 px identity
text, restrained selection fill with a leading accent, aligned hierarchy indentation and compact
section separators. The curve rail keeps its stage-specific membership checkbox, plot-color sample
and independent visibility command, but these controls must not make the identity look bold, crowded
or card-like. Section labels use sentence case rather than oversized uppercase navigation chrome.
The method parent and its specimen children remain visually distinguishable at every supported pane
width; full identities stay accessible, and a conditional local scrollbar appears when content
actually overflows.

The curve legend is a compact overlay inside a measured data-free plot quadrant, using lower-right
for the current Fit response when it remains clear. It must not cover any curve, observed boundary,
axis, tick/title, graph-state overlay or direct-selection feedback. The renderer checks candidate
quadrants against current geometry and moves the legend when necessary; a compact docked legend is
the fallback only when no safe plot region exists. A permanent external legend column must not tax
the normal plot width. Recommendation/selection workflow status is not part of the curve legend.

### 7.2 Session lifecycle

Normal-path states:

```text
new (Data) → draft/preview → saved processing result → calculated candidates → explicit saved fit decision → model/card preparation → card preview → delivered card
```

- Sessions autosave non-destructive UI state: selected curves, pane sizes, active stage and draft controls.
- Numerical outputs are not silently committed by autosave.
- The status bar distinguishes Preview, saved output, explicit selection, and blocked/stale downstream states. It never calls a fit reviewed, validated, approved, released, or delivered without its real event.
- Session v3 uses explicit context events and clearable current pointers. Material revision/state/family/Test Data changes cannot retain a current downstream output; historical server objects are not deleted.
- Leaving with uncommitted material changes prompts once, with Save draft / Discard / Stay.
- Stale exact-revision conflicts must offer Reload current, Keep local draft as new revision, or Cancel.
- Validation, review and release follow a separate governance branch and require their own real events;
  they do not rename a normal-path state.

### 7.3 Data stage

Entry choices:

- use selected Material/Test Data from the Library;
- upload CSV/TSV/XLSX;
- import canonical Test Data JSON.

Flow:

1. choose source;
2. detect worksheet/test type/channels/units;
3. show a mapping grid;
4. highlight only uncertain or invalid mappings;
5. preview curves;
6. confirm Data selection.

The user must not edit JSON for the normal path. Advanced JSON remains available for expert recovery and exchange.

### 7.4 Process stage

The navigator lists specimen/curve membership and ordered processing operations. The graph supports direct range/point selection.

Commands:

- include/exclude from current analysis;
- crop/range;
- scale/shift;
- resample;
- smoothing;
- replicate alignment/statistics;
- reset current operation;
- preview;
- commit Processing Output.

Every operation shows its effect as a graph overlay before commit. The source curve remains visible or recoverable.

### 7.5 Fit stage

The graph displays observed data, candidate fits, residual or tangent view and the observed/extrapolated boundary.

Candidate grid columns:

- family/model;
- fit status;
- error metric;
- applicability/extrapolation range;
- stability/warning;
- selected state.

Flow:

1. select observed/processed dataset;
2. run candidates;
3. compare response/residual;
4. inspect parameters/bounds on demand;
5. explicitly select a recomputed candidate and record reason;
6. acknowledge only warnings that apply to that selected row;
7. save the typed decision snapshot as an immutable Processing Output;
8. promote the exact decision to a Material Model IR.

The calculated recommendation and engineer selection are separate states. A changed recommendation
does not select a row or mutate an existing selection. Metal can retain a named single law or a
two-law ratio blend with both parameter sets. The exact calculated preview blend is a distinct
selectable row; changing either law or ratio requires recalculation before it can be selected.
Until then the graph says `Preview blend`, and after row selection it shows the same explicit
single/blend identity as the decision evidence. Polymer selection is the actual server-produced
term-count result, not the requested policy. A save is disabled until a row is selected, its reason
is present and any row warning is acknowledged.

One exact Test Data/Processing Output revision may branch into several independently calculated and
saved models. For example, Swift, Voce and a Swift/Voce blend can share the same tensile input while
retaining different method/version/options, parameters, fit domain, diagnostics and engineer
decision. Saving one branch never updates or supersedes its siblings. Each promoted Material Model
IR revision pins one exact saved branch, and each Solver Card pins that IR revision plus one explicit
target tuple and mapping digest. Several Solver Cards may therefore coexist for the same experiment.
A current pointer is only a workspace convenience; it never rewrites these links or makes a sibling
the implicit source.

The normal GUI identifies the branch by its selected model identity and keeps the common experiment,
material state and condition in the page/session context. It does not use a source test name or an
ambiguous label such as `r1` to distinguish model branches. Exact Test Data, Processing Output,
selected-model/IR and Solver Card revision links remain inspectable in Advanced/Evidence and history.
`Open in Fit` returns to the exact selected branch, not the newest branch derived from that test.

### 7.6 Export stage

Flow:

1. selected, saved model is pinned;
2. choose one exporter-declared target tuple; Output unit system remains a visible selector so the
   tuple is explicit even when the current exporter offers one supported value. Supported values are
   selectable; capability-declared unavailable values may be visible but disabled with their reason;
3. run the Export check and disclose mapping consequences;
4. resolve required missing values;
5. acknowledge approximations when present;
6. preview native card;
7. download and save/link to the Material Library.

Export is a setup/result workspace. The left setup pane contains only the selected model identity,
Destination and Export check. It does not repeat physical properties, lineage flags or generated
output labels. The result side keeps the native Solver Card preview dominant and may divide its
bounded secondary column between Mapping details and a compact family-specific Fit source preview.
This secondary column is read-only result context, not a permanent control inspector. Mapping rows
use one compact title/value/status grammar; explanatory paragraphs, technical mapping counts,
identifiers and receipt mechanics remain under Advanced or Delivery details.

The Export check uses three user-facing states:

- `Ready to create`: zero blockers and no unacknowledged review item;
- `Review required`: zero blockers and one or more named approximations awaiting acknowledgement;
- `Cannot create`: one or more missing, stale, unsupported or unsafe prerequisites.

Source Material/State/model values are read-only in Export. A physical value such as Density appears
once in Mapping details when it affects the target representation; changing it requires an upstream
governed revision. Changing the target tuple changes only the deterministic output representation
and invalidates the current preview/delivery pointer. Mapping details show source value/unit, target
value/unit or representation and one concise user consequence. Material State retained only as
applicability context is not counted as a successful solver-field mapping.

Output unit system is never presented as an unexplained read-only value. The selector is populated
from the exporter capability response. With one supported option it remains visible and exposes that
no other unit system is available; with several supported options it permits a change. An unsupported
value is not accepted and then rejected by a warning dialog or a disabled Create action. If the
capability response declares an unavailable option and reason, the option may be shown disabled.
A valid unit-system change clears preview, acknowledgement and delivery pointers and requires a new
Export check.

Readiness is stated once in Export check as `Ready to create`, `Review required`, or `Cannot create`,
with one short blocker, review item or next action. Preview and Mapping details must not restate the
same failure in competing prose or large alert fields. The compact Fit source plot computes axis
headroom as a ratio of its displayed data span, preserves a meaningful zero anchor where required,
uses family-specific quantities/units and keeps the legend in a curve-free plot quadrant. Normal
content has no decorative scroll rail; genuine long native or mapping content scrolls locally with
a visible, proportional affordance.

User-facing mapping language is consequence-first (`Values unchanged`, `Converted`,
`Native formatting`, `Review required`, `Not supported`, `Context only`). The exporter-owned
`exact`, `transformed`, `approximated`, `ignored`, `unsupported` and `not_applicable` values remain
available in Advanced mapping details and are never silently changed. Reformatting immutable values
as native ASCII rows is not presented as a numerical conversion.

The visible mapping rows and Fit source preview are family-specific:

- metal elastoplastic: density, elasticity, initial yield, hardening response, extension and
  temperature/rate applicability;
- linear viscoelastic: density, instantaneous/long-term elastic convention, shear/bulk Prony terms
  and temperature shift/applicability;
- hyperelastic or hyper-viscoelastic: density, strain-energy terms, volumetric response, available
  test modes and optional Prony terms.

A hyperelastic source preview may switch among or overlay uniaxial, biaxial, planar and volumetric
responses. It must not force those different quantities into a metal stress/plastic-strain chart.

## 8. Activity workspace

Default view is one compact queue, not a dashboard:

```text
Needs attention | In progress | Recent outcomes
```

- **Needs attention** contains pending review requests only for Reviewer and Administrator, with one
  row-level Review command.
- **In progress** contains the browser-local Modeling session and a User's own pending review
  requests. A User cannot approve or request changes here.
- **Recent outcomes** contains returned immutable review decisions and browser-local solver-card
  preview/download history.
- The review API currently supplies immutable request/revision data but not readable submitted-item
  or actor names. The normal row therefore states task type, request reason, state and time; exact
  identifiers remain in Advanced evidence until a readable projection exists.

Advanced disclosure:

- Recipe/Batch execution details;
- mapping reports;
- bulk packages;
- low-level attempts and diagnostics.

Selecting an item returns to the exact workspace context instead of a generic dashboard. A Review
action requires a non-empty reason and calls the existing decision API with the request's manifest;
the returned immutable request replaces that row. Request entry, job monitoring and release
projection are follow-up work, not synthetic queue rows.

## 9. Administration workspace

### 9.1 Topology

```text
object navigator ⇆ data grid/list ⇆ property editor / preview
```

Administration must not use a card gallery for schema objects.

### 9.2 Database design flow

```text
Select Table
→ inspect/add Attribute Definition
→ edit unit/quantity/value semantics
→ place Attribute in Layout
→ preview a real Record datasheet
→ publish revision
```

Link Type flow:

```text
Select source/target Tables
→ define forward/reverse labels
→ define cardinality and revision binding policy
→ validate
→ publish
→ test through Related Records
```

Draft edits stay local to the draft revision until Save/Publish. The property editor indicates dirty fields and validation errors at field level.

## 10. Loading, empty, error and job states

### Loading

- preserve the previous selection while fetching a new context;
- use row or pane skeletons rather than blanking the entire page;
- long-running calculation is represented in the status bar and Activity.

### Empty

Empty states provide one next command. They do not contain a marketing paragraph.

### Error

Errors include:

- what failed;
- whether current work is preserved;
- a recovery command;
- technical details in disclosure.

### Disabled commands

A disabled command must expose a reason through adjacent text or tooltip. It must not be a silent grey button.

## 11. Keyboard and pointer interaction

Minimum keyboard contract:

- `Ctrl/Cmd+K`: focus workspace command/search;
- `Ctrl/Cmd+S`: save draft or commit current editable object as applicable;
- `Ctrl/Cmd+Z` / `Ctrl/Cmd+Shift+Z`: undo/redo UI-supported draft operations;
- `Enter`: open/confirm selected row;
- `Space`: toggle comparison/include selection;
- `Esc`: close inspector/disclosure or return one workspace level;
- arrow keys/Home/End: Tree and grid navigation;
- The former `F6` navigator/main/inspector/status cycle was a DUI-01 shell contract. It is not a
  current requirement where the product route has no persistent generic status area.

Context menus are optional accelerators; every command must also have a keyboard-accessible non-context-menu path.

## 12. State continuity

The following must survive route transitions and browser back/forward:

- Materials query, filters, sort, mode, selected Material, selected Record and result scroll;
- pane sizes and collapsed state by viewport class;
- active datasheet tab;
- Modeling session, active stage, selected curves/candidate and graph view;
- Administration selected Table/Attribute/Layout/Link Type and unsaved draft indicator.

URLs identify shareable domain context. Session storage may retain convenience state but cannot be the only source of a shareable selection.

## 13. Component contracts

Required production primitives:

- `ApplicationShell`
- `WorkspaceCommandBar`
- `ResizableSplitPane`
- `NavigatorTree`
- `EngineeringDataGrid`
- `PropertySheet`
- `TabStrip`
- `StatusBar`
- `CurvePlotFrame`
- `PlotToolbar`
- `TaskInspector`
- `SolverCardGrid`
- `NativeCardPreview`
- `TechnicalDisclosure`

These primitives must use one token system and must not depend on legacy `content-card`, `hero`, `module-material-card` or chip-heavy layout classes.

## 14. Reference-to-production contract

Issue #167 freezes the complete service reference set before any production visual change. It covers
Materials search/tree/detail/card; Modeling Data/Process/Fit/Export; Activity user/reviewer/recovery;
and Administration database/table/attribute/layout/subset/link/access edit/publish, at 1366×768,
1440×900 and 1920×1080. Each affected workflow also has the relevant long, empty, loading, blocked
and error state. A reference entry records its static HTML/CSS source, rendered image path and hash,
viewport, date, status, main-agent evaluation and product-owner approval.

Static HTML/CSS plus an approved rendered image are the implementation source and visual authority.
React ports their workspace regions and CSS faithfully while connecting the existing component,
state and backend contracts. It does not invent a replacement topology or add incremental route-level
CSS overrides. This does not require pixel-perfect copying or arbitrary number tuning. Review the
whole task flow, region topology, information priority, readable density, graph/table/tree dominance,
control-result continuity and absence of overlap, clipping and overflow; measurements prevent unsafe
regressions rather than becoming the design objective.

No visual implementation starts until the main agent has opened/evaluated every target image and the
product owner has approved it. Every visual PR supplies registered reference/current side-by-side live
captures to the main agent and product owner before merge. On a failure, make one evidence-backed
correction and re-review; do not retry the same local CSS approach.

The main agent and fresh read-only reviewer independently complete the
[mandatory qualitative owner checklist](visual-acceptance-matrix.md#mandatory-qualitative-owner-checklist)
at original resolution. Numeric scoring and automated measurements cannot override a qualitative
failure. The main agent repeats the judgment after reviewer disposition, and product-owner approval
is the final visual decision.

## 15. Tooling and implementation approach

- Repository specifications are the source of product and domain truth.
- Figma MCP, when connected, is used to review editable layouts and component states.
- Storybook is used for isolated primitive states before legacy CSS cleanup is accepted.
- Playwright is the executable authority for complete workflows and viewport behavior.
- The mandatory visual-work skills are `.agents/skills/desktop-engineering-ui`,
  `.agents/skills/frontend-ui-engineering`, `.agents/skills/web-design-guidelines`, and
  `.agents/skills/webapp-testing`.

Recommended dependency policy:

- prefer existing native React/HTML components where contracts are already met;
- introduce `react-resizable-panels` only for persistent split-pane behavior instead of implementing drag/keyboard resize incorrectly;
- introduce a grid library only if current table/virtualization requirements cannot be met with the existing implementation and bundle budget;
- do not introduce a general-purpose UI kit that forces marketing/SaaS visual defaults.

## 16. Acceptance metrics

### Workflow

- known Material to exact native card: no more than three primary actions after search;
- Material/Record selection updates context without a full-page reset;
- upload-to-card completes without editing JSON;
- all solver mapping blocks and approximation decisions remain explicit;
- user can resume an interrupted Modeling session from Activity.

### Layout

- no major workspace uses a centered fixed-width page container;
- main results/graph is the dominant area;
- panes resize and scroll independently;
- no nested persistent cards;
- no authenticated workspace hero section;
- no route displays a different legacy visual grammar.

### Evidence

Required Playwright scenarios:

1. search → select → direct card preview/download;
2. Browse Tree → exact Record → Related link → return;
3. CSV/XLSX/JSON → Data → Process → Fit → Export;
4. missing card → create card from existing reviewed evidence;
5. Administration Table → Attribute → Layout → Record preview;
6. Link Type → Related Records navigation;
7. interrupted session → Activity → exact resume context.

Required viewports: 1366×768, 1440×900 and 1920×1080.

## 17. Non-goals

- pixel-copying Granta MI or Material Modeler;
- changing numerical algorithms or domain persistence to obtain a visual effect;
- hiding mapping approximations, provenance or revisions from users who open Evidence/Advanced;
- adding new material models or solvers as part of this UI program;
- turning every desktop command into an icon without a label or accessible name.

## 18. Open decisions

- whether the resizable pane implementation uses `react-resizable-panels` or an internal accessible primitive;
- whether Material result column customization is included after P0;
- final shortcut mapping after conflicts with browser defaults are tested;
- whether a detachable/full-screen graph is required after the core persistent graph workflow is accepted.

## 19. UXC information architecture and interaction corrections

Materials has three deliberately separate intentions inside one navigator: scope/tree browse changes
the governed result scope, facets refine that scoped server query, and advanced criteria is an
explicit search task. Result total, rows, pagination and facet counts describe that same query.
Provider and evidence source are distinct facets. Condition-aware properties carry source, revision,
condition and unit; Yield is not shown for polymer or elastomer results.

Modeling uses a session context strip (exact Material/Test Data revision, family, condition and stage)
above one persistent graph. Data owns input mapping; Process owns ordered operations and commit; Fit
owns candidate comparison and explicit selection; Validate owns the pinned non-production reference plan/run/result;
Export owns only an exact allowed source, target, preflight, preview and delivery. Review and Release remain
policy-dependent states, not labels grafted onto Fit, Validate or Export. A task has one primary action and displays unmet prerequisites by
blocked commands. Clearing a stale pointer preserves local inputs and graph context rather than
blanking the workspace; a failed job retains its source/selection and exposes recovery in task and
Activity.
