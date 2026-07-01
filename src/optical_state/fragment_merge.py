"""Fragment merge candidate audit helpers for OTY1a.

OTY1a starts from OTY1 optical tracklet candidate outputs. It proposes
fragment-merge review candidates using runtime-safe optical geometry only.
It does not confirm identity and does not use SAR, GT, final, manual, oracle,
review, selector, G2, A008, threshold, or training signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from statistics import median
from typing import Any, Mapping, Sequence

from .state_features import BBox, bbox_iou, center_distance, parse_float, parse_int


MERGE_POSITIVE_STATUSES = {
    "fragment_merge_candidate",
    "overlap_shape_transition_candidate",
    "partial_to_full_box_transition_candidate",
    "ambiguous_competing_merge",
    "needs_visual_review",
}


@dataclass(frozen=True)
class FragmentMergeLimits:
    endpoint_k: int = 3
    max_forward_gap: int = 8
    max_scan_forward_gap: int = 24
    max_endpoint_distance_px: float = 320.0
    max_motion_predicted_distance_px: float = 360.0
    min_area_ratio: float = 0.18
    min_aspect_ratio: float = 0.18
    shape_transition_area_ratio: float = 0.75
    shape_transition_aspect_ratio: float = 0.65
    partial_full_bridge_iou: float = 0.20
    min_fragment_score: float = 0.48
    min_review_score: float = 0.34


def bbox_from_state_row(row: Mapping[str, Any]) -> BBox | None:
    x1 = parse_float(row.get("bbox_x1"))
    y1 = parse_float(row.get("bbox_y1"))
    x2 = parse_float(row.get("bbox_x2"))
    y2 = parse_float(row.get("bbox_y2"))
    if None in (x1, y1, x2, y2):
        return None
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    return BBox(x1, y1, x2, y2)


def safe_ratio(left: float | None, right: float | None) -> float | str:
    if left is None or right is None or left <= 0 or right <= 0:
        return ""
    return min(left, right) / max(left, right)


def _mean(values: Sequence[float]) -> float | str:
    return sum(values) / len(values) if values else ""


def _median(values: Sequence[float]) -> float | str:
    return median(values) if values else ""


def _bool_count(rows: Sequence[Mapping[str, Any]], field: str) -> int:
    count = 0
    for row in rows:
        value = str(row.get(field, "")).lower()
        if value == "true" or row.get(field) is True:
            count += 1
    return count


def _mode_text(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field, "") or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _endpoint_velocity(rows: Sequence[Mapping[str, Any]], at_end: bool) -> tuple[float | str, float | str]:
    ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
    if len(ordered) < 2:
        return "", ""
    left, right = (ordered[-2], ordered[-1]) if at_end else (ordered[0], ordered[1])
    left_frame = parse_int(left.get("optical_frame_num"))
    right_frame = parse_int(right.get("optical_frame_num"))
    if left_frame is None or right_frame is None or right_frame <= left_frame:
        return "", ""
    left_x = parse_float(left.get("bbox_center_x"))
    left_y = parse_float(left.get("bbox_center_y"))
    right_x = parse_float(right.get("bbox_center_x"))
    right_y = parse_float(right.get("bbox_center_y"))
    if None in (left_x, left_y, right_x, right_y):
        return "", ""
    assert left_x is not None and left_y is not None and right_x is not None and right_y is not None
    gap = right_frame - left_frame
    return (right_x - left_x) / gap, (right_y - left_y) / gap


def _endpoint_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    centers_x = [value for value in (parse_float(row.get("bbox_center_x")) for row in rows) if value is not None]
    centers_y = [value for value in (parse_float(row.get("bbox_center_y")) for row in rows) if value is not None]
    areas = [value for value in (parse_float(row.get("bbox_area")) for row in rows) if value is not None]
    aspects = [value for value in (parse_float(row.get("bbox_aspect")) for row in rows) if value is not None]
    bottoms = []
    confidences = []
    for row in rows:
        bbox = bbox_from_state_row(row)
        if bbox is not None:
            bottoms.append(bbox.y2)
        confidence = parse_float(row.get("confidence"))
        if confidence is not None:
            confidences.append(confidence)
    return {
        "center_x_mean": _mean(centers_x),
        "center_y_mean": _mean(centers_y),
        "area_median": _median(areas),
        "aspect_median": _median(aspects),
        "bottom_y_median": _median(bottoms),
        "confidence_min": min(confidences) if confidences else "",
        "confidence_median": _median(confidences),
        "boundary_contact_count": _bool_count(rows, "touch_any"),
        "neighbor_ambiguity_count": _bool_count(rows, "neighbor_ambiguity_proxy"),
        "class_name": _mode_text(rows, "class_name"),
    }


def build_component_profiles(
    components: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, Any]],
    limits: FragmentMergeLimits,
) -> dict[str, dict[str, Any]]:
    rows_by_component: dict[str, list[Mapping[str, Any]]] = {}
    for row in state_rows:
        component_id = str(row.get("tracklet_candidate_id", "") or "").strip()
        if component_id:
            rows_by_component.setdefault(component_id, []).append(row)
    component_meta = {str(row.get("tracklet_candidate_id", "")): row for row in components}

    profiles: dict[str, dict[str, Any]] = {}
    for component_id, rows in rows_by_component.items():
        ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
        if not ordered:
            continue
        meta = component_meta.get(component_id, {})
        frame_values = [parse_int(row.get("optical_frame_num")) for row in ordered]
        frames = sorted({value for value in frame_values if value is not None})
        if not frames:
            continue
        first_rows = ordered[: limits.endpoint_k]
        last_rows = ordered[-limits.endpoint_k :]
        first_stats = _endpoint_stats(first_rows)
        last_stats = _endpoint_stats(last_rows)
        first_bbox = bbox_from_state_row(ordered[0])
        last_bbox = bbox_from_state_row(ordered[-1])
        first_vx, first_vy = _endpoint_velocity(ordered, at_end=False)
        last_vx, last_vy = _endpoint_velocity(ordered, at_end=True)
        profiles[component_id] = {
            "tracklet_candidate_id": component_id,
            "scene": str(meta.get("scene", ordered[0].get("scene", "")) or ""),
            "detection_count": parse_int(meta.get("detection_count")) or len(ordered),
            "frame_start": frames[0],
            "frame_end": frames[-1],
            "frame_span": (frames[-1] - frames[0] + 1),
            "frame_set": set(frames),
            "identity_status": str(meta.get("identity_status", ordered[0].get("identity_status", "")) or ""),
            "tracklet_status": str(meta.get("tracklet_status", "") or ""),
            "neighbor_ambiguity_count": parse_int(meta.get("neighbor_ambiguity_count")) or 0,
            "boundary_contact_count": parse_int(meta.get("boundary_contact_count")) or 0,
            "missing_frame_gap_count": parse_int(meta.get("missing_frame_gap_count")) or 0,
            "max_frame_gap": parse_int(meta.get("max_frame_gap")) or 0,
            "first_det_id": str(ordered[0].get("det_id", "") or ""),
            "last_det_id": str(ordered[-1].get("det_id", "") or ""),
            "first_optical_path": str(ordered[0].get("optical_path", "") or ""),
            "last_optical_path": str(ordered[-1].get("optical_path", "") or ""),
            "first_bbox": first_bbox,
            "last_bbox": last_bbox,
            "first_velocity_x_px_per_frame": first_vx,
            "first_velocity_y_px_per_frame": first_vy,
            "last_velocity_x_px_per_frame": last_vx,
            "last_velocity_y_px_per_frame": last_vy,
            "first_k_center_x_mean": first_stats["center_x_mean"],
            "first_k_center_y_mean": first_stats["center_y_mean"],
            "first_k_area_median": first_stats["area_median"],
            "first_k_aspect_median": first_stats["aspect_median"],
            "first_k_bottom_y_median": first_stats["bottom_y_median"],
            "first_k_confidence_min": first_stats["confidence_min"],
            "first_k_confidence_median": first_stats["confidence_median"],
            "first_k_boundary_contact_count": first_stats["boundary_contact_count"],
            "first_k_neighbor_ambiguity_count": first_stats["neighbor_ambiguity_count"],
            "first_k_class_name": first_stats["class_name"],
            "last_k_center_x_mean": last_stats["center_x_mean"],
            "last_k_center_y_mean": last_stats["center_y_mean"],
            "last_k_area_median": last_stats["area_median"],
            "last_k_aspect_median": last_stats["aspect_median"],
            "last_k_bottom_y_median": last_stats["bottom_y_median"],
            "last_k_confidence_min": last_stats["confidence_min"],
            "last_k_confidence_median": last_stats["confidence_median"],
            "last_k_boundary_contact_count": last_stats["boundary_contact_count"],
            "last_k_neighbor_ambiguity_count": last_stats["neighbor_ambiguity_count"],
            "last_k_class_name": last_stats["class_name"],
            "rows": ordered,
        }
    return profiles


def component_review_rows(profiles: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "tracklet_candidate_id",
        "scene",
        "detection_count",
        "frame_start",
        "frame_end",
        "frame_span",
        "identity_status",
        "tracklet_status",
        "neighbor_ambiguity_count",
        "boundary_contact_count",
        "missing_frame_gap_count",
        "max_frame_gap",
        "first_det_id",
        "last_det_id",
        "first_k_center_x_mean",
        "first_k_center_y_mean",
        "first_k_area_median",
        "first_k_aspect_median",
        "first_k_bottom_y_median",
        "first_k_confidence_min",
        "last_k_center_x_mean",
        "last_k_center_y_mean",
        "last_k_area_median",
        "last_k_aspect_median",
        "last_k_bottom_y_median",
        "last_k_confidence_min",
        "first_velocity_x_px_per_frame",
        "first_velocity_y_px_per_frame",
        "last_velocity_x_px_per_frame",
        "last_velocity_y_px_per_frame",
    ]
    rows: list[dict[str, Any]] = []
    for profile in sorted(profiles.values(), key=lambda item: (item.get("scene", ""), item.get("frame_start", 0), item.get("tracklet_candidate_id", ""))):
        rows.append({field: profile.get(field, "") for field in fields})
    return rows


def _predict_center(profile: Mapping[str, Any], target_frame: int) -> tuple[float, float] | None:
    bbox = profile.get("last_bbox")
    if not isinstance(bbox, BBox):
        return None
    vx = parse_float(profile.get("last_velocity_x_px_per_frame"))
    vy = parse_float(profile.get("last_velocity_y_px_per_frame"))
    frame_end = parse_int(profile.get("frame_end"))
    if vx is None or vy is None or frame_end is None:
        return (bbox.cx, bbox.cy)
    gap = max(0, target_frame - frame_end)
    return bbox.cx + vx * gap, bbox.cy + vy * gap


def _nearest_frame_iou(left: Mapping[str, Any], right: Mapping[str, Any]) -> float | str:
    left_rows = list(left.get("rows", []))
    right_rows = list(right.get("rows", []))
    left_by_frame: dict[int, list[BBox]] = {}
    right_by_frame: dict[int, list[BBox]] = {}
    for row in left_rows:
        frame = parse_int(row.get("optical_frame_num"))
        bbox = bbox_from_state_row(row)
        if frame is not None and bbox is not None:
            left_by_frame.setdefault(frame, []).append(bbox)
    for row in right_rows:
        frame = parse_int(row.get("optical_frame_num"))
        bbox = bbox_from_state_row(row)
        if frame is not None and bbox is not None:
            right_by_frame.setdefault(frame, []).append(bbox)
    shared = sorted(set(left_by_frame) & set(right_by_frame))
    if shared:
        values = [
            bbox_iou(left_box, right_box)
            for frame in shared
            for left_box in left_by_frame[frame]
            for right_box in right_by_frame[frame]
        ]
        return max(values) if values else ""
    left_bbox = left.get("last_bbox")
    right_bbox = right.get("first_bbox")
    if isinstance(left_bbox, BBox) and isinstance(right_bbox, BBox):
        return bbox_iou(left_bbox, right_bbox)
    return ""


def _temporal_relation(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, int, int]:
    left_start = parse_int(left.get("frame_start")) or 0
    left_end = parse_int(left.get("frame_end")) or 0
    right_start = parse_int(right.get("frame_start")) or 0
    right_end = parse_int(right.get("frame_end")) or 0
    overlap_frames = set(left.get("frame_set", set())) & set(right.get("frame_set", set()))
    if left_end < right_start:
        return "forward_gap", right_start - left_end, 0
    if left_start <= right_start <= left_end or right_start <= left_start <= right_end:
        return "overlap_or_interleave", right_start - left_end, len(overlap_frames)
    return "reverse_or_disjoint", right_start - left_end, len(overlap_frames)


def _class_consistent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_class = str(left.get("last_k_class_name") or left.get("first_k_class_name") or "").strip()
    right_class = str(right.get("first_k_class_name") or right.get("last_k_class_name") or "").strip()
    return not left_class or not right_class or left_class == right_class


def _confidence_min(left: Mapping[str, Any], right: Mapping[str, Any]) -> float | str:
    values = []
    for value in (left.get("last_k_confidence_min"), right.get("first_k_confidence_min")):
        parsed = parse_float(value)
        if parsed is not None:
            values.append(parsed)
    return min(values) if values else ""


def _score(
    frame_gap: int,
    center_distance: float | str,
    motion_distance: float | str,
    bridge_iou: float | str,
    area_ratio: float | str,
    aspect_ratio: float | str,
    bottom_delta: float | str,
    confidence_min: float | str,
    limits: FragmentMergeLimits,
) -> float:
    positive_gap = max(0, frame_gap)
    temporal_score = 1.0 / (1.0 + positive_gap / max(1, limits.max_forward_gap))
    center_score = 0.0 if center_distance == "" else 1.0 / (1.0 + float(center_distance) / limits.max_endpoint_distance_px)
    motion_score = 0.0 if motion_distance == "" else 1.0 / (1.0 + float(motion_distance) / limits.max_motion_predicted_distance_px)
    iou_score = float(bridge_iou) if bridge_iou != "" else 0.0
    area_score = float(area_ratio) if area_ratio != "" else 0.0
    aspect_score = float(aspect_ratio) if aspect_ratio != "" else 0.0
    bottom_score = 0.0 if bottom_delta == "" else 1.0 / (1.0 + float(bottom_delta) / 220.0)
    confidence_score = float(confidence_min) if confidence_min != "" else 0.0
    return (
        temporal_score
        + center_score
        + motion_score
        + min(1.0, iou_score * 1.4)
        + area_score
        + aspect_score
        + bottom_score
        + confidence_score
    ) / 8.0


def _shape_transition_proxy(area_ratio: float | str, aspect_ratio: float | str) -> str:
    area = float(area_ratio) if area_ratio != "" else 0.0
    aspect = float(aspect_ratio) if aspect_ratio != "" else 0.0
    if area and aspect and (area < 0.45 or aspect < 0.45):
        return "large_shape_transition_review"
    if area and area < 0.75:
        return "area_transition_review"
    if aspect and aspect < 0.65:
        return "aspect_transition_review"
    return "stable_or_minor_shape_change"


def _partial_to_full_proxy(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    area_ratio: float | str,
    aspect_ratio: float | str,
    bridge_iou: float | str,
    limits: FragmentMergeLimits,
) -> str:
    area = float(area_ratio) if area_ratio != "" else 0.0
    aspect = float(aspect_ratio) if aspect_ratio != "" else 0.0
    iou = float(bridge_iou) if bridge_iou != "" else 0.0
    boundary_present = (parse_int(left.get("boundary_contact_count")) or 0) > 0 or (
        parse_int(right.get("boundary_contact_count")) or 0
    ) > 0
    shape_shift = (area and area < limits.shape_transition_area_ratio) or (
        aspect and aspect < limits.shape_transition_aspect_ratio
    )
    if boundary_present and shape_shift and iou >= limits.partial_full_bridge_iou:
        return "partial_to_full_box_transition_review"
    if boundary_present and shape_shift:
        return "partial_to_full_low_overlap_review"
    return "not_indicated"


def _base_status(
    temporal_relation: str,
    frame_gap: int,
    center_distance_px: float | str,
    motion_predicted_center_distance_px: float | str,
    bridge_iou: float | str,
    area_ratio_endpoint: float | str,
    aspect_ratio_endpoint: float | str,
    class_consistent: bool,
    shape_transition_proxy: str,
    partial_to_full_proxy: str,
    score: float,
    limits: FragmentMergeLimits,
) -> str:
    if not class_consistent:
        return "reject_class_mismatch"
    if frame_gap > limits.max_forward_gap:
        return "reject_gap_too_large"
    center = float(center_distance_px) if center_distance_px != "" else 1e9
    motion = (
        float(motion_predicted_center_distance_px)
        if motion_predicted_center_distance_px != ""
        else center
    )
    iou = float(bridge_iou) if bridge_iou != "" else 0.0
    if center > limits.max_endpoint_distance_px and motion > limits.max_motion_predicted_distance_px and iou < 0.10:
        return "reject_motion_inconsistent"
    area = float(area_ratio_endpoint) if area_ratio_endpoint != "" else 0.0
    aspect = float(aspect_ratio_endpoint) if aspect_ratio_endpoint != "" else 0.0
    shape_is_candidate = (
        shape_transition_proxy != "stable_or_minor_shape_change"
        and iou >= limits.partial_full_bridge_iou
    )
    if (area and area < limits.min_area_ratio) or (aspect and aspect < limits.min_aspect_ratio):
        if not shape_is_candidate:
            return "reject_size_aspect_inconsistent"
    if partial_to_full_proxy == "partial_to_full_box_transition_review":
        return "partial_to_full_box_transition_candidate"
    if temporal_relation == "overlap_or_interleave" and shape_transition_proxy != "stable_or_minor_shape_change":
        return "overlap_shape_transition_candidate"
    if score >= limits.min_fragment_score:
        return "fragment_merge_candidate"
    if score >= limits.min_review_score or iou >= 0.15:
        return "needs_visual_review"
    return "reject_motion_inconsistent"


def build_fragment_merge_edges(
    profiles: Mapping[str, Mapping[str, Any]],
    limits: FragmentMergeLimits,
) -> list[dict[str, Any]]:
    profile_list = sorted(
        profiles.values(),
        key=lambda item: (str(item.get("scene", "")), int(item.get("frame_start", 0)), str(item.get("tracklet_candidate_id", ""))),
    )
    rows: list[dict[str, Any]] = []
    for left_index, left in enumerate(profile_list):
        for right in profile_list[left_index + 1 :]:
            if str(left.get("scene", "")) != str(right.get("scene", "")):
                continue
            temporal_relation, frame_gap, overlap_count = _temporal_relation(left, right)
            if temporal_relation == "reverse_or_disjoint":
                continue
            if frame_gap > limits.max_scan_forward_gap:
                # Keep explicit reject rows only inside a bounded review window.
                continue
            left_bbox = left.get("last_bbox")
            right_bbox = right.get("first_bbox")
            if not isinstance(left_bbox, BBox) or not isinstance(right_bbox, BBox):
                continue
            endpoint_distance = center_distance(left_bbox, right_bbox)
            predicted = _predict_center(left, parse_int(right.get("frame_start")) or int(right.get("frame_start", 0)))
            if predicted is None:
                motion_distance: float | str = ""
            else:
                motion_distance = hypot(predicted[0] - right_bbox.cx, predicted[1] - right_bbox.cy)
            bridge_iou = _nearest_frame_iou(left, right)
            area_ratio = safe_ratio(left_bbox.area, right_bbox.area)
            aspect_ratio = safe_ratio(left_bbox.aspect, right_bbox.aspect)
            bottom_delta = abs(left_bbox.y2 - right_bbox.y2)
            class_ok = _class_consistent(left, right)
            conf_min = _confidence_min(left, right)
            shape_proxy = _shape_transition_proxy(area_ratio, aspect_ratio)
            partial_proxy = _partial_to_full_proxy(left, right, area_ratio, aspect_ratio, bridge_iou, limits)
            score = _score(
                frame_gap,
                endpoint_distance,
                motion_distance,
                bridge_iou,
                area_ratio,
                aspect_ratio,
                bottom_delta,
                conf_min,
                limits,
            )
            status = _base_status(
                temporal_relation,
                frame_gap,
                endpoint_distance,
                motion_distance,
                bridge_iou,
                area_ratio,
                aspect_ratio,
                class_ok,
                shape_proxy,
                partial_proxy,
                score,
                limits,
            )
            rows.append(
                {
                    "merge_edge_id": f"{left['tracklet_candidate_id']}__{right['tracklet_candidate_id']}",
                    "scene": left.get("scene", ""),
                    "from_tracklet_candidate_id": left["tracklet_candidate_id"],
                    "to_tracklet_candidate_id": right["tracklet_candidate_id"],
                    "from_frame_start": left.get("frame_start", ""),
                    "from_frame_end": left.get("frame_end", ""),
                    "to_frame_start": right.get("frame_start", ""),
                    "to_frame_end": right.get("frame_end", ""),
                    "temporal_relation": temporal_relation,
                    "frame_gap": frame_gap,
                    "frame_overlap_count": overlap_count,
                    "from_detection_count": left.get("detection_count", ""),
                    "to_detection_count": right.get("detection_count", ""),
                    "endpoint_center_distance_px": endpoint_distance,
                    "motion_predicted_center_distance_px": motion_distance,
                    "bridge_iou_proxy": bridge_iou,
                    "area_ratio_endpoint": area_ratio,
                    "aspect_ratio_endpoint": aspect_ratio,
                    "bottom_y_delta_px": bottom_delta,
                    "class_consistent": class_ok,
                    "confidence_bridge_min": conf_min,
                    "from_boundary_contact_count": left.get("boundary_contact_count", ""),
                    "to_boundary_contact_count": right.get("boundary_contact_count", ""),
                    "from_neighbor_ambiguity_count": left.get("neighbor_ambiguity_count", ""),
                    "to_neighbor_ambiguity_count": right.get("neighbor_ambiguity_count", ""),
                    "shape_transition_proxy": shape_proxy,
                    "partial_to_full_box_transition_proxy": partial_proxy,
                    "competing_merge_count_from": "",
                    "competing_merge_count_to": "",
                    "merge_candidate_score_not_selector": score,
                    "merge_candidate_status": status,
                    "merge_policy": "oty1a_runtime_optical_geometry_only_candidate_not_confirmed_identity",
                }
            )
    counts_from: dict[str, int] = {}
    counts_to: dict[str, int] = {}
    for row in rows:
        if str(row.get("merge_candidate_status", "")) in MERGE_POSITIVE_STATUSES:
            from_id = str(row["from_tracklet_candidate_id"])
            to_id = str(row["to_tracklet_candidate_id"])
            counts_from[from_id] = counts_from.get(from_id, 0) + 1
            counts_to[to_id] = counts_to.get(to_id, 0) + 1
    for row in rows:
        from_id = str(row["from_tracklet_candidate_id"])
        to_id = str(row["to_tracklet_candidate_id"])
        row["competing_merge_count_from"] = counts_from.get(from_id, 0)
        row["competing_merge_count_to"] = counts_to.get(to_id, 0)
        status = str(row["merge_candidate_status"])
        if (
            status in {"fragment_merge_candidate", "needs_visual_review"}
            and (counts_from.get(from_id, 0) > 1 or counts_to.get(to_id, 0) > 1)
        ):
            row["merge_candidate_status"] = "ambiguous_competing_merge"
    return rows


def shape_transition_rows(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for edge in edges:
        status = str(edge.get("merge_candidate_status", ""))
        shape = str(edge.get("shape_transition_proxy", ""))
        partial = str(edge.get("partial_to_full_box_transition_proxy", ""))
        if (
            status in {"overlap_shape_transition_candidate", "partial_to_full_box_transition_candidate"}
            or shape != "stable_or_minor_shape_change"
            or partial != "not_indicated"
        ):
            out.append(dict(edge))
    return out


def edge_status_counts(edges: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        status = str(edge.get("merge_candidate_status", ""))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def count_positive_edges(edges: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for edge in edges if str(edge.get("merge_candidate_status", "")) in MERGE_POSITIVE_STATUSES)
