# ADR-005: 공통 IR envelope와 model-owned payload

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

