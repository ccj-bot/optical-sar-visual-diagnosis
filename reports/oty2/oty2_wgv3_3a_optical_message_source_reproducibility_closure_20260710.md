# OTY2 WGV3.3A Optical Message Source Reproducibility Closure

Date: 20260710

## Status

Conclusion: `CLOSED_PARTIALLY_REPRODUCIBLE`

This is not a rollback to WGV1. It preserves WGV2/WGV3 as valid mechanism work and closes the missing source-dependency question: which optical messages can be produced by the automatic optical backbone, and which remain WGV1.4 posthoc visual constraints.

## Source And Freeze

- Detection source: YOLO26l OTY0-equivalent detection tables from the 20260704 detector-quality probe.
- Tracker source: OTY1t standard MOT replay, primary BoT-SORT raw; ByteTrack raw retained as source audit comparison.
- BoT-SORT appearance use: not ReID-enabled; `with_reid=False` and blank-image update remain true for MOT replay.
- Appearance source: 512-d torchvision ResNet18 ImageNet learned appearance baseline from explicit local external weights, used post-tracker for evidence only.
- WGV1.4/WGV1.4b role: posthoc reference and validation only, read after automatic files were frozen.

## Input Files

| input_group | source |
| --- | --- |
| YOLO26l detection tables | outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv; outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv; outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm019/oty0_yolo_detection_table.csv |
| standard MOT tracker outputs | outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM011_yolo26l_probe_botsort_raw; outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM011_yolo26l_probe_bytetrack_raw; outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM017_yolo26l_probe_botsort_raw; outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM017_yolo26l_probe_bytetrack_raw; outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM019_yolo26l_probe_botsort_raw; outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM019_yolo26l_probe_bytetrack_raw |
| appearance and tracklet embeddings | outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000 |
| WGV1.4 posthoc references | reports/oty2/samples/oty2_yolo26l_wgv1_4_vehicle_fragments_20260708.csv; reports/oty2/samples/oty2_yolo26l_wgv1_4_same_vehicle_edges_20260708.csv; reports/oty2/samples/oty2_yolo26l_wgv1_4_temporal_context_edges_20260708.csv; reports/oty2/samples/oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv |

| frozen_file | sha256 |
| --- | --- |
| reports/oty2/samples/oty2_wgv3_3a_source_alignment_20260710.csv | 138cd41e65d86d1898d0d1ef71852e1d987d469ab53a658ce45b2f11076bae71 |
| reports/oty2/samples/oty2_wgv3_3a_auto_tracklet_nodes_20260710.csv | 4f7104f08b86bee1b830e4b9bd93ae57e9699bac41d2f11b7bd3d2b3d9dcfa51 |
| reports/oty2/samples/oty2_wgv3_3a_auto_relation_candidates_20260710.csv | ca72c314aa16dd8ec569b248fa9caf520bc1254d0267ebaa04311104a4ed1bdf |
| reports/oty2/samples/oty2_wgv3_3a_auto_relation_decisions_20260710.csv | ca72c314aa16dd8ec569b248fa9caf520bc1254d0267ebaa04311104a4ed1bdf |
| reports/oty2/samples/oty2_wgv3_3a_competition_relations_20260710.csv | 6caa6bc6322d0cedd6c4dbc391a1033768155bb46aa251ae3ea816832a5710a2 |

## Automatic Results

- automatic nodes: `53` (`ready=14`, `ready_with_uncertainty=10`, `insufficient=10`, `blocked=19`)
- candidate relations: `274`
- strong: `1`
- weak: `1`
- ambiguous: `172`
- blocked: `37`
- not_candidate: `63`

## WGV1.4 Mapping And Evaluation

- mapped fragments: `32/32`
- accepted-edge recall: `8/16`
- weak-edge recall: `6/7`
- forbidden_edge_violation_count: `0`
- context-edge false bridge count: `0`

| scene | auto_nodes | auto_nodes_ready | auto_nodes_ready_with_uncertainty | auto_nodes_insufficient_or_blocked | candidate_relations | strong_continuity | weak_continuity | ambiguous_continuity | blocked_continuity | not_candidate | wgv1_4_fragments | mapped_fragments | unmapped_fragments | mapping_coverage | accepted_reference_edges | accepted_recovered_edges | accepted_edge_recall | weak_reference_edges | weak_recovered_edges | weak_edge_recall | forbidden_or_context_reference_edges | forbidden_edge_violation_count | context_edge_false_bridge_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | 33 | 10 | 8 | 15 | 206 | 0 | 1 | 143 | 17 | 45 | 20 | 20 | 0 | 1.000000 | 14 | 6 | 0.428571 | 0 | 0 | 0.000000 | 4 | 0 | 0 |
| GM_RM017 | 4 | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 12 | 0 | 1.000000 | 2 | 2 | 1.000000 | 7 | 6 | 0.857143 | 14 | 0 | 0 |
| GM_RM019 | 16 | 3 | 2 | 11 | 68 | 1 | 0 | 29 | 20 | 18 | 0 | 0 | 0 | 0.000000 | 0 | 0 | 0.000000 | 0 | 0 | 0.000000 | 0 | 0 | 0 |

## Runtime-Reproducible Optical Messages

| optical_message_type | automatic_source_available | runtime_reproducible | confidence_or_uncertainty |
| --- | --- | --- | --- |
| stable_tracklet_segments | True | True | 14/53 nodes ready; remaining uncertain/blocked |
| strong_continuity_relation | True | True | 1 strong automatic relations |

## Automatic-Uncertain Or Diagnostic Messages

| optical_message_type | automatic_source_available | runtime_reproducible | confidence_or_uncertainty | wgv2_wgv3_usage_permission |
| --- | --- | --- | --- | --- |
| weak_continuity_relation | True | True | 1 weak automatic relations | automatic_uncertain_message |
| ambiguous_continuity_relation | True | True | 172 ambiguous automatic relations after competition preservation | automatic_uncertain_message |
| blocked_continuity_relation | True | True | 37 blocked automatic relations | automatic_uncertain_message |
| same_frame_multicar_competition | True | True | available as neighbor/competition pressure, not vehicle identity | automatic_uncertain_message |
| edge_truncation_pressure | True | True | available from bbox boundary/contact proxies | automatic_uncertain_message |
| forbidden_boundary_preservation | True | True | 0 forbidden/context violations under posthoc evaluation | automatic_uncertain_message |

## Posthoc-Visual-Only Or Blocked Messages

| optical_message_type | wgv2_wgv3_usage_permission | blocking_reason |
| --- | --- | --- |
| visible_unboxed_gap | posthoc_visual_constraint_only | requires visual or multimodal judgment outside current automatic source |
| occlusion_or_target_switch | posthoc_visual_constraint_only | current automatic route lacks explicit object-level visual switch adjudication |

## Not Available As Automatic Messages

| optical_message_type | wgv2_wgv3_usage_permission | blocking_reason |
| --- | --- | --- |
| non_vehicle_exclusion | not_available | requires negative non-vehicle evidence not produced by this optical route |

## Remaining Blockers

- Automatic MOT can produce tracklet hypotheses and some continuity relations, but it still bridges or misses several WGV1.4 visual boundaries.
- BoT-SORT does not use real ReID internally; appearance is post-tracker evidence.
- Visible-unboxed gaps, subject switch, same-color replacement, and non-vehicle exclusion are not closed as runtime automatic messages.
- WGV1.4 accepted and weak optical threads therefore cannot be represented as fully automatic runtime identity constraints.

## Output Files

- `reports/oty2/oty2_wgv3_3a_optical_message_source_audit_20260710.md`
- `reports/oty2/samples/oty2_wgv3_3a_source_alignment_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_auto_tracklet_nodes_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_auto_relation_candidates_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_auto_relation_decisions_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_competition_relations_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_auto_freeze_manifest_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_wgv1_4_node_mapping_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_reference_edge_evaluation_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_scene_metrics_20260710.csv`
- `reports/oty2/oty2_wgv3_3a_visual_failure_diagnosis_20260710.md`
- `reports/oty2/samples/oty2_wgv3_3a_visual_failure_cases_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3a_optical_message_capability_20260710.csv`
- `reports/oty2/oty2_wgv3_3a_optical_message_source_reproducibility_closure_20260710.md`

## Commands

```powershell
D:/MINICONDA/envs/py311/python.exe -m py_compile tools/diagnostics/run_oty2_wgv3_3a_optical_message_source_closure.py
D:/MINICONDA/envs/py311/python.exe tools/diagnostics/run_oty2_wgv3_3a_optical_message_source_closure.py
```

## Validation Summary

- Script syntax check: passed.
- Full run: passed with fixed seed `20260710`.
- Output rows: source alignment `6`, nodes `53`, relation candidates `274`, relation decisions `274`, competition rows `64`, node mappings `32`, reference edge evaluations `41`, scene metrics `3`, capability rows `11`, visual failure cases `8`.
- Required-field, duplicate-key, bbox availability, freeze manifest, and null-stat validation: passed in the final session check.
- Fixed-seed reproducibility: 14 WGV3.3A output files retained identical SHA256 hashes on rerun.

## Closure

WGV3.3A closes as partially reproducible: stable automatic optical segments and some strong/weak continuity messages are available, but WGV1.4 posthoc visual adjudication remains necessary for subject-switch, competitor-boundary, visible-unboxed, weak-thread, and forbidden-boundary messages.
