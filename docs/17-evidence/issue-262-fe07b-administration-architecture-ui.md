# Issue #262 FE-07B Administration 구조 및 UI 정비

Status: 제품 소유자 교정을 반영한 구현과 Main의 FHD·5-viewport 원본 검토가 완료된 후보입니다. 폐기된 v2/inspection 화면은 증거와 사용자 가이드에 포함하지 않았으며 canonical Balanced 독립 감사가 남아 있습니다.

범위는 FE-07B Administration뿐입니다. FE-07A Materials와 두 Materials-to-Modeling 여정, Modeling domain/backend data와 release artifact는 변경하지 않았습니다.

## 현재 상태 분류와 결과

| 영역 | 구현 전 분류 | FE-07B 결과 |
| --- | --- | --- |
| Administration 진입·task order | missing | 기본 앱 바의 `Materials | Modeling | Activity`를 보존하고 `Database | Format definitions | Records | Access`를 한 taskbar에 둔다. 중복 Administration 표시는 제거하고 `/administration`은 Database로 진입한다. |
| Database/Profile/Table/Attribute/Layout/Subset/Link Type | partial | 기존 create/revise/duplicate/delete-draft/check 계약을 유지하고 stable ID와 exact revision ID를 URL에 고정한다. Table/Layout/Record를 사용자가 명시적으로 선택하며 reload가 같은 좌표를 다시 읽는다. |
| Record preview와 Records 이동 | partial | 실제 server Record만 preview하고 `Open in Records`가 exact Table/Folder/Record identity·revision을 전달한다. 1366/1440/1920에서는 editor를 preview로 바꾸며, 2560/3840에서만 bounded 비교로 나란히 둔다. |
| Format definitions | partial | 기존 upload→plan→confirm→apply→read-back→export 계약을 보존한다. `application_id` URL이 stale session recovery보다 우선하며 checksum/provenance를 직접 표시한다. |
| Records | partial | compact search/filter와 Name·Code·Revision 결과 목록을 기본 작업면으로 만들고, create/edit는 요청할 때만 bounded editor로 연다. exact r2는 명시적으로 선택한 뒤 `Create revision 3 from revision 2`로 새 immutable 결과를 만든다. 지원되는 create/revise, folder, search/compare, multiple-row preview/publish, review request만 유지한다. |
| Access | behavior complete, UI partial | assignment 표를 주 작업면으로 만들고 subject/team·role·effective capabilities·row action을 같은 행에서 읽는다. add/edit는 사용자가 열 때만 compact surface로 표시하며 실제 grant/revoke 계약만 유지한다. |
| Database 일반 Publish | missing backend configuration | 화면에 Publish 명령을 표시하지 않는다. FE-07B가 존재하지 않는 backend 동작을 만들지 않는다. |
| feature ownership | missing | `features/administration/{database-design,definition-bundles,records,access,routes,model}`과 public `index.ts`로 소유권을 분리했다. root compatibility re-export 제거는 #263 소유다. |

이 구조 정비와 exact-navigation UI는 하나의 응집된 단위다. route-state가 stable identity/immutable revision 연속성을 공급하고, 네 Administration task가 그 상태를 같은 shell에서 소비한다. 등록된 root hotspot에는 새 책임을 추가하지 않았다.

## 주 사용자 여정과 복구

1. Administrator가 `/administration`에서 Database를 열고 `Demo Material Records` Table을 명시적으로 선택한다.
2. Layouts에서 `Material overview` stable identity와 exact r1을 열어 정의를 검사하거나 지원되는 draft create/edit/duplicate/delete를 수행한다.
3. `Preview record`에서 실제 `DP780 synthetic reference steel` Record r2를 선택한다. URL은 Table/Layout/Record stable ID와 exact revision ID를 함께 보존한다.
4. reload 후 같은 Layout r1과 Record r2가 다시 나타나는지 확인하고 `Open in Records`로 이동한다.
5. Records에서 결과 행의 Name·Code·Revision을 확인하고 exact Table/Folder/Record r2를 연다. 새 Record r1을 만든 뒤 `Create revision 2 from revision 1`로 immutable revision을 저장하고 반환된 exact 좌표를 reload로 read-back한다.
6. Format definitions에서 canonical JSON을 Select→Plan→Apply→Read back 순서로 처리하고 application ID·checksum·provenance를 다시 읽는다.
7. Access에서 실제 role consequence를 확인한 뒤 assignment를 grant하고, 같은 assignment ID를 revoke하여 목록 read-back을 확인한다. 일반 탐색은 `Open Materials`로 돌아간다.

복구와 의미 있는 negative case는 다음과 같다.

- URL의 stable ID와 revision ID가 없거나 서로 맞지 않으면 current/latest/첫 항목/다른 session 값으로 대체하지 않고 해당 task에서 오류와 재선택 경로를 보인다.
- 요청한 과거 Record revision은 read-only이며 current revision을 명시적으로 열기 전에는 revise할 수 없다.
- 사용 중인 draft 삭제는 서버가 publication/revision/reference/dependency cause로 차단하며 선택과 원본을 보존한다.
- Format Definition의 conflict/error/migration-required plan은 Apply를 활성화하지 않는다. stale plan은 기존 Apply를 반복하지 않고 Plan again으로 복구한다.
- Record가 없는 Table은 예시 Record를 만들지 않는다. multiple-row 오류는 유효한 행 전체가 확인되기 전 publish하지 않는다.
- User/Reviewer는 Format Definition apply와 Access 관리 기능을 얻지 않으며, 권한 오류가 다른 identity의 결과로 대체되지 않는다.

## 계약·API·schema·소유권

| 책임 | 실제 경계 |
| --- | --- |
| route composition | `apps/web/src/features/administration/routes/administration-workspace.tsx` |
| URL parse/serialize | `apps/web/src/features/administration/model/administration-route-state.ts` |
| Database UI/API boundary | `features/administration/database-design/*`, `shared/catalog/configurable-definition-api.ts` |
| Format definitions | `features/administration/definition-bundles/*` |
| Records | `features/administration/records/*` |
| Access | `features/administration/access/*` |
| public import | `apps/web/src/features/administration/index.ts` |

Database는 실제 `/api/v1/catalog/databases`, `/profiles`, `/tables`, Table-scoped `/attributes`, `/layouts`, `/subsets`, `/folders`, `/records`, `/catalog/link-types`, 각 aggregate의 `/revisions`, `/catalog/records:search`, `/catalog/publication:validate`를 사용한다. Records는 `/catalog/record-registrations:preview`, `:publish`, `/catalog/records/{id}`, `/revisions`, `/revisions:compare`도 사용한다. Format definitions는 `/uploads` multipart completion, `/catalog/schema-definition-bundles:plan`, `:apply`, `/schema-definition-bundle-applications/{application_id}`, `/{bundle_key}:export`를 사용한다. Access는 `/product-access/me`, `/product-access/assignments`, `/{assignment_id}/revoke`만 사용한다.

권위 schema는 `contracts/catalog/configurable-catalog-resources.schema.json`, `configurable-catalog-record-resources.schema.json`, `configurable-catalog-link-resources.schema.json`, `schema-definition-{bundle,source-set,plan,bundle-application}.schema.json`, `contracts/identity/product-access-resources.schema.json`, `contracts/revisions/revision-metadata.schema.json`과 `contracts/http/openapi.yaml`이다. 핵심 필드는 aggregate stable ID와 `current_revision.id/revision_no/content_hash`, Record의 `table_id`, `folder_revision_id`, `values[].attribute_definition_id/attribute_definition_revision_id`, Link의 source/target exact revision, Format Definition의 `source_artifact.artifact_id/artifact_sha256`, `plan_fingerprint`, `application_id`, result `id/revision_id/content_hash`다.

## 시각 증거

[구조화 manifest](images/issue-262-fe07b-administration-architecture-ui/visual-evidence.yaml)는 100% zoom, DPR 1의 after 원본 25장, direct 1:1 crop 100장, geometry measurement 25개를 등록한다. Main은 최종 원본 25장 전부와 각 상태·해상도의 대표 crop을 원본 해상도로 직접 확인했다. 제품 소유자가 거부한 v2/inspection 캡처는 추적용 임시 파일로만 사용하고 게시 대상에서 제외했다. 아래 `B/A`는 기존에 등록된 FE-07B 직전 화면과 교정 후 최종 before/after다.

| 상태 | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | --- | --- | --- | --- | --- |
| Database editor | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-1366x768.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-1366x768.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-1440x900.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-1440x900.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-1920x1080.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-1920x1080.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-2560x1440.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-2560x1440.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-3840x2160.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-3840x2160.png) |
| Database preview | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-preview-1366x768.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-1366x768.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-preview-1440x900.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-1440x900.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-preview-1920x1080.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-1920x1080.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-preview-2560x1440.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-2560x1440.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-database-preview-3840x2160.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-3840x2160.png) |
| Records exact revision | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-records-1366x768.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-1366x768.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-records-1440x900.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-1440x900.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-records-1920x1080.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-1920x1080.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-records-2560x1440.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-2560x1440.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-records-3840x2160.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-3840x2160.png) |
| Access | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-access-1366x768.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-1366x768.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-access-1440x900.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-1440x900.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-access-1920x1080.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-1920x1080.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-access-2560x1440.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-2560x1440.png) | [B](images/issue-261-fe06-m3-governance-css-ownership/after/originals/administration-access-3840x2160.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-3840x2160.png) |
| Format definitions | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-1366x768.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-schema-bundle-plan-1366x768.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-1440x900.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-schema-bundle-plan-1440x900.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-1920x1080.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-schema-bundle-plan-1920x1080.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-2560x1440.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-schema-bundle-plan-2560x1440.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-3840x2160.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-schema-bundle-plan-3840x2160.png) |

### FHD 제품 소유자 검토 packet

1920×1080 원본 다섯 장만 순서대로 검토하면 된다: [Database editor](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-1920x1080.png), [exact Record preview](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-1920x1080.png), [Records results](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-1920x1080.png), [Format definitions](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-schema-bundle-plan-1920x1080.png), [Access assignments](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-1920x1080.png). 이 순서형 링크 묶음이 중복 PNG를 만들지 않는 compact owner packet이다. 비교 기준은 같은 행의 before 원본이며 다섯 장 모두 기본 앱 바와 `Materials | Modeling | Activity`, 한 줄의 Administration taskbar를 보존한다.

### #249 synthesis와 Q-17~Q-20

| 항목 | 결과 | 판정 |
| --- | --- | --- |
| Carbon hierarchy / Q-17 | pass Main | taskbar→object list→selected identity→decision fields 순서, flat pane/divider, 직접 label을 사용한다. badge·eyebrow·중첩 card·도움말 문단으로 구조를 보충하지 않는다. |
| COMSOL task flow / Q-18 | pass Main | browse→select exact definition→edit/check/save 또는 preview→Open in Records→immutable revision save/read-back 순서다. Add는 실제 draft를 열고 지원되지 않는 Publish는 표시하지 않는다. |
| exact links / Q-19 | pass Main | Layout Attribute pins, Record/Folder/Table revisions, Link Type cardinality와 Format Definition application을 구체 revision으로 유지한다. |
| SAP composition / Q-20 | pass Main | navigator/form/prose는 bounded이고 table/list/preview는 elastic이다. preview는 1920 이하에서 editor를 교체하고 2560/3840에서만 bounded 비교가 된다. 25개 측정 모두 page horizontal overflow 0이다. |

3840×2160 자동 capture는 CSS geometry 증거이지 실제 Windows 4K 판독성 주장이 아니다. 물리 장비 100%·150%·200% 판정은 #223 경계다.

## 검증 기록

| gate | 결과 |
| --- | --- |
| frontend tests | pass — Vitest 432/432; correction-focused 31/31 |
| frontend guard | pass — 0 violations, 15 registered historical warnings |
| actual API browser journey | pass — Database exact URL/reload/Open in Records/read-back, legacy Records exact query/shell/read-back, Access grant/revoke, button semantics, Format Definition plan/apply evidence |
| five-viewport geometry | pass Main — 25 originals, 100 direct crops, 25 measurements; zoom 100%, DPR 1, overflow 0 |
| scoped implementation gates | pass — frontend guard 0 violations plus guard unit tests 17/17, production build/bundle budget, five-viewport Playwright 2/2, actual-API Playwright 3/3 plus bounded correction rerun 1/1, user-guide CLI and corrected contract assertions, doc-impact, diff check |
| canonical independent Balanced audit | pass — initial Major 1 legacy shell classification corrected; re-review blocker 0, major 0, material-minor 0 |

Canonical Compose preflight는 다른 보존 worktree가 같은 composition을 소유해 거부했다. 해당 container, volume, database에는 변경을 가하지 않았고, 실제 API가 이미 제공하는 canonical synthetic fixture를 current-worktree Vite proxy로 읽어 browser 검증을 수행했다.
