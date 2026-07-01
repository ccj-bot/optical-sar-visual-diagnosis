# OTY1a Cross-Scene Fragment Merge Summary

Generated: `2026-07-01T18:50:19`

## Boundary

- Runtime construction uses OTY1 optical outputs only.
- No review/final/SAR GT/evidence/selector/G2/A008/threshold/training source is used.
- These are fragment merge review candidates, not confirmed identities and not annotation proposals.

## Totals

- scenes: `2`
- merge candidate edge rows: `357`
- positive fragment merge review candidates: `101`
- ambiguous merge candidates: `49`
- shape transition audit rows: `324`

## Scene Rows

| scene | output_dir | positive merge candidates | ambiguous merge candidates | 0039/0045 status |
| --- | --- | ---: | ---: | --- |
| `GM_RM017` | `outputs\oty1a_fragment_merge_audit_20260701_184935` | 7 | 0 | `not_found` |
| `GM_RM019` | `outputs\oty1a_fragment_merge_audit_20260701_185019` | 94 | 49 | `partial_to_full_box_transition_candidate` |

## Recommendation

GM_RM019 0039/0045 should be reviewed as an optical geometry fragment-merge candidate, not promoted to identity truth. If the visual/metric presentation is acceptable, the next mainline step is OTY2 high-FPS optical-to-SAR temporal alignment. If the review burden is too high, add OTY1b visualization/metric cleanup first.
