# Main orchestrator acceptance trace

이 문서는 구현 packet, main acceptance, 교정, 최종 독립 검토를 짧게 추적하는 실무 양식이다.
문서 자체가 요구사항이나 승인 권한을 만들지는 않는다. 활성 사용자/제품 소유자 지시와 정확한
issue가 항상 이 요약보다 우선한다.

## 권위와 시작

권위 순서는 다음과 같다.

1. 활성 사용자/제품 소유자 지시와 정확한 GitHub issue
2. issue에 연결된 승인 reference 또는 계약
3. 이 문서와 orchestration 요약

요약은 범위, 합격 조건, 승인 경계를 발명하거나 덮어쓰지 않는다. Main은 시작할 때 의미·운영
위험을 한 문장으로 설명하며 `Administrative direct path`, `Trivial maintenance fast path`,
`Full workflow` 중 하나를 선언하고, 일상적인 권한 질문은 하지 않는다. 명시적인 `full workflow`
또는 `main-direct` 지시는 경로와 수행자를 정한다. 모호성, 계약·정책·요구사항 변경, 새 제품
판단, 위험 확대 또는 fast path gate의 범위 확대가 있으면 질문하거나 Full workflow로 승격한다.

경로 분류만으로 commit, push, PR 생성, ready-for-review, merge 권한이 생기지 않는다. 명시된
사용자/제품 소유자 권한은 이름을 적은 repository·branch·diff·행동에만 적용한다. ready와 merge는
별도 외부 상태 변경이며, pre-publish 실패는 모든 경로에서 게시를 막는다.

이번 #190 실행의 활성 지시는 gate와 독립 검토 뒤 commit, push, Draft PR까지만 명시적으로
허용하며 ready-for-review 전환과 merge는 허용하지 않는다. 이 사례의 허용 범위는 다른 작업에
자동 상속되지 않는다.

## 재사용 trace (모든 범위 내 항목)

| # | 기록할 필드 | 확인할 내용 |
|---:|---|---|
| 1 | 권위/source | 정확한 issue, 승인 reference/계약, 사용자 지시와 우선순위 |
| 2 | fixture/setup와 정확한 operator action | 시작 상태, fixture, 사용자가 고른 값과 수행한 행동 |
| 3 | known-bad baseline 또는 구별되는 precondition | 의미 있는 gate가 실패해야 하는 기준과 그 이유 |
| 4 | visible outcome | 화면·메시지·상태에서 사용자가 판단할 결과 |
| 5 | persistence/reload/read-back outcome | 저장, 재접속, 외부 기록 재조회에서 유지되는 결과 |
| 6 | preserved contract/state | API·UI·데이터·revision·승인 상태와 보존해야 할 기존 상태 |
| 7 | automated/live/visual gate | 해당 항목에 실제 적용한 결정적 검사와 관찰 증거 |
| 8 | recovery/escalation와 N/A/deferred/stop | 복구 행동, 승격 조건, 적용하지 않거나 미룬 이유, 중단 조건 |
| 9 | owned files/systems와 forbidden shortcuts | 편집·외부 변경 대상과 금지한 우회 방법 |

Administrative direct path는 repository 파일을 건드리지 않는 외부 fact만 다룬다. 외부 기록을
정확히 쓰고 다시 읽어 target/value/body/SHA와 상태를 맞춘다. 작업 전후에 다음 fingerprint를
byte 단위로 비교한다.

- `git status --porcelain=v2 -z`
- `git diff --no-ext-diff --binary`
- `git diff --cached --no-ext-diff --binary`
- `git ls-files --others --exclude-standard -z`의 정렬된 untracked 경로 목록과 각 기존 untracked
  regular file의 SHA-256

기존 tracked·staged·untracked 변경은 dirty 상태 그대로 보존하며 clean worktree나
`git diff --exit-code`를 요구하지 않는다. API 오류·read-back 불일치는 성공으로 기록하지 않고,
입증된 일시적·idempotent 오류만 재시도한다.

Trivial maintenance fast path는 이미 승인·병합된 사실을 동기화하는 docs/metadata 수선, typo,
깨진 내부 링크처럼 의미를 바꾸지 않는 로컬 수정에만 쓴다. scoped diff, `git diff --check`,
`uv run cmp-check-user-guide --root .`, `make docs-impact` (Make를 사용할 수 없으면
`uv run cmp-check-doc-impact --root . --mode worktree`; 같은 gate이며 skip이 아니다)와 변경 경로별
결정적 검사를 실행하고,
명시적으로 승인된 commit 뒤 push/PR 전에는 최신 `origin/main`, 예상 diff와 clean worktree를
확인한 뒤 `make pre-publish`를 실행한다. Make를 사용할 수 없으면
`uv run cmp-pre-publish --root . --trigger manual`을 같은 gate로 실행하며 skip하지 않는다. 새로운
정책·계약·요구사항·제품 판단이나 범위 확대가
나오면 Full workflow로 승격한다.

Full workflow는 위 제외에 해당하지 않는 code/UI/calculation/API/schema/data/migration,
security/authorization, test/build policy, product requirement, `AGENTS.md`, skill,
orchestration workflow, visual approval, product-owner judgment 변경을 포함한다. Main packet 동결
→ 새 requirements auditor `approve` → 한 명의 bounded writer → main 독립 acceptance → 새
read-only reviewer `approve` 순서를 지킨다. Main은 packet에 실제 적용 대상으로 고정된 모든
live gate를 독립적으로 수행한다. Docker gate가 적용되면 Compose preflight와 canonical
recreate를 먼저 실행하고, visual 작업이면 모든 필수 viewport를 원본 해상도로 확인한다. 적용되지
않는 gate 유형은 이유와 함께 N/A 또는 deferred로 기록한다.

실패한 checkpoint에서는 frozen evidence가 유효한 동안 안전한 applicable 검사를 모두 수행하고
결과를 기록한다. 계속하는 것이 안전하지 않거나 실패한 prerequisite 때문에 나머지 증거가 유효하지
않을 때만 discovery를 멈추며, 그 경계와 이후 검사가 무효인 이유를 적는다. 관련 원인을 묶어
새롭고 실질적으로 바뀐 correction packet을 만들며, **변경하지 않은 packet을 다시 실행하지 않는다**.
세 번 실패하면 authority·범위·journey·packet·gate·evidence를 재감사·재계획하고, 제품 결정·권한
부족·unsafe action·외부 blocker 또는 범위를 바꾸는 모호성이 없으면 수정된 packet으로 횟수를
초기화해 계속한다.

## Process geometry calibration trace

User guide의 Process 계약은 visible evaluation method, range, processed-curve label, save reason,
Save 버튼을 같은 `28px` compact control height로 둔다. 기존 browser gate와 동일하게 다음을
검사한다.

- 모든 visible control height는 `28 ± 1px`이다.
- 각 row는 top과 bottom이 모두 `2px` 이내로 정렬된다.
- 각 control box의 네 모서리는 panel box 안에 있다.
- Save action/label은 `white-space: "nowrap"`이고 `scrollHeight <= clientHeight + 1`이다.

Main은 새 framework나 파일을 만들지 않고 아래 두 fixture를 한 번의 bounded inline assertion으로
직접 평가한다. Assertion은 prose를 검색하지 않고 geometry 값을 계산한다.

```python
TOLERANCE = 2

def inside(box, panel):
    return (
        box["left"] >= panel["left"] - 1
        and box["right"] <= panel["right"] + 1
        and box["top"] >= panel["top"] - 1
        and box["bottom"] <= panel["bottom"] + 1
    )

def aligned(row):
    boxes = [item["box"] for item in row]
    tops = [box["top"] for box in boxes]
    bottoms = [box["bottom"] for box in boxes]
    return (
        len(boxes) >= 2
        and max(tops) - min(tops) <= TOLERANCE
        and max(bottoms) - min(bottoms) <= TOLERANCE
    )

def height_ok(item):
    return abs(item["box"]["height"] - 28) <= 1

def nowrap_ok(item):
    return (
        item["whiteSpace"] == "nowrap"
        and item["scrollHeight"] <= item["clientHeight"] + 1
    )

def process_gate(fixture):
    rows = [fixture["normal_row"], fixture["save_row"]]
    controls = [item for row in rows for item in row]
    boxes_inside = all(inside(item["box"], fixture["panel"]) for item in controls)
    heights_ok = all(height_ok(item) for item in controls)
    rows_aligned = all(aligned(row) for row in rows)
    save_wrap_ok = nowrap_ok(fixture["save_button"]) and nowrap_ok(fixture["save_label"])
    return boxes_inside and heights_ok and rows_aligned and save_wrap_ok
```

### Known-bad baseline (must fail)

```python
known_bad = {
    "panel": {"left": 0, "top": 0, "right": 600, "bottom": 80},
    "normal_row": [
        {"name": "Evaluation input", "box": {"left": 10, "top": 6, "right": 210, "bottom": 38, "height": 32}},
        {"name": "range start", "box": {"left": 216, "top": 10, "right": 316, "bottom": 38, "height": 28}},
        {"name": "range end", "box": {"left": 322, "top": 10, "right": 422, "bottom": 38, "height": 28}},
    ],
    "save_row": [
        {"name": "label input", "box": {"left": 10, "top": 50, "right": 220, "bottom": 78, "height": 28}},
        {"name": "reason input", "box": {"left": 226, "top": 50, "right": 446, "bottom": 78, "height": 28}},
        {"name": "Save button", "box": {"left": 452, "top": 10, "right": 590, "bottom": 86.78, "height": 76.78}, "whiteSpace": "normal", "clientHeight": 28, "scrollHeight": 76.78},
    ],
    "save_button": {"whiteSpace": "normal", "clientHeight": 28, "scrollHeight": 76.78},
    "save_label": {"whiteSpace": "normal", "clientHeight": 28, "scrollHeight": 56},
}
assert process_gate(known_bad) is False
```

실패 원인은 Evaluation input `32px`와 Save button `76.78px`의 높이, normal row의 top 정렬,
save row의 top/bottom 정렬, panel bottom `80`을 벗어난 Save box bottom `86.78`, 그리고 Save
action/label wrapping이다.

### Accepted fixture (must pass)

```python
accepted = {
    "panel": {"left": 0, "top": 0, "right": 600, "bottom": 100},
    "normal_row": [
        {"name": "Evaluation input", "box": {"left": 10, "top": 10, "right": 210, "bottom": 38, "height": 28}},
        {"name": "range start", "box": {"left": 216, "top": 10, "right": 316, "bottom": 38, "height": 28}},
        {"name": "range end", "box": {"left": 322, "top": 10, "right": 422, "bottom": 38, "height": 28}},
    ],
    "save_row": [
        {"name": "label input", "box": {"left": 10, "top": 55, "right": 220, "bottom": 83, "height": 28}},
        {"name": "reason input", "box": {"left": 226, "top": 55, "right": 446, "bottom": 83, "height": 28}},
        {"name": "Save button", "box": {"left": 452, "top": 55, "right": 590, "bottom": 83, "height": 28}, "whiteSpace": "nowrap", "clientHeight": 28, "scrollHeight": 28},
    ],
    "save_button": {"whiteSpace": "nowrap", "clientHeight": 28, "scrollHeight": 28},
    "save_label": {"whiteSpace": "nowrap", "clientHeight": 28, "scrollHeight": 28},
}
assert process_gate(accepted) is True
```

Accepted에서는 모든 box가 panel의 네 edge 안에 있고 normal row bottoms `[38, 38, 38]`, save
row bottoms `[83, 83, 83]`와 tops가 정렬되며 모든 control이 `28px`이고 Save action/label이
줄바꿈하지 않는다. Numeric evidence(수치 결과)는 supporting evidence일 뿐 qualitative owner가 화면을 실패로
판정하면 이를 덮어쓰지 않는다. 반대로 이 문서와 수치 준수만으로 구현을 승인하지 않는다.

## N/A·deferred·stop

- **N/A:** 이 문서/정책 변경처럼 product runtime을 건드리지 않는 단위에서는 Compose, DB,
  browser interaction, 새 screenshot, viewport 재오픈, visual score를 실행하지 않고 그 이유를
  적는다.
- **Deferred:** 제품 소유자 승인 전에는 merge SHA, 완료/종료 상태와 다음 backlog unit 활성화를
  완료로 기록하지 않는다.
- **Stop:** 해결되지 않은 제품 결정, missing authority, unsafe action, 외부 blocker, 또는 범위를
  바꾸는 classification 모호성이 있을 때 정확한 경계를 기록하고 멈춘다.

Visual evidence가 필요한 경우에만 [Prepare and implement from authority](../../.agents/skills/desktop-engineering-ui/SKILL.md#prepare-and-implement-from-authority),
[Verify the complete screen](../../.agents/skills/desktop-engineering-ui/SKILL.md#verify-the-complete-screen),
[Independent review and approval](../../.agents/skills/desktop-engineering-ui/SKILL.md#independent-review-and-approval)의
해당 절을 교차 참조한다. 이 문서는 별도 전역 skill이나 공통 verification framework가 아니다.
