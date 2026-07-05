# OTY2 Suppressed-Row Side-Effect And Component Grouping Audit

Timestamp: `20260705_095404`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `1c040f7 Probe tracker sensitivity to normalized input`

## Boundary

This pass audits side effects from the existing shadow pretracking normalization probe and designs the next component-level grouping direction. It does not change OTY0, OTY1, OTY1a, OTY1t, ByteTrack, P4G, detector weights, tracker parameters, or runtime configuration.

It does not tune thresholds, replace the main detector, enter SAR pairing, enter support audit, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, claim identity truth, or promote `GM_RM011` into the clean `215` pool.

The audit uses existing ignored outputs only. Tracker IDs are diagnostic hypotheses, not identity truth.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_pretracking_observation_normalization_probe_20260705_024520.md`
- `reports/oty2/oty2_normalized_input_tracker_sensitivity_probe_20260705_093617.md`
- `tools/diagnostics/run_oty0_pretracking_observation_normalization_probe.py`
- `tools/diagnostics/run_oty1t_tracker_audit_from_normalized_oty0.py`

Existing ignored outputs inspected:

- `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/`
- `outputs/oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617/`

Committed sample table:

- `reports/oty2/samples/oty2_suppressed_row_side_effect_samples_20260705_095404.csv`

The sample table contains detection IDs, diagnostic labels, scalar grouping proxies, raw tracker role, local tracker deltas, and recommended component policies. It contains no bbox coordinates, final annotations, revised GT, final boxes, selector/ranking output, or runtime prediction artifact.

## Method

For each mainline YOLO11l normalized table, the audit selected rows with:

```text
active_for_tracking=false
normalization_action=suppress_duplicate_like_for_tracking
```

For those rows, it compared:

- normalization action and grouping label;
- raw tracker assignment for the suppressed secondary detection;
- raw unmatched diagnosis bucket when the row was unmatched;
- raw track status when the row was tracked;
- raw and normalized frame-level tracker event counts near the suppressed frame;
- raw and normalized track identity-status distributions.

The local event window is the suppressed frame plus or minus three frames. This is only a side-effect probe, not a temporal identity claim.

## Scene-Level Summary

| Scene | Suppressed YOLO11l rows | Suppressed frames | Raw tracker effect of suppressed rows | Normalized tracker side effect |
| --- | ---: | --- | --- | --- |
| `GM_RM011` | 9 | `47, 48, 50, 165, 212, 213, 214, 289, 290` | 6 rows were raw duplicate-overlap unmatched; 3 rows were raw tracked duplicate-overlap hypotheses | Duplicate-overlap hypotheses/events drop to zero, but fragmented tracks increase `5 -> 8` and reactivated events increase `11 -> 13` |
| `GM_RM019` | 4 | `1, 2, 4, 26` | 3 rows were raw unmatched, including one neighbor-ambiguous unmatched row; 1 row was a raw tracked duplicate-overlap hypothesis | Duplicate-overlap hypotheses/events drop `8 -> 7`, but short tracks increase `9 -> 10` |
| `GM_RM017` | 0 | none | no active-only suppression | Raw and normalized tracker diagnostics are identical |

## GM_RM011 Suppressed Rows

The 9 suppressed rows form four local groups:

| Group | Frames | Evidence | Side-effect interpretation |
| --- | --- | --- | --- |
| Early edge/class-instability component | `47, 48, 50` | all high-overlap class-instability duplicate-like rows; frame `48` secondary was a raw tracked duplicate-overlap hypothesis; frames `47` and `50` were duplicate-overlap unmatched | Suppression removes duplicate pressure, but the normalized run collapses the raw duplicate tracks into one track with a lost/reactivated break near frame `52` |
| Single partial/full duplicate candidate | `165` | raw secondary was duplicate-overlap unmatched; tags include `partial_visible`, `partial_to_full_transition`, and `shape_instability` | Suppression is useful for duplicate pressure, but the state is not safe enough for blind inactive-only policy |
| Mid edge/class-instability component | `212, 213, 214` | frame `212` was duplicate-overlap unmatched; frames `213` and `214` were tracked duplicate-overlap hypotheses | Suppression removes duplicate-track events, but the normalized component becomes a fragmented track spanning `211-245`; secondaries should remain fragment context |
| Late edge/class-instability component | `289, 290` | both suppressed rows were duplicate-overlap unmatched; local event counts did not materially change | These are the cleanest current examples of safe probe suppression, still not identity truth |

Detailed row samples are in the committed CSV.

## Direct Answers

1. GM_RM011 suppressed rows and frames:

`GM_RM011_000047_003`, `GM_RM011_000048_003`, `GM_RM011_000050_003`, `GM_RM011_000165_003`, `GM_RM011_000212_002`, `GM_RM011_000213_002`, `GM_RM011_000214_002`, `GM_RM011_000289_003`, and `GM_RM011_000290_003`.

They occur at frames `47`, `48`, `50`, `165`, `212`, `213`, `214`, `289`, and `290`.

2. Nearby side effects:

The early `47-50` component loses raw duplicate/ambiguous events, but normalized replay introduces a `track_reactivated` event near frame `52`. The `212-214` component removes duplicate-track events but leaves a normalized fragmented hypothesis. The `165` and `289-290` groups do not show a new local event increase in the inspected plus-or-minus-three-frame window.

3. Raw tracker role:

Six GM_RM011 suppressed rows were raw duplicate-overlap unmatched: frames `47`, `50`, `165`, `212`, `289`, and `290`. Three were raw tracked duplicate-overlap hypotheses: frames `48`, `213`, and `214`.

4. Clearly useful suppressions:

Frames `47`, `289`, and `290` are the cleanest duplicate-pressure reductions: the suppressed secondary was duplicate-overlap unmatched, the primary remained tracked, and no local continuity event increase was visible. They can remain `secondary_suppress_for_tracking` in the next probe, while preserving the raw row as component context.

5. Suppressions that may harm continuity:

Frames `48`, `50`, `212`, `213`, and `214` should not be treated as simple inactive rows. They sit inside components where raw duplicate tracks or nearby primary reassignment can carry temporal bridge information. These should move toward `secondary_keep_for_continuity_context`.

6. Rows that should become `keep_with_duplicate_context` or review-context:

`GM_RM011_000048_003`, `GM_RM011_000050_003`, `GM_RM011_000212_002`, `GM_RM011_000213_002`, and `GM_RM011_000214_002` should feed fragment relation context. `GM_RM011_000165_003` should be review-safe context because its tags include partial/full and shape instability.

## Component-Level Grouping Design

The next normalization design should not use pair-level greedy suppression as the final policy. It should build same-frame duplicate-like components first.

### 1. Build The Pair Graph

Nodes:

- OTY0 detection observations from one scene and one frame.

Edges:

- high-overlap duplicate-like pair;
- class-instability duplicate-like pair;
- possible partial/full pair;
- close-neighbor or crowding competition pair;
- unjudgeable same-frame pair.

The graph should keep edge labels and state tags. It should not merge boxes and should not create final boxes.

### 2. Connected Components

Connected components become observation components:

```text
observation_component_id = scene + frame + component_index
```

A component can contain more than one pair. This prevents a row from being suppressed by one pair while another pair in the same frame says it is a partial/full or competition case.

### 3. Component Roles

Each row receives:

- `component_role=primary_observation`
- `component_role=secondary_observation`
- `component_role=competing_observation`
- `component_role=orphan_observation`

This role is a diagnostic role only. It is not identity truth.

### 4. Secondary Policies

Secondary observations should not all become inactive. The policy should be one of:

| Policy | Meaning | Tracker-side use | Fragment-relation use |
| --- | --- | --- | --- |
| `secondary_suppress_for_tracking` | duplicate-like secondary that was raw unmatched duplicate-overlap and has low continuity risk | may be excluded from active tracker input in probe | preserve as evidence attached to component |
| `secondary_keep_for_continuity_context` | secondary was raw tracked or sits in a component with continuity side effects | do not feed blindly as normal detection; evaluate in controlled tracker probe | must be available to OTY1a fragment relation audit |
| `secondary_review_required` | state tags or competition make suppression unsafe | no automatic grouping | preserve for visual/sample review and blocked/ambiguous relation |

### 5. Primary Selection

Primary selection must not rely only on confidence. It should consider:

- confidence;
- class stability inside the component;
- area relation and whether the box is partial/full;
- boundary contact and truncation-like tags;
- center consistency with adjacent active observations;
- whether the candidate primary produces avoidable lost/reactivated behavior;
- whether a secondary appears temporally useful in raw tracking.

The primary is still a runtime-safe observation handle, not identity truth.

### 6. Required Output Fields

The next dry-run component table should preserve:

- `observation_component_id`;
- `component_role`;
- `tracking_policy`;
- `fragment_context_policy`;
- `suppression_risk`;
- `temporal_review_needed`;
- raw OTY0 `det_id`;
- raw bbox and confidence fields in ignored outputs only;
- state tags and grouping labels;
- primary/secondary relation provenance.

Committed reports should summarize these fields without committing runtime prediction artifacts.

## How Raw, Active, And Suppressed Rows Should Enter Fragment Audit

Raw OTY0 rows remain the evidence source. They must not be discarded because active-only replay showed a cleaner tracker table.

`active_for_tracking=true` rows can be used as a controlled tracker input probe, but only as one view of the observation field.

Suppressed secondary rows should enter OTY1a fragment relation audit as context:

- duplicate-like unmatched rows can explain duplicate pressure;
- raw tracked duplicate-overlap rows can explain why a fragmented normalized track may need a component-level bridge candidate;
- partial/full and edge-contact rows can explain shape transition uncertainty;
- neighbor-ambiguous rows can block automatic grouping.

The fragment audit should read these rows as component evidence, not as active tracker detections and not as identity truth.

## Mechanism Recommendation

Do not continue current pair-level suppression as the mechanism. It is useful as a probe and should remain available for bounded sensitivity runs, but it is not safe as a mainline replacement.

Next recommended step:

```text
Implement component-level grouping dry run before any further tracker-side replacement probe.
```

The dry run should classify each same-frame component into:

- clean duplicate pressure;
- continuity-useful duplicate context;
- partial/full review context;
- neighbor or multi-object competition;
- unresolved.

Then the suppressed rows should be passed into OTY1a fragment relation audit as context fields, not removed from the evidence set.

GM_RM011 suppressed-row visual/sample review is useful before any stronger automatic suppression claim, especially for frames `48`, `50`, `165`, and `212-214`. The current evidence is enough to justify component-level dry-run design, but not enough to replace tracker input.

Bounded tracker-side probing can continue after the component-level dry run, using three variants:

1. raw OTY0 input;
2. active-only pair-suppressed input;
3. component-policy input with `secondary_keep_for_continuity_context` preserved for fragment relation context.

## Conclusion

```text
PAIR_SUPPRESSION_USEFUL_BUT_NEEDS_COMPONENT_GROUPING
```

Pair-level active-only suppression reduces duplicate-overlap pressure, but it can convert duplicate competition into continuity risk. The next safe optimization is component-level grouping with separate tracking and fragment-context policies.

## Explicit Non-Actions

- No OTY0 runtime was changed.
- No OTY1/OTY1a/OTY1t/ByteTrack runtime was changed.
- No mainline detector was replaced.
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
