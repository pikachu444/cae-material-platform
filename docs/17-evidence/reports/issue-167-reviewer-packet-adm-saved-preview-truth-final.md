# Issue #167 ADM-SCHEMA-CORE saved-preview-truth final reviewer packet

Date: 2026-07-31
Reviewer: fresh configured read-only `reviewer_terra_high`

## Read-only boundary

Review only the product-owner-authorized ADM-SCHEMA-CORE correction described in:

- `docs/17-evidence/reports/issue-167-owner-authorized-correction-packet-adm-saved-preview-truth.md`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 89–90 and 94–96.

Do not edit any file, review unrelated dirty-worktree changes, reinterpret dependent Administration
families or begin production implementation.

## Acceptance and exact correction

The complete family retains the accepted three-pane Administration topology, Add Table/Add
Attribute flows, typed Attribute fields, immutable-revision behavior, stale-conflict recovery,
local scroll rails and wide saved Record/Layout/curve preview.

The bounded defect was saved-versus-draft truth:

- Object-list identity must be exactly `Material condition | Discrete choice | 3`;
- the deliberately long invalid draft must appear only in the editable `Attribute name` field;
- the saved Record and ordered Layout projections must each keep stored label `Material condition`
  and exact Attribute revision `55555555-5555-4555-8555-555555555555`;
- the draft must be absent from saved preview title, subtitle, Record, Table, value rows and Layout
  rows;
- no valid save/new revision is implied while the three field errors remain.

## Changed implementation and evidence

- `docs/00-research/ux-service-reference/administration-schema-core.js`;
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`;
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`;
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`;
- the six long-invalid/long-scroll responsive images and measurements under
  `docs/17-evidence/images/issue-167-service-reference/`.

The correction did not change any PNG bytes. The six relevant image hashes remain:

| Image pair | SHA-256 |
| --- | --- |
| `administration-attribute-long-invalid-1366x768.png` and `administration-long-scroll-1366x768.png` | `ca0f3f45eb18a225e5aa01b583b4a0653a3c78023277331d61e109b78b5f3968` |
| `administration-attribute-long-invalid-1440x900.png` and `administration-long-scroll-1440x900.png` | `5e8316055d0384863322a2eb8b538181f278c728f773f4576433b00fc9ba8f43` |
| `administration-attribute-long-invalid-1920x1080.png` and `administration-long-scroll-1920x1080.png` | `b448db4ce191d413b80b2022dcc69319363312d703106dbf4b069af739d49f37` |

The staging file is the complete finite evidence index. Open all eleven approval images, all sixty
state images and both wide images at original resolution. Verify every staged hash and inspect the
saved preview DOM/measurements for the corrected truth boundary; do not infer the saved label from a
row that is outside the initial scroll position.

## Deterministic evidence

The active main agent reran:

```powershell
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

All passed. Independently verify hashes and rerun these non-mutating gates.

## Required qualitative review

Apply the current Web Interface Guidelines and complete Q-01–Q-20 from
`docs/01-product/visual-acceptance-matrix.md` with `pass`, `fail` or `not-applicable` plus direct
evidence. In particular:

- Q-09: local editor and preview rails are visible, proportional, operable and do not cover text;
- Q-17: governed identity, editable draft and saved projections are three distinct truths;
- Q-18: Add Table/Add Attribute and valid-draft behavior remain available without invented commands;
- Q-20: 1920/2560/3840 uses the available area for the existing Record/Layout/curve contract without
  stretched rows, fabricated filler or stale draft data.

Return actionable findings first, followed by exactly `approve` or `changes_requested`. The reviewer
is not the final design authority; the active main agent repeats the full-screen gate afterward.
