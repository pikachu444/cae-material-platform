# 스키마 기반 물성 DB 통합 계획

상태: **승인된 기획 gate, 구현 전**
기준선: `main@63a076c`
승인일: 2026-08-08
상위 추적: [#117](https://github.com/pikachu444/cae-material-platform/issues/117)

이 문서는 내부 전체 기획서, 다섯 개의 파생 Markdown 문서와 JSON Schema 참고 포맷을 현재
구현에 대조한 공개용 계획이다. 내부 원문, 스캔 이미지, 기밀 데이터와 원본 JSON bytes는 이
저장소에 포함하지 않는다. 실제 구현 범위와 완료 조건은 연결된 GitHub issue가 소유한다.

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
| Configurable Catalog | Database/Profile/Table/Attribute/Layout/Subset/Link Type, Record, 발행과 immutable revision | 동적 JSON 정의 bundle의 계약·계획·일괄 적용·내보내기 없음 | versioned Import Adapter와 기존 객체 projection으로 추가 |
| Artifact/Provenance | immutable bytes/digest, exact revision lineage | source schema bundle부터 생성된 Catalog revision까지의 공통 lineage 없음 | 원본 보존 후 모든 생성 revision에 source를 고정 |
| Unit | 등록용 13개 변환과 일부 SI Export | density, temperature, force, mass, time 및 Unit Profile 없음 | 공통 dimension/unit service와 versioned profile |
| Curve | canonical Test Data channel과 Catalog curve Artifact pointer | Catalog/Statistics/Fit가 공유하는 channel/deviation 계약 없음 | additive metadata와 과거 revision adapter |
| Import | CSV/TSV/XLSX governed import와 versioned Test Data JSON | DMA sweep·FLD profile과 품질 정책 없음 | 기존 Raw Asset/Dataset/Test Data 수명주기 재사용 |
| Statistics | mean, SD, median, MAD, IQR, 일부 confidence interval | distribution fitting, p05/p95 representative envelope 없음 | 후보·선택·계산 결과를 immutable revision으로 분리 |
| Process/Fit | explicit Process methods, exact Fit input/selection/reload | toe compensation과 승인된 representative input 없음 | 원본 불변, explicit option, stale propagation |
| Export | Abaqus/OpenRadioss preview/delivery와 mapping status | governed text Template, LS-DYNA, 다중 Unit Profile 없음 | 기존 renderer를 compatibility baseline으로 유지 |
| Review/Release | 일부 Material/Solver Card Review와 release kernel | Record/Test Data/계산/Template subject와 복구 흐름 미완 | #160에 공통 subject 경계만 합침 |
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
- 내부 원본·기밀 test data·scan PDF를 공개 저장소 fixture로 사용

## 4. 개발 이슈와 의존성

문서의 다섯 장을 그대로 다섯 issue로 만들지 않고, transaction·contract·UI·수치 검증과 소유
module 경계로 분해했다.

| 권장 순서 | Issue | 개발 단위 | 직접 선행 |
| ---: | --- | --- | --- |
| 1 | [#160](https://github.com/pikachu444/cae-material-platform/issues/160) | Record/Test Data를 포함한 검토·승인·공개·복구 기반 | #189 |
| 2 | [#161](https://github.com/pikachu444/cae-material-platform/issues/161) | 공통 UI token·전역 shell·오래된 스타일 정리 | #160 |
| 3 | [#221](https://github.com/pikachu444/cae-material-platform/issues/221) | 실제 4K 대표 화면에서 layout·pane·density·table·plot 정책 결정 | #161 |
| 4 | [#184](https://github.com/pikachu444/cae-material-platform/issues/184) | #221 승인 정책의 전체 route 적용과 실제 Windows 최종 검증 | #221 |
| 5 | [#204](https://github.com/pikachu444/cae-material-platform/issues/204) | 동적 JSON Schema 정의 bundle 계약과 no-write plan | #189, #184, 기획 gate |
| 6 | [#205](https://github.com/pikachu444/cae-material-platform/issues/205) | 공통 CAE unit/dimension과 Unit Profile | #189, #184, 기획 gate |
| 7 | [#206](https://github.com/pikachu444/cae-material-platform/issues/206) | curve channel metadata와 deviation | #205 |
| 8 | [#207](https://github.com/pikachu444/cae-material-platform/issues/207) | bundle apply/export와 provenance | #204, #205 |
| 9 | [#210](https://github.com/pikachu444/cae-material-platform/issues/210) | scalar distribution fitting | #205 |
| 10 | [#212](https://github.com/pikachu444/cae-material-platform/issues/212) | explicit toe compensation | #184, method/tolerance 결정 gate |
| 11 | [#208](https://github.com/pikachu444/cae-material-platform/issues/208) | bundle Administration plan/apply UI | #184, #204, #207 |
| 12 | [#209](https://github.com/pikachu444/cae-material-platform/issues/209) | DMA·FLD governed import | #160, #184, #205~#207 |
| 13 | [#211](https://github.com/pikachu444/cae-material-platform/issues/211) | representative envelope와 approved Fit input | #160, #184, #206, #210 |
| 14 | [#213](https://github.com/pikachu444/cae-material-platform/issues/213) | governed solver-card Template/renderer | #160, #184, #205, sandbox ADR |
| 15 | [#214](https://github.com/pikachu444/cae-material-platform/issues/214) | LS-DYNA MAT_024·다중 단위·Template UI | #160, #184, #205, #213 |
| 16 | [#215](https://github.com/pikachu444/cae-material-platform/issues/215) | SPA OIDC Code+PKCE | #160, #184, role policy |
| 17 | [#216](https://github.com/pikachu444/cae-material-platform/issues/216) | 제품 command audit wiring/coverage | #160, #184, 필요 시 #213/#215 |

#195와 #196은 각각 polymer/elastomer Fit의 별도 deferred issue다. DMA import나 공통 Template 기반을
이유로 자동 착수하지 않으며, family별 수치·입력·모델 상세 기획 승인이 필요하다.

## 5. 권장 실행과 제한된 병렬화

저장소의 기본 규칙은 `docs/13-delivery/backlog.md`의 첫 미완료 단위 하나만 진행하는 것이다.
순서상 선행 단위 #189는 PR #218에서 완료됐고, 현재 첫 미완료 단위는
`#160 → #161 → #221 → #184`의 첫 단계인 #160이다. 위 확장 구현은 이 선행 작업을 건너뛰지 않는다.
#161, #221과 #184는 원래 schema 기능 분해가 아니라, 이후 UI가 잘못된
1920px 전역 cap과 고정 density를 반복하지 않도록 제품 소유자가 앞당긴 공통 기반이다.

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
- Toe method: #212 전에 식, eligibility, parameter, tolerance와 failure criterion을 승인한다.
- Template engine: #213 전에 표현력, sandbox, resource limit와 static validation ADR을 승인한다.
- Differential Evolution: 기존 bounded multistart가 실패하는 재현 사례와 성공률·시간·결정론 근거가
  생길 때만 별도 issue로 검토한다.
- Production model/solver/threshold: 이 계획은 선택 권한을 부여하지 않는다. bounded synthetic
  reference와 explicit `non-production` 표시를 유지한다.

## 8. 공개 저장소 보관 정책

저장소에는 이 계획과 구현 시 확정되는 public contract, synthetic fixture, test와 사용자/운영 문서만
보관한다. 내부 다섯 문서, 전체 스캔 PDF, 참고 포맷 원본, confidential build/validation data와 내부
식별자는 Library 또는 승인된 내부 보관소에 남긴다. 구현자가 issue 본문만 읽어도 범위·제외·검증을
재현할 수 있어야 하며, 대화 기억이나 내부 원문 접근을 전제로 하지 않는다.
