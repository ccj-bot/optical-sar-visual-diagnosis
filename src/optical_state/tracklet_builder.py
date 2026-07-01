"""Deterministic optical tracklet candidate construction helpers.

The helpers in this module only consume OTY0 YOLO detection geometry and
detector fields. They do not consume GT, final/manual/oracle labels, SAR
evidence, review status, or selector outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import median
from typing import Any, Mapping, Sequence

from .state_features import (
    BBox,
    bbox_from_row,
    bbox_iou,
    boundary_contact_features,
    center_distance,
    compute_state_features,
    neighbor_context,
    parse_float,
    parse_int,
    size_consistency,
)


@dataclass(frozen=True)
class TrackletAuditLimits:
    """Audit limits for geometry-only candidate construction."""

    max_frame_gap: int = 4
    scan_frame_gap: int = 8
    max_center_distance_px: float = 260.0
    min_size_consistency: float = 0.35
    max_edges_per_detection: int = 5
    neighbor_distance_px: float = 120.0
    contact_margin_px: float = 2.0
    min_tracklet_length: int = 3
    high_confidence_min_detections: int = 8
    high_confidence_max_frame_gap: int = 2


class UnionFind:
    def __init__(self, items: Sequence[str]) -> None:
        self.parent = {str(item): str(item) for item in items}

    def find(self, item: str) -> str:
        item = str(item)
        parent = self.parent.setdefault(item, item)
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def normalize_detections(
    rows: Sequence[Mapping[str, Any]],
    frame_sizes: Mapping[str, tuple[int, int] | None] | None = None,
    scene: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize OTY0 rows into runtime-safe detection dictionaries."""

    out: list[dict[str, Any]] = []
    frame_sizes = frame_sizes or {}
    for index, row in enumerate(rows, start=1):
        row_scene = str(row.get("scene", "") or scene or "").strip()
        if scene and row_scene != scene:
            continue
        frame_num = parse_int(row.get("optical_frame_num"))
        bbox = bbox_from_row(row)
        if frame_num is None or bbox is None:
            continue
        optical_path = str(row.get("optical_path", "") or "").strip()
        size = frame_sizes.get(optical_path)
        frame_width = float(size[0]) if size else None
        frame_height = float(size[1]) if size else None
        det_id = str(row.get("det_id", "") or "").strip() or f"{row_scene}_{frame_num:06d}_{index:03d}"
        out.append(
            {
                "scene": row_scene,
                "optical_frame_num": frame_num,
                "optical_path": optical_path,
                "det_id": det_id,
                "class_id": str(row.get("class_id", "") or "").strip(),
                "class_name": str(row.get("class_name", "") or "").strip(),
                "confidence": parse_float(row.get("confidence")),
                "bbox": bbox,
                "frame_width": frame_width,
                "frame_height": frame_height,
                "frame_size_status": "available_from_optical_path" if size else "missing_frame_size",
            }
        )
    return sorted(out, key=lambda item: (item["scene"], item["optical_frame_num"], item["det_id"]))


def same_frame_boxes(detections: Sequence[dict[str, Any]]) -> dict[tuple[str, int], list[BBox]]:
    grouped: dict[tuple[str, int], list[BBox]] = {}
    for det in detections:
        grouped.setdefault((str(det["scene"]), int(det["optical_frame_num"])), []).append(det["bbox"])
    return grouped


def neighbor_facts(
    detections: Sequence[dict[str, Any]],
    limits: TrackletAuditLimits,
) -> dict[str, dict[str, Any]]:
    boxes_by_frame = same_frame_boxes(detections)
    out: dict[str, dict[str, Any]] = {}
    for det in detections:
        out[str(det["det_id"])] = neighbor_context(
            det["bbox"],
            boxes_by_frame.get((str(det["scene"]), int(det["optical_frame_num"])), []),
            limits.neighbor_distance_px,
        )
    return out


def _class_consistent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_name = str(left.get("class_name", "") or "").strip()
    right_name = str(right.get("class_name", "") or "").strip()
    if left_name and right_name:
        return left_name == right_name
    left_id = str(left.get("class_id", "") or "").strip()
    right_id = str(right.get("class_id", "") or "").strip()
    return bool(left_id and right_id and left_id == right_id)


def _ratio_delta(next_value: float | None, previous_value: float | None) -> float | str:
    if next_value is None or previous_value is None or previous_value == 0:
        return ""
    return (next_value - previous_value) / previous_value


def _edge_status(
    gap: int,
    class_consistent: bool,
    distance: float,
    distance_limit: float,
    size_score: float,
    limits: TrackletAuditLimits,
) -> tuple[bool, str]:
    if gap > limits.max_frame_gap:
        return False, "gap_too_large"
    if not class_consistent:
        return False, "class_mismatch"
    if distance > distance_limit:
        return False, "outside_distance_limit"
    if size_score < limits.min_size_consistency:
        return False, "outside_size_limit"
    return True, "within_audit_limits"


def build_candidate_edges(
    detections: Sequence[dict[str, Any]],
    limits: TrackletAuditLimits,
) -> list[dict[str, Any]]:
    """Build runtime-safe geometry-only candidate edges."""

    neighbors = neighbor_facts(detections, limits)
    raw_by_source: dict[str, list[dict[str, Any]]] = {}
    within_outgoing: dict[str, int] = {}
    within_incoming: dict[str, int] = {}

    ordered = sorted(detections, key=lambda item: (item["scene"], item["optical_frame_num"], item["det_id"]))
    for source in ordered:
        source_id = str(source["det_id"])
        raw_by_source[source_id] = []
        for target in ordered:
            if source["scene"] != target["scene"] or source["det_id"] == target["det_id"]:
                continue
            gap = int(target["optical_frame_num"]) - int(source["optical_frame_num"])
            if gap <= 0 or gap > limits.scan_frame_gap:
                continue

            source_bbox: BBox = source["bbox"]
            target_bbox: BBox = target["bbox"]
            distance = center_distance(source_bbox, target_bbox)
            distance_limit = limits.max_center_distance_px * sqrt(max(1, gap))
            iou = bbox_iou(source_bbox, target_bbox)
            size_score = size_consistency(source_bbox, target_bbox)
            class_ok = _class_consistent(source, target)
            within, status = _edge_status(gap, class_ok, distance, distance_limit, size_score, limits)

            area_change_ratio = _ratio_delta(target_bbox.area, source_bbox.area)
            aspect_change_ratio = _ratio_delta(target_bbox.aspect, source_bbox.aspect)
            distance_score = 1.0 / (1.0 + distance / max(distance_limit, 1.0))
            gap_score = 1.0 / gap
            iou_score = min(1.0, iou * 4.0)
            conf_values = [value for value in (source.get("confidence"), target.get("confidence")) if value is not None]
            conf_min = min(conf_values) if conf_values else ""
            conf_score = float(conf_min) if conf_min != "" else 0.0
            audit_score = (distance_score + size_score + iou_score + gap_score + conf_score) / 5.0

            if within:
                within_outgoing[source_id] = within_outgoing.get(source_id, 0) + 1
                target_id = str(target["det_id"])
                within_incoming[target_id] = within_incoming.get(target_id, 0) + 1

            from_neighbor = neighbors.get(source_id, {})
            to_neighbor = neighbors.get(str(target["det_id"]), {})
            raw_by_source[source_id].append(
                {
                    "edge_id": f"{source_id}__{target['det_id']}",
                    "edge_kind": "tracklet_candidate_edge",
                    "from_det_id": source_id,
                    "to_det_id": str(target["det_id"]),
                    "scene": source["scene"],
                    "from_optical_frame_num": source["optical_frame_num"],
                    "to_optical_frame_num": target["optical_frame_num"],
                    "optical_frame_gap": gap,
                    "from_class_name": source.get("class_name", ""),
                    "to_class_name": target.get("class_name", ""),
                    "class_consistent": class_ok,
                    "center_distance_px": distance,
                    "center_distance_limit_px": distance_limit,
                    "bbox_iou": iou,
                    "size_consistency": size_score,
                    "area_change_ratio": area_change_ratio,
                    "aspect_change_ratio": aspect_change_ratio,
                    "confidence_pair_min": conf_min,
                    "neighbor_ambiguity_from": from_neighbor.get("neighbor_ambiguity_proxy", ""),
                    "neighbor_ambiguity_to": to_neighbor.get("neighbor_ambiguity_proxy", ""),
                    "edge_audit_score_not_selector": audit_score,
                    "edge_within_audit_limits": within,
                    "edge_status": status,
                    "source_within_candidate_count": "",
                    "target_within_candidate_count": "",
                    "candidate_rank_for_source_detection": "",
                    "edge_selected_for_component": False,
                    "edge_policy": "runtime_yolo_bbox_geometry_only_candidate_edge_not_same_target_proof",
                }
            )

    out: list[dict[str, Any]] = []
    for source_id, candidates in raw_by_source.items():
        candidates.sort(
            key=lambda item: (
                not bool(item["edge_within_audit_limits"]),
                item["optical_frame_gap"],
                item["center_distance_px"],
                -item["bbox_iou"],
                -item["size_consistency"],
                -item["edge_audit_score_not_selector"],
            )
        )
        for rank, edge in enumerate(candidates[: limits.max_edges_per_detection], start=1):
            edge["candidate_rank_for_source_detection"] = rank
            edge["source_within_candidate_count"] = within_outgoing.get(source_id, 0)
            edge["target_within_candidate_count"] = within_incoming.get(str(edge["to_det_id"]), 0)
            if edge["edge_within_audit_limits"] and (
                int(edge["source_within_candidate_count"]) > 1
                or int(edge["target_within_candidate_count"]) > 1
            ):
                edge["edge_status"] = "ambiguous_multiple_candidates"
            out.append(edge)
    return out


def _better_edge(left: Mapping[str, Any], right: Mapping[str, Any] | None) -> bool:
    if right is None:
        return True
    return (
        float(left.get("edge_audit_score_not_selector") or 0.0),
        -int(left.get("optical_frame_gap") or 9999),
        -float(left.get("center_distance_px") or 1e12),
    ) > (
        float(right.get("edge_audit_score_not_selector") or 0.0),
        -int(right.get("optical_frame_gap") or 9999),
        -float(right.get("center_distance_px") or 1e12),
    )


def select_component_edges(edges: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_source: dict[str, dict[str, Any]] = {}
    for edge in edges:
        if not edge.get("edge_within_audit_limits"):
            continue
        source_id = str(edge.get("from_det_id", ""))
        if _better_edge(edge, best_by_source.get(source_id)):
            best_by_source[source_id] = edge

    best_by_target: dict[str, dict[str, Any]] = {}
    for edge in best_by_source.values():
        target_id = str(edge.get("to_det_id", ""))
        if _better_edge(edge, best_by_target.get(target_id)):
            best_by_target[target_id] = edge

    selected_ids = {str(edge["edge_id"]) for edge in best_by_target.values()}
    for edge in edges:
        edge["edge_selected_for_component"] = str(edge.get("edge_id", "")) in selected_ids
    return list(best_by_target.values())


def build_tracklet_components(
    detections: Sequence[dict[str, Any]],
    edges: list[dict[str, Any]],
    limits: TrackletAuditLimits,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Create conservative connected components from selected candidate edges."""

    det_ids = [str(det["det_id"]) for det in detections]
    uf = UnionFind(det_ids)
    selected_edges = select_component_edges(edges)
    for edge in selected_edges:
        uf.union(str(edge["from_det_id"]), str(edge["to_det_id"]))

    root_groups: dict[str, list[dict[str, Any]]] = {}
    for det in detections:
        root_groups.setdefault(uf.find(str(det["det_id"])), []).append(det)

    sorted_groups = sorted(
        root_groups.values(),
        key=lambda group: (
            min(int(det["optical_frame_num"]) for det in group),
            min(str(det["det_id"]) for det in group),
        ),
    )

    selected_by_component_det = {
        str(edge["from_det_id"]): edge for edge in selected_edges
    } | {
        str(edge["to_det_id"]): edge for edge in selected_edges
    }
    neighbors = neighbor_facts(detections, limits)
    assignments: dict[str, str] = {}
    rows: list[dict[str, Any]] = []

    for idx, group in enumerate(sorted_groups, start=1):
        tracklet_id = f"oty1_tracklet_{idx:04d}"
        for det in group:
            assignments[str(det["det_id"])] = tracklet_id
        ordered = sorted(group, key=lambda item: (int(item["optical_frame_num"]), str(item["det_id"])))
        frames = [int(det["optical_frame_num"]) for det in ordered]
        unique_frames = sorted(set(frames))
        frame_gaps = [b - a for a, b in zip(unique_frames, unique_frames[1:])]
        speeds = []
        area_changes = []
        for left, right in zip(ordered, ordered[1:]):
            gap = int(right["optical_frame_num"]) - int(left["optical_frame_num"])
            if gap <= 0:
                continue
            speeds.append(center_distance(left["bbox"], right["bbox"]) / gap)
            if left["bbox"].area > 0:
                area_changes.append(abs((right["bbox"].area - left["bbox"].area) / left["bbox"].area))

        frame_counts: dict[int, int] = {}
        for frame in frames:
            frame_counts[frame] = frame_counts.get(frame, 0) + 1
        same_frame_conflicts = sum(max(0, count - 1) for count in frame_counts.values())
        group_ids = {str(det["det_id"]) for det in group}
        edge_conflict_det_ids = set()
        for edge in edges:
            if str(edge.get("from_det_id")) in group_ids and int(edge.get("source_within_candidate_count") or 0) > 1:
                edge_conflict_det_ids.add(str(edge.get("from_det_id")))
            if str(edge.get("to_det_id")) in group_ids and int(edge.get("target_within_candidate_count") or 0) > 1:
                edge_conflict_det_ids.add(str(edge.get("to_det_id")))

        neighbor_ambiguity_count = sum(
            1 for det in group if neighbors.get(str(det["det_id"]), {}).get("neighbor_ambiguity_proxy") is True
        )
        boundary_contact_count = 0
        for det in group:
            contact = boundary_contact_features(
                det["bbox"],
                det.get("frame_width"),
                det.get("frame_height"),
                limits.contact_margin_px,
            )
            if contact.get("touch_any") is True:
                boundary_contact_count += 1

        detection_count = len(group)
        max_frame_gap = max(frame_gaps) if frame_gaps else 0
        missing_gap_count = sum(1 for gap in frame_gaps if gap > 1)
        if detection_count < limits.min_tracklet_length:
            identity_status = "fragmented_short_track"
            tracklet_status = "fragmented_short_track"
        elif same_frame_conflicts > 0:
            identity_status = "ambiguous_crossing_risk"
            tracklet_status = "same_frame_identity_conflict_review"
        elif edge_conflict_det_ids or neighbor_ambiguity_count > 0:
            identity_status = "ambiguous_crossing_risk"
            tracklet_status = "ambiguous_geometry_review"
        elif (
            detection_count >= limits.high_confidence_min_detections
            and max_frame_gap <= limits.high_confidence_max_frame_gap
            and missing_gap_count == 0
        ):
            identity_status = "high_confidence_geometry_only"
            tracklet_status = "high_confidence_geometry_only"
        else:
            identity_status = "geometry_consistent_but_unverified"
            tracklet_status = "candidate_component_built"

        rows.append(
            {
                "tracklet_candidate_id": tracklet_id,
                "scene": ordered[0]["scene"] if ordered else "",
                "detection_count": detection_count,
                "frame_start": min(frames) if frames else "",
                "frame_end": max(frames) if frames else "",
                "frame_span": (max(frames) - min(frames) + 1) if frames else "",
                "missing_frame_gap_count": missing_gap_count,
                "max_frame_gap": max_frame_gap,
                "mean_center_speed": sum(speeds) / len(speeds) if speeds else "",
                "median_center_speed": median(speeds) if speeds else "",
                "mean_area_change_abs": sum(area_changes) / len(area_changes) if area_changes else "",
                "edge_conflict_count": len(edge_conflict_det_ids),
                "same_frame_conflict_count": same_frame_conflicts,
                "neighbor_ambiguity_count": neighbor_ambiguity_count,
                "boundary_contact_count": boundary_contact_count,
                "selected_edge_count": sum(
                    1
                    for edge in selected_edges
                    if str(edge.get("from_det_id")) in group_ids and str(edge.get("to_det_id")) in group_ids
                ),
                "tracklet_status": tracklet_status,
                "identity_status": identity_status,
                "policy": "connected_component_from_selected_runtime_yolo_geometry_edges_not_confirmed_identity",
            }
        )
    return rows, assignments


def compute_tracklet_state_timeseries(
    detections: Sequence[dict[str, Any]],
    components: Sequence[Mapping[str, Any]],
    assignments: Mapping[str, str],
    limits: TrackletAuditLimits,
) -> list[dict[str, Any]]:
    component_by_id = {str(row["tracklet_candidate_id"]): row for row in components}
    detections_by_component: dict[str, list[dict[str, Any]]] = {}
    for det in detections:
        component_id = assignments.get(str(det["det_id"]), f"oty1_singleton_{det['det_id']}")
        detections_by_component.setdefault(component_id, []).append(det)
    boxes_by_frame = same_frame_boxes(detections)
    rows: list[dict[str, Any]] = []

    for component_id, group in sorted(detections_by_component.items()):
        ordered = sorted(group, key=lambda item: (int(item["optical_frame_num"]), str(item["det_id"])))
        component = component_by_id.get(component_id, {})
        identity_status = str(component.get("identity_status", "candidate_only"))
        for idx, det in enumerate(ordered):
            prev_det = ordered[idx - 1] if idx > 0 else None
            next_det = ordered[idx + 1] if idx + 1 < len(ordered) else None
            state = compute_state_features(
                det["bbox"],
                det.get("frame_width"),
                det.get("frame_height"),
                boxes_by_frame.get((str(det["scene"]), int(det["optical_frame_num"])), []),
                previous_bbox=prev_det["bbox"] if prev_det else None,
                previous_frame_num=int(prev_det["optical_frame_num"]) if prev_det else None,
                current_frame_num=int(det["optical_frame_num"]),
                next_bbox=next_det["bbox"] if next_det else None,
                contact_margin_px=limits.contact_margin_px,
                neighbor_distance_px=limits.neighbor_distance_px,
            )
            if identity_status == "ambiguous_crossing_risk":
                state_status = "ambiguous_tracklet_state_review"
            elif identity_status == "fragmented_short_track":
                state_status = "fragmented_short_track_state"
            elif state.get("touch_any") is True:
                state_status = "boundary_contact_state_review"
            else:
                state_status = "runtime_geometry_state"
            rows.append(
                {
                    "tracklet_candidate_id": component_id,
                    "scene": det["scene"],
                    "det_id": det["det_id"],
                    "optical_frame_num": det["optical_frame_num"],
                    "optical_path": det.get("optical_path", ""),
                    "class_name": det.get("class_name", ""),
                    "confidence": det.get("confidence", ""),
                    "frame_width": det.get("frame_width", ""),
                    "frame_height": det.get("frame_height", ""),
                    **state,
                    "state_status": state_status,
                    "identity_status": identity_status,
                    "state_source_policy": "oty1_runtime_from_oty0_yolo_detections_only_no_gt_review_sar",
                }
            )
    return rows


def build_quality_audit_rows(components: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in components:
        notes: list[str] = []
        if str(row.get("identity_status")) == "fragmented_short_track":
            notes.append("short component; keep candidate-only")
        if int(row.get("same_frame_conflict_count") or 0) > 0:
            notes.append("same-frame detection conflict inside component")
        if int(row.get("edge_conflict_count") or 0) > 0:
            notes.append("multiple plausible geometry edges")
        if int(row.get("neighbor_ambiguity_count") or 0) > 0:
            notes.append("near same-frame neighbors")
        if int(row.get("boundary_contact_count") or 0) > 0:
            notes.append("boundary contact/truncation proxy review")
        rows.append(
            {
                "tracklet_candidate_id": row.get("tracklet_candidate_id", ""),
                "scene": row.get("scene", ""),
                "detection_count": row.get("detection_count", ""),
                "tracklet_status": row.get("tracklet_status", ""),
                "identity_status": row.get("identity_status", ""),
                "edge_conflict_count": row.get("edge_conflict_count", ""),
                "same_frame_conflict_count": row.get("same_frame_conflict_count", ""),
                "neighbor_ambiguity_count": row.get("neighbor_ambiguity_count", ""),
                "boundary_contact_count": row.get("boundary_contact_count", ""),
                "quality_notes": "; ".join(notes) if notes else "geometry-only candidate; no runtime identity proof",
                "policy": "quality_audit_only_not_selector_not_sar_annotation_ranking",
            }
        )
    return rows
