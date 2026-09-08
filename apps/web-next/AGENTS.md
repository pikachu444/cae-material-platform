# 새 frontend 기반 작업 지침

[공통 지침](../../docs/repository/frontend-development.md)을 따른다. `apps/web-next`는 일괄 전환 전의 임시 코드·CSS 경계다.

- 첫 업무는 실제 실험 조회와 기존 카드 다운로드다. 소재 경유와 직접 진입을 함께 지원한다.
- 화면은 [UI 원칙](../../docs/product/frontend-ui-principles.md)의 현재 대표 화면을 기준으로 구현한다. 필터 항목·열·문구·패널 폭은 조정 가능하다.
- 실제 API가 필요한 단계에서 합성 gateway 성공으로 대체하지 않는다. 현재 합성 기반과 실행 명령은 [README](README.md)에 명시한다.
- 업무가 요구하는 feature와 component부터 만든다. 빈 폴더·범용 controller·설정 framework를 선제 구축하지 않는다.
- 이 앱의 검사와 기존 앱의 guard를 구분한다. 외부 primitive·서버 상태 도구를 쓰되 검증된 계산·단위·출력 조합은 확인 후 재사용한다.
