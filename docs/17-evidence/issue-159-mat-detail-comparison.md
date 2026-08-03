# MAT-DETAIL approved/current comparison

Issue #159 bounded evidence for the Response points restoration. The current captures were
regenerated from the verified `960d476` Compose image after reusing `MaterialsScrollRegion`; the approved
references are the registered MAT-DETAIL normal family. The comparison records design and functional
similarity rather than pixel equality.

## Side-by-side captures

| Viewport | Approved reference | Current capture | Result |
| --- | --- | --- | --- |
| 1366×768 | [MAT-DETAIL 1366](../17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png) | [current 1366](../user-guide/images/current/material-detail-1366x768.png) | Pass: compact topology keeps the graph and hides the optional points table. |
| 1440×900 | [MAT-DETAIL 1440](../17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png) | [current 1440](../user-guide/images/current/material-detail-1440x900.png) | Pass: shared header, tabs, graph and delivery/context panes remain aligned. |
| 1920×1080 | [MAT-DETAIL 1920](../17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png) | [current 1920](../user-guide/images/current/material-detail-1920x1080.png) | Pass: Response points heading, compact rows and visible proportional rail match the approved hierarchy. |
| 2560×1440 | [MAT-DETAIL 1920](../17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png) | [current 2560](../user-guide/images/current/material-detail-2560x1440.png) | Pass: 1920px left-aligned bounded cluster; unused right space is preserved. |
| 3840×2160 | [MAT-DETAIL 1920](../17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png) | [current 3840](../user-guide/images/current/material-detail-3840x2160.png) | Pass: same bounded cluster and local response-table rail at the wide Q-20 viewport. |

## Region mapping

| Approved static region | React/CSS target | Functional consequence | Judgment |
| --- | --- | --- | --- |
| Response points heading and ordered-series context | `ResponsePointsTable` in `apps/web/src/material-library.tsx`; `.material-response-points-heading` in `apps/web/src/design/layout.css` | Point count and engineering-unit context are visible without exposing implementation identifiers. | Pass |
| Flat table surface, subtle sticky header and 26px rows | `MaterialsScrollRegion` table markup; `.material-response-points-scroll` and table rules in `layout.css` | Header remains readable while rows move inside the bounded response cluster. | Pass |
| Reserved 13px vertical scrollbar with proportional thumb | Existing `MaterialsScrollRegion` / `.materials-scroll-rail` shared by Materials result/tree regions | Rail appears only when the point series overflows; wheel, keyboard, track click and thumb drag stay local. | Pass |
| Graph/table balance in the overview response cluster | `.material-overview-response-cluster`, `.material-curve-preview`, and `.material-response-points` | The graph and table remain a compact 240px pair; the datasheet does not grow for the full series. | Pass |
| Wide-screen bounded behavior | `.materials-page` 1920px cap plus existing wide layout rules | 2560px and 3840px retain the same left/top work cluster without page-level horizontal overflow. | Pass |

The live capture gate and Playwright scenario verify role/tabindex, sticky-header styling, genuine
vertical overflow, absence of a fake horizontal rail, local wheel/keyboard/pointer movement, and
restoration to the top before capture. Full-screen review remains qualitative; geometry and presence
checks do not replace the region comparison.
