"""Audit temporal continuation and SAR posthoc support for OTY2 detection dropouts.

This script focuses on the 12 no_oty_iou_match cases. It separates:
- runtime-safe temporal continuation evidence from optical object streams,
- posthoc-only SAR GT / SAR image evidence,
- detector-ablation planning for possible YOLO upgrades.

It does not emit automatic annotation proposals, train or tune thresholds,
write propagation boxes as final labels, or use SAR evidence as runtime identity
truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageStat


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
OUTPUT_PARENT = REPO_ROOT / "outputs"
SAMPLE_DIR = REPORT_DIR / "samples" / "detection_dropout_temporal_sar_support"
DEFAULT_OBJECT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"
DEFAULT_GT_CSV = Path(
    r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv"
)
DEFAULT_WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

OPTICAL_FPS = 24.0
SAR_FPS = 50.0
OPTICAL_WIDTH = 800.0
OPTICAL_HEIGHT = 600.0
PAIR_IOU_MIN = 0.05
TEMPORAL_RADIUS_FRAMES = 10

TEMPORAL_FIELDS = [
    "scene",
    "sar_gt_id",
    "optical_frame",
    "sar_frame",
    "target_identity",
    "review_bbox",
    "current_frame_primary_available",
    "current_frame_secondary_available",
    "current_primary_iou",
    "current_secondary_iou",
    "previous_support_frame_count",
    "next_support_frame_count",
    "nearest_previous_support_frame",
    "nearest_next_support_frame",
    "same_track_support",
    "same_track_ids",
    "spatial_continuity_support",
    "bbox_size_continuity_support",
    "edge_truncation_status",
    "temporal_continuation_status",
    "temporal_continuation_confidence",
    "continuation_reason",
    "propagation_source",
    "propagated_bbox_diagnostic",
    "propagated_bbox_iou_with_review",
    "propagated_bbox_review_containment",
    "propagation_diagnostic_status",
    "sample_use_categories",
    "existence_recovered_by_temporal_continuation",
    "temporal_continuation_with_detection_dropout",
    "secondary_supported_truncated_same_vehicle",
    "sar_posthoc_supported_dropout_case",
    "yolo_upgrade_candidate",
    "manual_review_required",
    "exclude_from_clean_shape_statistics",
    "blockers",
    "local_visualization_path",
    "repo_sample_visualization_path",
    "notes",
]

SAR_FIELDS = [
    "scene",
    "sar_gt_id",
    "optical_frame",
    "sar_frame",
    "expected_sar_frame_raw",
    "temporal_error_sar_frames",
    "gt_in_software_sync_window",
    "sar_gt_center",
    "sar_gt_width",
    "sar_gt_height",
    "sar_gt_heading_deg",
    "sar_gt_axis_aligned_bbox",
    "sar_box_mean",
    "sar_background_mean",
    "sar_box_to_background_ratio",
    "sar_peak_to_background_ratio",
    "sar_scatter_support_status",
    "sar_posthoc_support_status",
    "sar_posthoc_support_reason",
    "sar_image_path",
    "notes",
]

BOUNDARY_FLAGS = {
    "optical_frames_read": True,
    "existing_oty_outputs_read": True,
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "propagated_box_written_as_final_annotation": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_path(pattern: str) -> Path:
    matches = sorted(REPORT_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No reports/oty2 file matches {pattern}")
    return matches[-1]


def safe_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return int(number)


def fmt(value: Any, digits: int = 4) -> str:
    number = safe_float(value)
    if number is None:
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_bbox_text(text: str) -> tuple[float, float, float, float] | None:
    parts = [safe_float(part) for part in str(text).split(",")]
    if len(parts) != 4 or any(part is None for part in parts):
        return None
    x1, y1, x2, y2 = (float(part) for part in parts if part is not None)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def parse_bbox(row: Mapping[str, Any], keys: Sequence[str]) -> tuple[float, float, float, float] | None:
    values = [safe_float(row.get(key)) for key in keys]
    if any(value is None for value in values):
        return None
    x1, y1, x2, y2 = (float(value) for value in values if value is not None)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_text(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return ""
    return ",".join(fmt(value, 3) for value in bbox)


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    denom = bbox_area(a) + bbox_area(b) - inter
    return inter / denom if denom > 0 else 0.0


def bbox_containment(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> float:
    ix1 = max(inner[0], outer[0])
    iy1 = max(inner[1], outer[1])
    ix2 = min(inner[2], outer[2])
    iy2 = min(inner[3], outer[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    return inter / max(bbox_area(inner), 1e-6)


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def bbox_diag(bbox: tuple[float, float, float, float]) -> float:
    return math.hypot(bbox[2] - bbox[0], bbox[3] - bbox[1])


def primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    return parse_bbox(row, ("primary_bbox_x1", "primary_bbox_y1", "primary_bbox_x2", "primary_bbox_y2"))


def parse_secondary_boxes(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(row.get("secondary_bbox_summary", "")).strip()
    if not text:
        return []
    boxes: list[dict[str, Any]] = []
    for item in re.split(r"[;|]\s*", text):
        if ":" not in item:
            continue
        det_id, coords = item.split(":", 1)
        bbox = parse_bbox_text(coords)
        if bbox is not None:
            boxes.append(
                {
                    "type": "secondary",
                    "det_id": det_id.strip(),
                    "bbox": bbox,
                    "object_hypothesis_id": str(row.get("object_hypothesis_id", "")),
                    "main_tracker_track_id": str(row.get("main_tracker_track_id", "")),
                    "row": row,
                }
            )
    return boxes


def object_observations(row: Mapping[str, str]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    pbox = primary_box(row)
    if pbox is not None:
        observations.append(
            {
                "type": "primary",
                "det_id": str(row.get("primary_det_id", "")),
                "bbox": pbox,
                "object_hypothesis_id": str(row.get("object_hypothesis_id", "")),
                "main_tracker_track_id": str(row.get("main_tracker_track_id", "")),
                "row": row,
            }
        )
    observations.extend(parse_secondary_boxes(row))
    return observations


def group_object_frames(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, int], list[dict[str, str]]]:
    by_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        scene = str(row.get("scene", ""))
        frame = safe_int(row.get("optical_frame_num"))
        if scene and frame is not None:
            by_frame[(scene, frame)].append(dict(row))
    return by_frame


def gt_by_final_id(rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("final_id", "")): dict(row) for row in rows if str(row.get("final_id", ""))}


def support_score(review_bbox: tuple[float, float, float, float], candidate_bbox: tuple[float, float, float, float]) -> dict[str, float]:
    iou = bbox_iou(review_bbox, candidate_bbox)
    containment = bbox_containment(review_bbox, candidate_bbox)
    cx, cy = bbox_center(review_bbox)
    bx, by = bbox_center(candidate_bbox)
    dist = math.hypot(bx - cx, by - cy)
    proximity = max(0.0, 1.0 - dist / max(bbox_diag(review_bbox) + bbox_diag(candidate_bbox), 1.0))
    return {"iou": iou, "containment": containment, "center_distance": dist, "proximity": proximity}


def is_support(metrics: Mapping[str, float]) -> bool:
    return metrics["iou"] >= PAIR_IOU_MIN or metrics["containment"] >= 0.25 or metrics["proximity"] >= 0.55


def collect_frame_support(
    scene: str,
    frame: int,
    review_bbox: tuple[float, float, float, float],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
) -> list[dict[str, Any]]:
    supports: list[dict[str, Any]] = []
    for row in object_by_frame.get((scene, frame), []):
        for obs in object_observations(row):
            metrics = support_score(review_bbox, obs["bbox"])
            if is_support(metrics):
                supports.append({**obs, **metrics, "frame": frame})
    supports.sort(key=lambda item: (float(item["iou"]), float(item["containment"]), float(item["proximity"])), reverse=True)
    return supports


def best_frame_support(
    scene: str,
    frame: int,
    review_bbox: tuple[float, float, float, float],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
) -> dict[str, Any] | None:
    supports = collect_frame_support(scene, frame, review_bbox, object_by_frame)
    return supports[0] if supports else None


def interpolate_bbox(
    frame: int,
    prev_support: Mapping[str, Any] | None,
    next_support: Mapping[str, Any] | None,
) -> tuple[tuple[float, float, float, float] | None, str]:
    if prev_support and next_support:
        prev_frame = int(prev_support["frame"])
        next_frame = int(next_support["frame"])
        if next_frame == prev_frame:
            return prev_support["bbox"], "nearest_previous_support_copy"
        t = (frame - prev_frame) / (next_frame - prev_frame)
        pb = prev_support["bbox"]
        nb = next_support["bbox"]
        return tuple(pb[i] + t * (nb[i] - pb[i]) for i in range(4)), "linear_interpolation_between_nearest_support_frames"
    if prev_support:
        return prev_support["bbox"], "nearest_previous_support_copy"
    if next_support:
        return next_support["bbox"], "nearest_next_support_copy"
    return None, "no_support_frame_available"


def edge_status(review_bbox: tuple[float, float, float, float], supports: Sequence[Mapping[str, Any]]) -> str:
    x1, y1, x2, y2 = review_bbox
    edge = x1 <= 5 or y1 <= 5 or x2 >= OPTICAL_WIDTH - 5 or y2 >= OPTICAL_HEIGHT - 5
    states = []
    for support in supports:
        row = support.get("row", {})
        for key in ("boundary_truncation_state", "partial_full_transition_state", "state_visibility_status"):
            value = str(row.get(key, ""))
            if value and value not in states:
                states.append(value)
    prefix = "review_bbox_edge_truncated" if edge else "review_bbox_not_edge_truncated"
    return prefix + (";" + ";".join(states) if states else "")


def temporal_audit_case(
    triage_row: Mapping[str, str],
    accounting_row: Mapping[str, str],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    scene = str(triage_row["scene"])
    frame = safe_int(triage_row["optical_frame"]) or 0
    sar_frame = safe_int(triage_row["sar_frame"]) or 0
    review_bbox = parse_bbox_text(str(triage_row["review_optical_bbox"]))
    if review_bbox is None:
        raise ValueError(f"Missing review bbox for {scene} {triage_row.get('sar_gt_id')}")

    current_supports = collect_frame_support(scene, frame, review_bbox, object_by_frame)
    current_primary = [item for item in current_supports if item["type"] == "primary" and float(item["iou"]) >= PAIR_IOU_MIN]
    current_secondary = [item for item in current_supports if item["type"] == "secondary" and float(item["iou"]) >= PAIR_IOU_MIN]
    prev_supports: list[dict[str, Any]] = []
    next_supports: list[dict[str, Any]] = []
    for delta in range(1, TEMPORAL_RADIUS_FRAMES + 1):
        prev = best_frame_support(scene, frame - delta, review_bbox, object_by_frame)
        if prev:
            prev_supports.append(prev)
        nxt = best_frame_support(scene, frame + delta, review_bbox, object_by_frame)
        if nxt:
            next_supports.append(nxt)

    nearest_prev = prev_supports[0] if prev_supports else None
    nearest_next = next_supports[0] if next_supports else None
    propagated_bbox, propagation_source = interpolate_bbox(frame, nearest_prev, nearest_next)
    prop_iou = bbox_iou(review_bbox, propagated_bbox) if propagated_bbox else 0.0
    prop_containment = bbox_containment(review_bbox, propagated_bbox) if propagated_bbox else 0.0
    prop_status = (
        "temporal_propagation_can_recover_review_target"
        if propagated_bbox and (prop_iou >= PAIR_IOU_MIN or prop_containment >= 0.30)
        else "temporal_propagation_insufficient_or_needs_review"
    )

    support_object_ids = [str(item["object_hypothesis_id"]) for item in current_supports + prev_supports + next_supports if item.get("object_hypothesis_id")]
    repeated_ids = sorted({item for item in support_object_ids if support_object_ids.count(item) >= 2})
    same_track = bool(repeated_ids)
    all_supports = current_supports + prev_supports + next_supports
    spatial_continuity = bool(prev_supports or next_supports)
    sizes = [bbox_area(item["bbox"]) for item in all_supports if item.get("bbox")]
    size_continuity = "insufficient_support"
    if len(sizes) >= 2:
        ratio = max(sizes) / max(min(sizes), 1e-6)
        size_continuity = "bbox_size_continuity_with_truncation_variation" if ratio <= 8.0 else "bbox_size_changes_heavily_due_to_truncation_or_handoff"

    if current_secondary and prev_supports and next_supports:
        status = "temporal_continuation_with_current_secondary_support"
        confidence = "high"
    elif current_secondary and (prev_supports or next_supports):
        status = "temporal_continuation_with_detection_dropout"
        confidence = "medium_high"
    elif prev_supports and next_supports:
        status = "temporal_continuation_hypothesis_supported"
        confidence = "medium"
    elif prev_supports or next_supports:
        status = "one_sided_temporal_continuation_hypothesis"
        confidence = "low_medium"
    else:
        status = "no_temporal_continuation_support"
        confidence = "low"

    expected_sar = frame * SAR_FPS / OPTICAL_FPS
    temporal_error = sar_frame - expected_sar
    sar_time_ok = abs(temporal_error) <= 2.0
    continuation_reason = (
        f"prev_support_frames={len(prev_supports)};next_support_frames={len(next_supports)};"
        f"current_secondary={bool(current_secondary)};propagation={prop_status};"
        f"software_sync_error_sar_frames={fmt(temporal_error, 3)}"
    )
    blockers = []
    if not current_primary:
        blockers.append("current_frame_primary_target_missing")
    if not current_secondary:
        blockers.append("current_frame_secondary_missing")
    if not sar_time_ok:
        blockers.append("software_sync_frame_error_large")
    if prop_status != "temporal_propagation_can_recover_review_target":
        blockers.append("propagation_needs_manual_review")

    # Existence recovery here means temporal continuity explains target presence;
    # it still remains excluded from full optical-shape statistics.
    existence_recovered = confidence in {"high", "medium_high"} and prop_status == "temporal_propagation_can_recover_review_target"
    secondary_truncated = bool(current_secondary) and not bool(current_primary)
    yolo_candidate = not bool(current_primary) or secondary_truncated

    categories = []
    if existence_recovered:
        categories.append("existence_recovered_by_temporal_continuation")
    if status != "no_temporal_continuation_support":
        categories.append("temporal_continuation_with_detection_dropout")
    if secondary_truncated:
        categories.append("secondary_supported_truncated_same_vehicle")
    if yolo_candidate:
        categories.append("yolo_upgrade_candidate")
    categories.extend(["manual_review_required", "exclude_from_clean_shape_statistics"])

    row = {
        "scene": scene,
        "sar_gt_id": triage_row.get("sar_gt_id", ""),
        "optical_frame": str(frame),
        "sar_frame": str(sar_frame),
        "target_identity": triage_row.get("target_identity", ""),
        "review_bbox": bbox_text(review_bbox),
        "current_frame_primary_available": bool_text(bool(current_primary)),
        "current_frame_secondary_available": bool_text(bool(current_secondary)),
        "current_primary_iou": triage_row.get("best_primary_iou", ""),
        "current_secondary_iou": triage_row.get("best_secondary_iou", ""),
        "previous_support_frame_count": str(len(prev_supports)),
        "next_support_frame_count": str(len(next_supports)),
        "nearest_previous_support_frame": "" if nearest_prev is None else str(nearest_prev["frame"]),
        "nearest_next_support_frame": "" if nearest_next is None else str(nearest_next["frame"]),
        "same_track_support": bool_text(same_track),
        "same_track_ids": ";".join(repeated_ids),
        "spatial_continuity_support": bool_text(spatial_continuity),
        "bbox_size_continuity_support": size_continuity,
        "edge_truncation_status": edge_status(review_bbox, all_supports),
        "temporal_continuation_status": status,
        "temporal_continuation_confidence": confidence,
        "continuation_reason": continuation_reason,
        "propagation_source": propagation_source,
        "propagated_bbox_diagnostic": bbox_text(propagated_bbox),
        "propagated_bbox_iou_with_review": fmt(prop_iou, 6),
        "propagated_bbox_review_containment": fmt(prop_containment, 6),
        "propagation_diagnostic_status": prop_status,
        "sample_use_categories": ";".join(categories),
        "existence_recovered_by_temporal_continuation": bool_text(existence_recovered),
        "temporal_continuation_with_detection_dropout": bool_text(status != "no_temporal_continuation_support"),
        "secondary_supported_truncated_same_vehicle": bool_text(secondary_truncated),
        "sar_posthoc_supported_dropout_case": "",
        "yolo_upgrade_candidate": bool_text(yolo_candidate),
        "manual_review_required": "true",
        "exclude_from_clean_shape_statistics": "true",
        "blockers": ";".join(blockers),
        "notes": "Propagation bbox is diagnostic only; not a final label or runtime prior.",
    }
    context = {
        "review_bbox": review_bbox,
        "current_supports": current_supports,
        "prev_support": nearest_prev,
        "next_support": nearest_next,
        "propagated_bbox": propagated_bbox,
        "propagation_status": prop_status,
        "accounting_row": accounting_row,
    }
    return row, context


def sar_audit_case(temporal_row: Mapping[str, Any], gt_row: Mapping[str, str]) -> dict[str, Any]:
    frame = safe_int(temporal_row.get("optical_frame")) or 0
    sar_frame = safe_int(temporal_row.get("sar_frame")) or 0
    expected = frame * SAR_FPS / OPTICAL_FPS
    temporal_error = sar_frame - expected
    time_ok = abs(temporal_error) <= 2.0
    cx = safe_float(gt_row.get("final_cx")) or 0.0
    cy = safe_float(gt_row.get("final_cy")) or 0.0
    w = safe_float(gt_row.get("final_w")) or 0.0
    h = safe_float(gt_row.get("final_h")) or 0.0
    heading = safe_float(gt_row.get("final_heading_deg")) or 0.0
    ax_bbox = parse_bbox(gt_row, ("final_ax_x1", "final_ax_y1", "final_ax_x2", "final_ax_y2"))
    if ax_bbox is None:
        ax_bbox = (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
    image_path = Path(str(gt_row.get("sar_pseudocolor_path", "")))
    box_mean = bg_mean = box_bg_ratio = peak_bg_ratio = 0.0
    scatter_status = "sar_image_missing_or_unreadable"
    if image_path.exists():
        image = Image.open(image_path).convert("L")
        x1 = max(0, int(math.floor(ax_bbox[0])))
        y1 = max(0, int(math.floor(ax_bbox[1])))
        x2 = min(image.width, int(math.ceil(ax_bbox[2])))
        y2 = min(image.height, int(math.ceil(ax_bbox[3])))
        if x2 > x1 and y2 > y1:
            box = image.crop((x1, y1, x2, y2))
            pad = 20
            bx1 = max(0, x1 - pad)
            by1 = max(0, y1 - pad)
            bx2 = min(image.width, x2 + pad)
            by2 = min(image.height, y2 + pad)
            bg = image.crop((bx1, by1, bx2, by2))
            box_stat = ImageStat.Stat(box)
            bg_stat = ImageStat.Stat(bg)
            box_mean = float(box_stat.mean[0])
            bg_mean = float(bg_stat.mean[0])
            box_peak = float(max(box.getdata())) if box.size[0] and box.size[1] else box_mean
            box_bg_ratio = box_mean / max(bg_mean, 1e-6)
            peak_bg_ratio = box_peak / max(bg_mean, 1e-6)
            if peak_bg_ratio >= 1.8 or box_bg_ratio >= 1.05:
                scatter_status = "sar_gt_crop_has_local_scatter_support"
            else:
                scatter_status = "sar_gt_crop_scatter_support_weak"
    posthoc_support = (
        "sar_posthoc_supported_detection_dropout"
        if time_ok and scatter_status == "sar_gt_crop_has_local_scatter_support"
        else "sar_posthoc_support_requires_review"
    )
    return {
        "scene": temporal_row.get("scene", ""),
        "sar_gt_id": temporal_row.get("sar_gt_id", ""),
        "optical_frame": temporal_row.get("optical_frame", ""),
        "sar_frame": temporal_row.get("sar_frame", ""),
        "expected_sar_frame_raw": fmt(expected, 4),
        "temporal_error_sar_frames": fmt(temporal_error, 4),
        "gt_in_software_sync_window": bool_text(time_ok),
        "sar_gt_center": f"{fmt(cx,3)},{fmt(cy,3)}",
        "sar_gt_width": fmt(w, 3),
        "sar_gt_height": fmt(h, 3),
        "sar_gt_heading_deg": fmt(heading, 3),
        "sar_gt_axis_aligned_bbox": bbox_text(ax_bbox),
        "sar_box_mean": fmt(box_mean, 6),
        "sar_background_mean": fmt(bg_mean, 6),
        "sar_box_to_background_ratio": fmt(box_bg_ratio, 6),
        "sar_peak_to_background_ratio": fmt(peak_bg_ratio, 6),
        "sar_scatter_support_status": scatter_status,
        "sar_posthoc_support_status": posthoc_support,
        "sar_posthoc_support_reason": "SAR GT and SAR image are posthoc-only; support confirms target presence mechanism, not runtime identity truth.",
        "sar_image_path": str(image_path),
        "notes": "SAR crop statistics are posthoc-only and not a runtime detector or scoring rule.",
    }


def load_font(size: int) -> ImageFont.ImageFont:
    for path in (Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf"), Path(r"C:\Windows\Fonts\arial.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_box(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[float, float, float, float] | None,
    offset: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    label: str,
    font: ImageFont.ImageFont,
    width: int = 3,
    dashed: bool = False,
) -> None:
    if bbox is None:
        return
    ox, oy = offset
    coords = [ox + bbox[0] * scale, oy + bbox[1] * scale, ox + bbox[2] * scale, oy + bbox[3] * scale]
    if dashed:
        dash_rectangle(draw, coords, color, width)
    else:
        draw.rectangle(coords, outline=color, width=width)
    draw.text((coords[0] + 2, max(0, coords[1] - 18)), label, fill=color, font=font)


def dash_rectangle(draw: ImageDraw.ImageDraw, coords: Sequence[float], color: tuple[int, int, int], width: int) -> None:
    x1, y1, x2, y2 = coords
    for start in frange(x1, x2, 13):
        draw.line((start, y1, min(start + 8, x2), y1), fill=color, width=width)
        draw.line((start, y2, min(start + 8, x2), y2), fill=color, width=width)
    for start in frange(y1, y2, 13):
        draw.line((x1, start, x1, min(start + 8, y2)), fill=color, width=width)
        draw.line((x2, start, x2, min(start + 8, y2)), fill=color, width=width)


def frange(start: float, stop: float, step: float) -> Iterable[float]:
    value = start
    while value < stop:
        yield value
        value += step


def image_panel(path: Path, size: tuple[int, int]) -> Image.Image:
    if path.exists():
        image = Image.open(path).convert("RGB")
    else:
        image = Image.new("RGB", (int(OPTICAL_WIDTH), int(OPTICAL_HEIGHT)), (235, 235, 235))
    image.thumbnail(size)
    panel = Image.new("RGB", size, "white")
    panel.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return panel


def frame_path_from_accounting(accounting_row: Mapping[str, str], frame: int) -> Path:
    base = Path(str(accounting_row.get("optical_path", "")))
    return base.with_name(f"{frame:06d}{base.suffix or '.png'}")


def render_visual(
    temporal_row: Mapping[str, Any],
    sar_row: Mapping[str, Any],
    context: Mapping[str, Any],
    output_path: Path,
) -> None:
    font_title = load_font(24)
    font = load_font(16)
    font_small = load_font(13)
    page = Image.new("RGB", (1600, 980), "white")
    draw = ImageDraw.Draw(page)
    title = f"{temporal_row['scene']} GT {temporal_row['sar_gt_id']} | 检测缺失时序延续 + SAR后验支持"
    draw.text((25, 18), title, fill=(20, 20, 20), font=font_title)

    accounting_row = context["accounting_row"]
    frame = int(temporal_row["optical_frame"])
    prev_frame = safe_int(temporal_row.get("nearest_previous_support_frame"))
    next_frame = safe_int(temporal_row.get("nearest_next_support_frame"))
    frame_specs = [
        ("前支持帧", prev_frame, context.get("prev_support")),
        ("当前帧", frame, None),
        ("后支持帧", next_frame, context.get("next_support")),
    ]
    panel_w, panel_h = 390, 292
    y0 = 70
    for idx, (label, opt_frame, support) in enumerate(frame_specs):
        x0 = 25 + idx * (panel_w + 18)
        if opt_frame is None:
            panel = Image.new("RGB", (panel_w, panel_h), (245, 245, 245))
        else:
            panel = image_panel(frame_path_from_accounting(accounting_row, opt_frame), (panel_w, panel_h))
        page.paste(panel, (x0, y0))
        scale = min(panel_w / OPTICAL_WIDTH, panel_h / OPTICAL_HEIGHT)
        draw.text((x0, y0 - 22), f"{label}: {opt_frame if opt_frame is not None else '无'}", fill=(20, 20, 20), font=font)
        if label == "当前帧":
            draw_box(draw, context["review_bbox"], (x0, y0), scale, (220, 20, 20), "review框", font_small, 3)
            for sup in context.get("current_supports", []):
                color = (190, 20, 170) if sup["type"] == "secondary" else (20, 130, 220)
                draw_box(draw, sup["bbox"], (x0, y0), scale, color, sup["type"], font_small, 3, dashed=sup["type"] == "secondary")
            draw_box(draw, context.get("propagated_bbox"), (x0, y0), scale, (20, 150, 60), "传播诊断框", font_small, 2, dashed=True)
        elif support:
            draw_box(draw, support.get("bbox"), (x0, y0), scale, (20, 130, 220), f"{support.get('type')}支持", font_small, 3)

    sar_x, sar_y = 25, 420
    sar_path = Path(str(sar_row.get("sar_image_path", "")))
    sar_panel = image_panel(sar_path, (570, 330))
    page.paste(sar_panel, (sar_x, sar_y))
    draw.text((sar_x, sar_y - 24), f"SAR后验帧 {temporal_row['sar_frame']}（仅机制确认）", fill=(20, 20, 20), font=font)
    # Draw approximate GT box on resized full SAR canvas.
    sar_bbox = parse_bbox_text(str(sar_row.get("sar_gt_axis_aligned_bbox", "")))
    if sar_bbox and sar_path.exists():
        image = Image.open(sar_path)
        scale = min(570 / image.width, 330 / image.height)
        x_offset = sar_x + (570 - int(image.width * scale)) // 2
        y_offset = sar_y + (330 - int(image.height * scale)) // 2
        draw_box(draw, sar_bbox, (x_offset, y_offset), scale, (220, 30, 30), "SAR GT", font_small, 3)

    text_x, text_y = 635, 420
    lines = [
        f"当前结论: {temporal_row['temporal_continuation_status']} / {temporal_row['temporal_continuation_confidence']}",
        f"当前主观测可用: {temporal_row['current_frame_primary_available']}；辅助可用: {temporal_row['current_frame_secondary_available']}",
        f"前/后支持帧数: {temporal_row['previous_support_frame_count']} / {temporal_row['next_support_frame_count']}",
        f"传播诊断: {temporal_row['propagation_diagnostic_status']}；containment={temporal_row['propagated_bbox_review_containment']}",
        f"SAR同步误差: {sar_row['temporal_error_sar_frames']} 帧；SAR散射: {sar_row['sar_scatter_support_status']}",
        f"样本用途: {temporal_row['sample_use_categories']}",
        "边界: 传播框不是最终标注；SAR GT/图像只做posthoc机制确认；不写入runtime identity truth。",
    ]
    y = text_y
    for line in lines:
        for wrapped in wrap_text(line, 54):
            draw.text((text_x, y), wrapped, fill=(20, 20, 20), font=font)
            y += 24
        y += 8
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(output_path)


def wrap_text(text: str, width: int) -> list[str]:
    result: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= width:
            result.append(current)
            current = ""
    if current:
        result.append(current)
    return result


def select_sample_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    wanted = [
        "temporal_continuation_with_current_secondary_support",
        "temporal_continuation_hypothesis_supported",
        "one_sided_temporal_continuation_hypothesis",
    ]
    for status in wanted:
        match = next((row for row in rows if row.get("temporal_continuation_status") == status and row not in selected), None)
        if match:
            selected.append(match)
    for scene in ("GM_RM017", "GM_RM019"):
        if not any(row.get("scene") == scene for row in selected):
            match = next((row for row in rows if row.get("scene") == scene), None)
            if match and match not in selected:
                selected.append(match)
    return selected[:4]


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[str]:
    if not rows:
        return ["无。"]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    return lines


def render_report(
    path: Path,
    timestamp: str,
    temporal_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
    sources: Mapping[str, str],
) -> None:
    status_counts = Counter(str(row.get("temporal_continuation_status", "")) for row in temporal_rows)
    category_counter: Counter[str] = Counter()
    for row in temporal_rows:
        for category in str(row.get("sample_use_categories", "")).split(";"):
            if category:
                category_counter[category] += 1
    sar_counts = Counter(str(row.get("sar_posthoc_support_status", "")) for row in sar_rows)
    lines = [
        "# OTY2 检测缺失的时序延续与 SAR 后验支持审计",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本轮只针对 12 条 `no_oty_iou_match` 样本，检查当前帧检测缺失、重度截断、前后帧时序延续和 SAR 后验支持。运行时安全证据、posthoc-only 证据和 detector-ablation 计划分开记录。",
        "",
        "## 三层边界",
        "",
        "- Runtime-safe：光学帧、OTY 主/辅观测、前后帧对象流、软件同步 24:50 时间关系。",
        "- Posthoc-only：SAR GT、SAR 图像局部散射、GT 框形态；只用于机制确认，不能写入 runtime prior construction。",
        "- Detector-ablation：更强 YOLO 只作为 A/B 计划或小样本 dry-run，不提交权重，不把检测数量当核心指标。",
        "",
        "## 总结",
        "",
        f"- 样本数：`{len(temporal_rows)}`。",
        f"- 时序延续状态：`{json.dumps(dict(status_counts), ensure_ascii=False)}`。",
        f"- 样本用途类别：`{json.dumps(dict(category_counter), ensure_ascii=False)}`。",
        f"- SAR 后验支持状态：`{json.dumps(dict(sar_counts), ensure_ascii=False)}`。",
        "",
        "## 逐条样本",
        "",
    ]
    lines.extend(
        markdown_table(
            temporal_rows,
            [
                "scene",
                "sar_gt_id",
                "optical_frame",
                "sar_frame",
                "current_frame_secondary_available",
                "previous_support_frame_count",
                "next_support_frame_count",
                "temporal_continuation_status",
                "propagation_diagnostic_status",
                "sample_use_categories",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 解释",
            "",
            "- 当前帧 YOLO/OTY 主观测缺失不等于目标不存在。多数样本在当前帧有辅助观测，或在前后帧有空间连续的车辆观测。",
            "- `existence_recovered_by_temporal_continuation` 表示时序延续恢复目标存在性；它不等于 clean paired，不等于完整光学框形态样本，不是自动标注。",
            "- `temporal_propagation_can_recover_review_target` 只表示传播诊断能解释 review 框，不是自动标注建议，也不是最终框。",
            "- 有 SAR 后验支持的样本可以用于研究 detection dropout / 重度截断 / SAR 目标存在机制，但不能直接进入完整车辆光学框形态主统计。",
            "- 所有 12 条仍保留 `manual_review_required` 和 `exclude_from_clean_shape_statistics`，避免污染完整车辆形态统计。",
            "",
            "## SAR 后验支持",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            sar_rows,
            [
                "scene",
                "sar_gt_id",
                "sar_frame",
                "gt_in_software_sync_window",
                "sar_box_to_background_ratio",
                "sar_peak_to_background_ratio",
                "sar_scatter_support_status",
                "sar_posthoc_support_status",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 边界 flags",
            "",
        ]
    )
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## 数据源", ""])
    for key, value in sources.items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_yolo_plan(path: Path, timestamp: str, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 YOLO dropout recovery A/B 小样本计划",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本轮没有下载或提交模型权重，也没有替换主线 YOLO。建议下一步只做 12 条样本及其前后帧的小样本 A/B。",
        "",
        "## A/B 输入",
        "",
        "- A 组：当前 OTY/YOLO 输出。",
        "- B 组：本地已有或后续明确下载的更强 YOLO 权重；权重不得提交到 git。",
        "- 帧范围：12 条 no_oty_iou_match 的当前帧，以及前后 3/5/10 帧。",
        "- 类别范围：vehicle-like / car-like object，不把无关 YOLO 类别混入主分析。",
        "",
        "## 核心指标",
        "",
        "- 是否恢复当前帧重度截断车。",
        "- primary missing 是否下降。",
        "- secondary-only 是否下降。",
        "- 检测框对 review 框的 containment / overlap 是否改善。",
        "- 是否引入更多远小噪声。",
        "- 时序连续性是否改善。",
        "- handoff / duplicate 是否下降。",
        "",
        "## 当前 12 条样本给出的动机",
        "",
        f"- YOLO 升级候选：`{summary['yolo_upgrade_candidate_count']}`。",
        f"- 当前帧 secondary-supported 或 temporal continuation supported：`{summary['temporal_continuation_supported_count']}`。",
        f"- SAR 后验支持 detection dropout：`{summary['sar_posthoc_supported_dropout_count']}`。",
        "",
        "## 边界",
        "",
        "A/B 结果只能用于 detector-ablation 观察；不能直接作为 runtime prior 规则、自动标注建议、阈值调参结论或 identity truth。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> None:
    DEFAULT_WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DEFAULT_WORKSPACE_LOG_DIR / f"oty2_detection_dropout_temporal_sar_support_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_detection_dropout_temporal_sar_support_audit",
        f"summary={json.dumps(summary, ensure_ascii=False)}",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    triage_csv = Path(args.triage_csv) if args.triage_csv else latest_path("oty2_no_oty_iou_match_triage_*.csv")
    accounting_csv = Path(args.accounting_csv) if args.accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv")
    gt_csv = Path(args.final_gt_csv)
    object_frame_csv = Path(args.object_frame_state_csv)
    triage_rows = read_csv(triage_csv)
    accounting_rows = read_csv(accounting_csv)
    gt_rows = read_csv(gt_csv)
    object_frame_rows = read_csv(object_frame_csv)
    object_by_frame = group_object_frames(object_frame_rows)
    accounting_by_key = {(row.get("scene", ""), row.get("sar_gt_id", "")): row for row in accounting_rows}
    gt_by_id = gt_by_final_id(gt_rows)

    out_dir = OUTPUT_PARENT / f"oty2_detection_dropout_temporal_sar_support_{timestamp}"
    page_dir = out_dir / "detection_dropout_pages"
    sample_dir = SAMPLE_DIR / f"detection_dropout_temporal_sar_support_{timestamp}"
    page_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    temporal_rows: list[dict[str, Any]] = []
    sar_rows: list[dict[str, Any]] = []
    contexts: dict[tuple[str, str], dict[str, Any]] = {}
    for triage in triage_rows:
        key = (triage.get("scene", ""), triage.get("sar_gt_id", ""))
        accounting = accounting_by_key.get(key, {})
        gt = gt_by_id.get(str(triage.get("sar_gt_id", "")), {})
        temporal_row, context = temporal_audit_case(triage, accounting, object_by_frame)
        sar_row = sar_audit_case(temporal_row, gt) if gt else {}
        if sar_row.get("sar_posthoc_support_status") == "sar_posthoc_supported_detection_dropout":
            temporal_row["sar_posthoc_supported_dropout_case"] = "true"
            temporal_row["sample_use_categories"] = temporal_row["sample_use_categories"] + ";sar_posthoc_supported_dropout_case"
        else:
            temporal_row["sar_posthoc_supported_dropout_case"] = "false"
        page_name = f"detection_dropout_{temporal_row['scene'].lower()}_gt{temporal_row['sar_gt_id']}_of{temporal_row['optical_frame']}_sar{temporal_row['sar_frame']}_{timestamp}.png"
        local_page = page_dir / page_name
        render_visual(temporal_row, sar_row, context, local_page)
        temporal_row["local_visualization_path"] = str(local_page)
        temporal_rows.append(temporal_row)
        sar_rows.append(sar_row)
        contexts[key] = context

    for row in select_sample_rows(temporal_rows):
        local_path = Path(str(row.get("local_visualization_path", "")))
        if local_path.exists():
            sample_path = sample_dir / local_path.name
            shutil.copy2(local_path, sample_path)
            row["repo_sample_visualization_path"] = str(sample_path)

    temporal_csv = REPORT_DIR / f"oty2_detection_dropout_temporal_support_audit_{timestamp}.csv"
    sar_csv = REPORT_DIR / f"oty2_detection_dropout_sar_posthoc_support_audit_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_detection_dropout_temporal_sar_support_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_detection_dropout_temporal_sar_support_summary_{timestamp}.json"
    yolo_plan = REPORT_DIR / f"oty2_yolo_dropout_recovery_ablation_plan_{timestamp}.md"
    sources = {
        "no_oty_iou_match_triage_csv": str(triage_csv),
        "gt_sample_accounting_csv": str(accounting_csv),
        "final_gt_csv": str(gt_csv),
        "object_frame_state_csv": str(object_frame_csv),
        "local_visual_output": str(out_dir),
        "repo_sample_visual_output": str(sample_dir),
    }
    summary = {
        "timestamp": timestamp,
        "sample_count": len(temporal_rows),
        "temporal_continuation_status_counts": dict(Counter(str(row.get("temporal_continuation_status", "")) for row in temporal_rows)),
        "temporal_continuation_supported_count": sum(1 for row in temporal_rows if row.get("temporal_continuation_with_detection_dropout") == "true"),
        "existence_recovered_by_temporal_continuation_count": sum(1 for row in temporal_rows if row.get("existence_recovered_by_temporal_continuation") == "true"),
        "secondary_supported_truncated_same_vehicle_count": sum(1 for row in temporal_rows if row.get("secondary_supported_truncated_same_vehicle") == "true"),
        "sar_posthoc_supported_dropout_count": sum(1 for row in temporal_rows if row.get("sar_posthoc_supported_dropout_case") == "true"),
        "yolo_upgrade_candidate_count": sum(1 for row in temporal_rows if row.get("yolo_upgrade_candidate") == "true"),
        "manual_review_required_count": sum(1 for row in temporal_rows if row.get("manual_review_required") == "true"),
        "exclude_from_clean_shape_statistics_count": sum(1 for row in temporal_rows if row.get("exclude_from_clean_shape_statistics") == "true"),
        "sar_posthoc_support_status_counts": dict(Counter(str(row.get("sar_posthoc_support_status", "")) for row in sar_rows)),
        "local_visualization_count": len(list(page_dir.glob("*.png"))),
        "remote_sample_visualization_count": len(list(sample_dir.glob("*.png"))),
        "boundary_flags": BOUNDARY_FLAGS,
        "sources": sources,
    }

    write_csv(temporal_csv, temporal_rows, TEMPORAL_FIELDS)
    write_csv(sar_csv, sar_rows, SAR_FIELDS)
    render_report(report_md, timestamp, temporal_rows, sar_rows, sources)
    render_yolo_plan(yolo_plan, timestamp, summary)
    write_json(summary_json, summary)
    outputs = {
        "temporal_csv": str(temporal_csv),
        "sar_csv": str(sar_csv),
        "report_md": str(report_md),
        "summary_json": str(summary_json),
        "yolo_plan": str(yolo_plan),
        "local_visualization_dir": str(out_dir),
        "repo_sample_visualization_dir": str(sample_dir),
    }
    write_workspace_log(timestamp, outputs, summary)
    print(json.dumps({"outputs": outputs, "summary": summary}, ensure_ascii=False, indent=2))
    return {"outputs": outputs, "summary": summary}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--triage-csv", default="")
    parser.add_argument("--accounting-csv", default="")
    parser.add_argument("--final-gt-csv", default=str(DEFAULT_GT_CSV))
    parser.add_argument(
        "--object-frame-state-csv",
        default=str(DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"),
    )
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
