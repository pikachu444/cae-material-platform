# Architecture decision record index

이 색인은 구현 전에 관련 결정을 빠르게 찾기 위한 진입점입니다. ADR 번호, 본문, 경로와
기존 링크는 변경하지 않으며 새 ADR은 아래 한 분류에 정확히 한 번 추가합니다.

## 시스템·도메인·모델

- [ADR-0001 Modular monolith](0001-modular-monolith.md)
- [ADR-0002 PostgreSQL provenance](0002-postgresql-provenance.md)
- [ADR-0003 Immutable artifacts](0003-immutable-artifacts.md)
- [ADR-0004 Isolated plugins](0004-isolated-plugins.md)
- [ADR-0005 Material Model IR](0005-material-model-ir.md)
- [ADR-0018 Reference elastoplastic multisolver slice](0018-reference-elastoplastic-multisolver-slice.md)
- [ADR-0020 Material classification and polymer viscoelastic delivery](0020-material-classification-and-polymer-viscoelastic-delivery.md)
- [ADR-0023 Reference Ogden, Prony and LAW62 mapping](0023-reference-ogden-prony-and-law62-mapping.md)
- [ADR-0028 Configurable material information system](0028-configurable-material-information-system.md)
- [ADR-0029 JSON exchange and reusable processing](0029-json-exchange-and-reusable-processing.md)
- [ADR-0036 Material-only domain revisions and stable data links](0036-material-only-revisions-and-data-links.md)

## 데이터·가져오기·처리

- [ADR-0007 Reference processing slice](0007-reference-processing-slice.md)
- [ADR-0008 Reference statistics pair slice](0008-reference-statistics-pair-slice.md)
- [ADR-0009 Reference outlier assessment slice](0009-reference-outlier-assessment-slice.md)
- [ADR-0010 Reference import orchestration slice](0010-reference-import-orchestration-slice.md)
- [ADR-0021 Reference shear relaxation processing](0021-reference-shear-relaxation-processing.md)
- [ADR-0031 Reviewed polymer processing output promotion](0031-reviewed-polymer-processing-output-promotion.md)

## 보정·검증

- [ADR-0011 Reference linear elastic calibration slice](0011-reference-linear-elastic-calibration-slice.md)
- [ADR-0012 Reference candidate selection and IR promotion](0012-reference-candidate-selection-and-ir-promotion.md)
- [ADR-0013 Reference validation template and runner boundary](0013-reference-validation-template-and-runner-boundary.md)
- [ADR-0014 Reference validation result interpretation policy](0014-reference-validation-result-interpretation-policy.md)
- [ADR-0022 Bounded reference Prony calibration](0022-bounded-reference-prony-calibration.md)
- [ADR-0026 Iterative calibration evidence chain](0026-iterative-calibration-evidence-chain.md)

## 릴리스·거버넌스

- [ADR-0015 Review lifecycle policy](0015-review-lifecycle-policy.md)
- [ADR-0016 Reference release completeness gate](0016-reference-release-completeness-gate.md)
- [ADR-0017 Release lifecycle and impact](0017-release-lifecycle-and-impact.md)
- [ADR-0019 Near-term delivery and PostgreSQL verification gate](0019-near-term-delivery-and-postgresql-verification-gate.md)
- [ADR-0024 Catalog genealogy revision links](0024-catalog-genealogy-revision-links.md)
- [ADR-0025 Production pilot completion program](0025-production-pilot-completion-program.md)
- [ADR-0027 Bulk export bundle](0027-bulk-export-bundle.md)
- [ADR-0032 Conditional OpenRadioss linear Prony export](0032-conditional-openradioss-linear-prony-export.md)
- [ADR-0033 Recipe/Batch output promotion lineage](0033-recipe-batch-output-promotion-lineage.md)
- [ADR-0035 Visual evidence lifecycle and recovery](0035-visual-evidence-lifecycle-and-recovery.md)

## 프론트엔드·제품

- [ADR-0006 Product vertical slice](0006-product-vertical-slice.md)
- [ADR-0030 Product workbench and access surface](0030-product-workbench-and-access-surface.md)
- [ADR-0034 Product-facing session and workspace rebuild](0034-product-facing-session-and-workspace-rebuild.md)
- [ADR-0037 Task-first frontend foundation and single cutover](0037-task-first-frontend-foundation.md)

- [ADR-0038 개발 지침의 역할 분리와 소재 중심 조회 기준](0038-development-guidance-and-reader-baseline.md)

## 현재 결정과 대체 관계

ADR-0036은 소재 정보 수정만 리비전 관리하는 현재 데이터 정책이다. 기존 ADR-0002·0003·0006~0034 중 보편적 비소재 이력/PROV 요구를 부분 대체한다. 각 본문의 보존·대체 범위를 따른다. ADR-0001·0004·0005의 모듈·plugin 격리·IR 결정은 유지한다.

ADR-0037은 새 frontend 기반·단계적 구현·일괄 전환을 정한다. 2026-09-07 후속 결정이 기존 A/B와 여섯 비교 상태를 갱신했다. 현재 기준은 소재 중심 카드/표와 오른쪽 미리보기·확대 복귀이며 필터·열·세부 디자인은 조정 가능하다.
ADR-0035의 evidence 경로·frozen bytes·복구·checksum·offline 검사는 유지하고, 작은 변경의 무조건적인 다섯 viewport 반복만 ADR-0037이 대체한다. 과거 P1 캡처 수는 당시 범위의 완료 기록이다.

ADR-0038은 지침·skill·T/Q의 중복과 적용 범위를 정리한다. 개인 모델/오케스트레이션 비용 정책은 보류했다.
ADR의 Proposed/Accepted/Superseded 상태와 부분 대체 범위는 각 본문에서 확인한다. manifest의 authoritative 분류가 과거 결정의 대체 상태를 되돌리지 않는다.
진행 상태는 [현재 작업 상태](../docs/planning/frontend-redesign-status.md), 전체 순서는 [개편 계획](../docs/planning/frontend-redesign-program.md)을 따른다.
