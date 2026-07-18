# 기능 요구사항과 비기능 요구사항

## 1. 적용 규칙

- `MUST`: MVP 또는 플랫폼 불변조건이다.
- `SHOULD`: MVP 권고이며 정당한 사유와 ADR 없이 제거하지 않는다.
- `MAY`: 후속 확장이다.
- 모든 write API는 사용자/서비스 agent, organization, request/trace ID를 기록한다.
- 모든 계산 결과는 immutable input revision만 참조한다.

## 2. 기능 요구사항

### 2.0 Configurable catalog와 제품 탐색

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-CFG-001` | 관리자는 migration 없이 Table과 typed Attribute Definition revision을 추가해야 한다. | 새 Attribute가 즉시 record form, validation과 search schema에 나타난다. |
| `FR-CFG-002` | Attribute는 number, integer, text, boolean, date, discrete, file, curve/table, record-reference를 구분해야 한다. | 잘못된 type의 값이 DB/API 양쪽에서 거부된다. |
| `FR-CFG-003` | 수치 Attribute는 original value/unit text, normalized value/unit과 quantity semantics를 함께 보존해야 한다. | datasheet와 JSON export에서 원본과 정규화 값을 모두 조회한다. |
| `FR-CFG-004` | required/default/validation/parameter/conditional visibility를 Attribute revision에 고정해야 한다. | 과거 record revision은 새 definition으로 재해석되거나 덮어쓰이지 않는다. |
| `FR-CFG-005` | 대형 curve/file은 immutable artifact를 참조하고 row-per-point 또는 opaque record JSON을 authority로 사용하지 않아야 한다. | digest와 schema를 통해 record revision에서 원본 artifact까지 추적한다. |
| `FR-CFG-006` | 관리자는 Table별 Layout을 정의해야 한다. | 같은 record를 목적별 datasheet layout으로 표시할 수 있다. |
| `FR-CFG-007` | 사용자는 filter를 저장하여 Subset으로 다시 열 수 있어야 한다. | Subset 실행 시 현재 권한 범위에서 동일 query 정의를 재현한다. |
| `FR-NAV-001` | Catalog Explorer는 Workspace → Table → Folder → Record를 lazy load해야 한다. | breadcrumb와 deep link를 유지하며 대형 tree를 전부 선로딩하지 않는다. |
| `FR-NAV-002` | Workflow Explorer는 Material에서 Release까지 exact revision link를 투영하고 각 domain workbench에서 해당 Catalog node를 역조회해야 한다. | Explorer 노드에서 exact workbench로 이동하고 Material/Test JSON/Processing/Neutral 화면에서 같은 graph로 돌아가 관련 revision을 열 수 있으며 `latest`를 관계로 저장하지 않는다. |
| `FR-NAV-003` | 전체 text와 typed Attribute facet/range 검색을 지원해야 한다. | unit-normalized 수치 범위와 권한 필터가 count/facet에도 동일하게 적용된다. |
| `FR-NAV-004` | 여러 record를 선택한 Layout으로 비교해야 한다. | 값, 단위, 출처와 revision 차이를 한 화면에 표시한다. |
| `FR-NAV-005` | 기존 flat module route를 유지해야 한다. | `/materials`, `/tests`, `/datasets`, `/models`, `/exports`, `/governance`가 계속 동작한다. |
| `FR-NAV-006` | record page는 forward/back link와 breadcrumb를 제공해야 한다. | 검색 또는 link로 이동한 사용자가 이전 문맥으로 돌아갈 수 있다. |
| `FR-LNK-001` | 관리자는 방향명, 허용 source/target Table과 cardinality를 가진 Link Type revision을 정의해야 한다. | 정의에 맞지 않는 endpoint와 개수는 거부된다. |
| `FR-LNK-002` | record link 양 끝은 exact record revision을 고정해야 한다. | head가 바뀌어도 과거 link가 가리키는 content가 변하지 않는다. |
| `FR-LNK-003` | cross-organization/project 또는 classification 역전 link를 거부해야 한다. | service와 PostgreSQL negative test가 모두 통과한다. |
| `FR-LNK-004` | link supersede/remove는 과거 link를 삭제하지 않고 새 상태 revision을 남겨야 한다. | audit과 reverse-link query에서 과거 관계를 재구성한다. |
| `FR-LNK-005` | Workflow Explorer는 record를 복제하지 않고 typed link를 projection해야 한다. | 한 record의 수정이 복제 record divergence를 만들지 않는다. |

### 2.1 재료·시험 문맥

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-CAT-001` | Material의 안정 identity와 content revision을 분리해야 한다. | 이름·조성 변경이 기존 revision을 덮어쓰지 않고 새 revision을 만든다. |
| `FR-CAT-002` | Material State를 Material과 분리해야 한다. | 열처리·수분·노화·물리적 상태를 시험조건과 혼동하지 않고 별도 revision으로 참조한다. |
| `FR-CAT-003` | Manufacturing Process Definition과 실제 Process Run을 분리해야 한다. | 공정 recipe와 실제 실행 날짜·장비·조건·operator가 별도 entity로 조회된다. |
| `FR-CAT-004` | Lot과 Batch를 구분하고 batch input/output 관계를 표현해야 한다. | 하나의 batch가 여러 lot을 소비하거나 lot의 일부가 여러 batch로 갈라지는 예를 저장한다. |
| `FR-CAT-005` | Specimen을 물리적 identity로 관리해야 한다. | geometry, orientation, source lot/batch, preparation, conditioning history를 추적한다. |
| `FR-CAT-006` | Test Method, Test Campaign, Test Run, Test Condition을 분리해야 한다. | 같은 method를 여러 campaign/run이 사용하며 각 run의 condition snapshot이 고정된다. |
| `FR-CAT-007` | Instrument와 instrument calibration reference를 test run에 연결해야 한다. | run 시점의 장비·교정 상태를 조회할 수 있다. |
| `FR-CAT-008` | 도메인별 metadata는 plugin schema로 확장해야 한다. | core migration 없이 새 시험 metadata schema를 등록·검증한다. |

### 2.2 원본 수집과 단위

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-ING-001` | 원본 파일을 streaming upload하고 SHA-256 digest를 계산해야 한다. | 큰 파일을 API 메모리에 전부 적재하지 않고 저장하며 digest가 manifest와 일치한다. |
| `FR-ING-002` | 원본 asset은 application 경로에서 변경할 수 없어야 한다. | raw object overwrite/update endpoint가 없고 동일 key 덮어쓰기가 거부된다. |
| `FR-ING-003` | 동일 바이트 재업로드는 content dedup할 수 있으나 ingestion event는 각각 남겨야 한다. | 하나의 blob에 두 ingestion record가 연결되고 사용자·문맥이 각각 보존된다. |
| `FR-ING-004` | original filename, MIME, byte size, source, timestamp, original unit string을 보존해야 한다. | normalized dataset만으로도 원본 manifest에 역추적된다. |
| `FR-ING-005` | Importer는 detect와 import를 분리해야 한다. | detect 결과를 사용자가 확인한 뒤 고정된 mapping revision으로 import한다. |
| `FR-ING-006` | column semantics, original unit, canonical quantity kind, normalized unit mapping을 명시해야 한다. | stress/strain처럼 차원이 같아도 의미가 다른 column이 semantic type으로 구분된다. |
| `FR-ING-007` | unit conversion은 conversion factor와 offset, library/version, mapping rule을 기록해야 한다. | 동일 conversion을 재계산하고 original/normalized value를 비교할 수 있다. |
| `FR-ING-008` | 알 수 없는 단위·column은 자동 추측으로 확정하지 않아야 한다. | unresolved mapping이 있으면 normalization job이 `needs_input`으로 종료된다. |
| `FR-ING-009` | importer 실패 시 원본 asset과 오류 report를 보존해야 한다. | partial normalized dataset을 성공으로 발행하지 않는다. |
| `FR-ING-010` | 첫 governed tabular importer는 CSV, TSV, XLSX의 sheet/header/encoding/locale을 명시해야 한다. | detect/preview 이후 승인된 Mapping revision만 import하며 spreadsheet formula는 data로 실행하지 않는다. |

### 2.2.1 JSON 교환과 계산 매핑

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-JSON-001` | `cmp.test-data` versioned JSON Schema를 공식 시험 데이터 교환 계약으로 제공해야 한다. | validate/preview/import/export와 lossless round-trip test가 통과한다. |
| `FR-JSON-002` | Test JSON은 maker, date, operator, instrument, specimen, condition과 channel quantity/unit을 포함해야 한다. | 필수 metadata와 channel 의미가 없으면 import가 확정되지 않는다. |
| `FR-JSON-003` | CSV/TSV/XLSX importer는 canonical Test JSON 구조로 수렴해야 한다. | 같은 값의 tabular/JSON fixture가 동일 normalized Dataset을 만든다. |
| `FR-JSON-004` | 원본 JSON bytes와 digest를 보존하고 내부 Parquet 변환을 별도 derived artifact로 기록해야 한다. | JSON export와 계산 artifact가 각각 provenance에 나타난다. |
| `FR-JSON-005` | 25 MiB 초과 또는 복수 문서는 manifest/checksum을 가진 deterministic JSON+ZIP으로 전달해야 한다. | archive path, ordering, digest와 chunk 재조립 test가 통과한다. |
| `FR-JSON-006` | missing observation은 `null`과 reason으로 표현하고 NaN/Infinity JSON을 거부해야 한다. | schema 및 semantic negative fixture가 통과한다. |
| `FR-JSON-007` | `cmp.neutral-material`은 source, mapping, recipe, curve stages, candidates, selected IR, applicability와 mapping evidence를 포함해야 한다. | import 후 같은 IR과 mapping report를 재생성한다. |
| `FR-JSON-008` | Neutral JSON과 solver-native ASCII card를 분리해야 한다. | ZIP manifest가 JSON evidence와 `.inp`/`.rad`를 별도 component로 기록한다. |
| `FR-JSON-009` | Neutral JSON import는 지원되지 않는 model/method version을 명시적으로 거부해야 한다. | unknown version이 silent downgrade되지 않는다. |
| `FR-JSON-010` | 모든 exchange document는 organization/project/classification과 exact revision reference를 포함해야 한다. | cross-scope import와 unresolved reference가 거부된다. |
| `FR-MAP-001` | Mapping Profile은 record Attribute와 test channel을 calculation quantity에 연결하는 stable identity/immutable revision이어야 한다. | profile 변경이 과거 run의 mapping을 바꾸지 않는다. |
| `FR-MAP-002` | Profile은 required channel, accepted quantity/unit, transform과 applicability를 선언해야 한다. | incompatible Dataset은 run 전 preflight에서 거부된다. |
| `FR-MAP-003` | 사용자는 mapping을 확인·수정하고 새 Profile revision으로 저장해야 한다. | UI와 API가 같은 validation report를 표시한다. |
| `FR-MAP-004` | 계산 Run은 exact Mapping Profile revision을 참조해야 한다. | profile head 변경 후에도 run 재현 결과가 같다. |

### 2.3 Dataset, revision, provenance

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-DAT-001` | Dataset identity와 Dataset Revision을 분리해야 한다. | 새 처리 결과가 기존 dataset revision을 수정하지 않는다. |
| `FR-DAT-002` | curve points는 object storage의 typed columnar artifact에 저장해야 한다. | DB에는 schema·statistics·digest·location만 있고 대형 point array가 row-per-point로 저장되지 않는다. |
| `FR-DAT-003` | dataset schema는 channel semantic, dtype, unit, null/mask, independent/dependent axis를 포함해야 한다. | schema validator가 누락과 불일치를 탐지한다. |
| `FR-DAT-004` | 계산 입력 집합을 immutable Selection Revision으로 고정해야 한다. | specimen 추가/제외 후에도 과거 calibration 입력을 정확히 재현한다. |
| `FR-DAT-005` | 모든 derived artifact는 생성 activity와 사용 input entity를 가져야 한다. | provenance completeness 검사에서 고아 산출물이 거부된다. |
| `FR-DAT-006` | revision 간 `wasRevisionOf`와 계산 파생 `wasDerivedFrom`을 구분해야 한다. | 편집 revision과 processing output이 다른 relation으로 조회된다. |
| `FR-DAT-007` | lineage를 upstream/downstream 양방향으로 조회해야 한다. | card에서 raw asset까지, raw asset에서 모든 release까지 탐색한다. |
| `FR-DAT-008` | artifact digest 검증을 주기적으로 수행하고 손상을 보고해야 한다. | 변조 fixture가 integrity job에서 탐지된다. |

### 2.4 QC, 이상치, 통계

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-QC-001` | import/schema/unit/signal/specimen/population 수준의 QC를 구분해야 한다. | 각 QC observation에 level, rule, severity, evidence가 있다. |
| `FR-QC-002` | QC rule과 rule version, parameter를 기록해야 한다. | rule 변경 전후 결과가 별도 run으로 재현된다. |
| `FR-QC-003` | outlier detection은 candidate만 만들고 데이터를 삭제하지 않아야 한다. | candidate 생성 후 원본·normalized dataset의 row/curve 수가 변하지 않는다. |
| `FR-QC-004` | outlier adjudication은 actor, decision, reason, scope, timestamp를 기록해야 한다. | 특정 calibration에서만 제외하고 다른 analysis에는 포함할 수 있다. |
| `FR-STA-001` | specimen/test-run을 기본 독립 표본 단위로 계산해야 한다. | curve point 수가 증가해도 replicate `n`이 증가하지 않는다. |
| `FR-STA-002` | scalar descriptive statistics와 curve ensemble statistics를 분리해야 한다. | 두 결과 유형의 schema와 method가 별도다. |
| `FR-STA-003` | 각 통계량에 n, missingness, method, assumptions, grouping key를 기록해야 한다. | report가 숫자만 표시하지 않고 population 정의를 보여 준다. |
| `FR-STA-004` | mean, SD, median, MAD, IQR, quantile, CV, confidence interval을 지원해야 한다. | near-zero mean에서 CV가 경고 또는 undefined로 처리된다. |
| `FR-STA-005` | curve alignment/resampling을 명시적 Processor activity로 실행해야 한다. | Statistical Analyzer가 숨은 interpolation으로 원본 곡선을 바꾸지 않는다. |
| `FR-STA-006` | curve band의 공통 domain, grid, interpolation, extrapolation policy를 기록해야 한다. | overlap 밖을 기본적으로 mask하고 임의 extrapolation하지 않는다. |
| `FR-STA-007` | lot/batch/orientation/rate/temperature 등 strata 비교를 지원해야 한다. | grouping 차원을 바꾼 analysis가 독립 revision으로 저장된다. |

### 2.5 전처리와 보정

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-PRO-001` | processing recipe를 ordered step과 parameter로 versioning해야 한다. | smoothing, cropping, offset, conversion 등 모든 step이 manifest에 있다. |
| `FR-PRO-002` | preview와 committed run을 구분해야 한다. | preview artifact는 release provenance 입력으로 사용할 수 없다. |
| `FR-PRO-003` | 각 step은 input/output schema와 diagnostics를 선언해야 한다. | incompatible step composition이 실행 전에 거부된다. |
| `FR-PRO-004` | manual point edit도 재현 가능한 operation으로 표현해야 한다. | 수정 point, before/after, actor, reason이 recipe step으로 남는다. |
| `FR-PRO-005` | method registry는 method ID/version, input/output quantity, option schema, applicability와 deterministic 여부를 제공해야 한다. | UI가 registry schema로 option editor와 preflight를 구성한다. |
| `FR-PRO-006` | common workbench는 crop, scale/shift, resample, moving-average, Savitzky–Golay, spline, alignment와 통계를 ordered step으로 제공해야 한다. | 단계별 overlay와 committed output revision이 일치한다. |
| `FR-PRO-007` | 사용자는 기존 Recipe를 불러와 수정하고 새 revision으로 저장해야 한다. | published revision이 수정되지 않고 draft revision이 추가된다. |
| `FR-PRO-008` | processing은 단계별 diagnostics와 warning/failure를 보존해야 한다. | 부분 계산이 성공 결과로 발행되지 않는다. |
| `FR-PRO-009` | 금속, 폴리머, 엘라스토머 method는 공통 registry 계약을 사용해야 한다. | core가 특정 재료 family 구현을 직접 import하지 않는다. |
| `FR-PRO-010` | raw, normalized, processed, fitted, extrapolated curve를 UI와 exchange에서 구분해야 한다. | 사용자가 각 stage와 적용 operation을 역추적한다. |
| `FR-BAT-001` | Batch는 ordered Dataset Selection, Mapping Profile과 Recipe revision을 고정해야 한다. | 실행 중 head가 바뀌어도 member 입력은 변하지 않는다. |
| `FR-BAT-002` | 실행 전 member별 compatibility preflight를 제공해야 한다. | incompatible member와 이유가 계산 전에 표시된다. |
| `FR-BAT-003` | member 결과는 독립 Processing Run/Output revision이어야 한다. | 한 member 실패가 성공 member를 롤백하거나 덮어쓰지 않는다. |
| `FR-BAT-004` | 실패한 member만 동일 입력으로 재실행할 수 있어야 한다. | retry가 성공 결과를 중복 생성하지 않고 attempt를 기록한다. |
| `FR-BAT-005` | batch 결과는 success/failure/warning과 output revision을 항목별로 제공해야 한다. | API와 Batch Monitor count가 일치한다. |
| `FR-BAT-006` | deterministic Recipe는 동일 입력에서 tolerance 내 동일 결과를 내야 한다. | batch regression fixture가 재현된다. |
| `FR-CAL-001` | Material Model과 Calibrator를 분리해야 한다. | 동일 model evaluator에 서로 다른 calibrator를 적용한다. |
| `FR-CAL-002` | calibration plan은 inputs, parameters, bounds, objective, weighting, constraints, seed를 고정해야 한다. | run manifest만으로 설정을 재구성한다. |
| `FR-CAL-003` | plugin/package/container digest와 source commit, dependency lock을 기록해야 한다. | 이름·semantic version이 같아도 digest가 다른 실행을 구분한다. |
| `FR-CAL-004` | convergence, objective history, residual, warnings, failure reason을 보존해야 한다. | 실패한 run도 검색·비교 가능하다. |
| `FR-CAL-005` | multi-start 및 candidate comparison을 지원해야 한다. | 각 attempt와 최종 선택 이유가 분리된다. |
| `FR-CAL-006` | train/calibration selection과 holdout/validation selection을 구분해야 한다. | 동일 specimen 중복 사용을 policy에 따라 차단 또는 경고한다. |
| `FR-CAL-007` | parameter uncertainty 또는 식별성 diagnostic의 schema를 제공해야 한다. | 미지원 calibrator는 `not_provided`를 명시하고 빈 값을 성공처럼 표시하지 않는다. |
| `FR-CAL-008` | 같은 Material Model을 반복 보정할 때 prior promotion evidence를 보존해야 한다. | 같은 stable identity에 새 IR revision과 revision-owned evidence를 append하고 과거 IR/Card/Release digest가 변하지 않는다. |

### 2.5.1 Material Modeling reference track

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-MOD-M-001` | 금속 tensile workbench는 자동 선형구간, 지정구간 회귀, chord/secant와 수동 slope 방식의 탄성계수 평가를 구분해야 한다. | method별 option과 결과가 Recipe/Neutral JSON에 남는다. |
| `FR-MOD-M-002` | proof stress는 0.2%와 사용자 offset 및 수동 판정을 지원해야 한다. | 선택 방법과 교차점 diagnostics가 보존된다. |
| `FR-MOD-M-003` | engineering/true 및 true plastic strain 변환을 명시적 step으로 수행해야 한다. | hidden 변환 없이 수식 version과 입력 E가 기록된다. |
| `FR-MOD-M-004` | necking point는 수동 선택과 자동 candidate를 분리해야 한다. | 자동 candidate가 원본을 자르거나 확정하지 않는다. |
| `FR-MOD-M-005` | Voce, Swift, Hockett–Sherby와 Ghosh 계열 공개식 후보를 같은 objective 계약으로 비교해야 한다. | 공개 수식 fixture와 candidate별 residual test가 통과한다. |
| `FR-MOD-M-006` | fitting 선택 또는 두 후보의 명시적 구간/비율 조합을 새 curve revision으로 저장해야 한다. | 조합 방식과 범위가 Neutral JSON에 재현된다. |
| `FR-MOD-M-007` | 지정 strain까지 외삽하되 fitted domain과 extrapolated domain을 구분해야 한다. | validity 경계를 넘으면 UI/card preflight가 경고한다. |
| `FR-MOD-P-001` | 점탄성 workbench는 relaxation/modulus-time 입력과 log-time resampling을 지원해야 한다. | time/modulus quantity와 domain이 검증된다. |
| `FR-MOD-P-002` | generalized Maxwell/Prony term 수, initial value, bounds와 수동/자동 term 선택을 지원해야 한다. | candidate별 term, prediction, residual과 warning이 남는다. |
| `FR-MOD-P-003` | 온도 series는 수동 shift와 WLF/Arrhenius candidate를 지원해야 한다. | shift factor, reference temperature와 master-curve domain이 저장된다. |
| `FR-MOD-P-004` | 검토된 1~10항 generalized-Maxwell Processing Output은 exact source/profile/output digest와 modulus-consistency evidence를 보존하며 IR과 Neutral JSON으로 승격되어야 한다. | 사용자가 fitted candidate를 확인·승인한 뒤 solver card까지 이동할 수 있고 client가 fitted parameter를 바꿀 수 없다. OpenRadioss는 ADR-0032의 nearly-incompressible, shear-only `/VISC/LPRONY` 조건만 허용하며 LAW62로 silent 변환할 수 없다. |
| `FR-MOD-P-005` | OpenRadioss linear-Prony preflight는 bulk 미특성화·zero `k_ratio`, `0.49 <= nu < 0.5`, Form 2/`flag_visc=2`와 외부 solid `/PROP`의 `I_smstr=10/12` 요구를 명시해야 한다. | 조건 위반은 `unsupported`; 허용 조합의 근사와 외부 property 요구는 `approximated`로 표시되어 사용자 확인 전 card 생성이 차단된다. |
| `FR-MOD-E-001` | 초탄성 workbench는 uniaxial, planar, biaxial Dataset과 시험별 weight/domain을 지원해야 한다. | Plan이 exact multi-test selection을 고정한다. |
| `FR-MOD-E-002` | Neo-Hookean, Mooney–Rivlin, Yeoh와 Ogden 공개 모델을 동일 candidate contract로 실행해야 한다. | 모델별 analytical fixture와 multistart regression이 통과한다. |
| `FR-MOD-E-003` | model stability, bounds, non-finite, extrapolation과 physical constraint를 별도 diagnostics로 제공해야 한다. | objective success만으로 `validated`가 되지 않는다. |
| `FR-MOD-E-004` | hyperelastic IR에 선택적 Prony viscoelastic overlay를 연결해야 한다. | unsupported solver 조합은 preflight에서 실패한다. |
| `FR-MOD-001` | 모든 model 결과는 `reference`, `validated`, `production-approved`를 구분해야 한다. | reference 결과가 production release로 오인되지 않는다. |

### 2.6 Material Model IR와 solver card

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-IR-001` | 모든 production card는 released 또는 release-candidate IR revision에서 생성해야 한다. | raw parameter dict에서 exporter를 직접 호출하는 API가 없다. |
| `FR-IR-002` | IR은 model family/schema version, quantities/units, conventions, applicability, validity domain을 포함해야 한다. | schema와 semantic validator가 누락을 거부한다. |
| `FR-IR-003` | table/function은 axes semantics, interpolation, extrapolation, monotonicity policy를 포함해야 한다. | 값 배열만 있는 curve가 release validation을 통과하지 않는다. |
| `FR-IR-004` | IR core envelope와 model-plugin-owned payload schema를 분리해야 한다. | 새 model family를 core DB migration 없이 등록한다. |
| `FR-IR-005` | exporter는 capability 및 mapping report를 먼저 생성해야 한다. | exact/transformed/approximated/unsupported 항목이 machine-readable하다. |
| `FR-EXP-001` | card 생성은 target solver/name/version, unit system, exporter digest, options를 기록해야 한다. | card header 또는 sidecar manifest와 DB가 일치한다. |
| `FR-EXP-002` | unsupported mapping은 실패해야 하며 approximation은 policy 승인 없이는 release할 수 없어야 한다. | negative contract test가 통과한다. |
| `FR-EXP-003` | card text와 semantic normalized representation을 비교할 수 있어야 한다. | golden test가 volatile text와 semantic change를 구분한다. |
| `FR-EXP-004` | exporter는 target solver card를 parsing하거나 최소 syntax validation hook을 제공해야 한다. | 잘못된 keyword/field fixture가 validation에서 실패한다. |
| `FR-EXP-005` | 사용자는 선택한 test data, neutral IR, mapping report와 card를 immutable Bulk Export Bundle로 받을 수 있어야 한다. | archive의 manifest/checksum이 모든 파일과 exact source revision을 검증하고 누락·미지원 항목을 조용히 제외하지 않는다. |
| `FR-EXP-006` | Bulk Export와 governed Release의 의미를 분리해야 한다. | Release lifecycle 또는 manifest를 변경하지 않고 별도 Export Selection/Job/Bundle이 생성된다. |

### 2.7 가상 시편 검증

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-VAL-001` | Validation Template은 geometry, mesh, BC, loading, output extraction, metric을 versioning해야 한다. | template 변경이 새 revision을 만든다. |
| `FR-VAL-002` | Validation Plan은 IR/card, dataset selection, template, solver runner를 고정해야 한다. | 실행 후 input pointer가 최신 head로 바뀌지 않는다. |
| `FR-VAL-003` | solver deck, stdout/stderr, solver status, raw result, extracted response를 보존해야 한다. | 실패 run도 log와 deck을 내려받을 수 있다. |
| `FR-VAL-004` | 수동 실행 결과 반입과 managed runner 실행을 동일 Result Manifest로 표현해야 한다. | 두 경로의 provenance completeness가 동일하다. |
| `FR-VAL-005` | numerical verification와 experimental validation status를 분리해야 한다. | 정상 종료만으로 validation pass가 되지 않는다. |
| `FR-VAL-006` | metric threshold와 판정 규칙을 versioning해야 한다. | threshold 변경 전후 판정이 재현된다. |

### 2.8 검토·승인·발행

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-WF-001` | Draft, Submitted, In Review, Approved, Released, Superseded, Withdrawn 상태를 관리해야 한다. | 허용되지 않은 transition이 거부된다. |
| `FR-WF-002` | review request와 decision을 append-only로 기록해야 한다. | 기존 승인 comment를 수정할 수 없다. |
| `FR-WF-003` | release 전 provenance, required evidence, unresolved issue, mapping policy를 자동 검사해야 한다. | 하나라도 실패하면 release가 생성되지 않는다. |
| `FR-WF-004` | release는 IR, cards, validation, report, manifest digest를 고정해야 한다. | release 이후 구성 artifact가 바뀌지 않는다. |
| `FR-WF-005` | supersede/withdraw는 과거 release를 삭제하지 않아야 한다. | 과거 사용 이력과 당시 package가 조회된다. |
| `FR-WF-006` | production channel은 released artifact만 노출해야 한다. | draft/card URL을 production consumer token으로 읽지 못한다. |

### 2.9 플러그인·API·운영

| ID | 요구사항 | 검수 기준 |
| --- | --- | --- |
| `FR-PLG-001` | Importer, Processor, Statistical Analyzer, Material Model, Calibrator, Validator, Solver Exporter extension type을 등록해야 한다. | 각 type의 sample plugin이 compatibility suite를 통과한다. |
| `FR-PLG-002` | plugin manifest에 ID, version, API range, digest, schemas, capabilities, resource/network policy가 있어야 한다. | 누락 manifest가 설치되지 않는다. |
| `FR-PLG-003` | core API process가 plugin code를 직접 import하지 않아야 한다. | architecture test가 core→plugin implementation dependency를 탐지한다. |
| `FR-PLG-004` | plugin run은 immutable Job Spec과 Result Manifest로 통신해야 한다. | worker 재시작 후에도 job을 복구한다. |
| `FR-PLG-005` | plugin package 설치·활성화·폐기 이력을 감사해야 한다. | 같은 semantic version의 digest 교체가 금지된다. |
| `FR-API-001` | REST API는 OpenAPI로 정의하고 optimistic concurrency 및 idempotency를 지원해야 한다. | `If-Match`, `Idempotency-Key` contract test가 통과한다. |
| `FR-API-002` | 장시간 작업은 `202 Accepted`와 Job resource를 사용해야 한다. | HTTP request가 solver/calibration 완료까지 열린 채 유지되지 않는다. |
| `FR-API-003` | domain event는 transactional outbox에 기록해야 한다. | DB commit과 event 누락/유령 event가 발생하지 않는다. |
| `FR-API-004` | event consumer는 at-least-once delivery에서 idempotent해야 한다. | duplicate event fixture가 중복 side effect를 만들지 않는다. |
| `FR-SRCH-001` | material, state, lot/batch, test condition, model, solver target, release 상태로 검색해야 한다. | 권한 밖 record가 search count와 facet에도 노출되지 않는다. |
| `FR-ACC-001` | 제품 역할은 Administrator와 User를 기본으로 표시해야 한다. | 사용자 관리 UI가 내부 역할 vocabulary를 요구하지 않는다. |
| `FR-ACC-002` | schema 관리, catalog 편집, processing/calibration, model 승인과 card export를 feature grant로 제어해야 한다. | grant별 positive/negative API·UI test가 통과한다. |
| `FR-ACC-003` | 기존 세부 permission과 RLS는 feature grant의 내부 enforcement로 유지해야 한다. | 기존 token과 tenant isolation regression이 유지된다. |
| `FR-ACC-004` | 권한 설명은 작업 중심이어야 하며 보안 foundation을 제품 핵심 흐름보다 앞세우지 않아야 한다. | README와 UI가 가능한 작업과 필요한 grant를 먼저 설명한다. |
| `FR-UX-001` | GUI 변경 Task는 task-oriented user/admin guide와 deterministic screenshot을 함께 갱신해야 한다. | guide manifest가 stale/missing capture를 차단한다. |
| `FR-UX-002` | Dashboard에서 Catalog 탐색, 시험 처리와 card 생성 시작점을 제공해야 한다. | E2E가 각 시작점에서 실제 workbench까지 이동한다. |
| `FR-UX-003` | API error를 domain action과 해결 방법으로 표시해야 한다. | 사용자가 trace ID와 수정 가능한 입력을 확인한다. |

## 3. 비기능 요구사항

아래 수치는 `ASSUMPTION` 기반 초기 service-level objective다. 실제 데이터 샘플과 사용자를 측정한 뒤 수정한다.

### 3.1 데이터 무결성과 재현성

| ID | 요구사항/초기 목표 |
| --- | --- |
| `NFR-INT-001` | raw blob과 released artifact는 100% digest를 가지며 write-once key를 사용한다. |
| `NFR-INT-002` | DB transaction이 성공했으나 object가 없거나 그 반대인 상태를 reconciliation job이 탐지한다. |
| `NFR-REP-001` | deterministic plugin은 동일 input/config/image digest에서 byte-identical 또는 선언된 numeric tolerance 내 결과를 낸다. |
| `NFR-REP-002` | release provenance completeness check는 누락 0건이어야 한다. |
| `NFR-REP-003` | random algorithm은 seed와 RNG/library version을 기록한다. |

### 3.2 성능·용량

| ID | 요구사항/초기 목표 |
| --- | --- |
| `NFR-PERF-001` | 일반 metadata read/write API p95 < 500 ms, p99 < 1.5 s; object transfer와 계산은 제외한다. |
| `NFR-PERF-002` | 10,000개 material/release 범위의 권한 필터 검색 p95 < 2 s를 목표로 한다. |
| `NFR-PERF-003` | 10 hop 또는 10,000 edge 이내 lineage 조회 p95 < 2 s를 목표로 한다. |
| `NFR-PERF-004` | 최소 2 GiB 단일 파일을 streaming 방식으로 수집할 수 있어야 한다. 최대값은 배포 정책으로 설정한다. |
| `NFR-PERF-005` | 단일 curve dataset 10 million points를 columnar artifact로 처리하되 UI에는 downsampled view를 제공한다. |
| `NFR-PERF-006` | worker concurrency와 CPU/GPU/memory/time quota를 job class별로 설정한다. |

### 3.3 가용성·복구

| ID | 요구사항/초기 목표 |
| --- | --- |
| `NFR-AVL-001` | MVP 월 가용성 목표 99.5%; 계획된 정비 제외. |
| `NFR-DR-001` | metadata RPO ≤ 15분, RTO ≤ 4시간을 목표로 한다. raw/release object는 versioning/replication 정책을 적용한다. |
| `NFR-DR-002` | 장시간 job은 worker/process 재시작 후 lease timeout과 attempt 기록으로 복구한다. |
| `NFR-DR-003` | backup restore drill을 정기 실행하고 restore된 digest와 provenance를 검증한다. |

### 3.4 보안·격리

| ID | 요구사항/초기 목표 |
| --- | --- |
| `NFR-SEC-001` | enterprise IdP의 OIDC를 기본으로 하고 MFA 정책은 IdP에 위임한다. |
| `NFR-SEC-002` | deny-by-default RBAC + project/data-classification ABAC를 적용한다. |
| `NFR-SEC-003` | PostgreSQL RLS와 service-layer authorization을 함께 사용하며 RLS bypass role을 application에 부여하지 않는다. |
| `NFR-SEC-004` | 전송 TLS, 저장 암호화, secret manager, short-lived object access를 사용한다. |
| `NFR-SEC-005` | plugin은 기본 network deny, read-only input, ephemeral output, resource quota로 실행한다. |
| `NFR-SEC-006` | 조직/project 간 권한 누출 test를 모든 release에 실행한다. |
| `NFR-AUD-001` | 보안·데이터·승인·plugin·runner 관리 event를 append-only audit에 기록한다. |
| `NFR-AUD-002` | audit log는 hash chain 또는 주기적 signed root로 tamper evidence를 제공한다. |

### 3.5 유지보수·확장성

| ID | 요구사항/초기 목표 |
| --- | --- |
| `NFR-MOD-001` | core domain module 사이 dependency rule을 architecture test로 강제한다. |
| `NFR-MOD-002` | 새 시험·모델·solver plugin 추가에 core schema 변경이 필수여서는 안 된다. 단, 새 공통 개념이 발견되면 ADR 후 core를 확장할 수 있다. |
| `NFR-COMP-001` | API, event, plugin SDK, IR은 각각 semantic version과 compatibility policy를 가진다. |
| `NFR-COMP-002` | 하나의 major 전 버전 plugin contract를 최소 migration window 동안 지원한다는 목표를 둔다. |
| `NFR-OBS-001` | request/job/plugin/solver 실행에 trace ID를 전달하고 logs, metrics, traces를 연계한다. |
| `NFR-DOC-001` | public contract는 OpenAPI, AsyncAPI 또는 JSON Schema로 machine-readable하게 제공한다. |
| `NFR-DOC-002` | 사용자가 Material 등록부터 시험 데이터 처리와 card 다운로드를 수행하는 task-oriented guide를 제공하고 user-visible GUI 변경 시 관련 이미지와 절차를 갱신한다. |

### 3.6 과학적 품질과 사용성

| ID | 요구사항/초기 목표 |
| --- | --- |
| `NFR-SCI-001` | numeric function은 reference dataset, tolerance, assumptions, failure domain을 문서화한다. |
| `NFR-SCI-002` | UI는 raw/processed/fitted/simulated curve를 동일 축·단위로 비교하고 변환 상태를 명시한다. |
| `NFR-SCI-003` | 경고·실패·미평가를 색상만으로 구분하지 않고 text/status code를 함께 표시한다. |
| `NFR-SCI-004` | plot downsampling은 통계·fitting input에 사용되지 않고 display artifact로만 취급한다. |
| `NFR-I18N-001` | UI locale과 별개로 numeric serialization은 locale-neutral하고 소수점·단위 parsing 규칙을 명시한다. |

## 4. MVP 요구사항 제외 조건

다음 항목은 core contract를 설계하되 production 구현은 도메인 결정 후 진행한다.

- `TBD-TEST`: 인장시험 표준, 재료군, 필수 metadata, raw format
- `TBD-MODEL`: 구성방정식, parameterization, objective/constraint
- `TBD-SOLVER`: solver, version, card keyword, unit system
- `TBD-VSPEC`: specimen geometry/mesh/BC, extracted response, pass/fail threshold

이 결정이 없다고 core 작업을 중단하지 않는다. synthetic fixtures와 reference plugins으로 계약을 구현한다.

