---
name: frontend-ui-engineering
license: MIT; complete terms in LICENSE.txt
description: Implement React components, forms and interactions in CAE Material Platform with feature ownership, accessible controls and explicit edit/result states.
---

# React 구현

프로젝트에서 유지하는 skill이다. 원래 addyosmani/agent-skills의 frontend-ui-engineering에서 가져왔으며 현재 본문은 로컬 정책에 맞게 관리한다. [MIT 라이선스](LICENSE.txt)와 원저작권 고지를 보존한다.

- 해당 앱 AGENTS와 작업에 필요한 API·화면 계약을 확인한다. [공통 구현 지침](../../../docs/repository/frontend-development.md)을 중복 작성하지 않는다.
- native 요소나 검토된 외부 primitive로 키보드 동작을 조합한다. 단위 입력·곡선·모델 상태의 의미는 제품 component에 둔다.
- form label·오류 연결·visible focus·Dialog 열기/닫기 초점·Escape·키보드 경로를 확인한다. 색만으로 상태를 전달하지 않는다.
- 서버 재조회가 미저장 편집을 덮거나 늦은 응답이 새 선택을 바꾸지 않게 한다. 이전 결과의 표시·저장/출력 차단·복구를 확인한다.
- 긴 이름, 조건과 단위, 많은 행·곡선으로 확인한다. 실제 규모에 따라 pagination/virtualization과 그래프 렌더링을 선택한다.
- 변경한 규칙은 component/단위 검사, 연결 업무는 브라우저로 확인한다. 화면 기준과 캡처 범위는 [검토 절차](../../../docs/repository/frontend-change-review-playbook.md)를 따른다.
