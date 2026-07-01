# OTY1 跨场景结论与建议

日期：2026-07-01

## 1. 当前主线状态

OTY 当前已经形成两层 runtime-safe 输入：

1. OTY0：raw optical frames -> YOLO detections。
2. OTY1：YOLO detections -> optical tracklet candidate / optical state stream。

这仍然不是自动标注完成态，也不是 SAR band。OTY1 没有做 SAR 对齐、SAR GT coverage、selector、G2、A008 scoring、阈值调参、training 或 annotation proposal。

## 2. 场景结果

| scene | optical frames | YOLO detection rows | frames with detections | OTY1 candidate edges | within-limit edges | tracklet candidates | ambiguous tracklets | fragmented short tracks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GM_RM019 | 368 | 334 | 193 | 1612 | 1367 | 54 | 24 | 30 |
| GM_RM017 | 368 | 215 | 100 | 1050 | 916 | 10 | 6 | 4 |

GM_RM017 已经补上 OTY0/OTY1。它在 SAR 侧是重要场景，但 OTY 这条线仍然只能把它作为 optical temporal stream 审计对象；SAR 证据和 SAR GT 后续只能进入 posthoc 或 OTY2+ 之后的边界化审计。

## 3. 关于 GM_RM019 tracklet_0039 / tracklet_0045

`oty1_tracklet_0039` 和 `oty1_tracklet_0045` 很可能应该进入同目标 fragment-merge review：

- 0039 覆盖 frame 162-172，0045 覆盖 frame 171-183。
- 两者在 frame 171/172 附近发生 bbox 形态切换。
- `GM_RM019_000172_002 -> GM_RM019_000173_001` 是强候选边：center distance 约 71.6px，IoU 约 0.534，size consistency 约 0.586。
- 当前 OTY1 未合并，是因为 `GM_RM019_000172_001 -> GM_RM019_000173_001` 更强，保守 one-to-one best-edge 策略把 0045 维持为独立连续轨迹。

结论：这不是“没有可连边”，而是 OTY1 缺少 fragment merge audit 层。0039/0045 应标记为 `fragment_merge_candidate`，但不能直接写成 confirmed identity。

## 4. Timeline 孤立点含义

Timeline 中的孤立点是 detection_count=1 的 singleton component。它表示 YOLO 在某一帧产生了检测，但在当前几何规则下没有足够安全的一对一 runtime edge。

孤立点常见来源：

- 低置信检测；
- bbox 与画面边界接触，可能是截断目标；
- 邻车/重叠框造成同帧歧义；
- YOLO bbox 从局部车体框切换到整车框，导致 area/aspect 突变；
- frame gap 或短暂漏检造成 tracklet fragment。

孤立点不是确认目标，也不是错误样本；它是 OTY1 应保留给后续 fragment merge / temporal alignment 审计的候选状态。

## 5. 建议

下一步不应进入 SAR band。更合理的顺序是：

1. OTY1a：新增 fragment merge candidate audit，只在 optical runtime geometry 内判断可合并片段，输出 `fragment_merge_candidate_edges.csv`，不生成 confirmed identity。
2. OTY1b：把 timeline 可视化升级为分层显示：long component、fragment、singleton、merge-candidate 分开着色，避免把孤立点误解为失败。
3. OTY1c：为 0039/0045 这类 bbox shape transition 加一个专项字段，例如 `bbox_shape_transition_risk` 或 `partial_to_full_box_transition_proxy`。
4. OTY2：审计 optical-to-SAR high-FPS temporal alignment，只建立 optical state stream 到 SAR frame window 的时间关系，不生成 SAR fan/range band。
5. OTY3：在 OTY2 对齐成立后，再从 optical state stream 转 SAR fan/range band。

建议优先做 OTY1a，因为它直接处理当前看到的 0039/0045 问题，也能让 GM_RM017 的长轨迹和 fragment 更清晰。

## 6. 边界声明

本轮结论只来自 OTY0 YOLO detection table 和 OTY1 geometry-only tracklet audit。`review_queue.csv`、`final_gt_working.csv`、SAR GT、manual/final/oracle/review 字段没有用于 runtime tracklet construction。
