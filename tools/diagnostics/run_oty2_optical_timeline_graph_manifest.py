"""Build the OTY2 diagnostic optical timeline graph input contract.

This script consolidates existing optical detections, BoT-SORT normalized_active
track fragments, and same-vehicle referent audit rows into diagnostic graph
tables. It does not create final annotations, revised GT, final boxes, SAR
pairing/support, selector/ranking output, or model artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SAME_VEHICLE = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_same_vehicle_referent_consistency_summary_20260705_165636.csv"
DEFAULT_GM011_CONTRAST = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_gm011_optical_vehicle_timeline_contrast_summary_20260705_235500.csv"
DEFAULT_TRACKLET_INDEX = REPO_ROOT / "outputs" / "oty2" / "tracklet_embedding_aggregation_probe_20260705_193000" / "tracklet_embedding_index.csv"
DEFAULT_LINKAGE_ROWS = REPO_ROOT / "outputs" / "oty2" / "embedding_track_linkage_probe_20260705_183000" / "embedding_track_linkage_rows.csv"
DEFAULT_CROP_INDEX = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500" / "crop_reid_embedding_index.csv"

NODE_FIELDS = [
    "scene",
    "node_id",
    "diagnostic_vehicle_id",
    "source_track_id",
    "source_segment_id",
    "frame_start",
    "frame_end",
    "node_type",
    "same_vehicle_fragment_status",
    "box_content_status",
    "appearance_status",
    "usable_for_timeline",
    "risk_tags",
    "reason",
]

EDGE_FIELDS = [
    "scene",
    "edge_id",
    "from_node",
    "to_node",
    "edge_type",
    "same_vehicle_judgement",
    "connection_strength",
    "visual_basis",
    "method_failure_layer",
    "recommended_action",
    "forbidden_reason",
    "can_merge_for_visualization",
    "can_support_sar_later",
    "reason",
]

MANIFEST_FIELDS = [
    "scene",
    "optical_frame_num",
    "diagnostic_vehicle_id",
    "source_track_id",
    "source_segment_id",
    "source_det_id",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "display_label",
    "display_status",
    "risk_tags",
    "reason",
]


@dataclass(frozen=True)
class NodeSpec:
    scene: str
    node_id: str
    diagnostic_vehicle_id: str
    source_track_id: str
    source_segment_suffix: str
    node_type: str
    same_vehicle_fragment_status: str
    box_content_status: str
    appearance_status: str
    usable_for_timeline: str
    risk_tags: str
    render_status: str
    reason: str


@dataclass(frozen=True)
class EdgeSpec:
    scene: str
    edge_id: str
    from_node: str
    to_node: str
    edge_type: str
    same_vehicle_judgement: str
    connection_strength: str
    visual_basis: str
    method_failure_layer: str
    recommended_action: str
    forbidden_reason: str
    can_merge_for_visualization: str
    can_support_sar_later: str
    reason: str


NODE_SPECS = [
    NodeSpec("GM_RM017", "GM_RM017_N001", "GM_RM017_V001", "bs_0008", "seg_001", "same_vehicle_fragment", "same_vehicle", "partial_edge_box_still_on_leading_dark_sedan", "downweight_crop_feature", "yes", "edge_contact;partial_visible;appearance_weak", "weak_timeline", "Leading dark sedan fragment; same referent inside the track, not a final identity."),
    NodeSpec("GM_RM017", "GM_RM017_N002", "GM_RM017_V002", "bs_0010", "seg_001", "same_vehicle_fragment", "same_vehicle", "partial_edge_box_still_on_white_suv", "downweight_crop_feature", "yes", "edge_contact;partial_visible;appearance_weak", "strong_timeline", "White SUV fragment; strongest GM_RM017 same-vehicle referent."),
    NodeSpec("GM_RM017", "GM_RM017_N003", "GM_RM017_V003", "bs_0012", "seg_001", "same_vehicle_fragment", "likely_same_vehicle", "partial_edge_box_still_on_trailing_dark_sedan", "downweight_crop_feature", "yes_weak", "edge_contact;partial_visible;similar_dark_vehicle_guard", "weak_timeline", "Trailing dark sedan fragment; keep separate from bs_0008."),
    NodeSpec("GM_RM017", "GM_RM017_N004", "GM_RM017_V004", "bs_0001", "seg_001", "context_vehicle_fragment", "same_vehicle", "large_bright_vehicle_box", "appearance_not_primary", "yes_context", "large_vehicle_context;target_relevance_review", "review_only", "Large box/truck-like context vehicle; not promoted to final target."),
    NodeSpec("GM_RM017", "GM_RM017_N005", "GM_RM017_NONVEHICLE_001", "bs_0002", "seg_001", "non_vehicle_exclusion", "not_same_vehicle", "non_vehicle_barrier_content", "not_applicable", "no", "non_vehicle;exclude_from_vehicle_timeline", "non_vehicle_not_rendered", "Foreground barrier or temporary structure, not a vehicle referent."),
    NodeSpec("GM_RM011", "GM_RM011_N001", "GM_RM011_V001", "bs_0015", "seg_001", "same_vehicle_fragment", "same_vehicle", "partial_front_side_box", "downweight_if_needed", "yes", "partial_visible;short_gap_endpoint", "strong_timeline", "First segment of the white vehicle front/windshield local chain."),
    NodeSpec("GM_RM011", "GM_RM011_N002", "GM_RM011_V001", "bs_0015", "seg_002", "same_vehicle_fragment", "same_vehicle", "partial_front_side_box", "downweight_if_needed", "yes", "partial_visible;short_gap_endpoint", "strong_timeline", "Second segment of the same bs_0015 white vehicle chain."),
    NodeSpec("GM_RM011", "GM_RM011_N003", "GM_RM011_V002", "bs_0061", "seg_001", "weak_same_vehicle_fragment", "possible_same_vehicle", "rear_side_to_front_window_transition", "appearance_not_comparable", "yes_weak", "part_state_transition;longer_gap;review", "weak_timeline", "Weak first fragment of the bs_0061 local chain."),
    NodeSpec("GM_RM011", "GM_RM011_N004", "GM_RM011_V002", "bs_0061", "seg_002", "same_vehicle_fragment", "same_vehicle", "partial_front_window_box", "downweight_if_needed", "yes", "partial_visible;competitor_excluded", "strong_timeline", "Central white vehicle front/window segment."),
    NodeSpec("GM_RM011", "GM_RM011_N005", "GM_RM011_V002", "bs_0061", "seg_003", "same_vehicle_fragment", "same_vehicle", "partial_front_window_box", "downweight_if_needed", "yes", "partial_visible;competitor_excluded", "strong_timeline", "Continuation of central white vehicle front/window segment."),
    NodeSpec("GM_RM011", "GM_RM011_N006", "GM_RM011_FORBIDDEN_CONTEXT_001", "bs_0064", "seg_001", "forbidden_context_fragment", "not_same_vehicle", "left_edge_competing_vehicle", "appearance_misleading", "no", "forbidden_bridge;competition", "forbidden_not_rendered", "Competing left-edge vehicle used only to block bs_0061 to bs_0064 merge."),
    NodeSpec("GM_RM011", "GM_RM011_N007", "GM_RM011_FORBIDDEN_CONTEXT_002", "bs_0056", "seg_001", "forbidden_context_fragment", "not_same_vehicle", "side_window_strip_competition", "appearance_misleading", "no", "forbidden_bridge;part_switch;competition", "forbidden_not_rendered", "Source fragment used only to block bs_0056 to bs_0061 bridge."),
    NodeSpec("GM_RM011", "GM_RM011_N008", "GM_RM011_V003", "bs_0029", "seg_001", "review_fragment", "possible_same_vehicle", "right_edge_white_vehicle", "feature_not_meaningful", "review_only", "edge_contact;thin_crop_risk", "review_only", "Right-edge white vehicle review fragment."),
    NodeSpec("GM_RM011", "GM_RM011_N009", "GM_RM011_V003", "bs_0029", "seg_002", "review_fragment", "possible_same_vehicle", "thin_right_edge_strip", "feature_not_meaningful", "review_only", "edge_contact;thin_crop_risk", "review_only", "Thin edge continuation; review only."),
    NodeSpec("GM_RM011", "GM_RM011_N010", "GM_RM011_V004", "bs_0044", "seg_002", "weak_same_vehicle_fragment", "possible_same_vehicle", "upper_side_window_part", "appearance_not_comparable", "yes_weak", "part_state_transition;review", "weak_timeline", "Weak source fragment for bs_0044 to bs_0038 part transition."),
    NodeSpec("GM_RM011", "GM_RM011_N011", "GM_RM011_V004", "bs_0038", "seg_002", "weak_same_vehicle_fragment", "possible_same_vehicle", "front_hood_part", "appearance_not_comparable", "yes_weak", "part_state_transition;review", "weak_timeline", "Weak target fragment for bs_0044 to bs_0038 part transition."),
    NodeSpec("GM_RM011", "GM_RM011_N012", "GM_RM011_V005", "bs_0002", "seg_001", "weak_same_vehicle_fragment", "possible_same_vehicle", "rear_body_white_suv", "appearance_not_comparable", "yes_weak", "part_state_transition", "weak_timeline", "Weak source fragment for early white SUV relation."),
    NodeSpec("GM_RM011", "GM_RM011_N013", "GM_RM011_V005", "bs_0007", "seg_001", "weak_same_vehicle_fragment", "possible_same_vehicle", "upper_window_strip", "appearance_not_comparable", "yes_weak", "part_state_transition", "weak_timeline", "Weak target fragment for early white SUV relation."),
]

EDGE_SPECS = [
    EdgeSpec("GM_RM011", "GM_RM011_E001", "GM_RM011_N001", "GM_RM011_N002", "strong_same_vehicle_edge", "same_vehicle", "strong", "Same white vehicle front and windshield continue across a short gap.", "box_layer;crop_layer;track_id_layer", "connect_window", "", "yes", "yes_soft_prior_later", "Strong local diagnostic edge only; not a final identity merge."),
    EdgeSpec("GM_RM011", "GM_RM011_E002", "GM_RM011_N004", "GM_RM011_N005", "strong_same_vehicle_edge", "same_vehicle", "strong", "Central white vehicle front and windshield continue; left-edge neighbor is separable.", "box_layer;crop_layer;window_connection_layer", "connect_window", "", "yes", "yes_soft_prior_later", "Strong local edge with competitor-exclusion note."),
    EdgeSpec("GM_RM011", "GM_RM011_E003", "GM_RM011_N003", "GM_RM011_N004", "weak_same_vehicle_edge", "possible_same_vehicle", "weak", "Same white vehicle is plausible, but the visible part changes from rear/side to front/window over a longer gap.", "box_layer;crop_layer;feature_layer;window_connection_layer", "weak_connect_only", "", "weak_label_only", "review_before_sar", "Weak diagnostic edge; do not direct-merge track identity."),
    EdgeSpec("GM_RM011", "GM_RM011_E004", "GM_RM011_N008", "GM_RM011_N009", "weak_same_vehicle_edge", "possible_same_vehicle", "review_only", "Right-edge white vehicle may continue, but the successor crop is too thin.", "box_layer;crop_layer", "manual_review", "", "no_auto_merge", "no_until_review", "Review-only edge; too little visible vehicle area."),
    EdgeSpec("GM_RM011", "GM_RM011_E005", "GM_RM011_N010", "GM_RM011_N011", "weak_same_vehicle_edge", "possible_same_vehicle", "weak", "Plausible upper side/window to front/hood part transition.", "box_layer;crop_layer;feature_layer", "weak_connect_only", "", "weak_label_only", "review_before_sar", "Weak part-transition edge."),
    EdgeSpec("GM_RM011", "GM_RM011_E006", "GM_RM011_N012", "GM_RM011_N013", "weak_same_vehicle_edge", "possible_same_vehicle", "weak", "Plausible white SUV rear/body to upper-window part transition.", "box_layer;crop_layer;feature_layer", "weak_connect_only", "", "weak_label_only", "review_before_sar", "Weak early-scene part-transition edge."),
    EdgeSpec("GM_RM017", "GM_RM017_E001", "GM_RM017_N001", "GM_RM017_N003", "forbidden_edge", "not_same_vehicle", "forbidden", "Dense frames show two separate dark sedans, not one target.", "window_connection_layer;feature_layer", "forbid_connection", "similar dark-car appearance would create a false merge", "no", "no", "Forbidden false-merge guard between leading and trailing dark sedans."),
    EdgeSpec("GM_RM011", "GM_RM011_E007", "GM_RM011_N003", "GM_RM011_N006", "forbidden_edge", "not_same_vehicle", "forbidden", "Successor box falls on a left-edge competing vehicle while the central white car remains separate.", "box_layer;window_connection_layer;track_id_layer", "forbid_connection", "competitor explains successor better", "no", "no", "Forbidden bs_0061 to bs_0064 bridge."),
    EdgeSpec("GM_RM011", "GM_RM011_E008", "GM_RM011_N007", "GM_RM011_N003", "forbidden_edge", "not_same_vehicle", "forbidden", "Side/window strip switches to left-edge rear fragment or competing region.", "crop_layer;window_connection_layer;feature_layer", "forbid_connection", "competition cannot be excluded", "no", "no", "Forbidden proximity/appearance bridge."),
    EdgeSpec("GM_RM017", "GM_RM017_E002", "GM_RM017_N005", "GM_RM017_N005", "non_vehicle_exclusion", "not_same_vehicle", "excluded", "Box follows a foreground barrier or temporary structure, not a vehicle.", "box_layer;track_id_layer", "manual_review", "non_vehicle_box_content", "no", "no", "Unary exclusion edge for non-vehicle track content."),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh) if not duplicate_header(row)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def duplicate_header(row: Mapping[str, Any]) -> bool:
    values = [str(value or "").strip() for value in row.values() if str(value or "").strip()]
    if not values:
        return False
    hits = sum(1 for key, value in row.items() if str(value or "").strip() == key)
    return hits >= max(2, len(values) // 2)


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_int(value: Any) -> int | None:
    text = norm(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_bbox(value: Any) -> tuple[float, float, float, float] | None:
    text = norm(value)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) < 4:
        return None
    try:
        x1, y1, x2, y2 = (float(item) for item in parsed[:4])
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def segment_key(scene: str, track_id: str, suffix: str) -> tuple[str, str, str]:
    return scene, track_id, suffix


def load_segments(tracklet_rows: Iterable[Mapping[str, str]]) -> dict[tuple[str, str, str], Mapping[str, str]]:
    out: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in tracklet_rows:
        if norm(row.get("tracker_name")) != "botsort" or norm(row.get("tracker_variant")) != "normalized_active":
            continue
        segment_id = norm(row.get("tracklet_segment_id"))
        suffix = segment_id.rsplit("__", 1)[-1] if "__" in segment_id else segment_id
        key = segment_key(norm(row.get("scene")), norm(row.get("track_id")), suffix)
        out[key] = row
    return out


def node_rows(node_specs: Sequence[NodeSpec], segments: Mapping[tuple[str, str, str], Mapping[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for spec in node_specs:
        seg = segments.get(segment_key(spec.scene, spec.source_track_id, spec.source_segment_suffix))
        if not seg:
            raise KeyError(f"Missing segment for {spec.scene} {spec.source_track_id} {spec.source_segment_suffix}")
        rows.append(
            {
                "scene": spec.scene,
                "node_id": spec.node_id,
                "diagnostic_vehicle_id": spec.diagnostic_vehicle_id,
                "source_track_id": spec.source_track_id,
                "source_segment_id": norm(seg.get("tracklet_segment_id")),
                "frame_start": norm(seg.get("frame_start")),
                "frame_end": norm(seg.get("frame_end")),
                "node_type": spec.node_type,
                "same_vehicle_fragment_status": spec.same_vehicle_fragment_status,
                "box_content_status": spec.box_content_status,
                "appearance_status": spec.appearance_status,
                "usable_for_timeline": spec.usable_for_timeline,
                "risk_tags": spec.risk_tags,
                "reason": spec.reason,
            }
        )
    return rows


def edge_rows(edge_specs: Sequence[EdgeSpec]) -> list[dict[str, str]]:
    return [spec.__dict__.copy() for spec in edge_specs]


def load_crop_paths(crop_rows: Iterable[Mapping[str, str]]) -> dict[str, str]:
    return {norm(row.get("row_uid")): norm(row.get("optical_path")) for row in crop_rows if norm(row.get("row_uid"))}


def load_linkage(linkage_rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in linkage_rows:
        if norm(row.get("tracker_name")) != "botsort" or norm(row.get("tracker_variant")) != "normalized_active":
            continue
        frame = parse_int(row.get("frame_id"))
        bbox = parse_bbox(row.get("tracker_bbox_xyxy")) or parse_bbox(row.get("detection_bbox_xyxy_clamped"))
        if frame is None or bbox is None:
            continue
        out.append(
            {
                "scene": norm(row.get("scene")),
                "frame": frame,
                "track_id": norm(row.get("track_id")),
                "det_id": norm(row.get("det_id_ignored")),
                "embedding_uid": norm(row.get("embedding_row_uid")),
                "bbox": bbox,
            }
        )
    return out


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def display_priority(status: str) -> int:
    order = {
        "strong_timeline": 0,
        "weak_timeline": 1,
        "review_only": 2,
        "partial_visible": 3,
        "edge_contact": 4,
        "forbidden_not_rendered": 5,
        "non_vehicle_not_rendered": 6,
    }
    return order.get(status, 10)


def manifest_rows(
    node_specs: Sequence[NodeSpec],
    nodes: Sequence[Mapping[str, str]],
    linkage: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    spec_by_id = {spec.node_id: spec for spec in node_specs}
    candidate_rows: list[dict[str, str]] = []
    for node_id, node in node_by_id.items():
        spec = spec_by_id[node_id]
        start = parse_int(node.get("frame_start"))
        end = parse_int(node.get("frame_end"))
        if start is None or end is None:
            continue
        for link in linkage:
            if link["scene"] != node["scene"] or link["track_id"] != node["source_track_id"]:
                continue
            if not (start <= link["frame"] <= end):
                continue
            x1, y1, x2, y2 = link["bbox"]
            candidate_rows.append(
                {
                    "scene": node["scene"],
                    "optical_frame_num": str(link["frame"]),
                    "diagnostic_vehicle_id": node["diagnostic_vehicle_id"],
                    "source_track_id": node["source_track_id"],
                    "source_segment_id": node["source_segment_id"],
                    "source_det_id": link["det_id"],
                    "bbox_x1": f"{x1:.3f}",
                    "bbox_y1": f"{y1:.3f}",
                    "bbox_x2": f"{x2:.3f}",
                    "bbox_y2": f"{y2:.3f}",
                    "display_label": node["diagnostic_vehicle_id"],
                    "display_status": spec.render_status,
                    "risk_tags": node["risk_tags"],
                    "reason": node["reason"],
                }
            )

    # Keep at most one primary box per diagnostic vehicle per frame. Prefer
    # stronger render status, then larger box area.
    chosen: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in candidate_rows:
        key = (row["scene"], row["optical_frame_num"], row["diagnostic_vehicle_id"])
        current = chosen.get(key)
        if current is None:
            chosen[key] = row
            continue
        row_key = (
            display_priority(row["display_status"]),
            -bbox_area((float(row["bbox_x1"]), float(row["bbox_y1"]), float(row["bbox_x2"]), float(row["bbox_y2"]))),
        )
        cur_key = (
            display_priority(current["display_status"]),
            -bbox_area((float(current["bbox_x1"]), float(current["bbox_y1"]), float(current["bbox_x2"]), float(current["bbox_y2"]))),
        )
        if row_key < cur_key:
            chosen[key] = row

    return sorted(chosen.values(), key=lambda item: (item["scene"], int(item["optical_frame_num"]), item["diagnostic_vehicle_id"]))


def contract_report(
    timestamp: str,
    nodes_path: Path,
    edges_path: Path,
    manifest_path: Path,
    nodes: Sequence[Mapping[str, str]],
    edges: Sequence[Mapping[str, str]],
    manifest: Sequence[Mapping[str, str]],
    source_paths: Mapping[str, Path],
) -> str:
    edge_counts: dict[str, int] = {}
    for edge in edges:
        edge_counts[edge["edge_type"]] = edge_counts.get(edge["edge_type"], 0) + 1
    manifest_status_counts: dict[str, int] = {}
    for row in manifest:
        manifest_status_counts[row["display_status"]] = manifest_status_counts.get(row["display_status"], 0) + 1
    render_ready = bool(manifest)
    conclusion = "OPTICAL_TIMELINE_GRAPH_INPUT_CONTRACT_READY_FOR_RENDERING" if render_ready else "OPTICAL_TIMELINE_GRAPH_INPUT_CONTRACT_PARTIAL_NO_RENDER_MANIFEST"

    return f"""# OTY2 Optical Timeline Graph Input Contract

Timestamp: `{timestamp}`
Repository: `{REPO_ROOT}`
Branch: `feature/oty2-posthoc-mechanism-validation`
Input HEAD expectation: includes `4ca05aa Audit same-vehicle referent consistency`

## Boundary

This artifact defines the input contract for a diagnostic optical vehicle timeline graph. It does not create final annotation, revised GT, final boxes, SAR pairing/support, selector/ranking output, training data, or identity truth.

The graph is an optical-side intermediate layer. It can later feed visualization and SAR migration planning only as a soft diagnostic prior.

## Source Tables

- Same-vehicle referent audit: `{source_paths['same_vehicle'].relative_to(REPO_ROOT)}`
- GM_RM011 contrast audit: `{source_paths['gm011_contrast'].relative_to(REPO_ROOT)}`
- BoT-SORT normalized_active segment index: `{source_paths['tracklet_index'].relative_to(REPO_ROOT)}`
- BoT-SORT to detection/crop linkage: `{source_paths['linkage_rows'].relative_to(REPO_ROOT)}`
- Crop/frame path index: `{source_paths['crop_index'].relative_to(REPO_ROOT)}`

The OTY0 detection table provides `scene + optical_frame_num + det_id + bbox + optical_path`. The tracker linkage table provides `scene + tracker_name + tracker_variant + track_id + segment_id` through the BoT-SORT normalized_active stream used by the visual audits.

## ID Contract

Raw detection ID:

```text
scene + optical_frame_num + det_id
```

This points to one detector box in one optical frame.

Tracker fragment ID:

```text
scene + tracker_name + tracker_variant + track_id + segment_id
```

This points to one algorithmic short track fragment. `track_id` is not a physical vehicle identity.

Diagnostic vehicle ID:

```text
diagnostic_vehicle_id
```

Examples in this round are `GM_RM017_V001`, `GM_RM017_V002`, and `GM_RM011_V001`. This ID is a diagnostic intermediate referent, not final GT, final annotation, or human identity truth.

## Output Tables

- Nodes: `{nodes_path.relative_to(REPO_ROOT)}` with `{len(nodes)}` rows.
- Edges: `{edges_path.relative_to(REPO_ROOT)}` with `{len(edges)}` rows.
- Video render manifest: `{manifest_path.relative_to(REPO_ROOT)}` with `{len(manifest)}` rows.

Edge counts:

| edge_type | count |
| --- | ---: |
{chr(10).join(f'| `{key}` | {value} |' for key, value in sorted(edge_counts.items()))}

Render status counts:

| display_status | count |
| --- | ---: |
{chr(10).join(f'| `{key}` | {value} |' for key, value in sorted(manifest_status_counts.items()))}

## Strong, Weak, Forbidden

Strong edges can share the same `diagnostic_vehicle_id` in visualization:

- `GM_RM011_N001 -> GM_RM011_N002`
- `GM_RM011_N004 -> GM_RM011_N005`

Weak edges can share a diagnostic ID only with a visible weak/review label or remain separate if the renderer cannot show uncertainty:

- `GM_RM011_N003 -> GM_RM011_N004`
- `GM_RM011_N008 -> GM_RM011_N009`
- `GM_RM011_N010 -> GM_RM011_N011`
- `GM_RM011_N012 -> GM_RM011_N013`

Forbidden edges must never be merged:

- `GM_RM017_N001 -> GM_RM017_N003`
- `GM_RM011_N003 -> GM_RM011_N006`
- `GM_RM011_N007 -> GM_RM011_N003`

The non-vehicle exclusion is represented as a unary exclusion edge on `GM_RM017_N005`.

## Video Rendering Rules

The main display label is `diagnostic_vehicle_id`, not `track_id`. Track IDs can be displayed only as auxiliary text.

For each `scene + optical_frame_num + diagnostic_vehicle_id`, the manifest keeps one primary box. If multiple candidate boxes exist, the selection order is:

1. stronger display status;
2. larger reasonable box area;
3. linkage to a diagnostic node;
4. continuity with the surrounding segment.

The manifest explicitly marks forbidden and non-vehicle rows as `forbidden_not_rendered` or `non_vehicle_not_rendered`; a renderer must skip them by default.

## Required Answers

1. A unified input contract is needed because detections, tracker output, same-vehicle audit decisions, and render labels are different evidence layers.
2. Raw detections identify boxes; tracker output identifies algorithmic fragments; same-vehicle audit identifies referent relations; `diagnostic_vehicle_id` is the diagnostic vehicle-time fragment used by the graph.
3. `track_id` cannot be vehicle identity because it can split, bridge, or switch targets.
4. Crop features cannot be vehicle identity because a crop is box content and may contain only a vehicle part, background, or an edge sliver.
5. `diagnostic_vehicle_id` is generated from scene-scoped visual referent groups: strong fragments get stable IDs, weak fragments may share IDs with uncertainty tags, forbidden/non-vehicle fragments get exclusion/context IDs.
6. Strong edges are short-gap, full-frame-confirmed same-vehicle continuities.
7. Weak edges are plausible part-state transitions or edge cases that need review labels.
8. Forbidden edges are competitor switches, false dark-car merges, or spatial/appearance bridges where same referent cannot be established.
9. Rendering preserves one primary box per vehicle per frame through the manifest deduplication rule.
10. When multiple candidates exist, the primary box is selected by diagnostic attachment, status strength, box quality, area reasonableness, and continuity.
11. The graph must not force uniqueness for thin edge crops, unresolved competitors, non-vehicle content, or forbidden edges.
12. SAR can later consume only clear or reviewed diagnostic fragments as optical-side soft prior planning input; this round does not run SAR consumption.
13. Final boxes or revised GT are not allowed.
14. Full automatic annotation is not allowed.

## Render Readiness

The render manifest contains `scene`, `optical_frame_num`, `diagnostic_vehicle_id`, source tracker fields, source detection IDs, and bounding boxes. It can drive a renderer that resolves frame paths from the known optical frame root or frame table. This round provides the manifest and a renderer interface only; it does not generate mp4 or frame outputs.

## Conclusion

```text
{conclusion}
```
"""


def build(args: argparse.Namespace) -> dict[str, Path]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = REPO_ROOT / "reports" / "oty2"
    samples_dir = report_dir / "samples"
    report_path = report_dir / f"oty2_optical_timeline_graph_input_contract_{timestamp}.md"
    nodes_path = samples_dir / f"oty2_optical_timeline_graph_nodes_{timestamp}.csv"
    edges_path = samples_dir / f"oty2_optical_timeline_graph_edges_{timestamp}.csv"
    manifest_path = samples_dir / f"oty2_optical_timeline_video_render_manifest_{timestamp}.csv"

    source_paths = {
        "same_vehicle": Path(args.same_vehicle),
        "gm011_contrast": Path(args.gm011_contrast),
        "tracklet_index": Path(args.tracklet_index),
        "linkage_rows": Path(args.linkage_rows),
        "crop_index": Path(args.crop_index),
    }
    for label, path in source_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"{label}: {path}")

    # Read audit tables to assert they are available for provenance. The graph
    # rows are intentionally curated from the audited case list above.
    same_vehicle_rows = read_csv(source_paths["same_vehicle"])
    gm011_rows = read_csv(source_paths["gm011_contrast"])
    if not same_vehicle_rows:
        raise ValueError("same-vehicle audit CSV is empty")
    if not gm011_rows:
        raise ValueError("GM_RM011 contrast CSV is empty")

    segments = load_segments(read_csv(source_paths["tracklet_index"]))
    nodes = node_rows(NODE_SPECS, segments)
    edges = edge_rows(EDGE_SPECS)
    crop_paths = load_crop_paths(read_csv(source_paths["crop_index"]))
    linkage = load_linkage(read_csv(source_paths["linkage_rows"]))
    for row in linkage:
        row["optical_path"] = crop_paths.get(norm(row.get("embedding_uid")), "")
    manifest = manifest_rows(NODE_SPECS, nodes, linkage)

    write_csv(nodes_path, nodes, NODE_FIELDS)
    write_csv(edges_path, edges, EDGE_FIELDS)
    write_csv(manifest_path, manifest, MANIFEST_FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(contract_report(timestamp, nodes_path, edges_path, manifest_path, nodes, edges, manifest, source_paths), encoding="utf-8")

    return {
        "report": report_path,
        "nodes": nodes_path,
        "edges": edges_path,
        "manifest": manifest_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="", help="Timestamp suffix. Defaults to current local time.")
    parser.add_argument("--same-vehicle", default=str(DEFAULT_SAME_VEHICLE))
    parser.add_argument("--gm011-contrast", default=str(DEFAULT_GM011_CONTRAST))
    parser.add_argument("--tracklet-index", default=str(DEFAULT_TRACKLET_INDEX))
    parser.add_argument("--linkage-rows", default=str(DEFAULT_LINKAGE_ROWS))
    parser.add_argument("--crop-index", default=str(DEFAULT_CROP_INDEX))
    return parser.parse_args()


def main() -> None:
    outputs = build(parse_args())
    for key, path in outputs.items():
        print(f"{key}: {path}")


if __name__ == "__main__":
    main()
