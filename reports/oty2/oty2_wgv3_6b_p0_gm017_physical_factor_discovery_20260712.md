# WGV3.6B-P0 GM_RM017 Physical Response Factor Discovery

## Scope

This report records a phase-separated GM_RM017 physical-factor study. It does not produce final annotations, revised GT, selector/ranking logic, or a unique final vehicle box.

## Worktree And Start

- start_commit: `aba57096e6b38e33bfac4a6e68d6d00aa40ace5c`
- current_head: `aba57096e6b38e33bfac4a6e68d6d00aa40ace5c`
- branch: `feature/oty2-gm017-physical-factor-discovery`
- worktree: `D:\profile\research\optical-sar-visual-diagnosis-gm017-physics`

## Input Provenance

- `DOC01` required_doc: read_before_task; no final box, selector, ranking, or GT leakage into holdout generation
- `DOC02` required_doc: read_before_task; no final box, selector, ranking, or GT leakage into holdout generation
- `DOC03` required_doc: read_before_task; no final box, selector, ranking, or GT leakage into holdout generation
- `DOC04` required_doc: read_before_task; no final box, selector, ranking, or GT leakage into holdout generation
- `DOC05` required_doc: read_before_task; no final box, selector, ranking, or GT leakage into holdout generation
- `SRC01` paired_annotations: target_thread=oty1t_obj_GM_RM017_bytetrack_bt_0010; target_paired_sar=315;317;319;321;323;325;327;331-394
- `SRC02` frame_map: exact timestamp metadata is unavailable; current source is frame-count ratio audit only
- `SRC03` temporal_window: N005 real optical range is 121-129; SAR range comes from P0 frame-ratio temporal-window source, not exact timestamp truth
- `SRC04` optical_timeline_graph_node: GM_RM017_N005=non_vehicle_exclusion; Foreground barrier or temporary structure, not a vehicle referent.
- `SRC05` optical_timeline_graph_edge: Box follows a foreground barrier or temporary structure, not a vehicle.
- `SRC06` image_inventory: sample_size=(800, 600)
- `SRC07` image_inventory: sample_size=(2308, 1334); grid_matches_2308x1334=True

## Split

- `GM017_DISC_CAL_0010` physical_discovery_and_parameter_calibration: SAR `315-360`, optical `151-173`, gt_allowed=`true`
- `GM017_GUARD_0010` time_guard_gap: SAR `361-370`, optical `173-178`, gt_allowed=`false`
- `GM017_HOLDOUT_0010` holdout_validation_generation_then_eval: SAR `371-394`, optical `178-189`, gt_allowed=`false_during_validate_generate;true_after_prediction_freeze_in_evaluate`
- `GM017_N005_BACKGROUND_CONTROL` background_non_vehicle_control: SAR `249-274`, optical `121-129`, gt_allowed=`manual_non_vehicle_status_allowed_for_calibration_counterexample_only`

## Phase Counts

- control_points: `37`
- response_component_observations: `2043`
- holdout_prediction_rows: `1603`

## Factor Verdicts

- `F1_COMMON_MOTION` = `SUPPORTED`; SUPPORTED; relative_improvement=0.985837; same_motion_candidates=31
- `F2_BACKGROUND_STABILITY` = `SUPPORTED`; SUPPORTED; static_background_candidates=37
- `F3_PART_VISIBILITY` = `PARTIAL`; PARTIAL; missing_summary_frames=6
- `F4_SCALE_RANGE_RELATION` = `PARTIAL`; PARTIAL; relative_improvement=-0.821687
- `F5_OPTICAL_SAR_TREND` = `PARTIAL`; PARTIAL; sign_agreement=0.695652

## Gate Integrity

- `PARALLEL_WORKTREE_ISOLATED`: `PASS` (branch=feature/oty2-gm017-physical-factor-discovery;head=aba57096e6b38e33bfac4a6e68d6d00aa40ace5c;worktrees=D:/profile/research/optical-sar-visual-diagnosis               0b6f1c5 [feature/oty2-posthoc-mechanism-validation] | D:/profile/research/optical-sar-visual-diagnosis-gm017-physics aba5709 [feature/oty2-gm017-physical-factor-discovery])
- `CALIBRATION_GT_USAGE_EXPLICIT`: `PASS` (control point table exists)
- `HOLDOUT_TARGET_GT_ISOLATED`: `PASS` (validate-generate prediction rows declare target_gt_read=false)
- `CONTIGUOUS_BLOCK_SPLIT_VALID`: `PASS` (cal=315-360;guard=361-370;holdout=371-394)
- `GUARD_GAP_PRESENT`: `PASS` (361-370)
- `FACTOR_PARAMETERS_FROZEN`: `PASS` (d29e5be1e20f0a443ca68ba7eb03fd2a7faf7f359cb689d99b0ff4a8ec3de363)
- `HOLDOUT_PREDICTIONS_FROZEN`: `PASS` (c0186ffe0428177d809d7214e8f42b6786c8b68b134294865d74149fb773764d)
- `FROZEN_REPLAY_IDENTICAL`: `PASS` (PASS)
- `F1_COMMON_MOTION`: `PASS` (SUPPORTED)
- `F2_BACKGROUND_STABILITY`: `PASS` (SUPPORTED)
- `F3_PART_VISIBILITY`: `PARTIAL` (PARTIAL)
- `F4_SCALE_RANGE_RELATION`: `PARTIAL` (PARTIAL)
- `F5_OPTICAL_SAR_TREND`: `PARTIAL` (PARTIAL)
- `GM_RM017_PHYSICAL_FACTOR_LIBRARY_READY`: `PARTIAL` (supported=2;downgraded_or_rejected=3;evaluation_exists=True)
- `GM_RM017_DYNAMIC_MEMBERSHIP_STAGE_READY`: `NOT_READY` (final response membership/box selection explicitly out of scope)

## Frozen SHA Manifest

- `report` `9636cc4ca2ac7134efd9601c1c8738d8843d040889177696ece2e288e88cc928` `reports\oty2\oty2_wgv3_6b_p0_gm017_physical_factor_discovery_20260712.md`
- `input_provenance` `f88d0e1900e3a070a8c3915d02426833eebd82434bb01ddce7b7a0c0c8e518a5` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_input_provenance_audit_20260712.csv`
- `frame_alignment` `ce801cbc3f48a9fba6ed940b3493dfe2fc3c386ba0af7025f9e8db0b83ac2c3d` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_frame_alignment_audit_20260712.csv`
- `split_manifest` `8d01ec416e90ebab430157754d53429f9e0c69cbb7696ce5705e1cbc9d8b5fd4` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_split_manifest_20260712.csv`
- `control_points` `fd12e6ded147decb165446e1fd085ef46ee96e8510eb85ec8419aab7a2bdf67f` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_calibration_control_points_20260712.csv`
- `components` `1f91d5fd6db1699429ed6c8d1ba719eb51039b0a7e7c4aadfe3b8b29bbeafc1d` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_response_component_observations_20260712.csv`
- `motion_fit` `9181664352ab8c1d671085ab81496f458b920f6c4e6960517996ccd938ffe3da` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_motion_factor_fit_20260712.csv`
- `background_fit` `aedcb132650c152d4ff2dd6edc873220289b6aef60ea5ad67251ae14bf3d58aa` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_background_stability_fit_20260712.csv`
- `visibility_fit` `9cb618775b5f3f5e5bfd578ec2048577fd42279e4cce3a3665f842e839d638e4` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_visibility_transition_fit_20260712.csv`
- `scale_fit` `9499d601b371f1879c2024cf2d80f0db84c39d6e1522864d27aec614e1a69f08` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_scale_range_fit_20260712.csv`
- `trend_fit` `4e9fa59f6f41c534bf73e3ff9f391d6ab987b748a0978c1775e4c50a5c6d7490` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_optical_sar_trend_fit_20260712.csv`
- `frozen_params` `d29e5be1e20f0a443ca68ba7eb03fd2a7faf7f359cb689d99b0ff4a8ec3de363` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_frozen_factor_parameters_20260712.csv`
- `holdout_predictions` `c0186ffe0428177d809d7214e8f42b6786c8b68b134294865d74149fb773764d` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_holdout_factor_predictions_20260712.csv`
- `holdout_eval` `520ead1b3bba2425a45de9f746d9fe93447a3068780276ebef5f0cc26cea9a7e` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_holdout_evaluation_20260712.csv`
- `verdicts` `fd3d897c523850747339c2b1a81eaef1bb9e463f4d5ab8b1495d4e6d0257951a` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_factor_verdicts_20260712.csv`
- `counterexamples` `d04f365250f3b4cbc8d69a008c4656ec1c9764ec3ad76daf8e195079edec9b41` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_counterexamples_20260712.csv`
- `gate_integrity` `014bbf33d1c2cfc98706dc3c3548e3013496820c9f34f34ca7cc166ad86aa49b` `reports\oty2\samples\oty2_wgv3_6b_p0_gm017_gate_integrity_20260712.csv`

## Replay

- verify-replay: `PASS`
- frozen prediction sha: `c0186ffe0428177d809d7214e8f42b6786c8b68b134294865d74149fb773764d`
- replay prediction sha: `c0186ffe0428177d809d7214e8f42b6786c8b68b134294865d74149fb773764d`

## Boundary Notes

- Calibration uses GT control points explicitly. Holdout generation reads only frozen parameters and SAR gray frames.
- Holdout GT is read only by `evaluate` after `holdout_factor_predictions` exists and is SHA-recorded.
- N005 is used as an explicit non-vehicle/background counterexample, not as a runtime vehicle label.
- Metric coordinates use the audited 2308x1334 SAR grid, fan center, and existing 0.03 px-to-meter convention only for factor fitting; outputs remain SAR image-domain candidates.
