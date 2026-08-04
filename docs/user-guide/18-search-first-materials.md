# Search-first Materials와 Modeling

일반 사용자의 전역 메뉴는 `Materials | Modeling | Activity`입니다. Administration은 권한이
있는 사용자의 메뉴에서 열며, `/database`와 기존 deep link는 호환 경로로 유지됩니다.

현재 제품 shell은 공통 44–48 px header와 workspace별 제어 영역으로 구성됩니다. Materials의
Browse/Filters/Subsets 전환은 왼쪽 Navigator에서 수행합니다. Modeling은 compact context/stage와
graph-adjacent의 얕은 ribbon에 현재 단계의 제어를 두며, 별도의 범용 command/status band를
지속적으로 렌더하지 않습니다. Modeling graph는 별도 compact header 아래에서 작업영역의 대부분을
유지합니다. `Ctrl+K`는 Materials 검색으로 이동합니다. 사용할 수 없는 명령은 비활성화되며
hover/focus title에 이유가 표시됩니다.

## 기존 Material과 CAE card 찾기

1. `/materials`는 Browse Navigator로 시작합니다. 이름, grade, code 또는 family를 검색해도 현재 Navigator mode는 바뀌지 않습니다.
2. 현재는 `Material class`, `Provider`, `Evidence source`, 정렬과 페이지로 결과를 좁힙니다. Yield는
   모든 재료에 공통으로 표시하거나 필터하지 않습니다.
3. 결과 행을 한 번 선택해 오른쪽 Context의 재료 계열과 다음 작업 가능 여부를 확인합니다. 행에서
   `Enter`를 누르거나 두 번 클릭하면 엽니다.
4. Material은 같은 작업영역의 중앙 datasheet에 열립니다. 요청한 자료를 읽을 수 없으면 임의의
   최신 자료로 바꾸지 않고 오류와 `Retry`를 표시합니다. 왼쪽 Navigator는 유지되며
   `Overview | Properties | Curves | CAE Cards | Evidence`를 검토할 수 있습니다.
5. Material Detail의 `Preview OpenRadioss`로 native ASCII를 확인한 뒤 `Download .rad`를 누릅니다.
   Preview가 필요 없다면 같은 compact record strip에서 바로 다운로드할 수 있습니다.

Browse Tree에서도 저장된 자료를 찾을 수 있습니다.

### Browse Tree에서 자료 찾기

1. 왼쪽 Navigator의 `Browse`를 선택합니다.
2. `Find in tree`에 이름을 입력하고, 방향키와 Home/End로 이동합니다.
3. Left/Right로 항목을 접거나 펼치고 Enter로 선택합니다. 선택한 자료는 중앙 화면에서 엽니다.

긴 목록은 손잡이, 마우스 휠 또는 키보드로 이동합니다. 결과가 짧거나 비어 있으면 불필요한
스크롤 막대가 나타나지 않습니다.

| 상태 | 캡처 |
| --- | --- |
| 긴 결과, 1366×768 | [긴 결과 1366](images/current/materials-search-long-1366x768.png) |
| 긴 결과, 1440×900 | [긴 결과 1440](images/current/materials-search-long-1440x900.png) |
| 긴 결과, 1920×1080 | [긴 결과 1920](images/current/materials-search-long-1920x1080.png) |
| 짧은 결과, 막대 없음 | [짧은 결과](images/current/materials-search-short-1440x900.png) |
| 빈 결과, 막대 없음 | [빈 결과](images/current/materials-search-empty-1440x900.png) |

넓은 화면에서도 작업 영역은 필요 이상으로 늘어나지 않고 페이지 전체 가로 스크롤이 생기지 않습니다.

| 경로 | 캡처 |
| --- | --- |
| 검색 결과, 2560×1440 | [넓은 검색 결과 2560](images/current/materials-search-2560x1440.png) |
| 검색 결과, 3840×2160 | [넓은 검색 결과 3840](images/current/materials-search-3840x2160.png) |
| 데이터시트, 2560×1440 | [넓은 데이터시트 2560](images/current/material-detail-2560x1440.png) |
| 데이터시트, 3840×2160 | [넓은 데이터시트 3840](images/current/material-detail-3840x2160.png) |

1920 px 이상에서는 그래프 오른쪽에 응답값 표가 함께 나타납니다. 행이 많을 때는 표 오른쪽
손잡이를 끌거나 마우스 휠과 키보드를 사용해 나머지 값을 확인할 수 있습니다. 작은 화면에서는
그래프를 먼저 보여 줍니다.

| 데이터시트 화면 | 현재 캡처 |
| --- | --- |
| 1366×768 | [데이터시트 1366](images/current/material-detail-1366x768.png) |
| 1440×900 | [데이터시트 1440](images/current/material-detail-1440x900.png) |
| 1920×1080 | [데이터시트 1920](images/current/material-detail-1920x1080.png) |
| 2560×1440 | [데이터시트 2560](images/current/material-detail-2560x1440.png) |
| 3840×2160 | [데이터시트 3840](images/current/material-detail-3840x2160.png) |

Find의 필터와 정렬은 결과에 반영됩니다. 각 행의 상세, graph, card는 사용자가 열 때 확인합니다.

검색어, Material class, Provider, Evidence source와 선택 Material은 `/materials` URL에 저장됩니다.
Material Detail의 탭과 관련 작업은 선택한 자료를 유지합니다.
Material Detail command bar, 왼쪽 `← Results`, 브라우저 뒤로 가기는 같은 검색 조건과 선택으로
돌아옵니다.

### Layout, Related와 Evidence 확인

- `Properties`와 `Curves`에서 현재 자료의 속성과 곡선을 확인합니다.
- Related records 목록에서 연결된 자료를 선택하면 중앙 datasheet에서 확인할 수 있습니다. 자료를
  읽지 못하면 최신 자료로 바꾸지 않고 오류와 `Retry`를 표시합니다.
- `Download CSV`는 현재 화면의 표 값을 내려받습니다. `Curves` 탭에서는 연결된 curve preview를
  확인하고, `Related records`에서는 연결된 자료를 다시 엽니다.

## 시험 데이터에서 card delivery 준비하기

1. Modeling의 Data에서 canonical Test Data JSON, CSV 또는 XLSX를 선택합니다.
2. Library에서 현재 재료와 상태에 연결된 정확한 Test Data revision을 한 개 이상 고릅니다. specimen,
   revision, 채널과 원본/정규화 단위를 확인하고, 체크박스로 모델링에 포함할 곡선과 눈 아이콘으로 그래프에
   표시할 곡선을 각각 정합니다. 여러 반복시험은 실제 곡선을 한 그래프에서 비교합니다.
3. JSON schema/channel/quantity semantics/original+normalized unit 또는 CSV/XLSX의 worksheet,
   column/channel/unit mapping을 확인합니다. 필수 채널 누락, 같은 열의 중복 사용, 지원하지 않는 원본 단위는
   Update/Save를 막으며 파일과 마지막 정상 그래프를 유지한 채 수정·재시도할 수 있습니다.
4. Process에서 원본을 보존한 채 crop, smoothing, resample과 반복시험 통계를 검토합니다.
5. Fit의 한 표에서 candidate별 상태, 오차, 적용 범위와 경고를 비교하고 같은 그래프의
   response, residual, tangent modulus와 observed/extrapolated 경계를 확인합니다.
6. 하나의 candidate를 명시적으로 선택하고 이유를 기록합니다. 추천 결과는 선택을 대신하지 않습니다.
7. Export는 현재 작업에서 선택하고 저장한 재료, 상태, 시험 데이터 및 모델 결과가 서로 맞을 때만
   해당 재료군의 전달 옵션을 엽니다. 내보내기 전에 필요한 값과 대상 조건을 다시 확인합니다. 하나라도
   최신이 아니거나 현재 작업과 맞지 않으면 **Blocked**로 남으며, 다른 작업의 결과로 대신 내보내지 않습니다.

`Import JSON / CSV / XLSX`에서 CSV/XLSX의 `Open governed mapping workbench`를 선택하면
`/datasets/import`가 최근 Modeling session의 exact Material State를 복원합니다. 여기서 immutable
원본 preview → sheet/header/channel/unit 확인 → Import Profile revision 승인 → raw/normalized SI
Dataset 생성을 완료할 수 있습니다. Canonical adapter로 돌아오면 같은 파일을 `cmp.test-data`로
검증·저장해 Process 입력으로 선택합니다. JSON 파일은 server validation에서 schema, channel,
quantity semantics, original/normalized unit과 missing reason을 먼저 확인합니다.

Fit 그래프의 곡선은 계속 `Preview — not saved`로 표시됩니다. 계산 성공이나 추천은
선택·검토·승인을 뜻하지 않습니다. 선택·저장 조건이 충족되지 않은 상태는 Warning 또는
Blocked로 남습니다. 추천과 선택은 별도 상태이며, 행을 명시적으로 고르고 이유와 필요한 경고
확인을 마친 candidate만 상단의 **Save fit & continue**로 immutable Processing Output을 만듭니다.
금속 blend는 두 law·ratio·두 parameter set을, 폴리머는 server가 실제 산출한 term-count identity를
그대로 저장합니다. Export는 current session의 exact Material, State, Test Data와 Processing Output이
모두 pin되지 않으면 prerequisite만 표시하며 다른 세션이나 전역 output을 대체 사용하지 않습니다.
모두 exact pin일 때만 family adapter의 mapping preflight와 native card 작업을 계속할 수 있습니다.
이 경로에서도 server 검사가 실패하면 Export를 완료로 표시하거나 fallback delivery를 만들지 않습니다.

처리 설정, 일괄 실행, 전체 식별값과 JSON 근거는 Advanced/Evidence에 남습니다.
Unsupported mapping은 차단되고 approximation은 명시적 확인이 필요합니다.

### Modeling 화면 읽기

- 상단 command bar의 `New session | Save draft | Undo | Redo`는 현재 보정 세션에 작용하고,
  `Data | Process | Fit | Export` stepper는 같은 세션의 일반 작업 단계를 전환합니다. 검증과
  review/release는 Advanced 또는 (향후) Activity queue의 별도 작업입니다.
  단계 이름만 간결하게 보이며, 준비 상태와 다음 행동은 hover/focus 설명과 접근성 레이블로 확인합니다. 단계와 material family는
  URL에, 선택한 Test Data의 정확한 revision·curve·step·plot view·settings 상태는 clear 가능한 Modeling session v4에 저장됩니다.
  새 session은 항상 Data에서 시작하며, 진행 중이던 Material/State/Test Data/Mapping/Output
  pointer나 늦게 도착한 자동 선택 결과를 다시 pin하지 않습니다.
- Data/Process/Fit의 왼쪽 `Curves`와 Process/Fit의 `Process`는 27 px 일반 문자열 행입니다. Data에서는 specimen과
  revision을 한 개 이상 포함할 수 있고, 체크박스는 모델링에 포함할 곡선, 눈 아이콘은 그래프에 표시할 곡선을 뜻합니다.
  원본 document key와 exact revision은 hover/focus title에서 확인합니다. 서로 다른 반복시험은 실제 서버 preview 곡선으로
  같은 그래프에 겹쳐 보며, 포함 선택은 reload 뒤에도 유지됩니다.
- 가운데 그래프가 주 작업면입니다. Process와 Fit을 전환해도 선택 curve와 server preview가
  유지되며 response, residual, tangent 또는 extrapolation 보기를 같은 그래프에서 바꿉니다.
  현재 캡처 자동화는 렌더링된 가로축이 Modeling workspace 폭의 72% 미만이면 실패합니다.
- 1366 px 이상에서는 current-step settings가 그래프 위의 104 px 이하 얕은 ribbon으로 열립니다.
  오른쪽 접기 버튼으로 필요할 때 숨길 수 있습니다. 이 ribbon은 세 번째
  열이 아니므로 그래프 폭을 줄이지 않습니다.
- `Add method`는 한 줄 도구 메뉴입니다. Recipe와 Batch는 `Advanced · Recipe and Batch`, ordered
  step JSON은 `Advanced Recipe JSON`에서 확인합니다.
- Fit ribbon의 candidate 표는 상태, 오차, 적용 범위와 bound 경고를 같은 행에서 비교합니다.
  선택한 식의 parameter와 bounds는 disclosure로 열 수 있고, 선택 이유는 수치 preview를 다시
  계산하지 않는 decision evidence입니다. 추천 변경은 선택을 바꾸지 않으며, reason만 입력해도
  선택된 것으로 처리하지 않습니다.
- Export dock은 저장한 현재 source/model이 확인될 때만 `Model → mapping preflight → native card` 순서를 보여 줍니다. solver 이름·버전과
  `kg·m·s (SI)` unit system을 읽은 뒤 preflight를 실행합니다. unsupported 항목은 생성을 막고,
  approximated/ignored 항목은 바로 옆 확인을 요구합니다. 생성 뒤 native ASCII card와 mapping
  report를 내려받거나 Material의 CAE Cards로 이동할 수 있습니다.
- Export를 열었다가 Fit으로 돌아와도 그래프 DOM, 선택 curve와 plot view는 그대로 유지됩니다.
- Material revision/State/physical family/Test Data가 바뀌면 호환되지 않는 Test Data 선택은 추측 없이 clear되고 downstream current pointer도 clear되며,
  실제로 존재한 Review/Release history만 Stale evidence로 남습니다. history가 없으면 Review/Release는
  정책 prerequisite의 Blocked 상태입니다. mapping/process/fit/target 변경도 영향 범위를 표시해
  재계산 또는 재생성을 요구합니다. source revision과 Recipe step을 바꾼 뒤에는 command bar의 Undo/Redo로 draft를 되돌릴 수 있습니다.
  브라우저를 닫을 때 미저장 변경이 있으면 이탈 경고가 한 번 표시되며, `New session`은 확인 후
  비수치 UI session 상태만 초기화합니다. Preview는 계속 `Preview — not saved`로 표시되어
  저장한 처리 결과 또는 선택·저장한 모델과 혼동되지 않습니다.
- 저장 시 다른 사용자가 같은 Recipe head를 먼저 갱신했다면 조용히 덮어쓰지 않습니다. 화면의
  `Reload current`, `Keep local draft as new revision`, `Cancel` 중 하나를 선택해 stale exact-revision
  충돌을 명시적으로 해결합니다.

## 현재 대표 화면

아래 이미지는 최신 `main`의 Compose demo에서 현재 캡처 자동화로 생성한 화면입니다. 완료 PR의
before/after 및 과거 Task 화면은 `docs/17-evidence`에만 보관하며 현재 사용법의 기준으로 사용하지
않습니다.

![Materials 검색과 선택](images/current/materials-search-1440x900.png)

![Searchable governed Browse Tree](images/current/materials-browse-1440x900.png)

![Material Detail과 직접 solver-card action](images/current/material-detail-1440x900.png)

![Native CAE Cards](images/current/material-cae-cards-1440x900.png)

CAE Cards에서는 command bar의 현재 형식 다운로드만 filled primary action입니다. 표의 각 형식별
다운로드는 secondary action이므로 한 화면에서 여러 primary action이 경쟁하지 않습니다.

![Persistent Modeling Fit](images/current/modeling-fit-1440x900.png)

Fit keeps the curve rail and response graph visible while model/range/extrapolation inputs stay in the
shallow task band. **Candidate parameters** separates the server recommendation
from the engineer's explicit selection; it contains comparison metrics and reason/warning acknowledgement.
The only **Save fit & continue** action remains in the top action row.

## Activity에서 진행 상황 확인

Material 상세 또는 Native Solver Card preview에서 **Request review**를 누르고 검토 사유를 적으면,
현재 화면의 자료로 요청됩니다.
같은 revision에 요청이 있으면 다시 보내지 않고 **Waiting for review**, **Approved**, 또는
**Changes requested** 상태를 보입니다. 전송 오류는 사유를 유지한 채 **Retry request**로 다시 시도할 수
있습니다. 승인이나 변경 요청 결정은 Activity의 Reviewer/Administrator만 기록합니다.

현재 Activity 캡처는 실제 pending review request를 사용해 Reviewer/Administrator의 **Review**
동작과 User의 **In progress** 상태를 검증합니다. 브라우저에 Modeling session이 있으면 exact
stage·revision·curve 선택으로 복귀하고, 없으면 **Start Modeling** 복구 동작을 표시합니다.

![최근 브라우저 Modeling session이 없는 Activity 초기 상태](images/current/activity-1440x900.png)

관리자는 user menu에서 Administration을 열 수 있습니다. Database design은 왼쪽 객체 탐색기,
가운데 목록, 오른쪽 속성 편집기를 한 화면에 유지합니다. Current table을 바꾸면 Attribute, Layout,
Subset과 Link Type 목록이 해당 Table 문맥으로 바뀌며, Link Type은 출발/도착 Table과 방향 문구를 읽기 쉬운
형태로 보여 줍니다. 현재 서비스가 지원하지 않는 기존 정의 수정·삭제는 가짜 버튼으로 노출하지
않습니다.

![Administration Database design](images/current/administration-database-1440x900.png)

같은 3열 편집 구조는 [1366×768 화면](images/current/administration-database-1366x768.png)과
[1920×1080 화면](images/current/administration-database-1920x1080.png)에서도 가로 스크롤 없이
유지됩니다.

## Desktop viewport evidence

1366 px에서는 optional 상세와 settings를 접어 result/graph 폭을 지키고, 1920 px에서는 중앙 작업면이
남는 폭을 확장합니다. 모든 panel을 같은 비율로 늘리거나 좁은 중앙 max-width에 가두지 않습니다.
현재 캡처는 가로축 drawable이 전체 Modeling workspace의 약 75% 이상을 차지하며, 캡처 자동화가
Data/Process/Fit/Export의 세 viewport 모두에서 72% hard gate를 적용합니다.

![Materials at 1366](images/current/materials-search-1366x768.png)

![Materials at 1920](images/current/materials-search-1920x1080.png)

### Modeling 단계·해상도 검수 화면

아래 화면은 같은 exact DP780 입력을 선택한 브라우저 session에서 Data → Process → Fit → Export를
전환해 각 단계의 비동기 preview가 끝난 뒤 캡처했습니다. Data는 Library, Local file,
Test Data JSON을 한 ribbon에서 고르고 등록 전에 같은 그래프로 확인합니다. Process는 원본과 선택
단계를 겹쳐 보고 preview와 immutable output commit을 명시적으로 나눕니다. Fit은 네 candidate를
한 표와 세 그래프 보기로 비교하고 명시적인 선택 결과 저장을 제공합니다. 검증과 review/release는
일반 단계가 아니라 Advanced/Activity의 별도 작업입니다. Export는 저장한 source/model을 확인한 뒤
Neutral, mapping preflight와 native-card 전달을 한 dock에 연결합니다.

UXC-02 live Compose recapture는 New session의 pin-free Data-first 상태와, exact Test Data·Mapping
Profile·Processing Output을 다시 선택한 Data → Process → Fit → Export 흐름을 분리해 검증합니다.
Export adapter는 늦게 도착한 model-list refresh가 방금 promotion한 IR 선택을 덮지 않도록 local
결과와 server 목록을 병합합니다. Catalog projection이 아직 없으면 related-data panel은 이를
`unprojected` terminal state로 명시하며 resolved link로 위장하지 않습니다. Capture별
source/time/command는 [`screenshot manifest`](screenshot-manifest.yaml)에 기록합니다.

UXC-01 Materials Search 이미지는 web과 API를 같은 코드로 재빌드한 뒤
1366×768, 1440×900, 1920×1080에서 다시 캡처했습니다. 세 viewport 모두 horizontal overflow가
0이었고, Browse 기본 mode, server total과 Material class facet, 그리고 사용자용 결과 열을 확인했습니다.
캡처는 fixture를 변경하지 않으므로 생성 명령을 실행한 결과가 아니라 각 단계의 현재 조작면을
보여 줍니다. 실제 생성 완료 흐름과 identity/revision 고정은 DUI-06 evidence report에 기록합니다.

| 단계 | 1366×768 | 1440×900 | 1920×1080 |
| --- | --- | --- | --- |
| Data | ![Data 1366](images/current/modeling-data-1366x768.png) | ![Data 1440](images/current/modeling-data-1440x900.png) | ![Data 1920](images/current/modeling-data-1920x1080.png) |
| Process | ![Process 1366](images/current/modeling-process-1366x768.png) | ![Process 1440](images/current/modeling-process-1440x900.png) | ![Process 1920](images/current/modeling-process-1920x1080.png) |
| Fit | ![Fit 1366](images/current/modeling-fit-1366x768.png) | ![Fit 1440](images/current/modeling-fit-1440x900.png) | ![Fit 1920](images/current/modeling-fit-1920x1080.png) |
| Export | ![Export 1366](images/current/modeling-export-1366x768.png) | ![Export 1440](images/current/modeling-export-1440x900.png) | ![Export 1920](images/current/modeling-export-1920x1080.png) |
| UXC-02 session shell | ![Session 1366](images/current/modeling-session-1366x768.png) | ![Session 1440](images/current/modeling-session-1440x900.png) | ![Session 1920](images/current/modeling-session-1920x1080.png) |

UXC-02 session shell 화면은 선택 사항인 곡선 탐색기를 접어 그래프 공간을 넓힌 실제 작업 상태를
보여 줍니다. 아래 Empty new session 화면은 탐색기를 펼친 채 Local file로 복구하는 별도 상태입니다.

Task 1 Data의 targeted capture는 실제 Library에서 고른 exact revision을 두 개 이상 Include하고,
그래프의 Show를 바꾼 뒤 reload해 같은 선택이 남는지 확인합니다. 2560×1440과 3840×2160도 같은
정상 흐름으로 확인하며, 1440×900에서는 새 session의 빈 Data와 실행 중 생성한 잘못된 CSV mapping
상태를 별도 예외 화면으로 기록합니다. CSV는 저장소에 fixture로 남기지 않습니다.

| Data evidence | 화면 |
| --- | --- |
| Wide 2560×1440 | ![Data 2560](images/current/modeling-data-2560x1440.png) |
| Wide 3840×2160 | ![Data 3840](images/current/modeling-data-3840x2160.png) |
| Empty new session 1440×900 | ![Data empty](images/current/modeling-data-empty-1440x900.png) |
| Invalid runtime CSV 1440×900 | ![Data invalid](images/current/modeling-data-invalid-1440x900.png) |
