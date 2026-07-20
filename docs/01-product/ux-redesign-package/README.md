# CAE Material Platform UX Redesign Package

이 디렉터리는 현재 프론트엔드를 검색 중심 제품으로 재설계하기 위한 목표, 조사 근거, 실행계획, 수용 기준과 Codex 지시문을 포함한다.

핵심 방향은 다음 두 가지다.

1. 기존 재료를 검색하고 검토한 뒤 CAE solver card를 내려받는 흐름을 기본 경로로 만든다.
2. 필요한 재료 또는 solver card가 없을 때만 시험 데이터를 업로드하여 처리·보정·카드 생성 흐름으로 진입한다.

## 파일 구성

- `00_UX_REDESIGN_GOAL.md`: 제품 목표, North Star workflow, 정량 수용 기준
- `01_RESEARCH_EVIDENCE_AND_COLLECTION.md`: 저장소 진단, 참고 제품 근거, 추가 자료 수집 계획
- `02_UX_REDESIGN_EXECUTION_PLAN.md`: 문서·정보구조·디자인 시스템·화면별 구현 순서
- `03_UX_ACCEPTANCE_CRITERIA.md`: 사용자 시나리오와 품질 게이트
- `04_CODEX_MASTER_PROMPT.md`: Codex 구현 지시문
- `05_REFERENCE_SOURCES.md`: 공식 공개 자료와 저장소 내부 근거

Codex 작업 시작점은 저장소 루트의 `CODEX_UX_REDESIGN_START.md`다.

## 구현 원칙

- 백엔드 domain, revision, provenance, processing, fitting과 exporter는 보존한다.
- 내부 개념을 삭제하지 않고 일반 사용자 기본 화면에서 숨긴다.
- 검색·상세·카드 다운로드 경로를 가장 먼저 완성한다.
- Modeling은 `Data | Process | Fit | Export`로 단순화한다.
- CSS 장식 변경만으로 완료 처리하지 않는다.
- 각 단계는 실제 사용자 task와 screenshot으로 검증한다.
