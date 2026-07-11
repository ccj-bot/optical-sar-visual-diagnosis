# OTY2 WGV3.5A-R2C GM17 Leakage-Free Control

R2B的旧无锚点消融把固定裁剪比例隐含带入恢复，旧的L2零误差不再作为有效通过证据。

- hidden degraded input rows: `92`
- scoring truth rows: `92`
- physical vehicles: `2`
- L2 controlled pass: `true`
- recovery flags: truth_loaded_by_recovery=false; crop_ratio_loaded_by_recovery=false; original_bbox_loaded_by_recovery=false; original_depth_loaded_by_recovery=false

## Method

Recovery reads only degraded local boxes, visible-edge flags, frame order and polluted local depth. It estimates vehicle-level width/height from the observed upper envelope, applies single-edge equality constraints, keeps width/height as lower-bound-constrained latent states, and applies a short forward/backward temporal smoother. Scoring truth is loaded only after recovery.

## Results

|method|sample_count|physical_vehicle_count|center_x_median_error|center_x_p90_error|center_y_median_error|center_y_p90_error|width_median_error|width_p90_error|height_median_error|height_p90_error|depth_median_error|depth_p90_error|SAR_azimuth_median_error|SAR_azimuth_p90_error|SAR_radial_median_error|SAR_radial_p90_error|center_coverage|truth_loaded_by_recovery|crop_ratio_loaded_by_recovery|original_bbox_loaded_by_recovery|original_depth_loaded_by_recovery|controlled_pass|notes|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|L0_local_box_direct_state|88|2|28.343406|65.13382|0|14.641558|64.054018|143.69775|0|29.283115|0.071822|0.292499|2.72118|6.378704|63.014019|131.751846|51/88|false|false|false|false|false|recovery read only gm17_hidden_degraded_inputs; truth read only by scoring summary|
|L1_temporal_smoothed_local_box|92|2|16.68434|34.728911|4.883967|9.251799|65.440507|110.403911|9.279167|18.481623|0.13292|0.193617|1.644745|3.399409|63.339622|105.109565|88/92|false|false|false|false|false|recovery read only gm17_hidden_degraded_inputs; truth read only by scoring summary|
|L2_anchorless_track_level_full_vehicle_state|92|2|10.227265|26.628393|3.545452|6.812311|57.367221|67.819948|15.076446|25.246132|0.131219|0.195602|1.00731|2.65843|63.644021|77.128704|88/92|false|false|false|false|true|recovery read only gm17_hidden_degraded_inputs; truth read only by scoring summary|