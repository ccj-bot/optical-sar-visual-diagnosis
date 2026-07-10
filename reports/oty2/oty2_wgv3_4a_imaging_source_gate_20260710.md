# OTY2 WGV3.4A Imaging Source Gate

Date: 20260710

Imaging source gate status: `RAW_SOURCE_LOCATION_UNKNOWN`

## Inventory Summary

- source_role_counts: `{'other': 3557, 'possible_generation_code': 90, 'optical_depth_not_sar_source': 736, 'sar_png_display_product': 618}`
- sar_png_display_products: `618`
- generation_code_candidates: `7`
- confirmed_generation_code_candidates: `0`
- sar_raw_or_float_candidates: `0`

## Interpretation

The current checkout and GM_RM011 data directory expose SAR PNG display products, optical frames, and depth arrays. No confirmed raw SAR pulse data, pulse-to-PNG mapping, or radial-pixel-to-range calibration was recovered by this gate.

This is a source-location result, not proof that the original SAR source does not exist elsewhere.

## Minimum Recovery Path

- `float_sar_amplitude`: Needed to compare SAR response magnitudes across time without framewise PNG display scaling.
- `float_sar_power`: Needed to distinguish local scatter strength from display contrast.
- `fixed_dynamic_range_log_sar`: Needed if raw amplitude cannot be shared but cross-frame comparability is required.
- `pulse_to_png_mapping`: Needed to evaluate whether path continuity is physical or a windowing artifact.
- `radial_pixel_to_range_mapping`: Needed to convert radial pixels into a physically interpretable SAR shell.
