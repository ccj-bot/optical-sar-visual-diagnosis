# OTY2 Runtime Spatial Prior Audit Report

Generated: `20260702_144929`

This report reviews the first-pass runtime-safe spatial prior descriptions. It does not read SAR images, use SAR GT, implement SAR spatial search, generate search regions, generate candidate boxes, score candidates, tune thresholds, or make annotation recommendations.

## Summary

- total rows: `28`
- normal spatial priors: `11`
- review-only spatial contexts: `7`
- blocked rows: `10`
- spatial prior status counts: `{"blocked_missing_object_level_flow": 1, "blocked_no_spatial_prior": 9, "loose_spatial_prior_generated": 7, "normal_spatial_prior_generated": 4, "review_only_spatial_context_generated": 7}`
- geometry confidence counts: `{"blocked_missing_object_level_flow": 1, "blocked_no_runtime_spatial_prior": 9, "review_only_weak_azimuth_context_range_unknown": 7, "weak_azimuth_only_expanded_geometry": 8, "weak_azimuth_only_primary_geometry": 3}`
- range prior mode counts: `{"broad_unknown_range_prior": 11, "broad_unknown_range_prior_review_only": 7, "not_generated_for_blocked_object": 9, "not_generated_no_object_flow": 1}`

## Per-Scene Results

| scene | normal priors | review-only contexts | blocked | notes |
| --- | ---: | ---: | ---: | --- |
| `GM_RM011` | 0 | 0 | 1 | time metadata available, object flow missing |
| `GM_RM017` | 5 | 1 | 0 | range degraded to broad_unknown where prior exists |
| `GM_RM019` | 6 | 6 | 9 | range degraded to broad_unknown where prior exists |

## Degradation Findings

- All normal and review-only rows have azimuth weak priors available from configured optical-x to azimuth metadata and object bbox envelopes.
- All normal and review-only rows degrade range to `broad_unknown_range_prior` because no reliable per-object runtime range/depth field is present in current OTY2 inputs.
- No target was blocked solely because of secondary observation, edge, partial, duplicate, occlusion, or handoff state; those states expand/loosen the prior.
- Ambiguous/review-required targets are review-only contexts and are not mixed into normal priors.
- Short/noise and not-ready targets remain blocked.
- `GM_RM011` remains blocked only at the target level: timing metadata exists, but object flow is missing.

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

## Artifacts

- runtime_spatial_prior_contract: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_contract_20260702_144929.md`
- object_runtime_spatial_priors: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- runtime_spatial_prior_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_summary_20260702_144929.json`
- runtime_spatial_prior_report: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_report_20260702_144929.md`
- object_runtime_spatial_priors_sample: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_object_runtime_spatial_priors_sample.csv`
