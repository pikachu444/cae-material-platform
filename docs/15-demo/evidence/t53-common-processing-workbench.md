# T-53 common Mapping Profile and Processing Workbench evidence

Verified on 2026-07-18 against the Docker Compose demo and PostgreSQL migration head
`20260829_063_T53_mapping_profiles`.

## Demonstrated workflow

1. The user opened `/datasets/processing` and selected exact DP600 Test Data revision 2.
2. The browser loaded canonical JSON through the API rather than using a UI-only fixture.
3. The user created a reusable Mapping Profile and appended revision 2 with a strong current ETag.
4. PostgreSQL retained both immutable profile revisions and typed channel binding rows.
5. The workbench loaded seven versioned deterministic processing methods from the server registry.
6. A server preview mapped engineering strain/stress, applied `rows.sort_unique`, and returned each
   intermediate curve stage, row counts, diagnostics and a Mapping Profile SHA-256.
7. The UI rendered mapped input and the selected stage on shared numeric axes. It labels the result
   `Preview only · not promotable` so an ephemeral result cannot be mistaken for stored evidence.

## Evidence

![Exact input, reusable profile and ordered processing steps](../images/t53-processing-stage-overlay.png)

![Server-produced processing stages and shared-axis curve overlay](../images/t53-processing-curve-overlay.png)

- Domain fixtures cover sorting, duplicate/missing policies, crop, scale/shift, interpolation,
  moving average, Savitzky–Golay, smoothing spline and invalid option/quantity paths.
- API tests cover the method registry, preview composition and immutable profile create/list/get/revise.
- A fresh PostgreSQL migration verified explicit identity/revision/channel/attribute-binding tables,
  exact catalog Attribute Definition revision pins, RLS and immutable revision triggers.
- React tests cover exact Test Data loading, saved profile selection and a real server-preview response.

This is T-53 increment 1. Immutable processing outputs and multi-curve alignment/statistics remain
required before T-53 is complete.
