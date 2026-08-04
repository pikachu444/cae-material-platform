# Implementation Instructions

## Authority and safety

- Preserve the current branch and all existing worktree changes. Never use `git reset`, `git clean`,
  stash, checkout discard, or another operation that drops or hides existing work.
- A new issue starts from latest main with `git pull --ff-only origin main`. An active issue stays on
  its branch; do not reopen merged work. Close it only after all its listed units finish.
- `docs/13-delivery/backlog.md` is the baseline, issue order, and handoff router. Read it and the exact
  issue first; use `rg` to locate only affected requirements, ADRs, contracts, tests, and product specs.
  `IMPLEMENTATION_STATUS.md`, live code, and user guides describe implemented behavior.
  Do not bulk-read archives or `docs/_incoming/`.
- `.codex/config.toml` and `.codex/agents/*.toml` solely authorize configured models, reasoning, sandbox,
  and roles. Verify that the configured role actually loaded; if unavailable, report the exact error and
  never silently substitute or redefine it in a prompt. Product language is **test data**, **selected
  model**, **review request**, and **solver card**; UUIDs, hashes, Mapping Profile, Recipe/Batch,
  provenance, and checksums belong in Evidence, Advanced, or Administration.

## Routing

- A fresh Codex task takes the first unfinished backlog unit and merges dependent work before it.
- Visual or production UI work uses `.agents/skills/desktop-engineering-ui`, the approved family
  in `docs/01-product/service-reference-inventory.yaml`, selected entries in
  `docs/01-product/service-reference-manifest.yaml`, original assets, affected UI contracts, and
  `docs/01-product/visual-acceptance-matrix.md`. Use `frontend-ui-engineering` only for production
  React/CSS, `web-design-guidelines` for an explicit UI/accessibility audit, and `webapp-testing` for
  live interaction or browser evidence.
- Domain, API, data, migration, and documentation work reads the exact requirement and affected contract
  before implementation and loads visual references only for UI changes. README/user-guide prose follows
  `docs/documentation-manifest.yaml` and its restrained Korean-humanizer hook.

## Workflow contract

- Each fresh task defines one realistic primary user journey grounded in actual product work, not a
  contrived validation story. Keep recovery, negative, and technical failure cases separate. The packet
  names fixture/setup, user actions, visible and persistence outcomes, preserved data/state, owned files,
  forbidden shortcuts, captures, and implementation-adjacent gates.
- Before implementation, the main orchestrator gives that packet and its exact authoritative sources to
  one fresh configured requirements auditor. The auditor independently traces every in-scope requirement
  to a user action, visible outcome, persistence outcome, preserved state, recovery behavior, and an
  observable automated, live, or visual acceptance condition. `changes_requested` blocks implementation
  until the main orchestrator revises and resubmits the packet; the auditor never writes or redesigns it.
  For visual work, the auditor opens every packet-required approved viewport at original resolution and
  requires explicit content-visibility, clipping, wrapping, identity/revision, interaction-reachability,
  and relevant layout-bound checks. Tooltips, hidden text, and measurements alone do not prove normal-
  surface usability.
- Parallelize only genuinely independent read-only work by default. After the bounded packet exists, the
  main orchestrator may use at most three read-only lanes in total, including the mandatory requirements
  auditor, for non-overlapping requirements audit, code/contract mapping, and visual/browser evidence
  inspection. Each agent receives one explicit question and returns a concise evidence summary rather
  than raw logs. The main orchestrator waits for every requested result and consolidates all findings once
  before any writer starts; do not spawn agents merely to use the available capacity.
- The implementation writer changes only packet-owned files, runs only packet automated gates, reports
  exact unrun or blocked gates, and never claims main-orchestrator live acceptance. Writers do not
  reinterpret requirements, add scope/gates, or start another writer; unrelated changes remain untouched.
- The main orchestrator owns requirement interpretation, packets, integration, failure diagnosis, and
  final internal gate; it is not a subagent. Never run concurrent writers in the same checkout. Keep the
  implementation writer and every later correction writer fresh and sequential; do not bind them into a
  standing team that can carry the implementation's confirmation bias into correction. Truly independent
  write-heavy issues may run in separately created Codex worktree chats and branches, each with its own
  orchestrator and gates, but dependent backlog units and work sharing one branch never qualify.
- The main orchestrator independently performs live Compose, database, and browser acceptance. Writer
  tests/screenshots are evidence, never a substitute. For visual work, main opens every issue-required
  viewport at original resolution after the live capture; a representative subset is not sufficient.
  After all implementation and main-orchestrator gates pass, one fresh independent read-only reviewer
  reopens every required viewport at original resolution, completes the full bounded review, and must
  return `approve` before publication.
- Before any live Docker gate, main orchestrator runs `make compose-preflight`. The canonical
  composition is rebuilt/recreated for this work; stale or foreign environments are rejected.
  Ad-hoc projects use dynamic host ports, guaranteed `finally` cleanup, and post-cleanup verification.
  Preflight never removes or mutates containers, volumes, or data.
- Before correction, root/main reproduces and diagnoses the whole UI -> request -> service -> DB -> reload
  chain. A failed checkpoint does not end discovery: continue every safe applicable check, collect all
  failures from the frozen evidence, and consolidate related causes before giving one fresh configured
  correction writer one bounded pass. Stop discovery early only when continuing would be unsafe or when
  the failed prerequisite makes the remaining evidence invalid, and record that exact boundary. Each
  correction pass has a new diagnosis and packet. After three failed correction passes, main runs a full
  re-audit and re-plan checkpoint over authority, scope, user journey, packet, gates, and the complete
  frozen evidence. Unless that checkpoint exposes a product decision, missing authority, unsafe action,
  or external blocker that requires owner input, reset the correction-pass count and continue with one
  fresh packet and writer. Never repeat the same failed packet merely because the count was reset.
- Automation stays thin: one realistic high-value browser flow where applicable, lower-level regression
  tests for rules, and Docker preflight. Do not create a generic verification or review framework.

## Domain invariants

- Raw bytes and released artifacts are immutable. Stable identities and immutable revisions are separate;
  runs and links pin concrete revisions, never `latest`.
- Preserve original unit text, normalized unit, and quantity semantics. Never delete outliers; candidate
  detection and adjudication are separate records.
- Every derived entity records input usage, generation activity, and responsible agents. A production
  solver card requires a Material Model IR revision. Exporters report exact, transformed, approximated,
  and unsupported mappings without silent defaults.
- Core code never imports domain plugin implementations. Organization/project authorization is enforced
  at service and database levels.

## Product and UX invariants

- Normal-user navigation is `Materials | Modeling | Activity`; `/materials` is home. Search-first does
  not remove Database/Profile/Table/Folder/Record navigation, Administration schema objects,
  exact-revision links, or keyboard browsing.
- Materials is one continuous explorer/result/datasheet workspace, with results wider than optional
  context. Modeling keeps a compact curve/process explorer and dominant persistent graph; current-step
  controls use a shallow ribbon or disclosure, never a permanent third inspector column.
- Prefer flat panes, alignment, and dividers before borders, radius, background, or shadow. Avoid nested
  cards, decorative gradients, repeated eyebrow labels, and non-status badges.
- Every visible engineering field has a user decision or workflow consequence and a canonical UI
  contract; otherwise remove it or move it to Advanced/Evidence. Recommendation, engineer selection,
  saved result, review, release, and delivered artifact are distinct states. Upstream changes invalidate
  downstream current pointers without mutating revisions.
- Materials rows, totals, and facet counts come from one server-scoped query. Condition-aware properties
  are not universal facets. Approved static HTML/CSS and registered images are authority for their exact
  target. The qualitative owner checklist is a hard gate; measurements cannot override a qualitative
  failure and the product owner gives final visual approval.

## Delivery

- Implement one issue or clearly bounded subset. Define or update contracts before adapters and add the
  specified unit, integration, regression, and browser tests. Run only gates required by issue acceptance,
  affected contracts, selected skills, changed behavior, or hooks; resolve hook failures.
- User-visible React/CSS changes update the current guide, screenshot manifest, and required live
  screenshots. An `app.tsx` navigation change also updates the navigation contract.
- Before handoff, run affected tests, `uv run cmp-check-user-guide --root .`, `make docs-impact`, and
  `git diff --check` when applicable. Do not commit, push, open, or merge a pull request without
  explicit user or product-owner confirmation.

## Do not decide TBD domain items

Do not select or imply a production tensile standard, material family, constitutive model, optimizer
policy, solver card, virtual specimen, or validation threshold. Use bounded synthetic non-production
references until the corresponding open decision is approved.

## Forbidden shortcuts

No generic EAV for core domain data, row-per-point storage for large curves, mutable raw/released keys,
hidden conversion/resampling/smoothing/manual curve edits, direct plugin database access, in-process
production plugin loading, silent solver approximation, unreviewed golden updates, or confidential
test data in source control.

`docs/_incoming/2026-07-24-organic-ux-update/` remains temporary #162 input. Do not read it early or
delete it before #162 absorbs valid content and proves inbound links are zero.
