# OTY2 WGV3.5A-R1 Physical Vehicle Identity Audit

Date: 20260710

## Boundary

This audit treats ByteTrack IDs as track hypotheses, not physical identity truth. SAR GT remains posthoc validation evidence only.

## Frozen WGV3.5A Baseline SHA256

| source_file | sha256 | bytes | rows |
| --- | --- | --- | --- |
| reports/oty2/oty2_wgv3_5a_pair_and_depth_audit_20260710.md | 3e929ada8518476c6cbd999aa5ae9a02a22f9a60bf1368ed1496aaca32523cc4 | 3253 |  |
| reports/oty2/oty2_wgv3_5a_visual_feasible_field_diagnosis_20260710.md | b981e9337bac30f000bebb7b0c4a3db3793aab7c7a98d6499e455785c8b0524e | 18038 |  |
| reports/oty2/oty2_wgv3_5a_weak_physical_projection_closure_20260710.md | f2bfeb65712f1c43077eb5c4a89f6162a32dacdf0dd388e0019a77f2a9ca7c8e | 6924 |  |
| reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv | 54c558f1308629f4be349dedf9618803b8b3d99eed845dffa370c47d7ec9203d | 98642 | 204 |
| reports/oty2/samples/oty2_wgv3_5a_sar_polar_targets_20260710.csv | d5da737d9d260f5cb0de24c0af4d7327999022a0d2cdb1fd417729419497a330 | 23783 | 204 |
| reports/oty2/samples/oty2_wgv3_5a_optical_vehicle_states_20260710.csv | bdff06bd75f748f84a023caddf50312fc793646eb76d5f7113a6e97ea565fba2 | 69268 | 204 |
| reports/oty2/samples/oty2_wgv3_5a_identity_safe_split_20260710.csv | 4b7648b894fc45d6f92ebfbf1ad335c05dda3c536f76abb30aa3da67d408f9fc | 2249 | 9 |
| reports/oty2/samples/oty2_wgv3_5a_azimuth_calibration_20260710.csv | a645fc0b5f5806b2b29dccc056a13fcdde191c48f73fa9974713eccd139a9867 | 1100 | 5 |
| reports/oty2/samples/oty2_wgv3_5a_radial_calibration_20260710.csv | ff80eabbd505ebbab4dab1c04b74d92af0c736ff610928c67978db4c1557413d | 943 | 4 |
| reports/oty2/samples/oty2_wgv3_5a_failure_cases_20260710.csv | f767785c164b416d7814da38584c6c1ad4a80b8440a6e1e166ae5babd9f76252 | 4349 | 13 |

## Source Thread Counts

| track_id | pair_count |
| --- | --- |
| oty1t_obj_GM_RM017_bytetrack_bt_0008 | 61 |
| oty1t_obj_GM_RM017_bytetrack_bt_0010 | 72 |
| oty1t_obj_GM_RM017_bytetrack_bt_0012 | 52 |
| oty1t_obj_GM_RM017_bytetrack_bt_0014 | 3 |

## Physical Vehicle Map

| physical_vehicle_id | source_track_ids | optical_frame_start | optical_frame_end | same_vehicle_relation | same_vehicle_confidence | evidence | conflict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM17_DARK_FOLLOW | oty1t_obj_GM_RM017_bytetrack_bt_0012 | 162 | 210 | same_physical_vehicle | 0.9 | dark sedan following the white SUV; visible from left to right across frames 162-210 | co-occurs with 0010 and 0014 in frame 184, so it is not the same vehicle as those tracks |
| PV_GM17_DARK_LEAD_CANDIDATE | oty1t_obj_GM_RM017_bytetrack_bt_0008;oty1t_obj_GM_RM017_bytetrack_bt_0014 | 145 | 212 | same_physical_vehicle | 0.65 | dark leading/right-edge vehicle; 0008 exits at the right edge by frame 181-182 and 0014 appears near the same edge from frame 184 | 0014 is only a small edge fragment and remains a candidate continuation of 0008, not a training/test identity truth |
| PV_GM17_WHITE_SUV | oty1t_obj_GM_RM017_bytetrack_bt_0010 | 151 | 189 | same_physical_vehicle | 0.95 | white SUV; appears as the middle vehicle across frames 151-189; co-occurs with dark vehicles | none for 0010 as a single physical vehicle; not independent from same-scene traffic context |
| PV_REL_0010_VS_0012 | oty1t_obj_GM_RM017_bytetrack_bt_0010;oty1t_obj_GM_RM017_bytetrack_bt_0012 | 162 | 189 | overlapping_different_vehicles | 0.98 | same frames show a white SUV and a separate dark sedan at different image positions | none |
| PV_REL_0012_VS_0014 | oty1t_obj_GM_RM017_bytetrack_bt_0012;oty1t_obj_GM_RM017_bytetrack_bt_0014 | 184 | 184 | overlapping_different_vehicles | 0.98 | frame 184 contains both track boxes simultaneously: 0012 on the left dark sedan, 0014 at the far right edge | none |
| PV_REL_0008_VS_0014 | oty1t_obj_GM_RM017_bytetrack_bt_0008;oty1t_obj_GM_RM017_bytetrack_bt_0014 | 181 | 184 | same_physical_vehicle | 0.65 | right-edge dark vehicle continuity from 0008 exit to 0014 fragment is plausible | 0014 fragment is too small for a hard identity claim |

## Same-Frame Evidence

- same-frame multi-track frames: `38`
- Visual audit overlay: `outputs/wgv3_5a_r1_20260710/frame_overlap_contact_sheet.png`
- Direct inspection shows a white SUV and at least two dark sedans co-existing in the GM_RM017 sequence.
- 0010 and 0012 are overlapping different physical vehicles; 0012 and 0014 are also different in frame 184.
- 0008 and 0014 are a plausible right-edge continuation, but confidence is only moderate because 0014 is a small fragment.

## WGV3.5A Leakage Decision

No hard 0010-vs-0012 same-vehicle leakage was found, but the WGV3.5A split is not a physical-vehicle-generalization proof: train/validation/test are same-scene, same-time traffic phases with overlapping vehicles. R1 therefore uses observation-state mechanism analysis rather than split-based generalization claims.
