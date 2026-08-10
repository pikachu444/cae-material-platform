# Issue #161 제한 후속 — Administration 버튼 의미 체계

## Disposition

PR #226이 squash 병합된 `main@c2283fb0912df93dc4201f216a68aaedea75460b`에서 새 브랜치를
만들어, Administration에 남아 있던 구형 청록색 버튼 체계만 공통 semantic button primitive로
이관했다. Database design, Records & registration, Users & access의 기능, 저장·검토·게시 계약,
권한, revision, 백엔드와 데이터는 바꾸지 않았다. 전역 `.button.primary`도 수정하지 않았다.

이 문서는 #161의 제한 후속 evidence다. Product Owner 승인과 병합 전에는 #161과 #117을 완료
처리하지 않는다. #221의 display-tier 결정은 시작하지 않았으며, draft PR의 ready 전환과 병합도
현재 범위에 포함되지 않는다.

## Baseline classification and button inventory

기존 동작은 **partial**이었다. `--ux-accent: #245ea8`을 사용하는 공통 `.ux-button` primitive가 이미
있었지만 Administration 컴포넌트는 `button primary`, `button secondary`, `text-button`을 계속 사용해
전역 구형 `#147a76`/`#0f6966`, 별도 그림자와 큰 모서리를 상속했다. 성공 상태의 녹색과 일반 주요
동작의 색도 시각적으로 구분되지 않았다.

| 화면/문맥 | Primary | Neutral / secondary | Tertiary / text | Disabled / loading | Danger |
| --- | --- | --- | --- | --- | --- |
| Database command bar | 현재 object의 `Add …` | Refresh, Preview datasheet | 새 정의의 Close, 목록 Refresh | save 중 Add/편집 동작 차단 | 없음 |
| Database edit footer | Publish 한 개 | Check, Save draft | 없음 | 세 동작 모두 save 중 차단 | 없음 |
| Database create form | 해당 `Save …` 한 개 | 관련 없는 생성 보조 동작 | Close | 입력 전제 또는 save 중 차단 | 없음 |
| Records bulk registration | Register checked rows | Read columns / Check rows | Folder reset 등 text action | preview가 없거나 invalid이면 primary 0.5 opacity; busy 중 차단 | 없음 |
| Records record editor | Create/Save immutable revision 또는 Publish | Check, Save draft, review 보조 동작 | 저장된 view 등 text action | busy/필수 입력 누락 시 차단 | 없음 |
| Users & access | Try again, Create assignment | 없음 | 없음 | Saving…은 `aria-busy=true`, progress cursor, 0.72 opacity | Revoke |
| Administration shell | 없음 | task/navigator 선택은 기존 구조 유지 | Open Material Database | 해당 없음 | 없음 |

한 task context에서 채워진 primary는 최대 한 개다. 특히 Database 편집 footer의 Save draft를
neutral로 낮추고 Publish만 primary로 남겼다. 성공은 기존 success status/banner에서만 녹색을
사용하며 primary action에는 `--ux-accent`를 사용한다.

## Primary user journey and preserved outcomes

1. **Setup** — canonical `cmp-local-demo`의 합성 비운영 demo와 Administrator persona를 사용한다.
2. **Actions** — Database design에서 Add Table과 Check/Save draft/Publish를 확인하고, Records에서
   Multiple rows를 연 뒤 disabled Register checked rows를 확인하며, Users & access에서 Create
   assignment와 Revoke를 확인한다.
3. **Visible outcome** — 주요 동작은 공통 파란색, 보조 동작은 중립색, Revoke는 danger 색으로
   보인다. 버튼은 36px 높이, 4px 모서리, 무그림자이며 hover/focus/disabled/loading도 공통 규칙을
   따른다.
4. **Persistence/read-back** — 이 검증은 저장 또는 revoke 성공을 만들지 않는다. 기존 Table,
   Record와 access assignment는 API reload 뒤 동일하게 읽힌다.
5. **Preserved contract/state** — Check, Save draft, Publish, bulk registration, assignment와 revoke의
   handler·request·검증 조건은 유지된다. immutable revision과 권한 계약은 바뀌지 않는다.
6. **Recovery** — 합성 503에서 Saving… 상태와 오류 안내를 확인한 뒤 Create assignment가 다시
   실행 가능해진다. 데이터 reset이나 검증 우회는 없다.
7. **Owned scope** — 세 Administration 컴포넌트의 버튼 class, 공통 danger/loading primitive,
   capture registry, 회귀 테스트, 가이드와 evidence만 소유한다.
8. **Forbidden shortcuts** — Administration 전용 색 override, 전역 legacy primary 변경, success/primary
   혼용, route별 해상도 CSS, CSS zoom/scale, #221 정책 선택을 사용하지 않는다.
9. **Exact acceptance** — 관련 Vitest/contract/Playwright, production build, canonical Compose,
   3화면×5 viewport 전후 원본, 1920/2560/3840 1:1 crop, 상태 원본, docs gate, 독립 읽기 전용 검수,
   pre-publish를 통과하고 draft PR까지만 만든다.

## Implementation boundary

- `configurable-catalog-admin.tsx`, `configurable-catalog-records.tsx`,
  `product-access-center.tsx`의 legacy action class를 공통 `.ux-button` modifier로 이관했다.
- 공통 primitive에 `danger`와 `aria-busy=true` 상태를 추가했다. 색은 `--ux-danger`,
  `--ux-danger-soft`, `--ux-accent`, `--ux-focus-ring` 등 기존 공통 token만 사용한다.
- Administration shell의 Open Material Database는 공통 tertiary primitive를 사용한다.
- `styles.css`의 `.button.primary`, `#147a76`, `#0f6966`은 diff에 없다. 다른 화면의 legacy 버튼을
  전역에서 바꾸지 않았다.
- Python contract는 Administration 대상 파일의 legacy class/청록색 재도입, success token을
  primary로 사용하는 구현, 편집 footer의 복수 primary를 실패시킨다.

## Canonical Compose and deterministic browser evidence

| Item | Result |
| --- | --- |
| Git | `agent/issue-161-admin-button-semantics`, base `c2283fb0912df93dc4201f216a68aaedea75460b` |
| Compose preflight | pass, project `cmp-local-demo`, canonical configuration accepted |
| Services | PostgreSQL/API healthy, migration exit 0, web running; API health pass |
| Rebuild | current working tree로 web/API/migrate 이미지를 재빌드하고 data volume 유지 |
| Full demo verifier | preserved state의 `metal selected model does not have exactly one pending review request`에서 실패; reset·삭제·verifier 완화 없음 |
| Browser | Playwright 1.62.0, Chromium 151.0.7922.34, zoom 100%, DPR 1 |
| Normal captures | Database/Records/Access 각각 1366×768, 1440×900, 1920×1080, 2560×1440, 3840×2160 |
| State captures | primary hover/focus, disabled primary, danger hover, loading primary |
| Crops | 1920/2560/3840의 세 화면 전후 18개; Pillow direct crop, resize/resampling 없음 |

정확한 path, source rectangle, dimensions, SHA-256와 capture command는
[structured visual sidecar](images/issue-161-administration-button-semantics/visual-evidence.yaml)에 있다.

- [immutable latest-main before originals](images/issue-161-administration-button-semantics/before/)
- [canonical current after originals](../user-guide/images/current/)
- [working-tree state evidence](images/issue-161-administration-button-semantics/after/states/)
- [before/after 100% crops](images/issue-161-administration-button-semantics/crops/)
- [approved #167 originals](images/issue-167-service-reference/)

#167 원본 중 Database normal, Table/Attribute draft, Publish blocked, Access normal/revoke/denied와
long invalid 상태를 수정 전에 원본 해상도로 열었다. 레퍼런스의 파란색 값을 복사하지 않고 현재
공통 `--ux-*` token을 사용했다. 기존 승인 이미지는 수정하거나 현재 화면으로 소급 교체하지 않았다.

### Registered artifact index

| Screen | Viewport | Before | After | Direct 100% crop |
| --- | --- | --- | --- | --- |
| Database | 1366×768 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-1366x768.png) | [after](../user-guide/images/current/administration-database-1366x768.png) | N/A |
| Database | 1440×900 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-1440x900.png) | [after](../user-guide/images/current/administration-database-1440x900.png) | N/A |
| Database | 1920×1080 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-1920x1080.png) | [after](../user-guide/images/current/administration-database-1920x1080.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-database-1920x1080-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-database-1920x1080-button-actions-100pct.png) |
| Database | 2560×1440 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-2560x1440.png) | [after](../user-guide/images/current/administration-database-2560x1440.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-database-2560x1440-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-database-2560x1440-button-actions-100pct.png) |
| Database | 3840×2160 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-3840x2160.png) | [after](../user-guide/images/current/administration-database-3840x2160.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-database-3840x2160-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-database-3840x2160-button-actions-100pct.png) |
| Records | 1366×768 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-1366x768.png) | [after](../user-guide/images/current/administration-records-1366x768.png) | N/A |
| Records | 1440×900 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-1440x900.png) | [after](../user-guide/images/current/administration-records-1440x900.png) | N/A |
| Records | 1920×1080 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-1920x1080.png) | [after](../user-guide/images/current/administration-records-1920x1080.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-records-1920x1080-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-records-1920x1080-button-actions-100pct.png) |
| Records | 2560×1440 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-2560x1440.png) | [after](../user-guide/images/current/administration-records-2560x1440.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-records-2560x1440-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-records-2560x1440-button-actions-100pct.png) |
| Records | 3840×2160 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-3840x2160.png) | [after](../user-guide/images/current/administration-records-3840x2160.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-records-3840x2160-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-records-3840x2160-button-actions-100pct.png) |
| Access | 1366×768 | [before](images/issue-161-administration-button-semantics/before/access/administration-access-1366x768.png) | [after](../user-guide/images/current/administration-access-1366x768.png) | N/A |
| Access | 1440×900 | [before](images/issue-161-administration-button-semantics/before/access/administration-access-1440x900.png) | [after](../user-guide/images/current/administration-access-1440x900.png) | N/A |
| Access | 1920×1080 | [before](images/issue-161-administration-button-semantics/before/access/administration-access-1920x1080.png) | [after](../user-guide/images/current/administration-access-1920x1080.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-access-1920x1080-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-access-1920x1080-button-actions-100pct.png) |
| Access | 2560×1440 | [before](images/issue-161-administration-button-semantics/before/access/administration-access-2560x1440.png) | [after](../user-guide/images/current/administration-access-2560x1440.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-access-2560x1440-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-access-2560x1440-button-actions-100pct.png) |
| Access | 3840×2160 | [before](images/issue-161-administration-button-semantics/before/access/administration-access-3840x2160.png) | [after](../user-guide/images/current/administration-access-3840x2160.png) | [before](images/issue-161-administration-button-semantics/crops/before/administration-access-3840x2160-button-actions-100pct.png) · [after](images/issue-161-administration-button-semantics/crops/after/administration-access-3840x2160-button-actions-100pct.png) |

State originals: [primary hover](images/issue-161-administration-button-semantics/after/states/database-primary-hover-1440x900.png),
[keyboard focus](images/issue-161-administration-button-semantics/after/states/database-primary-focus-1440x900.png),
[disabled primary](images/issue-161-administration-button-semantics/after/states/records-primary-disabled-1440x900.png),
[danger hover](images/issue-161-administration-button-semantics/after/states/access-danger-hover-1440x900.png),
[loading primary](images/issue-161-administration-button-semantics/after/states/access-primary-loading-1440x900.png).

## Main qualitative review — Q-01 through Q-20

| Gate | Result | Rationale |
| --- | --- | --- |
| Q-01–Q-16 | not-applicable | 이 후속은 Materials tree, Modeling graph/ribbon/export 또는 Activity rail topology를 변경하지 않는다. |
| Q-17 | pass | 세 Administration normal 원본에서 object/record/access identity와 일반 task copy가 유지되고 버튼 이관으로 잘림·중복 prose가 생기지 않았다. |
| Q-18 | not-applicable | Add command의 새-definition draft, Attribute type 전환, Record preview/Layout projection 동작은 변경하지 않았고 이번 normal-state packet은 해당 workflow를 새로 승인하지 않는다. |
| Q-19 | not-applicable | Link Type cardinality, related/workflow evidence와 exact revision pin은 변경하지 않았다. |
| Q-20 | **fail (inherited; Product Owner disposition pending)** | 2560/3840 Database design과 Records & registration의 기존 bounded workgroup이 navigator와 관련 task region 사이 및 오른쪽에 큰 내부 여백을 남긴다. before/after에서 동일한 #161 선행 실패이며 버튼 이관은 새 workaround를 추가하지 않았다. 실제 Windows 4K 물리 판독성과 display tier 결정은 여기서 주장하지 않으며 #221을 시작하지 않았다. |
| V-09 | pass | Database edit footer의 filled primary는 Publish 한 개이고, bulk registration과 access form도 task context당 한 개다. |

## Inherited Q-20 carryover boundary

이 버튼 후속의 시각 검수는 아래 네 normal route/viewport를 **상속된 Q-20 fail**로 기록한다.
1920 원본에서는 관련 task region이 viewport를 사용하며, Users & access는 1920/2560/3840에서
content가 main 영역을 사용한다. 실패 범위는 Database design과 Records & registration의
2560/3840 normal state다.

| Route / state | Viewport | Before | After | Disposition |
| --- | --- | --- | --- | --- |
| `/administration/database` · normal selected Table | 2560×1440 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-2560x1440.png) | [after](../user-guide/images/current/administration-database-2560x1440.png) | inherited fail |
| `/administration/database` · normal selected Table | 3840×2160 | [before](images/issue-161-administration-button-semantics/before/database/administration-database-3840x2160.png) | [after](../user-guide/images/current/administration-database-3840x2160.png) | inherited fail |
| `/administration/records` · normal 10-record workspace | 2560×1440 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-2560x1440.png) | [after](../user-guide/images/current/administration-records-2560x1440.png) | inherited fail |
| `/administration/records` · normal 10-record workspace | 3840×2160 | [before](images/issue-161-administration-button-semantics/before/records/administration-records-3840x2160.png) | [after](../user-guide/images/current/administration-records-3840x2160.png) | inherited fail |

원인은 이번 diff 이전부터 있던 `--ux-bounded-workgroup-max-inline-size` 기반의 centered workgroup
geometry다. 이번 diff는 Administration 전용 2560/3840 override, CSS `zoom`, blanket
`transform: scale`, filler를 추가하지 않았고 해당 geometry를 변경하지도 않았다. #161 transition
exception으로 carry할 수 있는지는 Product Owner의 명시적 처분이 필요하다. 독립 검수는 최초
`CHANGES_REQUESTED`에서 Q-20·verifier·#223 기록을 정정한 뒤 correction loop `APPROVE`로
종료됐다. 이 승인은 evidence 정확성과 제한된 버튼 변경에 대한 것이며 Q-20 carryover의 Product
Owner 처분을 대신하지 않는다. Product Owner 처분은 `pending`이고, 그 전에는 ready, merge,
#161/#117 완료를 금지한다. 이 기록은 #221의 shared display-tier 정책을 선택하거나 시작하지 않는다.

## Verification ledger

| Gate | Result |
| --- | --- |
| Administration/capture/user-guide Python contracts | 88 passed |
| Focused Administration Vitest | 3 files, 12 tests passed |
| Administration semantic Playwright | 1 passed; hover/focus/disabled/loading/danger computed style와 recovery 검증 |
| Full web Vitest | 60 files, 317 tests passed. 병렬 부하 중 변경 범위 밖 Modeling restore 1건이 최초 timeout됐으나 단독 재현 1건과 전체 단독 재실행 317건이 모두 통과했다. |
| Changed Python Ruff | pass |
| Production build and bundle budget | pass |
| Canonical Compose preflight / health | pass |
| Five-viewport normal and state captures | pass; Main이 전후 30개, 상태 5개, crop 18개를 모두 원본 해상도로 열어 판정 |
| User guide / screenshot manifest | pass; 20 guides, 87 current captures, 422 local links, 366 images |
| Docs impact / whitespace | pass; navigation contract v21 동기화, 6 visual sources 분류, `git diff --check` 오류 없음 |
| Independent read-only visual review | correction loop `APPROVE`; 8 approved references + 15 before + 15 after + 18 direct crops + 5 states = 61개 원본 확인. 최초 `CHANGES_REQUESTED`의 Q-20·verifier·#223 기록을 정정했으며, Product Owner carryover 처분은 pending |
| Pre-publish | pass; `uv run cmp-pre-publish --root . --trigger manual` on the clean final commit |
| Product Owner review | pending; #161/#117 completion, ready, merge 금지 |

## Publication boundary

이 evidence와 대표 전후 원본/crop, 검사 결과를 Product Owner에게 먼저 제시한다. 사용자 요청은
명시된 diff의 commit, push와 draft PR까지만 허용한다. ready 전환, merge, #161/#117 완료 처리,
#221 시작은 별도의 명시적 지시 없이는 수행하지 않는다.
