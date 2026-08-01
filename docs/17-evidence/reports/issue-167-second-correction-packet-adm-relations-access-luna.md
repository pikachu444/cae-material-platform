# Issue #167 Administration relations/access — owner-authorized second correction packet

Date: `2026-08-01`
Branch: `agent/complete-167-and-157`
Candidate checkpoint: `2bcbbfa` plus the current uncommitted WAVE-06 correction
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
PR: <https://github.com/pikachu444/cae-material-platform/pull/170>

## Authorization and hard bounds

The product owner explicitly authorized a second correction on 2026-08-01 because the accepted
findings are bounded and low complexity. This is the second and last correction. Use exactly one
configured `implementer_luna_max` writer and then stop for deterministic gates, main-agent review,
and fresh read-only Terra High re-review. A third correction is forbidden.

Correct only the three accepted findings below. Do not start #157, production React/CSS/API/backend
work, a redesign, a commit, a push, a GitHub edit, or any approval-state change. The reviewer concern
about Q-18 `Add Table` / `Add Attribute` is explicitly out of scope: the already approved prerequisite
`ADM-SCHEMA-CORE` owns that workflow.

The writer owns only:

- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/administration-remaining.css`, only if a visible-focus fix is necessary
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- the affected ADM-SCHEMA-RELATIONS and ADM-ACCESS WAVE-06 PNG and measurement JSON files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit `AGENTS.md`, either common service-reference manifest, common evidence/reviewer/product-
owner reports, production files, or any unrelated dirty file. Preserve all existing work; do not
reset, clean, stash, discard, revert, or rewrite history.

## Authority and preserved contracts

Read before editing:

- root `AGENTS.md`
- `.agents/skills/desktop-engineering-ui/SKILL.md`
- `.agents/skills/frontend-ui-engineering/SKILL.md`
- `.agents/skills/web-design-guidelines/SKILL.md`
- `.agents/skills/webapp-testing/SKILL.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-administration-remaining-correction-packet.md`
- `docs/17-evidence/reports/issue-167-reviewer-packet-adm-schema-relations-final.md`
- `docs/17-evidence/reports/issue-167-reviewer-packet-adm-access-final.md`

Preserve the approved three-pane Administration topology, compact hierarchy, local scroll behavior,
exact-revision language, Layout/Subset/Link Type domain truth, Access task/role/scope behavior,
loading/empty/error/blocked recovery, bounded wide composition, canonical command placement, and all
current state semantics. Use only deterministic synthetic non-production reference fixtures already
present in the source. Do not invent a production policy, standard, endpoint, threshold, capability,
or technical filler.

## Accepted finding A — remove Access implementation prose

Remove the Access callout containing implementation-facing language such as `Enforcement`,
`PostgreSQL`, or `row policies` from normal and service-error rendering. Do not replace it with filler;
the task list already communicates the permission model. Preserve denied, revoke-confirmation, empty,
loading and service-error behavior and recovery.

Required assertion: normal and service-error rendered document text contains none of `Enforcement`,
`PostgreSQL`, or `row policies` (case-insensitive), with no replacement developer-facing prose.

## Accepted finding B — make relation list selection real

The Layout, Subset and Link Type family lists are selectors, not cosmetic decoration. Selecting every
non-default row must update all of the following without changing the three-pane topology:

- selected styling and `aria-pressed` state;
- the editor heading/context to the row's complete identity;
- the row-specific editor/preview context using the existing deterministic fixture fields;
- the complete identity affordance when a list label is ellipsized.

Default selection appearance and the existing state-specific normal/loading/error/blocked semantics
must remain unchanged. A long Link Type identity at 1366×768 must be reachable through an accessible
name/title and through the selected editor heading; do not widen the list until the editor loses
dominance.

Required assertions must exercise every non-default Layout, Subset and Link Type row and verify that
the full selected editor identity and expected row-specific preview context change. A click that only
changes highlight/`aria-pressed` is a failure.

## Accepted finding C — keyboard-operable object lists

Implement keyboard navigation within the current Layout, Subset and Link Type family lists:

- `ArrowDown` and `ArrowUp` move to and select the next/previous row;
- `Home` and `End` move to and select the first/last row;
- `Enter` invokes/opens the selected row through the same existing button semantics;
- use roving `tabindex` or an equivalent single, predictable focus model;
- preserve visible keyboard focus.

Keyboard movement must update the same editor/preview context as pointer selection, and focus and
selection must remain synchronized. Do not add a separate keyboard-only state or duplicate command.

Required assertions must exercise `ArrowDown`, `ArrowUp`, `Home`, `End`, and `Enter`, verify focus,
selection, `aria-pressed`, and editor/preview identity, and detect console/page errors.

## Capture and deterministic gate

Recapture only the affected families, at every already registered viewport/state:

- ADM-SCHEMA-RELATIONS: 9 approval targets, 6 wide support targets, 27 state targets;
- ADM-ACCESS: 5 approval targets, 2 wide support targets, 9 state targets.

If broad capture would overwrite unrelated WAVE-06 files, add a bounded family-target capture mode
and use it. Do not touch ADM-PUBLISH pixels. The measurement evidence must record the interaction
proof described above, even when a screenshot's pixels are unchanged.

Run and report exact results:

```powershell
node --check docs/00-research/ux-service-reference/administration-remaining.js
.venv\Scripts\ruff.exe check docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

All existing 1,815 checks must continue to pass, with additional interaction/text assertions added.
There must be no new console/page errors, overlap, clipping, document overflow, child overflow,
duplicate commands, or fabricated filler. Return a concise changed-file list, command results, and
the affected approval-image paths and SHA-256 values. Do not integrate common reports/manifests or
request product-owner approval; the main agent owns those steps.
