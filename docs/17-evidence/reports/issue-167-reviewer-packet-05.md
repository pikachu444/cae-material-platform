# Issue #167 reviewer packet 05

Date: 2026-07-28

Fresh read-only review:

```text
Materials / datasheet overview / normal / 1366×768
target id: materials-datasheet-overview-normal-1366x768
```

Do not edit files or rely on the writer/correction/main-agent disposition. This packet contains only
the bounded acceptance contract, registered authority, implementation boundary and reproducible
evidence needed for an independent review.

## Issue acceptance

This responsive approval unit must faithfully preserve the approved 1440 datasheet while keeping
the compact engineering workspace readable at 1366×768:

- one continuous Browse navigator/divider/datasheet workspace;
- readable typed tree kinds and selected DP780 Record;
- six direct datasheet tabs;
- four governed property rows with `Property | Value | Unit | Condition | Source`;
- dominant representative response with its application condition;
- restrained 280 px CAE delivery region with two native formats and Preview/Download;
- approved font sizes, flat divider-led topology and no permanent third inspector;
- graph domain derived from the data span with proportional headroom, not fixed display maxima;
- truthful keyboard splitter, minimum 720 px inner main-data region, no clipping or overflow;
- all normal-state content and actions visible in the first viewport.

Normal overview must not expose technical IDs/hashes/provenance/mapping details, a Yield facet,
solver-card result columns, or inferred universal condition fields.

## Exact target and approved authority

Candidate:

- [materials-datasheet-overview-normal-1366x768.png](../images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png)
- SHA-256
  `362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.measurements.json`

Approved structural parent:

- [materials-datasheet-overview-normal-1440x900.png](../images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png)
- SHA-256
  `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`

Approved compact Materials continuity:

- [materials-search-normal-1366x768.png](../images/issue-167-service-reference/materials-search-normal-1366x768.png)
- SHA-256
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`

Manifest:

- `docs/01-product/service-reference-manifest.yaml`
- candidate must be `pending`, main-agent evaluation `accepted`, product-owner approval `absent`;
- approved parent and search reference must retain recorded product-owner approval.

Evidence and comparison history:

- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`
  sections `Implementer packet 05`, `Main-agent implementation inspection 05 and correction packet
  05-A`, and `Main-agent evaluation 05-A`;
- current production comparison:
  `docs/user-guide/images/current/material-detail-1440x900.png`.

Only the registered static target is visual authority for this review. Current production is
comparison evidence, not a reason to redesign the approved target.

## Implementation and sole-correction boundary

The single configured `implementer_luna_max` added:

- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1366x768.css`;
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1366x768.js`;
- 1366 target support in the standalone datasheet capture/validator;
- one pending manifest entry and one PNG/measurement pair.

The only configured `correction_terra_high` writer changed only:

- `docs/00-research/ux-service-reference/capture_materials_datasheet.py`;
- `docs/00-research/ux-service-reference/validate_materials_datasheet.py`;
- the regenerated 1366 measurements JSON.

The correction strengthened per-state main/aside/plot, property-cell and first-viewport evidence.
It did not change the PNG or any visual source.

Final source hashes:

```text
shared HTML       7b9611b6398f6cbd21db52663e654c4eba60da8feea28ba9d4ec76b2e1e00de6
base CSS          0f09dae7b9350e73613d21b3c2694e609b71b9486ecfd3c8546fcd691758b589
detail CSS        3ccb42ddc80c597472d1858898add18be8d10dba0d63bfe27c92847b15b404f6
shared JavaScript 2bf6bb304314c7f38a9d73ecf6159be2e55336b76d60a88122372abf6b75d101
1366 CSS          70667ba510b7ad973ce812ad9c403859bd9e056341dee60aab9ef1ebe60ed438
1366 JavaScript   b08ada1fc8d08514c9237e194e736347d9dbfff4c23b01b832d521058f0fbbf9
capture           596f37b3471ee5b68ffe560b4bf9f31244186c20e2a294e92bc03f8745e21c17
validator         5c8f639f4c0d3e33470af7f3288c59ae14e8951f217a25ca8a7cc5d41ca5ae2a
measurements      94803fbab596ab6a1ec53f29de743c5f93317101d30ce816c4ab6e6bfeada076
```

Production React/CSS, shared approved sources and every approved image must be unchanged.

## Direct reproducible evidence

Registered geometry:

```text
viewport/status boundary  1366×768 / y=744
default                   nav/divider/datasheet 244/5/1101
                          main/aside/plot        821/280/797
ArrowRight                252/5/1093            813/280/789
Home                      200/5/1145            865/280/841
End                       345/5/1000            720/280/696
ARIA min/max              200/345, now equals visible navigator
```

The 345 maximum must derive from
`min(360, floor(1350 workspace - 5 divider - 280 aside - 720 main))`, not from a layout override
that lets the visible width disagree with ARIA.

Each state records 5 header and 20 body cells. All 25 cells fit their client widths and property
table boundaries, table/container overflow is zero, document/body/tree overflow is zero, and typed
tree kinds remain inside their content edge.

The first viewport records rendered boxes above the status bar for one selected DP780 Record, six
tabs, five headers, four rows, one graph, condition and delivery regions, two formats, two Preview
and two Download controls.

Graph contract:

```text
series extrema       x 0.00–0.20 / y 0–850 MPa
upper padding        10% of each data span
target intervals     x 5 / y 4
nice factors         1 / 2 / 2.5 / 5 / 10 × 10^n
derived domains      x 0.25 / y 1,000 MPa
response endpoint    approximately 598.4 / 51.6
headroom             133.6 right / 24.6 top SVG units
```

Main-agent independent native Playwright reproduced all geometry, containment and data derivation
without importing project helper functions. Ctrl+K search, DP780 search consequence,
OpenRadioss Preview/Download and browser error checks passed.

Registered gates passed:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --target materials-datasheet-overview-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_materials_datasheet.py docs/00-research/ux-service-reference/validate_materials_datasheet.py
node --check docs/00-research/ux-service-reference/materials-datasheet.js
node --check docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1366x768.js
uv run cmp-check-user-guide
uv run cmp-check-doc-impact
git diff --check
```

## Independent review gate

Use `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate
zero and complete evidence.

Independently:

1. open the candidate, approved 1440 parent and approved 1366 search image at original resolution;
2. verify registered hashes and lifecycle, then rerun the candidate, parent and all search
   validators;
3. load the shared HTML with the target override exactly as capture does and exercise default,
   ArrowRight, Home and End;
4. independently measure navigator/divider/datasheet/main/aside/plot and ARIA at each state;
5. independently inspect all property-cell, tree-kind, page/table and first-viewport containment;
6. read DOM series/policy and recompute padded maxima, nice steps, domains and endpoint without
   trusting measurements/helper outputs; vary input extrema to ensure the policy is data-relative;
7. exercise search, tree, tabs, Back-to-results, Preview and Download, and inspect browser errors;
8. judge full-screen parity, font and tree readability, property/graph dominance, graph range
   comfort, condition/delivery continuity, clipping, overflow and reference-authority boundaries;
9. inspect scope so production/shared/approved files are not altered.

Return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual compact readability, splitter, property containment, graph scaling, first-viewport,
   interaction or reference-authority concern.

Do not edit files, commit, push, modify GitHub, start another agent or request product-owner
approval.

## Fresh review disposition

Fresh configured `reviewer_terra_high` read-only review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each;
- total: 32/32;
- hard-gate zero: none;
- actionable findings: none;
- residual concerns: none.

The reviewer independently matched the candidate, approved parent and approved compact-search
hashes and confirmed lifecycle `pending / accepted / absent`. It reran all registered gates and used
a new native Playwright sequence without project helper results.

It reproduced:

```text
default       244/5/1101   main/aside/plot 821/280/797
ArrowRight    252/5/1093   main/aside/plot 813/280/789
Home          200/5/1145   main/aside/plot 865/280/841
End           345/5/1000   main/aside/plot 720/280/696
```

ARIA remained truthful, every property cell and tree kind was contained, all overflow values were
zero, and all required normal-state elements stayed above the y=744 status boundary. Independent
graph derivation reproduced `0.25 / 1,000` and endpoint `598.4/51.6`; varying input extrema
confirmed data-relative behavior. Search, tree, tabs, Back-to-results and OpenRadioss
Preview/Download passed without browser errors.

Full-screen review found preserved approved topology, readable tree/data text, property and graph
dominance, flat dividers and restrained 280 px delivery. No nested persistent cards, technical
provenance leakage, Yield facet or legacy route override was found. Only the registered candidate
image may now be submitted for product-owner approval.
