# Desktop Engineering UI Visual Acceptance Matrix

Status: authoritative visual review gate

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
- task controls are property rows, not cards;
- response/residual/extrapolation state is visible in the plot;
- cursor/selection state appears in status bar.

### Modeling Export

Required topology:

```text
Export properties | Native card preview
```

Additional checks:

- native text preview is the dominant area;
- solver/law/unit controls fit in 300–360 px pane;
- approximation/unsupported warning is visible;
- Download is the sole filled primary command;
- detailed mapping evidence is disclosed.

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

The approved Modeling target is the **lower proposal** in
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
The next design-only PR must create responsive prototypes, record region ratios, and receive explicit
product-owner approval before any production React/CSS implementation. Current Activity and
Administration captures are pending-redesign evidence, not target approval.

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
