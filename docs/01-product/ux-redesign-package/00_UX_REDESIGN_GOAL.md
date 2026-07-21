# UX Redesign Goal

## 1. 문제 정의

현재 서비스는 재료 검색, 데이터베이스 관리, 시험 데이터 등록, 데이터 처리, fitting, Recipe, Batch, provenance, review와 solver card 생성을 한 화면 체계에 함께 노출한다.

기능은 구현되어 있으나 일반 사용자는 다음을 빠르게 수행하기 어렵다.

- 기존 재료를 찾는다.
- 물성과 시험 조건을 검토한다.
- 사용할 solver card가 있는지 확인한다.
- card를 미리 보고 내려받는다.
- 적절한 자료가 없을 때만 새 시험 데이터 기반 모델링을 시작한다.

현재 제품은 내부 데이터 구조와 엔진 기능을 사용자 작업보다 앞에 보여 준다. 이 때문에 복잡하고 읽기 어려우며, 여러 기능 패널을 덕지덕지 붙인 개발자용 관리 화면처럼 보인다.

## 2. 확인된 사실

- 저장소에는 Material Database, search/facet/compare, Test Data, processing, fitting, Neutral Material과 Abaqus/OpenRadioss card 엔진이 존재한다.
- 현재 상단 내비게이션은 Dashboard, Material Database, Material Modeling, Jobs & Reviews, Administration으로 구성되어 있다.
- Modeling 화면은 Import, Map, Prepare, Fit, Extrapolate, Card와 재료군 선택, Dataset, Recipe, Batch, graph, step option을 동시에 노출한다.
- Test Data 화면은 일반 CSV/XLSX 업로드보다 canonical JSON, classification, change reason과 revision 정보를 전면에 둔다.
- 백엔드의 revision/provenance/solver mapping 계약은 유지할 가치가 있다.
- 사용자의 실제 우선순위는 다음과 같다.
  1. 기존 재료 검색 → 검토 → solver card 다운로드
  2. 시험 데이터 업로드 → 처리·보정 → 새 card 생성

## 3. 제품 Goal

> 사용자는 서비스에 들어오자마자 재료를 검색하고, 필요한 물성·곡선·적용 조건을 확인한 뒤, 지원되는 CAE solver card를 최소한의 조작으로 내려받을 수 있어야 한다. 적절한 재료 또는 card가 없을 때만 시험 데이터 기반 모델 생성 흐름으로 전환한다.

## 4. North Star workflow

### 4.1 기본 경로: Search and Download

```text
재료 검색
→ 검색 결과에서 재료 선택
→ 핵심 물성·곡선·적용 조건 확인
→ solver 선택
→ card 미리보기 및 다운로드
```

### 4.2 보조 경로: Create from Test Data

```text
시험 파일 업로드
→ 열·단위·시험 종류 확인
→ 데이터 처리
→ 모델 fitting 및 extrapolation 검토
→ solver card 생성
→ Material Library에 저장
```

## 5. 목표 정보 구조

일반 사용자 전역 내비게이션은 다음 수준으로 단순화한다.

```text
Materials | Modeling | Activity
```

- `Materials`: 기본 홈, 검색, 필터, 비교, 상세 보기와 card 다운로드
- `Modeling`: 시험 데이터 기반 material model/card 생성 또는 기존 재료의 누락 card 생성
- `Activity`: 최근 작업, 진행 중 import/batch와 검토 요청
- `Administration`: 일반 전역 메뉴에서 제외하고 사용자 메뉴 또는 설정으로 이동

`Jobs & Reviews`, schema administration, Recipe/Batch 관리와 revision/provenance 상세는 해당 역할 또는 고급 화면에서만 노출한다.

## 6. 핵심 화면

### 6.1 Material Search

- 페이지 진입 즉시 검색창에 초점
- 왼쪽에는 제한된 핵심 필터
- 가운데에는 비교 가능한 table/list
- 선택 시 우측 quick preview 또는 상세 페이지
- card 보유 여부와 solver를 검색 결과에서 확인
- Download 또는 Details가 명확한 primary action

기본 결과 열:

- Material name / grade
- material family
- maker / source
- key properties
- applicable condition summary
- supported solvers
- validation/release status
- updated date

### 6.2 Material Detail

기본 탭은 최대 5개로 제한한다.

```text
Overview | Properties | Curves | CAE Cards | Evidence
```

- `Overview`: 식별 정보, 적용 범위, 핵심 물성과 상태
- `Properties`: 단위가 있는 물성 표
- `Curves`: 시험·처리·fitting 곡선
- `CAE Cards`: solver별 지원 상태, 미리보기와 다운로드
- `Evidence`: 시험 원본, revision, mapping report와 provenance

일반 사용자가 거의 사용하지 않는 정보는 `Evidence`에 둔다.

### 6.3 Modeling

단계를 6개에서 4개로 줄인다.

```text
Data | Process | Fit | Export
```

- `Data`: upload/import, 시험 종류, channel/unit mapping
- `Process`: crop, smoothing, resample과 replicate statistics
- `Fit`: model candidate, residual과 extrapolation
- `Export`: Neutral model summary, solver mapping과 card preview/download

Recipe, Batch, exact revision, hash와 JSON editor는 기본 화면이 아니라 `Advanced` 또는 `Evidence`로 이동한다.

## 7. 정량 수용 목표

### 7.1 Search and Download

알고 있는 재료명을 사용하는 경우:

- 홈 진입 후 검색 결과까지 1회 검색
- 결과 선택 후 card 다운로드까지 primary action 3회 이하
- card 존재 여부를 상세 페이지 진입 전 확인 가능
- 내부 UUID, SHA와 revision ID를 보지 않고 완료 가능

데모 기준:

```text
DP780 검색 → 재료 선택 → Abaqus 또는 OpenRadioss card 다운로드
```

위 작업을 신규 사용자 기준 60초 이내에 완료한다.

### 7.2 Modeling

- 일반 사용자에게 보이는 top-level 단계는 4개 이하
- 파일 업로드 후 channel/unit mapping 초안을 자동 생성
- mapping 확신도가 낮은 항목만 확인 요청
- Process와 Fit에서 graph가 항상 유지
- card 생성 완료 후 Material Library record로 자연스럽게 이동

### 7.3 시각적 품질

- 1440×900 첫 화면에서 현재 작업의 핵심 영역이 모두 보인다.
- 한 viewport의 major region은 최대 3개다.
- 한 영역의 primary button은 원칙적으로 1개다.
- body text는 14px 이상, 주요 값은 16px 이상을 기본으로 한다.
- 보조 텍스트도 12px 미만을 사용하지 않는다.
- 일반 클릭 target은 최소 32×32px을 목표로 한다.
- WCAG 2.2 AA 대비를 만족한다.
- gradient, 과도한 shadow와 card 안의 card 중첩을 기본 스타일로 사용하지 않는다.
- 상태 표현은 색상만으로 구분하지 않는다.
- 한 제품 shell 안에서 typography, spacing, border와 radius를 token으로 통일한다.
- Materials는 실제 Tree/filter와 dominant results/datasheet가 divider로 연결된 연속 surface다.
- Modeling은 permanent 3열이 아니라 compact curve/process tree와 settings ribbon을 사용하고,
  1440px에서 graph가 workspace 폭의 72% 이상을 차지한다.
- reference 유사성은 영역 topology, 면적 비율, 밀도, surface 문법과 작업 연속성으로
  측정한다. 색상·브랜드·pixel 유사도는 측정하지 않는다.

### 7.4 복잡성 감소

기본 검색·상세·다운로드 경로에서 다음 용어를 제거한다.

- exact revision
- immutable output
- mapping profile
- recipe lifecycle
- compatibility preflight
- content hash
- classification
- change reason

데이터 계약은 유지하되 일반 사용자의 기본 경로에서 숨긴다.

## 8. 비목표

- 백엔드 domain model과 provenance engine을 다시 설계하지 않는다.
- 경쟁 제품 화면을 pixel 단위로 복제하지 않는다.
- 상용 reference material library를 복제하거나 배포하지 않는다.
- 이번 UX 개편에서 새로운 constitutive model, solver 또는 fitting algorithm을 추가하지 않는다.
- 기능 수를 늘리는 것을 완료 기준으로 삼지 않는다.
- CSS theme 변경만으로 완료 처리하지 않는다.

## 9. 최종 성공 조건

다음 두 데모를 별도 설명서 없이 수행할 수 있어야 한다.

### Demo A

```text
서비스 실행
→ DP780 검색
→ 적용 조건과 응력-변형률 곡선 확인
→ OpenRadioss card 미리보기
→ .rad 다운로드
```

### Demo B

```text
Canonical Test Data JSON / CSV / XLSX 인장시험 업로드
→ schema 또는 worksheet·열·quantity semantics·단위 확인
→ 처리 결과와 반복시험 산포 확인
→ hardening 후보 비교
→ Abaqus/OpenRadioss card 생성
→ Library record에서 다시 검색
```

JSON 입력은 기존 channel과 original/normalized unit을 복원하며, CSV/XLSX 입력은 명시적
mapping을 거친다. invalid schema, unit, worksheet 또는 column은 silent fallback 없이 차단한다.
