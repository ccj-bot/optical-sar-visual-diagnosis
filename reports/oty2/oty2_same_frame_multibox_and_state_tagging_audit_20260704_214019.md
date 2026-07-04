# OTY2 Same-Frame Multi-Box And State Tagging Audit

Timestamp: `20260704_214019`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`

## Boundary

This audit diagnoses same-frame multi-box observations and normalizes optical state tags. It does not build a fragment relation graph, implement automatic grouping, modify runtime logic, tune thresholds, switch trackers, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, enter SAR pairing, enter support audit, claim identity truth, or promote `GM_RM011` into the clean `215` pool.

The audit uses existing non-archive optical artifacts only. SAR GT, SAR image observation, and GT-local fields were not used for optical runtime identity.

## Inputs

Required sources read:

- `docs\OTY2_SESSION_START_HERE.md`
- `docs\OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs\OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `reports\oty2\oty2_optical_stream_failure_layer_attribution_audit_20260704_213127.md`
- `reports\oty2\samples\oty2_optical_stream_failure_layer_attribution_samples_20260704_213127.csv`

Artifacts inspected read-only:

| Scene | OTY0 detection table | State/context references |
| --- | --- | --- |
| `GM_RM011` | `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv` | OTY1 state fields and OTY1a merge fields for tag vocabulary only |
| `GM_RM019` | `outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv` | OTY1 state fields and OTY1a merge fields for tag vocabulary only |
| `GM_RM017` | `outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv` | OTY1 state fields and OTY1a merge fields for tag vocabulary only |

New artifacts:

- `docs\OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports\oty2\samples\oty2_same_frame_multibox_grouping_samples_20260704_214019.csv`

The sample CSV contains diagnostic detection IDs and scalar proxies only. It contains no bbox coordinates, final annotations, revised GT, final boxes, selector/ranking outputs, or runtime prediction artifacts.

## Same-Frame Multi-Box Probe

The probe grouped OTY0 detections by `scene + optical_frame_num`, computed pairwise overlap proxy, center distance, class agreement, size relation, and frame crowding count, and assigned review-safe grouping diagnosis labels. No detections were merged.

| Scene | Frames with detections | Crowded frames | Same-frame pairs | Candidate multi-box pairs | Label distribution |
| --- | ---: | ---: | ---: | ---: | --- |
| `GM_RM011` | 233 | 147 | 233 | 67 | `unjudgeable_without_visual_review=49; class_instability_duplicate_like=9; multi_vehicle_crowding_unresolved=5; possible_partial_full_same_vehicle_competition=3; likely_neighbor_vehicle_competition=1` |
| `GM_RM019` | 193 | 100 | 196 | 108 | `likely_neighbor_vehicle_competition=34; unjudgeable_without_visual_review=32; multi_vehicle_crowding_unresolved=31; possible_partial_full_same_vehicle_competition=10; class_instability_duplicate_like=1` |
| `GM_RM017` | 100 | 69 | 167 | 22 | `unjudgeable_without_visual_review=10; multi_vehicle_crowding_unresolved=6; class_instability_duplicate_like=3; likely_neighbor_vehicle_competition=3` |

These counts are diagnostic, not threshold-tuning results. They show that all three scenes have same-frame multi-box issues, with GM_RM019 most severe by candidate count and GM_RM011 also clearly above GM_RM017.

## Grouping Diagnosis Labels

| Label | Meaning | Automatic grouping status |
| --- | --- | --- |
| `likely_duplicate_same_vehicle_observation` | Same-frame boxes have substantial overlap and close centers without class conflict | diagnostic candidate only; not identity truth |
| `possible_partial_full_same_vehicle_competition` | One box may be local/partial and another fuller, but same-vehicle relation is not proven | no automatic grouping; requires temporal/state evidence |
| `likely_neighbor_vehicle_competition` | Low overlap or geometry suggests nearby vehicles rather than duplicate boxes | blocks grouping |
| `class_instability_duplicate_like` | Boxes are nearly identical spatially but class labels differ | diagnostic candidate only; class conflict blocks direct merge |
| `multi_vehicle_crowding_unresolved` | Crowded frame has multiple plausible interpretations | no automatic grouping |
| `unjudgeable_without_visual_review` | Scalar evidence cannot separate duplicate, partial/full, and neighbor competition | visual review or stronger temporal context required |

The labels are not identity truth and do not create final boxes.

## Cross-Scene Findings

1. All three scenes contain same-frame multi-box candidates.

`GM_RM011`, `GM_RM019`, and `GM_RM017` all include high-overlap or close-neighbor same-frame pairs. This confirms the issue is global, not GM_RM011-only.

2. GM_RM011 and GM_RM019 are more severe.

`GM_RM019` has the largest candidate count (`108`) and the most neighbor/crowding competition. `GM_RM011` has many unjudgeable pairs and repeated class-instability duplicate-like pairs. `GM_RM017` has the same pattern but fewer candidates (`22`) and was previously easier for tracking.

3. GM_RM017 is a simpler comparator, not a clean exception.

The stable scene still has class-instability duplicate-like pairs, likely neighbor competition, and unresolved crowded frames. Its relative stability likely comes from easier association after detection, not absence of multi-box observations.

## Same-Vehicle-Like Duplicate Observations

Likely duplicate-like observations include:

- `GM_RM011` frame `47`: detections `GM_RM011_000047_002` and `GM_RM011_000047_003`, overlap proxy `0.997`, center distance `0.2`, classes `car|truck`.
- `GM_RM019` frame `4`: detections `GM_RM019_000004_002` and `GM_RM019_000004_003`, overlap proxy `0.998`, center distance `0.1`, classes `car|bus`.
- `GM_RM017` frame `127`: detections `GM_RM017_000127_002` and `GM_RM017_000127_003`, overlap proxy `0.994`, center distance `0.6`, classes `bus|truck`.
- `GM_RM019` frame `1`: detections `GM_RM019_000001_002` and `GM_RM019_000001_003`, overlap proxy `0.714`, center distance `25.5`, classes `car|car`.

These are good candidates for a later same-frame grouping diagnostic, but not for automatic merge. The class-conflicting cases especially need a detection-postprocess explanation before any grouping rule can be considered.

## Neighbor And Crowding Competition

Likely neighbor competition or unresolved crowding includes:

- `GM_RM019` frame `77`, detections `000077_002/000077_003`: low overlap (`0.005`) and close center distance (`31.1`) in a 5-detection frame.
- `GM_RM011` frame `147`, detections `000147_003/000147_004`: low overlap (`0.062`) and close center distance (`67.9`) in a 4-detection frame.
- `GM_RM017` frame `151`, detections `000151_002/000151_003`: low overlap (`0.088`) and near-neighbor geometry.

These cases should block automatic grouping. They can later become competition nodes or negative edges in a fragment relation graph, but this audit does not build that graph.

## Partial/Full And Visual Review Cases

Possible partial/full same-vehicle competition appears in all scenes except that GM_RM017 is lighter:

- `GM_RM011` frames `260-261` include one-small-one-large same-class pairs with moderate overlap.
- `GM_RM019` frame `1` and frame `72` include one-small-one-large same-class pairs under crowding.
- `GM_RM017` frame `154` has one-small-one-large same-class geometry, but summary evidence is not enough to decide same vehicle versus neighbor competition.

These require temporal continuity, state tags, and possibly visual review. They are not safe for automatic grouping from same-frame scalar evidence alone.

## Optical State Tag Normalization

The new spec is `docs\OTY2_OPTICAL_STATE_TAGGING_SPEC.md`.

Tags that are already supported by existing fields or direct OTY0 pair proxies:

| Tag | Current evidence source |
| --- | --- |
| `edge_contact` | OTY0 bbox proximity to image boundary; OTY1 `touch_*`, `touch_any`, `boundary_contact_count` |
| `truncation_like` | OTY1 `truncation_likelihood_proxy`, boundary contact plus size-change proxies |
| `partial_visible` | one-small-one-large same-frame relation; OTY1 bbox area/aspect context |
| `partial_to_full_transition` | OTY1a `partial_to_full_box_transition_proxy`, area/aspect endpoint ratios |
| `occlusion_like` | OTY1/OTY1t missing gap, lost/reactivated, and gap fields; sign only, not true occlusion |
| `short_missing_gap` | OTY1a gap fields and OTY1t gap/lost fields |
| `multi_object_competition` | per-frame detection count, neighbor counts, competing merge counts |
| `duplicate_overlap_detection` | same-frame overlap proxy, center distance, OTY1t duplicate/overlap unmatched bucket |
| `neighbor_competition` | low overlap plus close center distance, OTY1 neighbor ambiguity fields |
| `shape_instability` | OTY1 size/aspect proxies, OTY1a shape transition fields |
| `class_instability` | OTY0 class mismatch under high spatial overlap, OTY1a class consistency fields |

Tags that still need stronger evidence before reconnect rules:

- `partial_visible`: needs temporal consistency to distinguish local same-vehicle box from neighbor.
- `occlusion_like`: can only mark a sign; true occlusion cannot be claimed from current fields.
- `truncation_like`: can only mark edge/FOV-like evidence; true truncation cannot be claimed.
- `neighbor_competition`: scalar geometry can flag risk, but visual or temporal context is needed for hard separation.
- `duplicate_overlap_detection`: high overlap is a strong postprocess signal, but it is not identity truth.

## Fragment Relation Graph Readiness

Condition status: partially ready.

Ready inputs:

- same-frame multi-box candidates are identified across the three scenes;
- diagnostic grouping labels are normalized;
- state tags are specified with observable fields and forbidden uses;
- duplicate-like observations and neighbor competition are separated at the diagnostic-label level.

Missing before fragment relation graph can be trusted:

- normalized per-detection state tag table across all candidate frames;
- explicit same-frame grouping candidates preserved as observation-level context;
- temporal checks connecting same-frame grouping evidence to adjacent-frame fragments;
- review-safe visual evidence for unjudgeable and partial/full cases;
- global rule validation that does not collapse neighbor competition into same-target identity.

Therefore the next step may prepare a fragment relation graph input, but it should not yet implement automatic reconnect or merge rules.

## Answers To Required Questions

1. Do all three scenes have same-frame multi-box problems?

Yes. All three scenes contain duplicate-like, neighbor, crowding, or unjudgeable same-frame multi-box candidates.

2. Are GM_RM011 and GM_RM019 more severe?

Yes. GM_RM019 is most severe by candidate count and neighbor/crowding labels. GM_RM011 has many unjudgeable and class-instability duplicate-like pairs. GM_RM017 has fewer candidates.

3. Does GM_RM017 have the same problem at lower severity?

Yes. GM_RM017 still has high-overlap class-instability duplicate-like pairs and neighbor/crowding candidates, but the downstream tracker summary was more stable.

4. Which multi-boxes look like same-vehicle duplicate observations?

High-overlap, near-identical-center pairs such as GM_RM011 frame `47`, GM_RM019 frame `4`, and GM_RM017 frame `127` are duplicate-like observations. They remain diagnostic candidates only.

5. Which look like neighbor competition?

Low-overlap close-center pairs in crowded frames, especially GM_RM019 frame `77`, GM_RM011 frame `147`, and GM_RM017 frame `151`, are more consistent with neighbor competition and should block grouping.

6. Which require visual review?

All class-instability duplicate-like pairs, all possible partial/full cases, all unjudgeable cases, and all crowded unresolved cases require review or stronger temporal evidence before grouping.

7. Which state tags are supported by existing fields?

`edge_contact`, `truncation_like`, `partial_visible`, `partial_to_full_transition`, `occlusion_like`, `short_missing_gap`, `multi_object_competition`, `duplicate_overlap_detection`, `neighbor_competition`, `shape_instability`, and `class_instability` all have existing proxies, though some are only weak signs.

8. Which tags need more evidence?

`partial_visible`, `occlusion_like`, `truncation_like`, `neighbor_competition`, and `duplicate_overlap_detection` need temporal or visual context before they can support reconnect.

9. Is the pipeline ready to enter fragment relation graph?

It is ready to define graph inputs, not ready to perform automatic reconnect. Same-frame observation grouping context and normalized state tags should be carried into the graph as evidence, not identity truth.

10. What is still missing?

Missing pieces are a normalized per-detection state tag table, visual review for unjudgeable/partial-full samples, and a cross-scene validation rule that distinguishes duplicate same-vehicle observations from neighbor competition.

## Recommendation

Next step: prepare fragment relation graph inputs only after carrying forward the same-frame grouping diagnosis labels and normalized state tags. The graph should consume these as uncertainty/context fields and must still avoid automatic identity merge, final boxes, SAR pairing, support audit, selector/ranking, weighted fusion, threshold tuning, and clean `215` promotion.
