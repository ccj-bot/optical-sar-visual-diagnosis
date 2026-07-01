# Range Prior Rethink Notes

Current suspicion: single-point robust distance regression may be unsuitable as the only range prior.

Range prior should move from a point estimate toward uncertainty-aware representation. Candidate representations:

- band
- interval
- distribution
- multi-hypothesis
- ordinal near/mid/far
- visibility-conditioned prior
- temporal-smoothed prior

## V0 Requirement

V0 should first visualize the localization region implied by robust regression. It should not treat a scalar distance estimate as already validated.

Future diagnosis should compare:

- whether the target lies inside single-point `± sigma`
- whether the target lies inside a broader band
- whether candidate generation is biased by a narrow prior
- whether truncation/occlusion samples require wider priors
- whether GM_RM019 and GM_RM011 have different range-prior error patterns

## Boundary

Do not tune candidates from posthoc location. Do not convert this rethink into threshold tuning. The purpose is to inspect representation, not to create a new selector rule.
