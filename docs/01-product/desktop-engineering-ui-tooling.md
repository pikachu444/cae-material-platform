# Desktop Engineering UI Tooling

Status: authoritative product-design tooling decision

## Purpose

The frontend must be designed and reviewed as a desktop engineering application, not as a marketing site or generic SaaS dashboard. No single design plugin is authoritative. The workflow uses four coordinated layers.

## Required reference inputs

Every visual task must use both repository reference layers:

- `docs/00-research/ux-reference-gallery/README.md` for the curated cross-product principles;
- `docs/00-research/images/gui-reference/README.md` and the local images it inventories for
  screen-level Granta MI and Material Modeler comparison.

The relevant implementation interpretation in `docs/01-product/gui-functional-parity-plan.md` must
also be checked. A filename or README-only review does not satisfy this requirement. Evidence must
name the images opened and distinguish what the current DUI task changes from what a later backlog
task owns.

## 1. Figma MCP — editable design canvas

Use Figma MCP when a connected Figma workspace is available.

Primary uses:

- import current application screens or code-backed components into an editable canvas;
- create and review the Materials, Material Detail, Modeling and Administration layouts before broad implementation;
- inspect spacing, typography, pane proportions and responsive states;
- connect approved Figma components to production React components;
- return implementation screenshots to the canvas for design review.

Figma is not the source of domain truth. The repository specifications remain authoritative for data semantics, workflow, links, revision/provenance and solver-card behavior.

Required Figma pages:

1. Foundations
2. Desktop shell
3. Materials workspace
4. Material Detail
5. Modeling workbench
6. Administration
7. Component states
8. Responsive 1366 / 1440 / 1920

## 2. Codex project Skill — implementation discipline

The repository contains `.codex/skills/desktop-engineering-ui/SKILL.md`.

The Skill must be applied to every frontend task that changes layout, typography, navigation, components or CSS. It converts the product specification into repeatable implementation rules and prevents regression to card-heavy SaaS layouts.

The Skill does not replace `AGENTS.md`. `AGENTS.md` owns repository-wide engineering invariants; the Skill owns the desktop engineering UI workflow.

## 3. Storybook — component specification

Storybook is the target component workbench. It is not currently installed.

Required stories:

- ApplicationShell
- CommandBar
- SplitPane
- NavigatorTree
- DataGrid
- PropertySheet
- TabStrip
- StatusBar
- CurvePlotFrame
- PlotToolbar
- InspectorPanel
- SolverCardTable
- NativeCardPreview
- Empty / loading / error states

Every primitive must provide compact, normal and constrained-width stories where relevant. Visual states include default, hover, focus, selected, disabled, loading, warning and error.

Storybook must be introduced after the component contracts are accepted and before legacy CSS cleanup is considered complete.

## 4. Playwright — full-screen visual acceptance

Playwright remains the authoritative executable check for complete application screens and user workflows.

Required viewport baselines:

- 1366 × 768
- 1440 × 900
- 1920 × 1080

Required screen baselines:

- Materials Search
- Browse Tree
- Material Detail Overview
- Material Detail Properties
- Material Detail Curves
- CAE Cards
- Native Card Preview
- Modeling Data
- Modeling Process
- Modeling Fit
- Modeling Export
- Governed Import
- Activity
- Administration Database
- Administration Layout
- Administration Links

Visual comparison must fail on unintended changes to pane proportions, header height, typography, wrapping, overflow, control density or plot size.

## Tool responsibility boundary

| Tool | Owns | Does not own |
| --- | --- | --- |
| Figma MCP | visual exploration, layout review, editable prototypes | domain contracts, database schema, solver mapping |
| Codex Skill | repeatable implementation rules and review sequence | product decisions not written in repository specs |
| Storybook | isolated component states and component visual regression | end-to-end application workflow |
| Playwright | complete screens, viewport behavior and task flow | detailed component design exploration |


## 5. External open-source skills — mandatory quality loop

The project skill is the workbench-specific fourth layer. Add three external helpers before the first
new DUI slice. Run these from the repository root; do not use a global installation.

    npx --yes skills@latest add addyosmani/agent-skills --skill frontend-ui-engineering --agent codex --yes
    npx --yes skills@latest add vercel-labs/agent-skills --skill web-design-guidelines --agent codex --yes
    npx --yes skills@latest add anthropics/skills --skill webapp-testing --agent codex --yes

| Layer | Responsibility | Boundary |
| --- | --- | --- |
| \`frontend-ui-engineering\` | Build production React components, connect state correctly, and apply keyboard/accessibility discipline. | It cannot replace the approved CAE workspace topology with a generic responsive/mobile dashboard. |
| \`web-design-guidelines\` | Audit implemented UI code for accessibility, interaction, performance and web-interface defects. | Its generic advice is advisory when it conflicts with the desktop-engineering product specification. |
| \`webapp-testing\` | Drive the real local app, assert workflow state, capture browser evidence and inspect console errors. | A passing automated interaction does not by itself prove reference/workbench quality. |
| \`desktop-engineering-ui\` | Enforce repository references, desktop CAE grammar, measurements and legacy-CSS migration. | It does not authorize new domain behavior or substitute for the three external checks. |

Run the same loop for every target screen:

    inspect current route and relevant local reference images
    → implement against existing API/controller/state
    → run route/domain regression tests
    → capture and exercise the live app at 1366×768, 1440×900 and 1920×1080
    → audit with desktop-engineering-ui and web-design-guidelines
    → verify task flow and browser errors with webapp-testing
    → fix every hard-gate failure
    → recapture/retest until every gate passes
    → update evidence, screenshot manifest and user documentation

Record the external-skill audit results in the visual PR evidence. Do not mark a visual task complete
because an agent says it looks polished; use the repository visual-acceptance matrix and actual
screenshots, measurements and interactions.

## 6. Decision

The authoritative decision hierarchy is:

1. repository domain contracts and \`AGENTS.md\`;
2. the UI program brief and product/interaction specification;
3. the project \`desktop-engineering-ui\` skill;
4. the external implementation, audit and browser-testing skills;
5. optional Figma exploration and planned Storybook workbench.

Figma remains optional. Storybook remains a planned component dependency. Playwright and the external
browser-testing skill both protect the real application screen and task flow; neither permits a
mock-only implementation.
