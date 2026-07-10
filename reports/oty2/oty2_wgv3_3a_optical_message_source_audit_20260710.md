# OTY2 WGV3.3A Optical Message Source Audit

Date: 20260710

## Boundary

This audit checks whether WGV2/WGV3 optical messages can be reproduced by an automatic optical backbone. WGV1.4 is not an input to automatic construction.

## Source Alignment

| scene | tracker | detection_rows | tracker_rows | tracker_tracks | mapping_available | blocking_reason |
| --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | botsort | 413 | 413 | 18 | not_evaluated_before_freeze |  |
| GM_RM011 | bytetrack | 413 | 413 | 23 | not_evaluated_before_freeze |  |
| GM_RM017 | botsort | 215 | 215 | 4 | not_evaluated_before_freeze |  |
| GM_RM017 | bytetrack | 215 | 215 | 4 | not_evaluated_before_freeze |  |
| GM_RM019 | botsort | 288 | 288 | 14 | not_evaluated_before_freeze |  |
| GM_RM019 | bytetrack | 288 | 288 | 15 | not_evaluated_before_freeze |  |

## Automatic Freeze

| frozen_file | sha256 | bytes |
| --- | --- | --- |
| reports/oty2/samples/oty2_wgv3_3a_source_alignment_20260710.csv | 138cd41e65d86d1898d0d1ef71852e1d987d469ab53a658ce45b2f11076bae71 | 4992 |
| reports/oty2/samples/oty2_wgv3_3a_auto_tracklet_nodes_20260710.csv | 4f7104f08b86bee1b830e4b9bd93ae57e9699bac41d2f11b7bd3d2b3d9dcfa51 | 41516 |
| reports/oty2/samples/oty2_wgv3_3a_auto_relation_candidates_20260710.csv | ca72c314aa16dd8ec569b248fa9caf520bc1254d0267ebaa04311104a4ed1bdf | 138770 |
| reports/oty2/samples/oty2_wgv3_3a_auto_relation_decisions_20260710.csv | ca72c314aa16dd8ec569b248fa9caf520bc1254d0267ebaa04311104a4ed1bdf | 138770 |
| reports/oty2/samples/oty2_wgv3_3a_competition_relations_20260710.csv | 6caa6bc6322d0cedd6c4dbc391a1033768155bb46aa251ae3ea816832a5710a2 | 23362 |

The listed automatic files were written before WGV1.4/WGV1.4b reference tables were read.
