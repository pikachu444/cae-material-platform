# Configurable Catalog와 Material Modeling 사용자 흐름

이 문서는 물성 데이터의 구조를 만들고 값을 등록·검색하는 사용자 흐름을 설명한다. Administration에서
Database와 Profile을 먼저 만들고, 그 안에 Table, Attribute, Layout, Subset과 Link Type을 정의한다.

## 지금 사용할 수 있는 Catalog schema designer

1. 우측 workspace menu에서 **Administration → Database design**을 연다. `/catalog/schema`는
   같은 Administration 화면으로 연결되는 호환 주소다.
2. 왼쪽 **Objects**에서 Database, Profile, Table, Attribute, Layout, Subset 또는 Link Type을 고른다. 가운데 목록과
   오른쪽 속성 화면은 같은 선택을 유지한다.
3. **Current table**을 바꾸면 Attribute, Layout, Subset 목록이 그 Table 기준으로 즉시 바뀐다.
4. **Add Database**, **Add Profile**, **Add Table** 또는 **Add Attribute**를 누른 뒤, 표시명·참조 key·사용자에게 필요한 입력 안내만
   작성한다. 수치 Attribute는 무엇을 뜻하는 수치인지와 표준 단위를 함께 입력하고, Record reference는
   연결할 Table을 고정한다.
5. **Add layout**은 선택한 Attribute를 현재 Attribute 순서로 datasheet Layout에 저장하고, **Add subset**은 현재
   Table의 검색 보기를 만든다. 기존 항목을 수정하면 새 초안이 생기며, 검증을 통과한 초안만 **Publish**할 수 있다.
6. Link Type에서는 출발/도착 Table, 양방향으로 읽을 문구와 한 항목당 연결 수를 정한다. 저장할 때
   두 Table의 현재 정의 revision이 함께 고정된다.

Administration에서는 한 작업 묶음의 다음 주요 동작 하나만 파란색으로 강조한다. 기존 정의를
편집할 때 **Check**와 **Save draft**는 보조 동작이고 **Publish**가 주요 동작이다. 여러 행 등록에서는
검사가 끝나기 전 **Register checked rows**가 흐리게 비활성화되며, 모든 행이 유효해진 뒤에만 실행할
수 있다. 녹색은 저장 성공 같은 상태 표시에만 사용한다.

넓은 화면에서는 Database design shell이 viewport를 사용하되 Objects navigator, 정의 목록, 속성
form으로 이루어진 작업 묶음은 가운데의 읽기 좋은 공통 범위에 남는다. 속성 form은 남는 화면 폭만큼
늘어나지 않고, 작업 묶음 양쪽 여백은 균형을 유지한다. 같은 화면을
[2560×1440](images/current/administration-database-2560x1440.png)과
[3840×2160](images/current/administration-database-3840x2160.png)에서도 확인할 수 있다.

Table/Attribute/Layout/Subset은 stable identity와 immutable revision으로 저장되며, 새 정의는 기존
Record나 과거 revision을 바꾸지 않는다.

### JSON Schema 정의를 적용 전에 확인하기

여러 record schema를 한 번에 준비하는 관리자는 현재 API에서 Schema Definition Bundle dry-run을
실행할 수 있다. JSON 원문을 immutable Artifact로 저장한 뒤 Artifact ID와 lowercase SHA-256을
`POST /api/v1/catalog/schema-definition-bundles:plan`에 보낸다. 응답은 현재 Catalog와 비교한
`create`, `update`, `no-op`, `conflict`, `error`와 수정 위치를 반환한다. 같은 bundle 안의 local
JSON Pointer와 선언된 record `$id`만 참조할 수 있다.

오류가 있으면 기존 Artifact를 수정하지 않고 새 Artifact로 다시 요청한다. 이 기능은 계획만 만들며
Catalog revision, current pointer, publication과 감사 이력을 바꾸지 않는다. Bundle에 없는 기존
객체도 삭제하지 않는다. Administration의 upload/apply 화면과 실제 적용·발행은 아직 제공되지 않는다.
운영 절차와 no-write 응답 필드는 [관리자 가이드](../admin-guide/index.md#21-api로-schema-definition-bundle-점검)를
참고한다.


## Catalog Record 등록·검색·비교

1. 일반 탐색은 **Materials → Browse Tree**를 사용한다. 새 Folder/Record를 관리하는 고급 작업은
   `/catalog/records`를 열고 Table과 datasheet Layout을 선택한다.
2. 필요하면 왼쪽 **New Folder**에서 root 또는 parent Folder를 만든다. cycle은 거부된다.
3. **New record**를 누르고 이름, 외부 key, Folder와 Layout 순서의 Attribute 값을 입력한다.
4. 수치값은 원본 값·원본 단위 문자열·정규화 값이 모두 보이도록 입력한다. normalized unit과
   quantity semantics는 Attribute revision에서 가져오며 숨겨서 바꾸지 않는다.
5. **Create Record revision 1**을 선택한다. 수정할 때는 검색 결과를 열고 **Save new immutable
   revision**을 선택한다. 기존 revision은 덮어쓰지 않는다.
6. 이름·설명·text Attribute, Folder, discrete facet 또는 normalized 수치 범위로 검색한다.
7. 현재 검색을 이름과 함께 Subset revision으로 저장하고, 저장된 chip으로 다시 적용한다.
8. 두 revision 이상인 Record를 열면 revision 1과 current 사이의 Attribute 차이를 확인한다.
9. **Single entry**에서 검색 결과의 Record를 열면 current revision의 **Request review** action이
   같은 화면에 나타난다. 사유를 입력했다가 취소하거나 전송하면 Activity에서 해당 exact revision의
   상태를 이어서 확인한다.
10. 여러 건은 **Multiple rows**를 선택해 CSV/TSV/XLSX 내용을 확인하고 원본 열, Attribute, 값 형식,
   원본 단위와 재료 상태를 매핑한다. **Check rows**에서 행별 오류를 고친 뒤 모든 행이 유효할 때만
   **Register checked rows**를 누른다. 이미 데이터가 연결된 재료 상태는 검색 결과에서 기존 Record를
   열어 수정한다. 등록 과정에서 기존 재료나 상태를 자동으로 만들거나 덮어쓰지 않는다.

![여러 행 물성 데이터 등록](images/current/administration-records-1440x900.png)

같은 등록 화면은 [1366×768](images/current/administration-records-1366x768.png),
[1920×1080](images/current/administration-records-1920x1080.png),
[2560×1440](images/current/administration-records-2560x1440.png),
[3840×2160](images/current/administration-records-3840x2160.png)에서도 확인할 수 있다. shell은 전체
viewport를 사용하지만 검색·등록 작업 묶음과 입력 form은 가운데의 읽기 좋은 범위에 남으며, 원본
파일과 행 검사 명령을 첫 화면에 유지한다.

아래 화면은 실제 Docker API와 PostgreSQL에 저장한 DP600 및 AA6061-T6 Record를 조회한 결과다.
왼쪽 facet은 재료군별 건수를 집계하고, 가운데 검색 결과는 각 Record의 current revision을 표시하며,
오른쪽 datasheet는 Layout에 고정된 typed Attribute를 편집한다.


DP600의 Young's modulus를 210 GPa에서 205 GPa로 바꾸면 기존 값을 덮어쓰지 않고 revision 2를
생성한다. 아래 비교는 원본 단위 문자열과 정규화된 Pa 값을 함께 보존한 결과다.


file/curve 값과 다른 레코드 연결의 상세 식별자는 **Evidence** 또는 **Advanced**에서 확인한다.
일반 입력 화면에는 내부 식별자가 표시되지 않는다.

## Material Database와 exact Record Link 사용

1. 전역 **Materials → Browse Tree**를 연다. `/database`와 `/catalog/explorer`는 전체
   datasheet/link 관리를 위한 호환·고급 화면으로 남아 있지만 일반 탐색의 시작점이 아니다.
2. 왼쪽 **Contents Tree**에서 CAE Material Database → Engineering Materials Profile → Table →
   Folder → Record를 펼친다. Folder 하위 노드는 펼칠 때 실제 PostgreSQL에서 지연 로딩된다.
3. 이름·external key·설명·text Attribute로 검색하거나 **Saved Subsets**의 revisioned 검색 조건을
   적용한다. 검색 결과는 exact current Record revision이며 선택하면 같은 가운데 workspace가 열린다.
4. Record를 선택하면 가운데 **Workflow Tree**가 Material → State → Test Data → Processing →
   Material Model IR → Neutral Material → Solver Card 경로를 계층으로 표시한다. 주소에는
   `/database/records/{record_id}/revisions/{revision_id}`가 남는다.
5. Workflow 노드를 누르면 대상 exact governed revision의 workbench로 이동한다. 브라우저에서
   돌아오면 기존 Contents Tree 문맥을 이어 탐색할 수 있다. 오른쪽 **Related Data**는 현재 선택한
   exact revision에 직접 연결된 관계만 표시한다.
6. 새 링크는 오른쪽에서 Link Type과 대상 Record의 현재 exact revision을 확인한 후 만든다.
   endpoint를 전진시키려면 기존 링크를 덮어쓰지 않고 같은 stable Link의 새 revision을 만든다.
7. **Deactivate**는 링크를 삭제하거나 덮어쓰지 않고 `active=false`인 새 Record Link revision을
   추가한다.


8. **Datasheet** 탭을 열면 관리자가 정의한 Layout section과 순서로 typed Attribute가 표시된다.
   number 값은 원본 값/단위와 normalized 값/단위, quantity semantics를 함께 표시한다. 여러 Layout이
   있으면 우측 Layout 선택기로 datasheet 구성을 바꾼다.
9. 상단 검색에서 Table과 검색어를 선택한다. 오른쪽에서 discrete facet 또는 normalized numeric
   range를 적용할 수 있다. 두 결과의 **Compare**를 체크한 뒤 **Compare 2**를 누르면 선택한 Layout
   순서로 exact current Record revision을 나란히 비교한다.
10. **Curves**에서 현재 Record revision의 곡선을 선택하면 같은 화면의 큰 그래프에서 채널 이름,
    축 역할, 원본/정규화·표시 단위와 기록된 통계 band 의미를 확인할 수 있다. **Evidence**는 exact
    Record/Artifact revision과 digest, source와 calculation chain을 펼쳐 보여 준다. 정확히 연결된
    Test Data 곡선만 **Open in Modeling**으로 전달된다. 통계 envelope와 provenance가 없는 legacy
    곡선은 view-only이며 Fit 입력으로 추정하지 않는다.






## 시험 curve를 그래프 중심 Workbench에서 처리

1. 전역 **Modeling**을 선택한다. 상단의 `Data | Process | Fit | Export`가 일반 작업 경로다.
2. Data에서 Canonical JSON, CSV 또는 XLSX를 선택하고 **Test Data revision**과 channel/unit
   Mapping Profile을 확인한다. Materials에서 연 exact Test Data도 같은 channel definition SHA와
   표시 adapter를 사용한다. 원시 JSON은 Advanced mapping definition에서만 연다.
3. Process에서 왼쪽 `Curves`의 실제 test method 그룹과 specimen/revision 행, `Process`의 일반 문자열
   행을 선택한다. 각 curve 행의 원형 색 키는 그래프 선을 구분할 뿐이며, inclusion checkbox와 눈 아이콘은
   각각 계산 포함 여부와 브라우저 로컬 plot visibility를 독립적으로 바꾼다. `Add method`로 ordered
   step을 추가하고 current-step settings ribbon에서 crop/smoothing/resample/statistics option을
   바꾼다. 1366 px에서는 `Show settings`로 ribbon을 연다.
4. **Preview changes**를 누른다. 오른쪽에 별도 inspector 열을 만들지 않고, 같은 큰 graph가 실제
   서버 계산 raw/mapped/processed stage를 유지한다. 그래프 tooltip은 pointer와 Arrow key로 같은
   point를 탐색하며 축 label/unit, 값, 기록된 band method·coverage와 pointwise `n`을 표시한다.
5. Fit에서 candidate response, residual, tangent와 extrapolation을 비교한다. 현재 curve/step과
   settings는 같은 surface에 연결된다.
6. Recipe와 Batch는 ribbon의 **Advanced · Recipe and Batch**, ordered JSON은 **Advanced Recipe
   JSON**에서 확인한다. 원본과 released artifact는 수정되지 않는다.
7. Export에서 reviewed Processing Output/Material Model IR, Neutral Material, mapping 상태와 native
   card preview/download를 실행한다.


### 재료군별 Modeling track 사용

상단에서 **Metal**, **Polymer**, **Elastomer** 중 하나를 선택한다. 재료군을 바꾸면 이전 재료군의
Test Data 선택은 해제되므로, 새 quantity 계약에 맞는 exact revision을 다시 선택해야 한다. 이렇게
해야 금속 인장 curve가 폴리머 relaxation 또는 엘라스토머 다중 시험 입력으로 조용히 재사용되지 않는다.


- **Metal · Elastoplastic:** E/proof/necking, true-plastic 변환, Voce/Swift/
  Hockett--Sherby/Ghosh 후보와 제한 외삽을 처리한다.
- **Polymer · Viscoelastic:** time/modulus 매핑, log-time resampling, Prony 후보를 처리하고 exact
  Processing Output에서 generalized-Maxwell IR과 Neutral/Card 단계로 이동한다.
- **Elastomer · Hyper-viscoelastic:** 공통 Test JSON 처리가 선택 사항이며, 아래 family panel에서
  uniaxial/planar/biaxial governed Dataset과 holdout, saved Calibration Plan을 선택한다.

그래프 위의 **Current-step settings** ribbon에서 method option을 바꾼다. **Advanced · Recipe and
Batch**를 펼치면 Recipe revision을 저장·게시하거나 exact Dataset batch를 preflight·실행·재시도할 수 있다.
각 track 아래의 Material context는 해당 분류의 Material, State, Property revision을 실제 API에서
불러오며 **Open full datasheet**로 원본 Material record에 돌아간다.


엘라스토머 데모는 저장된 exact Plan revision을 불러와 단축·평면·이축 calibration curve와 holdout을
함께 실행한다. 실행 후 네 model family, 여덟 multistart candidate, fitted/residual plot, rank와
uncertainty를 비교한 뒤에만 Candidate 선택 또는 Neutral 승격으로 진행한다.


### Interim reviewed-delivery controls

> 이 절은 Export 안에 보존된 T-81 engine-connected delivery contract를 설명한다. 외형은
> Data/Process/Fit/Export shell로 바뀌었지만 exact Neutral/card 계약은 변경하지 않았다.

After a metal, polymer or elastomer result is promoted, the same **Final step · reviewed delivery**
panel appears inside Material Modeling. Do not create a second Neutral revision when the panel says
`Exact Neutral JSON rN restored`; the exact immutable result has already been found for the selected
Material and Processing/Candidate evidence.

1. Check **Evidence reviewed** for the selected model family, selection reason, exact model or
   Processing Output revision, input revision count, preserved curve stages and applicability.
2. Select **Download exact Neutral JSON** when the solver-neutral exchange document is required.
3. Choose Abaqus or OpenRadioss and select **Run mapping preflight**.
4. Read every `exact`, `transformed`, `approximated`, `ignored`, `unsupported` and
   `not_applicable` row. The card remains blocked when the report is not exportable.
5. When an approximation or ignored field exists, check the explicit review acknowledgement.
6. Select **Create solver card**, inspect the native ASCII preview, then download the card and
   mapping report. **Add exact files to a bulk package** opens the package builder with the same
   Material context; **Return to Material datasheet** returns without copying an ID.


### Open a governed object from the Workflow Explorer

An administrator or catalog editor can bind the selected configurable Record revision to one exact
governed domain revision. In **Domain revision binding**, choose the object type and paste the stable
object UUID plus its exact revision UUID. The server rejects a missing, cross-project, differently
classified, or already-bound target. A binding cannot be edited or deleted; create a new Record
revision when the catalog representation must point at a newer governed revision.

After binding, the node shows the domain type and shortened exact revision. Selecting that node opens
the existing Materials, Tests, Datasets, Models, Exports, or Governance workbench while retaining the
exact object and revision in the URL. Unbound nodes continue to open their configurable datasheet.


### Return to the Workflow Explorer from governed data

Material, imported Test Data JSON, committed Processing Output and Neutral/Card screens show an
**Exact linked data** panel when that exact revision has a configurable Catalog binding. Select
**Open Workflow Explorer** to return to the bound Record revision. The center graph loads five hops,
so the clean metal journey shows Material, State, Test JSON, Processing Output, Material Model IR,
Neutral JSON and both native cards together. Selecting another node opens its pinned domain workbench.

The **Forward and reverse links** list is intentionally narrower than the graph: it shows only edges
directly incident to the currently selected Record revision. This prevents a downstream edge from
being presented as though it directly connected to the selected Test or Material.


## 목표 따라하기

1. Catalog Explorer 또는 검색에서 Material record를 찾는다.
2. 관련 Test/Specimen/Dataset revision link를 열거나 Test Data JSON/CSV를 등록한다.
3. channel과 자유 Attribute를 calculation quantity에 연결하고 Mapping Profile을 저장한다.
4. Processing Workbench에서 crop, smoothing, resampling, 통계와 family-specific method를 구성한다.
5. 설정을 Processing Recipe revision으로 저장하고 다른 Dataset 또는 선택 집합에 batch 실행한다.
6. processed/fitted/extrapolated curve와 residual/candidate를 비교한다.
7. 선택 결과를 Neutral Material JSON/IR revision으로 승격한다.
8. Abaqus 또는 OpenRadioss mapping report를 확인한다.
9. native card를 preview/download하거나 관련 JSON과 함께 Bundle을 내려받는다.

## 데이터 형식

- 시험 교환: `cmp.test-data` JSON; CSV/TSV/XLSX는 같은 구조로 변환
- 처리 설정: Mapping Profile JSON과 Processing Recipe JSON
- 중립 모델 교환: `cmp.neutral-material` JSON
- 대용량/복수 전달: deterministic JSON+ZIP와 `checksums.sha256`
- solver output: `.inp`, `.rad` 등 native ASCII

## 현재 사용 가능 여부

정확한 상태와 다음 Task는 [제품 capability map](../00-research/product-capability-map.md)을
따른다. GUI 변경 PR은 이 문서와 `screenshot-manifest.yaml`을 함께 갱신해야 한다.
