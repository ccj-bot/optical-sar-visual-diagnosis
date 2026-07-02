# OTY2 YOLO 升级 A/B 对比接口设计

生成时间：`20260702_180326`

本文件只设计对比接口，不替换主线模型，不下载权重，不训练或调阈值，也不声称更高级 YOLO 已被验证为改进。

## 当前 YOLO 可能的问题

- 漏检：当前对象流只反映已被检测并跟踪到的目标，无法证明所有车辆都被召回。
- 误检：本轮对象级主流中没有发现非车辆类主对象，但这不代表更大范围没有误检。
- 框不准：远小车和边缘对象的 bbox 面积很小，少量像素误差会显著影响方位弱先验。
- 重复框 / handoff：辅助观测、多观测和可能 ID 切换会把对象降级为弱车层或仅审阅层。
- 远小车过多：更强 YOLO 可能检出更多远小车，这对检测数量是好事，但会提高远小车层和 review-only 比例。
- 类别不聚焦：当前主线只研究 vehicle/car-like，不应把所有 YOLO 类别都混入主结果。
- 跟踪断裂：短轨迹对象即便类别是 car，也不适合作为主研究迁移对象。

## 更高级 YOLO 可能改善什么

- 可能提高车辆召回，尤其是远小车或遮挡车辆。
- 可能让框更稳定，从而改善轨迹连续性和方位弱先验的包络质量。
- 可能减少部分误检或类别混淆。

## 可能副作用

- 检出更多极小远车，导致主研究对象池被弱目标稀释。
- 产生更多短轨迹、重复框和 handoff，需要更多 review-only 处理。
- 检测数量上升不等于 SAR 标注迁移质量上升。
- 如果只看 detection count，会误判模型升级价值。

## A/B 对比接口

1. 固定同一批场景、光学帧范围和软件同步时间契约。
2. 分别运行 baseline YOLO 与 candidate YOLO，输出同 schema 的 OTY0 检测表。
3. 用同一 OTY1/OTY1t 对象流构造逻辑生成对象假设，禁止引入 SAR GT 或后验 selector。
4. 运行本准入审计脚本，比较对象级 eligibility，而不是只比较检测数量。
5. 只把模型权重路径写入本地配置或命令参数，不提交权重文件。

## 推荐指标

- `vehicle_research_eligibility` 分布：主研究车辆、弱车、远小车、仅审阅、阻断分别如何变化。
- `track_frame_span` 和 `visible_frame_count`：轨迹是否更连续。
- 远小车比例：`low_resolvable_far_vehicle` + `unresolved_tiny_vehicle` 是否显著上升。
- duplicate/handoff 比率：更多检测是否制造更多重复对象。
- downstream normal / review-only / blocked 变化：是否真正增加可进入主研究的对象，而不是只增加审阅负担。
- bbox 面积比例和置信度分布：框是否更稳定、更可解析。

## 当前建议

不建议马上把主线替换成更高级 YOLO。应先做 A/B 对比，判断升级是否增加主研究车辆和轨迹连续性，同时不显著增加远小车、重复框和 review-only 负担。

## 本轮基线摘要

```json
{
  "eligibility_counts": {
    "blocked_no_object_flow": 1,
    "weak_vehicle_layer": 6,
    "main_research_vehicle": 2,
    "review_only_vehicle": 4,
    "blocked_vehicle_or_noise": 10,
    "far_small_vehicle_layer": 5
  },
  "resolvability_tier_counts": {
    "no_object_flow": 1,
    "high_resolvable_vehicle": 9,
    "medium_resolvable_vehicle": 3,
    "blocked_noise_or_short_track": 10,
    "low_resolvable_far_vehicle": 4,
    "unresolved_tiny_vehicle": 1
  },
  "scene_summary": [
    {
      "scene": "GM_RM011",
      "total_rows": 1,
      "main_research_vehicle": 0,
      "weak_vehicle_layer": 0,
      "far_small_vehicle_layer": 0,
      "review_only_vehicle": 0,
      "blocked": 1,
      "high_resolvable_vehicle": 0,
      "medium_resolvable_vehicle": 0,
      "low_resolvable_far_vehicle": 0,
      "unresolved_tiny_vehicle": 0
    },
    {
      "scene": "GM_RM017",
      "total_rows": 6,
      "main_research_vehicle": 2,
      "weak_vehicle_layer": 3,
      "far_small_vehicle_layer": 0,
      "review_only_vehicle": 1,
      "blocked": 0,
      "high_resolvable_vehicle": 5,
      "medium_resolvable_vehicle": 1,
      "low_resolvable_far_vehicle": 0,
      "unresolved_tiny_vehicle": 0
    },
    {
      "scene": "GM_RM019",
      "total_rows": 21,
      "main_research_vehicle": 0,
      "weak_vehicle_layer": 3,
      "far_small_vehicle_layer": 5,
      "review_only_vehicle": 3,
      "blocked": 10,
      "high_resolvable_vehicle": 4,
      "medium_resolvable_vehicle": 2,
      "low_resolvable_far_vehicle": 4,
      "unresolved_tiny_vehicle": 1
    }
  ]
}
```
