# Issue #167 reviewer packet 02-B

Date: 2026-07-28

Review only the product-owner-authorized visual correction for:

`Materials / search-results / normal / 1366×768`

This is a fresh, read-only review. The previous reviewer disposition for the collapsed-context image
is superseded and is not evidence for this corrected image.

## Issue acceptance

The product owner rejected the prior 1366 image because:

1. it omitted the selected-material region present in the supplied service reference and approved
   1440 reference;
2. `Database`, `Profile`, `Table`, `Folder`, and `Record` were clipped at the right edge of the
   244 px navigator.

The corrected reference must:

- show the 244 px governed navigator, dominant result grid and 280 px selected-material context
  together at 1366×768;
- keep the result grid at least 720 px and wider than the selected context;
- expose all governed tree-kind labels without pane-local horizontal overflow or edge clipping;
- keep only the governed default search columns
  `Compare | Material / grade | Family | Description | Status`;
- show the supported selected identity, description, Family, Status and `Open datasheet`;
- avoid fixed Yield, Condition or CAE Cards columns. A condition-aware property is only comparable
  when a later server-scoped response carries quantity, unit, condition and source semantics;
- reserve full attributes, curves, related data and CAE Cards for the later full Datasheet approval
  unit instead of squeezing them into the 280 px search context;
- preserve dense rows, flat divider grammar, one filled primary command, in-place selection,
  keyboard consequences, status, and zero overlap/clipping/overflow;
- leave the approved shared source, 1440 image, production React/CSS and every other approval unit
  unchanged.

## Reference authority and comparison paths

Approved same-state standard viewport:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- SHA-256:
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`

Corrected review target:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
- SHA-256:
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
- measurements:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.measurements.json`

Relevant local service references for structural judgment:

- `docs/00-research/images/gui-reference/granta-list-results.png`
- `docs/00-research/images/gui-reference/granta-datasheet-embedded.png`
- `docs/00-research/images/gui-reference/granta-datasheet-full.png`
- `docs/00-research/ux-reference-gallery/images/material-data-center-search-detail.png`

The local service references demonstrate selectable condition/unit-aware property columns, selected
record context beside search results, and a wider full Datasheet for attributes/curves. They are
comparison evidence; the registered corrected image and approved 1440 image remain the exact
platform authority.

## Bounded implementation

The one visual correction writer changed only:

- `docs/00-research/ux-service-reference/materials-search-normal-1366x768.css`;
- `docs/00-research/ux-service-reference/capture_reference.py`;
- `docs/00-research/ux-service-reference/validate_reference.py`;
- the 1366 entry in `docs/01-product/service-reference-manifest.yaml`;
- the corrected 1366 PNG and measurement JSON.

The target-only CSS is injected only for the registered 1366 capture. Shared
`materials-search-normal.html`, `reference.css`, `reference.js`, the approved 1440 PNG and production
visual sources were not changed.

## Direct measurement and interaction evidence

- workspace: 1,350×620 px;
- regions: 244 px navigator / 5 px divider / 816 px results / 5 px divider / 280 px context;
- visible splitter count: 2; visible rules: 1 px each;
- tree/result row heights: 25/36 px;
- result rows: 6;
- selected tree/result rows: 1/1;
- tree scroller horizontal overflow: 0;
- tree-kind right edges: seven at 245 px, all inside content edge 252 px;
- selected context and `Open datasheet`: present;
- page/body horizontal and vertical overflow: 0;
- nested persistent cards: 0;
- filled primary commands: 1;
- search shortcut, tree Home/End/Arrow/Enter and result Enter Datasheet consequence: passed;
- console errors and page errors: none.

Main-agent independent commands passed:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

After direct original-resolution acceptance, the main agent advanced only the 1366
`main_agent_evaluation.status` to `accepted`; reference status remains `pending` and
product-owner approval is unset. Re-run the 1366 validator with
`--expect-main-agent-status accepted`.

## Review gate and required response

Use `docs/01-product/visual-acceptance-matrix.md`. Score V-01 through V-16 from 0 to 2. Passing
requires at least 28/32, no hard-gate zero, and complete image/measurement evidence. Directly open
both target and approved 1440 images at original resolution; do not accept command success alone.

Return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual compact-usability, condition/unit semantics or reference-authority concern.

Do not edit files, commit, push, open a PR, write to GitHub, start another agent, or request
product-owner approval.

## Fresh reviewer disposition

Fresh `reviewer_terra_high` read-only review on 2026-07-28: `changes_requested`.

- V-01–V-04 and V-06–V-16: 2 each;
- V-05: 0;
- total: 30/32;
- hard-gate zero: none;
- the two product-owner visual findings are resolved;
- condition/unit semantics and target-only source authority have no additional finding.

Finding:

`docs/00-research/ux-service-reference/materials-search-normal-1366x768.css:3` fixes all three pane
widths to `244px 5px 816px 5px 280px`, while
`docs/00-research/ux-service-reference/reference.js:138`–`:156` changes only
`--navigator-width`/`--context-width`. In an independent browser exercise, navigator ArrowRight and
context ArrowLeft changed `aria-valuenow` but left the visible pane widths at `[244, 816, 280]`.
`capture_reference.py` did not exercise or assert splitter resizing.

The main agent independently reproduced the finding:

```text
initial      [244, 816, 280]  navigator aria=264  context aria=280
nav-right    [244, 816, 280]  navigator aria=272  context aria=280
context-left [244, 816, 280]  navigator aria=272  context aria=288
```

The main-agent evaluation is therefore `rejected`. Product-owner approval remains unset.
