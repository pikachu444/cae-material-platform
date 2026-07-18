# T-63 three-family Neutral Material JSON evidence

## Demonstrated workflow

The connected Docker/PostgreSQL service restored a governed elastomer calibration Run, selected an
exact reviewed Ogden Candidate, and promoted it to immutable Neutral Material revision 1. The
workbench displayed the canonical digest and enabled the exact `cmp.neutral-material` JSON download.

## Implemented family coverage

- metal: an exact T-55M Processing Output containing a selected tabulated hardening candidate is
  promoted to `isotropic_tabulated_plasticity` without re-fitting or copying a latest alias;
- polymer: an exact reviewed T-55P Prony Candidate is promoted to `generalized_maxwell` with its
  ordered terms, fit domain, residual diagnostics and source Dataset revisions;
- elastomer: an exact reviewed T-55E hyperelastic family Candidate is promoted with the baseline
  model revision and ordered shear-Prony overlay when that evidence exists;
- every source, selection, processing and calibration reference is an exact revision pin;
- all three family documents use the versioned `cmp.neutral-material` JSON contract and deterministic
  canonical content SHA-256.

## Persisted evidence

- migration head: `20260911_076_t63_neutral`;
- stable identity: `modeling.neutral_material`;
- immutable revision: `modeling.neutral_material_revision`;
- ordered viscoelastic terms: `modeling.neutral_material_prony_term`;
- explicit typed family, source, selection, applicability and overlay columns rather than a generic
  EAV or an opaque model JSON blob;
- PostgreSQL tenant/classification scope checks, exact-source checks, append-only triggers and RLS;
- native Test Data, common Processing Output and diagnostics Artifact digests are verified again when
  a canonical Neutral document is imported.

## Live verification

The browser restored calibration Run `8472bdf8-8c4e-4753-8e97-4d5c9c56d395`, selected its exact
`ogden_1` Candidate and created Neutral model revision 1. The API ran as the non-owner application
role after the migration/bootstrap sequence, and the resulting row plus ordered Prony evidence were
read back through the service. Focused schema/domain/API/UI tests and PostgreSQL integration tests
passed before the repository-wide CI gate.

The deterministic demo currently seeds the complete elastomer promotion path. A desktop-size T-63
capture is intentionally deferred to T-65, where all three guided seed paths can be shown together
instead of documenting only one family. Metal and polymer promotion controls deliberately remain
gated until their exact T-55M Processing Output or reviewed
T-55P Prony Candidate exists; T-65 will add those two guided seed paths rather than inventing evidence
or silently selecting a latest revision.

T-64 is the next boundary: all three Neutral families must enter the same versioned Abaqus and
OpenRadioss preflight, mapping report, preview and native ASCII card flow.
