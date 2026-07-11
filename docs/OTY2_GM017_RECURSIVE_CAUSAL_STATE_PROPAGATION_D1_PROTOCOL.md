# OTY2 GM_RM017 Recursive Causal State Propagation D1 Protocol

Updated: 2026-07-12

This protocol defines WGV3.6B-D1 for GM_RM017. Synthetic Aperture Radar (SAR, 合成孔径雷达) observations are processed in frame order to update a recursive target state and concrete local response tracks. This stage is not a final annotation stage.

## Scope

Allowed for D1 generation:

- Frozen P0 calibration artifacts from SAR 315-360.
- SAR gray frames up to and including the current frame.
- Calibration-derived loose region of interest (ROI, 感兴趣区域) size and uncertainty parameters.
- Weak optical state metadata already frozen by P0, only as provenance.

Forbidden for D1 generation:

- Holdout target GT.
- Future SAR frames.
- Evaluation tables.
- Selector, ranking, weighted aggregate score, final vehicle box, final annotation, or GT modification.

## P0 Reinterpretation

- P0 `F1_COMMON_MOTION` is downgraded to `P0_ABSOLUTE_FRAME_GT_TRAJECTORY_BASELINE=SUPPORTED` and `P0_RECURSIVE_COMMON_MOTION_MECHANISM=NOT_VALIDATED`.
- P0 `x/y intercept` and `x/y slope` are baseline-only and are never the D1 recursive state.
- P0 `same_motion_tolerance_px` is only a loose `motion_shell_candidate` bound.
- P0 `F2_BACKGROUND_STABILITY` is downgraded to recurrence evidence until a concrete cross-frame background track exists.
- P0 gap and reappearance tolerance are not reused as proof. D1 missing and reappearance are track-specific.
- P0 range/theta scale coefficients are frozen as a counterexample; D1 uses constant size only as a loose ROI size.
- P0 optical trend remains weak support/conflict/unavailable and does not project a SAR center.

## Phase Boundary

The D1 generation stage runs SAR 361-394 in order. SAR 361-370 is burn-in and SAR 371-394 is frozen holdout generation. Holdout GT is read only by the evaluator after the pre-evaluation seal is verified.

Required commands:

```powershell
D:\MINICONDA\envs\py311\python.exe -m py_compile tools\diagnostics\run_oty2_wgv3_6b_d1_gm017_recursive_state_generate.py tools\diagnostics\run_oty2_wgv3_6b_d1_gm017_recursive_state_evaluate.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_d1_gm017_recursive_state_generate.py generate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_d1_gm017_recursive_state_generate.py verify-replay
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_d1_gm017_recursive_state_evaluate.py evaluate
```

There is no `all` command.

## Recursive State Contract

Each frame records:

- prior position and velocity;
- predicted position and uncertainty;
- current SAR observation-supported position;
- posterior position and velocity;
- observation correction;
- used and rejected response track IDs;
- `max_sar_frame_read`, `gt_file_opened`, `evaluation_file_opened`, and `future_frame_read`.

If current SAR observations never change posterior position or velocity, `CURRENT_SAR_OBSERVATION_UPDATES_STATE` must fail and the stage status becomes `D1_NOT_RECURSIVE`.

## Local Response Tracks

Every local response claim must carry a `response_track_id`. Association evidence is stored as separate residuals and gate decisions, not as a combined score. `same_motion_supported` is allowed only after a track has multi-frame support, controlled relative position residuals, controlled motion residuals, and no stable-background conflict.

## Background Tracks

Background evidence must come from concrete cross-frame radar-stationary tracks. A single-frame elongated component is only a `background_recurrence_candidate`, not a `static_background_response`.

## Visual Review

The generator writes per-frame diagnostic PNGs under `outputs/`. They are ignored by git. The committed `visual_review_manifest` records reviewed frame scope and diagnostic paths without committing the PNG files.

## Success Definition

`D1_RECURSIVE_CAUSAL_STAGE_READY=PASS` requires strict causal generation, current SAR observation updates, concrete response tracks, concrete background tracks, no motion-shell-to-same-motion shortcut, pre-evaluation seal verification, replay identity, and visual review evidence. It does not require D1 to outperform P0.
