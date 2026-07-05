# OTY2 Sliding-Window Local Continuity Probe

Timestamp: `20260705_104945`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `25fa130 Add observation component grouping dry run`

## Boundary

This pass implements a bounded sliding-window local optical continuity feasibility probe. It does not modify OTY0, OTY1, OTY1a, OTY1t, ByteTrack, detector weights, tracker parameters, runtime configs, or manifests.

It does not run SAR pairing, run support audit, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, tune thresholds, declare identity truth, create a clean object stream, or promote `GM_RM011` into the clean `215` pool.

The output is window-level local continuity evidence only. OTY1 tracklet ids and OTY1t tracker ids are treated as optical hypotheses and optional context, not identity truth.

## Inputs

| Scene | OTY0 detections | Component row context | OTY1 state rows | OTY1t assignment context |
| --- | --- | --- | --- | --- |
| `GM_RM011` | `outputs/oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream/oty0_yolo_detection_table.csv` | `outputs/oty0_observation_component_grouping_dryrun_20260705_101430/GM_RM011_yolo11l_baseline_observation_component_rows.csv` | `outputs/oty1_optical_tracklet_audit_20260704_gm011_oty_stream/oty1_optical_tracklet_state_timeseries.csv` | `outputs/oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617/GM_RM011_yolo11l_baseline_raw/oty1t_tracker_detection_assignments.csv` |
| `GM_RM019` | `outputs/oty0_yolo_detection_stream_audit_20260701_170751/oty0_yolo_detection_table.csv` | `outputs/oty0_observation_component_grouping_dryrun_20260705_101430/GM_RM019_yolo11l_baseline_observation_component_rows.csv` | `outputs/oty1_optical_tracklet_audit_20260701_175422/oty1_optical_tracklet_state_timeseries.csv` | `outputs/oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617/GM_RM019_yolo11l_baseline_raw/oty1t_tracker_detection_assignments.csv` |
| `GM_RM017` | `outputs/oty0_yolo_detection_stream_audit_20260701_181317/oty0_yolo_detection_table.csv` | `outputs/oty0_observation_component_grouping_dryrun_20260705_101430/GM_RM017_yolo11l_baseline_observation_component_rows.csv` | `outputs/oty1_optical_tracklet_audit_20260701_181347/oty1_optical_tracklet_state_timeseries.csv` | `outputs/oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617/GM_RM017_yolo11l_baseline_raw/oty1t_tracker_detection_assignments.csv` |

The window inventory is defined over the optical frame range covered by each OTY0 detection table, with empty detection frames counted as gaps inside that range.

## Script

New diagnostic script:

```text
tools/diagnostics/run_oty2_sliding_window_local_continuity_probe.py
```

The script builds window lengths `8`, `12`, and `16` frames with strides `4`, `6`, and `8`. Candidate local paths are OTY1 tracklet local slices when OTY1 state rows are available; OTY1t tracker ids are carried only as optional context. Component grouping context supplies duplicate pressure, continuity-useful duplicate context, partial/full review, neighbor competition, and unresolved review fields.

Certification requires sufficient window coverage, short gaps only, smooth motion, no strong neighbor/multi-object competition, no unresolved review blocker, no equally plausible competing path, and class mismatch explained by duplicate/component context if present.

## Commands

```powershell
$ts='20260705_104945'
$out="outputs\oty2_sliding_window_local_continuity_probe_$ts"

D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_sliding_window_local_continuity_probe.py --scene GM_RM011 --detector-label yolo11l_baseline --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv --component-row-table outputs\oty0_observation_component_grouping_dryrun_20260705_101430\GM_RM011_yolo11l_baseline_observation_component_rows.csv --oty1-state-table outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream\oty1_optical_tracklet_state_timeseries.csv --tracker-assignment-table outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM011_yolo11l_baseline_raw\oty1t_tracker_detection_assignments.csv --output-dir $out --timestamp $ts

D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_sliding_window_local_continuity_probe.py --scene GM_RM019 --detector-label yolo11l_baseline --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv --component-row-table outputs\oty0_observation_component_grouping_dryrun_20260705_101430\GM_RM019_yolo11l_baseline_observation_component_rows.csv --oty1-state-table outputs\oty1_optical_tracklet_audit_20260701_175422\oty1_optical_tracklet_state_timeseries.csv --tracker-assignment-table outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM019_yolo11l_baseline_raw\oty1t_tracker_detection_assignments.csv --output-dir $out --timestamp $ts

D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_sliding_window_local_continuity_probe.py --scene GM_RM017 --detector-label yolo11l_baseline --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv --component-row-table outputs\oty0_observation_component_grouping_dryrun_20260705_101430\GM_RM017_yolo11l_baseline_observation_component_rows.csv --oty1-state-table outputs\oty1_optical_tracklet_audit_20260701_181347\oty1_optical_tracklet_state_timeseries.csv --tracker-assignment-table outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM017_yolo11l_baseline_raw\oty1t_tracker_detection_assignments.csv --output-dir $out --timestamp $ts
```

## Generated Probe Artifacts

Ignored output root:

```text
outputs/oty2_sliding_window_local_continuity_probe_20260705_104945/
```

Per scene and window length, the script writes:

- `<scene>_yolo11l_baseline_w<length>_sliding_window_local_continuity_windows.csv`
- `<scene>_yolo11l_baseline_w<length>_sliding_window_local_paths.csv`
- `<scene>_yolo11l_baseline_sliding_window_local_continuity_scene_summary.csv`
- `<scene>_yolo11l_baseline_sliding_window_local_continuity_probe.json`

Committed small summary:

```text
reports/oty2/samples/oty2_sliding_window_local_continuity_summary_20260705_104945.csv
```

## Window Distribution

| Scene | Total windows | Path-eligible windows | Certified | Probable | Ambiguous competition | Neighbor blocked | Partial/full blocked | Gap/motion blocked | Review required | Certified+probable / all | Certified+probable / eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 187 | 150 | 19 | 41 | 17 | 17 | 29 | 52 | 12 | 32.1% | 40.0% |
| `GM_RM019` | 189 | 107 | 23 | 10 | 28 | 19 | 13 | 87 | 9 | 17.5% | 30.8% |
| `GM_RM017` | 131 | 55 | 11 | 5 | 6 | 16 | 0 | 79 | 14 | 12.2% | 29.1% |

## Per-Window-Length Summary

| Scene | Window | Stride | Windows | Eligible | Certified | Probable | Ambiguous | Neighbor blocked | Partial/full blocked | Gap/motion blocked | Review | Median best coverage | Median score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 8 | 4 | 87 | 66 | 13 | 21 | 4 | 10 | 9 | 25 | 5 | 0.8125 | 0.741445 |
| `GM_RM011` | 12 | 6 | 57 | 47 | 4 | 12 | 6 | 5 | 10 | 15 | 5 | 0.6250 | 0.692194 |
| `GM_RM011` | 16 | 8 | 43 | 37 | 2 | 8 | 7 | 2 | 10 | 12 | 2 | 0.5625 | 0.667083 |
| `GM_RM019` | 8 | 4 | 88 | 49 | 14 | 6 | 11 | 9 | 2 | 41 | 5 | 0.8750 | 0.718282 |
| `GM_RM019` | 12 | 6 | 58 | 33 | 7 | 3 | 10 | 5 | 4 | 26 | 3 | 0.7500 | 0.648148 |
| `GM_RM019` | 16 | 8 | 43 | 25 | 2 | 1 | 7 | 5 | 7 | 20 | 1 | 0.4375 | 0.641482 |
| `GM_RM017` | 8 | 4 | 61 | 25 | 6 | 2 | 3 | 7 | 0 | 37 | 6 | 1.0000 | 0.810974 |
| `GM_RM017` | 12 | 6 | 40 | 17 | 3 | 2 | 2 | 5 | 0 | 24 | 4 | 1.0000 | 0.792826 |
| `GM_RM017` | 16 | 8 | 30 | 13 | 2 | 1 | 1 | 4 | 0 | 18 | 4 | 1.0000 | 0.772079 |

## Overlap-Window Chain Check

Certified+probable windows form short overlapping chains, but not clean identity streams:

| Scene | W8 max chain | W8 approx frames | W12 max chain | W12 approx frames | W16 max chain | W16 approx frames |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 8 | 36 | 5 | 36 | 3 | 32 |
| `GM_RM019` | 7 | 32 | 4 | 30 | 1 | 16 |
| `GM_RM017` | 5 | 24 | 3 | 24 | 2 | 24 |

This supports the feasibility of overlapping local continuity certificates as a longer optical hypothesis substrate. It does not support identity truth or clean object-stream promotion.

## Required Answers

1. Window counts:

`GM_RM011` has `187` windows total (`87` W8, `57` W12, `43` W16). `GM_RM019` has `189` windows (`88`, `58`, `43`). `GM_RM017` has `131` windows (`61`, `40`, `30`).

2. State distribution:

`GM_RM011` has `19` certified and `41` probable windows, but also `17` ambiguous, `17` neighbor-blocked, `29` partial/full-blocked, `52` gap/motion-blocked, and `12` review-required windows. `GM_RM019` has `23` certified and `10` probable, with more competition/gap blocking. `GM_RM017` has fewer total windows and high median best-path coverage inside path-eligible windows, but many full-range windows are gap/motion blocked because detection rows are sparse across the detected frame range.

3. GM_RM011 has enough certified/probable local windows to justify the sliding-window direction, but not enough to call the stream recovered. The certified+probable rate is `32.1%` over all windows and `40.0%` over path-eligible windows.

4. GM_RM011 breakpoints are not only long-range fragment endpoints. Many failures remain inside short windows: gap/motion blocking, partial/full review context, neighbor competition, unresolved review, and ambiguous competing paths all appear before any global identity decision.

5. GM_RM019 is not clearly more suitable than GM_RM011. It has more certified windows in absolute count (`23` vs `19`), but fewer certified+probable windows (`33` vs `60`) and degrades sharply at W16. It remains a same-family risk scene.

6. GM_RM017 verifies that simpler detection-populated windows can produce stable local paths: median best-path coverage is `1.0` at all three window lengths. However, it does not prove mechanism success across the full frame range because sparse detection intervals still create many gap/motion-blocked windows.

7. Component context is useful. Neighbor and unresolved component context almost always blocks certification. Duplicate pressure and continuity-useful duplicate context can coexist with certified/probable windows, especially in `GM_RM011`. Partial/full context is useful as a review-safe state tag: it can explain transitions, but often blocks certification when coverage or gap evidence is insufficient.

8. Overlap windows can form longer local object-stream hypotheses. The strongest `GM_RM011` certified/probable chain spans approximately `36` frames at W8/W12 and `32` frames at W16. These are longer hypotheses, not identity truth.

9. Sliding windows cannot solve windows with missing detection coverage, strong neighbor competition, unresolved component context, partial/full state that lacks stable motion support, class mismatch not explained by component context, or multiple equally plausible local paths.

10. The next mechanism step should be a sliding-window continuity graph rather than continuing endpoint-only fragment merge. The graph should connect certified/probable windows through overlap consistency, preserve ambiguous/blocked windows as blockers, and keep raw observations plus component context available.

## Interpretation

The probe supports the corrected hypothesis: local same-target continuity can sometimes be certified inside bounded windows even when global identity is unsafe. GM_RM011 has enough local positive evidence to justify a window-graph design, but its frequent partial/full and competition blockers show why direct fragment merge or tracker-id consumption remains unsafe.

GM_RM019 confirms that previous apparent passes were not mechanism success. It has local positives, but also substantial competition and gap blocking. GM_RM017 remains the simpler control, but even it should be described as diagnostic availability with local stable windows, not clean identity continuity.

## Conclusion

```text
SLIDING_WINDOW_LOCAL_CONTINUITY_PARTIAL
```

Recommended next step:

```text
Design a sliding-window continuity graph that links overlapping certified/probable local windows, while preserving ambiguous, partial/full, neighbor-competition, gap/motion, and review-required windows as explicit blockers.
```

## Explicit Non-Actions

- No OTY0 runtime was changed.
- No OTY1/OTY1a/OTY1t/ByteTrack runtime was changed.
- No detector or tracker was replaced.
- No tracker parameters or thresholds were tuned.
- No SAR pairing was run.
- No support audit was run.
- No final annotation was generated.
- No revised GT was generated.
- No final box was generated.
- No selector/ranking output was generated.
- No weighted fusion was used.
- No identity truth was claimed.
- `GM_RM011` was not promoted into the clean `215` pool.
