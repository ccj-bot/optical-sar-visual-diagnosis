# OTY2 Normalized Input Tracker Sensitivity Probe

Timestamp: `20260705_093617`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `32f287d Add pretracking observation normalization probe`

## Boundary

This pass is a bounded tracker-side sensitivity probe. It compares the current raw OTY0 detection table against the pretracking-normalized active-only table for the same scene and tracker settings.

It does not replace the mainline detector, modify OTY0, modify OTY1/OTY1a/OTY1t/ByteTrack runtime, tune tracker parameters, tune thresholds, enter SAR pairing, enter support audit, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, promote `GM_RM011` into the clean `215` pool, or claim identity truth.

`active_for_tracking=false` remains a shadow/probe flag only. The wrapper strips the normalized table to OTY0-compatible columns and keeps original bbox coordinates. No new bbox or clean object stream is generated.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_pretracking_observation_normalization_probe_20260705_024520.md`
- `reports/oty2/samples/oty2_pretracking_observation_normalization_summary_20260705_024520.csv`
- `tools/diagnostics/run_oty0_pretracking_observation_normalization_probe.py`
- `tools/diagnostics/run_oty1t_tracker_audit.py`
- `src/optical_state/tracker_audit.py`
- `src/optical_state/tracker_diagnosis.py`

## Probe Wrapper

New wrapper:

```text
tools/diagnostics/run_oty1t_tracker_audit_from_normalized_oty0.py
```

The wrapper exists because the main OTY1t audit script writes auxiliary report-side samples and expects a raw OTY0 detection table. This wrapper keeps the replay isolated under an ignored output directory and accepts either raw OTY0 rows or normalized active-only rows.

For normalized inputs, it:

1. reads the normalized detection table;
2. filters to `active_for_tracking=true`;
3. writes `tracker_input_detection_table.csv` with only OTY0-compatible detection columns;
4. runs the same ByteTrack replay helpers and default audit parameters used by the main OTY1t diagnostics;
5. writes all runtime/probe outputs under the requested ignored `outputs/` directory.

It does not call OTY1a, P4G, SAR pairing, support audit, final annotation, final box, revised GT, selector/ranking, or identity-truth logic.

## Inputs

Mainline YOLO11l sources:

| Scene | Raw OTY0 table | Normalized active-only source |
| --- | --- | --- |
| `GM_RM011` | `outputs/oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream/oty0_yolo_detection_table.csv` | `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM011_yolo11l_baseline_normalized_detection_table.csv` |
| `GM_RM019` | `outputs/oty0_yolo_detection_stream_audit_20260701_170751/oty0_yolo_detection_table.csv` | `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM019_yolo11l_baseline_normalized_detection_table.csv` |
| `GM_RM017` | `outputs/oty0_yolo_detection_stream_audit_20260701_181317/oty0_yolo_detection_table.csv` | `outputs/oty0_pretracking_observation_normalization_probe_20260705_024520/GM_RM017_yolo11l_baseline_normalized_detection_table.csv` |

The ByteTrack dependency was available for all six runs. `review_required_object_hypothesis_status` is `not_run_no_p4g_downstream_in_this_probe` because downstream P4G/object-hypothesis construction was intentionally not run.

## Commands

The completed runs used the same wrapper and default tracker settings. Raw runs used the full OTY0 table. Normalized runs used `--active-only`.

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene GM_RM011 --detector-label yolo11l_baseline --input-variant raw --input-detection-table outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv --output-dir outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM011_yolo11l_baseline_raw --timestamp 20260705_093617
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene GM_RM011 --detector-label yolo11l_baseline --input-variant normalized_active --input-detection-table outputs\oty0_pretracking_observation_normalization_probe_20260705_024520\GM_RM011_yolo11l_baseline_normalized_detection_table.csv --output-dir outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM011_yolo11l_baseline_normalized_active --timestamp 20260705_093617 --active-only

D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene GM_RM019 --detector-label yolo11l_baseline --input-variant raw --input-detection-table outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv --output-dir outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM019_yolo11l_baseline_raw --timestamp 20260705_093617
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene GM_RM019 --detector-label yolo11l_baseline --input-variant normalized_active --input-detection-table outputs\oty0_pretracking_observation_normalization_probe_20260705_024520\GM_RM019_yolo11l_baseline_normalized_detection_table.csv --output-dir outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM019_yolo11l_baseline_normalized_active --timestamp 20260705_093617 --active-only

D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene GM_RM017 --detector-label yolo11l_baseline --input-variant raw --input-detection-table outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv --output-dir outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM017_yolo11l_baseline_raw --timestamp 20260705_093617
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit_from_normalized_oty0.py --scene GM_RM017 --detector-label yolo11l_baseline --input-variant normalized_active --input-detection-table outputs\oty0_pretracking_observation_normalization_probe_20260705_024520\GM_RM017_yolo11l_baseline_normalized_detection_table.csv --output-dir outputs\oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617\GM_RM017_yolo11l_baseline_normalized_active --timestamp 20260705_093617 --active-only
```

## Generated Artifacts

Ignored runtime/probe output root:

```text
outputs/oty1t_normalized_input_tracker_sensitivity_probe_20260705_093617/
```

Each scene/variant output contains:

- `tracker_input_detection_table.csv`
- `oty1t_tracker_detection_assignments.csv`
- `oty1t_tracker_tracks.csv`
- `oty1t_tracker_state_timeseries.csv`
- `oty1t_tracker_events.csv`
- `oty1t_unmatched_detection_audit.csv`
- `oty1t_tracker_failure_buckets.csv`
- `oty1t_tracker_sensitivity_summary.json`
- `oty1t_tracker_sensitivity_summary.csv`

Committed small summary:

```text
reports/oty2/samples/oty2_normalized_input_tracker_sensitivity_summary_20260705_093617.csv
```

## Tracker Summary

| Scene | Variant | Input rows | Suppressed rows | Tracked rows | Unmatched rows | Unmatched rate | Duplicate-overlap unmatched | Tracks | Short tracks | Fragmented tracks | Duplicate-overlap hypotheses | Duplicate-track overlap events | Possible ID switch events | Lost | Reactivated |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | raw | 422 | 0 | 331 | 91 | 0.215640 | 14 | 28 | 2 | 5 | 5 | 4 | 5 | 39 | 11 |
| `GM_RM011` | normalized active | 413 | 9 | 327 | 86 | 0.208232 | 8 | 25 | 2 | 8 | 0 | 0 | 4 | 38 | 13 |
| `GM_RM019` | raw | 334 | 0 | 207 | 127 | 0.380240 | 34 | 21 | 9 | 1 | 8 | 8 | 6 | 29 | 8 |
| `GM_RM019` | normalized active | 330 | 4 | 206 | 124 | 0.375758 | 32 | 21 | 10 | 1 | 7 | 7 | 6 | 29 | 8 |
| `GM_RM017` | raw | 215 | 0 | 196 | 19 | 0.088372 | 6 | 6 | 0 | 0 | 0 | 0 | 1 | 8 | 2 |
| `GM_RM017` | normalized active | 215 | 0 | 196 | 19 | 0.088372 | 6 | 6 | 0 | 0 | 0 | 0 | 1 | 8 | 2 |

## Delta Summary

| Scene | Suppressed rows | Unmatched delta | Duplicate-overlap unmatched delta | Duplicate-overlap hypothesis delta | Duplicate-track overlap delta | Short-track delta | Fragmented-track delta | Lost delta | Reactivated delta | Diagnosis |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `GM_RM011` | 9 | -5 | -6 | -5 | -4 | 0 | +3 | -1 | +2 | Partial conflict reduction, but continuity risk remains |
| `GM_RM019` | 4 | -3 | -2 | -1 | -1 | +1 | 0 | 0 | 0 | Marginal conflict reduction, short-track risk remains |
| `GM_RM017` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Stable control, no rows suppressed |

Negative deltas mean the normalized active-only input reduced that diagnostic count. Positive deltas mean it increased that diagnostic count.

## Required Answers

1. Normalized active-only input reduces unmatched detections only modestly. `GM_RM011` drops from `91` to `86`, `GM_RM019` from `127` to `124`, and `GM_RM017` is unchanged at `19`.

2. Normalized active-only input reduces duplicate-overlap events in the scenes where it suppresses rows. `GM_RM011` improves clearly: duplicate-overlap hypotheses drop from `5` to `0`, duplicate-track overlap events from `4` to `0`, and duplicate-overlap unmatched detections from `14` to `8`. `GM_RM019` improves slightly: `8` to `7` duplicate-overlap hypotheses/events and `34` to `32` duplicate-overlap unmatched detections. `GM_RM017` is unchanged.

3. It does not reduce short tracks. `GM_RM011` remains `2`, `GM_RM019` worsens from `9` to `10`, and `GM_RM017` remains `0`.

4. It does not clearly reduce lost/reactivated behavior. `GM_RM011` lost events drop slightly from `39` to `38`, but reactivated events increase from `11` to `13`. `GM_RM019` and `GM_RM017` are unchanged.

5. It introduces possible missed-tracking or continuity risk. `GM_RM011` tracked assignment rows decrease from `331` to `327`, fragmented hypotheses increase from `5` to `8`, and reactivated events increase. `GM_RM019` short hypotheses increase from `9` to `10`. These are not final proof of missed targets, but they block a direct mainline replacement claim.

6. `GM_RM011` improves on duplicate-overlap tracker diagnostics, but not on continuity. The improvement is real enough to keep normalization as a probe input, not strong enough to call the object stream recovered or clean.

7. `GM_RM019` improves only marginally. It remains a high-risk old scene with many unmatched detections and short tracks.

8. `GM_RM017` remains the simpler control scene. It had no suppressed rows in the YOLO11l normalization pass, so tracker diagnostics remain identical.

9. Normalization is worth carrying into the next OTY1/OTY1a fragment relation audit as observation context and a bounded sensitivity input. It should not replace raw observations or become the mainline tracker input yet.

10. Component-level grouping is still needed. The active-only duplicate-like suppression does not solve partial/full competition, neighbor/crowding conflict, short gaps, class instability context, or fragment relation recovery.

## Interpretation

Pretracking observation normalization partially improves tracker diagnostics by removing some same-frame duplicate-like observations before ByteTrack sees them. The effect is clearest for `GM_RM011`, where duplicate-overlap tracker signals disappear in the normalized active-only run.

The probe also shows why this cannot be treated as a standalone fix. Suppressing duplicate-like observations can reduce duplicate-overlap events while still increasing fragmentation or reactivation. That means the next mechanism must keep both raw observations and normalized active flags available to the fragment relation layer, instead of treating active-only rows as identity truth.

## Recommendation

Conclusion:

```text
NORMALIZED_INPUT_PARTIALLY_IMPROVES_TRACKER_DIAGNOSTICS
```

Next step:

```text
Use normalized observation context in the OTY1/OTY1a fragment relation audit, but keep raw OTY0 rows as evidence and do not replace the mainline tracker input yet.
```

The next bounded mechanism work should focus on component-level grouping and fragment relation context: duplicate-like suppression, partial/full relation evidence, short missing gaps, and multi-object competition must be represented separately before any automatic reconnection or object-hypothesis update.

## Explicit Non-Actions

- No SAR pairing was run.
- No support audit was run.
- No final annotation was generated.
- No revised GT was generated.
- No final box was generated.
- No selector/ranking output was generated.
- No weighted fusion was used.
- No threshold or tracker-parameter tuning was performed.
- No mainline detector or tracker configuration was replaced.
- No identity truth was claimed from tracker IDs.
- `GM_RM011` was not promoted into the clean `215` pool.
