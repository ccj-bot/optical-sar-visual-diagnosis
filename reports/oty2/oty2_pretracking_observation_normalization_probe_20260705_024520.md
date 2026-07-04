# OTY2 Pre-Tracking Observation Normalization Probe

Timestamp: `20260705_024520`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `79ec17e Add OTY0 pretracking observation grouping audit`

## Boundary

This pass implements a controlled shadow/probe optimization at the confirmed insertion point:

```text
INSERT_AFTER_OTY0_BEFORE_TRACKING
```

New script:

```text
tools/diagnostics/run_oty0_pretracking_observation_normalization_probe.py
```

The script reads an existing OTY0 detection table and writes a shadow normalized detection table for later bounded tracker-side diagnostics. It preserves every original OTY0 row and every original bbox. It does not merge boxes, delete boxes, create final boxes, replace the main detector, edit OTY0/OTY1/OTY1a/OTY1t/P4G runtime, run tracker, tune thresholds, enter SAR pairing, enter support audit, create final annotations, create revised GT, create selector/ranking output, or claim identity truth.

`active_for_tracking=false` is a shadow/probe flag only. It is not a final object decision.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_pretracking_observation_grouping_audit_20260705_023040.md`
- `reports/oty2/samples/oty2_pretracking_observation_grouping_summary_20260705_023040.csv`
- `reports/oty2/oty2_optical_stream_tracking_insertion_point_audit_20260704_215625.md`
- `reports/oty2/oty2_yolo26l_detector_quality_probe_20260704_231830.md`

## Inputs

Mainline YOLO11l baseline OTY0 tables:

| Scene | Table |
| --- | --- |
| `GM_RM011` | `outputs/oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream/oty0_yolo_detection_table.csv` |
| `GM_RM019` | `outputs/oty0_yolo_detection_stream_audit_20260701_170751/oty0_yolo_detection_table.csv` |
| `GM_RM017` | `outputs/oty0_yolo_detection_stream_audit_20260701_181317/oty0_yolo_detection_table.csv` |

Additional YOLO26l probe tables were run because they were already present. They are detector-contrast inputs only, not detector replacement:

| Scene | Table |
| --- | --- |
| `GM_RM011` | `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv` |
| `GM_RM019` | `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm019/oty0_yolo_detection_table.csv` |
| `GM_RM017` | `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv` |

## Probe Rule

For same-frame detection pairs, the script computes overlap proxy, center distance, area ratio, class relation, confidence comparison, frame detection count, boundary touch proxy, and size relation through the existing grouping-audit semantics.

Only high-overlap, near-center, similar-size duplicate-like pairs are eligible for shadow suppression:

- overlap proxy at least `0.75`;
- center distance no greater than `120 px`;
- area ratio at least `0.65`;
- primary confidence at least `0.50`.

For eligible pairs, the higher-confidence row remains `active_for_tracking=true`; the lower-confidence row is marked:

```text
active_for_tracking=false
normalization_action=suppress_duplicate_like_for_tracking
suppression_reason=high_overlap_near_center_duplicate_like
safe_for_identity_claim=false
```

If the pair has class conflict, `class_mismatch_explained_by_duplicate_like=true` is recorded as context only.

Partial/full, neighbor/crowding, and unjudgeable pairs are not suppressed.

## Output Schema

For each input table, the probe writes ignored output files:

- `<scene>_<detector>_normalized_detection_table.csv`
- `<scene>_<detector>_normalization_actions.csv`
- `<scene>_<detector>_normalization_scene_summary.csv`
- `<scene>_<detector>_normalization_probe.json`

The normalized detection table contains all original OTY0 columns plus:

- `observation_group_id`
- `active_for_tracking`
- `normalization_action`
- `primary_detection_id`
- `suppression_reason`
- `grouping_diagnosis_label`
- `state_tags`
- `class_mismatch_explained_by_duplicate_like`
- `safe_for_identity_claim`
- `why_not_identity_truth`

All rows have `safe_for_identity_claim=false`.

Full outputs were written under ignored:

```text
outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/
```

Committed small summary:

```text
reports/oty2/samples/oty2_pretracking_observation_normalization_summary_20260705_024520.csv
```

## Mainline YOLO11l Summary

| Scene | Before active | After active | Suppressed duplicate-like rows | Class-instability pairs | Class-mismatch rows explained | Partial/full pairs kept | Neighbor/crowding pairs kept | Unjudgeable pairs kept |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 422 | 413 | 9 | 9 | 16 | 44 | 11 | 20 |
| `GM_RM019` | 334 | 330 | 4 | 2 | 2 | 34 | 89 | 14 |
| `GM_RM017` | 215 | 215 | 0 | 3 | 0 | 14 | 34 | 24 |

## Additional YOLO26l Probe Summary

| Scene | Before active | After active | Suppressed duplicate-like rows | Class-instability pairs | Class-mismatch rows explained | Partial/full pairs kept | Neighbor/crowding pairs kept | Unjudgeable pairs kept |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 413 | 383 | 30 | 19 | 32 | 28 | 8 | 15 |
| `GM_RM019` | 288 | 272 | 16 | 1 | 0 | 8 | 50 | 12 |
| `GM_RM017` | 215 | 211 | 4 | 0 | 0 | 14 | 40 | 24 |

## Required Answers

1. How did active-for-tracking counts change?

Mainline YOLO11l:

- `GM_RM011`: `422 -> 413`, down `9`;
- `GM_RM019`: `334 -> 330`, down `4`;
- `GM_RM017`: `215 -> 215`, unchanged.

Additional YOLO26l probe:

- `GM_RM011`: `413 -> 383`, down `30`;
- `GM_RM019`: `288 -> 272`, down `16`;
- `GM_RM017`: `215 -> 211`, down `4`.

2. How many high-overlap duplicate-like rows were shadow suppressed?

Mainline YOLO11l suppresses `9` rows in GM_RM011, `4` rows in GM_RM019, and `0` rows in GM_RM017. The suppression is deliberately conservative: only high-overlap, near-center, similar-size duplicate-like pairs are affected.

3. How many class-instability duplicate-like rows were explained as duplicate-like context?

For YOLO11l, class-mismatch duplicate-like context is attached to `16` rows in GM_RM011 and `2` rows in GM_RM019. These are context flags on primary and/or secondary rows, not identity claims. GM_RM017 has `3` class-instability duplicate-like pairs, but none meet the suppression rule, so no rows are marked as explained-by-suppressed duplicate-like context.

For YOLO26l, GM_RM011 has `32` rows marked with class-mismatch duplicate-like context. GM_RM019 has one class-instability pair but it is not suppressed by the conservative rule, so no rows are counted as explained-by-suppressed context.

4. How many partial/full, neighbor/crowding, and unjudgeable cases were retained?

Mainline YOLO11l retained all such contexts:

- `GM_RM011`: `44` partial/full pairs, `11` neighbor/crowding pairs, `20` unjudgeable pairs;
- `GM_RM019`: `34` partial/full pairs, `89` neighbor/crowding pairs, `14` unjudgeable pairs;
- `GM_RM017`: `14` partial/full pairs, `34` neighbor/crowding pairs, `24` unjudgeable pairs.

These are not suppressed because they are not safe same-frame duplicate cases.

5. Is GM_RM011 tracking input clearly cleaner?

Partially. GM_RM011 YOLO11l loses `9` duplicate-like rows from the shadow tracking input, and YOLO26l loses `30`. That reduces direct duplicate-overlap pressure. It does not solve the scene: GM_RM011 still keeps many partial/full, neighbor/crowding, unjudgeable, boundary/state, and class-instability contexts. The normalized table is cleaner as a probe input, not a clean stream.

6. Is GM_RM019 suitable for a later bounded tracker-side probe?

Yes, as a bounded diagnostic. YOLO11l normalization only suppresses `4` rows, but it preserves explicit context for `89` neighbor/crowding pairs and `34` partial/full pairs. YOLO26l normalization suppresses `16` duplicate-like rows and keeps fewer partial/full contexts. GM_RM019 is a good controlled follow-up scene because it is improved but still has enough competition context to test tracker sensitivity.

7. Is GM_RM017 still the simpler comparator?

Yes. YOLO11l normalization suppresses no rows in GM_RM017, and YOLO26l suppresses only `4`. GM_RM017 still has retained partial/full, neighbor/crowding, and unjudgeable contexts, so it remains a simpler comparator rather than proof of mechanism success.

8. Which conflicts cannot be solved by this normalization?

This probe cannot solve:

- partial/full competition;
- neighbor/crowding ambiguity;
- unjudgeable visual-review cases;
- adjacent-frame association breaks;
- short missing gaps;
- state transitions across time;
- class mismatch when the duplicate-like geometry is not strong enough;
- identity continuity.

Those conflicts require fragment relation context and later bounded tracker-side diagnosis.

9. Can the next step enter bounded tracker-side probe?

Yes, if kept as a shadow sensitivity probe. The tracker-side probe should consume normalized tables as alternate diagnostic inputs and compare changes in unmatched detections, duplicate-overlap events, lost/reactivated events, and short tracks. It must not replace ByteTrack settings, claim identity truth, enter SAR pairing, or enter support audit.

10. Is fragment relation audit still needed?

Yes. The normalization only suppresses same-frame duplicate-like observations. It intentionally preserves partial/full, neighbor competition, and unjudgeable cases. OTY1a/fragment relation context is still needed to explain whether retained observations should become strong, weak, ambiguous, or blocked continuity relations.

## Conclusion

```text
NORMALIZATION_PARTIALLY_REDUCES_CONFLICT_NEEDS_FRAGMENT_CONTEXT
```

The shadow normalized tables are useful and ready as diagnostic inputs for a bounded tracker-side probe. They are not clean object streams and they do not remove the need for fragment relation audit.

## Generated Artifacts

Committed:

- `tools/diagnostics/run_oty0_pretracking_observation_normalization_probe.py`
- `reports/oty2/oty2_pretracking_observation_normalization_probe_20260705_024520.md`
- `reports/oty2/samples/oty2_pretracking_observation_normalization_summary_20260705_024520.csv`

Generated but not committed:

- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM011_yolo11l_baseline_normalized_detection_table.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM011_yolo11l_baseline_normalization_actions.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM011_yolo11l_baseline_normalization_scene_summary.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM019_yolo11l_baseline_normalized_detection_table.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM019_yolo11l_baseline_normalization_actions.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM019_yolo11l_baseline_normalization_scene_summary.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM017_yolo11l_baseline_normalized_detection_table.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM017_yolo11l_baseline_normalization_actions.csv`
- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM017_yolo11l_baseline_normalization_scene_summary.csv`
- corresponding YOLO26l probe normalized tables, action tables, scene summaries, and JSON sidecars in the same ignored directory.

## No-Overstep Check

This pass did not:

- modify OTY0 runtime;
- modify OTY1, OTY1a, OTY1t, ByteTrack, P4, or P4G runtime;
- replace the main detector;
- edit main config or manifest files;
- run tracker;
- enter SAR pairing;
- enter support audit;
- create final annotations;
- create revised GT;
- create final boxes;
- create selector/ranking output;
- use weighted fusion;
- tune thresholds for optimization;
- submit outputs runtime artifacts;
- submit detector weights or large binaries;
- claim tracker ID, P4 ID, P4G object ID, or shadow normalized row state as identity truth.
