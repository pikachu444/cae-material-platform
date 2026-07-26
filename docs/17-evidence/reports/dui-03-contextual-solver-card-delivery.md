# DUI-03 contextual solver-card delivery evidence

Verified on 2026-07-23 against the rebuilt Docker Compose demo and its protected synthetic
non-production data. Scope is GitHub issue #117, `DUI-03`, `FR-IR-005`, `FR-EXP-001`,
`FR-EXP-002`, `FR-UX-001`, `FR-UX-003`, `FR-UX-006`, `FR-UX-009`, `ADR-004`, `ADR-008` and
`ADR-0034`.

## Implemented scope

- The selected-Material context chooses one truthful primary command from mapping evidence:
  direct Download, Preview, Create card, or Start Modeling.
- The same decision is used in Material Detail and CAE Cards. An approximated card does not
  duplicate Preview in the header or show a misleading Download in its row.
- Preview is a two-pane native ASCII/property-sheet workspace. Solver, version, unit system,
  card revision, lifecycle and solver material ID remain visible; UUIDs, checksums and the full
  mapping report remain under Advanced mapping evidence.
- `exact` and `transformed` mappings download without confirmation. `approximated` and `ignored`
  states require one adjacent acknowledgement. `unsupported` names the blocking field and keeps
  generation or delivery disabled.
- A missing target card can be created only from the graph-linked exact Neutral Material revision
  after the existing mapping preflight. The implementation uses the existing synthetic reference
  exporters and does not select a production solver policy.
- If no card or Neutral Material exists, Start Modeling stores the selected exact Material revision
  in the existing browser-local Modeling session before opening Data.
- Successful preview/download activity stores both Material and Solver Card revision IDs in the
  current browser session. Activity exposes the recent task without putting those technical IDs in
  the normal path.
- No backend, database, worker, OpenAPI or domain schema changed.

## Live task and viewport gates

The current-product capture starts at Materials, searches DP780, selects the result, opens Material
Detail and CAE Cards, then opens the graph-linked OpenRadioss card. The live reference mapping
contains one `approximated` field. The script proves Download is disabled before acknowledgement,
checks the adjacent acknowledgement, proves Download becomes enabled, and then opens Activity in the
same browser context to verify the exact-revision activity entry.

| Viewport | Native text region | Property sheet | Native share of split tracks | Horizontal overflow |
| --- | ---: | ---: | ---: | ---: |
| 1366×768 | 942 px | 360 px | 72.4% | 0 px |
| 1440×900 | 1,016 px | 360 px | 73.8% | 0 px |
| 1920×1080 | 1,496 px | 360 px | 80.6% | 0 px |

The fixed-width property sheet remains subordinate while the native artifact gains width. It is a
single divider-separated second pane, not a permanent third inspector or a nested card. The capture
also rejects unfinished async text, `aria-busy`, unsupported demo mappings, redundant exact-mapping
confirmation, multiple filled Material Detail delivery commands and any horizontal overflow.

## Direct reference comparison

The implementation was compared directly with
`docs/00-research/images/gui-reference/modeler-create-cae-card.png`,
`modeler-cae-card-details.png`, and the selected-Material/datasheet references already registered by
DUI-02. It follows their compact target properties, dominant native card text, ordinary property
rows, preview-before-delivery progression and one local command hierarchy. Product-specific
revision, provenance and mapping rules remain explicit instead of copying proprietary decoration.

| Screen | Structure /20 | Density /20 | Data dominance /20 | Command grammar /20 | Disclosure /20 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Selected Material context | 18 | 18 | 17 | 19 | 17 | 89 |
| Material CAE Cards | 19 | 18 | 18 | 19 | 17 | 91 |
| Native card preview | 19 | 18 | 20 | 19 | 18 | 94 |

All target screens exceed 85/100. Topology, dominant-area and nested-card hard gates pass. At
1366×768, the lower mapping states and acknowledgement require vertical scrolling; the warning
itself enters the first viewport and the full adjacent control is visible at taller target
viewports. This bounded limitation preserves readable 12–14 px engineering text.

## Regression

- All 44 web test files and 112 tests pass, including Material, delivery-policy,
  creation/preflight and Activity coverage.
- Production TypeScript/Vite build and bundle budgets pass.
- The existing download APIs remain responsible for native bytes and mapping-report bytes; no
  alternate client-generated native card was introduced.
- The live acknowledged OpenRadioss download returned 5,090 bytes, contained `/MAT/LAW36/`, and its
  SHA-256 matched the exact card revision. The 3,189-byte mapping report contained all 8 mapping
  items and the same mapping-report SHA-256 recorded on that revision.
- Current-product capture registers Material search at all three target viewports, CAE Cards at
  1440×900, native preview at all three target viewports, and browser-local delivery Activity at
  1440×900.
- User-guide screenshot, documentation-impact, architecture, contract lint/OpenAPI compatibility and
  clean-demo verification gates pass. Clean-demo verification retains all three material families,
  exact workflow graph, both DP780 native cards and checksum-verified download evidence.
