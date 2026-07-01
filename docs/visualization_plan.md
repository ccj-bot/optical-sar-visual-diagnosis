# Visualization Plan

## V0 Panels

1. Transfer panel
   - left: optical frame and optional optical box
   - right: SAR frame, azimuth ray, range prior band, factor prior box
   - final boxes only as `posthoc_only` debug overlays

2. Candidate overlay
   - overlay SAR candidates by source family
   - show `candidate_id`, source, rank, and IoU only when posthoc debug is enabled

3. Factor breakdown
   - prior consistency
   - top-k support
   - wedge support
   - ray support
   - signed temporal support
   - visible risk
   - conflict score
   - rank
   - unavailable values remain `missing`

4. Temporal strip
   - neighboring SAR frames
   - factor prior
   - top-k candidate
   - wedge/ray/signed candidate
   - optional posthoc-only final debug box
   - range offset curve

## First Diagnostic Questions

- Is the optical azimuth fan band visually correct?
- Is the range prior systematically biased?
- Does the SAR target fall inside the range band?
- Are candidates generated around the wrong prior?
- Do wedge/ray/signed candidates actually align with vehicle structure?
- Does temporal context support range release?
- Do GM_RM011 and GM_RM019 show different visual or geometric failure modes?
