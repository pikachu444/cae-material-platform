# T-64 family-neutral exporter and Bulk evidence

Date: `2026-07-18`

## Implemented boundary

- Metal `isotropic_tabulated_plasticity`: Abaqus `*PLASTIC` and OpenRadioss `/MAT/LAW36`.
- Polymer `generalized_maxwell`: Abaqus `*VISCOELASTIC, TIME=PRONY`; OpenRadioss remains an
  explicit `unsupported` preflight result because a linear model is not LAW62.
- Hyperelastic with exact Prony overlay: Abaqus for every declared public potential; OpenRadioss
  `/MAT/LAW62` only for one-term Ogden. Non-Ogden requests are blocked before card creation.
- Rate-independent T-57 hyperelastic documents and card content keep their compatibility path.

Migration 077 extends the existing immutable Neutral solver-card projection with a closed model
family, typed metal/viscoelastic fields, ordered Prony terms and one row per mapping status. It does
not add a generic EAV or unrestricted JSON value column.

## Live PostgreSQL/API proof

The retained local Compose database was migrated from revision 076 to
`20260912_077_t64_export`. Through the protected application API, exact Neutral revisions for an
Ogden+Prony Candidate and a Yeoh+Prony Candidate produced:

| Neutral family | target | result | card SHA-256 |
| --- | --- | --- | --- |
| Ogden + two exact Prony terms | Abaqus 2025 | `201`, report reproduced | `5c58afb5a79c0a8f540e7eb8211f51df0fd9a0bebd06fdfd655fdf29f2d698db` |
| Ogden + two exact Prony terms | OpenRadioss 2025 | `201`, LAW62 with acknowledged ν approximation | `918ea412f443d8c8f97f091c28ce9ba65830c376c3536a9cabadb600a70ad151` |
| Yeoh + two exact Prony terms | Abaqus 2025 | `201`, report reproduced | `21cee5c42673b479c22f4618f57574bd0d4f3c161fdbc0da64d3bfdade965877` |
| Yeoh + two exact Prony terms | OpenRadioss 2025 | `200` preflight, `exportable=false`, `unsupported` | no card |

All three stored card revisions have seven immutable mapping-item rows and two ordered Prony rows.
The primary `/neutral-solver-cards/{id}` preview and mapping-report resources reproduced the stored
report digests. T-58 candidate discovery returned both exact Neutral JSON documents plus each
generic report/native-card pair (eight Neutral members total), proving that Bulk uses the
family-neutral dispatcher instead of the former hyperelastic-only regeneration call.

## Automated regression

- domain fixtures cover metal Abaqus/OpenRadioss, polymer Abaqus plus explicit OpenRadioss block,
  hyper-viscoelastic Abaqus, Ogden LAW62 and non-Ogden LAW62 rejection;
- migration fixtures cover closed typed projections, composite revision foreign keys, RLS,
  immutable triggers and absence of JSON/EAV value storage;
- API fixtures cover primary resources and T-57 compatibility aliases;
- React tests cover acknowledgement, immutable creation and preview through the primary resource;
- full Python suite: `759 passed`, with the `76` PostgreSQL-marked cases skipped in that pass;
- isolated PostgreSQL suite against PostgreSQL 16: `76 passed`;
- web production build: passed the 300,000-byte entry and 120,000-byte lazy-chunk budgets;
- web regression: `29` files and `58` tests passed;
- Ruff, mypy (`562` source files), architecture, contract lint/compatibility and user-guide gates
  passed.

T-65 remains responsible for a clean seed that creates the complete metal/polymer/elastomer Neutral
genealogy, browser download checks, checksum Bundle assembly and current desktop screenshots. Solver
execution is intentionally excluded.
