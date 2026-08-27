# 스키마 기반 통합 요구사항 추적표

상태: `authoritative`
현재 구현 기준선: `main@5d7f65a`
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
| P1 Catalog Schema Bundle | #204, #207, #208 완료; #246 Task 1A 완료; #341 | 부분 | #246 Task 1A는 PR #250, main `b9a82e9`에서 source-v2 어댑터, 객체형 `x-curve`, business-key 승격·참조 해석을 병합했다. #341은 변경하지 않은 기준 파일 묶음을 plan → atomic apply → exact-source export → no-op 재적용한다. 원본은 연결 6개를 선언하지만 승인 범위는 직접 연결 5개다. 원본 `dma_to_elastoplasticity`는 변경하지 않고 증거로 보존하며 `CMP-SCHEMA-SOURCE-0029`로 제외한다. 실제 JSON 데이터 등록은 #246 Task 1B다. |
| P2 Curve 채널·편차 | #206 완료; #246 Task 1A 완료; #341 회귀 | 구현 | 공통 채널·편차 계약과 source-v2 객체형 `x-curve` 해석·원본 위치 보존이 구현됐다. #341은 #209의 explicit-legacy `Hz` 경계를 공통 registry로 옮기지 않고 그대로 재사용해 변경하지 않은 source-v2 전체 apply를 통과시킨다. |
| P3 단위·Unit Profile | #205, #209 Hz 완료; #341, #214 | 부분 | 공통 계약 `1.1.0`은 기존 8개 dimension·ID·alias와 exact Unit Profile revision trace를 보존하고 explicit `speed`의 `m/s`·`mm/s`·`mm/min`, density의 `tonne/mm3`를 추가한다. DMA frequency의 `Hz`는 #209 explicit-legacy 계약을 유지한다. source profile의 범위 밖 `mass: tonne`는 원본 Artifact에 보존하고 위치가 있는 경고와 함께 공통-unit projection에서 제외하며 변환을 추론하지 않는다. 추가 solver profile과 관리 UI는 #214 범위다. |
| P4 DMA·FLD | #209 완료; #246 Task 2B, #195 또는 이후 승인 이슈 | 부분/보류 | #209 PR #248, main `3e642e8`에서 `dma_frequency_temperature_sweep`와 `forming_limit` governed import, Hz, canonical lineage를 완료했다. `dma_strain_sweep` 전용 처리는 실제 운용 자료와 승인 요구가 없어 #246 Task 2B에서 명시적 미지원으로 보류한다. master curve·Prony·LinearViscoelastic IR production 확장은 #195 또는 이후 승인 이슈가 소유하며 #209나 #246의 구현 완료로 간주하지 않는다. |
| P5 분포·대표곡선 | #210 완료; #211, #246 Task 3 | 부분 | scalar 분포 피팅 외에도 common-grid piecewise-linear/no-extrapolation alignment, append-only 포함·제외 판단과 exact Dataset/Test Run lineage, pointwise mean/95% CI immutable Artifact, calibration input scope exact pinning이 구현돼 있다. #211 잔여는 pointwise p05/p95 representative revision, 그 revision의 review/approval/invalidation, 승인된 representative exact revision의 Fit 선택 연결이다. 범용 scalar 확장은 완료로 주장하지 않으며 #246 Task 3에서 소유권을 재대조한다. |
| P6 Template·solver·다단위 | #213, #214 | 미구현 | governed Template, LS-DYNA MAT_024, 추가 solver unit system과 관리 UI가 남아 있다. |
| P7 승인·역할 | #160 완료; #246 Task 4 | 부분/결정 | Record/Test Data 검토·게시·복구는 구현됐다. 역할 preset 변경과 `data_manager`는 자동 구현하지 않고 제품 결정을 기록한다. |
| P8 SPA OIDC | #215 | 미구현 | Authorization Code+PKCE login/callback/token lifecycle과 demo identity 운영 guard가 남아 있다. |
| P9 Audit wiring | #216 | 미구현 | 기반 hash chain은 있으나 제품 command의 전면 event coverage가 남아 있다. |
| P10 Toe·선택적 DE | #212 완료; #246 Task 4 | 부분/결정 | 명시 구간 OLS zero-intercept 방식은 구현됐다. `offset_shift`와 선택적 DE는 근거를 검토해 구현·보류·제외를 결정한다. |

## G1~G24 대조

| 갭 | 판정 | 현재 처리 또는 남은 결정 |
| --- | --- | --- |
| G1 bundle import/export | 부분 | #246 Task 1A가 PR #250에서 source-v2 다중 파일/ZIP 입력과 적용된 원본 Artifact 바이트 export를 병합했다. #341은 변경하지 않은 기준 파일 묶음의 plan/apply/export/no-op을 통과시키며 원본 연결 6개 중 승인된 5개만 제품 Link로 투영한다. 실제 JSON 데이터 등록은 Task 1B에 남는다. |
| G2 `x-*` 해석 | 구현 | #246 Task 1A가 source-v2 확장을 결정적으로 해석하고 원본 위치·파일 해시를 보존한다. `dma_to_elastoplasticity`는 승인되지 않은 원본 의미이므로 `CMP-SCHEMA-SOURCE-0029` 증거 경고로 남기고 제품 관계로 만들지 않는다. |
| G3 curve metadata | 구현 | #206 공통 계약과 #246 Task 1A source-v2 bundle 연결을 구현했다. |
| G4 business key/pointer | 구현 | #246 Task 1A가 source-v2 business key 승격, 정확한 개정 고정, 각 Attribute의 원본 JSON pointer·파일 해시 저장과 원본 Artifact export를 병합했다. #341의 변경하지 않은 전체 적용과 exact-source export도 같은 위치·해시를 유지한다. 원본 DMA 참조는 증거 필드로 보존하되 금지된 제품 관계로 승격하지 않는다. |
| G5 단위 | 부분 | 공통 기반과 #209의 explicit-legacy `Hz`를 보존한다. #341은 additive common-unit `1.1.0`으로 `speed`의 `m/s`·`mm/s`·`mm/min`과 `mass_per_volume`의 `tonne/mm3`를 닫고 변경하지 않은 source-v2를 적용한다. 추가 solver profile은 #214 범위다. |
| G6 DMA/FLD | 부분/보류 | #209가 frequency-temperature DMA와 FLD governed import 및 exact lineage를 완료했다. `dma_strain_sweep` 전용 처리는 #246 Task 2B에서 명시적 미지원으로 보류하고, master curve·Prony·LinearViscoelastic IR production 확장은 #195 또는 이후 승인 이슈가 소유한다. |
| G7 publication validation | 구현 방식 변경 | #207이 원본의 부분 성공보다 강한 atomic apply/read-back을 구현했다. |
| G8 `non_production` | 보류 | production 근거 전까지 유지한다. |
| G9 SPA login | 미구현 | #215. |
| G10 demo identity guard | 미구현 | #215와 운영 gate. |
| G11 upload review | 구현 | #160. |
| G12 role preset | 결정 필요 | #246 Task 4에서 기존 preset 유지 또는 변경을 명시적으로 닫는다. |
| G13 audit wiring | 미구현 | #216. |
| G14 approval→publication/recovery | 구현 | #160. |
| G15 multistage approval | 결정 필요 | #246 Task 4. |
| G16 frontend role gating | 부분 | #246에서 현재 역할 matrix를 재확인한다. |
| G17 toe compensation | 부분 | #212의 한 방식 완료; 추가 방식은 #246 Task 4 결정. |
| G18 Differential Evolution | 결정 필요 | #246 Task 4. |
| G19 distribution/envelope | 부분 | #210과 기존 alignment·outlier·pointwise mean/95% CI·exact scope pinning 기반은 완료했다. #211은 p05/p95 representative revision, representative review/approval/invalidation과 approved representative exact revision→Fit selection만 추가하며, #246 Task 3은 원본 대비 소유권을 재대조한다. |
| G20 template/solver 확장 | 미구현 | #213/#214. |
| G21 multi-unit export | 부분 | #205 기반 완료, #214 solver 확장 예정. |
| G22 plugin wiring | 결정 필요 | #246 Task 4와 #213 sandbox 결정 이후 판단한다. |
| G23 비동기 계산 실행 | 결정 필요 | #246 Task 4에서 이번 계획 포함 여부를 닫는다. |
| G24 추가 경화식 | 결정 필요 | #246 Task 4에서 별도 모델 요구 여부를 닫는다. |

## 실행 계획

### 1. #209 — DMA·FLD import 완료

#209는 PR #248, main `3e642e8c3e96e95dd7d10b19d87e18af53db9e7c`에서
`dma_frequency_temperature_sweep`와 `forming_limit` governed import, Hz, source-to-canonical
lineage를 완료했다. `dma_strain_sweep`, source-v2 전체 bundle 호환, #209 수락 조건 밖의 단위와
DMA→master curve/Prony→IR production 확장은 #209 완료에 포함하지 않는다.

### 2. #341 — #246 Task 2 공통 단위 보완

Task 1A source-v2 bundle adapter와 business-key/reference E2E는 PR #250, main `b9a82e9`에서
완료했다. #341은 #246의 native Sub-issue로 Task 2의 `mm/min`·`tonne/mm3`와 변경하지 않은
source-v2 전체 apply/export/no-op을 소유한다. 그 다음 #246은 Task 1B 실제 JSON 데이터 등록,
Task 2B DMA/점탄성 경계, Task 3 후속 이슈 정합과 Task 4 보류 항목 disposition을 순차 처리한다. #276은 이 과정에서 드러난
Simulation Data→Modeling/solver-card 후보 후속이지만 native parent와 실행 순서는 승인되지 않았고
현재 #117 순서를 바꾸지 않는다.

각 Task는 별도 branch/PR로 처리하며 이미 구현된 기능을 재작성하지 않는다. #246이 닫힐 때
P1~P10/G1~G24 각 행은 구현 완료, 기존 Issue 소유, 제품 보류 또는 제외 중 하나를 가져야 한다.

### 3. #211 — #246 뒤의 좁은 대표곡선 잔여

#211은 existing common-grid piecewise-linear/no-extrapolation alignment, append-only inclusion/exclusion
assessment와 exact Dataset/Test Run lineage, pointwise mean/95% CI immutable Artifact, calibration input
scope exact pinning을 재사용하고 회귀검증한다. 새 구현은 pointwise p05/p95 representative revision,
representative review/approval/invalidation과 승인된 representative exact revision을 Fit에서 명시적으로
선택하는 연결로 제한한다.
