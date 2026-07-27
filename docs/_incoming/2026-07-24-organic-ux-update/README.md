# CAE Material Platform 유기적 통합 패키지

기준일: 2026-07-24  
검토 기준선: `main@d16d925d71310d940f93ed5707e7bc229e4c4809`  
포함 상태: PR #124 병합 완료, DUI-01~06 완료, DUI-07~09 미완료, #119 보류

## 이 패키지가 해결하는 문제

이 패키지는 Granta와 Material Modeler의 화면 모양을 모방하는 자료가 아니다. 최신 `main`의 문서·코드·스크린샷을 다시 감사하여 다음을 결정하는 실행 명세다.

- 어떤 기존 문서를 갱신하고 어떤 중복 문서를 삭제할지
- 어떤 코드를 유지하고, 분해하고, 대체하고, 삭제 후보로 둘지
- 각 화면 요소가 어떤 사용자 판단을 위해 존재하는지
- 요소를 어디에 두고 언제 노출하며 무엇을 입력·출력하는지
- 입력 변경이 어떤 후속 결과를 무효화하는지
- 추천·선택·저장·검토·승인·릴리스·내보내기를 어떻게 분리하는지
- 기능 구현 후 어떤 증거로 상용 수준의 사용성을 판정할지

## 중요한 사용 원칙

이 폴더는 Codex 전달을 위해 `main`의
`docs/_incoming/2026-07-24-organic-ux-update/`에 임시로 둔 일회성 통합
자료다. 최종 권위 문서나 영구 reference tree가 아니다. Codex는 다음
순서로 사용해야 한다.

1. 최신 `main`과 applicable `AGENTS.md`를 다시 확인한다.
2. `01_LATEST_MAIN_AUDIT_AND_DOCUMENT_INTEGRATION.md`의 경로별 지시에 따라 내용을 기존 권위 문서에 병합한다.
3. 중복된 예전 실행 프롬프트와 UX 패키지는 inbound link를 고친 뒤 삭제한다.
4. `03_COMPONENT_RATIONALE_SPEC.md`와 `04_WORKFLOW_STATE_AND_INVALIDATION_CONTRACT.md`를 기존 제품·UI 명세의 단일 원본으로 흡수한다.
5. `05_CODE_DISPOSITION_AND_REFACTOR_PLAN.md`의 삭제 게이트를 통과한 코드만 삭제한다.
6. 작업을 작은 검증 가능한 PR로 나누고 `06_DELIVERY_PLAN_AND_ACCEPTANCE.md`의 회귀 시나리오를 실행한다.
7. **#162에서만**, 저장소 통합이 끝나고 이 폴더를 가리키는 참조가 0인지 확인한 뒤
   `docs/_incoming/2026-07-24-organic-ux-update/` 전체를 삭제한다. 그 전에는 삭제하지 않는다.

## 읽기 순서

| 순서 | 파일 | 역할 |
|---:|---|---|
| 1 | `01_LATEST_MAIN_AUDIT_AND_DOCUMENT_INTEGRATION.md` | 최신 상태, 문서 단일 원본, 병합·삭제 지도 |
| 2 | `02_REFERENCE_SERVICE_WORKFLOW_SYNTHESIS.md` | Granta·Material Modeler에서 검증한 실제 업무 원리 |
| 3 | `03_COMPONENT_RATIONALE_SPEC.md` | 화면·컴포넌트·필드별 상세 명세 |
| 4 | `04_WORKFLOW_STATE_AND_INVALIDATION_CONTRACT.md` | 업무 상태, 명령 의미, 무효화·복구 계약 |
| 5 | `05_CODE_DISPOSITION_AND_REFACTOR_PLAN.md` | 파일별 유지·분해·교체·삭제 조건 |
| 6 | `06_DELIVERY_PLAN_AND_ACCEPTANCE.md` | 구현 순서, 테스트, 시각 증거, 완료 정의 |
| 7 | `07_MASTER_CODEX_INTEGRATION_PROMPT.md` | 다음 Codex에 그대로 전달할 실행 프롬프트 |
| 8 | `08_INTEGRATION_MANIFEST.yaml` | AI가 읽을 수 있는 구조화된 통합 규칙 |
| 9 | `09_SOURCE_CATALOG.json` | 공식 출처와 각 출처가 뒷받침하는 사실 |

## 이 패키지가 대체하는 이전 자료

이전에 만든 `materials-platform-reference/` 10개 문서와 `cae-material-platform-reference-pack-2026-07-24.zip`은 조사 초안으로만 취급한다. 그대로 저장소에 넣지 않는다.

특히 이전 자료의 다음 내용은 폐기한다.

- `436ad76` 기준의 현재 화면 진단
- DUI-06이 병합 전이라는 상태
- 별도 `UX_RULES.yaml`을 새 권위 원본으로 추가하라는 지시
- 영구 2열·3열 형태 자체를 제품 목표로 보는 해석
- 완료된 DUI-01~06을 다시 구현하라는 지시
- 외부 패키지 문서를 기존 `docs/` 옆에 병렬로 쌓는 방식

이전 조사 중 유효한 공식 사실과 출처는 이 패키지의 02·09 문서로 정리했으며, 저장소에서는 기존 `docs/00-research/`에 병합한다.

## 제품 판단 원칙

모든 visible component와 engineering field는 다음 질문에 답해야 한다.

1. 사용자는 이 요소로 어떤 결정을 내리는가?
2. 왜 이 단계와 이 위치에 있어야 하는가?
3. 어떤 물리 workflow·재료군·권한·데이터 상태에서만 보이는가?
4. 입력은 어디에서 왔고 단위·조건·출처·revision은 무엇인가?
5. 변경하면 어떤 데이터와 후속 산출물이 stale 되는가?
6. 오류나 미지원 상태에서 입력·선택·그래프 문맥을 어떻게 보존하는가?
7. 이 요소가 없으면 사용자가 실제로 완료하지 못하는 일이 무엇인가?

답하지 못하는 요소는 “전문적으로 보이기 때문에” 유지하지 않는다. 사용자 업무에 연결되도록 재설계하거나 삭제한다.

## 제품 경계

- `Materials`: governed material knowledge를 찾고, 비교하고, 근거를 확인하고, 승인된 모델·카드를 재사용하는 공간
- `Modeling`: 시험 데이터를 import·map·process·fit·validate·review/release하고 solver artifact로 전달하는 공간
- `Activity`: 진행 중 작업, 검토 요청, 실패·경고, 최근 결과를 정확한 상태로 재개하는 공간

Granta MI, Granta Selector, Material Modeler, Material Data Center의 역할을 한 화면에 섞지 않는다. 참고 서비스의 검증된 업무 원리를 채택하되, 현재 플랫폼의 API·revision·provenance·Material Model IR·mapping contract를 보존한다.
