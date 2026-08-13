# 스키마 기반 물성 DB 통합 원본 패키지

상태: `reference`
원본 작성일: 2026-08-06~2026-08-07
원본 코드 분석 기준선: `main@31f9a3f`
현재 상태 대조: [`schema-driven-requirement-traceability.md`](../../02-requirements/schema-driven-requirement-traceability.md)

이 디렉터리는 스키마 기반 물성 DB 통합 작업의 원래 요구, 검증 계획, 갭 분석과 샘플
스키마 형식을 보존한다. 실제 시험값, 소재값, 고객·협력사 식별자 또는 운영 인증정보는
포함하지 않는다.

## 사용 규칙

- 이 파일들은 작성 당시의 원본 기록이다. 현재 구현 상태는 라이브 코드,
  `IMPLEMENTATION_STATUS.md`, delivery backlog와 GitHub Issue/PR에서 확인한다.
- #204~#216과 #246 작업자는 관련 P/G 항목과 최신 추적표를 함께 읽는다.
- 원본 요구와 현재 Issue의 수락 조건이 다르면 원본을 조용히 무시하지 않는다. 차이를 추적표와
  Issue에 기록하고 제품 결정을 받은 뒤 구현한다.
- 샘플 형식의 테이블명·개수는 제품에 고정하는 값이 아니다. 동적 스키마 입력과 호환성을
  검증하는 공개 reference다.
- 실제 JSON 파일은 [`fixtures/schema-definition-bundle/source-v2`](../../../fixtures/schema-definition-bundle/source-v2)에
  있으며 Markdown 코드 블록에서 내용 변경 없이 추출했다.

## 문서

| 파일 | 역할 |
| --- | --- |
| [`01_전체_작업_기획서.md`](01_전체_작업_기획서.md) | 전체 목표, P1~P10, V0~V4 실행 전략 |
| [`02_오픈소스_요구사항_명세.md`](02_오픈소스_요구사항_명세.md) | P1~P10 원본 수락 조건 |
| [`03_스키마_정의_세트.md`](03_스키마_정의_세트.md) | 샘플 번들 구성과 `x-*` 매핑 규칙 |
| [`04_내부_빌드_검증_계획.md`](04_내부_빌드_검증_계획.md) | V0~V4 검증 기준과 내부 데이터 경계 |
| [`05_갭_분석_상세.md`](05_갭_분석_상세.md) | G1~G24 작성 시점 분석 |

## 샘플 스키마

[`schemas/`](schemas/)에는 복원된 설명용 Markdown 원본 7개가 있다.

- 번들 manifest 1개
- `technical-data`, `tensile-test`, `dma-test`, `fld-test`, `elastoplasticity`,
  `statistics` record schema 6개

합본 PDF와 원본 스크린샷은 Markdown/JSON과 내용이 중복되므로 저장소에 포함하지 않는다.
