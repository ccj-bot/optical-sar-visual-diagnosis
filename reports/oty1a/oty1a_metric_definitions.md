# OTY1a Metric Definitions

OTY1a is an optical runtime-geometry fragment merge audit. It consumes OTY1
optical tracklet outputs and emits review candidates. It does not confirm
identity, generate annotation proposals, sample SAR evidence, evaluate SAR GT,
or create SAR fan/range bands.

## Status Definitions

`fragment_merge_candidate`
: A nonambiguous optical-geometry review candidate between two OTY1 fragments.

`overlap_shape_transition_candidate`
: A nonambiguous review candidate where fragments overlap or interleave in
optical time and the endpoint shape changes enough to need review.

`partial_to_full_box_transition_candidate`
: A nonambiguous review candidate where boundary contact plus bbox shape change
suggests a partial/full detection transition. This is still not identity truth.

`needs_visual_review`
: A nonambiguous low-strength review candidate that is not clean enough to treat
as a geometry-consistent merge.

`ambiguous_competing_merge`
: A review candidate with competing from/to merge options. It must not be
treated as a merged track.

`reject_gap_too_large`, `reject_motion_inconsistent`,
`reject_size_aspect_inconsistent`, `reject_class_mismatch`
: Reject rows retained for audit context inside the bounded OTY1a scan.

## Edge Count Definitions

`review_candidate_edges_including_ambiguous`
: All review candidates, including `ambiguous_competing_merge`.

`nonambiguous_merge_review_candidates`
: Review candidates excluding `ambiguous_competing_merge`.

`ambiguous_competing_merge_candidates`
: Only `ambiguous_competing_merge` rows.

`confirmed_identity_merges`
: Always `0` in OTY1a.

`rejected_merge_edges`
: Rows with reject statuses.

`needs_visual_review_edges`
: Rows with `needs_visual_review`.

`shape_transition_review_edges`
: Rows with `overlap_shape_transition_candidate`.

`partial_to_full_box_transition_edges`
: Rows with `partial_to_full_box_transition_candidate`.

## Temporal Relation Definitions

`temporal_relation`
: `forward_gap` means the second fragment starts after the first fragment ends.
`overlap_or_interleave` means their optical frame spans overlap or interleave.

`temporal_offset_frames`
: `to_frame_start - from_frame_end`.

`forward_gap_frames`
: Positive forward gap for `forward_gap`; `0` for overlap/interleave.

`overlap_or_interleave_offset_frames`
: Populated only for overlap/interleave. A negative value does not mean a
reverse-time error. It means the second fragment starts before the first
fragment ends, usually because YOLO produced competing bbox shapes around the
same target or nearby targets.

## Why Ambiguous Is Separate

Ambiguous candidates indicate that more than one plausible fragment continuation
exists. They are useful review signals, but collapsing them into a merged track
would create identity truth that OTY1a does not have.

## Why OTY1a Does Not Confirm Identity

OTY1a has no runtime-safe identity source. It uses optical bbox geometry,
detector confidence, class consistency, endpoint motion, neighbor ambiguity,
boundary contact, and shape transition proxies only. It does not read
`review_queue.csv`, `final_gt_working.csv`, SAR GT, SAR evidence, final/manual/
oracle/review fields, selector outputs, G2, A008, threshold tuning, or training
signals.

## Why OTY1a Does Not Enter SAR Band

OTY1a operates before SAR temporal alignment. It cannot assume optical frame
number equals SAR frame number, and it cannot generate a SAR fan/range band.
OTY2 is only allowed to audit high-FPS optical-to-SAR temporal alignment before
any SAR band construction is considered.
