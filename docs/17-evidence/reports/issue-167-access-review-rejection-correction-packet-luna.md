# Issue #167 — ADM-ACCESS reviewer-rejection correction packet for Luna Max

Date: `2026-08-01`
Branch: `agent/complete-167-and-157`
Authority: product owner requested all identified defects be corrected with the configured Luna Max
implementer; this packet is the main-agent interpretation of the fresh final reviewer rejection.

## Bounded scope

Correct only the ADM-ACCESS selection and revoke/cancel interaction contracts in WAVE-06 static
reference source, capture, validator and generated WAVE-06 evidence. Preserve all current Relations,
Publish, product-language, typography, responsive and exact-revision corrections. Do not edit
production React/CSS, AGENTS.md, the shared service-reference manifest or common evidence reports.

## Rejected behavior

1. Selecting `material-engineers` changes the highlighted row but the editor and status remain hard-
   coded to `material-reviewers`. Access is excluded from the row keyboard-selection coverage.
2. Clicking `Revoke access…` from the normal screen mounts a second, incomplete confirmation renderer
   rather than the approved revoke-confirm contract. It omits Classification and the right Reviewer-
   access panel. Clicking Cancel changes only status text and leaves the confirmation mounted.
3. Existing deterministic evidence only checks that a revoke heading and reason appear. It does not
   verify selected identity propagation, complete confirmation content or safe cancellation recovery.

Direct evidence:

- `docs/00-research/ux-service-reference/administration-remaining.js:63-71,100-121,294-314,331-377`
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py:329-443`
- `docs/17-evidence/images/issue-167-service-reference/administration-access-revoke-confirm-1440x900.png`

## Required state and UI contract

### Assignment selection

- Add one selected-assignment lookup from the existing `assignments` collection; do not duplicate or
  hard-code selected identity in editor/status renderers.
- Access rows are real selectable rows with the same one-selected-row, `aria-pressed`, roving-tabstop,
  ArrowUp/ArrowDown/Home/End/Enter and focus-preservation behavior used by the other governed lists.
- Pointer and keyboard selection must update together:
  - highlighted/focused row,
  - editor heading and subtitle,
  - User or team, Role, Scope, Classification and Status/validity values,
  - role-appropriate task-access preview,
  - status-bar assignment identity.
- Do not invent infrastructure fields. Use the existing assignment data and ordinary Administrator
  terms. For a `User`, show user work and clearly mark Reviewer/Administrator tasks not granted; for a
  `Reviewer`, retain the current review-work preview; for an `Administrator`, show the governed catalog
  and access work it can perform. The preview must follow the selected role rather than always saying
  Reviewer access.
- Preserve 13px data and 11.5–12px metadata typography, full identity visibility, compact rows and
  bounded three-pane composition.

### Revoke and cancel

- Use one canonical revoke-confirm renderer for both the direct `state=revoke-confirm` capture and the
  normal → Revoke interaction. Delete or refactor the incomplete duplicate renderer.
- Confirmation derives from the currently selected assignment and must show the same identity, Role,
  Scope, Classification, reason field and role-appropriate access preview as the approved static state.
- It has exactly one destructive `Revoke access` command and one local `Cancel` command.
- Cancel must restore the normal editor for the same selected assignment, preserve list selection and
  focusable identity, remove the confirm strip, restore `Revoke access…`, and report `Revocation
  cancelled` in the status bar.
- Confirm need not fabricate a completed immutable revocation state. It may report a bounded request/
  completion status consistent with the existing static reference, but it must not silently mutate the
  assignment collection or claim backend persistence.
- Keep the current direct 1440×900 revoke-confirm image topology and plain-language explanation. No
  modal/card redesign, new internal prose or unrelated visual changes.

## Required deterministic regression coverage

Extend capture evidence for Access normal at every registered normal/wide viewport:

1. Pointer-select `material-engineers` and assert selected row identity, one `aria-pressed=true`, editor
   heading `material-engineers`, Role `User`, Scope `Project/current project`, Classification
   `Confidential`, User-access preview, and status `Assignment · material-engineers`.
2. Exercise ArrowDown/ArrowUp/Home/End/Enter over Access rows and assert row/editor/preview/status/focus
   synchronization exactly as for Relations.
3. Restore/select `material-reviewers`, click `Revoke access…`, and assert the canonical confirmation:
   selected identity, Reviewer role, current-project scope, Confidential classification, reason value,
   right Reviewer-access panel, one destructive command and one Cancel.
4. Click Cancel and assert the confirmation is removed, the normal `material-reviewers` editor and
   access preview return, the row remains selected, `Revoke access…` is present, and status reports
   `Revocation cancelled`.
5. Add validator failures for any stale identity, missing confirmation field/panel, duplicate action,
   lost selection or failed cancel recovery. Demonstrate the new regression fails against the current
   rejected behavior before applying the fix.

Retain all existing header/nav geometry, overflow, typography, internal-language, wide-bound and state
assertions. Recapture all 72 WAVE-06 artifacts after shared JS/capture changes so staging, hashes and
measurements remain consistent.

## Owned files

- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/administration-remaining.css` only if a minimal role-preview
  alignment rule is genuinely necessary
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- generated WAVE-06 PNG and measurement artifacts under
  `docs/17-evidence/images/issue-167-service-reference/`

## Completion gates

Run Node syntax, Ruff, Python compilation, `validate_administration_remaining_wave06.py --all-packet-
targets`, `validate_service_reference_inventory.py` and `git diff --check`. Open Access normal at
1366/1440/1920, revoke-confirm 1440, service-error 1440 and both wide images at original resolution.
Report changed files, exact gate results, pre-fix regression failure evidence, and new SHA-256 values for
all 17 owner-approval targets. Do not edit the shared manifest or common reports; the main agent will
integrate them serially.
