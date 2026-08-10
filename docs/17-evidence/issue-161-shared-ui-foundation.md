# Issue #161 — shared UI foundation evidence

## Disposition

PR #226의 기존 설계를 유지한 채 canonical Compose 제품에서 #161의 shared desktop boundary를
검증했다. 현재 working tree는 84개 current capture를 모두 새로 실행했고, 1366×768, 1440×900,
1920×1080, 2560×1440, 3840×2160 필수 viewport와 등록된 long/empty/invalid/blocked/failed/restored/
delivered/role-aware 상태를 통과했다. 1920/2560/3840 전후 원본 30쌍, 별도 long-tree 1920 전후
1쌍, 1:1 crop 44개를 보존했다.

Main의 원본 해상도 검토와 독립 읽기 전용 시각 검토는 통과했다. Product Owner 최종 검토는 아직
남아 있으므로 PR #226은 draft 상태를 유지하며 ready 전환이나 merge를 하지 않는다. 자동
3840×2160 CSS viewport 캡처는 실제 Windows 4K 물리 가독성 판정이 아니다. Windows 4K
100%/150%/200% 판정은 요청대로 #223에 남긴다.

## Baseline classification and preserved scope

| Area | 시작 상태 | #161의 bounded change |
| --- | --- | --- |
| Application shell | 이미 전체 viewport 사용 | 보존 |
| Materials search/detail/card preview | 로컬 rail과 splitter는 있었으나 primary workspace가 1920px에 제한됨 | shell cap 제거, navigator/context와 실제 overflow 보존 |
| Modeling Data/Process/Fit | graph reflow가 있었으나 wide width/height cap이 남음 | 공통 elastic shell 사용, stage별 graph chrome 보존 |
| Modeling Export | 3-pane task의 outer task가 1920px에 제한됨 | native preview를 elastic하게 하고 Setup/context는 읽기 좋은 범위로 유지 |
| Activity | shared compact rhythm과 2656px comparison pane이 구현됨 | 기존 구조 보존, long-state rail을 모든 viewport에서 실제 overflow로 검증 |
| Administration | 3-pane editor와 Record workflow가 구현됐으나 4K에서 한쪽 cluster/form stretch가 남음 | 기존 topology를 유지하고 공통 centered workgroup/form bound 적용 |
| Display profile | 승인된 Compact/Standard/Large 선택 없음 | 선택하지 않음; #221/#184 책임 보존 |

API, persistence, immutable revision, review/release, solver mapping, authorization 계약은 바꾸지 않았다.
제품 row를 채우기 위한 filler, 중복 Record, CSS `zoom`, blanket `transform: scale`, 비균일 SVG
stretch, 2560/3840 route-only override도 추가하지 않았다.

## Primary journey and acceptance

1. 사용자는 Materials에서 검색하거나 tree를 탐색하고 exact Material revision을 열어 datasheet와
   solver card를 확인한다. shell은 viewport를 사용하고 navigator/context는 bounded 상태를 유지한다.
2. 같은 session에서 Modeling Data → Process → Fit → Export를 이동한다. exact source와 saved result
   pointer는 유지되고 graph/native preview만 남는 폭을 사용한다. 저장된 Fit을 복원한 `Saved current`
   상태는 StrictMode의 자동 preview 평가로 덮어쓰이지 않는다.
3. Reviewer는 Activity의 전체 role-correct request list와 별도 Recent outcomes를 확인한다. long 상태는
   실제 local overflow와 조작 가능한 rail을 가진다.
4. Administrator는 Database design과 Record registration을 연다. shell은 full viewport이고 의미상
   관련된 workgroup은 가운데 정렬되며 navigator와 form은 읽기 좋은 범위에 남는다.
5. reload/read-back 뒤 exact revision, selected model, review request, solver card, Processing/Fit Output
   관계가 바뀌지 않는다. 실패·blocked 상태는 기존 recovery를 유지하며 `latest` fallback을 만들지 않는다.

## Canonical Compose and capture provenance

| Item | Evidence |
| --- | --- |
| Git worktree | `agent/issue-161-shared-ui-foundation`, `e095ef5d1f4d26af65ad38ebbbef922f129626cf + PR #226 working tree` |
| Compose | project `cmp-local-demo`, `deploy/compose/docker-compose.demo.yml`; PostgreSQL/API/worker/web healthy |
| Preflight | pass; canonical configuration accepted without deleting data |
| Pre-capture product verification | `uv run python scripts/verify_full_demo.py --api-base-url http://127.0.0.1:5173/api/v1` pass |
| Post-capture product verification | blocked at the clean-demo assertion `metal selected model does not have exactly one pending review request`; the capture flows had appended 44 legitimate projected models and only one retained the seeded pending review, so no reset or verifier relaxation was used |
| Browser | Playwright 1.62.0, Chromium 151.0.7922.34, headless Windows, zoom 100%, DPR 1 |
| Host display | `\\.\DISPLAY5`, 2560×1440, 96 DPI, 100%; physical 4K not present |
| Full capture | `uv run --with playwright python scripts/capture_current_product.py --base-url http://127.0.0.1:5173` |
| Capture window | 2026-08-09 22:55:39+09:00 through 23:45:52+09:00 |
| Current set | exactly 84 PNGs; all five required viewport families present; atomic replacement validated |

Catalog bindings와 review 승인은 제품 API를 사용했다. 직접 DB mutation, data reset, 검증 우회는 하지
않았다. Administration의 centered workgroup 보정 뒤 Database/Records만 다시 캡처했고, 3840 Activity
long state에서 rail이 실제로 생기지 않은 것을 원본 검토에서 발견한 뒤 capture-only browser-local
recovery history 20건을 추가했다. 최종 Activity long fixture는 immutable server 결정 10건,
browser-local solver-card 활동 20건, 성공한 recovery outcome 20건이며 모든 history viewport에서
overflow가 없으면 capture가 실패한다.

전체 E2E를 반복 실행하면서 review-publication recovery가 의도적으로 DP780 Record의 current pointer를
새 draft revision으로 전진시켰다. 각 검증 뒤 Reviewer decision과 두 active Record Link revision을 제품
API로 append하고 exact current revision에서 두 관계가 보이는지 read-back했다. 기존 revision, review,
link, model, card는 삭제하거나 덮어쓰지 않았다.

## Approved references and comparison packet

승인된 #167 원본 14개를 구현 판단 전에 원본 해상도로 열었다. Materials 3개, Modeling 4개,
Activity 1개, Administration 6개이며 exact path와 SHA-256은 sidecar에 기록했다. 레퍼런스는 bounded
navigator/context/form과 elastic table/plot/native preview의 관계를 일관되게 보여 준다.

- [structured visual sidecar](images/issue-161-shared-ui-foundation/visual-evidence.yaml)
- [immutable before originals](images/issue-161-shared-ui-foundation/before/)
- [before 100% crops](images/issue-161-shared-ui-foundation/crops/before/)
- [after 100% crops](images/issue-161-shared-ui-foundation/crops/after/)
- [current after originals](../user-guide/images/current/)

Before 31개는 Git HEAD의 PNG blob을 `git archive`로 정확히 추출했으며 after로 재표시하거나 resize하지
않았다. Crop 44개는 Pillow direct crop으로 만들었고 resize/resampling/interpolation은 없다. Sidecar는
각 before/after/crop의 path, source rectangle, dimensions, SHA-256, command, environment를 기록한다.
Main은 승인 레퍼런스 14개, before 31개, 최종 after 84개, crop 44개를 모두 원본 해상도로 열었다.
정상적으로 같은 픽셀이 나온 10개 hash group은 screenshot manifest에 exact path와 이유를 명시했다.
여기에는 1920에서 변화가 없는 Fit 원본/legend와 Process axis, 이전 capped geometry에서 같은 픽셀을
가진 baseline crop이 포함된다. 중복 검사를 피하려고 PNG metadata나 픽셀을 바꾸지 않았다. 검증기는
명시된 evidence-only group 또는 evidence와 current 한 장의 조합만 허용하며 current-current 중복은
계속 거부한다.

대표 비교 결과는 다음과 같다.

- Materials: shell/result/datasheet는 viewport를 사용하고 navigator/main boundary와 실제 local rail은
  유지된다. short/empty 결과에는 fake result rail이 없다.
- Modeling: Process/Fit axes·units·legend는 잘리지 않고 plot viewBox가 rendered frame에 맞춰 다시
  계산된다. Export native preview가 남는 폭을 사용하고 Setup/Mapping-Fit context는 bounded 상태다.
- Activity: 3840에서도 2656px comparison pane이 균형 있게 놓이고 50-item Recent outcomes에는
  distinct local track/thumb가 보인다.
- Administration: measured Database workgroup은 1920에서 x=296/w=1592, 2560에서 x=612/w=1600,
  3840에서 x=1252/w=1600이다. property form은 736px로 유지되며 양쪽 gutter가 균형을 이룬다.
- 공통: page-level horizontal overflow, 1920px work island, route-specific high-resolution override,
  distorted SVG, scrollbar overlap, clipped primary control을 찾지 못했다.

## Main qualitative review — Q-01 through Q-20

| ID | Result | Direct evidence and rationale |
| --- | --- | --- |
| Q-01 | pass | `materials-search-long-*`; navigator에 독립 local track/thumb가 보임 |
| Q-02 | pass | long/short/empty Materials originals; long result만 rail을 가짐 |
| Q-03 | pass | long-tree 1920 1:1 crop과 1366/1440 originals; 26px row grid, 분리된 disclosure/glyph/label, full-value affordance 보존 |
| Q-04 | pass | `modeling-fit-*`; 104px ribbon의 여섯 group, Remove step, Candidate parameters, 28px action이 graph를 침범하지 않음 |
| Q-05 | pass | Process graph-axis 1:1 crops와 Fit originals; title/unit/tick/frame collision이나 detached x-title 없음 |
| Q-06 | pass | Fit graph-legend crops; curve identities는 compact plot legend이며 footer/status와 분리됨 |
| Q-07 | pass | five-viewport Process/Fit originals와 capture geometry; SVG viewBox가 rendered frame과 일치하고 stroke/glyph 비율 유지 |
| Q-08 | pass | `material-detail-*`; positive initial yield at zero plastic strain인 response와 정확한 true stress/plastic strain labeling 유지 |
| Q-09 | pass | Materials/Activity 1:1 rail crops; reserved track와 proportional thumb가 픽셀에서 구분되고 capture가 pointer/wheel/keyboard 결과를 검증 |
| Q-10 | pass | Fit legend crops와 collision gates; legend는 curve-free quadrant에 있고 axis/state/extrapolation과 겹치지 않음 |
| Q-11 | pass | `modeling-fit-*`; flat pane rhythm, sentence-case group, restrained selection과 curve controls 유지 |
| Q-12 | pass | `modeling-export-*`; exact selected model branch, capability-backed unit selector, Mapping details 경계 유지 |
| Q-13 | pass | Export originals; Setup/result row grammar와 한 줄 consequence/recovery 유지 |
| Q-14 | pass | Export normal/blocked/delivered states; readiness가 한 곳에서 exact blocker/review/action과 일치 |
| Q-15 | pass | Data/Process/Fit/detail originals; domain headroom, zero anchor, units, legend placement이 viewport별로 유지 |
| Q-16 | pass | Export native-preview 1:1 crops; preview가 dominant이고 Setup/context와 genuine local scroll이 독립적임 |
| Q-17 | pass | Administration Database/Records originals; identity-first list와 일반 property wording, readable complete values 유지 |
| Q-18 | not-applicable | #161 target capture는 Add Table/Attribute와 alternate Record preview를 새로 승인하는 unit이 아니다. Database/Records의 기존 navigator/list/form topology만 변경 없이 재검증했고 lifecycle contracts는 보존했다. |
| Q-19 | not-applicable | #161 target state는 Link Type endpoint/cardinality 또는 lineage branching을 편집하지 않는다. 해당 domain behavior와 exact pins는 변경하지 않았다. |
| Q-20 | pass (deterministic geometry) | 1920/2560/3840 originals와 shell/navigator/graph/native-preview/form crops; full shell, elastic primary regions, bounded secondary regions, balanced gutters를 확인. 실제 Windows 4K 물리 판독성은 Q-20 규정대로 #223에서 미승인 상태로 남음 |

## Independent read-only visual review

2026-08-10 00:47+09:00의 단일 독립 감사 판정은 `approve`, actionable finding은 0건이다. 감사자는
current 원본 84개, immutable before 원본 31개, direct 100% crop 44개를 모두 원본 해상도로 열고,
#167 승인 normal/exception 레퍼런스와 sidecar SHA-256을 대조했다. 1920/2560/3840 비교는 Q-20의
full shell, elastic primary surface, bounded secondary pane, balanced Administration group을 뒷받침하고
work island, filler, clipping, axis/unit/legend/rail 손상을 보이지 않았다. 이 판정은 Product Owner 승인이나
publication cleanliness를 대신하지 않으며 실제 Windows 4K 물리 가독성은 #223에 남는다.

## Verification ledger

| Gate | Result |
| --- | --- |
| Compose preflight and healthy services | pass |
| Full demo verification | pre-capture pass; post-capture clean-demo-only selected-model assertion blocked by accumulated immutable model projections, with no reset or verifier bypass |
| Final focused Python contracts | 99 passed (`test_user_guide`, `test_documentation_impact`, `test_capture_current_product`, `test_shared_ui_foundation`) |
| Common Processing Workbench focused Vitest | 23 passed |
| Full Python | 1,165 passed, 88 skipped, 2 failed in unchanged authority files: `test_root_agent_guidance_stays_within_context_budget` sees 10,319 checkout bytes over the stale 8,192-byte cap; `test_cold_start_routes_user_work_in_product_order` expects the retired exact text `#161 공통 화면 정리`. `AGENTS.md` and `docs/13-delivery/backlog.md` have no PR #226 diff. |
| Python lint / architecture / contracts | `ruff check .`, architecture check, contract lint, and compatibility check pass |
| Full Python type check | 63 pre-existing errors in 10 unchanged files; no changed #161 file is reported |
| Web production build | pass, including bundle budget |
| Full web unit/component suite | 60 files, 316 tests passed |
| Full canonical Compose Playwright E2E | 7 tests passed in 2.0 minutes; viewport occupancy, Activity tabs, exact card scoping, local scroll, governed download, and review-publication recovery all passed |
| User-guide inventory | pass: 20 guides, 84 current captures, 3 navigation entries, 129 classified Markdown files, 351 links, 325 images |
| Documentation impact | pass: worktree mode, 181 changed files and 11 visual sources classified |
| Whitespace | `git diff --check` pass; PowerShell reports only expected LF-to-CRLF working-tree warnings |
| Independent read-only visual review | pass / `approve`; findings 0; all 84 current, 31 before, and 44 1:1 crops opened at original resolution |
| Product Owner review | pending |

## Remaining publication boundary

1. Present this packet and the 1920/2560/3840 original/crop comparison to the Product Owner.
2. Keep PR #226 draft. A separate explicit owner instruction is required for commit, push, ready transition,
   or merge.
