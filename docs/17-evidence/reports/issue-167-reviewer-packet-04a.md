# Issue #167 reviewer packet 04-A

Date: 2026-07-28

Fresh re-review only:

```text
Materials / datasheet overview / normal / 1440×900
product-owner graph-range correction 04-A.1
```

This is the one permitted fresh, read-only re-review after the sole correction writer. Do not edit
files or rely on the earlier 32/32 disposition.

## Product-owner findings and required result

The first submitted image placed the response curve against its maximum x/y range. The product owner
requested more range headroom, then clarified before re-review that the range must be derived from
the data span rather than hard-coded to display values.

The corrected reference must:

- declare actual series extrema separately from axis outputs;
- add 10% of each data span as upper padding;
- choose readable nice steps using `1, 2, 2.5, 5, 10 × 10^n`;
- use 5 target x intervals and 4 target y intervals for this plot aspect;
- preserve the physical zero origin;
- derive, not prescribe, the displayed domain and response endpoint;
- retain visible top/right headroom without extrapolating the curve;
- preserve every previously accepted datasheet region, interaction and semantic boundary.

For the registered synthetic series, independent derivation should produce:

```text
x data 0.00–0.20 → padded 0.22 → step 0.05 → domain 0.25
y data 0–850 MPa → padded 935 → step 250 → domain 1,000 MPa
endpoint in plot → approximately 598.4 / 51.6
```

These output maxima are not fixed product policy.

## Exact target and authority

Corrected target:

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
- SHA-256
  `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.measurements.json`

Approved same-viewport search authority:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- SHA-256
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`

Earlier review and correction history:

- `docs/17-evidence/reports/issue-167-reviewer-packet-04.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`
  sections 04, 04-A and 04-A.1

The corrected registered target is current authority for this review. Current production and
research comparisons from reviewer packet 04 remain comparison evidence only.

## Sole correction diff and preserved boundary

The same single `correction_terra_high` writer changed only:

- the graph SVG/data policy in
  `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`;
- graph-domain capture evidence in
  `docs/00-research/ux-service-reference/capture_materials_datasheet.py`;
- matching deterministic derivation assertions in
  `docs/00-research/ux-service-reference/validate_materials_datasheet.py`;
- the target manifest hash/lifecycle;
- the target PNG and measurement JSON.

Final target source hashes:

```text
HTML       7b9611b6398f6cbd21db52663e654c4eba60da8feea28ba9d4ec76b2e1e00de6
capture    46a053c29dbeddbb655a37b77e0ae4c897f28e4ad1af0e3e1c91d3b63d04f7
validator  1b40ca4160cf2ca43d06f49ab2073cba094af201df3837fcb226ff2e8790c9d4
CSS        3ccb42ddc80c597472d1858898add18be8d10dba0d63bfe27c92847b15b404f6
JavaScript 2bf6bb304314c7f38a9d73ecf6159be2e55336b76d60a88122372abf6b75d101
```

The CSS/JavaScript hashes equal the pre-correction values. Approved search images and production
sources are unchanged. No second writer or correction agent was used.

## Main-agent direct review and independent evidence

The main agent opened the corrected PNG at original 1440×900. The curve ends at the `0.20` grid
position and below the `1,000 MPa` ceiling; the x axis continues to `0.25`. This resolves the cramped
upper/right boundary while preserving graph size, typography and surrounding information priority.

Registered plot evidence:

```text
plot area       64/27–732/191
path endpoint   598.4/51.6
right headroom  133.6 SVG units
top headroom     24.6 SVG units
path containment true
```

The main agent ran a separate inline Python/Playwright test that did not call the capture or
validator derivation helpers. It read the declared DOM series/policy, independently recomputed both
nice domains and endpoint, and matched the serialized SVG. It also reproduced:

```text
default          264/5/1155  aria 264
navigator +8     272/5/1147  aria 272
navigator Home   200/5/1219  aria 200
navigator End    360/5/1059  aria 360
```

All states retained zero page/tree overflow and fully visible kinds. Search, tabs,
Preview/Download and Back-to-results consequences passed without console/page errors.

The complete gate set passed:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --help
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_materials_datasheet.py docs/00-research/ux-service-reference/validate_materials_datasheet.py
node --check docs/00-research/ux-service-reference/materials-datasheet.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

The reference remains `pending`; main-agent evaluation is `accepted`; product-owner approval is
absent.

## Re-review gate and required response

Use `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate
zero and complete evidence.

Independently:

1. open the corrected target and approved 1440 search image at original resolution;
2. rerun the corrected target and all three approved search validators;
3. read the DOM series extrema and policy, independently recompute padded maxima, nice steps,
   domains and endpoint without trusting stored JSON/helper results;
4. confirm changing input extrema would change the computed domain contract rather than reusing
   `0.25/1,000` as fixed policy;
5. confirm curve containment/headroom, axes, legend and accessible description;
6. exercise separator and ordinary interactions;
7. inspect scope hashes, lifecycle and preserved authority;
8. judge full-screen range comfort, curve readability, topology, data semantics, clipping and
   overflow.

Return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual data-relative scaling, headroom, graph readability, datasheet usability or
   reference-authority concern.

Do not edit files, commit, push, open a PR, write GitHub, start another agent or request
product-owner approval.

## Fresh re-review disposition

Fresh `reviewer_terra_high` read-only re-review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each;
- total: 32/32;
- hard-gate zero: none;
- actionable findings: none.

The reviewer independently matched the corrected target and all approved search hashes, passed all
four validators, and recomputed the DOM-declared data-relative domains without using stored helper
results:

```text
x 0.22 padded → 0.05 step → 0.25 domain
y 935 padded → 250 step → 1,000 domain
endpoint 598.4 / 51.6
```

It also substituted different extrema: x maximum `0.26` derived domain `0.30`, and y maximum
`950 MPa` derived domain `1,500 MPa`. This confirms that `0.25/1,000` are outputs for the registered
series rather than fixed policy.

Curve containment/headroom, axes, legend, accessible description, all four splitter states, search,
tree selection, keyboard tabs, Preview/Download and Back-to-results passed with synchronized ARIA,
zero page/tree overflow and no browser errors.

The existing non-blocking Overview-only residual remains: future tab-specific reference targets and
the production port must provide each non-Overview tab with its own reachable panel and matching
ARIA relationship.

The reference remains `pending` with product-owner approval absent. Only the registered corrected
PNG may now be resubmitted.
