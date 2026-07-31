# Issue #167 ADM-SCHEMA-CORE governed-name fresh re-review packet

Date: 2026-07-31

## Read-only review boundary

Review only the bounded governed-identity correction described in
`docs/17-evidence/reports/issue-167-main-sol-correction-packet-adm-governed-name.md`.
Do not edit files or review unrelated dirty-worktree changes.

The previous fresh review found one blocking Q-17 defect: in the long-invalid Attribute state, the
center Object list substituted the long draft description for the governed Name `Material
condition`. The active main agent corrected that one product defect directly under the product
owner's authorization to continue dependency-independent #167 work. The earlier implementer/
correction lifecycle is otherwise frozen.

## Exact changed implementation/evidence paths

- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1366x768.measurements.json`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1440x900.measurements.json`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1920x1080.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1920x1080.measurements.json`
- `docs/17-evidence/images/issue-167-service-reference/administration-long-scroll-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-long-scroll-1366x768.measurements.json`
- `docs/17-evidence/images/issue-167-service-reference/administration-long-scroll-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-long-scroll-1440x900.measurements.json`
- `docs/17-evidence/images/issue-167-service-reference/administration-long-scroll-1920x1080.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-long-scroll-1920x1080.measurements.json`

The complete UI contract and cumulative qualitative rules remain:

- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 49–61 and 89

## Images and exact hashes

Open all six images at original resolution. The long-scroll images are intentionally byte-identical
to the responsive long-invalid state because they prove the same real local-overflow topology.

| Image | SHA-256 |
| --- | --- |
| `administration-attribute-long-invalid-1366x768.png` | `ca0f3f45eb18a225e5aa01b583b4a0653a3c78023277331d61e109b78b5f3968` |
| `administration-attribute-long-invalid-1440x900.png` | `5e8316055d0384863322a2eb8b538181f278c728f773f4576433b00fc9ba8f43` |
| `administration-attribute-long-invalid-1920x1080.png` | `b448db4ce191d413b80b2022dcc69319363312d703106dbf4b069af739d49f37` |
| `administration-long-scroll-1366x768.png` | `ca0f3f45eb18a225e5aa01b583b4a0653a3c78023277331d61e109b78b5f3968` |
| `administration-long-scroll-1440x900.png` | `5e8316055d0384863322a2eb8b538181f278c728f773f4576433b00fc9ba8f43` |
| `administration-long-scroll-1920x1080.png` | `b448db4ce191d413b80b2022dcc69319363312d703106dbf4b069af739d49f37` |

The other ten approval candidates, all other state evidence, and both 2560/3840 wide captures must
retain their registered hashes.

## Required deterministic and qualitative review

Independently rerun:

```powershell
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

Complete Q-01–Q-20 with direct image/path evidence. Q-17 must fail unless:

- the selected center row reads exactly `Material condition`;
- `Discrete choice` and revision `3` remain aligned;
- the full governed identity is reachable without clipping or ellipsis;
- the distinct long invalid draft appears only in the editor's Attribute name field;
- no Name/help/description prose leaks into the Object list.

Also verify Q-09 local rail visibility/operation and Q-20 wide Layout/Record truth remain intact.
Return actionable findings first, then `approve` or `changes_requested`.
