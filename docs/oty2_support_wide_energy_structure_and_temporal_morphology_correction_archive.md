# OTY2 Support-Wide Energy Structure And Temporal Morphology Correction Archive

Updated: 20260703

This archive records the mechanism correction after the fixed support overlay QA atlas. It is still OTY2 posthoc mechanism diagnosis. It does not create annotation proposals, final candidate boxes, selector/ranking outputs, training data, tuned thresholds, best weights, or identity truth.

## Why The Previous Support Judgment Was Too Narrow

The previous visual question was too close to "is the GT-local or center-near peak bright?" That is not enough for SAR vehicle morphology. A SAR vehicle should not be reduced to an isolated top-k peak. A peak is only a scattering atom; the vehicle hypothesis must be read from support-wide structure:

1. top-k peak is not the vehicle; peak is only a scattering atom.
2. high-energy atoms, strips, blocks, and connected structures must be observed over the whole support region.
3. SAR vehicle structure is closer to shell / boundary / near-side strong scattering strip / endpoint corner / far-side weak return.
4. horizontal, vertical, and near-field vehicles may show different SAR morphology.
5. people, e-bikes, bicycles, and other small targets may appear point-like or small-block-like, but that remains a future morphology cue.
6. support is an optical-derived feasible region / reconstructed sector-range reference, not a final rule.
7. association means a constrained relation between an optical object hypothesis and SAR vehicle structure / temporal tube; it is not "does GT contain a vehicle?"
8. multi-vehicle arrangements can confuse the interpretation, but they can also provide relative position and temporal information.
9. temporal non-jump / gradual drift is a core mechanism.
10. strong GT morphology and unresolved optical-SAR association are two layers and must not be collapsed into one conclusion.

## Corrected Diagnostic Question

The corrected question is:

Can the energy atoms inside the whole reconstructed support organize into vehicle-like shell, strip, block, boundary, or temporal drift structure, and how does that posthoc structure relate to GT, neighboring structures, and the optical object hypothesis?

The corrected question is not:

Does the brightest GT-local or center-near peak prove the vehicle identity?

## Sample Pool Boundary

- 442 = all SAR GT / SAR-side morphology reference pool.
- 215 = current frame-level posthoc optical-SAR paired pool with available OTY optical object stream.
- 195 = GM_RM011 blocked by missing current OTY optical object stream; not unannotated.
- 20 = SAR-only GT; SAR morphology / observation reference only, not optical-SAR correspondence.
- 12 = dropout / no_oty_iou_match / temporal continuation pool; temporal existence support only, not clean paired morphology.

## Paused Or Corrected Old Conclusions

- Old support coverage judgments from the un-QA atlas remain paused.
- Top-k peak tables cannot be interpreted as vehicle structure by themselves.
- "Support covers GT" does not mean association succeeds.
- "Support misses GT-local energy" does not mean SAR morphology fails.
- Weak or discontinuous SAR structure cannot be rejected only because it is not a compact center peak.
- SAR-only and GM_RM011 panels remain reference-only for this branch.

## Allowed Use

- posthoc support-wide high-energy atom/component analysis
- GT-anchored morphology reference
- vehicle shell / boundary proxy
- support failure taxonomy
- temporal morphology drift probe
- Chinese multi-frame review atlas
- manual/review anchor provenance

## Forbidden Use

- annotation proposal
- final candidate box
- selected component
- selector/ranking
- training or threshold tuning
- best-weight selection
- identity truth
- GT-guided prediction logic
- support-wide shell proxy as an automatic annotation rule
- temporal tube as identity truth
- SAR-only or GM_RM011 rows mixed into paired correspondence
- dropout/no-match rows mixed into clean paired morphology
