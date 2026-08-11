# Issue #184 — high-DPI global production implementation

## Disposition

- 상태: **`IMPLEMENTATION_COMPLETE; EVIDENCE_CARRYOVER_TRACKED_IN_223`**
- 기준선: `main@36e8312fa85253ad8fee88f63a3a4bf096d92a9c`
- 작업 branch: `agent/issue-184-high-dpi-global-implementation`
- PR: [#231](https://github.com/pikachu444/cae-material-platform/pull/231)
- merge commit: `ab27e3947817cefa997e49c5dc1d237ec5035adb`
- capture commit: `97f850acf454a8fb6d8caeb8cf5e9ccb5d413a16`
- 승인 정책: **P2**, 기본/reset `Standard`, 사용자 선택 `Compact | Standard | Large`
- 제품 소유자 disposition: **2026-08-11 #184 완료; fixture 누락은 미해결 상태로 #223 인계**
- 실제 Windows 4K 100%·150%·200% 물리 가독성: **`DEFERRED_TO_223`**

Production 코드와 현재 만들 수 있는 route/state의 자동·시각 증거는 준비됐다. 그러나 canonical
append-only fixture에서 exact Material datasheet/card projection이 `CMP-CATALOG-0015`로 차단되어
density별 90개 중 10개 원본을 다시 만들지 못했다. 독립 읽기 전용 감수는 사용 가능한 334개 원본을
모두 실제 해상도로 확인한 뒤 이 30개 coverage 누락만 blocking finding으로 남겼다. 제품 소유자는
2026-08-11에 이 누락과 실제 Windows 4K 판정 유보를 보고받은 뒤 구현 PR을 merge하고 #184를
완료하도록 결정했다. 이 disposition은 누락 증거를 통과로 바꾸지 않는다. 정확한 30개 원본,
structured manifest 완성, 독립 원본 재감수와 `DEFERRED_TO_223` 물리 판정은 #223에 그대로 인계했다.
#117은 열린 상태를 유지하며 다음 미완료 단위 #204는 별도 세션에서 시작한다.

## 시작 시 구현 분류

| 분류 | `main@36e8312` 상태 |
| --- | --- |
| 완료 | #161의 full-shell 공통 token/pane 기반, #221의 읽기 전용 후보 prototype·measurement·P2 승인 기록 |
| 부분 구현 | Materials/Modeling pane persistence와 일부 넓은 화면 layout, Activity bounded table, graph의 기존 `ResizeObserver` 기반 재배치 |
| 미구현 | production density provider·첫 paint bootstrap·설정 UI·검증/복구, 세 density의 공통 production token, Modeling navigator reset, allocation 기반 context overlay, Administration Database/Records semantic three-pane, Export preview 공통 최소 높이, 모든 route/state의 Q-20 matrix |

현재 branch는 위 미구현 production 범위를 구현했다. backend, database, authorization, revision,
material-model 기능과 #221 이미지·측정·승인 기록은 변경하지 않았다.

## Primary user journey와 bounded acceptance

1. 사용자는 같은 canonical synthetic data와 exact revision으로 Materials를 연다.
2. 우측 사용자 메뉴에서 **Display density**를 열어 Compact, Standard 또는 Large를 키보드나 pointer로
   선택한다. shell과 현재 작업영역이 같은 공통 token 계약으로 즉시 재배치된다.
3. Materials → Modeling Data/Process/Fit/Export → Activity → Administration을 이동한다. 선택 density와
   pane 배치는 route 이동과 reload 뒤에도 복원된다.
4. Navigator/Context를 resize·collapse·reset하고 그래프의 frame, SVG viewBox, axis, legend, label과
   hit region이 실제 container에 맞춰 다시 계산되는지 확인한다. Context를 명시적으로 열었으나 실제
   배정 폭이 1px 미만일 때만 bounded overlay를 사용한다.
5. **Reset display density**는 density만 Standard로 돌리고 pane/column 배치는 보존한다. 손상되거나
   과거 형식인 저장값은 첫 shell paint 전에 Standard로 복구한다.
6. raw bytes, exact revision, selected model, review request, solver card와 server state는 바꾸지 않는다.
   preference는 active user/workspace를 구분하는 browser-local product-wide 값이며 backend와 다른
   장비에 동기화하지 않는다.
7. 다섯 CSS viewport, 세 density, browser zoom 200%, 정상·위험 상태에서 page horizontal overflow,
   clipping, unreachable action, graph mismatch가 0이고 원본·direct crop·structured manifest가 완전해야
   acceptance다. 실제 4K 물리 가독성만 #223으로 이관한다.

Forbidden shortcuts는 route별 4K CSS/private density, CSS `zoom`, blanket `transform: scale`,
DPR/viewport/resolution 자동 tier, 비균일 SVG stretch와 filler content다. 제품 코드에 이 방식은 없다.

## 사용자가 확인할 수 있는 변경

- 우측 기존 사용자 utility 메뉴에 작은 **Display density** radio group과 **Reset display density**를
  추가했다. `Escape`로 닫으면 focus가 menu summary로 돌아온다.
- `html[data-display-density]`를 React root 생성 전에 적용해 Standard 기본 또는 저장된 값으로 첫 shell
  paint가 시작된다. 허용되지 않은 값은 Standard로 수리해 다시 저장한다.
- Materials, Modeling, Activity, Administration이 같은 typography/control/row/spacing/pane/splitter/
  scrollbar/plot/native-preview token을 소비한다. route별 density 값은 없다.
- Administration Database design과 Records는 navigator, 남는 폭을 쓰는 list/table, 최대 800px의
  읽기형 property form으로 이뤄진 공통 semantic three-pane 구조를 사용한다.
- Modeling Navigator는 resize/collapse/double-click reset/reload persistence를 지원한다. Materials의
  Navigator/Context와 마찬가지로 density reset과 독립적이다.
- Export native preview는 공통 최소 높이를 사용한다. Activity identity/status/action 열은 bounded,
  data/evidence 열은 flexible이며 Large 1366의 4px local horizontal overflow를 제거했다.
- Materials와 Fit의 명시적 context는 실제 배정 폭이 1px 미만일 때만 overlay가 된다. 닫기,
  `Escape`, focus 복귀와 Materials의 직접 **Open datasheet**를 지원한다.
- Data hydration의 이전 요청은 `AbortController`로 취소되고, Data/Process/Fit graph는 pane/density
  변경 뒤 frame과 interaction geometry를 함께 다시 계산한다.

## 승인된 production token

| Token group | Compact | Standard | Large |
| --- | ---: | ---: | ---: |
| data / emphasis / metadata / table heading | 13 / 14 / 12 / 11px | 14 / 15 / 13 / 12px | 16 / 17 / 14 / 13px |
| control / input minimum | 36 / 38px | 38 / 40px | 40 / 44px |
| work / navigator row | 46 / 26px | 48 / 30px | 52 / 34px |
| navigator / context default | 264 / 280px | 288 / 304px | 312 / 328px |
| pane splitter / scrollbar | 5 / 13px | 6 / 14px | 7 / 15px |
| plot / native preview minimum | 360 / 240px | 400 / 320px | 440 / 360px |

값은 [#221 decision packet](issue-221-high-dpi-decision.md)의 승인 범위를 그대로 production에
이식했다. route별 수치나 자동 tier를 추가하지 않았다.

## 적용 route/state

| 영역 | 정상 화면 | 고위험·복구 화면 |
| --- | --- | --- |
| Materials | explorer, result, Browse tree, selected Context | empty/short/long result, local scrollbar, context allocation overlay, direct Open datasheet |
| Material datasheet/card | 현재 guide의 exact datasheet와 card preview 기준선 보존 | canonical projection blocker로 이번 density별 재캡처 10개 누락 |
| Modeling Data | library/local input, multi-curve selection, wide graph | empty, invalid mapping, scrolled recovery, navigator expanded/collapsed/reset/reload |
| Modeling Process | normal, Linear regression, wide graph | prerequisite/read error, saved-result siblings, Manual controls local scroll와 Save reachability |
| Modeling Fit | normal, wide graph | calculation/save/exact-read/source blocker, restored result, 긴 candidate parameters/evidence overlay |
| Modeling Export | normal native preview, wide preview | source/approximation blocked; delivered 상태는 fixture blocker에 포함 |
| Activity | role-aware request queue, long Recent outcomes | user/admin role, decision error, recovery, Large 1366 bounded columns/local overflow |
| Administration | Database design, Records, Users & access | three-pane table/form, long local table, file input, role control keyboard/selected state |
| 공통 | route 이동, reload, 세 density | 손상 preference, popup/overlay focus, pane collapse/resize/reset, zoom 200% |

전체 상태 fingerprint와 density/viewport coverage는
[visual-evidence.json](images/issue-184-high-dpi-global-implementation/visual-evidence.json)의
`route_state_geometry_matrix`가 authoritative structured inventory다.

## 다섯 viewport geometry

아래 값은 browser zoom 100%, DPR 1, `Standard` production 코드의 live DOM 측정이다. Materials,
Modeling과 Activity의 task 폭은 viewport 양쪽 8px gutter를 제외한 값이다. Administration 값은 바깥
Administration navigator를 제외하고 중앙에 배치된 semantic three-pane group이다.

| CSS viewport | Materials task / nav / main / context | Modeling Data task / nav / main | Activity task / table | Admin three-pane / nav / center / form | Page H overflow |
| --- | --- | --- | --- | --- | --- |
| 1366×768 | 1350 / 288 / 1048 / overlay | 1350 / 288 / 1056 | 1350 / 1254 | 1103.56 / 288 / 288 / 527.56 | 0 |
| 1440×900 | 1424 / 288 / 818 / 304 | 1424 / 288 / 1130 | 1424 / 1328 | 1175.06 / 288 / 288 / 599.06 | 0 |
| 1920×1080 | 1904 / 288 / 1298 / 304 | 1904 / 288 / 1610 | 1904 / 1822 | 1568 / 288 / 480 / 800 | 0 |
| 2560×1440 | 2544 / 287.98 / 1938.02 / 304 | 2544 / 288.02 / 2249.98 | 2544 / 2462 | 2208 / 288 / 1120 / 800 | 0 |
| 3840×2160 | 3824 / 288 / 3218 / 304 | 3824 / 287.98 / 3530.02 | 3824 / 2598 | 3488 / 288 / 2400 / 800 | 0 |

20개 측정 모두 shell 폭=viewport, page horizontal overflow=0이다. Data graph SVG는
1366에서 1038×323, 1440에서 1112×455, 1920에서 1592×635, 2560에서 2231.98×995,
3840에서 3512.02×1715다. 마지막 axis tick은 SVG 안에 있고 legend/frame 및 legend/curve overlap은
모두 false다. 세 density의 full-state geometry는 각 원본과 token metadata로 추가 검증했다.

Activity의 3840 task shell은 3824px 전체를 사용하고 request/history 비교 표만 2598px로 중앙에
묶는다. 이는 [#221 승인 비교](issue-221-high-dpi-decision.md)의 normal 2656px, history 2642px와 같은
공통 `166rem` comparison-table bound다. 좌우 gutter가 균형이고 identity/evidence 열이 남는 표 폭을
흡수하며 status/action은 bounded다. 따라서 실패 기준인 1920px 이하의 한쪽 작업 섬이나 임의 shell
cap이 아니며, 모든 행·prose를 3840 폭으로 균일하게 늘리지 않는 승인된 readable comparison 정책이다.

## 원본과 direct 100% crop

Structured manifest는 총 334개 파일의 SHA-256, 원본 크기, capture commit, viewport, DPR, browser
zoom, density와 상태 fingerprint를 기록한다.

| Evidence | 수량 | 직접 링크 |
| --- | ---: | --- |
| 변경 전 exact `main@36e8312` 원본 | 59 | [before Modeling Data 3840](images/issue-184-high-dpi-global-implementation/before/modeling-data-3840x2160.png) · [before Admin 3840](images/issue-184-high-dpi-global-implementation/before/administration-database-3840x2160.png) |
| 변경 후 Compact 원본 | 80/90 | [Compact Materials 3840](images/issue-184-high-dpi-global-implementation/after/compact/materials-search-3840x2160.png) |
| 변경 후 Standard 원본 | 80/90 | [Standard Materials 3840](images/issue-184-high-dpi-global-implementation/after/standard/materials-search-3840x2160.png) · [Standard Admin 3840](images/issue-184-high-dpi-global-implementation/after/standard/administration-database-3840x2160.png) |
| 변경 후 Large 원본 | 80/90 | [Large Materials 1366](images/issue-184-high-dpi-global-implementation/after/large/materials-search-1366x768.png) · [Large Activity 1366](images/issue-184-high-dpi-global-implementation/after/large/activity-1366x768.png) |
| direct 1:1 crops, resampling 없음 | 21 | [1920](images/issue-184-high-dpi-global-implementation/crops/1920x1080/header.png) · [2560](images/issue-184-high-dpi-global-implementation/crops/2560x1440/modeling-data-graph.png) · [3840](images/issue-184-high-dpi-global-implementation/crops/3840x2160/administration-form.png) |
| browser zoom 200% 원본 | 14 | [Materials overlay](images/issue-184-high-dpi-global-implementation/zoom-200/materials-context-overlay-outer-1920x1080-css-960x540.png) · [Data graph](images/issue-184-high-dpi-global-implementation/zoom-200/modeling-data-graph-reachable-outer-1920x1080-css-960x540.png) · [Export preview](images/issue-184-high-dpi-global-implementation/zoom-200/modeling-export-preview-outer-1920x1080-css-960x540.png) |

1920/2560/3840 각각 header, Materials navigator/table, Modeling Data graph, Administration form,
Export native preview, density control을 실제 픽셀로 잘라 직접 확인한다. 축소 contact sheet는 승인
증거로 사용하지 않는다.

## Density와 browser zoom 결과

| 검사 | 결과 |
| --- | --- |
| Compact/Standard/Large token 적용 | PASS — 공통 `html` attribute와 production token만 사용 |
| route 이동/reload persistence | PASS — active user/workspace별 browser-local product-wide 값 유지 |
| reset | PASS — density만 Standard, pane preference 보존 |
| malformed/legacy 값 | PASS — 첫 paint 전에 Standard로 수리 |
| keyboard/screen reader | PASS — labelled radio group, selected state, Escape close와 focus return |
| browser zoom 200% | 14개 대표/고위험 상태에서 기능 손실, 불필요한 양방향 page scroll, direct action 미도달 없음 |
| 실제 Windows 4K | **`DEFERRED_TO_223`** — zoom 200%나 CSS 3840 capture로 대체하지 않음 |

## Capture 환경

| 항목 | 기록 |
| --- | --- |
| Compose | canonical `cmp-local-demo`, `deploy/compose/docker-compose.demo.yml`; 기존 volume 보존 |
| Browser | Playwright Chromium, five-viewports zoom 100%/DPR 1; zoom audit outer 1920×1080, CSS 960×540, DPR 2 |
| 외부 monitor | 2560×1440@59Hz |
| 통합 display | 2560×1600@165Hz |
| Windows scale / applied DPI | 100% / 96 DPI |
| 실제 3840×2160 monitor | 없음 — **`DEFERRED_TO_223`** |
| 데이터 | synthetic non-production canonical demo; production write 없음 |

## Canonical fixture와 baseline failure 구분

현재 canonical composition에서 exact Material datasheet/card projection 10개 상태는
`CMP-CATALOG-0015`로 실패한다. 변경 전 원본 59개는 exact `main@36e8312`에서 보존했고 #221 증거는
수정하지 않았다. density별 after capture는 성공한 80개만 atomic하게 교체했다.

별도 `cmp-issue184-clean` project와 새 volume으로 clean-main 구분 검사를 수행했다. seed는
`CMP-CATALOG-0004` immutable catalog identity conflict로 실패했고 full-demo verifier는
`polymer Recipe-to-card Bulk ZIP was not generated`로 실패했다. 데이터를 초기화하거나 verifier를
완화하지 않았다. clean project는 중지했고 canonical project를 재시작한 뒤 preflight와 기존 volume의
idempotent seed는 통과했다. 따라서 현재 10개 캡처 누락은 #184 CSS/React 회귀 통과로 바꿔 말할 수
없고, 깨끗한 main에서도 fixture 준비 경로가 독립적으로 실패한다는 정확한 환경 경계로 남긴다.

## Validation과 review

Main 작업자의 구현·증거 gate 결과다. exact-main baseline 실패는 통과로 바꾸지 않고 별도 행에
분리했다.

| Gate | 결과 |
| --- | --- |
| Web Vitest | PASS — 61 files, 331 tests |
| Playwright non-blocked suite | PASS — 12/12; density 전환/저장/reset/복구, Materials·Modeling pane, allocation overlay, Administration semantics, Activity Large 1366, local scroll, exact download/recovery 포함 |
| Playwright exact-datasheet baseline | `BLOCKED_BASELINE_FIXTURE` — `clean demo exposes…`, `Materials workspaces…`가 기존 `CMP-CATALOG-0015` projection 오류로 차단 |
| production build / bundle budget | PASS — entry 261,708/300,000 bytes, material-library 124,458/131,000, common-processing 121,056/131,000 |
| Python contracts | PASS — 비차단 287개; exact `main@36e8312`에도 존재하는 AGENTS context-budget 및 오래된 backlog 문구 기대 2개는 별도 baseline failure |
| capture / evidence contracts | PASS — 69 tests; 334개 structured evidence SHA·크기·coverage·crop 무결성 포함 |
| Ruff / architecture / contract lint+compat | PASS |
| user-guide inventory / docs-impact | PASS — 20 guides, 90 current captures, 546 links, 1,573 images; 465 changed files / 15 visual sources |
| Compose preflight / `git diff --check` | PASS |
| Web Interface Guidelines review | PASS — semantic controls, visible focus, overlay focus trap·Escape·focus return, no changed zoom/outline/transition anti-pattern |
| full-demo | `BLOCKED_BASELINE_FIXTURE`; 위 clean/current 결과로 구분 |
| independent visual audit | `CHANGES_REQUESTED` — manifest 334개(59 before, 240 after, 21 direct crop, 14 zoom-200)를 모두 원본 해상도로 열고 path/SHA/dimension을 확인했다. 사용 가능한 Q-01–Q-20 상태에는 새 visual defect가 없고, density별 exact datasheet/card/delivered 30개 누락만 blocking finding이다. Activity 3840은 #221 승인 comparison bound와 일치해 finding에서 철회됐다. |
| product-owner disposition | `ISSUE_184_COMPLETE_WITH_223_EVIDENCE_CARRYOVER` — 2026-08-11; PR #231/main `ab27e3947817cefa997e49c5dc1d237ec5035adb`의 production 구현과 #184 완료를 승인했다. 누락 30개는 해결 또는 PASS로 간주하지 않고 #223의 선행 gate로 인계한다. |

## 남은 위험과 #223 인계 경계

- density별 exact Material datasheet/card/delivered 10개, 총 30개 원본이 아직 없다.
- 실제 Windows 4K 100%·150%·200% 물리 판독성은 전혀 판정하지 않았으며 #223 인계 대상이다.
- 독립 감수의 유일한 blocking finding인 fixture 의존 원본 30개를 현재 허용 범위에서는 해소할 수 없다.
- 제품 소유자는 2026-08-11에 위 위험을 보고받은 뒤 구현 PR merge와 #184 완료를 승인했다. 이
  disposition은 독립 감수 PASS 또는 누락 30개 해소를 뜻하지 않는다. 정확한 30개 파일과 manifest,
  독립 원본 재감수는 [#223 handoff](issue-184-to-223-windows-4k-handoff.md)의 선행 gate다.
- #117은 남은 단위 때문에 열린 상태다. backlog의 다음 미완료 단위 #204는 별도 세션에서 시작한다.
