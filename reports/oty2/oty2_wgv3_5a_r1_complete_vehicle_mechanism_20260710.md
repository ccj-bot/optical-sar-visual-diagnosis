# OTY2 WGV3.5A-R1 Complete Vehicle Mechanism

Date: 20260710

## Mechanism Boundary

Only GM_RM017 is used. Complete-observable samples fit a weak forward optical-state to SAR-polar relation. Truncated samples are used for controlled degradation and recovery diagnosis.

## Observation Regime

- direct_observable samples: `92`
- temporally_recoverable natural samples: `34`
- physical vehicle count in direct pool: `2`
- direct depth median/P90: `10.347963` / `10.933333`
- natural truncation depth median/P90: `10.823677` / `12.440637`

## Baseline Models

| model_target | model_name | input_features | sample_count | physical_vehicle_count | selected | parameters | median_error | p90_error | center_coverage_95 | full_box_coverage_95 | median_search_ratio | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| azimuth | linear_center_x | bbox_center_x | 92 | 2 | false | {"coefficients": [0.09704652], "intercept": -42.33557812, "ridge_alpha": 0.0} | 0.437468 | 1.177644 |  |  |  | complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only |
| azimuth | quadratic_center_x | bbox_center_x;bbox_center_x_sq | 92 | 2 | true | {"coefficients": [0.10234231, -7.54e-06], "intercept": -43.12392545, "ridge_alpha": 0.0} | 0.428394 | 1.157673 |  |  |  | complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only |
| azimuth | pinhole_like_effective | atan((bbox_center_x-400)/360) | 92 | 2 | false | {"coefficients": [0.67165213], "intercept": -3.55182094, "ridge_alpha": 0.0} | 0.690444 | 1.585435 |  |  |  | complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only |
| radial | gradient_boosting_reference | depth_D4;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | false | reference_only;random_state=3401;max_depth=2;n_estimators=80 | 1.722598 | 5.387377 |  |  |  | reference only; not used as R1 mechanism projection |
| radial | depth_only_linear | depth_D4 | 92 | 2 | false | {"coefficients": [41.36527612], "intercept": 18.18559874, "ridge_alpha": 0.0} | 19.286194 | 40.975611 |  |  |  | interpretable complete-observable radial baseline |
| radial | bbox_geometry_linear | bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | true | {"coefficients": [-0.87848784, -1.23553812, 0.71459414], "intercept": 452.12739216, "ridge_alpha": 0.0} | 8.218456 | 22.310641 |  |  |  | interpretable complete-observable radial baseline |
| radial | depth_plus_bbox_ridge | depth_D4;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | false | {"coefficients": [7.99359194, -0.81883957, -0.86590487, -0.18623806], "intercept": 673.12618677, "ridge_alpha": 1.0} | 8.171366 | 23.186981 |  |  |  | interpretable complete-observable radial baseline |
| complete_observation_selected | quadratic_center_x+bbox_geometry_linear | bbox_center_x;bbox_center_x_sq;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | true | {"azimuth": "{\"coefficients\": [0.10234231, -7.54e-06], \"intercept\": -43.12392545, \"ridge_alpha\": 0.0}", "radial": "{\"coefficients\": [-0.87848784, -1.23553812, 0.71459414], \"intercept\": 452.12739216, \"ridge_alpha\": 0.0}", "intervals": {"az_q50": 1.0, "az_q95": 2.0, "rad_q50": 8.218456189457498, "rad_q95": 31.795472356059967}} | az=0.428394;radial=8.218456 | az=1.157673;radial=22.310641 | 0.945652 | 0 | 0.00107227 | selected R1 interpretable complete-vehicle projection baseline |

## Selected Complete-Observation Baseline

| model_target | model_name | input_features | sample_count | physical_vehicle_count | selected | parameters | median_error | p90_error | center_coverage_95 | full_box_coverage_95 | median_search_ratio | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complete_observation_selected | quadratic_center_x+bbox_geometry_linear | bbox_center_x;bbox_center_x_sq;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | true | {"azimuth": "{\"coefficients\": [0.10234231, -7.54e-06], \"intercept\": -43.12392545, \"ridge_alpha\": 0.0}", "radial": "{\"coefficients\": [-0.87848784, -1.23553812, 0.71459414], \"intercept\": 452.12739216, \"ridge_alpha\": 0.0}", "intervals": {"az_q50": 1.0, "az_q95": 2.0, "rad_q50": 8.218456189457498, "rad_q95": 31.795472356059967}} | az=0.428394;radial=8.218456 | az=1.157673;radial=22.310641 | 0.945652 | 0 | 0.00107227 | selected R1 interpretable complete-vehicle projection baseline |

## Projection Comparison Summary

| evaluation_group | method | sample_count | azimuth_median_error | azimuth_p90_error | radial_median_error | radial_p90_error | center_coverage_95 | full_box_coverage_95 | median_search_ratio | multi_target_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| direct_observable_control | M0_local_direct_projection | 92 | 0.428394 | 1.157673 | 8.218456 | 22.310641 | 0.945652 | 0 | 0.00107227 | 0 |
| direct_observable_control | M1_interval_inflation_only | 92 | 0.428394 | 1.157673 | 8.218456 | 22.310641 | 0.945652 | 0 | 0.00107227 | 0 |
| direct_observable_control | M2_recovered_full_vehicle_state | 92 | 0.428394 | 1.157673 | 8.218456 | 22.310641 | 0.945652 | 0 | 0.00107227 | 0 |
| natural_truncation | M0_local_direct_projection | 34 | 1.103418 | 2.921491 | 24.599103 | 63.997887 | 0.470588 | 0 | 0.00107227 | 0 |
| natural_truncation | M1_interval_inflation_only | 34 | 1.103418 | 2.921491 | 24.599103 | 63.997887 | 0.470588 | 0 | 0.00107227 | 0 |
| natural_truncation | M2_recovered_full_vehicle_state | 18 | 0.9606 | 1.941507 | 30.867945 | 41.388449 | 0.888889 | 0 | 0.00213177 | 0 |
| simulated_truncation | M0_local_direct_projection | 120 | 3.718112 | 6.048506 | 61.461814 | 113.955562 | 0.225 | 0 | 0.00107227 | 0 |
| simulated_truncation | M1_interval_inflation_only | 120 | 3.718112 | 6.048506 | 61.461814 | 113.955562 | 0.4 | 0 | 0.00525096 | 0 |
| simulated_truncation | M2_recovered_full_vehicle_state | 120 | 0.381762 | 1.040682 | 9.616955 | 18.736635 | 0.916667 | 0 | 0.00107227 | 0 |

## Interpretation

GM_RM017 works mainly in the mid-range complete-body regime: the optical bbox center still has a full-vehicle meaning, depth remains weakly monotonic, and SAR azimuth/radial errors stay lower than in natural or simulated truncation. This is a controlled complete-observability mechanism, not a scene-accident-only explanation.
