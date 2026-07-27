# UXC-04C / UXC-04D Fit reference restoration

Date: 2026-07-27

## Authority and gates

The permanent product-owner-approved **lower proposal** in
`docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png` is the acceptance
target. `docs/00-research/images/gui-reference/modeler-fit-extrapolation.png` is the supporting
official reference. Neither asset is a current-state screenshot and neither may be deleted or
replaced by UXC-04C or its UXC-04D presentation correction.

UXC-04C passes only when all of the following are demonstrated in the live Fit screen:

- the 184–208 px Fit rail retains the real curve tree and groups the configured metal sequence as
  Sort duplicate x, True/plastic conversion, Necking boundary and active Hardening fit; modulus and
  proof operations remain in the executed sequence but are not normal-rail rows;
- the shallow band contains one line with `Step 4 · Hardening fit and extrapolation` left and the
  actual-impact note plus Remove right, then Candidate equations, Fit domain (Start/End), Selected
  blend (Primary), Primary contribution, Extrapolation (Target strain), and Graph interaction
  (Select fit range/Pick point); Secondary blend law and Output points are only in Candidate
  parameters/Advanced. The closed disclosure has its own final ribbon row above a visible divider
  and cannot overlap the graph header;
- range and point actions exist once in Graph interaction, and the separate graph header reads
  `Stress response · observed evidence and hardening candidates` with only compact Response,
  Residual, Tangent modulus and Reset view controls;
- SVG drawable area fills the available graph region responsively without distorted axes/text,
  blank bands, overlap, or a third inspector column; zoom, pan, range and point interactions remain
  available;
- decision-relevant observed/candidate/blend curves remain locally hideable in the legend, while
  curve-tree rows preserve DUI-09E checkbox → title/revision → horizontal key → eye order;
- Data, Process and Fit captures at 1366×768, 1440×900 and 1920×1080 all pass topology,
  dominant-area and nested-card hard gates, and each affected Fit score is at least 85/100.

## Implemented correction and verification status

The Fit rail retains the real test tree while presenting the configured metal operations as the four
approved user-facing steps. The active hardening row and heading both read Step 4. The heading,
ordered controls and Candidate parameters trigger occupy separate rows inside a 124 px ribbon with
a visible lower divider. Secondary blend law and Output points are inside Candidate parameters.
The graph has its own header row with only Response, Residual, Tangent modulus and Reset view.

The responsive plot measures its rendered SVG with `ResizeObserver`; every axis, series, selection
and pointer calculation uses the same effective dimensions. The Fit graph therefore occupies its
available grid cell instead of stretching a fixed 1750×420 coordinate system into a blank band.
The typed Fit-to-plot interaction bridge replaces global browser events and returns to Pan after a
range/point selection is applied.

Focused frontend regression tests pass (**2 files, 16 tests**). The production TypeScript/Vite build
and bundle gate pass; the largest lazy Modeling chunk is **119.99 kB** (limit 120 kB).

## Live viewport evidence

The rebuilt local demo produced 15 current Modeling captures. Data, Process, Fit, Export and the
session shell were all recaptured at 1366×768, 1440×900 and 1920×1080 so shared rail/plot CSS was
checked rather than assuming the Fit-only change was isolated.

| Fit viewport | Rail | Ribbon | SVG | Drawable width ratio | Structural score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 184 px | 124 px | 1145×406.97 px | 77.11% | **93/100** |
| 1440×900 | 192 px | 124 px | 1211×538.97 px | 77.74% | **94/100** |
| 1920×1080 | 208 px | 124 px | 1675×718.97 px | 82.51% | **95/100** |

Each viewport has a distinct ribbon bottom, graph header and graph region. No input, disclosure or
label intersects the graph header. The 1366 view keeps every normal control visible; the 1440 and
1920 views retain the same hierarchy while giving the graph additional height. Data and Process
retain the 184–208 px rail and responsive graph after the shared sizing change.

Current evidence:

- `docs/user-guide/images/current/modeling-fit-1366x768.png`
- `docs/user-guide/images/current/modeling-fit-1440x900.png`
- `docs/user-guide/images/current/modeling-fit-1920x1080.png`
- `docs/user-guide/images/current/modeling-data-*.png`
- `docs/user-guide/images/current/modeling-process-*.png`

The permanent approved comparison remains
`docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`; it is not replaced by
the current screenshots. UXC-04B's former Fit 98/100 score remains withdrawn.
