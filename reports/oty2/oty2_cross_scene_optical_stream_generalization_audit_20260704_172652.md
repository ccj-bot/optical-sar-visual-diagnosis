# OTY2 Cross-Scene Optical Stream Generalization Audit

Timestamp: `20260704_172652`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`

## Boundary

This audit stays inside OTY2 posthoc mechanism diagnosis and checks only the optical object-stream mechanism across scenes.

No SAR pairing, support audit, Lane A morphology, final annotation, revised GT, final box, selector/ranking logic, threshold tuning, weighted fusion, clean `215` promotion, or identity-truth declaration was performed. SAR GT, SAR image observation, and GT-local energy fields were not used for runtime optical-stream construction or for this optical-stream comparison.

`PASS_WITH_UNCERTAINTY` is treated as schema/result availability for diagnosis, not as mechanism success.

## Inputs Reused

No OTY0/OTY1/OTY1a/OTY1t/P4G reconstruction was rerun. This report reuses existing same-stage reports and generated artifacts:

| Scene | OTY0 | OTY1 | OTY1a | OTY1t ByteTrack | P4G object hypotheses |
| --- | --- | --- | --- | --- | --- |
| `GM_RM011` | `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream` | `outputs\oty1_optical_tracklet_audit_20260704_gm011_oty_stream` | `outputs\oty1a_fragment_merge_audit_20260704_gm011_oty_stream` | `outputs\oty1t_tracker_audit_bytetrack_20260704_gm011_oty_stream` | `outputs\oty1t_object_hypothesis_generalization_audit_20260704_gm011_oty_stream` |
| `GM_RM017` | `outputs\oty0_yolo_detection_stream_audit_20260701_181317` | `outputs\oty1_optical_tracklet_audit_20260701_181347` | `outputs\oty1a_fragment_merge_audit_20260701_190431` | `outputs\oty1t_tracker_audit_bytetrack_20260701_205803` | `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500` |
| `GM_RM019` | `outputs\oty0_yolo_detection_stream_audit_20260701_170751` | `outputs\oty1_optical_tracklet_audit_20260701_175422` | `outputs\oty1a_fragment_merge_audit_20260701_190559` | `outputs\oty1t_tracker_audit_bytetrack_20260701_205928` | `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500` |

Report context reused:

- `reports\oty2\oty2_gm011_object_stream_reconstruction_report_20260704_gm011_oty_stream.md`
- `reports\oty1\oty1_cross_scene_findings_and_recommendations_20260701.md`
- `reports\oty1a\oty1a_cross_scene_fragment_merge_summary_20260701_190559.md`
- `reports\oty1t\oty1t_tracker_diagnosis_summary_20260701_205928.md`
- `reports\oty1t\oty1t_object_hypothesis_generalization_summary_20260701_231500.md`

The comparison below was computed by read-only inspection of the existing CSV/JSON artifacts.

## Detection Continuity

| Scene | Optical frames | Detection rows | Frames with detections | Empty frames | Per-frame detection count | Classes | Confidence p25/median/p75 | Crowded frames | Overlap pairs | Bad bbox rows |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: |
| `GM_RM011` | 368 | 422 | 233 | 135 | `0=135; 1=86; 2=107; 3=38; 4=2` | `car=413; truck=9` | `0.466172/0.826799/0.926538` | 147 | 102 / 233 same-frame pairs | 0 |
| `GM_RM017` | 368 | 215 | 100 | 268 | `0=268; 1=31; 2=29; 3=34; 4=6` | `bus=4; car=153; truck=58` | `0.885724/0.915091/0.932095` | 69 | 51 / 167 same-frame pairs | 0 |
| `GM_RM019` | 368 | 334 | 193 | 175 | `0=175; 1=93; 2=70; 3=22; 4=5; 5=3` | `bus=6; car=327; truck=1` | `0.333000/0.543359/0.880918` | 100 | 48 / 196 same-frame pairs | 0 |

Detection is not the primary hard blocker. All three scenes have countable optical frames, generated detections, and bbox-coordinate sanity. GM_RM011 has the most detection rows and the most frames with detections, but also the most crowded frames and overlap pairs. The issue is therefore not simply "no detector output"; the detector creates enough observations to expose association pressure.

GM_RM017 looked easier because it has fewer detection-active frames, fewer crowded frames, and a much cleaner tracker outcome later. GM_RM019 already shows low confidence quartiles and heavy fragmentation risk, so it should not be treated as a clean precedent.

## Track Fragmentation

| Scene | OTY1 tracklets | OTY1 median/max length | OTY1 short `<=3` | OTY1 statuses | OTY1t tracks | OTY1t median/max length | OTY1t short `<=3` | Unmatched detections | ID-switch count | Duplicate-overlap count | OTY1t statuses |
| --- | ---: | --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- |
| `GM_RM011` | 45 | `4/42` | 20 (0.444) | `ambiguous_geometry_review=28; fragmented_short_track=17` | 28 | `5.500/40` | 6 (0.214) | 91 | 10 | 8 | `duplicate_overlap_review=5; fragmented_tracker_hypothesis=5; possible_id_switch_review=5; short_tracker_hypothesis=2; tracker_stable_hypothesis=11` |
| `GM_RM017` | 10 | `7/54` | 4 (0.400) | `ambiguous_geometry_review=6; fragmented_short_track=4` | 6 | `42.500/49` | 0 (0.000) | 19 | 2 | 0 | `possible_id_switch_review=2; tracker_stable_hypothesis=4` |
| `GM_RM019` | 54 | `2/52` | 35 (0.648) | `ambiguous_geometry_review=24; fragmented_short_track=30` | 21 | `3/39` | 11 (0.524) | 127 | 12 | 16 | `duplicate_overlap_review=8; fragmented_tracker_hypothesis=1; short_tracker_hypothesis=9; tracker_stable_hypothesis=3` |

GM_RM011's main failure type is track fragmentation under crowded, overlapping, boundary-contact optical observations. OTY1 creates 45 components from 422 detections, and all components are either ambiguous review or short fragments. ByteTrack reduces this to 28 tracks, but 91 detections remain unmatched and only 11 of 28 tracks are stable hypotheses.

GM_RM019 has the same failure family and is worse on short-track ratio, unmatched detections, duplicate overlap, and review-required object ratio. GM_RM017 has a lighter version: OTY1 is still ambiguous/fragmented, but ByteTrack produces six tracks with a much longer median length and no duplicate-overlap count.

The old "usable" scenes therefore did not prove identity continuity. GM_RM017 was easier, and GM_RM019 was already mechanism-uncertain.

## Multi-Object Competition And Shape/State Instability

| Scene | OTY0 crowded frames | Same-frame overlap pairs | OTY1 rows with same-frame neighbors | OTY1 boundary-contact rows | OTY1 truncation proxy | OTY1a ambiguous merge edges | OTY1a partial/full candidates | OTY1t p90/max center speed | OTY1t p90/max area change |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- |
| `GM_RM011` | 147 | 102 / 233 | 336 | 422 | `edge_contact_and_size_change_review=93; edge_contact_review=247; low_no_contact_or_large_size_change=80; size_change_review=2` | 13 | 25 | `40.2/69.9` | `0.220/1.092` |
| `GM_RM017` | 69 | 51 / 167 | 184 | 215 | `edge_contact_and_size_change_review=24; edge_contact_review=69; low_no_contact_or_large_size_change=122` | 0 | 1 | `23.9/58.1` | `0.086/0.707` |
| `GM_RM019` | 100 | 48 / 196 | 241 | 334 | `edge_contact_and_size_change_review=32; edge_contact_review=106; low_no_contact_or_large_size_change=174; size_change_review=22` | 49 | 10 | `26.9/77.7` | `0.181/0.340` |

GM_RM011 is the strongest pressure test for same-frame competition and boundary/shape instability: it has the largest crowded-frame count, largest overlap-pair count, 336 OTY1 state rows with same-frame neighbors, all OTY1 rows marked with boundary contact, and 25 partial-to-full merge candidates. This means adjacent-frame geometry alone is not enough to decide continuity.

GM_RM019 exposes the same mechanism weakness through a different signature: many short tracks, many duplicate overlaps, many ambiguous competing merge edges, and many unmatched detections. GM_RM017 is less severe but still has same-frame neighbors, boundary-contact rows, possible ID-switch review, and four of six P4G objects requiring review.

## P4G Object-Hypothesis Readiness

| Scene | Object hypotheses | Object-frame rows | Orphans | Review required | Object type distribution | Same-object support | Recommended use | Readiness |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `GM_RM011` | 28 | 800 | 35 | 23 (0.821) | `ambiguous_object_hypothesis=6; main_track_with_secondary_observations=15; short_or_noise_track_hypothesis=2; stable_object_hypothesis=5` | `moderate=14; strong=8; weak=6` | `do_not_use_for_oty2=2; main_track_only=4; main_track_with_uncertainty_handoff=15; optional_continuity_hint_with_visual_review=6; tracklet_stitching_review_before_oty2=1` | `ready_with_uncertainty` |
| `GM_RM017` | 6 | 308 | 8 | 4 (0.667) | `ambiguous_object_hypothesis=1; main_track_with_secondary_observations=3; stable_object_hypothesis=2` | `moderate=3; strong=3` | `main_track_only=2; main_track_with_uncertainty_handoff=3; optional_continuity_hint_with_visual_review=1` | `ready_with_uncertainty` |
| `GM_RM019` | 21 | 672 | 42 | 19 (0.905) | `ambiguous_object_hypothesis=6; main_track_with_secondary_observations=4; short_or_noise_track_hypothesis=9; stable_object_hypothesis=2` | `moderate=8; strong=2; weak=11` | `do_not_use_for_oty2=9; main_track_only=2; main_track_with_uncertainty_handoff=4; optional_continuity_hint_with_visual_review=6` | `ready_with_uncertainty` |

All three scenes are `ready_with_uncertainty`, not clean mechanism successes. The old flow allowed object hypotheses to be produced and passed downstream as schema-compatible diagnostic inputs. It did not prove object identity, clean track continuity, or readiness for final pairing/support work.

## Answers To The Generalization Questions

1. GM_RM011's main failure type is not detector absence. It is a global optical-stream weakness: track fragmentation plus multi-object competition plus boundary/shape-state instability. Detector output exists, but the association mechanism cannot reliably convert dense, crowded detections into stable object identities.

2. GM_RM017 and GM_RM019 also have same-family risks. GM_RM017 is lighter and therefore looked usable: fewer tracks, longer ByteTrack median length, fewer unmatched detections, and no duplicate-overlap count. GM_RM019 is not a clean counterexample; it already shows severe short-track, duplicate-overlap, unmatched-detection, and review-required risk.

3. The old workflow looked like it passed because the pass condition was largely table generation and schema compatibility. It accepted `ready_with_uncertainty` as a usable handoff state for diagnosis. That is not mechanism success.

4. The previous "passes" should be rephrased as schema-compatible object-hypothesis generation with unresolved identity uncertainty. They are not evidence that the optical target-stream mechanism generalizes cleanly.

5. The most important global adjustment area is not local detector threshold tuning. The priority is the optical association mechanism: tracker association, fragment-merge review semantics, object-level uncertainty propagation, and explicit multi-object competition handling. Detection postprocessing may need descriptive diagnostics, but it should not be locally tuned to make GM_RM011 pass.

## Implicit Mechanism Assumptions Exposed

The current optical stream implicitly assumes:

- detections are continuous enough for adjacent-frame association;
- boxes are smooth enough in center, area, and aspect ratio;
- a one-to-one adjacent-frame edge is enough to form a useful tracklet;
- same-frame targets are sufficiently separated;
- short gaps and late fragments are rare enough to defer;
- boundary contact and truncation do not dominate the stream;
- partial-object and full-object boxes can be reconciled by simple review candidates;
- object hypotheses can be useful even when identity is not confirmed.

GM_RM011 violates the separation, smoothness, boundary/truncation, and fragment rarity assumptions. GM_RM019 violates many of the same assumptions and should be treated as prior warning evidence. GM_RM017 mostly avoided the worst case because its tracker output was simpler, not because the mechanism was proven.

## Global Mechanism Adjustment Recommendations

- Add an explicit optical-stream readiness taxonomy that separates `schema_compatible`, `ready_with_uncertainty`, and `mechanism_stable`. Do not let `ready_with_uncertainty` imply success.
- Treat OTY1a/P4G merge and secondary-observation links as review or uncertainty carriers unless a later globally justified mechanism proves identity continuity. Do not convert them to identity truth.
- Improve global multi-object competition handling before any scene-specific repair: preserve competing hypotheses, duplicate overlaps, same-frame neighbor flags, and orphan detections as first-class uncertainty.
- Add cross-scene diagnostics for fragmentation and review burden as a standard gate before support/pairing audits.
- Diagnose state interpretation globally: boundary contact, truncation proxy, partial-to-full transitions, and large center/area jumps should be mechanism inputs for uncertainty, not automatic merge or discard rules.
- If tracker or fragment-merge changes are proposed later, evaluate them across GM_RM011, GM_RM017, and GM_RM019 together. Do not locally tune thresholds to make GM_RM011 pass.

## Next Step

Recommendation: `CROSS_SCENE_OPTICAL_STREAM_GENERALIZATION_AUDIT_COMPLETE__GLOBAL_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_REQUIRED`

The next correct step is a global optical-stream mechanism revision plan or diagnostic probe across the same scenes, focused on association, fragment merge semantics, state instability, and multi-object competition. It should remain optical-only and should not proceed to SAR pairing, support audit, final annotations, revised GT, selector/ranking, threshold tuning, weighted fusion, or clean `215` promotion.

## Generated Artifacts

This audit created only this report. It did not create or modify OTY0/OTY1/OTY1a/OTY1t/P4G runtime outputs, image atlases, final annotations, revised GT, runtime prediction artifacts, selector/ranking outputs, or large binaries.
