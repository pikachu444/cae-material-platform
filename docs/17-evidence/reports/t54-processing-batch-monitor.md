# T-54 Processing Batch Monitor evidence

Date: 2026-07-18

- Runtime: Docker Compose demo, PostgreSQL 16, migration `20260901_066_t54_batch`.
- Recipe: `DP600 common cleanup`, exact published revision 2.
- Inputs: `DP600-TENSILE-02` revision 1 and `DP600-TENSILE-01` revision 2.
- Preflight: both exact revisions compatible; two output points per member.
- Execution: batch `3f12edd5-a8c2-429c-8309-67ef0677eb8d`, status `succeeded`.
- Evidence: two append-only attempts and two separately committed immutable Processing Outputs.
- UI: the connected `/datasets/processing` Batch Run Monitor displays the exact Recipe digest,
  input revision pins, compatibility result, member attempt number, and output revision.

The screenshot contains synthetic demo data only. It is not evidence of production material-model
validation or solver execution.
