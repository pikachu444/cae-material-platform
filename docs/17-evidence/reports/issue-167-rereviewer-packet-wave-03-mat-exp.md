# Issue #167 fresh re-review packet — WAVE-03 / MAT-EXP correction

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance

Review the product-owner-authorized correction of the two still-pending Materials exceptional
references:

- `materials-search-long-1440x900`
- `materials-search-empty-1440x900`

The approved normal family remains frozen. The correction must preserve its continuous
navigator/results/context topology while making tree and long-result scrolling visually
discoverable, using 24–26 px compact tree rows, reducing indentation/type-label width tax and
exposing complete long identities through accessible names/title and local scrolling. Long remains
50 of 126 rows with one selection/context; empty remains zero rows/selections, keeps `Find` as the
sole filled primary action and exposes `Clear search` as the secondary recovery.

The product owner rejected the preceding reviewed version because its synthetic vertical scrollbar
overpainted long tree titles. Specifically verify that the current tree uses a reserved native
scrollbar gutter, that no custom indicator overlays any title, and that this remains true in every
responsive and state image.

Open and assess all 18 current MAT-EXP images at original resolution: two candidates, their
1366/1920 responsive siblings, and loading/tree-loading/query-error/tree-error at all three
viewports. Score V-01–V-16 from `docs/01-product/visual-acceptance-matrix.md`. Passing requires at
least 28/32, no hard-gate zero and complete evidence. Do not edit any file.

Authoritative correction packet:
`docs/17-evidence/reports/issue-167-correction-packet-wave-03-mat-exp.md`.

## Approved parents

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
  — `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
  — `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png`
  — `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`

## Corrected candidates and evidence

- `docs/17-evidence/images/issue-167-service-reference/materials-search-long-1440x900.png`
  — `bc3812759e3fae464fde19782767e5680f10ba343898f3beb9d59b362613a66d`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-empty-1440x900.png`
  — `35e814d1e807468f97e3daaa6507a4ae98bba1a1e5d3fa2dc731a0e77a922725`
- complete paths, dimensions and hashes:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.state-evidence.json`

The source/evidence diff boundary is:

- `docs/00-research/ux-service-reference/materials-search-exceptional.html`
- `docs/00-research/ux-service-reference/materials-search-exceptional.css`
- `docs/00-research/ux-service-reference/materials-search-exceptional.js`
- `docs/00-research/ux-service-reference/capture_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.staging.json`
- the MAT-EXP WAVE-03 images, measurements and state-evidence JSON above
- the two MAT-EXP pending lifecycle entries only in
  `docs/01-product/service-reference-manifest.yaml`

No approved parent, shared Materials normal CSS/JavaScript, production UI or other family was
changed.

## Main-agent and deterministic evidence

The main agent opened all 18 final images at original resolution. It confirmed independent local
tree/result scrolling, a native tree scrollbar with a measured 15 px reservation and no custom
overlay, 25 px rows, 9 px indentation increments, longer usable identity width, one selected long
record/context, no empty-state stale selection and no fake empty result scrollbar.

```text
family validator                                             pass, 18 targets
approved normal validators                                   pass, hashes unchanged
long rows / total / local result scroll                      50 / 126 / wheel+PageDown
tree local scroll at 1366/1440/1920                          wheel+PageDown
tree native gutter / custom overlay                          15 px / absent
empty result overflow / selected tree-result-context         zero / zero
tree row height / indentation increment                      25 px / 9 px
titles and accessible node types                             pass
empty visible filled actions / secondary recovery            Find only / Clear search
splitters, keyboard navigation and recovery                  pass
console/page errors; document/body overflow                  zero
legacy selectors / nested interaction                       zero
Ruff / Node syntax / inventory / diff checks                 pass
lifecycle                                                     pending / main accepted / PO absent
```

Fresh Terra High result: `approve`; V-01–V-16 all `2`, total `32/32`; no hard-gate failure,
actionable finding or material residual concern. All 18 images were inspected at original
resolution, including the native 15 px tree gutter and absence of a custom tree overlay.
