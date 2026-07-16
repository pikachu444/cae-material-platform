# Steel 시험 데이터에서 탄소성 카드까지

## 입력 범위

현재 Steel workflow는 `metal` Material과 monotonic uniaxial tensile CSV를 위한
`reference/non-production` 기능입니다. 실제 시험 표준, necking 이후 inverse identification,
rate/temperature dependency와 damage/failure model은 포함하지 않습니다.

Reference sample은 `examples/data/`의 tensile CSV를 사용하십시오. 각 curve에는 engineering
strain과 engineering stress 의미 및 원래 단위를 명시해야 합니다.

## 절차

1. `metal` Material, State와 Property Set을 만듭니다. Density, E, ν, yield stress를 확인합니다.
2. **Test data workflow**에서 Specimen과 reference tensile Test Run을 만듭니다.
3. CSV를 업로드합니다. 원본은 immutable Raw Asset으로 먼저 저장됩니다.
4. strain/stress column, original unit와 normalized unit을 확인하고 import합니다.
5. raw와 normalized Dataset을 구분해 curve를 확인합니다.
6. 여러 반복시험이면 Selection을 만들고 명시적 common-grid alignment를 실행합니다.
7. 통계 band와 outlier Candidate를 확인합니다. Candidate는 원본 curve를 삭제하지 않습니다.
8. 다음 중 하나를 선택합니다.
   - Dataset에서 tabulated plasticity IR을 생성합니다.
   - reference Voce calibration을 실행하고 Candidate의 fitted curve/residual/warning을 비교한
     뒤 선택 이유를 기록해 IR로 승격합니다.
9. OpenRadioss LAW36 또는 Abaqus isotropic plasticity target을 선택합니다.
10. mapping report의 status와 post-necking approximation을 확인하고 report digest를 승인합니다.
11. card preview를 확인하고 `.rad` 또는 `.inp`를 다운로드합니다.

## 성공 확인

- Source Raw Asset과 normalized/processed Dataset revision이 서로 다릅니다.
- IR은 exact Property/Dataset 또는 Candidate Selection revision을 가리킵니다.
- Abaqus preview에는 `*DENSITY`, `*ELASTIC`, `*PLASTIC`이 있습니다.
- OpenRadioss preview에는 `/MAT/LAW36`과 hardening function이 있습니다.
- download SHA-256은 card revision의 digest와 같습니다.

`approximated`가 있으면 reference card 생성은 가능할 수 있지만 production release는 별도
domain approval이 필요합니다. `unsupported`가 하나라도 있으면 card를 생성하지 마십시오.
