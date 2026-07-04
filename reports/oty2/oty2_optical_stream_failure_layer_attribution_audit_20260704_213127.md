# OTY2 Optical Stream Failure-Layer Attribution Audit

Timestamp: `20260704_213127`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`

## Boundary

This is an implementation-preflight attribution audit. It does not implement a new mechanism, change runtime logic, tune thresholds, switch trackers, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, enter SAR pairing, enter support audit, claim identity truth, or promote `GM_RM011` into the clean `215` pool.

Inputs are existing non-archive optical-stream artifacts and reports. SAR GT, SAR image observation, and GT-local energy fields were not used for optical runtime identity or for sample attribution.

## Input Sources

Required reading used:

- `docs\OTY2_SESSION_START_HERE.md`
- `docs\OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs\OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `reports\oty2\oty2_cross_scene_optical_stream_generalization_audit_20260704_172652.md`
- `reports\oty2\oty2_gm011_object_stream_reconstruction_report_20260704_gm011_oty_stream.md`

Existing artifacts inspected read-only:

| Scene | OTY0 | OTY1 | OTY1a | OTY1t | P4G |
| --- | --- | --- | --- | --- | --- |
| `GM_RM011` | `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream` | `outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream` | `outputs\oty1a_fragment_merge_audit_20260704_gm011_oty_stream` | `outputs\oty1t_tracker_audit_bytetrack_20260704_gm011_oty_stream` | `outputs\oty1t_object_hypothesis_generalization_audit_20260704_gm011_oty_stream` |
| `GM_RM019` | `outputs\oty0_yolo_detection_stream_audit_20260701_170751` | `outputs\oty1_optical_tracklet_audit_20260701_175422` | `outputs\oty1a_fragment_merge_audit_20260701_190559` | `outputs\oty1t_tracker_audit_bytetrack_20260701_205928` | `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500` |
| `GM_RM017` | `outputs\oty0_yolo_detection_stream_audit_20260701_181317` | `outputs\oty1_optical_tracklet_audit_20260701_181347` | `outputs\oty1a_fragment_merge_audit_20260701_190431` | `outputs\oty1t_tracker_audit_bytetrack_20260701_205803` | `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500` |

Small diagnostic summary written:

- `reports\oty2\samples\oty2_optical_stream_failure_layer_attribution_samples_20260704_213127.csv`

The sample CSV contains diagnostic IDs, counts, statuses, and attribution notes only. It contains no bbox coordinates, final annotations, revised GT, final boxes, selector/ranking outputs, or runtime prediction artifacts.

## Sampling Strategy

The audit samples are intentionally small and risk-targeted. They were selected from existing CSVs to cover:

- short tracklets;
- unmatched detections;
- duplicate-overlap tracks;
- ambiguous merge candidates;
- review-required object hypotheses;
- same-frame multi-box competition;
- boundary/truncation/shape-change indicators;
- a relatively stable `GM_RM017` contrast case.

`GM_RM011` is the pressure-test scene. `GM_RM019` is the old scene with same-family risk. `GM_RM017` is the simpler comparator: it has stable tracker examples but still contains duplicate boxes and review-required object hypotheses.

## Scene-Level Attribution

| Scene | Primary layer diagnosis | Evidence summary |
| --- | --- | --- |
| `GM_RM011` | Association / stream construction, driven by detection-postprocess instability and multi-object competition | OTY0 detections exist and bbox sanity passed. Failures cluster in shape-transition unmatched detections (`55`), boundary/truncated unmatched detections (`19`), duplicate/overlap unmatched detections (`14`), ambiguous merge edges (`13`), and review-required P4G objects (`23/28`). |
| `GM_RM019` | Same family as GM_RM011, with stronger detection-confidence and duplicate/competition symptoms | Old scene already has shape-transition unmatched detections (`72`), duplicate/overlap unmatched detections (`34`), ambiguous merge edges (`49`), short tracker hypotheses (`9`), duplicate-overlap tracks (`8`), and review-required P4G objects (`19/21`). |
| `GM_RM017` | Easier scene, not proof of mechanism success | It has four stable tracker hypotheses and no duplicate-overlap track status, but still has duplicate/overlap unmatched detections (`6`), boundary/truncated unmatched detections (`4`), review-required P4G objects (`4/6`), and same-frame high-overlap boxes. |

The current evidence points away from a pure detector-ability blocker. The dominant failure layer is association / stream construction, but it is fed by detection-postprocess instability and multi-object competition. Optical state evidence is observable and important, but it currently explains why reconnect is uncertain rather than proving identity.

## Detector Ability Evidence

Detector ability is not the primary blocker for `GM_RM011`: OTY0 produced `422` detections across `233` frames, with bbox coordinate sanity passing. The detector finds vehicles often enough to expose downstream association pressure.

Detector ability is still a contributor:

- `GM_RM019` has lower confidence distribution in the cross-scene audit (`p25=0.333`, median `0.543`) than `GM_RM017`, so weak observations can contribute to short fragments.
- Same-frame high-overlap pairs often have different class names, such as `car|truck`, `car|bus`, or `bus|truck`. This suggests detector/category instability can feed postprocess and association problems.
- Boundary/truncation state appears frequently in the sampled failures, so detector boxes near image edges or partial views may be incomplete or unstable.

Conclusion: detector ability should be audited as a contributing layer, especially for low-confidence or partial observations, but the present GM_RM011/GM_RM019 failures are not explained by missing detector output alone.

## Detection Postprocess Evidence

Detection postprocess is a concrete failure contributor. The clearest evidence is same-frame, highly overlapping multi-box output:

| Scene | Sample | Evidence | Attribution |
| --- | --- | --- | --- |
| `GM_RM011` | frame `47`, detections `002/003` | same frame has 3 detections; pair IoU proxy `0.997`; center distance `0.2`; classes `car|truck` | likely same-vehicle duplicate observation, but class instability blocks direct merge |
| `GM_RM019` | frame `4`, detections `002/003` | same frame has 5 detections; pair IoU proxy `0.998`; center distance `0.1`; classes `car|bus` | same duplicate-like pattern exists in the old scene |
| `GM_RM017` | frame `127`, detections `002/003` | same frame has 3 detections; pair IoU proxy `0.994`; center distance `0.6`; classes `bus|truck` | simpler scene still has duplicate-like observations |

Unmatched detections also point to postprocess instability:

- `GM_RM011_000050_003` was unmatched as `duplicate_or_overlap_rejected`, while it overlapped nearest tracker `bt_0020` with IoU proxy `0.770` and center distance `3.44`.
- `GM_RM019_000001_003` had the same bucket, IoU proxy `0.690`, center distance `24.72`, and an OTY1a ambiguous edge relation.
- `GM_RM017_000128_003` had IoU proxy `0.940` and center distance `1.67` to an existing tracker.

These are not final boxes or identity claims. They show that same-frame duplicate/local/partial observations are entering the association stage.

## Association / Stream Construction Evidence

Association is the main layer where the stream fails to close.

`GM_RM011` examples:

- `oty1_tracklet_0024`: only 3 detections on frames `212-214`, with `neighbor_ambiguity_count=3`, `boundary_contact_count=3`, and mean area change `0.323`. This is a short local fragment with state and competition risk.
- `bt_0046`: 18 detections on frames `213-245`, but `duplicate_track_overlap_count=2`, `lost=2`, and `reactivated=1`. This is not a clean identity stream.
- `oty1_tracklet_0003__oty1_tracklet_0007`: gap `2`, endpoint distance `54.21`, bridge IoU proxy `0.689`, but competing merge counts `4/5`. The relation is geometrically plausible but association-ambiguous.

`GM_RM019` examples:

- `oty1_tracklet_0040`: only 2 detections, with both neighbor ambiguity and boundary contact.
- `bt_0069`: 17 detections but duplicate-overlap count `2` and possible ID switch count `1`.
- `oty1_tracklet_0013__oty1_tracklet_0034`: gap `5`, endpoint distance `60.05`, bridge IoU proxy `0`, aspect transition review, and competing merge counts `14/2`. This is blocked by competition and weak bridge evidence.

`GM_RM017` contrast:

- `bt_0012`: 49 detections on frames `162-210`, no missing gap, no duplicate overlap, no possible ID switch. It is a stable comparator, but still only a tracker hypothesis, not identity truth.

Conclusion: the next pre-implementation question should not be "which tracker ID is correct?" It should be "which association edges are strong, weak, ambiguous, or blocked after accounting for state and competition?"

## Multi-Object Competition Evidence

Multi-object competition appears in all three scenes, but severity differs.

Likely same-vehicle duplicate observations:

- `GM_RM011` frame `47`, pair `002/003`: extremely high overlap and near-identical centers.
- `GM_RM019` frame `4`, pair `002/003`: extremely high overlap and near-identical centers.
- `GM_RM017` frame `127`, pair `002/003`: same pattern in the simpler comparator.

Likely neighbor or competing-fragment cases:

- `GM_RM019` merge edge `oty1_tracklet_0013__oty1_tracklet_0034`: `from_neighbor_ambiguity_count=21`, many competing candidates, zero bridge IoU proxy. This should remain blocked rather than reconnected.
- `GM_RM011` `bt_0046`: duplicate-overlap plus lost/reactivated state means the track can inform a fragment graph, but not identity closure.

Cannot judge safely from current summary alone:

- `GM_RM011` object `oty1t_obj_GM_RM011_bytetrack_bt_0032` has partial/full, duplicate, boundary, and multi-vehicle flags all active. It may contain useful reconnect evidence, but the current summaries are not enough to decide same vehicle vs neighbor competition.
- `GM_RM019` object `oty1t_obj_GM_RM019_bytetrack_bt_0098` has strong same-object support but all major risk flags active; it remains a review-required hypothesis.

Evidence needed for safe reconnect:

- same-frame duplicate grouping evidence before temporal association;
- fragment relation graph showing all competing predecessors/successors;
- optical state tags for boundary, partial/full transition, short missing gaps, and neighbor competition;
- cross-scene confirmation that the rule closes true duplicate/fragment cases without collapsing neighbor competition;
- review-safe visual evidence if the runtime-safe summary remains ambiguous.

## Optical State Tag Observability

State tags are observable enough for audit, but not enough for identity truth.

`edge_contact` / `truncation`:

- Observable through existing `boundary_contact`, `boundary_contact_count`, and OTY1 truncation proxy fields.
- `GM_RM011` sample `oty1_tracklet_0024` has boundary contact on all 3 observations.
- `GM_RM019` sample `oty1_tracklet_0040` has boundary contact on both observations.

`occlusion_like`:

- Must remain a sign, not a true occlusion claim.
- Existing evidence includes tracker `lost`, `reactivated`, and short missing-gap fields.
- `GM_RM011` object `bt_0032` has `lost=2`, `reactivated=1`; `bt_0046` has `lost=2`, `reactivated=1`.

`partial_to_full_transition`:

- Observable through OTY1a `partial_to_full_box_transition_candidate`, P4G `partial_full_transition_present`, and area/aspect transition proxies.
- `GM_RM011` has 25 partial-to-full merge candidates; `GM_RM019` has 10.
- Partial/full flags appear in review-required P4G objects for all three scenes.

`multi_object_competition`:

- Observable through same-frame detection counts, neighbor ambiguity counts, duplicate overlap counts, and competing merge counts.
- `GM_RM019` ambiguous merge sample has `competing_merge_count_from=14` and `from_neighbor_ambiguity_count=21`.

These tags should be used to decide whether a breakpoint is bridgeable, not to declare a physical identity.

## Global Reconnect Candidates vs Blocked Cases

Can enter global reconnect or diagnostic mechanism design:

- same-frame high-overlap duplicate-like pairs, before temporal association;
- duplicate/overlap unmatched detections with high overlap to active tracker hypotheses;
- short-gap merge candidates where bridge IoU and endpoint geometry are plausible but competition must be modeled;
- partial-to-full transition candidates when center motion and timing remain plausible;
- stable comparator tracks from `GM_RM017` as controls, not as truth.

Must remain `review_required` / blocked for now:

- merge candidates with many competitors and weak bridge evidence, such as the `GM_RM019` `0013 -> 0034` edge;
- P4G objects with simultaneous partial/full, duplicate, boundary, and multi-vehicle flags;
- tracker IDs with duplicate-overlap or possible ID-switch status;
- any case where the only justification is that two boxes "look like one vehicle."

## Stop Condition Before Implementation

Stop condition status: partially satisfied for attribution, not satisfied for implementation.

Answered enough to proceed to the next diagnostic design step:

- The GM_RM011 and GM_RM019 failures are primarily association / stream-construction failures fed by detection-postprocess instability and multi-object competition.
- GM_RM019 has same-family risk, so this is not a GM_RM011-only issue.
- GM_RM017 appears easier because stable tracker hypotheses are more common and duplicate-overlap tracker states are absent in the sampled summary.

Not answered enough to implement reconnect logic:

- Same-vehicle duplicate boxes versus neighboring-vehicle competition are not yet separated reliably.
- State tags are observable, but they need a consistent cross-scene tagging table before rules use them.
- Fragment relation edges need full competitor context before any global bridge rule can be trusted.

Therefore implementation should remain stopped.

## Recommendation

Recommendation: first do same-frame multi-box grouping diagnosis plus optical state tagging, then build a fragment relation graph.

Rationale:

1. Same-frame duplicate-like boxes appear in `GM_RM011`, `GM_RM019`, and `GM_RM017`, so detection postprocess is a global input problem.
2. State tags are available from existing fields, but they must be normalized before association can use them.
3. Fragment relation graph construction should come after same-frame observation cleanup and state tagging, because ambiguous merge edges depend on both.

Do not proceed to SAR pairing/support audit, clean `215` promotion, final annotations, revised GT, final boxes, selector/ranking, weighted fusion, threshold tuning, or tracker-ID identity claims.
