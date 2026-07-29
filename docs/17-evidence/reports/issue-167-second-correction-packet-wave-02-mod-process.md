# Issue #167 second-correction packet — WAVE-02 / MOD-PROCESS

Date: 2026-07-29  
Writer role: fresh configured Terra High correction writer  
Authority: product owner explicitly authorized a second correction and re-review on 2026-07-29

## Bounded objective

Correct only the MOD-PROCESS nested-interactive accessibility failure reported by the first fresh
read-only reviewer. The approval images already passed the visual topology review and must remain
visually faithful.

Each `.curve-row` is currently a focusable `role="button"` that contains an inclusion checkbox and
a visibility button. The invalid nesting causes the row and eye button to resolve with the same
accessible button name in role queries.

## Owned files

The correction writer exclusively owns:

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- regenerated MOD-PROCESS images, responsive/state evidence, measurements and staging JSON

Do not edit the common manifest, common evidence report, reviewer packets, approved parent assets,
production code, or another family. Other agents may be working in the same worktree; preserve all
unrelated edits and never reset, clean, stash or discard work.

## Required correction

1. Make the curve-row wrapper non-interactive and non-focusable.
2. Keep the inclusion checkbox, curve-selection control and visibility control as semantic siblings.
   Use a native `button type="button"` with a distinct accessible name for curve selection; retain
   the existing native visibility button with its own Show/Hide name.
3. Preserve the current row geometry, selected styling, checkbox inclusion semantics, visibility
   semantics and approval-image topology. Update JavaScript selectors and state synchronization so
   pointer and keyboard activation of curve selection still work.
4. Add deterministic accessibility assertions proving:
   - exactly one button is named `Hide Specimen 02 from plot` in the normal initial state;
   - the Specimen 02 curve-selection button has a distinct accessible name;
   - no button, input, select, textarea, link or focusable role is nested inside another interactive
     element;
   - keyboard activation changes the selected curve without toggling inclusion or visibility.
5. Re-run every existing responsive, state, range-headroom, action-count, overflow and clipping
   assertion. No visual or behavioral regression is acceptable.

## Required gates and handoff

Run the MOD-PROCESS capture and pending-lifecycle validator from final sources, Ruff on the owned
Python files, `node --check` on the owned JavaScript, and `git diff --check` on owned paths. Report:

- exact files changed;
- exact commands and results;
- accessibility query/assertion results and keyboard consequence;
- final SHA-256 of all four approval images;
- any residual concern.

Do not edit the manifest/evidence report and do not commit, push, open a PR or start another family.
