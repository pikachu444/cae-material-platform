# ADR-0012: Human Candidate Selection is versioned separately from numerical convergence and IR promotion

- Status: Accepted
- Date: 2026-07-20
- Decision owners: Product, Material Modeling, Scientific Software
- Related: `T-24`, `T-23`, `T-22`, `T-25`, ADR-005, ADR-006, ADR-011

## Context

`T-23` retains every reference Calibration Candidate, including its objective, convergence state,
and immutable diagnostics Artifact. Numerical convergence is not a human acceptance, release, or
production-qualification decision. The platform must let a material modeler record why one
converged Candidate is acceptable for the narrow reference IR while preserving prior decisions and
preventing a stale evaluated IR from being overwritten.

The first reference Material Model is an immutable revisioned aggregate, not a mutable parameter
record. A candidate from an old Calibration Run can no longer be safely applied after the model
head changes. The decision must retain tenant/project/classification isolation and concrete
Selection, Candidate, Run, and diagnostics references without an EAV or opaque parameter payload.

## Decision

1. Add a stable `modeling.calibration_candidate_selection` identity with an immutable
   `calibration_candidate_selection_revision` history. Its stable identity is fixed to one
   Calibration Run and a human label. A later revision may change the chosen Candidate only inside
   that same Run and must record a new non-blank human reason.
2. A Selection revision may only reference a `converged` Candidate from a `succeeded` Run and pins
   the Candidate SHA-256. PostgreSQL checks, composite organization/project/classification foreign
   keys, forced RLS, append-only revision guards, and a trigger repeat these rules at persistence
   time. There is no automatic lowest-objective acceptance.
3. Promotion is allowed only from the **current** Selection revision and only when the exact
   Material Model revision evaluated by the Calibration Run remains the current model head. The
   command appends a new Material Model revision; it never updates the selected Candidate, Run,
   source Model revision, Property Set, Dataset, or card.
4. The promoted reference linear-elastic revision changes only the selected Young's modulus and
   carries explicit typed evidence columns and API fields for Selection/revision, Run, Candidate
   and Candidate SHA-256, diagnostics Artifact and diagnostics SHA-256. PostgreSQL verifies those
   values reproduce the frozen Selection/Candidate/Run facts and rejects an attempt to remove
   evidence from a later derived revision.
5. The protected workbench labels numerical convergence separately from human acceptance. It
   requires a selection label and reason, then exposes a distinct promotion action and stale-head
   conflict. This is non-production reference workflow evidence, not approval, release, uncertainty
   estimation, or solver validation.

## Consequences

- A user can traverse `Calibration Run -> converged Candidate -> human Selection revision -> new
  Material Model IR revision` while preserving all prior revisions and diagnostic provenance.
- The OpenRadioss reference exporter continues to consume a frozen IR revision. A card generated
  after promotion is a new downstream artifact, not a change to an existing card or source IR.
- The initial reference schema deliberately supports one parameter (`youngs_modulus_pa`) and one
  exact evaluated source revision. General candidate comparison, production review approval,
  uncertainty, model-family-specific promotion rules, and validation remain separate decisions.

## Revisit trigger

- A production model family requires more than the explicit reference parameter/evidence fields.
- Candidate selection must feed a formal review/approval or release manifest.
- Validation templates and solver result evidence (`T-27`/`T-28`) require a stronger promotion or
  qualified-card policy.
