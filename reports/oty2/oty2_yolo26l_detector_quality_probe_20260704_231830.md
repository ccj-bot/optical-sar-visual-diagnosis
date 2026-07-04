# OTY2 YOLO26l Detector Quality Probe

Timestamp: `20260704_231830`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `684cbf9 Check YOLO26 weight download and schema smoke`

## Boundary

This is an OTY0-only detector quality probe comparing the existing YOLO11l baseline detections with new YOLO26l Detect outputs on `GM_RM011`, `GM_RM019`, and `GM_RM017`.

No mainline detector was replaced. No main `configs/oty_yolo_stream_config.yaml` or `manifests/oty0_yolo_manifest.csv` files were changed. No OTY0 runtime code, OTY1, OTY1a, OTY1t, P4G, tracker, SAR pairing, support audit, threshold tuning, final annotation, revised GT, final box, selector/ranking, weighted fusion, identity-truth claim, or GM_RM011 clean-215 promotion was performed.

## Inputs

Required boundary source read:

- `docs/OTY2_SESSION_START_HERE.md`
- `reports/oty2/oty2_yolo26_weight_download_and_schema_smoke_20260704_230517.md`

YOLO26l weight:

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo26l.pt
```

Probe-only config/manifest were created under ignored `outputs`:

```text
outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty_yolo26l_probe_config.yaml
outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo26l_probe_manifest.csv
```

Existing YOLO11l baseline OTY0 tables:

| Scene | Baseline table |
| --- | --- |
| `GM_RM011` | `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv` |
| `GM_RM019` | `outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv` |
| `GM_RM017` | `outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv` |

New YOLO26l OTY0-equivalent outputs, not committed:

| Scene | Probe table |
| --- | --- |
| `GM_RM011` | `outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm011\oty0_yolo_detection_table.csv` |
| `GM_RM019` | `outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm019\oty0_yolo_detection_table.csv` |
| `GM_RM017` | `outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm017\oty0_yolo_detection_table.csv` |

Committed summary CSV:

```text
reports\oty2\samples\oty2_yolo26l_detector_quality_probe_summary_20260704_231830.csv
```

## Metric Notes

The probe used the same OTY0 settings as baseline except for detector weight: `imgsz=960`, confidence floor `0.25`, and class filter `car`, `truck`, `bus`.

The summary CSV contains aggregate diagnostics only. It does not contain final annotations, revised GT, final boxes, identity labels, selector/ranking output, SAR evidence, or tracker output.

Same-frame labels are diagnostic proxies:

- candidate multi-box pairs: same-frame boxes with high overlap, close centers, class conflict under overlap, or partial/full-like size relation;
- high-overlap same-frame pairs: overlap proxy at least `0.75`;
- class-instability duplicate-like pairs: near-identical high-overlap boxes with different classes;
- partial/full competition pairs: one-small-one-large same-frame pairs with overlap support;
- likely neighbor/crowding pairs: likely neighbor competition plus multi-vehicle crowding unresolved.

These labels are not identity truth and do not authorize automatic grouping.

## Cross-Scene Summary

| Scene | Model | Rows | Frames with detections | Empty frames | Candidate multi-box | High-overlap pairs | Class-conflict duplicate-like | Partial/full pairs | Crowded ratio | Boundary-touch ratio | Low-conf ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GM_RM011` | YOLO11l | 422 | 233 | 135 | 66 | 54 | 9 | 25 | 0.399 | 0.905 | 0.156 |
| `GM_RM011` | YOLO26l | 413 | 243 | 125 | 76 | 61 | 18 | 20 | 0.361 | 0.985 | 0.099 |
| `GM_RM019` | YOLO11l | 334 | 193 | 175 | 77 | 29 | 1 | 7 | 0.272 | 0.488 | 0.284 |
| `GM_RM019` | YOLO26l | 288 | 193 | 175 | 52 | 28 | 1 | 6 | 0.196 | 0.573 | 0.167 |
| `GM_RM017` | YOLO11l | 215 | 100 | 268 | 14 | 9 | 3 | 9 | 0.188 | 0.437 | 0.042 |
| `GM_RM017` | YOLO26l | 215 | 104 | 264 | 16 | 11 | 0 | 10 | 0.168 | 0.465 | 0.056 |

## Scene Findings

### GM_RM011

YOLO26l does not solve the main pressure-case conflict.

Positive changes:

- frames with detections increased from `233` to `243`;
- empty frames decreased from `135` to `125`;
- total rows decreased slightly from `422` to `413`;
- low-confidence ratio decreased from `0.156` to `0.099`;
- partial/full proxy pairs decreased from `25` to `20`;
- crowded-frame ratio decreased from `0.399` to `0.361`.

Negative changes:

- candidate multi-box pairs increased from `66` to `76`;
- high-overlap same-frame pairs increased from `54` to `61`;
- class-instability duplicate-like pairs doubled from `9` to `18`;
- boundary-touch ratio increased from `0.905` to `0.985`.

Interpretation: YOLO26l finds slightly more frames and fewer low-confidence boxes, but it increases same-frame high-overlap/class-conflict instability. GM_RM011 still requires OTY0-post pre-tracking observation grouping and state tagging before tracker-side claims.

### GM_RM019

YOLO26l gives the clearest improvement on the older risk scene.

Positive changes:

- detection rows decreased from `334` to `288` without losing frames with detections (`193` unchanged);
- candidate multi-box pairs decreased from `77` to `52`;
- crowded-frame ratio decreased from `0.272` to `0.196`;
- likely neighbor/crowding pairs decreased from `49` to `30`;
- low-confidence ratio decreased from `0.284` to `0.167`;
- median confidence increased from `0.543` to `0.805`.

Remaining issues:

- high-overlap pairs are nearly unchanged (`29` to `28`);
- class-instability duplicate-like pairs remain `1`;
- boundary-touch ratio increased from `0.488` to `0.573`.

Interpretation: YOLO26l improves observation cleanliness for GM_RM019, especially crowded-frame and low-confidence burden, but it does not eliminate high-overlap or boundary-touch risk.

### GM_RM017

GM_RM017 remains the simpler comparator.

Changes:

- total rows unchanged at `215`;
- frames with detections increased from `100` to `104`;
- crowded-frame ratio decreased from `0.188` to `0.168`;
- class-instability duplicate-like pairs decreased from `3` to `0`;
- median confidence increased from `0.915` to `0.935`.

Remaining or worsened signals:

- candidate multi-box pairs increased from `14` to `16`;
- high-overlap pairs increased from `9` to `11`;
- partial/full proxy pairs increased from `9` to `10`;
- boundary-touch ratio increased from `0.437` to `0.465`;
- low-confidence ratio increased slightly from `0.042` to `0.056`.

Interpretation: GM_RM017 is still easier, but it is not conflict-free. YOLO26l removes the observed class-instability duplicate-like proxy in this scene, while leaving mild multi-box and partial/full risks.

## Required Answers

1. Does YOLO26l reduce same-frame multi-box conflict?

Partially. It reduces candidate multi-box pairs in GM_RM019 (`77` to `52`) but increases them in GM_RM011 (`66` to `76`) and GM_RM017 (`14` to `16`).

2. Does YOLO26l reduce high-overlap class-conflict boxes?

Not globally. It removes the GM_RM017 class-instability proxy (`3` to `0`) and leaves GM_RM019 unchanged (`1`), but worsens GM_RM011 (`9` to `18`).

3. Does YOLO26l reduce partial/full competition?

Partially. It reduces GM_RM011 (`25` to `20`) and GM_RM019 (`7` to `6`), but slightly increases GM_RM017 (`9` to `10`).

4. Does YOLO26l improve crowded-frame conflict?

Yes by crowded-frame ratio in all three scenes: GM_RM011 `0.399` to `0.361`, GM_RM019 `0.272` to `0.196`, and GM_RM017 `0.188` to `0.168`. The improvement is strongest in GM_RM019.

5. Does YOLO26l introduce more missed detections or low-confidence boxes?

It does not show a clear missing-frame penalty in this probe. Frames with detections are unchanged in GM_RM019 and increase in GM_RM011/GM_RM017. Low-confidence ratio improves in GM_RM011 and GM_RM019, but worsens slightly in GM_RM017.

6. Does GM_RM011 improve?

Only partially and not on the key conflict metrics. It improves frame coverage, low-confidence ratio, partial/full count, and crowded ratio, but worsens candidate multi-box, high-overlap, class-instability duplicate-like, and boundary-touch ratios.

7. Does GM_RM019 improve?

Yes, GM_RM019 is the strongest improvement case. YOLO26l reduces total rows, candidate multi-box pairs, crowded-frame ratio, likely neighbor/crowding pairs, and low-confidence burden while preserving frames with detections.

8. Is GM_RM017 still simpler?

Yes. It has the fewest candidate multi-box pairs and lowest crowded-frame ratio under both detectors. It still shows mild multi-box/partial-full risk, so it is a simpler comparator rather than proof of clean mechanism success.

9. Is a tracker-side probe worth doing?

Yes, as a bounded downstream diagnostic only. YOLO26l changes pre-tracking observations enough to justify a tracker-side sensitivity probe later, especially on GM_RM019 and GM_RM011. That probe must not be treated as tracker replacement, identity truth, SAR pairing, or support audit.

10. Is OTY0-post pre-tracking observation grouping still needed?

Yes. YOLO26l does not remove the core issue. GM_RM011 still has more candidate multi-box pairs, more high-overlap pairs, and more class-instability duplicate-like pairs under YOLO26l. A pre-tracking observation grouping/context layer remains necessary to label duplicate overlap, class instability, partial/full competition, boundary contact, and crowding before association.

## Conclusion

```text
YOLO26L_PARTIALLY_REDUCES_PRETRACKING_CONFLICT
```

YOLO26l is useful as a detector-swap probe and improves some observation-quality dimensions, especially GM_RM019 crowded/low-confidence burden. It is not a general solution for pre-tracking conflict. The GM_RM011 pressure case remains unresolved and in several conflict dimensions becomes worse.

Recommended next step: if authorized, run a bounded tracker-side sensitivity probe using YOLO26l OTY0 outputs as diagnostic input only. Continue to prioritize OTY0-post observation grouping and optical state tags before any mechanism claim.

## No-Overstep Check

This pass did not:

- replace `yolo11l.pt`;
- edit main `configs/oty_yolo_stream_config.yaml`;
- edit main `manifests/oty0_yolo_manifest.csv`;
- edit OTY0, OTY1, OTY1a, OTY1t, P4, or P4G runtime;
- run tracker;
- enter SAR pairing;
- enter support audit;
- create final annotation;
- create revised GT;
- create final box;
- create selector/ranking output;
- use weighted fusion;
- tune thresholds;
- commit `.pt` weights;
- commit `outputs` runtime artifacts.
