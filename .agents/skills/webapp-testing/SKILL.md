---
name: webapp-testing
description: Reproduce and verify local web workflows with the installed Playwright environment, including downloads, read-back, keyboard focus and error recovery.
license: Complete terms in LICENSE.txt
---

# 웹 앱 재현과 검사

Anthropic skills의 webapp-testing에서 시작한 로컬 관리본이다. 라이선스와 기존 helper/example은 보존한다.

- 앱의 README·package.json·설치된 Playwright 환경과 대상 계약을 먼저 확인한다. Node/Python 중 저장소의 해당 검사와 맞는 환경을 사용한다.
- 필요한 소스와 DOM을 읽어 사용자 경로를 선택한다. 모든 페이지에서 networkidle을 기다리지 않는다. 해당 요소·응답·계산 완료 등 관찰 가능한 준비 상태를 기다린다.
- 현실적인 주요 업무 하나와 영향받는 오류·복구 사례를 검사한다. 실패 시 환경·앱·테스트 원인을 구분한다.
- console/page 오류, 키보드·초점, 실제 다운로드 bytes, 저장 후 새로고침/재조회, 목록 복귀와 이전 결과 상태를 확인한다.
- 합성 응답은 시안/분리 검사로 표시한다. 실제 API·권한·영구 저장 검사를 대신하지 않는다.
- 캡처는 [시각 매트릭스](../../../docs/product/visual-acceptance-matrix.md)의 해당 범위를 따른다. 실행 명령·URL·fixture·viewport·결과와 한계를 기록한다.

기존 서버 helper가 필요하면 `scripts/with_server.py --help`로 사용법을 확인한다. 수정/진단이 필요하면 소스를 읽는다.
기존 예제의 고정 대기나 단순 selector는 설명용이며 공통 실행 규칙이 아니다. 사용한 브라우저와 직접 시작한 임시 서버의 종료 책임을 구분한다.
저장소의 Python 제품 캡처는 `uv run --with playwright==1.62.0 python scripts/capture_current_product.py`를 사용한다. Node 앱 검사는 설치된 lockfile을 따른다.
