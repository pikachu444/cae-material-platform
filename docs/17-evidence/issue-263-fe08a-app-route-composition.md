# Issue #263 FE-08A App·route composition evidence

상태: Main acceptance PASS, canonical independent audit APPROVE, publication 전
기준선: `origin/main` `4d0ef93ff4b21dc66d298ac86732a6a71fdb3603`
브랜치: `codex/issue-263-fe08a-app-routing`
권위: #249, #263, `frontend-refactoring-roadmap.md`, frontend architecture/UI contract

## 작업 판정과 범위

기존 route·session 동작은 **complete**, app ownership은 **partial**이었다. `app.tsx`가 lazy import,
browser history/popstate, route parsing, product-session refresh/retry, legacy page workflow와 shell
composition을 함께 소유했다. FE-08A는 동작을 새로 만들지 않고 다음 누락 경계만 분리한다.

| 경계 | FE-08A owner | 보존 계약 |
| --- | --- | --- |
| browser location | `app/navigation.ts` | pathname+query가 단일 truth, 동일 target 중복 push 없음, popstate·top reset |
| typed route registry | `app/routes.ts` | canonical/legacy path, query, exact revision pin, default fallback |
| product session | `app/product-session.tsx` | loading, signed-out, retry, stored demo persona, timed refresh, production bearer |
| lazy page composition | `app/route-composition.tsx` | public feature entry 우선, route별 기존 props와 Suspense boundary |
| app-owned compatibility pages | `app/legacy-route-pages.tsx` | 기존 copy·DOM·class·API/type 계약 |
| composition root | `app.tsx` | session, density provider, application shell, Suspense와 route composition |

`app.tsx` registered hotspot은 1,101행에서 composition-only 48행으로 축소되었으며 guard baseline의
hotspot entry를 제거했다. 새 router/state/server-state dependency는 없다.

## Primary journey와 복구

Setup은 synthetic browser fixture와 현재 public feature entry를 사용한다. 사용자는 `/materials`에서
검색하고 exact Material/Record revision을 열어 reload·Back 뒤 검색 문맥을 읽고, exact Card를 열거나
Card가 없으면 exact Material revision query로 Modeling Data를 시작한다. 보이는 검색, detail, native
preview와 Modeling workspace는 그대로이며 URL의 `record_id`, `record_revision_id`,
`material_revision_id`, `stage`가 read-back truth다. 서버나 다른 session의 latest/first/global output은
사용하지 않는다.

복구 사례는 demo-session 시작 실패 뒤 `Try again` 한 동작으로 같은 `/materials?q=DP780` route를
보존해 재개한다. 별도 negative 사례는 unsupported/missing exact solver-card `kind`와 unknown path가
기존 Materials fallback을 사용하고 원 query를 잃지 않는 것이다.

## Route와 compatibility inventory

- Canonical: Materials search/detail/tabs/new, exact Record/Card, Modeling stage, Activity,
  Administration Database/Format definitions/Records/Access, bulk export, exact Material Model,
  Neutral Material와 Solver Card revision.
- Legacy: Material `testing|datasets|models|governance` area, Catalog explorer/schema/records,
  Tests/Datasets/Models/Governance hub, `/datasets/test-json`, `/datasets/import`,
  `/datasets/processing`, `/jobs-reviews`, `/access`.
- App-owned root compatibility consumers: Activity(`/activity`, `/jobs-reviews`), Modeling
  (`/modeling`, `/datasets/processing`), Catalog explorer, governed import, bulk export, canonical Test
  Data와 exact domain pages. Owning feature가 같은 route-level contract를 public entry로 제공한 뒤만
  root import를 제거한다.
- `ModuleHubPage`는 네 legacy hub만 소비하며 #331의 live route evidence 뒤 retire한다.
  `MaterialCreatePage`는 `/materials/new`만 소비하며 FE-08B/08C 경계 뒤 승인된 Materials ownership
  unit에서 이동한다.

## 검증 기록

| Gate | Main 결과 |
| --- | --- |
| pure parser + composition + navigation/popstate + existing app/session tests | PASS — 4 files, 73 tests |
| full frontend unit/component suite | PASS — 77 files, 498 tests; unrelated pre-existing React `act(...)` warnings only |
| frontend guard | PASS — 0 violation; app hotspot retired; unchanged legacy label 5건만 exact #263 exception, #331 removal |
| frontend guard rule tests | PASS — 18 tests |
| architecture/dependency/cycle guards | PASS — architecture checker and 29 architecture tests |
| production TypeScript/Vite build and bundle budget | PASS — entry 242,243 B; largest lazy Materials chunk 125,480 B; 0 warning/error |
| bundle policy tests | PASS — 24 tests |
| browser root/navigation/popstate, legacy Activity·Administration reload, session retry | PASS — 3 tests; no unexpected console/page errors |
| browser exact Materials search/detail/card/reload/Back/recovery and Modeling handoff | PASS — existing issue-261 M2 journey 1 test |
| copy/DOM/CSS/layout/screenshot impact | N/A for new capture — production copy, rendered hierarchy, class names and CSS are unchanged; existing component/browser behavior gates pass |
| user-guide integrity | PASS — 21 guides, 123 current captures, 3 navigation items, 4,872 links, 9,322 images |
| navigation contract | PASS — version 28 records browser URL truth, exact identity, compatibility routes and app/public-feature dependency direction |
| generic documentation-impact classifier | N/A by FE-08A authority — it classifies any changed production TSX as visual and requires a new five-viewport screenshot family; this unit's explicit acceptance instead requires no new capture after Main proves no copy/DOM/layout/CSS change. No visual artifact was changed to manufacture a pass. |
| `git diff --check` | PASS — line-ending notices only |
| Compose/database | N/A — pure frontend routing fixture exercises no database write or changed backend contract |

Main은 전체 diff와 evidence를 검사했고 canonical `independent_auditor_terra_high`는 처음에 generic
documentation-impact failure를 blocker로 보았다. 같은 auditor에게 checker의 실제 validator를 다시
제시했다. Validator는 base에 존재한 `.tsx` source에서 byte-identical declaration을 새 `.ts` target으로
옮기는 경우만 허용하므로, base에 없던 세 app composition `.tsx`와 residual이 바뀐 `app.tsx`를 표현할
valid relocation mapping이 없음을 auditor가 확인했다. Foundation exception도 `apps/web/src/design`에만
허용된다. Auditor는 invalid exception metadata, screenshot family 조작 또는 checker 변경이 frozen
FE-08A scope를 넘는다고 판정하고 최종 **APPROVE**했다.

FE-08A does not close #263 or #249. After an authorized FE-08A merge, tracking records the PR/merge SHA
and keeps FE-08B as the next unit.
