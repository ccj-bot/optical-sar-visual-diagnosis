# OTY2 YOLO26l WGV1.2 tracking-style MRQ association adjudication

Date: 2026-07-08

## 结论

上一版 gate-style triage 的问题是把 `competing_candidate_present` 过早解释成“不能合并”。这不符合常规跟踪关联逻辑。更合理的做法是：先把 from endpoint 与 to-frame 所有候选框做局部关联评分，再判断最高分候选到底是同一辆车上的重复/更优框，还是空间上分离的另一辆车。

修正后，前后帧已经重叠、归一化位移小、视觉上落在同一车辆主体上的片段，不再因为同帧存在更高分候选而直接拆开。它们会保留为 `diagnostic same-vehicle candidate`，或标记为 `same_object_better_box_primary_selection_issue`。

- adjudication CSV: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_2_mrq_tracking_style_association_adjudication_20260708.csv`
- rule CSV: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_2_tracking_style_association_rules_20260708.csv`

Decision counts:

- `diagnostic_same_vehicle_candidate_supported`: 8
- `keep_separate_competing_candidate_better`: 1
- `same_object_better_box_primary_selection_issue`: 2

## 为什么“有竞争框”不能直接当作禁止合并

目标跟踪里的核心不是“有几辆车就拒绝”，而是构造局部候选集、计算匹配代价，然后做一对一关联。常见 MOT 思路会同时看：

1. 前后框是否重叠，尤其是 `IoU` 和 intersection-over-min-area。
2. 中心点位移是否相对于车辆尺寸合理，即 normalized motion。
3. 框面积和长宽是否连续，避免把远处小车跳到近处大车。
4. 类别、横向槽位、外观只作为辅助惩罚，因为车窗/车头/车尾局部检测会导致 class/x_bin 抖动。
5. 同一帧内如果多个框压在同一辆真实车上，先做 duplicate / primary-box selection resolution，不能把它当成不同车辆证据。

因此，你指出的情况是成立的：如果大断点两端的光学框仍然有强重叠，且都落在同一辆车上，那么它应该至少保留为诊断同车候选。上一版不能合并的原因不是物理逻辑不支持，而是机制把 `rank != 1` 简化成了 `competing_candidate_better`，没有判断那个更高分候选是不是同一车的重复框。

## MRQ Results

| MRQ | scene | endpoint frames | IoU | IoMin | norm_dist | rank | same-frame best relation | decision | rule |
|---|---|---|---:|---:|---:|---:|---|---|---|
| MRQ001 | GM_RM011 | 4->8 | 0.671 | 0.916 | 0.103 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ002 | GM_RM011 | 10->13 | 0.853 | 0.979 | 0.040 | 2 | same_object_duplicate_or_better_box | same_object_better_box_primary_selection_issue | resolve_duplicate_candidate_before_identity_split |
| MRQ003 | GM_RM011 | 16->18 | 0.944 | 0.998 | 0.014 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ004 | GM_RM011 | 25->31 | 0.000 | 0.000 | 1.108 | 2 | spatially_distinct_competing_vehicle | keep_separate_competing_candidate_better | spatially_distinct_competing_candidate_wins_local_association |
| MRQ005 | GM_RM011 | 161->164 | 0.224 | 0.998 | 0.215 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ006 | GM_RM011 | 233->236 | 0.950 | 0.998 | 0.014 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ007 | GM_RM011 | 266->269 | 0.643 | 0.992 | 0.159 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ008 | GM_RM011 | 270->279 | 0.741 | 0.984 | 0.092 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ009 | GM_RM017 | 144->145 | 0.750 | 0.873 | 0.117 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |
| MRQ010 | GM_RM017 | 158->164 | 0.405 | 0.685 | 0.350 | 2 | same_object_duplicate_or_better_box | same_object_better_box_primary_selection_issue | resolve_duplicate_candidate_before_identity_split |
| MRQ011 | GM_RM017 | 213->214 | 0.378 | 0.999 | 0.267 | 1 | same_candidate | diagnostic_same_vehicle_candidate_supported | local_tracking_association_supports_review_candidate |

## 关键样例解释

- `MRQ002 / GM_RM011 10->13`: 前后 endpoint IoU=0.853、IoMin=0.979、normalized distance=0.040。frame 13 的更高分候选与 proposed to-target 是同一辆白色 SUV 上的重叠框，所以这是 `same_object_better_box_primary_selection_issue`，不是不同车竞争。
- `MRQ010 / GM_RM017 158->164`: selected to-target 是白车上的窄框，frame 164 的更高分 left candidate 仍压在同一辆白车上；黑车和右侧 truck 是真实多车背景，但并不是这条 from->to 的最佳同车证据。因此这里也不应因为多车存在而直接拆开，应先解决同车主框选择。
- `MRQ004 / GM_RM011 25->31`: frame 25 是右侧白车车头局部，frame 31 selected 是左侧 Maxus 车头，IoU=0、IoMin=0、normalized distance=1.108，并且横向槽位跳变。这里保留 `keep_separate_competing_candidate_better` 是合理的。
- `MRQ009 / GM_RM017 144->145`: truck 前后框稳定重叠，左侧黑车只是背景竞争对象；这里应保留 truck 的同车诊断候选，不应因为场景中同时有 car 就混淆。

## 机制修正

修正后的机制不是 `competitor exists -> block`，而是：

1. 在下一帧或短断点后建立局部 candidate set。
2. 用 overlap、IoMin、normalized motion、scale continuity、class/x_bin penalty 对所有候选评分。
3. 先判断 proposed to-target 与 best candidate 是否是同一真实车上的重复框或更优框。
4. 如果是同车重复框，记录 primary-box selection issue，不拆 identity。
5. 如果 best candidate 空间上分离，且比 proposed to-target 更符合 from endpoint，再保留 keep-separate / identity-switch review。
6. 即便保留为同车候选，也仍然是 diagnostic-only，不是自动合并成 final identity。

## 为什么会出现“大断点但可合并候选”

当前 WGV1.2 的断点主要来自 detector primary selection 和 fragment construction，而不是车辆真实消失。只要断点两端的 endpoint 框有强 overlap/IoMin，中心位移相对车辆尺寸合理，并且视觉上仍覆盖同一车身主体，就应该进入同车候选。大断点只意味着需要更强证据和人工/诊断复核，不等于必须禁止连接。

## Boundary

- `auto_merge_allowed=no` for every row.
- `sar_ready=no / blocked` for every row.
- No final boxes, no GT boxes, no final/revised annotation.
- No tracker replay and no SAR.
