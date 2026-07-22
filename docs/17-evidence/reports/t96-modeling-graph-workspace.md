# T-96 Graph-dominant Modeling workspace

Date: 2026-07-21

## Implemented task structure

The normal Modeling route now presents exactly four tasks:

```text
Data | Process | Fit | Export
```

Data explicitly offers canonical JSON, CSV and XLSX and then exposes exact Test Data plus typed
channel/unit Mapping Profile controls. Process and Fit share one persistent plot. Export opens the
reviewed Material Model IR → Neutral Material → solver mapping/card surface. Recipe, Batch, raw JSON
definitions and full identifiers remain available under Advanced; none of those engines or exact
revision contracts were removed.

## Direct reference comparison

| Directly inspected reference | Reference layout grammar | Applied result |
| --- | --- | --- |
| `docs/00-research/images/gui-reference/modeler-fit-extrapolation.png` | Compact curve list and fitting/extrapolation controls occupy a shallow band; the plot owns the remaining width and height. | One 180–190 px curve/process tree, one shallow settings ribbon and one fluid graph; no permanent right inspector. |
| `docs/00-research/images/gui-reference/modeler-youngs-manual.png` | Curve names are ordinary list text; units belong to controls and axes rather than large source cards. | `Curve 01`–`Curve 03` use 12.5 px normal labels in 26 px rows. Full document key/specimen/exact revision is retained in the title, and MPa/strain units remain on axes/settings. |
| `docs/00-research/ux-reference-gallery/images/material-modeler-curve-fitting.png` | A selected curve owns the visible fit response and nearby parameters. | The selected curve/process step remains highlighted while current-step controls and response/residual/extrapolation share the same work surface. |
| `docs/00-research/ux-reference-gallery/images/material-modeler-hyperelastic-fitting.jpg` | Engineering graph is the dominant region; fitting choices are bounded rather than parallel dashboard cards. | Fit evidence overlays the graph command area and detailed candidate evidence remains scrollable in the settings ribbon. |
| `docs/00-research/images/gui-reference/modeler-create-cae-card.png` | Card creation follows reviewed fitting and keeps solver-native delivery in the same application. | Export is the fourth task and opens Neutral/model mapping, preview and download without switching to a separate product shell. |

The implementation does not copy logos, brand color, commercial names, proprietary icons or
inferred internal algorithms.

## Before and after measurements

- Before: `docs/17-evidence/images/ux-layout-review/rejected-modeling-1440x900.png`; the reviewed layout
  used a permanent three-column workspace and a 743 px graph.
- Approved prototype: `docs/17-evidence/images/ux-layout-review/modeling-1440x900.jpg`.
- Live after: `docs/17-evidence/images/ux-redesign-v2/modeling-fit-1366x768.png` and
  `docs/17-evidence/images/ux-redesign-v2/modeling-fit-1440x900.png`.

| Viewport | Workspace | Curve/process tree | Settings | Graph region | Actual SVG | SVG/workspace |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 1,304.6 px | 180.3 px | toggle; closed by default | 1,124.3 px | 1,099.9 px | 84.3% |
| 1440×900 | 1,376.1 px | 190.1 px | 1,186 × 124 px ribbon | 1,186 px | 1,161.6 px | 84.4% |

At 1366, 295.7 px of the live SVG is visible in the first viewport while the graph keeps its full
1,099.9 px width. At 1440, 303.7 px is visible with settings open. The ribbon can be closed without
changing graph width. There is no third grid column.

The old document-key blocks were replaced by `Curve 01`, `Curve 02`, and `Curve 03`. All three names
fit without ellipsis in the live fixture. Original identifiers are still available through hover and
focus title text. The process list uses the same plain rows and ordinary weight.

## User tasks

```text
JSON / CSV / XLSX → Data mapping → Process → Fit → Export → solver preview/download
```

- Data format selection: one task click plus one format action.
- Process/Fit switching: one click while preserving selected exact Test Data and curve context.
- Current-step controls: visible at 1440; one `Show settings` click at 1366.
- Recipe/Batch: one Advanced disclosure, then the existing typed controls.
- Solver delivery: one Export task click after reviewed fitting; mapping states remain exact,
  transformed, approximated or unsupported according to the existing contract.

## Verification

- `common-processing-workbench.test.tsx` verifies the four task labels, removal of the old Card task,
  compact specimen names with full source title, settings toggle, JSON/CSV/XLSX entry, Advanced
  Recipe/Batch, processing interaction, fitting evidence and Export handoff.
- `engineering-curve-plot.test.tsx` keeps response/residual/selection behavior covered.
- Production build and bundle budget pass; the common Modeling lazy chunk is 102.26 kB and remains
  below the 120 kB budget.
- Live Docker/Chromium verified both viewports and saved the screenshots above.

## Remaining limits

- The 1366 policy intentionally defaults the settings ribbon closed so the graph remains visible;
  controls are one toggle away rather than squeezed into a third column.
- Production constitutive-model approval and solver correlation remain outside this reference UX
  task. Synthetic reference models and existing explicit mapping gates remain authoritative.
