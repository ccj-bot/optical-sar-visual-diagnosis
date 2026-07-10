# OTY2 WGV3.5A Visual Feasible Field Diagnosis

Date: 20260710

The overlay PNGs are written under the ignored `outputs/` directory and are not intended for commit.

## Case 01: `WGV35A_PAIR_0003`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_01_WGV35A_PAIR_0003.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=partial_to_full_transition;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`12.264336`, D4=`12.264336`
- 方位预测是否合理: predicted `-40.434461`, GT `-42.9511`
- 径向预测是否合理: predicted `527.9568`, GT `532.931`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.4798`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 02: `WGV35A_PAIR_0006`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_02_WGV35A_PAIR_0006.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=mixed_partial_full_observations;boundary=boundary_truncation_present;multi=multiple_observations`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`12.7847`, D4=`11.938991`
- 方位预测是否合理: predicted `-39.343211`, GT `-42.5568`
- 径向预测是否合理: predicted `525.125237`, GT `528.621`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.5497`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 03: `WGV35A_PAIR_0007`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_03_WGV35A_PAIR_0007.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=partial_to_full_transition;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`11.613646`, D4=`11.613646`
- 方位预测是否合理: predicted `-38.785771`, GT `-41.0111`
- 径向预测是否合理: predicted `516.80387`, GT `518.435`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.5395`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 04: `WGV35A_PAIR_0173`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_04_WGV35A_PAIR_0173.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=low_uncertainty;partial=none;boundary=none;multi=single_observation`; split=`test`
- 深度是否可信: `1` valid ratio; strategy values D1=`7.31741`, D4=`7.31741`
- 方位预测是否合理: predicted `33.070377`, GT `35.5874`
- 径向预测是否合理: predicted `518.243471`, GT `397.746`
- 航向信息是否产生有效压缩: `unknown`; P2/P1 search ratio `1.6399`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `false`
- 失败由哪一层造成: `see_failure_cases_csv`

## Case 05: `WGV35A_PAIR_0176`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_05_WGV35A_PAIR_0176.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=low_uncertainty;partial=none;boundary=none;multi=single_observation`; split=`test`
- 深度是否可信: `1` valid ratio; strategy values D1=`7.31741`, D4=`7.31741`
- 方位预测是否合理: predicted `33.070475`, GT `36.8063`
- 径向预测是否合理: predicted `518.243471`, GT `402.758`
- 航向信息是否产生有效压缩: `unknown`; P2/P1 search ratio `1.6399`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 06: `WGV35A_PAIR_0199`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_06_WGV35A_PAIR_0199.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=low_uncertainty;partial=none;boundary=none;multi=single_observation`; split=`test`
- 深度是否可信: `1` valid ratio; strategy values D1=`7.505392`, D4=`7.31741`
- 方位预测是否合理: predicted `32.608638`, GT `32.1525`
- 径向预测是否合理: predicted `519.636954`, GT `540.514`
- 航向信息是否产生有效压缩: `unknown`; P2/P1 search ratio `1.6151`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 07: `WGV35A_PAIR_0030`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_07_WGV35A_PAIR_0030.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=mixed_partial_full_observations;boundary=boundary_truncation_present;multi=multiple_observations`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.509308`, D4=`10.686965`
- 方位预测是否合理: predicted `-31.802521`, GT `-30.6021`
- 径向预测是否合理: predicted `448.327591`, GT `455.063`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.6409`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 08: `WGV35A_PAIR_0033`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_08_WGV35A_PAIR_0033.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=mixed_partial_full_observations;boundary=boundary_truncation_present;multi=multiple_observations`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.509308`, D4=`10.686965`
- 方位预测是否合理: predicted `-31.803012`, GT `-30.7731`
- 径向预测是否合理: predicted `448.327591`, GT `453.933`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.6409`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 09: `WGV35A_PAIR_0204`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_09_WGV35A_PAIR_0204.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=low_uncertainty;partial=none;boundary=none;multi=single_observation`; split=`external_scene_test`
- 深度是否可信: `1` valid ratio; strategy values D1=`2.567564`, D4=`2.567564`
- 方位预测是否合理: predicted `-25.478492`, GT `-35.451`
- 径向预测是否合理: predicted `412.117435`, GT `155.671`
- 航向信息是否产生有效压缩: `unknown`; P2/P1 search ratio `2.422`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `false`
- 失败由哪一层造成: `see_failure_cases_csv`

## Case 10: `WGV35A_PAIR_0205`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_10_WGV35A_PAIR_0205.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=low_uncertainty;partial=none;boundary=none;multi=single_observation`; split=`external_scene_test`
- 深度是否可信: `1` valid ratio; strategy values D1=`2.829986`, D4=`2.61297`
- 方位预测是否合理: predicted `-20.487319`, GT `-33.2059`
- 径向预测是否合理: predicted `412.117435`, GT `149.63`
- 航向信息是否产生有效压缩: `unknown`; P2/P1 search ratio `2.2991`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `false`
- 失败由哪一层造成: `see_failure_cases_csv`

## Case 11: `WGV35A_PAIR_0206`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_11_WGV35A_PAIR_0206.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=low_uncertainty;partial=none;boundary=none;multi=single_observation`; split=`external_scene_test`
- 深度是否可信: `1` valid ratio; strategy values D1=`2.417665`, D4=`2.61297`
- 方位预测是否合理: predicted `23.263646`, GT `42.8808`
- 径向预测是否合理: predicted `407.724325`, GT `169.247`
- 航向信息是否产生有效压缩: `unknown`; P2/P1 search ratio `2.3676`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `false`
- 失败由哪一层造成: `see_failure_cases_csv`

## Case 12: `WGV35A_PAIR_0010`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_12_WGV35A_PAIR_0010.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=partial_to_full_transition;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.727476`, D4=`10.727476`
- 方位预测是否合理: predicted `-37.6049`, GT `-40.2321`
- 径向预测是否合理: predicted `503.120148`, GT `506.307`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.7226`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 13: `WGV35A_PAIR_0012`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_13_WGV35A_PAIR_0012.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=partial_to_full_transition;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.347659`, D4=`10.642591`
- 方位预测是否合理: predicted `-36.535321`, GT `-39.4391`
- 径向预测是否合理: predicted `498.938973`, GT `500.909`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.7316`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 14: `WGV35A_PAIR_0014`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_14_WGV35A_PAIR_0014.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=none;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.642591`, D4=`10.642591`
- 方位预测是否合理: predicted `-36.043381`, GT `-37.5648`
- 径向预测是否合理: predicted `491.706112`, GT `493.565`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.597`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 15: `WGV35A_PAIR_0016`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_15_WGV35A_PAIR_0016.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=none;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.354179`, D4=`10.642591`
- 方位预测是否合理: predicted `-35.301795`, GT `-37.2899`
- 径向预测是否合理: predicted `483.641026`, GT `485.124`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.6017`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 16: `WGV35A_PAIR_0021`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_16_WGV35A_PAIR_0021.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=none;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`11.038594`, D4=`10.823677`
- 方位预测是否合理: predicted `-33.737236`, GT `-34.1324`
- 径向预测是否合理: predicted `469.213006`, GT `470.457`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.6062`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 17: `WGV35A_PAIR_0023`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_17_WGV35A_PAIR_0023.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=none;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`11.038594`, D4=`10.823677`
- 方位预测是否合理: predicted `-33.737628`, GT `-33.4408`
- 径向预测是否合理: predicted `463.220719`, GT `462.867`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.6062`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`

## Case 18: `WGV35A_PAIR_0025`

- Overlay: `outputs/wgv3_5a_20260710/wgv3_5a_review_18_WGV35A_PAIR_0025.png`
- 光学车辆状态: `visibility=visible_main_observation;uncertainty=moderate_uncertainty;partial=none;boundary=boundary_truncation_present;multi=single_observation`; split=`train`
- 深度是否可信: `1` valid ratio; strategy values D1=`10.823677`, D4=`10.823677`
- 方位预测是否合理: predicted `-32.892594`, GT `-32.6885`
- 径向预测是否合理: predicted `463.220719`, GT `464.178`
- 航向信息是否产生有效压缩: `lateral_right`; P2/P1 search ratio `1.6182`
- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.
- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.
- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.
- 真实SAR标注是否被覆盖: `true`
- 失败由哪一层造成: `covered`
