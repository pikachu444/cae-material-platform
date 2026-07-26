# DUI-08A Activity review queue evidence

## User outcome

Activity is now a compact work queue instead of a destination card page. A User sees only review
requests they submitted, a Reviewer or Administrator sees submitted work waiting for a decision,
and completed decisions remain visible as recent outcomes. Browser-local Modeling and solver-card
activity remains available to resume.

## Implemented workspace

`/activity` is one continuous queue:

```text
Needs attention | In progress | Recent outcomes | Advanced evidence
```

- The effective product role comes from `/product-access/me`; the authenticated principal comes
  from `/me`.
- Review requests come from the existing tenant-scoped review API. User rows are filtered by the
  authenticated `requested_by` value. Reviewer and Administrator rows retain the tenant review
  queue.
- Reviewer and Administrator decisions require a reason and the request's exact manifest hash.
  The API-returned immutable request replaces only the decided row.
- User-facing rows use work labels such as Material data review, Solver card review, and Test data
  review. Full identifiers and immutable evidence remain in the collapsed Advanced area.
- Loading, failed loading with Retry, stale-response suppression, decision failure, and empty states
  are explicit. A failed decision leaves the request pending and recoverable.

This slice does not invent request submission, job progress, or release results. Those projections
remain follow-up work until their real source and lifecycle are connected.

## Verification

- Focused React and API tests cover User isolation, Reviewer decisions, required decision reason,
  exact manifest submission, returned-row replacement, role loading, and stale-response handling.
- Production TypeScript/Vite build and bundle budgets pass.
- The live Activity route was captured at 1366×768, 1440×900, and 1920×1080 with one real pending
  synthetic Material review request. The capture does not create a decision or fake a completed
  release.
- Documentation impact, user-guide classification/link checks, and the screenshot manifest pass.

The current guide, navigation contract, product policy, UI component contract, user flow, capture
script, and all three current Activity screenshots are updated in this same change.
