# ADR-0030: material modeling workbench and simplified product access surface

## 먼저 읽기

- **무엇을 정했나요?** mapping부터 crop·통계·fitting·후보 비교까지 하나의 method-driven Workbench에서
  수행하고, 저장되는 모든 변화는 explicit Recipe step과 output revision으로 남깁니다.
- **왜 중요한가요?** 흩어진 reference 기능을 하나의 공학 흐름으로 연결하고, 화면의 숨은 변환이나
  내부 권한 용어가 일반 사용자의 model 선택을 대신하지 않게 하기 위해서입니다.
- **언제 읽나요?** Modeling Workbench 단계·action, 새 processing method, selected result→IR→solver card
  흐름, 제품 역할·feature grant 또는 GUI 증거를 바꿀 때 읽습니다.
- **용어를 쉽게 말하면:** `method-driven`은 사용자가 고른 계산 방법과 설정이 작업 단계를 결정한다는
  뜻입니다. `Recipe step`은 저장된 한 번의 명시적 변환이고, `feature grant`는 제품 역할이 어떤 기능을
  사용할 수 있는지 나타냅니다. 세부 RLS 권한은 내부 통제로 남습니다.
- **상태 표기는?** `Accepted`는 공통 Workbench와 단순한 제품 접근 방식을 채택했다는 뜻입니다.
  licensed solver 실행이나 모든 reference track의 production 승인이 완료됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0018, ADR-0020 through ADR-0023, ADR-0025; T-53 through T-60

## Context

Reference steel, polymer and elastomer flows exist, but each exposes a bounded workflow rather than
one configurable Material Modeling Workbench. Internal authorization concepts also dominate parts
of the product surface even though ordinary users need a simpler mental model.

## Decision

1. Build one method-driven Workbench for mapping, crop, scale/shift, resampling, smoothing,
   alignment, statistics, fitting, extrapolation and candidate comparison. Every committed change
   is an explicit Recipe step and output revision.
2. Deepen three reference tracks in parallel: metal elastoplasticity, polymer linear
   viscoelasticity and elastomer hyperelastic/hyper-viscoelasticity. Public equations and official
   solver documentation are the only numeric and mapping sources.
3. Promote selected results to solver-neutral IR before generating an Abaqus or OpenRadioss card.
   Preserve the six mapping states and prohibit silent defaults or approximations.
4. Expose two product roles, `Administrator` and `User`, with feature grants for schema management,
   catalog editing, processing/calibration, model approval and card export. Existing fine-grained
   permissions and RLS remain implementation controls and compatibility inputs.
5. Every GUI-changing increment updates the task-oriented user/admin guide and deterministic
   screenshot evidence. Actual licensed solver execution remains out of scope.

## Consequences

- The platform foregrounds material discovery and scientific work instead of infrastructure
  vocabulary.
- Existing bounded APIs and models are extended behind common contracts rather than rebuilt.
- `reference`, `validated` and `production-approved` remain distinct user-visible states.
