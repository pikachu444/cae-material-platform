# 스키마 기반 통합 요구사항 추적표

상태: `authoritative`
현재 구현 기준선: `main@1dcd4c90`
원본 요구 기준선: `main@31f9a3f`
원본 패키지: [`schema-driven-integration-source`](../00-research/schema-driven-integration-source/README.md)
보완 추적: [#246](https://github.com/pikachu444/cae-material-platform/issues/246)

## 판정 규칙

- 원본 P1~P10과 G1~G24는 요구와 설계 배경을 보존한다.
- 현재 코드와 `IMPLEMENTATION_STATUS.md`는 구현된 동작의 근거다.
- delivery backlog와 GitHub Issue/PR은 실행 단위를 소유하지만, 원본보다 범위가 좁아졌다면 그
  차이를 이 문서와 Issue에 명시해야 한다.
- `closed` Issue는 해당 Issue 수락 조건의 완료를 뜻한다. 원본 요구 전체의 완료를 자동으로
  뜻하지 않는다.

## P1~P10 대조

| 패킷 | 현재 연결 | 판정 | 원본 대비 남은 차이 |
| --- | --- | --- | --- |
| P1 Catalog Schema Bundle | #204, #207, #208 완료; #246 Task 1A·Task 1B; #341 | 구현 | #246 Task 1A는 PR #250, main `b9a82e9`에서 source-v2 어댑터, 객체형 `x-curve`, business-key 승격·참조 해석을 병합했다. Task 1B는 PR #353, main `fa4e451`에서 서버가 실제 JSON의 installed exact format revision을 resolve하는 strict preview, 파일별 진단, 원자 DRAFT batch와 exact source JSON/CSV read-back을 완료했다. #341은 변경하지 않은 기준 파일 묶음을 plan → atomic apply → exact-source export → no-op 재적용한다. 원본은 연결 6개를 선언하지만 승인 범위는 직접 연결 5개다. 원본의 상충하는 `dma_to_elastoplasticity` 항목은 source evidence로만 보존하고 `CMP-SCHEMA-SOURCE-0029`로 제외한다. |
| P2 Curve 채널·편차 | #206 완료; #246 Task 1A 완료; #341 회귀 | 구현 | 공통 채널·편차 계약과 source-v2 객체형 `x-curve` 해석·원본 위치 보존이 구현됐다. #341은 #209의 explicit-legacy `Hz` 경계를 공통 registry로 옮기지 않고 그대로 재사용해 변경하지 않은 source-v2 전체 apply를 통과시킨다. |
| P3 단위·Unit Profile | #205, #209 Hz 완료; #341, #214 | 부분 | 공통 계약 `1.1.0`은 기존 8개 dimension·ID·alias와 exact Unit Profile revision trace를 보존하고 explicit `speed`의 `m/s`·`mm/s`·`mm/min`, density의 `tonne/mm3`를 추가한다. DMA frequency의 `Hz`는 #209 explicit-legacy 계약을 유지한다. source profile의 범위 밖 `mass: tonne`는 원본 Artifact에 보존하고 위치가 있는 경고와 함께 공통-unit projection에서 제외하며 변환을 추론하지 않는다. 추가 solver profile과 관리 UI는 #214 범위다. |
| P4 DMA·FLD | #209 완료; #343 PR #356 지원 경계 확정; #195 production 점탄성 | 부분/보류 | #209 PR #248, main `3e642e8`에서 `dma_frequency_temperature_sweep`와 `forming_limit` governed import, Hz, canonical lineage를 완료했다. #343 PR #356은 실제 운용 자료와 승인 요구가 없는 `dma_strain_sweep`을 구현하지 않고, 현재 계약 열거값과 Modeling 선택지에서 제외된 명시적 미지원으로 확정한다. source-v2 DMA 형식이 `Strain Sweep` 값을 허용하는 것은 Record 검증·보존 범위이며 canonical 처리 지원을 뜻하지 않는다. master curve·Prony·LinearViscoelastic IR production 확장은 #195가 소유하고 별도 production 입력·수치 검증·UI 승인을 거친다. |
| P5 분포·대표곡선 | #210 완료; #211 | 부분 | scalar 분포 피팅 외에도 common-grid piecewise-linear/no-extrapolation alignment, append-only 포함·제외 판단과 exact Dataset/Test Run lineage, pointwise mean/95% CI immutable Artifact, calibration input scope exact pinning이 구현돼 있다. #211 잔여는 pointwise p05/p95 representative revision, 그 revision의 review/approval/invalidation, 승인된 representative exact revision의 Fit 선택 연결이다. 범용 scalar 확장은 완료로 주장하지 않는다. |
| P6 Template·solver·다단위 | #213, #214 | 미구현 | governed Template, LS-DYNA MAT_024, 추가 solver unit system과 관리 UI가 남아 있다. |
| P7 승인·역할 | #160 완료; #215 기존 역할 유지 | 구현/보류 | Record/Test Data 검토·게시·복구는 구현됐다. 제품 역할은 User/Reviewer/Administrator를 유지하고 #215가 OIDC claim을 이 역할에 연결한다. 독립 책임·감사·수명주기 근거가 승인되기 전에는 `data_manager` 역할을 추가하지 않는다. |
| P8 SPA OIDC | #215 | 미구현 | Authorization Code+PKCE login/callback/token lifecycle과 demo identity 운영 guard가 남아 있다. |
| P9 Audit wiring | #216 | 미구현 | 기반 hash chain은 있으나 제품 command의 전면 event coverage가 남아 있다. |
| P10 Toe·선택적 DE | #212 완료; 추가 방식 보류 | 구현/보류 | 명시 구간 OLS zero-intercept 방식은 구현됐다. `offset_shift`는 승인된 시험 절차와 수치 fixture가 생길 때, Differential Evolution은 현재 bounded multistart의 재현 가능한 실패와 결정성·시간 이점이 증명될 때만 별도 이슈로 검토한다. |

## G1~G24 대조

| 갭 | 판정 | 현재 처리 또는 남은 결정 |
| --- | --- | --- |
| G1 bundle import/export | 구현 방식 변경 | #246 Task 1A가 PR #250에서 source-v2 다중 파일/ZIP 입력과 적용된 원본 Artifact 바이트 export를 병합했고, Task 1B는 PR #353에서 실제 JSON component의 canonical STORED package 검증, exact source Artifact와 deterministic source-aware CSV read-back을 완료했다. Import records에는 별도 File/Record/Format selector가 없고 서버가 exact format을 resolve한다. #341은 변경하지 않은 기준 파일 묶음의 plan/apply/export/no-op을 통과시키며 원본 연결 6개 중 승인된 5개만 제품 Link로 투영한다. |
| G2 `x-*` 해석 | 구현 | #246 Task 1A가 source-v2 확장을 결정적으로 해석하고 원본 위치·파일 해시를 보존한다. `dma_to_elastoplasticity`는 승인되지 않은 원본 의미이므로 `CMP-SCHEMA-SOURCE-0029` 증거 경고로 남기고 제품 관계로 만들지 않는다. |
| G3 curve metadata | 구현 | #206 공통 계약과 #246 Task 1A source-v2 bundle 연결을 구현했다. |
| G4 business key/pointer | 구현 | #246 Task 1A가 source-v2 business key 승격, 정확한 개정 고정, 각 Attribute의 원본 JSON pointer·파일 해시 저장과 원본 Artifact export를 병합했다. Task 1B는 strict wrapper/binding validation, exact reference pinning, durable source pointer/unit/curve evidence와 deterministic downloads를 같은 immutable Record revision에 고정했다. #341의 변경하지 않은 전체 적용과 exact-source export도 같은 위치·해시를 유지한다. 상충하는 원본 DMA 참조는 증거 필드로 보존하되 제품 관계로 승격하지 않는다. |
| G5 단위 | 부분 | 공통 기반과 #209의 explicit-legacy `Hz`를 보존한다. #341은 additive common-unit `1.1.0`으로 `speed`의 `m/s`·`mm/s`·`mm/min`과 `mass_per_volume`의 `tonne/mm3`를 닫고 변경하지 않은 source-v2를 적용한다. 추가 solver profile은 #214 범위다. |
| G6 DMA/FLD | 부분/보류 | #209가 frequency-temperature DMA와 FLD governed import 및 exact lineage를 완료했다. #343 PR #356은 `dma_strain_sweep`을 현재 계약·UI에서 명시적 미지원으로 확정한다. 동적 source-v2 Record의 형식 값과 canonical 처리 capability를 혼동하지 않는다. master curve·Prony·LinearViscoelastic IR production 확장은 #195가 소유한다. |
| G7 publication validation | 구현 방식 변경 | #207이 원본의 부분 성공보다 강한 atomic apply/read-back을 구현했다. |
| G8 `non_production` | 보류 | #195/#196의 family별 production 입력 의미, 독립 수치 acceptance와 실제 흐름 승인이 끝날 때까지 유지한다. |
| G9 SPA login | 미구현 | #215. |
| G10 demo identity guard | 미구현 | #215와 운영 gate. |
| G11 upload review | 구현 | #160. |
| G12 role preset | 기존 역할 유지 | User/Reviewer/Administrator를 유지한다. `data_manager`는 별도 조직·IAM 근거가 승인될 때만 새 이슈로 검토한다. |
| G13 audit wiring | 미구현 | #216. |
| G14 approval→publication/recovery | 구현 | #160. |
| G15 multistage approval | 보류 | #160의 단일 review lifecycle을 유지한다. 규제·전자서명·복수 승인자 요구가 승인되면 별도 governance 이슈로 연다. |
| G16 frontend role gating | 부분 | 서버 권한은 유지되고 SPA login과 기존 역할별 action/recovery 정합은 #215가 소유한다. |
| G17 toe compensation | 구현/보류 | #212의 명시 구간 OLS zero-intercept 방식은 완료했다. `offset_shift`는 승인된 절차·fixture 전에는 추가하지 않는다. |
| G18 Differential Evolution | 보류 | bounded multistart의 재현 가능한 실패와 DE의 결정성·시간·성공률 이점이 입증될 때만 별도 optimizer 이슈로 검토한다. |
| G19 distribution/envelope | 부분 | #210과 기존 alignment·outlier·pointwise mean/95% CI·exact scope pinning 기반은 완료했다. #211은 p05/p95 representative revision, representative review/approval/invalidation과 approved representative exact revision→Fit selection만 추가한다. |
| G20 template/solver 확장 | 미구현 | #213/#214. |
| G21 multi-unit export | 부분 | #205 기반 완료, #214 solver 확장 예정. |
| G22 plugin wiring | 보류 | #213은 안전한 Template renderer 경계만 소유하고 generic plugin wiring은 추가하지 않는다. 실제 격리 배포 대상과 운영 수명주기가 승인될 때 별도 plugin 이슈로 연다. |
| G23 비동기 계산 실행 | 보류 | 현재 계산 경계를 유지한다. 실제 응답 시간·중단 복구·내구성 요구가 동기 실행의 실패를 입증할 때 bounded job 이슈로 연다. |
| G24 추가 경화식 | 보류 | 승인된 재료 family·solver target·수치 reference가 특정 추가 식을 요구할 때 별도 모델 이슈로 연다. Swift의 부분 커버만으로 production 모델을 추론하지 않는다. |

## 실행 계획

### 1. #209 — DMA·FLD import 완료

#209는 PR #248, main `3e642e8c3e96e95dd7d10b19d87e18af53db9e7c`에서
`dma_frequency_temperature_sweep`와 `forming_limit` governed import, Hz, source-to-canonical
lineage를 완료했다. `dma_strain_sweep`, source-v2 전체 bundle 호환, #209 수락 조건 밖의 단위와
DMA→master curve/Prony→IR production 확장은 #209 완료에 포함하지 않는다.

### 2. #341 — #246 Task 2 공통 단위 보완

Task 1A source-v2 bundle adapter와 business-key/reference E2E는 PR #250, main `b9a82e9`에서
완료했다. #341은 Task 2의 `mm/min`·`tonne/mm3`와 변경하지 않은 source-v2 전체
apply/export/no-op을 완료했고, Task 1B 실제 JSON 데이터 등록은 PR #353, main `fa4e451`에서
완료했다. #343 Task 2B는 PR #356, #344 Task 3+4는 PR #357에서 완료했다. #276은 이 과정에서 드러난
Simulation Data→Modeling/solver-card 후보 후속이지만 native parent와 실행 순서는 승인되지 않았다.

각 Task는 별도 branch/PR로 처리하며 이미 구현된 기능을 재작성하지 않는다. #246이 닫힐 때
P1~P10/G1~G24 각 행은 구현 완료, 기존 Issue 소유, 제품 보류 또는 제외 중 하나를 가져야 한다.

### 3. #343 — DMA 지원 경계와 점탄성 소유권 (PR #356)

#209가 구현한 governed import와 Modeling 입력은 frequency-temperature DMA만 지원한다.
`dma_strain_sweep`은 현재 계약 열거값과 사용자 선택지에 없으므로 추측해 변환하지 않고 명시적으로
지원하지 않는다. source-v2 `dma-test` 형식의 `Test Type` 값은 동적 Record로 검증·보존할 수 있지만,
그 값만으로 canonical 처리·master curve·Prony·LinearViscoelastic IR 경로를 만들지 않는다.
production 점탄성 입력 의미, 계산 정책, 수치 검증과 사용자 흐름은 #195가 소유한다. #344까지 완료해
#246을 닫았으며 현재 제품 작업은 #195다.

### 4. #344 — 후속 소유권과 보류 결정 (PR #357, main `1dcd4c90`)

#211은 대표곡선 잔여, #213/#214는 Template·solver·다중 단위, #215는 SPA OIDC와 기존 역할 정합,
#216은 구현된 제품 command의 audit coverage를 각각 소유한다. `data_manager`, `offset_shift`,
Differential Evolution, 다단계 승인, generic plugin wiring, 새 비동기 계산 구조와 추가 경화식은
위 G행의 재개 근거가 생길 때까지 보류하며 이번 순서에 새 이슈를 만들지 않는다. 점탄성 production
입력·수치 acceptance·사용자 흐름은 #195가 소유한다. #246은 이 결정과 함께 완료했으며 #195를
현재 제품 작업으로 진행한다.

### 5. #211 — #195 뒤의 좁은 대표곡선 잔여

#211은 existing common-grid piecewise-linear/no-extrapolation alignment, append-only inclusion/exclusion
assessment와 exact Dataset/Test Run lineage, pointwise mean/95% CI immutable Artifact, calibration input
scope exact pinning을 재사용하고 회귀검증한다. 새 구현은 pointwise p05/p95 representative revision,
representative review/approval/invalidation과 승인된 representative exact revision을 Fit에서 명시적으로
선택하는 연결로 제한한다.
