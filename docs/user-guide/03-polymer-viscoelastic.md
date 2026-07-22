# Polymer 완화시험에서 Abaqus 점탄성 카드까지

## Material Modeling에서 시작하기

상단 **Modeling**에서 **Polymer · Viscoelastic**을 선택합니다. 시험 자료가
`time + relaxation modulus`이면 relaxation Recipe가, `frequency + storage/loss modulus`이면 DMA
Recipe가 선택됩니다. Test Data를 바꾸면 호환 Mapping Profile과 처리 단계도 같이 바뀌므로 서로
다른 시험 형식을 같은 옵션으로 계산하지 않습니다.

DMA에서는 **Fit** 단계에서 Prony 항수 후보를 고르고 storage/loss 응답, joint residual, BIC,
normalized RMSE와 `(g_i, tau_i)` 표를 함께 검토합니다. **Engineer selection**을 사용하면 선택 항수와
이유가 새 Recipe revision에 저장됩니다. 공개 generalized-Maxwell 주파수 응답식을 사용하며 숨은
parameter database나 silent smoothing은 없습니다.


**Export**에서는 현재 선택한 시험 revision에서 승격된 Neutral JSON을 자동으로 엽니다. Abaqus는
`*VISCOELASTIC, TIME=PRONY`를 직접 생성합니다. OpenRadioss는 `/VISC/LPRONY`의 deviatoric-only
근사와 외부 total-strain `/PROP` 요구를 확인해야 생성 버튼이 활성화됩니다.



## 재사용 가능한 Processing Recipe로 후보 비교

1. **Modeling → Data**에서 시험을 고르고 **Process**에서 Polymer relaxation template을
   확인합니다. Recipe Library는 current-step ribbon의 **Advanced · Recipe and Batch**에 있습니다.
2. Test Data JSON의 실제 channel key가 `time_s`, `shear_modulus_mpa`와 다르면 Profile JSON의
   `channel_key`만 실제 이름으로 고칩니다. normalized unit은 각각 `s`, `Pa`여야 합니다.
3. template은 0초 행을 crop한 뒤 관측 범위 안에서만 log-time resampling을 수행합니다.
   시작/끝 시간이 원본 범위를 벗어나면 preview가 실패하며 외삽하지 않습니다.
4. `candidate_term_counts`에 비교할 Prony 항수(각각 1~10)를 지정합니다.
5. `selection_mode`는 `automatic_bic` 또는 `manual`입니다. manual이면
   `selected_term_count`가 후보 목록에 포함돼야 합니다.
6. **Preview all stages**에서 항수별 curve, selected curve, normalized RMSE, BIC, `g_i`, `tau_i`를
   확인합니다. 적합 결과는 reference evidence이며 검토 없이 production-qualified가 되지 않습니다.
7. Mapping Profile과 Recipe를 저장·publish하면 다른 compatible Dataset에 batch 실행할 수 있습니다.
   각 성공/실패와 Output revision은 별도로 남고 원본이나 이전 결과를 덮어쓰지 않습니다.

## 공통 Processing Output을 모델과 카드로 승격

1. **Processing**에서 마지막 step이 `polymer.prony_fit_compare`인 pipeline을 Recipe draft로
   저장하고 publish합니다. exact Test JSON을 선택해 Batch preflight 후 실행합니다. preview나
   Recipe draft 상태만으로는 모델을 만들 수 없습니다.
2. Material의 **Models** 탭에서 **Reviewed Processing Promotion**의 **Exact Processing Output**을
   선택합니다. Output revision과 Artifact digest가 고정되며 서버가 selected 항과 수치를 다시
   읽습니다.
3. 화면의 selection 방식, 항수, normalized RMSE, fitted curve와 catalog 순간 전단계수 G₀의
   불일치율을 확인합니다.
4. **Reviewed maximum G₀ mismatch**에 이 사례에서 허용할 비율을 입력합니다. 이는 전 제품에
   적용되는 silent default가 아니라 사용자가 기록하는 engineering review 결정입니다.
5. review 확인란을 선택하고 **Promote exact Processing Output**을 누릅니다. client가 임의의
   Prony coefficient를 전송해 저장된 Output을 바꿀 수 없습니다.
6. **Saved Material Model IR**에서 exact published Recipe revision, 성공한 Batch Attempt, Output
   revision, selected 항수, RMSE와 G₀ mismatch를 확인합니다. 링크로 Recipe Library/Batch Monitor로
   돌아갈 수 있습니다. 과거 direct Output은 Recipe evidence가 없다고 명시됩니다.
7. **Create Neutral JSON and solver mapping**을 누른 뒤 Abaqus 2025 preflight를 실행하고
   `*VISCOELASTIC, TIME=PRONY` preview와 `.inp`를 내려받습니다. `0.49 <= nu < 0.5`이며 bulk
   relaxation이 미특성화되고 모든 `k_ratio=0`이면 OpenRadioss 2025도 선택할 수 있습니다.
   이 경우 `/PROP I_smstr=10/12` 요구와 shear-only 근사를 확인한 뒤 `/VISC/LPRONY` `.rad`를
   내려받습니다.
8. **Exports**에서 같은 Material의 Test JSON, Mapping Profile, Processing Recipe, Neutral JSON,
   두 solver mapping report와 native card를 선택해 checksum ZIP으로 내려받습니다.






이 경로는 1~10항 공통 Recipe Output을 새 stable Material Model identity의 revision 1로 만듭니다.
아래 기존 bounded two-term Candidate 경로는 과거 자료와 별도의 multistart 진단을 위해 유지되며,
두 경로의 evidence를 서로 바꾸거나 최신값으로 암묵 연결하지 않습니다.

## 온도 이동 모델

Viscoelastic master curve 화면은 세 가지 방식을 제공합니다.

- **Manual:** 각 온도의 검증된 `log10(aT)`를 사용자가 입력합니다.
- **WLF fit:** 세 온도 이상에서 관측 shift를 WLF 식에 적합합니다.
- **Arrhenius fit:** 세 온도 이상에서 `log10(aT)=Ea/(2.303R)(1/T-1/Tref)`를 적합합니다.

Arrhenius 결과 화면에는 활성화에너지(kJ/mol)가 표시됩니다. 각 온도의 observed shift, fitted
shift, residual과 curve alignment RMSE를 함께 검토해야 하며, fitted 온도 범위 밖 사용을 자동으로
정당화하지 않습니다.

## 입력 파일

현재 자동 fitting 경로는 UTF-8 CSV와 다음 두 channel을 사용합니다.

```text
time_s,shear_modulus_mpa
0.01,1000
...
```

예제: `examples/data/reference-shear-relaxation.csv`

- time은 strictly increasing이어야 합니다.
- 현재 bounded reference에서는 shear relaxation modulus가 증가하면 입력을 거부합니다.
- `s`, `ms`, `Pa`, `kPa`, `MPa`처럼 실제 source unit을 mapping 화면에서 명시합니다.

## 절차

1. `polymer` Material, State와 density/E/ν Property Set을 만듭니다.
2. **Shear-relaxation Dataset**에서 Specimen과 Test Run을 만듭니다.
3. CSV를 업로드하고 time/modulus column과 unit을 승인합니다.
4. raw Dataset과 normalized SI Dataset을 확인합니다. 두 representation은 별도 identity입니다.
5. 필요한 observed time range를 입력하고 crop Recipe/Run을 실행합니다. 이 step은 interpolation을
   수행하지 않으며 output은 별도 processed Dataset입니다.
6. 여러 온도/반복시험을 처리하려면 아래 **다온도 master curve** 절차를 실행합니다. 한 curve
   fitting만 필요하면 이 단계는 생략할 수 있습니다.
7. 새 공통 경로는 위 절차대로 saved `polymer.prony_fit_compare` Output을 승격합니다. 기존
   bounded 경로를 사용할 때만 baseline linear-Prony IR을 만들거나 compatible baseline을 선택합니다.
8. 기존 bounded 경로에서는 processed 또는 검토한 master Dataset으로 deterministic multistart
   calibration을 실행합니다.
9. Candidates의 objective, RMSE, fitted curve, residual, convergence, bound와 identifiability
   warning을 비교합니다.
10. 수치가 가장 작다는 이유만으로 선택하지 말고 engineering 판단 이유를 입력해 Candidate를
   선택합니다.
11. 선택된 evidence를 같은 Material Model identity의 새 IR revision으로 승격합니다.
12. Abaqus 2025 mapping preflight를 실행하고 `.inp` preview/download를 확인합니다.

## 다온도 반복시험과 master curve

1. 각 반복 curve를 별도의 Test Run과 normalized shear-relaxation Dataset으로 등록합니다.
   Test Run에는 반드시 실제 시험 온도(K)를 입력합니다.
2. Material State 화면의 **Viscoelastic master curve**에서 둘 이상의 온도에 걸친 curve를
   선택합니다. 원본과 normalized revision은 이 선택으로 변경되지 않습니다.
3. reference temperature를 선택합니다.
4. 온도별 검증된 shift가 있으면 **Manual shift factors**에서 각 `log10(aT)`를 입력합니다.
   reference temperature의 값은 0으로 고정됩니다.
5. 세 개 이상의 서로 다른 온도가 있고 reference WLF 추정이 필요하면 **WLF fit**을 선택합니다.
   이는 deterministic reference fit이며 재료의 유효 온도 범위를 자동 승인하지 않습니다.
6. **Create Selection, process statistics and master curve**를 실행합니다.
7. 결과 표에서 온도별 `n`, shift 방법/값, sample standard-deviation band와 outlier 상태를
   확인하고 shifted replicate와 master curve를 검토합니다.

처리는 각 온도 curve의 공통 log-time 교집합에서만 선형 보간하며 외삽하지 않습니다. 결과는
aligned Dataset, pointwise-statistics Dataset, master-curve Dataset과 shift evidence로 나뉘어
immutable revision으로 저장됩니다. 온도별 curve가 겹치지 않거나 시험 온도가 누락되면 Run을
만들지 않습니다.







## 중요한 제한

- 공통 Recipe는 1~10항 후보를 비교하고 기존 calibration은 bounded two-term reference fitting을
  유지합니다. 어느 결과도 곧바로 production-qualified Prony parameter를 뜻하지 않습니다.
- uncertainty가 `unassessed`이거나 identifiability warning이 있으면 그대로 보존됩니다.
- linear-Prony IR은 OpenRadioss LAW62로 변환되지 않습니다.
- T-44의 반복 승격 계약은 governed Ogden Candidate 흐름에 먼저 적용되었습니다. 이 문서의
  bounded linear-Prony 흐름은 아직 기존 단일 승격 guard를 유지하므로 promoted r2의 재승격은
  안전하게 거부됩니다.

## 기존 bounded Candidate를 Neutral JSON으로 승격

Candidate를 선택하고 같은 Material Model identity의 새 IR revision으로 승격한 뒤 **Create
Neutral Material JSON**을 누릅니다. 수동 baseline만 있는 상태에서는 버튼을 사용하지
마십시오. Neutral 승격에는 reviewed Candidate와 diagnostics digest가 필요합니다.

생성된 `generalized_maxwell` 문서는 exact Prony Plan/Run/Candidate, processed shear-relaxation
Dataset revision과 Artifact digest, observed/fitted/residual curve, ordered `(g_ratio, k_ratio,
relaxation_time)` 항, reference temperature와 유효 time domain을 보존합니다. **Download Neutral
JSON r1**으로 받으며, validate/import 시 어느 digest나 수치가 달라져도 거부됩니다. 현재
Neutral JSON 생성 뒤 같은 화면의 **T-64 · family-neutral solver mapping**에서 Abaqus 2025를
선택하면 ordered Prony term을 `*VISCOELASTIC, TIME=PRONY` ASCII로 preview·download할 수 있습니다.
ADR-0032 조건을 만족하는 nearly-incompressible shear-only 자료는 OpenRadioss 2025
`/MAT/LAW1` + `/VISC/LPRONY` fragment로도 내보낼 수 있습니다. `/PROP I_smstr=10/12`는 외부 모델
요구사항이며 CMP가 만들거나 수정하지 않습니다. 조건을 벗어나면 `unsupported`이고, LAW62를
만들기 위해 hyperelastic base나 bulk relaxation 값을 임의로 보충하지 않습니다.
