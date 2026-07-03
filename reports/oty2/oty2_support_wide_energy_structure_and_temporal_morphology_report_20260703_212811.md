# OTY2 Support-Wide Energy Structure And Temporal Morphology Report

Generated: `20260703_212811`

This report corrects the previous GT-local/top-k support judgment by inspecting the whole reconstructed support region. It is posthoc mechanism diagnosis only: no annotation proposal, final box, selected component, selector/ranking, training, threshold tuning, best weight, or identity truth is produced.

## Ledger Boundary

- 442 = all SAR GT / SAR-side morphology reference pool
- 215 = current paired optical-object-to-SAR GT posthoc pool
- 195 = GM_RM011 blocked_missing_object_stream, not unannotated
- 20 = SAR-only morphology reference only
- 12 = dropout/no-match temporal continuation special pool, not clean paired morphology

## Fixed Diagnostic Thresholds

- support energy atoms: support-internal p97 local maxima with `12.0` px minimum separation.
- bright connected components: support-internal p85, 8-connected, area >= `8` px.
- These thresholds are public fixed diagnostics and are not selected by GT, not tuned for success, and not used for runtime prediction.

## Key Metrics

- paired_state_conditioned_support_rows: `215`
- support_image_available_rows: `215`
- support_wide_structure_yes: `155`
- support_wide_structure_uncertain: `60`
- support_wide_structure_no: `0`
- dominant_component_shape_mix: `strip_like=106;shell_like=88;block_like=21`
- support_wide_shell_proxy_yes_cases: `83`
- support_failure_type_mix: `support_ok_but_not_exclusive=191;support_contains_neighbor_structure=147;support_too_broad=146;state_compensation_missing=112;temporal_compensation_needed=112;optical_truncation_induced_shift=65;near_field_truncation_issue=33;support_too_narrow=24`
- temporal_probe_rows: `645`
- temporal_10frame_vehicle_like_cases: `112`
- temporal_10frame_background_stable_risk_cases: `2`
- continuity_case_rows: `13`
- panel_review_correction_note_rows: `13`
- manual_review_needed_case_count: `151`
- manual_review_needed_case_examples: `PAIR_GM_RM017_o145_s302_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o149_s310_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o151_s315_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o151_s315_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o152_s317_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o152_s317_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o153_s319_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o153_s319_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o154_s321_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o154_s321_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o155_s323_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o155_s323_oty1t_obj_GM_RM017_bytetrack_bt_0010`

## Vehicle Shell Proxy Definitions

- `dominant_side_ridge_proxy`: A large elongated component can act as a body-side ridge or boundary strip. Method: strip_like or shell_like dominant component. Limit: display grayscale and image-axis geometry do not prove physical near/far side
- `facing_side_hotspot_proxy`: Strong atoms may reflect facing-side or endpoint scattering. Method: at least two high-energy atoms under fixed p97 rule. Limit: hotspots may be background or neighbor scatterers
- `endpoint_or_corner_reflector_proxy`: Atoms near support boundary can be endpoint/corner candidates. Method: atom within fixed 15% support-edge band. Limit: support edge is optical-derived and may be shifted
- `far_side_weak_return_proxy`: Secondary weaker components can be far-side or weak body return candidates. Method: component count and secondary/dominant area ratio. Limit: physical far side is not calibrated
- `discontinuous_aligned_edges_proxy`: Separated atoms aligned along one axis may form discontinuous body edges. Method: fixed PCA eigenvalue ratio >= 2.5. Limit: road edges and guardrails can also align
- `strip_plus_corner_composition_proxy`: A strip component plus edge atom can represent strip + endpoint/corner composition. Method: strip/shell dominant component and edge_atom_count >= 1. Limit: depends on support reconstruction
- `multi_peak_enclosed_shell_proxy`: Multiple atoms/components spanning both image axes may form a shell-like body. Method: >=4 atoms, >=2 components, x/y spread thresholds. Limit: multi-vehicle arrangements can mimic a shell
- `block_like_vehicle_body_proxy`: A compact bright block can represent a body-core morphology. Method: fixed fill-ratio and area heuristic. Limit: small objects and background structures may be block-like
- `range_spread_with_core_proxy`: A range-spread component with a core can preserve vehicle morphology. Method: fixed range extent and area thresholds. Limit: spread mechanism is a hypothesis, not a physical proof
- `support_wide_vehicle_shell_proxy`: Aggregate support-wide shell/body structure evidence. Method: >=7 supportive proxies and <=1 competing component => yes; otherwise uncertain/no. Limit: not calibrated for selection or annotation

## Required Answers

1. 不能孤立看 top-k 高能点，因为 top-k 只是散射原子；车辆 morphology 需要 support 全域内的 atoms、条带、块、边界和时序漂移共同解释。
2. support 全域结构比 GT 内 top-k 更有机制意义：在 215 个 paired support 行中，`155` 个在固定规则下显示 atoms/components 可组织成 vehicle-like structure。
3. SAR 车辆外壳/边界 morphology 在本报告中定义为 support 内 elongated ridge、strip+corner、multi-peak shell、block-like body 或 range-spread-with-core 这些 posthoc proxy 的组合。
4. support 内散射原子可组织成 shell/strip/block/boundary 的样本数为 `83`；这些只是 posthoc shell proxy，不是 selector feature。
5. support 错误主要分为 range/azimuth misalignment、too narrow/too broad、range compression、truncation/near-field shift、state/temporal compensation missing、neighbor/background interference 和 reference-only no-support。
6. azimuth 对齐但 range 错的样本数为 `7`；样例包括 `PAIR_GM_RM019_o15_s31_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM019_o114_s238_oty1t_obj_GM_RM019_bytetrack_bt_0080;PAIR_GM_RM019_o129_s269_oty1t_obj_GM_RM019_bytetrack_bt_0080;PAIR_GM_RM019_o131_s273_oty1t_obj_GM_RM019_bytetrack_bt_0080;PAIR_GM_RM019_o0_s0_oty1t_obj_GM_RM019_bytetrack_bt_0001;PAIR_GM_RM019_o2_s4_oty1t_obj_GM_RM019_bytetrack_bt_0001;PAIR_GM_RM019_o4_s8_oty1t_obj_GM_RM019_bytetrack_bt_0001`。
7. 截断/近场需要状态或时序补偿的样本数为 `65`；这指向 support 重建/状态补偿，不是否定 SAR morphology。
8. temporal drift probe 在 10-frame 窗口中显示 vehicle-like gradual structure 的 case 数为 `112`。
9. wrong-frame/background-stable 风险在 10-frame 窗口中出现 `2` 个 case；这些需要人工复核 temporal context。
10. 所有 GT relation、SAR image atoms/components、shell proxy 和 temporal tube 仍然只是 posthoc hypothesis / validation，不进入 runtime prediction logic。
11. 下一步更适合做 motion/drift compatibility 与 GM_RM019 optical continuity review；若要收束阶段，也可以先做阶段复盘。GM_RM011 object stream recovery 是后续规模扩展，不应混入本 paired pool。

## Posthoc Hypotheses Only

- support-wide atoms/components use SAR image content for diagnosis only
- GT relation columns validate atom/component relation posthoc only
- vehicle shell proxies are not selector features or annotation rules
- temporal morphology tube labels are not identity truth
- support coverage quality does not equal association success

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- support_wide_energy_structure_diagnostic_entered: `true`
- vehicle_shell_proxy_entered: `true`
- support_failure_taxonomy_entered: `true`
- temporal_morphology_drift_probe_entered: `true`
- multi_frame_chinese_atlas_generated: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- annotation_proposal_entered: `false`
- final_candidate_box_output: `false`
- selected_component_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- best_weight_selected: `false`
- identity_truth_claimed: `false`
- support_wide_shell_proxy_written_as_annotation_rule: `false`
- temporal_tube_written_as_identity_truth: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
- matlab_zip_or_any_zip_committed: `false`

## Outputs

- correction_archive_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_support_wide_energy_structure_and_temporal_morphology_correction_archive.md`
- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_support_wide_energy_structure_and_temporal_morphology_plan.md`
- support_wide_energy_atoms_and_components_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_wide_energy_atoms_and_components_20260703_212811.csv`
- support_wide_vehicle_shell_proxy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_wide_vehicle_shell_proxy_20260703_212811.csv`
- support_failure_taxonomy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_failure_taxonomy_20260703_212811.csv`
- temporal_morphology_drift_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_morphology_drift_probe_20260703_212811.csv`
- multiframe_structure_continuity_cases_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_multiframe_structure_continuity_cases_20260703_212811.csv`
- panel_review_correction_notes_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_panel_review_correction_notes_20260703_212811.csv`
- support_wide_energy_structure_and_temporal_morphology_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_wide_energy_structure_and_temporal_morphology_report_20260703_212811.md`
- support_wide_energy_structure_and_temporal_morphology_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_wide_energy_structure_and_temporal_morphology_summary_20260703_212811.json`
- visual_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_support_wide_energy_structure_temporal_atlas_cn_20260703_212811.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_support_wide_energy_structure_and_temporal_morphology_20260703_212811.log`

## Sources

- support_peak_competition_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- support_coverage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_support_coverage_hypothesis_audit_20260703_163000.csv`
- gt_energy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_box_energy_distribution_audit_20260703_163000.csv`
- complete_pool_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_complete_optical_high_confidence_coverage_pool_20260703_163000.csv`
- compensation_pool_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_truncated_occluded_temporal_compensation_pool_20260703_163000.csv`
- chinese_review_card_index_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_chinese_review_card_index_20260703_174930.csv`
- overlay_geometry_debug_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_overlay_case_geometry_debug_20260703_174930.csv`
