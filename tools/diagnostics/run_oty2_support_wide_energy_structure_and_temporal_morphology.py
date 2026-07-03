"""OTY2 support-wide energy structure and temporal morphology diagnostics.

This diagnostic corrects the previous GT-local/top-k support judgment by
inspecting the whole optical-derived support region. It extracts high-energy
atoms, connected bright components, coarse vehicle shell proxies, support
failure taxonomy, and temporal morphology drift signals.

The outputs are posthoc mechanism diagnostics only. They are not annotation
proposals, final boxes, selected components, selector/ranking outputs,
training products, tuned thresholds, best weights, or identity-truth claims.
SAR GT and SAR image observations are used only for posthoc validation and
mechanism diagnosis, not for runtime prediction logic.
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
from matplotlib.patches import Polygon, Rectangle
from scipy import ndimage

from run_oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage import (
    angle_in_interval,
    crop_box_for,
    fan_azimuth,
    fan_radius,
    support_available,
    support_boundary_points,
)
from run_oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion import (
    box_available,
    gt_box_from_correspondence,
    rotated_corners,
    sanitize,
)
from run_oty2_support_overlay_visualization_qa_and_chinese_review_atlas import (
    FONT,
    support_closed_polygon,
    wrap_zh,
)
from run_oty2_support_region_sar_observation_probe import (
    FAN_RADIUS_PX,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    SarImageCache,
    compact_counts,
    fmt,
    latest_path,
    read_csv,
    safe_float,
    safe_int,
    sar_path,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
VISUAL_DIR = REPORT_DIR / "visual_exemplars"
STATE_MODE = "state_conditioned_range_band"

ATOM_QUANTILE = 0.97
COMPONENT_SUPPORT_QUANTILE = 0.85
LOCAL_MAX_FILTER_SIZE = 5
LOCAL_MAX_MIN_DISTANCE_PX = 12.0
MIN_COMPONENT_AREA_PX = 8
MAX_ATOMS_PER_SUPPORT = 80
MAX_ATOMS_FOR_CSV = 16
WINDOW_OFFSETS = {
    3: [-1, 0, 1],
    5: [-2, -1, 0, 1, 2],
    10: [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
}

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "support_wide_energy_structure_diagnostic_entered": True,
    "vehicle_shell_proxy_entered": True,
    "support_failure_taxonomy_entered": True,
    "temporal_morphology_drift_probe_entered": True,
    "multi_frame_chinese_atlas_generated": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "final_candidate_box_output": False,
    "selected_component_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "best_weight_selected": False,
    "identity_truth_claimed": False,
    "support_wide_shell_proxy_written_as_annotation_rule": False,
    "temporal_tube_written_as_identity_truth": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
    "matlab_zip_or_any_zip_committed": False,
}

ATOM_COMPONENT_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "support_available",
    "support_source",
    "gt_available",
    "support_area_px",
    "n_support_energy_atoms",
    "n_support_connected_components",
    "n_gt_inside_atoms",
    "n_outside_gt_inside_support_atoms",
    "n_competing_components_inside_support",
    "dominant_component_area",
    "dominant_component_range_extent",
    "dominant_component_azimuth_extent",
    "dominant_component_shape_type",
    "energy_atoms_form_vehicle_structure",
    "peaks_alone_sufficient",
    "support_wide_structure_note",
    "posthoc_gt_relation_validation_only",
    "notes",
    "support_image_available",
    "atom_threshold_rule",
    "component_threshold_rule",
    "top_atom_points_support_wide",
    "component_shape_mix",
]

PROXY_FIELDS = [
    "case_id",
    "proxy_name",
    "proxy_available",
    "proxy_value_or_label",
    "evidence_summary",
    "vehicle_shell_supported",
    "main_failure_reason",
    "manual_review_needed",
    "notes",
]

FAILURE_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "optical_state",
    "support_failure_type",
    "azimuth_alignment_status",
    "range_alignment_status",
    "gt_area_coverage_ratio",
    "gt_energy_coverage_ratio",
    "morphology_coverage_proxy",
    "main_energy_strip_relative_to_support",
    "neighbor_or_background_interference",
    "human_review_note",
    "recommended_next_action",
    "not_allowed_conclusion",
]

TEMPORAL_FIELDS = [
    "case_id",
    "scene",
    "object_hypothesis_id",
    "sar_frame",
    "window_size",
    "frame_offsets_used",
    "temporal_data_available",
    "dominant_structure_persistence",
    "hotspot_drift_available",
    "hotspot_drift_direction",
    "component_centroid_drift",
    "ridge_or_strip_persistence",
    "shell_structure_persistence",
    "structure_changes_gradually",
    "possible_vehicle_like_temporal_tube",
    "possible_background_stable_structure",
    "compatible_with_optical_tracklet_motion",
    "main_temporal_failure_reason",
    "notes",
]

CONTINUITY_FIELDS = [
    "panel_id",
    "case_id",
    "scene",
    "sar_frame",
    "continuity_case_type",
    "support_wide_structure_label",
    "temporal_best_window",
    "possible_vehicle_like_temporal_tube",
    "possible_background_stable_structure",
    "manual_review_needed",
    "atlas_panel_path",
    "notes",
]

PANEL_NOTE_FIELDS = [
    "panel_id",
    "case_id",
    "human_structure_observation",
    "support_observation",
    "support_failure_hypothesis",
    "temporal_hypothesis",
    "confounder_note",
    "concept_correction",
    "recommended_next_action",
]


def bool_text(value: bool | None) -> str:
    if value is None:
        return "uncertain"
    return "yes" if value else "no"


def is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def rate_text(num: int, den: int) -> str:
    if den <= 0:
        return ""
    return fmt(num / den, 4)


def median_text(values: Sequence[float]) -> str:
    if not values:
        return ""
    return fmt(float(median(values)), 4)


def case_id_from_support(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    optical_frame = sanitize(row.get("optical_frame", "opt"))
    sar_frame = sanitize(row.get("sar_frame", "sar"))
    obj = sanitize(row.get("object_hypothesis_id", "obj"))
    return f"PAIR_{scene}_o{optical_frame}_s{sar_frame}_{obj}"


def case_id_from_correspondence(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    optical_frame = sanitize(row.get("optical_frame", "opt"))
    sar_frame = sanitize(row.get("sar_frame", "sar"))
    obj = sanitize(row.get("object_hypothesis_id", "obj"))
    return f"PAIR_{scene}_o{optical_frame}_s{sar_frame}_{obj}"


def compact_points(atoms: Sequence[Mapping[str, Any]], limit: int = MAX_ATOMS_FOR_CSV) -> str:
    parts = []
    for atom in atoms[:limit]:
        parts.append(
            f"{int(atom['x'])},{int(atom['y'])},{fmt(float(atom['value']) / 255.0, 4)}"
        )
    if len(atoms) > limit:
        parts.append(f"...+{len(atoms) - limit}")
    return ";".join(parts)


def support_source(row: Mapping[str, Any], coverage: Mapping[str, Any] | None) -> str:
    if coverage and coverage.get("support_source"):
        return str(coverage.get("support_source", ""))
    parts = [str(row.get("mode_name", "")), str(row.get("range_band_source", ""))]
    return ";".join(part for part in parts if part)


def support_context(
    cache: SarImageCache,
    shape: tuple[int, int],
    support: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not support_available(support):
        return None
    rmin = safe_float(support.get("support_radius_min_px"))
    rmax = safe_float(support.get("support_radius_max_px"))
    amin = safe_float(support.get("support_azimuth_start_deg"))
    amax = safe_float(support.get("support_azimuth_end_deg"))
    if None in (rmin, rmax, amin, amax):
        return None
    radius, azimuth, fan_mask = cache.grids(shape)
    mask = (
        (radius >= float(rmin))
        & (radius <= float(rmax))
        & angle_in_interval(azimuth, float(amin), float(amax))
        & fan_mask
    )
    if not bool(mask.any()):
        return None
    ys, xs = np.where(mask)
    pad = 2
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(shape[1], int(xs.max()) + pad + 1)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(shape[0], int(ys.max()) + pad + 1)
    return {
        "crop": (x0, y0, x1, y1),
        "mask_crop": mask[y0:y1, x0:x1],
        "support_area_px": int(mask.sum()),
        "fan_mask": fan_mask,
        "support_radius_min_px": float(rmin),
        "support_radius_max_px": float(rmax),
        "support_azimuth_start_deg": float(amin),
        "support_azimuth_end_deg": float(amax),
    }


def rotated_mask_for_crop(
    crop: tuple[int, int, int, int],
    box: Mapping[str, float] | None,
) -> np.ndarray | None:
    if box is None or not box_available(box):
        return None
    x0, y0, x1, y1 = crop
    if x1 <= x0 or y1 <= y0:
        return None
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
    return (np.abs(local_x) <= w / 2.0) & (np.abs(local_y) <= h / 2.0)


def points_inside_rotated_box(
    atoms: Sequence[Mapping[str, Any]],
    box: Mapping[str, float] | None,
) -> list[bool]:
    if box is None or not box_available(box):
        return [False for _ in atoms]
    cx = float(box["cx"])
    cy = float(box["cy"])
    w = float(box["w"])
    h = float(box["h"])
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    inside = []
    for atom in atoms:
        dx = float(atom["x"]) + 0.5 - cx
        dy = float(atom["y"]) + 0.5 - cy
        local_x = ca * dx + sa * dy
        local_y = -sa * dx + ca * dy
        inside.append(abs(local_x) <= w / 2.0 and abs(local_y) <= h / 2.0)
    return inside


def separated_local_maxima(
    crop_arr: np.ndarray,
    mask_crop: np.ndarray,
    threshold: float,
    origin: tuple[int, int],
) -> list[dict[str, Any]]:
    if not bool(mask_crop.any()):
        return []
    maximum = ndimage.maximum_filter(crop_arr, size=LOCAL_MAX_FILTER_SIZE, mode="nearest")
    candidates = mask_crop & (crop_arr >= threshold) & (crop_arr == maximum)
    ys, xs = np.where(candidates)
    if ys.size == 0:
        return []
    values = crop_arr[ys, xs]
    order = np.argsort(values)[::-1]
    atoms: list[dict[str, Any]] = []
    ox, oy = origin
    for idx in order[:1000]:
        x = int(xs[idx]) + ox
        y = int(ys[idx]) + oy
        value = float(values[idx])
        if all(
            math.hypot(x - float(atom["x"]), y - float(atom["y"]))
            >= LOCAL_MAX_MIN_DISTANCE_PX
            for atom in atoms
        ):
            atoms.append({"x": x, "y": y, "value": value})
        if len(atoms) >= MAX_ATOMS_PER_SUPPORT:
            break
    return atoms


def classify_component(
    area: int,
    bbox_w: int,
    bbox_h: int,
    fill_ratio: float,
    range_extent: float,
    azimuth_extent: float,
    support_area: int,
) -> str:
    max_dim = max(bbox_w, bbox_h)
    min_dim = max(1, min(bbox_w, bbox_h))
    elongation = max_dim / min_dim
    if area <= 12 or max_dim <= 5:
        return "point_like"
    if area / max(support_area, 1) >= 0.20 and fill_ratio < 0.28:
        return "diffuse"
    if elongation >= 3.0 and max_dim >= 18:
        return "strip_like"
    if (range_extent >= 45.0 and azimuth_extent <= 3.0) or (
        azimuth_extent >= 5.0 and range_extent <= 45.0
    ):
        return "strip_like"
    if area >= 35 and fill_ratio < 0.38 and max_dim >= 18:
        return "shell_like"
    if area >= 30 and fill_ratio >= 0.32:
        return "block_like"
    return "uncertain"


def component_summaries(
    crop_arr: np.ndarray,
    hot_crop: np.ndarray,
    gt_mask_crop: np.ndarray | None,
    origin: tuple[int, int],
    support_area: int,
) -> list[dict[str, Any]]:
    labels, n_labels = ndimage.label(hot_crop, structure=np.ones((3, 3), dtype=np.int8))
    if n_labels == 0:
        return []
    objects = ndimage.find_objects(labels)
    components: list[dict[str, Any]] = []
    ox, oy = origin
    for label_idx, slc in enumerate(objects, start=1):
        if slc is None:
            continue
        local_mask = labels[slc] == label_idx
        area = int(local_mask.sum())
        if area < MIN_COMPONENT_AREA_PX:
            continue
        sub_y, sub_x = np.where(local_mask)
        y_local = sub_y + slc[0].start
        x_local = sub_x + slc[1].start
        full_x = x_local.astype(np.float32) + ox
        full_y = y_local.astype(np.float32) + oy
        values = crop_arr[y_local, x_local].astype(np.float64)
        bbox_x0 = int(full_x.min())
        bbox_x1 = int(full_x.max()) + 1
        bbox_y0 = int(full_y.min())
        bbox_y1 = int(full_y.max()) + 1
        bbox_w = max(1, bbox_x1 - bbox_x0)
        bbox_h = max(1, bbox_y1 - bbox_y0)
        fill_ratio = area / max(1, bbox_w * bbox_h)
        radii = fan_radius(full_x, full_y)
        azimuth = fan_azimuth(full_x, full_y)
        range_extent = float(np.max(radii) - np.min(radii)) if radii.size else 0.0
        azimuth_extent = float(np.max(azimuth) - np.min(azimuth)) if azimuth.size else 0.0
        shape_type = classify_component(
            area, bbox_w, bbox_h, fill_ratio, range_extent, azimuth_extent, support_area
        )
        if values.sum() > 0:
            centroid_x = float(np.average(full_x, weights=values))
            centroid_y = float(np.average(full_y, weights=values))
        else:
            centroid_x = float(full_x.mean())
            centroid_y = float(full_y.mean())
        gt_overlap = 0.0
        if gt_mask_crop is not None:
            gt_overlap = float(gt_mask_crop[y_local, x_local].sum() / area)
        components.append(
            {
                "area": area,
                "bbox_x0": bbox_x0,
                "bbox_y0": bbox_y0,
                "bbox_x1": bbox_x1,
                "bbox_y1": bbox_y1,
                "range_extent": range_extent,
                "azimuth_extent": azimuth_extent,
                "shape_type": shape_type,
                "fill_ratio": fill_ratio,
                "centroid_x": centroid_x,
                "centroid_y": centroid_y,
                "mean_value": float(values.mean()) if values.size else 0.0,
                "peak_value": float(values.max()) if values.size else 0.0,
                "gt_overlap_ratio": gt_overlap,
            }
        )
    components.sort(key=lambda item: (int(item["area"]), float(item["peak_value"])), reverse=True)
    return components


def atom_alignment_ratio(atoms: Sequence[Mapping[str, Any]]) -> float | None:
    if len(atoms) < 3:
        return None
    points = np.asarray([[float(atom["x"]), float(atom["y"])] for atom in atoms], dtype=np.float64)
    points -= points.mean(axis=0, keepdims=True)
    cov = np.cov(points.T)
    eigvals = np.linalg.eigvalsh(cov)
    if eigvals[0] <= 1e-6:
        return float("inf")
    return float(eigvals[-1] / eigvals[0])


def atom_edge_count(
    atoms: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> int:
    if not atoms:
        return 0
    rmin = float(context["support_radius_min_px"])
    rmax = float(context["support_radius_max_px"])
    amin = float(context["support_azimuth_start_deg"])
    amax = float(context["support_azimuth_end_deg"])
    rspan = max(1e-6, rmax - rmin)
    aspan = (amax - amin) % 360.0
    if aspan <= 0:
        aspan = 360.0
    count = 0
    for atom in atoms:
        rpos = (float(fan_radius(float(atom["x"]), float(atom["y"]))) - rmin) / rspan
        az = float(fan_azimuth(float(atom["x"]), float(atom["y"])))
        apos = ((az - amin) % 360.0) / aspan
        edge_distance = min(rpos, 1.0 - rpos, apos, 1.0 - apos)
        if edge_distance <= 0.15:
            count += 1
    return count


def extract_structure(
    arr: np.ndarray,
    context: Mapping[str, Any],
    box: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    x0, y0, x1, y1 = context["crop"]
    crop_arr = arr[y0:y1, x0:x1]
    mask_crop = context["mask_crop"]
    values = crop_arr[mask_crop]
    if values.size == 0:
        return {
            "status": "empty_support_region",
            "atoms": [],
            "components": [],
            "support_area_px": 0,
        }
    atom_threshold = float(np.quantile(values, ATOM_QUANTILE))
    component_threshold = float(np.quantile(values, COMPONENT_SUPPORT_QUANTILE))
    atoms = separated_local_maxima(crop_arr, mask_crop, atom_threshold, (x0, y0))
    gt_mask_crop = rotated_mask_for_crop(context["crop"], box)
    hot_crop = mask_crop & (crop_arr >= component_threshold)
    components = component_summaries(
        crop_arr,
        hot_crop,
        gt_mask_crop,
        (x0, y0),
        int(context["support_area_px"]),
    )
    inside_flags = points_inside_rotated_box(atoms, box)
    gt_inside_atoms = sum(1 for flag in inside_flags if flag)
    edge_count = atom_edge_count(atoms, context)
    alignment = atom_alignment_ratio(atoms)
    if atoms:
        atom_x = [float(atom["x"]) for atom in atoms]
        atom_y = [float(atom["y"]) for atom in atoms]
        atom_spread_x = max(atom_x) - min(atom_x)
        atom_spread_y = max(atom_y) - min(atom_y)
    else:
        atom_spread_x = 0.0
        atom_spread_y = 0.0
    dominant = components[0] if components else None
    dominant_area = int(dominant["area"]) if dominant else 0
    if box is not None and box_available(box):
        n_competing = sum(
            1
            for comp in components
            if float(comp["gt_overlap_ratio"]) < 0.10
            and int(comp["area"]) >= max(MIN_COMPONENT_AREA_PX, 0.25 * dominant_area)
        )
    else:
        n_competing = max(0, len(components) - 1)
    shape_mix = Counter(str(comp["shape_type"]) for comp in components)
    return {
        "status": "support_structure_extracted",
        "support_area_px": int(context["support_area_px"]),
        "support_mean": float(values.mean()),
        "support_peak": float(values.max()),
        "atom_threshold": atom_threshold,
        "component_threshold": component_threshold,
        "atoms": atoms,
        "components": components,
        "dominant_component": dominant,
        "n_gt_inside_atoms": gt_inside_atoms,
        "n_outside_gt_inside_support_atoms": len(atoms) - gt_inside_atoms,
        "n_competing_components_inside_support": n_competing,
        "edge_atom_count": edge_count,
        "atom_alignment_ratio": alignment,
        "atom_spread_x": atom_spread_x,
        "atom_spread_y": atom_spread_y,
        "component_shape_mix": dict(shape_mix),
    }


def structure_label(features: Mapping[str, Any]) -> str:
    n_atoms = int(features.get("n_support_energy_atoms_raw", 0))
    n_components = int(features.get("n_support_connected_components_raw", 0))
    shape = str(features.get("dominant_shape_raw", "uncertain"))
    edge_count = int(features.get("edge_atom_count", 0))
    competing = int(features.get("n_competing_components_inside_support_raw", 0))
    alignment = features.get("atom_alignment_ratio")
    aligned = alignment is not None and (math.isinf(float(alignment)) or float(alignment) >= 2.5)
    spread_x = float(features.get("atom_spread_x", 0.0))
    spread_y = float(features.get("atom_spread_y", 0.0))
    if shape in {"strip_like", "block_like", "shell_like"} and n_atoms >= 2 and competing <= 2:
        return "yes"
    if n_atoms >= 4 and aligned and spread_x >= 25.0 and spread_y >= 18.0 and competing <= 2:
        return "yes"
    if n_components >= 2 and n_atoms >= 4 and (edge_count >= 1 or aligned) and competing <= 2:
        return "yes"
    if n_atoms <= 1 and n_components <= 1 and shape == "point_like":
        return "no"
    return "uncertain"


def structure_note(features: Mapping[str, Any]) -> str:
    n_atoms = int(features.get("n_support_energy_atoms_raw", 0))
    n_components = int(features.get("n_support_connected_components_raw", 0))
    shape = str(features.get("dominant_shape_raw", "uncertain"))
    competing = int(features.get("n_competing_components_inside_support_raw", 0))
    if features.get("support_image_available") != "yes":
        return "SAR image unavailable; support-wide structure not extracted."
    if features.get("support_available") != "yes":
        return "Support unavailable; reference-only morphology, not paired support diagnosis."
    if structure_label(features) == "yes":
        return (
            f"Support-wide atoms/components form a {shape} structure; "
            f"atoms={n_atoms}, components={n_components}, competing={competing}."
        )
    if structure_label(features) == "no":
        return "Support contains only isolated point-like evidence under fixed diagnostic thresholds."
    return (
        f"Support-wide structure is uncertain under fixed thresholds; atoms={n_atoms}, "
        f"components={n_components}, dominant_shape={shape}, competing={competing}."
    )


def build_atom_component_rows(
    support_rows: Sequence[Mapping[str, Any]],
    corr_by_case: Mapping[str, Mapping[str, Any]],
    coverage_by_case: Mapping[str, Mapping[str, Any]],
    cache: SarImageCache,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    features_by_key: dict[str, dict[str, Any]] = {}
    for row_index, support in enumerate(support_rows, start=1):
        case_id = case_id_from_support(support)
        feature_key = str(support.get("peak_audit_id", "")).strip() or f"{case_id}__row{row_index:03d}"
        scene = str(support.get("scene", ""))
        sar_frame = str(support.get("sar_frame", ""))
        object_id = str(support.get("object_hypothesis_id", ""))
        corr = corr_by_case.get(case_id, {})
        coverage = coverage_by_case.get(case_id, {})
        box = gt_box_from_correspondence(corr) if corr else {}
        gt_available = bool(box and box_available(box))
        image_path = Path(str(support.get("sar_image_path", "")))
        arr = cache.image(image_path)
        base_feature: dict[str, Any] = {
            "feature_key": feature_key,
            "case_id": case_id,
            "scene": scene,
            "sar_frame": sar_frame,
            "object_hypothesis_id": object_id,
            "support_row": support,
            "corr_row": corr,
            "coverage_row": coverage,
            "box": box,
            "image_path": str(image_path),
            "support_available": "yes" if support_available(support) else "no",
            "support_image_available": "yes" if arr is not None else "no",
            "gt_available": "yes" if gt_available else "no",
        }
        if arr is None:
            raw = {
                "support_area_px": "",
                "atoms": [],
                "components": [],
                "dominant_component": None,
                "n_gt_inside_atoms": 0,
                "n_outside_gt_inside_support_atoms": 0,
                "n_competing_components_inside_support": 0,
                "component_shape_mix": {},
            }
            status_note = "SAR image unavailable."
        else:
            context = support_context(cache, arr.shape, support)
            base_feature["support_context"] = context
            if context is None:
                raw = {
                    "support_area_px": "",
                    "atoms": [],
                    "components": [],
                    "dominant_component": None,
                    "n_gt_inside_atoms": 0,
                    "n_outside_gt_inside_support_atoms": 0,
                    "n_competing_components_inside_support": 0,
                    "component_shape_mix": {},
                }
                status_note = "Support boundary unavailable or empty."
            else:
                raw = extract_structure(arr, context, box if gt_available else None)
                status_note = "Fixed thresholds: atoms=support p97 local maxima; components=support p85 connected regions."
        dominant = raw.get("dominant_component")
        components = list(raw.get("components", []))
        atoms = list(raw.get("atoms", []))
        dominant_shape = str(dominant.get("shape_type", "uncertain")) if dominant else "uncertain"
        base_feature.update(
            {
                "support_area_px_raw": raw.get("support_area_px", ""),
                "atoms": atoms,
                "components": components,
                "n_support_energy_atoms_raw": len(atoms),
                "n_support_connected_components_raw": len(components),
                "n_gt_inside_atoms_raw": int(raw.get("n_gt_inside_atoms", 0)),
                "n_outside_gt_inside_support_atoms_raw": int(
                    raw.get("n_outside_gt_inside_support_atoms", 0)
                ),
                "n_competing_components_inside_support_raw": int(
                    raw.get("n_competing_components_inside_support", 0)
                ),
                "dominant_component": dominant,
                "dominant_shape_raw": dominant_shape,
                "edge_atom_count": int(raw.get("edge_atom_count", 0)),
                "atom_alignment_ratio": raw.get("atom_alignment_ratio"),
                "atom_spread_x": float(raw.get("atom_spread_x", 0.0)),
                "atom_spread_y": float(raw.get("atom_spread_y", 0.0)),
                "component_shape_mix_raw": dict(raw.get("component_shape_mix", {})),
            }
        )
        label = structure_label(base_feature)
        base_feature["energy_atoms_form_vehicle_structure"] = label
        note = structure_note(base_feature)
        atom_component_row = {
            "case_id": case_id,
            "scene": scene,
            "sar_frame": sar_frame,
            "object_hypothesis_id": object_id,
            "support_available": base_feature["support_available"],
            "support_source": support_source(support, coverage),
            "gt_available": base_feature["gt_available"],
            "support_area_px": raw.get("support_area_px", ""),
            "n_support_energy_atoms": len(atoms),
            "n_support_connected_components": len(components),
            "n_gt_inside_atoms": int(raw.get("n_gt_inside_atoms", 0)),
            "n_outside_gt_inside_support_atoms": int(
                raw.get("n_outside_gt_inside_support_atoms", 0)
            ),
            "n_competing_components_inside_support": int(
                raw.get("n_competing_components_inside_support", 0)
            ),
            "dominant_component_area": int(dominant["area"]) if dominant else "",
            "dominant_component_range_extent": fmt(dominant["range_extent"], 4) if dominant else "",
            "dominant_component_azimuth_extent": fmt(dominant["azimuth_extent"], 4)
            if dominant
            else "",
            "dominant_component_shape_type": dominant_shape,
            "energy_atoms_form_vehicle_structure": label,
            "peaks_alone_sufficient": "no" if base_feature["support_available"] == "yes" else "uncertain",
            "support_wide_structure_note": note,
            "posthoc_gt_relation_validation_only": (
                "GT relation columns use SAR GT only for posthoc validation; "
                "they are not runtime prediction logic."
            ),
            "notes": status_note,
            "support_image_available": base_feature["support_image_available"],
            "atom_threshold_rule": f"fixed support p{int(ATOM_QUANTILE * 100)} local maxima",
            "component_threshold_rule": f"fixed support p{int(COMPONENT_SUPPORT_QUANTILE * 100)} connected components",
            "top_atom_points_support_wide": compact_points(atoms),
            "component_shape_mix": compact_counts(
                str(comp.get("shape_type", "")) for comp in components
            ),
        }
        rows.append(atom_component_row)
        base_feature["atom_component_row"] = atom_component_row
        features_by_key[feature_key] = base_feature
    return rows, features_by_key


def proxy_definitions() -> list[dict[str, str]]:
    return [
        {
            "proxy_name": "dominant_side_ridge_proxy",
            "mechanism_meaning": "A large elongated component can act as a body-side ridge or boundary strip.",
            "input_source": "support-wide connected component shape under fixed p90/p95 rule",
            "runtime_safe": "no; posthoc SAR image diagnostic only",
            "SAR_observation": "dominant component shape_type and extent",
            "posthoc_validation_fields": "GT overlap ratio is used only for validation",
            "calculation_method_public": "strip_like or shell_like dominant component",
            "known_limitations": "display grayscale and image-axis geometry do not prove physical near/far side",
            "what_it_can_explain": "why a car may appear as a side strip rather than a center peak",
            "what_it_cannot_explain": "identity truth or final localization",
        },
        {
            "proxy_name": "facing_side_hotspot_proxy",
            "mechanism_meaning": "Strong atoms may reflect facing-side or endpoint scattering.",
            "input_source": "support-wide p97 local maxima",
            "runtime_safe": "no; SAR observation diagnostic only",
            "SAR_observation": "atom count and peak/support contrast",
            "posthoc_validation_fields": "GT-inside atom count",
            "calculation_method_public": "at least two high-energy atoms under fixed p97 rule",
            "known_limitations": "hotspots may be background or neighbor scatterers",
            "what_it_can_explain": "why a vehicle contains multiple high-energy atoms",
            "what_it_cannot_explain": "that any one atom is the vehicle",
        },
        {
            "proxy_name": "endpoint_or_corner_reflector_proxy",
            "mechanism_meaning": "Atoms near support boundary can be endpoint/corner candidates.",
            "input_source": "support-wide atom positions relative to support radial/azimuth edges",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "edge_atom_count",
            "posthoc_validation_fields": "GT relation optional validation",
            "calculation_method_public": "atom within fixed 15% support-edge band",
            "known_limitations": "support edge is optical-derived and may be shifted",
            "what_it_can_explain": "endpoint/corner high-energy regions",
            "what_it_cannot_explain": "head/tail truth",
        },
        {
            "proxy_name": "far_side_weak_return_proxy",
            "mechanism_meaning": "Secondary weaker components can be far-side or weak body return candidates.",
            "input_source": "multiple support components and component area ratios",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "secondary components weaker/smaller than dominant component",
            "posthoc_validation_fields": "none required",
            "calculation_method_public": "component count and secondary/dominant area ratio",
            "known_limitations": "physical far side is not calibrated",
            "what_it_can_explain": "asymmetric strong/weak vehicle body response",
            "what_it_cannot_explain": "physical side identity",
        },
        {
            "proxy_name": "discontinuous_aligned_edges_proxy",
            "mechanism_meaning": "Separated atoms aligned along one axis may form discontinuous body edges.",
            "input_source": "support-wide p97 atoms",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "PCA alignment ratio over atoms",
            "posthoc_validation_fields": "GT-inside atoms optional validation",
            "calculation_method_public": "fixed PCA eigenvalue ratio >= 2.5",
            "known_limitations": "road edges and guardrails can also align",
            "what_it_can_explain": "non-continuous strips that still look vehicle-like",
            "what_it_cannot_explain": "object identity",
        },
        {
            "proxy_name": "strip_plus_corner_composition_proxy",
            "mechanism_meaning": "A strip component plus edge atom can represent strip + endpoint/corner composition.",
            "input_source": "dominant component shape and edge atom count",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "strip_like/shell_like component and edge atoms",
            "posthoc_validation_fields": "GT overlap optional validation",
            "calculation_method_public": "strip/shell dominant component and edge_atom_count >= 1",
            "known_limitations": "depends on support reconstruction",
            "what_it_can_explain": "vehicle side strip with endpoint hotspot",
            "what_it_cannot_explain": "final annotation",
        },
        {
            "proxy_name": "multi_peak_enclosed_shell_proxy",
            "mechanism_meaning": "Multiple atoms/components spanning both image axes may form a shell-like body.",
            "input_source": "support-wide atoms and components",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "atom count, component count, atom spread",
            "posthoc_validation_fields": "GT relation optional validation",
            "calculation_method_public": ">=4 atoms, >=2 components, x/y spread thresholds",
            "known_limitations": "multi-vehicle arrangements can mimic a shell",
            "what_it_can_explain": "vehicle body made from multiple scatter atoms",
            "what_it_cannot_explain": "single-object certainty",
        },
        {
            "proxy_name": "block_like_vehicle_body_proxy",
            "mechanism_meaning": "A compact bright block can represent a body-core morphology.",
            "input_source": "dominant connected component",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "block_like dominant component",
            "posthoc_validation_fields": "GT overlap optional validation",
            "calculation_method_public": "fixed fill-ratio and area heuristic",
            "known_limitations": "small objects and background structures may be block-like",
            "what_it_can_explain": "compact vehicle core response",
            "what_it_cannot_explain": "class identity",
        },
        {
            "proxy_name": "range_spread_with_core_proxy",
            "mechanism_meaning": "A range-spread component with a core can preserve vehicle morphology.",
            "input_source": "dominant component range extent and area",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "range_extent >= 60 px with non-trivial component area",
            "posthoc_validation_fields": "GT relation optional validation",
            "calculation_method_public": "fixed range extent and area thresholds",
            "known_limitations": "spread mechanism is a hypothesis, not a physical proof",
            "what_it_can_explain": "why diffuse/range-spread samples should not be rejected directly",
            "what_it_cannot_explain": "motion physics certainty",
        },
        {
            "proxy_name": "support_wide_vehicle_shell_proxy",
            "mechanism_meaning": "Aggregate support-wide shell/body structure evidence.",
            "input_source": "all support-wide proxy labels",
            "runtime_safe": "no; posthoc diagnostic only",
            "SAR_observation": "count of supportive shell/body proxies",
            "posthoc_validation_fields": "GT relation is validation only",
            "calculation_method_public": ">=7 supportive proxies and <=1 competing component => yes; otherwise uncertain/no",
            "known_limitations": "not calibrated for selection or annotation",
            "what_it_can_explain": "whether support-wide atoms organize into a relatively clean vehicle-like structure",
            "what_it_cannot_explain": "selector success or final target identity",
        },
    ]


def proxy_rows_for_case(features: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    case_id = str(features["case_id"])
    n_atoms = int(features.get("n_support_energy_atoms_raw", 0))
    n_components = int(features.get("n_support_connected_components_raw", 0))
    shape = str(features.get("dominant_shape_raw", "uncertain"))
    dominant = features.get("dominant_component") or {}
    components = list(features.get("components", []))
    edge_count = int(features.get("edge_atom_count", 0))
    alignment = features.get("atom_alignment_ratio")
    alignment_value = float(alignment) if alignment is not None and not math.isinf(float(alignment)) else math.inf
    atom_spread_x = float(features.get("atom_spread_x", 0.0))
    atom_spread_y = float(features.get("atom_spread_y", 0.0))
    range_extent = float(dominant.get("range_extent", 0.0)) if dominant else 0.0
    dom_area = int(dominant.get("area", 0)) if dominant else 0
    secondary_area = int(components[1]["area"]) if len(components) > 1 else 0
    secondary_ratio = secondary_area / max(dom_area, 1)
    available = features.get("support_available") == "yes" and features.get("support_image_available") == "yes"

    evaluations: list[tuple[str, bool, str, str]] = [
        (
            "dominant_side_ridge_proxy",
            available and shape in {"strip_like", "shell_like"},
            shape,
            f"dominant_shape={shape}; range_extent={fmt(range_extent, 3)}",
        ),
        (
            "facing_side_hotspot_proxy",
            available and n_atoms >= 2,
            f"atoms={n_atoms}",
            f"{n_atoms} support-wide p97 atoms",
        ),
        (
            "endpoint_or_corner_reflector_proxy",
            available and edge_count >= 1,
            f"edge_atoms={edge_count}",
            "atoms within fixed 15% support-edge band",
        ),
        (
            "far_side_weak_return_proxy",
            available and n_components >= 2 and 0.05 <= secondary_ratio <= 0.75,
            f"secondary_ratio={fmt(secondary_ratio, 4)}",
            "secondary component is smaller than dominant component; physical far-side not asserted",
        ),
        (
            "discontinuous_aligned_edges_proxy",
            available and n_atoms >= 3 and alignment_value >= 2.5,
            f"alignment_ratio={fmt(alignment_value, 4) if math.isfinite(alignment_value) else 'inf'}",
            "support-wide atoms are elongated under fixed PCA proxy",
        ),
        (
            "strip_plus_corner_composition_proxy",
            available and shape in {"strip_like", "shell_like"} and edge_count >= 1,
            f"shape={shape}; edge_atoms={edge_count}",
            "strip/shell component plus endpoint/corner atom proxy",
        ),
        (
            "multi_peak_enclosed_shell_proxy",
            available and n_atoms >= 4 and n_components >= 2 and atom_spread_x >= 25 and atom_spread_y >= 18,
            f"atoms={n_atoms}; components={n_components}; spread={fmt(atom_spread_x, 1)}x{fmt(atom_spread_y, 1)}",
            "multiple support-wide atoms/components span a body-like extent",
        ),
        (
            "block_like_vehicle_body_proxy",
            available and shape == "block_like",
            shape,
            "dominant component is block_like under fixed fill-ratio heuristic",
        ),
        (
            "range_spread_with_core_proxy",
            available and range_extent >= 60.0 and dom_area >= 20,
            f"range_extent={fmt(range_extent, 3)}; area={dom_area}",
            "range spread with non-trivial core component",
        ),
    ]
    supportive_count = sum(1 for _, ok, _, _ in evaluations if ok)
    competing = int(features.get("n_competing_components_inside_support_raw", 0))
    if not available:
        aggregate = "unavailable"
        aggregate_supported = "uncertain"
    elif supportive_count >= 7 and competing <= 1:
        aggregate = f"supportive_proxy_count={supportive_count}"
        aggregate_supported = "yes"
    elif supportive_count >= 1:
        aggregate = f"supportive_proxy_count={supportive_count}"
        aggregate_supported = "uncertain"
    else:
        aggregate = "supportive_proxy_count=0"
        aggregate_supported = "no"
    evaluations.append(
        (
            "support_wide_vehicle_shell_proxy",
            aggregate_supported == "yes",
            aggregate,
            "aggregate of fixed support-wide shell/body proxies",
        )
    )

    rows: list[dict[str, Any]] = []
    for name, ok, value, evidence in evaluations:
        if not available:
            proxy_available = "no"
            supported = "uncertain"
            failure = "support or SAR image unavailable"
        elif name == "support_wide_vehicle_shell_proxy":
            proxy_available = "yes"
            supported = aggregate_supported
            failure = "" if supported == "yes" else "insufficient support-wide proxy agreement"
        else:
            proxy_available = "yes"
            supported = "yes" if ok else "no"
            failure = "" if ok else "proxy condition not met under fixed diagnostic rule"
        rows.append(
            {
                "case_id": case_id,
                "proxy_name": name,
                "proxy_available": proxy_available,
                "proxy_value_or_label": value,
                "evidence_summary": evidence,
                "vehicle_shell_supported": supported,
                "main_failure_reason": failure,
                "manual_review_needed": "yes"
                if supported != "yes"
                or int(features.get("n_competing_components_inside_support_raw", 0)) > 0
                else "no",
                "notes": "Posthoc support-wide morphology proxy only; not a selector feature.",
            }
        )
    return rows, aggregate_supported


def build_proxy_rows(
    features_by_key: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    aggregate_by_key: dict[str, str] = {}
    for feature_key, features in features_by_key.items():
        case_rows, aggregate = proxy_rows_for_case(features)
        rows.extend(case_rows)
        aggregate_by_key[feature_key] = aggregate
    return rows, aggregate_by_key


def failure_types_for_case(features: Mapping[str, Any], aggregate_proxy: str) -> list[str]:
    coverage = features.get("coverage_row") or {}
    corr = features.get("corr_row") or {}
    support = features.get("support_row") or {}
    types: list[str] = []
    if features.get("support_available") != "yes":
        return ["reference_only_no_support"]
    area_cov = safe_float(coverage.get("gt_area_coverage_ratio"))
    energy_cov = safe_float(coverage.get("gt_energy_coverage_ratio"))
    morph_cov = safe_float(coverage.get("morphology_primitive_coverage_proxy"))
    az_aligned = is_true(corr.get("azimuth_prior_contains_gt")) or is_true(
        support.get("gt_inside_support_posthoc")
    )
    range_aligned = is_true(corr.get("range_shell_contains_gt")) or is_true(
        support.get("gt_radius_inside_posthoc")
    )
    band_width = safe_float(support.get("radius_band_width_px"))
    state_condition = str(support.get("state_condition", ""))
    truncation_state = str(coverage.get("truncation_or_occlusion_state", ""))
    optical_state = ";".join(
        str(value)
        for value in [
            coverage.get("optical_state", ""),
            coverage.get("truncation_or_occlusion_state", ""),
            corr.get("visibility_state", ""),
            corr.get("edge_partial_duplicate_handoff_ambiguity_flags", ""),
        ]
        if value
    )
    if az_aligned and not range_aligned:
        types.append("azimuth_aligned_range_misaligned")
    if any(value is not None and value < 0.80 for value in [area_cov, energy_cov, morph_cov]):
        types.append("support_too_narrow")
    support_area = safe_float(support.get("support_area_px")) or 0.0
    area_ratio = safe_float(support.get("area_ratio_vs_broad")) or 0.0
    local_peak_count = safe_float(support.get("local_peak_count_above_bg_p95")) or 0.0
    if area_ratio >= 0.12 or support_area >= 50000.0 or (
        is_true(coverage.get("support_too_broad_for_unique_association"))
        and local_peak_count >= 35.0
    ):
        types.append("support_too_broad")
    if band_width is not None and band_width < 90.0 and any(
        value is not None and value < 0.85 for value in [area_cov, energy_cov, morph_cov]
    ):
        types.append("range_compression_too_strong")
    is_truncated = (
        state_condition == "edge_or_truncated"
        or "state_condition=edge_or_truncated" in truncation_state
        or "boundary_truncation_present" in truncation_state
    )
    if is_truncated:
        types.append("optical_truncation_induced_shift")
    gt_radius = safe_float(support.get("gt_radius_px_posthoc"))
    if gt_radius is not None and gt_radius < 450.0 and is_truncated:
        types.append("near_field_truncation_issue")
    if state_condition in {
        "edge_or_truncated",
        "duplicate_or_handoff",
        "ambiguous_or_review_only",
        "far_small_or_weak",
    }:
        types.append("state_compensation_missing")
    if state_condition in {"edge_or_truncated", "ambiguous_or_review_only", "duplicate_or_handoff"}:
        types.append("temporal_compensation_needed")
    if int(features.get("n_competing_components_inside_support_raw", 0)) >= 1:
        types.append("support_contains_neighbor_structure")
    if (
        all(value is not None and value >= 0.80 for value in [area_cov, energy_cov, morph_cov])
        and aggregate_proxy in {"yes", "uncertain"}
    ):
        types.append("support_ok_but_not_exclusive")
    if not types:
        types.append("support_reconstruction_uncertain")
    return list(dict.fromkeys(types))


def alignment_status(corr: Mapping[str, Any], support: Mapping[str, Any], kind: str) -> str:
    if kind == "azimuth":
        if is_true(corr.get("azimuth_prior_contains_gt")) or is_true(support.get("gt_inside_support_posthoc")):
            return "aligned_posthoc"
        if str(corr.get("azimuth_prior_contains_gt", "")).strip():
            return "misaligned_posthoc"
    if kind == "range":
        if is_true(corr.get("range_shell_contains_gt")) or is_true(support.get("gt_radius_inside_posthoc")):
            return "aligned_posthoc"
        if str(corr.get("range_shell_contains_gt", "")).strip() or str(
            support.get("gt_radius_inside_posthoc", "")
        ).strip():
            return "misaligned_posthoc"
    return "uncertain"


def main_energy_relative_to_support(
    coverage: Mapping[str, Any],
    gt_energy: Mapping[str, Any] | None,
    features: Mapping[str, Any],
) -> str:
    morph_cov = safe_float(coverage.get("morphology_primitive_coverage_proxy"))
    energy_cov = safe_float(coverage.get("gt_energy_coverage_ratio"))
    dominant_region = str((gt_energy or {}).get("dominant_energy_region", "unknown"))
    if morph_cov is not None and morph_cov >= 0.80:
        return f"main_energy_strip_inside_support_proxy;gt_dominant={dominant_region}"
    if energy_cov is not None and energy_cov < 0.80:
        return f"support_misses_or_shifts_gt_high_energy_proxy;gt_dominant={dominant_region}"
    if int(features.get("n_competing_components_inside_support_raw", 0)) > 0:
        return "support_contains_competing_non_gt_energy_structure"
    return f"uncertain;gt_dominant={dominant_region}"


def recommended_action(types: Sequence[str], aggregate_proxy: str) -> str:
    joined = ";".join(types)
    if "azimuth_aligned_range_misaligned" in joined or "range_compression_too_strong" in joined:
        return "review range mapping and motion/drift compatibility; do not tune selector"
    if "optical_truncation_induced_shift" in joined or "near_field_truncation_issue" in joined:
        return "review state compensation and temporal continuation"
    if "support_contains_neighbor_structure" in joined:
        return "manual association review with support-wide atlas and temporal context"
    if aggregate_proxy == "yes":
        return "preserve as posthoc morphology support; keep association layer separate"
    return "manual review or phase recap; no final annotation"


def build_failure_rows(
    features_by_key: Mapping[str, Mapping[str, Any]],
    aggregate_proxy_by_key: Mapping[str, str],
    gt_energy_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature_key, features in features_by_key.items():
        case_id = str(features["case_id"])
        coverage = features.get("coverage_row") or {}
        corr = features.get("corr_row") or {}
        support = features.get("support_row") or {}
        gt_id = str(corr.get("sar_gt_id", ""))
        gt_energy = gt_energy_by_key.get((str(features["scene"]), str(features["sar_frame"]), gt_id))
        aggregate = aggregate_proxy_by_key.get(feature_key, "uncertain")
        types = failure_types_for_case(features, aggregate)
        neighbor = (
            "yes"
            if "support_contains_neighbor_structure" in types
            or "serious" in str(support.get("peak_competition_label", ""))
            else "uncertain"
        )
        optical_state = ";".join(
            str(value)
            for value in [
                coverage.get("optical_state", ""),
                coverage.get("truncation_or_occlusion_state", ""),
            ]
            if value
        )
        rows.append(
            {
                "case_id": case_id,
                "scene": features["scene"],
                "sar_frame": features["sar_frame"],
                "optical_state": optical_state or str(support.get("state_condition", "")),
                "support_failure_type": ";".join(types),
                "azimuth_alignment_status": alignment_status(corr, support, "azimuth"),
                "range_alignment_status": alignment_status(corr, support, "range"),
                "gt_area_coverage_ratio": coverage.get("gt_area_coverage_ratio", ""),
                "gt_energy_coverage_ratio": coverage.get("gt_energy_coverage_ratio", ""),
                "morphology_coverage_proxy": coverage.get("morphology_primitive_coverage_proxy", ""),
                "main_energy_strip_relative_to_support": main_energy_relative_to_support(
                    coverage, gt_energy, features
                ),
                "neighbor_or_background_interference": neighbor,
                "human_review_note": (
                    "support coverage, SAR morphology strength, and optical-SAR association "
                    "remain separate review layers"
                ),
                "recommended_next_action": recommended_action(types, aggregate),
                "not_allowed_conclusion": (
                    "not final annotation; not selector success; not identity truth; "
                    "not GT-guided prediction logic"
                ),
            }
        )
    return rows


def temporal_snapshot(
    arr: np.ndarray,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    raw = extract_structure(arr, context, None)
    atoms = list(raw.get("atoms", []))
    components = list(raw.get("components", []))
    dominant = components[0] if components else None
    if dominant:
        centroid = (float(dominant["centroid_x"]), float(dominant["centroid_y"]))
        shape = str(dominant["shape_type"])
    elif atoms:
        centroid = (float(atoms[0]["x"]), float(atoms[0]["y"]))
        shape = "point_like"
    else:
        centroid = None
        shape = "unavailable"
    return {
        "present": bool(atoms or components),
        "atoms": len(atoms),
        "components": len(components),
        "centroid": centroid,
        "shape": shape,
        "ridge_like": shape in {"strip_like", "shell_like"},
        "shell_like": shape in {"shell_like", "block_like", "strip_like"},
    }


def direction_label(dx: float, dy: float) -> str:
    if abs(dx) < 3.0 and abs(dy) < 3.0:
        return "near_stationary"
    horiz = "right" if dx > 0 else "left"
    vert = "down" if dy > 0 else "up"
    if abs(dx) >= abs(dy) * 1.6:
        return horiz
    if abs(dy) >= abs(dx) * 1.6:
        return vert
    return f"{horiz}_{vert}"


def centroid_drift_summary(points: Sequence[tuple[float, float]]) -> tuple[str, float, float]:
    if len(points) < 2:
        return "", 0.0, 0.0
    steps = [
        math.hypot(points[idx][0] - points[idx - 1][0], points[idx][1] - points[idx - 1][1])
        for idx in range(1, len(points))
    ]
    total = math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1])
    return f"total={fmt(total, 3)};median_step={median_text(steps)};max_step={fmt(max(steps), 3)}", total, max(steps)


def build_temporal_rows(
    features_by_key: Mapping[str, Mapping[str, Any]],
    cache: SarImageCache,
) -> list[dict[str, Any]]:
    object_case_counts = Counter(
        (str(features.get("scene", "")), str(features.get("object_hypothesis_id", "")))
        for features in features_by_key.values()
    )
    rows: list[dict[str, Any]] = []
    for _feature_key, features in features_by_key.items():
        case_id = str(features["case_id"])
        support = features.get("support_row") or {}
        current_context = features.get("support_context")
        scene = str(features["scene"])
        current_frame = safe_int(features.get("sar_frame"))
        for window_size, offsets in WINDOW_OFFSETS.items():
            snapshots: list[dict[str, Any]] = []
            used_offsets: list[int] = []
            if current_context is not None and current_frame is not None:
                for offset in offsets:
                    frame = current_frame + offset
                    path = sar_path(scene, frame)
                    arr = cache.image(path)
                    if arr is None:
                        continue
                    context = current_context
                    if arr.shape != cache.image(Path(str(features.get("image_path")))).shape:
                        context = support_context(cache, arr.shape, support)
                    if context is None:
                        continue
                    snapshots.append({"offset": offset, **temporal_snapshot(arr, context)})
                    used_offsets.append(offset)
            available = len(snapshots) >= 2
            present_count = sum(1 for snap in snapshots if snap["present"])
            ridge_count = sum(1 for snap in snapshots if snap["ridge_like"])
            shell_count = sum(1 for snap in snapshots if snap["shell_like"])
            points = [snap["centroid"] for snap in snapshots if snap.get("centroid") is not None]
            drift_text, total_drift, max_step = centroid_drift_summary(points)  # type: ignore[arg-type]
            direction = ""
            if len(points) >= 2:
                direction = direction_label(points[-1][0] - points[0][0], points[-1][1] - points[0][1])
            persistence = present_count / max(1, len(snapshots)) if snapshots else 0.0
            gradual = "uncertain"
            if len(points) >= 3:
                gradual = "yes" if max_step <= 80.0 else "no"
            vehicle_like = "uncertain"
            background_stable = "uncertain"
            if not available:
                vehicle_like = "uncertain"
                background_stable = "uncertain"
                reason = "temporal data unavailable or fewer than two frames inside window"
            elif persistence >= 0.60 and gradual == "yes" and total_drift > 5.0:
                vehicle_like = "yes"
                background_stable = "no"
                reason = "support-wide structure persists and drifts gradually"
            elif persistence >= 0.75 and total_drift <= 5.0:
                vehicle_like = "uncertain"
                background_stable = "yes"
                reason = "persistent structure is nearly stationary; background-stable risk"
            elif persistence < 0.40:
                vehicle_like = "no"
                background_stable = "uncertain"
                reason = "support-wide structure is not persistent in this window"
            else:
                reason = "temporal evidence mixed under fixed window rule"
            obj_key = (scene, str(features.get("object_hypothesis_id", "")))
            compatible = "uncertain"
            if object_case_counts[obj_key] >= 3 and vehicle_like == "yes":
                compatible = "yes"
            elif object_case_counts[obj_key] < 2:
                compatible = "uncertain"
            rows.append(
                {
                    "case_id": case_id,
                    "scene": scene,
                    "object_hypothesis_id": features.get("object_hypothesis_id", ""),
                    "sar_frame": features.get("sar_frame", ""),
                    "window_size": window_size,
                    "frame_offsets_used": ";".join(str(offset) for offset in used_offsets),
                    "temporal_data_available": "yes" if available else "no",
                    "dominant_structure_persistence": rate_text(present_count, len(snapshots)),
                    "hotspot_drift_available": "yes" if len(points) >= 2 else "no",
                    "hotspot_drift_direction": direction,
                    "component_centroid_drift": drift_text,
                    "ridge_or_strip_persistence": rate_text(ridge_count, len(snapshots)),
                    "shell_structure_persistence": rate_text(shell_count, len(snapshots)),
                    "structure_changes_gradually": gradual,
                    "possible_vehicle_like_temporal_tube": vehicle_like,
                    "possible_background_stable_structure": background_stable,
                    "compatible_with_optical_tracklet_motion": compatible,
                    "main_temporal_failure_reason": reason,
                    "notes": (
                        "Temporal support reuse is posthoc morphology drift diagnosis only; "
                        "not an identity tube or final track."
                    ),
                }
            )
    return rows


def panel_correction_notes(card_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    note_data = [
        (
            "Panel 1",
            "support 与 GT 重叠弱；高能角点/条带在 support 下面。",
            "support 可能偏移或重建不足。",
            "support_offset_or_reconstruction_issue",
            "需要看全域条带是否随时序迁移。",
            "邻车不应简单作为竞争解释。",
            "不能只看 GT 局部亮点；需要看 support 全域结构。",
            "review support reconstruction and range alignment",
        ),
        (
            "Panel 2",
            "GT 被 support 包裹；高能点形成水平带和竖直带，可组成 car。",
            "support 覆盖主结构。",
            "support_ok_but_not_exclusive",
            "可补看时序确认多峰是否稳定。",
            "邻近主要是花坛/背景，车体自洽。",
            "多峰/条带可构成结构，不是孤立峰。",
            "preserve as strong morphology anchor; association separate",
        ),
        (
            "Panel 3",
            "明显近场截断/光学信息问题；扩散中心仍是高能区域。",
            "support may need state compensation.",
            "near_field_truncation_issue",
            "use temporal continuation to separate drift from background.",
            "需区分扩散、背景噪声和车体结构。",
            "diffuse 不能直接等于 reject。",
            "review truncation/state and temporal compensation",
        ),
        (
            "Panel 4",
            "强侧边条带在该样本中是车体结构。",
            "support 是参考，不是可直接使用规则。",
            "support_ok_but_rule_not_final",
            "能量分布会随雷达相对位置变化。",
            "邻车/方位重叠仍需复核。",
            "强侧边条带是 morphology anchor，不是 final rule。",
            "inspect support-wide ridge and temporal persistence",
        ),
        (
            "Panel 5",
            "应看 10 帧后最高能区域相对车体条带的位置变化。",
            "single-frame support insufficient for this question.",
            "temporal_compensation_needed",
            "check -5/0/+5 and 10-frame drift.",
            "车/雷达相对位置影响热点位置。",
            "时序 non-jump / gradual drift 是核心机制。",
            "run motion/drift compatibility review",
        ),
        (
            "Panel 6",
            "截断未处理好；GT 框内峰点像车形。",
            "support may miss weak/discontinuous structure.",
            "optical_truncation_induced_shift",
            "check whether weak structure persists.",
            "不要因结构弱就否定。",
            "weak/diffuse 仍可能是 vehicle morphology.",
            "review truncation plus support-wide weak structure",
        ),
        (
            "Panel 7",
            "结构还行但可能混淆。",
            "若用峰点，应看 support 全域。",
            "support_contains_neighbor_structure",
            "temporal context needed to resolve confusion.",
            "background-stable or neighboring object risk.",
            "peak-level judgment must expand to support-wide structure.",
            "manual review with temporal context",
        ),
        (
            "Panel 8",
            "车体内部结构自洽。",
            "support can be reviewed with neighboring/repeated fan overlap in mind.",
            "support_ok_but_not_exclusive",
            "combine temporal context for neighbor/overlap fan bands.",
            "邻近车/重合扇带混淆。",
            "SAR morphology strong and association review can both be true.",
            "separate morphology strength from association",
        ),
        (
            "Panel 9",
            "方位对齐但径向未对齐；support 径向压缩偏强。",
            "support range band too compressed.",
            "azimuth_aligned_range_misaligned",
            "use temporal flow and vehicle long-axis cue.",
            "support overlap and truncation possible.",
            "coverage failure points to range/support reconstruction, not SAR morphology failure.",
            "review range mapping and motion/drift compatibility",
        ),
        (
            "Panel 10",
            "与 Panel 9 同一车相邻时序，问题类似。",
            "support range issue repeats in adjacent frame.",
            "azimuth_aligned_range_misaligned",
            "compare adjacent frames for gradual drift.",
            "same-object temporal repetition remains hypothesis only.",
            "adjacent-frame consistency supports diagnosis but not identity truth.",
            "review as paired temporal case with Panel 9",
        ),
        (
            "Panel 11",
            "association 概念需明确；多车排列也是信息。",
            "support coverage cannot be read as identity.",
            "support_ok_but_not_exclusive",
            "relative position can help temporal reasoning.",
            "multi-vehicle arrangement.",
            "association is optical hypothesis to SAR structure, not GT truth.",
            "manual association review using relative position",
        ),
        (
            "Panel 12",
            "峰点围成车；边缘能量弱但仍有结构。",
            "paired support unavailable; reference-only.",
            "reference_only_no_support",
            "use as temporal validation supplement only.",
            "SAR-only edge/boundary case.",
            "SAR-only cannot enter paired correspondence.",
            "keep as SAR morphology reference",
        ),
        (
            "Panel 13",
            "近场容易逸散/发散；高能对岸体现结构，车体两侧条带合理。",
            "GM_RM011 support unavailable until object stream exists.",
            "reference_only_no_support",
            "future object stream needed before paired temporal diagnosis.",
            "near-field truncation and GM_RM011 missing object stream.",
            "GM_RM011 blocked is not unannotated and not paired here.",
            "keep as reference; do not mix into paired pool",
        ),
    ]
    rows: list[dict[str, Any]] = []
    by_panel = {str(row.get("panel_index", "")): row for row in card_rows}
    for idx, data in enumerate(note_data, start=1):
        card = by_panel.get(str(idx), {})
        rows.append(
            {
                "panel_id": data[0],
                "case_id": card.get("case_id", ""),
                "human_structure_observation": data[1],
                "support_observation": data[2],
                "support_failure_hypothesis": data[3],
                "temporal_hypothesis": data[4],
                "confounder_note": data[5],
                "concept_correction": data[6],
                "recommended_next_action": data[7],
            }
        )
    return rows


def parse_json_points(text: Any) -> list:
    value = str(text or "").strip()
    if not value:
        return []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


def draw_base_axis(
    ax: Any,
    crop_arr: np.ndarray,
    title: str,
    gt_local: Sequence[Sequence[float]] | None = None,
    support_local_lines: Sequence[Sequence[Sequence[float]]] | None = None,
    atoms_local: Sequence[tuple[float, float]] | None = None,
    components_local: Sequence[tuple[float, float, float, float, str]] | None = None,
) -> None:
    h, w = crop_arr.shape[:2]
    ax.imshow(crop_arr, cmap="gray", origin="upper", extent=(0, w, h, 0))
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.set_aspect("equal")
    ax.set_title(title, fontproperties=FONT, fontsize=9)
    ax.tick_params(labelsize=6)
    ax.grid(color="#4a9cff", alpha=0.15, linewidth=0.5)
    if gt_local:
        ax.add_patch(Polygon(gt_local, closed=True, fill=False, edgecolor="#ffd400", linewidth=2.0))
    if support_local_lines:
        closed = support_closed_polygon(
            [[(float(x), float(y)) for x, y in line] for line in support_local_lines]
        )
        if closed:
            ax.add_patch(Polygon(closed, closed=True, fill=True, facecolor="#ff00aa", alpha=0.10))
        for line in support_local_lines:
            if line:
                xs, ys = zip(*[(float(x), float(y)) for x, y in line])
                ax.plot(xs, ys, color="#ff00cc", linewidth=1.3)
    if components_local:
        for x0, y0, x1, y1, shape in components_local[:6]:
            color = "#00d084" if shape in {"strip_like", "shell_like", "block_like"} else "#74c0fc"
            ax.add_patch(
                Rectangle((x0, y0), max(1.0, x1 - x0), max(1.0, y1 - y0), fill=False, edgecolor=color, linewidth=1.4)
            )
    if atoms_local:
        xs, ys = zip(*atoms_local)
        ax.scatter(xs, ys, s=16, facecolors="none", edgecolors="#ff5a00", linewidths=1.1)


def temporal_image_path(current_path: str, offset: int) -> str:
    path = Path(str(current_path or ""))
    if not path.exists():
        return ""
    try:
        frame = int(path.stem)
    except ValueError:
        return str(path) if offset == 0 else ""
    candidate = path.with_name(f"{frame + offset:06d}{path.suffix}")
    return str(candidate) if candidate.exists() else ""


def render_atlas_panel(
    idx: int,
    geometry: Mapping[str, Any],
    card: Mapping[str, Any],
    features: Mapping[str, Any] | None,
    failure: Mapping[str, Any] | None,
    output_path: Path,
) -> None:
    image_path = str(geometry.get("image_path", ""))
    with plt.rc_context({"axes.unicode_minus": False}):
        arr = np.asarray(plt.imread(image_path))
    if arr.ndim == 3:
        crop_source = arr[:, :, 0]
    else:
        crop_source = arr
    crop = (
        safe_int(geometry.get("crop_x0"), 0) or 0,
        safe_int(geometry.get("crop_y0"), 0) or 0,
        safe_int(geometry.get("crop_x1"), 0) or 0,
        safe_int(geometry.get("crop_y1"), 0) or 0,
    )
    x0, y0, x1, y1 = crop
    crop_arr = crop_source[y0:y1, x0:x1]
    gt_local = parse_json_points(geometry.get("gt_crop_local_coords"))
    support_local = parse_json_points(geometry.get("support_crop_local_coords"))
    atoms_local: list[tuple[float, float]] = []
    components_local: list[tuple[float, float, float, float, str]] = []
    if features:
        for atom in list(features.get("atoms", []))[:24]:
            atoms_local.append((float(atom["x"]) - x0, float(atom["y"]) - y0))
        for comp in list(features.get("components", []))[:8]:
            components_local.append(
                (
                    float(comp["bbox_x0"]) - x0,
                    float(comp["bbox_y0"]) - y0,
                    float(comp["bbox_x1"]) - x0,
                    float(comp["bbox_y1"]) - y0,
                    str(comp["shape_type"]),
                )
            )

    fig = plt.figure(figsize=(16.5, 9.2), dpi=140, constrained_layout=True)
    gs = fig.add_gridspec(2, 4, width_ratios=[1, 1, 1, 1.2])
    fig.suptitle(f"{idx}. support-wide temporal structure | {geometry.get('case_id', '')}", fontproperties=FONT, fontsize=12)
    ax0 = fig.add_subplot(gs[0, 0])
    draw_base_axis(ax0, crop_arr, "当前 SAR + GT + support", gt_local, support_local)
    ax1 = fig.add_subplot(gs[0, 1])
    draw_base_axis(ax1, crop_arr, "support 全域高能点/组件", gt_local, support_local, atoms_local, components_local)
    for ax_idx, offset in enumerate([-5, 0, 5], start=0):
        ax = fig.add_subplot(gs[1, ax_idx])
        path = temporal_image_path(image_path, offset)
        if path:
            frame_arr = plt.imread(path)
            if frame_arr.ndim == 3:
                frame_arr = frame_arr[:, :, 0]
            draw_base_axis(ax, frame_arr[y0:y1, x0:x1], f"时序 {offset:+d} 帧")
        else:
            ax.text(0.5, 0.5, "帧不可用", ha="center", va="center", fontproperties=FONT, fontsize=10)
            ax.set_axis_off()
    ax_text = fig.add_subplot(gs[:, 3])
    ax_text.set_axis_off()
    structure = features.get("energy_atoms_form_vehicle_structure", "reference-only") if features else "reference-only"
    failure_type = failure.get("support_failure_type", "reference_only_no_support") if failure else "reference_only_no_support"
    text_lines = [
        "本图目的：检查 support 全域能量点、条带、块是否能组成车体结构，以及该结构是否随时序连续迁移。",
        "请重点看：高能点是否组成条带/块/车体边界，support 是否只覆盖部分结构，前后帧结构是否平滑变化。",
        "可以记录：SAR morphology strong/weak、support failure type、temporal compensation needed、background-stable risk、association review needed。",
        "不能记录：identity truth、final annotation、selector success。",
        f"case: {geometry.get('case_id', '')}",
        f"support-wide structure: {structure}",
        f"support failure: {failure_type}",
        f"manual card: {card.get('中文标题', '')}",
    ]
    ax_text.text(
        0.0,
        1.0,
        "\n\n".join(wrap_zh(line, 28) for line in text_lines),
        va="top",
        fontproperties=FONT,
        fontsize=8.0,
        linespacing=1.15,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def render_atlas(
    timestamp: str,
    geometry_rows: Sequence[Mapping[str, Any]],
    card_rows: Sequence[Mapping[str, Any]],
    features_by_case: Mapping[str, Mapping[str, Any]],
    failure_by_case: Mapping[str, Mapping[str, Any]],
) -> tuple[str, dict[str, str]]:
    card_by_panel = {str(row.get("panel_index", "")): row for row in card_rows}
    panel_paths: dict[str, str] = {}
    html_cards: list[str] = []
    for geometry in geometry_rows:
        idx = safe_int(geometry.get("panel_index"), 0) or 0
        case_id = str(geometry.get("case_id", ""))
        card = card_by_panel.get(str(idx), {})
        panel_name = f"{idx:02d}_{sanitize(case_id)}_support_wide_temporal_structure_cn.png"
        panel_path = VISUAL_DIR / panel_name
        image_path = Path(str(geometry.get("image_path", "")))
        if image_path.exists():
            render_atlas_panel(
                idx,
                geometry,
                card,
                features_by_case.get(case_id),
                failure_by_case.get(case_id),
                panel_path,
            )
            panel_paths[case_id] = str(panel_path)
            html_cards.append(
                "<article>"
                f"<h2>{idx}. {html.escape(str(card.get('中文标题', case_id)))}</h2>"
                f"<p><code>{html.escape(case_id)}</code></p>"
                f"<img src='{html.escape(panel_name)}' alt='{html.escape(case_id)}' />"
                "</article>"
            )
    atlas_path = VISUAL_DIR / f"oty2_support_wide_energy_structure_temporal_atlas_cn_{timestamp}.html"
    lines = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>OTY2 support-wide energy structure temporal atlas</title>",
        "<style>body{font-family:'Microsoft YaHei',Arial,sans-serif;background:#f5f5f5;color:#111;margin:24px;}article{background:#fff;border:1px solid #bbb;margin:0 0 24px;padding:16px;}img{max-width:100%;height:auto;border:1px solid #555;display:block;}code{font-size:12px;color:#064f8a;}</style>",
        "</head><body>",
        "<h1>OTY2 support-wide energy structure and temporal morphology atlas</h1>",
        "<p>本 atlas 是 posthoc mechanism diagnosis。support 是 optical-derived feasible region；GT 是 SAR posthoc morphology anchor；高能点/组件是 SAR observation。不能记录 final annotation、selector/ranking、identity truth。</p>",
        *html_cards,
        "</body></html>",
    ]
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    atlas_path.write_text("".join(lines), encoding="utf-8")
    return str(atlas_path), panel_paths


def build_continuity_rows(
    card_rows: Sequence[Mapping[str, Any]],
    features_by_case: Mapping[str, Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    atlas_panel_paths: Mapping[str, str],
) -> list[dict[str, Any]]:
    temporal_by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in temporal_rows:
        temporal_by_case[str(row.get("case_id", ""))].append(row)
    rows: list[dict[str, Any]] = []
    for card in card_rows:
        case_id = str(card.get("case_id", ""))
        features = features_by_case.get(case_id)
        temporal = temporal_by_case.get(case_id, [])
        best = ""
        vehicle_like = "reference-only"
        background = "reference-only"
        for candidate in temporal:
            if str(candidate.get("possible_vehicle_like_temporal_tube")) == "yes":
                best = str(candidate.get("window_size", ""))
                vehicle_like = "yes"
                background = str(candidate.get("possible_background_stable_structure", "uncertain"))
                break
        if not best and temporal:
            best_row = temporal[-1]
            best = str(best_row.get("window_size", ""))
            vehicle_like = str(best_row.get("possible_vehicle_like_temporal_tube", "uncertain"))
            background = str(best_row.get("possible_background_stable_structure", "uncertain"))
        rows.append(
            {
                "panel_id": f"Panel {card.get('panel_index', '')}",
                "case_id": case_id,
                "scene": (features or {}).get("scene", ""),
                "sar_frame": (features or {}).get("sar_frame", ""),
                "continuity_case_type": card.get("样例类型", ""),
                "support_wide_structure_label": (features or {}).get(
                    "energy_atoms_form_vehicle_structure", "reference-only"
                ),
                "temporal_best_window": best,
                "possible_vehicle_like_temporal_tube": vehicle_like,
                "possible_background_stable_structure": background,
                "manual_review_needed": "yes"
                if vehicle_like != "yes" or background == "yes" or features is None
                else "no",
                "atlas_panel_path": atlas_panel_paths.get(case_id, ""),
                "notes": "Chinese atlas case; reference-only if no paired support feature exists.",
            }
        )
    return rows


def render_correction_archive(path: Path) -> None:
    source = DOCS_DIR / "oty2_support_wide_energy_structure_and_temporal_morphology_correction_archive.md"
    if not source.exists():
        return
    # The stable archive is maintained as a doc file; this function only confirms it exists.
    _ = path


def render_report(path: Path, summary: Mapping[str, Any], proxy_defs: Sequence[Mapping[str, str]]) -> None:
    metrics = summary["key_metrics"]
    answers = summary["required_answers"]
    lines = [
        "# OTY2 Support-Wide Energy Structure And Temporal Morphology Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report corrects the previous GT-local/top-k support judgment by inspecting the whole reconstructed support region. It is posthoc mechanism diagnosis only: no annotation proposal, final box, selected component, selector/ranking, training, threshold tuning, best weight, or identity truth is produced.",
        "",
        "## Ledger Boundary",
        "",
        "- 442 = all SAR GT / SAR-side morphology reference pool",
        "- 215 = current paired optical-object-to-SAR GT posthoc pool",
        "- 195 = GM_RM011 blocked_missing_object_stream, not unannotated",
        "- 20 = SAR-only morphology reference only",
        "- 12 = dropout/no-match temporal continuation special pool, not clean paired morphology",
        "",
        "## Fixed Diagnostic Thresholds",
        "",
        f"- support energy atoms: support-internal p{int(ATOM_QUANTILE * 100)} local maxima with `{LOCAL_MAX_MIN_DISTANCE_PX}` px minimum separation.",
        f"- bright connected components: support-internal p{int(COMPONENT_SUPPORT_QUANTILE * 100)}, 8-connected, area >= `{MIN_COMPONENT_AREA_PX}` px.",
        "- These thresholds are public fixed diagnostics and are not selected by GT, not tuned for success, and not used for runtime prediction.",
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Vehicle Shell Proxy Definitions", ""])
    for item in proxy_defs:
        lines.append(
            f"- `{item['proxy_name']}`: {item['mechanism_meaning']} Method: {item['calculation_method_public']}. "
            f"Limit: {item['known_limitations']}"
        )
    lines.extend(["", "## Required Answers", ""])
    for idx, answer in enumerate(answers, start=1):
        lines.append(f"{idx}. {answer}")
    lines.extend(["", "## Posthoc Hypotheses Only", ""])
    for item in summary["posthoc_hypotheses_only"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Sources", ""])
    for key, value in summary["sources"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_required_answers(
    atom_rows: Sequence[Mapping[str, Any]],
    proxy_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    structure_yes = sum(1 for row in atom_rows if row.get("energy_atoms_form_vehicle_structure") == "yes")
    shell_yes_cases = {
        row["case_id"]
        for row in proxy_rows
        if row.get("proxy_name") == "support_wide_vehicle_shell_proxy"
        and row.get("vehicle_shell_supported") == "yes"
    }
    az_range_cases = [
        row["case_id"]
        for row in failure_rows
        if "azimuth_aligned_range_misaligned" in str(row.get("support_failure_type", ""))
    ]
    trunc_cases = [
        row["case_id"]
        for row in failure_rows
        if "truncation" in str(row.get("support_failure_type", ""))
        or "near_field" in str(row.get("support_failure_type", ""))
    ]
    temporal_yes = {
        row["case_id"]
        for row in temporal_rows
        if row.get("window_size") == 10 and row.get("possible_vehicle_like_temporal_tube") == "yes"
    }
    background_risk = {
        row["case_id"]
        for row in temporal_rows
        if row.get("window_size") == 10 and row.get("possible_background_stable_structure") == "yes"
    }
    return [
        "不能孤立看 top-k 高能点，因为 top-k 只是散射原子；车辆 morphology 需要 support 全域内的 atoms、条带、块、边界和时序漂移共同解释。",
        f"support 全域结构比 GT 内 top-k 更有机制意义：在 215 个 paired support 行中，`{structure_yes}` 个在固定规则下显示 atoms/components 可组织成 vehicle-like structure。",
        "SAR 车辆外壳/边界 morphology 在本报告中定义为 support 内 elongated ridge、strip+corner、multi-peak shell、block-like body 或 range-spread-with-core 这些 posthoc proxy 的组合。",
        f"support 内散射原子可组织成 shell/strip/block/boundary 的样本数为 `{len(shell_yes_cases)}`；这些只是 posthoc shell proxy，不是 selector feature。",
        "support 错误主要分为 range/azimuth misalignment、too narrow/too broad、range compression、truncation/near-field shift、state/temporal compensation missing、neighbor/background interference 和 reference-only no-support。",
        f"azimuth 对齐但 range 错的样本数为 `{len(az_range_cases)}`；样例包括 `{';'.join(az_range_cases[:8])}`。",
        f"截断/近场需要状态或时序补偿的样本数为 `{len(trunc_cases)}`；这指向 support 重建/状态补偿，不是否定 SAR morphology。",
        f"temporal drift probe 在 10-frame 窗口中显示 vehicle-like gradual structure 的 case 数为 `{len(temporal_yes)}`。",
        f"wrong-frame/background-stable 风险在 10-frame 窗口中出现 `{len(background_risk)}` 个 case；这些需要人工复核 temporal context。",
        "所有 GT relation、SAR image atoms/components、shell proxy 和 temporal tube 仍然只是 posthoc hypothesis / validation，不进入 runtime prediction logic。",
        "下一步更适合做 motion/drift compatibility 与 GM_RM019 optical continuity review；若要收束阶段，也可以先做阶段复盘。GM_RM011 object stream recovery 是后续规模扩展，不应混入本 paired pool。",
    ]


def build_summary(
    timestamp: str,
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
    atom_rows: Sequence[Mapping[str, Any]],
    proxy_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    continuity_rows: Sequence[Mapping[str, Any]],
    panel_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    atom_count = len(atom_rows)
    structure_counts = Counter(row.get("energy_atoms_form_vehicle_structure", "") for row in atom_rows)
    shape_counts = Counter(row.get("dominant_component_shape_type", "") for row in atom_rows)
    proxy_case_yes = {
        row["case_id"]
        for row in proxy_rows
        if row.get("proxy_name") == "support_wide_vehicle_shell_proxy"
        and row.get("vehicle_shell_supported") == "yes"
    }
    failure_types: list[str] = []
    for row in failure_rows:
        failure_types.extend(str(row.get("support_failure_type", "")).split(";"))
    temporal_10 = [row for row in temporal_rows if str(row.get("window_size")) == "10"]
    temporal_vehicle_like = sum(
        1 for row in temporal_10 if row.get("possible_vehicle_like_temporal_tube") == "yes"
    )
    temporal_background = sum(
        1 for row in temporal_10 if row.get("possible_background_stable_structure") == "yes"
    )
    manual_review_cases = sorted(
        {
            row["case_id"]
            for row in failure_rows
            if "support_contains_neighbor_structure" in str(row.get("support_failure_type", ""))
            or "reference_only_no_support" in str(row.get("support_failure_type", ""))
        }
        | {
            row["case_id"]
            for row in temporal_10
            if row.get("possible_vehicle_like_temporal_tube") != "yes"
            or row.get("possible_background_stable_structure") == "yes"
        }
    )
    key_metrics = {
        "paired_state_conditioned_support_rows": atom_count,
        "support_image_available_rows": sum(1 for row in atom_rows if row.get("support_image_available") == "yes"),
        "support_wide_structure_yes": structure_counts.get("yes", 0),
        "support_wide_structure_uncertain": structure_counts.get("uncertain", 0),
        "support_wide_structure_no": structure_counts.get("no", 0),
        "dominant_component_shape_mix": compact_counts(row.get("dominant_component_shape_type", "") for row in atom_rows),
        "support_wide_shell_proxy_yes_cases": len(proxy_case_yes),
        "support_failure_type_mix": compact_counts(failure_types),
        "temporal_probe_rows": len(temporal_rows),
        "temporal_10frame_vehicle_like_cases": temporal_vehicle_like,
        "temporal_10frame_background_stable_risk_cases": temporal_background,
        "continuity_case_rows": len(continuity_rows),
        "panel_review_correction_note_rows": len(panel_rows),
        "manual_review_needed_case_count": len(manual_review_cases),
        "manual_review_needed_case_examples": ";".join(manual_review_cases[:12]),
    }
    summary = {
        "timestamp": timestamp,
        "sample_ledger": {
            "paired_optical_object_sar_gt": 215,
            "blocked_missing_gm011_object_stream": 195,
            "sar_only_gt": 20,
            "dropout_no_oty_iou_match_temporal_continuation": 12,
        },
        "row_counts": {
            "support_wide_energy_atoms_and_components": len(atom_rows),
            "support_wide_vehicle_shell_proxy": len(proxy_rows),
            "support_failure_taxonomy": len(failure_rows),
            "temporal_morphology_drift_probe": len(temporal_rows),
            "multiframe_structure_continuity_cases": len(continuity_rows),
            "panel_review_correction_notes": len(panel_rows),
        },
        "key_metrics": key_metrics,
        "posthoc_hypotheses_only": [
            "support-wide atoms/components use SAR image content for diagnosis only",
            "GT relation columns validate atom/component relation posthoc only",
            "vehicle shell proxies are not selector features or annotation rules",
            "temporal morphology tube labels are not identity truth",
            "support coverage quality does not equal association success",
        ],
        "required_answers": build_required_answers(atom_rows, proxy_rows, failure_rows, temporal_rows),
        "boundary_flags": BOUNDARY_FLAGS,
        "sources": dict(sources),
        "outputs": dict(outputs),
    }
    return summary


def write_workspace_log(path: Path, timestamp: str, summary: Mapping[str, Any] | None = None) -> None:
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_support_wide_energy_structure_and_temporal_morphology",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_runtime_paths_used=false",
        "archive_runtime_paths_used=false",
        "outputs_base=reports/oty2",
        "selector_or_ranking_used=false",
        "final_annotation_or_identity_truth=false",
        "stage=start" if summary is None else "stage=complete",
    ]
    if summary is not None:
        lines.append(f"row_counts={json.dumps(summary['row_counts'], ensure_ascii=False)}")
        lines.append(f"key_metrics={json.dumps(summary['key_metrics'], ensure_ascii=False)}")
        lines.append(f"outputs={json.dumps(summary['outputs'], ensure_ascii=False)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "support_peak_competition_csv": Path(args.support_peak_competition_csv)
        if args.support_peak_competition_csv
        else latest_path("oty2_support_region_peak_competition_audit_*.csv"),
        "correspondence_csv": Path(args.correspondence_csv)
        if args.correspondence_csv
        else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "support_coverage_csv": Path(args.support_coverage_csv)
        if args.support_coverage_csv
        else latest_path("oty2_optical_support_coverage_hypothesis_audit_*.csv"),
        "gt_energy_csv": Path(args.gt_energy_csv)
        if args.gt_energy_csv
        else latest_path("oty2_gt_box_energy_distribution_audit_*.csv"),
        "complete_pool_csv": Path(args.complete_pool_csv)
        if args.complete_pool_csv
        else latest_path("oty2_complete_optical_high_confidence_coverage_pool_*.csv"),
        "compensation_pool_csv": Path(args.compensation_pool_csv)
        if args.compensation_pool_csv
        else latest_path("oty2_truncated_occluded_temporal_compensation_pool_*.csv"),
        "chinese_review_card_index_csv": Path(args.chinese_review_card_index_csv)
        if args.chinese_review_card_index_csv
        else latest_path("oty2_chinese_review_card_index_*.csv"),
        "overlay_geometry_debug_csv": Path(args.overlay_geometry_debug_csv)
        if args.overlay_geometry_debug_csv
        else latest_path("oty2_overlay_case_geometry_debug_*.csv"),
    }
    peak_rows = read_csv(paths["support_peak_competition_csv"])
    state_rows = [
        row
        for row in peak_rows
        if row.get("mode_name") == STATE_MODE
        and row.get("sample_pool") == "paired_optical_object_sar_gt"
    ]
    if len(state_rows) != 215:
        raise RuntimeError(f"Expected 215 paired {STATE_MODE} rows; got {len(state_rows)}")
    coverage_rows = read_csv(paths["support_coverage_csv"])
    if len(coverage_rows) != 215:
        raise RuntimeError(f"Expected 215 support coverage rows; got {len(coverage_rows)}")
    return {
        "paths": paths,
        "state_rows": state_rows,
        "corr_rows": read_csv(paths["correspondence_csv"]),
        "coverage_rows": coverage_rows,
        "gt_energy_rows": read_csv(paths["gt_energy_csv"]),
        "complete_rows": read_csv(paths["complete_pool_csv"]),
        "compensation_rows": read_csv(paths["compensation_pool_csv"]),
        "card_rows": read_csv(paths["chinese_review_card_index_csv"]),
        "geometry_rows": read_csv(paths["overlay_geometry_debug_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_log = WORKSPACE_LOG_DIR / f"oty2_support_wide_energy_structure_and_temporal_morphology_{timestamp}.log"
    write_workspace_log(workspace_log, timestamp)
    inputs = load_inputs(args)
    paths = inputs["paths"]
    sources = {name: str(path) for name, path in paths.items()}
    corr_by_case = {case_id_from_correspondence(row): row for row in inputs["corr_rows"]}
    coverage_by_case = {str(row.get("case_id", "")): row for row in inputs["coverage_rows"]}
    gt_energy_by_key = {
        (str(row.get("scene", "")), str(row.get("sar_frame", "")), str(row.get("gt_id", ""))): row
        for row in inputs["gt_energy_rows"]
    }
    cache = SarImageCache(max_images=args.image_cache_size)

    atom_rows, features_by_key = build_atom_component_rows(
        inputs["state_rows"], corr_by_case, coverage_by_case, cache
    )
    features_by_case: dict[str, Mapping[str, Any]] = {}
    for features in features_by_key.values():
        features_by_case.setdefault(str(features["case_id"]), features)
    proxy_rows, aggregate_proxy_by_key = build_proxy_rows(features_by_key)
    failure_rows = build_failure_rows(features_by_key, aggregate_proxy_by_key, gt_energy_by_key)
    failure_by_case: dict[str, Mapping[str, Any]] = {}
    for row in failure_rows:
        failure_by_case.setdefault(str(row.get("case_id", "")), row)
    temporal_rows = build_temporal_rows(features_by_key, cache)
    panel_rows = panel_correction_notes(inputs["card_rows"])
    atlas_path, atlas_panel_paths = render_atlas(
        timestamp,
        inputs["geometry_rows"],
        inputs["card_rows"],
        features_by_case,
        failure_by_case,
    )
    continuity_rows = build_continuity_rows(
        inputs["card_rows"], features_by_case, temporal_rows, atlas_panel_paths
    )

    atom_csv = REPORT_DIR / f"oty2_support_wide_energy_atoms_and_components_{timestamp}.csv"
    proxy_csv = REPORT_DIR / f"oty2_support_wide_vehicle_shell_proxy_{timestamp}.csv"
    failure_csv = REPORT_DIR / f"oty2_support_failure_taxonomy_{timestamp}.csv"
    temporal_csv = REPORT_DIR / f"oty2_temporal_morphology_drift_probe_{timestamp}.csv"
    continuity_csv = REPORT_DIR / f"oty2_multiframe_structure_continuity_cases_{timestamp}.csv"
    panel_csv = REPORT_DIR / f"oty2_panel_review_correction_notes_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_support_wide_energy_structure_and_temporal_morphology_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_support_wide_energy_structure_and_temporal_morphology_summary_{timestamp}.json"
    outputs = {
        "correction_archive_doc": str(
            DOCS_DIR / "oty2_support_wide_energy_structure_and_temporal_morphology_correction_archive.md"
        ),
        "plan_doc": str(DOCS_DIR / "oty2_support_wide_energy_structure_and_temporal_morphology_plan.md"),
        "support_wide_energy_atoms_and_components_csv": str(atom_csv),
        "support_wide_vehicle_shell_proxy_csv": str(proxy_csv),
        "support_failure_taxonomy_csv": str(failure_csv),
        "temporal_morphology_drift_probe_csv": str(temporal_csv),
        "multiframe_structure_continuity_cases_csv": str(continuity_csv),
        "panel_review_correction_notes_csv": str(panel_csv),
        "support_wide_energy_structure_and_temporal_morphology_report_md": str(report_md),
        "support_wide_energy_structure_and_temporal_morphology_summary_json": str(summary_json),
        "visual_atlas_html": atlas_path,
        "workspace_log": str(workspace_log),
    }
    summary = build_summary(
        timestamp,
        sources,
        outputs,
        atom_rows,
        proxy_rows,
        failure_rows,
        temporal_rows,
        continuity_rows,
        panel_rows,
    )

    write_csv(atom_csv, atom_rows, ATOM_COMPONENT_FIELDS)
    write_csv(proxy_csv, proxy_rows, PROXY_FIELDS)
    write_csv(failure_csv, failure_rows, FAILURE_FIELDS)
    write_csv(temporal_csv, temporal_rows, TEMPORAL_FIELDS)
    write_csv(continuity_csv, continuity_rows, CONTINUITY_FIELDS)
    write_csv(panel_csv, panel_rows, PANEL_NOTE_FIELDS)
    render_report(report_md, summary, proxy_definitions())
    write_json(summary_json, summary)
    write_workspace_log(workspace_log, timestamp, summary)

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
    parser.add_argument("--support-peak-competition-csv", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--support-coverage-csv", default="")
    parser.add_argument("--gt-energy-csv", default="")
    parser.add_argument("--complete-pool-csv", default="")
    parser.add_argument("--compensation-pool-csv", default="")
    parser.add_argument("--chinese-review-card-index-csv", default="")
    parser.add_argument("--overlay-geometry-debug-csv", default="")
    parser.add_argument("--image-cache-size", type=int, default=96)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
