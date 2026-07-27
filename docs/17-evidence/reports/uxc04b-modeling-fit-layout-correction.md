# UXC-04B Modeling Process/Fit layout correction — superseded current-state acceptance

Date: 2026-07-26

## Approval and correction

The product owner approved the **lower proposal only** in
`docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png` on 2026-07-26. It is
the single authoritative visual target for this correction. This report supersedes
only the old **Modeling Fit 99/100** claim in T-97; T-97 Materials and Administration evidence stays
historical and valid.

## Region mapping and hard gates

| Lower-proposal region | Production selector | Acceptance hard gate |
| --- | --- | --- |
| One compact title/context row and right actions | `.modeling-context-strip` | One row; only Advanced, preview/run and the sole save action appear on the right. |
| Four-stage strip | `.modeling-stage-shell` | Exactly `Data | Process | Fit | Export`; Validate/Review remain Advanced/Activity paths. |
| Compact input and process rail | `.modeling-workspace-rail` | 184–210 px; inclusion checkbox and separate icon-only plot visibility. |
| Shallow Fit control band | `.modeling-task-ribbon > .fit-stage-options` | Candidate equations, domain, model pair/contribution, extrapolation/output and graph actions share one graph-adjacent band. |
| Dominant graph with compact legend | `.persistent-modeling-plot`, `.curve-legend` | Graph is below the band, axes/ticks visible at 1366×768, and legend is lower-right rather than a full-width strip. |
| Candidate details on demand | `.fit-evidence-disclosure` | Closed by default and never creates a persistent lower dock or right inspector. |

## Corrected contract

- Process and Fit use a 180–210 px one-line curve/operation rail with independent inclusion and
  icon-only visibility controls.
- Current task controls are shallow and graph-adjacent; Fit uses **Preview changes** and the one
  top-row **Save fit & continue** action.
- The graph has first-viewport axes and legend. Candidate metrics are not graph overlays.
- Model comparison, explicit engineer selection and reason/warning acknowledgement are available
  from the closed **Candidate parameters** disclosure. Recommendation and
  selection remain distinct; no persistent bottom dock exists.
- The compact stepper is `Data | Process | Fit | Export`; Validate/Review remain reachable through
  Advanced and Activity without occupying the normal modeling path.

## Withdrawal

The UXC-04B current Fit acceptance is withdrawn. The current implementation no longer meets the
approved lower proposal: it substitutes a one-row Fit-candidate rail for the configured sequence,
does not expose the active fit step in the shallow heading, duplicates graph range/point actions,
and can leave unused plot height. The permanent approved lower proposal and the official reference
remain authoritative and are not replaced by this withdrawal.

UXC-04C is the completed corrective acceptance slice. Its live captures and replacement structural
scores are authoritative; the measurements and **98** Fit score below remain historical UXC-04B
evidence only, not a current claim.

## Historical verification record

- Focused frontend tests: 2 files, 6 tests passed.
- TypeScript/Vite build and bundle budget passed; the largest Modeling chunk was 118.91 kB.
- The deterministic live browser scenario replaced all six current Process/Fit screenshots at
  1366×768, 1440×900 and 1920×1080.
- The capture opens the on-demand model evidence disclosure, verifies a selectable model, reason entry
  and the sole enabled top-row save action, then closes the disclosure before each final screenshot.

## Measurement acceptance

| Viewport | Rail | Process / Fit ribbon | Process / Fit SVG height | Drawable width / workspace |
| --- | ---: | ---: | ---: | ---: |
| 1366×768 | 184 px | 104 / 104 px | 425.45 / 425.45 px | 79.77% |
| 1440×900 | 192 px | 104 / 104 px | 557.45 / 557.45 px | 79.99% |
| 1920×1080 | 208 px | 104 / 104 px | 737.45 / 737.45 px | 82.74% |

The capture rejects document-level horizontal overflow, a clipped SVG or x-axis label, a clipped
legend, less than 72% drawable graph width, and a non-compact rail. The final screenshots keep the
model-evidence disclosure closed, so the graph stays dominant.

## Historical structural-reference score

| Screen | Topology /25 | Dominant area /25 | Density /15 | Surface /15 | Continuity /10 | Action/disclosure /10 | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Modeling Process | 25 | 25 | 14 | 14 | 10 | 10 | **98** |
| Modeling Fit | 25 | 25 | 14 | 14 | 10 | 10 | **98** |

These historical captures were once scored against the lower proposal. They do not establish current
Fit acceptance after the issues recorded above.

Current evidence:

- `docs/user-guide/images/current/modeling-process-1366x768.png`
- `docs/user-guide/images/current/modeling-process-1440x900.png`
- `docs/user-guide/images/current/modeling-process-1920x1080.png`
- `docs/user-guide/images/current/modeling-fit-1366x768.png`
- `docs/user-guide/images/current/modeling-fit-1440x900.png`
- `docs/user-guide/images/current/modeling-fit-1920x1080.png`
