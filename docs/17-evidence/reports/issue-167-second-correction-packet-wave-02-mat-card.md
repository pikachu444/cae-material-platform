# Issue #167 second-correction packet — WAVE-02 / MAT-CARD

Date: 2026-07-29  
Writer role: fresh configured Terra High correction writer  
Authority: product owner explicitly authorized a second correction and re-review on 2026-07-29

## Bounded objective

Correct only the MAT-CARD error-state evidence integrity failure reported by the first fresh
read-only reviewer. The approved-image appearance and interaction design already passed the visual
rubric and must not be redesigned.

The current capture clicks `Retry` before taking the screenshot and recording the snapshot for the
required error scenario. Consequently the three error records incorrectly contain `state: normal`
and `error_visible: false`. The validator only proves that retained preview text remains visible; it
does not prove that the pre-retry error state was captured.

## Owned files

The correction writer exclusively owns:

- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- regenerated MAT-CARD state/responsive evidence and staging JSON produced by those scripts
- MAT-CARD approval PNGs only if the correction genuinely changes their rendered bytes

Do not edit shared CSS/JavaScript, the common manifest, the common evidence report, reviewer
packets, production code, or another family. Other agents may be working in the same worktree;
preserve all unrelated edits and never reset, clean, stash or discard work.

## Required correction

1. For each 1366×768, 1440×900 and 1920×1080 error scenario, capture and serialize the actual
   pre-retry state before activating `Retry`.
2. The pre-retry record must prove `state == "error"`, `error_visible == true`, retained native
   preview/context, the Retry recovery control, no page overflow, no clipped decision text and no
   browser error.
3. Exercise Retry after that capture and record its consequence separately, without overwriting or
   relabeling the pre-retry evidence. The recovery record must prove the announced/normal recovered
   state and preserved task context.
4. Strengthen the deterministic validator so it fails unless all three error viewports contain the
   actual pre-retry error state and a separate successful recovery consequence.
5. Preserve the approved normal, approximation-blocked and unsupported-blocked images and their
   topology. Do not make visual changes merely to change hashes.

## Required gates and handoff

Run the MAT-CARD capture and pending-lifecycle validator from final sources, Ruff on the owned
Python files, and `git diff --check` on owned paths. Report:

- exact files changed;
- exact commands and results;
- the three corrected error records and separate recovery assertions;
- final SHA-256 of all five approval images, explicitly stating whether any changed;
- any residual concern.

Do not edit the manifest/evidence report and do not commit, push, open a PR or start another family.
