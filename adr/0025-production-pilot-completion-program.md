# ADR-0025: complete the product as user-visible production-pilot verticals

## 먼저 읽기

- **무엇을 정했나요?** 기존 migration과 불변 data 기반을 보존하면서, test context부터 Processing,
  Calibration, neutral IR, solver card, 개별·bulk download까지 사용자 흐름별로 완성합니다.
- **왜 중요한가요?** 또 다른 기반 재작성보다 사용자가 실제로 끝낼 수 있는 작업을 먼저 제공하고,
  reference 기능의 domain 승인 상태를 숨기지 않기 위해서입니다.
- **언제 읽나요?** 새 foundation과 end-to-end 기능 중 우선순위를 정하거나, material family·importer·
  calibration·export·connector의 제품 완료 범위를 판단할 때 읽습니다.
- **용어를 쉽게 말하면:** `production-pilot vertical`은 실제 제품 흐름으로 연결됐지만 production
  qualification은 별도로 남은 단계입니다. `domain sign-off`는 재료·solver 전문가가 사용 범위를
  승인하는 일이며, `reference/unapproved`는 실행 가능해도 그 승인을 받지 않았다는 뜻입니다.
- **상태 표기는?** `Accepted`는 이 사용자 흐름 중심 완성 전략을 채택했다는 뜻입니다. 세 reference
  family나 Abaqus·OpenRadioss가 production 검증을 마쳤다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-16
- Related: ADR-0006, ADR-0019, ADR-0020, ADR-0024; T-39 through T-47

## Context

The repository already contains a substantial immutable revision, provenance, authorization,
artifact, job, plugin and review/release foundation. It also contains bounded PostgreSQL-backed
reference flows for steel elastoplasticity, polymer linear viscoelasticity and elastomer
Ogden--Prony cards. The remaining gap is not another foundation rewrite: users need deeper test
context, selected real tabular formats, repeat processing, iterative calibration, bulk delivery
and task-oriented documentation.

Public Granta MI and Simcenter Material Data Center material-management capabilities inform the
linked-record and governed-delivery requirements. Simcenter Material Modeler and MCalibration
inform missing processing/calibration interactions. Their proprietary schema, UI and algorithms
are not inputs to this implementation.

## Decision

1. Preserve migrations 001 through 048, all released/raw objects and existing verticals.
2. Deliver T-39 through T-47 as small end-to-end increments. Each increment includes typed
   PostgreSQL persistence, protected API, connected React UI, tests and user documentation.
3. Prioritize this user path: Material/Test context -> immutable Dataset -> explicit Processing ->
   manual or automatic Calibration -> neutral IR -> mapping report -> card -> individual/bulk
   download.
4. Keep three declared reference families: metal elastoplasticity, polymer linear viscoelasticity
   and elastomer Ogden--Prony. They remain `reference/unapproved` without domain sign-off.
5. Support Abaqus 2025 and OpenRadioss 2025 as explicit reference targets. Actual solver execution
   and qualification remain excluded by product-owner decision.
6. Add no generic EAV, proprietary vendor parser, model-specific core shortcut or silent mapping.
7. Maintain one execution-status document so another development session can resume at the first
   unfinished acceptance gate without rediscovering priorities.

## Consequences

- The product becomes usable through vertical workflows before enterprise connector breadth.
- Domain approval may lag implementation. The UI and API must expose that state rather than block
  reference development or imply production qualification.
- New global workbench routes may be added, but existing Material deep links remain compatible.
- Proprietary laboratory, PLM and licensed-solver integrations require separately authorized
  credentials, samples and acceptance evidence.
