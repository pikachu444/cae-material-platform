# 프론트엔드 변경 검토 절차

두 앱의 검사 적용 범위를 정한다. [공통 구현 지침](frontend-development.md), [아키텍처](../architecture/frontend-architecture.md), [UI 원칙](../product/frontend-ui-principles.md), [시각 매트릭스](../product/visual-acceptance-matrix.md)를 필요한 부분만 읽는다.
현재 작업은 [개편 상태](../planning/frontend-redesign-status.md)에서 확인한다. 과거 #249 FE 순서와 D0 문서 예외는 새 작업의 선행 의무가 아니다.

## 변경과 검사 연결

| 변경 | 필요한 확인 |
| --- | --- |
| 문서·지침 | 링크/분류/대체 관계, docs-impact, user-guide, diff 검사. runtime을 바꾸지 않으면 DB·브라우저·재촬영은 N/A |
| 기존 앱 코드 | 해당 계약/component 검사·build, `@cmp/web` frontend guard. 실제 변화가 있는 업무·복구·화면만 추가 확인 |
| 새 앱 코드 | `npm run check:web-next`의 현재 범위와 관련 단위 검사. 연결 이후 실제 API·권한·다운로드·재조회 흐름 검증 |
| primitive/token/layout | 접근성·키보드와 영향 화면·viewport 원본. 공통 layout 영향이면 범위를 넓힘 |
| 단위·처리·통계·모델·출력 | 기준 입력·허용오차·미지원 사례, 실제 결과 저장/재조회. golden 변경 이유와 검증 근거 |
| 이관·전환 | ID/link/bytes·권한 비교, backup read-back, 전환·복구 rehearsal, 쓰기 정합성 |

루트 `npm run check`는 기존 `apps/web`의 guard/build/test다. 새 앱을 검사했다고 보고하지 않는다.
새 앱의 `check:web-next`는 현재 합성 prototype 검사이며 실제 API 연결의 완료 증거가 아니다. 연결 단위에서 필요한 검사를 보강한다.
CI의 자동 실행 범위는 workflow/스크립트를 따른다. 변경 범위별 작업 검사와 자동 CI 전체 검증을 구분한다.

## 책임·상태 검토

경계가 바뀌면 아키텍처의 점검표를 작업 계획에 포함한다. 필수 architecture skill 호출이나 고정 controller 추출 순서는 없다.
큰 파일에 책임이 더 쌓이지 않게 하되 줄 수만으로 분할하지 않는다. 기존 API·계산·출력의 의미와 호출자를 확인한다.
입력 변경·늦은 응답·이름 변경·미저장 편집·목록 복귀를 해당 업무에서 검사한다.

## 화면 검토

현재 기준과 대상 상태를 확인하고 실제 전후 화면을 비교한다. 정보 위계·공학 업무·넓고 좁은 화면 구성을 함께 판단한다.
모든 작은 수정에 전체 Q 표와 여섯 비교안을 재작성하지 않는다. 해당 Q와 영향 상태를 기록하고 무관한 항목은 묶어서 N/A와 이유를 남긴다.
독립 검수가 배정되면 같은 기준·diff·실제 증거를 전달한다. 검수의 판정은 사용자의 제품 방향 선택이나 게시 권한을 대신하지 않는다.

## 문서와 guard

실제 제품의 navigation/화면이 바뀌면 해당 계약·가이드·현재 PNG·manifest를 함께 갱신한다. 합성 시안과 미사용 Storybook fixture는 실제 제품 화면이라고 기록하지 않는다.
기존 documentation-impact의 정밀한 예외/소비자 검사는 유지한다. 검사 실패를 피하려고 production 경로를 reference로 분류하거나 넓은 예외를 추가하지 않는다.
legacy guard baseline을 새 앱의 설계 기준으로 복사하지 않는다. 예외는 정확한 rule/path/원인·소유 범위·제거 조건을 설명하고 관련 검사를 유지한다.

## High-DPI policy and historical handoff (authoritative)

현재 캡처 크기·원본/crop·판독 기준은 시각 매트릭스에서 관리한다. 브라우저 geometry와 실제 모니터/Windows 배율의 가독성은 다른 검증이다.
실제 4K 장비가 없으면 물리 가독성은 #223에 deferred로 기록할 수 있다. 알려진 clipping·overflow·접근 불가능한 동작까지 미루지는 않는다.
#160/161 → #221 → #184 → #223은 과거 전환/장비 검증의 이력이다. 당시 예외·화면 수치를 새 frontend 모든 변경에 강제하지 않는다.
공통 token을 사용하고 route별 4K override·CSS zoom·전체 scale·가짜 filler·SVG 비균일 확대는 허용하지 않는다.

## 전달

사용자에게 달라진 행동, 보존 의미, 검사와 한계, 남은 작업을 설명한다. 시안 검증·실제 API 검증·공학 검증·제품 전환 완료를 구별한다.
커밋/게시와 추적 동기화는 루트 AGENTS의 사용자 권한 범위에서 수행한다.
