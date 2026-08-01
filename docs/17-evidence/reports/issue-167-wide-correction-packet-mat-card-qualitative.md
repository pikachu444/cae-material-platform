# Issue #167 qualitative wide correction — MAT-CARD

Date: 2026-07-30
Writer: configured fresh correction writer
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Why the first wide result is rejected

The first writer satisfied its numeric packet, but the main agent opened all normal images at
original resolution and rejects the result:

- 1920×1080 remains unchanged because the linked plot starts only above 2200 px. The short native
  text therefore sits at the top of a nearly full-height dark surface, recreating the exact
  high-resolution empty-space defect this correction is meant to remove.
- At 3840×2160 the native surface is 41.3% of the dominant region, which passes the prior 45%
  maximum but is still far taller than its exact content. Passing a ratio is insufficient when the
  region visibly reads as unused space.
- 2560×1440 establishes the correct two-band idea, but the native band should be governed by its
  content rather than grow proportionally with viewport height.

This is the sole correction. Preserve the exact card, linked response and delivery contracts from
`issue-167-wide-correction-packet-mat-card.md`; change only the responsive height policy and its
tests/evidence.

## Required result

1. Keep the approved 1366×768 and 1440×900 topology unchanged.
2. Activate the linked response at 1920×1080 as well as 2560×1440 and 3840×2160.
3. At those three expanded viewports, size the native preview from useful content:
   - use a stable bounded height, for example a CSS clamp whose maximum is 440 CSS px;
   - it must remain independently scrollable for a longer native card;
   - it must not exceed 42% of the dominant evidence height at 1920, 34% at 2560, or 24% at 3840;
   - the linked graph receives all remaining height and remains fully visible above the status bar.
4. Do not shrink the native text, add prose, duplicate mapping evidence or add another pane to fill
   space. The useful additional information is the same-card response plot.
5. Preserve the graph semantics and exact six `*PLASTIC` rows:
   `True plastic strain [1]` versus `True stress (MPa)`, first point `(0, 450 MPa)`, data-derived
   headroom, stable 10–12.5 px graph typography, compact in-plot legend and no non-uniform scaling.
6. Preserve normal/blocked/loading/error interactions, two top-level panes and the 300–340 px
   delivery sheet.

## Owned paths

Only the existing MAT-CARD packet-owned HTML/CSS/JS, capture, validator, staging/state/measurement
files and MAT-CARD images may change. Do not touch the common manifest, inventory, common evidence
report, production files, git/GitHub state or another family. Preserve all concurrent work.

## Deterministic and qualitative gates

- Recapture all seven packet targets and existing state evidence.
- Assert the linked plot is visible at 1920, 2560 and 3840 and hidden at 1366/1440.
- Assert the native-band ratios above and an absolute height no greater than 440 CSS px.
- Assert graph containment, data-derived headroom, SVG ratio, font/stroke stability, delivery width,
  state behavior, zero page overflow and zero browser errors.
- Open the final 1920, 2560 and 3840 images at original resolution and verify that neither band looks
  like an empty proportional filler.

Run the same full gate set from `issue-167-wide-correction-packet-mat-card.md` and report all seven
final hashes.
