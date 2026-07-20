# Research Evidence and Material Collection Plan

## 1. 조사 범위

UX 개편은 다음 세 종류의 근거를 함께 사용한다.

1. 현재 저장소의 실제 화면·코드·라우트
2. Ansys Granta MI, Altair/Simcenter Material Data Center, Altair/Simcenter Material Modeler의 공식 공개 workflow
3. enterprise data UI의 progressive disclosure, data table과 accessibility 원칙

## 2. 현재 저장소에서 확인된 사실

### 2.1 내부 workflow를 전면에 노출한다

현재 목표 workflow는 Catalog tree/search/link, Test Data JSON, Mapping Profile, Processing Recipe/Batch, Neutral Material JSON, solver mapping report와 native card의 긴 artifact chain으로 설명된다. 이 흐름은 provenance에는 적합하지만 일반 사용자 task model로는 과도하다.

### 2.2 전역 메뉴가 사용자 목적보다 모듈을 나열한다

현재 상단 메뉴는 Dashboard, Material Database, Material Modeling, Jobs & Reviews, Administration이다. 재료를 찾고 card를 내려받는 사용자가 내부 제품 영역을 먼저 학습해야 한다.

### 2.3 Modeling 화면이 과도한 동시 정보를 가진다

`apps/web/src/common-processing-workbench.tsx`는 다음을 한 화면에 배치한다.

- Import / Map / Prepare / Fit / Extrapolate / Card
- Metal / Polymer / Elastomer
- Test Data와 Mapping Profile
- Dataset/curve rail와 Recipe steps
- persistent graph
- Step Options / Recipe / Batch inspector
- Reviewed Outputs와 Replicate Statistics

사용자가 현재 어디에 집중해야 하는지 분명하지 않다.

### 2.4 파일 업로드 경로가 일반 사용자 기준이 아니다

`apps/web/src/canonical-test-data-workbench.tsx`는 `Test Data JSON`, metadata/mapping JSON, classification, change reason, immutable revision과 SHA-256을 주요 작업으로 표시한다. 일반 사용자의 사고 방식은 `파일 → 열과 단위 → 그래프`다.

### 2.5 스타일이 누적 패치 형태다

`apps/web/src/styles.css`에는 수천 줄의 단일 CSS, 여러 surface/radius/gradient/shadow/chip/badge, 0.58rem~0.8rem 수준의 작은 글자와 feature별 panel 스타일이 누적되어 있다. 디자인 시스템보다 기능별 장식 패치가 우선된 상태다.

### 2.6 문서 기준도 제품 복잡성을 강화한다

제품 문서는 검색과 CAE 활용을 핵심 가치로 두지만 Contents Tree와 6단계 Modeling flow를 필수 제품 형태로 고정한다. `AGENTS.md`는 데이터 무결성 규칙은 강하게 규정하지만 검색 우선순위, progressive disclosure와 기본 화면에서 숨겨야 할 내부 용어는 규정하지 않는다.

## 3. 공식 참고 제품에서 확인된 원칙

### 3.1 Ansys Granta MI

공식 도움말에서 확인되는 기본 사용자 흐름:

- hierarchy browse
- material name 또는 engineering property search
- 주요 property를 비교하는 결과 list
- record datasheet
- selected record의 material card export

적용할 원칙:

- 검색 결과가 데이터 목록의 중심이다.
- hierarchy는 검색의 대체 수단이다.
- datasheet가 상세 정보를 한 곳에 모은다.
- card export는 selected material의 action이다.
- 세부 tabular data는 필요할 때만 펼친다.

### 3.2 Altair/Simcenter Material Data Center

공식 공개 기능:

- quick/advanced search
- left filter navigation
- table/tile result
- material compare
- details/property/plot
- solver-ready card export

적용할 원칙:

- 검색, 필터와 결과가 안정된 shell을 이룬다.
- solver 호환 여부가 검색과 상세에 연결된다.
- 상세 record 안에서 CAE Model을 선택하고 download한다.
- 사용자의 기본 task는 적합한 material을 찾고 활용하는 것이다.

### 3.3 Altair/Simcenter Material Modeler

공식 도움말에서 확인되는 흐름:

- local file 또는 Material Data Center에서 raw data import
- curve preparation
- fitting/extrapolation
- 선택 결과 저장
- solver law/card 선택
- material card 생성

적용할 원칙:

- import source는 local file과 library 모두 가능하다.
- fitting 후보와 extrapolation을 graph에서 검토한다.
- Create Card와 Advanced를 분리한다.
- card 생성은 workflow의 마지막 명확한 결과다.

### 3.4 일반 UX 원칙

- data table은 많은 resource를 찾고 비교하는 기본 component다.
- row expansion과 detail view로 progressive disclosure를 제공한다.
- 사용 빈도가 낮은 세부 내용은 Details/Advanced로 숨긴다.
- 필수 정보는 숨기지 않는다.
- interaction target, contrast와 keyboard navigation은 기본 수용 기준이다.

## 4. 구현 전 반드시 수집할 자료

### 4.1 Current UI capture set

현행 demo data를 사용해 다음 화면을 1440×900과 1366×768로 캡처한다.

- Dashboard
- Material Database search/result와 detail
- Metal / Polymer / Elastomer Modeling
- Test Data import
- CAE card preview/download
- Recipe/Batch inspector
- Administration

각 캡처에 route, viewport, selected material/task, visible primary actions, full-page scroll height와 first viewport의 panel/button/heading 수를 기록한다.

### 4.2 Route and component inventory

다음 열을 가진 문서를 작성한다.

```text
Route
User job
Primary action
Secondary actions
Internal concepts exposed
Main component
API calls
Keep / merge / hide / remove
Replacement route
```

### 4.3 Terminology inventory

UI 문자열을 user-facing domain, advanced engineering, governance/audit, internal implementation과 obsolete task label로 분류한다.

우선 숨길 용어:

```text
exact revision
immutable
aggregate
mapping profile
content hash
preflight
classification
change reason
lifecycle
canonical exchange
```

### 4.4 Design token audit

`styles.css`에서 color, font size, spacing, radius, shadow, gradient, status chip, button와 panel/card variant를 추출하고 중복을 계산한다.

### 4.5 Reference screen gallery

공식 자료에서 다음 interaction을 수집한다.

- Granta MI search/filter/list, datasheet와 card export
- Material Data Center filter/result, detail와 CAE Model download
- Material Modeler import/prepare, fitting/extrapolation과 Create Card

각 이미지에는 `관찰한 원칙`, `우리 제품에 적용할 부분`, `복제하지 않을 부분`을 기록한다.

### 4.6 Baseline task measurements

현행 UI에서 다음 작업을 직접 수행한다.

1. DP780을 찾아 Abaqus/OpenRadioss card 내려받기
2. solver 호환 재료만 필터링하기
3. 시험 곡선 확인하기
4. CSV/XLSX 인장시험 업로드 후 fitting 화면 열기
5. 처리 결과에서 card 생성하기

완료 여부, 시간, 클릭 수, route 전환, 내부 용어 수, 막힌 지점과 다음 행동 식별 여부를 기록한다.

## 5. 조사 산출물

```text
docs/01-product/ux-redesign-goal.md
docs/01-product/ux-information-architecture.md
docs/01-product/ux-visual-system.md
docs/00-research/ux-reference-analysis.md
docs/15-demo/evidence/ux-current-baseline.md
docs/15-demo/evidence/ux-target-acceptance.md
adr/0035-search-first-product-surface.md
```

## 6. 사실·가정·미결정 사항

### 확인된 사실

- 검색·상세·card download가 최우선 사용자 가치다.
- 시험 데이터 기반 card 생성은 두 번째 핵심 경로다.
- 현재 backend와 calculation/export engine은 보존할 가치가 있다.
- 현재 UI는 내부 artifact와 관리 기능을 과도하게 노출한다.

### 설계 가정

- 일반 사용자는 revision/provenance를 필요할 때 확인하면 된다.
- Materials가 기본 홈이어야 한다.
- table/list가 card grid보다 재료 비교에 적합하다.
- administration과 governance는 역할 기반으로 숨길 수 있다.

### 미결정 사항

- 전역 메뉴 최종 명칭과 Activity 범위
- detail page와 split preview 중 기본 방식
- material family별 기본 결과 열
- card download 전에 확인해야 하는 경고 수준
- 즐겨찾기·최근 재료를 P0에 포함할지
- 한국어 UI와 영어 전문 용어 병기 정책
