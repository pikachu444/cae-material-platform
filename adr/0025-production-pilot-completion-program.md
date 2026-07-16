# ADR-0025: complete the product as user-visible production-pilot verticals

- Status: Accepted
- Date: 2026-07-16
- Related: ADR-0006, ADR-0019, ADR-0020, ADR-0024; T-39 through T-47

## Context

The repository already contains a substantial immutable revision, provenance, authorization,
artifact, job, plugin and review/release foundation. It also contains bounded PostgreSQL-backed
reference flows for steel elastoplasticity, polymer linear viscoelasticity and elastomer
Ogden--Prony cards. The remaining gap is not another foundation rewrite: users need deeper test
context, selected real tabular formats, repeat processing, iterative calibration, bulk delivery
and task-oriented documentation.

Public Granta MI and Simcenter Material Data Center material-management capabilities inform the
linked-record and governed-delivery requirements. Simcenter Material Modeler and MCalibration
inform missing processing/calibration interactions. Their proprietary schema, UI and algorithms
are not inputs to this implementation.

## Decision

1. Preserve migrations 001 through 048, all released/raw objects and existing verticals.
2. Deliver T-39 through T-47 as small end-to-end increments. Each increment includes typed
   PostgreSQL persistence, protected API, connected React UI, tests and user documentation.
3. Prioritize this user path: Material/Test context -> immutable Dataset -> explicit Processing ->
   manual or automatic Calibration -> neutral IR -> mapping report -> card -> individual/bulk
   download.
4. Keep three declared reference families: metal elastoplasticity, polymer linear viscoelasticity
   and elastomer Ogden--Prony. They remain `reference/unapproved` without domain sign-off.
5. Support Abaqus 2025 and OpenRadioss 2025 as explicit reference targets. Actual solver execution
   and qualification remain excluded by product-owner decision.
6. Add no generic EAV, proprietary vendor parser, model-specific core shortcut or silent mapping.
7. Maintain one execution-status document so another development session can resume at the first
   unfinished acceptance gate without rediscovering priorities.

## Consequences

- The product becomes usable through vertical workflows before enterprise connector breadth.
- Domain approval may lag implementation. The UI and API must expose that state rather than block
  reference development or imply production qualification.
- New global workbench routes may be added, but existing Material deep links remain compatible.
- Proprietary laboratory, PLM and licensed-solver integrations require separately authorized
  credentials, samples and acceptance evidence.
