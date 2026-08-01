# Issue #167 reviewer packet — MAT-DETAIL wide response density

Date: 2026-07-30
Scope: read-only review of `Materials / Datasheet / Overview / normal`

## Issue acceptance

Review the bounded implementation against:

- `AGENTS.md`
- `docs/17-evidence/reports/issue-167-implementer-packet-wide-mat-detail-response-grid.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`, sections 4.2.1 and 5.6
- `docs/01-product/desktop-engineering-ui-spec.md`, sections 3.4 and 5
- `docs/01-product/visual-acceptance-matrix.md`, V-01–V-16 and Q-01–Q-20

The required outcome is one exact ordered response source shared by graph and table. The point grid
is absent at 1366/1440, appears beside a still-dominant graph at 1920/2560/3840, scrolls locally only
on real overflow and has no fake rail when every row fits. The selected Record, compact navigator,
property table, Application condition, CAE delivery and Related/empty evidence remain preserved.

## Approved dependency and preserved comparison

Product-owner-approved MAT-EXP dependency:

| Viewport | SHA-256 |
| --- | --- |
| 1366×768 | `bd400b2f913a0d2c8c1e5dba6565c05b12055118ffbbaac1b9e5845cf6bfff89` |
| 1440×900 | `7f96a68d0ff03eb20b95abf831354e6a1052e34f0246871c9318ede0cce367a0` |
| 1920×1080 | `57f136268f52386c99cb13970f694cf40a30bdb57a6bc3badcab0b70a24ed3ae` |

Frozen MAT-DETAIL exceptional images:

| Image | SHA-256 |
| --- | --- |
| `materials-datasheet-related-long-1440x900.png` | `810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6` |
| `materials-datasheet-related-long-1440x900.responsive-1366x768.png` | `4963c0eb91ba711ffcaf370999fb07dbb53735ce6dce32fe5884e675170a583d` |
| `materials-datasheet-related-long-1440x900.responsive-1920x1080.png` | `bf98b166f6b89ffae6baddb24321296837b340704352d74769b5764334eb0fc2` |
| `materials-datasheet-empty-1440x900.png` | `8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6` |
| `materials-datasheet-empty-1440x900.responsive-1366x768.png` | `9aa40656c8aa86fe858b438efd5f9447401af439b629df65e25b7e6537fb0d95` |
| `materials-datasheet-empty-1440x900.responsive-1920x1080.png` | `958b8b7f228d6df776885ddcb3760b33881625b9fd1086a94db38fdb3bffa1d5` |

## Implementation diff

Review only these authored reference paths plus their generated evidence:

- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`
- `docs/00-research/ux-service-reference/materials-datasheet.css`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.css`
- `docs/00-research/ux-service-reference/materials-datasheet.js`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.js`
- `docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py`
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`
- the five image/measurement pairs below
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-wave01.staging.json`
- main-agent integration diff in the manifest, product/UI specification, acceptance matrix and
  `issue-167-service-reference-freeze.md`

Production contract context is read-only:

- `apps/web/src/material-library.tsx`: `MaterialExperience.representativeCurve`,
  `curveFromNativeCard`, `loadMaterialExperience`, `RepresentativeCurve`, Material Overview
- `apps/web/src/material-datasheet-projection.tsx`: Layout-ordered typed Record/curve projection

## Direct image evidence

| Viewport | Path | SHA-256 |
| --- | --- | --- |
| 1366×768 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png` | `89fafcd8245fec6742d48ad32d0a8ac9909265554eac5cbe3d74c7d869b6a4d0` |
| 1440×900 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png` | `afa1c12b73b06223955a62b2ca937484be27d76a9cfc203190abd63081c353eb` |
| 1920×1080 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png` | `ac1785993e00de1972826019aafe9b907ae0821676464310624c10e9dac4be4a` |
| 2560×1440 support | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-2560x1440.png` | `df5155fbecb6384558e22a83ea987d50cee9676e1deed910b173e8dad6ab72e7` |
| 3840×2160 support | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-3840x2160.png` | `86d4879f6b19cc4d91760862cba98d63f89527bde3b9ad25c943ccfa6d385156` |

Open all five images at original resolution. The superseded main-agent rejection and earlier hashes
are recorded in sections 62 and 66 of `issue-167-service-reference-freeze.md`.

## Interaction and deterministic results

The configured Luna Max implementer completed the bounded authoring pass. The main agent then reran:

```powershell
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --all-packet-targets --expect-main-agent-status accepted --assert-preserved-hashes
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1920x1080 --expect-main-agent-status accepted --wide-evidence --assert-preserved-hashes
node --check docs/00-research/ux-service-reference/materials-datasheet.js
node --check docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.js
python -m py_compile docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
python -m ruff check docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
git diff --check
```

Expected measured facts:

- graph and table each contain the exact ordered 29-point `#response-series`;
- 1366/1440 hide the grid and retain 795×240 / 829×330 plots;
- 1920 uses 953 px graph + 340 px grid; overflow 347 px and proportional 243 px thumb;
- 2560 uses 1433 px graph + 500 px grid; overflow 117 px and proportional 566 px thumb;
- 3840 uses 2713 px graph + 500 px grid; all 29 rows fit and the rail is absent;
- pointer, wheel, Arrow, Page, Home and End consequences pass where the table overflows;
- plot viewBox/rendered aspect delta is zero; axes/ticks/titles/legend are contained; 10% data-span
  headroom resolves to 0.25 strain and 1,000 MPa;
- page/document overflow, nested controls, console errors and page errors are zero;
- all six frozen Related/empty hashes remain exact.

## Required independent disposition

Record:

- V-01–V-16 score with every hard gate;
- Q-01–Q-20 as `pass`, `fail` or `not-applicable`, with a topology reason for every N/A;
- contract/data-source fidelity, accessibility and latest Web Interface Guidelines findings;
- full-screen qualitative findings at all five original resolutions;
- exact rerun command results and matched SHA-256 values;
- `approve` or `changes_requested`, with only actionable findings.

The reviewer is read-only. It does not update lifecycle, images or implementation.
