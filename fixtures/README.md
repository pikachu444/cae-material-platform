# Fixture 안내

이 폴더에는 테스트와 형식 검증을 같은 입력으로 다시 실행하기 위한 고정 자료가 있습니다. 실제
생산 데이터나 측정 데이터의 보관소는 아닙니다.

- **fixture**는 특정 동작을 매번 같은 조건에서 확인할 수 있도록 저장한 예제 입력과 기대값입니다.
- **manifest**는 fixture의 출처, 관리 주체, 사용 조건, 기밀 등급, 파일 지문을 기록한 설명서입니다.
  파일 지문(`digest`)은 내용이 바뀌었는지 확인하는 값입니다.
- **schema**는 데이터에 어떤 필드가 있고 각 필드가 어떤 형식이어야 하는지 적은 규칙입니다.

## 어디서 시작하나

먼저 하려는 작업에 맞는 상세 안내를 하나 고른 뒤, 그 문서가 가리키는 파일과 소비 테스트를
확인합니다. 세 디렉터리는 서로 다른 책임을 가집니다.

| 작업 | 열어 볼 문서 | 이 디렉터리의 역할 |
| --- | --- | --- |
| 계산이나 처리 결과를 재현하는 테스트를 고칠 때 | [합성 fixture 상세 안내](synthetic/README.md) | 실제 측정값이 아닌, 의도적으로 만든 반복 가능한 입력과 기대값을 둡니다. |
| fixture의 출처·소유자·라이선스·분류·파일 지문을 확인할 때 | [manifest 상세 안내](manifests/README.md) | fixture 내용과 분리된 추적 정보를 기록합니다. |
| 여러 schema를 한 묶음으로 가져오는 외부 형식을 읽거나 정규화할 때 | [source-v2 상세 안내](schema-definition-bundle/source-v2/README.md) | 공개된 원본 형식이 제품의 내부 형식으로 어떻게 들어오는지 검증하는 예시입니다. 현재 내부 bundle contract에 그대로 넣어 성공해야 하는 정상 예제는 아닙니다. |

권장 순서는 `이 안내 → 해당 상세 README → 정확한 fixture와 manifest → 실제 소비 코드와 테스트`입니다.
하위 README가 가진 파일 목록이나 긴 회귀 조건은 이 문서에 복사하지 않습니다.

## 실제로 어디서 쓰나

- [metal hardening fixture 검사](../tests/unit/test_metal_hardening_reference_fixture.py)는 합성 JSON과
  manifest를 함께 읽어 파일 지문, 출처와 기준값을 확인합니다.
- [tensile 처리 결과 검사](../tests/unit/test_common_processing_output.py)와
  [처리 방법 검사](../tests/unit/test_metal_processing_methods.py)는 합성 tensile fixture를 직접
  읽어 반복 가능한 처리 결과를 확인합니다.
- [source-v2 adapter 검사](../tests/unit/test_schema_definition_source_adapter.py)는 source-v2 전체를
  읽어 [제품의 schema source 정규화 코드](../backend/src/cmp/modules/catalog/domain/schema_sources.py)에
  전달합니다. 제품 코드는 저장소 fixture 경로를 직접 읽는 것이 아니라, 같은 형식으로 들어온 입력을
  처리합니다.

대표 검사는 다음과 같습니다.

```powershell
uv run pytest tests/unit/test_metal_hardening_reference_fixture.py
uv run pytest tests/unit/test_common_processing_output.py tests/unit/test_metal_processing_methods.py
uv run pytest tests/unit/test_schema_definition_source_adapter.py
uv run pytest tests/contracts/test_contracts.py::test_metal_fit_reference_assets_are_explicitly_lf_only
```

문서의 분류와 링크, 저장소 지도가 맞는지는 `uv run cmp-check-user-guide --root .`로 확인합니다.

## 사용 경계와 중단 기준

계산 입력과 기대값에는 합성한 비기밀·비운영 자료만 추가합니다. source-v2처럼 공개 원본 형식을
보존하는 fixture는 정확한 활성 이슈와 권위가 승인한 형식 전용 자료이며, 실제 Record·시험 데이터나
측정값을 포함하지 않습니다. 고객·공급자 자료와 기밀 자료도 fixture로 넣지 않습니다. fixture의 값과
허용 오차는 생산 표준, 재료 모델이나 검증 기준을 결정하지 않습니다. 파일 지문으로 고정된 fixture를
바꿔야 한다면 기존 파일을 덮어쓰지 말고, 승인된 새 버전 범위를 먼저 확인합니다.

활성 이슈·요구사항·contract·상세 README·manifest·소비 코드나 테스트가 서로 다른 내용을 말하면
작업을 멈춥니다. 특히 manifest의 경로·분류·파일 지문이 fixture와 다르거나 source-v2를 현재
canonical contract의 정상 예제로 취급해야 하는 상황이면 임의로 파일을 고치지 않습니다. 충돌한
경로와 ID, 확인한 동작을 기록하고 제품 소유자 지시나 활성 이슈에서 해결합니다.
