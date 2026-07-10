# OTY2 WGV3.4A Visual Path Diagnosis

Date: 20260710

Codex opened optical frames and SAR path overlays for the cases below. PNG overlays are ignored by Git and are not committed.

## WGV34A_EVAL_VP_001 posthoc_vehicle_present_evaluation

- Optical contact sheet: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/WGV34A_EVAL_VP_001_optical_contact.png`
- Visual basis: 0-25帧主要是近场右侧白车，画面从侧窗、车门到前机盖/前挡风局部裁切连续变化；M003附近多个框仍指向同一辆车的不同可见部分。

## WGV34A_EVAL_VP_002 posthoc_vehicle_present_evaluation

- Optical contact sheet: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/WGV34A_EVAL_VP_002_optical_contact.png`
- Visual basis: 231-288帧主要跟随桥下右侧近场白车，经历车窗、车顶、车尾和局部裁切变化；289-292帧转为左侧白色SUV。

## WGV34A_EVAL_COMPLEX_001 complex_competition_evaluation

- Optical contact sheet: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/WGV34A_EVAL_COMPLEX_001_optical_contact.png`
- Visual basis: 135-137帧是白车、黑车和覆盖车辆并列的竞争场景；151-166帧转为右边缘白车的稳定但强截断/边缘接触段。

## WGV34A_EVAL_NEG_001 trusted_negative_evaluation

- Optical contact sheet: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/WGV34A_EVAL_NEG_001_optical_contact.png`
- Visual basis: foreground dominated by fence/vegetation/covered structure; distant bridge-side car-like objects remain a caveat

## WGV34A_EVAL_NEG_002 trusted_negative_evaluation

- Optical contact sheet: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/WGV34A_EVAL_NEG_002_optical_contact.png`
- Visual basis: foreground dominated by fence/vegetation and motorbike/scooter; no clear foreground car in the optical search direction

### VIS_01 WGV34A_EVAL_VP_001 WGV34A_PATH_0000044

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_01_WGV34A_PATH_0000044.png`
- 中文判断：路径位于 R1，方位 -41.9946 到 -41.9817 deg，径向像素 146 到 146；持续 2 帧，状态为 insufficient_length。持续不足3帧，不能作为稳定连续结构。存在 2 个分支竞争候选，不能排除换接。方位速度中位数 0.0129 deg/frame，径向速度中位数 0 px/frame；方位/径向加速度中位数分别为 0/0，方向反转 0 次。平均重叠 1，形状一致性 1，局部对比 4.63，静态背景重叠 0.431。与保守负例相比，该片段没有形成稳定可分离的车辆存在证据。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_02 WGV34A_EVAL_VP_001 WGV34A_PATH_0001518

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_02_WGV34A_PATH_0001518.png`
- 中文判断：路径位于 R1，方位 -41.9946 到 -41.9817 deg，径向像素 146 到 146；持续 2 帧，状态为 insufficient_length。持续不足3帧，不能作为稳定连续结构。存在 2 个分支竞争候选，不能排除换接。方位速度中位数 0.0129 deg/frame，径向速度中位数 0 px/frame；方位/径向加速度中位数分别为 0/0，方向反转 0 次。平均重叠 1，形状一致性 1，局部对比 4.63，静态背景重叠 0.431。与保守负例相比，该片段没有形成稳定可分离的车辆存在证据。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_03 WGV34A_EVAL_VP_002 WGV34A_PATH_0001230

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_03_WGV34A_PATH_0001230.png`
- 中文判断：路径位于 R2，方位 -12.5 到 -12.5 deg，径向像素 392.0616 到 391.8867；持续 2 帧，状态为 insufficient_length。持续不足3帧，不能作为稳定连续结构。未见显著分支竞争。方位速度中位数 0 deg/frame，径向速度中位数 -0.1749 px/frame；方位/径向加速度中位数分别为 0/0，方向反转 0 次。平均重叠 1，形状一致性 1，局部对比 6.52，静态背景重叠 0.431。与保守负例相比，该片段没有形成稳定可分离的车辆存在证据。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_04 WGV34A_EVAL_VP_002 WGV34A_PATH_0003078

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_04_WGV34A_PATH_0003078.png`
- 中文判断：路径位于 R2，方位 -12.5 到 -12.5 deg，径向像素 392.0616 到 391.8867；持续 2 帧，状态为 insufficient_length。持续不足3帧，不能作为稳定连续结构。未见显著分支竞争。方位速度中位数 0 deg/frame，径向速度中位数 -0.1749 px/frame；方位/径向加速度中位数分别为 0/0，方向反转 0 次。平均重叠 1，形状一致性 1，局部对比 6.52，静态背景重叠 0.431。与保守负例相比，该片段没有形成稳定可分离的车辆存在证据。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_05 WGV34A_EVAL_COMPLEX_001 WGV34A_PATH_0002502

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_05_WGV34A_PATH_0002502.png`
- 中文判断：路径位于 R3，方位 -48.9758 到 -45.0485 deg，径向像素 610 到 594；持续 8 帧，状态为 physically_consistent_short_path。满足固定策略下的单向短路径条件，但仍只是局部SAR响应片段。存在 1 个分支竞争候选，不能排除换接。方位速度中位数 0.4901 deg/frame，径向速度中位数 -2 px/frame；方位/径向加速度中位数分别为 -0.4929/0，方向反转 1 次。平均重叠 0.75，形状一致性 1，局部对比 7.77，静态背景重叠 0.384。该窗口存在多车、遮挡或主体切换，响应不能唯一归因到单一车辆。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_06 WGV34A_EVAL_NEG_001 WGV34A_PATH_0006658

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_06_WGV34A_PATH_0006658.png`
- 中文判断：路径位于 R0，方位 -2.1052 到 -2.3603 deg，径向像素 45.2679 到 44.6862；持续 9 帧，状态为 static_structure_path。与固定/近固定背景高度重叠，更像道路、护栏、桥梁边缘或固定亮脊线散射。存在 12 个分支竞争候选，不能排除换接。方位速度中位数 0.00655 deg/frame，径向速度中位数 0.0058 px/frame；方位/径向加速度中位数分别为 -0.04475/-0.0121，方向反转 5 次。平均重叠 1，形状一致性 1，局部对比 3.03，静态背景重叠 1。该窗口本身是保守负例/结构控制，仍出现高响应片段，说明PNG域响应并非车辆存在特异。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_07 WGV34A_EVAL_NEG_001 WGV34A_PATH_0006670

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_07_WGV34A_PATH_0006670.png`
- 中文判断：路径位于 R0，方位 -15.4713 到 -15.4559 deg，径向像素 48.6115 到 48.5066；持续 2 帧，状态为 insufficient_length。持续不足3帧，不能作为稳定连续结构。存在 2 个分支竞争候选，不能排除换接。方位速度中位数 0.0154 deg/frame，径向速度中位数 -0.1049 px/frame；方位/径向加速度中位数分别为 0/0，方向反转 0 次。平均重叠 1，形状一致性 1，局部对比 4.05，静态背景重叠 1。该窗口本身是保守负例/结构控制，仍出现高响应片段，说明PNG域响应并非车辆存在特异。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_08 WGV34A_EVAL_NEG_002 WGV34A_PATH_0003417

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_08_WGV34A_PATH_0003417.png`
- 中文判断：路径位于 R0，方位 49.6716 到 51.5581 deg，径向像素 106.8948 到 118；持续 5 帧，状态为 recurrent_background_path。具有重复背景位置压力，更像反复出现的背景响应。存在 6 个分支竞争候选，不能排除换接。方位速度中位数 0.6276 deg/frame，径向速度中位数 2.836 px/frame；方位/径向加速度中位数分别为 0.4308/-0.1347，方向反转 1 次。平均重叠 0.75，形状一致性 1，局部对比 6.27，静态背景重叠 0.426。该窗口本身是保守负例/结构控制，仍出现高响应片段，说明PNG域响应并非车辆存在特异。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。

### VIS_09 WGV34A_EVAL_NEG_002 WGV34A_PATH_0006810

- SAR overlay: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/visual_exemplars/wgv3_4a_20260710/wgv3_4a_path_review_09_WGV34A_PATH_0006810.png`
- 中文判断：路径位于 R0，方位 49.6716 到 51.5581 deg，径向像素 106.8948 到 118；持续 5 帧，状态为 recurrent_background_path。具有重复背景位置压力，更像反复出现的背景响应。存在 6 个分支竞争候选，不能排除换接。方位速度中位数 0.6276 deg/frame，径向速度中位数 2.836 px/frame；方位/径向加速度中位数分别为 0.4308/-0.1347，方向反转 1 次。平均重叠 0.75，形状一致性 1，局部对比 6.27，静态背景重叠 0.426。该窗口本身是保守负例/结构控制，仍出现高响应片段，说明PNG域响应并非车辆存在特异。因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。
