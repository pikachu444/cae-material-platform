---
name: frontend-ui-engineering
description: Implement or modify production React/CSS components and responsive interactions with accessibility, contract preservation, and project design-system fidelity.
---

# Frontend UI Engineering

Use this skill only for production UI code changes. The approved project target, canonical UI field
contracts and existing application contracts outrank generic frontend patterns.

## Implement against existing contracts

- Inspect current components, semantic tokens, state, API adapters and tests before adding an
  abstraction or dependency.
- Keep data loading and state transitions separate from rendering. Preserve URL/server state and the
  explicit loading, empty, blocked, stale and error-recovery paths.
- Reuse shared primitives and tokens. Avoid inline styling, arbitrary one-off values, new UI-kit
  dependencies and route-specific override layers unless the task proves they are required.
- Exercise real engineering-length labels and datasets. Virtualize or paginate large tables and do
  not render unbounded curve points.
- Preserve upstream invalidation and immutable revision behavior; a rendering shortcut must not create
  a client-side fallback or a second source of truth.

## Accessibility and interaction

- Prefer native buttons, links, inputs, tables and landmarks before ARIA substitutes.
- Give every control an accessible name, visible focus and keyboard operation. Dialog, drawer and
  error focus movement, Escape behavior and dismissal must be explicit.
- Do not use color alone for status. Maintain WCAG AA contrast and respect reduced motion.
- Keep pane, tree, list and table overflow local and discoverable without page-level horizontal
  overflow. Preserve selection and focus after resize, refresh and recoverable failure.

## Responsive implementation

Follow the exact approved topology and the canonical visual checklist selected by
`desktop-engineering-ui`. Recompute plot geometry for each viewport rather than stretching glyphs or
SVG axes. Add wide-screen information only when an existing contract supplies it; never fabricate
content or stretch graphs, tables, forms or copy merely to fill space.

## Verify

- Run affected unit/component tests and the production build.
- Exercise keyboard navigation and every changed loading/empty/blocked/error state.
- Capture and inspect the required viewports through the project visual workflow.
- Check console errors, overlap, clipping, local/page overflow and stale state after upstream changes.
