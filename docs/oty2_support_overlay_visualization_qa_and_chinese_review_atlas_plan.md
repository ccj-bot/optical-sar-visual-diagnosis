# OTY2 Support Overlay Visualization QA And Chinese Review Atlas Plan

Updated: 20260703

This plan fixes and audits the OTY2 support overlay review atlas. It is visualization coordinate QA only. It does not generate annotation proposals, final candidate boxes, selector/ranking outputs, training data, threshold tuning, best weights, or identity truth.

## Problem

The previous support overlay atlas rendered static PNGs, but its panel generator cropped the SAR image and then resized the crop before drawing GT/support/energy overlays. The overlay coordinates were shifted into crop-local coordinates, but they were not scaled after image resize. Therefore panels with crop width greater than the display cap could show GT, support, or energy atoms in the wrong visual location.

Because of this, the previous atlas should not be used for support coverage visual judgment until coordinate QA is attached. Manual text observations about SAR morphology can be retained as review notes, but visual support coverage conclusions from the un-QA atlas must be paused.

## Fix

- Render each new PNG as a fully composed diagnostic panel.
- Use matplotlib axes with image origin at the upper-left and data extent equal to crop-local pixel coordinates.
- Convert every GT/support coordinate from full-image to crop-local before drawing.
- Do not use browser-side overlay layers.
- Embed only finished PNG panels in the HTML atlas.
- Record full-image, crop-local, and render coordinates in CSV for every panel.
- Mark SAR-only and GM_RM011 panels as reference-only for support coverage.

## Coordinate Contract

- Original coordinates: SAR full-image pixels, x rightward and y downward.
- Crop-local coordinates: original coordinate minus `(crop_x0, crop_y0)`.
- Render coordinates: identical to crop-local data coordinates in the new matplotlib axes.
- `scale_x = scale_y = 1.0` because the overlay and image share the same axes and data extent.
- Support boundary is reconstructed from sector/range fields when available. It is not an explicit support mask.

## Human Review Contract

Each Chinese card states:

- why the case was selected,
- what to inspect,
- what the reviewer should answer,
- what conclusions may be recorded,
- what conclusions must not be recorded,
- whether support coverage can be judged,
- whether GT morphology can be judged,
- whether adjacent frames are needed,
- the allowed manual tags.

The atlas is still posthoc mechanism evidence. It is not runtime optical prior construction and not final localization.
