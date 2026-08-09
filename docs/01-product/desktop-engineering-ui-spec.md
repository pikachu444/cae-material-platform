# Desktop Engineering UI Specification

Status: authoritative implementation specification

## Canonical visible-field contract

This document is the single source for component-level field behavior. Each visible engineering
component or field must record: `purpose` (the user decision), `placement` (why it is adjacent to
its evidence), `visible_when` (family, workflow, permission and data state), `source` (including
revision, unit and condition), `requires`, `invalidates`, `states`, and `error_recovery`. The
implementation may add `action_output`, validation, and forbidden representations where needed.

Use this contract as follows: Materials search scope, facets and result count share a server-scoped
query source; a condition-aware Yield control is visible only for compatible metal results. Modeling
recommendations, explicit engineer selections, saved snapshots, validation, review, release and
delivery are separate states. An upstream input change clears downstream *current pointers* and
marks UI state stale, but never rewrites immutable revisions. In a blocked or error state, preserve
the source, selected curves/candidate and plot context, name the unmet requirement, and offer the
next safe recovery action. UUIDs, hashes, raw JSON and plugin keys remain Advanced/Evidence fields.

## Canonical component registry

This authoritative annex retains the component-specific contract. Each compact row states
**purpose/placement**; **visible when, source, requires**; **output, state, invalidates, recovery**.
`Target` is pending work, not a claim about the current product.

| Components | Contract | Not allowed / status |
| --- | --- | --- |
| G-01 navigation; G-02 identity header | Move among Materials/Modeling/Activity in the shell; show human Material/session name, form/condition, version and state from exact context. | Internal module hub, UUID/hash as title, duplicated headings; current. |
| G-03 primary action; G-04 Evidence | One next task action in header/footer with prerequisite and calculating/blocked/error state; disclose IDs, JSON and checksums only on demand. | Multiple equal primaries, silent disabled action, technical default fields; current. |
| M-01 scope; M-02 search; M-03 tree | Establish governed scope, find known material, or browse Database→Profile→Table→Folder→Record; exact selection updates workspace. | Fake sole-scope selector, client subset presented as complete, tree as form; search correction is UXC-01 target. |
| M-04–07 facets/filter/header | Refine the same server query; show condition/unit/source, active restrictions, total/sort/page and loading/empty/error state. | Facet counts/rows/totals from different sources; UXC-01 target. |
| M-05 Yield | Show only for compatible metal property definition with condition/unit/source. | Yield filter/column for polymer or elastomer; UXC-01 target. |
| M-08–12 grid/layout/compare/inspector/start | Compare/select/open dense rows; select allowed Layout; pin Material/Test Data into Modeling; preserve selection and result context. | Truncated identity, auto-compare, unpinned latest start, blanking main pane; current. |
| M-13–18 detail/property/curve/cards/relations | Display identity, Layout value, original/normalized units, curve, target card/mapping and exact relation evidence in purpose tabs. | Long generic accordion, ambiguous Preview/fake Download, hidden mapping; current. |
| W-01 session; W-02 stage; W-03 context; W-04 action | Establish exact family/Material/State/Test Data pins, use the v3 clearable session reducer, and change the normal `Data | Process | Fit | Export` path without graph remount. Validation and review remain separate governed actions reached from Advanced or Activity; they never occupy permanent normal-path columns or stage tiles. The compact title row keeps the current task, human Material/session context, Advanced, preview/run and at most one save/continue action visible. | Global output fallback, a stale current pointer, Fit as new-session default, six normal-path stage tiles, or “reviewed”/“released” labels without an event; UXC-04C current. |
| D-01 source; D-02 library; D-03 raw inspector | Select a permitted exact Test Data revision or inspect CSV/TSV/XLSX parser output. The inspector stays beside source selection because sheet/header/decimal, raw sample rows and immutable raw checksum are the evidence for the next decision. | Visible until a source is saved; source is the permitted revision or immutable Raw Asset; requires a supported parser result; empty/inspecting/blocked/error preserve file and parser choices for retry. |
| D-04 provenance; D-05 axis/unit mapping; D-06 plot; D-07 save | Record Test Run/specimen/condition provenance and show each source column, quantity/axis semantics, raw unit, normalized unit and mapping state before preview. A manual mapping requires source column, unit and reason; changing it creates the next Test Data revision and clears Process→Export current pointers. `Save dataset` is the only Data primary action and never implies review. | Raw bytes and raw-unit text are never mutated; hidden conversion, internal semantic keys, or `reviewed data` labels are forbidden. Save failure retains source, mapping and plot for retry. |
| P-01 rail; P-02 replicate; P-03–05 operation; P-06 workup; P-07 plot; P-08 save | The Process rail is a compact test-method/specimen tree: `Curves · curve count · included count`, filter, canonical method parent, inclusion checkbox, specimen identity/revision and an icon-only plot-visibility control. Inclusion and visibility remain distinct. Replicate analysis is a secondary disclosure only with two compatible included curves. Purpose-grouped operations form an ordered recipe; the contextual inspector keeps the selected operation, source and before/after plot together. Metal elastoplastic exposes manual Young’s modulus and selected necking-boundary workup only when they affect the executed method. Each requires a value, explicit unit/quantity semantics and reason, then is retained as typed `workup_overrides` with original and canonical values in the immutable Processing Output revision and Artifact. Yield remains curve-derived proof stress at the selected offset; direct manual yield is unavailable until its production definition is approved. A draft operation/order/scope/workup change dispatches `CHANGE_PROCESS` even without a saved Recipe pin, stales downstream current pointers, and `Save processed curves` creates the immutable output revision. | A visible `Hide`/`Show` word row, decorative tree branches without a parent, generic `Curve NN` identity, combined include/visibility semantics, manual curve edits, outlier deletion, implicit smoothing/resample, duplicate commit actions and review language are forbidden. Preview/save failures retain draft, selection and plot for retry. |
| F-01–07 rail/workflow/model/bounds/range/run/plot | Select compatible processed data, model/bounds/range, run fit and show response/residual/tangent plus observed/extrapolated domain. For metal, the Fit rail groups the six configured operations as Sort duplicate x, True/plastic conversion, Necking boundary and Hardening fit; grouped internal modulus/proof work remains executed but is not a normal-rail row. The approved `modeling.html` topology is a compact Curves/Process rail, a 31 px heading plus 72 px control ribbon, then the separate graph header and dominant graph. The normal ribbon contains Candidate equations, Fit domain, Selected blend (Primary and Secondary), Primary contribution/Review metric, Extrapolation (Target strain and Output points), and Graph interaction. The normal Fit title row shows only a human Process source label/revision and one concise surface state; full digest, method key/version and run remain in Candidate parameters Evidence. Input change invalidates decision onward. | One-row Fit-candidate substitute, duplicate range/point actions, opaque score, graph-overlay metric cards, preview/zoom/pan diagnostics in the Fit graph header, a ribbon/graph-header collision, hidden fit inputs, or a permanent third inspector column; UXC-04E current. |
| F-08–11 comparison/selection/blend/save | The closed `Candidate parameters` disclosure in the shallow Fit band exposes calculated comparison, explicit selection, reason/warning acknowledgement and parameter evidence on demand. Blend laws and output resolution stay visible in the normal ribbon because they directly change the persistent preview. The sole commit action is top-row `Save fit & continue`; closing the disclosure returns the full dominant graph. Recommendation never mutates the immutable decision snapshot. | Auto-selection, reason-only selection, duplicate save action, a persistent bottom dock/right inspector, blend represented as one law, or a permanently open wide table/editor above the graph; UXC-04E current. |
| V-01–04 plan/run/result | When the current selection, Material Model IR calibration evidence and Solver Card exact revisions match, pin an existing synthetic reference Template and Dataset Selection, submit/evaluate the non-production runner and retain its immutable result separately from Fit evidence. A normal Processing Output without that adapter is `Not supported`. | Validated without a Validation Run, same-State model substitution, first-item/latest fallback, or a result reused as Fit evidence; UXC-05 current. |
| R-01–04 package/submit/approve/release | Display Submit, Request changes, Approve and Release as distinct command/state contracts. Until an immutable candidate-package producer and release-policy input exist, each unavailable command is explicitly `Not configured`/`Not run`; exact context may open Activity or the governed reference harness. | Approval/release without policy, permission, event or an authoritative package digest; UXC-05 current boundary. |
| E-01–08 prerequisites/pin/lineage/target/preflight/preview/deliver/evidence | Pin current allowed exact model, select solver/version/unit, expose mapping/acknowledgement, preview and deliver immutable lineage artifact. Source/target change invalidates preview/delivery pointer; retain preflight for recovery. A newly saved governed local-file Test Data revision may carry server-verified Test Run→Specimen→Material State→Material pins, and its Processing Output projects those exact pins. Historical or JSON-only revisions remain explicitly unqualified. UXC-06C1 remains a stateless server-proven preview; UXC-06C2 explicitly delivers one immutable Solver Card/receipt. | A permanent curve/specimen rail, alignment/mean-band controls, inferred proof for a null historical projection, artifact UI without server-proven exact source, silent approximation, preview labelled delivered, or a duplicate delivery on exact retry. |

### Curve/specimen rail component and field contracts (`P-01`, `F-01`)

| ID / component or field | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `P-01` rail summary, test group and selected specimen row | State the available test scope and let the engineer focus one specimen without consuming graph width. | Left of the persistent graph; the compact summary and real method group precede indented 26 px specimen rows. A group is a native keyboard-operable disclosure only when its rows can truly be collapsed; otherwise it has no disclosure glyph. Each row's 20 px horizontal plot-color legend sample follows the title and precedes the plot-visibility control, so it cannot read as a branch or title prefix. Printed `└`/`ㄴ` glyphs and decorative branches are forbidden. | Data/Process with compatible Test Data; the same row grammar is used by `F-01` in Fit. It is absent from Validate, Review / Release and Export. | Compatible Test Data/Processing Output revisions, canonical `method`, specimen identity, session selected-document identity and revision metadata. Add a condition subgroup only when exact condition metadata is present; never invent temperature or rate. | Current compatible source context. | Selecting a row changes local selected-curve/plot context only; it never rewrites a revision. | empty, compatible, selected, stale, blocked. | Keep selection and graph context; name a missing/incompatible revision and return to Data/Process. |
| `P-01a` Include in processing/fit checkbox | Make the engineer’s calculation-membership decision explicit and independent of viewing a line. | First control in each Data/Process tree row. | Data/Process when the existing session authorization allows selection changes; never rendered as editable downstream evidence. | Session selection IDs and the row’s exact Test Data/Processing Output revision. | Compatible exact source and a stage that owns selection. | Dispatches `CHANGE_SELECTION`; clears fit decision, validation, review, release and delivery current pointers while immutable history remains. | included, excluded, limit-reached, stale. | Preserve the row and current plot; retain selection on failed preview and explain the blocked prerequisite. |
| `P-01b` Show on plot eye control | Toggle only the browser-local line visibility while retaining inclusion and exact curve identity. | Final compact control in each Data/Process row. | Data/Process with a plotted source; keyboard reachable with an accessible show/hide label. | Local view state keyed by the exact selected document ID. | A loaded compatible curve. | Does not invalidate selection, Recipe, output, candidate or any immutable revision. | visible, hidden, selected, unavailable. | Preserve all engineering state and restore the prior local visibility when the same exact session is resumed. |
| `P-07a` wide Process graph alignment | Keep the Process task visually coherent on 2560/3840 without leaving a one-sided 1920 px work island, stretching every element or adding unrelated filler. | The full shell spans the viewport. The graph sits directly below the bounded settings band; its plot grows while extra area improves curve comparison and point/range interaction, then stops at a measured useful bound with balanced remaining gutters. Its right edge remains coherent with `Save processed curves`. | Process at 2560×1440 and 3840×2160; the same graph-first topology remains at canonical viewports. | The same ordered observed, processed-preview and calculated-fit arrays rendered by `P-07`; no companion table is introduced. | A finite compatible saved Test Data selection and current processing preview. | View-only responsive layout using shared display-tier tokens; it never changes source, selection, preview or output state. | current, stale-with-last-valid-plot, blocked, unavailable. | Preserve the last valid plot and the bounded settings/graph alignment; recover through the owning Process action. |

### Export component and field contract (`E-01`–`E-08`)

| ID / component | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `E-01–04` exact source checklist and lineage | Make every required current pin and the Processing Output → IR → Neutral → target preflight → native card chain inspectable before an artifact action. | Export graph dock, replacing artifact controls while any prerequisite is not current. | Export stage. | Session refs plus the loaded Processing Output `export_provenance`, copied from the exact Canonical Test Data revision after Catalog/Testing verification. | Matching current refs and non-null exact Material/State proof; Test Run is validated server-side through its Specimen. | A new Test Data/Processing Output revision or any upstream change retains history but clears/regenerates downstream current pointers. | current, missing, stale, not-supported. | Null is an honest historical/unqualified state and is never backfilled or inferred. Name the missing/mismatched pin, preserve session context, and return to Local file Data or the owning stage. |
| `E-05–08` destination, Export check, preview, create and delivery details | Select one explicit exporter-declared **Reference target tuple**, disclose every decision-relevant mapping consequence, create a stateless preview, then explicitly create one immutable Solver Card. | The Export setup pane shows only selected model identity, Destination, one Export check state and its current action. The common experiment/method/condition remains in the compact page context instead of being mislabeled as a Fit result. It is followed by a dominant native preview. A bounded read-only result column may place family-specific Mapping details above a compact Fit source preview; it is not a control inspector and never overlays or clips either result. Normal-path labels use engineer task language (`Create solver card`, `Destination`, `Export check`, `Solver card preview`, `Mapping details`, `Fit source`). Exact IDs, checksums, technical mapping status, lineage flags and receipt mechanics stay in Advanced or Delivery details. Metal recovery remains in the setup pane when only the IR/Neutral pins are absent; it requires a bounded-extrapolation acknowledgement and reason, pins the returned upstream model immediately, and offers Neutral-only retry if the second promotion fails. | Only after `E-01–04` server proof and C1's server resolver. | Exact Processing Output proof, the exporter capability tuple and target-preview/delivery contracts. Source Material/State/model values are read-only here and physical values appear once in Mapping details when they affect output. The upstream model pin and the Neutral document's embedded canonical IR are distinct identities: C1 sends the exact Neutral revision and the server resolves/verifies its embedded IR. The current choices mirror `neutral_hyperelastic_capability_manifest`'s non-production Abaqus/OpenRadioss 2025 kg-m-s tuples; they are not a production matrix. | Exact output/model/neutral source, one supported target tuple, deterministic mapping result and acknowledgement identity where required. | Target tuple change clears the local preview and delivery pointer, never the source IR/Neutral. An upstream physical-property correction creates a governed revision and invalidates current downstream pointers. | cannot-create, checking, review-required, ready-to-create, creating, created, stale, failed, retry. | C1 writes no card/artifact/receipt/Activity. C2 acknowledgement is bound to acknowledgement identity only when mapping requires it; its card/receipt/outbox write is atomic and an exact retry returns the original delivery. Materials CAE Card reuse is canonical. When Activity projection is not configured, omit an Activity link/status. Non-metal recovery says `Not configured` only at the unavailable action and never substitutes a model. |

#### Export user-facing field contract (`E-05`–`E-08`)

| ID / component or field | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `E-05a` Destination | Choose only a real exporter-declared solver/version/unit tuple. Output unit system is always a visible capability-backed selector: supported options are selectable, while an exporter-declared unavailable option may be visible but disabled with its reason. Never accept a known-invalid option and defer the failure to a warning dialog or disabled Create action. | Top of the left Export setup pane. | Exact export source is current. | Exporter capability manifest; synthetic reference tuples remain explicitly non-production. | One supported tuple. | Any valid tuple change clears preview, acknowledgement and delivery pointers and requires a new Export check. | unselected, selected, unavailable, stale. | Preserve the source and explain why a target is unavailable; never substitute a default. When only one unit system is supported, retain the selector and disclose that no other option is available. |
| `E-05b` source physical properties | Let the engineer verify pinned Material/State/model inputs without implying they can be edited during export. | Once in the corresponding Mapping details row; the left setup pane retains only selected model identity. | A mapping item uses the value. | Exact Material/State/Neutral revision with original and canonical value/unit semantics. | Current source chain. | No local edit exists. An upstream governed revision invalidates downstream current pointers. | current, missing, stale, context-only. | `Open in Fit` returns to the exact selected model branch and an Advanced source link exposes its immutable upstream chain; Export never mutates Density, elasticity or fitted parameters. |
| `E-06a` Export check | Answer whether the card can be created now, rather than exposing an unexplained preflight mechanism. | Below Destination in the setup pane, adjacent to the sole current action. | Export stage. | Current source/target mapping report and acknowledgement identity. | Deterministic mapping report. | Source/target change recomputes the state. | `Ready to create`, `Review required`, `Cannot create`, checking, failed. | State the readiness once, then name only the exact blocker/review item/next action; preserve source, target and any valid preview without repeating the failure across regions. |
| `E-06b` shared Mapping details | Show the decision consequence of each mapped quantity with source value/unit and target value/unit or representation, using one component grammar in Modeling Export and the Materials CAE Card preview. | Read-only result column beside the dominant Export preview or the bounded Materials delivery pane; normal rows fit without a decorative rail and genuine long content scrolls locally. | The current preview or saved Solver Card has a mapping report. | Exporter mapping items plus exact source values and rendered target values. | Same mapping-report digest used by preview/create or saved-card download. | Source/target change replaces the rows deterministically; a saved card remains pinned to its immutable report. | values-unchanged, converted, native-formatting, review-required, reviewed, not-supported, context-only. | Keep the last valid report marked stale while a new check fails. Each visible row uses one compact title/value/plain-status grammar; route-specific pills and per-row explanatory paragraphs are forbidden. Technical exact/transformed/approximated/ignored/unsupported/not-applicable counts stay in Advanced. |
| `E-07a` Solver Card preview | Let the engineer inspect the native ASCII result before creating an immutable card. | Dominant center result region on a light code surface with independent scrolling. | Stateless preview succeeds. | Exact preview bytes and target tuple. | Current source, target and mapping digest. | Source/target change removes the current preview pointer. | unavailable, preparing, ephemeral, stale, failed, created. | Preserve setup/mapping context and offer one specific retry. |
| `E-07b` Fit source preview | Retain compact visual continuity with the selected model without squeezing the native preview. | Bottom of the bounded read-only result column; `Open full graph` returns to the full Fit graph. | The selected family has a meaningful response projection. | Exact selected Fit result and family-specific quantities. | Current selected model. | A source change replaces the plot. | metal-response, viscoelastic-response, hyperelastic-mode, unavailable. | Preserve textual source identity when a plot cannot be produced; never reuse metal axes for another family. The compact plot derives headroom from the displayed data span, preserves a meaningful zero anchor where applicable, uses uniform SVG geometry and places its compact legend in a curve-free quadrant. |
| `E-08` Create/open and Delivery details | Create exactly one immutable Solver Card, then open it; expose the separate receipt through plain-language delivery details. | One filled action in Export check; a secondary `Delivery details` action appears only after creation. | Ready/create/created states and permission allow it. | Atomic delivery response and exact retry identity. | Zero blockers and any required acknowledgement. | A source/target change clears only the current delivery pointer. | disabled-with-reason, creating, created, failed, retry. | Exact retry returns the original result; duplicate submission is blocked and no review/release/Activity event is implied. |
| A-01–03 queue/item/job | Show `Needs attention | In progress | Recent outcomes`, resume exact browser-local Modeling/card context, and record a role-gated decision on an existing review request. User and Administrator pending requests stay in progress; only Reviewer pending requests receive one row-level Review action. Queue loading/error/empty states retain context and offer Refresh/Retry; object/person IDs stay in Advanced evidence. | Placeholder dashboard, generic job history, decision controls for User or Administrator, fake release/publish, stale-response overwrite, or a duplicate review request; DUI-08A current queue/decision boundary. |

### Fit component and field contracts (`F-01`–`F-11`)

| ID / component or field | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `F-01` processed-curve rail and configured sequence | Choose exact curves independently from plot visibility and focus a real ordered process/fit step, using the same compact tree row as `P-01`. | Left of the persistent graph: curve tree first, then the complete configured sequence with active hardening-fit step; never a one-row `Fit candidates` substitute. | Fit with a compatible saved Processing Output/Test Data context; never Export. | Exact Test Data/Processing Output revisions, immutable Recipe-draft step order and session inclusion state. | Current Material, State, Test Data and Mapping Profile pins. | Inclusion change dispatches `CHANGE_SELECTION`; focused-step change is local; option change dispatches `CHANGE_PROCESS` and both clear the applicable downstream current pointers. | empty, compatible, selected, stale, blocked. | Preserve rail, step and graph; identify the missing/incompatible exact revision and return to Data/Process. |
| `F-02` Fit task and primary action | Run/re-run candidates for the current input intent without implying a decision. | Compact stage strip and graph-adjacent ribbon. | Fit stage and write permission. | Session stage plus current Recipe step options. | Compatible processed input and one supported synthetic reference fit method. | Run-intent change clears the current selection and downstream pointers; immutable outputs remain. | blocked, ready, calculating, warning, error. | Keep inputs and prior graph; show the failed method and offer Update candidates. |
| `F-03` model/law intent | Declare bounded candidate families or Prony term-count policy and the explicit preview blend. | The shallow labelled current-step band: `Step N · method` left and impact/Remove right, then Candidate equations, Fit domain (Start/End), Selected blend (Primary/Secondary), Primary contribution with Review metric, Extrapolation (Target strain/Output points), and Graph interaction (Select fit range/Pick point). The normal Fit title row keeps only human source label/revision plus concise state; Candidate parameters is the compact evidence disclosure for full source digest, method key/version, run and parameter/bound evidence. It does not duplicate normal preview controls or overlay plot chrome. | Metal hardening or polymer Prony Fit respectively. | Versioned processing method registry and Recipe draft options. | Supported family/method capability; no production TBD default. | Change invalidates candidate preview and every downstream current pointer. | default intent, edited, unsupported, stale. | Restore last draft option or choose a supported synthetic reference option, then re-run. |
| `F-04` parameter and bound inspector | Inspect fitted parameter value, unit, lower and upper bounds before selecting. | Contextual disclosure beside the selected candidate, never a permanent third column. | Recomputed stage exposes parameter scalars for the focused candidate. | Server `scalar_results`; exact method/version and quantity unit. | Successful candidate computation. | Inspector viewing changes nothing; changing an input bound invalidates preview onward. | collapsed, available, bound-warning, missing-evidence. | Keep candidate focus; name the missing scalar and require re-run instead of inventing a fallback. |
| `F-05` fit/extrapolation range | Distinguish observed fit domain from unobserved bounded extension. | Fit-domain values are in the shallow band; range/point application lives once in its Graph interaction group beside the plot, never duplicated in the plot toolbar. | Metal Fit; polymer shows measured grid and `observed_only`. | Executed step options plus recomputed stage domain. | Finite ordered range; metal extension acknowledgement when warning applies. | Range change invalidates preview, selection and all downstream pointers. | observed, extrapolated-warning, observed-only, invalid. | Preserve values and graph; correct the ordered range and re-run. |
| `F-06` Update candidates | Produce deterministic candidate evidence, not a saved selection. | Only primary run action in the Fit header. | Fit prerequisites are satisfied. | Exact input revisions, method/version and current options. | Server preview endpoint and supported method. | New successful preview clears any selection made against an older preview. | ready, calculating, succeeded, failed, superseded. | Cancel/supersede older requests; retain current draft and offer retry. |
| `F-07` persistent response plot | Compare observed, decision-relevant candidate/blend, residual/tangent and extrapolated response without remounting the workspace. | Dominant center region (at least 72% at 1440 px), headed `Hardening response` for metal hardening Fit; a single concise `Ghosh exceeds chart scale` helper appears only when the display tail is clipped. Compact Response/Residual/Tangent modulus/Reset view controls precede a locally hideable legend. SVG uses the available measured plot box without distorting axes/text. The Fit ribbon and all six groups remain contained at 1366/1440/1920/2560/3840 through shared display-tier tokens; above 1920 the shell spans the viewport and the plot grows to a measured useful bound instead of imposing a global 1920 px cap. | Data is loaded; overlays vary by current stage/view. | Server preview stages and exact source series. | Matching quantity semantics and explicit units. | Plot-view/zoom changes do not invalidate engineering state; graph range edits follow `F-05`. | loading, response, residual, tangent, empty, error. | Preserve plot controls and last good context; identify unavailable overlay and retry preview. |
| `F-08` candidate comparison table | Compare model identity, recommendation, metric, range, stability, compatibility and warning on one row. | Inside the on-demand `Candidate parameters` disclosure opened from the graph-adjacent Fit band; it is closed in the normal graph view. | Successful Fit preview and the engineer opens candidate detail. | Recomputed `scalar_results` and method capability; recommendation is calculated evidence only. | Complete metrics for the row; missing diagnostics are explicit warnings. | Recommendation changes never mutate engineer selection or downstream snapshots. | calculated, recommended, selected, incomplete, warning. | Keep all rows; show missing diagnostics and require re-run rather than ranking a fallback. |
| `F-09` engineer selection, reason and acknowledgement | Make one explicit engineering decision after comparison. | Directly below the candidate table. | A selectable recomputed candidate row is clicked. | User event plus exact active preview identity; reason and warning acknowledgement are user inputs. | Selected row, non-empty reason, and acknowledgement only when that row has a warning. | `CHANGE_SELECTION` clears saved-current output, validation, review, release and delivery pointers. | null, selected-unsaved, reason-missing, acknowledgement-required, stale. | Preserve row/graph/reason on save error; refocus the missing requirement. Reason text alone never selects a row. |
| `F-10` single/blend identity | Preserve one law or both named laws and primary ratio consistently in UI, graph, API, model projection and Neutral evidence. | Candidate rows, selected-candidate evidence and saved evidence. | Metal with at least two compatible laws exposes the exact calculated preview blend as its own selectable row; polymer is single actual server result only. | Explicit row choice; fitted parameter sets for every selected law. | Distinct blend laws, ratio strictly inside `(0,1)`, both parameter sets and bounds. A preview law/ratio change must be recalculated before the blend can be selected. | Preview option change dispatches `CHANGE_PROCESS`; row choice dispatches `CHANGE_SELECTION`; either invalidates saved-current and downstream pointers. | preview-blend, selected-single, selected-blend, stale. | Keep candidate evidence; update candidates after a preview identity change, then explicitly select and re-save. Never label preview as selected or collapse a blend to its primary law. |
| `F-11` Save fit decision | Commit the exact selected decision as an immutable Processing Output revision for model promotion. | Sole Fit primary action, **Save fit & continue**, in the compact title/context row; numerical selection detail is an on-demand disclosure. | `F-09` is ready and the current server preview matches the selection. | Exact source/Profile revisions, executed steps, recomputed scalars and typed `fit_decision`. | Explicit row selection; valid identity/range/metric/parameters/reason/acknowledgement. Polymer requires `prony:{actual_term_count}` from the server result. | Successful save advances the current output pointer and leaves validation/review/release/delivery unset; later upstream change clears only current pointers. | disabled, ready, saving, saved, stale, failed. | Preflight before Artifact/revision creation; on failure create neither, retain selection and graph, show the mismatch and offer re-run/retry. |

The same exact Test Data/Processing Output revision may generate several sibling saved decisions with
different fit methods, versions, options, parameter sets or fit domains. Every sibling is immutable
and promotes to its own exact Material Model IR revision; no save mutates another sibling. Export
receives one explicitly selected IR branch and creates target-specific Solver Card revisions from
that branch. The normal surface names the selected model, while Advanced/Evidence exposes the exact
Test Data → Processing Output → selected decision/IR → Solver Card links. No run or card follows an
aggregate `latest` pointer.

### Validation and review component contracts (`V-01`–`R-04`)

| ID / component or field | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `V-01` selected candidate / Fit metric ledger | Keep a saved candidate and its fit metric visibly distinct from validation. | Top ledger of the governed Advanced or Activity surface, adjacent to governed state. | A governed validation, review, or release action is opened from Advanced or Activity. | Exact session Processing Output and selection refs; server Fit evidence. | Explicit saved candidate. | Candidate/process/material context change clears validation and all downstream current pointers. | not configured, fit-evidence-only, stale. | Preserve immutable candidate history and return to Fit to make a new selection. |
| `V-02` pinned validation inputs | Select Template and Dataset Selection revisions for one non-production OpenRadioss plan without substituting a model/card from another candidate. | Compact Validate control area under the ledger. | Metal session whose selection ID matches the server model's calibration-candidate evidence and whose IR/card refs match exact revisions. | Existing API list responses, model calibration evidence and session exact refs; no default item. | Saved candidate; exact candidate-linked Material Model IR and Solver Card; explicit Template and Dataset Selection choices. | New plan dispatches `CHANGE_VALIDATION_TARGET`; later source change clears validation/review/release pointers. | blocked, ready, pinning, pinned, not supported, error. | Retain each selected artifact and name the unavailable adapter/service/input; retry after correction. Never substitute another model from the same State. |
| `V-03` validation job and result | Submit and evaluate a supported reference runner, then expose the result verdict and holdout-independence separately from fit. | Beside the pinned plan rather than in Fit or Export. | A pinned reference plan exists. | Separate exact `validationPlan` and `validation` result session refs plus immutable plan/run/result API records. | Pinned plan; supported reference runner. | Changing validation target clears current plan/result and stales review; no historical run is mutated. | not run, queued, running, passed, failed, not evaluated, not supported. | Restore both plan and result by exact IDs after remount; keep run evidence and collect, evaluate, retry or revise the plan as the returned state allows. |
| `R-01` review/release command ledger | State Submit, Request changes, Approve and Release independently and prevent any inferred governance event. | Below the validation ledger in a governed Advanced or Activity surface. | A review or release action is opened from Advanced or Activity. | Session stale state and authoritative review-package/release-policy capability. | Immutable candidate package for Submit; submitted request for decision; passed result and approved package for Release. | Source change stales review and clears release current pointer without changing immutable history. | not configured, not run, in review, changes requested, approved, released, stale. | Link exact available context to Activity/governed harness; do not fabricate digest, policy or fallback command. |

## 1. Product character

The product is a desktop-first CAE material engineering application delivered through a browser. It must visually and behaviorally resemble a professional engineering tool rather than a marketing site, content portal or card-based SaaS dashboard.

Reference character:

- Granta MI: persistent hierarchy, compact record list, datasheet, typed links and configurable schema tools.
- Material Data Center: stable filters, comparable results, selected material context and direct CAE delivery.
- Material Modeler: persistent engineering plot, compact curve navigator, task-specific controls and direct card export.

The product must not copy commercial branding, exact colors, icons or proprietary geometry.

## 2. Global shell

### 2.1 Vertical structure

```text
Application frame
├─ Menu bar                  28 px
├─ Command bar               36 px
├─ Workspace                 remaining height
└─ Status bar                24 px
```

The current 60 px brand-centric header is retired.

### 2.2 Menu bar

Content:

```text
File | Materials | Modeling | View | Tools | Help
```

Right side:

- workspace name;
- current user;
- connection state.

The product logo is limited to a compact 20–24 px mark. No subtitle or marketing description is shown.

### 2.3 Command bar

The command bar changes with the active workspace.

Examples:

Materials:

```text
Search field | Search | Browse | Compare | Columns | Refresh
```

Modeling:

```text
Open data | Save session | Undo | Redo | Fit | Export | Advanced
```

Commands use compact icon-plus-label controls. Only the task-primary command uses a filled accent treatment.

### 2.4 Status bar

Always visible. Shows:

- current selection;
- record count or selected curve count;
- unit system;
- active revision or `Draft` state when relevant;
- background job state;
- warnings/errors count.

Technical identifiers remain available through a status-bar disclosure or Evidence, not as default body text.

## 3. Shared dimensional system

### 3.1 Typography

| Role | Size | Weight | Use |
| --- | ---: | ---: | --- |
| Compact application/menu | 12.5 px | 500 | menu and command labels |
| Compact data/body | 13 px | 400 | tables, forms, descriptions |
| Compact metadata | 11.5–12 px | 400 | units, source, secondary state |
| Compact pane title | 13.5–14 px | 600 | navigator and inspector headings |
| Compact page/workspace title | 16 px | 600 | one title per workspace |
| Compact dialog title | 16 px | 600 | modal only |

Weight 650 or above is not used for ordinary rows, buttons or explanatory text.
Shared high-DPI display tiers may increase these sizes and the matching control, row, spacing, pane,
and plot tokens only after actual Windows 4K comparison. Route-specific scale values are forbidden.

### 3.2 Spacing

Base scale:

```text
2, 4, 6, 8, 12, 16, 24 px
```

Rules:

- default pane padding: 8 px;
- dense form/group padding: 6–8 px;
- workspace outer margin: 0–8 px;
- section gap: 8–12 px;
- 24 px is reserved for dialogs or empty states;
- 32 px and 48 px are not used in normal engineering workspaces.

### 3.3 Shape and surface

- persistent panes: no radius;
- tables and property sheets: no radius;
- splitter: 4 px hit area, 1 px visual divider;
- inputs and compact controls: 2–3 px radius;
- popovers/dialogs: 4 px radius;
- shadows: overlays only;
- no gradients;
- no nested persistent cards;
- selection uses a flat background plus a 2–3 px accent edge.

### 3.4 Wide-screen allocation

Responsive layout uses semantic elasticity rather than uniform scaling:

- `bounded rails`: navigator, object list, compact setup controls and property forms keep readable
  widths and density;
- `elastic results`: graph, data grid, native solver-card preview and real datasheet/Record preview
  grow only to a useful reading or interaction bound, never solely to consume remaining pixels;
- `companion evidence`: a wide-only adjacent region is permitted only when it projects the current
  Layout, Record, mapping, curve or workflow contract and remains synchronized with the selection;
- `full shell, adjacent task regions`: the shell spans the viewport and related components remain
  adjacent with the normal divider or gutter. A bounded region uses balanced remaining gutters or a
  truthful adjacent task region; the complete task does not stay as a one-sided 1920 px island;
- `no filler`: repeated descriptions, decorative summaries and fabricated engineering fields never
  occupy a wide region;
- `no forced fill`: modest balanced whitespace is permitted after truthful task content reaches its
  useful bound; a dominant trailing void caused by a global cap, stretched controls, rows, prose,
  plots or previews are not responsive solutions;
- `plot geometry`: render width and height, viewBox, axes, ticks, paths and hit regions share one
  recomputed coordinate system. CSS must not stretch an SVG differently on each axis.

Registered #167 static targets remain 1366×768, 1440×900 and 1920×1080. Every user-visible React/CSS
change also records deterministic 2560×1440 and 3840×2160 live evidence and obtains product-owner
disposition before merge. These captures do not rewrite the static inventory; #184 separately records
actual Windows 4K 100%, 150%, and 200% physical readability.

## 4. Materials workspace

### 4.1 Layout

At 1440 px:

```text
Navigator 264 px | Result grid 856 px | Inspector 280 px
```

At 1366 px:

```text
Navigator 244 px | Result grid dominant | Inspector collapsed
```

At 1920 px:

```text
Navigator 280 px | Result grid 1292 px | Inspector 300 px
```

Navigator and inspector are resizable. Minimum and maximum widths:

- navigator: 200–360 px;
- inspector: 260–480 px.

### 4.2 Navigator

Tabbed modes:

```text
Browse | Filters | Subsets
```

The navigator owns the mode control. Plain `/materials` opens Browse; a Find preserves the current
mode. Filters contains only facets present in the same server query, without availability
explanations for unavailable projections.

Browse mode contains:

- Database/Profile/Table selectors;
- local tree search;
- compact 24–26 px rows;
- node glyph, disclosure and label on one grid row with a shared vertical center;
- full keyboard navigation;
- independent scroll;
- concise stored identities rather than qualification prose repeated in every node;
- a reserved, perceptually visible vertical rail when rows overflow and a horizontal rail only when
  a genuine stored identity overflows. Pointer, wheel and keyboard interaction must operate the
  local pane, and neither rail may cover text.

Subsets mode displays saved subsets as compact rows, not cards.

### 4.3 Result grid

The result grid is the dominant area.

Default columns:

- Material/Grade
- Family
- Description
- Status

Compare remains a local row-selection feature. Provider/source, validation, card readiness and
condition-aware properties are absent until the server-scoped response provides them.

Behavior:

- resizable columns;
- sortable headers;
- sticky header;
- row height 32–36 px;
- single click selects;
- double click opens datasheet;
- row checkboxes support local comparison without a duplicate global command;
- column chooser stores user preference.

No explanatory banner is displayed above the grid. Search state stays in the query bar and the
server result count stays with the result grid.

Large-display normal evidence uses a complete scoped server page when the response provides one.
The current Material search page limit is 50 rows. A smaller genuinely returned final page may
remain sparse, but a six-row synthetic fixture must not be used to excuse avoidable blank space at
1920×1080, 2560×1440 or 3840×2160.

### 4.4 Inspector

The selected-material inspector contains:

- identity and grade;
- description when supplied by the same Material result;
- Family and user-facing Status;
- primary command: Open Datasheet.

Key properties, condition summary, card availability and a preferred-card command appear here only
after the same server-scoped query projects their quantity/condition semantics, unit, source revision
and readiness state. Until then they are absent rather than rendered as `Not projected`, inferred by
client enrichment or replaced by a Modeling command. The datasheet remains the governed place to
inspect those details and start a supported downstream task.

## 5. Material Datasheet workspace

### 5.1 Layout

```text
Optional Tree/List 240–320 px | Datasheet flexible
```

The selected Record stays in context. Opening a record does not replace the entire application shell.

### 5.2 Datasheet tabs

```text
Overview | Properties | Curves | CAE Cards | Related | Evidence
```

`Related` is a first-class tab rather than being hidden inside Evidence.

### 5.3 Property sheet

Properties are presented as a compact property grid:

```text
Property | Value | Unit | Condition | Source
```

- row height 30–34 px;
- groups use collapsible headers;
- editable values use in-cell or right-side property editor;
- original and normalized unit/value can be toggled;
- administrator-defined Layout order is preserved.

### 5.4 Representative response

The Overview response plot and any wide-screen point grid are two projections of one ordered linked
series. The grid uses `Point | Engineering strain | Engineering stress (MPa)` for the current
synthetic metal reference and changes its quantities and units with the response family. It appears
at 1920×1080 and above only when it can sit beside a still-dominant plot. Its rows are exact source
points, not sampled pixels or fitted/interpolated values. Real overflow gets an independent visible,
proportional and keyboard-operable local scrollbar; when every row fits, no decorative rail remains.

### 5.5 Related and workflow

The Related tab contains two synchronized views:

- typed link list;
- optional workflow/relationship graph.

Selecting a relation changes the adjacent context without navigating away. Forward/reverse labels, target type and exact revision are visible in the detail row.

## 6. Modeling workspace

### 6.1 Stable layout

```text
Curve/process navigator 184–210 px | Plot flexible
```

The plot must remain visible and dominant through Process and Fit and stay available where Data or
Export needs visual source/model context. A permanent right inspector is forbidden. Current controls
use one shallow graph-adjacent band; advanced or numerical evidence opens only in a drawer or
disclosure. Validation and review/release are governed Advanced or Activity paths, not normal-path
workspace columns.

### 6.2 Task strip

The normal modeling path appears as one compact strip:

```text
Data | Process | Fit | Export
```

They are not large buttons, numbered tiles or cards. The visible strip keeps only the task name;
the accessible label/title provides concise readiness or recovery context. New session starts at
Data; resume restores the last saved normal-path task and graph-view state. Validation and review
remain distinct states and actions, but are reached through Advanced or Activity.

### 6.3 Navigator

Rows are 24–26 px and support:

- calculation-membership checkbox;
- curve-type glyph;
- short label;
- exact revision suffix;
- separate icon-only plot visibility.

The rail shares the Materials navigator's flat desktop grammar without copying its catalog topology:
sentence-case section headings, regular 12–13 px identities, aligned disclosure/type marks, a clear
parent-to-child indent, restrained selected-row fill and one leading accent. The title/count pair and
filter use the same spacing rhythm as the row list. A curve color sample is a narrow line rather than
a decorative badge, and the exact revision is visually secondary. At the minimum pane width, the
specimen identity, inclusion checkbox and visibility control must remain distinct and unclipped.
Overflow remains local and produces a discoverable conditional scrollbar without changing plot
width.

Source paths, UUIDs and detailed metadata appear in a properties inspector, not inside each row.

### 6.4 Plot

Plot requirements:

- minimum 72% of workspace width at 1440 px;
- the normal curve legend is a compact plot-internal overlay in a measured curve-free quadrant,
  lower-right when clear; it moves to another safe quadrant as data changes and docks outside only
  when no collision-free internal placement exists;
- legend placement must not intersect data, boundaries, axes, labels, state overlays or selection
  feedback, and it must not reserve a permanent column beside the plot;
- direct range/point selection;
- observed, processed, fitted and extrapolated styling is consistent;
- response, residual and derivative/tangent views use plot tabs;
- cursor coordinates and selected point/range appear in status bar;
- toolbar supports Zoom, Pan, Fit view, Select range and Export image.

### 6.5 Current-task control band

Only current-task controls are shown in the shallow graph-adjacent band or an on-demand disclosure;
there is no permanent inspector column.

Process examples:

- include/exclude;
- crop range;
- smoothing;
- resampling;
- mean/band.

Fit examples:

- candidate model;
- parameter values/bounds;
- objective and residual summary;
- extrapolation limit;
- Apply selected model.

Controls use property-editor rows, not independent cards.

### 6.6 Export

Export uses a two-pane layout:

```text
Destination + Export check 300–340 px | Solver Card result workspace flexible
                                       | preview dominant + bounded read-only Mapping/Fit source
```

`Create solver card` is the task-primary command before creation; `Open solver card` replaces it
after creation. The result workspace may use a bounded secondary read-only column, but it never
becomes a third control inspector. Mapping warnings remain visible beside their source/target
consequence. Detailed mapping JSON, technical status values, revision IDs and receipt mechanics are
under Advanced or Delivery details.

## 6.7 Canonical component contracts (UXC-00R target)

These contracts cover the current Administration and Activity surfaces plus their remaining
projections. The three-pane Administration workspace (PR #143), Reviewer product-role access,
role-aware Activity queue (DUI-08A), exact Material/Solver Card request entry (DUI-08B), and
legacy review-workbench cleanup (DUI-09A) are implemented. Only failed-job recovery, server delivery
receipt, and release projections remain separate work.

| Component | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Materials explorer/result/datasheet | find, compare and assess a material without leaving context | continuous Tree/filter → dominant results/datasheet → optional context | Materials | one scoped Material query plus selected record | permitted scope | query/selection changes replace only current view | loading, empty, selected, unavailable, error | retain query/selection; retry or broaden search |
| Administration object tools | configure schema and preview its user effect | object tree → list/grid → property editor/live record preview | Administrator | revisioned catalog definitions | Administrator permission and valid draft | draft edits invalidate preview only | clean, dirty, validating, blocked, saved, error | keep draft; expose field error; reload or save new revision |
| Activity action queue | resume work or decide one submitted review action without confusing it with release | compact `Needs attention | In progress | Recent outcomes` rows | User sees own pending review work in progress; Reviewer sees pending review rows in Needs attention; every role sees saved local session/card history | authenticated principal plus effective product access and immutable review-request response, including the requester display-name snapshot; browser-local session/card history | readable available context and an existing request manifest for a decision | returned immutable response replaces only that queue row; later source changes never erase history | loading, attention, in-progress, changes-requested, approved, empty, error | Refresh/Retry preserves the current rows; a decision failure keeps entered reason and request; exact identifiers remain Advanced while the normal row uses the supplied requester label |
| Role-gated command | expose only the action a role may take | command bar, selected row, or governed action disclosure | role and object state permit action | service authorization plus database enforcement | User/Reviewer/Administrator grant and state prerequisites; only Reviewer may decide | action input changes mark downstream pointers stale | hidden, available, disabled-with-reason, running, denied | preserve context; explain prerequisite or request review/access |

Role target: **User** searches/views/downloads, requests upload review, processes/fits and requests
card review; **Reviewer** additionally reviews material/card data, requests changes, approves and
publishes downloads; **Administrator** has access/edit/configure and recovery actions but cannot decide
another user's review request. Current
implementation exposes User, Reviewer, and Administrator task presets. Internal RBAC/RLS remains
extensible and is not a normal-user vocabulary; future failed-job, receipt, and release projections
remain separate from the implemented Activity and Administration workspaces.

## 7. Administration workspace

### 7.1 Layout

```text
Object navigator 220–280 px | Object list 280–420 px | Property editor flexible
```

Objects:

- Databases
- Profiles
- Tables
- Attributes
- Layouts
- Subsets
- Link Types

Administration must resemble a schema/property editor, not a landing page with task cards.

### 7.2 Editing contracts

- Table selection updates Attribute/Layout/Subset/Link Type lists in context;
- Add/Edit/Duplicate/Delete are command-bar actions;
- the Object list is a compact selector: its Name cell contains only identity, Table rows use
  `Name | Rev`, Attribute rows use `Name | Value type | Rev`, and full description/quantity/unit/help
  remains in the property editor;
- Attribute editor is a structured property sheet;
- Layout editor supports ordered rows and drag/reorder commands;
- Link Type editor displays source table, target table, direction labels, cardinality and revision binding;
- preview opens the real datasheet alongside the editor.

### 7.3 Current DUI-07 capability boundary

The service contracts can create Tables, typed Attributes, ordered Layouts, saved Subsets and Link
Types, and can append immutable revisions to their stable identities. The current PR #156 product
route wires the supported **Add** commands and datasheet preview but does not yet wire every revise
operation. The #167 target reference may show a contract-backed Edit draft for the later React port,
but the same bundle must also exercise Add Table and Add Attribute as real right-pane draft states.
It must not show Duplicate, Delete, Publish or reorder commands until their complete live workflow is
implemented. Attribute fields are conditional on the selected type: numeric meaning/unit, discrete
choices, and related Table do not occupy the normal property sheet unless applicable.

Current visible-field contracts:

| Component | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Object navigator | change the schema object being inspected | 220–280 px left pane | Administrator in Database design | current Table and definition lists | readable Administration scope | changes the list/detail selection only | loading, empty, selected, error | retain Table selection; refresh |
| Current table | scope Attributes, Layouts and Subsets to one Table | navigator footer | one or more Tables exist | configurable Table API | selected Table | replaces scoped lists and selected detail only | loading, selected, empty, error | restore last valid Table or choose another |
| Object list row | identify and select one schema object without duplicating its property sheet | 280–420 px center pane | one or more objects exist for the selected family/scope | current definition list response | readable object identity | changes only selected detail | selected, unselected, long identity, empty | keep identity reachable; remove non-decision prose rather than compressing it |
| Property sheet | inspect a definition or provide values for one supported new definition | flexible right pane | selected object or Add command | immutable definition revision and local draft | Administrator and required fields | unsaved draft affects preview only; save creates a new definition | read-only, draft, saving, saved, blocked, error | preserve draft and field error; close or retry |
| Record/Layout preview | verify that the saved Record uses the ordered exact Attribute Definition revisions selected by its Layout | one active `Record preview` or `Layout definition` view; compact widths use a reversible full-height auxiliary surface, 1920+ may use a bounded companion pane | a saved Record and Layout exist for the selected Table; linked graph only when a curve/table Artifact field exists | saved Record Revision, Layout Revision and exact Attribute Definition Revisions | selected Table and readable saved projection | local draft never mutates the saved preview; selection changes replace only the current projection | record, layout-definition, genuine-overflow, no-saved-record, linked-curve | keep editor context and return action; expose independent table scrolling; retry the read without discarding a draft |
| Link Type direction | make a record relationship understandable before saving | Link Type property sheet | Link Type selected or being added | selected source/target Table revisions | both Tables and direction/cardinality values | saving creates a new Link Type; no existing relation changes | read-only, draft, saving, saved, error | keep entered labels and retry |

## 8. Activity workspace

Default view is a compact work queue:

```text
Task | Request reason | Status | Updated | Action
```

Reviews, jobs and releases are tabs or saved views. No dashboard cards or large summary tiles in the normal view.

The current review response supplies an immutable requester display-name snapshot. The table does not
invent Material labels; it uses the request task type, supplied requester label, and human reason while
exact object names remain in the governed detail view. User-owned pending requests belong in `In progress`;
Reviewer decision work belongs in `Needs attention`; Administrator sees their own pending requests in
`In progress` without decision controls. The role-appropriate view is the
default selected tab.

The normal reference exercises a representative page from the existing 50-request list contract.
The table body scrolls locally with a visible reserved track only when rows overflow. Row height and
type remain compact at every viewport; larger displays reveal more complete rows and do not stretch
the table, repeat prose, introduce KPI cards or fabricate receipt/release history. Browser-local
Modeling resume and solver-card history stay distinguishable from immutable server review requests.

### 8.1 Review request entry (DUI-08B)

| Component | purpose | placement | visible_when | source | requires | invalidates | states | error_recovery |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request review | ask for review of the exact Material revision currently displayed | Material detail header action area; reason expands only after the action is chosen | Material detail has loaded a draft current revision with no request; non-draft and requested revisions show status only | `material_id`, current revision id/content hash/classification/lifecycle | successful duplicate check and non-empty human reason | none; a request never changes the Material revision | checking, ready, entering reason, waiting, approved, changes requested, non-draft, sending, error | a failed duplicate check blocks submit and offers Retry status; a failed submit retains reason and offers Retry request |
| Request review | ask for review of the exact Solver Card revision currently previewed | Native Card Preview header action area; reason expands only after the action is chosen | card evidence has loaded a draft current revision with no request; non-draft and requested revisions show status only | `loadSolverCardEvidence` current revision id/content hash/classification/lifecycle and authoritative aggregate type | successful duplicate check, non-empty human reason and loaded card evidence | none; a request never changes the card or delivery state | checking, ready, entering reason, waiting, approved, changes requested, non-draft, sending, error | a failed duplicate check blocks submit and offers Retry status; a failed submit retains reason and offers Retry request |

Both controls query `aggregate_type + aggregate_id + revision_id` first and do not expose IDs, hashes,
classification or a decision control in the normal UI. Material uses `catalog.material`; Solver Card uses
`exporting.solver_card` (or `exporting.neutral_solver_card` for a Neutral card). Approval and
changes-request controls remain Reviewer Activity work.

## 9. Legacy removal contract

The following visual patterns are prohibited in active product routes:

- `.page-stack` as a normal workspace shell;
- `.page-heading` with marketing-style description;
- `.content-card` for ordinary sections;
- `.module-material-card` and task-card grids;
- persistent `.eyebrow` copy above every heading;
- pill badges for ordinary metadata;
- repeated large empty-state cards;
- nested bordered panels;
- large primary buttons for secondary navigation.

Existing legacy routes may retain compatibility redirects but must render canonical workspaces.

`/jobs-reviews` is one such compatibility route: it renders the Activity action queue and does not
render a raw aggregate/revision/hash request form or standalone decision control. `/governance`
remains an Advanced operations route for Operations, Release and Governance Evidence; it is not a
second review-entry workspace.

## 10. Acceptance gates

A route passes only when all are true:

1. The first viewport contains the main data/plot area, not introduction copy.
2. Persistent panes are flat and resizable where required.
3. No normal body text is larger than 13.5 px.
4. No normal workspace uses 24–32 px internal padding around every section.
5. There is at most one filled primary command per task context.
6. The route has no nested persistent cards.
7. Keyboard navigation covers menu, command bar, navigator, grid and tabs.
8. The status bar reports current selection and state.
9. 1366, 1440 and 1920 layouts pass without page-level horizontal overflow.
10. Tree, Attribute/Layout/Subset/Link Type, revisions, provenance and solver-mapping contracts remain intact.
