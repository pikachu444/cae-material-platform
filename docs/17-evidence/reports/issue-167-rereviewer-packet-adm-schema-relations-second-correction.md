# Issue #167 — ADM-SCHEMA-RELATIONS second-correction re-review packet

Date: 2026-08-01
Review mode: fresh configured Terra High, independent and read-only
Lifecycle: 9 approval targets `pending`; product-owner approval absent

## Scope and correction to verify

Review only the final Administration Layout, Subset and Link Type service-reference bundle after the
product-owner-authorized second and last correction. The accepted correction made every family-list
row a real selector: pointer and keyboard selection now update selected styling, the complete editor
identity, row-specific editor/preview context and the status summary. The lists use a synchronized
roving focus model for `ArrowDown`, `ArrowUp`, `Home`, `End` and `Enter`; ellipsized identities remain
available through the accessible name/title and the selected editor heading.

The first review's Q-18 concern about `Add Table` / `Add Attribute` is `not-applicable` here. The
already approved prerequisite `ADM-SCHEMA-CORE` owns object creation; this bundle owns editing the
selected Layout, Subset or Link Type. Do not reopen that approved prerequisite.

Preserve and judge the existing three continuous panes, exact-revision and cardinality truth,
single canonical command set, local scrolling, state recovery and bounded left/top-aligned wide
composition. This is static #167 reference work; it does not authorize production React/CSS, #157,
recapture, lifecycle changes, commits or pushes.

## Authority and evidence

- Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
- Candidate branch: `agent/complete-167-and-157`, checkpoint `2bcbbfa` plus current uncommitted WAVE-06 diff
- `docs/01-product/service-reference-inventory.yaml`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-second-correction-packet-adm-relations-access-luna.md`
- `docs/00-research/ux-service-reference/administration-remaining.html`
- `docs/00-research/ux-service-reference/administration-remaining.css`
- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

The staging JSON is the finite path/hash/measurement and interaction index. Open all 42 images below
at original resolution under `docs/17-evidence/images/issue-167-service-reference/`.

## Approval targets

| Image | SHA-256 |
| --- | --- |
| `administration-layout-edit-draft-1366x768.png` | `fb149e4885106512b543e5e20394b2fe64a72eaa42fb9f9134e392c5605596b8` |
| `administration-layout-edit-draft-1440x900.png` | `84c01e3fb09aab698307c8c3eb90c23d4265aac0974d4ff75af15490b8731d47` |
| `administration-layout-edit-draft-1920x1080.png` | `a14c328d3992af1cebc0bb26f1f7b550432f7170f39501165742073632a0f03c` |
| `administration-subset-edit-draft-1366x768.png` | `820ccede55774feaa060ea39707bdc1a8717e5cc2d8b59d694cc9bc4a9e85cc1` |
| `administration-subset-edit-draft-1440x900.png` | `1a333cba51ee882d58eb7630a63cea459ddd60e87f5b0e6257eb0a274a890641` |
| `administration-subset-edit-draft-1920x1080.png` | `2cb8f6a71ebd33e2db131e4a364245a50e966d1bdfa3984138bb3b9ae5f44c8b` |
| `administration-link-type-edit-draft-1366x768.png` | `2a7950527a0ef4c24f8261b4764f188cf70fb5608ffccd4597d94136e8970e77` |
| `administration-link-type-edit-draft-1440x900.png` | `f6bbd8bfc106869fd9fef37e52f3f4433b24d0daeb250cdab73d2572cbacc5c7` |
| `administration-link-type-edit-draft-1920x1080.png` | `3b69de18a9c61008bf7fadd1f6e4041279ac668d5eae589a3b9671125651a077` |

## Wide support

| Image | SHA-256 |
| --- | --- |
| `administration-layout-edit-draft-wide-2560x1440.png` | `19bb6fb4fcd20a343786da1a7a2d3d1f499376f11239c5779b181f8a5df170ac` |
| `administration-layout-edit-draft-wide-3840x2160.png` | `f8c7b8c626d43d95899a25d55645626e01205c96262f6fe878203ebbbbccc3dd` |
| `administration-subset-edit-draft-wide-2560x1440.png` | `dd9bfc356d9d0647aa190e61081a1a53b40acbf74a288214b8a5739b0c183c68` |
| `administration-subset-edit-draft-wide-3840x2160.png` | `55a50a78de41b34709bc9b33ccefca2d1bb5bbce5430435ce9e1552fca9c76bd` |
| `administration-link-type-edit-draft-wide-2560x1440.png` | `f7d5d32ca9a9e3a47958688d407f91c2ff40ce496c917ab1887deb4f73e347f8` |
| `administration-link-type-edit-draft-wide-3840x2160.png` | `523bc04304ccf2543dae1554995ffb96a8886e11a47d1a7eeeb961e747b49777` |

## State evidence

Open each pattern at 1366×768, 1440×900 and 1920×1080 (27 images):

- `administration-layout-missing-attribute-blocked-*`
- `administration-layout-preview-error-*`
- `administration-layout-preview-loading-*`
- `administration-subset-invalid-filter-blocked-*`
- `administration-subset-preview-error-*`
- `administration-subset-preview-loading-*`
- `administration-link-type-invalid-endpoint-or-cardinality-blocked-*`
- `administration-link-type-related-test-error-*`
- `administration-link-type-validation-loading-*`

## Supplied gates and required disposition

The main agent independently obtained `PASS: 1861 checks across 72 captures`; Node syntax, Ruff,
`py_compile`, inventory (`55/72 approved; 17 remaining`) and `git diff --check` passed. Interaction
evidence exercises every non-default row in all three viewports, all five keyboard commands, focus,
selection, `aria-pressed`, full editor identity, row-specific preview and status identity. The main
agent also opened all 42 bundle images at original resolution and found no blocking qualitative issue.

Independently complete V-01–V-16 and Q-01–Q-20 from the canonical matrix with `pass`, `fail` or
`not-applicable` and a direct path-based reason. Treat Q-01, Q-02, Q-09, Q-17, Q-19 and Q-20 as
applicable; record Q-18 as `not-applicable` for the prerequisite reason above. Verify full-screen
hierarchy, local overflow, reachable full identities, pointer/keyboard continuity, command
duplication, exact-revision/cardinality truth, recovery states, wide composition and the absence of
developer vocabulary or fabricated filler.

Return exactly one disposition, `approve` or `changes_requested`, with actionable findings and
residual risks. Do not edit, recapture, change lifecycle state, commit, push or infer product-owner
approval. This is the final allowed re-review; do not propose an unbounded redesign.
