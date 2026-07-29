# Issue #167 WAVE-05 ADM-SCHEMA-CORE typed-state semantics correction

Date: 2026-07-29
Author: active `/root` primary agent
Correction writer: reuse the same configured Terra High WAVE-05 sole correction agent

## Main-agent finding

Original-resolution inspection of all evidence-only captures found a semantic state leak that the
bundle validator did not detect:

- `attribute-discrete` selects and titles `Material condition`, but `Attribute name` still contains
  `Density` and its entry guidance still instructs the user to enter measured mass density.
- `attribute-reference` selects and titles `Source reference`, but `Attribute name` and entry
  guidance still contain Density semantics.
- `attribute-text` selects and titles `Test method`, but `Attribute name` and entry guidance still
  contain Density semantics.

This fails state/data correctness and makes the conditional-field evidence visually plausible but
contractually false.

The continued original-resolution review also found that the deliberately long Attribute name
crosses the Name-cell boundary and overlaps the adjacent Definition text at all three viewports.
The correction must keep that name inside its own cell with a visible ellipsis and no overlap with
Definition or Rev.

## Allowed ownership

- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- only ADM-SCHEMA-CORE PNG/measurement evidence whose bytes or hashes actually change

Do not edit the common manifest or evidence report, production React/CSS, inventory, tooling,
Activity/Materials/Modeling sources, commit, push or spawn agents.

## Required correction

1. Every conditional Attribute state must initialize all visible draft values from the selected
   Attribute rather than leaking the Density draft.
2. `Material condition` must show a matching name and controlled-choice guidance.
3. `Source reference` must show a matching name and Record-reference guidance that explains which
   supporting record is linked.
4. `Test method` must show a matching name and text guidance for the method identifier.
5. Keep the existing typed field sets:
   - number: quantity, normalized unit, minimum and maximum;
   - discrete: allowed choices;
   - record reference: related Table;
   - text: maximum length and optional pattern.
6. Add deterministic assertions that selected row, editor title, Attribute name, value type,
   conditional fields and entry guidance describe the same Attribute for all three viewports.
7. Recapture the affected evidence states. Approval-target bytes should remain unchanged unless the
   correction proves otherwise; report their hashes explicitly.
8. Add a deterministic three-viewport assertion that the selected long name remains inside the Name
   cell and cannot overlap the Definition or Rev cells.

## Gates

```text
python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status pending
uv run ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

Open the nine affected conditional-state images at original resolution before returning. Report
changed files, old/new evidence hashes, approval-target hash stability and all gate results.
