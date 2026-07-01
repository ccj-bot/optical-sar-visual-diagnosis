# Failure Case Selection Plan

Select 20-40 V0 cases before V0.1. Keep the set small enough for human visual review and broad enough to cover source families and scenes.

| Class | Selection criteria | Required fields | Fallback if fields missing | Why this class matters | Expected visual diagnosis question |
|---|---|---|---|---|---|
| `top1_bad_top20_good` | Top1 visually poor or low posthoc AABB proxy; top20 contains better candidate | target id, scene, SAR frame, ranked candidates, top-k accounting | use C1.4 frozen ranked table plus posthoc top-k accounting; mark missing if no rank table | separates candidate availability from rank ordering | Is there a good candidate, and why is it not early? |
| `candidate_pool_bad` | Full pool has no visually vehicle-like candidate | candidate bank, source family, SAR frame | use C1.3 structural bank or C1.2 extended bank | tests pool ceiling | Is the upstream candidate pool insufficient? |
| `top1_good` | Top1 visually on vehicle | frozen rank, SAR frame, source family | use base/factor candidate if frozen rank missing | provides controls and prevents only-failure bias | What does a visually correct case look like? |
| `factor_topk_best` | Best visual candidate comes from factor top-k family | `factor_topk_candidate`, rank/source fields | use C1.1/C1.2 candidate tables | tests retrieval candidate quality | Does factor retrieval recover vehicle-like structure? |
| `wedge_best` | Wedge candidate is visually best or uniquely plausible | wedge mode rows, geometry fields | use C1.2 wedge candidates; mark support fields missing | tests local SAR structure | Does wedge evidence align with the vehicle body? |
| `ray_best` | Ray/multi-peak candidate is visually best or explains range correction | ray mode rows, range deltas | use C1.2 ray rows or C1.3 structural bank | tests range profile evidence | Is range prior wrong and corrected by SAR peaks? |
| `signed_best` | Signed/track evidence suggests a different range direction | signed rows, neighbor context, deltas | use C1.3/C1.4 signed partial fields | tests temporal release | Does temporal evidence support range movement? |
| `sar_only_blocked` | SAR-only target lacks runtime prior | SAR frame, target id, missing prior reason | keep final/posthoc fields hidden; mark blocked | prevents final-box leakage | What can be diagnosed without optical prior? |
| `gmrm011_probe` | GM_RM011 case with available raw frames but no replicated chain | scene/frame paths, config | create manual placeholder and missing accounting report | tests cross-scene risk | Does GM_RM011 geometry/OBB convention differ visually? |
| `gmrm017_reference` | Reference case from better-supported scene | scene/frame paths and known accounting if available | use manual reference panel | gives baseline contrast | What does stable geometry look like? |

## Minimum Mix

- 6-10 `top1_bad_top20_good`
- 4-6 `candidate_pool_bad`
- 3-5 `top1_good`
- 2-4 each for wedge/ray/signed best
- 2-3 SAR-only blocked
- 3-5 GM_RM011 probes
- 2-3 GM_RM017 references

Do not expand beyond 40 before the first human review sheet is populated.
