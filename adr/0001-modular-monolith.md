# ADR-001: 모듈형 모놀리스와 격리 실행 plane

## 먼저 읽기

- **무엇을 정했나요?** 서버의 핵심 기능은 한 코드베이스 안에서 모듈로 나누고, API와 worker는
  별도 process로 실행합니다. 의존성과 위험이 큰 plugin·solver 계산은 별도 runner에 맡깁니다.
- **왜 중요한가요?** revision, provenance, review처럼 함께 저장돼야 하는 정보는 한 transaction으로
  일관되게 처리하면서도, 오래 걸리거나 위험한 계산이 API에 영향을 주지 않게 할 수 있습니다.
- **언제 읽나요?** 새 backend module을 만들거나 service를 분리하려 할 때, 또는 plugin·solver 코드를
  API process 안에서 실행해도 되는지 판단할 때 읽습니다.
- **용어를 쉽게 말하면:** `모듈형 모놀리스`는 하나의 애플리케이션을 책임별 내부 모듈로 나눈
  구조입니다. `authoritative`는 해당 정보의 공식 원본이라는 뜻이고, `runner`는 계산을 격리해
  실행하는 별도 process나 container입니다.
- **상태 표기는?** `Accepted`는 이 결정을 채택했다는 뜻입니다. 관련 기능이 모두 구현됐거나 현재
  환경에서 검증을 마쳤다는 뜻은 아닙니다.

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

