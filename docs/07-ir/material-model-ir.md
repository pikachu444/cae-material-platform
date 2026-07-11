# Solver-neutral Material Model IR 구조

## 1. 목적

Material Model IR은 보정된 재료 거동의 **solver-independent source representation**이다. 하나의 IR revision에서 여러 solver exporter가 target-specific card를 만들 수 있게 하고, 각 mapping의 손실·근사·미지원을 명시한다.

IR은 모든 solver의 최소 공통분모가 아니다. 다음을 분리한다.

- 공통 provenance·unit·convention·applicability envelope
- model family plugin이 소유하는 constitutive payload
- solver exporter가 소유하는 target mapping

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

```json
{
  "calibration_run_id": "uuid",
  "input_selection_revision_id": "uuid",
  "processed_dataset_revision_ids": ["uuid"],
  "calibrator": {
    "plugin_id": "TBD",
    "package_digest": "sha256:...",
    "algorithm": "TBD"
  },
  "objective": {"definition": "TBD", "final_value": null},
  "weights": {"definition": "TBD"},
  "convergence": {"status": "TBD", "reason": null},
  "diagnostic_artifact_ids": ["uuid"],
  "candidate_selection_reason": "TBD"
}
```

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

- `OQ-IR-001` 첫 model family와 schema
- `OQ-IR-002` 일반 symbolic expression/portable equation representation 필요 여부
- `OQ-IR-003` uncertainty/covariance의 MVP 필수 수준
- `OQ-IR-004` material orientation과 field dependency의 공통 envelope 범위
- `OQ-IR-005` solver-specific parameterization 변환의 허용 정책

첫 vertical model이 결정되면 domain expert와 exporter expert가 실제 IR instance 세 개 이상을 작성하여 envelope/payload 경계를 검증한 뒤 schema를 동결한다.

