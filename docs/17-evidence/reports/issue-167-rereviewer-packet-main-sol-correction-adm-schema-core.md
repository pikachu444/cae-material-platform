# #167 fresh review packet — ADM-SCHEMA-CORE direct correction

Date: 2026-07-30
Mode: bounded read-only review

Follow the reviewer role and workflow defined by `AGENTS.md`, `.codex/config.toml` and the configured
reviewer agent file. Do not edit files.

## Acceptance under review

1. At 1920×1080, Table saving and save-error show the full form, exact status/recovery action and the
   complete Save new revision / Discard draft row in the initial editor viewport.
2. The saved response graph is suppressed only for these transient/recovery states; the synchronized
   saved Record/Layout preview remains truthful.
3. Normal, Table-draft and Attribute-draft graph/preview behavior is unchanged.
4. Lists remain identity-first, local panes own genuine scroll, and no page overflow, clipped action,
   stale preview, heading-only graph or decorative filler appears.
5. All eleven approval targets, sixty state captures and two wide support images pass their
   deterministic contracts.

## Required original-resolution approval and wide images

- `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1920x1080.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1920x1080.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1920x1080.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-edit-stale-conflict-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-wide-2560x1440.png`
- `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-wide-3840x2160.png`

Registered SHA-256 values are in `docs/01-product/service-reference-manifest.yaml` and §60 of the
evidence report. The complete validator must prove them before disposition.

## Required original-resolution corrected state images

| Image | SHA-256 |
| --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-saving-1920x1080.png` | `8f2acc66981be5ed9df16c5815d866d83a4443aca2aaf5168a983aa3315861e3` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-save-error-1920x1080.png` | `6254b8265d43f29a6f48e8288233358514d1f1ecc53ec9267290ef33aaf75f8d` |

## Implementation and evidence

- packet:
  `docs/17-evidence/reports/issue-167-main-sol-direct-correction-packet-materials-admin.md`;
- implementation:
  `administration-schema-core.css`, `administration-schema-core.js`;
- browser evidence:
  `capture_administration_schema_core_wave05.py`,
  `administration-schema-core-wave05.staging.json` and named measurement files;
- deterministic contract:
  `validate_administration_schema_core_wave05.py`;
- lifecycle/evidence:
  `docs/01-product/service-reference-manifest.yaml`,
  `docs/17-evidence/reports/issue-167-service-reference-freeze.md` §60.

Rerun the complete family validator with staging status `pending`, JavaScript syntax, Python
compilation, Ruff, inventory and whitespace gates. Open every image named above at original
resolution. Complete every applicable Q-01–Q-20 item before V-01–V-16 scoring. Return actionable
findings first and then exactly `approve` or `changes_requested`.
