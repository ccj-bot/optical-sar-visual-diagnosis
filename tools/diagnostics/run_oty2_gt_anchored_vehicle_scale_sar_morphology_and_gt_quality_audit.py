"""OTY2 GT-anchored vehicle-scale SAR morphology and GT quality audit.

This is a bounded posthoc mechanism diagnostic. It anchors SAR morphology to
SAR GT vehicle scale, audits GT quality, and marks paired cases where the
optical-derived support misses the GT-anchored vehicle-scale structure.

It does not output revised GT boxes, final candidate boxes, annotation
proposals, selector/ranking results, training products, tuned thresholds, or
identity-truth claims. SAR GT and SAR image observations remain posthoc
diagnosis / validation only and are not written into runtime prediction logic.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon
from scipy import ndimage

from run_oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage import (
    angle_in_interval,
    crop_box_for,
    fan_azimuth,
    fan_radius,
    gt_pixel_table,
    read_image_gray,
    support_available,
    support_boundary_points,
)
from run_oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion import (
    PAIRED_POOL,
    box_available,
    gt_box_from_accounting,
    gt_box_from_correspondence,
    pool_type as source_pool_type,
    rotated_corners,
    sanitize,
)
from run_oty2_support_overlay_visualization_qa_and_chinese_review_atlas import (
    FONT,
    support_closed_polygon,
    wrap_zh,
)
from run_oty2_support_region_sar_observation_probe import (
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    compact_counts,
    fmt,
    latest_path,
    read_csv,
    safe_float,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
VISUAL_DIR = REPORT_DIR / "visual_exemplars"
STATE_MODE = "state_conditioned_range_band"

SCALE_FIELDS = [
    "gt_id",
    "scene",
    "sar_frame",
    "pool_type",
    "gt_box_available",
    "image_available",
    "gt_x",
    "gt_y",
    "gt_w",
    "gt_h",
    "gt_area_px",
    "gt_aspect_ratio",
    "gt_long_axis_px",
    "gt_short_axis_px",
    "gt_orientation_proxy",
    "near_image_boundary",
    "valid_for_scale_reference",
    "scale_outlier_flag",
    "scale_outlier_reason",
    "notes",
]

QUALITY_FIELDS = [
    "gt_id",
    "scene",
    "sar_frame",
    "pool_type",
    "gt_quality_label",
    "gt_quality_confidence",
    "gt_area_px",
    "gt_energy_inside",
    "gt_energy_nearby_context",
    "energy_center_offset_from_gt_center",
    "dominant_energy_inside_gt",
    "vehicle_scale_structure_inside_gt",
    "gt_contains_most_vehicle_structure",
    "gt_contains_too_much_background",
    "needs_manual_gt_review",
    "review_reason",
    "not_allowed_conclusion",
]

MORPHOLOGY_FIELDS = [
    "gt_id",
    "case_id",
    "scene",
    "sar_frame",
    "pool_type",
    "gt_quality_label",
    "gt_crop_available",
    "dominant_energy_pattern",
    "dominant_side_or_axis_proxy",
    "energy_distribution_description",
    "near_or_dominant_side_ridge_proxy",
    "corner_or_endpoint_hotspot_proxy",
    "far_or_opposite_side_weak_return_proxy",
    "discontinuous_edge_proxy",
    "enclosed_shell_proxy",
    "block_like_body_proxy",
    "range_spread_with_core_proxy",
    "vehicle_morphology_supported",
    "morphology_strength",
    "confounders",
    "posthoc_only",
    "notes",
]

HIERARCHY_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "component_id",
    "source_region",
    "component_area",
    "component_long_axis",
    "component_short_axis",
    "component_aspect_ratio",
    "component_energy",
    "relative_to_gt_scale",
    "hierarchy_label",
    "why_not_vehicle_if_atom",
    "composition_group_id",
    "composition_description",
    "posthoc_gt_relation",
    "notes",
]

SUPPORT_MISS_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "optical_state",
    "support_available",
    "gt_quality_label",
    "gt_vehicle_morphology_supported",
    "support_gt_area_coverage",
    "support_gt_energy_coverage",
    "support_morphology_coverage",
    "vehicle_scale_morphology_inside_support",
    "main_gt_structure_outside_support",
    "support_miss_vehicle_structure",
    "support_failure_type",
    "if_support_miss_do_not_search_inside_support",
    "recommended_next_action",
    "not_allowed_conclusion",
]

REVIEW_FIELDS = [
    "review_id",
    "gt_id",
    "case_id",
    "scene",
    "sar_frame",
    "category",
    "why_selected",
    "what_to_look_for",
    "possible_decision_options",
    "image_panel_path",
    "notes",
]

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_quality_audit_entered": True,
    "gt_anchored_vehicle_scale_morphology_entered": True,
    "atom_part_shell_hierarchy_entered": True,
    "support_miss_diagnostic_entered": True,
    "visual_review_candidate_list_generated": True,
    "chinese_atlas_generated": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "revised_gt_box_output": False,
    "final_candidate_box_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "gt_quality_audit_used_as_auto_relabel": False,
    "vehicle_scale_shell_hypothesis_written_as_annotation_rule": False,
    "support_miss_written_as_runtime_rule": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
    "archive_or_old_work_used_as_active_source": False,
    "zip_7z_rar_committed": False,
}


class GrayImageCache:
    def __init__(self, max_images: int = 128) -> None:
        self.max_images = max_images
        self._cache: dict[str, np.ndarray | None] = {}

    def image(self, path_text: str) -> np.ndarray | None:
        key = str(path_text or "")
        if key in self._cache:
            return self._cache[key]
        arr = read_image_gray(key)
        if len(self._cache) >= self.max_images:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = arr
        return arr


def case_id_from_corr(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    opt = sanitize(row.get("optical_frame", "opt"))
    sar = sanitize(row.get("sar_frame", "sar"))
    obj = sanitize(row.get("object_hypothesis_id", "obj"))
    return f"PAIR_{scene}_o{opt}_s{sar}_{obj}"


def case_id_from_support(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    opt = sanitize(row.get("optical_frame", "opt"))
    sar = sanitize(row.get("sar_frame", "sar"))
    obj = sanitize(row.get("object_hypothesis_id", "obj"))
    return f"PAIR_{scene}_o{opt}_s{sar}_{obj}"


def gt_key(scene: Any, sar_frame: Any, gt_id: Any) -> tuple[str, str, str]:
    return (str(scene), str(sar_frame), str(gt_id))


def bool_yes(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1"}


def pool_label(row: Mapping[str, Any]) -> str:
    label = source_pool_type(row)
    if label == "gm011_blocked":
        return "gm011_waiting_object_stream"
    if label in {PAIRED_POOL, "sar_only", "dropout_special"}:
        return label
    return "unknown"


def percentile(values: Sequence[float], q: float) -> float | None:
    clean = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not clean:
        return None
    idx = min(len(clean) - 1, max(0, int(math.floor((len(clean) - 1) * q))))
    return clean[idx]


def median_text(values: Sequence[float]) -> str:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    return fmt(median(clean), 4) if clean else ""


def metric_summary(values: Sequence[float]) -> dict[str, str]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {key: "" for key in ["n", "min", "q05", "q25", "median", "q75", "q95", "max"]}
    return {
        "n": str(len(clean)),
        "min": fmt(min(clean), 4),
        "q05": fmt(percentile(clean, 0.05), 4),
        "q25": fmt(percentile(clean, 0.25), 4),
        "median": fmt(percentile(clean, 0.50), 4),
        "q75": fmt(percentile(clean, 0.75), 4),
        "q95": fmt(percentile(clean, 0.95), 4),
        "max": fmt(max(clean), 4),
    }


def orientation_proxy(w: float, h: float) -> str:
    if not math.isfinite(w) or not math.isfinite(h) or w <= 0 or h <= 0:
        return "uncertain"
    ratio = max(w, h) / max(1e-6, min(w, h))
    if ratio < 1.25:
        return "square_like"
    return "horizontal_like" if w >= h else "vertical_like"


def image_shape(path_text: str, cache: GrayImageCache) -> tuple[int, int] | None:
    arr = cache.image(path_text)
    if arr is None:
        return None
    return int(arr.shape[1]), int(arr.shape[0])


def boundary_status(box: Mapping[str, float], path_text: str, cache: GrayImageCache, margin_px: float = 8.0) -> tuple[str, float | None]:
    shape = image_shape(path_text, cache)
    if not shape or not box_available(box):
        return "uncertain", None
    width, height = shape
    corners = rotated_corners(box)
    min_margin = min(
        min(x for x, _ in corners),
        min(y for _, y in corners),
        min(width - x for x, _ in corners),
        min(height - y for _, y in corners),
    )
    return ("yes" if min_margin <= margin_px else "no"), float(min_margin)


def scale_thresholds(gt_rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    areas: list[float] = []
    aspects: list[float] = []
    longs: list[float] = []
    shorts: list[float] = []
    for row in gt_rows:
        box = gt_box_from_accounting(row)
        if not box_available(box):
            continue
        w = float(box["w"])
        h = float(box["h"])
        areas.append(w * h)
        aspects.append(max(w, h) / max(1e-6, min(w, h)))
        longs.append(max(w, h))
        shorts.append(min(w, h))
    return {
        "area_q05": percentile(areas, 0.05) or 0.0,
        "area_q95": percentile(areas, 0.95) or float("inf"),
        "aspect_q95": percentile(aspects, 0.95) or float("inf"),
        "long_q05": percentile(longs, 0.05) or 0.0,
        "short_q05": percentile(shorts, 0.05) or 0.0,
    }


def scale_flag(box: Mapping[str, float], near_boundary: str, thresholds: Mapping[str, float]) -> tuple[str, str]:
    if not box_available(box):
        return "uncertain", "GT box unavailable."
    w = float(box["w"])
    h = float(box["h"])
    area = w * h
    aspect = max(w, h) / max(1e-6, min(w, h))
    long_axis = max(w, h)
    short_axis = min(w, h)
    if near_boundary == "yes":
        return "boundary_affected", "GT rotated box is close to image boundary."
    if area <= thresholds["area_q05"] or long_axis <= thresholds["long_q05"] or short_axis <= thresholds["short_q05"]:
        return "too_small", "GT scale is in the lower tail of the 442-row vehicle-scale distribution."
    if area >= thresholds["area_q95"]:
        return "too_large", "GT area is in the upper tail of the 442-row vehicle-scale distribution."
    if aspect >= thresholds["aspect_q95"]:
        return "extreme_aspect", "GT aspect ratio is in the upper tail of the 442-row distribution."
    return "none", "GT scale is inside the fixed diagnostic reference band."


def build_scale_rows(
    gt_rows: Sequence[Mapping[str, Any]],
    cache: GrayImageCache,
    thresholds: Mapping[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in gt_rows:
        box = gt_box_from_accounting(row)
        image_path = str(row.get("sar_pseudocolor_path", ""))
        near_boundary, margin = boundary_status(box, image_path, cache)
        flag, reason = scale_flag(box, near_boundary, thresholds)
        if box_available(box):
            w = float(box["w"])
            h = float(box["h"])
            area = w * h
            aspect = max(w, h) / max(1e-6, min(w, h))
            long_axis = max(w, h)
            short_axis = min(w, h)
        else:
            w = h = area = aspect = long_axis = short_axis = math.nan
        valid = "yes" if flag == "none" and pool_label(row) != "dropout_special" else "no"
        if flag == "uncertain":
            valid = "uncertain"
        rows.append(
            {
                "gt_id": row.get("sar_gt_id", ""),
                "scene": row.get("scene", ""),
                "sar_frame": row.get("sar_frame", ""),
                "pool_type": pool_label(row),
                "gt_box_available": "yes" if box_available(box) else "no",
                "image_available": "yes" if cache.image(image_path) is not None else "no",
                "gt_x": fmt(box.get("cx"), 3),
                "gt_y": fmt(box.get("cy"), 3),
                "gt_w": fmt(w, 3),
                "gt_h": fmt(h, 3),
                "gt_area_px": fmt(area, 3),
                "gt_aspect_ratio": fmt(aspect, 4),
                "gt_long_axis_px": fmt(long_axis, 3),
                "gt_short_axis_px": fmt(short_axis, 3),
                "gt_orientation_proxy": orientation_proxy(w, h),
                "near_image_boundary": near_boundary,
                "valid_for_scale_reference": valid,
                "scale_outlier_flag": flag,
                "scale_outlier_reason": reason,
                "notes": (
                    "Scale statistics are GT-anchored posthoc diagnostics. "
                    f"min_image_margin_px={fmt(margin, 3)}"
                ),
            }
        )
    return rows


def gt_context(
    arr: np.ndarray | None,
    box: Mapping[str, float],
    pad_ratio: float = 0.70,
) -> dict[str, Any] | None:
    if arr is None or not box_available(box):
        return None
    corners = rotated_corners(box)
    pad = max(float(box["w"]), float(box["h"])) * pad_ratio
    x0 = max(0, int(math.floor(min(x for x, _ in corners) - pad)))
    y0 = max(0, int(math.floor(min(y for _, y in corners) - pad)))
    x1 = min(arr.shape[1], int(math.ceil(max(x for x, _ in corners) + pad)))
    y1 = min(arr.shape[0], int(math.ceil(max(y for _, y in corners) + pad)))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = arr[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    cx = float(box["cx"])
    cy = float(box["cy"])
    w = float(box["w"])
    h = float(box["h"])
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    dx = xx + 0.5 - cx
    dy = yy + 0.5 - cy
    local_x = ca * dx + sa * dy
    local_y = -sa * dx + ca * dy
    mask = (np.abs(local_x) <= w / 2.0) & (np.abs(local_y) <= h / 2.0)
    return {
        "crop": (x0, y0, x1, y1),
        "arr": crop,
        "x": xx + 0.5,
        "y": yy + 0.5,
        "local_x": local_x,
        "local_y": local_y,
        "gt_mask": mask,
    }


def energy_center_offset(table: Mapping[str, np.ndarray], box: Mapping[str, float]) -> float | None:
    values = table["values"].astype(np.float64)
    if values.size == 0:
        return None
    weights = values - float(values.min()) + 1.0
    total = float(weights.sum())
    if total <= 0:
        return None
    cx = float((table["x"] * weights).sum() / total)
    cy = float((table["y"] * weights).sum() / total)
    return math.hypot(cx - float(box["cx"]), cy - float(box["cy"]))


def component_axis(points: np.ndarray) -> tuple[float, float]:
    if points.shape[0] <= 1:
        return 1.0, 1.0
    centered = points - points.mean(axis=0, keepdims=True)
    cov = np.cov(centered.T)
    try:
        vals = np.linalg.eigvalsh(cov)
    except np.linalg.LinAlgError:
        vals = np.asarray([0.0, 0.0])
    vals = np.maximum(vals, 0.0)
    long_axis = max(1.0, 4.0 * math.sqrt(float(vals[-1])) if vals.size else 1.0)
    short_axis = max(1.0, 4.0 * math.sqrt(float(vals[0])) if vals.size else 1.0)
    return long_axis, short_axis


def extract_components(
    context: Mapping[str, Any] | None,
    box: Mapping[str, float],
    source_region: str = "gt_inside",
    quantile: float = 0.85,
    min_area: int = 5,
) -> list[dict[str, Any]]:
    if context is None:
        return []
    crop = context["arr"]
    mask = context["gt_mask"]
    values = crop[mask]
    if values.size == 0:
        return []
    threshold = float(np.quantile(values, quantile))
    hot = mask & (crop >= threshold)
    labels, count = ndimage.label(hot, structure=np.ones((3, 3), dtype=np.uint8))
    components: list[dict[str, Any]] = []
    x0, y0, _, _ = context["crop"]
    gt_area = float(box["w"]) * float(box["h"]) if box_available(box) else 0.0
    gt_long = max(float(box["w"]), float(box["h"])) if box_available(box) else 0.0
    gt_short = min(float(box["w"]), float(box["h"])) if box_available(box) else 0.0
    for label in range(1, count + 1):
        comp = labels == label
        area = int(comp.sum())
        if area < min_area:
            continue
        yy, xx = np.nonzero(comp)
        points = np.column_stack([xx.astype(np.float64) + x0 + 0.5, yy.astype(np.float64) + y0 + 0.5])
        long_axis, short_axis = component_axis(points)
        aspect = long_axis / max(short_axis, 1e-6)
        energy = float(crop[comp].sum())
        area_ratio = area / max(gt_area, 1e-6)
        long_ratio = long_axis / max(gt_long, 1e-6)
        short_ratio = short_axis / max(gt_short, 1e-6)
        if area_ratio < 0.015 or (long_ratio < 0.18 and short_ratio < 0.35):
            relative = "too_small_atom"
            hierarchy = "scattering_atom"
            why = "Component is far below GT vehicle scale; it can only be a scattering atom."
        elif area_ratio >= 0.16 and (long_ratio >= 0.45 or short_ratio >= 0.55):
            relative = "vehicle_scale"
            hierarchy = "vehicle_scale_shell_hypothesis"
            why = ""
        elif area_ratio >= 1.25:
            relative = "too_large_context"
            hierarchy = "background_context"
            why = ""
        else:
            relative = "plausible_part"
            hierarchy = "vehicle_part"
            why = "Component is a plausible body part, not a complete vehicle by itself."
        components.append(
            {
                "source_region": source_region,
                "component_area": area,
                "component_long_axis": long_axis,
                "component_short_axis": short_axis,
                "component_aspect_ratio": aspect,
                "component_energy": energy,
                "relative_to_gt_scale": relative,
                "hierarchy_label": hierarchy,
                "why_not_vehicle_if_atom": why,
                "_centroid_x": float(points[:, 0].mean()),
                "_centroid_y": float(points[:, 1].mean()),
            }
        )
    components.sort(key=lambda item: float(item["component_energy"]), reverse=True)
    return components


def separated_atoms(table: Mapping[str, np.ndarray], limit: int = 12, distance_px: float = 12.0) -> list[tuple[float, float, float]]:
    values = table["values"]
    if values.size == 0:
        return []
    threshold = float(np.quantile(values, 0.97))
    candidates = np.nonzero(values >= threshold)[0]
    if candidates.size == 0:
        return []
    order = sorted(candidates.tolist(), key=lambda idx: float(values[idx]), reverse=True)
    selected: list[tuple[float, float, float]] = []
    for idx in order:
        x = float(table["x"][idx])
        y = float(table["y"][idx])
        value = float(values[idx])
        if all(math.hypot(x - sx, y - sy) >= distance_px for sx, sy, _ in selected):
            selected.append((x, y, value))
        if len(selected) >= limit:
            break
    return selected


def edge_continuity(table: Mapping[str, np.ndarray], box: Mapping[str, float]) -> float | None:
    values = table["values"]
    if values.size < 16:
        return None
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(box["w"])
    h = float(box["h"])
    edge = (np.abs(ly) >= 0.35 * h) | (np.abs(lx) >= 0.35 * w)
    if not bool(edge.any()):
        return None
    threshold = float(np.quantile(values, 0.75))
    occupied = 0
    possible = 0
    for axis in (lx, ly):
        axis_vals = axis[edge]
        if axis_vals.size == 0:
            continue
        edges = np.linspace(float(axis_vals.min()), float(axis_vals.max()), 13)
        for lo, hi in zip(edges[:-1], edges[1:]):
            part = edge & (axis >= lo) & (axis < hi)
            if bool(part.any()):
                possible += 1
                occupied += int(float(values[part].max()) >= threshold)
    return occupied / possible if possible else None


def side_means(table: Mapping[str, np.ndarray], box: Mapping[str, float]) -> dict[str, float]:
    values = table["values"]
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(box["w"])
    h = float(box["h"])
    masks = {
        "lower_side": ly >= 0.25 * h,
        "upper_side": ly <= -0.25 * h,
        "left_side": lx <= -0.25 * w,
        "right_side": lx >= 0.25 * w,
        "body_core": (np.abs(lx) < 0.25 * w) & (np.abs(ly) < 0.25 * h),
    }
    return {key: float(values[mask].mean()) if bool(mask.any()) else 0.0 for key, mask in masks.items()}


def quality_label_for(
    scale_row: Mapping[str, Any],
    table: Mapping[str, np.ndarray] | None,
    context: Mapping[str, Any] | None,
    components: Sequence[Mapping[str, Any]],
    energy_mean_q05: float,
) -> tuple[str, str, str, dict[str, Any]]:
    if table is None or context is None:
        return "uncertain", "low", "Image or GT crop unavailable.", {}
    values = table["values"]
    offset = safe_float(scale_row.get("_energy_offset_px"))
    long_axis = safe_float(scale_row.get("gt_long_axis_px"), 0.0) or 0.0
    gt_total = float(values.sum())
    ctx_arr = context["arr"]
    mask = context["gt_mask"]
    outside = ctx_arr[~mask]
    outside_total = float(outside.sum()) if outside.size else 0.0
    inside_peak = float(values.max()) if values.size else 0.0
    outside_peak = float(outside.max()) if outside.size else 0.0
    component_count = len(components)
    mean_energy = float(values.mean()) if values.size else 0.0
    flag = str(scale_row.get("scale_outlier_flag", "none"))
    dominant_inside = inside_peak >= 0.80 * max(outside_peak, 1e-6) or gt_total >= 0.28 * max(gt_total + outside_total, 1e-6)
    aux = {
        "gt_total": gt_total,
        "outside_total": outside_total,
        "dominant_inside": dominant_inside,
        "component_count": component_count,
        "inside_peak": inside_peak,
        "outside_peak": outside_peak,
        "mean_energy": mean_energy,
    }
    if flag == "boundary_affected":
        return "review_boundary", "medium", "GT is close to image boundary; morphology may be incomplete.", aux
    if flag == "too_small":
        return "review_too_small", "medium", "GT scale is in the lower tail; may only box a local scatterer.", aux
    if flag == "too_large":
        return "review_too_large", "medium", "GT scale is in the upper tail; may include background or neighboring structure.", aux
    if flag == "extreme_aspect":
        return "review_extreme_aspect", "medium", "GT aspect ratio is unusually high for this 442-row pool.", aux
    if offset is not None and long_axis > 0 and offset >= 0.32 * long_axis and not dominant_inside:
        return "review_offset", "medium", "Weighted energy center is far from GT center and nearby context is competitive.", aux
    if mean_energy <= energy_mean_q05:
        return "review_low_energy", "low", "GT crop is in the lower tail of display-grayscale energy mean; weak target or edge case.", aux
    if component_count >= 12 and outside_peak >= 1.15 * inside_peak and outside_total >= 2.0 * gt_total:
        return "review_multi_structure", "medium", "Many internal components and competitive nearby context suggest possible multi-structure confusion.", aux
    return "good", "medium", "No fixed GT quality review trigger fired.", aux


def morphology_from_components(
    table: Mapping[str, np.ndarray] | None,
    box: Mapping[str, float],
    components: Sequence[Mapping[str, Any]],
    quality_label: str,
) -> dict[str, Any]:
    if table is None or not box_available(box):
        return {
            "gt_crop_available": "no",
            "dominant_energy_pattern": "uncertain",
            "dominant_side_or_axis_proxy": "uncertain",
            "vehicle_morphology_supported": "uncertain",
            "morphology_strength": "uncertain",
        }
    side = side_means(table, box)
    dominant_side = max(side, key=side.get) if side else "uncertain"
    sorted_side = sorted(side.values(), reverse=True)
    side_contrast = sorted_side[0] / max(sorted_side[1], 1e-6) if len(sorted_side) >= 2 else 1.0
    corner_mask = (np.abs(table["local_x"]) >= 0.28 * float(box["w"])) & (
        np.abs(table["local_y"]) >= 0.28 * float(box["h"])
    )
    corner_ratio = float(table["values"][corner_mask].max() / max(float(table["values"].mean()), 1e-6)) if bool(corner_mask.any()) else 0.0
    continuity = edge_continuity(table, box)
    part_count = sum(1 for comp in components if comp.get("hierarchy_label") in {"vehicle_part", "vehicle_scale_shell_hypothesis"})
    vehicle_scale_count = sum(1 for comp in components if comp.get("hierarchy_label") == "vehicle_scale_shell_hypothesis")
    span_x = 0.0
    span_y = 0.0
    if components:
        xs = [safe_float(comp.get("_centroid_x"), 0.0) or 0.0 for comp in components[:8]]
        ys = [safe_float(comp.get("_centroid_y"), 0.0) or 0.0 for comp in components[:8]]
        span_x = max(xs) - min(xs) if xs else 0.0
        span_y = max(ys) - min(ys) if ys else 0.0
    side_ridge = side_contrast >= 1.12 and dominant_side != "body_core"
    corner = corner_ratio >= 2.0
    discontinuous = (continuity is not None and continuity >= 0.55 and part_count >= 2)
    enclosed = part_count >= 3 and span_x >= 0.45 * float(box["w"]) and span_y >= 0.30 * float(box["h"])
    block = vehicle_scale_count >= 1
    spread = max(span_x, span_y) >= 0.65 * max(float(box["w"]), float(box["h"])) and part_count >= 2
    if enclosed:
        pattern = "enclosed_shell"
    elif side_ridge:
        pattern = "side_ridge"
    elif corner:
        pattern = "corner_hotspot"
    elif discontinuous:
        pattern = "discontinuous_edges"
    elif block:
        pattern = "block_body"
    elif spread:
        pattern = "diffuse_with_core"
    elif (continuity or 0.0) >= 0.35:
        pattern = "weak_boundary"
    else:
        pattern = "uncertain"
    supported = "yes" if pattern in {"enclosed_shell", "side_ridge", "discontinuous_edges", "block_body", "diffuse_with_core"} else "uncertain"
    if quality_label.startswith("review_too_small") or quality_label == "review_offset":
        supported = "uncertain"
    strength = "strong" if pattern in {"enclosed_shell", "side_ridge", "block_body"} and quality_label == "good" else "medium"
    if supported == "uncertain":
        strength = "weak" if pattern == "weak_boundary" else "uncertain"
    return {
        "gt_crop_available": "yes",
        "dominant_energy_pattern": pattern,
        "dominant_side_or_axis_proxy": dominant_side,
        "energy_distribution_description": (
            f"dominant_side={dominant_side};side_contrast={fmt(side_contrast, 4)};"
            f"corner_ratio={fmt(corner_ratio, 4)};edge_continuity={fmt(continuity, 4)};"
            f"component_count={len(components)};part_count={part_count}"
        ),
        "near_or_dominant_side_ridge_proxy": "yes" if side_ridge else "no",
        "corner_or_endpoint_hotspot_proxy": "yes" if corner else "no",
        "far_or_opposite_side_weak_return_proxy": "yes" if side_contrast >= 1.18 else "uncertain",
        "discontinuous_edge_proxy": "yes" if discontinuous else "no",
        "enclosed_shell_proxy": "yes" if enclosed else "no",
        "block_like_body_proxy": "yes" if block else "no",
        "range_spread_with_core_proxy": "yes" if spread else "no",
        "vehicle_morphology_supported": supported,
        "morphology_strength": strength,
    }


def build_quality_and_morphology(
    gt_rows: Sequence[Mapping[str, Any]],
    scale_rows: Sequence[Mapping[str, Any]],
    energy_rows: Sequence[Mapping[str, Any]],
    cache: GrayImageCache,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    energy_means = [safe_float(row.get("gt_energy_mean")) for row in energy_rows]
    energy_mean_q05 = percentile([float(value) for value in energy_means if value is not None], 0.05) or 0.0
    scale_by_key = {gt_key(row["scene"], row["sar_frame"], row["gt_id"]): dict(row) for row in scale_rows}
    quality_rows: list[dict[str, Any]] = []
    morphology_rows: list[dict[str, Any]] = []
    hierarchy_rows: list[dict[str, Any]] = []
    quality_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, row in enumerate(gt_rows, start=1):
        key = gt_key(row.get("scene", ""), row.get("sar_frame", ""), row.get("sar_gt_id", ""))
        scale = dict(scale_by_key.get(key, {}))
        box = gt_box_from_accounting(row)
        image_path = str(row.get("sar_pseudocolor_path", ""))
        arr = cache.image(image_path)
        table = gt_pixel_table(arr, box) if arr is not None else None
        context = gt_context(arr, box)
        offset = energy_center_offset(table, box) if table is not None else None
        scale["_energy_offset_px"] = offset
        components = extract_components(context, box)
        label, confidence, reason, aux = quality_label_for(scale, table, context, components, energy_mean_q05)
        morph = morphology_from_components(table, box, components, label)
        gt_id = str(row.get("sar_gt_id", ""))
        case_id = f"GTREF_{sanitize(row.get('scene'))}_s{sanitize(row.get('sar_frame'))}_{sanitize(gt_id)}"
        if pool_label(row) == "paired_215":
            case_id = f"GTREF_PAIRED_{sanitize(row.get('scene'))}_s{sanitize(row.get('sar_frame'))}_{sanitize(gt_id)}"
        quality = {
            "gt_id": gt_id,
            "scene": row.get("scene", ""),
            "sar_frame": row.get("sar_frame", ""),
            "pool_type": pool_label(row),
            "gt_quality_label": label,
            "gt_quality_confidence": confidence,
            "gt_area_px": scale.get("gt_area_px", ""),
            "gt_energy_inside": fmt(aux.get("gt_total"), 3),
            "gt_energy_nearby_context": fmt(aux.get("outside_total"), 3),
            "energy_center_offset_from_gt_center": fmt(offset, 3),
            "dominant_energy_inside_gt": "yes" if aux.get("dominant_inside") else "no" if aux else "uncertain",
            "vehicle_scale_structure_inside_gt": morph.get("vehicle_morphology_supported", "uncertain"),
            "gt_contains_most_vehicle_structure": "yes"
            if label == "good" and morph.get("vehicle_morphology_supported") == "yes"
            else "uncertain",
            "gt_contains_too_much_background": "yes" if label in {"review_too_large", "review_multi_structure"} else "no",
            "needs_manual_gt_review": "no" if label == "good" else "yes",
            "review_reason": reason,
            "not_allowed_conclusion": "do not revise GT; do not output final box; do not use as selector; posthoc review candidate only",
        }
        quality_rows.append(quality)
        quality_by_key[key] = quality
        confounders = []
        if label == "review_boundary":
            confounders.append("boundary")
        if label in {"review_too_large", "review_multi_structure"}:
            confounders.append("neighbor_vehicle")
            confounders.append("background_clutter")
        if label == "review_low_energy":
            confounders.append("uncertain")
        morphology_rows.append(
            {
                "gt_id": gt_id,
                "case_id": case_id,
                "scene": row.get("scene", ""),
                "sar_frame": row.get("sar_frame", ""),
                "pool_type": pool_label(row),
                "gt_quality_label": label,
                "gt_crop_available": morph.get("gt_crop_available", "no"),
                "dominant_energy_pattern": morph.get("dominant_energy_pattern", "uncertain"),
                "dominant_side_or_axis_proxy": morph.get("dominant_side_or_axis_proxy", "uncertain"),
                "energy_distribution_description": morph.get("energy_distribution_description", ""),
                "near_or_dominant_side_ridge_proxy": morph.get("near_or_dominant_side_ridge_proxy", "uncertain"),
                "corner_or_endpoint_hotspot_proxy": morph.get("corner_or_endpoint_hotspot_proxy", "uncertain"),
                "far_or_opposite_side_weak_return_proxy": morph.get("far_or_opposite_side_weak_return_proxy", "uncertain"),
                "discontinuous_edge_proxy": morph.get("discontinuous_edge_proxy", "uncertain"),
                "enclosed_shell_proxy": morph.get("enclosed_shell_proxy", "uncertain"),
                "block_like_body_proxy": morph.get("block_like_body_proxy", "uncertain"),
                "range_spread_with_core_proxy": morph.get("range_spread_with_core_proxy", "uncertain"),
                "vehicle_morphology_supported": morph.get("vehicle_morphology_supported", "uncertain"),
                "morphology_strength": morph.get("morphology_strength", "uncertain"),
                "confounders": ";".join(confounders) if confounders else "none",
                "posthoc_only": "yes",
                "notes": "GT-anchored morphology is SAR image observation and posthoc hypothesis; not final box or identity truth.",
            }
        )
        shell_component_ids: list[str] = []
        for comp_idx, comp in enumerate(components[:8], start=1):
            cid = f"C{comp_idx:03d}"
            if comp.get("hierarchy_label") in {"vehicle_part", "vehicle_scale_shell_hypothesis"}:
                shell_component_ids.append(cid)
            hierarchy_rows.append(
                {
                    "case_id": case_id,
                    "scene": row.get("scene", ""),
                    "sar_frame": row.get("sar_frame", ""),
                    "component_id": cid,
                    "source_region": comp.get("source_region", "gt_inside"),
                    "component_area": comp.get("component_area", ""),
                    "component_long_axis": fmt(comp.get("component_long_axis"), 3),
                    "component_short_axis": fmt(comp.get("component_short_axis"), 3),
                    "component_aspect_ratio": fmt(comp.get("component_aspect_ratio"), 4),
                    "component_energy": fmt(comp.get("component_energy"), 3),
                    "relative_to_gt_scale": comp.get("relative_to_gt_scale", ""),
                    "hierarchy_label": comp.get("hierarchy_label", ""),
                    "why_not_vehicle_if_atom": comp.get("why_not_vehicle_if_atom", ""),
                    "composition_group_id": f"SHELL_{index:04d}" if comp.get("hierarchy_label") != "scattering_atom" else "",
                    "composition_description": "component participates in GT-scale part composition" if comp.get("hierarchy_label") != "scattering_atom" else "",
                    "posthoc_gt_relation": "inside SAR GT morphology anchor; posthoc only",
                    "notes": "Small components are atoms or parts unless GT-scale composition supports a shell hypothesis.",
                }
            )
        if morph.get("vehicle_morphology_supported") == "yes" and len(shell_component_ids) >= 2:
            hierarchy_rows.append(
                {
                    "case_id": case_id,
                    "scene": row.get("scene", ""),
                    "sar_frame": row.get("sar_frame", ""),
                    "component_id": f"SHELL_{index:04d}",
                    "source_region": "gt_inside",
                    "component_area": sum(int(comp.get("component_area", 0)) for comp in components[:8]),
                    "component_long_axis": fmt(max((safe_float(comp.get("component_long_axis"), 0.0) or 0.0 for comp in components[:8]), default=0.0), 3),
                    "component_short_axis": fmt(max((safe_float(comp.get("component_short_axis"), 0.0) or 0.0 for comp in components[:8]), default=0.0), 3),
                    "component_aspect_ratio": "",
                    "component_energy": fmt(sum(float(comp.get("component_energy", 0.0)) for comp in components[:8]), 3),
                    "relative_to_gt_scale": "vehicle_scale",
                    "hierarchy_label": "vehicle_scale_shell_hypothesis",
                    "why_not_vehicle_if_atom": "",
                    "composition_group_id": f"SHELL_{index:04d}",
                    "composition_description": "multiple atom/part components form a GT-scale shell/body hypothesis",
                    "posthoc_gt_relation": "GT-scale composition hypothesis; not final annotation",
                    "notes": "Vehicle-scale shell hypothesis requires multiple parts at GT scale and remains posthoc.",
                }
            )
    return quality_rows, morphology_rows, hierarchy_rows, quality_by_key


def build_support_miss_rows(
    coverage_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    quality_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
    morphology_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failure_by_case = {str(row.get("case_id", "")): row for row in failure_rows}
    corr_by_case = {case_id_from_corr(row): row for row in corr_rows}
    rows: list[dict[str, Any]] = []
    for row in coverage_rows:
        case_id = str(row.get("case_id", ""))
        corr = corr_by_case.get(case_id, {})
        key = gt_key(row.get("scene", ""), row.get("sar_frame", ""), corr.get("sar_gt_id", ""))
        quality = quality_by_key.get(key, {})
        morph = morphology_by_key.get(key, {})
        area = safe_float(row.get("gt_area_coverage_ratio"))
        energy = safe_float(row.get("gt_energy_coverage_ratio"))
        morphology = safe_float(row.get("morphology_primitive_coverage_proxy"))
        support_available_text = "yes" if row.get("support_boundary_available") == "yes" else "no"
        gt_anchor_usable = quality.get("gt_quality_label") in {"good", "review_low_energy", "review_extreme_aspect"}
        gt_morph = str(morph.get("vehicle_morphology_supported", "uncertain"))
        low_support = any(value is not None and value < 0.80 for value in [energy, morphology])
        if low_support and gt_anchor_usable and gt_morph == "yes":
            support_miss = "yes"
            outside = "yes"
            inside = "no"
        elif low_support:
            support_miss = "uncertain"
            outside = "uncertain"
            inside = "uncertain"
        else:
            support_miss = "no"
            outside = "no"
            inside = "yes"
        base_failure = str(failure_by_case.get(case_id, {}).get("support_failure_type", "none"))
        if support_miss == "yes":
            if area is not None and area < 0.50 and energy is not None and energy < 0.50:
                failure_type = "support_miss"
            elif area is not None and energy is not None and abs(area - energy) > 0.15:
                failure_type = "range_misaligned"
            elif morphology is not None and morphology < 0.80:
                failure_type = "too_narrow"
            else:
                failure_type = "reconstruction_uncertain"
        elif support_miss == "uncertain":
            failure_type = "reconstruction_uncertain" if base_failure == "support_ok_but_not_exclusive" else base_failure
        else:
            failure_type = "none" if base_failure == "support_ok_but_not_exclusive" else base_failure
        rows.append(
            {
                "case_id": case_id,
                "scene": row.get("scene", ""),
                "sar_frame": row.get("sar_frame", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "optical_state": row.get("optical_state", ""),
                "support_available": support_available_text,
                "gt_quality_label": quality.get("gt_quality_label", "uncertain"),
                "gt_vehicle_morphology_supported": gt_morph,
                "support_gt_area_coverage": row.get("gt_area_coverage_ratio", ""),
                "support_gt_energy_coverage": row.get("gt_energy_coverage_ratio", ""),
                "support_morphology_coverage": row.get("morphology_primitive_coverage_proxy", ""),
                "vehicle_scale_morphology_inside_support": inside,
                "main_gt_structure_outside_support": outside,
                "support_miss_vehicle_structure": support_miss,
                "support_failure_type": failure_type,
                "if_support_miss_do_not_search_inside_support": "yes" if support_miss == "yes" else "no",
                "recommended_next_action": (
                    "review support construction / range-azimuth mapping / motion-drift compatibility; do not search only inside support"
                    if support_miss == "yes"
                    else "preserve layer separation; support quality is not association success"
                ),
                "not_allowed_conclusion": "not final box; not annotation proposal; not selector success; not GT-guided runtime prediction logic",
            }
        )
    return rows


def review_template(category: str) -> tuple[str, str]:
    options = (
        "GT good;GT too small;GT too large;GT offset;GT boundary affected;"
        "weak but structured;multi-structure;support miss;support reconstruction uncertain"
    )
    look = {
        "possible_gt_too_small": "看 GT 是否只框到局部亮点，是否漏掉车辆尺度的条带/边界/角点组合。",
        "possible_gt_too_large": "看 GT 是否包含过多背景、邻车或路边结构。",
        "possible_gt_offset": "看能量主体是否偏在 GT 外或明显靠一侧。",
        "possible_gt_boundary_affected": "看目标是否靠近 SAR 图像边界，车体结构是否不完整。",
        "possible_extreme_aspect": "看长宽比是否合理，是否只框了一条边或过度拉长。",
        "weak_but_structured_gt": "看弱能量中是否仍有车辆尺度条带、角点或边界结构。",
        "multi_structure_inside_gt": "看 GT 内是否包含多车/邻近结构而非单车。",
        "support_miss_but_gt_good": "看 GT 内车辆尺度结构是否清楚，同时 support 是否错过主结构。",
        "support_miss_and_gt_uncertain": "同时看 GT 质量和 support miss，先不要下强结论。",
        "good_gt_scale_anchor": "确认这是可作为车辆尺度参考的好 GT anchor。",
    }.get(category, "检查 GT 质量、车辆尺度结构和 support 关系。")
    return look, options


def add_review(
    rows: list[dict[str, Any]],
    category: str,
    source: Mapping[str, Any],
    why: str,
    seq: int,
) -> int:
    look, options = review_template(category)
    rows.append(
        {
            "review_id": f"R{seq:04d}",
            "gt_id": source.get("gt_id", ""),
            "case_id": source.get("case_id", ""),
            "scene": source.get("scene", ""),
            "sar_frame": source.get("sar_frame", ""),
            "category": category,
            "why_selected": why,
            "what_to_look_for": look,
            "possible_decision_options": options,
            "image_panel_path": "",
            "notes": (
                "本图目的：检查 GT 框是否合理，以及 GT 内能量结构是否达到车辆尺度。"
                "不能记录 revised annotation、final box、identity truth、selector success。"
            ),
        }
    )
    return seq + 1


def build_review_candidates(
    quality_rows: Sequence[Mapping[str, Any]],
    morphology_rows: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    morph_by_key = {gt_key(row.get("scene", ""), row.get("sar_frame", ""), row.get("gt_id", "")): row for row in morphology_rows}
    rows: list[dict[str, Any]] = []
    seq = 1
    label_to_category = {
        "review_too_small": "possible_gt_too_small",
        "review_too_large": "possible_gt_too_large",
        "review_offset": "possible_gt_offset",
        "review_boundary": "possible_gt_boundary_affected",
        "review_extreme_aspect": "possible_extreme_aspect",
        "review_low_energy": "weak_but_structured_gt",
        "review_multi_structure": "multi_structure_inside_gt",
    }
    for label, category in label_to_category.items():
        candidates = [row for row in quality_rows if row.get("gt_quality_label") == label]
        candidates = sorted(candidates, key=lambda item: str(item.get("gt_id", "")))[:4]
        for cand in candidates:
            m = morph_by_key.get(gt_key(cand.get("scene", ""), cand.get("sar_frame", ""), cand.get("gt_id", "")), {})
            merged = dict(cand)
            merged["case_id"] = m.get("case_id", "")
            seq = add_review(rows, category, merged, str(cand.get("review_reason", "")), seq)
    support_good = [
        row
        for row in support_rows
        if row.get("support_miss_vehicle_structure") == "yes" and row.get("gt_quality_label") == "good"
    ]
    for row in sorted(support_good, key=lambda item: safe_float(item.get("support_morphology_coverage"), 1.0) or 1.0)[:6]:
        seq = add_review(rows, "support_miss_but_gt_good", row, "GT appears usable but support misses vehicle-scale morphology.", seq)
    support_uncertain = [
        row
        for row in support_rows
        if row.get("support_miss_vehicle_structure") in {"yes", "uncertain"} and row.get("gt_quality_label") != "good"
    ]
    for row in sorted(support_uncertain, key=lambda item: safe_float(item.get("support_morphology_coverage"), 1.0) or 1.0)[:6]:
        seq = add_review(rows, "support_miss_and_gt_uncertain", row, "Support miss overlaps with GT quality uncertainty.", seq)
    good = [
        row
        for row in morphology_rows
        if row.get("gt_quality_label") == "good"
        and row.get("vehicle_morphology_supported") == "yes"
        and row.get("morphology_strength") == "strong"
    ]
    for row in sorted(good, key=lambda item: (str(item.get("scene", "")), str(item.get("sar_frame", ""))))[:6]:
        seq = add_review(rows, "good_gt_scale_anchor", row, "Good GT-scale morphology anchor for calibration/reference.", seq)
    seen_categories = {row["category"] for row in rows}
    for category in [
        "possible_gt_too_small",
        "possible_gt_too_large",
        "possible_gt_offset",
        "possible_gt_boundary_affected",
        "possible_extreme_aspect",
        "weak_but_structured_gt",
        "multi_structure_inside_gt",
        "support_miss_but_gt_good",
        "support_miss_and_gt_uncertain",
        "good_gt_scale_anchor",
    ]:
        if category not in seen_categories:
            fallback = {"gt_id": "", "case_id": "", "scene": "", "sar_frame": ""}
            seq = add_review(rows, category, fallback, "No fixed-rule positive candidate; included as an empty review category placeholder.", seq)
    return rows


def lookup_gt_row(gt_rows: Sequence[Mapping[str, Any]], scene: str, sar_frame: str, gt_id: str) -> Mapping[str, Any] | None:
    for row in gt_rows:
        if str(row.get("scene", "")) == str(scene) and str(row.get("sar_frame", "")) == str(sar_frame) and str(row.get("sar_gt_id", "")) == str(gt_id):
            return row
    return None


def first_support_for_case(support_rows: Sequence[Mapping[str, Any]], case_id: str) -> Mapping[str, Any] | None:
    for row in support_rows:
        row_case_id = str(row.get("case_id", "")) or case_id_from_support(row)
        if row_case_id == str(case_id):
            return row
    return None


def draw_crop_axis(ax: Any, arr: np.ndarray | None, crop: tuple[int, int, int, int], title: str) -> None:
    ax.set_title(title, fontproperties=FONT, fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
    if arr is None:
        ax.text(0.5, 0.5, "图像不可用", ha="center", va="center", fontproperties=FONT)
        return
    x0, y0, x1, y1 = crop
    ax.imshow(arr[y0:y1, x0:x1], cmap="gray", vmin=0, vmax=255)


def to_local(points: Sequence[tuple[float, float]], crop: tuple[int, int, int, int]) -> list[tuple[float, float]]:
    x0, y0, _, _ = crop
    return [(float(x) - x0, float(y) - y0) for x, y in points]


def render_case_panel(
    idx: int,
    candidate: Mapping[str, Any],
    gt_rows: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    cache: GrayImageCache,
    output_path: Path,
) -> bool:
    gt_row = lookup_gt_row(gt_rows, str(candidate.get("scene", "")), str(candidate.get("sar_frame", "")), str(candidate.get("gt_id", "")))
    if gt_row is None:
        return False
    box = gt_box_from_accounting(gt_row)
    image_path = str(gt_row.get("sar_pseudocolor_path", ""))
    arr = cache.image(image_path)
    if arr is None or not box_available(box):
        return False
    support = first_support_for_case(support_rows, str(candidate.get("case_id", "")))
    crop = crop_box_for(type("ImageShim", (), {"size": (arr.shape[1], arr.shape[0])})(), box, support)
    gt_local = to_local(rotated_corners(box), crop)
    support_local = [to_local(line, crop) for line in support_boundary_points(support)] if support and support_available(support) else []
    table = gt_pixel_table(arr, box)
    atoms = separated_atoms(table, limit=10) if table is not None else []
    atom_local = [(x - crop[0], y - crop[1]) for x, y, _ in atoms]

    fig = plt.figure(figsize=(15.5, 8.8), dpi=140, constrained_layout=True)
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 1.15])
    fig.suptitle(f"{idx}. GT quality / vehicle-scale morphology | {candidate.get('category', '')}", fontproperties=FONT, fontsize=13)
    ax_gt = fig.add_subplot(gs[0, 0])
    draw_crop_axis(ax_gt, arr, crop, "SAR crop + GT 框")
    ax_gt.add_patch(Polygon(gt_local, closed=True, fill=False, edgecolor="#ffd400", linewidth=2.0))
    ax_support = fig.add_subplot(gs[0, 1])
    draw_crop_axis(ax_support, arr, crop, "GT + support boundary")
    ax_support.add_patch(Polygon(gt_local, closed=True, fill=False, edgecolor="#ffd400", linewidth=2.0))
    if support_local:
        closed = support_closed_polygon(support_local)
        if closed:
            ax_support.add_patch(Polygon(closed, closed=True, fill=True, facecolor="#ff00cc", alpha=0.10, edgecolor="none"))
        for line in support_local:
            if line:
                xs, ys = zip(*line)
                ax_support.plot(xs, ys, color="#ff00cc", linewidth=1.5)
    ax_atoms = fig.add_subplot(gs[1, 0])
    draw_crop_axis(ax_atoms, arr, crop, "GT 内高能 atom / part 提示")
    ax_atoms.add_patch(Polygon(gt_local, closed=True, fill=False, edgecolor="#ffd400", linewidth=2.0))
    if atom_local:
        xs, ys = zip(*atom_local)
        ax_atoms.scatter(xs, ys, s=28, facecolors="none", edgecolors="#ff5a00", linewidths=1.3)
    ax_context = fig.add_subplot(gs[1, 1])
    draw_crop_axis(ax_context, arr, crop, "context crop")
    ax_context.add_patch(Polygon(gt_local, closed=True, fill=False, edgecolor="#ffd400", linewidth=2.0))
    ax_text = fig.add_subplot(gs[:, 2])
    ax_text.set_axis_off()
    text_lines = [
        "本图目的：检查 GT 框是否合理，以及 GT 内能量结构是否达到车辆尺度。",
        "请重点看：GT 是否过小/过大/偏移，GT 内是否存在车体外壳/边界/条带/角点结构，小组件是否只是散射 atom。",
        "若 GT 主体结构不在 support 内，应记录 support miss，而不是继续只在 support 内找车。",
        "不能记录：revised annotation、final box、identity truth、selector success。",
        "可以记录：GT 质量疑点、车辆尺度结构、atom/part/shell 分层、support failure type。",
        f"case_id: {candidate.get('case_id', '')}",
        f"gt_id: {candidate.get('gt_id', '')}; scene={candidate.get('scene', '')}; sar={candidate.get('sar_frame', '')}",
        f"why: {candidate.get('why_selected', '')}",
        f"look: {candidate.get('what_to_look_for', '')}",
    ]
    ax_text.text(
        0,
        1,
        "\n\n".join(wrap_zh(line, 32) for line in text_lines),
        va="top",
        fontproperties=FONT,
        fontsize=8.3,
        linespacing=1.18,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)
    return True


def render_atlas(
    timestamp: str,
    review_rows: list[dict[str, Any]],
    gt_rows: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    cache: GrayImageCache,
    max_panels: int = 18,
) -> tuple[str, int]:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    html_cards: list[str] = []
    rendered = 0
    for idx, row in enumerate(review_rows[:max_panels], start=1):
        case_part = sanitize(row.get("case_id") or f"GT_{row.get('scene')}_{row.get('sar_frame')}_{row.get('gt_id')}")
        panel_path = VISUAL_DIR / f"{idx:02d}_{case_part}_gt_quality_vehicle_scale_cn.png"
        ok = render_case_panel(idx, row, gt_rows, support_rows, cache, panel_path)
        if ok:
            rendered += 1
            row["image_panel_path"] = str(panel_path)
            img_html = f'<img src="{html.escape(panel_path.name)}" alt="{html.escape(case_part)}" />'
        else:
            img_html = "<p><strong>panel unavailable</strong></p>"
        html_cards.append(
            "<article>"
            f"<h2>{idx}. {html.escape(str(row.get('category', '')))}</h2>"
            f"<p><code>{html.escape(str(row.get('case_id') or row.get('gt_id', '')))}</code></p>"
            f"{img_html}"
            f"<p><strong>为什么选：</strong>{html.escape(str(row.get('why_selected', '')))}</p>"
            f"<p><strong>看什么：</strong>{html.escape(str(row.get('what_to_look_for', '')))}</p>"
            "<p><strong>边界：</strong>不能记录 revised annotation、final box、identity truth、selector success。</p>"
            "</article>"
        )
    atlas_path = VISUAL_DIR / f"oty2_gt_quality_vehicle_scale_morphology_atlas_cn_{timestamp}.html"
    atlas_html = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'/>"
        "<title>OTY2 GT quality vehicle-scale morphology atlas</title>"
        "<style>body{font-family:'Microsoft YaHei',Arial,sans-serif;background:#f5f5f5;color:#111;margin:24px;}"
        "article{background:#fff;border:1px solid #bbb;margin:0 0 24px;padding:16px;border-radius:4px;}"
        "img{max-width:100%;height:auto;border:1px solid #555;display:block;}code{font-size:12px;color:#064f8a;}</style>"
        "</head><body>"
        "<h1>OTY2 GT quality / vehicle-scale SAR morphology atlas</h1>"
        "<p>本 atlas 检查 GT 框是否合理，以及 GT 内能量结构是否达到车辆尺度。若 GT 主体结构不在 support 内，应记录 support miss，而不是继续只在 support 内找车。"
        "本 atlas 不输出 revised annotation、final box、identity truth 或 selector success。</p>"
        + "\n".join(html_cards)
        + "</body></html>"
    )
    atlas_path.write_text(atlas_html, encoding="utf-8")
    return str(atlas_path), rendered


def summarize_scale(scale_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metrics = {}
    for field in ["gt_w", "gt_h", "gt_area_px", "gt_aspect_ratio", "gt_long_axis_px", "gt_short_axis_px"]:
        values = [safe_float(row.get(field)) for row in scale_rows]
        metrics[field] = metric_summary([float(value) for value in values if value is not None])
    by_scene: dict[str, dict[str, Any]] = {}
    for scene, rows in groupby(scale_rows, "scene").items():
        areas = [safe_float(row.get("gt_area_px")) for row in rows]
        by_scene[scene] = {
            "count": len(rows),
            "area": metric_summary([float(value) for value in areas if value is not None]),
            "scale_outlier_mix": compact_counts(row.get("scale_outlier_flag", "") for row in rows),
        }
    by_pool: dict[str, dict[str, Any]] = {}
    for pool, rows in groupby(scale_rows, "pool_type").items():
        by_pool[pool] = {
            "count": len(rows),
            "scale_outlier_mix": compact_counts(row.get("scale_outlier_flag", "") for row in rows),
            "valid_scale_reference_count": sum(1 for row in rows if row.get("valid_for_scale_reference") == "yes"),
        }
    return {"overall": metrics, "by_scene": by_scene, "by_pool_type": by_pool}


def groupby(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row.get(field, ""))].append(row)
    return dict(result)


def build_summary(
    timestamp: str,
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
    scale_rows: Sequence[Mapping[str, Any]],
    quality_rows: Sequence[Mapping[str, Any]],
    morphology_rows: Sequence[Mapping[str, Any]],
    hierarchy_rows: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    review_rows: Sequence[Mapping[str, Any]],
    atlas_path: str,
    atlas_panels: int,
) -> dict[str, Any]:
    quality_review = [row for row in quality_rows if row.get("needs_manual_gt_review") == "yes"]
    support_miss_yes = [row for row in support_rows if row.get("support_miss_vehicle_structure") == "yes"]
    support_miss_uncertain = [row for row in support_rows if row.get("support_miss_vehicle_structure") == "uncertain"]
    good_scale = [row for row in scale_rows if row.get("valid_for_scale_reference") == "yes"]
    shell_rows = [row for row in hierarchy_rows if row.get("hierarchy_label") == "vehicle_scale_shell_hypothesis"]
    def split_count(values: Sequence[Any]) -> str:
        counter: Counter[str] = Counter()
        for value in values:
            for part in str(value or "").split(";"):
                text = part.strip()
                if text:
                    counter[text] += 1
        return ";".join(f"{key}={count}" for key, count in counter.most_common(10))

    key_metrics = {
        "gt_total": len(scale_rows),
        "gt_image_available": sum(1 for row in scale_rows if row.get("image_available") == "yes"),
        "gt_box_available": sum(1 for row in scale_rows if row.get("gt_box_available") == "yes"),
        "valid_vehicle_scale_reference_count": len(good_scale),
        "scale_outlier_mix": compact_counts(row.get("scale_outlier_flag", "") for row in scale_rows),
        "gt_quality_label_mix": compact_counts(row.get("gt_quality_label", "") for row in quality_rows),
        "manual_gt_review_candidate_count": len(quality_review),
        "dominant_energy_pattern_mix": compact_counts(row.get("dominant_energy_pattern", "") for row in morphology_rows),
        "vehicle_morphology_supported_mix": compact_counts(row.get("vehicle_morphology_supported", "") for row in morphology_rows),
        "hierarchy_label_mix": compact_counts(row.get("hierarchy_label", "") for row in hierarchy_rows),
        "vehicle_scale_shell_hypothesis_rows": len(shell_rows),
        "support_miss_vehicle_structure_yes": len(support_miss_yes),
        "support_miss_vehicle_structure_uncertain": len(support_miss_uncertain),
        "support_failure_type_mix": split_count([row.get("support_failure_type", "") for row in support_rows]),
        "review_candidate_rows": len(review_rows),
        "atlas_panels_generated": atlas_panels,
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "all_sar_gt_reference_pool": 442,
            "paired_optical_object_sar_gt": 215,
            "gm011_blocked_missing_object_stream": 195,
            "sar_only_gt": 20,
            "dropout_no_oty_iou_match_temporal_continuation": 12,
        },
        "row_counts": {
            "sar_gt_vehicle_scale_statistics": len(scale_rows),
            "sar_gt_quality_audit": len(quality_rows),
            "gt_anchored_energy_morphology": len(morphology_rows),
            "atom_part_shell_hierarchy": len(hierarchy_rows),
            "gt_support_miss_failure_cases": len(support_rows),
            "gt_quality_visual_review_candidates": len(review_rows),
        },
        "scale_statistics": summarize_scale(scale_rows),
        "key_metrics": key_metrics,
        "posthoc_hypotheses_only": [
            "GT quality audit flags review candidates; it does not revise GT.",
            "GT-anchored energy morphology is SAR image observation and posthoc hypothesis.",
            "vehicle_scale_shell_hypothesis is not an annotation rule or final box.",
            "support miss is a support construction diagnostic, not runtime logic.",
            "SAR-only and GM_RM011 rows are reference-only and not paired correspondence.",
        ],
        "corrected_or_paused_old_conclusions": [
            "Support-wide vehicle search is paused when GT-anchored vehicle-scale morphology is outside support.",
            "Small support-internal components cannot be called cars or vehicle shells.",
            "Support coverage high/low is separate from optical-SAR association success.",
            "GT quality uncertainty weakens morphology and coverage conclusions until manual review.",
        ],
        "next_step": "motion/drift compatibility and GM_RM019 optical continuity review are more useful than more static support-internal tables; stage recap is also reasonable after this handoff.",
        "boundary_flags": BOUNDARY_FLAGS,
        "visual_atlas_path": atlas_path,
        "sources": sources,
        "outputs": outputs,
    }


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    km = summary["key_metrics"]
    scale = summary["scale_statistics"]
    lines = [
        "# OTY2 GT-Anchored Vehicle-Scale SAR Morphology And GT Quality Audit Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report anchors SAR morphology to SAR GT vehicle scale and audits GT quality before interpreting support-wide structures. It is posthoc mechanism diagnosis only: no revised GT, final box, annotation proposal, selector/ranking, training, threshold tuning, or identity truth is produced.",
        "",
        "## Ledger Boundary",
        "",
        "- 442 = all SAR GT / SAR-side target reference pool",
        "- 215 = current OTY optical-object to SAR-GT frame-level paired pool",
        "- 195 = GM_RM011 blocked_missing_object_stream, not unannotated",
        "- 20 = SAR-only GT, SAR morphology reference only",
        "- 12 = dropout/no_oty_iou_match/temporal continuation special pool",
        "",
        "## 442 SAR GT Scale Statistics",
        "",
        f"- gt_total: `{km['gt_total']}`",
        f"- gt_image_available: `{km['gt_image_available']}`",
        f"- gt_box_available: `{km['gt_box_available']}`",
        f"- valid_vehicle_scale_reference_count: `{km['valid_vehicle_scale_reference_count']}`",
        f"- scale_outlier_mix: `{km['scale_outlier_mix']}`",
        f"- width distribution: `{json.dumps(scale['overall']['gt_w'], ensure_ascii=False)}`",
        f"- height distribution: `{json.dumps(scale['overall']['gt_h'], ensure_ascii=False)}`",
        f"- area distribution: `{json.dumps(scale['overall']['gt_area_px'], ensure_ascii=False)}`",
        f"- aspect distribution: `{json.dumps(scale['overall']['gt_aspect_ratio'], ensure_ascii=False)}`",
        "",
        "### By Scene",
        "",
    ]
    for scene, values in scale["by_scene"].items():
        lines.append(f"- {scene}: count=`{values['count']}`, area=`{json.dumps(values['area'], ensure_ascii=False)}`, scale_outlier_mix=`{values['scale_outlier_mix']}`")
    lines.extend(["", "### By Pool Type", ""])
    for pool, values in scale["by_pool_type"].items():
        lines.append(f"- {pool}: count=`{values['count']}`, valid_scale_reference_count=`{values['valid_scale_reference_count']}`, scale_outlier_mix=`{values['scale_outlier_mix']}`")
    lines.extend(
        [
            "",
            "## GT Quality Audit",
            "",
            f"- gt_quality_label_mix: `{km['gt_quality_label_mix']}`",
            f"- manual_gt_review_candidate_count: `{km['manual_gt_review_candidate_count']}`",
            "",
            "The GT quality audit only finds review candidates. It does not modify GT, does not output revised boxes, and does not become a selector.",
            "",
            "## GT-Anchored Morphology",
            "",
            f"- dominant_energy_pattern_mix: `{km['dominant_energy_pattern_mix']}`",
            f"- vehicle_morphology_supported_mix: `{km['vehicle_morphology_supported_mix']}`",
            "",
            "GT-anchored morphology uses SAR image observations inside the GT crop to describe side ridges, corner hotspots, discontinuous edges, enclosed shell hypotheses, block-like body hypotheses, weak boundaries, and uncertain cases.",
            "",
            "## Atom / Part / Shell Hierarchy",
            "",
            f"- hierarchy_label_mix: `{km['hierarchy_label_mix']}`",
            f"- vehicle_scale_shell_hypothesis_rows: `{km['vehicle_scale_shell_hypothesis_rows']}`",
            "",
            "This hierarchy prevents the baby-car error: small bright components are `scattering_atom` or `vehicle_part`; only a GT-scale composition of multiple parts can be named `vehicle_scale_shell_hypothesis`, and even that remains a posthoc hypothesis.",
            "",
            "## GT-Support Miss Failure Cases",
            "",
            f"- support_miss_vehicle_structure_yes: `{km['support_miss_vehicle_structure_yes']}`",
            f"- support_miss_vehicle_structure_uncertain: `{km['support_miss_vehicle_structure_uncertain']}`",
            f"- support_failure_type_mix: `{km['support_failure_type_mix']}`",
            "",
            "**If GT-anchored vehicle-scale morphology is outside support, the correct diagnostic is support construction failure, not support-internal vehicle search.**",
            "",
            "Support failure and GT quality issue are separated: GT quality asks whether the SAR GT box is a reliable morphology anchor; support failure asks whether optical-derived support covers the GT-anchored vehicle-scale structure.",
            "",
            "## GT Quality Visual Review Candidates",
            "",
            f"- review_candidate_rows: `{km['review_candidate_rows']}`",
            f"- atlas_panels_generated: `{km['atlas_panels_generated']}`",
            f"- atlas: `{summary['visual_atlas_path']}`",
            "",
            "Review categories include possible GT too small, too large, offset, boundary affected, extreme aspect, weak but structured GT, multi-structure inside GT, support miss but GT good, support miss and GT uncertain, and good GT scale anchors.",
            "",
            "## Why This Corrects The Support-Internal / Baby-Car Error",
            "",
            "1. If the GT-anchored vehicle-scale body is outside support, support is wrong for that case; a tiny structure inside support cannot rescue it.",
            "2. A small component is only a scattering atom or vehicle part. It cannot be called a vehicle shell by itself.",
            "3. GT width, height, area, and long/short axes provide the vehicle-scale reference that prevents baby-car interpretations.",
            "4. The hierarchy separates scattering atom, vehicle part, and vehicle-scale shell hypothesis.",
            "5. GT quality issue and support failure must remain separate because a bad GT anchor and a bad support construction imply different next actions.",
            "6. This run outputs no revised annotation, no final box, no selector, and no GT-guided prediction logic.",
            "7. Manual review is still needed for GT quality flags, low-energy structured cases, multi-structure GT, and support-miss cases.",
            "8. The next useful step is motion/drift compatibility and GM_RM019 optical continuity review, not another static support-internal metric table.",
            "",
            "## Required Answers",
            "",
            "1. The 442 GT scale distribution is reported above for width, height, area, aspect ratio, long axis, and short axis, with scene and pool splits.",
            f"2. Potential GT issues are summarized by `gt_quality_label_mix={km['gt_quality_label_mix']}` and review candidates in the CSV.",
            f"3. Vehicle-scale reference count: `{km['valid_vehicle_scale_reference_count']}`.",
            f"4. Main GT morphology patterns: `{km['dominant_energy_pattern_mix']}`.",
            "5. The atom/part/shell hierarchy prevents baby-car promotion by blocking tiny components from being called vehicle shells.",
            f"6. Support miss yes cases: `{km['support_miss_vehicle_structure_yes']}`; uncertain cases: `{km['support_miss_vehicle_structure_uncertain']}`.",
            "7. Rows with `support_miss_vehicle_structure=yes` are cases where GT body structure is outside support and support-internal search must stop.",
            "8. GT quality issue is a GT anchor problem; support issue is an optical-derived feasible-region problem.",
            f"9. Manual GT review candidates: `{km['manual_gt_review_candidate_count']}` quality rows plus categorized visual review CSV rows.",
            "10. GT quality labels, morphology patterns, shell hypotheses, support miss, and atlas notes are all posthoc hypotheses.",
            f"11. Next step: {summary['next_step']}",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Sources", ""])
    for key, value in summary["sources"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any], phase: str) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKSPACE_LOG_DIR / f"oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit",
        f"phase={phase}",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "archive_directory_active_source=false",
        "repo_outputs_written=true",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "gt_accounting_csv": Path(args.gt_accounting_csv) if args.gt_accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "gt_energy_csv": Path(args.gt_energy_csv) if args.gt_energy_csv else latest_path("oty2_gt_box_energy_distribution_audit_*.csv"),
        "support_coverage_csv": Path(args.support_coverage_csv) if args.support_coverage_csv else latest_path("oty2_optical_support_coverage_hypothesis_audit_*.csv"),
        "support_peak_competition_csv": Path(args.support_peak_competition_csv) if args.support_peak_competition_csv else latest_path("oty2_support_region_peak_competition_audit_*.csv"),
        "support_wide_atoms_csv": Path(args.support_wide_atoms_csv) if args.support_wide_atoms_csv else latest_path("oty2_support_wide_energy_atoms_and_components_*.csv"),
        "support_wide_shell_csv": Path(args.support_wide_shell_csv) if args.support_wide_shell_csv else latest_path("oty2_support_wide_vehicle_shell_proxy_*.csv"),
        "support_failure_csv": Path(args.support_failure_csv) if args.support_failure_csv else latest_path("oty2_support_failure_taxonomy_*.csv"),
    }
    gt_rows = read_csv(paths["gt_accounting_csv"])
    if len(gt_rows) != 442:
        raise RuntimeError(f"Expected 442 GT accounting rows; got {len(gt_rows)}")
    pool_counts = Counter(pool_label(row) for row in gt_rows)
    expected = {"paired_215": 215, "gm011_waiting_object_stream": 195, "sar_only": 20, "dropout_special": 12}
    for key, value in expected.items():
        if pool_counts.get(key, 0) != value:
            raise RuntimeError(f"Ledger mismatch for {key}: expected {value}, got {pool_counts.get(key, 0)}")
    coverage_rows = read_csv(paths["support_coverage_csv"])
    if len(coverage_rows) != 215:
        raise RuntimeError(f"Expected 215 support coverage rows; got {len(coverage_rows)}")
    peak_rows = read_csv(paths["support_peak_competition_csv"])
    state_rows = [
        row
        for row in peak_rows
        if row.get("mode_name") == STATE_MODE and row.get("sample_pool") == "paired_optical_object_sar_gt"
    ]
    if len(state_rows) != 215:
        raise RuntimeError(f"Expected 215 paired {STATE_MODE} support rows; got {len(state_rows)}")
    return {
        "paths": paths,
        "gt_rows": gt_rows,
        "corr_rows": read_csv(paths["correspondence_csv"]),
        "gt_energy_rows": read_csv(paths["gt_energy_csv"]),
        "coverage_rows": coverage_rows,
        "state_support_rows": state_rows,
        "support_wide_atoms_rows": read_csv(paths["support_wide_atoms_csv"]),
        "support_wide_shell_rows": read_csv(paths["support_wide_shell_csv"]),
        "support_failure_rows": read_csv(paths["support_failure_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    cache = GrayImageCache(max_images=args.image_cache_size)
    inputs = load_inputs(args)
    sources = {key: str(value) for key, value in inputs["paths"].items()}
    thresholds = scale_thresholds(inputs["gt_rows"])
    scale_rows = build_scale_rows(inputs["gt_rows"], cache, thresholds)
    quality_rows, morphology_rows, hierarchy_rows, quality_by_key = build_quality_and_morphology(
        inputs["gt_rows"], scale_rows, inputs["gt_energy_rows"], cache
    )
    morphology_by_key = {gt_key(row.get("scene", ""), row.get("sar_frame", ""), row.get("gt_id", "")): row for row in morphology_rows}
    support_miss_rows = build_support_miss_rows(
        inputs["coverage_rows"],
        inputs["support_failure_rows"],
        inputs["corr_rows"],
        quality_by_key,
        morphology_by_key,
    )
    review_rows = build_review_candidates(quality_rows, morphology_rows, support_miss_rows)
    atlas_path, atlas_panels = render_atlas(timestamp, review_rows, inputs["gt_rows"], inputs["state_support_rows"], cache)

    scale_csv = REPORT_DIR / f"oty2_sar_gt_vehicle_scale_statistics_{timestamp}.csv"
    quality_csv = REPORT_DIR / f"oty2_sar_gt_quality_audit_{timestamp}.csv"
    morphology_csv = REPORT_DIR / f"oty2_gt_anchored_energy_morphology_{timestamp}.csv"
    hierarchy_csv = REPORT_DIR / f"oty2_atom_part_shell_hierarchy_{timestamp}.csv"
    support_miss_csv = REPORT_DIR / f"oty2_gt_support_miss_failure_cases_{timestamp}.csv"
    review_csv = REPORT_DIR / f"oty2_gt_quality_visual_review_candidates_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_summary_{timestamp}.json"

    outputs = {
        "concept_correction_archive_doc": str(DOCS_DIR / "oty2_gt_support_failure_concept_correction_archive.md"),
        "plan_doc": str(DOCS_DIR / "oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_plan.md"),
        "sar_gt_vehicle_scale_statistics_csv": str(scale_csv),
        "sar_gt_quality_audit_csv": str(quality_csv),
        "gt_anchored_energy_morphology_csv": str(morphology_csv),
        "atom_part_shell_hierarchy_csv": str(hierarchy_csv),
        "gt_support_miss_failure_cases_csv": str(support_miss_csv),
        "gt_quality_visual_review_candidates_csv": str(review_csv),
        "gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_report_md": str(report_md),
        "gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_summary_json": str(summary_json),
        "visual_atlas_html": atlas_path,
    }
    summary = build_summary(
        timestamp,
        sources,
        outputs,
        scale_rows,
        quality_rows,
        morphology_rows,
        hierarchy_rows,
        support_miss_rows,
        review_rows,
        atlas_path,
        atlas_panels,
    )
    log_path = write_workspace_log(timestamp, outputs, summary, "after_run")
    summary["outputs"]["workspace_log"] = str(log_path)

    write_csv(scale_csv, scale_rows, SCALE_FIELDS)
    write_csv(quality_csv, quality_rows, QUALITY_FIELDS)
    write_csv(morphology_csv, morphology_rows, MORPHOLOGY_FIELDS)
    write_csv(hierarchy_csv, hierarchy_rows, HIERARCHY_FIELDS)
    write_csv(support_miss_csv, support_miss_rows, SUPPORT_MISS_FIELDS)
    write_csv(review_csv, review_rows, REVIEW_FIELDS)
    render_report(report_md, summary)
    write_json(summary_json, summary)

    print(
        json.dumps(
            {
                "outputs": summary["outputs"],
                "row_counts": summary["row_counts"],
                "key_metrics": summary["key_metrics"],
                "boundary_flags": summary["boundary_flags"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--image-cache-size", type=int, default=160)
    parser.add_argument("--gt-accounting-csv", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--gt-energy-csv", default="")
    parser.add_argument("--support-coverage-csv", default="")
    parser.add_argument("--support-peak-competition-csv", default="")
    parser.add_argument("--support-wide-atoms-csv", default="")
    parser.add_argument("--support-wide-shell-csv", default="")
    parser.add_argument("--support-failure-csv", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
