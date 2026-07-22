# Search-first Materials와 Modeling

일반 사용자의 전역 메뉴는 `Materials | Modeling | Activity`입니다. Administration은 권한이
있는 사용자의 메뉴에서 열며, `/database`와 기존 deep link는 호환 경로로 유지됩니다.

인증 후 화면은 46 px application bar, 38 px workspace command bar, 작업영역, 24 px status bar
순서로 구성됩니다. command bar는 현재 workspace의 Search/Browse/Subsets, Data/Process/Fit/Export
같은 작업 명령만 표시합니다. status bar는 선택 Material 또는 Modeling session, exact revision
문맥, 실행 중 계산, 경고와 연결 상태를 계속 표시합니다. `Ctrl+K`는 Materials 검색으로 이동하고,
`F6`와 `Shift+F6`는 application bar, command bar, navigator/main/inspector, status bar 사이를
순환합니다. 사용할 수 없는 명령은 비활성화되며 hover/focus title에 이유가 표시됩니다.

## 기존 Material과 CAE card 찾기

1. `/materials`에서 이름, grade, code 또는 family를 검색합니다.
2. family, source, normalized property 범위, solver availability 또는 release 상태를 좁힙니다.
3. 결과 행을 선택해 핵심 물성과 사용 가능한 solver card를 확인합니다.
4. Material을 열어 `Overview | Properties | Curves | CAE Cards | Evidence`를 검토합니다.
5. Material Detail의 `Preview OpenRadioss`로 native ASCII를 확인한 뒤 `Download .rad`를 누릅니다.
   Preview가 필요 없다면 같은 compact record strip에서 바로 다운로드할 수 있습니다.

Browse Tree는 검색의 대체 수단으로 Database, Profile, Table, Folder, Record 계층을 유지합니다.
Table, Attribute, Layout, Subset, Link Type과 exact revision은 삭제되지 않으며 Browse, Evidence
또는 Administration에서 접근합니다.

### Browse Tree에서 Record 찾기

1. Materials 상단의 `Browse Tree`를 선택합니다.
2. 왼쪽 Browse navigator에서 Database, Profile, Table을 확인합니다. Search/Browse/Subsets
   전환은 중복된 panel tab이 아니라 상단 command bar 한 곳에서만 수행합니다.
3. Folder 앞의 disclosure를 열거나 고정된 `Find in tree`에 이름을 입력합니다. 검색 결과는
   상위 Folder 경로를 유지합니다.
4. 방향키와 Home/End로 이동하고, Left/Right로 접거나 펼치며, Enter로 Record를 선택합니다.
5. Record를 한 번 선택하면 중앙 Material 결과와 exact revision 문맥이 연결됩니다. 두 번
   누르면 Layout datasheet를 엽니다.
6. `Subsets`에서는 관리자가 저장한 typed 검색 조건을 같은 Tree에 적용합니다.

Tree는 자체 스크롤을 사용하므로 깊은 계층에서도 Database/Profile과 검색 동작을 다시 찾을
수 있습니다. 긴 이름은 한 줄로 유지되고 hover/focus의 전체 이름으로 확인합니다.

검색어, family/source/solver/status/수치 범위, 정렬, Browse/Subsets mode와 선택 Material은
`/materials` URL에 저장됩니다. Material Detail command bar의 `Back to results`를 누르면 같은 검색 조건과 선택으로
돌아옵니다. Browse에서 선택한 exact Record는 현재 browser session에만 보존되며 돌아올 때 실제
Table과 Folder ancestor를 다시 조회해 펼칩니다.

### Layout, Related와 Evidence 확인

- `Properties`와 `Curves`는 관리자가 정의한 현재 Record Layout의 Attribute를 해당 일반 사용자
  탭에 투영합니다.
- `Evidence`의 Related Records는 Link Type의 forward/reverse label을 사용하고, Workflow는
  Material에서 native solver card까지의 Record 순서를 표시합니다.
- 추가 Layout은 `Additional Layout datasheets and typed values`에서 선택합니다.
- full revision ID, aggregate ID, content hash, classification과 change reason은
  `Technical revision and provenance identifiers`를 펼쳐 확인합니다.
- 수량 Attribute는 원본 값/단위와 정규화 값/단위, quantity semantics를 함께 보존합니다.

## 시험 데이터에서 새 card 만들기

1. Modeling의 Data에서 canonical Test Data JSON, CSV 또는 XLSX를 선택합니다.
2. JSON schema/channel/quantity semantics/original+normalized unit 또는 CSV/XLSX의 worksheet,
   column/channel/unit mapping을 확인합니다.
3. Process에서 원본을 보존한 채 crop, smoothing, resample과 반복시험 통계를 검토합니다.
4. Fit에서 candidate, response, residual과 extrapolation을 비교합니다.
5. Export에서 Material Model IR, Neutral Material과 solver mapping을 확인하고 native card를
   생성한 뒤 Material Library에 저장합니다.

`Import JSON / CSV / XLSX`에서 CSV/XLSX의 `Open governed mapping workbench`를 선택하면
`/datasets/import`가 최근 Modeling session의 exact Material State를 복원합니다. 여기서 immutable
원본 preview → sheet/header/channel/unit 확인 → Import Profile revision 승인 → raw/normalized SI
Dataset 생성을 완료할 수 있습니다. Canonical adapter로 돌아오면 같은 파일을 `cmp.test-data`로
검증·저장해 Process 입력으로 선택합니다. JSON 파일은 server validation에서 schema, channel,
quantity semantics, original/normalized unit과 missing reason을 먼저 확인합니다.

기존 Neutral/Card가 있어도 Export의 `Create from another reviewed output`으로 방금 commit한
Processing Output을 선택할 수 있습니다. 이 action은 기존 immutable Neutral을 덮어쓰지 않고 새
IR/Neutral/Card revision을 추가합니다.

Mapping Profile, Recipe/Batch, full revision, hash와 JSON evidence는 Advanced/Evidence에 남습니다.
Unsupported mapping은 차단되고 approximation은 명시적 확인이 필요합니다.

### Modeling 화면 읽기

- 왼쪽 `Curves`와 `Process`는 27 px 일반 문자열 행입니다. `Curve 01` 같은 짧은 이름을
  선택하고, 원본 document key와 exact revision은 hover/focus title에서 확인합니다.
- 가운데 그래프가 주 작업면입니다. Process와 Fit을 전환해도 선택 curve와 server preview가
  유지되며 response, residual, tangent 또는 extrapolation 보기를 같은 그래프에서 바꿉니다.
- 1440 px 이상에서는 current-step settings가 그래프 위의 얕은 ribbon으로 열립니다. 1366 px에서는
  그래프 노출을 위해 기본적으로 닫혀 있으며 `Show settings`로 엽니다. 이 ribbon은 세 번째
  열이 아니므로 그래프 폭을 줄이지 않습니다.
- `Add method`는 한 줄 도구 메뉴입니다. Recipe와 Batch는 `Advanced · Recipe and Batch`, ordered
  step JSON은 `Advanced Recipe JSON`에서 확인합니다.
- Export는 reviewed fitting에서 Neutral Material과 solver-native preview/download로 이어집니다.

![Full-width Materials production shell](../15-demo/images/ux-redesign-v2/final-materials-1440x900.png)

![DUI-01 compact Materials application and command bars](../15-demo/images/ux-redesign-v2/dui-01-materials-search-1440x900.png)

![Searchable governed Materials Browse Tree](../15-demo/images/ux-redesign-v2/final-browse-tree-1366x768.png)

![DUI-01 Browse Tree in the same compact shell](../15-demo/images/ux-redesign-v2/dui-01-browse-tree-1440x900.png)

![Material Detail with direct OpenRadioss delivery](../15-demo/images/ux-redesign-v2/material-detail-overview-1440x900.png)

![DUI-01 Material Detail command and status context](../15-demo/images/ux-redesign-v2/dui-01-material-detail-1440x900.png)

![Native CAE card preview and direct downloads](../15-demo/images/ux-redesign-v2/material-detail-cae-cards-1440x900.png)

![Related, Workflow, Layout and progressive Evidence](../15-demo/images/ux-redesign-v2/material-detail-evidence-1440x900.png)

![Graph-dominant Modeling Fit workspace](../15-demo/images/ux-redesign-v2/final-modeling-fit-1440x900.png)

![DUI-01 Modeling commands and persistent session status](../15-demo/images/ux-redesign-v2/dui-01-modeling-fit-1440x900.png)

![Explicit JSON, CSV and XLSX Modeling Data entry](../15-demo/images/ux-redesign-v2/modeling-data-1366x768.png)

![Governed CSV and XLSX import workbench](../15-demo/images/ux-redesign-v2/governed-import-1440x900.png)

![Reviewed IR to native solver-card Export](../15-demo/images/ux-redesign-v2/modeling-export-1440x900.png)

## Activity에서 진행 상황 확인

`Activity`는 최근 Modeling session과 review를 먼저 보여 줍니다. Recipe lifecycle, Batch preflight,
mapping report와 장시간 실행의 상세 진단은 같은 화면의 Advanced jobs에서 필요할 때만 펼칩니다.

![Recent modeling and review activity](../15-demo/images/ux-redesign-v2/activity-1440x900.png)

![DUI-01 Activity command and status shell](../15-demo/images/ux-redesign-v2/dui-01-activity-1440x900.png)

관리자는 user menu에서 Administration을 열 수 있습니다. Database design route는 같은 shell 안에서
Table, Attribute, Layout, Subset과 Link Type 편집 상태를 유지하며, 현재 configuration과 validation
상태를 status bar에 표시합니다.

![DUI-01 Administration database design shell](../15-demo/images/ux-redesign-v2/dui-01-administration-1440x900.png)

## Desktop viewport evidence

1366 px에서는 optional 상세와 settings를 접어 result/graph 폭을 지키고, 1920 px에서는 중앙 작업면이
남는 폭을 확장합니다. 모든 panel을 같은 비율로 늘리거나 좁은 중앙 max-width에 가두지 않습니다.

![Materials at 1366](../15-demo/images/ux-redesign-v2/final-materials-1366x768.png)

![Materials at 1920](../15-demo/images/ux-redesign-v2/final-materials-1920x1080.png)

![Modeling Fit at 1366](../15-demo/images/ux-redesign-v2/final-modeling-fit-1366x768.png)

![Modeling Fit at 1920](../15-demo/images/ux-redesign-v2/final-modeling-fit-1920x1080.png)
