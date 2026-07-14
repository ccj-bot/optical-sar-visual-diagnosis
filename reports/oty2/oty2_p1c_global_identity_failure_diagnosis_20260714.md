# OTY2 P1-C 光学全局身份失败诊断

日期：`2026-07-14`

## 1. 诊断结论

本轮在修改求解代码前完成了 P1-B 全量 CSV、线程 atlas、mandatory-event atlas、指定线程 MP4 和原始光学帧的直接审阅。

结论分成两类：

1. GM_RM019 早期黑车并未被运行时求解器拆断。黑车在 frame 0–14 连续可见并从右侧退出，P1-B 输出 `GM_RM019:GV001 / AT0001 / 0-14` 与完整视觉一致。所谓 frame 0–29 留出失败来自 evidence evaluator 把审阅窗口的 `frame_end=29` 当成同车锚点；frame 15–29 的主体是同时进入的白色 MPV，而不是黑车。
2. GM_RM011 确有多条同色车辆长缺口错误串接。至少 `E000020`、`E001940`、`E003224`、`E003685` 均把已经从一侧边界退出的车辆连接到从对侧边界新进入的另一辆车。

因此，GM_RM019 需要修复验证语义；GM_RM011 需要修复统一目标中的生命周期 turnover 表达。不得把 GM_RM019 的 frame 29 强制加入黑车线程，也不得把四个 GM_RM011 edge ID 写入最终运行时黑名单。

## 2. 完整视觉审阅记录

已逐帧完整解码并审阅：

- `GM_RM019_GV001/thread_overlay.mp4`：15/15 帧；黑色轿车从左侧主体经过并在 frame 14 退出。
- `GM_RM019_GV002/thread_overlay.mp4`：39/39 帧；白色 MPV 在 frame 5–43 独立通过，frame 5–14 与黑车同时可见。
- `GM_RM011_GV002/thread_overlay.mp4`：60/60 帧；frame 0–18 的近场白 SUV 与 frame 20 后的白色轿车不是同一辆车。
- `GM_RM011_GV005/thread_overlay.mp4`：183/183 帧；线程跨越遮盖车辆、多个白色轿车、长时间无框和多次边界 turnover，显著过串接。
- `GM_RM011_GV007/thread_overlay.mp4`：73/73 帧；frame 270 右侧退出车辆与 frame 284 左侧进入 SUV 被错误连接。

同时审阅 GM_RM011 的 0–60、110–170、188–212、231–292、303–316 原始逐帧页，以及 GM_RM019 的 0–45、149–183 原始逐帧页。临时视觉页位于 gitignored `outputs/oty2_p1c_visual_review_20260714/`，不得提交。

## 3. GM_RM019 根因

`GM019_P1A_E001` 的证据语义是“第一辆黑色轿车生命周期”，但表中 `frame_start=0, frame_end=29` 实际是审阅窗口，不是两个身份锚点。当前 `evaluate_evidence()` 对 `same_vehicle` 只检查是否有同一线程在起止帧 ±2 内出现，因此把 frame 29 的白色 MPV错误当成黑车应到达的终点。

候选图按帧锚点可找到 0→29 路径，但该路径会跨物理对象；这说明当前所谓候选召回和留出评价是 frame-only，不是 object-aware。正确修复是分离 review window 与 identity anchor，而不是生成或强制一条黑车到 frame 29 的边。

## 4. GM_RM011 根因

四条已确认错误边的共同结构是：

| edge | source exit | target entry | gap | edge cost | fixed exit+birth |
| --- | --- | --- | ---: | ---: | ---: |
| `E000020` | right | left | 15 | 216 | 240 |
| `E001940` | left+bottom | right+bottom | 20 | 0 | 240 |
| `E003224` | right+bottom | left+bottom | 16 | 237 | 240 |
| `E003685` | right | left+bottom | 13 | 212 | 240 |

当前模型对所有出生和退出使用固定 120 成本；同时 transition 只包含一阶局部运动、appearance、颜色、shape、gap、tracker 支持和 detector source。它没有表达“车辆已经从一侧完成退出、另一车辆从对侧重新进入”这一完整生命周期 turnover。

更严重的是：

- YOLO11l-only tracklet 没有 ResNet18 appearance，缺失特征只罚 18；
- 共享 tracker 奖励为 80，可把长缺口边压到 0；
- boundary support 目前只给 transition 折扣，反而可能鼓励跨边界串接；
- 固定 birth+exit 240 使错误桥接与正确生命周期解释只差很小。

## 5. 原子短轨迹粒度

| scene | atomic | 1-frame | 2-frame | 3–5 | >5 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| GM_RM011 | 185 | 132 / 71.35% | 3 / 1.62% | 14 / 7.57% | 36 / 19.46% | 过度碎片化 |
| GM_RM017 | 36 | 28 / 77.78% | 0 | 0 | 8 / 22.22% | 全池碎片化，但四条选中主干稳定 |
| GM_RM019 | 230 | 199 / 86.52% | 6 / 2.61% | 1 / 0.43% | 24 / 10.43% | 严重过度碎片化 |

主要来源不是必要 subject switch，而是 `supplement_singleton`：GM_RM011/017/019 分别为 123/28/190。全局图因此接近帧级关联；但 GM_RM019 黑车恰好由一个 15 帧长 tracklet 完整承载，不能把 validator false positive 误归因于该场景的碎片化。

## 6. 候选覆盖与 forbidden 绕行

按当前 frame-only 定义，可评价 same-vehicle 关系的候选路径召回为：

- development：`2/2`；
- heldout：`9/9`。

该数字不能当作对象级召回，因为 GM019_P1A_E001 的 0→29 路径连接的是不同车辆。

对显式 forbidden tracker pair 的 DAG reachability 审计显示：

- `GM011_P1A_E013`：存在 a→b 候选绕行路径；
- `GM011_P1A_E014`：存在 a→b 候选绕行路径；
- `GM017_P1A_E007`：不存在候选绕行路径。

P1-B 通过求解后 path cut 保证当前解零违规，但候选图仍包含 GM_RM011 的等价绕行压力。

## 7. 反事实与近似等价解

联合禁止四条错误边仅用于诊断：

- coverage：`41140 -> 41140`；
- identity explanation cost：`2995 -> 3008`，仅 `+13`；
- selected edge total：`1315 -> 1088`，`-227`；
- birth+exit count：`14 -> 16`，增加的两个生命周期端点成本为 `+240`；
- thread count：`7 -> 8`。

四条边逐一 no-good 的身份代价差分别为 `+9, 0, +3, +1`。其中 `E001940` 存在完全等价替代；其余也只差 1–9。GM_RM011 的 0.591 Jaccard 不是均匀噪声，而是由这些 lifecycle bridge 及其替代边主导的整条线程重组。

## 8. 建议的最小通用机制

优先引入一个统一、软性的 `exit_to_opposite_entry_turnover` 目标项：当 source tracklet 在水平边界完成退出、target tracklet 从对侧水平边界重新进入时，transition 必须承担一次未建模的生命周期 reset 成本。该项：

- 只使用运行时光学 bbox、时间和边界状态；
- 不使用场景名、帧号、人工 edge ID、SAR 或 GT；
- 不禁止边，只在统一目标中表达物理上需要解释的退出—重新进入；
- 直接针对四条已确认错误的共同结构；
- 预计不影响 GM_RM017 的四条无 gap 长 tracklet。

原子 tracklet 的局部连续性重建仍是后续必要改进，但本轮先用最小生命周期机制验证能否消除已确认错误，并避免一次加入多个复杂项。

诊断阶段状态：`P1C_DIAGNOSIS_COMPLETE_BEFORE_CODE_CHANGE`。
