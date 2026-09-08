# 작업 결과 검증

이 문서는 짧은 검증 양식이다. 사용자 지시나 승인된 범위에 새로운 요구·승인 단계를 더하지 않는다.
제품 데이터 의미는 [데이터 정책](../product/data-management-policy.md), frontend 검사 범위는 [검토 절차](../repository/frontend-change-review-playbook.md)에서 확인한다.

## 작업 전에 남길 내용

| 항목 | 기록 |
| --- | --- |
| 범위 | 현재 지시·해당 계획/issue, 수정 책임, 기존 완료/부분/누락 상태 |
| 주요 업무 | 시작 데이터·사용자 행동·눈에 보이는 결과 |
| 저장과 복구 | 재조회/재접속 결과, 입력 변경, 실패/미저장 편집 복구 |
| 보존할 의미 | 해당 API·ID/관계·단위·소재 리비전·권한·출력 계약 |
| 확인 방법 | 관련 자동 검사, 실제 업무/화면 증거, 적용하지 않는 검사와 이유 |

한 작업 계획에 이 내용이 있으면 별도 긴 packet을 복제하지 않는다. 단순 문서·문구 변경에 무관한 사용자 흐름이나 DB 시나리오를 꾸며 쓰지 않는다.

## 적용할 검사

- 문서·지침: 로컬 링크·분류·관련 결정 일치, `uv run cmp-check-user-guide --root .`, `uv run cmp-check-doc-impact --root . --mode worktree`, `git diff --check`.
- 코드: 변경한 계약/규칙의 단위·통합 검사와 해당 앱 build. 실제 연결 업무는 브라우저로 저장/재조회까지 확인한다.
- 화면: 시각 매트릭스의 해당 상태·viewport 원본 검토. 측정치나 selector 존재만으로 사용성을 통과시키지 않는다.
- 계산/변환/출력: 기준 데이터와 허용오차, 미지원/잘못된 입력을 검사한다. 잘못된 기존 golden을 무조건 정답으로 삼지 않는다.
- DB·Compose·이관: 관련 변경일 때만 적용한다. Docker 전 compose-preflight, 실제 환경 식별, 원본/데이터 보존과 복구를 확인한다.

D0는 과거 문서 작업이었다. 그때의 N/A를 현재 코드 작업의 면제 사유로 사용하지 않는다.
T/Q는 관련 요구·검사를 찾는 표식이며 매 작업에 전부 실행할 별도 승인 절차가 아니다.

## 실패와 전달

실패 원인을 환경·구현·검사·요구 불일치로 나누고 안전한 관련 검사는 계속한다. 입력이나 진단이 바뀌지 않은 재시도를 반복하지 않는다.
반복 실패는 범위·기준·환경을 다시 확인할 신호다. 실제 제품 판단이나 위험한 변경이 필요하면 구체적인 결정 경계를 제시한다.
기존 미커밋·staged·untracked 작업을 보존한다. 다른 작업 폴더를 수정하지 않는 검사에서는 필요에 따라 status·diff·untracked hash를 비교한다.
완료 보고에는 결과·검증·남은 조건을 적는다. 게시 권한과 원격 read-back은 루트 AGENTS를 따른다.

## 기존 Process geometry 회귀 예시 — legacy 구현에만 적용

아래는 기존 앱의 28px control과 save reason UI를 확인하던 역사적 회귀 예시다. 새 frontend의 높이·편집 사유·화면 배치를 고정하지 않는다. 해당 legacy 소비자 수정에만 적용한다.

당시 User guide의 Process 계약은 visible evaluation method, range, processed-curve label, save reason,
Save 버튼을 같은 `28px` compact control height로 둔다. 기존 browser gate와 동일하게 다음을
검사한다.

- 모든 visible control height는 `28 ± 1px`이다.
- 각 row는 top과 bottom이 모두 `2px` 이내로 정렬된다.
- 각 control box의 네 모서리는 panel box 안에 있다.
- Save action/label은 `white-space: "nowrap"`이고 `scrollHeight <= clientHeight + 1`이다.

검증 코드는 새 공통 framework를 만들지 않고 아래 두 fixture를 한 번의 bounded inline assertion으로
평가한다. Assertion은 prose를 검색하지 않고 geometry 값을 계산한다.

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
