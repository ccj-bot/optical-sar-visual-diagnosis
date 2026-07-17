# OTY2-RSA0-R1 Free-Geometry Response Atlas and Continuous Temporal Reaudit

Date: `2026-07-17`

## Scope

This report corrects the RSA0 v0 fixed-template atlas and sparse-keyframe representation diagnosis. It does not enter seed propagation, object memory, lifecycle modeling, S1-D events, final masks, weighted fusion, winner/ranking, VOS, or training.

## Atlas v1 correction

- v1 version: `OTY2-RSA0-response-atlas-v1-free-geometry`.
- Geometry is explicit per keyframe: variable skeleton length, variable point count, variable polygon area, and actual background controls.
- v0 remains frozen and is not rewritten.
- GT is used only as review coordinate context; no `geometry_template`, fixed x offsets, fixed rectangles, fixed background line/arc, or same-area frame template is used.

## Continuous temporal correction

- PV002 uses continuous frames `330-350`; PV003 uses continuous frames `360-384`.
- Local temporal windows use `t-2...t+2` and `t-4...t+4`, clipped at window boundaries.
- Positive/negative change is computed from the real adjacent pair `t-1 -> t`; it is not sparse keyframe differencing.

## Top skeleton-primary channel/family summaries

- `PV002_330_350` `GT_CONDITIONED_RESEARCH_ORACLE` `temporal_w4_mad_sar_display`: median skeleton-background `0.100000`, hit-rate `1.000000`, failure `skeleton_signal_retained`.
- `PV002_330_350` `SAR_DISPLAY_WORLD_STABILIZED` `structure_tensor_orientation_coherence`: median skeleton-background `0.048201`, hit-rate `0.000000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `GT_CONDITIONED_RESEARCH_ORACLE` `tangential_directional_gradient_response`: median skeleton-background `0.046466`, hit-rate `0.800000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `GT_CONDITIONED_RESEARCH_ORACLE` `sobel_x_abs_gradient_component`: median skeleton-background `0.038462`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `SAR_DISPLAY_WORLD_STABILIZED` `multiscale_hessian_bright_ridge`: median skeleton-background `0.036073`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV002_330_350` `SAR_DISPLAY_WORLD_STABILIZED` `display_local_contrast`: median skeleton-background `0.034240`, hit-rate `0.200000`, failure `skeleton_signal_retained`.
- `PV002_330_350` `GT_CONDITIONED_RESEARCH_ORACLE` `display_local_contrast`: median skeleton-background `0.033982`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `GT_CONDITIONED_RESEARCH_ORACLE` `multiscale_hessian_bright_ridge`: median skeleton-background `0.033234`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV002_330_350` `GT_CONDITIONED_RESEARCH_ORACLE` `display_multiscale_highpass`: median skeleton-background `0.031974`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `GT_CONDITIONED_RESEARCH_ORACLE` `display_local_contrast`: median skeleton-background `0.031690`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV002_330_350` `SAR_DISPLAY_WORLD_STABILIZED` `display_local_z`: median skeleton-background `0.030217`, hit-rate `0.000000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `SAR_DISPLAY_WORLD_STABILIZED` `display_local_z`: median skeleton-background `0.030205`, hit-rate `0.400000`, failure `skeleton_signal_retained`.
- `PV003_360_384` `GT_CONDITIONED_RESEARCH_ORACLE` `display_multiscale_highpass`: median skeleton-background `0.029642`, hit-rate `0.400000`, failure `background_competes_with_target`.
- `PV002_330_350` `GT_CONDITIONED_RESEARCH_ORACLE` `display_local_z`: median skeleton-background `0.029043`, hit-rate `0.000000`, failure `background_competes_with_target`.
- `PV002_330_350` `SAR_DISPLAY_WORLD_STABILIZED` `display_multiscale_highpass`: median skeleton-background `0.028938`, hit-rate `0.200000`, failure `background_competes_with_target`.
- `PV003_360_384` `SAR_DISPLAY_WORLD_STABILIZED` `display_local_contrast`: median skeleton-background `0.028718`, hit-rate `0.400000`, failure `background_competes_with_target`.
- `PV003_360_384` `GT_CONDITIONED_RESEARCH_ORACLE` `display_local_z`: median skeleton-background `0.027965`, hit-rate `0.400000`, failure `background_competes_with_target`.
- `PV003_360_384` `SAR_DISPLAY_WORLD_STABILIZED` `display_multiscale_highpass`: median skeleton-background `0.023237`, hit-rate `0.400000`, failure `background_competes_with_target`.

## PV003 optical-proxy drift

- Frame `360`: dx `12.529` px, dy `86.425` px, magnitude `87.329` px, dominant `down`.
- Frame `364`: dx `2.676` px, dy `93.669` px, magnitude `93.707` px, dominant `down`.
- Frame `372`: dx `-13.705` px, dy `97.311` px, magnitude `98.272` px, dominant `down`.
- Frame `378`: dx `-12.372` px, dy `105.179` px, magnitude `105.904` px, dominant `down`.
- Frame `384`: dx `-22.643` px, dy `130.210` px, magnitude `132.164` px, dominant `down`.

## Formal answers

1. **Does v1 escape the GT-relative fixed template?** Yes for this R1 atlas: all keyframes have explicit free geometry, no shared template, no fixed x-offset skeleton bank, no fixed rectangles, and no fixed background translation.
2. **Do skeletons and components show real morphology differences?** Yes. Lengths, point counts, definite areas, unresolved areas, and background controls vary by frame and case; the consistency audit records this explicitly.
3. **Does v0 temporal positive/negative change still stand after continuous recomputation?** Only as a preliminary hypothesis. Adjacent-frame temporal change remains useful on some strong states, but it is not a stable standalone conclusion once weak states, background activation, and proxy drift are separated.
4. **Which channels are stable on both vehicle-window skeletons?** Raw display, multiscale Hessian ridge, tangential/radial directional gradients, and temporal local component continuity are the most consistently useful skeleton diagnostics. Their usefulness is state-dependent and must be read with background controls.
5. **Which channels suppress true background lines/arcs/hotspots?** No single channel fully suppresses them. Hessian/ridge and directional responses help identify line-like structure but can also activate on fan arcs and vertical streaks, so explicit background controls remain required.
6. **How much GT-conditioned effectiveness remains under optical proxy alignment?** PV002 retains more because drift is moderate. PV003 loses much more in late frames, especially frame 384 where the proxy center is far below the GT-conditioned response; GT-oracle and optical-proxy results must not be merged.
7. **Is the next propagation stage allowed?** Not yet as an automatic propagation/training stage. R1 supports a next-session seed-object-propagation design discussion, but only after treating v1 as a reviewed atlas and keeping background controls and proxy drift gates explicit.

## Output files

- Frames: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_response_atlas_frames_v1.csv`
- Regions: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_response_atlas_regions_v1.csv`
- Skeletons: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_response_skeletons_v1.csv`
- Background controls: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_background_controls_v1.csv`
- Consistency audit: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r1_atlas_consistency_audit.csv`
- Metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r1_representation_channel_metrics.csv`
- Coordinate-family summary: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r1_coordinate_family_summary.csv`
- Proxy drift: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r1_proxy_drift.csv`
- Review overlays: `D:\profile\research\workspace\output\oty2_rsa0_r1_20260717\response_atlas_review_v1`
