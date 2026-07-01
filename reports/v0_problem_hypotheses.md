# V0 Problem Hypotheses

This document is a starting list for visualization-first diagnosis. It is not a selector design.

## H1: Optical Prior Shell Is Misplaced Or Too Weak

The azimuth ray, range prior band, and factor prior box disagree visually before SAR evidence is considered.

Needed evidence: transfer panels with optical box, azimuth ray, range band, and factor prior box.

## H2: Candidate Pool Contains The Right Family But Poor Local Geometry

Wedge, ray, signed, visible-support, or factor-topk candidates exist but cluster away from the plausible SAR body.

Needed evidence: source-family overlays and candidate geometry review.

## H3: Evidence Factors Are Missing Rather Than Negative

Some apparent failures may be missing descriptor or temporal support fields, not evidence against the candidate.

Needed evidence: factor breakdown rows where unavailable factors are explicitly marked `missing`.

## H4: Temporal Context Is Ambiguous

Neighboring frames support motion continuity only partially, or target identity is blocked by same-frame ambiguity.

Needed evidence: temporal strips and C1.3/C1.4 accounting fields, kept audit-only.

## H5: Posthoc Debug Layers Are Being Mistaken For Runtime Inputs

Final debug boxes or posthoc IoU values may explain a case visually, but must not change candidate construction.

Needed evidence: posthoc-only styling and a scope check in every report.
