# OTY1t 0039/0045 Failure Trace

## Required Conclusion

- tracker_connected = `false`
- confirmed_identity = `false`
- oty2_continuity_hint = `false`
- visual_review_required = `true`
- failure_mode = `partial_component_unmatched_then_later_full_component_tracked`

## Why OTY1a Marked Partial-To-Full

OTY1a marks 0039/0045 as partial/full because endpoint overlap, bridge IoU, boundary/shape transition proxies, and temporal overlap support review without proving identity.

## Why ByteTrack Did Not Connect Them

ByteTrack did not assign any 0039 detections to the same tracker id as 0045; the tracked hypothesis starts later on the fuller box sequence.

## Detection And Tracker Facts

- OTY1a status: `partial_to_full_box_transition_candidate`
- 0039 entered OTY0 detection table: `true`
- 0039 unmatched detection count: `8`
- 0039 unmatched det ids: `['GM_RM019_000162_002', 'GM_RM019_000163_002', 'GM_RM019_000164_002', 'GM_RM019_000165_002', 'GM_RM019_000166_002', 'GM_RM019_000167_001', 'GM_RM019_000168_002', 'GM_RM019_000172_002']`
- 0045 tracker ids: `['bt_0098']`
- 0045 unmatched detection count: `2`
- `bt_0098` frame_start: `149`
- `bt_0098` frame_end: `182`
- `bt_0098` detection_count: `25`
- unmatched detections between 0039/0045 span: `22`
- unmatched det ids between span: `['GM_RM019_000162_002', 'GM_RM019_000163_001', 'GM_RM019_000163_002', 'GM_RM019_000164_001', 'GM_RM019_000164_002', 'GM_RM019_000164_003', 'GM_RM019_000165_001', 'GM_RM019_000165_002', 'GM_RM019_000166_001', 'GM_RM019_000166_002', 'GM_RM019_000166_003', 'GM_RM019_000167_001', 'GM_RM019_000167_002', 'GM_RM019_000167_003', 'GM_RM019_000168_002', 'GM_RM019_000170_001', 'GM_RM019_000171_001', 'GM_RM019_000172_002', 'GM_RM019_000173_002', 'GM_RM019_000174_002', 'GM_RM019_000181_002', 'GM_RM019_000183_001']`
- duplicate/competing event count: `0`
- related event types: `['track_end', 'track_lost', 'track_reactivated', 'track_start']`

## Boundary

This is a tracker failure diagnosis and OTY2 continuity-hint audit only. It is not confirmed identity, SAR alignment, SAR band generation, SAR GT coverage, SAR evidence sampling, selector output, training signal, or annotation proposal.
