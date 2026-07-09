# OTY2 WGV2.1 Small-Window Factor-Graph Instantiation

Date: 2026-07-09

## Scope

WGV2.1 instantiates the WGV2.0 permission-gated cross-modal mechanism factor graph for nine selected WGV1.x windows. It is a graph representation and consistency audit only.

This report does not optimize, score-rank, select candidates, create labels, create final boxes, create GT boxes, revise GT, generate SAR-ready annotations, emit selector/ranking outputs, emit runtime prediction logic, instantiate final object identity, or turn mechanism support into annotation permission.

## Required Reading

Read before creating this report:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_CROSS_MODAL_MECHANISM_FACTOR_GRAPH_DESIGN.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `reports/oty2/oty2_wgv1_8_gm011_optical_behavior_to_sar_gt_local_mechanism_audit_20260709.md`
- `reports/oty2/oty2_wgv1_6_small_window_optical_sar_dual_evidence_closure_audit_20260709.md`
- `reports/oty2/oty2_wgv1_7_azimuth_constrained_optical_sar_temporal_alignment_audit_20260709.md`

## Outputs

- `reports/oty2/samples/oty2_wgv2_1_factor_graph_node_instances_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_1_factor_graph_factor_instances_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_1_mechanism_relation_decisions_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_1_factor_graph_consistency_audit_20260709.csv`

## Instantiated Windows

| Window | Role | Conservative result |
| --- | --- | --- |
| `GM_RM011_WGV14T001` | GM_RM011 mechanism construction | Supports posthoc vehicle-existence and truncation/support-shift explanation; mapping unresolved |
| `GM_RM011_WGV14T004` | GM_RM011 mechanism construction | Supports posthoc vehicle-existence vocabulary; direct GM_RM011 mapping missing |
| `GM_RM011_WGV14T005` | GM_RM011 mechanism construction | Explains visible-unboxed gap and competition; remains search hint only |
| `GM_RM011_M005` | GM_RM011 mechanism construction | Boundary preserved; bridge blocked |
| `GM_RM011_M016` | GM_RM011 mechanism construction | Boundary preserved; bridge blocked; SAR boundary evidence insufficient |
| `GM_RM017_WGV14T001` | GM_RM017 conservativeness validation | Weak posthoc support only; no upgrade |
| `GM_RM017_WGV14T002` | GM_RM017 conservativeness validation | Weak posthoc/dropout explanation only; background and competitor risks retained |
| `GM_RM017_WGV14T003` | GM_RM017 conservativeness validation | Weak posthoc support only; primary-box repair does not upgrade identity |
| `GM_RM017_WGV14V004` | GM_RM017 conservativeness validation | Blocked by identity risk and permission |

## Direct Answers

### 1. Can the WGV2.0 graph schema represent WGV1.x evidence without forcing one-to-one optical-SAR mapping?

Yes. WGV2.1 represents optical threads, behavior states, SAR morphology, geometry feasibility, boundary/competition, permission gates, and relation outcomes as separate nodes and factors. A window can have optical strength and SAR morphology vocabulary while still ending in `insufficient_evidence`, `blocked_by_permission`, or `blocked_by_boundary`.

### 2. Which GM_RM011 windows produce meaningful mechanism-relation graph instances?

`GM_RM011_WGV14T001` is the clearest posthoc mechanism instance: optical stability plus near-field truncation plus GT-local SAR morphology supports `supports_vehicle_existence` and `explains_support_shift`.

`GM_RM011_WGV14T004` is meaningful but mapping-unresolved: optical evidence is strong and SAR morphology vocabulary exists, but direct GM_RM011 azimuth/object-stream mapping is absent.

`GM_RM011_WGV14T005` is meaningful as an ambiguity instance: it explains visible-unboxed gaps and same-color competition, but remains search-hint only.

`GM_RM011_M005` and `GM_RM011_M016` are meaningful boundary instances. They are not failures of the graph; they are positive boundary-preservation outcomes.

### 3. Which GM_RM017 windows remain weak or blocked?

`GM_RM017_WGV14T001`, `GM_RM017_WGV14T002`, and `GM_RM017_WGV14T003` remain weak/search-hint only. Their posthoc SAR overlap is mixed with temporal ambiguity, competitor or multi-target signal, unknown evidence, or background risk.

`GM_RM017_WGV14V004` remains blocked by identity risk and permission. Posthoc SAR overlap cannot unblock it.

### 4. Did any weak or blocked item get incorrectly upgraded?

No. The consistency audit records `weak_or_blocked_item_upgraded=no` for all nine windows.

### 5. Did any preserved boundary get relaxed?

No. `GM_RM011_M005` and `GM_RM011_M016` both remain boundary-preserved. The consistency audit records `boundary_relaxed=no` for all rows.

### 6. Which relation outcomes appear most often?

The relation-decision table contains 19 relation rows:

- `blocked_by_boundary`: 2
- `indicates_competition`: 2
- `insufficient_evidence`: 2
- `supports_boundary`: 2
- `supports_vehicle_existence`: 2
- `weak_posthoc_support_only`: 2
- `blocked_by_identity_risk`: 1
- `blocked_by_permission`: 1
- `contradiction`: 1
- `explains_detection_dropout`: 1
- `explains_support_shift`: 1
- `explains_visible_unboxed_gap`: 1
- `indicates_background_risk`: 1

This distribution is intentional: WGV2.1 is not trying to maximize positive support. It records support, ambiguity, insufficiency, and blockers as first-class graph outcomes.

### 7. What evidence is still missing before graph-based mechanism reasoning can become stronger?

Missing evidence:

- direct GM_RM011 object-stream and azimuth/fan-polar mapping source;
- independent SAR-internal evidence units inside the temporal tubes;
- boundary-specific SAR evidence for M005 and M016;
- competitor separation for same-color vehicles in GM_RM011 and weak GM_RM017 windows;
- negative SAR logic distinguishing vehicles from static reflectors, background edges, clutter, and multi-target structures;
- a later written SAR consumption protocol if any annotation-producing stage is ever opened.

### 8. Does this produce final boxes, revised GT, SAR-ready annotation, selector, identity truth, or runtime prediction?

No. WGV2.1 produces no final boxes, no GT boxes, no revised GT, no revised annotations, no SAR-ready annotation, no selector/ranking output, no runtime prediction artifact, no identity truth, no score optimization, no weighted fusion, and no final object identity.

## Conclusion

WGV2.1 confirms that the WGV2.0 graph can encode WGV1.x evidence without collapsing it into one-to-one optical-SAR mapping. GM_RM011 mainly contributes mechanism-construction and boundary-preservation examples. GM_RM017 mainly validates conservativeness: weak items remain weak, and blocked items remain blocked.

The current graph is useful for mechanism explanation and later evidence planning only. It is not a SAR consumption artifact.
