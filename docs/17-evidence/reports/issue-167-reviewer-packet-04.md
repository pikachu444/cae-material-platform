# Issue #167 reviewer packet 04

Date: 2026-07-28

Review only:

```text
Materials / datasheet overview / normal / 1440×900
```

This is a fresh, read-only review of the first registered datasheet approval unit. Do not edit
files or rely on the writer/main-agent score.

## Issue acceptance

- one continuous 264 px Browse navigator / 5 px separator / dominant 1155 px datasheet workspace;
- Database/Profile/Table/Folder/Record navigation with the selected DP780 Record visible;
- all tree-kind text fully rendered with zero navigator overflow over the complete 200–360 px
  splitter range;
- selected `DP780 synthetic demo steel`, `DP780-REF` and current `r1 · Draft` identity;
- explicit synthetic/not-validated language without a production tensile standard, validation,
  approval, release or delivery claim;
- six direct tabs:
  `Overview | Properties | Curves | CAE Cards | Related | Evidence`;
- compact typed property sheet:
  `Property | Value | Unit | Condition | Source`;
- Density, Young's modulus, Yield strength and Poisson ratio with non-empty engineering semantics;
- readable representative response with axes, legend and stated condition;
- typed application-condition summary, including explicit missing strain rate;
- exactly two synthetic native reference formats: Abaqus `.inp` and OpenRadioss `.rad`;
- visible Preview/Download entry points, exactly one filled primary command;
- single truthful keyboard-resizable separator, actual/ARIA width synchronization and no
  page/body/tree overflow at default, Arrow, Home or End;
- Back-to-results, search, tree, tabs, Preview and Download consequences intact;
- flat divider-led workspace with no nested persistent cards, decorative gradients, clipping or
  Evidence-only identifiers in the normal overview;
- all approved search assets/lifecycle and production React/CSS/API/state/test sources unchanged.

Yield is not a universal search facet or result column. It is allowed here only because this is a
selected metal Record whose typed Property Set supplies its value, normalized unit, condition,
source and applicability.

## Exact target and comparison evidence

Review target:

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
- SHA-256
  `bf2f2e20bcde69ddefc24f8701837ba8805d2f377cbfcab6be30b3f5eaf14c8a`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.measurements.json`

Approved same-viewport search authority:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- SHA-256
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`

Approved responsive search authority:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
- SHA-256
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png`
- SHA-256
  `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`

Current production comparison:

- `docs/user-guide/images/current/material-detail-1440x900.png`

Structural research comparison only:

- `docs/00-research/images/gui-reference/granta-datasheet-embedded.png`
- `docs/00-research/images/gui-reference/granta-datasheet-full.png`
- `docs/00-research/ux-reference-gallery/images/material-data-center-search-detail.png`
- `docs/00-research/ux-reference-gallery/images/material-data-center-cae-model.png`

The registered target and approved platform search images are authority. Current production and
external research images are comparison evidence, not permission to add data, fields or workflow
states.

## Bounded implementation

The configured single `implementer_luna_max` writer created:

- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`;
- `docs/00-research/ux-service-reference/materials-datasheet.css`;
- `docs/00-research/ux-service-reference/materials-datasheet.js`;
- `docs/00-research/ux-service-reference/capture_materials_datasheet.py`;
- `docs/00-research/ux-service-reference/validate_materials_datasheet.py`;
- one pending datasheet entry in `docs/01-product/service-reference-manifest.yaml`;
- the target PNG and measurement JSON.

The HTML imports the frozen `reference.css` first and the new detail stylesheet second. Search
capture/validator behavior was not changed.

During the still-active writer turn, the main agent found that the first PNG shortened `Database`
and the selected `Record` kind. The writer replaced the detail-only fixed kind track with
max-content behavior, suppressed the inherited selected-kind prefix for this navigator and added
exact-text/client-width/containment validation over all four splitter states. The target was then
recaptured. No correction agent was used.

Final target source hashes:

```text
HTML       a492b06b027cbe695964edc225b42e39346ec89013136e5e4dd6de7704200f13
CSS        3ccb42ddc80c597472d1858898add18be8d10dba0d63bfe27c92847b15b404f6
JavaScript 2bf6bb304314c7f38a9d73ecf6159be2e55336b76d60a88122372abf6b75d101
capture    b9b0864a5eace698b3ad27552a63cd436ae28883e534e6132dbb4744459d63c3
validator  6aca3191b4ff7e920d3693bbaaa084aa71398523c90dbcc6174de0c742b23ec9
```

## Main-agent direct review and tests

The main agent opened the final target and approved 1440 search PNG at original resolution. It
accepted the continuous explorer/datasheet flow, the data-first property/graph hierarchy, the
855/300 internal main/aside balance, readable 12–14 px desktop density, flat dividers, condition
semantics, bounded card delivery and absence of clipping or Evidence leakage.

Separate native Playwright reproduced:

```text
default          264/5/1155  aria 264
navigator +8     272/5/1147  aria 272
navigator Home   200/5/1219  aria 200
navigator End    360/5/1059  aria 360
```

Every state had document/body/tree horizontal overflow zero, datasheet width at least 1059 px and
exact visible kind texts `Database/Profile/Table/Folder/Folder/Record/Record`. For every kind,
`scrollWidth <= clientWidth` and its right edge remained inside the tree scroller.

The independent interaction sequence passed:

- Ctrl+K focused navigator search;
- submitting `dp780` recorded `DP780-REF` while retaining ancestors;
- Enter selected the DP780 tree Record;
- tab End/Home/ArrowRight selected Evidence/Overview/Properties and Overview restoration worked;
- OpenRadioss Preview recorded `OpenRadioss:.rad`;
- OpenRadioss Download recorded `OpenRadioss:.rad` without a real artifact/release;
- Back to results recorded query `steel` and selection `DP780-REF`;
- console/page errors were empty.

The main-agent gate set passed:

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

The main agent advanced only `main_agent_evaluation.status` to `accepted`. The reference remains
`pending`; `product_owner_approval` is absent.

## Review gate and required response

Use `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate
zero and complete image/measurement evidence.

Independently:

1. open the target, approved 1440 search and current production detail PNGs at original resolution;
2. rerun the datasheet validator with accepted lifecycle and all three approved search validators;
3. exercise the separator through default, Arrow, Home and End without trusting stored JSON;
4. verify exact tree-kind rendering and pane/page overflow in every state;
5. exercise search/tree/tab/back/Preview/Download consequences;
6. inspect semantic HTML, target-only CSS/JavaScript, manifest registration and frozen asset hashes;
7. judge full-screen task flow, data/graph priority, readable density, condition/unit/source
   semantics, card-delivery restraint, clipping, overflow and reference authority.

Return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual tree, splitter, datasheet usability, condition/property/card semantics or
   reference-authority concern.

Do not edit files, commit, push, open a PR, write to GitHub, start another agent or request
product-owner approval.

## Fresh reviewer disposition

Fresh `reviewer_terra_high` read-only review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each;
- total: 32/32;
- hard-gate zero: none;
- actionable findings: none.

The reviewer independently opened the target, approved 1440 search, current production detail,
responsive search and research images at original resolution. The target and all three frozen search
validators passed and the target SHA-256 matched
`bf2f2e20bcde69ddefc24f8701837ba8805d2f377cbfcab6be30b3f5eaf14c8a`.
Native Playwright reproduced `264/5/1155`, `272/5/1147`, `200/5/1219` and `360/5/1059`,
with synchronized ARIA, exact contained kind text and zero document/body/tree overflow. The
search/tree/tab/back/Preview/Download consequences passed without console or page errors. Source
registration, semantic structure, synthetic/Draft boundary, property/condition meaning, direct tabs,
flat layout and restrained card delivery passed.

One non-blocking residual concern is recorded for later production porting: this bounded static
Overview unit lets all non-Overview tab buttons select the one Overview panel. Every later approved
tab target and the production implementation must give each tab its own reachable panel/route and
matching ARIA relationship. This does not block the single Overview-state reference.

The reference remains `pending` with product-owner approval absent. Only the registered target PNG
may now be submitted for product-owner confirmation.
