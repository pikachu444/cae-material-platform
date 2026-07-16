# Revision, provenance와 다운로드 이해

## Stable identity와 revision

Material, State, Dataset과 Material Model은 사용자가 같은 대상으로 인식하는 stable identity와
시점별 immutable revision을 따로 가집니다. 수정은 기존 revision의 update가 아니라 다음
revision의 append입니다.

Run과 card는 항상 정확한 revision ID를 사용합니다. `latest`를 계산 입력으로 사용하지 않습니다.

## 세 가지 이력

- Revision history: 같은 논리 대상의 내용 변경
- Provenance: 어떤 immutable input과 activity/agent가 결과를 만들었는지
- Audit: 누가 어떤 command/download/decision을 수행했는지

Material 상세의 Revision history와 Provenance summary에서 이 정보를 확인합니다. Catalog
genealogy도 화면에 보이는 최신 label이 아니라 선택한 exact revision을 저장합니다.

![Process와 Lot exact-revision genealogy](../15-demo/images/process-lot-genealogy.png)

## Mapping status

| 상태 | 사용자 해석 |
| --- | --- |
| `exact` | target이 같은 의미를 직접 표현 |
| `transformed` | 단위/parameterization을 의미 보존 변환 |
| `approximated` | 의미 손실이 있어 명시적 검토 필요 |
| `ignored` | target에서 사용하지 않음; 필수 항목이면 차단 |
| `unsupported` | 표현할 수 없어 생성 실패 |
| `not_applicable` | 이 target에는 적용되지 않음 |

## 현재 다운로드

- 개별 Raw/derived Artifact: short-lived download token 또는 protected content endpoint
- 개별 Solver Card: card의 Download 버튼
- Release: 구성요소 digest를 고정한 release manifest

여러 시험 Dataset, IR과 Card를 실제 파일 ZIP으로 받는 기능은 T-45 Bulk Export Bundle에서
추가합니다. Release manifest를 임의의 bulk archive로 재해석하지 않습니다.

다운로드한 card나 Artifact는 화면 또는 API가 제공하는 SHA-256과 비교할 수 있습니다. Digest가
다르면 사용하지 말고 integrity issue로 보고하십시오.
