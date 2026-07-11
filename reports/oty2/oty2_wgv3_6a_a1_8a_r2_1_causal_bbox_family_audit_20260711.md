# OTY2 WGV3.6A-A1.8A-R2.1 Causal BBox Family Audit

## Boundary

- requested start commit: `54d0f90284e7833fafea9af918309c2fa5026a68`
- commands: `generate`, `blind-raw-pack`, `blind-assisted-pack`, `evaluate`, `verify-replay`; no `all` command.
- generation inputs: SAR grayscale PNG, A1.7R source-only compact shell CSV, static fan geometry, embedded deterministic runtime frame list.
- R1 frozen atom/role/lineage inputs in generate: `false`.
- R2 artifacts are read only in evaluate for frozen baseline delta.
- GT, labels, vehicle identity are read only in evaluate.
- GM_RM011_BLOCKED=true

## Frozen Generation SHA

- `runtime_manifest`: `ecef41b220070b9aeed8be0c19d02a1366e38433eb57587a1991b0958f485f7b`
- `causal_shell`: `fc30a3510e3858a6f47bb3c8480f1f7ddf4ed610bad0e3e36051191aaa58d419`
- `atom_trace`: `37b3c0ae07ab0f09e276da23caa280d3ce805714f7beed419b666ecebf5b5694`
- `roles`: `e4bd86a646a29de6c63d572142f40b5d9968e5e167c8990287658916e4f26b91`
- `support_metrics`: `b964c2f1b8c279532e95c664941da54ed025c9b090ae8eb6309a547af7980038`
- `lineage_nodes`: `f96004ca38b46ae3e266a925e4495aad744725ed144f21a851b12a887d9bc8e1`
- `lineage_edges`: `2b50f3766b4c4dc30f3c1b327753d2e9e1b680530268d7d363ba9937dcdaaabd`
- `atom_graph_nodes`: `5dbce3dfb3567df40e63a21d9557c69e431f1dcaf0081fe22aa1a92e5f4c5192`
- `atom_graph_edges`: `c8937600e51ca304ae75405c528989c145cf6a81f651aa2b5e6c756a6231edb1`
- `core_hypotheses`: `a683af5b203464a392db23bde58eb975d2acc4aa668d6e97ca1c4a9bcb3cb6ae`
- `optional_membership`: `9c766ff8081763ea81e2bdd5272c646bb345be8644b23600d89aaeec1135df02`
- `response_boxes`: `b0102c04730d44a67f17f517e9942afb0e902da92084879a0b18b2eaf1fed209`
- `families`: `d5e049429b4b20fca39987fa82a694afb88b0a3665f7a67d83dd958473391294`
- `family_members`: `d2e7a82b7b67145701d9f2faae8cf72d84d28317c04e74a2761666ee4c75e6cc`
- `family_temporal`: `ec58f32dc92899ca0ed645dc64a0b65e542f47c96d88c86bf395390813f43294`
- `background_counterexamples`: `ef831956cc1e6ecea4510441209d7325c9132ed8238c121534038d573ef24043`
- `FROZEN_REPLAY_IDENTICAL`: `PASS`
- replay evidence: `runtime_manifest:PASS; causal_shell:PASS; atom_trace:PASS; roles:PASS; support_metrics:PASS; lineage_nodes:PASS; lineage_edges:PASS; atom_graph_nodes:PASS; atom_graph_edges:PASS; core_hypotheses:PASS; optional_membership:PASS; response_boxes:PASS; families:PASS; family_members:PASS; family_temporal:PASS; background_counterexamples:PASS`

## Source Shell And Staleness

- source lag max: `29`
- stale/high-risk shell rows: `35`
- old future-source frames audited: `[30, 60, 227, 228, 259, 260, 262, 263, 272, 281, 284]`

## Runtime Counts

- R2.1 atoms: `184`
- role counts: `{'unresolved_atom': 49, 'body_core_candidate': 41, 'isolated_small_atom': 49, 'endpoint_hotspot_candidate': 24, 'side_ridge_candidate': 13, 'background_arc_candidate': 8}`
- lineage nodes/edges: `184/193`
- atom graph edges: `339` / `{'accepted_local_relation': 81, 'blocked_by_role': 172, 'ambiguous_relation': 50, 'blocked_by_geometry': 16, 'blocked_by_background': 20}`
- core subgraphs: `250`
- raw response boxes: `250`
- box states: `{'vehicle_response_box_supported': 16, 'vehicle_response_box_possible': 48, 'vehicle_part_box_only': 37, 'background_counterexample': 0, 'unresolved': 149}`
- exact/near/nested families: `Counter({'nested_boundary_variant': 21, 'distinct_core_same_response': 11, 'spatially_distinct_hypothesis': 11, 'single_member_family': 6})`
- hypothesis families: `49`
- family count per frame: `{'27': 1, '28': 1, '29': 1, '30': 1, '31': 1, '32': 1, '34': 1, '39': 1, '40': 2, '46': 1, '52': 1, '60': 2, '77': 1, '78': 1, '79': 1, '80': 1, '81': 1, '212': 1, '213': 1, '216': 1, '220': 1, '224': 1, '227': 1, '228': 1, '238': 1, '239': 1, '243': 1, '250': 1, '259': 1, '260': 1, '262': 1, '263': 1, '269': 1, '270': 1, '271': 1, '272': 1, '273': 2, '276': 1, '278': 1, '279': 1, '280': 1, '281': 1, '284': 1, '288': 1, '289': 1, '290': 1}`
- optional decisions: `{'uncertain_bbox_membership': 689, 'exclude_from_bbox': 125}`
- optional evidence types: `{'uncertain_spatial_proximity_only': 689, 'exclude_excessive_bbox_expansion': 75, 'exclude_background_conflict': 50}`
- background counterexamples: `46`

## Blind Review

- raw judgement counts: `{'unresolved': 25, 'vehicle_response': 10, 'background': 14}`
- raw object-specific unique reason ratio: `1`
- assisted judgement counts: `{'unresolved': 11, 'mechanism_partial': 18, 'background_or_misled': 16, 'vehicle_response': 4}`
- raw to assisted changes: `{'unresolved->unresolved': 11, 'vehicle_response->mechanism_partial': 6, 'background->background_or_misled': 14, 'unresolved->background_or_misled': 2, 'unresolved->mechanism_partial': 12, 'vehicle_response->vehicle_response': 4}`

## Evaluation

- raw-primary error taxonomy: `{'raw_unresolved_runtime_acceptance': 23, 'exact_gt_background_inclusion': 2, 'not_evaluable_no_exact_gt': 38, 'exact_gt_vehicle_part_exclusion': 3, 'raw_background_runtime_acceptance': 13, 'assisted_overlay_induced_background_change': 2, 'current_evidence_no_mechanism_error_found': 2}`
- exact GT mean IoU / coverage / purity: `0.243414` / `0.398917` / `0.413759`
- metric auxiliary max error m: `0.0`
- nonselective family temporal edges: `50`

## R2 vs R2.1 Delta

| sar_frame | r2_atom_count | r2_1_causal_atom_count | atom_bbox_change | role_change | lineage_change | core_hypothesis_change | response_bbox_change | hypothesis_family_change | change_caused_by_causal_regeneration_cn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 5 | 5 | same_count_bbox_not_pairwise_assumed | {'unresolved_atom': 2, 'body_core_candidate': 1, 'endpoint_hotspot_candidate': 1, 'isolated_small_atom': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=2;r2_1=8 | r2=2;r2_1=8 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 60 | 9 | 3 | changed_count_or_support | {'background_arc_candidate': 1, 'body_core_candidate': 1, 'isolated_small_atom': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=2;r2_1=2 | r2=2;r2_1=2 | r2_1_family_count=2 | 因果重生成导致原子/核心/框数量发生变化。 |
| 227 | 5 | 3 | changed_count_or_support | {'unresolved_atom': 1, 'endpoint_hotspot_candidate': 1, 'isolated_small_atom': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=1;r2_1=4 | r2=1;r2_1=4 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 228 | 4 | 3 | changed_count_or_support | {'unresolved_atom': 1, 'body_core_candidate': 1, 'isolated_small_atom': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=1;r2_1=4 | r2=1;r2_1=4 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 259 | 5 | 3 | changed_count_or_support | {'body_core_candidate': 2, 'side_ridge_candidate': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=2;r2_1=7 | r2=2;r2_1=7 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 260 | 3 | 3 | same_count_bbox_not_pairwise_assumed | {'unresolved_atom': 1, 'body_core_candidate': 1, 'endpoint_hotspot_candidate': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=1;r2_1=7 | r2=1;r2_1=7 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 262 | 3 | 1 | changed_count_or_support | {'body_core_candidate': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=1;r2_1=1 | r2=1;r2_1=1 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 263 | 2 | 1 | changed_count_or_support | {'body_core_candidate': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=1;r2_1=1 | r2=1;r2_1=1 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 272 | 5 | 6 | changed_count_or_support | {'unresolved_atom': 1, 'body_core_candidate': 1, 'endpoint_hotspot_candidate': 1, 'isolated_small_atom': 3} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=2;r2_1=8 | r2=2;r2_1=8 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 281 | 5 | 4 | changed_count_or_support | {'unresolved_atom': 1, 'body_core_candidate': 1, 'endpoint_hotspot_candidate': 1, 'isolated_small_atom': 1} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=3;r2_1=8 | r2=3;r2_1=8 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |
| 284 | 5 | 5 | same_count_bbox_not_pairwise_assumed | {'unresolved_atom': 1, 'body_core_candidate': 1, 'isolated_small_atom': 3} | R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied | r2=2;r2_1=6 | r2=2;r2_1=6 | r2_1_family_count=1 | 因果重生成导致原子/核心/框数量发生变化。 |

## Focus Window Conclusions

- 27-31: causal regeneration changes the atom basis before core generation; frame 31 can now surface part-only family members instead of only unresolved whole boxes.
- 78-81: horizontal arc-like responses are nearby background unless the core itself is dominated by the arc; nearby background is not a global veto.
- 227-263: long source lag produces stale-shell/boundary-contact risk; this is audited separately from causality and is not repaired with GT.
- 263: remains unsupported at runtime when raw evidence is unresolved/background and no exact GT is used to rescue it.
- 270-273: supported/possible families are separated from vehicle_part_box_only side/endpoint fragments.
- 289-290: long side-line responses are retained as counterexamples or part-only variants, not complete vehicle response closure.
- Duplicate same-frame boxes are counted at family level, so repeated member hypotheses are not double-counted as independent detections.

## Why This, Why Not That

| accepted_family_id | alternative_object_id | same_frame | accepted_visible_structure | alternative_visible_structure | accepted_core_relation | alternative_relation | accepted_lineage | alternative_lineage | accepted_bbox_membership | alternative_exclusion_reason | why_accepted_is_vehicle_response_cn | why_alternative_is_not_vehicle_response_cn | remaining_uncertainty_cn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R21F00001 | R21A00004 | 27 | family bbox 1006,1131,1018,1137 contains local core/member responses | isolated_small_atom at 1006,1131,1018,1137 | unresolved:5;vehicle_response_box_possible:1 | nearby_noncore_response | R21A00001;R21A00002;R21A00003;R21A00004;R21A00005 | single_frame_or_no_shared_lineage | R21B00001;R21B00002;R21B00003;R21B00004;R21B00005;R21B00006 | no whole-core membership evidence | 27帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00004 位于同帧邻近区域，但角色为 isolated_small_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00002 | R21A00009 | 28 | family bbox 1006,1131,1024,1143 contains local core/member responses | isolated_small_atom at 1006,1131,1024,1143 | unresolved:4;vehicle_response_box_possible:1 | nearby_noncore_response | R21A00006;R21A00007;R21A00008;R21A00009 | single_frame_or_no_shared_lineage | R21B00007;R21B00008;R21B00009;R21B00010;R21B00011 | no whole-core membership evidence | 28帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00009 位于同帧邻近区域，但角色为 isolated_small_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00003 | R21A00010 | 29 | family bbox 1042,1131,1192,1197 contains local core/member responses | unresolved_atom at 1042,1131,1192,1197 | unresolved:3;vehicle_response_box_possible:1 | nearby_noncore_response | R21A00010;R21A00011;R21A00012 | R21PT0001 | R21B00012;R21B00013;R21B00014;R21B00015 | no whole-core membership evidence | 29帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00010 位于同帧邻近区域，但角色为 unresolved_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00004 | R21A00013 | 30 | family bbox 1042,1131,1193,1197 contains local core/member responses | unresolved_atom at 1042,1131,1193,1197 | unresolved:5;vehicle_part_box_only:1;vehicle_response_box_possible:1;vehicle_response_box_supported:1 | nearby_noncore_response | R21A00013;R21A00014;R21A00015;R21A00016;R21A00017 | R21PT0002 | R21B00016;R21B00017;R21B00018;R21B00019;R21B00020;R21B00021;R21B00022;R21B00023 | no whole-core membership evidence | 30帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00013 位于同帧邻近区域，但角色为 unresolved_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00005 | R21A00019 | 31 | family bbox 1042,1135,1114,1243 contains local core/member responses | unresolved_atom at 1090,1135,1114,1147 | unresolved:3;vehicle_part_box_only:2;vehicle_response_box_possible:1;vehicle_response_box_supported:2 | nearby_noncore_response | R21A00018;R21A00019;R21A00020;R21A00021 | single_frame_or_no_shared_lineage | R21B00024;R21B00025;R21B00026;R21B00027;R21B00028;R21B00029;R21B00030;R21B00031 | no whole-core membership evidence | 31帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00019 位于同帧邻近区域，但角色为 unresolved_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00006 | R21A00023 | 32 | family bbox 1048,1165,1072,1177 contains local core/member responses | unresolved_atom at 1072,1159,1096,1189 | unresolved:5;vehicle_part_box_only:2;vehicle_response_box_possible:1 | nearby_noncore_response | R21A00022;R21A00023;R21A00024;R21A00025;R21A00026;R21A00027 | R21PT0002 | R21B00032;R21B00033;R21B00034;R21B00035;R21B00036;R21B00037;R21B00038;R21B00039 | no whole-core membership evidence | 32帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00023 位于同帧邻近区域，但角色为 unresolved_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00007 | R21A00034 | 34 | family bbox 1018,1141,1042,1159 contains local core/member responses | unresolved_atom at 1018,1141,1042,1159 | unresolved:3;vehicle_part_box_only:3;vehicle_response_box_possible:1;vehicle_response_box_supported:1 | nearby_noncore_response | R21A00028;R21A00029;R21A00030;R21A00031;R21A00032;R21A00033;R21A00034 | R21PT0006 | R21B00040;R21B00041;R21B00042;R21B00043;R21B00044;R21B00045;R21B00046;R21B00047 | no whole-core membership evidence | 34帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00034 位于同帧邻近区域，但角色为 unresolved_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00008 | R21A00036 | 39 | family bbox 1048,1165,1192,1276 contains local core/member responses | background_arc_candidate at 1042,1135,1084,1159 | unresolved:2;vehicle_part_box_only:3;vehicle_response_box_possible:3 | nearby_background | R21A00035;R21A00038;R21A00039;R21A00040;R21A00041 | single_frame_or_no_shared_lineage | R21B00048;R21B00049;R21B00050;R21B00051;R21B00052;R21B00053;R21B00054;R21B00055 | background arc excluded | 39帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00036 位于同帧邻近区域，但角色为 background_arc_candidate，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00009 | R21A00046 | 40 | family bbox 1054,1207,1108,1237 contains local core/member responses | isolated_small_atom at 1090,1171,1114,1183 | unresolved:3;vehicle_response_box_possible:2 | nearby_noncore_response | R21A00042;R21A00044;R21A00045;R21A00046 | single_frame_or_no_shared_lineage | R21B00056;R21B00058;R21B00059;R21B00060;R21B00061 | no whole-core membership evidence | 40帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00046 位于同帧邻近区域，但角色为 isolated_small_atom，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00010 | R21A00043 | 40 | family bbox 994,1135,1090,1159 contains local core/member responses | side_ridge_candidate at 994,1135,1090,1159 | vehicle_part_box_only:1 | nearby_noncore_response | R21A00043 | R21PT0006 | R21B00057 | no whole-core membership evidence | 40帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00043 位于同帧邻近区域，但角色为 side_ridge_candidate，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00011 | R21A00047 | 46 | family bbox 1030,1135,1193,1255 contains local core/member responses | body_core_candidate at 1030,1135,1193,1255 | vehicle_response_box_possible:1 | nearby_noncore_response | R21A00047 | R21PT0007 | R21B00062 | no whole-core membership evidence | 46帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00047 位于同帧邻近区域，但角色为 body_core_candidate，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| R21F00012 | R21A00049 | 52 | family bbox 1024,1135,1193,1189 contains local core/member responses | background_arc_candidate at 1114,1213,1180,1243 | unresolved:3;vehicle_part_box_only:1 | nearby_background | R21A00048;R21A00050;R21A00051 | single_frame_or_no_shared_lineage | R21B00063;R21B00064;R21B00065;R21B00066 | background arc excluded | 52帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。 | R21A00049 位于同帧邻近区域，但角色为 background_arc_candidate，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。 | 边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。 |
| ... |  |  |  |  |  |  |  |  |  |  |  |  |  |

## Gate Verdicts

| gate | status | evidence | provenance |
| --- | --- | --- | --- |
| GENERATION_GT_ISOLATION_VALID | PASS | generate reads SAR gray, A1.7R source shell, static geometry, embedded runtime frame list only | runtime_safe |
| R1_FROZEN_ATOMS_NOT_USED_IN_R2_1_GENERATE | PASS | no R1 atom/role/lineage CSV is read by generate | runtime_safe |
| CAUSAL_ATOM_REGENERATION_USED | PASS | regenerated atoms=184 | runtime_safe |
| SOURCE_SHELL_CAUSALITY_VALID | PASS | selected source frame is max source<=sar frame or fallback | runtime_safe |
| SOURCE_SHELL_STALENESS_AUDITED | PASS | high risk rows=35 | runtime_safe |
| CAUSAL_REGENERATION_DELTA_AUDITED | PASS | delta rows=11 | eval_only |
| SUPPORT_PIXEL_METRICS_VALID | PASS | support metric rows=434 | runtime_safe |
| ATOM_GRAPH_USED_FOR_CORE_GENERATION | PASS | multi-atom cores reference accepted graph edge ids | runtime_safe |
| CORE_SUBGRAPH_CONNECTED | PASS | core rows=250 | runtime_safe |
| ISOLATED_ATOM_NOT_GLOBAL_VETO | PASS | single/optional isolated atoms do not globally reject other connected cores | runtime_safe |
| NEARBY_BACKGROUND_NOT_GLOBAL_VETO | PASS | nearby_background is separated from core dominance | runtime_safe |
| BACKGROUND_DOMINANCE_EXPLICIT | PASS | background counterexamples=46 | runtime_safe |
| OPTIONAL_MEMBERSHIP_WHOLE_CORE_AWARE | PASS | optional relation is checked against all core atoms | runtime_safe |
| OPTIONAL_MEMBERSHIP_LINEAGE_AWARE | PASS | shared-lineage include rows=0; lineage rule evaluated before proximity fallback | runtime_safe |
| SPATIAL_PROXIMITY_NOT_AUTO_INCLUDE | PASS | spatial-only relations remain uncertain | runtime_safe |
| VEHICLE_PART_BOX_STATE_ACTIVE | PASS | part-only boxes=37 | runtime_safe |
| HYPOTHESIS_FAMILY_GROUPING_VALID | PASS | families=49 | runtime_safe |
| DUPLICATE_BOXES_NOT_DOUBLE_COUNTED | PASS | response boxes are grouped into family ids before family-level eval | runtime_safe |
| RAW_REVIEW_OBJECT_SPECIFIC | PASS | unique raw reason ratio=1 | blind_visual_review |
| ASSISTED_REVIEW_OBJECT_SPECIFIC | PASS | unique assisted reason ratio=1 | blind_visual_review |
| RAW_EVIDENCE_PRIMARY_FOR_ERROR_TAXONOMY | PASS | error taxonomy starts from raw judgement, assisted is separate | eval_only |
| ASSISTED_NOT_USED_AS_TRUTH | PASS | assisted judgement is mechanism interpretation only | blind_visual_review |
| METRIC_AUXILIARY_COORDINATE_VALID | PASS | max metric consistency error=0 | runtime_safe |
| FAMILY_TEMPORAL_GRAPH_NONSELECTIVE | PASS | family temporal edges=50 | runtime_safe |
| FROZEN_REPLAY_IDENTICAL | PASS | verify-replay compares all R2.1 frozen generation artifacts | runtime_safe |
| CORE_RESPONSE_BBOX_R2_1_READY | PARTIAL | family-level causal bbox audit exists but remains local and posthoc-validated | eval_only |
| VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2 | NO | R2.1 still audit-only; no selector/final annotation/runtime contract | eval_only |
| GM_RM011_BLOCKED | true | GM_RM011 not executed | eval_only |

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_8a_r2_1_causal_bbox_family_audit_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_runtime_frame_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_causal_source_shell_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_causal_atom_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_role_proposals_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_support_pixel_metrics_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_part_lineage_nodes_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_part_lineage_edges_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_atom_graph_nodes_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_atom_graph_edges_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_core_subgraph_hypotheses_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_optional_response_membership_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_response_box_hypotheses_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_bbox_hypothesis_families_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_family_member_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_family_temporal_edges_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_background_counterexamples_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_blind_raw_family_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_blind_assisted_family_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_gt_assisted_family_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r2_vs_r2_1_causal_delta_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_error_taxonomy_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_gate_integrity_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_frozen_artifact_manifest_20260711.csv`

## Research Judgment

R2.1 fixes the causal atom-regeneration gap: atoms, roles, lineage, graph cores, bbox hypotheses, and families are regenerated from SAR grayscale under historical source shells. The product is still a mechanism audit, not final annotation, selector, ranking, training data, or an A1.7R2 runtime contract.