# Issue #167 reviewer packet 02-C

Date: 2026-07-28

Review only the product-owner-authorized V-05 correction for:

`Materials / search-results / normal / 1366×768`

This is a fresh, read-only review. Do not reuse the earlier collapsed-context approval or the 02-B
`changes_requested` score. Re-evaluate the current registered sources, interaction evidence and exact
image.

## Issue acceptance

The current approval unit must satisfy all of the following:

- 244 px governed navigator, dominant result grid and 280 px selected-material context visible
  together at the default 1366×768 state;
- all `Database`, `Profile`, `Table`, `Folder`, and `Record` tree kinds fully visible, with zero
  pane-local horizontal overflow;
- supported default result columns only:
  `Compare | Material / grade | Family | Description | Status`;
- selected identity, description, Family, Status and `Open datasheet` in the context;
- no unconditional Yield, Condition or CAE Cards search column and no inferred engineering value;
- both visible separators resize actual panes on ArrowLeft/ArrowRight/Home/End;
- actual pane width and `aria-valuenow` remain equal, with truthful dynamic maxima;
- result width never drops below 720 px and page/tree overflow remains zero at defaults and extremes;
- ordinary search, tree and result keyboard consequences remain intact;
- dense rows, flat dividers, one filled primary command, no nested cards or clipping;
- approved shared sources, 1440 image and production visual sources remain unchanged.

The prior 02-B defect was exact: fixed target grid columns ignored the variables changed by the
shared splitter handler, so ARIA changed while visible pane widths did not. The correction must solve
the behavior, not merely change validation or hide the splitters.

## Exact reference and comparison paths

Corrected review target:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
- SHA-256:
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
- measurements:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.measurements.json`

Approved same-state 1440 authority:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- SHA-256:
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`

Relevant local structural comparison:

- `docs/00-research/images/gui-reference/granta-list-results.png`
- `docs/00-research/images/gui-reference/granta-datasheet-embedded.png`
- `docs/00-research/images/gui-reference/granta-datasheet-full.png`
- `docs/00-research/ux-reference-gallery/images/material-data-center-search-detail.png`

The registered corrected image and approved 1440 image are exact platform authority. Granta/Altair
images are comparison evidence for selectable engineering properties, selected-record context and a
wider full Datasheet.

## Bounded implementation

The one correction writer changed only:

- `docs/00-research/ux-service-reference/materials-search-normal-1366x768.css`;
- new `docs/00-research/ux-service-reference/materials-search-normal-1366x768.js`;
- `docs/00-research/ux-service-reference/capture_reference.py`;
- `docs/00-research/ux-service-reference/validate_reference.py`;
- the 1366 entry in `docs/01-product/service-reference-manifest.yaml`;
- the 1366 PNG and measurement JSON.

The target CSS now uses `--navigator-width` and `--context-width` with a `minmax(720px, 1fr)` result
column. The registered target JavaScript is injected only for the 1366 capture after the target CSS.
Its document capture-phase handler intercepts only splitter
ArrowLeft/ArrowRight/Home/End, prevents the inherited target listener from creating conflicting
state, computes dynamic maxima from the 1,350 px workspace and 720 px result minimum, and writes
pane variables and ARIA together.

Shared `materials-search-normal.html`, `reference.css`, `reference.js`, approved 1440 image/
measurements and production sources are byte-identical.

## Independent main-agent evidence

The main agent independently reran the registered capture, validators and a separate native
Playwright sequence:

```text
default        widths 244/816/280  nav now/max 244/340  context now/max 280/376
navigator +8   widths 252/808/280  nav now/max 252/340
navigator Home widths 200/860/280  nav now/max 200/340
navigator End  widths 340/720/280  nav now/max 340/340
context +8     widths 244/808/288  context now/max 288/376
context Home   widths 244/836/260  context now/max 260/376
context End    widths 244/720/376  context now/max 376/376
```

Every state had document/body horizontal overflow `[0, 0]`, visible selected context, actual pane
width equal to `aria-valuenow`, and result width at least 720 px.

Other registered evidence:

- two 5 px splitter hit areas and two 1 px visible rules;
- tree horizontal overflow 0; all tree-kind right edges 245 px inside content edge 252 px;
- six 36 px result rows and seven 25 px tree rows;
- one selected tree Record and one selected result;
- one filled primary command; no nested persistent cards;
- search shortcut, tree Home/End/Arrow/Enter, result Enter Datasheet consequence: passed;
- selected summary and `Open datasheet`: present;
- console/page errors: none.

Main-agent commands passed:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
node --check docs/00-research/ux-service-reference/materials-search-normal-1366x768.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

The main agent then advanced only the 1366 main-agent evaluation to `accepted`. Reference status
remains `pending`; product-owner approval is unset. Re-run the 1366 validator with
`--expect-main-agent-status accepted`.

## Review gate and required response

Use `docs/01-product/visual-acceptance-matrix.md`. Score V-01 through V-16 from 0 to 2. Passing
requires at least 28/32, no hard-gate zero and complete image/measurement evidence.

Required independent work:

1. open the current 1366 and approved 1440 PNGs at original resolution;
2. rerun both registered validators;
3. independently exercise default, arrow, Home and End geometry for both splitters rather than
   trusting stored JSON;
4. confirm unrelated search/tree/result keyboard behavior is not intercepted;
5. inspect target-only source registration and frozen shared/1440 hashes;
6. judge full-screen task flow, information priority, tree label readability, selected context,
   engineering condition/unit boundary, clipping and overflow.

Return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual splitter, compact-usability, condition/unit semantics or reference-authority concern.

Do not edit files, commit, push, open a PR, write to GitHub, start another agent, or request
product-owner approval.

## Fresh reviewer disposition

Fresh `reviewer_terra_high` read-only review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each;
- total: 32/32;
- hard-gate zero: none;
- actionable findings: none.

The reviewer independently:

- reran the 1366 148-check and frozen 1440 88-check validators and confirmed both PNG hashes;
- opened the 1366 and approved 1440 PNGs at original resolution;
- exercised both splitters through default, Arrow, Home and End states;
- confirmed actual pane width, `aria-valuenow` and dynamic `aria-valuemax` synchronization;
- confirmed results remained at least 720 px and document/body/tree horizontal overflow remained
  zero in every state;
- confirmed Ctrl+K search, tree Home/End/Arrow/Enter, result Enter Datasheet consequence and
  in-place DP600 context update;
- confirmed explicit target-only CSS/JavaScript registration and unchanged shared/1440 authority;
- found no residual splitter, compact-usability, condition/unit semantics or source-authority
  concern.

The only remaining lifecycle item is product-owner approval. Reference status is correctly
`pending`, and no product-owner approval is recorded.

## Product-owner approval

The product owner approved the submitted correction 02-C image in conversation on 2026-07-28.
The registered 1366 reference lifecycle is now `approved`.
