# OTY2 WGV3.6A GM_RM019 Visual Diagnosis

Codex generated and reviewed these visual panels:

- anchor_contact: `outputs\wgv3_6a_gm019_20260711\wgv3_6a_anchor_audit_contact_sheet.png`
- adjacent_review: `outputs\wgv3_6a_gm019_20260711\wgv3_6a_adjacent_sar_review_sheet.png`
- propagation_methods: `outputs\wgv3_6a_gm019_20260711\wgv3_6a_propagation_methods_overview.png`
- bidirectional: `outputs\wgv3_6a_gm019_20260711\wgv3_6a_bidirectional_closure.png`
- failure_cases: `outputs\wgv3_6a_gm019_20260711\wgv3_6a_failure_cases.png`

## Chinese Visual Judgement

- 白色SUV和银色MPV存在可用的同车可见响应锚点；它们只作为mask内局部响应起点，不作为完整车辆中心。
- 黑色轿车和灰色左边车保留为压力审计：局部响应可见，但边缘/短段/近距mask语义降低锚点置信度。
- 右侧暗片段仍然需要配对复核，不能进入A1扩散。
- 短间隔双锚点中，P3能在局部窗口内覆盖mask内可见响应；长间隔只给部分闭合或复核状态。

## Anchor Audit

|pair_id|physical_vehicle_id|optical_frame|sar_frame|mask_class|anchor_status|visible_response_bbox_or_region|response_center_for_local_tracking|response_extent|response_confidence|forward_safe_limit|backward_safe_limit|stop_reason|visual_reason_cn|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|WGV35A_PAIR_0200|PV_GM19_BLACK_SEDAN_NEAR_FIELD|0|0|SAR_MASK_S2_CENTER_CENSORED|ANCHOR_WEAK|1104.480,1165.800,1250.293,1230.300|1177.387,1198.050|145.813x64.500|high|0|0|pressure_vehicle_short_or_edge_observation|SAR局部响应可见，但光学状态为压力/边缘/短段条件；只能作为压力审计，不进入A1主传播。|
|WGV35A_PAIR_0201|PV_GM19_BLACK_SEDAN_NEAR_FIELD|2|4|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_WEAK|1112.153,1163.477,1261.526,1228.510|1186.840,1195.994|149.373x65.033|high|0|0|pressure_vehicle_short_or_edge_observation|SAR局部响应可见，但光学状态为压力/边缘/短段条件；只能作为压力审计，不进入A1主传播。|
|WGV35A_PAIR_0202|PV_GM19_BLACK_SEDAN_NEAR_FIELD|4|8|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_WEAK|1123.629,1159.738,1269.835,1230.416|1196.732,1195.077|146.206x70.678|high|0|0|pressure_vehicle_short_or_edge_observation|SAR局部响应可见，但光学状态为压力/边缘/短段条件；只能作为压力审计，不进入A1主传播。|
|WGV35A_PAIR_0203|PV_GM19_RIGHT_DARK_FRAGMENT|13|27|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_PAIRING_REVIEW_REQUIRED|1207.149,1148.719,1386.602,1224.337|1296.876,1186.528|179.453x75.618|high|0|0|identity_or_pairing_review_required|同帧车辆或短片段身份复核未闭合，不能作为扩散起点。|
|WGV35A_PAIR_0204|PV_GM19_WHITE_SUV_NEAR_FIELD|13|27|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|972.572,1167.739,1154.849,1239.839|1063.710,1203.789|182.277x72.100|high|4|3|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0205|PV_GM19_WHITE_SUV_NEAR_FIELD|15|31|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|990.094,1171.077,1154.017,1239.729|1072.055,1205.403|163.923x68.652|high|8|4|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0206|PV_GM19_WHITE_SUV_NEAR_FIELD|37|77|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|1184.523,1169.528,1353.813,1243.634|1269.168,1206.581|169.290x74.106|high|4|8|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0207|PV_GM19_WHITE_SUV_NEAR_FIELD|39|81|SAR_MASK_S2_CENTER_CENSORED|ANCHOR_CONFIRMED|1202.549,1177.058,1355.094,1250.527|1278.822,1213.793|152.545x73.469|high|3|4|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0208|PV_GM19_SILVER_MPV_NEAR_FIELD|102|212|SAR_MASK_S2_CENTER_CENSORED|ANCHOR_CONFIRMED|935.174,1162.205,1093.287,1244.449|1014.231,1203.327|158.113x82.244|high|8|3|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0209|PV_GM19_SILVER_MPV_NEAR_FIELD|114|238|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|1041.740,1171.593,1179.860,1243.581|1110.800,1207.587|138.120x71.988|high|8|8|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0210|PV_GM19_SILVER_MPV_NEAR_FIELD|129|269|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|1145.765,1174.396,1293.455,1244.367|1219.610,1209.381|147.690x69.971|high|4|8|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0211|PV_GM19_SILVER_MPV_NEAR_FIELD|131|273|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|1153.612,1176.902,1301.192,1246.322|1227.402,1211.612|147.580x69.420|high|8|4|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0212|PV_GM19_SILVER_MPV_NEAR_FIELD|138|288|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|1184.225,1174.411,1331.705,1246.411|1257.965,1210.411|147.480x72.000|high|2|8|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0213|PV_GM19_SILVER_MPV_NEAR_FIELD|139|290|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|ANCHOR_CONFIRMED|1194.080,1169.575,1341.760,1245.122|1267.920,1207.349|147.680x75.547|high|3|2|same_vehicle_visible_response_confirmed|光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。|
|WGV35A_PAIR_0214|PV_GM19_GRAY_CAR_LEFT_EDGE|151|315|SAR_MASK_S2_CENTER_CENSORED|ANCHOR_WEAK|960.920,1189.494,1105.330,1264.106|1033.125,1226.800|144.410x74.612|high|0|0|pressure_vehicle_short_or_edge_observation|SAR局部响应可见，但光学状态为压力/边缘/短段条件；只能作为压力审计，不进入A1主传播。|
|WGV35A_PAIR_0215|PV_GM19_GRAY_CAR_LEFT_EDGE|152|317|SAR_MASK_S2_CENTER_CENSORED|ANCHOR_WEAK|969.999,1190.234,1114.470,1264.766|1042.235,1227.500|144.471x74.532|high|0|0|pressure_vehicle_short_or_edge_observation|SAR局部响应可见，但光学状态为压力/边缘/短段条件；只能作为压力审计，不进入A1主传播。|

## Bidirectional Closure

|interval_id|physical_vehicle_id|start_pair_id|end_pair_id|start_sar_frame|end_sar_frame|gap_frames|forward_status|backward_status|closure_status|mid_frame|mid_region_overlap|mid_center_distance_px|identity_consistent|visible_response_coverage|search_ratio_median|review_cn|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|WGV35A_PAIR_0204_TO_WGV35A_PAIR_0205|PV_GM19_WHITE_SUV_NEAR_FIELD|WGV35A_PAIR_0204|WGV35A_PAIR_0205|27|31|4|PROPAGATED_WEAK|PROPAGATED_CONFIDENT|BIDIRECTIONAL_CLOSED|29|0.737974|10.889085|true|0.996128|0.023264|双向局部响应在短间隔内可闭合，区域覆盖mask内可见响应；不使用完整车辆中心。|
|WGV35A_PAIR_0205_TO_WGV35A_PAIR_0206|PV_GM19_WHITE_SUV_NEAR_FIELD|WGV35A_PAIR_0205|WGV35A_PAIR_0206|31|77|46|REVIEW_REQUIRED|REVIEW_REQUIRED|BIDIRECTIONAL_PARTIAL|54|0.093964|135.771239|true||0.022825|长间隔或局部响应弱化导致只能部分闭合，需要后续A2机制固化或人工复核。|
|WGV35A_PAIR_0206_TO_WGV35A_PAIR_0207|PV_GM19_WHITE_SUV_NEAR_FIELD|WGV35A_PAIR_0206|WGV35A_PAIR_0207|77|81|4|PROPAGATED_WEAK|PROPAGATED_WEAK|BIDIRECTIONAL_CLOSED|79|0.823644|11.158358|true|0.96822|0.022778|双向局部响应在短间隔内可闭合，区域覆盖mask内可见响应；不使用完整车辆中心。|
|WGV35A_PAIR_0208_TO_WGV35A_PAIR_0209|PV_GM19_SILVER_MPV_NEAR_FIELD|WGV35A_PAIR_0208|WGV35A_PAIR_0209|212|238|26|REVIEW_REQUIRED|REVIEW_REQUIRED|BIDIRECTIONAL_PARTIAL|225|0.603346|33.30011|true||0.022125|长间隔或局部响应弱化导致只能部分闭合，需要后续A2机制固化或人工复核。|
|WGV35A_PAIR_0209_TO_WGV35A_PAIR_0210|PV_GM19_SILVER_MPV_NEAR_FIELD|WGV35A_PAIR_0209|WGV35A_PAIR_0210|238|269|31|REVIEW_REQUIRED|REVIEW_REQUIRED|BIDIRECTIONAL_PARTIAL|253|0.352727|59.836125|true||0.020232|长间隔或局部响应弱化导致只能部分闭合，需要后续A2机制固化或人工复核。|
|WGV35A_PAIR_0210_TO_WGV35A_PAIR_0211|PV_GM19_SILVER_MPV_NEAR_FIELD|WGV35A_PAIR_0210|WGV35A_PAIR_0211|269|273|4|PROPAGATED_CONFIDENT|PROPAGATED_WEAK|BIDIRECTIONAL_CLOSED|271|0.630465|18.794202|true|0.91765|0.020453|双向局部响应在短间隔内可闭合，区域覆盖mask内可见响应；不使用完整车辆中心。|
|WGV35A_PAIR_0211_TO_WGV35A_PAIR_0212|PV_GM19_SILVER_MPV_NEAR_FIELD|WGV35A_PAIR_0211|WGV35A_PAIR_0212|273|288|15|REVIEW_REQUIRED|REVIEW_REQUIRED|BIDIRECTIONAL_PARTIAL|280|0.980657|1.387244|true||0.020662|长间隔或局部响应弱化导致只能部分闭合，需要后续A2机制固化或人工复核。|
|WGV35A_PAIR_0212_TO_WGV35A_PAIR_0213|PV_GM19_SILVER_MPV_NEAR_FIELD|WGV35A_PAIR_0212|WGV35A_PAIR_0213|288|290|2|PROPAGATED_WEAK|PROPAGATED_WEAK|BIDIRECTIONAL_CLOSED|289|0.88315|6.631148|true|0.929834|0.021331|双向局部响应在短间隔内可闭合，区域覆盖mask内可见响应；不使用完整车辆中心。|