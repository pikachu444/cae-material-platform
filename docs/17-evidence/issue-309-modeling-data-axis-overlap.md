# Issue #309 Modeling Data 저해상도 y축 겹침 수정

## 범위와 진단

- 기준: `origin/main` 및 작업트리 시작점 `12e592dc546e6b8a0dd77216f8ab0f7aee8c72f1`.
- 상태 분류: 부분 구현. 공용 engineering graph는 이미 `ResizeObserver`로 실제 SVG 크기를 읽었지만,
  Data의 resolved-mapping review 분기는 높이가 133 px여도 최소 5개 interval을 요구했다.
  nice tick 확장 결과 8개 y축 값이 8.14 px 간격으로 배치되어 17 px glyph가 일곱 번 겹쳤다.
- 수정: review 분기도 실제 렌더링 높이가 180 px 미만이면 기존 공용 short-frame 밀도인 2개
  interval을 사용한다. 180 px 이상 review graph의 기존 engineering tick 계산은 그대로 둔다.
- 읽기 전용 비교: Issue #261 M1A8 보존 후보의 plot/test diff가 최신 main 구조와 맞는지 확인했다.
  #261의 CSS ownership, inventory, M1A18 guide 문구와 evidence manifest는 복사하지 않았고 해당
  작업트리를 수정하지 않았다.
- 소유 범위: `engineering-curve-plot.tsx`의 review-only y축 밀도와 해당 focused regression뿐이다.
  CSS, route topology, copy, API/domain/URL/persistence, Process/Fit/Export 계산은 변경하지 않았다.

## 기본 사용자 여정

| 항목 | 판정 |
| --- | --- |
| Setup | 세 개의 exact DP780 Test Data revision, 현재 문서 하나, bounded synthetic non-production engineering strain/stress CSV |
| Actions | Data → Process → Data, reload, Local file의 invalid mapping 확인, 열 연결 수정, exact approved t60 reference profile 선택, **Update preview** |
| Visible outcome | `Columns ready` resolved-mapping review와 persistent engineering graph; 1366×768에서 분리된 y축 값 |
| Persistence/read-back | 세 exact Test Data ref, 현재 선택 문서와 session을 stage 왕복 및 reload 뒤 그대로 읽음 |
| Preserved contract/state | Material/State/Test Data exact context, revision, session, selection, preview, focus, last-valid graph |
| Recovery | invalid mapping은 preview를 막고 원인을 표시하며, 수정 뒤 **Update preview**와 focus가 다시 도달 가능 |
| Forbidden shortcuts | media query, CSS zoom/transform, hidden/fabricated data, dependency, CSS 이동, first/latest fallback 없음 |
| Acceptance | 1366에서 tick/title/frame 충돌 0; 큰 viewport의 유용성·픽셀·geometry 보존; overflow/왜곡 0 |

## 실측 전·후

브라우저 zoom은 100%, DPR은 1이다. `SVG`는 화면에 실제 렌더링된 크기이며 자동화된
3840×2160 CSS viewport는 실제 Windows 4K 물리 가독성을 주장하지 않는다.

| CSS viewport | 실제 SVG | Before y ticks / 인접 충돌 | After y ticks / 인접 충돌 | title/frame/page overflow | 비교 |
| --- | ---: | --- | --- | --- | --- |
| 1366×768 | 1348×133 | `700…0` 8개 / 7 | `500, 250, 0` / 0 | 모두 0 | 의도한 y축 영역만 변경 |
| 1440×900 | 1422×195.21875 | 8 / 0 | 8 / 0 | 모두 0 | 원본·graph crop SHA-256 동일 |
| 1920×1080 | 1902×375.21875 | 8 / 0 | 8 / 0 | 모두 0 | 원본·graph crop SHA-256 동일 |
| 2560×1440 | 2542×735.21875 | 8 / 0 | 8 / 0 | 모두 0 | 원본·graph crop SHA-256 동일 |
| 3840×2160 | 2782×1085.21875 | 8 / 0 | 8 / 0 | 모두 0 | 원본·graph crop SHA-256 동일 |

모든 viewport에서 session 보존, **Update preview** focus 도달, console error 0을 확인했다.
10개의 header/control before-after crop 쌍도 모두 byte-identical이다. 상세 geometry는
[`before/measurements.json`](images/issue-309-modeling-data-axis-overlap/before/measurements.json)과
[`after/measurements.json`](images/issue-309-modeling-data-axis-overlap/after/measurements.json)에 있다.

### Original과 100% crop

- Before originals: [`before/originals`](images/issue-309-modeling-data-axis-overlap/before/originals)
- After originals: [`after/originals`](images/issue-309-modeling-data-axis-overlap/after/originals)
- Before 100% crops: [`before/crops`](images/issue-309-modeling-data-axis-overlap/before/crops)
- After 100% crops: [`after/crops`](images/issue-309-modeling-data-axis-overlap/after/crops)
- 전체 등록과 판정: [`visual-evidence.yaml`](images/issue-309-modeling-data-axis-overlap/visual-evidence.yaml)

| Viewport | Before | After |
| --- | --- | --- |
| 1366×768 | [original](images/issue-309-modeling-data-axis-overlap/before/originals/modeling-data-mapping-resolved-1366x768.png) · [header](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1366x768-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1366x768-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1366x768-graph-100pct.png) | [original](images/issue-309-modeling-data-axis-overlap/after/originals/modeling-data-mapping-resolved-1366x768.png) · [header](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1366x768-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1366x768-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1366x768-graph-100pct.png) |
| 1440×900 | [original](images/issue-309-modeling-data-axis-overlap/before/originals/modeling-data-mapping-resolved-1440x900.png) · [header](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1440x900-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1440x900-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1440x900-graph-100pct.png) | [original](images/issue-309-modeling-data-axis-overlap/after/originals/modeling-data-mapping-resolved-1440x900.png) · [header](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1440x900-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1440x900-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1440x900-graph-100pct.png) |
| 1920×1080 | [original](images/issue-309-modeling-data-axis-overlap/before/originals/modeling-data-mapping-resolved-1920x1080.png) · [header](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1920x1080-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1920x1080-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-1920x1080-graph-100pct.png) | [original](images/issue-309-modeling-data-axis-overlap/after/originals/modeling-data-mapping-resolved-1920x1080.png) · [header](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1920x1080-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1920x1080-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-1920x1080-graph-100pct.png) |
| 2560×1440 | [original](images/issue-309-modeling-data-axis-overlap/before/originals/modeling-data-mapping-resolved-2560x1440.png) · [header](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-2560x1440-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-2560x1440-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-2560x1440-graph-100pct.png) | [original](images/issue-309-modeling-data-axis-overlap/after/originals/modeling-data-mapping-resolved-2560x1440.png) · [header](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-2560x1440-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-2560x1440-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-2560x1440-graph-100pct.png) |
| 3840×2160 | [original](images/issue-309-modeling-data-axis-overlap/before/originals/modeling-data-mapping-resolved-3840x2160.png) · [header](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-3840x2160-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-3840x2160-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/before/crops/modeling-data-mapping-resolved-3840x2160-graph-100pct.png) | [original](images/issue-309-modeling-data-axis-overlap/after/originals/modeling-data-mapping-resolved-3840x2160.png) · [header](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-3840x2160-header-100pct.png) · [controls](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-3840x2160-controls-100pct.png) · [graph](images/issue-309-modeling-data-axis-overlap/after/crops/modeling-data-mapping-resolved-3840x2160-graph-100pct.png) |

Main은 전·후 원본 10장과 header/controls/graph 100% crop 30장, 총 40개 PNG를 모두 원본
해상도로 열었다. Before 1366에서는 y축 숫자가 수직으로 겹치지만 After 1366에서는
`500 / 250 / 0`이 분리되고 세로축 제목과 frame이 선명하게 유지된다. 1440 이상은 픽셀 변화가 없다.

## #249 design synthesis

- 정보 계층: **Pass.** mapping 결정이 graph 앞에 있고 graph가 결과 영역을 계속 지배한다. 충돌하던
  축 세부 정보만 줄어들며 Material/Test Data identity나 결정 상태를 밀어내지 않는다.
- engineering task flow: **Pass.** exact Data → Process → Data, reload, invalid mapping → repair →
  **Update preview**와 keyboard focus 흐름이 그대로다.
- responsive/wide-screen composition: **Pass.** 실제 SVG 높이로 짧은 frame만 조정한다. 1440–3840의
  기존 pixels, 3840의 중앙 2800 px 유용한 graph bound, full-viewport shell과 zero overflow를 보존한다.

## 정성 판정 Q-01~Q-20

| 항목 | 판정 | 근거 |
| --- | --- | --- |
| Q-01 | Not applicable | 짧은 curve navigator fixture이며 긴 tree overflow가 없다. |
| Q-02 | Not applicable | resolved local mapping에 긴 result list가 없다. |
| Q-03 | Not applicable | Materials navigator는 변경하지 않았다. |
| Q-04 | Not applicable | Fit ribbon은 변경하지 않았다. |
| Q-05 | Pass | 모든 viewport에서 tick/title/frame 충돌 0. |
| Q-06 | Not applicable | 단일 review curve라 multi-curve legend가 없다. |
| Q-07 | Pass | 실제 SVG/viewBox를 재측정하며 stretch, zoom, transform이 없다. |
| Q-08 | Not applicable | 이 preview는 true-yield response가 아니다. |
| Q-09 | Not applicable | genuine overflow fixture가 아니다. |
| Q-10 | Not applicable | Fit legend는 변경하지 않았다. |
| Q-11 | Not applicable | Fit rail은 변경하지 않았다. |
| Q-12 | Not applicable | Export selected model은 변경하지 않았다. |
| Q-13 | Not applicable | Export row grammar는 변경하지 않았다. |
| Q-14 | Not applicable | Export readiness는 변경하지 않았다. |
| Q-15 | Pass | zero anchor, data headroom, 단위와 curve/frame 간격을 보존했다. |
| Q-16 | Not applicable | Export native preview는 변경하지 않았다. |
| Q-17 | Not applicable | Administration list는 변경하지 않았다. |
| Q-18 | Not applicable | Administration editing은 변경하지 않았다. |
| Q-19 | Not applicable | Link Type/revision 동작은 변경하지 않았다. |
| Q-20 | Pass | full shell, bounded wide graph, zero overflow를 유지하며 responsive shortcut이 없다. |

## 실행 환경과 검증

Compose preflight는 이 작업트리의 canonical composition을 통과했다. 기존 volume과 데이터를
보존하고 after capture 전에 web만 새 production source로 rebuild/recreate했다. Seed는 base demo
단계를 마친 뒤 기존 volume의 Issue #246 domain-binding POST가 idempotency conflict를 반환했다.
동일 명령을 반복하거나 volume을 지우지 않고, 보존된 데이터에 대한 exact session/read-back 검증을
계속했다.

최종 focused/full frontend test, production build, user-guide, docs-impact, diff와 pre-publish 결과는
동일 candidate의 publication gate에서 확인한다. Balanced 독립 read-only 감사 승인이 commit 전 필수다.
