# OTY2 OTY1t Standard MOT Backbone Closure

Timestamp: `20260705_110947`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `16074d0 Probe sliding-window local continuity`

## Boundary

This pass closes the existing OTY1t standard MOT route as the primary temporal-backbone candidate to evaluate next. It does not introduce a sliding-window graph, component stacking, runtime tracker replacement, detector replacement, threshold tuning, SAR pairing, support audit, final annotation, revised GT, final box, selector/ranking, weighted fusion, identity truth, or clean `215` promotion.

All tracker replay artifacts were written under ignored `outputs/`. Only this Markdown report, a small summary CSV, and the diagnostic wrapper extension are intended for commit.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `src/optical_state/tracker_audit.py`
- `tools/diagnostics/run_oty1t_tracker_audit.py`
- `tools/diagnostics/run_oty1t_tracker_audit_from_normalized_oty0.py`
- `reports/oty2/oty2_normalized_input_tracker_sensitivity_probe_20260705_093617.md`
- `reports/oty2/oty2_observation_component_grouping_dryrun_20260705_101430.md`
- `reports/oty2/oty2_sliding_window_local_continuity_probe_20260705_104945.md`

## Adapter Closure

The repository already has standard MOT replay adapters:

- `src/optical_state/tracker_audit.py` has `run_bytetrack_detection_table_replay(...)`.
- `src/optical_state/tracker_audit.py` has `run_botsort_detection_table_replay(...)`.
- `tools/diagnostics/run_oty1t_tracker_audit.py` routes `--tracker bytetrack|botsort` through those adapters.

Both ByteTrack and BoT-SORT were available in the current environment and ran on `GM_RM011`, `GM_RM019`, and `GM_RM017`.

Current BoT-SORT is not ReID-enabled. The adapter sets:

```text
with_reid=False
```

Both ByteTrack and BoT-SORT replay detections with:

```text
tracker.update(adapter, img=_blank_image(frame_rows))
```

Therefore the current OTY1t route is a real MOT replay route, but it is still geometry/detection-table driven. It does not provide real optical appearance to BoT-SORT and should not be treated as a ReID-capable result.

## Wrapper Change

The existing normalized-input wrapper was extended to support:

```text
--tracker bytetrack|botsort
```

This was necessary only to run normalized active-only BoT-SORT in the same isolated wrapper used for the prior ByteTrack normalized probe. It does not modify OTY0, OTY1, OTY1a, OTY1t runtime helpers, tracker parameters, manifests, or configs.

## Commands

The 12 closure runs used the same wrapper and default tracker settings:

```powershell
$ts='20260705_110947'
$root="outputs\oty1t_standard_mot_backbone_closure_$ts"

# For each scene in GM_RM011, GM_RM019, GM_RM017:
#   tracker: bytetrack, botsort
#   input: raw OTY0, normalized active-only OTY0
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene <scene> --detector-label yolo11l_baseline --tracker <bytetrack|botsort> --input-variant <raw|normalized_active> --input-detection-table <table> --output-dir <ignored-output-dir> --timestamp 20260705_110947 [--active-only]
```

Ignored output root:

```text
outputs/oty1t_standard_mot_backbone_closure_20260705_110947/
```

Committed small summary:

```text
reports/oty2/samples/oty2_oty1t_standard_mot_backbone_summary_20260705_110947.csv
```

## Summary Table

| Scene | Tracker | Input | Rows | Tracked | Unmatched | Rate | Tracks | Stable | Frag | Amb | Short | Dup hyp | Dup event | Switch | Lost | React | Mean len | Median len | Longest span |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | ByteTrack | raw | 422 | 331 | 91 | 0.215640 | 28 | 11 | 5 | 5 | 2 | 5 | 4 | 5 | 39 | 11 | 11.821 | 5.5 | 45 |
| `GM_RM011` | ByteTrack | normalized | 413 | 327 | 86 | 0.208232 | 25 | 10 | 8 | 5 | 2 | 0 | 0 | 4 | 38 | 13 | 13.080 | 8 | 45 |
| `GM_RM011` | BoT-SORT | raw | 422 | 347 | 75 | 0.177725 | 20 | 7 | 8 | 0 | 3 | 2 | 4 | 1 | 33 | 13 | 17.350 | 18.5 | 47 |
| `GM_RM011` | BoT-SORT | normalized | 413 | 344 | 69 | 0.167070 | 17 | 8 | 9 | 0 | 0 | 0 | 0 | 0 | 29 | 12 | 20.235 | 22 | 47 |
| `GM_RM019` | ByteTrack | raw | 334 | 207 | 127 | 0.380240 | 21 | 3 | 1 | 0 | 9 | 8 | 8 | 6 | 29 | 8 | 9.857 | 3 | 43 |
| `GM_RM019` | ByteTrack | normalized | 330 | 206 | 124 | 0.375758 | 21 | 3 | 1 | 0 | 10 | 7 | 7 | 6 | 29 | 8 | 9.810 | 3 | 43 |
| `GM_RM019` | BoT-SORT | raw | 334 | 222 | 112 | 0.335329 | 19 | 3 | 2 | 0 | 6 | 8 | 8 | 4 | 28 | 9 | 11.684 | 6 | 44 |
| `GM_RM019` | BoT-SORT | normalized | 330 | 221 | 109 | 0.330303 | 19 | 3 | 2 | 0 | 7 | 7 | 7 | 4 | 28 | 9 | 11.632 | 6 | 44 |
| `GM_RM017` | ByteTrack | raw | 215 | 196 | 19 | 0.088372 | 6 | 4 | 0 | 2 | 0 | 0 | 0 | 1 | 8 | 2 | 32.667 | 42.5 | 49 |
| `GM_RM017` | ByteTrack | normalized | 215 | 196 | 19 | 0.088372 | 6 | 4 | 0 | 2 | 0 | 0 | 0 | 1 | 8 | 2 | 32.667 | 42.5 | 49 |
| `GM_RM017` | BoT-SORT | raw | 215 | 200 | 15 | 0.069767 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 40.000 | 47 | 53 |
| `GM_RM017` | BoT-SORT | normalized | 215 | 200 | 15 | 0.069767 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 40.000 | 47 | 53 |

## Required Answers

1. ByteTrack and BoT-SORT real adapters are available.

Both trackers ran successfully through detection-table replay. BoT-SORT is not unavailable.

2. BoT-SORT ran on all three scenes.

It ran on `GM_RM011`, `GM_RM019`, and `GM_RM017`, for both raw and normalized active-only inputs.

3. BoT-SORT is currently not running with ReID.

The current adapter sets `with_reid=False`.

4. The replay does not provide real image appearance.

Both tracker adapters pass `_blank_image(frame_rows)` into `tracker.update(...)`. That means BoT-SORT is not consuming optical frame appearance features in this route.

5. Best GM_RM011 continuity candidate:

`BoT-SORT normalized active-only` gives the strongest diagnostic continuity on simple MOT metrics: lowest unmatched rate (`0.167070`), fewest tracks (`17`), no short tracks, no duplicate-overlap hypotheses/events, no possible ID-switch events, lower lost events (`29`), and the longest mean/median track length (`20.235` / `22`). It is still not a clean solution because fragmented hypotheses increase to `9` and the input uses active-only suppression that previously showed continuity side effects.

6. BoT-SORT vs ByteTrack:

BoT-SORT reduces unmatched detections and track count in all three scenes. It improves duplicate-overlap and possible ID-switch signals on `GM_RM011`, and gives the cleanest `GM_RM017` control. It does not uniformly reduce fragmentation: `GM_RM011` raw fragmentation is `8` vs ByteTrack raw `5`, and `GM_RM019` raw fragmentation is `2` vs ByteTrack raw `1`. Reactivated events are also not uniformly better.

7. Normalized active-only effect:

For ByteTrack, normalized input reduces unmatched and duplicate-overlap pressure on `GM_RM011`, but increases fragmentation and reactivation. `GM_RM019` improves only marginally and short tracks worsen. `GM_RM017` is unchanged.

For BoT-SORT, normalized input improves `GM_RM011` unmatched, track count, duplicate-overlap, short-track, switch, and lost metrics, but fragmentation remains high. `GM_RM019` improves only slightly and short tracks worsen. `GM_RM017` is unchanged because no rows were suppressed.

8. Is standard MOT enough without ReID?

No. Standard MOT is the correct main temporal backbone candidate, but the current route is geometry-only / blank-image / no-ReID. It improves over endpoint-only fragment reasoning, yet it cannot close crowded-scene re-identification, partial/full transition, and dirty-detection cases.

9. Exact ReID/stitching input needed next:

- OTY1t tracklets from BoT-SORT and ByteTrack, especially endpoint rows, lost/reactivated events, and short/fragmented tracks.
- Raw OTY0 detections with `optical_path`, bbox, class, and confidence.
- Actual optical frame crops for each tracklet endpoint and representative midpoints.
- OTY0 component grouping fields: `observation_component_id`, `component_role`, `component_conflict_family`, `tracking_policy`, `fragment_context_policy`, `suppression_risk`, and `temporal_review_needed`.
- Normalized active/suppressed row context, but not as a replacement for raw observations.
- Sliding-window local continuity certificates/probable windows as local temporal evidence.
- Candidate stitch edges with temporal gap, motion, bbox size/aspect, bottom-y, class, component blockers, appearance similarity, and explicit `not_identity_truth` policy.

The next probe should output ReID-aware stitch candidates, not merged object identities.

10. Component grouping and sliding-window use after MOT:

They should be post-MOT explainers and blockers. Component grouping explains dirty detections, duplicate/partial/neighbor context, and suppression risk. Sliding-window continuity explains local same-target plausibility inside bounded windows. Neither should replace the MOT backbone or become the main tracker.

## Failure Attribution

The current failure is not `BoT-SORT unavailable` and not simply `detector blocked`.

The evidence points to a mixed mechanism:

- no ReID / no real appearance prevents BoT-SORT from doing appearance-assisted recovery;
- dirty detections and duplicate/partial boxes remain visible because normalized active-only can remove duplicate pressure but can also increase fragmentation;
- tracker geometry alone improves continuity, but still cannot resolve crowded multi-target ambiguity and partial/full transitions safely.

Therefore the next mechanism should keep OTY1t standard MOT as the backbone and add a ReID-aware stitching probe around tracklet endpoints and blocked events.

## Conclusion

```text
OTY1T_STANDARD_MOT_PARTIAL_NEEDS_REID_STITCHING
```

Recommended next step:

```text
Design a ReID-aware tracklet stitching probe over OTY1t BoT-SORT/ByteTrack hypotheses using real optical crops, component blockers, and sliding-window local continuity as post-MOT evidence. Do not merge identities or replace the mainline tracker.
```

## Explicit Non-Actions

- No OTY0 runtime was changed.
- No OTY1/OTY1a/OTY1t runtime helper was changed.
- No mainline tracker was replaced.
- No tracker parameters were tuned.
- No detector was replaced.
- No SAR pairing was run.
- No support audit was run.
- No final annotation was generated.
- No revised GT was generated.
- No final box was generated.
- No selector/ranking output was generated.
- No weighted fusion was used.
- No identity truth was claimed.
- `GM_RM011` was not promoted into the clean `215` pool.
