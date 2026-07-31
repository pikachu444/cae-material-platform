# Issue #167 product-owner-authorized final correction packet — MOD-PROCESS

Date: 2026-07-31
Writer: configured fresh `correction_terra_high`
Mode: exceptional bounded correction explicitly authorized by the product owner after the exhausted
family correction/re-review lifecycle

## Authority and rejection being corrected

Read and follow:

- `AGENTS.md`;
- GitHub issue #167;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`;
- `docs/01-product/visual-acceptance-matrix.md`;
- `docs/17-evidence/reports/issue-167-correction-packet-mod-process-wide-proportion.md`;
- `docs/17-evidence/reports/issue-167-reviewer-packet-mod-process-wide-proportion.md`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 77, 84–88 and 94.

The fresh reviewer and active main agent rejected the current family for two exact reasons:

1. At 3840×2160, the six-column settings ribbon stretches compact controls across the complete
   workspace width, producing implausible control and line lengths.
2. Long-rail, preview-loading, save-loading, preview-error and save-error evidence exists only as
   geometry JSON. Q-01/Q-09 cannot pass until the actual original-resolution states are persisted
   as PNGs at 1366×768, 1440×900 and 1920×1080.

The product owner explicitly authorized this additional correction. It does not reopen approved
dependencies or authorize production React/CSS, commit, push, PR or merge work.

## Ownership

This writer owns only:

- `docs/00-research/ux-service-reference/modeling-process-normal.html`;
- `docs/00-research/ux-service-reference/modeling-process.css`;
- `docs/00-research/ux-service-reference/modeling-process.js`;
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`;
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`;
- `docs/00-research/ux-service-reference/modeling-process-wave02.staging.json`;
- MOD-PROCESS images, measurements and state/responsive evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

Do not edit the common manifest, common inventory, common freeze report, product/UI specifications,
shared source, another family, production React/CSS or GitHub state. Other agents and the user own
all unrelated worktree changes; do not revert them.

## Required correction

1. Preserve the approved MOD-DATA prerequisite and all existing Process behavior: independent
   selection/inclusion/local plot visibility, five operations in order, preview as non-persistent,
   save as one immutable Processing Output, invalidation behavior and the blocked recovery path.
2. Preserve the current CSS-pixel SVG engineering renderer, finite source arrays, data-derived nice
   bounds/headroom, zero anchors, complete axes, compact curve-free legend, stable typography and
   non-scaling strokes.
3. Keep 1366×768, 1440×900, 1920×1080 and 2560×1440 graph-first. At 3840×2160 retain the already
   specified flat ten-row `Processed response` grid directly below the plot and generated from the
   exact displayed arrays.
4. Bound the 3840 settings controls to compact readable tracks aligned from the start of the ribbon.
   The elastic workspace may remain wide; individual fields and helper text must not grow to fill
   it. Do not add a card, filler prose, a permanent inspector or a second action group.
5. Reduce the 3840 graph's vertical dominance to a credible engineering work region while keeping it
   the primary result. The plot must not return to the rejected roughly 3,600×1,700 scale. Use the
   recovered height for the existing exact result grid, not invented information. The validator
   must assert a bounded graph height and a credible graph-to-grid relationship rather than a
   brittle single pixel value.
6. Persist original-resolution PNG and measurement evidence for the genuine long rail and for each
   loading/error state at all three canonical viewports. Use deterministic names and register paths
   and SHA-256 values in `modeling-process-state-evidence.json`. These are supporting state images,
   not new lifecycle inventory entries.
7. The state images must show the same real workspace and retained context. Loading disables
   duplicate action without hiding the selected Test Data or graph; errors preserve the recoverable
   settings/result and expose one concise retry path. The long rail must be visibly reserved,
   proportional and local, and must not cover row text.
8. Do not add internal/developer vocabulary, decorative badges, repeated explanation, arbitrary
   technical values or new product behavior.

## Deterministic gates

Call both helpers with `--help` before capture/validation. Then run:

```powershell
python docs/00-research/ux-service-reference/capture_modeling_process_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m py_compile docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

If the actual capture CLI differs, use the exact option shown by `--help`; never guess a destructive
or broader command. Return changed paths, commands/results, all lifecycle/support/state hashes and
residual qualitative concerns. Do not claim visual approval.
