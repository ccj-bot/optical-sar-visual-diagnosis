# OTY2 Optical Timeline Human Review Packet

Date: 2026-07-06
Repository: `D:/profile/research/optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Base HEAD: `2182688 Define OTY2 optical timeline override contract`

## Scope

This packet guides human review of the current optical diagnostic timeline graph. It is based only on the existing node table, edge table, render manifest, and smoke-rendered diagnostic frames.

It does not apply overrides, run detector swap, run a YOLO probe, run tracker replay, enter SAR pairing/support, run selector/ranking, generate final or revised annotation, generate final boxes, or generate GT boxes.

## Source Artifacts

| Role | Path | Status |
| --- | --- | --- |
| Node table | `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv` | 18 rows |
| Edge table | `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv` | 10 rows |
| Render manifest | `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv` | 311 rows |
| Smoke render frames | `outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames` | 198 ignored PNG frames |
| Override template | `manifests/oty2_optical_timeline_override_template.csv` | header-only template |
| Override schema | `configs/oty2_optical_timeline_override_schema.yaml` | dry-run contract |
| Override validator | `tools/diagnostics/validate_oty2_optical_timeline_overrides.py` | dry-run only |

Render frame path convention:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/<scene_id>_<frame:06d>.png
```

Example:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
```

## Review Method

For each edge, inspect the representative frames first, then scan the full key range if the decision is unclear.

Use this judgement scale:

| Decision | Meaning | Override action if a row is needed |
| --- | --- | --- |
| Accept current strong edge | Same physical vehicle is visually supported across the gap. | No override row needed, or `force_strong_connect` for explicit review trace. |
| Accept current weak edge | Same vehicle is plausible but should remain weak/review-labeled. | No override row needed, or `force_weak_connect` for explicit review trace. |
| Upgrade weak to strong | Evidence is strong enough after full-frame review. | `upgrade_to_strong` with `edge_strength=strong`. |
| Downgrade strong to weak | Same vehicle remains plausible but not strong. | `downgrade_to_weak` with `edge_strength=weak`. |
| Forbid connection | The edge switches target, follows non-vehicle content, or competitor cannot be excluded. | `forbid_connect` with `edge_strength=forbidden`. |
| Mark review required | Human review cannot decide safely. | `mark_review_required` with `edge_strength=review_only`. |
| Confirm non-vehicle node | The node is not a vehicle referent. | No override row needed, or node `exclude_non_vehicle` for explicit trace. |
| Select render-only primary box | Existing rendered primary box is visually misleading. | Render `select_diagnostic_primary_box`; use an existing `source_detection_id`; do not write coordinates. |

Important: an override row is not a final label. It only changes the diagnostic timeline graph or diagnostic render manifest after a later explicit apply step.

## Override CSV Hints

Use `manifests/oty2_optical_timeline_override_template.csv` only when the human judgement differs from the current edge, or when you want an explicit review trace.

For edge decisions, fill:

```text
override_id,override_type=edge,override_scope=edge,scene_id,from_node_id,to_node_id,action,edge_strength,reason_code,evidence_frame_start,evidence_frame_end,confidence,review_status,note
```

For node decisions, fill:

```text
override_id,override_type=node,override_scope=node,scene_id,node_id,action,reason_code,confidence,review_status,note
```

For render-only box selection, fill:

```text
override_id,override_type=render,override_scope=event,scene_id,frame_start,frame_end,target_node_id,action=select_diagnostic_primary_box,source_detection_id,reason_code=diagnostic_primary_box_selection,review_status,note
```

Do not add bbox coordinate columns. Do not write final boxes or GT boxes. Do not use the override CSV as manual frame-by-frame annotation.

After editing an override CSV, validate it with:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_optical_timeline_overrides.py --overrides manifests\oty2_optical_timeline_override_template.csv
```

## Strong Same-Vehicle Edges

### GM_RM011_E001

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N001` |
| to_node | `GM_RM011_N002` |
| current_edge_type | `strong_same_vehicle_edge` |
| connection_strength | `strong` |
| from range | `GM_RM011_N001`, `GM_RM011_V001`, frames `13-16` |
| to range | `GM_RM011_N002`, `GM_RM011_V001`, frames `18-35` |
| key frame range | `13-35` |
| rendered frame count in range | 22 |
| visual basis | Same white vehicle front and windshield continue across a short gap. |
| current reason | Strong local diagnostic edge only; not a final identity merge. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000024.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000035.png
```

Human questions:

- Does the white vehicle front/windshield remain the same physical referent from frames `13-16` to `18-35`?
- Is the short missing gap harmless for diagnostic continuity?
- Is there any better competitor that explains the target box after the gap?
- Should this remain `strong`, be downgraded to `weak`, be forbidden, or require review?

Override hint:

- Accept: no row needed.
- Downgrade: `override_type=edge`, `action=downgrade_to_weak`, `edge_strength=weak`, `reason_code=weak_continuity_only`.
- Forbid: `action=forbid_connect`, `edge_strength=forbidden`, `reason_code=forbidden_competitor_switch`.
- Unclear: `action=mark_review_required`, `edge_strength=review_only`, `reason_code=review_uncertain`.

### GM_RM011_E002

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N004` |
| to_node | `GM_RM011_N005` |
| current_edge_type | `strong_same_vehicle_edge` |
| connection_strength | `strong` |
| from range | `GM_RM011_N004`, `GM_RM011_V002`, frames `279-281` |
| to range | `GM_RM011_N005`, `GM_RM011_V002`, frames `283-292` |
| key frame range | `279-292` |
| rendered frame count in range | 13 |
| visual basis | Central white vehicle front and windshield continue; left-edge neighbor is separable. |
| current reason | Strong local edge with competitor-exclusion note. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000279.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000286.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

Human questions:

- Does the central white vehicle remain the same referent across frames `279-292`?
- Is the left-edge neighbor visually separate enough to keep a strong diagnostic edge?
- Do any rendered boxes drift from the central vehicle to the neighbor?
- Should this remain `strong`, be downgraded to `weak`, be forbidden, or require review?

Override hint:

- Accept: no row needed.
- Downgrade: `action=downgrade_to_weak`, `edge_strength=weak`, `reason_code=weak_continuity_only`.
- Forbid: `action=forbid_connect`, `edge_strength=forbidden`, `reason_code=forbidden_competitor_switch`.
- Render-only issue: use `override_type=render`, `action=select_diagnostic_primary_box`, and an existing `source_detection_id`.

## Weak Same-Vehicle Edges

### GM_RM011_E003

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N003` |
| to_node | `GM_RM011_N004` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| to range | `GM_RM011_N004`, `GM_RM011_V002`, frames `279-281` |
| key frame range | `262-281` |
| rendered frame count in range | 12 |
| visual basis | Same white vehicle is plausible, but the visible part changes from rear/side to front/window over a longer gap. |
| current reason | Weak diagnostic edge; do not direct-merge track identity. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000267.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000281.png
```

Human questions:

- Is the rear/side to front/window visible-part transition still the same physical vehicle?
- Is the gap from frame `270` to `279` too large for strong continuity?
- Are there competing vehicles that make this only weak or forbidden?
- Should this remain `weak`, upgrade to `strong`, be forbidden, or require review?

Override hint:

- Accept weak: no row needed, or `action=force_weak_connect`, `edge_strength=weak`.
- Upgrade: `action=upgrade_to_strong`, `edge_strength=strong`, `reason_code=same_vehicle_continuity`.
- Forbid: `action=forbid_connect`, `edge_strength=forbidden`, `reason_code=forbidden_competitor_switch`.
- Unclear: `action=mark_review_required`, `edge_strength=review_only`, `reason_code=review_uncertain`.

### GM_RM011_E004

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N008` |
| to_node | `GM_RM011_N009` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `review_only` |
| from range | `GM_RM011_N008`, `GM_RM011_V003`, frames `135-161` |
| to range | `GM_RM011_N009`, `GM_RM011_V003`, frames `164-166` |
| key frame range | `135-166` |
| rendered frame count in range | 30 |
| visual basis | Right-edge white vehicle may continue, but the successor crop is too thin. |
| current reason | Review-only edge; too little visible vehicle area. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000135.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000149.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000166.png
```

Human questions:

- Does the right-edge vehicle remain visible enough to support any same-vehicle relation?
- Is the successor at frames `164-166` too thin to use beyond review-only?
- Should this stay review-only, become weak, be forbidden, or mark the node/frames as bad detection?
- Is a render marker needed so future review does not over-trust the thin crop?

Override hint:

- Keep review-only: no row needed, or `action=mark_review_required`, `edge_strength=review_only`.
- Upgrade to weak: `action=force_weak_connect`, `edge_strength=weak`, `reason_code=weak_continuity_only`.
- Forbid: `action=forbid_connect`, `edge_strength=forbidden`, `reason_code=edge_contact_thin_crop` or `forbidden_competitor_switch`.
- Bad detection node: use node `mark_bad_detection_node` on `GM_RM011_N009` if the thin crop is not usable.

### GM_RM011_E005

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N010` |
| to_node | `GM_RM011_N011` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N010`, `GM_RM011_V004`, frames `231-233` |
| to range | `GM_RM011_N011`, `GM_RM011_V004`, frames `236-245` |
| key frame range | `231-245` |
| rendered frame count in range | 13 |
| visual basis | Plausible upper side/window to front/hood part transition. |
| current reason | Weak part-transition edge. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000231.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000239.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000245.png
```

Human questions:

- Is the upper side/window region in frames `231-233` plausibly the same vehicle as the front/hood region in frames `236-245`?
- Does full-frame context support a part-state transition rather than a target switch?
- Are competitors present that should keep this weak?
- Should this remain `weak`, upgrade to `strong`, be forbidden, or require review?

Override hint:

- Accept weak: no row needed.
- Upgrade: `action=upgrade_to_strong`, `edge_strength=strong`, `reason_code=same_vehicle_continuity`.
- Forbid: `action=forbid_connect`, `edge_strength=forbidden`, `reason_code=forbidden_competitor_switch`.
- Unclear: `action=mark_review_required`, `edge_strength=review_only`, `reason_code=review_uncertain`.

### GM_RM011_E006

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N012` |
| to_node | `GM_RM011_N013` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N012`, `GM_RM011_V005`, frames `0-4` |
| to range | `GM_RM011_N013`, `GM_RM011_V005`, frames `8-10` |
| key frame range | `0-10` |
| rendered frame count in range | 8 |
| visual basis | Plausible white SUV rear/body to upper-window part transition. |
| current reason | Weak early-scene part-transition edge. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000000.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000003.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000010.png
```

Human questions:

- Does the rear/body region in frames `0-4` plausibly continue to the upper-window strip in frames `8-10`?
- Is the gap and part-state transition acceptable only as weak?
- Is there enough full-frame evidence to exclude competitor or background confusion?
- Should this remain `weak`, upgrade to `strong`, be forbidden, or require review?

Override hint:

- Accept weak: no row needed.
- Upgrade: `action=upgrade_to_strong`, `edge_strength=strong`, `reason_code=same_vehicle_continuity`.
- Forbid: `action=forbid_connect`, `edge_strength=forbidden`, `reason_code=forbidden_competitor_switch`.
- Render-only correction: use `select_diagnostic_primary_box` only if a different existing detection is a better diagnostic primary box.

## Forbidden Edges

### GM_RM017_E001

| Field | Value |
| --- | --- |
| scene_id | `GM_RM017` |
| from_node | `GM_RM017_N001` |
| to_node | `GM_RM017_N003` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM017_N001`, `GM_RM017_V001`, frames `145-185` |
| to range | `GM_RM017_N003`, `GM_RM017_V003`, frames `162-214` |
| key frame range | `145-214` |
| rendered frame count in range | 70 |
| visual basis | Dense frames show two separate dark sedans, not one target. |
| current reason | Forbidden false-merge guard between leading and trailing dark sedans. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000145.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000179.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000214.png
```

Human questions:

- Are `GM_RM017_N001` and `GM_RM017_N003` clearly two different dark sedans?
- Does the white SUV/context vehicle separate the leading and trailing dark sedans?
- Would any appearance similarity create a false merge if this edge were allowed?
- Should this remain forbidden, become weak/strong, or require review?

Override hint:

- Accept forbidden: no row needed.
- If only weakly connectable: `action=force_weak_connect`, `edge_strength=weak`, `reason_code=weak_continuity_only`.
- If clearly same vehicle: `action=force_strong_connect`, `edge_strength=strong`, `reason_code=same_vehicle_continuity`.
- Unclear: `action=mark_review_required`, `edge_strength=review_only`, `reason_code=review_uncertain`.

### GM_RM011_E007

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N003` |
| to_node | `GM_RM011_N006` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| to range | `GM_RM011_N006`, `GM_RM011_FORBIDDEN_CONTEXT_001`, frames `283-292` |
| key frame range | `262-292` |
| rendered frame count in range | 22 |
| visual basis | Successor box falls on a left-edge competing vehicle while the central white car remains separate. |
| current reason | Forbidden bs_0061 to bs_0064 bridge. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000280.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

Human questions:

- Does the target switch from the central white vehicle to a left-edge competitor?
- Is the central white vehicle still visible separately when the successor appears?
- Should this remain a hard forbidden edge?
- Is a render marker needed to make the forbidden competitor relation visible during review?

Override hint:

- Accept forbidden: no row needed.
- If reviewer wants the marker visible: use render `show_forbidden_edge_marker`.
- If actually weak: `action=force_weak_connect`, `edge_strength=weak`, `reason_code=weak_continuity_only`.
- If uncertain: `action=mark_review_required`, `edge_strength=review_only`, `reason_code=review_uncertain`.

### GM_RM011_E008

| Field | Value |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N007` |
| to_node | `GM_RM011_N003` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM011_N007`, `GM_RM011_FORBIDDEN_CONTEXT_002`, frames `256-261` |
| to range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| key frame range | `256-270` |
| rendered frame count in range | 15 |
| visual basis | Side/window strip switches to left-edge rear fragment or competing region. |
| current reason | Forbidden proximity/appearance bridge. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000263.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000270.png
```

Human questions:

- Does the before segment describe a side/window strip that cannot be safely linked to `GM_RM011_N003`?
- Is the apparent proximity or appearance match misleading?
- Can competitor switch be excluded, or should the edge remain forbidden?
- Should this remain forbidden, become weak/strong, or require review?

Override hint:

- Accept forbidden: no row needed.
- If weak only: `action=force_weak_connect`, `edge_strength=weak`, `reason_code=weak_continuity_only`.
- If same vehicle is clear: `action=force_strong_connect`, `edge_strength=strong`, `reason_code=same_vehicle_continuity`.
- If uncertain: `action=mark_review_required`, `edge_strength=review_only`, `reason_code=review_uncertain`.

## Non-Vehicle Exclusion

### GM_RM017_E002

| Field | Value |
| --- | --- |
| scene_id | `GM_RM017` |
| from_node | `GM_RM017_N005` |
| to_node | `GM_RM017_N005` |
| current_edge_type | `non_vehicle_exclusion` |
| connection_strength | `excluded` |
| node range | `GM_RM017_N005`, `GM_RM017_NONVEHICLE_001`, frames `121-129` |
| key frame range | `121-129` |
| rendered frame count in range | 9 |
| visual basis | Box follows a foreground barrier or temporary structure, not a vehicle. |
| current reason | Unary exclusion edge for non-vehicle track content. |

Representative rendered frames:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000121.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000125.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000129.png
```

Human questions:

- Is the boxed content a foreground barrier or temporary structure rather than a vehicle?
- Should the node remain excluded from the vehicle timeline?
- Is this better described as `exclude_non_vehicle`, `mark_bad_detection_node`, or `mark_review_required`?
- Is a non-vehicle marker needed in diagnostic rendering?

Override hint:

- Accept exclusion: no row needed, or node `action=exclude_non_vehicle`, `reason_code=non_vehicle_barrier`.
- If it is actually a vehicle node: node `action=keep_vehicle_node`, `reason_code=custom_vehicle_referent`.
- If the box is simply unusable: node `action=mark_bad_detection_node`, `reason_code=bad_detection_box_fit`.
- If uncertain: node `action=mark_review_required`, `reason_code=review_uncertain`.
- Render marker only: render `action=show_non_vehicle_marker`.

## Completion Checklist

Before any later apply step, confirm:

- Each of the 10 edges has one human decision: accept current, change strength, forbid, exclude, or review-required.
- Any override rows use only `node`, `edge`, or `render` override types.
- No override row contains bbox coordinates.
- `select_diagnostic_primary_box` references an existing `source_detection_id` from the render manifest.
- The override CSV passes the dry-run validator.
- No final annotation, revised annotation, final boxes, GT boxes, SAR output, detector output, tracker replay output, selector/ranking output, or committed image/video artifact is produced.
