# OTY2 WGV3.5A-R2B Anchorless Track-Level Full-Vehicle State Reconstruction

## Method

For each physical vehicle and optical frame, R2B estimates latent state `s_t=(center_x, center_y, full_width, full_height, relative_depth, velocity_x, velocity_y, scale_velocity, depth_velocity)`.

Pseudo-code:

```text
for each physical vehicle:
  estimate robust full_width/full_height from full-stream direct frames if any, else from high-percentile partial observations
  for each frame:
    if right edge is truncated: center_x = observed_left + full_width / 2
    if left edge is truncated:  center_x = observed_right - full_width / 2
    if bottom edge is truncated: center_y = observed_top + full_height / 2
    otherwise: center ~= observed center
    relative_depth uses vehicle-region depth when usable and is smoothed over time
  fit a weighted temporal line to center/depth and blend with per-frame constraints
  never update one physical vehicle with another physical vehicle state
```

## GM_RM017 Controlled No-Anchor Ablation

| scene | method | sample_count | physical_vehicle_count | full_center_x_median_error | full_center_x_p90_error | full_center_y_median_error | full_center_y_p90_error | full_width_median_error | full_width_p90_error | full_height_median_error | full_height_p90_error | depth_median_error | depth_p90_error | SAR_azimuth_median_error | SAR_azimuth_p90_error | SAR_radial_median_error | SAR_radial_p90_error | center_coverage_95 | median_search_ratio | controlled_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM017 | L0 | 72 | 2 | 37.94028 | 49.549479 | 0 | 15.423632 | 75.88056 | 99.098958 | 0 | 30.847264 | 1 | 1 | 3.789945 | 5.155199 | 66.310836 | 96.581116 | 24/72 | 0.00107227 | reference |
| GM_RM017 | L1 | 72 | 2 | 37.94028 | 49.549479 | 0 | 15.423632 | 93.303 | 100.002714 | 0 | 30.847264 | 1 | 1 | 3.789945 | 5.155199 | 87.440854 | 109.253332 | 0/72 | 0.00107227 | reference |
| GM_RM017 | L2 | 72 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.395852 | 1.028004 | 7.552072 | 16.664621 | 70/72 | 0.00107227 | true |

## Branch A Recovery Rows

| pair_id | physical_vehicle_id | previous_optical_anchor | next_optical_anchor | anchor_gap | recovered_center | recovered_size | recovered_depth | recovery_confidence | blocked_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WGV35A_PAIR_0200 | PV_GM19_BLACK_SEDAN_NEAR_FIELD |  |  |  |  |  |  | 0 | no_full_stream_optical_anchor_for_vehicle |
| WGV35A_PAIR_0201 | PV_GM19_BLACK_SEDAN_NEAR_FIELD |  |  |  |  |  |  | 0 | no_full_stream_optical_anchor_for_vehicle |
| WGV35A_PAIR_0202 | PV_GM19_BLACK_SEDAN_NEAR_FIELD |  |  |  |  |  |  | 0 | no_full_stream_optical_anchor_for_vehicle |
| WGV35A_PAIR_0203 | PV_GM19_RIGHT_DARK_FRAGMENT |  |  |  |  |  |  | 0 | no_full_stream_optical_anchor_for_vehicle |
| WGV35A_PAIR_0204 | PV_GM19_WHITE_SUV_NEAR_FIELD |  | 20 | 7 | 264.3055,418.821 | 338.671,308.354 | 3.608809 | 0.611111 |  |
| WGV35A_PAIR_0205 | PV_GM19_WHITE_SUV_NEAR_FIELD |  | 20 | 5 | 264.3055,418.821 | 338.671,308.354 | 3.608809 | 0.722222 |  |
| WGV35A_PAIR_0206 | PV_GM19_WHITE_SUV_NEAR_FIELD | 31 |  | 6 | 559.2815,447.428 | 468.981,298.86 | 2.88976 | 0.48 |  |
| WGV35A_PAIR_0207 | PV_GM19_WHITE_SUV_NEAR_FIELD | 31 |  | 8 | 559.2815,447.428 | 468.981,298.86 | 2.88976 | 0.4 |  |
| WGV35A_PAIR_0208 | PV_GM19_SILVER_MPV_NEAR_FIELD |  | 119 | 17 |  |  |  | 0 | one_sided_anchor_gap_too_large |
| WGV35A_PAIR_0209 | PV_GM19_SILVER_MPV_NEAR_FIELD |  | 119 | 5 | 256.394,432.3165 | 353.574,321.275 | 3.163009 | 0.635556 |  |
| WGV35A_PAIR_0210 | PV_GM19_SILVER_MPV_NEAR_FIELD | 124 |  | 5 | 432.061,429.963 | 456.862,335.356 | 3.491174 | 0.635556 |  |
| WGV35A_PAIR_0211 | PV_GM19_SILVER_MPV_NEAR_FIELD | 124 |  | 7 | 432.061,429.963 | 456.862,335.356 | 3.491174 | 0.537778 |  |
| WGV35A_PAIR_0212 | PV_GM19_SILVER_MPV_NEAR_FIELD | 124 |  | 14 |  |  |  | 0 | one_sided_anchor_gap_too_large |
| WGV35A_PAIR_0213 | PV_GM19_SILVER_MPV_NEAR_FIELD | 124 |  | 15 |  |  |  | 0 | one_sided_anchor_gap_too_large |
| WGV35A_PAIR_0214 | PV_GM19_GRAY_CAR_LEFT_EDGE |  | 170 | 19 |  |  |  | 0 | one_sided_anchor_gap_too_large |
| WGV35A_PAIR_0215 | PV_GM19_GRAY_CAR_LEFT_EDGE |  | 170 | 18 |  |  |  | 0 | one_sided_anchor_gap_too_large |

## Branch B Reconstruction Sample

| physical_vehicle_id | frame | source_track_id | observed_bbox | latent_center_x | latent_center_y | latent_full_width | latent_full_height | latent_relative_depth | velocity_x | velocity_y | scale_velocity | depth_velocity | edge_constraint_used | reconstruction_confidence | blocked_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 0 | bt_0001 | 123.223,342.616,705.465,598.302 | 429.593742 | 487.413261 | 639.168498 | 273.560424 | 3.484537 | 0 | 0 | 0 | 0 | latent_center~=observed_center;latent_top~=observed_top | 0.66 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 1 | bt_0001 | 172.014,347.161,744.78,598.597 | 468.232202 | 489.838604 | 639.168498 | 273.560424 | 3.242964 | 38.63846 | 2.425343 | 0 | -0.241573 | latent_center~=observed_center;latent_top~=observed_top | 0.66 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 2 | bt_0001 | 220.345,356.585,772.313,598.682 | 503.076151 | 495.289664 | 639.168498 | 273.560424 | 3.068051 | 34.84395 | 5.45106 | 0 | -0.174913 | latent_center~=observed_center;latent_top~=observed_top | 0.66 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 3 | bt_0001 | 257.156,365.314,788.479,598.221 | 560.315331 | 499.745558 | 639.168498 | 273.560424 | 3.066398 | 57.23918 | 4.455894 | 0 | -0.001653 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 4 | bt_0001 | 295.429,374.187,804.489,597.669 | 594.35401 | 503.665711 | 639.168498 | 273.560424 | 3.066521 | 34.038679 | 3.920153 | 0 | 0.000123 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 5 | bt_0001 | 328.249,385.319,809.084,596.822 | 625.666844 | 508.716052 | 639.168498 | 273.560424 | 2.989024 | 31.312834 | 5.050341 | 0 | -0.077497 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 6 | bt_0001 | 352.329,386.261,826.59,596.532 | 652.60898 | 508.670965 | 639.168498 | 273.560424 | 3.019041 | 26.942137 | -0.045087 | 0 | 0.030018 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 7 | bt_0001 | 368.297,380.83,847.785,596.569 | 675.496002 | 505.439476 | 639.168498 | 273.560424 | 3.163947 | 22.887022 | -3.231489 | 0 | 0.144906 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 8 | bt_0001 | 380.091,369.42,873.772,596.832 | 696.295057 | 499.218073 | 639.168498 | 273.560424 | 3.287349 | 20.799055 | -6.221403 | 0 | 0.123402 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 9 | bt_0001 | 388.948,346.413,900.708,589.829 | 715.626232 | 487.198804 | 639.168498 | 273.560424 | 3.411136 | 19.331175 | -12.01927 | 0 | 0.123788 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 10 | bt_0001 | 397.373,322.76,924.938,583.832 | 734.741571 | 474.856231 | 639.168498 | 273.560424 | 3.428927 | 19.115339 | -12.342573 | 0 | 0.017791 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | 11 | bt_0001 | 427.737,329.573,933.272,591.162 | 764.825675 | 477.746599 | 639.168498 | 273.560424 | 3.469232 | 30.084104 | 2.890368 | 0 | 0.040306 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 5 | bt_0003 | 10.559,336.835,78.186,516.065 | -75.684641 | 425.524498 | 397.567734 | 299.933838 | 3.758629 | 0 | 0 | 0 | 0 | latent_right~=observed_right | 0.53 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 6 | bt_0003 | 22.344,333.28,96.164,526.226 | -55.898808 | 428.008068 | 397.567734 | 299.933838 | 3.648113 | 19.785834 | 2.48357 | 0 | -0.110516 | latent_right~=observed_right | 0.53 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 7 | bt_0003 | 33.651,326.493,115.219,534.278 | 66.061493 | 429.967647 | 397.567734 | 299.933838 | 3.730585 | 121.9603 | 1.959578 | 0 | 0.082472 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 8 | bt_0003 | 44.12,316.744,134.471,538.081 | 81.966853 | 427.674348 | 397.567734 | 299.933838 | 3.807752 | 15.90536 | -2.293299 | 0 | 0.077167 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 9 | bt_0003 | 50.079,297.836,156.542,547.698 | 97.153399 | 423.959527 | 397.567734 | 299.933838 | 3.716192 | 15.186546 | -3.714821 | 0 | -0.09156 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 10 | bt_0003 | 53.942,280.806,176.923,556.321 | 110.730891 | 420.620809 | 397.567734 | 299.933838 | 3.56886 | 13.577492 | -3.338718 | 0 | -0.147332 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 11 | bt_0003 | 60.264,279.049,201.092,577.992 | 126.963162 | 429.318613 | 397.567734 | 299.933838 | 3.258474 | 16.232271 | 8.697804 | 0 | -0.310386 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 12 | bt_0003 | 73.628,293.432,225.943,593.091 | 141.408186 | 440.359273 | 397.567734 | 299.933838 | 3.249852 | 14.445024 | 11.04066 | 0 | -0.008621 | latent_center~=observed_center;latent_top~=observed_top | 0.7 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 13 | bt_0003 | 90.881,308.063,253.913,598.662 | 160.524574 | 447.073199 | 397.567734 | 299.933838 | 3.021369 | 19.116388 | 6.713926 | 0 | -0.228483 | latent_center~=observed_center;latent_top~=observed_top | 0.48 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 14 | bt_0003 | 108.587,326.366,281.792,600.265 | 180.91032 | 453.644305 | 397.567734 | 299.933838 | 3.296116 | 20.385746 | 6.571106 | 0 | 0.274747 | latent_center~=observed_center;latent_top~=observed_top | 0.4 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 15 | bt_0003 | 128.513,345.559,314.05,600.553 | 204.442416 | 462.257482 | 397.567734 | 299.933838 | 3.164494 | 23.532095 | 8.613177 | 0 | -0.131622 | latent_center~=observed_center;latent_top~=observed_top | 0.4 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 16 | bt_0003 | 137.421,353.602,341.811,600.173 | 224.871432 | 466.410686 | 397.567734 | 299.933838 | 3.186783 | 20.429016 | 4.153204 | 0 | 0.022289 | latent_center~=observed_center;latent_top~=observed_top | 0.4 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 17 | bt_0003 | 132.892,346.853,365.154,599.747 | 242.701938 | 468.936446 | 397.567734 | 299.933838 | 3.158591 | 17.830507 | 2.52576 | 0 | -0.028192 | latent_center~=observed_center;latent_top~=observed_top | 0.48 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 18 | bt_0003 | 119.298,329.197,387.792,600.426 | 256.221706 | 461.272771 | 397.567734 | 299.933838 | 3.496322 | 13.519768 | -7.663674 | 0 | 0.337731 | latent_center~=observed_center;latent_top~=observed_top | 0.48 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 19 | bt_0003 | 103.277,301.538,406.891,591.31 | 264.748862 | 449.534011 | 397.567734 | 299.933838 | 3.301503 | 8.527156 | -11.738761 | 0 | -0.194819 | latent_center~=observed_center;latent_top~=observed_top | 0.7 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 20 | bt_0003 | 94.97,264.644,433.641,572.998 | 270.011283 | 423.179697 | 397.567734 | 299.933838 | 3.556083 | 5.262421 | -26.354314 | 0 | 0.25458 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 21 | bt_0003 | 80.499,254.048,438.322,567.264 | 269.124145 | 416.473365 | 397.567734 | 299.933838 | 3.507776 | -0.887138 | -6.706332 | 0 | -0.048307 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 22 | bt_0003 | 85.771,262.307,458.602,573.757 | 283.257588 | 422.976456 | 397.567734 | 299.933838 | 3.366308 | 14.133443 | 6.503091 | 0 | -0.141468 | latent_center~=observed_center | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 23 | bt_0003 | 106.661,288.441,488.699,588.375 | 324.33323 | 443.784303 | 397.567734 | 299.933838 | 3.182068 | 41.075642 | 20.807847 | 0 | -0.184239 | latent_center~=observed_center;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 24 | bt_0003 | 144.856,309.497,532.104,595.183 | 357.922985 | 457.431998 | 397.567734 | 299.933838 | 3.06894 | 33.589754 | 13.647695 | 0 | -0.113129 | latent_center~=observed_center;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 25 | bt_0003 | 222.909,319.54,620.477,596.837 | 417.808606 | 464.251027 | 397.567734 | 299.933838 | 2.977009 | 59.885621 | 6.819029 | 0 | -0.091931 | latent_center~=observed_center;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 26 | bt_0003 | 282.33,314.008,700.031,595.605 | 469.184615 | 461.413926 | 397.567734 | 299.933838 | 3.004887 | 51.376009 | -2.8371 | 0 | 0.027878 | latent_center~=observed_center;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 27 | bt_0003 | 294.161,303.645,737.316,594.985 | 492.70425 | 455.582026 | 397.567734 | 299.933838 | 3.056101 | 23.519636 | -5.8319 | 0 | 0.051215 | latent_center~=observed_center;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 29 | bt_0003 | 295.131,291.24,767.825,596.831 | 519.050218 | 449.076006 | 397.567734 | 299.933838 | 3.005782 | 13.172984 | -3.25301 | 0 | -0.025159 | latent_center~=observed_center;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 30 | bt_0003 | 305.648,291.791,781.939,596.738 | 510.574997 | 450.010522 | 397.567734 | 299.933838 | 3.081886 | -8.47522 | 0.934516 | 0 | 0.076104 | latent_left~=observed_left;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 31 | bt_0003 | 324.791,297.998,793.772,596.858 | 530.737507 | 454.451232 | 397.567734 | 299.933838 | 2.922907 | 20.16251 | 4.44071 | 0 | -0.15898 | latent_left~=observed_left;latent_top~=observed_top | 0.72 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 32 | bt_0003 | 345.967,302.289,806.166,596.263 | 554.500252 | 459.425392 | 397.567734 | 299.933838 | 2.882158 | 23.762745 | 4.97416 | 0 | -0.040748 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 33 | bt_0003 | 372.324,308.414,819.095,596.343 | 578.59107 | 463.267712 | 397.567734 | 299.933838 | 2.756054 | 24.090818 | 3.84232 | 0 | -0.126104 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 34 | bt_0003 | 398.404,310.728,833.978,596.228 | 602.543994 | 465.204484 | 397.567734 | 299.933838 | 2.896659 | 23.952924 | 1.936772 | 0 | 0.140605 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 35 | bt_0003 | 426.806,315.176,845.795,596.251 | 627.657928 | 468.208548 | 397.567734 | 299.933838 | 2.831686 | 25.113935 | 3.004064 | 0 | -0.064973 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 36 | bt_0003 | 460.047,324.701,853.535,596.181 | 655.190839 | 473.750575 | 397.567734 | 299.933838 | 2.893032 | 27.53291 | 5.542027 | 0 | 0.061346 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 37 | bt_0003 | 493.164,334.888,859.158,595.873 | 682.662195 | 479.623932 | 397.567734 | 299.933838 | 2.791039 | 27.471357 | 5.873357 | 0 | -0.101993 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 38 | bt_0003 | 530.892,352.022,860.397,595.752 | 712.438941 | 488.971013 | 397.567734 | 299.933838 | 2.880412 | 29.776746 | 9.347081 | 0 | 0.089373 | latent_left~=observed_left;latent_top~=observed_top | 0.5 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 39 | bt_0003 | 568.47,370.313,860.322,595.285 | 734.606769 | 492.481257 | 397.567734 | 299.933838 | 2.852141 | 22.167828 | 3.510245 | 0 | -0.028271 | latent_left~=observed_left;latent_top~=observed_top | 0.35 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 40 | bt_0003 | 606.872,388.459,858.92,591.994 | 762.234141 | 499.846266 | 397.567734 | 299.933838 | 2.856909 | 27.627372 | 7.365009 | 0 | 0.004768 | latent_left~=observed_left;latent_top~=observed_top | 0.35 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | 41 | bt_0003 | 644.866,400.589,858.271,582.618 | 789.718407 | 505.10571 | 397.567734 | 299.933838 | 2.929001 | 27.484266 | 5.259444 | 0 | 0.072092 | latent_left~=observed_left;latent_top~=observed_top | 0.35 |  |
| PV_GM19_RIGHT_DARK_FRAGMENT | 12 | bt_0004 | 603.083,416.935,800.12,594.822 | 709.991047 | 511.199233 | 214.889828 | 182.017321 | 3.043927 | 0 | 0 | 0 | 0 | latent_left~=observed_left;latent_top~=observed_top | 0 | insufficient_temporal_extent |
| PV_GM19_RIGHT_DARK_FRAGMENT | 13 | bt_0004 | 642.817,434.437,813.995,589.636 | 751.334521 | 518.934399 | 214.889828 | 182.017321 | 3.092253 | 41.343474 | 7.735166 | 0 | 0.048326 | latent_left~=observed_left;latent_top~=observed_top | 0 | insufficient_temporal_extent |
| PV_GM19_RIGHT_DARK_FRAGMENT | 14 | bt_0004 | 687.173,450.286,827.919,579.512 | 794.295592 | 516.852109 | 214.889828 | 182.017321 | 3.550368 | 42.961071 | -2.08229 | 0 | 0.458115 | latent_left~=observed_left | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_044_049 | 44 | bt_0016 | 393.503,316.452,406.178,342.892 | 399.181391 | 328.280815 | 13.808258 | 26.425018 | 23.614542 | 0 | 0 | 0 | 0 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_044_049 | 45 | bt_0016 | 397.478,314.641,410.215,341.022 | 404.349122 | 328.478664 | 13.808258 | 26.425018 | 23.360659 | 5.167731 | 0.197849 | 0 | -0.253882 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_044_049 | 46 | bt_0016 | 403.921,315.68,416.751,341.921 | 410.75821 | 330.081396 | 13.808258 | 26.425018 | 24.162612 | 6.409087 | 1.602733 | 0 | 0.801953 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_044_049 | 47 | bt_0016 | 410.655,319.407,423.864,345.817 | 417.384307 | 333.105356 | 13.808258 | 26.425018 | 22.958786 | 6.626098 | 3.023959 | 0 | -1.203826 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_044_049 | 48 | bt_0016 | 417.517,323.568,431.08,349.944 | 424.06832 | 336.29572 | 13.808258 | 26.425018 | 24.000289 | 6.684012 | 3.190364 | 0 | 1.041503 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_044_049 | 49 | bt_0016 | 423.461,326.081,437.515,352.34 | 430.327604 | 338.64109 | 13.808258 | 26.425018 | 22.80863 | 6.259284 | 2.34537 | 0 | -1.191659 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_060_080 | 60 | bt_0033 | 461.229,322.996,488.197,350.073 | 474.917595 | 336.852381 | 33.032959 | 27.513794 | 28.119466 | 0 | 0 | 0 | 0 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_060_080 | 61 | bt_0033 | 465.638,322.689,492.884,349.976 | 479.360072 | 336.82376 | 33.032959 | 27.513794 | 28.943712 | 4.442477 | -0.028621 | 0 | 0.824245 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
| PV_GM19_UNPAIRED_SMALL_060_080 | 62 | bt_0033 | 471.032,323.111,498.628,350.609 | 484.313123 | 337.159732 | 33.032959 | 27.513794 | 28.586004 | 4.953051 | 0.335972 | 0 | -0.357708 | latent_center~=observed_center | 0 | insufficient_temporal_extent |
