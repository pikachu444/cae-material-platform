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

At task start, the main orchestrator reads the exact authority, announces the selected route and one
short semantic/operational risk reason, then proceeds without a routine permission question. Classify
by meaning and operational risk, never by file or line count. An explicit user instruction for
`full workflow` or `main-direct` handling controls the route and performer. Ambiguity, a changed
contract/policy/requirement, new product judgment, risk expansion, a widened owned path, or a
fast-path gate that exposes broader impact requires a question or promotion to Full workflow; do not
demote a task after work has started. The reusable trace and Process calibration example live in
[`docs/14-testing/main-orchestrator-acceptance.md`](docs/14-testing/main-orchestrator-acceptance.md).

### Administrative direct path

- Entry is an authorized external fact record only (for example an issue checkbox/comment, an
  already-known merge SHA, or equivalent GitHub metadata), with no repository file change and no
  product, policy, requirement, contract, or approval judgment.
- Main writes the exact requested fact, fetches it again, and matches the target, value/body/SHA, and
  resulting state. Before and after the write, record the same content-preserving fingerprint:
  `git status --porcelain=v2 -z`; byte-for-byte `git diff --no-ext-diff --binary`; byte-for-byte
  `git diff --cached --no-ext-diff --binary`; and the sorted untracked-path list from
  `git ls-files --others --exclude-standard -z` plus a SHA-256 for every pre-existing untracked
  regular file. Require exact equality. This path allows pre-existing tracked, staged, or untracked
  work and never requires a clean worktree or `git diff --exit-code`.
- No requirements auditor, writer, or independent reviewer is called mechanically. On an
  authorization/API error or read-back mismatch, do not claim success; retry only a demonstrably
  transient, idempotent failure, otherwise report the exact blocker/ambiguity and stop. A repository
  edit or new interpretation promotes to the appropriate path. Publication is N/A unless separately
  requested.

### Trivial maintenance fast path

- Entry is a local docs/metadata repair that synchronizes an already-approved or merged fact, fixes a
  typo, or repairs a broken internal link while changing no product behavior, policy, requirement,
  contract, workflow, test/build rule, `AGENTS.md`/skill/orchestration rule, or approval judgment.
- Main records branch/base/status, the already-authoritative fact, and owned paths; edits only those
  paths; and inspects the scoped diff. Before commit, require meaning-preserving scope, `git diff
  --check`, `uv run cmp-check-user-guide --root .`, and `make docs-impact` (or, when Make is
  unavailable, `uv run cmp-check-doc-impact --root . --mode worktree`; this is the same gate, not a
  skip), plus any changed-path-specific deterministic check required by the documentation manifest,
  links, manifests, or hooks.
- After an explicitly authorized commit and before push/PR, require a clean worktree, current fetched
  `origin/main`, expected base/head/diff/paths, and `make pre-publish` (or, when Make is unavailable,
  `uv run cmp-pre-publish --root . --trigger manual`; this is the same gate, not a skip). Reopen
  changed files/links and inspect the exact commit diff; after push/PR, fetch and read the remote
  branch or PR metadata. A gate that reveals broader product, policy, contract, test, or visual impact
  promotes to Full workflow. This path does not create or reuse a publication approval; existing
  approval boundaries remain in force. Main owns this path; do not call agents mechanically.

### Full workflow

- Entry is every exclusion above, including code, UI, engineering calculation, API/schema,
  data/migration, security/authorization, test/build policy, product requirement, `AGENTS.md`, skill,
  orchestration workflow, visual approval, or product-owner judgment changes.
- Main freezes the packet; one configured requirements auditor must approve; one bounded writer changes
  only packet-owned files; main independently performs the issue-specific acceptance; then one
  independent read-only reviewer approves. Compose/DB/browser/viewport gates are required only when the
  issue, contract, skill, or changed behavior makes them relevant and are otherwise marked N/A or
  deferred with a reason.
- On a failed checkpoint, main continues every safe applicable check while frozen evidence remains
  valid and records all failures. Stop discovery early only when continuing would be unsafe or the
  failed prerequisite makes remaining evidence invalid; record that exact boundary and why. Consolidate
  related causes into a new, materially revised correction packet. Never replay an unchanged packet.
  After three failed correction passes, re-audit and re-plan authority, scope, journey, packet, gates,
  and evidence; stop for a product decision, missing authority, unsafe action, external blocker, or
  scope-changing ambiguity, otherwise freeze a materially revised packet, reset the count, and continue.

- A route classification alone authorizes no commit, push, PR creation, ready-for-review transition,
  or merge. An explicit user/product-owner instruction may name one or more of those actions, limited
  to the named repository, branch, diff, and action; failure or scope expansion requires renewed
  authority when the action or risk changes. Ready and merge remain separate external-state changes
  unless explicitly included. `main-direct` removes mechanical delegation but never waives relevant
  acceptance gates, preserved-state checks, or publication approvals. A pre-publish failure blocks
  publication on every path.

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

## Full workflow contract

The following workflow contract applies only to Full workflow. Administrative direct path and Trivial
maintenance fast path use their route-specific contracts above; an explicit user `main-direct`
instruction may override mechanical delegation while preserving relevant acceptance and publication
boundaries.

- Each Full workflow task defines one realistic primary user journey grounded in actual product work,
  not a contrived validation story. Keep recovery, negative, and technical failure cases separate. The
  packet names fixture/setup, user actions, visible and persistence outcomes, preserved data/state,
  owned files, forbidden shortcuts, captures, and implementation-adjacent gates.
- Before Full workflow implementation, the main orchestrator gives that packet and its exact
  authoritative sources to one configured requirements auditor. On that role's first creation in the
  current root task, use `spawn_agent` with `fork_turns: "none"` and the bounded packet; this creates a
  new agent without parent-turn inheritance and is never described as resetting an existing agent. The
  same canonical auditor receives materially revised packets and later re-audit packets through
  `followup_task`. On every invocation it reopens the named authority; retained context and prior
  dispositions are not authority. The auditor independently traces
  every in-scope requirement to a user action, visible outcome, persistence outcome, preserved state,
  recovery behavior, and an observable automated, live, or visual acceptance condition.
  `changes_requested` blocks implementation until the main orchestrator revises and resubmits the
  packet; the auditor never writes or redesigns it. For visual work, the auditor opens every
  packet-required approved viewport at original resolution and requires explicit content-visibility,
  clipping, wrapping, identity/revision, interaction-reachability, and relevant layout-bound checks.
  Tooltips, hidden text, and measurements alone do not prove normal-surface usability.
- Full workflow may parallelize only genuinely independent read-only work by default. After the bounded
  packet exists, the main orchestrator may use at most three read-only lanes in total, including the
  mandatory requirements auditor, for non-overlapping requirements audit, code/contract mapping, and
  visual/browser evidence inspection. Each agent receives one explicit question and returns a concise
  evidence summary rather than raw logs. The main orchestrator waits for every requested result and
  consolidates all findings once before any writer starts; do not spawn agents merely to use the
  available capacity.
- Agent lifecycle is bounded per root task. Create each configured role at most once, always with
  `fork_turns: "none"` on its initial `spawn_agent` call, then use `followup_task` when that same role
  must examine a materially revised versioned packet. `fork_turns: "none"` applies only to new-agent
  creation; neither it nor `interrupt_agent` resets an existing agent. The normal maximum is the
  canonical auditor, up to two additional read-only lanes, one implementation writer, one correction
  writer created only if needed, and one reviewer. The configured limit of 12 is recovery headroom for
  threads that the current runtime may not reclaim, not a spawning target. Record every completed result
  and never create a replacement merely to claim freshness. If a mandatory canonical role becomes
  unavailable, checkpoint authority, packet, evidence, branch, base, status, and next action, then
  continue in a new root task instead of accumulating replacements in the current task.
- The Full workflow implementation writer changes only packet-owned files, runs only packet automated
  gates, reports exact unrun or blocked gates, and never claims main-orchestrator live acceptance.
  Writers do not reinterpret requirements, add scope/gates, or start another writer; unrelated changes
  remain untouched.
- The Full workflow main orchestrator owns requirement interpretation, packets, integration, failure
  diagnosis, and final internal gate; it is not a subagent. Never run concurrent writers in the same
  checkout. Keep the implementation writer and correction writer as distinct configured roles and run
  them sequentially. Create the correction writer on the first correction need and reuse that same role
  for later versioned correction packets, at most one bounded pass per invocation. Main's new diagnosis
  and current evidence, not either writer's retained context, control every correction. Truly independent
  write-heavy issues may run in separately created Codex worktree chats
  and branches, each with its own orchestrator and gates, but dependent backlog units and work sharing
  one branch never qualify.
- For Full workflow, the main orchestrator independently performs every packet-applicable live gate,
  including Compose, database, browser, reload, or required viewport checks. Writer tests/screenshots
  are evidence, never a substitute. For visual work, main opens every issue-required viewport at
  original resolution after the live capture; a representative subset is not sufficient. After all
  implementation and main-orchestrator gates pass, create one independent read-only reviewer with
  `fork_turns: "none"`. That canonical reviewer reopens every required viewport at original resolution,
  completes the full bounded review, and must return `approve` before publication. If correction changes
  implementation or evidence, send the reviewer a new versioned packet with `followup_task`; it reopens
  the current evidence, and its prior verdict is not authority.
- Before any packet-applicable live Docker gate, the Full workflow main orchestrator runs
  `make compose-preflight`. The canonical composition is rebuilt/recreated for this work; stale or
  foreign environments are rejected. Ad-hoc projects use dynamic host ports, guaranteed `finally`
  cleanup, and post-cleanup verification. Preflight never removes or mutates containers, volumes, or
  data.
- Before correction, root/main reproduces and diagnoses the whole UI -> request -> service -> DB -> reload
  chain. A failed checkpoint does not end discovery: continue every safe applicable check, collect all
  failures from the frozen evidence, and consolidate related causes before giving the canonical
  correction writer one bounded pass. Stop discovery early only when continuing would be unsafe or when
  the failed prerequisite makes the remaining evidence invalid, and record that exact boundary. Each
  correction pass has a new diagnosis and packet. After three failed correction passes, main runs a full
  re-audit and re-plan checkpoint over authority, scope, user journey, packet, gates, and the complete
  frozen evidence. Reuse the canonical requirements auditor for this re-audit. Unless that checkpoint
  exposes a product decision, missing authority, unsafe action, or external blocker that requires owner
  input, reset the correction-pass count and continue with a materially revised packet and the same
  correction writer. Never repeat the same failed packet merely because the count was reset. If evidence
  contradicts the selected issue, authority, material or model family, contract set, scope, journey, or
  fixture classification, main stops correction immediately, reclassifies existing work as complete,
  partial, or missing, and re-plans with the canonical auditor; repeated Compose or test execution never
  substitutes for that semantic diagnosis.
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
- A work unit remains incomplete until delivery tracking is synchronized: after a PR number exists and
  before merge, the work PR updates `docs/13-delivery/backlog.md` with the completed numbered unit/PR
  and next unfinished numbered row; immediately after merge and before the final report, the main
  orchestrator records the PR, merge SHA, and next unit in the exact issue, checks the corresponding
  parent-tracker item (#117 when applicable), and keeps a multi-unit issue open until all units finish.
- User-visible React/CSS changes update the current guide, screenshot manifest, and required live
  screenshots. An `app.tsx` navigation change also updates the navigation contract.
- Before handoff, run affected tests, `uv run cmp-check-user-guide --root .`, and `make docs-impact`
  (or, when Make is unavailable, `uv run cmp-check-doc-impact --root . --mode worktree`; this is the
  same gate, not a skip), plus `git diff --check` when applicable. Do not commit, push, open, or merge
  a pull request without explicit user or product-owner confirmation.

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
