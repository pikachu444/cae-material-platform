# DUI-08B review submission evidence

## Scope

Users can request review from Material Detail and Native Solver Card Preview without entering a raw
identifier. The action pins the immutable revision that the workspace already loaded; it does not
create a decision, release, or new domain contract.

## Contract and recovery

| Surface | aggregate type | immutable source | duplicate key | recovery |
| --- | --- | --- | --- | --- |
| Material Detail header | `catalog.material` | current Material `material_id`, revision id, content hash, classification and lifecycle | type + id + revision | block submit and Retry status if duplicate check fails; retain reason and Retry request if submit fails |
| Native Card Preview header | `exporting.solver_card` or `exporting.neutral_solver_card` | `loadSolverCardEvidence` current card revision id, content hash, classification and lifecycle | type + id + revision | block submit and Retry status if duplicate check fails; retain reason and Retry request if submit fails |

The action reads matching requests before it enables a submission. A failed read cannot fall through
to a possibly duplicate submit. It reports Waiting for review, Approved, Changes requested, or the
existing non-draft lifecycle and never re-submits the same immutable revision. Reviewer and
Administrator decision controls remain in Activity.

## Visual acceptance

The action stays in each existing shallow header action area. The default state is one secondary
button; the compact reason input appears only while composing a request. Native card text remains the
dominant preview and there is no persistent inspector or developer identifier UI. Live browser
captures at 1366×768, 1440×900, and 1920×1080 are registered in the current screenshot manifest.

## Verification

- `npm run build --workspace @cmp/web`
- focused Vitest coverage: exact payload, required reason, existing pending/decided state, duplicate
  prevention, failure/retry, solver evidence hash projection, and existing card/activity regressions.
