# 저장소 규칙 정리 — 적용 전 변경안

2026-09-07. **이 폴더는 검토 자료다. 아래 규칙이 현재 저장소에 적용된 것은 아니다.**

추천은 규칙을 없애는 것이 아니라 **짧은 작업 지침 + 한 곳에 있는 제품 기준 + 해당 변경의 검사**로 정리하는 것이다.
소재만 리비전 관리하는 결정은 기존 ADR-0036에 이미 반영됐다. 실제 DB/API 이관과 남은 문서 충돌 해소는 별개다.

## 바로 검토할 변경 문구

| 초안 | 승인 후 적용 위치 | 달라지는 점 |
| --- | --- | --- |
| [루트 지침](root-instructions.md) | 루트 AGENTS.md | 작업 시작·의미 보존·검증·게시만 짧게 안내한다. 특정 시안·행 높이·모델 배정은 제거한다. |
| [프론트엔드 지침](frontend-instructions.md) | apps/web/AGENTS.md 및 새 기반의 해당 지침 | 기존 코드 이동 규칙과 새 화면 설계를 구분한다. 범용 helper 추출을 모든 작업의 선행 조건으로 강요하지 않는다. |
| [제품·설계·검증 문서](decisions-and-checks.md) | ADR index, architecture, UI principles, T/Q, acceptance, manifest | 현행 계약·과거 결정·검토 자료의 역할과 실제 대체 문구를 지정한다. |
| [skill·오케스트레이션](skills-and-orchestration.md) | 프로젝트 skill, 개인 orchestration, 프로필 | Main 직접 수행이 기본이다. 반복 업무에 도움이 되는 skill만 남기고 필요할 때 독립 검수한다. 개인 파일은 별도 적용 범위다. |

## 조사에서 확인한 충돌

- ADR-0037에는 과거 A/B 비교를 대체한다는 기록이 있지만 `adr/README.md` 마지막 단락은 여전히 A를 권장안으로 설명한다.
- `apps/web/AGENTS.md`의 Brownfield refactoring은 “hotspot or the new foundation”에 같은 추출 순서를 적용한다. 기존 복잡한 코드를 옮길 때의 안전장치가 새 설계까지 묶는다.
- `docs/testing/product-work-acceptance.md`의 재사용 양식에 A/B 화면 설명과 D0 문서 작업의 N/A 조건이 섞여 있다. 후속 구현에서 그 조건을 그대로 읽으면 안 된다.
- `docs/product/visual-acceptance-matrix.md`의 Q-03은 24–26 px, Q-10은 특정 범례 위치, Q-12는 선택지 하나여도 Select를 고정한다. 가독성·충돌 방지·출력 의미라는 목적을 유지하면서 구현 방법을 다시 선택할 수 있어야 한다.
- `docs/planning/risks-open-questions-decisions.md` §6의 `ADR-004`는 revision이고 실제 `adr/0004-isolated-plugins.md`는 plugin이다. 서로 다른 번호 체계가 동일한 결정처럼 보인다.
- 문서 manifest는 `docs/analysis/**`, `docs/planning/**`, 모든 ADR을 넓게 authoritative로 분류한다. 분류만으로 과거 제안과 미선택 화면이 현재 의무가 되지 않도록 실제 상태를 구분해야 한다.
- 기본 `npm run check`의 frontend guard는 `apps/web/src`를 검사한다. 새 기반 검사와 같다고 말할 수 없다. 현재 새 기반 명령은 `npm run check:web-next`다.
- 개인 orchestration skill은 Sol 중심 역할 배정을 고정한다. `cae-full.config.toml`의 medium과 skill의 xhigh도 다르다. 사용자 선택 Main으로 직접 작업한다는 이번 방식과 정합성이 낮다.

복잡한 규칙이 맥락 상실이나 수동적인 대응의 원인 전부라는 결론은 아니다. Main이 전체 목표를 확인하지 않은 채
지적받은 한 부분만 수정한 것도 작업 방식의 문제다. 주기적으로 혼잣말을 하거나 자동 태스크를 늘리는 것으로 해결하지 않는다.
현재 상태 문서에는 **전체 목표·최근 변경점·완료 증거·다음 행동**을 남기고, 재개 시 실제 파일·검증 결과와 맞춘다.

## 적용 순서와 완료 조건

1. 이번 문구의 방향을 승인받으면 루트/프론트 지침과 ADR index부터 함께 바꾼다. 시각 후보를 임의로 승인 상태로 바꾸지 않는다.
2. 동일한 단위에서 architecture·UI principles·acceptance·Q·skill의 반복 문구를 제거하고 기준 링크로 연결한다. 과거 결정을 삭제하지 않는다.
3. manifest와 검사 scope를 바꿀 때 분류 fixture와 실패/통과 사례를 먼저 정한다. 검사 코드를 크게 재작성하는 별도 framework는 만들지 않는다.
4. 개인 orchestration·프로필은 내용 확인 후 별도 적용한다. 기존 다른 프로젝트 설정·신뢰 hash·자격증명은 건드리지 않는다.
5. 짧은 실제 작업을 한 번 수행해 지침 중복 읽기, 불필요한 질문, 검사 시간, 놓친 요구를 확인한다. 문서 행 수 감소만 성공으로 평가하지 않는다.

검사 실패는 원인을 고쳐 해결한다. 정리 작업이라는 이유로 golden, 권한, 단위, 데이터 손실 방지 검사를 삭제하거나 통과 기준을 낮추지 않는다.
개편 자체와 사소한 구현 선택을 매번 승인받지는 않는다. 최종 시안·공학 기준·외부 게시·개인 설정처럼 실제 선택이 남은 경계만 구분한다.

## 공식 지침과의 관계

OpenAI는 최신 모델 전환 시 충돌하거나 과도하게 처방적인 지침을 점검하고 자율성·검증 범위를 명확히 하도록 안내한다.
따라서 특정 모델이면 문서가 필요 없다거나, 여러 에이전트를 강제로 써야 한다는 결론은 맞지 않는다.
[모델 안내](https://developers.openai.com/api/docs/guides/latest-model), [작업 지침](https://learn.chatgpt.com/guides/best-practices).

AGENTS는 전역/상위/하위 지침이 합쳐진다. 짧은 루트 안내와 범위별 세부 지침이 적합하다.
기본 크기 제한을 실제 이 세션의 잘림 증거로 간주하지 않았다.
[AGENTS 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

현재 hook의 `^Bash$` matcher는 공식 예시와 양립한다. 도구 표기 차이만으로 고장이라고 판정하지 않는다.
발화 여부와 중복 실행 시간은 안전한 실제 이벤트에서 따로 확인해야 한다.
[Hooks 안내](https://learn.chatgpt.com/ko-KR/docs/hooks).
