# Root-Cause Hypothesis Tree

## H1: Optical Azimuth Transfer Reliability

- current evidence: Shared fan mapping exists, but visual confirmation across GM_RM011/017/019 is incomplete.
- visual panel can verify: transfer panel with optical box, azimuth ray, and SAR frame.
- would falsify: ray consistently crosses plausible SAR target body across reviewed cases.
- if true: audit azimuth mapping, optical box-to-theta conversion, and scene binding.
- if false: move focus to range prior and SAR candidate generation.

## H2: Range Prior / Robust Distance Regression Is Not Suitable As A Single Point

- current evidence: Candidate pool ceiling and range-shift issues suggest single-point range may be brittle.
- visual panel can verify: range band in transfer panel and range offset curve in temporal strip.
- would falsify: target consistently lies inside reasonable range bands while candidates still fail for other reasons.
- if true: represent range as band/distribution/release direction before any selector work.
- if false: inspect local SAR structure and candidate source families.

## H3: Candidate Generation Is Centered Around Wrong Prior

- current evidence: top1 is weak and top20 approaches pool ceiling; good candidates may exist but are not dense.
- visual panel can verify: candidate overlay by source family around factor prior and range band.
- would falsify: candidate families cluster on the visual vehicle but ranking/posthoc still fails.
- if true: fix input source alignment and candidate construction before scoring.
- if false: focus on factor evidence and visual selector later, after review.

## H4: Wedge/Ray/Signed May Or May Not Provide Real SAR Structure Evidence

- current evidence: structural candidates exist, but no runtime factor layer has proven reliability.
- visual panel can verify: source-family overlays and factor breakdown with missing fields shown.
- would falsify: wedge/ray/signed candidates repeatedly miss vehicle-like SAR structure.
- if true: design a runtime factor layer only after visual review confirms support.
- if false: keep these as audit-only and avoid structural selector claims.

## H5: Temporal Evidence Does Not Close The Loop

- current evidence: C1.3/C1.4 only reached partial short-window or partial tracklet evidence; no identity-supported rows.
- visual panel can verify: temporal strip with neighboring SAR frames and range offset curve.
- would falsify: explicit same-target track IDs produce stable, visually correct range release.
- if true: build identity-aware temporal audit before scoring.
- if false: keep temporal evidence as stabilizer, not a main driver.

## H6: GM_RM011 Has Scene-Specific Geometry / OBB Convention Risk

- current evidence: GM_RM011 has not reproduced the GM_RM019 candidate input chain, and legacy notes warn mixed OBB convention behavior.
- visual panel can verify: GM_RM011 probe transfer panels and source alignment reports.
- would falsify: GM_RM011 panels match GM_RM019 behavior under the same config and accounting fields.
- if true: create scene-specific geometry/box convention audit.
- if false: reuse shared guidance while still avoiding unsupported generalization.

## H7: SAR-Only Targets Need An Independent Branch

- current evidence: SAR-only targets lack runtime priors and cannot be backfilled from final boxes.
- visual panel can verify: SAR-only blocked cases with missing optical/range prior evidence.
- would falsify: runtime SAR-only prior can be derived without final/oracle/GT leakage.
- if true: design a SAR-only diagnostic branch with separate inputs.
- if false: keep SAR-only cases marked blocked/missing.

## H8: Selector Is A Downstream Issue, Not The Current Main Cause

- current evidence: full pool ceiling is limited and structural/temporal evidence is incomplete.
- visual panel can verify: top1/top20/full-pool visual comparison and case review sheet.
- would falsify: high-quality candidate pool exists consistently, and visual errors are purely ranking order.
- if true: keep selector/threshold/G2/A008 prohibited until upstream diagnosis matures.
- if false: propose selector work only after human review and explicit scope approval.
