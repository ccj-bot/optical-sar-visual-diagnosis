# OTY2 P1-D 物理车辆线程冻结与全生命周期验收报告

日期：`2026-07-14`

## 1. 执行结论

最终状态：`P1D_PHYSICAL_VEHICLE_THREADS_BLOCKED`。

三场景的 368 帧联合场景视频与全部 24 条 P1-C 线程上下文均已完整审阅。GM_RM011 共观察到 14 辆真实停放车辆，但 GV009/GV010 是同一辆罩车、GV004 生命周期提前结束，且 GV014 之后还有一辆罩车完全未进入 P1-C；GM_RM017 的 4 条线程构成正向基线；GM_RM019 存在一个非车辆线程、一个混合身份线程和一辆车被两个 ID 表示。因此不得生成最终冻结输出，也不得进入 P2。

本轮只使用光学时间流和 P1-C provenance，未读取 SAR、SAR GT、方位映射或 P2 资产。

## 2. 场景总览

| scene | P1-C threads | audited physical vehicles | clean row-level identities | formal frozen vehicles | stage result |
| --- | ---: | ---: | ---: | ---: | --- |
| GM_RM011 | 14 | 14 | 11 | 0 | blocked by lifecycle and coverage conflicts |
| GM_RM017 | 4 | 4 | 4 | 0 | audit-passed but not formally emitted |
| GM_RM019 | 6 | 4 | 3 | 0 | blocked by false, mixed, and duplicate identities |

`formal frozen vehicles` 为 0，是因为阶段整体 BLOCKED，最终 frozen registry、global-to-canonical map 和 frozen per-frame threads 均未生成。审计层确认的物理车辆数为 GM_RM011 `14`、GM_RM017 `4`、GM_RM019 `4`。

## 3. GM_RM011：14 线程过度拆分压力测试

完整相机扫掠中共观察到 14 辆物理车辆，但 14 条 P1-C 线程并非一一对应：`GM_RM011:GV009`（155-166）与 `GM_RM011:GV010`（188-191）是同一辆连续可见的银色罩车，167-187 为可见无框 gap；`GM_RM011:GV004` 在 55 帧退出后，同一罩车仍可见至约 87 帧；`GM_RM011:GV014` 之后约 307-336 还有一辆独立罩车完全没有 P1-C 线程。

其余相邻白车分离正确：GV011/GV012 在 243-245 共存，GV012/GV013 在 262-266 共存，GV013/GV014 在 284-292 共存。14 条 P1-C 线程实际表示 13 辆独立物理车辆，另有 1 辆物理车辆完全漏线程，因此场景总物理车辆数仍为 14。GM_RM011 有 1 个过度拆分/重复身份、1 个提前退出的不完整生命周期和 1 辆漏线程车辆；这些问题均可由光学完整时间流明确判断，不属于 `optically_unresolvable`。

## 4. GM_RM017：正向基线

四条线程分别是白色厢式货车、前方深色轿车、白色 SUV 和后方深色轿车。四车在 162-164 同时可区分并保持次序，退出帧依次为 164、185、200、214；215-367 不再出现车辆线程。未发现过拆、错并或主体交换。

## 5. GM_RM019：阻断失败

- `GM_RM019:GV001`：0-14 的黑色轿车，纯且完整；frame 29 的白色 MPV 与其无关。

- `GM_RM019:GV002`：5-43 的白色 MPV，纯且完整。

- `GM_RM019:GV003`：45-100 跟随行人和路侧小物体，不对应任何车辆，是非车辆伪线程。

- `GM_RM019:GV004`：51-124 为非车辆/行人碎片，约从 125 起切换到银色 MPV，属于身份混合；其后缀又与 `GM_RM019:GV005` 表示同一辆银色 MPV。

- `GM_RM019:GV005`：98-143 的真实银色 MPV，但被 `GM_RM019:GV004` 后缀重复表示。

- `GM_RM019:GV006`：149-183 的灰色 SUV，纯且完整。

因此 GM_RM019 只有 4 辆物理车辆，不是 6 辆；发现 1 个重复/过拆实例、1 个错误混合实例和 1 个非车辆线程。连同 GM_RM011，本轮总计发现 2 个同车多 ID/过拆实例、1 个线程内错误混合、1 个非车辆线程和 1 辆真实车辆漏线程。问题均可由光学完整时间流明确判定，不存在真正光学不可分辨区间。

## 6. exit-new birth 与 pairwise 审计

GM_RM011 的 reset 修复了 P1-B 已知的 4 条错误长桥，但也至少把一辆持续可见罩车拆成 GV009/GV010，并未恢复 GV004 的可见后缀；因此 exit-new birth/visible recovery 存在局部过度使用或恢复不足。GM_RM017 未出现 reset 失败。GM_RM019 的主要问题则是非车辆线程准入、线程内主体切换和并行重复身份。不得增加场景专用 Gate，应返回 P1-C 修复通用生命周期恢复、身份纯度与一车一 ID 约束。

线程对审计共记录 `25` 对；生命周期审计共记录 `26` 行。

## 7. 稳定性、约束与可追溯性

P1-C hard constraints：`{"same_frame_duplicate_identity_count": 0, "forbidden_merge_violation_count": 0, "observation_duplicate_use_count": 0, "track_time_reverse_count": 0, "total_hard_constraint_violations": 0}`。

P1-C 固定种子重放已确认三场景 thread count 保持 14/4/6，全部扰动的 minimum selected-edge Jaccard=1.0，P1-C validator PASS，hard constraint 违规为 0。P1-D registry 中的 detector 和 tracker 字段直接聚合自 P1-C 逐帧线程，不建立新的身份求解路径。

## 8. 冻结决定与 P2

由于 GM_RM011 的提前退出、同车双 ID 和漏线程，以及 `GM_RM019:GV003`、`GM_RM019:GV004` 和 `GM_RM019:GV004/GM_RM019:GV005` 关系违反冻结条件，本轮不生成：

- `oty2_p1d_frozen_physical_vehicle_registry.csv`
- `oty2_p1d_global_to_canonical_vehicle_map.csv`
- `oty2_p1d_frozen_optical_vehicle_threads.csv`

必须返回 P1-C 做通用机制修复，重跑三个场景并重新执行 P1-D。当前明确不允许进入 P2。

## 9. 未运行内容

未运行 SAR/SAR GT 读取、方位映射、SAR 坐标、P2、Mask、candidate、selector、ranking、训练、自动标注、参数大搜索、场景专用运行时 Gate 或 manual override；未修改原始图像、视频、检测资产、P1-B 或 P1-C 历史产物。临时 MP4/JPG 仅位于 workspace/output，不提交。
