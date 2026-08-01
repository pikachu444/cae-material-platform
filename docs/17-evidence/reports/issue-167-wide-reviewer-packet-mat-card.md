# Issue #167 reviewer packet — MAT-CARD wide correction

Date: 2026-07-30
Reviewer: fresh configured read-only reviewer
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Acceptance scope

Review the final MAT-CARD result defined by:

- `issue-167-wide-correction-packet-mat-card.md`
- `issue-167-wide-correction-packet-mat-card-qualitative.md`

The initial wide implementation was rejected by the main agent because 1920 still contained the
full-height dark filler and the 3840 native band merely passed a weak proportional cap. The sole
correction activates the linked same-card response at 1920, caps the native surface at 320 CSS px
for all expanded viewports and adds an always-identifiable local rail/thumb when exact native text
overflows.

| Target | SHA-256 |
| --- | --- |
| `materials-card-preview-normal-1366x768.png` | `60497b5fef2239cd17a468b4e8fcf1316e0bccca5b753600aff5f240b21a4372` |
| `materials-card-preview-normal-1440x900.png` | `74f06d51955b1d7b8f95fed9aaa8f17af147ca00435d7e04f619638c977b2f21` |
| `materials-card-preview-normal-1920x1080.png` | `63c0947178da30fadaf16401b780234c6731551e4bf1a54bd1719bbca235eaaa` |
| `materials-card-approximation-blocked-1440x900.png` | `2ea15b1bb5d0984296bab458a7d8572111f816c12f87ba5830ec3cbef7d7be92` |
| `materials-card-unsupported-blocked-1440x900.png` | `688a0fd8bd9d4d72042f2ad21813df3b8f7ede78b128f75d3cfb1a6c63466d6d` |
| `materials-card-preview-normal-2560x1440.png` | `8544204ba6d4508ad6c041ae8ea80ba0cfdb0687d5514d273903b661a77ea427` |
| `materials-card-preview-normal-3840x2160.png` | `8b2ef53ee04164b42a5ce343cb886027d319063b9545f16307e148685e3e96f2` |

Images and measurements are under
`docs/17-evidence/images/issue-167-service-reference/`; lifecycle staging is
`materials-card-wave02.staging.json`.

## Bounded diff and contracts

Review only MAT-CARD packet-owned HTML/CSS/JS, capture/validator, staging/state/measurement and image
diffs. The final expanded topology remains:

`Browse navigator | (bounded exact native card over linked response) | delivery sheet`

The two top-level card regions remain dominant evidence and the 312 px delivery sheet; the graph is
not a third application pane. The response uses the exact six `*PLASTIC` rows from the same native
card, first point `(0, 450 MPa)`, axes `True plastic strain [1]` and `True stress (MPa)`,
data-derived headroom, render-size geometry and compact in-plot legend. No unrelated test or
material data is introduced.

At 1920/2560/3840:

- native exact-text height: 320 px;
- native surface ratios: 0.397 / 0.274 / 0.170;
- response plot ratios: 0.512 / 0.662 / 0.791;
- native scroll range: 80 px;
- reserved gutter: 11 px;
- proportional thumb ratio: 0.799;
- text-to-rail clearance: 32 px;
- wheel-scroll consequence: proven.

1366/1440 retain the already-approved native-preview/delivery topology. Approximation review and
unsupported recovery, exact solver/version/unit/revision/lifecycle, mapping dispositions,
acknowledgement/download gating, Browse tree, tabs, loading/error context and keyboard behavior are
preserved.

## Completed verification and main-agent judgment

- MAT-CARD full capture and validator pass for seven targets plus responsive/state evidence.
- Inventory: 18 families / 72 images.
- Ruff, Node syntax and `git diff --check` pass.
- Zero browser/page errors and page/body overflow.
- Graph aspect/font/stroke/headroom, native-band ratios, delivery width and state contracts pass.
- The main agent opened all seven final targets at original resolution. It accepts the final result
  for review: 1920 no longer presents a giant empty native surface; 2560/3840 assign the extra
  height to the linked engineering result; the exact text rail is visible and does not cover text;
  blocked states remain truthful and recoverable.

## Reviewer duties

Read-only: do not edit, recapture, commit, push or update lifecycle/GitHub state.

1. Re-run all non-mutating packet gates and verify all seven hashes.
2. Open all seven PNGs at original resolution and inspect the bounded diff.
3. Score V-01–V-16 and every applicable mandatory Q item with direct evidence.
4. Pay particular attention to Q-05–Q-09, Q-15, Q-20, exact-card linkage, positive initial yield,
   graph/data headroom, 1920/3840 useful-space allocation, visible local scroll affordance and
   absence of a third top-level pane.
5. Return `approve` or `changes_requested`, hard gates, actionable findings and residual concerns.
