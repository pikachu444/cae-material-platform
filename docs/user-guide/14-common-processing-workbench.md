# 시험 데이터 처리와 모델 비교하기

이 화면은 시험 데이터를 선택하고 처리 결과와 모델 후보를 비교하는 작업을 제공합니다.
입력은 저장된 `cmp.test-data`의 정확한 revision이며, 브라우저에서 계산한 임시 값이 아니라
서버가 반환한 각 처리 단계의 수치와 진단을 비교합니다.

일반 사용자는 전역 **Modeling**(`/modeling`)에서 이 엔진을 사용합니다. 이 화면은
`Data | Process | Fit | Export`와 Metal/Polymer/Elastomer track을 제공합니다. Data와 여러 처리
단계가 있는 Process는 compact curve/process tree를 사용합니다. 한 단계뿐인 DMA TTS Process와
Fit은 그 폭을 그래프와 결과 확인에 돌려줍니다.
`/datasets/processing`은 같은 통합 Modeling 화면으로
연결되는 기술 호환 route입니다. 재료군을 바꾸면
기존 Test Data 선택이 해제되므로 새 track과 호환되는 exact revision을 명시적으로 다시 고릅니다.


Data와 여러 단계 Process의 왼쪽에는 현재 재료군과 호환되는 시험 curve 및 Process 단계가 있고,
나머지 폭은 실제 서버 계산 결과를 표시하는 engineering graph입니다. 한 단계 DMA TTS Process와
Fit은 왼쪽 rail 없이 전체 폭의 graph와
아래 후보 비교·엔지니어 선택 영역을 사용합니다. 선택 단계 설정은 graph 위의 얕은 band에 있고
영구적인 오른쪽 열은 없습니다. 1366 px에서도 graph 축·눈금·범례가 첫 화면에
모두 보입니다. Process 범례는 x축 값과 제목을 가리지 않는 아래쪽 여백 위에 작게 놓입니다. 일반 작업에서는 내부 주소,
토큰 또는 식별자를 입력하지 않습니다. 범례를 눌러 series를 숨기거나 표시하고, plot을
드래그해 이동하며 wheel 또는 `Zoom in/out`으로 확대하고 `Reset`으로 전체 범위로 돌아갑니다.

Data와 여러 단계 Process 왼쪽 Navigator의 divider를 끌어 폭을 바꾸고 **Collapse navigator**로 접을 수 있습니다. divider를
두 번 누르거나 **Reset navigator**를 실행하면 현재 표시 밀도의 공통 기본 폭으로 돌아갑니다. 이
배치는 같은 브라우저에서 route 이동과 reload 뒤에도 유지되며 표시 밀도 reset과는 별개입니다.
Data/Process/Fit graph는 Navigator, ribbon, candidate evidence pane 또는 표시 밀도가 바뀔 때 실제
container를 다시 측정해 frame, SVG viewBox, axis, legend, label과 pointer hit region을 함께 갱신합니다.
Data의 열 연결을 검토하는 짧은 graph에서는 실제 SVG 높이에 맞춰 y축 눈금 수를 줄입니다. 1366×768에서도
눈금값·축 제목·frame이 겹치지 않으며, 더 큰 화면에서는 기존 engineering 눈금 간격을 유지합니다.

Data의 **Library**에서는 검색과 시험 종류·조건으로 목록을 좁히고, 표에서 현재 입력 하나를
고른 뒤 그래프를 확인하고 **Continue to Process**로 이동합니다. 다른 곡선은 **Add comparison**을
연 경우에만 그래프에 더할 수 있으며 현재 Process 입력은 바뀌지 않습니다. **Local file**은 별도
입력 경로이며 source 선택과 mapping 작업을 같은 local surface 안에 유지합니다. 여기서 native file
input으로 파일을 고르고 exact **Test record**를 선택한 뒤 **Inspect file**로 내용을 읽습니다. 파일이나
Test record를 다시 고르기 전까지 현재 exact 선택과 마지막 유효 graph는 그대로 유지됩니다. **Match file columns**
아래에서 잘못된 열 연결의 원인과 고칠 항목을 하나의 안내 블록으로 해당 위치에 표시하면서 마지막
유효 그래프를 유지합니다. 이 안내는 mapping controls보다
먼저 읽을 수 있습니다. 긴 source column은 native select 안에서 줄여 보여도
선택한 원문, keyboard focus, file unit과 modeling unit을 같은 decision table에서 유지합니다. DMA 형식에서는 제공된 경우 **Include optional tan delta
channel**을 선택할 수 있으며, 이 선택과 focus는 같은 local mapping 영역에서 유지됩니다. 선택한 시험과 실제로 연결된 소재 자료, 다른 시험,
해석·모델 결과와 솔버 카드는 왼쪽
**Related data**에 종류별로 나타납니다. 정확한 revision과 내부 식별 정보는 화면에 반복하지 않고
접힌 **Technical details**에 둡니다. 넓은 화면에서는 목록과 작업 흐름의 가독성을 유지하면서
그래프만 비교에 유용한 범위까지 커집니다.

이 **Match file columns** 영역의 CSS 소유권 이동은
[#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
다섯 viewport 원본, 내부 scroll-end 상태, 직접 crop과 exact journey read-back으로 기록합니다. 화면의
문구·선택·revision·graph·복구 흐름과 좁은 화면의 의도된 내부 스크롤은 바꾸지 않습니다.

유효한 column 연결 뒤 표시되는 **Columns ready · Change mapping · Update preview** 영역의 CSS 소유권
이동은 [#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
다섯 viewport 원본, 안정 상태, 직접 crop과 exact journey read-back으로 기록합니다. 이 compact 상태는
내부 스크롤이 필요하지 않지만, Local file 영역의 기존 keyboard scroll 계약은 그대로 유지합니다.

**Choose data file · Test record · Save details · JSON result**에 공통으로 쓰이는 Data intake field-row의
CSS 소유권 이동은 [#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
다섯 viewport 원본과 header/source/controls/graph 직접 crop으로 기록합니다. 정확한 Test Data와 revision,
Update preview, graph, reload 복구와 Data→Process→Data 흐름은 바꾸지 않습니다.

**Match file columns** 결정 프레임의 CSS 소유권 이동은
[#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
다섯 viewport 원본과 header/navigator/controls/Save details/graph 100% crop으로 기록합니다. 1366 화면의
Data 설정 내부 스크롤, Test type focus, 정확한 선택·revision, #309 graph와 Process 왕복은 그대로 유지합니다.

Data 설정이 길어지면 위 설정 영역만 스크롤합니다. 설정과 그래프 사이 가로 구분선은 pointer 또는
키보드로 높이를 조절할 수 있으며, 이때도 선택한 Test Data, 현재 그래프와 exact revision은 바뀌지
않습니다. Local file의 긴 column mapping도 이 한 개의 키보드 스크롤 영역 안에서 이동하며, 바깥
Data ribbon과 그래프에는 별도 중첩 스크롤을 만들지 않습니다.

Local file의 column 연결이 유효하면 **Save details**에서 변경 사유를 입력하고 **Update preview**로
마지막 유효 그래프를 다시 확인한 뒤 **Save Test Data**를 실행합니다. 사유를 입력하기 전에는 preview가,
preview를 갱신하기 전에는 저장이 각각 비활성화됩니다. 이 순서는 현재 Test record와 그래프를 유지한 채
mapping 변경을 명시적으로 검토하도록 합니다.

Local file의 **File details**는 평소 접혀 있습니다. 펼치면 file parsing, 원본 column, Mapping Profile,
Raw asset와 hash, specimen, exact Test Run 및 raw table을 확인할 수 있습니다. 이 상세 증거를 열거나
접어도 선택한 Test Data와 그래프는 바뀌지 않으며, 내용이 길면 Data 설정 영역 안에서만 스크롤합니다.

그래프에서 처리 범위를 지정하려면 Recipe 단계(예: **Metal elastic modulus**)를 먼저 고르고
**Select range**를 누른 뒤 x-domain을 드래그합니다. necking처럼 한 점을 고르는 단계는
**Pick point**를 사용합니다. 선택 영역과 marker는 임시 상태이며 **Apply selection**을 눌러야
호환되는 Recipe step option으로 들어갑니다. 이때도 원본이나 저장된 Recipe revision은 바뀌지
않습니다. **Advanced · Recipe and Batch**에서 새 revision으로 저장해야 선택을 재사용할 수 있습니다.
option 변경은 300 ms 동안 모아서 서버 preview를 다시 계산하며, 그 사이 더 최신 변경이 오면
이전 계산 요청은 취소됩니다.

인장 시험 초반의 toe 구간을 보정할 때는 Process Navigator의
**Add tensile toe compensation**을 직접 누릅니다. 이 단계는 자동으로 켜지지 않습니다. 사용자가 고른
Estimation start/end 구간에서 `σ = Eε + b`, `ε₀ = −b/E`를 계산하고 출력 strain만
`ε − ε₀`로 옮깁니다. 원본 Test Data와 stress 값은 그대로 유지됩니다. Preview 뒤에는 offset,
Slope E, R²와 사용한 point 수가 Result에 나타나고, graph에는 mapped input, 보정 결과와
평가 직선이 함께 표시됩니다. R²가 0.995보다 작거나 offset 절댓값이 선택 구간 폭보다 크면 품질
경고를 검토해 acknowledgement를 선택하고 다시 Preview해야 저장할 수 있습니다. 구간을 바꾸면
acknowledgement가 해제되고 마지막 정상 graph는 남지만 저장은 새 Preview까지 차단됩니다. 저장한
Processing Output은 exact revision으로 Fit에 전달되며 기술 정보는 **Calculation settings** 또는
**Evidence**에서 확인할 수 있습니다. Equipment compliance는
추정하지 않고 `Not provided`로 기록합니다.

Material Database의 Material 상세에서 State 아래 **Open in Material Modeling**을 누르면 해당
Material/State exact revision이 자동으로 선택됩니다. Test Data JSON 목록의 **Open in Material
Modeling**은 해당 Test Data exact revision을 같은 방식으로 전달합니다. 화면을 다시 열어도 최근
Material, State, Test Data, Mapping Profile과 Recipe exact revision을 복원하며, 저장된 revision이
현재 선택 가능한 head와 다르면 조용히 최신값으로 바꾸지 않고 검토 경고를 표시합니다.

금속 **Metal elastic modulus** 단계에서는 current-step settings ribbon의 native **Evaluation method**
select에서 Auto robust, Linear regression, Chord, Secant, Manual slope를 선택합니다. 내부 값은
`robust_huber`, `linear_regression`, `chord`, `secant`, `manual`로 유지되며 Start/End strain은 같은
Calculation group에 놓입니다. 그래프의 **Select range**로도 같은 구간을 정할 수 있습니다. Manual
slope의 값·unit·engineering reason은 두 번째 줄에 나타나며 키보드 순서는 value → unit → reason입니다.
GPa/MPa 입력은
canonical Pa로 변환해 실제 계산에 사용합니다. 선택한 necking point도 point index와 reason을 요구합니다.
두 수동 workup은 원값/원 단위·canonical 값/단위·사유를 `workup_overrides`로 Processing Output revision과
다운로드 Artifact에 함께 고정합니다. **Offset proof stress**는 선택한 offset/search range의 curve-derived
값만 사용합니다. 직접 manual yield 값은 production yield-definition contract가 승인되기 전까지 제공하지 않습니다.
**Engineering to true/plastic**은 necking boundary와 음의 plastic strain 정책을 설정합니다. 이 physical
workup은 Metal elastoplastic Process에만 보이며 Fit, Polymer, Elastomer에는 노출하지 않습니다. **Metal hardening candidates**에서는 Voce/Swift/Hockett-Sherby/Ghosh, primary/secondary,
혼합비와 외삽 strain을 직접 바꿉니다. 모든 조작은 Recipe draft와 서버 preview에 반영됩니다.

실제 Metal Fit은 저장된 Process-only Processing Output의 exact `id/rN`과 digest를 소스로
사용합니다. 서버는 true plastic strain(unit `1`)과 true stress(Pa)를 같은 normalized
least-squares objective로 네 law에 적용하고, 각 후보의 response·predicted-minus-observed
residual·analytical tangent, Lower/Initial/Fitted/Upper, RMSE, convergence/nfev, active bound,
Jacobian rank/condition, identifiability와 `uncertainty=not_provided`를 Fit evidence로 반환합니다.
Ghosh는 `k_pa`, `epsilon_0`, `delta_p_minus_n`만 저장하며 `plastic strain < epsilon_0`를 벗어나면
차단합니다. 추천은 선택과 별도이고, 저장에는 단일 law 또는 strict two-law blend와 사유·warning
acknowledgement가 모두 필요합니다. exact source/digest 또는 계산·저장이 실패해도 마지막 정상
graph와 입력을 유지하며 명시적인 Retry action만 재시도합니다.

Polymer는 선택한 데이터가 TTS를 요구하는지 먼저 판별합니다. 완화시험과 한 온도의 DMA 주파수
자료는 **Fit**으로 바로 가고, 한 주파수에서 여러 온도를 측정한 DMA 자료만 **Process**에서 master
curve를 만든 뒤 **Fit**으로 갑니다. Fit의 정상 흐름은 **입력 확인 → Calculate Prony models →
후보 비교와 엔지니어 선택 → Save fit & continue**입니다. 서버가 데이터로 가능한 1~10항 후보를
자동 계산하므로 사용자가 3항이나 5항을 먼저 정하지 않습니다. Response curves/Point differences와
Fit difference·Check difference,
적용 범위, Recommendation을 비교하고 엔지니어가 모델과 이유를 선택합니다. 내부 식별자, digest,
원시 최적화 점수와 반복 설명은 정상 화면에 표시하지 않습니다. 후보와 파라미터 범위를 직접 바꾸는
작업은 전문가용 **Calculation settings**에만 둡니다.

백엔드 #391은 여러 DMA 등온선을 하나의 exact multi-isotherm Processing Output으로 정렬하고,
CALIBRATION 행만 다음 Polymer Fit의 Prony 입력으로 제공합니다. 이 단위에는 React 화면을 포함하지
않으며, 해당 Process 연결 UI는 #392에서 진행합니다. 명시적인 한 주파수 sweep 안에서는 대표 온도와
각 실측 온도의 차이를 `0.5 K`까지 허용하되 실측값을 수정하지 않고 모두 보존합니다. 이 범위를 넘는
sweep은 서로 다른 온도 자료가 섞이지 않도록 전체를 차단합니다.

Metal Fit 상단 상태는 `Calculating`(계산 중), `Saved current`(정확한 Fit Output 복원과 사용 가능한
preview가 모두 검증됨), `Preview not saved`(현재 preview만 사용 가능), `Saved result stale`(Fit
history는 있으나 현재 preview/pointer가 검증되지 않음), `Not calculated`(그 밖의 상태)로 고정됩니다.
복원 read 실패는 `Saved current`가 될 수 없고, 저장 실패는 현재 preview를 유지하되 `Preview not saved`로
남습니다. 정확한 saved Fit을 복원한 직후 자동 preview 조건이 다시 평가되더라도 복원된
`Saved current` graph와 pointer를 새 계산으로 덮어쓰지 않습니다. 사용자가 입력을 바꾸고
**Recalculate**를 실행한 경우에만 새 계산이 시작됩니다.

Data와 여러 단계 Process의 왼쪽 **Curves** rail은 `N curves · N included` 요약 뒤 시험 방법 그룹과
specimen별 26 px tree 행을 표시합니다. 예를 들어 tensile 문서는 `Tensile tests` 아래에 놓입니다.
온도·변형률 속도 조건은 서버가 정확한 조건 메타데이터를 제공할 때만 하위 그룹으로 보이며 화면이
추정하지 않습니다. 시편 행은 들여쓰기로 계층을 표현하며 `└`/`ㄴ` 문자를 제목 앞에 붙이지 않습니다.
시험 방법 그룹은 실제로 접고 펼칠 수 있는 native disclosure이며 키보드로도 작동합니다. 각 행의 checkbox는 **Include in processing/fit**이고, 끝의 눈 아이콘은 **Show on plot**만
바꿉니다. 제목 오른쪽의 짧은 가로 색상 표본은 해당 curve의 plot 색상만 나타내며 제목 앞에 기호처럼 붙지 않습니다. 따라서 line을 숨겨도 fitting 포함 여부는 바뀌지 않습니다. 행에는 specimen 이름과 exact revision을
짧게 표시합니다. Data는 specimen과 exact revision을 두 줄로, Process는 `Specimen 0N · rN` 한 줄로
표시하므로 hover 없이도 현재 선택 identity를 확인할 수 있습니다. Fit의 입력 이름은 graph 위의
얕은 band에 한 번만 표시합니다. 긴 curve 이름은 이름 줄만 말줄임표로 정리하고 exact revision과
선택·키보드 focus 상태는 유지하므로, graph를 오가거나 화면을 다시 열어도 현재 입력을 구분할 수 있습니다.
이 rail은 Validate, Review와
Export에는 표시하지 않습니다. Process에서 호환되는 포함 curve가 두 개 이상일 때만 **Replicate analysis**를 열고 **Preview mean & band**를
누를 수 있습니다. 그러면 가운데 plot이 **Mean & band** 보기로 전환되어 개별 curve,
pointwise mean과 서버 metadata에 기록된 confidence band를 함께 표시합니다. 범례와 tooltip은
고정 문구 대신 method, confidence level, pointwise/simultaneous 여부와 source count를 읽습니다. 이 계산에는 `rows.*`와 `curve.*`
공통 전처리만 적용되며, hardening이나 Prony 같은 모델 fitting 단계는 반복 실행하지 않습니다.

Fit의 **Calculation settings**는 필요할 때만 bounded drawer로 열립니다. 긴 파라미터 표는 drawer
안에서 독립적으로 스크롤하고 model과 column heading을 유지합니다. Drawer는 닫기 버튼과 `Escape`를
지원하고 닫은 뒤 원래 control로 focus를 돌려줍니다.


## 처리 미리보기

1. `Modeling → Data`를 열고 Library, local CSV/TSV/XLSX 또는 Advanced canonical JSON 입력을 선택합니다.
2. local file은 **Raw source inspector**에서 sheet/header/decimal, sample table, Raw Asset checksum을 확인합니다.
3. **Axis and unit mapping decision table**에서 source column, axis/quantity semantics, raw unit, normalized unit과 상태를 확인합니다. 수동 해석은 변경 이유를 함께 기록합니다.
4. Test Run, specimen, 수행 시각과 편집 provenance를 확인하고 필요하면 secondary preview를 갱신합니다.
5. **Save dataset**으로 raw source와 mapping을 참조하는 새 Test Data revision을 만듭니다. 이는 review가 아닙니다.

DMA frequency-temperature sweep를 고르면 decision table이 Temperature·Frequency Independent와
Storage modulus·Loss modulus Dependent 행을 표시하고, 필요할 때만 **Include optional tan delta
channel**을 켭니다. FLD는 Minor strain Independent와 Major strain Dependent를 별도 schema 의미로
표시합니다. DMA graph는 response 비교를 위해 frequency를 series 축으로 다루지만, 저장된 canonical
Test Data에는 frequency channel과 모든 exact source pin이 그대로 남습니다. FLD의 signed strain과
비단조 입력은 유지됩니다.

저장 실패 시 file, sheet/header, mapping, provenance와 graph preview를 유지하므로 원인을 고치고
같은 입력으로 다시 시도할 수 있습니다. mapping 변경은 Process부터 Export까지의 current pointer를
stale/clear하며 이전 immutable revision은 history에 남습니다.

잘못된 channel mapping이 길어지면 setup 안의 실제 local scrollbar로 validation과 recovery action까지
이동할 수 있고 마지막 정상 graph는 유지됩니다.

![잘못된 Data mapping의 local scroll과 복구](images/current/modeling-data-invalid-scrolled-1440x900.png)

재사용할 처리 설정을 관리할 때만 **Advanced mapping definition**의 JSON에서 다음 항목을 확인합니다.
   - `independent_quantity`
   - source `channel_key`와 계산용 `target_quantity`
   - 허용 normalized unit
   - required 여부와 명시적 scale/offset
   - `reject` 또는 `drop_any` missing-data 정책
6. 재사용할 매핑이면 **Save new profile**을 누릅니다. 기존 profile을 변경할 때는 변경 사유를
   입력하고 **Append profile revision**을 눌러 새 revision을 만듭니다. 기존 revision은 덮어쓰지 않습니다.
7. Process/Fit의 **Add operation**, **Add fit method**와 얕은 settings band를 사용합니다. Optional
   smoothing 방법은 서버 registry/capability로 보존되며, 이 guide는 새 smoothing 단계나 별도
   discoverability를 추가로 요구하지 않습니다.
8. 처리 결과와 모델 후보는 같은 graph에서 비교합니다. 계산 식별자와 상세 수치 기록은 일반 graph를
   밀어내지 않고 Advanced/Evidence에서만 확인합니다.

## Validate와 Review

**Validate**는 Fit 점수의 별칭이 아닙니다. Metal synthetic reference 경로에서도 현재
selection ID와 server Material Model의 calibration-candidate evidence가 같고, session에 pin된 IR/Card의
ID와 revision이 정확히 일치할 때만 Template과 Dataset Selection을 골라
**Create pinned validation plan**을 누를 수 있습니다. 화면은 같은 Material State의 다른 model,
목록 첫 항목이나 `latest`를 대신 선택하지 않습니다. common Processing Output 후보처럼 현재
validation adapter가 없는 경우에는 `Not supported`를 표시합니다. 지원되는 exact reference chain에서는
**Submit validation job**, **Collect and evaluate result**를 실행하면 별도 Validation Run/Result,
holdout-independence, verdict가 나타납니다. plan만 있으면 `Not run`이며 원본 Fit metric은 계속
`fit evidence only`로 남습니다. 브라우저 session은 Plan과 Result의 exact ID를 서로 다른 pointer로
보존하고 다시 열 때 각각 조회하므로 Result가 Plan을 덮어쓰거나 `Not configured`로 되돌아가지 않습니다.

**Review**는 제출, 수정 요청, 승인 상태를 Fit 결과와 구분합니다. Validate와 Review는 일반
`Data | Process | Fit | Export` 단계가 아니라 Advanced의 governed contract입니다. Fit 또는
Validate 완료를 승인으로 표시하지 않습니다. Material, Test Data, Solver Card의 exact revision에서
요청한 review는 Activity에서 Reviewer가 별도로 승인하거나 변경을 요청합니다. governed tabular
Test Data는 current exact Record binding이 있으면 그 Record를 사용하고, 없으면 revision에 기록된
exact governed Material pin을 사용합니다. 둘 다 없는 Test Data는 제출할 수 없습니다. failed job
복구와 server receipt projection은 아직 Activity에 연결되지 않았습니다.

현재 등록된 공통 method는 다음과 같습니다.

- 정렬과 duplicate 정책: `rows.sort_unique`
- 범위 선택: `curve.crop`
- 수치 변환: `curve.scale_shift`
- 선형 resampling: `curve.resample_linear`
- moving average: `curve.moving_average`
- Savitzky–Golay: `curve.savitzky_golay`
- smoothing spline: `curve.smoothing_spline`

금속 단축 인장 데이터에는 다음 family method도 같은 ordered pipeline에서 사용할 수 있습니다.

- 명시적 toe 보정: `tensile.toe_zero_intercept` — 선택 구간 OLS zero intercept와 strain-axis translation
- 탄성계수: `metal.elastic_modulus` — `linear_regression`, `robust_huber`, `chord`, `secant`, `manual`
- offset proof stress: `metal.proof_stress`
- 자동 necking 후보: `metal.necking_candidate`
- engineering → true/true-plastic 변환: `metal.engineering_to_true_plastic`
- hardening 후보 비교·조합·제한 외삽: `metal.hardening_fit_extrapolate`

1366×768의 Manual slope 설정도 control 영역 안에서만 스크롤되며 graph와 **Save processed curves**는
직접 도달할 수 있습니다.

![Manual Process local scroll과 저장 동작](images/current/modeling-process-manual-1366x768.png)

탄성계수, proof stress와 necking 위치는 선택한 stage의 **Scalar results**에 값과 단위로 나타납니다.
자동 necking 단계는 후보 index만 보고하며 curve를 자르거나 확정하지 않습니다. 변환 단계에서
`manual_index`를 명시해야 후보를 실제 경계로 사용합니다. `observed_full_domain`은 post-necking을
포함할 수 있다는 경고를 남깁니다. 금속 method는 normalized strain `1`, stress `Pa`만 받으며,
다른 단위를 Pa로 가장하거나 묵시적으로 변환하지 않습니다.

Hardening 단계는 Voce, Swift, Hockett–Sherby, Ghosh 중 2~4개를 같은 목적함수로 fitting합니다.
`fit_minimum_strain`, `fit_maximum_strain`은 관측값을 사용하는 구간이고
`extrapolation_maximum_strain`은 관측되지 않은 출력 한계입니다. `primary_family`,
`secondary_family`, `primary_weight`가 선택 조합을 완전히 정의합니다. 결과의 **Scalar results**에는
후보별 RMSE와 parameter lower/initial/fitted/upper가 표시되므로 숨은 초기값이나 경계가 없습니다.
Ghosh는 Altair Material Modeler 2025 식 계약을 따르며 `n`, `p` 대신 식별 가능한
`delta_p_minus_n = p - n`만 저장합니다. 해당 행에는 구조적 비식별성과
`plastic strain < epsilon_0` domain 경고가 항상 표시됩니다. 이 식 계약이 없는 과거 Recipe는
자동 변환하지 않으므로 새 revision으로 명시적으로 저장해야 합니다. 서버 Ghosh candidate의
`active_bound`에 정확히 `epsilon_0`가 포함되면 현재 선택과 무관하게 response/tangent의 표시
scale 계산에서 `fit_maximum_strain` 이후 tail을 제외합니다. 실제 response/residual/tangent
evidence 배열과 polyline은 그대로이며, 선택 preview/blend는 Ghosh를 포함할 때 같은 표시 규칙을
적용합니다.

**Hardening response**에서 observed plastic workup, single-law candidate와 현재 선택을 비교합니다.
**Residual**은
선택 fit domain에서 `predicted - observed`를, **Tangent modulus**는 후보별 수치 미분을 보여줍니다.
황색 배경과 점선의 `EXTRAPOLATED · UNOBSERVED` 영역은 시험 관측값이 아닙니다. 후보는 graph 아래
**Calculated models**에서 한 행씩 비교하며, 파라미터 범위는 **Calculation settings**에서 확인합니다.
**Recommended**는 계산 결과일 뿐 선택이 아닙니다. 사용할 행을 고른 뒤 **Why this model was selected**를
작성하고, 선택한 행에 경고가 있을 때만 acknowledgement가 나타납니다.
**Recalculate**가 새 계산에 성공하면 이전 행 선택과 이유는 자동으로 해제됩니다. 이미 저장한
Fit Output을 current로 가리키던 pointer도 새 행을 고르는 순간 해제되므로, 다시 선택·저장하기 전에는
이전 output이 Export fallback으로 사용되지 않습니다.
금속 blend는 candidate table의 계산된 blend 행에서만 명시적으로 선택합니다. 설정에서
두 law 또는 ratio를 바꿨다면 먼저 **Recalculate**로 다시 계산해야 하며, 선택 이후에는 두 law 이름,
ratio, 두 parameter set을 하나의 decision identity로 보존합니다. single-law 행을 선택하면 graph도 그 law를
`Selected`로 표시하며 계산된 blend를 선택으로 가장하지 않습니다.
폴리머는 요청한 term policy가 아니라 server가 실제 산출한 term-count 행만 선택할 수 있습니다.
**Save fit & continue**는 graph 아래 엔지니어 선택 영역에 한 번만 나타나며 이 선택을 새 Processing
Output으로 저장합니다. 저장 전에는
Material Model IR이나 Neutral Material로 승격할 수 없습니다.

Fit 입력은 Process에서 선택한 Test Data 또는 저장된 Processing Output의 정확한 revision을 그대로
이어받고 현재 head나 `latest`를 대신 바인딩하지 않습니다. 정상 화면에는 사람이 읽는 입력 이름과
현재 저장 상태만 표시하며, 전체 source digest, method key/version, run과 저장된 Fit Output revision은
**Calculation settings**, **Advanced** 또는 **Evidence**에서 확인합니다. Process Output이 없거나 stale이면 graph 중앙에
**Fit is blocked**와 **Back to Process**가 나타나고, 이 복구는 ref/history/pointer를 바꾸지 않는
탐색만 수행합니다. Fit 계산/저장 실패에서는 이전 유효 graph와 decision reason, warning acknowledgement를
유지하고, 저장된 Fit을 다시 읽지 못하면 **Saved Fit result unavailable**과 **Retry saved Fit**만
표시합니다. retry는 같은 saved Output revision의 content URL을 다시 읽으며 raw Test Data나 최신
Output을 fallback으로 사용하지 않습니다. 저장 후에도 현재 task는 Fit에 남고 Export는 별도 task로
시작하지 않습니다.

현재 Fit capture topology는 Metal과 Polymer의 5개 viewport(1366×768, 1440×900, 1920×1080,
2560×1440, 3840×2160), Polymer Calculation settings, Point differences, 입력 없음, 저장 결과와
stale/recovery 상태를 포함합니다. Calculation settings는 1~10항 수동 선택과 10항의 21개
파라미터 행을 실제 독립 스크롤로 검증합니다. 모든 정상 상태는 document overflow, pane 겹침,
graph/legend/axis 충돌과 keyboard focus 복귀를 함께 확인합니다.

| Fit evidence | 화면 |
| --- | --- |
| 1366×768 | ![Fit 1366](images/current/modeling-fit-1366x768.png) |
| 1440×900 | ![Fit 1440](images/current/modeling-fit-1440x900.png) |
| 1920×1080 | ![Fit 1920](images/current/modeling-fit-1920x1080.png) |
| Wide 2560×1440 | ![Fit 2560](images/current/modeling-fit-2560x1440.png) |
| Wide 3840×2160 | ![Fit 3840](images/current/modeling-fit-3840x2160.png) |
| Polymer Calculation settings · 10-term | ![Polymer calculation settings](images/current/modeling-fit-polymer-calculation-settings-1920x1080.png) |
| Calculation failed | ![Fit calculation failed](images/current/modeling-fit-calculation-failed-1920x1080.png) |
| Save failed | ![Fit save failed](images/current/modeling-fit-save-failed-1920x1080.png) |
| Exact Process source blocked | ![Fit exact source blocked](images/current/modeling-fit-exact-source-blocked-1920x1080.png) |
| Polymer 입력 미선택—Data로 이동 · 1366×768 | ![Polymer Fit input selection 1366](images/current/modeling-fit-polymer-source-blocked-1366x768.png) |
| Polymer 입력 미선택—Data로 이동 · 1440×900 | ![Polymer Fit input selection 1440](images/current/modeling-fit-polymer-source-blocked-1440x900.png) |
| Polymer 입력 미선택—Data로 이동 · 1920×1080 | ![Polymer Fit input selection 1920](images/current/modeling-fit-polymer-source-blocked-1920x1080.png) |
| Polymer 입력 미선택—Data로 이동 · 2560×1440 | ![Polymer Fit input selection 2560](images/current/modeling-fit-polymer-source-blocked-2560x1440.png) |
| Polymer 입력 미선택—Data로 이동 · 3840×2160 | ![Polymer Fit input selection 3840](images/current/modeling-fit-polymer-source-blocked-3840x2160.png) |
| Polymer saved Selection · 1920×1080 | ![Polymer saved Selection](images/current/modeling-fit-polymer-saved-1920x1080.png) |
| Polymer used/check point differences · 1920×1080 | ![Polymer point differences](images/current/modeling-fit-polymer-residual-1920x1080.png) |
| Polymer input changed · 1920×1080 | ![Polymer input changed](images/current/modeling-fit-polymer-stale-1920x1080.png) |
| Exact saved Fit read failed | ![Fit exact read failed](images/current/modeling-fit-exact-read-failed-1920x1080.png) |
| Restored saved Fit | ![Fit restored](images/current/modeling-fit-restored-1920x1080.png) |



## Export의 현재 exact-source 경계

2026-08-22 Issue #261 M1E ownership 통합 검증은 작업 흐름과 화면 의미를 바꾸지 않고
검증·engineering graph·calibration·viscoelastic 영역에 이어 공통 Modeling shell, rail, stage navigator,
persistent graph와 workspace 배치의 CSS 생산자를 feature 소유 파일로 옮겼습니다. 이번 core-shell
단위는 101개 selector row와 95개 전체 rule group이며, 누적 이동은 334개 row와 304개 group입니다.
Elastoplastic, hyperelastic, Export와 reference-family 묶음은 다음 단위로 남겨 두었습니다. 현재
1440×900 Export 이미지는 앞선 exact-source M1E 여정의 live evidence를 그대로 참조합니다. 별도
core-shell evidence에서 Storybook 15개 pair는 모두 pixel-identical이고, Product 119개 pair 가운데
98개도 pixel-identical입니다. 18개 pair는 900 px 이하에서 Export가 잘리지 않도록 stage navigator를
두 줄로 보이게 한 수정이며, 나머지 3개 차이는 native select 글리프에만 한정됩니다. 두 Modeling
경로의 860, 861, 900 px 화면에서 Data, Process, Fit, Export가 모두 보이고 선택할 수 있음을 확인했습니다.
DOM, API, copy, exact revision과 저장·복구 상태는 바뀌지 않았습니다.

Fit 검토 뒤 상단 **Export** task를 열면 current Material, Material State, Test Data, Mapping Profile,
Processing Output pin과 `Processing Output → Material Model IR → Neutral → target preflight → native card`
lineage를 먼저 확인합니다. Export는 Setup(왼쪽), native preview(가운데), Mapping/Fit context(오른쪽)가
한 화면에 있는 전용 workspace이며 native preview가 가장 넓은 pane을 차지합니다. 선택 model graph의 축은
internal quantity key 대신 사람이 읽는 물성명과 unit(예: `True plastic strain [1]`, `Hardening stress [MPa]`)으로
표시됩니다. source가 없거나 다른 revision이면 Export check가 **Cannot create**가 되고 source 복구 안내만
표시됩니다. **Back to Fit**은 같은 session과 Recipe draft를 유지합니다.

Export는 모든 상태에서 같은 세 칸 작업 묶음(Setup 300–340 px, 넓은 native preview,
Mapping/Fit context 326–360 px)을 유지합니다. 1366×768, 1440×900, 1920×1080,
2560×1440, 3840×2160 정상 화면과 1440×900 source-blocked,
approximation-blocked, delivered 상태를 캡처 계약으로 관리합니다. Wide 화면에서는 Export shell과
native preview가 남는 폭을 사용하고 Setup·Mapping/Fit context만 읽기 좋은 pane 범위를 유지합니다.

2026-08-17 FE-04F current-source capture는 기존 데이터와 볼륨을 보존하고 web만 다시 빌드한 뒤,
8개 Export 상태마다 새 synthetic Processing/Fit 결과를 만들었습니다. source-blocked를 제외한 7개
상태에서는 새 selected model과 Neutral revision도 만들었고, 최종 전달 상태에서만 그 Neutral을 current
Material의 exact Materials record에 연결한 뒤 새 solver card와 receipt/link를 읽어 Materials에서 다시
열었습니다. Preview-only 상태는 Materials 연결을 만들지 않으며, 어떤 상태도 과거 Output·Neutral·solver
card를 대신 사용하지 않습니다. 다섯 viewport와 세 상태 원본을 모두 원본 해상도로 열고,
1920/2560/3840의 header·destination controls·native preview·Mapping/Fit result 1:1 crop을 전후
비교했습니다. header·controls·result는 픽셀까지 같고, native preview는 실행마다 생기는 model revision과
mapping digest 두 줄만 달랐습니다. 전달 완료 화면도 현재 세 칸 구조, 문구, action과 exact receipt/link
read-back을 유지합니다.

| Export evidence | Capture |
| --- | --- |
| Wide 2560×1440 | [modeling-export-2560x1440.png](images/current/modeling-export-2560x1440.png) |
| Wide 3840×2160 | [modeling-export-3840x2160.png](images/current/modeling-export-3840x2160.png) |
| Source blocked · 1440×900 | [modeling-export-source-blocked-1440x900.png](images/current/modeling-export-source-blocked-1440x900.png) |
| Approximation blocked · 1440×900 | [modeling-export-approximation-blocked-1440x900.png](images/current/modeling-export-approximation-blocked-1440x900.png) |
| Delivered · 1440×900 | [modeling-export-delivered-1440x900.png](images/current/modeling-export-delivered-1440x900.png) |

Modeling의 **Local file** 경로에서 exact Test Run을 선택하고 저장한 새 Test Data revision은 서버가
`Test Run → Specimen → Material State → Material` exact revision 관계를 검증합니다. 이후 그 Test Data로
저장한 Processing Output은 `export_provenance`에 같은 Material/State/Test Run pin을 보존합니다. Export
체크리스트는 이 서버 proof와 현재 session의 exact Material/State/Test Data를 비교해 `current` 또는 `stale`을
표시합니다.

DMA/FLD governed import는 이 proof에 Raw Asset/Artifact, Import Run, Import Profile과 normalized
Dataset exact revision까지 추가합니다. canonical row 값을 다시 직렬화한 normalized Parquet digest도
저장된 Dataset digest와 일치해야 하므로, Test Data 값이나 source pin 하나가 달라지면 read-back
검증이 실패합니다. 고정 주파수 DMA 온도 sweep은 저장한 shifted DMA response를 거쳐 Polymer Fit으로
연결됩니다. FLD는 Data/Review 전용이며 다른 재료군의 Fit 후보로 자동 노출되지 않습니다.

직접 등록한 Test Data JSON과 과거 revision은 이 proof가 없으므로 `Server provenance proof · missing`입니다.
현재 session의 이름이나 ID가 우연히 같아도 추론하거나 backfill하지 않습니다. Canonical Test Data JSON
Artifact 자체에는 proof가 추가되지 않으며, immutable revision content에만 저장됩니다. Omitted proof로 revise하면
새 revision은 unqualified 상태가 됩니다.

source proof와 current Material Model IR/Neutral pin이 모두 current일 때만 capability manifest가 선언한
solver/version/unit tuple을 선택해 stateless native preview를 생성할 수 있습니다. 현재 선택지는 synthetic
non-production Abaqus/OpenRadioss 2025 kg-m-s tuple뿐이며 production support를 뜻하지 않습니다. Output
unit select에는 capability가 선언한 `kg_m_s` 선택지와 함께 실제로 선택할 수 없는
`Other unit systems — unavailable (not declared by this exporter capability).` disabled option을 둡니다.
Export check의 상태는 **Ready to create**, **Review required**, **Cannot create** 중 하나이며 Mapping
normal row는 `quantity · source → target expression · consequence`로 표시합니다. raw
status/count/digest/ID는 Advanced evidence에만 둡니다. C1 preview가 없으면 primary **Run Export check**,
stale 또는 실패한 C1이면 **Retry Export check**, current C1이면 **Create solver card**만 primary로
노출합니다. approximation acknowledgement가 없으면 Create가 disabled입니다. target 또는 source를
바꾸면 preview와 delivery pointer는 사라지지만 exact upstream 입력은 재시도를 위해 남습니다.

금속에서 source proof는 current인데 Model IR/Neutral pin만 없으면 같은 Export checklist 아래의
**Prepare selected model**을 사용합니다. 일반 화면에서는 사용자가 검토할 extrapolated range와 준비 사유만
묻고, 선택된 Processing Output revision, current Material/State revision, current Property Set revision은
**Advanced · prerequisite evidence**에 둡니다. 서버가 반환한 upstream tabulated-plasticity model은 먼저
session에 pin되고, 이어 Neutral document를 생성합니다. Neutral 생성이 실패해도 model pin과 입력을
유지하므로 **Retry preparation**은 model을 다시 만들지 않습니다. upstream model revision은 Validation에 쓰이는 session pointer이고,
Neutral document 안의 canonical IR revision과 같은 값으로 바꾸지 않습니다. target preview는 caller가 IR
revision을 추측해 보내지 않고 exact Neutral revision을 보내며 server가 embedded IR relation을 검증합니다.
Polymer와 Elastomer에는 이 recovery path가 아직 **Not configured**이며 다른 material family의 model을 대신
선택하지 않습니다.

Recovery가 끝나면 같은 workspace에서 capability가 선언한 solver/version/unit tuple을 고르고
`preview_only` native 결과를 확인합니다. C1 heading은 **Current preview · not created**이며 filename과
mapping consequence를 함께 검토합니다. Approximation이 있으면 exact acknowledgement를 먼저 기록하고,
그 뒤 별도의 **Create solver card**로 immutable card와 receipt를 만듭니다. Delivered 화면의 normal
surface에는 filename/status만 남기고 receipt를 inline으로 반복하지 않습니다. 대신 keyboard-reachable
**Delivery details** disclosure를 열어 `solver_card`, `preview`, `download`, `receipt` 네 typed API
resource link와 exact card/revision/receipt IDs 및 native/mapping digests를 확인합니다. source의 exact
IDs와 digests는 별도 **Advanced · exact source** disclosure에만 둡니다. Delivered의 primary는
**Open solver card**이며, source/target 변경이나 실패는 upstream revision을 바꾸지 않고 현재
preview/delivery pointer만 지웁니다.

이 preview는 card, Artifact, receipt, download, Activity, Material CAE Card link 또는 `exportArtifact`를 만들지
않습니다. 응답의 delivery status는 `preview_only`이며 approximation이 있으면 Evidence disclosure의
acknowledgement identity는 **UXC-06C2 delivery 입력**일 뿐 C1에서 승인·기록되지 않습니다.

**Create solver card**는 current preview와 정확히 같은 source/target/mapping identity를 다시 검증합니다.
경고 mapping이면 해당 acknowledgement identity를 명시적으로 확인해야 하며, exact mapping에는 acknowledgement를
제출할 수 없습니다. 성공하면 immutable Solver Card와 filename/checksum·exact revision chain·mapping digest·actor·timestamp를
포함한 immutable Exporting receipt/outbox event가 하나의 transaction에서 함께 기록됩니다. Materials CAE Cards는 기존
canonical card API로 delivered card를 재사용합니다. 같은 preview identity로 다시 요청하면 새 card를 만들지 않고 기존
receipt를 반환합니다. 성공 영역에는 `Solver Card created`와 filename/status만 표시하며, card/receipt 리소스는
**Delivery details** disclosure 안에서 확인합니다. receipt UUID, checksum, source chain과 mapping 상태는 receipt 또는
**Preview & mapping evidence**에서 확인하며,
구성되지 않은 Activity projection 같은 내부 구조 용어는 일반 경로에 노출하지 않습니다. 현재 Activity 연결이 없으므로
Activity에 Delivered 상태나 링크를 만들지 않습니다. source/target 변경, 실패 또는 재시도는 기존 immutable delivery를
수정하지 않고 current preview/delivery pointer만 지웁니다.

### 보호된 API의 Unit Profile 사용

현재 화면에는 Unit Profile 관리 기능이 없습니다. API 사용자는 `GET /api/v1/unit-system`에서
지원하는 dimension과 stable unit identifier를 확인하고, `POST /api/v1/unit-conversions`로
location·quantity semantics·원본 단위 문자열을 명시한 변환만 요청할 수 있습니다. 지원하지 않는
단위, dimension 불일치, strain과 일반 무차원 수치의 혼용, 절대온도와 온도차의 혼용은 추론하거나
대체하지 않고 location과 source/target dimension을 포함한 오류로 반환합니다.

Unit Profile은 `POST /api/v1/unit-profiles`로 stable identity를 만들고
`POST /api/v1/unit-profiles/{profile_id}/revisions`로 immutable revision을 추가합니다. 처리나 Export
요청에는 `profile_id`, `revision_id`, `content_sha256` 세 값을 모두 고정하며, 이름이나 `latest`만
전달하지 않습니다. Profile을 사용해 저장한 Processing Output, Fit, preview, Solver Card와 delivery
receipt는 같은 exact pin과 각 적용 위치의 unit application을 read-back합니다. 기존 profile 없는
결과와 13개 registration 변환은 그대로 읽히고, `kg_m_s`는 기존 solver-card 호환 tuple일 뿐 새
production 기본 Profile이 아닙니다.




각 method의 option 계약은 서버의 versioned registry에서 읽습니다. 알 수 없는 option, 호환되지
않는 quantity/unit, 범위 밖 extrapolation, 비유한 수치, 허용되지 않은 결측값은 묵시적으로
보정하지 않고 실패시킵니다.



## 불변 Processing Output 저장

### Process 상태와 저장 결과 비교

Process band는 선택한 exact Test Data revision과 Mapping Profile을 항상 함께 표시하고,
Calculation과 Result를 첫 줄에, Save result를 다음 전체 폭 줄에 둡니다. Evaluation method select의
다섯 선택지와 range input, processed-curve label, save reason과 Save 버튼은 같은 28px compact
control height를 사용합니다. Result에는 서버가 계산한 현재 step label과 modulus 값을 직접 표시합니다.
서버 preview가 성공한 동안에는 mapped input, 선택한 processed stage, server modulus fit을 하나의
engineering graph에 겹쳐 보여 주며, draft option을 바꾸거나 재계산에 실패해도 마지막 유효
server preview를 화면에 남깁니다. Toe 보정 단계에서는 같은 graph에 평가 직선도 표시하고 Result의
offset/slope/R²/point 수와 품질 경고를 함께 검토합니다. 경고가 있으면 acknowledgement를 포함한
동일한 options로 다시 Preview하기 전까지 저장할 수 없습니다. 실패한 응답은 저장 입력으로 승격되지 않습니다. exact source나
profile을 복구할 수 없으면 graph는 `blocked` 상태와 **Back to Data** recovery를 표시하며
`latest` revision으로 조용히 대체하지 않습니다. 선택한 exact ref 자체가 없는 경우에는
**No exact Test Data**와 **Back to Data**만 보입니다. exact ref는 있지만 content read가 실패한
경우에는 **Exact source unavailable · rN**으로 settled되고 자동 재시도하지 않습니다. 이전
document/preview/scalar나 newest/current-head를 fallback으로 사용하지 않으며, 직접 보이는
**Retry exact source** 또는 **Back to Data**로만 복구합니다. 같은 exact ref의 재시도는 한 번의
새 요청이고 실패하면 다시 settled blocked 상태로 남습니다.

**Saved results (N)** disclosure는 현재 exact source/profile에 맞는 Processing Output만
보여 주며, `Label | Method | Range | Result | Revision | State | Action` 일곱 열을 직접 제공합니다.
Method 열은 `robust_huber` 같은 내부 ID 대신 Auto robust, Linear regression, Chord, Secant, Manual
slope를 표시하고 Revision은 정확한 `r1` 형식으로 고정합니다. 각 row에 source 설명을 반복하지 않아
1366px에서도 열과 Retry/Use settings action을 바로 사용할 수 있습니다. Artifact를 읽지 못하거나
source, profile, output id, revision, ordered steps가 맞지 않으면 Result에 **Saved result unavailable**과
row-local **Retry**를 표시하고 fallback을 만들지 않습니다. 성공적으로 읽은 row만 **Use settings**를
제공하며, 같은 settings를 새 draft로 복사하므로 Preview 후 새 immutable output을 저장해야 합니다.
Save한 결과는 새 current가 되고 이전 결과는 history로 남습니다. 오래된 row에서 **Use settings**를
누르면 해당 history의 settings를 local draft로 복사하지만 새로 저장한 current result와 그 exact
identity는 그대로 유지됩니다. 복사된 draft는 Preview changes를 다시 실행해야 하며, 실제로 새
current가 되는 것은 **Save processed curves**를 눌렀을 때뿐입니다. Preview, rerender, reload와
stage 이동 중에도 saved history와 current pointer는 바뀌지 않습니다. Material/State/family,
Data selection 같은 일반 upstream draft 변경은 기존 invalidation 규칙을 따릅니다.

정상 화면에는 `Preview — not saved` 같은 반복 상태 문구를 두지 않습니다. 설정을 바꿔 재계산이
필요하거나 차단·실패한 경우에만 Result 옆의 한 줄 recovery 안내와 접근 가능한 live status를
보여 줍니다. Process의 live evidence는 linear-regression과 manual local-scroll을 별도 settled state로 포함한 10개
출력(`modeling-process-linear-regression-1366x768.png` 포함)으로, 일반 viewport
(1366×768, 1440×900, 1920×1080)와 wide viewport
(2560×1440, 3840×2160), manual local-scroll(1366×768), exact prerequisite blocked(1440×900), exact-read failed(1440×900), saved-result siblings(1440×900)
상태를 각각 확인합니다. 캡처가 `Loading Process controls…` fallback에서 settled panel로 전환되지
않았거나 graph/axis가 잘리면 기존 capture directory를 교체하지 않습니다.
현재 5개 Process 화면은 계산 곡선을 plot 영역 안에서만 그려 범례 공간을 침범하지 않는 상태를
확인한 결과입니다. Test Data, Mapping Profile, 저장 결과와 복구 동작은 그대로 유지됩니다.

| Process evidence | 화면 |
| --- | --- |
| Standard 1366×768 | ![Process 1366](images/current/modeling-process-1366x768.png) |
| Standard 1440×900 | ![Process 1440](images/current/modeling-process-1440x900.png) |
| Standard 1920×1080 | ![Process 1920](images/current/modeling-process-1920x1080.png) |
| Linear regression 1366×768 | ![Process Linear regression](images/current/modeling-process-linear-regression-1366x768.png) |
| Wide 2560×1440 | ![Process 2560](images/current/modeling-process-2560x1440.png) |
| Wide 3840×2160 | ![Process 3840](images/current/modeling-process-3840x2160.png) |
| Exact prerequisite blocked 1440×900 | ![Process blocked](images/current/modeling-process-blocked-1440x900.png) |
| Exact source read failed 1440×900 | ![Process exact source read failed](images/current/modeling-process-exact-read-failed-1440x900.png) |
| Saved-result siblings 1440×900 | ![Process saved results](images/current/modeling-process-siblings-1440x900.png) |

1. Process preview 결과와 저장된 Mapping Profile revision이 일치하는지 확인합니다.
2. current-step settings에서 Processed curve label과 저장 사유를 입력합니다. Result 이름 입력은
   1366px에서 최소 240px, 사유 입력은 최소 360px의 사용 가능한 폭을 유지합니다.
3. **Save processed curves**를 누릅니다. 이것이 Process의 유일한 primary action이고 preview는 secondary입니다.
4. 서버는 화면의 preview 배열을 저장하지 않고 exact Test Data revision과 exact Mapping Profile
   revision을 다시 읽어 동일한 ordered steps를 재실행합니다. 수동 modulus/necking workup이 있으면
   typed `workup_overrides`도 원값·정규값·사유와 함께 immutable output에 고정합니다.
5. 저장된 목록에서 revision 1, stage/point 수, Output SHA-256을 확인합니다.
6. **Download JSON**으로 `cmp.processing-output` Artifact의 정확한 바이트를 받습니다.


## 반복시험 정렬과 pointwise 통계

1. 동일 조건에서 얻은 각 반복시험을 별도 Test Data identity로 등록합니다. 한 문서의 평균값으로
   합치거나 원본 curve를 삭제하지 않습니다.
2. 왼쪽 **Curves**에서 비교할 revision을 checkbox로 두 개 이상 선택합니다.
3. **Replicate analysis**를 열어 공통 grid point 수를 입력하고 **Preview mean & band**를 누릅니다.
4. 서버는 각 문서에 같은 Mapping Profile과 ordered preprocessing steps를 적용합니다.
5. 모든 curve에서 실제로 관측된 x-domain의 교집합만 사용해 선형 보간합니다. 교집합 밖
   extrapolation은 허용하지 않습니다.
6. member curve, 평균과 metadata가 선언한 band를 함께 확인하고, 마지막 grid point의 표본 표준편차,
   MAD와 IQR을 검토합니다. Pointer 또는 graph focus 뒤 Arrow key로 point를 옮기면 축 label/unit,
   값, band kind·method·coverage와 `n`이 같은 tooltip/live text에 나타납니다. `Escape`는 탐색을
   끝내고 legend toggle은 현재 graph에서만 series visibility를 바꿉니다.

현재 Processing ensemble 통계 계약은 표본 표준편차 `ddof=1`, unscaled MAD, linear q1/q3
quantile, normal-approximation pointwise 95% mean CI를 명시합니다. 화면은 이 기존 method evidence를
그대로 표시하며 새 통계를 계산하거나 모든 band를 95% CI로 추정하지 않습니다. 이 결과는 T-53 preview이며, T-54에서 exact Selection과 versioned
Recipe/Batch 실행 결과로 저장됩니다.

### Peak stress 분포 후보 비교와 선택

분포 적합은 선택 기능입니다. 사용하지 않으면 Selection/Plan/Run/Distribution Result를 새로 만들지
않으며 Process, Fit, Export 진행을 막지 않습니다. 필요할 때 `Modeling → Process` 상단의
**Distribution analysis**를 누르면 현재 작업면을 덮는 분석 sheet가 열립니다. 기존 Process 설정과
graph는 뒤에서 그대로 유지되고, **Close** 또는 `Escape`로 닫으면 버튼으로 focus가 돌아옵니다.

1. **Replicate set**에서 exact processed Dataset revision 8개 이상을 가진 Selection을 고릅니다.
   정렬 전 normalized source Selection은 목록에 섞이지 않습니다. Dataset head가 전진해도 과거
   processed revision을 고정한 Selection은 **historical exact revisions**로 남아 저장된 Plan/Run/Result를
   다시 읽을 수 있습니다. 새 Selection이 필요하면 **Replicate sets**에서 두 개 이상을 고정해
   저장합니다.
2. 필요할 때 **Replay**에서 seed와 exact Unit Profile ID/revision/SHA-256을 함께 지정합니다.
   Profile은 세 필드를 모두 입력하거나 모두 비워야 하며 계산 자체는 Pa에서 수행됩니다.
3. **Fit candidates** 또는 **Refit candidates**를 누르거나 **Plan / Run history**에서 저장 기록을
   선택합니다. 같은 Selection revision,
   seed, bootstrap 수와 Unit Profile pin은 기존 immutable Plan을 재사용하고 새 committed Run/Result를
   만듭니다.
4. **Probability comparison**에서 empirical CDF와 저장된 후보 curve를 비교하고, 아래 원장에서
   candidate별 parameter, AICc, delta AICc, BIC, Anderson–Darling, 999회 bootstrap p-value와 성공
   refit 수를 함께 봅니다. n 8–19 경고, support 또는 수치 실패,
   missing/non-finite/censored, outlier assessment가 모두 보존됩니다. 관측을 숨기거나 자동 삭제하지
   않습니다.
5. **Recommendation · AICc Δ ≤ 2**는 비교 근거일 뿐 선택이 아닙니다. 성공한 candidate 행의
   **Select**를 누르고 **Engineering rationale**을 작성한 뒤 **Save exact selection**을 눌러 exact
   Result revision과 candidate digest에 고정합니다. 저장한 selected model과 이유는 전체 새로고침
   뒤에도 복원됩니다.

기존 mean, sample SD, median, MAD, IQR, min/max가 있는 descriptive Statistical Result는 후보 비교로
덮어쓰지 않습니다. source observation, Selection, Plan, Run, Result와 Artifact의 전체 exact identity와
library/RNG manifest는 **Evidence and replay manifest**에서 확인합니다.

| Distribution evidence | 화면 |
| --- | --- |
| 1366×768 | ![Distribution analysis 1366](images/current/modeling-distribution-1366x768.png) |
| 1440×900 | ![Distribution analysis 1440](images/current/modeling-distribution-1440x900.png) |
| 1920×1080 | ![Distribution analysis 1920](images/current/modeling-distribution-1920x1080.png) |
| Wide 2560×1440 | ![Distribution analysis 2560](images/current/modeling-distribution-2560x1440.png) |
| Wide 3840×2160 | ![Distribution analysis 3840](images/current/modeling-distribution-3840x2160.png) |


## Processing Recipe 저장과 게시

1. 저장된 exact Mapping Profile을 선택하고 ordered step을 검토합니다. 현재 재료군에 맞는 게시
   Recipe가 있으면 가장 최근 exact revision이 자동 선택됩니다.
2. **Recipe Library**에서 lifecycle과 exact revision을 확인합니다. 기존 설정에서 독립 Recipe를
   만들려면 **Clone as new**를 누르고 Recipe key, label, 설명과 변경 사유를 수정합니다.
3. **Save new Recipe**를 눌러 stable identity와 draft revision 1을 만듭니다.
4. 옵션이나 순서를 변경할 때는 저장된 Recipe를 선택하고 **Append draft revision**을 누릅니다.
5. 검토가 끝난 draft는 **Publish reviewed revision**으로 게시합니다. published revision을 직접
   수정하지 않으며, 후속 변경은 새 draft revision으로 추가합니다.

Recipe는 Mapping Profile의 stable identity뿐 아니라 exact revision UUID와 SHA-256을 고정하고,
각 step의 method ID, version, options와 options digest를 순서대로 보존합니다. Batch preflight와
실행은 이 exact published Recipe revision을 입력으로 사용합니다.


## Batch preflight와 실행

1. **Saved Processing Recipe**에서 자동 복원된 `published` revision을 확인합니다. draft Recipe는 실행할 수 없습니다.
2. **Batch Monitor**의 **Test Data selection**에서 처리할 revision을 선택합니다. 화면의 각
   항목은 current head를 표시하지만 실행 요청과 저장된 Member는 그 시점의 exact revision UUID를 고정합니다.
3. **Compatibility preflight**를 누릅니다. 모든 member의 채널 quantity, 단위, Mapping Profile과
   ordered step을 서버에서 실제 실행하여 예상 output point 또는 차단 diagnostic을 표시합니다.
4. 모든 member가 `Ready to run`일 때만 **Execute published Recipe**가 활성화됩니다.
5. 실행 후 Monitor에서 member별 Attempt 번호, 성공 Output revision 또는 오류 코드를 확인합니다.
6. 일부 member가 실패해도 성공한 Output은 유지됩니다. **Retry failed members only**는 실패 member에만
   다음 Attempt를 추가하며 이전 Attempt와 Output을 수정하지 않습니다.


## 현재 경계

화면의 stage overlay와 반복시험 통계는 명확히 preview로 표시됩니다. 별도의 single-curve commit은
서버 재계산 결과를 exact input/profile FK와 canonical JSON Artifact로 영속화합니다. Monitor는
현재 재료군 Recipe의 run만 표시하고 성공 attempt/전체 attempt를 함께 보여줍니다. Recipe
저장/게시와 exact-input batch 실행을 지원하며, reviewed 금속 Processing Output은 같은 Modeling
화면의 Card task에서 IR/Neutral Material JSON으로 승격할 수 있습니다. 폴리머와 엘라스토머의
Polymer relaxation/DMA와 Elastomer multi-mode/holdout graph/task 흐름도 T-89/T-90에서
검증되었습니다. 전체 clean 제품 journey는 T-93에서 최종 승인합니다.

내부 API와 자료형의 소유 위치는 Modeling 기능 아래로 정리됐습니다. 화면, 버튼 순서, HTTP 요청,
exact revision 연결, 새로고침 복원, 저장 결과와 Solver Card 형식은 기존과 같습니다.

Data, Process, Fit, Export 화면의 스타일도 각 stage 소유 파일로 정리됐습니다. 사용자가 보는 작업
순서와 저장·복구 동작은 바뀌지 않습니다. exact Test Data와 Mapping Profile을 선택한 뒤 Process 결과를
저장하고, Fit 후보를 명시적으로 선택·저장한 다음 Export check와 Solver Card 생성을 진행하는 기존
경로가 그대로 유지됩니다. 이 정리는 화면 재설계가 아니며 shared shell, M1E 경계와 다른 기능의
스타일에는 영향을 주지 않습니다.

### Issue #261 B4 combined CSS ownership evidence provenance

The completed combined ownership batch and its validation are recorded in
[`Issue #261`](https://github.com/pikachu444/cae-material-platform/issues/261).
It preserves the exact Data → Process → Fit → Export session, Administration plan → confirm →
apply/read-back, and Activity error/recovery journeys across five CSS viewports at browser zoom
100%. Main original-resolution review passed the Carbon hierarchy, COMSOL engineering flow and SAP
responsive logic checks; 207 PNG and 8 JSON artifacts remain retained as task evidence. Physical
Windows 4K readability remains the #223 gate, and no user-facing workflow or exact-revision contract
is changed by this provenance entry.

### Issue #261 M1E3 Modeling family CSS ownership provenance

The constitutive/reference-family styles used by engineering curves, calibration, Export delivery,
elastoplastic preview, viscoelasticity and elastomer comparison now live with their Modeling
producers. This changes stylesheet ownership only. The exact Test Data → Process → Fit → explicit
saved model → Export journey, selected-model identity, acknowledgement, solver preview, recovery and
route aliases remain unchanged.

The [Issue #261 approval history](https://github.com/pikachu444/cae-material-platform/issues/261) records frozen-base
and current Product/Storybook states at browser zoom 100%, including all five CSS viewports, direct
100%-pixel crops, generated bundle provenance, and reload read-back. No current-guide PNG is replaced
because the move is behavior-preserving. Automated 3840×2160 proves geometry only; physical Windows
4K readability remains the #223 gate.

### Issue #261 M1E4 common Modeling core/stage CSS ownership provenance

공통 Modeling workbench와 stage navigator의 CSS selector 소유권은 기존
`modeling-core-workbench.css` 및 engineering-curve plot owner에 정리됩니다. 이번 범위는
감사된 172개 selector row/137개 rule group(공통 core 168개, plot 4개)뿐이며, DOM, 문구,
URL, API, stage 순서, graph, exact revision, 저장·복구 상태는 바꾸지 않습니다. 실제 사용자는
기존처럼 exact `CMP-DEMO-DP780-TEST-JSON` Test Data를 고른 뒤 Data → Process → Fit → Export를
진행하고, 선택된 `swift + voce 50/50`, target/native preview와 reload read-back을 확인합니다.

이번 결과는 [#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
최종 acceptance 기록으로 남겼습니다. 다섯 CSS viewport의 before/after 원본과 header·navigator·
stage controls·engineering graph 100%-pixel crop을 실제 크기로 검토했고, computed-style·geometry와
Storybook bundle도 같은 동작을 유지했습니다. 48개 비교 record와 220개 image pair에서 geometry·
text·pixel failure는 0건입니다. 전체 924개 PNG 중 702개는 acceptance evidence이며, 첫 후보의
회귀를 보여 주는 222개는 non-acceptance diagnostic으로 분리했습니다. 실제 cross-route/import/
export/test-JSON consumer가 있는 60개 deferred row는 legacy owner에 그대로 남습니다.
CSS-1618/1619 hyperelastic chart rule은 live CSSOM에서 확인한 12px cascade를 지키기 위해 원래
`styles.css` producer/order에 유지했습니다. 자동 3840×2160은 geometry만 증명하며 physical
Windows 4K readability는 #223 gate입니다.

M1E4의 실제 acceptance 여정은 서버가 반환한 Material·State·Test Data ID와 revision을 고정한
상태에서 Data 결과를 저장하고, Process 저장 pointer/source aggregate를 read-back한 뒤 Fit에서
Swift와 Voce 후보를 비교해 `swift + voce 50/50`을 명시적으로 저장하는 흐름입니다. 준비된
Material Model IR revision으로 Export check·acknowledgement·Solver Card 생성을 완료하고,
API resource read-back, Solver Card 열기, Materials Material Detail/CAE Cards와 Materials Browse의
동일한 exact card/target/IR/mapping/native resource/preview/download lineage까지 확인합니다.
canonical Modeling alias와 reload 후에도 같은 run의 ID·revision·digest·resource URL·preview 및
download hash가 보존되어야 하며 latest/first/global/다른 session fallback은 허용하지 않습니다.
정상 네 stage와 대표 blocked/read-back 상태는 manifest의 live evidence로 기록했습니다. 나머지
loading·error edge state는 실제 캡처로 가장하지 않고 durable source oracle로 제한했습니다.
header·navigator·table/form·stage controls·engineering graph와 해당 native preview를 검토한 결과,
keyboard reachability, page·console error, computed-style·geometry 및 #249의 information hierarchy,
engineering task flow, responsive/wide-screen composition이 모두 통과했습니다.
`EngineeringCurvePlot/EmptyCompatibleSeries` Storybook 1440×900 DPR1 before/after도 동일한 SHA-256을
기록합니다. `CMP-DEMO-DP780-TEST-JSON-03 · r1` 정적 참조는 topology 전용이며 동작 동일성의
근거로 사용하지 않았습니다.

### Issue #261 M1E5 producer-routed residual ownership provenance

M1E5는 M1E4 이후 남은 60개 selector row(51개 rule group) 중 승인된 58개 row(49개 group)를
공통 primitive, Materials curve-contract, Test Data governed-import/canonical JSON, Modeling
mapping-report producer stylesheet로 옮깁니다. 두 hyperelastic chart-axis/chart-tick row는
기존 12px processing cascade를 보존하기 위해 `styles.css`에 그대로 남습니다. 이 작업은 CSS
소유권과 import 경계만 정리하며 Data → Process → Fit → Export 순서, exact revision/session
선택, 저장·reload read-back, route alias, copy와 API 계약을 바꾸지 않습니다.

M1E5의 일곱 topology에 대한 다섯 viewport before/after 및 직접 100%-pixel crop은
[#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
Main visual/runtime acceptance PASS로 기록됩니다. 현재 guide의 1920×1080 Data PNG는
승인된 캡처를 재사용하며 새 route나 screenshot을 추가하지 않았습니다. 자동 3840×2160 검사는 geometry만
증명하고 physical Windows 4K readability는 #223 gate로 남습니다.

### Issue #261 M4 shared CSS ownership consolidation provenance

M4는 frozen base의 314개 selector row/262개 rule group 중 승인된 284개 row/239개 group과
같은 Fit cascade의 누락된 4개 row/4개 group을 합친 288개 row/243개 group을 15개 truthful
owner stylesheet로 정리합니다. 이미 shared layout이 truthful한 11개 row는
in-place로 기록하고, mixed source/selector cascade가 남은 19개 row(12개 group)는 HOLD로
보존합니다. DOM, 문구, API, route, state, exact revision/session contract와 #249의 정보
계층·engineering flow·wide-screen composition은 변경하지 않습니다. Fit owner는 frozen
M4 규칙과 기존 Fit baseline을 별도 import slot으로 유지하고, 반복된 Fit 입력 selector
family 전체를 원래 source 순서대로 함께 소유해 generic Modeling cascade를 역전시키지 않습니다.

다섯 CSS viewport의 13개 topology before/after 원본과 header·navigator·table/form·stage
controls·engineering graph/native preview crop은 [#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
기록되어 있습니다. Main은 원본과 직접 crop에서 1366px Fit control 잘림이 제거되고 원래
cascade와 폭이 복구된 것을 확인했으며, 현재 상태는 `ACCEPTED_MAIN_VISUAL_AND_RUNTIME`입니다.
현재 guide PNG는 검토된 M4 after 원본을 재사용하고, 자동 3840×2160은 geometry만 증명하며
physical Windows 4K readability는 #223 gate입니다.

### Issue #261 M6 zero-consumer legacy CSS audit provenance

M6는 PR #318이 넘긴 556개 selector row/495개 rule group을 하나의 frozen batch로
감사합니다. Static producer/reference, production bundle, 13개 live route/state topology를 모두
확인해 세 축이 전부 zero인 511개 row를 제거했습니다. 실제 producer/reference 또는 live DOM
증거가 남은 45개 row/43개 group은 current owner와 제거 조건을 명시한 HOLD로 보존합니다.
React, DOM, 문구, API, route, state, exact revision/session contract는 변경하지 않습니다.

다섯 CSS viewport의 305개 before/after pair와 원본·header·navigator·table/form·stage
controls·engineering graph/native preview crop은 [#261 승인 이력](https://github.com/pikachu444/cae-material-platform/issues/261)에
`ACCEPTED_MAIN_VISUAL_AND_RUNTIME`으로 기록됩니다. 차이는 생성된 revision/UUID/hash 문자열과
큰 viewport의 Search 화면에서 확인된 2–15개의 저강도 raster pixel뿐이며, geometry와 interaction
reachability는 동일합니다. 현재 guide의 1920×1080
Export PNG는 이 검토된 M6 after 원본으로 갱신했습니다. 자동 3840×2160 검사는 geometry만
증명하며 physical Windows 4K readability는 #223 gate로 남습니다.
