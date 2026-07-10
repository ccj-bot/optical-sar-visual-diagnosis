# OTY2 WGV3.4A WGV3.3D Failure Diagnosis

Date: 20260710

WGV3.3D files were not modified. This audit reads their code and automatic products to identify repair targets for WGV3.4A.

## Confirmed Structural Issues

- `WGV34A_FAIL_001` thread_graph_construction: undirected adjacency confirmed=True; strong_or_weak_edges=13063
- `WGV34A_FAIL_002` branch_competition: threads_with_branch_count_gt0=3083/3547; dense_branch_threads=136
- `WGV34A_FAIL_003` motion_interpretation: threads_with_temporal_continuity_le_0_5=3233/3547
- `WGV34A_FAIL_004` static_background_model: static_clutter_like_threads=0
- `WGV34A_FAIL_005` matched_control_model: control_supported_threads=3521/3547
- `WGV34A_FAIL_006` negative_window_definition: WGV3.3D late background was only not-T001, not visually verified vehicle-absent evidence.

## WGV3.3D Counts Reused For Diagnosis

- relation_status_counts: `{'ambiguous_local_continuity': 45288, 'weak_local_continuity': 12940, 'strong_local_continuity': 123}`
- thread_status_counts: `{'transient_unlinked': 2530, 'dynamic_local_response_mixed': 380, 'dynamic_local_response_supported': 635, 'control_indistinguishable': 2}`

## Repair Boundary

WGV3.4A repairs the observation path, static background, empirical controls, and radial stratification in new files only. It does not reinterpret WGV3.3D graph components as object tracks.
