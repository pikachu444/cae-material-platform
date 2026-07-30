# Issue #167 wide correction packet — MOD-DATA

Date: 2026-07-30  
Writer: configured `implementer_luna_max`, one bounded writer for this family  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded result

Correct the already-approved MOD-DATA static reference so its normal graph is professional and
geometrically uniform at 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160. Recapture the
complete five-reference family and add two normal wide-support images:

- `modeling-data-normal-1366x768`
- `modeling-data-normal-1440x900`
- `modeling-data-normal-1920x1080`
- `modeling-data-empty-new-session-1440x900`
- `modeling-data-long-invalid-mapping-blocked-1440x900`
- support: `modeling-data-normal-2560x1440`
- support: `modeling-data-normal-3840x2160`

Static reference work only. Do not change production React/CSS, common manifest, inventory, common
evidence report, issue/PR state, git state or another family.

## Main-agent finding

The active main agent opened temporary 2560 and 3840 captures at original resolution. At 3840 the
graph renders at 3609×1740 while its fixed SVG remains `viewBox="0 0 1000 500"` with
`preserveAspectRatio="none"`. The plot box ratio is 2.074 while the viewBox ratio is 2.0. SVG text
and strokes scale independently from the stable 11–14 px application typography, making axis labels
and values visibly oversized and non-professional. Page overflow and console checks pass, but Q-07
and Q-20 fail.

## Authorities and contracts inspected by the main agent

- `AGENTS.md`
- `.codex/config.toml` and `.codex/agents/*.toml`
- GitHub #167, the common manifest/inventory and evidence sections 76–77
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`, including Q-02, Q-05, Q-07, Q-08 and Q-20
- original WAVE-01 packet and correction:
  - `issue-167-implementer-packet-mod-data-wave-01.md`
  - `issue-167-correction-packet-mod-data-wave-01.md`
- approved MOD-DATA HTML/CSS/JS, canonical images, staging and state evidence
- current production contracts:
  - `apps/web/src/common-processing-workbench.tsx`
  - `apps/web/src/modeling-data-intake.tsx`
  - `apps/web/src/design/modeling-workspace-layout.tsx`
  - `apps/web/src/engineering-curve-plot.tsx`
  - `apps/web/src/api.ts`, `apps/web/src/types.ts` and current Modeling tests

Preserve the existing exact Test Data revision, Library/Local file/Test Data JSON sources, selected
curves, raw/original/normalized unit semantics, invalid-mapping recovery, preview-not-saved state,
rail resizing and later-stage invalidation contracts. The current React plot already derives padded
bounds from data and builds its SVG geometry from the actual render size; the static reference must
freeze the same structural behavior without implementing production code.

## Owned paths

Only this writer may edit:

- `docs/00-research/ux-service-reference/modeling-data-normal.html`
- `docs/00-research/ux-service-reference/modeling-data.css`
- `docs/00-research/ux-service-reference/modeling-data.js`
- `docs/00-research/ux-service-reference/capture_modeling_data.py`
- `docs/00-research/ux-service-reference/validate_modeling_data.py`
- MOD-DATA staging/state/measurement files
- MOD-DATA canonical, responsive and new wide-support PNGs

Do not edit shared policy/manifest/inventory/evidence files, `apps/**`, Materials sources or another
writer's files. Other work exists in the worktree; do not reset, clean, stash or discard it.

## Required implementation

1. Replace the fixed-distortion plot contract with render-size geometry.
   - The SVG viewBox width and height must match its measured CSS-pixel render box after each resize.
   - `preserveAspectRatio="none"` is forbidden.
   - Recompute grid, ticks, axis titles and each series from the same synthetic source values using
     fixed CSS-pixel margins. A `ResizeObserver` or equivalent bounded renderer is acceptable.
   - Use non-scaling strokes or exact render-size coordinates so grid/curve thickness and 10–12.5 px
     graph typography stay visually stable across all five viewports.
2. Preserve data-relative headroom. The observed maximum must not touch the top/right axes. Do not
   hard-code a viewport-specific maximum; derive a nice bound from the data and current 10% policy.
3. Preserve engineering semantics.
   - x: `Engineering strain` with dimensionless unit represented consistently.
   - y: `Engineering stress (MPa)`.
   - A zero/zero origin is valid for this total engineering stress/strain preview.
   - Legend stays compact and collision-free; do not create a wide footer row.
4. Keep the graph dominant at wide sizes. It may use the elastic remaining region; do not center it
   in a fixed-width wrapper, add fabricated prose, stretch controls or introduce a third inspector.
5. Preserve normal, empty, invalid, loading and error state behavior. The invalid state must retain
   the prior graph-height correction and stale-preview boundary at all canonical responsive sizes.
6. Add deterministic 2560/3840 capture support and writer-owned staging pointers. Do not change the
   common manifest; `/root` integrates it after review.

## Deterministic gates

The capture/validator must prove:

- exact viewport dimensions and device scale factor 1;
- no console/page errors, broken resources, body/document overflow or clipped task text;
- at every normal viewport, viewBox ratio and rendered SVG ratio differ by at most 0.005 and
  `preserveAspectRatio` is not `none`;
- SVG tick/title computed fonts stay within 10–12.5 px and axis titles/ticks remain within the graph;
- grid and curve strokes remain within a bounded CSS-pixel range and do not scale with viewport;
- both axes retain data-relative headroom; the plotted series never touches its top/right frame;
- normal curve selection, graph controls, source tabs, navigator resizing and keyboard behavior
  retain measurable consequences;
- empty/invalid/loading/error assertions and all existing responsive evidence still pass;
- canonical images and both wide-support images match their staging hashes.

Run:

```text
python docs/00-research/ux-service-reference/capture_modeling_data.py --all-packet-targets --responsive-evidence
python docs/00-research/ux-service-reference/validate_modeling_data.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_data.py docs/00-research/ux-service-reference/validate_modeling_data.py
node --check docs/00-research/ux-service-reference/modeling-data.js
git diff --check
```

Return exact changed paths, command results, all seven final image hashes and any residual risk.

