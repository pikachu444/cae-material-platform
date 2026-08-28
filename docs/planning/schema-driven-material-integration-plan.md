# 스키마 기반 물성 DB 통합 계획

상태: **승인된 기획 gate, #246 Task 3+4 최종 정합**
원기획 기준선: `main@63a076c`
현재 대조 기준선: `main@712bda0`
승인일: 2026-08-08
상위 추적: [#117](https://github.com/pikachu444/cae-material-platform/issues/117)

이 문서는 내부 전체 기획서, 다섯 개의 파생 Markdown 문서와 JSON Schema 참고 포맷을 현재
구현에 대조한 공개용 계획이다. 실제 데이터가 아닌 원본 요구 문서와 샘플 포맷은
[`원본 패키지`](../00-research/schema-driven-integration-source/README.md)와
[`source-v2 JSON fixture`](../../fixtures/schema-definition-bundle/source-v2/README.md)로 공개한다.
현재 구현 차이는 [`요구사항 추적표`](../requirements/schema-driven-requirement-traceability.md)가
기록하고 [#246](https://github.com/pikachu444/cae-material-platform/issues/246)이 보완 작업을
소유한다. 실제 시험 데이터, 스캔 이미지와 기밀 식별자는 포함하지 않는다.

## 1. JSON 참고 포맷의 해석

JSON 입력은 제품에 고정된 데이터 schema가 아니다. 관리자가 JSON Schema draft 2020-12 정의를
업로드하면 시스템이 Table, Attribute, Layout과 Link Type으로 해석하고, 이후 Record 데이터가
그 정의에 따라 검증·저장되는 **동적 정의 입력**이다.

- 정의 bundle은 record schema를 임의 개수 포함할 수 있어야 한다.
- 원본에서 확인한 `technical-data`, `tensile-test`, `elastoplasticity`는 참고 예시일 뿐이다.
- 이후 테스트에서 3개나 6개 schema를 사용해도 제품 계약의 고정 cardinality가 되지 않는다.
- schema 정의 upload와 실제 Record/Test Data upload는 서로 다른 command와 검토 대상을 가진다.
- 원본 JSON bytes와 digest는 immutable Artifact로 보존하고, 내부 객체는 기존 stable identity와
  immutable revision으로 투영한다.
- configurable Catalog는 canonical Material, Test Data, Dataset, Material Model IR, Solver Card,
  Revision, Artifact 또는 Provenance를 대체하지 않는다.
- 알 수 없는 `x-*` 확장 키워드는 조용히 실행하지 않는다. 보존·경고·거절 정책을 versioned
  contract로 명시한다.

다음은 방향만 설명하는 비규범 합성 예시다. key 이름과 지원 키워드의 정식 계약은 #204가
positive/negative fixture와 함께 확정한다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Synthetic Property Record",
  "type": "object",
  "properties": {
    "synthetic-property": {
      "type": "object",
      "properties": {
        "Data Information": {
          "type": "object",
          "properties": {
            "Record ID": {
              "type": "string",
              "x-business-key": true
            }
          },
          "required": ["Record ID"]
        },
        "Property": {
          "type": ["number", "null"],
          "x-unit": "MPa"
        }
      }
    }
  },
  "additionalProperties": false
}
```

## 2. 현재 구현과의 대조

| 영역 | 현재 구현 | 이번 계획의 실제 공백 | 처리 원칙 |
| --- | --- | --- | --- |
| Configurable Catalog | 기존 configurable objects와 #246 Task 1A의 source-v2 adapter, 객체형 `x-curve`, business-key/reference 해석, exact source export | 변경하지 않은 source-v2의 남은 단위와 실제 JSON 데이터 등록 | Task 2 단위와 Task 1B 등록을 기존 versioned adapter/object projection 위에 추가 |
| Artifact/Provenance | immutable bytes/digest, exact revision lineage와 source-v2 원본 파일·JSON pointer·해시 보존 | 실제 데이터 등록 결과의 source-to-Record/Test Data lineage | Task 1A를 재작성하지 않고 Task 1B가 exact installed-format revision을 고정 |
| Unit | #205 공통 dimension/Unit Profile과 #209의 `Hz` 구현 | `mm/min`, `tonne/mm3`, 추가 solver unit system과 Unit Profile 관리 UI | 앞의 두 단위는 #246 Task 2, solver profile/UI는 #214; production 기본값을 정하지 않음 |
| Curve | #206 공통 channel/deviation 계약, source-v2 객체형 `x-curve` adapter와 기존 통계 projection | p05/p95 representative revision과 승인된 Fit 연결 | additive representative result/review 계약; 기존 Artifact·과거 revision 유지 |
| Import | CSV/TSV/XLSX, versioned Test Data JSON, #209 DMA frequency-temperature/FLD governed import, #246 Task 1B exact JSON 다건 등록 | `dma_strain_sweep` 전용 처리는 운용 자료·승인 요구가 없어 보류 | #343은 현재 계약·UI의 명시적 미지원과 #195 production 점탄성 소유권을 기록하며 새 처리 기능을 만들지 않음 |
| Statistics | scalar distribution, common-grid piecewise-linear/no-extrapolation alignment, append-only outlier 판단, pointwise mean/95% CI와 exact Dataset/Test Run lineage | p05/p95 representative revision·review/approval/invalidation·approved representative exact revision→Fit selection | 기존 기반을 회귀검증하고 #211의 좁은 잔여만 추가 |
| Process/Fit | explicit Process, toe compensation, exact Fit input/selection/reload와 calibration scope exact pinning | 승인된 representative exact revision을 Fit source로 선택하는 연결 | 원본 불변, explicit option, stale propagation을 재사용 |
| Export | Abaqus/OpenRadioss preview/delivery, mapping status와 exact Unit Profile trace; 기존 `kg_m_s` bytes 보존 | governed text Template, LS-DYNA와 추가 solver unit system 없음 | 기존 renderer를 compatibility baseline으로 유지 |
| Review/Release | #160의 Record/Test Data 검토·게시·복구와 기존 Material/Solver Card lifecycle | representative result와 Template subject의 구체 연결 | representative는 #211, Template는 #213/#214에서 기존 kernel 재사용 |
| Identity | backend bearer/OIDC validation, permission과 RLS | SPA Code+PKCE login/callback/token lifecycle 없음 | 기존 User/Reviewer/Administrator preset 유지 |
| Audit | append-only hash chain, query/export/integrity verifier | 제품 command wiring이 일부 validation/holdout에 한정 | 기반 재작성 없이 event coverage와 atomicity 보강 |

## 3. 중복·충돌 처리

다음 항목은 새 기능으로 다시 만들지 않는다.

- #158에서 완료한 Data → Process → Fit → Export와 exact-revision lineage
- #159에서 완료한 configurable Catalog CRUD, Record 등록과 Administration 기본 화면
- 기존 Review/Release, Artifact, Provenance, Audit hash-chain 기반
- 기존 Abaqus/OpenRadioss renderer와 synthetic reference fixtures

다음 해석은 현재 구조와 충돌하므로 금지한다.

- 예시 schema 이름이나 개수를 core database schema로 고정
- canonical aggregate를 generic EAV/JSONB record로 치환
- released/raw revision 또는 bytes를 in-place 수정
- schema bundle에 없다는 이유로 기존 객체나 Record 자동 삭제
- Jinja2, Differential Evolution, production model·solver·threshold를 기획 문구만으로 확정
- 조직 근거 없이 `data_manager` persistent role을 추가
- 실제 사내·기밀 test data, 내부 식별자 또는 scan PDF를 공개 저장소 fixture로 사용

## 4. 개발 이슈와 의존성

문서의 다섯 장을 그대로 다섯 issue로 만들지 않고, transaction·contract·UI·수치 검증과 소유
module 경계로 분해했다.

| 권장 순서 | Issue | 개발 단위 | 직접 선행 |
| ---: | --- | --- | --- |
| 1 | [#160](https://github.com/pikachu444/cae-material-platform/issues/160) | Record/Test Data를 포함한 검토·승인·공개·복구 기반 | #189 |
| 2 | [#161](https://github.com/pikachu444/cae-material-platform/issues/161) | 공통 UI token·전역 shell·오래된 스타일 정리 | #160 |
| 3 | [#221](https://github.com/pikachu444/cae-material-platform/issues/221) | 다섯 viewport 대표 화면에서 구현용 잠정 layout·pane·density·table·plot 정책 결정 | #161 |
| 4 | [#184](https://github.com/pikachu444/cae-material-platform/issues/184) | #221 잠정 정책의 전체 route 적용과 자동 geometry 검증; 실제 장비는 #223 | #221 |
| 5 | [#204](https://github.com/pikachu444/cae-material-platform/issues/204) | 동적 JSON Schema 정의 bundle 계약과 no-write plan | #189, #184, 기획 gate |
| 6 | [#205](https://github.com/pikachu444/cae-material-platform/issues/205) | 공통 CAE unit/dimension과 Unit Profile | #189, #184, 기획 gate |
| 7 | [#206](https://github.com/pikachu444/cae-material-platform/issues/206) | curve channel metadata와 deviation | #205 |
| 8 | [#207](https://github.com/pikachu444/cae-material-platform/issues/207) | bundle apply/export와 provenance | #204, #205 |
| 9 | [#210](https://github.com/pikachu444/cae-material-platform/issues/210) | scalar distribution fitting | #205 |
| 10 | [#208](https://github.com/pikachu444/cae-material-platform/issues/208) | bundle Administration plan/apply UI | #184, #204, #207 |
| 11 | [#212](https://github.com/pikachu444/cae-material-platform/issues/212) | explicit toe compensation | #184, method/tolerance 결정 gate |
| 12 | [#209](https://github.com/pikachu444/cae-material-platform/issues/209) | DMA·FLD governed import — PR #248 완료 | #160, #184, #205~#207 |
| 13 | [#246](https://github.com/pikachu444/cae-material-platform/issues/246) | source-v2 원본 정합과 누락 범위 폐쇄 — Task 1A PR #250, Task 2 PR #345, Task 1B PR #353, Task 2B PR #356 완료; #344 최종 정합 | #209, 원본 패키지와 추적표 |
| 14 | [#195](https://github.com/pikachu444/cae-material-platform/issues/195) | production 폴리머 점탄성 입력·수치 acceptance·선택 저장·reload·사용자 흐름 | #158, #209, #246, 별도 제품 scope gate; #211에 의존하지 않음 |
| 15 | [#211](https://github.com/pikachu444/cae-material-platform/issues/211) | p05/p95 representative revision·review/approval/invalidation·approved exact Fit selection | #160, #184, #206, #210, #246; 기존 alignment/outlier/mean CI/exact pinning 재사용 |
| 16 | [#213](https://github.com/pikachu444/cae-material-platform/issues/213) | governed solver-card Template/renderer | #160, #184, #205, #246, sandbox ADR |
| 17 | [#214](https://github.com/pikachu444/cae-material-platform/issues/214) | LS-DYNA MAT_024·다중 단위·Template UI | #160, #184, #205, #213 |
| 18 | [#215](https://github.com/pikachu444/cae-material-platform/issues/215) | SPA OIDC Code+PKCE | #160, #184, #246 |
| 19 | [#216](https://github.com/pikachu444/cae-material-platform/issues/216) | 제품 command audit wiring/coverage | #160, #184, #246, 필요 시 #213/#215 |

#195와 #196에는 각각 bounded synthetic `reference/non-production` 구현이 이미 있고,
[#195 planning packet](issue-195-polymer-viscoelastic-fit-plan.md)과
[#196 planning packet](issue-196-elastomer-hyperelastic-hyperviscoelastic-fit-plan.md)도 존재한다.
두 이슈의 deferred 잔여는 해당 기반을 재작성하는 일이 아니라 family별 production 입력·정책·수치
검증·계약 확장이다. #246 뒤에는 제품 소유자가 승인한 순서에 따라 #195를 진행한다. 현재 계산과
화면을 production-ready로 소급하지 않고 input semantics, 독립 numerical reference, acceptance와
실제 사용자 흐름을 먼저 하나의 bounded packet으로 승인한다. #196의 순서는 별도 승인 전에는 바꾸지 않는다.

## 5. 권장 실행과 제한된 병렬화

저장소의 기본 규칙은 `docs/planning/backlog.md`의 첫 미완료 단위 하나만 진행하는 것이다.
#209는 PR #248, main `3e642e8`에서 완료했고 #246의 Task 1A·Task 2·Task 1B도 각각
PR #250·#345·#353에서 완료했고 #343 Task 2B도 PR #356, main `712bda0`에서 완료했다.
#344가 Task 3+4의 후속 소유권·보류 결정을 닫으면 #246을 종료한다. 그 다음에는 #195의 production
점탄성 입력·수치 acceptance·사용자 흐름을 먼저 진행하고, 이어 #211로 이동한다. #211은 이미
구현된 alignment·outlier·mean/95% CI·exact input pinning을
재사용하고 pointwise p05/p95 representative revision, review/approval/invalidation과 approved
representative exact revision→Fit selection만 구현한다.

[#276](https://github.com/pikachu444/cae-material-platform/issues/276)은 Simulation Data 등록 결과를
Modeling·solver-card 경로와 잇는 후보 후속이며 현재 `배치 결정 대기`다. native parent와 실행 순서는
지정되지 않았고, 이 후보 등록 자체는 #117의 승인된 `#246 → #195 → #211 → #213 → #214 → #215
→ #216 → #162 작업 1 → #162 작업 2 → #223` 순서를 바꾸지 않는다.

제품 소유자가 별도 branch/worktree, 소유 파일과 shared contract 동결을 명시적으로 승인한 경우에만
다음 병렬 묶음을 검토할 수 있다.

- #204 + #205: Catalog bundle contract와 unit service의 소유 파일 분리
- #207 + #210 + #212: Catalog/Statistics/Processing module 분리, shared provenance 조정
- #208 + #209: Administration/import route와 공통 component 충돌 사전 조정
- #211 + #213: Statistics/Fit와 Export 경계 분리, exact-revision contract 공유
- #215 + #216: auth event contract를 먼저 동결하고 middleware 소유권 분리

Data → Fit → Export → Publication처럼 downstream이 exact upstream revision을 소비하는 흐름은 병렬
구현하지 않는다.

## 6. 공통 완료 원칙

각 issue의 세부 완료 조건에 더해 다음을 공통 적용한다.

- source/raw/released bytes와 과거 revision은 immutable이다.
- moving `latest`가 아니라 exact identity/revision/digest를 고정한다.
- 입력, option, algorithm/library version, decision과 결과를 Provenance로 재생할 수 있다.
- unsupported, approximation, missing evidence와 failure를 성공처럼 표시하지 않는다.
- schema/API positive·negative contract, unit/domain, PostgreSQL integration과 applicable browser
  journey를 검증한다.
- UI 변경은 keyboard/focus, 긴 이름, 오류 복구와 1366/1440/1920/2560/3840 원본 화면을
  검수한다. 1920/2560/3840 전체 화면과 100% 핵심 영역 crop을 제품 소유자가 직접 승인한다.
- 공개 fixture는 synthetic/non-production이며 내부 원본을 파생해도 식별 가능한 기밀 값은 넣지 않는다.
- 구현 PR마다 current docs, `IMPLEMENTATION_STATUS.md`와 backlog를 동기화한다.

## 7. 제품 결정 gate

- `data_manager`: 기본은 추가하지 않고 기존 permission/preset으로 해결한다. 독립 책임·감사·수명주기
  근거가 승인될 때만 별도 IAM issue를 만든다.
- Toe method: #212의 명시 구간 OLS zero-intercept를 유지한다. `offset_shift`는 승인된 시험 절차,
  eligibility, parameter, tolerance와 수치 fixture가 생길 때만 별도 issue로 검토한다.
- Template engine: #213 전에 표현력, sandbox, resource limit와 static validation ADR을 승인한다.
- Differential Evolution: 기존 bounded multistart가 실패하는 재현 사례와 성공률·시간·결정론 근거가
  생길 때만 별도 issue로 검토한다.
- 다단계 승인: 현재 #160 단일 review lifecycle을 유지한다. 규제·전자서명·복수 승인자 근거가
  승인될 때 별도 governance issue로 검토한다.
- Plugin wiring: #213의 안전한 Template 경계와 generic plugin 연결을 분리한다. 실제 격리 배포 대상과
  운영 수명주기가 승인될 때만 별도 plugin issue로 검토한다.
- 비동기 계산: 실제 응답 시간, 중단 복구 또는 내구성 요구가 현재 동기 경계의 실패를 입증할 때만
  bounded job issue로 검토한다.
- 추가 경화식: 승인된 재료 family, solver target과 독립 수치 reference가 특정 식을 요구할 때만
  별도 model issue로 검토한다.
- Production model/solver/threshold: 이 계획은 선택 권한을 부여하지 않는다. bounded synthetic
  reference와 explicit `non-production` 표시를 유지한다. #195/#196은 family별 production acceptance를
  통과하기 전까지 이 표시를 제거하지 않는다.

## 8. 공개 저장소 보관 정책

저장소에는 이 계획, 실제 데이터가 없는 원본 요구 문서 5개, 샘플 스키마 형식, public contract,
fixture, test와 사용자/운영 문서를 보관한다. 원본 문서와 설명용 샘플은
[`docs/00-research/schema-driven-integration-source`](../00-research/schema-driven-integration-source/README.md),
기계 판독 JSON은 [`fixtures/schema-definition-bundle/source-v2`](../../fixtures/schema-definition-bundle/source-v2/README.md),
현재 구현과의 차이는
[`docs/requirements/schema-driven-requirement-traceability.md`](../requirements/schema-driven-requirement-traceability.md)가
소유한다. 전체 스캔 PDF, 실제 시험 데이터, confidential build/validation 결과와 내부 식별자는
승인된 내부 보관소에 남긴다. 구현자는 대화 기억 없이 저장소 문서와 exact Issue만으로 범위·제외·검증을
재현할 수 있어야 한다.
