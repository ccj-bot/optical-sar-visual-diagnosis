# OTY2 Counterfactual Confounder Triage And Handoff

Updated: 2026-07-03

This document closes the current OTY2 counterfactual/confounder triage stage. It is not an experiment proposal, not OTY3, not a final automatic annotation plan, not selector/ranking, and not training or threshold tuning.

## What This Stage Completed

- Established the 442 GT ledger and kept the pools separated.
- Built optical-to-SAR support-region observation probes.
- Audited range narrowing and peak competition.
- Reframed SAR evidence from top1 peak to scatter cluster plus temporal persistence.
- Ran counterfactual / negative-control support validation.
- Triage-tested why wrong-object, wrong-frame, and azimuth-shift controls remain high.

## More Reliable Conclusions

- Broad support is a coverage baseline, not localization: broad true top-k near-GT is `0.0279`.
- Range/state constraints carry the clearest posthoc signal: state-conditioned true is `0.8977`, random is `0.1163`, and range-shift is `0.0419`.
- SAR vehicles should be treated as extended scatter structures and temporal tubes, not single brightest points.
- Wrong-object and wrong-frame controls show that association is still unresolved.

## Posthoc Observations Only

- `topk_contains_near_gt_posthoc` is a validation metric, not runtime capability.
- State-conditioned range success is posthoc and must not be written as a runtime rule.
- Object-smoothed range trends, scene residuals, and shape-radius relations are hypotheses to validate.
- SAR GT and GT-near peak distances are posthoc evidence only.

## Directions Downgraded Or Rejected

- Top1 peak as target center is rejected.
- Top-k/cluster metric tuning alone is downgraded; it risks becoming local metric engineering.
- `associated_posthoc_strong` count is not a valid objective.
- Timing-only or wrong-frame-tolerant association is not enough to claim identity.
- Broad fan peak/background is not enough to localize a vehicle.

## Current Biggest Blockers

- Wrong-frame remains high: `0.9116`.
- Wrong-object remains high: `0.6977`.
- Azimuth-shift remains high: `0.7151`.
- GM_RM011 still lacks the current OTY optical object stream; it is not unannotated.
- GM_RM019 still benefits from limited manual optical GT / object-hypothesis review.

## What The Next Stage Should Not Do

- Do not generate final annotation proposals.
- Do not output selector/ranking.
- Do not train or tune thresholds.
- Do not claim identity truth.
- Do not write GT peak / GT residual into runtime prior.
- Do not write state-conditioned top-k success as a runtime rule.
- Do not mix dropout/no-match into clean morphology.
- Do not mix SAR-only into optical-SAR correspondence.
- Do not treat the GM_RM011 195 blocked rows as unannotated.
- Do not commit `MatlabToolboxZB.zip` or any zip.

## What The Next Stage Should Do

1. Gate provenance: separate runtime-safe optical/time/geometry/state gates from SAR observation and posthoc validation.
2. Object-time confounding: explain wrong-object and wrong-frame high cases before any association claim.
3. SAR scatter-structure mechanism: inspect compact, multi-peak, range-spread, azimuth-spread, diffuse, sidelobe-like, jumping, and stable tube structures.
4. Optical information bottleneck: derive which cues are runtime-safe and which are still posthoc.
5. GM_RM019 review: confirm object hypotheses, trajectory direction, and complete morphology frames.
6. GM_RM011 recovery: build the current OTY optical object stream before optical-SAR correspondence modeling.

## Why A New Session Should Take Over

This session has accumulated a long chain of reports and generated diagnostics. A new GPT/Codex session should start from this handoff and the committed reports so it can reason from a compact state, avoid repeating local top-k/cluster tuning, and focus on object-time confounding and gate provenance.

## Ledger To Preserve

```text
paired_optical_object_sar_gt = 215
blocked_missing_gm011_object_stream = 195
sar_only_gt = 20
dropout/no_oty_iou_match/temporal continuation pool = 12
```

## Provenance Labels

Use: `runtime_safe_optical_evidence`, `runtime_safe_temporal_evidence`, `runtime_safe_geometry_or_vehicle_physics`, `SAR_image_observation`, `SAR_temporal_observation`, `SAR_GT_posthoc_evidence`, `manual_or_review_anchor`, `hypothesis_to_validate`, and `insufficient_or_not_supported`.
