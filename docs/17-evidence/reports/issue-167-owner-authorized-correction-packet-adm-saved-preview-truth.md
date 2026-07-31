# Issue #167 product-owner-authorized final correction packet — ADM-SCHEMA-CORE saved preview truth

Date: 2026-07-31
Writer: configured fresh `correction_terra_high`
Mode: exceptional bounded correction explicitly authorized by the product owner after the exhausted
family correction/re-review lifecycle

## Authority and rejection being corrected

Read and follow:

- `AGENTS.md`;
- GitHub issue #167;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`;
- `docs/01-product/visual-acceptance-matrix.md`;
- `docs/17-evidence/reports/issue-167-main-sol-correction-packet-adm-governed-name.md`;
- `docs/17-evidence/reports/issue-167-rereviewer-packet-adm-governed-name.md`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 49–61, 89–90 and 94.

The previous correction restored the governed Object-list identity
`Material condition | Discrete choice | 3`. The fresh reviewer and active main agent then found one
remaining Q-17 product defect: `previewAttributeLabel` substitutes the unsaved invalid draft name
into the saved Record and saved Layout projections. An invalid local draft has not created a new
Attribute revision and must not rename either read-only saved projection.

The product owner explicitly authorized this additional correction. It does not authorize any new
Administration feature or production React/CSS, commit, push, PR or merge work.

## Ownership

This writer owns only:

- `docs/00-research/ux-service-reference/administration-schema-core.js`;
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`;
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`;
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`;
- ADM-SCHEMA-CORE images, measurements and state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

Do not edit the common manifest, common inventory, common freeze report, product/UI specifications,
another family, production React/CSS or GitHub state. Other agents and the user own all unrelated
worktree changes; do not revert them.

## Required correction

1. Saved Record values and saved ordered Layout fields always render the stored Attribute
   `field.name`. The unsaved draft name must never alter either saved read-only projection.
2. In `attribute-long-invalid`, keep the Object list exactly
   `Material condition | Discrete choice | 3`. Keep the deliberately long invalid name only in the
   editable `Attribute name` field.
3. Preserve the invalid choices/guidance/change-reason errors, disabled Save, complete local editor
   scrolling, selected-row/editor relationship, exact saved revision IDs, linked Artifact truth,
   Layout/Record projection and all existing Add Table/Add Attribute states.
4. Do not change topology, add explanation, rename stored data, fabricate a saved revision or add a
   new feature.
5. Extend deterministic assertions so all three long-invalid viewports prove:
   - the editable input contains the distinct long invalid draft;
   - the draft string is absent from Object-list Name, Record values, Layout fields, preview
     heading/subtitle and preview context;
   - both saved projections show exactly `Material condition`;
   - the saved Attribute/Layout/Record revision identifiers remain exact;
   - local scroll rails remain visible, proportional, operable and non-overlapping.
6. Re-capture the complete owned eleven-target bundle and state evidence so unchanged-image hashes
   can be proved stable. Do not update the common manifest or common report; the main agent integrates
   those serially after its original-resolution gate.

## Deterministic gates

Call both helpers with `--help` before capture/validation. Then run:

```powershell
python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

If the actual capture CLI differs, use the exact option shown by `--help`. Return changed paths,
commands/results, lifecycle/support/state hashes and residual qualitative concerns. Do not claim
visual approval.
