# Source data format bundle v2 reference

이 디렉터리는 물성 데이터 형식을 운영 환경에 설정하기 위한 공개 예시다. 실제 데이터는
포함하지 않는다. 이 파일들은 자주 올리는 데이터가 아니라, 운영을 시작하거나 승인된 형식이
추가될 때 적용하는 설정이다.

## 구성

- `catalog-schema-bundle.manifest.json`: 데이터 형식 6개, 원본 연결 6개, 단위 설정 2개를 선언한다.
  #246 제품 결정에 따라 어댑터는 `dma_to_elastoplasticity`를 원본 증거로만 보존하고,
  실제 제품 설정에는 승인된 직접 연결 5개만 만든다.
- `record-schemas/*.json`: JSON Schema draft 2020-12 record schema 6개다.

모든 JSON은 파싱 가능하며 manifest의 `record_schema_ref`는 이 디렉터리에서 해석된다.

## 현재 호환성 상태

이 fixture는 현재
`contracts/catalog/schema-definition-bundle.schema.json`의 positive fixture가 아니다. 원본은
`document_type/tables/link_types/unit_profiles` 형식과 `x-table-key`, `x-key`, `x-quantity`,
객체형 `x-curve` 등을 사용하지만 현재 계약은 다른 bundle envelope와 더 좁은 `x-*` 집합을
요구한다.

따라서 구현자는 fixture를 현재 계약에 맞게 몰래 수정하지 않는다. versioned source-format
adapter 또는 명시적으로 승인된 contract evolution으로 받아들인 뒤 canonical 내부 bundle로
정규화해야 한다. 호환성 작업의 최소 회귀 기준은 다음과 같다.

1. manifest와 모든 `record_schema_ref`를 해석한다.
2. 원본 연결 6개를 보존하고, 데이터 형식 6개와 승인된 직접 연결 5개를 계획한다.
3. 같은 입력의 재계획·재적용은 변경 0건이다.
4. business key와 reference pointer를 안정 identity/exact revision으로 해석한다.
5. 지원하지 않는 확장이나 단위를 항목별 오류로 보고하며 조용히 버리지 않는다.

원본 설명과 작성 배경은
[`docs/00-research/schema-driven-integration-source`](../../../docs/00-research/schema-driven-integration-source)를,
현재 차이와 처리 순서는
[`schema-driven-requirement-traceability.md`](../../../docs/02-requirements/schema-driven-requirement-traceability.md)를
참조한다.
