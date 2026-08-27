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
- 순서 3 `#159 물성 데이터 등록·관리`는 제품 소유자 확인을 거쳐 PR #181에서
  완료했습니다. #159의 두 작업 단위가 모두 끝났습니다.
- 순서 4 `#158 Modeling Data`는 PR #183, main `f5c69d1`에서 완료했습니다.
- 순서 5 `#158 Modeling Process`는 제품 소유자 확인을 거쳐 PR #188, main `38571a8`에서
  완료했습니다. Modeling Process 시각 일관성 후속도 PR #191, main `e7c938b`에서 완료했습니다.
- 순서 6 `#158 Modeling Process 7개 결과·저장 사용성 보정`은 제품 소유자 확인·승인을 거쳐 PR #192,
  main `248e086`에서 완료했습니다. 순서 7 `#190 메인 오케스트레이터 acceptance 문서`는 PR #194,
  순서 8 `#158 Modeling Fit 작업 3A`는 PR #197, 순서 9 실제 Fit은 PR #198, 순서 10 Fit UI
  보정은 PR #199에서 완료했습니다.
- 순서 11 `#158 Modeling Export`는 구현, main acceptance, 독립 review와 제품 소유자 최종 시각
  승인을 거쳐 [PR #202](https://github.com/pikachu444/cae-material-platform/pull/202), main
  `94387e4`에서 완료했고 #158을 닫았습니다.
- 2026-08-08 기획 gate에서 내부 전체 기획서와 동적 JSON Schema 참고 포맷을 현재 구현에 대조하고
  [#204~#216 계획](../12-roadmap/schema-driven-material-integration-plan.md)으로 분해했습니다. 이 gate는
  구현을 앞당기지 않습니다.
- 순서 12 `#189 lazy chunk 예산과 Workbench 분할 기준`은
  [PR #218](https://github.com/pikachu444/cae-material-platform/pull/218)에서 완료했습니다. 순서 14
  `#160` Task 2는 [PR #224](https://github.com/pikachu444/cae-material-platform/pull/224)에서 완료했습니다.
  순서 15 `#161`은 [PR #226](https://github.com/pikachu444/cae-material-platform/pull/226)과
  [PR #227](https://github.com/pikachu444/cae-material-platform/pull/227), main
  `ca7c97869522e3fe5d889fdc5f834bd963f85340`에서 완료했습니다. 순서 16 `#221`의
  [decision packet](../17-evidence/issue-221-high-dpi-decision.md)은 제품 소유자가 2026-08-10에
  P2/`Standard`를 #184의 구현용 잠정 정책으로 승인했고 [PR #228](https://github.com/pikachu444/cae-material-platform/pull/228)의
  ready 전환과 squash merge를 승인했습니다. 순서 17 `#184`의 production 이식은
  [PR #231](https://github.com/pikachu444/cae-material-platform/pull/231), main
  `ab27e3947817cefa997e49c5dc1d237ec5035adb`에서 완료했습니다.
  [issue-owned evidence](../17-evidence/issue-184-high-dpi-global-implementation.md)의 독립 시각 감수는
  fixture 의존 원본 30개 누락을 `CHANGES_REQUESTED`로 남겼습니다. 제품 소유자는 2026-08-11에
  이 누락을 통과로 소급하지 않은 채 정확한 30개 원본·manifest·재감수를 #223으로 인계하고 #184를
  완료하도록 결정했습니다. 순서 18 `#204`는
  [PR #233](https://github.com/pikachu444/cae-material-platform/pull/233)에서 구현·검증을 완료했으며,
  순서 19 `#205`는 [PR #234](https://github.com/pikachu444/cae-material-platform/pull/234)에서
  구현·검증을 완료했습니다. 순서 20 `#206`은
  [PR #235](https://github.com/pikachu444/cae-material-platform/pull/235)에서 구현·검증과 제품 소유자
  화면 승인을 완료하고 main `9535ee00adfd880990c31e6d623c5f9c39af99ea`에 병합했습니다. 순서 21
  `#207`과 순서 22 `#210`도 완료했습니다. 순서 23 `#208`은
  [PR #242](https://github.com/pikachu444/cae-material-platform/pull/242)에서 구현·검증·독립 감수와
  제품 소유자 화면 승인을 완료하고 main `9d8314d882fd395a509ede81291fab69cbf34c84`에 병합했습니다.
  순서 24 `#212`는 [PR #244](https://github.com/pikachu444/cae-material-platform/pull/244)에서
  구현·검증·독립 Balanced 감수와 제품 소유자 화면 승인을 완료하고 main
  `aa009e5898a6e46577a80a7382bda2b7b17fd002`에 병합했습니다. 순서 25 `#209`는
  [PR #248](https://github.com/pikachu444/cae-material-platform/pull/248), main
  `3e642e8c3e96e95dd7d10b19d87e18af53db9e7c`에서 완료했고, 순서 26 `#246` Task 1A는
  [PR #250](https://github.com/pikachu444/cae-material-platform/pull/250), main
  `b9a82e96532fe796aaf1889387cd391c952e1c67`에서 완료했습니다. 현재 첫 미완료 실행 단위는
  `#246`의 native Sub-issue인 [#341](https://github.com/pikachu444/cae-material-platform/issues/341)이며,
  Task 2 공통 단위와 변경하지 않은 source-v2 전체 왕복을 닫습니다. 그다음 `#246` Task 1B로
  복귀하고, 부모의 승인된 남은 범위를 마친 뒤 순서 27 `#211`로 진행합니다.
- 순서 14 `#160` Task 1은 [PR #220](https://github.com/pikachu444/cae-material-platform/pull/220),
  main `53e4a698235e4c7dad8c87e0156bc2627866989f`에서 병합했습니다. Task 2는
  [PR #224](https://github.com/pikachu444/cae-material-platform/pull/224)에서 병합해 `#160`을 [x]로
  완료했습니다. Reviewer Activity `Needs attention`의 2560×1440·3840×2160 고정 밀도 control/text
  전체 화면 폭·고해상도 전 제품 구성 (Q-20) 실패는 Task 2의 공통 compact token과 Activity layout/geometry
  범위에서 보정했습니다. 2026-08-09
  제품 소유자 disposition에 따라 실제 Windows 4K 100%·150%·200% 물리 가독성 최종 판정은
  [#223](https://github.com/pikachu444/cae-material-platform/issues/223)으로 이관하고 전체 순서의
  마지막에 둡니다. PR #224 병합과 delivery tracking을 동기화했으며,
  공통 기반 전환 전까지 경로 전용 4K workaround를 추가하지 않습니다.
  #162 작업 1·2는 모든 기능과 고해상도 기준이 병합된 뒤 수행하는 최종 제품 흐름 검증이고,
  #223은 그 뒤 Activity를 포함한 제품 전체를 실제 장비에서 최종 검증합니다.
- 현재 작업 환경에는 실제 3840×2160 디스플레이가 없습니다. #221은 다섯 CSS viewport에서 공통
  layout·pane·density·table·plot의 구현용 잠정 정책을 결정했고, #184는 이를 전체 route와 고위험
  상태에 적용했습니다. 실제 Windows 4K 100%·150%·200% 물리 가독성과 제품 소유자가 정확히 열거한
  fixture 의존 원본 30개·manifest·독립 재감수만 #223으로 인계합니다. 30개는 여전히 미완료이며
  알려진 잘림·겹침·overflow·상호작용 결함을 #223으로 미루는 일반 예외가 아닙니다.

#167의 승인 target은 다시 만들거나 재승인하지 않습니다. 과거 packet, correction 이미지와 완료
보고서는 working tree에 보관하지 않고 Git/PR 이력에서 조회합니다.

## 제품 순서를 바꾸지 않는 지원 작업

- [#282 개발환경 재현성](https://github.com/pikachu444/cae-material-platform/issues/282)은 제품 기능
  순서를 바꾸지 않는 공통 기반 작업입니다. Python·uv·Node·npm과 Docker 실행 버전을 고정한 뒤,
  #261·#279·#280은 #282가 병합된 최신 `main`에서 각각 별도 worktree로 시작합니다.
- #282는 #249의 FE 체크 항목이 아니며, 아래 표의 첫 미완료 제품 단위 #341/#246과 도메인 작업 순서를
  앞당기거나 완료 처리하지 않습니다.
- [#321 Windows 네이티브 실행·오프라인 설치 지원 프로그램](https://github.com/pikachu444/cae-material-platform/issues/321)은
  #322~#324의 코드 전달이 모두 `main`에 병합된 독립 지원 프로그램입니다. 그러나 clean Windows 11
  PC의 offline Demo 전체 흐름, 실제 machine-scope 방화벽과 LAN 접속, #215 뒤 Server OIDC 검증이
  남아 #321은 OPEN입니다. 이는 #162의 Hyper-V Ubuntu 최종 통합검증 harness를 대체하거나 아래
  #117 제품 순서를 바꾸지 않습니다.

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
| 6 | [#158 Modeling Process 7개 결과·저장 사용성 보정](https://github.com/pikachu444/cae-material-platform/issues/158) | 계산 결과와 저장 행동을 한눈에 구분하고 Process 화면을 현재 기준으로 확정 | issue의 병합 뒤 제품 소유자 피드백, `modeling-process` 승인 화면, Process React/CSS/state/test | 잘림 없는 method 선택, 직접 읽히는 결과, 충분한 저장 입력, 절제된 상태·보조 문구, 명확한 saved-results disclosure, 지속 그래프·오류 복구·current/history 보존, 시각 승인, merge |
| 7 | [#190 메인 오케스트레이터 acceptance 문서](https://github.com/pikachu444/cae-material-platform/issues/190) ([PR #194](https://github.com/pikachu444/cae-material-platform/pull/194)) | 이후 작업의 요구·실화면·보존 계약·검증 조건이 세션과 구현자를 넘어 일관되게 추적됨 | issue, root `AGENTS.md`, 현재 `product-work-acceptance`, desktop-engineering-ui skill의 관련 절 | 짧은 acceptance trace와 known-bad 실패 예시, 사용자 결과·보존·검증 경계, merge |
| 8 | [#158 Modeling Fit 작업 3A — 공학 검증 계약과 reference set](https://github.com/pikachu444/cae-material-platform/issues/158) ([PR #197](https://github.com/pikachu444/cae-material-platform/pull/197)) | 네 금속 hardening 공개식과 독립 reference 값·식별성·검증 경계를 후속 구현이 재현할 수 있음 | issue의 작업 3A, fitting validation, synthetic fixture/manifest, production hardening 식과 관련 test | Altair 2025 식 계약, 독립 stress/tangent/objective/recovery·tamper gate, provenance digest, reviewer 승인, merge |
| 9 | [#158 Modeling Fit 작업 3B — 실제 Fit 구현](https://github.com/pikachu444/cae-material-platform/issues/158) ([PR #198](https://github.com/pikachu444/cae-material-platform/pull/198)) | 같은 처리 결과에 여러 방법을 적용해 모델을 비교하고 사용할 모델을 명시적으로 선택 | merge된 3A 계약, issue의 작업 3B, `modeling-fit` 승인 화면, Fit React/API/state/test | 추천·선택·저장 상태 분리, 여러 방법/결과 보존, production persistence와 실제 revision round-trip, 그래프·키보드·시각 승인, merge |
| 10 | [#158 Modeling Fit UI 정보 위계·공통 액션 보정](https://github.com/pikachu444/cae-material-platform/issues/158) ([PR #199](https://github.com/pikachu444/cae-material-platform/pull/199)) | Fit 상단 source/state 위계를 정리하고 104px ribbon, 여섯 그룹, Candidate evidence와 1366–3840 responsive geometry를 일관되게 제공 | issue 작업 3B 후속 packet, `modeling-fit` 승인 화면, Fit React/CSS/capture/document contracts | 공통 28px action baseline, source digest/method/run Evidence 이동, 상태 매핑·실패 복구·1920 recovery captures, 독립 visual acceptance |
| 11 | [#158 Modeling Export](https://github.com/pikachu444/cae-material-platform/issues/158) ([PR #202](https://github.com/pikachu444/cae-material-platform/pull/202)) | 선택 모델에서 솔버별 카드를 생성·미리보기하고 Materials DB에 연결할 결과를 준비 | issue, `modeling-export` 승인 화면, selected-model·mapping·unit-system·solver-card 계약 | 솔버·버전·단위계별 결과, 지원 수준·차단 사유, 정확한 모델 연결, 시각 승인, merge |
| 12 | [#189 lazy chunk 예산과 Workbench 분할 기준](https://github.com/pikachu444/cae-material-platform/issues/189) ([PR #218](https://github.com/pikachu444/cae-material-platform/pull/218)) | 완성된 Process/Fit/Export의 실제 사용자 비용을 근거로 Workbench 성능과 분할 시점을 관리 | issue, production build 관찰값, bundle checker, test strategy, Process/Fit/Export 계약 | raw/gzip·실제 경로 비용, warning/error 근거와 분할 촉발 기준, 필요한 경우 별도 보존적 분할, merge |
| 13 | 2026 스키마 기반 확장 기획 gate (승인·issue 분해 완료) | 내부 기획과 동적 JSON Schema 참고 포맷을 현재 구현에 맞는 bounded issue로 전환 | [승인된 계획](../12-roadmap/schema-driven-material-integration-plan.md), #204~#216 | 고정 schema/EAV 오해 제거, 중복·충돌·의존성·결정 gate와 공개 보관 경계 기록 |
| 14 | [x] [#160 검토·승인·DB 공개·복구](https://github.com/pikachu444/cae-material-platform/issues/160) — Task 1 PR #220, Task 2 PR #224 | 요청을 검토·승인하고 승인 결과를 Materials DB에서 찾고 내려받으며 실패를 복구 | issue, Activity/Admin 승인 화면, Record/Test Data subject, review·release·publication·download·recovery·권한 계약 | Task 1은 PR #220, main `53e4a698235e4c7dad8c87e0156bc2627866989f`에서 병합. Task 2 구현·다섯 viewport 증거·회귀·문서·한정 화면 승인은 PR #224에서 완료. 실제 Windows 4K 100%·150%·200% 최종 물리 판정은 #223으로 이관. 다음 단위는 #161 |
| 15 | [x] [#161 공통 화면·전역 레이아웃 기반](https://github.com/pikachu444/cae-material-platform/issues/161) — PR #226, 후속 PR #227 | 트리·표·그래프·상태·키보드와 글자·control·pane·plot token이 모든 현재 화면에서 일관됨 | issue, visual/frontend skill, 활성 화면·공통 구성요소·1920 cap 사용처·승인 화면 | PR #226과 #227이 main `ca7c97869522e3fe5d889fdc5f834bd963f85340`에서 완료. 다음 단위는 #221 |
| 16 | [x] [#221 4K·고DPI 레이아웃·밀도 결정 게이트](https://github.com/pikachu444/cae-material-platform/issues/221) — [PR #228](https://github.com/pikachu444/cae-material-platform/pull/228), Product Owner approved | 다섯 viewport에서 대표 후보를 비교해 구현용 잠정 layout·pane·density·table·plot 정책을 승인 | issue, #161 결과, [고해상도 전략](../12-roadmap/high-dpi-display-strategy.md), [decision packet](../17-evidence/issue-221-high-dpi-decision.md)의 원본/crop과 review prompt | 2026-08-10에 P2/`Standard` 잠정 정책과 ready/squash merge를 승인. 실제 Windows 4K 물리 가독성은 #223으로 이관하고 다음 단위는 #184 |
| 17 | [x] [#184 4K·고DPI 전역 대응](https://github.com/pikachu444/cae-material-platform/issues/184) — [PR #231](https://github.com/pikachu444/cae-material-platform/pull/231), main `ab27e3947817cefa997e49c5dc1d237ec5035adb` | #221의 잠정 정책을 모든 핵심 화면과 고위험 상태에 적용하고 넓은 화면 geometry를 완성 | issue, #221 승인 packet, 공통 token, 전체 정상·예외 다섯 viewport, [issue-owned evidence](../17-evidence/issue-184-high-dpi-global-implementation.md) | 2026-08-11 제품 소유자 결정으로 production 구현과 #184를 완료. 독립 감수의 `CHANGES_REQUESTED`를 PASS로 바꾸지 않고 fixture 의존 density별 10개 상태, 총 30개 원본·manifest·재감수를 #223으로 명시적으로 인계. 실제 장비 판정도 #223. 다음 단위는 #204 |
| 18 | [x] [#204 동적 JSON Schema 정의 bundle 계약·plan](https://github.com/pikachu444/cae-material-platform/issues/204) — [PR #233](https://github.com/pikachu444/cae-material-platform/pull/233) | 관리자가 임의 개수의 schema 정의를 적용 전에 검증하고 변경 계획을 확인 | issue, configurable Catalog/Artifact/Provenance, FR-CFG/LNK/JSON | Bundle/plan `1.0.0`, HTTP `0.33.0`, deterministic PostgreSQL no-write plan, arbitrary-cardinality synthetic fixture와 독립 감수. 다음 단위는 #205 |
| 19 | [x] [#205 공통 CAE unit과 Unit Profile](https://github.com/pikachu444/cae-material-platform/issues/205) — [PR #234](https://github.com/pikachu444/cae-material-platform/pull/234) | 등록부터 Export까지 같은 차원·단위와 profile을 사용 | issue, 기존 13개 registration mapping, canonical Test Data와 Export unit 계약 | bounded 공통 service와 immutable exact profile revision, 기존 13개·`kg_m_s`·profile-free bytes 호환, domain/API/PostgreSQL/Compose/독립 감수 완료. 다음 단위는 #206 |
| 20 | [x] [#206 curve channel metadata와 deviation](https://github.com/pikachu444/cae-material-platform/issues/206) — [PR #235](https://github.com/pikachu444/cae-material-platform/pull/235), main `9535ee00adfd880990c31e6d623c5f9c39af99ea` | Chart·Statistics·Fit가 곡선 채널·단위·편차를 같은 의미로 표시 | issue, #205, curve/Test Data/Artifact 계약 | metadata `1.0.0`, HTTP `0.35.0`, 기존 Artifact adapter와 exact revision/provenance, Materials·Modeling 공유 표시, PostgreSQL·Compose·브라우저·다섯 viewport·독립 감수·제품 소유자 승인 완료. 다음 단위는 #207 |
| 21 | [x] [#207 정의 bundle apply/export와 provenance](https://github.com/pikachu444/cae-material-platform/issues/207) — [PR #237](https://github.com/pikachu444/cae-material-platform/pull/237), main `382da2f6cc088c0ee3149ee44687a9a6df8686b9` | 승인한 plan을 원자적으로 적용하고 source JSON까지 역추적·재내보내기 | issue, #204~#205, Catalog publication/Revision/Artifact/Provenance | exact Artifact·`plan_fingerprint` 서버 재검증, 단일 transaction apply/publication/provenance/audit/outbox, 멱등·rollback·round-trip·Record migration block과 독립 감수를 완료. 다음 단위는 #210 |
| 22 | [x] [#210 scalar distribution fitting](https://github.com/pikachu444/cae-material-platform/issues/210) — [PR #239](https://github.com/pikachu444/cae-material-platform/pull/239), main `2fd68e569c790639c17c237e640465b65d811eae` | 반복 scalar 값의 후보 분포와 적합 근거를 비교·선택·저장 | issue, #205, Statistics/Calibration 계약 | 승인된 2-parameter MLE·AICc/AD bootstrap 정책, immutable exact revision/provenance, 선택형 Modeling 분석 sheet, PostgreSQL·Compose·브라우저·Standard/Large 다섯 viewport·독립 감수·제품 소유자 승인을 완료. 실제 Windows 4K 물리 판정은 #223이며 다음 단위는 #208 |
| 23 | [x] [#208 Definition Bundle Administration UI](https://github.com/pikachu444/cae-material-platform/issues/208) — [PR #242](https://github.com/pikachu444/cae-material-platform/pull/242), main `9d8314d882fd395a509ede81291fab69cbf34c84` | 관리자가 upload → plan → apply → read-back/export를 안전하게 수행 | issue, #184, #204/#207, Administration 승인 화면과 권한 | stale/conflict/recovery, 역할·browser·다섯 viewport·제품 소유자 피드백 반영본의 독립 Balanced 재감수와 2026-08-13 시각 승인을 완료. 다음 단위는 #212 |
| 24 | [x] [#212 explicit toe compensation](https://github.com/pikachu444/cae-material-platform/issues/212) — [PR #244](https://github.com/pikachu444/cae-material-platform/pull/244), main `aa009e5898a6e46577a80a7382bda2b7b17fd002` | 원본을 보존하며 명시적으로 선택한 toe 보정 결과와 영향을 비교 | issue의 method/tolerance 결정 gate, #158 Process/Fit 계약 | 승인된 `tensile.toe_zero_intercept@1.0.0`, deterministic replay·failure/recovery·source/corrected overlay·immutable exact Fit input, 다섯 viewport, 독립 Balanced 감수와 2026-08-13 제품 소유자 시각 승인을 완료. 실제 Windows 4K 물리 판정은 #223이며 다음 단위는 #209 |
| 25 | [x] [#209 DMA·FLD governed import](https://github.com/pikachu444/cae-material-platform/issues/209) — [PR #248](https://github.com/pikachu444/cae-material-platform/pull/248), main `3e642e8c3e96e95dd7d10b19d87e18af53db9e7c` | DMA/FLD 원본을 검증해 canonical Test Data로 등록·연결 | issue, #160/#184, #205~#207, governed import/Test Data | 두 독립 profile, Hz, atomic whole-file rejection, 품질·unit·provenance·review/browser·다섯 viewport·Balanced 독립 감수와 2026-08-13 제품 소유자 시각 승인을 완료. 다음 단위는 #246 |
| 26 | [#246 source-v2 원본 정합과 누락 범위 폐쇄](https://github.com/pikachu444/cae-material-platform/issues/246) — Task 1A [PR #250](https://github.com/pikachu444/cae-material-platform/pull/250), main `b9a82e96532fe796aaf1889387cd391c952e1c67`; Task 2 active Sub-issue [#341](https://github.com/pikachu444/cae-material-platform/issues/341) | 원본 포맷을 실제로 수용하고 완료 Issue 밖에 남은 요구를 중복 없이 폐쇄 | issue, 원본 패키지, 요구사항 추적표, #204~#216 현재 코드·계약 | Task 1A의 source adapter·정확한 직접 연결 5개·Materials 네 분류·실데이터 검증·Balanced 감사·제품 소유자 화면 승인을 완료. #341이 additive common-unit `1.1.0`과 변경하지 않은 source-v2 plan/apply/export/no-op을 소유한다. 병합 뒤 #246은 열어 두고 Task 1B로 복귀한다. |
| 27 | [#211 representative envelope와 approved Fit input](https://github.com/pikachu444/cae-material-platform/issues/211) | 기존 mean/95% CI와 append-only 포함·제외 lineage를 재사용해 p05/p95 대표 revision을 검토·승인하고 승인된 exact revision을 Fit에 사용 | issue, #160/#184, #206/#210/#246, 현재 alignment·Statistics/QC·calibration scope·Fit 계약 | 기존 common-grid piecewise-linear/no-extrapolation, exact Dataset/Test Run lineage, outlier 판단, immutable mean/95% CI와 exact input pinning 회귀검증; 새 p05/p95 representative revision·review/approval/invalidation·approved representative exact revision→Fit selection 검증, merge |
| 28 | [#213 governed solver-card Template 기반](https://github.com/pikachu444/cae-material-platform/issues/213) | 기존 Export 결과를 보존하며 검토된 Template로 안전하게 render | issue의 sandbox ADR gate, #160/#184/#205/#246, #158 Export | renderer 호환성, isolation, exact Template/Mapping provenance, merge |
| 29 | [#214 LS-DYNA MAT_024·다중 단위·Template UI](https://github.com/pikachu444/cae-material-platform/issues/214) | released Template로 MAT_024와 여러 Unit Profile 카드를 생성·관리 | issue, #160/#184/#205/#213, solver mapping/Administration | golden·unit·review·preview/download checksum·다섯 viewport·기존 solver 회귀, merge |
| 30 | [#215 SPA OIDC Code+PKCE](https://github.com/pikachu444/cae-material-platform/issues/215) | production SPA login·logout·expiry/권한 오류를 안전하게 복구 | issue, #160/#184/#246, identity/security 계약과 deployment config | provider·negative·role·production bypass E2E·다섯 viewport, merge |
| 31 | [#216 제품 command audit wiring](https://github.com/pikachu444/cae-material-platform/issues/216) | 주요 command의 성공·거절·복구를 기존 hash chain에서 누락 없이 추적 | issue, #160/#184/#246, 필요 시 #213/#215, Audit 계약 | event matrix, atomicity, redaction, integrity·restore 검증, merge |
| 32 | [#162 Ubuntu VM·문서 최종 검증](https://github.com/pikachu444/cae-material-platform/issues/162) | 사용자 설치 방식과 분리된 Hyper-V Ubuntu 최종 통합검증 harness에서 전체 흐름과 역할별 복구가 재현되고 현재 문서와 화면이 일치 | issue, 병합된 기능·화면, 전체 문서 목록. 이 단계에서만 임시 문서 묶음을 읽음; Windows 11 native/offline 제품 경로는 독립 #321 | Hyper-V Ubuntu VM의 깨끗한 최종 통합검증, 전체 흐름·역추적, 문서/화면 일치, 임시 자료 정리, merge. 이를 사용자 제품 설치·배포 방식으로 선언하지 않음 |
| 33 | [#162 공개 실측 데이터 최종 검증](https://github.com/pikachu444/cae-material-platform/issues/162) | 인터넷에서 확보한 실제 측정 샘플을 제품에 등록해 솔버 카드와 Materials 재조회까지 완료 | issue의 고정 NIST Numisheet 2020 파일·공식 해시·이용조건, 병합된 실제 제품 흐름 | 원본 바이트·출처 보존, 실제 등록·처리·여러 모델·선택·카드 생성·검토·승인·재조회·다운로드·원본 역추적 자동 확인, 최종 승인, merge |
| 34 | [#223 제품 전체 실제 Windows 4K 최종 물리 가독성 검증](https://github.com/pikachu444/cae-material-platform/issues/223) | Materials·Modeling·Activity·Administration을 실제 Windows 4K 100%·150%·200%에서 읽고 조작할 수 있음을 최종 확인하고 #184의 fixture 증거 부채를 닫음 | issue, #221 잠정 정책, #184 전역 적용·handoff matrix·누락 30개 목록, #160 Activity 증거, #162 작업 2 완료 상태 | #184에서 인계한 정확한 30개 원본을 세 density로 재수집하고 structured manifest와 독립 원본 재감수를 완료. 이어 세 Windows 배율의 환경 메타데이터·대표 route/state 원본·1:1 crop, 물리 가독성·상호작용·복구·read-back 검증, 제품 소유자 최종 판정, 발견 결함 bounded bug와 재검증, merge |

## 새 Codex 작업 운영

- 표의 첫 미완료 작업 단위만 진행합니다. PR 번호가 생기면 merge 전에 작업 PR에서 이 표에 완료한
  작업 단위·PR과 다음 미완료 행을 기록하고, 이 갱신이 끝날 때까지 작업 단위를 완료하지 않습니다.
  merge 후에는 다음 행을 새 Codex 작업에서 시작합니다. 서로 종속된 Data → Process → Fit → Export와
  공개 흐름은 병렬로 구현하지 않습니다.
- 새 작업의 첫 요청에는 `이전 단위가 병합된 최신 main에서 backlog의 첫 미완료 작업 단위를
  진행하라`고 적으면 됩니다. 대화 기억 대신 이 문서와 GitHub issue의 완료 표시를 사용합니다.
- merge 직후 최종 보고 전에 작업 책임자가 exact issue에 PR·merge SHA·다음 단위를 기록하고,
  해당하는 경우 parent tracker(`#117`)의 대응 항목을 체크합니다. 여러 작업 단위가 있는 issue는
  모든 행이 끝날 때까지 열어 둡니다.
- exact issue와 현재 계약에서 범위·사용자 결과·보존 상태·검증 조건을 정해 GitHub issue에
  기록합니다. 작업 방식과 개인 도구 설정은 저장소 밖에서 관리하며 이 문서에 중복 정의하지
  않습니다. 승인과 commit/push/PR/merge 경계는 `AGENTS.md`를 따릅니다.
- 대형 spec과 manifest는 처음부터 읽지 않습니다. `rg`로 ID·family·component를 찾아 관련 절과
  선택된 entry만 읽고, 시각 작업에서는 승인 이미지를 원본 해상도로 직접 확인합니다.
- `docs/_incoming/2026-07-24-organic-ux-update/`는 #162 전에는 읽거나 삭제하지 않습니다.
