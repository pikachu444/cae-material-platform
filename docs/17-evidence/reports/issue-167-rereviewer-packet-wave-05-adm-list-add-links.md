# Issue #167 WAVE-05 ADM-SCHEMA-CORE product-owner correction reviewer packet

Date: 2026-07-30
Review mode: one fresh configured Terra High, independent and read-only

## Bounded acceptance

Review only the product-owner correction to ADM-SCHEMA-CORE. The accepted topology remains:

`Schema objects | Object list | Property editor`

The correction removes low-value clipped prose from the center Object list and adds real,
contract-aligned Add Table and Add Attribute evidence. It does not authorize production React/CSS,
add approval targets, or start the dependent Layout/Subset/Link Type bundle.

Reject the bundle if:

- a Table row exposes anything beyond `Name | Rev`;
- an Attribute row exposes anything beyond `Name | Value type | Rev`;
- low-value purpose, quantity or help prose is clipped into Name;
- Add replaces the navigator, current Table scope or Object list;
- Add Attribute does not provide an editable Value type with conditional fields;
- a fourth pane, nested-card composition, page overflow, clipped control or mutable-history
  language appears;
- current-core copy implies every linked engineering record is one-to-one or follows `latest`.

## Authority

- Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
- Product-owner correction packet:
  `docs/17-evidence/reports/issue-167-product-owner-correction-packet-wave-05-adm-list-add-links.md`
- Inventory: `docs/01-product/service-reference-inventory.yaml`
- Manifest: `docs/01-product/service-reference-manifest.yaml`
- Staging/evidence registry:
  `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- Main evidence: `docs/17-evidence/reports/issue-167-service-reference-freeze.md`, section 49
- Canonical qualitative checklist:
  `docs/01-product/visual-acceptance-matrix.md`
- Product/UI contracts:
  `docs/01-product/desktop-engineering-ui-product-spec.md` and
  `docs/01-product/desktop-engineering-ui-spec.md`

Review this implementation and evidence diff:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- the eleven Administration entries in
  `docs/01-product/service-reference-manifest.yaml`

## Approval images

Open every image at original resolution and independently verify its SHA-256:

| Image | SHA-256 |
| --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1366x768.png` | `9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724` |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1440x900.png` | `1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf` |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1920x1080.png` | `a8b088bcf69f6047e9bc85558415c585825cede677ef4e4114a8d821155cc56d` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1366x768.png` | `9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1440x900.png` | `2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1920x1080.png` | `eace016ff08a9b76577ba30761e35e99a43eee3d525b39f66c65e7c2d6fc6909` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1366x768.png` | `e5c3c38265828ef22054ae5b99b41dec34bec8c9c5d32c926ff9abd603cfcf6c` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1440x900.png` | `268d91e523b73fc39feba7cd05e32eeea0c02515f5a90cbb4908df0974b3c63e` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1920x1080.png` | `b853473a282ee2c93dc7fe158afd06222809fdb4bead211078c784145aecb349` |
| `docs/17-evidence/images/issue-167-service-reference/administration-edit-stale-conflict-1440x900.png` | `e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1440x900.png` | `0f103bfa1b19b90e60aca2a90be2a1ea7070d7666bd45a47e437e65a2d4c823f` |

Open all 60 evidence images registered by the staging JSON, including:

- `administration-table-add-draft-{1366x768,1440x900,1920x1080}.png`;
- `administration-attribute-add-draft-{1366x768,1440x900,1920x1080}.png`;
- all responsive siblings for empty/loading/error, typed fields, saving/save-error, conflict,
  long-invalid, pane scroll/splitter, selection continuity and stale-response suppression.

## Required independent checks

Run without recapturing or modifying files:

```text
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

Independently inspect or exercise:

- Table and Attribute family selection;
- `Add Table` and `Add Attribute`, retained navigator/list/Table context and Cancel;
- editable new-Attribute Value type and transition from Discrete choice to Record reference;
- identity-only list columns, full-width rows and long-name containment;
- keyboard splitter min/default/max and local list/editor scroll;
- typed Attribute state alignment;
- duplicate-submit blocking, stale-conflict recovery and zero browser errors.

Complete V-01–V-16 and Q-01–Q-19. For this bounded core bundle, Q-17 and the current-core part of
Q-18 are applicable. Q-19 is not applicable because Link Type/Related is owned by the dependent
ADM-SCHEMA-RELATIONS bundle; confirm that this core bundle contains no false one-to-one or `latest`
claim. The later Layout/Record-preview clause of Q-18 is an explicit dependency gate, not a claim
that this bundle already freezes that screen.

Return `approve` or `changes_requested`, the complete V and Q results, hard-gate failures,
actionable findings with direct evidence and residual concerns. Do not edit, commit, push, update
GitHub or spawn another agent.

## Recorded disposition

The fresh read-only reviewer returned `changes_requested`. V-01–V-16, Q-17 and Q-18 passed and
Q-19 was correctly not applicable, but Q-09 failed: the long editor had genuine measured overflow
without a perceptually distinct proportional scrollbar thumb in the original-resolution images.
This packet and disposition remain unchanged as the record of the rejected pre-correction bundle.
