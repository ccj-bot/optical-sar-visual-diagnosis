# OTY2 Object-SAR Physical Mechanism Modeling Plan

Updated: 20260702_222218

This plan records the next modeling step after OTY2 posthoc validation. It is not OTY3, not an automatic annotation proposal, not a selector/ranking design, and not training or threshold tuning.

## Objective

Model how an optical object hypothesis maps to SAR GT / SAR image evidence through physical factors: time synchronization, fan-polar azimuth, vehicle shell, optical range-shape cues, optical trajectory, SAR image scattering, SAR temporal continuity, and state-conditioned uncertainty.

## Evidence Boundaries

- Runtime-safe construction may use optical object stream, optical temporal continuity, acquisition timing, scene geometry, and vehicle physical assumptions.
- SAR GT, SAR image crop statistics, and manual/review anchors may be used only as posthoc validation or SAR observation evidence.
- SAR image evidence is important for final annotation reasoning, but posthoc SAR GT / SAR image discoveries must not be written back into runtime optical prior construction.
- The uploaded MATLAB imaging toolbox is similar_imaging_reference_only: it explains SAR/FMCW concepts such as range FFT, range-azimuth grids, BP focusing, mainlobe/sidelobe, IRW/PSLR/ISLR/ENL, and motion compensation; it is not the same OTY2 pipeline and the zip is not committed.

## Ledger Pools

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- detection dropout / no_oty_iou_match / temporal continuation pool = 12

The 215 paired rows are frame-level posthoc pairs, not 215 independent physical objects. SAR-only rows stay outside optical-SAR correspondence statistics. Dropout/no-match rows stay outside clean paired morphology statistics.

## Factor Families

- F_time: 24fps optical to 50fps SAR software-sync temporal tube.
- F_az: fan-polar / range-azimuth azimuth mapping.
- F_shell: vehicle physical length/width footprint shell.
- F_range_shape: complete-state optical bbox height / bottom_y / area relation to SAR radius.
- F_traj: optical object trajectory direction and SAR GT trend.
- F_sar_image: SAR local peak, mainlobe/sidelobe, long/short axis, box/background, peak/background.
- F_sar_temporal: SAR scattering continuity across adjacent SAR frames.
- F_state: complete / truncated / edge / far-small / duplicate / dropout conditioned uncertainty.

## Immediate Modeling Use

1. Use F_az + F_shell + F_sar_image as a joint SAR observation probe, not a candidate selector.
2. Use F_range_shape + F_traj only as object-level posthoc hypotheses until complete-state and scene balance improve.
3. Use F_sar_temporal for SAR observation inside the temporal tube, especially dropout/truncation cases.
4. Use GM_RM019 manual optical GT / identity review to confirm object hypotheses, trajectory direction, and complete morphology frames, not SAR identity truth.
5. Recover GM_RM011 through OTY optical object stream construction before optical-SAR correspondence modeling.

## Prohibited Shortcuts

- Do not treat 215 as 442.
- Do not treat frame-level correlation as object-level law.
- Do not mix SAR-only rows into optical-SAR correspondence.
- Do not mix dropout/no-match rows into clean paired morphology.
- Do not write SAR GT / SAR image posthoc discoveries into runtime prior construction.
- Do not generate annotation proposals, selector/ranking outputs, tuned thresholds, model weights, or identity truth claims.

## Generated Evidence Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_object_sar_physical_mechanism_modeling_plan.md`
- physical_factor_evidence_taxonomy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_evidence_taxonomy_20260702_222218.csv`
- joint_factor_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_joint_factor_probe_20260702_222218.csv`
- object_level_factor_evidence_ledger_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_level_factor_evidence_ledger_20260702_222218.csv`
- sar_temporal_observation_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_temporal_observation_probe_20260702_222218.csv`
- manual_review_candidate_list_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_manual_review_candidate_list_20260702_222218.csv`
- physical_factor_modeling_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_modeling_report_20260702_222218.md`
- physical_factor_modeling_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_modeling_summary_20260702_222218.json`
