# T-95 production UX foundation shell

Date: 2026-07-21

## Scope

This slice ports only the previously proven route/session behavior and establishes the approved
full-width application shell, shared tokens, typography, primitives, and continuous workspace
grammar. It does not claim the governed Browse Tree or final Modeling workflow complete.

## Reference principle

- Granta MI and Material Data Center: data table and selected record remain the dominant continuous
  surface; headings and description do not consume the engineering workspace.
- Material Modeler: Modeling cannot retain a permanent third column; the graph receives the fluid
  column and settings become a shallow row or disclosure.

## Before and after

- Rejected baseline: `docs/15-demo/images/ux-layout-review/rejected-materials-1440x900.png`
- Approved target: `docs/15-demo/images/ux-layout-review/materials-1440x900.png`
- Live shell: `docs/15-demo/images/ux-redesign-v2/foundation-materials-1440x900.png`

Live Chromium measurements at 1440×900:

| Region | Width |
| --- | ---: |
| Workspace | 1,376 px |
| Filter | 264 px |
| Results | 830 px |
| Selected context | 280 px |

At 1366×768 the selected context closes and the result region expands beyond 1,000 px. Workspace
titles are 20 px; body and table data are 14 px. Persistent workspace panes use dividers without
shadow or nested-card treatment.

## User task improved

The root route now resolves to Materials. The global navigation exposes only Materials, Modeling,
and Activity; Administration remains in the role-gated user menu. Search results, solver-card counts,
and selected context are visible without opening legacy module dashboards.

## Verification

- `npm test -- --run app.test.tsx`: 9 passed
- `npm run build`: TypeScript, Vite, and bundle budget passed
- Live Docker/Chromium load at 1440×900 and 1366×768
- `python docs/00-research/ux-layout-review/validate_review.py`
- `uv run cmp-check-user-guide --root .`

## Remaining limits

- Browse Tree is not yet the scalable governed navigator.
- Result-cell tooltip/column-priority behavior remains in the Materials PR.
- Live Modeling DOM still requires the full Data/Process/Fit/Export restructuring and final graph
  measurement.
