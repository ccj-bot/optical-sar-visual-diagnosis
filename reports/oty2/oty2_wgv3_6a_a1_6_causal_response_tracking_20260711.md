# OTY2 WGV3.6A-A1.6 Causal Response Tracking Audit

## Boundary

- requested start commit: `2bf1ea2bafffe9876935b3b41f8c091d0a3fad2a`
- scene: `GM_RM019`
- generate/evaluate separation: `PASS`
- frozen predictions SHA256: `31ce1b65317fea5b1cb2a5b37afb8c2eb79416de625801d8e0ddef6da7df9c31`
- generation target manual boxes loaded: `false`
- evaluation target manual boxes loaded after freeze: `true`
- GM_RM011 executed: `false`

## Independent Temporal Source

| source_file | source_type | optical_time_field | sar_time_field | mapping_rule | uses_gt_or_manual_target | target_independent | usable_for_runtime | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reports/oty2/oty2_alignment_mode_decision_report_20260702_132945.md | alignment_mode_decision_report | known_optical_fps=24; software_sync_zero_offset_assumption | known_sar_fps=50; software_sync_zero_offset_assumption | sar_frame = optical_frame * 50 / 24, offset_seconds=0, jitter_ms=20 | false | true | conditional | Not hardware timestamp truth; sufficient only for conditional optical motion phase lookup and jitter-aware temporal reasoning. |
| reports/oty2/oty2_alignment_mode_decision_summary_20260702_132945.csv | per_scene_alignment_summary_csv | known_optical_fps; sync_mode; offset_seconds | known_sar_fps; software_sync_jitter_ms | GM_RM019 decision=timestamp_offset_scale_hypothesis; confidence=medium | false | true | conditional | Manual anchor candidates are explicitly not allowed temporal anchors; FPS scale is source metadata. |
| reports/oty2/oty2_temporal_metadata_inventory_20260702_132945.csv | temporal_metadata_inventory | numeric_filename_order_only; no per-frame timestamp | numeric_filename_order_only; no per-frame timestamp | does_not_upgrade_beyond_conditional_fps_scale | false | true | no | Inventory confirms missing real timestamps and missing hardware synchronization record. |

Decision: `TEMPORAL_ALIGNMENT_RUNTIME_SAFE=CONDITIONAL`. The source is target-independent FPS and software-sync metadata, not hardware per-frame timestamp truth.

## Method Definitions

- `C0`: fixed source anchor visible-response box; no SAR image response read.
- `C1`: pure SAR causal local response follower; previous frozen Y state + current SAR gray frame + static fan only; update only when exactly one component survives hard gates.
- `C2`: C1 plus conditional optical motion/depth consistency gates from the R2B optical state table; no optical-to-SAR center regression.

## Method Summary

| method | rows | coverage_median | coverage_mean | center_error_median | search_ratio_median | search_ratio_p90 | search_ratio_max | missing | ambiguous | switches |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 16 | 0.300733 | 0.401942 | 102.744106 | 0.004947 | 0.005 | 0.005 | 0 | 0 | 0 |
| C1 | 16 | 0.471385 | 0.431144 | 54.357845 | 0.014584 | 0.014824 | 0.014824 | 0 | 16 | 0 |
| C2 | 16 | 0 | 0.217602 | 174.864471 | 0.015919 | 0.016066 | 0.016066 | 4 | 15 | 0 |

## Hidden Anchor Evaluation

| experiment_id | method | hidden_target_pair_id | sar_frame | hidden_target_coverage | hidden_target_iou | prediction_center_to_visible_response_center | selection_status | first_lost_frame | ambiguous_frame_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ_0204_TO_0205 | C0 | WGV35A_PAIR_0205 | 31 | 1 | 0.8563 | 8.499648 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0204_TO_0205 | C1 | WGV35A_PAIR_0205 | 31 | 1 | 0.8563 | 8.499648 | ambiguous_response | 28 | 4 |
| ADJ_0204_TO_0205 | C2 | WGV35A_PAIR_0205 | 31 | 0.693498 | 0.470386 | 22.986468 | ambiguous_response | 29 | 2 |
| ADJ_0205_TO_0206 | C0 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 197.11602 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0205_TO_0206 | C1 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 101.100419 | ambiguous_response | 32 | 45 |
| ADJ_0205_TO_0206 | C2 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 656.121844 | selected_unique_component_after_hard_gate | 33 | 15 |
| ADJ_0206_TO_0207 | C0 | WGV35A_PAIR_0207 | 81 | 0.898568 | 0.736034 | 12.049722 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0206_TO_0207 | C1 | WGV35A_PAIR_0207 | 81 | 0.898568 | 0.736034 | 12.049722 | ambiguous_response | 78 | 4 |
| ADJ_0206_TO_0207 | C2 | WGV35A_PAIR_0207 | 81 | 0.898568 | 0.736034 | 12.049722 | ambiguous_response | 78 | 4 |
| ADJ_0208_TO_0209 | C0 | WGV35A_PAIR_0209 | 238 | 0.373204 | 0.192907 | 96.663416 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0208_TO_0209 | C1 | WGV35A_PAIR_0209 | 238 | 0.494538 | 0.272728 | 54.357845 | ambiguous_response | 213 | 24 |
| ADJ_0208_TO_0209 | C2 | WGV35A_PAIR_0209 | 238 | 0 | 0 | 174.864464 | missing_observation | 214 | 8 |
| ADJ_0209_TO_0210 | C0 | WGV35A_PAIR_0210 | 269 | 0.228262 | 0.131647 | 108.824796 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0209_TO_0210 | C1 | WGV35A_PAIR_0210 | 269 | 0.448232 | 0.296072 | 49.70154 | selected_unique_component_after_hard_gate | 239 | 29 |
| ADJ_0209_TO_0210 | C2 | WGV35A_PAIR_0210 | 269 | 0 | 0 | 174.833503 | missing_observation | 242 | 24 |
| ADJ_0210_TO_0211 | C0 | WGV35A_PAIR_0211 | 273 | 0.920889 | 0.846561 | 8.104961 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0210_TO_0211 | C1 | WGV35A_PAIR_0211 | 273 | 0.920889 | 0.846561 | 8.104961 | ambiguous_response | 270 | 4 |
| ADJ_0210_TO_0211 | C2 | WGV35A_PAIR_0211 | 273 | 0.774872 | 0.628029 | 22.925254 | selected_unique_component_after_hard_gate | 270 | 3 |
| ADJ_0211_TO_0212 | C0 | WGV35A_PAIR_0212 | 288 | 0.764685 | 0.637165 | 30.586588 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0211_TO_0212 | C1 | WGV35A_PAIR_0212 | 288 | 0.764685 | 0.637165 | 30.586588 | ambiguous_response | 274 | 15 |
| ADJ_0211_TO_0212 | C2 | WGV35A_PAIR_0212 | 288 | 0 | 0 | 363.489159 | ambiguous_response | 275 | 4 |
| ADJ_0212_TO_0213 | C0 | WGV35A_PAIR_0213 | 290 | 0.872259 | 0.808022 | 10.415418 | fixed_anchor_no_sar_response_read |  | 0 |
| ADJ_0212_TO_0213 | C1 | WGV35A_PAIR_0213 | 290 | 0.872259 | 0.808022 | 10.415418 | ambiguous_response | 289 | 2 |
| ADJ_0212_TO_0213 | C2 | WGV35A_PAIR_0213 | 290 | 0.4212 | 0.275194 | 67.256486 | selected_unique_component_after_hard_gate |  | 0 |

## Open Loop Evaluation

| experiment_id | method | hidden_target_pair_id | sar_frame | hidden_target_coverage | hidden_target_iou | prediction_center_to_visible_response_center | selection_status | first_lost_frame | ambiguous_frame_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPEN_WHITE_0204_TO_0207 | C0 | WGV35A_PAIR_0205 | 31 | 1 | 0.8563 | 8.499648 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0205 | 31 | 1 | 0.8563 | 8.499648 | ambiguous_response | 28 | 4 |
| OPEN_WHITE_0204_TO_0207 | C2 | WGV35A_PAIR_0205 | 31 | 0.693498 | 0.470386 | 22.986468 | ambiguous_response | 29 | 2 |
| OPEN_WHITE_0204_TO_0207 | C0 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 205.47647 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0206 | 77 | 0.0046 | 0.002252 | 91.740749 | ambiguous_response | 28 | 49 |
| OPEN_WHITE_0204_TO_0207 | C2 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 99.26076 | ambiguous_response | 29 | 27 |
| OPEN_WHITE_0204_TO_0207 | C0 | WGV35A_PAIR_0207 | 81 | 0 | 0 | 215.343475 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0207 | 81 | 0 | 0 | 100.928516 | ambiguous_response | 28 | 53 |
| OPEN_WHITE_0204_TO_0207 | C2 | WGV35A_PAIR_0207 | 81 | 0 | 0 | 181.094212 | ambiguous_response | 29 | 31 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0209 | 238 | 0.373204 | 0.192907 | 96.663416 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0209 | 238 | 0.494538 | 0.272728 | 54.357845 | ambiguous_response | 213 | 24 |
| OPEN_SILVER_0208_TO_0213 | C2 | WGV35A_PAIR_0209 | 238 | 0 | 0 | 174.864464 | missing_observation | 214 | 8 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0210 | 269 | 0 | 0 | 205.468723 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0210 | 269 | 0 | 0 | 279.647929 | ambiguous_response | 213 | 47 |
| OPEN_SILVER_0208_TO_0213 | C2 | WGV35A_PAIR_0210 | 269 | 0 | 0 | 215.585344 | missing_observation | 214 | 8 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0211 | 273 | 0 | 0 | 213.332439 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0211 | 273 | 0 | 0 | 331.910669 | ambiguous_response | 213 | 51 |
| OPEN_SILVER_0208_TO_0213 | C2 | WGV35A_PAIR_0211 | 273 | 0 | 0 | 244.608861 | selected_unique_component_after_hard_gate | 214 | 8 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0212 | 288 | 0 | 0 | 243.837424 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0212 | 288 | 0 | 0 | 590.424162 | ambiguous_response | 213 | 61 |
| OPEN_SILVER_0208_TO_0213 | C2 | WGV35A_PAIR_0212 | 288 | 0 | 0 | 408.839985 | selected_unique_component_after_hard_gate | 214 | 17 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0213 | 290 | 0 | 0 | 253.721373 | fixed_anchor_no_sar_response_read |  | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0213 | 290 | 0 | 0 | 640.645778 | ambiguous_response | 213 | 63 |
| OPEN_SILVER_0208_TO_0213 | C2 | WGV35A_PAIR_0213 | 290 | 0 | 0 | 437.366532 | ambiguous_response | 214 | 19 |

## Delta Audit

| comparison | experiment_id | experiment_type | physical_vehicle_id | hidden_target_pair_id | sar_frame | coverage_delta | iou_delta | center_error_delta | search_ratio_delta | verdict | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1_minus_C0 | ADJ_0204_TO_0205 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | 0 | 0 | 0 | 0.009824 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0204_TO_0205 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | -0.306502 | -0.385914 | -14.48682 | 0.001242 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0205_TO_0206 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 0 | 0 | 96.015601 | 0.00924 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0205_TO_0206 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 0 | 0 | -555.021425 | -0.001205 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0206_TO_0207 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 0 | 0 | 0 | 0.009587 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0206_TO_0207 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 0 | 0 | 0 | 0.001261 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0208_TO_0209 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | 0.121334 | 0.079821 | 42.305571 | 0.009637 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0208_TO_0209 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | -0.494538 | -0.272728 | -120.506619 | 0.001335 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0209_TO_0210 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 0.21997 | 0.164425 | 59.123256 | 0.008744 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0209_TO_0210 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | -0.448232 | -0.296072 | -125.131963 | 0.001241 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0210_TO_0211 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 0 | 0 | 0 | 0.008897 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0210_TO_0211 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | -0.146017 | -0.218532 | -14.820293 | 0.001223 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0211_TO_0212 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 0 | 0 | 0 | 0.008872 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0211_TO_0212 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | -0.764685 | -0.637165 | -332.902571 | 0.001219 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | ADJ_0212_TO_0213 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | 0 | 0 | 0 | 0.008972 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | ADJ_0212_TO_0213 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | -0.451059 | -0.532828 | -56.841068 | 0.001242 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | 0 | 0 | 0 | 0.009824 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | -0.306502 | -0.385914 | -14.48682 | 0.001242 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 0.0046 | 0.002252 | 113.735721 | 0.009824 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | -0.0046 | -0.002252 | -7.520011 | 0.001242 | neutral | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 0 | 0 | 114.414959 | 0.009824 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 0 | 0 | -80.165696 | 0.001242 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | 0.121334 | 0.079821 | 42.305571 | 0.009637 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | -0.494538 | -0.272728 | -120.506619 | 0.001335 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 0 | 0 | -74.179206 | 0.009637 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 0 | 0 | 64.062585 | 0.001335 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 0 | 0 | -118.57823 | 0.009637 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 0 | 0 | 87.301808 | 0.001335 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 0 | 0 | -346.586738 | 0.009637 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 0 | 0 | 181.584177 | 0.001335 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C1_minus_C0 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | 0 | 0 | -386.924405 | 0.009637 | harmed | Positive center_error_delta means the right method is closer to the hidden visible response center. |
| C2_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | 0 | 0 | 203.279246 | 0.001335 | improved | Positive center_error_delta means the right method is closer to the hidden visible response center. |

## Search Budget

- static fan geometry area: `2628414`
- C1/C2 search ratio median: `0.014584`
- C1/C2 search ratio p90: `0.015919`
- C1/C2 search ratio max: `0.016066`
- area expansion policy: fixed per-frame padding from prior response extent; no unbounded expansion.

## State And Failure Counts

- first lost frame: `28`
- missing observation trace rows: `76`
- ambiguous response trace rows: `353`
- measured response switch rows: `0`

## Gate Verdicts

- `TEMPORAL_ALIGNMENT_RUNTIME_SAFE`: `CONDITIONAL`
- `CAUSAL_RUNTIME_LEAK_FREE`: `PASS`
- `SAR_ONLY_CAUSAL_SIGNAL`: `PARTIAL_SUPPORTED`
- `OPTICAL_CONSTRAINT_ADDED_VALUE`: `improved=4;harmed=10`
- `OPEN_LOOP_STABILITY`: `PARTIAL_SHORT_RANGE_ONLY`
- `IDENTITY_AND_RESPONSE_SWITCH_MEASURED`: `PASS`
- `SEARCH_BUDGET_CONTROLLED`: `PASS`
- `A1.6_CAUSAL_CORE_READY`: `NO`
- `GM_RM011_BLOCKED`: `true`

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_6_causal_response_tracking_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_temporal_alignment_source_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_hidden_target_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_runtime_input_field_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_frozen_predictions_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_frame_state_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_hidden_anchor_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_6_c0_c1_c2_delta_audit_20260711.csv`

## Ignored Visual Outputs

- `outputs/wgv3_6a_a1_6_20260711/a1_6_runtime_adjacent_predictions.png`
- `outputs/wgv3_6a_a1_6_20260711/a1_6_runtime_open_loop_predictions.png`
- `outputs/wgv3_6a_a1_6_20260711/a1_6_eval_only_adjacent_target_overlay.png`
- `outputs/wgv3_6a_a1_6_20260711/a1_6_eval_only_failure_examples.png`

## Next Step

Do not run GM_RM011 yet. If this hard-gate follower remains ambiguous/missing, first repair causal SAR response association or add an independent intermediate-frame blind review set; do not resurrect P3 endpoint interpolation.