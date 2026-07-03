# OTY2 GT-Anchored SAR Vehicle Morphology And Support Coverage Plan

Updated: 20260703_163000

This plan redirects the mechanism line from generic compact/spread/diffuse descriptors toward GT-anchored SAR vehicle morphology and optical-support coverage hypotheses. It is not OTY3, not automatic annotation, not selector/ranking, not training, and not identity truth.

## Purpose

- Archive manual visual review as a durable mechanism source.
- Treat the 442 SAR GT rows as the SAR-side morphology reference pool while preserving 215 / 195 / 20 / 12 pool semantics.
- Audit 215 paired rows for optical-derived support coverage of GT area, GT energy, and high-energy morphology proxy.
- Render support overlays only from existing sector/range support fields; do not fabricate support boundaries.

## Coverage Semantics

- GT area coverage: fraction of GT polygon pixels inside reconstructed support.
- GT energy coverage: fraction of GT-box display-grayscale SAR energy inside reconstructed support.
- Morphology primitive coverage: fraction of high-energy GT pixels inside reconstructed support.
- The 80-85% hypothesis is a posthoc audit hypothesis and must be reported separately for the three coverage definitions.

## Inputs

- gt_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- support_peak_competition_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- visual_review_cards_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_visual_review_candidate_cards_20260703_151500.csv`
