# Issue #167 reviewer packet — ADM-SCHEMA-CORE wide correction

Date: 2026-07-30
Reviewer: one fresh configured `reviewer_terra_high`, read-only
Issue: GitHub #167

> **Withdrawn before reviewer invocation.** The active main agent rejected the later wide-graph
> correction at original resolution because the 1920 `table-saving` and `table-save-error` states
> show only partial lower action buttons at the top of the plot band. This packet's hashes predate
> that correction and are not an approval request. Do not review or approve this packet.

## Acceptance boundary

Review the complete pending ADM-SCHEMA-CORE family after the wide Layout/Record-preview change and
its sole state-truth correction. Do not edit files, regenerate captures, commit, push or change
GitHub. The visual authority and lifecycle are:

- `docs/01-product/service-reference-manifest.yaml`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-implementer-packet-wide-adm-schema-core.md`
- `docs/17-evidence/reports/issue-167-correction-packet-wide-adm-schema-core.md`

The workspace must remain three-pane: `Schema objects ⇆ Object list ⇆ Property editor / preview`.
At 1920 and above, property editing stays bounded while a synchronized Layout-driven saved Record
preview occupies the useful remaining region. It is a subregion of the third pane, not a fourth
inspector. Lower approved candidate pixels remain exact. The preview must be data-first, use one
toggle, highlight only Attributes present in the current Layout and never mutate the saved Record
from a local draft.

Zero-Table and new unsaved Table states must contain no stale `Materials master`, DP780 Record,
`Material datasheet`, or ordered Layout rows. Sparse is correct when no saved Record/Layout
projection exists. Loading/error states may retain the last valid synchronized projection.

## Approval targets

Open all eleven at original resolution and verify their registered hashes:

| Target | SHA-256 |
| --- | --- |
| `administration-database-normal-1366x768.png` | `9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724` |
| `administration-database-normal-1440x900.png` | `1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf` |
| `administration-database-normal-1920x1080.png` | `3dd9ac42672cdbea66595621af3ac6080c8bcb10d8bc4e4bef15339502d933a8` |
| `administration-table-edit-draft-1366x768.png` | `9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69` |
| `administration-table-edit-draft-1440x900.png` | `2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284` |
| `administration-table-edit-draft-1920x1080.png` | `125a9540afe217eef599c6770d086f6c041a1e6046fe1a78c27db8e013fa5207` |
| `administration-attribute-edit-draft-1366x768.png` | `e6682346823355eb99da5eb72eb5c795a31b4847a025d5f554a572e607d7dfd0` |
| `administration-attribute-edit-draft-1440x900.png` | `3db6cd5a26221bf62d13bcedd07c7d3a309df3984ef81914a5828da47f9a1a62` |
| `administration-attribute-edit-draft-1920x1080.png` | `2ccda7d4191368d788d8f740c10c205092e30a91fde613845531e2ca57663791` |
| `administration-edit-stale-conflict-1440x900.png` | `e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21` |
| `administration-attribute-long-invalid-1440x900.png` | `51157e7802a56e093d228a74770cd43b6ad85bc7cb4be2161eca1859087f3994` |

Also open every evidence-only capture enumerated in the staging JSON at original resolution,
including all three viewports for the twenty states. Pay particular attention to:

- `administration-database-empty-1920x1080.png`
  — `2d6b7f32d5bfef54e2c5165d612dc51b6cadfb518269e570f28be13e78182b24`;
- `administration-table-add-draft-1920x1080.png`
  — `e8ead9e58a34b3adca304a2da5fb039c34ad9c2d6663102e221067e5a98e1eaf`;
- `administration-database-normal-wide-2560x1440.png`
  — `3c5137f5b9e101968259dc983eead9dc11feaf3789e5bc0324db9f7e0e02c1e6`;
- `administration-database-normal-wide-3840x2160.png`
  — `85b2d8011d2d2c5d19331a629ec756b8dc84090e67e448d47d7544d8c6a86358`.

## Implementation diff and supplied gates

Inspect the bounded diff in:

- `administration-schema-core.html`
- `administration-schema-core.css`
- `administration-schema-core.js`
- `capture_administration_schema_core_wave05.py`
- `validate_administration_schema_core_wave05.py`
- `administration-schema-core-wave05.staging.json`
- generated ADM-SCHEMA-CORE PNG/measurement evidence
- serial main-agent policy, lifecycle and report changes.

Supplied results: eleven approval targets, sixty state captures and two wide captures pass the family
validator; all eight frozen lower-viewport hashes are exact; empty/new-Table stale-projection
assertions pass; preview toggle/focus, Table/Attribute selection, conditional fields, splitter,
local scrollbar, save/error/conflict recovery and stale-response suppression pass; page/body
overflow and browser errors are zero; Ruff, Python compilation, `node --check`, inventory validation
and `git diff --check` pass.

## Required independent disposition

Rerun only non-mutating gates. Complete V-01–V-16 and every Q-01–Q-20 item as `pass`, `fail` or a
topology-specific `not-applicable`, citing direct paths/images. Judge full-screen visual quality,
information density, line length, whitespace, state truth and task continuity—not just assertions.
Return actionable findings first, hard-gate result, scores/checklist, residual concerns and either
`approve` or `changes_requested`. Do not edit any file.
