# OTY2 Temporal Window to Spatial Constraint Design

This document designs the next interface from object-level SAR temporal windows to a future time-window-driven SAR spatial constraint stage. It is design-only: it does not read SAR images, generate SAR spatial regions, generate candidate boxes, score candidates, use SAR GT, tune thresholds, or produce annotation proposals.

## Layer Separation

| layer | allowed meaning | forbidden promotion |
| --- | --- | --- |
| temporal window | inclusive SAR frame range for an optical object hypothesis | not a SAR location and not a candidate box |
| spatial prior | future geometry-only shell or interval proposal derived from optical state and scene geometry | not SAR evidence and not final localization |
| SAR evidence | future SAR content inspected inside an allowed prior, only after scope is opened | not GT and not an automatic annotation decision |
| GT coverage | posthoc audit only | cannot construct runtime priors |
| annotation proposal | later explicitly authorized stage only | cannot be produced by this design stage |

## Future Spatial-Constraint Inputs

The next stage should consume these upstream fields:

- From temporal windows: `scene`, `object_hypothesis_id`, `sar_start_frame`, `sar_end_frame`, `sar_window_frame_count`, `sync_mode`, `offset_seconds`, `software_sync_jitter_ms`, `padding_sar_frames`, `object_state_category`, `uses_primary_observations`, `uses_secondary_observations`, `readiness_status`, `confidence_status`, `blockers`.
- From optical object state: primary observation stream, secondary observation stream, object frame bounds, optical bbox envelope, partial/full or occlusion state, edge-visible state, duplicate observation state, handoff/reactivation indicators, ambiguity indicators, and runtime-safe provenance.
- From scene geometry: frame inventory, optical frame dimensions, SAR frame inventory, configured fan/polar calibration, azimuth mapping contract, range convention, and any runtime-safe coarse pose or size priors.

The next stage must not consume final/manual/oracle/review fields, SAR GT, posthoc IoU, selector/ranking output, tuned thresholds, or annotation labels as runtime construction inputs.

## Connection Logic

1. Temporal gating first: only `eligible_primary_spatial_constraint_input` and `eligible_uncertainty_expanded_spatial_constraint_input` rows enter normal spatial-prior construction.
2. Low-confidence temporal windows remain review-only context unless a later bounded review mode is explicitly opened.
3. For each eligible object, the SAR frame range limits when a future spatial prior may be evaluated.
4. Optical object state defines the shape and uncertainty of a future prior shell; it must not collapse secondary observations or ambiguity into identity truth.
5. Scene geometry maps optical state into future azimuth/range prior descriptors. SAR evidence, if later authorized, is evaluated only inside those descriptors.

## Geometry Priors That Can Be Designed Before Reading SAR Images

The following can be specified as contracts without reading SAR content:

- Azimuth interval policy from optical object center/envelope and scene fan mapping.
- Range-shell policy from runtime-safe geometry and coarse depth/size priors, kept broad when calibration is weak.
- Vehicle size prior as a range, not a single fixed box.
- Coarse yaw/main-axis prior as optional weak orientation context, not a hard final heading.
- Edge/truncation recovery policy that expands the prior when an object is near fan or optical-frame boundaries.
- Secondary-observation expansion policy that keeps duplicate, partial, and handoff uncertainty visible.
- Ambiguity policy that either blocks normal spatial-prior construction or marks the row review-only.

This document does not instantiate any actual SAR spatial region. A future implementation may emit region descriptors only after the OTY3 scope is opened.

## Uncertainty Effects

| signal | future spatial effect | runtime/posthoc status |
| --- | --- | --- |
| stable primary continuity | smaller azimuth/range margin; primary prior can be normal input | runtime prior |
| secondary observations | expand azimuth/range margin; keep secondary provenance | runtime uncertainty prior |
| edge-visible, partial, or occluded state | expand toward missing side; do not require full vehicle center inside the shell | runtime uncertainty prior |
| duplicate observations | allow wider optical envelope or multiple prior components | runtime uncertainty prior |
| handoff/reactivation | expand along time and geometry continuity; do not assert identity truth | runtime uncertainty prior |
| ambiguous/review-required state | review-only or blocked from normal spatial prior | runtime blocker/context only |
| SAR GT coverage | evaluate coverage after the prior exists | posthoc audit only |
| selector/ranking score | not allowed in this stage | forbidden runtime input |

## Runtime Priors vs Posthoc Audit

Runtime priors may use object-level optical state, temporal windows, software-sync metadata, frame inventories, and runtime-safe scene geometry. Posthoc audit may later use GT coverage or manual review only to evaluate an already-generated prior. Posthoc audit results must not be fed back into runtime prior construction without a separate explicitly authorized stage.

## Future Boundary for SAR Spatial Search

If a later stage enters SAR spatial search, it should remain bounded as follows:

- Start from object-level temporal windows and runtime-safe geometry priors.
- Read SAR image content only after the scope explicitly opens SAR search.
- Do not use SAR GT, final/manual/oracle/review fields, selector/ranking outputs, or tuned thresholds to construct the search prior.
- Keep SAR evidence as evidence, not as identity truth or an automatic annotation proposal.
- Emit diagnostics separately from any later annotation proposal stage.

## Scene Handling

- `GM_RM011`: temporal metadata is usable under the 24:50 software-sync contract, but target-level input is unavailable because the optical object stream is missing.
- `GM_RM017`: object-level temporal windows are available for quality review and future spatial-prior input description.
- `GM_RM019`: object-level temporal windows are available; low-confidence and not-ready rows must remain separated from normal downstream inputs.

## Boundary Flags

- sar_image_content_used: `false`
- sar_spatial_search_entered: `false`
- sar_search_region_generated: `false`
- sar_candidate_boxes_generated: `false`
- sar_gt_used: `false`
- final_manual_oracle_review_runtime_fields_used: `false`
- selector_or_ranking_used: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- detection_box_level_merge_reintroduced: `false`
