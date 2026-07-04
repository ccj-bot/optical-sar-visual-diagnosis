"""Run OTY0-post pre-tracking observation grouping audit.

This diagnostic consumes an existing OTY0 detection table and labels same-frame
multi-box conflict candidates before OTY1/ByteTrack association. It preserves
all detector observations and emits review-safe context only. It does not merge
boxes, drop boxes, create final boxes, run a tracker, use SAR/GT evidence, tune
thresholds, or declare identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PAIR_FIELDS = [
    "scene",
    "detector_label",
    "optical_frame_num",
    "detection_id_a",
    "detection_id_b",
    "class_a",
    "class_b",
    "confidence_a",
    "confidence_b",
    "overlap_proxy",
    "center_distance",
    "area_ratio",
    "frame_detection_count",
    "boundary_touch_proxy",
    "size_relation",
    "class_relation",
    "grouping_diagnosis_label",
    "state_tags",
    "safe_for_auto_grouping",
    "why_not_identity_truth",
    "recommended_downstream_use",
]

FRAME_FIELDS = [
    "scene",
    "detector_label",
    "frame",
    "detection_count",
    "same_frame_pair_count",
    "candidate_pair_count",
    "high_overlap_pair_count",
    "class_conflict_pair_count",
    "neighbor_competition_pair_count",
    "unresolved_pair_count",
    "frame_state_tags",
]

SCENE_FIELDS = [
    "scene",
    "detector_label",
    "source_detection_table",
    "timestamp",
    "total_detections",
    "frames_with_detections",
    "frame_min",
    "frame_max",
    "same_frame_pair_count",
    "candidate_multi_box_pairs",
    "high_overlap_pairs",
    "class_instability_duplicate_like_pairs",
    "partial_full_pairs",
    "likely_neighbor_crowding_pairs",
    "unjudgeable_pairs",
    "safe_auto_grouping_count",
    "review_required_count",
    "pair_output_path",
    "frame_output_path",
]

STATE_TAG_ORDER = [
    "edge_contact",
    "truncation_like",
    "partial_visible",
    "partial_to_full_transition",
    "occlusion_like",
    "short_missing_gap",
    "multi_object_competition",
    "duplicate_overlap_detection",
    "neighbor_competition",
    "shape_instability",
    "class_instability",
]

LABELS = {
    "likely_duplicate_same_vehicle_observation",
    "class_instability_duplicate_like",
    "possible_partial_full_same_vehicle_competition",
    "likely_neighbor_vehicle_competition",
    "multi_vehicle_crowding_unresolved",
    "unjudgeable_without_visual_review",
}

HIGH_OVERLAP_PROXY = 0.75
CLASS_CONFLICT_OVERLAP_PROXY = 0.50
DUPLICATE_SIZE_RATIO_MIN = 0.65
PARTIAL_FULL_OVERLAP_PROXY = 0.45
PARTIAL_FULL_AREA_RATIO_MAX = 0.65
CLOSE_CENTER_PX = 120.0
NEIGHBOR_CENTER_PX = 160.0
CROWDING_CENTER_PX = 240.0
BOUNDARY_MARGIN_PX = 2.0


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
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not _is_duplicate_header_row(row)]


def _is_duplicate_header_row(row: Mapping[str, Any]) -> bool:
    hits = 0
    values = 0
    for key, value in row.items():
        text = str(value or "").strip()
        if not text:
            continue
        values += 1
        if text == key:
            hits += 1
    return values > 0 and hits >= max(2, values // 2)


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


def parse_int(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fmt_float(value: float | None, digits: int = 6) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("_") or "item"


def join_tags(tags: Iterable[str]) -> str:
    tag_set = set(tags)
    ordered = [tag for tag in STATE_TAG_ORDER if tag in tag_set]
    ordered.extend(sorted(tag for tag in tag_set if tag not in STATE_TAG_ORDER))
    return ";".join(ordered)


def png_size(path: str | Path) -> tuple[int, int] | None:
    try:
        with Path(path).open("rb") as fh:
            header = fh.read(24)
    except OSError:
        return None
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def bbox_from_row(row: Mapping[str, Any]) -> BBox | None:
    x1 = parse_float(row.get("bbox_x1"))
    y1 = parse_float(row.get("bbox_y1"))
    x2 = parse_float(row.get("bbox_x2"))
    y2 = parse_float(row.get("bbox_y2"))
    if None in (x1, y1, x2, y2):
        return None
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    box = BBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    if box.area <= 0:
        return None
    return box


def bbox_iou(left: BBox, right: BBox) -> float:
    inter_x1 = max(left.x1, right.x1)
    inter_y1 = max(left.y1, right.y1)
    inter_x2 = min(left.x2, right.x2)
    inter_y2 = min(left.y2, right.y2)
    inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
    union = left.area + right.area - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def containment_ratio(left: BBox, right: BBox) -> float:
    inter_x1 = max(left.x1, right.x1)
    inter_y1 = max(left.y1, right.y1)
    inter_x2 = min(left.x2, right.x2)
    inter_y2 = min(left.y2, right.y2)
    inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
    denominator = min(left.area, right.area)
    if denominator <= 0:
        return 0.0
    return inter_area / denominator


def center_distance(left: BBox, right: BBox) -> float:
    return math.hypot(left.cx - right.cx, left.cy - right.cy)


def class_value(row: Mapping[str, Any]) -> str:
    name = str(row.get("class_name", "") or "").strip()
    if name:
        return name
    return str(row.get("class_id", "") or "").strip()


def confidence_value(row: Mapping[str, Any]) -> float | None:
    return parse_float(row.get("confidence"))


def frame_size(row: Mapping[str, Any], cache: dict[str, tuple[int, int] | None]) -> tuple[float | None, float | None]:
    width = parse_float(row.get("frame_width")) or parse_float(row.get("image_width"))
    height = parse_float(row.get("frame_height")) or parse_float(row.get("image_height"))
    if width is not None and height is not None:
        return width, height
    optical_path = str(row.get("optical_path", "") or "").strip()
    if not optical_path:
        return None, None
    if optical_path not in cache:
        cache[optical_path] = png_size(optical_path)
    size = cache.get(optical_path)
    if size:
        return float(size[0]), float(size[1])
    return None, None


def boundary_touch(row: Mapping[str, Any], box: BBox, cache: dict[str, tuple[int, int] | None]) -> bool | None:
    width, height = frame_size(row, cache)
    if width is None or height is None:
        return None
    return (
        box.x1 <= BOUNDARY_MARGIN_PX
        or box.y1 <= BOUNDARY_MARGIN_PX
        or (width - box.x2) <= BOUNDARY_MARGIN_PX
        or (height - box.y2) <= BOUNDARY_MARGIN_PX
    )


def size_relation(area_ratio: float) -> str:
    if area_ratio >= 0.80:
        return "similar_size"
    if area_ratio < 0.35:
        return "very_large_small"
    if area_ratio < 0.65:
        return "one_small_one_large"
    return "moderate_size_difference"


def recommended_use(label: str) -> str:
    if label in {"likely_duplicate_same_vehicle_observation", "class_instability_duplicate_like"}:
        return "pass_as_duplicate_overlap_context_only_do_not_merge"
    if label == "possible_partial_full_same_vehicle_competition":
        return "pass_as_partial_full_context_only_do_not_merge"
    if label in {"likely_neighbor_vehicle_competition", "multi_vehicle_crowding_unresolved"}:
        return "pass_as_competition_blocking_context_only"
    return "pass_as_review_required_context_only"


def classify_pair(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    frame_detection_count: int,
    image_size_cache: dict[str, tuple[int, int] | None],
) -> dict[str, Any] | None:
    left_box = bbox_from_row(left)
    right_box = bbox_from_row(right)
    if left_box is None or right_box is None:
        return None

    iou = bbox_iou(left_box, right_box)
    containment = containment_ratio(left_box, right_box)
    overlap_proxy = max(iou, containment)
    distance = center_distance(left_box, right_box)
    area_ratio = min(left_box.area, right_box.area) / max(left_box.area, right_box.area)
    class_a = class_value(left)
    class_b = class_value(right)
    class_conflict = bool(class_a and class_b and class_a != class_b)
    high_overlap = overlap_proxy >= HIGH_OVERLAP_PROXY
    close_center = distance <= CLOSE_CENTER_PX
    neighbor_close = distance <= NEIGHBOR_CENTER_PX
    crowding_close = distance <= CROWDING_CENTER_PX
    boundary_a = boundary_touch(left, left_box, image_size_cache)
    boundary_b = boundary_touch(right, right_box, image_size_cache)
    boundary_any = boundary_a is True or boundary_b is True
    boundary_known = boundary_a is not None or boundary_b is not None
    partial_full = (
        (overlap_proxy >= PARTIAL_FULL_OVERLAP_PROXY and area_ratio <= PARTIAL_FULL_AREA_RATIO_MAX)
        or (containment >= 0.60 and area_ratio <= 0.75)
        or (area_ratio < 0.40 and overlap_proxy >= 0.15 and distance <= CROWDING_CENTER_PX)
    )
    duplicate_like = high_overlap and area_ratio >= DUPLICATE_SIZE_RATIO_MIN
    class_duplicate_like = class_conflict and (
        overlap_proxy >= CLASS_CONFLICT_OVERLAP_PROXY or (close_center and overlap_proxy >= 0.30)
    )
    likely_neighbor = (
        neighbor_close
        and overlap_proxy < 0.50
        and area_ratio >= 0.40
        and not class_duplicate_like
        and not duplicate_like
    )
    crowded_unresolved = (
        frame_detection_count >= 3
        and not duplicate_like
        and not class_duplicate_like
        and not partial_full
        and not likely_neighbor
        and (crowding_close or overlap_proxy >= 0.15)
    )
    unjudgeable = (
        not duplicate_like
        and not class_duplicate_like
        and not partial_full
        and not likely_neighbor
        and not crowded_unresolved
        and (
            (boundary_any and (distance <= 300.0 or overlap_proxy >= 0.05))
            or (class_conflict and distance <= CROWDING_CENTER_PX)
            or (area_ratio < 0.40 and distance <= 280.0)
        )
    )

    if class_duplicate_like:
        label = "class_instability_duplicate_like"
    elif duplicate_like:
        label = "likely_duplicate_same_vehicle_observation"
    elif partial_full:
        label = "possible_partial_full_same_vehicle_competition"
    elif likely_neighbor:
        label = "likely_neighbor_vehicle_competition"
    elif crowded_unresolved:
        label = "multi_vehicle_crowding_unresolved"
    elif unjudgeable:
        label = "unjudgeable_without_visual_review"
    else:
        return None

    tags: set[str] = set()
    if high_overlap or duplicate_like or class_duplicate_like:
        tags.add("duplicate_overlap_detection")
    if class_conflict:
        tags.add("class_instability")
    if partial_full:
        tags.update({"partial_visible", "partial_to_full_transition", "shape_instability"})
    if boundary_any:
        tags.update({"edge_contact", "truncation_like"})
    if likely_neighbor:
        tags.update({"multi_object_competition", "neighbor_competition"})
    if crowded_unresolved or frame_detection_count >= 3:
        tags.add("multi_object_competition")
    if label == "unjudgeable_without_visual_review" and frame_detection_count >= 2:
        tags.add("multi_object_competition")

    det_a = str(left.get("det_id", "") or "").strip()
    det_b = str(right.get("det_id", "") or "").strip()
    boundary_text = "unknown"
    if boundary_known:
        boundary_text = str(boundary_any).lower()

    return {
        "detection_id_a": det_a,
        "detection_id_b": det_b,
        "class_a": class_a,
        "class_b": class_b,
        "confidence_a": fmt_float(confidence_value(left)),
        "confidence_b": fmt_float(confidence_value(right)),
        "overlap_proxy": fmt_float(overlap_proxy),
        "center_distance": fmt_float(distance),
        "area_ratio": fmt_float(area_ratio),
        "frame_detection_count": frame_detection_count,
        "boundary_touch_proxy": boundary_text,
        "size_relation": size_relation(area_ratio),
        "class_relation": "class_conflict" if class_conflict else "class_agreement",
        "grouping_diagnosis_label": label,
        "state_tags": join_tags(tags),
        "safe_for_auto_grouping": "false",
        "why_not_identity_truth": (
            "same-frame bbox relation is detector-observation context only; "
            "no temporal association, visual review, or identity adjudication was used"
        ),
        "recommended_downstream_use": recommended_use(label),
    }


def frame_sort_key(value: Any) -> tuple[int, str]:
    parsed = parse_int(value)
    if parsed is None:
        return (10**12, str(value))
    return (parsed, str(value))


def summarize_frame(
    scene: str,
    detector_label: str,
    frame: int,
    detections: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    labels = [str(row.get("grouping_diagnosis_label", "")) for row in pair_rows]
    tag_values: set[str] = set()
    for row in pair_rows:
        tag_values.update(tag for tag in str(row.get("state_tags", "")).split(";") if tag)
    same_frame_pair_count = len(detections) * (len(detections) - 1) // 2
    return {
        "scene": scene,
        "detector_label": detector_label,
        "frame": frame,
        "detection_count": len(detections),
        "same_frame_pair_count": same_frame_pair_count,
        "candidate_pair_count": len(pair_rows),
        "high_overlap_pair_count": sum(
            1 for row in pair_rows if (parse_float(row.get("overlap_proxy")) or 0.0) >= HIGH_OVERLAP_PROXY
        ),
        "class_conflict_pair_count": sum(
            1 for row in pair_rows if str(row.get("class_relation", "")) == "class_conflict"
        ),
        "neighbor_competition_pair_count": sum(
            1
            for label in labels
            if label in {"likely_neighbor_vehicle_competition", "multi_vehicle_crowding_unresolved"}
        ),
        "unresolved_pair_count": sum(1 for label in labels if label == "unjudgeable_without_visual_review"),
        "frame_state_tags": join_tags(tag_values),
    }


def summarize_scene(
    scene: str,
    detector_label: str,
    source_detection_table: Path,
    timestamp: str,
    detection_rows: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    pair_output_path: Path,
    frame_output_path: Path,
) -> dict[str, Any]:
    frames = [parse_int(row.get("optical_frame_num")) for row in detection_rows]
    valid_frames = [frame for frame in frames if frame is not None]
    labels = [str(row.get("grouping_diagnosis_label", "")) for row in pair_rows]
    return {
        "scene": scene,
        "detector_label": detector_label,
        "source_detection_table": str(source_detection_table),
        "timestamp": timestamp,
        "total_detections": len(detection_rows),
        "frames_with_detections": len({frame for frame in valid_frames}),
        "frame_min": min(valid_frames) if valid_frames else "",
        "frame_max": max(valid_frames) if valid_frames else "",
        "same_frame_pair_count": sum(parse_int(row.get("same_frame_pair_count")) or 0 for row in frame_rows),
        "candidate_multi_box_pairs": len(pair_rows),
        "high_overlap_pairs": sum(
            1 for row in pair_rows if (parse_float(row.get("overlap_proxy")) or 0.0) >= HIGH_OVERLAP_PROXY
        ),
        "class_instability_duplicate_like_pairs": sum(
            1 for label in labels if label == "class_instability_duplicate_like"
        ),
        "partial_full_pairs": sum(
            1 for label in labels if label == "possible_partial_full_same_vehicle_competition"
        ),
        "likely_neighbor_crowding_pairs": sum(
            1
            for label in labels
            if label in {"likely_neighbor_vehicle_competition", "multi_vehicle_crowding_unresolved"}
        ),
        "unjudgeable_pairs": sum(1 for label in labels if label == "unjudgeable_without_visual_review"),
        "safe_auto_grouping_count": sum(
            1 for row in pair_rows if str(row.get("safe_for_auto_grouping", "")).lower() == "true"
        ),
        "review_required_count": len(pair_rows),
        "pair_output_path": str(pair_output_path),
        "frame_output_path": str(frame_output_path),
    }


def build_audit(
    detection_table: Path,
    scene: str,
    detector_label: str,
    output_dir: Path,
    timestamp: str,
) -> dict[str, Any]:
    raw_rows = read_csv_rows(detection_table)
    detection_rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, start=1):
        row_scene = str(row.get("scene", "") or "").strip()
        if row_scene and row_scene != scene:
            continue
        frame = parse_int(row.get("optical_frame_num"))
        if frame is None:
            continue
        if bbox_from_row(row) is None:
            continue
        item = dict(row)
        item.setdefault("scene", scene)
        if not str(item.get("det_id", "") or "").strip():
            item["det_id"] = f"{scene}_{frame:06d}_{index:06d}"
        detection_rows.append(item)

    by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in detection_rows:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is None:
            continue
        by_frame.setdefault(frame, []).append(row)

    image_size_cache: dict[str, tuple[int, int] | None] = {}
    pair_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        detections = sorted(by_frame[frame], key=lambda row: str(row.get("det_id", "")))
        frame_pair_rows: list[dict[str, Any]] = []
        for left_index, left in enumerate(detections):
            for right in detections[left_index + 1 :]:
                pair = classify_pair(left, right, len(detections), image_size_cache)
                if pair is None:
                    continue
                pair.update(
                    {
                        "scene": scene,
                        "detector_label": detector_label,
                        "optical_frame_num": frame,
                    }
                )
                frame_pair_rows.append(pair)
        frame_pair_rows = sorted(
            frame_pair_rows,
            key=lambda row: (
                str(row.get("grouping_diagnosis_label", "")),
                str(row.get("detection_id_a", "")),
                str(row.get("detection_id_b", "")),
            ),
        )
        pair_rows.extend(frame_pair_rows)
        frame_rows.append(summarize_frame(scene, detector_label, frame, detections, frame_pair_rows))

    prefix = f"{safe_name(scene)}_{safe_name(detector_label)}"
    pair_output_path = output_dir / f"{prefix}_pretracking_grouping_pairs.csv"
    frame_output_path = output_dir / f"{prefix}_pretracking_frame_summary.csv"
    scene_output_path = output_dir / f"{prefix}_pretracking_scene_summary.csv"
    json_output_path = output_dir / f"{prefix}_pretracking_grouping_audit.json"
    scene_summary = summarize_scene(
        scene,
        detector_label,
        detection_table,
        timestamp,
        detection_rows,
        pair_rows,
        frame_rows,
        pair_output_path,
        frame_output_path,
    )

    write_csv(pair_output_path, pair_rows, PAIR_FIELDS)
    write_csv(frame_output_path, frame_rows, FRAME_FIELDS)
    write_csv(scene_output_path, [scene_summary], SCENE_FIELDS)
    write_json(
        json_output_path,
        {
            "boundary": (
                "OTY0-post pre-tracking diagnostic only; raw detections preserved; "
                "safe_for_auto_grouping is false for all candidate pairs"
            ),
            "scene_summary": scene_summary,
            "label_set": sorted(LABELS),
            "thresholds": {
                "high_overlap_proxy": HIGH_OVERLAP_PROXY,
                "class_conflict_overlap_proxy": CLASS_CONFLICT_OVERLAP_PROXY,
                "duplicate_size_ratio_min": DUPLICATE_SIZE_RATIO_MIN,
                "partial_full_overlap_proxy": PARTIAL_FULL_OVERLAP_PROXY,
                "partial_full_area_ratio_max": PARTIAL_FULL_AREA_RATIO_MAX,
                "close_center_px": CLOSE_CENTER_PX,
                "neighbor_center_px": NEIGHBOR_CENTER_PX,
                "crowding_center_px": CROWDING_CENTER_PX,
                "boundary_margin_px": BOUNDARY_MARGIN_PX,
            },
            "outputs": {
                "pair_output_path": str(pair_output_path),
                "frame_output_path": str(frame_output_path),
                "scene_output_path": str(scene_output_path),
            },
        },
    )
    return {
        "pair_output_path": pair_output_path,
        "frame_output_path": frame_output_path,
        "scene_output_path": scene_output_path,
        "json_output_path": json_output_path,
        "scene_summary": scene_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-detection-table", required=True, type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--detector-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_detection_table.exists():
        raise FileNotFoundError(args.input_detection_table)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = build_audit(
        detection_table=args.input_detection_table,
        scene=str(args.scene),
        detector_label=str(args.detector_label),
        output_dir=args.output_dir,
        timestamp=str(args.timestamp),
    )
    print(json.dumps(result["scene_summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
