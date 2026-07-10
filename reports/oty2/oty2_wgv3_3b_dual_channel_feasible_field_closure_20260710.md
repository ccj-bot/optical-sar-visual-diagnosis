# OTY2 WGV3.3B Dual-Channel Feasible Field Closure

Date: 20260710

## Status

Conclusion: `CLOSED_BOUNDED_TIME_AZIMUTH_PROXY`

WGV3.3B closes for the first T001 non-GT response setup: time is recoverable as a bounded software-sync proxy, SAR PNG windows are traceable, and coarse azimuth is recoverable from WGV3.3A automatic bbox envelopes plus the configured legacy optical-x to SAR azimuth mapping. Range remains broad/unknown.

## Source Channels

- Posthoc channel: `WGV1.4/WGV1.8`, permission `posthoc_visual_constraint`, read only after automatic freeze.
- Automatic channel: `WGV3.3A automatic nodes/relations/competition`, permissions `automatic_runtime_hypothesis` and `automatic_uncertain_hypothesis`.

## T001 Feasible Fields

- Posthoc feasible field: SAR `0-36`, azimuth `-55.052..44.587`, range `broad_unknown_range_prior`.
- Automatic hypothesis count: `7`.
- Automatic fields: SAR union `0-119`, multi-azimuth proxy intervals preserved.
- Reference coverage: `covered_as_proxy`.
- Search reduction ratio: `0.088729` over time-azimuth cells; range remains full fan radius.
- Negative control: `NEG_T001_SHIFTED_AZIMUTH_CONTROL`, SAR `0-36`, azimuth `70..85`.

## Remaining Blockers

- No raw SAR pulse / MATLAB window / PRF-to-PNG provenance source was found under the GM_RM011 data tree.
- No per-frame optical or SAR timestamp is available; current time mapping is a bounded proxy.
- No runtime-safe per-object range transfer is available; the field is broad range within the fan.
- Automatic identity relations are intentionally uncertain; WGV3.3B does not force a single optical identity.

## Can WGV3.3C Proceed

Yes, but only as a first real non-GT SAR response experiment inside bounded time + coarse azimuth proxy fields. WGV3.3C must still let SAR evidence decide inside the field and must not treat this field as a final box or identity truth.

## Metrics

| metric_name | metric_value | metric_status | numerator | denominator | notes |
| --- | --- | --- | --- | --- | --- |
| time_source_coverage | 1 | proxy_available_not_direct_timestamp | 1 | 1 | 24/50 scale metadata plus software-sync zero-offset assumption and WGV1.7 offset stress band |
| sar_window_traceability | 1 | png_window_traceable_raw_pulse_mapping_missing | 1 | 1 | GM_RM011 SAR/SAR-gray PNG images 000000-000765 exist |
| azimuth_source_coverage | 1 | coarse_proxy_available | 1 | 1 | scene_config legacy azimuth_k/b + WGV3.3A automatic bbox envelope |
| range_source_coverage | 0 | broad_unknown_range_only | 0 | 1 | no runtime-safe per-object range/depth-to-SAR transfer or raw range-axis metadata |
| automatic_feasible_field_time_coverage | true | covered | 37 | 37 | auto union SAR 0-119; posthoc T001 SAR 0-36 |
| automatic_feasible_field_joint_time_azimuth_coverage | true | covered_as_proxy | 15731 | 15731 | coverage is evaluated over WGV1.4 fragment-level mapped-node time-azimuth proxy cells; range not evaluated |
| search_reduction_ratio_time_azimuth | 0.088729 | proxy_reduction_not_selector | 24264 | 273462 | automatic Channel B feasible field area over full SAR-frame by full-azimuth area; range full |
| time_only_search_reduction_ratio | 0.156658 | proxy_reduction_not_selector | 120 | 766 | union automatic SAR frame window divided by all SAR frames |
| automatic_hypothesis_count | 7 | multi_hypothesis_preserved | 7 |  | {"automatic_runtime_hypothesis": 1, "automatic_uncertain_hypothesis": 6} |
| negative_control_count | 1 | same_time_shifted_azimuth_control | 1 |  | 70..85 deg |

## Created Files

- `reports/oty2/oty2_wgv3_3b_source_provenance_audit_20260710.md`
- `reports/oty2/samples/oty2_wgv3_3b_source_provenance_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_optical_time_mapping_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_sar_window_mapping_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_dual_channel_feasible_fields_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_automatic_hypothesis_freeze_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_feasible_field_metrics_20260710.csv`
- `reports/oty2/oty2_wgv3_3b_visual_source_and_mapping_diagnosis_20260710.md`
- `reports/oty2/oty2_wgv3_3b_dual_channel_feasible_field_closure_20260710.md`

## Git Context At Generation

- branch: `feature/oty2-posthoc-mechanism-validation`
- start commit: `d53761f2b7cf2ed45d786d2ff32439e3014e4c20`
- generation HEAD: `d53761f2b7cf2ed45d786d2ff32439e3014e4c20`
