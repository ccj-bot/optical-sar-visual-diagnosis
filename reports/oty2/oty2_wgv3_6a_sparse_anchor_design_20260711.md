# OTY2 WGV3.6A Sparse-Anchor Response Propagation Design

## Boundary

- Scene: GM_RM019 only.
- Anchor semantics: `high_confidence_optical_sar_visible_response_anchor`.
- SAR state is `observed_masked_response_state`; `response_center_for_local_tracking` is not a complete vehicle center.
- No GT edit, no final SAR box, no selector/ranking, no full-SAR search, no GM_RM011, no detector training.

## Frozen Inputs

|source_file|sha256|bytes|rows|frozen_scope|
|---|---|---|---|---|
|docs/OTY2_SESSION_START_HERE.md|2ea33501abd9c27fb69a7056805242dad54524cd8dbb22dea606d800edf368fc|10079||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md|ca063c42eef75ee3912df58698d688528ce036fd422e94b737525d16702aae13|9123||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md|170169deb35d0c43fb54101364d624e04dbc2e9a3993dbb91b1367f9e8931c24|6788||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md|ee597b59440fc8a56b94b2bbdfbeef8ef6162efa31721069fd5b6c1c0da382cc|21226||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/oty2_wgv3_5a_r1_closure_20260710.md|a1e8ea691d5a4ce77af94c889a5f25793ae87cea3fd31f0f191d020649523163|11085||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/oty2_wgv3_5a_r2b_gm019_closure_20260710.md|faf03244e298a08e1f188ca373ab0bef1361f514a81755b27db55777a636ab7a|8905||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/oty2_wgv3_5a_r2c_mask_aware_closure_20260711.md|df81a199227c15f6a7f099c33c9efe33ffacaf52af0aa58d7df80549028544af|18719||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/oty2_wgv3_5a_r2c_sar_mask_definition_20260711.md|04591e40bb5c358f23f732d0d79d695727676b2ee6bfc4ec86d7d8a61daccabc|5341||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/oty2_wgv3_5a_r2c_mask_aware_visual_diagnosis_20260711.md|f8de6673f9d2593070d6f0e1a594d3ea52bd51996069ea89a3551853cb953215|9431||WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv|738c723f2ec03d53fdf67155ae8378ad204a61316eb5c9065cbcfe6a2110c22a|9223|16|WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv|6ba1d9b7d66b064a04e43f3c2a386aae607a9721706269a0ddf607bde3e65c57|1978|9|WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_20260710.csv|1e3a6eecb79a306a81b4dc0937b3282afb30d4864f29d9e56a4da74949872e9b|37239|173|WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|
|reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_20260710.csv|f48753fe33dbf83f7d2a04c1643cb556706a3482e6e1970cb7e2e5965aa93d4b|19917|112|WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources|

## A0 Anchor Rules

- `ANCHOR_CONFIRMED`: optical identity confidence is high, pairing is not review-blocked, and mask-internal SAR visible response is locally inspectable.
- `ANCHOR_WEAK`: pressure/edge/short observation is useful for stress reading but not for A1 main propagation.
- `ANCHOR_PAIRING_REVIEW_REQUIRED`: identity or pair relation remains unsafe.

## A1 Propagation Rules

- P0 keeps the anchor visible-response region fixed.
- P1 follows the bounded optical trend between two confirmed anchors.
- P2 corrects P1 inside a local SAR window using simple connected bright response continuity.
- P3 applies the reconstructed fan/mask boundary to the P2 local response and clips near-boundary drift.