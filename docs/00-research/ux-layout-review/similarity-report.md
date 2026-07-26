# Responsive prototype and reference similarity report

Status: historical 2026-07-21 approval retained; UXC-00D responsive proposal approved by the product owner on 2026-07-26

## UXC-00D measured proposal

These are the approved proposal measurements captured from Chromium. They supersede the older
five-screen measurements for the UXC-00D production-design decision; they do not rewrite the
historical 2026-07-21 evidence.

| Screen / viewport | Navigator or tree | Dominant data/graph | Optional context | Key density gate |
| --- | ---: | ---: | ---: | --- |
| Materials 1366×768 | 244 | 1,082 | closed | 38 px result row |
| Materials 1440×900 | 264 | 856 | 280 | results wider than context |
| Materials 1920×1080 | 280 | 1,292 | 300 | no horizontal overflow |
| Modeling 1366×768 | 196 | 1,130 graph region / 1,112 SVG | none | 104 px control band; 83.9% graph-width share |
| Modeling 1440×900 | 184 | 1,216 graph region / 1,198 SVG | none | 104 px control band; 85.6% graph-width share |
| Modeling 1920×1080 | 196 | 1,676 graph region / 1,658 SVG | none | 104 px control band; 88.6% graph-width share |
| Activity 1366×768 | none | 1,326 queue | none | 42 px row; one selected item |
| Activity 1440×900 | none | 1,400 queue | none | 42 px row; row-specific next action |
| Activity 1920×1080 | none | 1,872 queue | none | no KPI tiles |
| Administration 1366×768 | 204 object types | 470 object list | 652 editor/preview | three-part topology |
| Administration 1440×900 | 204 object types | 501 object list | 695 editor/preview | 30–34 px rows |
| Administration 1920×1080 | 204 object types | 698 object list | 970 editor/preview | no task-card landing |

The Modeling curve rows expose separate include-in-analysis checkboxes and icon-only plot visibility
commands. `Select fit range`, `Pick point`, and the closed `Candidate parameters` disclosure all fit
inside the 104 px band at every captured viewport. Activity is a compact selected-row queue; it does
not stretch a handful of rows to fill the page. Its role preview is explicitly `Reviewer (target)`
and shows `Request changes`, `Approve`, and `Publish` separately from User request actions; this is
proposal evidence and does not claim the pending Reviewer role is implemented.

### UXC-00D proposal rubric

| Screen | Topology /25 | Dominant area /25 | Density /15 | Surface /15 | Continuity /10 | Action/disclosure /10 | Total | Hard gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Materials | 25 | 24 | 14 | 15 | 10 | 9 | **97** | pass |
| Modeling Fit | 25 | 25 | 14 | 15 | 10 | 9 | **98** | pass |
| Activity | 25 | 25 | 14 | 15 | 8 | 9 | **96** | pass |
| Administration | 25 | 24 | 14 | 15 | 9 | 9 | **96** | pass |

These are structural proposal scores. Product-owner approval for this four-screen proposal is
recorded below; the scores do not claim that the production routes are already implemented.

## Reference-to-prototype mapping

| Prototype | Reference design method adopted | Explicitly excluded |
| --- | --- | --- |
| Materials | Granta continuous browse/list and restrained rows; MDC persistent filter/result/selected-detail relationship | branding, icons, colors, proprietary database naming, exact geometry |
| Material Detail | Granta datasheet density and MDC selected-record continuity | commercial data, logos, product-specific tabs |
| Modeling Fit | Modeler shallow task controls and dominant persistent graph; compact candidate/curve controls | proprietary workflow, constitutive policy, desktop widget styling |
| Modeling Export / CAE Card | Modeler reviewed-result continuity and MDC sequential solver/model/unit/Download | commercial solver catalog and internal implementation assumptions |

## Browser measurements

All dimensions below are CSS pixels measured in the in-app Chromium browser. Outer margin is the sum
of the left and right application-workspace margins.

### Materials

| Viewport | Workspace / outer margin | Explorer | Results | Context | Result row |
| --- | --- | ---: | ---: | ---: | ---: |
| 1366×768 | 1326 / 40 | 244 | 1082 | closed | 38 |
| 1440×900 | 1400 / 40 | 264 | 856 | 280 | 38 |
| 1920×1080 | 1872 / 48 | 280 | 1292 | 300 | 38 |

The governed Database/Profile/Table/Folder/Record tree uses 26 px rows and 12.5 px labels. Its
`Find in tree` control remains fixed above an independent node scroll; a `DP780` query was exercised
in Chromium and retained Database/Profile/Table/Folder ancestors. Up/Down keyboard movement was also
exercised. All eight demo labels, including the depth-6 record, remain untruncated at all measured
viewports. At 1440 px the result table keeps seven decision columns readable without horizontal
overflow. At 1366 px the optional selected-record context closes, leaving 81.6% of workspace width
to results; the governed Tree is not replaced by a family filter.

### Modeling

| Viewport | Workspace / outer margin | Curve tree | Settings ribbon | Graph region | Graph SVG | Graph width share |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 1326 / 40 | 176 | 1150×150 | 1150×469 | 1132×424 | 86.7% |
| 1440×900 | 1400 / 40 | 184 | 1216×154 | 1216×597 | 1198×552 | 86.9% |
| 1920×1080 | 1872 / 48 | 196 | 1676×152 | 1676×779 | 1658×734 | 89.5% |

At 1440×900 the graph region occupies 68.9% of total workbench area, compared with approximately
66.8% in the curve-fitting reference mask. The prior product screenshot exposed a 743×410 SVG;
the revised 1440 layout exposes 1198×552, an increase of 455 px in graph width. Method, response,
domain, weighting, iterations and Fit action are all visible in the first viewport. The left rail now
uses 26 px rows and 12.5 px ordinary string labels (`Specimen 01`, `Specimen 02`, …). No curve label
wraps or overflows. Full source identifiers, revisions and unit mapping move to hover/focus detail or
Evidence rather than consuming three lines per curve.

### Detail and CAE card

| Screen at 1440×900 | Explorer | Main data/preview | Secondary/action |
| --- | ---: | ---: | ---: |
| Material Detail | 238 | 1162 datasheet | 850×356 representative curve inside datasheet |
| CAE Card | 238 | 852 native preview | 310 download/action area |

All measured workspace regions have 0 px radius, no shadow, and zero nested cards. Workspace body
and data text is 14 px, utility/metadata has a 12 px floor, and compact workbench titles are 16–19 px.
Dividers, row selection and whitespace carry
the hierarchy instead of repeated rounded surfaces.

## Rubric

| Screen | Topology /25 | Dominant area /25 | Density /15 | Surface /15 | Continuity /10 | Action/disclosure /10 | Total | Hard gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Materials | 25 | 24 | 14 | 15 | 10 | 9 | **97** | pass |
| Detail | 25 | 23 | 14 | 15 | 10 | 9 | **96** | pass |
| Modeling Fit | 25 | 25 | 14 | 15 | 10 | 9 | **98** | pass |
| Modeling Export / Card | 24 | 24 | 14 | 15 | 10 | 10 | **97** | pass |

The score measures structural similarity, not brand or pixel copying. A prototype can pass only when
the total is at least 85 and every hard gate in the acceptance criteria passes: governed Tree remains,
the main data/graph area dominates, no permanent third Modeling column exists, no nested-card grammar
returns, and the primary solver-card action is visible in context. These scores do not substitute for
the required product-owner decision.

## Review images

- [Materials: rejected implementation, Granta/MDC references, proposal](../../17-evidence/images/ux-layout-review/materials-reference-comparison.png)
- [Modeling: rejected implementation, Material Modeler references, proposal](../../17-evidence/images/ux-layout-review/modeling-reference-comparison.png)
- [CAE card: MDC reference and proposal](../../17-evidence/images/ux-layout-review/card-reference-comparison.png)
- [All 1366, 1440 and 1920 captures](../../17-evidence/images/ux-layout-review/)

## Deviations requiring review

- The Granta reference does not fully show Database/Profile/Table/Folder/Record depth. The prototype
  deliberately includes it because the product contract makes the governed Tree authoritative.
- Materials combines the Granta explorer/list pattern with MDC optional selected context. At 1366 px
  context closes so results retain dominance.
- Modeling uses the Modeler curve-fitting top-ribbon topology rather than permanently showing the
  hyperelastic reference's side settings. The narrow left region is limited to curves/process; current
  settings remain above the graph, preserving graph width.
- The static Tree proves topology, search behavior, ancestor retention, keyboard movement, independent
  scrolling, and label allocation. It does not prove server latency or virtualization at production
  volume; the 10,000-record/150-DOM-row gate remains a T-95 implementation requirement.

## Approval

- Product-owner decision: **approved** on 2026-07-21 after the compact navigator and Tree-search review
- Approved screenshots/commit: `40726f6` and `docs/17-evidence/images/ux-layout-review/`
- Production React/CSS implementation: **authorized**, subject to the same hard gates on live screens

## UXC-00D disposition

The 2026-07-21 decision above remains historical evidence for the earlier five-screen review. The
Materials, Modeling, Activity and Administration proposal captured in
`docs/17-evidence/images/uxc-00d-responsive-design/` was explicitly **approved by the product
owner on 2026-07-26**. It authorizes production React/CSS implementation of the role-aware Activity
queue, Administration three-part workspace, and lower Modeling dimensions, subject to the same
live-screen hard gates. It does not mark any production route as already complete.
