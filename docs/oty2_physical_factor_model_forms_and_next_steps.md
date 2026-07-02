# OTY2 Physical Factor Model Forms And Next Steps

Updated: 20260702_224649

This document records the OTY2 physical feasible-domain + SAR observation confirmation model sketch. It is not OTY3, not an automatic annotation proposal, not selector/ranking, and not training or threshold tuning.

## Model Shift

Do not collapse all factors into a flat weighted score:

```text
E = w_time F_time + w_az F_az + w_shell F_shell + w_sar_image F_sar_image + ...
```

Use a two-stage form instead:

```text
C_o,t = C_time(o,t) intersect C_az(o,t) intersect C_shell(o,t) intersect C_state(o,t)

X*_o,1:T = argmax_{X_1:T in C_o,1:T} P(I_sar_1:T | X_1:T) P(X_1:T | O_1:T)
```

Equivalent energy form:

```text
X*_o,1:T = argmin_{X_1:T in C_o,1:T} E_sar_image(X_1:T) + E_sar_temporal(X_1:T) + E_optical_temporal(X_1:T, O_1:T)
```

The optical stream, timing, azimuth, vehicle shell, and state control the feasible domain. SAR image and SAR temporal evidence confirm the scattering structure inside that domain. SAR GT/manual/review fields validate and diagnose only.

## State-Conditioned Forms

```text
P(X | O,I) = sum_s P(s | O) P(X | O,I,s)

E(X,s) = E_state(s) + E(X | s)
```

- complete_visible: E_az + E_shell + E_range_shape + E_sar_image
- edge/truncated: E_az + E_shell_relaxed + E_sar_temporal; range_shape only modulates uncertainty
- far-small: E_time + E_az + E_sar_image
- dropout: E_time + E_optical_temporal + E_sar_temporal; excluded from clean paired morphology
- duplicate/handoff: review-needed object-hypothesis ambiguity; no identity truth

## Factor Roles

- Hard/semi-hard feasible-domain constraints: C_time, C_az, C_shell, C_state.
- Soft optical hypothesis: F_range_shape, only after state conditioning.
- SAR observation likelihood: F_sar_image and F_sar_temporal.
- Posthoc validation only: SAR GT, GT-crop SAR image statistics, manual/review anchors.
- Reference only: MATLAB/FMCW/SAR imaging toolbox concepts.

## Priority Answer

For the model itself, the first next step should be runtime support-region SAR peak/centroid extraction because it converts GT-crop SAR evidence into a usable SAR observation layer. GM_RM019 manual optical review is the next data-quality step for ambiguity; GM_RM011 object stream recovery is the next scale-expansion step.

## Generated Outputs

- next_steps_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_physical_factor_model_forms_and_next_steps.md`
- physical_model_form_comparison_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_comparison_20260702_224649.csv`
- feasible_domain_factor_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_feasible_domain_factor_audit_20260702_224649.csv`
- state_conditioned_model_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_state_conditioned_model_probe_20260702_224649.csv`
- dynamic_sar_observation_model_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_dynamic_sar_observation_model_probe_20260702_224649.csv`
- anchor_propagation_candidate_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_anchor_propagation_candidate_audit_20260702_224649.csv`
- physical_model_form_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_report_20260702_224649.md`
- physical_model_form_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_summary_20260702_224649.json`
