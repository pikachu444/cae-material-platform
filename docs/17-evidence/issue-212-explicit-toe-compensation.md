# Issue #212 explicit toe compensation evidence

## Boundary and baseline

Work started from fetched `origin/main`
`c341679e0e17654c6e13f718cd37044b29423431` on branch
`agent/issue-212-toe-compensation`. The existing pipeline was complete for exact Test Data and
Mapping Profile pins, immutable staged Processing Output Artifacts, deterministic replay, preserved
last-valid preview, stale downstream state, source/processed graph overlays and exact Process Output
input to Fit. It was missing a named toe-compensation method, quality evidence, warning
acknowledgement and the corresponding Process controls. Issue #212 is the first unfinished #117
backlog unit; #209 remains next.

## Primary user journey and acceptance

| Part | Issue-owned journey |
| --- | --- |
| Setup | An authenticated modeler opens **Modeling → Process** with one exact synthetic non-production tensile Test Data revision and its exact Mapping Profile. The source has an intentionally known strain-axis toe offset. |
| Actions | The modeler explicitly adds **Tensile toe compensation**, selects the inclusive linear estimation domain, previews the result, compares source and corrected curves, reviews offset/slope/R²/point count and acknowledges any computed quality warning before saving. The modeler then opens Fit and selects that exact saved Processing Output revision. |
| Visible outcome | Process keeps the persistent graph dominant. The selected operation shows the approved OLS zero-intercept equation, explicit domain, `equipment compliance: not provided`, calculated quality evidence and any acknowledgement requirement. The source and corrected curves remain distinguishable; no correction runs until the operation is added. |
| Persistence/read-back | Saving creates a new immutable Processing Output revision and Artifact containing the exact source/profile pins, ordered `tensile.toe_zero_intercept@1.0.0` step/options, all stages, diagnostics and scalar results. Reload reproduces the same corrected series and Fit consumes that exact Processing Output revision, never `latest`. |
| Preserved state | Original Test Data bytes, source strain/stress series, Mapping Profile and earlier Processing Outputs are unchanged. Stress values are unchanged by toe compensation. Method/version/options and provenance remain explicit. |
| Recovery | Too few selected points, non-finite values, duplicate/reversed strain, incompatible units and non-positive or numerically unstable slope fail explicitly. A changed domain resets acknowledgement and makes downstream state stale while the last valid graph remains visible; correcting the input and previewing again restores a saveable result. |
| Owned scope | One approved tensile zero-intercept method, its contract/domain/API behavior, Process controls, immutable-output/Fit linkage, synthetic fixture, focused tests, documentation and visual evidence. |
| Forbidden shortcuts | No automatic toe detection, hidden enablement, source mutation, generic scale/shift disguise, smoothing/resampling/manual point editing, equipment-compliance estimate, Differential Evolution, production tensile standard/model/threshold choice, route-specific layout override or unrelated #209/#211 work. |
| Exact acceptance | Noiseless offset recovery ≤ `1e-12` strain; bounded-noise recovery ≤ `2e-5`; replay `rtol=1e-12`, `atol=1e-15`; quality warning when R² < `0.995` or absolute offset exceeds the selected-domain width; warning acknowledgement enforced on save; failure/recovery, Artifact/provenance, Fit exact-input, browser and five-viewport geometry gates pass. |

## Approved method policy

The Product Owner approved `tensile.toe_zero_intercept@1.0.0` in issue #212 before implementation.
For the user-selected domain, ordinary least squares fits
`stress = estimated_slope * strain + intercept`. The strain-axis offset is
`toe_offset = -intercept / estimated_slope`, and every output strain is
`corrected_strain = source_strain - toe_offset`; stress is copied unchanged. Eligibility requires
normalized engineering strain `1`, engineering stress `Pa`, finite values, strictly increasing
strain, at least five selected points and a positive numerically stable slope. The method reports
the selected domain, point count, slope, intercept, offset and R². `equipment_compliance` is fixed to
`not_provided`. The warning thresholds and synthetic tolerances above are versioned regression and
review policy, not a production material-acceptance threshold or approved tensile standard.

## Verification record

### Main implementation and live acceptance

- The issue-owned implementation is rooted at `fa54841`; the warning-layout correction is
  `36c898654e2176a06eef868ee7412de22bad1a9e`, both based on exact `origin/main`
  `c341679e0e17654c6e13f718cd37044b29423431`.
- Focused backend/domain/API verification passed 51 tests. Capture contracts passed 67 tests,
  the focused web workbench/plot verification passed 46 tests, the post-correction workbench run
  passed 24 tests, affected Ruff and changed-scope mypy checks passed, and the production web build
  stayed below its lazy-chunk error budget.
- Compose preflight passed for `cmp-local-demo`. The canonical API and web images were rebuilt,
  services became healthy, and the exact Process-to-Fit browser journey passed at 1366×768,
  1440×900, 1920×1080, 2560×1440 and 3840×2160 with browser zoom 100% and DPR 1.
- The final packet is
  `docs/17-evidence/images/issue-212-explicit-toe-compensation/visual-evidence.yaml`. It contains
  71 PNGs plus the manifest: ten exact-main before originals, ten live after originals, 48 direct
  100%-pixel crops and three warning/exact-Fit-source states. Main inspected every unique PNG at
  original resolution. The corrected warning state records a 14×14 checkbox, a 10 px separation
  between acknowledgement and Result, and no warning-label clipping.
- The available physical displays are 2560×1440 and 2560×1600 at 96 DPI and 100% scale. The
  deterministic 3840×2160 CSS viewport proves geometry only; final physical 4K readability remains
  deferred to #223 under the repository-wide policy.

### Independent audit and Product Owner approval

- The first Balanced read-only audit found that Advanced Recipe JSON could retain a warning
  acknowledgement after changing the toe context. Correction `89aae5d9b020c005df4ef48f964da36d17314a74`
  centralized exact method/version/options context normalization. The same auditor then found that
  Undo could restore the historical acknowledgement; correction
  `4ee1ccfd36fea109ac449474f354d2d86df93a76` routed Apply, Undo and Redo through the same
  normalizer and added both bypasses to the realistic regression journey.
- The same implementation-uninvolved auditor reopened the final authority, diff, tests and visual
  packet and approved exact implementation head
  `4ee1ccfd36fea109ac449474f354d2d86df93a76`: blocker 0, major 0 and material-minor 0.
- The Product Owner approved the presented 1920×1080, 2560×1440 and 3840×2160 Process/Fit
  originals and their supporting five-viewport visibility, clipping and layout-bound evidence on
  2026-08-13. This approval does not convert the automated 3840×2160 viewport into physical 4K
  evidence; that product-wide readability gate remains assigned to #223.
- Draft PR #244 targets `main`; the PR/merge SHA and next-unit read-back record are appended after
  publication completes. The next unfinished #117 unit is #209.
