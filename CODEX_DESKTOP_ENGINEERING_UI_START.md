# Codex Desktop Engineering UI Start

`AGENTS.md` is the single execution handoff for a new session. Read its **Current execution handoff**
and `docs/13-delivery/backlog.md`, then take only the next linked issue.

The approved product/visual baseline is `55cfa62` (PR #156). Start every task from the latest `main`
with `git pull --ff-only origin main`. PR #125–#166 and every later PR already present on current
`main` are merged scope and must not be reimplemented.
Work begins with #167 service reference freeze, then proceeds #157 → #158 → #159 → #160 → #161 → #162
with one writer, deterministic gates, a fresh independent review, product-owner confirmation, and at
most one correction/re-review. Never run two writing subagents concurrently.
Automatic LLM review remains disabled under #119.

For visual work, use the four mandatory skills named in `AGENTS.md`. #167 must register and obtain
main-agent/product-owner approval for every static HTML/CSS/image target before React/CSS work starts.
Port that target faithfully while preserving product contracts; evaluate full-screen flow, topology,
priority, continuity and overflow rather than pixel-copying. `docs/_incoming/2026-07-24-organic-ux-update/`
is temporary reference and must remain until #162 completes its absorption and zero-inbound audit.
