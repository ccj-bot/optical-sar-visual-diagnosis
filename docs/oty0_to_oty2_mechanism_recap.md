# OTY0 to OTY2-P0 Mechanism Recap

This recap freezes the current mechanism state before any OTY2-P1 or OTY3 work.
It is a documentation checkpoint only. It does not implement temporal metadata
alignment, SAR band generation, SAR search corridors, SAR GT coverage, SAR
evidence sampling, selector/G2/A008 scoring, training, threshold tuning, or
annotation proposals.

## Section A: Current Chain

The current runtime-safe chain is:

```text
raw optical frames
-> YOLO detections
-> optical tracklets / state stream
-> fragment merge review hints
-> standard MOT tracker hypotheses
-> same-frame observation clusters
-> object-level optical hypotheses
-> object-level temporal alignment windows
```

The chain is now object-level at the OTY2 boundary:

- A detection box is one optical observation, not a physical object.
- A tracker id is a continuity hypothesis, not confirmed identity.
- `object_hypothesis_id` is the runtime optical object unit for later OTY2/OTY3 work.
- Primary observations provide temporal continuity.
- Secondary observations provide uncertainty, partial/full transition, duplicate-observation, and state-change evidence.

This is why OTY2-P0 consumes P4G object-level outputs rather than consuming raw
OTY0 detections, OTY1 tracklets, OTY1a merge edges, or OTY1t tracker assignments
directly.

## Section B: Stage-by-stage Contract

| stage | main question solved | allowed runtime inputs | forbidden inputs | main outputs | status | remaining blockers |
| --- | --- | --- | --- | --- | --- | --- |
| OTY0 | Can raw optical frames produce a runtime YOLO vehicle detection stream? | raw optical frame paths, YOLO model/config, scene frame inventory | `review_queue.csv`, `final_gt_working.csv`, SAR GT, final/manual/oracle/review fields, selector/G2/A008, thresholds/training | optical frame inventory, YOLO dependency audit, `oty0_yolo_detection_table.csv`, detection schema, runtime/posthoc boundary report | completed for GM_RM019 and GM_RM017; GM_RM019 has 334 detections, GM_RM017 has 215 detections | GM_RM011 has frame inventory but no committed downstream OTY chain in the current P4G/OTY2-P0 run |
| OTY1 | Can YOLO detections form optical tracklet candidates and an optical state stream without posthoc sources? | OTY0 detection table only, optical frame index, geometry audit limits | SAR GT, review/final/manual/oracle fields, posthoc IoU, selector/ranker, SAR band | tracklet candidate edges, tracklet components, `oty1_optical_tracklet_state_timeseries.csv`, quality audit | completed for GM_RM019 and GM_RM017; candidates remain geometry-only and unconfirmed | no hard OTY1 blocker, but many ambiguous/short fragments remain review or uncertainty signals |
| OTY1a | Can fragment relations be summarized as review hints without creating identity truth? | OTY1 tracklet components and optical state rows | confirmed identity, SAR evidence, SAR GT, selector/G2/A008, annotation proposal | fragment merge candidate edges, cross-scene merge summary, metric definitions | completed for GM_RM019 and GM_RM017; 101 review candidates including 49 ambiguous competing candidates | ambiguous candidates must not be force-merged |
| OTY1t-P0/P1/P2 | Can standard MOT trackers replay the OTY0 detection stream and expose tracker-level failure modes? | OTY0 detection table and optical frame inventory for replay gaps | OTY1/OTY1a as identity truth, SAR alignment, SAR band, SAR GT, SAR evidence, selector/training | tracker tracks, detection assignments, tracker audit summaries, tracker diagnosis, cross-tracker comparison | ByteTrack and BoT-SORT ran for GM_RM019; ByteTrack ran for GM_RM017; tracker ids remain optical hypotheses | trackers do not confirm 0039/0045 identity; OC-SORT/StrongSORT remain missing/unsupported adapters |
| OTY1t-P3 | What same-frame observations and bbox provenance explain tracker choices around the hard case? | OTY0 detections, OTY1 state rows, OTY1t tracker assignments | SAR content/GT/evidence, selector, training, annotation proposal | same-frame observation clusters, tracker association choice audit, bbox provenance audit | completed for GM_RM019 0039/0045 | outputs are review-only optical hypotheses; they do not confirm object identity |
| OTY1t-P4 | Can the local hard case be represented as one object-level optical hypothesis with primary/secondary observations? | P3 clusters, tracker main trajectory, OTY1a review hints, optical bbox provenance | SAR alignment, SAR band, SAR GT, final/manual/oracle/review fields | one GM_RM019 0039/0045 object hypothesis, 33 object-frame state rows | completed; main track `bt_0098`, frame-172 primary `GM_RM019_000172_001`, secondary `GM_RM019_000172_002` | identity remains `same_object_hypothesis_review_required`, not confirmed |
| OTY1t-P4G | Can the object-level hypothesis layer generalize across available scenes? | OTY0 detections, OTY1 state rows, OTY1a hints, OTY1t tracker outputs | SAR alignment/band/GT/evidence, selector/G2/A008, training, annotation proposal | `oty1t_object_hypotheses_generalized.csv`, `oty1t_object_frame_state_timeseries_generalized.csv`, orphan observations, ambiguity report | completed for GM_RM017 and GM_RM019; 27 object hypotheses and 980 object-frame states | GM_RM011 is not in P4G; review_required and ambiguity remain carried uncertainty |
| OTY2-P0 | Can object-level optical states be gated and mapped to SAR temporal frame/window candidates without entering SAR space? | P4G object hypotheses, P4G object-frame states, orphan/ambiguity context for uncertainty only, optical/SAR frame inventory counts | SAR image content, SAR GT, final/manual/oracle/review fields, posthoc IoU, selector/G2/A008, training, SAR band, annotation proposals | scene input status, readiness gating, object alignment frame map, object temporal window candidates, uncertainty report | completed for GM_RM017 and GM_RM019; 681 frame-map rows and 18 temporal windows, all `frame_ratio_hypothesis` | exact timestamp/anchor alignment is not solved; GM_RM011 is `blocked_missing_p4g` |

## Section C: Runtime-safe Boundary

The following sources and signals are still forbidden from runtime construction:

- SAR GT
- SAR image content
- final/manual/oracle/review fields
- `review_queue.csv`
- `final_gt_working.csv`
- posthoc IoU
- selector/G2/A008
- training/tuned thresholds
- annotation proposal labels

These sources may appear only in their allowed audit layer. In particular, SAR
GT can only appear in OTY4 posthoc coverage audit. It cannot generate OTY0
detections, OTY1 tracklets, OTY1a merge hints, OTY1t tracker ids, P4G object
hypotheses, OTY2 temporal windows, SAR bands, or annotation proposals.

The current chain keeps these boundary flags false at OTY2-P0:

```text
posthoc_sources_used_for_runtime_tracking = false
sar_image_content_used = false
sar_gt_coverage_entered = false
sar_band_entered = false
annotation_proposal_entered = false
identity_truth_claimed = false
```

## Section D: Object-level Logic

The system moved from detection-level and tracker-level records to
object-level records because neither individual detections nor tracker ids are
stable enough to be the optical unit passed to SAR.

Detection-level evidence is local and per-frame. It can show a vehicle-like box,
but it cannot by itself say that the same physical object persists across
frames. Tracker-level evidence provides continuity, but tracker ids can be
fragmented, reactivated, bridged through the wrong observation, or split by
partial/full detection changes. Object-level hypotheses keep the useful part of
the main tracker trajectory while carrying the uncertainty that the tracker
cannot resolve.

GM_RM019 0039/0045 is the mechanism example:

- `bt_0098` is the main tracker trajectory.
- 0039 partial/duplicate/edge observations are secondary observations.
- `GM_RM019_000172_001` is the primary frame-172 observation.
- `GM_RM019_000172_002` is the secondary frame-172 observation.
- `object_hypothesis_id` carries both the main trajectory and the secondary uncertainty.
- `identity_status` remains review-required, not confirmed.

The object hypothesis for this case is therefore suitable for OTY2 only as a
temporal alignment unit with uncertainty expansion:

```text
object_hypothesis_id = oty1t_obj_GM_RM019_bytetrack_bt_0098
recommended_use_for_oty2 = main_track_with_uncertainty_handoff
oty2_gate = use_with_uncertainty_expansion
uncertainty_policy = expanded_window
```

The lesson generalizes beyond this case. P4G produced 27 object hypotheses over
GM_RM017 and GM_RM019, including stable main-track objects, uncertainty-handoff
objects, ambiguous low-confidence hints, and short/noise hypotheses that OTY2
must exclude.

## Section E: OTY2-P0 Status

Current OTY2-P0 result:

```text
scenes_attempted = GM_RM017;GM_RM019
scenes_completed = GM_RM017;GM_RM019
GM_RM011 = blocked_missing_p4g
object_hypotheses_input_count = 27
object_frame_state_input_rows = 980
object_readiness_gating_rows = 27
alignment_frame_map_rows = 681
alignment_window_candidate_rows = 18
alignment_mode = frame_ratio_hypothesis only
```

Per-scene status:

| scene | OTY2-P0 input status | object hypotheses | object-frame states | frame-map rows | temporal window candidates | blocker / uncertainty |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| GM_RM017 | `ready_with_uncertainty` | 6 | 308 | 308 | 6 | missing exact timestamp metadata; using frame-ratio hypothesis audit only |
| GM_RM019 | `ready_with_uncertainty` | 21 | 672 | 373 | 12 | missing exact timestamp metadata; using frame-ratio hypothesis audit only |
| GM_RM011 | `blocked_missing_p4g` | 0 | 0 | 0 | 0 | missing OTY0/OTY1/OTY1a/OTY1t/P4G inputs |

Important interpretation:

- `frame_ratio_hypothesis` is audit-only.
- `optical_frame_num` is not `sar_frame_num`.
- Current OTY2-P0 is not verified timestamp alignment.
- `do_not_enter_sar_band=true` for every temporal window.
- Temporal windows are not SAR localization, not SAR search corridors, not SAR candidate boxes, and not annotation proposals.

The reason OTY2-P0 uses `frame_ratio_hypothesis` is that current scene inventory
has optical and SAR frame counts, but no exact optical/SAR timestamp metadata or
verified anchors. For GM_RM017 and GM_RM019 the frame inventory supports an
audit ratio from 368 optical frames to 766 SAR frames, but that ratio is only a
hypothesis for review and downstream planning.

## Section F: Readiness and Gating

OTY2-P0 does not consume all object hypotheses equally. It gates each object
hypothesis before temporal mapping:

| gate | meaning now | effect on OTY2-P1 / OTY2-P2 / OTY3 |
| --- | --- | --- |
| `use_as_primary_alignment_track` | stable or usable main-track object; primary observations can drive temporal continuity | OTY2-P1 should seek timestamps/anchors for these first; OTY2-P2 may narrow windows if metadata supports it; OTY3 may later use them as primary optical priors after OTY2-P1 is resolved |
| `use_with_uncertainty_expansion` | main trajectory is useful but secondary observations must expand or downgrade confidence | OTY2-P1 must preserve secondary observations; OTY2-P2 should keep expanded windows unless anchors reduce uncertainty; OTY3 must not collapse uncertainty into a single SAR location |
| `low_confidence_window_only` | ambiguous object hypothesis can provide a temporal review window only | OTY2-P1 can audit whether metadata/anchors clarify the time span; OTY3 should not use these as normal primary search-corridor inputs without an explicit review resolution |
| `exclude_from_oty2` | short/noise or do-not-use object hypotheses are blocked before temporal mapping | OTY2-P1 can leave them excluded unless a prior optical-stage blocker is reopened; OTY3 must not use them |
| `blocked_pending_visual_review` | object is not safe for runtime alignment until visual review resolves a blocker | OTY2-P1 should not promote it; OTY3 must wait |

Current gate counts:

```text
use_as_primary_alignment_track = 4
use_with_uncertainty_expansion = 7
low_confidence_window_only = 7
exclude_from_oty2 = 9
blocked_pending_visual_review = 0
```

## Section G: What Is Not Solved Yet

1. Exact optical/SAR timestamp alignment is not solved.
2. GM_RM011 lacks OTY0/OTY1/OTY1a/OTY1t/P4G inputs in the current object-level chain.
3. Current temporal windows are ratio-hypothesis audit windows.
4. SAR spatial search corridor has not started.
5. SAR scattering/evidence model has not started.
6. SAR GT coverage has not started.
7. Annotation proposal has not started.

These are not cosmetic blockers. They define the next safe engineering step.
Skipping them would mix audit windows with SAR spatial search, or treat frame
ratio as timestamp truth.

## Section H: Recommended Next Steps

Next immediate step:

```text
OTY2-P1 temporal metadata and anchor audit
```

Then:

```text
OTY2-P2 temporal window refinement
OTY3-P0 object-level SAR temporal-windowed search corridor audit
OTY4 object-level SAR corridor posthoc GT coverage audit
OTY5 automatic annotation proposal
```

Do not start OTY3 until OTY2-P1 clarifies timestamp / anchor availability.
OTY3 can start only after OTY2 has a defensible temporal alignment policy and
the object-level gates are preserved. OTY4 can start only after OTY3 produces
SAR corridors without GT. OTY5 can start only after OTY4 audits coverage
posthoc and does not back-propagate GT, selector, or tuned thresholds into the
runtime chain.

## Section I: Session Handoff Notes

The next session should first read this recap and the latest reports:

- `docs/oty_yolo_first_optical_temporal_transfer_plan.md`
- `docs/oty2_high_fps_optical_to_sar_alignment_design.md`
- `docs/oty2_object_level_input_contract.md`
- `reports/oty1t/oty1t_object_hypothesis_generalization_summary_20260701_231500.md`
- `reports/oty2/oty2_object_temporal_alignment_summary_20260702_124551.md`
- `reports/oty2/samples/oty2_scene_input_status_sample.csv`
- `reports/oty2/samples/oty2_object_alignment_uncertainty_report.md`

Then continue with OTY2-P1 temporal metadata / anchor audit. It should not
re-open tracking design unless a specific blocker points back to OTY1t. It
should not begin OTY3, SAR band generation, SAR search corridors, SAR GT
coverage, SAR evidence sampling, selector/ranking, threshold tuning, training,
or annotation proposal work.
