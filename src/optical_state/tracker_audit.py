"""Standard MOT tracker audit helpers for OTY1t.

OTY1t consumes runtime-safe optical detections and produces tracker-derived
optical identity hypotheses. Tracker ids are hypotheses only; this module does
not confirm identity and does not use SAR, GT, final/manual/oracle/review
fields, selector scores, thresholds tuned from labels, training signals, or
annotation proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from statistics import mean
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np

from .state_features import (
    BBox,
    bbox_iou,
    boundary_contact_features,
    center_distance,
    parse_float,
    parse_int,
)


SUPPORTED_TRACKERS = {"bytetrack"}


@dataclass(frozen=True)
class TrackerAuditConfig:
    tracker_name: str = "bytetrack"
    tracker_input_mode: str = "detection_table_replay"
    detector_source: str = "oty0_yolo_detection_table"
    frame_rate: int = 30
    track_high_thresh: float = 0.25
    track_low_thresh: float = 0.10
    new_track_thresh: float = 0.25
    track_buffer: int = 30
    match_thresh: float = 0.80
    fuse_score: bool = True
    neighbor_distance_px: float = 120.0
    contact_margin_px: float = 2.0
    min_stable_track_length: int = 8
    short_track_length: int = 3
    duplicate_iou_threshold: float = 0.50
    duplicate_center_distance_px: float = 80.0
    possible_switch_gap_frames: int = 4
    possible_switch_distance_px: float = 140.0


class ByteTrackResultAdapter:
    """Minimal object matching the Ultralytics BYTETracker update contract."""

    def __init__(
        self,
        xyxy: Sequence[Sequence[float]] | np.ndarray,
        conf: Sequence[float] | np.ndarray,
        cls: Sequence[float] | np.ndarray,
    ) -> None:
        xyxy_array = np.asarray(xyxy, dtype=np.float32)
        if xyxy_array.size == 0:
            xyxy_array = np.zeros((0, 4), dtype=np.float32)
        self.xyxy = xyxy_array.reshape(-1, 4)
        self.conf = np.asarray(conf, dtype=np.float32).reshape(-1)
        self.cls = np.asarray(cls, dtype=np.float32).reshape(-1)
        if len(self.xyxy):
            cx = (self.xyxy[:, 0] + self.xyxy[:, 2]) / 2.0
            cy = (self.xyxy[:, 1] + self.xyxy[:, 3]) / 2.0
            width = self.xyxy[:, 2] - self.xyxy[:, 0]
            height = self.xyxy[:, 3] - self.xyxy[:, 1]
            self.xywh = np.stack([cx, cy, width, height], axis=1).astype(np.float32)
        else:
            self.xywh = np.zeros((0, 4), dtype=np.float32)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, item: Any) -> "ByteTrackResultAdapter":
        return ByteTrackResultAdapter(self.xyxy[item], self.conf[item], self.cls[item])


def bytetrack_dependency_facts() -> dict[str, Any]:
    facts = {
        "tracker_name": "bytetrack",
        "ultralytics_available": False,
        "bytetrack_available": False,
        "lap_available": False,
        "dependency_status": "missing",
        "dependency_error": "",
        "install_hint": "D:\\MINICONDA\\envs\\py311\\python.exe -m pip install \"lap>=0.5.12\" ultralytics",
    }
    try:
        import ultralytics  # type: ignore

        facts["ultralytics_available"] = True
        facts["ultralytics_version"] = getattr(ultralytics, "__version__", "")
    except Exception as exc:
        facts["dependency_error"] = repr(exc)
        return facts
    try:
        import lap  # type: ignore  # noqa: F401

        facts["lap_available"] = True
    except Exception as exc:
        facts["dependency_error"] = repr(exc)
        return facts
    try:
        from ultralytics.trackers.byte_tracker import BYTETracker  # type: ignore  # noqa: F401

        facts["bytetrack_available"] = True
        facts["dependency_status"] = "available"
    except Exception as exc:
        facts["dependency_error"] = repr(exc)
    return facts


def _bbox_from_detection(det: Mapping[str, Any]) -> BBox:
    bbox = det.get("bbox")
    if isinstance(bbox, BBox):
        return bbox
    x1 = parse_float(det.get("bbox_x1")) or 0.0
    y1 = parse_float(det.get("bbox_y1")) or 0.0
    x2 = parse_float(det.get("bbox_x2")) or 0.0
    y2 = parse_float(det.get("bbox_y2")) or 0.0
    return BBox(x1, y1, x2, y2)


def _det_area(det: Mapping[str, Any]) -> float:
    return _bbox_from_detection(det).area


def _det_aspect(det: Mapping[str, Any]) -> float | str:
    aspect = _bbox_from_detection(det).aspect
    return "" if aspect is None else aspect


def _class_id(det: Mapping[str, Any]) -> float:
    parsed = parse_float(det.get("class_id"))
    return parsed if parsed is not None else 0.0


def group_detections_by_frame(
    detections: Sequence[Mapping[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for det in detections:
        frame = parse_int(det.get("optical_frame_num"))
        if frame is None:
            continue
        grouped.setdefault(frame, []).append(dict(det))
    for frame, rows in grouped.items():
        grouped[frame] = sorted(rows, key=lambda item: str(item.get("det_id", "")))
    return grouped


def same_frame_neighbor_flags(
    detections: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for frame_rows in group_detections_by_frame(detections).values():
        boxes = [_bbox_from_detection(row) for row in frame_rows]
        for row, box in zip(frame_rows, boxes):
            distances = [center_distance(box, other) for other in boxes if other is not box]
            out[str(row.get("det_id", ""))] = bool(distances and min(distances) <= config.neighbor_distance_px)
    return out


def _adapter_for_frame(rows: Sequence[Mapping[str, Any]]) -> ByteTrackResultAdapter:
    return ByteTrackResultAdapter(
        [[_bbox_from_detection(row).x1, _bbox_from_detection(row).y1, _bbox_from_detection(row).x2, _bbox_from_detection(row).y2] for row in rows],
        [parse_float(row.get("confidence")) or 0.0 for row in rows],
        [_class_id(row) for row in rows],
    )


def _blank_image(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    width = 800
    height = 600
    for row in rows:
        parsed_w = parse_float(row.get("frame_width"))
        parsed_h = parse_float(row.get("frame_height"))
        if parsed_w and parsed_h:
            width = max(1, int(parsed_w))
            height = max(1, int(parsed_h))
            break
    return np.zeros((height, width, 3), dtype=np.uint8)


def run_bytetrack_detection_table_replay(
    detections: Sequence[Mapping[str, Any]],
    frame_numbers: Sequence[int],
    config: TrackerAuditConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Run real Ultralytics BYTETracker over OTY0 detection-table rows."""

    facts = bytetrack_dependency_facts()
    if not facts.get("bytetrack_available"):
        return [], [], facts

    from ultralytics.trackers.byte_tracker import BYTETracker  # type: ignore

    args = SimpleNamespace(
        track_high_thresh=config.track_high_thresh,
        track_low_thresh=config.track_low_thresh,
        new_track_thresh=config.new_track_thresh,
        track_buffer=config.track_buffer,
        match_thresh=config.match_thresh,
        fuse_score=config.fuse_score,
    )
    tracker = BYTETracker(args=args, frame_rate=config.frame_rate)
    grouped = group_detections_by_frame(detections)
    frames = sorted(set(int(frame) for frame in frame_numbers) | set(grouped))
    if not frames:
        return [], [], facts

    assignments: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    first_seen: dict[str, int] = {}
    last_seen: dict[str, int] = {}
    active_previous: set[str] = set()

    for frame in frames:
        frame_rows = grouped.get(frame, [])
        adapter = _adapter_for_frame(frame_rows)
        track_result = tracker.update(adapter, img=_blank_image(frame_rows))
        assigned_indices: set[int] = set()
        active_now: set[str] = set()
        for result in track_result.tolist() if hasattr(track_result, "tolist") else list(track_result):
            if len(result) < 8:
                continue
            x1, y1, x2, y2, track_id, score, cls, idx = result[:8]
            det_idx = int(idx)
            if det_idx < 0 or det_idx >= len(frame_rows):
                continue
            det = frame_rows[det_idx]
            assigned_indices.add(det_idx)
            track_id_text = f"bt_{int(track_id):04d}"
            active_now.add(track_id_text)
            was_seen = track_id_text in first_seen
            prev_frame = last_seen.get(track_id_text)
            is_reactivated = was_seen and prev_frame is not None and frame - prev_frame > 1
            if not was_seen:
                first_seen[track_id_text] = frame
                events.append(
                    _event_row(
                        det.get("scene", ""),
                        config,
                        "track_start",
                        track_id_text,
                        "",
                        frame,
                        frame,
                        frame,
                        1.0,
                        "tracker id first assigned in detection-table replay",
                        False,
                    )
                )
            if is_reactivated:
                events.append(
                    _event_row(
                        det.get("scene", ""),
                        config,
                        "track_reactivated",
                        track_id_text,
                        "",
                        frame,
                        prev_frame,
                        frame,
                        1.0,
                        "tracker id reappeared after a missing optical frame gap",
                        True,
                    )
                )
            confidence = parse_float(det.get("confidence")) or float(score)
            is_low = confidence < config.track_high_thresh
            if is_low:
                events.append(
                    _event_row(
                        det.get("scene", ""),
                        config,
                        "low_score_recovery",
                        track_id_text,
                        "",
                        frame,
                        frame,
                        frame,
                        confidence,
                        "detection below ByteTrack high threshold remained associated",
                        True,
                    )
                )
            last_seen[track_id_text] = frame
            bbox = BBox(float(x1), float(y1), float(x2), float(y2))
            assignments.append(
                {
                    "scene": det.get("scene", ""),
                    "optical_frame_num": frame,
                    "det_id": det.get("det_id", ""),
                    "tracker_name": config.tracker_name,
                    "tracker_input_mode": config.tracker_input_mode,
                    "tracker_track_id": track_id_text,
                    "optical_identity_hypothesis_id": f"oty1t_{track_id_text}",
                    "class_name": det.get("class_name", ""),
                    "confidence": confidence,
                    "bbox_x1": bbox.x1,
                    "bbox_y1": bbox.y1,
                    "bbox_x2": bbox.x2,
                    "bbox_y2": bbox.y2,
                    "bbox_center_x": bbox.cx,
                    "bbox_center_y": bbox.cy,
                    "bbox_w": bbox.width,
                    "bbox_h": bbox.height,
                    "track_state": "tracked",
                    "association_confidence_proxy": float(score),
                    "is_low_score_detection": is_low,
                    "is_recovered_detection": is_low or is_reactivated,
                    "is_unmatched_detection": False,
                    "is_new_track": not was_seen,
                    "is_lost_track": False,
                    "is_reactivated_track": is_reactivated,
                    "runtime_source_policy": "oty1t_runtime_oty0_yolo_detection_table_replay_bytetrack_no_gt_no_sar",
                    "_frame_width": det.get("frame_width", ""),
                    "_frame_height": det.get("frame_height", ""),
                    "_optical_path": det.get("optical_path", ""),
                }
            )
        lost_now = active_previous - active_now
        for track_id_text in sorted(lost_now):
            events.append(
                _event_row(
                    frame_rows[0].get("scene", "") if frame_rows else _scene_from_detections(detections),
                    config,
                    "track_lost",
                    track_id_text,
                    "",
                    frame,
                    last_seen.get(track_id_text, frame),
                    frame,
                    1.0,
                    "track active in previous frame is not assigned in current frame",
                    True,
                )
            )
        active_previous = active_now
        for idx, det in enumerate(frame_rows):
            if idx in assigned_indices:
                continue
            bbox = _bbox_from_detection(det)
            confidence = parse_float(det.get("confidence")) or 0.0
            assignments.append(
                {
                    "scene": det.get("scene", ""),
                    "optical_frame_num": frame,
                    "det_id": det.get("det_id", ""),
                    "tracker_name": config.tracker_name,
                    "tracker_input_mode": config.tracker_input_mode,
                    "tracker_track_id": "",
                    "optical_identity_hypothesis_id": "",
                    "class_name": det.get("class_name", ""),
                    "confidence": confidence,
                    "bbox_x1": bbox.x1,
                    "bbox_y1": bbox.y1,
                    "bbox_x2": bbox.x2,
                    "bbox_y2": bbox.y2,
                    "bbox_center_x": bbox.cx,
                    "bbox_center_y": bbox.cy,
                    "bbox_w": bbox.width,
                    "bbox_h": bbox.height,
                    "track_state": "unmatched_detection",
                    "association_confidence_proxy": "",
                    "is_low_score_detection": confidence < config.track_high_thresh,
                    "is_recovered_detection": False,
                    "is_unmatched_detection": True,
                    "is_new_track": False,
                    "is_lost_track": False,
                    "is_reactivated_track": False,
                    "runtime_source_policy": "oty1t_runtime_oty0_yolo_detection_table_replay_bytetrack_no_gt_no_sar",
                    "_frame_width": det.get("frame_width", ""),
                    "_frame_height": det.get("frame_height", ""),
                    "_optical_path": det.get("optical_path", ""),
                }
            )

    for track_id_text, start in sorted(first_seen.items()):
        end = last_seen.get(track_id_text, start)
        events.append(
            _event_row(
                _scene_from_detections(detections),
                config,
                "track_end",
                track_id_text,
                "",
                end,
                start,
                end,
                1.0,
                "tracker hypothesis reached end of replay audit",
                False,
            )
        )
    events.extend(_duplicate_overlap_events(assignments, config))
    events.extend(_fragment_bridge_events(assignments, config))
    return assignments, sorted(events, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, row.get("event_type", ""), row.get("tracker_track_id", ""))), facts


def _scene_from_detections(detections: Sequence[Mapping[str, Any]]) -> str:
    for det in detections:
        scene = str(det.get("scene", "") or "")
        if scene:
            return scene
    return ""


def _event_row(
    scene: Any,
    config: TrackerAuditConfig,
    event_type: str,
    tracker_track_id: str,
    related_tracker_track_id: str,
    optical_frame_num: int,
    frame_start: Any,
    frame_end: Any,
    event_score_proxy: Any,
    event_reason: str,
    review_required: bool,
) -> dict[str, Any]:
    return {
        "scene": scene,
        "tracker_name": config.tracker_name,
        "event_type": event_type,
        "tracker_track_id": tracker_track_id,
        "related_tracker_track_id": related_tracker_track_id,
        "optical_frame_num": optical_frame_num,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "event_score_proxy": event_score_proxy,
        "event_reason": event_reason,
        "review_required": review_required,
    }


def _tracked_assignments(assignments: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in assignments if str(row.get("tracker_track_id", ""))]


def _assignment_bbox(row: Mapping[str, Any]) -> BBox:
    return BBox(
        parse_float(row.get("bbox_x1")) or 0.0,
        parse_float(row.get("bbox_y1")) or 0.0,
        parse_float(row.get("bbox_x2")) or 0.0,
        parse_float(row.get("bbox_y2")) or 0.0,
    )


def _duplicate_overlap_events(
    assignments: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    by_frame: dict[int, list[Mapping[str, Any]]] = {}
    for row in _tracked_assignments(assignments):
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            by_frame.setdefault(frame, []).append(row)
    for frame, rows in by_frame.items():
        for left_index, left in enumerate(rows):
            left_id = str(left.get("tracker_track_id", ""))
            left_box = _assignment_bbox(left)
            for right in rows[left_index + 1 :]:
                right_id = str(right.get("tracker_track_id", ""))
                if not left_id or left_id == right_id:
                    continue
                right_box = _assignment_bbox(right)
                iou = bbox_iou(left_box, right_box)
                distance = center_distance(left_box, right_box)
                if iou >= config.duplicate_iou_threshold or distance <= config.duplicate_center_distance_px:
                    events.append(
                        _event_row(
                            left.get("scene", ""),
                            config,
                            "duplicate_track_overlap",
                            left_id,
                            right_id,
                            frame,
                            frame,
                            frame,
                            max(iou, 1.0 / (1.0 + distance / max(1.0, config.duplicate_center_distance_px))),
                            "two tracker hypotheses overlap or are very close in the same optical frame",
                            True,
                        )
                    )
    return events


def _fragment_bridge_events(
    assignments: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> list[dict[str, Any]]:
    tracks = _tracks_for_events(assignments)
    events: list[dict[str, Any]] = []
    for left_id, left in tracks.items():
        for right_id, right in tracks.items():
            if left_id == right_id:
                continue
            gap = int(right["frame_start"]) - int(left["frame_end"])
            if gap <= 0 or gap > config.possible_switch_gap_frames:
                continue
            distance = center_distance(left["last_bbox"], right["first_bbox"])
            if distance <= config.possible_switch_distance_px:
                events.append(
                    _event_row(
                        left["scene"],
                        config,
                        "fragment_bridge",
                        left_id,
                        right_id,
                        int(right["frame_start"]),
                        int(left["frame_end"]),
                        int(right["frame_start"]),
                        1.0 / (1.0 + distance / max(1.0, config.possible_switch_distance_px)),
                        "nearby track endpoint/start suggests possible tracker fragmentation bridge",
                        True,
                    )
                )
                events.append(
                    _event_row(
                        left["scene"],
                        config,
                        "possible_id_switch",
                        left_id,
                        right_id,
                        int(right["frame_start"]),
                        int(left["frame_end"]),
                        int(right["frame_start"]),
                        1.0 / (1.0 + distance / max(1.0, config.possible_switch_distance_px)),
                        "nearby successive tracker hypotheses may represent an identity switch or fragment",
                        True,
                    )
                )
    return events


def _tracks_for_events(assignments: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in _tracked_assignments(assignments):
        grouped.setdefault(str(row.get("tracker_track_id", "")), []).append(row)
    for track_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
        if not ordered:
            continue
        out[track_id] = {
            "scene": ordered[0].get("scene", ""),
            "frame_start": parse_int(ordered[0].get("optical_frame_num")) or 0,
            "frame_end": parse_int(ordered[-1].get("optical_frame_num")) or 0,
            "first_bbox": _assignment_bbox(ordered[0]),
            "last_bbox": _assignment_bbox(ordered[-1]),
        }
    return out


def build_tracker_tracks(
    assignments: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in _tracked_assignments(assignments):
        grouped.setdefault(str(row.get("tracker_track_id", "")), []).append(row)
    event_counts: dict[tuple[str, str], int] = {}
    for event in events:
        event_type = str(event.get("event_type", ""))
        for field in ("tracker_track_id", "related_tracker_track_id"):
            track_id = str(event.get(field, "") or "")
            if track_id:
                event_counts[(track_id, event_type)] = event_counts.get((track_id, event_type), 0) + 1
    neighbor_flags = _neighbor_flags_from_assignments(assignments, config)
    rows: list[dict[str, Any]] = []
    for track_id, track_rows in sorted(grouped.items()):
        ordered = sorted(track_rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
        frames = [parse_int(row.get("optical_frame_num")) or 0 for row in ordered]
        gaps = [b - a for a, b in zip(frames, frames[1:])]
        confidences = [parse_float(row.get("confidence")) or 0.0 for row in ordered]
        speeds: list[float] = []
        area_changes: list[float] = []
        for left, right in zip(ordered, ordered[1:]):
            gap = max(1, (parse_int(right.get("optical_frame_num")) or 0) - (parse_int(left.get("optical_frame_num")) or 0))
            left_box = _assignment_bbox(left)
            right_box = _assignment_bbox(right)
            speeds.append(center_distance(left_box, right_box) / gap)
            if left_box.area > 0:
                area_changes.append(abs((right_box.area - left_box.area) / left_box.area))
        boundary_count = sum(1 for row in ordered if _boundary_contact(row, config))
        duplicate_count = event_counts.get((track_id, "duplicate_track_overlap"), 0)
        possible_switch_count = event_counts.get((track_id, "possible_id_switch"), 0)
        lost_count = event_counts.get((track_id, "track_lost"), 0)
        reactivated_count = event_counts.get((track_id, "track_reactivated"), 0)
        missing_gap_count = sum(1 for gap in gaps if gap > 1)
        low_score_count = sum(1 for row in ordered if _boolish(row.get("is_low_score_detection")))
        if len(ordered) < config.short_track_length:
            identity_status = "tracker_short_hypothesis"
            track_status = "short_tracker_hypothesis"
        elif duplicate_count > 0:
            identity_status = "tracker_duplicate_overlap_hypothesis"
            track_status = "duplicate_overlap_review"
        elif possible_switch_count > 0:
            identity_status = "tracker_ambiguous_hypothesis"
            track_status = "possible_id_switch_review"
        elif missing_gap_count > 0 or reactivated_count > 0 or lost_count > 1:
            identity_status = "tracker_fragmented_hypothesis"
            track_status = "fragmented_tracker_hypothesis"
        else:
            identity_status = "tracker_stable_hypothesis"
            track_status = "tracker_stable_hypothesis"
        rows.append(
            {
                "scene": ordered[0].get("scene", ""),
                "tracker_name": config.tracker_name,
                "tracker_track_id": track_id,
                "optical_identity_hypothesis_id": f"oty1t_{track_id}",
                "frame_start": min(frames),
                "frame_end": max(frames),
                "detection_count": len(ordered),
                "frame_span": max(frames) - min(frames) + 1,
                "missing_gap_count": missing_gap_count,
                "max_gap": max(gaps) if gaps else 0,
                "mean_confidence": mean(confidences) if confidences else "",
                "min_confidence": min(confidences) if confidences else "",
                "mean_center_speed": mean(speeds) if speeds else "",
                "max_center_speed": max(speeds) if speeds else "",
                "mean_area_change_ratio": mean(area_changes) if area_changes else "",
                "max_area_change_ratio": max(area_changes) if area_changes else "",
                "boundary_contact_count": boundary_count,
                "neighbor_ambiguity_count": sum(1 for row in ordered if neighbor_flags.get(str(row.get("det_id", "")), False)),
                "low_score_detection_count": low_score_count,
                "lost_count": lost_count,
                "reactivated_count": reactivated_count,
                "track_fragmentation_proxy": missing_gap_count + lost_count + reactivated_count,
                "possible_id_switch_count": possible_switch_count,
                "duplicate_track_overlap_count": duplicate_count,
                "track_status": track_status,
                "identity_status": identity_status,
            }
        )
    return rows


def build_tracker_state_timeseries(
    assignments: Sequence[Mapping[str, Any]],
    track_rows: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> list[dict[str, Any]]:
    identity_by_track = {str(row.get("tracker_track_id", "")): str(row.get("identity_status", "")) for row in track_rows}
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in _tracked_assignments(assignments):
        grouped.setdefault(str(row.get("tracker_track_id", "")), []).append(row)
    neighbor_flags = _neighbor_flags_from_assignments(assignments, config)
    out: list[dict[str, Any]] = []
    for track_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
        for idx, row in enumerate(ordered):
            bbox = _assignment_bbox(row)
            prev = ordered[idx - 1] if idx else None
            velocity_x: float | str = ""
            velocity_y: float | str = ""
            center_speed: float | str = ""
            area_change: float | str = ""
            aspect_change: float | str = ""
            bottom_shift: float | str = ""
            partial_to_full = "not_indicated"
            full_to_partial = "not_indicated"
            if prev is not None:
                prev_box = _assignment_bbox(prev)
                frame_gap = max(1, (parse_int(row.get("optical_frame_num")) or 0) - (parse_int(prev.get("optical_frame_num")) or 0))
                velocity_x = (bbox.cx - prev_box.cx) / frame_gap
                velocity_y = (bbox.cy - prev_box.cy) / frame_gap
                center_speed = hypot(float(velocity_x), float(velocity_y))
                if prev_box.area > 0:
                    area_change = (bbox.area - prev_box.area) / prev_box.area
                if prev_box.aspect and bbox.aspect:
                    aspect_change = (bbox.aspect - prev_box.aspect) / prev_box.aspect
                bottom_shift = bbox.y2 - prev_box.y2
                prev_boundary = _boundary_contact(prev, config)
                cur_boundary = _boundary_contact(row, config)
                if prev_boundary and not cur_boundary and parse_float(area_change) is not None and float(area_change) > 0.25:
                    partial_to_full = "partial_to_full_review"
                if cur_boundary and parse_float(area_change) is not None and float(area_change) < -0.25:
                    full_to_partial = "full_to_partial_review"
            identity_status = identity_by_track.get(track_id, "tracker_stable_hypothesis")
            if identity_status in {"tracker_ambiguous_hypothesis", "tracker_duplicate_overlap_hypothesis"}:
                state_status = "tracker_state_requires_review"
            elif partial_to_full != "not_indicated" or full_to_partial != "not_indicated":
                state_status = "shape_transition_review"
            else:
                state_status = "tracker_runtime_state"
            out.append(
                {
                    "scene": row.get("scene", ""),
                    "optical_frame_num": row.get("optical_frame_num", ""),
                    "tracker_track_id": track_id,
                    "optical_identity_hypothesis_id": f"oty1t_{track_id}",
                    "det_id": row.get("det_id", ""),
                    "bbox_center_x": bbox.cx,
                    "bbox_center_y": bbox.cy,
                    "bbox_w": bbox.width,
                    "bbox_h": bbox.height,
                    "bbox_area": bbox.area,
                    "bbox_aspect": "" if bbox.aspect is None else bbox.aspect,
                    "bottom_y": bbox.y2,
                    "velocity_x": velocity_x,
                    "velocity_y": velocity_y,
                    "center_speed": center_speed,
                    "area_change_ratio": area_change,
                    "aspect_change_ratio": aspect_change,
                    "bottom_y_shift": bottom_shift,
                    "boundary_contact": _boundary_contact(row, config),
                    "neighbor_ambiguity_proxy": neighbor_flags.get(str(row.get("det_id", "")), False),
                    "partial_to_full_transition_proxy": partial_to_full,
                    "full_to_partial_transition_proxy": full_to_partial,
                    "state_status": state_status,
                    "identity_status": identity_status,
                }
            )
    return out


def _boundary_contact(row: Mapping[str, Any], config: TrackerAuditConfig) -> bool:
    bbox = _assignment_bbox(row)
    contact = boundary_contact_features(
        bbox,
        parse_float(row.get("_frame_width")),
        parse_float(row.get("_frame_height")),
        config.contact_margin_px,
    )
    return bool(contact.get("touch_any") is True)


def _neighbor_flags_from_assignments(
    assignments: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> dict[str, bool]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for row in assignments:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            grouped.setdefault(frame, []).append(row)
    out: dict[str, bool] = {}
    for rows in grouped.values():
        boxes = [_assignment_bbox(row) for row in rows]
        for row, bbox in zip(rows, boxes):
            distances = [center_distance(bbox, other) for other in boxes if other is not bbox]
            out[str(row.get("det_id", ""))] = bool(distances and min(distances) <= config.neighbor_distance_px)
    return out


def _boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def build_comparison_row(
    scene: str,
    oty1_summary: Mapping[str, Any],
    oty1a_summary: Mapping[str, Any],
    tracker_tracks: Sequence[Mapping[str, Any]],
    tracker_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    tracker_track_count = len(tracker_tracks)
    short_count = _count_status(tracker_tracks, "identity_status", "tracker_short_hypothesis")
    fragmented_count = _count_status(tracker_tracks, "identity_status", "tracker_fragmented_hypothesis")
    ambiguous_count = _count_status(tracker_tracks, "identity_status", "tracker_ambiguous_hypothesis") + _count_status(
        tracker_tracks, "identity_status", "tracker_duplicate_overlap_hypothesis"
    )
    duplicate_count = sum(parse_int(row.get("duplicate_track_overlap_count")) or 0 for row in tracker_tracks)
    switch_count = sum(parse_int(row.get("possible_id_switch_count")) or 0 for row in tracker_tracks)
    oty1_fragmented = parse_int(oty1_summary.get("fragmented_short_track_count")) or 0
    oty1_ambiguous = parse_int(oty1_summary.get("ambiguous_tracklet_count")) or 0
    return {
        "scene": scene,
        "oty1_component_count": oty1_summary.get("tracklet_candidate_count", ""),
        "oty1_fragmented_count": oty1_fragmented,
        "oty1_ambiguous_count": oty1_ambiguous,
        "oty1a_review_candidates_including_ambiguous": oty1a_summary.get("review_candidate_edges_including_ambiguous", ""),
        "oty1a_nonambiguous_candidates": oty1a_summary.get("nonambiguous_merge_review_candidates", ""),
        "oty1a_ambiguous_competing_candidates": oty1a_summary.get("ambiguous_competing_merge_candidates", ""),
        "tracker_track_count": tracker_track_count,
        "tracker_short_track_count": short_count,
        "tracker_fragmented_hypothesis_count": fragmented_count,
        "tracker_ambiguous_hypothesis_count": ambiguous_count,
        "tracker_duplicate_overlap_count": duplicate_count,
        "tracker_possible_id_switch_count": switch_count,
        "singleton_reduction_proxy": oty1_fragmented - short_count,
        "fragment_reduction_proxy": oty1_fragmented - fragmented_count,
        "comparison_policy": "oty1t_comparison_only_no_runtime_gt_no_sar_no_confirmed_identity",
    }


def _count_status(rows: Sequence[Mapping[str, Any]], field: str, value: str) -> int:
    return sum(1 for row in rows if str(row.get(field, "")) == value)


def case_0039_0045_analysis(
    assignments: Sequence[Mapping[str, Any]],
    oty1_state_rows: Sequence[Mapping[str, Any]],
    tracker_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    det_to_tracker = {
        str(row.get("det_id", "")): str(row.get("tracker_track_id", ""))
        for row in assignments
        if row.get("det_id") and row.get("tracker_track_id")
    }
    fragments = {"oty1_tracklet_0039": set(), "oty1_tracklet_0045": set()}
    for row in oty1_state_rows:
        tracklet_id = str(row.get("tracklet_candidate_id", ""))
        if tracklet_id in fragments:
            fragments[tracklet_id].add(str(row.get("det_id", "")))
    tracks_0039 = {det_to_tracker[det] for det in fragments["oty1_tracklet_0039"] if det in det_to_tracker}
    tracks_0045 = {det_to_tracker[det] for det in fragments["oty1_tracklet_0045"] if det in det_to_tracker}
    shared = sorted(tracks_0039 & tracks_0045)
    related_tracks = tracks_0039 | tracks_0045
    duplicate_events = [
        event
        for event in tracker_events
        if str(event.get("event_type", "")) == "duplicate_track_overlap"
        and (
            str(event.get("tracker_track_id", "")) in related_tracks
            or str(event.get("related_tracker_track_id", "")) in related_tracks
        )
    ]
    switch_events = [
        event
        for event in tracker_events
        if str(event.get("event_type", "")) in {"possible_id_switch", "fragment_bridge"}
        and (
            str(event.get("tracker_track_id", "")) in related_tracks
            or str(event.get("related_tracker_track_id", "")) in related_tracks
        )
    ]
    return {
        "track_ids_for_0039": sorted(tracks_0039),
        "track_ids_for_0045": sorted(tracks_0045),
        "shared_tracker_track_ids": shared,
        "tracker_connected": bool(shared),
        "confirmed_identity": False,
        "competing_track_or_duplicate_overlap": bool(duplicate_events or len(related_tracks) > len(shared)),
        "duplicate_overlap_event_count": len(duplicate_events),
        "possible_id_switch_or_fragment_event_count": len(switch_events),
        "visual_review_required": True,
        "oty2_continuity_hint": bool(shared),
    }
