# Issue #167 correction packet — MAT-CARD shared Mapping details grammar

Date: 2026-07-30
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
Main agent: active `/root`
Writer: one configured `implementer_luna_max`

## Bounded result

Correct only the MAT-CARD static reference so its Mapping details use the same compact
title/value/plain-status grammar already accepted in Modeling Export. This is a product-owner
finding raised after the light-preview review. It does not authorize production React/CSS or a
redesign of either route.

## Evidence inspected by the main agent

- Current MAT-CARD:
  `docs/17-evidence/images/issue-167-service-reference/materials-card-preview-normal-1440x900.png`
- Common grammar reference:
  `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1440x900.png`
- MAT-CARD source:
  `docs/00-research/ux-service-reference/materials-card-preview-normal.html`,
  `materials-card-preview.css`, `materials-card-preview.js`
- Export grammar source:
  `docs/00-research/ux-service-reference/modeling-export-normal.html`,
  `modeling-export.css`, `modeling-export.js`
- Shared UI contract:
  `docs/01-product/desktop-engineering-ui-spec.md`, `E-06b`
- Production mapping:
  `apps/web/src/material-library.tsx` →
  `apps/web/src/solver-card-delivery-ui.tsx::MappingStatusList`

The defect is exact: MAT-CARD currently renders uppercase bordered pills in a 93 px leading column
and long explanatory copy, while Modeling Export renders a compact title and source→target value
with a plain consequence aligned at the right. These are projections of the same mapping item
contract and must not remain separate visual grammars in the future React port.

## Required visible grammar

1. Rename `Mapping summary` to `Mapping details`.
2. Every visible row uses `minmax(0, 1fr) auto`: title and one compact value/representation on the
   left, plain sentence-case consequence on the right.
3. Use only the user-facing consequences `Exact`, `Converted`, `Review required`, `Reviewed` and
   `Not supported` in the normal surface. Do not display uppercase API classifications.
4. Remove borders, radius, padding and badge silhouettes from row status text.
5. Replace prose with decision-relevant values from the existing synthetic reference:

   | Title | Compact value/representation | Consequence |
   | --- | --- | --- |
   | Density | `7 800 kg/m³ → 7.8000E+03 kg/m³` | `Exact` |
   | Isotropic elasticity | `210 GPa, ν 0.30 → *ELASTIC` | `Exact` |
   | Initial yield | `450 MPa at εp = 0 → first *PLASTIC row` | `Converted` |
   | Hardening response | `5 points → native *PLASTIC rows` | `Converted` |
   | Post-necking extension | `Bounded extension → target behavior` | `Review required`, then `Reviewed` after acknowledgement |
   | Damage initiation · GISSMO | `No governed target representation` | `Not supported` |

6. Retain the existing exact mapping, approximation acknowledgement, unsupported blocker,
   download enablement and recovery contracts. The acknowledgement changes the visible mapping
   consequence in place; it does not alter or recreate the immutable report.
7. Rename the disclosure to `Technical mapping details`. Keep IDs, checksums, raw classifications
   and any counts inside that disclosure.
8. If a mapped-count label is shown, derive it from currently visible mapping rows; do not hardcode
   a count that becomes stale across normal/approximation/unsupported states.

## Preserve

- Current Materials shell, navigator/tree alignment, tabs and selected Record.
- Light native preview surface, exact native bytes, local overflow rail and wide 320 px cap.
- The linked six-row `*PLASTIC` response, true-stress/true-plastic-strain labels, positive initial
  yield, data-relative headroom, stable SVG typography and in-plot legend.
- Delivery properties and its bounded width.
- Normal, approximation, unsupported, long, loading and error state behavior.
- Approved Modeling Export sources and images byte-for-byte.
- No production React/CSS changes.

## Owned paths

The writer may change only:

- `docs/00-research/ux-service-reference/materials-card-preview-normal.html`
- `docs/00-research/ux-service-reference/materials-card-preview.css`
- `docs/00-research/ux-service-reference/materials-card-preview.js`
- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-wave02.staging.json`
- MAT-CARD PNG and measurement/state-evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit the common manifest, inventory, evidence report, product/UI specifications, Export
family, production files, Git state or GitHub.

## Deterministic gates

Capture all five canonical targets, 2560×1440 and 3840×2160 normal support, and the existing
responsive/evidence-only states. Extend measurements and validation to prove:

- title is `Mapping details` and disclosure is `Technical mapping details`;
- every visible row has one title, one compact source→target value/representation and one allowed
  plain status in the trailing column;
- no status has a visible border, rounded badge or uppercase API classification;
- acknowledgement changes `Review required` to `Reviewed` while preserving the report and enabling
  only the existing exact `.rad` command;
- no row/status/text clipping or overlap at 1366, 1440, 1920, 2560 or 3840;
- all existing native-scroll, graph, state, keyboard, recovery, hash and lifecycle assertions pass;
- Modeling Export files and its six registered approval images remain byte-identical.

Run:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_card_wave02.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_card_wave02.py --all-packet-targets
uv run python docs/00-research/ux-service-reference/validate_materials_card_wave02.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_materials_card_wave02.py docs/00-research/ux-service-reference/validate_materials_card_wave02.py
node --check docs/00-research/ux-service-reference/materials-card-preview.js
git diff --check
```

Open all seven canonical/support images at original resolution before returning. Report every
changed path, final SHA-256, gate result and residual concern.
