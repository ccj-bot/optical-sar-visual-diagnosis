# OTY2 WGV3.3D PNG Normalization Audit

Date: 20260710

Status: `PNG_TEMPORAL_COMPARABILITY_UNCERTAIN`

## Findings

- Gray SAR frames scanned: `766`.
- Frames with max exactly 255: `163`.
- Frames with max >= 250: `606`.
- p99 mean: `64.946475`; p99 coefficient of variation: `0.20719035`.
- Image mean coefficient of variation: `0.19726594`.
- Color/gray comparison: sampled color-luma max range 255..255; p99 range 253..253; color PNG and gray PNG are display products, but luma values are not identical.

## Interpretation

The PNGs are display products. Cross-frame raw gray means are kept only as descriptive quantities. WGV3.3D therefore uses frame-internal percentiles plus local spatial and temporal background normalization for component extraction.

## Output

- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_png_frame_statistics_20260710.csv`
