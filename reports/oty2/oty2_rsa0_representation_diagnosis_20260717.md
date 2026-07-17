# OTY2-RSA0 Representation Diagnosis

Date: `2026-07-17`

The frozen atlas was evaluated without changing atlas geometry. Metrics are independent channel diagnostics, not weighted scores or winners. The channel list is sorted for triage only.

## Channel Summary

- `temporal_positive_change_sar_display` median positive-minus-background: `0.297223`
- `temporal_negative_change_sar_display` median positive-minus-background: `0.292313`
- `temporal_window_mad_sar_display` median positive-minus-background: `0.192308`
- `display_raw_8bit` median positive-minus-background: `0.173325`
- `display_gradient_magnitude` median positive-minus-background: `0.170119`
- `temporal_window_max_sar_display` median positive-minus-background: `0.166667`
- `structure_horizontal_line_response` median positive-minus-background: `0.146744`
- `temporal_window_median_sar_display` median positive-minus-background: `0.133442`
- `structure_vertical_line_response` median positive-minus-background: `0.117693`
- `temporal_window_min_sar_display` median positive-minus-background: `0.116279`
- `display_local_contrast` median positive-minus-background: `0.043404`
- `display_multiscale_highpass` median positive-minus-background: `0.042401`
- `display_local_z` median positive-minus-background: `0.024767`
- `temporal_local_frequency_sar_display` median positive-minus-background: `0.000000`
- `structure_ridge_laplacian` median positive-minus-background: `0.000000`

## Six Questions

1. S1X/S1D0 deviated by reducing the visible object to threshold components, persistent pixels, and lifecycle events before the response object was recovered.
2. A v0 non-rectangular atlas now exists for two short windows with skeleton, definite response, probable response, background, mixed, and unresolved geometry.
3. The main skeleton is most separable in temporal positive/negative change, temporal MAD, raw display, and gradient-style channels on this v0 atlas; local contrast, highpass, and local-z are weaker than expected.
4. Background suppression is not solved by a single channel. Channels with positive separation still need explicit vertical-line and fan-arc controls.
5. This run evaluates frozen `sar_display_px` atlas geometry. GT-conditioned and optical-proxy visual products were generated for review, and PV003 shows a proxy-coordinate limitation that must be handled before propagation.
6. The next seed-object-propagation prototype should start from conservative skeleton seeds plus background controls, not from whole GT boxes, persistent pixels, or weighted channel winners.

## Files

- Metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_representation_channel_metrics.csv`
- Failure modes: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_representation_failure_modes.csv`
