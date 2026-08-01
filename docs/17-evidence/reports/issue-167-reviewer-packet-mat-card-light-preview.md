# Issue #167 reviewer packet — MAT-CARD light native preview

Date: 2026-07-30
Reviewer: one fresh configured read-only Terra High reviewer
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded acceptance

Review the product-owner-directed correction defined by
`issue-167-product-owner-correction-packet-mat-card-light-preview.md`. The owner rejected the dark
console-style native preview and required consistency with the light document/code surface already
used by Modeling Export.

Final targets:

| Target | SHA-256 |
| --- | --- |
| `materials-card-preview-normal-1366x768.png` | `1cdbb5cc46f04116f5c97f66266869669d407e8be1d9ceed4d3211570a589cb2` |
| `materials-card-preview-normal-1440x900.png` | `07359c9cfb4d8c1429f6e046c9b22e8481c5abed9fde06f4b4c0dd535d8f6760` |
| `materials-card-preview-normal-1920x1080.png` | `5003ea1628f12d5d9001a705af2f79e338a1acbf84be410d58dbbfe81d47b07c` |
| `materials-card-approximation-blocked-1440x900.png` | `52235f10f98b4694a7124609d2aae9f6836e14ebe5415e04b24fe20814597697` |
| `materials-card-unsupported-blocked-1440x900.png` | `688a0fd8bd9d4d72042f2ad21813df3b8f7ede78b128f75d3cfb1a6c63466d6d` |
| `materials-card-preview-normal-2560x1440.png` | `e3f4e699756a7d989fd339efbcee7a83d2a69784e59d14547b812f0c7e2da7fa` |
| `materials-card-preview-normal-3840x2160.png` | `f120376f1433eadf781465bcc131f47e786ead77006c369c1fe2fdf466e67926` |

All paths are below
`docs/17-evidence/images/issue-167-service-reference/`.

## Implementation and preserved contracts

The correction changes only the native preview visual grammar and its capture/validation evidence:

- light surface `rgb(247, 249, 250)`;
- ink `rgb(37, 52, 61)`;
- border `rgb(170, 181, 187)`;
- genuine-overflow track `rgb(220, 231, 236)`, divider `rgb(182, 201, 210)`, thumb
  `rgb(78, 129, 149)`.

Exact text bytes, monospace typography, font size/line height, focus, keyboard/wheel scrolling,
two-region topology, 312 px delivery sheet, 320 px wide native cap, linked six-row `*PLASTIC`
response, axes, legend, headroom, selected Record, mapping states and recovery remain unchanged.
The unsupported image is byte-identical because it shows the existing light unavailable state.

## Main-agent verification and judgment

The active main agent:

- reran the full MAT-CARD validator, inventory validator, Ruff, Node syntax, staging hash check and
  `git diff --check`; all passed;
- opened all seven images above at original resolution;
- compared the result with the light Modeling Export Solver Card preview;
- confirmed that 1366/1440 and non-overflow blocked states show no false custom rail;
- confirmed that 1920/2560/3840 retain the visible proportional rail, 80 px scroll range, text
  clearance and wheel consequence;
- found the light document surface coherent, readable and no longer visually isolated from the
  product;
- found no regression in graph dominance, engineering labels, mapping decisions, clipping,
  horizontal overflow, error recovery or role/state meaning.

Main-agent disposition: `accepted`.

## Reviewer duties

Read-only. Do not edit, recapture, update lifecycle, commit, push or touch GitHub.

1. Read the correction packet, exact UI-spec `E-07a`, relevant diff and measurements.
2. Verify all seven hashes and open all seven PNGs at original resolution.
3. Rerun the non-mutating gates from the correction packet.
4. Independently check cross-route light-surface consistency, code-text contrast, non-overflow false
   rails, genuine-overflow rail discoverability, text clearance and graph/wide-space preservation.
5. Score V-01–V-16 and every applicable Q item from
   `docs/01-product/visual-acceptance-matrix.md`, especially Q-03, Q-05–Q-09, Q-15, Q-16 and Q-20.
6. Return `approve` or `changes_requested`, hard-gate failures, actionable findings and residual
   concerns.
