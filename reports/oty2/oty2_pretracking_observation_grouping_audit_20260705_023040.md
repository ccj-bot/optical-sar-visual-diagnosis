# OTY2 OTY0-Post Pre-Tracking Observation Grouping Audit

Timestamp: `20260705_023040`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `e8d8dbf Run YOLO26l detector quality probe`

## Boundary

This pass implements and runs an OTY0-post, OTY1/ByteTrack-pretracking diagnostic only:

```text
tools/diagnostics/run_oty0_pretracking_observation_grouping_audit.py
```

The script preserves raw OTY0 detections. It emits same-frame conflict labels and optical state tags as review-safe context only. It does not merge boxes, delete boxes, output final boxes, run OTY1/OTY1a/OTY1t/P4G, run tracker-side probes, replace the detector, tune thresholds, use weighted fusion, enter SAR pairing/support audit, create final annotations, create revised GT, create selector/ranking output, promote GM_RM011 into clean 215, or declare identity truth.

`safe_for_auto_grouping` is `false` for every candidate pair.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_yolo26l_detector_quality_probe_20260704_231830.md`
- `reports/oty2/oty2_same_frame_multibox_and_state_tagging_audit_20260704_214019.md`
- `reports/oty2/oty2_optical_stream_tracking_insertion_point_audit_20260704_215625.md`

## Inputs

YOLO11l baseline OTY0 tables:

| Scene | Table |
| --- | --- |
| `GM_RM011` | `outputs/oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream/oty0_yolo_detection_table.csv` |
| `GM_RM019` | `outputs/oty0_yolo_detection_stream_audit_20260701_170751/oty0_yolo_detection_table.csv` |
| `GM_RM017` | `outputs/oty0_yolo_detection_stream_audit_20260701_181317/oty0_yolo_detection_table.csv` |

YOLO26l probe OTY0 tables:

| Scene | Table |
| --- | --- |
| `GM_RM011` | `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv` |
| `GM_RM019` | `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm019/oty0_yolo_detection_table.csv` |
| `GM_RM017` | `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv` |

Full diagnostic outputs, not committed:

```text
outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/
```

Committed small summary:

```text
reports/oty2/samples/oty2_pretracking_observation_grouping_summary_20260705_023040.csv
```

## Commands Run

Equivalent command pattern:

```powershell
D:\MINICONDA\envs\py311\python.exe tools/diagnostics/run_oty0_pretracking_observation_grouping_audit.py `
  --input-detection-table <oty0_detection_table.csv> `
  --scene <GM_RM011|GM_RM019|GM_RM017> `
  --detector-label <yolo11l_baseline|yolo26l_probe> `
  --output-dir outputs/oty0_pretracking_observation_grouping_audit_20260705_023040 `
  --timestamp 20260705_023040
```

The command was run once for each of the six input tables listed above.

## Output Schema

Pair-level outputs include:

- `scene`, `detector_label`, `optical_frame_num`;
- `detection_id_a`, `detection_id_b`;
- `class_a`, `class_b`, `confidence_a`, `confidence_b`;
- `overlap_proxy`, `center_distance`, `area_ratio`, `frame_detection_count`;
- `boundary_touch_proxy`, `size_relation`, `class_relation`;
- `grouping_diagnosis_label`, `state_tags`;
- `safe_for_auto_grouping`;
- `why_not_identity_truth`;
- `recommended_downstream_use`.

Frame-level outputs include detection counts, same-frame pair counts, candidate pair counts, high-overlap counts, class-conflict counts, neighbor/crowding counts, unresolved counts, and frame state tags.

Scene-level outputs include total detections, frames with detections, same-frame pairs, candidate multi-box pairs, high-overlap pairs, class-instability duplicate-like pairs, partial/full pairs, neighbor/crowding pairs, unjudgeable pairs, safe automatic grouping counts, and review-required counts.

## Cross-Scene Summary

| Scene | Detector | Rows | Frames with det. | Same-frame pairs | Candidate pairs | High-overlap | Class-instability | Partial/full | Neighbor/crowding | Unjudgeable | Safe auto grouping |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | YOLO11l | 422 | 233 | 233 | 97 | 54 | 9 | 44 | 11 | 20 | 0 |
| `GM_RM011` | YOLO26l | 413 | 243 | 209 | 92 | 61 | 19 | 28 | 8 | 15 | 0 |
| `GM_RM019` | YOLO11l | 334 | 193 | 196 | 146 | 29 | 2 | 34 | 89 | 14 | 0 |
| `GM_RM019` | YOLO26l | 288 | 193 | 124 | 93 | 28 | 1 | 8 | 50 | 12 | 0 |
| `GM_RM017` | YOLO11l | 215 | 100 | 167 | 75 | 9 | 3 | 14 | 34 | 24 | 0 |
| `GM_RM017` | YOLO26l | 215 | 104 | 171 | 82 | 11 | 0 | 14 | 40 | 24 | 0 |

## Label Distribution

| Scene | Detector | Duplicate-like | Class-instability duplicate-like | Partial/full | Neighbor competition | Crowding unresolved | Unjudgeable |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | YOLO11l | 13 | 9 | 44 | 0 | 11 | 20 |
| `GM_RM011` | YOLO26l | 22 | 19 | 28 | 0 | 8 | 15 |
| `GM_RM019` | YOLO11l | 7 | 2 | 34 | 30 | 59 | 14 |
| `GM_RM019` | YOLO26l | 22 | 1 | 8 | 18 | 32 | 12 |
| `GM_RM017` | YOLO11l | 0 | 3 | 14 | 5 | 29 | 24 |
| `GM_RM017` | YOLO26l | 4 | 0 | 14 | 7 | 33 | 24 |

## Required Answers

1. Which conflicts are detector-independent?

High-overlap, partial/full, and multi-object competition signals remain under both YOLO11l and YOLO26l. All three scenes have candidate pairs under both detectors. GM_RM011 and GM_RM019 also keep class-instability duplicate-like pairs under both detectors. GM_RM017 is milder, but it still has high-overlap, partial/full, neighbor/crowding, and unjudgeable pairs under both detectors.

2. Which conflicts are detector-specific?

YOLO26l changes the distribution rather than removing the problem. On GM_RM011, YOLO26l increases high-overlap pairs from `54` to `61` and class-instability duplicate-like pairs from `9` to `19`, even though total candidate pairs drop from `97` to `92`. On GM_RM019, YOLO26l clearly reduces candidate pairs from `146` to `93`, partial/full pairs from `34` to `8`, and neighbor/crowding pairs from `89` to `50`. On GM_RM017, YOLO26l removes class-instability duplicate-like pairs from `3` to `0`, but candidate pairs rise from `75` to `82`.

3. Does YOLO26l reduce or worsen grouping burden per scene?

- `GM_RM011`: mixed and still unsafe. Overall candidate count drops slightly, but the most dangerous pretracking signals, high-overlap and class-instability duplicate-like pairs, worsen.
- `GM_RM019`: improves substantially, but not to clean. Candidate, partial/full, and crowding burden drop, while high-overlap remains almost unchanged.
- `GM_RM017`: remains the simpler comparator, but YOLO26l does not remove grouping burden and slightly increases candidate/high-overlap counts.

4. Does GM_RM011 still require observation grouping before tracker?

Yes. GM_RM011 still has `92` YOLO26l candidate pairs, `61` high-overlap pairs, and `19` class-instability duplicate-like pairs. Passing those rows directly into tracking would still expose ByteTrack/OTY1 to duplicate-overlap, class instability, partial/full competition, boundary-sensitive observations, and unresolved crowding.

5. Does GM_RM019 become cleaner enough for a bounded tracker-side probe?

Yes, as a bounded diagnostic only. YOLO26l reduces GM_RM019 candidate burden from `146` to `93`, and the cleaner input is useful for a later tracker-side sensitivity probe. It is not clean enough to skip observation grouping, because `93` candidate pairs, `28` high-overlap pairs, and `50` neighbor/crowding pairs remain.

6. Are any pairs safe for automatic grouping?

No. `safe_auto_grouping_count` is `0` for all six runs. Same-frame bbox geometry can identify duplicate-like, partial/full, and competition contexts, but it cannot prove identity. Class conflict, neighbor competition, boundary contact, and partial/full state make automatic grouping unsafe without later temporal and cross-scene mechanism evidence.

7. What should be passed downstream into OTY1/OTY1a later as context?

Pass the original OTY0 detection rows unchanged, plus review-safe context keyed by `scene`, `optical_frame_num`, and detection-id pairs:

- `grouping_diagnosis_label`;
- `state_tags`;
- `overlap_proxy`;
- `center_distance`;
- `area_ratio`;
- `class_relation`;
- `boundary_touch_proxy`;
- `safe_for_auto_grouping=false`;
- `recommended_downstream_use`.

This context can explain why a future OTY1 edge, OTY1a fragment relation, or tracker event is strong, weak, ambiguous, or blocked. It must not be used as identity truth or as a box merge instruction.

8. Should the next step be tracker-side probe or connecting grouping context to OTY1a fragment relation audit?

Priority: connect the grouping context to an OTY1/OTY1a fragment relation audit path first. GM_RM019 is now clean enough to justify a later bounded tracker-side sensitivity probe, but GM_RM011 still shows severe pretracking conflict. The safer next mechanism step is to carry these labels as explicit context into fragment relation diagnosis before treating tracker output differences as mechanism improvement.

## Interpretation

The audit supports the previous insertion-point conclusion:

```text
INSERT_AFTER_OTY0_BEFORE_TRACKING
```

YOLO26l is useful as detector contrast but not as a replacement for OTY0-post observation grouping. The dominant issue is still that OTY1/ByteTrack can receive unnormalized same-frame observations: high-overlap duplicates, class-conflict duplicates, partial/full competition, boundary-sensitive observations, and multi-object competition.

## Generated Artifacts

Committed:

- `tools/diagnostics/run_oty0_pretracking_observation_grouping_audit.py`
- `reports/oty2/oty2_pretracking_observation_grouping_audit_20260705_023040.md`
- `reports/oty2/samples/oty2_pretracking_observation_grouping_summary_20260705_023040.csv`

Generated but not committed:

- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM011_yolo11l_baseline_pretracking_grouping_pairs.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM011_yolo11l_baseline_pretracking_frame_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM011_yolo11l_baseline_pretracking_scene_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM011_yolo26l_probe_pretracking_grouping_pairs.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM011_yolo26l_probe_pretracking_frame_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM011_yolo26l_probe_pretracking_scene_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM019_yolo11l_baseline_pretracking_grouping_pairs.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM019_yolo11l_baseline_pretracking_frame_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM019_yolo11l_baseline_pretracking_scene_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM019_yolo26l_probe_pretracking_grouping_pairs.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM019_yolo26l_probe_pretracking_frame_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM019_yolo26l_probe_pretracking_scene_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM017_yolo11l_baseline_pretracking_grouping_pairs.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM017_yolo11l_baseline_pretracking_frame_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM017_yolo11l_baseline_pretracking_scene_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM017_yolo26l_probe_pretracking_grouping_pairs.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM017_yolo26l_probe_pretracking_frame_summary.csv`
- `outputs/oty0_pretracking_observation_grouping_audit_20260705_023040/GM_RM017_yolo26l_probe_pretracking_scene_summary.csv`
- JSON sidecars in the same ignored directory:
  `GM_RM011_yolo11l_baseline_pretracking_grouping_audit.json`,
  `GM_RM011_yolo26l_probe_pretracking_grouping_audit.json`,
  `GM_RM019_yolo11l_baseline_pretracking_grouping_audit.json`,
  `GM_RM019_yolo26l_probe_pretracking_grouping_audit.json`,
  `GM_RM017_yolo11l_baseline_pretracking_grouping_audit.json`,
  `GM_RM017_yolo26l_probe_pretracking_grouping_audit.json`

## No-Overstep Check

This pass did not:

- modify OTY0, OTY1, OTY1a, OTY1t, P4, or P4G runtime;
- replace the main detector;
- edit main config or manifest files;
- run tracker-side probes;
- enter SAR pairing;
- enter support audit;
- create final annotations;
- create revised GT;
- create final boxes;
- create selector/ranking output;
- use weighted fusion;
- tune thresholds;
- submit outputs runtime artifacts;
- submit detector weights or large binaries;
- claim tracker ID, P4 ID, or P4G object ID as identity truth.
