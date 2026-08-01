# Issue #167 reviewer packet — MAT-DETAIL navigator coherence

Date: 2026-07-30
Reviewer: one fresh configured Terra High, read-only
Issue: GitHub #167

## Acceptance boundary

Review the three changed normal Materials datasheet references as one MAT-DETAIL family. The exact
selected Record, six datasheet tabs, properties, linked response graph, application condition and
solver-card consequences must persist while the navigator adopts the same compact, readable
Database → Profile → Table → Folder → Record grammar as Materials search.

Do not edit files, regenerate captures, commit, push or change GitHub. Use:

- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/visual-acceptance-matrix.md`, including every Q-01–Q-20 item;
- `docs/17-evidence/reports/issue-167-implementer-packet-materials-navigator-coherence.md`;
- `docs/17-evidence/reports/issue-167-correction-packet-materials-navigator-coherence.md`.

## Approval candidates and comparison evidence

Open every candidate at original resolution:

| Viewport | Path | SHA-256 |
| --- | --- | --- |
| 1366×768 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png` | `67c296ad84bce9cb67195c09d6356efa9139d7c509255edc4bb969e13337529b` |
| 1440×900 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png` | `fb3a6ccd943f83ac872d27c7f1736597e1c74e964b0cdb99a7e36479106bea4c` |
| 1920×1080 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png` | `dc67582b5218f9f65602820d0c336097f1d3a4e28b8dbd237581eef8484031ac` |

Also inspect:

- `materials-datasheet-overview-normal-1920x1080.wide-evidence-2560x1440.png`
  (`0bc0f08cce179d32275c5b226674351628c372c900cf2298171b78ed4ade019d`);
- `materials-datasheet-overview-normal-1920x1080.wide-evidence-3840x2160.png`
  (`640c78e719af4f2feea98aee999732133506ce7efa3f9076e0435fb2176af9fa`);
- the approved MAT-EXP long-tree comparison;
- byte-preserved `materials-datasheet-related-long-1440x900.png`
  (`810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6`);
- byte-preserved `materials-datasheet-empty-1440x900.png`
  (`8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6`);
- every registered responsive and selected-record loading/error/blocked evidence image.

## Diff and supplied evidence

Inspect the bounded MAT-DETAIL diff in:

- `materials-datasheet-overview-normal.html`;
- `materials-navigator.css`;
- `materials-navigator.js`;
- the 1920 detail override;
- `capture_materials_datasheet_wave01.py`;
- `validate_materials_datasheet_wave01.py`;
- `materials-datasheet-wave01.staging.json`;
- the normal/wide images and measurements;
- the serial manifest/inventory/report lifecycle integration.

The main agent opened all five normal/wide images at original resolution. Full DP780/DP600 tree
identities are visible at the default widths, kind words no longer consume a trailing column, short
content has no fake rail, and the minimum-width/long fixture exposes real reserved scroll controls
without covering text. The selected Record, graph axes/ticks/legend, data-relative
`0.25 strain / 1,000 MPa` domains, condition semantics and delivery actions remain complete. At
2560/3840 the graph uses the elastic result region without non-uniform SVG stretching or filler.

## Required independent disposition

Rerun only non-mutating gates. Validate all packet targets, 1920 wide evidence and every preserved
exceptional hash. Independently exercise the navigator splitter and local scroll controls, tabs,
Back to results, graph accessibility and delivery actions. Complete V-01–V-16 and every Q-01–Q-20
item as `pass`, `fail` or genuinely topology-specific `not-applicable`, citing direct image/path
evidence. Judge full-screen tree/datasheet coherence and engineering readability, not assertions
alone.

Return actionable findings first, hard-gate result, score/checklist, residual concerns and either
`approve` or `changes_requested`. Do not modify any file.
