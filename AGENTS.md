# Implementation Instructions

## Current execution handoff

- **Approved product/visual baseline:** `55cfa62` (PR #156). The repository starting point is always the latest `main` obtained with `git pull --ff-only origin main`. PR #125–#165 are merged scope; do not reopen or reimplement them.
- **Product language:** User works with **test data**, a **selected model**, a **review request**, and a **solver card**. Reviewer handles requests; Administrator manages catalog structure, access, and governed operations. UUIDs, hashes, Mapping Profile, Recipe/Batch, provenance, and checksums belong in Evidence, Advanced, or Administration.
- **Order:** [#117](https://github.com/pikachu444/cae-material-platform/issues/117) is meta; [#119](https://github.com/pikachu444/cae-material-platform/issues/119) keeps automatic LLM review disabled. Then do [#157 demo](https://github.com/pikachu444/cae-material-platform/issues/157) → [#158 Fit](https://github.com/pikachu444/cae-material-platform/issues/158) → [#159 Materials](https://github.com/pikachu444/cae-material-platform/issues/159) → [#160 Governance/Activity](https://github.com/pikachu444/cae-material-platform/issues/160) → [#161 DUI-09](https://github.com/pikachu444/cae-material-platform/issues/161) → [#162 UXC-99](https://github.com/pikachu444/cae-material-platform/issues/162). For each: latest `main` → one implementer/writer → deterministic gates → fresh independent reviewer → PR/merge; at most one correction and re-review.
- **Visual authority:** `docs/00-research/ux-layout-review/modeling.html`, `docs/00-research/ux-layout-review/review.css`, and `docs/17-evidence/images/uxc-00d-responsive-design/modeling-1440x900.png`. PR #156 remains the approved product/visual baseline; do not reinterpret it into a topology redesign.
- **Incoming package:** `docs/_incoming/2026-07-24-organic-ux-update/` is temporary reference, not authority. Do not delete it before #162 absorbs the remaining content and audits inbound links to zero.

## Read first

1. `README.md`
2. `docs/02-requirements/requirements.md`
3. `docs/03-domain/canonical-domain-model.md`
4. `docs/04-provenance/revision-and-provenance.md`
5. `docs/05-architecture/system-architecture.md`
6. the task in `docs/13-delivery/backlog.md`
7. relevant plugin/IR/API/test/security documents

## Non-negotiable invariants

- Raw bytes and released artifacts are immutable.
- Stable identities and immutable revisions are separate.
- Runs reference concrete revisions, never `latest`.
- Original unit text, normalized unit, and quantity semantics are preserved.
- Outliers are never deleted; candidate and adjudication are separate records.
- Every derived entity has input usage, generation activity, and responsible agents.
- A production solver card requires a Material Model IR revision.
- Exporters must report exact/transformed/approximated/unsupported mappings.
- Core code must not import domain plugin implementations.
- Organization/project authorization is enforced at service and database levels.

## Product UX invariants

- Normal-user navigation is `Materials | Modeling | Activity`; `/materials` is the home route.
- Search-first changes entry priority only. Preserve Database/Profile/Table/Folder/Record navigation,
  Table/Attribute/Layout/Subset/Link Type administration, exact-revision links, and keyboard browsing.
- Materials uses one continuous explorer/result/datasheet workspace. Tree and filters are not
  separate feature cards, and results remain wider than optional context.
- Modeling uses a compact curve/process explorer and a dominant persistent graph. A permanent third
  inspector column is forbidden; current-step controls belong in a shallow graph-adjacent ribbon and
  advanced controls use a drawer or disclosure.
- Workspace panes use alignment and dividers before border, radius, background, or shadow. Nested
  cards, decorative gradients, repeated eyebrow labels, and non-status badges are not accepted.
- Page titles are compact; material data, table rows, curves, and engineering controls carry the
  visual emphasis. Tree and metadata text remain readable 12–13 px regular/medium, body/data 14 px.
- Full IDs, hashes, classification, change reason, Mapping Profile JSON, Recipe/Batch lifecycle,
  provenance graph, mapping report, and checksums belong in Evidence, Advanced, or Administration.
- A major workspace redesign requires a reference comparison, responsive prototype, measured region
  ratios, and explicit product-owner approval before production React/CSS implementation begins.
- Visual acceptance requires every target screen to score at least 85/100 against the structural
  reference rubric, with no topology, dominant-area, or nested-card hard-gate failure.
- Every visible engineering component or field has one canonical UI-spec entry that states its
  `purpose`, `placement`, `visible_when`, `source`, `requires`, `invalidates`, `states`, and
  `error_recovery`. A field without a user decision or workflow consequence must be redesigned,
  moved to Advanced/Evidence, or removed; it is not retained merely to look technical.
- Recommendation, engineer selection, saved result, review, release, and delivered artifact are
  distinct states. A recommendation never silently becomes the selected candidate, and an upstream
  change invalidates downstream current pointers without mutating immutable revisions.
- Materials query totals, facet counts, and rows come from the same server-side scoped query.
  Condition-aware properties are not exposed as universal facets (for example, Yield is absent for
  non-metal families).

## Do not decide TBD domain items

Do not choose or imply a production tensile standard, material family, constitutive model, optimizer policy, solver card, virtual specimen, or validation threshold. Use synthetic non-production reference plugins until the relevant open questions are resolved.

## Work by task

- Implement one backlog Task or a clearly bounded subset.
- Link requirement, ADR, and Task IDs in code/PR documentation.
- Define or update contracts before adapters.
- Add unit, integration, and regression tests listed by the Task.
- Obtain domain approval for numeric reference results, IR payload schemas, solver mappings, and golden files.
- For visual work, update the linked product policy, reference comparison, viewport evidence, and
  screenshot manifest in the same PR. Do not mark a visual Task complete before live browser review.

## Documentation enforcement

- `README.md` is a Korean project entrypoint, not an implementation journal. It must help a
  prospective Administrator, Reviewer, or User understand their work before internal engineering
  terms: state the role/task entry points, the two core user flows, a runnable quickstart,
  current-versus-approved-target status, current screen links, verification, and documentation
  links. Keep chronology in `docs/13-delivery/implementation-history.md`; do not impose a line
  count in place of useful guidance.
- Every tracked Markdown file must match exactly one `current`, `authoritative`, `historical`, or
  `reference` rule in `docs/documentation-manifest.yaml`.
- A commit that changes non-test `apps/web/**/*.tsx` or `apps/web/**/*.css` must also change all of:
  a current `docs/user-guide/*.md`, `docs/user-guide/screenshot-manifest.yaml`, and a current
  `docs/user-guide/images/current/*.png` captured from the live browser.
- A change to `apps/web/src/app.tsx` must additionally update
  `docs/user-guide/navigation-contract.yaml`. A user-visible OpenAPI workflow change must update a
  current user guide.
- Test-only, historical-evidence-only, and reference-research-only changes are exempt from visual
  screenshot impact, but never from valid links and document classification.
- Before committing visual work, run the affected live browser scenario at 1366x768 and 1440x900
  (and 1920x1080 when the layout materially expands), then run `make docs-screenshots` and
  `make docs-impact`.
- Project Codex hooks in `.codex/hooks.json` block `git commit` when required documentation evidence
  is missing. Before `git push`, `gh pr create`, `gh pr ready`, and `gh pr merge`, the automatic
  pre-publish pipeline runs deterministic documentation, diff, link, image, and manifest checks.
  It must never start an LLM reviewer. Independent code/visual review is a separately authorized,
  explicit opt-in command while GitHub issue #119 remains open. Review and trust the project hook
  with `/hooks` after cloning or whenever the hook definition changes.

## Forbidden shortcuts

- Generic EAV tables for core domain data
- Row-per-point storage for large curves
- Mutable raw or released object keys
- Hidden unit conversion, resampling, smoothing, or manual curve edits
- Direct plugin database access
- In-process loading of production plugins by the API
- Silent solver mapping defaults or approximation
- Golden snapshot updates without software and domain review
- Real confidential test data in source control

