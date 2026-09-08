# 프론트엔드 아키텍처

범위: 기존 `apps/web`와 새 `apps/web-next`. 결정은 [ADR-0037](../../adr/0037-task-first-frontend-foundation.md), 규칙 정리의 대체 관계는 [ADR-0038](../../adr/0038-development-guidance-and-reader-baseline.md)에서 확인한다.
진행 상태는 [개편 상태](../planning/frontend-redesign-status.md), 화면 구성은 [UI 원칙](../product/frontend-ui-principles.md)이 맡는다.

## 목표와 이행

검증된 backend·공학 로직을 활용하면서 frontend 기반을 새로 설계한다. 필요한 최소 기반 → 실제 조회·다운로드 → 검증 → 등록·처리·모델·솔버 확장 → 검증 후 일괄 전환 순서다.
`apps/web-next`는 임시 이행 경계다. 기존 화면 순서·DOM·CSS 호환이나 장기간 두 제품 병행은 필수 조건이 아니다.
데이터·권한·단위·저장·복구 의미는 보존한다. 데이터 구조 이관은 계약·DB·read-back 검증과 함께 수행하며 문서 변경만으로 완료 처리하지 않는다.

## 기술 기반

React·TypeScript·Vite의 버전은 현재 package.json과 lockfile을 따른다. 새 기반의 역할은 다음과 같다.

| 책임 | 기반과 판단 |
| --- | --- |
| 접근성 primitive | Radix 등 검토한 기반. native HTML로 충분하면 그대로 사용한다. Dialog·Select·Tooltip의 키보드 동작을 임의로 다시 만들지 않는다. |
| 탐색·서버 데이터·표 | React Router, TanStack Query/Table. query와 URL 역할을 나누고 표 크기에 따라 pagination/virtualization을 검증한다. |
| 편집·입력 검증 | React Hook Form/Zod. 사용자 form과 API 경계 검증을 구분하며 실제 계약을 복제해 불일치시키지 않는다. |
| 스타일·아이콘 | CSS Modules, CSS 변수 token, Lucide. 기존 resizable panels는 사용 적합성을 확인한다. |
| 공학 차트 | ECharts·SVG·Recharts 중 실제 점 수·곡선 수·줌·단위·내보내기 요구로 결정한다. 합성 SVG 시안은 성능 근거가 아니다. |
| 검사 | Vitest/Testing Library는 규칙·component, Playwright는 연결 업무, Storybook은 반복 확인할 재사용 component 상태에 사용한다. |

새 dependency는 기능·접근성·라이선스·유지보수·bundle·현재 stack 호환성을 확인하고 선택 이유를 해당 변경에 기록한다.
Tailwind/shadcn 전환은 이번 결정에 포함되지 않는다. 더 적합한 대안을 근거로 제안할 수 있으며 후보 목록 자체가 영구 금지 목록은 아니다.
패키지 대신 전체 외부 저장소를 복사하거나, 확인하지 않은 공학 계산을 UI 코드로 재작성하지 않는다.

## 책임과 디렉터리

의존 방향은 `app → features → shared`다. shared는 app/feature를 import하지 않는다. feature 사이에는 public entry 또는 app의 조합을 사용하며 내부 deep import와 순환 참조를 만들지 않는다.

```text
src/app/                   routing, provider, shell, 기능 간 연결
src/features/materials/    소재 탐색·물성·소재 편집
src/features/test-data/    실험 조회·등록
src/features/processing/   처리·반복 실험·저장 결과
src/features/models/       모델 선택·계산·저장
src/features/solver-cards/ 저장 카드·native 다운로드·출력 설정
src/shared/ui/             범용 primitive의 필요한 wrapper
src/shared/engineering/    검증된 순수 단위·계산·검증 로직
src/shared/api/            transport·공통 오류·계약 타입
src/styles/                reset·공통 token
```

필요한 feature부터 만든다. 모든 폴더를 미리 만들거나 업무마다 같은 파일 구성을 강요하지 않는다.
Activity·Administration도 해당 업무를 옮길 때 책임을 만든다. 단위 입력·조건 표·곡선 비교·모델 상태·출력 지원 설명은 제품 component가 맡고 범용 primitive에 domain 기본값을 넣지 않는다.
한 기능에서만 쓰는 계산은 그 기능에 두고 실제 공유 근거가 생기면 이동한다. 단순 prop 전달을 줄이려고 전역 store나 controller 계층을 만들지 않는다.

## 상태와 데이터 소유권

| 상태 | 소유자 | 확인할 동작 |
| --- | --- | --- |
| 서버 객체·조회 결과 | 기능 query/API 계층 | query key에 권한 범위·ID·조건 포함, 취소/늦은 응답 처리, 서버 전체 건수와 facet 범위 일치 |
| 검색·필터·정렬·페이지·선택·상세 | URL/Router | 직접 주소 진입, 새로고침, 뒤로 가기; 선택이 현재 목록 범위를 벗어나면 명시적으로 정리 |
| 미저장 편집 | 업무 form/draft | query 재조회가 입력을 덮지 않음, 이동·실패·재접속에서 저장/복구 의미 명시 |
| 패널 열림·hover 등 | 지역 UI state | 선택 대상과 패널 열림을 구분; 복원이 필요한 패널 상태만 URL/저장 대상에 포함 |
| 비동기 처리 결과 | 해당 작업의 결과 상태 | 실제 입력·설정·실행 식별과 결과 연결, 이전 결과 표시, 현재 결과와 저장 상태 분리 |

입력 signature는 현재 결과 유효성 판정에 사용할 수 있지만 비소재 revision 이력이 아니다.
입력·옵션 변경 후 이전 결과를 현재 결과로 저장하거나 출력하지 않는다. 이미 저장된 결과는 조회·다운로드할 수 있다.
이름 변경만으로 공학 결과를 무효화하지 않는다. [데이터 정책](../product/data-management-policy.md)의 소재 리비전·안정적 ID·명시적 관계를 따른다.

API adapter는 기능별 응답을 표시 모델로 바꾸며, backend 미지원 기능을 합성 성공으로 감추지 않는다.
권한은 서버에서 검사한다. `latest`, 첫 항목, 이름 추정, 다른 세션 결과로 누락된 문맥을 채우지 않는다.
모든 draft를 무조건 localStorage에 저장하는 범용 장치를 만들지 않는다. 필요한 저장 범위와 복구 기간은 해당 편집 업무에서 정한다.

## CSS와 시각 책임

앱 reset·token만 전역으로 두고 component 스타일은 module 범위로 관리한다. 기능 배치는 기능이, 공통 패널·입력 크기·글자·간격은 token이 소유한다.
경로마다 4K override, CSS zoom, 전체 scale transform을 추가하지 않는다. 그래프는 실제 크기에 맞춰 좌표를 계산한다.
기존 `apps/web/src/design/semantic-ui.tsx` API와 legacy guard는 기존 소비자에 적용한다. 새 앱에 같은 이름과 wrapper 구조를 강제하지 않는다.

## 기존 로직 이동과 삭제

기존 hotspot에서 계산·단위·검증·파일 출력·세션 복구의 위치와 호출자를 먼저 확인한다. 큰 render 파일을 작은 wrapper 여러 개로 나누는 것만으로 완료하지 않는다.
이동 순서는 실제 결합에 따라 정한다. 모든 변경에 순수 함수 → controller → UI 추출을 요구하지 않는다.
검증된 의미를 보존하되 잘못된 기존 동작은 합의한 기준 데이터로 바로잡는다. 필요한 호환 adapter에는 소비자와 제거 조건을 적는다.
구형 코드·CSS·dependency는 대체 업무 검사, 소비자 0개, 데이터 이관·복구 확인 후 삭제한다. 전환 복구는 기존 build/경로와 보존된 데이터로 수행하며 사용자 데이터를 파괴하는 downgrade를 쓰지 않는다.

## 경계가 바뀔 때의 짧은 점검표

- 어느 사용자 업무와 API·단위·저장 의미가 바뀌는가?
- 상태·계산·UI의 주인이 누구이며 중복 사본이나 순환 의존이 생기는가?
- 입력 변경·늦은 응답·미저장 편집·복귀를 어떤 검사로 확인하는가?
- 실제 재사용할 기존 로직과 제거할 소비자는 무엇인가?

이 점검은 작업 계획 안에 포함하면 된다. 별도 architecture skill이나 장문의 packet을 모든 변경에 요구하지 않는다.

## 확장 예시

### 실험 조회에서 처리 업무로 확장

RD-02의 다음 구조 검수 사례는 실험 선택 → 처리 설정 → 실행·결과 비교 → 저장·재조회 →
처리 데이터 다운로드다. reader는 안정적인 실험 ID, 실제 조회한 v1 revision pin, 검증된 채널·조건·단위를
전달한다. 목록 선택과 처리 입력은 별도 상태다. 앱은 기능 간 진입을 조합하고 processing 기능이 입력
적격성·기본/고급 설정 초안·실행 요청·결과 유효성·저장·복구를 소유한다.

현재 공통 처리 계약은 `POST /processing:preview`의 응답과 `POST /processing-outputs`의 명시적
저장을 구분한다. 조회는 `GET /processing-outputs`, 저장된 JSON 다운로드는
`GET /processing-outputs/{output_id}/content`다. 비동기 job/polling은 해당 방법의 실제 계약이
요구할 때만 추가한다. 입력 변경 뒤 늦은 응답은 processing의 요청/입력 식별로 구분하며 이전 결과를
현재 입력의 결과로 저장하지 않는다. 저장된 결과 조회는 실제 입력과 함께 계속 허용한다.

확장 시 processing의 API adapter·입력/설정 타입·적격성 규칙·설정 form·결과 비교·저장/복구 검사를
추가한다. 기존 reader 목록·페이지·미리보기 controller에 처리 명령을 붙이지 않는다. 조건/단위 표시,
곡선 renderer, 오류·다운로드 primitive는 실제 공통인 부분만 재사용하고, 계산·방법별 설정·결과 의미는
processing/domain에 둔다. 그래프에 처리 알고리즘을 넣거나 전역 선택 store를 처리 세션으로 사용하지 않는다.
이 설명은 확장 경계이며 RD-02에 빈 처리 framework나 미구현 실행 버튼을 추가할 이유가 아니다.

온도 의존 모델을 추가하면 모델 capability, API/IR adapter, 해당 form, 곡선 비교, 검증 fixture, solver 출력 지원 표를 수정한다.
소재 목록 shell·Dialog·공통 query transport·다른 solver 화면까지 함께 바꿔야 한다면 경계를 다시 확인한다.
backend가 지원하지 않는 모델을 frontend component만으로 지원한다고 표시하지 않는다.

모델 IR은 이미 solver-neutral 모델 내용이고 Neutral Material JSON은 그 내용과 출처·선택·적용 범위를
담는 교환 문서다(ADR 0005·0029, material-model-ir §17). reader는 이를 서로 다른 물성 모델 종류나
필수 생성 두 단계로 분류하지 않는다. 기존 source family와 revision별 API는 호환 adapter에 남고
일반 카드 목록은 실제 모델 계열로 묶는다. 기존 저장 객체의 통합과 중간 생성 API 제거는 중복·migration
영향을 확인하는 frontend·backend 공동 설계 검토 대상이며 RD-02는 저장 데이터와 계산을 바꾸지 않는다.
새 입력 형식은 importer·명시적 column/unit mapping·계약 검사, 새 solver는 exporter·지원표·검증으로
확장한다. 기존 CSV/TSV/XLSX의 공통 Test Data 변환이 모든 임의 형식의 자동 지원을 뜻하지 않는다.

공동 검토는 모델의 유일한 기준 데이터와 identity, IR·교환 JSON의 중복 값/동기화와 독립 저장 필요성,
importer→공통 Test Data→처리 결과→모델→solver exporter 계약, 교환 포장의 필수 생성 단계 여부를
함께 판단한다. 변경 시 원본·저장 산출물·계산 의미를 보존하는 migration과 동등성 검증을 선행한다.
RD-02의 표시/조회 호환 개선은 공통 domain/API 설계나 저장 모델 통합의 완료가 아니다.

현재 Neutral 승격은 별도 ID·revision과 물성 저장을 만들며 embedded model ref도 새 ID를 사용한다.
IR/교환 envelope는 통합 검토 방향이다. 현재 저장 identity가 이미 하나라는 뜻이 아니며, 공통 기준과
중복 저장·동기화·이관 동등성은 frontend·backend 공동 후속 검토에서 결정한다.
