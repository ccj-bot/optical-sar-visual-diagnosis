"""Failure diagnosis helpers for OTY1t tracker audits.

These helpers only consume runtime optical tracker outputs and OTY1/OTY1a
comparison context. They do not confirm identity and do not use SAR, GT,
final/manual/oracle/review fields, selector scores, threshold tuning, training
signals, or annotation proposal labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Mapping, Sequence

from .state_features import BBox, bbox_iou, boundary_contact_features, center_distance, parse_float, parse_int


REVIEW_MERGE_STATUSES = {
    "fragment_merge_candidate",
    "overlap_shape_transition_candidate",
    "partial_to_full_box_transition_candidate",
    "needs_visual_review",
}

AMBIGUOUS_MERGE_STATUSES = {"ambiguous_competing_merge"}

OTY2_RECOMMENDATIONS = {
    "not_recommended",
    "optional_continuity_hint_only",
    "recommended_with_visual_review",
    "recommended_for_nonambiguous_tracks_only",
}


@dataclass(frozen=True)
class DiagnosisConfig:
    tracker_name: str
    track_high_thresh: float = 0.25
    neighbor_distance_px: float = 120.0
    contact_margin_px: float = 2.0
    duplicate_iou_threshold: float = 0.50


def bbox_from_assignment(row: Mapping[str, Any]) -> BBox:
    return BBox(
        parse_float(row.get("bbox_x1")) or 0.0,
        parse_float(row.get("bbox_y1")) or 0.0,
        parse_float(row.get("bbox_x2")) or 0.0,
        parse_float(row.get("bbox_y2")) or 0.0,
    )


def det_to_oty1_context(oty1_state_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    return {
        str(row.get("det_id", "")): {
            "tracklet_candidate_id": str(row.get("tracklet_candidate_id", "")),
            "identity_status": str(row.get("identity_status", "")),
        }
        for row in oty1_state_rows
        if str(row.get("det_id", ""))
    }


def oty1a_counts_by_component(oty1a_merge_edges: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for edge in oty1a_merge_edges:
        status = str(edge.get("merge_candidate_status", ""))
        for field in ("from_tracklet_candidate_id", "to_tracklet_candidate_id"):
            component = str(edge.get(field, ""))
            if not component:
                continue
            bucket = counts.setdefault(
                component,
                {
                    "related": 0,
                    "nonambiguous": 0,
                    "ambiguous": 0,
                    "shape_transition": 0,
                },
            )
            bucket["related"] += 1
            if status in REVIEW_MERGE_STATUSES:
                bucket["nonambiguous"] += 1
            if status in AMBIGUOUS_MERGE_STATUSES:
                bucket["ambiguous"] += 1
            if "transition" in status:
                bucket["shape_transition"] += 1
    return counts


def _same_frame_rows(assignments: Sequence[Mapping[str, Any]]) -> dict[int, list[Mapping[str, Any]]]:
    by_frame: dict[int, list[Mapping[str, Any]]] = {}
    for row in assignments:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            by_frame.setdefault(frame, []).append(row)
    return by_frame


def _nearest_tracked(
    unmatched: Mapping[str, Any],
    frame_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, float | str, float | str]:
    bbox = bbox_from_assignment(unmatched)
    best_track = ""
    best_distance: float | None = None
    best_iou: float | None = None
    for row in frame_rows:
        track_id = str(row.get("tracker_track_id", "") or "")
        if not track_id:
            continue
        other = bbox_from_assignment(row)
        distance = center_distance(bbox, other)
        iou = bbox_iou(bbox, other)
        if best_distance is None or distance < best_distance:
            best_track = track_id
            best_distance = distance
            best_iou = iou
    return best_track, "" if best_distance is None else best_distance, "" if best_iou is None else best_iou


def _neighbor_ambiguous(row: Mapping[str, Any], frame_rows: Sequence[Mapping[str, Any]], config: DiagnosisConfig) -> bool:
    bbox = bbox_from_assignment(row)
    det_id = str(row.get("det_id", ""))
    distances = [
        center_distance(bbox, bbox_from_assignment(other))
        for other in frame_rows
        if str(other.get("det_id", "")) != det_id
    ]
    return bool(distances and min(distances) <= config.neighbor_distance_px)


def _diagnosis_bucket(
    row: Mapping[str, Any],
    *,
    low_score: bool,
    boundary_contact: bool,
    neighbor_ambiguity: bool,
    overlaps_existing_tracker: bool,
    near_existing_tracker: bool,
    oty1_identity_status: str,
    oty1a_counts: Mapping[str, int],
) -> tuple[str, str]:
    if low_score:
        return "low_score_unmatched", "detection confidence is below tracker high threshold"
    if overlaps_existing_tracker or near_existing_tracker:
        return "duplicate_or_overlap_rejected", "unmatched bbox overlaps or is close to an existing tracker hypothesis"
    if oty1a_counts.get("shape_transition", 0) > 0:
        return "shape_transition_unmatched", "OTY1a links this component to shape or partial/full transition review"
    if neighbor_ambiguity:
        return "neighbor_ambiguous_unmatched", "same-frame optical neighbor is within ambiguity distance"
    if boundary_contact:
        return "boundary_or_truncated_unmatched", "bbox touches optical frame boundary or truncation proxy is active"
    if oty1_identity_status == "fragmented_short_track":
        return "late_fragment_unmatched", "OTY1 component is short or fragmented and tracker did not keep it active"
    confidence = parse_float(row.get("confidence")) or 0.0
    if confidence >= 0.25:
        return "tracker_threshold_or_association_miss", "confidence is sufficient but tracker association did not accept it"
    return "unexplained_unmatched", "no dominant runtime-safe optical diagnosis bucket was identified"


def build_unmatched_detection_audit(
    assignments: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    oty1a_merge_edges: Sequence[Mapping[str, Any]],
    config: DiagnosisConfig,
) -> list[dict[str, Any]]:
    context_by_det = det_to_oty1_context(oty1_state_rows)
    merge_counts = oty1a_counts_by_component(oty1a_merge_edges)
    rows_by_frame = _same_frame_rows(assignments)
    out: list[dict[str, Any]] = []
    for row in assignments:
        if not _boolish(row.get("is_unmatched_detection")):
            continue
        frame = parse_int(row.get("optical_frame_num")) or 0
        frame_rows = rows_by_frame.get(frame, [])
        bbox = bbox_from_assignment(row)
        contact = boundary_contact_features(
            bbox,
            parse_float(row.get("_frame_width")),
            parse_float(row.get("_frame_height")),
            config.contact_margin_px,
        )
        nearest_track, nearest_distance, nearest_iou = _nearest_tracked(row, frame_rows)
        near_existing = parse_float(nearest_distance) is not None and float(nearest_distance) <= config.neighbor_distance_px
        overlaps_existing = parse_float(nearest_iou) is not None and float(nearest_iou) >= config.duplicate_iou_threshold
        det_context = context_by_det.get(str(row.get("det_id", "")), {})
        component_id = det_context.get("tracklet_candidate_id", "")
        identity_status = det_context.get("identity_status", "")
        related_counts = merge_counts.get(
            component_id,
            {"related": 0, "nonambiguous": 0, "ambiguous": 0, "shape_transition": 0},
        )
        low_score = _boolish(row.get("is_low_score_detection")) or (parse_float(row.get("confidence")) or 0.0) < config.track_high_thresh
        neighbor = _neighbor_ambiguous(row, frame_rows, config)
        bucket, reason = _diagnosis_bucket(
            row,
            low_score=low_score,
            boundary_contact=bool(contact.get("touch_any") is True),
            neighbor_ambiguity=neighbor,
            overlaps_existing_tracker=overlaps_existing,
            near_existing_tracker=near_existing,
            oty1_identity_status=identity_status,
            oty1a_counts=related_counts,
        )
        out.append(
            {
                "scene": row.get("scene", ""),
                "optical_frame_num": frame,
                "det_id": row.get("det_id", ""),
                "class_name": row.get("class_name", ""),
                "confidence": row.get("confidence", ""),
                "bbox_x1": bbox.x1,
                "bbox_y1": bbox.y1,
                "bbox_x2": bbox.x2,
                "bbox_y2": bbox.y2,
                "bbox_center_x": bbox.cx,
                "bbox_center_y": bbox.cy,
                "bbox_w": bbox.width,
                "bbox_h": bbox.height,
                "bbox_area": bbox.area,
                "bbox_aspect": "" if bbox.aspect is None else bbox.aspect,
                "bottom_y": bbox.y2,
                "is_low_score_detection": low_score,
                "boundary_contact": bool(contact.get("touch_any") is True),
                "neighbor_ambiguity_proxy": neighbor,
                "nearest_tracked_track_id": nearest_track,
                "nearest_tracked_center_distance_px": nearest_distance,
                "nearest_tracked_iou": nearest_iou,
                "overlaps_existing_tracker": overlaps_existing,
                "near_existing_tracker": near_existing,
                "oty1_component_id_if_available": component_id,
                "oty1_identity_status_if_available": identity_status,
                "oty1a_related_merge_edge_count": related_counts.get("related", 0),
                "oty1a_related_nonambiguous_edge_count": related_counts.get("nonambiguous", 0),
                "oty1a_related_ambiguous_edge_count": related_counts.get("ambiguous", 0),
                "diagnosis_bucket": bucket,
                "diagnosis_reason": reason,
            }
        )
    return sorted(out, key=lambda item: (parse_int(item.get("optical_frame_num")) or 0, str(item.get("det_id", ""))))


def build_failure_bucket_summary(
    unmatched_rows: Sequence[Mapping[str, Any]],
    scene: str,
    tracker_name: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in unmatched_rows:
        grouped.setdefault(str(row.get("diagnosis_bucket", "")), []).append(row)
    out: list[dict[str, Any]] = []
    for bucket, rows in sorted(grouped.items()):
        confidences = _float_values(rows, "confidence")
        distances = _float_values(rows, "nearest_tracked_center_distance_px")
        ious = _float_values(rows, "nearest_tracked_iou")
        row_count = len(rows)
        out.append(
            {
                "scene": scene,
                "tracker_name": tracker_name,
                "diagnosis_bucket": bucket,
                "row_count": row_count,
                "mean_confidence": mean(confidences) if confidences else "",
                "median_confidence": median(confidences) if confidences else "",
                "mean_nearest_tracked_distance_px": mean(distances) if distances else "",
                "mean_nearest_tracked_iou": mean(ious) if ious else "",
                "boundary_contact_rate": _rate(rows, "boundary_contact"),
                "neighbor_ambiguity_rate": _rate(rows, "neighbor_ambiguity_proxy"),
                "low_score_rate": _rate(rows, "is_low_score_detection"),
                "oty1a_related_rate": sum(1 for row in rows if (parse_int(row.get("oty1a_related_merge_edge_count")) or 0) > 0) / row_count,
                "interpretation": _bucket_interpretation(bucket),
                "recommended_next_action": _bucket_action(bucket),
            }
        )
    return out


def build_case_0039_0045_failure_trace(
    assignments: Sequence[Mapping[str, Any]],
    tracks: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    oty1a_merge_edges: Sequence[Mapping[str, Any]],
    unmatched_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    det_to_assignment = {str(row.get("det_id", "")): row for row in assignments if str(row.get("det_id", ""))}
    fragments = _fragment_det_ids(oty1_state_rows)
    dets_0039 = fragments.get("oty1_tracklet_0039", [])
    dets_0045 = fragments.get("oty1_tracklet_0045", [])
    tracks_0039 = sorted(
        {
            str(det_to_assignment.get(det, {}).get("tracker_track_id", ""))
            for det in dets_0039
            if str(det_to_assignment.get(det, {}).get("tracker_track_id", ""))
        }
    )
    tracks_0045 = sorted(
        {
            str(det_to_assignment.get(det, {}).get("tracker_track_id", ""))
            for det in dets_0045
            if str(det_to_assignment.get(det, {}).get("tracker_track_id", ""))
        }
    )
    shared = sorted(set(tracks_0039) & set(tracks_0045))
    unmatched_0039 = [det for det in dets_0039 if _boolish(det_to_assignment.get(det, {}).get("is_unmatched_detection"))]
    unmatched_0045 = [det for det in dets_0045 if _boolish(det_to_assignment.get(det, {}).get("is_unmatched_detection"))]
    case_edge = next(
        (
            edge
            for edge in oty1a_merge_edges
            if str(edge.get("from_tracklet_candidate_id", "")) == "oty1_tracklet_0039"
            and str(edge.get("to_tracklet_candidate_id", "")) == "oty1_tracklet_0045"
        ),
        {},
    )
    track_0098 = next((row for row in tracks if str(row.get("tracker_track_id", "")) == "bt_0098"), {})
    frame_values_0039 = _frames_for_dets(oty1_state_rows, "oty1_tracklet_0039")
    frame_values_0045 = _frames_for_dets(oty1_state_rows, "oty1_tracklet_0045")
    interval_start = min(frame_values_0039) if frame_values_0039 else None
    interval_end = max(frame_values_0045) if frame_values_0045 else None
    between_unmatched = []
    if interval_start is not None and interval_end is not None:
        between_unmatched = [
            row
            for row in unmatched_rows
            if interval_start <= (parse_int(row.get("optical_frame_num")) or -1) <= interval_end
        ]
    related_tracks = set(tracks_0039) | set(tracks_0045)
    related_events = [
        event
        for event in events
        if str(event.get("tracker_track_id", "")) in related_tracks
        or str(event.get("related_tracker_track_id", "")) in related_tracks
    ]
    failure_mode = "tracker_fragment_start_after_partial_component"
    if not dets_0039:
        failure_mode = "oty1_0039_missing_from_comparison_context"
    elif unmatched_0039 and tracks_0045:
        failure_mode = "partial_component_unmatched_then_later_full_component_tracked"
    elif not shared:
        failure_mode = "tracker_association_did_not_bridge_transition"
    return {
        "tracker_connected": bool(shared),
        "confirmed_identity": False,
        "oty2_continuity_hint": bool(shared),
        "visual_review_required": True,
        "failure_mode": failure_mode,
        "oty1a_status": str(case_edge.get("merge_candidate_status", "")),
        "oty1a_partial_to_full_reason": "OTY1a marks 0039/0045 as partial/full because endpoint overlap, bridge IoU, boundary/shape transition proxies, and temporal overlap support review without proving identity.",
        "byte_tracker_not_connected_reason": "ByteTrack did not assign any 0039 detections to the same tracker id as 0045; the tracked hypothesis starts later on the fuller box sequence.",
        "track_ids_for_0039": tracks_0039,
        "track_ids_for_0045": tracks_0045,
        "shared_tracker_track_ids": shared,
        "detection_count_0039": len(dets_0039),
        "detection_count_0045": len(dets_0045),
        "0039_entered_oty0_detection_table": bool(dets_0039 and all(det in det_to_assignment for det in dets_0039)),
        "0039_unmatched_detection_count": len(unmatched_0039),
        "0039_unmatched_det_ids": unmatched_0039,
        "0045_unmatched_detection_count": len(unmatched_0045),
        "0045_unmatched_det_ids": unmatched_0045,
        "bt_0098_frame_start": track_0098.get("frame_start", ""),
        "bt_0098_frame_end": track_0098.get("frame_end", ""),
        "bt_0098_detection_count": track_0098.get("detection_count", ""),
        "unmatched_between_0039_0045_count": len(between_unmatched),
        "unmatched_between_0039_0045_det_ids": [str(row.get("det_id", "")) for row in between_unmatched],
        "duplicate_or_competing_event_count": sum(
            1
            for event in related_events
            if str(event.get("event_type", "")) in {"duplicate_track_overlap", "possible_id_switch", "fragment_bridge", "ambiguous_association"}
        ),
        "related_event_types": sorted({str(event.get("event_type", "")) for event in related_events}),
        "merge_candidate_score_not_selector": case_edge.get("merge_candidate_score_not_selector", ""),
        "bridge_iou_proxy": case_edge.get("bridge_iou_proxy", ""),
        "endpoint_center_distance_px": case_edge.get("endpoint_center_distance_px", ""),
    }


def write_case_0039_0045_failure_trace_markdown(
    path: str,
    trace: Mapping[str, Any],
) -> None:
    from pathlib import Path

    lines = [
        "# OTY1t 0039/0045 Failure Trace",
        "",
        "## Required Conclusion",
        "",
        f"- tracker_connected = `{str(trace.get('tracker_connected', False)).lower()}`",
        "- confirmed_identity = `false`",
        f"- oty2_continuity_hint = `{str(trace.get('oty2_continuity_hint', False)).lower()}`",
        f"- visual_review_required = `{str(trace.get('visual_review_required', True)).lower()}`",
        f"- failure_mode = `{trace.get('failure_mode', '')}`",
        "",
        "## Why OTY1a Marked Partial-To-Full",
        "",
        str(trace.get("oty1a_partial_to_full_reason", "")),
        "",
        "## Why ByteTrack Did Not Connect Them",
        "",
        str(trace.get("byte_tracker_not_connected_reason", "")),
        "",
        "## Detection And Tracker Facts",
        "",
        f"- OTY1a status: `{trace.get('oty1a_status', '')}`",
        f"- 0039 entered OTY0 detection table: `{str(trace.get('0039_entered_oty0_detection_table', False)).lower()}`",
        f"- 0039 unmatched detection count: `{trace.get('0039_unmatched_detection_count', 0)}`",
        f"- 0039 unmatched det ids: `{trace.get('0039_unmatched_det_ids', [])}`",
        f"- 0045 tracker ids: `{trace.get('track_ids_for_0045', [])}`",
        f"- 0045 unmatched detection count: `{trace.get('0045_unmatched_detection_count', 0)}`",
        f"- `bt_0098` frame_start: `{trace.get('bt_0098_frame_start', '')}`",
        f"- `bt_0098` frame_end: `{trace.get('bt_0098_frame_end', '')}`",
        f"- `bt_0098` detection_count: `{trace.get('bt_0098_detection_count', '')}`",
        f"- unmatched detections between 0039/0045 span: `{trace.get('unmatched_between_0039_0045_count', 0)}`",
        f"- unmatched det ids between span: `{trace.get('unmatched_between_0039_0045_det_ids', [])}`",
        f"- duplicate/competing event count: `{trace.get('duplicate_or_competing_event_count', 0)}`",
        f"- related event types: `{trace.get('related_event_types', [])}`",
        "",
        "## Boundary",
        "",
        "This is a tracker failure diagnosis and OTY2 continuity-hint audit only. It is not confirmed identity, SAR alignment, SAR band generation, SAR GT coverage, SAR evidence sampling, selector output, training signal, or annotation proposal.",
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_case_failure_trace_svg(path: str, trace: Mapping[str, Any]) -> None:
    from html import escape as html_escape
    from pathlib import Path

    width = 980
    height = 260
    connected = str(trace.get("tracker_connected", False)).lower()
    hint = str(trace.get("oty2_continuity_hint", False)).lower()
    parts = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        '<text x="24" y="34" font-size="22" fill="#111827">OTY1t 0039/0045 Failure Trace</text>',
        '<text x="24" y="62" font-size="13" fill="#64748b">Tracker ids are optical identity hypotheses only; confirmed_identity=false.</text>',
        f'<text x="24" y="98" font-size="15" fill="#111827">tracker_connected={connected} | oty2_continuity_hint={hint} | visual_review_required=true</text>',
        f'<text x="24" y="126" font-size="13" fill="#b45309">failure_mode={html_escape(str(trace.get("failure_mode", "")))}</text>',
        f'<text x="24" y="154" font-size="12" fill="#475569">0039 unmatched={html_escape(str(trace.get("0039_unmatched_detection_count", 0)))} | 0045 trackers={html_escape(str(trace.get("track_ids_for_0045", [])))} | bt_0098={html_escape(str(trace.get("bt_0098_frame_start", "")))}-{html_escape(str(trace.get("bt_0098_frame_end", "")))}</text>',
        f'<text x="24" y="182" font-size="12" fill="#475569">OTY1a status={html_escape(str(trace.get("oty1a_status", "")))} | bridge_iou_proxy={html_escape(str(trace.get("bridge_iou_proxy", "")))} | endpoint_distance={html_escape(str(trace.get("endpoint_center_distance_px", "")))}</text>',
        '<text x="24" y="222" font-size="12" fill="#64748b">No SAR frame, SAR GT, SAR evidence, final boxes, selector, training, or annotation proposal.</text>',
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def event_distribution(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for event in events:
        event_type = str(event.get("event_type", ""))
        out[event_type] = out.get(event_type, 0) + 1
    return dict(sorted(out.items()))


def oty2_stable_input_recommendation(summary: Mapping[str, Any]) -> str:
    if not _boolish(summary.get("tracker_real_run")):
        return "not_recommended"
    detection_rows = parse_int(summary.get("detection_rows_in")) or 0
    unmatched = parse_int(summary.get("unmatched_detection_rows")) or 0
    duplicate = parse_int(summary.get("duplicate_track_overlap_count")) or 0
    switches = parse_int(summary.get("possible_id_switch_count")) or 0
    ambiguous = parse_int(summary.get("ambiguous_hypothesis_count")) or 0
    unmatched_rate = unmatched / detection_rows if detection_rows else 1.0
    if unmatched_rate > 0.20 or duplicate > 0 or switches > 2:
        return "optional_continuity_hint_only"
    if ambiguous > 0 or switches > 0:
        return "recommended_with_visual_review"
    return "recommended_for_nonambiguous_tracks_only"


def cross_tracker_row(summary: Mapping[str, Any]) -> dict[str, Any]:
    detection_rows = parse_int(summary.get("detection_rows_in")) or 0
    unmatched = parse_int(summary.get("unmatched_detection_rows")) or 0
    facts = summary.get("tracker_dependency_facts", {})
    if not isinstance(facts, Mapping):
        facts = {}
    recommendation = oty2_stable_input_recommendation(summary)
    if recommendation not in OTY2_RECOMMENDATIONS:
        recommendation = "not_recommended"
    return {
        "scene": summary.get("scene", ""),
        "tracker_name": summary.get("tracker_name", ""),
        "tracker_real_run": bool(summary.get("tracker_real_run") is True),
        "dependency_status": summary.get("dependency_status", facts.get("dependency_status", "")),
        "detection_rows_in": detection_rows,
        "tracked_assignment_rows": parse_int(summary.get("tracked_assignment_rows")) or 0,
        "unmatched_detection_rows": unmatched,
        "unmatched_rate": unmatched / detection_rows if detection_rows else "",
        "tracker_track_count": parse_int(summary.get("tracker_track_count")) or 0,
        "stable_hypothesis_count": parse_int(summary.get("stable_hypothesis_count")) or 0,
        "fragmented_hypothesis_count": parse_int(summary.get("fragmented_hypothesis_count")) or 0,
        "ambiguous_hypothesis_count": parse_int(summary.get("ambiguous_hypothesis_count")) or 0,
        "short_hypothesis_count": parse_int(summary.get("short_hypothesis_count")) or 0,
        "duplicate_overlap_count": parse_int(summary.get("duplicate_track_overlap_count")) or 0,
        "possible_id_switch_count": parse_int(summary.get("possible_id_switch_count")) or 0,
        "lost_event_count": parse_int(summary.get("lost_event_count")) or 0,
        "reactivated_event_count": parse_int(summary.get("reactivated_event_count")) or 0,
        "case_0039_0045_tracker_connected": bool(summary.get("case_0039_0045_tracker_connected") is True),
        "case_0039_0045_confirmed_identity": False,
        "case_0039_0045_oty2_continuity_hint": bool(
            isinstance(summary.get("case_0039_0045"), Mapping)
            and summary.get("case_0039_0045", {}).get("oty2_continuity_hint") is True
        ),
        "oty2_stable_input_recommendation": recommendation,
        "largest_blocker": summary.get("largest_blocker", ""),
    }


def _fragment_det_ids(oty1_state_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    fragments = {"oty1_tracklet_0039": [], "oty1_tracklet_0045": []}
    for row in sorted(oty1_state_rows, key=lambda item: (parse_int(item.get("optical_frame_num")) or 0, str(item.get("det_id", "")))):
        tracklet_id = str(row.get("tracklet_candidate_id", ""))
        if tracklet_id in fragments:
            fragments[tracklet_id].append(str(row.get("det_id", "")))
    return fragments


def _frames_for_dets(oty1_state_rows: Sequence[Mapping[str, Any]], tracklet_id: str) -> list[int]:
    frames = [
        parse_int(row.get("optical_frame_num"))
        for row in oty1_state_rows
        if str(row.get("tracklet_candidate_id", "")) == tracklet_id
    ]
    return sorted(value for value in frames if value is not None)


def _float_values(rows: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    values = [parse_float(row.get(field)) for row in rows]
    return [float(value) for value in values if value is not None]


def _rate(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    return sum(1 for row in rows if _boolish(row.get(field))) / len(rows) if rows else 0.0


def _bucket_interpretation(bucket: str) -> str:
    return {
        "low_score_unmatched": "Tracker rejected low-confidence detections; detector confidence is the first limiting factor.",
        "neighbor_ambiguous_unmatched": "Nearby same-frame vehicles create association ambiguity.",
        "boundary_or_truncated_unmatched": "Boundary contact or truncation proxy likely weakens tracker continuity.",
        "duplicate_or_overlap_rejected": "Tracker kept a competing nearby hypothesis and rejected this duplicate/overlap detection.",
        "shape_transition_unmatched": "Partial/full or shape transition review context explains the unmatched row.",
        "late_fragment_unmatched": "Short or late optical fragments were not absorbed by an active tracker hypothesis.",
        "tracker_threshold_or_association_miss": "Detection is plausible, but tracker association failed under current runtime settings.",
        "unexplained_unmatched": "No single runtime-safe optical explanation dominates.",
    }.get(bucket, "Unclassified unmatched detections.")


def _bucket_action(bucket: str) -> str:
    return {
        "low_score_unmatched": "Audit detector confidence distribution before considering tracker thresholds; do not tune with GT.",
        "neighbor_ambiguous_unmatched": "Compare BoT-SORT and preserve multiple hypotheses for OTY2.",
        "boundary_or_truncated_unmatched": "Keep truncation/contact state in OTY2 as uncertainty, not confirmed identity.",
        "duplicate_or_overlap_rejected": "Use duplicate/overlap rows as review flags; do not merge automatically.",
        "shape_transition_unmatched": "Carry OTY1a shape-transition candidates as optional visual-review hints.",
        "late_fragment_unmatched": "Review fragment starts/ends and compare tracker variants.",
        "tracker_threshold_or_association_miss": "Compare tracker variants and inspect association parameters without GT tuning.",
        "unexplained_unmatched": "Inspect representative frames and add runtime-safe diagnostic features.",
    }.get(bucket, "Review representative cases.")


def _boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"
