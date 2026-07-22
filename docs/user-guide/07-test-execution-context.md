# 시험 Campaign·장비 교정·실행 조건 고정

이 절차는 시험 결과가 나중에 바뀐 시험방법이나 장비 교정의 최신 revision을 따라가지
않도록, 실제 실행 당시의 근거를 Test Run에 고정하는 방법을 설명합니다.

## 준비 조건

- Material과 Material State가 있어야 합니다.
- 해당 State에 Specimen, Test Method, Test Run이 먼저 등록되어 있어야 합니다.
- Test Run의 `performed_at`은 실제 시험 시각이어야 합니다.

## 따라 하기

1. Material 상세에서 대상 State를 엽니다.
2. **Test execution governance** 영역의 **Register Campaign**에서 정확한 Test Method
   revision을 선택합니다.
3. 표준을 따랐다면 designation과 edition을 입력합니다. 차이가 있었다면 **Approved
   deviation**을 선택하고 승인된 사유를 남깁니다. 표준 적합성을 주장하지 않는 경우에는
   **Standard not claimed**를 선택합니다.
4. **Register Instrument**에 장비 코드, 장비명, 일련번호를 입력합니다.
5. **Record Calibration**에서 교정서 번호, 기관, 유효 시작·종료 시각을 입력합니다.
   같은 장비의 사용 가능한 교정 기간은 서로 겹칠 수 없습니다.
6. **Bind exact Run context**에서 Test Run을 선택합니다. 화면에는 그 Run과 같은 Method
   revision의 Campaign과, 실행 시각에 유효했던 장비 교정만 표시됩니다.
7. 관측 온도(K), loading rate와 단위, 시편 방향, 시험 매질을 명시적으로 입력하고
   **Capture and bind revisions**를 누릅니다.
8. 아래 목록에서 Run revision과 Context revision을 확인합니다.


## 오류를 해석하는 방법

- **No selected Instrument calibration is valid**: Run 실행 시각이 선택 장비의 교정 유효
  구간 `[valid_from, valid_until)` 밖에 있습니다. Run 시각을 임의로 바꾸지 말고 당시의
  교정 기록을 등록하십시오.
- **Campaign and Condition must pin the Test Run Method revision**: Campaign이나 조건이 다른
  Method revision을 가리킵니다. 같은 exact revision으로 다시 선택해야 합니다.
- **Test Run already has a stable Context identity**: 이미 실행 근거가 고정되어 있습니다.
  기존 근거는 덮어쓰지 않습니다. 정정 revision 기능은 후속 범위에서 별도 승인 흐름과
  함께 제공할 예정입니다.

## 보존되는 근거

Context revision에는 Test Run, Campaign, Condition, Instrument, Calibration 각각의 stable
identity와 exact revision ID가 함께 저장됩니다. 교정이나 시험방법의 current head가
바뀌어도 과거 Context는 변경되지 않습니다. 일반 환경조건은 명시적 typed column이며,
이름/값을 임의로 넣는 EAV나 하나의 불명확한 JSON payload로 저장되지 않습니다.
