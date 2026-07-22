# UX Acceptance Criteria

Acceptance record (`2026-07-21`): the product owner approved the T-94 responsive comparison and the
live T-95–T-97 implementation passes the same structural hard gates. Exact browser dimensions,
95–99/100 live scores, scenarios A–D including canonical JSON/CSV/XLSX, native downloads and full
regression results are in `docs/17-evidence/reports/t97-reference-similarity-final.md`.

## 1. 판정 원칙

- API 호출 성공만으로 UX 완료라고 판정하지 않는다.
- screenshot 존재만으로 UX 완료라고 판정하지 않는다.
- clean demo에서 실제 사용자 task가 완료되어야 한다.
- normal user path와 Advanced/Admin path를 별도로 검증한다.
- 기존 domain invariant와 solver mapping block은 유지한다.

## 2. Scenario A — Known Material Search and Download

### Given

- clean demo가 실행 중이다.
- DP780 Material과 Abaqus/OpenRadioss card가 존재한다.
- 사용자는 Materials 홈에 있다.

### When

1. `DP780`을 검색한다.
2. 결과 행을 선택한다.
3. OpenRadioss card를 미리 본다.
4. card를 다운로드한다.

### Then

- 검색 결과에 material family, grade, key properties와 solver availability가 보인다.
- 사용자는 UUID, SHA와 revision ID를 입력하거나 복사하지 않는다.
- primary action 3회 이하로 download에 도달한다.
- 신규 사용자 기준 60초 이내 완료 가능하다.
- 다운로드 파일은 기존 exporter domain contract를 만족한다.
- approximated/unsupported 상태는 숨겨지지 않는다.

## 3. Scenario B — Browse and Filter

### Given

사용자는 정확한 material name을 모른다.

### When

1. material family를 Metal로 선택한다.
2. OpenRadioss 지원 필터를 적용한다.
3. yield strength 범위를 적용한다.
4. 결과를 정렬한다.

### Then

- filter가 left panel 또는 compact filter bar에 일관되게 위치한다.
- 결과 table에서 선택한 조건이 명확히 표시된다.
- filter reset이 한 번의 action으로 가능하다.
- result count가 즉시 갱신된다.
- empty state가 다음 행동을 설명한다.

## 4. Scenario C — Material Detail

### When

사용자가 material detail을 연다.

### Then

- 첫 viewport에서 name, grade, maker/source, status, key properties와 card availability를 확인한다.
- tab은 최대 5개다.
- CAE Card download가 식별 가능한 위치에 있다.
- curve는 축, 단위와 legend를 가진다.
- Evidence를 열기 전에는 hash, full revision ID와 mapping JSON이 보이지 않는다.
- Evidence에서는 기존 provenance와 revision 정보를 잃지 않는다.

## 5. Scenario D — No Existing Card

### Given

선택한 material에 target solver card가 없다.

### Then

사용자는 다음 중 가능한 action을 구분할 수 있다.

- existing neutral model로 card 생성
- test data로 새 model 생성
- unsupported로 인해 생성 불가

silent fallback 또는 의미 없는 빈 download button을 제공하지 않는다.

## 6. Scenario E — Upload to Card

### Given

사용자는 canonical Test Data JSON, CSV 또는 XLSX 인장시험 데이터를 가지고 있다.

### When

1. JSON, CSV 또는 XLSX 파일을 업로드한다.
2. JSON schema 또는 자동 탐지된 worksheet, 열, quantity semantics와 단위를 검토한다.
3. Process에서 crop/smoothing/replicate selection을 확인한다.
4. Fit에서 candidate와 residual을 비교한다.
5. Export에서 solver card를 생성한다.

### Then

- top-level 단계는 Data/Process/Fit/Export 4개다.
- canonical JSON은 기존 channel, quantity semantics, 원본/정규화 단위를 손실 없이 복원한다.
- CSV/XLSX는 worksheet, 열, channel과 unit mapping을 명시적으로 확인한다.
- JSON editor를 직접 작성하지 않고도 완료 가능하며, 고급 사용자는 원본 JSON을 Evidence에서 확인한다.
- invalid schema, unit, worksheet 또는 column은 필드 수준 오류를 표시하고 silent fallback하지 않는다.
- classification/change reason은 normal path에서 필수가 아니다.
- graph는 Process와 Fit에서 지속적으로 보인다.
- raw curve와 processed/fitted/extrapolated curve를 구분한다.
- 생성 결과는 Material Library에서 검색 가능하다.
- 기존 revision/provenance는 내부적으로 저장된다.

### Required exported evidence

- normalized Test Data JSON
- Processing Output JSON
- Material Model IR JSON
- Neutral Material JSON
- solver mapping report JSON
- native `.inp`/`.rad`, manifest and checksum

## 7. Scenario F — Advanced Engineering Work

### When

고급 사용자가 Advanced를 연다.

### Then

다음 기능에 접근할 수 있다.

- Mapping Profile
- Recipe Library
- Batch Monitor
- exact revision
- JSON definition
- detailed mapping report

Advanced를 닫으면 normal task UI가 다시 단순해진다.

## 8. Visual Acceptance

### Reference-layout similarity gate

각 reference와 target 화면은 navigation, search/control band, explorer/filter, result/datasheet,
context, curve tree, settings, graph, primary action, advanced disclosure의 normalized rectangle로
표시한다. 실제 앱은 브라우저 DOM bounds를 같은 형식으로 기록한다.

| Criterion | Points | Required result |
| --- | ---: | --- |
| Region topology | 25 | reference-derived order and adjacency; hard gate |
| Dominant area and proportion | 25 | same work region dominates; no more than 12 percentage-point area deviation |
| Density and typography | 15 | title/body ratio ≤ 1.5; tree/table rows and font sizes within contract |
| Surface/divider grammar | 15 | nested cards 0; persistent pane shadows 0; hard gate |
| Selection/task continuity | 10 | selected Material/curve visibly owns detail/graph |
| Primary action/disclosure | 10 | one task primary; internal detail does not compete |

Every target screen must score at least 85/100. Materials fails if Tree is merely a link, results are
not wider than context, or headings/forms dominate data. Modeling fails if a permanent third column
exists, graph width is below 70%, three boxed bars precede the graph, curve names are oversized or
truncated, or key settings exist only under Advanced. CAE Card fails if multiple primary actions
compete with Download or internal identifiers appear in the normal viewport.

Approval evidence contains reference, rejected current screen, proposal, and annotated region mask.
An explicit product-owner approval is required; automated score alone cannot approve the design.

### Large-hierarchy navigation gate

- Materials Browse는 Database/Profile/Table/Folder/Record type을 한 줄 26 px 행, node glyph,
  indentation과 selection marker로 구분한다.
- Tree 전용 검색은 record 이름/grade뿐 아니라 Database, Profile, Table과 Folder 이름을 찾고,
  일치 node의 ancestor path를 유지한다. 전역 Material 검색으로 이를 대체하지 않는다.
- synthetic hierarchy 10,000 records에서 expanded visible rows는 virtualized되고 DOM treeitem은
  viewport overscan을 포함해 150개 이하를 유지한다. 검색 응답 후 첫 match와 path는 1초 안에
  keyboard focus를 받을 수 있어야 한다.
- Tree scroll은 검색, Browse/Filters/Subsets mode와 독립이다. 깊은 node를 스크롤해도 `Find in tree`
  control은 사라지지 않는다.
- Modeling curve/process navigator는 Materials와 같은 26 px row, 12–13 px normal text, selection
  background/leading marker를 사용한다. full source ID, revision과 unit metadata를 각 row 아래에
  반복하면 실패한다.

### 기본 화면

- 1440×900에서 major region 3개 이하
- 첫 viewport에 현재 task의 main content와 primary action 표시
- 중첩 card가 0개
- decorative badge가 데이터보다 눈에 띄지 않음
- primary color 1개
- background/surface hierarchy가 명확함
- 한 화면에 불필요한 gradient 없음
- Materials result/datasheet 또는 Modeling graph가 가장 큰 region
- 1440px Modeling graph SVG가 최소 1,050px이자 workspace의 72% 이상
- 1440px Materials results가 optional context가 열린 상태에서도 최소 820px

### Typography

- body 14px 이상
- primary data 16px 이상
- metadata 12px 이상
- line-height 1.4 이상
- uppercase eyebrow 남용 금지
- 전문 용어는 tooltip 또는 Evidence에서 설명

### Interaction

- 독립 button/input click target은 32×32px를 목표로 한다. Tree/table의 dense row는 24px WCAG
  minimum과 keyboard equivalent를 충족하며 전체 행이 하나의 target이어야 한다.
- visible focus
- keyboard table navigation
- Escape로 drawer/modal 닫기
- loading 중 이전 context 유지
- error는 원인과 recovery action 제공

## 9. Regression Gate

다음은 유지되어야 한다.

- immutable raw/released artifact
- original/normalized unit
- exact input revision pin
- solver mapping exact/transformed/approximated/unsupported
- unsupported generation block
- explicit approximation acknowledgement
- card native ASCII preview/download
- three existing reference material families
- PostgreSQL clean seed/demo verification

## 10. Completion Definition

UX redesign은 다음이 모두 충족될 때 완료다.

- Search-to-download task accepted
- Upload-to-card task accepted
- baseline 대비 click/time/internal-term count 개선 기록
- current and target screenshots available
- frontend tests and build pass
- backend regression pass
- clean PostgreSQL demo pass
- keyboard/accessibility checks pass
- legacy UI와 dead CSS 제거
- README/user guide/AGENTS/product docs가 새 방향과 일치
- reference similarity screen score가 모두 85점 이상이고 hard-gate 위반이 없음
- product-owner가 side-by-side prototype과 live implementation을 승인
