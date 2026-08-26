# Issue #262 FE-07B Administration 구조 및 UI 정비

Status: 제품 소유자 교정을 반영한 구현, Main의 FHD·5-viewport 원본 검토와 canonical Balanced 독립 감사를 마쳤습니다. 제품 소유자는 최종 FHD 5화면을 검토한 뒤 2026-08-26에 FE-07B 병합을 승인했습니다. 폐기된 v2/inspection 화면은 증거와 사용자 가이드에 포함하지 않았습니다.

범위는 FE-07B Administration뿐입니다. FE-07A Materials와 두 Materials-to-Modeling 여정, Modeling domain/backend data와 release artifact는 변경하지 않았습니다.

## 현재 상태 분류와 결과

| 영역 | 구현 전 분류 | FE-07B 결과 |
| --- | --- | --- |
| Administration 진입·task order | missing | 기본 앱 바의 `Materials | Modeling | Activity`를 보존하고 `Database | Format definitions | Records | Access`를 한 taskbar에 둔다. 중복 Administration 표시는 제거하고 `/administration`은 Database로 진입한다. |
| Database/Profile/Table/Attribute/Layout/Subset/Link Type | partial | canonical Profile/Table 계약과 URL은 유지하되 정상 화면에서는 Configuration/Record type으로 표시한다. Database 미선택 상태는 `No database selected`이며 Configuration을 숨기고 독립 Record type 선택을 유지한다. stable ID와 exact revision ID는 URL에 고정한다. |
| Record preview와 Records 이동 | partial | 실제 server Record만 preview하고 `Open in Records`가 exact Table/Folder/Record identity·revision을 전달한다. 모든 지원 viewport에서 editor를 dominant preview로 바꾸고 scope와 선택 Layout 목록만 문맥으로 남긴다. |
| Format definitions | partial | 기존 upload→plan→confirm→apply→read-back→export 계약을 보존한다. `application_id` URL이 stale session recovery보다 우선하며 checksum/provenance를 직접 표시한다. |
| Records | partial | Record type scope, Search와 Filters, 결과 toolbar를 분리하고 `Name | Material code | Revision | Status` 결과를 주 작업면으로 만든다. 명시적 행 선택이나 Create가 bounded editor를 열며 `Save new revision`은 기존 exact revision을 덮어쓰지 않는다. 지원되는 create/revise, Folder, search/filter/saved view, Display layout과 multi-record import만 유지한다. |
| Access | behavior complete, UI partial | assignment 표를 주 작업면으로 만들고 `Member | Role | Permissions | Action`을 같은 행에서 읽는다. `Grant access`는 사용자가 열 때만 compact surface로 표시하며 실제 grant/remove 계약과 immutable 회수 이력을 유지한다. |
| Layout publication transition | missing product authorization | shared validation/publication API는 유지하지만 Layout 정상 화면에 승인된 validate→publish 전환이 없다. standalone validation이나 가짜 Published 상태를 표시하지 않고 이 계약 간극을 남긴다. |
| feature ownership | missing | `features/administration/{database-design,definition-bundles,records,access,routes,model}`과 public `index.ts`로 소유권을 분리했다. root compatibility re-export 제거는 #263 소유다. |

이 구조 정비와 exact-navigation UI는 하나의 응집된 단위다. route-state가 stable identity/immutable revision 연속성을 공급하고, 네 Administration task가 그 상태를 같은 shell에서 소비한다. 등록된 root hotspot에는 새 책임을 추가하지 않았다.

## 주 사용자 여정과 복구

1. Administrator가 `/administration`에서 Database를 열고 Database와 독립적인 `Demo Material Records · Revision 1` Record type을 명시적으로 선택한다.
2. Layouts에서 `Material overview` stable identity와 exact Version 1을 열어 필드 포함 여부와 순서를 검사한다. `New layout`과 `More → Duplicate layout`은 local editor만 열고 명시적 `Save` 전에는 서버를 변경하지 않는다.
3. `Preview`에서 실제 `DP780 synthetic reference steel (Draft, revision 2)`를 선택한다. URL은 Record type/Layout/Record stable ID와 exact revision ID를 함께 보존한다.
4. reload 후 같은 Layout Revision 1과 Record Revision 2가 다시 나타나는지 확인하고 `Open in Records`로 이동한다.
5. Records에서 결과 행의 Name·Material code·Revision·Status를 확인하고 exact Table/Folder/Record Revision 2를 연다. 새 Record Revision 1을 만든 뒤 `Save new revision`으로 immutable Revision 2를 저장하고 반환된 exact 좌표를 reload로 read-back한다.
6. Format definitions에서 `1 Choose files → 2 Review changes → 3 Apply changes → 4 Verify result` 순서로 처리하고 application ID·checksum·provenance를 다시 읽는다.
7. Access에서 Member·Role·server-derived Permissions를 확인한 뒤 `Grant access`하고, 같은 assignment ID에 `Remove access`를 실행해 active 목록에서 제거된 것을 확인한다. immutable 회수 이력은 서버에 남고 일반 탐색은 기본 앱 바를 사용한다.

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
| Format definitions | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-1366x768.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-1366x768.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-1440x900.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-1440x900.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-1920x1080.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-1920x1080.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-2560x1440.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-2560x1440.png) | [B](images/issue-208-schema-bundle-administration/administration-schema-bundle-plan-3840x2160.png) / [A](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-3840x2160.png) |

### FHD 제품 소유자 검토 packet

1920×1080 원본 다섯 장만 순서대로 검토하면 된다: [Database editor](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-1920x1080.png), [exact Record preview](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-1920x1080.png), [Records results](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-1920x1080.png), [Format definitions](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-1920x1080.png), [Access assignments](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-1920x1080.png). 이 순서형 링크 묶음이 중복 PNG를 만들지 않는 compact owner packet이다. 비교 기준은 같은 행의 before 원본이며 다섯 장 모두 기본 앱 바와 `Materials | Modeling | Activity`, 한 줄의 Administration taskbar를 보존한다.

### Locked 제품 소유자 피드백 trace

아래에는 작업에 직접 영향을 준 문장만 원문 그대로 남겼다. 욕설, 상태 확인과 작업 지연에
관한 대화는 구현 요구가 아니므로 제외했다. 다섯 화면은 하나의 승인 범위이며 일부 화면만
끝난 것으로 처리하지 않았다.

| 화면 | 제품 소유자의 actionable 원문 | 구현·경계 | 증거와 disposition |
| --- | --- | --- | --- |
| Database / Layout | “preview랑 more 버튼이랑 이상한게 배치되어있는데, 의도한거야? 정렬이 안 되어있는데 내가 매번 지적한건데, 너가 그렇게 하는 의도가 있나 궁금하네.”<br>“New datasheet layout 은 너무 긴데, new layout 이라고 하면 틀려? 어색해?”<br>“그리고 각 필드의 화살표는 클릭해서 위로 아래로 끌수있게 하는 UI 쓰면 편할거 같은데, 이건 어려워서 못하고 화살표로 한거야?”<br>“Save new version도 그냥 Save 하면 안 돼? Preview도 Save 옆에 있으면 저장전에 보고 좋을거 같은데. More는 그대로 두고”<br>“Datasheet fields에는 스크롤 없어도 되는거야? 짤리는거 같아서. 그리고 오른쪽에 클릭해서 드래그해서 위아래로 올리는 기능은 근데 = 기호 많이 쓰지 않나?” | 생성 동작은 `New layout`으로 줄였다. More를 heading 쪽의 보조 동작으로 제한하고 Preview/Save를 같은 footer에 정렬했다. 필드는 grip으로 pointer drag, keyboard reorder와 edge auto-scroll을 지원하며 목록에는 발견 가능한 local scrollbar를 둔다. Save 전에는 server write가 없다. | [FHD 원본](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-1920x1080.png). Main pass / auditor APPROVE / owner APPROVE 2026-08-26. |
| Exact Record preview | “오른쪽 위에 있는 헬퍼메시지들 꼭 필요해? 레코드 리비전 곱하기 스테이터스 드래프트가 뭔 뜻이지” | 반복 helper와 `r2`식 축약 metadata를 제거하고 선택한 실제 Record와 datasheet를 주 작업면으로 두었다. exact revision은 URL/read-back 계약으로 보존하며 정상 화면에는 이해 가능한 Revision/Status만 필요한 위치에 표시한다. | [FHD 원본](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-database-preview-1920x1080.png). Main pass / auditor APPROVE / owner APPROVE 2026-08-26. |
| Access | “history 필요없을거 같은데”<br>“grant access는 뭐고 remove access는 뭐야? 팀이나 유저하나당 grant access하는게 아닌가? 처음 보는 사람관점에서 전혀 이해가 안가네 설명해봐”<br>“사용자 목록은 어디서 조회해? uuid는 또 뭐야 아이디인가?” | active assignment의 Member·Role·Permissions·Action을 먼저 보여주고 history와 UUID 설명을 정상 화면에서 제거했다. Grant는 명시적으로 form을 열 때만, Remove는 해당 assignment 행에서만 수행한다. 사용자/팀 directory 검색이라는 별도 backend capability gap은 #327이 소유하며 이 화면이 가짜 목록으로 대신하지 않는다. | [FHD 원본](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-access-1920x1080.png). Main pass / auditor APPROVE / owner APPROVE 2026-08-26. |
| Format definitions | “format definition 아래 4개 메뉴랑 change to review에 아래 메뉴들이 뭔가 어색한듯하지만 이게 디자인 정책이나 공통 요소랑 부합하는지도 확인해줘. 완전 어색한건 아니고 다른 영역에서는 못 보던 방식이라 확인하는거야.”<br>“bundle이라는게 대체 뭐고 사용자가 고르면 뭐가 되는거야? 좀 실제적인 단어를 쓰면 안되나?” | 낯선 bundle 중심 dashboard를 `Choose files → Review changes → Apply changes → Verify result`의 실제 작업 순서로 바꾸고, 선택·변경·결과 영역에 공통 flat pane과 action hierarchy를 적용했다. application ID, checksum과 provenance는 exact read-back에 필요한 결과 근거로만 유지한다. | [FHD 원본](images/issue-262-fe07b-administration-architecture-ui/after/format-definitions/administration-format-definitions-review-1920x1080.png). Main pass / auditor APPROVE / owner APPROVE 2026-08-26. |
| Records | “records 이건 뭐하는 기능이야? 각 데이터에 항목을 추가하는건가? 뭐지? 아니면 개별로 데이터를 넣어주는건가”<br>“5번 은 뭔가 어색해. 줄 간격이나 제목과 입력 칸 사이의 간격이라든지..배치가 뭐가 유아틱한 느낌이 드는데? 정돈되고 간결한 느낌이 안 들어. 미묘하지만 어색하다는 말이야. 이것도 디자인 정책이나 공통 요소 쓴건지 확인ㅇ해줘.” | Record type 범위, Search/Filters와 `Name | Material code | Revision | Status` 결과를 먼저 두고, 행 선택 또는 Create 뒤에만 편집기를 연다. heading/field/action 간격을 shared semantic rhythm으로 맞추고 create/revise는 실제 API save/read-back과 연결한다. | [FHD 원본](images/issue-262-fe07b-administration-architecture-ui/after/originals/administration-records-1920x1080.png). Main pass / auditor APPROVE / owner APPROVE 2026-08-26. |

### #249 synthesis와 Q-01~Q-20

| 항목 | 결과 | 판정 |
| --- | --- | --- |
| 긴 탐색 트리 독립 스크롤 / Q-01 | N/A Main | canonical Administration fixture에는 긴 계층 tree가 없다. Layout field editor의 실제 overflow는 별도 local scroll로 검증했다. |
| 긴 결과 목록 독립 스크롤 / Q-02 | N/A Main | 캡처 fixture는 Record 1개와 active assignment 3개라 긴 결과 상태가 아니다. 짧은 목록에 가짜 scrollbar가 없다. |
| Materials 탐색 밀도 / Q-03 | N/A Main | FE-07B Administration은 Materials 탐색 행을 변경하지 않는다. |
| Fit 리본·그래프 / Q-04 | N/A Main | Fit topology가 없다. |
| 그래프 축 배치 / Q-05 | N/A Main | 공학 그래프가 없다. |
| 곡선 범례·결정 상태 / Q-06 | N/A Main | 곡선 범례가 없다. |
| 반응형 plot glyph / Q-07 | N/A Main | plot이 없다. |
| 항복 응답 표기 / Q-08 | N/A Main | 항복 응답 plot이 없다. |
| overflow affordance / Q-09 | pass Main | Layout field, Preview와 Records editor는 genuine overflow에만 local scroll을 제공하고 pointer/keyboard scroll reachability를 browser에서 확인했다. |
| Fit 범례 충돌 / Q-10 | N/A Main | Fit plot이 없다. |
| Fit rail 일관성 / Q-11 | N/A Main | Fit rail이 없다. |
| Export exact branch / Q-12 | N/A Main | Export setup을 변경하지 않는다. |
| Export 행 문법 / Q-13 | N/A Main | Export surface가 없다. |
| Export 준비 상태 / Q-14 | N/A Main | Export readiness가 없다. |
| 그래프 데이터 여백 / Q-15 | N/A Main | plot이 없다. |
| Solver-card preview / Q-16 | N/A Main | solver-card preview가 없다. |
| Carbon hierarchy·object 용어 / Q-17 | pass Main | taskbar→scope→identity-first list→selected decision fields 순서와 flat pane/divider를 사용한다. normal DOM에서 legacy card·eyebrow·badge·helper clutter selector가 0이다. |
| COMSOL task flow·Add/Save / Q-18 | pass Main | New/Duplicate layout은 no-write editor를 열고 explicit Save, exact read-back, Preview, Back to layout 순서로 진행한다. Records와 Format definitions도 선택→검토→실행→read-back을 보존한다. |
| exact links / Q-19 | pass Main | Layout Attribute pins, Record/Folder/Table revisions, Link Type cardinality와 Format Definition application을 구체 revision으로 유지한다. |
| SAP responsive composition / Q-20 | pass Main | navigator/form은 bounded이고 table/list/preview는 elastic이다. 1366/1440은 switching을 사용하고 1920~3840은 관련 영역을 인접 배치한다. 25개 측정 모두 page horizontal overflow 0이며 route별 4K hack이 없다. |

3840×2160 자동 capture는 CSS geometry 증거이지 실제 Windows 4K 판독성 주장이 아니다. 물리 장비 100%·150%·200% 판정은 #223 경계다.

## 검증 기록

| gate | 결과 |
| --- | --- |
| frontend tests | pass — full Vitest 447/447, 74 files; missing exact revision recovery, Database independence, no-write Layout, section/order preview, Records/Access/Format semantics 포함 |
| frontend guard | pass — 0 violations, 15 registered historical warnings |
| focused browser journey | pass — actual API 3/3(Database Layout create/read-back/preview/duplicate/delete, exact Record create/revise/reload와 Access grant/remove, semantic buttons), deterministic Format contract route 1/1(choose/review/confirm/apply/verify/export/reload) |
| five-viewport geometry | pass Main — 25 originals, 100 direct crops, 25 measurements; zoom 100%, DPR 1, overflow 0 |
| scoped implementation gates | pass — production build/bundle budget, guard unit 17/17, Administration/capture/user-guide/shared-foundation contracts 125/125, five-viewport Playwright 5/5, user-guide check, doc-impact, diff check |
| terse UI/accessibility audit | pass Main — task와 heading 위계, label/accessible name, keyboard 가능한 More·reorder·row selection, focus 가능한 local scroll, 유일한 filled primary, normal DOM legacy selector 0을 확인했다. |
| canonical independent Balanced audit | pass — 같은 auditor가 stable identity URL의 immutable revision 누락 거부와 조기 audit 승인 표기 교정을 read-back한 뒤 `approve`로 종결했다. 하나뿐인 Configuration 자동 선택은 제품 소유자의 명시적 승인 범위를 보존한다. |

Canonical Compose preflight는 다른 보존 worktree가 같은 composition을 소유해 거부했다. 해당 container, volume, database에는 변경을 가하지 않았고, 실제 API가 이미 제공하는 canonical synthetic fixture를 current-worktree Vite proxy로 읽어 browser 검증을 수행했다.
