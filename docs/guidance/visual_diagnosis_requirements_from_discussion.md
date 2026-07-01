# Visual Diagnosis Requirements From Discussion

These requirements come from research discussion and define what future visual diagnostics must support. They do not require expanding V0 scripts in this round.

## 1. Optical-to-SAR Transfer Panel

Must show:

- optical frame
- optical box
- visible/truncation status if available
- depth / robust range prior if available
- SAR frame
- azimuth ray
- filled range band
- uncertainty band
- factor prior box
- top1 / top5 / top20 boxes
- posthoc final debug box only if enabled and clearly marked `posthoc_only`

## 2. Candidate Generation Panel

Must show:

- `factor_inference`
- `factor_topk`
- `visible_support`
- `wedge`
- `ray`
- `signed`
- bidirectional review-only candidates
- candidate source-family legend
- rank labels
- whether candidates cluster around a wrong prior
- whether any candidate visually covers vehicle-like SAR structure

## 3. Factor Breakdown Panel

Must show:

- prior consistency
- top-k support
- wedge support
- ray support
- signed temporal support
- visible risk
- temporal consistency
- conflict / ambiguity
- missing fields explicitly as `missing`
- no synthetic fake score

The goal is to explain why a candidate may look like a vehicle, not to immediately produce a selector score.

## 4. Temporal Strip Panel

Must show:

- neighboring SAR frames
- same target if available
- candidate overlays across frames if available
- range offset curve across frames
- signed vote direction
- whether temporal evidence is continuous or isolated
- note if the panel is only a context shell and not true track-level temporal evidence

## 5. Range Prior Diagnosis Panel

Must show:

- optical robust distance regression output
- corresponding SAR range band
- final/debug position only if posthoc is enabled
- whether target lies inside the band
- difference between single-point prior and band/multi-hypothesis prior

This panel is required before any renewed confidence in single-point range prior.
