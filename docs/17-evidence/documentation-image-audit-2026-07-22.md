# Documentation and image consistency audit

Date: `2026-07-22`

Follow-up verification: `2026-07-23` for PR #118 review corrections

Baseline: `main` at `f89cc50` after PR #112, #114 and #115 were merged

Scope: GitHub issue #116, `FR-UX-001`, `T-46`, ADR-0034 and the documentation rules in
`AGENTS.md`. Product behavior, API contracts, numeric results and domain scope are excluded.

## 1. Method and authority order

The audit used this authority order:

1. the checked-out `main` source and contracts;
2. the live Docker Compose application backed by the deterministic synthetic seed;
3. current user/admin guides and their screenshot manifest;
4. authoritative product, requirement, ADR and delivery documents;
5. historical delivery evidence and external reference images.

Repository links were resolved relative to every tracked Markdown file. Image references were also
compared with both screenshot manifests, capture-script output paths, SHA-256 hashes and recent PR
descriptions. A file was not selected for deletion merely because it was old.

## 2. Pre-cleanup inventory

| Item | Count | Finding |
| --- | ---: | --- |
| Tracked Markdown | 194 | Every file matches exactly one documentation-manifest rule. |
| Internal Markdown links/images | 417 | Two broken relative links exist in `implementation-history.md`. |
| External Markdown links | 114 | They are not treated as local artifact ownership. |
| Tracked PNG/JPG/JPEG images | 235 | 209 are product/evidence images and 26 are external reference images. |
| `docs/15-demo/images` files | 214 | 209 images and five JSON measurement files share one numbered historical directory. |
| `ux-redesign-v2` files | 40 | 36 are registered as current; the name does not identify ownership or lifecycle. |
| Current screenshot-manifest entries | 36 | T95/T98, DUI-01, DUI-02 and DUI-04 generations are mixed together. |
| SHA-256 duplicate groups | 5 | Each is a DUI-02 historical capture duplicated into `ux-redesign-v2`. |
| Repository/PR-unreferenced image candidates | 15 | Candidates are listed below and may be deleted only after the path audit is committed. |

Confirmed merge state from GitHub:

| PR | Merge commit | Actual state |
| --- | --- | --- |
| #112 / DUI-01 | `b81d53b` | merged 2026-07-22 |
| #114 / DUI-02 | `5fe6d63` | merged 2026-07-22 |
| #115 / DUI-04 | `f89cc50` | merged 2026-07-22 |

## 3. Reference relationships

| Role | Before cleanup | Required stable role |
| --- | --- | --- |
| Current product instructions | selected `docs/user-guide`/`docs/admin-guide` files | all published user/admin guides classified `current` |
| Current representative captures | `docs/15-demo/images/ux-redesign-v2` | `docs/user-guide/images/current`, generated from current `main` |
| Historical task/PR evidence | `docs/15-demo/evidence`, task-prefixed images and DUI before/after images | numbered `docs/17-evidence` tree, never used as a current-screen source |
| External product references | `docs/00-research/images` and `ux-reference-gallery/images` | remain `reference`; never application assets |
| Current capture registry | `docs/user-guide/screenshot-manifest.yaml` | current images only, with an owning capture script |
| Historical capture registry | `docs/15-demo/screenshot-archive.yaml` | move with historical evidence and retain immutable facts |

Past PR descriptions point either to a commit/branch-specific GitHub URL or to the historical evidence
path that existed in that revision. Those PR links remain historical records. Repository-local links
must be updated when the evidence directory moves.

## 4. Disposition list fixed before cleanup

### Maintain

- `README.md`, requirements, domain, provenance, architecture, ADR and current product-policy
  documents as the governing hierarchy.
- `docs/00-research` images and manifests as copyrighted external `reference` material.
- Task/PR evidence with dates, measurements, exact revisions and verification results as
  `historical`; do not overwrite its image bytes.
- `Materials | Modeling | Activity`, `/materials`, exact-revision navigation and all current product
  behavior without implementation changes.
- `docs/user-guide/screenshot-manifest.yaml` as the current capture registry, after its paths and
  generation ownership are corrected.

### Modify

- Update `CODEX_DESKTOP_ENGINEERING_UI_START.md` and the DUI backlog to record the actual merged
  status of DUI-01, DUI-02 and DUI-04 and leave DUI-03/DUI-05~09 pending.
- Resolve the duplicate numbered-directory meaning by keeping `docs/15-governance` and moving demo/
  delivery proof to `docs/17-evidence`.
- Move current representative captures out of the historical evidence tree to
  `docs/user-guide/images/current` and replace generation-labelled names such as
  `ux-redesign-v2`/`final-*` with stable screen/scenario names.
- Recapture the current representative screens from the live application at 1366x768, 1440x900 and
  1920x1080 where the layout expands; reject unfinished async states and horizontal overflow.
- Classify all published user/admin guides as `current`, remove historical screenshots from those
  guides, and use only registered current captures where a screenshot is needed.
- Fix the two broken `implementation-history.md` links.
- Extend the documentation checker to validate every tracked Markdown local link/image, exact
  manifest classification, current/archive separation, capture-script ownership, orphan-image
  reporting and duplicate hashes.
- Update `AGENTS.md`, documentation indexes, maintenance instructions, Make targets and tests to the
  new stable paths and commands.

### Archive

- Preserve all referenced task-prefixed, DUI before/after, layout-review and clean-demo evidence
  under `docs/17-evidence`.
- Preserve the historical screenshot archive with its original capture metadata.
- Preserve PR-specific duplicate image bytes when they are part of an immutable historical evidence
  set; current recaptures have independently owned stable current paths.

### Delete

The following files have no repository text/YAML/script reference, no current/archive manifest entry
and no filename reference in the latest 200 GitHub PR descriptions. They are removal candidates, not
historical evidence inputs:

- `docs/15-demo/images/historical-task-screenshots/t55m-hardening-candidates.png`
- `docs/15-demo/images/historical-task-screenshots/t59-product-access.png`
- `docs/15-demo/images/historical-task-screenshots/t89-polymer-prony-workbench.png`
- `docs/15-demo/images/ux-layout-review/card-1366x768.png`
- `docs/15-demo/images/ux-layout-review/card-1920x1080.png`
- `docs/15-demo/images/ux-layout-review/detail-1366x768.png`
- `docs/15-demo/images/ux-layout-review/detail-1440x900-mask.png`
- `docs/15-demo/images/ux-layout-review/detail-1920x1080.png`
- `docs/15-demo/images/ux-layout-review/export-1440x900-mask.png`
- `docs/15-demo/images/ux-layout-review/modeling-1366x768.png`
- `docs/15-demo/images/ux-layout-review/modeling-1920x1080.png`
- `docs/15-demo/images/ux-layout-review/reference-granta-mi-favourites-list-mask.png`
- `docs/15-demo/images/ux-layout-review/reference-material-data-center-search-detail-mask.png`
- `docs/15-demo/images/ux-layout-review/reference-material-modeler-curve-fitting-mask.png`
- `docs/15-demo/images/ux-layout-review/reference-material-modeler-hyperelastic-fitting-mask.png`

The reference and hash pass then identified 15 further redundant outputs for the same disposition:

- `docs/15-demo/images/ux-layout-review/export-1366x768.png`
- `docs/15-demo/images/ux-layout-review/export-1440x900.png`
- `docs/15-demo/images/ux-layout-review/export-1920x1080.png`
- `docs/15-demo/images/ux-layout-review/materials-1920x1080.png`
- `docs/15-demo/images/ux-redesign-v2/dui-01-activity-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/dui-01-administration-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/dui-01-browse-tree-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/dui-01-material-detail-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/dui-01-materials-search-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/dui-01-modeling-fit-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/final-materials-1366x768.png`
- `docs/15-demo/images/ux-redesign-v2/final-materials-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/final-materials-1920x1080.png`
- `docs/15-demo/images/ux-redesign-v2/material-detail-overview-1440x900.png`
- `docs/15-demo/images/ux-redesign-v2/materials-exact-record-1440x900.png`

## 5. Known pre-cleanup failures

- `docs/13-delivery/implementation-history.md` incorrectly resolves two repository-root paths below
  its own directory.
- `docs/13-delivery/desktop-engineering-ui-backlog.md` describes DUI-02 as a Draft-PR implementation
  and DUI-04 as branch-only implementation after both were merged.
- the start prompt still gates only on PR #112 and does not identify the completed merge sequence or
  next pending work.
- current and historical screenshots share `docs/15-demo`, and `docs/15-demo` collides numerically
  with `docs/15-governance`.
- the existing checker passes despite generation-mixed current captures and does not validate local
  links in authoritative/historical/reference Markdown or connect current captures to an owning
  script.

## 6. Post-cleanup verification to record

The completed change must append exact results for:

- live current-screen capture and visual inspection;
- current screenshot manifest and PNG dimension validation;
- every tracked Markdown local link/image;
- documentation classification;
- capture-script output ownership;
- orphan and duplicate image report;
- documentation-impact gate;
- web unit/build and browser journeys proving product behavior did not change.

## 7. Executed cleanup

The disposition above was applied without changing application source, API contracts, seed data or
domain behavior:

- moved historical reports, task captures, DUI evidence, the archive manifest and 12 one-off capture
  scripts from `docs/15-demo` into the numbered `docs/17-evidence` tree;
- created the stable `docs/user-guide/images/current` lifecycle and captured 20 current screens from
  the live Compose application at the required viewports;
- replaced the generation-mixed 36-entry current manifest with those 20 stable current captures and
  registered 111 retained historical captures in the separate archive;
- renamed 79 JPEG-byte historical files from a misleading `.png` suffix to `.jpg` without changing
  their bytes, then updated every owning report, archive entry and script output path;
- removed the 15 pre-audit orphan candidates above, four additional unreferenced layout-review
  exports, six redundant DUI-01 convenience copies and five history-to-history DUI-02 hash
  duplicates: 30 deletions in total, all recoverable from Git history;
- retained the canonical DUI-02 copies under `docs/17-evidence/images/desktop-engineering-ui/dui-02`
  and redirected historical references to them;
- kept nine current-to-history duplicate hash groups deliberately. They are independently owned
  lifecycle records: the current path is regenerated by the stable capture command, while the
  historical path remains immutable evidence for its merged task/PR;
- removed historical screenshots from current user/admin guides, corrected current labels against
  the live UI, repaired the two broken implementation-history links and updated the delivery status
  of merged PRs #112, #114 and #115.

The PR review follow-up tightened the evidence semantics and ownership contract:

- Activity is registered as the no-browser-session empty state; exact stage/revision/curve resume and
  review-attention remain DUI-08 pending.
- Modeling Process/Fit/Export captures are registered as ephemeral previews. In particular, Export
  is not evidence of a reviewed model commit or native-card delivery; DUI-05/06 remain pending.
- Current captures are produced in an empty sibling temporary directory. The script validates the
  exact 20-file set, PNG headers and encoded viewport dimensions before replacing the current tree;
  a failed or incomplete run leaves the previous tree untouched.
- Orphan ownership is the union of normalized repository-relative paths resolved from actual
  Markdown links, current manifest, historical archive, structured measurement/render manifests and
  capture scripts. A filename in audit prose or an unrelated same-name file grants no ownership.
- Duplicate hashes are counted by lifecycle. Only nine explicit path pairs containing exactly one
  current and one historical file are permitted; an unlisted pair, stale allowance or one-to-many
  group fails.

This preserves historical proof without allowing silent duplicate accumulation or pending-DUI
claims.

## 8. Final verification

| Check | Result |
| --- | --- |
| Live capture | 20/20 completed from `http://127.0.0.1:5173` through an empty temporary tree; exact viewport, no pending async state and no horizontal overflow |
| Visual inspection | Materials search/detail, Modeling data/fit/export and Administration inspected after capture; screens match current application structure |
| Current manifest | 20 unique current captures; pending DUI semantics, dimensions and `CURRENT_CAPTURE_OUTPUTS` ownership verified |
| Historical archive | 111 unique entries; dimensions and source-evidence paths verified |
| Historical scripts | 12 scripts; literal output files exist and stay in the historical tree |
| Documentation classification | 195 Markdown files, each matching exactly one manifest rule |
| Local Markdown links/images | 324 repository-local references resolved |
| Image inventory | 225 images; 0 suffix/byte mismatches; 0 orphans; 9 explicitly permitted one-to-one cross-lifecycle duplicate groups |
| Contract regression | `13 passed` for user-guide, capture replacement and documentation-impact contracts |
| Python regression | 794 passed, 76 PostgreSQL-dependent tests skipped because `CMP_TEST_POSTGRES_DSN` is not configured |
| Web unit regression | 42 files, 103 tests passed |
| Web build | TypeScript, Vite build and bundle-budget check passed |
| Browser regression | 3 Playwright governed-demo journeys passed |
| Change hygiene | Changed Python files pass Ruff and `git diff --check`; documentation impact reports 0 visual source changes |

The Windows audit host does not provide a `make` executable. The `docs-screenshots` and
`docs-impact` target bodies were therefore run directly with their exact `uv run` commands. No
non-test file under `apps/web` is changed by this audit.
