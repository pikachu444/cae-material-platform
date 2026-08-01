# Issue #167 reviewer packet — MAT-CARD shared Mapping details

Date: 2026-07-30
Reviewer: one fresh configured read-only Terra High reviewer
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded acceptance

Review only the product-owner correction defined by
`issue-167-correction-packet-mat-card-shared-mapping-grammar.md`. MAT-CARD and Modeling Export
project the same solver-mapping item contract, so MAT-CARD must use the accepted compact
title/value/plain-status grammar instead of uppercase bordered pills and repeated explanatory copy.
This is a static-reference correction; production React/CSS is out of scope.

Final targets:

| Target | SHA-256 |
| --- | --- |
| `materials-card-preview-normal-1366x768.png` | `b4f38c0117c13f50b9cefbccf833d389b7a91c8c719961c66b9d2226cf3950a3` |
| `materials-card-preview-normal-1440x900.png` | `05b327f3741f27962bb6dc7ee961071ab3dedb2b840fedc5c94799ea6076c8db` |
| `materials-card-preview-normal-1920x1080.png` | `963ac2613b244caadde2e9f576c9078ebbf6f6138177b8c25c30018797d77fb4` |
| `materials-card-approximation-blocked-1440x900.png` | `6cfe99b8f20b4609c0fc509e79c8013ef13d764ba55166a617cc9b08c2402ec8` |
| `materials-card-unsupported-blocked-1440x900.png` | `8eba256b6a59e6c9d61a7a3b6574e4878952dd62e690703ce25a88764fd1afc6` |
| `materials-card-preview-normal-2560x1440.png` | `0f3d84ac331ed902c208bddc2ba2971b502d1afd5dd4e0f7d4e906d54c9dc71c` |
| `materials-card-preview-normal-3840x2160.png` | `3e8a7747e37ccb99d14e600dd23c60410cd754115b001642e05f6a562ce45d9e` |

All paths are below `docs/17-evidence/images/issue-167-service-reference/`.

## Implementation diff and preserved contracts

Inspect:

- `docs/00-research/ux-service-reference/materials-card-preview-normal.html`
- `docs/00-research/ux-service-reference/materials-card-preview.css`
- `docs/00-research/ux-service-reference/materials-card-preview.js`
- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-wave02.staging.json`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md` (`E-06b`)
- `docs/01-product/service-reference-manifest.yaml`

The normal surface now uses `Mapping details`, `minmax(0, 1fr) auto` rows, one compact
source→target representation and a sentence-case trailing consequence. Allowed consequences are
`Exact`, `Converted`, `Review required`, `Reviewed` and `Not supported`. Raw classifications,
counts and identifiers remain under `Technical mapping details`. Approximation acknowledgement
updates `Review required` to `Reviewed` in place.

Preserve and verify:

- selected Record, light native preview, exact native bytes and genuine local overflow rail;
- bounded Delivery properties, existing download enablement and safe recovery actions;
- true-stress/true-plastic-strain graph, positive 450 MPa initial yield, data-relative headroom,
  stable SVG typography and compact in-plot legend;
- normal, approximation, unsupported, long, loading, error and recovery behavior;
- Modeling Export sources and six approval images byte-for-byte;
- no production React/CSS change.

## Deterministic and main-agent evidence

The active main agent reran the MAT-CARD packet validator, inventory validator, Ruff, Node syntax,
documentation impact, guide/archive comparison and `git diff --check`; all passed. The six
registered Modeling Export approval-image hashes remained unchanged. It independently recalculated
the seven hashes above and opened every image at original resolution.

Main-agent V result: 32/32, no hard-gate failure.

Main-agent qualitative result:

| Item | Result | Evidence / topology reason |
| --- | --- | --- |
| Q-01 | pass | The Materials tree retains its visible independent local overflow grammar. |
| Q-02 | not-applicable | This route has no result-list pane. |
| Q-03 | pass | Tree rows remain compact, aligned and clear of the reserved scrollbar track. |
| Q-04 | not-applicable | This is not the Modeling Fit control topology. |
| Q-05 | pass | Linked-response axes use compact consistent titles/values with no collision. |
| Q-06 | pass | The single linked-response identity remains a compact in-plot legend. |
| Q-07 | pass | Plot geometry is recomputed from rendered CSS pixels without non-uniform stretching. |
| Q-08 | pass | True plastic strain starts at zero with positive 450 MPa true yield stress. |
| Q-09 | pass | The native preview exposes a reserved proportional rail only when content overflows. |
| Q-10 | not-applicable | This is not the multi-candidate Fit legend topology. |
| Q-11 | not-applicable | This route has a Materials catalog tree, not the Fit curve rail. |
| Q-12 | not-applicable | Destination/setup semantics belong to Modeling Export. |
| Q-13 | pass | Mapping details use one compact title/value/status grammar without per-row paragraphs. |
| Q-14 | pass | Exact, review-required and cannot-create consequences are stated once per state. |
| Q-15 | pass | The linked response uses data-derived headroom and remains clear of the frame. |
| Q-16 | pass | Native preview remains dominant; Mapping details stay in the bounded delivery sheet. |
| Q-17 | not-applicable | This route has no Administration object list. |
| Q-18 | not-applicable | This route has no Administration new-definition workflow. |
| Q-19 | not-applicable | This route does not edit Link Type cardinality. |
| Q-20 | pass | At 1920/2560/3840 the graph uses elastic space while rails and native text stay bounded. |

Main-agent pre-review disposition: `accepted`.

## Reviewer duties

Read-only. Do not edit, recapture, update lifecycle, commit, push or touch GitHub.

1. Read this packet, the correction packet, issue acceptance, UI-spec `E-06b`, relevant diff and
   measurements.
2. Verify all seven hashes and open all seven PNGs at original resolution.
3. Rerun the non-mutating deterministic gates.
4. Independently compare the Mapping details grammar with the preserved Modeling Export 1440 image.
5. Score V-01–V-16 and record pass/fail/not-applicable evidence for every Q-01–Q-20 item.
6. Return `approve` or `changes_requested`, hard-gate failures, actionable findings and residual
   concerns.
