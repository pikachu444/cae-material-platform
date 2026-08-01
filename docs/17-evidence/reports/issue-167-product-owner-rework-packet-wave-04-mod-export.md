# Issue #167 product-owner rework packet — WAVE-04 / MOD-EXPORT

Date: 2026-07-29
Author: active `/root` primary agent
Configured main-agent source: `.codex/config.toml` (`gpt-5.6-sol`, `xhigh`)
Writer: one configured `implementer_luna_max` only
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Why this is a replacement candidate

The six MOD-EXPORT images in the manifest are still pending and have no product-owner approval. The
product owner rejected their information architecture after the earlier deterministic/correction
cycle and explicitly approved the rough region direction in:

- `docs/00-research/ux-service-reference/modeling-export-layout-concept.html`;
- `docs/17-evidence/images/issue-167-service-reference/modeling-export-layout-concept-1440x900.png`.

This packet replaces only the unapproved MOD-EXPORT candidate sources/evidence. It does not reopen an
approved dependency, alter production React/API/backend contracts, change the 72-image inventory,
approve any lifecycle, or authorize commit/push/PR/merge.

## 2. Authority read by the main agent

- GitHub #167 current body and checklist;
- `AGENTS.md`, `.codex/config.toml`, `.codex/agents/implementer-luna-max.toml`;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`, especially `E-01`–`E-08`;
- `docs/01-product/visual-acceptance-matrix.md`;
- approved MOD-FIT and MAT-CARD sources/images registered in
  `docs/01-product/service-reference-manifest.yaml`;
- all six current MOD-EXPORT candidates at original resolution, prior writer/correction/reviewer
  packets and the family state evidence;
- current React contracts:
  `modeling-export-prerequisites.tsx`, `neutral-hyperelastic-export.tsx`,
  `solver-card-delivery.ts`, `solver-card-delivery-ui.tsx`;
- current API/domain contracts:
  `target_preview.py`, `target_delivery.py`,
  `reference_isotropic_tabulated_plasticity.py`,
  `reference_linear_viscoelasticity.py`, `reference_ogden_prony.py`.

The current backend is synthetic/non-production and declares only supported `kg_m_s` reference
tuples. It keeps exporter mapping states
`exact|transformed|approximated|ignored|unsupported|not_applicable`, rejects unsupported/ignored
loss, and requires the exact acknowledgement identity for approximated/ignored preview delivery.

## 3. Product-owner findings to implement

1. Remove the shallow full-width graph above the result. It compresses the card/mapping result and
   gives the graph neither enough height nor enough task value.
2. Replace the black native-preview surface with a light professional code/data surface. The native
   preview remains the dominant region.
3. Replace developer/governance-first normal copy:
   - `Export preflight` → `Export check`;
   - `Next safe action` → the concrete current action;
   - `Mapping sheet` → `Mapping details`;
   - `Preflight evidence` → a target-specific consequence summary;
   - normal `Evidence`/`Receipt` language → `Advanced`/`Delivery details`.
4. Keep Destination and Export check in the left setup pane. Place Solver Card preview in the
   dominant center. Place read-only Mapping details above a compact Fit source preview in the bounded
   right result column. The right column is not a control inspector.
5. Physical values such as Density are never editable in Export. They are pinned from the exact
   source revision. Show `Source` and `Output`; provide `View source material`. A physical correction
   happens upstream through a governed revision.
6. A target tuple may change the deterministic output representation/status, but the same exact
   source + solver + version + unit tuple must always produce the same rows/statuses.
7. Material State is applicability/source context unless the exporter actually writes a dependency.
   Do not count a room-temperature label as an exact solver-field mapping.
8. `Ready to create`, `Review required` and `Cannot create` must agree with blockers and exact
   acknowledgement state. A visible unchecked approximation cannot coexist with Ready/enabled create.
9. The mapping set and Fit source plot are family-specific. Do not reuse metal hardening rows/axes for
   linear-viscoelastic or hyperelastic sources.
10. Preserve the existing exact preview versus immutable create/delivery distinction, source/target
    invalidation, local scrolling, responsive containment, accessibility and one primary action.

## 4. Exact normal topology

Semantic two-pane structure:

```text
Export setup 300–340 px | Result workspace flexible
                       | Solver Card preview dominant | result context 288–336 px
                                                       | Mapping details
                                                       | Fit source
```

At 1366, the center preview must remain at least 680 px wide after the fixed setup/result-context
widths and splitters. At 1920, the center preview receives the expansion. The result-context column
contains no editable model/property controls. Every long region scrolls locally with a perceptually
visible reserved rail; body/document overflow remains zero.

Keep the approved shell, compact title row, `Data | Process | Fit | Export` strip and status bar.
Remove the old `Selected Fit source` full-width top band. Keep the selected Fit identity in compact
source context and the right-bottom Fit source preview with `Open full graph`.

## 5. Deterministic synthetic metal fixture

Use the existing non-production DP780 reference semantics without choosing a production material
law or threshold. The displayed Abaqus target is the declared `2025 / kg_m_s` tuple. Native values
must be internally consistent with kg, m, s and Pa:

- density: `7.80000000E+03` kg/m³;
- Young's modulus: `2.10000000E+11` Pa;
- Poisson ratio: `3.00000000E-01`;
- initial yield and hardening stresses:
  `4.50000000E+08`, `5.00000000E+08`, `5.60000000E+08`,
  `6.20000000E+08`, `6.80000000E+08` Pa;
- plastic strain remains dimensionless.

The old static card incorrectly combined a `kg_m_s` label with tonne/mm³ and MPa-scale native
numbers. Do not preserve that inconsistency. The Fit source may display stress in MPa, but Mapping
details must make the source display unit and native output unit explicit.

Primary decision-relevant Mapping details:

| Item | Source | Target/output | User consequence | Technical status |
| --- | --- | --- | --- | --- |
| Density | 7,800 kg/m³ | `*DENSITY` 7.8e3 kg/m³ | Values unchanged | exact |
| Isotropic elasticity | E 210 GPa, ν 0.30 | `*ELASTIC` 2.1e11 Pa, 0.30 | Values unchanged | exact |
| Initial yield | 450 MPa at εp=0 | first `*PLASTIC` row, 4.5e8 Pa | Converted | transformed |
| Hardening response | true stress / true plastic strain | native `*PLASTIC` rows | Native formatting; values not approximated | transformed |
| Post-necking extension | acknowledged bounded extension | target extension behavior | Review required or Reviewed | approximated |
| Unit convention | kg·m·s / Pa | explicit consistent-unit comment | Native formatting | transformed |

Temperature and strain-rate items are `not_applicable` for this bounded reference and belong in
Advanced. Material State remains Source context and is not a mapping-success row. The visible header,
rows, summary and technical counts must agree: two exact, three transformed, one approximated,
two not-applicable in Advanced, zero unsupported.

The normal image represents the acknowledgement-complete state:
`Ready to create · 0 blockers · 1 reviewed mapping`. It exposes the checked identity-bound review
state and enables the sole filled `Create solver card`. The approximation-blocked image uses the
same exact source/target/report with the review unchecked:
`Review required · 0 blockers · 1 item to review`, and creation remains disabled.

## 6. Family adaptation evidence

Keep the six inventory approval targets unchanged. Add same-topology, non-approval state evidence at
1440×900 for:

- linear viscoelastic: density, instantaneous elasticity, shear/bulk Prony terms, temperature
  applicability and unit convention; Fit source plots normalized shear response against log time;
- hyperelastic/hyper-viscoelastic: density, Ogden/strain-energy terms, volumetric response, available
  test modes and Prony terms; Fit source uses compact `Uniaxial | Biaxial | Planar | Volumetric`
  mode affordance and plots the correct mode quantity.

Use actual bounded reference-plugin status semantics. For example, Ogden-Prony volumetric response
is exact for the Abaqus `D1=0` representation and approximated for the acknowledged OpenRadioss
`ν=0.495` representation. These images prove content adaptation only; they must not change topology,
inventory count or lifecycle.

## 7. Required approval and state behavior

Approval targets remain:

- normal 1366×768, 1440×900, 1920×1080;
- source blocked 1440×900;
- approximation/review blocked 1440×900;
- created/delivered 1440×900.

Exceptional responsive siblings remain required at 1366/1440/1920. Preserve and recapture the
existing no-target, checking/creating, delivery-error and long-mapping same-topology evidence.

State-specific primary commands:

- normal: `Create solver card`;
- source blocked: `Back to Fit`;
- review blocked: disabled `Create solver card` until exact acknowledgement;
- created: `Open solver card`, with secondary `Delivery details`;
- no target: select Destination;
- checking/creating: prevent duplicate submit and announce progress;
- failure: one specific retry while preserving the last valid check/preview.

No state may imply review, approval, release or Activity creation. The create result is one immutable
Solver Card; Delivery details may disclose the separate receipt identity without using it as normal
task vocabulary.

## 8. Source ownership

The writer may edit only:

- `docs/00-research/ux-service-reference/modeling-export-normal.html`;
- `docs/00-research/ux-service-reference/modeling-export.css`;
- `docs/00-research/ux-service-reference/modeling-export.js`;
- `docs/00-research/ux-service-reference/capture_modeling_export_wave04.py`;
- `docs/00-research/ux-service-reference/validate_modeling_export_wave04.py`;
- `docs/00-research/ux-service-reference/modeling-export-wave04.staging.json`;
- MOD-EXPORT-only images, measurements and family state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

The rough concept files are read-only direction. Do not edit approved dependencies, common manifest,
inventory, common evidence, product policy, production React/API/backend, Activity, git state or
GitHub. Preserve all unrelated dirty-worktree changes. Do not reset, clean, stash, discard, commit,
push, open or merge a PR.

## 9. Deterministic gates

Strengthen the family validator so it fails unless:

- all six targets and every state/responsive image have exact viewport, dimensions, hash and pending
  lifecycle;
- the kg-m-s/Pa target label, native card numbers and Mapping details agree;
- source Density is read-only and exposes Source/Output plus `View source material`;
- Material State is absent from mapping-success rows;
- visible user rows, technical statuses, counts and Advanced not-applicable rows agree;
- Ready/Review required/Cannot create agree with blockers, acknowledgement and button state;
- the same exact tuple produces identical mapping digest/rows across relevant states;
- target change clears preview, acknowledgement and current delivery;
- native preview is dominant, light, independently scrollable and at least 680 px wide at 1366;
- no full-width top graph exists; the family-specific Fit source stays in the bounded right-bottom
  region without distorted SVG text/strokes;
- linear-viscoelastic and hyperelastic evidence uses its own row set and plot quantities;
- long mapping/native preview show discoverable local rails without text collision;
- one filled primary action, semantic controls, focus-visible, ARIA announcements, keyboard paths,
  zero console/page/resource errors and zero document/body overflow pass;
- legacy selectors and nested persistent-card interactions remain zero;
- all applicable Q-01–Q-11 items are recorded from original-resolution images.

Run both helpers with `--help` before capture/validation, then at minimum:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_modeling_export_wave04.py --all-packet-targets
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_export_wave04.py --all-packet-targets --expect-main-agent-status pending
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py --all-packet-targets --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_modeling_export_wave04.py docs/00-research/ux-service-reference/validate_modeling_export_wave04.py
node --check docs/00-research/ux-service-reference/modeling-export.js
git diff --check
```

Apply the fresh Web Interface Guidelines already fetched by the main agent and the canonical
Q-01–Q-11 checklist. Return exact changed paths, commands/results, six approval image paths,
viewports/SHA-256, family adaptation evidence, Q results and residual concerns. Do not request
product-owner approval.
