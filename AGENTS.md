# Implementation Instructions

## Current execution handoff

- **Approved product/visual baseline:** `55cfa62` (PR #156). The repository starting point is always the latest `main` obtained with `git pull --ff-only origin main`. PR #125–#166 and every later PR already present on current `main` are merged scope; do not reopen or reimplement them.
- **Product language:** User works with **test data**, a **selected model**, a **review request**, and a **solver card**. Reviewer handles requests; Administrator manages catalog structure, access, and governed operations. UUIDs, hashes, Mapping Profile, Recipe/Batch, provenance, and checksums belong in Evidence, Advanced, or Administration.
- **Order:** [#117](https://github.com/pikachu444/cae-material-platform/issues/117) is meta; [#119](https://github.com/pikachu444/cae-material-platform/issues/119) keeps automatic LLM review disabled. First do [#167 service reference freeze](https://github.com/pikachu444/cae-material-platform/issues/167), then [#157 demo](https://github.com/pikachu444/cae-material-platform/issues/157) → [#158 Fit](https://github.com/pikachu444/cae-material-platform/issues/158) → [#159 Materials](https://github.com/pikachu444/cae-material-platform/issues/159) → [#160 Governance/Activity](https://github.com/pikachu444/cae-material-platform/issues/160) → [#161 DUI-09](https://github.com/pikachu444/cae-material-platform/issues/161) → [#162 UXC-99](https://github.com/pikachu444/cae-material-platform/issues/162). Except for the bounded #167 batch rule below, each issue uses latest `main` → one implementer/writer → deterministic gates → fresh independent reviewer → product-owner confirmation → PR/merge; at most one correction and re-review. Never run two writing subagents concurrently outside that explicit #167 exception.
- **#167 reference gate:** freeze a complete service reference set before any production visual change: Materials search/tree/detail/card; Modeling Data/Process/Fit/Export; Activity user/reviewer/recovery; and Administration database/table/attribute/layout/subset/link/access edit/publish. Maintain a finite authoritative target/state inventory with screen-family dependencies. Every normal screen family includes 1366×768, 1440×900 and 1920×1080. A topology-changing long, empty, loading, blocked or error state gets one canonical 1440×900 approval image plus deterministic 1366/1440/1920 browser evidence; add separate compact or wide state images only when that state changes responsive topology. Each reference has static HTML/CSS, image, path, hash, viewport, date and approval status. The main agent opens and evaluates every image. The product owner may approve multiple explicitly listed image paths/hashes in one response; every image still receives its own manifest lifecycle. No later visual implementation starts without the approved target assets for its exact screen/state.
- **#167 bounded parallel/batch rule:** after the shared shell, inventory and dependency edge are frozen, the main agent may run at most two independent screen-family writers concurrently. Concurrent packets must have disjoint source/capture/image ownership, must not edit shared CSS/JavaScript, the common manifest or the common evidence report, and must name their dependency prerequisites. The main agent integrates shared manifest/evidence changes serially after both writers finish. Within one screen family, normal structure precedes dependent tabs/actions and normal precedes topology-changing exceptional states; one writer owns the complete three-viewport bundle. Run deterministic gates and main-agent original-image review for every image, then one fresh read-only reviewer per family bundle; independent bundle reviewers may run concurrently. Each family bundle gets at most one correction and fresh re-review. Submit completed bundles together for product-owner batch approval, listing every image and SHA-256. Do not start a dependent family before its prerequisite bundle is approved.
- **Visual authority:** approved static HTML/CSS and their registered reference images are implementation source and visual authority, not inspiration. Port their region structure and CSS faithfully into production React while wiring existing state/backend contracts; do not redesign or add route-specific override layers. PR #156 remains the approved current baseline until a target is approved. Pixel-copying and arbitrary fine-number tuning are non-goals: judge task flow, topology, information priority, readability, graph/table/tree dominance, control-result continuity and absence of overlap, clipping and overflow. Measurements are safety rails.
- **Agent roles:** the main agent is the active `/root` primary agent, not a separate subagent, and owns product/UX judgment. Project `.codex/config.toml` pins it to GPT-5.6 Sol Extra High; if the active surface does not load that configuration, report the mismatch before visual judgment and never infer model identity from a role name. A bounded implementer starts with GPT-5.6 Luna Max. If its result fails the deterministic/main-agent/reviewer gate or is materially weak, use one fresh GPT-5.6 Terra High implementer for the sole correction. Start with GPT-5.6 Sol Extra High instead for genuinely complex state/data/migration work or a large-scale change. The reviewer is fresh, read-only GPT-5.6 Terra High and supplies independent contract, evidence, accessibility and full-screen qualitative findings; it is not the final design authority. Never run two writing agents concurrently except for two disjoint #167 screen-family writers authorized by the bounded parallel/batch rule above; do not use Ultra or Fast. If Luna is not callable in the active surface, report that before work and never silently substitute another model. Model selection is secondary to the concrete task packet and evidence gates.
- **Incoming package:** `docs/_incoming/2026-07-24-organic-ux-update/` is temporary reference, not authority. Do not delete it before #162 absorbs the remaining content and audits inbound links to zero.

## Read first

1. `README.md`
2. `docs/02-requirements/requirements.md`
3. `docs/03-domain/canonical-domain-model.md`
4. `docs/04-provenance/revision-and-provenance.md`
5. `docs/05-architecture/system-architecture.md`
6. the task in `docs/13-delivery/backlog.md`
7. relevant plugin/IR/API/test/security documents

## Non-negotiable invariants

- Raw bytes and released artifacts are immutable.
- Stable identities and immutable revisions are separate.
- Runs reference concrete revisions, never `latest`.
- Original unit text, normalized unit, and quantity semantics are preserved.
- Outliers are never deleted; candidate and adjudication are separate records.
- Every derived entity has input usage, generation activity, and responsible agents.
- A production solver card requires a Material Model IR revision.
- Exporters must report exact/transformed/approximated/unsupported mappings.
- Core code must not import domain plugin implementations.
- Organization/project authorization is enforced at service and database levels.

## Product UX invariants

- Normal-user navigation is `Materials | Modeling | Activity`; `/materials` is the home route.
- Search-first changes entry priority only. Preserve Database/Profile/Table/Folder/Record navigation,
  Table/Attribute/Layout/Subset/Link Type administration, exact-revision links, and keyboard browsing.
- Materials uses one continuous explorer/result/datasheet workspace. Tree and filters are not
  separate feature cards, and results remain wider than optional context.
- Modeling uses a compact curve/process explorer and a dominant persistent graph. A permanent third
  inspector column is forbidden; current-step controls belong in a shallow graph-adjacent ribbon and
  advanced controls use a drawer or disclosure.
- Workspace panes use alignment and dividers before border, radius, background, or shadow. Nested
  cards, decorative gradients, repeated eyebrow labels, and non-status badges are not accepted.
- Page titles are compact; material data, table rows, curves, and engineering controls carry the
  visual emphasis. Tree and metadata text remain readable 12–13 px regular/medium, body/data 14 px.
- Full IDs, hashes, classification, change reason, Mapping Profile JSON, Recipe/Batch lifecycle,
  provenance graph, mapping report, and checksums belong in Evidence, Advanced, or Administration.
- A major workspace redesign requires a reference comparison, responsive prototype, measured region
  ratios, and explicit product-owner approval before production React/CSS implementation begins.
- Visual acceptance requires every target screen to score at least 85/100 against the structural
  reference rubric, with no topology, dominant-area, or nested-card hard-gate failure.
- Numeric acceptance is necessary but insufficient. For every target/state image, the main agent and
  fresh reviewer independently complete the canonical **Mandatory qualitative owner checklist** in
  `docs/01-product/visual-acceptance-matrix.md` at original resolution. Any applicable checklist
  failure blocks handoff regardless of score. After reviewer disposition, the main agent repeats the
  final product/UX judgment and the product owner makes the final visual approval.
- Every visible engineering component or field has one canonical UI-spec entry that states its
  `purpose`, `placement`, `visible_when`, `source`, `requires`, `invalidates`, `states`, and
  `error_recovery`. A field without a user decision or workflow consequence must be redesigned,
  moved to Advanced/Evidence, or removed; it is not retained merely to look technical.
- Recommendation, engineer selection, saved result, review, release, and delivered artifact are
  distinct states. A recommendation never silently becomes the selected candidate, and an upstream
  change invalidates downstream current pointers without mutating immutable revisions.
- Materials query totals, facet counts, and rows come from the same server-side scoped query.
  Condition-aware properties are not exposed as universal facets (for example, Yield is absent for
  non-metal families).

## Do not decide TBD domain items

Do not choose or imply a production tensile standard, material family, constitutive model, optimizer policy, solver card, virtual specimen, or validation threshold. Use synthetic non-production reference plugins until the relevant open questions are resolved.

## Work by task

- Implement one backlog Task or a clearly bounded subset.
- Link requirement, ADR, and Task IDs in code/PR documentation.
- Define or update contracts before adapters.
- Add unit, integration, and regression tests listed by the Task.
- Obtain domain approval for numeric reference results, IR payload schemas, solver mappings, and golden files.
- For visual work, update the linked product policy, reference comparison, viewport evidence, and
  screenshot manifest in the same PR. Do not mark a visual Task complete before live browser review.
- Visual implementer packets name the exact approved assets/screens/components, user task, preserved
  behaviors/data/states, static-region → React-component/contract mapping, forbidden shortcuts,
  required captures and tests. Reviewer packets contain only issue acceptance, approved references,
  implementation diff, direct paths to live/reference comparison captures, and interaction/test
  results plus the canonical qualitative checklist. Review full-screen usability and parity, not test
  success alone. The reviewer records pass/fail/not-applicable evidence for every checklist item; the
  main agent then repeats the original-resolution qualitative gate and makes the final internal UX
  judgment before product-owner approval. A rejected local CSS approach gets at most one
  correction/re-review and must not be repeated.
- Before spawning an implementer, the main Sol agent must inspect the exact issue, approved HTML/CSS
  and images, current components, and preserved state/data contracts, then author and deliver that
  detailed implementer packet itself. It must not delegate requirement interpretation or packet
  creation to the implementer. Before spawning, persist the packet in the GitHub issue or a current
  task evidence document and give the implementer that exact URL/path, so a fresh or compacted session
  can reopen the authoritative instructions instead of relying on chat memory. After implementation
  and deterministic gates, the main Sol agent prepares the bounded reviewer packet in the PR/evidence,
  and directly compares the resulting images before requesting product-owner confirmation.
- For visual work, use `.agents/skills/desktop-engineering-ui`, `frontend-ui-engineering`,
  `web-design-guidelines`, and `webapp-testing`; the first directs reference-to-React execution and
  the remaining three respectively implement, audit and exercise the live workspace.

## Documentation enforcement

- `README.md` is a Korean project entrypoint, not an implementation journal. It must help a
  prospective Administrator, Reviewer, or User understand their work before internal engineering
  terms: state the role/task entry points, the two core user flows, a runnable quickstart,
  current-versus-approved-target status, current screen links, verification, and documentation
  links. Keep chronology in `docs/13-delivery/implementation-history.md`; do not impose a line
  count in place of useful guidance.
- A change to `README.md`, `docs/README.md`, or a current `docs/user-guide/*.md` first corrects
  audience, structure, facts, and terminology, then uses the `korean-humanizer` skill for a restrained
  prose pass. Preserve commands, code blocks, links, numbers, proper nouns, API/schema identifiers,
  role/state/invalidation contracts, and the document's technical register. Do not apply this pass to
  historical/reference documents unless the task explicitly changes their prose; always rerun the
  deterministic documentation checks afterward.
- Every tracked Markdown file must match exactly one `current`, `authoritative`, `historical`, or
  `reference` rule in `docs/documentation-manifest.yaml`.
- A commit that changes non-test `apps/web/**/*.tsx` or `apps/web/**/*.css` must also change all of:
  a current `docs/user-guide/*.md`, `docs/user-guide/screenshot-manifest.yaml`, and a current
  `docs/user-guide/images/current/*.png` captured from the live browser.
- A change to `apps/web/src/app.tsx` must additionally update
  `docs/user-guide/navigation-contract.yaml`. A user-visible OpenAPI workflow change must update a
  current user guide.
- Test-only, historical-evidence-only, and reference-research-only changes are exempt from visual
  screenshot impact, but never from valid links and document classification.
- Before committing visual work, run the affected live browser scenario at 1366x768 and 1440x900
  (and 1920x1080 when the layout materially expands), then run `make docs-screenshots` and
  `make docs-impact`.
- Project Codex hooks in `.codex/hooks.json` block `git commit` when required documentation evidence
  is missing. Before `git push`, `gh pr create`, `gh pr ready`, and `gh pr merge`, the automatic
  pre-publish pipeline runs deterministic documentation, diff, link, image, and manifest checks.
  It must never start an LLM reviewer. Independent code/visual review is a separately authorized,
  explicit opt-in command while GitHub issue #119 remains open. Review and trust the project hook
  with `/hooks` after cloning or whenever the hook definition changes.

## Forbidden shortcuts

- Generic EAV tables for core domain data
- Row-per-point storage for large curves
- Mutable raw or released object keys
- Hidden unit conversion, resampling, smoothing, or manual curve edits
- Direct plugin database access
- In-process loading of production plugins by the API
- Silent solver mapping defaults or approximation
- Golden snapshot updates without software and domain review
- Real confidential test data in source control

