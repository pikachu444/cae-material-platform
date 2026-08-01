# #167 WAVE-05 ADM-SCHEMA-CORE product-owner correction packet

Date: 2026-07-30

## Authority and disposition

The product owner accepts the overall three-pane Administration design and rejects the current
center-list information economy and incomplete Add evidence. The eleven ADM-SCHEMA-CORE references
remain pending. This is a bounded primary-agent correction after the configured writer/reviewer cycle;
no additional substitute writer is authorized. A fresh configured Terra High read-only review is
required after deterministic and original-resolution main-agent gates.

The authoritative approval target count remains 72. Add Table and Add Attribute do not change the
three-pane topology and are registered as evidence-only states for the existing ADM-SCHEMA-CORE
family, not as forgotten approval targets.

## Exact product findings

1. The center `Name` cell currently appends small phrases such as
   `number · mass per volume`. The adjacent Definition column then clips a second sentence. This is
   redundant, difficult to scan and duplicates the property editor.
2. The deterministic/main/reviewer gates proved containment but failed to judge whether the clipped
   copy had user value. Ellipsis is not a successful outcome for low-value prose.
3. Edit drafts do not by themselves prove that an Administrator can add a Table or define a
   user-selected Attribute used by configurable Record values.
4. Later Link Type/Related references must preserve exact revision pins and configured `one`/`many`
   branching. They may not imply a universal one-to-one Material → Neutral → Solver Card chain.

## Required static-reference correction

Owned source and evidence:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- existing ADM-SCHEMA-CORE images, measurements and staging JSON
- Administration entries in `docs/01-product/service-reference-manifest.yaml`
- WAVE-05 sections in `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

Implement:

- Tables center list: `Name | Rev`; no inline detail or clipped Definition sentence.
- Attributes center list: `Name | Value type | Rev`; canonical visible types such as `Number`,
  `Discrete choice`, `Record reference`, `Text`, `Date`.
- Other family rows may use one concise family-specific Kind value, never a description sentence.
- Full purpose, quantity, unit and entry guidance remain in the property editor.
- Long names remain bounded in Name with full-value access and no column collision.
- Selecting Tables/Attributes exposes the matching `Add Table`/`Add Attribute` command.
- `Add Table` and `Add Attribute` open real right-pane new-definition drafts while retaining the
  selected family, current Table context and center list.
- New Attribute value type is selectable and controls the applicable fields.
- Add states use explicit Save actions and preserve the immutable revision consequence.

Do not add a fourth pane, nested cards, technical IDs/hashes, fake Publish/Delete/Duplicate, a
hard-coded Record field set, or a second description column.

## Evidence and gates

- Recapture the existing eleven approval targets at 1366×768, 1440×900 and 1920×1080 as registered.
- Add `administration-table-add-draft` and `administration-attribute-add-draft` evidence-only captures
  at all three viewports.
- Deterministically click Add Table and Add Attribute and verify the correct right-pane draft,
  retained navigator/list/context, conditional Attribute fields, keyboard path and zero browser errors.
- Assert that no visible `.object-name small` exists; Table rows have two columns and Attribute rows
  contain only canonical Value type metadata.
- Re-run the complete ADM validator, inventory validator, manifest/image/hash checks, Ruff,
  JavaScript syntax, Web Interface Guidelines audit and `git diff --check`.
- The main agent opens every changed target and all six Add-state images at original resolution,
  completes Q-01–Q-19, writes the bounded reviewer packet, and requests one fresh configured Terra
  High read-only review.
