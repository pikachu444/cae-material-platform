# Issue #167 WAVE-05 ADM-SCHEMA-CORE reviewer packet

Date: 2026-07-29
Review mode: one fresh configured Terra High, independent and read-only

## Bounded acceptance

Review the ADM-SCHEMA-CORE service-reference bundle only. It freezes Administration Database,
Table edit and typed Attribute edit, including stale-conflict and long-invalid topology. It does
not authorize production React/CSS or invent a governed Database/Profile resource, publication
lifecycle, access workflow, production material family or solver policy.

The expected desktop topology is exactly three continuous panes:

`Schema objects | Object list | Property editor`

The reviewer must reject a redundant fourth setup/inspector column, nested-card composition,
unreadable schema text, fake publication/access capability, page-level overflow, clipped controls,
missing local overflow access, mutable-history language or a conflict flow that discards the local
draft.

## Authority and packet

- Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
- Inventory: `docs/01-product/service-reference-inventory.yaml`
- Manifest: `docs/01-product/service-reference-manifest.yaml`
- Main evidence: `docs/17-evidence/reports/issue-167-service-reference-freeze.md`, sections 46–47
- Implementer packet:
  `docs/17-evidence/reports/issue-167-implementer-packet-adm-schema-core-wave-05.md`
- Canonical qualitative checklist:
  `docs/01-product/visual-acceptance-matrix.md`
- Product/UI contracts:
  `docs/01-product/desktop-engineering-ui-product-spec.md` and
  `docs/01-product/desktop-engineering-ui-spec.md`
- Current implementation/data contracts inspected by the main agent:
  `apps/web/src/configurable-catalog-admin.tsx`,
  `apps/web/src/api.ts`, `apps/web/src/types.ts`,
  `contracts/catalog/configurable-catalog-resources.schema.json` and
  `contracts/http/openapi.yaml`

Static implementation diff:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`

## Approval images

Open every image at original resolution and independently verify the SHA-256:

| Image | SHA-256 |
| --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1366x768.png` | `e0c2951b04d473c3d6b7e133c815446a22810037e7cfe1ae0b6664d9e0af07d6` |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1440x900.png` | `901f13632255d95added7455eb539ff78c9e8cefaa115f9aaa23b043af088ea9` |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1920x1080.png` | `b54ac84e90ea3dac980e8f7c0bc71fd10687d4777cffa11106ad519fac99e1f6` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1366x768.png` | `e95e21879f7877d4054a263005df835da8fb86a2d487e8375ccc463e751c758e` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1440x900.png` | `91edbc0bc8913832ee5f48f495e38d570a725407baaf76fa5bcb278b7d17c34f` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1920x1080.png` | `c8102c5e056a9848e7788aae183864fa65e774fad830eb96da62aad9a3cc46c3` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1366x768.png` | `e037e9b409bd3a16bafa4e4287454c2a3a2372a06b6d92c47fd8b5fd80ab47b7` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1440x900.png` | `e0f2ee98460f5ef5d5669aa37f26391763e3fc09085a314d85b2448dc3f02d11` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1920x1080.png` | `228757c2613d8dc552ec10db510780bb0ed0bae45a400c2122d0e0035117de32` |
| `docs/17-evidence/images/issue-167-service-reference/administration-edit-stale-conflict-1440x900.png` | `7a6befe06cf47a5eacbbe552658258d88e87336c57957832908a45b9a58b9d9e` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1440x900.png` | `eaf1e78c4be5e5c488f81f494144ff4d8464cd962768a969bc58a18d3a9ce766` |

Open all 54 evidence-only captures registered by the staging manifest, including all three
responsive siblings for stale-conflict and long-invalid. Explicitly verify that conditional
discrete, Record-reference and text states do not leak Density values or guidance, and that the
long-invalid selected-row name never overlaps Definition or Rev.

## Required independent checks

Run without recapturing or modifying files:

```text
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

Independently exercise or inspect evidence for object-family/list selection, refresh continuity,
conditional Attribute fields, splitter keyboard min/default/max, local editor scroll, duplicate
submit blocking, stale-conflict focus/recovery and zero console/page errors.

Score V-01–V-16 and record pass/fail/not-applicable for every canonical Mandatory qualitative owner
checklist item Q-01 onward. Administration-specific qualitative attention:

- overall desktop density and consistency with approved Materials/Modeling shell;
- real three-pane dominance at 1366, 1440 and 1920 rather than numeric-only compliance;
- text rhythm, form alignment and information economy;
- visible local overflow affordance where content exceeds a pane;
- long names remain accessible without a rail covering text;
- stale/invalid state emphasis is adjacent and not repeated;
- current definition, editable draft, immutable new revision and conflict recovery stay distinct.

Return `approve` or `changes_requested`, the complete V and Q results, hard-gate failures,
actionable findings with direct evidence and residual concerns. Do not edit, commit, push, update
GitHub or spawn another agent.
