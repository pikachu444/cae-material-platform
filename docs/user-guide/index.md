# CAE Material Platform 사용자 가이드

이 가이드는 개발자가 아니라 재료시험·재료모델·CAE 사용자가 demo에서 실제로 Material과
시험 데이터를 등록하고 material card를 내려받는 절차를 설명합니다. 현재 결과는
`reference/non-production`이며 회사의 승인된 재료값이나 solver qualification을 대신하지
않습니다.

## 빠른 경로

1. [서비스 실행과 연결](01-getting-started.md)
2. [Steel 시험 데이터에서 탄소성 카드까지](02-steel-elastoplastic.md)
3. [Polymer 완화시험에서 Abaqus 점탄성 카드까지](03-polymer-viscoelastic.md)
4. [Elastomer Ogden--Prony 카드](04-elastomer-ogden-prony.md)
5. [Revision, provenance와 다운로드 이해](05-revisions-downloads.md)
6. [Process Run과 Specimen source Lot 연결](06-process-run-genealogy.md)

## 현재 할 수 있는 일

- Material, Material State, 기본 물성과 immutable revision 등록·조회
- Process Definition, Lot/Batch와 State genealogy 연결
- Process Run의 consumed/produced Lot split·merge와 Specimen source Lot exact-pin
- 인장 또는 shear-relaxation CSV 원본 등록과 명시적 column/unit mapping
- raw, normalized, processed Dataset과 curve 확인
- 반복 인장 curve의 alignment/statistics/outlier assessment
- reference Voce 또는 two-term Prony automatic fitting과 수동 IR 입력
- 사람의 Candidate 선택과 새 IR revision 승격
- Abaqus/OpenRadioss mapping report, card preview와 개별 download
- one-term Ogden--Prony IR의 Abaqus/OpenRadioss LAW62 card 생성

## 아직 제한된 일

- CSV 외 일반 XLSX/TSV와 laboratory vendor format
- Test Campaign, Instrument calibration과 완전한 condition snapshot
- 점탄성 반복시험 통계, 온도 shift와 master curve
- promoted IR을 다시 보정하는 iterative promotion
- 여러 Dataset/IR/Card를 한 ZIP으로 받는 Bulk Export Bundle
- 실제 Abaqus/OpenRadioss solver 실행과 qualification

위 항목의 구현 순서는 [production-pilot 실행 계획](../13-delivery/production-pilot-execution-plan.md)에
기록합니다. 기능이 추가될 때 이 가이드와 화면 이미지를 함께 갱신합니다.

## 화면 예시

![Material 상세와 immutable revision](../15-demo/images/e2e-material-detail.png)

![시험 데이터와 processing workflow](../15-demo/images/e2e-shear-workflow.png)

문제가 생기면 먼저 브라우저의 Connection 상태, Material class, exact State/Property revision,
CSV column/unit, mapping report의 `unsupported` 또는 `approximated` 항목을 확인하십시오.
