# ADR-0020: Route Material workflows by governed class and deliver polymer viscoelasticity in two stages

## 먼저 읽기

- **무엇을 정했나요?** Material revision에 class를 명시해 알맞은 workflow를 안내하되 model을 자동
  선택하지 않습니다. polymer의 linear-Prony와 elastomer의 Ogden–Prony/LAW62는 별도 IR로 둡니다.
- **왜 중요한가요?** 금속·polymer·elastomer의 서로 다른 물리 의미를 섞거나, linear relaxation model을
  LAW62에 조용히 끼워 맞추는 constitutive approximation을 막기 위해서입니다.
- **언제 읽나요?** material class, workflow 추천, viscoelastic·hyper-viscoelastic IR, Abaqus·OpenRadioss
  exporter 또는 bulk relaxation 처리를 추가할 때 읽습니다.
- **용어를 쉽게 말하면:** `generalized-Maxwell/Prony`는 시간에 따른 선형 relaxation을 여러 항으로
  표현하는 model이고, `hyper-viscoelastic`은 큰 변형의 hyperelastic 거동과 시간 의존성을 함께
  다룹니다. `not_characterized`는 필요한 물성이 측정되지 않았음을 정직하게 표시합니다.
- **상태 표기는?** `Accepted`는 class routing과 두 단계 reference model 분리를 채택했다는 뜻입니다.
  production 재료 분류·parameter·solver execution이 승인됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-15
- Related: ADR-0005, ADR-0006, ADR-0018, ADR-0019; T-07, T-D01, T-D02, T-D03

## Context

The product is a Material data management and CAE-use platform, not an MCalibration clone.
The implemented vertical already supports typed basic properties, tensile data processing,
reference elastoplastic IRs, and OpenRadioss/Abaqus cards. It does not yet distinguish a steel
workflow from polymer or elastomer workflows at the Material revision boundary.

A single small-strain Prony representation maps naturally to Abaqus time-domain viscoelasticity,
but it is not semantically equivalent to OpenRadioss `/MAT/LAW62`, which requires a hyperelastic
base. Treating both as one card would create a silent constitutive approximation.

## Decision

1. Add `material_class` to Material schema v2 with `unclassified`, `metal`, `polymer`,
   `elastomer`, `composite`, `ceramic`, and `other` values.
2. Preserve every v1 revision unchanged. A missing stored class is read as `unclassified`; an
   explicit reclassification is a new Material revision.
3. Material class recommends compatible workflows but never selects a model or exporter by
   inference. Exact IR family, exporter capability, target version, unit system, and mapping
   preflight remain authoritative.
4. Keep the existing steel path: `metal` plus tabulated-plasticity IR can produce the bounded
   OpenRadioss LAW36 and Abaqus isotropic-plasticity reference cards.
5. Deliver polymer viscoelasticity in two independent stages:
   - a solver-neutral linear generalized-Maxwell/Prony IR and Abaqus time-domain card;
   - an Ogden-Prony hyper-viscoelastic IR for Abaqus and OpenRadioss LAW62.
6. Never project the linear Prony IR to LAW62. That target is reported as `unsupported`.
7. Use shear relaxation CSV (`time`, `relaxation shear modulus`) as the first calibration input.
   Bulk relaxation is never inferred from constant Poisson ratio. Missing bulk evidence is an
   explicit `not_characterized` model disposition and an acknowledged approximation where valid.
8. These implementations remain `reference/non-production` until numeric IR schemas, formulas,
   golden cards, and scientific fixtures receive domain approval. Real solver execution
   qualification is out of this delivery wave.

## Persistence and compatibility

`catalog.material_revision.material_class` is nullable only for legacy schema revisions. New v2
revisions store one explicit enum value under a database check and tenant-scoped index. Typed
family-specific modeling tables will hold Prony and Ogden terms; no generic EAV or unrestricted
model JSON is introduced.

The implemented linear stage uses migration 040 for the IR and migration 041 for the immutable
Solver Card projection. Abaqus 2025 `kg_m_s` cards emit `*DENSITY`, instantaneous `*ELASTIC`, and
`*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC`; each data row is ordered as shear ratio, bulk ratio,
and relaxation time in seconds. The mapping report records `exact`, `transformed`, or
`not_applicable` per item before creation. A deferred database guard compares every stored card
term with the exact source IR revision. This is a reference mapping and not solver-qualified.

Migration 042 implements the first shear-relaxation input boundary without changing the manual IR
contract. A dedicated Test Method/Run pins an exact Specimen and Material State revision. Dedicated
non-EAV Dataset identity/revision tables preserve the verified raw CSV and a normalized SI Parquet
Artifact as separate immutable revisions, including original column/unit semantics and Raw Asset
provenance. Time must increase strictly and the bounded reference relaxation modulus must not
increase. The web curve is evidence for later fitting; import never selects or changes Prony terms.

Official mapping references:

- [Abaqus `*VISCOELASTIC` keyword](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-viscoelastic.htm)
- [Abaqus time-domain viscoelasticity](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEMATRefMap/simamat-c-timevisco.htm)

## Consequences

- The web catalog can explain why a workflow is available, planned, or unsupported.
- Existing immutable hashes and revision histories remain valid.
- Polymer support cannot accidentally reuse metal plasticity or a non-equivalent solver card.
- Supporting a new class/model still requires an explicit IR schema, capability manifest,
  mapping report, tests, and governance evidence.
