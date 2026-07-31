# Issue #167 ADM-SCHEMA-CORE final fresh reviewer packet

Date: 2026-07-31  
Reviewer role: fresh configured Terra High, read-only  
Lifecycle: eleven approval targets `pending`; main-agent evaluation `accepted`; product-owner approval
`absent`

## Issue acceptance

Review only the owner-authorized ADM-SCHEMA-CORE preview correction:

- `Record preview` and `Layout definition` are mutually exclusive task projections.
- Compact preview opening is real and has a visible return path.
- The active long table has useful scan height, genuine local overflow and a proportional visible
  rail; wheel, keyboard and pointer input have observable consequences.
- A linked curve appears only for the selected saved curve value, remains read-only, secondary and
  bounded. A scalar Attribute edit is graph-free.
- At 2560×1440 and 3840×2160, related components form a left/top-aligned working cluster with only
  normal dividers or gutters. Components stop at useful readable bounds. Remaining whitespace may
  stay at the far right and bottom; viewport-fill percentage is not an acceptance criterion.
- Saved-versus-draft, exact revision, Add, stale conflict, loading/error, selection, focus return and
  conditional Attribute behavior do not regress.

The complete acceptance authority is:

- `docs/17-evidence/reports/issue-167-owner-authorized-correction-packet-adm-preview-information-architecture.md`
- `docs/17-evidence/reports/issue-167-correction-packet-adm-preview-wide-semantic-elasticity.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`

## Exact implementation and evidence diff

Static implementation and deterministic proof:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`

Main-agent integration:

- `docs/01-product/service-reference-manifest.yaml`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

The staging JSON is the finite index for all eleven lifecycle targets, sixty responsive state images
and two wide support images. Open every indexed PNG at original resolution and verify its recorded
SHA-256.

Approval-target and wide-support hashes:

| Image | SHA-256 |
| --- | --- |
| `administration-database-normal-1366x768.png` | `9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724` |
| `administration-database-normal-1440x900.png` | `1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf` |
| `administration-database-normal-1920x1080.png` | `866fe8bd0971878c4e8c723ddacb9cde0297be3d962790071721d101965feded` |
| `administration-table-edit-draft-1366x768.png` | `9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69` |
| `administration-table-edit-draft-1440x900.png` | `2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284` |
| `administration-table-edit-draft-1920x1080.png` | `eace016ff08a9b76577ba30761e35e99a43eee3d525b39f66c65e7c2d6fc6909` |
| `administration-attribute-edit-draft-1366x768.png` | `6eeb19ed91e1ea343623ae16c837d514bb97b85c307157dfe56f53af6b0d6b1f` |
| `administration-attribute-edit-draft-1440x900.png` | `8c4038ef03ae882ff8a099b12c78dba0affa4ef733ddec8a2f7fb9c68a341b97` |
| `administration-attribute-edit-draft-1920x1080.png` | `da0965abe9a9d0627979b549a71ae6a5fcaa0c5483e6f395ae751b422578810e` |
| `administration-edit-stale-conflict-1440x900.png` | `e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21` |
| `administration-attribute-long-invalid-1440x900.png` | `ac798d466063d9d0408f8f2e7d69ff39e92f6514fafdb4f4838b0582307cb898` |
| `administration-database-normal-wide-2560x1440.png` | `45b484095aa6a60f36ee53717aeb2fe15efafc67ce108d1b383a11f84bc82b12` |
| `administration-database-normal-wide-3840x2160.png` | `ed1a3050676bbed8504eeeb97d0ee7f58b1509318def6924a46a24e0de3a883f` |

## Deterministic results supplied to the reviewer

The main agent independently reran and passed:

```powershell
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

Wide measurements:

| Viewport | Editor | Editor-to-preview gap | Record / grid | Graph | Record-to-graph gutter | top delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2560×1440 | 808 px | 21 px | 541 / 524×460 px | 461×360 px | 20 px | 0 px |
| 3840×2160 | 808 px | 21 px | 640 / 623×460 px | 700×360 px | 20 px | 0 px |

Both wide targets record 547 px of genuine Record-grid overflow, a visible proportional rail and
successful wheel, PageDown, Home, End and pointer scrolling. These measurements are safety rails,
not substitutes for full-screen qualitative review.

## Required independent disposition

Complete V-01–V-16 and the canonical Q-01–Q-20 checklist. Record `pass`, `fail`, or
`not-applicable` plus direct image/path evidence for every Q item. At minimum, treat Q-02, Q-09,
Q-17, Q-18 and Q-20 as applicable and explicitly evaluate:

- full-screen hierarchy, density, typography and absence of nested-card styling;
- complete/reachable Object names and family-specific columns;
- one active saved projection and compact preview return;
- real scroll affordance without title or value overlap;
- graph engineering labels, aspect ratio, headroom and secondary visual weight;
- left/top working-cluster alignment without a blank internal column;
- absence of forced fill, stretched rows/prose/plot, filler or invented internal terminology;
- valid loading, saving, error, stale, selection and keyboard recovery behavior.

Return one disposition: `approve` or `changes_requested`, with actionable findings and residual
risks. Do not edit files, recapture evidence, change lifecycle state or make a product-owner
approval decision.
