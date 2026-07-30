# Issue #167 product-owner correction packet — MAT-CARD light native preview

Date: 2026-07-30
Owner: active main agent `/root`
Writer: one configured fresh Terra High correction writer
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Authorization and finding

The product owner rejected the pending MAT-CARD wide handoff because its native CAE Card preview
still uses a near-black console surface while the already established Modeling Export Solver Card
preview uses a light document/code surface. The product owner explicitly instructed the team to
change the surface, inspect the result, report it, and then stop.

This is a bounded product-owner-directed correction after the prior review cycle. It authorizes only
the paths and visual consequence below. Do not change another family, shared manifest/inventory,
common evidence report, production React/CSS, GitHub state, commits, pushes, PRs or merges.

## Direct authority and product judgment

- `docs/01-product/desktop-engineering-ui-spec.md`, `E-07a`, requires the dominant native Solver
  Card preview to use **a light code surface with independent scrolling**.
- `docs/00-research/ux-service-reference/modeling-export.css` is the established sibling grammar:
  surface `#f7f9fa`, ink `#25343d`, border `#aab5bb`, scrollbar track `#dce7ec`, track divider
  `#b6c9d2`, and thumb `#4e8195`.
- A native Solver Card preview is a read-only engineering document, not a terminal or editor. Dark
  console styling has no state or workflow meaning, over-dominates the page and breaks cross-route
  consistency.

## Required implementation

Change only MAT-CARD preview styling and the bounded capture/validation evidence needed to prove it.

1. Replace the MAT-CARD native preview surface and ink with the sibling light code grammar:
   - background `#f7f9fa`;
   - text `#25343d`;
   - border `#aab5bb`.
2. Keep the exact native bytes, monospace font, font size, line height, padding, scroll range,
   readable contrast, focus outline and keyboard/wheel behavior unchanged.
3. Restyle the existing custom overflow affordance as a light native-like reserved rail:
   - track `#dce7ec` with a `#b6c9d2` divider;
   - thumb `#4e8195`;
   - remain visible only when content genuinely overflows;
   - do not cover text or create a false rail at 1366/1440.
4. Preserve the approved two-region MAT-CARD topology, 312 px delivery sheet, 320 px wide native
   cap, linked exact `*PLASTIC` response, graph axes/legend/headroom, selected Record, mapping
   semantics, blocked recovery and every interaction/state contract.
5. Do not add syntax colors, gradients, shadows, terminal chrome, line numbers, explanatory filler,
   a third application pane or arbitrary optical offsets.

## Writer ownership

The writer may change only:

- `docs/00-research/ux-service-reference/materials-card-preview.css`
- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-wave02.staging.json`
- `docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`
- MAT-CARD PNG and measurement evidence under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit HTML or JavaScript unless the existing light-surface validation is impossible; stop and
report before doing so. Other agents and the user have unrelated work in this dirty worktree. Do not
revert, reset, clean, stash or overwrite their changes.

## Required capture and deterministic evidence

Recapture and validate:

- canonical normal: 1366×768, 1440×900, 1920×1080;
- canonical approximation-blocked and unsupported-blocked: 1440×900;
- wide support: 2560×1440 and 3840×2160;
- every existing MAT-CARD long/loading/error/recovery and responsive state.

Add executable assertions for:

- computed preview background equals `rgb(247, 249, 250)`;
- computed native text color equals `rgb(37, 52, 61)`;
- computed preview border equals `rgb(170, 181, 187)`;
- scrollable wide states expose the light track/divider and `rgb(78, 129, 149)` thumb;
- non-overflow normal states do not display a false custom rail;
- text clearance, 80 px wide-state scroll range and wheel consequence remain valid;
- exact text content is unchanged;
- every prior graph/topology/state assertion still passes.

Run:

```powershell
python docs/00-research/ux-service-reference/capture_materials_card_wave02.py --help
python docs/00-research/ux-service-reference/capture_materials_card_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_materials_card_wave02.py --help
python docs/00-research/ux-service-reference/validate_materials_card_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_materials_card_wave02.py docs/00-research/ux-service-reference/validate_materials_card_wave02.py
node --check docs/00-research/ux-service-reference/materials-card-preview.js
git diff --check
```

Open all seven approval/support images at original resolution before handoff. Report every resulting
SHA-256, changed path, gate result and residual concern. Do not update the common lifecycle.
