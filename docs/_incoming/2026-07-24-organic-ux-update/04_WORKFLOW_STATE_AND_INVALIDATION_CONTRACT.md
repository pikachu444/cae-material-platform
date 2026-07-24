# 업무 상태·명령·무효화 계약

## 1. 목적

현재 UX의 가장 큰 위험은 화면 배치보다 상태 이름이 실제 domain event를 과장하거나 여러 행위를 합치는 것이다. 이 문서는 버튼·badge·route가 어떤 object와 event를 뜻하는지 고정한다.

## 2. 서로 다른 object를 합치지 않는다

```text
Material revision
  └─ Test Data revision
      └─ Processed Dataset revision
          └─ Fit Run
              └─ Candidate Snapshot
                  └─ Engineer Decision
                      └─ Validation Run
                          └─ Review Package
                              └─ Released Model
                                  └─ Material Model IR
                                      └─ Neutral Model
                                          └─ Solver Artifact
```

### object별 정체성

| object | 변경 가능한가 | 핵심 identity | 다음 object를 만들기 위한 조건 |
|---|---|---|---|
| Raw source | 불변 | file/test run + checksum + origin | parser가 읽을 수 있음 |
| Test Data revision | versioned | raw source + mapping + units + conditions | mapping 저장 |
| Processed Dataset revision | versioned | Test Data rev + ordered recipe | process 저장 |
| Fit Run | 불변 실행 기록 | processed rev + model schema + bounds + range | 계산 완료 |
| Candidate Snapshot | 불변 | fit result + law/parameters/range/extrapolation | 사용자가 저장 |
| Engineer Decision | versioned/auditable | selected candidate or blend + reason + warning ack | explicit select |
| Validation Run | 불변 실행 기록 | frozen candidate + plan + reference/solver | 실행 완료 |
| Review Package | 불변 제출물 | source chain + decision + validation + diff | 제출 |
| Released Model | 불변 release | approved review package | release 권한·정책 |
| Material Model IR | 불변 변환 결과 | exact released/allowed source model | IR promotion |
| Neutral Model | 불변 변환 결과 | IR + normalized mapping | neutral promotion |
| Solver Artifact | 불변 전달 결과 | neutral + target/version/unit + mapping preflight | deliver |

현재 API가 이 모든 object를 별도 resource로 갖지 않더라도 UI state와 label은 의미를 합치지 않는다. backend gap이 있으면 임의로 reviewed/released라고 부르지 말고 backlog의 contract gap으로 기록한다.

## 3. 명령어 사전

| 명령 | 의미 | 생성되는 상태 | 생성하지 않는 상태 |
|---|---|---|---|
| Preview | 현재 입력으로 일시 계산 | ephemeral preview | saved, selected, reviewed, released |
| Save dataset | raw+mapping+unit+condition을 revision으로 저장 | Test Data revision | reviewed |
| Save processed curves | source+recipe+result를 revision으로 저장 | Processed Dataset revision | validated, reviewed |
| Run fit | candidate 계산 | Fit Run | selected |
| Select candidate | 사람이 candidate 또는 blend를 선택하고 이유를 기록 | Engineer Decision draft | saved snapshot이 자동인지는 구현 계약으로 명시; reviewed 아님 |
| Save candidate | 선택된 candidate snapshot과 decision을 보존 | saved candidate | reviewed |
| Run validation | frozen model에 validation plan 실행 | Validation Run | approval |
| Submit for review | immutable review package를 reviewer queue에 제출 | In review | approved/released |
| Request changes | reviewer가 변경을 요구 | Changes requested | source object overwrite |
| Approve | review package 승인 | Approved | Released |
| Release | 조직에서 사용 가능한 immutable version 발행 | Released Model | solver artifact |
| Generate preview | target mapping으로 임시 native card 생성 | preview | Delivered |
| Deliver card | lineage를 가진 persistent artifact 생성 | Solver Artifact/Delivered | source model 수정 |

### 금지 label

- 실제 review event 없이 `Commit reviewed fit`
- 실제 approval 없이 `Approved`
- validation run 없이 `Validated`
- 조직 release 없이 `Released`
- preview만 생성하고 `Delivered`
- file upload만 끝나고 `Reviewed data`
- 계산상 수렴만 했는데 `Ready`라고 단독 표시

대안:

- `Fit completed`
- `Candidate saved`
- `Validation not run`
- `Ready for review`
- `Mapping warning`
- `Preview ready`

## 4. Modeling stage state machine

### 4.1 Session

| state | 설명 | 허용 action |
|---|---|---|
| Setup incomplete | material/workflow/objective/source가 부족 | Complete setup |
| Working | current stage에 unsaved input 있음 | Preview, Save, Discard |
| Saved | current stage exact revision 저장 | 다음 stage 이동 |
| Stale downstream | upstream revision이 바뀌어 후속 object가 current가 아님 | Recompute, inspect old lineage |
| Blocked | prerequisite/permission/domain support 부족 | Resolve shown prerequisite |
| Failed | 현재 계산·저장이 실패 | Retry with context preserved |

### 4.2 Stage readiness

| stage | entry prerequisite | completion evidence |
|---|---|---|
| Data | session setup | saved Test Data revision |
| Process | saved Test Data | saved Processed Dataset revision |
| Fit | saved Processed Dataset | saved explicit candidate decision |
| Validate | saved candidate | validation run result or explicit policy `Not supported/waived` |
| Review | candidate + required validation policy | approved review package |
| Release | approval + permission/policy | Released Model |
| Export | exact source model + target mapping prerequisites | Delivered Solver Artifact |

stage를 건너뛸 수 있는 policy가 있다면 explicit reason과 actor를 기록한다. UI가 임의로 생략하지 않는다.

## 5. Recommendation과 engineer decision

### 5.1 Recommendation

- 계산 결과의 정렬·추천이다.
- metric과 tie-break, range, warning을 표시한다.
- default selection을 만들지 않는다.
- Fit가 다시 실행되면 바뀔 수 있다.

### 5.2 Selection

- 사용자가 row action으로 수행한다.
- selection reason이 필요하다.
- warning candidate는 reason과 별도로 acknowledgement가 필요하다.
- selected candidate는 recommendation 변화로 자동 변경되지 않는다.
- 선택 변경은 validation·review·release·export를 stale로 만든다.

### 5.3 Metal blend

```text
mode = single
identity = law + parameters + fit range

mode = blend
identity = primary law + secondary law + ratio
           + both parameter sets + fit range + extrapolation policy
```

blend의 graph, table, saved output, IR, Neutral, Export ribbon, artifact lineage가 모두 같은 identity를 사용한다. `Swift + Voce 50/50`을 `Swift`라고 축약하지 않는다.

### 5.4 Polymer automatic term selection

- server가 실제 선택한 term count와 metrics를 canonical result identity로 사용한다.
- recipe의 requested mode와 default term count는 input intent이지 result identity가 아니다.
- `automatic_bic`이면 UI는 requested range와 실제 selected term count를 함께 표시한다.
- candidate table, saved output, IR, export가 같은 server result를 참조해야 한다.

## 6. Downstream 무효화 매트릭스

범례:

- `CLEAR`: current working chain에서 제거
- `STALE`: 역사적 object는 보존하되 current로 사용할 수 없음
- `REGEN`: source는 유지하고 해당 artifact만 재생성
- `KEEP`: 영향 없음

| 변경 event | Test Data | Processed | Fit candidates | Decision | Validation | Review/Release | IR/Neutral | Export preview/artifact |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| material revision 변경 | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| material state/condition 변경 | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| physical workflow/family 변경 | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| source Test Data 변경 | KEEP new | CLEAR | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| axis/unit mapping 변경 | new revision | CLEAR | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| process operation/order/scope 변경 | KEEP | new revision | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| modulus/yield/necking 변경 | KEEP | new revision | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| fit evidence include set 변경 | KEEP | KEEP | CLEAR | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| model/bounds/fit range 변경 | KEEP | KEEP | CLEAR/re-run | CLEAR | CLEAR | STALE | CLEAR | CLEAR |
| selected candidate/blend 변경 | KEEP | KEEP | KEEP | new decision | CLEAR | STALE | CLEAR | CLEAR |
| validation plan/reference 변경 | KEEP | KEEP | KEEP | KEEP | new run | STALE | KEEP until approval policy | CLEAR |
| review 후 source 변경 | KEEP history | KEEP history | KEEP history | new working version | CLEAR | old release KEEP + new review needed | CLEAR | CLEAR |
| target solver/version/unit 변경 | KEEP | KEEP | KEEP | KEEP | solver validation may STALE | KEEP | REGEN if target-specific | REGEN |
| mapping profile 변경 | KEEP | KEEP | KEEP | KEEP | target validation STALE | KEEP | REGEN target representation | REGEN |

### 6.1 UI 표시

- stale object는 삭제된 것처럼 숨기지 않는다. history에서 원인과 former source revision을 볼 수 있다.
- current action에서는 stale object를 fallback으로 쓰지 않는다.
- user에게 `Upstream mapping changed. Re-run Process and Fit.`처럼 원인과 다음 행동을 말한다.
- 여러 downstream object를 한 번에 지우는 변경은 confirmation에 영향 목록을 표시한다.

## 7. Session context 저장 계약

현재 `saveModelingSession()`의 nullish merge 방식처럼 기존 field를 명시적으로 clear할 수 없는 API는 무효화 계약을 구현하기 어렵다.

필요한 방식 중 하나:

1. reducer/event model
   - `CHANGE_MATERIAL`
   - `PIN_TEST_DATA`
   - `SAVE_PROCESSED_REVISION`
   - `SELECT_CANDIDATE`
   - `INVALIDATE_DOWNSTREAM`
2. patch model
   - field별 `set`/`clear`를 구분하는 explicit operation
3. versioned session aggregate
   - event가 새 session revision을 만들고 derived current pointers를 계산

최소 수용 기준:

- material/state/Test Data/family 변경 시 previous `recipe`, `processingOutput`, `IR`, `Neutral`, `preflight`, `artifact` current pointer를 명시적으로 제거한다.
- 역사적 object 자체는 삭제하지 않는다.
- 변경 직후 Export route를 열어도 다른 material 또는 예전 session output이 보이지 않는다.
- resume하면 last exact stage와 saved view state가 복원된다.

## 8. Materials query 상태 계약

### 8.1 하나의 query source of truth

```text
scope
+ text query
+ category/subset
+ facets
+ sort
+ layout/columns
+ page
= one server query state
```

- total, facet count, results page, sort는 같은 query semantics를 사용한다.
- client는 display-only interaction을 할 수 있지만 catalog filtering을 첫 50개에만 적용하지 않는다.
- server가 아직 facet을 지원하지 않으면 해당 facet을 제품 기능처럼 노출하지 않고 contract gap으로 기록한다.

### 8.2 Selection과 compare

- selected row는 inspection context다.
- compare tray는 persistent shortlist다.
- filter 변경 후 selected row가 사라지면 selection을 clear한다.
- compare item이 current scope 밖이면 유지하되 `Outside current results`로 표시한다.
- material revision이 superseded면 tray가 successor를 자동 대체하지 않고 선택권을 준다.

### 8.3 condition-aware property

property projection은 최소 다음 key를 가진다.

```text
quantity
value/range
display unit
normalized unit
definition
form/condition
temperature
direction
rate/frequency when relevant
source type
source revision
availability state
```

이 semantics가 없는 경우 results의 공통 property 열이나 facet에 쓰지 않는다.

## 9. Review와 release 계약

### 9.1 작성자 경로

```text
Save candidate
→ inspect review package
→ Submit for review
→ In review
→ Changes requested 또는 Approved
```

Changes requested이면 기존 submitted package를 수정하지 않는다. new working decision/package를 만든다.

### 9.2 reviewer 경로

- source lineage와 diff를 본다.
- validation coverage와 warning을 본다.
- comment와 함께 Approve 또는 Request changes를 실행한다.
- reviewer와 author role을 임의로 동일시하지 않는다.

### 9.3 Release

- approved와 released는 다르다.
- organization policy와 권한이 아직 결정되지 않았으면 `Release policy not configured`로 표시한다.
- released model은 immutable하다.
- 새 변경은 successor working revision을 만든다.

## 10. Export와 fallback 금지 계약

### 10.1 source selection

기본 source는 current session의 exact candidate/released model이다. 다음 fallback은 금지한다.

- 전역 Processing Output 중 첫 항목
- material/state가 맞는지 검증하지 않은 최근 output
- method ID만 일치하는 output
- current session 결과가 없을 때 existing model을 조용히 선택

다른 released model을 재사용하는 별도 use case가 필요하면 `Choose released model`이라는 명시적 Materials 경로로 제공한다.

### 10.2 preflight

preflight는 각 차이를 사용자에게 말해야 한다.

| mapping state | 의미 | 행동 |
|---|---|---|
| Exact | source 의미가 target에 그대로 표현 | 진행 가능 |
| Transformed | 단위·표현 변환이 있으나 의미 보존 | 변환식·unit 표시 |
| Approximated | source behavior 일부를 target law로 근사 | 영향·validation·acknowledgement |
| Ignored | target에 전달되지 않는 source field | 영향·reason 표시; 정책에 따라 차단 |
| Unsupported | 유효 artifact를 만들 수 없음 | 차단하고 가능한 target/대안 제시 |

### 10.3 preview와 delivery

- preview는 target setting이 바뀌면 stale.
- delivery는 checksum, source version, mapping report, actor/time을 가진다.
- download만 제공해도 delivery event와 lineage를 기록한다.
- Materials CAE Cards와 Activity가 같은 delivered artifact를 참조한다.

## 11. 오류와 복구

모든 오류는 다음 네 가지를 말한다.

1. 무엇이 실패했는가
2. 가능한 이유 또는 확인된 원인
3. 현재 데이터와 downstream에 미친 영향
4. 사용자가 다음에 할 수 있는 행동

보존할 문맥:

- 입력 값
- query/filter/selection
- raw mapping
- chosen curve/specimen
- plot zoom/visibility/mode
- selected candidate
- warning acknowledgement 전의 reason
- target solver setting

stack trace, request ID, raw payload는 `Details`에서만 표시한다.

## 12. long-running job

validation, fit, export generation 같은 job은 다음을 가진다.

- persistent status: Queued, Running, Completed, Failed, Canceled
- stage/progress와 elapsed time
- exact input revision
- cancel 가능 여부
- same revision retry
- Activity item
- 완료 후 정확한 결과 route

browser refresh나 route 이동으로 job state가 사라지지 않는다.

## 13. 임의로 정하지 않을 domain policy

다음은 문서나 registry에 근거가 없으면 `TBD`, `Not configured`, `Unsupported`로 남긴다.

- production tensile standard
- family별 required property
- fit/stability/validation 합격 threshold
- default optimizer와 parameter bound
- production solver/version/card matrix
- organization review role과 separation-of-duty
- retention/residency policy
- 공개 자료만으로 확인하지 못한 SMM 2026 import/export 범위

그럴듯한 default를 넣어 “작동하는 화면”을 만드는 것은 완료가 아니다.

