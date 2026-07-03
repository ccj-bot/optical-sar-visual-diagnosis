# OTY2 Human Visual Review Notes And SAR Morphology Insight Archive

This archive preserves manual visual-review observations as mechanism anchors. It does not create annotation proposals, final boxes, selector/ranking outputs, or identity truth.

## Core Manual Mechanism Insights

1. GT 框内很多车辆确实存在肉眼可解释的 SAR 车体结构。
2. 近雷达侧 / 面向雷达侧通常更强。
3. 远雷达侧通常较弱。
4. 车辆结构常表现为连续或断续的车体边缘强散射条带。
5. 角点/端部/近侧区域常出现高能反射。
6. 断续结构仍可能构成车体，不应直接判为无结构。
7. 时序中高能区域可能随车辆运动迁移。
8. 邻近电动车、栏杆、路边结构、边缘效应、近场截断会造成结构解释困难。
9. support 如果没画出来，人工无法判断 support 是否过宽。
10. support coverage / optical association ambiguity 不能反过来否定 GT 框内 SAR morphology。

## Panel Notes

### Panel 1 - possible compact vehicle structure

能看出三辆车排列，中间车最明显。整体车架构边缘是高能结构。左边车靠近雷达侧边很明显，远离雷达侧稍弱。框内右边车辆因为较边缘，车体后部及远端高能区域不明显，但近端，即框左边和下边有明显轮廓。左下角最靠近雷达且直接面向雷达的区域是高能区域。肉眼可见高能区域能够直接导向车体轮廓。

- morphology insight: GT 框内存在可解释车体轮廓；近雷达/面向雷达侧更强，远侧较弱。
- mechanism keywords: `near_side_high_energy_ridge;facing_side_hotspot;body_edge_strip`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 2 - possible multi-peak vehicle structure

能看出两辆车和一个货车，货车不要求识别。框内车辆能看出车体轮廓，但不连贯。靠近雷达和面向雷达处是高能区域，尤其右下角。整体轮廓是断续片段，但框内仍呈现包裹状态。该样例说明车辆 SAR 结构可以是断续条带 + 高能角点 + 总体包裹结构，而不一定是连续闭合轮廓。

- morphology insight: 断续条带和角点热点仍可形成包裹式车体结构。
- mechanism keywords: `discontinuous_aligned_body_edges;corner_or_endpoint_strong_reflector;multi_peak_enclosed_body_structure`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 3 - possible range-spread vehicle structure

径向扩散主要在框上侧。人工假设可能与自身运动造成的逸散、支撑结构、车体逸散或环境影响有关，靠近路边栏杆可能影响结构。但上下两侧以及框右侧能量结构仍能形成车体轮廓。注意：运动逸散目前只是 hypothesis，不可写成确定结论。

- morphology insight: range spread 不能直接等于 diffuse/reject；仍可能保留车体 core。
- mechanism keywords: `range_spread_with_vehicle_body_core;environment_affected_body_structure;motion_hypothesis_only`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 4 - possible azimuth-spread vehicle structure

框下侧能量条带明显是车体结构，强度高且连续，不应简单解释为摊开或 diffuse spread。右下角面向雷达和近侧有高能区域，远侧能量较弱。该样例更应解释为 near-side continuous body ridge / strong body-side strip + near-side hotspot + far-side weak return。

- morphology insight: 连续强侧边条带是 morphology anchor，不是简单 diffuse spread。
- mechanism keywords: `near_side_high_energy_ridge;continuous_body_side_strip;far_side_weak_return`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 5 - possible stable vehicle tube

前后时序都能看到下侧条带。该车在时序中从雷达视场右侧走到左侧，下侧条带一般都明显，高能区域会随着时序面向雷达不断移动。该样例支持 temporal migration of vehicle high-energy region，而不是单帧亮点。

- morphology insight: 高能区随时序迁移，应建 temporal morphology tube。
- mechanism keywords: `temporal_migrating_hotspot;temporal_persistent_body_ridge`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 6 - diffuse / reject exemplar

虽然原标签可能是 diffuse / reject，但人工仍能肉眼看出是车。一方面面向雷达有高能区域，且可能随时序变化；另一方面上侧和下侧能量虽然断续，但能看出车体轮廓，即车长两侧。靠近雷达的一端较完整。正式表述时不要直接断言车头/车尾，应写近雷达侧端部更完整。

- morphology insight: 弱/散结构仍可能是车；不要用 diffuse 标签否定 GT 内 morphology。
- mechanism keywords: `discontinuous_aligned_body_edges;facing_side_hotspot;near_side_endpoint`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 7 - background-stable wrong-frame exemplar

与 Panel 6 和 Panel 3 是同一辆车或同一类问题。结构断续，不是非常明显的车体结构，但可根据排列形状和高能区域看出车是横向的，并且随时序变化。说明断续结构不应直接归为无结构。

- morphology insight: 断续结构需要 temporal/contextual morphology 判断。
- mechanism keywords: `discontinuous_aligned_body_edges;temporal_migrating_hotspot`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 8 - neighboring-object wrong-object exemplar

存在潜在混淆。光学中车屁股紧靠一个电动车，稍远左上还有一辆车。car 之间冲突不大，主要可能与后面的电动车有能量混淆。但车体本身是自洽的：下侧有一段断续条带，右侧近端/端部比左侧边界更明显，上侧比下侧条带弱很多。应标为 SAR structure strong but association may need review due to nearby non-target/e-bike interference。

- morphology insight: SAR morphology strong 与 association review 可以同时成立。
- mechanism keywords: `nearby_non_target_confounder;discontinuous_body_strip;association_review_needed`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 9 - support-overlap azimuth-shift exemplar

人工不清楚 support 想表达什么，因为 panel 没有清楚说明 support。仅从图看，GT 框明显包裹了一辆车的轮廓。下侧条带很强且没有断裂，右下角最靠近且面向雷达的一侧高能，上侧能量稍弱。需要 Codex 明确画出 optical-derived support / azimuth fan，不能让人工猜 support。可能受光学截断/遮挡、方位映射裕量、support 过宽影响。

- morphology insight: support 没画出来时不能让人工判断 support coverage。
- mechanism keywords: `support_overlay_required;continuous_body_side_strip;coverage_hypothesis`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 10 - statistics say vehicle-like but visual review likely needed

与 Panel 9 是同一时序中的同一辆车，具有同样结构特点。肉眼判断就是车，表现为近侧强条带、近侧/面向雷达高能区和远侧较弱回波。

- morphology insight: 同一时序重复出现近侧条带和热点。
- mechanism keywords: `temporal_persistent_body_ridge;facing_side_hotspot;far_side_weak_return`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 11 - case where GT is inside support but association should remain weak

与 Panel 9/10 是同一车或同一时序。图中本身有三辆车排列，远近左右均可见。周围没有很靠近的其他结构。GT 框可以完整自洽地包裹车体结构。该样例说明 GT inside support / GT boxed structure clear 时，应承认 SAR morphology strong；association 是否强是另一层问题。

- morphology insight: GT boxed structure clear 时应承认 morphology strong；association 是另一层。
- mechanism keywords: `gt_morphology_anchor;association_separate_layer`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 12 - SAR-only morphology reference exemplar

GT 框可能存在质量问题或边缘问题，因为目标太边缘、能量弱，可能不是理想样例。但仍有微弱能量点，像车身一侧的端部/角点。应标为 weak / boundary-affected morphology reference。

- morphology insight: 边界/弱能量样例只能作为 weak morphology reference。
- mechanism keywords: `boundary_weak_vehicle_structure;corner_or_endpoint_strong_reflector`
- boundary: manual visual review anchor; not identity truth; not annotation proposal

### Panel 13 - GM_RM011 waiting object-stream reference exemplar

整体还可以。光学是近场截断，目标很近，整体能量较强。车头/车尾相对弱，主要是车身两侧高能区域。不是典型连续条带，但明显像车两侧车身。正式表述中不要强断言车头/车尾，应写近侧/远侧或端部结构。

- morphology insight: 近场截断下两侧强回波可作为 near-field truncated morphology。
- mechanism keywords: `near_field_truncated_strong_body_sides;endpoint_structure_not_head_tail_truth`
- boundary: manual visual review anchor; not identity truth; not annotation proposal
