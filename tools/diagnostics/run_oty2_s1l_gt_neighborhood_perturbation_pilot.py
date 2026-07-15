#!/usr/bin/env python3
from __future__ import annotations

"""Run the bounded S1-L GT-neighbourhood perturbation pilot.

The runner evaluates a small symmetric parameter grid and keeps every metric
separate.  It does not rank settings, select a box, use GT IoU, or emit a
unique optimum.  Vehicle development, fixed heldout replay, fixed-world
background, and trajectory-swap counterfactuals use the same transform path.
"""

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

import run_oty2_s1l_body_support_coordinate_casebook as base


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
OUTPUT_ROOT = WORKSPACE_ROOT / "output" / "oty2_s1l_body_support_attribution_20260715"
SURFACE_ROOT = OUTPUT_ROOT / "gt_neighborhood_surfaces"
SUMMARY_PATH = OUTPUT_ROOT / "gt_neighborhood_perturbation_summary.json"
LOG_PATH = WORKSPACE_ROOT / "logs" / "oty2_s1l_body_support_attribution_20260715.log"

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
BACKGROUND_PATH = MANIFEST_DIR / "oty2_s1l_background_counterfactuals.csv"
SURFACE_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_surfaces.csv"
VISUAL_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_casebook_manifest.csv"

DEVELOPMENT_SEGMENT = "S0MV-GM_RM017-PV002-SEG02"
HELDOUT_SEGMENTS = ("S0MV-GM_RM017-PV003-SEG01", "S0MV-GM_RM017-PV004-SEG01")
VEHICLE_SEGMENTS = (DEVELOPMENT_SEGMENT, *HELDOUT_SEGMENTS)

CENTER_FRACTIONS = (-0.25, -0.125, 0.0, 0.125, 0.25)
SCALE_FACTORS = (0.85, 0.925, 1.0, 1.075, 1.15)
ROTATION_DEGREES = (-12.0, -6.0, 0.0, 6.0, 12.0)

FAILURE_PROBES = {
    (DEVELOPMENT_SEGMENT, "smoothed_gt"): {
        "radial": 0.0, "tangential": 0.0, "long": 1.0, "short": 1.0, "rotation": -12.0,
        "label": "rotation_-12_coherence_gain_but_baseline_alignment_loss",
        "note": "nonadjacent coherence and outer-mass diagnostics improve, but overlap with the baseline canonical high-occupancy support falls to about 0.158; this is coordinate-support alignment loss, not proof that physical response disappeared",
    },
    (HELDOUT_SEGMENTS[1], "smoothed_gt"): {
        "radial": 0.0, "tangential": 0.0, "long": 1.0, "short": 1.0, "rotation": 12.0,
        "label": "rotation_+12_coherence_gain_but_baseline_alignment_loss",
        "note": "adjacent/nonadjacent coherence improves, but overlap with the baseline canonical high-occupancy support falls to about 0.247 and outer mass rises; this is coordinate-support alignment loss, not proof that physical response disappeared",
    },
    (base.FIXED_BACKGROUND_UNIT, "smoothed_gt"): {
        "radial": 0.0, "tangential": 0.0, "long": 1.0, "short": 1.0, "rotation": 12.0,
        "label": "background_rotation_+12_also_improves_coherence",
        "note": "fixed background also gains adjacent and nonadjacent coherence, showing that coherence improvement is not vehicle-specific",
    },
}

SURFACE_FIELDS = (
    "perturbation_id", "research_unit_id", "research_unit_type", "scene", "canonical_vehicle_id",
    "benchmark_role", "research_role", "source_trajectory_segment_id", "target_region_segment_id",
    "anchor_variant", "perturbation_family", "radial_shift_fraction", "tangential_shift_fraction",
    "long_scale", "short_scale", "rotation_delta_deg", "is_gt_baseline", "frame_count",
    "optical_corridor_constraint", "temporal_parameter_constraint", "vehicle_scale_constraint",
    "valid_mask_constraint", "valid_fraction_mean", "valid_fraction_min", "boundary_missing_mean",
    "adjacent_ncc_median", "adjacent_ncc_p10", "nonadjacent_similar_view_pair_count",
    "nonadjacent_similar_view_ncc_median", "support_entropy_mean_bits", "support_area_fraction_mean",
    "support_area_fraction_cv", "outer_context_response_mass_fraction", "baseline_mean_field_ncc",
    "baseline_high_occupancy_recall", "baseline_high_occupancy_precision",
    "reference_world_adjacent_ncc", "reference_world_nonadjacent_ncc",
    "reference_smoothed_crop_adjacent_ncc", "reference_smoothed_crop_nonadjacent_ncc",
    "automatic_winner", "review_status", "notes",
)

VISUAL_FIELDS = (
    "case_id", "artifact_type", "research_unit_id", "research_unit_type", "scene",
    "canonical_vehicle_id", "anchor_variant", "perturbation_family", "artifact_path",
    "review_status", "notes",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fmt(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return "" if not math.isfinite(number) else f"{number:.{digits}f}"


def rotate_axes(u: np.ndarray, v: np.ndarray, delta_deg: float) -> tuple[np.ndarray, np.ndarray]:
    angle = math.radians(delta_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    new_u = u * cosine + v * sine
    new_v = -u * sine + v * cosine
    return new_u, new_v


def common_frame_unit(source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    source_index = {int(row["sar_frame_index"]): index for index, row in enumerate(source["rows"])}
    target_index = {int(row["sar_frame_index"]): index for index, row in enumerate(target["rows"])}
    frames = sorted(set(source_index) & set(target_index))
    source_middle_frame = frames[len(frames) // 2]
    source_middle = source["smooth_anchors"][source_index[source_middle_frame]]
    target_middle = target["smooth_anchors"][target_index[source_middle_frame]]
    rows: list[dict[str, str]] = []
    raw_anchors: list[dict[str, float]] = []
    smooth_anchors: list[dict[str, float]] = []
    raw_axes: list[tuple[np.ndarray, np.ndarray]] = []
    smooth_axes: list[tuple[np.ndarray, np.ndarray]] = []
    raw_angles: list[float] = []
    smooth_angles: list[float] = []
    for frame in frames:
        si, ti = source_index[frame], target_index[frame]
        rows.append(target["rows"][ti])
        raw = dict(source["raw_anchors"][si])
        smooth = dict(source["smooth_anchors"][si])
        raw["cx"] = target_middle["cx"] + source["raw_anchors"][si]["cx"] - source_middle["cx"]
        raw["cy"] = target_middle["cy"] + source["raw_anchors"][si]["cy"] - source_middle["cy"]
        smooth["cx"] = target_middle["cx"] + source["smooth_anchors"][si]["cx"] - source_middle["cx"]
        smooth["cy"] = target_middle["cy"] + source["smooth_anchors"][si]["cy"] - source_middle["cy"]
        raw_anchors.append(raw); smooth_anchors.append(smooth)
        raw_axes.append(source["raw_axes"][si]); smooth_axes.append(source["smooth_axes"][si])
        raw_angles.append(source["raw_angles"][si]); smooth_angles.append(source["smooth_angles"][si])
    identifier = f"SWAP-{source['canonical_vehicle_id'].replace(':','_')}-TRAJECTORY-AROUND-{target['canonical_vehicle_id'].replace(':','_')}"
    return {
        "research_unit_id": identifier,
        "research_unit_type": "trajectory_swap_counterfactual",
        "scene": source["scene"],
        "canonical_vehicle_id": source["canonical_vehicle_id"],
        "benchmark_role": "counterfactual",
        "research_role": "trajectory_swap_diagnostic",
        "segment_id": identifier,
        "source_trajectory_segment_id": source["segment_id"],
        "target_region_segment_id": target["segment_id"],
        "rows": rows, "raw_anchors": raw_anchors, "smooth_anchors": smooth_anchors,
        "raw_axes": raw_axes, "smooth_axes": smooth_axes, "raw_angles": raw_angles, "smooth_angles": smooth_angles,
        "reference_long": source["reference_long"], "reference_short": source["reference_short"],
        "reference_radial_half": statistics.median(base.parse_float(source["rows"][source_index[frame]]["smoothed_half_extent_radial_px"]) for frame in frames),
        "reference_tangential_half": statistics.median(base.parse_float(source["rows"][source_index[frame]]["smoothed_half_extent_tangential_px"]) for frame in frames),
    }


def augment_unit(unit: dict[str, Any]) -> dict[str, Any]:
    unit = dict(unit)
    unit.setdefault("target_region_segment_id", unit["segment_id"])
    unit["reference_radial_half"] = statistics.median(base.parse_float(row["smoothed_half_extent_radial_px"]) for row in unit["rows"])
    unit["reference_tangential_half"] = statistics.median(base.parse_float(row["smoothed_half_extent_tangential_px"]) for row in unit["rows"])
    return unit


def image_cache(unit: Mapping[str, Any]) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    output: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for row in unit["rows"]:
        frame = int(row["sar_frame_index"])
        if frame in output:
            continue
        image = cv2.imread(str(base.image_path(unit["scene"], frame)), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(base.image_path(unit["scene"], frame))
        output[frame] = (image, cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0))
    return output


def evaluate_stack(
    unit: Mapping[str, Any],
    anchor_variant: str,
    radial_fraction: float,
    tangential_fraction: float,
    long_scale: float,
    short_scale: float,
    rotation_delta: float,
    cache: Mapping[int, tuple[np.ndarray, np.ndarray]],
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    anchors = unit["raw_anchors"] if anchor_variant == "raw_gt" else unit["smooth_anchors"]
    axes = unit["raw_axes"] if anchor_variant == "raw_gt" else unit["smooth_axes"]
    scores: list[np.ndarray] = []
    valids: list[np.ndarray] = []
    view_angles: list[float] = []
    outer_mass: list[float] = []
    half_x = unit["reference_long"] * 0.5 * base.CROP_EXPANSION * long_scale
    half_y = unit["reference_short"] * 0.5 * base.CROP_EXPANSION * short_scale
    normalized_x = np.linspace(-1.0, 1.0, base.GRID_WIDTH)[None, :]
    normalized_y = np.linspace(-1.0, 1.0, base.GRID_HEIGHT)[:, None]
    nominal = (np.abs(normalized_x) <= 1.0 / base.CROP_EXPANSION) & (np.abs(normalized_y) <= 1.0 / base.CROP_EXPANSION)

    for index, row in enumerate(unit["rows"]):
        frame = int(row["sar_frame_index"])
        image, blurred = cache[frame]
        anchor = dict(anchors[index])
        radial, tangential = base.radial_tangential(anchor)
        center = np.asarray([anchor["cx"], anchor["cy"]], dtype=np.float64)
        center += radial * radial_fraction * unit["reference_radial_half"]
        center += tangential * tangential_fraction * unit["reference_tangential_half"]
        u, v = rotate_axes(axes[index][0], axes[index][1], rotation_delta)
        raw, valid = base.warp_axes(image, center, u, v, half_x, half_y)
        blur, _ = base.warp_axes(blurred, center, u, v, half_x, half_y)
        score = base.normalized_score(
            blur, valid, base.parse_float(row["local_background_median"]), base.parse_float(row["thread_raw_p99"]),
        )
        support_mass = float((score * valid).sum())
        outer_mass.append(float((score * valid * ~nominal).sum()) / max(support_mass, 1e-9))
        scores.append(score); valids.append(valid)
        shifted_anchor = dict(anchor); shifted_anchor["cx"], shifted_anchor["cy"] = float(center[0]), float(center[1])
        view_angles.append(base.radar_in_body(shifted_anchor, u, v)[2])

    score_stack = np.stack(scores, axis=0).astype(np.float32)
    valid_stack = np.stack(valids, axis=0).astype(bool)
    frames = [int(row["sar_frame_index"]) for row in unit["rows"]]
    metrics, mean_score, occupancy, entropy = base.stack_metrics(score_stack, valid_stack, frames, view_angles)
    metrics["boundary_missing_mean"] = 1.0 - float(valid_stack.mean())
    metrics["outer_context_response_mass_fraction"] = statistics.mean(outer_mass)
    return metrics, mean_score, occupancy, entropy, score_stack, valid_stack


def field_ncc(a: np.ndarray, b: np.ndarray) -> float:
    valid = np.isfinite(a) & np.isfinite(b)
    if int(valid.sum()) < 20:
        return math.nan
    av = a[valid].astype(np.float64); bv = b[valid].astype(np.float64)
    av -= av.mean(); bv -= bv.mean()
    denominator = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return float(av @ bv / denominator) if denominator > 1e-12 else math.nan


def baseline_overlap(candidate: np.ndarray, baseline: np.ndarray) -> tuple[float, float]:
    candidate_core = candidate >= 0.5
    baseline_core = baseline >= 0.5
    intersection = int((candidate_core & baseline_core).sum())
    recall = intersection / max(1, int(baseline_core.sum()))
    precision = intersection / max(1, int(candidate_core.sum()))
    return float(recall), float(precision)


def reference_metrics() -> dict[tuple[str, str], dict[str, str]]:
    path = MANIFEST_DIR / "oty2_s1l_body_support_coordinate_competition.csv"
    output: dict[tuple[str, str], dict[str, str]] = {}
    if path.exists():
        for row in read_csv(path):
            output[(row["research_unit_id"], row["representation"])] = row
    return output


def settings() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for radial in CENTER_FRACTIONS:
        for tangential in CENTER_FRACTIONS:
            output.append({"family": "center_shift", "radial": radial, "tangential": tangential, "long": 1.0, "short": 1.0, "rotation": 0.0})
    for long_scale in SCALE_FACTORS:
        for short_scale in SCALE_FACTORS:
            output.append({"family": "scale_surface", "radial": 0.0, "tangential": 0.0, "long": long_scale, "short": short_scale, "rotation": 0.0})
    for rotation in ROTATION_DEGREES:
        output.append({"family": "axis_rotation", "radial": 0.0, "tangential": 0.0, "long": 1.0, "short": 1.0, "rotation": rotation})
    return output


def color_panel(
    rows: Sequence[Mapping[str, Any]],
    x_field: str,
    y_field: str,
    value_field: str,
    title: str,
    higher_is_better: bool,
    baseline_x: float,
    baseline_y: float,
) -> np.ndarray:
    xs = sorted({float(row[x_field]) for row in rows})
    ys = sorted({float(row[y_field]) for row in rows})
    values = np.full((len(ys), len(xs)), np.nan, dtype=np.float32)
    for row in rows:
        values[ys.index(float(row[y_field])), xs.index(float(row[x_field]))] = base.parse_float(row[value_field])
    finite = values[np.isfinite(values)]
    minimum = float(finite.min()) if finite.size else 0.0
    maximum = float(finite.max()) if finite.size else 1.0
    normalized = np.zeros_like(values, dtype=np.float32)
    if maximum > minimum:
        normalized = (values - minimum) / (maximum - minimum)
    if not higher_is_better:
        normalized = 1.0 - normalized
    expanded = cv2.resize(np.nan_to_num(normalized, nan=0.0), (300, 210), interpolation=cv2.INTER_NEAREST)
    panel = cv2.applyColorMap(np.round(expanded * 255.0).astype(np.uint8), cv2.COLORMAP_TURBO)
    x_index = xs.index(baseline_x); y_index = ys.index(baseline_y)
    point = (int(round((x_index + 0.5) / len(xs) * 300)), int(round((y_index + 0.5) / len(ys) * 210)))
    cv2.circle(panel, point, 8, (255, 255, 255), 2, cv2.LINE_AA)
    base.put_text(panel, title, (6, 17), scale=0.38)
    base.put_text(panel, f"raw min={minimum:.3f} max={maximum:.3f}", (6, 205), scale=0.32)
    return panel


def surface_page(
    unit: Mapping[str, Any],
    anchor_variant: str,
    family: str,
    rows: Sequence[Mapping[str, Any]],
    review_status: str,
) -> dict[str, Any]:
    metrics = (
        ("adjacent_ncc_median", "adjacent NCC (high)", True),
        ("nonadjacent_similar_view_ncc_median", "similar-view NCC (high)", True),
        ("support_entropy_mean_bits", "support entropy (low)", False),
        ("outer_context_response_mass_fraction", "outer response mass (low)", False),
        ("baseline_high_occupancy_recall", "baseline support recall (high)", True),
        ("support_area_fraction_cv", "support area CV (low)", False),
    )
    if family == "center_shift":
        x_field, y_field, baseline_x, baseline_y = "tangential_shift_fraction", "radial_shift_fraction", 0.0, 0.0
    else:
        x_field, y_field, baseline_x, baseline_y = "long_scale", "short_scale", 1.0, 1.0
    canvas = np.full((2 * 210, 3 * 300, 3), 15, dtype=np.uint8)
    for index, (field, title, high) in enumerate(metrics):
        panel = color_panel(rows, x_field, y_field, field, title, high, baseline_x, baseline_y)
        row_index, column = divmod(index, 3)
        canvas[row_index * 210:(row_index + 1) * 210, column * 300:(column + 1) * 300] = panel
    directory = SURFACE_ROOT / unit["research_unit_id"] / anchor_variant
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{family}_separate_metric_surfaces.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}-{anchor_variant}-{family}",
        "artifact_type": "separate_metric_parameter_surfaces", "research_unit_id": unit["research_unit_id"],
        "research_unit_type": unit["research_unit_type"], "scene": unit["scene"],
        "canonical_vehicle_id": unit["canonical_vehicle_id"], "anchor_variant": anchor_variant,
        "perturbation_family": family, "artifact_path": str(path), "review_status": review_status,
        "notes": "white circle is GT-derived baseline; colours are per-metric only; no combined score or automatic winner",
    }


def curve_panel(rows: Sequence[Mapping[str, Any]], field: str, title: str, higher_is_better: bool) -> np.ndarray:
    ordered = sorted(rows, key=lambda row: float(row["rotation_delta_deg"]))
    xs = [float(row["rotation_delta_deg"]) for row in ordered]
    ys = [base.parse_float(row[field]) for row in ordered]
    panel = np.full((210, 300, 3), 22, dtype=np.uint8)
    finite = [value for value in ys if math.isfinite(value)]
    minimum = min(finite) if finite else 0.0; maximum = max(finite) if finite else 1.0
    if maximum <= minimum:
        maximum = minimum + 1.0
    points = []
    for x, y in zip(xs, ys):
        px = int(round(22 + (x - min(xs)) / max(1e-9, max(xs) - min(xs)) * 256))
        display_y = y if math.isfinite(y) else minimum
        py = int(round(180 - (display_y - minimum) / (maximum - minimum) * 140))
        points.append((px, py))
    cv2.line(panel, (22, 180), (278, 180), (160, 160, 160), 1)
    cv2.line(panel, (150, 35), (150, 185), (255, 255, 255), 1)
    cv2.polylines(panel, [np.asarray(points, dtype=np.int32)], False, (50, 220, 255) if higher_is_better else (255, 160, 50), 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(panel, point, 3, (60, 240, 80), -1, cv2.LINE_AA)
    base.put_text(panel, title, (6, 17), scale=0.38)
    base.put_text(panel, f"raw min={minimum:.3f} max={maximum:.3f}", (6, 205), scale=0.32)
    return panel


def rotation_page(
    unit: Mapping[str, Any], anchor_variant: str, rows: Sequence[Mapping[str, Any]], review_status: str,
) -> dict[str, Any]:
    metrics = (
        ("adjacent_ncc_median", "adjacent NCC", True),
        ("nonadjacent_similar_view_ncc_median", "similar-view NCC", True),
        ("support_entropy_mean_bits", "support entropy", False),
        ("outer_context_response_mass_fraction", "outer response mass", False),
        ("baseline_high_occupancy_recall", "baseline support recall", True),
        ("support_area_fraction_cv", "support area CV", False),
    )
    canvas = np.full((2 * 210, 3 * 300, 3), 15, dtype=np.uint8)
    for index, (field, title, high) in enumerate(metrics):
        panel = curve_panel(rows, field, title, high)
        row_index, column = divmod(index, 3)
        canvas[row_index * 210:(row_index + 1) * 210, column * 300:(column + 1) * 300] = panel
    directory = SURFACE_ROOT / unit["research_unit_id"] / anchor_variant
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "axis_rotation_separate_metric_curves.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}-{anchor_variant}-axis_rotation",
        "artifact_type": "separate_metric_rotation_curves", "research_unit_id": unit["research_unit_id"],
        "research_unit_type": unit["research_unit_type"], "scene": unit["scene"],
        "canonical_vehicle_id": unit["canonical_vehicle_id"], "anchor_variant": anchor_variant,
        "perturbation_family": "axis_rotation", "artifact_path": str(path), "review_status": review_status,
        "notes": "zero-degree vertical line is GT-derived baseline; no combined score or automatic winner",
    }


def single_field(
    unit: Mapping[str, Any],
    anchor_variant: str,
    index: int,
    setting: Mapping[str, float],
    cache: Mapping[int, tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    anchors = unit["raw_anchors"] if anchor_variant == "raw_gt" else unit["smooth_anchors"]
    axes = unit["raw_axes"] if anchor_variant == "raw_gt" else unit["smooth_axes"]
    row = unit["rows"][index]
    frame = int(row["sar_frame_index"])
    image, blurred = cache[frame]
    anchor = dict(anchors[index])
    radial, tangential = base.radial_tangential(anchor)
    center = np.asarray([anchor["cx"], anchor["cy"]], dtype=np.float64)
    center += radial * float(setting["radial"]) * unit["reference_radial_half"]
    center += tangential * float(setting["tangential"]) * unit["reference_tangential_half"]
    u, v = rotate_axes(axes[index][0], axes[index][1], float(setting["rotation"]))
    half_x = unit["reference_long"] * 0.5 * base.CROP_EXPANSION * float(setting["long"])
    half_y = unit["reference_short"] * 0.5 * base.CROP_EXPANSION * float(setting["short"])
    raw, valid = base.warp_axes(image, center, u, v, half_x, half_y)
    blur, _ = base.warp_axes(blurred, center, u, v, half_x, half_y)
    score = base.normalized_score(
        blur, valid, base.parse_float(row["local_background_median"]), base.parse_float(row["thread_raw_p99"]),
    )
    return raw, score, valid


def failure_probe_page(
    unit: Mapping[str, Any],
    anchor_variant: str,
    probe: Mapping[str, Any],
    cache: Mapping[int, tuple[np.ndarray, np.ndarray]],
    review_status: str,
) -> dict[str, Any]:
    baseline = {"radial": 0.0, "tangential": 0.0, "long": 1.0, "short": 1.0, "rotation": 0.0}
    indices = base.selected_indices(len(unit["rows"]), 4)
    canvas = np.full((len(indices) * 150, 4 * 260, 3), 15, dtype=np.uint8)
    for row_index, index in enumerate(indices):
        frame = unit["rows"][index]["sar_frame_index"]
        baseline_raw, baseline_score, baseline_valid = single_field(unit, anchor_variant, index, baseline, cache)
        probe_raw, probe_score, probe_valid = single_field(unit, anchor_variant, index, probe, cache)
        panels = (
            base.tile(base.colorize_gray(baseline_raw, baseline_valid), f"f{frame} baseline raw body"),
            base.tile(base.colorize_gray(probe_raw, probe_valid), f"f{frame} probe raw body"),
            base.tile(cv2.applyColorMap(np.round(baseline_score * 255.0).astype(np.uint8), cv2.COLORMAP_TURBO), f"f{frame} baseline response"),
            base.tile(cv2.applyColorMap(np.round(probe_score * 255.0).astype(np.uint8), cv2.COLORMAP_TURBO), f"f{frame} probe response"),
        )
        for column, panel in enumerate(panels):
            canvas[row_index * 150:(row_index + 1) * 150, column * 260:(column + 1) * 260] = panel
    directory = SURFACE_ROOT / unit["research_unit_id"] / anchor_variant
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{probe['label']}_frame_comparison.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}-{anchor_variant}-{probe['label']}",
        "artifact_type": "baseline_vs_tempting_perturbation_failure_probe",
        "research_unit_id": unit["research_unit_id"], "research_unit_type": unit["research_unit_type"],
        "scene": unit["scene"], "canonical_vehicle_id": unit["canonical_vehicle_id"],
        "anchor_variant": anchor_variant, "perturbation_family": "failure_probe",
        "artifact_path": str(path), "review_status": review_status,
        "notes": probe["note"] + "; this is not a selected relative optimum",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-status", choices=("pending_direct_review", "directly_reviewed_complete"), default="pending_direct_review")
    args = parser.parse_args()

    SURFACE_ROOT.mkdir(parents=True, exist_ok=True)
    local_fields = read_csv(LOCAL_FIELD_PATH)
    backgrounds = read_csv(BACKGROUND_PATH)
    by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in local_fields:
        if row["segment_id"] in VEHICLE_SEGMENTS:
            by_segment[row["segment_id"]].append(row)

    roles = {
        DEVELOPMENT_SEGMENT: "mechanism_discovery",
        HELDOUT_SEGMENTS[0]: "heldout_fixed_replay",
        HELDOUT_SEGMENTS[1]: "heldout_fixed_replay",
    }
    vehicles = {segment: augment_unit(base.build_vehicle_unit(by_segment[segment], roles[segment])) for segment in VEHICLE_SEGMENTS}
    fixed_background = augment_unit(base.build_fixed_background_unit(vehicles[DEVELOPMENT_SEGMENT], backgrounds))
    swap_23 = common_frame_unit(vehicles[DEVELOPMENT_SEGMENT], vehicles[HELDOUT_SEGMENTS[0]])
    swap_32 = common_frame_unit(vehicles[HELDOUT_SEGMENTS[0]], vehicles[DEVELOPMENT_SEGMENT])
    units = [vehicles[segment] for segment in VEHICLE_SEGMENTS] + [fixed_background, swap_23, swap_32]
    refs = reference_metrics()

    output_rows: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []
    counter = 1
    for unit in units:
        cache = image_cache(unit)
        anchor_variants = ("raw_gt", "smoothed_gt") if unit["research_unit_type"] == "vehicle_thread" else ("smoothed_gt",)
        for anchor_variant in anchor_variants:
            baseline_metrics, baseline_mean, baseline_occupancy, _, _, _ = evaluate_stack(
                unit, anchor_variant, 0.0, 0.0, 1.0, 1.0, 0.0, cache,
            )
            unit_rows: list[dict[str, Any]] = []
            for setting in settings():
                metrics, mean_score, occupancy, _, _, _ = evaluate_stack(
                    unit, anchor_variant, setting["radial"], setting["tangential"], setting["long"], setting["short"], setting["rotation"], cache,
                )
                recall, precision = baseline_overlap(occupancy, baseline_occupancy)
                mean_ncc = field_ncc(mean_score, baseline_mean)
                is_baseline = (
                    setting["radial"] == 0.0 and setting["tangential"] == 0.0
                    and setting["long"] == 1.0 and setting["short"] == 1.0 and setting["rotation"] == 0.0
                )
                world_ref = refs.get((unit["research_unit_id"], "world"), {})
                crop_ref = refs.get((unit["research_unit_id"], "smoothed_crop"), {})
                row = {
                    "perturbation_id": f"S1L-BSA-PERT-{counter:06d}", "research_unit_id": unit["research_unit_id"],
                    "research_unit_type": unit["research_unit_type"], "scene": unit["scene"],
                    "canonical_vehicle_id": unit["canonical_vehicle_id"], "benchmark_role": unit["benchmark_role"],
                    "research_role": unit["research_role"], "source_trajectory_segment_id": unit["source_trajectory_segment_id"],
                    "target_region_segment_id": unit.get("target_region_segment_id", unit["segment_id"]),
                    "anchor_variant": anchor_variant, "perturbation_family": setting["family"],
                    "radial_shift_fraction": fmt(setting["radial"]), "tangential_shift_fraction": fmt(setting["tangential"]),
                    "long_scale": fmt(setting["long"]), "short_scale": fmt(setting["short"]),
                    "rotation_delta_deg": fmt(setting["rotation"]), "is_gt_baseline": "true" if is_baseline else "false",
                    "frame_count": len(unit["rows"]),
                    "optical_corridor_constraint": "PASS_BY_BOUNDED_LOCAL_GRID" if unit["research_unit_type"] == "vehicle_thread" else "NOT_APPLICABLE_COUNTERFACTUAL",
                    "temporal_parameter_constraint": "PASS_CONSTANT_PARAMETER_OVER_COMPLETE_WINDOW",
                    "vehicle_scale_constraint": "PASS_FIXED_0.85_TO_1.15_AUDIT_RANGE" if unit["research_unit_type"] == "vehicle_thread" else "SOURCE_VEHICLE_SCALE_APPLIED_AS_FALSIFICATION",
                    "valid_mask_constraint": "PASS" if metrics["valid_fraction_min"] >= 0.95 else "FAIL",
                    "valid_fraction_mean": fmt(metrics["valid_fraction_mean"]), "valid_fraction_min": fmt(metrics["valid_fraction_min"]),
                    "boundary_missing_mean": fmt(metrics["boundary_missing_mean"]),
                    "adjacent_ncc_median": fmt(metrics["adjacent_ncc_median"]), "adjacent_ncc_p10": fmt(metrics["adjacent_ncc_p10"]),
                    "nonadjacent_similar_view_pair_count": metrics["nonadjacent_similar_view_pair_count"],
                    "nonadjacent_similar_view_ncc_median": fmt(metrics["nonadjacent_similar_view_ncc_median"]),
                    "support_entropy_mean_bits": fmt(metrics["support_entropy_mean_bits"]),
                    "support_area_fraction_mean": fmt(metrics["support_area_fraction_mean"]),
                    "support_area_fraction_cv": fmt(metrics["support_area_fraction_cv"]),
                    "outer_context_response_mass_fraction": fmt(metrics["outer_context_response_mass_fraction"]),
                    "baseline_mean_field_ncc": fmt(mean_ncc), "baseline_high_occupancy_recall": fmt(recall),
                    "baseline_high_occupancy_precision": fmt(precision),
                    "reference_world_adjacent_ncc": world_ref.get("adjacent_ncc_median", ""),
                    "reference_world_nonadjacent_ncc": world_ref.get("nonadjacent_similar_view_ncc_median", ""),
                    "reference_smoothed_crop_adjacent_ncc": crop_ref.get("adjacent_ncc_median", ""),
                    "reference_smoothed_crop_nonadjacent_ncc": crop_ref.get("nonadjacent_similar_view_ncc_median", ""),
                    "automatic_winner": "UNASSIGNED_NO_RANKING", "review_status": args.review_status,
                    "notes": "all metrics remain separate; baseline overlap is temporal-support overlap, not GT IoU",
                }
                counter += 1
                output_rows.append(row); unit_rows.append(row)

            center_rows = [row for row in unit_rows if row["perturbation_family"] == "center_shift"]
            scale_rows = [row for row in unit_rows if row["perturbation_family"] == "scale_surface"]
            rotation_rows = [row for row in unit_rows if row["perturbation_family"] == "axis_rotation"]
            visual_rows.append(surface_page(unit, anchor_variant, "center_shift", center_rows, args.review_status))
            visual_rows.append(surface_page(unit, anchor_variant, "scale_surface", scale_rows, args.review_status))
            visual_rows.append(rotation_page(unit, anchor_variant, rotation_rows, args.review_status))
            probe = FAILURE_PROBES.get((unit["research_unit_id"], anchor_variant))
            if probe:
                visual_rows.append(failure_probe_page(unit, anchor_variant, probe, cache, args.review_status))

    write_csv(SURFACE_OUTPUT_PATH, output_rows, SURFACE_FIELDS)
    write_csv(VISUAL_OUTPUT_PATH, visual_rows, VISUAL_FIELDS)
    summary = {
        "work_name": "S1-L Body Support Attribution and GT-Neighborhood Optimality Audit",
        "scope": "bounded symmetric GT-neighbourhood perturbation pilot",
        "review_status": args.review_status,
        "surface_row_count": len(output_rows),
        "visual_artifact_count": len(visual_rows),
        "vehicle_unit_count": 3,
        "counterfactual_unit_count": 3,
        "center_grid": list(CENTER_FRACTIONS), "scale_grid": list(SCALE_FACTORS), "rotation_grid_deg": list(ROTATION_DEGREES),
        "automatic_winner_assigned": False, "GT_IoU_used": False, "weighted_score_used": False,
        "final_stage_state_assigned": False, "s1d_allowed": False, "automatic_annotation_allowed": False,
        "latent_body_support_reconstruction_run": False,
        "outputs": {"surface_manifest": str(SURFACE_OUTPUT_PATH), "visual_manifest": str(VISUAL_OUTPUT_PATH), "temporary_visuals": str(SURFACE_ROOT)},
    }
    write_json(SUMMARY_PATH, summary)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(
            "2026-07-15 GT_NEIGHBORHOOD_PERTURBATION_RUN\n"
            f"review_status={args.review_status}\n"
            f"surface_rows={len(output_rows)}\n"
            f"visual_artifacts={len(visual_rows)}\n"
            "automatic_winner=false\nweighted_score=false\nGT_IoU=false\nlatent_support_reconstruction=false\n"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
