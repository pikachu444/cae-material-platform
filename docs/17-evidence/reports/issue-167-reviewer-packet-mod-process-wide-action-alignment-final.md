# Issue #167 fresh reviewer packet — MOD-PROCESS wide action alignment

Date: 2026-07-31
Reviewer: one fresh configured read-only `reviewer_terra_high`

## Owner direction

The product owner accepted the 1920 composition but rejected 2560/3840 because the graph extended
past the `Save processed curves` action. The owner directed that wide graph sizing align as it does
at 1920, remove the 3840 table, and receive direct active-main-agent inspection before owner review.

## Exact review scope

Read the current MOD-PROCESS HTML/CSS/JavaScript, capture, validator, staging, product/UI contracts,
inventory and manifest diffs. Open these originals:

- `modeling-process-normal-1920x1080.png`
  — `87a861aa3e8822e4fe19645230f426f902ced609eea09e62b6fdae67f1a9cf09`;
- `modeling-process-normal-2560x1440.png`
  — `a731e066c19132dfc1127712beacaec70350b74cbdaa143f1d4f1f438ef8057d`;
- `modeling-process-normal-3840x2160.png`
  — `33af25e5ad187e1ef81b52dad2a68c198d4829fcabea26503d4be26c35013ab4`;
- all four lifecycle originals and all responsive/state originals registered by the staging and
  evidence JSON files.

The 3840 image is now deterministic support evidence, not a lifecycle target, because it has the
same graph-first topology as 1920. The authoritative inventory is 72 images: 54 normal, 18
exceptional, zero topology variants.

Measured contract:

- 1920: graph canvas 1689×680; canvas and Save right edges both 1911;
- 2560: graph canvas 1035×417; canvas and Save right edges both 1257; graph/settings right edges
  both 1266;
- 3840: the same 1035×417 and the same aligned right edges; no Processed response table is mounted.

## Gates and qualitative decision

Independently run:

```powershell
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py
python -m py_compile docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

Complete every applicable V-01–V-16 and Q-01–Q-20 checklist item with direct evidence. In
particular, reject if the graph still crosses the Save action edge, changes aspect, appears
distorted/unprofessional, retains any 3840 response table, introduces filler, or leaves space
between related task components rather than only at the right/bottom after the complete cluster.
Return `approve` or `changes_requested`; do not edit files.
