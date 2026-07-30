# Issue #167 wide correction packet — MAT-CARD

Date: 2026-07-30  
Writer: configured `implementer_luna_max`, one bounded writer for this family  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded result

Correct the already-approved MAT-CARD static reference so the short exact native preview no longer
creates a dominant empty dark surface at 2560×1440 and 3840×2160. Recapture the five-reference
family and add two normal wide-support images:

- `materials-card-preview-normal-1366x768`
- `materials-card-preview-normal-1440x900`
- `materials-card-preview-normal-1920x1080`
- `materials-card-approximation-blocked-1440x900`
- `materials-card-unsupported-blocked-1440x900`
- support: `materials-card-preview-normal-2560x1440`
- support: `materials-card-preview-normal-3840x2160`

Static reference work only. Do not change production React/CSS, common manifest, inventory, common
evidence report, issue/PR state, git state or another family.

## Main-agent finding

The active main agent opened temporary 2560 and 3840 captures at original resolution. The exact
native text remains confined to the upper-left while the full-height dark preview surface consumes
nearly the entire center workspace. Mapping and delivery facts remain compressed into the 320 px
rail. This is a Q-20 failure even though overflow and console checks pass.

## Authorities and contracts inspected by the main agent

- `AGENTS.md`
- `.codex/config.toml` and `.codex/agents/*.toml`
- GitHub #167, common manifest/inventory and evidence sections 76–77
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`, including Q-01, Q-03, Q-05–Q-08 and Q-20
- original WAVE-02 packet and error-evidence correction
- approved MAT-DETAIL shell and MAT-CARD canonical assets/staging/state evidence
- current production contracts:
  - `apps/web/src/material-library.tsx`
  - `apps/web/src/solver-card-delivery.ts`
  - `apps/web/src/solver-card-delivery-ui.tsx`
  - `apps/web/src/modeling-target-preview.tsx`
  - `apps/web/src/modeling-target-delivery.tsx`
  - `apps/web/src/api.ts`, `apps/web/src/types.ts` and solver-card tests

The card route already loads a `MaterialExperience`. Its existing `representativeCurve` is derived
from the exact card preview by the current `curveFromNativeCard` contract. The wide reference may
therefore show the same card's tabulated `*PLASTIC` response; it must not invent an unrelated test,
fit candidate, material property or provenance field.

## Owned paths

Only this writer may edit:

- `docs/00-research/ux-service-reference/materials-card-preview-normal.html`
- `docs/00-research/ux-service-reference/materials-card-preview.css`
- `docs/00-research/ux-service-reference/materials-card-preview.js`
- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- MAT-CARD staging/state/measurement files
- MAT-CARD canonical, responsive and new wide-support PNGs

Do not edit shared MAT-DETAIL/reference CSS/JS, common policy/manifest/inventory/evidence files,
`apps/**` or another family. Preserve all unrelated changes and never reset, clean, stash or discard.

## Required implementation

1. Preserve the approved two-region top-level structure:
   `dominant card evidence | bounded delivery sheet`. Do not add a third application column.
2. At widths below 2200 px, preserve the existing native-preview/delivery topology and task
   priority. At 2560 and 3840, subdivide only the dominant card-evidence region:
   - upper: bounded, independently scrollable exact native text;
   - lower: a persistent linked response plot from the same native card's `*PLASTIC` rows.
3. The wide linked plot must be engineering-correct.
   - x: `True plastic strain [1]`.
   - y: `True stress (MPa)`.
   - The first point is `(0, 450 MPa)`; do not invent a zero-stress plastic-strain origin.
   - Use all exact preview rows, data-relative x/y headroom and nice data-derived bounds.
   - Use a render-size SVG viewBox with stable 10–12.5 px typography and bounded strokes.
     `preserveAspectRatio="none"` and non-uniform glyph scaling are forbidden.
   - Keep a compact in-plot legend such as `Card hardening data`; do not add a horizontal footer.
4. Bound the dark native surface by its task content. At 3840 it must not exceed 45% of the dominant
   card-evidence height; the linked plot must receive at least 40%. Long native text remains locally
   scrollable without expanding or hiding the plot.
5. Keep the delivery sheet at 300–340 px. Preserve exact solver/format, target version, unit system,
   revision/lifecycle, mapping disposition, direct/review/blocked download logic and Advanced
   evidence boundary. Do not duplicate the mapping list beside or below itself.
6. Preserve the Browse tree, selected Record, tabs, approximation acknowledgement, unsupported
   recovery, loading/error context and all existing keyboard behavior.
7. Add deterministic 2560/3840 capture support and writer-owned staging pointers. The common
   manifest remains `/root`-owned.

## Deterministic gates

The capture/validator must prove:

- exact viewport dimensions and device scale factor 1;
- no console/page errors, broken resources, body/document overflow or clipped tree/task text;
- canonical normal/blocked state behavior and all existing responsive/loading/error evidence pass;
- at 2560/3840 the linked graph is visible and derived from the same five `*PLASTIC` preview rows;
- its first point is 0 plastic strain at 450 MPa, both axes retain data-relative headroom and the
  series does not touch the frame;
- SVG viewBox/render aspect mismatch is at most 0.005, no `preserveAspectRatio="none"`, and
  tick/title fonts remain 10–12.5 px;
- at 3840 the dark native preview is at most 45% and the linked plot at least 40% of the dominant
  evidence height;
- delivery sheet width stays 300–340 px and no third top-level pane appears;
- staged hashes match all five canonical and both wide-support images.

Run:

```text
python docs/00-research/ux-service-reference/capture_materials_card_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_materials_card_wave02.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_materials_card_wave02.py docs/00-research/ux-service-reference/validate_materials_card_wave02.py
node --check docs/00-research/ux-service-reference/materials-card-preview.js
git diff --check
```

Return exact changed paths, command results, all seven final image hashes and any residual risk.
