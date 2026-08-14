# Frontend Implementation Instructions

These instructions apply to all work under `apps/web` and supplement the repository root `AGENTS.md`.
They do not replace product, domain, API, testing, visual-evidence, or publication authority.

## Authority and routing

For nontrivial frontend work, read only the relevant parts in this order:

1. the exact issue and approved backlog/program unit;
2. root `AGENTS.md` and this file;
3. `docs/01-product/frontend-ui-principles.md`;
4. `docs/05-architecture/frontend-architecture.md`;
5. the exact route/user-flow/component contract;
6. applicable `docs/01-product/visual-acceptance-matrix.md` gates and registered references;
7. `.agents/skills/material-platform-frontend-architecture/SKILL.md`;
8. `frontend-ui-engineering`, `desktop-engineering-ui`, and `webapp-testing` as applicable.

Issue #249 is a cross-cutting program. Its documentation unit does not authorize production React/CSS
changes, and its later units require a bounded issue and explicit owner priority. It does not silently
reorder unrelated domain backlog work.

## Primary journeys

Every frontend change identifies which primary journey it preserves or improves:

1. `Materials search/browse -> exact applicability/evidence/card -> download or Start Modeling`;
2. `exact Material/State/Test Data -> Data -> Process -> Fit -> explicit saved model -> Export ->
   solver card -> Materials read-back/download`.

Preserve exact identity/revision handoff, Materials search/tree/selection continuity, Modeling session and
stage continuity, graph context, invalidation, restore, retry, and recovery. Never replace missing current
context with `latest`, the first list item, another session output, or fabricated fallback data.

## Required preflight

Before a nontrivial React/CSS change:

- classify it as behavior, structural, semantic visual, defect, primitive, or shell/layout work;
- name the owned feature and current owner files;
- list preserved API/domain/URL/revision/state/recovery contracts;
- inspect affected tests and registered screenshots;
- run the project-local frontend architecture skill;
- state whether a registered hotspot gains responsibility;
- separate structural movement from broad visual movement unless an owner-approved reason makes
  separation impossible.

## Dependency and ownership

- The target direction is `app -> features -> shared`.
- Shared modules never import a feature or app module.
- A feature does not deep-import another feature's internals.
- Cross-feature use goes through a public feature entry point or app-level orchestration.
- Route/page modules compose features and shell regions; they do not own domain calculations or multiple
  independent async workflows.
- Feature API, model, controller, and UI code stay feature-owned.
- Compatibility code names its removal issue and exit condition.

## Registered debt hotspots

Do not add a new feature responsibility to these files without an issue-owned extraction plan or approved
exception:

- `src/common-processing-workbench.tsx`;
- `src/material-library.tsx`;
- `src/app.tsx`;
- `src/api.ts`;
- `src/types.ts`;
- `src/styles.css`;
- `src/design/layout.css`.

Line count is a review trigger, not a quality score. At roughly 400 component lines, list responsibilities
before expansion. At roughly 600 lines, reject a new responsibility without an extraction plan. A file
owning three or more of routing, API access, domain transformation, state machine, persistence, and
rendering requires architecture review before expansion.

## State and API

- Preserve URL and server state as sources of truth.
- Do not create a second client source of truth for convenience.
- Use reducer/controller boundaries for named transitions, invalidation, restore, retry, and recovery.
- Move pure defaults, registries, and transformations out of render components.
- Keep loading, empty, blocked, stale, error, and recovery paths explicit.
- Do not add a global state or server-state dependency without a separate approved decision.
- Migrate `api.ts` and `types.ts` through feature-owned modules plus bounded compatibility re-exports;
  do not perform an unbounded repository-wide rewrite.

## CSS ownership

- Tokens, density, typography roles, primitives, shell, and generic layout belong to the shared design layer.
- Feature-specific arrangement and responsive composition belong to the feature.
- Do not add a new feature selector to `src/styles.css` or `src/design/layout.css`.
- Do not add raw colors, arbitrary font weights, route-specific 4K media queries, CSS `zoom`, blanket scale
  transforms, or fabricated filler.
- A global selector change names every affected route and runs the full applicable visual gate.
- `!important`, deep descendant selectors, and `:has` require an explicit ownership and removal rationale.

## Semantic UI

- Build a Neutral Engineering Workbench, not a generic card dashboard.
- Data, current selection/revision, state, and the next valid action dominate.
- Ordinary headings, labels, values, counts, and method versions use neutral roles.
- Accent is limited to selection, focus, primary action, and links.
- Status colors and chips represent actual status only.
- Generic `workbench-card`, `eyebrow`, and non-status `status-chip` use requires a recorded semantic reason.
- Helper copy states consequence, block, recovery, or engineering interpretation; it does not restate a
  visible control or fill space.
- Do not add decorative illustration to authenticated workspaces.
- Grow plots only while additional area improves engineering comparison. After the useful bound, use
  truthful contract-backed companion information or preserve balanced whitespace.

## Brownfield refactoring

For a hotspot:

1. map current responsibilities and dependencies;
2. characterize the primary journey, state transitions, and recovery;
3. extract pure functions and registries;
4. extract controller hooks or reducers;
5. extract coherent stage or region UI;
6. retain bounded compatibility entry points;
7. verify behavior and geometry;
8. perform semantic visual normalization in a separate change;
9. remove compatibility only after zero-consumer proof.

Do not create empty wrappers or move code without creating a stable responsibility boundary.

## Verification

Run only applicable gates, but do not omit a gate because the work is called a refactor:

- affected unit/component tests;
- production build;
- primary journey and changed recovery paths;
- keyboard and focus checks;
- console and overflow checks;
- five registered viewports for user-visible or layout-sensitive work;
- original-resolution semantic review for 1920, 2560, and 3840;
- documentation, guide, and screenshot-manifest updates when required.

A passing test suite does not override a responsibility, semantic hierarchy, or visual-composition failure.

## Forbidden shortcuts

No full frontend rewrite, visual theme replacement, new UI kit, unapproved state/routing dependency,
route-specific 4K patch, one-off filler, blind golden update, silent API fallback, generic card conversion,
or broad formatting pass disguised as a feature change.
