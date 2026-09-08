# ADR-0037: Task-first frontend foundation and single cutover

- Status: Accepted target policy for the redesign program
- Date: 2026-09-05
- Scope: frontend foundation, workbench topology, validation, migration and retirement
- Program: [Frontend redesign program](../docs/planning/frontend-redesign-program.md)

## Context

The current React application has working domain flows but accumulates route, API, state and render
responsibilities in a small set of large files. The read-only baseline records `app.tsx` at 48
lines, an `api.ts` facade at 30 lines, a 2,878-line common processing workbench with 56 states and
31 effects, and 43 CSS files totaling 24,044 raw lines. Existing screenshots and product references
are observations of the current product. They are useful for parity but do not freeze the redesign
topology.

The owner asked for an integrated redesign that covers diagnosis, workflows, assets, navigation,
wireframes, stack comparison, governance, staged migration and retirement. A library-only cleanup
or revision-only rewrite would not meet that scope.

## Decision

Amendment, 2026-09-06: decision 2 below is superseded by the current comparison and cumulative
owner feedback in [program section 4](../docs/planning/frontend-redesign-program.md#4-current-comparison-candidates).
Its historical A/B wording is retained as a decision record, not current implementation authority.
The current comparison has four independent reference concepts and two syntheses, with no
owner-selected winner. Evaluate list-first lookup, dismissible previews, expanded details and
paginated return behavior; neither a table-first A winner nor a permanent list/detail split is
mandated. The other foundation, scientific, migration and retirement decisions remain applicable.

1. Use a task-first engineering workbench. Left navigation exposes the current task and direct Test
   Data and Solver Card paths; results, curves, tables and native previews receive the useful space.
   Modeling keeps a compact process rail and a persistent dominant graph without a permanent third
   inspector. Existing backend contracts and primary Data → Process → Fit → Export continuity remain.
2. Compare two layouts for the same Test Data/Card reader, using the same synthetic long-name tensile
   dataset and explicitly related stored card. A table-first engineering workbench is recommended for
   the daily search/download task; B is a full-width selected-detail/curve-focused reader with a
   Results return path. B is not a Modeling Data/Process/Fit/Export screen, although Modeling may
   later reuse its graph-dominant grammar. Review selected, empty, error and dense numeric/unit states.
3. Use the full foundation strategy with the proven backend. Build an isolated `apps/web-next`
   application with temporary CSS/build boundaries, then perform one cutover. It is not a permanent
   dual application. Keep React 19, TypeScript 7 and Vite 8. Candidate tooling is Radix accessible
   primitives, CSS Modules/custom-property tokens, React Router, TanStack Query/Table, RHF/Zod,
   Lucide and the existing resizable panels. Evaluate ECharts only with scientific/performance proof
   against SVG/Recharts. Retain Storybook, Vitest, Testing Library and Playwright. Maintained
   scientific libraries are allowed when validated; use packages rather than whole-repo copies or
   forks, and record an owner if shadcn source maintenance is adopted.
4. Keep the existing application as an explicitly legacy compatibility baseline until feature,
   scientific and UX parity are evidenced. Do not add route-specific high-DPI workarounds, fabricate
   wide-screen content, or use CSS zoom/blanket scaling.
5. Stage the work as RD-00 governance, RD-01 contracts/prototype, RD-02 connected reader, RD-03
   validation, RD-04 write journeys, RD-05 expansion, RD-06 single cutover and RD-07 retirement.
   Each stage preserves recovery, authorization, exact ordinary identity, explicit associations,
   native download and saved-result read-back.

## Preserved product and data contracts

The foundation uses the [data management policy](../docs/product/data-management-policy.md). Only
Material information edits have domain revision history. State/PropertySet, Specimen, TestRun,
TestData, Dataset, Selection, Mapping Profile, Process, Model, Solver Card and Link data are stable
saved objects; renames preserve links and do not stale science. Actual inputs/options change current
eligibility, while raw/input/output bytes, units, typed relations, authorization, scientific
validation and release meaning remain intact. A universal Entity–Activity–Agent graph is not a
frontend completion criterion.

The pilot is an ordinary-ID Test Data search/detail → explicitly associated stored Solver Card → native
download reader. The connected corpus uses ordinary Test Data objects authorized by `DATASET_READ` and
stored cards authorized by `EXPORT_READ`; Catalog publication is not required merely to query them.
Test Data and Cards open directly. A title metadata PATCH updates the same ordinary row, keeps the
association and creates zero nonmaterial domain revisions. A related card is never chosen by sibling
name or `latest`; relationship traversal is not derivation.

## Evidence and cutover

The first foundation evidence set captures 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160
at browser zoom 100%, at original resolution with 100%-pixel crops for header, navigator,
table/form controls and graph/native preview. It reviews information hierarchy, engineering task
flow and responsive/wide-screen composition separately. Actual Windows 4K physical readability is
deferred to #223; geometry, clipping, overflow and interaction failures remain blocking.

ADR-0035 remains authoritative for current, frozen and transient evidence paths, frozen bytes,
recovery, checksums and offline checks. This ADR partially supersedes only its Decision 2 rule that
every small change repeats the full five-viewport family: the first foundation shell and connected
reader still require all five, the P1 foundation still requires its 30 original screen captures, and
later small changes use risk-bounded affected viewport/state evidence. Known geometry, clipping,
overflow and interaction failures remain blocking.

### Partial supersession index

- **ADR-0035, Decision 2:** preserve the current/frozen/transient roots, frozen bytes, recovery,
  checksums and offline checks; supersede only the full five-viewport repeat requirement for later
  small risk-bounded changes. The first foundation shell, connected reader and P1 set of 30 originals
  still use the complete evidence requirement.

Cutover is additive and single: preserve pre-cutover artifacts, database backup and old build;
migrate forward; reconcile writes made during the transition; rehearse rollback without destructive
downgrade; then prove zero consumers before removing old routes, CSS, compatibility exports and
dependencies. The v1 exact compatibility mapping is private and the unmodified v1 runtime remains
legacy until this evidence exists.

## Consequences

The redesign can use an accessible maintained primitive or scientific package when the program's
capability, accessibility, bundle, numeric and ownership evidence supports it. The program does not
grant publication authority. Runtime/database/API changes belong to later bounded units, and no
production implementation is implied by this D0 ADR alone.


## 후속 결정 — 2026-09-07

사용자는 소재 중심 대표 화면의 큰 구조를 구현 기준으로 삼고, 필터 항목·표의 열 등 세부사항은 나중에 조정할 수 있음을 확인했다.
이 결정은 Decision 2와 2026-09-06 amendment의 미선택 비교 상태를 후속 갱신한다. 이전 본문은 당시 판단 기록으로 보존한다.

소재 중심 탐색과 직접 실험/솔버 카드 조회를 함께 제공한다. 소재 카드는 항목·값·단위를 정렬하고 표와 전환한다.
왼쪽 소재/시편 트리와 별도 필터, 목록 선택의 오른쪽 미리보기, 목록을 숨기는 확대 상세와 탐색 상태 복귀를 기준으로 한다.
구체 기준은 [UI 원칙](../docs/product/frontend-ui-principles.md)에 한 번만 기록한다. 등록·처리·모델 업무를 같은 목록 배치에 강제하지 않는다.
화면 구조에 대한 동의는 모든 픽셀·필터·공학 기본값·실제 장비 가독성·제품 전환의 승인이 아니다.

foundation·공학 의미·단일 전환 결정은 유지한다. 이전 여섯 안 및 P1의 고정 캡처 개수는 당시 비교 범위이며 앞으로 반복 제작할 의무가 아니다.
첫 새 shell/연결 reader의 다섯 viewport 검증과 변경 위험에 따른 후속 검증은 유지한다.
규칙 정리의 대체 관계와 개인 오케스트레이션 보류는 [ADR-0038](0038-development-guidance-and-reader-baseline.md)을 따른다.
