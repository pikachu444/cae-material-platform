# 4K·고DPI 화면 대응 전략과 결정 기록

- 상태: **#221 P2/Standard 승인·병합, #184 production 전역 이식 및 geometry 검증 중; 실제 장비 최종 판정은 #223**
- 기준선: `main@36e8312fa85253ad8fee88f63a3a4bf096d92a9c`
- 상위 추적: [#117](https://github.com/pikachu444/cae-material-platform/issues/117)
- 결정 게이트: [#221](https://github.com/pikachu444/cae-material-platform/issues/221)
- 전체 적용: [#184](https://github.com/pikachu444/cae-material-platform/issues/184)
- 실제 장비 최종 검증: [#223](https://github.com/pikachu444/cae-material-platform/issues/223)

이 문서는 4K 전용 CSS 값을 확정하지 않는다. 외부 제품과 웹 플랫폼의 공개 근거, 현재 코드의 제약,
비교할 후보와 측정 방법을 고정하고 [#221 decision packet](../17-evidence/issue-221-high-dpi-decision.md)의
실측 결과를 연결한다. 제품 소유자는 2026-08-10에 P2와 `Standard` 기본을 #184의 구현용 잠정
정책으로 승인했고 [PR #228](https://github.com/pikachu444/cae-material-platform/pull/228)에서 병합했다.
#184는 이 계약을 모든 route/state에 production 기능으로 이식한다. 실제 Windows 4K
100%·150%·200%의 물리적 가독성은 전체 기능이 끝난 뒤 #223에서 최종 판정한다.

## 1. 해결할 두 문제

4K 대응은 하나의 해상도 breakpoint 문제가 아니다.

1. **논리적 작업공간**: 넓어진 CSS viewport를 tree, table, plot, preview와 form에 어떻게 배분할지
   결정한다.
2. **물리적 가독성**: 실제 모니터에서 글자, 행, 버튼, splitter와 plot label이 읽고 조작할 만한지
   결정한다.

브라우저 확대 100%에서 3840×2160 모니터의 논리적 작업공간은 Windows 배율에 따라 대략 다음과
같다. 브라우저 chrome 때문에 실제 `innerWidth`와 `innerHeight`는 조금 작다.

| Windows 표시 배율 | 대략적인 CSS 작업공간 | 주 검증 목적 |
| ---: | ---: | --- |
| 100% | 3840×2160 | 가장 넓은 geometry와 가장 작은 물리 UI |
| 150% | 2560×1440 | 넓은 작업공간과 가독성의 중간 조건 |
| 200% | 1920×1080 | 표준 desktop geometry와 확대된 물리 UI |

`devicePixelRatio`는 브라우저 page zoom에도 변한다. 따라서 DPR 또는 CSS resolution만으로
물리적 4K를 추정해 화면 밀도를 자동 선택하지 않는다. 실제 환경 기록과 명시적 사용자 설정을
분리한다. [MDN devicePixelRatio](https://developer.mozilla.org/en-US/docs/Web/API/Window/devicePixelRatio)

현재 작업 환경에 실제 3840×2160 디스플레이가 없어도 headless Playwright는 2560×1440과
3840×2160 CSS viewport를 원본 픽셀로 생성할 수 있다. 이 증거는 shell·pane·table·plot의 배치,
넘침, 잘림과 상호작용을 검증하지만 모니터의 물리적 글자·control 크기를 증명하지 않는다. 따라서
가상 viewport 검증은 #221/#184의 병합 조건으로 유지하고, 실제 장비 판정만 #223으로 분리한다.

## 2. 공개 제품과 구현 참고에서 확인한 패턴

| 참고 | 확인한 방식 | 이 제품의 판단 기준 |
| --- | --- | --- |
| [Microsoft Windows UI 권장사항](https://learn.microsoft.com/en-us/windows/apps/get-started/best-practices) | pane과 page를 여러 창 크기, DPI와 scale에서 직접 검증 | viewport 자동 검사와 실제 표시 검증을 둘 다 수행 |
| [Altair HyperWorks UHD 지원](https://2025.help.altair.com/2025.1/hwdesktop/cfd/topics/getting_started/platform_support_r.htm) | 2160p를 지원하고 Windows 200% scale을 권장 | OS 배율을 정상 사용자 수단으로 존중하되 앱 geometry도 별도 대응 |
| [Altair dock/undock UI](https://help.altair.com/hwdesktop/hlwc/topics/user_interface/dock_undock_ui_t.htm) | browser와 panel을 dock, undock, resize, tab stack | 좌우 pane을 무한 확대하지 않고 조절·접기·복원 |
| [Altair Material Data Center](https://2025.help.altair.com/altairone/topics/materialsdb/material_properties_view_t.htm) | 상세를 우측에 표시하고 필요할 때 전체화면 전환 | bounded detail pane과 focused/full-screen 작업을 병행 |
| [Ansys Granta MI record tree](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Granta_MI_Rel_Notes/release_notes/what_s_new_mi.html) | tree 탐색과 data view를 역할별로 분리 | tree/table/datasheet topology를 유지하고 중앙 결과를 우선 확장 |
| [Figma UI scale](https://help.figma.com/hc/en-us/articles/360049549913-Adjust-the-scale-of-the-Figma-UI) | 사용자가 UI scale 또는 browser zoom을 조절 | 공통 사용자 선택 density를 후보로 검증 |
| [AG Grid column sizing](https://www.ag-grid.com/javascript-data-grid/column-sizing/) | fixed/bounded 열과 flex 열을 혼합하고 min/max 적용 | 모든 열을 균일하게 늘리지 않고 data/evidence 열에 잔여 폭 배분 |
| [MDN container queries](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Containment/Container_queries) | component가 viewport가 아니라 자기 container에 반응 | resizable pane 안의 table/form/plot을 local size로 전환 |
| [Apache ECharts resize](https://echarts.apache.org/handbook/en/concepts/chart-size/) | container 변화 뒤 chart geometry를 다시 계산 | splitter 변경에도 axis, legend, label과 hit region 재계산 |
| [W3C text resize](https://www.w3.org/WAI/WCAG22/Understanding/resize-text) | 200% text 확대에서 내용과 기능 유지 | browser zoom 200%를 실제 4K 승인과 별도 접근성 gate로 검증 |

위 제품의 모양을 복제하지 않는다. 공통 패턴은 **OS 배율 존중, 역할별 pane, 중앙 작업영역 우선,
사용자 조절, 실제 표시 검증**이다.

## 3. #161 공통 기반과 남은 결정

#161 이전 기준선에는 Materials·Modeling Data/Process/Fit·Export의 `max-width: 1920px`, Modeling의
`max-height: 878px`, Administration record workspace의 `max-width: 120rem`과 route별 control/row/pane
값이 흩어져 있었다. 2560·3840 CSS viewport에서 shell은 넓어져도 실제 task가 왼쪽 1920px 섬에
남는 직접 원인이었다.

#161은 다음 기반만 제공한다.

- app shell과 1차 data/graph/native-preview workspace는 공통 elastic boundary를 사용한다.
- navigator, context, 읽기형 form/prose와 비교 table만 의미에 맞는 공통 상한을 유지한다.
- typography, control/row, pane/splitter, tree, scroll rail과 plot 지표를 공통 CSS/TypeScript metric으로
  이동한다.
- 캡처 계약은 1920px 상한을 승인하지 않고, 1920px 이상에서 보이는 1차 workspace가 viewport 폭의
  80% 미만인 고정폭 섬으로 줄어들면 실패한다.
- route 전용 2560/3840 media rule, CSS `zoom`, 일괄 `scale`, 채우기용 행은 금지한다.

이 기반 자체는 Compact/Standard/Large 표시 단계나 기본값을 결정하지 않았다. #221은 구현용 잠정
layout·pane·density·table·plot 정책으로 P2/`Standard`를 승인했고, #184는 승인된 값을 전체 route와
고위험 상태에 적용한다.
#223은 실제 Windows 4K 장비에서 잠정 값을 최종 승인하거나 공통 보정 bug를 요구한다.

## 4. #221에서 비교할 세 후보

| 후보 | 구성 | 장점 | 위험 | 현재 입장 |
| --- | --- | --- | --- | --- |
| P1 | OS/browser scale + 의미 기반 full-shell layout | 단순하고 플랫폼 동작을 그대로 사용 | 4K 100%에서 개인별 가독성 차이를 앱에서 보완하기 어려움 | layout 기반으로 유효, 단독 채택은 비권고 |
| P2 | P1 + 공통 `Compact / Standard / Large` density | 사용자가 정보량과 가독성을 직접 조절, route 간 일관성 | token과 persistence 계약이 필요 | **제품 소유자 승인: Standard 기본, #184 production 이식** |
| P3 | viewport/DPR/resolution에 따른 자동 density | 사용자의 초기 조작이 적음 | browser zoom·PPI·OS scale을 오판하고 route 예외가 늘 수 있음 | **기각 — 제품 prototype 없음** |

동일 상태의 baseline을 먼저 측정한 뒤 P1, P2 Compact/Standard/Large를 다섯 viewport와 browser
zoom 200%에서 비교했다. P3는 100%에서 DPR 1이던 같은 browser가 zoom 200%에서 DPR 2를 내보내
OS/device scale과 구분할 수 없었으므로 자동 적용 code 없이 기각했다. 실제 Windows 측정 전에는
물리적 가독성이나 최종 기본 tier를 승인했다고 주장하지 않는다. 자동 추천 문구를 제공할 수는 있지만
사용자 선택을 조용히 덮어쓰지 않는다.

## 5. 의미 기반 레이아웃 계약

### 5.1 Shell과 pane

- application shell은 viewport 전체를 사용한다.
- navigator와 inspector는 공통 `min / ideal / max` 범위, keyboard-accessible splitter, collapse와
  reset을 갖는다.
- 사용자가 context를 펼쳤지만 shared pane minima 때문에 실제 배정 폭이 0이면 actual allocation을
  관찰해 bounded overlay 또는 동등한 공통 disclosure로 전환한다. viewport, DPR, resolution이나 route
  이름으로 이 상태를 추정하지 않는다.
- 중앙 table, plot와 native preview가 남은 공간을 우선 사용한다.
- bounded 영역이 유용한 최대 크기에 도달하면 관련 companion evidence를 배치하거나 균형 잡힌
  gutter를 유지한다. 전체 작업을 왼쪽 1920px 섬으로 남기지 않는다.
- pane 크기와 density persistence는 기존 client preference 경계를 우선 사용한다. 기존 경계가
  없으면 #221 prototype은 local client persistence로 제한하고 cross-device account setting은 별도
  승인 없이 만들지 않는다.

### 5.2 Table

- identity, status와 row action 열은 고정 또는 bounded width를 사용한다.
- description, evidence와 engineering data 열은 `minWidth`, `maxWidth`, flex 우선순위를 갖는다.
- 사용자가 바꾼 열 폭은 허용 범위에서 복원하고 reset을 제공한다.
- 넓은 화면에서는 더 많은 유효 열과 행을 보여 준다. 행과 문장을 단지 공간 채우기 위해 늘리지
  않는다.

### 5.3 Plot과 preview

- `ResizeObserver` 또는 동등한 실제 container 관찰로 resize한다.
- render box, SVG viewBox, axis, ticks, paths, legend, label과 hit region이 하나의 geometry를 쓴다.
- plot과 native preview는 비교·조작 이득이 있는 범위까지 확장하고, 제한 뒤에는 균형 잡힌 gutter나
  실제 evidence를 사용한다.
- CSS stretch, 비균일 SVG 확대와 고해상도 전용 고정 plot size를 사용하지 않는다.

### 5.4 Form과 문장

- property form, 설명 문장과 긴 value는 읽기 좋은 상한을 유지한다.
- 넓은 viewport에서 input 하나를 화면 전체로 늘리지 않는다.
- Administration list/table은 넓이를 사용하되 edit form은 adjacent bounded pane으로 유지한다.

## 6. 화면 밀도 prototype 값

아래 값은 #221 비교에서 제품 소유자가 #184 production 이식 범위로 잠정 승인한 값이다.
실제 4K 물리 가독성에 대한 최종 제품 계약은 #223 판정 전까지 아니다.

| 후보 tier | Data / emphasis | Metadata / table heading | Control / input min | Work / navigator row | 예상 용도 |
| --- | ---: | ---: | ---: | ---: | --- |
| Compact | 13 / 14px | 12 / 11px | 36 / 38px | 46 / 26px | 1366/1440 및 높은 OS 배율의 dense 작업 |
| Standard | 14 / 15px | 13 / 12px | 38 / 40px | 48 / 30px | **승인된 #184 기본값** |
| Large | 16 / 17px | 14 / 13px | 40 / 44px | 52 / 34px | 명시적 사용자 선택 상한과 실제 4K 비교 |

각 tier는 typography만 바꾸지 않고 control, row, spacing, pane, splitter와 plot label token을 함께
조절한다. 전체 화면을 동일 비율로 확대하지 않는다. 기본 tier, 사용자 변경, reset과 persistence는
#221에서 #184 구현용 잠정 계약으로 승인됐고 #223에서 실제 장비 기준으로 최종 확인한다.

## 7. 대표 화면과 전체 적용 경계

| 구조 | #221 대표 화면 | 넓은 공간의 우선 사용자 |
| --- | --- | --- |
| Tree + result + detail | Materials | result table, datasheet; detail은 bounded/full-screen |
| Navigator + data/preview | Modeling Data | mapping table와 preview |
| Controls + plot | Modeling Fit | plot과 candidate evidence |
| Setup + native preview + context | Modeling Export | native preview |
| Dense queue/history | Activity | 실제 request rows와 local history |
| List + edit form | Administration | list/table; form은 readable bound |

#221은 서로 다른 layout 유형을 대표하는 최소 화면에서 정책을 선택한다. #184는 승인된 정책을 모든
정상 route와 loading, empty, disabled, error, 긴 이름, popup/drawer, 긴 목록, 접힌/펼친 pane 상태에
적용한다.

## 8. 측정과 승인 기록

### 8.1 #221 결정용 자동 viewport 표

| Route/state | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | --- | --- | --- | --- | --- |
| Materials | 2 surfaces × 5 variants pass | pass | pass | pass | pass |
| Modeling Data | 5 variants pass | pass | pass | pass | pass |
| Modeling Fit | 5 variants pass | pass | pass | pass | pass |
| Modeling Export | 5 variants pass | pass | pass | pass | pass |
| Activity | 4 states × 5 variants pass | pass | pass | pass | pass |
| Administration | 2 surfaces × 5 variants pass | pass | pass | pass | pass |

각 칸의 full-screen 원본, 100% header/navigator/table-or-form/plot-or-preview crop, CSS viewport,
workspace/pane/plot 측정과 Q-01~Q-20 disposition은
[#221 decision packet](../17-evidence/issue-221-high-dpi-decision.md)과 그 structured measurement manifest를
가리킨다. `pass`는 대표 geometry 비교가 완료됐다는 뜻이다. 제품 소유자 정책 승인은 PR #228에서
별도로 이뤄졌으며 이 표만으로 #184의 product-wide Q-20 완료를 뜻하지 않는다.

### 8.2 #184 production 이식 측정

#184의 [issue-owned evidence](../17-evidence/issue-184-high-dpi-global-implementation.md)와
[structured geometry manifest](../17-evidence/images/issue-184-high-dpi-global-implementation/geometry-measurements.json)는
`Standard`의 Materials, Modeling Data, Activity, Administration Database design을 다섯 viewport에서
직접 측정한다. shell/task workspace는 Materials·Modeling·Activity에서 각각 viewport 폭에서 16px를
제외한 1350/1424/1904/2544/3824px를 사용하며 page horizontal overflow는 20개 측정 모두 0이다.
Administration의 semantic three-pane group은 1366에서 1103.56px, 1920에서 1568px, 2560에서
2208px, 3840에서 3488px를 사용하고 navigator/form은 각각 288px/최대 800px에 묶는다.

Compact/Standard/Large의 240개 production 원본과 21개 direct 100% crop, browser zoom 200%의
14개 원본은 structured manifest에서 hash와 상태 fingerprint로 관리한다. 다만 canonical append-only
fixture의 `CMP-CATALOG-0015` 때문에 density별 10개 exact datasheet/card/delivered 상태를 다시 만들지
못했으므로 전체 90개×3 matrix는 `INCOMPLETE_BASELINE_FIXTURE_BLOCKER`다. verifier나 데이터를
완화하지 않았다. 독립 읽기 전용 감수자는 사용 가능한 334개에서 새 visual defect를 찾지 않았지만
이 30개 누락을 blocking finding으로 유지했으며, 누락 해소와 제품 소유자 검토 전 #184를 통과로
기록하지 않는다.

### 8.3 실제 Windows 표 — #223 최종 증거

| Monitor 크기·해상도 | Windows scale | Browser zoom | CSS viewport | DPR | Density | 원본/crop | Owner disposition |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| | 100% | 100% | | | | | |
| | 150% | 100% | | | | | |
| | 200% | 100% | | | | | |

실제 표시 기록이 없으면 #221과 #184는 `DEFERRED_TO_223`을 기록한다. 이 상태는 다섯 viewport
geometry, 원본/crop 검토, 접근성 및 금지 방식 검사가 모두 통과한 경우에만 병합을 막지 않는다.
자동 viewport와 축소 contact sheet를 실제 물리 가독성 증거로 표시해서는 안 된다. #223은 이 표를
실제 값으로 채우지 못하면 완료할 수 없다.

### 8.4 접근성 분리 검증

Browser zoom 200%에서 내용·기능 손실, 겹침, 잘림, action reachability와 불필요한 양방향 page
scroll을 확인한다. 이 검사는 Windows 4K 100/150/200% 원본 검토를 대신하지 않는다.

## 9. 이슈별 책임

| Issue | 책임 | 완료로 주장하지 않는 것 |
| --- | --- | --- |
| #161 | 공통 token/shell/pane 기반, 오래된 값과 1920px cap 정리 | 잠정 density 후보와 실제 물리 가독성 승인 |
| #221 | P1/P2/P3 비교, 대표 화면 prototype, 다섯 viewport 기반 구현용 잠정 공통 결정 | 모든 route 적용과 실제 Windows 물리 가독성 최종 승인 |
| #184 | 잠정 결정을 전체 route/state에 적용하고 자동 geometry Q-20 완료 | 실제 Windows 물리 가독성 최종 승인이나 route별 scale 재결정 |
| #223 | 전체 제품을 실제 Windows 4K 100%·150%·200%에서 검증하고 최종 판정 | route별 임시 보정이나 새 기능 설계 |

실행 순서는 `#160 → #161 → #221 → #184 → #204~#216 → #162 → #223`이다.

## 10. 금지 방식

- route별 4K media rule 또는 private font/control 값
- CSS `zoom`, blanket `transform: scale`, 비균일 SVG stretch
- DPR/resolution만으로 density를 자동 강제
- 1920px 전체 workbench cap과 한쪽 정렬
- 가짜 행, 설명, 카드 또는 기술 metadata로 빈 공간 채우기
- 모든 table column, row, form, prose와 plot의 균일 확대
- 실제 표시 원본 없이 잠정 tier 값을 물리 가독성 최종 승인으로 표시

## 11. 결정 기록

| 항목 | 상태 |
| --- | --- |
| 구현용 잠정 선택 후보 | **P2 — 2026-08-10 제품 소유자 승인, PR #228 병합** |
| Compact/Standard/Large 잠정 token | packet의 실측 13/14/16px data font, 26/30/34px navigator row와 연동 control/pane/plot 범위를 #184 production에 이식 |
| 잠정 기본 tier와 사용자 변경/reset | `Standard` 기본, 세 tier만 사용자 변경, reset은 `Standard` |
| pane/column preference 저장 범위 | 기존 경계와 같은 browser-local product-wide preference; active user/workspace 구분, route URL/backend/cross-device sync 제외 |
| 기각 후보와 근거 | P3 기각: browser zoom 200%만으로 DPR 1→2, CSS viewport 1920→960이 되어 OS/device scale과 구분 불가 |
| 전체 route 이식 목록 | [decision packet의 #184 목록](../17-evidence/issue-221-high-dpi-decision.md#184-transplant-list-after-owner-approval)을 production에 구현; 증거 누락·검수는 issue-owned evidence에서 추적 |
| 실제 Windows 4K 물리 판정 | `DEFERRED_TO_223` |

#221 packet은 제품 소유자 승인과 직접 evidence 경로를 기록한다. 이 승인은 #184의 구현용 잠정
정책이며 실제 Windows 4K 물리 가독성 승인이 아니다. 대화 기억, 축소 이미지 또는 자동 수치만으로
물리 가독성을 완료 표시하지 않는다. #223은 실제 장비 증거와 최종 승인 또는 후속 공통 보정 bug를
기록한다.
