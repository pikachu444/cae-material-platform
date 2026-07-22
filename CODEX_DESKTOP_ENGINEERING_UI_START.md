# Codex Desktop Engineering UI Start

This entrypoint governs the next frontend program. It supersedes ad-hoc prompts about making the UI look more like Granta MI or Material Modeler.

## Read in order

1. `AGENTS.md`
2. `docs/01-product/desktop-engineering-ui-product-spec.md`
3. `docs/01-product/desktop-engineering-ui-tooling.md`
4. `docs/13-delivery/desktop-engineering-ui-backlog.md`
5. `.codex/skills/desktop-engineering-ui/SKILL.md`
6. `docs/00-research/ux-reference-gallery/README.md`
7. `docs/00-research/images/gui-reference/README.md` and every local image it inventories
8. the relevant screen section in `docs/01-product/gui-functional-parity-plan.md`
9. current route code, tests, screenshots and user guides

## Program rule

Do not begin with a generic visual cleanup. Implement the backlog in order and treat the product/interaction specification as the source of truth for workflow, state continuity, workspace topology and acceptance.

Each implementation PR must:

- complete one bounded DUI task;
- preserve database, revision/provenance, unit and solver-mapping contracts;
- show current → target user actions and state transitions;
- use the desktop engineering component grammar;
- capture 1366×768, 1440×900 and 1920×1080 states where the task affects layout;
- test keyboard, loading, empty, error and disabled states;
- identify legacy classes/components removed or still present;
- update current screenshots and user guidance.

The curated UX gallery is a source-level overview. The official GUI reference manifest and its
local images are the required screen-level comparison source. Filenames or written descriptions
alone are not sufficient: open each relevant image and record the applied structure, omissions,
current-task changes and explicitly deferred backlog work in the PR evidence.

The first implementation task is `DUI-01 — Application shell, command bar and status bar`.
