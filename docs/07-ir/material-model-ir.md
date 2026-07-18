# Solver-neutral Material Model IR 구조

## 1. 목적

Material Model IR은 보정된 재료 거동의 **solver-independent source representation**이다. 하나의 IR revision에서 여러 solver exporter가 target-specific card를 만들 수 있게 하고, 각 mapping의 손실·근사·미지원을 명시한다.

IR은 모든 solver의 최소 공통분모가 아니다. 다음을 분리한다.

- 공통 provenance·unit·convention·applicability envelope
- model family plugin이 소유하는 constitutive payload
- solver exporter가 소유하는 target mapping

ADR-006의 첫 구현은 `urn:cmp:reference:isotropic-linear-elasticity:1.0.0`과
OpenRadioss 2025 `/MAT/ELAST`만을 위한 non-production reference slice다. 이 문서의
일반 IR contract를 축소하거나 특정 solver keyword를 IR에 넣지 않으며, reference
payload와 target mapping은 명시적으로 분리한다.

### 1.1 구현된 reference subset

`modeling.material_model`은 stable identity이고, `modeling.material_model_revision`은
append-only immutable revision이다. 첫 revision은 하나의 concrete `Property Set Revision`에서만
생성한다. density, Young's modulus, Poisson ratio는 명시적 SI 열로 snapshot하며,
Material/State/Property의 각 concrete revision을 composite foreign key로 고정한다. optional
yield stress는 이 선형탄성 model에 적용되지 않음을 explicit disposition으로 남긴다. 따라서
새 Catalog revision이 생겨도 과거 IR의 source, 값, applicability는 바뀌지 않는다.

이 reference subset은 calibration, temperature/rate dependent law, plastic hardening, production
validation, release를 주장하지 않는다. OpenRadioss mapping/card는 별도 exporting slice가
그 IR revision만 입력으로 받는다.

### 1.2 구현된 reference export subset

`exporting.solver_card`는 stable identity이고, `exporting.solver_card_revision`은 append-only
immutable revision이다. 현재 허용되는 target tuple은 OpenRadioss `2025`, `/MAT/ELAST`,
`kg_m_s` 하나뿐이다. preflight는 density, Young's modulus, Poisson ratio와 unit을 `exact`로,
reference law에 적용되지 않는 source yield/temperature/rate를 `not_applicable`으로 명시한다.
지원하지 않는 target은 `unsupported`로 실패하며, default 또는 approximation은 사용하지 않는다.

card 생성은 concrete IR revision과 다시 계산한 mapping-report SHA-256을 함께 요구한다.
보고서와 입력이 달라지면 생성할 수 없고, 생성된 card에는 typed field, 각 mapping status,
report/card SHA-256 및 provenance derivation이 고정된다. 이 구현은 generic exporter framework,
arbitrary option payload, production solver qualification, 또는 release approval을 뜻하지 않는다.

## 2. IR이 해결해야 하는 문제

parameter 이름과 숫자만 저장하면 다음을 알 수 없다.

- engineering/true/log strain 중 무엇인지
- Cauchy/nominal/PK stress 중 무엇인지
- small/finite strain formulation인지
- rate/temperature/history dependency가 무엇인지
- table interpolation/extrapolation이 무엇인지
- anisotropy orientation과 material frame이 무엇인지
- parameter가 직접 입력인지 fitting 결과인지
- 적용 가능 strain/rate/temperature domain이 어디인지
- solver가 동일 의미를 지원하는지

따라서 IR은 계산 의미와 사용 제한을 함께 저장한다.

## 3. Top-level envelope

```json
{
  "ir_version": "1.0.0",
  "ir_id": "uuid",
  "ir_revision_id": "uuid",
  "material_ref": {
    "material_revision_id": "uuid",
    "material_state_revision_id": "uuid"
  },
  "model_family": {
    "id": "urn:cmp:model-family:TBD",
    "schema_version": "TBD",
    "schema_digest": "sha256:...",
    "provider_plugin": {
      "plugin_id": "TBD",
      "plugin_version": "TBD",
      "package_digest": "sha256:..."
    }
  },
  "semantics": {},
  "constituents": [],
  "payload": {},
  "applicability": {},
  "validity_domain": {},
  "calibration_evidence": {},
  "validation_evidence": [],
  "provenance": {},
  "extensions": {}
}
```

`TBD`는 실제 JSON instance에서 허용되는 값이 아니다. 구체 model 결정 후 등록된 ID/version으로 대체한다.

## 4. 공통 semantics

```json
{
  "kinematics": "small_strain | finite_strain | plugin_defined",
  "stress_measure": "cauchy | nominal | first_piola_kirchhoff | second_piola_kirchhoff | plugin_defined",
  "strain_measure": "engineering | true_logarithmic | green_lagrange | infinitesimal | plugin_defined",
  "dimensionality": ["3d"],
  "material_symmetry": "isotropic | orthotropic | anisotropic | plugin_defined",
  "material_frame": {
    "required": false,
    "definition": null
  },
  "sign_convention": "tension_positive",
  "temperature_scale": "K",
  "reference_temperature": {"value": 293.15, "unit": "K"},
  "density": {
    "value": null,
    "unit": "kg/m3",
    "required_for": ["explicit-dynamics"]
  }
}
```

허용 enum은 IR version과 model schema가 정의한다. 임의 문자열이면 namespaced plugin value여야 한다.

## 5. Constituent composition

하나의 material model은 여러 역할의 constituent/submodel로 조합될 수 있다.

```json
[
  {
    "id": "component-1",
    "role": "elasticity | plasticity | hardening | rate_dependence | viscoelasticity | damage | failure | thermal | coupling | plugin_defined",
    "model_type": "urn:cmp:model-type:TBD",
    "schema_version": "TBD",
    "payload_ref": "#/payload/components/component-1"
  }
]
```

core는 모든 역할 조합이 유효하다고 가정하지 않는다. model family schema와 semantic validator가 cardinality, compatibility, dependency를 검사한다.

## 6. Quantity와 parameter

### 6.1 Scalar parameter

```json
{
  "parameter_id": "plugin-stable-id",
  "symbol": "p1",
  "quantity_kind": "plugin-defined-physical-meaning",
  "value": 1.23,
  "unit": "MPa",
  "normalized_value": 1230000.0,
  "normalized_unit": "Pa",
  "source": {
    "kind": "calibrated | measured | assumed | literature | derived",
    "entity_revision_id": "uuid"
  },
  "bounds_used": {"lower": 0.0, "upper": 10.0, "unit": "MPa"},
  "uncertainty": {
    "status": "provided | not_provided | not_identifiable",
    "method": "TBD",
    "standard_uncertainty": null,
    "covariance_ref": null
  }
}
```

`symbol`은 UI 표현이고 `parameter_id`가 schema상의 안정 key다. unit dimension과 quantity kind를 모두 검증한다.

### 6.2 Function/table

```json
{
  "function_id": "curve-1",
  "role": "plugin-defined",
  "axes": [
    {
      "key": "x",
      "quantity_kind": "TBD",
      "unit": "1",
      "ordering": "strictly_increasing"
    }
  ],
  "value": {
    "quantity_kind": "TBD",
    "unit": "Pa"
  },
  "data_artifact_id": "uuid",
  "interpolation": {"method": "linear", "space": "linear-linear"},
  "extrapolation": {"below": "error", "above": "error"},
  "constraints": {"monotonic": "nondecreasing | none | plugin_defined"},
  "source_entity_revision_ids": ["uuid"]
}
```

값 배열을 IR JSON에 무제한 inline하지 않는다. 작은 table은 허용할 수 있으나 기준 크기 이상은 digest가 있는 artifact를 참조한다.

## 7. Applicability와 validity domain

### 7.1 Applicability

model의 의도된 해석 유형과 formulation 요구다.

```json
{
  "analysis_domains": ["structural"],
  "loading_modes": ["TBD"],
  "element_formulations": ["continuum | shell | plugin_defined"],
  "time_dependence": "none | rate_dependent | hereditary | plugin_defined",
  "temperature_dependence": "none | tabulated | coupled | plugin_defined",
  "required_state_variables": [],
  "required_initial_conditions": []
}
```

### 7.2 Validity domain

보정·검증 evidence가 지지하는 범위다.

```json
{
  "temperature": {"min": null, "max": null, "unit": "K", "status": "TBD"},
  "strain_rate": {"min": null, "max": null, "unit": "1/s", "status": "TBD"},
  "strain": {"min": null, "max": null, "unit": "1", "measure": "TBD"},
  "pressure_or_triaxiality": {"status": "not_characterized"},
  "loading_history": {"status": "not_characterized"},
  "extrapolation_policy": "disallowed_without_review"
}
```

범위를 모르면 null과 `not_characterized`를 쓴다. 무한 범위로 해석하지 않는다.

## 8. Calibration evidence

The current non-production reference linear-elastic promotion uses an explicit evidence shape;
it does not copy raw optimizer logs or a generic parameter dictionary into the IR:

```json
{
  "status": "reference_candidate_selected",
  "selection_id": "uuid",
  "selection_revision_id": "uuid",
  "calibration_run_id": "uuid",
  "candidate_id": "uuid",
  "candidate_sha256": "sha256:...",
  "diagnostics_artifact_id": "uuid",
  "diagnostics_sha256": "sha256:...",
  "selection_decision": "accepted_for_reference_ir_promotion"
}
```

`converged` is numerical evidence only. The separately versioned Candidate Selection requires a
human reason, and only its current revision may promote the exact IR revision evaluated by the
Calibration Run. Future model families may require richer evidence, but must preserve this
separation between immutable calculation evidence and a human domain decision.

IR은 calibration raw log를 복사하지 않고 immutable run/evidence를 참조한다. release package는 필요한 evidence digest를 함께 고정한다.

## 9. Validation evidence

각 evidence는 다음을 구분한다.

- `semantic`: schema/physical rule
- `material_point`: constitutive response check
- `holdout_data`: fitting에 쓰지 않은 실험 비교
- `virtual_specimen`: solver simulation과 실험 비교
- `solver_syntax`: target card parse/dry run
- `stability`: model 또는 solver-specific stability check

```json
{
  "validation_run_id": "uuid",
  "kind": "virtual_specimen",
  "status": "pass | fail | warning | not_evaluated",
  "plan_revision_id": "uuid",
  "metrics": [{"id": "TBD", "value": null, "threshold_ref": "uuid"}],
  "evidence_artifact_ids": ["uuid"]
}
```

## 10. Core validation level

| Level | 검사 | 담당 |
| --- | --- | --- |
| L0 Document | JSON parse, IR version | core |
| L1 Schema | envelope + model payload JSON Schema | core + model plugin schema |
| L2 Unit/Semantic | dimension, quantity kind, required convention | core + model plugin |
| L3 Physical | bounds, stability, monotonicity, model-specific invariant | model/validator plugin |
| L4 Evidence | calibration/validation provenance completeness | core governance |
| L5 Target Capability | exporter mapping exactness/support | solver exporter |
| L6 Release Policy | reviewer, required validations, no blocking issue | review/release module |

모든 L0~L6 성공 조건은 model/release profile에 따라 machine-readable policy로 정의한다.

## 11. Export capability와 mapping report

### 11.1 Mapping 상태

| 상태 | 의미 | 기본 release 정책 |
| --- | --- | --- |
| `exact` | IR 의미를 target이 직접 표현 | 허용 |
| `transformed` | 의미 보존 변환; 단위/parameterization 변환 포함 | 변환 evidence와 함께 허용 |
| `approximated` | 의미 손실 또는 근사 | domain reviewer 명시 승인 필요 |
| `ignored` | target에서 사용하지 않음 | 필수 constituent면 차단 |
| `unsupported` | 표현 불가 | 생성 실패 |
| `not_applicable` | 해당 target/application에 불필요 | 근거와 함께 허용 |

### 11.2 Mapping report 예시

```json
{
  "mapping_report_version": "1.0",
  "ir_revision_id": "uuid",
  "exporter_package_digest": "sha256:...",
  "target": {"solver": "TBD", "version": "TBD", "card_type": "TBD"},
  "unit_system": "TBD",
  "items": [
    {
      "ir_path": "/payload/components/component-1",
      "target_field": "TBD",
      "status": "exact",
      "transform": null,
      "warning_code": null
    }
  ],
  "summary": {
    "exact": 1,
    "transformed": 0,
    "approximated": 0,
    "unsupported": 0
  },
  "report_digest": "sha256:..."
}
```

승인된 report digest와 실제 export run의 report digest가 같아야 한다.

## 12. IR versioning과 migration

- envelope: semantic version; major는 breaking semantic/schema change
- model payload: model family별 독립 version
- schema digest: version label과 별도로 고정
- migration: old IR → new IR을 생성하는 explicit migration activity
- migration output: 새 IR revision, migration plugin digest, mapping report, warnings
- 과거 IR은 그대로 보존한다.
- exporter는 지원 IR/model schema version range를 manifest에 선언한다.

## 13. IR에서 금지하는 것

- arbitrary Python/JavaScript code
- solver keyword를 neutral semantic처럼 저장
- unit 없는 parameter/table
- 의미가 불명확한 `value1`, `curve2` payload
- model schema 없이 임의 JSON extension
- source/provenance 없는 manual override
- validity domain이 알려지지 않았는데 `unlimited`로 표기
- exporter에서 silent default를 삽입하고 report하지 않는 행위

## 14. 미결정 항목

- `OQ-IR-001` production에서 처음 승인할 model family와 schema. Reference linear elastic,
  tabulated/Voce, linear-Prony와 one-term Ogden--Prony family는 이미 별도 schema로 구현됐다.
- `OQ-IR-002` 일반 symbolic expression/portable equation representation 필요 여부
- `OQ-IR-003` uncertainty/covariance의 MVP 필수 수준
- `OQ-IR-004` material orientation과 field dependency의 공통 envelope 범위
- `OQ-IR-005` solver-specific parameterization 변환의 허용 정책
- `DECISION-IR-006` ADR-0026에 따라 같은 Material Model stable identity의 다음 revision에
  revision-owned promotion evidence를 append한다. T-44의 Ogden--Prony schema 1.1은 exact
  Selection/Run/Candidate/diagnostics와 `promoted_from_model_revision_id`를 각 revision-owned typed
  evidence row에 저장한다. r2 evidence를 r3에 복사하거나 mutable list로 합치지 않으며,
  linear-Prony의 기존 단일 승격 제한은 별도 bounded 계약으로 유지한다.

첫 vertical model이 결정되면 domain expert와 exporter expert가 실제 IR instance 세 개 이상을 작성하여 envelope/payload 경계를 검증한 뒤 schema를 동결한다.

## 15. Material class compatibility routing

Material class is Catalog metadata and is not a constitutive-model discriminator inside the IR.
The first routed families are:

- `metal`: existing isotropic elasticity and tabulated/Voce elastoplastic reference IRs;
- `polymer` or `elastomer`: implemented bounded linear generalized-Maxwell/Prony reference IR;
- `elastomer`: implemented bounded Ogden-Prony hyper-viscoelastic reference IR.

The linear Prony family is not exportable to OpenRadioss LAW62. The hyper-viscoelastic family owns
that mapping. ADR-0032 permits a separate conditional `/MAT/LAW1` + `/VISC/LPRONY` reference fragment
only for nearly-incompressible (`0.49 <= nu < 0.5`), shear-only records with uncharacterized bulk
relaxation and zero `k_ratio`. Form 2 and `flag_visc=2` preserve the instantaneous elastic base and
normalized shear ratios; the required external solid-property total-strain formulation
`I_smstr=10/12` remains an acknowledged mapping prerequisite. Exporters must inspect the concrete IR
family/schema digest and emit an explicit
mapping status; Material class alone never authorizes card generation.

The implemented linear family is
`urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0`. It pins exact Material, Material
State and Property Set revisions, interprets the Catalog elastic moduli as instantaneous, stores
one to ten ordered `(g_ratio, k_ratio, relaxation_time_s)` rows for the reviewed Processing Output
schema (legacy manual/reviewed Candidate revisions retain their earlier one-to-five boundary), and records bulk relaxation as
either `characterized` or `not_characterized`. The latter requires every `k_ratio` to be explicit
zero; it is not a silent incompressibility default. Both ratio sums remain below one. This bounded
family is reference/non-production until the domain and solver mapping fixtures are approved.

ADR-0031 defines the Processing Output promotion evidence. The new IR revision pins the exact
Processing Output, source Test Data JSON, Mapping Profile and Property Set revisions plus the
selected term count/mode, RMSE, BIC, fitted instantaneous shear modulus and caller-acknowledged
Catalog modulus mismatch limit. Terms are re-read from the immutable server Artifact; fitted
parameters are never accepted from the browser.

## 16. Bounded reference Ogden–Prony family

ADR-0023 adds a separate non-production family rather than widening linear viscoelasticity:

`urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0`

Its immutable revision pins the exact Material, Material State, and Property Set revisions and
contains explicit SI density, one Ogden term `(mu_pa, alpha)`, and one-to-five ordered normalized
shear-Prony terms `(g_ratio, relaxation_time_s)`. The model declares `instantaneous` moduli,
`incompressible` volumetric response, temperature-independent behavior, and `elastomer` class.
Catalog E and ν remain source-property provenance and do not replace Ogden parameters.

The two declared projections are:

| IR concept | Abaqus 2025 | OpenRadioss 2025 LAW62 |
| --- | --- | --- |
| density | `*DENSITY` — exact | `RHO_I` — exact |
| Ogden μ/α | `*HYPERELASTIC, OGDEN, N=1` — exact | LAW62 `MU1`/`ALPHA1` — exact |
| shear Prony | `*VISCOELASTIC, TIME=PRONY` — exact | LAW62 `GAMMA_i`/`TAU_i` — exact |
| incompressibility | `D1=0` — exact | `nu=0.495` — approximated |
| unit declaration | kg-m-s comment — transformed | kg-m-s comment — transformed |

The reference scope excludes generic parameter maps, EAV properties, multiple Ogden terms,
bulk-Prony terms, temperature shift functions, and production calibration. The mapping report
SHA-256 must be acknowledged before card creation. A card revision pins its exact source IR
revision and duplicates its ordered terms in typed card tables so deferred database constraints
can reject a mismatched projection.

## 17. Neutral Material JSON exchange envelope

`cmp.neutral-material` is the user exchange envelope around an IR; it is not a second constitutive
model authority. The document contains:

- document/schema version, organization/project/classification and content digest;
- exact Material/State/Test/Dataset revision references and source artifact digests;
- exact Mapping Profile and Processing Recipe revisions;
- common Batch가 생성한 Output이면 exact Batch/Member/successful Attempt와 Recipe digest;
- ordered processing methods/options and raw/normalized/processed/fitted/extrapolated curve stages;
- calibration candidates, selected candidate/reason, bounds, objective, prediction and residual;
- characterized, fitted and extrapolated domains;
- one schema-valid Material Model IR revision payload;
- applicability, validation state and solver mapping evidence.

Import validates every referenced schema/method/model version before creating an immutable imported
document and derived internal artifacts. Export of the same revision is deterministic. Large curves
may be chunked inside the documented JSON+ZIP package, but manifest order and SHA-256 make the
logical document identical. Abaqus `.inp` and OpenRadioss `.rad` remain separate native artifacts.

The reference family roadmap deepens existing implementations rather than introducing a generic
parameter map: metal elastoplastic candidates (Voce, Swift, Hockett–Sherby, Ghosh), polymer
generalized-Maxwell/Prony with optional WLF/Arrhenius evidence, and elastomer Neo-Hookean,
Mooney–Rivlin, Yeoh or Ogden with optional Prony overlay. A family is exported only where the
versioned solver capability manifest and mapping tests support that concrete schema.

### 17.1 Implemented T-56 reference envelope

Schema version `1.0.0` implements the bounded hyperelastic promotion path. A user reviews one
Neo-Hookean, Mooney--Rivlin, Yeoh or one-term Ogden Candidate and records a non-empty selection
reason. Promotion creates a new Neutral Material stable identity and revision 1; it never mutates the
Candidate, calibration Run, Dataset or existing solver-specific IR.

The canonical JSON is also stored as an immutable Artifact. PostgreSQL migration 071 projects its
governed fields into explicit typed tables and columns, including family-specific parameters and one
row per exact source Dataset revision. Import recalculates the canonical digest and resolves every
tenant-scoped Candidate, Plan, scientific profile, Dataset revision and Artifact digest before it
creates an identity. A mismatch is rejected rather than repaired or defaulted.

The exchange endpoint is solver-neutral. Abaqus/OpenRadioss capability decisions, six-state mapping
reports and native ASCII generation from this envelope belong to T-57.

### 17.2 T-63 closed three-family envelope

Migration 076 and the `cmp.neutral-material` contract extend the envelope without introducing a
generic parameter map. `material_model_ir.model_family` is a closed discriminator with these
typed branches:

- `isotropic_tabulated_plasticity`: density, E, Poisson ratio, initial yield stress, exact
  hardening-curve Artifact, reviewed candidate family blend and explicit characterized/extension
  domains;
- `generalized_maxwell`: density, instantaneous E/Poisson ratio, bulk-relaxation status,
  reference temperature and ordered typed Prony terms;
- `hyperelastic`: the four existing public families plus an optional exact-revision Prony overlay.

Source curve evidence also has a closed discriminator: governed Dataset, canonical Test Data
document or shear-relaxation Dataset. PostgreSQL verifies the exact revision in the corresponding
typed table. Metal selections pin an exact Processing Output and Mapping Profile; polymer and
hyperelastic selections pin the exact Candidate, Run, Plan, diagnostics Artifact and source
Dataset evidence used by the bounded fitting path. A missing Recipe or scientific profile is
represented by an explicit `not_applicable` reason, never a silent null/default.

The existing hyperelastic 1.0 canonical representation remains readable byte-for-byte. New
documents preserve `normalized`, `processed`, `fitted`, `extrapolated` or `residual` stages as
applicable and round-trip through validate/import/export without numeric changes. T-64 owns
family-specific solver-card regeneration and Bulk consumer parity from these exact Neutral
revisions.

### 17.3 T-64 family-neutral solver projection

Migration 077 extends the existing immutable Neutral solver-card identity rather than creating a
parallel card store. New revisions carry the closed `model_family`, the exact Neutral model-schema
digest, typed metal or linear-viscoelastic parameters, optional hardening Artifact evidence,
ordered Prony terms and every six-state mapping item. Existing T-57 rate-independent hyperelastic
revisions remain readable and preserve their original canonical bytes and digest.

The declared reference mappings are deliberately bounded:

- isotropic tabulated plasticity emits Abaqus `*DENSITY`, `*ELASTIC`, `*PLASTIC` or OpenRadioss
  `/MAT/LAW36` plus `/FUNCT` from the exact fitted/extrapolated Neutral curve stages;
- generalized Maxwell emits Abaqus `*VISCOELASTIC, TIME=PRONY`; OpenRadioss is explicitly
  `unsupported` because LAW62 requires a hyperelastic Ogden base;
- hyperelastic with an exact Prony overlay emits the selected public potential plus Abaqus Prony
  rows, while OpenRadioss LAW62 is allowed only for one-term Ogden. No other potential is converted
  silently.

The primary resource path is `/api/v1/neutral-solver-cards/{id}`. The former
`neutral-hyperelastic-solver-cards` paths remain compatibility aliases. A stored card can reproduce
its mapping report only by reading the exact Neutral revision and matching the pinned report digest.

