# OTY1t Cross-Tracker Comparison

Generated: `2026-07-01T21:01:16`
Scene: `GM_RM019`

## Boundary

Tracker outputs are optical identity hypotheses only. No confirmed identity, SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector, training, or annotation proposal was introduced.

## Rows

| tracker | real_run | dependency | detections | tracked | unmatched_rate | tracks | stable | ambiguous | duplicate | switch | 0039/0045 | recommendation | blocker |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `botsort` | `true` | `available` | 334 | 222 | 0.33532934131736525 | 19 | 3 | 0 | 8 | 4 | `false` | `optional_continuity_hint_only` | No hard OTY1t blocker; tracker ids remain optical hypotheses only. |
| `bytetrack` | `true` | `available` | 334 | 207 | 0.38023952095808383 | 21 | 3 | 0 | 8 | 6 | `false` | `optional_continuity_hint_only` | No hard OTY1t blocker; tracker ids remain optical hypotheses only. |
| `ocsort` | `false` | `missing_or_unsupported` | 334 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 | `false` | `not_recommended` | ocsort dependency unavailable or unsupported for real detection-table replay: ocsort is not installed or no stable detection-table replay adapter is integrated in OTY1t-P1/P2.; install hint: Integrate a runtime-safe detection-table replay adapter and install the tracker package before enabling real runs. |
| `strongsort` | `false` | `missing_or_unsupported` | 334 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 | `false` | `not_recommended` | strongsort dependency unavailable or unsupported for real detection-table replay: strongsort is not installed or no stable detection-table replay adapter is integrated in OTY1t-P1/P2.; install hint: Integrate a runtime-safe detection-table replay adapter and install the tracker package before enabling real runs. |
