# Issue #167 ACT-RECOVERY product-language correction packet

Date: 2026-07-31

## Correction authority and ownership

The configured Luna Max implementer completed ACT-RECOVERY and passed deterministic gates. The
active main agent opened all five normal/wide and nine state images at original resolution and
rejected the visible queue language before independent review. One fresh configured Terra High
correction writer owns this sole correction.

Owned paths:

- `docs/00-research/ux-service-reference/activity-recovery-blocked.html`
- `docs/00-research/ux-service-reference/activity-recovery.css`
- `docs/00-research/ux-service-reference/activity-recovery.js`
- `docs/00-research/ux-service-reference/capture_activity_recovery.py`
- `docs/00-research/ux-service-reference/validate_activity_recovery.py`
- `docs/00-research/ux-service-reference/activity-recovery.staging.json`
- every `activity-recovery-*.png` and matching measurements/state JSON under the issue #167 evidence
  directory

Do not edit the common manifest, inventory, freeze report, ACT-QUEUE, any other family, production
React/CSS, or Git history. The active main agent integrates shared files serially afterward.

## Preserved task and topology

Preserve without redesign:

- the approved flat Activity shell, User queue, selected In progress tab and 41 normal rows;
- one browser-local saved Modeling session followed by the existing server-backed request page;
- row heights, stable 12.5–14 px type, independent real local scroll and truthful 50-request
  contract density through 3840;
- failed calculations remain unavailable because no readable Activity projection joins them to the
  user's exact Modeling context;
- `Resume Modeling` is the one normal primary action;
- empty has no local saved session and one quiet `Open Modeling` action;
- loading preserves all rows/context and disables `Refreshing…`;
- action error preserves the selected local session and exposes one inline `Try again`;
- all frozen ACT-QUEUE hashes, layout, interactions and role boundaries.

## Required product-language correction

The normal User queue must use the product-owner vocabulary from `AGENTS.md`: Test Data, selected
model, review request and solver card. Replace every primary-surface task/reason template that exposes
internal or workflow-implementation language, including:

- `Import provenance`, `source provenance`;
- `Processing output`;
- `Curve selection`;
- `Fit result`;
- `Mapping`, exact field mappings or exceptions;
- `Evidence`;
- immutable revision mechanics.

Use a restrained finite set of scannable user tasks such as `Test Data review`, `Selected model
review`, `Solver card review` and, only when semantically needed, `Material review`. Reasons should
state the concrete user decision using those nouns. Do not relabel every row generically, fabricate
new domain states, add badges, cards, descriptions or actions, or expose readable people/items the
current projection does not supply.

The availability strip already states `Failed calculations | Not available in Activity`; its body
must not repeat the limitation or say `cannot yet`. Keep only the useful consequence/recovery:
`Resume the saved Modeling session to inspect the current step.` The empty state's `Open Modeling`
remains appropriate.

## Deterministic and visual gate

Extend the validator so every visible normal/state queue string rejects the forbidden vocabulary and
uses only the bounded product-language task set. Preserve exact row counts, row-density ranges,
scroll geometry, state interactions, zero errors/overflow and frozen ACT-QUEUE hashes.

Call capture and validator `--help`, recapture all five normal/wide and nine state images, and pass:

```powershell
python docs/00-research/ux-service-reference/validate_activity_recovery.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_activity_recovery.py docs/00-research/ux-service-reference/validate_activity_recovery.py
python -m py_compile docs/00-research/ux-service-reference/capture_activity_recovery.py docs/00-research/ux-service-reference/validate_activity_recovery.py
node --check docs/00-research/ux-service-reference/activity-recovery.js
git diff --check
```

Return all final hashes. The active main agent then opens every image at original resolution,
integrates common lifecycle evidence and requests one fresh read-only Terra High review.
