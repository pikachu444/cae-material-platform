# Configurable Catalog와 Material Modeling 사용자 흐름

이 문서는 T-49~T-60의 통합 사용자 흐름을 추적한다. T-49/T-50의 관리형 schema designer,
typed Record datasheet/search/compare와 기존 fixed-schema reference modeling 흐름은 실제 실행할 수 있다. 이후 단계는 각
Task 구현 시 실제 UI, 입력 fixture와 스크린샷으로 교체하며 미구현 기능을 완료로 표시하지 않는다.

## 지금 사용할 수 있는 Catalog schema designer

1. 상단 **Catalog** 또는 `/catalog/schema`를 연다.
2. Table stable key와 표시명을 입력하고 **Create Table revision 1**을 선택한다.
3. 선택한 Table에 typed Attribute를 추가한다. 수치 Attribute는 quantity semantics와 normalized
   unit을 함께 입력하고, Record reference는 대상 Table을 고정한다.
4. **Create datasheet Layout**으로 현재 Attribute revision 순서를 저장한다.
5. **Create All records Subset**으로 record 검색의 시작 Subset을 만든다.

Table/Attribute/Layout/Subset은 stable identity와 immutable revision으로 저장되며 API 수정은
current ETag를 요구한다.

![실제 Docker/PostgreSQL에 연결된 Catalog schema designer](../15-demo/images/t49-configurable-catalog.png)

## Catalog Record 등록·검색·비교

1. 상단 **Catalog** 또는 `/catalog/records`를 열고 Table과 datasheet Layout을 선택한다.
2. 필요하면 왼쪽 **New Folder**에서 root 또는 parent Folder를 만든다. cycle은 거부된다.
3. **New record**를 누르고 이름, 외부 key, Folder와 Layout 순서의 Attribute 값을 입력한다.
4. 수치값은 원본 값·원본 단위 문자열·정규화 값이 모두 보이도록 입력한다. normalized unit과
   quantity semantics는 Attribute revision에서 가져오며 숨겨서 바꾸지 않는다.
5. **Create Record revision 1**을 선택한다. 수정할 때는 검색 결과를 열고 **Save new immutable
   revision**을 선택한다. 기존 revision은 덮어쓰지 않는다.
6. 이름·설명·text Attribute, Folder, discrete facet 또는 normalized 수치 범위로 검색한다.
7. 현재 검색을 이름과 함께 Subset revision으로 저장하고, 저장된 chip으로 다시 적용한다.
8. 두 revision 이상인 Record를 열면 revision 1과 current 사이의 Attribute 차이를 확인한다.

아래 화면은 실제 Docker API와 PostgreSQL에 저장한 DP600 및 AA6061-T6 Record를 조회한 결과다.
왼쪽 facet은 재료군별 건수를 집계하고, 가운데 검색 결과는 각 Record의 current revision을 표시하며,
오른쪽 datasheet는 Layout에 고정된 typed Attribute를 편집한다.

![Catalog Record 검색, facet 및 Layout 기반 datasheet](../15-demo/images/t50-configurable-catalog-records.png)

DP600의 Young's modulus를 210 GPa에서 205 GPa로 바꾸면 기존 값을 덮어쓰지 않고 revision 2를
생성한다. 아래 비교는 원본 단위 문자열과 정규화된 Pa 값을 함께 보존한 결과다.

![DP600 exact revision 비교](../15-demo/images/t50-configurable-catalog-revision-compare.png)

file/curve 값은 이미 업로드된 Artifact UUID와 SHA-256을, record-reference 값은 대상 Record와
정확한 revision UUID를 함께 입력한다. 사용자 친화적 Artifact picker와 link editor는 T-51에서
Explorer와 함께 확장한다.

## Material Database와 exact Record Link 사용

1. 전역 **Material Database** 또는 `/database`를 연다. `/catalog/explorer`는 기존 관리·호환
   화면으로 남아 있지만 일반 탐색의 시작점이 아니다.
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

![Database/Profile/Table/Folder/Record Contents Tree와 exact Workflow Tree](../15-demo/images/t76-material-database-tree.png)

8. **Datasheet** 탭을 열면 관리자가 정의한 Layout section과 순서로 typed Attribute가 표시된다.
   number 값은 원본 값/단위와 normalized 값/단위, quantity semantics를 함께 표시한다. 여러 Layout이
   있으면 우측 Layout 선택기로 datasheet 구성을 바꾼다.
9. 상단 검색에서 Table과 검색어를 선택한다. 오른쪽에서 discrete facet 또는 normalized numeric
   range를 적용할 수 있다. 두 결과의 **Compare**를 체크한 뒤 **Compare 2**를 누르면 선택한 Layout
   순서로 exact current Record revision을 나란히 비교한다.
10. **Curves**는 현재 Record revision의 curve Artifact provenance를 표시한다. 실제 raw/normalized/
    processed curve overlay와 처리 option preview는 linked Test Data를 연 뒤 Material Modeling
    workspace에서 수행한다.

![Layout section, 원본/정규화 단위와 exact revision을 보존한 DP780 Datasheet](../15-demo/images/t77-material-datasheet.png)

![DP780 검색 결과의 facet과 Layout 기반 두 Record 비교](../15-demo/images/t77-material-search-compare.png)

![Explorer 검색 결과에서 exact Material revision과 전체 Workflow graph 열기](../15-demo/images/t71-explorer-search-workflow.png)

![Catalog tree와 Material workflow exact link](../15-demo/images/t51-catalog-workflow-explorer.png)

![시험 Record에서 Material revision으로 이동하는 역방향 링크](../15-demo/images/t51-reverse-record-link.png)

## 시험 curve를 그래프 중심 Workbench에서 처리

1. 전역 **Material Modeling**을 선택한다. 상단의 Import → Map → Prepare → Fit → Extrapolate →
   Card 순서가 현재 작업의 전체 경로다.
2. **Test Data revision**에서 등록된 문서를 고르고 **Load exact JSON**을 누른다. 왼쪽
   **Datasets & curves**에서도 같은 exact revision을 다시 선택할 수 있다.
3. 저장된 **Mapping Profile** 또는 Metal/Polymer template을 선택한다. 일반 사용자는 channel
   mapping을 확인하고, 원시 JSON이 필요한 경우에만 **Advanced mapping definition**을 펼친다.
4. 저장된 게시 Recipe를 불러오거나 상단 method를 눌러 ordered step을 추가한다. 왼쪽에서 단계를
   선택하면 오른쪽에 해당 method의 option이 표시된다. option 변경은 원본을 수정하지 않는다.
5. **Preview changes**를 누른다. 가운데 그래프는 실제 서버 계산 raw/mapped/processed/fitted/
   extrapolated stage를 표시한다. 하단 stage chip을 선택해 입력과 각 단계 결과를 비교한다.
6. 후보 진단은 그래프 아래에 보이고 전체 parameter/bound/수치 증거는 **Parameters and numerical
   evidence**를 펼쳐 확인한다. 미리보기는 저장되지 않으며 **Commit immutable output**만 새
   Processing Output revision을 만든다.

![Exact Dataset, ordered Recipe, server curve와 단계 옵션이 연결된 Material Modeling workspace](../15-demo/images/t79-material-modeling-workspace.png)

### 재료군별 Modeling track 사용

상단에서 **Metal**, **Polymer**, **Elastomer** 중 하나를 선택한다. 재료군을 바꾸면 이전 재료군의
Test Data 선택은 해제되므로, 새 quantity 계약에 맞는 exact revision을 다시 선택해야 한다. 이렇게
해야 금속 인장 curve가 폴리머 relaxation 또는 엘라스토머 다중 시험 입력으로 조용히 재사용되지 않는다.

![하나의 Modeling 흐름에서 선택하는 금속·폴리머·엘라스토머 track](../15-demo/images/t80-material-family-tracks.png)

- **Metal · Elastoplastic:** E/proof/necking, true-plastic 변환, Voce/Swift/
  Hockett--Sherby/Ghosh 후보와 제한 외삽을 처리한다.
- **Polymer · Viscoelastic:** time/modulus 매핑, log-time resampling, Prony 후보를 처리하고 exact
  Processing Output에서 generalized-Maxwell IR과 Neutral/Card 단계로 이동한다.
- **Elastomer · Hyper-viscoelastic:** 공통 Test JSON 처리가 선택 사항이며, 아래 family panel에서
  uniaxial/planar/biaxial governed Dataset과 holdout, saved Calibration Plan을 선택한다.

가운데 그래프 오른쪽의 **Step options / Recipe / Batch** 탭에서 현재 작업을 벗어나지 않고 method
option을 바꾸고 Recipe revision을 저장·게시하거나 exact Dataset batch를 preflight·실행·재시도할 수 있다.
각 track 아래의 Material context는 해당 분류의 Material, State, Property revision을 실제 API에서
불러오며 **Open full datasheet**로 원본 Material record에 돌아간다.

![공통 Workbench 안에서 실행한 polymer log-time/Prony 처리](../15-demo/images/t80-polymer-modeling-track.png)

엘라스토머 데모는 저장된 exact Plan revision을 불러와 단축·평면·이축 calibration curve와 holdout을
함께 실행한다. 실행 후 네 model family, 여덟 multistart candidate, fitted/residual plot, rank와
uncertainty를 비교한 뒤에만 Candidate 선택 또는 Neutral 승격으로 진행한다.

![exact multi-mode Plan으로 실행한 elastomer family 비교](../15-demo/images/t80-elastomer-calibration-track.png)

### Open a governed object from the Workflow Explorer

An administrator or catalog editor can bind the selected configurable Record revision to one exact
governed domain revision. In **Domain revision binding**, choose the object type and paste the stable
object UUID plus its exact revision UUID. The server rejects a missing, cross-project, differently
classified, or already-bound target. A binding cannot be edited or deleted; create a new Record
revision when the catalog representation must point at a newer governed revision.

After binding, the node shows the domain type and shortened exact revision. Selecting that node opens
the existing Materials, Tests, Datasets, Models, Exports, or Governance workbench while retaining the
exact object and revision in the URL. Unbound nodes continue to open their configurable datasheet.

![A configurable Material Record pinned to one exact governed Material revision](../15-demo/images/t62-domain-workflow-binding.png)

### Return to the Workflow Explorer from governed data

Material, imported Test Data JSON, committed Processing Output and Neutral/Card screens show an
**Exact linked data** panel when that exact revision has a configurable Catalog binding. Select
**Open Workflow Explorer** to return to the bound Record revision. The center graph loads five hops,
so the clean metal journey shows Material, State, Test JSON, Processing Output, Material Model IR,
Neutral JSON and both native cards together. Selecting another node opens its pinned domain workbench.

The **Forward and reverse links** list is intentionally narrower than the graph: it shows only edges
directly incident to the currently selected Record revision. This prevents a downstream edge from
being presented as though it directly connected to the selected Test or Material.

![Test JSON exact revision에서 전체 Material-to-card graph로 역이동](../15-demo/images/t66-reverse-workflow-navigation.png)

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
