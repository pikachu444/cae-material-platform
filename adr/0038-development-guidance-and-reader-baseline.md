# ADR-0038: 개발 지침의 역할 분리와 소재 중심 조회 기준

- 상태: Accepted — 2026-09-07 사용자 지시에 따른 저장소 규칙 적용
- 범위: 저장소 작업 지침·문서 역할·frontend 검증의 적용 범위
- 대체: ADR-0037의 화면 비교 상태는 아래 연결된 후속 결정으로 갱신한다. 과거 ADR 본문과 번호는 보존한다.

## 이유

AGENTS·아키텍처·시각 매트릭스·skill에 같은 지시가 반복되었고, 새 기반에 기존 hotspot 추출 순서가 적용됐다.
A/B·여섯 시안 비교와 D0 문서 작업의 검사 예외도 후속 작업의 현재 규칙처럼 남았다.
사용자는 소재 중심 대표 화면의 큰 구조를 받아들이되 필터·열·세부 디자인은 나중에 바꿀 수 있어야 한다고 확인했다.

## 결정

1. 루트 AGENTS는 작업 시작·데이터 의미·검증·전달을 안내한다. 앱 AGENTS는 공통 frontend 지침을 연결하고 기존/새 앱의 차이만 둔다.
2. 제품 데이터 의미는 데이터 정책, 화면 기준은 UI 원칙, 소유권·기술은 아키텍처, 검사 범위는 시각 매트릭스와 검토 절차에 둔다. program은 범위/순서, status는 현재 상태/증거/다음 행동만 관리한다.
3. architecture skill의 필수 packet 절차를 해제한다. React·시각 검토·브라우저 skill은 실제 실행에 유용한 안내만 유지한다. frontend-ui-engineering과 webapp-testing은 기존 출처/라이선스를 보존한 로컬 관리본으로 전환하므로 upstream 그대로 설치된 파일처럼 skills-lock에 남기지 않는다. web-design-guidelines의 upstream lock은 유지한다.
4. Q-03 행 높이, Q-10 범례 사분면, Q-12 단일 선택지 Select 같은 구현 고정값을 가독성·조작성·출력 의미 검사로 바꾼다. Q-04는 현재 대표 화면의 조회/복귀를 검사하고 여섯 비교안 재제작을 요구하지 않는다. Q-08 항복 시작점은 해당 물리량에만 적용한다.
5. T 항목은 해당 제품·기술 변경의 추적 표식이다. 과학·권한·이관 검사를 유지하고, 비소재 revision 관련 기존 검사는 실제 DB/API 이관과 대체 검증이 생길 때 변경한다. 이 문서 작업에서 제거하지 않는다.
6. 초기 기획의 ADR-001~012 개요 번호와 실제 ADR 파일 번호를 구분한다. 과거 roadmap은 reference로 분류하되 원문과 완료 기록을 보존한다. manifest 분류는 문서 안의 Accepted/Proposed/Superseded 상태를 덮지 않는다.
7. 개인 오케스트레이션·프로필·모델 배정은 **이번 적용에서 보류한다**. 사용자는 고급 모델의 설계와 낮은 비용 모델의 구현을 나누는 비용 절감 목적을 설명했으며 후속 논의를 요청했다. Main 직접 수행을 전 작업의 영구 정책으로 새로 고정하지 않는다.
8. hook/게시 검사는 유지한다. 도구 이름 차이만으로 고장이라고 판단하지 않으며 실제 실행·중복 비용은 별도 확인한다. 검사 실패를 없애려고 무관한 guard를 삭제하지 않는다.

## 유지하는 경계

소재 정보 수정만 리비전 관리한다. 안정적인 ID·저장 관계·원본 bytes·실제 입력/설정·단위·권한·IR/solver 의미는 유지한다.
최소 기반과 대표 조회 업무를 먼저 검증하고 이후 확장·일괄 전환한다. 현재 규칙 적용은 DB/API 이관, 공학 qualification, commit/push/PR/merge, 다른 worktree 삭제를 뜻하지 않는다.

## 검사와 남은 확인

문서 분류·링크·ADR 색인·docs-impact·user-guide, 변경 skill의 frontmatter와 실제 요청 해석을 확인한다.
합성 시안 변경과 실제 navigation 변경의 검사 범위를 구분하고, 실제 source/권한/단위 검사의 실패 의미를 유지한다.
새 태스크에서 이 지침으로 첫 연결 업무를 수행해 불필요한 지시 반복과 질문, 누락된 계약이 없는지 확인한다.
모델 배정의 비용 효과는 명세 작성·구현·교정·검수의 전체 비용으로 이후 평가하며 이번 결정에서 수치를 추정하지 않는다.

## 관련 자료

2026-09-08 후속 결정: 사용자는 모든 자료의 상세 화면에서 의미 없이 나열되는 긴 식별자와 해시를 제거하도록 지시했다.
기존 Evidence/Advanced 배치 지침을 새 reader의 표시 의무로 해석하지 않는다. 저장 관계와 파일 검증은 유지하되,
화면에는 사용한 자료·처리 설정·물성·적용 범위·출력의 근사를 읽을 수 있게 표시한다.
세부 기준은 [UI 원칙](../docs/product/frontend-ui-principles.md)의 공학 정보 표기가 대체한다. 과거 기록은 삭제하지 않는다.

- [현재 데이터 정책](../docs/product/data-management-policy.md)
- [frontend 결정과 후속 화면 선택](0037-task-first-frontend-foundation.md)
- [현재 작업 상태](../docs/planning/frontend-redesign-status.md)
- [적용 전 제안](../design/frontend-reader-proposals/material-workspace/governance/README.md)
- [공식 AGENTS 설명](https://learn.chatgpt.com/docs/agent-configuration/agents-md): 상위/하위 지침을 결합하므로 범위별 지침의 역할을 나누었다.
- [공식 Hooks 설명](https://learn.chatgpt.com/ko-KR/docs/hooks): matcher와 실행 결과를 구분하며 실제 이벤트 미확인을 오류로 단정하지 않았다.
