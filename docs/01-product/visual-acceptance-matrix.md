# Desktop Engineering UI Visual Acceptance Matrix

Status: authoritative visual review gate

## Reference registration and review gate

Before production React/CSS work, #167 registers an approved static HTML/CSS and rendered image for
every target screen/state. The register records direct source/image paths, image hash, viewport, date,
status, main-agent evaluation and product-owner approval. Required coverage is Materials
search/tree/detail/card; Modeling Data/Process/Fit/Export; Activity user/reviewer/recovery; and
Administration database/table/attribute/layout/subset/link/access edit/publish, at 1366×768,
1440×900 and 1920×1080 plus relevant long, empty, loading, blocked and error states.

References are implementation authority, not vague inspiration: port their region structure and CSS
faithfully while preserving backend/state/domain contracts. Each later visual PR gives the main agent
and product owner direct reference/current side-by-side live captures, the interaction/test result and
this rubric. Evaluate full-screen task flow, topology, information priority, readability, dominant
tree/table/graph region, control-result continuity, overlap, clipping and overflow. Pixel-perfect
copying and arbitrary fine-number tuning are not acceptance goals; measurements are safety rails.

## UXC measurement and state evidence additions

Every target route is measured at 1366×768, 1440×900 and 1920×1080 from a live deterministic demo.
The screenshot manifest records executable UI source commit, capture command/date, route, fixture and
viewport; a commit identifier without an actual capture is not capture evidence. The capture settles
async work, has no page-level horizontal overflow, and shows no unfinished checking/loading/
calculating/resolving status.

Acceptance also verifies that Materials total/facet/row values share one server-query scope;
non-metal routes expose no Yield facet; recommendation and selected candidate are distinct; blend
identity names both laws and ratio; upstream changes mark downstream state stale without removing
immutable evidence; and Export offers no artifact action without a current exact source. Validated,
Approved, Released, and Delivered labels require the corresponding audit event.

## Scoring rule

Each route is scored from 0 to 2 for every criterion.

- `0`: missing or contradicts the specification
- `1`: partially implemented or inconsistent
- `2`: fully implemented and verified

A route passes only when:

- total score is at least 28/32 (87.5%, satisfying the repository-wide 85/100 minimum);
- no hard-gate criterion scores 0;
- required screenshots and measurements exist.

The numeric result is necessary but never sufficient. Any applicable failure in the following
qualitative checklist blocks handoff regardless of score.

## Mandatory qualitative owner checklist

This is the canonical record of the cumulative product-owner findings. Every visual
implementer packet links it. After deterministic gates, both the main agent and fresh read-only
reviewer independently open every target/state image at original resolution and record `pass`,
`fail`, or `not-applicable` plus direct image/path evidence for Q-01–Q-20. `Not-applicable` requires
a screen-topology reason. A generic web-guideline audit supplements this checklist but cannot replace
it. After reviewer disposition, the main agent repeats the full-screen judgment and the product owner
makes the final visual approval.

| ID | Qualitative review requirement |
| --- | --- |
| Q-01 | Long navigator trees expose a visible, independent local scrollbar. |
| Q-02 | Long result lists expose a visible, independent local scrollbar; empty results show no fake result scrollbar. |
| Q-03 | Materials navigation uses compact 24–26 px rows, economical indentation/type glyphs, reachable complete identities and no scrollbar/text collision. Disclosure, type glyph and label share one grid row and vertical center; implicit auto-placement onto a second line fails. |
| Q-04 | Fit controls and status do not squeeze the graph; the ribbon stays shallow and candidate parameters use a bounded on-demand drawer while preserving a useful graph. |
| Q-05 | Engineering axes use compact, consistent typography; values, titles and frame do not collide, the x title is not detached, units appear in titles and unused whitespace is materially minimized. |
| Q-06 | Multiple curve identities do not form a wide footer or compete with decision status; the curve legend remains compact and semantically separate. |
| Q-07 | Responsive plots preserve real glyph/stroke proportions; measured plot geometry is recomputed without non-uniform SVG stretching. |
| Q-08 | True-yield-stress versus true-plastic-strain response starts at a positive initial yield stress at zero plastic strain and is not mislabeled as total stress–strain. |
| Q-09 | Overflow affordances are perceptually discoverable in captured pixels with distinct reserved tracks, proportional thumbs and pointer/wheel/keyboard consequences; tree rows remain concise stored identities. |
| Q-10 | Fit legend occupies a demonstrably curve-free plot quadrant and recovers graph width, with geometry-aware alternate placement or compact docked fallback on collision. |
| Q-11 | Fit rail shares the Materials navigator's flat pane rhythm, sentence-case sections, regular identity weight, aligned hierarchy, secondary revision text and restrained selection, while preserving curve-specific controls and its own topology. |
| Q-12 | Export setup identifies the exact branch by its selected model, while the shared experiment/method/condition remains page context. Output unit system remains a capability-backed selector even with one supported value; unsupported alternatives never become a selectable invalid state. Physical properties appear once in Mapping details when they affect output; ambiguous `r1` shorthand, duplicate Source/Output labels, `Saved`, `Pinned`, internal lineage and receipt vocabulary stay out of the normal surface. |
| Q-13 | Export setup and result columns use a consistent compact row grammar. Secondary copy is one short consequence or recovery instruction, not a paragraph squeezed beneath every field or mapping row; technical counts and classifications stay in Advanced. |
| Q-14 | Export readiness is expressed once as `Ready to create`, `Review required`, or `Cannot create`, followed by the exact blocker/review/action. The same state is not restated with competing colors or repeated in setup, preview and Mapping details. |
| Q-15 | Compact engineering plots derive domain headroom from the displayed data span, preserve a physically meaningful zero anchor where applicable, and keep curves clear of the frame. Family-specific axes, units, glyph proportions and legend placement remain correct at every viewport. |
| Q-16 | Export keeps the native solver-card preview dominant. Mapping details and Fit source share a bounded read-only context column; normal content does not show fake scroll rails, while genuine long mapping/native content exposes independent local scrolling without shrinking or obscuring the graph. |
| Q-17 | Administration Object lists use identity-first, family-specific columns. The Name cell contains only the complete/reachable identity; clipped descriptions, quantity/help sentences and duplicated property prose are forbidden. Tables use `Name | Rev`; Attributes use `Name | Value type | Rev`, with full semantics in the adjacent editor. |
| Q-18 | Administration Add commands open a real new-definition draft in the right pane without replacing the navigator, current Table scope or list. Add Table and Add Attribute are exercised; Attribute type changes expose only applicable fields, and a later Layout/Record preview proves that user-selected Attribute revisions drive stored Record values. |
| Q-19 | Administration Link Type and Related/workflow evidence preserve configured `one`/`many` endpoint cardinality and exact revision pins. The UI must support visible one-to-many/many-to-many branching where allowed and must not flatten Material/Test Data/Processing Output/model/Neutral/Solver Card lineage into an implied one-to-one or `latest` chain. |
| Q-20 | At 1920×1080, 2560×1440 and 3840×2160, bounded rails and forms keep readable widths while elastic graph/grid/native-preview or contract-backed Layout/Record/mapping context uses the remaining region. Large avoidable blank regions, uniformly stretched rows/prose, fabricated filler and non-uniform SVG geometry fail; sparse states may remain sparse only when no truthful projection exists. A deliberately under-filled normal search fixture fails when the scoped API already supplies a fuller server page. A sparse Datasheet curve also fails when it expands indefinitely although the same linked response already supplies exact points for a synchronized compact grid. |

An `approve` disposition must include the completed Q-01–Q-20 result. Automated measurements support
the evidence but do not prove visual quality. Any unresolved applicable `fail` requires
`changes_requested`.

## Criteria

| ID | Criterion | Hard gate | Verification |
| --- | --- | --- | --- |
| V-01 | Main task/data appears in first viewport | yes | screenshot |
| V-02 | Desktop menu and command bars replace marketing header | yes | DOM + screenshot |
| V-03 | Workspace uses full width without centered max-width shell | yes | measurement |
| V-04 | Persistent panes use flat divider grammar | yes | screenshot/CSS |
| V-05 | Required panes are resizable or have approved collapse behavior | no | interaction test |
| V-06 | Data/body typography follows 13 px system | yes | computed style |
| V-07 | Pane titles and hierarchy are restrained | no | computed style/screenshot |
| V-08 | Row and control density matches blueprint | yes | measurement |
| V-09 | At most one filled primary command per task context | yes | DOM review |
| V-10 | No nested persistent cards | yes | DOM/CSS review |
| V-11 | Introductory/explanatory copy is minimized | no | copy inventory |
| V-12 | Selection updates context in place | yes | interaction test |
| V-13 | Keyboard navigation covers primary workspace | yes | Playwright/manual |
| V-14 | Status bar reports selection and task state | no | screenshot |
| V-15 | No page-level horizontal overflow | yes | viewport test |
| V-16 | Legacy active-route classes are removed or justified | yes | selector report |

## Route-specific gates

### Materials Search

Required topology:

```text
Menu/Command
Navigator | Data Grid | optional Inspector
Status
```

Additional checks:

- Browse/Search/Subsets share the same navigator area;
- grid columns are resizable;
- result count is not presented as a decorative badge;
- selected material inspector does not exceed 480 px;
- no large page title or description block above the workspace.

### Browse Tree

Additional checks:

- 24–26 px rows;
- local search fixed above tree;
- Database/Profile/Table/Folder/Record depth is visible;
- tree scroll is independent;
- overflowing tree/result panes show a distinct reserved track and proportional thumb in the
  captured pixels; DOM overflow or an auto-hidden native scrollbar alone does not pass;
- the vertical and conditional horizontal tree scrollbars operate by pointer, wheel and keyboard,
  never cover node text and preserve access to the complete stored identity;
- node labels are concise identities with aligned disclosure/type glyphs; descriptive qualification
  prose is not repeated in every row;
- selected Record opens datasheet in adjacent context;
- forward/reverse links remain accessible.

### Material Detail

Required topology:

```text
Optional navigator/list | Datasheet tabs and content
```

Additional checks:

- property sheet uses compact rows;
- `Related` is directly accessible;
- card Preview/Download is visible without scrolling;
- technical identifiers remain under Evidence/Advanced;
- no 32 px blanket content padding.

### Modeling Data / Process / Fit

Required topology:

```text
184–210 px curve/process tree | Persistent dominant plot with shallow graph-adjacent band
```

Additional checks:

- plot remains mounted through task changes;
- actual plot width is at least 72% of workspace at 1440 px;
- curve rows separate inclusion checkbox from icon-only plot visibility;
- curve tree is 184–210 px and controls do not create a permanent third column;
- the Modeling rail and Materials navigator read as one desktop product: flat headings, sentence-case
  section labels, regular 12–13 px identities, aligned hierarchy indentation and the same restrained
  leading-accent selection grammar; stage-specific curve controls remain distinct rather than being
  copied into catalog rows;
- at the minimum rail width, every visible specimen identity/revision is unclipped, the narrow
  plot-color sample does not resemble a badge or branch, and long rail content scrolls locally
  without changing graph width;
- task controls are property rows, not cards;
- response/residual/extrapolation state is visible in the plot;
- the curve legend overlays a measured data-free plot quadrant and does not consume a permanent
  right column; deterministic geometry evidence proves it misses curves, boundaries, axes, labels
  and state overlays at every required viewport, with a docked fallback only when no safe quadrant
  exists;
- cursor/selection state appears in status bar.

### Modeling Export

Required topology:

```text
Destination + Export check | Native card preview | bounded read-only Mapping details / Fit source
```

Additional checks:

- native text preview is the dominant area;
- Destination and Export check fit in a 300–340 px setup pane;
- the Mapping/Fit-source region is read-only result context, not a permanent control inspector;
- physical source values such as Density are read-only and show source/output units when relevant;
- only exporter-declared target tuples are selectable; a one-value version/unit field is not
  presented as a meaningful choice;
- `Ready to create`, `Review required` and `Cannot create` agree with blockers and acknowledgement;
- Material State context is not counted as an exact solver-field mapping;
- native ASCII uses a light code surface and internally consistent target units/values;
- metal, linear-viscoelastic and hyperelastic mapping/plot content use their own quantities without
  changing the approved region topology;
- approximation/unsupported warning is visible;
- Create/Open Solver Card is the sole filled primary command for the current state;
- detailed technical mapping status, JSON, identifiers and receipt mechanics are disclosed.

### Administration

Required topology:

```text
Object navigator | Object list | Property editor / preview
```

Additional checks:

- no task-card landing page in the normal database-design route;
- Table, Attribute, Layout, Subset and Link Type are editable in context;
- Add/Edit/Duplicate/Delete live in command bar;
- Attribute and Link Type editors use property sheets;
- live datasheet preview can be opened adjacent to configuration.

### Activity

Additional checks:

- default view is a work queue/data grid;
- no KPI tile dashboard;
- reviews/jobs/releases use tabs or saved views;
- task action is row-specific.

## Reference and approval disposition

The historical 2026-07-21 Modeling target was the **lower proposal** in
`docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`. Materials references:
`docs/00-research/images/gui-reference/granta-profile.png`,
`docs/00-research/images/gui-reference/granta-list-results.png`, and
`docs/00-research/images/gui-reference/granta-datasheet-embedded.png`. Administration references:
`docs/00-research/images/gui-reference/granta-admin-schema-tool.png`,
`docs/00-research/images/gui-reference/granta-functional-edit.png`,
`docs/00-research/images/gui-reference/granta-admin-layout.png`, and
`docs/00-research/images/gui-reference/granta-record-links-datasheet.png`. Modeling references:
`modeler-start-data.png`, `modeler-youngs-auto.png`, `modeler-youngs-manual.png`,
`modeler-necking-point.png`, `modeler-fit-extrapolation.png`, `modeler-create-cae-card.png`, and
`modeler-cae-card-details.png` in `docs/00-research/images/gui-reference/README.md`, plus the
approved lower comparison above.
UXC-00D records a historically approved four-screen responsive proposal in
`docs/17-evidence/images/uxc-00d-responsive-design/`; it is evidence, not a complete service
reference register. #167 supplies the complete approved target set and supersedes any implication that
the historical four-screen approval alone authorizes later route work. Historical approval never
marks a live route as complete.

## Required measurement report

Every visual PR records:

| Metric | 1366 | 1440 | 1920 |
| --- | ---: | ---: | ---: |
| Menu + command height | | | |
| Workspace outer margin | | | |
| Navigator width | | | |
| Main data/plot width | | | |
| Inspector width | | | |
| Normal pane padding | | | |
| Data row height | | | |
| Body font size | | | |
| Primary command count | | | |
| Nested persistent card count | | | |
| Page horizontal overflow | | | |

## Legacy selector report

Every visual PR lists active-route usage of:

```text
page-stack
page-heading
content-card
module-material-card
hero-actions
eyebrow
status-badge
count-chip
```

Each occurrence must be removed, migrated or explicitly justified as an Advanced/legacy-only exception.
