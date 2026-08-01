# Issue #167 ADM-SCHEMA-CORE final cluster-chrome review packet

Date: 2026-07-31
Reviewer role: fresh configured Terra High, read-only
Lifecycle: eleven approval targets `pending`; main-agent evaluation `accepted`; product-owner approval
`absent`

## Bounded acceptance

Review the product-owner-authorized final qualitative correction only after reading:

- `docs/17-evidence/reports/issue-167-owner-authorized-extra-correction-packet-adm-preview-cluster-chrome.md`
- `docs/17-evidence/reports/issue-167-owner-authorized-correction-packet-adm-preview-information-architecture.md`
- `docs/17-evidence/reports/issue-167-correction-packet-adm-preview-wide-semantic-elasticity.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`

The final correction must:

- bound the preview heading, tabs, context, Record grid and graph as one coherent left/top task
  cluster at wide viewports;
- leave unused width outside that bounded cluster at the far right instead of inside full-width
  heading/tab/context rules;
- expose exactly one return action: task-bar `Close preview` on wide layouts and in-preview
  `Back to editor` on compact layouts;
- preserve focus return, one active saved projection, real Record overflow, conditional linked
  graph, graph-free scalar Attribute editing, exact revision truth and all recovery states;
- preserve the approved compact density and avoid cards, filler, invented terminology, forced
  stretching, overlap and clipping.

## Exact implementation and evidence

Review these implementation paths:

- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

The staging JSON is the finite index for all eleven lifecycle targets, sixty responsive state images
and two wide support images. Open every indexed PNG at original resolution and verify its recorded
SHA-256. Do not rely on contact sheets, measurements or previous reviewer conclusions as a
substitute for full-screen visual judgment.

Approval-target and wide-support hashes:

| Image | SHA-256 |
| --- | --- |
| `administration-database-normal-1366x768.png` | `9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724` |
| `administration-database-normal-1440x900.png` | `1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf` |
| `administration-database-normal-1920x1080.png` | `dd5bc7fecbe53bf6e97c94e5da99e86a2085b4f4672dfe483a56b8cdd1050d7c` |
| `administration-table-edit-draft-1366x768.png` | `9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69` |
| `administration-table-edit-draft-1440x900.png` | `2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284` |
| `administration-table-edit-draft-1920x1080.png` | `eace016ff08a9b76577ba30761e35e99a43eee3d525b39f66c65e7c2d6fc6909` |
| `administration-attribute-edit-draft-1366x768.png` | `6eeb19ed91e1ea343623ae16c837d514bb97b85c307157dfe56f53af6b0d6b1f` |
| `administration-attribute-edit-draft-1440x900.png` | `8c4038ef03ae882ff8a099b12c78dba0affa4ef733ddec8a2f7fb9c68a341b97` |
| `administration-attribute-edit-draft-1920x1080.png` | `da0965abe9a9d0627979b549a71ae6a5fcaa0c5483e6f395ae751b422578810e` |
| `administration-edit-stale-conflict-1440x900.png` | `e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21` |
| `administration-attribute-long-invalid-1440x900.png` | `ac798d466063d9d0408f8f2e7d69ff39e92f6514fafdb4f4838b0582307cb898` |
| `administration-database-normal-wide-2560x1440.png` | `500bbd5c0a3aeb06ce81967904275cbca0a1e3eb6f6626271a3cb5a9b224e774` |
| `administration-database-normal-wide-3840x2160.png` | `bbcaf1243e0396790b37cf659c248fb1224941058c26b8e69269cc8aed2b91bb` |

The aggregate digest for the sixty responsive state images is
`191ea454ae94a98c940fadc3152fe1404ab5180dd687cd995383a661cab4d2a7`.

## Main-agent deterministic and qualitative evidence

The main agent independently passed:

```powershell
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

At 3840×2160, `.preview-content` is capped at 1360 px and the complete visible task chrome ends at
the Record-plus-graph cluster. The heading, tabs and context share a 1327 px right bound; Record and
graph share a top edge with a 20 px gutter. At 2560×1440, the same composition uses the naturally
available 1055 px preview width. Both wide targets expose only `Close preview`; compact targets
expose only `Back to editor`. The active Record region retains 547 px of genuine overflow and
verified pointer, wheel, PageDown, Home and End consequences.

These measurements are safety rails. The main-agent qualitative review also found that the former
detached duplicate action and unfinished full-width component appearance are gone: blank space now
starts outside the bounded task at the far right and below the completed task, without fabricated
content.

## Required independent disposition

Independently rerun the non-mutating commands above and complete V-01–V-16 and canonical Q-01–Q-20.
Record `pass`, `fail` or `not-applicable` with direct image/path evidence for every applicable item.
Treat Q-02, Q-09, Q-17, Q-18 and Q-20 as applicable.

In addition to contract and measurement checks, explicitly judge:

- whether the 1366, 1440, 1920, 2560 and 3840 full screens look proportionate and intentional;
- whether typography, control density and hierarchy read as professional engineering software;
- whether any prose, label or action appears duplicated, internal, invented or forced into the UI;
- whether heading/tab/context boundaries visually finish with the task rather than stretching into
  unused viewport space;
- whether trailing whitespace is outside a coherent left/top component cluster;
- whether table/tree/graph dominance, scroll affordance, graph labels and graph bounds remain
  readable without clipping or crowding;
- whether state, keyboard, exact-revision and saved-versus-draft behavior remain truthful.

Return exactly one disposition, `approve` or `changes_requested`, plus actionable findings and
residual risks. Do not edit files, recapture evidence, change lifecycle state or make a
product-owner approval decision.
