# OTY2 WGV3.6A-A1.7R Bounded Hypothesis Tracking

## Boundary

- requested start commit: `4505b6af636c576b7f447a2409798ee5c9dfc249`
- frozen predictions SHA256: `6c3248d18061eb0919ae5d295ef577c2da145f6a2547c07e48f63bc06208ccc9`
- generate/evaluate separation: `PASS`
- A1.6 original outputs modified: `false`
- A1.7 historical outputs modified: `false`
- hidden target boxes loaded during generate: `false`
- multiple hypotheses unioned into prediction_region: `false`
- optical relation used for filtering: `false`
- GM_RM011 executed: `false`

## Corrected A1.7 Claims

| claim | original_status | corrected_status | code_evidence | metric_evidence | reason_cn |
| --- | --- | --- | --- | --- | --- |
| ASSEMBLY_SEMANTICS_SUPPORTED | YES | MULTI_COMPONENT_RESPONSE_HYPOTHESIS_SUPPORTED_ONLY | A1.7 used connected graph assemblies and could merge components into broad envelopes; A1.7R separates compact assemblies from hypothesis sets. | A1.7 C1A/C1B median center error 163.5/127.9 px with search ratio 0.1226/0.1171. | A1.7 只能支持多分量响应假设，不能证明组合体语义已经被真实视觉验证。 |
| ASSEMBLY_REDUCES_FALSE_AMBIGUITY | PARTIAL | NO_AS_PRIMARY_SUCCESS_CRITERION | A1.7R marks ambiguous_hypothesis_set with empty prediction_region and never unions branches. | A1.7 ambiguity下降伴随搜索比例扩大到约 0.12，远高于 C1 的 0.013。 | 歧义数量下降主要来自区域膨胀，不是可接受的因果关联修复。 |
| TEMPORAL_DELAYED_CONFIRMATION_ADDED_VALUE | PARTIAL | NOT_VALIDATED_UNTIL_PERSISTENT_BRANCH_RECOVERY | A1.7R counts true_ambiguity_recovery only after independent compact branches collapse by continuity without area expansion. | A1.7 C1B recovery count was 7 but allowed broad corridor behavior. | 延迟确认必须来自持久小分支连续性，不能来自大包络或算法性坍缩。 |
| ASSOCIATION_DISCONTINUITY_MEASURED | PASS | MEASURED_ONLY_FOR_PERSISTENT_COMPACT_BRANCHES | A1.7R outputs persistent_hypothesis_id and branch events. | A1.7 only reported 1 discontinuity for C1A/C1B under broad assemblies. | 关联不连续必须基于持久分支，而不是大包络 IoU。 |
| OPTICAL_AZIMUTH_RELATION_SUPPORTED | DIAGNOSTIC_ONLY_PARTIAL | POLAR_DIAGNOSTIC_ONLY_RETEST_REQUIRED | A1.7R uses build_geometry() assembly_azimuth instead of image x/y naming. | A1.7 x/y-based azimuth support was 0.616117 and was not stable enough for filtering. | 必须用真实极坐标方位重新诊断，仍不得参与过滤。 |
| OPTICAL_RADIAL_RELATION_SUPPORTED | DIAGNOSTIC_ONLY_PARTIAL | POLAR_DIAGNOSTIC_ONLY_RETEST_REQUIRED | A1.7R uses build_geometry() assembly_radial and excludes ambiguous unions. | A1.7 x/y-based radial support was 0.581646 and同步扰动敏感。 | 径向关系需要真实极坐标和紧凑分支过滤后重新判断。 |
| MULTI_COMPONENT_RESPONSE_HYPOTHESIS_SUPPORTED | not_separated | SUPPORTED_AS_HYPOTHESIS | source anchors contain multi-component cases and A1.7R traces compact groups separately. | A1.7 source average component count was 1.9. | 多分量现象存在，但只是待验证假设。 |
| ASSEMBLY_SEMANTICS_VISUALLY_VALIDATED | not_separated | NOT_YET_GLOBAL_VALIDATED | A1.7R visual review rows are explicit and non-circular. | visual review distinguishes same-vehicle compact cores, background scatter, and uncertain rows. | 只有经实际图像审阅的局部窗口可作为视觉语义证据，不能由 coverage 自动推出。 |

## Method Summary

| method | target_count | unique_confirmed_target_count | coverage_median | center_error_median | single_search_ratio_median | total_search_ratio_median | ambiguous_hypothesis_set_frames | budget_exceeded_frames | true_recovery | branch_collapse | discontinuities |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 8 | 8 | 0.818472 | 21.318155 | 0.013267 | 0.013267 | 127 | 0 | 0 | 0 | 0 |
| C1A | 8 | 8 | 1 | 163.52594 | 0.122606 | 0.122606 | 18 | 0 | 0 | 0 | 1 |
| C1B | 8 | 8 | 1 | 127.886536 | 0.117073 | 0.117073 | 16 | 0 | 7 | 0 | 1 |
| C1C | 8 | 1 | 0 | 308.761963 | 0.015096 | 0.015096 | 40 | 0 | 0 | 0 | 0 |
| C1D | 8 | 0 |  |  | 0.015188 | 0.044496 | 7 | 79 | 4 | 0 | 0 |

## Adjacent Evaluation

| experiment_id | method | hidden_target_pair_id | sar_frame | prediction_status | localization_metric_included | hidden_target_coverage | prediction_center_to_visible_response_center | hypothesis_count | total_search_ratio | first_irrecoverable_frame |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ_0204_TO_0205 | C1 | WGV35A_PAIR_0205 | 31 | A1.7_reference | true | 1 | 8.499648 |  | 0.014824 | 28 |
| ADJ_0204_TO_0205 | C1A | WGV35A_PAIR_0205 | 31 | A1.7_reference | true | 1 | 83.691418 |  | 0.056616 |  |
| ADJ_0204_TO_0205 | C1B | WGV35A_PAIR_0205 | 31 | A1.7_reference | true | 1 | 83.691418 |  | 0.056616 |  |
| ADJ_0205_TO_0206 | C1 | WGV35A_PAIR_0206 | 77 | A1.7_reference | true | 0 | 101.100419 |  | 0.013522 | 46 |
| ADJ_0205_TO_0206 | C1A | WGV35A_PAIR_0206 | 77 | A1.7_reference | true | 1 | 583.635628 |  | 1.17138 |  |
| ADJ_0205_TO_0206 | C1B | WGV35A_PAIR_0206 | 77 | A1.7_reference | true | 1 | 583.635628 |  | 1.17138 |  |
| ADJ_0206_TO_0207 | C1 | WGV35A_PAIR_0207 | 81 | A1.7_reference | true | 0.898568 | 12.049722 |  | 0.01436 | 78 |
| ADJ_0206_TO_0207 | C1A | WGV35A_PAIR_0207 | 81 | A1.7_reference | true | 1 | 86.499358 |  | 0.108566 |  |
| ADJ_0206_TO_0207 | C1B | WGV35A_PAIR_0207 | 81 | A1.7_reference | true | 1 | 86.499358 |  | 0.108566 |  |
| ADJ_0208_TO_0209 | C1 | WGV35A_PAIR_0209 | 238 | A1.7_reference | true | 0.494538 | 54.357845 |  | 0.014584 |  |
| ADJ_0208_TO_0209 | C1A | WGV35A_PAIR_0209 | 238 | A1.7_reference | true | 1 | 167.219731 |  | 0.119632 | 235 |
| ADJ_0208_TO_0209 | C1B | WGV35A_PAIR_0209 | 238 | A1.7_reference | true | 1 | 61.592196 |  | 0.063231 |  |
| ADJ_0209_TO_0210 | C1 | WGV35A_PAIR_0210 | 269 | A1.7_reference | true | 0.448232 | 49.70154 |  | 0.012527 |  |
| ADJ_0209_TO_0210 | C1A | WGV35A_PAIR_0210 | 269 | A1.7_reference | true | 1 | 541.930623 |  | 1.17138 |  |
| ADJ_0209_TO_0210 | C1B | WGV35A_PAIR_0210 | 269 | A1.7_reference | true | 1 | 541.930623 |  | 1.17138 |  |
| ADJ_0210_TO_0211 | C1 | WGV35A_PAIR_0211 | 273 | A1.7_reference | true | 0.920889 | 8.104961 |  | 0.012829 | 270 |
| ADJ_0210_TO_0211 | C1A | WGV35A_PAIR_0211 | 273 | A1.7_reference | true | 1 | 159.83215 |  | 0.125579 |  |
| ADJ_0210_TO_0211 | C1B | WGV35A_PAIR_0211 | 273 | A1.7_reference | true | 1 | 159.83215 |  | 0.125579 |  |
| ADJ_0211_TO_0212 | C1 | WGV35A_PAIR_0212 | 288 | A1.7_reference | true | 0.764685 | 30.586588 |  | 0.01277 | 274 |
| ADJ_0211_TO_0212 | C1A | WGV35A_PAIR_0212 | 288 | A1.7_reference | true | 1 | 576.344788 |  | 1.17138 |  |
| ADJ_0211_TO_0212 | C1B | WGV35A_PAIR_0212 | 288 | A1.7_reference | true | 1 | 576.344788 |  | 1.17138 |  |
| ADJ_0212_TO_0213 | C1 | WGV35A_PAIR_0213 | 290 | A1.7_reference | true | 0.872259 | 10.415418 |  | 0.013012 |  |
| ADJ_0212_TO_0213 | C1A | WGV35A_PAIR_0213 | 290 | A1.7_reference | true | 0.786596 | 95.940929 |  | 0.024171 |  |
| ADJ_0212_TO_0213 | C1B | WGV35A_PAIR_0213 | 290 | A1.7_reference | true | 0.786596 | 95.940929 |  | 0.024171 |  |
| ADJ_0204_TO_0205 | C1C | WGV35A_PAIR_0205 | 31 | ambiguous_hypothesis_set | false |  |  | 3 | 0.015625 | 28 |
| ADJ_0204_TO_0205 | C1D | WGV35A_PAIR_0205 | 31 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false |  |  | 0 | 0.062485 | 28 |
| ADJ_0205_TO_0206 | C1C | WGV35A_PAIR_0206 | 77 | missing_compact_assembly | false |  |  | 0 | 0.010381 | 59 |
| ADJ_0205_TO_0206 | C1D | WGV35A_PAIR_0206 | 77 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false |  |  | 0 | 0.045453 | 32 |
| ADJ_0206_TO_0207 | C1C | WGV35A_PAIR_0207 | 81 | ambiguous_hypothesis_set | false |  |  | 3 | 0.015901 | 78 |
| ADJ_0206_TO_0207 | C1D | WGV35A_PAIR_0207 | 81 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false |  |  | 0 | 0.063603 | 78 |
| ADJ_0208_TO_0209 | C1C | WGV35A_PAIR_0209 | 238 | missing_compact_assembly | false |  |  | 0 | 0.01702 | 226 |
| ADJ_0208_TO_0209 | C1D | WGV35A_PAIR_0209 | 238 | missing_compact_assembly | false |  |  | 0 | 0.01702 | 226 |
| ADJ_0209_TO_0210 | C1C | WGV35A_PAIR_0210 | 269 | confirmed_unique | true | 0 | 308.761958 | 1 | 0.014513 |  |
| ADJ_0209_TO_0210 | C1D | WGV35A_PAIR_0210 | 269 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false |  |  | 0 | 0.043538 | 239 |
| ADJ_0210_TO_0211 | C1C | WGV35A_PAIR_0211 | 273 | missing_compact_assembly | false |  |  | 0 | 0.014967 | 272 |
| ADJ_0210_TO_0211 | C1D | WGV35A_PAIR_0211 | 273 | missing_compact_assembly | false |  |  | 0 | 0.014967 | 270 |
| ADJ_0211_TO_0212 | C1C | WGV35A_PAIR_0212 | 288 | missing_compact_assembly | false |  |  | 0 | 0.014885 | 278 |
| ADJ_0211_TO_0212 | C1D | WGV35A_PAIR_0212 | 288 | missing_compact_assembly | false |  |  | 0 | 0.014885 | 278 |
| ADJ_0212_TO_0213 | C1C | WGV35A_PAIR_0213 | 290 | ambiguous_hypothesis_set | false |  |  | 3 | 0.015224 | 289 |
| ADJ_0212_TO_0213 | C1D | WGV35A_PAIR_0213 | 290 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false |  |  | 0 | 0.052995 | 289 |

## Open Loop

| experiment_id | method | hidden_target_pair_id | sar_frame | prediction_status | localization_metric_included | any_hypothesis_covers_target | hypothesis_count | total_search_ratio | first_irrecoverable_frame |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0205 | 31 | A1.7_reference | true |  |  | 0.014824 | 28 |
| OPEN_WHITE_0204_TO_0207 | C1A | WGV35A_PAIR_0205 | 31 | A1.7_reference | true |  |  | 0.056616 |  |
| OPEN_WHITE_0204_TO_0207 | C1B | WGV35A_PAIR_0205 | 31 | A1.7_reference | true |  |  | 0.056616 |  |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0206 | 77 | A1.7_reference | true |  |  | 0.014824 | 46 |
| OPEN_WHITE_0204_TO_0207 | C1A | WGV35A_PAIR_0206 | 77 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_WHITE_0204_TO_0207 | C1B | WGV35A_PAIR_0206 | 77 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0207 | 81 | A1.7_reference | true |  |  | 0.014824 | 46 |
| OPEN_WHITE_0204_TO_0207 | C1A | WGV35A_PAIR_0207 | 81 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_WHITE_0204_TO_0207 | C1B | WGV35A_PAIR_0207 | 81 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0209 | 238 | A1.7_reference | true |  |  | 0.014584 |  |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0209 | 238 | A1.7_reference | true |  |  | 0.119632 |  |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0209 | 238 | A1.7_reference | true |  |  | 0.063231 |  |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0210 | 269 | A1.7_reference | true |  |  | 0.014584 |  |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0210 | 269 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0210 | 269 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0211 | 273 | A1.7_reference | true |  |  | 0.014584 | 269 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0211 | 273 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0211 | 273 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0212 | 288 | A1.7_reference | true |  |  | 0.014584 |  |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0212 | 288 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0212 | 288 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0213 | 290 | A1.7_reference | true |  |  | 0.014584 | 287 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0213 | 290 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0213 | 290 | A1.7_reference | true |  |  | 1.17138 |  |
| OPEN_WHITE_0204_TO_0207 | C1C | WGV35A_PAIR_0205 | 31 | ambiguous_hypothesis_set | false | false | 3 | 0.015625 | 77 |
| OPEN_WHITE_0204_TO_0207 | C1D | WGV35A_PAIR_0205 | 31 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false | false | 0 | 0.062485 | 28 |
| OPEN_WHITE_0204_TO_0207 | C1C | WGV35A_PAIR_0206 | 77 | missing_compact_assembly | false | false | 0 | 0.006517 | 77 |
| OPEN_WHITE_0204_TO_0207 | C1D | WGV35A_PAIR_0206 | 77 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false | false | 0 | 0.062485 | 28 |
| OPEN_WHITE_0204_TO_0207 | C1C | WGV35A_PAIR_0207 | 81 | missing_compact_assembly | false | false | 0 | 0.006517 | 77 |
| OPEN_WHITE_0204_TO_0207 | C1D | WGV35A_PAIR_0207 | 81 | BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED | false | false | 0 | 0.062485 | 28 |
| OPEN_SILVER_0208_TO_0213 | C1C | WGV35A_PAIR_0209 | 238 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1D | WGV35A_PAIR_0209 | 238 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1C | WGV35A_PAIR_0210 | 269 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1D | WGV35A_PAIR_0210 | 269 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1C | WGV35A_PAIR_0211 | 273 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1D | WGV35A_PAIR_0211 | 273 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1C | WGV35A_PAIR_0212 | 288 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1D | WGV35A_PAIR_0212 | 288 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1C | WGV35A_PAIR_0213 | 290 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |
| OPEN_SILVER_0208_TO_0213 | C1D | WGV35A_PAIR_0213 | 290 | missing_compact_assembly | false | false | 0 | 0.01702 | 226 |

## Delta Audit

| comparison | experiment_id | experiment_type | physical_vehicle_id | hidden_target_pair_id | sar_frame | coverage_delta | iou_delta | center_error_delta | search_ratio_delta | area_ratio_delta | verdict | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1C_minus_C1 | ADJ_0204_TO_0205 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 |  |  |  | 0.000801 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0204_TO_0205 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 |  |  |  | 0.047661 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0205_TO_0206 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 |  |  |  | -0.003141 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0205_TO_0206 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 |  |  |  | 0.031931 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0206_TO_0207 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 |  |  |  | 0.001541 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0206_TO_0207 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 |  |  |  | 0.049243 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0208_TO_0209 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0208_TO_0209 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0209_TO_0210 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | -0.448232 | -0.296072 | -259.060418 | 0.001986 | 0.115861 | harmed | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0209_TO_0210 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 |  |  |  | 0.031011 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0210_TO_0211 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 |  |  |  | 0.002138 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0210_TO_0211 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 |  |  |  | 0.002138 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0211_TO_0212 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 |  |  |  | 0.002115 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0211_TO_0212 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 |  |  |  | 0.002115 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | ADJ_0212_TO_0213 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 |  |  |  | 0.002212 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | ADJ_0212_TO_0213 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 |  |  |  | 0.039983 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 |  |  |  | 0.000801 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 |  |  |  | 0.047661 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 |  |  |  | -0.008307 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 |  |  |  | 0.047661 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 |  |  |  | -0.008307 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 |  |  |  | 0.047661 |  | failed_hypothesis_budget | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1C_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |
| C1D_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 |  |  |  | 0.002436 |  | bounded_ambiguous_not_localized | Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization. |

## Visual Semantic Review

- reviewed frames: `27,28,29,30,31,32,40,46,60,77,78,79,80,81,212,213,220,227,238,239,243,250,260,269,270,271,272,273,276,280,284,288,289,290`
- runtime visual sheets:
  - `outputs/wgv3_6a_a1_7r_20260711/a1_7r_white_runtime_full_zoom_review.png`
  - `outputs/wgv3_6a_a1_7r_20260711/a1_7r_silver_runtime_full_zoom_review_a.png`
  - `outputs/wgv3_6a_a1_7r_20260711/a1_7r_silver_runtime_full_zoom_review_b.png`
  - `outputs/wgv3_6a_a1_7r_20260711/a1_7r_branch_budget_summary.png`
- eval-only overlay sheet: `outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png`

| review_id | experiment_id | sar_frame | visual_role | same_vehicle_response | background_response | uncertain | transitive_merge_error | human_multimodal_judgement_cn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIS_001 | ADJ_0204_TO_0205 | 27 | compact_vehicle_core | true | false | false | false | 白色 SUV 近距离响应核心位于扇形底部，主亮斑连续；边缘弱散射可解释为同车多热点，但横向远离的小亮点不应通过传递边并入。 |
| VIS_002 | ADJ_0204_TO_0205 | 28 | compact_vehicle_core | true | false | false | false | 白色 SUV 近距离响应核心位于扇形底部，主亮斑连续；边缘弱散射可解释为同车多热点，但横向远离的小亮点不应通过传递边并入。 |
| VIS_003 | ADJ_0204_TO_0205 | 29 | compact_vehicle_core | true | false | false | false | 白色 SUV 近距离响应核心位于扇形底部，主亮斑连续；边缘弱散射可解释为同车多热点，但横向远离的小亮点不应通过传递边并入。 |
| VIS_004 | ADJ_0204_TO_0205 | 30 | compact_vehicle_core | true | false | false | false | 白色 SUV 近距离响应核心位于扇形底部，主亮斑连续；边缘弱散射可解释为同车多热点，但横向远离的小亮点不应通过传递边并入。 |
| VIS_005 | ADJ_0204_TO_0205 | 31 | compact_vehicle_core | true | false | false | false | 白色 SUV 近距离响应核心位于扇形底部，主亮斑连续；边缘弱散射可解释为同车多热点，但横向远离的小亮点不应通过传递边并入。 |
| VIS_006 | ADJ_0205_TO_0206 | 32 | uncertain_split_or_background | false | false | true | true | 白色 SUV 长间隔中局部亮斑分散，部分回波靠近底部核心但远侧点状响应缺少连续车辆轮廓，不能确认同车。 |
| VIS_007 | ADJ_0205_TO_0206 | 40 | uncertain_split_or_background | false | false | true | true | 白色 SUV 长间隔中局部亮斑分散，部分回波靠近底部核心但远侧点状响应缺少连续车辆轮廓，不能确认同车。 |
| VIS_008 | ADJ_0205_TO_0206 | 46 | uncertain_split_or_background | false | false | true | true | 白色 SUV 长间隔中局部亮斑分散，部分回波靠近底部核心但远侧点状响应缺少连续车辆轮廓，不能确认同车。 |
| VIS_009 | ADJ_0205_TO_0206 | 60 | uncertain_split_or_background | false | false | true | true | 白色 SUV 长间隔中局部亮斑分散，部分回波靠近底部核心但远侧点状响应缺少连续车辆轮廓，不能确认同车。 |
| VIS_010 | ADJ_0206_TO_0207 | 77 | uncertain_split_or_background | false | false | true | true | 白色 SUV 长间隔中局部亮斑分散，部分回波靠近底部核心但远侧点状响应缺少连续车辆轮廓，不能确认同车。 |
| VIS_011 | ADJ_0206_TO_0207 | 78 | compact_vehicle_core | true | false | false | false | 白色 SUV 77-81 段存在可持续的底部紧凑响应核心；应跟随核心小框，而不是吸收远处背景线状散射。 |
| VIS_012 | ADJ_0206_TO_0207 | 79 | compact_vehicle_core | true | false | false | false | 白色 SUV 77-81 段存在可持续的底部紧凑响应核心；应跟随核心小框，而不是吸收远处背景线状散射。 |
| ... |  |  |  |  |  |  |  |  |

## Polar Optical Bypass

- C1C azimuth support: `0.742857`
- C1C radial support: `0.447619`
- C1D azimuth support: `0.888889`
- C1D radial support: `0.444444`
- relation_used_for_filtering: `false` for all rows

## Failure Cases

| case_id | experiment_id | method | physical_vehicle_id | failure_type | sar_frame | first_uncertain_frame | first_irrecoverable_frame | visual_png | chinese_judgement | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FAIL_001 | ADJ_0204_TO_0205 | C1C | PV_GM19_WHITE_SUV_NEAR_FIELD | bounded_hypothesis_not_ready | 31 | 28 | 28 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_002 | ADJ_0204_TO_0205 | C1D | PV_GM19_WHITE_SUV_NEAR_FIELD | bounded_hypothesis_not_ready | 31 | 28 | 28 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_003 | ADJ_0205_TO_0206 | C1C | PV_GM19_WHITE_SUV_NEAR_FIELD | bounded_hypothesis_not_ready | 77 | 32 | 59 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_004 | ADJ_0205_TO_0206 | C1D | PV_GM19_WHITE_SUV_NEAR_FIELD | bounded_hypothesis_not_ready | 77 | 32 | 32 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_005 | ADJ_0206_TO_0207 | C1C | PV_GM19_WHITE_SUV_NEAR_FIELD | bounded_hypothesis_not_ready | 81 | 78 | 78 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_006 | ADJ_0206_TO_0207 | C1D | PV_GM19_WHITE_SUV_NEAR_FIELD | bounded_hypothesis_not_ready | 81 | 78 | 78 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_007 | ADJ_0208_TO_0209 | C1C | PV_GM19_SILVER_MPV_NEAR_FIELD | bounded_hypothesis_not_ready | 238 | 215 | 226 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_008 | ADJ_0208_TO_0209 | C1D | PV_GM19_SILVER_MPV_NEAR_FIELD | bounded_hypothesis_not_ready | 238 | 213 | 226 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_009 | ADJ_0209_TO_0210 | C1C | PV_GM19_SILVER_MPV_NEAR_FIELD | bounded_hypothesis_not_ready | 269 | 240 |  | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_010 | ADJ_0209_TO_0210 | C1D | PV_GM19_SILVER_MPV_NEAR_FIELD | bounded_hypothesis_not_ready | 269 | 239 | 239 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_011 | ADJ_0210_TO_0211 | C1C | PV_GM19_SILVER_MPV_NEAR_FIELD | bounded_hypothesis_not_ready | 273 | 270 | 272 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| FAIL_012 | ADJ_0210_TO_0211 | C1D | PV_GM19_SILVER_MPV_NEAR_FIELD | bounded_hypothesis_not_ready | 273 | 270 | 270 | outputs/wgv3_6a_a1_7r_20260711/a1_7r_eval_only_overlay_review.png | 该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。 | A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction. |
| ... |  |  |  |  |  |  |  |  |  |  |

## Gate Verdicts

- `VISUAL_SEMANTIC_REVIEW_NON_CIRCULAR`: `PASS`
- `COMPACT_ASSEMBLY_SEMANTICS_SUPPORTED`: `PARTIAL`
- `TRANSITIVE_MERGE_CONTROLLED`: `PASS`
- `HYPOTHESIS_SET_BOUNDED`: `PARTIAL_BLOCKED`
- `AREA_EXPANSION_CONTROLLED`: `NO`
- `TRUE_DELAYED_CONFIRMATION_ADDED_VALUE`: `REJECTED_BY_AREA_BUDGET`
- `POLAR_OPTICAL_AZIMUTH_RELATION_SUPPORTED`: `DIAGNOSTIC_ONLY_PARTIAL`
- `POLAR_OPTICAL_RADIAL_RELATION_SUPPORTED`: `DIAGNOSTIC_ONLY_PARTIAL`
- `A1.7R_CAUSAL_ASSOCIATION_READY`: `NO`
- `INTERMEDIATE_FRAME_BLIND_EVAL_PENDING`: `true`
- `GM_RM011_BLOCKED`: `true`

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_7r_bounded_hypothesis_tracking_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_claim_correction_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_visual_semantic_review_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_compact_assembly_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_persistent_hypothesis_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_frozen_predictions_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_hidden_anchor_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_c1c_c1d_delta_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_polar_optical_bypass_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7r_failure_cases_20260711.csv`

## Next Step

Do not run GM_RM011. A1.7R should be treated as a bounded audit until intermediate-frame blind evaluation exists.