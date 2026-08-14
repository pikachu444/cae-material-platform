---
name: material-platform-frontend-architecture
description: Plan or review CAE Material Platform frontend feature work and refactoring before React/CSS implementation, preserving Materials-to-Modeling journeys, feature ownership, exact revision/state contracts, semantic UI rules, and behavior-preserving migration.
---

# Material Platform Frontend Architecture

Use this project-local skill before production React/CSS implementation whenever a task:

- adds or changes a frontend feature;
- touches a registered debt hotspot;
- changes Materials-to-Modeling handoff or Data/Process/Fit/Export continuity;
- changes application shell, workspace, plot, table, or responsive composition;
- refactors state, API, types, components, or CSS ownership; or
- adds helper copy, illustration, badge, emphasis, or wide-screen behavior.

This skill fixes architecture and semantic-UI scope. Use `frontend-ui-engineering` for implementation,
`desktop-engineering-ui` for approved visual execution/review, and `webapp-testing` for browser evidence.

## Authority

Read only relevant parts of:

1. exact issue and approved backlog/program unit;
2. root `AGENTS.md` and `apps/web/AGENTS.md`;
3. `docs/01-product/frontend-ui-principles.md`;
4. `docs/05-architecture/frontend-architecture.md`;
5. exact route/user-flow/component contract;
6. applicable visual acceptance gates and registered references;
7. target code, tests, API/state contracts, and styles.

Do not infer a redesign mandate from a request to improve one screen.

## Preflight packet

Before implementation, return one bounded packet containing:

- primary user journey and visible outcome;
- change classes: behavior, structural, semantic visual, defect, primitive, or shell;
- owned feature, current owner files, responsibilities, and dependencies;
- registered hotspot impact;
- target ownership and dependency direction;
- preserved API, domain, URL, identity/revision, state, persistence, and recovery contracts;
- Materials-to-Modeling handoff or Data-to-Export continuity impact;
- structural movement separated from semantic visual movement;
- helper-copy, color, weight, badge, illustration, surface, and wide-screen rationale;
- tests and five-viewport/interaction evidence;
- compatibility, removal conditions, forbidden shortcuts, and escalation points.

A file list or generic plan is insufficient.

## Architecture decisions

- Preserve `app -> features -> shared`.
- Reject feature deep imports and cycles.
- Keep route/page code composition-oriented.
- Keep multiple async workflows and named transitions out of large render components.
- Move pure registries, defaults, and transformations out of React components.
- Keep feature API/model/controller/UI ownership explicit.
- Do not add responsibility to a registered hotspot without extraction or an approved exception.
- Do not introduce a frontend dependency unless the issue proves a capability gap and records impact.

At roughly 400 component lines, require a responsibility inventory before expansion. At roughly 600 lines,
reject a new responsibility without an extraction plan. These are review triggers, not mechanical split targets.

## Journey and state decisions

Preserve both journeys:

```text
Materials -> exact material/revision/context -> card download or Start Modeling

exact Material/State/Test Data -> Data -> Process -> Fit -> explicit saved model
-> Export -> solver card -> Materials read-back
```

Reject:

- reselecting context that was already known upstream;
- `latest`, first-item, global-output, or another-session fallback;
- stage changes that discard the persistent graph or selected exact source without contract authority;
- failures that erase recoverable source, draft, selection, or last-valid result;
- UI-only completion that cannot be read back from the server or Materials workflow.

## Semantic UI decisions

For every new visible element, name its semantic role.

Reject:

- helper copy that restates controls or fills space;
- decorative illustration in a normal authenticated workspace;
- accent-colored ordinary headings;
- generic bold escalation;
- saved counts or categories styled as status;
- nested card grammar without object-level independence;
- plots enlarged beyond a useful engineering bound;
- fabricated wide-screen content;
- route-specific high-DPI patches.

Accept helper copy only for consequence, block, recovery, or engineering interpretation. Accept status styling
only for actual state. Accept wide-screen companion regions only when current contracts supply truthful data.

## Brownfield method

1. characterize current behavior and recovery;
2. extract pure functions and registries;
3. extract controller/reducer boundaries;
4. extract coherent UI regions;
5. maintain bounded compatibility;
6. verify behavior and viewport geometry;
7. normalize semantic visuals in a separate change;
8. remove compatibility after zero-consumer proof.

Do not perform a full rewrite. Do not combine broad structural and visual changes merely to reduce PR count.

## Stop and escalate

Stop for:

- a required route-topology or interaction-model decision;
- an API/domain contract change outside the issue;
- unavailable authoritative reference or acceptance;
- a proposed dependency or framework change;
- inability to preserve a critical exact-context, state, or recovery contract;
- a structural change that cannot be separated from broad visual change; or
- physical-4K claims without required actual-device evidence.

Return the exact decision required rather than inventing one.
