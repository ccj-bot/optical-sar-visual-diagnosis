# OTY1t Tracker Variant Blockers

This file lists tracker variants that did not produce real tracking rows. No blocker row is a synthesized tracker result.

| scene | tracker | dependency_status | adapter_status | blocker_reason | next_action |
| --- | --- | --- | --- | --- | --- |
| `GM_RM019` | `ocsort` | `missing_or_unsupported` | `blocker_contract_only` | ocsort dependency unavailable or unsupported for real detection-table replay: ocsort is not installed or no stable detection-table replay adapter is integrated in OTY1t-P1/P2.; install hint: Integrate a runtime-safe detection-table replay adapter and install the tracker package before enabling real runs. | Add and smoke-test a real adapter; do not synthesize tracking rows. |
| `GM_RM019` | `strongsort` | `missing_or_unsupported` | `blocker_contract_only` | strongsort dependency unavailable or unsupported for real detection-table replay: strongsort is not installed or no stable detection-table replay adapter is integrated in OTY1t-P1/P2.; install hint: Integrate a runtime-safe detection-table replay adapter and install the tracker package before enabling real runs. | Add and smoke-test a real adapter; do not synthesize tracking rows. |
