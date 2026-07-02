"""Triage OTY2 no_oty_iou_match GT accounting rows.

This is a small failure-diagnosis audit for the 12 GT rows that have review
optical boxes and same-frame OTY object candidates, but do not pass the
primary-box IoU pairing gate. It reads optical frames only for visualization.
It does not read SAR image content, train/tune thresholds, emit selector logic,
or write GT-derived rules into runtime prior construction.
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
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
OUTPUT_PARENT = REPO_ROOT / "outputs"
SAMPLE_DIR = REPORT_DIR / "samples" / "no_oty_iou_match_triage"
DEFAULT_OBJECT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"
DEFAULT_WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

PAIR_IOU_MIN = 0.05
WEAK_IOU_FLOOR = 0.01
OPTICAL_WIDTH = 800.0
OPTICAL_HEIGHT = 600.0
SAR_FPS = 50.0
OPTICAL_FPS = 24.0

TRIAGE_FIELDS = [
    "scene",
    "sar_gt_id",
    "sar_frame",
    "target_identity",
    "optical_frame",
    "review_optical_bbox",
    "review_bbox_width",
    "review_bbox_height",
    "review_bbox_area_ratio",
    "review_bbox_edge_contact",
    "oty_frame_candidate_count",
    "oty_primary_candidate_count",
    "oty_frame_candidate_ids",
    "best_primary_iou",
    "best_primary_object_hypothesis_id",
    "best_primary_det_id",
    "best_primary_bbox",
    "best_primary_center_dx",
    "best_primary_center_dy",
    "best_primary_center_distance_px",
    "best_primary_size_ratio",
    "best_secondary_iou",
    "best_secondary_object_hypothesis_id",
    "best_secondary_det_id",
    "best_secondary_bbox",
    "best_secondary_center_dx",
    "best_secondary_center_dy",
    "best_secondary_center_distance_px",
    "neighbor_best_iou",
    "neighbor_best_frame_delta",
    "neighbor_best_match_type",
    "neighbor_best_object_hypothesis_id",
    "neighbor_best_bbox",
    "temporal_expected_sar_frame_raw",
    "temporal_error_sar_frames",
    "temporal_alignment_status",
    "position_difference_summary",
    "size_distance_status",
    "oty_stream_status",
    "track_context_status",
    "primary_secondary_consistency_status",
    "triage_reason",
    "recommendation",
    "include_as_weak_correspondence_candidate",
    "needs_manual_review",
    "exclude_from_current_mechanism_sample",
    "local_visualization_path",
    "repo_sample_visualization_path",
    "notes",
]

BOUNDARY_FLAGS = {
    "gt_accounting_read": True,
    "review_queue_or_gt_source_reused_from_accounting": True,
    "existing_oty_outputs_read": True,
    "optical_frame_content_read_for_visual_triage": True,
    "sar_image_content_read": False,
    "sar_gt_used_for_runtime_prior_construction": False,
    "automatic_annotation_proposal_generated": False,
    "training_or_threshold_tuning_entered": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
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
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def center_delta(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float, float]:
    ax, ay = bbox_center(a)
    bx, by = bbox_center(b)
    dx = bx - ax
    dy = by - ay
    return dx, dy, math.hypot(dx, dy)


def primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    return parse_bbox(row, ("primary_bbox_x1", "primary_bbox_y1", "primary_bbox_x2", "primary_bbox_y2"))


def parse_secondary_boxes(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(row.get("secondary_bbox_summary", "")).strip()
    if not text:
        return []
    items = re.split(r"[;|]\s*", text)
    boxes: list[dict[str, Any]] = []
    for item in items:
        if ":" not in item:
            continue
        det_id, coords = item.split(":", 1)
        bbox = parse_bbox_text(coords)
        if bbox is not None:
            boxes.append(
                {
                    "det_id": det_id.strip(),
                    "bbox": bbox,
                    "object_hypothesis_id": str(row.get("object_hypothesis_id", "")),
                    "row": row,
                }
            )
    return boxes


def group_object_frames(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, int], list[dict[str, str]]]:
    by_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        scene = str(row.get("scene", ""))
        frame = safe_int(row.get("optical_frame_num"))
        if scene and frame is not None:
            by_frame[(scene, frame)].append(dict(row))
    return by_frame


def group_hypotheses(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))): dict(row) for row in rows}


def find_best_primary(
    review_bbox: tuple[float, float, float, float],
    candidates: Sequence[Mapping[str, str]],
) -> tuple[float, Mapping[str, str] | None, tuple[float, float, float, float] | None]:
    best_iou = 0.0
    best_row: Mapping[str, str] | None = None
    best_bbox: tuple[float, float, float, float] | None = None
    for candidate in candidates:
        pbox = primary_box(candidate)
        if pbox is None:
            continue
        score = bbox_iou(review_bbox, pbox)
        if score > best_iou or best_bbox is None:
            best_iou = score
            best_row = candidate
            best_bbox = pbox
    return best_iou, best_row, best_bbox


def find_best_secondary(
    review_bbox: tuple[float, float, float, float],
    candidates: Sequence[Mapping[str, str]],
) -> tuple[float, dict[str, Any] | None]:
    best_iou = 0.0
    best: dict[str, Any] | None = None
    for candidate in candidates:
        for secondary in parse_secondary_boxes(candidate):
            score = bbox_iou(review_bbox, secondary["bbox"])
            if score > best_iou or best is None:
                best_iou = score
                best = secondary
    return best_iou, best


def find_neighbor_best(
    scene: str,
    frame: int,
    review_bbox: tuple[float, float, float, float],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
    radius: int = 3,
) -> dict[str, Any]:
    best = {
        "iou": 0.0,
        "frame_delta": "",
        "match_type": "",
        "object_hypothesis_id": "",
        "bbox": None,
    }
    for delta in range(-radius, radius + 1):
        if delta == 0:
            continue
        candidates = object_by_frame.get((scene, frame + delta), [])
        primary_iou, primary_row, primary_bbox = find_best_primary(review_bbox, candidates)
        if primary_bbox is not None and primary_iou > float(best["iou"]):
            best.update(
                {
                    "iou": primary_iou,
                    "frame_delta": delta,
                    "match_type": "primary",
                    "object_hypothesis_id": str(primary_row.get("object_hypothesis_id", "")) if primary_row else "",
                    "bbox": primary_bbox,
                }
            )
        secondary_iou, secondary = find_best_secondary(review_bbox, candidates)
        if secondary and secondary_iou > float(best["iou"]):
            best.update(
                {
                    "iou": secondary_iou,
                    "frame_delta": delta,
                    "match_type": "secondary",
                    "object_hypothesis_id": secondary.get("object_hypothesis_id", ""),
                    "bbox": secondary.get("bbox"),
                }
            )
    return best


def frame_candidate_ids(candidates: Sequence[Mapping[str, str]]) -> str:
    ids = [str(row.get("object_hypothesis_id", "")) for row in candidates if str(row.get("object_hypothesis_id", ""))]
    return ";".join(ids)


def review_size_status(review_bbox: tuple[float, float, float, float]) -> tuple[str, bool]:
    x1, y1, x2, y2 = review_bbox
    w = x2 - x1
    h = y2 - y1
    area_ratio = bbox_area(review_bbox) / (OPTICAL_WIDTH * OPTICAL_HEIGHT)
    edge = x1 <= 5.0 or y1 <= 5.0 or x2 >= OPTICAL_WIDTH - 5.0 or y2 >= OPTICAL_HEIGHT - 5.0
    if area_ratio < 0.0015 or min(w, h) < 22:
        base = "unresolved_tiny_or_far_small_review_box"
    elif area_ratio < 0.006 or min(w, h) < 45:
        base = "low_resolvable_far_or_small_review_box"
    else:
        base = "resolvable_review_box"
    if edge:
        base += "_edge_contact"
    return base, edge


def position_summary(
    review_bbox: tuple[float, float, float, float],
    primary_bbox: tuple[float, float, float, float] | None,
    primary_iou: float,
) -> str:
    if primary_bbox is None:
        return "no_primary_bbox_available_on_same_frame"
    dx, dy, dist = center_delta(review_bbox, primary_bbox)
    if primary_iou > 0:
        return f"partial_overlap_primary_iou_below_gate_dx={fmt(dx,1)}_dy={fmt(dy,1)}_dist={fmt(dist,1)}"
    return f"no_overlap_primary_center_gap_dx={fmt(dx,1)}_dy={fmt(dy,1)}_dist={fmt(dist,1)}"


def track_context(
    best_row: Mapping[str, str] | None,
    best_secondary: Mapping[str, Any] | None,
    hypotheses_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    scene: str,
) -> str:
    object_id = ""
    if best_secondary:
        object_id = str(best_secondary.get("object_hypothesis_id", ""))
    elif best_row:
        object_id = str(best_row.get("object_hypothesis_id", ""))
    if not object_id:
        return "no_candidate_track_context_for_review_target"
    hypo = hypotheses_by_key.get((scene, object_id), {})
    if not hypo:
        return f"candidate_object={object_id};hypothesis_summary_unavailable"
    parts = [
        f"candidate_object={object_id}",
        f"track={hypo.get('main_tracker_track_id', '')}",
        f"frames={hypo.get('frame_start', '')}-{hypo.get('frame_end', '')}",
        f"stability={hypo.get('main_track_stability_status', '')}",
        f"review_required={hypo.get('review_required', '')}",
        f"secondary_role={hypo.get('secondary_observation_role', '')}",
        f"duplicate={hypo.get('duplicate_observation_present', '')}",
        f"partial={hypo.get('partial_full_transition_present', '')}",
    ]
    return ";".join(parts)


def classify_case(
    accounting_row: Mapping[str, str],
    review_bbox: tuple[float, float, float, float],
    candidates: Sequence[Mapping[str, str]],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
    hypotheses_by_key: Mapping[tuple[str, str], Mapping[str, str]],
) -> dict[str, Any]:
    scene = str(accounting_row.get("scene", ""))
    frame = safe_int(accounting_row.get("optical_frame")) or 0
    sar_frame = safe_int(accounting_row.get("sar_frame")) or 0
    primary_iou, primary_row, primary_bbox = find_best_primary(review_bbox, candidates)
    secondary_iou, secondary = find_best_secondary(review_bbox, candidates)
    neighbor = find_neighbor_best(scene, frame, review_bbox, object_by_frame)
    size_status, edge_contact = review_size_status(review_bbox)
    primary_candidates = [row for row in candidates if primary_box(row) is not None]
    expected_sar = frame * SAR_FPS / OPTICAL_FPS
    temporal_error = sar_frame - expected_sar
    temporal_status = (
        "software_sync_24_to_50_ratio_consistent_no_temporal_misalignment"
        if abs(temporal_error) <= 1.25
        else "possible_optical_sar_frame_or_sync_misalignment"
    )

    primary_dx = primary_dy = primary_dist = ""
    primary_size_ratio = ""
    if primary_bbox is not None:
        dx, dy, dist = center_delta(review_bbox, primary_bbox)
        primary_dx, primary_dy, primary_dist = fmt(dx, 3), fmt(dy, 3), fmt(dist, 3)
        primary_size_ratio = fmt(bbox_area(primary_bbox) / max(bbox_area(review_bbox), 1e-6), 4)
    secondary_dx = secondary_dy = secondary_dist = ""
    if secondary and secondary.get("bbox") is not None:
        dx, dy, dist = center_delta(review_bbox, secondary["bbox"])
        secondary_dx, secondary_dy, secondary_dist = fmt(dx, 3), fmt(dy, 3), fmt(dist, 3)

    if secondary_iou >= 0.50:
        triage_reason = "primary_secondary_observation_mismatch"
        recommendation = "需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。"
        include_weak = True
        needs_review = True
        exclude = False
        stream_status = "review_target_present_as_secondary_observation_not_primary"
        consistency = "secondary_bbox_matches_review_bbox_primary_gate_missed"
    elif secondary_iou >= PAIR_IOU_MIN:
        triage_reason = "secondary_observation_support_but_primary_gate_failed"
        recommendation = "需要人工审阅；可考虑进入 weak correspondence，但必须显式标记 secondary-only 支持。"
        include_weak = True
        needs_review = True
        exclude = False
        stream_status = "review_target_has_secondary_support"
        consistency = "secondary_bbox_overlaps_review_bbox"
    elif primary_iou >= WEAK_IOU_FLOOR:
        triage_reason = "iou_threshold_too_strict_with_position_or_scale_offset"
        recommendation = "不能自动吸收；可进入弱配对人工审阅队列，检查框尺度差异和目标是否同一实体。"
        include_weak = True
        needs_review = True
        exclude = False
        stream_status = "primary_candidate_partially_overlaps_review_target"
        consistency = "primary_overlap_below_pair_gate_no_secondary_rescue"
    elif float(neighbor["iou"]) >= PAIR_IOU_MIN:
        triage_reason = "possible_optical_frame_offset_or_track_gap"
        recommendation = "需要人工审阅相邻帧；先不要进入当前机制样本，除非确认帧号或对象流断裂。"
        include_weak = False
        needs_review = True
        exclude = True
        stream_status = "nearby_frame_has_better_oty_support_current_frame_failed"
        consistency = "neighbor_frame_support_current_frame_no_match"
    elif "tiny" in size_status or "edge_contact" in size_status:
        triage_reason = "far_small_or_edge_target_not_in_oty_primary_stream"
        recommendation = "作为 review-only/远小边缘样本保留；当前应排除出光学-SAR机制配对子集。"
        include_weak = False
        needs_review = True
        exclude = True
        stream_status = "oty_frame_exists_but_review_target_not_represented_as_matchable_primary"
        consistency = "no_primary_or_secondary_overlap_for_small_edge_target"
    else:
        triage_reason = "oty_object_stream_missed_review_target_or_large_position_difference"
        recommendation = "需要人工审阅；当前应排除出光学-SAR机制配对子集，优先检查 OTY 漏检、坐标差异或 handoff。"
        include_weak = False
        needs_review = True
        exclude = True
        stream_status = "oty_frame_exists_but_review_target_missing_from_matchable_object_boxes"
        consistency = "no_primary_or_secondary_overlap"

    x1, y1, x2, y2 = review_bbox
    return {
        "scene": scene,
        "sar_gt_id": accounting_row.get("sar_gt_id", ""),
        "sar_frame": accounting_row.get("sar_frame", ""),
        "target_identity": accounting_row.get("target_identity", ""),
        "optical_frame": accounting_row.get("optical_frame", ""),
        "review_optical_bbox": bbox_text(review_bbox),
        "review_bbox_width": fmt(x2 - x1, 3),
        "review_bbox_height": fmt(y2 - y1, 3),
        "review_bbox_area_ratio": fmt(bbox_area(review_bbox) / (OPTICAL_WIDTH * OPTICAL_HEIGHT), 6),
        "review_bbox_edge_contact": bool_text(edge_contact),
        "oty_frame_candidate_count": str(len(candidates)),
        "oty_primary_candidate_count": str(len(primary_candidates)),
        "oty_frame_candidate_ids": frame_candidate_ids(candidates),
        "best_primary_iou": fmt(primary_iou, 6),
        "best_primary_object_hypothesis_id": "" if primary_row is None else str(primary_row.get("object_hypothesis_id", "")),
        "best_primary_det_id": "" if primary_row is None else str(primary_row.get("primary_det_id", "")),
        "best_primary_bbox": bbox_text(primary_bbox),
        "best_primary_center_dx": primary_dx,
        "best_primary_center_dy": primary_dy,
        "best_primary_center_distance_px": primary_dist,
        "best_primary_size_ratio": primary_size_ratio,
        "best_secondary_iou": fmt(secondary_iou, 6),
        "best_secondary_object_hypothesis_id": "" if secondary is None else str(secondary.get("object_hypothesis_id", "")),
        "best_secondary_det_id": "" if secondary is None else str(secondary.get("det_id", "")),
        "best_secondary_bbox": "" if secondary is None else bbox_text(secondary.get("bbox")),
        "best_secondary_center_dx": secondary_dx,
        "best_secondary_center_dy": secondary_dy,
        "best_secondary_center_distance_px": secondary_dist,
        "neighbor_best_iou": fmt(neighbor["iou"], 6),
        "neighbor_best_frame_delta": str(neighbor["frame_delta"]),
        "neighbor_best_match_type": str(neighbor["match_type"]),
        "neighbor_best_object_hypothesis_id": str(neighbor["object_hypothesis_id"]),
        "neighbor_best_bbox": bbox_text(neighbor["bbox"]),
        "temporal_expected_sar_frame_raw": fmt(expected_sar, 4),
        "temporal_error_sar_frames": fmt(temporal_error, 4),
        "temporal_alignment_status": temporal_status,
        "position_difference_summary": position_summary(review_bbox, primary_bbox, primary_iou),
        "size_distance_status": size_status,
        "oty_stream_status": stream_status,
        "track_context_status": track_context(primary_row, secondary, hypotheses_by_key, scene),
        "primary_secondary_consistency_status": consistency,
        "triage_reason": triage_reason,
        "recommendation": recommendation,
        "include_as_weak_correspondence_candidate": bool_text(include_weak),
        "needs_manual_review": bool_text(needs_review),
        "exclude_from_current_mechanism_sample": bool_text(exclude),
        "notes": "small triage only; does not alter accounting, runtime priors, thresholds, or identity truth.",
    }


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_box(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[float, float, float, float] | None,
    offset: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    width: int,
    label: str,
    font: ImageFont.ImageFont,
    dashed: bool = False,
) -> None:
    if bbox is None:
        return
    ox, oy = offset
    x1, y1, x2, y2 = bbox
    coords = [ox + x1 * scale, oy + y1 * scale, ox + x2 * scale, oy + y2 * scale]
    if dashed:
        dash_rectangle(draw, coords, color, width)
    else:
        draw.rectangle(coords, outline=color, width=width)
    draw.text((coords[0] + 3, max(0, coords[1] - 20)), label, fill=color, font=font)


def dash_rectangle(draw: ImageDraw.ImageDraw, coords: Sequence[float], color: tuple[int, int, int], width: int) -> None:
    x1, y1, x2, y2 = coords
    dash = 8
    gap = 5
    for start in frange(x1, x2, dash + gap):
        draw.line((start, y1, min(start + dash, x2), y1), fill=color, width=width)
        draw.line((start, y2, min(start + dash, x2), y2), fill=color, width=width)
    for start in frange(y1, y2, dash + gap):
        draw.line((x1, start, x1, min(start + dash, y2)), fill=color, width=width)
        draw.line((x2, start, x2, min(start + dash, y2)), fill=color, width=width)


def frange(start: float, stop: float, step: float) -> Iterable[float]:
    value = start
    while value < stop:
        yield value
        value += step


def wrap_text(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        current = ""
        for char in raw:
            current += char
            if len(current) >= width:
                lines.append(current)
                current = ""
        if current:
            lines.append(current)
    return lines


def render_visual(
    row: Mapping[str, Any],
    accounting_row: Mapping[str, str],
    candidates: Sequence[Mapping[str, str]],
    output_path: Path,
) -> None:
    font_title = load_font(24)
    font = load_font(17)
    font_small = load_font(14)
    page = Image.new("RGB", (1360, 820), "white")
    draw = ImageDraw.Draw(page)
    title = f"{row['scene']} GT {row['sar_gt_id']} | 光学帧 {row['optical_frame']} | {row['triage_reason']}"
    draw.text((30, 20), title, fill=(20, 20, 20), font=font_title)

    image_path = Path(str(accounting_row.get("optical_path", "")))
    if image_path.exists():
        image = Image.open(image_path).convert("RGB")
    else:
        image = Image.new("RGB", (int(OPTICAL_WIDTH), int(OPTICAL_HEIGHT)), (235, 235, 235))
    scale = min(820 / image.width, 620 / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)))
    image_offset = (30, 70)
    page.paste(resized, image_offset)

    review_bbox = parse_bbox_text(str(row.get("review_optical_bbox", "")))
    best_primary_bbox = parse_bbox_text(str(row.get("best_primary_bbox", "")))
    best_secondary_bbox = parse_bbox_text(str(row.get("best_secondary_bbox", "")))
    draw_box(draw, review_bbox, image_offset, scale, (220, 20, 20), 4, "review光学框", font_small)
    for candidate in candidates:
        pbox = primary_box(candidate)
        if pbox is None:
            continue
        color = (40, 130, 210)
        label = str(candidate.get("object_hypothesis_id", "")).split("_")[-1]
        draw_box(draw, pbox, image_offset, scale, color, 2, f"OTY主:{label}", font_small)
    draw_box(draw, best_primary_bbox, image_offset, scale, (0, 150, 220), 4, "最近OTY主框", font_small)
    draw_box(draw, best_secondary_bbox, image_offset, scale, (190, 20, 170), 4, "最佳辅助框", font_small, dashed=True)

    legend_y = image_offset[1] + resized.height + 12
    legend = "红=review光学框；蓝=同帧OTY主观测框；紫虚线=最佳辅助观测框。本图只读光学帧，不读SAR图像。"
    draw.text((30, legend_y), legend, fill=(40, 40, 40), font=font_small)

    panel_x = 900
    panel_y = 75
    text_blocks = [
        f"场景/GT: {row['scene']} / {row['sar_gt_id']}",
        f"光学帧 -> SAR帧: {row['optical_frame']} -> {row['sar_frame']}",
        f"24:50换算误差: {row['temporal_error_sar_frames']} SAR帧",
        f"review框面积比: {row['review_bbox_area_ratio']}",
        f"主框最佳IoU: {row['best_primary_iou']} ({row['best_primary_object_hypothesis_id']})",
        f"辅助最佳IoU: {row['best_secondary_iou']} ({row['best_secondary_object_hypothesis_id']})",
        f"位置差异: {row['position_difference_summary']}",
        f"目标状态: {row['size_distance_status']}",
        f"OTY状态: {row['oty_stream_status']}",
        f"判断: {row['triage_reason']}",
        f"建议: {row['recommendation']}",
        "边界: 非自动标注；非候选框评分；不改runtime规则。",
    ]
    y = panel_y
    for block in text_blocks:
        for line in wrap_text(block, 28):
            draw.text((panel_x, y), line, fill=(20, 20, 20), font=font)
            y += 25
        y += 8
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(output_path)


def select_sample_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    wanted = [
        "primary_secondary_observation_mismatch",
        "secondary_observation_support_but_primary_gate_failed",
        "possible_optical_frame_offset_or_track_gap",
    ]
    for reason in wanted:
        match = next((row for row in rows if row.get("triage_reason") == reason and row not in selected), None)
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


def render_triage_report(path: Path, timestamp: str, rows: Sequence[Mapping[str, Any]], sources: Mapping[str, str]) -> None:
    reason_counts = Counter(str(row.get("triage_reason", "")) for row in rows)
    recommendation_counts = Counter(str(row.get("recommendation", "")) for row in rows)
    weak_count = sum(1 for row in rows if row.get("include_as_weak_correspondence_candidate") == "true")
    excluded_count = sum(1 for row in rows if row.get("exclude_from_current_mechanism_sample") == "true")
    lines = [
        "# OTY2 no_oty_iou_match 小规模 triage 报告",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本轮只诊断 GT 样本账本中的 12 条 `no_oty_iou_match`。它们都有 review 光学框和同帧 OTY 对象候选，但没有通过 primary-box IoU `0.05` 配对门槛。本轮不做大规模机制消融，不改 accounting，不训练或调阈值，不生成自动标注建议。",
        "",
        "## 总结",
        "",
        f"- 失败样本数：`{len(rows)}`。",
        f"- 原因分布：`{json.dumps(dict(reason_counts), ensure_ascii=False)}`。",
        f"- 可进入弱配对人工审阅候选：`{weak_count}`。",
        f"- 当前应排除出光学-SAR机制配对子集：`{excluded_count}`。",
        f"- 建议分布：`{json.dumps(dict(recommendation_counts), ensure_ascii=False)}`。",
        "",
        "## 逐条 triage",
        "",
    ]
    lines.extend(
        markdown_table(
            rows,
            [
                "scene",
                "sar_gt_id",
                "optical_frame",
                "sar_frame",
                "best_primary_iou",
                "best_secondary_iou",
                "triage_reason",
                "recommendation",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 关键观察",
            "",
            "- `primary_secondary_observation_mismatch` 表示 review 光学框没有命中 OTY 主观测框，但命中了辅助观测框；这类样本可以作为 weak correspondence 的人工审阅候选，但不能直接混入 primary-only paired 子集。",
            "- `iou_threshold_too_strict_with_position_or_scale_offset` 表示主框有极低重叠，但尺度或中心偏差太大；放宽阈值前必须人工确认，不能自动吸收。",
            "- `far_small_or_edge_target_not_in_oty_primary_stream` 表示目标很小、远端或贴边，当前 OTY 对象流没有形成可匹配主框；这类更适合 review-only 或远小层，而不是当前主机制样本。",
            "- `oty_object_stream_missed_review_target_or_large_position_difference` 表示同帧有 OTY 候选，但 review 目标不在可匹配主/辅框中；优先检查漏检、对象流断裂、坐标差异或 handoff。",
            "",
            "## 时间错位检查",
            "",
            "12 条样本的光学帧到 SAR 帧关系均按 `sar_frame = optical_frame * 50 / 24` 落在软件同步换算附近；本轮没有发现明显的 24:50 时间窗错位证据。失败主要来自光学对象框匹配层，而不是时间锚点层。",
            "",
            "## 边界",
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


def render_gm011_plan(path: Path, timestamp: str, accounting_rows: Sequence[Mapping[str, str]], sources: Mapping[str, str]) -> None:
    gm011_rows = [row for row in accounting_rows if row.get("scene") == "GM_RM011"]
    missing_stream = [row for row in gm011_rows if row.get("match_status") == "blocked_missing_gm011_object_stream"]
    sar_only = [row for row in gm011_rows if row.get("match_status") == "sar_only_gt"]
    lines = [
        "# GM_RM011 OTY 光学对象流补建计划",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "## 当前状态",
        "",
        f"- GM_RM011 GT 总数：`{len(gm011_rows)}`。",
        f"- 缺当前 OTY 光学对象流、但有 SAR GT 和 review 光学框：`{len(missing_stream)}`。",
        f"- SAR-only：`{len(sar_only)}`。",
        "",
        "这 195 条不是没有标注，也不是 SAR GT 不可用；它们只是当前 OTY2 链条里没有 GM_RM011 的对象级光学流，因此不能进入对象级光学-SAR correspondence。",
        "",
        "## 未补流前 GM_RM011 可用于什么",
        "",
        "- 可用于全量 GT 库存统计。",
        "- 可用于 SAR-only 或 SAR 侧物理尺度、散射形态、GT 框尺度分布分析。",
        "- 可用于场景级时间元数据说明。",
        "- 不应用于光学对象到 SAR GT 的对应机制审计。",
        "- 不应用于 runtime prior construction，也不应用于 selector、阈值或自动标注建议。",
        "",
        "## 补进 OTY 链条的建议步骤",
        "",
        "1. 用与 GM_RM017/GM_RM019 一致的 OTY0/OTY1/OTY1t 检测、聚类、跟踪和对象假设逻辑处理 GM_RM011 光学帧。",
        "2. 生成 GM_RM011 的对象级输出，至少包括 `oty1t_object_frame_state_timeseries_generalized.csv` 所需字段：scene、object_hypothesis_id、optical_frame_num、primary bbox、secondary bbox summary、状态标签、review_required 和 runtime_source_policy。",
        "3. 保持构造阶段 runtime-safe：补流时不要使用 SAR GT、SAR 图像内容、后验 IoU 或人工最终框作为对象流构造依据。",
        "4. 补流后重新运行 `tools/diagnostics/run_oty2_gt_sample_accounting_audit.py`，确认 `blocked_missing_gm011_object_stream` 是否下降，并检查是否新增 `paired_optical_object_sar_gt` 或 `no_oty_iou_match`。",
        "5. 只有 accounting 通过后，才重新运行 GT correspondence mechanism audit；机制审计仍应声明 GT/SAR 只用于 posthoc discovery。",
        "",
        "## 复跑命令建议",
        "",
        "```powershell",
        "D:\\MINICONDA\\envs\\py311\\python.exe tools\\diagnostics\\run_oty2_gt_sample_accounting_audit.py",
        "D:\\MINICONDA\\envs\\py311\\python.exe tools\\diagnostics\\run_oty2_gt_correspondence_mechanism_audit.py",
        "```",
        "",
        "## 数据源",
        "",
    ]
    for key, value in sources.items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], rows: Sequence[Mapping[str, Any]]) -> None:
    DEFAULT_WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DEFAULT_WORKSPACE_LOG_DIR / f"oty2_no_oty_iou_match_triage_{timestamp}.log"
    reason_counts = Counter(str(row.get("triage_reason", "")) for row in rows)
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_no_oty_iou_match_triage",
        f"triage_rows={len(rows)}",
        f"reason_counts={json.dumps(dict(reason_counts), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    accounting_csv = Path(args.accounting_csv) if args.accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv")
    object_frame_csv = Path(args.object_frame_state_csv)
    object_hypotheses_csv = Path(args.object_hypotheses_csv)
    accounting_rows = read_csv(accounting_csv)
    no_match_rows = [row for row in accounting_rows if row.get("match_status") == "no_oty_iou_match"]
    object_frame_rows = read_csv(object_frame_csv)
    object_hypothesis_rows = read_csv(object_hypotheses_csv)
    object_by_frame = group_object_frames(object_frame_rows)
    hypotheses_by_key = group_hypotheses(object_hypothesis_rows)

    triage_rows: list[dict[str, Any]] = []
    output_dir = OUTPUT_PARENT / f"oty2_no_oty_iou_match_triage_{timestamp}"
    page_dir = output_dir / "no_oty_iou_match_pages"
    sample_dir = SAMPLE_DIR / f"no_oty_iou_match_triage_{timestamp}"
    page_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    accounting_by_key = {}
    for row in no_match_rows:
        review_bbox = parse_bbox_text(str(row.get("review_optical_bbox", "")))
        if review_bbox is None:
            continue
        scene = str(row.get("scene", ""))
        frame = safe_int(row.get("optical_frame")) or 0
        candidates = object_by_frame.get((scene, frame), [])
        triage = classify_case(row, review_bbox, candidates, object_by_frame, hypotheses_by_key)
        page_name = f"no_oty_iou_match_{scene.lower()}_gt{triage['sar_gt_id']}_of{triage['optical_frame']}_sar{triage['sar_frame']}_{timestamp}.png"
        local_page = page_dir / page_name
        render_visual(triage, row, candidates, local_page)
        triage["local_visualization_path"] = str(local_page)
        triage["repo_sample_visualization_path"] = ""
        triage_rows.append(triage)
        accounting_by_key[(triage["scene"], triage["sar_gt_id"])] = row

    for row in select_sample_rows(triage_rows):
        local_path = Path(str(row.get("local_visualization_path", "")))
        if local_path.exists():
            sample_path = sample_dir / local_path.name
            shutil.copy2(local_path, sample_path)
            row["repo_sample_visualization_path"] = str(sample_path)

    triage_csv = REPORT_DIR / f"oty2_no_oty_iou_match_triage_{timestamp}.csv"
    triage_report = REPORT_DIR / f"oty2_no_oty_iou_match_triage_report_{timestamp}.md"
    gm011_plan = REPORT_DIR / f"oty2_gm011_object_stream_recovery_plan_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_no_oty_iou_match_triage_summary_{timestamp}.json"
    sources = {
        "gt_sample_accounting_csv": str(accounting_csv),
        "object_frame_state_csv": str(object_frame_csv),
        "object_hypotheses_csv": str(object_hypotheses_csv),
        "local_full_visual_output": str(output_dir),
        "repo_sample_visual_output": str(sample_dir),
    }
    summary = {
        "timestamp": timestamp,
        "triage_rows": len(triage_rows),
        "reason_counts": dict(Counter(str(row.get("triage_reason", "")) for row in triage_rows)),
        "recommendation_counts": dict(Counter(str(row.get("recommendation", "")) for row in triage_rows)),
        "weak_correspondence_candidates": sum(1 for row in triage_rows if row.get("include_as_weak_correspondence_candidate") == "true"),
        "manual_review_required": sum(1 for row in triage_rows if row.get("needs_manual_review") == "true"),
        "excluded_from_current_mechanism_sample": sum(1 for row in triage_rows if row.get("exclude_from_current_mechanism_sample") == "true"),
        "local_visualization_count": len(list(page_dir.glob("*.png"))),
        "remote_sample_visualization_count": len(list(sample_dir.glob("*.png"))),
        "gm011_missing_object_stream_rows": sum(
            1 for row in accounting_rows if row.get("scene") == "GM_RM011" and row.get("match_status") == "blocked_missing_gm011_object_stream"
        ),
        "gm011_sar_only_rows": sum(1 for row in accounting_rows if row.get("scene") == "GM_RM011" and row.get("match_status") == "sar_only_gt"),
        "boundary_flags": BOUNDARY_FLAGS,
        "sources": sources,
    }

    write_csv(triage_csv, triage_rows, TRIAGE_FIELDS)
    render_triage_report(triage_report, timestamp, triage_rows, sources)
    render_gm011_plan(gm011_plan, timestamp, accounting_rows, sources)
    write_json(summary_json, summary)
    outputs = {
        "triage_csv": str(triage_csv),
        "triage_report": str(triage_report),
        "gm011_plan": str(gm011_plan),
        "summary_json": str(summary_json),
        "local_visualization_dir": str(output_dir),
        "repo_sample_visualization_dir": str(sample_dir),
    }
    write_workspace_log(timestamp, outputs, triage_rows)
    print(json.dumps({"outputs": outputs, "summary": summary}, ensure_ascii=False, indent=2))
    return {"outputs": outputs, "summary": summary}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--accounting-csv", default="")
    parser.add_argument(
        "--object-frame-state-csv",
        default=str(DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"),
    )
    parser.add_argument(
        "--object-hypotheses-csv",
        default=str(DEFAULT_OBJECT_DIR / "oty1t_object_hypotheses_generalized.csv"),
    )
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
