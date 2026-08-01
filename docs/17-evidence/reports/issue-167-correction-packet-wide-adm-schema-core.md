# Issue #167 wide-screen correction packet — ADM-SCHEMA-CORE state truth

Date: 2026-07-30
Correction writer: one fresh configured `correction_terra_high`
Authority: GitHub #167, `AGENTS.md`,
`docs/17-evidence/reports/issue-167-implementer-packet-wide-adm-schema-core.md`, and Q-01–Q-20 in
`docs/01-product/visual-acceptance-matrix.md`.

## Gate failure found by the main agent

The initial wide implementation passes its deterministic assertions and the normal/edit images, but
main-agent original-resolution review rejects two 1920×1080 states:

1. `administration-database-empty-1920x1080.png` says `No Table yet`, while the adjacent preview still
   names `Materials master` and displays its four Layout fields.
2. `administration-table-add-draft-1920x1080.png` correctly says the new Table has no saved Record,
   but still displays the previous `Materials master` Layout fields.

Both states mix the current no-Table/new-Table selection with a stale companion projection. This
fails state truth, selection synchronization, the packet's new-Table truth boundary, Q-12, Q-18 and
Q-20. The sparse preview state may remain sparse; it must not use another Table's Layout as filler.

## Bounded correction

- In the zero-Table state, the wide companion region must not name a Table, Record or Layout that is
  unavailable. Show one concise empty-state consequence, or hide/disable the preview affordance.
- In a new unsaved Table draft, show that no saved Record or Layout projection exists until the Table
  is saved/configured. Do not render `Materials master` Layout rows.
- Keep the saved `Materials master` preview unchanged for normal, edit, loading-with-stale-context,
  error-with-stale-context, saving, save-error, conflict and Attribute states.
- Keep the compact data-first preview, single wide toggle, flat three-pane topology and all approved
  lower-viewport pixels.
- Add deterministic assertions that the zero-Table and new-Table states contain no stale
  `Materials master`, `DP780 synthetic demo steel`, `Material datasheet`, or ordered Layout rows in
  the preview; also assert that the normal state still contains the four ordered fields.

## Ownership and gates

The correction writer owns only:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- ADM-SCHEMA-CORE PNG/measurement outputs produced by the bounded capture.

Do not edit the common manifest, common issue report, product policy, Materials sources, production
React/CSS, GitHub state, or unrelated dirty paths. Other work exists in the worktree; do not reset,
clean, stash, revert or overwrite it.

Recapture the complete ADM-SCHEMA-CORE matrix and the two wide evidence images. Preserve every
listed 1366×768/1440×900 hash in the initial packet, rerun the full family validator and add the
state-truth assertions above. Run Ruff, `node --check`, and `git diff --check`. Return changed paths,
final 1920 approval and 2560/3840 hashes, preserved lower hashes, commands/results and residual risk.
Do not commit, push, open a PR or request product-owner approval.
