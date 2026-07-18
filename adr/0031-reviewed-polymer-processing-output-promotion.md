# ADR-0031: Reviewed polymer Processing Output promotion

- Status: Accepted
- Date: 2026-07-19
- Tasks: T-55P, T-56, T-57, T-67
- Requirements: FR-MOD-P-001..004, FR-JSON-007..009, FR-NAV-002

## Context

The common Processing Workbench can fit and compare one-to-ten-term generalized-Maxwell
candidates, select one candidate by BIC or an explicit user choice, and commit the complete result
as an immutable Processing Output. The existing linear-viscoelastic IR path accepts only one-to-five
terms and its reviewed promotion path is coupled to the older bounded two-term Calibration Run.
Consequently the configurable Workbench result cannot become the Neutral Material JSON or Abaqus
card that the user requested.

Abaqus time-domain isotropic viscoelasticity directly consumes dimensionless shear/bulk Prony
ratios and relaxation times. The official documentation states that its test-data calibration uses
up to 13 terms and that direct `TIME=PRONY` data lines may be repeated. The platform keeps the
smaller, explicit one-to-ten-term Workbench boundary:

- <https://docs.software.vt.edu/abaqusv2024/English/SIMACAEMATRefMap/simamat-c-timevisco.htm>
- <https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-viscoelastic.htm>

## Decision

1. Add a processing-owned promotion route from one exact Processing Output revision to a new
   stable linear-viscoelastic Material Model identity and immutable revision 1. The route does not
   mutate a manual or legacy calibrated model.
2. Accept only a final `polymer.prony_fit_compare` method at its declared version. Re-read the
   digest-pinned Processing Output Artifact and derive terms from its selected scalar results; the
   client cannot submit fitted parameters.
3. Pin the exact Processing Output, source Test Data JSON, Mapping Profile and Property Set
   revisions in typed IR evidence. Persist selection mode, selected term count, normalized RMSE,
   BIC, fitted instantaneous shear modulus and its relative difference from the Catalog elastic
   properties.
4. Require the caller to provide and acknowledge an explicit maximum instantaneous-modulus
   relative mismatch. The server rejects a larger mismatch. No production acceptance threshold is
   selected by this ADR.
5. Extend the reference processing-promoted IR and PostgreSQL/card projections to one-to-ten
   ordered Prony terms. Existing manual and legacy two-term Candidate revisions retain their exact
   schema IDs, digests and bytes.
6. Bulk relaxation remains `not_characterized` and every `k_i` is explicit zero because the common
   MVP input is shear-relaxation data. No bulk behavior is inferred.
7. Neutral Material JSON uses a distinct typed `prony_processing_output_selection`. It contains
   normalized, selected fitted and residual curves, exact Mapping Profile evidence, the output
   digest and the characterized time domain. Import must reproduce all of those pins.
8. Abaqus mapping remains exact for the declared ratios/times and transformed only for the stated
   unit convention. OpenRadioss linear-Prony remains `unsupported`; it is not silently converted to
   LAW62.

## Consequences

- A saved Recipe/Batch output and a directly committed output share the same promotion contract.
  Recipe identity is included only when an exact batch/recipe relation is available; the immutable
  ordered step snapshot is always present in the Processing Output.
- The UI must show the selected candidate evidence and modulus-consistency result before enabling
  promotion, then continue to Neutral JSON, mapping preflight, preview and native download.
- PostgreSQL constraints, exact cross-scope foreign keys and immutable triggers remain the
  authoritative evidence guard. No generic JSON/EAV model parameter store is introduced.
