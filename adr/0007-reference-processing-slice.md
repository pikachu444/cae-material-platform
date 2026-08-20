# ADR-007: Reference tensile processing 수직 기능의 불변 경계

## 먼저 읽기

- **무엇을 정했나요?** 하나의 정확한 normalized tensile Dataset revision을 선택하고, 관측된 strain
  범위만 잘라 새 processed Dataset을 만듭니다. 보간·평활화·단위 변환은 하지 않습니다.
- **왜 중요한가요?** 처리 결과를 원본처럼 덮어쓰거나 숨은 변환을 넣지 않고, 어떤 입력과 Recipe로
  결과가 만들어졌는지 다시 확인할 수 있게 하기 위해서입니다.
- **언제 읽나요?** 새 Processing step, Dataset 선택 방식, crop·resample·smoothing 또는 처리 결과의
  저장·복구 동작을 추가할 때 읽습니다.
- **용어를 쉽게 말하면:** `Selection`은 사용할 정확한 Dataset revision을 고른 기록이고, `Recipe`는
  처리 방법과 조건의 불변 버전입니다. `committed Run`은 미리보기가 아니라 저장된 실행이며,
  `moving head`는 나중에 바뀔 수 있는 최신 revision 포인터를 뜻합니다.
- **상태 표기는?** `Accepted`는 이 observed-point crop 경계를 채택했다는 뜻입니다. 통계, calibration,
  일반 processing graph나 production 처리 방법까지 구현됐다는 뜻은 아닙니다.

- 상태: Accepted
- 기준일: 2026-07-15

## Context

ADR-006의 첫 제품 흐름인 Material catalog와 reference solver card는 구현되었다. 다음
연속 흐름은 Material에 연결된 시험 Dataset을 명시적으로 선택하고, 그 선택과 전처리
조건을 고정한 뒤 파생 Dataset을 만드는 것이다. 이는 MCalibration형 독립 도구가 아니라
`Test Data → Processing → Statistics → Material Model` 경로의 Processing capability다.

처음부터 일반적인 processing graph, 임의의 JSON step payload, browser preview output,
또는 여러 curve의 평균/보간을 도입하면 raw/normalized source와 release input의 경계가
불명확해진다. 이번 slice에는 user-confirmed reference tensile CSV importer가 만든
정규화 SI Dataset만 존재한다.

## Decision

1. Reference Selection은 stable identity와 immutable revision을 분리하고, revision 하나가
   정확히 하나의 **정규화 reference tensile Dataset revision**을 pin한다. moving head,
   filter 재평가, raw Dataset 및 multi-member selection은 허용하지 않는다.
2. Reference Processing Recipe도 stable identity와 immutable revision을 분리한다. 유일한
   step은 engineering strain 범위의 양 끝을 포함하는 observed-point crop이다. 보간,
   resample, smoothing, unit conversion, engineering-to-true conversion 또는 source point
   변경은 수행하지 않는다.
3. 실행은 preview가 아닌 committed Processing Run뿐이다. Run은 Selection/Recipe/Dataset의
   구체 revision ID를 고정하고, typed processed Parquet Artifact와 **별도 Dataset stable
   identity의 revision 1**을 만든다. raw/normalized Dataset과 원 Artifact는 수정하거나
   덮어쓰지 않는다.
4. PostgreSQL에는 `datasets.dataset_selection*`, `processing.processing_recipe*`,
   `processing.processing_run`과 typed Dataset representation/foreign key/index/trigger를
   명시한다. 조직·project·classification 복합 FK와 forced RLS를 적용하며 generic EAV나
   자유 형식 content JSON을 사용하지 않는다.
5. processed Dataset generation provenance activity는 Processing Run을 domain run으로
   기록하고 pinned normalized Dataset을 usage, Recipe revision을 plan, output Dataset을
   generation/derivation으로 연결한다. Selection/Recipe/processed Dataset revision은 기존
   append-only audit chain에 기록된다.
6. output Dataset이 이미 immutable하게 commit된 뒤 Run의 terminal projection이 실패하면
   Run을 거짓 `failed`로 쓰지 않는다. `executing` 상태를 보존하고 reconciliation을 요구한다.
   durable recovery worker는 이 reference slice의 후속 작업이다.

## Consequences

- 사용자는 Material State의 웹 화면에서 normalized Dataset revision을 선택하고 Recipe와
  committed Run을 만든 뒤 processed curve를 조회할 수 있다.
- Processing output은 이후 Statistics, Calibration, IR promotion의 concrete input이 될 수
  있지만, 이번 구현은 statistics, QC, outlier, calibration, solver execution 또는 release를
  의미하지 않는다.
- source preservation과 typed unit semantics를 우선했으므로 multi-input alignment나 richer
  processing method가 필요하면 새 typed recipe/selection decision과 migration이 필요하다.

## Revisit trigger

- 여러 replicate를 하나의 statistics/calibration input으로 선택해야 할 때
- resample, true stress-strain transform, filtering 또는 domain-approved crop semantics가
  필요할 때
- durable Job/worker 기반 execution과 terminal-state reconciliation을 연결할 때
