# OTY2-RSA0-R2 Normalization and Sampling Audit

Four normalization schemes are reported without selecting one by target score. Exact, uniform, spatially stratified, and legacy first-3000 AUC are kept separate.

## PV002_337_341

- `RAW_SAR_DISPLAY` `raw_display_intensity`: legacy_full_frame=[0,66], valid_fan_per_frame=[0,67], window_frozen_valid=[0,66], local_target_matched_background=[36,94]
- `RAW_SAR_DISPLAY` `local_contrast_31`: legacy_full_frame=[-16.07,15.51], valid_fan_per_frame=[-16.53,16.15], window_frozen_valid=[-16.61,15.68], local_target_matched_background=[-19.69,25.1]
- `RAW_SAR_DISPLAY` `local_z_31`: legacy_full_frame=[-1.811,1.765], valid_fan_per_frame=[-1.885,1.833], window_frozen_valid=[-1.982,1.785], local_target_matched_background=[-1.936,2.056]
- `RAW_SAR_DISPLAY` `highpass_sigma9`: legacy_full_frame=[-15.76,15.23], valid_fan_per_frame=[-16.26,15.85], window_frozen_valid=[-16.44,15.37], local_target_matched_background=[-19.17,24.12]
- `RAW_SAR_DISPLAY` `sobel_x_abs_gradient_component`: legacy_full_frame=[0,64], valid_fan_per_frame=[0,66], window_frozen_valid=[0,65], local_target_matched_background=[1,88]
- `RAW_SAR_DISPLAY` `sobel_y_abs_gradient_component`: legacy_full_frame=[0,76], valid_fan_per_frame=[0,79], window_frozen_valid=[0,76], local_target_matched_background=[1,100]
- `RAW_SAR_DISPLAY` `gradient_magnitude_sobel`: legacy_full_frame=[0,88.1], valid_fan_per_frame=[0,90.87], window_frozen_valid=[0,88.77], local_target_matched_background=[6,124]
- `RAW_SAR_DISPLAY` `multiscale_laplacian_bright_ridge`: legacy_full_frame=[0,11.22], valid_fan_per_frame=[0,11.74], window_frozen_valid=[-0,11.08], local_target_matched_background=[0,15.24]
- `RAW_SAR_DISPLAY` `structure_tensor_orientation_coherence`: legacy_full_frame=[0,0.8859], valid_fan_per_frame=[0,0.8368], window_frozen_valid=[0,0.8351], local_target_matched_background=[0.02899,0.4388]
- `RAW_SAR_DISPLAY` `radial_gradient_normal_response`: legacy_full_frame=[0,79.89], valid_fan_per_frame=[0,82.43], window_frozen_valid=[0,79.76], local_target_matched_background=[0.7861,100.9]
- `RAW_SAR_DISPLAY` `tangential_gradient_normal_response`: legacy_full_frame=[0,56.15], valid_fan_per_frame=[0,58.31], window_frozen_valid=[0,57.39], local_target_matched_background=[0.8021,87.26]
- `RAW_SAR_DISPLAY` `temporal_w2_median`: legacy_full_frame=[0,58], valid_fan_per_frame=[0,59], window_frozen_valid=[0,59], local_target_matched_background=[39,79]

The complete channel-by-channel ranges and point values are in the CSV and point-trace ledger.

## PV003_380_384

- `RAW_SAR_DISPLAY` `raw_display_intensity`: legacy_full_frame=[0,52], valid_fan_per_frame=[0,52], window_frozen_valid=[0,53], local_target_matched_background=[25,66]
- `RAW_SAR_DISPLAY` `local_contrast_31`: legacy_full_frame=[-13.38,12.11], valid_fan_per_frame=[-13.78,12.59], window_frozen_valid=[-14.19,12.81], local_target_matched_background=[-15.24,17.01]
- `RAW_SAR_DISPLAY` `local_z_31`: legacy_full_frame=[-1.926,1.724], valid_fan_per_frame=[-2.034,1.788], window_frozen_valid=[-2.05,1.814], local_target_matched_background=[-2.148,1.994]
- `RAW_SAR_DISPLAY` `highpass_sigma9`: legacy_full_frame=[-13.19,11.91], valid_fan_per_frame=[-13.6,12.38], window_frozen_valid=[-14,12.61], local_target_matched_background=[-15.01,16.12]
- `RAW_SAR_DISPLAY` `sobel_x_abs_gradient_component`: legacy_full_frame=[0,52], valid_fan_per_frame=[0,54], window_frozen_valid=[0,53], local_target_matched_background=[1,64.86]
- `RAW_SAR_DISPLAY` `sobel_y_abs_gradient_component`: legacy_full_frame=[0,61], valid_fan_per_frame=[0,63], window_frozen_valid=[0,63], local_target_matched_background=[1,69]
- `RAW_SAR_DISPLAY` `gradient_magnitude_sobel`: legacy_full_frame=[0,71.01], valid_fan_per_frame=[0,73.06], window_frozen_valid=[0,73.01], local_target_matched_background=[4.472,86.31]
- `RAW_SAR_DISPLAY` `multiscale_laplacian_bright_ridge`: legacy_full_frame=[0,8.7], valid_fan_per_frame=[0,9.11], window_frozen_valid=[0,9.142], local_target_matched_background=[0,9.989]
- `RAW_SAR_DISPLAY` `structure_tensor_orientation_coherence`: legacy_full_frame=[0,0.8769], valid_fan_per_frame=[0,0.8276], window_frozen_valid=[0,0.826], local_target_matched_background=[0.02767,0.4264]
- `RAW_SAR_DISPLAY` `radial_gradient_normal_response`: legacy_full_frame=[0,64], valid_fan_per_frame=[0,66.1], window_frozen_valid=[0,65.8], local_target_matched_background=[0.6371,69.7]
- `RAW_SAR_DISPLAY` `tangential_gradient_normal_response`: legacy_full_frame=[0,46], valid_fan_per_frame=[0,47.76], window_frozen_valid=[0,47.72], local_target_matched_background=[0.5863,64.35]
- `RAW_SAR_DISPLAY` `temporal_w2_median`: legacy_full_frame=[0,50], valid_fan_per_frame=[0,50], window_frozen_valid=[0,50], local_target_matched_background=[32,65]

The complete channel-by-channel ranges and point values are in the CSV and point-trace ledger.

## Largest observed legacy sampling difference

`PV002_337_341` `GT_ALIGNED_RESEARCH_STACK` `temporal_w2_max` vs `all_background`: absolute AUC difference `0.042345`.

