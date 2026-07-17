# OTY2-RSA0-R2 Layer-by-Layer Forensic Audit of the SAR Response Representation Pipeline

Date: `2026-07-17`

This report answers only the eight frozen R2 questions. Large arrays and evidence cards remain outside Git.

## 1. What are the decoded PNG range, black region, and valid fan?

The decoded SAR PNG is uint8 display imagery. SAR 339 spans 0.0..250.0; SAR 384 spans 0.0..253.0. The frozen fan occupies 0.853693 of the canvas and about 29% of its pixels are zero in both primary frames.

- Frames: `PV002:339;PV003:384`
- Stages: `S00;S01;S02`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_array_lineage.csv` / `shape,dtype,min,max,zero_fraction,valid_fan_fraction`
- Point evidence: see point-trace ledger for named skeleton/background points.
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\phase_a\PV002_337_341\pv002_337_341_339_s00_s02_raw_decode_card.png;D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\phase_a\PV003_380_384\pv003_380_384_384_s00_s02_raw_decode_card.png`
- Evidence grade: `DIRECT_ARRAY_AND_IMAGE`

## 2. What does each coordinate transform actually do to image, geometry, and points?

RAW leaves image and geometry fixed; WORLD applies the same inverse scene translation to image, geometry, points, and valid-source mask; GT and optical-proxy stacks apply their own first-frame center translations before recomputing time channels. Geometry-only proxy shifting is retained only as localization-error sampling.

- Frames: `337-341;380-384`
- Stages: `S03;S04;S05;S06;S07`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_coordinate_stack_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_point_trace.csv` / `transform matrix, inverse point error, mask IoU, image reconstruction MAE`
- Point example: `skeleton_mid` at transformed coordinate `(1109.034,1063.685)`
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\coordinate_stacks\PV002_337_341\pv002_337_341_world_stabilized_image_stack_input_operation_output.png;D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\coordinate_stacks\PV003_380_384\pv003_380_384_world_stabilized_image_stack_input_operation_output.png`
- Evidence grade: `DIRECT_TRANSFORM_AND_POINT_TRACE`

## 3. Where is the first skeleton-to-response misalignment introduced?

The first systematic transform-induced skeleton misalignment in R1 occurs in the proxy-named branch: the image stays fixed while geometry shifts by proxy-minus-GT drift. At PV003 SAR 384 the shift is (-22.643,+130.210) px. Raw atlas endpoints also contain local offsets or semantic ambiguity, but those are pre-existing reference issues rather than transform-induced displacement.

- Frames: `PV003:384`
- Stages: `S07;S11`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_phase_a_findings.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_atlas_point_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_point_trace.csv` / `proxy drift, point status, transformed pixel sample`
- Point example: `skeleton_mid` at transformed coordinate `(1109.034,1063.685)`
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\phase_a\PV003_380_384\pv003_380_384_384_r1_coordinate_semantics_card.png`
- Evidence grade: `DIRECT_CODE_ARRAY_AND_VISUAL`

## 4. What does time mean in the real coordinate stacks?

RAW time mixes scene transport and local response change; WORLD time expresses residual change after background transport removal; GT-aligned time is oracle vehicle-centred change; optical-proxy-aligned time is proxy-centred change whose residual target motion includes proxy error. R1 had no WORLD temporal maps and did not construct the latter two aligned stacks.

- Frames: `337-341;380-384`
- Stages: `S05;S06;S07;S10`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_channel_semantic_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_coordinate_stack_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_phase_a_findings.csv` / `complete five-frame stack and temporal channel presence`
- Point evidence: see point-trace ledger for named skeleton/background points.
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\coordinate_stacks\PV002_337_341\pv002_337_341_world_stabilized_image_stack_input_operation_output.png;D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\coordinate_stacks\PV003_380_384\pv003_380_384_world_stabilized_image_stack_input_operation_output.png`
- Evidence grade: `DIRECT_STACK_AND_CHANNEL`

## 5. What image structures produce high values in each channel?

Channel high values are not target ownership: raw/local channels describe brightness, Sobel and gradient channels describe boundary normals, the legacy Hessian name is more accurately a multiscale negative-Laplacian bright-ridge response, coherence describes anisotropy, and fan directional channels describe gradient-normal components. Vertical lines, fan arcs, clutter, black boundaries, weak frames, and strong frames must remain separate.

- Frames: `PV002:339;PV003:384`
- Stages: `S08;S09;S10`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_channel_semantic_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_fan_geometry_audit.csv` / `raw skeleton/background subtype distributions and synthetic direction tests`
- Point evidence: see point-trace ledger for named skeleton/background points.
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\channels`
- Evidence grade: `DIRECT_ARRAY_VISUAL_AND_SYNTHETIC`

## 6. Do normalization and sampling manufacture or hide target-background differences?

R1 normalization and sampling can manufacture or hide differences: full-frame per-frame quantiles include invalid black support and AUC uses spatially ordered first-3000 samples. The largest exact-versus-legacy all-background AUC difference observed in R2 is 0.042345 for PV002_337_341 GT_ALIGNED_RESEARCH_STACK temporal_w2_max.

- Frames: `PV002:339;PV003:384`
- Stages: `S08;S12;S13`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_normalization_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_sampling_auc_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_point_trace.csv` / `four normalization ranges, exact/uniform/spatial/legacy AUC`
- Point example: `skeleton_mid` at transformed coordinate `(1109.034,1063.685)`
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\channels`
- Evidence grade: `DIRECT_POINT_AND_DISTRIBUTION`

## 7. Which R1 conclusions stand, require withdrawal, or remain undecidable?

R1 conclusions retained: v1 uses per-frame explicit geometry rather than the v0 fixed template; no single channel fully rejects background; propagation was not authorized. Conclusions requiring withdrawal or relabeling: GT/proxy/world coordinate-family effectiveness, world temporal statements, component continuity, first-3000 AUC, and any signal-retained label derived only from median separation >=0.03. Atlas morphology claims remain partly supported but point-level caveats are required.

- Frames: `R1 keyframes plus R2 primary/extension frames`
- Stages: `S06;S07;S10;S11;S13;S14;S15`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_phase_a_findings.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_atlas_point_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_channel_semantic_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_sampling_auc_audit.csv` / `8 frozen Phase A findings and point statuses`
- Point evidence: see point-trace ledger for named skeleton/background points.
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards\atlas_review`
- Evidence grade: `FORENSIC_SYNTHESIS`

## 8. Is propagation design authorized after confirmed implementation fixes?

After the R2 implementation fixes, the pipeline is traceable and engineering-valid, but propagation design is still not authorized. Two short windows are insufficient for method admission, hotspot controls are absent in the primary atlas, several atlas points remain offset/ambiguous, and no channel is background-safe across all subtypes and coordinate families.

- Frames: `337-341;380-384;extensions 330,344,360,372`
- Stages: `S00-S15`
- Arrays/metrics: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_atlas_point_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_channel_semantic_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_sampling_auc_audit.csv;D:\profile\research\optical-sar-visual-diagnosis-sar-foundation\manifests\oty2\oty2_rsa0_r2_synthetic_test_results.csv` / `all required gates plus unresolved scientific questions`
- Point evidence: see point-trace ledger for named skeleton/background points.
- Visualization: `D:\profile\research\workspace\output\oty2_rsa0_r2_20260717\evidence_cards`
- Evidence grade: `CONSERVATIVE_STAGE_DECISION`

## Phase B fix record

- R1 remains frozen. R2 constructs real WORLD/GT/PROXY image stacks and recomputes temporal channels.
- Geometry-only proxy displacement is retained under an honest localization-error name.
- `component_continuity` is replaced by `high_intensity_pixel_frequency`.
- AUC now reports exact, fixed-seed uniform, spatially stratified, and legacy results separately.
- Normalization now exposes full-frame, valid-fan, window-frozen, and local matched ranges.
- Atlas v1 is not edited; point-level correction proposals remain a separate decision.

## Final stage decision

`NEXT_PROPAGATION_DESIGN=NOT_AUTHORIZED`
