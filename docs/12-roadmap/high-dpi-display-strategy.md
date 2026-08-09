# 4K·고DPI 화면 대응 전략과 결정 기록

상태: **#221 결정 입력, 값 미승인**  
기준선: `main@53e4a698235e4c7dad8c87e0156bc2627866989f`  
상위 추적: [#117](https://github.com/pikachu444/cae-material-platform/issues/117)  
결정 게이트: [#221](https://github.com/pikachu444/cae-material-platform/issues/221)  
전체 적용: [#184](https://github.com/pikachu444/cae-material-platform/issues/184)

이 문서는 4K 전용 CSS 값을 미리 확정하지 않는다. 외부 제품과 웹 플랫폼의 공개 근거, 현재
코드의 제약, 비교할 후보와 측정 방법을 고정하여 #221의 실제 Windows 원본 화면 검토가 같은
질문에 답하도록 한다. #221에서 승인된 결정만 #184의 전체 route 구현 권한이 된다.

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

## 3. 현재 기준선의 구체적 위험

현재 shell은 이미 viewport 전체 크기를 사용할 수 있고 Grid/Flex 및 일부 container query 기반도
있다. 전면 재작성보다 공통 token과 layout 경계의 정리가 먼저다.

- `apps/web/src/design/layout.css`
  - `.modeling-data-workspace-bounded`의 `max-width: 1920px`
  - 1920px 이상에서 적용되는 `max-height: 878px`
- `apps/web/src/styles.css`
  - `.export-workspace`의 `max-width: 1920px`
  - `.administration-record-workbench`의 `max-width: 120rem`
- 10~11.5px 글자 크기와 control/row 크기가 여러 route에 개별 선언되어 있다.
- route별 고정값은 같은 물리적 크기 정책을 재사용하거나 사용자가 밀도를 바꾸기 어렵게 한다.

#161은 이 고정값을 공통 semantic token과 full-shell 경계로 이동한다. #221은 그 기반 위에서 실제
표시 값을 고르고, #184는 승인된 값을 전체 route와 고위험 상태에 적용한다.

## 4. #221에서 비교할 세 후보

| 후보 | 구성 | 장점 | 위험 | 현재 입장 |
| --- | --- | --- | --- | --- |
| P1 | OS/browser scale + 의미 기반 full-shell layout | 단순하고 플랫폼 동작을 그대로 사용 | 4K 100%에서 개인별 가독성 차이를 앱에서 보완하기 어려움 | 비교 필요 |
| P2 | P1 + 공통 `Compact / Standard / Large` density | 사용자가 정보량과 가독성을 직접 조절, route 간 일관성 | token과 persistence 계약이 필요 | **우선 검토**, 아직 미승인 |
| P3 | viewport/DPR/resolution에 따른 자동 density | 사용자의 초기 조작이 적음 | browser zoom·PPI·OS scale을 오판하고 route 예외가 늘 수 있음 | 기각 근거 확인용 |

P2를 먼저 비교하되 원본 화면과 실제 Windows 측정 전에는 채택하지 않는다. 자동 추천 문구를
제공할 수는 있지만 사용자 선택을 조용히 덮어쓰지 않는다.

## 5. 의미 기반 레이아웃 계약

### 5.1 Shell과 pane

- application shell은 viewport 전체를 사용한다.
- navigator와 inspector는 공통 `min / ideal / max` 범위, keyboard-accessible splitter, collapse와
  reset을 갖는다.
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

아래 값은 #221 비교 시작점이며 제품 계약이 아니다. 실제 4K 원본 화면에서 수정·기각할 수 있다.

| 후보 tier | Body | Metadata | Control | Data row | 예상 용도 |
| --- | ---: | ---: | ---: | ---: | --- |
| Compact | 약 13px | 11.5~12px | 약 28px | 26~28px | 1366/1440 및 높은 OS 배율의 dense 작업 |
| Standard | 약 14px | 12.5~13px | 약 32px | 30~32px | 기본 후보 |
| Large | 약 15~16px | 13.5~14px | 36~40px | 34~36px | 4K 100% 가독성 비교 |

각 tier는 typography만 바꾸지 않고 control, row, spacing, pane, splitter와 plot label token을 함께
조절한다. 전체 화면을 동일 비율로 확대하지 않는다. 기본 tier, 사용자 변경, reset과 persistence는
#221에서 함께 승인한다.

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

### 8.1 자동 viewport 표

| Route/state | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | --- | --- | --- | --- | --- |
| Materials | | | | | |
| Modeling Data | | | | | |
| Modeling Fit | | | | | |
| Modeling Export | | | | | |
| Activity | | | | | |
| Administration | | | | | |

각 칸은 full-screen 원본, 100% header/navigator/table-or-form/plot-or-preview crop, CSS viewport,
workspace/pane/plot 측정과 Q-01~Q-20 disposition을 가리킨다.

### 8.2 실제 Windows 표

| Monitor 크기·해상도 | Windows scale | Browser zoom | CSS viewport | DPR | Density | 원본/crop | Owner disposition |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| | 100% | 100% | | | | | |
| | 150% | 100% | | | | | |
| | 200% | 100% | | | | | |

실제 표시 기록이 없으면 #221은 `BLOCKED_PHYSICAL_EVIDENCE`다. 자동 viewport와 축소 contact sheet만으로
scale tier를 승인하지 않는다.

### 8.3 접근성 분리 검증

Browser zoom 200%에서 내용·기능 손실, 겹침, 잘림, action reachability와 불필요한 양방향 page
scroll을 확인한다. 이 검사는 Windows 4K 100/150/200% 원본 검토를 대신하지 않는다.

## 9. 이슈별 책임

| Issue | 책임 | 완료로 주장하지 않는 것 |
| --- | --- | --- |
| #161 | 공통 token/shell/pane 기반, 오래된 값과 1920px cap 정리 | 정확한 4K tier와 실제 물리 가독성 승인 |
| #221 | 실제 4K 측정, P1/P2/P3 비교, 대표 화면 prototype, 정확한 공통 결정 | 모든 route와 모든 고위험 상태 완료 |
| #184 | 승인된 결정을 전체 route/state에 적용하고 제품 전체 Q-20 최종 승인 | 새로운 route별 scale 체계 재결정 |

실행 순서는 `#160 → #161 → #221 → #184 → #204~#216 → #162`다.

## 10. 금지 방식

- route별 4K media rule 또는 private font/control 값
- CSS `zoom`, blanket `transform: scale`, 비균일 SVG stretch
- DPR/resolution만으로 density를 자동 강제
- 1920px 전체 workbench cap과 한쪽 정렬
- 가짜 행, 설명, 카드 또는 기술 metadata로 빈 공간 채우기
- 모든 table column, row, form, prose와 plot의 균일 확대
- 실제 표시 원본 없이 exact tier 값을 승인

## 11. 결정 기록

| 항목 | 상태 |
| --- | --- |
| 선택 후보 | 미결정 — #221 제품 소유자 승인 필요 |
| Compact/Standard/Large 정확한 token | 미결정 |
| 기본 tier와 사용자 변경/reset | 미결정 |
| pane/column preference 저장 범위 | 미결정 |
| 기각 후보와 근거 | 미결정 |
| 전체 route 이식 목록 | #221 승인 뒤 #184로 전달 |

#221 PR은 이 표를 실제 값과 직접 evidence 경로로 교체한다. 대화 기억, 축소 이미지 또는 자동 수치만
근거로 완료 표시하지 않는다.
