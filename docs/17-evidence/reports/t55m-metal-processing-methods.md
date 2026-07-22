# T-55M metal tensile processing methods evidence

Date: 2026-07-18

- Runtime: Docker Compose demo with PostgreSQL 16 and the current API/web images.
- Input: `DP600-T55M-12PT` exact Test Data revision 1, imported from the synthetic MPa CSV
  adapter and stored with normalized stress in Pa.
- Mapping: exact `DP600 tensile normalized mapping` revision 1.
- Pipeline: sort/unique, Huber elastic modulus, 0.2% proof stress, peak-stress necking
  candidate, and manual-index engineering-to-true/plastic conversion.
- Results: 210 GPa elastic modulus on four points, 468.462 MPa proof stress, necking candidate
  at source index 10, and six retained positive true-plastic points.
- Recipe: `DP600 metal tensile preprocessing` revision 2 was published with the exact Mapping
  Profile and five ordered method versions/options.
- Batch: `67e760ed-c68c-4872-9012-52381a09b3ca` passed compatibility preflight and succeeded
  with one append-only attempt and one immutable Processing Output.
- UI: `/datasets/processing` shows all six stages, the actual server curve overlay, scalar values,
  units, diagnostics, and exact digest.

The fixture is synthetic and the methods are reference/non-production. This evidence proves the
data-processing contract and connected product flow, not material qualification or solver execution.
