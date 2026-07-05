"""Probe OTY2 sliding-window local optical continuity.

This diagnostic reads existing OTY0 detections, OTY1 local tracklet state
rows, optional OTY1t tracker assignments, and OTY0-post observation-component
context. It scores bounded windows for local same-target continuity
hypotheses. It does not merge boxes, create a clean object stream, run SAR
pairing/support, tune thresholds, or claim identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


WHY_NOT_IDENTITY_TRUTH = (
    "sliding-window continuity is a local optical hypothesis only; it does "
    "not merge boxes, create final annotations, use SAR/GT/support evidence, "
    "or confirm physical vehicle identity"
)

WINDOW_STATES = [
    "certified_local_continuity",
    "probable_local_continuity",
    "ambiguous_due_to_competition",
    "blocked_by_neighbor_competition",
    "blocked_by_partial_full_review",
    "blocked_by_gap_or_motion",
    "review_required",
]

CONTEXT_FAMILIES = [
    "clean_duplicate_pressure",
    "continuity_useful_duplicate_context",
    "partial_full_review_context",
    "neighbor_multi_object_competition",
    "unresolved_review_required",
]

WINDOW_FIELDS = [
    "scene",
    "detector_label",
    "window_length",
    "stride",
    "window_start",
    "window_end",
    "window_frame_count",
    "detection_rows_in_window",
    "frames_with_any_detection",
    "frame_coverage_ratio",
    "candidate_local_path_count",
    "competing_plausible_paths",
    "best_path_id",
    "best_path_source",
    "best_path_detection_count",
    "best_path_frames_covered",
    "best_path_frame_coverage_ratio",
    "best_path_max_missing_gap",
    "best_path_mean_step_px",
    "best_path_max_step_px",
    "best_path_turn_smoothness_px",
    "best_path_area_stability_ratio",
    "best_path_aspect_stability_ratio",
    "best_path_bottom_y_range_px",
    "best_path_confidence_min",
    "best_path_confidence_median",
    "best_path_class_count",
    "class_mismatch_explained_by_component_context",
    "duplicate_pressure_component_count",
    "continuity_useful_component_count",
    "partial_full_component_count",
    "neighbor_competition_component_count",
    "unresolved_review_component_count",
    "tracker_track_id_count",
    "tracker_unmatched_detection_count",
    "local_continuity_score_not_selector",
    "window_continuity_state",
    "blocker_reason",
    "component_context_used",
    "why_not_identity_truth",
]

PATH_FIELDS = [
    "scene",
    "detector_label",
    "window_length",
    "window_start",
    "window_end",
    "local_path_id",
    "path_source",
    "path_key",
    "detection_count",
    "frames_covered",
    "coverage_ratio",
    "max_missing_gap",
    "mean_step_px",
    "max_step_px",
    "turn_smoothness_px",
    "area_stability_ratio",
    "aspect_stability_ratio",
    "bottom_y_range_px",
    "confidence_min",
    "confidence_median",
    "class_names",
    "component_conflict_families",
    "component_context_flags",
    "tracker_track_ids",
    "local_continuity_score_not_selector",
    "path_policy",
    "why_not_identity_truth",
]

SUMMARY_FIELDS = [
    "scene",
    "detector_label",
    "source_oty0_detection_table",
    "source_component_row_table",
    "source_oty1_state_table",
    "source_tracker_assignment_table",
    "timestamp",
    "frame_min",
    "frame_max",
    "frame_span",
    "detection_rows",
    "frames_with_detections",
    "window_length",
    "stride",
    "total_windows",
    "path_eligible_windows",
    "certified_local_continuity",
    "probable_local_continuity",
    "ambiguous_due_to_competition",
    "blocked_by_neighbor_competition",
    "blocked_by_partial_full_review",
    "blocked_by_gap_or_motion",
    "review_required",
    "certified_rate",
    "certified_or_probable_rate",
    "certified_path_eligible_rate",
    "certified_or_probable_path_eligible_rate",
    "blocked_or_review_rate",
    "windows_with_component_context",
    "windows_with_competing_plausible_paths",
    "median_best_path_coverage",
    "median_best_path_score",
    "window_output_path",
    "path_output_path",
]


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height > 0 else 0.0

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def bottom_y(self) -> float:
        return self.y2


def parse_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def parse_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    if math.isfinite(parsed):
        return parsed
    return None


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def safe_name(value: str) -> str:
    out = []
    for char in value:
        out.append(char if char.isalnum() or char in {"_", "-"} else "_")
    return "".join(out).strip("_") or "unnamed"


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not is_duplicate_header_row(row)]


def is_duplicate_header_row(row: Mapping[str, Any]) -> bool:
    hits = 0
    values = 0
    for key, value in row.items():
        text = str(value or "").strip()
        if not text:
            continue
        values += 1
        if text == key:
            hits += 1
    return bool(values and hits >= max(2, values // 2))


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def split_values(value: Any) -> set[str]:
    return {part.strip() for part in str(value or "").split(";") if part.strip()}


def unique_join(values: Iterable[Any]) -> str:
    return ";".join(sorted({str(value) for value in values if str(value or "").strip()}))


def stable_median(values: Sequence[float]) -> float | str:
    return median(values) if values else ""


def stable_ratio(values: Sequence[float]) -> float | str:
    positive = [value for value in values if value > 0]
    if not positive:
        return ""
    return min(positive) / max(positive)


def mean(values: Sequence[float]) -> float | str:
    return sum(values) / len(values) if values else ""


def dist(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def bbox_from_detection(row: Mapping[str, Any]) -> BBox | None:
    x1 = parse_float(row.get("bbox_x1"))
    y1 = parse_float(row.get("bbox_y1"))
    x2 = parse_float(row.get("bbox_x2"))
    y2 = parse_float(row.get("bbox_y2"))
    if None in (x1, y1, x2, y2):
        return None
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1=x1, y1=y1, x2=x2, y2=y2)


def load_scene_detections(path: Path, scene: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(read_csv_rows(path), start=1):
        row_scene = str(row.get("scene", "") or "").strip()
        if row_scene and row_scene != scene:
            continue
        frame = parse_int(row.get("optical_frame_num"))
        bbox = bbox_from_detection(row)
        if frame is None or bbox is None:
            continue
        item = dict(row)
        item["scene"] = row_scene or scene
        item["optical_frame_num"] = frame
        if not str(item.get("det_id", "") or "").strip():
            item["det_id"] = f"{safe_name(scene)}_{frame:06d}_{index:06d}"
        item["bbox_center_x"] = parse_float(row.get("bbox_cx")) or bbox.cx
        item["bbox_center_y"] = parse_float(row.get("bbox_cy")) or bbox.cy
        item["bbox_width"] = parse_float(row.get("bbox_w")) or bbox.width
        item["bbox_height"] = parse_float(row.get("bbox_h")) or bbox.height
        item["bbox_area"] = bbox.area
        item["bbox_aspect"] = bbox.aspect
        item["bottom_y"] = bbox.bottom_y
        item["_bbox"] = bbox
        rows.append(item)
    return rows


def load_by_key(path: Path | None, key: str) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in read_csv_rows(path):
        value = str(row.get(key, "") or "").strip()
        if value:
            out[value] = dict(row)
    return out


def state_tags_from_oty1(row: Mapping[str, Any]) -> set[str]:
    tags: set[str] = set()
    if boolish(row.get("touch_any")):
        tags.add("edge_contact")
    truncation = str(row.get("truncation_likelihood_proxy", "") or "")
    if "edge_contact" in truncation or "size_change" in truncation:
        tags.add("truncation_like")
    if boolish(row.get("neighbor_ambiguity_proxy")):
        tags.add("multi_object_competition")
    occlusion = str(row.get("occlusion_proxy_status", "") or "")
    if occlusion and not occlusion.startswith("missing_no_runtime_safe"):
        tags.add("occlusion_like")
    state_status = str(row.get("state_status", "") or "")
    if "ambiguous" in state_status:
        tags.add("multi_object_competition")
    return tags


def enrich_rows(
    detections: Sequence[Mapping[str, Any]],
    component_by_det: Mapping[str, Mapping[str, Any]],
    oty1_by_det: Mapping[str, Mapping[str, Any]],
    tracker_by_det: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in detections:
        det_id = str(row.get("det_id", "") or "")
        component = component_by_det.get(det_id, {})
        oty1 = oty1_by_det.get(det_id, {})
        tracker = tracker_by_det.get(det_id, {})
        tags = split_values(component.get("row_state_tags"))
        tags.update(state_tags_from_oty1(oty1))
        family = str(component.get("component_conflict_family", "") or "missing_component_context")
        if family == "partial_full_review_context":
            tags.update({"partial_visible", "partial_to_full_transition", "shape_instability"})
        if family == "neighbor_multi_object_competition":
            tags.update({"multi_object_competition", "neighbor_competition"})
        if family in {"clean_duplicate_pressure", "continuity_useful_duplicate_context"}:
            tags.add("duplicate_overlap_detection")

        item = dict(row)
        item.update(
            {
                "observation_component_id": component.get("observation_component_id", ""),
                "component_size": parse_int(component.get("component_size")) or 1,
                "component_role": component.get("component_role", ""),
                "component_conflict_family": family,
                "component_policy": component.get("component_policy", ""),
                "tracking_policy": component.get("tracking_policy", ""),
                "fragment_context_policy": component.get("fragment_context_policy", ""),
                "suppression_risk": component.get("suppression_risk", ""),
                "temporal_review_needed": boolish(component.get("temporal_review_needed")),
                "row_state_tags": unique_join(tags),
                "tracklet_candidate_id": oty1.get("tracklet_candidate_id", ""),
                "oty1_state_status": oty1.get("state_status", ""),
                "oty1_identity_status": oty1.get("identity_status", ""),
                "tracker_track_id": tracker.get("tracker_track_id", ""),
                "tracker_track_state": tracker.get("track_state", ""),
                "tracker_is_unmatched": boolish(tracker.get("is_unmatched_detection")),
            }
        )
        enriched.append(item)
    return enriched


def window_starts(frame_min: int, frame_max: int, length: int, stride: int) -> list[int]:
    if frame_max < frame_min or length <= 0:
        return []
    last_start = frame_max - length + 1
    if last_start < frame_min:
        return [frame_min]
    return list(range(frame_min, last_start + 1, stride))


def group_path_candidates(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    by_tracklet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_tracker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tracklet = str(row.get("tracklet_candidate_id", "") or "").strip()
        tracker = str(row.get("tracker_track_id", "") or "").strip()
        if tracklet:
            by_tracklet[tracklet].append(dict(row))
        elif tracker:
            by_tracker[tracker].append(dict(row))

    paths: list[tuple[str, str, list[dict[str, Any]]]] = []
    for key, values in sorted(by_tracklet.items()):
        if len(values) >= 2:
            paths.append(("oty1_tracklet_local_slice", key, values))
    if not paths:
        for key, values in sorted(by_tracker.items()):
            if len(values) >= 2:
                paths.append(("oty1t_tracker_local_slice_optional_context", key, values))
    if not paths and rows:
        # Singletons keep the window diagnosable, but cannot certify continuity.
        best = max(rows, key=lambda item: parse_float(item.get("confidence")) or 0.0)
        paths.append(("single_detection_no_continuity_path", str(best.get("det_id", "")), [dict(best)]))
    return paths


def path_metrics(
    scene: str,
    detector_label: str,
    window_length: int,
    window_start: int,
    window_end: int,
    path_source: str,
    path_key: str,
    rows: Sequence[Mapping[str, Any]],
    index: int,
) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or -1, str(row.get("det_id", ""))))
    frames = [parse_int(row.get("optical_frame_num")) for row in ordered]
    frames = [frame for frame in frames if frame is not None]
    unique_frames = sorted(set(frames))
    centers = [
        (parse_float(row.get("bbox_center_x")), parse_float(row.get("bbox_center_y")))
        for row in ordered
    ]
    centers_xy = [(x, y) for x, y in centers if x is not None and y is not None]
    gaps = [right - left - 1 for left, right in zip(unique_frames, unique_frames[1:]) if right > left]
    step_values: list[float] = []
    velocities: list[tuple[float, float]] = []
    for left, right in zip(ordered, ordered[1:]):
        lf = parse_int(left.get("optical_frame_num"))
        rf = parse_int(right.get("optical_frame_num"))
        lx = parse_float(left.get("bbox_center_x"))
        ly = parse_float(left.get("bbox_center_y"))
        rx = parse_float(right.get("bbox_center_x"))
        ry = parse_float(right.get("bbox_center_y"))
        if None in (lf, rf, lx, ly, rx, ry) or rf == lf:
            continue
        assert lf is not None and rf is not None and lx is not None and ly is not None and rx is not None and ry is not None
        frame_gap = max(1, rf - lf)
        dx = (rx - lx) / frame_gap
        dy = (ry - ly) / frame_gap
        velocities.append((dx, dy))
        step_values.append(math.hypot(dx, dy))
    turn_values = [dist(left, right) for left, right in zip(velocities, velocities[1:])]

    areas = [value for value in (parse_float(row.get("bbox_area")) for row in ordered) if value is not None]
    aspects = [value for value in (parse_float(row.get("bbox_aspect")) for row in ordered) if value is not None]
    bottoms = [value for value in (parse_float(row.get("bottom_y")) for row in ordered) if value is not None]
    confidences = [value for value in (parse_float(row.get("confidence")) for row in ordered) if value is not None]
    class_names = {str(row.get("class_name", "") or "") for row in ordered if str(row.get("class_name", "") or "")}
    families = {str(row.get("component_conflict_family", "") or "") for row in ordered if str(row.get("component_conflict_family", "") or "")}
    tracker_ids = {str(row.get("tracker_track_id", "") or "") for row in ordered if str(row.get("tracker_track_id", "") or "")}
    component_flags = {family for family in families if family in CONTEXT_FAMILIES}

    coverage = len(unique_frames) / window_length if window_length else 0.0
    max_gap = max(gaps) if gaps else 0
    mean_step = mean(step_values)
    max_step = max(step_values) if step_values else ""
    turn_smoothness = mean(turn_values)
    area_ratio = stable_ratio(areas)
    aspect_ratio = stable_ratio(aspects)
    bottom_range = (max(bottoms) - min(bottoms)) if bottoms else ""
    conf_min = min(confidences) if confidences else ""
    conf_median = stable_median(confidences)
    score = local_score(
        coverage,
        max_gap,
        mean_step,
        turn_smoothness,
        area_ratio,
        aspect_ratio,
        conf_median,
        component_flags,
    )
    return {
        "scene": scene,
        "detector_label": detector_label,
        "window_length": window_length,
        "window_start": window_start,
        "window_end": window_end,
        "local_path_id": f"{safe_name(scene)}_w{window_length}_{window_start:06d}_{index:03d}",
        "path_source": path_source,
        "path_key": path_key,
        "detection_count": len(ordered),
        "frames_covered": len(unique_frames),
        "coverage_ratio": round(coverage, 6),
        "max_missing_gap": max_gap,
        "mean_step_px": round(mean_step, 6) if mean_step != "" else "",
        "max_step_px": round(max_step, 6) if max_step != "" else "",
        "turn_smoothness_px": round(turn_smoothness, 6) if turn_smoothness != "" else "",
        "area_stability_ratio": round(area_ratio, 6) if area_ratio != "" else "",
        "aspect_stability_ratio": round(aspect_ratio, 6) if aspect_ratio != "" else "",
        "bottom_y_range_px": round(bottom_range, 6) if bottom_range != "" else "",
        "confidence_min": round(conf_min, 6) if conf_min != "" else "",
        "confidence_median": round(conf_median, 6) if conf_median != "" else "",
        "class_names": unique_join(class_names),
        "component_conflict_families": unique_join(families),
        "component_context_flags": unique_join(component_flags),
        "tracker_track_ids": unique_join(tracker_ids),
        "local_continuity_score_not_selector": round(score, 6),
        "path_policy": "local_window_hypothesis_not_identity_truth",
        "why_not_identity_truth": WHY_NOT_IDENTITY_TRUTH,
        "_score": score,
        "_class_count": len(class_names),
        "_component_flags": component_flags,
        "_rows": ordered,
    }


def numeric_score(value: Any, scale: float, default: float) -> float:
    parsed = parse_float(value)
    if parsed is None:
        return default
    return 1.0 / (1.0 + parsed / scale)


def local_score(
    coverage: float,
    max_gap: int,
    mean_step_px: float | str,
    turn_smoothness_px: float | str,
    area_ratio: float | str,
    aspect_ratio: float | str,
    confidence_median: float | str,
    component_flags: set[str],
) -> float:
    coverage_score = min(1.0, coverage / 0.75)
    gap_score = 1.0 / (1.0 + max(0, max_gap) / 2.0)
    step_score = numeric_score(mean_step_px, 180.0, 0.75)
    turn_score = numeric_score(turn_smoothness_px, 160.0, 0.80)
    area_score = float(area_ratio) if area_ratio != "" else 0.55
    aspect_score = float(aspect_ratio) if aspect_ratio != "" else 0.55
    confidence_score = float(confidence_median) if confidence_median != "" else 0.50
    penalty = 0.0
    if "neighbor_multi_object_competition" in component_flags:
        penalty += 0.18
    if "partial_full_review_context" in component_flags:
        penalty += 0.10
    if "unresolved_review_required" in component_flags:
        penalty += 0.12
    if "continuity_useful_duplicate_context" in component_flags:
        penalty += 0.03
    raw = (
        0.24 * coverage_score
        + 0.15 * gap_score
        + 0.14 * step_score
        + 0.12 * turn_score
        + 0.10 * area_score
        + 0.08 * aspect_score
        + 0.17 * confidence_score
    )
    return max(0.0, min(1.0, raw - penalty))


def class_mismatch_explained(path: Mapping[str, Any]) -> bool:
    if int(path.get("_class_count", 0)) <= 1:
        return True
    flags = set(path.get("_component_flags", set()))
    return bool(flags & {"clean_duplicate_pressure", "continuity_useful_duplicate_context"})


def context_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    components_by_family: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        family = str(row.get("component_conflict_family", "") or "")
        component_id = str(row.get("observation_component_id", "") or row.get("det_id", "") or "")
        if family:
            components_by_family[family].add(component_id)
    return {
        "duplicate_pressure_component_count": len(components_by_family["clean_duplicate_pressure"]),
        "continuity_useful_component_count": len(components_by_family["continuity_useful_duplicate_context"]),
        "partial_full_component_count": len(components_by_family["partial_full_review_context"]),
        "neighbor_competition_component_count": len(components_by_family["neighbor_multi_object_competition"]),
        "unresolved_review_component_count": len(components_by_family["unresolved_review_required"]),
    }


def classify_window(
    window_rows: Sequence[Mapping[str, Any]],
    best_path: Mapping[str, Any] | None,
    competing_plausible_paths: int,
    counts: Mapping[str, int],
) -> tuple[str, str]:
    if best_path is None or int(best_path.get("frames_covered") or 0) < 2:
        return "blocked_by_gap_or_motion", "no_two_observation_local_path_candidate"

    coverage = parse_float(best_path.get("coverage_ratio")) or 0.0
    max_gap = parse_int(best_path.get("max_missing_gap")) or 0
    mean_step = parse_float(best_path.get("mean_step_px")) or 0.0
    turn = parse_float(best_path.get("turn_smoothness_px"))
    area_ratio = parse_float(best_path.get("area_stability_ratio")) or 0.0
    aspect_ratio = parse_float(best_path.get("aspect_stability_ratio")) or 0.0
    score = parse_float(best_path.get("local_continuity_score_not_selector")) or 0.0
    class_ok = class_mismatch_explained(best_path)
    has_neighbor = counts["neighbor_competition_component_count"] > 0
    has_partial = counts["partial_full_component_count"] > 0
    has_unresolved = counts["unresolved_review_component_count"] > 0
    turn_ok = turn is None or turn <= 160.0
    shape_ok = (area_ratio == 0.0 or area_ratio >= 0.25) and (aspect_ratio == 0.0 or aspect_ratio >= 0.25)

    if (
        coverage >= 0.75
        and max_gap <= 2
        and mean_step <= 220.0
        and turn_ok
        and shape_ok
        and not has_neighbor
        and not has_unresolved
        and competing_plausible_paths == 0
        and class_ok
        and score >= 0.62
    ):
        return "certified_local_continuity", "sufficient_window_coverage_smooth_motion_no_strong_competition"

    if has_neighbor and competing_plausible_paths >= 1:
        return "blocked_by_neighbor_competition", "neighbor_or_multi_object_component_context_with_competing_path"
    if has_neighbor or competing_plausible_paths > 1:
        return "ambiguous_due_to_competition", "multiple_plausible_local_paths_or_neighbor_competition"
    if has_partial and (coverage < 0.70 or max_gap > 1 or area_ratio < 0.45):
        return "blocked_by_partial_full_review", "partial_full_state_context_blocks_safe_window_certificate"
    if has_unresolved:
        return "review_required", "unresolved_component_context_present"
    if not class_ok:
        return "review_required", "class_mismatch_not_explained_by_duplicate_component_context"
    if coverage >= 0.55 and max_gap <= 3 and mean_step <= 280.0 and score >= 0.48:
        return "probable_local_continuity", "moderate_window_coverage_with_no_strong_blocker"
    if max_gap > 3 or coverage < 0.40 or mean_step > 350.0:
        return "blocked_by_gap_or_motion", "insufficient_window_coverage_or_motion_smoothness"
    if has_partial:
        return "blocked_by_partial_full_review", "partial_full_state_context_requires_review"
    return "review_required", "window_evidence_insufficient_for_certificate"


def build_window_rows(
    scene: str,
    detector_label: str,
    rows: Sequence[Mapping[str, Any]],
    window_length: int,
    stride: int,
    frame_min: int,
    frame_max: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            by_frame[frame].append(dict(row))

    window_rows_out: list[dict[str, Any]] = []
    path_rows_out: list[dict[str, Any]] = []
    for start in window_starts(frame_min, frame_max, window_length, stride):
        end = start + window_length - 1
        window_rows: list[dict[str, Any]] = []
        for frame in range(start, end + 1):
            window_rows.extend(by_frame.get(frame, []))
        frames_with_dets = sorted({parse_int(row.get("optical_frame_num")) for row in window_rows})
        frames_with_dets = [frame for frame in frames_with_dets if frame is not None]
        path_candidates = group_path_candidates(window_rows)
        path_metrics_rows = [
            path_metrics(scene, detector_label, window_length, start, end, source, key, candidate_rows, index)
            for index, (source, key, candidate_rows) in enumerate(path_candidates, start=1)
        ]
        candidate_paths = [row for row in path_metrics_rows if int(row.get("detection_count") or 0) >= 2]
        best_path = max(candidate_paths, key=lambda row: float(row.get("_score") or 0.0), default=None)
        if best_path is None and path_metrics_rows:
            best_path = max(path_metrics_rows, key=lambda row: float(row.get("_score") or 0.0))
        best_score = float(best_path.get("_score") or 0.0) if best_path else 0.0
        competing = sum(
            1
            for row in candidate_paths
            if row is not best_path
            and float(row.get("_score") or 0.0) >= max(0.48, best_score - 0.10)
            and float(row.get("coverage_ratio") or 0.0) >= 0.40
        )
        counts = context_counts(window_rows)
        state, blocker = classify_window(window_rows, best_path, competing, counts)
        tracker_ids = {
            str(row.get("tracker_track_id", "") or "")
            for row in window_rows
            if str(row.get("tracker_track_id", "") or "")
        }
        tracker_unmatched = sum(1 for row in window_rows if bool(row.get("tracker_is_unmatched")))
        component_context_used = any(counts[field] > 0 for field in counts)
        window_rows_out.append(
            {
                "scene": scene,
                "detector_label": detector_label,
                "window_length": window_length,
                "stride": stride,
                "window_start": start,
                "window_end": end,
                "window_frame_count": window_length,
                "detection_rows_in_window": len(window_rows),
                "frames_with_any_detection": len(frames_with_dets),
                "frame_coverage_ratio": round(len(frames_with_dets) / window_length, 6),
                "candidate_local_path_count": len(candidate_paths),
                "competing_plausible_paths": competing,
                "best_path_id": best_path.get("local_path_id", "") if best_path else "",
                "best_path_source": best_path.get("path_source", "") if best_path else "",
                "best_path_detection_count": best_path.get("detection_count", "") if best_path else "",
                "best_path_frames_covered": best_path.get("frames_covered", "") if best_path else "",
                "best_path_frame_coverage_ratio": best_path.get("coverage_ratio", "") if best_path else "",
                "best_path_max_missing_gap": best_path.get("max_missing_gap", "") if best_path else "",
                "best_path_mean_step_px": best_path.get("mean_step_px", "") if best_path else "",
                "best_path_max_step_px": best_path.get("max_step_px", "") if best_path else "",
                "best_path_turn_smoothness_px": best_path.get("turn_smoothness_px", "") if best_path else "",
                "best_path_area_stability_ratio": best_path.get("area_stability_ratio", "") if best_path else "",
                "best_path_aspect_stability_ratio": best_path.get("aspect_stability_ratio", "") if best_path else "",
                "best_path_bottom_y_range_px": best_path.get("bottom_y_range_px", "") if best_path else "",
                "best_path_confidence_min": best_path.get("confidence_min", "") if best_path else "",
                "best_path_confidence_median": best_path.get("confidence_median", "") if best_path else "",
                "best_path_class_count": best_path.get("_class_count", "") if best_path else "",
                "class_mismatch_explained_by_component_context": (
                    "true" if best_path and class_mismatch_explained(best_path) else "false"
                ),
                **counts,
                "tracker_track_id_count": len(tracker_ids),
                "tracker_unmatched_detection_count": tracker_unmatched,
                "local_continuity_score_not_selector": round(best_score, 6) if best_path else "",
                "window_continuity_state": state,
                "blocker_reason": blocker,
                "component_context_used": "true" if component_context_used else "false",
                "why_not_identity_truth": WHY_NOT_IDENTITY_TRUTH,
            }
        )
        for row in path_metrics_rows:
            serializable = {field: row.get(field, "") for field in PATH_FIELDS}
            path_rows_out.append(serializable)
    return window_rows_out, path_rows_out


def summarize_windows(
    scene: str,
    detector_label: str,
    args: argparse.Namespace,
    detection_rows: Sequence[Mapping[str, Any]],
    window_length: int,
    stride: int,
    frame_min: int,
    frame_max: int,
    window_rows: Sequence[Mapping[str, Any]],
    window_output_path: Path,
    path_output_path: Path,
) -> dict[str, Any]:
    state_counts = Counter(str(row.get("window_continuity_state", "")) for row in window_rows)
    best_coverages = [
        value
        for value in (parse_float(row.get("best_path_frame_coverage_ratio")) for row in window_rows)
        if value is not None
    ]
    best_scores = [
        value
        for value in (parse_float(row.get("local_continuity_score_not_selector")) for row in window_rows)
        if value is not None
    ]
    total = len(window_rows)
    eligible = sum(1 for window in window_rows if (parse_int(window.get("candidate_local_path_count")) or 0) > 0)
    frames = {
        frame
        for frame in (parse_int(row.get("optical_frame_num")) for row in detection_rows)
        if frame is not None
    }
    row = {
        "scene": scene,
        "detector_label": detector_label,
        "source_oty0_detection_table": str(args.oty0_detection_table),
        "source_component_row_table": str(args.component_row_table),
        "source_oty1_state_table": str(args.oty1_state_table or ""),
        "source_tracker_assignment_table": str(args.tracker_assignment_table or ""),
        "timestamp": args.timestamp,
        "frame_min": frame_min,
        "frame_max": frame_max,
        "frame_span": frame_max - frame_min + 1,
        "detection_rows": len(detection_rows),
        "frames_with_detections": len(frames),
        "window_length": window_length,
        "stride": stride,
        "total_windows": total,
        "path_eligible_windows": eligible,
        "windows_with_component_context": sum(
            1 for window in window_rows if str(window.get("component_context_used", "")).lower() == "true"
        ),
        "windows_with_competing_plausible_paths": sum(
            1 for window in window_rows if (parse_int(window.get("competing_plausible_paths")) or 0) > 0
        ),
        "median_best_path_coverage": round(stable_median(best_coverages), 6) if best_coverages else "",
        "median_best_path_score": round(stable_median(best_scores), 6) if best_scores else "",
        "window_output_path": str(window_output_path),
        "path_output_path": str(path_output_path),
    }
    for state in WINDOW_STATES:
        row[state] = state_counts[state]
    row["certified_rate"] = round(state_counts["certified_local_continuity"] / total, 6) if total else 0.0
    row["certified_or_probable_rate"] = (
        round((state_counts["certified_local_continuity"] + state_counts["probable_local_continuity"]) / total, 6)
        if total
        else 0.0
    )
    row["certified_path_eligible_rate"] = (
        round(state_counts["certified_local_continuity"] / eligible, 6) if eligible else 0.0
    )
    row["certified_or_probable_path_eligible_rate"] = (
        round((state_counts["certified_local_continuity"] + state_counts["probable_local_continuity"]) / eligible, 6)
        if eligible
        else 0.0
    )
    blocked_or_review = (
        state_counts["blocked_by_neighbor_competition"]
        + state_counts["blocked_by_partial_full_review"]
        + state_counts["blocked_by_gap_or_motion"]
        + state_counts["review_required"]
        + state_counts["ambiguous_due_to_competition"]
    )
    row["blocked_or_review_rate"] = round(blocked_or_review / total, 6) if total else 0.0
    return row


def run_probe(args: argparse.Namespace) -> list[dict[str, Any]]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detection_rows = load_scene_detections(Path(args.oty0_detection_table), args.scene)
    if not detection_rows:
        raise ValueError(f"No detection rows found for {args.scene}: {args.oty0_detection_table}")
    component_by_det = load_by_key(Path(args.component_row_table), "raw_det_id")
    oty1_by_det = load_by_key(Path(args.oty1_state_table), "det_id") if args.oty1_state_table else {}
    tracker_by_det = (
        load_by_key(Path(args.tracker_assignment_table), "det_id")
        if args.tracker_assignment_table
        else {}
    )
    enriched_rows = enrich_rows(detection_rows, component_by_det, oty1_by_det, tracker_by_det)
    frames = [parse_int(row.get("optical_frame_num")) for row in detection_rows]
    valid_frames = [frame for frame in frames if frame is not None]
    frame_min = min(valid_frames)
    frame_max = max(valid_frames)

    prefix = f"{safe_name(args.scene)}_{safe_name(args.detector_label)}"
    summaries: list[dict[str, Any]] = []
    output_manifest: dict[str, Any] = {
        "boundary": (
            "sliding-window local continuity probe only; no runtime changes, "
            "no clean object stream, no final boxes, no SAR/support, no "
            "selector/ranking, and no identity truth"
        ),
        "scene": args.scene,
        "detector_label": args.detector_label,
        "timestamp": args.timestamp,
        "window_lengths": args.window_lengths,
        "outputs": {},
    }
    for window_length in args.window_lengths:
        stride = max(4, window_length // 2)
        window_rows, path_rows = build_window_rows(
            args.scene,
            args.detector_label,
            enriched_rows,
            window_length,
            stride,
            frame_min,
            frame_max,
        )
        window_output_path = output_dir / f"{prefix}_w{window_length}_sliding_window_local_continuity_windows.csv"
        path_output_path = output_dir / f"{prefix}_w{window_length}_sliding_window_local_paths.csv"
        write_csv(window_output_path, window_rows, WINDOW_FIELDS)
        write_csv(path_output_path, path_rows, PATH_FIELDS)
        summaries.append(
            summarize_windows(
                args.scene,
                args.detector_label,
                args,
                detection_rows,
                window_length,
                stride,
                frame_min,
                frame_max,
                window_rows,
                window_output_path,
                path_output_path,
            )
        )
        output_manifest["outputs"][str(window_length)] = {
            "window_output_path": str(window_output_path),
            "path_output_path": str(path_output_path),
        }
    summary_path = output_dir / f"{prefix}_sliding_window_local_continuity_scene_summary.csv"
    manifest_path = output_dir / f"{prefix}_sliding_window_local_continuity_probe.json"
    write_csv(summary_path, summaries, SUMMARY_FIELDS)
    output_manifest["outputs"]["scene_summary"] = str(summary_path)
    write_json(manifest_path, output_manifest)
    return summaries


def parse_window_lengths(value: str) -> list[int]:
    out = []
    for part in value.split(","):
        parsed = parse_int(part)
        if parsed is not None and parsed > 0:
            out.append(parsed)
    if not out:
        raise argparse.ArgumentTypeError("window lengths must contain positive integers")
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--detector-label", required=True)
    parser.add_argument("--oty0-detection-table", required=True, type=Path)
    parser.add_argument("--component-row-table", required=True, type=Path)
    parser.add_argument("--oty1-state-table", type=Path, default=None)
    parser.add_argument("--tracker-assignment-table", type=Path, default=None)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--window-lengths", type=parse_window_lengths, default=[8, 12, 16])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in [args.oty0_detection_table, args.component_row_table, args.oty1_state_table, args.tracker_assignment_table]:
        if path is not None and not Path(path).exists():
            raise FileNotFoundError(path)
    summaries = run_probe(args)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
