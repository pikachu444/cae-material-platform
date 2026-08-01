# Implementation Instructions

## Authority and current work

- Preserve the current branch and every existing worktree change. Never use `git reset`, `git clean`,
  stash, checkout-based discard, or another operation that drops or hides existing work.
- When a new issue starts, use the latest `main` from `git pull --ff-only origin main`. During an
  active issue, continue on its branch and do not reopen work already merged to `main`.
- `docs/13-delivery/backlog.md` is the single current baseline, issue-order and handoff router.
  `IMPLEMENTATION_STATUS.md`, live code and current user guides describe implemented behavior.
- Read this file and the exact GitHub issue first. Use `rg` to locate only the affected requirement,
  ADR, API, state, test and product-spec sections. Do not bulk-read large specs, manifests, backlog
  archives, or `docs/_incoming/`.
- `.codex/config.toml` and `.codex/agents/*.toml` are the sole authority for agent models, reasoning
  levels and role instructions. Verify that the configured role actually loaded. If it is unavailable,
  report the exact error and never silently substitute or redefine a model in a prompt.
- Product language is **test data**, **selected model**, **review request**, and **solver card**.
  UUIDs, hashes, Mapping Profile, Recipe/Batch, provenance and checksums belong in Evidence,
  Advanced or Administration.

## Task routing

- **Current order:** open `docs/13-delivery/backlog.md`, take its first unfinished issue, and finish it
  before the next. Start each issue in a fresh Codex task so chat history is not a dependency.
- **Visual or production UI work:** use `.agents/skills/desktop-engineering-ui`. It routes to the exact
  approved family in `docs/01-product/service-reference-inventory.yaml`, the selected entries in
  `docs/01-product/service-reference-manifest.yaml`, the original assets, affected UI contracts and
  `docs/01-product/visual-acceptance-matrix.md`. Use `frontend-ui-engineering` only for production
  React/CSS, `web-design-guidelines` for an explicit UI/accessibility audit, and `webapp-testing` for
  live interaction, capture or browser evidence.
- **Domain, API, data or migration work:** read the exact requirement/ADR and affected contract before
  implementation. Do not load visual references unless user-visible UI changes.
- **Documentation work:** follow `docs/documentation-manifest.yaml` and the project hooks. Current
  README or user-guide prose changes require the restrained `korean-humanizer` pass prescribed there.
- **Publish work:** trust the project commit/publish hooks, run the requested deterministic gates, and
  never start automatic LLM review while GitHub issue #119 remains open.

## Agent workflow

- The active `/root` primary agent owns requirement interpretation, product/UX judgment, packets,
  integration and the final internal gate. It is not a separate subagent.
- Before calling a writer, `/root` inspects the exact issue, relevant contracts and approved assets,
  then persists one bounded implementation packet in the issue or current task evidence. The packet
  names the user outcome, exact sources, preserved behavior/data/states, component or contract mapping,
  forbidden shortcuts, captures and tests. The writer does not reinterpret it.
- Use one configured writer. Do not run concurrent writers. Use the configured correction role for the
  first bounded correction after a failed deterministic, main-agent or reviewer gate. If fresh
  re-review still fails, stop with exact findings. A second bounded correction is allowed only after
  explicit product-owner authorization; a third correction is forbidden.
- After deterministic gates, `/root` prepares a bounded packet for the configured fresh read-only
  reviewer. It checks contracts, evidence, accessibility and qualitative full-screen usability.
  Reviewer approval does not replace `/root` judgment or product-owner approval.
- Commit, push, PR and merge are separate operations. Do not perform them before the required user or
  product-owner confirmation.

## Non-negotiable domain invariants

- Raw bytes and released artifacts are immutable.
- Stable identities and immutable revisions are separate; runs and links pin concrete revisions,
  never `latest`.
- Preserve original unit text, normalized unit and quantity semantics.
- Never delete outliers; candidate detection and adjudication are separate records.
- Every derived entity records input usage, generation activity and responsible agents.
- A production solver card requires a Material Model IR revision.
- Exporters report exact, transformed, approximated and unsupported mappings without silent defaults.
- Core code never imports domain plugin implementations.
- Organization/project authorization is enforced at service and database levels.

## Product and UX invariants

- Normal-user navigation is `Materials | Modeling | Activity`; `/materials` is the home route.
  Search-first does not remove Database/Profile/Table/Folder/Record navigation, Administration schema
  objects, exact-revision links or keyboard browsing.
- Materials is one continuous explorer/result/datasheet workspace. Results remain wider than optional
  context. Modeling keeps a compact curve/process explorer and dominant persistent graph; current-step
  controls use a shallow ribbon or disclosure, never a permanent third inspector column.
- Use flat panes, alignment and dividers before borders, radius, background or shadow. Avoid nested
  cards, decorative gradients, repeated eyebrow labels and non-status badges.
- Every visible engineering field has a user decision or workflow consequence and a canonical UI-spec
  contract. Otherwise remove it or move it to Advanced/Evidence.
- Recommendation, engineer selection, saved result, review, release and delivered artifact are
  distinct states. Upstream changes invalidate downstream current pointers without mutating revisions.
- Materials rows, totals and facet counts come from one server-scoped query. Condition-aware properties
  are not universal facets.
- Approved static HTML/CSS and registered images are implementation authority for their exact target.
  The mandatory qualitative checklist is a hard gate: numeric scores and automated measurements cannot
  override a qualitative failure, and the product owner gives final visual approval.

## Do not decide TBD domain items

Do not select or imply a production tensile standard, material family, constitutive model, optimizer
policy, solver card, virtual specimen or validation threshold. Use bounded synthetic non-production
references until the corresponding open decision is approved.

## Delivery and verification

- Implement one issue or clearly bounded subset. Link requirement, ADR and task IDs where the project
  records them. Define or update contracts before adapters and add the specified unit, integration,
  regression and browser tests.
- A user-visible React/CSS change must update the current guide, screenshot manifest and live browser
  screenshots required by the documentation contract. An `app.tsx` navigation change also updates the
  navigation contract. Run affected browser scenarios at required viewports before commit.
- Formatting and mechanical documentation rules belong in hooks, linters and tests rather than prose.
  Resolve hook failures; do not bypass them.
- Before handoff, run affected tests plus `uv run cmp-check-user-guide --root .`, `make docs-impact`
  and `git diff --check` when applicable. Report results and remaining risk.
- `docs/_incoming/2026-07-24-organic-ux-update/` remains temporary #162 input. Do not read it early or
  delete it before #162 absorbs valid content and proves inbound links are zero.

## Forbidden shortcuts

No generic EAV for core domain data, row-per-point storage for large curves, mutable raw/released keys,
hidden conversion/resampling/smoothing/manual curve edits, direct plugin database access, in-process
production plugin loading, silent solver approximation, unreviewed golden updates, or confidential
test data in source control.
