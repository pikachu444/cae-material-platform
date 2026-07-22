# T-56 Neutral Material JSON evidence

## Demonstrated workflow

The Docker/PostgreSQL demo restores an immutable multi-test calibration Run by exact ID, lets the
user select one reviewed hyperelastic family Candidate, and promotes that Candidate into a new
stable Neutral Material identity with immutable revision 1. The connected workbench shows the
canonical document digest and downloads the exact `cmp.neutral-material` JSON.

![Reviewed family promoted to canonical Neutral Material JSON](../images/t56-neutral-material-json.jpg)

## Persisted evidence

- migration head: `20260906_071_t56_neutral`
- stable identity: `modeling.neutral_material`
- immutable revision: `modeling.neutral_material_revision`
- exact sources: four Dataset revisions and their normalized Artifact SHA-256 digests
- candidate evidence: exact Plan, Run, family Candidate and diagnostic Artifact digest
- exchange contract: `cmp.neutral-material` `1.0.0` with deterministic content SHA-256
- model representation: typed Neo-Hookean, Mooney--Rivlin, Yeoh or one-term Ogden union
- curve evidence: normalized, fitted and residual stages with quantity and unit semantics
- status: `reference/non-production`; no automatic approval or solver qualification

## Verified workflow

The live browser restored Run `5bd58c37-d3e4-4470-8456-55cabea426e0`, selected its Ogden family
Candidate, and created Neutral model revision 1. The result pinned four exact Dataset revisions,
twelve curve stages, the numerical validation result and content digest. Schema/domain/API/migration,
React, production build, fresh PostgreSQL migration and repository CI are required before merge.

T-57 remains the boundary for consuming this canonical family-neutral IR through versioned
Abaqus/OpenRadioss capability manifests and native solver-card mappings.
