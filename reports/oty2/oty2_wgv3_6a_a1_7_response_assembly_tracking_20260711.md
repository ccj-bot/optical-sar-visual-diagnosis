# OTY2 WGV3.6A-A1.7 Response Assembly Tracking

## Boundary

- requested start commit: `325bc393f8514377b34f7c6cc014e128cbb21417`
- frozen predictions SHA256: `96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb`
- generate/evaluate separation: `PASS`
- A1.6 original outputs modified: `false`
- hidden target boxes loaded during generate: `false`
- optical relation used for filtering: `false`
- GM_RM011 executed: `false`

## Metric Rename

- A1.6 `first_lost_frame` is renamed here to `first_uncertain_frame`.
- `first_uncertain_frame`: first `missing_observation`, `ambiguous_response`, `missing_assembly`, or `ambiguous_assemblies` frame.
- `first_irrecoverable_frame`: first uncertain run of K frames with no later confirmed assembly before evaluation endpoint. Frozen K=`3`; sensitivity K=2/3/5 is reported.
- `response_switch_event` is not reused as a reliable switch metric; A1.7 reports `association_discontinuity` and leaves `identity_contamination=NOT_TESTED`.

## Source Assemblies

| experiment_id | source_pair_id | source_sar_frame | source_component_count | assembly_envelope | azimuth_span | radial_span | frozen_predictions_sha256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ_0204_TO_0205 | WGV35A_PAIR_0204 | 27 | 1 | 1038.000,1155.000,1169.000,1235.000 | 0 | 0 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0205_TO_0206 | WGV35A_PAIR_0205 | 31 | 3 | 1040.000,1159.000,1168.000,1247.000 | 32.775274 | 14.698288 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0206_TO_0207 | WGV35A_PAIR_0206 | 77 | 3 | 1170.000,1157.000,1346.000,1256.000 | 19.736439 | 76.131195 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0208_TO_0209 | WGV35A_PAIR_0208 | 212 | 1 | 961.000,1150.000,1105.000,1246.000 | 0 | 0 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0209_TO_0210 | WGV35A_PAIR_0209 | 238 | 1 | 1051.000,1159.000,1171.000,1255.000 | 0 | 0 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0210_TO_0211 | WGV35A_PAIR_0210 | 269 | 2 | 1131.000,1162.000,1275.000,1250.000 | 7.373184 | 41.900513 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0211_TO_0212 | WGV35A_PAIR_0211 | 273 | 3 | 1139.000,1164.000,1283.000,1252.000 | 28.335651 | 49.788818 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| ADJ_0212_TO_0213 | WGV35A_PAIR_0212 | 288 | 3 | 1170.000,1162.000,1306.000,1242.000 | 13.268406 | 57.04628 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| OPEN_WHITE_0204_TO_0207 | WGV35A_PAIR_0204 | 27 | 1 | 1038.000,1155.000,1169.000,1235.000 | 0 | 0 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |
| OPEN_SILVER_0208_TO_0213 | WGV35A_PAIR_0208 | 212 | 1 | 961.000,1150.000,1105.000,1246.000 | 0 | 0 | 96cf4920e47b0a0d8b6e9e6776ea179a71b1b2b5d6827e79d60703b2d83965bb |

## Method Summary

| method | adjacent_count | coverage_median | center_error_median | confirmed | ambiguous | missing | recoveries | discontinuities | search_ratio_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 8 | 0.818472 | 21.318155 | 0 | 0 | 0 | 0 | 0 | 0.004161 |
| C1 | 8 | 0.818472 | 21.318155 | 5 | 127 | 0 | 0 | 0 | 0.013267 |
| C1A | 8 | 1 | 163.52594 | 114 | 18 | 0 | 0 | 1 | 0.122605 |
| C1B | 8 | 1 | 127.886539 | 116 | 16 | 0 | 7 | 1 | 0.117073 |

## Adjacent Hidden Targets

| experiment_id | method | hidden_target_pair_id | sar_frame | hidden_target_coverage | hidden_target_iou | prediction_center_to_visible_response_center | first_uncertain_frame | first_irrecoverable_frame_k3 | ambiguous_assembly_frames | ambiguity_recovery_count | association_discontinuity_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ_0204_TO_0205 | C0 | WGV35A_PAIR_0205 | 31 | 1 | 0.8563 | 8.499648 |  |  | 0 | 0 | 0 |
| ADJ_0204_TO_0205 | C1 | WGV35A_PAIR_0205 | 31 | 1 | 0.8563 | 8.499648 | 28 | 28 | 4 | 0 | 0 |
| ADJ_0204_TO_0205 | C1A | WGV35A_PAIR_0205 | 31 | 1 | 0.097688 | 83.691418 | 30 |  | 2 | 0 | 0 |
| ADJ_0204_TO_0205 | C1B | WGV35A_PAIR_0205 | 31 | 1 | 0.097688 | 83.691418 | 30 |  | 2 | 0 | 0 |
| ADJ_0205_TO_0206 | C0 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 197.11602 |  |  | 0 | 0 | 0 |
| ADJ_0205_TO_0206 | C1 | WGV35A_PAIR_0206 | 77 | 0 | 0 | 101.100419 | 32 | 46 | 45 | 0 | 0 |
| ADJ_0205_TO_0206 | C1A | WGV35A_PAIR_0206 | 77 | 1 | 0.005021 | 583.635628 | 33 |  | 5 | 0 | 1 |
| ADJ_0205_TO_0206 | C1B | WGV35A_PAIR_0206 | 77 | 1 | 0.005021 | 583.635628 | 33 |  | 5 | 1 | 1 |
| ADJ_0206_TO_0207 | C0 | WGV35A_PAIR_0207 | 81 | 0.898568 | 0.736034 | 12.049722 |  |  | 0 | 0 | 0 |
| ADJ_0206_TO_0207 | C1 | WGV35A_PAIR_0207 | 81 | 0.898568 | 0.736034 | 12.049722 | 78 | 78 | 4 | 0 | 0 |
| ADJ_0206_TO_0207 | C1A | WGV35A_PAIR_0207 | 81 | 1 | 0.124725 | 86.499358 | 78 |  | 1 | 0 | 0 |
| ADJ_0206_TO_0207 | C1B | WGV35A_PAIR_0207 | 81 | 1 | 0.124725 | 86.499358 | 78 |  | 1 | 1 | 0 |
| ADJ_0208_TO_0209 | C0 | WGV35A_PAIR_0209 | 238 | 0.373204 | 0.192907 | 96.663416 |  |  | 0 | 0 | 0 |
| ADJ_0208_TO_0209 | C1 | WGV35A_PAIR_0209 | 238 | 0.494538 | 0.272728 | 54.357845 | 213 |  | 24 | 0 | 0 |
| ADJ_0208_TO_0209 | C1A | WGV35A_PAIR_0209 | 238 | 1 | 0.0433 | 167.219731 | 227 | 235 | 5 | 0 | 0 |
| ADJ_0208_TO_0209 | C1B | WGV35A_PAIR_0209 | 238 | 1 | 0.118414 | 61.592196 | 227 |  | 3 | 2 | 0 |
| ADJ_0209_TO_0210 | C0 | WGV35A_PAIR_0210 | 269 | 0.228262 | 0.131647 | 108.824796 |  |  | 0 | 0 | 0 |
| ADJ_0209_TO_0210 | C1 | WGV35A_PAIR_0210 | 269 | 0.448232 | 0.296072 | 49.70154 | 239 |  | 29 | 0 | 0 |
| ADJ_0209_TO_0210 | C1A | WGV35A_PAIR_0210 | 269 | 1 | 0.004303 | 541.930623 | 243 |  | 3 | 0 | 0 |
| ADJ_0209_TO_0210 | C1B | WGV35A_PAIR_0210 | 269 | 1 | 0.004303 | 541.930623 | 243 |  | 3 | 2 | 0 |
| ADJ_0210_TO_0211 | C0 | WGV35A_PAIR_0211 | 273 | 0.920889 | 0.846561 | 8.104961 |  |  | 0 | 0 | 0 |
| ADJ_0210_TO_0211 | C1 | WGV35A_PAIR_0211 | 273 | 0.920889 | 0.846561 | 8.104961 | 270 | 270 | 4 | 0 | 0 |
| ADJ_0210_TO_0211 | C1A | WGV35A_PAIR_0211 | 273 | 1 | 0.047785 | 159.83215 | 273 |  | 1 | 0 | 0 |
| ADJ_0210_TO_0211 | C1B | WGV35A_PAIR_0211 | 273 | 1 | 0.047785 | 159.83215 | 273 |  | 1 | 0 | 0 |
| ADJ_0211_TO_0212 | C0 | WGV35A_PAIR_0212 | 288 | 0.764685 | 0.637165 | 30.586588 |  |  | 0 | 0 | 0 |
| ADJ_0211_TO_0212 | C1 | WGV35A_PAIR_0212 | 288 | 0.764685 | 0.637165 | 30.586588 | 274 | 274 | 15 | 0 | 0 |
| ADJ_0211_TO_0212 | C1A | WGV35A_PAIR_0212 | 288 | 1 | 0.003924 | 576.344788 | 276 |  | 1 | 0 | 0 |
| ADJ_0211_TO_0212 | C1B | WGV35A_PAIR_0212 | 288 | 1 | 0.003924 | 576.344788 | 276 |  | 1 | 1 | 0 |
| ADJ_0212_TO_0213 | C0 | WGV35A_PAIR_0213 | 290 | 0.872259 | 0.808022 | 10.415418 |  |  | 0 | 0 | 0 |
| ADJ_0212_TO_0213 | C1 | WGV35A_PAIR_0213 | 290 | 0.872259 | 0.808022 | 10.415418 | 289 |  | 2 | 0 | 0 |
| ADJ_0212_TO_0213 | C1A | WGV35A_PAIR_0213 | 290 | 0.786596 | 0.152664 | 95.940929 |  |  | 0 | 0 | 0 |
| ADJ_0212_TO_0213 | C1B | WGV35A_PAIR_0213 | 290 | 0.786596 | 0.152664 | 95.940929 |  |  | 0 | 0 | 0 |

## Open Loop

| experiment_id | method | hidden_target_pair_id | sar_frame | hidden_target_coverage | prediction_center_to_visible_response_center | first_uncertain_frame | first_irrecoverable_frame_k3 | ambiguous_assembly_frames | ambiguity_recovery_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPEN_WHITE_0204_TO_0207 | C0 | WGV35A_PAIR_0205 | 31 | 1 | 8.499648 |  |  | 0 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0205 | 31 | 1 | 8.499648 | 28 | 28 | 4 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1A | WGV35A_PAIR_0205 | 31 | 1 | 83.691418 | 30 |  | 2 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1B | WGV35A_PAIR_0205 | 31 | 1 | 83.691418 | 30 |  | 2 | 0 |
| OPEN_WHITE_0204_TO_0207 | C0 | WGV35A_PAIR_0206 | 77 | 0 | 205.47647 |  |  | 0 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0206 | 77 | 0.0046 | 91.740749 | 28 | 46 | 49 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1A | WGV35A_PAIR_0206 | 77 | 1 | 583.635628 | 30 |  | 3 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1B | WGV35A_PAIR_0206 | 77 | 1 | 583.635628 | 30 |  | 3 | 2 |
| OPEN_WHITE_0204_TO_0207 | C0 | WGV35A_PAIR_0207 | 81 | 0 | 215.343475 |  |  | 0 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1 | WGV35A_PAIR_0207 | 81 | 0 | 100.928516 | 28 | 46 | 53 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1A | WGV35A_PAIR_0207 | 81 | 1 | 585.549552 | 30 |  | 3 | 0 |
| OPEN_WHITE_0204_TO_0207 | C1B | WGV35A_PAIR_0207 | 81 | 1 | 585.549552 | 30 |  | 3 | 2 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0209 | 238 | 0.373204 | 96.663416 |  |  | 0 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0209 | 238 | 0.494538 | 54.357845 | 213 |  | 24 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0209 | 238 | 1 | 167.219731 | 227 |  | 5 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0209 | 238 | 1 | 61.592196 | 227 |  | 3 | 2 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0210 | 269 | 0 | 205.468723 |  |  | 0 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0210 | 269 | 0 | 279.647929 | 213 |  | 47 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0210 | 269 | 1 | 541.930623 | 227 |  | 5 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0210 | 269 | 1 | 541.930623 | 227 |  | 6 | 3 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0211 | 273 | 0 | 213.332439 |  |  | 0 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0211 | 273 | 0 | 331.910669 | 213 | 269 | 51 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0211 | 273 | 1 | 551.95311 | 227 |  | 5 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0211 | 273 | 1 | 551.95311 | 227 |  | 6 | 3 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0212 | 288 | 0 | 243.837424 |  |  | 0 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0212 | 288 | 0 | 590.424162 | 213 |  | 61 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0212 | 288 | 1 | 576.344788 | 227 |  | 5 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0212 | 288 | 1 | 576.344788 | 227 |  | 6 | 3 |
| OPEN_SILVER_0208_TO_0213 | C0 | WGV35A_PAIR_0213 | 290 | 0 | 253.721373 |  |  | 0 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1 | WGV35A_PAIR_0213 | 290 | 0 | 640.645778 | 213 | 287 | 63 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1A | WGV35A_PAIR_0213 | 290 | 1 | 566.216099 | 227 |  | 5 | 0 |
| OPEN_SILVER_0208_TO_0213 | C1B | WGV35A_PAIR_0213 | 290 | 1 | 566.216099 | 227 |  | 6 | 3 |

## Delta Audit

| comparison | experiment_id | experiment_type | physical_vehicle_id | hidden_target_pair_id | sar_frame | coverage_delta | iou_delta | center_error_delta | search_ratio_delta | ambiguity_delta | verdict | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1A_minus_C1 | ADJ_0204_TO_0205 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | 0 | -0.758612 | -75.19177 | 0.041792 | -2 | harmed | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0204_TO_0205 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | 0 | -0.758612 | -75.19177 | 0.041792 | -2 | harmed | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0205_TO_0206 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 1 | 0.005021 | -482.535209 | 1.157858 | -40 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0205_TO_0206 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 1 | 0.005021 | -482.535209 | 1.157858 | -40 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0206_TO_0207 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 0.101432 | -0.611309 | -74.449636 | 0.094206 | -3 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0206_TO_0207 | adjacent_hidden_anchor | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 0.101432 | -0.611309 | -74.449636 | 0.094206 | -3 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0208_TO_0209 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | 0.505462 | -0.229428 | -112.861886 | 0.105048 | -19 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0208_TO_0209 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | 0.505462 | -0.154314 | -7.234351 | 0.048647 | -21 | coverage_only_broad_assembly | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0209_TO_0210 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 0.551768 | -0.291769 | -492.229083 | 1.158853 | -26 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0209_TO_0210 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 0.551768 | -0.291769 | -492.229083 | 1.158853 | -26 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0210_TO_0211 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 0.079111 | -0.798776 | -151.727189 | 0.11275 | -3 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0210_TO_0211 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 0.079111 | -0.798776 | -151.727189 | 0.11275 | -3 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0211_TO_0212 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 0.235315 | -0.633241 | -545.7582 | 1.15861 | -14 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0211_TO_0212 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 0.235315 | -0.633241 | -545.7582 | 1.15861 | -14 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | ADJ_0212_TO_0213 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | -0.085663 | -0.655358 | -85.525511 | 0.011159 | -2 | harmed | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | ADJ_0212_TO_0213 | adjacent_hidden_anchor | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | -0.085663 | -0.655358 | -85.525511 | 0.011159 | -2 | harmed | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | 0 | -0.758612 | -75.19177 | 0.041792 | -2 | harmed | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0205 | 31 | 0 | -0.758612 | -75.19177 | 0.041792 | -2 | harmed | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 0.9954 | 0.002769 | -491.894879 | 1.156556 | -46 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0206 | 77 | 0.9954 | 0.002769 | -491.894879 | 1.156556 | -46 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 1 | 0.004394 | -484.621036 | 1.156556 | -50 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_WHITE_0204_TO_0207 | open_loop | PV_GM19_WHITE_SUV_NEAR_FIELD | WGV35A_PAIR_0207 | 81 | 1 | 0.004394 | -484.621036 | 1.156556 | -50 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | 0.505462 | -0.229428 | -112.861886 | 0.105048 | -19 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0209 | 238 | 0.505462 | -0.154314 | -7.234351 | 0.048647 | -21 | coverage_only_broad_assembly | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 1 | 0.004303 | -262.282694 | 1.156796 | -42 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0210 | 269 | 1 | 0.004303 | -262.282694 | 1.156796 | -41 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 1 | 0.00434 | -220.042441 | 1.156796 | -46 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0211 | 273 | 1 | 0.00434 | -220.042441 | 1.156796 | -45 | harmed_area_expansion | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 1 | 0.003924 | 14.079374 | 1.156796 | -56 | neutral | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0212 | 288 | 1 | 0.003924 | 14.079374 | 1.156796 | -55 | neutral | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1A_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | 1 | 0.003971 | 74.429679 | 1.156796 | -58 | neutral | Positive center_error_delta means assembly method is closer than A1.6 C1. |
| C1B_minus_C1 | OPEN_SILVER_0208_TO_0213 | open_loop | PV_GM19_SILVER_MPV_NEAR_FIELD | WGV35A_PAIR_0213 | 290 | 1 | 0.003971 | 74.429679 | 1.156796 | -57 | neutral | Positive center_error_delta means assembly method is closer than A1.6 C1. |

## Optical Bypass Summary

- optical azimuth trend relation support ratio: `0.616117`
- optical radial trend relation support ratio: `0.581646`
- +/-1 SAR frame sensitivity is recorded in the optical bypass CSV; optical did not delete any SAR assembly.

## Visual Self Review

- `outputs/wgv3_6a_a1_7_20260711/a1_7_priority_short_interval_runtime_assemblies.png`: runtime view without hidden boxes.
- `outputs/wgv3_6a_a1_7_20260711/a1_7_priority_short_interval_eval_only_overlay.png`: EVAL_ONLY target overlay.
- `outputs/wgv3_6a_a1_7_20260711/a1_7_c1a_c1b_difference_examples.png`: C1A/C1B differences.
- `outputs/wgv3_6a_a1_7_20260711/a1_7_open_loop_eval_only_overlay.png`: open-loop EVAL_ONLY overlay.

Chinese judgements:

- ADJ_0204_TO_0205 的 C1A 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。
- ADJ_0204_TO_0205 的 C1B 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。
- ADJ_0206_TO_0207 的 C1A 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。
- ADJ_0206_TO_0207 的 C1B 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。
- ADJ_0210_TO_0211 的 C1A 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。
- ADJ_0210_TO_0211 的 C1B 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。

## Gate Verdicts

- `ASSEMBLY_SEMANTICS_SUPPORTED`: `YES`
- `ASSEMBLY_REDUCES_FALSE_AMBIGUITY`: `PARTIAL`
- `TEMPORAL_DELAYED_CONFIRMATION_ADDED_VALUE`: `PARTIAL`
- `ASSOCIATION_DISCONTINUITY_MEASURED`: `PASS`
- `OPTICAL_AZIMUTH_RELATION_SUPPORTED`: `DIAGNOSTIC_ONLY_PARTIAL`
- `OPTICAL_RADIAL_RELATION_SUPPORTED`: `DIAGNOSTIC_ONLY_PARTIAL`
- `A1.7_CAUSAL_ASSOCIATION_READY`: `NO`
- `INTERMEDIATE_FRAME_BLIND_EVAL_PENDING`: `true`
- `GM_RM011_BLOCKED`: `true`

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_7_response_assembly_tracking_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_source_assembly_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_component_graph_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_response_assembly_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_frozen_predictions_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_hidden_anchor_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_c1_c1a_c1b_delta_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_optical_sar_trend_bypass_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_7_failure_cases_20260711.csv`

## Next Step

Do not run GM_RM011. If A1.7 is not ready, repair assembly association and add independent intermediate-frame blind evaluation before any pressure-test expansion.