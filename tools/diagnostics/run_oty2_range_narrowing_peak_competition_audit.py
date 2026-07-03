"""OTY2 range narrowing and peak competition audit.

This diagnostic starts from the OTY2 optical-derived broad fan support regions
and audits whether posthoc range-band hypotheses can reduce the broad unknown
range prior while preserving GT coverage. It also measures peak competition
inside each support region.

The outputs are SAR observation diagnostics. They are not final boxes,
annotation proposals, selector/ranking outputs, training products, tuned
thresholds, or identity-truth claims. SAR GT and SAR image evidence are used
only for posthoc validation and SAR observation extraction, not for runtime
prior construction.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from run_oty2_support_region_sar_observation_probe import (
    DOCS_DIR,
    FAN_CENTER_X,
    FAN_CENTER_Y,
    FAN_RADIUS_PX,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    SarImageCache,
    bool_text,
    compact_counts,
    fmt,
    latest_path,
    mean_clean,
    median_clean,
    point_from_polar,
    read_csv,
    safe_float,
    safe_int,
    sar_path,
    short_window_frames,
    slope,
    write_csv,
    write_json,
)


EXPECTED_LEDGER = {
    "paired_optical_object_sar_gt": 215,
    "blocked_missing_gm011_object_stream": 195,
    "sar_only_gt": 20,
    "no_oty_iou_match": 12,
}

# Peak diagnostics are not final localization. A stride keeps the audit fast
# enough while preserving original-pixel coordinates for trend comparisons.
EXTRACTION_STRIDE = 3

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "posthoc_shape_radius_relation_used_for_hypothesis_audit": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "sar_gt_residual_written_to_runtime_prior": False,
    "support_region_uses_gt_crop": False,
    "annotation_proposal_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "matlab_zip_or_any_zip_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
}

MODE_FIELDS = [
    "mode_name",
    "mode_family",
    "mode_boundary",
    "n_rows",
    "n_paired_rows",
    "n_clean_complete_rows",
    "n_dropout_rows",
    "selected_shape_feature",
    "gt_coverage_rate_paired_posthoc",
    "gt_coverage_rate_clean_complete_posthoc",
    "median_radius_band_width_px",
    "median_support_area_px",
    "median_area_ratio_vs_broad",
    "median_peak_to_background_ratio",
    "median_top1_top2_ratio",
    "median_top2_to_background_ratio",
    "median_local_peak_count_above_bg_p95",
    "peak_competition_serious_rate",
    "short_window_peak_persistence_rate",
    "tube_peak_continuity_rate",
    "interpretation",
    "provenance_labels",
]

PEAK_FIELDS = [
    "peak_audit_id",
    "mode_name",
    "relationship_type",
    "sample_pool",
    "clean_morphology_inclusion",
    "scene",
    "object_hypothesis_id",
    "state_condition",
    "optical_frame",
    "sar_frame",
    "support_azimuth_start_deg",
    "support_azimuth_end_deg",
    "support_radius_min_px",
    "support_radius_max_px",
    "radius_band_width_px",
    "range_band_source",
    "support_area_px",
    "area_ratio_vs_broad",
    "gt_radius_px_posthoc",
    "gt_azimuth_deg_posthoc",
    "gt_inside_support_posthoc",
    "gt_radius_inside_posthoc",
    "top1_peak_value",
    "top2_peak_value",
    "top1_top2_ratio",
    "top1_background_ratio",
    "top2_background_ratio",
    "top1_x",
    "top1_y",
    "top2_x",
    "top2_y",
    "top1_top2_distance_px",
    "local_peak_count_above_bg_p95",
    "scatter_centroid_x",
    "scatter_centroid_y",
    "centroid_residual_px",
    "short_window_frames",
    "short_window_observed_frames",
    "short_window_top1_persistence_rate",
    "short_window_peak_persistence_label",
    "tube_peak_continuity_label",
    "peak_competition_label",
    "sar_image_path",
    "notes",
    "provenance_labels",
]

STATE_FIELDS = [
    "state_condition",
    "mode_name",
    "sample_pool",
    "n_rows",
    "gt_coverage_rate_posthoc",
    "median_radius_band_width_px",
    "median_support_area_px",
    "median_area_ratio_vs_broad",
    "median_peak_to_background_ratio",
    "median_top1_top2_ratio",
    "peak_competition_serious_rate",
    "recommended_range_band_treatment",
    "notes",
]

OBJECT_FIELDS = [
    "object_probe_id",
    "mode_name",
    "scene",
    "object_hypothesis_id",
    "sample_pool",
    "state_mix",
    "n_rows",
    "optical_frame_span",
    "sar_frame_span",
    "gt_coverage_rate_posthoc",
    "median_radius_band_width_px",
    "median_support_area_px",
    "median_peak_to_background_ratio",
    "median_top1_top2_ratio",
    "peak_continuity_step_mean_px",
    "centroid_continuity_step_mean_px",
    "tube_peak_continuity_label",
    "optical_height_vs_gt_radius_slope_posthoc",
    "optical_bottom_y_vs_gt_radius_slope_posthoc",
    "optical_area_vs_gt_radius_slope_posthoc",
    "manual_review_need",
    "notes",
    "provenance_labels",
]

TUBE_FIELDS = [
    "tube_probe_id",
    "mode_name",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "state_mix",
    "n_rows",
    "sar_frame_span",
    "gt_coverage_rate_posthoc",
    "median_radius_band_width_px",
    "median_peak_to_background_ratio",
    "median_top1_top2_ratio",
    "peak_continuity_step_mean_px",
    "centroid_continuity_step_mean_px",
    "tube_peak_continuity_label",
    "notes",
    "provenance_labels",
]


def as_float_list(values: Iterable[Any]) -> list[float]:
    clean: list[float] = []
    for value in values:
        number = safe_float(value)
        if number is not None and math.isfinite(number):
            clean.append(float(number))
    return clean


def quantile(values: Iterable[Any], q: float) -> float | None:
    clean = sorted(as_float_list(values))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    q = max(0.0, min(1.0, q))
    pos = q * (len(clean) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return clean[lo]
    alpha = pos - lo
    return clean[lo] * (1.0 - alpha) + clean[hi] * alpha


def rate(num: int, den: int) -> str:
    return fmt(num / den if den else None, 4)


def parse_metric_blob(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for part in str(text or "").replace(",", ";").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        number = safe_float(value)
        if number is not None:
            result[key.strip()] = float(number)
    return result


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 3:
        return None
    mx = sum(x for x, _ in pairs) / len(pairs)
    my = sum(y for _, y in pairs) / len(pairs)
    vx = sum((x - mx) ** 2 for x, _ in pairs)
    vy = sum((y - my) ** 2 for _, y in pairs)
    if vx <= 1e-12 or vy <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / math.sqrt(vx * vy)


def parse_center(text: str) -> tuple[float, float] | None:
    parts = [safe_float(part) for part in str(text or "").split(",")]
    if len(parts) < 2 or parts[0] is None or parts[1] is None:
        return None
    return float(parts[0]), float(parts[1])


def point_to_radius_px(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


def point_to_azimuth_deg(x: float, y: float) -> float:
    return math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))


def key_for_row(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("sar_frame_probe", row.get("sar_frame", ""))),
    )


def state_min_halfwidth(state: str) -> float:
    return {
        "complete": 65.0,
        "edge_or_truncated": 145.0,
        "duplicate_or_handoff": 180.0,
        "ambiguous_or_review_only": 165.0,
        "far_small_or_weak": 210.0,
        "dropout_or_no_match": 260.0,
    }.get(state, 170.0)


def state_treatment(state: str) -> str:
    return {
        "complete": "narrowest band allowed, but still posthoc until runtime-safe range geometry is available",
        "edge_or_truncated": "widen range band; optical box shape is partial and should not hard-localize range",
        "duplicate_or_handoff": "widen range band and require object-continuity review; no identity truth claim",
        "ambiguous_or_review_only": "keep review-conditioned wider band; use as hypothesis evidence only",
        "far_small_or_weak": "use broad or separately calibrated weak range band; shape cue is fragile",
        "dropout_or_no_match": "exclude from clean morphology; use temporal continuation plus SAR support only",
    }.get(state, "state-conditioned widening required")


def clamp_band(center: float, halfwidth: float) -> tuple[float, float]:
    radius_min = max(0.0, center - halfwidth)
    radius_max = min(FAN_RADIUS_PX, center + halfwidth)
    if radius_max <= radius_min:
        radius_max = min(FAN_RADIUS_PX, radius_min + 20.0)
    return radius_min, radius_max


def support_from_frame_row(
    frame_row: Mapping[str, Any],
    mode_name: str,
    radius_min: float,
    radius_max: float,
    source: str,
) -> dict[str, Any]:
    az_start = safe_float(frame_row.get("support_azimuth_start_deg"), -89.0) or -89.0
    az_end = safe_float(frame_row.get("support_azimuth_end_deg"), 89.0) or 89.0
    az_center = (az_start + az_end) / 2.0
    radius_center = (radius_min + radius_max) / 2.0
    center_x, center_y = point_from_polar(radius_center, az_center)
    return {
        "mode_name": mode_name,
        "support_azimuth_start_deg": az_start,
        "support_azimuth_end_deg": az_end,
        "support_radius_min_px": radius_min,
        "support_radius_max_px": radius_max,
        "support_center_x": center_x,
        "support_center_y": center_y,
        "range_band_source": source,
    }


def support_from_broad(frame_row: Mapping[str, Any]) -> dict[str, Any]:
    radius_min = safe_float(frame_row.get("support_radius_min_px"), 0.0) or 0.0
    radius_max = safe_float(frame_row.get("support_radius_max_px"), FAN_RADIUS_PX) or FAN_RADIUS_PX
    return support_from_frame_row(frame_row, "broad_fan_baseline", radius_min, radius_max, "previous_broad_unknown_range_prior")


def gt_inside(row: Mapping[str, Any], support: Mapping[str, Any]) -> tuple[bool | None, bool | None]:
    gt_radius = safe_float(row.get("gt_radius_px_posthoc"))
    gt_az = safe_float(row.get("gt_azimuth_deg_posthoc"))
    if gt_radius is None or gt_az is None:
        return None, None
    az_ok = float(support["support_azimuth_start_deg"]) <= gt_az <= float(support["support_azimuth_end_deg"])
    radius_ok = float(support["support_radius_min_px"]) <= gt_radius <= float(support["support_radius_max_px"])
    return az_ok and radius_ok, radius_ok


def normalize_frame_rows(frame_rows: Sequence[Mapping[str, Any]], corr_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    corr_by_key = {
        (row.get("scene", ""), row.get("object_hypothesis_id", ""), row.get("optical_frame", ""), row.get("sar_frame", "")): row
        for row in corr_rows
    }
    normalized: list[dict[str, Any]] = []
    for row in frame_rows:
        item = dict(row)
        corr = corr_by_key.get(key_for_row(row), {})
        metrics = parse_metric_blob(str(corr.get("optical_bbox_width_height_area", "")))
        item["bbox_width_px"] = metrics.get("w", "")
        item["bbox_height_px"] = metrics.get("h", "")
        item["bbox_area_px"] = metrics.get("area", "")
        item["bbox_bottom_y"] = safe_float(corr.get("optical_bbox_bottom_y"))
        item["gt_radius_px_posthoc"] = safe_float(corr.get("sar_gt_radius_px"))
        item["gt_azimuth_deg_posthoc"] = safe_float(corr.get("sar_gt_azimuth_deg"))
        center = parse_center(str(corr.get("sar_gt_center", "")))
        if center and item["gt_radius_px_posthoc"] is None:
            item["gt_radius_px_posthoc"] = point_to_radius_px(center[0], center[1])
        if center and item["gt_azimuth_deg_posthoc"] is None:
            item["gt_azimuth_deg_posthoc"] = point_to_azimuth_deg(center[0], center[1])
        item["has_shape_radius_posthoc_pair"] = bool_text(
            item.get("sample_pool") == "paired_optical_object_sar_gt"
            and item["gt_radius_px_posthoc"] is not None
            and safe_float(item.get("bbox_height_px")) is not None
        )
        normalized.append(item)
    return normalized


def select_shape_feature(rows: Sequence[Mapping[str, Any]]) -> tuple[str, dict[str, float]]:
    complete = [
        row
        for row in rows
        if row.get("sample_pool") == "paired_optical_object_sar_gt"
        and row.get("state_condition") == "complete"
        and safe_float(row.get("gt_radius_px_posthoc")) is not None
    ]
    candidates = {
        "bbox_height_px": [],
        "bbox_bottom_y": [],
        "bbox_area_px": [],
    }
    radii: dict[str, list[float]] = {key: [] for key in candidates}
    for row in complete:
        radius = safe_float(row.get("gt_radius_px_posthoc"))
        if radius is None:
            continue
        for key in candidates:
            value = safe_float(row.get(key))
            if value is not None:
                candidates[key].append(float(value))
                radii[key].append(float(radius))
    correlations: dict[str, float] = {}
    for key, values in candidates.items():
        corr = pearson(values, radii[key])
        correlations[key] = float(corr) if corr is not None else 0.0
    selected = max(correlations, key=lambda key: abs(correlations[key])) if correlations else "bbox_height_px"
    return selected, correlations


def complete_quantile_band(
    row: Mapping[str, Any],
    complete_rows: Sequence[Mapping[str, Any]],
    feature: str,
    exclude_same_row: bool = True,
) -> dict[str, Any] | None:
    value = safe_float(row.get(feature))
    if value is None:
        return None
    pool = []
    this_key = key_for_row(row)
    for item in complete_rows:
        if exclude_same_row and key_for_row(item) == this_key:
            continue
        item_value = safe_float(item.get(feature))
        item_radius = safe_float(item.get("gt_radius_px_posthoc"))
        if item_value is not None and item_radius is not None:
            pool.append((abs(item_value - value), float(item_radius)))
    if len(pool) < 8:
        return None
    pool.sort(key=lambda item: item[0])
    k = min(len(pool), max(15, math.ceil(len(pool) * 0.25)))
    radii = [radius for _, radius in pool[:k]]
    lo = quantile(radii, 0.10)
    hi = quantile(radii, 0.90)
    center = median(radii)
    if lo is None or hi is None:
        return None
    radius_min = max(0.0, lo - 25.0)
    radius_max = min(FAN_RADIUS_PX, hi + 25.0)
    return {
        "center": center,
        "radius_min": radius_min,
        "radius_max": radius_max,
        "halfwidth": (radius_max - radius_min) / 2.0,
        "source": f"posthoc_complete_shape_quantile_neighborhood;feature={feature};neighbors={k}",
    }


def build_range_context(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selected_feature, correlations = select_shape_feature(rows)
    complete_rows = [
        row
        for row in rows
        if row.get("sample_pool") == "paired_optical_object_sar_gt"
        and row.get("state_condition") == "complete"
        and safe_float(row.get("gt_radius_px_posthoc")) is not None
        and safe_float(row.get(selected_feature)) is not None
    ]
    scene_median = {}
    for scene, group in groupby_key(rows, lambda row: str(row.get("scene", ""))).items():
        scene_median[scene] = median_clean(row.get("gt_radius_px_posthoc") for row in group)
    object_stats: dict[tuple[str, str], dict[str, Any]] = {}
    for key, group in groupby_key(rows, lambda row: (str(row.get("scene", "")), str(row.get("object_hypothesis_id", "")))).items():
        paired = [
            row
            for row in group
            if row.get("sample_pool") == "paired_optical_object_sar_gt" and safe_float(row.get("gt_radius_px_posthoc")) is not None
        ]
        paired.sort(key=lambda row: safe_int(row.get("sar_frame_probe"), 0) or 0)
        frames = [float(safe_int(row.get("sar_frame_probe"), 0) or 0) for row in paired]
        radii = [safe_float(row.get("gt_radius_px_posthoc"), 0.0) or 0.0 for row in paired]
        object_stats[key] = {
            "rows": paired,
            "radius_median": median_clean(radii),
            "radius_slope": slope(frames, radii),
            "abs_residual_q90": None,
        }
        pred = []
        r_slope = object_stats[key]["radius_slope"]
        if len(frames) >= 2 and r_slope is not None:
            mx = sum(frames) / len(frames)
            my = sum(radii) / len(radii)
            for frame, radius in zip(frames, radii):
                pred.append(abs(radius - (my + r_slope * (frame - mx))))
            object_stats[key]["frame_mean"] = mx
            object_stats[key]["radius_mean"] = my
            object_stats[key]["abs_residual_q90"] = quantile(pred, 0.90)
    quantile_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        qband = complete_quantile_band(row, complete_rows, selected_feature)
        if qband:
            quantile_by_key[key_for_row(row)] = qband
    residual_by_scene: dict[str, dict[str, float | None]] = {}
    for scene, group in groupby_key(rows, lambda row: str(row.get("scene", ""))).items():
        residuals = []
        for row in group:
            qband = quantile_by_key.get(key_for_row(row))
            gt_radius = safe_float(row.get("gt_radius_px_posthoc"))
            if qband and gt_radius is not None:
                residuals.append(gt_radius - float(qband["center"]))
        residual_by_scene[scene] = {
            "median_residual": median_clean(residuals),
            "abs_residual_q90": quantile((abs(item) for item in residuals), 0.90),
        }
    return {
        "selected_feature": selected_feature,
        "feature_correlations": correlations,
        "complete_rows": complete_rows,
        "scene_median": scene_median,
        "object_stats": object_stats,
        "quantile_by_key": quantile_by_key,
        "scene_residual_by_scene": residual_by_scene,
    }


def groupby_key(rows: Sequence[Mapping[str, Any]], key_fn: Any) -> dict[Any, list[Mapping[str, Any]]]:
    groups: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[key_fn(row)].append(row)
    return groups


def state_conditioned_band(row: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any] | None:
    state = str(row.get("state_condition", ""))
    qband = context["quantile_by_key"].get(key_for_row(row))
    scene = str(row.get("scene", ""))
    object_key = (scene, str(row.get("object_hypothesis_id", "")))
    obj = context["object_stats"].get(object_key, {})
    center = None
    source_parts = ["posthoc_state_conditioned_range_band"]
    if qband:
        center = float(qband["center"])
        base_halfwidth = max(float(qband["halfwidth"]), state_min_halfwidth(state))
        source_parts.append(str(qband["source"]))
    elif obj.get("radius_median") is not None:
        center = float(obj["radius_median"])
        base_halfwidth = state_min_halfwidth(state) + 45.0
        source_parts.append("object_posthoc_radius_median_fallback")
    elif context["scene_median"].get(scene) is not None:
        center = float(context["scene_median"][scene])
        base_halfwidth = state_min_halfwidth(state) + 85.0
        source_parts.append("scene_posthoc_radius_median_fallback")
    else:
        return None
    if state != "complete":
        base_halfwidth += {
            "edge_or_truncated": 35.0,
            "duplicate_or_handoff": 55.0,
            "ambiguous_or_review_only": 45.0,
            "far_small_or_weak": 65.0,
            "dropout_or_no_match": 90.0,
        }.get(state, 45.0)
    radius_min, radius_max = clamp_band(center, base_halfwidth)
    return {
        "radius_min": radius_min,
        "radius_max": radius_max,
        "source": ";".join(source_parts),
    }


def object_smoothed_band(row: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any] | None:
    if row.get("sample_pool") != "paired_optical_object_sar_gt":
        return None
    scene = str(row.get("scene", ""))
    object_id = str(row.get("object_hypothesis_id", ""))
    obj = context["object_stats"].get((scene, object_id), {})
    object_rows = obj.get("rows") or []
    if len(object_rows) < 2:
        return None
    sar_frame = safe_float(row.get("sar_frame_probe"))
    if sar_frame is None:
        return None
    radius_slope = obj.get("radius_slope")
    center = obj.get("radius_median")
    source = "posthoc_object_smoothed_radius_median"
    if radius_slope is not None and obj.get("frame_mean") is not None and obj.get("radius_mean") is not None:
        trend_center = float(obj["radius_mean"]) + float(radius_slope) * (sar_frame - float(obj["frame_mean"]))
        local_radii = []
        for item in object_rows:
            item_frame = safe_float(item.get("sar_frame_probe"))
            item_radius = safe_float(item.get("gt_radius_px_posthoc"))
            if item_frame is not None and item_radius is not None and abs(item_frame - sar_frame) <= 25.0:
                local_radii.append(item_radius)
        if local_radii:
            center = (trend_center + float(median(local_radii))) / 2.0
            source = "posthoc_object_smoothed_range_trend_plus_local_median"
        else:
            center = trend_center
            source = "posthoc_object_smoothed_range_trend"
    if center is None:
        return None
    residual_q90 = safe_float(obj.get("abs_residual_q90"))
    state = str(row.get("state_condition", ""))
    halfwidth = max(residual_q90 or 0.0, state_min_halfwidth(state))
    if state != "complete":
        halfwidth += 45.0
    radius_min, radius_max = clamp_band(float(center), halfwidth)
    return {
        "radius_min": radius_min,
        "radius_max": radius_max,
        "source": source,
    }


def scene_residual_band(row: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any] | None:
    if row.get("sample_pool") != "paired_optical_object_sar_gt":
        return None
    qband = context["quantile_by_key"].get(key_for_row(row))
    if not qband:
        return None
    scene = str(row.get("scene", ""))
    residual = context["scene_residual_by_scene"].get(scene, {})
    median_residual = safe_float(residual.get("median_residual"), 0.0) or 0.0
    residual_q90 = safe_float(residual.get("abs_residual_q90"), 120.0) or 120.0
    state = str(row.get("state_condition", ""))
    center = float(qband["center"]) + median_residual
    halfwidth = max(residual_q90, state_min_halfwidth(state))
    if state != "complete":
        halfwidth += 45.0
    radius_min, radius_max = clamp_band(center, halfwidth)
    return {
        "radius_min": radius_min,
        "radius_max": radius_max,
        "source": f"posthoc_scene_residual_diagnostic;scene={scene};median_residual={fmt(median_residual, 3)}",
    }


def build_supports_for_row(row: Mapping[str, Any], context: Mapping[str, Any]) -> list[dict[str, Any]]:
    supports = [support_from_broad(row)]
    if row.get("state_condition") == "complete" and row.get("sample_pool") == "paired_optical_object_sar_gt":
        qband = context["quantile_by_key"].get(key_for_row(row))
        if qband:
            supports.append(
                support_from_frame_row(
                    row,
                    "complete_shape_quantile_range_band",
                    float(qband["radius_min"]),
                    float(qband["radius_max"]),
                    str(qband["source"]),
                )
            )
    state_band = state_conditioned_band(row, context)
    if state_band:
        supports.append(
            support_from_frame_row(
                row,
                "state_conditioned_range_band",
                float(state_band["radius_min"]),
                float(state_band["radius_max"]),
                str(state_band["source"]),
            )
        )
    object_band = object_smoothed_band(row, context)
    if object_band:
        supports.append(
            support_from_frame_row(
                row,
                "object_smoothed_range_band",
                float(object_band["radius_min"]),
                float(object_band["radius_max"]),
                str(object_band["source"]),
            )
        )
    scene_band = scene_residual_band(row, context)
    if scene_band:
        supports.append(
            support_from_frame_row(
                row,
                "scene_residual_range_band",
                float(scene_band["radius_min"]),
                float(scene_band["radius_max"]),
                str(scene_band["source"]),
            )
        )
    return supports


def separated_peaks(
    arr: np.ndarray,
    mask: np.ndarray,
    threshold: float,
    k: int = 5,
    min_distance_px: float = 20.0,
    cap: int = 400,
) -> tuple[list[tuple[int, int, float]], int]:
    flat = np.flatnonzero(mask & (arr >= threshold))
    if flat.size == 0:
        flat = np.flatnonzero(mask)
    if flat.size == 0:
        return [], 0
    values = arr.ravel()[flat]
    n_pick = min(flat.size, cap)
    if n_pick < flat.size:
        candidate_pos = np.argpartition(values, -n_pick)[-n_pick:]
        ordered = flat[candidate_pos[np.argsort(values[candidate_pos])[::-1]]]
    else:
        ordered = flat[np.argsort(values)[::-1]]
    peaks: list[tuple[int, int, float]] = []
    all_count = 0
    width = arr.shape[1]
    for idx in ordered:
        y = int(idx // width)
        x = int(idx % width)
        value = float(arr[y, x])
        if all(math.hypot(x - px, y - py) >= min_distance_px for px, py, _ in peaks):
            peaks.append((x, y, value))
            all_count += 1
            if len(peaks) >= max(k, 50):
                break
    return peaks[:k], all_count


def extract_peak_competition(
    cache: SarImageCache,
    scene: str,
    sar_frame: int,
    support: Mapping[str, Any],
    detail: bool = True,
) -> dict[str, Any]:
    image_path = sar_path(scene, sar_frame)
    arr_full = cache.image(image_path)
    if arr_full is None:
        return {"sar_image_path": str(image_path), "status": "sar_image_missing"}
    full_radius, full_azimuth, full_fan_mask = cache.grids(arr_full.shape)
    stride = EXTRACTION_STRIDE
    arr = arr_full[::stride, ::stride]
    radius = full_radius[::stride, ::stride]
    azimuth = full_azimuth[::stride, ::stride]
    fan_mask = full_fan_mask[::stride, ::stride]
    mask = (
        (azimuth >= float(support["support_azimuth_start_deg"]))
        & (azimuth <= float(support["support_azimuth_end_deg"]))
        & (radius >= float(support["support_radius_min_px"]))
        & (radius <= float(support["support_radius_max_px"]))
        & fan_mask
    )
    support_area = int(mask.sum()) * stride * stride
    if support_area <= 0:
        return {"sar_image_path": str(image_path), "status": "empty_support_region", "support_area_px": 0}
    values = arr[mask]
    background = arr[fan_mask & ~mask]
    if background.size == 0:
        background = arr[fan_mask]
    background_mean = float(background.mean()) if background.size else 1.0
    background_p95 = float(np.quantile(background, 0.95)) if background.size else float(values.mean())
    support_p75 = float(np.quantile(values, 0.75)) if values.size else 0.0
    threshold = max(background_p95, support_p75)
    peaks, local_peak_count = separated_peaks(arr, mask, threshold, k=5 if detail else 2, min_distance_px=20.0 / stride)
    if not peaks:
        return {
            "sar_image_path": str(image_path),
            "status": "no_peak_in_support_region",
            "support_area_px": support_area,
        }
    top1 = peaks[0]
    top2 = peaks[1] if len(peaks) > 1 else None
    hot = mask & (arr >= threshold)
    hot_weights = arr[hot].astype(np.float64)
    if hot_weights.size and float(hot_weights.sum()) > 0:
        ys, xs = np.where(hot)
        centroid_x = float(np.average(xs, weights=hot_weights)) * stride
        centroid_y = float(np.average(ys, weights=hot_weights)) * stride
    else:
        centroid_x = float(top1[0] * stride)
        centroid_y = float(top1[1] * stride)
    centroid_residual = math.hypot(
        centroid_x - float(support["support_center_x"]),
        centroid_y - float(support["support_center_y"]),
    )
    top2_value = float(top2[2]) if top2 else None
    top1_value = float(top1[2])
    top1_top2_ratio = top1_value / max(top2_value or 1e-6, 1e-6) if top2_value is not None else None
    top1_top2_distance = math.hypot((top1[0] - top2[0]) * stride, (top1[1] - top2[1]) * stride) if top2 else None
    return {
        "sar_image_path": str(image_path),
        "status": "support_region_peak_competition_extracted",
        "support_area_px": support_area,
        "background_mean": background_mean / 255.0,
        "background_p95": background_p95 / 255.0,
        "top1_peak_value": top1_value / 255.0,
        "top2_peak_value": top2_value / 255.0 if top2_value is not None else "",
        "top1_top2_ratio": top1_top2_ratio,
        "top1_background_ratio": top1_value / max(background_mean, 1e-6),
        "top2_background_ratio": top2_value / max(background_mean, 1e-6) if top2_value is not None else "",
        "top1_x": top1[0] * stride,
        "top1_y": top1[1] * stride,
        "top2_x": top2[0] * stride if top2 else "",
        "top2_y": top2[1] * stride if top2 else "",
        "top1_top2_distance_px": top1_top2_distance,
        "local_peak_count_above_bg_p95": local_peak_count,
        "scatter_centroid_x": centroid_x,
        "scatter_centroid_y": centroid_y,
        "centroid_residual_px": centroid_residual,
    }


def peak_competition_label(obs: Mapping[str, Any]) -> str:
    ratio = safe_float(obs.get("top1_top2_ratio"))
    count = safe_int(obs.get("local_peak_count_above_bg_p95"), 0) or 0
    top2_bg = safe_float(obs.get("top2_background_ratio"))
    if ratio is None:
        return "single_detected_peak_or_insufficient_top2"
    if ratio <= 1.10 or count >= 6 or (top2_bg is not None and top2_bg >= 1.75):
        return "serious_peak_competition_or_clutter"
    if ratio <= 1.25 or count >= 3:
        return "moderate_peak_competition"
    return "dominant_peak_observed"


def short_window_persistence(
    cache: SarImageCache,
    row: Mapping[str, Any],
    support: Mapping[str, Any],
    top1_x: float | None,
    top1_y: float | None,
) -> dict[str, Any]:
    optical_frame = safe_int(row.get("optical_frame"))
    if optical_frame is None or top1_x is None or top1_y is None:
        return {
            "short_window_frames": "",
            "short_window_observed_frames": 0,
            "short_window_top1_persistence_rate": "",
            "short_window_peak_persistence_label": "insufficient_single_frame_peak",
        }
    tau0 = safe_float(row.get("tau0_sar_frame"))
    if tau0 is None:
        tau0 = 50.0 / 24.0 * optical_frame
    window = short_window_frames(tau0)
    observed = 0
    close = 0
    for frame in window:
        obs = extract_peak_competition(cache, str(row.get("scene", "")), frame, support, detail=False)
        px = safe_float(obs.get("top1_x"))
        py = safe_float(obs.get("top1_y"))
        if px is None or py is None:
            continue
        observed += 1
        if math.hypot(px - top1_x, py - top1_y) <= 30.0:
            close += 1
    persistence = close / observed if observed else None
    if persistence is None:
        label = "insufficient_short_window_observation"
    elif persistence >= 0.60:
        label = "top1_peak_persistent_in_short_window"
    else:
        label = "top1_peak_not_persistent_in_short_window"
    return {
        "short_window_frames": ";".join(str(item) for item in window),
        "short_window_observed_frames": observed,
        "short_window_top1_persistence_rate": fmt(persistence, 4),
        "short_window_peak_persistence_label": label,
    }


def build_peak_rows(
    rows: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    cache: SarImageCache,
) -> list[dict[str, Any]]:
    peak_rows: list[dict[str, Any]] = []
    baseline_area_by_key: dict[tuple[str, str, str, str], float] = {}
    row_supports: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for row in rows:
        supports = build_supports_for_row(row, context)
        for support in supports:
            row_supports.append((row, support))
    for idx, (row, support) in enumerate(row_supports, start=1):
        scene = str(row.get("scene", ""))
        sar_frame = safe_int(row.get("sar_frame_probe"))
        if sar_frame is None:
            continue
        obs = extract_peak_competition(cache, scene, sar_frame, support)
        key = key_for_row(row)
        if support["mode_name"] == "broad_fan_baseline":
            baseline_area_by_key[key] = float(obs.get("support_area_px") or row.get("support_area_px") or 0)
        baseline_area = baseline_area_by_key.get(key)
        if baseline_area is None:
            baseline_area = safe_float(row.get("support_area_px"), 0.0) or 0.0
        area = safe_float(obs.get("support_area_px"), 0.0) or 0.0
        top1_x = safe_float(obs.get("top1_x"))
        top1_y = safe_float(obs.get("top1_y"))
        if support["mode_name"] in {"broad_fan_baseline", "state_conditioned_range_band"}:
            window = short_window_persistence(cache, row, support, top1_x, top1_y)
        else:
            window = {
                "short_window_frames": "",
                "short_window_observed_frames": "",
                "short_window_top1_persistence_rate": "",
                "short_window_peak_persistence_label": "not_recomputed_for_secondary_posthoc_mode",
            }
        gt_ok, gt_radius_ok = gt_inside(row, support)
        label = peak_competition_label(obs)
        radius_min = float(support["support_radius_min_px"])
        radius_max = float(support["support_radius_max_px"])
        peak_rows.append(
            {
                "peak_audit_id": f"P{idx:05d}",
                "mode_name": support["mode_name"],
                "relationship_type": "support_region_range_band_peak_competition_diagnostic",
                "sample_pool": row.get("sample_pool", ""),
                "clean_morphology_inclusion": row.get("clean_morphology_inclusion", ""),
                "scene": scene,
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "state_condition": row.get("state_condition", ""),
                "optical_frame": row.get("optical_frame", ""),
                "sar_frame": row.get("sar_frame_probe", ""),
                "support_azimuth_start_deg": fmt(support.get("support_azimuth_start_deg"), 4),
                "support_azimuth_end_deg": fmt(support.get("support_azimuth_end_deg"), 4),
                "support_radius_min_px": fmt(radius_min, 3),
                "support_radius_max_px": fmt(radius_max, 3),
                "radius_band_width_px": fmt(radius_max - radius_min, 3),
                "range_band_source": support.get("range_band_source", ""),
                "support_area_px": int(area),
                "area_ratio_vs_broad": fmt(area / baseline_area if baseline_area else None, 4),
                "gt_radius_px_posthoc": fmt(row.get("gt_radius_px_posthoc"), 3),
                "gt_azimuth_deg_posthoc": fmt(row.get("gt_azimuth_deg_posthoc"), 4),
                "gt_inside_support_posthoc": bool_text(gt_ok),
                "gt_radius_inside_posthoc": bool_text(gt_radius_ok),
                "top1_peak_value": fmt(obs.get("top1_peak_value"), 4),
                "top2_peak_value": fmt(obs.get("top2_peak_value"), 4),
                "top1_top2_ratio": fmt(obs.get("top1_top2_ratio"), 4),
                "top1_background_ratio": fmt(obs.get("top1_background_ratio"), 4),
                "top2_background_ratio": fmt(obs.get("top2_background_ratio"), 4),
                "top1_x": obs.get("top1_x", ""),
                "top1_y": obs.get("top1_y", ""),
                "top2_x": obs.get("top2_x", ""),
                "top2_y": obs.get("top2_y", ""),
                "top1_top2_distance_px": fmt(obs.get("top1_top2_distance_px"), 3),
                "local_peak_count_above_bg_p95": obs.get("local_peak_count_above_bg_p95", ""),
                "scatter_centroid_x": fmt(obs.get("scatter_centroid_x"), 3),
                "scatter_centroid_y": fmt(obs.get("scatter_centroid_y"), 3),
                "centroid_residual_px": fmt(obs.get("centroid_residual_px"), 3),
                **window,
                "tube_peak_continuity_label": "",
                "peak_competition_label": label,
                "sar_image_path": obs.get("sar_image_path", ""),
                "notes": "SAR image observation diagnostic inside optical-derived support; not a selector score.",
                "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return peak_rows


def build_tube_rows(peak_rows: Sequence[Mapping[str, Any]], source_rows: Sequence[Mapping[str, Any]], manual_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], str]]:
    source_by_object = groupby_key(source_rows, lambda row: (str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))))
    manual_by_object = groupby_key(manual_rows, lambda row: (str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))))
    grouped = groupby_key(
        [row for row in peak_rows if row.get("sample_pool") == "paired_optical_object_sar_gt"],
        lambda row: (str(row.get("mode_name", "")), str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))),
    )
    tube_rows: list[dict[str, Any]] = []
    labels: dict[tuple[str, str, str], str] = {}
    for idx, ((mode, scene, object_id), rows) in enumerate(sorted(grouped.items()), start=1):
        rows = sorted(rows, key=lambda row: safe_int(row.get("sar_frame"), 0) or 0)
        if len(rows) < 2:
            continue
        peak_steps = distance_steps(rows, "top1_x", "top1_y")
        centroid_steps = distance_steps(rows, "scatter_centroid_x", "scatter_centroid_y")
        peak_mean = mean_clean(peak_steps)
        centroid_mean = mean_clean(centroid_steps)
        if (peak_mean is not None and peak_mean <= 35.0) or (centroid_mean is not None and centroid_mean <= 35.0):
            label = "tube_peak_or_centroid_continuity_observed"
        elif peak_mean is None and centroid_mean is None:
            label = "insufficient_tube_peak_observation"
        else:
            label = "tube_peak_variable_or_competing"
        labels[(mode, scene, object_id)] = label
        source_group = source_by_object.get((scene, object_id), [])
        frames = [safe_float(row.get("sar_frame_probe")) for row in source_group]
        radii = [safe_float(row.get("gt_radius_px_posthoc")) for row in source_group]
        heights = [safe_float(row.get("bbox_height_px")) for row in source_group]
        bottoms = [safe_float(row.get("bbox_bottom_y")) for row in source_group]
        areas = [safe_float(row.get("bbox_area_px")) for row in source_group]
        review_need = ";".join(
            str(row.get("review_need", "")) for row in manual_by_object.get((scene, object_id), []) if row.get("review_need")
        )
        sar_frames = [safe_int(row.get("sar_frame")) for row in rows if safe_int(row.get("sar_frame")) is not None]
        tube_rows.append(
            {
                "tube_probe_id": f"TU{idx:04d}",
                "mode_name": mode,
                "sample_pool": "paired_optical_object_sar_gt",
                "scene": scene,
                "object_hypothesis_id": object_id,
                "state_mix": compact_counts(row.get("state_condition", "") for row in rows),
                "n_rows": len(rows),
                "sar_frame_span": f"{min(sar_frames)}-{max(sar_frames)}" if sar_frames else "",
                "gt_coverage_rate_posthoc": rate(sum(1 for row in rows if row.get("gt_inside_support_posthoc") == "true"), len(rows)),
                "median_radius_band_width_px": fmt(median_clean(row.get("radius_band_width_px") for row in rows), 3),
                "median_peak_to_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in rows), 4),
                "median_top1_top2_ratio": fmt(median_clean(row.get("top1_top2_ratio") for row in rows), 4),
                "peak_continuity_step_mean_px": fmt(peak_mean, 3),
                "centroid_continuity_step_mean_px": fmt(centroid_mean, 3),
                "tube_peak_continuity_label": label,
                "notes": "Tube continuity is a SAR observation diagnostic inside range-band supports; it is not identity truth.",
                "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence",
            }
        )
    return tube_rows, labels


def build_object_rows(
    tube_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
    manual_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    source_by_object = groupby_key(source_rows, lambda row: (str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))))
    manual_by_object = groupby_key(manual_rows, lambda row: (str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))))
    object_rows: list[dict[str, Any]] = []
    for idx, tube in enumerate(tube_rows, start=1):
        scene = str(tube.get("scene", ""))
        object_id = str(tube.get("object_hypothesis_id", ""))
        source_group = source_by_object.get((scene, object_id), [])
        optical_frames = [safe_int(row.get("optical_frame")) for row in source_group if safe_int(row.get("optical_frame")) is not None]
        sar_frames = [safe_int(row.get("sar_frame_probe")) for row in source_group if safe_int(row.get("sar_frame_probe")) is not None]
        radii = [safe_float(row.get("gt_radius_px_posthoc")) for row in source_group]
        heights = [safe_float(row.get("bbox_height_px")) for row in source_group]
        bottoms = [safe_float(row.get("bbox_bottom_y")) for row in source_group]
        areas = [safe_float(row.get("bbox_area_px")) for row in source_group]
        review_need = ";".join(
            str(row.get("review_need", "")) for row in manual_by_object.get((scene, object_id), []) if row.get("review_need")
        )
        object_rows.append(
            {
                "object_probe_id": f"O{idx:04d}",
                "mode_name": tube.get("mode_name", ""),
                "scene": scene,
                "object_hypothesis_id": object_id,
                "sample_pool": tube.get("sample_pool", ""),
                "state_mix": tube.get("state_mix", ""),
                "n_rows": tube.get("n_rows", ""),
                "optical_frame_span": f"{min(optical_frames)}-{max(optical_frames)}" if optical_frames else "",
                "sar_frame_span": f"{min(sar_frames)}-{max(sar_frames)}" if sar_frames else tube.get("sar_frame_span", ""),
                "gt_coverage_rate_posthoc": tube.get("gt_coverage_rate_posthoc", ""),
                "median_radius_band_width_px": tube.get("median_radius_band_width_px", ""),
                "median_support_area_px": "",
                "median_peak_to_background_ratio": tube.get("median_peak_to_background_ratio", ""),
                "median_top1_top2_ratio": tube.get("median_top1_top2_ratio", ""),
                "peak_continuity_step_mean_px": tube.get("peak_continuity_step_mean_px", ""),
                "centroid_continuity_step_mean_px": tube.get("centroid_continuity_step_mean_px", ""),
                "tube_peak_continuity_label": tube.get("tube_peak_continuity_label", ""),
                "optical_height_vs_gt_radius_slope_posthoc": fmt(slope_pairs(heights, radii), 5),
                "optical_bottom_y_vs_gt_radius_slope_posthoc": fmt(slope_pairs(bottoms, radii), 5),
                "optical_area_vs_gt_radius_slope_posthoc": fmt(slope_pairs(areas, radii), 5),
                "manual_review_need": review_need,
                "notes": "Object row summarizes posthoc range/peak continuity; object_hypothesis_id is not identity truth.",
                "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return object_rows


def slope_pairs(xs: Sequence[Any], ys: Sequence[Any]) -> float | None:
    pairs = [(safe_float(x), safe_float(y)) for x, y in zip(xs, ys)]
    clean = [(float(x), float(y)) for x, y in pairs if x is not None and y is not None]
    if len(clean) < 2:
        return None
    return slope([x for x, _ in clean], [y for _, y in clean])


def distance_steps(rows: Sequence[Mapping[str, Any]], x_key: str, y_key: str) -> list[float]:
    distances: list[float] = []
    last: tuple[float, float] | None = None
    for row in rows:
        x = safe_float(row.get(x_key))
        y = safe_float(row.get(y_key))
        if x is None or y is None:
            continue
        if last is not None:
            distances.append(math.hypot(x - last[0], y - last[1]))
        last = (float(x), float(y))
    return distances


def attach_tube_labels(peak_rows: list[dict[str, Any]], labels: Mapping[tuple[str, str, str], str]) -> None:
    for row in peak_rows:
        key = (str(row.get("mode_name", "")), str(row.get("scene", "")), str(row.get("object_hypothesis_id", "")))
        row["tube_peak_continuity_label"] = labels.get(key, "insufficient_or_not_paired_tube")


def build_state_rows(peak_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = groupby_key(peak_rows, lambda row: (str(row.get("state_condition", "")), str(row.get("mode_name", "")), str(row.get("sample_pool", ""))))
    for (state, mode, sample_pool), group in sorted(grouped.items()):
        with_gt = [row for row in group if row.get("gt_inside_support_posthoc") in {"true", "false"}]
        serious = [row for row in group if row.get("peak_competition_label") == "serious_peak_competition_or_clutter"]
        rows.append(
            {
                "state_condition": state,
                "mode_name": mode,
                "sample_pool": sample_pool,
                "n_rows": len(group),
                "gt_coverage_rate_posthoc": rate(sum(1 for row in with_gt if row.get("gt_inside_support_posthoc") == "true"), len(with_gt)),
                "median_radius_band_width_px": fmt(median_clean(row.get("radius_band_width_px") for row in group), 3),
                "median_support_area_px": fmt(median_clean(row.get("support_area_px") for row in group), 1),
                "median_area_ratio_vs_broad": fmt(median_clean(row.get("area_ratio_vs_broad") for row in group), 4),
                "median_peak_to_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in group), 4),
                "median_top1_top2_ratio": fmt(median_clean(row.get("top1_top2_ratio") for row in group), 4),
                "peak_competition_serious_rate": rate(len(serious), len(group)),
                "recommended_range_band_treatment": state_treatment(state),
                "notes": "State split preserves dropout/no-match outside clean paired morphology.",
            }
        )
    return rows


def build_mode_rows(peak_rows: Sequence[Mapping[str, Any]], context: Mapping[str, Any], tube_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = groupby_key(peak_rows, lambda row: str(row.get("mode_name", "")))
    tube_by_mode = groupby_key(tube_rows, lambda row: str(row.get("mode_name", "")))
    mode_family = {
        "broad_fan_baseline": "A baseline broad_unknown_range_prior",
        "complete_shape_quantile_range_band": "B complete-shape posthoc quantile range band",
        "state_conditioned_range_band": "C state-conditioned range band",
        "object_smoothed_range_band": "D object-smoothed posthoc range band",
        "scene_residual_range_band": "E scene residual posthoc diagnostic",
    }
    mode_boundary = {
        "broad_fan_baseline": "runtime-safe broad support baseline from prior probe",
        "complete_shape_quantile_range_band": "posthoc hypothesis audit only; complete rows only",
        "state_conditioned_range_band": "posthoc hypothesis audit of state uncertainty, not runtime rule",
        "object_smoothed_range_band": "posthoc object trend diagnostic, not identity truth",
        "scene_residual_range_band": "posthoc scene residual diagnostic; GT residual not runtime prior",
    }
    interpretation = {
        "broad_fan_baseline": "high GT coverage but broad area and strong risk of clutter peak competition",
        "complete_shape_quantile_range_band": "physically interpretable for complete/stable rows if coverage survives narrowing",
        "state_conditioned_range_band": "most direct bridge toward future runtime-safe uncertainty design, but current numbers are posthoc",
        "object_smoothed_range_band": "useful for temporal smoothing and jitter diagnosis; requires identity/tracklet review before runtime use",
        "scene_residual_range_band": "diagnoses scene bias; should not be copied into runtime construction",
    }
    for mode, group in sorted(grouped.items()):
        paired = [row for row in group if row.get("sample_pool") == "paired_optical_object_sar_gt"]
        clean = [row for row in paired if row.get("clean_morphology_inclusion") == "true"]
        dropout = [row for row in group if row.get("sample_pool") != "paired_optical_object_sar_gt"]
        serious = [row for row in group if row.get("peak_competition_label") == "serious_peak_competition_or_clutter"]
        measured_windows = [
            row
            for row in group
            if row.get("short_window_peak_persistence_label") not in {"", "not_recomputed_for_secondary_posthoc_mode"}
        ]
        persistent = [row for row in measured_windows if row.get("short_window_peak_persistence_label") == "top1_peak_persistent_in_short_window"]
        tubes = tube_by_mode.get(mode, [])
        continuous = [row for row in tubes if row.get("tube_peak_continuity_label") == "tube_peak_or_centroid_continuity_observed"]
        rows.append(
            {
                "mode_name": mode,
                "mode_family": mode_family.get(mode, ""),
                "mode_boundary": mode_boundary.get(mode, ""),
                "n_rows": len(group),
                "n_paired_rows": len(paired),
                "n_clean_complete_rows": len(clean),
                "n_dropout_rows": len(dropout),
                "selected_shape_feature": context["selected_feature"] if mode != "broad_fan_baseline" else "",
                "gt_coverage_rate_paired_posthoc": rate(sum(1 for row in paired if row.get("gt_inside_support_posthoc") == "true"), len(paired)),
                "gt_coverage_rate_clean_complete_posthoc": rate(sum(1 for row in clean if row.get("gt_inside_support_posthoc") == "true"), len(clean)),
                "median_radius_band_width_px": fmt(median_clean(row.get("radius_band_width_px") for row in group), 3),
                "median_support_area_px": fmt(median_clean(row.get("support_area_px") for row in group), 1),
                "median_area_ratio_vs_broad": fmt(median_clean(row.get("area_ratio_vs_broad") for row in group), 4),
                "median_peak_to_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in group), 4),
                "median_top1_top2_ratio": fmt(median_clean(row.get("top1_top2_ratio") for row in group), 4),
                "median_top2_to_background_ratio": fmt(median_clean(row.get("top2_background_ratio") for row in group), 4),
                "median_local_peak_count_above_bg_p95": fmt(median_clean(row.get("local_peak_count_above_bg_p95") for row in group), 1),
                "peak_competition_serious_rate": rate(len(serious), len(group)),
                "short_window_peak_persistence_rate": rate(len(persistent), len(measured_windows)) if measured_windows else "",
                "tube_peak_continuity_rate": rate(len(continuous), len(tubes)),
                "interpretation": interpretation.get(mode, ""),
                "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return rows


def build_summary(
    timestamp: str,
    mode_rows: Sequence[Mapping[str, Any]],
    peak_rows: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    tube_rows: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    mode_by_name = {row.get("mode_name", ""): row for row in mode_rows}
    baseline = mode_by_name.get("broad_fan_baseline", {})
    state_mode = mode_by_name.get("state_conditioned_range_band", {})
    object_mode = mode_by_name.get("object_smoothed_range_band", {})
    scene_mode = mode_by_name.get("scene_residual_range_band", {})
    selected_feature = str(context.get("selected_feature", ""))
    serious_baseline = baseline.get("peak_competition_serious_rate", "")
    answers = {
        "1_broad_fan_problem": (
            "The broad fan support preserves posthoc coverage, but it covers a large radial sector. "
            f"Baseline median support area is {baseline.get('median_support_area_px', '')} px and serious peak competition rate is {serious_baseline}; "
            "therefore the observed top peak can be a competing clutter or sidelobe peak rather than a unique target localization."
        ),
        "2_range_narrowing_area_vs_coverage": (
            f"State-conditioned narrowing has paired GT coverage {state_mode.get('gt_coverage_rate_paired_posthoc', '')} "
            f"with median area ratio {state_mode.get('median_area_ratio_vs_broad', '')} versus broad fan. "
            f"Object-smoothed narrowing has paired GT coverage {object_mode.get('gt_coverage_rate_paired_posthoc', '')} "
            f"with median area ratio {object_mode.get('median_area_ratio_vs_broad', '')}."
        ),
        "3_most_interpretable_mode": (
            "State-conditioned range band is the most physically interpretable next form because it separates complete, edge/truncated, duplicate, far-small, and dropout uncertainty. "
            "Complete-shape quantile is useful only for complete/stable rows, while scene residual remains posthoc diagnostic only."
        ),
        "4_peak_competition": (
            f"Peak competition is nontrivial: broad fan serious competition rate is {serious_baseline}, "
            f"with median top1/top2 ratio {baseline.get('median_top1_top2_ratio', '')}. "
            "This should be treated as SAR observation uncertainty, not a selector score."
        ),
        "5_temporal_continuity": (
            f"Broad fan short-window persistence rate is {baseline.get('short_window_peak_persistence_rate', '')}; "
            f"state-conditioned short-window persistence rate is {state_mode.get('short_window_peak_persistence_rate', '')}. "
            f"Tube continuity for state-conditioned rows is {state_mode.get('tube_peak_continuity_rate', '')}."
        ),
        "6_state_differences": (
            "Complete rows can use narrower range bands. Edge/truncated rows need wider bands because optical box height/bottom are partial. "
            "Duplicate/handoff rows need review-conditioned widening. Dropout/no-match rows stay outside clean morphology and should use temporal continuation plus SAR support only."
        ),
        "7_posthoc_observations": (
            f"The selected shape feature `{selected_feature}`, all shape-radius quantile bands, object-smoothed radius trends, and scene residual bands are posthoc observations. "
            "They must not be written back into runtime prior construction without a separate runtime-safe derivation."
        ),
        "8_next_priority": (
            "Next priority should be runtime-safe range hypothesis design from optical-only geometry/state, then SAR temporal peak tracking. "
            "GM_RM019 review should proceed to confirm optical object continuity and complete frames; GM_RM011 object-stream recovery remains the scale-expansion blocker."
        ),
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "ledger_valid": True,
            "category_counts": EXPECTED_LEDGER,
            "note": "The audit preserves the 442 ledger. Paired rows are range-band validation rows; dropout rows are separate diagnostics.",
        },
        "row_counts": {
            "range_band_mode_comparison": len(mode_rows),
            "support_region_peak_competition_audit": len(peak_rows),
            "state_conditioned_range_band_probe": len(state_rows),
            "object_smoothed_range_band_probe": len(object_rows),
            "range_narrowing_tube_continuity_probe": len(tube_rows),
        },
        "range_model_context": {
            "selected_shape_feature": selected_feature,
            "complete_shape_feature_correlations": context.get("feature_correlations", {}),
            "scene_residual_by_scene": context.get("scene_residual_by_scene", {}),
        },
        "key_metrics": {
            "broad_gt_coverage_paired_posthoc": baseline.get("gt_coverage_rate_paired_posthoc", ""),
            "broad_median_area_px": baseline.get("median_support_area_px", ""),
            "broad_serious_peak_competition_rate": baseline.get("peak_competition_serious_rate", ""),
            "state_conditioned_gt_coverage_paired_posthoc": state_mode.get("gt_coverage_rate_paired_posthoc", ""),
            "state_conditioned_area_ratio_vs_broad_median": state_mode.get("median_area_ratio_vs_broad", ""),
            "object_smoothed_gt_coverage_paired_posthoc": object_mode.get("gt_coverage_rate_paired_posthoc", ""),
            "object_smoothed_area_ratio_vs_broad_median": object_mode.get("median_area_ratio_vs_broad", ""),
            "scene_residual_gt_coverage_paired_posthoc": scene_mode.get("gt_coverage_rate_paired_posthoc", ""),
            "scene_residual_area_ratio_vs_broad_median": scene_mode.get("median_area_ratio_vs_broad", ""),
        },
        "question_answers": answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }


def render_plan_doc(path: Path, timestamp: str, outputs: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 Support-Region Range Narrowing And Peak Competition Plan",
        "",
        f"Updated: {timestamp}",
        "",
        "This plan defines a posthoc audit for narrowing `broad_unknown_range_prior` into range-band hypotheses and measuring SAR peak competition. It is not OTY3, not final automatic annotation, not selector/ranking, and not training or threshold tuning.",
        "",
        "## Boundary",
        "",
        "- Broad fan support remains the runtime-safe baseline from the previous probe.",
        "- Complete shape quantile, object smoothing, and scene residual bands are posthoc hypothesis audits.",
        "- SAR image content is used only for observation extraction inside optical-derived support regions.",
        "- SAR GT is used only for coverage and residual validation columns.",
        "- GT crop extraction, annotation proposals, selector scores, ranking, tuned thresholds, and identity truth are out of scope.",
        "",
        "## Compared Support Modes",
        "",
        "A. `broad_fan_baseline`: previous `broad_unknown_range_prior`.",
        "B. `complete_shape_quantile_range_band`: complete/stable optical shape versus SAR radius posthoc quantile relation.",
        "C. `state_conditioned_range_band`: narrower complete bands and wider edge/truncated/duplicate/dropout bands.",
        "D. `object_smoothed_range_band`: posthoc object-level range trend smoothing to reduce single-frame jitter.",
        "E. `scene_residual_range_band`: scene-level residual diagnostic only; GT residual must not become runtime prior.",
        "",
        "## Peak Competition Diagnostics",
        "",
        "The audit extracts top1/top2 peak values and locations, top1/top2 ratio, top1/background and top2/background ratios, local peak counts above background percentile, scatter centroid, centroid residual, short-window peak persistence, and tube-level continuity.",
        "",
        "## Generated Outputs",
        "",
    ]
    for name, output_path in outputs.items():
        lines.append(f"- {name}: `{output_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(path: Path, summary: Mapping[str, Any], mode_rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# OTY2 Range Narrowing And Peak Competition Audit Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report audits posthoc range-band hypotheses and peak competition inside optical-derived SAR support regions. It does not generate final boxes, annotation proposals, selector/ranking output, training, tuned thresholds, or identity truth.",
        "",
        "## Ledger Boundary",
        "",
        "- paired_optical_object_sar_gt = 215",
        "- blocked_missing_gm011_object_stream = 195",
        "- sar_only_gt = 20",
        "- dropout/no_oty_iou_match/temporal continuation pool = 12",
        "",
        "GM_RM011 remains blocked by missing current OTY object stream. SAR-only rows are not mixed into optical-SAR correspondence. Dropout/no-match rows remain outside clean paired morphology.",
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in summary["key_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Mode Comparison", ""])
    for row in mode_rows:
        lines.append(
            f"- {row['mode_name']}: paired coverage `{row['gt_coverage_rate_paired_posthoc']}`, "
            f"median area ratio `{row['median_area_ratio_vs_broad']}`, serious peak competition `{row['peak_competition_serious_rate']}`, "
            f"boundary `{row['mode_boundary']}`."
        )
    lines.extend(["", "## Required Answers", ""])
    answers = summary["question_answers"]
    for idx, key in enumerate(
        [
            "1_broad_fan_problem",
            "2_range_narrowing_area_vs_coverage",
            "3_most_interpretable_mode",
            "4_peak_competition",
            "5_temporal_continuity",
            "6_state_differences",
            "7_posthoc_observations",
            "8_next_priority",
        ],
        start=1,
    ):
        lines.append(f"{idx}. {answers[key]}")
    lines.extend(["", "## Boundary Flags", ""])
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
    log_path = WORKSPACE_LOG_DIR / f"oty2_range_narrowing_peak_competition_audit_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_range_narrowing_peak_competition_audit",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "frame_support_csv": Path(args.frame_support_csv) if args.frame_support_csv else latest_path("oty2_optical_frame_to_sar_frame_support_probe_*.csv"),
        "window_support_csv": Path(args.window_support_csv) if args.window_support_csv else latest_path("oty2_optical_frame_to_sar_window_support_probe_*.csv"),
        "tracklet_tube_csv": Path(args.tracklet_tube_csv) if args.tracklet_tube_csv else latest_path("oty2_optical_tracklet_to_sar_tube_probe_*.csv"),
        "support_summary_json": Path(args.support_summary_json) if args.support_summary_json else latest_path("oty2_support_region_sar_observation_summary_*.json"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "manual_review_csv": Path(args.manual_review_csv) if args.manual_review_csv else latest_path("oty2_manual_review_candidate_list_*.csv"),
    }
    summary = json.loads(paths["support_summary_json"].read_text(encoding="utf-8"))
    ledger = summary.get("sample_ledger", {}).get("category_counts", {})
    if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
        raise RuntimeError(f"Ledger changed; refusing audit: {json.dumps(ledger, ensure_ascii=False)}")
    return {
        "paths": paths,
        "support_summary": summary,
        "frame_rows": read_csv(paths["frame_support_csv"]),
        "window_rows": read_csv(paths["window_support_csv"]),
        "tube_rows": read_csv(paths["tracklet_tube_csv"]),
        "corr_rows": read_csv(paths["correspondence_csv"]),
        "manual_rows": read_csv(paths["manual_review_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    cache = SarImageCache(max_images=args.image_cache_size)
    source_rows = normalize_frame_rows(inputs["frame_rows"], inputs["corr_rows"])
    context = build_range_context(source_rows)
    peak_rows = build_peak_rows(source_rows, context, cache)
    tube_rows, tube_labels = build_tube_rows(peak_rows, source_rows, inputs["manual_rows"])
    attach_tube_labels(peak_rows, tube_labels)
    state_rows = build_state_rows(peak_rows)
    object_rows = build_object_rows(tube_rows, source_rows, inputs["manual_rows"])
    mode_rows = build_mode_rows(peak_rows, context, tube_rows)

    plan_doc = DOCS_DIR / "oty2_support_region_range_narrowing_and_peak_competition_plan.md"
    mode_csv = REPORT_DIR / f"oty2_range_band_mode_comparison_{timestamp}.csv"
    peak_csv = REPORT_DIR / f"oty2_support_region_peak_competition_audit_{timestamp}.csv"
    state_csv = REPORT_DIR / f"oty2_state_conditioned_range_band_probe_{timestamp}.csv"
    object_csv = REPORT_DIR / f"oty2_object_smoothed_range_band_probe_{timestamp}.csv"
    tube_csv = REPORT_DIR / f"oty2_range_narrowing_tube_continuity_probe_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_range_narrowing_peak_competition_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_range_narrowing_peak_competition_summary_{timestamp}.json"
    outputs = {
        "plan_doc": str(plan_doc),
        "range_band_mode_comparison_csv": str(mode_csv),
        "support_region_peak_competition_audit_csv": str(peak_csv),
        "state_conditioned_range_band_probe_csv": str(state_csv),
        "object_smoothed_range_band_probe_csv": str(object_csv),
        "range_narrowing_tube_continuity_probe_csv": str(tube_csv),
        "range_narrowing_peak_competition_report_md": str(report_md),
        "range_narrowing_peak_competition_summary_json": str(summary_json),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}
    summary = build_summary(timestamp, mode_rows, peak_rows, state_rows, object_rows, tube_rows, context, sources, outputs)
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    render_plan_doc(plan_doc, timestamp, summary["outputs"])
    write_csv(mode_csv, mode_rows, MODE_FIELDS)
    write_csv(peak_csv, peak_rows, PEAK_FIELDS)
    write_csv(state_csv, state_rows, STATE_FIELDS)
    write_csv(object_csv, object_rows, OBJECT_FIELDS)
    write_csv(tube_csv, tube_rows, TUBE_FIELDS)
    render_report(report_md, summary, mode_rows)
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
    parser.add_argument("--frame-support-csv", default="")
    parser.add_argument("--window-support-csv", default="")
    parser.add_argument("--tracklet-tube-csv", default="")
    parser.add_argument("--support-summary-json", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--manual-review-csv", default="")
    parser.add_argument("--image-cache-size", type=int, default=64)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
