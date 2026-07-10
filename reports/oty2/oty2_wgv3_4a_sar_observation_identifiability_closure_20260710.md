# OTY2 WGV3.4A SAR Observation Identifiability Closure

Date: 20260710

WGV3.4A status: `CLOSED_PNG_DISPLAY_DOMAIN_INSUFFICIENT`
Imaging source gate status: `RAW_SOURCE_LOCATION_UNKNOWN`

## Boundary

Automatic stage used WGV3.3B, WGV3.3D automatic products, and SAR PNG display products only. WGV1.4/WGV1.8 and optical posthoc windows were read only after the automatic freeze.

No path is named as a final target trajectory. Paths remain local SAR response path segments.

## Automatic Freeze

- combined SHA256: `0d45f569889393fd21613b29ea9e3a1f85d9aeed113c878856011bc0769f510a`
- wgv1_4_read_before_freeze=false
- wgv1_8_read_before_freeze=false
- sar_gt_ids_loaded=false
- gt_box_or_center_loaded=false
- posthoc_window_labels_loaded=false

## Static Background Map

- persistent_static_structure: `162`
- recurrent_background_structure: `1737`
- variable_background: `28736`
- rare_response_location: `7883`
- insufficient_support: `949`

## Directed Short Paths

- directed_edges: `146441`
- short_paths: `6857`
- path_status_counts: `{'physically_possible_ambiguous_path': 306, 'recurrent_background_path': 2357, 'insufficient_length': 2553, 'static_structure_path': 1601, 'physically_consistent_short_path': 40}`

## Radial Bands

| radial_band | extraction_profile | short_path_count | physical_path_count | static_path_count | median_spatial_effect | median_temporal_effect |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | strict_physical_path | 424 | 0 | 250 | 0.31552955 | 0.09736563 |
| R1 | strict_physical_path | 538 | 1 | 303 | 0.22337478 | 0.19882975 |
| R2 | strict_physical_path | 472 | 1 | 231 | 0.01574258 | 0.00228641 |
| R3 | strict_physical_path | 17 | 0 | 3 | 0 | 0 |
| R4 | strict_physical_path | 0 | 0 | 0 | 0 | 0 |
| R5 | strict_physical_path | 0 | 0 | 0 | 0 | 0 |
| R0 | balanced_physical_path | 592 | 0 | 367 | 0.28902642 | 0.06690759 |
| R1 | balanced_physical_path | 762 | 3 | 435 | 0.1681056 | 0.10461494 |
| R2 | balanced_physical_path | 609 | 13 | 291 | 0 | -0.01648467 |
| R3 | balanced_physical_path | 30 | 3 | 5 | 0 | 0.02080166 |
| R4 | balanced_physical_path | 0 | 0 | 0 | 0 | 0 |
| R5 | balanced_physical_path | 0 | 0 | 0 | 0 | 0 |
| R0 | relaxed_physical_path | 1383 | 0 | 912 | 0.08663318 | 0.04631382 |
| R1 | relaxed_physical_path | 1380 | 3 | 850 | 0.08569214 | 0.06360692 |
| R2 | relaxed_physical_path | 620 | 13 | 307 | -0.00352308 | -0.04292116 |
| R3 | relaxed_physical_path | 30 | 3 | 4 | 0 | 0.02080166 |
| R4 | relaxed_physical_path | 0 | 0 | 0 | 0 | 0 |
| R5 | relaxed_physical_path | 0 | 0 | 0 | 0 | 0 |

## Automatic Hypotheses

| hypothesis_id | intersecting_short_path_count | physically_consistent_path_count | static_structure_path_count | recurrent_background_path_count | path_density_per_effective_volume |
| --- | --- | --- | --- | --- | --- |
| WGV33B_H001 | 305 | 0 | 101 | 79 | 0.000055166741 |
| WGV33B_H002 | 32 | 0 | 20 | 3 | 0.000035138235 |
| WGV33B_H003 | 271 | 0 | 106 | 50 | 0.000060900045 |
| WGV33B_H004 | 209 | 0 | 72 | 45 | 0.000072366054 |
| WGV33B_H005 | 429 | 0 | 143 | 119 | 0.000069460231 |
| WGV33B_H006 | 836 | 0 | 235 | 270 | 0.000069943841 |
| WGV33B_H007 | 225 | 0 | 63 | 87 | 0.000072922867 |

## Posthoc Evaluation

| evaluation_window_id | evaluation_class | confidence_status | overlapping_path_count | physical_path_count | static_path_count | path_density_per_effective_volume | identifiability_signal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WGV34A_EVAL_VP_001 | posthoc_vehicle_present_evaluation | vehicle_present_high_confidence | 261 | 0 | 82 | 0.000029990961 | static_background_competes_with_path_signal |
| WGV34A_EVAL_VP_002 | posthoc_vehicle_present_evaluation | vehicle_present_moderate_confidence | 77 | 0 | 18 | 0.00006547452 | static_background_competes_with_path_signal |
| WGV34A_EVAL_COMPLEX_001 | complex_competition_evaluation | complex_competition_evaluation | 876 | 14 | 146 | 0.000067716269 | static_background_competes_with_path_signal |
| WGV34A_EVAL_NEG_001 | trusted_negative_evaluation | vehicle_absent_moderate_confidence | 131 | 0 | 51 | 0.000021421484 | static_background_competes_with_path_signal |
| WGV34A_EVAL_NEG_002 | trusted_negative_evaluation | non_vehicle_structure_control | 97 | 0 | 25 | 0.000015861709 | static_background_competes_with_path_signal |

## Conclusion

The PNG-domain repairs reduce the WGV3.3D graph-percolation failure by using directed short paths and an independent static background map. However, the available PNG display products still do not provide a stable, source-grounded separation between vehicle-present windows and conservative negative/structure controls. Continuing by tuning PNG thresholds is therefore not recommended unless the imaging source chain is recovered.
