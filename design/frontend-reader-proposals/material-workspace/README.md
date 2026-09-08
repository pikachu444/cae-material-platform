# 소재·데이터 작업공간 검토 시안

2026-09-07 · RD-01 · **사용자 선택 전**. 실제 API·DB·업로드·모델 생성 구현이 아니다.

위 문장은 작성 당시의 상태다. 이후 큰 화면 구조를 구현 기준으로 삼기로 했으며, 최신 결정은
[UI 원칙](../../../docs/product/frontend-ui-principles.md)을 따른다. 비교를 위해 원본 HTML/CSS/JS는 그대로 보존한다.

## 새 태스크에서 시안 다시 열기

- 로컬 주소: <http://127.0.0.1:8767/index.html>
- 원본 폴더: `C:\SourceCodes\cae-material-platform-rd02\design\frontend-reader-proposals\material-workspace`
- 현재 코드 작업 폴더: `C:\SourceCodes\cae-material-platform-rd02`, branch `codex/rd02-connected-reader`.
- 시안은 브라우저만 있으면 실행된다. Codex 시각화 도구, API, DB가 필요하지 않다.

서버가 꺼졌으면 PowerShell에서 다음을 실행한 뒤 위 주소를 브라우저로 연다.

```powershell
python -m http.server 8767 --bind 127.0.0.1 --directory C:/SourceCodes/cae-material-platform-rd02/design/frontend-reader-proposals/material-workspace
```

이 PC에서는 `python` 대신 `C:\Program Files\Python313\python.exe`를 사용할 수도 있다.
이미 8767이 실행 중이면 먼저 그 주소를 확인하며 중복 서버를 시작하지 않는다.
다른 폴더에서 이어받았다면 `--directory`만 해당 원본 폴더로 바꾼다.
종료는 서버 터미널에서 Ctrl+C다. 8767은 시안, 5174는 실제 API 연결 화면으로 구분한다.

예를 들어 소재 카드는 `index.html?scope=materials&view=tiles`, 실험 표는
`index.html?scope=tests&view=table`로 열 수 있다. 화면의 검색·선택·패널 상태는 URL로 복원한다.
이전 비교안들은 상위 폴더에 보존되어 있으며 현재 대표 시안과 구분한다.

태스크 전환 전 원본 파일을 별도로 묶어 두었다:
`C:/Users/pikac/.codex/backups/cae-material-platform/rd02-recovery-20260908/material-workspace-reference-20260908.zip`.
같은 이름의 JSON에는 파일 해시와 실행 원본 비교 결과가 있다. 다른 PC에서는 이 로컬 백업도 함께 옮겨야 한다.
현재 파일은 main에 아직 반영되지 않은 작업이므로 브라우저 주소나 태스크 이름만으로 인계하지 않는다.

[화면 열기](index.html) · [규칙 정리안](governance/README.md) · [전체 계획](../../../docs/planning/frontend-redesign-program.md)

## 확인할 업무

첫 화면에서 소재를 한 번 선택하면 오른쪽에 물성과 연결된 자료가 나온다. 소재는 카드/표를 전환한다.
실험 목록은 온도·속도·시편·방향을 별도 열로 비교한다. 확대 상세나 더블클릭/Enter로 목록을 감추고,
목록 보기로 돌아오면 페이지·검색·선택·스크롤·초점을 되찾는다. 미리보기 접기는 선택을 지우지 않는다.
좁은 화면에서는 아래로 쌓지 않고 미리보기로 전환하며 목록 복귀 버튼을 제공한다.

상단 **실험 데이터**, **솔버 카드**는 소재를 먼저 선택하지 않아도 들어갈 수 있다.
SC-ST-001의 저장된 합성 카드 파일을 처리·모델 생성을 거치지 않고 내려받는다. 파일이 없는 항목은
다운로드를 막고 이유를 보여준다. 소재 연결을 곧 카드의 실제 입력 실험 목록이라고 표현하지 않는다.

실험을 복수 선택하거나 처리·통계 메뉴를 열면 반복 실험 처리 예시를 확인한다.
계산 전, 계산 후 저장 전, 입력 변경 후 이전 결과, 브라우저 탭에 저장됨을 구분한다.
처리 데이터 CSV와 솔버 카드 파일은 별개다. 등록 화면은 파일 선택 이후 확인할 단계를 보여주는 흐름 검토에 한정한다.

## 설계 기준과 범위

- [Altair 공식 안내](https://help.altair.com/altairone/topics/materialsdb/tutorial_amdc_interface_r.htm)의 소재별 물성 타일·오른쪽 정보 패널을 참고했다. 자료 항목을 정렬하고 실제 트리와 별도 조건 필터를 제공한다. 로고·화면 자산을 복제하지 않았다.
- 차분한 좌측 메뉴, 회색 구분선, 파란 선택/실행 강조, 숫자 정렬, 단위 열을 공통 기준으로 쓴다. 긴 소재명은 줄바꿈하고 조건을 제목에 몰아넣지 않는다.
- 24개 소재, 96개 실험, 12개 카드 metadata와 한 개 합성 native 파일이다. 페이지당 12개를 표시한다. 대규모 성능을 입증하는 fixture가 아니다.
- 합성 곡선과 단순 선형 보간은 화면 검토를 위한 계산이다. 151점, 온도·속도별 묶음, 평균·표준편차 표기는 생산 기본값이나 검증된 통계 정책의 승인이 아니다.
- 소재 수정 리비전만 표시한다. 다른 자료의 버전 이력을 새로 만드는 기능은 없다. stable ID 연결, 입력 목록, 실제 파일·설정의 의미는 보존 대상이다.
- 저수준 SVG는 이 독립 시안에 한정한다. 운영 차트 라이브러리 선택을 바꾸거나 자체 차트 엔진을 제안하지 않는다.

Main이 이 폴더만 작성한다. 기존 6개 비교안, apps/web, apps/web-next, 개인 설정, 활성 AGENTS/skill/hook은 이번 작업에서 수정하지 않는다.
허용된 문서 수정은 이 시안의 상태와 다음 단계를 기존 planning 문서에 정확히 반영하는 것까지다.

## 검증

`node design/frontend-reader-proposals/material-workspace/verify.mjs`

결과는 `.artifacts/material-workspace-review/`에 기록한다. 화면 원본과 영역별 원본 픽셀 crop을 확인한다.
1366×768, 1440×900, 1920×1080, 2560×1440, 3840×2160 CSS viewport와 좁은 화면을 검사한다.
실제 API 지연·권한·영구 저장·재시도, 실제 데이터와 공학적 오차, Windows 물리 4K/배율 가독성은 별도 구현 검증 대상이다.
상세 결과와 남은 결정은 [완료 보고서](review-result.md)에 기록한다.
