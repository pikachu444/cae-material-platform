# Issue #221 — 4K·high-DPI policy decision packet

## Disposition

- 상태: **`PENDING_PRODUCT_OWNER`**
- 기준선: `main@ca7c97869522e3fe5d889fdc5f834bd963f85340`
- Codex 권고: **P2 — OS/browser 배율 존중 + 공통 `Compact / Standard / Large` density**, 잠정 기본은
  `Standard`
- 제품 결정: 아직 없음. 이 packet과 후보 화면을 제품 소유자가 승인하기 전에는 설정을 제품 기능으로
  노출하거나 #184에 이식하지 않는다.
- 실제 Windows 4K 100%·150%·200% 물리 가독성: **`DEFERRED_TO_223`**

#221은 제품 전체의 high-DPI 구현이 아니라 대표 화면에서 공통 정책 후보를 비교하는 결정 gate다.
프로덕션 React/CSS, backend, database, permission, revision과 material-model 기능은 변경하지 않았다.
후보 CSS는 canonical Compose 화면이 준비된 뒤 Playwright가 주입하는 issue 전용 prototype이며 web
bundle에서 import하지 않는다. #167 승인 이미지는 읽기 전용 비교 자료로만 사용했고 파일과 hash를
변경하지 않았다.

## Primary journey and bounded acceptance

1. 같은 canonical Compose 데이터와 exact revision을 준비한다.
2. 각 surface/viewport에서 먼저 current `main` 기준선을 측정한 뒤 같은 URL, 상태 fingerprint와 DOM에
   P1, P2 Compact, P2 Standard, P2 Large를 차례로 적용한다.
3. Materials navigator/result/datasheet, Modeling Data/Fit/Export, Activity 정상·긴 history·decision/error/
   recovery, Administration Database design/Records만 비교한다.
4. shell, 실제 사용 폭, pane/table/form/graph/native preview, typography/control/row/splitter, overflow,
   column allocation과 graph geometry를 측정한다. pane resize/collapse/reset/persistence도 별도로 조작한다.
5. 실제 browser zoom 200%에서 action reachability와 양방향 page scroll을 검사한다.
6. reload/read-back 뒤 같은 exact product state를 보존한다. 후보 비교 중 API write는 0건이어야 한다.

Forbidden shortcuts는 route별 4K media rule, CSS `zoom`, blanket `transform: scale`, DPR/resolution 기반
자동 적용, 비균일 SVG stretch와 filler data다. prototype stylesheet에는 이 방식이 없다.

## Candidate disposition

| 후보 | 측정 결론 | 장점 | 비용·위험 | Codex disposition |
| --- | --- | --- | --- | --- |
| P1 | semantic full-shell/pane 정책은 유효하다. Administration 3840 used width를 1600px에서 3512px로 늘리고 form은 760px에 묶었다. 200% zoom Export preview도 0px에서 240px로 회복했다. 명시적으로 펼친 context가 pane 최소값 충돌로 0px를 받으면 viewport/DPR가 아니라 실제 배정 폭을 기준으로 bounded overlay를 쓰는 공통 정책도 검증했다. | 구현 표면이 작고 OS/browser scale을 그대로 존중한다. | 실제 4K 100%에서 개인별 글자·control 가독성을 앱에서 보완할 선택지가 없다. | 단독 채택보다 P2의 layout 기반으로 유지 |
| P2 Compact | P1과 같은 semantic layout에 current compact token을 그대로 사용했다. 픽셀 결과와 측정값은 의도적으로 P1과 동일하다. | 1366/1440과 높은 OS scale에서 정보량을 가장 많이 보존한다. | 2560/3840의 물리적 100% 화면에서 작게 느껴질 수 있으나 실제 장비 판정은 아직 없다. | 사용자 선택 범위의 하한으로 권고 |
| P2 Standard | Administration 3840 used width 3488px(90.8%), center 2400px, form 800px를 만들었다. Activity long-history row median은 53px에서 57px, app/command bar token은 46/38px에서 50/42px로 증가했다. page horizontal overflow와 기능 손실은 0이었다. | current compact보다 읽기·조작 여유를 주면서 1366/1440에서도 대표 task를 유지한다. | 모든 route가 아직 모든 shared token을 소비하지 않는다. 실제 물리 가독성과 최종 값은 #223에서 확인해야 한다. | **잠정 기본으로 권고; 제품 소유자 승인 대기** |
| P2 Large | 가장 큰 typography/control/row/pane token을 비교했다. 3840 Administration form은 840px, nav 312px이며 Activity history median row는 67px다. | 사용자가 더 큰 UI를 명시적으로 선택할 수 있다. | 1366 Activity table에 4px local horizontal overflow가 생기고 긴 목록의 세로 비용이 커진다. 실제 4K 없이 기본값으로 정할 근거가 없다. | 선택 범위의 상한으로만 권고 |
| P3 | 100% capture는 CSS viewport=outer width, DPR 1이었다. 같은 outer 1920×1080에서 browser zoom 200%는 CSS viewport 960×540, DPR 2, `visualViewport.scale=1`이었다. 같은 DPR 신호가 browser zoom만으로 생겨 OS/device scale과 구분되지 않는다. | 초기 사용자 조작이 적을 수 있다. | 잘못된 자동 tier, browser zoom 이중 확대와 환경별 oscillation 위험이 있다. 브라우저 내부는 host/default zoom을 별도 preference로 관리하지만 page가 안정적인 물리-display 원인을 받지 못한다. | **기각. 제품 코드 prototype 없음** |

P3 근거는 [MDN `devicePixelRatio`](https://developer.mozilla.org/en-US/docs/Web/API/Window/devicePixelRatio),
[Chromium `HostZoomMap`](https://chromium.googlesource.com/chromium/src/+/master/content/public/browser/host_zoom_map.h),
[Chromium zoom preferences](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/common/pref_names.h)와
이번 browser 신호 측정이다. viewport/DPR/resolution을 자동 density 입력으로 제품 코드에 넣지 않았다.

## Proposed P2 contract — not yet approved

제품 소유자가 P2를 승인할 때 #184가 다음을 하나의 공통 계약으로 구현하는 방안을 권고한다.

- 기본: `Standard`.
- 사용자 범위: `Compact | Standard | Large`만 제공하고 route별 값은 제공하지 않는다.
- reset: 한 번의 공통 `Reset display density`로 `Standard`를 복원한다. pane/column reset과 density reset은
  목적이 다르므로 각각 명시적으로 제공한다.
- 저장: 기존 resizable pane과 같은 browser-local preference 경계에 active user/workspace를 구분하는
  하나의 product-wide density key로 저장한다. route URL, backend profile, domain record나 revision에 넣지
  않는다. cross-device/account sync는 별도 승인 전까지 만들지 않는다.
- 복원: 첫 shell paint 전에 허용된 값을 읽어 `html`의 공통 density attribute에 적용한다. malformed 또는
  과거 값은 `Standard`로 안전하게 복구하고 저장값이 사용자의 새 선택을 자동으로 덮어쓰지 않는다.
- 범위: typography만 키우지 않고 control, row, spacing, pane, splitter, scrollbar, plot label/min-height와
  native preview를 함께 조절한다. 그래프 데이터 geometry는 container 측정으로 다시 계산한다.
- pane 충돌: 사용자가 context를 펼쳤는데 shared pane minima 때문에 실제 배정 폭이 0이면 actual pane
  allocation을 관찰해 bounded overlay로 제시한다. viewport, DPR, route 이름으로 이 상태를 추정하지 않는다.

### Proposed shared token range

`Compact`는 current main 값을 그대로 사용한다. 아래는 prototype에서 실제 적용·측정한 값이며 승인 전
production contract가 아니다.

| Token group | Compact | Standard | Large |
| --- | ---: | ---: | ---: |
| data / emphasis / metadata / table heading font | 13 / 14 / 12 / 11px | 14 / 15 / 13 / 12px | 16 / 17 / 14 / 13px |
| control / interactive / input min height | 36 / 32 / 38px | 38 / 34 / 40px | 40 / 38 / 44px |
| work row / navigator row | 46 / 26px | 48 / 30px | 52 / 34px |
| pane padding / table cell block×inline | 12 / 11×12px | 14 / 12×14px | 16 / 14×16px |
| navigator default / context default / form max | 264 / 280 / 760px | 288 / 304 / 800px | 312 / 328 / 840px |
| pane / workbench splitter | 5 / 8px | 6 / 9px | 7 / 10px |
| scrollbar track / thumb min | current / current | 14 / 40px | 15 / 44px |
| plot / native preview min height | 360 / 240px in P1/P2 prototype | 400 / 320px | 440 / 360px |
| application / command / status bar | 46 / 38 / 24px | 50 / 42 / 26px | 54 / 46 / 28px |

## Capture provenance and environment

| Item | Record |
| --- | --- |
| Git | `agent/issue-221-high-dpi-decision`, base `ca7c97869522e3fe5d889fdc5f834bd963f85340` |
| Compose | canonical `cmp-local-demo`, `deploy/compose/docker-compose.demo.yml`; existing volumes preserved |
| Browser | Playwright 1.62.0 / headless Chromium; browser zoom 100%, context DPR 1 for the five CSS viewports |
| Required CSS viewports | 1366×768, 1440×900, 1920×1080, 2560×1440, 3840×2160 |
| Zoom audit | actual Chromium default zoom 200%; outer 1920×1080, CSS viewport 960×540, DPR 2, `visualViewport.scale=1` |
| Active Windows display | `\\.\DISPLAY5`, 2560×1440, work area 2560×1392 |
| OS scale signal | registry `LogPixels=144` (150% logical scale signal), `Win8DpiScaling=0` |
| Enumerated displays | AUO C199 34×22cm; Samsung LS27B61x 60×34cm |
| Actual 3840×2160 hardware | unavailable; **`DEFERRED_TO_223`** |
| Capture interval | 2026-08-10 12:22:30Z–13:38:53Z; Materials search was recaptured after the independent-audit correction |
| State | canonical non-production synthetic data; 55 comparison groups share exact state fingerprints across five variants |
| Candidate writes | 0 blocked/attempted product writes after state setup |

The final Materials workflow used exact Record `3508c64c-e1fa-44ff-bdab-610bad02021f`, revision
`c908ad55-6e86-4807-aacd-8389a40d9f5f` (r10), with six published graph nodes. Preparation recovered the
canonical public graph through append-only product APIs when prior E2E runs had advanced the current pointer;
no existing revision, review, link, model or card was deleted or overwritten. The final comparison run reused
that state. Four datasheet waits required extended semantic UI readiness after exact graph API read-back passed;
two Modeling Data waits used one read-only reload after exact selected/included/visible session state matched.
All six retries and read-back details are in the measurement manifest.

## Evidence inventory and integrity

| Artifact | Count / result |
| --- | ---: |
| 100% zoom full-screen originals | 275 = 11 surfaces × 5 viewports × 5 variants |
| Direct 1:1 crops | 540, only 1920/2560/3840; no resize, resampling or interpolation |
| 200% browser-zoom originals | 55 = 11 surfaces × 5 variants |
| Normal measurements | 275 |
| State fingerprints | 55 comparison groups |
| Surface manifests | 11, merged only after every required surface passed |
| PNG files | 870; every file decoded, declared dimensions and SHA-256 validated |
| Intentional equal-byte groups | 172 complete repository groups declared in the structured manifest; unchanged candidate pixels are retained, not altered |
| Output size | 74,593,242 bytes across 882 files |
| Empty/blank heuristic | no decode error; minimum grayscale standard deviation 9.672 |

- [merged structured measurements](images/issue-221-high-dpi-decision/measurements.json)
- [all 100% originals](images/issue-221-high-dpi-decision/originals/)
- [all direct 100% crops](images/issue-221-high-dpi-decision/crops/)
- [all browser zoom 200% originals](images/issue-221-high-dpi-decision/zoom-200/originals/)
- [evidence-only prototype CSS](../../scripts/high_dpi_decision_prototype.css)
- [deterministic capture harness](../../scripts/capture_high_dpi_decision.py)

## Measured geometry

### P2 Standard five-viewport workspace use

Values are `used width / CSS viewport`. Activity intentionally keeps its wide comparison table at a centered,
balanced 2656px maximum at 3840 rather than stretching prose and every row. Materials reserves the bounded
optional context side at 1440+; the result/datasheet primary area still grows. Administration is the #221
input that changes materially.

| Surface/state | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Materials navigator + result | 1358 / 99.4% | 1152 / 80.0% | 1612 / 84.0% | 2252 / 88.0% | 3532 / 92.0% |
| Materials navigator + datasheet | 1358 / 99.4% | 1152 / 80.0% | 1612 / 84.0% | 2252 / 88.0% | 3532 / 92.0% |
| Modeling Data | 1350 / 98.8% | 1424 / 98.9% | 1904 / 99.2% | 2544 / 99.4% | 3824 / 99.6% |
| Modeling Fit | 1350 / 98.8% | 1424 / 98.9% | 1904 / 99.2% | 2544 / 99.4% | 3824 / 99.6% |
| Modeling Export | 1350 / 98.8% | 1424 / 98.9% | 1904 / 99.2% | 2544 / 99.4% | 3824 / 99.6% |
| Activity normal / decision-error / recovery | 1312 / 96.0% | 1386 / 96.2% | 1866–1880 / 97.2–97.9% | 2520 / 98.4% | 2656 / 69.2% |
| Activity long history | 1312 / 96.0% | 1386 / 96.2% | 1866 / 97.2% | 2506 / 97.9% | 2642 / 68.8% |
| Administration Database / Records | 1104 / 80.8% | 1175 / 81.6% | 1568 / 81.7% | 2208 / 86.2% | 3488 / 90.8% |

All P2 Standard rows had page horizontal overflow 0. Long Activity history alone had expected page/local vertical
travel; no surface had unnecessary bidirectional page scroll.

### Candidate comparison at wide viewports

| Surface | Candidate | 1920 used width | 2560 used width | 3840 used width | 3840 outer gutters L/R |
| --- | --- | ---: | ---: | ---: | ---: |
| Materials result/datasheet | baseline | 1613 (84.0%) | 2253 (88.0%) | 3533 (92.0%) | 9 / 298px |
| Materials result/datasheet | P1 | 1613 (84.0%) | 2253 (88.0%) | 3533 (92.0%) | 9 / 298px |
| Materials result/datasheet | P2 Standard | 1612 (84.0%) | 2252 (88.0%) | 3532 (92.0%) | 9 / 299px |
| Modeling Data/Fit/Export | baseline / P1 / P2 Standard | 1904 (99.2%) | 2544 (99.4%) | 3824 (99.6%) | 8 / 8px |
| Activity normal | baseline / P1 / P2 Standard | 1880 (97.9%) | 2520 (98.4%) | 2656 (69.2%) | 592 / 592px |
| Administration Database/Records | baseline | 1586 (82.6%) | 1600 (62.5%) | 1600 (41.7%) | 1252 / 988px |
| Administration Database/Records | P1 / P2 Compact | 1592 (82.9%) | 2232 (87.2%) | 3512 (91.5%) | 296 / 32px |
| Administration Database/Records | P2 Standard | 1568 (81.7%) | 2208 (86.2%) | 3488 (90.8%) | 320 / 32px |
| Administration Database/Records | P2 Large | 1568 (81.7%) | 2184 (85.3%) | 3464 (90.2%) | 344 / 32px at 2560/3840 |

Administration baseline의 2560/3840 1600px island와 좌우 612/348px, 1252/988px 불균형은 실패 입력이다.
P1/P2는 route media rule 없이 three-pane의 semantic middle region만 flex로 만들고 navigator/form을
bounded 상태로 유지한다. left gutter는 Administration section rail의 실제 264–312px 공간이며 빈 shell
margin이 아니다.

### Representative region sizes at 3840×2160

| Surface | Variant | Navigator | Primary table/form | Graph/native preview | Context/form bound |
| --- | --- | ---: | ---: | ---: | ---: |
| Materials search | P2 Standard | 280×2002 | table 3245×66 | N/A | optional context reserve 299px |
| Materials datasheet | P2 Standard | 280×2042 | table 330×240 | graph 2554×238 | datasheet 3246×2042 |
| Modeling Data | P2 Standard | 208×1956 | data band 3586×100 | graph 3592×1720 | N/A |
| Modeling Fit | P2 Standard | 208×2000 | controls 3610×104 | graph 3592×1827 | N/A |
| Modeling Export | P2 Standard | N/A | setup 326×1996 | native preview 3108×1939 | context 360×1996; source graph 339×266 |
| Activity history | Compact / Standard / Large | N/A | table 2589×1141 / 2584×1290 / 2579×1522 | N/A | centered 2643 / 2642 / 2641px |
| Administration Database | baseline | 360×1961 | list 480×1961 | N/A | form 760×1961 |
| Administration Database | P1 / P2 Compact | 264×1961 | list 2488×1961 | N/A | form 760×1961 |
| Administration Database | P2 Standard | 288×1951 | list 2400×1951 | N/A | form 800×1951 |
| Administration Database | P2 Large | 312×1941 | list 2312×1941 | N/A | form 840×1941 |
| Administration Records | baseline | 360×2340 | list 480×2340 | N/A | form 760×2340 |
| Administration Records | P2 Standard | 288×2342 | list 2400×2342 | N/A | form 800×2342 |

Form/graph/table containment pairs detected by the generic rectangle probe are expected DOM nesting, not sibling
collision. Original-resolution review found no unintended clipping or overlap. The only P2 Large local horizontal
overflow at 100% was 4px in the 1366 Activity table; Standard remained 0 and is the recommended default.

### Table allocation, pane behavior and graph reflow

- Materials result columns at 1366/1920/2560/3840 baseline were
  `110/403/258/339`, `131/482/309/405`, `194/715/457/600`,
  `321/1180/755/991px`. P2 Standard preserved the same proportions within 0–2px and local X overflow 0.
- Activity normal columns at 3840 baseline were `520/1249/312/312/208px`; P2 Standard measured
  `520/1247/312/312/208px`. Identity/evidence absorbs the useful width while action/status remain bounded.
- Materials navigator keyboard resize changed 280→360px, collapse reached 0px, double-click reset returned 280px,
  and the existing `react-resizable-panels` localStorage layout survived read-back.
- Modeling navigator keyboard resize changed 208→240px and collapse reached 0px. Current main exposes no Modeling
  navigator reset; this is a named #184 transplant requirement rather than a screen-specific #221 workaround.
- Modeling Data graph changed 1673×641 → 1641×684 after splitter/navigator resize and reset to 1641×641.
  In each state the SVG viewBox followed the rendered frame, one legend and 14 labels remained, and the center hit
  region stayed the interactive SVG.
- Across the five viewports Modeling Data graph grew from 1143×329 to 3593×1721; Fit grew from 1143×435 to
  3593×1827. P2 Standard was within one border pixel of those boxes. Axis/legend/label/hit-region counts stayed
  stable; no non-uniform SVG scale was applied.

## Browser zoom 200%

The table records the P2 Standard reachability audit at actual browser zoom 200%. `Initially clipped` means the
element began outside a local scrollport; each item was then scrolled into view, hit-tested and focused. A tall
splitter may remain geometrically clipped while still reachable. `Functional loss` excludes an unreachable direct
action only when an equivalent primary keyboard contract was actually executed.

| Surface | CSS viewport / DPR | Initial offscreen / clipped | After-scroll unreachable | Page overflow X/Y | Bidirectional | Functional loss |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Materials search | 960×540 / 2 | 2 / 5 | 0 | 0 / 0 | no | 0; explicit details expansion detected a 0px allocation, opened a 304px semantic overlay and direct `Open datasheet` passed |
| Materials datasheet | 960×540 / 2 | 4 / 6 | 0 | 0 / 0 | no | 0 |
| Modeling Data | 960×540 / 2 | 0 / 0 | 0 | 0 / 0 | no | 0 |
| Modeling Fit | 960×540 / 2 | 0 / 0 | 0 | 0 / 0 | no | 0 |
| Modeling Export | 960×540 / 2 | 3 / 4 | 0 | 0 / 0 | no | 0 |
| Activity normal | 960×540 / 2 | 5 / 5 | 0 | 0 / 0 | no | 0 |
| Activity long history | 960×540 / 2 | 40 / 40 | 0 | 0 / 2168 | no | 0 |
| Activity decision/error | 960×540 / 2 | 5 / 6 | 0 | 0 / 0 | no | 0 |
| Activity recovery | 960×540 / 2 | 6 / 6 | 0 | 0 / 0 | no | 0 |
| Administration Database | 960×540 / 2 | 4 / 5 | 0 | 0 / 0 | no | 0 |
| Administration Records | 960×540 / 2 | 54 / 58 | 0 | 0 / 0 | no | 0 |

At 200%, Export native preview height measured baseline 0px, P1/P2 Compact 240px, P2 Standard 320px and
P2 Large 360px, with page X/Y overflow 0 for every variant. This is the clearest functional geometry benefit of
the semantic preview token. [baseline zoom original](images/issue-221-high-dpi-decision/zoom-200/originals/baseline/modeling-export-outer-1920x1080-css-960x540.png)
and [P2 Standard zoom original](images/issue-221-high-dpi-decision/zoom-200/originals/p2-standard/modeling-export-outer-1920x1080-css-960x540.png)
show the comparison.

The Materials correction is also semantic: the existing compact pane solver kept `main` at 718px and left the
expanded context at 0px because the 720px main and 260px context minima cannot both fit a 960px CSS viewport.
The candidate now observes that zero allocation after the user's explicit expansion and presents the context as a
304px bounded overlay. The audit then scrolls, hit-tests and clicks the actual `Open datasheet` button; it does not
substitute the selected-row keyboard shortcut or infer the condition from browser zoom.

## Original full-screen comparison links

The directories contain the exact five-viewport matrix. The links below are the main owner-review entry points;
all images remain original PNGs rather than contact sheets.

| Surface | Baseline 1920 / 2560 / 3840 | P1 3840 | P2 Standard 1920 / 2560 / 3840 | P2 Large 3840 |
| --- | --- | --- | --- | --- |
| Materials result | [1920](images/issue-221-high-dpi-decision/originals/baseline/materials-search/materials-search-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/materials-search/materials-search-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/materials-search/materials-search-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/materials-search/materials-search-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/materials-search/materials-search-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/materials-search/materials-search-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/materials-search/materials-search-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/materials-search/materials-search-3840x2160.png) |
| Materials datasheet | [1920](images/issue-221-high-dpi-decision/originals/baseline/materials-datasheet/materials-datasheet-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/materials-datasheet/materials-datasheet-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/materials-datasheet/materials-datasheet-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/materials-datasheet/materials-datasheet-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/materials-datasheet/materials-datasheet-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/materials-datasheet/materials-datasheet-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/materials-datasheet/materials-datasheet-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/materials-datasheet/materials-datasheet-3840x2160.png) |
| Modeling Data | [1920](images/issue-221-high-dpi-decision/originals/baseline/modeling-data/modeling-data-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/modeling-data/modeling-data-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/modeling-data/modeling-data-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/modeling-data/modeling-data-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-data/modeling-data-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-data/modeling-data-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-data/modeling-data-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/modeling-data/modeling-data-3840x2160.png) |
| Modeling Fit | [1920](images/issue-221-high-dpi-decision/originals/baseline/modeling-fit/modeling-fit-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/modeling-fit/modeling-fit-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/modeling-fit/modeling-fit-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/modeling-fit/modeling-fit-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-fit/modeling-fit-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-fit/modeling-fit-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-fit/modeling-fit-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/modeling-fit/modeling-fit-3840x2160.png) |
| Modeling Export | [1920](images/issue-221-high-dpi-decision/originals/baseline/modeling-export/modeling-export-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/modeling-export/modeling-export-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/modeling-export/modeling-export-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/modeling-export/modeling-export-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-export/modeling-export-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-export/modeling-export-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/modeling-export/modeling-export-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/modeling-export/modeling-export-3840x2160.png) |
| Activity normal/history/error/recovery | [baseline surface directory](images/issue-221-high-dpi-decision/originals/baseline/) | [P1 directory](images/issue-221-high-dpi-decision/originals/p1/) | [P2 Standard directory](images/issue-221-high-dpi-decision/originals/p2-standard/) | [P2 Large directory](images/issue-221-high-dpi-decision/originals/p2-large/) |
| Administration Database | [1920](images/issue-221-high-dpi-decision/originals/baseline/administration-database/administration-database-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/administration-database/administration-database-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/administration-database/administration-database-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/administration-database/administration-database-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/administration-database/administration-database-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/administration-database/administration-database-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/administration-database/administration-database-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/administration-database/administration-database-3840x2160.png) |
| Administration Records | [1920](images/issue-221-high-dpi-decision/originals/baseline/administration-records/administration-records-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/baseline/administration-records/administration-records-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/baseline/administration-records/administration-records-3840x2160.png) | [P1](images/issue-221-high-dpi-decision/originals/p1/administration-records/administration-records-3840x2160.png) | [1920](images/issue-221-high-dpi-decision/originals/p2-standard/administration-records/administration-records-1920x1080.png) · [2560](images/issue-221-high-dpi-decision/originals/p2-standard/administration-records/administration-records-2560x1440.png) · [3840](images/issue-221-high-dpi-decision/originals/p2-standard/administration-records/administration-records-3840x2160.png) | [Large](images/issue-221-high-dpi-decision/originals/p2-large/administration-records/administration-records-3840x2160.png) |

## Direct 100% crop links

- Header: [Materials baseline 3840](images/issue-221-high-dpi-decision/crops/baseline/materials-search/materials-search-3840x2160-header-100pct.png),
  [P2 Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/materials-search/materials-search-3840x2160-header-100pct.png)
- Navigator: [Materials baseline 3840](images/issue-221-high-dpi-decision/crops/baseline/materials-search/materials-search-3840x2160-navigator-100pct.png),
  [P2 Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/materials-search/materials-search-3840x2160-navigator-100pct.png)
- Result table: [Materials baseline 3840](images/issue-221-high-dpi-decision/crops/baseline/materials-search/materials-search-3840x2160-table-100pct.png),
  [P2 Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/materials-search/materials-search-3840x2160-table-100pct.png)
- Datasheet form/graph: [form Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/materials-datasheet/materials-datasheet-3840x2160-form-100pct.png),
  [graph Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/materials-datasheet/materials-datasheet-3840x2160-graph-100pct.png)
- Modeling Data graph: [1920](images/issue-221-high-dpi-decision/crops/p2-standard/modeling-data/modeling-data-1920x1080-graph-100pct.png),
  [2560](images/issue-221-high-dpi-decision/crops/p2-standard/modeling-data/modeling-data-2560x1440-graph-100pct.png),
  [3840](images/issue-221-high-dpi-decision/crops/p2-standard/modeling-data/modeling-data-3840x2160-graph-100pct.png)
- Modeling Fit controls/graph: [controls 3840](images/issue-221-high-dpi-decision/crops/p2-standard/modeling-fit/modeling-fit-3840x2160-form-100pct.png),
  [graph 3840](images/issue-221-high-dpi-decision/crops/p2-standard/modeling-fit/modeling-fit-3840x2160-graph-100pct.png)
- Native preview: [baseline 3840](images/issue-221-high-dpi-decision/crops/baseline/modeling-export/modeling-export-3840x2160-preview-100pct.png),
  [P2 Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/modeling-export/modeling-export-3840x2160-preview-100pct.png)
- Activity long table: [baseline 3840](images/issue-221-high-dpi-decision/crops/baseline/activity-history/activity-history-3840x2160-table-100pct.png),
  [P2 Standard 3840](images/issue-221-high-dpi-decision/crops/p2-standard/activity-history/activity-history-3840x2160-table-100pct.png)
- Administration Database list/form: [baseline table](images/issue-221-high-dpi-decision/crops/baseline/administration-database/administration-database-3840x2160-table-100pct.png),
  [Standard table](images/issue-221-high-dpi-decision/crops/p2-standard/administration-database/administration-database-3840x2160-table-100pct.png),
  [baseline form](images/issue-221-high-dpi-decision/crops/baseline/administration-database/administration-database-3840x2160-form-100pct.png),
  [Standard form](images/issue-221-high-dpi-decision/crops/p2-standard/administration-database/administration-database-3840x2160-form-100pct.png)
- Administration Records list/form: [baseline table](images/issue-221-high-dpi-decision/crops/baseline/administration-records/administration-records-3840x2160-table-100pct.png),
  [Standard table](images/issue-221-high-dpi-decision/crops/p2-standard/administration-records/administration-records-3840x2160-table-100pct.png),
  [baseline form](images/issue-221-high-dpi-decision/crops/baseline/administration-records/administration-records-3840x2160-form-100pct.png),
  [Standard form](images/issue-221-high-dpi-decision/crops/p2-standard/administration-records/administration-records-3840x2160-form-100pct.png)

## Q-01–Q-20 Main disposition

This is a candidate-policy review, not the #184 all-route pass. `Pass` below means the representative #221 state
preserved the existing contract under the prototype. Product-owner policy approval remains pending.

| ID | Result | Evidence / boundary |
| --- | --- | --- |
| Q-01 | pass | Materials navigator local overflow and 200% collapse/expand remain reachable; a zero-width expanded context uses the measured shared overlay policy. |
| Q-02 | pass | Result and Activity long table use actual local/page travel; no filler was added. |
| Q-03 | pass | Compact remains current 26px navigator token; Standard/Large use only shared 30/34px proposals. |
| Q-04 | pass | Fit keeps the 104px six-group control band and dominant graph in all candidates. |
| Q-05 | pass | Data/Fit axis, units and frame remain visible in originals and graph crops. |
| Q-06 | pass | One compact legend remains separate from status and controls. |
| Q-07 | pass | viewBox follows measured frame within the border pixel; no non-uniform stretch. |
| Q-08 | pass | Representative material-response semantics are unchanged from main. |
| Q-09 | pass | splitters and scroll containers are reachable; 200% audit scrolls, hit-tests and focuses controls, and directly clicks `Open datasheet`. |
| Q-10 | pass | Fit legend stays in the measured graph region without collision in representative candidates. |
| Q-11 | pass | Modeling navigator topology and flat divider rhythm are unchanged. |
| Q-12 | pass | Export exact source/setup/context are unchanged; candidate only changes shared geometry token. |
| Q-13 | pass | Export compact row grammar remains; no prose/filler was introduced. |
| Q-14 | pass | readiness/action state is unchanged and remains reachable. |
| Q-15 | pass | graph domain, zero anchor, paths and labels are unchanged; only container geometry reflows. |
| Q-16 | pass | native preview remains dominant at 100% and regains a non-zero 200% block in P1/P2. |
| Q-17 | pass | Administration list grows while edit form remains 760/800/840px bounded. |
| Q-18 | not-applicable | #221 does not change Add/edit lifecycle or stored Record projections. |
| Q-19 | not-applicable | #221 does not change Link Type cardinality or exact revision pins. |
| Q-20 | provisional pass for representative geometry | P1/P2 remove the measured Administration island without route-specific scaling. P2 Standard retains full-shell geometry and no page-X overflow. Full route/state application belongs to #184; physical readability is `DEFERRED_TO_223`. |

## #184 transplant list after owner approval

1. Add one shared density provider/attribute and the approved Compact/Standard/Large token sets; no route-specific
   display tier or DPR automation.
2. Implement the approved browser-local select/reset/restore contract and malformed-value recovery before shell
   paint. Do not create account/server persistence without separate approval.
3. Move Administration Database design and Records to the shared semantic three-pane policy; retain bounded
   navigator/form and elastic center list/table. Remove the 1600px work island without page CSS patches.
4. Apply the semantic native-preview minimum to the shared preview region and revalidate Export setup/context at
   browser zoom 200%.
5. Audit every route/state for token consumption. Components that still hard-code font/control/row/splitter values
   must consume shared tokens before P2 can be called product-wide.
6. Revalidate table allocation. Preserve bounded identity/status/action columns, flexible data/evidence columns and
   reset/persistence; specifically remove the 4px P2 Large Activity local overflow if Large is approved.
7. Add a Modeling navigator reset matching Materials and revalidate pane resize, collapse, reset and persistence
   across viewport class changes and reload.
8. Re-run graph `ResizeObserver` behavior for Data/Process/Fit: frame/viewBox, axes, legend, labels and hit regions
   must update together after every pane change.
9. Implement the shared zero-allocation context policy demonstrated by the prototype: after an explicit expand,
   actual pane allocation below 1px selects a bounded overlay/close path. Revalidate the direct Materials
   `Open datasheet` action without viewport/DPR or route-specific inference.
10. Apply the approved policy to every normal and high-risk loading/empty/error/disabled/long/drawer/popup state at
    all five viewports, update current user-guide captures, and repeat independent visual review.
11. Keep actual Windows 4K 100%·150%·200% physical readability explicitly pending for #223.

## Verification ledger

| Gate | Result |
| --- | --- |
| Compose preflight and healthy canonical services | pass before capture and final rerun; `cmp-local-demo` postgres/api/web accepted |
| Same-state baseline-first capture contract | pass; 55 groups, five exact fingerprints per group |
| Evidence integrity / crop contract | pass; 870 PNGs, 540 direct crops, dimensions/hash/set validated |
| Focused #221 Python contracts and Ruff | pass; 4 focused tests, final 97-test contract bundle, Ruff and Python compile clean |
| Related capture contracts | pass; `test_capture_current_product.py` + `test_high_dpi_decision.py`, 67-test focused run included in the final contract bundle |
| Related Vitest | pass; 60 files, 317 tests |
| Related Playwright | pass; `review-publication-recovery.spec.ts`, 1 test in 19.3s; append-only recovery/read-back preserved |
| Production build | pass; TypeScript, Vite and bundle budget, 0 warnings/errors |
| Browser zoom 200% | pass for representative P2 Standard functionality; no functional loss or bidirectional page scroll |
| Latest Web Interface Guidelines audit | pass for issue-owned CSS/harness against the 2026-08-10 fetched upstream checklist; no production interactive markup added and no forbidden focus/zoom/transition pattern |
| User-guide checker / docs impact / whitespace | pass; 20 guides / 1,236 images, 891 changed files / 0 visual sources, `git diff --check` clean |
| Final full-demo verifier | environment-state failure; preserved append-only state has a selected model without exactly one pending review request; no reset or verifier relaxation performed |
| Pre-publish | pass at the committed clean-worktree boundary; deterministic fingerprint `a0fcd83c36eedb58a8c15634d0e38f5b5d25444c474da302452b4f67f4d089c3` |
| Independent read-only visual audit | pass on re-audit; first-pass Materials 200% direct-action change request was corrected and cleared, with no remaining actionable findings |
| Product Owner decision | **pending** |

## Remaining risks and publication boundary

- The active machine has no physical 3840×2160 display. Virtual 3840 screenshots prove CSS geometry only;
  100%·150%·200% physical readability remains **`DEFERRED_TO_223`**.
- `LogPixels=144` is an OS-scale signal, not evidence for 4K 150% readability. Headless DPR 1 and zoom-200 DPR 2
  further demonstrate why P3 is unsafe.
- Standard/Large token visibility in existing routes is partial because #221 deliberately does not port every
  component. #184 must inventory and migrate remaining literal sizes before claiming product-wide consistency.
- The 200% context overlay exists only in the evidence prototype. #184 must implement the approved shared
  allocation-driven behavior and revalidate its close/focus-return contract across every context-pane consumer.
- Long Activity and Records content legitimately requires vertical/local travel. It must remain one-directional and
  preserve keyboard reachability.
- Final full-demo clean-state verification may be blocked by immutable evidence accumulated by approved E2E runs;
  no data reset or verifier relaxation is permitted. Any such result is recorded as environment state, not hidden.

The draft PR must remain draft. Do not mark #221 complete, transition ready, merge, start #184 or describe this
recommendation as the Product Owner's final policy. The owner decision requested by this packet is:

1. approve P2 as the provisional #184 policy with `Standard` default and the proposed local preference contract;
2. request bounded token/layout changes and recapture; or
3. choose P1 and explicitly accept the absence of an application density control.
