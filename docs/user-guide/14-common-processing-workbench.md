# Mapping Profile과 공통 Processing Workbench 사용하기

이 화면은 특정 시험·재료모델·solver에 종속되지 않은 채널 매핑과 커브 전처리를 제공합니다.
입력은 저장된 `cmp.test-data`의 정확한 revision이며, 브라우저에서 계산한 임시 값이 아니라
서버가 반환한 각 처리 단계의 수치와 진단을 비교합니다.

## 처리 미리보기

1. `Datasets` → `Processing Workbench`를 엽니다.
2. **Exact Test Data input**에서 문서와 revision을 선택하고 **Load exact JSON**을 누릅니다.
3. 저장된 Mapping Profile을 선택하거나 JSON editor에서 다음 항목을 확인합니다.
   - `independent_quantity`
   - source `channel_key`와 계산용 `target_quantity`
   - 허용 normalized unit
   - required 여부와 명시적 scale/offset
   - `reject` 또는 `drop_any` missing-data 정책
4. 재사용할 매핑이면 **Create profile**을 누릅니다. 기존 profile을 변경할 때는 변경 사유를
   입력하고 **Append revision**을 눌러 새 revision을 만듭니다. 기존 revision은 덮어쓰지 않습니다.
5. **Ordered processing steps**에서 method ID, version과 option을 순서대로 편집합니다.
6. **Preview with server**를 누릅니다.
7. Stage 목록에서 `mapping` 또는 각 method를 선택해 동일한 축의 원본/처리 curve overlay와
   row 수, warning, SHA-256을 확인합니다.

현재 등록된 공통 method는 다음과 같습니다.

- 정렬과 duplicate 정책: `rows.sort_unique`
- 범위 선택: `curve.crop`
- 수치 변환: `curve.scale_shift`
- 선형 resampling: `curve.resample_linear`
- moving average: `curve.moving_average`
- Savitzky–Golay: `curve.savitzky_golay`
- smoothing spline: `curve.smoothing_spline`

각 method의 option 계약은 서버의 versioned registry에서 읽습니다. 알 수 없는 option, 호환되지
않는 quantity/unit, 범위 밖 extrapolation, 비유한 수치, 허용되지 않은 결측값은 묵시적으로
보정하지 않고 실패시킵니다.

![정확한 시험 revision과 재사용 Mapping Profile](../15-demo/images/t53-processing-stage-overlay.png)

![공통 축으로 비교하는 처리 단계 curve overlay](../15-demo/images/t53-processing-curve-overlay.png)

## 현재 경계

화면의 결과는 명확히 **Preview only · not promotable**로 표시됩니다. 이 단계에서는 Mapping
Profile revision만 PostgreSQL에 영속화되고, preview curve는 아직 Dataset/Processing Run
revision으로 승격되지 않습니다. T-53의 다음 increment에서 immutable output과 다중 curve
alignment/statistics를 연결한 뒤에만 저장 결과를 후속 Recipe와 Modeling 입력으로 사용할 수
있습니다.
