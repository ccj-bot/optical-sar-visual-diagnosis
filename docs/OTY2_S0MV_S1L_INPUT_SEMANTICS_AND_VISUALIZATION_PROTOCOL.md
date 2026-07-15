# OTY2 S0-MV S1-L Input Semantics and Visualization Protocol

Date: `2026-07-15`
Frozen start HEAD: `6578488f9ed9a0b5d917302bffc2672699ec717a`
Branch: `feature/oty2-sar-gt-structure-foundation`

## Purpose and boundary

S0-MV is a read-only semantic and visual audit of the S0-M statement that 12 rows were selected for future S1-L work. It identifies the generating code, separates mapping-anchor eligibility from SAR-structure eligibility, reconstructs vehicle-level GT segments, and directly reviews timelines and raw SAR contact pages.

S0-MV may add audit manifests, a report, a validator, and temporary visualizations. It must not modify any existing S0/S0-M formal product, refit or freeze a mapping, change canonical identity or synchronization, consume P1-F propagation, extract peaks/islands/ridges, generate candidate boxes, run a Gate/selector/ranking/oracle, train a model, or perform automatic annotation.

## Authoritative inputs

- `manifests/oty2/oty2_s0_sar_gt_quality_audit.csv`: 442-row reviewed SAR GT and S0-M Mask/quality/identity fields.
- `manifests/oty2/oty2_s0m_s1l_frame_eligibility_ledger.csv`: historical 12-row selection flags and their original `candidate_only_s1l_not_started` status.
- `manifests/oty2/oty2_s0_sar_golden_vehicle_threads.csv`: development, heldout, and diagnostic vehicle roles.
- `manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv`: optical visibility context.
- Raw SAR gray frames and optical reference frames under `D:\profile\research\data`.

The fixed `imaging_valid_mask` contract from S0-M remains authoritative. S0-MV reads it through existing per-GT fields and does not redefine it.

## Historical 12-frame source semantics

The historical rows are written by `tools/diagnostics/run_oty2_s0m_mask_anchor_pose_mapping_audit.py`. Its `select_s1l_candidates(...)` function:

1. keeps only `calibration_gold`, `calibration_usable`, `heldout_gold`, or `heldout_usable` mapping anchors;
2. groups those rows by `(scene, canonical_vehicle_id)`;
3. sorts each vehicle by `(center_theta_deg, center_radius_px)`;
4. keeps all rows when a group has at most four, otherwise keeps indices `0`, approximately `1/3`, approximately `2/3`, and the last index.

The rule is deterministic and capped at four rows per mapping-eligible vehicle. It is not `head(12)`, `[:12]`, random sampling, fixed temporal stepping, a continuous-segment rule, a pilot seed definition, or a formal S1-L input definition.

The historical `candidate` wording means only a future representative shortlist with `selection_status=candidate_only_s1l_not_started`. S0-MV must call these rows `representative previews, not the full eligible set`.

## Three separate eligibility contracts

### Mapping anchor

`mapping_anchor_eligible` belongs only to optical-to-SAR azimuth mapping. It may require reliable optical geometry/full visibility, canonical identity, synchronization, SAR GT quality, and absence of mapping-specific competition or geometry defects.

### S1-L structure frame

`s1l_structure_frame_eligible` belongs to GT-anchored SAR local-structure research. A row is eligible only when:

- a canonical vehicle is linked;
- GT quality is `gold` or `usable`;
- GT is completely inside `imaging_valid_mask`;
- no identity/geometry conflict or S0 exclusion applies;
- the SAR gray image is readable;
- the vehicle thread role is known.

Mapping-anchor eligibility and optical full visibility remain descriptive fields, not hard S1-L structure gates. Optical visibility may support pose/visibility interpretation or define a later high-confidence subset. Multi-vehicle competition remains an explicit context flag for local cropping and failure analysis; it is not silently converted into mapping eligibility.

### S1-L continuous segment

`s1l_continuous_segment_eligible` belongs to temporal structure research. Unique GT frames are grouped by scene and canonical vehicle and split when a consecutive GT-frame gap exceeds five. A segment is eligible only when:

- its benchmark role is development or heldout validation;
- it contains at least three structure-eligible GT frames;
- it contains no identity/geometry conflict;
- structure-eligible GT-frame coverage is at least `0.5`;
- its maximum internal GT-frame gap is at most five.

Raw frames inside a segment span are still shown when a GT row is absent, and the missing count is recorded. A single frame or two-frame fragment may support coordinate checks but cannot replace a temporal sequence.

## Visualization and direct-review contract

Temporary images are written only under:

`D:\profile\research\workspace\output\oty2_s0mv_s1l_input_semantics_visualization_20260715`

Required artifacts are:

- one timeline for each of 17 canonical-linked vehicles;
- one context page for each of the 12 historical previews, with current SAR/GT, Mask boundary, plus/minus ten raw frames, optical reference, roles, eligibility, segment ID, and the preview-only label;
- one or more raw-response contact pages for each eligible continuous segment;
- compact overview pages used only to accelerate direct review.

The manifest may use `directly_reviewed_complete` only after every timeline, preview context, eligible-segment contact page, and overview has been directly inspected. Images and videos remain temporary and must never be staged or committed.

No visualization may add a derived peak, island, ridge, skeleton, candidate box, ranking score, or predicted localization.

## Reproducibility and validation

Run from the SAR worktree with the research Python environment:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_s0mv_s1l_input_semantics_visualization.py --review-status directly_reviewed_complete
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_s0mv_outputs.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_s0m_mask_anchor_pose_mapping_outputs.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_s0_sar_foundation_outputs.py
```

The S0-MV validator checks that existing S0/S0-M files are unchanged from the frozen start HEAD, counts remain fixed, all visual artifacts exist outside Git with complete review status, the 12 rows remain previews rather than formal inputs, and no temporary image/video is staged.

## Decision language

Primary semantic conclusion:

`S1L_ELIGIBILITY_WAS_INCORRECTLY_TIED_TO_MAPPING_ANCHORS`

Descriptive interpretation of the 12 rows:

`12_FRAMES_ARE_ONLY_REPRESENTATIVE_PREVIEWS`

Final S0-MV state after complete direct review:

`S0MV_S1L_INPUT_SEMANTICS_CLEAR`

`CLEAR` authorizes redesign of the S1-L input ledger using the independent structure and temporal contracts. It does not authorize S1-L structure extraction.
