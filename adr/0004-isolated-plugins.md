# ADR-004: Plugin의 out-of-process 실행

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

