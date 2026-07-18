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
6. `Datasets` → `Processing Workbench`에서 strain을 `strain.engineering`/`1`, stress를
   `stress.engineering`/`Pa`로 연결한 Mapping Profile을 선택합니다.
7. `rows.sort_unique` 뒤에 필요한 금속 처리 단계를 순서대로 추가합니다.
   - `metal.elastic_modulus`: OLS, Huber robust, chord, secant 또는 manual 방식과 평가 구간
   - `metal.proof_stress`: E, proof offset(예: `0.002`)과 검색 구간
   - `metal.necking_candidate`: 최대 engineering stress 위치를 자동 후보로 보고
   - `metal.engineering_to_true_plastic`: 사용자가 확정한 `manual_necking_index`와 음의 plastic
     strain 처리 정책을 적용
   - `metal.hardening_fit_extrapolate`: Voce/Swift/Hockett–Sherby/Ghosh 후보, 관측 fitting 구간,
     최대 외삽 strain, primary/secondary 후보와 조합 weight를 명시
8. 각 stage의 curve와 **Scalar results**를 확인합니다. 자동 necking 후보는 원본을 자르지 않습니다.
   hardening stage에서는 네 후보와 선택 조합, 후보별 RMSE, 각 parameter의 lower/initial/fitted/upper,
   관측 구간과 외삽 구간을 확인합니다. 외삽 구간은 시험 관측값으로 표시되지 않습니다.
   처리 조건을 반복 사용할 경우 Recipe 새 revision으로 저장·게시하고 다른 시험에 preflight/batch 실행합니다.

   ![Recipe로 재사용할 수 있는 금속 인장 처리 단계](../15-demo/images/t55m-metal-processing-methods.png)

   ![네 hardening 후보와 선택 조합의 제한 외삽](../15-demo/images/t55m-hardening-candidates.png)
9. 여러 반복시험이면 Selection을 만들고 명시적 common-grid alignment를 실행합니다.
10. 통계 band와 outlier Candidate를 확인합니다. Candidate는 원본 curve를 삭제하지 않습니다.
11. 다음 중 하나를 선택합니다. 현재 Workbench의 새 선택 조합을 IR로 직접 승격하는 연결은 T-55M
    마지막 increment에서 제공될 예정이므로, 그 전에는 기존 tabulated/reference Voce 흐름과 혼동하지
    마십시오.
   - Dataset에서 tabulated plasticity IR을 생성합니다.
   - reference Voce calibration을 실행하고 Candidate의 fitted curve/residual/warning을 비교한
     뒤 선택 이유를 기록해 IR로 승격합니다.
12. OpenRadioss LAW36 또는 Abaqus isotropic plasticity target을 선택합니다.
13. mapping report의 status와 post-necking approximation을 확인하고 report digest를 승인합니다.
14. card preview를 확인하고 `.rad` 또는 `.inp`를 다운로드합니다.

## 성공 확인

- Source Raw Asset과 normalized/processed Dataset revision이 서로 다릅니다.
- IR은 exact Property/Dataset 또는 Candidate Selection revision을 가리킵니다.
- Abaqus preview에는 `*DENSITY`, `*ELASTIC`, `*PLASTIC`이 있습니다.
- OpenRadioss preview에는 `/MAT/LAW36`과 hardening function이 있습니다.
- download SHA-256은 card revision의 digest와 같습니다.

`approximated`가 있으면 reference card 생성은 가능할 수 있지만 production release는 별도
domain approval이 필요합니다. `unsupported`가 하나라도 있으면 card를 생성하지 마십시오.
