# Issue #167 implementer packet — MAT-DETAIL wide response density

Date: 2026-07-30
Owner: active `/root` main agent
Writer: one configured `implementer_luna_max`
Prerequisite: the MAT-EXP normal 1366/1440/1920 bundle is product-owner approved.

## Bounded objective

Correct only the `Materials / Datasheet / Overview / normal` family. Preserve its approved compact
navigator, property table, application condition, CAE delivery, tabs, actions and engineering graph
grammar. At 1920×1080 and above, replace the indefinitely enlarged sparse-curve treatment with one
dominant graph plus a compact synchronized point grid derived from the exact same ordered synthetic
response series.

The approval targets remain:

- `materials-datasheet-overview-normal-1366x768`
- `materials-datasheet-overview-normal-1440x900`
- `materials-datasheet-overview-normal-1920x1080`

The 2560×1440 and 3840×2160 captures remain supporting evidence for the registered 1920 target.
They must keep the same graph-plus-grid topology; they do not become new manifest items.

## Main-agent failure record

The main agent opened the current 1366, 1440, 1920, 2560 and 3840 images at original resolution.
The graph geometry, complete axis titles, compact type and 10% data-span headroom pass Q-05, Q-07
and Q-15. The 2560 and especially 3840 images fail Q-20: one low-density curve expands across an
oversized plot while the current response already supplies exact points that can carry useful
engineering detail. The right Application/CAE rail may remain bounded; duplicated prose or invented
metadata must not fill it.

## Authoritative product and contract inputs

- `AGENTS.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`, sections 4.2.1 and 5.6
- `docs/01-product/desktop-engineering-ui-spec.md`, sections 3.4 and 5
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-01–Q-03, Q-05–Q-09, Q-15 and Q-20
- current static sources listed in the ownership section below
- current normal images and 2560/3840 supporting images
- `apps/web/src/material-library.tsx`
  - `MaterialExperience.representativeCurve`
  - `curveFromNativeCard`
  - `loadMaterialExperience`
  - `RepresentativeCurve`
  - `MaterialDetailPage` Overview composition
- `apps/web/src/material-datasheet-projection.tsx`
  - administrator-selected Layout order and typed Record/curve projection

The production files are read-only context. This packet does not authorize production React/CSS.

## Required response contract

Use one explicit ordered synthetic series as the sole source for both the rendered polyline and the
point-grid rows. The series represents total `Engineering strain` versus `Engineering stress (MPa)`;
therefore the zero/zero start is intentional and must not be relabelled as plastic strain.

Use these exact points, in this order:

| Point | Engineering strain | Engineering stress (MPa) |
| ---: | ---: | ---: |
| 1 | 0.000 | 0 |
| 2 | 0.001 | 210 |
| 3 | 0.002 | 420 |
| 4 | 0.003 | 560 |
| 5 | 0.004 | 578 |
| 6 | 0.006 | 596 |
| 7 | 0.008 | 608 |
| 8 | 0.010 | 620 |
| 9 | 0.015 | 638 |
| 10 | 0.020 | 655 |
| 11 | 0.025 | 668 |
| 12 | 0.030 | 680 |
| 13 | 0.040 | 700 |
| 14 | 0.050 | 718 |
| 15 | 0.060 | 735 |
| 16 | 0.070 | 750 |
| 17 | 0.080 | 765 |
| 18 | 0.090 | 778 |
| 19 | 0.100 | 790 |
| 20 | 0.110 | 801 |
| 21 | 0.120 | 810 |
| 22 | 0.130 | 818 |
| 23 | 0.140 | 826 |
| 24 | 0.150 | 832 |
| 25 | 0.160 | 838 |
| 26 | 0.170 | 842 |
| 27 | 0.180 | 846 |
| 28 | 0.190 | 849 |
| 29 | 0.200 | 850 |

Do not sample the SVG path to populate the table. Do not fit, interpolate, resample or smooth. Store
the ordered points once in the static reference and have both projections read that source. The
existing domain derivation remains data-span-relative with 10% upper headroom, a meaningful zero
anchor and nice displayed maxima of 0.25 and 1,000 MPa.

## Required topology and behavior

- 1366×768 and 1440×900: keep the current useful dominant graph and hide the companion grid. Do not
  squeeze, stack or add a decorative scrollbar merely for cross-viewport symmetry.
- 1920×1080, 2560×1440 and 3840×2160: inside `Representative response`, use a flat divided
  graph-plus-grid region. The plot remains visually dominant. The point grid uses the remaining
  width without creating a third application pane or changing the bounded 300 px Application/CAE
  rail.
- Point-grid columns are exactly `Point`, `Engineering strain`, `Engineering stress (MPa)`.
  Keep 12–13 px compact engineering typography, tabular numerals, readable row rhythm and a sticky
  header.
- The point grid has an independent local scrollbar only when the 29 exact rows overflow. Capture
  and validate proportional thumb geometry plus pointer, wheel, Arrow, Page, Home and End
  consequences. At a viewport where all rows fit, omit the fake rail.
- The plot retains complete centered x title, rotated y title, unit-free tick values, compact
  typography, contained legend and curve/frame separation. Rendered box, viewBox, axes, ticks,
  polyline and hit geometry use the same coordinate system at every viewport.
- Preserve the current Materials navigator split and its independent vertical/horizontal scroll
  contract. No graph/table scrollbar may cover tree or table text.
- Preserve selected DP780 Record identity, property/header contents, tabs, application values, CAE
  card rows/actions, status bar and existing keyboard behaviors.
- Preserve every approved Related/empty canonical and responsive image byte-for-byte.

## Static-region to production-contract mapping

| Static region | Preserved production contract |
| --- | --- |
| selected Record and navigator | existing Materials selection and `ResizableSplitPane` continuity |
| property rows | administrator-selected Layout/Attribute and typed Record projection |
| response graph | `MaterialExperience.representativeCurve` / `RepresentativeCurve` |
| response point grid | the same ordered `representativeCurve` points, not a second API or derived series |
| Application condition | current property applicability/material state projection |
| CAE delivery | current linked solver-card availability and actions |

## Forbidden shortcuts

- no production code changes;
- no shared `reference.css`, shared navigator CSS/JavaScript, common manifest, inventory or common
  evidence-report edits;
- no route-specific override pile, non-uniform SVG stretching, raster graph or screenshot embedded
  as content;
- no duplicated help paragraphs, developer vocabulary, fabricated values, IDs, hashes, provenance,
  mapping or workflow filler;
- no mutation of Related/empty images or their responsive siblings;
- no commit, push, PR or merge.

## Writer-owned paths

- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`
- `docs/00-research/ux-service-reference/materials-datasheet.css`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.css`
- `docs/00-research/ux-service-reference/materials-datasheet.js`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.js`
- `docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py`
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`
- the three normal MAT-DETAIL PNG/measurement pairs
- the 2560/3840 MAT-DETAIL supporting PNG/measurement pairs
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-wave01.staging.json`

The main agent owns the common manifest, inventory, policy/spec/matrix and
`issue-167-service-reference-freeze.md`.

## Required deterministic evidence

Capture all three normal targets plus 2560/3840 support. Extend measurements and assertions to prove:

- the exact ordered 29-point source is shared by graph and table;
- 1366/1440 have no visible companion grid and retain useful plot dimensions;
- 1920/2560/3840 have one graph-plus-grid topology, graph dominance and bounded context rail;
- table header/row count/value/unit fidelity;
- real-overflow versus no-fake-rail behavior and all required scroll inputs;
- complete axes, 10% data-span headroom, curve/frame separation, proportional geometry and legend
  containment;
- no clipping, overlap, document overflow, nested cards, console/page errors or hidden actions;
- all frozen Related/empty hashes remain exact.

Run at minimum:

```powershell
python docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py --all-packet-targets
python docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1920x1080 --wide-evidence
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --all-packet-targets --expect-main-agent-status rejected --assert-preserved-hashes
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1920x1080 --expect-main-agent-status rejected --wide-evidence --assert-preserved-hashes
node --check docs/00-research/ux-service-reference/materials-datasheet.js
node --check docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.js
python -m py_compile docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
ruff check docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
git diff --check
```

Return changed paths, commands/results, five final image paths/hashes, measurement summary and any
remaining risk. Do not edit main-owned integration documents.
