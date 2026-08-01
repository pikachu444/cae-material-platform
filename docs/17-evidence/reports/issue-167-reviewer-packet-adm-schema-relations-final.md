# Issue #167 — ADM-SCHEMA-RELATIONS final reviewer packet

Date: 2026-08-01
Review mode: fresh configured Terra High, independent and read-only
Lifecycle: 9 approval targets `pending`; main-agent correction gate passed; product-owner approval absent

## Bounded acceptance

Review only the final Administration Layout, Subset and Link Type service-reference bundle. This is
static #167 reference work; it does not authorize production React/CSS or #157. The reviewer must
independently reject any full-screen qualitative failure even when deterministic measurements pass.

Required task and domain behavior:

- the three continuous panes remain `Schema objects | family list | editor + read-only preview`;
- Layout orders user-selected exact Attribute revisions and keeps saved Record values visible;
- Subset counts and rows come from the same scoped result and an invalid filter cannot be saved;
- Link Type preserves exact source/target revision pins and visible one-to-many branching;
- one canonical top command set is used; the editor has only the local `Discard draft` action;
- 2560×1440 and 3840×2160 keep a bounded, left/top-aligned working cluster without clipping or
  stretching content to fill the viewport;
- loading, error and blocked states preserve context and expose a truthful consequence or recovery.

Authority:

- Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
- Approved checkpoint: branch `issue-167-service-reference-freeze`, commit `3b72d48`
- Candidate branch checkpoint: `agent/complete-167-and-157`, commit `2bcbbfa`, plus the current
  uncommitted correction diff
- `docs/01-product/service-reference-inventory.yaml`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-administration-remaining-correction-packet.md`

## Implementation and evidence

- `docs/00-research/ux-service-reference/administration-remaining.html`
- `docs/00-research/ux-service-reference/administration-remaining.css`
- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

Open every image below at original resolution. The staging JSON is the finite hash and measurement
index for the normal, wide and state evidence.

Approval targets:

| Image | SHA-256 |
| --- | --- |
| `administration-layout-edit-draft-1366x768.png` | `afee2c3d3fd0b820d96f01ec3b70e30d6ea0077b9f796ff2b622babee2df7f2f` |
| `administration-layout-edit-draft-1440x900.png` | `d6a75a1b0aa42f189209b79fc03cda70bad96d91a840c50ea425aa67c3565d91` |
| `administration-layout-edit-draft-1920x1080.png` | `dba360e90511548c499f44fa0bca14f70ac754722369f539c2728673682eddbc` |
| `administration-subset-edit-draft-1366x768.png` | `f8e470899cb5300c26a42bde0ca57ab46e6ac920bf23c6ebf43489c319f793d5` |
| `administration-subset-edit-draft-1440x900.png` | `08a07d0d264ac41134fcc84617344460e407f411c165f7f124fa489652efd3cb` |
| `administration-subset-edit-draft-1920x1080.png` | `f451e528409cbd0a68e0f9afe8da384cc35e282affbef691900831e24709d767` |
| `administration-link-type-edit-draft-1366x768.png` | `e051f463bd391450e323bbeb21011d31d1d7ef4c140ce5281a4202bf517ae687` |
| `administration-link-type-edit-draft-1440x900.png` | `94b967c8d5ed5b96d2234115d247302394395875efcff77cfa3483449cb0cb57` |
| `administration-link-type-edit-draft-1920x1080.png` | `e970d43fecd177e4d9bca62ab08d26981c1cc012e7979126f35c91017162424a` |

Wide support:

| Image | SHA-256 |
| --- | --- |
| `administration-layout-edit-draft-wide-2560x1440.png` | `8cd1ff0f08ca5a03374dffe9a9e32e0a633fd5842a221262024e984bba3640f9` |
| `administration-layout-edit-draft-wide-3840x2160.png` | `865762eccd197b12de3633f6bdccde04143e13a70c4ad6ade0b92d696fa5548c` |
| `administration-subset-edit-draft-wide-2560x1440.png` | `2c89a3e0aabfdd791482bdf7999cb9ff26b9ac9ff6e71c7d5130cbc6eb80e954` |
| `administration-subset-edit-draft-wide-3840x2160.png` | `7e716603c8da0a8d032863568581ce089084d6437cb84ffe856c81b27ab41a39` |
| `administration-link-type-edit-draft-wide-2560x1440.png` | `cb6bc5897e999631b7acd319753c1e9cbfbc83859a1d5a7181dde33713391e86` |
| `administration-link-type-edit-draft-wide-3840x2160.png` | `bc601b0a6954f99def1c63d0d03f3f4e5c046e55c07e1f8e068d1cb98ae38618` |

State evidence, each at 1366×768, 1440×900 and 1920×1080:

- `administration-layout-missing-attribute-blocked-*`
- `administration-layout-preview-error-*`
- `administration-layout-preview-loading-*`
- `administration-subset-invalid-filter-blocked-*`
- `administration-subset-preview-error-*`
- `administration-subset-preview-loading-*`
- `administration-link-type-invalid-endpoint-or-cardinality-blocked-*`
- `administration-link-type-related-test-error-*`
- `administration-link-type-validation-loading-*`

## Supplied deterministic result

The main agent independently reran:

```powershell
node --check docs/00-research/ux-service-reference/administration-remaining.js
.venv\Scripts\ruff.exe check docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/finalize_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/finalize_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

Result: `PASS: 1815 checks across 72 captures`; inventory `55/72 approved; 17 remaining`; diff check
clean.

## Required independent disposition

Complete V-01–V-16 and every Q-01–Q-20 item with `pass`, `fail` or `not-applicable` plus a direct
path-based reason. Treat at least Q-01, Q-02, Q-09, Q-17, Q-18, Q-19 and Q-20 as applicable.
Explicitly inspect full-screen hierarchy, local overflow, complete/reachable identities, command
duplication, exact-revision/cardinality truth, state recovery, wide bounded composition and the
absence of internal/developer vocabulary or fabricated filler.

Return exactly one disposition, `approve` or `changes_requested`, with actionable findings and
residual risks. Do not edit, recapture, commit, push, alter lifecycle state or infer product-owner
approval.
