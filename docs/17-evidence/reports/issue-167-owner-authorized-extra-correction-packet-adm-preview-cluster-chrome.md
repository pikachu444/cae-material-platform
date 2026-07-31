# Issue #167 ADM-SCHEMA-CORE owner-authorized extra correction — bounded preview chrome

Date: 2026-07-31  
Status: product-owner-authorized correction after final qualitative rejection  
Prerequisite: `issue-167-reviewer-packet-adm-preview-bounded-composition-final.md`

## Why this correction exists

The preceding correction passed deterministic gates and fresh review, but the active main agent's
subsequent full-screen qualitative review found two connected defects in the final 3840×2160
original:

1. `Back to editor` is detached at the far right of the full-width preview heading while the global
   `Close preview` command remains visible. The duplicate return actions weaken task continuity.
2. The actual Record/grid and graph pair is correctly bounded, but `.preview-content` expands across
   the complete remaining pane. Its heading, tabs and context dividers therefore continue far beyond
   the task content, making trailing space read as an unfinished component interior rather than
   space after a bounded left/top working cluster.

The product owner explicitly authorized the fix with `응 수정해`.

## Required product result

- Keep the current 2560/3840 Record grid and graph sizes, shared top edge, 20 px gutter, graph
  geometry, local scrolling and visual hierarchy.
- Bound the complete preview task chrome — heading, tabs, context, Record grid and graph — to one
  left/top-aligned content width at wide viewports. The heading/tab/context rules end with that
  bounded cluster. Remaining width is visibly outside the task content at the far right.
- Expose exactly one obvious return action while preview is open:
  - compact preview keeps the in-preview `Back to editor` action;
  - wide preview keeps the task-bar `Close preview` action and hides the in-preview duplicate.
- The retained return action must preserve the existing focus-return contract and keyboard path.
- Do not add a card, wrapper background, explanatory copy, badge, internal term or filler. Do not
  stretch the preview chrome or actual content to reduce empty pixels.
- Preserve one active `Record preview` or `Layout definition`, conditional saved curve, graph-free
  scalar Attribute edit, exact revision labels, Add, loading/saving/error/stale behavior and all
  existing responsive states.

## Correction ownership

The extra configured correction writer owns only:

- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- ADM-SCHEMA-CORE-owned PNG and measurement/state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

Do not edit common product specs, manifest, inventory, reports, production files or another family.
Existing unrelated changes belong to other work and must not be reverted.

## Deterministic and qualitative proof

Recapture the complete eleven-target, sixty-state and two-wide packet. Extend the measurement and
validator to prove:

- wide preview-content width is bounded to the actual Record-plus-graph cluster rather than the
  entire remaining pane;
- task chrome and section content share the same left/right bound;
- wide inline `Back to editor` is hidden while the visible enabled task-bar `Close preview` is the
  sole return action;
- compact task-bar return is hidden while the visible enabled in-preview `Back to editor` is the
  sole return action;
- the retained return action closes preview and restores focus correctly;
- Record/grid and graph dimensions, 12–24 px gutter, shared top edge, real overflow rail and
  pointer/wheel/PageDown/Home/End consequences remain valid;
- all existing projection, conditional, selection, stale, error and keyboard assertions remain
  valid.

Required commands:

```powershell
python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

The writer returns exact changed paths, final hashes, test results and residual risks without making
an acceptance decision. The active main agent then performs a new original-resolution qualitative
gate and prepares one final fresh read-only review. No further correction is authorized.
