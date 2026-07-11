# ADR-001: 모듈형 모놀리스와 격리 실행 plane

- 상태: Accepted
- 기준일: 2026-07-11

## Context

Domain 경계와 첫 시험/model/solver가 아직 확정되지 않았고 revision, provenance, review, release는 강한 transaction 일관성이 필요하다. 반면 scientific plugin과 상용 solver는 dependency, 자원, 보안 및 실행 시간이 다르다.

## Decision

하나의 repository와 authoritative PostgreSQL을 사용하는 모듈형 모놀리스로 시작한다. API와 worker는 같은 application codebase에서 별도 process로 배포한다. Plugin과 solver는 Job Spec/Result Manifest를 사용하는 별도 runner에서 실행한다.

## Consequences

- domain refactoring과 transaction이 단순하다.
- 위험한 계산은 격리된다.
- module ownership과 architecture test가 없으면 다시 결합될 위험이 있다.
- service별 독립 배포는 측정된 trigger가 생길 때까지 미룬다.

## Revisit trigger

독립 팀/release cadence, 별도 규제 경계, module별 현저한 scale 차이, process 격리로 해결되지 않는 장애 요구.

