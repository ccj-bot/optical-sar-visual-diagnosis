# Problem Statement

The current failure is not just a selector problem.

Legacy diagnostics indicate that candidate-pool quality and visual alignment are still insufficient:

- full candidate pool best AABB IoU median is about `0.650594`
- full candidate pool best AABB IoU max is about `0.872249`
- top1 median AABB IoU is about `0.465558`
- top20 median best AABB IoU is about `0.645357`

This means a better ranker alone cannot solve the root cause. The visual diagnosis must determine whether failures arise from optical azimuth, range prior expression, SAR local structure, source-family candidate generation, temporal ambiguity, or scene-specific geometry.

V0 therefore prioritizes visual panels and missing-field reporting before any scoring or selection design.
