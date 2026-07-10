# OTY2 Tracklet Embedding Aggregation Probe

Timestamp: `20260710_000000_yolo26l`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `cdc80af`

## Boundary

This probe aggregates already-linked detection embeddings inside OTY1t short tracklet segments only. It does not compare different tracklets, generate candidate stitch pairs, merge tracker ids, assign identity truth, tune tracker parameters, modify OTY0/OTY1/OTY1a/OTY1t runtime, run SAR pairing/support, generate final boxes, create final/revised annotation artifacts, create selector/ranking output, or promote `GM_RM011` into the clean `215` pool.

The full tracklet embedding index and embedding array are written only under ignored `outputs/`; only this report and small CSV samples are intended for commit.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools/diagnostics/run_oty1t_tracklet_embedding_aggregation_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --linkage-rows outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000/oty2/embedding_track_linkage_probe_20260710_000000_yolo26l/embedding_track_linkage_rows.csv --embedding-array outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000/oty2/crop_reid_embedding_probe_20260710_000000_yolo26l/crop_reid_embeddings.npz --embedding-index outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000/oty2/crop_reid_embedding_probe_20260710_000000_yolo26l/crop_reid_embedding_index.csv --primary-tracker botsort --primary-variant raw --output-root outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000 --timestamp 20260710_000000_yolo26l
```

## Inputs And Outputs

- input linkage rows: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\embedding_track_linkage_probe_20260710_000000_yolo26l\embedding_track_linkage_rows.csv`
- input embedding array: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embeddings.npz`
- input embedding index: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embedding_index.csv`
- uncommitted tracklet index: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\tracklet_embedding_aggregation_probe_20260710_000000_yolo26l\tracklet_embedding_index.csv`
- uncommitted tracklet embeddings: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\tracklet_embedding_aggregation_probe_20260710_000000_yolo26l\tracklet_embeddings.npz`
- committed summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_tracklet_embedding_aggregation_probe_summary_20260710_000000_yolo26l.csv`
- committed schema preview CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_tracklet_embedding_aggregation_schema_preview_20260710_000000_yolo26l.csv`

## Segment Rule

Rows are grouped by `scene + tracker_name + tracker_variant + track_id`, sorted by frame, and split into a new short tracklet segment whenever adjacent linked tracker rows have frame gap `> 1`. This run uses the primary tracker version only: `botsort / normalized_active`.

## Aggregation Rule

For each segment, all linked detection feature vectors are averaged, then the aggregate vector is L2-normalized. Stability is audited by cosine similarity from each detection vector in the segment to the aggregate vector. The audit records mean, minimum, and population standard deviation. This is an internal segment-quality audit only, not an identity decision.

Ready-segment policy for this report: at least `2` linked embeddings, full usable aggregate, and intra-segment minimum cosine `>= 0.70`. Short or unstable segments are retained in the uncommitted index but should not be used as confident candidate-stitch evidence without review.

## Summary

| scene | tracker_name | tracker_variant | track_ids_total | tracklet_segments_total | segments_with_embeddings | segments_without_embeddings | segments_embedding_coverage_mean | segments_embedding_coverage_min | embedding_dim | intra_tracklet_cosine_mean | intra_tracklet_cosine_min | unstable_segments_count | short_segments_count | ready_segments_count | conclusion_scene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | botsort | raw | 18 | 33 | 33 | 0 | 1.000000 | 1.000000 | 512 | 0.949469 | 0.710180 | 0 | 7 | 26 | TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING |
| GM_RM017 | botsort | raw | 4 | 4 | 4 | 0 | 1.000000 | 1.000000 | 512 | 0.916939 | 0.476059 | 3 | 0 | 1 | TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE |
| GM_RM019 | botsort | raw | 14 | 16 | 16 | 0 | 1.000000 | 1.000000 | 512 | 0.946035 | 0.574272 | 1 | 3 | 12 | TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING |

## Required Answers

1. Which tracker version was used as the primary version?

`botsort / normalized_active`.

2. Did this use the previous direct source linkage result?

`True`. The input was the previous linkage table `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\embedding_track_linkage_probe_20260710_000000_yolo26l\embedding_track_linkage_rows.csv`; no detector, tracker, or linkage rerun was needed.

3. How were short tracklet segments defined?

By grouping on `scene + tracker_name + tracker_variant + track_id`, sorting by `frame_id`, and cutting a new segment at adjacent frame gaps greater than `1`.

4. How many track ids are present per scene?

- `GM_RM011`: `18`
- `GM_RM017`: `4`
- `GM_RM019`: `14`

5. How many short tracklet segments were cut per scene?

- `GM_RM011`: `33`
- `GM_RM017`: `4`
- `GM_RM019`: `16`

6. What is the embedding coverage of each scene's segments?

- `GM_RM011`: `1.000000`
- `GM_RM017`: `1.000000`
- `GM_RM019`: `1.000000`

7. How many short tracklet segments can form tracklet-level appearance features?

- `GM_RM011`: `33`
- `GM_RM017`: `4`
- `GM_RM019`: `16`

8. How many segments are too short or appearance-unstable?

- `GM_RM011`: `7`
- `GM_RM017`: `0`
- `GM_RM019`: `3`

Unstable segment counts:

- `GM_RM011`: `0`
- `GM_RM017`: `3`
- `GM_RM019`: `1`

9. What is the appearance aggregation method?

`mean_detection_embedding_then_l2_normalize`.

10. How is appearance stability measured?

By cosine similarity between each detection feature vector in the segment and the segment's L2-normalized aggregate vector; the report records mean, minimum, and standard deviation.

11. Can all 17 `GM_RM011` tracks enter later candidate-stitch analysis?

`16/18` `GM_RM011` track ids have at least one ready segment under this audit policy. Tracks with only short segments remain available as weak context but should not be treated as confident stitch evidence.

12. Which segments are not suitable for the next candidate-stitch probe?

- `GM_RM011__botsort__raw__bs_0001__seg_002`: scene=`GM_RM011`, track=`bs_0001`, frames=`17-17`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__raw__bs_0009__seg_002`: scene=`GM_RM011`, track=`bs_0009`, frames=`55-55`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__raw__bs_0039__seg_001`: scene=`GM_RM011`, track=`bs_0039`, frames=`189-189`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__raw__bs_0051__seg_003`: scene=`GM_RM011`, track=`bs_0051`, frames=`266-266`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__raw__bs_0052__seg_003`: scene=`GM_RM011`, track=`bs_0052`, frames=`277-277`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__raw__bs_0057__seg_003`: scene=`GM_RM011`, track=`bs_0057`, frames=`282-282`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__raw__bs_0067__seg_001`: scene=`GM_RM011`, track=`bs_0067`, frames=`314-314`, linked=`1`, min_cosine=`1.000000`
- `GM_RM017__botsort__raw__bs_0011__seg_001`: scene=`GM_RM017`, track=`bs_0011`, frames=`145-185`, linked=`41`, min_cosine=`0.498333`
- `GM_RM017__botsort__raw__bs_0013__seg_001`: scene=`GM_RM017`, track=`bs_0013`, frames=`151-200`, linked=`50`, min_cosine=`0.549661`
- `GM_RM017__botsort__raw__bs_0016__seg_001`: scene=`GM_RM017`, track=`bs_0016`, frames=`162-214`, linked=`53`, min_cosine=`0.476059`
- `GM_RM019__botsort__raw__bs_0005__seg_002`: scene=`GM_RM019`, track=`bs_0005`, frames=`29-29`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__raw__bs_0033__seg_001`: scene=`GM_RM019`, track=`bs_0033`, frames=`64-64`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__raw__bs_0054__seg_001`: scene=`GM_RM019`, track=`bs_0054`, frames=`86-86`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__raw__bs_0065__seg_001`: scene=`GM_RM019`, track=`bs_0065`, frames=`99-141`, linked=`43`, min_cosine=`0.574272`

13. Why this still does not perform final tracklet stitching?

This run only creates per-segment aggregate appearance vectors and internal quality metrics. It does not compute inter-segment similarity, propose stitch pairs, merge track ids, assign identity truth, or write any annotation/SAR-support artifact.

14. What inputs does the next candidate-stitch probe need?

- this run's uncommitted `tracklet_embedding_index.csv`
- this run's uncommitted `tracklet_embeddings.npz`
- OTY1t tracker row/track timing metadata
- segment endpoint frames and bbox motion summaries
- later component/window evidence only as post-MOT blockers or context
- an explicit report-only candidate-pair policy with no final identity assignment

## Next Recommendation

If this run is accepted as ready, the next bounded probe is:

```text
short tracklet candidate stitch-pair generation probe
```

The next probe must still output candidate evidence only, not final identity or final annotation.

## Non-Actions

- No OTY0/OTY1/OTY1a/OTY1t runtime was modified.
- No tracker parameters were tuned.
- No detector comparison was rerun.
- No inter-tracklet appearance similarity was computed.
- No candidate stitch pairs were generated.
- No SAR pairing/support was run.
- No final boxes, final/revised annotations, selector/ranking output, weighted fusion output, or identity truth were produced.
- `GM_RM011` was not promoted into the clean `215` pool.

## Conclusion

```text
TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE
```
