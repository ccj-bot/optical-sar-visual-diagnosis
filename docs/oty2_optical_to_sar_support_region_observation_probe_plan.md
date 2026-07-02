# OTY2 Optical-To-SAR Support-Region Observation Probe Plan

Updated: 20260702_233406

This document defines the OTY2 support-region observation probe. It is not OTY3, not final automatic annotation, not selector/ranking, and not training or threshold tuning.

## Boundary

- Support regions are constructed from optical object observations, 24 fps to 50 fps software-sync timing, configured fan-polar azimuth mapping, vehicle shell assumptions, and state-conditioned margins.
- SAR image content is allowed for SAR observation extraction inside the support region.
- SAR GT is allowed only for posthoc validation columns such as `gt_inside_support_posthoc`.
- No GT crop is used for peak or centroid extraction.
- GM_RM011 remains blocked by missing current OTY optical object stream; SAR-only rows remain SAR reference only; dropout rows remain a separate temporal-continuation pool.

## Four Probe Relations

1. `optical single frame -> SAR single frame`: build `C_o,t,tau = C_time intersect C_az intersect C_shell intersect C_state`, then extract local peak, peak/background, scatter centroid, centroid residual, range-profile peak, azimuth-profile peak, support area, and top-k local peaks from `I_tau`.
2. `optical single frame -> SAR short window`: reuse the optical-derived support region over `W_t^SAR` and check whether peak/centroid observations are stable across nearby SAR frames.
3. `optical tracklet -> SAR single frame`: invert SAR frame time to optical time and interpolate optical tracklet state before constructing the support region.
4. `optical tracklet -> SAR temporal tube`: build an object-level sequence of support regions and extract SAR observation sequences for peak/centroid continuity and drift checks.

## Current Blocker

Current OTY2 runtime-safe spatial priors have `broad_unknown_range_prior`. The probe therefore extracts observations from coarse optical-derived azimuth sectors across the valid SAR fan radius. This is useful for SAR observation evidence and blocker diagnosis, but it is not a final localization box.

## Generated Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_optical_to_sar_support_region_observation_probe_plan.md`
- optical_frame_to_sar_frame_support_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_frame_to_sar_frame_support_probe_20260702_233406.csv`
- optical_frame_to_sar_window_support_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_frame_to_sar_window_support_probe_20260702_233406.csv`
- optical_tracklet_to_sar_frame_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_tracklet_to_sar_frame_probe_20260702_233406.csv`
- optical_tracklet_to_sar_tube_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_tracklet_to_sar_tube_probe_20260702_233406.csv`
- support_region_sar_observation_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_sar_observation_summary_20260702_233406.json`
- support_region_sar_observation_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_sar_observation_report_20260702_233406.md`
