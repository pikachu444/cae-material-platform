# Issue #167 reviewer packet — WAVE-04 / MOD-EXPORT

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the Modeling Export service-reference bundle:

- preview-ready normal at 1366×768, 1440×900 and 1920×1080;
- exact saved-Fit source blocked at 1440×900;
- named approximation acknowledgement blocked at 1440×900;
- immutable Solver Card delivered at 1440×900.

Normal must retain the exact saved Fit result and exact Processing Output/Neutral revisions, one
selected target/version/unit tuple, internally consistent mapping categories and an ephemeral native
card preview. `Deliver native card` is the sole filled commit action. Source-blocked cannot show a
believable graph/preview/delivery and has one safe `Back to Fit`. Approximation-blocked preserves the
preview but binds one unchecked acknowledgement to the exact named approximation. Delivered creates
one immutable Solver Card and a separate receipt without claiming review, release or an Activity
entry.

Open and inspect all six approval images, six responsive siblings for the three exceptional
approvals, and all twelve responsive state images at original resolution. The state evidence covers
no-target empty, preflight/loading, delivery error with preflight preserved and a 28-row long mapping
sheet. Verify that state labels/actions agree, no-target controls are truly unselected, loading
blocks duplicate preview/delivery, retry uses one coherent command, and all 28 mapping identities are
reachable through a visible local scrollbar without ellipsis.

Score V-01–V-16 and independently complete Q-01–Q-11 from
`docs/01-product/visual-acceptance-matrix.md`. A numeric score cannot override an applicable
qualitative failure. Return `approve` only with at least 28/32, no hard-gate zero, complete evidence
and no applicable Q failure. Do not modify any file.

Authoritative implementation and correction packets:

- `docs/17-evidence/reports/issue-167-implementer-packet-mod-export-wave-04.md`
- `docs/17-evidence/reports/issue-167-correction-packet-wave-04-mod-export.md`

## Approved authority and dependencies

- approved MOD-FIT references registered in
  `docs/01-product/service-reference-manifest.yaml`;
- approved MAT-CARD native-preview/mapping references registered in the same manifest;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`;
- `docs/01-product/visual-acceptance-matrix.md`;
- current Fit/source/revision/mapping/preview/delivery contracts inspected in the implementer
  packet.

Approved sources/images are visual authority. Production React/API sources are read-only contract
evidence.

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1366x768.png`
  — `2e19f612f7ff6edc026f11541e64e32c7c03e75738fcc39af2c17df87d37ab43`
- `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1440x900.png`
  — `514a88da7d0106b1a5522724de58b173bc98998eb543370f681c1c1572493a92`
- `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1920x1080.png`
  — `2798779cb7c87a160a7a41014eb0de690c92dfb672399c513aefc48b20006e7c`
- `docs/17-evidence/images/issue-167-service-reference/modeling-export-source-blocked-1440x900.png`
  — `25cf93f53351919643775fb79789e8a0b9eace914a0c17e131446161cc934554`
- `docs/17-evidence/images/issue-167-service-reference/modeling-export-approximation-blocked-1440x900.png`
  — `374ac6b28dbc5723aac6ae73db1dfe3994eb67ad987c7bde66e8bd974d82efae`
- `docs/17-evidence/images/issue-167-service-reference/modeling-export-delivered-1440x900.png`
  — `de49f9feeec1e90f57d7f89587c450bf903d005d9cececfd8f6eeb3dfb44b134`

Exceptional responsive siblings:

- `modeling-export-source-blocked-responsive-1366x768.png`
  — `2d63942408488907ca6358a6fb994f92bf372db9be7071de7d1699cc00553f6e`
- `modeling-export-source-blocked-responsive-1920x1080.png`
  — `f176fcea6fab3208ac95f50328cf197be594f7b27ca6c4d2226c907216f2d965`
- `modeling-export-approximation-blocked-responsive-1366x768.png`
  — `422de4b305eed53c801df5b79637653d208b9fe65cff2b5de55d76a2e23f6705`
- `modeling-export-approximation-blocked-responsive-1920x1080.png`
  — `b40471f77581d3a6cc19a36174183ca21ffacde3153ab5f01622ff419d32ed20`
- `modeling-export-delivered-responsive-1366x768.png`
  — `a403d1fb6b5148b2741d0178356add0cd114a43ebfc1ef05ffc846cb78c61705`
- `modeling-export-delivered-responsive-1920x1080.png`
  — `9a5ac6ebe00072b720f4aacae12368ff0efc93cc5a61ed1da55be673baf3a4e9`

All twelve other state paths, dimensions and SHA-256 values are recorded in
`docs/17-evidence/images/issue-167-service-reference/modeling-export-wave04.state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/modeling-export-normal.html`
- `docs/00-research/ux-service-reference/modeling-export.css`
- `docs/00-research/ux-service-reference/modeling-export.js`
- `docs/00-research/ux-service-reference/capture_modeling_export_wave04.py`
- `docs/00-research/ux-service-reference/validate_modeling_export_wave04.py`
- `docs/00-research/ux-service-reference/modeling-export-wave04.staging.json`
- the MOD-EXPORT candidate, responsive, measurement and state-evidence files named above;
- the six MOD-EXPORT pending entries in
  `docs/01-product/service-reference-manifest.yaml`.

Production React/CSS, approved dependencies, Activity and other families are outside the review
diff.

## Main-agent original-resolution evaluation

The main `/root` agent rejected the first writer result despite passing its automated checks.
Contradictory per-state labels, mapping-count/visible-row mismatch, a plastic-strain unit error,
missing receipt navigation, unsafe blocked-state command hierarchy and undersized graph text were
corrected. Its subsequent inspection found and corrected an ellipsized source-context value,
untruthful no-target defaults, loading action/status contradictions, an incoherent delivery retry
label and an inaccessible 28-row mapping sheet. The final six approval candidates did not change
during the final evidence-completeness pass.

The final main-agent Q record is:

| ID | Result | Direct evidence / topology reason |
| --- | --- | --- |
| Q-01 | not-applicable | Export has no navigator tree. |
| Q-02 | not-applicable | The right pane is mapping evidence, not a result list; its overflow is evaluated in Q-09. |
| Q-03 | not-applicable | Materials navigation is not mounted in Modeling Export. |
| Q-04 | not-applicable | Fit controls/drawer are upstream; Export mounts only a bounded source graph. |
| Q-05 | pass | Normal and delivered images use compact non-colliding `Yield stress (MPa)` / `True plastic strain [1]` axes with materially reduced unused lanes. |
| Q-06 | pass | The two source identities stay in a compact in-plot legend and never become a wide status/footer row. |
| Q-07 | pass | The source SVG preserves aspect ratio and recomputes responsive geometry without stretched glyphs or strokes. |
| Q-08 | pass | The response is explicitly true yield stress versus true plastic strain and starts at positive yield stress at zero plastic strain. |
| Q-09 | pass | `modeling-export-long-mapping-disclosure-{1366x768,1440x900,1920x1080}.png` exposes a reserved local rail, full wrapped titles and reachable 28-row content; keyboard consequences are recorded. |
| Q-10 | pass | The compact legend occupies a curve-free lower-right plot region across normal viewports. |
| Q-11 | not-applicable | Export's source/target properties pane is not a Fit curve rail. |

## Deterministic and interaction results

```text
family capture from final sources                              pass
pending-lifecycle family validator                             pass, 6 approval targets
approval-exception responsive evidence                         pass, 3 × 1366/1440/1920
same-topology state evidence                                   pass, 4 × 1366/1440/1920
source/target/preflight/mapping count consistency              pass
no-target status/control values                                unselected / placeholders
loading state / duplicate preview-delivery actions             Checking / disabled
delivery-error recovery                                        one Retry delivery
long mapping rows / local rail / full titles                   28 / visible+reserved / wrapped
source graph labels, positive initial yield, legend lanes       pass
target/source invalidation, acknowledgement identity            pass
receipt/card distinction and no review/release claim            pass
pointer/keyboard/ARIA, typography, clipping, page overflow       pass / pass / zero / zero
legacy active-route selectors / nested interactions             zero / zero
console errors / page errors                                   zero / zero
MOD-FIT dependency validator / inventory / Ruff / Node / diff   pass
lifecycle                                                       pending / main accepted / PO absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, the completed
Q-01–Q-11 table, hard-gate failures, actionable findings with direct paths, and residual concerns.
Independently open every approval and evidence image at original resolution and rerun the validator.
Do not edit.
