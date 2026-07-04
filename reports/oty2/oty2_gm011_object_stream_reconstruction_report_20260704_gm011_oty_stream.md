# OTY2 GM_RM011 Object-Stream Reconstruction Report

Timestamp: `20260704_gm011_oty_stream`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Start HEAD: `5b90760`

## Boundary

This run stays inside OTY2 posthoc mechanism diagnosis, Lane B: GM_RM011 optical object-stream recovery and pairing-failure diagnosis.

Runtime construction used only GM_RM011 optical frames and optical detector/tracker outputs. SAR raw/gray frame inventories remain reference-only. No SAR GT, SAR image observation, GT-local fields, final/manual/oracle/review labels, final boxes, revised GT, selector/ranking logic, threshold tuning, weighted fusion, or identity-truth claim entered runtime construction.

GM_RM011 is not merged into the clean paired `215` pool. The recovered output is an optical object stream pending later posthoc pairing diagnosis.

## Commands Run

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_yolo_detection_stream_audit.py --scene GM_RM011 --frame-range-start 0 --frame-range-end 367 --timestamp 20260704_gm011_oty_stream
```

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1_optical_tracklet_audit.py --scene GM_RM011 --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv --no-run-oty0-if-missing --timestamp 20260704_gm011_oty_stream
```

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1a_fragment_merge_audit.py --scene GM_RM011 --oty1-output-dir outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream --timestamp 20260704_gm011_oty_stream
```

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit.py --scene GM_RM011 --tracker bytetrack --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv --oty1-output-dir outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream --oty1a-output-dir outputs\oty1a_fragment_merge_audit_20260704_gm011_oty_stream --no-run-oty0-if-missing --timestamp 20260704_gm011_oty_stream
```

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_object_hypothesis_generalization_audit.py --scene GM_RM011 --tracker bytetrack --timestamp 20260704_gm011_oty_stream
```

Only GM_RM011 was requested in each runner.

## Stage Results

| Stage | Status | Blocker taxonomy |
| --- | --- | --- |
| Stage 1: OTY0 detection | PASS | none |
| Stage 2: OTY1 optical tracklet stream | PASS_WITH_UNCERTAINTY | none |
| Stage 3a: OTY1a fragment-merge candidates | PASS_WITH_UNCERTAINTY | none |
| Stage 3b: OTY1t ByteTrack replay | PASS_WITH_UNCERTAINTY | none |
| Stage 3c: P4G object hypotheses | PASS_WITH_UNCERTAINTY | none |

No stage stopped with `DETECTOR_BLOCKED`, `TRACKER_BLOCKED`, `CONVENTION_BLOCKED`, `SCHEMA_BLOCKED`, or `UNRESOLVED`.

## OTY0 Detection Summary

Output directory: `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream`

| Diagnostic | Result |
| --- | --- |
| Processed frame inventory | `368` rows, optical frames `0-367` |
| Inventory filename continuity | PASS, no missing frame ids and no filename mismatch |
| Detection rows | `422` GM_RM011 rows |
| Frames with detections | `233` |
| Per-frame detection count distribution | `0=135; 1=86; 2=107; 3=38; 4=2` |
| Class distribution | `car=413; truck=9` |
| Confidence distribution | min `0.250541`; p25 `0.466035`; median `0.826515`; p75 `0.926495`; max `0.971165` |
| Bbox coordinate sanity | PASS, no rows outside 800x600 image bounds and no non-positive width/height |
| Scene sanity | PASS, all detection rows are `GM_RM011` |
| Downstream schema | PASS, header matches OTY1 expected detection-table fields |

OTY0 generated a usable GM_RM011 optical detection table. No SAR/GT/runtime boundary blocker was reported.

## OTY1 Tracklet Summary

Output directory: `outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream`

| Diagnostic | Result |
| --- | --- |
| Input detections | `422` |
| Tracklet candidate components | `45` |
| Object/state rows | `422` OTY1 state rows |
| Candidate edges | `2003` total, `1596` within audit limits |
| Frame coverage | state rows cover optical frames `0-352`, `233` unique frames |
| Track length distribution | `1=11; 2=6; 3=3; 4=5; 5=3; 6=1; 11=3; 13=2; 14=2; 17=1; 19=2; 24=1; 28=1; 35=1; 37=1; 41=1; 42=1` |
| Tracklet status distribution | `ambiguous_geometry_review=28; fragmented_short_track=17` |
| Identity status distribution | `ambiguous_crossing_risk=28; fragmented_short_track=17` |
| ID convention | PASS, `oty1_tracklet_####` ids only |
| Duplicate tracklet-frame rows | `0` |
| Downstream required files | PASS |

OTY1 is structurally compatible with downstream stages, but it is not a clean identity result. All OTY1 candidates are either ambiguous geometry review or short fragments.

## OTY1a Fragment-Merge Summary

Output directory: `outputs\oty1a_fragment_merge_audit_20260704_gm011_oty_stream`

| Diagnostic | Result |
| --- | --- |
| Component review rows | `45` |
| Merge candidate edge rows | `179` |
| Shape-transition audit rows | `162` |
| Review candidate edges including ambiguous | `40` |
| Nonambiguous merge review candidates | `27` |
| Ambiguous competing merge candidates | `13` |
| Confirmed identity merges | `0` |
| Merge status distribution | `ambiguous_competing_merge=13; needs_visual_review=1; overlap_shape_transition_candidate=1; partial_to_full_box_transition_candidate=25; reject_class_mismatch=19; reject_gap_too_large=69; reject_motion_inconsistent=44; reject_size_aspect_inconsistent=7` |

OTY1a produced review-only optical geometry candidates. It did not confirm identity and did not enter SAR/GT evaluation.

## OTY1t ByteTrack Summary

Output directory: `outputs\oty1t_tracker_audit_bytetrack_20260704_gm011_oty_stream`

| Diagnostic | Result |
| --- | --- |
| Detection rows in | `422` |
| Tracker real run | `true` |
| Dependency status | `available` |
| Tracker tracks | `28` |
| Tracked state rows | `331` |
| Unmatched detections | `91` |
| Events | `125` |
| Stable hypotheses | `11` |
| Fragmented hypotheses | `5` |
| Ambiguous hypotheses | `5` |
| Short hypotheses | `2` |
| Duplicate-overlap hypotheses | `5` |
| Possible ID-switch count | `5` |
| Track status distribution | `duplicate_overlap_review=5; fragmented_tracker_hypothesis=5; possible_id_switch_review=5; short_tracker_hypothesis=2; tracker_stable_hypothesis=11` |
| Tracker state frame coverage | optical frames `0-315`, `201` unique frames |
| Track length summary | min `1`; median `5`; max `40` |
| Scene/schema sanity | PASS, all track/state rows are GM_RM011 |

OTY1t recovered tracker hypotheses but kept them as optical hypotheses only. Tracker ids are not identity truth.

## P4G Object-Hypothesis Summary

Output directory: `outputs\oty1t_object_hypothesis_generalization_audit_20260704_gm011_oty_stream`

| Diagnostic | Result |
| --- | --- |
| Scenes completed | `GM_RM011` |
| Object hypothesis rows | `28` |
| Object-frame state rows | `800` |
| Orphan observations | `35` |
| Stable object hypotheses | `5` |
| Main-track with secondary observations | `15` |
| Ambiguous object hypotheses | `6` |
| Short/noise track hypotheses | `2` |
| Same-object support | `strong=8; moderate=14; weak=6` |
| Review required | `23` of `28` objects |
| Recommended use distribution | `do_not_use_for_oty2=2; main_track_only=4; main_track_with_uncertainty_handoff=15; optional_continuity_hint_with_visual_review=6; tracklet_stitching_review_before_oty2=1` |
| Object-frame coverage | optical frames `0-316`, `240` unique frames |
| Object id convention | PASS, `oty1t_obj_GM_RM011_bytetrack_bt_####` ids only |
| Duplicate object-frame rows | `0` |
| Required object/frame fields | PASS |
| Explicit SAR/GT/IoU/final/manual/oracle/selector/ranking fields | none in P4G object/frame schemas |
| SAR frame mapping fields | none produced |

P4G is the recovered GM_RM011 optical object-stream layer for later OTY2 posthoc pairing diagnosis. It is ready with uncertainty, not clean paired validation.

## Generated Runtime Artifacts

Generated runtime artifacts were kept under ignored `outputs/` directories and should not be committed:

- `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream`
- `outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream`
- `outputs\oty1a_fragment_merge_audit_20260704_gm011_oty_stream`
- `outputs\oty1t_tracker_audit_bytetrack_20260704_gm011_oty_stream`
- `outputs\oty1t_object_hypothesis_generalization_audit_20260704_gm011_oty_stream`

The runners also produced temporary side reports/samples under `reports\oty1`, `reports\oty1a`, and `reports\oty1t`; those byproducts were removed or restored before this OTY2 report was prepared so that only this report is intended for commit.

Workspace logs written by the runners:

- `D:\profile\research\workspace\logs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream.md`
- `D:\profile\research\workspace\logs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream.md`

## Recommendation

Recommendation: `GM011_OBJECT_STREAM_RECOVERED_PENDING_POSTHOC_PAIRING_DIAGNOSIS`

Minimal next step:

Use the recovered P4G object hypotheses only as uncertain optical object-stream inputs for GM_RM011 posthoc pairing-failure diagnosis. The next diagnostic should check optical-to-SAR time mapping / pairing compatibility without final IoU scoring, selector/ranking, revised GT, threshold tuning, weighted fusion, or clean-pool promotion.
