# Implementation Instructions

## Authority and safety

- Preserve the current branch and all worktree changes. Never use `git reset`, `git clean`, stash,
  checkout discard, or another operation that drops or hides work.
- Start new issues from latest main with `git pull --ff-only origin main`. Keep an active issue on its
  branch; do not reopen merged work or close a multi-unit issue before all its listed units finish.
- `docs/13-delivery/backlog.md` is the baseline, issue order, and handoff router. Read it and the exact
  issue first. Use `rg` to locate only affected requirements, ADRs, contracts, tests, and product specs.
  `IMPLEMENTATION_STATUS.md`, live code, and user guides describe implemented behavior. Do not bulk-read
  archives or `docs/_incoming/`.
- Product language is **test data**, **selected model**, **review request**, and **solver card**. Keep
  UUIDs, hashes, Mapping Profile, Recipe/Batch, provenance, and checksums in Evidence, Advanced, or
  Administration.

## Work definition and acceptance

- A fresh task takes the first unfinished backlog unit and its dependencies. Before
  implementation, classify existing behavior as complete, partial, or missing and change only the
  missing bounded scope.
- For nontrivial work, record one realistic primary user journey: setup, actions, visible outcome,
  persistence/read-back outcome, preserved contract/state, recovery, owned scope, forbidden shortcuts,
  and exact acceptance. Keep negative and technical cases separate; use
  [`docs/14-testing/product-work-acceptance.md`](docs/14-testing/product-work-acceptance.md).
- Read the exact requirement and affected contract before domain, API, data, migration, or
  documentation. Update contracts before adapters; load visual references only for UI work.
- Run Compose, database, browser, reload, and viewport checks only when applicable; otherwise record N/A
  or deferred. Before Docker, run `make compose-preflight`, recreate canonical composition, and reject
  stale environments without deleting data.
- After failure, continue safe applicable checks while evidence remains valid. Stop only for unsafe or
  invalid evidence, record that boundary, diagnose related causes, revise observable pass conditions,
  and never replay unchanged instructions. After three failures, recheck authority, scope, journey,
  gates, and evidence.
- Stop for unresolved product decisions, missing authority, unsafe action, external blockers, or
  scope-changing ambiguity. Repeated Compose or test execution never substitutes for semantic diagnosis.
- Keep automation thin: one realistic high-value browser flow when applicable, lower-level regression
  tests for rules, and Docker preflight. Do not create a generic verification framework.

## Visual work

- Production UI uses `.agents/skills/desktop-engineering-ui`, its selected inventory/manifest entry,
  original assets, affected contracts, and `docs/01-product/visual-acceptance-matrix.md`.
- Use `frontend-ui-engineering` for React/CSS, `web-design-guidelines` for explicit UI audits, and
  `webapp-testing` for browser evidence.
- For every user-visible React/CSS change, capture the live before/after state at 1366×768,
  1440×900, 1920×1080, 2560×1440, and 3840×2160 with browser zoom fixed at 100%. Open every image at
  original resolution and also provide 100%-pixel crops of the header, navigator, table/form controls,
  and graph or native preview where applicable. A scaled contact sheet alone is not approval evidence.
- The application shell uses the full viewport. Inside it, graphs, tables, and native previews may grow
  while extra space improves comparison or interaction; navigators, property forms, and prose retain
  readable bounds. A one-sided 1920 px work island, unrelated internal void, or tiny fixed-density UI at
  2560/3840 fails, as does uniformly stretching every row, sentence, form, or plot merely to fill space.
- Only #160 and #161 may carry an already-existing global high-DPI failure forward to #184, and only
  with the before/after evidence, exact affected routes/states, no new page-specific workaround, and an
  explicit product-owner disposition. After #184 merges, no later visual task may defer this gate.
- Implement display tiers only through shared typography, control, row, spacing, pane, and plot tokens.
  Do not use route-specific 4K overrides, CSS `zoom`, blanket `transform: scale`, fabricated filler, or
  non-uniform SVG stretching. Automated viewport capture proves geometry, not physical readability;
  #184 additionally records actual Windows 4K 100%, 150%, and 200% scale, CSS viewport, and device pixel
  ratio.
- Check visibility, clipping, wrapping, exact identity/revision, interaction reachability, and layout
  bounds. Hidden text and measurements do not replace normal-surface usability. Present the original
  1920/2560/3840 comparison to the product owner and do not merge before the owner checklist and final
  visual approval pass.

## Domain invariants

- Raw bytes and released artifacts are immutable. Stable identities and immutable revisions are
  separate; runs and links pin concrete revisions, never `latest`.
- Preserve original unit text, normalized unit, and quantity semantics. Never delete outliers;
  candidate detection and adjudication are separate records.
- Every derived entity records input usage, generation activity, and responsible agents. A production
  solver card requires a Material Model IR revision. Exporters report exact, transformed, approximated,
  and unsupported mappings without silent defaults.
- Core code never imports domain plugin implementations. Organization/project authorization is enforced
  at service and database levels.

## Product and UX invariants

- Normal navigation is `Materials | Modeling | Activity`; `/materials` is home. Search-first does not
  remove Database/Profile/Table/Folder/Record navigation, Administration schema objects, exact-revision
  links, or keyboard browsing.
- Materials is one explorer/result/datasheet workspace with results dominant. Modeling keeps a compact
  curve/process explorer and dominant persistent graph; use a shallow ribbon or disclosure, never a
  third inspector column.
- Prefer flat panes, alignment, and dividers before borders, radius, background, or shadow. Avoid nested
  cards, decorative gradients, repeated eyebrow labels, and non-status badges.
- Every engineering field has a decision consequence and UI contract or moves to Advanced/Evidence.
  Recommendation, selection, saved result, review, release, and artifact are distinct states. Upstream
  changes invalidate current pointers without mutating revisions.
- Materials rows, totals, and facet counts come from one server-scoped query. Condition-aware properties
  are not universal facets. Approved static HTML/CSS and registered images are authority for their exact
  target.

## Delivery and publication

- Implement one issue or clearly bounded subset and add the specified unit, integration, regression,
  and browser tests. Run only gates required by issue acceptance, affected contracts, selected skills,
  changed behavior, or hooks; resolve hook failures.
- A unit remains incomplete until delivery tracking is synchronized. Before merge, record its PR and
  next row; after merge, record PR, merge SHA, and next unit in the issue, update parent #117 when
  applicable, and keep a multi-unit issue open until every row finishes.
- User-visible React/CSS changes update the current guide, screenshot manifest, and required live
  screenshots. An `app.tsx` navigation change also updates the navigation contract. README/user-guide
  prose follows `docs/documentation-manifest.yaml` and its restrained Korean-humanizer hook.
- Before handoff, run affected tests, `uv run cmp-check-user-guide --root .`, `make docs-impact` (or
  `uv run cmp-check-doc-impact --root . --mode worktree` when Make is unavailable), and
  `git diff --check` when applicable.
- An edit or validation authorizes no commit, push, PR, ready transition, or merge. Each requires an
  explicit owner instruction for the named repository, branch, diff, and action; failure or scope
  expansion requires renewed authority.
- Before commit, fetch `origin/main`, confirm expected base/head/diff/paths, and inspect the pending diff.
  After commit and before publication, require a clean worktree, inspect the exact commit diff, and run
  `make pre-publish` (or `uv run cmp-pre-publish --root . --trigger manual`). A failed gate blocks
  publication. After push/PR, fetch and read back remote state. Immediately after merge and before the
  final report, synchronize delivery records and verify the remote `main` merge SHA.

## Do not decide TBD domain items

Do not select or imply a production tensile standard, material family, constitutive model, optimizer
policy, solver card, virtual specimen, or validation threshold. Use bounded synthetic non-production
references until the corresponding open decision is approved.

## Forbidden shortcuts

No generic EAV for core domain data, row-per-point storage for large curves, mutable raw/released keys,
hidden conversion/resampling/smoothing/manual curve edits, direct plugin database access, in-process
production plugin loading, silent solver approximation, unreviewed golden updates, or confidential test
data in source control.

`docs/_incoming/2026-07-24-organic-ux-update/` remains temporary #162 input. Do not read it early or
delete it before #162 absorbs valid content and proves inbound links are zero.
