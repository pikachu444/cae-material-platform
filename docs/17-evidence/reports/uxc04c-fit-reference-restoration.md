# UXC-04C Fit reference restoration

Date: 2026-07-27

## Authority and gates

The permanent product-owner-approved **lower proposal** in
`docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png` is the acceptance
target. `docs/00-research/images/gui-reference/modeler-fit-extrapolation.png` is the supporting
official reference. Neither asset is a current-state screenshot and neither may be deleted or
replaced by UXC-04C.

UXC-04C passes only when all of the following are demonstrated in the live Fit screen:

- the 184–208 px Fit rail retains the real curve tree and complete configured process plus fit-step
  sequence, with the active hardening-fit step visible; a `Fit candidates` substitute is rejected;
- the shallow band contains `Step N · <actual fit method>`, Remove, the actual-impact note, and the
  ordered groups Candidate equations, Fit domain, Selected blend, Primary contribution,
  Extrapolation, and Graph interaction; Output points is only in Candidate parameters/Advanced;
- range and point actions exist once in Graph interaction, and the graph header reads `Stress
  response · observed evidence and hardening candidates` with compact Response, Residual, Tangent
  modulus and Reset view controls;
- SVG drawable area fills the available graph region responsively without distorted axes/text,
  blank bands, overlap, or a third inspector column; zoom, pan, range and point interactions remain
  available;
- decision-relevant observed/candidate/blend curves remain locally hideable in the legend, while
  curve-tree rows preserve DUI-09E checkbox → title/revision → horizontal key → eye order;
- Data, Process and Fit captures at 1366×768, 1440×900 and 1920×1080 all pass topology,
  dominant-area and nested-card hard gates, and each affected Fit score is at least 85/100.

## Implemented correction and verification status

The Fit rail now retains the real test tree and configured step sequence; the active hardening step
has the shallow `Step N · method` heading. Metal controls are loaded as a small on-demand Fit module
and are grouped in the approved order. Output points moved into the closed Candidate parameters
disclosure. Graph range/point controls are exposed only from the Graph interaction group; the plot
keeps its response/residual/tangent controls, Reset view and locally hideable decision-curve legend.

The responsive plot measures its rendered SVG with `ResizeObserver`; every axis, series, selection
and pointer calculation uses the same effective dimensions. The Fit graph therefore occupies its
available grid cell instead of stretching a fixed 1750×420 coordinate system into a blank band.
The typed Fit-to-plot interaction bridge replaces global browser events and returns to Pan after a
range/point selection is applied.

Focused frontend regression tests pass (**2 files, 16 tests**). The production TypeScript/Vite build
and bundle gate pass; the largest lazy Modeling chunk is **118.76 kB** (limit 120 kB).

## Live viewport evidence

The rebuilt local demo produced 15 current Modeling captures. Data, Process, Fit, Export and the
session shell were all recaptured at 1366×768, 1440×900 and 1920×1080 so shared rail/plot CSS was
checked rather than assuming the Fit-only change was isolated.

| Fit viewport | Rail | Ribbon | SVG | Drawable width ratio | Structural score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 184 px | 104 px | 1145×426.97 px | 77.11% | **93/100** |
| 1440×900 | 192 px | 104 px | 1211×558.97 px | 77.74% | **94/100** |
| 1920×1080 | 208 px | 104 px | 1675×738.97 px | 82.51% | **95/100** |

Each viewport passes the topology, dominant-area and nested-card hard gates. The 1366 view keeps
every labelled control visible without overlap; the 1440 and 1920 views retain the same hierarchy
while giving the graph the additional height. Data and Process retain the 184–208 px rail and
responsive graph after the shared sizing change.

Current evidence:

- `docs/user-guide/images/current/modeling-fit-1366x768.png`
- `docs/user-guide/images/current/modeling-fit-1440x900.png`
- `docs/user-guide/images/current/modeling-fit-1920x1080.png`
- `docs/user-guide/images/current/modeling-data-*.png`
- `docs/user-guide/images/current/modeling-process-*.png`

The permanent approved comparison remains
`docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`; it is not replaced by
the current screenshots. UXC-04B's former Fit 98/100 score remains withdrawn.
