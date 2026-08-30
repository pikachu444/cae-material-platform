# Issue #195 polymer viscoelastic Fit implementation and acceptance packet

## 1. Packet status and decision

| Item | Decision |
| --- | --- |
| GitHub issue | [#195 `modeling: 폴리머 점탄성 Fit 확장`](https://github.com/pikachu444/cae-material-platform/issues/195) |
| Packet type | Implementation 전 제품·공학·검증 명세. 이 문서 자체는 기능 구현이나 생산 정책 승인이 아니다. |
| Audited baseline | `origin/main` `36e8312fa85253ad8fee88f63a3a4bf096d92a9c`, 2026-08-11 |
| Scope recommendation | **`narrow`**. `close`나 `supersede`가 아니라, 이미 구현된 bounded reference 기능을 재구현하지 않고 production-grade 입력·보정·검증 계약과 독립 reference set의 미충족 범위만 남긴다. |
| User outcome | 정확한 Material/Condition/Test Data/Processing Output 개정본에서 relaxation 또는 승인된 DMA 입력을 선택하고, 재현 가능한 후보를 비교·검토하여 엔지니어가 선택한 immutable model revision을 저장한 뒤 Neutral/solver export 경계까지 추적한다. |
| Explicit exclusions | #196 hyperelastic·finite-strain·Ogden-Prony, production release, 비공개 상용 optimizer 추정, generic calibration framework, 현재 UI/API/DB/contract/test 변경, 중앙 backlog 순서 변경 |
| Current-PR verification boundary | Compose, DB migration, browser, screenshot, five-viewport capture는 `N/A — planning-only documentation`이다. 미래 UI 구현의 acceptance 조건만 정의한다. |

이 packet의 근거 표기는 다음 다섯 값만 사용한다.

- `CONFIRMED_CURRENT`: 위 baseline의 코드·계약·migration·test·현재 제품 문서로 확인한 사실.
- `FACT_PUBLIC`: 직접 연결한 공식 공개 문서, 1차 논문 또는 공식 표준 metadata로 확인한 사실.
- `INFERENCE`: 여러 확인 사실에서 도출했지만 별도 제품 결정이 필요한 해석.
- `PROPOSED_DECISION`: 이 packet이 구현 방향으로 권고하되 아직 승인되지 않은 결정.
- `OPEN_DECISION`: 구현 전에 제품 소유자 또는 공학 책임자가 명시적으로 승인해야 하는 결정.

### 1.1 Executive conclusion

`CONFIRMED_CURRENT` — #195 본문의 “현재 Modeling Fit은 단순 금속 Fit이고 polymer branch는 향후 범위”라는 전제는 최신 main과 일치하지 않는다. main에는 다음 bounded reference 흐름이 이미 있다.

- shear relaxation 전용 import와 canonical Test Data;
- manual/WLF/Arrhenius temperature shift와 master curve Processing Output;
- time-domain generalized-Maxwell/Prony 1–10 term candidate 비교;
- DMA storage/loss joint response와 BIC 기반 bounded recommendation;
- 추천과 엔지니어 선택·이유의 분리, `Save fit & continue`, immutable Processing Output;
- linear-viscoelastic IR와 Neutral Material IR 승격;
- Abaqus Prony exact mapping과 OpenRadioss `/MAT/LAW1` + `/VISC/LPRONY` 조건부 mapping;
- exact revision, method version, provenance digest, save/reload와 stale recovery.

`PROPOSED_DECISION` — 따라서 #195의 잔여 목적은 “polymer Fit을 새로 추가”하는 것이 아니라 아래 네 가지로 좁힌다.

1. current bounded reference의 수식·입력·단위·convention을 production 후보 계약으로 명문화하고 독립 oracle로 교차 검증한다.
2. #205/#206/#209가 제공할 공통 unit/channel/governed DMA 위에서 bulk, loss factor, explicit frequency convention 등 승인된 canonical 입력을 연결한다.
3. weighting, multistart, identifiability, holdout, regularization, term selection과 recovery를 모두 기록 가능한 Plan/Run/Candidate 계약으로 확장한다.
4. 기존 Fit/Processing Output/IR/Neutral/export를 재사용하며, 새 evidence가 필요한 부분만 additive하게 확장한다.

이 결론은 현재 bounded reference를 production-ready라고 선언하지 않는다. 현 구현의 hard-coded reference options, single-start least squares, BIC/nRMSE, observed-only domain과 `non_production=true` 표시는 생산 정책이 아니다.

## 2. Authority, dependencies, and bounded ownership

### 2.1 Authority read for this packet

`CONFIRMED_CURRENT` — 범위 판정에는 root `AGENTS.md`, [current backlog](../planning/backlog.md), #117/#158/#184/#195/#205/#206/#209/#211/#213/#214, `FR-CAL-001`–`007`, `FR-MOD-P-001`–`005`, ADR-0020/0022/0031/0032, 현재 implementation/status 문서와 아래 gap evidence를 사용했다. `docs/_incoming/`은 열람하지 않았다.

중앙 backlog의 첫 미완료 단위는 #184이고 #195는 #117에서 deferred implementation 후보다. 이 packet의 merge는 #117의 실행 순서를 바꾸거나 #195 구현을 시작하지 않는다. #195는 packet merge 후에도 open·implementation-waiting 상태여야 한다.

### 2.2 Owned and forbidden future scope

| Boundary | In #195 narrowed implementation | Not in #195 |
| --- | --- | --- |
| Constitutive regime | isotropic, small-strain, linear viscoelastic generalized Maxwell | #196 large-strain hyperelastic/hyper-viscoelastic, Ogden base, nonlinear strain-dependent viscoelasticity |
| Input | approved shear/bulk relaxation and approved DMA channels with explicit units/conventions | silent conversion, unreviewed creep inversion, proprietary formats/defaults |
| Fit | reproducible candidate evaluation, diagnostics, recommendation, engineer selection | automatic engineer approval, undisclosed objective or preprocessing |
| State | exact input revisions, immutable run/candidate/selection evidence, selected-model revision | mutable released artifacts, `latest` pins, row-per-point large-curve storage |
| Promotion/export | reuse Processing Output, linear-viscoelastic IR, Neutral, Abaqus and conditional OpenRadioss | LAW62 for the linear family, new solver families, #213 template sandbox, #214 LS-DYNA MAT_024 |
| UI | reuse #158 common Fit structure and shared tokens | new navigation, third inspector, route-specific 4K workaround |

## 3. Primary journey: Data → Process → Fit → Check/Review → Export

### 3.1 Setup and exact context

The primary actor is a materials engineer with permission to read the source records, execute Modeling, and save a selected model.

1. **Data** — The engineer selects one stable Material and its exact Material revision, one exact Condition revision, and one or more exact Test Data revisions. The normal surface shows human-readable names, test kind, temperature, domain and units. UUIDs, hashes and full provenance stay in Evidence.
2. The engineer confirms either an approved relaxation input or an approved DMA input. A relaxation input identifies stress/modulus quantity, deformation mode, time unit, temperature and strain amplitude. A DMA input identifies storage/loss channels, frequency kind and unit, temperature and strain amplitude. A source lacking these semantics is blocked, not guessed.
3. **Process** — If resampling, replicate aggregation, temperature shifting or another approved preparation is needed, the engineer selects an immutable Processing Output revision. That output pins every source Test Data revision, method key/version, settings and digest. Original bytes remain immutable.

### 3.2 Fit actions and visible result

4. **Fit** — Source/context and input-domain summary remain visible. The engineer chooses manual term counts or an approved candidate policy, supplies every required bound/weight/scale option, and starts a deterministic Run. The UI never substitutes a product default for an omitted production decision.
5. Candidate results show response and residual over the fitted domain, dimensional and normalized parameters, instantaneous/equilibrium convention, temperature-shift evidence, validation/holdout domain, warnings and claimed applicability. Time and frequency views identify `s`, `Hz`, `rad/s`, `log10` or `ln` explicitly.
6. The system may mark one candidate as **recommended** using the Plan's serialized rule and evidence. Recommendation is not selection. The engineer compares candidates and chooses a candidate, records a selection reason, and acknowledges any blocking-to-warning disposition such as modulus mismatch, identifiability, TTS limitation or extrapolation risk.

### 3.3 Check/Review, save, read-back, and recovery

7. **Check/Review** — The engineer checks response, residual, parameters, fitted/holdout domains and warnings. A failed convergence, invalid coefficient, source digest mismatch or unsupported conversion remains a failed/blocked Run and cannot be promoted.
8. The engineer invokes **`Save fit & continue`**. The server recomputes or verifies the exact selected candidate identity and creates an immutable selected-model revision. Client-supplied replacement parameters are rejected. Sibling candidates and Run evidence remain unchanged.
9. After reload, the same exact source revisions, Plan, Run, candidates, recommendation, selection reason/acknowledgements, parameters, curves/digests and selected-model revision read back deterministically. A byte-equivalent read produces the same canonical digest.
10. If an upstream Material, Condition, Test Data or Processing Output gets a new revision, only the relevant **current pointer** becomes stale. The old selected-model revision and its evidence are never mutated. The user sees old versus new revision context and may restore the exact old context or intentionally recompute with the new one.
11. On save failure, the unsaved choice and reason stay in local session state, the immutable inputs and successful Run remain readable, and retry is idempotent. On calculation failure, the user may correct an explicit Plan option and create a new Run; the failed Run is retained as evidence.

### 3.4 Neutral and solver-card boundary

12. **Export** — A valid selected-model revision may be promoted through the existing linear-viscoelastic Material Model IR and Neutral Material IR boundary. Promotion pins the exact selected Processing Output/Run evidence and does not reinterpret its convention.
13. Solver preflight reports each mapping as exact, transformed, approximated, unsupported or not applicable. Abaqus Prony remains the current exact target for supported inputs. OpenRadioss remains conditional on ADR-0032 constraints and an acknowledged external solid-property requirement. Unsupported bulk/TTS or solver semantics block card creation rather than falling back silently.
14. A solver card is its own immutable revision with target solver/version/unit profile, exact Neutral revision, mapping report and checksum. It is distinct from recommendation, selection, saved result, review and release.

### 3.5 Primary acceptance

The journey passes only when an engineer can complete steps 1–14 with an exact synthetic reference input, reload the same result, observe deliberate stale invalidation after an upstream revision change, recover without mutating history, and obtain the expected solver preflight disposition. Passing an optimizer regression alone is insufficient.

Negative and technical cases are specified separately in Sections 10 and 13.

## 4. Current implementation and target gap matrix

The matrix distinguishes current user value from bounded-reference limitations. A “new implementation” value of “No” means #195 must reuse that capability and add only contract/evidence changes proven necessary.

| Capability and status | Current implementation and test evidence | What a current user can do | Bounded reference limit / production gap | Reuse / new implementation | Dependency and do-not-duplicate rule |
| --- | --- | --- | --- | --- | --- |
| Exact Modeling source context — **complete** | `apps/web/src/common-processing-workbench.tsx`; `apps/web/src/common-processing-workbench.test.tsx`; `backend/src/cmp/modules/processing/application/common_outputs.py` | Select exact Test Data/Processing Output context, process, fit, save and reload in the common Workbench. | Some production input semantics are not governed channel metadata yet. Server-side invalidation must be verified for every new upstream type. | Reuse; additive metadata/invalidation only. **New: partial.** | #205/#206. Do not create a polymer-only source picker or parallel current-pointer model. |
| Shear relaxation import — **complete (bounded)** | `backend/src/cmp/modules/datasets/domain/reference_shear_relaxation.py`; `backend/tests/unit/test_reference_shear_relaxation_dataset.py`; `backend/tests/unit/test_reference_shear_relaxation_processing.py` | Import a dedicated monotone positive shear-relaxation modulus CSV with declared time/modulus units and preserve raw/normalized evidence. | Accepts an already-derived shear modulus, not governed raw stress + step-strain semantics; no bulk channel; bounded validation rules. | Reuse importer for its exact profile; add approved canonical channels elsewhere. **New: yes for raw/bulk semantics, not for existing profile.** | #205/#206. Do not rewrite the accepted shear profile or hide stress-to-modulus derivation. |
| DMA processing — **partial** | `backend/src/cmp/modules/processing/domain/polymer_viscoelastic.py`; `tests/unit/test_common_processing_pipeline.py`; migrations 083–085; common Workbench tests | Use canonical Test Data carrying `frequency_hz`, shear storage and shear loss modulus; compare joint response and save the selected result. | Governed DMA import is not on main; only Hz and absolute storage/loss Pa; no loss factor, angular-frequency source, bulk DMA, explicit conversion evidence or per-temperature weighting. | Reuse evaluator and output contract where conventions match. **New: yes, bounded to approved channels/evidence.** | #205/#206/#209. Do not build another DMA importer in #195. |
| Master curve and temperature shift — **complete (bounded)** | `backend/src/cmp/modules/processing/domain/viscoelastic_master_curve.py`; `backend/tests/unit/test_viscoelastic_master_curve.py`; `tests/integration/test_viscoelastic_master_api.py`; `apps/web/src/viscoelastic-master-workbench.tsx` | Build manual, WLF or Arrhenius shear-relaxation master curves at an exact reference temperature with observed-overlap alignment and no hidden extrapolation. | Isothermal shear-relaxation reference only; current fit initial values/bounds are reference constants; no TTS adequacy metric/holdout rule; no DMA master-curve production path. | Reuse immutable outputs and shift evidence. **New: yes for adequacy/approved domains, not for existing methods.** | #206/#209 and an `OPEN_DECISION` on TTS validity. Do not copy the master-curve service into Fit. |
| Time-domain generalized Maxwell/Prony — **complete (bounded)** | `backend/src/cmp/modules/processing/domain/polymer_viscoelastic.py`; `backend/src/cmp/modules/processing/domain/common_pipeline.py`; unit/common-output tests | Evaluate 1–10 shear terms, BIC/nRMSE and candidate curves using an observed time domain. | Single start; one residual normalization; no bulk, holdout, identifiability, regularization or approved production policy; Workbench currently carries reference options. | Reuse equations and typed output after independent oracle check. **New: production engine extension required.** | Engineering contract/reference set first. Do not create a generic EAV optimizer. |
| Frequency-domain generalized Maxwell — **complete (bounded)** | Same domain module and `test_common_processing_pipeline.py` DMA exact/negative cases | Jointly fit shear storage/loss response after internal `omega=2*pi*f` conversion. | Conversion is not first-class evidence; only Hz input; equal concatenation under one scale; no mixed-domain or per-channel weights. | Reuse analytical response. **New: explicit unit/objective/evidence extensions.** | #205/#206/#209. Do not infer frequency kind from column magnitude or name. |
| Candidate recommendation and engineer selection — **complete (bounded)** | `apps/web/src/features/modeling/ui/stages/fit/modeling-fit-decision.tsx`; decision-contract tests; `backend/src/cmp/modules/processing/application/common_outputs.py` | See candidate comparison/BIC, keep recommendation separate, select the actual server result, record reason and save. | To select a different Prony count the current user changes policy and reruns; no general durable production candidate set, uncertainty or holdout comparison. | Preserve state separation. **New: candidate persistence/diagnostics may be additive.** | FR-CAL-005/006/007. Do not auto-select the recommendation or accept client-substituted parameters. |
| Processing Output promotion — **complete** | common output application/persistence/API; `tests/unit/test_common_processing_output.py`; common Workbench integration tests | Save exact fit decision and promote the server-calculated selected result as immutable Processing Output. | New objective/bounds/weights/TTS evidence need versioned fields or artifact references; schema change must remain typed and backward compatible. | Reuse stable identity + immutable revisions. **New: additive only.** | Contract-first implementation unit. Do not create a second “fit result” aggregate without proving need. |
| Legacy Plan/Run/Attempt/Candidate calibration — **complete but separate bounded slice** | `backend/src/cmp/modules/modeling/domain/reference_prony_calibration.py`; ADR-0022; unit/integration tests | Run a deterministic bounded two-term multistart reference calibration and persist attempts/candidates. | Deliberately excludes production term range, TTS/frequency data and automatic promotion. It is not the common Workbench result model. | Reuse lifecycle semantics after a compatibility decision, not necessarily its tables/API. **New: decision required.** | Avoid merging two existing stores into a generic framework merely for symmetry. |
| Linear-viscoelastic IR and selected-model revision — **complete (bounded)** | `backend/src/cmp/modules/modeling/domain/reference_linear_viscoelasticity.py`; contract; migrations; unit/integration tests | Promote reviewed 1–10 term Processing Output with exact pins, instantaneous `E/nu`, fitted/catalog `G0` comparison and acknowledgement. | Production validity and uncertainty unassessed; bulk may only be explicit or `not_characterized`; no new objective evidence fields. | Reuse convention and immutable identity. **New: additive evidence only if required.** | ADR-0031. Do not silently infer bulk or mutate old revisions. |
| Neutral Material IR — **complete** | `backend/src/cmp/modules/modeling/domain/neutral_material.py`; `tests/unit/test_neutral_material.py`; Neutral API tests | Promote exact linear-viscoelastic selection into the typed family-neutral envelope and retain curve stages/provenance. | New bulk/TTS metadata may need additive schema support; current family remains non-production. | Reuse. **New: only if a concrete new field cannot be represented.** | No generic parameter map and no #196 payload. |
| Abaqus mapping — **complete for current subset** | `backend/src/cmp/modules/exporting/domain/reference_linear_viscoelasticity.py`; Abaqus golden fixture; unit/integration tests | Emit density, instantaneous elasticity and `*VISCOELASTIC, TIME=PRONY` for supported normalized terms. | Production qualification, temperature-shift export and new bulk cases are not established. | Reuse preflight/card pipeline. **New: target-specific extensions only after public-contract proof.** | Do not adopt Abaqus `NMAX`/`ERRTOL` as platform defaults. |
| OpenRadioss mapping — **complete, conditional** | ADR-0032; `tests/unit/test_neutral_material.py` asserts `/MAT/LAW1` + `/VISC/LPRONY`; current Neutral solver-card code | Export only shear-only, nearly-incompressible records with Form 2, deviatoric flag and explicit `I_smstr=10/12` acknowledgement. | Bulk relaxation and other Poisson/form combinations are unsupported; external property is not emitted here. | Reuse exact conditional mapping. **New: no unless solver contract changes.** | Never map this linear family to LAW62. #213/#214 are not prerequisites for the current mapping. |
| Holdout, uncertainty and identifiability — **missing/partial** | FR-CAL-006/007; current outputs expose BIC/nRMSE/residual but no production holdout/uncertainty result | Inspect fit residual and BIC only. | No calibration/holdout split, sensitivity/rank/correlation, confidence schema, warning policy or threshold authority. | **New: yes, after decision and reference set.** | Do not present a low nRMSE/BIC as production validity. |
| Joint time/frequency and shear/bulk fit — **missing** | Public solver theory supports these combinations; current engine implements separate shear time or shear DMA paths | Cannot jointly constrain one candidate with time and frequency, or characterize bulk. | Input compatibility, shared parameters, weights and common relaxation-time rules are undecided. | **New: separate bounded implementation unit.** | Must not be slipped into the first production engine PR. |
| Fit UX evidence depth — **partial** | #158 F-01–F-11 structure and current Workbench/decision components | Compare observed response/residual, terms, recommendation and selection; save/reload/retry. | No production bounds/uncertainty/holdout/TTS adequacy surface; long term list behavior needs future five-viewport evidence. | Reuse layout and state components. **New: additive UI only after API.** | #184 shared geometry policy. No new screen or third inspector. |

### 4.1 Document and implementation mismatch register

| Mismatch | Evidence and impact | Disposition |
| --- | --- | --- |
| #195 legacy premise versus main | Issue says polymer branch is future; capability map, guide, code, migrations and tests show bounded relaxation/DMA/TTS/Prony/promotion/export. | `PROPOSED_DECISION`: narrow the implementation issue; do not duplicate current work. Keep issue open for the bounded residual scope. |
| `material-model-ir.md` §17.3 versus later authority/code | §17.3 says generalized Maxwell OpenRadioss is unsupported because LAW62 requires Ogden, while the later family section, ADR-0032 and current tests support a separate conditional LAW1+LPRONY path. | Record a proposed follow-up documentation delta; do not edit the shared IR document in this PR. Implementation must follow ADR-0032/current tested behavior and still prohibit LAW62. |
| Current Workbench options versus production policy | Current React and processing registry contain candidate counts, normalization, tau bounds and evaluation limits for a bounded reference demo. | Label as `CONFIRMED_CURRENT` reference settings only. None becomes a production default through this packet. |
| Solver capabilities versus platform product range | Abaqus public help allows up to 13 terms when it performs calibration; OpenRadioss LPRONY documents up to 100 rows. Current platform IR accepts 1–10. | Solver maxima are interoperability facts, not product-policy evidence. Production term range remains `OPEN_DECISION`. |

## 5. Canonical input data contract

### 5.1 Exact input identity envelope

Every production Plan must serialize the following human-readable context and exact revision references. A missing exact reference is a validation error, not a request to resolve `latest`.

| Field | Contract |
| --- | --- |
| Material | stable Material identity plus exact immutable Material revision; displayed label/family and classification are snapshots, not lookup substitutes |
| Condition | exact Condition revision including temperature, humidity/environment where applicable, specimen orientation/mode and test conditions; absence is explicit |
| Test Data | one or more exact Test Data revisions, each with test method revision, raw artifact digest, channel metadata and source-unit text |
| Processing Output | optional exact immutable revision; when used it pins its Test Data revisions, Recipe/Batch or method evidence, transformations and output digest |
| Fit domain | explicit calibration and holdout intervals in original domain and canonical domain; observed-only versus extrapolated classification |
| Method | method key, semantic version, implementation build digest and independent reference-set version |
| Units/conventions | original text, normalized unit, canonical unit, frequency kind, log base, modulus convention, temperature scale and sign convention |

### 5.2 Approved input families

| Input family | Required channels and conditions | Canonical representation | Hidden behavior prohibited |
| --- | --- | --- | --- |
| Uniaxial stress relaxation | time, axial stress, held axial strain amplitude, matching engineering or true/logarithmic definitions, temperature, preconditioning and specimen orientation; a verified step or recorded ramp duration | immutable raw channels plus an explicit Processing Output deriving $E_R(t)=\sigma(t)/\epsilon_0$ only under the approved small-strain step assumption; stress/modulus in `Pa`, strain dimensionless | mixing engineering stress with true strain; treating $E_R$ as shear/bulk response; silently assuming constant Poisson ratio |
| Shear stress relaxation | time, shear stress, held shear strain amplitude and its measure, temperature, preconditioning, specimen/mode; a verified step or recorded ramp duration | immutable raw channels plus an explicit Processing Output deriving $G_R(t)=\tau(t)/\gamma_0$ where the approved small-strain step assumption holds; time in `s`, stress/modulus in `Pa`, strain as dimensionless ratio | treating stress as modulus; assuming strain amplitude; removing the loading ramp; converting engineering/true measures silently |
| Shear relaxation modulus | time, $G_R(t)$, temperature, strain amplitude/derivation evidence and mode | time in `s`, modulus in `Pa`; original unit/value preserved | inferring raw stress/strain that was not supplied; accepting negative or dimensionless modulus |
| Bulk relaxation | time, hydrostatic pressure and held volumetric strain, or an already-derived $K_R(t)$, with sign convention and temperature | $K_R(t)=-p(t)/\epsilon_{vol,0}$ under the packet sign convention, time in `s`, modulus in `Pa` | inferring bulk from shear, $E$, or a nearly-incompressible label; dropping the pressure/volume sign convention |
| DMA shear storage/loss | frequency value and kind, $G'(\omega)$, $G''(\omega)$, temperature, strain amplitude, deformation mode, sweep direction and preconditioning | angular frequency $\omega$ in `rad/s`; modulus in `Pa`; original frequency and unit retained | treating Hz as rad/s; deriving missing loss from storage; pooling temperatures without explicit shift/weight evidence |
| DMA loss factor | frequency, $\tan\delta$, and an absolute storage or loss modulus at the same points, plus the DMA conditions above | derive the missing absolute channel only as an explicit Processing Output using $\tan\delta=G''/G'$ and preserve the input/derived role | fitting loss factor alone as if it sets absolute modulus; silently replacing zero/invalid storage values |

`PROPOSED_DECISION` — The first production input slice should accept already-governed shear relaxation modulus and governed shear DMA storage/loss. Raw stress-to-modulus, bulk and loss-factor derivations should be separate channel/Processing contracts, not implicit Fit preprocessing.

### 5.3 Frequency, time, temperature, strain, and logarithm conventions

- Preserve original frequency value and unit (`Hz`, cycles/time, or `rad/s`) and frequency kind. Canonical angular frequency is $\omega=2\pi f$ for $f$ in `Hz`. The conversion and $2\pi$ factor are serialized evidence.
- Canonical time and relaxation time are seconds. Source `ms`, `min`, `h` or other approved units remain in source metadata and are converted through the versioned unit service.
- Canonical absolute temperature is kelvin. Celsius input is preserved and converted as $T_K=T_{^\circ C}+273.15$. Temperature differences in the WLF denominator are in kelvin and numerically equal to Celsius differences; the absolute Arrhenius calculation uses kelvin.
- Source strain amplitude preserves ratio versus percent, engineering versus true/logarithmic definition, and shear-strain convention. Canonical small-strain amplitude is dimensionless, but the source meaning is never discarded.
- `log10` means base 10 and `ln` means natural logarithm. Log-time interpolation and WLF use `log10` in the current bounded implementation. Arrhenius may be stored as `ln(a_T)` or explicitly converted to `log10(a_T)=ln(a_T)/ln(10)`; the representation is recorded.
- Zero time/frequency cannot enter a logarithm. A zero-time instantaneous observation may be retained as a separately classified limit datum; it is not silently nudged to a positive value.

### 5.4 Modulus and quantity conventions

The canonical linear family uses **instantaneous** $G_0$, $K_0$, $E_0$ and $\nu_0$ as the rate-independent base. The equilibrium or long-term values are $G_\infty$ and $K_\infty$. Every source and solver mapping states which convention it supplies.

For isotropic small-strain elasticity at a single consistent state,

$$G=\frac{E}{2(1+\nu)},\qquad K=\frac{E}{3(1-2\nu)},\qquad E=\frac{9KG}{3K+G},\qquad \nu=\frac{3K-2G}{2(3K+G)}.$$

These identities are not permission to infer a time-dependent missing modulus. A conversion from $E_R(t)$ to $G_R(t)$ or $K_R(t)$ requires an approved assumption about time-dependent Poisson ratio or an independently characterized second modulus. `OPEN_DECISION` — production support for relaxation Young's modulus and complex $E^*$ conversion is deferred until that assumption and its evidence are approved.

For a nearly incompressible record, $\nu_0$ close to $0.5$ makes $K_0$ highly sensitive to $\nu_0$. “Nearly incompressible” is an applicability classification, not bulk relaxation data. Current OpenRadioss preflight's $0.49\le\nu_0<0.5$ condition remains a solver-specific bounded rule and does not establish a general material threshold.

### 5.5 Instantaneous observation, preconditioning, and valid range

Each Test Data/Processing Output must carry or explicitly mark unavailable:

- loading waveform, ramp duration, hold quality and the first trustworthy time;
- temperature history and equilibrium/soak evidence;
- strain amplitude and evidence that response stayed in an approved linear-viscoelastic range;
- preconditioning cycles, sweep direction, dwell, sampling method and replicate identity;
- instrument resolution, missing-value mask, saturation/slip/compliance warnings and operator exclusions;
- original sample points, any resampling grid and the observed valid interval;
- whether response is stress, modulus, compliance, storage, loss or loss factor;
- calibration versus holdout assignment made before the fit Run.

Missing/NaN/infinite values are rejected or explicitly excluded with a reason before fitting. Outliers remain in the immutable source; candidate detection and adjudication are separate Processing evidence. Smoothing, averaging, shifting, resampling and compliance correction are never hidden inside Fit.

### 5.6 Creep disposition

`FACT_PUBLIC` — Abaqus 2024 accepts shear/bulk creep data and converts normalized compliance to relaxation through convolution before a nonlinear least-squares Prony fit. This proves solver capability, not numerical suitability for this product.

`PROPOSED_DECISION: defer` — Do not include creep automatically in the first #195 production slice. Compliance-to-modulus recovery is an inverse problem that can amplify sampling noise and depends on instantaneous compliance, quadrature and regularization choices. A later bounded issue may include creep only after it supplies:

1. an explicit compliance input contract and step-stress semantics;
2. an independently verified convolution/inversion oracle;
3. noise and regularization sensitivity cases;
4. separate raw, converted and fitted revisions;
5. an approved failure/warning policy.

Silent compliance-to-modulus conversion is `exclude` for #195.

## 6. Theory and mathematical contract

### 6.1 Symbols and units

| Symbol | Physical meaning | Unit / constraint |
| --- | --- | --- |
| $t$, $s$ | chronological time and integration variable | `s`, nonnegative |
| $t_r$, $\xi$ | isothermal reduced time and general reduced-time measure | `s`, nonnegative |
| $\gamma$, $\dot\gamma$ | small shear strain and strain rate | dimensionless, `1/s` |
| $\epsilon_{vol}$ | small volumetric strain under the declared sign convention | dimensionless |
| $\tau$ | shear stress response; not a relaxation-time symbol when un-subscripted | `Pa` |
| $p$ | hydrostatic pressure, positive in compression in this packet | `Pa` |
| $G_R(t)$, $K_R(t)$ | shear and bulk relaxation moduli | `Pa` |
| $G_0$, $K_0$ | instantaneous shear and bulk moduli | `Pa`, positive |
| $G_\infty$, $K_\infty$ | equilibrium/long-term shear and bulk moduli | `Pa`, positive for the supported solid family |
| $G_i$, $K_i$ | dimensional modulus of Maxwell branch $i$ | `Pa`, nonnegative |
| $g_i$, $k_i$ | normalized shear and bulk Prony coefficients | dimensionless, nonnegative |
| $\tau_i$ | relaxation time of branch $i$ | `s`, positive and strictly ordered canonically |
| $N$ | actual candidate term count after canonical zero-term handling | positive integer; production range is `OPEN_DECISION` |
| $f$, $\omega$ | cyclic and angular frequency | `Hz` and `rad/s` |
| $G'(\omega)$, $G''(\omega)$ | shear storage and loss moduli | `Pa`; loss is nonnegative for the supported passive model |
| $a_T$ | horizontal time-temperature shift factor relative to $T_{ref}$ | positive, dimensionless |
| $T$, $T_{ref}$ | absolute and reference temperature | `K` |
| $C_1$, $C_2$ | WLF parameters at the stated reference temperature | dimensionless and `K` |
| $E_a$, $R$ | Arrhenius activation energy and molar gas constant | `J/mol` and `J/(mol K)` |
| $y$, $\hat y$ | observed and predicted response for a declared channel | channel unit or declared transformed unit |
| $w_d$, $w_{dc}$, $q_{dcj}$ | dataset, channel and sample weights | dimensionless, nonnegative, explicitly normalized |
| $s_{dc}$ | residual scaling for dataset/channel | same unit as the output of $h_{dc}$; positive. It is `Pa` for an identity modulus transform and dimensionless for a dimensionless logarithmic transform. |
| $y_{ref,dc}$, $b_{dc}$ | positive dimensional reference and base for an optional logarithmic response transform | same unit as $y$ and dimensionless base with $b_{dc}>0$, $b_{dc}\ne1$ |
| $\Phi$, $\mathcal R$ | total objective and regularization functional | dimensionless under the declared residual convention |

The repeated use of the Greek letter tau in engineering literature is a known ambiguity. Serialized fields use distinct names such as `shear_stress_pa` and `relaxation_time_s`; no API or UI label may rely on a bare `tau`.

### 6.2 Linear hereditary response

`FACT_PUBLIC` — For isotropic small-strain linear viscoelasticity, the shear and volumetric responses are hereditary integrals:

$$\tau(t)=\int_0^t G_R(t-s)\,\dot\gamma(s)\,ds.$$

$$p(t)=-\int_0^t K_R(t-s)\,\dot\epsilon_{vol}(s)\,ds.$$

For an ideal held step shear strain $\gamma_0 H(t)$, the response after the step is $\tau(t)=\gamma_0G_R(t)$. For a held volumetric step, $p(t)=-\epsilon_{vol,0}K_R(t)$. A finite loading ramp is not an ideal step; either the measured relaxation modulus already accounts for it or the waveform belongs in a forward convolution. Fit must not discard the ramp and pretend the first measured point is $t=0$.

The supported model is linear in strain history: the relaxation kernel does not depend on strain amplitude inside the approved range. Evidence outside that range produces an applicability warning or rejection; it does not silently turn this into a nonlinear or #196 model.

### 6.3 Generalized Maxwell / Prony convention

The canonical dimensional and normalized shear forms are equivalent:

$$G_R(t)=G_\infty+\sum_{i=1}^{N}G_i e^{-t/\tau_i}=G_0\left(1-\sum_{i=1}^{N}g_i+\sum_{i=1}^{N}g_i e^{-t/\tau_i}\right).$$

$$G_i=G_0g_i,\qquad G_\infty=G_0\left(1-\sum_{i=1}^{N}g_i\right),\qquad G_0=G_\infty+\sum_{i=1}^{N}G_i.$$

The bulk form is:

$$K_R(t)=K_\infty+\sum_{i=1}^{N}K_i e^{-t/\tau_i}=K_0\left(1-\sum_{i=1}^{N}k_i+\sum_{i=1}^{N}k_i e^{-t/\tau_i}\right).$$

$$K_i=K_0k_i,\qquad K_\infty=K_0\left(1-\sum_{i=1}^{N}k_i\right),\qquad K_0=K_\infty+\sum_{i=1}^{N}K_i.$$

Thus $G_R(0)=G_0$, $K_R(0)=K_0$, $G_R(\infty)=G_\infty$, and $K_R(\infty)=K_\infty$. A record declaring a long-term base must be transformed explicitly before it enters the current instantaneous IR convention. Solver cards report the source convention and the transformation.

The canonical IR uses a strictly increasing union of relaxation times. If independently fitted shear and bulk branches have different time grids, create the sorted union and put an explicit zero coefficient in the absent component. Do not pair branches merely by array index. Zero coefficients may be retained for solver-row alignment in a projection, but `actual_term_count` and identifiability evidence state whether they are active parameters.

### 6.4 Frequency-domain response

For $\omega=2\pi f$, Fourier transformation of the canonical shear relaxation function gives:

$$G'(\omega)=G_\infty+\sum_{i=1}^{N}G_i\frac{(\omega\tau_i)^2}{1+(\omega\tau_i)^2}=G_0\left(1-\sum_{i=1}^{N}g_i+\sum_{i=1}^{N}g_i\frac{(\omega\tau_i)^2}{1+(\omega\tau_i)^2}\right).$$

$$G''(\omega)=\sum_{i=1}^{N}G_i\frac{\omega\tau_i}{1+(\omega\tau_i)^2}=G_0\sum_{i=1}^{N}g_i\frac{\omega\tau_i}{1+(\omega\tau_i)^2}.$$

The bulk storage/loss expressions replace $G$ and $g_i$ with $K$ and $k_i$. For a valid absolute pair with $G'>0$,

$$\tan\delta(\omega)=\frac{G''(\omega)}{G'(\omega)}.$$

Limits provide independent checks: $G'(0)=G_\infty$, $G'(\infty)=G_0$, and $G''$ tends to zero at both limits for finite positive branches. A reported negative loss modulus, negative coefficient or negative relaxation time conflicts with passivity in this supported model and is not repaired by absolute value.

### 6.5 Time-temperature superposition

For an isothermal observation at temperature $T$, this packet follows the current master-curve convention:

$$t_r=\frac{t}{a_T(T)},\qquad a_T(T_{ref})=1.$$

For a temperature history, the general reduced time is:

$$\xi(t)=\int_0^t\frac{ds}{a_T(T(s))}.$$

The Prony response uses $t_r$ for an isothermal shifted datum or $\xi$ for a variable-temperature history. The direction `time_divided_by_a_t` is serialized; a left/right plot shift alone is not adequate evidence.

The WLF form is:

$$\log_{10}a_T(T)=-\frac{C_1(T-T_{ref})}{C_2+(T-T_{ref})}.$$

The Arrhenius form in canonical kelvin is:

$$\ln a_T(T)=\frac{E_a}{R}\left(\frac{1}{T}-\frac{1}{T_{ref}}\right).$$

`FACT_PUBLIC` — WLF is grounded in Williams, Landel and Ferry's 1955 primary paper; Abaqus 2024 publishes WLF and Arrhenius shift definitions. `INFERENCE` — successful horizontal alignment does not prove thermorheological simplicity. Multi-phase polymers can require more than one shift process, so temperature-wise residual structure and holdout evidence are mandatory before a production applicability claim.

`OPEN_DECISION` — approved temperature interval, shift-law selection rule, manual-shift review, vertical shifting, and TTS adequacy criteria. The current reference WLF/Arrhenius bounds and starting values are not adopted.

### 6.6 Residual and objective contract

Every Plan declares a response transform $h_{dc}$ for dataset $d$ and channel $c$. No transform is implied by chart axes. An identity transform preserves the response unit. A logarithmic transform is dimensionless and must be serialized as:

$$h_{dc}(y)=\log_{b_{dc}}\left(\frac{y}{y_{ref,dc}}\right),\qquad y>0,\qquad y_{ref,dc}>0.$$

The Plan stores $b_{dc}$, $y_{ref,dc}$ and the reference unit; nonpositive observations or predictions are invalid for this transform. For observation $j$:

$$r_{dcj}=\sqrt{w_d w_{dc} q_{dcj}}\,\frac{h_{dc}(\hat y_{dcj})-h_{dc}(y_{dcj})}{s_{dc}}.$$

The Plan normalizes sample weights within each channel, channel weights within each included dataset, and dataset weights globally:

$$\sum_j q_{dcj}=1,\qquad \sum_c w_{dc}=1\ \text{for each included }d,\qquad \sum_d w_d=1.$$

The data objective and optional regularized objective are:

$$\Phi_{data}(\theta)=\sum_d\sum_c\sum_j r_{dcj}^2.$$

$$\Phi(\theta)=\Phi_{data}(\theta)+\lambda\mathcal R(\theta).$$

Because $s_{dc}$ has the output unit of $h_{dc}$, every $r_{dcj}$ and $\Phi$ is dimensionless. The Plan serializes all transform kinds, log bases/reference quantities, $s_{dc}$ values/units, weights, masks, calibration/holdout assignment, regularizer, $\lambda$, parameter transformation and bounds. “Equal weighting” must say whether it means equal dataset, equal channel, equal point, equal log-decade or equal temperature contribution.

Time-domain, frequency-domain and joint fits use the same objective envelope but distinct channel evaluators. Joint fitting is valid only when exact source evidence justifies shared $G_0$, $G_\infty$, branch parameters, reference temperature and deformation mode. A joint objective does not permit arbitrary concatenation of unrelated specimens or temperatures.

For comparable candidates with the same transformed observations, masks and likelihood convention, a reference information criterion may be computed as:

$$AIC=m\ln\left(\frac{RSS}{m}\right)+2p.$$

$$BIC=m\ln\left(\frac{RSS}{m}\right)+p\ln m.$$

Here $m$ is the number of scalar residual observations, $p$ is the number of fitted free parameters, and $RSS$ is the unregularized residual sum under the declared convention. Weighted or correlated observations can invalidate this simple interpretation. AIC/BIC values from different preprocessing, domains, transforms or weights are not comparable.

### 6.7 Parameter scaling, constraints, and passivity

The production optimizer interface receives a typed physical parameter vector and an explicit reversible optimization transform. The Run records both physical and transformed values. A reference implementation may use $\log\tau_i$ and logarithms of positive dimensional moduli to improve scaling, but the production transform and optimizer remain `OPEN_DECISION`.

Every accepted candidate satisfies:

$$G_0>0,\qquad K_0>0,\qquad G_i\ge 0,\qquad K_i\ge 0,\qquad \tau_i>0.$$

$$0\le g_i<1,\qquad 0\le k_i<1,\qquad \sum_i g_i<1,\qquad \sum_i k_i<1.$$

$$\tau_1<\tau_2<\cdots<\tau_N.$$

These conditions make $G_\infty$ and $K_\infty$ positive for the supported solid family and rule out negative branch dissipation. The exact numerical guard from unity, minimum time separation and zero-coefficient canonicalization are `OPEN_DECISION`; they cannot be copied from solver input limits without platform evidence.

Constraints must be enforced by the declared parameterization or optimizer, then revalidated in physical space. Post-fit clipping, sorting coefficients without preserving their paired times, taking absolute values or dropping failed terms changes the solution and is forbidden.

### 6.8 Term count, identifiability, noise, and regularization

More terms do not automatically mean more identifiable physics. A branch whose transition $\omega\tau_i\approx1$ or $t\approx\tau_i$ lies far outside the measured domain may trade off with $G_\infty$, $G_0$ or another branch. Nearly equal relaxation times produce correlated columns and non-unique parameter splits even when the predicted curve is accurate.

Every candidate therefore records at least:

- actual active parameter count and ordered relaxation times;
- calibration and holdout domains in time/frequency/temperature;
- residuals by dataset, channel, temperature and log-decade;
- optimizer termination, gradient/step information available from the selected interface, and active bounds;
- sensitivity/Jacobian rank or another approved identifiability diagnostic;
- parameter correlation or profile evidence when available;
- multistart spread and equivalent-response candidates when multistart is enabled;
- whether regularization contributes to the objective and its unregularized residual separately.

`FACT_PUBLIC` — Abaqus advises sufficient data relative to fitted parameters and relates a typical maximum useful term count to the measured log-time decades. `FACT_PUBLIC` — Fujikawa et al. demonstrate positive/smooth Prony identification from dynamic modulus using a regularized formulation. Neither is a platform default. They motivate warnings and reference cases; production rules, penalty form and thresholds remain `OPEN_DECISION`.

### 6.9 Calibration, holdout, and extrapolation

Calibration and holdout assignments are exact, immutable input evidence chosen before candidate evaluation. Holdout points never influence objective, initialization, term selection or stopping. The result reports calibration and holdout metrics separately with the same declared response transform.

The fitted applicability interval is the intersection of approved input coverage after explicit shifting, not the numerical interval over which a Prony formula can be evaluated. Predictions outside the observed/validated time, frequency, temperature or strain-amplitude range are marked extrapolated. No chart extension, solver-card export or successful convergence removes that warning.

Production quality thresholds for fit, holdout, identifiability, convergence and extrapolation are all `OPEN_DECISION`. Synthetic double-precision regression tolerances in Section 10 verify implementation arithmetic only and must never be surfaced as material-quality thresholds.

## 7. Calibration policy and unresolved decisions

The table gives a recommendation and one of the required disposition categories. No row authorizes a production default.

| Policy item | Evidence-based recommendation | Disposition |
| --- | --- | --- |
| Manual/automatic term count | Keep manual candidate counts and allow an automatic **recommendation** only from a serialized rule; engineer selection remains separate. | **구현 전에 승인 필요** |
| Supported term range | Preserve current 1–10 only for bounded reference compatibility. Decide the production range from identifiability/reference evidence, not Abaqus 13 or OpenRadioss 100 limits. | **구현 전에 승인 필요** |
| Initial values | Fixture cases may declare exact deterministic starts. Production generation algorithm/version and seed must be Plan evidence. | **reference fixture에만 고정 가능** |
| Parameter bounds | Require every production Plan to contain explicit physical bounds. Do not ship undocumented global bounds; approved profiles may follow later. | **제품 기본값 없이 사용자가 명시** pending approval of safe validation envelope |
| Linear versus logarithmic response scale | Serialize transform per channel and show its consequence. Do not infer from plot axis. | **제품 기본값 없이 사용자가 명시** |
| Time/frequency joint fit | Implement only after shared quantity/reference-temperature and weighting contracts pass independent mixed-domain cases. | **후속 단계로 연기** |
| Dataset/channel/temperature weighting | Serialize normalized hierarchy and zero-weight/exclusion reasons; first production runs require explicit choice. | **제품 기본값 없이 사용자가 명시** |
| Multistart | Keep deterministic seeded interface and preserve every attempt summary. Number, sampling method and stopping rule require evidence. | **구현 전에 승인 필요** |
| Regularization | Report data and penalty objectives separately. Select penalty and strength only after noisy/ill-conditioned reference cases. | **구현 전에 승인 필요**; first minimal slice may be unregularized and explicitly scoped |
| AIC/BIC or holdout term selection | Information criteria may rank comparable candidates; holdout is stronger external evidence. Neither makes the final selection. | **구현 전에 승인 필요** |
| Optimizer interface | Define typed evaluator, constraints, transform, seed, termination and attempt evidence before choosing an implementation. | **구현 전에 승인 필요** |
| Concrete optimizer/library | Do not infer MCalibration/Material Modeler internals. Assess supported open implementations in the numerical-engine unit. | **구현 전에 승인 필요** |
| Convergence and recovery | Terminal states are `succeeded`, `failed`, `cancelled` or an existing compatible set; failure preserves attempts and permits a new Plan/Run without mutation. Numeric thresholds remain open. | Lifecycle **구현 전에 승인 필요**; thresholds `OPEN_DECISION` |
| User override | Allow explicit Plan values within approved physical validation; record override source/reason and never silently repair invalid values. | **제품 기본값 없이 사용자가 명시** |
| Recommendation vs final selection | Recommendation is immutable derived evidence. Selection is a separate engineer action with reason and acknowledgements. | **구현 전에 승인 필요** as a preserved invariant, not a tunable default |
| Bulk fit | Do not infer bulk. Add only after canonical bulk input and independent shear/bulk reference cases exist. | **후속 단계로 연기** after #205/#206 channel work |
| Creep | No automatic compliance inversion in #195. | **범위 제외** |
| Production thresholds | Fit quality, holdout, convergence, identifiability, TTS and extrapolation thresholds require approved domain evidence. | **구현 전에 승인 필요** / `OPEN_DECISION` |

### 7.1 Required decision record before implementation

A first implementation unit may begin only after a decision record names:

1. first supported input slice and whether it is shear relaxation, shear DMA, or both;
2. production term candidate range and whether manual choice is mandatory;
3. objective transforms, scaling and weight-entry requirements;
4. optimizer interface, deterministic seed/multistart policy, bounds representation and convergence evidence;
5. calibration/holdout split and warning-only versus blocking validations;
6. TTS scope and adequacy evidence;
7. whether the existing common Processing Output is sufficient or needs an additive schema version;
8. exact solver targets to requalify.

The record may approve “no product default; user must specify” but must not leave a required runtime value implicit.

## 8. UX and state contract

### 8.1 Reuse the #158 common Fit structure

`PROPOSED_DECISION` — Do not design a new polymer screen. Extend the existing F-01–F-11 common Fit flow with typed polymer content:

| Existing Fit region | Polymer content and behavior |
| --- | --- |
| Source/context | Material, Condition, exact Test Data or Processing Output revision label; domain type; temperature/reference temperature; human-readable source status. UUIDs/digests live in Evidence. |
| Input-domain summary | relaxation/DMA, shear/bulk, time/frequency range, source/canonical units, strain amplitude, temperature count, calibration/holdout coverage and excluded points with reasons |
| Candidate/term setting | manual candidate counts or approved policy; explicit objective transform, weights, bounds, shift model and seed/multistart summary; full arrays in Advanced |
| Persistent response graph | observed calibration and holdout response, selected/recommended candidates and no hidden extrapolation; toggles preserve graph context across candidate changes |
| Residual view | residual by domain/channel/temperature with zero line, unit/transform and calibration versus holdout distinction; never replace response view entirely |
| Term parameter table | ordered term, $\tau_i$, dimensional $G_i/K_i$, normalized $g_i/k_i$, active bounds and boundary status; $G_0/G_\infty/K_0/K_\infty$ convention visible |
| Temperature-shift evidence | $T_{ref}$, manual/WLF/Arrhenius method, $a_T$ or log shift per temperature, shifted overlap and adequacy/holdout warnings |
| Domain/applicability | fitted and validated time/frequency/temperature/strain-amplitude ranges; extrapolated regions visually and textually distinguished |
| Recommendation | system-ranked candidate, serialized rule/version and concise evidence; no selected styling before engineer action |
| Selection | engineer choice, required reason, warning acknowledgements and exact server candidate identity; a different candidate may require a new Run if current server contract calculates one selected term count |
| Primary action | `Save fit & continue` creates an immutable selected-model revision only after server verification; it is not enabled by recommendation alone |

The graph remains dominant. A shallow ribbon/disclosure contains settings; the implementation must not add a third inspector or nested cards. Long technical values, hashes, Jacobian details, optimizer traces, bounds arrays and provenance digests belong in Advanced/Evidence.

### 8.2 User-visible states

| State | Visible contract | Preserved state / recovery |
| --- | --- | --- |
| No compatible input | Explain missing quantity/unit/condition and link back to Data/Process. | Existing selections are not discarded. |
| Ready to calculate | All required settings are explicit; unresolved required decisions block Run. | Source exact revisions and draft settings survive navigation within the Workbench session. |
| Calculating | Run identity/status and cancel behavior if supported; prior successful result remains readable. | Do not blank the persistent graph or mutate a prior Run. |
| Candidate result | Response/residual/parameters/domain/warnings and distinct recommendation. | Candidate evidence is bound to the terminal Run. |
| Selected but unsaved | Engineer selection/reason/ack are visibly distinct from recommendation. | Draft decision survives a transient save failure. |
| Saved | Exact immutable selected-model revision and next boundary are visible. | Reload reads the same canonical state. |
| Save failed | Explain retryability and whether server created anything; never claim saved. | Idempotency key prevents duplicate revision; local decision remains. |
| Stale upstream | Identify which exact upstream pointer changed and compare old/new labels. | Old Run/model remains immutable; restore old context or create a new Plan/Run. |
| Calculation failed | Typed cause, last valid input/settings, attempt summary and corrective affordance. | Failed Run remains Evidence; retry creates a new Run or declared new attempt, never rewrites it. |
| Unsupported export | Mapping report names the unsupported semantic and target. | Selected Neutral/model remains valid; no fallback solver law. |

### 8.3 Warnings and acknowledgements

Warnings must be actionable and tied to a consequence. Required categories are:

- input convention/derivation, including Hz-to-rad/s and stress-to-modulus evidence;
- non-monotone/negative/invalid physical response;
- active bounds, close/equal relaxation times and weak identifiability;
- calibration/holdout divergence and sparse log-domain coverage;
- thermorheological-simplicity or temperature-overlap concern;
- instantaneous/catalog modulus mismatch;
- extrapolation beyond fitted/validated domain;
- solver mapping approximation, unsupported bulk/TTS and external prerequisites.

An acknowledgement stores warning code/version, exact candidate/model revision, actor and reason/time. Acknowledgement does not change severity, response, parameters or source evidence. A blocking error cannot be acknowledged into success unless an approved rule explicitly classifies it as overridable.

### 8.4 Keyboard, screen reader, long lists, and viewport acceptance

Future UI implementation must satisfy:

- logical tab order from source → candidate settings → graph controls → candidate table → selection/reason → save;
- native labels and accessible names for every setting, table, disclosure and action;
- selected, recommended, stale, warning and saved states conveyed by text/semantics, not color alone;
- chart series and residual summaries available as accessible tables or concise text with exact units/domain;
- keyboard comparison of candidates without losing graph focus/context;
- long term lists use a bounded table region with sticky header or an approved equivalent, preserving the save action and graph; no horizontal clipping of term identity/value/unit;
- 1366×768 and 1440×900 keep source, dominant graph, candidate evidence and primary action reachable without overlapping fixed regions;
- 1920×1080, 2560×1440 and 3840×2160 use shared pane/table/plot/typography tokens so graph and evidence gain useful space without stretching prose or creating a one-sided work island;
- browser zoom is 100% for deterministic geometry evidence. Capture all five viewports and inspect original-resolution images plus 100%-pixel crops of header, navigator, settings/table controls and graph.

This packet contains no React/CSS/image change, so those captures are not performed now.

## 9. Persistence, API, and provenance plan

### 9.1 State model

The future contract may reuse existing aggregates, but it must expose these semantic roles without collapsing them:

| Role | Durability and minimum fields |
| --- | --- |
| Modeling Plan | Immutable once executed. Exact Material/Condition/Test Data/Processing Output revisions; input roles; method key/version/build; candidate term policy; parameterization; initial-value generator/version/seed; bounds; objective transforms/scales/weights; calibration/holdout masks; TTS settings; optimizer and convergence policy; reference-set version. |
| Run | Append-only execution under one Plan. Run/attempt identity, terminal status, timestamps/actors, environment/dependency lock, source and Plan digests, deterministic seed, termination evidence, warnings/errors and artifact manifest. |
| Attempt | Persist when multistart/retry is semantically part of one Run. Start vector, transformed/physical bounds, termination, objective components and candidate link. A correction that changes Plan semantics creates a new Plan/Run. |
| Candidate | Immutable evaluated physical parameter set with actual term count, response/residual artifact digests, per-domain metrics, active bounds, identifiability/uncertainty evidence, applicability and warnings. |
| Recommendation | Immutable derived result binding the complete comparable candidate set, rule key/version/settings and evidence. It may be absent. |
| Selection | Separate engineer event binding one exact Candidate, selection reason and warning acknowledgements. It never overwrites Recommendation. |
| Selected-model revision | Immutable domain revision produced by verified selection; exact Plan/Run/Candidate/Selection and upstream references, convention, parameters, applicability, provenance digest and `non_production`/release state as applicable. |
| Processing Output / IR / Neutral | Reuse current immutable promotion boundaries. Each new revision pins its concrete predecessor and carries additive evidence only when the current typed contract cannot represent it. |
| Solver preflight/card | Exact Neutral revision, target solver/version/unit profile, mapping method/version/report, approximation/unsupported statuses, acknowledgements, artifact checksum and immutable card revision. |

### 9.2 Preview and Candidate persistence

`PROPOSED_DECISION` — A parameter edit or chart preview that has not executed an auditable Plan is ephemeral client/server computation and need not be a permanent DB object. It must never look saved or selectable for promotion.

Every successfully evaluated candidate that participates in a terminal Run's comparison, recommendation or selection must remain reproducible. Persist its compact typed summary and canonical parameter/evidence digest with the Run. Large response, residual and attempt histories should be content-addressed artifacts, not row-per-point relational tables. A candidate that was never part of an executed Run need not be retained.

This preserves auditability without generalizing the current common Processing Output store into a generic candidate database. The implementation design must first compare:

1. extending common Processing Output artifacts;
2. adapting ADR-0022 Plan/Run/Attempt/Candidate lifecycle;
3. a bounded new polymer-specific Run aggregate.

The selected option requires a contract/migration compatibility packet before code. Similar names alone are not proof that legacy and Workbench stores should merge.

### 9.3 API behavior

The future API surface may map to existing routes, but it must provide these behaviors:

1. create/validate a Plan without executing it and return all normalized explicit settings;
2. execute a Plan idempotently and observe a Run/Attempt lifecycle;
3. list/read exact Candidates and response/residual artifacts from one Run;
4. read Recommendation separately;
5. submit a Selection with exact expected Candidate/Run digest, reason and acknowledgements;
6. save/promote only after the server verifies the selected Candidate was produced by that Run and exact inputs remain valid;
7. read the immutable selected-model revision deterministically after reload;
8. report upstream-current staleness without changing old revisions;
9. promote to existing IR/Neutral through explicit commands;
10. perform solver preflight before card creation and reject unsupported mappings.

Write commands use an idempotency key and expected revision/digest. A mismatch returns conflict/stale evidence; the server never rewrites the request to current input or recomputes with hidden defaults.

### 9.4 Canonical provenance digest

The selected result's canonical provenance manifest includes, in stable order:

- stable identities and exact revisions for Material, Condition, Test Data and Processing Output;
- raw/source artifact SHA-256 and every intermediate Processing artifact digest;
- method/contract/schema keys and versions plus implementation build/dependency lock;
- full normalized Plan, including frequency/log/modulus conventions;
- Run/Attempt terminal evidence and candidate-set digest;
- exact selected Candidate parameters, actual term count and curve/residual artifact digests;
- Recommendation and Selection as separate entries;
- warning/acknowledgement codes and applicability;
- promotion chain to selected-model/IR/Neutral and, separately, solver-card mapping report.

The digest is calculated server-side from canonical bytes. Reload compares stored canonical bytes/digest; it does not reserialize through a lossy client representation. Tamper or missing referenced revision blocks promotion/export.

### 9.5 Upstream invalidation

An upstream new revision performs no cascading mutation. It updates the owning stable aggregate's current revision and marks dependent **current pointers** stale through existing invalidation semantics. The old chain remains addressable by exact revision.

A stale Fit surface must show:

- which upstream stable identity changed;
- exact old and current revision labels;
- whether the old result is still reproducible/readable;
- “restore old exact context” and “start a new Plan from current revision” as distinct actions;
- that a previously generated card remains an immutable historical artifact and is not a card for the new upstream revision.

## 10. Independent numerical reference-set plan

### 10.1 Oracle rules

The implementation unit will add a versioned synthetic reference package, but this planning PR adds no fixture. The package must be generated by an independent script that does **not** import the production evaluator, optimizer, serializer or unit converter. Closed-form cases use high-precision arithmetic or a second, documented numerical implementation. Each case stores formula, input points, exact parameters, expected response, source code/version, canonical manifest and SHA-256.

Tolerance types are deliberately separated:

- **closed-form arithmetic tolerance**: fixture-specific absolute plus relative double-precision comparison against the high-precision oracle;
- **optimizer recovery tolerance**: fixture-specific response/objective and, only when identifiable, parameter recovery; it is not a material-quality threshold;
- **serialization tolerance**: exact canonical bytes/digest and exact discrete fields; no float rounding beyond the declared canonical representation;
- **classification tolerance**: exact warning/error/mapping code and boundary side;
- **production threshold**: absent until separately approved.

### 10.2 Reference matrix

| ID and case | Input generation and parameters | Expected response / independent oracle | Tolerance nature and failure meaning |
| --- | --- | --- | --- |
| R01 single-term exact recovery and transformed residual | $G_\infty=2$ MPa, $G_1=8$ MPa, $\tau_1=3$ s; logarithmically spaced $t$ including 0, 3, 6, 30 s. Residual subcase at 3 s uses observed 4.5 MPa, $h(y)=\log_{10}(y/(1\ \mathrm{MPa}))$, $s=1$ and unit weights. | $G_R(t)=2+8e^{-t/3}$ MPa; at those checks: 10, 4.9430355294, 3.0826822659, 2.0003631994 MPa. The residual subcase is $\log_{10}(4.9430355294/4.5)=0.0407812183$. Independent scalar exponential/logarithm. | Closed-form arithmetic, dimensionless transformed-residual arithmetic and identifiable parameter recovery. Failure means response convention, unit/reference/base, objective scaling or optimizer binding is wrong. |
| R02 multi-term time recovery | $G_\infty=1$ MPa; $(G_i,\tau_i)=(4,0.1),(3,10),(2,1000)$ in MPa/s over $10^{-3}$–$10^4$ s. | At $t=0,0.1,10,1000,10000$ s: 10, 7.4414672759, 4.0837379910, 1.7357588823, 1.0000907999 MPa. | Closed-form response; parameter recovery only with exact broad coverage. Failure can mean term ordering, equilibrium convention or lost branch. |
| R03 DMA storage/loss joint recovery | Use R02 parameters at frequencies including 0.001, 0.1, 1 and 100 Hz with $\omega=2\pi f$. | $(G',G'')$ MPa: (2.9623894859, 0.5007138002), (5.9416106352, 0.7191914923), (7.1314130316, 1.8499616750), (9.9989869688, 0.0641265035). Independent complex-response formula. | Closed-form channel response and joint identifiable recovery. Failure distinguishes storage/loss formula, channel order or frequency conversion. |
| R04 WLF shift recovery | $T_{ref}=293.15$ K, $C_1=8.5$, $C_2=120$ K; shift the R02 curve at 273.15, 293.15, 313.15, 333.15 K using $t_r=t/a_T$. | $(\log_{10}a_T,a_T)$: (1.7, 50.11872336), (0,1), (-1.2142857143,0.0610540230), (-2.125,0.0074989421). | Closed-form shifts and curve collapse; fixture-only parameter recovery. Failure means sign/direction/log base/reference-temperature error. |
| R05 Arrhenius shift recovery | $T_{ref}=293.15$ K, $E_a=60{,}000$ J/mol, $R=8.314462618$ J/(mol K), same temperatures and R02 curve. | $(\log_{10}a_T,a_T)$ approximately (0.7827809877,6.06430433), (0,1), (-0.6827929963,0.207590275), (-1.2836057439,0.052046827). | Closed-form shift; catches kelvin/Celsius, `ln`/`log10`, sign and energy-unit errors. |
| R06 shear/bulk convention | $G_0=10$ MPa, $g=(0.2,0.3)$ at 1/100 s; $K_0=100$ MPa, $k=0.1$ at 10 s; canonical union times 1/10/100 s. | $G_\infty=5$ MPa, $K_\infty=90$ MPa. At $t=10$ s, $G_R=7.714603054$ MPa and $K_R=93.67879441$ MPa. Missing-component union coefficients are explicit zero. | Closed-form and exact canonical term alignment. Failure means instantaneous/long-term or shear/bulk row mismatch. |
| R07 Hz to rad/s | Evaluate R03 twice: source A in Hz and source B in rad/s with every B value exactly $2\pi$ times A. | Canonical $\omega$, response arrays and model parameters are identical; provenance retains different originals and explicit conversion. | Arithmetic response equal within conversion tolerance, metadata/digest deliberately different. Failure means hidden or double $2\pi$. |
| R08 normalized-coefficient boundary | For a fixed positive $G_0$, test coefficient sums below 1, exactly 1 and above 1, plus one negative coefficient. | Below-bound case has positive $G_\infty$ and evaluates; at/above or negative cases return exact validation codes and create no promotable candidate. | Classification boundary, not a production margin. Failure means nonpositive equilibrium modulus or negative dissipation can pass. |
| R09 noisy identifiability loss | Add seeded zero-mean synthetic noise to R02 and include two near-equivalent term decompositions with close times. Store noise vector/seed. | Response recovery may remain good while Jacobian/correlation or multistart spread flags weak parameter identity; recommendation evidence includes warning. | Fixture-specific response distribution and exact warning presence; no production quality threshold. Failure means uncertainty is hidden or seed is not reproducible. |
| R10 sparse domain | Sample R02 only over a narrow fraction of one log decade, far from the 1000 s branch transition. | Long-time branch parameters are not claimed recovered; candidate carries sparse-domain/weak-identifiability warning and bounded applicability. | Exact diagnostic classification plus response arithmetic. Failure means unobserved times are presented as identified. |
| R11 invalid modulus/data | Include NaN/infinite value, nonpositive $G'$, negative $G''$, negative relaxation modulus and missing strain amplitude for raw-stress derivation as separate subcases. | Typed input errors before optimization; immutable source remains unchanged; no absolute-value or point-dropping repair. | Exact validation code/path. Failure means hidden cleaning or non-passive input acceptance. |
| R12 equal times and ordering | Provide two active terms with equal $\tau$, then a descending-order representation of a valid distinct pair. | Equal active times are rejected or explicitly canonicalized only under an approved zero-term rule; descending distinct pair is reordered with coefficient pairing preserved and canonical digest defined. | Exact classification/canonical fields. Failure means coefficient/time pairs become detached or non-identifiable duplicates pass silently. |
| R13 fit versus holdout | Generate R02, designate alternating log-decade blocks before Fit, perturb only holdout points in one block. | Objective and recommendation use calibration only; holdout metrics detect the perturbation separately; changing holdout values cannot change fitted parameters when initialization is fixed. | Parameter/response comparison plus exact domain lineage. Failure means holdout leaks into training or is not reported. |
| R14 extrapolation | Fit R02 only over 0.1–100 s and request display/preflight at $10^{-4}$ and $10^6$ s. | Formula may evaluate, but outside points are classified extrapolated and are excluded from validated applicability. | Exact domain classification. Failure means mathematical evaluability is mistaken for validation. |
| R15 tampered source digest | After a valid Run, alter one source byte or manifest digest in a controlled test copy. | Read/promotion detects digest mismatch, creates no selected-model revision and retains original valid evidence. | Exact checksum/conflict behavior. Failure means provenance can be forged or silently repaired. |
| R16 save/reload | Select an exact R03 Candidate, reason and warning acknowledgement; save and reload through persistence/API. | Canonical Plan/Run/Candidate/Recommendation/Selection/model bytes and digest match; response artifact checksum is unchanged. | Exact serialization/digest and float-bit/canonical-decimal contract. Failure means nondeterministic read-back or state collapse. |
| R17 upstream stale | Create a new revision of one pinned Test Data/Processing Output stable identity after R16. | Old model remains readable and byte-identical; current pointer is stale with old/new refs; recompute creates a new chain. | Exact revision and state transition. Failure means history mutation or `latest` rebinding. |
| R18 solver mapping preflight | Use R06 variants: Abaqus-valid; OpenRadioss shear-only $k_i=0$, $0.49\le\nu<0.5$ with acknowledgement; bulk-active; bad $\nu$; missing `I_smstr` acknowledgement. | Abaqus supported rows preserve normalized terms; only the exact ADR-0032 OpenRadioss case passes conditionally; others return named unsupported/prerequisite items; never LAW62. | Exact mapping statuses and golden text/checksum. Failure means silent approximation or wrong solver family. |
| R19 loss-factor derivation | Take R03 $G'$/$G''$, store $G'$ and $\tan\delta=G''/G'$ as source, derive $G''$ through an explicit Processing Output. | Derived $G''$ equals the R03 oracle, with source/derived roles and formula version in provenance. Loss factor alone is rejected. | Closed-form response plus exact lineage. Failure means dimensionless loss factor was treated as an absolute modulus. |
| R20 temperature holdout / TTS failure | Create one thermorheologically simple WLF dataset and one synthetic dataset whose two branches shift by different factors; hold out one temperature. | Simple case collapses/reconstructs holdout under the fixture rule; complex case retains systematic residual and an adequacy warning rather than forcing one good-looking master curve. | Fixture-specific residual pattern and exact warning; no production TTS threshold. Failure means invalid horizontal-shift assumption is hidden. |

### 10.3 Solver-oracle separation

Native card golden tests are not the only oracle. The implementation must independently:

1. evaluate the canonical IR response at selected time/frequency points;
2. parse emitted solver coefficients back into the documented solver convention;
3. evaluate that parsed convention with an independent test helper;
4. compare canonical and parsed responses within fixture arithmetic tolerance;
5. verify mapping report status, target/version/unit profile and unsupported cases.

This catches a card whose text is stable but whose modulus convention or $2\pi$ semantics are wrong.

## 11. Implementation decomposition and dependency plan

### 11.1 Dependency classification

| Dependency | Relationship to narrowed #195 | Minimum condition |
| --- | --- | --- |
| #184 global 4K/high-DPI | UI implementation dependency, not numerical-contract dependency | Shared layout/density policy is applied before #195 Fit UI captures; no page-specific workaround. |
| #205 common CAE unit / Unit Profile | **Required** for new canonical frequency/modulus/time/temperature channels and solver-unit round trip | Versioned unit conversion preserves source text/value and canonical value; Hz/rad/s and temperature cases pass. |
| #206 curve channel metadata/deviation | **Required** for typed relaxation/DMA/bulk/loss-factor semantics and chart/Fit agreement | Additive metadata identifies physical quantity, component, domain, source/canonical unit and uncertainty/deviation. |
| #209 governed DMA import | **Required** before governed DMA is called a production #195 input | Exact DMA Test Data revision with reviewed storage/loss/frequency/condition provenance and negative cases. #195 does not duplicate the importer. |
| #211 representative envelope / approved Fit input | **Conditional** | Required only when a representative/mean/envelope Processing Output is selected. Direct approved exact Test Data remains independently valid. Candidate lineage identifies which representation was used. |
| #213 governed solver-card Template | **Not a prerequisite** for current Abaqus/OpenRadioss generator requalification | Needed only if #195 output must use released Templates. Keep existing native generation intact. |
| #214 LS-DYNA MAT_024 / multi-unit / Template UI | **Outside #195** | #195 neither adds MAT_024 nor waits for it, except shared Unit Profile work already owned by #205. |
| #196 hyperelastic extension | **Mutually bounded, not a dependency** | Linear #195 payload never selects Ogden/LAW62 or finite-strain semantics. Shared shell components may be reused without sharing constitutive payloads. |

### 11.2 Recommended implementation issues

Do not implement this packet as one PR. The issue numbers below are placeholders to be created/approved by the product owner; this packet does not edit #117 or the central backlog.

| Unit | Bounded ownership | Prerequisites | Exit condition |
| --- | --- | --- | --- |
| #195-A engineering contract and independent reference set | Contract/schema proposal for symbols, input conventions, evaluator interface and R01–R20 fixtures/oracles; no production UI | This packet plus approved decisions for first input slice and physical constraints | Independent implementation reproduces closed-form cases; tamper manifest passes; no production default is smuggled into fixture constants. |
| #195-B canonical viscoelastic input adapters | Bind approved shear relaxation and governed DMA channels to #195 Plan; add only approved raw/bulk/loss-factor transformations | #205, #206, #209 for DMA; #195-A | Source/canonical units, frequency kind, condition and exact revisions round-trip; hidden-conversion negative tests pass. |
| #195-C backend numerical engine | Typed evaluator, objective, bounds/transform, deterministic attempts, candidate diagnostics and first approved term policy | #195-A and the relevant #195-B input slice | R01–R14/R19/R20 applicable cases pass against independent oracle; failure/recovery is observable; no auto-selection. |
| #195-D API, state and persistence | Plan/Run/Attempt/Candidate/Recommendation/Selection lifecycle or approved reuse, artifacts/digests, reload and invalidation | Contract decision from #195-A; engine interfaces from #195-C can be mocked initially | R15–R17 and authorization/idempotency/concurrency tests pass; old schemas/revisions remain readable. |
| #195-E common Fit UI extension | Add polymer settings/diagnostics/states to existing #158 structure | #184, #195-B/C/D stable API and UX decision | Primary journey through save/reload/stale/recovery; keyboard/screen-reader and five deterministic viewport evidence approved. |
| #195-F IR/Neutral promotion delta | Only fields/evidence not representable in current Processing Output/linear IR/Neutral | #195-C/D; contract-first gap proof | Exact selected revision promotes without parameter reinterpretation; legacy bounded records round-trip unchanged. If no gap, close this unit as no-code. |
| #195-G solver mapping requalification/delta | Independent response round-trip and only approved bulk/TTS mapping extensions for Abaqus/current conditional OpenRadioss | #195-A/F; public target docs; target decisions | R18 and target golden/negative/preflight pass; exact/transformed/approximated/unsupported status is truthful. If current mapping suffices, no new exporter code. |
| #195-H live acceptance | One realistic Data→Process→Fit→Review→Export flow plus focused lower-level regressions | #195-B–G; #160 review/release integration only if included in acceptance scope | Product acceptance trace, reload/stale/recovery, applicable Compose/DB/browser and five-viewport evidence; guide updated only after implementation. |

`CONFIRMED_CURRENT_WORKTREE` — The bounded backend unit now implements the approved governed shear-relaxation and shear-DMA input semantics, including fixed-frequency temperature-sweep DMA reduced by an explicit tabulated, WLF, or Arrhenius shift law before Prony calibration. It also provides fully serialized Plan policy, isolated calibration execution, Candidate/Recommendation/engineer Selection separation, immutable PostgreSQL persistence, exact-revision reload and upstream-stale rejection. Its independent Decimal oracle validates the equations and units. Repository-owned CC BY 4.0 DaRUS and Zenodo archives additionally exercise all 18 DMA/master-curve/shift-factor members and all 30 DMA/normalized-relaxation/Arrhenius/tensile members through manifest-driven source parsing and eligibility rejection; the DaRUS 1 Hz temperature slice is checked against the authors' published shift factors and master curve. No missing absolute modulus or static property is inferred: static-property-free public data is not promoted or exported, synthetic relaxation promotion retains `non_production=true`, and no frontend path is changed. #195-E and the browser/visual part of #195-H remain separate; commit, publication and merge are not implied by this worktree status.

### 11.3 Parallelism and recommended insertion

- #195-A can proceed after this planning packet and decision approval while #205/#206/#209 are implemented, because its synthetic source contract does not require production adapters.
- #195-B cannot declare governed DMA complete before #209. A shear-relaxation-only adapter subunit may proceed after #205/#206 if explicitly approved.
- #195-C engine core can use #195-A synthetic typed inputs in parallel with late #195-B work, but it cannot merge as a production route before input contract compatibility is proven.
- #195-D contract design can proceed with engine interfaces, while persistence migrations wait for the final typed schema.
- #195-E starts after #184 shared geometry and stable state/API contracts. #195-F/G start only when selected-model evidence is stable.
- #195-H is last and must not become a generic browser suite.

`PROPOSED_DECISION` — If #117/backlog sequencing is later approved, place #195-A after this packet/decision gate and place production route units after #209; a conservative contiguous insertion is after #211 and before #213. This is a proposal only. It does not change the current order, start #195, or make #213/#214 dependencies.

### 11.4 Migration and compatibility risks

| Risk | Required mitigation |
| --- | --- |
| Two overlapping persistence models | Compare common Processing Output and ADR-0022 lifecycle explicitly; choose one bounded adapter strategy. No generic union table or EAV. |
| Existing method/version semantics change | Add a new method/schema version for new objective or convention. Old bounded runs reproduce byte-for-byte. |
| Candidate payload size | Store large response/residual arrays as immutable artifacts with digest; never row-per-point. |
| New unit/channel metadata | Additive adapters for historical Test Data; absence is `unknown/not_characterized`, not fabricated. |
| Bulk introduction | Preserve `bulk_behavior=not_characterized` and zero $k_i$ semantics for old records. Do not reinterpret zero as measured. |
| Frequency convention | Preserve old `frequency_hz` method behavior/version; new canonical angular-frequency evidence cannot silently change old digests. |
| TTS evidence | Preserve current manual/WLF/Arrhenius Processing Outputs and version any adequacy/holdout additions. |
| Term-range change | Old 1–10 validation remains readable. A new production range requires versioned validation and solver preflight; no in-place widening assumption. |
| Export mapping | Existing golden outputs remain unchanged unless an explicitly versioned target mapping is selected. |

## 12. Proposed follow-up deltas

This planning PR deliberately does not modify shared requirements, ADRs, contracts, source catalog, user guides or backlog. The implementation owner should propose only the deltas proven necessary.

| Authority/file family | Proposed delta | Trigger |
| --- | --- | --- |
| `docs/requirements/requirements.md` | Clarify FR-MOD-P production input conventions, calibration/holdout/identifiability and recommendation/selection acceptance; avoid duplicating existing FR-CAL requirements. | #195-A decision identifies a genuine unexpressed requirement. |
| ADR | New production calibration-policy ADR covering optimizer interface, term policy, objective/weights, deterministic multistart, bounds, thresholds and TTS scope. ADR-0022 remains legacy bounded reference; ADR-0031/0032 remain promotion/mapping authority. | Before #195-C production implementation. |
| Dataset/processing/modeling contracts | Add versioned typed channel/convention/evidence fields and Plan/Run/Candidate schema only after reuse analysis. | #195-A/B/D contract-first work. |
| `docs/domain/material-model-ir.md` | Reconcile stale §17.3 “OpenRadioss unsupported” wording with later ADR-0032 conditional LAW1+LPRONY path, while retaining the LAW62 prohibition. | A shared-doc PR with conflict check, or the first relevant exporter/IR unit. |
| `docs/00-research/product-reference-source-catalog.json` | Add direct Abaqus 2024, OpenRadioss LPRONY, Ansys Material Calibration 2025 R2, WLF primary paper and standards metadata entries with limitations. | A separately owned source-catalog update or when a required documentation index owns it. |
| User guide | Describe only merged production behavior, decisions and current limitations; retain bounded-reference labels until then. | #195-E/H implementation merge, not this packet. |
| #117 and backlog | Add approved split issues and insertion only after product-owner sequencing decision. | Explicit owner approval; never as a side effect of this packet. |

## 13. Acceptance packet for future implementation

### 13.1 User and persistence acceptance

| Acceptance | Observable pass condition |
| --- | --- |
| Exact setup | UI/API identify exact Material, Condition, Test Data and optional Processing Output revisions; no `latest` resolution in a persisted Plan. |
| Input semantics | Relaxation/DMA quantity, original/canonical units, frequency kind, temperature, strain amplitude and modulus convention are readable and persisted. |
| Candidate calculation | Approved synthetic inputs reproduce the independent oracle and show response, residual, parameters, domains and warnings. |
| Recommendation/selection | Recommendation has rule evidence; engineer selection is a distinct event with reason/acknowledgement and may differ. |
| Immutable save | `Save fit & continue` server-verifies exact Candidate and creates one immutable selected-model revision idempotently. |
| Reload | All exact references, settings, results, decision and digests read back deterministically after a fresh session. |
| Upstream change | New upstream revision stales only current pointers; old model/evidence stays byte-identical and addressable. |
| Recovery | Failed calculation/save preserves inputs and successful evidence, gives a corrective action and does not create a false saved state. |
| Promotion/export | Exact selected model promotes through existing typed IR/Neutral; preflight truthfully reports target mapping and blocks unsupported cases. |

### 13.2 Negative acceptance

Implementation must reject or explicitly block:

- Hz/rad/s, Celsius/kelvin, `log10`/`ln`, instantaneous/long-term or stress/modulus ambiguity;
- missing exact revision, tampered digest, unauthorized source or stale expected revision;
- nonfinite/negative invalid inputs, nonpositive modulus, negative coefficient/time or invalid normalized sum;
- missing strain amplitude for raw stress conversion and loss factor without one absolute modulus channel;
- equal active relaxation times or coefficient/time pairing corruption;
- hidden smoothing, outlier deletion, extrapolation, creep inversion or bulk inference;
- holdout leakage, incomparable information-criterion ranking or unrecorded weighting;
- promotion of a client-substituted/non-server candidate;
- automatic selection of a recommendation;
- LAW62 mapping for linear generalized Maxwell or any unsupported solver fallback.

### 13.3 Technical acceptance

- Unit: analytical response, conversions, constraints, objective components, shift laws, identifiability classifications and canonical serialization.
- Contract: typed resources and OpenAPI runtime equality, semantic-version compatibility and negative schema cases.
- Migration: old records/golden bytes readable, new revisions immutable, downgrade/rollback boundary documented, no JSON/EAV shortcut for core fields.
- Integration: exact Test Data/Processing Output → Plan/Run/Candidate → Selection → model/IR/Neutral → preflight/card plus tamper/stale/retry.
- Browser: one primary journey, keyboard actions and essential error/recovery; focused lower-level tests own combinatorics.
- Visual: live five-viewport evidence at 100% browser zoom plus original images and 100%-pixel crops, after #184.
- Documentation: implemented guide/current status/contracts match the live behavior; no future tense presented as current.

### 13.4 Current planning-PR acceptance and N/A register

| Gate | This PR |
| --- | --- |
| Changed scope | Only `docs/planning/issue-195-polymer-viscoelastic-fit-plan.md` unless a mandatory checker proves otherwise. |
| Product/code behavior | Unchanged. |
| Compose / DB / migration | `N/A — planning-only documentation` |
| Browser / screenshot / five viewport | `N/A — planning-only documentation` |
| Public research | Direct source/version/check-date register in Section 14; no proprietary defaults inferred. |
| Independent review | Section 15 records findings and disposition; blocker prevents merge. |
| Required repository gates | `cmp-check-user-guide`, `docs-impact`, `git diff --check`, relevant documentation hook and manual `pre-publish`. |

## 14. Source and evidence register

All public links were checked on **2026-08-11**. A public product/solver capability is not automatically this platform's product policy.

| Evidence | Version/date | Type | Direct support and limitation |
| --- | --- | --- | --- |
| Current repository baseline: code/contracts/migrations/tests/docs listed in Section 4 | main `36e8312fa85253ad8fee88f63a3a4bf096d92a9c` | `CONFIRMED_CURRENT` | Establishes the implemented bounded reference and actual gaps. It does not establish production fitness. |
| [Simcenter Material Modeler](https://www.siemens.com/en-us/products/simcenter/materials-science-management/material-modeler/) | current Siemens page, checked 2026-08-11 | `FACT_PUBLIC`, official product page | Publicly describes test-data preparation, automated curve fitting, validation, viscoelastic capability and solver-card workflow. It does not expose proprietary optimizer, bounds or defaults. |
| [Altair Material Modeler release notes](https://help.altair.com/material_modeler/topics/material_modeler/whats_new/release_notes_amm_2025_r.htm) and [file load/save](https://help.altair.com/material_modeler/topics/material_modeler/ammp_file_import_export_t.htm) | 2025.0 help | `FACT_PUBLIC`, official help | Confirms polymer modeling workflow context and saving material/test/fitted state. It is not a schema or algorithm specification for this platform. |
| [MCalibration product page](https://www.ansys.com/products/structures/mcalibration) | current page, checked 2026-08-11 | `FACT_PUBLIC`, official product page | Confirms semi-automatic parameter extraction, viscoelastic calibration, dataset cleanup, virtual experiments and stability checks. No internal algorithm/default is inferred. |
| [Ansys Material Calibration Standalone Help](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v252/en/pdf/Ansys_Material_Calibration_Standalone_Help.pdf) | 2025 R2 | `FACT_PUBLIC`, official help | Publicly documents Prony shear/bulk orders, relaxation or storage/loss frequency inputs, user initial/bound entries, selectable algorithms and residual views. Product options/defaults are comparison evidence only. |
| [Abaqus Time Domain Viscoelasticity](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEMATRefMap/simamat-c-timevisco.htm) and [VISCOELASTIC keyword](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-viscoelastic.htm) | Abaqus 2024 | `FACT_PUBLIC`, official solver reference | Direct support for hereditary response, normalized Prony/instantaneous-long-term relations, relaxation/creep/frequency calibration, storage/loss formulas, WLF/Arrhenius and solver inputs. Abaqus `ERRTOL`/`NMAX` are not platform defaults. |
| [OpenRadioss `/VISC/LPRONY`](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/visc_lprony_starter_r.htm), [solid property TYPE14](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/prop_type14_solid_starter_r.htm), and [LAW1](https://2024.help.altair.com/2024/hwsolvers/rad/topics/solvers/rad/mat_law1_elast_starter_r.htm) | OpenRadioss 2025 help; LAW1 2024 page | `FACT_PUBLIC`, official solver reference | Supports LPRONY fields, Form 1/2, viscous flag, maximum rows and total-strain prerequisite; base law/property constraints require preflight. Solver maxima/default flags are not product Fit policy. |
| [Williams, Landel and Ferry](https://pubs.acs.org/doi/10.1021/ja01619a008) | JACS 77(14), 1955, DOI `10.1021/ja01619a008` | `FACT_PUBLIC`, primary paper | Primary source for WLF time-temperature shift behavior. Access to bibliographic/abstract scope does not define a universal platform parameter range. |
| [Fujikawa et al., Prony-series viscoelastic parameters](https://www.jstage.jst.go.jp/article/zairyosystem/25/0/25_65/_article/-char/en) | 2007, DOI `10.34401/zairyosystem.25.0_65` | `FACT_PUBLIC`, peer-reviewed primary paper | Supports positivity/smoothness and regularization as identification concerns from dynamic modulus. The paper's formulation/tuning is not adopted as a production default. |
| [Fesko and Tschoegl, thermorheologically complex materials](https://onlinelibrary.wiley.com/doi/pdf/10.1002/polc.5070350106) | 1971 | `FACT_PUBLIC`, peer-reviewed primary paper | Supports warning that one horizontal shift process may fail for thermorheologically complex multiphase systems. It motivates validation, not a platform threshold. |
| [ISO 6721-1:2019](https://www.iso.org/standard/73142.html) | 2019, confirmed current 2024 | `FACT_PUBLIC`, official metadata/scope | Dynamic mechanical properties of rigid plastics within a linear-viscoelastic region and deformation-mode comparability scope. Paid body text was not used. |
| [ASTM D4065-20](https://store.astm.org/d4065-20.html) | 2020 | `FACT_PUBLIC`, official metadata/scope | DMA storage/loss response versus temperature/frequency/time under linear-viscoelastic assumptions and reporting context. Paid body text was not used. |
| [ASTM E328-26](https://store.astm.org/e0328-26.html) | 2026 | `FACT_PUBLIC`, official metadata/scope | General stress-relaxation scope and note that plastics responsibility moved to Practice D2991. This packet makes no claim to possess or implement paid D2991 procedure text. |

### 14.1 Evidence-level conflict disposition

- Public solver formulas and the current canonical instantaneous convention agree on normalized Prony response. That convention is retained.
- Current code's DMA response agrees with the published generalized-Maxwell storage/loss equations, but current conversion/weight evidence is too implicit for production. The formula is reused; the contract is expanded.
- Public products show broad workflows and user-adjustable fitting, not their internal optimizers. This packet uses them only as workflow/gap evidence.
- Abaqus supports creep conversion, combined shear/bulk and a product-specific automatic term procedure. Current platform code does not. Creep is deferred; combined domains are split into later units; Abaqus defaults are not copied.
- OpenRadioss publishes broader raw row capacity than current platform terms. The current stricter bounded IR remains until a product decision and independent reference evidence approve a change.

## 15. Independent review record

The Main-authored draft was reviewed read-only by `/root/issue195_independent_audit`, an `independent_auditor_terra_high` that did not write the packet or Git state. The initial verdict was `CHANGES_REQUESTED`; Main corrected the one blocker and the same reviewer re-audited the correction as `APPROVE`.

| Review item | Finding | Main disposition / re-review |
| --- | --- | --- |
| Current implementation not replanned as new | Pass. Existing relaxation/DMA/TTS/Prony/selection/promotion/Neutral/Abaqus/conditional LAW1+LPRONY is correctly classified as bounded current capability. | No change. Narrow recommendation retained. |
| Equations and parameter conventions | Initial **blocker**: §6.1/§6.6 allowed a dimensionless log transform while defining residual scale in the untransformed response unit; log base/reference and weight normalization were ambiguous. | Corrected $s_{dc}$ to use the output unit of $h_{dc}$; added serialized $b_{dc}$ and positive dimensional $y_{ref,dc}$, nonpositive-input rejection, per-level normalized weights and the R01 transformed-residual oracle. Re-review: pass. |
| Time/frequency and instantaneous/equilibrium consistency | Pass after correction. Time/frequency equations, $2\pi$, normalized/dimensional terms, reduced-time direction and instantaneous/long-term limits are consistent. | No further change. |
| No hidden conversion or guessed production default | Pass. Current reference options are not promoted to production policy; every conversion is explicit. | Added an explicit uniaxial engineering/true stress-relaxation row while preserving the deferred $E_R$-to-shear/bulk decision. Re-review found no scope regression. |
| Independent reproducibility of reference matrix | Pass after correction. R01–R20 numerical values recompute; R01 now independently checks a dimensionless transformed residual. | No further change. Synthetic tolerances remain separate from production thresholds. |
| Recommendation versus engineer selection | Pass. Separate immutable Recommendation and engineer Selection/reason/acknowledgement are preserved. | No change. |
| Exact revision / immutable evidence | Pass. Exact input pins, immutable revisions, deterministic reload, digest tamper and current-pointer staleness are covered. | No change. |
| #196 boundary | Pass. Uniaxial addition remains small-strain and does not add hyperelastic/finite-strain semantics. | No change. |
| Implementation size/dependency | Pass. Units A–H are bounded; #184/#205/#206/#209/#211/#213/#214 relationships are distinguished. | No change. |
| Direct source support | Pass. Claims and limitations are supported without inferring proprietary defaults or paid standard body text. | No change. |
| Final verdict | **`APPROVE` — no blocker, major or minor finding remains.** | Any later substantive packet change or main update requires re-review before ready/merge. |
