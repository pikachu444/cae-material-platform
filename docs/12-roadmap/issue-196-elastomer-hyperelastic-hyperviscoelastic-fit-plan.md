# Issue #196 elastomer hyperelastic and hyper-viscoelastic Fit implementation and acceptance packet

## 1. Packet status and decision

| Field | Decision |
|---|---|
| Issue | [#196 modeling: elastomer hyperelastic and hyper-viscoelastic Fit expansion](https://github.com/pikachu444/cae-material-platform/issues/196) |
| Planning baseline | `origin/main` `7c796ac127312761d2816af6acaff133ff1c0b48`, including merged [#195 planning PR #229](https://github.com/pikachu444/cae-material-platform/pull/229) |
| Scope recommendation | **`narrow`**. The current product already has a bounded executable four-family, three-mode, holdout, Neutral and dual-export reference. #196 must deepen only the production engineering, evidence and state gaps; it must not recreate those paths. |
| Packet effect | Planning and future acceptance authority only. It changes no application, API, contract, migration, test, fixture, current guide, ADR or delivery order. |
| Implementation state after merge | #196 remains open and waiting. This packet does not approve any `OPEN_DECISION` or start implementation. |
| Current runtime gates | Compose, database, browser, screenshots and five-viewport execution are **N/A — planning-only documentation**. |

Evidence labels used throughout this packet are:

- `CONFIRMED_CURRENT`: directly verified in current source, tests, contract or a versioned official product/solver reference.
- `FACT_PUBLIC`: directly supported by a cited public primary or official source, without claiming current product behavior.
- `INFERENCE`: an explicitly identified derivation from stated equations or sources.
- `PROPOSED_DECISION`: a bounded design recommendation that still requires implementation authorization.
- `OPEN_DECISION`: a production policy that must be approved before its dependent implementation begins.

### 1.1 Executive conclusion

The old premise that main contains only a simple Ogden example is no longer true. `CONFIRMED_CURRENT`:

1. `hyperelastic_families.py` evaluates Neo-Hookean, Mooney--Rivlin, Yeoh and one-term Ogden for
   incompressible uniaxial, planar and equibiaxial tension using engineering strain and nominal stress.
2. The legacy one-term Ogden path persists every multistart attempt, holdout metrics, Jacobian
   rank/condition and covariance or an explicit not-estimable result.
3. The four-family path persists one best Candidate per family and response/residual Parquet diagnostics,
   then promotes one Candidate into immutable typed Neutral Material JSON with exact Plan, Run, Candidate,
   Dataset, baseline Prony and diagnostics pins.
4. Abaqus and OpenRadioss preflight, six-state mapping reports, exact report digests, immutable solver
   cards and bounded golden fixtures already exist.
5. The Modeling UI saves Plans, executes the comparison, displays response/residual results and can
   reload exact evidence, although the normal family path collapses selection and Neutral promotion.

The implementation issue remains valuable because the reference slice is deliberately tension-only,
incompressible, non-production and policy-bound. The narrowed residual is:

- explicit test-mode, stress/strain/force/area, sign, condition, cycle, unit and fit-domain evidence;
- independently derived finite-strain family and solver-convention reference sets;
- versioned, visible objective, weighting, parameter, multistart and failed-run evidence;
- diagnostics that separate optimizer, fit, identifiability, physical, mathematical, bounded-path,
  extrapolation and solver results;
- Recommendation, engineer Selection, immutable selected-model save and Neutral promotion as distinct
  states with deterministic reload and stale recovery;
- a truly optional #195-compatible Prony overlay and explicit instantaneous/equilibrium base semantics;
- requalification, rather than replacement, of current IR, Neutral and Abaqus/OpenRadioss exporters.

### 1.2 Production decisions intentionally not made

The following remain `OPEN_DECISION` and a planning merge does not approve them:

- production tensile/compression/volumetric standard, specimen geometry, conditioning, precycling,
  selected cycle, temperature and strain-rate policy;
- production default family, Yeoh/Ogden order, Ogden exponent policy and volumetric potential/order;
- optimizer implementation, parameter transform/scaling, initial values, bounds, seed and multistart;
- residual transform, dataset/mode/range/point-density weighting, regularization and ranking;
- holdout allocation, identifiability/uncertainty method and quality/convergence thresholds;
- stability algorithms, scan domains, tolerances, extrapolation targets and acceptance thresholds;
- Prony term range, shear-only versus shear+bulk, sequential versus joint fitting and temperature shift;
- solver target versions, LAW42/LAW69/LAW82 choice, element compatibility and any new mapping.

## 2. Authority, dependencies and bounded ownership

### 2.1 Authority read for this packet

This packet applies the active owner instruction, #196, parent #117 without editing it, #158 common Fit
state, merged #195, #184, #205, #206, #209, #211, #213 and #214; `FR-CAL-001~007` and
`FR-MOD-E-001~004`; ADR-0023 and ADR-0026; the current product capability map, official-product research,
source catalog, desktop engineering UI specification, fitting validation, Material Model IR, current
elastomer guide and product-work acceptance contract.

The repository backlog still places #184 at the current execution position. This packet recommends a
future split and insertion point only. It does not edit the backlog, change #117 order, close #196 or
authorize any implementation unit.

### 2.2 Owned and forbidden future scope

| Boundary | Narrowed #196 scope | Excluded or separate follow-up |
|---|---|---|
| Material response | isotropic finite-strain hyperelasticity; optional separable linear Prony overlay | Mullins damage, permanent set, constitutive hysteresis, anisotropy, foam, biological tissue, failure/damage |
| Test evidence | uniaxial tension/compression, planar tension/pure shear, equibiaxial, volumetric/compressibility; explicit metadata and selected cycle | simple shear unless separately approved; FE inverse/virtual specimen; confidential test data |
| Rate dependence | exact relaxation/rate evidence and #195-compatible optional Prony overlay | nonlinear viscoelasticity, rate-dependent plasticity, viscoplasticity |
| Models | typed Neo-Hookean, Mooney--Rivlin, Yeoh and Ogden extensions | family-independent plugin framework or generic parameter map |
| Selection | evidence-backed Recommendation plus explicit engineer Selection | automatic production model selection |
| Export | requalify existing Abaqus/OpenRadioss mappings for newly approved typed variants | all-solver generic mapping; solver-card template implementation |
| Current PR | one bounded planning packet | application/API/schema/migration/test/fixture/UI/current-guide changes |

### 2.3 Dependency classification

| Dependency | Relationship | Minimum condition |
|---|---|---|
| #195 polymer viscoelastic planning | **Satisfied shared contract dependency.** Reuse its normalized instantaneous Prony convention, canonical time union, explicit shear/bulk zeros, constraints and objective-evidence envelope. Do not copy it into a second Prony system. | PR #229 is in the baseline and its shared convention is cross-checked before final review. |
| #184 global high-DPI implementation | Future Fit UI dependency, not a numerical-contract dependency. | Shared layout/density policy is implemented before #196 live five-viewport evidence; no route-specific 4K workaround. |
| #205 CAE units/Unit Profile | Production input/output normalization dependency. | Stress, force, area, length, time, temperature and reciprocal-pressure quantities have versioned conversions and round-trip evidence. |
| #206 curve channel metadata | Production curve semantic dependency. | Typed x/y quantities, unit provenance, mode, direction and deviation metadata can be pinned without column-name guessing. |
| #209 DMA/FLD governed import | **Conditional.** | Needed only if DMA, rate sweep or temperature-shift evidence enters the approved Prony slice; not needed for rate-independent hyperelastic inputs. |
| #211 representative envelope | **Conditional.** | Required only when an approved representative Processing Output is selected. Direct exact Test Data remains independently valid. |
| #213 governed solver-card Template | Not a prerequisite for reusing current code-owned Abaqus/OpenRadioss exporters. | Becomes a dependency only if #196 later adopts governed templates. |
| #214 LS-DYNA | Not a #196 prerequisite. | Separate scope if LS-DYNA or its multi-unit Template UI is approved. |

`PROPOSED_DECISION` — place the production implementation after #211 and before #213 to minimize unit
and curve-contract rework, while allowing the engineering contract/reference-set unit to be prepared
earlier. This recommendation is recorded only here and does not change central delivery order.

## 3. Primary journey: Data → Process → Fit → Check/Review → Export

### 3.1 Setup and exact input

1. An engineer opens Modeling for an exact Material and Material State and chooses the elastomer branch.
2. In Data, the engineer selects exact Test Data revisions or approved Processing Output revisions. Each
   selected curve displays a human label and revision while its stable/revision identity, source digest
   and provenance remain available in Evidence.
3. Every member declares role (`calibration` or `holdout`), exact mode, loading direction and sign,
   x/y quantity measures, units, temperature, strain rate or time history, preconditioning, cycle choice
   and fit/holdout domain. No field is inferred from a filename or curve shape.
4. The UI distinguishes uniaxial tension, uniaxial compression, planar tension/pure shear,
   equibiaxial tension and volumetric/compressibility evidence. “Planar/pure shear” is never presented
   as simple shear, and “biaxial” must resolve to an exact subtype.
5. If Process converts raw force/displacement or another stress/strain measure, the engineer sees the
   assumptions and selects one immutable Processing Output revision. The original Test Data remains
   unchanged.

### 3.2 Fit actions and visible outcome

1. The engineer chooses explicit candidate families and an approved order/term configuration. No family
   or order is silently added because a commercial product happens to support it.
2. Fit domain, optional extrapolation target, residual transform, normalization scales, mode/member/range
   weights, parameter bounds and initial/multistart evidence are visible in the normal surface or
   bounded Advanced disclosure according to their decision consequence.
3. The server creates an immutable Plan, executes a Run and streams or returns terminal evidence.
   A completed Run shows every attempt needed for reproducibility rather than only the winning point.
4. Candidate comparison shows, per mode and domain, observed/predicted response, signed and normalized
   residuals, parameters with units and conventions, objective contributions, bound activity,
   convergence, identifiability/uncertainty, physical and numerical diagnostics, and applicability.
5. Fit and holdout data are visually distinct. Extrapolated response is visually distinct from both and
   never extends the claimed fitted range.

### 3.3 Check/Review and immutable save

1. A derived Recommendation may rank or decline to rank Candidates. It records the approved rule and
   evidence; it never selects on the engineer's behalf.
2. The engineer may choose the recommendation or another server Candidate. Selection records a reason
   and acknowledges each applicable warning identity.
3. `Save fit & continue` server-verifies exact Plan/Run/Candidate/Selection identities, source digests,
   current head expectations and acknowledgements, then creates one immutable selected-model revision.
4. Reload restores the exact inputs, Plan, terminal Run, Candidate results, Recommendation, Selection,
   warning acknowledgements and selected-model revision. A browser-local reconstruction is not accepted.
5. If an upstream current revision changes, the saved model and all evidence stay immutable while the
   current workspace becomes stale and identifies the changed source. Re-run creates new evidence.

### 3.4 Optional Prony, Neutral and solver-card boundary

1. After the hyperelastic selected model is saved, the engineer may explicitly choose no overlay or pin
   an exact reviewed Prony evidence revision compatible with Section 9.
2. The UI states whether the hyperelastic coefficients represent instantaneous or equilibrium response,
   which conversion was applied, the finite-strain separability assumption and the approved
   time/rate/temperature domain.
3. Neutral promotion is a separate action that consumes the exact selected-model revision and optional
   Prony evidence. It never treats a recommendation as a model.
4. Export consumes an exact Neutral revision, target/version and current preflight digest. The mapping
   report retains `exact`, `transformed`, `approximated`, `ignored`, `unsupported` and
   `not_applicable` separately.
5. Solver-card creation remains distinct from preview and requires any mapping acknowledgement. The card
   and bytes are immutable and do not imply external solver qualification.

### 3.5 Recovery and acceptance

- Calculation failure persists a failed Run with failure class, completed attempts and preserved inputs;
  retry produces a new Run.
- Save conflict, stale source or invalid acknowledgement leaves the reviewed Candidate visible and
  permits source refresh or retry without mutating it.
- Neutral or card failure leaves the selected-model revision intact and offers only the failed downstream
  retry.
- Success means the engineer can reload the exact selected model, reproduce the visible evidence and
  trace every solver mapping to one immutable source chain.

## 4. Current implementation and target gap matrix

| Capability and classification | Current files/tests | Current user result | Bounded limitation / production gap | Reuse and future work | Dependency / duplicate prohibition |
|---|---|---|---|---|---|
| Four public family equations — **partial** | `backend/src/cmp/modules/modeling/domain/hyperelastic_families.py`; `backend/tests/unit/test_hyperelastic_families.py` | Compare Neo-Hookean, Mooney--Rivlin, Yeoh and one-term Ogden on the same curves. | Incompressible, tension-only, engineering strain/nominal stress; hidden stress-scale initials/bounds; Ogden alpha positive 0.25–12; primary recovery data are generated by the same evaluator. | Reuse typed families and response path. **New:** explicit convention/config and independent oracle. | Do not build a generic family registry. |
| Multi-test inputs — **partial** | `reference_ogden_calibration.py::{OgdenTestMode,OgdenCalibrationMember,OgdenCalibrationCurve}`; `tests/integration/test_ogden_calibration_api.py`; `tests/integration/test_catalog_postgresql.py` | Pin 1–24 exact normalized Dataset revisions as uniaxial, planar or biaxial calibration/holdout members. | Entire Dataset is used; no per-member domain. Rejects compression and requires non-negative increasing tension stress/strain. No force/area, lateral strain, true/2PK stress, temperature, rate or cycle semantics. | Reuse exact member/source validation. **New:** typed mode/quantity/domain evidence. | #205/#206; no hidden column-name adapter. |
| Legacy one-term Ogden attempts — **complete for bounded reference** | `reference_ogden_calibration.py::calibrate_reference_ogden`; `backend/tests/unit/test_reference_ogden_calibration.py`; `tests/integration/test_ogden_calibration_api.py` | Preserve every start/Candidate, mode objective, rank/condition, covariance or explicit not-estimable state. | One term, incompressible and reference-only; no physical/extrapolation diagnostics. | Reuse lifecycle and diagnostic semantics after typed compatibility decision. | Do not discard or rewrite existing revisions. |
| Four-family comparison — **partial** | `fit_hyperelastic_families`; family unit tests | Return one best Candidate per family, response/residual Artifact, calibration/holdout nRMSE and warnings. | Other starts and failed attempts are lost; scientific-profile mode weights are ignored; no bound, rank, covariance, objective history or explicit `not_provided`. | Preserve current Candidates. **New:** versioned per-attempt evidence. | Do not present current “BEST FIT” label as approved recommendation. |
| Current stability result — **partial / misleading if generalized** | `fit_hyperelastic_families` and family Candidate persistence | Display `monotonic_on_fitted_domain` or `nonmonotonic`. | Only a 201-point nominal-stress monotonicity sample from strain 0 to the maximum of all supplied curves and modes. It is not global energy boundedness, convexity, polyconvexity, strong ellipticity, Drucker stability or solver stability. | Keep as a versioned bounded-path diagnostic. **New:** taxonomy/domain/status array. | Never collapse all checks into one stable flag. |
| Plan/Run persistence — **partial** | `application/ogden_calibration.py`; repository; migrations 054/069/070; PostgreSQL and API tests | Save exact Profile, State, baseline model, Dataset members, successful Run, Candidates and diagnostic Artifacts. | Plan evaluator still says one-term Ogden while execution also runs four families; failed execution creates no failed Run; environment evidence is one digest rather than full FR-CAL-003 fields. | Version existing typed resources additively. | No new generic calibration tables solely for symmetry. |
| Selection and selected model — **partial** | legacy `reference_ogden_candidate_selection.py`, ADR-0026, `tests/integration/test_ogden_candidate_promotion_api.py`; family `NeutralMaterialService.promote_family_candidate` | Legacy Ogden has a revisioned Selection; family path records a reason and directly creates Neutral JSON. | Four-family Recommendation, Selection, saved selected model and Neutral promotion are collapsed; no warning acknowledgement identity or expected-head CAS. | Reuse legacy evidence-chain invariants. **New:** typed family Selection/selected-model. | Client cannot submit substituted parameters. |
| Prony overlay — **partial** | `NeutralPronyOverlay`; `tests/unit/test_neutral_material.py`; `backend/tests/unit/test_reference_ogden_prony_export.py` | Preserve exact ordered terms; Abaqus overlay for four families; OpenRadioss only one-term Ogden LAW62. | Normal promotion requires a baseline and always copies 1–5 shear terms, so “optional” is not a normal choice. No joint identification, bulk or TTS. | Reuse #195 normalized convention and exact pins. **New:** explicit none/pinned choice and coupling evidence. | Do not infer bulk or create a second Prony contract. |
| Neutral promotion — **partial** | `neutral_material.py`; migration 071; `tests/unit/test_neutral_material.py`; `tests/integration/test_neutral_material_api.py` | Immutable typed JSON/IR with exact Plan/Run/Candidate/Dataset/Artifact/baseline pins. | No preceding family Selection; numerical-check pass can be based only on the monotonic flag despite other warnings. | Preserve canonical 1.0 bytes. Add a new version only for concrete new semantics. | No in-place widening. |
| Abaqus/OpenRadioss mapping — **complete for declared non-production matrix** | `neutral_hyperelastic.py`, `neutral_solver.py`, `backend/tests/unit/test_reference_ogden_prony_export.py`, `tests/integration/test_neutral_hyperelastic_solver_card_api.py` and current golden fixtures | Exact preflight digest, mapping report and card for current supported tuples; blocks unsupported overlay combinations. | No licensed-solver run; current family mappings use declared 2025/reference assumptions. | Reuse and requalify only approved additions. | Do not reimplement exporters or assume a new target supports the same names/conventions. |
| Fit UI, save/reload/stale — **partial** | `apps/web/src/reference-ogden-calibration-workbench.tsx` and `reference-ogden-calibration-workbench.test.tsx` | Save/revise Plan, execute, view response/residual, load exact Run by ID and create Neutral. | Not fully aligned to #158 F-01–F-11; no per-test domain, full parameter/uncertainty comparison, standalone save selection or explicit stale/save-failure flow. | Reuse #158 common Fit components after #184. | No React/CSS or screenshot changes in this planning PR. |

### 4.1 Confirmed documentation and implementation mismatches

| Mismatch | Evidence | Disposition |
|---|---|---|
| Stability enum | Contract allows `nonmonotonic_on_fitted_domain` while code, persistence and web types use `nonmonotonic`. | Proposed contract-first follow-up; do not change either in this PR. |
| Plan evaluator identity | Plan pins `one_term_incompressible_ogden_nominal` while the same execution produces all four family Candidates. | New version must state exact evaluator/family set; old Plan remains readable. |
| Family weighting | The scientific profile and guide imply mode weights govern comparison; only legacy Ogden uses them. Four-family comparison derives equal mode balancing plus member weight. | Expose and pin effective weighting; do not claim the old value applied. |
| Plan restore | The guide says opening a saved Plan restores its reviewed Run/diagnostics; the normal input loader restores members, while automatic Run discovery depends on an existing Neutral document or manual Run ID. | Future common Fit read-back contract; current guide correction only with implementation. |
| Parameter visibility | The guide says family parameters are displayed; the family rail currently renders family, rank label, calibration nRMSE and warnings. | Future Candidate evidence surface; no current-guide edit in planning. |

## 5. Test modes, quantities and normalization

### 5.1 Canonical mode and sign contract

`CONFIRMED_CURRENT` — the named nominal test measures and incompressible principal-stretch states
below agree with the current evaluator and the cited Abaqus public hyperelastic reference.

The canonical engineering axis is material 1 in homogeneous principal deformation unless a future
typed mode explicitly states otherwise. Tension and extension are positive. Compression enters with
$0<\lambda<1$, engineering strain $\epsilon_\mathrm{eng}<0$ and signed tensile-positive stress; a
compression-positive raw convention is preserved and explicitly transformed. Hydrostatic pressure $p$
is compression-positive, while $J-1$ is expansion-positive.

| Mode | Principal stretches for incompressible analytical response | Required evidence | Failure boundary |
|---|---|---|---|
| Uniaxial tension | $(\lambda,\lambda^{-1/2},\lambda^{-1/2})$, $\lambda>1$ | axial direction, original/current area as applicable, transverse traction-free assumption or measured lateral strain | “tension” without quantity/sign/area metadata |
| Uniaxial compression | same kinematic family with $0<\lambda<1$ | platen/contact procedure, friction/boundary metadata, sign, selected cycle | converting a compression-positive column without an explicit sign transform |
| Planar tension / pure shear | $(\lambda,1,\lambda^{-1})$ | constrained width direction, free thickness direction and geometry | labeling simple shear or assuming the constraint from curve shape |
| Equibiaxial | $(\lambda,\lambda,\lambda^{-2})$ | equal in-plane stretches/loads and thickness response or incompressible assumption | storing generic `biaxial` without subtype |
| Volumetric/compressibility | $\lambda_1=\lambda_2=\lambda_3=\lambda_V$, $J=\lambda_V^3$ for pure volumetric oracle | pressure-volume or equivalent hydrostatic data, pressure sign, $J$ or volume ratio, temperature | inferring bulk response from shear data, $E/\nu$ or “nearly incompressible” |

Planar tension/pure shear and simple shear are different boundary-value problems. Simple shear,
anisotropic directions and mixed loading require a separately approved typed evaluator.

### 5.2 Strain and stretch measures

For a principal stretch $\lambda=L/L_0$:

$$\epsilon_\mathrm{eng}=\lambda-1,\qquad \epsilon_\mathrm{log}=\ln\lambda.$$

Conversions among these three are lossless for finite positive $\lambda$ only when the same reference
length and direction are established. Zero/negative stretch, missing gauge length, changed reference
after preconditioning or an unspecified compression convention fails normalization.

### 5.3 Stress and force measures

The first Piola--Kirchhoff/nominal stress tensor, Cauchy stress and second Piola--Kirchhoff stress obey:

$$\mathbf P=\frac{\partial W}{\partial\mathbf F},\qquad \boldsymbol\sigma=J^{-1}\mathbf P\mathbf F^\mathsf T,\qquad \mathbf S=\mathbf F^{-1}\mathbf P.$$

For an aligned principal uniaxial component:

$$P_1=\frac{F_\mathrm{load}}{A_0},\qquad \sigma_1=\frac{F_\mathrm{load}}{A},\qquad \sigma_1=\frac{\lambda_1}{J}P_1,\qquad S_1=\frac{P_1}{\lambda_1}.$$

Force requires calibrated force units and an original area for nominal stress. True/Cauchy stress
requires current area, or an explicit homogeneous deformation and incompressibility/compressibility
assumption sufficient to derive it. Tensor conversion to/from second Piola--Kirchhoff stress requires
the deformation gradient, not only axial strain. Missing information blocks conversion; it is not
filled by a material-family default.

### 5.4 Raw and processed curve boundary

- Raw Asset and Test Data retain source bytes, original column text, original units, sign, machine
  channel, specimen, cycle and every point including outliers.
- Processing Output records source revisions, transform method/version, equations, assumptions, selected
  cycle, explicit exclusions/masks, units, digest and actor. It may create canonical stretch/nominal-stress
  channels but never rewrites raw data.
- A fit domain is a per-member closed interval in the declared x measure plus an explicit point-selection
  rule. A holdout member or domain is disjoint from the objective by construction.
- Preconditioning, hysteresis and cycle selection are evidence. The selected loading/unloading branch is
  explicit; unselected branches remain preserved and are not silently averaged or smoothed.
- Temperature, strain rate and time history are stored even for a rate-independent fit and define
  applicability. Mixing conditions requires an approved policy, not an automatic collapse.
- Exact Test Data/Processing Output revision and Artifact digest are pinned in the Plan; “latest” is
  forbidden.

## 6. Finite-strain theory and family equations

### 6.1 Kinematics and stress derivation

Let:

$$\mathbf F=\frac{\partial\mathbf x}{\partial\mathbf X},\qquad J=\det\mathbf F>0,\qquad \mathbf C=\mathbf F^\mathsf T\mathbf F,\qquad \mathbf B=\mathbf F\mathbf F^\mathsf T.$$

The principal stretches are the positive square roots of the eigenvalues of $\mathbf C$. Define:

$$\bar{\mathbf F}=J^{-1/3}\mathbf F,\qquad \bar\lambda_i=J^{-1/3}\lambda_i,\qquad \bar I_1=\sum_i\bar\lambda_i^2,\qquad \bar I_2=\sum_i\bar\lambda_i^{-2}.$$

The approved isotropic form is described as:

$$W(\mathbf F)=W_\mathrm{dev}(\bar I_1,\bar I_2,\bar\lambda_i)+W_\mathrm{vol}(J).$$

For incompressibility, $J=1$ is enforced with a Lagrange multiplier $p$:

$$\boldsymbol\sigma=-p\mathbf I+2W_1\mathbf B-2W_2\mathbf B^{-1},\qquad W_1=\frac{\partial W}{\partial I_1},\quad W_2=\frac{\partial W}{\partial I_2}.$$

The traction-free transverse equations determine $p$. For the three incompressible test modes, the
axial nominal responses are:

$$P_U=2(1-\lambda^{-3})(\lambda W_1+W_2),$$

$$P_P=2(\lambda-\lambda^{-3})(W_1+W_2),$$

$$P_B=2(\lambda-\lambda^{-5})(W_1+\lambda^2W_2).$$

`INFERENCE` — these follow by substituting each principal-stretch state and eliminating the
traction-free pressure. Compressible response must instead use
$\sigma_i=(\lambda_i/J)\partial W/\partial\lambda_i$ and solve the measured or free transverse
condition. The incompressible closed forms are invalid when $J\ne1$.

### 6.2 Neo-Hookean

`CONFIRMED_CURRENT` — the current/Abaqus-style isochoric convention is:

$$W_\mathrm{dev}=C_{10}(\bar I_1-3),\qquad G_0=2C_{10}.$$

$C_{10}$ has stress units. Current code supports one positive fitted $C_{10}$ and no volumetric
parameter. In the incompressible modes:

$$P_U=2C_{10}(\lambda-\lambda^{-2}),\qquad P_P=2C_{10}(\lambda-\lambda^{-3}),\qquad P_B=2C_{10}(\lambda-\lambda^{-5}).$$

Positive $C_{10}$ gives a positive initial shear modulus; it does not by itself qualify a solver,
boundary condition or extrapolation range.

### 6.3 Mooney--Rivlin

`CONFIRMED_CURRENT` — the current two-parameter form is:

$$W_\mathrm{dev}=C_{10}(\bar I_1-3)+C_{01}(\bar I_2-3),\qquad G_0=2(C_{10}+C_{01}).$$

$C_{10}$ and $C_{01}$ have stress units. The responses are:

$$P_U=2(1-\lambda^{-3})(\lambda C_{10}+C_{01}),$$

$$P_P=2(\lambda-\lambda^{-3})(C_{10}+C_{01}),$$

$$P_B=2(\lambda-\lambda^{-5})(C_{10}+\lambda^2C_{01}).$$

Planar data identify only the sum in this two-parameter form; multiple independent modes are needed
to separate the coefficients. A positive $C_{10}+C_{01}$ establishes only positive initial shear,
not global admissibility.

### 6.4 Yeoh

`CONFIRMED_CURRENT` — the current three-term form is:

$$W_\mathrm{dev}=\sum_{i=1}^{3}C_{i0}(\bar I_1-3)^i,\qquad G_0=2C_{10}.$$

Each $C_{i0}$ has stress units. With

$$Q=C_{10}+2C_{20}x+3C_{30}x^2,$$

use the Neo-Hookean mode factor with $C_{10}$ replaced by $Q$, where:

$$x_U=\lambda^2+2\lambda^{-1}-3,\qquad x_P=\lambda^2+1+\lambda^{-2}-3,\qquad x_B=2\lambda^2+\lambda^{-4}-3.$$

Higher-order terms are weakly informed by small-strain data and dominate extrapolation. Negative
$C_{20}$ may reproduce an S-shaped response but can introduce high-strain instability; parameter sign
alone is not a universal production rule. Yeoh order and bounds remain `OPEN_DECISION`.

### 6.5 Ogden convention matrix

`CONFIRMED_CURRENT` — the current family evaluator, current hyperelastic IR, Abaqus convention and
OpenRadioss LAW82 use:

$$W_\mathrm{dev}^{A}=\sum_{i=1}^{N}\frac{2\mu_i^A}{\alpha_i^2}\left(\sum_{a=1}^{3}\bar\lambda_a^{\alpha_i}-3\right),\qquad G_0=\sum_i\mu_i^A.$$

$\mu_i^A$ has stress units and $\alpha_i$ is dimensionless. Current code implements $N=1$,
$\mu>0$ and $0.25\le\alpha\le12$ as a bounded fixture policy. Those bounds are not production policy.
The test-mode responses are:

$$P_U=\sum_i\frac{2\mu_i^A}{\alpha_i}\left(\lambda^{\alpha_i-1}-\lambda^{-\alpha_i/2-1}\right),$$

$$P_P=\sum_i\frac{2\mu_i^A}{\alpha_i}\left(\lambda^{\alpha_i-1}-\lambda^{-\alpha_i-1}\right),$$

$$P_B=\sum_i\frac{2\mu_i^A}{\alpha_i}\left(\lambda^{\alpha_i-1}-\lambda^{-2\alpha_i-1}\right).$$

OpenRadioss LAW42의 명시적 계수 입력과 LAW69가 입력 곡선에서 내부 적합해 산출하는 Ogden
계수는 다음 에너지 convention을 사용한다:

$$W_\mathrm{dev}^{R}=\sum_i\frac{\mu_i^R}{\alpha_i}\left(\sum_a\bar\lambda_a^{\alpha_i}-3\right),\qquad G_0=\frac{1}{2}\sum_i\mu_i^R\alpha_i.$$

For unchanged $\alpha_i\ne0$, equality of energy and response requires:

$$\mu_i^R=\frac{2\mu_i^A}{\alpha_i},\qquad \mu_i^A=\frac{\alpha_i\mu_i^R}{2}.$$

| Representation | Coefficient before stretch sum | Initial shear | Mooney--Rivlin specialization |
|---|---:|---:|---|
| Current IR / Abaqus / LAW82 | $2\mu_i^A/\alpha_i^2$ | $\sum\mu_i^A$ | $(2C_{10},2)$ and $(2C_{01},-2)$ |
| LAW42 explicit input / LAW69 fitted-pair interpretation | $\mu_i^R/\alpha_i$ | $\frac12\sum\mu_i^R\alpha_i$ | $(2C_{10},2)$ and $(-2C_{01},-2)$ |

Neo-Hookean with $\alpha=2$ can appear to copy unchanged and conceal a broken general conversion.
`PROPOSED_DECISION` — every typed Ogden payload must identify the convention; a bare `mu_i` field
without it is invalid. Every exporter needs energy and mode-response round-trip fixtures.

`CONFIRMED_CURRENT` — LAW69의 카드 입력은 $(\mu_i^R,\alpha_i)$ 계수 배열이 아니라 단축 인장·압축
공학 응력–공학 변형률 곡선, pair 수와 fitting-control 항목이다. Starter가 nonlinear least-squares로
계수를 계산한다. 따라서 위 변환식은 LAW69가 산출한 계수를 해석·비교하는 oracle일 뿐, typed
Candidate 계수를 LAW69 카드로 직접 내보내거나 exact/transformed round-trip이라고 분류할 근거가
아니다. LAW69 경로를 추가하려면 곡선 생성 규칙, 허용 mode/domain/quantity, Starter 재적합과 그
오차를 별도 evidence로 고정하고 mapping status를 `approximated`로 표시해야 한다. 그 전에는 direct
LAW69 coefficient export를 `unsupported`로 차단한다.

### 6.6 Current bounded parameter policy and identification risk

Let $S=\max P^\mathrm{obs}$ over current calibration tension curves. The current family path hard-codes:

| Family | Initial | Bounds | Term/identification consequence |
|---|---|---|---|
| Neo-Hookean | $C_{10}=S/6$ | $S\times10^{-8}\le C_{10}\le10S$ | one fitted coefficient; one mode can determine it but cannot validate another mode |
| Mooney--Rivlin | $(C_{10},C_{01})=(S/12,S/12)$ | $S\times10^{-8}\le C_{10}\le10S$, $0\le C_{01}\le10S$ | planar response alone identifies only the sum; multiple modes are needed |
| Yeoh, three terms | $(S/6,0,0)$ | $S\times10^{-8}\le C_{10}\le10S$, $-10S\le C_{20},C_{30}\le10S$ | large-strain evidence is needed for higher terms; extrapolation is sensitive |
| Ogden, one term | $(\mu,\alpha)=(S/3,2)$ | $S\times10^{-8}\le\mu\le10S$, $0.25\le\alpha\le12$ | one positive exponent only; does not cover general multi-term/negative-exponent conventions |

`CONFIRMED_CURRENT` — these values come from `hyperelastic_families.py::_contract` and are not
stored as complete family policy evidence. They are `reference fixture only`. Production term counts,
initials, bounds and allowed exponent signs remain `OPEN_DECISION` and must be explicit Plan content.

### 6.7 Volumetric response and compressibility

`CONFIRMED_CURRENT` — one public Abaqus polynomial form is:

$$W_\mathrm{vol}=\sum_{i=1}^{N}\frac{1}{D_i}(J-1)^{2i},\qquad K_0=\frac{2}{D_1}.$$

$D_i$ has reciprocal-stress units. For pure volumetric deformation and compression-positive pressure:

$$p=-\frac{\partial W_\mathrm{vol}}{\partial J}=-\sum_i\frac{2i}{D_i}(J-1)^{2i-1}.$$

This is a solver convention and an independent reference candidate, not an approved platform default.
OpenRadioss laws may instead expose Poisson ratio, bulk parameters or law-specific forms. The Plan and
IR must name the chosen volumetric potential/convention and never translate only by parameter name.

The product must distinguish:

- `incompressible`: constrained $J=1$, no fitted volumetric data;
- `nearly_incompressible`: finite explicit bulk response, not a synonym for $D=0$;
- `compressible`: finite $W_\mathrm{vol}$ identified or supplied with its evidence and domain.

Production volumetric potential, number of $D_i$ terms, allowed $\nu$ or $K/G$, and whether the first
implementation slice is incompressible-only remain `OPEN_DECISION`.

## 7. Fitting objective, candidates and recovery

### 7.1 Reproducible objective envelope

For Dataset/member $d$, mode $m$ and point $n$, the stored objective must be reconstructable as:

$$r_{dmn}=\frac{\rho_d\!\left(P^\mathrm{pred}_{dmn},P^\mathrm{obs}_{dmn};\theta_d\right)}{s_d}\sqrt{w_mw_dw_{r,dmn}w_{p,dmn}},\qquad \Phi=\sum_{d,m,n}r_{dmn}^2.$$

The multiplication by the square-root weights applies to the transformed/scaled residual; the
serialized envelope identifies:

- $\rho_d$: signed linear difference, relative difference or logarithmic ratio and every denominator,
  floor/reference and logarithm base in $\theta_d$;
- $s_d$: explicit positive scale in the transformed residual's units; it has stress units for a linear
  stress difference and is dimensionless for a dimensionless relative/log residual;
- $w_m$, $w_d$: mode and member weights;
- $w_{r,dmn}$: loading-range weighting;
- $w_{p,dmn}$: point-density or quadrature weighting;
- the exact included points/domains and aggregation order.

Relative residual is undefined at zero observed stress without an approved denominator floor.
Logarithmic stress residual is invalid for zero or sign-changing stress unless an explicit signed
transform is approved. Such points are not silently dropped or shifted.

The current family path uses each curve maximum as $s_d$, divides member weight by curve count in the
mode and point count, and does not use scientific-profile mode weights. This remains a named legacy
reference behavior, not the production default.

### 7.2 Single-mode, joint fit and holdout

- Single-mode fitting is allowed only when the family is identifiable for the selected configuration or
  the Candidate carries a specific insufficiency warning. It cannot claim unobserved modes validated.
- Multi-mode fitting is one joint parameter optimization with separately visible objective contribution
  by mode, Dataset and domain.
- Holdout members/points never enter $\Phi$. Any use of holdout for ranking or model selection must be
  separately approved and serialized.
- Point-density handling is explicit so a densely sampled curve cannot dominate merely because it has
  more rows.
- Extrapolation targets are explicit stretches, modes and condition envelopes; absent targets produce
  `not_provided` rather than a global claim.

### 7.3 Parameter scaling, bounds and multistart

The typed Plan records physical parameters, units, reversible optimization transform, scales, lower and
upper bounds, initial seeds, random generator/seed, start-generation method, optimizer/method version,
stopping settings and maximum evaluations. Physical and transformed values remain distinguishable.

Each start produces an immutable Attempt with initial vector, terminal vector, objective, convergence
code/reason, evaluations, gradient/optimality evidence where available and failure classification.
Candidate selection from attempts is deterministic and records the rule. A failed attempt is evidence,
not discarded noise.

Current SciPy `least_squares(method="trf")`, PCG64, bounds and $10^{-10}$ tolerances are
`reference fixture only`. Production optimizer, transforms, starts, bounds and tolerances remain
`OPEN_DECISION`.

### 7.4 Identifiability and uncertainty

The minimum production contract provides:

- Jacobian rank, singular values or condition evidence on the scaled residual system when meaningful;
- parameter-at-bound and correlation/flat-direction evidence;
- covariance confidence intervals only when assumptions, rank and degrees of freedom permit;
- bootstrap or profile-likelihood evidence only under an approved bounded method;
- explicit `not_provided` or `not_estimable_*` instead of empty successful fields.

Parameter recovery is not required for an intentionally non-identifiable reference case; response and
the diagnostic classification are the oracle. Multi-start, low residual and narrow confidence intervals
are separate facts.

### 7.5 Recommendation, Selection and failure

Recommendation is immutable derived evidence containing the ranking policy/version, eligible Candidates,
metrics and warnings. It may return `no_recommendation`. Selection binds one exact server Candidate,
reason and warning acknowledgements; a user override is valid when the same hard constraints pass.

No objective minimum automatically creates a selected model. Optimizer failure, non-finite response,
invalid modulus, unsupported quantity conversion, insufficient evidence and persistence conflict have
different terminal error classes. Recovery creates a new Run or repeats only the failed downstream save;
it never edits a prior attempt or Candidate.

## 8. Physical, mathematical and numerical diagnostics

### 8.1 Concepts must remain separate

| Diagnostic | What it establishes | What it does not establish | Minimum stored evidence |
|---|---|---|---|
| Parameter finiteness/sign | Required parameters are finite and satisfy a declared family-specific algebraic condition. | Positive response, identifiability or stability. | convention, rule/version, offending parameter |
| Initial shear/bulk modulus | The tangent moduli at the reference state satisfy the declared positive-modulus rule. | Finite-strain response away from the reference state. | derived $G_0$, $K_0$, derivation and tolerance |
| Strain-energy boundedness | Energy remains finite/nondecreasing along one declared path or satisfies a proved family condition. | Global coercivity over all deformations unless a theorem and its assumptions are supplied. | path/theorem, parameter conditions and domain |
| Monotonic response | A predicted scalar stress does not decrease on a declared sampled test path. | Convexity, strong ellipticity or general three-dimensional stability. | mode, stretch grid, tolerance, minimum slope |
| Convexity/polyconvexity | An analytical or numerical condition for the declared energy and parameter subset. | Equivalence to every material-stability notion. Numerical convexity sampling is not a proof. | exact condition or `not_provided` |
| Strong ellipticity | Positive acoustic-tensor condition for declared states/directions, analytically or by a bounded scan. | Global stability outside those states/directions. | state/direction grid, minimum eigenvalue and method |
| Drucker stability | Positive incremental work or positive-definite tangent under the stated solver/path convention. | Polyconvexity or solver convergence. | definition, path, solver/version if applicable |
| Solver stability test | The named solver/version's own bounded diagnostic passed. | Solver independence, global mathematical validity or qualification of other elements/load paths. | solver/version/options/domain and raw result |
| Numerical evaluation | Energy/stress/tangent and optimizer arithmetic remained finite and converged. | Physical suitability or material quality. | failure class, point/state and numeric details |
| Fit-domain applicability | Declared checks passed inside the fitted domain. | Extrapolation. | exact fitted mode/range/condition |
| Extrapolation applicability | Declared checks passed on a separate target domain. | States or modes outside that target. | exact target and results |

Every diagnostic item uses `pass`, `fail`, `warning`, `not_provided` or
`not_applicable`; includes method/version, exact mode/state/domain, threshold source and evidence digest;
and never gets collapsed into a single `stable/unstable` flag.

### 8.2 Implementable checks by family

| Family/check | Deterministic platform check | Bounded numerical scan | Solver-dependent or deferred |
|---|---|---|---|
| All families | finite parameters; $J>0$; finite $W$, stress and tangent where implemented; positive declared $G_0$ and $K_0$ | mode response, energy, tangent and non-finite scan over fit and explicit extrapolation domains | global polyconvexity/strong ellipticity unless an approved theorem or acoustic-tensor method exists |
| Neo-Hookean | $C_{10}>0$; approved volumetric parameter gives $K_0>0$ | monotonic and tangent scan in declared modes | solver element/locking/stability remains target-specific |
| Mooney--Rivlin | $C_{10}+C_{01}>0$ for initial shear; finite coefficient/convention | mode/path response, energy and tangent; flag individual coefficient/bound activity | global admissibility is not inferred from $G_0>0$ |
| Yeoh | $C_{10}>0$ for initial shear; explicit higher coefficients/order | response/tangent and high-strain energy scan; negative higher coefficient is a diagnostic input, not automatic acceptance | analytical sufficient conditions only when their exact assumptions are implemented |
| Ogden | finite nonzero $\alpha_i$; $G_0=\sum\mu_i^A>0$ in current convention; exact convention conversion | multiple modes, tension/compression, energy, tangent and exponent overflow/underflow | termwise sign/global conditions differ by convention/law; solver-specific test remains separate |
| Volumetric | finite $D_i$ or named law parameters; $K_0>0$ under the selected convention | $J$ domain, pressure, tangent and singular/non-finite response | locking, element formulation and solver convergence |
| Prony | $\tau_i>0$, ordered canonical terms, nonnegative ratios/branches and positive long-term moduli | relaxation monotonicity/passivity over declared time range | finite-strain algorithm and supported law/element combination by solver |

`CONFIRMED_CURRENT` — Abaqus documents a Drucker-style bounded scan over uniaxial, equibiaxial and
planar tension/compression, commonly over $0.1\le\lambda\le10$ with increment 0.01. That is evidence
about the named Abaqus calibration diagnostic, not a platform default and not a global proof.

`PROPOSED_DECISION` — retain the existing 201-point monotonic result under a renamed/versioned
`bounded_mode_monotonicity` item with its actual range. Add stronger checks only as distinct evidence.
Thresholds, acoustic-tensor coverage and extrapolation domains remain `OPEN_DECISION`.

## 9. Hyper-viscoelastic Prony overlay

### 9.1 Shared #195 contract

`CONFIRMED_CURRENT` — the shared canonical representation remains the #195 normalized
instantaneous-modulus form and agrees with the cited Abaqus normalized Prony convention:

$$G_R(t)=G_\infty+\sum_iG_i e^{-t/\tau_i}=G_0\left(1-\sum_i g_i+\sum_i g_i e^{-t/\tau_i}\right),$$

$$K_R(t)=K_\infty+\sum_iK_i e^{-t/\tau_i}=K_0\left(1-\sum_i k_i+\sum_i k_i e^{-t/\tau_i}\right).$$

Thus:

$$G_i=G_0g_i,\quad G_\infty=G_0(1-\sum_i g_i),\qquad K_i=K_0k_i,\quad K_\infty=K_0(1-\sum_i k_i).$$

The reusable invariants are:

- $G_0,K_0>0$ when that branch is characterized; $g_i,k_i\ge0$; $\tau_i>0$;
- strictly increasing canonical union of relaxation times;
- an absent shear or bulk component at a union time is an explicit zero, not a missing inference;
- $\sum g_i<1$ and $\sum k_i<1$ for positive long-term moduli;
- original dimensional or normalized source convention, reference temperature, temperature-shift
  evidence and every transformation remain pinned;
- missing bulk relaxation remains `not_characterized`; it is never inferred from shear.

#196 references this section of #195 rather than defining a parallel Prony Plan/Run/Candidate family.

### 9.2 Instantaneous/equilibrium hyperelastic base

Abaqus normalized time-domain semantics use the instantaneous hyperelastic stiffness as the base. If
an exact equilibrium hyperelastic coefficient set is converted under the separable normalized model:

$$C_{ij}^{\infty}=C_{ij}^{0}(1-\sum g_i),\qquad \mu_j^{\infty}=\mu_j^{0}(1-\sum g_i),$$

$$D_j^{\infty}=\frac{D_j^{0}}{1-\sum k_i}.$$

Therefore an equilibrium-to-instantaneous conversion divides deviatoric coefficients by
$1-\sum g_i$ and multiplies the stated $D_i^\infty$ by $1-\sum k_i$, subject to the exact selected
volumetric convention. The source base, conversion direction, formulas, inputs and result digest are
mandatory evidence; they are never inferred from loading rate alone.

`CONFIRMED_CURRENT` — OpenRadioss LAW42/internal or external Prony forms use law-specific
long-term/dimensional semantics. The solver mapping must therefore expose:

$$G_i^R=g_iG_0,\qquad K_i^R=k_iK_0,\qquad \beta_i=1/\tau_i,$$

with $G_\infty,K_\infty$ as the base where the target law requires it. Identical parameter names do not
establish identical base semantics.

### 9.3 Finite-strain coupling assumption

The overlay is limited to isotropic, separable linear relaxation of a finite-strain hyperelastic base
over an approved strain/rate/temperature domain. Abaqus finite-strain viscoelasticity transports
historical deviatoric Kirchhoff stress into the current configuration; it is not equivalent to
multiplying the current hyperelastic Cauchy stress by $G_R(t)/G_0$.

The selected model records:

- constitutive coupling/method identifier and version;
- instantaneous or equilibrium hyperelastic base and conversion evidence;
- deviatoric and optional bulk kernels;
- reference temperature and optional approved shift law;
- modes, strain/rate/relaxation ranges and selected loading/hold histories;
- whether hyperelastic and Prony parameters were identified sequentially or jointly;
- validation/holdout evidence that is independent of the fitted data.

### 9.4 Sequential and joint identification

| Strategy | Benefit | Risk and required evidence | Disposition |
|---|---|---|---|
| Sequential | Reuses an exact reviewed hyperelastic selected model and #195 Prony result; separates parameter groups and is easier to diagnose. | Base may represent the wrong rate limit; hyperelastic/Prony scaling remains coupled; validation must show the chosen loading and relaxation ranges. | `PROPOSED_DECISION` for the first bounded integration slice, with no claim that it is a universal production default. |
| Joint | Can account for loading and relaxation history in one forward objective. | More local minima/non-identifiability, solver-specific finite-strain history, heavier objective and new uncertainty policy. | Separate implementation unit after explicit method/objective approval. |

Production sequential/joint policy, waveform handling, term count, bulk branch and temperature shift are
`OPEN_DECISION`.

### 9.5 Current and future solver boundary

| Target | Current bounded behavior | Future preflight requirement |
|---|---|---|
| Abaqus | Four current hyperelastic potentials may carry normalized Prony rows; one-term reference uses `MODULI=INSTANTANEOUS`. | Reconfirm target version, base semantics, volumetric terms, term alignment and element compatibility for every new versioned IR. |
| OpenRadioss current product | Only one-term Ogden plus exact baseline overlay maps to current LAW62; other family overlays are blocked. | Keep that matrix until official target-version evidence and independent energy/response fixtures qualify LAW42/LAW82 plus external `/VISC/PRONY`. LAW69 is curve-driven internal fitting, so direct coefficient export is `unsupported`; a separately approved curve-generation/Starter-refit path is `approximated`, never `exact` or merely `transformed`. LAW94 overlay remains unsupported without direct evidence. |

No public solver term maximum, automatic fitting rule, error tolerance or stability default becomes a
platform policy.

## 10. UX and state contract

### 10.1 Reuse the #158 common Fit structure

The future UI uses the existing Modeling shell and #158 F-01–F-11 state contract. It does not create a
third inspector column or a separate elastomer-only application.

| Surface | Normal decision content | Evidence/Advanced |
|---|---|---|
| Source context | selected Test Data/Processing Output labels, revisions, modes, roles and conditions | stable/revision IDs, digests, provenance and full channel metadata |
| Candidate rail | family, order, concise fit/holdout metric, Recommendation marker and actionable warning state | exact Candidate/Attempt IDs, objective components and method digest |
| Parameter controls | approved family-specific parameters, units, bounds and explicit order; normal fields only when user-adjustable | transformed values, all starts, bound activity and full convergence data |
| Dominant graph | mode selector; observed/predicted response; fit/holdout/extrapolation styling; persistent selection | exact point residual and source identity |
| Residual | signed and normalized residual with zero line and selected transform/scale | per-member/point weights and Artifact digest |
| Diagnostics | separate fit, identifiability, physical, stability, extrapolation and solver groups with domain | algorithms, grids, thresholds, raw values |
| Prony | explicit `No overlay` or exact reviewed overlay, base semantics and application range | ordered union, branch coefficients, temperature/shift and conversion evidence |
| Decision/save | Recommendation distinct from selected Candidate; reason; warnings; `Save fit & continue` | Selection and selected-model exact identities |

### 10.2 User-visible states

| State | Visible outcome | Persistence/recovery |
|---|---|---|
| Empty/unsupported source | Exact missing mode/quantity/metadata and corrective action. | No Plan or Run is created. |
| Draft Plan | Inputs, domains and policy are editable and downstream pointers are absent. | Saved draft revision may be reopened. |
| Calculating | Run identity and bounded progress/cancel state; old reviewed result remains distinguishable. | Refresh reads server state. |
| Succeeded | Candidate evidence, Recommendation or no-recommendation, warnings and applicability. | Exact Run/Candidates reload. |
| Failed/cancelled | Failure class, completed attempts and retry action. | Terminal Run remains searchable; retry creates a new Run. |
| Selected, unsaved | Candidate, reason and acknowledgements are present; Neutral/card remain unavailable. | Refresh restores only if Selection was committed. |
| Saved selected model | Immutable selected-model identity and continue action. | Exact read-back; idempotent retry returns the same result. |
| Stale | Changed upstream label/revision and affected downstream pointers. | Historical evidence remains; refresh/re-run creates new evidence. |
| Neutral/card failure | Saved model remains intact; failed downstream action is named. | Retry only the Neutral or card action. |

### 10.3 Accessibility and responsive acceptance

- Candidate selection, mode selection, fit/holdout legend, diagnostics, warning acknowledgement and save
  are keyboard reachable with visible focus and deterministic order.
- Screen-reader names include family, mode, role, domain and state. Color is never the only distinction
  among fit, holdout, extrapolation, pass, warning and fail.
- Long Ogden/Prony parameter lists use a bounded scroll/disclosure while the selected result and save
  action remain reachable. No horizontal clipping hides units, signs or bounds.
- Small viewports keep source/controls compact and the graph dominant. Wide viewports allow graphs,
  tables and native previews to grow while prose/forms retain readable bounds.
- Future implementation captures and opens original evidence at 1366×768, 1440×900, 1920×1080,
  2560×1440 and 3840×2160 at browser zoom 100%, including normal, warning, failed, stale and long-list
  states. Current planning makes no screenshot or CSS change.

## 11. Persistence, API and provenance plan

### 11.1 Typed state model

| Resource | Immutable/versioned content |
|---|---|
| Input reference | exact Dataset/Test Data or Processing Output stable/revision IDs, Artifact digest, mode, role, quantities, units, sign, conditions, selected cycle and domain |
| Plan | typed family set/order/convention, source members, evaluator/method versions, objective transform/scales/weights, constraints, parameter transform/bounds/starts/seed, fit/holdout/extrapolation domains |
| Run | Plan/source digests, terminal status, timestamps/actors, source commit, dependency lock, package/plugin/container digests, resource limits, failure receipt and Artifact manifest |
| Attempt | family/config, initial and terminal physical/transformed vectors, objective/convergence history boundary, evaluations, termination/failure and diagnostics summary |
| Candidate | exact Attempt or deterministic derivation, parameters/convention/units, response/residual Artifact digests, per-domain metrics, bound/identifiability/uncertainty/stability/applicability evidence |
| Recommendation | policy/version, eligible Candidates, ranking inputs/result or `no_recommendation` |
| Selection | exact Candidate/Run, engineer reason, warning acknowledgement identities, actor/time and expected current head |
| Selected-model revision | exact source/Plan/Run/Candidate/Recommendation/Selection pins, family parameters, convention, applicability and provenance digest |
| Optional Prony evidence | explicit none or exact #195-compatible source revision, base/coupling/conversion, terms and application range |
| IR/Neutral | typed versioned selected family; optional exact Prony overlay; no generic parameter bag |
| Solver preflight/card | exact Neutral revision, target/version, mapping states, acknowledgement identity, report/card byte digests |

Large response, residual, convergence and scan arrays remain immutable Artifacts with schema and digest;
they are never stored row-per-point in generic tables.

### 11.2 API behavior

Future protected APIs must:

1. create/revise a Plan with exact-source and expected-head checks;
2. execute idempotently under one request key and return a persistent Run even on calculation failure;
3. list/read all Attempts and Candidates for an exact Run and fetch typed diagnostic Artifacts;
4. read a Recommendation separately from Candidates;
5. create a Selection only from an exact server Candidate and explicit warning acknowledgements;
6. save an immutable selected-model revision only after revalidating exact source/Run/Candidate/Selection;
7. promote Neutral separately, with explicit no-overlay or exact Prony evidence;
8. return stale/conflict/not-found/invalid-evidence/unsupported distinctly and enforce organization/project
   authorization at service and database levels;
9. keep legacy Plan/Run/Candidate/Selection/Neutral revisions byte-readable.

Family configuration remains a typed discriminated union: Neo-Hookean, Mooney--Rivlin, Yeoh and Ogden
each own their parameter/order/convention fields. A generic family-independent EAV or opaque parameter
map is forbidden.

### 11.3 Provenance digest

The canonical evidence digest includes, in a deterministic order:

- exact Material/State, Dataset/Test Data/Processing Output and Artifact identities/digests;
- mode, role, quantity, unit, sign, conditions, selected cycle and domains;
- family/order, strain-energy and volumetric convention versions;
- objective transform/scales/weights, constraints, parameter transforms/bounds/starts/seed;
- source commit, dependency lock, package/plugin/container and method digests;
- all Attempt terminal records, selected Candidate and diagnostic Artifact digests;
- Recommendation and Selection as distinct entries, including reason and acknowledgements;
- selected-model/optional-Prony/IR/Neutral identities and solver preflight report where applicable.

Changing any item creates new downstream evidence. A stable identity may advance to a new immutable
revision, but prior revisions, raw bytes, released Artifacts and solver cards never mutate.

### 11.4 Migration and backward compatibility

- Do not widen the ADR-0023 one-term, 1–5 shear-Prony reference schema in place. A production-capable
  typed IR requires a new schema/version decision.
- Preserve current enum values and canonical bytes. Where the stability enum mismatch is corrected,
  an adapter must read both old representations and emit the version-appropriate value.
- Existing successful Runs remain readable even if a new Run version adds failed terminal states and
  expanded environment evidence.
- New Selection/selected-model records reference existing Candidates rather than rewriting them.
- Response/history/scan payload size is bounded and artifact-backed; migrations do not create
  row-per-point storage.
- Concurrent save/promotion uses expected-head/CAS and idempotency. A conflict never overwrites another
  revision or acknowledgement.

## 12. Independent numerical reference-set plan

### 12.1 Oracle and tolerance rules

- Production family evaluators, fitting code and solver exporters must not generate their own expected
  values. Closed-form equations, high-precision scalar arithmetic or a separately implemented reference
  evaluator produce the oracle.
- Synthetic values use MPa and seconds in the source table, then verify explicit conversion to canonical
  Pa and seconds. They are non-production and contain no confidential data.
- Closed-form point checks use combined relative and near-zero absolute tolerances appropriate to
  double precision; convention and digest round-trips use exact values where algebra/serialization permits.
- Noiseless identifiable recovery checks both parameters and response. Noisy or non-identifiable cases
  check response, objective ordering and diagnostic status rather than forcing false parameter equality.
- Synthetic regression tolerance verifies arithmetic/reproducibility only. It is never reused as a real
  material fit, stability or release threshold.

### 12.2 Reference matrix

| ID and case | Input/generation | Expected response / independent oracle | Tolerance nature and failure meaning |
|---|---|---|---|
| H01 Neo-Hookean uniaxial analytical | $C_{10}=0.5$ MPa; $\lambda=0.8,1.0,1.25$; $P=2C_{10}(\lambda-\lambda^{-2})$. | $P(0.8)=-0.7625$ MPa, $P(1)=0$, $P(1.25)=0.61$ MPa. | Closed-form float tolerance. Failure means strain, sign, nominal stress or coefficient convention is wrong. |
| H02 Mooney--Rivlin multi-mode recovery | $C_{10}=0.3$, $C_{01}=0.2$ MPa; noiseless U/P/B grids over $\lambda=1.0..1.5$. | At $\lambda=1.5$: U $0.9148148148$, P $1.2037037037$, B $2.0524691358$ MPa; joint fit recovers the identifiable pair. | Closed-form response plus condition-aware parameter tolerance. Failure means mode equation, aggregation or binding is wrong. |
| H03 Yeoh large strain | $(C_{10},C_{20},C_{30})=(0.4,0.05,0.01)$ MPa; uniaxial $\lambda=1..2$. | At $\lambda=2$, $x=2$, $Q=0.72$ MPa and $P=2.52$ MPa. | Closed-form response. Failure means invariant/power/order implementation is wrong. |
| H04 Ogden convention conversion | Abaqus/LAW82 $(\mu^A,\alpha)=((0.6,1.3),(0.4,-2.2))$ MPa. | LAW42 explicit-input / LAW69 fitted-pair convention $\mu^R=(0.9230769231,-0.3636363636)$ MPa; uniaxial $P(1.4)=0.7434847676$ MPa in both equations. | Energy and three-mode stress round-trip for coefficient conventions only. It does not qualify direct LAW69 export. Failure means a coefficient was copied by name/sign or a solver input boundary was lost. |
| H05 joint U/P/B fitting | Generate three modes from H02 on equal stretch grids; explicit equal-mode fixture weights. | One parameter set reproduces all modes; each mode objective and effective weight are reconstructable. | Response/objective equality. Failure means one mode or weighting was omitted. |
| H06 volumetric/compressibility | Abaqus-reference $D_1=0.02$ MPa$^{-1}$, $J=0.98,1,1.02$. | $K_0=100$ MPa and compression-positive $p=2,0,-2$ MPa. | Closed-form pressure/tangent and unit check. Failure means sign, $J$ or reciprocal-pressure convention is wrong. |
| H07 holdout mode | Fit H02 U/P only; keep B entirely out of the objective. | B residual is reported as holdout and objective contribution is exactly absent. | Exact membership/aggregation. Failure means leakage. |
| H08 noisy data | Add PCG64 seed 196 Gaussian noise with $\sigma=1\%$ of each mode's stated scale to H02. | Seeded bytes/objective reproduce; prediction remains compared with noiseless oracle, while exact parameters are not required. | Deterministic bytes plus response envelope. Failure means hidden seed/normalization or false recovery claim. |
| H09 parameter non-identifiability | Planar-only Mooney--Rivlin data from H02. | Only $C_{10}+C_{01}=0.5$ MPa is identifiable; rank/condition or equivalent diagnostic reports the flat direction. | Diagnostic status and response, not individual coefficients. Failure means false certainty. |
| H10 local basin and multistart | Two-term Ogden H04 data; fixed starts near truth/permutation and a distant constrained basin; retain every Attempt. Cross-reference the public Ogden--Saccomandi--Sgura nonuniqueness result. | Deterministic Attempt set; best response is selected by the declared rule; distinct parameter sets/local or symmetric basins are not collapsed. | Attempt persistence, gradient/termination and objective ordering. Failure means multistart evidence was discarded or “unique” was claimed. |
| H11 invalid initial modulus | Neo-Hookean $C_{10}=-0.5$ MPa; Mooney--Rivlin sum $\le0$; Ogden $\sum\mu_i^A\le0$. | Candidate is rejected or gets hard physical-constraint failure before selected-model save. | Exact diagnostic/error class. Failure means optimizer success overrode invalid modulus. |
| H12 stability-violating Candidate | Yeoh $(0.5,-0.2,0.01)$ MPa over uniaxial $\lambda=1..3$. | It is positive and monotonic only in a bounded early range, reaches its response maximum at the first root of $dP/d\lambda$ near $\lambda=1.401837$, and turns negative later. | Evaluate the closed-form response and derivative on 20,001 uniform points over $[1,3]$ (step $10^{-4}$), bracket every derivative sign change, and refine roots independently. Failure means the domain was hidden or global stability claimed. |
| H13 fit pass / extrapolation fail | Fit H12 only through $\lambda=1.4$; extrapolate to 2.0. | The closed-form derivative remains positive through $\lambda=1.4$ (endpoint $dP/d\lambda=0.0141520652$ MPa), with $P(1.4)=0.6212573988$ MPa, while $P(2)=-0.63$ MPa; fit and extrapolation statuses differ. | Closed-form endpoint, the declared derivative/response scan and separate statuses. Failure means extrapolation was treated as fitted validation. |
| H14 stress-measure mismatch | Supply H01 numeric Cauchy stress while descriptor requests nominal stress without current area/$\mathbf F$. | Normalization rejects the source; it does not fit the values as nominal. | Exact validation error. Failure means a hidden stress conversion. |
| H15 sign-convention error | Supply compression-positive H01 compression values but label tensile-positive without transform evidence. | Sign validation/review blocks the Plan or produces an explicit mismatch error. | Exact evidence/error. Failure means compression can be mirrored silently. |
| H16 unit mismatch | Supply H02 MPa values once correctly converted and once mislabeled as Pa. | Correct path multiplies by $10^6$; mislabeled data trigger scale/unit evidence failure rather than a “good” rescaled fit. | Exact unit round-trip and factor check. |
| H17 optional Prony recovery | $G_0=1$ MPa, $(g,\tau)=((0.2,0.1\,s),(0.3,10\,s))$. | $G_\infty=0.5$ MPa; $G_R(0.1)=0.8705908384$ and $G_R(10)=0.6103638324$ MPa. | Independent exponentials; failure means instantaneous/equilibrium or time-unit mismatch. |
| H18 Prony coefficient boundary | Same base with ratio sums 0.99 and 1.0. | 0.99 passes the strict positive-long-term algebraic check; 1.0 fails. | Exact inequality classification, not a material-quality threshold. |
| H19 tampered source digest | Mutate one normalized point or Artifact byte after Plan construction. | Execute/save rejects the digest mismatch; prior evidence remains unchanged. | Exact digest/read-back. |
| H20 save/reload | Select exact H02 Candidate with reason and any warning acknowledgements; save and reload. | Canonical Plan/Run/Attempt/Candidate/Recommendation/Selection/selected-model fields and Artifact digests match exactly. | Byte/canonical-decimal contract. |
| H21 upstream stale | Advance one input stable identity to a new revision after H20. | Historical selected model still reloads; current workspace is stale and cannot silently reuse the old Candidate. | Exact revision/CAS state. |
| H22 solver mapping preflight | Promote H01–H04 approved typed fixtures with and without H17 overlay to declared Abaqus/OpenRadioss targets. | Energy/stress convention round-trip, six-state mapping, acknowledgement identity and report/card digests match; unsupported combinations fail preflight. Direct LAW69 coefficient export must fail as `unsupported`. Any future LAW69 curve path pins the generated engineering stress–strain curve, mode/domain/quantity, Starter-refit provenance and error, and reports `approximated`, never `exact`/`transformed`. | Algebraic oracle plus golden bytes only after independent review. A pass on H04 cannot qualify LAW69 card syntax. |

### 12.3 Solver-oracle separation

Solver documentation establishes parameter and keyword semantics. It does not replace an independent
family evaluator, qualify external solver execution or justify platform defaults. Licensed solver runs,
element benchmarks and cross-solver equivalence are future qualification evidence and must name solver
version, element, boundary condition, units and tolerances.

## 13. Implementation decomposition and delivery dependencies

### 13.1 Recommended implementation issues

| Unit | Owned outcome | Preconditions | Exit condition |
|---|---|---|---|
| #196-A engineering contract and reference set | approve mode/quantity/convention vocabulary, equations, synthetic H01–H22 oracles and initial decision record | this packet; product owner selects the first bounded slice and applicable `OPEN_DECISION` items | independent equation/convention review passes; no production default remains implicit |
| #196-B test-mode and quantity normalization | typed exact inputs, transforms, units, signs, conditions, cycle and per-member domain | #205/#206; #211 only for representative input | unit/contract tests cover valid round-trips and H14–H16 failures; old normalized Datasets remain readable |
| #196-C numerical family engine | approved incompressible/compressible evaluators, family-specific typed configs and responses | #196-A/B; volumetric policy only if included | H01–H06 pass independently; no current family path duplicated |
| #196-D objective, multistart and diagnostics | reconstructable objective, all Attempts, holdout, identifiability/uncertainty, stability/extrapolation taxonomy | #196-A/C and approved objective/diagnostic decisions | H07–H13 and failure recovery pass; no single global stable flag |
| #196-E Plan/Run/Candidate/Selection persistence | versioned resources, failed Runs, Recommendation, Selection, selected-model, reload/stale | contract-first decision; #196-B/D interfaces may be mocked in parallel | H19–H21 plus authorization/idempotency/concurrency/PostgreSQL tests pass |
| #196-F Fit UI | #158 common shell, full Candidate evidence, optional overlay, save/reload/stale/error | #184 and #196-E API | focused Vitest plus one realistic browser flow and all five viewport states pass |
| #196-G Prony overlay | explicit none/pinned selection, #195 shared convention, base conversion, sequential path; joint path only if approved | #195 merged; #209 only for DMA/TTS; #196-C/E | H17/H18 plus base/conversion and unsupported mapping tests pass |
| #196-H IR/Neutral and solver mapping | new typed IR version only if necessary; current canonical compatibility; target-specific preflight | #196-C/E/G; explicit solver target evidence | H22, old golden regressions, mapping report/read-back and no licensed-solver overclaim |
| #196-I live/product acceptance | primary journey, recovery, reload, browser, visual and product-owner review | all applicable units and #184 | Section 15 passes; implementation issue remains open until every approved unit completes |

### 13.2 Parallelism and recommended insertion

- #196-A can proceed as the first future unit after explicit product-owner scope approval.
- #196-B waits for #205/#206 production contracts; direct exact Test Data does not require #211, while a
  representative envelope does.
- #196-C's independent incompressible evaluator can follow #196-A while persistence interfaces are
  designed, but no concurrent writer modifies the same contract.
- #196-E may use mocked engine results after the typed contract is frozen.
- #196-F waits for #184 and the stable #196-E contract.
- #196-G reuses merged #195; DMA/TTS work waits for #209.
- #196-H retains existing code-owned exporters and is independent of #213/#214 unless those scopes are
  explicitly added.

Recommended central position is after #211 and before #213. This packet does not edit the central
backlog or activate that position.

### 13.3 Migration and compatibility risks

| Risk | Required mitigation |
|---|---|
| Old one-term Plan evaluator and new family set | version the Plan/evaluator; never reinterpret stored 1.0 content |
| Stability enum mismatch | dual-read/versioned-write adapter and exact regression before migration |
| Candidate payload growth | artifact-backed arrays with size/count limits and digests |
| Failed Run persistence | append terminal state/error evidence without fabricating Candidates |
| New Selection/selected model | reference existing immutable Candidate; expected-head/CAS and idempotency |
| Compressibility | new typed IR/version decision; no in-place $D$ or $\nu$ fields on old incompressible revisions |
| Ogden convention | explicit enum and round-trip; reject unknown/bare $\mu$ |
| Prony base | explicit instantaneous/equilibrium conversion; preserve current ADR-0023 bytes |
| Solver expansion | target/version capability manifest and preflight; old supported/unsupported results remain reproducible |
| Current guide/API clients | additive version/adapter and implementation-time guide update; planning does not advertise future behavior |

### 13.4 Product-owner approval gates

Before the dependent code unit begins, the owner must approve:

1. first input modes/quantities and incompressible versus compressible slice;
2. allowed family/order/convention and volumetric potential if applicable;
3. objective transform/scales/weights, holdout/ranking and optimizer/multistart policy;
4. identifiability/uncertainty and stability/extrapolation methods/domains/thresholds;
5. Prony sequential/joint, base, term/bulk/TTS policy;
6. target solver/version scope and mapping qualification;
7. implementation order and any change to #117/backlog.

## 14. Proposed follow-up deltas

No common file is changed by this planning PR. Future approved units should consider:

| Authority/contract | Proposed delta | Owning future unit |
|---|---|---|
| `FR-MOD-E-001~004` | clarify compression/volumetric typed evidence, selected-model state and diagnostic taxonomy without adopting defaults | #196-A, then requirements PR if approved |
| `FR-CAL-002~007` | versioned family Plan/failed Run/all Attempts/Recommendation/Selection evidence and explicit `not_provided` | #196-A/E |
| ADR-0023 | retain current reference; create a new ADR for any compressible, multi-term or production hyper-viscoelastic IR | #196-H decision gate |
| ADR-0026 | extend evidence-chain semantics to typed family Selection/selected model without changing old promotions | #196-E |
| Source catalog | add versioned Abaqus/OpenRadioss/Material Modeler/MCalibration and primary-paper entries that directly support approved new claims | #196-A |
| Modeling contracts | correct stability enum/evaluator mismatch through a new version; add typed input/objective/diagnostic resources | #196-B/E |
| Material Model IR/Neutral | add only concrete versioned fields required by an approved selected model/overlay | #196-H |
| Current user guide | update actual implemented modes, controls, reload/stale and solver behavior only when code and live evidence exist | #196-F/H |
| Backlog/#117 | record split/order only after product-owner approval | delivery coordination; not this packet |

## 15. Acceptance packet for future implementation

### 15.1 Primary user and persistence acceptance

| Step | Observable acceptance |
|---|---|
| Data | engineer selects exact elastomer Test Data/Processing Output revisions; each mode, role, quantity, unit, condition, cycle and domain is visible and pinned |
| Process | any conversion has an immutable transform revision with assumptions; unsupported conversion fails without changing raw data |
| Fit | approved families execute from one exact Plan; all Attempts and failed Run evidence are searchable; response/residual/objective reconstruct |
| Check/Review | fit, holdout, uncertainty/identifiability, physical/stability and extrapolation evidence are separate and scoped |
| Decision | Recommendation or no-recommendation remains distinct from engineer Selection/reason/acknowledgements |
| Save | `Save fit & continue` creates one immutable selected-model revision from exact server evidence |
| Read-back | reload reproduces source, Plan, Run, Candidate, decision, warnings, plots and digests |
| Stale/recovery | upstream change marks the current path stale without mutating history; retry creates new Run or retries only the failed downstream action |
| Prony/Export | explicit no-overlay or exact #195-compatible overlay is preserved; Neutral and solver card remain separate and unsupported mappings fail preflight |

### 15.2 Negative acceptance

The following must fail or warn with the exact stated class:

- missing/ambiguous mode, stress/strain measure, area, sign, unit, condition, cycle or transform evidence;
- nonpositive stretch/$J$, non-finite values, duplicate source revision or overlapping forbidden
  calibration/holdout selection;
- relative/log residual at invalid zero/sign points without an approved transform;
- invalid modulus, unknown Ogden convention, unsupported order/potential or Prony sum;
- optimizer nonconvergence, rank deficiency, parameter at bound, sparse domain and no holdout without
  presenting them as validation success;
- selected client parameters that do not match a server Candidate;
- stale/tampered source, missing acknowledgement, expected-head conflict or cross-scope identity;
- unsupported solver target/version/law/overlay or stale preflight digest.

### 15.3 Technical acceptance

- Unit: independent H01–H18 equations, conversions, constraints, objective, attempts and diagnostics.
- Contract: typed versions, enum compatibility, canonical serialization and old revision fixtures.
- Integration/PostgreSQL: exact source → Plan → Run/Attempts/Candidates → Recommendation → Selection →
  selected model → optional Prony → IR/Neutral → preflight/card, including H19–H22.
- API/security: organization/project isolation, idempotency, CAS conflict, failed Run/read-back and
  immutable bytes.
- UI: focused state tests plus one realistic primary browser flow, reload, stale and downstream recovery.
- Visual: all five CSS viewports at zoom 100%, original images and required 100%-pixel crops; qualitative
  owner approval remains mandatory.
- Solver: independent energy/stress conversion and golden rendering; licensed solver execution only when
  separately authorized and never implied by a card fixture.

### 15.4 Current planning-PR acceptance and N/A register

| Gate | Current packet disposition |
|---|---|
| Changed paths | only `docs/12-roadmap/issue-196-elastomer-hyperelastic-hyperviscoelastic-fit-plan.md` |
| Requirement/implementation/source trace | applicable; current code/tests, #195 and direct public sources cited |
| Markdown, link, manifest and documentation impact | applicable deterministic repository checks |
| Independent engineering/product review | applicable on the exact final PR head; findings/disposition recorded in Section 17 |
| Compose/database/API/runtime tests | N/A — no code, contract, migration, fixture or runtime behavior changed |
| Browser/screenshots/five viewports | N/A — no React/CSS/current guide or approved visual reference changed |
| Product owner production-policy approval | deferred; every unapproved value remains `OPEN_DECISION` |
| #196 implementation/closure and #117/backlog order | forbidden in this planning unit |

## 16. Source and evidence register

All public URLs were checked on 2026-08-11. Product pages support only the claims written below; no
private optimizer, automatic recommendation rule, bound, weighting or threshold is inferred.

| Source | Version / evidence type | Directly supported use |
|---|---|---|
| Repository [official-product research](../00-research/official-product-research.md) and [source catalog](../00-research/product-reference-source-catalog.json), entry `material-modeler-hyperelastic-edit` | baseline `7c796ac`, `CONFIRMED_CURRENT` | Current approved product-reference routing and the limited Material Modeler UI claims already admitted by the repository |
| [Altair Material Modeler — Edit Physics Workflow](https://help.altair.com/material_modeler/hyperelastic/topics/amm_hyperelastic_web/edit_physics_workflow_t.htm), [Add Workflow](https://help.altair.com/material_modeler/hyperelastic/topics/amm_hyperelastic_web/amm_add_worklfow_t.htm), [tutorial](https://help.altair.com/material_modeler/topics/material_modeler/tutorials/ammp_hyperelastic_fit_r.htm) | 2025 official, `FACT_PUBLIC` | enabled test curves, model choice, editable parameter bounds, refit/reset, visual/numeric comparison, Save State and publish/export separation; UXT/EBT/PLN terminology |
| [MCalibration product page](https://www.ansys.com/products/structures/mcalibration) and [official quick tutorial](https://www.ansys.com/content/dam/resource-center/datasheet/mcalibration-quick-tutorial.pdf) | current official, checked 2026-08-11, `FACT_PUBLIC` | public scope includes test-data import, parameter calibration, visualization/virtual experiments, export and stability-related review; no internal algorithm/default is used |
| [Ansys Material Calibration Standalone Help](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v252/en/pdf/Ansys_Material_Calibration_Standalone_Help.pdf) | 2025 R2 official, `FACT_PUBLIC` | supported hyperelastic modes, unit consistency, user-edited initials/bounds and staged combined hyperelastic/Prony workflow |
| [Abaqus Hyperelastic Behavior](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEMATRefMap/simamat-c-hyperelastic.htm) | Abaqus 2025, `CONFIRMED_CURRENT` for public solver convention | energies, initial moduli, nominal test data/modes, volumetric data, solver fitting objective and bounded Drucker diagnostic; its defaults are not platform policy |
| [Abaqus Time Domain Viscoelasticity](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEMATRefMap/simamat-c-timevisco.htm) and [finite-strain theory](https://docs.software.vt.edu/abaqusv2024/English/SIMACAETHERefMap/simathe-c-finitestrvisco.htm) | Abaqus 2024 official, `CONFIRMED_CURRENT` for public solver convention | normalized instantaneous Prony, long-term conversion and finite-strain hereditary push-forward |
| OpenRadioss [LAW42](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/mat_law42_ogden_starter_r.htm), [LAW69](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/mat_law69_starter_r.htm), [LAW82](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/mat_law82_starter_r.htm), [LAW94](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/mat_law94_starter_r.htm), [`/VISC/PRONY`](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/visc_prony_starter_r.htm) | 2026 official, `CONFIRMED_CURRENT` for public solver convention | law-specific Ogden/volumetric conventions, LAW69 curve-input/internal-fit boundary, initial shear relations, dimensional branches/rates and declared law compatibility |
| [Mooney 1940](https://doi.org/10.1063/1.1712836), [Rivlin 1948](https://doi.org/10.1098/rsta.1948.0002), [Treloar 1943](https://pubs.rsc.org/en/content/articlepdf/1943/tf/tf9433900241) | primary papers, `FACT_PUBLIC` | historical invariant/rubber-elasticity model provenance |
| [Ogden incompressible 1972](https://doi.org/10.1098/rspa.1972.0026), [Ogden compressible 1972](https://doi.org/10.1098/rspa.1972.0096), [Yeoh 1993](https://doi.org/10.5254/1.3538343) | primary papers, `FACT_PUBLIC` | model-form provenance and finite-strain context; solver parameter names still require solver documentation |
| [Ogden, Saccomandi and Sgura 2004](https://link.springer.com/article/10.1007/s00466-004-0593-y) | peer-reviewed primary research, `FACT_PUBLIC` | nonlinear parameter-fit nonuniqueness and different downstream responses |
| [Quigley 1995](https://meridian.allenpress.com/rct/article-pdf/68/2/230/1943906/1_3538738.pdf) | peer-reviewed research, `FACT_PUBLIC` | finite-strain Prony calibration/validation range and stability-constrained comparison |
| [ISO 37:2024](https://www.iso.org/standard/86892.html), [ASTM D412-16(2021)](https://store.astm.org/standards/d412) | official public scope metadata, `CONFIRMED_CURRENT` | rubber tension scope and the relevance of specimen, rate, temperature, conditioning and geometry; not a selected production standard |
| [ISO 7743:2017](https://www.iso.org/standard/72784.html), [ASTM D575-91(2024)](https://store.astm.org/standards/d575) | official public scope metadata, `CONFIRMED_CURRENT` | rubber compression scope; not a selected procedure |
| [ISO 1827:2022](https://www.iso.org/standard/84135.html) | official public scope metadata, `CONFIRMED_CURRENT` | bonded quadruple-shear scope, used to prevent confusion with planar tension/pure shear |
| [ISO 3384-1:2024](https://www.iso.org/standard/86478.html), [ASTM D6147-97(2026)](https://store.astm.org/d6147-97r26.html) | official public scope metadata, `CONFIRMED_CURRENT` | compression stress-relaxation scope and limits on unsupported time/temperature extrapolation |

### 16.1 Evidence conflict disposition

- Current code, current IR, Abaqus and LAW82 align on the $2\mu/\alpha^2$ Ogden convention. LAW42
  explicit input and LAW69 internally fitted pairs use the different coefficient convention in Section
  6.5, but LAW69 accepts a curve rather than direct pair input and therefore is not a coefficient exporter.
- #195 and Abaqus align on normalized instantaneous Prony storage. OpenRadioss dimensional/long-term
  target inputs require explicit conversion rather than a second internal convention.
- Abaqus' residual objective and bounded Drucker scan are solver facts, not recommended production
  defaults.
- Altair/Ansys product workflows support comparison, editable bounds and review separation; they do not
  disclose or authorize copying proprietary optimization/recommendation defaults.
- Standards establish test scope/metadata only. The production standard and specimen/cycle policy remain
  `OPEN_DECISION`.

## 17. Independent review record

The independent read-only reviewer first audited commit
`f7d47877f726086ecf6e46d878b854fd8f84f8a4` and returned `changes_requested`. The table records every
finding and its packet disposition. Because recording a verdict changes the document SHA, the final
publication gate is a same-reviewer read-back of the corrected exact PR head; that exact-head verdict is
kept in PR delivery evidence, and no content edit may follow it without another review.

| Review item | Finding | Disposition |
|---|---|---|
| Current implementation versus new scope | Pass: the `narrow` recommendation and gap matrix do not re-plan the bounded reference path. | No change required. |
| Mode, quantity, stress/strain and sign equations | Pass: equations and normalization boundaries are internally consistent. | No change required. |
| Family and Ogden solver conventions | Major: LAW69 shares the fitted-pair equation convention but does not accept direct coefficients; the first draft could be read as qualifying coefficient export. | Sections 6.5, 9.5, H04, H22 and the source/conflict record now forbid direct LAW69 coefficient export. A separately evidenced curve/Starter-refit path is `approximated`, not `exact`/`transformed`. |
| Incompressibility and volumetric response | Pass: constraint pressure and compressibility evidence remain distinct. | No change required. |
| Fitting, weighting, holdout, identifiability and recovery | Pass: the production policy remains `OPEN_DECISION` and fixture rules are reconstructable. | No change required. |
| Stability taxonomy and domain claims | Reviewer pass; Main's post-review dense scan found that H13's first fitted endpoint, $\lambda=1.5$, extended beyond the response maximum. | H12/H13 now bound the fit at $\lambda=1.4$, record $P(1.4)=0.6212573988$ MPa, $dP/d\lambda=0.0141520652$ MPa there and the first derivative root near $1.401837$, and keep $P(2)=-0.63$ MPa as extrapolation failure. |
| #195 Prony reuse and finite-strain boundary | Pass: shared normalized Prony evidence is referenced rather than forked, while finite-strain coupling/base conversion is elastomer-specific. | No change required. |
| Recommendation, Selection and immutable evidence | Pass: machine recommendation, engineer Selection and immutable exact-revision evidence are separate states. | No change required. |
| Independent reference matrix and solver oracle | Blocker: the first draft left the review record pending. The numerical oracles themselves had no reported equation error; LAW69 needed the boundary above. | This completed finding/disposition record replaces placeholders; final merge still requires same-reviewer approval of the corrected exact PR head. |
| Dependencies, exclusions and direct-source support | Pass: dependencies and exclusions are bounded, production TBDs are not approved, and direct public sources support the claims. | LAW69's official source is now explicit in the source register. |
