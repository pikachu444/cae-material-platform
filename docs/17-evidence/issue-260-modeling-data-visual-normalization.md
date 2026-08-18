# Issue #260 — Modeling workflow semantic visual normalization

This record covers the owner-approved FE-05 candidate under parent issue #249. The initial bounded
unit was Modeling **Data**. Direct product-owner review then required the same restrained hierarchy,
plain language, flat engineering grammar, and wide-screen composition to be carried through the
visible **Process, Fit, and Export** surfaces touched by the candidate. Work started from fetched
`origin/main` `4f753deaeb4dae9dc48ea2c63fd313c6fe5e7b01` on `issue-260-fe05`.
The approved MOD-DATA, MOD-PROCESS, MOD-FIT, and MOD-EXPORT workflow references still control
preserved behavior; the owner's later screen comments control where an older reference reproduces a
known comprehension or visual defect.

## Product-owner discussion checklist — controlling correction authority

**Current disposition: IMPLEMENTED CANDIDATE VERIFIED; PRODUCT-OWNER SCREEN APPROVAL PENDING.**
This checklist records the owner's direct feedback from the current #260 review. It controls over a
  conflicting or stale MOD-DATA screenshot. The latest production implementation passed the first-time-engineer
  review. A late owner check then found two remaining visual inconsistencies; both are corrected and
  the refreshed exact candidate passed its final Balanced re-audit with blocker 0, major 0, and
  material-minor 0.
  This record does not claim final product-owner
  approval or publication authority.

### Review method and visual baseline

- [x] Treat the owner's current instruction and this discussion as higher priority than a conflicting
  registered reference. Record and update a stale reference instead of reproducing its defect.
- [x] Keep the mockup phase limited to design, wording, layout, and interaction comprehension. Diverse
  example data stress-tests the layout; it is not evidence that the production database was tested.
- [x] During mockup review, show only `1920×1080` and `1440×900` unless the owner asks for another
  viewport. Run the full five-viewport and production-data gates only after the design is accepted.
- [x] Do not continue changing a screen after presenting it while the owner is reviewing it. Apply the
  next correction only from the owner's next instruction.
- [x] The owner-confirmed direction is preserved in
  [1440×900](images/issue-260-fe05-modeling-data/owner-reference/modeling-data-approved-direction-1440x900.png)
  and
  [1920×1080](images/issue-260-fe05-modeling-data/owner-reference/modeling-data-approved-direction-1920x1080.png).
  It authorizes the flat search/filter/browser → result → graph flow and overrides stale reference defects.
- [x] Explicitly judge all three #249 axes: Carbon-level hierarchy and alignment, COMSOL-style compact
  engineering flow, and SAP-style full-viewport/responsive composition.
- [x] Require an independent first-time-engineer review of the whole screen, not merely a check of the
  problems already named by the owner.

### First-use task flow and selection model

- [x] A first-time engineer can tell, without instructions, that the screen selects test data for
  Modeling and then proceeds to Process.
- [x] The normal flow is visually unambiguous: choose a material, choose a test type, narrow the
  compatible tests, choose one current input curve, inspect it, then continue. Additional linked
  curves may be overlaid for comparison without becoming joint Process inputs.
- [x] Remove the visible `Material state` field. Do not reintroduce it as a normal-surface selector or
  repeated subtitle. Preserve required exact state internally and in technical evidence only.
- [x] Show the selected material, test type, and selected test identity clearly enough that the user
  never has to infer what material or experiment the graph represents.
- [x] Use one normal selection surface. Do not require selecting a specimen in both a tree and a
  second central table, and do not show a preview for a different specimen.
- [x] Restore an exact upstream/session selection when it exists, but never silently select the first
  material, first test, latest revision, or first included curve as a fallback. A genuinely empty/new
  session must visibly wait for an explicit input-curve choice.
- [x] Preserve #158 Data's approved **one-or-more exact Test Data records** linking contract without
  misrepresenting the downstream calculation. Process receives one focused exact Test Data source;
  Fit receives one exact saved Process Output. Multiple linked curves are session/comparison state,
  not one combined Process/Fit input.
- [x] Treat that contract as required behavior and preserved state, not as permission to expose every
  checkbox, count, eye, revision, and duplicate row on the normal surface. Keep the confirmed clean
  visual baseline; reveal compact graph comparison only when the engineer deliberately enters that
  task after narrowing the result set.
- [x] Make the one row selected for inspection also be the current Process input. Selecting another
  row changes that exact input and invalidates downstream current pointers; it must not be confused
  with adding a comparison overlay.
- [x] Make optional comparison understandable without turning every large result list into a bulk
  checklist. The engineer first narrows the collection, then opens `Compare curves` and chooses only
  the additional curves needed on the graph.
- [x] Keep graph visibility independent from the current Process input. Comparison visibility changes
  no engineering state, while the current input remains visible and is the only source sent forward.
- [x] Bound graph comparison to five named curves. At the limit, never evict a deliberately added
  overlay silently. Replacing the current input may retire only the previous current input; any action
  that would exceed five curves requires the engineer to remove one first.
- [x] Do not show cryptic summaries such as `Process 2 · Plot 3` or bare `Use` / `Show` headings. In
  comparison mode, use the short `On graph` label and keep the singular `Continue to Process` action.
- [x] Do not expose two competing primary actions such as `Use as modeling input` and
  `Continue to Process`. After a valid choice there is one clear next action.
- [x] Keep `Import file` available and visibly separate from saved test data. Do not make local-file
  support disappear while simplifying the saved-data path.
- [x] Do not redesign the Materials page or change the platform navigation as part of this Data-screen
  mockup. Preserve the Materials-to-Modeling connection.

### Large and varied test collections

- [x] Exercise long material names, several material families, several test types, repeated specimen
  names/dates/conditions, and hundreds or thousands of test records in the mockup.
- [x] Let users narrow a large collection by material, test type, search, and useful filters before
  touching individual rows. Nobody should need to check one thousand records one by one.
- [x] Keep the result count data-derived and clearly associated with the current search/filter. Never
  invent a fixed `4 records` count or style a count as status.
- [x] Paginate or virtualize long results, preserve selection during navigation, and keep scrolling
  local to the explorer. No page-level overflow or awkward clipped right-hand scrollbar is allowed.
- [x] Keep list/table headings short enough to stay on one line at the approved density. Do not allow
  long action-like column titles to make rows grow unpredictably.
- [x] Make row padding and text baselines visually even. The selected row may be emphasized, but its
  top/bottom spacing must not look accidental.

### Wording and information hierarchy

- [x] Every visible line must be one of: a field name, current choice, result, real status, blocker,
  recovery action, or engineering interpretation. Delete helper copy that merely restates a nearby
  heading or control.
- [x] Do not add explanatory prose to make a confusing layout appear understandable. Fix the grouping,
  naming, alignment, and action order instead.
- [x] Remove repeated normal-state subtitles and default status noise, including material/test text
  already shown nearby, `available`, `review required`, `No active job`, `0 warnings`, and `Online`.
- [x] Do not show `Test Data linked to this material` when the surrounding title already says it.
- [x] Keep ordinary metadata neutral. Counts, material family, source kind, and dates are not success
  badges or status chips.
- [x] Keep technical identifiers and audit vocabulary off the normal surface: `r1`, `observed*r1`,
  `Evidence`, `provenance`, UUIDs, record keys, checksums, Mapping Profile, Recipe/Batch, raw headers,
  and source-system labels such as `CMP DEMO` belong in Technical details/Evidence/Administration.
- [x] Never append a revision to the display name. Exact revision remains preserved for reproducibility
  but is visible only when the user opens technical details or an explicit revision action is required.
- [x] Do not display vague labels such as `Available`, `Original file data`, `Long channel name`,
  `CSV header row 1`, or `Reason for correction` without a direct decision or recovery consequence.
- [x] Use `Specimen` only as the experiment specimen identifier, never as a material name. Show enough
  surrounding material/test context that `Specimen 03` cannot be mistaken for the material.
- [x] Put units only where they qualify an engineering value or graph axis. Do not present units as
  badges, transformation status, or unexplained metadata.
- [x] Use plain source names that describe the choice: saved test data versus importing a local file.
  Do not present unexplained `Workspace`, `Local file`, and `JSON` as three equivalent product concepts.

### Import-file surface and recovery

- [x] Use one aligned file chooser. Do not stack or repeat `File`, `Choose file`, `No file chosen`, and
  extension lists in mismatched boxes.
- [x] After a file is checked, show only the tests the user can choose and one explicit apply action.
  Do not change the graph merely because a file was picked.
- [x] Put column mapping, original bytes/rows, raw headers, correction reason, and provenance under a
  collapsed technical disclosure unless a mismatch requires an immediate decision.
- [x] On an invalid mapping, show one concise cause and one recovery action; preserve the last valid
  graph and the user's recoverable file/selection.
- [x] Give the Import panel its own discoverable local scroll when its required controls exceed the
  pane. No clipped controls or unreachable content is acceptable.

### Visual grammar and graph

- [x] Start from flat panes, alignment, and dividers. Do not reintroduce nested cards, decorative
  backgrounds, repeated eyebrow labels, shadows, or non-status badges.
- [x] Use one corner policy. Inputs, selects, disclosures, buttons, and technical panes must not mix
  arbitrary rounded and square treatments.
- [x] Keep controls compact, aligned, and adult/professional: restrained height, balanced vertical
  padding, consistent font baseline, and no thick or childlike spacing.
- [x] Use a neutral application/plot background. The graph must not resemble yellowed paper or a
  scanned image.
- [x] Scale the graph from its engineering data and useful comparison task, not merely from available
  pixels. Avoid an awkward oversized curve, crushed axes, unrelated void, or position-only correction.
- [x] At wider viewports, let the plot use additional space when it improves comparison while keeping
  the explorer and controls readable. Do not stretch every row or create fabricated filler.
- [x] Keep Technical details collapsed by default, aligned with the same flat grammar, reachable, and
  unclipped. Opening it must not depend on an unexplained splitter trick.

### Preserved production contracts and publication boundary

- [x] After visual approval, preserve exact revision/session, Data→Process→Fit→Export continuity,
  splitter persistence, reload recovery, last-valid graph, saved result, and Materials read-back.
- [x] Do not change backend, API meaning, request payload, saved format, database, or public React
  contracts for this visual unit.
- [x] After production implementation, test the approved design with real repository data and the
  required empty, large, varied, invalid, recovery, keyboard, scroll, and reload states.
- [x] Do not stage, commit, push, create a PR, mark Ready, merge, or close #260 without the separately
  required owner approvals.

## Starting-state classification

| Area | Starting status | Candidate outcome |
| --- | --- | --- |
| Exact Data behavior and persistence | Complete | Preserved: exact revisions, Include/Show independence, keyboard browsing, splitter persistence, reload, last-valid graph, and recovery. |
| Information hierarchy | Partial | Revision/count/family facts use neutral metadata; only real success, blocker, error, and recovery states use status emphasis. |
| Source selection and technical detail | Partial | Library and Local file are separated into the normal task flow. Exact revision, source identity, and mapping details remain reachable in the collapsed Technical details surface. |
| Process/Fit/Export visual continuity | Partial | One focused Process input, one exact saved Fit input, and one selected Export model are now explicit; optional comparison and technical evidence no longer compete with the primary task. |
| 2560/3840 composition | Missing | The shell remains full-width; readable task controls are bounded while Data, Process, Fit plots and the Export native preview use additional space only where it improves engineering comparison. |

## Reference interpretation

The MOD-DATA, MOD-PROCESS, MOD-FIT, and MOD-EXPORT inventories remain the source for preserved
workflow and exception-state coverage.
Where its pixels conflict with the owner's later comments, the two owner-approved direction images
above control. The implementation therefore keeps Library and Local file, exact selection, recovery,
and the persistent graph while replacing the stale duplicate-selection, technical-copy, card, and
always-on comparison presentation.

## Parent #249 inherited-unit review

| Parent unit | Result | Exact evidence in this candidate |
| --- | --- | --- |
| FE-00 — authority and routing | PASS | Root `AGENTS.md` and the frontend principles now require the Carbon/COMSOL/SAP synthesis, the parent issue and roadmap, and explicit owner-feedback precedence over a stale screenshot. |
| FE-01 — architecture guards | PASS | The actual frontend guard reports 0 violations and 15 unchanged inherited warnings. The registered Common Workbench change uses the issue-owned Data workspace/model/related-data extraction and a fingerprinted bounded exception rather than adding an unregistered responsibility. |
| FE-02 — semantic primitives | PASS | Existing typography, surface, notice, action, token, divider, disclosure, and selected-row roles are used. No new raw color, decorative card/eyebrow, non-status chip, shadow grammar, or route-specific 4K scaling is introduced. |
| FE-03 — Modeling characterization | PASS | Regression coverage preserves exact source selection, one current Process input, comparison independence, downstream invalidation, session/reload restoration, splitter state, last-valid graph, blocked recovery, save, Export, and Materials read-back behavior. |
| FE-04 — behavior-preserving extraction | PASS | Data-owned model, related-data resolver, workspace, and CSS remain behind the existing workbench/layout interfaces. The full 406-test frontend suite, focused 130-test set, and final 70-test graph/workbench/Process/Fit rerun pass without API, public type, route, or storage changes. |
| FE-05 — semantic visual normalization | PASS | The owner-approved selection structure, restrained normal surface, optional comparison, compact flat grammar, and balanced five-viewport composition are fixed in the 208-file visual packet. The late comparison-color and peer-heading-width corrections passed live five-viewport measurement and final independent re-audit with blocker 0, major 0, and material-minor 0. |

## Implemented scope

- Library is a compact search, test-type/condition filter, browser, paged result table, one current
  input, persistent graph, and one `Continue to Process` flow. A 1,000-row varied fixture verifies
  that large collections do not become a bulk checklist.
- Comparison is absent from the default flow. `Add comparison` is available only after a valid current
  input, keeps the current Process input distinct, and permits at most five named graph curves without
  silently evicting one.
- Local file is a separate source. The empty state keeps the chooser adjacent to the graph. A mapping
  failure puts its cause and repair at the decision point, hides premature save/update actions, keeps
  local scrolling, and preserves the last valid graph. Saving the imported record replaces the one
  current Process input without converting the previous input into a comparison curve.
- Related data contains only records returned by the selected Test Data's real workflow graph. It groups
  available Technical Data, Test Data, Simulation Data, and Solver Cards without exposing CMP/demo
  source prefixes or inventing empty categories.
- Normal surfaces no longer expose material state, revision suffixes, provenance/evidence vocabulary,
  source-system labels, repeated helper prose, or status-like counts. The graph heading names the
  current material and test record; exact technical state remains behind the collapsed details surface.
- The Data-owned flat/square CSS keeps the explorer and form readable while the graph uses a useful
  comparison bound on wide displays. Technical details immediately follows the graph instead of being
  separated by an internal void.
- Exact restoration requires the recorded identity and revision. There is no first-item or latest-item
  fallback, and comparison visibility does not invalidate Process/Fit state.
- Process shows one current Test Data input and treats additional curves as graph comparison only.
  Compact ordered steps, preview, save action, and exact saved-result handoff remain unchanged.
- Fit shows one exact saved Process result, four ordered engineering steps, compact candidate/range
  controls, the persistent response graph, and one explicit save-and-continue action. Candidate laws
  remain alternatives; they are not presented as several Test Data inputs.
- Export uses a flat setup / native preview / mapping-and-fit workspace. Ordinary status and recovery
  language is plain, exact technical identity remains collapsed, and the blocked state exposes one
  cause and one preparation action without prefilled internal wording.
- All four stages share the same square, divider-led, shadow-free grammar and the same full-viewport
  responsive policy. Readable controls stop growing while plots and the native solver-card preview
  receive the useful wide-screen space.

No backend, API path/payload, DTO, database, saved document, browser session shape, public React
interface, or Modeling workspace layout contract changed.

## Independent visual corrections

The first read-only review requested four corrections: remove the wide/empty internal void, distinguish
Browser scope from the current input, hide comparison in an empty state, and place invalid-mapping
cause/recovery before the controls. The final implementation includes all four. After the current-input
and Related-data semantic corrections, the same reviewer reopened the latest 1440/1920/3840 originals,
all five viewport crops, and the three exception states. It reported no blocker, major, or material-minor
 finding and judged the Library/Local file → current input → graph → Process flow understandable to a
 first-time engineer. A separate final Balanced auditor then required fresh Process/Fit regression evidence
 after the Data-only graph guard correction. The 130 focused tests and 15-stage browser consistency capture
 pass against the exact candidate; a final post-correction run of the four directly affected graph/workbench/
 Process/Fit files also passed 70 of 70 tests. The auditor then returned PASS with blocker 0, major 0, and
 material-minor 0. The owner subsequently flagged two details that were not acceptable despite that pass:
 the inherited teal `Add comparison` color and mismatched Browser/Related data heading widths. The same
 auditor reopened the candidate and classified both as material-minor findings. The correction uses the
 Modeling action color and moves the Browser scrollbar gutter into its list so the peer headings align;
 the live five-viewport flow now measures both conditions directly. The final exact-candidate re-audit
 returned PASS with blocker 0, major 0, and material-minor 0.

## Browser resource-exhaustion diagnosis and correction

The first candidate validation intermittently logged Chromium
`net::ERR_INSUFFICIENT_RESOURCES`. Diagnosis continued against the preserved Compose data:

1. The closed `Saved outputs` disclosure always mounted all 678 output articles, including one
   `DomainWorkflowLinks` instance per output, even while Data/Process/Fit CSS hid the disclosure.
2. Each instance immediately resolved its exact Catalog binding. React development `StrictMode`
   ran the effect setup twice, so a clean Data mount started 1,356 jobs at once.
3. Before correction, 1,356 requests were simultaneously in flight; after 15 seconds, 713 had
   finished and 643 were still pending. The API data was valid; the browser request fan-out was the
   direct cause.

The correction keeps the summary/count available but mounts the drawer body only after a user opens
it on Export. Closed Data, Process, and Fit surfaces therefore create no saved-output link-resolution
work. Opening the drawer preserves the existing append-only list and lets the browser schedule its
normal requests. It changes neither the API nor the user's saved-output workflow.

| Live measurement | Result |
| --- | --- |
| Data, drawer closed | 0 processing-output resolution requests; 0 output articles mounted |
| Export, drawer closed | 0 processing-output resolution requests; 0 output articles mounted |
| Export, drawer opened | The existing append-only output articles mount and their exact links resolve on demand. |
| Failed requests / `ERR_INSUFFICIENT_RESOURCES` | 0 / 0 |
| New requests after closing the drawer | 0 |

## Original before/after comparison

Browser zoom is 100%, DPR is 1, and density is Standard. Every image is an original PNG at its
declared CSS viewport. The issue-owned [image manifest](images/issue-260-fe05-modeling-data/manifest.json)
records dimensions, SHA-256, and every direct 100%-pixel crop.

| Stage | Viewport | Before | Candidate |
| --- | --- | --- | --- |
| Data | 1366×768 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-data-1366x768.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-data-1366x768.png) |
| Data | 1440×900 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-data-1440x900.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-data-1440x900.png) |
| Data | 1920×1080 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-data-1920x1080.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-data-1920x1080.png) |
| Data | 2560×1440 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-data-2560x1440.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-data-2560x1440.png) |
| Data | 3840×2160 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-data-3840x2160.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-data-3840x2160.png) |
| Process | 1366×768 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-process-1366x768.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-process-1366x768.png) |
| Process | 1440×900 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-process-1440x900.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-process-1440x900.png) |
| Process | 1920×1080 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-process-1920x1080.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-process-1920x1080.png) |
| Process | 2560×1440 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-process-2560x1440.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-process-2560x1440.png) |
| Process | 3840×2160 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-process-3840x2160.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-process-3840x2160.png) |
| Fit | 1366×768 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-fit-1366x768.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-fit-1366x768.png) |
| Fit | 1440×900 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-fit-1440x900.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-fit-1440x900.png) |
| Fit | 1920×1080 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-fit-1920x1080.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-fit-1920x1080.png) |
| Fit | 2560×1440 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-fit-2560x1440.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-fit-2560x1440.png) |
| Fit | 3840×2160 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-fit-3840x2160.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-fit-3840x2160.png) |
| Export | 1366×768 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-export-1366x768.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-export-1366x768.png) |
| Export | 1440×900 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-export-1440x900.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-export-1440x900.png) |
| Export | 1920×1080 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-export-1920x1080.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-export-1920x1080.png) |
| Export | 2560×1440 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-export-2560x1440.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-export-2560x1440.png) |
| Export | 3840×2160 | [before](images/issue-260-fe05-modeling-data/before/originals/modeling-export-3840x2160.png) | [after](images/issue-260-fe05-modeling-data/after/originals/modeling-export-3840x2160.png) |

Product-owner wide-screen review links (candidate, direct pixels):

- Data 1920: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-data-1920x1080-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-data-1920x1080-graph-100pct.png); 2560: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-data-2560x1440-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-data-2560x1440-graph-100pct.png); 3840: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-data-3840x2160-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-data-3840x2160-graph-100pct.png).
- Process 1920: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-process-1920x1080-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-process-1920x1080-graph-100pct.png); 2560: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-process-2560x1440-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-process-2560x1440-graph-100pct.png); 3840: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-process-3840x2160-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-process-3840x2160-graph-100pct.png).
- Fit 1920: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-fit-1920x1080-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-fit-1920x1080-graph-100pct.png); 2560: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-fit-2560x1440-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-fit-2560x1440-graph-100pct.png); 3840: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-fit-3840x2160-controls-100pct.png), [graph](images/issue-260-fe05-modeling-data/after/crops/modeling-fit-3840x2160-graph-100pct.png).
- Export 1920: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-export-1920x1080-controls-100pct.png), [native preview](images/issue-260-fe05-modeling-data/after/crops/modeling-export-1920x1080-native-preview-100pct.png); 2560: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-export-2560x1440-controls-100pct.png), [native preview](images/issue-260-fe05-modeling-data/after/crops/modeling-export-2560x1440-native-preview-100pct.png); 3840: [controls](images/issue-260-fe05-modeling-data/after/crops/modeling-export-3840x2160-controls-100pct.png), [native preview](images/issue-260-fe05-modeling-data/after/crops/modeling-export-3840x2160-native-preview-100pct.png).

The manifest also records the five direct header and navigator crops for every stage and the 1366/1440
control and graph/preview crops. Supporting states include Data [empty session](images/issue-260-fe05-modeling-data/after/states/modeling-data-empty-1440x900.png), [invalid mapping](images/issue-260-fe05-modeling-data/after/states/modeling-data-invalid-1440x900.png), [locally scrolled recovery](images/issue-260-fe05-modeling-data/after/states/modeling-data-invalid-scrolled-1440x900.png), and Export [source blocker](images/issue-260-fe05-modeling-data/after/states/modeling-export-source-blocked-1440x900.png), [approximation blocker](images/issue-260-fe05-modeling-data/after/states/modeling-export-approximation-blocked-1440x900.png), and [delivered state](images/issue-260-fe05-modeling-data/after/states/modeling-export-delivered-1440x900.png).

## Original-image integrity

The [image manifest](images/issue-260-fe05-modeling-data/manifest.json) records the dimensions and
SHA-256 of two owner-direction images, forty before/after originals, 160 direct 100%-pixel crops,
and six supporting states. The final integrity check opens every recorded file, recomputes its hash
and dimensions, and confirms that every crop is an unscaled source-pixel extraction.

## Verification record

| Gate | Current result |
| --- | --- |
| Focused frontend regression | PASS — 130 tests cover Data workspace, intake, related data, graph/layout, one-input semantics, comparison open/close behavior, and deferred Saved outputs body mounting. |
| TypeScript, production build, and bundle budget | PASS — build completes with 0 bundle warnings/errors; entry 263,168 bytes, Common Workbench 116,188 bytes, Data workspace 50,744 bytes. |
| Compose preflight and web refresh | PASS — canonical project/source match; only web rebuilt/recreated; existing data and volumes preserved. |
| Data/session browser flow | PASS — 11 captures across all five viewports plus reload, empty, invalid, local-scroll, splitter, keyboard, and last-valid-graph checks. |
| Data → Process → Fit → Export consistency | PASS — 15 captures across 1366, 1440, and 1920 after correcting the stale capture assumption; exact Process save precedes Fit and Export exact-target preview. |
| Resource-exhaustion reproduction | PASS — closed requests 0, failed/resource errors 0, and no new requests after closing the drawer. |
| Full frontend, capture contracts, documentation, and diff gates | PASS — 71 files / 406 frontend tests, 17 guard tests, actual frontend guard 0 violations, 68 capture-contract tests, 24 user-guide contract tests, 24 bundle/route contract tests, live route measurement, user-guide links, documentation impact, and `git diff --check`. |
| Original-resolution visual and packet integrity review | PASS — 40 before/after originals, 160 direct 100%-pixel crops, 6 supporting states, and 2 owner-direction images; all 208 manifest hashes, dimensions, crop boxes, and source-pixel comparisons match. |
| Balanced independent read-only audit | PASS — the earlier pass was reopened after the owner identified the comparison-color and peer-heading-width inconsistencies. The corrected exact candidate, live assertions, refreshed originals, and 208-file packet were re-audited with blocker 0, major 0, and material-minor 0. |

## Preserved and deferred boundaries

Data→Process→Fit→Export, exact revision/session behavior, saved output formats, Materials read-back,
backend/API/database/storage, and public component contracts remain unchanged. #276 Simulation
Data/no-fit work, #261–#264, global density policy, and CSS ownership movement remain outside this
unit. Automated 3840 geometry is not an actual Windows 4K readability decision; that final physical
gate remains #223. Draft PR publication is authorized only after the final independent re-audit and
pre-publish gate pass. Ready transition, merge, and issue closure remain outside this authorization.
