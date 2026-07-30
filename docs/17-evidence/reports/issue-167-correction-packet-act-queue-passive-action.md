# Issue #167 — ACT-QUEUE passive-action correction packet

Date: 2026-07-30
Owner: active `/root` main agent
Writer: one fresh configured `correction_terra_high`

## 1. Rejection

The wide-density ACT-QUEUE rework passes its deterministic gates, and the active main agent opened
all eleven approval and wide-support images at original resolution. The main qualitative gate still
rejects the bundle.

In every User normal image, a pending server review request renders `Needs a decision` in both the
`Status` and `Action` columns. The User has no decision command for that row. Repeating the lifecycle
state in the action cell makes a non-action look like a control or second status, and violates the
canonical rule that a visible field must have a user decision or workflow consequence.

This is a bounded semantic correction, not a layout redesign.

## 2. Owned paths

The correction writer may modify only:

- `docs/00-research/ux-service-reference/activity-queue.js`
- `docs/00-research/ux-service-reference/capture_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/validate_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/activity-queue-wave04.staging.json`
- the seven existing ACT-QUEUE approval PNG/measurement pairs;
- the existing ACT-QUEUE state-evidence PNG/measurement/state-evidence files;
- the four User/Reviewer normal 2560×1440 and 3840×2160 wide-support PNG/measurement pairs.

Do not edit HTML, CSS, product/UI specifications, the common manifest, inventory, common evidence
report, production React/CSS, GitHub state, commits, pushes, PRs or any other family.

## 3. Exact correction

1. Keep the exact columns `Task | Request reason | Status | Updated | Action`.
2. Keep lifecycle values such as `Needs a decision`, `Approved` and `Changes requested` only in
   `Status`.
3. When a row has no available command, render a compact visible em dash in `Action` with an
   accessible name such as `No available action`. Do not render the lifecycle state twice.
4. Preserve real commands unchanged:
   - Reviewer pending rows: `Review`;
   - browser-local Modeling session: `Resume Modeling`;
   - browser-local solver-card history: `Open card`;
   - the governed role-blocked recovery explanation and its one valid recovery command.
5. Do not add `View`, `Open`, person, Material, owner, identifier or evidence actions that the
   current response/navigation contract cannot support.
6. Preserve the 50 server request split, role defaults, row density, proportional local scrollbar,
   all exceptional-state truth boundaries and every current responsive topology.

## 4. Required evidence

Strengthen the capture and validator so that:

- every passive `Action` cell has the visible em dash and accessible `No available action` name;
- no passive action cell repeats its row's lifecycle status;
- all real commands remain present only for their supported row and role;
- all existing count, role, table, density, overflow, interaction, error and recovery assertions
  remain green.

Recapture the seven registered approval images, all existing responsive state evidence, and the four
normal wide-support images. Do not create new wide exceptional-state files.

Run at minimum:

```powershell
node --check docs/00-research/ux-service-reference/activity-queue.js
python -m py_compile docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
python -m ruff check docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
python docs/00-research/ux-service-reference/capture_activity_queue_wave04.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_activity_queue_wave04.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/capture_activity_queue_wave04.py --wide-support
python docs/00-research/ux-service-reference/validate_activity_queue_wave04.py --wide-support --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

Return the changed paths, eleven final hashes, command results and any residual risk. Do not request
product-owner approval.
