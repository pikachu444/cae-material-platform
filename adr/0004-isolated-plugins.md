# ADR-004: Plugin의 out-of-process 실행

## 먼저 읽기

- **무엇을 정했나요?** core는 plugin의 설명과 입출력 schema만 알고, 실제 parser·model·exporter는
  별도 process나 container에서 실행합니다. plugin에는 database 자격증명을 주지 않습니다.
- **왜 중요한가요?** plugin마다 다른 library와 자원 요구가 API와 충돌하지 않으며, 문제가 생겨도
  영향 범위를 격리하고 같은 실행 조건을 다시 만들기 쉽습니다.
- **언제 읽나요?** 새 parser, 수치 model, solver exporter를 추가하거나 plugin이 database나 API
  내부 객체에 직접 접근하게 만들려 할 때 읽습니다.
- **용어를 쉽게 말하면:** `out-of-process`는 핵심 서버와 다른 process에서 실행한다는 뜻입니다.
  `plugin manifest`는 plugin의 버전·입출력·package 정보를 적은 명세이고, `scoped artifact I/O`는
  허가된 Artifact만 입력으로 읽고 결과로 쓸 수 있다는 뜻입니다.
- **상태 표기는?** `Accepted`는 이 결정을 채택했다는 뜻입니다. 관련 기능이 모두 구현됐거나 현재
  환경에서 검증을 마쳤다는 뜻은 아닙니다.

- 상태: Accepted
- 기준일: 2026-07-11

## Context

시험 parser, numeric model, solver exporter는 서로 다른 dependency와 자원, 신뢰 수준을 가진다. API에 직접 import하면 dependency 충돌과 재현성·보안 문제가 생긴다.

## Decision

Core는 plugin manifest와 schema만 등록한다. 실행은 immutable Job Spec과 Result Manifest로 별도 process/container runner에서 수행한다. Plugin은 DB credential을 받지 않고 scoped artifact I/O만 사용한다.

## Consequences

- package digest, dependency, resource, network policy를 고정할 수 있다.
- IPC/artifact contract와 runner 운영이 추가된다.
- calibration loop 성능을 위해 Material Model과 Calibrator를 한 runner에 co-locate할 수 있지만 논리 interface와 digest는 분리한다.

## Revisit trigger

없음에 가깝다. 개발 편의를 위한 local subprocess adapter는 허용하지만 production API in-process loading은 허용하지 않는다.

