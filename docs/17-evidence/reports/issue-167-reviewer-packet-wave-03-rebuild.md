# Issue #167 fresh review packet — WAVE-03 integrated rebuild

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Review boundary

Review the product-owner-authorized rebuild of the same six still-pending references:

- `materials-search-long-1440x900`
- `materials-search-empty-1440x900`
- `modeling-fit-normal-1366x768`
- `modeling-fit-normal-1440x900`
- `modeling-fit-normal-1920x1080`
- `modeling-fit-candidate-parameters-long-1440x900`

Do not edit any file. Open every current candidate, responsive sibling and state-evidence image at
original resolution: 18 MAT-EXP images and 16 MOD-FIT images. Score V-01–V-16 from
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero
and complete evidence.

Authoritative product-owner packet:
`docs/17-evidence/reports/issue-167-product-owner-rebuild-packet-wave-03.md`.

## Product-owner acceptance focus

The review must assess all eight findings as an integrated engineering-UI quality gate:

1. The Materials tree scrolls vertically and horizontally inside its pane without covering text.
2. Long Materials results scroll independently while headers and selected context remain mounted.
3. Long Database/Profile/Table/Folder/Record identities remain readable and reachable rather than
   being permanently ellipsized.
4. Fit keeps the graph dominant; controls form a shallow ribbon and candidate detail is an on-demand
   bounded bottom drawer.
5. Plot ticks and titles use compact, consistent engineering typography; units live in axis titles,
   both titles are present, and titles/ticks/axes do not collide.
6. The multi-curve legend sits beside the plot rather than consuming a wide row above it.
7. The responsive SVG matches its actual rendered viewport and must not use non-uniform stretching.
8. The synthetic hardening contract is true yield stress versus true plastic strain: all candidate
   laws start at zero plastic strain and positive initial yield stress, never at `(0, 0)`.

Reject a mechanically valid screen that still looks cramped, distorted or non-professional.

## Approved parents

All paths are under `docs/17-evidence/images/issue-167-service-reference/`.

Materials normal:

- `materials-search-normal-1366x768.png`
  — `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
- `materials-search-normal-1440x900.png`
  — `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`
- `materials-search-normal-1920x1080.png`
  — `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`

Modeling Data normal:

- `modeling-data-normal-1366x768.png`
  — `07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95`
- `modeling-data-normal-1440x900.png`
  — `fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f`
- `modeling-data-normal-1920x1080.png`
  — `b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5`

Modeling Process normal:

- `modeling-process-normal-1366x768.png`
  — `c537c7caf60d668a82021e50cdc0307b185faf118d5091edc41c10d9c5ef0cad`
- `modeling-process-normal-1440x900.png`
  — `57d5c9e8f9ebbf21315ca94f76eb21e11ce116526afffc717973ebb514417461`
- `modeling-process-normal-1920x1080.png`
  — `154c21e6679b999ee63ca65c10ac6e7af8a8ebdb54b69490be67460078ce53c1`

## Current candidates and complete evidence

- `materials-search-long-1440x900.png`
  — `c486fc6f6236c44083e2d8a52502be6d59729f2e8849ffcb46301ca9ef2365a2`
- `materials-search-empty-1440x900.png`
  — `9ce804bf79dcb083ccb979a15b2245847e30fae6da5849dba6a6c351706d03b0`
- MAT-EXP responsive and state paths/hashes:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.state-evidence.json`
- `modeling-fit-normal-1366x768.png`
  — `6752cb38650332daadf0273903e99319ca807e92c4d797a0ca4c314304524543`
- `modeling-fit-normal-1440x900.png`
  — `6c4ad9a9b73f956cb3986017e7afc403f19fb8dfe9450ac078ee69c937be57ac`
- `modeling-fit-normal-1920x1080.png`
  — `ee2d95c45fc8c01e0ed02eb96832bcdaa8c290341e2c211ac8209378b2bd00c5`
- `modeling-fit-candidate-parameters-long-1440x900.png`
  — `336eafcad832cf0f149d32fc7aad2c880b97b9ba0c1df000a7cc8fe4f847b180`
- MOD-FIT state paths/hashes:
  `docs/17-evidence/images/issue-167-service-reference/modeling-fit-state-evidence.json`

## Source and evidence diff

MAT-EXP:

- `docs/00-research/ux-service-reference/materials-search-exceptional.html`
- `docs/00-research/ux-service-reference/materials-search-exceptional.css`
- `docs/00-research/ux-service-reference/materials-search-exceptional.js`
- `docs/00-research/ux-service-reference/capture_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`
- the two candidates, four responsive captures, 12 state captures and their measurements/evidence

MOD-FIT:

- `docs/00-research/ux-service-reference/modeling-fit-normal.html`
- `docs/00-research/ux-service-reference/modeling-fit.css`
- `docs/00-research/ux-service-reference/modeling-fit.js`
- `docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py`
- the four candidates, 12 state captures and their measurements/evidence

Shared serial integration is limited to the six pending entries in
`docs/01-product/service-reference-manifest.yaml` and current issue evidence reports. Approved
parents, production React/CSS, other reference families and inventory denominator are unchanged.

## Deterministic and main-agent evidence

The main agent opened all 34 final images at original resolution and assessed information density,
scroll discoverability, graph dominance, typography, axis semantics and state continuity in
addition to running the deterministic gates.

```text
MAT-EXP approval/responsive/state targets                   18 / pass
MOD-FIT approval/state targets                              4 + 12 / pass
Materials tree client/scroll width                          249 / 558 px
Materials tree vertical/horizontal overflow                 190 / 309 px
tree native scrollbar / keyboard horizontal consequence    present / pass
long result rows and vertical overflow                      50 of 126 / 1127 px
result native independent scrollbar / custom overlay        present / absent
Fit x/y quantity and units                                  true plastic strain [1] /
                                                            true yield stress (MPa)
initial yield at zero plastic strain                        312 MPa / pass all curves
data-derived nice x/y ranges                                0–0.50 / 200–1400 MPa
range derivation / proportional headroom                    finite plotted span / 10%
SVG rendered size / viewBox / scale delta                   exact match / exact match / 0
plot tick/title typography                                  11 / 11.5 px
normal 1440 actual plot / Fit-workspace share               481 px / 80.2%
long drawer / actual plot                                   148 px / about 375 px
axis containment, centering and collision gates             pass
loading/empty/stale/error graph and source continuity        pass
console errors / page errors / document overflow            zero
legacy selectors / nested interactive controls              zero
Web Interface Guidelines audit                              pass
approved-parent validators and hashes                       pass / unchanged
Ruff / Node syntax / inventory / diff checks                pass
lifecycle                                                   pending / main accepted / PO absent
```

Return one verdict for the integrated six-image bundle, the V-01–V-16 scores, total score,
hard-gate result, actionable findings, and any non-blocking residual concern.

## Fresh review result

The configured fresh Terra High read-only reviewer opened all 18 MAT-EXP and 16 MOD-FIT images at
original resolution, verified the listed hashes/dimensions and reran the bounded non-mutating gates.
Verdict: `approve`; V-01–V-16 all `2`; total `32/32`; hard gates pass; no actionable finding.
The only residual observation is the expected lifecycle: all six entries remain pending with
product-owner approval absent.
