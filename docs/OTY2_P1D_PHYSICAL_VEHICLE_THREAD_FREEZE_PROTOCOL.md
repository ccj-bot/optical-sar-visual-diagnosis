# OTY2 P1-D 物理车辆线程冻结与全生命周期验收协议

日期：`2026-07-14`

## 1. 目的与边界

P1-D 只验收 P1-C 光学全局线程是否与真实物理车辆形成完整、唯一、稳定的对应关系。它不修改 P1-C 求解结果，不执行人工合并、拆分或重编号，也不读取 SAR、SAR GT、方位映射或任何 P2 资产。

P1-D 可以输出三种阶段状态：

- `P1D_PHYSICAL_VEHICLE_THREADS_FROZEN`
- `P1D_PHYSICAL_VEHICLE_THREADS_PARTIALLY_FROZEN`
- `P1D_PHYSICAL_VEHICLE_THREADS_BLOCKED`

只有 `P1D_PHYSICAL_VEHICLE_THREADS_FROZEN` 允许进入 P2。

## 2. 强制审阅单元

每个场景必须同时完成：

1. 368 帧完整联合场景审阅；
2. 每条 P1-C 线程的进入前、活动期、全部 gap、恢复、退出和退出后上下文审阅；
3. 相邻、相似、时间接近或空间邻近线程对的物理身份审阅；
4. 非车辆线程、重复身份、主体切换和真实车辆漏线程检查；
5. tracker 与 detector provenance 追溯；
6. P1-C 固定种子重放与 hard constraint 复核。

atlas、CSV、embedding、bbox 数值和高风险事件只能辅助审阅，不能替代完整时间流。

## 3. 线程级判定

一条线程只有同时满足以下条件才可在审计总账中标为 `frozen`：

- 全部可见帧属于同一物理车辆；
- 没有其他线程同时或分段表示同一车辆；
- 进入、退出和长 gap 均可由完整画面解释；
- detector 与 tracker provenance 可追溯；
- 参数扰动不改变身份结构；
- 与场景级联合审阅无冲突。

需要通用 P1-C 修复的情况分别标为：

- `merge_required`
- `split_required`
- `identity_conflict`
- `optically_unresolvable`

`optically_unresolvable` 只允许在完整过去、未来与联合场景仍无法区分时使用，不能作为一般性退出项。

## 4. 禁止人工覆盖

P1-D 发现错误时必须记录到生命周期、线程对和验收清单中，并返回 P1-C 做通用机制修复。禁止：

- 手工编辑最终身份 CSV；
- 使用帧号特例或场景专用运行时 Gate；
- 使用 manual override；
- 为接近预估车辆数而强制合并；
- 为保留当前线程数而忽略视觉冲突。

审计表中的帧号是复核证据索引，不是求解器规则。

## 5. 冻结与阻断规则

出现任一未修复的情况即不得生成最终冻结 registry、P1-C 到 canonical 映射或冻结逐帧线程：

- 非车辆线程被输出为车辆；
- 一条 global ID 混合不同主体；
- 一辆物理车辆由多个 global ID 表示；
- 未解释的长 gap、进入或退出；
- provenance 不可追溯；
- hard constraint 违规非零；
- 固定种子重放不一致；
- 完整场景或逐线程审阅未完成。

阻断状态允许提交审计 registry、生命周期账本、线程对账本、reset 审计、验收清单、协议、报告、runner 和 validator，但不得伪造最终冻结输出。

## 6. 本轮执行边界

本协议对应的 `2026-07-14` 执行为光学-only blocked audit。临时 MP4、JPG、atlas、NPZ 和 outputs 仅用于本地审阅，不得进入提交。P1-B 与 P1-C 历史产物必须保持不变。
