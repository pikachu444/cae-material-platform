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

Implementation, independent audit, live evidence, Product Owner visual approval and publication
records are appended here as their gates complete.
