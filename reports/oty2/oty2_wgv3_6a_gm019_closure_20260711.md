# OTY2 WGV3.6A GM_RM019 Closure

Closure status: `CLOSED_SPARSE_ANCHOR_RESPONSE_PROPAGATION_FEASIBLE`

## Anchor Audit

- total paired rows: `16`
- confirmed anchors: `10`
- weak anchors: `5`
- identity-conflict anchors: `0`
- response-ambiguous anchors: `0`
- pairing-review anchors: `1`
- confirmed physical vehicles: `2` (PV_GM19_SILVER_MPV_NEAR_FIELD;PV_GM19_WHITE_SUV_NEAR_FIELD)

## Propagation

|method|propagated_rows|target_frame_count|target_visible_response_coverage_median|target_visible_response_coverage_p90|confident_rows|review_required_rows|blocked_rows|
|---|---|---|---|---|---|---|---|
|P0|140|8|0.818472|0.944622|0|0|0|
|P1|140|8|1|1|140|0|0|
|P2|54|4|0.949027|0.987756|14|4|0|
|P3|54|4|0.949027|0.987756|14|4|0|

## Bidirectional Results

- bidirectionally closed: `4`
- bidirectional partial: `4`
- bidirectional conflicts: `0`
- visible response coverage: `0.952958`
- masked overlap coverage: `0.952958`
- identity contamination count: `0`
- response switch count: `0`
- review required count: `8`
- blocked count: `0`
- median local search ratio: `0.020971`
- p90 local search ratio: `0.023709`

## Boundary Checks

- No GT or manual annotations were modified.
- No final SAR boxes were emitted.
- No GM_RM011 experiment was executed.
- No full-SAR response search was performed; all SAR response correction stayed inside local windows around the current propagated region.
- No detector training, selector, ranking, or full MOT rerun was performed.
- `response_center_for_local_tracking` is never named as a complete vehicle center.
- Identity-conflict/pairing-review rows do not enter propagation.
- Diagnostic images are under ignored `outputs/wgv3_6a_gm019_20260711/`.

## Created Files

- `reports/oty2/oty2_wgv3_6a_sparse_anchor_design_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_gm019_anchor_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_gm019_propagation_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_gm019_bidirectional_closure_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_gm019_failure_cases_20260711.csv`
- `reports/oty2/oty2_wgv3_6a_gm019_visual_diagnosis_20260711.md`
- `reports/oty2/oty2_wgv3_6a_gm019_closure_20260711.md`