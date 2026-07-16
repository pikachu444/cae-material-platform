# Polymer 완화시험에서 Abaqus 점탄성 카드까지

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
6. baseline linear-Prony IR을 만들거나 기존 compatible baseline을 선택합니다.
7. processed Dataset으로 bounded deterministic multistart calibration을 실행합니다.
8. Candidates의 objective, RMSE, fitted curve, residual, convergence, bound와 identifiability
   warning을 비교합니다.
9. 수치가 가장 작다는 이유만으로 선택하지 말고 engineering 판단 이유를 입력해 Candidate를
   선택합니다.
10. 선택된 evidence를 같은 Material Model identity의 새 IR revision으로 승격합니다.
11. Abaqus 2025 mapping preflight를 실행하고 `.inp` preview/download를 확인합니다.

![시험 등록과 processing](../15-demo/images/e2e-shear-workflow.png)

![Calibration Candidates](../15-demo/images/e2e-prony-candidates.png)

![Fitted curve와 residual](../15-demo/images/e2e-prony-diagnostics.png)

![Abaqus VISCOELASTIC card](../15-demo/images/e2e-abaqus-card.png)

## 중요한 제한

- 현재는 한 curve의 bounded two-term reference fitting입니다. 반복 relaxation 통계와
  temperature master curve는 T-42에서 추가합니다.
- uncertainty가 `unassessed`이거나 identifiability warning이 있으면 그대로 보존됩니다.
- linear-Prony IR은 OpenRadioss LAW62로 변환되지 않습니다.
- promoted r2를 다시 승격하는 iterative workflow는 T-44 전까지 안전하게 거부됩니다.
