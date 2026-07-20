# Responsive prototype and reference similarity report

Status: browser measurements complete; pending product-owner approval

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
| 1366×768 | 1326 / 40 | 220 | 1106 | closed | 43 |
| 1440×900 | 1400 / 40 | 238 | 870 | 292 | 43 |
| 1920×1080 | 1872 / 48 | 248 | 1324 | 300 | 43 |

The governed Database/Profile/Table/Folder/Record tree uses 26 px rows and 12.5 px labels. At
1440 px the result table keeps seven decision columns readable without horizontal overflow. At
1366 px the optional selected-record context closes, leaving 83.4% of the workspace width to the
result area; the Tree is not replaced by a family filter.

### Modeling

| Viewport | Workspace / outer margin | Curve tree | Settings ribbon | Graph region | Graph SVG | Graph width share |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 1326 / 40 | 186 | 1140×150 | 1140×469 | 1122×424 | 86.0% |
| 1440×900 | 1400 / 40 | 198 | 1202×154 | 1202×597 | 1184×552 | 85.9% |
| 1920×1080 | 1872 / 48 | 204 | 1668×152 | 1668×779 | 1650×734 | 89.1% |

At 1440×900 the graph region occupies 68.2% of total workbench area, compared with approximately
66.8% in the curve-fitting reference mask. The prior product screenshot exposed a 743×410 SVG;
the proposed 1440 layout exposes 1184×552, an increase of 441 px in graph width. Method, response,
domain, weighting, iterations and Fit action are all visible in the first viewport. The left rail uses
12 px labels; each long specimen name uses at most two name lines plus one metadata line with no
horizontal overflow.

### Detail and CAE card

| Screen at 1440×900 | Explorer | Main data/preview | Secondary/action |
| --- | ---: | ---: | ---: |
| Material Detail | 238 | 1162 datasheet | 850×356 representative curve inside datasheet |
| CAE Card | 238 | 852 native preview | 310 download/action area |

All measured workspace regions have 0 px radius, no shadow, and zero nested cards. Workspace body
text is 14 px; compact workbench titles are 16–19 px. Dividers, row selection and whitespace carry
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

- [Materials: rejected implementation, Granta/MDC references, proposal](../../15-demo/images/ux-layout-review/materials-reference-comparison.png)
- [Modeling: rejected implementation, Material Modeler references, proposal](../../15-demo/images/ux-layout-review/modeling-reference-comparison.png)
- [CAE card: MDC reference and proposal](../../15-demo/images/ux-layout-review/card-reference-comparison.png)
- [All 1366, 1440 and 1920 captures](../../15-demo/images/ux-layout-review/)

## Deviations requiring review

- The Granta reference does not fully show Database/Profile/Table/Folder/Record depth. The prototype
  deliberately includes it because the product contract makes the governed Tree authoritative.
- Materials combines the Granta explorer/list pattern with MDC optional selected context. At 1366 px
  context closes so results retain dominance.
- Modeling uses the Modeler curve-fitting top-ribbon topology rather than permanently showing the
  hyperelastic reference's side settings. The narrow left region is limited to curves/process; current
  settings remain above the graph, preserving graph width.

## Approval

- Product-owner decision: **pending**
- Approved screenshots/commit: pending
- Production React/CSS implementation: **blocked**
