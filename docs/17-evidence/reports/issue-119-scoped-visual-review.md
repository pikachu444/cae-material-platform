# Issue #119 scoped visual-review corrections

Date: 2026-07-23

## Scope

The independent design-only review found four correctable presentation issues while the
pre-publish pipeline itself was being implemented. This follow-up changed no product workflow or
domain behavior:

- CAE Cards keeps one filled contextual download; row downloads are secondary actions.
- Modeling gives the rendered engineering curve a graph-dominant drawable at 1366×768,
  1440×900, and 1920×1080.
- Activity explicitly labels the no-local-session empty state and states that attention/queue
  integration remains pending.
- Export calls the current state an ephemeral candidate/delivery preview and does not claim a
  reviewed model or new native card.

DUI-06 reviewed-model/native-card delivery, DUI-08 exact-session restoration and review attention,
and Administration topology work remain outside this change.

## Reference and topology comparison

The structural reference remains the graph-dominant workspace documented in
`docs/17-evidence/reports/t96-modeling-graph-workspace.md`. The two-column navigator plus persistent
graph topology is unchanged. The fix only prevents the SVG flex item from shrinking vertically,
widens its responsive coordinate space, restores readable axis separation, and corrects status
language.

| Viewport | Current screenshot | Rendered graph result |
| --- | --- | --- |
| 1366×768 | `docs/user-guide/images/current/modeling-data-1366x768.png` | Axis labels visible; drawable is about 75% of the full Modeling workspace. |
| 1440×900 | `docs/user-guide/images/current/modeling-fit-1440x900.png` | Shallow settings ribbon remains above a dominant graph; no third inspector column. |
| 1920×1080 | `docs/user-guide/images/current/modeling-export-1920x1080.png` | Central graph expands with the viewport; delivery remains explicitly pending. |

The live capture script measures the rendered horizontal axis, not a source-coordinate width, and
fails every Data, Process, Fit, or Export capture below 72% of the full Modeling workspace.

## Evidence and verification

- 20 current PNGs were regenerated from the live deterministic Compose fixture in an empty staging
  directory and atomically replaced only after the complete expected output set passed.
- The current inventory has no equal-byte current↔historical image pair, so the manifest contains no
  duplicate allowance.
- The capture rejects multiple filled CAE Card download actions and requires the Activity
  no-session status.
- `npm --prefix apps/web test -- --run common-processing-workbench.test.tsx
  material-library-activity.test.tsx engineering-curve-plot.test.tsx`
- `npm --prefix apps/web run build`
- `uv run pytest tests/contracts/test_capture_current_product.py -q`
- `uv run --with playwright python scripts/capture_current_product.py`
