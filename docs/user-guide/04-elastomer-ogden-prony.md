# Elastomer Ogden--Prony 카드

Elastomer workflow는 uniaxial/planar/biaxial normalized curve를 한 화면에서 비교하고
Neo-Hookean, Mooney--Rivlin, Yeoh, one-term Ogden을 fitting하는 `reference/non-production`
수직 기능입니다. 저장된 Plan을 열면 calibration/holdout 역할, mode와 weight, reviewed Run과
선택된 diagnostics가 자동 복원됩니다. 일반 사용자는 Run ID를 입력할 필요가 없습니다.
shear-Prony term은 baseline IR에서 별도 시간 의존 overlay로 보존·표시됩니다.

## 초탄성 모델 family 비교

동일한 calibration/holdout Dataset revisions를 대상으로 Neo-Hookean, Mooney--Rivlin, Yeoh,
one-term Ogden을 한 번에 비교할 수 있습니다. Run을 실행하면 **T-55E public hyperelastic
families** 표에 family별 parameter, normalized RMSE, fitted-domain monotonicity와 warning이
표시됩니다. family 행을 선택하면 서버가 보존한 immutable diagnostics Artifact에서
observed/fitted curve와 residual을 불러옵니다. 가장 낮은 objective는 참고값일 뿐 자동 승인
또는 자동 승격되지 않습니다. 검토한 family 행을 선택하면 T-56 영역에서 선택 사유를 남기고
canonical Neutral Material JSON/IR revision으로 승격할 수 있습니다. family별
Abaqus/OpenRadioss mapping/card는 이 Neutral revision을 직접 소비합니다. 기존 Ogden 행의 사람 선택,
Ogden--Prony IR revision과 두 solver card 경로는 계속 사용할 수 있습니다.


**Response / Residual** 탭에서 measured point, fitted curve와 residual을 전환합니다. 색상은
시험 mode를, legend의 역할은 calibration/holdout을 구분합니다. `+`, `−`, **Reset**으로 graph
domain을 검토할 수 있으며 point에 마우스를 올리면 strain과 nominal stress가 표시됩니다.


복구·진단 상황에서만 **Advanced recovery and Neutral JSON interchange**를 열어 exact Run ID나
기존 Neutral JSON을 지정합니다. 이 영역은 정상 modeling 절차에서는 사용할 필요가 없습니다.

## Calibration Plan 저장·재사용

**Saved Calibration Plan library**에는 현재 Material State와 baseline model identity에 속한 Plan의
current immutable revision이 표시됩니다. **Use exact revision**을 누르면 당시 고정한 Dataset
revision, calibration/holdout 역할, 시험 mode와 curve weight를 폼에 복원합니다. 설정을 바꾸지
않고 아래 **Execute Ogden Calibration Run**을 누르면 그 exact Plan revision을 다시 실행합니다.

역할, mode 또는 weight를 바꾼 뒤 **Save new Plan revision**을 누르면 같은 stable Plan identity에
새 revision이 추가됩니다. 기존 revision과 그 revision을 사용한 Run은 수정되지 않습니다. 다른
작업자가 먼저 Plan을 수정했다면 compare-and-swap 검사가 충돌을 반환하므로 **Refresh inputs**로
current revision을 다시 읽어야 합니다. 별도 Plan을 만들려면 **New Plan**을 누릅니다.


## 절차

1. Material class를 `elastomer`로 만들고 State/Property Set을 준비합니다.
2. **Ogden--Prony** 영역에서 positive finite `mu`, `alpha`와 ordered Prony terms를 입력합니다.
3. shear ratio 합이 1 미만이고 relaxation time이 양수·strictly increasing인지 확인합니다.
4. exact Material/State/Property revision으로 immutable IR을 만듭니다.
5. target을 선택합니다.
   - Abaqus 2025: `*HYPERELASTIC, OGDEN, N=1`과 `*VISCOELASTIC`
   - OpenRadioss 2025: `/MAT/LAW62`
6. mapping report를 확인하고 report digest를 승인한 뒤 card를 생성합니다.
   `approximated` 또는 `ignored` 항목이 있으면 화면의 검토 확인을 해야 생성 버튼이 활성화됩니다.
7. preview와 `.inp` 또는 `.rad` download를 확인합니다.



## Multi-test fitting 절차

Docker demo에서 공개 합성 입력과 완료된 fitting 화면을 빠르게 준비하려면 저장소 루트에서
다음을 실행할 수 있습니다. 이 명령은 실제 회사 데이터가 아니라 해석식으로 생성한
uniaxial/planar/biaxial calibration 3개와 uniaxial holdout 1개를 immutable evidence로
추가합니다. 세 loading mode는 각각 `reference_uniaxial_tensile`,
`reference_planar_tension`, `reference_biaxial_tension` Test Method revision으로 구분되며,
Dataset schema만 바꾸어 시험 의미를 가장하지 않습니다.

```bash
uv run python scripts/seed_ogden_calibration_demo.py
```

1. 같은 Material State의 각 시편에 Test Run을 만들고 **Governed tabular import**에서 CSV,
   TSV 또는 XLSX 원본을 보존합니다.
2. column과 unit을 명시해 별도 normalized Dataset revision을 생성합니다. 현재 지원 mode는
   `monotonic_tension`(uniaxial), `planar_tension`, `biaxial_tension`입니다.
3. 먼저 manual Ogden--Prony baseline IR을 만듭니다. 이 revision이 density, State와
   shear-Prony evidence를 고정합니다.
4. **Calibration profile**에서 reference profile을 생성하거나 기존 revision을 확인합니다.
   bounds, scaling, mode weights, multistart seed와 uncertainty policy가 이 revision에 고정됩니다.
5. **Multi-test Ogden calibration**에서 사용할 normalized curve를 선택하고 각 항목의 역할을
   `calibration` 또는 `holdout`으로 지정합니다. Dataset revision은 두 역할에 중복될 수 없습니다.
6. 새 설정이면 **New Plan**에서 immutable Plan을 생성합니다. 기존 설정이면 **Saved Calibration
   Plan library**에서 **Use exact revision**을 누르고 그대로 실행하거나, 설정을 수정해
   **Save new Plan revision**으로 append한 뒤 Run을 실행합니다.
7. Candidate별 `mu`, `alpha`, objective, per-mode error, convergence, Jacobian rank,
   identifiability, uncertainty/95% CI와 warning을 비교합니다.
8. observed/fitted nominal-stress curve와 residual plot을 확인합니다. single-mode이면
   `insufficient test modes`, holdout이 없으면 `no holdout data`가 명시됩니다.
9. Candidate row를 눌러 diagnostics를 고른 뒤 fitted/residual, holdout, convergence, bounds,
   rank와 uncertainty를 검토합니다. 시스템은 가장 작은 objective를 자동 승인하지 않습니다.
10. **Promote the reviewed family to Neutral Material JSON**에서 family 선택 사유와 change
    reason을 기록하고 승격합니다. 새 stable Neutral model identity의 revision 1이 생성되며,
    exact Plan/Run/Candidate/Dataset/diagnostics digest, curve stage, parameter와 적용 범위가
    `cmp.neutral-material` 문서에 고정됩니다.
11. 화면에 표시된 Dataset revision 수, curve stage 수, validation 상태와 content SHA-256을
    확인한 뒤 **Download Neutral Material JSON**으로 canonical JSON을 받습니다. 기존 JSON은
    상단 import 영역에서 검증 후 다시 가져올 수 있으며 참조 digest가 다르면 거부됩니다.
12. 이어지는 **Generate a native solver card from this exact Neutral revision**에서 Abaqus 2025
    또는 OpenRadioss 2025를 고르고 **Run mapping preflight**를 실행합니다.
13. 모든 mapping item의 `exact`, `transformed`, `approximated`, `ignored`, `unsupported`,
    `not_applicable` 상태를 확인합니다. OpenRadioss LAW82 경로처럼 근사가 있으면 확인 체크를
    해야만 **Create solver card**가 활성화됩니다.
14. 생성 후 ASCII preview를 확인하고 native `.inp`/`.rad`와 mapping report JSON을 각각
    다운로드합니다. Card는 exact Neutral revision과 preflight SHA-256을 고정합니다.
15. 기존 Ogden 전용 경로가 필요하면 **Human decision gate**에서 Selection label과 검토 사유를 기록합니다. Selection revision은
    exact Run/Candidate/candidate digest/diagnostics Artifact digest/baseline IR revision을 pin합니다.
16. IR promotion reason을 입력하고 승격합니다. 요청은 화면이 읽은 current IR의 strong ETag를
    사용하므로 다른 사용자가 먼저 새 revision을 만든 경우 412로 거부되고 새로고침이 필요합니다.
17. **Append-only IR revision history**에서 r1, r2, r3를 비교합니다. 각 promoted revision은
    자신의 Selection/Run/Candidate/diagnostics evidence만 소유하며 과거 evidence를 복사하거나
    덮어쓰지 않습니다. 과거 IR에서 만든 Card와 Release는 그 concrete revision을 계속 pin합니다.



두 번 이상의 calibration round를 회귀 데이터로 확인하려면 아래 명령을 두 번 실행할 수 있습니다.
각 실행은 실행 시점의 current IR을 새 baseline으로 pin하고 r2, r3처럼 새 revision을 추가합니다.

```powershell
uv run python scripts/seed_ogden_calibration_demo.py --promote
uv run python scripts/seed_ogden_calibration_demo.py --promote
```





입력 strain은 engineering strain(무차원), stress는 nominal stress(Pa)로 해석합니다. 현재
one-term incompressible public reference equation만 지원하며 compression, simple shear,
compressible/temperature-dependent fit과 실제 solver 검증은 이 범위가 아닙니다.


## Mapping 해석

- Abaqus 2025는 네 family를 각각 `NEO HOOKE`, `MOONEY-RIVLIN`, `YEOH`, `OGDEN, N=1`으로
  직접 내보내며 incompressible volumetric coefficient를 0으로 명시합니다.
- OpenRadioss 2025는 Neo-Hookean/Yeoh를 LAW94로, Mooney--Rivlin/Ogden을 LAW82로 내보냅니다.
- LAW94 Neo-Hookean과 LAW82 Mooney--Rivlin coefficient 변환은 `transformed`이지만 문서화된
  strain-energy 등가식입니다. LAW82의 `nu=0.495`는 별도 `approximated` 항목입니다.

- Ogden μ/α와 shear-Prony는 두 target에서 explicit mapping입니다.
- Abaqus의 incompressible `D1=0`은 현재 reference convention에서 exact입니다.
- OpenRadioss LAW62는 volumetric response를 `nu=0.495`로 표현하므로 `approximated`입니다.
- 이 근사는 반드시 화면과 mapping report에 남으며 production 승인을 의미하지 않습니다.

선형 점탄성 IR을 LAW62로 우회시키거나 없는 bulk relaxation 값을 추측해서 입력하지 마십시오.

## Hyperelastic Neutral JSON의 Prony overlay

T-63 이후 reviewed hyperelastic family를 Neutral Material로 승격하면 calibration baseline의
exact Ogden-Prony model revision과 ordered shear-Prony 항도 `prony_overlay`로 함께 보존됩니다.
overlay가 없는 것처럼 생략하거나 다른 revision의 항을 조합하지 않습니다. 기존 1.0
hyperelastic Neutral JSON은 canonical bytes를 바꾸지 않고 계속 읽을 수 있습니다.

T-64 통합 mapping/report는 exact Prony overlay를 Abaqus native card에 포함합니다. OpenRadioss
LAW62는 한 항 Ogden base일 때만 허용합니다. Neo-Hookean, Mooney–Rivlin 또는 Yeoh overlay를
LAW62로 변환하려 하면 preflight가 `unsupported`로 차단하며 다른 potential로 조용히 바꾸지
않습니다. Neutral JSON 생성 뒤 **T-64 · family-neutral solver mapping**에서 report를 확인하고
native ASCII를 preview·download하십시오.
