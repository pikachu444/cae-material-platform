# ADR-0036: Material-only domain revisions and stable data links

- Status: Accepted target policy for the redesign program
- Date: 2026-09-05
- Scope: Material information persistence, stable saved objects, typed links and migration
- Canonical policy: [Data management policy](../docs/product/data-management-policy.md)

## Context

The original domain documents made immutable revisions and a provenance graph the default for
nearly every saved object. That protected raw bytes and scientific results, but it also made an
ordinary title or metadata correction look like a scientific change and encouraged hidden revision
writers. It blurred the difference between a Material information edit, a TestRun/TestData fact,
an analysis result and a relationship traversal.

The product owner has accepted a narrower history boundary. This ADR is the target contract for the
future database/API migration; current v1 persistence remains explicitly legacy until that migration
is implemented and read back.

## Decision

1. Only Material information edits have domain revision history. A Material information revision
   contains Material identity fields, associated Material State, manufacturing and heat-treatment
   information, and direct property values such as density, `E`, `nu`, yield and applicability.
2. State and PropertySet identities are ordinary stable objects without independent domain history.
   Specimen, TestRun, TestData, Dataset, Selection, Mapping Profile, Process, Model, Solver Card
   and Link data are stable-ID saved objects. Renaming one preserves its typed links and does not
   stale scientific data.
3. Test conditions remain TestRun/TestData data. Actual computational inputs/options affect current
   eligibility. They do not rewrite immutable saved bytes. Saved results retain the actual inputs and
   settings used to create them as result data.
4. Raw, input and output artifacts remain immutable. Original unit text, normalized units, quantity
   semantics, typed input/output relations, authorization, scientific validation and release meaning
   remain required.
5. A universal Entity–Activity–Agent provenance graph, per-edit save reasons, snapshot proliferation
   and hidden nonmaterial revision writers are not required. Concrete result and artifact contracts
   may retain the input usage, generation or responsibility evidence they need. Software/schema/file
   versions, hashes and opaque concurrency tokens are metadata, not domain history.
6. Links are explicit typed relationships between stable objects. Traversing a relationship in either
   direction is not derivation. Link resolution never guesses by title, sibling name or `latest`.
   Direct Test Data and direct Solver Card routes remain independently addressable.
7. The primary compatibility journey is ordinary-ID Test Data search/detail → explicitly associated
   stored Solver Card → native download. A title metadata PATCH updates the same row, keeps the
   association, and creates zero nonmaterial domain revisions. Native file bytes and card JSON stay
   separate representations.

## Compatibility and migration

The v1 exact compatibility mapping is private, and the unmodified v1 runtime is explicitly legacy.
Two old concrete revisions are imported as independent objects rather than reconstructed as a head
chain. Migration must be a real additive database/API change with exact read-back, authorization,
artifact and scientific regression evidence. Hiding fields, aliasing to `latest` or maintaining a
second browser-only model is not migration. Pre-cutover artifacts, backups and a new-write
reconciliation path are retained; rollback never destructively downgrades new data.

## Preserved and superseded decisions

This ADR partially supersedes the revision/provenance assumptions in ADR-0002, ADR-0003 and ADR-0006
through ADR-0034. It does not alter ADR-0001 modular boundaries, ADR-0004 isolated plugins, or ADR-0005 Material
Model IR semantics. ADR-0035 visual evidence lifecycle remains accepted, except for the narrow
five-viewport rule in Decision 2 that ADR-0037 partially supersedes; current/frozen/transient paths,
frozen bytes, recovery, checksums and offline checks remain intact. Each affected ADR carries a reciprocal
notice naming the portion preserved and the portion superseded. Scientific equations, solver
eligibility, security controls, raw/released byte immutability and actual validation/release meaning
remain authoritative within their own scopes.

| ADR | Preserved scope | Superseded scope |
| --- | --- | --- |
| 0002 | PostgreSQL, tenant/RLS and typed domain integrity | universal provenance/audit and all-entity revision default |
| 0003 | immutable content-addressed raw/released artifacts | treating artifact identity as a revision history for every object |
| 0006 | Material-data-first product purpose and bounded reference work | universal revision/provenance as the product surface |
| 0007 | processing semantics, units, raw bytes and immutable outputs | nonmaterial processing revision/activity requirement |
| 0008 | statistics/QC, source data and selection semantics | universal Selection/statistics history requirement |
| 0009 | candidate detection, human adjudication and no silent deletion | per-decision candidate/selection revision/activity requirement |
| 0010 | import, raw bytes, detection and explicit mapping acknowledgement | universal mapping-profile/snapshot revision history |
| 0011 | bounded calibration equations, execution and evidence | universal calibration revision history |
| 0012 | convergence, human selection, IR promotion and evidence | default Candidate/Model revision chain |
| 0013 | validation template/runner boundaries and explicit evidence | universal validation revision/provenance requirement |
| 0014 | separate non-production interpretation and immutable evidence | universal activity writer for interpretation edits |
| 0015 | review requests and separation of duties | every review edit as a domain revision |
| 0016 | release completeness, package bytes and release meaning | all-entity provenance history as a release gate |
| 0017 | release lifecycle and downstream impact | every lifecycle edit as a content revision |
| 0018 | metal equations, IR semantics, mappings and support gates | nonmaterial model/result domain-history assumption |
| 0019 | live PostgreSQL verification and staged delivery evidence | universal revision/provenance delivery criterion |
| 0020 | governed classification, route boundaries and polymer scope | history assumptions for ordinary State/TestData/model objects |
| 0021 | shear-relaxation Dataset semantics and immutable result bytes | Dataset identity revision chain |
| 0022 | Prony equations, bounded candidates and manual selection | universal Plan/Candidate/IR revision histories |
| 0023 | Ogden/Prony equations, LAW62 mapping and support gates | ordinary model/card revision-history assumption |
| 0024 | typed genealogy, cardinality, authorization and exact pins when required | universal exact-revision links and graph-as-derivation assumption |
| 0025 | pilot journeys, recovery and scientific/security acceptance | all-entity snapshots/provenance as completion criteria |
| 0026 | calibration evidence, comparison and promotion boundaries | IR revisions for ordinary nonmaterial changes |
| 0027 | immutable export bundle/card bytes and delivery integrity | ordinary export selection/bundle revision history |
| 0028 | typed Catalog, attributes, links, explorer and publication meaning | independent histories for ordinary records/profiles/layouts/links |
| 0029 | JSON exchange, mapping, recipe and exact input/output contracts | universal mapping/recipe revision history |
| 0030 | workbench actions, access surfaces, solver mapping and eligibility | every committed change as a recipe/output revision |
| 0031 | Processing Output review, promotion and release eligibility | revision wrapper around ordinary saved objects |
| 0032 | exporter eligibility, unsupported/approximation reporting and bytes | default exporter/card history assumption |
| 0033 | exact Recipe/Batch inputs and promoted result evidence where required | universal lineage/domain-history requirement |
| 0034 | session, workspace, API and product-shell behavior | universal revision/provenance and per-edit save assumptions |
