# Issue #167 Administration remaining — sole correction packet

Date: `2026-08-01`
Branch: `agent/complete-167-and-157`
Rejected candidate baseline: `2bcbbfa`
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
PR: <https://github.com/pikachu444/cae-material-platform/pull/170>

## Role and bounds

This is the one permitted correction after the main-agent qualitative gate rejected the existing WAVE-06 candidates. One configured `correction_terra_high` writer owns this correction. Do not start #157, production React/CSS, a second redesign, a commit, a push, or an approval-state change.

Owned files are limited to:

- `docs/00-research/ux-service-reference/administration-remaining.html`
- `docs/00-research/ux-service-reference/administration-remaining.css`
- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/finalize_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- the corresponding WAVE-06 images and measurement JSON under `docs/17-evidence/images/issue-167-service-reference/`
- `docs/17-evidence/reports/issue-167-administration-remaining-product-owner-packet.md`
- the WAVE-06 section of `docs/17-evidence/reports/issue-167-service-reference-freeze.md`
- the 17 pending WAVE-06 entries in `docs/00-research/ux-service-reference/service-reference-manifest.json`

Preserve every unrelated user or agent change. Do not reset, clean, stash, discard, or rewrite history.

## Authority to read before editing

- root `AGENTS.md`
- `.agents/skills/desktop-engineering-ui/SKILL.md`
- `.agents/skills/frontend-ui-engineering/SKILL.md`
- `.agents/skills/web-design-guidelines/SKILL.md`
- `.agents/skills/webapp-testing/SKILL.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-01–Q-20 and V-01–V-16
- `docs/00-research/ux-service-reference/administration-database-normal-1920x1080.png`
- the rejected WAVE-06 source, captures, measurement JSON, and product-owner packet

## Main-agent rejection evidence

The deterministic validator passed 1,481 checks, but original-resolution review found hard qualitative failures that the existing measurements did not detect.

1. **Wide internal clipping:** all five wide support screens clip their right-hand preview/detail content even though most of the viewport is empty. Examples:
   - `administration-layout-edit-draft-wide-2560x1440.png`: the visible editor grid ends around x=1361 while the preview column geometry continues to x=1767. The screenshot clips the heading and most preview values.
   - The same failure is visible at 3840×2160 and in Subset, Link Type, Access, and Publish wide captures.
   - This violates Q-06, Q-08, Q-11, Q-17, Q-20 and the product-owner rule that meaningful content must not be clipped merely to leave right-side whitespace.
2. **Competing duplicate commands:** Layout and Subset show `Save new revision` in both the page command bar and the editor footer. Link Type additionally duplicates validation/test intent (`Validate`, `Test Related`, and `Validate and test`). The top command bar must be the single canonical location for global validate/preview/test/save actions. Keep only truly local secondary actions such as `Discard draft` in the editor.
3. **Duplicate confirmation escape:** Access revoke confirmation shows `Cancel` in both the page command bar and editor action row. Keep one clear local confirmation action pair next to the destructive action; the command bar should show status only for this state.
4. **Publish command duplication and internal language:** `Publish catalog` is disabled in both the command bar and detail panel. Retain a single disabled canonical command with a concise, visible reason. Remove or rewrite developer/evidence language such as `publication capability boundary`, `publication transition and policy endpoint`, `service exposes no ... endpoint`, and `Not fabricated`. Administrators need to know that publishing is not configured, what remains editable, and what to do next—not API implementation terminology.
5. **Evidence quality gap:** the validator currently accepts internal child overflow because document-level overflow remains zero. Add a deterministic check that every `.remaining-editor-grid`, `.editor-column`, and `.preview-column` stays inside the visible `.remaining-editor-pane`/content bounds and that required headings/actions are not horizontally clipped at every captured viewport, including 2560 and 3840.
6. **Packet hygiene:** remove the existing trailing whitespace on lines 3–5 of `issue-167-administration-remaining-product-owner-packet.md` and update hashes/measurements only after recapture.

## Required correction behavior

- Preserve the approved three-pane Administration topology, compact 12–13 px hierarchy, dividers, scroll behavior, exact-revision language, server-scoped Subset result, one-to-many Link Type branch evidence, task-based Access model, and truthful blocked Publish capability.
- Do not stretch controls, tables, or text merely to fill 2560/3840. Use a bounded left/top-aligned useful cluster whose width is sufficient for all of its children. Trailing whitespace may remain only to the right/bottom.
- At 1366/1440/1920, keep the current density and pane dominance unless required to remove clipping or duplicated commands.
- At 2560/3840, all useful child content must be fully visible within the bounded cluster. The preview/detail column may be wider than the rejected version, but must remain proportional to the editor and must not become an oversized filler region.
- Ellipsis is acceptable only for identity-list values with a deterministic full-value affordance. Headings, action labels, field labels, result column headers, and status explanations must not be clipped.
- Preserve semantic buttons/labels, keyboard splitter behavior, visible focus, local scrollbars, truthful loading/empty/error/blocked state recovery, and one filled primary action maximum.
- Do not add cards, badges, decorative panels, internal IDs, hashes, endpoint names, receipts, provenance jargon, or new unsupported capabilities.

## Capture and validation

Recapture the entire existing WAVE-06 set, not just the five wide images, because shared source and hashes change:

- 17 approval targets: ADM-SCHEMA-RELATIONS 9, ADM-ACCESS 5, ADM-PUBLISH 3
- 10 wide support targets at 2560×1440 and 3840×2160
- 45 deterministic state captures at 1366×768, 1440×900, and 1920×1080

Run and record:

```powershell
node --check docs/00-research/ux-service-reference/administration-remaining.js
.venv\Scripts\ruff.exe check docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/finalize_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/finalize_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check 3b72d48..HEAD
```

Do not mark main-agent, reviewer, or product-owner approval. Return a concise file list, exact commands/results, and the 17 approval image paths plus SHA-256 values for main-agent review.
