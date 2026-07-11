# OTY2 GM_RM017 Physical Factor Calibration Protocol

Updated: 2026-07-12

This protocol defines WGV3.6B-P0 for GM_RM017. The goal is to discover, fit, freeze, and holdout-test physical response factors for optical-timeline-assisted SAR vehicle response diagnosis.

## Scope

Allowed in calibration:

- GM_RM017 calibration-window SAR GT boxes and paired rows.
- Calibration-window optical timeline states.
- Calibration-window SAR gray frames.
- Explicit non-vehicle control evidence such as `GM_RM017_N005`.
- Human or multimodal posthoc conclusions, only as calibration/control provenance.

Forbidden in holdout generation:

- Holdout target GT boxes.
- Holdout manual same-vehicle centers or per-frame assignment.
- Future holdout target boxes.
- Holdout evaluation results.
- Any threshold or time-offset retuning after evaluation.

## Required Phase Boundary

The script `tools/diagnostics/run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py` exposes only staged commands:

```powershell
D:\MINICONDA\envs\py311\python.exe -m py_compile tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py audit-inputs
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py build-calibration-pack
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py calibrate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py validate-generate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py evaluate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_p0_gm017_physical_factor_discovery.py verify-replay
```

There is no `all` command.

## Continuous Split

The active target thread is `oty1t_obj_GM_RM017_bytetrack_bt_0010`, selected because it has a dense calibration-eligible paired sequence.

- Calibration/discovery: SAR `315-360`.
- Guard gap: SAR `361-370`.
- Holdout generation/evaluation: SAR `371-394`.
- Background control: `GM_RM017_N005`, optical `121-129`, SAR temporal window from P0 frame-ratio source.

The temporal source remains `frame_ratio_hypothesis`, with optical fps `24`, SAR fps `50`, and no exact timestamp metadata. This is an audit mapping, not timestamp truth.

## Factors

F1 common motion estimates a shared target-state trajectory and residual tolerance.

F2 background stability estimates fixed high-response structures, using time-position stability before shape.

F3 intermittent visibility estimates visible, weak-visible, missing, and reappeared response states.

F4 scale-range relation estimates SAR image-domain response size against radar-local range and azimuth.

F5 optical-SAR trend tests weak sign-level compatibility only; it must not directly project SAR centers or choose holdout time offsets.

## Output Boundary

Outputs may contain:

- local response trajectories;
- same-motion candidates;
- static-background candidates;
- intermittent-visibility candidates;
- frozen factor parameters;
- holdout factor predictions and evaluation.

Outputs must not contain:

- a final vehicle box;
- final annotation;
- selector/ranking;
- weighted aggregate score;
- final dynamic membership assignment.
