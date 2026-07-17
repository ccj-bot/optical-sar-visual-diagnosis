# OTY2 Session Start Here: Required Mechanism Context

This document must be read at the beginning of every new OTY2-related Codex session before writing scripts, running diagnostics, generating atlas outputs, or proposing next steps.

每个新的 OTY2 / optical-SAR mechanism 相关 Codex session，必须先读本文件，再读具体任务 prompt。不得直接沿用旧 support-wide / component-box / weighted-fusion 思路。

## 1. Current Non-Negotiable Boundaries

- 当前仍是 OTY2 posthoc mechanism diagnosis，不是 OTY3。
- 不做 final annotation。
- 不做 revised GT。
- 不做 final candidate box。
- 不做 selector/ranking。
- 不训练、不调阈值。
- 不声明 identity truth。
- SAR GT / SAR image observation / GT-local energy field 只能作为 posthoc mechanism reference，不能写回 runtime prediction logic。
- support 不是 final box。
- weighted fusion 不是当前主线。

## 2. Fixed Sample-Pool Semantics

- `442` = all SAR GT / SAR-side target reference pool.
- `215` = current clean paired optical-object-stream / SAR-GT posthoc frame-level pool.
- `195` = GM_RM011 blocked_missing_object_stream, not unlabeled, not unusable.
- `20` = SAR-only GT reference, usable for SAR morphology only.
- `12` = dropout / no OTY IoU match / temporal continuation special pool.

GM_RM011 不能继续被简单丢弃。它不能直接混入 `215` clean paired support validation，但它可以也应该用于 SAR morphology reference 和 object-stream recovery / pairing failure diagnosis。

## 3. What Was Corrected In Previous Sessions

- support-wide atlas 曾经错误地在 support 内找小组件。
- physical shell grammar atlas 曾经错误地把 GT 外 support-internal peaks/components 画成 vehicle parts。
- baby-car 小绿框问题：小组件不能叫车。
- top-k peak 是 scattering atom，不是 vehicle。
- 如果 GT-anchored vehicle-scale morphology 不在 support 内，正确诊断是 support construction failure / support miss vehicle structure，不是在错误 support 内继续找车。
- `de5e6d7` 的 GT-local atlas 修正了方向：GT crop 主坐标，不画 support boundary，不把 support-internal component 画成 shell，但后续仍需检查可读性和物理表达深度。

## 4. SAR-Only Must Close Both Positive And Negative Logic

SAR-only / SAR morphology lane 不能只回答“为什么 GT 内是车”，还必须回答“为什么其他强散射不是车”。

Positive mechanism cues include:

- vehicle scale;
- near-side / dominant-side ridge;
- endpoint / corner hotspot;
- weak opposite-side return;
- discontinuous but self-consistent boundary;
- long-axis / short-axis structure;
- temporal non-jump / gradual drift.

Negative mechanism cues include:

- isolated peak;
- tiny component / baby car;
- guardrail / building edge / road edge;
- flowerbed / background blob;
- pedestrian / e-bike / small object point-like response;
- fixed background hotspot;
- texture-like clutter without vehicle-scale shell closure.

Vehicle explanation without non-vehicle rejection is not a closed mechanism.

只解释为什么这是车，不解释为什么别的不是车，机制是不闭环的。

## 5. Physical Mechanism First, Not Weighted Fusion Or Heuristic Stacking

赋权叠加不是主线。启发式堆叠不是主线。

Shallow fusion:

```text
time_score + azimuth_score + support_score + energy_score + shell_score + temporal_score
```

Mechanism fusion:

- optical object stream supplies hypothesis and temporal continuity;
- optical state explains truncation / occlusion / edge contact;
- geometry supplies azimuth/range feasible field;
- SAR morphology explains vehicle vs non-vehicle structure;
- SAR temporal continuity checks non-jump drift;
- support statistics feed back to mechanism correction.

多信息融合是必要的，但不是简单加权；它应该是约束传播、失败回流和机制修正。

## 6. GM_RM011 Is A Recovery And Failure-Diagnosis Lane

GM_RM011 不是不能用。它有 SAR GT，也有对应 optical sequence / optical frames。当前问题是缺当前 OTY optical object stream，因此不能直接进入 `215` clean paired pool。

GM_RM011 应作为：

- SAR morphology reference;
- optical object stream recovery;
- pairing failure diagnosis;
- optical temporal pipeline stress test.

需要诊断：

- optical frame 是否存在；
- optical object 是否可见；
- YOLO / detection 是否存在；
- ByteTrack / object stream 是否断；
- optical-SAR time mapping 是否错；
- azimuth / range mapping 是否错；
- state compensation 是否缺失；
- 如果对应不上，说明 optical temporal stream / mapping / object association 流程有问题，而不是 GM_RM011 没价值。

## 7. Support Is Not Fixed; Support Statistics Must Feed Back

support 当前不是固定方法，也不是 final box。support 是 optical-derived hypothesis field。

如果 support 统计有问题，就说明机制有问题，必须回流修正，而不是继续在错误 support 内找结构。

Feedback cases:

- support miss GT vehicle shell -> check time mapping / range shell / azimuth mapping / optical state / near-field / temporal compensation.
- support too broad -> check azimuth margin / range looseness / state over-compensation.
- support contains neighbor -> check multi-object scene / identity ambiguity / optical tracklet / SAR temporal separation.
- support contains no GT but vehicle-like energy -> check neighbor GT / missing annotation candidate / false vehicle-like clutter.
- support contains no GT and no vehicle-like structure -> check optical false hypothesis / time mismatch / support false positive.
- support covers only part of vehicle -> check truncation / partial optical object / range compression.

Support audit must include support-without-GT cases, not only `215` paired rows.

## 8. Required Mechanism Lanes

Lane A: SAR vehicle / non-vehicle morphology closure

- Input: `442` SAR GT + context, including GM_RM011 / SAR-only / dropout special as SAR morphology reference.
- Goal: explain why vehicle is vehicle and why non-vehicle is not vehicle.
- Output: vehicle-vs-nonvehicle physical morphology grammar.
- No selector.

Lane B: GM_RM011 optical object stream recovery and pairing failure diagnosis

- Input: GM11 SAR GT, optical frames, detection / object stream pipeline artifacts if available.
- Goal: recover or diagnose missing object stream and pairing failure.
- Output: recoverable paired candidates / failure taxonomy.
- Do not force into clean `215`.

Lane C: dynamic support hypothesis audit

- Input: all optical object hypotheses with support, not only paired GT rows.
- Goal: classify support with/without GT, neighbor GT, background structure, vehicle-like but unpaired structure, empty support.
- Output: support failure taxonomy and mechanism feedback.
- No final box.

Lane D: optical-SAR temporal compatibility

- Input: SAR morphology that is physically interpretable + optical tracklet.
- Goal: check whether ridge / hotspot / shell drifts non-jump and matches optical continuity.
- Output: motion/drift compatibility.
- No identity truth.

## 9. Mandatory Reading Order For Future Sessions

Current route-reset decision stack, in this order:

1. `docs/OTY2_RESEARCH_ROUTE_RESET_RECORD_20260713.md`
2. `docs/OTY2_DATA_FOUNDATION_AND_GLOBAL_IDENTITY_ROUTE_RESET.md`
3. `reports/oty2/oty2_p0_data_asset_and_hard_sync_audit_20260713.md`
4. `docs/OTY2_P0_EXIT_AND_P1_ENTRY_DECISION_20260713.md`

The first three items are respectively the highest-level route basis, the execution contract, and the P0 evidence record. The fourth is the independent P0-exit/P1-entry stage decision. Then preserve the historical mechanism reading stack below.

For the independent SAR-foundation line, read next in this order:

1. `docs/OTY2_S0_SAR_GT_STRUCTURE_FOUNDATION_PROTOCOL.md`
2. `docs/OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md`
3. `docs/OTY2_S0_OPTICAL_TO_SAR_AZIMUTH_MAPPING_CONTRACT.md`
4. `reports/oty2/oty2_s0_sar_gt_structure_foundation_audit_20260715.md`

For the S1X project-level transition on `feature/oty2-sar-gt-structure-foundation`, after the S0/S0-M/S0-MV and S1-L/S1-LR/S1-LR2 inheritance stack, read:

1. `docs/OTY2_S1X_PROJECT_UNDERSTANDING_AND_EXECUTION_CONTRACT.md`
2. `reports/oty2/oty2_s1x_optical_conditioned_joint_temporal_support_recovery_20260717.md`

S1X is a controlled transition from target-reference-neighbourhood audit to target-reference-free optical-conditioned SAR temporal support recovery. It permits optical-only, SAR-only diagnostic, and optical+SAR inference under explicit freeze/evaluation isolation. It still does not authorize final boxes, unique centres, revised GT, selector/ranking, training, or automatic annotation. All prior S0/S1-L/S1-LR/S1-LR2 reports remain frozen evidence and must not be rewritten.

The S0-M correction is authoritative: the deterministic shared fan is the fixed `imaging_valid_mask`; mapping qualification is decided before residuals; only Mask-inside, optically complete, identity-clear anchors may support mapping freeze or future S1-L structure claims.

For the RSA0 visible-response-object route reset on `feature/oty2-sar-gt-structure-foundation`, read before any RSA0 code, atlas output, representation metric, or seed-propagation design:

1. `docs/OTY2_RSA0_GLOBAL_ROUTE_RESET_AND_RESEARCH_CONTRACT.md`
2. `docs/OTY2_RSA0_FAILURE_LESSONS_AND_NON_NEGOTIABLES.md`
3. `docs/OTY2_RSA0_VISIBLE_RESPONSE_OBJECT_SEMANTICS.md`

RSA0 freezes S1X and S1D0 as failure baselines, changes the research unit to a short-window visible SAR response object, and requires atlas-before-representation ordering. It does not authorize pre-entry/closed SAR background negatives, whole-GT-box positive masks, lifecycle dynamics, candidate ranking, final boxes, weighted winners, training, or automatic annotation.

Every new OTY2-related session must first read:

1. `docs/OTY2_SESSION_START_HERE.md`
2. `docs/OTY2_TEMPORAL_BACKBONE_ROUTE_RESET.md`
3. `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
4. `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
5. `docs/OTY2_POINT_TO_STRUCTURE_OPTICAL_SAR_VEHICLE_RESPONSE_FRAMEWORK.md`
6. `docs/OTY2_GENERATION_FREEZE_AND_GT_ASSISTED_ANALYSIS_BOUNDARY.md`
7. `docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md`
8. `docs/oty2_gt_support_failure_concept_correction_archive.md`
9. `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
10. `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`

Then read the task-specific latest report/summary from `reports/oty2`.

For WGV2 factor-graph sessions, after the standard OTY2 reading order, read:

1. `docs/OTY2_CROSS_MODAL_MECHANISM_FACTOR_GRAPH_DESIGN.md`
2. `docs/OTY2_CROSS_MODAL_FACTOR_IDEA_BANK.md`
3. `reports/oty2/oty2_wgv2_2_factor_graph_constraint_propagation_and_missing_factor_audit_20260709.md`
4. `reports/oty2/oty2_wgv2_3_factor_idea_bank_gt_validation_boundary_and_joint_factor_admission_rules_20260709.md`
5. `docs/OTY2_WGV2_FACTOR_GRAPH_PHASE_CLOSEOUT_AND_REPOSITORY_INHERITANCE_20260709.md`

For WGV3 optical-message source sessions, after the standard OTY2 reading order, read:

1. `docs/OTY2_TEMPORAL_BACKBONE_ROUTE_RESET.md`
2. `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
3. `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
4. `reports/oty2/oty2_wgv3_3a_optical_message_source_reproducibility_closure_20260710.md`
5. `reports/oty2/oty2_wgv3_3a_visual_failure_diagnosis_20260710.md`

WGV3.3A audits whether optical messages used by WGV2/WGV3 can be reproduced by the automatic optical backbone. It does not revoke WGV2/WGV3; it separates automatic runtime messages from WGV1.4 human/multimodal posthoc visual constraints.

Future sessions should inherit the repository historically, including failed or corrected work, but must preserve scope, provenance, and anti-leakage boundaries.

For WGV3.6A / A1.7R follow-up sessions: 不得直接从 compact assembly 进入多假设关联；必须先检查 `vehicle-supported observation entity`，并保留正向车辆支持与负向背景排除的闭环证据。

For A1.8A / A1.8A-R1 follow-up sessions, after the standard OTY2 reading order, read:

1. `docs/OTY2_POINT_TO_STRUCTURE_OPTICAL_SAR_VEHICLE_RESPONSE_FRAMEWORK.md`
2. `docs/OTY2_GENERATION_FREEZE_AND_GT_ASSISTED_ANALYSIS_BOUNDARY.md`
3. `reports/oty2/oty2_wgv3_6a_a1_8a_vehicle_response_grammar_audit_20260711.md`
4. `reports/oty2/oty2_wgv3_6a_a1_8a_r1_mechanism_integrity_audit_20260711.md`

For optical timeline video review and manual override sessions, also read:

1. `docs/OTY2_OPTICAL_TIMELINE_SESSION_CLOSEOUT_20260705.md`
2. `docs/OTY2_OPTICAL_TIMELINE_RENDER_REVIEW_AND_OVERRIDE_CONTRACT.md`

## 10. What Not To Do Next

- Do not immediately create another large CSV table without redefining the mechanism question.
- Do not use support-internal components outside GT to explain vehicle shell.
- Do not call small green component boxes shell.
- Do not do weighted fusion as mainline.
- Do not keep GM_RM011 permanently blocked.
- Do not treat GM_RM011 as a scene-specific patch target.
- Do not proceed from recovered object stream to pairing/support audit before cross-scene optical-stream generalization is checked.
- Do not treat PASS_WITH_UNCERTAINTY as mechanism success.
- Do not assume support is fixed.
- Do not avoid support-without-GT cases.
- Do not treat atlas as success unless it actually shows GT-local energy-field structure that humans can inspect.
