# OTY2 WGV3.6A-A1.5 Propagation Integrity Audit

## Repository State At Audit Start

- requested start commit: `022884893cef913c66f187c05bc05c17093fc2d5`
- branch: `feature/oty2-posthoc-mechanism-validation`
- HEAD at audit start: `022884893cef913c66f187c05bc05c17093fc2d5`
- local/remote divergence before new commit: `0	0`
- initial `git status --short`: `clean` (verified before creating A1.5 audit artifacts)

## WGV3.6A Commit Inventory

```text
A	reports/oty2/oty2_wgv3_6a_gm019_closure_20260711.md
A	reports/oty2/oty2_wgv3_6a_gm019_visual_diagnosis_20260711.md
A	reports/oty2/oty2_wgv3_6a_sparse_anchor_design_20260711.md
A	reports/oty2/samples/oty2_wgv3_6a_gm019_anchor_audit_20260711.csv
A	reports/oty2/samples/oty2_wgv3_6a_gm019_bidirectional_closure_20260711.csv
A	reports/oty2/samples/oty2_wgv3_6a_gm019_failure_cases_20260711.csv
A	reports/oty2/samples/oty2_wgv3_6a_gm019_propagation_manifest_20260711.csv
A	tools/diagnostics/run_oty2_wgv3_6a_sparse_anchor_response_propagation.py
```

## Main Finding

WGV3.6A is not independent single-anchor propagation. In `propagate_interval`, the future anchor manual SAR box is read into `target_box` before output generation, and P1/P2/P3 use the source and target manual boxes as a known two-endpoint interpolation base. The original `0.952958` visible-response coverage is therefore `invalid_for_independent_propagation` and should be kept only as a record-level endpoint diagnostic.

This does not mean the files should be deleted. It means the experiment must be named `bidirectional_interpolation_with_known_endpoints`, while single-anchor forward/backward extrapolation remains untested by an independent non-anchor metric.

## Latest Manual Identity And Review Context

- `reports/oty2/oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_20260710.md` is the latest GM_RM019 identity/observation audit used here.
- `reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_center_semantic_review_20260711.csv` records that SAR centers are visible-response centers or mask-biased centers, not complete vehicle centers.
- `reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv` records the manual optical-state/identity gate used by WGV3.6A anchors.

## Variant Definitions

| variant | initial_region_source | optical_motion_used | relative_depth_used | sar_image_used | sar_response_extractor | region_center_update | region_size_update | mask_used | mask_trigger_condition | target_frame_manual_box_read_before_output | future_anchor_read_before_output | actual_changed_row_count_vs_previous | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | source anchor manual SAR visible-response bbox | false | false | false | none | fixed source anchor center | fixed source anchor size | denominator_only | none | true | true_for_interval_control_and_metric_not_region |  | P0 output box itself is fixed to the source anchor, but target_pair is still loaded before loop and metric computation. |
| P1 | linear interpolation between source and future target manual SAR anchor bboxes | implicit_endpoint_trend_only | false | false | none | linear source-to-target endpoint interpolation | linear source-to-target width/height interpolation | denominator_only | none | true | true | 132 | P1 is known-two-endpoint interpolation; endpoint coverage of 1.0 is not independent propagation evidence. |
| P2 | P1 endpoint interpolation base | implicit_endpoint_trend_only | false | true | local connected bright component within expanded predicted window | 40 percent shift from P1 base toward local SAR response centroid | inherits P1 interpolated size; local response does not resize | fan_mask filters local response pixels | all local response extraction is fan-mask filtered | true | true | 54 | P2 adds SAR-image response centering but remains anchored to the future manual endpoint. |
| P3 | P2 local response region | implicit_endpoint_trend_only | false | true | same as P2, plus post-response fan/bottom boundary clipping branch | same as P2 unless mask branch clips y extent | same as P2 unless mask branch clips y extent | fan_mask plus boundary clipping check | mask_intersection_ratio < 0.92 or bottom_valid_margin < 55 | true | true | 0 | P3 mask branch trigger count in existing manifest: 0; common forward P2/P3 rows are identical after excluding the method label when this is zero. |

## Variant Difference Diagnostics

- P1 changed vs P0 rows: `132`
- P2 changed vs P1 rows: `54`
- P3 changed vs P2 rows: `0`
- P3 mask branch trigger count: `0`
- P2/P3 common forward rows: `54`
- P2/P3 no-op rows: `54`

Category counts:

| category | count |
| --- | --- |
| P2_hurts_coverage | 4 |
| P2_moves_to_stronger_response | 44 |
| P2_moves_to_wrong_or_unverified_response | 6 |
| P3_no_op | 54 |

## Unique Frame Accounting

- original P3 forward records: `54`
- original P3 backward records: `54`
- unique SAR frames, all variants: `134`
- unique SAR frames, P3: `82`
- unique optical anchor frames: `10`
- unique vehicles: `2`
- unique anchor intervals: `8`
- anchor self count: `10`
- unique non-anchor middle SAR frames, all variants: `124`
- unique non-anchor middle SAR frames, P3: `72`
- forward/backward duplicate unique frames: `51`
- cross-interval duplicate unique frames: `6`

## Metric Recompute

- original record-level visible_response_coverage: `0.952958` over P3 forward target endpoint records
- original record-level masked_overlap_coverage: `0.952958` over the same endpoint records
- recomputed unique_non_anchor_visible_box_coverage: `not_tested`
- recomputed unique_non_anchor_region_area_ratio mean/median: `0.004198` / `0.004015`
- unique_non_anchor_search_ratio_median: `0.020842`

Non-anchor coverage is `NOT_TESTED`, not zero: the WGV3.6A manifest does not contain independent middle-frame manual/eval boxes. The correct conclusion is missing evaluation evidence, not failure of every middle-frame region.

## Search Ratio Denominator

- canvas_area: `3078872`
- static_fan_geometry_area / actual_denominator_area: `2628414`
- stable_nonzero_area from R2C inventory: `1860594`
- denominator_type: `static_fan_geometry_area`
- denominator consistency: same for P0/P1/P2/P3; target independent; not built from manual boxes.

## Closure Reaudit

- C0 count: `2`
- C1 count: `0`
- C2 count: `6`
- C3 count: `0`

C0 is only window/region intersection and is not complete closure. C3 is not supported because the manifest does not preserve connected-component identity across forward/backward runs.

## Gate Table

| item | status | reason |
| --- | --- | --- |
| anchor_initialization_roles_clear | PASS | Manual anchor fields and identity-review gates are now explicitly ledgered. |
| propagation_does_not_read_target_frame_manual_box | FAIL | target_box is read before P1/P2/P3 output and used for endpoint interpolation. |
| propagation_does_not_read_eval_response_region | CONDITIONAL | No middle-frame eval region is read, but R2C mask class gates anchors and fan mask filters local response. |
| metrics_unique_non_anchor_frames | FAIL | Original 0.952958 coverage is P3 forward target-endpoint record-level only. |
| P1_improvement_independent_evidence | FAIL | P1 uses future endpoint manual anchor; endpoint coverage is structurally inflated. |
| P2_sar_correction_net_positive | NOT_TESTED | P2 moves to local SAR response, but non-anchor independent eval boxes are absent. |
| P3_mask_actual_trigger | FAIL | P3 mask branch triggered 0 times. |
| bidirectional_closure_reaches_C2_or_C3 | CONDITIONAL | C2=6, C3=0; C3 is not supported by component identity. |
| search_denominator_clear | PASS | actual denominator is static fan geometry area 2628414. |
| identity_contamination_eval_independent | CONDITIONAL | Anchor identities are reviewed, but no middle-frame identity contamination measurement exists. |
| current_results_support_A2 | FAIL | Known-endpoint/manual target leakage plus no unique non-anchor coverage eval. |
| current_results_support_GM_RM011 | FAIL | A2 gate fails; GM_RM011 was not run and remains future pressure-test only. |

## A2 And GM_RM011 Gates

- A2 gate: `A2_NOT_READY`
- GM_RM011 gate: `GM_RM011_NOT_READY`
- Minimum next step: add or recover an independent non-anchor evaluation set, then rerun this audit without target-endpoint boxes in region generation. Do not run GM_RM011 pressure testing until the A2 gate is cleared.

## Created Audit Artifacts

- `reports/oty2/samples/oty2_wgv3_6a_a1_5_source_role_ledger_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_5_variant_definition_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_5_unique_frame_accounting_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_5_metric_recompute_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_5_closure_reaudit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_5_variant_difference_diagnostics_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_5_visual_audit_index_20260711.csv`
- `reports/oty2/oty2_wgv3_6a_a1_5_propagation_integrity_audit_20260711.md`
- `outputs/wgv3_6a_a1_5_20260711/a1_5_visual_audit_01_P2_moves_to_stronger_response.png`
- `outputs/wgv3_6a_a1_5_20260711/a1_5_visual_audit_02_P2_hurts_coverage.png`
- `outputs/wgv3_6a_a1_5_20260711/a1_5_visual_audit_03_P3_no_op.png`
