# OTY2 YOLO26l WGV1.4b long-window identity stability stress test

Date: 2026-07-09

## Scope and hard boundary

This is a conservative optical-only WGV1.4b stress test. It uses the existing WGV1.4 accepted / weak / context_only / blocked graph as input and reads the existing WGV1.3 PNG review evidence.

No SAR stage was entered. This report does not create final boxes, GT boxes, revised annotations, selector/ranking output, SAR-ready artifacts, runtime prediction artifacts, or tracked output images/videos. SAR-ready remains `no / blocked` for every tested item.

Inputs:

- `reports/oty2/oty2_yolo26l_wgv1_4_auto_visual_thread_audit_and_repair_20260708.md`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4_vehicle_threads_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4_same_vehicle_edges_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4_temporal_context_edges_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4_blocked_review_items_20260708.csv`
- existing PNG evidence under `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/`

Temporary contact sheets were generated only under the system temp directory for visual reading. They are not repo outputs and are not tracked artifacts.

## Outputs

- Thread summary: `reports/oty2/samples/oty2_yolo26l_wgv1_4b_thread_stability_summary_20260709.csv`
- Edge/context summary: `reports/oty2/samples/oty2_yolo26l_wgv1_4b_edge_boundary_stress_summary_20260709.csv`
- Visual evidence manifest: `reports/oty2/samples/oty2_yolo26l_wgv1_4b_visual_evidence_manifest_20260709.csv`

## Main answer

The WGV1.4 optical threads do not show a new confirmed vehicle-mixing failure under this long-window stress test, but the safe consumption level is uneven.

- `GM_RM011_WGV14T001` is stable enough as an `optical_identity_constraint` inside the optical graph.
- `GM_RM011_WGV14T005` remains visually stable over frames 231-288, including every merge neighborhood from M007-M015, but it should stay `optical_search_hint_only` because the left white SUV competitor appears at frames 286-288 and becomes the selected object after M016.
- GM_RM017 weak threads remain weak. They are not upgraded. They can be kept only as `optical_search_hint_only`, with SAR consumption blocked.
- All known different-vehicle/context boundaries remain preserved, especially GM_RM011 M005/M016 and GM_RM017 M002-M004/M006-M009.

## GM_RM011 accepted-thread stress results

| Thread | Frames | Verdict | Safe as | Stress conclusion |
| --- | ---: | --- | --- | --- |
| `GM_RM011_WGV14T001` | 0-25 | `stable_same_vehicle` | `optical_identity_constraint` | T001+T002 keep one near-field white car. M003 is overlapping/better primary boxes on the same vehicle. |
| `GM_RM011_WGV14T002` | 31-35 | `stable_same_vehicle` | `optical_search_hint_only` | Stable short standalone front-facing white car, but M005 proves it is not the prior right near-field car. |
| `GM_RM011_WGV14T003` | 135-137 | `stable_same_vehicle` | `optical_search_hint_only` | Stable short standalone competition scene, not a long-window identity constraint. |
| `GM_RM011_WGV14T004` | 151-166 | `stable_same_vehicle` | `optical_identity_constraint` | Same white car despite truncation and local scooter/covered-vehicle competition. |
| `GM_RM011_WGV14T005` | 231-288 | `stable_same_vehicle` | `optical_search_hint_only` | T006-T012 keep the right near-field white car across M007-M015. Competitor at 286-288 forces conservative use. |
| `GM_RM011_WGV14T006` | 289-292 | `stable_same_vehicle` | `optical_search_hint_only` | Separate left white SUV after M016, not the right-side car from T005. |

## Boundary preservation checks

- `GM_RM011_WGV12M005`: `boundary_preserved`. Frame 25 selects/right-boxes a near-field white car hood/body crop while a different front-facing white car is also visible. Frames 31-35 select the front-facing white car. Same color is not identity evidence here.
- `GM_RM011_WGV12M016`: `boundary_preserved`. Frames 286-288 still keep the right near-field white car as the WGV14T005 target while a left white SUV competitor is visible. Frames 289-292 select that left SUV. The edge must remain context-only.
- `GM_RM017_WGV12M002-M004`: `boundary_preserved`. These preserve white box truck/van, black sedan, and white SUV as separate identities.
- `GM_RM017_WGV12M006-M009`: `boundary_preserved`. These are black-sedan/white-SUV interleavings and same-frame competition, not same-vehicle continuity.

## Primary-box repair checks

- `GM_RM011_WGV12M003`: `stable_same_vehicle`. Original edge-review PNGs show duplicate/overlapping boxes on the same near-field white car, not a switch to another vehicle.
- `GM_RM017_WGV12M005`: `weak_but_usable`. The white SUV remains plausible across frames 158-164, but black-sedan and box-truck competitors are present, and frame 164 is narrow/ambiguous. Keep weak; do not upgrade.

## GM_RM017 weak-thread stress results

| Thread | Frames | Verdict | Safe as | Stress conclusion |
| --- | ---: | --- | --- | --- |
| `GM_RM017_WGV14T001` | 118-157 | `weak_but_usable` | `optical_search_hint_only` | Far white box truck/van is plausible before and after the black-sedan interleave, but distance/occlusion prevents upgrade. |
| `GM_RM017_WGV14T002` | 149-214 | `weak_but_usable` | `optical_search_hint_only` | Black sedan continuity is plausible, but the 181-200 bridge is an `identity_risk` edge and stays weak. |
| `GM_RM017_WGV14T003` | 158-185 | `weak_but_usable` | `optical_search_hint_only` | White SUV continuity is plausible but interleaved with black sedan and affected by M005 primary-box ambiguity. |

## Consumption boundary

No tested item is SAR-ready. Even rows that are safe as optical identity constraints are only optical graph constraints inside this pre-SAR diagnostic layer. A later SAR consumption protocol would need to be designed separately before any SAR-ready use.

Final/GT/revised annotation status:

- final boxes generated: no
- GT boxes generated: no
- revised annotation generated: no
- selector/ranking outputs generated: no
- runtime prediction artifacts generated: no
- tracked output images/videos generated: no
- SAR entered: no
- SAR-ready: no / blocked for all rows
