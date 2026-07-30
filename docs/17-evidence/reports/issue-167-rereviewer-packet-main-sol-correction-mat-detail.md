# #167 fresh review packet — MAT-DETAIL direct correction

Date: 2026-07-30
Mode: bounded read-only review

Follow the reviewer role and workflow defined by `AGENTS.md`, `.codex/config.toml` and the configured
reviewer agent file. Do not edit files.

## Acceptance under review

1. The normal 1366, 1440, 1920, 2560 and 3840 graphs derive SVG geometry from the rendered box and
   do not stretch independently by axis.
2. Both axis titles are present and consistent: `Engineering strain` and
   `Engineering stress (MPa)`; tick values do not repeat units.
3. The declared series remains strain `0–0.20` and stress `0–850 MPa`. Data-span-relative headroom
   yields displayed maxima `0.25` and `1,000 MPa` without touching the top or right axes.
4. Compact viewports use available height to improve graph legibility without clipping the legend,
   right-side delivery actions or status bar.
5. The shared Materials navigator remains coherent and approved Related/empty evidence is frozen.

## Required original-resolution images

| Image | SHA-256 |
| --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png` | `ac9e1b781974062688a12771c1c26d8b9b388ef20522f62030cb2fd19aca3d37` |
| `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png` | `4015b2b014e895d0e990987af820b236f4c090d155aa6817abcb35f6ab75f69a` |
| `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png` | `dc67582b5218f9f65602820d0c336097f1d3a4e28b8dbd237581eef8484031ac` |
| `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-2560x1440.png` | `0bc0f08cce179d32275c5b226674351628c372c900cf2298171b78ed4ade019d` |
| `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-3840x2160.png` | `640c78e719af4f2feea98aee999732133506ce7efa3f9076e0435fb2176af9fa` |

## Implementation and evidence

- packet:
  `docs/17-evidence/reports/issue-167-main-sol-direct-correction-packet-materials-admin.md`;
- implementation:
  `materials-datasheet-overview-normal.html`, `materials-datasheet.css`,
  `materials-datasheet.js`, `materials-datasheet-overview-normal-1920x1080.js`;
- browser evidence:
  `capture_materials_datasheet_wave01.py` and the normal/wide measurement files;
- deterministic contract:
  `validate_materials_datasheet_wave01.py`;
- lifecycle/evidence:
  `docs/01-product/service-reference-manifest.yaml`,
  `docs/17-evidence/reports/issue-167-service-reference-freeze.md` §60.

Rerun the all-packet validator against the common manifest with expected main-agent status
`accepted` and preserved hashes, then rerun the 1920 target with wide evidence. Complete every
applicable Q-01–Q-20 item before V-01–V-16 scoring. Return actionable findings first and then exactly
`approve` or `changes_requested`.
