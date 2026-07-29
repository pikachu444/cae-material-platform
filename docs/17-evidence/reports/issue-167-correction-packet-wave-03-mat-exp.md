# #167 WAVE-03 MAT-EXP product-owner correction packet

Date: 2026-07-29  
Author: main Sol High agent  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Authorization and bounded ownership

Apply the single allowed product-owner correction to the two pending MAT-EXP exceptional references:

1. `materials-search-long-1440x900`
2. `materials-search-empty-1440x900`

The three approved Materials normal references and their sources remain frozen. This correction is a
comparison candidate for the pending images only; it does not reopen an approved lifecycle.

Owned paths:

- `docs/00-research/ux-service-reference/materials-search-exceptional.html`
- `docs/00-research/ux-service-reference/materials-search-exceptional.css`
- `docs/00-research/ux-service-reference/materials-search-exceptional.js`
- `docs/00-research/ux-service-reference/capture_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/materials-search-wave03.staging.json`
- the existing MAT-EXP WAVE-03 candidate, measurement and state-evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit `reference.css`, `reference.js`, `materials-search-normal.html`, any approved image or
measurement, the common manifest/inventory/evidence report, MOD-FIT paths, production paths, or
GitHub. Other agents are working in the same worktree; do not revert or overwrite their work.

## 2. Product-owner finding and source interpretation

The current exceptional references prove mechanical overflow but do not make scrolling discoverable,
and the tree spends too much width on repeated node-type text and indentation. Long identities are
therefore truncated earlier than an engineering catalog browser should tolerate.

The supplied GRANTA MI photographs are not Fit topology authority. They are Materials/Neutral
Material datasheets whose sections and attributes are Administrator-configured Layout content, and
whose graphs render exact linked saved data Records/revisions without client-side reprocessing. Their
applicable lessons for this packet are compact information density, a readable hierarchy, visible
independent scrolling, and preserving longer identity text:

- `.codex-remote-attachments/019fa7c4-2275-7610-9ece-d689a97d7610/6289ff56-374d-4e30-b78a-e8143f23f1ed/1-Photo-1.jpg`
- `.codex-remote-attachments/019fa7c4-2275-7610-9ece-d689a97d7610/6289ff56-374d-4e30-b78a-e8143f23f1ed/2-Photo-2.jpg`
- `.codex-remote-attachments/019fa7c4-2275-7610-9ece-d689a97d7610/6289ff56-374d-4e30-b78a-e8143f23f1ed/3-Photo-3.jpg`

## 3. Required correction

### Tree density and identity

- Use deterministic synthetic catalog content deep and long enough to create real vertical overflow
  in the tree at 1366×768, 1440×900 and 1920×1080 evidence viewports.
- Keep tree rows in the 24–26 px range and tree text at 12–13 px regular/medium.
- Reduce hierarchical indentation to approximately 8–10 px per depth. Do not flatten the hierarchy.
- Remove the repeated full-width right column labels `Database`, `Profile`, `Table`, `Folder` and
  `Record`, and remove visible `Selected · Record` prefix text. Preserve type semantics using a
  compact accessible icon/glyph, `data-kind`, accessible name and `title`/tooltip.
- Show selection through the existing accent/background treatment, not by consuming label width.
- Long labels may ellipsize in the resting view only if the complete identity is available through
  `title`, keyboard focus/tooltip and horizontal scrolling when depth plus identity genuinely exceed
  the pane.

### Discoverable independent scrolling

- Tree and long results must each be independently scrollable where their own content overflows.
- Use a stable scrollbar gutter and visible desktop scrollbar track/thumb styling. The scrollbar
  must be visible in the 1440×900 long candidate image without relying on hover.
- Preserve sticky result headers.
- Page/body and the continuous workspace must not gain horizontal scrolling.
- The empty result region must not show a fake scrollbar when it has no rows. Its populated catalog
  tree may still scroll.
- Wheel and PageDown/keyboard scrolling must produce a measurable local `scrollTop` change without
  moving the document or another pane.

### Preserved state contracts

- Long remains `1–50 of 126 matches`, renders 50 rows, and retains one selected Record plus truthful
  selected context.
- Empty remains zero rows, zero result/tree/context selection and one `Clear search` recovery.
- Search loading/error and tree loading/error retain exactly the context already required by the
  implementation packet.
- Search, tree navigation, row selection, compare cap and both splitters remain operable.
- Do not add columns, cards, badges, recommendations, condition-aware Yield, provider fields or
  client-computed counts.

## 4. Deterministic evidence additions

Update capture/validation so the family-local evidence records and asserts:

- tree and result `clientHeight`, `scrollHeight`, `clientWidth`, `scrollWidth`, overflow mode,
  computed `scrollbar-gutter`, and scrollbar track/thumb styling;
- actual wheel or PageDown before/after `scrollTop` for every overflowing local pane;
- tree row-height range and indentation increment;
- full text, visible text-box width, `title` and accessible type for the longest representative
  Database/Profile/Table/Folder/Record identities;
- selected state without a visible type/prefix width tax;
- sticky result header and 50/126 long count;
- empty state has no result overflow or stale selection;
- zero browser/page errors and zero document/body overflow.

Recreate all existing MAT-EXP WAVE-03 approval, responsive and state evidence so their hashes and
measurements describe the corrected source. Do not change the approved normal-family hashes.

## 5. Required gates and return

Run:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_search_wave03.py --all-packet-targets
uv run python docs/00-research/ux-service-reference/validate_materials_search_wave03.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_materials_search_wave03.py docs/00-research/ux-service-reference/validate_materials_search_wave03.py
node --check docs/00-research/ux-service-reference/materials-search-exceptional.js
git diff --check
```

Open all 18 recreated MAT-EXP images at original resolution. Return changed paths, exact gate
results, both approval-image hashes and any residual risk. Do not edit common lifecycle evidence or
request product-owner approval.
