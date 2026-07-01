# OTY1a Cross-Scene Fragment Merge Summary

Generated: `2026-07-01T19:05:59`

## Boundary

- Runtime construction uses OTY1 optical outputs only.
- No review/final/SAR GT/evidence/selector/G2/A008/threshold/training source is used.
- These are fragment merge review candidates, not confirmed identities and not annotation proposals.

## Totals

- scenes: `2`
- merge candidate edge rows: `357`
- review candidates including ambiguous: `101`
- nonambiguous merge review candidates: `52`
- ambiguous competing merge candidates: `49`
- confirmed identity merges: `0`
- rejected merge edges: `256`
- needs visual review edges: `0`
- shape transition review edges: `39`
- partial-to-full box transition edges: `11`
- shape transition audit rows: `324`

## Scene Rows

| scene | output_dir | merge edge rows | review candidates incl. ambiguous | nonambiguous review candidates | ambiguous competing candidates | 0039/0045 status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `GM_RM017` | `outputs\oty1a_fragment_merge_audit_20260701_190431` | 25 | 7 | 7 | 0 | `not_found` |
| `GM_RM019` | `outputs\oty1a_fragment_merge_audit_20260701_190559` | 332 | 94 | 45 | 49 | `partial_to_full_box_transition_candidate` |

## Recommendation

OTY1a candidates are review candidates, not identity truth. Nonambiguous candidates may proceed to visual review or OTY2 alignment preparation. Ambiguous candidates must not be treated as merged tracks. OTY2 may start only as a high-FPS optical-to-SAR temporal alignment audit, not SAR band generation.
