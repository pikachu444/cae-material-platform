# Issue #167 reviewer packet 03

Date: 2026-07-28

Review only:

```text
Materials / search-results / normal / 1920×1080
```

This is a fresh, read-only review of the current registered reference after its sole correction.
Do not edit files or rely on the writer/main-agent scores.

## Issue acceptance

- continuous 280 px navigator / dominant result grid / 300 px selected context at default;
- Database/Profile/Table/Folder/Record browsing with readable kinds and zero tree overflow over the
  complete registered 200–360 px navigator range;
- exactly `Compare | Material / grade | Family | Description | Status` as default result columns;
- selected identity, description, Family, Status and `Open datasheet` in the context;
- no unconditional Yield, Condition, CAE Card or inferred property/condition/unit/source value;
- both separators resize actual panes with truthful ARIA on ArrowLeft/ArrowRight/Home/End;
- result width at least 720 px, selected context visible and no page/body/tree horizontal overflow
  at default or extremes;
- search, tree keyboard, row selection, in-place context and Datasheet consequences intact;
- dense flat desktop workspace, one primary command, no nested cards, clipping or visual redesign;
- shared sources, approved 1440/1366 assets/lifecycle and production sources unchanged.

The first writer result was rejected before review because navigator Home at 200 px produced 52 px
tree overflow and placed all kind labels beyond the content edge. The sole correction must solve
that behavior, not conceal it in the normal screenshot or weaken validation.

## Exact references and comparison captures

Review target:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png`
- SHA-256
  `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.measurements.json`

Approved same-state authority:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- SHA-256
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
- SHA-256
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`

Current production responsive comparison:

- `docs/user-guide/images/current/materials-search-1920x1080.png`

Structural research comparison only:

- `docs/00-research/images/gui-reference/granta-list-results.png`
- `docs/00-research/images/gui-reference/granta-datasheet-embedded.png`
- `docs/00-research/ux-reference-gallery/images/material-data-center-search-detail.png`

The three registered service-reference images are authority. Current production and external
research images are comparison evidence, not permission to add fields or redesign the target.

## Bounded implementation diff

The initial writer registered:

- `materials-search-normal-1920x1080.js`: one-time actual-width to ARIA synchronization only;
- 1920 target configuration/evidence in `capture_reference.py` and `validate_reference.py`;
- the 1920 manifest entry, PNG and measurement JSON.

The sole correction added:

- `materials-search-normal-1920x1080.css` containing only
  `.material-tree { min-width: 0; }`;
- its target-only capture/manifest/validator registration;
- tree overflow and kind-edge evidence for all seven 1920 splitter states.

Shared `materials-search-normal.html`, `reference.css`, `reference.js`, approved target sources/assets
and production React/CSS are byte-identical.

## Main-agent interaction and test evidence

Independent native Playwright results:

```text
default          280/1314/300  now 280/300  tree overflow 0  kinds 281 <= 288
navigator +8     288/1306/300  now 288/300  tree overflow 0  kinds 289 <= 296
navigator Home   200/1394/300  now 200/300  tree overflow 0  kinds 201 <= 208
navigator End    360/1234/300  now 360/300  tree overflow 0  kinds 361 <= 368
context +8       280/1306/308  now 280/308  tree overflow 0  kinds 281 <= 288
context Home     280/1354/260  now 280/260  tree overflow 0  kinds 281 <= 288
context End      280/1134/480  now 280/480  tree overflow 0  kinds 281 <= 288
```

All states: document/body overflow 0, selected context visible, actual width equals ARIA now, result
width at least 1134 px. Ctrl+K/submit, tree Home/End/Arrow/Enter, DP600 selection/context update and
DP600 Datasheet consequence passed. Console/page errors were empty.

Main-agent commands passed:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1920x1080
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
node --check docs/00-research/ux-service-reference/materials-search-normal-1366x768.js
node --check docs/00-research/ux-service-reference/materials-search-normal-1920x1080.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

## Review gate and required response

Use `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate
zero and complete image/measurement evidence.

Independently:

1. open the current 1920 and approved 1440/1366 PNGs at original resolution;
2. rerun all three validators with accepted main-agent lifecycle;
3. exercise both splitters through default, Arrow, Home and End without trusting stored JSON;
4. confirm tree overflow/kind containment in every state, especially navigator Home;
5. confirm ordinary search/tree/result selection/Datasheet behavior is not intercepted;
6. inspect target-only source registration and frozen hashes;
7. judge full-screen flow, information priority, wide-screen restraint, selected context,
   engineering condition/unit boundary, clipping and overflow.

Return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual splitter, wide-screen usability, condition/unit semantics or reference-authority
   concern.

Do not edit files, commit, push, open a PR, write to GitHub, start another agent or request
product-owner approval.

## Fresh reviewer disposition

Fresh `reviewer_terra_high` read-only review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each;
- total: 32/32;
- hard-gate zero: none;
- actionable findings: none;
- residual concerns: none.

The reviewer independently opened all three supplied PNGs at original resolution, passed the
1920/1440/1366 validators at 162/88/150 checks, exercised both splitters through default, Arrow,
Home and End, and reproduced navigator Home as 200/1394/300 with kind edges 201 inside content edge
208. Every state kept actual/ARIA widths synchronized, selected context visible and
document/body/tree overflow zero. Search, tree keyboard navigation, DP600 context update and
Datasheet consequence passed without console/page errors. Target-only CSS/JavaScript registration,
all three PNG hashes, frozen shared/approved authority, the restrained wide layout and the governed
condition/unit information boundary passed.

The reference remains `pending` with no product-owner approval. Only the registered 1920 PNG may now
be submitted for product-owner confirmation.
