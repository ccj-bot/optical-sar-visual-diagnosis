# OTY2 Runtime Spatial Prior Contract

Generated: `20260702_144929`

This contract defines the first runtime-safe spatial prior description emitted from object-level temporal windows. It is not SAR detection, not a final annotation, not a candidate-box score, and not a final position claim.

## Inputs

- Object-level SAR temporal windows from OTY2 software-sync timing.
- Temporal-window quality gate rows that separate normal, review-only, and blocked objects.
- P4G object hypotheses and object-frame state rows for optical bbox envelopes and uncertainty states.
- Scene-config fan/azimuth constants as weak configured geometry metadata.

Forbidden runtime inputs remain excluded: SAR image content, SAR GT, final/manual/oracle/review fields, selector/ranking output, tuned thresholds, and annotation labels.

## Output Semantics

- Normal spatial priors are emitted for `ready_primary_sar_temporal_window` and `ready_uncertainty_expanded_sar_temporal_window` rows.
- `low_confidence_sar_temporal_window` rows emit review-only spatial context and are not mixed into normal priors.
- `not_ready_for_sar_temporal_window` rows remain blocked.
- `GM_RM011` remains a scene-level blocker: timing metadata is available, but object-level optical flow is missing.

## Geometry Interpretation

- Azimuth is a weak configured prior from optical bbox envelope and the configured legacy `azimuth_k/azimuth_b` mapping.
- Secondary, edge, partial, duplicate, occlusion, and handoff states expand the azimuth margin instead of forcing a blocker.
- Ambiguous/review-required rows can keep review-only azimuth context, but not normal priors.
- Range is currently degraded to `broad_unknown_range_prior` because the current OTY2 inputs do not contain a reliable per-object runtime range/depth transfer.
- No row in this output is a SAR search region, SAR candidate box, final localization, or annotation recommendation.

## Per-Scene Counts

| scene | normal priors | review-only contexts | blocked | azimuth available | range broad-unknown | geometry insufficient |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 0 | 0 | 1 | 0 | 0 | 0 |
| `GM_RM017` | 5 | 1 | 0 | 6 | 6 | 0 |
| `GM_RM019` | 6 | 6 | 9 | 12 | 12 | 0 |

## Boundary Flags

- sar_image_content_used: `false`
- sar_spatial_search_implemented: `false`
- sar_search_region_generated: `false`
- sar_candidate_boxes_generated: `false`
- candidate_box_scoring_used: `false`
- sar_gt_used: `false`
- final_manual_oracle_review_runtime_fields_used: `false`
- selector_or_ranking_used: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- detection_box_level_merge_reintroduced: `false`
- spatial_prior_claimed_as_final_location: `false`

## Sources

- temporal_window_quality_audit: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_audit_20260702_142454.csv`
- object_sar_temporal_windows: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- object_hypotheses: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_hypotheses_generalized.csv`
- object_frame_states: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- scene_config: `D:\profile\research\optical-sar-visual-diagnosis\configs\scene_config.yaml`

## Artifacts

- runtime_spatial_prior_contract: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_contract_20260702_144929.md`
- object_runtime_spatial_priors: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- runtime_spatial_prior_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_summary_20260702_144929.json`
- runtime_spatial_prior_report: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_report_20260702_144929.md`
- object_runtime_spatial_priors_sample: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_object_runtime_spatial_priors_sample.csv`
