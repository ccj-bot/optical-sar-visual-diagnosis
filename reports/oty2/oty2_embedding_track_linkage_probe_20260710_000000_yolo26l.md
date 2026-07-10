# OTY2 Embedding Track Linkage Probe

Timestamp: `20260710_000000_yolo26l`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `cdc80af`

## Boundary

This probe only attaches existing OTY0 detection-level crop embedding handles to existing OTY1t tracker assignment rows. It does not compute appearance similarity, aggregate tracklet embeddings, stitch tracklets, assign identity truth, tune tracker parameters, modify OTY0/OTY1/OTY1a/OTY1t runtime, run SAR pairing/support, generate final boxes, create final/revised annotations, create selector/ranking output, use weighted fusion, or promote `GM_RM011` into the clean `215` pool.

The full linkage table is written only under ignored `outputs/`; only this report and small CSV samples are intended for commit.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools/diagnostics/run_oty1t_embedding_track_linkage_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --embedding-index outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000/oty2/crop_reid_embedding_probe_20260710_000000_yolo26l/crop_reid_embedding_index.csv --embedding-array outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000/oty2/crop_reid_embedding_probe_20260710_000000_yolo26l/crop_reid_embeddings.npz --tracker-output-root outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000 --output-root outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000 --timestamp 20260710_000000_yolo26l
```

## Inputs

- embedding index: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embedding_index.csv`
- embedding array: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embeddings.npz`
- full uncommitted linkage rows: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\embedding_track_linkage_probe_20260710_000000_yolo26l\embedding_track_linkage_rows.csv`
- summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_embedding_track_linkage_probe_summary_20260710_000000_yolo26l.csv`
- schema preview CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_embedding_track_linkage_schema_preview_20260710_000000_yolo26l.csv`

Tracker assignment outputs discovered and used:

- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM011_yolo26l_probe_botsort_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM011_yolo26l_probe_bytetrack_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM017_yolo26l_probe_botsort_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM017_yolo26l_probe_bytetrack_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM019_yolo26l_probe_botsort_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM019_yolo26l_probe_bytetrack_raw\oty1t_tracker_detection_assignments.csv`

## Summary

| scene | tracker_name | tracker_variant | tracker_rows_total | tracker_rows_with_valid_bbox | embedding_rows_available | direct_source_links | iou_high_links | iou_acceptable_links | iou_weak_links | unmatched_tracker_rows | ambiguous_links | linked_tracker_rows_total | linked_tracker_row_rate | unique_track_ids | track_ids_with_any_embedding | track_ids_with_embedding_rate | conclusion_scene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | botsort | raw | 413 | 413 | 413 | 413 | 0 | 0 | 0 | 0 | 0 | 413 | 1.000000 | 18 | 18 | 1.000000 | EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION |
| GM_RM011 | bytetrack | raw | 413 | 413 | 413 | 413 | 0 | 0 | 0 | 0 | 0 | 413 | 1.000000 | 23 | 23 | 1.000000 | EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION |
| GM_RM017 | botsort | raw | 215 | 215 | 215 | 215 | 0 | 0 | 0 | 0 | 0 | 215 | 1.000000 | 4 | 4 | 1.000000 | EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION |
| GM_RM017 | bytetrack | raw | 215 | 215 | 215 | 215 | 0 | 0 | 0 | 0 | 0 | 215 | 1.000000 | 4 | 4 | 1.000000 | EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION |
| GM_RM019 | botsort | raw | 288 | 288 | 288 | 288 | 0 | 0 | 0 | 0 | 0 | 288 | 1.000000 | 14 | 14 | 1.000000 | EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION |
| GM_RM019 | bytetrack | raw | 288 | 288 | 288 | 288 | 0 | 0 | 0 | 0 | 0 | 288 | 1.000000 | 15 | 15 | 1.000000 | EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION |

## Required Answers

1. Which OTY1t tracker outputs were discovered and used?

- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM011_yolo26l_probe_botsort_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM011_yolo26l_probe_bytetrack_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM017_yolo26l_probe_botsort_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM017_yolo26l_probe_bytetrack_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM019_yolo26l_probe_botsort_raw\oty1t_tracker_detection_assignments.csv`
- `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000\GM_RM019_yolo26l_probe_bytetrack_raw\oty1t_tracker_detection_assignments.csv`

2. Which tracker variant is the primary target?

`BoT-SORT normalized active-only`, recorded as `tracker_name=botsort` and `tracker_variant=normalized_active`.

3. Did tracker outputs preserve direct source detection row linkage?

`True`. The assignment schema carries `scene`, `optical_frame_num`, and `det_id`, which maps directly to embedding index `scene`, `frame_id`, and `det_id_ignored`.

4. If not, was same-scene/same-frame IoU matching used?

`False`. IoU fallback is implemented for rows without direct keys, but the discovered closure outputs linked through direct source detection handles.

5. What IoU thresholds were used?

- high confidence link: `IoU >= 0.90`
- acceptable link: `IoU >= 0.70`
- weak candidate: `IoU >= 0.50`
- unmatched: `IoU < 0.50`

6. How many tracker rows were linked to OTY0 crop embeddings per scene?

- primary rows unavailable

7. What percentage of tracker rows were linked per scene?

- primary rows unavailable

8. How many track ids have at least one linked embedding?

- primary rows unavailable

9. Are there unmatched tracker rows? Why?

`0` unmatched linkage rows across all used outputs. For the primary BoT-SORT normalized active-only rows, direct source linkage covered every row, so there is no source-row or IoU review blocker.

10. Are there ambiguous same-frame matches?

`0` ambiguous linkage rows across all used outputs. Direct source linkage avoided same-frame bbox ambiguity in the discovered closure outputs.

11. Does the linkage support tracklet-level embedding aggregation?

`True` for the primary BoT-SORT normalized active-only variant: each primary tracker row links to an embedding row handle and each nonempty primary tracker track id has at least one linked embedding.

12. What exact tracklet-level aggregation input is now available?

For each linked row: `scene`, `frame_id`, `tracker_name`, `tracker_variant`, `track_id`, tracker bbox, source `det_id_ignored`, embedding row uid, embedding backend, embedding dimension, and the uncommitted embedding artifact path. This is sufficient to group linked detection embeddings by `(scene, tracker_name, tracker_variant, track_id)` in a later report-only aggregation probe.

13. Why this still does not perform final stitching or assign identity truth?

The probe performs only deterministic row linkage. It does not compare embedding vectors, aggregate vectors, score stitch candidates, merge tracker ids, produce identity decisions, or write any final annotation or SAR-support artifact.

14. What exact next probe should be run after linkage?

`OTY1t tracklet-level embedding aggregation and candidate stitch pair proposal`

That next probe should remain report-only and must not produce final identity assignment.

## Non-Actions

- No OTY0/OTY1/OTY1a/OTY1t runtime was modified.
- No tracker parameters were tuned.
- No detector comparison was rerun.
- No appearance similarity was used for linkage.
- No SAR pairing/support was run.
- No final boxes, final/revised annotations, selector/ranking output, weighted fusion output, or identity truth were produced.
- `GM_RM011` was not promoted into the clean `215` pool.

## Conclusion

```text
EMBEDDING_TRACK_LINKAGE_INPUTS_MISSING
```
