# OTY2 WGV3.5A Pair And Depth Audit

Date: 20260710

## Boundary

This stage uses existing optical-SAR correspondence rows for weak calibration. It does not modify GT, does not output final automatic annotations, and does not use SAR PNG brightness for whole-image target discovery.

## Pair Inventory

- source: `reports/oty2/oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- total_pairs: `204`
- usable_high_confidence_pairs: `138`
- scenes: `{'GM_RM017': 188, 'GM_RM019': 16}`
- pair_confidence_counts: `{'posthoc_only_pair': 64, 'high_confidence_pair': 138, 'identity_ambiguous_pair': 1, 'non_vehicle_pair': 1}`

## Depth Source Audit

| scene | depth_source_status | depth_meaning | frame_alignment | depth_file_count | optical_frame_count | strategy | train_spearman_like_corr_to_sar_radial |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | RELATIVE_DEPTH_UNSTABLE | depth_arrays_exist_but_monotonic_relation_is_weak_or_scene_limited | one_to_one_filename_alignment | 368 | 368 | D0 | 0 |
| GM_RM017 | RELATIVE_DEPTH_MONOTONIC | relative_depth_or_network_depth_monotonic_to_sar_radial;not_treated_as_metric | one_to_one_filename_alignment | 368 | 368 | D4 | 0.755807 |
| GM_RM019 | RELATIVE_DEPTH_UNSTABLE | depth_arrays_exist_but_monotonic_relation_is_weak_or_scene_limited | one_to_one_filename_alignment | 368 | 368 | D0 | 0 |

## Identity-Safe Split

| scene | thread_id | split_role | pair_count | frame_start | frame_end | leakage_check |
| --- | --- | --- | --- | --- | --- | --- |
| GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0008 | blocked | 61 | 145 | 182 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=61 |
| GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0010 | train | 71 | 151 | 189 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=1 |
| GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0012 | validation | 52 | 162 | 210 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=0 |
| GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0014 | test | 3 | 184 | 212 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=0 |
| GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0001 | blocked | 3 | 0 | 4 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=3 |
| GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0005 | external_scene_test | 4 | 13 | 39 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=0 |
| GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0009 | blocked | 1 | 13 | 13 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=1 |
| GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0080 | external_scene_test | 6 | 102 | 139 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=0 |
| GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0098 | external_scene_test | 2 | 151 | 152 | thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread=0 |

## Interpretation

GM_RM017 provides the main high-confidence calibration pool. GM_RM019 is preserved as an external-scene holdout. The split is by vehicle thread/scene, not random frame sampling.
