# Issue #167 reviewer packet — MAT-EXP wide result density

Date: 2026-07-30
Reviewer: one fresh configured `reviewer_terra_high`, read-only
Owner: active `/root` main agent

## Bounded review

Review only `Materials / search-results / normal` after the product-owner-directed cross-family
large-display correction. Do not edit files, recapture evidence, update lifecycle state or review
Datasheet, Administration, production React/CSS, commits, pushes, PRs or merges.

Issue acceptance and governing policy:

- <https://github.com/pikachu444/cae-material-platform/issues/167>
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`, including the complete mandatory Q-01–Q-20
  qualitative checklist
- `docs/17-evidence/reports/issue-167-implementer-packet-wide-mat-exp-density.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`, sections 62–63

The exact contract reviewed by the main agent is:

- `apps/web/src/material-library.tsx:407` — one page requests `limit: 50`;
- `apps/web/src/api.ts:1042` and `apps/web/src/api.ts:1058` — response count/offset/limit and default
  request page;
- `apps/web/src/app.test.tsx:235` — 50 items out of 10,000 with no row-detail enrichment.

## Review evidence

Open every image below at original resolution and independently judge the whole screen:

| Viewport | Image | SHA-256 |
| --- | --- | --- |
| 1366×768 | `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png` | `bd400b2f913a0d2c8c1e5dba6565c05b12055118ffbbaac1b9e5845cf6bfff89` |
| 1440×900 | `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png` | `7f96a68d0ff03eb20b95abf831354e6a1052e34f0246871c9318ede0cce367a0` |
| 1920×1080 | `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png` | `57f136268f52386c99cb13970f694cf40a30bdb57a6bc3badcab0b70a24ed3ae` |
| 2560×1440 support | `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.wide-evidence-2560x1440.png` | `004b040f7045f7889f0264b3d418bccef605d6158d6b8dbe6bc12e62977dd50d` |
| 3840×2160 support | `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.wide-evidence-3840x2160.png` | `fec578d690b4573a2d049e7c2fd50d24540e866b20a71c89c40ccd8bc69784df` |

Use the corresponding measurement JSON files beside those images. Compare navigator/tree grammar
against the approved MAT-EXP long/empty references registered in
`docs/01-product/service-reference-manifest.yaml`; their hashes must remain unchanged.

Implementation diff boundary:

- `docs/00-research/ux-service-reference/materials-search-normal.html`
- `docs/00-research/ux-service-reference/reference.css`
- `docs/00-research/ux-service-reference/reference.js`
- `docs/00-research/ux-service-reference/capture_reference.py`
- `docs/00-research/ux-service-reference/validate_reference.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`
- the five Search image/measurement pairs above
- the main-agent-owned manifest, product policy and sections 62–63 evidence changes

## Required independent disposition

Rerun these non-mutating checks:

```powershell
python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted --wide-evidence
python docs/00-research/ux-service-reference/validate_materials_search_wave03.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
node --check docs/00-research/ux-service-reference/reference.js
```

Independently verify:

- 50 distinct synthetic rows, the truthful `1–50 of 10,000` range and no added detail fetch;
- 14/18/23/33/50 complete initially visible rows, with no partial bottom row;
- sticky result header and fixed range/paging footer;
- the reserved result rail appears only on genuine overflow, stays outside text and has
  pointer/wheel/Arrow/Page/Home/End consequences;
- DP780/DP600 result/tree/context synchronization, non-Record context preservation and compare limit;
- no body overflow, clipped tree identity, scrollbar/title collision, nested persistent card,
  stretched row/font/prose, fabricated filler or avoidable dominant blank region;
- at 3840, hiding the rail after all 50 rows fit is preferable to stretching rows or inventing
  content;
- every applicable Q-01–Q-20 item with explicit pass/fail/not-applicable evidence, emphasizing
  Q-01–Q-03, Q-09 and Q-20;
- V-01–V-16 and every hard gate.

Return `approve` or `changes_requested`, exact actionable findings, V score, hard-gate result and the
complete Q checklist. The reviewer is independent evidence; final product/UX authority remains with
the active main agent and product owner.
