# OTY2 Observation Component Grouping Dry Run

Timestamp: `20260705_101430`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `271865d Audit suppression side effects and component grouping`

## Boundary

This pass implements an OTY0-post component-level grouping dry run. It does not change OTY0, OTY1, OTY1a, OTY1t, ByteTrack, P4G, detector weights, tracker parameters, or runtime configuration.

It does not tune thresholds, replace the main detector, enter SAR pairing, enter support audit, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, claim identity truth, or promote `GM_RM011` into the clean `215` pool.

The dry run keeps raw OTY0 detection rows as evidence. It emits diagnostic observation components and row policies only. It does not emit merged boxes or clean object streams.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_pretracking_observation_normalization_probe_20260705_024520.md`
- `reports/oty2/oty2_normalized_input_tracker_sensitivity_probe_20260705_093617.md`
- `reports/oty2/oty2_suppressed_row_side_effect_and_component_grouping_audit_20260705_095404.md`
- `reports/oty2/samples/oty2_suppressed_row_side_effect_samples_20260705_095404.csv`
- `tools/diagnostics/run_oty0_pretracking_observation_grouping_audit.py`
- `tools/diagnostics/run_oty0_pretracking_observation_normalization_probe.py`

## New Script

```text
tools/diagnostics/run_oty0_observation_component_grouping_dryrun.py
```

The script:

1. reads an existing OTY0 detection table;
2. groups detections by `scene + optical_frame_num`;
3. reuses the existing same-frame pair classifier;
4. builds a graph from candidate pair labels;
5. converts connected components into `observation_component_id`;
6. assigns component and row-level tracking/context policies;
7. optionally reads the previous side-effect sample table to mark known continuity-risk suppressed rows;
8. writes component, row-role, scene-summary, and JSON sidecar files under ignored `outputs/`.

No boxes are merged, deleted, or rewritten.

## Commands

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_observation_component_grouping_dryrun.py --scene GM_RM011 --detector-label yolo11l_baseline --input-detection-table outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv --output-dir outputs\oty0_observation_component_grouping_dryrun_20260705_101430 --timestamp 20260705_101430 --side-effect-samples reports\oty2\samples\oty2_suppressed_row_side_effect_samples_20260705_095404.csv
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_observation_component_grouping_dryrun.py --scene GM_RM019 --detector-label yolo11l_baseline --input-detection-table outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv --output-dir outputs\oty0_observation_component_grouping_dryrun_20260705_101430 --timestamp 20260705_101430 --side-effect-samples reports\oty2\samples\oty2_suppressed_row_side_effect_samples_20260705_095404.csv
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_observation_component_grouping_dryrun.py --scene GM_RM017 --detector-label yolo11l_baseline --input-detection-table outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv --output-dir outputs\oty0_observation_component_grouping_dryrun_20260705_101430 --timestamp 20260705_101430 --side-effect-samples reports\oty2\samples\oty2_suppressed_row_side_effect_samples_20260705_095404.csv
```

## Outputs

Ignored runtime/probe output root:

```text
outputs/oty0_observation_component_grouping_dryrun_20260705_101430/
```

Per scene, the dry run writes:

- `<scene>_yolo11l_baseline_observation_components.csv`
- `<scene>_yolo11l_baseline_observation_component_rows.csv`
- `<scene>_yolo11l_baseline_observation_component_scene_summary.csv`
- `<scene>_yolo11l_baseline_observation_component_grouping_dryrun.json`

Committed small summary:

```text
reports/oty2/samples/oty2_observation_component_grouping_summary_20260705_101430.csv
```

## Scene Summary

| Scene | Detections | Frames | Components | Candidate components | Orphan components | Clean duplicate pressure | Continuity-useful duplicate context | Partial/full review | Neighbor/multi-object competition | Unresolved/review |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 422 | 233 | 333 | 70 | 263 | 7 | 5 | 38 | 9 | 11 |
| `GM_RM019` | 334 | 193 | 227 | 72 | 155 | 0 | 0 | 26 | 33 | 13 |
| `GM_RM017` | 215 | 100 | 141 | 56 | 85 | 3 | 0 | 8 | 29 | 16 |

## Row Policy Summary

| Scene | `secondary_suppress_for_tracking` rows | `secondary_keep_for_continuity_context` rows | `keep_block_auto_grouping` rows | `review_required` rows | Known side-effect components |
| --- | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | 7 | 7 | 17 | 58 | 9 |
| `GM_RM019` | 0 | 0 | 63 | 44 | 4 |
| `GM_RM017` | 3 | 0 | 47 | 24 | 0 |

## Required Answers

1. Components per scene:

`GM_RM011` has `333` components, `GM_RM019` has `227`, and `GM_RM017` has `141`. Candidate multi-box components are `70`, `72`, and `56` respectively.

2. Clean duplicate pressure:

`GM_RM011` has `7` clean duplicate-pressure components. `GM_RM017` has `3`. `GM_RM019` has `0`, because its suppressed and candidate components are better explained by partial/full state, neighbor competition, or review-required ambiguity.

3. Continuity-useful duplicate context:

`GM_RM011` has `5` continuity-useful duplicate-context components. These are driven by the prior side-effect audit where some raw secondaries participated in duplicate-overlap tracks or sat in clusters that produced normalized replay continuity side effects. `GM_RM019` and `GM_RM017` have `0` under this dry-run policy.

4. Partial/full review context:

`GM_RM011` has `38`, `GM_RM019` has `26`, and `GM_RM017` has `8` partial/full review components. These are not safe for automatic grouping because partial/full and shape tags can explain a breakpoint without proving identity.

5. Neighbor/multi-object competition:

`GM_RM011` has `9`, `GM_RM019` has `33`, and `GM_RM017` has `29` neighbor/multi-object competition components. These should block automatic grouping and be preserved as competition context.

6. Unresolved/review-required:

`GM_RM011` has `11`, `GM_RM019` has `13`, and `GM_RM017` has `16` unresolved/review-required components. These contain unjudgeable or mixed evidence and should not be used as automatic tracker input replacement.

7. Does component grouping reduce the pair-suppression risk?

Yes. Pair-level normalization suppressed all eligible duplicate-like secondaries. Component grouping separates the policy into tracking and fragment-context decisions. In `GM_RM011`, rows at frames `48`, `50`, `212`, `213`, and `214` are no longer simple inactive secondaries; they become `secondary_keep_for_continuity_context` with `preserve_as_continuity_bridge_candidate`. Frame `165` becomes `review_required` partial/full state evidence. Frames `47`, `289`, and `290` remain clean duplicate-pressure candidates.

8. GM_RM011 key components:

| Frame group | Component interpretation |
| --- | --- |
| `47-50` | Frame `47` has a clean duplicate-pressure component; frames `48` and `50` are continuity-useful duplicate context. There was no separate suppressed-row component at frame `49` in the side-effect sample. |
| `165` | The duplicate-like row is reclassified as `partial_full_review_context` because it carries `partial_visible`, `partial_to_full_transition`, and `shape_instability` tags. |
| `212-214` | Each frame becomes `continuity_useful_duplicate_context`; secondaries are preserved as continuity bridge candidates rather than direct inactive rows. |
| `289-290` | Both frames have clean duplicate-pressure components suitable for `secondary_suppress_for_tracking` in a probe, while still preserving duplicate-pressure evidence. |

9. What should be passed into OTY1/OTY1a fragment relation audit:

Pass the row-role fields, not a clean stream:

- raw `det_id`;
- `observation_component_id`;
- `component_role`;
- `component_conflict_family`;
- `component_policy`;
- `tracking_policy`;
- `fragment_context_policy`;
- `suppression_risk`;
- `temporal_review_needed`;
- pair labels and state tags;
- primary candidate.

Raw OTY0 rows remain evidence. Suppressed or secondary rows must remain available to OTY1/OTY1a as fragment context.

10. Next step:

The next step should be fragment relation audit using component context. A tracker replay with component-policy input is useful later, but only after OTY1/OTY1a decides how to consume `secondary_keep_for_continuity_context`, partial/full state evidence, and competition blockers.

## Interpretation

The dry run changes the mechanism direction from pair-level inactive suppression to component-level evidence routing. This directly addresses the side effect found in the previous tracker sensitivity probe: active-only suppression can reduce duplicate-overlap pressure while increasing fragmentation or reactivation.

The component output gives the fragment layer enough context to avoid treating all secondaries the same:

- clean duplicate pressure can be suppressed in a bounded tracker-policy probe;
- continuity-useful duplicate context should remain available for bridge reasoning;
- partial/full state components should remain review-safe and state-aware;
- neighbor/multi-object competition should block automatic grouping;
- unresolved components should stay review-required.

## Conclusion

```text
COMPONENT_GROUPING_READY_FOR_FRAGMENT_RELATION_AUDIT
```

Component grouping is ready to feed an OTY1/OTY1a fragment relation audit as diagnostic context. It is not yet a mainline tracker input replacement.

## Explicit Non-Actions

- No OTY0 runtime was changed.
- No OTY1/OTY1a/OTY1t/ByteTrack runtime was changed.
- No detector was replaced.
- No tracker parameters were tuned.
- No threshold tuning was performed.
- No SAR pairing was run.
- No support audit was run.
- No final annotation was generated.
- No revised GT was generated.
- No final box was generated.
- No selector/ranking output was generated.
- No weighted fusion was used.
- No identity truth was claimed.
- `GM_RM011` was not promoted into the clean `215` pool.
