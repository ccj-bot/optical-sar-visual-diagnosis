# OTY2 WGV3.3A Visual Failure Diagnosis

Date: 20260710

## Scope

This report records Codex-side visual/mechanism diagnosis for representative WGV3.3A mismatches. It does not ask for new user frame review and does not feed conclusions back into the automatic relation rules.

## Cases

### VFAIL_001 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M002`
- auto status: `not_in_candidate_set`
- evidence frames: `9;10`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/01_GM_RM011_GM_RM011_WGV13T001_same_vehicle_candidate/frames_yolo/GM_RM011_WGV13T001_GM_RM011_WGV12TF002_000009_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/frames_yolo/GM_RM011_WGV13T002_GM_RM011_WGV12TF003_000010_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_002 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M004`
- auto status: `ambiguous_continuity`
- evidence frames: `16;18`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000013_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000014_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000015_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000016_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000017_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000018_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000019_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/02_GM_RM011_GM_RM011_WGV13T002_primary_box_review/edge_review_frames/GM_RM011_WGV12M004/GM_RM011_WGV12M004_000020_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_003 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M006`
- auto status: `ambiguous_continuity`
- evidence frames: `161;164`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000151_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000152_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000153_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000154_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000155_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000156_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000157_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/05_GM_RM011_GM_RM011_WGV13T005_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M006/GM_RM011_WGV12M006_000158_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_004 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M009`
- auto status: `ambiguous_continuity`
- evidence frames: `239;242`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/07_GM_RM011_GM_RM011_WGV13T007_same_vehicle_candidate/frames_yolo/GM_RM011_WGV13T007_GM_RM011_WGV12TF012_000239_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/08_GM_RM011_GM_RM011_WGV13T008_standalone_split/frames_yolo/GM_RM011_WGV13T008_GM_RM011_WGV12TF013_000242_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_005 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M012`
- auto status: `ambiguous_continuity`
- evidence frames: `259;260`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/10_GM_RM011_GM_RM011_WGV13T010_standalone_split/frames_yolo/GM_RM011_WGV13T010_GM_RM011_WGV12TF015_000259_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/11_GM_RM011_GM_RM011_WGV13T011_standalone_split/frames_yolo/GM_RM011_WGV13T011_GM_RM011_WGV12TF016_000260_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_006 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M013`
- auto status: `not_in_candidate_set`
- evidence frames: `264;265`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/11_GM_RM011_GM_RM011_WGV13T011_standalone_split/frames_yolo/GM_RM011_WGV13T011_GM_RM011_WGV12TF016_000264_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/frames_yolo/GM_RM011_WGV13T012_GM_RM011_WGV12TF017_000265_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_007 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M014`
- auto status: `ambiguous_continuity`
- evidence frames: `266;269`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M014/GM_RM011_WGV12M014_000265_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M014/GM_RM011_WGV12M014_000266_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M014/GM_RM011_WGV12M014_000267_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M014/GM_RM011_WGV12M014_000268_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M014/GM_RM011_WGV12M014_000269_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M014/GM_RM011_WGV12M014_000270_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

### VFAIL_008 accepted_edge_missed

- scene: `GM_RM011`
- reference edge: `GM_RM011_WGV12M015`
- auto status: `ambiguous_continuity`
- evidence frames: `270;279`
- visual evidence paths: `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000269_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000270_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000271_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000272_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000273_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000274_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000275_diagnostic_yolo26l.png;outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/12_GM_RM011_GM_RM011_WGV13T012_same_vehicle_candidate/edge_review_frames/GM_RM011_WGV12M015/GM_RM011_WGV12M015_000276_diagnostic_yolo26l.png`
- diagnosis: WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。
- mechanism layer: `standard_mot_fragmentation_or_motion_gap`
- minimal cross-scene fix: `add post-MOT stitch candidate evidence, not identity truth`

## Representative Visual Spot-Checks

These checks were made after automatic relation decisions and WGV1.4 posthoc mapping were frozen. They do not change thresholds or feed back into automatic relation construction.

### VFAIL_001 GM_RM011_WGV12M002

- inspected frames: `9;10`
- visual judgment: 画面 000009/000010 中主体是同一辆白色车辆的相邻可见片段，但检测框从偏局部的侧窗/车身框切换到更大主体框。视觉上可以接受同车后验解释；自动层失败在标准 MOT 片段切分和框尺度变化，不能把该后验边直接升级成运行时同车消息。
- runtime implication: keep the edge as posthoc visual evidence unless a future automatic competitor/partial-box mechanism recovers it cross-scene.

### VFAIL_004 GM_RM011_WGV12M009

- inspected frames: `239;242`
- visual judgment: 画面 000239/000242 位于桥下近景，存在两辆白色车辆、局部车头和同帧竞争对象。源片段和目标片段都可能落在白车局部外观上，但仅靠自动 MOT 与框运动无法安全裁决主体是否相同；失败层是多车竞争、边缘局部框和后验视觉裁决缺口。
- runtime implication: keep the edge as posthoc visual evidence unless a future automatic competitor/partial-box mechanism recovers it cross-scene.

## Summary

The recurring failure is not lack of YOLO26l detections alone. It is standard MOT/geometry association plus incomplete automatic competitor, subject-switch, edge-truncation, and visual adjudication evidence.
