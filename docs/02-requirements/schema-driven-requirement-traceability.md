# 스키마 기반 통합 요구사항 추적표

상태: `authoritative`
현재 구현 기준선: `main@6bff4c7`
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
| P1 Catalog Schema Bundle | #204, #207, #208 완료; #246 Task 1 | 부분 | #246 Task 1 후보가 source-v2 어댑터, 객체형 `x-curve`, business-key 승격·참조 해석과 원본 왕복을 구현했다. 원본은 연결 6개를 선언하지만 승인 범위는 직접 연결 5개다. 원본 `dma_to_elastoplasticity`는 변경하지 않고 증거로 보존하며 `CMP-SCHEMA-SOURCE-0029`로 제외한다. 병합 및 Task 2 단위 지원 전에는 부분 상태를 유지한다. |
| P2 Curve 채널·편차 | #206 완료; #246 Task 1 | 부분 | 공통 채널·편차 계약은 구현됐으나 source-v2의 객체형 `x-curve`를 bundle import가 해석하지 못한다. |
| P3 단위·Unit Profile | #205 완료; #246 Task 2, #214 | 부분 | 공통 8개 dimension과 revision trace는 구현됐다. source-v2에 필요한 `Hz`, `mm/min`, `tonne/mm3`와 추가 solver profile은 없다. |
| P4 DMA·FLD | #209; #246 | 미구현 | 진행 중인 #209는 기존 수락 범위인 `dma_frequency_temperature_sweep`와 `forming_limit` governed import를 소유한다. `dma_strain_sweep`, source-v2 전체 호환성과 DMA→master curve/Prony→IR 연결의 추가 범위는 #209에 끼워 넣지 않고 #246에서 닫는다. |
| P5 분포·대표곡선 | #210 완료; #211, #246 Task 3 | 부분 | 분포 피팅은 특정 processed scalar 중심이다. 범용 scalar 선택, p05/p95 envelope와 승인된 Fit input은 남아 있다. |
| P6 Template·solver·다단위 | #213, #214 | 미구현 | governed Template, LS-DYNA MAT_024, 추가 solver unit system과 관리 UI가 남아 있다. |
| P7 승인·역할 | #160 완료; #246 Task 4 | 부분/결정 | Record/Test Data 검토·게시·복구는 구현됐다. 역할 preset 변경과 `data_manager`는 자동 구현하지 않고 제품 결정을 기록한다. |
| P8 SPA OIDC | #215 | 미구현 | Authorization Code+PKCE login/callback/token lifecycle과 demo identity 운영 guard가 남아 있다. |
| P9 Audit wiring | #216 | 미구현 | 기반 hash chain은 있으나 제품 command의 전면 event coverage가 남아 있다. |
| P10 Toe·선택적 DE | #212 완료; #246 Task 4 | 부분/결정 | 명시 구간 OLS zero-intercept 방식은 구현됐다. `offset_shift`와 선택적 DE는 근거를 검토해 구현·보류·제외를 결정한다. |

## G1~G24 대조

| 갭 | 판정 | 현재 처리 또는 남은 결정 |
| --- | --- | --- |
| G1 bundle import/export | 부분 | #246 Task 1 후보가 source-v2 다중 파일/ZIP 입력과 원본 바이트 export를 구현했다. 원본 연결 6개 중 승인된 5개만 제품 Link로 투영하며, 변경하지 않은 원본 적용은 Task 2의 단위 오류 10건이 해소될 때까지 차단된다. |
| G2 `x-*` 해석 | 부분 | #246 Task 1 후보가 현재 source-v2 확장을 결정적으로 해석하고 원본 위치·파일 해시를 보존한다. `dma_to_elastoplasticity`는 승인되지 않은 원본 의미이므로 `CMP-SCHEMA-SOURCE-0029` 증거 경고로 남기고 제품 관계로 만들지 않는다. 병합 전까지 부분 상태다. |
| G3 curve metadata | 구현 | #206 공통 계약 구현. source bundle 연결은 #246 Task 1. |
| G4 business key/pointer | 부분 | #246 Task 1 후보가 source-v2 business key 승격, 정확한 개정 고정, 원본 JSON pointer·파일 해시 왕복을 검증했다. 원본 DMA 참조는 증거 필드로 보존하되 금지된 제품 관계로 승격하지 않는다. 병합 전까지 부분 상태다. |
| G5 단위 | 부분 | 공통 기반은 구현됐으나 변경하지 않은 source-v2는 필수 단위 10곳에서 정확히 차단된다. `Hz`, `mm/min`, `tonne/mm3`와 추가 solver profile은 #246 Task 2가 소유한다. |
| G6 DMA/FLD | 미구현/분리 | #209는 기존 frequency-temperature DMA와 FLD import 범위를 처리한다. 그 밖의 원본 P4 차이는 #246이 소유한다. |
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
| G19 distribution/envelope | 부분 | #210 완료, #211과 #246 Task 3. |
| G20 template/solver 확장 | 미구현 | #213/#214. |
| G21 multi-unit export | 부분 | #205 기반 완료, #214 solver 확장 예정. |
| G22 plugin wiring | 결정 필요 | #246 Task 4와 #213 sandbox 결정 이후 판단한다. |
| G23 비동기 계산 실행 | 결정 필요 | #246 Task 4에서 이번 계획 포함 여부를 닫는다. |
| G24 추가 경화식 | 결정 필요 | #246 Task 4에서 별도 모델 요구 여부를 닫는다. |

## 실행 계획

### 1. #209 — DMA·FLD import

#209 구현 브랜치는 이 문서가 병합된 최신 `main`을 반영한 뒤 source-v2의 DMA/FLD schema를
직접 읽는다. 구현 범위는 기존 Issue 본문과 수락 조건에 적힌 frequency-temperature DMA와 FLD
governed import로 유지한다. 해당 두 profile의 검증·단위 처리·source-to-canonical lineage에 직접
필요한 작업만 #209에서 수행한다.

`dma_strain_sweep`, source-v2 전체 bundle 호환, #209 수락 조건 밖의 단위 확장과
DMA→master curve/Prony→IR 연결은 #209에 추가하지 않는다. 원본과 현재 Issue 사이의 이 차이는
#246에서 후속 처리한다.

### 2. #246 — 원본 정합 보완

#209 병합 직후 #211 전에 다음 Task를 순차 처리한다.

1. source-v2 bundle adapter와 business-key/reference E2E.
2. source-v2에 실제 필요한 공통 단위 확장.
3. #211/#213~#216 수락 조건을 원본과 재대조해 중복 없이 보완.
4. Toe 추가 방식, DE, 역할 preset, 다단계 승인 등 보류 항목의 명시적 disposition.

각 Task는 별도 branch/PR로 처리하며 이미 구현된 기능을 재작성하지 않는다. #246이 닫힐 때
P1~P10/G1~G24 각 행은 구현 완료, 기존 Issue 소유, 제품 보류 또는 제외 중 하나를 가져야 한다.
