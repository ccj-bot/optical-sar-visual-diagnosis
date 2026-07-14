# OTY2 P1-F 多帧主体观察整理与缺失观察恢复报告

日期：`2026-07-14`

## 1. 阶段结论

阶段状态：`P1F_SUBJECT_OBSERVATION_LAYER_PARTIALLY_READY`。

运行时脚本只读取光学帧、两路 normalized detections 和已有 tracker 局部关系；P1-E canonical、reference bbox、逐帧状态与 role 仅由独立 evaluator 读取。未读取 SAR、SAR GT、方位映射或 P2。

## 2. 四级实验按车辆角色结果

| baseline | role | visible | correct | recall | complete | visible-no-observation | correct recovered | mean segment | single-frame segments |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_YOLO26L | development | 345 | 315 | 0.9130 | 315 | 30 | 0 | 19.688 | 2 |
| A_YOLO26L | heldout_validation | 281 | 270 | 0.9609 | 268 | 11 | 0 | 22.500 | 1 |
| A_YOLO26L | diagnostic_only | 167 | 67 | 0.4012 | 63 | 100 | 0 | 7.444 | 5 |
| B_MULTI_SOURCE_SELECTION | development | 345 | 341 | 0.9884 | 341 | 4 | 0 | 26.231 | 1 |
| B_MULTI_SOURCE_SELECTION | heldout_validation | 281 | 278 | 0.9893 | 274 | 3 | 0 | 27.800 | 0 |
| B_MULTI_SOURCE_SELECTION | diagnostic_only | 167 | 87 | 0.5210 | 84 | 80 | 0 | 12.429 | 3 |
| C_FORWARD_RECOVERY | development | 345 | 341 | 0.9884 | 341 | 4 | 0 | 26.231 | 1 |
| C_FORWARD_RECOVERY | heldout_validation | 281 | 278 | 0.9893 | 274 | 3 | 0 | 27.800 | 0 |
| C_FORWARD_RECOVERY | diagnostic_only | 167 | 87 | 0.5210 | 83 | 80 | 4 | 17.400 | 0 |
| D_BIDIRECTIONAL_CONTROLLED | development | 345 | 341 | 0.9884 | 341 | 4 | 0 | 26.231 | 1 |
| D_BIDIRECTIONAL_CONTROLLED | heldout_validation | 281 | 278 | 0.9893 | 274 | 3 | 0 | 27.800 | 0 |
| D_BIDIRECTIONAL_CONTROLLED | diagnostic_only | 167 | 94 | 0.5629 | 86 | 73 | 11 | 18.800 | 0 |

## 3. 观察纯度

| baseline | mixed selected | non-vehicle selected | wrong subject links | wrong recoveries | occlusion/outside misrecoveries | duplicate subject frames | reused observation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_YOLO26L | 13 | 167 | 0 | 0 | 0 | 76 | 0 |
| B_MULTI_SOURCE_SELECTION | 5 | 253 | 0 | 0 | 0 | 34 | 0 |
| C_FORWARD_RECOVERY | 6 | 260 | 16 | 15 | 0 | 24 | 0 |
| D_BIDIRECTIONAL_CONTROLLED | 6 | 373 | 17 | 16 | 0 | 24 | 0 |

## 4. visible-but-unboxed 恢复

P1-E 共确认 83 个 visible-but-unboxed 帧；Baseline D 正确恢复 `10` 帧。恢复框来自 LK 光流、RANSAC 相似仿射和模板相关性，不使用线性 bbox 插值作为最终结果。

## 5. GM_RM017 / GM_RM019 回归

- GM_RM017: Baseline B=191/191，Baseline D=191/191，regressed=`false`。
- GM_RM019: Baseline B=135/135，Baseline D=135/135，regressed=`false`。

## 6. READY 条件

- `heldout_recall_improved`: `false`
- `visible_unboxed_recovered`: `true`
- `no_wrong_vehicle_recovery`: `false`
- `no_occlusion_or_outside_misrecovery`: `true`
- `unique_subject_selection`: `false`
- `mixed_selection_reduced`: `false`
- `non_vehicle_selection_reduced`: `false`
- `gm017_gm019_no_regression`: `true`
- `mean_segment_length_improved`: `false`
- `leakage_audit_pass`: `true`

## 7. 泄漏与阶段边界

Runtime/benchmark leakage audit: `PASS`。P1-F representation entry allowed: `false`。P2 entry allowed: `false`。

未修改 P1-C solver、ILP、目标函数、birth/exit cost 或身份边权重；未训练 detector/ReID；未使用 frame/scene-specific Gate、manual override 或 heldout 调参；未运行 SAR 候选、selector、ranking、标注或 P2。

## 8. 直接视觉审阅

已直接审阅 90 页临时视觉产物，覆盖三个场景全部 1104 帧、全部 83 个 visible-but-unboxed 上下文、全部 245 个接受恢复，以及错误恢复、mixed-subject、非车辆稳定观察、同车多框竞争、heldout 完整序列和 GM_RM017/019 无回归检查。临时图片保留在 workspace/output，未进入正式产物。

视觉结论与自动评价一致：PV004 在 60--63 帧附近仅短暂恢复，64--87 帧仍缺失；PV009 在约 181--187 帧恢复成功，但 192--196 帧再次漏失；PV014 在约 318--336 帧仍无主体观察。GM_RM011 存在同一物理车辆对应多个 runtime local subject 的情况。GM_RM017/019 的基准车辆召回未退化，但红色门栏、路侧设施、行人、两轮车和相邻碎片仍被错误选择或传播。

因此视觉审阅不支持 READY：正确恢复范围有限，错误车辆恢复、非车辆选择和每车每帧唯一性问题仍然存在。

## 9. 固定输出摘要

- evaluation hash: `08db93338d282ee03d62a6525a387c90aa6b40b7dbcd9555f5d6ec5d535e87a6`
- failure inventory hash: `8e977922562c7602ec49d13de2f58c04b0f3bf2e1314205c1e248c2faf40d231`
- leakage audit hash: `e82dab50fc97a3839706c3be02ef9afaea583de66b56bc92c95a9af38cc72d3a`
