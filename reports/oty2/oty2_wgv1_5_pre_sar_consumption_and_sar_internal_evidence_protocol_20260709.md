# OTY2 WGV1.5 pre-SAR consumption and SAR-internal evidence protocol

Date: 2026-07-09

## Scope

WGV1.5 starts a pre-SAR consumption contract and SAR-internal evidence discovery design. It uses WGV1.4b optical outputs as input, but it does not enter SAR execution and does not create SAR-ready annotations.

WGV1.5A defines how optical thread outputs may constrain or prioritize later SAR analysis. WGV1.5B defines a SAR-only evidence schema for a future exploration pass. Current SAR state remains unknown until WGV1.5B/C evidence exploration is completed.

Inputs:

- `reports/oty2/samples/oty2_yolo26l_wgv1_4b_thread_stability_summary_20260709.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4b_edge_boundary_stress_summary_20260709.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4b_visual_evidence_manifest_20260709.csv`

Outputs:

- `reports/oty2/samples/oty2_yolo26l_wgv1_5a_optical_to_sar_consumption_contract_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5b_sar_internal_evidence_schema_20260709.csv`

## Hard boundary statements

- Optical evidence is not SAR evidence.
- Optical threads may only constrain or prioritize SAR exploration.
- SAR identity support requires independent SAR-internal evidence.
- Long-window optical stability does not imply SAR-ready annotation.
- Current SAR state remains unknown until WGV1.5B/C evidence exploration is completed.
- No final boxes, GT boxes, revised annotations, selector/ranking outputs, runtime prediction artifacts, or tracked media outputs are generated here.

## WGV1.5A consumption classes

### optical_identity_constraint

Allowed SAR use: prioritize independent SAR inspection inside the relevant optical time span and carry an optical identity hypothesis into the review queue.

Forbidden SAR use: cannot create SAR-ready labels, final boxes, GT boxes, revised annotations, selector/ranking output, or SAR identity confirmation. Optical continuity cannot be cited as SAR support.

Required evidence before upgrade: SAR-internal vehicle-like scatter, SAR temporal continuity, SAR boundary support, and explicit optical-to-SAR frame mapping uncertainty resolution.

Failure modes: optical primary-box repair may hide duplicate boxes; a stable optical vehicle may be a weak or invisible SAR target; long-window stability may overconstrain SAR if alignment is wrong.

Examples from WGV1.4b: `GM_RM011_WGV14T001`, `GM_RM011_WGV14T004`, and local GM_RM011 edges M001-M004/M006.

### optical_search_hint_only

Allowed SAR use: prioritize where a SAR reviewer or later SAR-only pass should look first. It may suggest a broad interval or target family for exploration.

Forbidden SAR use: cannot constrain SAR identity, merge SAR targets, generate annotations, or claim target continuity.

Required evidence before upgrade: independent SAR vehicle-like signal and continuity over the proposed interval without SAR competitor or boundary contradiction.

Failure modes: weak optical threads may bridge occlusion or missing detections; long gaps such as GM_RM017 181-200 may look plausible optically but fail in SAR; same-color or far objects may be over-associated.

Examples from WGV1.4b: `GM_RM011_WGV14T005`, `GM_RM011_WGV14T006`, and all three GM_RM017 weak threads.

### boundary_preserved

Allowed SAR use: keep SAR hypotheses separated across the boundary and inspect both sides independently for SAR boundary support.

Forbidden SAR use: cannot bridge adjacent vehicles, smooth over a replacement, or merge same-color vehicles.

Required evidence before upgrade: a later written protocol plus SAR-internal boundary evidence and explicit competitor analysis. Optical evidence alone cannot relax the boundary.

Failure modes: SAR search may inherit an optical boundary that is correct optically but misaligned in time; a boundary may hide a SAR frame offset; same-frame competition may produce two SAR-like responses.

Examples from WGV1.4b: GM_RM011 M005, GM_RM011 M016, GM_RM017 M002-M004, and GM_RM017 M006-M009.

### context_only

Allowed SAR use: flag competitor, occlusion, multi-target, replacement, or adjacency context for reviewer attention.

Forbidden SAR use: cannot be treated as same-vehicle continuity, identity support, or a target merge edge.

Required evidence before upgrade: SAR-only evidence must independently identify the physical relation and show it is not background, a static reflector, or another vehicle.

Failure modes: context can be mistaken for continuity; competitor boxes can be suppressed too early; nearby static reflectors may look like multi-target support.

Examples from WGV1.4b: `GM_RM011_WGV14C001`, `GM_RM011_WGV14C002`, and `GM_RM017_WGV14C001` through `GM_RM017_WGV14C007`.

### blocked_for_sar_consumption

Allowed SAR use: documentation only as a blocked risk or backlog item.

Forbidden SAR use: no identity, search contraction, target merge, annotation, final box, GT box, selector, ranking, or runtime prediction use.

Required evidence before upgrade: new SAR-internal evidence plus an explicit protocol change. Optical evidence alone can never unblock it.

Failure modes: identity-risk optical bridges may leak into SAR search; a blocked row may be treated as a low-confidence hint; posthoc findings may be mistaken for runtime permission.

Examples from WGV1.4b: `GM_RM017_WGV14V004` is blocked for consumption because the 181-200 black-sedan bridge is an identity-risk optical edge.

## Contract CSV summary

The WGV1.5A contract contains 50 rows derived from WGV1.4b: 9 thread rows plus 41 edge/context rows.

Class counts:

- `optical_identity_constraint`: 7
- `optical_search_hint_only`: 24
- `boundary_preserved`: 9
- `context_only`: 9
- `blocked_for_sar_consumption`: 1

All rows keep `sar_frame_start_estimate` and `sar_frame_end_estimate` as `not_estimated_pre_sar`. Mapping uncertainty is unresolved in WGV1.5A.

## WGV1.5B SAR-only evidence categories

The future SAR evidence pass must record SAR-internal support using these categories:

- `vehicle_like_scatter`: SAR itself shows vehicle-like scatter, structure, or energy contrast.
- `temporal_continuity`: SAR itself supports continuity across SAR frames.
- `boundary_support`: SAR itself supports separation, replacement, disappearance, or competitor boundary.
- `competitor_or_multi_target_signal`: SAR itself indicates multiple targets or ambiguous nearby target support.
- `background_or_static_reflector_risk`: signal may be static background, infrastructure, or non-vehicle clutter.
- `imaging_quality_or_motion_artifact`: SAR quality, motion, truncation, or artifact blocks a clean read.
- `unknown_or_insufficient_evidence`: SAR evidence is not enough for a support claim.

The schema file is a data dictionary for future evidence units. It does not instantiate any SAR evidence unit and does not claim that SAR support has been found.

## Upgrade gate

A WGV1.4b optical item can move beyond `pre_sar_only` or `blocked` only if a later SAR-only exploration creates independent SAR evidence units and a written WGV1.5B/C decision links those units to a specific consumption class. Until then, SAR consumption status remains `pre_sar_only` or `blocked`, and SAR-ready remains unavailable.

## Validation boundary

Generated artifacts are reports and CSV schemas/contracts only. They contain no tracked images/videos, no output media, no final boxes, no GT boxes, no revised annotations, no selector/ranking outputs, and no runtime prediction artifacts.
