# OTY1t Tracker Diagnosis Report

Generated: `2026-07-01T20:59:30`
Scene: `GM_RM019`
Tracker: `bytetrack`

## Boundary

- Runtime tracking source: OTY0 YOLO detection table and optical frame inventory only.
- OTY1/OTY1a are comparison context only.
- No SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector, training, or annotation proposal was introduced.
- Tracker ids remain optical identity hypotheses, not confirmed identities.

## Scene Diagnosis

- detection rows in: `334`
- tracked assignment rows: `207`
- unmatched detection rows: `127`
- tracker track count: `21`
- stable hypotheses: `3`
- fragmented hypotheses: `1`
- ambiguous hypotheses: `0`
- short hypotheses: `9`

## Unmatched Detection Distribution

| diagnosis_bucket | row_count | interpretation | recommended_next_action |
| --- | ---: | --- | --- |
| `boundary_or_truncated_unmatched` | 9 | Boundary contact or truncation proxy likely weakens tracker continuity. | Keep truncation/contact state in OTY2 as uncertainty, not confirmed identity. |
| `duplicate_or_overlap_rejected` | 34 | Tracker kept a competing nearby hypothesis and rejected this duplicate/overlap detection. | Use duplicate/overlap rows as review flags; do not merge automatically. |
| `late_fragment_unmatched` | 8 | Short or late optical fragments were not absorbed by an active tracker hypothesis. | Review fragment starts/ends and compare tracker variants. |
| `neighbor_ambiguous_unmatched` | 2 | Nearby same-frame vehicles create association ambiguity. | Compare BoT-SORT and preserve multiple hypotheses for OTY2. |
| `shape_transition_unmatched` | 72 | Partial/full or shape transition review context explains the unmatched row. | Carry OTY1a shape-transition candidates as optional visual-review hints. |
| `tracker_threshold_or_association_miss` | 2 | Detection is plausible, but tracker association failed under current runtime settings. | Compare tracker variants and inspect association parameters without GT tuning. |

## Duplicate / Possible ID Switch Distribution

- duplicate_track_overlap: `8`
- possible_id_switch: `6`
- fragment_bridge: `6`
- ambiguous_association: `16`

## 0039/0045 Failure Trace Summary

- tracker_connected: `false`
- confirmed_identity: `false`
- oty2_continuity_hint: `false`
- visual_review_required: `true`
- failure_mode: `partial_component_unmatched_then_later_full_component_tracked`
- 0039 unmatched detection count: `8`
- 0045 tracker ids: `['bt_0098']`

## OTY2 Input Recommendation

- oty2_stable_input_recommendation: `optional_continuity_hint_only`

ByteTrack should remain an audit baseline and optional continuity source, not a stable identity stream for OTY2.

## Tracker Variant Recommendation

Compare BoT-SORT against ByteTrack on unmatched rate, duplicate overlaps, possible ID switches, and 0039/0045 continuity. OC-SORT and StrongSORT must remain blocker-only until real adapters are integrated.

## Cross-Tracker Snapshot

| tracker | real_run | unmatched_rate | recommendation | blocker |
| --- | --- | ---: | --- | --- |
| `botsort` | `true` | 0.33532934131736525 | `optional_continuity_hint_only` | No hard OTY1t blocker; tracker ids remain optical hypotheses only. |
| `bytetrack` | `true` | 0.38023952095808383 | `optional_continuity_hint_only` | No hard OTY1t blocker; tracker ids remain optical hypotheses only. |
| `ocsort` | `false` | 1.0 | `not_recommended` | ocsort dependency unavailable or unsupported for real detection-table replay: ocsort is not installed or no stable detection-table replay adapter is integrated in OTY1t-P1/P2.; install hint: Integrate a runtime-safe detection-table replay adapter and install the tracker package before enabling real runs. |
| `strongsort` | `false` | 1.0 | `not_recommended` | strongsort dependency unavailable or unsupported for real detection-table replay: strongsort is not installed or no stable detection-table replay adapter is integrated in OTY1t-P1/P2.; install hint: Integrate a runtime-safe detection-table replay adapter and install the tracker package before enabling real runs. |
