# ADR-005: 공통 IR envelope와 model-owned payload

## 먼저 읽기

- **무엇을 정했나요?** 모든 재료 model이 공유해야 할 unit, 적용 범위, evidence 같은 정보는 공통
  IR envelope에 두고, model마다 다른 parameter와 식은 해당 model이 관리하는 payload에 둡니다.
- **왜 중요한가요?** 새 model을 추가할 때마다 core schema를 크게 바꾸지 않아도 되며, exporter가
  model의 의미와 target solver가 지원하는 범위를 명확하게 비교할 수 있습니다.
- **언제 읽나요?** 새 constitutive model family, IR 필드, payload schema, solver exporter나 mapping
  규칙을 추가할 때 읽습니다.
- **용어를 쉽게 말하면:** `IR`은 특정 solver 문법에 묶이지 않은 재료 model의 중간 표현입니다.
  `envelope`는 모든 model에 공통인 바깥 구조, `model-owned payload`는 model별 내용이며,
  `mapping report`는 target으로 정확히 옮긴 값과 변환·근사·미지원 항목을 알리는 결과입니다.
- **상태 표기는?** `Accepted`는 이 결정을 채택했다는 뜻입니다. 관련 기능이 모두 구현됐거나 현재
  환경에서 검증을 마쳤다는 뜻은 아닙니다.

- 상태: Accepted
- 기준일: 2026-07-11

## Context

Parameter key/value만으로는 stress/strain measure, kinematics, unit, history, validity를 표현할 수 없다. 반대로 모든 model을 하나의 거대 core schema에 넣으면 확장이 core release에 종속된다.

## Decision

IR은 core가 versioning하는 common envelope와 model plugin이 versioning하는 payload schema로 구성한다. Envelope는 unit, semantics, applicability, validity, evidence, provenance를 강제한다. Exporter는 target capability와 mapping report를 생성한다.

## Consequences

- 새로운 model이 core migration 없이 추가된다.
- model schema와 exporter 모두 semantic 책임을 가진다.
- schema가 지나치게 자유로워지지 않도록 실제 model instance와 validation이 필요하다.

## Revisit trigger

서로 다른 실제 model family 세 개 이상을 작성했을 때 공통 envelope가 반복적으로 payload 의미를 방해하거나 핵심 공통 개념을 놓치는 경우.

