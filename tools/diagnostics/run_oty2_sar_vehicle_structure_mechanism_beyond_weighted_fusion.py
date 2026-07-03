"""OTY2 SAR vehicle structure mechanism exploration beyond weighted fusion.

This diagnostic explores SAR vehicle structure mechanisms as primitives,
compositions, graph proxies, temporal tubes, optical-conditioned hypotheses,
and visual-review cards. It reuses the committed OTY2 posthoc evidence and
SAR image observations, but it does not generate annotation proposals, final
boxes, selector/ranking outputs, trained models, tuned thresholds, best weights,
or identity-truth claims.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from run_oty2_range_narrowing_peak_competition_audit import (
    EXPECTED_LEDGER,
    FAN_CENTER_X,
    FAN_CENTER_Y,
    FAN_RADIUS_PX,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    compact_counts,
    fmt,
    latest_path,
    median_clean,
    read_csv,
    safe_float,
    safe_int,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
VISUAL_DIR = REPORT_DIR / "visual_exemplars"
PAIRED_POOL = "paired_215"
STATE_MODE = "state_conditioned_range_band"

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "sar_gt_valid_mask_audit_entered": True,
    "structure_primitive_extraction_entered": True,
    "structure_composition_hypothesis_entered": True,
    "structure_graph_probe_entered": True,
    "temporal_tube_probe_entered": True,
    "visual_review_cards_generated": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "gt_peak_or_residual_written_to_runtime_prior": False,
    "state_conditioned_topk_written_as_runtime_rule": False,
    "annotation_proposal_entered": False,
    "final_candidate_box_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "best_weight_selected": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "matlab_zip_or_any_zip_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
}

GT_AUDIT_FIELDS = [
    "gt_id",
    "scene",
    "sar_frame",
    "gt_box_or_polygon_available",
    "sar_valid_mask_available",
    "valid_mask_source",
    "image_available",
    "full_inside_sar_valid_mask",
    "mask_overlap_ratio",
    "near_mask_boundary",
    "gt_area_px",
    "pool_type",
    "valid_for_sar_morphology_reference",
    "valid_for_optical_sar_correspondence",
    "recommended_use",
    "not_allowed_use",
    "reason",
    "sar_pseudocolor_path",
]

PRIMITIVE_FIELDS = [
    "primitive_id",
    "case_id",
    "scene",
    "sar_frame",
    "primitive_type",
    "extraction_source",
    "intensity_relation",
    "range_position",
    "azimuth_position",
    "range_extent",
    "azimuth_extent",
    "area",
    "peak_count",
    "local_background_relation",
    "possible_vehicle_role",
    "possible_failure_role",
    "posthoc_gt_relation_validation_only",
    "human_review_needed",
    "notes",
]

COMPOSITION_FIELDS = [
    "hypothesis_id",
    "case_id",
    "composition_type",
    "primitives_used",
    "composition_rule_public",
    "n_primitives",
    "spatial_extent",
    "range_extent",
    "azimuth_extent",
    "internal_consistency",
    "peak_competition_context",
    "temporal_support_available",
    "compatible_with_optical_state",
    "compatible_with_vehicle_physics",
    "posthoc_gt_relation_validation_only",
    "can_support_association",
    "why_not_identity_truth",
    "failure_mode",
    "notes",
]

GRAPH_FIELDS = [
    "case_id",
    "graph_variant",
    "n_nodes",
    "n_edges",
    "n_connected_components",
    "dominant_component_size",
    "n_competing_components",
    "graph_fragmentation_level",
    "possible_vehicle_component_count",
    "neighboring_object_confounder_signal",
    "wrong_object_confounder_signal",
    "wrong_frame_confounder_signal",
    "human_review_needed",
    "mechanism_interpretation",
]

TUBE_FIELDS = [
    "tube_id",
    "case_id",
    "frame_window",
    "linked_primitives_or_components",
    "tube_type",
    "persistence_length",
    "centroid_drift",
    "range_drift",
    "azimuth_drift",
    "extent_stability",
    "intensity_stability",
    "compatible_with_optical_motion",
    "supports_existence_only",
    "supports_association_weakly",
    "confounded_by_wrong_frame",
    "failure_mode",
    "notes",
]

OPTICAL_FIELDS = [
    "optical_condition",
    "runtime_safe",
    "expected_sar_structure_change",
    "support_region_effect",
    "expected_failure_mode",
    "compatible_structure_types",
    "not_reliable_structure_types",
    "posthoc_evidence_seen",
    "needs_manual_review",
    "next_probe",
]

FAILURE_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "failure_type",
    "evidence_source",
    "why_selected",
    "mechanism_interpretation",
    "human_review_needed",
    "next_probe",
]

CARD_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "gt_id",
    "category",
    "why_selected",
    "what_human_should_look_for",
    "mechanism_question",
    "expected_decision_options",
    "image_path_if_generated",
    "posthoc_fields_present",
    "notes",
]


def bool_text(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def rate(num: int, den: int) -> str:
    return fmt(num / den if den else None, 4)


def clean_numbers(values: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        number = safe_float(value)
        if number is not None and math.isfinite(number):
            out.append(float(number))
    return out


def sanitize(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "").strip()).strip("_")[:96]


def case_id_for(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    frame = sanitize(row.get("sar_frame", row.get("expected_sar_frame", "frame")))
    if row.get("object_hypothesis_id"):
        obj = sanitize(row.get("object_hypothesis_id"))
        opt = sanitize(row.get("optical_frame", "opt"))
        return f"PAIR_{scene}_o{opt}_s{frame}_{obj}"
    return f"GT_{scene}_s{frame}_{sanitize(row.get('sar_gt_id', row.get('gt_id', 'gt')))}"


def parse_kv_box(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in str(text or "").replace(",", ";").split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        number = safe_float(value)
        if key.strip() and number is not None:
            values[key.strip()] = float(number)
    return values


def parse_center(text: str) -> tuple[float, float] | None:
    parts = [safe_float(part) for part in str(text or "").split(",")]
    if len(parts) >= 2 and parts[0] is not None and parts[1] is not None:
        return float(parts[0]), float(parts[1])
    return None


def gt_box_from_accounting(row: Mapping[str, Any]) -> dict[str, float]:
    box = parse_kv_box(str(row.get("gt_box", "")))
    return {
        "cx": box.get("cx", math.nan),
        "cy": box.get("cy", math.nan),
        "w": box.get("w", math.nan),
        "h": box.get("h", math.nan),
        "heading": box.get("heading", 0.0),
    }


def gt_box_from_correspondence(row: Mapping[str, Any]) -> dict[str, float]:
    center = parse_center(str(row.get("sar_gt_center", "")))
    size = parse_kv_box(str(row.get("sar_gt_width_height_or_rotated_box", "")))
    return {
        "cx": center[0] if center else math.nan,
        "cy": center[1] if center else math.nan,
        "w": size.get("w", math.nan),
        "h": size.get("h", math.nan),
        "heading": size.get("heading", 0.0),
    }


def box_available(box: Mapping[str, float]) -> bool:
    return all(math.isfinite(float(box.get(key, math.nan))) and float(box[key]) > 0 for key in ("cx", "cy", "w", "h"))


def rotated_corners(box: Mapping[str, float]) -> list[tuple[float, float]]:
    cx = float(box["cx"])
    cy = float(box["cy"])
    w = float(box["w"])
    h = float(box["h"])
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    corners: list[tuple[float, float]] = []
    for lx, ly in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        corners.append((cx + lx * ca - ly * sa, cy + lx * sa + ly * ca))
    return corners


def fan_radius(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


def fan_azimuth(x: float, y: float) -> float:
    return math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))


def fan_valid(x: float, y: float) -> bool:
    return fan_radius(x, y) <= FAN_RADIUS_PX


def box_overlap_with_fan(box: Mapping[str, float], step: float = 5.0) -> dict[str, Any]:
    if not box_available(box):
        return {
            "gt_box_or_polygon_available": False,
            "mask_overlap_ratio": None,
            "full_inside": None,
            "near_boundary": None,
            "min_boundary_distance_px": None,
        }
    corners = rotated_corners(box)
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    x0, x1 = math.floor(min(xs)), math.ceil(max(xs))
    y0, y1 = math.floor(min(ys)), math.ceil(max(ys))
    if x1 <= x0 or y1 <= y0:
        return {
            "gt_box_or_polygon_available": True,
            "mask_overlap_ratio": None,
            "full_inside": None,
            "near_boundary": None,
            "min_boundary_distance_px": None,
        }
    cx = float(box["cx"])
    cy = float(box["cy"])
    w = float(box["w"])
    h = float(box["h"])
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    xs_grid = np.arange(x0 + 0.5, x1 + 0.5, step, dtype=np.float32)
    ys_grid = np.arange(y0 + 0.5, y1 + 0.5, step, dtype=np.float32)
    xx, yy = np.meshgrid(xs_grid, ys_grid)
    dx = xx - cx
    dy = yy - cy
    local_x = ca * dx + sa * dy
    local_y = -sa * dx + ca * dy
    inside_poly = (np.abs(local_x) <= w / 2) & (np.abs(local_y) <= h / 2)
    if not bool(inside_poly.any()):
        ratio = None
    else:
        radius = np.hypot(xx - FAN_CENTER_X, yy - FAN_CENTER_Y)
        ratio = float((inside_poly & (radius <= FAN_RADIUS_PX)).sum() / inside_poly.sum())
    corner_dists = [FAN_RADIUS_PX - fan_radius(x, y) for x, y in corners]
    center_dist = FAN_RADIUS_PX - fan_radius(cx, cy)
    min_boundary = min(abs(value) for value in corner_dists + [center_dist])
    full_inside = all(value >= 0 for value in corner_dists)
    near_boundary = min_boundary <= 35.0 or (ratio is not None and ratio < 0.98)
    return {
        "gt_box_or_polygon_available": True,
        "mask_overlap_ratio": ratio,
        "full_inside": full_inside,
        "near_boundary": near_boundary,
        "min_boundary_distance_px": min_boundary,
    }


def pool_type(row: Mapping[str, Any]) -> str:
    status = str(row.get("match_status", ""))
    skip = str(row.get("skip_reason", ""))
    if status == "paired_optical_object_sar_gt":
        return PAIRED_POOL
    if status == "sar_only_gt":
        return "sar_only"
    if status == "no_oty_iou_match":
        return "dropout_special"
    if status == "blocked_missing_gm011_object_stream" or "gm011" in skip.lower():
        return "gm011_blocked"
    return "unknown"


def recommended_gt_use(pool: str, overlap: float | None, image_available: bool) -> tuple[str, str, str]:
    if overlap is None:
        return (
            "image_or_mask_availability_audit_only",
            "optical-SAR correspondence or morphology claims",
            "GT box/mask relation could not be judged",
        )
    boundary = overlap < 0.98
    if pool == PAIRED_POOL:
        use = "paired optical-SAR mechanism reference"
        if boundary:
            use += "; boundary-affected SAR morphology reference"
        return (use, "identity truth or final annotation", "paired object stream exists but GT relation remains posthoc")
    if pool == "sar_only":
        return ("SAR-only morphology reference", "optical-SAR correspondence", "no optical object stream counterpart")
    if pool == "gm011_blocked":
        return ("GM_RM011 waiting object-stream SAR reference", "paired correspondence before object stream recovery", "current OTY object stream missing")
    if pool == "dropout_special":
        return ("temporal continuation/existence support special pool", "clean paired morphology", "dropout/no-match rows are not clean morphology")
    if image_available:
        return ("SAR-side morphology reference with review", "paired correspondence", "pool type is unknown")
    return ("availability audit only", "mechanism conclusion", "image missing")


class ImageCache:
    def __init__(self) -> None:
        self._gray: dict[Path, np.ndarray | None] = {}

    def gray(self, path_text: str) -> np.ndarray | None:
        path = Path(str(path_text or ""))
        if path in self._gray:
            return self._gray[path]
        if not path.exists():
            self._gray[path] = None
            return None
        try:
            with Image.open(path) as source:
                self._gray[path] = np.asarray(source.convert("L"), dtype=np.float32)
        except OSError:
            self._gray[path] = None
        return self._gray[path]


def separated_peaks(xs: np.ndarray, ys: np.ndarray, values: np.ndarray, max_peaks: int = 5, min_distance: float = 12.0) -> list[tuple[float, float, float]]:
    if values.size == 0:
        return []
    order = np.argsort(values)[::-1]
    peaks: list[tuple[float, float, float]] = []
    for idx in order:
        x = float(xs[idx])
        y = float(ys[idx])
        value = float(values[idx])
        if all(math.hypot(x - px, y - py) >= min_distance for px, py, _ in peaks):
            peaks.append((x, y, value))
        if len(peaks) >= max_peaks:
            break
    return peaks


def primitive_from_patch(row: Mapping[str, Any], gt_audit: Mapping[str, Any], box: Mapping[str, float], cache: ImageCache) -> dict[str, Any]:
    case_id = case_id_for(row)
    image_path = str(row.get("sar_pseudocolor_path", ""))
    arr = cache.gray(image_path)
    gt_id = str(row.get("sar_gt_id", row.get("gt_id", "")))
    primitive_id = f"PRIM_{case_id}"
    if arr is None or not box_available(box):
        return {
            "primitive_id": primitive_id,
            "case_id": case_id,
            "scene": row.get("scene", ""),
            "sar_frame": row.get("sar_frame", ""),
            "primitive_type": "image_or_gt_box_unavailable",
            "extraction_source": "442_gt_reference_patch",
            "intensity_relation": "",
            "range_position": "",
            "azimuth_position": "",
            "range_extent": "",
            "azimuth_extent": "",
            "area": fmt(safe_float(gt_audit.get("gt_area_px")), 2),
            "peak_count": "",
            "local_background_relation": "",
            "possible_vehicle_role": "unjudged",
            "possible_failure_role": "availability_blocker",
            "posthoc_gt_relation_validation_only": f"gt_id={gt_id}",
            "human_review_needed": "yes",
            "notes": "No image or no GT polygon; no primitive was fabricated.",
        }
    cx = float(box["cx"])
    cy = float(box["cy"])
    w = float(box["w"])
    h = float(box["h"])
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    corners = rotated_corners(box)
    x0 = max(0, int(math.floor(min(x for x, _ in corners))) - 8)
    x1 = min(arr.shape[1], int(math.ceil(max(x for x, _ in corners))) + 8)
    y0 = max(0, int(math.floor(min(y for _, y in corners))) - 8)
    y1 = min(arr.shape[0], int(math.ceil(max(y for _, y in corners))) + 8)
    if x1 <= x0 or y1 <= y0:
        values = np.array([], dtype=np.float32)
        xx = yy = np.array([], dtype=np.float32)
    else:
        yy_grid, xx_grid = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx = xx_grid + 0.5 - cx
        dy = yy_grid + 0.5 - cy
        local_x = ca * dx + sa * dy
        local_y = -sa * dx + ca * dy
        poly_mask = (np.abs(local_x) <= w / 2) & (np.abs(local_y) <= h / 2)
        radius = np.hypot(xx_grid + 0.5 - FAN_CENTER_X, yy_grid + 0.5 - FAN_CENTER_Y)
        valid = poly_mask & (radius <= FAN_RADIUS_PX)
        values = arr[y0:y1, x0:x1][valid]
        xx = (xx_grid + 0.5)[valid]
        yy = (yy_grid + 0.5)[valid]
        bg_mask = (~poly_mask) & (radius <= FAN_RADIUS_PX)
        bg_values = arr[y0:y1, x0:x1][bg_mask]
    if values.size == 0:
        primitive_type = "boundary_or_empty_gt_patch"
        peak_count = 0
        range_pos = az_pos = range_extent = az_extent = ""
        relation = ""
        local_bg = ""
    else:
        bg_mean = float(bg_values.mean()) if "bg_values" in locals() and bg_values.size else max(float(arr.mean()), 1.0)
        p95 = float(np.quantile(values, 0.95))
        peak = float(values.max())
        relation_value = peak / max(bg_mean, 1.0)
        threshold = max(float(np.quantile(values, 0.9)), bg_mean)
        high = values >= threshold
        if not bool(high.any()):
            high = values >= p95
        peaks = separated_peaks(xx[high], yy[high], values[high])
        peak_count = len(peaks)
        weights = np.maximum(values[high], 1.0) if bool(high.any()) else np.maximum(values, 1.0)
        hx = xx[high] if bool(high.any()) else xx
        hy = yy[high] if bool(high.any()) else yy
        centroid_x = float((hx * weights).sum() / weights.sum())
        centroid_y = float((hy * weights).sum() / weights.sum())
        radii = np.hypot(hx - FAN_CENTER_X, hy - FAN_CENTER_Y)
        azimuths = np.degrees(np.arctan2(hx - FAN_CENTER_X, FAN_CENTER_Y - hy))
        range_pos = fmt(float(np.median(radii)), 3)
        az_pos = fmt(float(np.median(azimuths)), 3)
        range_extent_value = float(radii.max() - radii.min()) if radii.size else 0.0
        az_extent_value = float(azimuths.max() - azimuths.min()) if azimuths.size else 0.0
        range_extent = fmt(range_extent_value, 3)
        az_extent = fmt(az_extent_value, 3)
        relation = f"peak_bg={fmt(relation_value, 3)};p95_bg={fmt(p95 / max(bg_mean, 1.0), 3)}"
        local_bg = f"gt_patch_mean={fmt(float(values.mean()), 3)};local_bg_mean={fmt(bg_mean, 3)}"
        if float(gt_audit.get("mask_overlap_ratio") or 0) < 0.5:
            primitive_type = "boundary_affected_body_proxy"
        elif p95 / max(bg_mean, 1.0) < 1.08:
            primitive_type = "background_clutter_patch"
        elif peak_count <= 1 and range_extent_value < 70 and az_extent_value < 5:
            primitive_type = "compact_blob"
        elif peak_count == 2:
            primitive_type = "peak_pair"
        elif range_extent_value >= 90:
            primitive_type = "range_ridge"
        elif az_extent_value >= 8:
            primitive_type = "azimuth_ridge"
        elif peak_count >= 3:
            primitive_type = "peak_group"
        else:
            primitive_type = "multi_peak_body_proxy"
    possible_vehicle_role, possible_failure_role = primitive_roles(primitive_type)
    return {
        "primitive_id": primitive_id,
        "case_id": case_id,
        "scene": row.get("scene", ""),
        "sar_frame": row.get("sar_frame", ""),
        "primitive_type": primitive_type,
        "extraction_source": "442_gt_reference_patch;fallback_fan_valid_mask",
        "intensity_relation": relation,
        "range_position": range_pos,
        "azimuth_position": az_pos,
        "range_extent": range_extent,
        "azimuth_extent": az_extent,
        "area": fmt(safe_float(gt_audit.get("gt_area_px")), 2),
        "peak_count": peak_count,
        "local_background_relation": local_bg,
        "possible_vehicle_role": possible_vehicle_role,
        "possible_failure_role": possible_failure_role,
        "posthoc_gt_relation_validation_only": f"gt_id={gt_id};pool={gt_audit.get('pool_type', '')}",
        "human_review_needed": "yes" if primitive_type in {"background_clutter_patch", "boundary_affected_body_proxy", "range_ridge", "azimuth_ridge", "peak_group"} else "no",
        "notes": "Primitive is SAR-side observation/reference, not a selector feature or final target box.",
    }


def primitive_roles(primitive_type: str) -> tuple[str, str]:
    roles = {
        "compact_blob": ("possible compact vehicle body", "can be confused with a compact clutter peak"),
        "peak_pair": ("possible two-scatter vehicle proxy", "nearby object or sidelobe pair"),
        "peak_group": ("possible multi-peak vehicle body", "peak competition / neighboring scatterers"),
        "range_ridge": ("possible range-spread vehicle body", "range sidelobe or radial background streak"),
        "azimuth_ridge": ("possible azimuth-spread vehicle body", "wide sector inclusion or azimuth sidelobe"),
        "background_clutter_patch": ("unlikely vehicle by itself", "background clutter / weak contrast"),
        "boundary_affected_body_proxy": ("boundary-affected vehicle reference", "partial valid-mask support"),
        "multi_peak_body_proxy": ("possible body scatter composition", "under-specified multi-peak support"),
    }
    return roles.get(primitive_type, ("unjudged", "availability or extraction blocker"))


def build_gt_reference_audit(gt_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for row in gt_rows:
        box = gt_box_from_accounting(row)
        overlap = box_overlap_with_fan(box)
        path = Path(str(row.get("sar_pseudocolor_path", "")))
        image_available = path.exists()
        pool = pool_type(row)
        area = float(box.get("w", 0.0)) * float(box.get("h", 0.0)) if box_available(box) else None
        ratio = overlap.get("mask_overlap_ratio")
        recommended_use, not_allowed, reason = recommended_gt_use(pool, ratio, image_available)
        valid_for_morph = image_available and ratio is not None and ratio > 0
        valid_for_corr = pool == PAIRED_POOL and is_true(row.get("usable_for_optical_sar_correspondence"))
        audit_rows.append(
            {
                "gt_id": row.get("sar_gt_id", ""),
                "scene": row.get("scene", ""),
                "sar_frame": row.get("sar_frame", ""),
                "gt_box_or_polygon_available": bool_text(bool(overlap.get("gt_box_or_polygon_available"))),
                "sar_valid_mask_available": "true",
                "valid_mask_source": "fallback_fan_valid_region_no_external_mask_file_found",
                "image_available": bool_text(image_available),
                "full_inside_sar_valid_mask": bool_text(overlap.get("full_inside")),
                "mask_overlap_ratio": fmt(ratio, 4),
                "near_mask_boundary": bool_text(overlap.get("near_boundary")),
                "gt_area_px": fmt(area, 3),
                "pool_type": pool,
                "valid_for_sar_morphology_reference": bool_text(valid_for_morph),
                "valid_for_optical_sar_correspondence": bool_text(valid_for_corr),
                "recommended_use": recommended_use,
                "not_allowed_use": not_allowed,
                "reason": reason,
                "sar_pseudocolor_path": row.get("sar_pseudocolor_path", ""),
            }
        )
    return audit_rows


def build_primitives(gt_rows: Sequence[Mapping[str, Any]], gt_audit_rows: Sequence[Mapping[str, Any]], cache: ImageCache) -> list[dict[str, Any]]:
    audit_by_id = {
        (str(row.get("scene", "")), str(row.get("sar_frame", "")), str(row.get("gt_id", ""))): row
        for row in gt_audit_rows
    }
    primitives: list[dict[str, Any]] = []
    for row in gt_rows:
        key = (str(row.get("scene", "")), str(row.get("sar_frame", "")), str(row.get("sar_gt_id", "")))
        audit = audit_by_id.get(key, {})
        primitives.append(primitive_from_patch(row, audit, gt_box_from_accounting(row), cache))
    return primitives


def support_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("sar_frame", "")),
    )


def corr_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("sar_frame", "")),
    )


def build_compositions(
    support_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    primitive_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    primitive_by_scene_frame: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for prim in primitive_rows:
        primitive_by_scene_frame[(str(prim.get("scene", "")), str(prim.get("sar_frame", "")))].append(prim)
    corr_by_key = {corr_key(row): row for row in corr_rows}
    rows: list[dict[str, Any]] = []
    state_support = [row for row in support_rows if row.get("support_type_or_source") == STATE_MODE]
    for idx, row in enumerate(state_support, start=1):
        case_id = case_id_for(row)
        primitives = primitive_by_scene_frame.get((str(row.get("scene", "")), str(row.get("sar_frame", ""))), [])
        primitive_names = [str(item.get("primitive_type", "")) for item in primitives[:4]]
        cluster = str(row.get("dominant_structure_type", ""))
        temporal = str(row.get("observed_sar_structures_inside_support", ""))
        composition_type, rule = composition_type_for(cluster, temporal, primitive_names)
        association = str(row.get("association_state_posthoc", ""))
        if str(row.get("unique_sar_structure_exists", "")) == "yes" and str(row.get("association_candidate_exists", "")) == "yes":
            support = "posthoc_candidate"
        elif str(row.get("association_candidate_exists", "")) == "yes":
            support = "weak" if "weak" in association else "review"
        elif "review" in association:
            support = "review"
        else:
            support = "no"
        corr = corr_by_key.get(support_key(row), {})
        rows.append(
            {
                "hypothesis_id": f"COMP{idx:05d}",
                "case_id": case_id,
                "composition_type": composition_type,
                "primitives_used": ";".join(primitive_names) if primitive_names else cluster,
                "composition_rule_public": rule,
                "n_primitives": len(primitive_names) if primitive_names else 1,
                "spatial_extent": f"support_area_px={row.get('support_area_px', '')};gt_box={corr.get('sar_gt_width_height_or_rotated_box', '')}",
                "range_extent": row.get("radius_band_width_px", ""),
                "azimuth_extent": row.get("support_azimuth_width_deg", ""),
                "internal_consistency": internal_consistency(row, cluster),
                "peak_competition_context": "serious" if row.get("serious_peak_competition") == "yes" else "not_serious_by_current_proxy",
                "temporal_support_available": "yes" if "stable_cluster_tube" in temporal else "partial_or_no",
                "compatible_with_optical_state": "uncertain" if "review" in association or "ambiguous" in association else "yes",
                "compatible_with_vehicle_physics": vehicle_physics_compatibility(composition_type),
                "posthoc_gt_relation_validation_only": f"gt_inside={row.get('gt_inside_support_posthoc', '')};topk_near={row.get('topk_contains_near_gt_posthoc', '')}",
                "can_support_association": support,
                "why_not_identity_truth": "object-time association still has wrong-object/wrong-frame confounding; this is not a final label",
                "failure_mode": failure_mode_for(row, composition_type),
                "notes": "Composition hypothesis uses public structure rules and posthoc validation columns; no final box is emitted.",
            }
        )
    return rows


def composition_type_for(cluster: str, temporal: str, primitives: Sequence[str]) -> tuple[str, str]:
    if "stable_cluster_tube" in temporal and cluster in {"compact_cluster", "multi_peak_nearby_cluster"}:
        return ("stable-tube vehicle proxy", "stable SAR tube plus compact/multi-peak primitive family")
    if cluster == "compact_cluster" or "compact_blob" in primitives:
        return ("single compact body hypothesis", "one compact primitive with bounded spread inside support")
    if cluster == "multi_peak_nearby_cluster" or "peak_pair" in primitives or "peak_group" in primitives:
        return ("multi-peak body hypothesis", "nearby high-response primitive group without selecting a single peak")
    if cluster == "range_spread_cluster" or "range_ridge" in primitives:
        return ("range-spread body hypothesis", "radial primitive extent suggests body/ridge or sidelobe risk")
    if cluster == "azimuth_spread_cluster" or "azimuth_ridge" in primitives:
        return ("azimuth-spread body hypothesis", "cross-range primitive extent suggests body spread or sector overlap")
    if cluster == "diffuse_clutter":
        return ("diffuse-only reject hypothesis", "diffuse clutter lacks isolated vehicle composition")
    return ("background-stable reject hypothesis", "weak or unstable structure cannot support association")


def internal_consistency(row: Mapping[str, Any], cluster: str) -> str:
    if row.get("unique_sar_structure_exists") == "yes":
        return "high"
    if cluster in {"compact_cluster", "multi_peak_nearby_cluster"} and row.get("observed_sar_structures_inside_support", "").find("stable_cluster_tube") >= 0:
        return "medium_temporal_but_not_unique"
    if cluster in {"range_spread_cluster", "azimuth_spread_cluster"}:
        return "medium_spread_structure"
    return "low_or_ambiguous"


def vehicle_physics_compatibility(composition_type: str) -> str:
    if composition_type in {"single compact body hypothesis", "multi-peak body hypothesis", "stable-tube vehicle proxy"}:
        return "yes"
    if "spread" in composition_type:
        return "uncertain"
    return "no"


def failure_mode_for(row: Mapping[str, Any], composition_type: str) -> str:
    if row.get("no_unique_structure_can_be_isolated") == "yes":
        return "no_unique_structure_isolated"
    if "reject" in composition_type:
        return "sar_structure_ambiguous_or_background"
    if row.get("support_too_broad_for_association") == "yes":
        return "support_still_too_broad_for_association"
    return "object_time_provenance_not_closed"


def bucket_count(value: Any, limits: Sequence[tuple[float, str]], default: str) -> str:
    number = safe_float(value)
    if number is None:
        return default
    for threshold, label in limits:
        if number <= threshold:
            return label
    return default


def build_graph_rows(
    support_rows: Sequence[Mapping[str, Any]],
    crosscheck_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    wrong_object_by_structure = {
        row.get("structure_type"): safe_float(row.get("near_gt_topk_rate_posthoc"))
        for row in crosscheck_rows
        if row.get("control_type") == "wrong_object_support"
    }
    wrong_frame_by_structure = {
        row.get("structure_type"): safe_float(row.get("near_gt_topk_rate_posthoc"))
        for row in crosscheck_rows
        if row.get("control_type") == "wrong_sar_frame_support"
    }
    rows: list[dict[str, Any]] = []
    state_support = [row for row in support_rows if row.get("support_type_or_source") == STATE_MODE]
    for row in state_support:
        structure = str(row.get("dominant_structure_type", ""))
        plausible = safe_float(row.get("number_of_plausible_structures"))
        if structure == "compact_cluster":
            nodes, edges, comps = 2, 1, 1
        elif structure == "multi_peak_nearby_cluster":
            nodes, edges, comps = 5, 5, 1
        elif structure in {"range_spread_cluster", "azimuth_spread_cluster"}:
            nodes, edges, comps = 6, 4, 2
        elif structure == "diffuse_clutter":
            nodes, edges, comps = 8, 3, 5
        else:
            nodes, edges, comps = 3, 1, 2
        if plausible is not None and plausible > 2000:
            comps = max(comps, 4)
        competing = max(0, comps - 1)
        frag = "low_single_component" if comps == 1 else ("medium_multi_component" if comps <= 3 else "high_fragmented_or_dense")
        wrong_obj = wrong_object_by_structure.get(structure)
        wrong_frame = wrong_frame_by_structure.get(structure)
        rows.append(
            {
                "case_id": case_id_for(row),
                "graph_variant": "primitive_proxy_graph_from_state_conditioned_support",
                "n_nodes": nodes,
                "n_edges": edges,
                "n_connected_components": comps,
                "dominant_component_size": max(1, nodes - competing),
                "n_competing_components": competing,
                "graph_fragmentation_level": frag,
                "possible_vehicle_component_count": 1 if structure in {"compact_cluster", "multi_peak_nearby_cluster"} else "uncertain",
                "neighboring_object_confounder_signal": "possible" if wrong_obj is not None and wrong_obj >= 0.5 else "not_established",
                "wrong_object_confounder_signal": "high" if wrong_obj is not None and wrong_obj >= 0.5 else "unknown_or_low",
                "wrong_frame_confounder_signal": "high" if wrong_frame is not None and wrong_frame >= 0.5 else "unknown_or_low",
                "human_review_needed": "yes" if frag != "low_single_component" or row.get("association_candidate_exists") != "yes" else "no",
                "mechanism_interpretation": graph_interpretation(structure, frag),
            }
        )
    return rows


def graph_interpretation(structure: str, frag: str) -> str:
    if frag == "low_single_component":
        return "support resembles one dominant structure, but identity still needs temporal/object provenance"
    if structure in {"range_spread_cluster", "azimuth_spread_cluster"}:
        return "support contains an extended component; graph form captures spread better than top-k"
    if structure == "diffuse_clutter":
        return "support is fragmented/diffuse and likely needs review or rejection"
    return "multiple competing components explain why unique structure isolation remains zero"


def build_tube_rows(temporal_rows: Sequence[Mapping[str, Any]], confounder_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    wrong_frame_rate = safe_float(confounder_summary.get("key_metrics", {}).get("state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc"))
    wrong_frame_high = wrong_frame_rate is not None and wrong_frame_rate >= 0.5
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(temporal_rows, start=1):
        label = str(row.get("stability_label", row.get("temporal_cluster_label", "")))
        sample_pool = str(row.get("sample_pool", ""))
        mix = str(row.get("scatter_structure_mix", row.get("scatter_cluster_type_mix", "")))
        if sample_pool != "paired_optical_object_sar_gt":
            tube_type = "dropout_existence_tube"
        elif label == "stable_cluster_tube" and "diffuse" not in mix:
            tube_type = "vehicle-like drifting tube candidate"
        elif label == "stable_cluster_tube":
            tube_type = "stable background tube risk"
        elif label == "jumping_peak":
            tube_type = "jumping peak tube"
        else:
            tube_type = "diffuse or fragmented tube"
        rows.append(
            {
                "tube_id": f"TUBE{idx:04d}",
                "case_id": case_id_for(row),
                "frame_window": row.get("frame_window", row.get("sar_frame_span", "")),
                "linked_primitives_or_components": mix,
                "tube_type": tube_type,
                "persistence_length": row.get("persistence_length", row.get("n_frames", "")),
                "centroid_drift": row.get("drift_or_centroid_change_px", row.get("centroid_step_mean_px", "")),
                "range_drift": "not_available_in_existing_temporal_probe",
                "azimuth_drift": "not_available_in_existing_temporal_probe",
                "extent_stability": row.get("range_extent_stability", "partial_not_available"),
                "intensity_stability": row.get("peak_consistency", row.get("cluster_persistence_rate", "")),
                "compatible_with_optical_motion": "uncertain_needs_motion_gate",
                "supports_existence_only": "yes" if sample_pool != "paired_optical_object_sar_gt" else "no",
                "supports_association_weakly": "yes" if tube_type == "vehicle-like drifting tube candidate" else "no",
                "confounded_by_wrong_frame": "yes" if wrong_frame_high else "uncertain",
                "failure_mode": "wrong_frame_persistence_risk" if wrong_frame_high else "temporal_evidence_partial",
                "notes": "Temporal persistence is split from identity association; dropout rows remain existence support only.",
            }
        )
    return rows


def build_optical_condition_rows(support_rows: Sequence[Mapping[str, Any]], corr_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    corr_states = Counter()
    for row in corr_rows:
        text = ";".join(
            str(row.get(key, ""))
            for key in ("optical_object_state", "visibility_state", "edge_partial_duplicate_handoff_ambiguity_flags")
        ).lower()
        if "complete" in text or "low_uncertainty" in text:
            corr_states["complete_visible_object"] += 1
        if "partial=true" in text or "trunc" in text:
            corr_states["left_right_truncation_or_edge"] += 1
        if "boundary=true" in text:
            corr_states["edge_contact"] += 1
        if "duplicate" in text or "handoff" in text or "ambiguous" in text:
            corr_states["identity_ambiguity"] += 1
    support_counts = Counter(row.get("dominant_structure_type", "") for row in support_rows if row.get("support_type_or_source") == STATE_MODE)
    rows = [
        (
            "complete visible object",
            "yes",
            "compact or multi-peak body should become more plausible if SAR structure is stable",
            "can use tighter optical state support, but current range bands are still posthoc",
            "compact clutter may be mistaken for body",
            "compact_cluster;multi_peak_nearby_cluster;stable_cluster_tube",
            "diffuse_clutter;weak_no_structure",
            f"complete/low-uncertainty proxy rows={corr_states['complete_visible_object']};structure_mix={compact_counts(support_counts.elements())}",
            "no",
            "visual exemplar check for compact/multi-peak cases",
        ),
        (
            "left/right truncation",
            "yes",
            "vehicle structure may become spread, partial, or shifted within support",
            "widen or relax feasible domain rather than selecting a center",
            "range/azimuth spread can be vehicle or boundary artifact",
            "range_spread_cluster;azimuth_spread_cluster;stable_cluster_tube",
            "single top1 peak",
            f"partial/truncation proxy rows={corr_states['left_right_truncation_or_edge']}",
            "yes",
            "state-specific visual review and boundary-aware support",
        ),
        (
            "bottom truncation / occlusion",
            "yes",
            "SAR body may be only partly represented; temporal tube may be stronger than current frame",
            "use existence and tube support, not clean morphology",
            "dropout/existence can be over-promoted",
            "stable_cluster_tube;range_spread_cluster",
            "complete-shape range rule",
            "dropout pool remains 12 special rows",
            "yes",
            "keep dropout pool separate",
        ),
        (
            "edge contact",
            "yes",
            "mask-boundary and fan-edge effects can truncate SAR structure",
            "support should remain boundary-aware",
            "valid-mask partial overlap and weak structure",
            "boundary_affected_body_proxy;azimuth_spread_cluster",
            "unique center isolation",
            f"edge proxy rows={corr_states['edge_contact']}",
            "yes",
            "inspect boundary cases in 442 valid mask audit",
        ),
        (
            "motion instability",
            "yes",
            "SAR tube should show plausible drift, not jumping peak",
            "requires temporal linking rather than per-frame selection",
            "wrong-frame persistence can mimic stable structure",
            "vehicle-like drifting tube candidate",
            "jumping_peak;stable background tube risk",
            "existing tube rows lack explicit range/azimuth drift",
            "yes",
            "add optical-motion compatible drift gate",
        ),
        (
            "identity ambiguity",
            "yes",
            "structure may be vehicle-like but not attributable to one optical object",
            "association must become review_required or weak",
            "wrong-object support overlap",
            "multi_peak_nearby_cluster;stable_cluster_tube",
            "associated strong without review",
            f"duplicate/handoff/ambiguous proxy rows={corr_states['identity_ambiguity']}",
            "yes",
            "GM_RM019 optical continuity review",
        ),
        (
            "bbox height / apparent scale",
            "no_currently_posthoc_hypothesis",
            "may relate to range concentration, but not runtime-approved here",
            "do not convert shape-radius relation into runtime prior",
            "GT-validated range bands can leak",
            "range_spread_cluster as diagnostic",
            "state-conditioned top-k success as runtime rule",
            "state-conditioned true is 0.8977 but posthoc",
            "yes",
            "derive optical-only range mechanism before runtime use",
        ),
        (
            "tracklet smoothing",
            "partial",
            "may stabilize feasible support across adjacent SAR frames",
            "use as temporal support stabilizer, not identity truth",
            "wrong-frame controls remain high",
            "stable_cluster_tube",
            "wrong-frame-tolerant association",
            "wrong-frame state-conditioned top-k near-GT is 0.9116",
            "yes",
            "separate vehicle-like drift from background persistence",
        ),
        (
            "azimuth trend",
            "yes",
            "may condition which azimuth-spread structures are plausible",
            "sector overlap must be audited before strong gate",
            "azimuth-shift confounding",
            "azimuth_spread_cluster with temporal support",
            "azimuth alone as strong gate",
            "azimuth-shift state-conditioned top-k near-GT is 0.7151",
            "yes",
            "overlap-aware azimuth margin audit",
        ),
        (
            "near/mid/far relative depth hint",
            "partial_or_hypothesis",
            "may alter expected spread and intensity concentration",
            "only weak conditioning unless runtime-safe source is documented",
            "depth-like cues can become hidden range GT leakage",
            "range_spread_cluster;compact_cluster",
            "hard depth controller",
            "not sufficiently separated in existing tables",
            "yes",
            "document runtime-safe depth source before use",
        ),
    ]
    return [
        {
            "optical_condition": item[0],
            "runtime_safe": item[1],
            "expected_sar_structure_change": item[2],
            "support_region_effect": item[3],
            "expected_failure_mode": item[4],
            "compatible_structure_types": item[5],
            "not_reliable_structure_types": item[6],
            "posthoc_evidence_seen": item[7],
            "needs_manual_review": item[8],
            "next_probe": item[9],
        }
        for item in rows
    ]


def build_failure_index(support_rows: Sequence[Mapping[str, Any]], graph_rows: Sequence[Mapping[str, Any]], crosscheck_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    graph_by_case = {row.get("case_id"): row for row in graph_rows}
    for row in support_rows:
        if row.get("support_type_or_source") != STATE_MODE:
            continue
        if row.get("unique_sar_structure_exists") == "yes" and row.get("association_candidate_exists") == "yes":
            continue
        case_id = case_id_for(row)
        graph = graph_by_case.get(case_id, {})
        state = str(row.get("association_state_posthoc", ""))
        if "temporal" in state:
            failure_type = "temporal_instability_or_wrong_frame_risk"
        elif "optical_ambiguous" in state or "review" in state:
            failure_type = "optical_object_ambiguity"
        elif "sar_ambiguous" in state:
            failure_type = "sar_structure_ambiguity"
        else:
            failure_type = "no_unique_structure_isolated"
        failures.append(
            {
                "case_id": case_id,
                "scene": row.get("scene", ""),
                "sar_frame": row.get("sar_frame", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "failure_type": failure_type,
                "evidence_source": "support_region_structure_observation;proxy_graph_probe",
                "why_selected": f"structure={row.get('dominant_structure_type', '')};association_state={state};graph={graph.get('graph_fragmentation_level', '')}",
                "mechanism_interpretation": "case needs isolation/weak/review handling before association",
                "human_review_needed": "yes",
                "next_probe": "visual exemplar review and motion/graph disambiguation",
            }
        )
    for row in crosscheck_rows:
        control = str(row.get("control_type", ""))
        if control not in {"wrong_object_support", "wrong_sar_frame_support", "azimuth_shifted_support"}:
            continue
        rate_value = safe_float(row.get("near_gt_topk_rate_posthoc"))
        if rate_value is None or rate_value < 0.5:
            continue
        case_id = f"CONTROL_{sanitize(control)}_{sanitize(row.get('structure_type'))}_{len(failures)+1:04d}"
        failures.append(
            {
                "case_id": case_id,
                "scene": "",
                "sar_frame": "",
                "object_hypothesis_id": "",
                "failure_type": f"{control}_confounder",
                "evidence_source": "structure_counterfactual_crosscheck",
                "why_selected": f"topk_rate_posthoc={row.get('near_gt_topk_rate_posthoc', '')};structure={row.get('structure_type', '')}",
                "mechanism_interpretation": row.get("mechanism_interpretation", ""),
                "human_review_needed": "yes",
                "next_probe": "negative-control visual exemplar and overlap/motion audit",
            }
        )
    return failures


def select_first(rows: Sequence[Mapping[str, Any]], predicate) -> Mapping[str, Any] | None:
    for row in rows:
        if predicate(row):
            return row
    return None


def card_from_support(row: Mapping[str, Any] | None, category: str, why: str, look_for: str, question: str) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "case_id": case_id_for(row),
        "scene": row.get("scene", ""),
        "sar_frame": row.get("sar_frame", ""),
        "object_hypothesis_id": row.get("object_hypothesis_id", ""),
        "gt_id": "",
        "category": category,
        "why_selected": why,
        "what_human_should_look_for": look_for,
        "mechanism_question": question,
        "expected_decision_options": "isolate / weak / review / posthoc_candidate",
        "image_path_if_generated": "",
        "posthoc_fields_present": f"gt_inside={row.get('gt_inside_support_posthoc', '')};topk={row.get('topk_contains_near_gt_posthoc', '')}",
        "notes": "Visual card is for review only and is not an annotation proposal.",
    }


def build_visual_cards(
    support_rows: Sequence[Mapping[str, Any]],
    gt_audit_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    support = [row for row in support_rows if row.get("support_type_or_source") == STATE_MODE]
    cards: list[dict[str, Any]] = []
    specs = [
        (
            lambda r: r.get("dominant_structure_type") == "compact_cluster",
            "possible compact vehicle structure",
            "compact_cluster observed inside support",
            "whether compact response is vehicle body or compact clutter",
            "Can compact SAR evidence support weak/posthoc association?",
        ),
        (
            lambda r: r.get("dominant_structure_type") == "multi_peak_nearby_cluster",
            "possible multi-peak vehicle structure",
            "multi_peak_nearby_cluster observed",
            "whether nearby peaks form one vehicle body or neighboring scatterers",
            "Can a peak group be composed before association?",
        ),
        (
            lambda r: r.get("dominant_structure_type") == "range_spread_cluster",
            "possible range-spread vehicle structure",
            "range_spread_cluster observed",
            "whether radial spread is vehicle body, sidelobe, or support artifact",
            "Does range-spread structure need a separate composition rule?",
        ),
        (
            lambda r: r.get("dominant_structure_type") == "azimuth_spread_cluster",
            "possible azimuth-spread vehicle structure",
            "azimuth_spread_cluster dominates current state-conditioned support",
            "whether spread is vehicle width/cross-range response or sector overlap",
            "Does azimuth-spread explain high azimuth-shift controls?",
        ),
        (
            lambda r: "stable_cluster_tube" in str(r.get("observed_sar_structures_inside_support", "")),
            "possible stable vehicle tube",
            "stable_cluster_tube appears in observation",
            "whether the tube drifts like a target or persists like background",
            "Can temporal persistence be split into vehicle-like versus background?",
        ),
        (
            lambda r: r.get("dominant_structure_type") == "diffuse_clutter",
            "diffuse / reject exemplar",
            "diffuse_clutter observed",
            "whether support contains only diffuse background",
            "When should SAR structure remain isolated or rejected?",
        ),
        (
            lambda r: r.get("association_state_posthoc") == "rejected_for_temporal_instability",
            "background-stable wrong-frame exemplar",
            "temporal instability or wrong-frame risk",
            "whether same scene structure persists across wrong frames",
            "Why does wrong-frame remain high?",
        ),
        (
            lambda r: r.get("association_state_posthoc") == "sar_structure_present_but_optical_ambiguous",
            "neighboring-object wrong-object exemplar",
            "SAR structure exists but optical object ambiguous",
            "whether graph components overlap neighboring objects",
            "Why does wrong-object remain high?",
        ),
        (
            lambda r: r.get("dominant_structure_type") == "azimuth_spread_cluster" and r.get("topk_contains_near_gt_posthoc") == "true",
            "support-overlap azimuth-shift exemplar",
            "azimuth-spread plus posthoc hit",
            "whether broad azimuth support contains the same component after shifts",
            "Why is azimuth-shift still high?",
        ),
        (
            lambda r: r.get("vehicle_like_sar_structure_exists") == "yes" and r.get("unique_sar_structure_exists") != "yes",
            "statistics say vehicle-like but visual review likely needed",
            "vehicle-like structure exists but unique isolation is false",
            "whether one component is visually dominant enough for review",
            "Should this be weak, review, or posthoc candidate?",
        ),
        (
            lambda r: r.get("gt_inside_support_posthoc") == "true" and r.get("association_state_posthoc") == "associated_posthoc_weak",
            "case where GT is inside support but association should remain weak",
            "GT is inside support but association remains weak",
            "whether GT coverage hides object-time ambiguity",
            "Why coverage is not localization or identity truth?",
        ),
    ]
    for pred, category, why, look_for, question in specs:
        card = card_from_support(select_first(support, pred), category, why, look_for, question)
        if card:
            cards.append(card)
    # Add SAR-only and GM_RM011 reference cards from the 442 audit.
    for pool, category in [
        ("sar_only", "SAR-only morphology reference exemplar"),
        ("gm011_blocked", "GM_RM011 waiting object-stream reference exemplar"),
    ]:
        ref = select_first(gt_audit_rows, lambda r, p=pool: r.get("pool_type") == p and r.get("image_available") == "true")
        if ref:
            cards.append(
                {
                    "case_id": f"GTREF_{sanitize(ref.get('scene'))}_s{sanitize(ref.get('sar_frame'))}_{sanitize(ref.get('gt_id'))}",
                    "scene": ref.get("scene", ""),
                    "sar_frame": ref.get("sar_frame", ""),
                    "object_hypothesis_id": "",
                    "gt_id": ref.get("gt_id", ""),
                    "category": category,
                    "why_selected": ref.get("recommended_use", ""),
                    "what_human_should_look_for": "SAR morphology only; no optical-SAR correspondence claim",
                    "mechanism_question": "What SAR-side structure should be used as reference without mixing pools?",
                    "expected_decision_options": "isolate / weak / review / posthoc_candidate",
                    "image_path_if_generated": "",
                    "posthoc_fields_present": "SAR GT reference only",
                    "notes": ref.get("reason", ""),
                }
            )
    return cards


def accounting_lookup(gt_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    return {
        (str(row.get("scene", "")), str(row.get("sar_frame", "")), str(row.get("sar_gt_id", ""))): row
        for row in gt_rows
    }


def corr_lookup(corr_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    return {corr_key(row): row for row in corr_rows}


def source_for_card(card: Mapping[str, Any], gt_rows: Sequence[Mapping[str, Any]], corr_rows: Sequence[Mapping[str, Any]]) -> tuple[str, dict[str, float] | None]:
    if card.get("gt_id"):
        for row in gt_rows:
            if str(row.get("scene")) == str(card.get("scene")) and str(row.get("sar_frame")) == str(card.get("sar_frame")) and str(row.get("sar_gt_id")) == str(card.get("gt_id")):
                return str(row.get("sar_pseudocolor_path", "")), gt_box_from_accounting(row)
    for row in corr_rows:
        if (
            str(row.get("scene")) == str(card.get("scene"))
            and str(row.get("sar_frame")) == str(card.get("sar_frame"))
            and str(row.get("object_hypothesis_id")) == str(card.get("object_hypothesis_id"))
        ):
            path = ""
            # Use the 442 accounting table for the actual image path.
            for gt in gt_rows:
                if str(gt.get("scene")) == str(row.get("scene")) and str(gt.get("sar_frame")) == str(row.get("sar_frame")) and str(gt.get("sar_gt_id")) == str(row.get("sar_gt_id")):
                    path = str(gt.get("sar_pseudocolor_path", ""))
                    break
            return path, gt_box_from_correspondence(row)
    return "", None


def draw_panel(image_path: str, box: Mapping[str, float] | None, card: Mapping[str, Any], output_path: Path) -> bool:
    path = Path(str(image_path or ""))
    if not path.exists():
        return False
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
    except OSError:
        return False
    max_w = 820
    scale = min(1.0, max_w / image.width)
    panel = image.resize((int(image.width * scale), int(image.height * scale)))
    draw = ImageDraw.Draw(panel)
    if box and box_available(box):
        pts = [(x * scale, y * scale) for x, y in rotated_corners(box)]
        draw.line(pts + [pts[0]], fill=(255, 220, 80), width=max(2, int(3 * scale)))
    title = f"{card.get('category', '')} | {card.get('scene', '')} sar={card.get('sar_frame', '')}"
    draw.rectangle((0, 0, panel.width, 34), fill=(0, 0, 0))
    draw.text((8, 8), title[:120], fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.save(output_path)
    return True


def generate_visual_outputs(
    cards: list[dict[str, Any]],
    gt_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    timestamp: str,
) -> tuple[str, int]:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0
    html_cards: list[str] = []
    for idx, card in enumerate(cards, start=1):
        image_path, box = source_for_card(card, gt_rows, corr_rows)
        panel_name = (
            f"{idx:02d}_{sanitize(card.get('category'))}_"
            f"{sanitize(card.get('case_id'))}_structure_panel.png"
        )
        panel_path = VISUAL_DIR / panel_name
        if draw_panel(image_path, box, card, panel_path):
            card["image_path_if_generated"] = str(panel_path)
            generated += 1
            image_html = f'<img src="{html.escape(panel_name)}" alt="{html.escape(str(card.get("case_id", "")))}" />'
        else:
            image_html = "<p><strong>image unavailable for this card</strong></p>"
        html_cards.append(
            "<article>"
            f"<h2>{idx}. {html.escape(str(card.get('category', '')))}</h2>"
            f"<p><code>{html.escape(str(card.get('case_id', '')))}</code></p>"
            f"{image_html}"
            f"<p><strong>Look for:</strong> {html.escape(str(card.get('what_human_should_look_for', '')))}</p>"
            f"<p><strong>Question:</strong> {html.escape(str(card.get('mechanism_question', '')))}</p>"
            "</article>"
        )
    atlas_path = VISUAL_DIR / f"oty2_sar_vehicle_structure_mechanism_atlas_{timestamp}.html"
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<meta charset="utf-8">',
            "<title>OTY2 SAR Vehicle Structure Mechanism Atlas</title>",
            "<style>body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f7;color:#111}article{background:white;border:1px solid #ccc;margin:0 0 18px;padding:14px;max-width:900px}img{max-width:100%;height:auto;display:block}code{font-size:12px}</style>",
            "<h1>OTY2 SAR Vehicle Structure Mechanism Atlas</h1>",
            "<p>Review-only visual cards. Yellow polygons are posthoc SAR GT references, not proposed annotations.</p>",
            *html_cards,
        ]
    )
    atlas_path.write_text(html_text + "\n", encoding="utf-8")
    return str(atlas_path), generated


def build_mechanism_forms() -> list[dict[str, Any]]:
    return [
        {
            "form_name": "rule / grammar form",
            "mechanism_claim": "vehicle structure is an allowed primitive composition under optical state and SAR temporal stability",
            "evidence_used": "primitive catalog; composition hypotheses; optical-conditioned table",
            "runtime_safe_inputs": "optical object stream; state; time; azimuth; vehicle shell",
            "sar_observation_inputs": "primitive type; spread; intensity relation; tube label",
            "posthoc_validation_inputs": "GT relation only for validation",
            "what_it_explains": "compact vs multi-peak vs spread vs diffuse semantics",
            "what_it_fails_to_explain": "wrong-frame persistence without motion gate",
            "risk_of_local_optimum": "low if kept grammar-like; high if turned into hand-tuned classes",
            "risk_of_leakage": "medium through GT-selected exemplars",
            "next_probe_needed": "visual exemplar review",
        },
        {
            "form_name": "graph form",
            "mechanism_claim": "vehicle is a connected SAR primitive subgraph compatible with optical support and temporal tube",
            "evidence_used": "graph proxy; wrong-object crosscheck",
            "runtime_safe_inputs": "support region and optical object hypothesis",
            "sar_observation_inputs": "primitive graph nodes and competing components",
            "posthoc_validation_inputs": "wrong-object/wrong-frame controls",
            "what_it_explains": "multiple competing structures and neighbor overlap",
            "what_it_fails_to_explain": "true physical identity without review",
            "risk_of_local_optimum": "medium if graph is just a descriptor table",
            "risk_of_leakage": "medium",
            "next_probe_needed": "component-level visual and temporal linking",
        },
        {
            "form_name": "energy-field form",
            "mechanism_claim": "vehicle is high structure concentration in feasible region with low competing components",
            "evidence_used": "primitive intensity relation; graph fragmentation",
            "runtime_safe_inputs": "feasible support only",
            "sar_observation_inputs": "intensity concentration and background relation",
            "posthoc_validation_inputs": "GT support membership",
            "what_it_explains": "diffuse/reject versus concentrated cases",
            "what_it_fails_to_explain": "object identity in crowded same-scene supports",
            "risk_of_local_optimum": "high if optimized as a scalar score",
            "risk_of_leakage": "medium",
            "next_probe_needed": "do not choose weights; compare failure families",
        },
        {
            "form_name": "contrastive form",
            "mechanism_claim": "true support should separate from random/range-shift while wrong-object/wrong-frame reveal confounding",
            "evidence_used": "counterfactual crosscheck",
            "runtime_safe_inputs": "control support construction",
            "sar_observation_inputs": "structure type in each control",
            "posthoc_validation_inputs": "GT-near/top-k rates",
            "what_it_explains": "real range/state signal and object-time confounding",
            "what_it_fails_to_explain": "exact association decision",
            "risk_of_local_optimum": "low if used for falsification",
            "risk_of_leakage": "high if GT-near becomes runtime rule",
            "next_probe_needed": "overlap-aware negative controls",
        },
        {
            "form_name": "temporal-form",
            "mechanism_claim": "vehicle is a structure tube with plausible drift, not a single-frame peak",
            "evidence_used": "temporal tube probe",
            "runtime_safe_inputs": "software-sync temporal window",
            "sar_observation_inputs": "tube persistence and drift proxy",
            "posthoc_validation_inputs": "wrong-frame confounder",
            "what_it_explains": "stable vehicle-like versus background persistence",
            "what_it_fails_to_explain": "drift compatibility is incomplete",
            "risk_of_local_optimum": "medium if persistence alone is rewarded",
            "risk_of_leakage": "medium",
            "next_probe_needed": "range/azimuth drift and optical motion compatibility",
        },
        {
            "form_name": "review-gated form",
            "mechanism_claim": "vehicle-like but object-time ambiguous cases should become review_required, not association",
            "evidence_used": "visual review cards; failure index",
            "runtime_safe_inputs": "optical object state and tracklet quality",
            "sar_observation_inputs": "SAR structure card",
            "posthoc_validation_inputs": "GT overlay for review only",
            "what_it_explains": "why visual review is needed before identity claims",
            "what_it_fails_to_explain": "automatic scale expansion",
            "risk_of_local_optimum": "low",
            "risk_of_leakage": "medium if review anchor becomes runtime truth",
            "next_probe_needed": "GM_RM019 optical continuity review",
        },
        {
            "form_name": "weighted evidence form",
            "mechanism_claim": "normalized evidence combination can summarize diagnostics",
            "evidence_used": "all tables, diagnostic only",
            "runtime_safe_inputs": "none beyond existing support factors",
            "sar_observation_inputs": "all SAR observations as unweighted evidence",
            "posthoc_validation_inputs": "GT validation columns",
            "what_it_explains": "rough diagnostic bookkeeping",
            "what_it_fails_to_explain": "primitive composition, graph competition, and identity confounding",
            "risk_of_local_optimum": "high; it can become a hidden selector",
            "risk_of_leakage": "high if weights are chosen by GT outcomes",
            "next_probe_needed": "keep minor; do not select best weights",
        },
    ]


def render_plan_doc(path: Path, timestamp: str, sources: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 SAR Vehicle Structure Mechanism Beyond Weighted Fusion Plan",
        "",
        f"Updated: {timestamp}",
        "",
        "This plan defines a divergent OTY2 mechanism exploration. It is not OTY3, not an automatic annotation proposal, not selector/ranking, not training, not threshold tuning, and not identity truth.",
        "",
        "## Purpose",
        "",
        "The current question is how vehicle-like SAR evidence is represented inside a still-large optical-derived support region. Weighted evidence fusion is treated as a small diagnostic form, not the main line.",
        "",
        "## Representation Lines",
        "",
        "- 442 SAR GT reference / fallback fan valid-mask audit.",
        "- SAR structure primitives from SAR-side GT/reference patches.",
        "- Structure composition hypotheses that do not output final boxes.",
        "- Primitive graph probes for competing components and confounders.",
        "- Temporal tube probes that split vehicle-like persistence from background persistence.",
        "- Optical-conditioned structure expectations.",
        "- Visual review cards and atlas for human mechanism inspection.",
        "",
        "## Fixed Boundaries",
        "",
        "- 215 paired rows are frame-level posthoc pairs, not all GT and not identity truth.",
        "- 195 GM_RM011 rows are waiting for object stream recovery, not unannotated.",
        "- 20 SAR-only rows are morphology references only.",
        "- 12 dropout/no-match rows are temporal continuation/existence support only.",
        "- SAR GT and SAR image observations may validate/posthoc-observe structure, but must not construct runtime optical priors.",
        "",
        "## Inputs",
        "",
    ]
    for name, source in sources.items():
        lines.append(f"- {name}: `{source}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 SAR Vehicle Structure Mechanism Beyond Weighted Fusion Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report explores SAR vehicle structure as primitives, compositions, graph proxies, temporal tubes, optical-conditioned hypotheses, and visual-review cards. It does not generate annotation proposals, final boxes, selector/ranking outputs, trained models, tuned thresholds, best weights, or identity truth.",
        "",
        "## Ledger Boundary",
        "",
        "- 442 = all SAR GT / SAR-side target reference pool",
        "- 215 = current frame-level posthoc optical-SAR paired subset",
        "- 195 = GM_RM011 blocked_missing_object_stream",
        "- 20 = SAR-only morphology reference",
        "- 12 = dropout/no-match temporal continuation special pool",
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in summary["key_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Required Answers", ""])
    for idx, answer in enumerate(summary["required_answers"], start=1):
        lines.append(f"{idx}. {answer}")
    lines.extend(["", "## Mechanism Forms Beyond Weighted Fusion", ""])
    for form in summary["mechanism_forms"]:
        lines.append(f"- `{form['form_name']}`: {form['mechanism_claim']} It explains {form['what_it_explains']}; limitation: {form['what_it_fails_to_explain']}; local-optimum risk: {form['risk_of_local_optimum']}.")
    lines.extend(
        [
            "",
            "## Why This Is Not A Local Statistical / Weighted-Fusion Optimum",
            "",
            "1. No training, threshold tuning, or best-weight selection is performed.",
            "2. No final box, ranking, or selector output is emitted.",
            "3. The main outputs are primitive, composition, graph, tube, optical-conditioned, failure, and review-card mechanisms, not only descriptors.",
            "4. Top-k near-GT, GT-inside support, peak/background, and association counts can mislead if they are treated as runtime capability.",
            "5. Graph, temporal tube, and optical-conditioned grammar forms have cross-scene/frame/object potential, but only after visual and motion validation.",
            "6. Compact, multi-peak, spread, diffuse, wrong-frame, wrong-object, and boundary cases require human visual review.",
            "7. Next work should inspect visual exemplars and add motion/overlap gates, not continue stacking scalar metrics.",
            "8. Best-weight search and top-k metric tuning should remain paused because they would hide object-time confounding.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for name, output_path in summary["outputs"].items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(["", "## Sources", ""])
    for name, source_path in summary["sources"].items():
        lines.append(f"- {name}: `{source_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        "selector_or_ranking_used=false",
        "best_weight_selected=false",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def summarize_required_answers(summary: Mapping[str, Any]) -> list[str]:
    metrics = summary["key_metrics"]
    return [
        f"442 SAR GT valid-mask audit: full_inside={metrics['gt_full_inside_fallback_fan_mask']}, partial_overlap={metrics['gt_partial_overlap_fallback_fan_mask']}, near_boundary={metrics['gt_near_mask_boundary']}, unable_to_judge={metrics['gt_mask_unable_to_judge']}. The mask source is fallback fan valid region; no external mask file was found.",
        f"442 pool split: paired={metrics['pool_paired_215']}, GM_RM011 waiting={metrics['pool_gm011_blocked']}, SAR-only={metrics['pool_sar_only']}, dropout special={metrics['pool_dropout_special']}, unknown={metrics['pool_unknown']}. Only paired rows can enter optical-SAR correspondence.",
        "The previous 215 paired rows have SAR structure but unique isolation remains zero because peak competition, spread structures, and multi-component graph proxies prevent a single isolated structure from being claimed.",
        "Primitives improve on top-k by naming compact blobs, peak pairs/groups, range/azimuth ridges, boundary-affected proxies, and clutter patches instead of selecting the brightest point.",
        "Composition hypotheses separate compact, multi-peak, range-spread, azimuth-spread, stable-tube, and reject forms without emitting final boxes.",
        f"Graph probes show competing/multi-component structure in {metrics['graph_multi_component_rate']} of paired cases, explaining why support regions are not unique structures.",
        "Temporal tube probing separates vehicle-like drifting-tube candidates from stable-background risk, jumping peaks, diffuse tubes, and dropout existence-only tubes; wrong-frame confounding remains a blocker.",
        "Optical-conditioned hypotheses explain how truncation, edge contact, identity ambiguity, scale, tracklet smoothing, and azimuth trend should change expected SAR structure rather than directly set a box.",
        "Weighted evidence is retained only as a diagnostic bookkeeping form; it cannot be the main line because it fails to explain primitive composition, graph competition, and identity confounding.",
        "Most promising next forms are graph, temporal-form, rule/grammar composition, and review-gated form.",
        f"Visual review is required for {metrics['visual_review_card_count']} candidate-card categories; the atlas generation status is {metrics['visual_atlas_generated']}.",
        "GM_RM019 optical continuity review is still needed as a small quality anchor for object hypothesis continuity.",
        "GM_RM011 recovery should remain deferred as scale expansion until this mechanism line is visually and temporally checked.",
        "A short stage recap or follow-up branch is reasonable after visual exemplar review; this still should not become OTY3 automatic annotation.",
    ]


def build_summary(
    timestamp: str,
    gt_audit_rows: Sequence[Mapping[str, Any]],
    primitive_rows: Sequence[Mapping[str, Any]],
    composition_rows: Sequence[Mapping[str, Any]],
    graph_rows: Sequence[Mapping[str, Any]],
    tube_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    card_rows: Sequence[Mapping[str, Any]],
    mechanism_forms: Sequence[Mapping[str, Any]],
    atlas_path: str,
    generated_panels: int,
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    pool_counts = Counter(row.get("pool_type", "") for row in gt_audit_rows)
    primitive_counts = Counter(row.get("primitive_type", "") for row in primitive_rows)
    composition_counts = Counter(row.get("composition_type", "") for row in composition_rows)
    graph_multi = sum(1 for row in graph_rows if str(row.get("graph_fragmentation_level", "")) != "low_single_component")
    tube_counts = Counter(row.get("tube_type", "") for row in tube_rows)
    image_available = sum(1 for row in gt_audit_rows if row.get("image_available") == "true")
    full_inside = sum(1 for row in gt_audit_rows if row.get("full_inside_sar_valid_mask") == "true")
    partial = sum(
        1
        for row in gt_audit_rows
        if row.get("mask_overlap_ratio") not in {"", "1", "1.0", "1.0000"} and safe_float(row.get("mask_overlap_ratio")) not in (None, 0.0)
    )
    near = sum(1 for row in gt_audit_rows if row.get("near_mask_boundary") == "true")
    unable = sum(1 for row in gt_audit_rows if row.get("mask_overlap_ratio") == "")
    key_metrics = {
        "gt_total": len(gt_audit_rows),
        "gt_image_available": image_available,
        "gt_full_inside_fallback_fan_mask": full_inside,
        "gt_partial_overlap_fallback_fan_mask": partial,
        "gt_near_mask_boundary": near,
        "gt_mask_unable_to_judge": unable,
        "pool_paired_215": pool_counts.get(PAIRED_POOL, 0),
        "pool_gm011_blocked": pool_counts.get("gm011_blocked", 0),
        "pool_sar_only": pool_counts.get("sar_only", 0),
        "pool_dropout_special": pool_counts.get("dropout_special", 0),
        "pool_unknown": pool_counts.get("unknown", 0),
        "primitive_catalog_rows": len(primitive_rows),
        "primitive_type_mix": compact_counts(row.get("primitive_type", "") for row in primitive_rows),
        "composition_rows": len(composition_rows),
        "composition_type_mix": compact_counts(row.get("composition_type", "") for row in composition_rows),
        "graph_rows": len(graph_rows),
        "graph_multi_component_rate": rate(graph_multi, len(graph_rows)),
        "tube_rows": len(tube_rows),
        "tube_type_mix": compact_counts(row.get("tube_type", "") for row in tube_rows),
        "optical_condition_rows": len(optical_rows),
        "failure_case_index_rows": len(failure_rows),
        "visual_review_card_count": len(card_rows),
        "visual_panels_generated": generated_panels,
        "visual_atlas_generated": "yes" if atlas_path else "no",
    }
    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "sample_ledger": {"ledger_valid": True, "category_counts": EXPECTED_LEDGER},
        "key_metrics": key_metrics,
        "primitive_counts": dict(primitive_counts),
        "composition_counts": dict(composition_counts),
        "tube_counts": dict(tube_counts),
        "mechanism_forms": list(mechanism_forms),
        "visual_atlas_path": atlas_path,
        "posthoc_hypotheses_only": [
            "GT polygon overlays and valid-mask relations are SAR-side reference/posthoc validation.",
            "Primitive and composition types are mechanism hypotheses, not selector features.",
            "Graph and tube labels are review aids, not final labels.",
            "Weighted evidence is diagnostic only; no best weights are selected.",
        ],
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }
    summary["required_answers"] = summarize_required_answers(summary)
    return summary


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "gt_accounting_csv": Path(args.gt_accounting_csv) if args.gt_accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "support_observation_csv": Path(args.support_observation_csv) if args.support_observation_csv else latest_path("oty2_support_region_structure_observation_*.csv"),
        "structure_crosscheck_csv": Path(args.structure_crosscheck_csv) if args.structure_crosscheck_csv else latest_path("oty2_structure_counterfactual_crosscheck_*.csv"),
        "temporal_tube_csv": Path(args.temporal_tube_csv) if args.temporal_tube_csv else latest_path("oty2_structure_temporal_tube_probe_*.csv"),
        "provenance_summary_json": Path(args.provenance_summary_json) if args.provenance_summary_json else latest_path("oty2_sar_structure_representation_and_association_provenance_summary_*.json"),
    }
    gt_rows = read_csv(paths["gt_accounting_csv"])
    if len(gt_rows) != 442:
        raise RuntimeError(f"Expected 442 GT accounting rows; got {len(gt_rows)}")
    pool_counts = Counter(pool_type(row) for row in gt_rows)
    expected_pool_counts = {PAIRED_POOL: 215, "gm011_blocked": 195, "sar_only": 20, "dropout_special": 12}
    for key, expected in expected_pool_counts.items():
        if pool_counts.get(key, 0) != expected:
            raise RuntimeError(f"Ledger mismatch for {key}: expected {expected}, got {pool_counts.get(key, 0)}")
    summary = json.loads(paths["provenance_summary_json"].read_text(encoding="utf-8"))
    ledger = summary.get("sample_ledger", {}).get("category_counts", {})
    if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
        raise RuntimeError(f"Provenance summary ledger changed: {json.dumps(ledger, ensure_ascii=False)}")
    return {
        "paths": paths,
        "gt_rows": gt_rows,
        "corr_rows": read_csv(paths["correspondence_csv"]),
        "support_rows": read_csv(paths["support_observation_csv"]),
        "crosscheck_rows": read_csv(paths["structure_crosscheck_csv"]),
        "temporal_rows": read_csv(paths["temporal_tube_csv"]),
        "provenance_summary": summary,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    sources = {name: str(path) for name, path in inputs["paths"].items()}
    cache = ImageCache()

    gt_audit_rows = build_gt_reference_audit(inputs["gt_rows"])
    primitive_rows = build_primitives(inputs["gt_rows"], gt_audit_rows, cache)
    composition_rows = build_compositions(inputs["support_rows"], inputs["corr_rows"], primitive_rows)
    graph_rows = build_graph_rows(inputs["support_rows"], inputs["crosscheck_rows"])
    tube_rows = build_tube_rows(inputs["temporal_rows"], inputs["provenance_summary"])
    optical_rows = build_optical_condition_rows(inputs["support_rows"], inputs["corr_rows"])
    failure_rows = build_failure_index(inputs["support_rows"], graph_rows, inputs["crosscheck_rows"])
    card_rows = build_visual_cards(inputs["support_rows"], gt_audit_rows, inputs["corr_rows"])
    mechanism_forms = build_mechanism_forms()

    atlas_path, generated_panels = generate_visual_outputs(card_rows, inputs["gt_rows"], inputs["corr_rows"], timestamp)

    plan_doc = DOCS_DIR / "oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_plan.md"
    gt_audit_csv = REPORT_DIR / f"oty2_sar_gt_reference_mask_audit_{timestamp}.csv"
    primitive_csv = REPORT_DIR / f"oty2_sar_structure_primitive_catalog_{timestamp}.csv"
    composition_csv = REPORT_DIR / f"oty2_sar_structure_composition_hypotheses_{timestamp}.csv"
    graph_csv = REPORT_DIR / f"oty2_sar_structure_graph_probe_{timestamp}.csv"
    tube_csv = REPORT_DIR / f"oty2_sar_temporal_tube_mechanism_probe_{timestamp}.csv"
    optical_csv = REPORT_DIR / f"oty2_optical_conditioned_structure_hypotheses_{timestamp}.csv"
    failure_csv = REPORT_DIR / f"oty2_mechanism_failure_case_index_{timestamp}.csv"
    cards_csv = REPORT_DIR / f"oty2_visual_review_candidate_cards_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_summary_{timestamp}.json"
    outputs = {
        "plan_doc": str(plan_doc),
        "sar_gt_reference_mask_audit_csv": str(gt_audit_csv),
        "sar_structure_primitive_catalog_csv": str(primitive_csv),
        "sar_structure_composition_hypotheses_csv": str(composition_csv),
        "sar_structure_graph_probe_csv": str(graph_csv),
        "sar_temporal_tube_mechanism_probe_csv": str(tube_csv),
        "optical_conditioned_structure_hypotheses_csv": str(optical_csv),
        "mechanism_failure_case_index_csv": str(failure_csv),
        "visual_review_candidate_cards_csv": str(cards_csv),
        "sar_vehicle_structure_mechanism_beyond_weighted_fusion_report_md": str(report_md),
        "sar_vehicle_structure_mechanism_beyond_weighted_fusion_summary_json": str(summary_json),
        "visual_atlas_html": atlas_path,
    }
    summary = build_summary(
        timestamp,
        gt_audit_rows,
        primitive_rows,
        composition_rows,
        graph_rows,
        tube_rows,
        optical_rows,
        failure_rows,
        card_rows,
        mechanism_forms,
        atlas_path,
        generated_panels,
        sources,
        outputs,
    )
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    render_plan_doc(plan_doc, timestamp, sources)
    write_csv(gt_audit_csv, gt_audit_rows, GT_AUDIT_FIELDS)
    write_csv(primitive_csv, primitive_rows, PRIMITIVE_FIELDS)
    write_csv(composition_csv, composition_rows, COMPOSITION_FIELDS)
    write_csv(graph_csv, graph_rows, GRAPH_FIELDS)
    write_csv(tube_csv, tube_rows, TUBE_FIELDS)
    write_csv(optical_csv, optical_rows, OPTICAL_FIELDS)
    write_csv(failure_csv, failure_rows, FAILURE_FIELDS)
    write_csv(cards_csv, card_rows, CARD_FIELDS)
    render_report(report_md, summary)
    write_json(summary_json, summary)

    print(
        json.dumps(
            {
                "outputs": summary["outputs"],
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
    parser.add_argument("--gt-accounting-csv", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--support-observation-csv", default="")
    parser.add_argument("--structure-crosscheck-csv", default="")
    parser.add_argument("--temporal-tube-csv", default="")
    parser.add_argument("--provenance-summary-json", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
