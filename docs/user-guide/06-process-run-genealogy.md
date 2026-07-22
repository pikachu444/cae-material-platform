# Process Run과 Specimen source Lot 연결

이 화면은 “현재 보이는 Lot”을 느슨하게 연결하지 않습니다. Process, Material State, 입력 Lot,
출력 Lot과 Specimen의 정확한 immutable revision을 한 번에 고정합니다. 과거 revision은 수정되지
않으며 정정은 새 revision으로 남습니다.

## 준비

1. Material 상세에서 Material State를 선택합니다.
2. `Catalog genealogy`에서 Process Definition과 입력·출력에 사용할 Lot/Batch를 등록합니다.
3. 시험 시편까지 연결하려면 같은 State의 `Test Data`에서 Specimen을 먼저 등록합니다.

## Process Run 기록

1. `Process Run input / output Lots`에서 Process revision을 선택합니다.
2. 고유한 Run code를 입력합니다.
3. Balance basis를 `mass`, `volume`, `count`, `not_assessed` 중에서 선택합니다.
4. `Consumed Lots`와 `Produced Lots`에 각 Lot revision, 수량, 원본 단위를 입력합니다.
5. 분할은 출력 Lot을, 병합은 입력 Lot을 `Add input/output Lot`으로 추가합니다.
6. 평가하는 balance에는 허용 상대오차를 입력합니다. 평가하지 않으면 사유를 입력합니다.
7. `Create Process Run revision 1`을 누르고 저장된 입력합, 출력합과 상대차를 확인합니다.

현재 원본 단위는 질량 `kg`, `g`, `mg`, 부피 `m3`, `L`, `mL`, `cm3`, 개수 `1`을 지원합니다.
서비스는 입력한 원본 단위를 보존하면서 질량은 `kg`, 부피는 `m3`, 개수는 `1`로 정규화합니다.
평가 basis와 단위 차원이 다르거나 허용오차를 넘으면 저장하지 않습니다.


## Specimen source 연결

1. 같은 화면의 `Specimen source Lots`에서 exact Specimen revision을 선택합니다.
2. 실제 시편의 원재료가 된 Lot revision을 하나 이상 선택합니다.
3. `Pin exact source revisions`를 누릅니다.
4. 생성된 source revision과 Lot label을 확인합니다.

한 시편에 여러 source Lot을 연결할 수 있습니다. 이미 생성된 source genealogy의 과거 revision은
덮어쓰지 않습니다. 현재 demo 화면은 최초 연결을 제공하며 정정 revision은 protected API 계약으로
지원합니다. 화면에서의 정정 기능은 후속 사용성 개선 항목입니다.

## 저장이 거부되는 경우

- 입력과 출력에 같은 exact Lot revision을 동시에 사용한 경우
- 다른 Material revision에 속한 State 또는 Lot을 연결한 경우
- 현재 Process Run graph가 순환하게 되는 경우
- 평가 basis와 수량 단위의 차원이 다른 경우
- 출력 balance가 선언한 tolerance를 초과한 경우
- 다른 organization/project 또는 허용 classification의 revision을 참조한 경우

Run card에 표시되는 revision 번호와 balance evidence를 기록에 사용하십시오. 화면의 최신 label만
보고 과거 실행 입력을 추정하지 마십시오.
