# OTY2 Tracklet Embedding Aggregation Probe

Timestamp: `20260705_193000`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `5127cbc`

## Boundary

This probe aggregates already-linked detection embeddings inside OTY1t short tracklet segments only. It does not compare different tracklets, generate candidate stitch pairs, merge tracker ids, assign identity truth, tune tracker parameters, modify OTY0/OTY1/OTY1a/OTY1t runtime, run SAR pairing/support, generate final boxes, create final/revised annotation artifacts, create selector/ranking output, or promote `GM_RM011` into the clean `215` pool.

The full tracklet embedding index and embedding array are written only under ignored `outputs/`; only this report and small CSV samples are intended for commit.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracklet_embedding_aggregation_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --linkage-rows outputs\oty2\embedding_track_linkage_probe_20260705_183000\embedding_track_linkage_rows.csv --embedding-array outputs\oty2\crop_reid_embedding_probe_20260705_170500\crop_reid_embeddings.npz --primary-tracker botsort --primary-variant normalized_active --output-root outputs --timestamp 20260705_193000
```

## Inputs And Outputs

- input linkage rows: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\embedding_track_linkage_probe_20260705_183000\embedding_track_linkage_rows.csv`
- input embedding array: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\crop_reid_embedding_probe_20260705_170500\crop_reid_embeddings.npz`
- input embedding index: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\crop_reid_embedding_probe_20260705_170500\crop_reid_embedding_index.csv`
- uncommitted tracklet index: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\tracklet_embedding_aggregation_probe_20260705_193000\tracklet_embedding_index.csv`
- uncommitted tracklet embeddings: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\tracklet_embedding_aggregation_probe_20260705_193000\tracklet_embeddings.npz`
- committed summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_tracklet_embedding_aggregation_probe_summary_20260705_193000.csv`
- committed schema preview CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_tracklet_embedding_aggregation_schema_preview_20260705_193000.csv`

## Segment Rule

Rows are grouped by `scene + tracker_name + tracker_variant + track_id`, sorted by frame, and split into a new short tracklet segment whenever adjacent linked tracker rows have frame gap `> 1`. This run uses the primary tracker version only: `botsort / normalized_active`.

## Aggregation Rule

For each segment, all linked detection feature vectors are averaged, then the aggregate vector is L2-normalized. Stability is audited by cosine similarity from each detection vector in the segment to the aggregate vector. The audit records mean, minimum, and population standard deviation. This is an internal segment-quality audit only, not an identity decision.

Ready-segment policy for this report: at least `2` linked embeddings, full usable aggregate, and intra-segment minimum cosine `>= 0.70`. Short or unstable segments are retained in the uncommitted index but should not be used as confident candidate-stitch evidence without review.

## Summary

| scene | tracker_name | tracker_variant | track_ids_total | tracklet_segments_total | segments_with_embeddings | segments_without_embeddings | segments_embedding_coverage_mean | segments_embedding_coverage_min | embedding_dim | intra_tracklet_cosine_mean | intra_tracklet_cosine_min | unstable_segments_count | short_segments_count | ready_segments_count | conclusion_scene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | botsort | normalized_active | 17 | 29 | 29 | 0 | 1.000000 | 1.000000 | 512 | 0.937761 | 0.714843 | 0 | 4 | 25 | TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING |
| GM_RM017 | botsort | normalized_active | 5 | 5 | 5 | 0 | 1.000000 | 1.000000 | 512 | 0.926826 | 0.457126 | 3 | 0 | 2 | TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE |
| GM_RM019 | botsort | normalized_active | 19 | 28 | 28 | 0 | 1.000000 | 1.000000 | 512 | 0.962961 | 0.621923 | 2 | 6 | 20 | TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING |

## Required Answers

1. Which tracker version was used as the primary version?

`botsort / normalized_active`.

2. Did this use the previous direct source linkage result?

`True`. The input was the previous linkage table `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\embedding_track_linkage_probe_20260705_183000\embedding_track_linkage_rows.csv`; no detector, tracker, or linkage rerun was needed.

3. How were short tracklet segments defined?

By grouping on `scene + tracker_name + tracker_variant + track_id`, sorting by `frame_id`, and cutting a new segment at adjacent frame gaps greater than `1`.

4. How many track ids are present per scene?

- `GM_RM011`: `17`
- `GM_RM017`: `5`
- `GM_RM019`: `19`

5. How many short tracklet segments were cut per scene?

- `GM_RM011`: `29`
- `GM_RM017`: `5`
- `GM_RM019`: `28`

6. What is the embedding coverage of each scene's segments?

- `GM_RM011`: `1.000000`
- `GM_RM017`: `1.000000`
- `GM_RM019`: `1.000000`

7. How many short tracklet segments can form tracklet-level appearance features?

- `GM_RM011`: `29`
- `GM_RM017`: `5`
- `GM_RM019`: `28`

8. How many segments are too short or appearance-unstable?

- `GM_RM011`: `4`
- `GM_RM017`: `0`
- `GM_RM019`: `6`

Unstable segment counts:

- `GM_RM011`: `0`
- `GM_RM017`: `3`
- `GM_RM019`: `2`

9. What is the appearance aggregation method?

`mean_detection_embedding_then_l2_normalize`.

10. How is appearance stability measured?

By cosine similarity between each detection feature vector in the segment and the segment's L2-normalized aggregate vector; the report records mean, minimum, and standard deviation.

11. Can all 17 `GM_RM011` tracks enter later candidate-stitch analysis?

`17/17` `GM_RM011` track ids have at least one ready segment under this audit policy. Tracks with only short segments remain available as weak context but should not be treated as confident stitch evidence.

12. Which segments are not suitable for the next candidate-stitch probe?

- `GM_RM011__botsort__normalized_active__bs_0022__seg_001`: scene=`GM_RM011`, track=`bs_0022`, frames=`106-106`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__normalized_active__bs_0031__seg_001`: scene=`GM_RM011`, track=`bs_0031`, frames=`145-145`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__normalized_active__bs_0044__seg_001`: scene=`GM_RM011`, track=`bs_0044`, frames=`229-229`, linked=`1`, min_cosine=`1.000000`
- `GM_RM011__botsort__normalized_active__bs_0051__seg_002`: scene=`GM_RM011`, track=`bs_0051`, frames=`251-251`, linked=`1`, min_cosine=`1.000000`
- `GM_RM017__botsort__normalized_active__bs_0008__seg_001`: scene=`GM_RM017`, track=`bs_0008`, frames=`145-185`, linked=`41`, min_cosine=`0.496744`
- `GM_RM017__botsort__normalized_active__bs_0010__seg_001`: scene=`GM_RM017`, track=`bs_0010`, frames=`151-200`, linked=`50`, min_cosine=`0.559784`
- `GM_RM017__botsort__normalized_active__bs_0012__seg_001`: scene=`GM_RM017`, track=`bs_0012`, frames=`162-214`, linked=`53`, min_cosine=`0.457126`
- `GM_RM019__botsort__normalized_active__bs_0004__seg_001`: scene=`GM_RM019`, track=`bs_0004`, frames=`5-43`, linked=`39`, min_cosine=`0.693182`
- `GM_RM019__botsort__normalized_active__bs_0020__seg_001`: scene=`GM_RM019`, track=`bs_0020`, frames=`42-42`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__normalized_active__bs_0032__seg_003`: scene=`GM_RM019`, track=`bs_0032`, frames=`66-66`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__normalized_active__bs_0032__seg_004`: scene=`GM_RM019`, track=`bs_0032`, frames=`72-72`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__normalized_active__bs_0043__seg_001`: scene=`GM_RM019`, track=`bs_0043`, frames=`71-71`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__normalized_active__bs_0056__seg_001`: scene=`GM_RM019`, track=`bs_0056`, frames=`84-84`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__normalized_active__bs_0056__seg_002`: scene=`GM_RM019`, track=`bs_0056`, frames=`87-87`, linked=`1`, min_cosine=`1.000000`
- `GM_RM019__botsort__normalized_active__bs_0066__seg_002`: scene=`GM_RM019`, track=`bs_0066`, frames=`125-141`, linked=`17`, min_cosine=`0.621923`

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
