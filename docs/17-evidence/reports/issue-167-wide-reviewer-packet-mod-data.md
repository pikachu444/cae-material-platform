# Issue #167 reviewer packet — MOD-DATA wide correction

Date: 2026-07-30
Reviewer: fresh configured read-only reviewer
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Acceptance scope

Review only the MOD-DATA correction defined by
`issue-167-wide-correction-packet-mod-data.md`. The prior approved family is being reapproved because
its fixed 1000×500 SVG was non-uniformly stretched at wide viewports.

Required targets:

| Target | SHA-256 |
| --- | --- |
| `modeling-data-normal-1366x768.png` | `a5a61b1f960575ed5f266d218bc5ff748a4fb986dcc53807604c8e17d0d0e64c` |
| `modeling-data-normal-1440x900.png` | `5e831b9ea26489f44d6b8ef263d104951968f0107aecb983f0cd9ed0ebcefe54` |
| `modeling-data-normal-1920x1080.png` | `fc3fc35693718f5aa5e3902d6b7ade39f8f2009f33c6507fadc6733b517a0fbe` |
| `modeling-data-empty-new-session-1440x900.png` | `c6b7949a32019ef3dc29a3c4dd27444c5a4e466798360c1f76fb650242a105e8` |
| `modeling-data-long-invalid-mapping-blocked-1440x900.png` | `0c661147014fecdb5ad290a9c9ead01d9a389c84f12eb9fe87f6548cbe362356` |
| `modeling-data-normal-2560x1440.png` | `598c842321ff880fecceda86c2b53849e11a704e3d1faa511045c5bb3957ae49` |
| `modeling-data-normal-3840x2160.png` | `1130be05d5567adaeed71f8460a7161826942bc6fa44902d6bc440937e9866be` |

Images and measurements are in
`docs/17-evidence/images/issue-167-service-reference/`. The writer-owned lifecycle index is
`docs/00-research/ux-service-reference/modeling-data-wide-correction.staging.json`.

## Implementation diff

Review the worktree diff limited to:

- `modeling-data-normal.html`
- `modeling-data.css`
- `modeling-data.js`
- `capture_modeling_data.py`
- `validate_modeling_data.py`
- `modeling-data-wide-correction.staging.json`
- MOD-DATA state/measurement/image evidence

The implementation replaces the fixed-distortion SVG with a render-size renderer, data-derived nice
bounds and headroom, stable CSS-pixel margins/fonts/strokes and resize observation. It preserves
exact revision/source selection, original and normalized unit semantics, preview-not-saved status,
invalid-mapping recovery, graph controls, navigator resizing and exceptional states.

After the first review, the main agent overrode its approval because `[MPa]` contradicted the parent
packet and product spec. The sole correction in
`issue-167-wide-correction-packet-mod-data-axis-unit.md` changes the y-axis title to the required
`Engineering stress (MPa)` without changing geometry or behavior. This review is the fresh
post-correction re-review.

## Verification already completed

The writer and main agent report:

- full capture and validator pass for seven targets plus responsive state evidence;
- inventory validator pass: 18 families / 72 images;
- Ruff, Node syntax and `git diff --check` pass;
- no page/body overflow, console/page errors or broken resources;
- viewBox/render aspect mismatch within 0.005, no `preserveAspectRatio="none"`;
- graph font and stroke bounds remain stable;
- data-relative top/right headroom at every normal viewport;
- invalid-state useful graph shares: 0.423 at 1366, 0.524 at 1440, 0.635 at 1920.

The main agent opened all seven targets at original resolution and accepts them for independent
review: graph typography and strokes remain visually uniform from 1366 through 3840, the graph
dominates without unused wide padding, axes/legend do not collide, and empty/invalid states preserve
context and recovery.

## Reviewer duties

Read-only: do not edit, capture, commit or update lifecycle state.

1. Re-run the non-mutating validator, inventory, Ruff, Node and diff gates.
2. Verify every target hash and open all seven PNGs at original resolution.
3. Inspect the bounded source diff and preserved interactions/state contracts.
4. Score V-01–V-16 and every applicable Q item from
   `docs/01-product/visual-acceptance-matrix.md`, with explicit pass/fail/N/A evidence.
5. Pay particular attention to Q-05, Q-06, Q-07, graph dominance, 3840 information use, axis
   semantics, data-derived headroom and fixed CSS-pixel legibility.
6. Return `approve` or `changes_requested`, hard-gate failures, actionable findings and residual
   concerns.
