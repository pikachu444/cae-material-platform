# 프론트엔드 개편 — 현재 상태와 다음 작업

## 최신 전달 범위 — 2026-09-08

이번 전달은 누적된 새 조회 화면(RD-02), frontend 기반, 규칙 정리와 시안 원본 보존이다.
**사용자의 최신 지시: 커밋·push·PR 생성까지만 진행한다. 내용을 보고한 뒤 멈춘다.
사용자 승인 후 병합하고 다시 대기한다. 포크와 다음 구현은 그다음 지시를 받아 시작한다.**
이전 기록의 자동 병합·연속 포크 지시는 이 순서로 대체한다.

이번 상세 화면 정리에서는 소재·실험·처리 결과·모델·카드·연결 모델의 UUID, 해시,
응답 전문을 나열하던 영역을 없앴다. 실제 물성·단위, 사용한 처리 설정, 적용 범위와
솔버의 변환·근사·미지원은 항목별로 남겼다. 소재 코드·소재 리비전과 솔버 내 소재 번호는
사용자가 판단할 정보다. 다운로드할 원본 파일 내용은 바꾸지 않았다.
점탄성 및 초탄성 카드와 연결 모델은 Prony 계수와 완화 시간을 표로 보여준다.

독립 검수에서 발견한 neutral 카드 목록 링크 오류와 Prony 계수 누락을 수정하고 재검수 v4에서 approve를 받았다.
긴 문자열을 진단용 접기 안으로 옮기는 것으로 끝내지 말고, 실제 공학 값은 정상 상세에 표시한다.
이 기준은 UI 원칙·개발 지침·시각 매트릭스·ADR-0038·사용자 가이드에 함께 반영했다.

현재 작업: `C:/SourceCodes/cae-material-platform-rd02`, `codex/rd02-connected-reader`.
기준 main은 `4c545ea18322769b25d67177d609e3eb14202666`이다. PR의 최종 커밋·검사·병합 상태는
해당 PR에서 확인한다. 로컬 검수 원본은 `.artifacts/rd02/detail-cleanup/`, 이전 연결 업무 검수는
`.artifacts/rd02/reader-finish/`와 `.artifacts/rd02/direct-fix/`에 있다.
현재 가이드에는 대표 조회 화면 20장을 보존했다. 물리 장비의 4K 가독성과 서비스 전환은 미승인이다.

다음 태스크는 [통합 계획](frontend-redesign-program.md)의 RD-04 대표 등록·처리 업무를 이어간다.
우선 기존 API가 지원하는 실험 데이터 업로드에서 저장·재조회까지 작은 연결 업무를 정하고,
그 뒤 실제 처리 설정·실행·저장 결과·다운로드로 확장한다. 반복 실험 평균화 기준은 아직 미결정이다.
소재만 리비전 관리하는 정책의 DB/API 이관, 생성 화면, 전체 기능 검증·일괄 전환·구형 삭제도 남았다.
이 PR을 전체 개편 완료로 해석하지 않는다.

시안 원본은 `design/frontend-reader-proposals/material-workspace/`에 있다.
외부 접속은 [root README](../../README.md)의 실제 앱·시안 HTTPS 주소를 사용한다.
Quick Tunnel 주소가 만료되면 README 절차로 다시 열고 두 주소를 갱신한다.
로컬 주소만으로 remote 사용자의 접근 방법을 설명하지 않는다.

## 이전 진행 기록 — 현재 권한과 다음 행동은 위 내용 기준


갱신: 2026-09-08. **RD-02 조회·다운로드가 구현되어 있으며, 사용자 화면 재검토 요청에 따라 Main이 직접 화면을 수정했다. 화면 최종 승인과 서비스 전환은 아직 하지 않았다.**

이번 조회 화면 마무리에서는 소재 표의 물성 비교, 실험 카드의 개별 조건, 솔버·단위계 필터,
선택을 유지하는 미리보기 접기, 상세 확대 후 목록 복귀, 탐색기 접기와 좁은 화면을 보완했다.
반복 helper를 정리하고 제조사·시험 방법·날짜·시편 설명 등을 항목으로 분리했다.
실제 화면 비교에서 발견한 카드 내용 잘림, 제목 정렬, 큰 화면의 조건 이름 줄바꿈과
모델 목록의 빈 도구 행을 수정했다. 처리 결과의 점 개수 정렬과 모델 목록의 실패 후 재시도도 고쳤다.
사용자가 정보를 비교하고 행동하기 쉬운지를 우선하며, 검사 통과를 화면 승인으로 대신하지 않는다.
Main 직접 검증: frontend 기존 62개와 추가 복구 검사 3개, build, 14개 browser 검사,
기존 저장본/다운로드 검사 7개와 카드→저장 모델 연결 검사가 통과했다. 이전 33장, 최종 51장과 별도 오류·긴 이름·좁은 화면의 근거는
`.artifacts/rd02/reader-finish/`에 있다. 독립 검수는 두 지적을 수정한 뒤 approve를 받았다.
사용자 화면 승인은 남아 있다.
현재 사용자 가이드의 RD-02 화면 20장을 이번 구현으로 갱신했다.

후속 피드백의 네 캡처에 따라 트리의 코드·건수, 이름 없는 소재 상태 단계, 카드의 부제·설명·리비전,
메뉴 소개와 반복 제목을 제거했다. 물성·단위·적용 온도는 항목으로 유지하고 소재 코드·리비전은
소재 정보에서 확인한다. 근거는 `.artifacts/rd02/copy-cleanup/`에 있다.
외부 테스트용 Quick Tunnel 및 Access 절차를 root와 `apps/web-next` README에 추가했다.
외부 터널은 이후 아래 Docker 방식으로 열었으며 외부 화면과 API 응답을 검증했다.

후속으로 사용자가 실제 임시 도메인 발급을 지시했으나, 2026-09-08 자동 실행 정책이
cloudflared 다운로드·실행·터널 시작 명령을 차단했다. 이를 전체 발급 불가로 잘못 판단했다.
사용자가 기존 README의 Docker 방식을 지적한 뒤 기존 이미지를 확인해 시안과 실제 앱의 터널을 생성했다.
현재 외부 주소와 재발급·갱신 방법은 root README에 있다. 외부 HTTPS의 시안 HTML·JS, 실제 앱·API에서 200 응답을 확인했다.
시안 주소는 `http://127.0.0.1:8767/index.html`, 원본은 `design/frontend-reader-proposals/material-workspace/`다.
이 폴더 README에 재실행·새 태스크 인계 방법과 별도 ZIP 백업을 기록했다.
최초 개편 계획 전체는 미완료다. RD-02 대표 조회 기능 구현과 일부 RD-03 검증까지 진행했고,
RD-04~07의 새 등록·처리·생성 화면, 확장·일괄 전환·구형 코드 삭제는 남아 있다.

현재 작업 폴더는 `C:/SourceCodes/cae-material-platform-rd02`, 브랜치는
`codex/rd02-connected-reader`다. 아래의 d0b9 경로와 완료 판정은 이전 작업 기록이다.
작업 중 앱 내부 워크트리가 사라져 Git에 남은 작업 트리
`5721e2e037bf93b1ac4ebd1943ce8c6b3d4e136d`를 복구했다. 원래 staged 내용과 일치하는 것을
확인한 뒤 이번 수정만 다시 적용했다. main과 다른 작업 브랜치는 변경하지 않았다.

이번 수정은 미리보기 머리글·물성 표·실험 목록 열·곡선 축·다운로드 위치와 공통 CSS에 한정한다.
API, 저장된 입력 관계, 다운로드 bytes와 공학 계산은 보존한다. 검증 기록과 전후 화면은
`.artifacts/rd02/direct-fix/`에 있다. 기존 독립 검수의 통과를 이번 화면 승인으로 대신하지 않는다.
등록·처리 실행·평균화·모델 생성과 일괄 전환은 다음 단계로 남아 있다.

## 이전 RD-02 진행 기록 — 현재 상태는 위 요약 기준

- 현재 구현 위치는 `C:/Users/pikac/.codex/worktrees/d0b9/cae-material-platform`이며 base/HEAD는
  `4c545ea18322769b25d67177d609e3eb14202666`, branch는 `codex/rd02-connected-reader`다.
  처음 detached 상태에서 현재 변경을 보존한 채 분기했다. 원본 redesign 폴더는 수정하지 않았다.
- `frontend-continuation-v2`의 base/head와 세 checkpoint 순서를 확인하고 committed/pending patch를
  3-way 적용했다. ZIP 44개 SHA-256을 검증했으며 미추적 19개는 길이와 추출 후 hash도 확인했다.
  두 문서의 CRLF/LF 차이 외에 backlog는 최신 #391/#397 행을 함께 보존했다.
  API 문서에는 개편 정책과 최신 HTTP `0.41.0`/DMA 호환성 본문을 함께 유지했다.
  이관 직후 backend 및 machine-readable contracts의 main 대비 변경은 없다.
- [현재 구현·검수 범위](rd02-connected-reader-packet.md)는 RD-02 실제 조회·다운로드와 구조적
  확장성을 함께 다룬다. Full 경로의 요구 검수 후 단일 구현자, Main 실환경 검증, 독립 검수를 수행한다.
  개인 오케스트레이션·모델/effort·hook 설정은 변경하지 않는다.
- 기존 live 화면은 API 미연결 상태다. 다섯 viewport의 전 화면을 `.artifacts/rd02/before/`에
  기록했다. 기존 합성 화면을 실제 연결 검증으로 사용하지 않는다.
- 추가 사용자 요구는 app/features/shared 의존 방향, 상태·CSS 소유권, 공학 component 경계,
  도구 선택 근거와 대표 확장 사례를 구현·독립 검수·인계에 포함하는 것이다.
- 첫 Test Data 경로를 실제 1920 화면에서 먼저 비교했다. 그래프의 실제 비균일 x 좌표와 단위,
  JSON 1,959 bytes 일치, 확장·복귀를 확인했다. 빈 미리보기 영역·Enter·복귀 초점·전체 스크롤
  결함은 같은 수정 담당자가 보완했고 중간 재검증을 통과했다. 결과 영역의 스크롤 복원과
  tree/filter·관계·다른 조회 화면·신규 회귀·최종 viewport 검수는 계속 진행 중이다.
- 실제 PostgreSQL application role에서 Test Data 전용·카드 전용·두 권한·무권한·다른 프로젝트의
  읽기 격리를 확인했다. 모든 transaction은 rollback했으며 HTTP 데모 사용자 권한 조합을
  검증한 것으로 해석하지 않는다. 화면의 부분 권한 거절은 별도 검증 대상이다.
- 실제 화면의 실험 → 처리 결과 두 개 → 정확한 모델 → 해당 카드 13개 → native 다운로드는
  통과했다. 별도 neutral 모델 경로와 화면 원본의 트리·필터·내부 정보 노출·빈 미리보기 영역은
  [C2 보완 범위](rd02-correction-packet-c2.md)에 묶어 같은 수정 담당자가 마무리한다.
- 정상 생성 경로 검증 후 격리 합성 실험의 온도를 23°C에서 24°C로 새 저장본에 기록했다.
  기존 처리 결과에는 이전 입력 상태가 나타났고, 이전 저장본의 실험·처리 JSON과 native 카드는
  기존 bytes와 같았다. 이 fixture는 재초기화하지 않으며 저장 결과의 링크는 이전 입력을 유지한다.
- 확장 검수 사례는 선택 실험 → 처리 설정 → 실행·비교 → 저장·재조회·처리 데이터 다운로드다.
  이번에는 처리 화면을 선구현하지 않고 reader 입력 전달과 processing의 초안·결과·복구 소유권을 검토한다.
- Docker 시작 실패는 접근 불가능한 임시 소켓 디렉터리를
  `C:/Users/pikac/AppData/Local/Docker/run.rd02-preserved-20260907`로 보존 이동해 복구했다.
  기존 볼륨은 유지했고, 이전 경로의 중지 컨테이너는 증거에서 제외했다.
  canonical Compose 설정으로 `cmp-demo-test-rd02-20260907`의 격리 환경을 새로 빌드했다.
  8000번은 별도 httpd가 사용하므로 API만 18000번을 사용하는 effective config를 기록했다.
  기존 preflight validator로 해당 project/config/workdir/image/health/port를 검증해 통과했다.
- 요구 검수 v3의 정확한 저장본 조회·카드 직접 목록·페이지 범위·관계 구분·권한 독립성·화면 오류 상태
  지적을 v4에 반영해 approve를 받았고 단일 구현자가 작업 중이다.
- 실제 PostgreSQL의 기본 합성 corpus는 소재 3개·실험 16개·저장 처리 결과 3개다. RD-02에서
  기존 입력/설정을 사용한 별도 직접 처리 결과 1개와 모델·native 카드 13개를 추가해 목록 검증을 준비했다.
  recipe-aware v1.3 모델의 기존 탄소성 exporter 거절과 neutral 경로 지원은 그대로 보존했다.
  실제 사용자 토큰으로 실험 JSON 1,959 bytes, 처리 JSON 64,422 bytes, native 카드 5,094 bytes를
  내려받아 서버 hash와 비교했다. 이는 backend 기준값이며 아직 새 UI acceptance 결과가 아니다.
- 첫 backend checkpoint를 격리 API에 재빌드했다. 실험·처리 결과·탄소성 카드의 정확한 저장본 조회,
  없는 저장본의 404, 처리 JSON/native bytes 일치를 확인했다. 기존 네 카드 종류와 neutral 카드
  8개도 실제 지정 저장본 조회·다운로드를 통과했다. 새 통합 카드 목록은 neutral 저장 테이블의
  없는 컬럼 참조로 500이 발생했으며, 알려진 neutral 스키마/모델 분류 누락과 함께 진단을 기록했다.
  이 목록에 의존하는 화면 검증은 수정 후 수행한다. 초기 구현은 진행 중이며 최종 독립 검수는 대기 중이다.
- 후속 index checkpoint는27개 전체 목록과6종 대표 링크를 실제 API에서 조회했다. 마지막
  generalized-Maxwell 분류는 source에 반영됐고 다음 image에서 재검증한다. 초기 UI의 실험 JSON과
  native 다운로드는 기준 bytes와 같았다. 그러나 승인한 workspace 구성·확대/복귀·관계 탐색이
  누락됐고, 카드 URL pin을 current로 바꾸는 동작과 배열 순서로 그리는 곡선도 확인했다.
  Main은 초기 writer를 중지하고 [C1 보완 범위](rd02-correction-packet.md)를 canonical correction
  writer 한 명에게 넘겼다. 전체 화면 증거와 사용자 가이드 승격은 이 실패를 해결한 뒤 수행한다.

아래 원본 위치와 과거 검사 기록은 이관 출처다. 현재 RD-02 완료 증거와 구분한다.
전체 범위는 [개편 계획](frontend-redesign-program.md), 화면 기준은 [UI 원칙](../product/frontend-ui-principles.md), 규칙 변경 이유는 [ADR-0038](../../adr/0038-development-guidance-and-reader-baseline.md)에 있다.

## 이어받을 전체 목표

- 공학용 서비스다. 실험 조회·기존 솔버 카드 조회/다운로드가 우선이다. 물성은 항목·값·단위·조건으로 읽는다.
- 소재 정보 수정만 리비전 관리한다. 다른 데이터는 안정적인 ID·저장된 연결을 사용한다. raw·처리 결과·모델·카드를 구분하며 이름 변경으로 관계를 깨지 않는다. 실제 DB/API 이관은 아직이다.
- 왼쪽 업무 메뉴·소재/시편 트리·별도 필터, 중앙 카드/표, 오른쪽 미리보기·확대 상세·목록 복귀를 구현 기준으로 삼는다. 필터 항목·열·문구·패널 폭·시각 세부값은 조정 가능하다.
- 실험/카드는 소재 선택 없이 직접 연다. 관련 소재 카드와 실제 생성 입력 관계를 혼동하지 않는다. 저장된 처리 데이터 다운로드와 솔버 카드 다운로드를 구별한다.
- 외부 primitive/data/form 도구를 검토해 활용한다. 검증된 계산·단위·출력 로직은 UI와 함께 폐기하지 않는다. 과도한 helper·설명·공통 framework를 만들지 않는다.
- 최소 기반 → 연결된 대표 업무 → 검증 → 등록·처리·모델/솔버 확장 → 검증 후 일괄 전환 → 구형 코드 삭제 순서다.

## 이번에 적용한 규칙

루트/앱 AGENTS, 공통 frontend 지침, architecture/UI principles, ADR index와 후속 결정, T/Q 적용 범위, 검토 양식·playbook, 프로젝트 skill을 정리했다.
기존 FE roadmap은 원문을 보존한 reference로, 초기 ADR 개요는 실제 파일 번호와 다른 역사적 번호로 표시했다.
두 외부 skill은 출처·라이선스를 유지한 로컬 관리본으로 전환했다. 개인 오케스트레이션·프로필·모델/effort·hook 설정은 변경하지 않았다.

사용자는 오케스트레이션의 비용 절감 목적을 설명하고 후속 논의를 요청했다. 고급 모델의 명세 작성과 낮은 비용 모델의 구현을 나누는 가능성을 유지한다. 이번 정리를 Main 직접 수행 영구 정책이나 저비용 모델 위임 폐기로 해석하지 않는다.

## 코드와 검증의 실제 상태

- [소재 중심 시안](../../design/frontend-reader-proposals/material-workspace/index.html): 24개 소재·96개 실험·12개 카드 metadata 및 합성 파일. 선택/접기·카드/표·트리/필터·페이지/초점 복귀·다운로드·이전 결과 차단·다섯 viewport 검사와 독립 검수 완료. 실제 API·물리 4K·공학 qualification은 미검증.
- [이전 제출 보고서](../../design/frontend-reader-proposals/material-workspace/review-result.md)와 governance 초안은 적용 전 판단 기록으로 보존한다. 현재 적용 여부는 이 상태 문서와 ADR-0038을 따른다.
- `apps/web-next`는 앞서 만든 합성 A/B React 기반이다. 이번 소재 중심 HTML은 아직 React로 옮기거나 API에 연결하지 않았다. [실행 명령](../../apps/web-next/README.md).
- 이번 변경은 문서·프로젝트 skill·manifest/skill lock이다. runtime·DB·API·production React/CSS·원래 작업 폴더는 변경하지 않았다.
- 최종 검사 결과는 아래 검증 기록에 있다. 과거 시안 검사를 이번 규칙 변경의 증거로 재사용하지 않는다.

## 작업 위치와 보존할 변경

작업 폴더: `C:/SourceCodes/cae-material-platform-redesign`, branch `codex/frontend-redesign`.
base `6abddd25b9ef8e7f2e0a8d112feaf3846996379b`, HEAD `4147635284f1c781db7b6d3380e6c7f713a3dbe9`.
로컬 3개 checkpoint: `c8d33d56` 데이터 정책/규칙, `9539bcad` 분리된 React 기반, `41476352` 여섯 비교 시안.
**원격에는 redesign branch가 아직 없다.** 이후 Granta/소재 중심 시안·계획 문서·이번 규칙 정리는 미커밋이다. 전체 상태를 확인하고 보존한다.
기본 폴더 `C:/SourceCodes/cae-material-platform`는 이제 clean main `4c545ea18322769b25d67177d609e3eb14202666`이다. #392 백엔드만 PR #397로 병합했고 실패한 UI branch는 로컬·원격에서 정리했다. 새 frontend 자산은 위 redesign 폴더에 그대로 보존되어 있다.

이번 적용 전 원본·hash와 worktree 조사 결과는 `.artifacts/governance-application/`에 있다. commit/push/PR/merge·브랜치/worktree 삭제는 이번에 수행하지 않았다.

## 로컬·원격 정리 판단

2026-09-07 fetch/read-back 기준: worktree 10개, 로컬 branch 7개, 원격 branch 4개(main 포함). 원격은 branch를 저장하며 로컬 worktree 폴더를 갖지 않는다.

| 대상 | 확인한 상태 | 판단 |
| --- | --- | --- |
| 기본 폴더 / main | PR #397 백엔드만 병합, clean `4c545ea1` | 정리 완료; 이전 issue-392 branch 로컬·원격 삭제 |
| redesign 폴더 / frontend-redesign | 로컬 3 commit과 미커밋 시안/규칙 | 다음 구현에 사용, 보존 |
| issue-394 폴더 | 미커밋 9개(CI/검사 수정) | 보존·해당 작업 확인 |
| Codex worktree `530e` | main에 포함된 HEAD지만 미커밋 137개 | 반드시 보존; merged 여부만으로 삭제 금지 |
| Codex worktree `cbaa` | 실패한 미커밋 62개 백업 후 취소, clean main `4c545ea1` | DMA UI 작업 철회 완료; 다른 미커밋 작업과 구분 |
| 381-docs / codex/381-doc-cleanup | PR #395는 merged지만 마지막 문서 commit `6ff249f6`은 main 미포함 | 두 문서 변경 확인 후 통합/보존 결정 |
| issue-391 / codex/issue-391-dma-tts-backend | clean, PR #396 merged, HEAD는 main 조상 | local/remote branch와 폴더 정리 후보; ignored 자료 확인 후 삭제 결정 |
| Codex worktree `5fb0` | main 동일 HEAD, clean, ignored 없음 | 가장 단순한 정리 후보; 연결 태스크 사용 여부 확인 |
| issue392-before / Codex `e8b9` | clean, main 포함 HEAD, ignored 산출물 존재 | 비교/증거·환경 사용 여부 확인 후 정리 후보 |

실제 삭제 전에는 status·현재 사용 태스크·ignored 파일·미병합 commit·remote SHA를 다시 확인한다. 폴더 삭제와 local/remote branch 삭제를 구분한다. 정리 목적만으로 강제 삭제하거나 진행 중인 작업을 숨기지 않는다.

## 다음 태스크의 업무

1. 이 폴더의 AGENTS → 이 상태 문서 → 계획의 RD-02 → 관련 API/권한/화면 계약 순서로 읽는다. 새 태스크의 기본 cwd가 다르더라도 실제 편집 폴더를 먼저 확인한다.
2. 현재 소재 중심 대표 화면을 `apps/web-next`의 필요한 최소 영역에 옮기고, 실험 직접 조회·상세·명시적으로 관련된 기존 카드·native 다운로드를 실제 API로 연결한다. 독립 카드 진입도 제공한다.
3. 이미 연결된 소재/시편을 반복 선택하게 하지 않는다. 조건·단위·원본/결과·카드 적용 범위·실제 관계를 확인하고 서버의 미지원 범위는 명시한다.
4. 늦은 요청/선택 변경, 검색/페이지/초점 복귀, 권한 거절, 파일 없음/미지원, 다운로드 bytes를 검증한다. 실제 서버 저장 객체를 재조회한다. 공학 계산이나 광범위 DB 이관을 이 조회 단위에 섞지 않는다.
5. 기존 v1에만 있는 revision 키가 필요하면 typed adapter에 명시적으로 격리하고, 새 UI 편집 이력으로 노출하거나 stable ID를 revision으로 추정하지 않는다. API 부족은 backend의 최소 계약 단위로 분리한다.
6. prototype 검사와 실제 API 검사를 구분하고, 첫 연결 reader의 다섯 viewport와 실제 데이터 규모를 확인한다. 속도·조작 횟수는 측정 후 목표를 제안한다.

다음 태스크는 최신 main의 별도 worktree에서 시작하고, 원본의 3개 checkpoint와 미커밋 44개를 검증된 스냅샷으로 가져온다. `docs/architecture/api-events-jobs.md`와 `docs/planning/backlog.md`는 DMA backend와 겹치므로 양쪽 변경을 병합한다. 원본 redesign 폴더는 보존하며 새 worktree 한 곳에서만 구현한다.

그다음 등록·처리·반복 통계의 저장/재조회/다운로드, 모델·솔버·Activity·Administration을 확장한다.
통계의 동일 조건 묶음·공통 구간·파단 처리·허용오차는 실제 예시와 추천안을 준비해 해당 단계에서 결정한다.
전환은 검증 후 한 번에 수행하며 기존 build·데이터 보존·이관/복구를 확인한 뒤 구형 코드와 dependency를 제거한다.

## 최종 검증 기록

- 문서 분류·영향·게시 검사 회귀: 253개 통과. 실제 manifest의 reference/current authority 경계 5개 확인.
- user-guide: 21개 가이드·158개 current capture·186개 분류 MD·2733개 링크 통과. docs-impact: 브랜치 누적 230개 변경 경로·production visual source 0개 통과. diff 검사 통과.
- 프로젝트 skill 4개 validator 통과. Windows 기본 cp949로 UTF-8 본문을 읽던 검사 환경 오류는 `python -X utf8`로 해결했다. 전역 설정은 바꾸지 않았다.
- hook 직접 smoke: 일반 read-only 명령은 통과, 잘못된 payload는 deny. 실제 Codex 이벤트에서의 발화/중복 실행 시간은 아직 측정하지 않았다. hook·CI·개인 모델 설정은 유지했다.
- 독립 검수에서 지적한 frontend-ui skill 라이선스 누락을 upstream MIT 원문으로 보완했고 교정 재검수에서 approve를 받았다. 해당 변경의 출처와 hash는 application-evidence.json에 있다.
- 기존 시안 파일 90개는 작업 전 hash와 일치한다. 새 화면/계산/DB 변경이 없어 이번 단위의 브라우저·Compose·공학 검사는 N/A다.
- 사용자는 DMA 정리 후 원래 작업을 계속 완수하도록 재확인했다. 새 태스크는 최신 main의 worktree에 보존한 시안·규칙을 이관해 시작한다. 기본 main에만 있는 파일로 구현을 시작하지 않고 스냅샷의 누락·충돌 확인을 먼저 한다.

## DMA 정리 결과와 새 구현의 출발점

- PR #397: backend/support 29개 경로만 main `4c545ea18322769b25d67177d609e3eb14202666`에 병합. apps/web·시각 자료·개인/저장소 지침의 main 대비 변경은 0개다. 사용자 가이드 한 문단은 API 지원 범위와 UI 미완료 상태만 교정했다.
- 구형 TTS metadata에 추천 정보가 없어도 원본 bytes/hash를 바꾸지 않고 read/Fit 가능한 회귀를 보완했다. 독립 검수 approve, backend 104개·계약 628개, Linux/Windows CI 통과. Linux에서 DMA PostgreSQL 8개 실행을 확인했다.
- 실패 작업 복구본: `C:/Users/pikac/.codex/backups/cae-material-platform/dma-ui-retirement-20260907T083150Z`. frontend 이관본은 그 아래 `frontend-continuation-v2`다.
- #392·#195는 frontend/전체 프로그램 완료로 닫지 않았다. #392·#195·#117에 PR·merge SHA·다음 우선 업무를 기록했다. #394·530e·381 등 다른 작업은 정리 범위에 포함하지 않았다.

## RD-02 현재 구현 검증 (2026-09-07)

`codex/rd02-connected-reader`의 보존 이관본에서 Materials/Test Data/Processing Outputs/Models/Solver Cards
실제 reader를 연결했다. 사용자 지시에 따라 Main이 남은 구현과 교정을 직접 소유했고 기존 writer는 중단했다.
27개 카드·6개 API source family를 읽으며 일반 목록은 실제 모델 계열로 묶는다. 소재 속성의 값·단위·적용 조건,
실험 계층, 선택/상세/복귀, 정확한 저장 관계와 세 종류 다운로드를 실제 격리 API에서 검증했다.
원본 변경 뒤 과거 입력과 결과의 bytes는 유지된다. 새 등록·처리 실행·통계·생성 기능 및 일괄 전환은 다음 범위다.

이전 기능 검증은 프런트엔드45개·backend 관련52개·계약 검사 및 당시 화면 증거로 남겼다.
해당 시각 판정은 아래 재교정 결과로 대체한다. 최소·최대12개 부정 상태,
1366 로컬 스크롤·키보드 접근, 실제 원본/결과/native 다운로드 검증을 남겼다. 상세 기록은 로컬
`.artifacts/rd02/main-acceptance.md`, 최신 화면은 `docs/user-guide/images/current/rd02-*`다.
독립 완성본 검수와 문서 최종 게이트 결과는 아래에 동기화한다. 오너 시각 승인·물리적4K 가독성은 아직
확정하지 않았다. commit/push/PR/merge/전환은 하지 않았으며 #392·#195·전체 개편을 완료로 닫지 않았다.

IR/Neutral JSON과 공통 입력→솔버 출력은 frontend·backend 공동 후속 설계 검토다. 현재 확인된
CSV/TSV/XLSX 공통화 adapter, 모델 IR을 감싼 교환 JSON, 기존 solver renderer 재사용과 여러 모델 API
호환 분기는 RD-02에서 유지했다. 모델의 기준 데이터/identity와 중복 동기화·독립 저장 필요성,
각 단계의 계약 및 불필요한 생성 단계 여부를 함께 검토하고, 저장 객체 변경에는 원본·산출물·계산
동등성을 입증하는 이관 검증을 요구한다. API/DB 개선을 금지하지 않으며 현재 완료로 보고하지 않는다.


### RD-02 시안 일치 재교정 — 로컬 구현·독립 검수 완료

이전 독립 approve는 저장 조회·기술 검사를 통과했지만 승인 시안과의 직접 비교를 충분히 검증하지 못했다.
사용자가 시안 불일치와 영어 UI를 지적하여 해당 시각 완료 판정을 대체하고 Main이 직접 교정했다.
승인 material-workspace의 한국어·업무 rail·scope·필터·결과·preview 구조와 실제 1920 화면을 비교하고,
같은 독립 검수자가 수정본을 다시 검수하여 2026-09-08 approve했다. 로컬 구현·검수 범위가 완료됐다.

참조와의 필요한 계약 차이: canonical 목록에는 저장된 온도·기타 수치 조건과 시편·원본 파일을 노출한다.
속도·문자 방향은 testing 조건에 존재하지만 canonical의 exact 저장 입력으로 연결하는 공통 요약 계약이
아직 없다. 현재 context를 무조건 join하거나 파일명에서 추론하지 않는다. RD-04 공동 데이터 검토에서
이 연결을 다루며, 모든 조건 열 지원 완료라고 보고하지 않는다.

현재 Neutral 구현은 단순 serializer만이 아니다. 별도 neutral ID와 revision 및 물성 저장 경로가 있으며
승격 시 embedded model ref도 새 ID를 사용한다. IR/교환 envelope 설명은 통합 방향이며 현재 저장 identity가
이미 하나라는 뜻이 아니다. 기준 모델 identity·중복 저장·동기화와 이관 동등성은 공동 후속 검토 대상이다.

승인 material-workspace 원본의 한국어·rail·scope·검색/필터·결과·미리보기 구성을 직접 포팅했다.
Root는 소재 카드를 제목/상태·물성 행·적용 조건 푸터로 직접 고쳐 반복 helper를 제거했고,
Main은 모델 목록의 정확한 소재 상태·저장 시각과 독립 숫자 열을 연결했다. 단위 변환은 표시만 바꾼다.
현재 프런트엔드53개(19파일), typecheck·build가 통과했고 API 조건/파일 요약 영향10개와 계약 검사를 통과했다.
실제 과거 입력·처리 결과·native 카드의 세 다운로드 bytes는 동일하다. 검색 초안/Enter검색/복귀초점,
1366 목록 내부 스크롤 및401 재연결 경계도 검증했다.
최신 화면은 `.artifacts/rd02/fidelity/verified` 정상20원본/81crop과 `supplement` 추가20원본/75crop,
`negative` 최소·최대12원본이다. guide20원본과 manifest145를 갱신했고 사용자 가이드·문서 영향 검사는 통과했다.
동일 독립 검수자의 최종 판정은 approve이며 잔여 blocking finding은 없다. 오너 승인·물리적4K·전체 개편 완료 또는 publication을 주장하지 않는다.

스크롤바가 보이지 않던 증거는 Playwright headless의 `--hide-scrollbars` 기본 인수 때문이었다.
해당 인수를 제외한 실제 기본 스크롤바로 목록·탐색기·native·소재 카드 5뷰포트20장을 확인했다.
추가했던 제품 스크롤 스타일은 제거했다. 정상 guide20원본은 수정된 캡처 설정으로 교체했으며,
기존 기능·bytes·권한 검증은 그대로 유효하다. 증거는 `.artifacts/rd02/fidelity/scrollbar/report.json`이다.

최종 독립 검수: Q01–Q05, Q07, Q09, Q15–Q16, Q19–Q20 PASS. 나머지 항목은 RD-02 외부 범위로 N/A.
정보 위계·공학 업무 흐름·반응형/와이드 화면 구성 3축을 통과했다. 가이드21문서/178캡처,
문서 영향320경로 및 diff 검사가 통과했다. #392·#195는 후속 단위와 함께 유지하며, 다음 작업은
기존 backlog 순서와 오너 우선순위를 따른다. commit/push/PR/merge는 하지 않았다.
