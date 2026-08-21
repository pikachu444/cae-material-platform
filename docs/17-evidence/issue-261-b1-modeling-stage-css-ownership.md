# Issue #261 B1 — Modeling stage CSS ownership evidence

## 결과

PR #311 head `4d53d95ce926b96b84e47f9d942127f0853d8ed2`에서 Data → Process → Fit → Export의
CSS 소유권만 stage owner로 이동했다. React/DOM/API/state/copy와 exact revision 계약은 변경하지 않았다.
Main acceptance에서 legacy source에서 빠진 505 selector tuple이 owner CSS에 모두 존재하고, owner 쪽
추가 7행은 승인된 normalization peer뿐임을 독립 비교했다. missing 0, unexpected extra 0이다.

## selector disposition

| disposition | count | evidence |
| --- | ---: | --- |
| Data owner move | 9 | roster `69187e3795a42f81dca870c85a7e88b9ccead20da46b9d5b5445d04fb7c22231` |
| Process owner move | 128 | roster `ebe6c392b99f7ade9f4723f7535685077a49b1e63da2d7b22751a3d1b3e7891b` |
| Fit owner move | 66 | roster `c24f124e093af98ca0212750553d6dd90bb15a10a619ac5a76b9898d4ce1d580` |
| Export owner move | 302 | roster `c95b0f68ad1031af4845044714ffbf4c620c0c5ff75c84ba70f48923da6dbf8d` |
| M1E-boundary deferred | 38 | regenerated residual M1A 9 + M1B 29 |
| Existing M1E dependency | 717 | untouched |
| HOLD | 446 | untouched |
| normalization peers | 7 | moved to Export owner; no declaration change |

최종 accounting은 corrected raw `543 = 505 moved + 38 deferred`다. legacy structural delta는
397 touched rule groups, 367 fully removed, 30 partially shrunk이고, regenerated residual은 2,332 rule
groups/2,869 selector rows다. 이 숫자는 inventory guard를 설명하기 위한 값이며 사용자 화면의 품질을
대신하지 않는다.

### CSS-2331 corrected ownership

- historical source: `apps/web/src/styles.css`, rule 629 selector 1, main import rank 0
- context: `@media (min-width: 1101px)`
- selector: `.modeling-target-preview .export-mapping-status.approximated`
- declaration: `color: #826100`
- declaration signature: `4836508e074141e89c0c2c3c15598e35c3b938cb27c88ddafbbd57b7e33a0357`
- disposition: M1D Export owner
- source-group peer `.modeling-target-preview .export-mapping-status.ignored`: legacy HOLD 유지
- target-property peers CSS-0316 Materials delivery/CSS-2375 generic: unchanged

### Seven normalization peers

`export-divider`, `export-properties`, `export-native-preview-shell`, 그 native scroll-shell direct child,
`export-context-heading`, `export-mapping-row`, 그리고 1101px 이상 `export-workspace-grid` rule만 Export
owner로 옮겼다. 다른 normalization selector는 바꾸지 않았다.

## 사용자 journey와 보존 계약

격리 demo에서 synthetic DP780 exact Test Data r1, Mapping Profile r1과 세 exact Test Data ref를 선택한
뒤 다음을 다섯 viewport마다 실행했다.

1. Data에서 현재 입력과 graph를 확인한다.
2. Process에서 preview를 확인하고 결과 이름·사유를 입력해 immutable Processing Output을 저장한다.
3. Fit에서 계산 결과와 후보를 비교하고 사유·warning acknowledgement를 포함해 명시적으로 저장한다.
4. Export에서 exact saved model을 읽고 Abaqus target preview, mapping status와 approximation
   acknowledgement를 확인한다.

각 viewport에서 stage navigation은 `Data | Process | Fit | Export` 네 항목만 노출했고, page horizontal
overflow, workspace horizontal overflow, 축/legend overlap, Process row clipping은 0이었다. canonical
Export는 exact target preview와 `Ready to create` 상태를 유지했다. recovery와 negative 상태의 동작은
React/state 변화가 없는 데 더해 전체 frontend 412 tests와 focused Modeling 131 tests가 검증한다.

## 시각 evidence

- after originals: [`images/issue-261-b1-modeling-stage-css-ownership/after/originals`](images/issue-261-b1-modeling-stage-css-ownership/after/originals)
- direct DPR-1 crops: [`images/issue-261-b1-modeling-stage-css-ownership/after/crops`](images/issue-261-b1-modeling-stage-css-ownership/after/crops)
- compatibility alias: [`images/issue-261-b1-modeling-stage-css-ownership/after/alias`](images/issue-261-b1-modeling-stage-css-ownership/after/alias)
- measurements: [`images/issue-261-b1-modeling-stage-css-ownership/after/measurements.json`](images/issue-261-b1-modeling-stage-css-ownership/after/measurements.json)
- exact image index: [`images/issue-261-b1-modeling-stage-css-ownership/image-index.md`](images/issue-261-b1-modeling-stage-css-ownership/image-index.md)
- bounded capture wrapper: [`images/issue-261-b1-modeling-stage-css-ownership/capture_modeling_stage_ownership.py`](images/issue-261-b1-modeling-stage-css-ownership/capture_modeling_stage_ownership.py)

20 canonical originals와 80 direct 100%-pixel crops를 1366×768, 1440×900, 1920×1080,
2560×1440, 3840×2160, browser zoom 100%, DPR 1에서 만들었다. Main은 20 originals를 원본 해상도로
열었다. 화면은 전 viewport에서 전체 폭을 사용하고 navigator/form은 읽기 좋은 범위를 지키며 graph와
native preview가 남는 공간을 사용한다.

기준 이미지는 Data의 M1A20 canonical 5장과 Process/Fit/Export의 Issue #260 originals 15장이다.
모든 비교 image dimension은 일치했다. Fit 1366/1440/1920은 pixel-identical이다. 나머지 pixel 차이는
Data comparison의 열림 상태, 새 synthetic output label, generated revision UUID/hash와 wide capture의
동적 state 차이에서 발생했고, 원본 검토에서 사용자에게 보이는 geometry/cascade 회귀는 없었다. 최신
사용자 지침에 따라 이 비본질 차이를 맞추기 위한 CSS 변경은 하지 않았다.

`/datasets/processing` 1440 alias는 네 stage를 모두 열고 같은 owner CSS의 clipping/overflow를 검사했다.
Data/Process/Fit은 current session을 유지했다. Export alias가 exact preview 대신 기존 prerequisite
recovery surface를 복원하는 PR #311 이전 상태 계약은 React/state diff가 없는 pre-existing behavior로
기록하고 이 CSS ownership unit에서 고치지 않는다. canonical `/modeling` Export journey는 exact saved
model/preview를 통과했다.

자동 3840×2160은 geometry evidence이며 실제 Windows 4K 물리 가독성을 주장하지 않는다. 최종 physical
readability는 #223에 남는다.

## 환경과 gate 경계

canonical Compose preflight는 다른 병렬 task의 `cmp-local-demo`가 B3 worktree에서 실행 중임을 정확히
거부했다. 그 환경은 변경하지 않았다. 대신 `cmp-demo-test-261b1` 격리 project를 이 worktree source로
build/seed하고 browser journey 후 container, network, local image와 두 disposable volume만 제거했다.

공유 capture helper의 선택적 `.modeling-data-related` heading 필수 assertion은 현재 PR #311 DOM에서
관련 group이 없을 때 timeout한다. task-local wrapper는 이 한 locator만 N/A로 처리하고 Data browser,
graph, primary action, exact Test Data r1/Mapping Profile r1/세 refs를 계속 hard gate로 확인했다. shared
capture script는 수정하지 않았다.

`cmp-check-doc-impact --mode worktree`는 현재 unit의 CSS나 문서 오류가 아니라, unmerged PR #311의
M1A evidence manifest들을 `main` 이후의 동시 변경으로 포함한 뒤 새 proof와 같은 visual-file 집합을
요구해 중단됐다. B1은 7개 CSS를 바꾸지만 이전 M1A manifest들은 Data owner와 `layout.css` 두 파일만
선언한다. 다른 task evidence 수정은 금지되어 이 stacked-branch gate를 N/A로 남긴다. 새 Balanced
integration root가 combined tree를 재생성한 뒤 publication 범위에서 다시 실행한다. 현재 guide 계약,
CSS inventory, frontend guard, 전체 회귀, build와 live 5-viewport acceptance는 별도로 통과했다.

## #249 세 축

- information hierarchy: stage title, bounded navigator/setup, dominant graph/native preview와 primary action이
  같은 우선순위를 유지한다.
- engineering task flow: exact Data → saved Process → explicit Fit selection → Export check 순서와 recovery
  경계가 유지된다.
- responsive/wide-screen composition: 1366–3840에서 one-sided fixed work island, page horizontal overflow,
  control/legend/axis clipping이 없고 plot/preview가 여유 공간을 사용한다.

## Main acceptance

**APPROVE.** 프로덕션 변경은 승인된 8개 경로에만 있고 `main.tsx`, 다른 feature CSS, M1E 717,
deferred 38, HOLD 446은 바뀌지 않았다. corrected CSS-2331은 Export owner에 있으며 CSS-2332
`ignored` peer는 legacy HOLD에 남는다.

- exact movement: 505/505 declaration·context match, missing 0, unexpected 0
- inventory: 2,332 rule groups, 2,869 selector rows, cross-CSS duplicate 7
- frontend: 71 files/412 tests, guard 17/17, actual guard violation 0, build PASS, bundle 24/24
- documentation: user-guide contract 46/46, guide inventory 4,321 images PASS
- browser: canonical 20 originals/80 crops, alias 4, horizontal overflow 0, #249 세 축 PASS
- deferred/N/A: stacked worktree documentation-impact aggregation, physical Windows 4K #223

독립 `reviewer_terra_high`도 **APPROVE**했다. reviewer는 20개 canonical original을 모두 원본
해상도로 열고 production 8경로, 505+38 accounting, CSS-2331/CSS-2332 경계, seven normalization
peers, import order, 24개 measurement의 horizontal-overflow 0과 Q-01~Q-20 적용 결과를 재확인했다.
actionable correctness, cascade, contract, visual, scope finding과 local-commit blocker는 0이다.

## 통합 handoff

이 branch의 inventory JSON, migration plan, guard baseline, guide와 screenshot metadata는 독립 검증을
위한 shared artifact다. 이후 새 Balanced root integration task는 combined tree에서 이를 재생성하고,
다른 parallel branch의 shared artifact와 branch-local generated file을 무조건 cherry-pick하지 않는다.
`main.tsx`, Materials/Administration/Activity CSS, 다른 task owner CSS, M1E 717, deferred 38, HOLD 446은
conflict-free forbidden boundary다.
