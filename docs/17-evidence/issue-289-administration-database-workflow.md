# Issue #289 Administration Database workflow evidence

## 판정과 범위

기존 동작은 **부분 구현**이었다. Administration 진입점과 일부 Database/Profile/Table 편집기는 있었지만,
정확한 identity/revision 목록, 모든 정의 유형의 Add/Edit/Duplicate, 실제 Record 미리보기, 의존성 설명을
포함한 안전한 초안 삭제가 하나의 작업 흐름으로 완결되지 않았다.

주 사용자 여정은 관리자가 Database design에서 exact Table revision을 선택하고 실제 Record와 Layout/
Attribute pin을 확인한 뒤, 깨끗한 비공개 r1 Table을 복제하여 새 identity를 만들고 **초안 삭제(Delete draft)** 확인
후 물리 삭제한 다음 목록 재조회에서 부재를 확인하는 흐름이다. 같은 여정에서 Record가 참조하는 기존
Table 삭제를 시도하면 서버가 차단 이유를 반환하고 선택·원본은 그대로 남는다.

삭제 예외는 게시 이력이 없는 revision 1이면서 Record, Link, 참조 또는 다른 의존성이 없는 Database,
Profile, Table, Attribute, Layout, Subset, Link Type에만 적용한다. Layout item은 Layout이 소유하는
구성요소로 함께 제거한다. 게시되었거나 revision 2 이상이거나 사용 중인 identity/revision은 기존
불변 보호를 유지한다. stale revision, 권한 부족, 지원하지 않는 유형, 동시 게시/참조 추가도 서버에서
차단한다.

소유 범위는 Catalog 삭제 domain/application/persistence/API, 해당 PostgreSQL migration과 계약,
Administration Database design feature, shared frontend transport 추출, 그 회귀/E2E 테스트, 사용자
가이드·현재 이미지·증거 packet이다. 다른 worktree, #261 소유 코드, Materials/Modeling 의미, Record
삭제, 실제 게시 구현, 범용 삭제 프레임워크, 인증/권한 정책 재설계는 제외한다.

## 시각 판정

- 정보 계층: Objects → exact identity/revision 목록 → bounded 속성 form → 실제 Record 미리보기 순서를 유지한다.
- 엔지니어링 작업 흐름: 선택, 편집/복제, 서버 검증 삭제, 재조회/복구가 한 화면에서 이어진다.
- 반응형/와이드 구성: 1366×768과 1440×900에서는 미리보기가 오른쪽 pane을 교체하고, 1920×1080 이상에서는
  네 번째 pane으로 나란히 보인다. navigator는 compact bound, form과 미리보기는 최대 800px의 읽기 폭을
  유지하고 중앙 목록이 남은 공간을 사용하며, 다섯 viewport 모두 page horizontal overflow가 0이다.
- 자동화한 3840×2160 CSS viewport는 geometry 근거이며 실제 Windows 4K 물리 가독성을 주장하지 않는다.
- 최종 product-owner 1920×1080, 2560×1440, 3840×2160 original geometry 승인은 PR merge 전 별도 필수 gate다.

## 검증

- 프런트엔드: Vitest 71 files / 410 tests, frontend guard 17 tests, production build와 bundle budget 통과.
- 서버/마이그레이션: #289 PostgreSQL/API/migration 대상 23 tests 통과.
- 브라우저: 실제 current-worktree API/PostgreSQL/Vite에서 primary journey와 button semantics 2 specs 통과.
- 정적/계약: Ruff, issue-owned backend mypy, backend architecture 29 tests, OpenAPI lint/compatibility,
  계약·가이드 150 tests, user-guide/doc-impact, git diff check 통과.
- canonical Compose는 다른 보존 worktree가 사용 중이라 preflight에서 거부되었고 변경하지 않았다.
  전용 current-worktree PostgreSQL/API/Vite로 live evidence를 만들었다.

## 기존 #280 근거

#280 완료 assessment의 원본만 이 packet에 복사해 비교 근거로 사용했으며 assessment 문구는 복사하지 않았다.

- [1366x768 기존 전체 화면](images/issue-289-administration-database-workflow/before/originals/administration-database-1366x768.png)
- [1366x768 기존 header 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1366x768-header-100pct.png)
- [1366x768 기존 navigator 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1366x768-navigator-100pct.png)
- [1366x768 기존 object-list 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1366x768-object-list-100pct.png)
- [1366x768 기존 property-editor 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1366x768-property-editor-100pct.png)
- [1440x900 기존 전체 화면](images/issue-289-administration-database-workflow/before/originals/administration-database-1440x900.png)
- [1440x900 기존 header 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1440x900-header-100pct.png)
- [1440x900 기존 navigator 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1440x900-navigator-100pct.png)
- [1440x900 기존 object-list 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1440x900-object-list-100pct.png)
- [1440x900 기존 property-editor 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1440x900-property-editor-100pct.png)
- [1920x1080 기존 전체 화면](images/issue-289-administration-database-workflow/before/originals/administration-database-1920x1080.png)
- [1920x1080 기존 header 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1920x1080-header-100pct.png)
- [1920x1080 기존 navigator 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1920x1080-navigator-100pct.png)
- [1920x1080 기존 object-list 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1920x1080-object-list-100pct.png)
- [1920x1080 기존 property-editor 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-1920x1080-property-editor-100pct.png)
- [2560x1440 기존 전체 화면](images/issue-289-administration-database-workflow/before/originals/administration-database-2560x1440.png)
- [2560x1440 기존 header 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-2560x1440-header-100pct.png)
- [2560x1440 기존 navigator 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-2560x1440-navigator-100pct.png)
- [2560x1440 기존 object-list 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-2560x1440-object-list-100pct.png)
- [2560x1440 기존 property-editor 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-2560x1440-property-editor-100pct.png)
- [3840x2160 기존 전체 화면](images/issue-289-administration-database-workflow/before/originals/administration-database-3840x2160.png)
- [3840x2160 기존 header 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-3840x2160-header-100pct.png)
- [3840x2160 기존 navigator 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-3840x2160-navigator-100pct.png)
- [3840x2160 기존 object-list 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-3840x2160-object-list-100pct.png)
- [3840x2160 기존 property-editor 100% crop](images/issue-289-administration-database-workflow/before/crops/administration-database-3840x2160-property-editor-100pct.png)

## 최종 #289 근거

- [1366x768 최종 편집 화면](images/issue-289-administration-database-workflow/after/originals/administration-database-1366x768.png)
- [1366x768 최종 Record 미리보기](images/issue-289-administration-database-workflow/after/originals/administration-database-preview-1366x768.png)
- [1366x768 최종 header 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1366x768-header-100pct.png)
- [1366x768 최종 navigator 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1366x768-navigator-100pct.png)
- [1366x768 최종 table 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1366x768-table-100pct.png)
- [1366x768 최종 form 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1366x768-form-100pct.png)
- [1366x768 최종 preview 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1366x768-preview-100pct.png)
- [1440x900 최종 편집 화면](images/issue-289-administration-database-workflow/after/originals/administration-database-1440x900.png)
- [1440x900 최종 Record 미리보기](images/issue-289-administration-database-workflow/after/originals/administration-database-preview-1440x900.png)
- [1440x900 최종 header 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1440x900-header-100pct.png)
- [1440x900 최종 navigator 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1440x900-navigator-100pct.png)
- [1440x900 최종 table 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1440x900-table-100pct.png)
- [1440x900 최종 form 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1440x900-form-100pct.png)
- [1440x900 최종 preview 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1440x900-preview-100pct.png)
- [1920x1080 최종 편집 화면](images/issue-289-administration-database-workflow/after/originals/administration-database-1920x1080.png)
- [1920x1080 최종 Record 미리보기](images/issue-289-administration-database-workflow/after/originals/administration-database-preview-1920x1080.png)
- [1920x1080 최종 header 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1920x1080-header-100pct.png)
- [1920x1080 최종 navigator 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1920x1080-navigator-100pct.png)
- [1920x1080 최종 table 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1920x1080-table-100pct.png)
- [1920x1080 최종 form 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1920x1080-form-100pct.png)
- [1920x1080 최종 preview 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-1920x1080-preview-100pct.png)
- [2560x1440 최종 편집 화면](images/issue-289-administration-database-workflow/after/originals/administration-database-2560x1440.png)
- [2560x1440 최종 Record 미리보기](images/issue-289-administration-database-workflow/after/originals/administration-database-preview-2560x1440.png)
- [2560x1440 최종 header 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-2560x1440-header-100pct.png)
- [2560x1440 최종 navigator 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-2560x1440-navigator-100pct.png)
- [2560x1440 최종 table 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-2560x1440-table-100pct.png)
- [2560x1440 최종 form 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-2560x1440-form-100pct.png)
- [2560x1440 최종 preview 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-2560x1440-preview-100pct.png)
- [3840x2160 최종 편집 화면](images/issue-289-administration-database-workflow/after/originals/administration-database-3840x2160.png)
- [3840x2160 최종 Record 미리보기](images/issue-289-administration-database-workflow/after/originals/administration-database-preview-3840x2160.png)
- [3840x2160 최종 header 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-3840x2160-header-100pct.png)
- [3840x2160 최종 navigator 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-3840x2160-navigator-100pct.png)
- [3840x2160 최종 table 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-3840x2160-table-100pct.png)
- [3840x2160 최종 form 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-3840x2160-form-100pct.png)
- [3840x2160 최종 preview 100% crop](images/issue-289-administration-database-workflow/after/crops/administration-database-3840x2160-preview-100pct.png)

## 감사와 승인

Main Q1–Q20은 모두 통과했다.

1. Q1 범위와 기존 상태: partial 판정 및 #289 bounded scope와 일치한다.
2. Q2 사용자 여정: exact Table 선택 → 실제 Record 확인 → clean r1 복제 → 영구 삭제 → 부재 read-back이 완결된다.
3. Q3 삭제 자격: unpublished revision 1만 허용한다.
4. Q4 게시 보호: publication marker가 있으면 차단하고 동시 게시 race를 잠금으로 직렬화한다.
5. Q5 사용 보호: Record, Link, reference와 FK dependency가 있으면 원자적으로 rollback하고 차단한다.
6. Q6 권한: catalog.write, tenant/project/classification RLS context와 schema configuration grant를 모두 유지한다.
7. Q7 동시성: strong If-Match와 expected current revision으로 stale 요청을 거절한다.
8. Q8 원자성: identity/revision pair만 한 transaction에서 삭제하고 unrelated constraint timing은 바꾸지 않는다.
9. Q9 불변성: 승인 capability 밖의 identity/revision UPDATE/DELETE는 기존처럼 거절한다.
10. Q10 migration: up/down/up, immutable trigger와 deferred FK 복원이 검증된다.
11. Q11 정확한 선택: 목록과 편집 surface가 stable identity와 rN을 함께 표시한다.
12. Q12 작업 완결성: 7개 정의 유형의 Add/Edit/Duplicate/Delete 경로가 한 feature boundary에 있다.
13. Q13 복구: 서버 차단 이유가 보이고 현재 선택과 원본이 유지된다.
14. Q14 미리보기: selected Table의 이름순 첫 authorized 실제 Record만 읽고 값을 만들지 않는다.
15. Q15 exact pin: Record rN, Layout rN과 Layout이 고정한 Attribute revision을 보여 준다.
16. Q16 접근성: native dialog, cancel, 설명 연결, focus-visible, alert/status와 keyboard button semantics를 유지한다.
17. Q17 좁은 화면: 1366×768/1440×900에서 preview가 editor를 대체하고 list revision 열이 잘리지 않는다.
18. Q18 넓은 화면: 1920/2560/3840에서 bounded navigator/form과 elastic list/preview가 공존한다.
19. Q19 #249: information hierarchy, engineering task flow, responsive/wide-screen composition 세 축이 통과한다.
20. Q20 전달 경계: tests/docs/evidence는 현재 후보와 일치하며 commit·push·PR·merge는 수행하지 않았다.

첫 독립 Balanced 읽기 전용 감사에서는 blocker 1건과 major 3건을 찾았다. DELETE API에
`schema_configuration`을 서버에서도 강제하고, 원자 삭제 시점의 stale 경쟁을 412로 보존하고, Layout이
고정한 과거 Attribute revision을 exact endpoint로 읽으며, 2560/3840 미리보기를 800px 읽기 폭으로 제한해
네 건을 수정했다. 같은 감사자의 재검토는 blocker 0, major 0, minor 0, `approve`로 통과했고 #249의
정보 계층·엔지니어링 작업 흐름·반응형/와이드 구성 세 축도 모두 통과했다. 제품 책임자의 최종
wide-original 시각 승인은 아직 대기 중이며, 승인 전에는 merge할 수 없다.
