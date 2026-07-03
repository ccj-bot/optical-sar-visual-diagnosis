# OTY2 GT Support Failure Concept Correction Archive

Updated: 2026-07-03

This archive records the correction from support-internal SAR morphology search to GT-anchored vehicle-scale morphology and GT quality audit. It is still OTY2 posthoc mechanism diagnosis. It is not OTY3, not automatic annotation, not selector/ranking, not training or threshold tuning, and not identity truth.

## Core Correction

If the GT-anchored vehicle-scale SAR structure is outside the optical-derived support region, the correct diagnostic is support construction failure / support miss vehicle structure. It is not valid to keep searching only inside the wrong support and reinterpret a small local component as the vehicle.

The support region is an optical-derived feasible region. It is not a final rule, not a final SAR box, and not a permission to ignore the GT-anchored vehicle body structure.

## GT Quality Is A Separate Layer

SAR GT is the morphology anchor for this audit, but the GT box itself must be audited. Some GT boxes may be too small, too large, offset, boundary-affected, weak, or mixed with neighboring structures. If the GT box is abnormal, morphology and support coverage conclusions must be weakened or routed to manual review.

GT quality issue and support issue are distinct:

- GT quality issue: the SAR GT box may not be a reliable vehicle-scale morphology anchor.
- support issue: the optical-derived support may miss, shift away from, or over-broaden around the GT-anchored vehicle structure.

An abnormal GT sample cannot be used as strong morphology or support coverage evidence without review.

## Atom / Part / Shell Hierarchy

The audit must separate three levels:

- `scattering_atom`: a single bright point, small local peak, or tiny component. It cannot be called a vehicle.
- `vehicle_part`: a strip fragment, endpoint, corner reflector, edge fragment, or local body block. It can be part of a vehicle but is not the complete vehicle.
- `vehicle_scale_shell_hypothesis`: multiple parts arranged at GT vehicle scale, forming a body shell, boundary, long-axis/short-axis relation, strip-plus-corner pattern, or block-with-edge structure. It is still a hypothesis and not a final box.

Small components must not be named as cars or vehicle shells. Vehicle-scale claims require GT-scale consistency plus part composition.

## Boundary

Allowed in this stage:

- 442 SAR GT quality audit.
- GT-anchored morphology reference.
- GT scale statistics.
- atom / part / shell hierarchy.
- support miss diagnostics on the 215 paired pool.
- visual review candidate list.
- SAR-only and GM_RM011 morphology reference-only rows.

Forbidden:

- annotation proposal.
- revised GT box.
- final candidate box.
- selector/ranking.
- training or threshold tuning.
- identity truth.
- GT-guided runtime prediction logic.
- writing GT quality or SAR image discoveries into runtime priors.
- mixing SAR-only or GM_RM011 rows into paired optical-SAR correspondence.
- mixing dropout/no-match rows into clean paired morphology.

## Ledger Boundary

```text
442 = all SAR GT / SAR-side target reference pool
215 = current OTY optical-object to SAR-GT frame-level paired pool
195 = GM_RM011 blocked_missing_object_stream; not unannotated
20 = SAR-only GT; SAR morphology reference only
12 = dropout/no_oty_iou_match/temporal continuation special pool
```

## What This Corrects

Previous support-wide morphology work correctly rejected single peak reasoning, but it could still over-focus on energy inside the support. This archive adds the missing rule:

If GT vehicle-scale morphology is outside support, do not explain the support-internal small component as the car. Mark the support as missing the vehicle-scale structure, separate any GT quality concern, and hand the case to support construction / motion-drift compatibility review.
