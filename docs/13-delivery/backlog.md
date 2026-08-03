# 현재 전달 Backlog

이 문서는 남은 제품 작업의 순서, 새 Codex 작업을 나누는 기준과 읽기 경로를 관리합니다.
완료 이력은 Git과 병합된 GitHub issue/PR에서 확인합니다. 새 Codex 작업은 `AGENTS.md`, 아래
표의 첫 미완료 작업 단위, 해당 GitHub 본문 순서로 시작합니다.

## 기준선

- production React/CSS: PR #156, commit `55cfa62`
- 승인된 시각 target: PR #170, commit `7601ec8`
- #167 결과: 18 family, 13 bundle, 72/72 이미지 승인 완료
- target 선택: `docs/01-product/service-reference-inventory.yaml`
- 정확한 HTML/CSS/image/hash: `docs/01-product/service-reference-manifest.yaml`
- 자동 LLM review: #119가 열려 있는 동안 비활성

## 현재 위치

- 순서 1 `#157 깨끗한 데모 실행`은 PR #176, main `8469c03`에서 완료했습니다.
- 순서 2 `#159 Materials 검색·조회·다운로드`는 제품 소유자 확인을 거쳐 PR #177,
  main `7d67ef2`에서 완료했습니다.
- 첫 미완료 작업 단위는 순서 3 `#159 물성 데이터 등록·관리`입니다. #159는 이 작업이
  남아 있으므로 열린 상태를 유지하며, 최신 main에서 별도 Codex 작업으로 시작합니다.

#167의 승인 target은 다시 만들거나 재승인하지 않습니다. 과거 packet, correction 이미지와 완료
보고서는 working tree에 보관하지 않고 Git/PR 이력에서 조회합니다.

## 제품 목적과 우선순위

대부분의 사용자가 가장 자주 끝내야 하는 일은 **Materials에서 필요한 물성을 검색하고, 적용
조건과 출처를 확인한 뒤, 적합한 데이터나 솔버 카드를 내려받는 것**입니다. 이 흐름은 시작
화면, 일정, 화면 면적, 응답 속도와 검수에서 가장 높은 우선순위를 갖습니다.

데이터 등록·처리·모델 생성은 전문 사용자의 핵심 제작 흐름이고, 검토·승인·관리·접근 통제는
그 결과를 신뢰하고 재사용할 수 있게 하는 지원 흐름입니다. 보안과 권한 검사는 생략하지 않되,
일반 사용자의 조회·다운로드 화면을 복잡하게 만들거나 제품 일정의 중심을 대신하지 않습니다.
내부 ID, 해시값, 구현 상태명과 개발 용어도 정상 사용자 화면의 빈 공간을 채우는 데 쓰지 않습니다.

## 최종 완료 흐름

다음 흐름이 실제 데이터와 정확한 개정본 연결로 처음부터 끝까지 동작해야 합니다.

```text
물성 데이터 등록 → 시험 데이터 연결 → 데이터 처리 → 여러 방법으로 모델 생성
→ 사용 모델 선택 → 솔버별 카드 생성 → 검토·승인
→ Materials DB에서 검색·조회·다운로드 → 모든 결과에서 원본 데이터까지 역추적
```

하나의 재료나 시험 데이터에서 여러 처리 결과와 모델이 나올 수 있고, 같은 데이터에 서로 다른
방법을 적용한 모델도 각각 보존합니다. 사용자가 선택한 정확한 모델 개정본에서 솔버·버전·단위계별
카드가 여러 개 생성될 수 있습니다. 승인된 결과는 Materials DB에서 다시 찾을 수 있어야 하며,
어느 결과에서 시작하더라도 사용한 시험 데이터와 원본 파일까지 거슬러 올라갈 수 있어야 합니다.

## 실행 순서와 문서 라우팅

한 GitHub issue가 여러 행에 나오면 서로 다른 작업 단위입니다. 각 행은 새 Codex 작업, 별도 구현
packet, 검증, 검토, 제품 소유자 확인과 PR/merge를 거칩니다. issue는 그 issue의 모든 행이 끝난
뒤 닫습니다.

| 순서 | 작업 단위와 Issue | 사용자가 얻는 결과 | 처음 읽을 범위 | 종료 조건 |
| ---: | --- | --- | --- | --- |
| 1 | [#157 깨끗한 데모 실행](https://github.com/pikachu444/cae-material-platform/issues/157) | 새 환경에서 예제 데이터와 대표 흐름을 한 번에 실행 | issue, 실패한 데이터 생성·자동 확인 절차, 관련 requirement·ADR·test. 실제 화면이 바뀔 때만 visual skill과 승인 화면을 읽음 | 깨끗한 환경에서 전체 데모와 자동 확인 성공, 관련 검사와 문서, merge |
| 2 | [#159 Materials 검색·조회·다운로드](https://github.com/pikachu444/cae-material-platform/issues/159) | 재료를 찾고 조건·출처·관련 시험/모델/카드를 확인해 적합한 결과를 내려받음 | issue, visual skill, Materials 승인 화면, 검색·트리·datasheet·다운로드 계약 | 검색 결과·정확한 개정본·다운로드, 긴 목록·스크롤·필수 화면 크기, 시각 승인, merge |
| 3 | [#159 물성 데이터 등록·관리](https://github.com/pikachu444/cae-material-platform/issues/159) | 사용자가 정한 Attribute와 단위·형식에 맞춰 물성 데이터를 등록하고 검증·공개 | issue, Administration 승인 화면, import·Table·Attribute·Layout·Link·revision·권한 계약 | 등록 미리보기, 열 연결, 단위·형식·행 오류, 정확한 개정본과 사용자 지정 화면, 시각 승인, merge |
| 4 | [#158 Modeling Data](https://github.com/pikachu444/cae-material-platform/issues/158) | 재료와 하나 이상의 시험 데이터를 정확한 개정본으로 연결하고 사용할 곡선을 선택 | issue, visual skill, inventory의 `modeling-data`, 선택된 manifest entry, test-data/link/API/state/test | 연결·단위·채널·여러 시험 데이터·오류 복구, 시각 승인, merge |
| 5 | [#158 Modeling Process](https://github.com/pikachu444/cae-material-platform/issues/158) | 원본을 바꾸지 않고 처리 방법별 결과를 만들어 비교·저장 | issue, `modeling-process` 승인 화면, processing·revision·invalidation 계약 | 처리 설정·결과·원본 연결·재실행·무효화, 그래프와 시각 승인, merge |
| 6 | [#158 Modeling Fit](https://github.com/pikachu444/cae-material-platform/issues/158) | 같은 처리 결과에 여러 방법을 적용해 모델을 비교하고 사용할 모델을 명시적으로 선택 | issue, `modeling-fit` 승인 화면, Fit React/API/state/test | 추천·선택·저장 상태 분리, 여러 방법/결과 보존, 그래프·키보드·시각 승인, merge |
| 7 | [#158 Modeling Export](https://github.com/pikachu444/cae-material-platform/issues/158) | 선택 모델에서 솔버별 카드를 생성·미리보기하고 Materials DB에 연결할 결과를 준비 | issue, `modeling-export` 승인 화면, selected-model·mapping·unit-system·solver-card 계약 | 솔버·버전·단위계별 결과, 지원 수준·차단 사유, 정확한 모델 연결, 시각 승인, merge |
| 8 | [#160 검토·승인·DB 공개·복구](https://github.com/pikachu444/cae-material-platform/issues/160) | 요청을 검토·승인하고 승인 결과를 Materials DB에서 찾고 내려받으며 실패를 복구 | issue, Activity/Admin 승인 화면, review·release·publication·download·recovery·권한 계약 | 역할별 흐름, 승인 결과 공개와 불변성, 무효화·복구·다운로드, 시각 승인, merge |
| 9 | [#161 공통 화면 정리](https://github.com/pikachu444/cae-material-platform/issues/161) | 트리·표·그래프·상태·키보드 조작이 모든 완료 화면에서 일관됨 | issue, visual/frontend skill, 활성 화면·공통 구성요소·사용 여부와 승인 화면 | 접근성·긴 이름·스크롤·넘침, 삭제 대상 참조 0, 전체 회귀와 시각 승인, merge |
| 10 | [#162 Ubuntu VM·문서 최종 검증](https://github.com/pikachu444/cae-material-platform/issues/162) | 지원 환경에서 전체 흐름과 역할별 복구가 재현되고 현재 문서와 화면이 일치 | issue, 병합된 기능·화면, 전체 문서 목록. 이 단계에서만 임시 문서 묶음을 읽음 | Hyper-V Ubuntu VM의 깨끗한 실행, 전체 흐름·역추적, 문서/화면 일치, 임시 자료 정리, merge |
| 11 | [#162 공개 실측 데이터 최종 검증](https://github.com/pikachu444/cae-material-platform/issues/162) | 인터넷에서 확보한 실제 측정 샘플을 제품에 등록해 솔버 카드와 Materials 재조회까지 완료 | issue의 고정 NIST Numisheet 2020 파일·공식 해시·이용조건, 병합된 실제 제품 흐름 | 원본 바이트·출처 보존, 실제 등록·처리·여러 모델·선택·카드 생성·검토·승인·재조회·다운로드·원본 역추적 자동 확인, 최종 승인, merge |

## 새 Codex 작업 운영

- 표의 첫 미완료 작업 단위만 진행하고 merge 후 다음 행을 새 Codex 작업에서 시작합니다. 서로
  종속된 Data → Process → Fit → Export와 공개 흐름은 병렬로 구현하지 않습니다.
- 새 작업의 첫 요청에는 `이전 단위가 병합된 최신 main에서 backlog의 첫 미완료 작업 단위를
  진행하라`고 적으면 됩니다. 대화 기억 대신 이 문서와 GitHub issue의 완료 표시를 사용합니다.
- 작업 단위를 끝낼 때 GitHub issue와 이 표에서 완료 위치, PR, 다음 행과 남은 위험을 확인합니다.
- 메인 에이전트가 exact issue와 현재 계약을 해석해 구현 packet을 GitHub issue에 저장합니다.
  구현자와 reviewer는 그 packet의 정확한 URL만 받습니다.
- 모델, 수정 횟수, reviewer, 승인, commit/push/PR/merge 경계는 `AGENTS.md`와 `.codex` 설정을
  따릅니다. 이 문서나 issue 본문에서 중복 정의하지 않습니다.
- 대형 spec과 manifest는 처음부터 읽지 않습니다. `rg`로 ID·family·component를 찾아 관련 절과
  선택된 entry만 읽고, 시각 작업에서는 승인 이미지를 원본 해상도로 직접 확인합니다.
- `docs/_incoming/2026-07-24-organic-ux-update/`는 #162 전에는 읽거나 삭제하지 않습니다.
