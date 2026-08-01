# T-54 versioned Processing Recipe Library evidence

Verified on 2026-07-18 against the Docker Compose demo and PostgreSQL migration head
`20260831_065_t54_recipe`.

## Demonstrated increment

1. The user selected an existing exact Mapping Profile revision and one ordered common step.
2. The API created a stable `common_processing_recipe` identity and immutable draft revision 1.
3. The Recipe revision pinned the exact Mapping Profile aggregate/revision/SHA-256 and
   `rows.sort_unique@1.0.0` options.
4. Publishing appended revision 2 with lifecycle `published`; revision 1 was not updated.
5. The connected React workbench listed `DP600 common cleanup · r2 · published`, restored the
   ordered step editor and displayed the exact profile revision and Recipe content digest.

![Published reusable Recipe with exact profile and content pins](../images/historical-task-screenshots/t54-processing-recipe-library.jpg)

Migration 065 uses explicit identity, revision and ordered step tables. Method options are bounded,
schema-validated JSON objects with detached SHA-256, not catalog EAV. Composite tenant/classification
foreign keys prevent cross-scope Profile pins; RLS and immutable triggers match the existing
architecture boundary.

This is T-54 increment 1. Exact batch input membership, compatibility preflight, per-member
run/attempt persistence, partial failure retention and failed-member retry remain in the next increment.
