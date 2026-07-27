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
6. **Modeling → Data**에서 JSON/CSV/XLSX 입력을 선택하고 strain을
   `strain.engineering`/`1`, stress를 `stress.engineering`/`Pa`로 연결한 Mapping Profile을
   확인합니다.
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


   Fit rail에서 실제 처리와 hardening fit 단계를 확인합니다. 얕은 설정 영역에서 Candidate equations,
   한 줄 Fit 설정 띠에서 Candidate equations, Fit domain(Start/End), Selected blend(Primary),
   Primary contribution, Extrapolation(Target strain) 및 Graph interaction을 조정하고
   **Stress response / Residual / Tangent modulus**를 차례로 확인합니다. observed 영역 이후의 황색
   배경과 점선이 실제 시험값이 아닌지 확인합니다. Output points와 후보 parameter/bound evidence는
   그래프 바로 위의 분리된 **Candidate parameters** 행을 열어 secondary blend law, Output points,
   parameter/bound evidence를 확인한 뒤 primary/secondary, blend ratio와
   **Selection reason**을 정합니다.


9. 여러 반복시험이면 Selection을 만들고 명시적 common-grid alignment를 실행합니다.
10. 통계 band와 outlier Candidate를 확인합니다. Candidate는 원본 curve를 삭제하지 않습니다.
11. Material 상세의 **Tensile Dataset → Elastoplastic IR → Solver Card**를 엽니다.
12. **Promote a fitted metal Processing Output**에서 방금 만든 exact Output revision을 선택합니다.
    표시된 point 수와 revision을 확인하고 bounded fitted extrapolation acknowledgement를 체크한 뒤
    승격합니다. 이 단계는 curve를 다시 fitting하지 않습니다. Output, source Test Data, Mapping Profile,
    후보 선택과 domain이 새 immutable IR revision에 그대로 고정됩니다.


13. IR의 origin이 `selected fitted hardening Processing Output`인지, hardening curve point 수와
    characterized/extension strain이 선택한 Output과 일치하는지 확인합니다.

    저장한 Recipe를 Batch로 실행한 Output이라면 같은 evidence 패널에 **Published Recipe
    revision**과 **Successful Batch attempt**가 표시됩니다. **Open Recipe library and Batch
    monitor**를 눌러 정확히 같은 Recipe revision, 옵션, Attempt와 Output으로 돌아갈 수 있습니다.
    이 정보가 없는 과거 direct Output은 schema `1.2.0`으로 유지되며 Recipe 재사용을 주장하지
    않습니다.



14. OpenRadioss LAW36 또는 Abaqus isotropic plasticity target을 선택합니다.
15. mapping report에서 `exact`, `transformed`, `approximated`, `not_applicable` 상태와 bounded
    extrapolation 설명을 확인합니다. report digest를 승인한 뒤 카드를 생성합니다.
16. card preview를 확인하고 OpenRadioss `.rad` 또는 Abaqus `.inp`를 다운로드합니다.


## 성공 확인

- Source Raw Asset과 normalized/processed Dataset revision이 서로 다릅니다.
- IR은 exact Property Set과 Processing Output revision을 가리키고, Processing Output은 다시 exact
  Test Data와 Mapping Profile revision을 가리킵니다.
- saved Recipe 경로라면 IR `1.3.0`과 Neutral JSON이 동일한 exact Recipe revision을 가리킵니다.
- Abaqus preview에는 `*DENSITY`, `*ELASTIC`, `*PLASTIC`이 있습니다.
- OpenRadioss preview에는 `/MAT/LAW36`과 hardening function이 있습니다.
- download SHA-256은 card revision의 digest와 같습니다.

`approximated`가 있으면 reference card 생성은 가능할 수 있지만 production release는 별도
domain approval이 필요합니다. `unsupported`가 하나라도 있으면 card를 생성하지 마십시오.

## Canonical Neutral Material JSON 받기

Material Modeling 상단에서 **Export**를 누릅니다. 화면은 현재 Fit 결과를 버리지 않고
exact Material/State와 reviewed Processing Output/IR을 고정한 delivery task로 전환됩니다. 선택한
IR의 origin이 `selected fitted hardening Processing Output`인지 확인한 뒤 **Create Neutral Material
JSON**을 누릅니다. 이 작업은 현재 IR을 다시 fitting하지 않습니다. exact
Test Data revision, Mapping Profile revision, Processing Output revision, 후보 family 조합,
hardening Artifact와 관측/외삽 영역을 하나의 immutable `cmp.neutral-material` revision으로
고정합니다.

완료되면 **Download Neutral JSON r1**으로 JSON을 받습니다. JSON에는 normalized engineering
curve, processed true stress/plastic strain, fitted 영역과 extrapolated 영역이 서로 다른 stage로
들어갑니다. 수동 constant-extension IR은 이 승격 대상이 아니며, 공통 Processing Workbench에서
선택 hardening Output을 먼저 만들어야 합니다. Neutral JSON 생성 뒤 같은 화면에 나타나는
**T-64 · family-neutral solver mapping**에서 target을 고르고 **Run mapping preflight**를 누릅니다.
`approximated`인 bounded extension을 검토·확인한 뒤 카드를 생성하면 Abaqus `*PLASTIC` 또는
OpenRadioss `LAW36` ASCII를 preview하고 내려받을 수 있습니다. 생성 결과에서 **Download native
ASCII card**로 `.inp`/`.rad`를, **Download mapping report JSON**으로 sidecar를 받습니다. 생성 후에는
exact evidence가 접혀 카드가 먼저 보이며 **Review exact evidence and mapping**으로 같은 화면에서
다시 펼칠 수 있습니다. 이 경로는 exact Neutral revision의 fitted/extrapolated stage를 다시
fitting하지 않습니다.
