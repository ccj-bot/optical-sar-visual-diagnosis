# OTY2 autonomous local-structure extraction demo

状态：`Result A / L1_CONDITIONED_LOCAL_EXTRACTION`

## 审阅顺序

1. `E01_RUNTIME_INPUT_RESPONSE_AND_OBJECTS.png`
   - 左：运行期允许信息；中：多尺度响应；右：显式带中心线和附着热点。
2. `E02_MULTIFRAME_STRUCTURE_GRAPH.png`
   - 八帧主结构对象；允许厚带分裂，不输出 winner。
3. `E03_POSTHOC_GT_AND_MANUAL_CARD_AUDIT.png`
   - 左侧先冻结运行输出；右侧才显示研究期 GT 和人工 NSB 卡。
4. `E04_WORLD_REGISTERED_ROAD_CONTROL_EXTRACTION.png`
   - RC1–RC3 使用相同多帧准入，最终均无时序支持主带。
5. `T01`–`T07`
   - 多模态教师的局部、允许提示、邻帧、全局、中间 alpha、道路和不可辨识消融图板。

## 方法能看见

- 原始 SAR 灰度；
- 相邻 SAR 帧；
- 冻结 G1F0002 中心扇区；
- 扇形有效区、粗方向和车辆尺寸范围。

## 方法不能看见

- 当前目标 SAR GT 中心或框；
- 人工 NSB 折线/多边形；
- 已知响应峰；
- 历史 `0.65-0.79` 峰区间；
- 最终框、selector 或 winner。

## 输出语义

- `BAND_CENTERLINE`：由多尺度亮脊/LSD 碎片图组装的开放带中心线；
- `HOTSPOT_CLUSTER`：依附于时序支持带的局部热点；
- `TEMPORALLY_SUPPORTED_MULTIPLE_BANDS_UNRESOLVED`：同一厚带可能分裂成多条中心线，保留不确定性；
- `NOT_IDENTIFIABLE_NO_TEMPORALLY_SUPPORTED_BAND`：道路或压力案例没有通过时序准入。

这些对象不是 Mask、GT 修订、最终车辆框或训练标签。
