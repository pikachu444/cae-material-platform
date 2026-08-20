# Issue #298 PR #297 frontend guard 회귀 교정 근거

## 판정과 경계

PR #297이 추가한 Administration Database design 동작은 완성되어 있었지만, 같은 PR의 feature CSS에
frontend guard 위반 5건이 유입되었고 `shared`에서 legacy `types.ts`로 향하는 import 1건이 baseline에
정확히 설명되지 않았다. 따라서 기존 상태를 **semantic visual defect 5건과 bounded compatibility debt
1건이 있는 partial**로 판정했다.

구현 범위는 `database-design.css`의 literal font weight 3건, raw backdrop color 1건, viewport 기준 wide
media 1건을 기존 semantic token과 Database design feature container 기준으로 교체하고,
`configurable-definition-api.ts`의 exact import finding 1건만 #298 소유 임시 예외로 기록하는 것이다.
React/DOM/API/copy/route/state, shared primitive·token, application shell, backend와 guard source/test는
변경하지 않았다. 예외는 #263 FE-08C가 catalog type을 owned type/model module로 옮겨 해당 import가
사라질 때 제거한다.

## 사용자 여정과 보존 결과

관리자는 Database design에서 exact Table identity와 `r1`을 선택해 편집하고 실제 Record preview의
Layout `r1`과 14개 exact Attribute revision pin을 확인한다. 사용 중인 seeded draft 삭제는 서버가 이유와
함께 차단하며 선택과 원본을 유지한다. clean unpublished `r1` 복제본은 확인 후 삭제되고 목록 재조회에서
사라진다.

1366×768과 1440×900에서는 preview가 editor를 교체하며 `Close preview`로 복귀한다. 1920×1080,
2560×1440, 3840×2160에서는 Objects, Table list, editor, preview 네 pane이 인접한다. navigator와
form/preview는 읽기 폭을 유지하고 중앙 table이 남은 비교 공간을 사용한다. 픽셀 수치 자체가 목표가
아니며 exact identity/revision, 작업 순서, clipping·overflow 부재와 #249의 세 축이 판정 기준이다.

## 구현 판정

- 정보 계층: `Objects → exact identity/revision list → editor → real Record preview`가 유지된다.
- 엔지니어링 작업 흐름: 선택·편집·preview·삭제 차단 복구·clean draft 삭제/read-back이 유지된다.
- 반응형/와이드 구성: viewport media 대신 88rem Database design inline-size container를 사용한다.
  88rem은 네 pane의 최소 작업 폭 합계이며, application shell이나 route별 4K override가 아니다.
- 표 머리는 `--ux-font-weight-table-heading`, Link/preview label은 `--ux-font-weight-label`, delete dialog
  scrim은 `--ux-text` 기반 `color-mix()`를 사용한다. 새 token이나 raw fallback은 없다.
- guard baseline source는 실제 merge base `5e6ebf5484d601f0487539dde8d579f4b03a4ee8`로 갱신했다.
  debt는 font `216/216`, raw color `954/954`, wide media `2/2`이며 증가하지 않았다.

## live 검증

- frontend guard: 위반 0, baseline warning 15, exact exception 생성·소멸 검사를 포함한 17 tests 통과.
- focused frontend: `configurable-catalog-admin.test.tsx` 9 tests 통과.
- production frontend build와 bundle budget 통과.
- browser: `administration-button-semantics.spec.ts`와 `administration-database-workflow.spec.ts` 2개 통과.
- capture: before/after 각각 editor 5장과 preview 5장, 총 원본 20장과 직접 100% crop 50장을 모두
  원해상도로 열어 확인했다. browser zoom 100%, DPR 1, Standard density다.
- 픽셀 비교: editor 5장은 before/after가 픽셀 단위로 동일하다. preview 차이는 semantic label weight가
  있는 preview pane 내부에만 있고 전체 픽셀의 최대 0.73%이며 geometry·copy·identity 변화는 0이다.
- Compose: Windows에 `make`가 없어 `make compose-preflight`는 N/A다. 동등한 Python preflight는 실행 중인
  `cmp-local-demo`가 다른 보존 worktree 소유임을 확인해 canonical 변경을 거부했다. 전용
  `cmp-demo-test-298before`/`cmp-demo-test-298after`에서 current-worktree 이미지를 build하고 seed를 두 번
  실행해 304개 table의 안정성을 확인했다. 각 project의 container·volume·local image·network만
  제거했으며, canonical volume identity와 8개 핵심 count는 전후 동일하다.
- 실제 Windows 4K 100%/150%/200% 물리 가독성은 주장하지 않으며 #223에 남는다.
- base refreeze: #299 전후 `apps/web` 전체 tree, 두 #298 production 파일, runtime 입력과 #289 visual
  evidence tree가 byte-identical이다. 실제 capture base는 `ae93058d61f4a229addbcb746a50a86689639f6f`이며,
  새 merge base `5e6ebf5484d601f0487539dde8d579f4b03a4ee8`에서도 route/state/input/source hash가 같아 기존
  browser·viewport evidence를 재사용했다. 이미지와 등록 SHA-256은 변경하지 않았다.

## 시각 근거

전체 70개 asset의 경로·크기·SHA-256, crop 좌표, geometry, 픽셀 비교와 Q-01~Q-20 판정은
[visual-evidence.yaml](images/issue-298-frontend-guard-297-correction/visual-evidence.yaml)에 있다.

- [1920×1080 수정 전 preview](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-1920x1080.png)
- [1920×1080 수정 후 preview](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-1920x1080.png)
- [2560×1440 수정 전 preview](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-2560x1440.png)
- [2560×1440 수정 후 preview](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-2560x1440.png)
- [3840×2160 수정 전 preview](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-3840x2160.png)
- [3840×2160 수정 후 preview](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-3840x2160.png)

Q-01과 Q-02는 bounded short fixture라 해당하지 않고 Q-03~Q-16은 Materials/Modeling/Export 전용이라
해당하지 않는다. Q-17 Administration identity/용어, Q-18 편집·preview·draft 동작, Q-19 cardinality와
exact revision, Q-20 전체 폭/고해상도 구성은 모두 통과했다.

+## 전체 원본·crop 인덱스

### after

- [after · crops · administration-database-1366x768-form-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1366x768-form-100pct.png)
- [after · crops · administration-database-1366x768-header-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1366x768-header-100pct.png)
- [after · crops · administration-database-1366x768-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1366x768-navigator-100pct.png)
- [after · crops · administration-database-1366x768-preview-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1366x768-preview-100pct.png)
- [after · crops · administration-database-1366x768-table-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1366x768-table-100pct.png)
- [after · crops · administration-database-1440x900-form-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1440x900-form-100pct.png)
- [after · crops · administration-database-1440x900-header-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1440x900-header-100pct.png)
- [after · crops · administration-database-1440x900-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1440x900-navigator-100pct.png)
- [after · crops · administration-database-1440x900-preview-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1440x900-preview-100pct.png)
- [after · crops · administration-database-1440x900-table-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1440x900-table-100pct.png)
- [after · crops · administration-database-1920x1080-form-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1920x1080-form-100pct.png)
- [after · crops · administration-database-1920x1080-header-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1920x1080-header-100pct.png)
- [after · crops · administration-database-1920x1080-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1920x1080-navigator-100pct.png)
- [after · crops · administration-database-1920x1080-preview-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1920x1080-preview-100pct.png)
- [after · crops · administration-database-1920x1080-table-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-1920x1080-table-100pct.png)
- [after · crops · administration-database-2560x1440-form-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-2560x1440-form-100pct.png)
- [after · crops · administration-database-2560x1440-header-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-2560x1440-header-100pct.png)
- [after · crops · administration-database-2560x1440-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-2560x1440-navigator-100pct.png)
- [after · crops · administration-database-2560x1440-preview-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-2560x1440-preview-100pct.png)
- [after · crops · administration-database-2560x1440-table-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-2560x1440-table-100pct.png)
- [after · crops · administration-database-3840x2160-form-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-3840x2160-form-100pct.png)
- [after · crops · administration-database-3840x2160-header-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-3840x2160-header-100pct.png)
- [after · crops · administration-database-3840x2160-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-3840x2160-navigator-100pct.png)
- [after · crops · administration-database-3840x2160-preview-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-3840x2160-preview-100pct.png)
- [after · crops · administration-database-3840x2160-table-100pct.png](images/issue-298-frontend-guard-297-correction/after/crops/administration-database-3840x2160-table-100pct.png)
- [after · originals · administration-database-1366x768.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-1366x768.png)
- [after · originals · administration-database-1440x900.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-1440x900.png)
- [after · originals · administration-database-1920x1080.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-1920x1080.png)
- [after · originals · administration-database-2560x1440.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-2560x1440.png)
- [after · originals · administration-database-3840x2160.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-3840x2160.png)
- [after · originals · administration-database-preview-1366x768.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-1366x768.png)
- [after · originals · administration-database-preview-1440x900.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-1440x900.png)
- [after · originals · administration-database-preview-1920x1080.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-1920x1080.png)
- [after · originals · administration-database-preview-2560x1440.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-2560x1440.png)
- [after · originals · administration-database-preview-3840x2160.png](images/issue-298-frontend-guard-297-correction/after/originals/administration-database-preview-3840x2160.png)
### before

- [before · crops · administration-database-1366x768-form-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1366x768-form-100pct.png)
- [before · crops · administration-database-1366x768-header-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1366x768-header-100pct.png)
- [before · crops · administration-database-1366x768-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1366x768-navigator-100pct.png)
- [before · crops · administration-database-1366x768-preview-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1366x768-preview-100pct.png)
- [before · crops · administration-database-1366x768-table-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1366x768-table-100pct.png)
- [before · crops · administration-database-1440x900-form-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1440x900-form-100pct.png)
- [before · crops · administration-database-1440x900-header-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1440x900-header-100pct.png)
- [before · crops · administration-database-1440x900-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1440x900-navigator-100pct.png)
- [before · crops · administration-database-1440x900-preview-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1440x900-preview-100pct.png)
- [before · crops · administration-database-1440x900-table-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1440x900-table-100pct.png)
- [before · crops · administration-database-1920x1080-form-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1920x1080-form-100pct.png)
- [before · crops · administration-database-1920x1080-header-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1920x1080-header-100pct.png)
- [before · crops · administration-database-1920x1080-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1920x1080-navigator-100pct.png)
- [before · crops · administration-database-1920x1080-preview-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1920x1080-preview-100pct.png)
- [before · crops · administration-database-1920x1080-table-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-1920x1080-table-100pct.png)
- [before · crops · administration-database-2560x1440-form-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-2560x1440-form-100pct.png)
- [before · crops · administration-database-2560x1440-header-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-2560x1440-header-100pct.png)
- [before · crops · administration-database-2560x1440-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-2560x1440-navigator-100pct.png)
- [before · crops · administration-database-2560x1440-preview-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-2560x1440-preview-100pct.png)
- [before · crops · administration-database-2560x1440-table-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-2560x1440-table-100pct.png)
- [before · crops · administration-database-3840x2160-form-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-3840x2160-form-100pct.png)
- [before · crops · administration-database-3840x2160-header-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-3840x2160-header-100pct.png)
- [before · crops · administration-database-3840x2160-navigator-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-3840x2160-navigator-100pct.png)
- [before · crops · administration-database-3840x2160-preview-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-3840x2160-preview-100pct.png)
- [before · crops · administration-database-3840x2160-table-100pct.png](images/issue-298-frontend-guard-297-correction/before/crops/administration-database-3840x2160-table-100pct.png)
- [before · originals · administration-database-1366x768.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-1366x768.png)
- [before · originals · administration-database-1440x900.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-1440x900.png)
- [before · originals · administration-database-1920x1080.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-1920x1080.png)
- [before · originals · administration-database-2560x1440.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-2560x1440.png)
- [before · originals · administration-database-3840x2160.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-3840x2160.png)
- [before · originals · administration-database-preview-1366x768.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-1366x768.png)
- [before · originals · administration-database-preview-1440x900.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-1440x900.png)
- [before · originals · administration-database-preview-1920x1080.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-1920x1080.png)
- [before · originals · administration-database-preview-2560x1440.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-2560x1440.png)
- [before · originals · administration-database-preview-3840x2160.png](images/issue-298-frontend-guard-297-correction/before/originals/administration-database-preview-3840x2160.png)


## 감사와 출판 경계

Main acceptance는 통과했다. canonical Balanced 독립 읽기 전용 감사자는 이 exact candidate의 81개
경로, guard debt·예외, 70개 시각 asset과 Q-01~Q-20, #249 세 축, 접근성·계약·출판 경계를 독립적으로
확인했다. blocker 0, major 0, material-minor 0, actionable finding 0으로 `APPROVE`했다.
#299 이후에는 같은 감사자가 새 base와 validator contract를 포함한 82개 경로, byte-identical source/input,
증거 재사용 provenance와 통과한 최소 게이트를 다시 열어 확인했다. blocker 0, major 0, material-minor 0,
actionable finding 0으로 revised candidate도 `APPROVE`했다.

- independent auditor: APPROVE
- refrozen-base independent auditor: APPROVE
- Product Owner geometry review: PENDING — 1920×1080, 2560×1440, 3840×2160 수정 후 원본
- Ready 전환: 금지
- merge: 금지
