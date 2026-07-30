# Issue #167 WAVE-05 ADM-SCHEMA-CORE visible-scroll correction re-review packet

Date: 2026-07-30
Review mode: one fresh configured Terra High, independent and read-only

## Bounded decision

Review the sole correction made after the preceding reviewer rejected Q-09. The approved
three-pane topology and the product-owner list/Add correction are unchanged:

`Schema objects | Object list | Property editor`

The correction adds a visible proportional scrollbar control only when the property editor has
genuine overflow. It is synchronized to the real editor scroll position and supports keyboard,
wheel and pointer input. It also removes redundant outer editor bottom padding so trivial padding
does not create a false scrollbar.

Return `changes_requested` if any visible rail is decorative, detached from actual scroll state,
covers form content, remains visible without overflow, introduces page-level overflow, or causes
any regression in the eleven approval candidates or sixty evidence images.

## Authority and evidence

- Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
- Product-owner packet:
  `docs/17-evidence/reports/issue-167-product-owner-correction-packet-wave-05-adm-list-add-links.md`
- Rejected reviewer packet and recorded disposition:
  `docs/17-evidence/reports/issue-167-rereviewer-packet-wave-05-adm-list-add-links.md`
- Main correction evidence:
  `docs/17-evidence/reports/issue-167-service-reference-freeze.md`, section 50
- Inventory and manifest:
  `docs/01-product/service-reference-inventory.yaml` and
  `docs/01-product/service-reference-manifest.yaml`
- Staging/evidence registry:
  `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- Canonical qualitative checklist:
  `docs/01-product/visual-acceptance-matrix.md`

Review the implementation and evidence diff:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- the eleven Administration entries in
  `docs/01-product/service-reference-manifest.yaml`

## Eleven approval candidates

Open each image at original resolution and independently verify its SHA-256:

| Image | SHA-256 |
| --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1366x768.png` | `9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724` |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1440x900.png` | `1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf` |
| `docs/17-evidence/images/issue-167-service-reference/administration-database-normal-1920x1080.png` | `a8b088bcf69f6047e9bc85558415c585825cede677ef4e4114a8d821155cc56d` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1366x768.png` | `9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1440x900.png` | `2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284` |
| `docs/17-evidence/images/issue-167-service-reference/administration-table-edit-draft-1920x1080.png` | `eace016ff08a9b76577ba30761e35e99a43eee3d525b39f66c65e7c2d6fc6909` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1366x768.png` | `e6682346823355eb99da5eb72eb5c795a31b4847a025d5f554a572e607d7dfd0` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1440x900.png` | `3db6cd5a26221bf62d13bcedd07c7d3a309df3984ef81914a5828da47f9a1a62` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-edit-draft-1920x1080.png` | `b853473a282ee2c93dc7fe158afd06222809fdb4bead211078c784145aecb349` |
| `docs/17-evidence/images/issue-167-service-reference/administration-edit-stale-conflict-1440x900.png` | `e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21` |
| `docs/17-evidence/images/issue-167-service-reference/administration-attribute-long-invalid-1440x900.png` | `51157e7802a56e093d228a74770cd43b6ad85bc7cb4be2161eca1859087f3994` |

The fifteen images with a visible rail must receive focused original-resolution review:

- `administration-attribute-add-draft-1366x768.png`;
- `administration-attribute-conditional-number-{1366x768,1440x900}.png`;
- `administration-attribute-edit-draft-{1366x768,1440x900}.png`;
- `administration-attribute-long-invalid-{1366x768,1440x900,1920x1080}.png`;
- `administration-attribute-save-error-{1366x768,1440x900}.png`;
- `administration-attribute-saving-{1366x768,1440x900}.png`;
- `administration-long-scroll-{1366x768,1440x900,1920x1080}.png`.

Open the remaining registered images as a regression check. The full registry contains twenty
evidence states at three viewports, sixty evidence images total.

## Required read-only checks

Run without recapturing or modifying files:

```text
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

Independently verify:

- Q-09 at 1366, 1440 and 1920: visible track, proportional thumb and preserved pane content;
- `aria-valuemax` equals actual editor maximum, `aria-valuenow` follows `scrollTop`, and
  Home/End/ArrowDown move the real editor;
- the rail is hidden when no actual editor overflow exists;
- Q-17 list information economy, Q-18 Add flows and the Q-19 dependency boundary remain intact;
- V-01–V-16 and Q-01–Q-19 with explicit pass/fail/not-applicable evidence;
- no topology, dominant-area, nested-card, overlap, clipping or page-overflow hard-gate failure.

Return `approve` or `changes_requested`, complete V/Q results, hard-gate failures, actionable
findings and residual concerns. Do not edit, recapture, commit, push, update GitHub or spawn agents.

## Recorded disposition

The fresh read-only reviewer returned `approve` with no actionable finding, hard-gate failure or
material residual concern. V-01–V-16 passed. Q-09, Q-17, Q-18 and Q-19 passed; the remaining Q
checks were correctly not applicable. Independent runtime values confirmed actual/ARIA maxima of
354, 222 and 46 at 1366, 1440 and 1920, with End, Home and ArrowDown synchronized to the editor.
