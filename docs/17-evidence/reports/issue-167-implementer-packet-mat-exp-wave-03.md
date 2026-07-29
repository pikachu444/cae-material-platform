# #167 WAVE-03 MAT-EXP exceptional-state implementer packet

Date: 2026-07-29
Author: main Sol High agent
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Bounded assignment

Create the two remaining MAT-EXP approval references and their deterministic responsive/state
evidence. This is static service-reference work only. Do not edit production React/CSS, the common
manifest, the common inventory, the common #167 evidence report, GitHub, or any other family.

Approval targets:

1. `materials-search-long-1440x900`
2. `materials-search-empty-1440x900`

Dependency prerequisite:

- The MAT-EXP normal structure is already product-owner approved at all three viewports:
  - `materials-search-normal-1366x768.png`
    `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
  - `materials-search-normal-1440x900.png`
    `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`
  - `materials-search-normal-1920x1080.png`
    `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`
- Read those exact HTML/CSS/JavaScript sources, measurements and images. They are authority, not
  inspiration. Do not modify them or their bytes.

## 2. User task and product judgment

The user must be able to keep working when a scoped Material query produces many rows/long labels or
no rows. Search, Browse Tree, result count, selected context and keyboard behavior remain one
continuous explorer/result workspace.

The long state proves density and containment, not a redesigned large-data dashboard. The empty
state clears stale result selection and gives one direct recovery action without blanking or
replacing the navigator.

## 3. Preserved contracts

### React/API/state mapping

| Static region or state | Production contract that must be represented |
| --- | --- |
| search query and result header | `MaterialSearchPage` query/offset/sort URL state and `listMaterials` |
| total, rows and family counts | one server-scoped `MaterialSearchResponse`; never mixed client totals |
| Database/Profile/Table/Folder/Record tree | `MaterialsBrowseTree`, governed exact Record selection and keyboard path |
| dense result grid | `MaterialResponse.current_revision`; only Compare, Material/grade, Family, Description and Status |
| selected context | current result identity/description/family/lifecycle only |
| long rows | server page up to 50 rows, sticky header and independent result scrolling |
| empty query | `!loading && !error && !materials.length`; selected material is cleared |
| Retry/clear recovery | current query/tree context remains; retry does not invent rows |

Do not expose provider/source, card readiness, validation or condition-aware Yield because the
current scoped result response does not supply those fields consistently. Totals, rows and any
family counts must come from the same synthetic server-response fixture.

### Interaction/state

- `Ctrl/Cmd+K` focuses search.
- Enter applies the query.
- Browse/Filters/Subsets remain sibling modes in the same navigator.
- Tree Up/Down/Home/End and Enter remain operable.
- Result selection and Enter/double-click consequences stay in place.
- Compare remains local and capped at three.
- Both visible splitters update actual pane widths and ARIA on Arrow keys/Home/End at viewports where
  the pane is visible.
- The long result list scrolls independently; page/body do not scroll horizontally.
- Empty clears the stale selected row/context and offers exactly one primary recovery command:
  `Clear search`.

### Responsive structure

- Preserve the approved target-specific normal proportions and splitter behavior.
- 1366 retains the approved selected-context correction; do not silently revert it to the older
  collapsed-context rule.
- 1440 uses the approved continuous three-pane topology.
- 1920 keeps a restrained 280 px navigator and 300 px context while results dominate.
- Tree type text (`Database`, `Profile`, `Table`, `Folder`, `Record`) must remain contained at every
  splitter state, including minimum navigator width.

## 4. Required visual states

### Long approval state

- Canonical approval image: 1440×900.
- Use a deterministic synthetic non-production server page with 50 visible-result records and a
  truthful larger total (for example `1–50 of 126 matches`).
- Include deliberately long but realistic material names, grade codes and descriptions.
- Keep the selected DP780-style Record and selected context visible.
- Sticky headers, tabular counts, 12–13 px metadata and 13–14 px data remain readable.
- Long values may ellipsize only when the full value is exposed with a semantic `title`; row identity
  must never disappear.
- No nested cards, badge counts, new columns, decorative gradients or page-level overflow.

### Empty approval state

- Canonical approval image: 1440×900.
- Query shows `0 matches`, table has no stale rows, and selected context truthfully says that no
  material is selected.
- Navigator, query, scope and status context remain mounted.
- One `Clear search` recovery is visible in the result region.
- Do not show Start Modeling, Add Material, fake recommendations or marketing copy.

### Deterministic evidence-only states

Persist browser-evidence PNGs with path, viewport, dimensions and SHA-256 for all three viewports:

- long
- empty
- search refresh/loading with previous rows and selection retained
- tree lazy-loading with current results retained
- query error with previous rows/selection retained and Retry
- tree error with current query/results retained and Retry

If two evidence-only variants share an exact topology they may use one source/state controller, but
each required state/viewport snapshot must be independently named and hash-bound. Loading/error copy
must state what is retained. Do not record only in-memory screenshots.

## 5. Source and ownership

Owned paths may include only new MAT-EXP WAVE-03 family paths:

- `docs/00-research/ux-service-reference/materials-search-exceptional.html`
- `docs/00-research/ux-service-reference/materials-search-exceptional.css`
- `docs/00-research/ux-service-reference/materials-search-exceptional.js`
- `docs/00-research/ux-service-reference/capture_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`
- a family-local staging/state JSON such as
  `docs/00-research/ux-service-reference/materials-search-wave03.staging.json`
- new MAT-EXP WAVE-03 PNG/measurement/state-evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit:

- `materials-search-normal.html`, `reference.css`, `reference.js`, their viewport overrides, approved
  measurements or approved PNGs;
- `service-reference-manifest.yaml`, `service-reference-inventory.yaml` or
  `issue-167-service-reference-freeze.md`;
- any MOD-FIT path;
- any production path under `apps/web`.

Use one standalone exceptional-state source or import frozen assets read-only. Do not create a
route-specific override stack on top of the approved normal source.

## 6. Evidence schema and assertions

For each approval target record:

- id, screen/family, state and viewport;
- source paths;
- PNG path, exact dimensions and SHA-256;
- date `2026-07-29`;
- lifecycle `pending`, main-agent evaluation `pending`, product-owner approval `absent`;
- measured application/search/workspace/status regions and pane widths;
- tree/result/context containment;
- result count, rendered row count and sticky-header evidence;
- body/data/metadata computed font sizes;
- zero browser console/page errors and zero document/body horizontal overflow;
- interaction results and all splitter states;
- exact zero-count legacy-selector report for `page-stack`, `page-heading`, `content-card`,
  `module-material-card`, `hero-actions`, `eyebrow`, `status-badge`, `count-chip`.

Validator hard gates:

- frozen normal image and source hashes remain unchanged;
- long 1440 shows 50 rows, truthful total > 50, selected context and independently scrollable result
  pane;
- empty 1440 shows zero rows, zero selection, one Clear search recovery and no stale context;
- all responsive/state PNGs exist, match recorded dimensions/hashes and preserve topology;
- no result/navigator/context/page clipping or overflow;
- semantic controls, labels, visible focus and named recovery actions pass the current Web Interface
  Guidelines.

## 7. Required commands

Run each helper with `--help` before capture, then:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_search_wave03.py --all-packet-targets
uv run python docs/00-research/ux-service-reference/validate_materials_search_wave03.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-status approved
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-status approved
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-status approved
uv run ruff check docs/00-research/ux-service-reference/capture_materials_search_wave03.py docs/00-research/ux-service-reference/validate_materials_search_wave03.py
node --check docs/00-research/ux-service-reference/materials-search-exceptional.js
git diff --check
```

Open both approval PNGs and representative evidence PNGs at original resolution before returning.
Report changed paths, exact commands/results, approval-image hashes and residual risks. Do not
request product-owner approval.
