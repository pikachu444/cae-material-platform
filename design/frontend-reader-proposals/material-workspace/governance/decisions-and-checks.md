# 제품·설계 문서의 대체 문구와 검사 연결

적용 전. 문서 수를 늘리는 영구 보고 체계가 아니라 기존 기준 문서를 정리하기 위한 변경 목록이다.

## 기준 문서의 역할

| 문서 | 남길 역할 | 옮기거나 없앨 중복 |
| --- | --- | --- |
| root/앱 AGENTS | 작업 방법과 필요한 기준으로 가는 안내 | 시안 설명, Q 전체 목록, 모델별 역할, 이슈별 과거 증거 |
| data-management-policy | 소재 리비전·ID·링크·원본/결과·저장 의미 | 화면 배치와 사용자 행동 순서 |
| frontend-architecture | module 소유권·상태·API·기술 선택과 경계 | 현재 작업 진행률, 시안 우승 후보 |
| frontend-ui-principles | 정보 표기·상호작용·시각 기준 | 특정 회사 UI 합성 의무, 예전 화면의 영구 픽셀 규칙 |
| ADR + index | 결정 이유, 상태, 대체 관계 | 현재 진행 상황을 모든 ADR에서 반복 갱신 |
| program/status | 전체 범위/순서와 현재 작업·증거·다음 행동 | 서로 다른 “현재 추천안”의 중복 |
| product-work-acceptance | 짧은 검증 양식 | D0 문서 작업의 N/A를 전체 작업 규칙처럼 표현 |
| visual matrix | 사용자 요구 → 해당 화면/상태 → 증거/판정 | 모든 소규모 변경에 6개 비교안 재제작 |
| 과거 T/Q·증거 | 목적과 결정 이력·회귀 이유 | 파일명이 있다는 이유만으로 새로운 의무 생성 |

### ADR index 마지막 단락 대체

> ADR-0036은 소재 정보 수정만 리비전 관리하는 현재 데이터 정책이다. ADR-0037은 새 frontend 기반과 단계적 구현·일괄 전환의 결정을 담는다. 과거 A/B 및 6개 비교안은 평가 이력이다. 현재 검토 화면과 사용자 선택 상태는 frontend-redesign-status에서 확인한다. 소재 중심 탐색과 독립 실험·카드 경로를 함께 검토하며, 미선택 시안은 구현의 고정 기준이 아니다.

ADR-0037의 기존 본문을 조용히 덮어쓰지 않는다. 이번 소재 중심 탐색이 승인되면 날짜와 범위가 있는 amendment를
추가해 “decision 2 및 2026-09-06 비교 범위의 후속 결정”임을 남긴다. 최종 승인 전에는 다음 문구를 Proposed로 둔다.

> 소재 중심 탐색과 직접 실험/솔버 카드 조회를 함께 제공한다. 소재 카드는 항목·값·단위를 정렬하고 표 보기와 전환한다. 목록 선택은 오른쪽 미리보기, 확대 상세는 목록을 숨기며 복귀 시 탐색 상태를 복원한다. 소재 연결을 실제 생성 입력 관계와 혼동하지 않는다. 구체 시각 기준은 승인된 대표 화면에 한정하며 이후 등록·처리 화면을 같은 목록 구성에 강제로 맞추지 않는다. 기존 foundation·공학·단일 전환 결정은 유지한다.

새 ADR 번호가 필요하면 실제 index의 다음 번호를 확인한 뒤 할당한다. 이 초안에서 미사용 번호를 확정하지 않는다.

### planning 문서의 중복 ADR 번호

`risks-open-questions-decisions.md` §6 제목을 “초기 기획의 결정 개요 — 역사적 번호”로 바꾼다.
첫 열은 `ADR-001`~`ADR-012`를 `초기 개요 01`~`초기 개요 12`로 표시하고 원래 번호를 괄호로 보존한다.
현재 Accepted라고 쓰인 상태는 “작성 당시 상태”로 명시한다. 실제 ADR과 자동 일대일 매핑하지 않는다.
특히 개요 04의 불변 revision과 개요 05의 범용 provenance는 ADR-0036과 데이터 정책의 현재 범위로 대체됨을 적는다.
다른 개요는 해당 실제 ADR을 확인한 경우에만 링크한다. 이유 없이 모두 폐기하거나 모든 문서의 ADR 번호를 치환하지 않는다.

## architecture에 넣을 현재 책임 구조

```text
src/app/                  routing, provider, shell
src/features/materials/   소재 탐색·물성·소재 편집
src/features/test-data/   실험 조회·등록
src/features/processing/  처리·반복 실험·저장 결과
src/features/models/      모델 선택·맞춤·저장
src/features/solver-cards/ 저장 카드 조회·native 다운로드·출력 설정
src/shared/ui/            검토한 primitive의 얇은 wrapper
src/shared/engineering/   검증된 단위·계산·validation (순수 로직)
src/shared/api/           transport·공통 오류·생성된 계약 타입
src/styles/               reset·공통 token
```

필요한 feature부터 만든다. 모든 폴더를 빈 scaffolding으로 만들거나 업무마다 같은 8개 파일을 강요하지 않는다.
feature별 `api`, component, form은 실제 복잡도가 필요할 때 분리한다. 기존 export 조합·단위 검증의 위치와 소비자를
확인하고 옮긴 뒤 새 UI에 연결한다. 새 UI가 편하다는 이유로 science 로직을 다시 추정해 쓰지 않는다.

서버 데이터는 TanStack Query, 탐색은 URL/Router, 편집은 RHF 등 form, 임시 UI는 지역 state를 기본으로 한다.
작업 결과는 입력 ID·실제 입력 signature·설정·저장 상태를 보유한다. signature는 유효성 판정이지 비소재 revision 이력이 아니다.
오래된 비동기 응답을 현재 결과로 받아들이지 않는 검사와 미저장 편집 복구 검사를 별도로 둔다.
query에 폼의 미저장 값을 덮어쓰거나 미저장 상태를 localStorage에 무조건 영구 보관하는 공통 장치를 만들지 않는다.

외부 기반은 ADR-0037의 검토 stack을 이어간다. Radix 기반 접근성, TanStack의 query/table, RHF/Zod, Lucide,
CSS Modules/token이 각각 맡는 역할을 유지한다. Tailwind/shadcn 전환을 이 규칙 정리에서 새로 확정하지 않는다.
차트는 실제 점 수·곡선 수·확대/범례/내보내기·공학 단위를 비교해 결정한다. 이번 SVG 시안은 성능 근거가 아니다.

예: 온도 의존 모델을 추가하면 모델 capability·API/IR adapter·해당 설정 form·곡선 비교·검증 fixture·출력 지원 표를
수정한다. 소재 목록 shell, Dialog, query transport, 다른 솔버 화면까지 일괄 수정해야 한다면 경계를 다시 검토한다.
backend가 새 모델을 지원하지 않으면 frontend component만 추가해 지원된다고 표시하지 않는다.

## UI principles와 Q 변경

| 기존 항목 | 대체할 검사 가능한 문구 |
| --- | --- |
| Q-03 고정 24–26 px | 탐색 트리의 펼침·표식·이름은 같은 행에 정렬한다. 합의한 화면 크기에서 이름/선택/포커스가 읽히고 스크롤과 겹치지 않는다. 크기는 공통 token으로 조정한다. |
| Q-04 6개 비교 의무 | 현재 사용자 검토 대상 화면의 목록·오른쪽 미리보기·확대·접기·페이지 복귀를 같은 자료로 확인한다. 이전 비교안은 역사적 증거로 남긴다. |
| Q-08 양의 항복 시작점 | true stress–plastic strain 출력에만 적용한다. 공칭 응력–전체 변형률 등 다른 축 의미의 곡선에 복제하지 않는다. 모든 차트는 물리량·단위·변환을 확인한다. |
| Q-10 범례 위치 | 범례·축·곡선이 겹치지 않고 곡선의 대응을 식별할 수 있어야 한다. 고정 사분면을 강제하지 않는다. 실제 곡선 수와 지원 viewport에서 확인한다. |
| Q-12 선택지 1개의 Select | 지원 단위가 하나면 고정값으로, 여러 개면 선택으로 보여준다. 사용자가 지원 범위와 출력 단위를 알 수 있고 잘못된 대안을 선택할 수 없어야 한다. |

나머지 Q와 T는 ID별로 **목적, 현재 적용 대상, 연결 검사, 과거 증거**만 유지한다. T는 제품 요구나 해당 검사로 이어지는
추적 표식이지 모든 작업에 모든 테스트를 요구하는 승인 단계가 아니다. 실제 T 정의·소비자 검색 없이 번호를 일괄 삭제하지 않는다.
기존 권한·단위·동일 identity·결과 무효화·미저장 편집 보호 항목은 유지한다.

구체적으로 `docs/testing/test-strategy.md`의 T-42는 로그 축 공통 구간 정렬, 선형 보간, 반복 수 기반 통계,
외삽 금지, 온도·권한 검사를 보존한다. 같은 절의 immutable nonmaterial revisions와 필수 세 provenance subactivity는
ADR-0036 적용 이관 시 stable ID·실제 입력/설정·저장 결과의 read-back 검사로 대체한다. 현재 backend가 구 계약을 쓰는
동안 테스트를 미리 제거하지 않는다. 인장 반복 통계에 로그 축 TTS 조건을 그대로 복제하지 않는다.
T-43 Ogden, T-64 솔버 출력은 해당 모델/출력 변경 때 적용하고 단순 조회 시안에는 N/A다.
T-47의 관측/복구, supply-chain, 전체 성능, 외부 worker 절은 서로 다른 적용 범위를 제목에서 명시한다.
테스트 분류표의 “모든 PR”은 CI 실행 정책과 변경 범위를 확인해 “관련 변경 PR / 정기 통합 검증”으로 나눈다.

시각 token의 초안은 시안 CSS에서 검토한다. 흰 데이터 면, 차분한 회색 분리, 파란 선택/주요 행동, 오류색은 상태에만 쓴다.
물성은 수치 우측 정렬과 별도 단위·조건, 긴 이름은 줄바꿈, 표 header는 스크롤해도 대응을 유지한다.
색만으로 선택/오류를 구별하지 않는다. 승인 전 이 색상과 수치를 영구 정책으로 승격하지 않는다.

## 검사와 문서 impact 정리

| 변경 | 연결 검사 | 하지 않을 일 |
| --- | --- | --- |
| 문서·지침 | 현재 docs-impact/user-guide/diff 검사, 로컬 링크, 신규 규칙의 소비자 확인 | 코드를 안 바꾼 작업에 DB/전체 브라우저 강제 |
| 새 reader | 새 앱 typecheck/build/test + 1개 연결된 조회→저장 카드 다운로드 흐름 + 오류/권한/복귀 회귀 | legacy guard 통과를 새 앱 검사로 보고 |
| primitive/token/layout | component 접근성/키보드 + 영향 viewport 원본/영역 crop | 한 단어 수정마다 다섯 해상도·모든 시안 재촬영 |
| 단위/처리/평균/출력 | 승인 기준 데이터·허용오차·금지/미지원 사례 + 실제 저장/재조회 | 기존 잘못된 결과를 golden으로 확정 |
| 데이터 이관/전환 | 백업 read-back, migration 검증, ID/link/bytes 비교, 전환·복구 rehearsal | 되돌리기 위해 사용자 데이터 삭제 |

현재 명령 `npm run check`와 `npm run check:web-next`의 역할을 README에서 분리한다. 새 앱 production 연결 후에는
prototype 검사가 아닌 해당 계약/브라우저 검사로 새 앱의 통합 명령을 갱신한다. legacy hotspot/raw CSS guard는 legacy에만 남긴다.
새 기반에서 실제 필요한 import/CSS 경계만 lint로 검사한다. 파일 줄 수를 설계 품질의 단독 기준으로 삼지 않는다.

manifest는 `reference` 시안/조사와 현행 요구·계약을 구분한다. 모든 `docs/analysis/**`를 한꺼번에 reference로 바꾸지는 않는다.
우선 중복 결정 개요·역사적 roadmap처럼 이미 대체 관계가 확인된 **정확한 파일**부터 분류를 바꾼다. ADR은 index에
Accepted/Proposed/Superseded 및 대체 링크를 기록하고, manifest의 광역 authoritative 표기가 상태를 덮지 않게 검사한다.

적용 단위에서 확인할 최소 fixture는 (1) 참고 시안 수정은 production 가이드 재촬영 요구 없음,
(2) 실제 navigation 변경은 현행 계약/가이드 갱신 누락을 검출,
(3) Superseded ADR은 기록을 보존하되 현재 시안 고정을 요구하지 않음,
(4) 잘못된 단위/끊긴 링크/미지원 exporter의 실패는 그대로 검출이다.

현재 hooks와 pre-push를 즉시 삭제하지 않는다. 중복 실행이 실제 발생하는지 측정하고 같은 SHA·diff·gate 범위의 결과만
재사용한다. 다른 diff 결과를 재사용해 검사를 우회하지 않는다. Stop hook이 작업 완료 여부를 AI 문구로 추정하는 규칙은
추가하지 않는다. 변경 경로와 누락 자료를 알려주는 좁은 결정적 검사로 유지한다.
