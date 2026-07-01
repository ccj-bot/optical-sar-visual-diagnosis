# Project Principles

This repository is a visualization-first root-cause diagnosis repo.

The goal is not to recreate the legacy pipeline. The goal is to see where optical-to-SAR transfer fails: optical azimuth, range prior, candidate construction, SAR structure, temporal evidence, scene convention, or posthoc/runtime leakage.

## Principles

- Look at visual failures before changing candidate generation, factor layers, temporal logic, or selector design.
- Candidate input success does not imply selector success.
- Frozen rank success does not imply calibrated selector success.
- Posthoc accounting is not runtime evidence.
- `candidate_source_family` is provenance, not a selector rule.
- Final/oracle/GT/posthoc IoU fields may explain failures, but cannot generate or rank runtime candidates.
- Codex is a local implementation assistant. It can prepare artifacts, checks, and visualizations, but it does not own research conclusions.
- Research conclusions require visual review plus accounting evidence.
- Missing factors must remain `missing`; do not invent values to make a panel look complete.

## Current Research Position

The active question is still root-cause diagnosis. The current evidence says the problem is not only rank selection: high-quality candidate density is insufficient, range prior expression may be wrong, and GM_RM011 has not reproduced the GM_RM019 input chain.
