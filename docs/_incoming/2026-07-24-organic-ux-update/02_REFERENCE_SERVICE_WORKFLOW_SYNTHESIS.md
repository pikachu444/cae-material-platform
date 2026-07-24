# Granta·Material Modeler 실제 사용 방식과 제품 적용 원리

## 1. 읽는 법

이 문서는 참고 서비스의 기능 목록이 아니라 사용자가 실제로 수행하는 일을 재구성한다.

- **FACT**: 공식 제품 페이지나 도움말로 확인된 동작
- **OBSERVATION**: 공개 화면·도움말 구조에서 관찰한 UI 패턴
- **DECISION**: 현재 CAE Material Platform에 적용할 설계 결정
- **NOT ADOPTED**: 참고 제품에 있어도 현재 제품 경계상 채택하지 않는 것

참고 서비스의 명칭·메뉴·정보 구조를 그대로 복제하지 않는다. 공식 사실을 제품 요구사항으로 채택하려면 현재 사용자 문제와 domain contract에 맞는 이유가 있어야 한다.

## 2. 제품별 역할을 먼저 분리한다

| 제품 역할 | 대표 사용자 질문 | 실제 흐름 | 현재 제품의 대응 영역 |
|---|---|---|---|
| Granta MI / Material Data Center 탐색 | “우리 조직에서 승인된 이 재료의 정확한 조건·revision·근거·CAE 모델은 무엇인가?” | scope → search/tree → facet → results → datasheet/evidence → compare → model/card reuse | `Materials` |
| Granta Selector | “요구조건과 trade-off를 만족하는 후보 재료군은 무엇인가?” | selection project → Tree/Limit/Chart stage → shortlist → compare → 선택 근거 | 미래 `Selection study`; 일반 검색과 분리 |
| Material Modeler | “이 시험 데이터로 재현 가능한 constitutive model을 어떻게 만들고 검증할 것인가?” | objective → import/map → prepare/workup → fit → extrapolation/stability → validate → save/review/release → export | `Modeling` |
| Granta MI / SMDC governance | “누가 무엇을 바꿨고 어느 version이 조직에서 사용 가능한가?” | author/edit → commit version → review → publish/release → successor version | `Materials` detail, `Activity`, 역할 기반 admin |

이 구분이 중요한 이유는 “재료 찾기”, “재료 선정 연구”, “시험 데이터 fitting”, “조직 승인”이 서로 다른 사용자 판단과 데이터 상태를 갖기 때문이다. 하나의 왼쪽 필터와 오른쪽 폼에 전부 섞으면 어떤 입력이 검색 조건인지, 모델 parameter인지, 조직 정책인지 알 수 없게 된다.

## 3. Granta MI: governed material knowledge를 사용하는 방식

### 3.1 탐색과 검색

**FACT**

- Profile은 사용자가 접근하는 table·tree·subset·search 범위를 정하고, Layout은 record에서 보이는 attribute 구성을 정한다.
- 사용자는 계층 tree로 record를 탐색하거나 text/advanced search를 사용한다.
- 고급 검색은 typed property, 단위가 있는 threshold, ALL/ANY 조건, linked attribute와 version state를 다룬다.
- 결과는 정렬·열 조정이 가능한 list와 datasheet로 이어진다.

공식 근거:

- [Granta MI Viewer: Browsing your data](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/GetStart_Profile.html)
- [Granta MI Viewer: Advanced search](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/Search_AdvancedSearch.html)
- [Granta Materials Gateway: Advanced search using filters](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Materials_Gateway/gw/advanced_search_using_filters.html)

**DECISION**

- `Materials`는 search-first와 tree browse를 모두 제공한다.
- 좌측 rail은 “아무 항목을 클릭하면 입력 폼이 나타나는 곳”이 아니다.
- Tree는 category·subset으로 scope를 바꾸고, facet은 현재 result set을 좁히며, advanced criteria는 별도 의도적 작업이다.
- scope가 하나뿐이면 가짜 select를 노출하지 않고 `Enterprise Materials · Released` 같은 read-only context로 표시한다.
- 내부 database/table/profile key는 정상 경로에서 숨긴다.

### 3.2 Datasheet와 evidence

**FACT**

- Granta datasheet는 목적에 따른 layout을 사용하고, tabular/functional data와 curve를 보여준다.
- version context와 linked record를 통해 값의 출처·관계를 추적할 수 있다.
- full/summary/hidden 같은 progressive disclosure가 가능하다.

공식 근거:

- [View a datasheet](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Materials_Gateway/gw/view_a_datasheet.html)
- [Viewing tabular data](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/Datasheet_tabulardata.html)

**DECISION**

- material detail은 모든 attribute를 하나의 긴 accordion으로 펼치지 않는다.
- header에서 identity, form/condition, release state, current/superseded, version, provider를 먼저 확인하게 한다.
- value 가까이에 unit, temperature, direction, strain rate, source type, revision을 표시한다.
- `Overview | Properties | Curves | CAE Cards | Evidence` 같은 목적별 layout을 사용한다.
- UUID, hash, plugin key, raw JSON은 `Evidence/Advanced`에서만 보인다.

### 3.3 Material model과 solver 전달

**FACT**

- Granta는 material record와 model definition을 연결하고 exporter attribute, unit, transformation, compatible model type을 다룬다.
- material model에 필요한 parameter가 없으면 missing-data 상태가 발생할 수 있다.
- specialized CAE simulation record와 일반 material record는 관련 record로 연결될 수 있다.

공식 근거:

- [Material models](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Materials_Gateway/gw/material_models.html)
- [Specify parameter values](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Materials_Gateway/gw/specify_parameter_values.html)
- [Simulation records and models](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Materials_Gateway/gw/simulation_records_and_models.html)

**DECISION**

- 재료, 시험 데이터, calibrated physical model, solver-neutral IR, solver card를 같은 객체처럼 표시하지 않는다.
- CAE card action은 target solver/version, solver law, unit system, condition, mapping state, validation/release를 선택·확인한 뒤 실행한다.
- `Preview card`가 여러 solver target 중 무엇인지 모호하면 안 된다. row별 target action 또는 명시적 target chooser가 필요하다.
- mapping은 `exact | transformed | approximated | unsupported`를 숨기지 않는다.

### 3.4 Version과 governance

**FACT**

- Granta MI는 version control, 권한, workflow를 재료 정보 관리의 핵심으로 둔다.
- read/edit와 release·withdraw 같은 privileged action은 구분된다.

공식 근거:

- [Ansys Granta MI](https://www.ansys.com/products/materials/granta-mi)
- [Read and edit modes](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/GetStart_Read_Edit.html)

**DECISION**

- released record를 직접 덮어쓰지 않는다.
- 변경은 새 working revision을 만들고 review·approval·release를 거친다.
- 조회 사용자에게 admin control을 섞지 않는다.
- `Draft`, `In review`, `Changes requested`, `Approved`, `Released`, `Superseded`, `Withdrawn`을 같은 “status” 드롭다운 하나로 뭉개지 않는다.

## 4. Granta Selector: 일반 검색과 다른 selection study

**FACT**

- Granta Selector는 property constraint와 chart selection을 단계적으로 조합해 후보를 거르고 trade-off를 비교하는 도구다.

공식 근거:

- [Ansys Granta Selector](https://www.ansys.com/products/materials/granta-selector)
- [Selection stages](https://ansyshelp.ansys.com/public/account/secured?returnurl=%2FViews%2FSecured%2FGranta%2Fv261%2Fen%2FSelector%2Fsel_edu%2Fselection_stages_about.html)

**DECISION**

- `DP780`처럼 이미 아는 재료를 찾는 Find와 “밀도·강성·비용 trade-off로 후보군을 고르는” Selection study를 분리한다.
- 초기 업데이트에서 decorative Ashby chart나 자동 “최적 재료” 추천을 넣지 않는다.
- 실제 stage, limit, chart interaction, shortlist rationale를 지원할 수 있을 때 별도 workflow로 추가한다.

**NOT ADOPTED**

- 일반 Materials results의 view toggle로 Selection study를 가장하는 것
- 근거가 없는 단일 점수로 후보를 자동 순위화하는 것
- property의 방향성이 항상 “높을수록 좋다” 또는 “낮을수록 좋다”고 색칠하는 것

## 5. Simcenter Material Data Center: search·compare·review·card download

### 5.1 Quick search와 facet

**FACT**

- quick search는 name, type, characteristic, property suggestion과 value range를 지원한다.
- 좌측 filter는 Type, Producer, Provider, Software 등 명시된 범주를 사용한다.

공식 근거:

- [Quick Search](https://2025.help.altair.com/altairone/topics/materialsdb/material_quicksearch_t.htm)
- [Filter Materials](https://2025.help.altair.com/altairone/topics/materialsdb/materials_filter_t.htm)

**DECISION**

- categorical facet은 label, count, selected state, zero-result behavior, group clear가 있어야 한다.
- continuous property는 unit-aware min/max와 missing/not-applicable 구분이 필요하다.
- material family와 active layout에 무관한 property facet은 숨긴다.
- `Manufacturer/source`처럼 서로 다른 provenance 개념을 한 값으로 합치지 않고 `Provider`와 `Evidence source`를 분리한다.

### 5.2 Compare

**FACT**

- Material Data Center는 여러 material의 property와 plot을 나란히 비교하는 기능을 제공한다.

공식 근거:

- [Compare Materials](https://2025.help.altair.com/altairone/topics/materialsdb/materials_compare_t.htm)

**DECISION**

- result row selection과 compare shortlist는 별도 상태다.
- compare tray에서 add/remove/reorder/base pin을 명시한다.
- unit을 통일하고 condition mismatch, missing, restricted, measured/derived/fitted 차이를 함께 보여준다.
- 초기 수용 범위를 3~5개 material로 제한해도 되지만 command bar의 영구 disabled Compare는 제거한다.

### 5.3 Review, version, CAE card

**FACT**

- data review와 publish, version control은 별도 흐름이다.
- CAE model download는 solver·model·condition·unit과 같은 전달 문맥을 선택하고 card preview로 이어진다.

공식 근거:

- [Material data review](https://2025.help.altair.com/altairone/topics/materialsdb/material_data_review_r.htm)
- [Version control](https://2025.help.altair.com/altairone/topics/materialsdb/version_control_dataedit_t.htm)
- [CAE models download](https://2025.help.altair.com/altairone/topics/materialsdb/cae_models_download_t.htm)

**DECISION**

- Save, Select, Submit for review, Approve, Release, Generate, Deliver를 한 버튼으로 합치지 않는다.
- solver card가 존재한다는 사실과 현재 condition에 사용할 수 있다는 판단을 구분한다.
- card row에는 solver/version, law, source model, condition, unit, mapping, validation, release, updated time, blocked reason을 포함한다.

## 6. Material Modeler: import에서 solver card까지

### 6.1 제품의 중심 흐름

**FACT**

Siemens는 Simcenter Material Modeler 2026을 raw test data를 정리·처리하고 constitutive model을 calibrate하며 simulation-ready card로 전달하는 browser-based product로 소개한다. 공개 설명에는 곡선 정리·smoothing·mean, Young’s modulus·necking·Rp0.2 또는 사용자 기준 검출, law fitting과 extrapolation, Material Data Center와의 provenance 연결이 포함된다.

공식 근거:

- [Simcenter Material Modeler 2026 소개](https://blogs.sw.siemens.com/simcenter/material-model-calibration-for-cae/)

**제한**

- 2026 제품의 전체 상세 UI와 모든 import/export 형식은 공개 도움말로 완전히 확인되지 않았다.
- “regardless of format” 같은 제품 소개 문구를 현재 parser 지원 범위로 해석하지 않는다.
- 2025 Altair 도움말 화면을 2026 Siemens UI라고 부르거나 그대로 복제하지 않는다.

### 6.2 Import와 mapping

**FACT**

- 시험 데이터를 불러온 뒤 축·열·단위의 의미를 확인하고 처리 가능한 curve로 준비한다.
- engineering data의 원본과 처리 결과를 구분한다.

공식 근거:

- [Material Modeler 2025: Import Data](https://help.altair.com/material_modeler/topics/material_modeler/data_import_t.htm)

**DECISION**

- Data 단계는 `Inspect source → Confirm mapping → Save dataset`의 상태형 작업이다.
- raw 파일, test run, specimen, test type, temperature, direction, rate, raw unit, normalized unit, source revision을 함께 고정한다.
- mapping error가 나도 입력 파일, 선택 열, raw preview와 plot zoom을 보존한다.
- “업로드 완료”를 reviewed dataset으로 부르지 않는다.

### 6.3 Prepare/Workup와 Yield definition

**FACT**

- metal elastoplastic workflow에서는 Young’s modulus를 자동 또는 수동으로 구하고, curve를 scale·shift·smooth·mean할 수 있다.
- Rp0.2 또는 사용자 정의 yield criterion과 necking point는 engineering stress–strain을 true stress–true plastic strain으로 변환하고 elastic/plastic 영역을 나누는 과정에 쓰인다.

공식 근거:

- [Prepare Data](https://help.altair.com/material_modeler/topics/material_modeler/prepare_data_t.htm)
- [Simcenter Material Modeler 2026 소개](https://blogs.sw.siemens.com/simcenter/material-model-calibration-for-cae/)

**DECISION**

`Yield strength`라는 bare input을 Fit이나 모든 material의 공통 form에 두지 않는다.

대신 metal workflow의 `Process > Elastic–plastic separation`에 다음 component를 둔다.

| 항목 | 명세 |
|---|---|
| label | `Yield definition` |
| 기본 mode | `Rp0.2 · derived from curve` |
| 대안 | `User-defined criterion` |
| source | selected processed tensile curve와 modulus definition |
| output | calculated yield stress, detection range, graph marker, source |
| manual override | value, unit, reason이 모두 필요 |
| validation | 음수, curve 범위 밖, necking 이후, elastic sample 부족 차단 |
| invalidation | processed dataset 새 revision; Fit·Validate·Review·Export stale |
| family visibility | metal elastoplastic만 표시; hyperelastic·viscoelastic에서는 숨김 |
| evidence relation | supplier datasheet yield는 참고 evidence이며 curve-derived 값을 조용히 대체하지 않음 |

### 6.4 Curve fitting과 candidate 판단

**FACT**

- 사용자는 prepared curve에 fitting approach와 range를 적용하고 graph/derivative로 결과를 본다.
- 여러 fit을 선택·비교하고, 필요하면 law를 blend하며, 선택한 상태를 저장한다.

공식 근거:

- [Curve Fitting](https://help.altair.com/material_modeler/topics/material_modeler/curve_fitting_t.htm)

**DECISION**

- 최저 RMSE나 BIC는 `Recommended`일 수 있지만 `Selected`가 아니다.
- 후보 table은 metric definition, fit range, extrapolation, stability, parameter/bounds, solver compatibility를 함께 보여준다.
- `Single law`와 `Blend`를 별도 mode로 둔다.
- blend output identity는 두 law와 ratio를 끝까지 보존한다.
- 사용자가 row action으로 후보를 선택하고 이유를 기록하기 전에는 Save candidate나 Submit for review를 할 수 없다.
- Fit success, physical validity, solver validation, organizational approval은 각각 다른 상태다.

### 6.5 Hyperelastic 공개 UI에서 얻을 수 있는 배치 근거

**OBSERVATION**

Material Modeler Hyperelastic Web 도움말은 왼쪽을 test curve list, 중앙을 plot, 오른쪽을 model settings/results로 설명한다. curve의 Enable과 checkbox는 fitting 포함 여부를 제어하고, model을 고르면 parameter가 나타나며 bounds·refit·reset이 가능하다. Save State와 Publish도 구분된다.

공식 근거:

- [Hyperelastic Web: Edit Physics Workflow](https://help.altair.com/material_modeler/hyperelastic/topics/amm_hyperelastic_web/edit_physics_workflow_t.htm)

**DECISION**

- Fit 왼쪽은 임의 설정 필터가 아니라 specimen/test curve list다.
- 항목에는 test mode, condition, included/excluded, visible/hidden, quality warning이 있다.
- curve가 많을 때만 test type·temperature·direction·strain rate filter를 목록 위에 보조적으로 둔다.
- 중앙은 response/residual/derivative/extrapolation을 판단하는 dominant plot과 폭이 필요한 candidate table이다.
- 오른쪽은 선택한 candidate의 parameter/bounds/range/blend/compatibility/reason/warning acknowledgement다.
- 이 배치는 3열 모양을 복제하기 위한 것이 아니라 세 가지 동시 판단—어떤 증거를 쓸지, 결과가 어떻게 거동하는지, 어떤 가정을 조정하는지—을 분리하기 위해 채택한다.

## 7. 현재 제품에 채택할 공통 원리

1. **검색·선정·calibration·governance·delivery를 다른 업무로 분리한다.**
2. **화면 배치는 데이터 관계와 사용자 판단의 동시성으로 정한다.**
3. **값 가까이에 조건·단위·출처·revision을 둔다.**
4. **자동 계산과 사람의 선택을 분리한다.**
5. **업stream 변경은 downstream stale 상태를 명시적으로 만든다.**
6. **released object는 직접 덮어쓰지 않고 새 working revision으로 변경한다.**
7. **solver artifact는 source model과 다른 mapping 결과일 수 있음을 preflight에서 보여준다.**
8. **내부 key·hash·raw JSON은 evidence이며 정상 업무의 label이 아니다.**
9. **미지원 상태를 그럴듯한 기본값이나 fallback으로 숨기지 않는다.**
10. **참고 서비스의 모든 기능을 넣지 않고 현재 대표 시나리오에 필요한 것만 구현한다.**

## 8. 채택하지 않을 것

- Granta의 database schema와 navigation을 그대로 복제
- Material Modeler의 특정 화면 외형을 그대로 복제
- 고정 2열·3열 자체를 acceptance criterion으로 사용
- 모든 family에 같은 property filter·column·fit field 표시
- 최저 error candidate의 자동 승인
- supplier value와 curve-derived value의 조용한 대체
- Fit 완료를 Validated 또는 Reviewed로 표시
- source model과 solver card를 같은 객체처럼 표시
- static demo 한 건으로 전체 catalog filter와 workflow를 증명
- 내부 method ID와 API vocabulary를 제품 정보 계층으로 사용

