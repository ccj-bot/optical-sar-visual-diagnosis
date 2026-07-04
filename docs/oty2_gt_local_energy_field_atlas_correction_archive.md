# OTY2 GT-Local Energy-Field Atlas Correction Archive

Updated: 2026-07-04

This archive corrects the previous physical shell grammar atlas. The atlas generated as `reports/oty2/visual_exemplars/oty2_physical_shell_grammar_temporal_drift_atlas_cn_20260704_143456.html` must be treated as a failed visualization, not as successful evidence.

## Why The Previous Atlas Failed

The failed atlas reused support-wide panels. That means the visual frame still emphasized optical-derived support, support-internal peaks/components, and component boxes. This violated the intended correction:

- the primary coordinate frame was not the SAR GT crop;
- support-internal peaks/components outside GT could still look like vehicle parts;
- small component boxes could still look like shell boxes;
- the viewer could still read a baby-car explanation from component boxes rather than GT-scale energy structure.

The failed atlas remains a historical artifact only. It must not be cited as evidence for vehicle shell grammar.

## Corrected Visualization Contract

The corrected atlas uses the SAR GT crop as the primary coordinate frame. Every visual cue must be extracted and displayed inside the GT crop:

- ridge-like energy bands;
- endpoint hotspots;
- weak opposite-side returns;
- boundary occupancy;
- vehicle-scale energy-field shell contour.

The corrected atlas must not draw support boundaries, support-internal components outside GT, small component boxes, final boxes, revised GT boxes, selector outputs, or identity truth.

## Interpretation Boundary

The corrected visualization is still posthoc mechanism diagnosis. SAR GT anchors the local coordinate frame, and SAR image energy describes morphology. The result is not runtime prior construction, not automatic annotation, and not a final localization rule.

The corrected atlas may say:

- GT-local ridge-like band;
- endpoint hotspot candidate;
- weak opposite-side return candidate;
- boundary occupancy ratio;
- vehicle-scale shell contour candidate.

It must not say:

- revised annotation;
- final vehicle box;
- selected component;
- selector success;
- identity truth;
- support-internal component equals vehicle.

## Relation To Human Contour Markings

The rough human contour markings provided on 2026-07-04 are useful as qualitative visual vocabulary only. They motivate the GT-local extraction of long side ridges, endpoint hotspots, weak opposite-side returns, and continuous or discontinuous shell contour. They are not GT edits and are not committed as raw files.
