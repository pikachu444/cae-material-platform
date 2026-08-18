# 프론트엔드 UI 원칙

상태: authoritative cross-cutting product contract
범위: 인증 후 사용하는 CAE Material Platform 데스크톱 작업공간
관련 이슈: [#249 프론트엔드 아키텍처 및 UI 체계 재정비](https://github.com/pikachu444/cae-material-platform/issues/249)

## 1. 이 문서의 역할

이 문서는 기존 제품 명세를 대체하지 않는다. 다음 문서에 이미 정의된 사용자 흐름, 화면별 필드,
상태 전이와 시각 합격 기준을 프론트엔드 전체에 공통으로 적용하기 위한 상위 원칙이다.

- [Desktop engineering 사용자 흐름](desktop-engineering-user-flows.md)
- [UI 제품·상호작용 명세](desktop-engineering-ui-product-spec.md)
- [UI 컴포넌트 명세](desktop-engineering-ui-spec.md)
- [시각 수용 매트릭스](visual-acceptance-matrix.md)

화면별 구체 계약이 이 문서보다 상세하면 화면별 계약을 따른다. 충돌이 생기면 구현자가 임의로
선택하지 않고 이슈에 차이를 기록한다.

## 2. 제품 성격

CAE Material Platform은 웹사이트나 카드형 대시보드가 아니라 **공학용 작업도구**다.

화면의 중심은 다음이어야 한다.

1. 사용자가 현재 다루는 Material, Test Data, 모델 또는 솔버 카드
2. 정확한 선택 문맥과 개정본
3. 표, 곡선, 그래프, 파라미터와 계산 결과
4. 지금 수행할 수 있는 가장 중요한 동작
5. 차단 사유와 복구 방법

장식, 소개문, 큰 빈 카드, 의미 없는 색상과 굵기는 위 항목과 경쟁하지 않는다. 기존 application
shell, `Materials | Modeling | Activity`, density 정책, 공통 token과 승인된 화면 구조는 유지한다.
이번 정비는 전면 재디자인이 아니라 기존 제품을 하나의 문법으로 정돈하는 작업이다.

내부 설계 명칭은 **Neutral Engineering Workbench**로 한다. 조용하고 중립적이며, 정보 밀도가
충분하고, 데이터와 작업 상태가 먼저 보이는 화면을 의미한다. 특정 상용 제품의 시각 요소를
그대로 복제한다는 뜻은 아니다.

### 2.1 #249 필수 설계 합성

모든 사용자 노출 프론트엔드 작업은 #249에서 승인한 다음 세 기준을 함께 적용한다.

- **Carbon 계열의 조형 완성도**: 타이포그래피, 정렬, 간격, 선택과 상태 표현을 한 위계로
  정돈한다. Carbon 컴포넌트나 외형을 복제한다는 뜻은 아니다.
- **COMSOL 계열의 공학 작업구조**: 입력, 현재 선택, 그래프·결과, 다음 유효 작업이 한 작업
  흐름으로 읽혀야 한다. 내부 데이터 형식이나 시스템 식별자를 사용자 작업 종류처럼 노출하지
  않는다.
- **SAP 계열의 반응형 논리**: shell은 전체 viewport를 사용하되, 넓어진 공간은 비교와 조작
  가치가 커지는 표·그래프·native preview에 우선 배정한다. navigator, form, 문장은 읽기 좋은
  범위를 유지한다.

세 기준은 선택 가능한 참고사항이 아니라 하나의 필수 합성 기준이다. 승인 reference는 해당
화면의 구조와 상태를 확인하는 원본이며, 불필요한 문구나 기술 메타데이터까지 그대로 복제하는
근거가 아니다. 구현 전후 검토에서는 **정보 위계, 공학 작업 흐름, 반응형·넓은 화면 구성**을
각각 pass/fail로 기록한다.
현재 제품 소유자의 명시적 피드백과 승인 reference가 충돌하면 현재 피드백을 우선한다. 충돌한
화면은 낡은 결함을 다시 구현하지 말고, 같은 단위에서 reference와 manifest까지 갱신한다.

## 3. 반드시 자연스럽게 이어져야 하는 두 흐름

### 3.1 기존 결과를 찾아 사용하는 흐름

```text
Materials 검색 또는 Browse
→ Material/Record 선택
→ 조건·출처·개정본·곡선·카드 적용 가능성 확인
→ 정확한 솔버 카드 미리보기/다운로드
  또는 정확한 문맥으로 Start Modeling
```

이 흐름에서는 검색 결과와 선택 문맥을 잃지 않는다. Modeling으로 이동할 때 Material, Material
State, 관련 Test Data와 정확한 revision을 넘기며, 사용자가 같은 항목을 다시 찾도록 만들지 않는다.
Modeling에서 Materials로 돌아오면 이전 검색, Tree 위치, 선택과 상세 탭을 가능한 범위에서 복원한다.

### 3.2 시험 데이터에서 모델과 카드를 만드는 흐름

```text
정확한 Material/State/Test Data 선택
→ Data
→ Process
→ Fit
→ 사용할 모델을 명시적으로 선택·저장
→ Export
→ 솔버 카드 생성·저장
→ Materials에서 다시 검색·조회·다운로드
```

`Data | Process | Fit | Export`는 하나의 작업 세션과 shell 안에서 이어진다. stage가 바뀔 때
그래프와 선택 문맥이 불필요하게 사라지지 않는다. recommendation, preview, selected candidate,
saved model, validation, review, release와 delivered artifact는 서로 다른 상태로 표현한다.

실패하거나 입력이 바뀌면 원본과 과거 개정본을 수정하지 않는다. 현재 선택, 초안, 마지막 유효한
그래프와 입력 문맥을 보존하고 한 개의 안전한 복구 동작을 제시한다.

## 4. 정보 위계

화면 공간과 강조는 다음 순서로 배정한다.

1. 현재 작업 데이터와 공학 결과
2. 선택된 identity, revision, condition과 state
3. primary action과 바로 필요한 local action
4. blocker, warning과 recovery
5. 비교, residual, 통계, validation과 evidence
6. 고급 설정
7. 일반 설명과 배경 지식

6과 7은 현재 의사결정에 직접 필요하지 않으면 `Advanced`, `Evidence`, disclosure 또는 사용자 문서로
이동한다. 내부 ID, hash, endpoint, 구현 객체명은 정상 사용자 화면의 빈 공간을 채우는 용도로 쓰지
않는다.

## 5. 보조문구 규칙

보조문구는 다음 중 하나를 수행할 때만 둔다.

- 사용자가 하기 쉬운 중대한 오해를 막는다.
- 동작이 차단된 정확한 이유를 설명한다.
- 실패 뒤 수행할 수 있는 복구 동작을 알려준다.
- revision 생성, release, approximation처럼 결과가 남는 동작의 영향을 설명한다.
- 단위, 좌표계, 통계 정의, extrapolation 범위 등 공학적 해석 조건을 명시한다.

다음 보조문구는 사용하지 않는다.

- 이미 보이는 버튼, label, stage 제목과 선택값을 다시 설명한다.
- “여기에서 무엇을 할 수 있다”는 소개문을 매 화면에 반복한다.
- 서버 구조, API 계약, 내부 상태명을 정상 작업면에 노출한다.
- Evidence에 있는 provenance를 정상 화면에서 다시 길게 설명한다.
- 빈 공간을 채우기 위해 문단을 추가한다.

기본은 관련 상태나 동작 옆의 짧은 한 문장이다. 더 긴 설명은 disclosure나 문서로 이동한다.

## 6. 그림과 시각 요소

인증된 작업공간에는 장식용 illustration을 기본적으로 사용하지 않는다.

허용되는 시각 요소는 실제 데이터나 작업을 설명해야 한다.

- 공학 그래프와 결과 preview
- 실제 genealogy, mapping, revision 관계
- specimen, imported file, solver card와 artifact preview
- 사용자가 다음 동작을 이해하는 데 필요한 작은 empty-state diagram

빈 공간을 채우는 큰 그림, 마케팅형 illustration, 현재 데이터와 무관한 공학 아이콘 모음은 사용하지
않는다.

## 7. 글자·굵기·색의 의미

글자 크기와 굵기는 공통 typography role을 따른다. 화면이나 컴포넌트가 임의 값을 새로 만들지 않는다.

- workspace title과 section heading은 계층을 나타낸다.
- 일반 label, table heading, tab, button을 습관적으로 bold 처리하지 않는다.
- revision, unit, method version과 count는 neutral metadata다.
- accent color는 selection, focus, primary action과 link에 한정한다.
- success, warning, danger는 실제 상태나 개입 필요성을 표현할 때만 사용한다.
- 색상만으로 상태를 전달하지 않는다.
- saved count, material family, method version과 분류값은 status chip이 아니다.

`eyebrow`, `workbench-card`, non-status `status-chip`, 장식용 badge는 공통 문법으로 사용하지 않는다.
필요하면 해당 요소가 어떤 사용자 판단을 돕는지 이슈와 PR에 기록한다.

### 7.1 공통 semantic UI API

신규 UI는 `apps/web/src/design/semantic-ui.tsx`의 다음 역할을 우선 사용한다. 역할은 보이는 모양이
아니라 사용자에게 전달할 의미로 선택한다.

| API | 허용 역할 | 선택 기준 |
| --- | --- | --- |
| `SemanticText` | `workspaceTitle`, `sectionHeading` | 작업공간과 section의 실제 계층 제목 |
| `SemanticText` | `label`, `value` | 필드·결과의 중립적인 이름과 값 |
| `SemanticText` | `metadata` | revision, unit, method version, count, family와 같은 보조 식별 정보 |
| `SemanticText` | `importantResult` | 사용자가 명시적으로 선택했거나 현재 판단에 중요한 결과 |
| `SemanticStatus` | `success`, `warning`, `danger` | 실제 완료·개입 필요·실패 상태. 보이는 `label`이 반드시 있어야 함 |
| `WorkbenchMessage` | `loading`, `empty`, `blocked`, `error`, `recovery`, `engineeringCondition` | 현재 작업 상태, 차단·복구 또는 공학적 해석 조건 |
| `EngineeringPane`, `EngineeringSection` | 접근 가능한 `label` | 정렬·여백·divider를 우선하는 flat grouping |
| `EngineeringPlotRegion` | 필수 plot, 선택적 companion | plot과 계약에 존재하는 실제 비교·evidence를 함께 배치할 때 |

`WorkbenchMessage`의 `recovery`에는 한 개의 명시적 action이 필요하다. primitive가 native button과
종류별 ARIA live semantics를 제공하므로 route가 임의의 alert/focus 문법을 다시 만들지 않는다.
`engineeringCondition`은 상태 색을 쓰지 않고 해석 조건을 전달한다.

`SemanticStatus`에 `neutral`을 추가하거나 metadata를 status로 감싸지 않는다. label 없는 status,
action 없는 recovery, label 없는 plot companion은 허용되지 않는다. ordinary heading을 accent로
표현하거나 `importantResult`를 단순 bold 용도로 선택하는 것도 금지한다.

## 8. 표면과 그룹화

그룹화는 다음 순서로 해결한다.

1. 정렬과 근접성
2. 일관된 여백
3. divider
4. 약한 배경 차이
5. border
6. radius 또는 shadow

독립적으로 선택·이동·재사용되는 객체가 아니라면 중첩 card를 기본 레이아웃으로 사용하지 않는다.
Materials는 explorer/result/datasheet, Modeling은 compact rail과 dominant graph라는 현재 topology를
유지한다. 별도 제품 결정 없이 Modeling에 영구적인 세 번째 inspector column을 추가하지 않는다.

## 9. 그래프와 고해상도

그래프는 배경 장식이 아니라 비교와 판단을 위한 도구다.

- 곡선 식별, 축 판독, 비교, 범위 선택과 annotation이 실제로 좋아지는 범위까지만 키운다.
- plot family마다 유용한 aspect와 크기 범위를 둔다.
- 유용한 범위에 도달한 뒤에는 계약에 이미 존재하는 실제 companion information을 사용할 수 있다.
  예: 선택 데이터 표, candidate/parameter/residual 비교, revision summary, validation result, evidence.
- 보여줄 실제 정보가 없으면 장식이나 가짜 데이터를 넣지 않고 균형 잡힌 여백을 허용한다.
- 3840×2160 화면은 FHD 그래프를 단순히 두 배로 키웠다는 이유로 통과하지 않는다.

1366×768에서는 핵심 작업과 동작을 보존하고 선택적 문맥을 줄인다. 1920×1080은 기준 정보 밀도를
제공한다. 2560×1440과 3840×2160에서는 실제 비교·열·evidence 용량을 늘리되, 글·form·plot을
무조건 비례 확대하지 않는다. CSS `zoom`, blanket scale transform, route 전용 4K patch와 fabricated
filler는 금지한다.

`EngineeringPlotRegion`은 plot과 선택적 companion의 접근 가능한 구조만 제공한다. 공통 primitive는
전 제품에 적용되는 픽셀 상한을 정하지 않는다. 각 plot family가 승인된 feature-owned CSS 또는
token으로 실제 축 판독·비교 작업을 측정해 useful bound를 소유한다. companion은 label과 실제
데이터가 함께 있을 때만 렌더링하며, 빈 region이나 placeholder를 공간 채우기용으로 만들지 않는다.

### 9.1 기존 화면 migration 경계

FE-02는 공통 문법과 개발자 예제를 제공하지만 기존 route의 `ux-meta`, `ux-kicker`, `ux-notice`,
`eyebrow`, `status-chip`, `workbench-card` 소비자를 일괄 변경하지 않는다. Modeling 정규화는 #260,
Materials·Administration 정비는 #262, 제품 전체 잔여 검증은 #264가 각각 실제 route와 다섯 viewport
근거를 가지고 수행한다. 구조·동작 특성화 단계에서 이 migration을 앞당기지 않는다.

## 10. 예외

이 원칙의 예외는 다음을 기록해야 한다.

- 필요한 사용자 판단 또는 공학 작업
- 기존 primitive와 topology로 해결할 수 없는 이유
- 영향받는 route와 state
- 동작·접근성·다섯 viewport 검증
- 제품 소유자 결정
- 임시 예외라면 제거 조건

“더 예뻐 보인다”, “빈 공간이 줄어든다”, “기존 파일에 비슷한 코드가 있다”는 예외 근거가 아니다.
