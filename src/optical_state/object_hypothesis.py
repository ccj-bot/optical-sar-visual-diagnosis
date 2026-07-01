"""Object-level optical hypothesis helpers for OTY1t-P4.

P4 sits above detection-level tracker outputs. It combines one main tracker
trajectory with primary detections, same-frame secondary observations,
observation clusters, and OTY1a fragment-review hints. Outputs are
object-level optical hypotheses only; this module does not confirm identity
and does not use SAR, GT, final/manual/oracle/review labels, selector scores,
threshold tuning, training signals, or annotation proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as html_escape
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from .observation_cluster import case_tracklet_ids
from .state_features import BBox, parse_float, parse_int


RUNTIME_SOURCE_POLICY = (
    "oty1t_p4_runtime_safe_object_optical_hypothesis_no_gt_no_sar_no_selector"
)

OBJECT_HYPOTHESIS_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "case_id",
    "frame_start",
    "frame_end",
    "main_tracker_name",
    "main_tracker_track_id",
    "main_tracker_frame_start",
    "main_tracker_frame_end",
    "main_tracker_detection_count",
    "primary_tracklet_ids",
    "secondary_tracklet_ids",
    "primary_det_ids",
    "secondary_det_ids",
    "primary_observation_cluster_ids",
    "secondary_observation_cluster_ids",
    "related_oty1a_merge_edge_ids",
    "related_oty1a_statuses",
    "same_object_support_level",
    "same_object_support_score_proxy",
    "main_track_stability_status",
    "secondary_observation_role",
    "partial_full_transition_present",
    "duplicate_observation_present",
    "boundary_truncation_present",
    "multi_vehicle_confusion_risk",
    "detector_artifact_risk",
    "tracker_chose_bridge_source_det",
    "tracker_chose_alternative_det",
    "bbox_provenance_status_summary",
    "idx_mapping_suspicious_count",
    "recommended_use_for_oty2",
    "identity_status",
    "review_required",
    "runtime_source_policy",
]

OBJECT_FRAME_STATE_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "optical_frame_num",
    "main_tracker_track_id",
    "primary_det_id",
    "secondary_det_ids",
    "observation_cluster_id",
    "primary_bbox_x1",
    "primary_bbox_y1",
    "primary_bbox_x2",
    "primary_bbox_y2",
    "primary_bbox_center_x",
    "primary_bbox_center_y",
    "primary_bbox_w",
    "primary_bbox_h",
    "primary_confidence",
    "secondary_bbox_summary",
    "tracker_state_bbox_x1",
    "tracker_state_bbox_y1",
    "tracker_state_bbox_x2",
    "tracker_state_bbox_y2",
    "bbox_provenance_status",
    "cluster_role",
    "cluster_risk_status",
    "state_visibility_status",
    "state_uncertainty_status",
    "partial_full_transition_state",
    "boundary_truncation_state",
    "multi_observation_state",
    "recommended_oty2_weight",
    "review_required",
]


@dataclass(frozen=True)
class ObjectHypothesisConfig:
    scene: str = "GM_RM019"
    case_id: str = "0039_0045"
    tracker_name: str = "bytetrack"


def boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def safe_int(value: Any, default: int = 0) -> int:
    parsed = parse_int(value)
    return default if parsed is None else parsed


def safe_float(value: Any, default: float = 0.0) -> float:
    parsed = parse_float(value)
    return default if parsed is None else parsed


def fmt_float(value: Any, digits: int = 6) -> Any:
    parsed = parse_float(value)
    if parsed is None or not isfinite(parsed):
        return ""
    return round(parsed, digits)


def split_values(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.replace(",", ";").split(";") if item.strip()]


def unique_sorted(values: Sequence[Any]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value or "").strip()})


def join_values(values: Sequence[Any]) -> str:
    return ";".join(unique_sorted(values))


def index_by(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field, "") or "").strip()
        if key:
            out[key] = dict(row)
    return out


def bbox_from_row(row: Mapping[str, Any], prefix: str = "bbox") -> BBox | None:
    x1 = parse_float(row.get(f"{prefix}_x1"))
    y1 = parse_float(row.get(f"{prefix}_y1"))
    x2 = parse_float(row.get(f"{prefix}_x2"))
    y2 = parse_float(row.get(f"{prefix}_y2"))
    if None in (x1, y1, x2, y2):
        return None
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    return BBox(x1, y1, x2, y2)


def bbox_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        box = bbox_from_row(row)
        if box is None:
            continue
        parts.append(
            f"{row.get('det_id', '')}:"
            f"{fmt_float(box.x1, 2)},{fmt_float(box.y1, 2)},"
            f"{fmt_float(box.x2, 2)},{fmt_float(box.y2, 2)}"
        )
    return ";".join(parts)


def object_hypothesis_id(scene: str, case_id: str, tracker_track_id: str) -> str:
    safe_track = str(tracker_track_id or "no_tracker").replace(" ", "_")
    return f"oty1t_obj_{scene}_{case_id}_{safe_track}"


def find_main_tracker_track_id(
    association_rows: Sequence[Mapping[str, Any]],
    config: ObjectHypothesisConfig,
) -> str:
    _, to_tracklet = case_tracklet_ids(config.case_id)
    counts: dict[str, int] = {}
    for row in association_rows:
        if str(row.get("scene", "") or "") != config.scene:
            continue
        if str(row.get("chosen_oty1_tracklet_id", "") or "") != to_tracklet:
            continue
        track_id = str(row.get("tracker_track_id", "") or "").strip()
        if track_id:
            counts[track_id] = counts.get(track_id, 0) + 1
    if counts:
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    for row in association_rows:
        track_id = str(row.get("tracker_track_id", "") or "").strip()
        if track_id:
            return track_id
    return ""


def related_edges_for_tracklets(
    merge_edges: Sequence[Mapping[str, Any]],
    tracklet_ids: Sequence[str],
    scene: str,
) -> list[dict[str, Any]]:
    wanted = set(tracklet_ids)
    out: list[dict[str, Any]] = []
    for row in merge_edges:
        if str(row.get("scene", "") or "") != scene:
            continue
        left = str(row.get("from_tracklet_candidate_id", "") or "")
        right = str(row.get("to_tracklet_candidate_id", "") or "")
        if left in wanted and right in wanted:
            out.append(dict(row))
    return sorted(out, key=lambda row: str(row.get("merge_edge_id", "")))


def track_stability_status(track: Mapping[str, Any]) -> str:
    identity = str(track.get("identity_status", "") or "")
    status = str(track.get("track_status", "") or "")
    if safe_int(track.get("reactivated_count")) > 0:
        return "reactivated_main_track"
    if "ambiguous" in identity or "ambiguous" in status:
        return "ambiguous_main_track"
    if "fragment" in identity or "fragment" in status or safe_int(track.get("missing_gap_count")) > 0:
        return "fragmented_main_track"
    return "stable_main_track"


def provenance_summary(rows: Sequence[Mapping[str, Any]], det_ids: Sequence[str]) -> str:
    wanted = set(det_ids)
    counts: dict[str, int] = {}
    for row in rows:
        if str(row.get("det_id", "") or "") not in wanted:
            continue
        status = str(row.get("bbox_provenance_status", "") or "bbox_provenance_unknown")
        counts[status] = counts.get(status, 0) + 1
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def secondary_role(
    secondary_rows: Sequence[Mapping[str, Any]],
    cluster_rows: Sequence[Mapping[str, Any]],
) -> str:
    if not secondary_rows:
        return "none"
    roles = {str(row.get("cluster_role", "") or "") for row in cluster_rows}
    aspects = [safe_float(row.get("bbox_aspect")) for row in secondary_rows if str(row.get("bbox_aspect", "")).strip()]
    boundary = any(boolish(row.get("touch_any")) for row in secondary_rows)
    wide = bool(aspects and max(aspects) >= 2.8)
    partial = "partial_full_observation_cluster" in roles
    duplicate = "same_object_duplicate_candidates" in roles
    active = sum(1 for flag in (boundary, wide, partial, duplicate) if flag)
    if active > 1:
        return "mixed_secondary_observations"
    if partial:
        return "partial_observation"
    if duplicate:
        return "duplicate_observation"
    if boundary:
        return "edge_truncated_observation"
    if wide:
        return "wide_unstable_observation"
    return "partial_observation"


def support_score_and_level(
    *,
    main_track_id: str,
    related_edges: Sequence[Mapping[str, Any]],
    secondary_det_ids: Sequence[str],
    cluster_rows: Sequence[Mapping[str, Any]],
    p3_summary: Mapping[str, Any],
) -> tuple[float, str]:
    score = 0.0
    if main_track_id:
        score += 0.25
    if any(str(row.get("merge_candidate_status", "")).endswith("candidate") for row in related_edges):
        score += 0.20
    if any(str(row.get("cluster_role", "")) == "partial_full_observation_cluster" for row in cluster_rows):
        score += 0.15
    if secondary_det_ids:
        score += 0.12
    if boolish(p3_summary.get("tracker_chose_alternative_det")):
        score += 0.08
    bridge_iou = safe_float(p3_summary.get("bridge_pair_raw_iou"))
    score += min(0.10, max(0.0, bridge_iou) * 0.15)
    if safe_int(p3_summary.get("idx_mapping_suspicious_count")) == 0:
        score += 0.10
    score = min(1.0, score)
    if score >= 0.72:
        return score, "strong"
    if score >= 0.45:
        return score, "moderate"
    return score, "weak"


def identity_status(
    support_level: str,
    multi_vehicle_confusion_risk: bool,
    secondary_det_ids: Sequence[str],
) -> str:
    if multi_vehicle_confusion_risk:
        return "same_object_hypothesis_review_required"
    if support_level == "strong" and secondary_det_ids:
        return "same_object_hypothesis_high_confidence_review_required"
    if support_level == "weak":
        return "ambiguous_object_hypothesis"
    return "same_object_hypothesis_review_required" if secondary_det_ids else "tracker_only_identity_hypothesis"


def build_object_hypotheses(
    *,
    tracks: Sequence[Mapping[str, Any]],
    association_rows: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    merge_edges: Sequence[Mapping[str, Any]],
    cluster_rows: Sequence[Mapping[str, Any]],
    provenance_rows: Sequence[Mapping[str, Any]],
    p3_summary: Mapping[str, Any],
    config: ObjectHypothesisConfig,
) -> list[dict[str, Any]]:
    from_tracklet, to_tracklet = case_tracklet_ids(config.case_id)
    main_track_id = find_main_tracker_track_id(association_rows, config)
    tracks_by_id = index_by(tracks, "tracker_track_id")
    main_track = tracks_by_id.get(main_track_id, {})
    obj_id = object_hypothesis_id(config.scene, config.case_id, main_track_id)

    primary_associations = [
        row
        for row in association_rows
        if str(row.get("scene", "") or "") == config.scene
        and str(row.get("tracker_track_id", "") or "") == main_track_id
    ]
    primary_tracklets = unique_sorted([row.get("chosen_oty1_tracklet_id", "") for row in primary_associations])
    if to_tracklet not in primary_tracklets:
        primary_tracklets.append(to_tracklet)
        primary_tracklets = unique_sorted(primary_tracklets)

    rejected_secondary_tracklets = [
        item
        for row in primary_associations
        for item in split_values(row.get("rejected_neighbor_oty1_tracklet_ids"))
    ]
    secondary_tracklets = unique_sorted([from_tracklet, *rejected_secondary_tracklets])

    state_rows_by_tracklet: dict[str, list[Mapping[str, Any]]] = {}
    for row in oty1_state_rows:
        if str(row.get("scene", "") or "") != config.scene:
            continue
        state_rows_by_tracklet.setdefault(str(row.get("tracklet_candidate_id", "") or ""), []).append(row)

    primary_det_ids = unique_sorted([row.get("chosen_det_id", "") for row in primary_associations])
    secondary_det_ids = unique_sorted(
        [
            row.get("det_id", "")
            for tracklet in secondary_tracklets
            for row in state_rows_by_tracklet.get(tracklet, [])
        ]
        + [item for row in primary_associations for item in split_values(row.get("rejected_neighbor_det_ids"))]
    )
    cluster_rows_for_object = [
        row
        for row in cluster_rows
        if set(split_values(row.get("det_ids"))) & (set(primary_det_ids) | set(secondary_det_ids))
    ]
    primary_clusters = [
        row.get("observation_cluster_id", "")
        for row in cluster_rows_for_object
        if set(split_values(row.get("tracked_det_ids"))) & set(primary_det_ids)
    ]
    secondary_clusters = [
        row.get("observation_cluster_id", "")
        for row in cluster_rows_for_object
        if set(split_values(row.get("det_ids"))) & set(secondary_det_ids)
    ]
    related_edges = related_edges_for_tracklets(
        merge_edges,
        unique_sorted([*primary_tracklets, *secondary_tracklets]),
        config.scene,
    )
    secondary_rows = [
        row
        for tracklet in secondary_tracklets
        for row in state_rows_by_tracklet.get(tracklet, [])
        if str(row.get("det_id", "") or "") in set(secondary_det_ids)
    ]
    support_score, support_level = support_score_and_level(
        main_track_id=main_track_id,
        related_edges=related_edges,
        secondary_det_ids=secondary_det_ids,
        cluster_rows=cluster_rows_for_object,
        p3_summary=p3_summary,
    )
    partial_full = any(
        str(row.get("cluster_role", "")) == "partial_full_observation_cluster"
        for row in cluster_rows_for_object
    ) or any("partial_to_full" in str(row.get("merge_candidate_status", "")) for row in related_edges)
    duplicate = any(safe_int(row.get("cluster_size")) > 1 for row in cluster_rows_for_object)
    boundary = any(boolish(row.get("boundary_contact_any")) for row in cluster_rows_for_object) or any(
        boolish(row.get("touch_any")) for row in secondary_rows
    )
    multi_vehicle = any(
        str(row.get("cluster_risk_status", "")) == "review_multi_vehicle_ambiguity"
        or str(row.get("cluster_role", "")) == "ambiguous_multi_vehicle_cluster"
        for row in cluster_rows_for_object
    ) or bool(duplicate and secondary_det_ids)
    artifact = any(str(row.get("cluster_role", "")) == "detector_artifact_cluster" for row in cluster_rows_for_object)

    frames = [
        safe_int(row.get("optical_frame_num"))
        for row in [*primary_associations, *secondary_rows]
        if str(row.get("optical_frame_num", "")).strip()
    ]
    ident_status = identity_status(support_level, multi_vehicle, secondary_det_ids)
    recommended = (
        "do_not_use_for_oty2"
        if not main_track_id
        else "main_track_with_uncertainty_handoff"
        if secondary_det_ids and safe_int(p3_summary.get("idx_mapping_suspicious_count")) == 0
        else "main_track_only"
    )
    if not main_track_id and secondary_det_ids:
        recommended = "tracklet_stitching_review_before_oty2"

    return [
        {
            "scene": config.scene,
            "object_hypothesis_id": obj_id,
            "case_id": config.case_id,
            "frame_start": min(frames) if frames else "",
            "frame_end": max(frames) if frames else "",
            "main_tracker_name": config.tracker_name,
            "main_tracker_track_id": main_track_id,
            "main_tracker_frame_start": main_track.get("frame_start", ""),
            "main_tracker_frame_end": main_track.get("frame_end", ""),
            "main_tracker_detection_count": main_track.get("detection_count", ""),
            "primary_tracklet_ids": join_values(primary_tracklets),
            "secondary_tracklet_ids": join_values(secondary_tracklets),
            "primary_det_ids": join_values(primary_det_ids),
            "secondary_det_ids": join_values(secondary_det_ids),
            "primary_observation_cluster_ids": join_values(primary_clusters),
            "secondary_observation_cluster_ids": join_values(secondary_clusters),
            "related_oty1a_merge_edge_ids": join_values([row.get("merge_edge_id", "") for row in related_edges]),
            "related_oty1a_statuses": join_values([row.get("merge_candidate_status", "") for row in related_edges]),
            "same_object_support_level": support_level,
            "same_object_support_score_proxy": fmt_float(support_score),
            "main_track_stability_status": track_stability_status(main_track),
            "secondary_observation_role": secondary_role(secondary_rows, cluster_rows_for_object),
            "partial_full_transition_present": partial_full,
            "duplicate_observation_present": duplicate,
            "boundary_truncation_present": boundary,
            "multi_vehicle_confusion_risk": multi_vehicle,
            "detector_artifact_risk": artifact,
            "tracker_chose_bridge_source_det": boolish(p3_summary.get("tracker_chose_bridge_source_det")),
            "tracker_chose_alternative_det": boolish(p3_summary.get("tracker_chose_alternative_det")),
            "bbox_provenance_status_summary": provenance_summary(provenance_rows, primary_det_ids),
            "idx_mapping_suspicious_count": safe_int(p3_summary.get("idx_mapping_suspicious_count")),
            "recommended_use_for_oty2": recommended,
            "identity_status": ident_status,
            "review_required": ident_status != "tracker_only_identity_hypothesis",
            "runtime_source_policy": RUNTIME_SOURCE_POLICY,
        }
    ]


def rows_by_frame(rows: Sequence[Mapping[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            out.setdefault(frame, []).append(dict(row))
    return out


def cluster_lookup(cluster_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in cluster_rows:
        for det_id in split_values(row.get("det_ids")):
            out[det_id] = dict(row)
    return out


def choose_primary_for_frame(
    frame: int,
    main_track_id: str,
    primary_tracklets: Sequence[str],
    assignments_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
    state_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    for row in assignments_by_frame.get(frame, []):
        if str(row.get("tracker_track_id", "") or "") == main_track_id:
            return normalize_association_primary(row)
    for row in state_by_frame.get(frame, []):
        if str(row.get("tracklet_candidate_id", "") or "") in set(primary_tracklets):
            return dict(row)
    return {}


def normalize_association_primary(row: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a P3 association-choice row to generic detection-like fields."""

    return {
        **dict(row),
        "det_id": row.get("chosen_det_id", ""),
        "tracklet_candidate_id": row.get("chosen_oty1_tracklet_id", ""),
        "confidence": row.get("chosen_confidence", ""),
        "bbox_x1": row.get("chosen_raw_bbox_x1", row.get("bbox_x1", "")),
        "bbox_y1": row.get("chosen_raw_bbox_y1", row.get("bbox_y1", "")),
        "bbox_x2": row.get("chosen_raw_bbox_x2", row.get("bbox_x2", "")),
        "bbox_y2": row.get("chosen_raw_bbox_y2", row.get("bbox_y2", "")),
    }


def frame_state_statuses(
    primary: Mapping[str, Any],
    secondary_rows: Sequence[Mapping[str, Any]],
    cluster: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> tuple[str, str, str, str, str, bool]:
    has_primary = bool(str(primary.get("det_id", "") or ""))
    has_secondary = bool(secondary_rows)
    cluster_role = str(cluster.get("cluster_role", "") or "")
    cluster_risk = str(cluster.get("cluster_risk_status", "") or "")
    bbox_status = str(provenance.get("bbox_provenance_status", "") or "")

    if has_primary:
        visibility = "visible_main_observation"
    elif has_secondary:
        visibility = "missing_main_with_secondary"
    else:
        visibility = "missing_observation"
    if has_secondary and not has_primary:
        visibility = "partial_secondary_observation"
    if boolish(cluster.get("boundary_contact_any")) and not has_primary:
        visibility = "edge_truncated_observation"

    if not has_primary and not has_secondary:
        uncertainty = "high_uncertainty"
    elif cluster_risk in {"review_multi_vehicle_ambiguity", "review_detector_artifact"}:
        uncertainty = "high_uncertainty"
    elif has_secondary or cluster_role == "partial_full_observation_cluster" or bbox_status not in {"", "raw_bbox_preserved"}:
        uncertainty = "moderate_uncertainty"
    else:
        uncertainty = "low_uncertainty"

    if cluster_role == "partial_full_observation_cluster" and has_primary and has_secondary:
        partial_state = "mixed_partial_full_observations"
    elif cluster_role == "partial_full_observation_cluster":
        partial_state = "partial_to_full_transition"
    else:
        partial_state = "none"
    boundary_state = "boundary_truncation_present" if boolish(cluster.get("boundary_contact_any")) else "none"
    multi_state = "multiple_observations" if has_secondary else "single_observation" if has_primary else "missing_observation"
    if has_primary and uncertainty == "low_uncertainty":
        weight = "primary_track_high"
    elif has_primary:
        weight = "primary_track_with_uncertainty"
    elif has_secondary:
        weight = "secondary_hint_only"
    else:
        weight = "do_not_use"
    return visibility, uncertainty, partial_state, boundary_state, multi_state, uncertainty != "low_uncertainty"


def build_object_frame_state_timeseries(
    *,
    object_rows: Sequence[Mapping[str, Any]],
    association_rows: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    cluster_rows: Sequence[Mapping[str, Any]],
    provenance_rows: Sequence[Mapping[str, Any]],
    config: ObjectHypothesisConfig,
) -> list[dict[str, Any]]:
    if not object_rows:
        return []
    obj = object_rows[0]
    obj_id = str(obj.get("object_hypothesis_id", "") or "")
    main_track_id = str(obj.get("main_tracker_track_id", "") or "")
    primary_tracklets = split_values(obj.get("primary_tracklet_ids"))
    secondary_tracklets = set(split_values(obj.get("secondary_tracklet_ids")))
    assignments_by_frame = rows_by_frame(association_rows)
    state_by_frame = rows_by_frame([row for row in oty1_state_rows if str(row.get("scene", "") or "") == config.scene])
    provenance_by_det = index_by(provenance_rows, "det_id")
    cluster_by_det = cluster_lookup(cluster_rows)

    secondary_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in oty1_state_rows:
        if str(row.get("scene", "") or "") != config.scene:
            continue
        if str(row.get("tracklet_candidate_id", "") or "") in secondary_tracklets:
            frame = parse_int(row.get("optical_frame_num"))
            if frame is not None:
                secondary_by_frame.setdefault(frame, []).append(dict(row))
    for row in association_rows:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is None:
            continue
        for det_id in split_values(row.get("rejected_neighbor_det_ids")):
            if any(str(existing.get("det_id", "") or "") == det_id for existing in secondary_by_frame.get(frame, [])):
                continue
            secondary_by_frame.setdefault(frame, []).append({"scene": config.scene, "optical_frame_num": frame, "det_id": det_id})

    frames = sorted(
        set(assignments_by_frame)
        | set(secondary_by_frame)
        | {safe_int(row.get("optical_frame_num")) for rows in state_by_frame.values() for row in rows if str(row.get("tracklet_candidate_id", "") or "") in set(primary_tracklets)}
    )
    start = parse_int(obj.get("frame_start"))
    end = parse_int(obj.get("frame_end"))
    if start is not None and end is not None:
        frames = [frame for frame in frames if start <= frame <= end]

    out: list[dict[str, Any]] = []
    for frame in frames:
        primary = choose_primary_for_frame(frame, main_track_id, primary_tracklets, assignments_by_frame, state_by_frame)
        primary_det = str(primary.get("det_id", "") or "")
        secondary_rows = sorted(secondary_by_frame.get(frame, []), key=lambda row: str(row.get("det_id", "")))
        secondary_det_ids = [str(row.get("det_id", "") or "") for row in secondary_rows if str(row.get("det_id", "") or "")]
        cluster = cluster_by_det.get(primary_det, {})
        if not cluster and secondary_det_ids:
            cluster = cluster_by_det.get(secondary_det_ids[0], {})
        provenance = provenance_by_det.get(primary_det, {})
        primary_box = bbox_from_row(primary)
        tracker_box = bbox_from_row(provenance, "tracker_output_bbox")
        visibility, uncertainty, partial_state, boundary_state, multi_state, review = frame_state_statuses(
            primary, secondary_rows, cluster, provenance
        )
        out.append(
            {
                "scene": config.scene,
                "object_hypothesis_id": obj_id,
                "optical_frame_num": frame,
                "main_tracker_track_id": main_track_id,
                "primary_det_id": primary_det,
                "secondary_det_ids": join_values(secondary_det_ids),
                "observation_cluster_id": cluster.get("observation_cluster_id", ""),
                "primary_bbox_x1": "" if primary_box is None else primary_box.x1,
                "primary_bbox_y1": "" if primary_box is None else primary_box.y1,
                "primary_bbox_x2": "" if primary_box is None else primary_box.x2,
                "primary_bbox_y2": "" if primary_box is None else primary_box.y2,
                "primary_bbox_center_x": "" if primary_box is None else primary_box.cx,
                "primary_bbox_center_y": "" if primary_box is None else primary_box.cy,
                "primary_bbox_w": "" if primary_box is None else primary_box.width,
                "primary_bbox_h": "" if primary_box is None else primary_box.height,
                "primary_confidence": fmt_float(primary.get("confidence")),
                "secondary_bbox_summary": bbox_summary(secondary_rows),
                "tracker_state_bbox_x1": "" if tracker_box is None else tracker_box.x1,
                "tracker_state_bbox_y1": "" if tracker_box is None else tracker_box.y1,
                "tracker_state_bbox_x2": "" if tracker_box is None else tracker_box.x2,
                "tracker_state_bbox_y2": "" if tracker_box is None else tracker_box.y2,
                "bbox_provenance_status": provenance.get("bbox_provenance_status", ""),
                "cluster_role": cluster.get("cluster_role", ""),
                "cluster_risk_status": cluster.get("cluster_risk_status", ""),
                "state_visibility_status": visibility,
                "state_uncertainty_status": uncertainty,
                "partial_full_transition_state": partial_state,
                "boundary_truncation_state": boundary_state,
                "multi_observation_state": multi_state,
                "recommended_oty2_weight": (
                    "primary_track_high"
                    if primary_det and uncertainty == "low_uncertainty"
                    else "primary_track_with_uncertainty"
                    if primary_det
                    else "secondary_hint_only"
                    if secondary_det_ids
                    else "do_not_use"
                ),
                "review_required": review,
            }
        )
    return out


def evidence_payload(
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    p3_summary: Mapping[str, Any],
) -> dict[str, Any]:
    hypotheses: list[dict[str, Any]] = []
    for obj in object_rows:
        frame_172 = [row for row in frame_rows if safe_int(row.get("optical_frame_num")) == 172]
        frame_172_row = frame_172[0] if frame_172 else {}
        hypotheses.append(
            {
                "object_hypothesis_id": obj.get("object_hypothesis_id", ""),
                "identity_status": obj.get("identity_status", ""),
                "same_object_support_level": obj.get("same_object_support_level", ""),
                "main_track_evidence": [
                    f"{obj.get('main_tracker_track_id', '')} is the main tracker trajectory with {obj.get('main_tracker_detection_count', '')} tracked detections from frame {obj.get('main_tracker_frame_start', '')} to {obj.get('main_tracker_frame_end', '')}.",
                    f"Primary tracklet ids: {obj.get('primary_tracklet_ids', '')}.",
                    f"Frame 172 primary_det_id={frame_172_row.get('primary_det_id', '')}.",
                ],
                "secondary_observation_evidence": [
                    f"Secondary tracklet ids: {obj.get('secondary_tracklet_ids', '')}.",
                    f"Frame 172 secondary_det_ids={frame_172_row.get('secondary_det_ids', '')}.",
                    "Secondary observations are retained as same-object observation hypotheses, not discarded as independent physical objects.",
                ],
                "observation_cluster_evidence": [
                    f"Frame 172 cluster role={frame_172_row.get('cluster_role', '')}, risk={frame_172_row.get('cluster_risk_status', '')}.",
                    f"tracker_chose_bridge_source_det={str(obj.get('tracker_chose_bridge_source_det', '')).lower()}, tracker_chose_alternative_det={str(obj.get('tracker_chose_alternative_det', '')).lower()}.",
                ],
                "OTY1a_fragment_hint_evidence": [
                    f"related edge ids: {obj.get('related_oty1a_merge_edge_ids', '')}.",
                    f"related statuses: {obj.get('related_oty1a_statuses', '')}.",
                ],
                "counter_evidence": [
                    f"172_001 -> 173_001 raw continuity is stronger than 172_002 -> 173_001 ({p3_summary.get('pair_172_001_173_001_raw_iou', '')}/{p3_summary.get('pair_172_001_173_001_center_distance_px', '')} vs {p3_summary.get('pair_172_002_173_001_raw_iou', '')}/{p3_summary.get('pair_172_002_173_001_center_distance_px', '')}).",
                    "Tracker did not assign the 0039 fragment to the same tracker id, so this remains review-required.",
                ],
                "risk_factors": [
                    f"main_track_stability_status={obj.get('main_track_stability_status', '')}.",
                    f"secondary_observation_role={obj.get('secondary_observation_role', '')}.",
                    f"multi_vehicle_confusion_risk={str(obj.get('multi_vehicle_confusion_risk', '')).lower()}.",
                    f"idx_mapping_suspicious_count={obj.get('idx_mapping_suspicious_count', '')}.",
                ],
                "recommended_handoff": (
                    "Use the main track for temporal continuity and pass secondary observations as uncertainty / partial-full transition state. "
                    "Do not generate SAR band in P4."
                ),
            }
        )
    return {
        "scene": object_rows[0].get("scene", "") if object_rows else "",
        "case_id": object_rows[0].get("case_id", "") if object_rows else "",
        "confirmed_identity": False,
        "hypotheses": hypotheses,
        "boundary_flags": {
            "posthoc_sources_used_for_runtime_tracking": False,
            "sar_alignment_entered": False,
            "sar_band_entered": False,
            "sar_gt_coverage_entered": False,
            "annotation_proposal_entered": False,
            "identity_truth_claimed": False,
        },
    }


def render_evidence_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# OTY1t Object Hypothesis Evidence",
        "",
        "## Boundary",
        "",
        "- Outputs are object-level optical hypotheses.",
        "- confirmed_identity=false",
        "- posthoc_sources_used_for_runtime_tracking=false",
        "- sar_alignment_entered=false",
        "- sar_band_entered=false",
        "- sar_gt_coverage_entered=false",
        "- annotation_proposal_entered=false",
        "- identity_truth_claimed=false",
        "",
    ]
    for row in payload.get("hypotheses", []):
        if not isinstance(row, Mapping):
            continue
        lines.extend(
            [
                f"## {row.get('object_hypothesis_id', '')}",
                "",
                f"- same_object_support_level: `{row.get('same_object_support_level', '')}`",
                f"- identity_status: `{row.get('identity_status', '')}`",
                "",
            ]
        )
        for section in (
            "main_track_evidence",
            "secondary_observation_evidence",
            "observation_cluster_evidence",
            "OTY1a_fragment_hint_evidence",
            "counter_evidence",
            "risk_factors",
        ):
            lines.append(f"### {section}")
            for item in row.get(section, []):
                lines.append(f"- {item}")
            lines.append("")
        lines.extend(["### recommended_handoff", f"- {row.get('recommended_handoff', '')}", ""])
    return "\n".join(lines)


def build_summary(
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    cluster_rows: Sequence[Mapping[str, Any]],
    related_edge_count: int,
) -> dict[str, Any]:
    obj = object_rows[0] if object_rows else {}
    frame_172 = [row for row in frame_rows if safe_int(row.get("optical_frame_num")) == 172]
    frame_172_row = frame_172[0] if frame_172 else {}
    return {
        "scene": obj.get("scene", ""),
        "case_id": obj.get("case_id", ""),
        "object_hypothesis_count": len(object_rows),
        "object_frame_state_rows": len(frame_rows),
        "main_tracker_track_count_used": len({row.get("main_tracker_track_id", "") for row in object_rows if row.get("main_tracker_track_id")}),
        "secondary_observation_count": len(split_values(obj.get("secondary_det_ids"))),
        "observation_cluster_count_used": len({row.get("observation_cluster_id", "") for row in cluster_rows if row.get("observation_cluster_id")}),
        "related_oty1a_edge_count": related_edge_count,
        "strong_same_object_hypothesis_count": sum(1 for row in object_rows if row.get("same_object_support_level") == "strong"),
        "moderate_same_object_hypothesis_count": sum(1 for row in object_rows if row.get("same_object_support_level") == "moderate"),
        "ambiguous_object_hypothesis_count": sum(1 for row in object_rows if row.get("identity_status") == "ambiguous_object_hypothesis"),
        "frame_172_primary_det_id": frame_172_row.get("primary_det_id", ""),
        "frame_172_secondary_det_ids": frame_172_row.get("secondary_det_ids", ""),
        "main_tracker_track_id": obj.get("main_tracker_track_id", ""),
        "same_object_support_level_for_0039_0045": obj.get("same_object_support_level", ""),
        "recommended_use_for_oty2_for_0039_0045": obj.get("recommended_use_for_oty2", ""),
        "identity_status_for_0039_0045": obj.get("identity_status", ""),
        "posthoc_sources_used_for_runtime_tracking": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "annotation_proposal_entered": False,
        "identity_truth_claimed": False,
    }


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    def md_value(value: Any) -> Any:
        if isinstance(value, bool):
            return str(value).lower()
        return value

    fields = [
        "scene",
        "case_id",
        "object_hypothesis_count",
        "object_frame_state_rows",
        "main_tracker_track_count_used",
        "secondary_observation_count",
        "observation_cluster_count_used",
        "related_oty1a_edge_count",
        "strong_same_object_hypothesis_count",
        "moderate_same_object_hypothesis_count",
        "ambiguous_object_hypothesis_count",
        "frame_172_primary_det_id",
        "frame_172_secondary_det_ids",
        "main_tracker_track_id",
        "same_object_support_level_for_0039_0045",
        "recommended_use_for_oty2_for_0039_0045",
        "identity_status_for_0039_0045",
        "posthoc_sources_used_for_runtime_tracking",
        "sar_alignment_entered",
        "sar_band_entered",
        "sar_gt_coverage_entered",
        "annotation_proposal_entered",
        "identity_truth_claimed",
    ]
    lines = [
        "# OTY1t Object Hypothesis Summary",
        "",
        "OTY1t-P4 adds an object-level optical hypothesis layer that combines main tracker trajectories, same-frame observation clusters, secondary partial/duplicate observations, and OTY1a fragment hints. Outputs remain review-only optical object hypotheses. No confirmed identity, SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector output, training signal, or annotation proposal was introduced.",
        "",
        "## Summary Fields",
        "",
    ]
    for field in fields:
        lines.append(f"- {field}: `{md_value(summary.get(field, ''))}`")
    return "\n".join(lines) + "\n"


def render_object_graph_svg(
    path: str | Path,
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
) -> None:
    obj = object_rows[0] if object_rows else {}
    frame_172 = [row for row in frame_rows if safe_int(row.get("optical_frame_num")) == 172]
    frame_172_row = frame_172[0] if frame_172 else {}
    width = 1120
    height = 560
    obj_id = str(obj.get("object_hypothesis_id", "") or "")
    primary_dets = split_values(obj.get("primary_det_ids"))[:8]
    secondary_dets = split_values(obj.get("secondary_det_ids"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="34" font-size="18" font-family="Arial" font-weight="700" fill="#111827">OTY1t-P4 object-level hypothesis graph</text>',
        '<text x="24" y="58" font-size="13" font-family="Arial" fill="#374151">confirmed_identity=false; same_object_hypothesis_review_required; main_track_with_uncertainty_handoff</text>',
    ]
    boxes = [
        ("object_hypothesis_id", obj_id, 42, 94, 320, 70, "#dbeafe"),
        ("main tracker track", str(obj.get("main_tracker_track_id", "")), 430, 94, 260, 70, "#dcfce7"),
        ("primary dets", "; ".join(primary_dets) + ("; ..." if len(split_values(obj.get("primary_det_ids"))) > 8 else ""), 760, 94, 320, 92, "#ecfdf5"),
        ("secondary observations", "; ".join(secondary_dets[:8]) + ("; ..." if len(secondary_dets) > 8 else ""), 430, 244, 360, 98, "#fef3c7"),
        ("frame 172 cluster", f"{frame_172_row.get('observation_cluster_id', '')}: {frame_172_row.get('primary_det_id', '')} + {frame_172_row.get('secondary_det_ids', '')}", 42, 244, 320, 98, "#ffedd5"),
        ("OTY1a hint", str(obj.get("related_oty1a_statuses", "")), 430, 402, 360, 78, "#fce7f3"),
    ]
    for title, body, x, y, w, h, fill in boxes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#94a3b8"/>')
        parts.append(f'<text x="{x + 14}" y="{y + 24}" font-size="13" font-family="Arial" font-weight="700" fill="#111827">{html_escape(title)}</text>')
        for line_index, chunk in enumerate([body[i : i + 62] for i in range(0, len(body), 62)][:3]):
            parts.append(f'<text x="{x + 14}" y="{y + 46 + line_index * 18}" font-size="12" font-family="Arial" fill="#374151">{html_escape(chunk)}</text>')
    for x1, y1, x2, y2 in ((362, 128, 430, 128), (690, 128, 760, 128), (560, 164, 560, 244), (362, 292, 430, 292), (610, 342, 610, 402)):
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"/>')
    parts.insert(
        2,
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 Z" fill="#64748b"/></marker></defs>',
    )
    parts.append("</svg>")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(parts), encoding="utf-8")
