# OTY2 YOLO A/B 机制对比计划

生成时间：`20260702_190435`

本计划不替换主线 YOLO，不下载或提交权重，不训练或调阈值。目标是比较更强 YOLO 是否改善“可用于光学到 SAR 迁移机制研究”的 vehicle-like 对象，而不是只比较检测数量。

## 对比设计

1. 固定同一批场景、光学帧、SAR GT 表和软件同步 24:50 时间契约。
2. baseline YOLO 与 candidate YOLO 分别输出 OTY0 detection table。
3. 使用同一 OTY1/OTY1t 对象流构造逻辑，避免把 detector 差异和 tracker 规则差异混在一起。
4. 只评估 vehicle-like objects；非车辆类别保留记录但不进入主指标。
5. 运行车辆准入审计和本 GT 对应机制审计，比较机制变量，不生成自动标注建议。

## 核心指标

- 主研究车辆覆盖：有多少 GT 对应到 main_research_vehicle。
- 远小弱目标比例：far_small / unresolved_tiny 是否膨胀。
- 目标框稳定性：bbox 面积、高度、bottom_y 的时序抖动。
- 轨迹连续性：visible_frame_count、track_frame_span、断裂/短轨迹比例。
- duplicate / handoff 率：辅助观测、多观测、ID 切换风险。
- 光学框与 SAR GT 机制变量相关性：area/height/bottom_y 与 SAR radius/azimuth 的关系。
- 方位扇区覆盖率和宽度：覆盖是否改善，扇区是否更窄。
- 车辆尺度壳覆盖率和压缩率：尺度壳是否更常覆盖 GT，是否减少过宽方位扇带。
- normal / relaxed / review-only / blocked 分布变化。

## 当前基线

```json
{
  "gt_correspondence_samples": 215,
  "azimuth_prior_coverage": {
    "total": 215,
    "pass": 205,
    "fail": 9,
    "pass_rate": 0.9534883720930233
  },
  "vehicle_size_shell_coverage": {
    "total": 215,
    "pass": 215,
    "fail": 0,
    "pass_rate": 1.0
  },
  "shape_correlations": {
    "area_ratio_vs_radius": -0.7384331151126269,
    "height_vs_radius": -0.8417789316036687,
    "bottom_y_vs_radius": -0.7722411362128231
  }
}
```

## 建议

建议先做小样本 A/B，而不是马上替换主线。只有当 candidate YOLO 同时提升主研究车辆覆盖、轨迹稳定性、方位/尺度机制覆盖，并且不显著增加远小弱目标和 handoff/review-only 负担时，才值得进入更大范围对比。
