# OTY2 WGV3.5A-R2B GM_RM019 Full-Stream Anchor Re-Audit

Date: 20260710

## Boundary

R2B keeps original R2 as a paired-row-only anchor audit. It does not overwrite R2 and does not run GM_RM011 or R4.

## Freeze Manifest

| source_file | sha256 | bytes | rows |
| --- | --- | --- | --- |
| reports/oty2/oty2_wgv3_5a_r1_closure_20260710.md | a1e8ea691d5a4ce77af94c889a5f25793ae87cea3fd31f0f191d020649523163 | 11085 |  |
| reports/oty2/oty2_wgv3_5a_r2_gm019_closure_20260710.md | 7584cfbe78d392446adcc34f313c7bef2b5e99dd7c947f0a0b5a69f5d4ec19c1 | 7199 |  |
| reports/oty2/oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_20260710.md | cf79ef60e3f700149c19347bd929089862acd01d5c9395abc01445923e1809cd | 14686 |  |
| reports/oty2/samples/oty2_wgv3_5a_r1_observation_state_audit_20260710.csv | 963d41fa69deec7da491f1fd3911b2288e319acf38568944566cc16fcc8defa9 | 71814 | 188 |
| reports/oty2/samples/oty2_wgv3_5a_r1_complete_vehicle_baseline_20260710.csv | 6175d85260702a5b1b2dccb0ef8c64dbb8d9da15b9439f8450cdd9b1b1a2ea22 | 2595 | 8 |
| reports/oty2/samples/oty2_wgv3_5a_r2_gm019_observation_states_20260710.csv | 19b1a10a6a82b3a5001aa520bffd9e57b32c83d5ba732fd2e0bfb5dbae155d98 | 9056 | 16 |
| reports/oty2/samples/oty2_wgv3_5a_r2_gm019_projection_comparison_20260710.csv | 0cb77de2c912106e0960ed241892c8c0c4ed61ebaaae0c8ee8190446cc82ebd5 | 1509 | 11 |

## Full-Stream Source Inventory

| source_name | source_path | frame_count | detection_count | track_count | coordinate_size | confidence_available | bbox_available | identity_available | usable_for_full_stream_reconstruction | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM019全部光学帧 | D:\profile\research\data\GM_RM019\GM_RM019_frames | 368 |  |  | 800x600 | false | false | false | visual_audit_only | 现有16条配对行覆盖帧0;2;4;13;15;37;39;102;114;129;131;138-139;151-152 |
| GM_RM019相对深度 | D:\profile\research\data\GM_RM019\GM_RM019_depth | 368 |  |  | 800x600 | false | false | false | depth_quality_audit | 深度只作为相对弱证据，不作为米制距离或硬控制器 |
| YOLO11l归一化检测 | outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM019_yolo11l_baseline_normalized_detection_table.csv | 193 | 334 |  | 800x600 | true | true | false | true | R2B does not treat tracker ids as physical identity truth |
| YOLO26l归一化检测 | outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM019_yolo26l_probe_normalized_detection_table.csv | 193 | 288 |  | 800x600 | true | true | false | true | R2B does not treat tracker ids as physical identity truth |
| YOLO26l ByteTrack全流线程 | outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM019_yolo26l_probe_bytetrack_raw/oty1t_tracker_state_timeseries.csv | 167 | 194 | 15 | 800x600 | false | true | hypothesis | true | R2B does not treat tracker ids as physical identity truth |
| YOLO26l BoT-SORT全流线程 | outputs/oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000/GM_RM019_yolo26l_probe_botsort_raw/oty1t_tracker_state_timeseries.csv | 170 | 200 | 14 | 800x600 | false | true | hypothesis | true | R2B does not treat tracker ids as physical identity truth |
| WGV3.3A自动线程节点 | reports/oty2/samples/oty2_wgv3_3a_auto_tracklet_nodes_20260710.csv | 49 | 53 | 85 | 800x600 | false | true | hypothesis | cross_check | R2B does not treat tracker ids as physical identity truth |
| WGV1.4节点映射 | reports/oty2/samples/oty2_wgv3_3a_wgv1_4_node_mapping_20260710.csv |  | 32 | 9 | 800x600 | true | false | hypothesis | cross_check | R2B does not treat tracker ids as physical identity truth |
| WGV3.3A线程关系审计 | reports/oty2/samples/oty2_wgv3_3a_auto_relation_decisions_20260710.csv |  | 274 |  | 800x600 | false | false | hypothesis | cross_check | R2B does not treat tracker ids as physical identity truth |

## Physical Vehicle Timeline

| physical_vehicle_id | source_track_ids | all_observation_frames | paired_frames | unpaired_frames | first_visible_frame | last_visible_frame | simultaneous_vehicle_conflict | same_vehicle_evidence | different_vehicle_evidence | identity_confidence | identity_blocked_interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | bytetrack:bt_0001;botsort:bs_0001;botsort:bs_0002 | 0-11 | 0;2;4 | 1;3;5-11 | 0 | 11 | none | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.9 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | bytetrack:bt_0003;botsort:bs_0003 | 5-27;29-41 | 13;15;37;39 | 5-12;14;16-27;29-36;38;40-41 | 5 | 41 | none | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.9 |  |
| PV_GM19_RIGHT_DARK_FRAGMENT | bytetrack:bt_0004;botsort:bs_0002 | 12-14 | 13 | 12;14 | 12 | 14 | frame 13 simultaneous with PV_GM19_WHITE_SUV_NEAR_FIELD | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.55 | single short fragment; not merged for recovery |
| PV_GM19_UNPAIRED_SMALL_044_049 | bytetrack:bt_0016 | 44-49 |  | 44-49 | 44 | 49 | none | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.65 | unpaired small distant vehicle; not used for GM_RM019 SAR evaluation |
| PV_GM19_UNPAIRED_SMALL_060_080 | bytetrack:bt_0033 | 60-80 |  | 60-80 | 60 | 80 | none | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.65 | unpaired small distant vehicle; not used for GM_RM019 SAR evaluation |
| PV_GM19_UNPAIRED_SMALL_083_098 | bytetrack:bt_0053 | 83-98 |  | 83-98 | 83 | 98 | none | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.65 | unpaired small distant vehicle; not used for GM_RM019 SAR evaluation |
| PV_GM19_SILVER_MPV_NEAR_FIELD | bytetrack:bt_0068;botsort:bs_0065 | 99-140 | 102;114;129;131;138-139 | 99-101;103-113;115-128;130;132-137;140 | 99 | 140 | small duplicate/overlap fragments exist in neighboring tracker rows | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.9 |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | bytetrack:bt_0078;botsort:bs_0072;botsort:bs_0074 | 149-182 | 151-152 | 149-150;153-182 | 149 | 182 | small duplicate/overlap fragments exist in neighboring tracker rows | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.9 |  |
| PV_GM19_UNPAIRED_SMALL_259_261 | bytetrack:bt_0090 | 259-261 |  | 259-261 | 259 | 261 | none | continuous optical motion and appearance inside assigned full-stream track | kept separate when simultaneous, appearance, or scale is inconsistent | 0.65 | unpaired small distant vehicle; not used for GM_RM019 SAR evaluation |

## Direct Observable Full-Stream Search

- paired-row direct observable count: `0`
- full optical stream direct observable count: `22`
- full optical stream answer: 原R2的0个完整锚点只是在配对行内为0；完整光学时序内为`22`。

| physical_vehicle_id | frame | source_detector | source_track_id | bbox | hard_edge_state | soft_edge_state | visible_front | visible_rear | visible_side | whole_body_confidence | depth_quality | direct_observable_full_stream | direct_observable_reason | paired_with_sar | cross_detector_support |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 0 | yolo26l_probe | bt_0001 | 123.223,342.616,705.465,598.302 | bottom_contact | bottom_near_edge | true | false | true | 0.66 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0 | true | yolo11l:iou=0.708;yolo26l:iou=1 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 1 | yolo26l_probe | bt_0001 | 172.014,347.161,744.78,598.597 | bottom_contact | bottom_near_edge | true | false | true | 0.66 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.091 | false | yolo11l:iou=0.897;yolo26l:iou=0.751 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 2 | yolo26l_probe | bt_0001 | 220.345,356.585,772.313,598.682 | bottom_contact | bottom_near_edge | true | false | true | 0.66 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.182 | true | yolo11l:iou=0.879;yolo26l:iou=0.86 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 3 | yolo26l_probe | bt_0001 | 257.156,365.314,788.479,598.221 | bottom_contact | right_near_edge;bottom_near_edge | true | false | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.273 | false | yolo11l:iou=0.958;yolo26l:iou=0.985 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 4 | yolo26l_probe | bt_0001 | 295.429,374.187,804.489,597.669 | right_contact | right_near_edge;bottom_near_edge | true | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.364 | true | yolo11l:iou=0.957;yolo26l:iou=0.959 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 5 | yolo26l_probe | bt_0001 | 328.249,385.319,809.084,596.822 | right_contact | right_near_edge;bottom_near_edge | true | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.455 | false | yolo11l:iou=0.954;yolo26l:iou=0.949 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 6 | yolo26l_probe | bt_0001 | 352.329,386.261,826.59,596.532 | right_contact | right_near_edge;bottom_near_edge | true | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.545 | false | yolo11l:iou=0.867;yolo26l:iou=0.874 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 7 | yolo26l_probe | bt_0001 | 368.297,380.83,847.785,596.569 | right_contact | right_near_edge;bottom_near_edge | true | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.636 | false | yolo11l:iou=0.782;yolo26l:iou=0.788 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 8 | yolo26l_probe | bt_0001 | 380.091,369.42,873.772,596.832 | right_contact | right_near_edge;bottom_near_edge | false | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.727 | false | yolo11l:iou=0.684;yolo26l:iou=0.686 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 9 | yolo26l_probe | bt_0001 | 388.948,346.413,900.708,589.829 | right_contact | right_near_edge;bottom_near_edge | false | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.818 | false | yolo11l:iou=0.585;yolo26l:iou=0.583 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 10 | yolo26l_probe | bt_0001 | 397.373,322.76,924.938,583.832 | right_contact | right_near_edge;bottom_near_edge | false | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.909 | false | yolo11l:iou=0.517;yolo26l:iou=0.515 |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 11 | yolo26l_probe | bt_0001 | 427.737,329.573,933.272,591.162 | right_contact | right_near_edge;bottom_near_edge | false | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=1 | false | yolo11l:iou=0.45;yolo26l:iou=0.456 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 5 | yolo26l_probe | bt_0003 | 10.559,336.835,78.186,516.065 | none | left_near_edge | true | false | true | 0.53 | depth_edge_mixed_risk | false | not_direct_full_stream;无硬边缘接触;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=false;phase_ok=false;phase=0 | false | yolo11l:iou=0.68;yolo26l:iou=0.692 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 6 | yolo26l_probe | bt_0003 | 22.344,333.28,96.164,526.226 | none | left_near_edge | true | false | true | 0.53 | depth_edge_mixed_risk | false | not_direct_full_stream;无硬边缘接触;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=false;phase_ok=false;phase=0.028 | false | yolo11l:iou=0.557;yolo26l:iou=0.563 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 7 | yolo26l_probe | bt_0003 | 33.651,326.493,115.219,534.278 | none | none | true | false | true | 0.85 | depth_vehicle_region_usable | false | not_direct_full_stream;无硬边缘接触;多检测源支持;深度区域可用;width_ok=false;height_ok=false;phase_ok=false;phase=0.056 | false | yolo11l:iou=0.514;yolo26l:iou=0.521 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 8 | yolo26l_probe | bt_0003 | 44.12,316.744,134.471,538.081 | none | none | true | false | true | 0.97 | depth_vehicle_region_usable | false | not_direct_full_stream;无硬边缘接触;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=false;height_ok=true;phase_ok=false;phase=0.083 | false | yolo11l:iou=0.486;yolo26l:iou=0.491 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 9 | yolo26l_probe | bt_0003 | 50.079,297.836,156.542,547.698 | none | none | true | false | true | 0.97 | depth_vehicle_region_usable | false | not_direct_full_stream;无硬边缘接触;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=false;height_ok=true;phase_ok=false;phase=0.111 | false | yolo11l:iou=0.495;yolo26l:iou=0.494 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 10 | yolo26l_probe | bt_0003 | 53.942,280.806,176.923,556.321 | none | none | true | false | true | 0.97 | depth_vehicle_region_usable | false | not_direct_full_stream;无硬边缘接触;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=false;height_ok=true;phase_ok=false;phase=0.139 | false | yolo11l:iou=0.518;yolo26l:iou=0.523 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 11 | yolo26l_probe | bt_0003 | 60.264,279.049,201.092,577.992 | none | none | true | false | true | 0.97 | depth_vehicle_region_usable | false | not_direct_full_stream;无硬边缘接触;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=false;height_ok=true;phase_ok=false;phase=0.167 | false | yolo11l:iou=0.511;yolo26l:iou=0.515 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 12 | yolo26l_probe | bt_0003 | 73.628,293.432,225.943,593.091 | none | bottom_near_edge | true | false | true | 0.7 | depth_edge_mixed_risk | false | not_direct_full_stream;无硬边缘接触;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=false;phase=0.194 | false | yolo11l:iou=0.489;yolo26l:iou=0.481 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 13 | yolo26l_probe | bt_0003 | 90.881,308.063,253.913,598.662 | bottom_contact | bottom_near_edge | true | false | true | 0.48 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=false;phase=0.222 | true | yolo11l:iou=0.451;yolo26l:iou=0.452 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 14 | yolo26l_probe | bt_0003 | 108.587,326.366,281.792,600.265 | bottom_contact | bottom_near_edge | true | false | true | 0.4 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;高度接近轨迹主体;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=true;phase=0.25 | false |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 15 | yolo26l_probe | bt_0003 | 128.513,345.559,314.05,600.553 | bottom_contact | bottom_near_edge | true | false | true | 0.4 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;高度接近轨迹主体;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=true;phase=0.278 | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 16 | yolo26l_probe | bt_0003 | 137.421,353.602,341.811,600.173 | bottom_contact | bottom_near_edge | true | false | true | 0.4 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;高度接近轨迹主体;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=true;phase=0.306 | false |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 17 | yolo26l_probe | bt_0003 | 132.892,346.853,365.154,599.747 | bottom_contact | bottom_near_edge | true | false | true | 0.48 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=true;phase=0.333 | false | yolo26l:iou=0.468 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 18 | yolo26l_probe | bt_0003 | 119.298,329.197,387.792,600.426 | bottom_contact | bottom_near_edge | true | true | true | 0.48 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:bottom_contact;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=true;phase=0.361 | false | yolo11l:iou=0.476;yolo26l:iou=0.526 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 19 | yolo26l_probe | bt_0003 | 103.277,301.538,406.891,591.31 | none | bottom_near_edge | true | true | true | 0.7 | depth_edge_mixed_risk | false | not_direct_full_stream;无硬边缘接触;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=false;height_ok=true;phase_ok=true;phase=0.389 | false | yolo11l:iou=0.516;yolo26l:iou=0.578 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 20 | yolo26l_probe | bt_0003 | 94.97,264.644,433.641,572.998 | none | none | true | true | true | 1 | depth_vehicle_region_usable | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=true;height_ok=true;phase_ok=true;phase=0.417 | false | yolo11l:iou=0.536;yolo26l:iou=0.609 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 21 | yolo26l_probe | bt_0003 | 80.499,254.048,438.322,567.264 | none | none | true | true | true | 1 | depth_vehicle_region_usable | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=true;height_ok=true;phase_ok=true;phase=0.444 | false | yolo11l:iou=0.559;yolo26l:iou=0.713 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 22 | yolo26l_probe | bt_0003 | 85.771,262.307,458.602,573.757 | none | none | true | true | true | 1 | depth_vehicle_region_usable | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;深度区域可用;width_ok=true;height_ok=true;phase_ok=true;phase=0.472 | false | yolo26l:iou=0.676 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 23 | yolo26l_probe | bt_0003 | 106.661,288.441,488.699,588.375 | none | bottom_near_edge | true | true | true | 0.88 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.5 | false | yolo26l:iou=0.607 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 24 | yolo26l_probe | bt_0003 | 144.856,309.497,532.104,595.183 | none | bottom_near_edge | true | true | true | 0.88 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.528 | false | yolo26l:iou=0.626 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 25 | yolo26l_probe | bt_0003 | 222.909,319.54,620.477,596.837 | none | bottom_near_edge | true | true | true | 0.88 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.556 | false | yolo11l:iou=0.599;yolo26l:iou=0.656 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 26 | yolo26l_probe | bt_0003 | 282.33,314.008,700.031,595.605 | none | bottom_near_edge | true | true | true | 0.88 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.583 | false | yolo11l:iou=0.72;yolo26l:iou=0.74 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 27 | yolo26l_probe | bt_0003 | 294.161,303.645,737.316,594.985 | none | bottom_near_edge | true | true | true | 0.88 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.611 | false | yolo11l:iou=0.765;yolo26l:iou=0.738 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 29 | yolo26l_probe | bt_0003 | 295.131,291.24,767.825,596.831 | none | bottom_near_edge | false | true | true | 0.88 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.667 | false | yolo11l:iou=0.841;yolo26l:iou=0.854 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 30 | yolo26l_probe | bt_0003 | 305.648,291.791,781.939,596.738 | none | right_near_edge;bottom_near_edge | false | true | true | 0.72 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.694 | false | yolo11l:iou=0.885;yolo26l:iou=0.921 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 31 | yolo26l_probe | bt_0003 | 324.791,297.998,793.772,596.858 | none | right_near_edge;bottom_near_edge | false | true | true | 0.72 | depth_edge_mixed_risk | true | direct_observable_full_stream;无硬边缘接触;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.722 | false | yolo11l:iou=0.923;yolo26l:iou=0.96 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 32 | yolo26l_probe | bt_0003 | 345.967,302.289,806.166,596.263 | right_contact | right_near_edge;bottom_near_edge | false | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.75 | false | yolo11l:iou=0.969;yolo26l:iou=0.961 |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 33 | yolo26l_probe | bt_0003 | 372.324,308.414,819.095,596.343 | right_contact | right_near_edge;bottom_near_edge | false | true | true | 0.5 | depth_edge_mixed_risk | false | not_direct_full_stream;硬边缘接触:right_contact;宽度接近轨迹主体;高度接近轨迹主体;多检测源支持;depth_edge_mixed_risk;width_ok=true;height_ok=true;phase_ok=true;phase=0.778 | false | yolo11l:iou=0.904;yolo26l:iou=0.9 |

## Optical Recovery Anchors

| physical_vehicle_id | optical_frame | bbox | depth | source_detector | source_track | whole_body_confidence | identity_confidence | paired_with_sar | usable_as_optical_recovery_anchor | blocked_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 20 | 94.97,264.644,433.641,572.998 | 3.608809 | yolo26l_probe | bt_0003 | 1 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 21 | 80.499,254.048,438.322,567.264 | 3.556474 | yolo26l_probe | bt_0003 | 1 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 22 | 85.771,262.307,458.602,573.757 | 3.394538 | yolo26l_probe | bt_0003 | 1 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 23 | 106.661,288.441,488.699,588.375 | 3.182813 | yolo26l_probe | bt_0003 | 0.88 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 24 | 144.856,309.497,532.104,595.183 | 3.015966 | yolo26l_probe | bt_0003 | 0.88 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 25 | 222.909,319.54,620.477,596.837 | 2.883309 | yolo26l_probe | bt_0003 | 0.88 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 26 | 282.33,314.008,700.031,595.605 | 2.943892 | yolo26l_probe | bt_0003 | 0.88 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 27 | 294.161,303.645,737.316,594.985 | 3.042115 | yolo26l_probe | bt_0003 | 0.88 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 29 | 295.131,291.24,767.825,596.831 | 2.992193 | yolo26l_probe | bt_0003 | 0.88 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 30 | 305.648,291.791,781.939,596.738 | 3.13056 | yolo26l_probe | bt_0003 | 0.72 | 0.9 | false | true |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 31 | 324.791,297.998,793.772,596.858 | 2.88976 | yolo26l_probe | bt_0003 | 0.72 | 0.9 | false | true |  |
| PV_GM19_SILVER_MPV_NEAR_FIELD | 119 | 79.607,271.679,433.181,592.954 | 3.163009 | yolo26l_probe | bt_0068 | 0.88 | 0.9 | false | true |  |
| PV_GM19_SILVER_MPV_NEAR_FIELD | 120 | 88.141,273.072,459.949,594.522 | 3.566367 | yolo26l_probe | bt_0068 | 0.88 | 0.9 | false | true |  |
| PV_GM19_SILVER_MPV_NEAR_FIELD | 121 | 100.263,266.673,500.394,595.968 | 3.697172 | yolo26l_probe | bt_0068 | 0.88 | 0.9 | false | true |  |
| PV_GM19_SILVER_MPV_NEAR_FIELD | 122 | 113.596,264.769,535.282,597.055 | 4.006345 | yolo26l_probe | bt_0068 | 0.88 | 0.9 | false | true |  |
| PV_GM19_SILVER_MPV_NEAR_FIELD | 123 | 145.219,263.611,584.931,596.945 | 3.658923 | yolo26l_probe | bt_0068 | 0.88 | 0.9 | false | true |  |
| PV_GM19_SILVER_MPV_NEAR_FIELD | 124 | 203.63,262.285,660.492,597.641 | 3.491174 | yolo26l_probe | bt_0068 | 0.88 | 0.9 | false | true |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | 170 | 153.156,303.095,587.54,597.888 | 2.018886 | yolo26l_probe | bt_0078 | 0.88 | 0.9 | false | true |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | 171 | 231.702,297.764,685.647,597.487 | 2.085166 | yolo26l_probe | bt_0078 | 0.88 | 0.9 | false | true |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | 172 | 258.316,297.215,725.41,597.894 | 2.018554 | yolo26l_probe | bt_0078 | 0.88 | 0.9 | false | true |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | 173 | 297.65,299.152,766.247,597.692 | 1.743712 | yolo26l_probe | bt_0078 | 0.88 | 0.9 | false | true |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | 174 | 320.016,304.315,784.172,597.609 | 1.720499 | yolo26l_probe | bt_0078 | 0.72 | 0.9 | false | true |  |

## SAR Scene Calibration Anchors

| pair_id | physical_vehicle_id | optical_frame | sar_frame | optical_state_source | direct_or_recovered | state_confidence | usable_as_scene_calibration_anchor | blocked_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WGV35A_PAIR_0200 | PV_GM19_BLACK_SEDAN_NEAR_FIELD | 0 | 0 | anchorless_track_level_completion | Z1B | 0.66 | false | low_confidence_or_not_high_confidence_pair |
| WGV35A_PAIR_0201 | PV_GM19_BLACK_SEDAN_NEAR_FIELD | 2 | 4 | anchorless_track_level_completion | Z1B | 0.66 | false | low_confidence_or_not_high_confidence_pair |
| WGV35A_PAIR_0202 | PV_GM19_BLACK_SEDAN_NEAR_FIELD | 4 | 8 | anchorless_track_level_completion | Z1B | 0.5 | false | low_confidence_or_not_high_confidence_pair |
| WGV35A_PAIR_0203 | PV_GM19_RIGHT_DARK_FRAGMENT | 13 | 27 |  | blocked | 0 | false | insufficient_temporal_extent |
| WGV35A_PAIR_0204 | PV_GM19_WHITE_SUV_NEAR_FIELD | 13 | 27 | optical_recovery_anchor_interpolation | Z1A | 0.611111 | true |  |
| WGV35A_PAIR_0205 | PV_GM19_WHITE_SUV_NEAR_FIELD | 15 | 31 | optical_recovery_anchor_interpolation | Z1A | 0.722222 | true |  |
| WGV35A_PAIR_0206 | PV_GM19_WHITE_SUV_NEAR_FIELD | 37 | 77 | optical_recovery_anchor_interpolation | Z1A | 0.48 | true |  |
| WGV35A_PAIR_0207 | PV_GM19_WHITE_SUV_NEAR_FIELD | 39 | 81 | optical_recovery_anchor_interpolation | Z1A | 0.4 | false | low_confidence_or_not_high_confidence_pair |
| WGV35A_PAIR_0208 | PV_GM19_SILVER_MPV_NEAR_FIELD | 102 | 212 | anchorless_track_level_completion | Z1B | 0.72 | true |  |
| WGV35A_PAIR_0209 | PV_GM19_SILVER_MPV_NEAR_FIELD | 114 | 238 | optical_recovery_anchor_interpolation | Z1A | 0.635556 | true |  |
| WGV35A_PAIR_0210 | PV_GM19_SILVER_MPV_NEAR_FIELD | 129 | 269 | optical_recovery_anchor_interpolation | Z1A | 0.635556 | true |  |
| WGV35A_PAIR_0211 | PV_GM19_SILVER_MPV_NEAR_FIELD | 131 | 273 | optical_recovery_anchor_interpolation | Z1A | 0.537778 | true |  |
| WGV35A_PAIR_0212 | PV_GM19_SILVER_MPV_NEAR_FIELD | 138 | 288 | anchorless_track_level_completion | Z1B | 0.35 | false | low_confidence_or_not_high_confidence_pair |
| WGV35A_PAIR_0213 | PV_GM19_SILVER_MPV_NEAR_FIELD | 139 | 290 | anchorless_track_level_completion | Z1B | 0.35 | false | low_confidence_or_not_high_confidence_pair |
| WGV35A_PAIR_0214 | PV_GM19_GRAY_CAR_LEFT_EDGE | 151 | 315 | anchorless_track_level_completion | Z1B | 0.72 | true |  |
| WGV35A_PAIR_0215 | PV_GM19_GRAY_CAR_LEFT_EDGE | 152 | 317 | anchorless_track_level_completion | Z1B | 0.7 | true |  |
