# OTY2 P0 Data Asset and Hard-Sync Audit (20260713)

## 1. 执行结论

- P0 最终状态：`P0_DATA_FOUNDATION_PARTIALLY_READY`。
- 三个场景的可用完整编号帧目录均已建立逐文件 SHA-256 manifest；源目录只读，未移动、重命名、覆盖或复制原始资产。
- 光学/SAR 编号连续性：`clean`；SAR 灰度与伪彩按场景的编号集合一一对应：`true`。
- 三场景光学源 MP4 均为 `24` fps，SAR 灰度源 MP4 均为 `50` fps，且抽查帧与 PNG 解码结果逐像素完全一致；固定帧率已由源容器元数据确认。共同起始仍缺少公共时钟/采集日志证明。
- GM_RM011/017 的 SAR 伪彩源 MP4 为 50 fps；GM_RM019 伪彩源 `GM_RM019_R.MP4` 的容器元数据为约 48.300063 fps，虽与 766 张伪彩 PNG 逐像素对应，但和同场景 50 fps 灰度源存在时间元数据冲突。硬同步以 SAR 灰度源 50 fps 为准。
- 因此已生成确定性的全帧时间轴/配对结果，但它们的 `assumption_status=UNFROZEN_COMMON_START_ASSUMPTION_FPS_CONFIRMED_FROM_SOURCE_MP4_METADATA`：固定帧率已确认，共同起始假设未冻结。
- 当前可访问 canonical review/GT 表为 `442` 行，而不是 231 行；没有找到独立 231 行资产。旧表中的光学帧号与 `round(sar_frame * 24/50)` 完全一致，因此旧表是该比例的实现证据，不是独立验证证据。
- 已定位产生当前 PNG 序列的源 MP4 容器；仍未找到三个场景对应的原始 ADC/IQ、距离压缩结果、复数成像结果、采集配置、成像配置或有效成像 Mask。SAR MP4/PNG 是已有成像产品，不能冒充原始雷达数据。
- P0 尚不具备冻结条件；本轮不允许进入 P1。

## 2. 已确认的数据事实

| scene | optical frames | SAR gray | SAR pseudocolor | optical dimensions | SAR gray dimensions | SAR pseudocolor dimensions |
| --- | ---: | ---: | ---: | --- | --- | --- |
| GM_RM011 | 368 | 766 | 766 | 800x600: 368 | 2308x1334: 766 | 2308x1334: 766 |
| GM_RM017 | 368 | 766 | 766 | 800x600: 368 | 2308x1334: 766 | 2308x1334: 766 |
| GM_RM019 | 368 | 766 | 766 | 800x600: 368 | 2308x1334: 766 | 2308x1334: 766 |

- 文件名均以零填充数字帧号开头；P0 使用该数字作为目录内 frame index。
- 文件系统时间只反映文件落盘/复制状态，不作为采集时间戳。
- `configs/scene_config.yaml` 是本地路径路由配置，不是采集配置或成像配置。
- `review_queue.csv` 和 `final_gt_working.csv` 是稀疏标注/审阅资产，不是完整光学流或完整 SAR 流。

## 3. 当前采用的工作假设

- `same_scene_optical_frame_0_and_sar_frame_0_share_acquisition_start`。这是工作假设，不是已确认事实。
- 候选比例配置：`optical_fps=24`, `sar_fps=50`, `sar/optical=2.083333333`。
- 不使用每样本软同步分数、不使用逐帧自适应 offset、不使用 GT 反向调整同步关系。

## 4. 各场景资产总表

| scene | role | source directory | count | index range | format | bytes | source/derived interpretation |
| --- | --- | --- | ---: | --- | --- | ---: | --- |
| GM_RM011 | optical_frame | D:\profile\research\data\GM_RM011\GM_RM011_frames | 368 | 0..367 | .png:368 | 207013863 | available source optical frame sequence; original capture container unresolved |
| GM_RM011 | sar_gray_frame | D:\profile\research\data\GM_RM011\GM_RM011_SARframes_gray | 766 | 0..765 | .png:766 | 2313168185 | derived SAR imaging product; complex/range-compressed source unresolved |
| GM_RM011 | sar_pseudocolor_frame | D:\profile\research\data\GM_RM011\GM_RM011_SARframes | 766 | 0..765 | .png:766 | 2652576709 | derived display product; exact transform lineage unresolved |
| GM_RM011 | depth_array | D:\profile\research\data\GM_RM011\GM_RM011_depth | 368 | 0..367 | .npy:368 | 706607104 | derived optical depth sidecar |
| GM_RM011 | depth_visualization | D:\profile\research\data\GM_RM011\GM_RM011_depth | 368 | 0..367 | .png:368 | 29825085 | derived optical depth visualization |
| GM_RM017 | optical_frame | D:\profile\research\data\GM_RM017\GM_RM017_frames | 368 | 0..367 | .png:368 | 189604532 | available source optical frame sequence; original capture container unresolved |
| GM_RM017 | sar_gray_frame | D:\profile\research\data\GM_RM017\GM_RM017_SARframes_gray | 766 | 0..765 | .png:766 | 2410413539 | derived SAR imaging product; complex/range-compressed source unresolved |
| GM_RM017 | sar_pseudocolor_frame | D:\profile\research\data\GM_RM017\GM_RM017_SARframes | 766 | 0..765 | .png:766 | 2730909098 | derived display product; exact transform lineage unresolved |
| GM_RM017 | depth_array | D:\profile\research\data\GM_RM017\GM_RM017_depth | 368 | 0..367 | .npy:368 | 706607104 | derived optical depth sidecar |
| GM_RM017 | depth_visualization | D:\profile\research\data\GM_RM017\GM_RM017_depth | 368 | 0..367 | .png:368 | 50085747 | derived optical depth visualization |
| GM_RM019 | optical_frame | D:\profile\research\data\GM_RM019\GM_RM019_frames | 368 | 0..367 | .png:368 | 221783221 | available source optical frame sequence; original capture container unresolved |
| GM_RM019 | sar_gray_frame | D:\profile\research\data\GM_RM019\GM_RM019_SARframes_gray | 766 | 0..765 | .png:766 | 2239389965 | derived SAR imaging product; complex/range-compressed source unresolved |
| GM_RM019 | sar_pseudocolor_frame | D:\profile\research\data\GM_RM019\GM_RM019_SARframes | 766 | 0..765 | .png:766 | 2071115015 | derived display product; exact transform lineage unresolved |
| GM_RM019 | depth_array | D:\profile\research\data\GM_RM019\GM_RM019_depth | 368 | 0..367 | .npy:368 | 706607104 | derived optical depth sidecar |
| GM_RM019 | depth_visualization | D:\profile\research\data\GM_RM019\GM_RM019_depth | 368 | 0..367 | .png:368 | 56320491 | derived optical depth visualization |

命名规则与直接源容器：

- 光学帧：`000000.png` ... `000367.png`，直接源为 `<scene>_C.MP4`。
- SAR 灰度帧：`000000.png` ... `000765.png`，直接源为 `<scene>_0_R_1.MP4`。
- SAR 伪彩帧：`000000.png` ... `000765.png`；GM_RM011/017 直接源为 `<scene>_0_R.MP4`，GM_RM019 直接源为 `GM_RM019_R.MP4`。
- Depth array/visualization：`<frame>_depth.npy` 与 `<frame>_depth_vis.png`，均为光学帧派生。
- 对每个源容器抽查 frame 0、100、last，解码像素与对应 PNG 完全一致。

资产 manifest 还记录了源 MP4 容器，并以 placeholder/reference rows 明确记录未找到的 ADC/IQ、距离压缩、复数成像、采集配置、成像配置和 Mask，而不是静默省略。

## 5. 光学和 SAR 完整帧范围

| scene | optical range | optical count | SAR gray range | SAR gray count | SAR pseudocolor range | SAR pseudocolor count | count ratio |
| --- | --- | ---: | --- | ---: | --- | ---: | ---: |
| GM_RM011 | 0..367 | 368 | 0..765 | 766 | 0..765 | 766 | 2.081521739 |
| GM_RM017 | 0..367 | 368 | 0..765 | 766 | 0..765 | 766 | 2.081521739 |
| GM_RM019 | 0..367 | 368 | 0..765 | 766 | 0..765 | 766 | 2.081521739 |

## 6. 缺失、重复和异常资产

- GM_RM011 `optical_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM011 `sar_gray_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM011 `sar_pseudocolor_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM011 `depth_array`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM011 `depth_visualization`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM017 `optical_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM017 `sar_gray_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM017 `sar_pseudocolor_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM017 `depth_array`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM017 `depth_visualization`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM019 `optical_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM019 `sar_gray_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM019 `sar_pseudocolor_frame`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM019 `depth_array`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- GM_RM019 `depth_visualization`: missing indices=none; duplicate indices=0; duplicate-content rows=0; dimension outliers=0.
- 原始 ADC/IQ：三个场景均未在已配置 scene roots 或仓库引用中定位到。
- 距离压缩/中间成像：三个场景均未定位到可证明 lineage 的资产。
- 复数成像结果：三个场景均未定位到。
- 采集配置/成像配置：三个场景均未定位到；仓库 scene config 仅为路径配置。
- 有效成像 Mask：未定位到独立 Mask 文件，也未找到足以冻结的 Mask 语义。

## 7. 实际或候选帧率

- 实际源容器证据：三场景 optical `_C.MP4` 均为 `24` fps / 368 帧；三场景 SAR gray `_0_R_1.MP4` 均为 `50` fps / 766 帧。
- 对每个已归类源视频抽查 frame 0、100、last，解码像素与对应 PNG 完全相同，因此可确认这些 MP4 是当前帧目录的直接源容器。
- SAR pseudocolor：GM_RM011/017 源容器为 50 fps；GM_RM019 源容器为约 48.300063 fps。该冲突不改变灰度 SAR 50 fps 硬同步基准，但必须在后续 lineage 修复前保留为 blocker。
- 源容器帧率并不证明多个设备共享同一时钟或 frame 0 真正同时开始。
- 候选名义持续时间：光学 `368/24=15.333333333s`；SAR `766/50=15.320000000s`；差 `0.013333333s`。
- 最后一个样本时间：光学 `367/24=15.291666667s`；SAR `765/50=15.300000000s`。SAR 最后一帧比光学最后一帧晚 `0.008333333s`。

## 8. 共同起始硬同步是否自洽

- 固定帧率不再只是脚本常量：源 MP4 容器确认 optical=24 fps、SAR gray=50 fps；编号连续，三场景帧数一致，旧表也精确采用最近帧换算，因此共同起始假设内部自洽。
- 共同起始本身仍未被独立时间戳、采集日志或硬件同步记录证实；旧配对不能作为独立验证，因为旧配对本身由相同比例生成。

## 9. 全帧配对结果

- `oty2_p0_hard_sync_sar_to_optical.csv` 覆盖每一张 SAR 灰度帧，给出确定性的左右光学帧及插值比例。
- `oty2_p0_hard_sync_optical_to_sar.csv` 按光学帧半开时间区间确定性地划分全部 SAR 灰度帧。
- 所有行标记为 `UNFROZEN_COMMON_START_ASSUMPTION_FPS_CONFIRMED_FROM_SOURCE_MP4_METADATA`。已建立确定性配对，但尚未冻结为经公共时钟证实的真实配对。

## 10. 与现有 231 样本配对的差异

- 未找到独立 231 行 GT/review 或 pair table。当前 canonical review queue 为 `442` 行；final GT 位于 `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`。
- canonical 行数包含同一帧对上的多车辆/多标注，因此 annotation row count 不等于 frame-pair count。
- 与确定性最近帧规则的逐场景对照：
  - GM_RM011: rows=201, unique frame pairs=82, SAR range=0..510, optical range=0..245, exact `round(sar*24/50)` rows=201/201.
  - GM_RM017: rows=216, unique frame pairs=79, SAR range=302..446, optical range=145..214, exact `round(sar*24/50)` rows=216/216.
  - GM_RM019: rows=25, unique frame pairs=20, SAR range=0..354, optical range=0..170, exact `round(sar*24/50)` rows=25/25.
- 当前表与完整流的差异来自稀疏选样和同一帧对上的重复标注行；可访问表中没有不同起点 offset 或不同 scale。
- 因 231 行资产缺失，无法判断其精确抽样、裁剪或版本关系。

## 11. 当前仍缺少的数据或日志

1. 证明共同起始的场景采集配置、公共时钟或同步日志。
2. 逐帧时间戳或公共 clock log。
3. 原始 ADC/IQ 位置和不可变 acquisition manifest。
4. 距离压缩、复数成像中间结果位置及 lineage。
5. 伪彩变换定义，以及 GM_RM019 伪彩 MP4 48.300063 fps 与灰度 50 fps 冲突的解释。
6. 唯一 SAR 米制坐标、有效成像 Mask 和 Mask 语义。
7. 独立 231 行 review/pair 资产，或确认 231 已过时/写错。

## 12. P0 是否具备冻结条件

否。当前状态为 `P0_DATA_FOUNDATION_PARTIALLY_READY`：编号图像产品与固定帧率已完成审计，但共同起始证明、原始雷达 lineage、GM_RM019 伪彩时间元数据冲突和 Mask 语义尚未冻结。

## 13. 是否允许进入 P1

`no`。P0 达到 `P0_DATA_FOUNDATION_READY` 前不得进入 P1。

## 14. 本轮没有运行的内容

- 未运行任何光学 detector 或 tracker（ByteTrack、BoT-SORT、OC-SORT 等）。
- 未更新 Working Graph，未做多车身份合并。
- 未拟合方位向映射。
- 未生成 SAR candidate，未运行 Gate、selector、ranking 或 GT 驱动选框。
- 未运行 GM_RM017 物理因素、SAR 结构动力学、训练、阈值调优或自动标注。
- 未写入、移动、重命名、复制源资产，未操作 stash。

## Audit provenance

- review queue: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv`
- final GT: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`
- hash algorithm: `SHA-256` for every discovered file; no hash shortcut used.
- fps evidence status: `confirmed`；共同起始仍为工作假设。
