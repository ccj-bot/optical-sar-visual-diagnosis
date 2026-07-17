# OTY2-RSA0-R2 SAR 响应表示管线逐层取证审计契约

日期：`2026-07-17`

英文名称：`OTY2-RSA0-R2 Layer-by-Layer Forensic Audit of the SAR Response Representation Pipeline`

分支：`feature/oty2-sar-gt-structure-foundation`

冻结起始 HEAD：`2a1feea580b076b6c2f81571b72f3bc2db4a455f`

解释器：`D:/MINICONDA/envs/py311/python.exe`

Git 外输出根：`D:/profile/research/workspace/output/oty2_rsa0_r2_20260717`

## 1. 唯一目标与禁止范围

本轮只从原始 SAR PNG 开始，对 RSA0-R1 的输入、坐标变换、图像变换、通道、几何采样、统计汇总和正式结论进行逐层取证，定位第一处科学语义偏离。

本轮禁止种子传播、对象记忆、VOS、模型训练、新响应恢复算法、生命周期、跨场景自动重放、S1-D 事件、通道融合、新阈值搜索、候选排序、winner 或最终框。`SAR GT` 只允许作为研究期坐标和事后审计依据，不得进入部署推理或自动生成响应 Mask。

本文件是实验前契约。完成 docs-only 提交与推送后，不得为了迎合结果静默改写。新事实只能进入 Phase A findings、Phase B fix record 或独立 addendum。

## 2. 冻结审计样本

主审计帧：

- `GM_RM017:PV002 / SAR 339`：强响应，主带明显，竖线与扇形弧交叉；
- `GM_RM017:PV003 / SAR 384`：弱响应，optical proxy drift 最大。

连续小窗：

- PV002：`337–341`；
- PV003：`380–384`。

只有上述两帧和两个小窗逐层账本、点追踪、证据卡和视觉核查完成后，才允许检查扩展帧 `PV002 330/344` 与 `PV003 360/372`。

## 3. 已读取并冻结的现状来源

语义与历史来源：

- `docs/OTY2_RSA0_GLOBAL_ROUTE_RESET_AND_RESEARCH_CONTRACT.md`；
- `docs/OTY2_RSA0_FAILURE_LESSONS_AND_NON_NEGOTIABLES.md`；
- `docs/OTY2_RSA0_VISIBLE_RESPONSE_OBJECT_SEMANTICS.md`；
- `docs/OTY2_RSA0_R1_TEMPLATE_ATLAS_CORRECTION_ADDENDUM.md`；
- `reports/oty2/oty2_rsa0_r1_representation_reaudit_20260717.md`。

R1 实现与产物来源：

- `tools/diagnostics/run_oty2_rsa0_r1_free_geometry_reaudit.py`；
- `tools/diagnostics/run_oty2_rsa0_build_visual_review_pack.py`；
- `configs/oty2/oty2_rsa0_r1_free_geometry_atlas.json`；
- atlas v1 frames/regions/skeletons/background/freeze/consistency manifests；
- `manifests/oty2/oty2_rsa0_r1_representation_channel_metrics.csv`；
- `manifests/oty2/oty2_rsa0_r1_coordinate_family_summary.csv`；
- `manifests/oty2/oty2_rsa0_r1_proxy_drift.csv`；
- `D:/profile/research/workspace/output/oty2_rsa0_20260717/visual_review_pack`；
- `D:/profile/research/workspace/output/oty2_rsa0_r1_20260717/response_atlas_review_v1`。

坐标、扇区与运输来源：

- `docs/OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md`；
- `docs/OTY2_S1LR_GM_RM017_MOTION_COHERENT_VISIBLE_RESPONSE_FLOW_PROTOCOL.md`；
- `docs/OTY2_S1LR2_GM_RM017_COMMON_SCENE_TRANSPORT_AND_LOCAL_RESPONSE_ORGANIZATION_PROTOCOL.md`；
- `tools/diagnostics/oty2_s1x_common.py`；
- `tools/diagnostics/run_oty2_s1x_joint_temporal_support.py`；
- `tools/diagnostics/run_oty2_s1d0_dynamic_response.py`；
- `tools/diagnostics/run_oty2_s1lr2_gm_rm017_common_scene_transport_and_local_response.py`。

## 4. R1 实际执行链

```text
SAR PNG
→ cv2.IMREAD_UNCHANGED 像素解码
→ read_gray() 取第 0 通道并强制 uint8
→ review-only display_u8() 的 0..85 截断显示
→ imaging_valid_mask / GT center / optical proxy / S1D0 scene transport 参考
→ R1 三个被命名的 coordinate family 分支
→ 单帧 channels_for()
→ 原始显示栈 temporal_maps()
→ manual_annotations() + GT-center local_to_global()
→ polygon_mask()/polyline_mask()
→ sample_values()
→ skeleton/background/unresolved 统计与 auc_score()
→ family median / hit-rate / failure_mode
→ 排序后的 top-18 与固定 formal-answer 文本
→ freeze manifest / summary / validator
```

R2 必须保留一条并列的“应有链”，不得用名称替代实现：

```text
SAR PNG
→ 原始解码数组与灰度标量数组
→ 固定有效扇区与有效源像素 Mask
→ RAW / WORLD / GT-ALIGNED / OPTICAL-PROXY-ALIGNED 独立完整连续栈
→ 每个栈分别重算单帧与时间通道
→ 同步变换后的 atlas geometry 与逐点坐标
→ 原始值、各归一化值和实际 mask 采样值
→ 精确/均匀/空间分层 AUC 与背景 subtype 结果
→ 可回溯到数组、像素、图像和逻辑条件的结论
```

## 5. 逐层现状账本与验证契约

### S00 原始 PNG 解码

- 实际函数：`cv2.imread(path, cv2.IMREAD_UNCHANGED)`，随后 `oty2_s1x_common.read_gray()`。
- 输入文件：`manifests/oty2/oty2_s1x_optical_condition_frames.csv::sar_gray_path` 指向的 `GM_RM017_SARframes_gray/*.png`。
- 输入数组：OpenCV 原始解码当前为 `shape=(1334,2308,3)`、`dtype=uint8`；`read_gray()` 取 `image[:,:,0]`，输出 `shape=(1334,2308)`、`dtype=uint8`。
- 已冻结抽查：SAR 339 原始范围 `0..250`，SAR 384 原始范围 `0..253`。
- 坐标系：`sar_display_px`，`x` 向右、`y` 向下。
- 输出：原始三通道数组、标量灰度数组、源文件 SHA256。
- 后续消费者：visual pack、R1 runner、所有变换与通道。
- 当前假设：三个 PNG 通道等价；取第 0 通道不丢失语义。
- 潜在错误：通道并非严格一致、PNG mapping 未记录、把显示产品误叫原始雷达幅度。
- R2 验证：逐帧记录通道相等性、shape、dtype、全量统计、有效扇区统计、源哈希；保存原始解码与标量数组 NPZ。

### S01 显示域截断

- 实际函数：R1 overlay 的 `display_u8(image)` 等价于 `clip(image/85,0,1)*255`；visual pack 使用冻结 `display_min=0, display_max=85`。
- 输入：S00 标量灰度数组，`shape=(1334,2308)`、`uint8`、范围约 `0..255`。
- 输出：`uint8` 显示图，范围 `0..255`；大于等于 85 的输入饱和。
- 后续消费者：人工 review PNG/MP4；R1 `channels_for()` 本身使用未做 0..85 截断的标量数组。
- 已冻结抽查：有效扇区内饱和比例 SAR 339 为 `0.002329`，SAR 384 为 `0.000510`。
- 当前假设：0..85 截断只改善审阅，不改变结构解释。
- 潜在错误：审阅图中的亮结构宽度和相对强度被饱和改变；报告把 review appearance 与通道输入混写。
- R2 验证：同时输出原始 0..255、0..85 截断、固定窗口显示和差异/饱和 Mask。

### S02 固定扇区与黑区

- 实际函数：`oty2_s1x_common.imaging_valid_mask()`。
- 参数：origin `(1154.0,1330.6)`，radius `1332.7 px`，theta `[-90,90] deg`。
- 输出：`shape=(1334,2308)`、`dtype=bool`，像素数 `2,628,412`，画布占比 `0.8536931707456497`，packed-bit SHA256 `7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef`。
- 已冻结抽查：有效扇区内零值比例 SAR 339 为 `0.289706`，SAR 384 为 `0.290144`；全画布零值比例约 `0.3924..0.3930`。
- 当前 R1 使用：通道归一化、percentile threshold、ridge threshold、AUC 默认没有排除扇区外像素；世界变换也没有传播独立有效源 Mask。
- 潜在错误：无效黑区和变换黑边进入分位数、阈值、背景与统计。
- R2 验证：分别保留 `imaging_valid_mask`、`display_nonzero_mask`、经验固定黑区、变换有效源 Mask；所有统计声明使用哪一种 Mask。

### S03 坐标参考输入

- GT 输入：`oty2_s0_sar_gt_quality_audit.csv::bbox`，由 `parse_rotated_bbox()` 读取中心与尺寸。
- optical proxy 输入：`oty2_s1x_optical_condition_frames.csv::predicted_center_x_px/predicted_center_y_px`。
- world transport 输入：`oty2_s1d0_causal_transport_diagnostics.csv::cumulative_dx_px/cumulative_dy_px`，R1 `transport_map()` 只按 `scene` 和 `state_mode=causal` 选择。
- atlas 输入：`manual_annotations()` 中的 GT-center-relative 点，经 `local_to_global()` 变为 `sar_display_px`。
- 当前假设：GT center、proxy center 和 scene transport 能直接构成三个可比较 coordinate family。
- 潜在错误：中心参考、图像重采样、geometry 移动与时间重计算被混为同一“坐标族”；R1 名称可能超出实际操作。
- R2 验证：为每个参考记录来源行、哈希、坐标定义、正向矩阵、逆矩阵、点闭合误差和图像有效域。

### S04 `RAW_SAR_DISPLAY`

- 应实现：原图不变、geometry 不变、连续原始帧栈不变；所有单帧和时间通道在该栈上独立计算。
- R1 对应现状：不存在该诚实名称；R1 `GT_CONDITIONED_RESEARCH_ORACLE` 实际使用 `raw_image + raw temporal maps + unwarped shapes`，最接近 RAW，而不是真正 GT-aligned stack。
- R2 验证：把 RAW 作为显式基线，禁止再以 GT-conditioned 名称代替。

### S05 `WORLD_STABILIZED_IMAGE_STACK`

- R1 实际函数：`warp_translation(raw_image, shift_x, shift_y, INTER_LINEAR)`，其中 `shift=-(transport(frame)-transport(frame_start))`；geometry 使用同一平移。
- R1 输入/输出：单帧 `uint8 (1334,2308)`；边界 `BORDER_CONSTANT=0`；没有独立变换有效源 Mask 进入归一化。
- R1 实际时间行为：只对当前关键帧重算 `channels_for(stabilized_image)`；`SAR_DISPLAY_WORLD_STABILIZED` 没有任何 temporal channel，R1 metrics 中只有 11 个单帧通道。
- 潜在错误：名称暗示世界稳定时间表示，但时间通道缺失；黑边可进入全图 robust01；只看运输 CSV 不能证明背景稳定。
- R2 验证：对连续小窗每帧应用同一场景逆运输，生成完整 stack、geometry stack 与 valid-source stack，在该 stack 上重算全部时间通道；至少三处冻结背景点做前后可视化和残差。

### S06 `GT_ALIGNED_RESEARCH_STACK`

- R1 实际操作：`raw_image` 不变；atlas geometry 保持在原始显示坐标；原始显示 temporal maps 被附加；没有按逐帧 GT 中心重采样连续图像。
- R1 visual pack 仅以 `crop_center(disp, gt_center)` 形成 GT-centered crop montage/average；该 crop stack 没有被 R1 representation runner 消费。
- 因此 R1 `GT_CONDITIONED_RESEARCH_ORACLE` 是命名超前，不能视作真实 GT-aligned image stack。
- R2 应实现：把每帧 GT center 映射到冻结参考中心，图像、atlas geometry、有效源 Mask 同步变换；中心对齐和可选方向对齐必须分开；再重算全部时间通道。
- R2 验证：正逆闭合、同一点变换前后局部 patch、像素值与 Mask IoU；所有产物标记 `RESEARCH_ORACLE_COORDINATE_ONLY`。

### S07 `OPTICAL_PROXY_ALIGNED_STACK`

- R1 实际操作：图像仍为 `raw_image`；atlas geometry 按 `proxy-GT drift` 平移；原始显示 temporal maps 被复用。
- 该操作实际是 `OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING`：只移动 geometry，不移动图像。
- R1 visual pack 的 proxy-aligned montage只是以 proxy center 裁剪，不等于 representation runner 中的完整重采样 stack。
- 潜在错误：把定位误差采样结果解释为 proxy-aligned 坐标表示能力。
- R2 应实现并分开报告：
  - `OPTICAL_PROXY_ALIGNED_STACK`：图像、geometry、有效源 Mask 同步重采样后重算时间通道；
  - `OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING`：原图不动、只移动 geometry，专门测量 proxy drift。

### S08 单帧通道

- 实际函数：`channels_for(image)`。
- 输入：`float32 (1334,2308)`，来自当前 family 的单帧图。
- 通道：raw、31×31 local contrast/local z、sigma 9 highpass、Sobel x/y、gradient magnitude、双尺度 Laplacian-like bright ridge、structure-tensor coherence、radial/tangential gradient projection。
- 当前归一化：每个通道立即调用 `robust01()`，在全图所有有限像素上逐帧取 2%/98% 分位数并裁剪到 `[0,1]`；未保存原始浮点通道。
- 潜在错误：黑区参与分位数、每帧缩放制造可比性、Hessian 名称与公式不完全等价、方向通道受 fan origin 与图像 y 方向定义影响。
- R2 验证：每个通道同时保存 raw float、current full-frame robust01、valid-fan robust01、scene-frozen normalization、local matched normalization；生成真实图像与合成图的语义卡。

### S09 fan radial/tangential 几何

- R1 实际原点：`cx=image_width/2=1154.0`、`cy=image_height-3.4=1330.6`。
- 上游冻结依据：S0 coordinate contract 明确给出相同 origin `(1154.0,1330.6)`；R1 数值一致，但实现没有来源引用或运行时一致性断言。
- R1 公式：radial unit vector 从 fan origin 指向像素；tangential vector 为 `(-radial_y, radial_x)`；对 Sobel 梯度投影后取绝对值。
- 潜在错误：数值来源不可追溯、方向名称被误读为线条走向而实际响应的是法向梯度、黑区边界产生强梯度。
- R2 验证：候选 origin/来源/公式/非零边界误差写入 fan audit；原图叠加径向线、切向圆弧、扇区边界和 atlas；合成水平线、竖线与圆弧验证。

### S10 时间通道

- 实际函数：`temporal_maps(images, frame, half_window)`，使用原始显示连续帧字典。
- 输入：`stack=(N,1334,2308)`、`float32`，半窗 `2` 与 `4`，边界裁剪。
- 输出：median/max/min/MAD、相邻帧 positive/negative、per-pixel temporal 75th-percentile frequency、x-gradient sign persistence、per-frame 80th-percentile high-intensity occurrence frequency。
- 当前命名错误：`temporal_w*_local_component_continuity` 没有连通部件、关联或 component ID，只是高亮像素出现频率。
- 当前 coordinate 错误：GT/proxy family 复用 RAW temporal maps；WORLD family 没有 temporal maps。
- R2 验证：诚实改名为 `temporal_high_intensity_pixel_frequency`；每个独立 stack 重算全部时间通道；保存 stack、raw 输出、归一化输出和脉冲/平移/恒定图合成测试。

### S11 atlas geometry 与 mask

- 实际来源：R1 runner 内硬编码 `manual_annotations()`，以 GT center-relative 点存储，再由 `local_to_global()` 转到 `sar_display_px`。
- 实际 mask：polygon 用 `cv2.fillPoly`；skeleton/seed/background 用 `cv2.polylines`，thickness 分别为 3/3/5，`LINE_AA` 后转 bool。
- 输入：atlas v1 skeletons/regions/background manifests 与代码内 annotation；图像 shape `(1334,2308)`。
- 输出：skeleton、seed、definite、background、unresolved bool Mask。
- 当前假设：人工点落在真实响应；consistency CSV 中的 `skeleton_inside...`、`definite_covers_dark_areas`、`background_controls...` 可代表实际审阅。
- 潜在错误：一致性布尔值在 runner 中直接写死；mask thickness 和抗锯齿扩大采样；R1 没有逐点 patch 账本。
- R2 验证：每个关键帧输出无 overlay、单类 overlay、全 overlay、每个点 21×21 patch；逐点赋予 `CONFIRMED/MINOR_OFFSET/WRONG_STRUCTURE/SEMANTICALLY_AMBIGUOUS`，不静默修改 v1。

### S12 通道采样

- 实际函数：`sample_values(channel, mask)`。
- 输入：已 robust01 的 `[0,1] float32` 通道与 bool Mask。
- 输出：按 NumPy 行优先顺序展平的采样值。
- 后续消费者：median、coverage、ridge distance、AUC、background activation。
- 潜在错误：只保留归一化值；不同 subtype 混合；geometry-only shift 被当坐标表示；无效源像素与黑边可能进入。
- R2 验证：保存每个 mask 的像素坐标、raw channel value、各 normalization value、valid-source 状态、background subtype 和最终 conclusion 使用关系。

### S13 frame-level 指标与 AUC

- coverage：以当前通道全图 90/95 分位阈值计算 skeleton coverage。
- ridge distance：把全图 90 分位以上像素当 ridge，距离变换后取 skeleton 中位距离。
- frame hit：`skeleton_p90_coverage > 0.25`；seed hit：`>0.34`。
- AUC：`auc_score()` 先按展平顺序截取正负各前 3000 个像素，再构造两两比较。
- 潜在错误：空间顺序偏差、全图黑区影响 threshold、背景 subtype 被合并、单阈值替代多证据。
- R2 验证：规模允许时精确 Mann–Whitney/rank AUC；固定随机种子均匀抽样；空间分层抽样；vertical line/fan arc/hotspot/clutter/unresolved 分开报告；比较三种方法差异。

### S14 family summary 与 failure label

- 实际聚合：按 `case_id, coordinate_family, channel` 对关键帧的 `skeleton_minus_background_median` 取中位数；hit 取均值；background activation 取均值。
- 实际 failure label：中位 separation `<0.03` 为 `background_competes_with_target`，否则 `skeleton_signal_retained`。
- 潜在错误：单一 `0.03` 门把弱/强帧、背景 subtype、ridge distance、坐标族依赖和反例压成一个标签。
- R2 验证：分别报告 skeleton separation/hit、weak/strong hit、background subtype activation、ridge distance、跨帧一致性、坐标族依赖；不做加权总分或统一 PASS。

### S15 正式文字结论

- 实际生成：family rows 按 median separation 降序，报告前 18 行；七条 formal answers 是 runner 内固定模板文字。
- 潜在错误：固定文字可能超出实际数组能力；“GT-conditioned”“proxy-conditioned”“world-stabilized temporal”名称与实现不一致；top-18 排序掩盖反例。
- R2 验证：每条正式结论必须进入 conclusion lineage，引用具体 stage、数组、帧、点/像素、可视化、逻辑条件、反例和证据等级。没有 lineage 的文字不得进入正式报告。

## 6. 必须建立的 Git 内账本

### 6.1 数组血缘

`manifests/oty2/oty2_rsa0_r2_array_lineage.csv`

字段固定为：

```text
case_id,frame,stage_id,variable_name,source_file,source_sha256,
coordinate_system,shape,dtype,minimum,maximum,mean,median,p02,p50,
p75,p80,p90,p95,p98,zero_fraction,finite_fraction,
valid_fan_fraction,output_npz_path,output_sha256
```

大型 NPZ 留在 Git 外；manifest 与哈希进 Git。

### 6.2 逐点追踪

`manifests/oty2/oty2_rsa0_r2_point_trace.csv`

每个主审计帧至少选择 skeleton 左/中/右、seed 中点、竖线背景点、弧线背景点、unresolved 点、GT center、proxy center。每个点记录所有坐标、正逆闭合、图内/扇区/有效源状态、原始灰度、raw/normalized 通道值、mask 成员和 conclusion 使用关系。

### 6.3 fan geometry

`manifests/oty2/oty2_rsa0_r2_fan_geometry_audit.csv`

记录候选 origin、来源、公式、有效角度/半径、非零边界误差、与 S0/S1-LR2/S1X 的一致性。

### 6.4 atlas 点审计

`manifests/oty2/oty2_rsa0_r2_atlas_point_audit.csv`

只允许 `CONFIRMED`、`MINOR_OFFSET`、`WRONG_STRUCTURE`、`SEMANTICALLY_AMBIGUOUS`。发现问题只写 correction proposal，不修改 atlas v1。

### 6.5 结论血缘

`manifests/oty2/oty2_rsa0_r2_conclusion_lineage.csv`

每条结论必须有文本、依赖 stage/file/metric/frame/visualization、逻辑条件、反例和证据等级。

## 7. 证据卡契约

路径：`D:/profile/research/workspace/output/oty2_rsa0_r2_20260717/evidence_cards`

每个 stage 至少包含输入图与坐标、公式/矩阵、输出图、差异图、数值范围、关键点变换、预期、实际观察、`PASS/FAIL/UNRESOLVED` 和原因。每张卡必须同时显示 atlas skeleton、background controls、GT center、proxy center、fan origin、有效扇区边界、运输向量、实际变换点和有效源 Mask；只给灰度热图无效。

## 8. 变换验证门

每个 transform 必须通过：

1. 图像与 geometry 同步：同一点变换前后仍落在相同局部结构；
2. 正逆闭合：point error、mask IoU、image reconstruction error；
3. 插值与边界：插值方法、填充值、有效源 Mask、黑边比例及其是否进入归一化；
4. 世界稳定：337–341 与 380–384 各至少三个固定背景点的前后 patch、轨迹和残差；
5. geometry-only 实验必须显式命名 `LOCALIZATION_ERROR_SAMPLING`。

## 9. 归一化审计门

每个通道至少比较：

- 当前全图逐帧 2%–98%；
- 有效扇区逐帧 2%–98%；
- 从独立背景/预冻结样本得到的场景固定范围；
- 局部车辆邻域与匹配背景范围。

同一物理点在全部方案下必须逐值对照。不得依据正响应 atlas 调冻结范围。

## 10. 合成测试门

必须覆盖：水平亮线、竖直亮线、已知圆弧、全场平移静态线、目标相对背景运动、单帧亮度脉冲、恒定图像。每项保存输入、理论预期、实际数组、误差与 PASS/FAIL。合成测试只验证公式和实现，不证明真实图像科学语义。

## 11. Phase A 与 Phase B

Phase A 只审计，不修复。必须先冻结完整 findings、哈希、可视化和结论血缘。

Phase B 只允许修复已由 Phase A 证据确认的实现错误，例如：图像/geometry 不同步、world stack 缺时间通道、proxy-aligned 定义错误、fan origin 实现错误、无效黑区进入归一化、AUC 顺序偏差、指标命名错误、结论门与指标不一致。

每项修复必须记录修复前证据、代码原因、最小补丁、合成测试、修复后证据以及是否改变科学结论。禁止为提高指标调阈值、改 atlas、发明融合或进入传播。

## 12. 正式报告限制

正式报告只回答八个问题：原始 PNG；坐标变换；首次错位 stage；三个真实坐标栈的时间含义；通道高值结构；归一化/采样偏差；R1 结论保留/撤回/不可判定；修复后是否具备传播设计基础。

每个回答必须引用具体帧、stage、数组、点/像素和可视化路径。validator PASS、文件数、均值或 commit 状态不得替代科学核查。

## 13. 停止条件

只有在主帧与连续小窗的所有坐标变换、同步关系、三种真实对齐 stack、fan origin、raw/normalized channel、至少两个 skeleton 点与两个 background 点、归一化、AUC、合成测试和 conclusion lineage 全部有证据时，才允许扩展帧和结束本轮。

本轮最终许可默认为：

```text
NEXT_PROPAGATION_DESIGN=NOT_AUTHORIZED_UNTIL_R2_EVIDENCE_CLOSES_ALL_REQUIRED_GATES
```
