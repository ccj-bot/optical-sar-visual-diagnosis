"""Observation-cluster and tracker association-choice audits for OTY1t-P3.

The helpers in this module consume runtime-safe optical artifacts only:
OTY0 detections, OTY1 optical state rows, OTY1a optical merge-review context,
and OTY1t tracker assignment rows. Outputs are review-only optical
hypotheses. They do not confirm identity and do not use SAR, GT, final/manual/
oracle/review labels, selector scores, threshold tuning, training signals, or
annotation proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as html_escape
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from .state_features import (
    BBox,
    bbox_iou,
    boundary_contact_features,
    center_distance,
    parse_float,
    parse_int,
)


RUNTIME_SOURCE_POLICY = (
    "oty1t_p3_runtime_safe_oty0_oty1_oty1a_oty1t_optical_only_no_gt_no_sar"
)

CLUSTER_ROLES = {
    "stable_single_box",
    "same_object_duplicate_candidates",
    "partial_full_observation_cluster",
    "ambiguous_multi_vehicle_cluster",
    "edge_truncation_cluster",
    "detector_artifact_cluster",
    "unclassified_observation_cluster",
}

CLUSTER_RISK_STATUSES = {
    "low_risk_single_observation",
    "review_duplicate_or_partial",
    "review_multi_vehicle_ambiguity",
    "review_boundary_truncation",
    "review_detector_artifact",
}

ASSOCIATION_CHOICE_STATUSES = {
    "clean_single_choice",
    "chose_full_over_partial",
    "chose_stable_over_duplicate",
    "chose_tracker_state_over_raw_overlap",
    "possible_wrong_choice",
    "ambiguous_choice_requires_review",
}

BBOX_PROVENANCE_STATUSES = {
    "raw_bbox_preserved",
    "tracker_state_bbox_shift",
    "tracker_state_bbox_scale_change",
    "idx_mapping_suspicious",
    "bbox_provenance_unknown",
}

RECOMMENDED_USES = {
    "do_not_use_for_oty2",
    "optional_uncertainty_hint_only",
    "optional_continuity_hint_with_visual_review",
    "candidate_for_tracklet_stitching_review",
}

OBSERVATION_CLUSTER_FIELDS = [
    "scene",
    "optical_frame_num",
    "observation_cluster_id",
    "cluster_size",
    "det_ids",
    "class_names",
    "confidence_list",
    "bbox_x1_min",
    "bbox_y1_min",
    "bbox_x2_max",
    "bbox_y2_max",
    "cluster_union_area",
    "member_bbox_areas",
    "member_bbox_aspects",
    "member_bottom_y",
    "pairwise_iou_max",
    "pairwise_iou_mean",
    "pairwise_center_distance_min",
    "pairwise_center_distance_mean",
    "boundary_contact_any",
    "neighbor_ambiguity_any",
    "oty1_tracklet_ids",
    "oty1_identity_statuses",
    "tracker_assigned_track_ids",
    "tracked_det_ids",
    "unmatched_det_ids",
    "cluster_role",
    "cluster_risk_status",
    "runtime_source_policy",
]

ASSOCIATION_CHOICE_FIELDS = [
    "scene",
    "optical_frame_num",
    "tracker_name",
    "tracker_track_id",
    "chosen_det_id",
    "chosen_oty1_tracklet_id",
    "chosen_confidence",
    "chosen_raw_bbox_x1",
    "chosen_raw_bbox_y1",
    "chosen_raw_bbox_x2",
    "chosen_raw_bbox_y2",
    "chosen_tracker_bbox_x1",
    "chosen_tracker_bbox_y1",
    "chosen_tracker_bbox_x2",
    "chosen_tracker_bbox_y2",
    "chosen_bbox_area",
    "chosen_boundary_contact",
    "rejected_neighbor_det_ids",
    "rejected_neighbor_oty1_tracklet_ids",
    "rejected_neighbor_confidences",
    "rejected_neighbor_bbox_areas",
    "chosen_vs_rejected_iou_max",
    "chosen_vs_rejected_center_distance_min",
    "chosen_vs_rejected_area_ratio_min",
    "chosen_vs_rejected_area_ratio_max",
    "observation_cluster_id",
    "association_choice_status",
    "association_choice_reason",
    "review_required",
]

BBOX_PROVENANCE_FIELDS = [
    "scene",
    "optical_frame_num",
    "det_id",
    "tracker_name",
    "tracker_track_id",
    "raw_bbox_x1",
    "raw_bbox_y1",
    "raw_bbox_x2",
    "raw_bbox_y2",
    "tracker_output_bbox_x1",
    "tracker_output_bbox_y1",
    "tracker_output_bbox_x2",
    "tracker_output_bbox_y2",
    "center_delta_px",
    "area_delta_ratio",
    "iou_raw_vs_tracker_output",
    "output_idx",
    "mapped_det_id",
    "mapping_verified",
    "bbox_provenance_status",
    "bbox_provenance_reason",
]


@dataclass(frozen=True)
class ObservationClusterConfig:
    scene: str = "GM_RM019"
    tracker_name: str = "bytetrack"
    case_id: str = "0039_0045"
    frame_start: int | None = 149
    frame_end: int | None = 183
    same_class_iou_threshold: float = 0.25
    same_class_center_distance_px: float = 120.0
    containment_threshold: float = 0.50
    contact_margin_px: float = 2.0
    bbox_scale_change_threshold: float = 0.15
    bbox_small_center_delta_px: float = 5.0


def boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def safe_float(value: Any, default: float = 0.0) -> float:
    parsed = parse_float(value)
    return default if parsed is None else parsed


def safe_int(value: Any, default: int = 0) -> int:
    parsed = parse_int(value)
    return default if parsed is None else parsed


def fmt_float(value: Any, digits: int = 6) -> Any:
    parsed = parse_float(value)
    if parsed is None or not isfinite(parsed):
        return ""
    return round(parsed, digits)


def join_values(values: Sequence[Any]) -> str:
    return ";".join(str(value) for value in values if str(value) != "")


def unique_join(values: Sequence[Any]) -> str:
    text_values = sorted({str(value) for value in values if str(value or "").strip()})
    return ";".join(text_values)


def det_short_id(det_id: str) -> str:
    parts = str(det_id).split("_")
    if len(parts) >= 4:
        return f"{parts[-2]}_{parts[-1]}"
    return str(det_id)


def case_tracklet_ids(case_id: str) -> tuple[str, str]:
    left, right = str(case_id or "0039_0045").split("_", 1)
    return f"oty1_tracklet_{left}", f"oty1_tracklet_{right}"


def bbox_from_row(row: Mapping[str, Any], prefix: str = "bbox") -> BBox | None:
    x1 = parse_float(row.get(f"{prefix}_x1"))
    y1 = parse_float(row.get(f"{prefix}_y1"))
    x2 = parse_float(row.get(f"{prefix}_x2"))
    y2 = parse_float(row.get(f"{prefix}_y2"))
    if None in (x1, y1, x2, y2):
        return None
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    return BBox(x1, y1, x2, y2)


def raw_bbox(row: Mapping[str, Any]) -> BBox | None:
    return bbox_from_row(row, "bbox")


def in_scene_frame_window(row: Mapping[str, Any], config: ObservationClusterConfig) -> bool:
    if str(row.get("scene", "") or "") != config.scene:
        return False
    frame = parse_int(row.get("optical_frame_num"))
    if frame is None:
        return False
    if config.frame_start is not None and frame < config.frame_start:
        return False
    if config.frame_end is not None and frame > config.frame_end:
        return False
    return True


def filter_scene_frame_rows(
    rows: Sequence[Mapping[str, Any]], config: ObservationClusterConfig
) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if in_scene_frame_window(row, config)]


def index_by_det(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        det_id = str(row.get("det_id", "") or "").strip()
        if det_id:
            out[det_id] = dict(row)
    return out


def frame_size_for_det(
    det: Mapping[str, Any],
    state_by_det: Mapping[str, Mapping[str, Any]],
) -> tuple[float | None, float | None]:
    det_id = str(det.get("det_id", "") or "")
    state = state_by_det.get(det_id, {})
    width = parse_float(det.get("frame_width")) or parse_float(state.get("frame_width"))
    height = parse_float(det.get("frame_height")) or parse_float(state.get("frame_height"))
    return width, height


def boundary_contact_any(
    det: Mapping[str, Any],
    state_by_det: Mapping[str, Mapping[str, Any]],
    config: ObservationClusterConfig,
) -> bool:
    state = state_by_det.get(str(det.get("det_id", "") or ""), {})
    if "touch_any" in state:
        value = state.get("touch_any")
        if str(value).strip() != "":
            return boolish(value)
    bbox = raw_bbox(det)
    if bbox is None:
        return False
    width, height = frame_size_for_det(det, state_by_det)
    contact = boundary_contact_features(bbox, width, height, config.contact_margin_px)
    return boolish(contact.get("touch_any"))


def containment_ratio(a: BBox, b: BBox) -> float:
    inter_x1 = max(a.x1, b.x1)
    inter_y1 = max(a.y1, b.y1)
    inter_x2 = min(a.x2, b.x2)
    inter_y2 = min(a.y2, b.y2)
    inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
    denominator = min(a.area, b.area)
    if denominator <= 0:
        return 0.0
    return inter_area / denominator


def should_link_observations(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    config: ObservationClusterConfig,
) -> bool:
    if str(left.get("class_name", "") or left.get("class_id", "")) != str(
        right.get("class_name", "") or right.get("class_id", "")
    ):
        return False
    left_box = raw_bbox(left)
    right_box = raw_bbox(right)
    if left_box is None or right_box is None:
        return False
    return (
        bbox_iou(left_box, right_box) >= config.same_class_iou_threshold
        or center_distance(left_box, right_box) <= config.same_class_center_distance_px
        or containment_ratio(left_box, right_box) >= config.containment_threshold
    )


def connected_components(rows: Sequence[Mapping[str, Any]], config: ObservationClusterConfig) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(rows))}
    for left_index, left in enumerate(rows):
        for right_index in range(left_index + 1, len(rows)):
            if should_link_observations(left, rows[right_index], config):
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)
    components: list[list[dict[str, Any]]] = []
    seen: set[int] = set()
    for start in range(len(rows)):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component: list[dict[str, Any]] = []
        while stack:
            index = stack.pop()
            component.append(dict(rows[index]))
            for neighbor in sorted(adjacency[index]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component, key=lambda row: str(row.get("det_id", ""))))
    return components


def pairwise_stats(member_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ious: list[float] = []
    distances: list[float] = []
    boxes = [raw_bbox(row) for row in member_rows]
    valid_boxes = [box for box in boxes if box is not None]
    for left_index, left_box in enumerate(valid_boxes):
        for right_box in valid_boxes[left_index + 1 :]:
            ious.append(bbox_iou(left_box, right_box))
            distances.append(center_distance(left_box, right_box))
    return {
        "pairwise_iou_max": max(ious) if ious else 0.0,
        "pairwise_iou_mean": mean(ious) if ious else 0.0,
        "pairwise_center_distance_min": min(distances) if distances else 0.0,
        "pairwise_center_distance_mean": mean(distances) if distances else 0.0,
    }


def classify_cluster(
    member_rows: Sequence[Mapping[str, Any]],
    state_by_det: Mapping[str, Mapping[str, Any]],
    assignment_by_det: Mapping[str, Mapping[str, Any]],
    config: ObservationClusterConfig,
) -> tuple[str, str]:
    boxes = [raw_bbox(row) for row in member_rows]
    valid_boxes = [box for box in boxes if box is not None]
    if len(member_rows) == 1:
        if boundary_contact_any(member_rows[0], state_by_det, config):
            return "edge_truncation_cluster", "review_boundary_truncation"
        return "stable_single_box", "low_risk_single_observation"

    stats = pairwise_stats(member_rows)
    areas = [box.area for box in valid_boxes if box.area > 0]
    aspects = [box.aspect for box in valid_boxes if box.aspect is not None]
    area_ratio = min(areas) / max(areas) if areas else 1.0
    aspect_ratio = min(aspects) / max(aspects) if aspects else 1.0
    max_aspect = max(aspects) if aspects else 0.0
    boundary_count = sum(1 for row in member_rows if boundary_contact_any(row, state_by_det, config))
    tracklets = {
        str(state_by_det.get(str(row.get("det_id", "")), {}).get("tracklet_candidate_id", "") or "")
        for row in member_rows
    }
    tracklets.discard("")
    unmatched_count = sum(
        1 for row in member_rows if boolish(assignment_by_det.get(str(row.get("det_id", "")), {}).get("is_unmatched_detection"))
    )
    min_confidence = min((safe_float(row.get("confidence"), 1.0) for row in member_rows), default=1.0)

    if boundary_count and (area_ratio < 0.75 or aspect_ratio < 0.65 or max_aspect >= 2.8):
        return "partial_full_observation_cluster", "review_duplicate_or_partial"
    if stats["pairwise_iou_max"] >= 0.50 and area_ratio >= 0.65 and aspect_ratio >= 0.65:
        return "same_object_duplicate_candidates", "review_duplicate_or_partial"
    if len(tracklets) > 1 or unmatched_count:
        return "ambiguous_multi_vehicle_cluster", "review_multi_vehicle_ambiguity"
    if min_confidence < 0.30 and max_aspect >= 2.8:
        return "detector_artifact_cluster", "review_detector_artifact"
    return "unclassified_observation_cluster", "review_multi_vehicle_ambiguity"


def build_same_frame_observation_clusters(
    detection_rows: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    assignment_rows: Sequence[Mapping[str, Any]],
    config: ObservationClusterConfig,
) -> list[dict[str, Any]]:
    state_by_det = index_by_det(oty1_state_rows)
    assignment_by_det = index_by_det(assignment_rows)
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in filter_scene_frame_rows(detection_rows, config):
        frame = parse_int(row.get("optical_frame_num"))
        if frame is None or raw_bbox(row) is None:
            continue
        by_frame.setdefault(frame, []).append(dict(row))

    out: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        components = connected_components(sorted(by_frame[frame], key=lambda row: str(row.get("det_id", ""))), config)
        for index, members in enumerate(components, start=1):
            boxes = [box for box in (raw_bbox(row) for row in members) if box is not None]
            if not boxes:
                continue
            cluster_id = f"{config.scene}_{frame:06d}_oc_{index:03d}"
            det_ids = [str(row.get("det_id", "")) for row in members]
            stats = pairwise_stats(members)
            role, risk = classify_cluster(members, state_by_det, assignment_by_det, config)
            tracked_det_ids = [
                det_id
                for det_id in det_ids
                if str(assignment_by_det.get(det_id, {}).get("tracker_track_id", "") or "").strip()
            ]
            unmatched_det_ids = [
                det_id
                for det_id in det_ids
                if boolish(assignment_by_det.get(det_id, {}).get("is_unmatched_detection"))
            ]
            out.append(
                {
                    "scene": config.scene,
                    "optical_frame_num": frame,
                    "observation_cluster_id": cluster_id,
                    "cluster_size": len(members),
                    "det_ids": join_values(det_ids),
                    "class_names": unique_join([row.get("class_name", "") for row in members]),
                    "confidence_list": join_values([fmt_float(row.get("confidence")) for row in members]),
                    "bbox_x1_min": min(box.x1 for box in boxes),
                    "bbox_y1_min": min(box.y1 for box in boxes),
                    "bbox_x2_max": max(box.x2 for box in boxes),
                    "bbox_y2_max": max(box.y2 for box in boxes),
                    "cluster_union_area": BBox(
                        min(box.x1 for box in boxes),
                        min(box.y1 for box in boxes),
                        max(box.x2 for box in boxes),
                        max(box.y2 for box in boxes),
                    ).area,
                    "member_bbox_areas": join_values([fmt_float(box.area) for box in boxes]),
                    "member_bbox_aspects": join_values([fmt_float(box.aspect) for box in boxes]),
                    "member_bottom_y": join_values([fmt_float(box.y2) for box in boxes]),
                    "pairwise_iou_max": fmt_float(stats["pairwise_iou_max"]),
                    "pairwise_iou_mean": fmt_float(stats["pairwise_iou_mean"]),
                    "pairwise_center_distance_min": fmt_float(stats["pairwise_center_distance_min"]),
                    "pairwise_center_distance_mean": fmt_float(stats["pairwise_center_distance_mean"]),
                    "boundary_contact_any": any(boundary_contact_any(row, state_by_det, config) for row in members),
                    "neighbor_ambiguity_any": len(members) > 1
                    or any(boolish(state_by_det.get(det_id, {}).get("neighbor_ambiguity_proxy")) for det_id in det_ids),
                    "oty1_tracklet_ids": unique_join(
                        [state_by_det.get(det_id, {}).get("tracklet_candidate_id", "") for det_id in det_ids]
                    ),
                    "oty1_identity_statuses": unique_join(
                        [state_by_det.get(det_id, {}).get("identity_status", "") for det_id in det_ids]
                    ),
                    "tracker_assigned_track_ids": unique_join(
                        [assignment_by_det.get(det_id, {}).get("tracker_track_id", "") for det_id in det_ids]
                    ),
                    "tracked_det_ids": join_values(tracked_det_ids),
                    "unmatched_det_ids": join_values(unmatched_det_ids),
                    "cluster_role": role,
                    "cluster_risk_status": risk,
                    "runtime_source_policy": RUNTIME_SOURCE_POLICY,
                }
            )
    return out


def cluster_lookup(cluster_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cluster in cluster_rows:
        for det_id in str(cluster.get("det_ids", "") or "").split(";"):
            if det_id:
                out[det_id] = dict(cluster)
    return out


def area_ratio(left: float, right: float) -> float:
    if left <= 0 or right <= 0:
        return 0.0
    return min(left, right) / max(left, right)


def classify_association_choice(
    chosen: Mapping[str, Any],
    rejected: Sequence[Mapping[str, Any]],
    state_by_det: Mapping[str, Mapping[str, Any]],
    assignment: Mapping[str, Any],
    config: ObservationClusterConfig,
) -> tuple[str, str, bool]:
    if not rejected:
        return "clean_single_choice", "no same-frame observation-cluster neighbor was rejected", False
    chosen_box = raw_bbox(chosen)
    chosen_boundary = boundary_contact_any(chosen, state_by_det, config)
    rejected_boundaries = [boundary_contact_any(row, state_by_det, config) for row in rejected]
    rejected_boxes = [box for box in (raw_bbox(row) for row in rejected) if box is not None]
    chosen_area = chosen_box.area if chosen_box is not None else 0.0
    chosen_aspect = chosen_box.aspect or 0.0 if chosen_box is not None else 0.0
    max_rejected_aspect = max((box.aspect or 0.0 for box in rejected_boxes), default=0.0)
    max_rejected_iou = max((bbox_iou(chosen_box, box) for box in rejected_boxes), default=0.0) if chosen_box else 0.0
    tracker_box = raw_bbox(assignment)
    raw_vs_tracker_iou = bbox_iou(chosen_box, tracker_box) if chosen_box and tracker_box else 1.0

    if any(rejected_boundaries) and not chosen_boundary and chosen_area >= max((box.area for box in rejected_boxes), default=0.0):
        return (
            "chose_full_over_partial",
            "chosen detection is larger/taller and not boundary-touching while rejected neighbor is edge/partial-like",
            True,
        )
    if max_rejected_iou >= 0.50 and max_rejected_aspect > chosen_aspect * 1.35:
        return (
            "chose_full_over_partial",
            "chosen detection overlaps a wider shallow rejected neighbor, consistent with full-over-partial tracker choice",
            True,
        )
    if max_rejected_iou >= 0.50:
        return (
            "chose_stable_over_duplicate",
            "tracker kept one high-overlap detection and rejected a duplicate-like neighbor",
            True,
        )
    if raw_vs_tracker_iou < 0.80:
        return (
            "chose_tracker_state_over_raw_overlap",
            "tracker output bbox differs from the raw detection bbox; association should be read as tracker-state hypothesis",
            True,
        )
    return (
        "ambiguous_choice_requires_review",
        "same-frame neighbor competition exists but geometry does not isolate a clean reason",
        True,
    )


def build_association_choice_audit(
    cluster_rows: Sequence[Mapping[str, Any]],
    detection_rows: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    assignment_rows: Sequence[Mapping[str, Any]],
    config: ObservationClusterConfig,
) -> list[dict[str, Any]]:
    raw_by_det = index_by_det(detection_rows)
    state_by_det = index_by_det(oty1_state_rows)
    assignments = [row for row in filter_scene_frame_rows(assignment_rows, config) if str(row.get("tracker_track_id", "") or "")]
    cluster_by_det = cluster_lookup(cluster_rows)
    out: list[dict[str, Any]] = []
    for assignment in sorted(assignments, key=lambda row: (safe_int(row.get("optical_frame_num")), str(row.get("det_id", "")))):
        det_id = str(assignment.get("det_id", "") or "")
        chosen = raw_by_det.get(det_id, dict(assignment))
        chosen_box = raw_bbox(chosen)
        tracker_box = raw_bbox(assignment)
        cluster = cluster_by_det.get(det_id, {})
        cluster_det_ids = [item for item in str(cluster.get("det_ids", det_id) or det_id).split(";") if item]
        rejected = [raw_by_det[item] for item in cluster_det_ids if item != det_id and item in raw_by_det]
        rejected_boxes = [box for box in (raw_bbox(row) for row in rejected) if box is not None]
        status, reason, review_required = classify_association_choice(chosen, rejected, state_by_det, assignment, config)
        chosen_area = chosen_box.area if chosen_box else 0.0
        ious = [bbox_iou(chosen_box, box) for box in rejected_boxes] if chosen_box else []
        distances = [center_distance(chosen_box, box) for box in rejected_boxes] if chosen_box else []
        ratios = [area_ratio(chosen_area, box.area) for box in rejected_boxes]
        out.append(
            {
                "scene": config.scene,
                "optical_frame_num": safe_int(assignment.get("optical_frame_num")),
                "tracker_name": assignment.get("tracker_name", config.tracker_name),
                "tracker_track_id": assignment.get("tracker_track_id", ""),
                "chosen_det_id": det_id,
                "chosen_oty1_tracklet_id": state_by_det.get(det_id, {}).get("tracklet_candidate_id", ""),
                "chosen_confidence": fmt_float(chosen.get("confidence")),
                "chosen_raw_bbox_x1": "" if chosen_box is None else chosen_box.x1,
                "chosen_raw_bbox_y1": "" if chosen_box is None else chosen_box.y1,
                "chosen_raw_bbox_x2": "" if chosen_box is None else chosen_box.x2,
                "chosen_raw_bbox_y2": "" if chosen_box is None else chosen_box.y2,
                "chosen_tracker_bbox_x1": "" if tracker_box is None else tracker_box.x1,
                "chosen_tracker_bbox_y1": "" if tracker_box is None else tracker_box.y1,
                "chosen_tracker_bbox_x2": "" if tracker_box is None else tracker_box.x2,
                "chosen_tracker_bbox_y2": "" if tracker_box is None else tracker_box.y2,
                "chosen_bbox_area": fmt_float(chosen_area),
                "chosen_boundary_contact": boundary_contact_any(chosen, state_by_det, config),
                "rejected_neighbor_det_ids": join_values([row.get("det_id", "") for row in rejected]),
                "rejected_neighbor_oty1_tracklet_ids": unique_join(
                    [state_by_det.get(str(row.get("det_id", "")), {}).get("tracklet_candidate_id", "") for row in rejected]
                ),
                "rejected_neighbor_confidences": join_values([fmt_float(row.get("confidence")) for row in rejected]),
                "rejected_neighbor_bbox_areas": join_values([fmt_float(box.area) for box in rejected_boxes]),
                "chosen_vs_rejected_iou_max": fmt_float(max(ious) if ious else 0.0),
                "chosen_vs_rejected_center_distance_min": fmt_float(min(distances) if distances else 0.0),
                "chosen_vs_rejected_area_ratio_min": fmt_float(min(ratios) if ratios else 0.0),
                "chosen_vs_rejected_area_ratio_max": fmt_float(max(ratios) if ratios else 0.0),
                "observation_cluster_id": cluster.get("observation_cluster_id", ""),
                "association_choice_status": status,
                "association_choice_reason": reason,
                "review_required": review_required,
            }
        )
    return out


def best_other_raw_match(
    tracker_box: BBox,
    det_id: str,
    frame_raw_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, float, float] | None:
    best: tuple[str, float, float] | None = None
    for row in frame_raw_rows:
        other_id = str(row.get("det_id", "") or "")
        if other_id == det_id:
            continue
        box = raw_bbox(row)
        if box is None:
            continue
        iou = bbox_iou(tracker_box, box)
        distance = center_distance(tracker_box, box)
        if best is None or iou > best[1] or (iou == best[1] and distance < best[2]):
            best = (other_id, iou, distance)
    return best


def build_tracker_bbox_provenance_audit(
    detection_rows: Sequence[Mapping[str, Any]],
    assignment_rows: Sequence[Mapping[str, Any]],
    config: ObservationClusterConfig,
) -> list[dict[str, Any]]:
    raw_by_det = index_by_det(detection_rows)
    raw_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in filter_scene_frame_rows(detection_rows, config):
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            raw_by_frame.setdefault(frame, []).append(dict(row))
    out: list[dict[str, Any]] = []
    output_idx = 0
    for assignment in sorted(
        filter_scene_frame_rows(assignment_rows, config),
        key=lambda row: (safe_int(row.get("optical_frame_num")), str(row.get("det_id", ""))),
    ):
        if not str(assignment.get("tracker_track_id", "") or ""):
            continue
        output_idx += 1
        det_id = str(assignment.get("det_id", "") or "")
        raw = raw_by_det.get(det_id, {})
        raw_box = raw_bbox(raw)
        tracker_box = raw_bbox(assignment)
        if raw_box is None or tracker_box is None:
            status = "idx_mapping_suspicious" if raw_box is None else "bbox_provenance_unknown"
            reason = "mapped det_id is missing from the OTY0 raw detection table" if raw_box is None else "tracker output bbox is incomplete"
            center_delta: Any = ""
            area_delta_ratio: Any = ""
            raw_iou: Any = ""
            mapping_verified = False
        else:
            center_delta = center_distance(raw_box, tracker_box)
            area_delta_ratio = abs(tracker_box.area - raw_box.area) / raw_box.area if raw_box.area > 0 else ""
            raw_iou = bbox_iou(raw_box, tracker_box)
            frame = safe_int(assignment.get("optical_frame_num"))
            other = best_other_raw_match(tracker_box, det_id, raw_by_frame.get(frame, []))
            mapping_suspicious = bool(
                other
                and raw_iou < 0.25
                and other[1] >= raw_iou + 0.25
                and other[2] + 20.0 < center_delta
            )
            mapping_verified = not mapping_suspicious
            if mapping_suspicious:
                status = "idx_mapping_suspicious"
                reason = f"tracker bbox matches nearby raw det {other[0]} better than mapped det_id"
            elif raw_iou >= 0.98 and parse_float(area_delta_ratio) is not None and area_delta_ratio <= 0.02:
                status = "raw_bbox_preserved"
                reason = "tracker output bbox is effectively the raw OTY0 detection bbox"
            elif center_delta <= config.bbox_small_center_delta_px and parse_float(area_delta_ratio) is not None and area_delta_ratio >= config.bbox_scale_change_threshold:
                status = "tracker_state_bbox_scale_change"
                reason = "mapped det_id is verified; bbox center stays close while tracker state changes scale"
            elif center_delta > config.bbox_small_center_delta_px or raw_iou < 0.90:
                status = "tracker_state_bbox_shift"
                reason = "mapped det_id is verified; tracker state bbox shifts relative to raw detection"
            else:
                status = "raw_bbox_preserved"
                reason = "mapped det_id is verified and tracker bbox delta is small"
        out.append(
            {
                "scene": config.scene,
                "optical_frame_num": safe_int(assignment.get("optical_frame_num")),
                "det_id": det_id,
                "tracker_name": assignment.get("tracker_name", config.tracker_name),
                "tracker_track_id": assignment.get("tracker_track_id", ""),
                "raw_bbox_x1": "" if raw_box is None else raw_box.x1,
                "raw_bbox_y1": "" if raw_box is None else raw_box.y1,
                "raw_bbox_x2": "" if raw_box is None else raw_box.x2,
                "raw_bbox_y2": "" if raw_box is None else raw_box.y2,
                "tracker_output_bbox_x1": "" if tracker_box is None else tracker_box.x1,
                "tracker_output_bbox_y1": "" if tracker_box is None else tracker_box.y1,
                "tracker_output_bbox_x2": "" if tracker_box is None else tracker_box.x2,
                "tracker_output_bbox_y2": "" if tracker_box is None else tracker_box.y2,
                "center_delta_px": fmt_float(center_delta),
                "area_delta_ratio": fmt_float(area_delta_ratio),
                "iou_raw_vs_tracker_output": fmt_float(raw_iou),
                "output_idx": output_idx,
                "mapped_det_id": det_id,
                "mapping_verified": mapping_verified,
                "bbox_provenance_status": status,
                "bbox_provenance_reason": reason,
            }
        )
    return out


def find_case_bridge_pair(
    detection_rows: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    config: ObservationClusterConfig,
) -> dict[str, Any]:
    from_tracklet, to_tracklet = case_tracklet_ids(config.case_id)
    raw_by_det = index_by_det(detection_rows)
    state_rows = filter_scene_frame_rows(oty1_state_rows, config)
    from_rows = [row for row in state_rows if str(row.get("tracklet_candidate_id", "") or "") == from_tracklet]
    to_rows = [row for row in state_rows if str(row.get("tracklet_candidate_id", "") or "") == to_tracklet]
    best: dict[str, Any] = {}
    best_score = -1.0
    for left in from_rows:
        left_frame = parse_int(left.get("optical_frame_num"))
        left_id = str(left.get("det_id", "") or "")
        left_box = raw_bbox(raw_by_det.get(left_id, left))
        if left_frame is None or left_box is None:
            continue
        for right in to_rows:
            right_frame = parse_int(right.get("optical_frame_num"))
            right_id = str(right.get("det_id", "") or "")
            right_box = raw_bbox(raw_by_det.get(right_id, right))
            if right_frame is None or right_box is None:
                continue
            frame_gap = right_frame - left_frame
            if frame_gap <= 0 or frame_gap > 4:
                continue
            iou = bbox_iou(left_box, right_box)
            distance = center_distance(left_box, right_box)
            score = iou - 0.001 * abs(frame_gap)
            if score > best_score:
                best_score = score
                best = {
                    "from_det_id": left_id,
                    "to_det_id": right_id,
                    "from_frame": left_frame,
                    "to_frame": right_frame,
                    "frame_gap": frame_gap,
                    "raw_iou": iou,
                    "center_distance_px": distance,
                }
    return best


def pair_metrics(
    detection_rows: Sequence[Mapping[str, Any]], left_det_id: str, right_det_id: str
) -> dict[str, Any]:
    raw_by_det = index_by_det(detection_rows)
    left_box = raw_bbox(raw_by_det.get(left_det_id, {}))
    right_box = raw_bbox(raw_by_det.get(right_det_id, {}))
    if left_box is None or right_box is None:
        return {"left_det_id": left_det_id, "right_det_id": right_det_id, "raw_iou": "", "center_distance_px": ""}
    return {
        "left_det_id": left_det_id,
        "right_det_id": right_det_id,
        "raw_iou": bbox_iou(left_box, right_box),
        "center_distance_px": center_distance(left_box, right_box),
    }


def merge_edge_for_case(
    merge_edges: Sequence[Mapping[str, Any]], config: ObservationClusterConfig
) -> dict[str, Any]:
    from_tracklet, to_tracklet = case_tracklet_ids(config.case_id)
    for row in merge_edges:
        if str(row.get("scene", "") or "") != config.scene:
            continue
        if (
            str(row.get("from_tracklet_candidate_id", "") or "") == from_tracklet
            and str(row.get("to_tracklet_candidate_id", "") or "") == to_tracklet
        ):
            return dict(row)
    return {}


def hypothesis_rows(
    summary: Mapping[str, Any],
    merge_edge: Mapping[str, Any],
) -> list[dict[str, Any]]:
    bridge_iou = safe_float(summary.get("bridge_pair_raw_iou"))
    bridge_distance = safe_float(summary.get("bridge_pair_center_distance_px"))
    multi_count = safe_int(summary.get("multi_det_cluster_count"))
    provenance_issues = safe_int(summary.get("bbox_provenance_issue_count"))
    frame_172_rejected = str(summary.get("frame_172_rejected_det_ids", "") or "")
    oty1a_status = str(merge_edge.get("merge_candidate_status", "") or "")

    hypothesis_a_support = "moderate" if bridge_iou >= 0.45 and bridge_distance <= 120 else "weak"
    hypothesis_b_support = "strong" if "GM_RM019_000172_002" in frame_172_rejected else "moderate"
    hypothesis_c_support = "strong" if multi_count >= 3 else "moderate" if multi_count else "weak"
    if provenance_issues and hypothesis_b_support == "strong":
        hypothesis_b_support = "moderate"

    return [
        {
            "hypothesis_name": "Hypothesis A",
            "hypothesis": "0039 partial boxes and 0045 full/right-edge boxes are same-object observation variants.",
            "support_level": hypothesis_a_support,
            "evidence": [
                f"bridge pair {summary.get('bridge_source_det_id', '')}->{summary.get('frame_173_tracked_det_id', '')} raw IoU={fmt_float(bridge_iou)} center_distance_px={fmt_float(bridge_distance, 3)}",
                f"OTY1a status={oty1a_status or 'missing'} with partial/full transition context",
                "existing optical visual panel impression is contiguous but review-only",
                "boundary / partial / shape transition evidence is present in OTY1/OTY1a context",
            ],
            "counter_evidence": [
                f"ByteTrack chose {summary.get('frame_172_chosen_det_id', '')} instead of the bridge source",
                "same-frame detection competition remains unresolved",
            ],
            "recommended_use": "optional_continuity_hint_with_visual_review",
        },
        {
            "hypothesis_name": "Hypothesis B",
            "hypothesis": "0039 boxes are duplicate / partial / wide detector artifacts that should not override the stable tracker hypothesis.",
            "support_level": hypothesis_b_support,
            "evidence": [
                f"frame 172 rejected neighbor det_ids={frame_172_rejected}",
                "0039-side boxes include wide / shallow / boundary-touching observations",
                f"tracker chose alternative det={summary.get('frame_172_chosen_det_id', '')} on the 0045 side",
                "0039 unmatched sequence persists through the local transition window",
            ],
            "counter_evidence": [
                f"bridge pair still has nontrivial raw IoU={fmt_float(bridge_iou)}",
                "artifact interpretation is an optical review hypothesis, not identity truth",
            ],
            "recommended_use": "optional_uncertainty_hint_only",
        },
        {
            "hypothesis_name": "Hypothesis C",
            "hypothesis": "0039/0045 region contains multi-vehicle or same-frame detection competition.",
            "support_level": hypothesis_c_support,
            "evidence": [
                f"multi-det observation clusters in analyzed window={multi_count}",
                "frame 172 cluster contains both 172_001 and 172_002 with tracker choosing one and rejecting the other",
                "OTY1/OTY1a context marks ambiguous crossing / competing merge risk",
                "nearby detections appear across frames 162-174 in OTY0 rows",
            ],
            "counter_evidence": [
                "same-frame clusters are optical observation clusters, not confirmed multi-vehicle truth",
                "tracker id continuity alone cannot resolve identity",
            ],
            "recommended_use": "candidate_for_tracklet_stitching_review",
        },
    ]


def build_summary(
    cluster_rows: Sequence[Mapping[str, Any]],
    association_rows: Sequence[Mapping[str, Any]],
    provenance_rows: Sequence[Mapping[str, Any]],
    bridge_pair: Mapping[str, Any],
    pair_172_001_173_001: Mapping[str, Any],
    pair_172_002_173_001: Mapping[str, Any],
    config: ObservationClusterConfig,
    output_dir: str,
) -> dict[str, Any]:
    frames = sorted({safe_int(row.get("optical_frame_num")) for row in cluster_rows})
    frame_172_choices = [
        row for row in association_rows if safe_int(row.get("optical_frame_num")) == 172 and str(row.get("tracker_track_id", "")) == "bt_0098"
    ]
    if not frame_172_choices:
        frame_172_choices = [row for row in association_rows if safe_int(row.get("optical_frame_num")) == 172]
    frame_172_choice = frame_172_choices[0] if frame_172_choices else {}
    frame_173_tracked = [
        row for row in association_rows if safe_int(row.get("optical_frame_num")) == 173 and str(row.get("tracker_track_id", "")) == "bt_0098"
    ]
    frame_173_det = str(frame_173_tracked[0].get("chosen_det_id", "")) if frame_173_tracked else ""
    bridge_source = str(bridge_pair.get("from_det_id", "") or "")
    frame_172_chosen = str(frame_172_choice.get("chosen_det_id", "") or "")
    idx_suspicious = sum(1 for row in provenance_rows if row.get("bbox_provenance_status") == "idx_mapping_suspicious")
    provenance_issues = sum(1 for row in provenance_rows if row.get("bbox_provenance_status") != "raw_bbox_preserved")
    recommended_next_step = (
        "adapter_bugfix"
        if idx_suspicious
        else "tracklet_stitching_review_or_observation_cluster_handoff"
    )
    return {
        "scene": config.scene,
        "case_id": config.case_id,
        "frames_analyzed": f"{frames[0]}-{frames[-1]}" if frames else "",
        "frame_start": config.frame_start,
        "frame_end": config.frame_end,
        "observation_cluster_count": len(cluster_rows),
        "multi_det_cluster_count": sum(1 for row in cluster_rows if safe_int(row.get("cluster_size")) > 1),
        "partial_full_cluster_count": sum(1 for row in cluster_rows if row.get("cluster_role") == "partial_full_observation_cluster"),
        "ambiguous_multi_vehicle_cluster_count": sum(1 for row in cluster_rows if row.get("cluster_role") == "ambiguous_multi_vehicle_cluster"),
        "detector_artifact_cluster_count": sum(1 for row in cluster_rows if row.get("cluster_role") == "detector_artifact_cluster"),
        "frame_172_chosen_det_id": frame_172_chosen,
        "frame_172_rejected_det_ids": str(frame_172_choice.get("rejected_neighbor_det_ids", "") or ""),
        "frame_173_tracked_det_id": frame_173_det,
        "bridge_source_det_id": bridge_source,
        "bridge_pair_raw_iou": fmt_float(bridge_pair.get("raw_iou")),
        "bridge_pair_center_distance_px": fmt_float(bridge_pair.get("center_distance_px"), 3),
        "pair_172_001_173_001_raw_iou": fmt_float(pair_172_001_173_001.get("raw_iou")),
        "pair_172_001_173_001_center_distance_px": fmt_float(pair_172_001_173_001.get("center_distance_px"), 3),
        "pair_172_002_173_001_raw_iou": fmt_float(pair_172_002_173_001.get("raw_iou")),
        "pair_172_002_173_001_center_distance_px": fmt_float(pair_172_002_173_001.get("center_distance_px"), 3),
        "tracker_chose_bridge_source_det": bool(bridge_source and frame_172_chosen == bridge_source),
        "tracker_chose_alternative_det": bool(bridge_source and frame_172_chosen and frame_172_chosen != bridge_source),
        "bbox_provenance_issue_count": provenance_issues,
        "idx_mapping_suspicious_count": idx_suspicious,
        "recommended_next_step": recommended_next_step,
        "posthoc_sources_used_for_runtime_tracking": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "annotation_proposal_entered": False,
        "identity_truth_claimed": False,
        "output_dir": output_dir,
        "runtime_source_policy": RUNTIME_SOURCE_POLICY,
    }


def local_window_explanations_payload(
    summary: Mapping[str, Any],
    merge_edge: Mapping[str, Any],
) -> dict[str, Any]:
    hypotheses = hypothesis_rows(summary, merge_edge)
    return {
        "scene": summary.get("scene", ""),
        "case_id": summary.get("case_id", ""),
        "frames_analyzed": summary.get("frames_analyzed", ""),
        "confirmed_identity": False,
        "hypotheses": hypotheses,
        "final_conclusion": (
            "OTY1t-P3 keeps 0039/0045 as review-only optical observation and tracker association hypotheses. "
            "The audit supports an observation-cluster / tracklet-stitching review handoff, not confirmed identity."
        ),
        "boundary_flags": {
            "posthoc_sources_used_for_runtime_tracking": False,
            "sar_alignment_entered": False,
            "sar_band_entered": False,
            "sar_gt_coverage_entered": False,
            "annotation_proposal_entered": False,
            "identity_truth_claimed": False,
        },
    }


def render_explanations_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# OTY1t 0039/0045 Local Window Explanations",
        "",
        "## Boundary",
        "",
        "- These are review-only optical hypotheses.",
        "- confirmed_identity=false",
        "- posthoc_sources_used_for_runtime_tracking=false",
        "- sar_alignment_entered=false",
        "- sar_band_entered=false",
        "- sar_gt_coverage_entered=false",
        "- annotation_proposal_entered=false",
        "- identity_truth_claimed=false",
        "",
        "## Hypotheses",
        "",
    ]
    for row in payload.get("hypotheses", []):
        if not isinstance(row, Mapping):
            continue
        lines.extend(
            [
                f"### {row.get('hypothesis_name', '')}",
                "",
                f"- hypothesis: `{row.get('hypothesis', '')}`",
                f"- support_level: `{row.get('support_level', '')}`",
                f"- recommended_use: `{row.get('recommended_use', '')}`",
                "- evidence:",
            ]
        )
        for item in row.get("evidence", []):
            lines.append(f"  - {item}")
        lines.append("- counter_evidence:")
        for item in row.get("counter_evidence", []):
            lines.append(f"  - {item}")
        lines.append("")
    lines.extend(["## Final Conclusion", "", str(payload.get("final_conclusion", "")), ""])
    return "\n".join(lines)


def render_summary_markdown(summary: Mapping[str, Any], hypotheses: Sequence[Mapping[str, Any]]) -> str:
    def md_value(value: Any) -> Any:
        if isinstance(value, bool):
            return str(value).lower()
        return value

    fields = [
        "scene",
        "case_id",
        "frames_analyzed",
        "observation_cluster_count",
        "multi_det_cluster_count",
        "partial_full_cluster_count",
        "ambiguous_multi_vehicle_cluster_count",
        "detector_artifact_cluster_count",
        "frame_172_chosen_det_id",
        "frame_172_rejected_det_ids",
        "frame_173_tracked_det_id",
        "bridge_pair_raw_iou",
        "bridge_pair_center_distance_px",
        "tracker_chose_bridge_source_det",
        "tracker_chose_alternative_det",
        "bbox_provenance_issue_count",
        "idx_mapping_suspicious_count",
        "recommended_next_step",
        "posthoc_sources_used_for_runtime_tracking",
        "sar_alignment_entered",
        "sar_band_entered",
        "sar_gt_coverage_entered",
        "annotation_proposal_entered",
        "identity_truth_claimed",
    ]
    lines = [
        "# OTY1t Observation Cluster Summary",
        "",
        "OTY1t-P3 audits same-frame observation clusters, tracker association choices, and bbox provenance around GM_RM019 0039/0045. Outputs remain review-only optical hypotheses. No confirmed identity, SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector output, training signal, or annotation proposal was introduced.",
        "",
        "## Summary Fields",
        "",
    ]
    for field in fields:
        lines.append(f"- {field}: `{md_value(summary.get(field, ''))}`")
    lines.extend(["", "## Pair Metrics", ""])
    lines.append(
        f"- 172_001 vs 173_001 raw IoU / center distance: `{summary.get('pair_172_001_173_001_raw_iou', '')}` / `{summary.get('pair_172_001_173_001_center_distance_px', '')}`"
    )
    lines.append(
        f"- 172_002 vs 173_001 raw IoU / center distance: `{summary.get('pair_172_002_173_001_raw_iou', '')}` / `{summary.get('pair_172_002_173_001_center_distance_px', '')}`"
    )
    lines.extend(["", "## Hypothesis Support", ""])
    for row in hypotheses:
        lines.append(
            f"- {row.get('hypothesis_name', '')}: `{row.get('support_level', '')}`, recommended_use=`{row.get('recommended_use', '')}`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Tracker id, observation cluster, tracklet link, and visual review hypothesis are not confirmed identity.",
            "- OTY2, SAR band, SAR GT coverage, SAR evidence sampling, selector/G2/A008, threshold tuning, training, and annotation proposal remain outside this audit.",
            "",
        ]
    )
    return "\n".join(lines)


def render_observation_clusters_svg(
    path: str | Path,
    cluster_rows: Sequence[Mapping[str, Any]],
    association_rows: Sequence[Mapping[str, Any]],
) -> None:
    rows = [row for row in cluster_rows if 162 <= safe_int(row.get("optical_frame_num")) <= 174]
    height = 90 + max(1, len(rows)) * 30
    width = 1120
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="32" font-size="18" font-family="Arial" font-weight="700" fill="#111827">OTY1t-P3 observation clusters 162-174</text>',
        '<text x="24" y="56" font-size="13" font-family="Arial" fill="#374151">confirmed_identity=false; optical review hypotheses only</text>',
        '<text x="24" y="78" font-size="13" font-family="Arial" fill="#374151">Frame 172: tracker chose 172_001 -> bt_0098; OTY1a bridge uses 172_002 -> 173_001</text>',
    ]
    y = 112
    for row in rows:
        frame = safe_int(row.get("optical_frame_num"))
        size = safe_int(row.get("cluster_size"))
        color = "#f59e0b" if frame == 172 else "#2563eb" if size > 1 else "#6b7280"
        if frame == 173:
            color = "#10b981"
        parts.append(f'<rect x="24" y="{y - 18}" width="92" height="22" rx="4" fill="{color}" opacity="0.16"/>')
        parts.append(f'<text x="34" y="{y - 3}" font-size="12" font-family="Arial" fill="#111827">F{frame}</text>')
        parts.append(
            f'<text x="130" y="{y - 3}" font-size="12" font-family="Arial" fill="#111827">{html_escape(str(row.get("observation_cluster_id", "")))} size={size}</text>'
        )
        parts.append(
            f'<text x="420" y="{y - 3}" font-size="12" font-family="Arial" fill="#111827">{html_escape(str(row.get("det_ids", "")))}</text>'
        )
        parts.append(
            f'<text x="790" y="{y - 3}" font-size="12" font-family="Arial" fill="#374151">{html_escape(str(row.get("cluster_role", "")))}</text>'
        )
        y += 30
    parts.append("</svg>")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def _scaled_rect(box: BBox, ox: float, oy: float, scale: float) -> tuple[float, float, float, float]:
    return ox + box.x1 * scale, oy + box.y1 * scale, box.width * scale, box.height * scale


def render_association_choice_svg(
    path: str | Path,
    detection_rows: Sequence[Mapping[str, Any]],
    assignment_rows: Sequence[Mapping[str, Any]],
) -> None:
    raw_by_det = index_by_det(detection_rows)
    assign_by_det = index_by_det(assignment_rows)
    width = 900
    height = 430
    scale = 0.42
    left_ox, top = 40, 94
    right_ox = 500
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="30" font-size="18" font-family="Arial" font-weight="700" fill="#111827">Association choice at frame 172</text>',
        '<text x="24" y="54" font-size="13" font-family="Arial" fill="#374151">confirmed_identity=false; tracker association hypothesis only</text>',
        '<text x="24" y="76" font-size="13" font-family="Arial" fill="#374151">tracker chose 172_001 -> bt_0098; OTY1a bridge uses 172_002 -> 173_001</text>',
        f'<rect x="{left_ox}" y="{top}" width="{800 * scale}" height="{600 * scale}" fill="#f9fafb" stroke="#d1d5db"/>',
        f'<rect x="{right_ox}" y="{top}" width="{800 * scale}" height="{600 * scale}" fill="#f9fafb" stroke="#d1d5db"/>',
        f'<text x="{left_ox}" y="{top - 10}" font-size="13" font-family="Arial" fill="#111827">frame 172</text>',
        f'<text x="{right_ox}" y="{top - 10}" font-size="13" font-family="Arial" fill="#111827">frame 173</text>',
    ]
    draw_specs = [
        ("GM_RM019_000172_001", left_ox, "#10b981", "172_001 chosen bt_0098"),
        ("GM_RM019_000172_002", left_ox, "#ef4444", "172_002 rejected/unmatched"),
        ("GM_RM019_000173_001", right_ox, "#2563eb", "173_001 tracked bt_0098"),
    ]
    for det_id, ox, color, label in draw_specs:
        box = raw_bbox(raw_by_det.get(det_id, {}))
        if box is None:
            continue
        x, y, w, h = _scaled_rect(box, ox, top, scale)
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{x:.2f}" y="{max(top + 14, y - 4):.2f}" font-size="12" font-family="Arial" fill="{color}">{html_escape(label)}</text>')
    tracker_box = raw_bbox(assign_by_det.get("GM_RM019_000172_001", {}))
    if tracker_box is not None:
        x, y, w, h = _scaled_rect(tracker_box, left_ox, top, scale)
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="#111827" stroke-width="2" stroke-dasharray="6 4"/>')
        parts.append(f'<text x="{x:.2f}" y="{y + h + 14:.2f}" font-size="12" font-family="Arial" fill="#111827">tracker state bbox for 172_001</text>')
    left_bridge = raw_bbox(raw_by_det.get("GM_RM019_000172_002", {}))
    right_bridge = raw_bbox(raw_by_det.get("GM_RM019_000173_001", {}))
    if left_bridge is not None and right_bridge is not None:
        x1 = left_ox + left_bridge.cx * scale
        y1 = top + left_bridge.cy * scale
        x2 = right_ox + right_bridge.cx * scale
        y2 = top + right_bridge.cy * scale
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5 4"/>')
    parts.extend(
        [
            '<text x="40" y="382" font-size="12" font-family="Arial" fill="#374151">Green/blue boxes are tracker-side chosen/tracked detections; red is rejected neighbor. Dashed black is tracker state bbox.</text>',
            "</svg>",
        ]
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def render_bbox_provenance_svg(path: str | Path, provenance_rows: Sequence[Mapping[str, Any]]) -> None:
    wanted = [
        "GM_RM019_000172_001",
        "GM_RM019_000173_001",
        "GM_RM019_000174_001",
        "GM_RM019_000181_001",
        "GM_RM019_000182_001",
    ]
    row_by_det = {str(row.get("det_id", "") or ""): row for row in provenance_rows}
    width = 920
    height = 300
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="30" font-size="18" font-family="Arial" font-weight="700" fill="#111827">BBox provenance 172-183</text>',
        '<text x="24" y="54" font-size="13" font-family="Arial" fill="#374151">confirmed_identity=false; mapping_verified is separate from tracker-state scale changes</text>',
    ]
    y = 92
    for det_id in wanted:
        row = row_by_det.get(det_id, {})
        center_delta = safe_float(row.get("center_delta_px"))
        area_delta = safe_float(row.get("area_delta_ratio"))
        status = str(row.get("bbox_provenance_status", "missing") or "missing")
        color = "#10b981" if status == "raw_bbox_preserved" else "#2563eb" if "scale" in status else "#ef4444" if "idx" in status else "#f59e0b"
        parts.append(f'<text x="30" y="{y}" font-size="12" font-family="Arial" fill="#111827">{html_escape(det_short_id(det_id))}</text>')
        parts.append(f'<rect x="160" y="{y - 13}" width="{min(260, center_delta * 20):.2f}" height="10" fill="#94a3b8"/>')
        parts.append(f'<text x="430" y="{y}" font-size="12" font-family="Arial" fill="#374151">center_delta={center_delta:.3f}px</text>')
        parts.append(f'<rect x="585" y="{y - 13}" width="{min(220, area_delta * 120):.2f}" height="10" fill="{color}"/>')
        parts.append(f'<text x="815" y="{y}" font-size="12" font-family="Arial" fill="#374151">{html_escape(status)}</text>')
        y += 36
    parts.append("</svg>")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(parts), encoding="utf-8")
