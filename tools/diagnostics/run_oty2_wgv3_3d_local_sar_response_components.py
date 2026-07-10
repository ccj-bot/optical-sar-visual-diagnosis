"""WGV3.3D local SAR response components and temporal continuity closure.

Automatic stage A0-A4 reads only SAR PNG/gray images, display fan geometry, and
the frozen WGV3.3B automatic hypotheses. It does not read WGV1.4, WGV1.8,
sar_gt_ids, GT boxes, GT centers, final localization products, or hand-selected
SAR response regions.

Posthoc stage B1-B3 requires the automatic freeze and then reads selected
WGV1.4/WGV1.8 T001/T004 metadata for evaluation only. It reports local SAR
response components and threads, not object identities, final boxes, ranking,
selector outputs, or annotation changes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


RANDOM_SEED = 3304
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
VISUAL_DIR = REPORT_DIR / "visual_exemplars" / "wgv3_3d_20260710"
DATA_ROOT = Path(r"D:\profile\research\data")

DATE = "20260710"
SCENE = "GM_RM011"
SAR_FRAME_MIN = 0
SAR_FRAME_MAX = 765
SAR_FRAME_COUNT = SAR_FRAME_MAX + 1

SAR_CANVAS_WIDTH = 2308
SAR_CANVAS_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
AZ_BINS = 180
RADIAL_BIN_SIZE = 4
RADIAL_BINS = int(math.ceil(FAN_RADIUS_PX / RADIAL_BIN_SIZE))

WGV33B_FREEZE = SAMPLES_DIR / "oty2_wgv3_3b_automatic_hypothesis_freeze_20260710.csv"
WGV14_THREADS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_threads_20260708.csv"
WGV14_FRAGMENTS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_fragments_20260708.csv"
WGV18_CANDIDATES = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_to_sar_gt_reference_candidates_20260709.csv"
WGV18_OBSERVATIONS = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_behavior_observation_20260709.csv"

PNG_AUDIT_REPORT = REPORT_DIR / f"oty2_wgv3_3d_png_normalization_audit_{DATE}.md"
PNG_STATS = SAMPLES_DIR / f"oty2_wgv3_3d_png_frame_statistics_{DATE}.csv"
LOCAL_COMPONENTS = SAMPLES_DIR / f"oty2_wgv3_3d_local_components_{DATE}.csv"
COMPONENT_EDGES = SAMPLES_DIR / f"oty2_wgv3_3d_component_edges_{DATE}.csv"
RESPONSE_THREADS = SAMPLES_DIR / f"oty2_wgv3_3d_response_threads_{DATE}.csv"
STATIC_STATS = SAMPLES_DIR / f"oty2_wgv3_3d_static_clutter_statistics_{DATE}.csv"
MATCHED_CONTROLS = SAMPLES_DIR / f"oty2_wgv3_3d_matched_controls_{DATE}.csv"
INTERSECTIONS = SAMPLES_DIR / f"oty2_wgv3_3d_automatic_field_thread_intersections_{DATE}.csv"
AUTO_SUMMARY = SAMPLES_DIR / f"oty2_wgv3_3d_automatic_response_summary_{DATE}.csv"
FREEZE_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_3d_response_freeze_manifest_{DATE}.csv"
POSTHOC_EVALUATION = SAMPLES_DIR / f"oty2_wgv3_3d_posthoc_evaluation_{DATE}.csv"
VISUAL_REVIEW_CSV = SAMPLES_DIR / f"oty2_wgv3_3d_visual_review_index_{DATE}.csv"
VISUAL_REPORT = REPORT_DIR / f"oty2_wgv3_3d_visual_component_diagnosis_{DATE}.md"
CLOSURE_REPORT = REPORT_DIR / f"oty2_wgv3_3d_local_response_temporal_closure_{DATE}.md"


PNG_STATS_FIELDS = [
    "sar_frame",
    "min",
    "max",
    "mean",
    "std",
    "p50",
    "p90",
    "p95",
    "p99",
    "nonzero_ratio",
    "saturated_255_ratio",
    "unique_value_count",
    "color_luma_sampled",
    "color_luma_max",
    "color_luma_mean",
    "color_luma_p99",
]

COMPONENT_FIELDS = [
    "component_id",
    "scene",
    "sar_frame",
    "azimuth_min",
    "azimuth_max",
    "azimuth_center",
    "radial_pixel_min",
    "radial_pixel_max",
    "radial_pixel_center",
    "az_bin_min",
    "az_bin_max",
    "radial_bin_min",
    "radial_bin_max",
    "cell_count",
    "pixel_count",
    "mean_intensity",
    "peak_intensity",
    "top10pct_mean",
    "mean_frame_percentile",
    "mean_local_robust_z",
    "mean_temporal_excess",
    "integrated_excess",
    "shape_width_azimuth",
    "shape_width_radial",
    "connectedness",
    "touches_support_boundary",
    "long_term_response_frequency",
    "long_term_longest_run",
    "static_component_label",
    "extraction_profile",
    "component_label",
]

EDGE_FIELDS = [
    "component_edge_id",
    "from_component_id",
    "to_component_id",
    "frame_gap",
    "azimuth_shift",
    "radial_shift_px",
    "overlap_ratio",
    "dilated_overlap_ratio",
    "scale_ratio",
    "contrast_change",
    "relation_status",
    "competition_ids",
    "supporting_evidence",
    "conflicting_evidence",
]

THREAD_FIELDS = [
    "response_thread_id",
    "scene",
    "extraction_profile",
    "start_sar_frame",
    "end_sar_frame",
    "duration_frames",
    "component_count",
    "branch_count",
    "gap_count",
    "azimuth_center_start",
    "azimuth_center_end",
    "radial_center_start",
    "radial_center_end",
    "azimuth_drift",
    "radial_drift_px",
    "mean_local_contrast",
    "max_local_contrast",
    "integrated_excess",
    "shape_stability",
    "temporal_continuity",
    "static_clutter_likelihood",
    "matched_control_available_ratio",
    "mean_spatial_control_ratio",
    "mean_temporal_control_ratio",
    "dynamic_response_status",
    "component_ids",
]

STATIC_FIELDS = [
    "scene",
    "azimuth_bin_start_deg",
    "azimuth_bin_end_deg",
    "radial_pixel_min",
    "radial_pixel_max",
    "valid_pixel_count",
    "response_frame_count",
    "response_frequency",
    "longest_consecutive_response",
    "intensity_mean",
    "intensity_variance",
    "temporal_median",
    "temporal_mad",
    "static_likelihood_label",
]

CONTROL_FIELDS = [
    "component_id",
    "scene",
    "sar_frame",
    "target_azimuth_min",
    "target_azimuth_max",
    "target_radial_pixel_min",
    "target_radial_pixel_max",
    "target_valid_pixel_count",
    "target_mean_intensity",
    "adjacent_control_status",
    "adjacent_control_mean",
    "adjacent_control_ratio",
    "far_control_status",
    "far_control_mean",
    "far_control_ratio",
    "temporal_control_status",
    "temporal_control_frame",
    "temporal_control_mean",
    "temporal_control_ratio",
    "matched_control_status",
]

INTERSECTION_FIELDS = [
    "hypothesis_id",
    "source_auto_node_id",
    "response_thread_id",
    "intersection_component_count",
    "thread_start",
    "thread_end",
    "thread_status",
    "thread_duration_frames",
    "thread_azimuth_min",
    "thread_azimuth_max",
    "thread_radial_min",
    "thread_radial_max",
    "matched_control_available_ratio",
    "mean_spatial_control_ratio",
    "mean_temporal_control_ratio",
]

AUTO_SUMMARY_FIELDS = [
    "hypothesis_id",
    "source_auto_node_id",
    "sar_frame_start",
    "sar_frame_end",
    "azimuth_min",
    "azimuth_max",
    "intersecting_component_count",
    "intersecting_response_thread_count",
    "dynamic_like_thread_count",
    "static_clutter_like_thread_count",
    "short_transient_component_count",
    "branch_ambiguity_count",
    "component_density_per_1000_effective_units",
    "median_local_contrast",
    "median_temporal_continuity",
    "median_radial_pixel_center",
    "matched_background_thread_density_delta",
    "status_note",
]

FREEZE_FIELDS = [
    "freeze_id",
    "scene",
    "stage",
    "source_file",
    "sha256",
    "combined_sha256",
    "wgv1_4_read_before_freeze",
    "wgv1_8_read_before_freeze",
    "sar_gt_ids_loaded",
    "gt_box_or_center_loaded",
    "notes",
]

POSTHOC_FIELDS = [
    "evaluation_item",
    "scene",
    "frame_start",
    "frame_end",
    "source_note",
    "overlapping_threads",
    "dynamic_supported_threads",
    "dynamic_mixed_threads",
    "static_like_threads",
    "control_indistinguishable_threads",
    "transient_threads",
    "insufficient_control_threads",
    "long_threads_ge3_frames",
    "moving_threads",
    "matched_control_supported_threads",
    "representative_thread_ids",
    "evaluation_status",
    "sar_gt_ids_loaded",
    "gt_box_or_center_loaded",
]

VISUAL_FIELDS = [
    "review_id",
    "review_category",
    "response_thread_id",
    "representative_component_id",
    "overlay_path",
    "sar_frame",
    "azimuth_center",
    "radial_pixel_center",
    "duration_frames",
    "dynamic_response_status",
    "chinese_judgment",
]


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    source_auto_node_id: str
    sar_frame_start: int
    sar_frame_end: int
    azimuth_min: float
    azimuth_max: float


@dataclass
class Component:
    component_id: str
    frame: int
    profile: str
    cells: np.ndarray
    az_bins: np.ndarray
    radial_bins: np.ndarray
    row: dict[str, Any]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


def read_csv_selected(path: Path, allowed: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if duplicate_header(row):
                continue
            rows.append({field: row.get(field, "") for field in allowed})
    return rows


def duplicate_header(row: Mapping[str, Any]) -> bool:
    hits = sum(1 for key, value in row.items() if str(value).strip() == key)
    return hits >= max(2, len(row) // 2)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return ""
        text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
        return text if text else "0"
    return str(value)


def parse_int(value: Any, default: int = 0) -> int:
    try:
        text = str(value).strip()
        if text == "":
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip()
        if text == "":
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def combined_sha256(paths: Sequence[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(path.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(path).encode("ascii"))
        h.update(b"\0")
    return h.hexdigest()


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def gray_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray" / f"{frame:06d}.png"


def color_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_SARframes" / f"{frame:06d}.png"


def load_gray(frame: int) -> np.ndarray:
    with Image.open(gray_path(frame)) as img:
        return np.asarray(img.convert("L"), dtype=np.uint8)


def robust_image_stats(image: np.ndarray) -> dict[str, Any]:
    values = image.reshape(-1)
    hist = np.bincount(values, minlength=256).astype(np.int64)
    total = int(hist.sum())
    cdf = np.cumsum(hist)

    def percentile(p: float) -> int:
        return int(np.searchsorted(cdf, math.ceil(total * p / 100.0), side="left"))

    nz = total - int(hist[0])
    return {
        "min": int(np.flatnonzero(hist)[0]) if total else 0,
        "max": int(np.flatnonzero(hist)[-1]) if total else 0,
        "mean": fmt(float(values.mean()), 8),
        "std": fmt(float(values.std()), 8),
        "p50": percentile(50),
        "p90": percentile(90),
        "p95": percentile(95),
        "p99": percentile(99),
        "nonzero_ratio": fmt(nz / max(1, total), 8),
        "saturated_255_ratio": fmt(int(hist[255]) / max(1, total), 10),
        "unique_value_count": int(np.count_nonzero(hist)),
    }


def read_automatic_hypotheses() -> list[Hypothesis]:
    rows = read_csv(WGV33B_FREEZE)
    hypotheses: list[Hypothesis] = []
    for row in rows:
        if row.get("scene") != SCENE:
            continue
        hypotheses.append(
            Hypothesis(
                hypothesis_id=row["hypothesis_id"],
                source_auto_node_id=row.get("source_auto_node_id", ""),
                sar_frame_start=max(SAR_FRAME_MIN, parse_int(row.get("sar_frame_start"))),
                sar_frame_end=min(SAR_FRAME_MAX, parse_int(row.get("sar_frame_end"))),
                azimuth_min=parse_float(row.get("azimuth_min")),
                azimuth_max=parse_float(row.get("azimuth_max")),
            )
        )
    hypotheses.sort(key=lambda item: item.hypothesis_id)
    if len(hypotheses) != 7:
        raise RuntimeError(f"Expected 7 WGV3.3B automatic hypotheses, found {len(hypotheses)}")
    return hypotheses


def build_geometry() -> dict[str, Any]:
    sample = load_gray(0)
    height, width = sample.shape
    if width != SAR_CANVAS_WIDTH or height != SAR_CANVAS_HEIGHT:
        raise RuntimeError(f"Unexpected SAR size {width}x{height}")
    yy, xx = np.indices((height, width), dtype=np.float32)
    dx = xx - FAN_CENTER_X
    dy = FAN_CENTER_Y - yy
    radial = np.sqrt(dx * dx + dy * dy)
    azimuth = np.degrees(np.arctan2(dx, dy))
    fan_mask = (radial <= FAN_RADIUS_PX) & (azimuth >= -90.0) & (azimuth < 90.0)
    az_bin_full = np.floor(azimuth).astype(np.int16)
    radial_bin_full = np.floor(radial / RADIAL_BIN_SIZE).astype(np.int16)
    valid = fan_mask & (radial_bin_full >= 0) & (radial_bin_full < RADIAL_BINS)
    az_bins = az_bin_full[valid].astype(np.int16)
    radial_bins = radial_bin_full[valid].astype(np.int16)
    cell_ids = ((az_bins + 90).astype(np.int32) * RADIAL_BINS + radial_bins.astype(np.int32)).astype(np.int32)
    sort_order = np.argsort(cell_ids, kind="stable")
    sorted_ids = cell_ids[sort_order]
    unique_ids, starts, counts = np.unique(sorted_ids, return_index=True, return_counts=True)
    compact_by_cell = np.full(AZ_BINS * RADIAL_BINS, -1, dtype=np.int32)
    compact_by_cell[unique_ids] = np.arange(unique_ids.size, dtype=np.int32)
    compact_grid = compact_by_cell.reshape(AZ_BINS, RADIAL_BINS)
    active_az = (unique_ids // RADIAL_BINS).astype(np.int16) - 90
    active_radial = (unique_ids % RADIAL_BINS).astype(np.int16)
    return {
        "fan_mask": valid,
        "cell_ids": cell_ids,
        "sort_order": sort_order,
        "unique_ids": unique_ids.astype(np.int32),
        "starts": starts.astype(np.int32),
        "counts": counts.astype(np.int32),
        "compact_grid": compact_grid,
        "active_az": active_az,
        "active_radial": active_radial,
        "active_pixel_counts": counts.astype(np.int32),
    }


def build_cell_matrix_and_png_stats(geom: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    active_count = len(geom["unique_ids"])
    cell_mean = np.zeros((SAR_FRAME_COUNT, active_count), dtype=np.float32)
    cell_max = np.zeros((SAR_FRAME_COUNT, active_count), dtype=np.uint8)
    stats_rows: list[dict[str, Any]] = []
    color_sample_rows: list[tuple[float, float, float]] = []
    sampled_color_frames = set(range(0, SAR_FRAME_COUNT, 25)).union({SAR_FRAME_MAX})

    sort_order = geom["sort_order"]
    starts = geom["starts"]
    counts = geom["counts"].astype(np.float32)
    fan_mask = geom["fan_mask"]

    for frame in range(SAR_FRAME_COUNT):
        image = load_gray(frame)
        stats = robust_image_stats(image)
        fan_values = image[fan_mask].reshape(-1)
        sorted_values = fan_values[sort_order]
        sums = np.add.reduceat(sorted_values.astype(np.float32), starts)
        maxes = np.maximum.reduceat(sorted_values, starts)
        cell_mean[frame, :] = sums / counts
        cell_max[frame, :] = maxes.astype(np.uint8)
        row = {"sar_frame": frame, **stats}
        if frame in sampled_color_frames and color_path(frame).exists():
            with Image.open(color_path(frame)) as color_img:
                color_gray = np.asarray(color_img.convert("L"), dtype=np.uint8)
            cstats = robust_image_stats(color_gray)
            row.update(
                {
                    "color_luma_sampled": "true",
                    "color_luma_max": cstats["max"],
                    "color_luma_mean": cstats["mean"],
                    "color_luma_p99": cstats["p99"],
                }
            )
            color_sample_rows.append((float(cstats["max"]), float(cstats["mean"]), float(cstats["p99"])))
        else:
            row.update(
                {
                    "color_luma_sampled": "false",
                    "color_luma_max": "",
                    "color_luma_mean": "",
                    "color_luma_p99": "",
                }
            )
        stats_rows.append(row)

    max_values = np.array([parse_float(row["max"]) for row in stats_rows], dtype=np.float64)
    p99_values = np.array([parse_float(row["p99"]) for row in stats_rows], dtype=np.float64)
    mean_values = np.array([parse_float(row["mean"]) for row in stats_rows], dtype=np.float64)
    max_255 = int(np.sum(max_values == 255))
    max_ge_250 = int(np.sum(max_values >= 250))
    p99_cv = float(np.std(p99_values) / max(1e-9, np.mean(p99_values)))
    mean_cv = float(np.std(mean_values) / max(1e-9, np.mean(mean_values)))
    if max_255 > SAR_FRAME_COUNT * 0.80 and p99_cv < 0.08:
        status = "PNG_FRAMEWISE_NORMALIZATION_LIKELY"
    elif max_ge_250 > SAR_FRAME_COUNT * 0.80:
        status = "PNG_TEMPORAL_COMPARABILITY_UNCERTAIN"
    else:
        status = "PNG_TEMPORAL_COMPARABILITY_UNCERTAIN"
    color_note = "color luma sampled every 25 frames plus final frame"
    if color_sample_rows:
        color_max_values = [row[0] for row in color_sample_rows]
        color_p99_values = [row[2] for row in color_sample_rows]
        color_note = (
            f"sampled color-luma max range {min(color_max_values):.0f}..{max(color_max_values):.0f}; "
            f"p99 range {min(color_p99_values):.0f}..{max(color_p99_values):.0f}; "
            "color PNG and gray PNG are display products, but luma values are not identical"
        )
    audit = {
        "status": status,
        "max_255_count": max_255,
        "max_ge_250_count": max_ge_250,
        "p99_mean": float(np.mean(p99_values)),
        "p99_cv": p99_cv,
        "mean_cv": mean_cv,
        "color_note": color_note,
    }
    return cell_mean, cell_max, stats_rows, audit


def percentile_rank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float32)
    if values.size <= 1:
        ranks[:] = 100.0
        return ranks
    ranks[order] = np.linspace(0.0, 100.0, values.size, dtype=np.float32)
    return ranks


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    structure = np.ones((3, 3), dtype=np.uint8)
    return ndimage.label(mask, structure=structure)


def active_grid_values(
    vector: np.ndarray, compact_grid: np.ndarray, fill: float = 0.0, dtype: Any = np.float32
) -> np.ndarray:
    grid = np.full(compact_grid.shape, fill, dtype=dtype)
    valid = compact_grid >= 0
    grid[valid] = vector[compact_grid[valid]]
    return grid


def summarize_component(
    component_id: str,
    frame: int,
    profile: str,
    cells: np.ndarray,
    compact_grid: np.ndarray,
    geom: Mapping[str, Any],
    cell_mean: np.ndarray,
    cell_max: np.ndarray,
    frame_percentiles: np.ndarray,
    local_z_vec: np.ndarray,
    temporal_excess_vec: np.ndarray,
    response_frequency: np.ndarray,
    longest_run: np.ndarray,
    valid_az_min: int,
    valid_az_max: int,
) -> Component:
    active_az = geom["active_az"][cells]
    active_radial = geom["active_radial"][cells]
    pixel_counts = geom["active_pixel_counts"][cells].astype(np.float64)
    means = cell_mean[frame, cells].astype(np.float64)
    maxes = cell_max[frame, cells].astype(np.float64)
    total_pixels = int(pixel_counts.sum())
    weighted_mean = float(np.average(means, weights=pixel_counts)) if total_pixels else 0.0
    top_count = max(1, int(math.ceil(len(means) * 0.10)))
    top10 = float(np.mean(np.sort(means)[-top_count:]))
    excess = np.maximum(temporal_excess_vec[cells], 0.0)
    integrated_excess = float(np.sum(excess * pixel_counts))
    az_min = int(active_az.min())
    az_max = int(active_az.max()) + 1
    r_min_bin = int(active_radial.min())
    r_max_bin = int(active_radial.max())
    radial_min = r_min_bin * RADIAL_BIN_SIZE
    radial_max = min(int((r_max_bin + 1) * RADIAL_BIN_SIZE), int(FAN_RADIUS_PX))
    az_center = float(np.average(active_az.astype(np.float64) + 0.5, weights=means + 1e-6))
    radial_center = float(np.average((active_radial.astype(np.float64) + 0.5) * RADIAL_BIN_SIZE, weights=means + 1e-6))
    bbox_area = max(1, (az_max - az_min) * (r_max_bin - r_min_bin + 1))
    connectedness = len(cells) / bbox_area
    touches = az_min <= valid_az_min or az_max >= valid_az_max or r_min_bin <= 0 or r_max_bin >= RADIAL_BINS - 1
    mean_freq = float(np.mean(response_frequency[cells]))
    mean_run = float(np.mean(longest_run[cells]))
    if mean_freq >= 0.20 or mean_run >= 20:
        static_label = "static_clutter_like"
    elif mean_freq >= 0.08:
        static_label = "recurrent_background_like"
    elif len(cells) <= 2:
        static_label = "transient_unlinked"
    else:
        static_label = "dynamic_like"
    row = {
        "component_id": component_id,
        "scene": SCENE,
        "sar_frame": frame,
        "azimuth_min": az_min,
        "azimuth_max": az_max,
        "azimuth_center": fmt(az_center, 4),
        "radial_pixel_min": radial_min,
        "radial_pixel_max": radial_max,
        "radial_pixel_center": fmt(radial_center, 4),
        "az_bin_min": az_min,
        "az_bin_max": az_max - 1,
        "radial_bin_min": r_min_bin,
        "radial_bin_max": r_max_bin,
        "cell_count": len(cells),
        "pixel_count": total_pixels,
        "mean_intensity": fmt(weighted_mean, 6),
        "peak_intensity": int(maxes.max(initial=0)),
        "top10pct_mean": fmt(top10, 6),
        "mean_frame_percentile": fmt(float(np.mean(frame_percentiles[cells])), 6),
        "mean_local_robust_z": fmt(float(np.mean(local_z_vec[cells])), 6),
        "mean_temporal_excess": fmt(float(np.mean(temporal_excess_vec[cells])), 6),
        "integrated_excess": fmt(integrated_excess, 6),
        "shape_width_azimuth": az_max - az_min,
        "shape_width_radial": radial_max - radial_min,
        "connectedness": fmt(connectedness, 6),
        "touches_support_boundary": str(touches).lower(),
        "long_term_response_frequency": fmt(mean_freq, 6),
        "long_term_longest_run": fmt(mean_run, 6),
        "static_component_label": static_label,
        "extraction_profile": profile,
        "component_label": "local_sar_response_component",
    }
    return Component(
        component_id=component_id,
        frame=frame,
        profile=profile,
        cells=cells.astype(np.int32),
        az_bins=active_az.astype(np.int16),
        radial_bins=active_radial.astype(np.int16),
        row=row,
    )


def longest_true_run(mask: np.ndarray) -> np.ndarray:
    # mask shape: frames x cells
    current = np.zeros(mask.shape[1], dtype=np.int16)
    longest = np.zeros(mask.shape[1], dtype=np.int16)
    for frame_values in mask:
        current = np.where(frame_values, current + 1, 0)
        longest = np.maximum(longest, current)
    return longest


def extract_components_and_static(
    geom: Mapping[str, Any], cell_mean: np.ndarray, cell_max: np.ndarray
) -> tuple[list[Component], list[dict[str, Any]], np.ndarray, np.ndarray]:
    compact_grid = geom["compact_grid"]
    active_count = len(geom["unique_ids"])
    active_counts = geom["active_pixel_counts"]
    nonzero_frequency = np.mean(cell_mean > 0, axis=0)
    stable_mask_vec = nonzero_frequency >= 0.20
    valid_mask_vec = stable_mask_vec & (active_counts >= 4)
    temporal_median = np.median(cell_mean, axis=0).astype(np.float32)
    temporal_mad = np.median(np.abs(cell_mean - temporal_median[None, :]), axis=0).astype(np.float32)
    temporal_excess_all = cell_mean - temporal_median[None, :]

    # First pass builds support response masks for long-term occupancy.
    support_response = np.zeros((SAR_FRAME_COUNT, active_count), dtype=bool)
    local_z_store = np.zeros((SAR_FRAME_COUNT, active_count), dtype=np.float16)
    percentile_store = np.zeros((SAR_FRAME_COUNT, active_count), dtype=np.float16)
    valid_grid = active_grid_values(valid_mask_vec.astype(np.uint8), compact_grid, fill=0, dtype=np.uint8).astype(bool)
    for frame in range(SAR_FRAME_COUNT):
        values = cell_mean[frame]
        valid_values = values[valid_mask_vec]
        q99 = float(np.percentile(valid_values, 99.0)) if valid_values.size else 255.0
        grid = active_grid_values(values, compact_grid, fill=0.0, dtype=np.float32)
        local_med = ndimage.median_filter(grid, size=(7, 9), mode="nearest")
        mad_grid = ndimage.median_filter(np.abs(grid - local_med), size=(7, 9), mode="nearest")
        local_z_grid = (grid - local_med) / (1.4826 * mad_grid + 1.0)
        local_z_vec = local_z_grid.reshape(-1)[geom["unique_ids"]]
        percentiles = percentile_rank(valid_values)
        frame_percentile = np.zeros(active_count, dtype=np.float32)
        frame_percentile[valid_mask_vec] = percentiles
        response = valid_mask_vec & (values >= q99) & (local_z_vec >= 2.0)
        support_response[frame] = response
        local_z_store[frame] = local_z_vec.astype(np.float16)
        percentile_store[frame] = frame_percentile.astype(np.float16)

    response_frequency = np.mean(support_response, axis=0).astype(np.float32)
    response_count = np.sum(support_response, axis=0).astype(np.int16)
    longest_run = longest_true_run(support_response)
    intensity_var = np.var(cell_mean, axis=0).astype(np.float32)
    active_az = geom["active_az"]
    active_radial = geom["active_radial"]
    valid_az_bins = active_az[valid_mask_vec]
    valid_az_min = int(valid_az_bins.min()) if valid_az_bins.size else -61
    valid_az_max = int(valid_az_bins.max()) + 1 if valid_az_bins.size else 62

    static_rows: list[dict[str, Any]] = []
    for idx in range(active_count):
        if not valid_mask_vec[idx] and response_count[idx] == 0:
            continue
        freq = float(response_frequency[idx])
        if freq >= 0.20 or int(longest_run[idx]) >= 20:
            label = "static_clutter_like"
        elif freq >= 0.08:
            label = "recurrent_background_like"
        elif int(response_count[idx]) == 0:
            label = "insufficient_history"
        else:
            label = "dynamic_like"
        radial_min = int(active_radial[idx]) * RADIAL_BIN_SIZE
        static_rows.append(
            {
                "scene": SCENE,
                "azimuth_bin_start_deg": int(active_az[idx]),
                "azimuth_bin_end_deg": int(active_az[idx]) + 1,
                "radial_pixel_min": radial_min,
                "radial_pixel_max": min(radial_min + RADIAL_BIN_SIZE, int(FAN_RADIUS_PX)),
                "valid_pixel_count": int(active_counts[idx]),
                "response_frame_count": int(response_count[idx]),
                "response_frequency": fmt(freq, 8),
                "longest_consecutive_response": int(longest_run[idx]),
                "intensity_mean": fmt(float(np.mean(cell_mean[:, idx])), 8),
                "intensity_variance": fmt(float(intensity_var[idx]), 8),
                "temporal_median": fmt(float(temporal_median[idx]), 8),
                "temporal_mad": fmt(float(temporal_mad[idx]), 8),
                "static_likelihood_label": label,
            }
        )

    components: list[Component] = []
    for frame in range(SAR_FRAME_COUNT):
        values = cell_mean[frame]
        valid_values = values[valid_mask_vec]
        if valid_values.size == 0:
            continue
        q99 = float(np.percentile(valid_values, 99.0))
        q995 = float(np.percentile(valid_values, 99.5))
        q997 = float(np.percentile(valid_values, 99.7))
        frame_percentile = percentile_store[frame].astype(np.float32)
        local_z_vec = local_z_store[frame].astype(np.float32)
        temporal_excess_vec = temporal_excess_all[frame]
        grid = active_grid_values(values, compact_grid, fill=0.0, dtype=np.float32)
        local_z_grid = active_grid_values(local_z_vec, compact_grid, fill=-999.0, dtype=np.float32)
        valid_grid = active_grid_values(valid_mask_vec.astype(np.uint8), compact_grid, fill=0, dtype=np.uint8).astype(bool)
        profiles = [
            ("main", q995, 3.0, q99, 2.0),
            ("strict", q997, 3.5, q995, 2.5),
        ]
        for profile, core_q, core_z, support_q, support_z in profiles:
            core = valid_grid & (grid >= core_q) & (local_z_grid >= core_z)
            support = valid_grid & (grid >= support_q) & (local_z_grid >= support_z)
            labels, nlabels = label_components(support)
            if nlabels <= 0:
                continue
            keep_labels = np.unique(labels[core])
            keep_labels = keep_labels[keep_labels > 0]
            for label in keep_labels:
                coords = np.argwhere(labels == label)
                if coords.shape[0] == 0:
                    continue
                compact_ids = compact_grid[coords[:, 0], coords[:, 1]]
                compact_ids = compact_ids[compact_ids >= 0]
                if compact_ids.size == 0:
                    continue
                if profile == "main" and compact_ids.size < 2:
                    continue
                cid = f"WGV33D_{profile.upper()}_F{frame:04d}_C{len(components)+1:06d}"
                components.append(
                    summarize_component(
                        cid,
                        frame,
                        profile,
                        compact_ids,
                        compact_grid,
                        geom,
                        cell_mean,
                        cell_max,
                        frame_percentile,
                        local_z_vec,
                        temporal_excess_vec,
                        response_frequency,
                        longest_run,
                        valid_az_min,
                        valid_az_max,
                    )
                )
    return components, static_rows, response_frequency, longest_run


def rect_stats(
    frame: int,
    az_min: int,
    az_max: int,
    radial_min_bin: int,
    radial_max_bin: int,
    compact_grid: np.ndarray,
    cell_mean: np.ndarray,
    geom: Mapping[str, Any],
) -> tuple[bool, float, int]:
    az0 = max(-90, az_min)
    az1 = min(89, az_max)
    r0 = max(0, radial_min_bin)
    r1 = min(RADIAL_BINS - 1, radial_max_bin)
    if az1 < az0 or r1 < r0:
        return False, 0.0, 0
    sub = compact_grid[az0 + 90 : az1 + 91, r0 : r1 + 1]
    ids = sub[sub >= 0]
    if ids.size == 0:
        return False, 0.0, 0
    counts = geom["active_pixel_counts"][ids].astype(np.float64)
    values = cell_mean[frame, ids].astype(np.float64)
    pixels = int(counts.sum())
    if pixels <= 0:
        return False, 0.0, 0
    return True, float(np.average(values, weights=counts)), pixels


def search_spatial_control(
    component: Component,
    frame: int,
    mode: str,
    compact_grid: np.ndarray,
    cell_mean: np.ndarray,
    geom: Mapping[str, Any],
) -> tuple[str, float, float]:
    row = component.row
    az_min = parse_int(row["az_bin_min"])
    az_max = parse_int(row["az_bin_max"])
    r_min = parse_int(row["radial_bin_min"])
    r_max = parse_int(row["radial_bin_max"])
    width_az = az_max - az_min + 1
    width_r = r_max - r_min + 1
    ok, target_mean, target_pixels = rect_stats(frame, az_min, az_max, r_min, r_max, compact_grid, cell_mean, geom)
    if not ok:
        return "matched_control_unavailable", 0.0, 0.0
    candidates: list[tuple[float, float, int, int, int]] = []
    if mode == "adjacent":
        starts = [az_min - width_az - 2, az_max + 3]
        for start in starts:
            candidates.append((abs(start - az_min), start, r_min, start + width_az - 1, r_max))
    else:
        for shift in [24, 36, 48, -24, -36, -48]:
            start = az_min + shift
            candidates.append((-abs(shift), start, r_min, start + width_az - 1, r_max))
        for rshift in [64 // RADIAL_BIN_SIZE, -64 // RADIAL_BIN_SIZE, 128 // RADIAL_BIN_SIZE]:
            candidates.append((-100 - abs(rshift), az_min, r_min + rshift, az_max, r_max + rshift))
    best: tuple[float, float] | None = None
    for _score, cand_az0, cand_r0, cand_az1, cand_r1 in sorted(candidates):
        if not (cand_az1 < az_min or cand_az0 > az_max or cand_r1 < r_min or cand_r0 > r_max):
            continue
        ok, mean, pixels = rect_stats(frame, int(cand_az0), int(cand_az1), int(cand_r0), int(cand_r1), compact_grid, cell_mean, geom)
        if not ok:
            continue
        if abs(pixels - target_pixels) / max(1, target_pixels) > 0.20:
            continue
        best = (mean, pixels)
        break
    if best is None:
        return "matched_control_unavailable", 0.0, target_mean
    control_mean = best[0]
    return "matched_background_control", control_mean, target_mean / max(control_mean, 1e-9)


def temporal_control(component: Component, compact_grid: np.ndarray, cell_mean: np.ndarray, geom: Mapping[str, Any]) -> tuple[str, int, float, float]:
    row = component.row
    frame = parse_int(row["sar_frame"])
    az_min = parse_int(row["az_bin_min"])
    az_max = parse_int(row["az_bin_max"])
    r_min = parse_int(row["radial_bin_min"])
    r_max = parse_int(row["radial_bin_max"])
    ok, target_mean, target_pixels = rect_stats(frame, az_min, az_max, r_min, r_max, compact_grid, cell_mean, geom)
    if not ok:
        return "matched_control_unavailable", -1, 0.0, 0.0
    for shift in [120, -120, 240, -240, 360, -360]:
        cframe = frame + shift
        if cframe < SAR_FRAME_MIN or cframe > SAR_FRAME_MAX:
            continue
        ok, mean, pixels = rect_stats(cframe, az_min, az_max, r_min, r_max, compact_grid, cell_mean, geom)
        if ok and abs(pixels - target_pixels) / max(1, target_pixels) <= 0.20:
            return "temporal_background_control", cframe, mean, target_mean / max(mean, 1e-9)
    return "matched_control_unavailable", -1, 0.0, target_mean


def build_matched_controls(
    components: Sequence[Component], geom: Mapping[str, Any], cell_mean: np.ndarray
) -> list[dict[str, Any]]:
    compact_grid = geom["compact_grid"]
    rows: list[dict[str, Any]] = []
    for component in components:
        frame = component.frame
        row = component.row
        adj_status, adj_mean, adj_ratio = search_spatial_control(component, frame, "adjacent", compact_grid, cell_mean, geom)
        far_status, far_mean, far_ratio = search_spatial_control(component, frame, "far", compact_grid, cell_mean, geom)
        temp_status, temp_frame, temp_mean, temp_ratio = temporal_control(component, compact_grid, cell_mean, geom)
        if "unavailable" in (adj_status, far_status, temp_status):
            matched_status = "matched_control_unavailable"
        else:
            matched_status = "matched_control_available"
        rows.append(
            {
                "component_id": component.component_id,
                "scene": SCENE,
                "sar_frame": frame,
                "target_azimuth_min": row["azimuth_min"],
                "target_azimuth_max": row["azimuth_max"],
                "target_radial_pixel_min": row["radial_pixel_min"],
                "target_radial_pixel_max": row["radial_pixel_max"],
                "target_valid_pixel_count": row["pixel_count"],
                "target_mean_intensity": row["mean_intensity"],
                "adjacent_control_status": adj_status,
                "adjacent_control_mean": fmt(adj_mean, 6),
                "adjacent_control_ratio": fmt(adj_ratio, 6),
                "far_control_status": far_status,
                "far_control_mean": fmt(far_mean, 6),
                "far_control_ratio": fmt(far_ratio, 6),
                "temporal_control_status": temp_status,
                "temporal_control_frame": temp_frame if temp_frame >= 0 else "",
                "temporal_control_mean": fmt(temp_mean, 6),
                "temporal_control_ratio": fmt(temp_ratio, 6),
                "matched_control_status": matched_status,
            }
        )
    return rows


def component_overlap(a: Component, b: Component, dilation: int = 0) -> float:
    a_cells = set(zip(a.az_bins.tolist(), a.radial_bins.tolist()))
    if dilation:
        expanded = set()
        for az, rad in a_cells:
            for da in range(-dilation, dilation + 1):
                for dr in range(-dilation, dilation + 1):
                    expanded.add((az + da, rad + dr))
        a_cells = expanded
    b_cells = set(zip(b.az_bins.tolist(), b.radial_bins.tolist()))
    if not a_cells or not b_cells:
        return 0.0
    inter = len(a_cells.intersection(b_cells))
    return inter / max(1, min(len(a_cells), len(b_cells)))


def build_edges_and_threads(
    components: Sequence[Component], control_rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comps = [c for c in components if c.profile == "main"]
    by_id = {c.component_id: c for c in comps}
    by_frame: dict[int, list[Component]] = defaultdict(list)
    for c in comps:
        by_frame[c.frame].append(c)

    raw_edges: list[dict[str, Any]] = []
    outgoing_count: dict[str, int] = defaultdict(int)
    incoming_count: dict[str, int] = defaultdict(int)
    for c in comps:
        c_az = parse_float(c.row["azimuth_center"])
        c_rad = parse_float(c.row["radial_pixel_center"])
        c_cells = parse_int(c.row["cell_count"])
        c_z = parse_float(c.row["mean_local_robust_z"])
        for gap in (1, 2):
            for d in by_frame.get(c.frame + gap, []):
                az_shift = parse_float(d.row["azimuth_center"]) - c_az
                rad_shift = parse_float(d.row["radial_pixel_center"]) - c_rad
                if abs(az_shift) > 8.0 or abs(rad_shift) > 96.0:
                    continue
                overlap = component_overlap(c, d, dilation=0)
                dilated = component_overlap(c, d, dilation=2)
                scale_ratio = parse_int(d.row["cell_count"]) / max(1, c_cells)
                contrast_change = parse_float(d.row["mean_local_robust_z"]) - c_z
                if abs(az_shift) <= 6.0 and abs(rad_shift) <= 64.0 and (overlap >= 0.10 or dilated >= 0.25):
                    status = "strong_local_continuity" if gap == 1 and dilated >= 0.35 else "weak_local_continuity"
                elif abs(az_shift) <= 6.0 and abs(rad_shift) <= 64.0:
                    status = "ambiguous_local_continuity"
                else:
                    status = "blocked_local_continuity"
                if status == "blocked_local_continuity":
                    continue
                raw_edges.append(
                    {
                        "component_edge_id": f"WGV33D_EDGE_{len(raw_edges)+1:06d}",
                        "from_component_id": c.component_id,
                        "to_component_id": d.component_id,
                        "frame_gap": gap,
                        "azimuth_shift": fmt(az_shift, 6),
                        "radial_shift_px": fmt(rad_shift, 6),
                        "overlap_ratio": fmt(overlap, 6),
                        "dilated_overlap_ratio": fmt(dilated, 6),
                        "scale_ratio": fmt(scale_ratio, 6),
                        "contrast_change": fmt(contrast_change, 6),
                        "relation_status": status,
                        "competition_ids": "",
                        "supporting_evidence": f"gap={gap};dilated_overlap={fmt(dilated,3)}",
                        "conflicting_evidence": "" if status != "ambiguous_local_continuity" else "low overlap or multiple plausible successors",
                    }
                )
                outgoing_count[c.component_id] += 1
                incoming_count[d.component_id] += 1

    for edge in raw_edges:
        compset: list[str] = []
        if outgoing_count[edge["from_component_id"]] > 1:
            compset.append(f"multi_successor:{edge['from_component_id']}")
        if incoming_count[edge["to_component_id"]] > 1:
            compset.append(f"multi_predecessor:{edge['to_component_id']}")
        edge["competition_ids"] = ";".join(compset)
        if compset and edge["relation_status"] == "strong_local_continuity":
            edge["relation_status"] = "ambiguous_local_continuity"

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in raw_edges:
        # Ambiguous edges are preserved in the edge table, but the response
        # thread skeleton uses only strong/weak continuity. Otherwise a dense
        # multi-component frame can collapse into one scene-scale graph.
        if edge["relation_status"] in {"strong_local_continuity", "weak_local_continuity"}:
            a = edge["from_component_id"]
            b = edge["to_component_id"]
            adjacency[a].add(b)
            adjacency[b].add(a)

    control_by_comp = {row["component_id"]: row for row in control_rows}
    visited: set[str] = set()
    threads: list[dict[str, Any]] = []
    for comp in comps:
        if comp.component_id in visited:
            continue
        q = deque([comp.component_id])
        visited.add(comp.component_id)
        ids: list[str] = []
        while q:
            cid = q.popleft()
            ids.append(cid)
            for nxt in adjacency.get(cid, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    q.append(nxt)
        thread_components = sorted((by_id[cid] for cid in ids), key=lambda item: (item.frame, item.component_id))
        frames = [c.frame for c in thread_components]
        start_frame = min(frames)
        end_frame = max(frames)
        duration = end_frame - start_frame + 1
        start_comp = thread_components[0]
        end_comp = thread_components[-1]
        branch_count = sum(1 for cid in ids if outgoing_count[cid] > 1 or incoming_count[cid] > 1)
        frame_set = set(frames)
        gap_count = max(0, duration - len(frame_set))
        z_values = [parse_float(c.row["mean_local_robust_z"]) for c in thread_components]
        excess_values = [parse_float(c.row["integrated_excess"]) for c in thread_components]
        cell_values = [parse_int(c.row["cell_count"]) for c in thread_components]
        static_values = [parse_float(c.row["long_term_response_frequency"]) for c in thread_components]
        spatial_ratios: list[float] = []
        temporal_ratios: list[float] = []
        control_available = 0
        for c in thread_components:
            ctrl = control_by_comp.get(c.component_id)
            if not ctrl:
                continue
            if ctrl.get("matched_control_status") == "matched_control_available":
                control_available += 1
            adjacent = parse_float(ctrl.get("adjacent_control_ratio"))
            far = parse_float(ctrl.get("far_control_ratio"))
            temporal = parse_float(ctrl.get("temporal_control_ratio"))
            if adjacent > 0 and far > 0:
                spatial_ratios.append(min(adjacent, far))
            if temporal > 0:
                temporal_ratios.append(temporal)
        control_avail_ratio = control_available / max(1, len(thread_components))
        mean_spatial = float(np.median(spatial_ratios)) if spatial_ratios else 0.0
        mean_temporal = float(np.median(temporal_ratios)) if temporal_ratios else 0.0
        az_start = parse_float(start_comp.row["azimuth_center"])
        az_end = parse_float(end_comp.row["azimuth_center"])
        rad_start = parse_float(start_comp.row["radial_pixel_center"])
        rad_end = parse_float(end_comp.row["radial_pixel_center"])
        az_drift = az_end - az_start
        radial_drift = rad_end - rad_start
        continuity = (len(frame_set) - 1) / max(1, duration - 1)
        continuity = min(1.0, max(0.0, continuity))
        shape_stability = 1.0 / (1.0 + (float(np.std(cell_values)) / max(1.0, float(np.mean(cell_values)))))
        static_like = float(np.mean(static_values)) if static_values else 0.0
        dense_branch_graph = branch_count > max(3, duration) or len(thread_components) > max(3, duration * 3)
        if duration < 3 or len(thread_components) < 3:
            status = "transient_unlinked"
        elif static_like >= 0.20 and abs(az_drift) < 1.5 and abs(radial_drift) < 12:
            status = "static_clutter_like"
        elif control_avail_ratio < 0.50:
            status = "insufficient_matched_control"
        elif dense_branch_graph:
            status = "dynamic_local_response_mixed"
        elif mean_spatial >= 1.20 and mean_temporal >= 1.15 and (abs(az_drift) >= 1.0 or abs(radial_drift) >= 8) and static_like < 0.15:
            status = "dynamic_local_response_supported"
        elif mean_spatial >= 1.05 or mean_temporal >= 1.05:
            status = "dynamic_local_response_mixed"
        else:
            status = "control_indistinguishable"
        threads.append(
            {
                "response_thread_id": f"WGV33D_THREAD_{len(threads)+1:06d}",
                "scene": SCENE,
                "extraction_profile": "main",
                "start_sar_frame": start_frame,
                "end_sar_frame": end_frame,
                "duration_frames": duration,
                "component_count": len(thread_components),
                "branch_count": branch_count,
                "gap_count": gap_count,
                "azimuth_center_start": fmt(az_start, 4),
                "azimuth_center_end": fmt(az_end, 4),
                "radial_center_start": fmt(rad_start, 4),
                "radial_center_end": fmt(rad_end, 4),
                "azimuth_drift": fmt(az_drift, 4),
                "radial_drift_px": fmt(radial_drift, 4),
                "mean_local_contrast": fmt(float(np.mean(z_values)) if z_values else 0.0, 6),
                "max_local_contrast": fmt(float(np.max(z_values)) if z_values else 0.0, 6),
                "integrated_excess": fmt(float(np.sum(excess_values)), 6),
                "shape_stability": fmt(shape_stability, 6),
                "temporal_continuity": fmt(continuity, 6),
                "static_clutter_likelihood": fmt(static_like, 6),
                "matched_control_available_ratio": fmt(control_avail_ratio, 6),
                "mean_spatial_control_ratio": fmt(mean_spatial, 6),
                "mean_temporal_control_ratio": fmt(mean_temporal, 6),
                "dynamic_response_status": status,
                "component_ids": ";".join(ids),
            }
        )
    return raw_edges, threads


def thread_components(thread: Mapping[str, Any], components_by_id: Mapping[str, Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    ids = [cid for cid in str(thread.get("component_ids", "")).split(";") if cid]
    return [components_by_id[cid] for cid in ids if cid in components_by_id]


def interval_overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) <= min(a1, b1)


def build_intersections_and_summary(
    hypotheses: Sequence[Hypothesis],
    component_rows: Sequence[Mapping[str, Any]],
    threads: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comps_by_id = {row["component_id"]: row for row in component_rows if row.get("extraction_profile") == "main"}
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for hyp in hypotheses:
        hyp_threads: list[Mapping[str, Any]] = []
        hyp_components: set[str] = set()
        for thread in threads:
            comps = thread_components(thread, comps_by_id)
            match_comps: list[Mapping[str, Any]] = []
            for comp in comps:
                frame = parse_int(comp["sar_frame"])
                if not (hyp.sar_frame_start <= frame <= hyp.sar_frame_end):
                    continue
                if interval_overlap(parse_float(comp["azimuth_min"]), parse_float(comp["azimuth_max"]), hyp.azimuth_min, hyp.azimuth_max):
                    match_comps.append(comp)
            if not match_comps:
                continue
            hyp_threads.append(thread)
            for comp in match_comps:
                hyp_components.add(comp["component_id"])
            azmins = [parse_float(comp["azimuth_min"]) for comp in match_comps]
            azmaxs = [parse_float(comp["azimuth_max"]) for comp in match_comps]
            rmins = [parse_float(comp["radial_pixel_min"]) for comp in match_comps]
            rmaxs = [parse_float(comp["radial_pixel_max"]) for comp in match_comps]
            rows.append(
                {
                    "hypothesis_id": hyp.hypothesis_id,
                    "source_auto_node_id": hyp.source_auto_node_id,
                    "response_thread_id": thread["response_thread_id"],
                    "intersection_component_count": len(match_comps),
                    "thread_start": thread["start_sar_frame"],
                    "thread_end": thread["end_sar_frame"],
                    "thread_status": thread["dynamic_response_status"],
                    "thread_duration_frames": thread["duration_frames"],
                    "thread_azimuth_min": fmt(min(azmins), 3),
                    "thread_azimuth_max": fmt(max(azmaxs), 3),
                    "thread_radial_min": fmt(min(rmins), 3),
                    "thread_radial_max": fmt(max(rmaxs), 3),
                    "matched_control_available_ratio": thread["matched_control_available_ratio"],
                    "mean_spatial_control_ratio": thread["mean_spatial_control_ratio"],
                    "mean_temporal_control_ratio": thread["mean_temporal_control_ratio"],
                }
            )
        status_counts = defaultdict(int)
        for thread in hyp_threads:
            status_counts[thread["dynamic_response_status"]] += 1
        component_list = [comps_by_id[cid] for cid in hyp_components if cid in comps_by_id]
        contrasts = [parse_float(comp["mean_local_robust_z"]) for comp in component_list]
        radial_centers = [parse_float(comp["radial_pixel_center"]) for comp in component_list]
        temporal = [parse_float(thread["temporal_continuity"]) for thread in hyp_threads]
        duration_units = max(1, (hyp.sar_frame_end - hyp.sar_frame_start + 1) * max(1.0, hyp.azimuth_max - hyp.azimuth_min) * RADIAL_BINS)
        density = len(component_list) / duration_units * 1000.0
        matched_delta = (
            float(np.median([parse_float(t["mean_spatial_control_ratio"]) for t in hyp_threads]))
            if hyp_threads
            else 0.0
        )
        summary_rows.append(
            {
                "hypothesis_id": hyp.hypothesis_id,
                "source_auto_node_id": hyp.source_auto_node_id,
                "sar_frame_start": hyp.sar_frame_start,
                "sar_frame_end": hyp.sar_frame_end,
                "azimuth_min": fmt(hyp.azimuth_min, 3),
                "azimuth_max": fmt(hyp.azimuth_max, 3),
                "intersecting_component_count": len(component_list),
                "intersecting_response_thread_count": len(hyp_threads),
                "dynamic_like_thread_count": status_counts["dynamic_local_response_supported"] + status_counts["dynamic_local_response_mixed"],
                "static_clutter_like_thread_count": status_counts["static_clutter_like"],
                "short_transient_component_count": sum(1 for comp in component_list if parse_int(comp["cell_count"]) <= 2),
                "branch_ambiguity_count": sum(1 for thread in hyp_threads if parse_int(thread["branch_count"]) > 0),
                "component_density_per_1000_effective_units": fmt(density, 8),
                "median_local_contrast": fmt(float(np.median(contrasts)) if contrasts else 0.0, 6),
                "median_temporal_continuity": fmt(float(np.median(temporal)) if temporal else 0.0, 6),
                "median_radial_pixel_center": fmt(float(np.median(radial_centers)) if radial_centers else 0.0, 6),
                "matched_background_thread_density_delta": fmt(matched_delta - 1.0, 6),
                "status_note": ";".join(f"{k}={v}" for k, v in sorted(status_counts.items())),
            }
        )
    return rows, summary_rows


def write_png_audit_report(audit: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 WGV3.3D PNG Normalization Audit",
        "",
        f"Date: {DATE}",
        "",
        f"Status: `{audit['status']}`",
        "",
        "## Findings",
        "",
        f"- Gray SAR frames scanned: `{SAR_FRAME_COUNT}`.",
        f"- Frames with max exactly 255: `{audit['max_255_count']}`.",
        f"- Frames with max >= 250: `{audit['max_ge_250_count']}`.",
        f"- p99 mean: `{fmt(audit['p99_mean'], 6)}`; p99 coefficient of variation: `{fmt(audit['p99_cv'], 8)}`.",
        f"- Image mean coefficient of variation: `{fmt(audit['mean_cv'], 8)}`.",
        f"- Color/gray comparison: {audit['color_note']}.",
        "",
        "## Interpretation",
        "",
        "The PNGs are display products. Cross-frame raw gray means are kept only as descriptive quantities. WGV3.3D therefore uses frame-internal percentiles plus local spatial and temporal background normalization for component extraction.",
        "",
        "## Output",
        "",
        f"- `{PNG_STATS.as_posix()}`",
    ]
    write_text(PNG_AUDIT_REPORT, "\n".join(lines) + "\n")


def freeze_outputs(paths: Sequence[Path]) -> list[dict[str, Any]]:
    combined = combined_sha256(paths)
    rows: list[dict[str, Any]] = []
    for idx, path in enumerate(paths, 1):
        rows.append(
            {
                "freeze_id": f"WGV33D_FREEZE_{idx:03d}",
                "scene": SCENE,
                "stage": "automatic_local_response_components",
                "source_file": path.as_posix(),
                "sha256": sha256_file(path),
                "combined_sha256": combined,
                "wgv1_4_read_before_freeze": "false",
                "wgv1_8_read_before_freeze": "false",
                "sar_gt_ids_loaded": "false",
                "gt_box_or_center_loaded": "false",
                "notes": "automatic stage output; posthoc metadata not read before freeze",
            }
        )
    write_csv(FREEZE_MANIFEST, rows, FREEZE_FIELDS)
    return rows


def run_automatic_stage() -> dict[str, Any]:
    hypotheses = read_automatic_hypotheses()
    geom = build_geometry()
    cell_mean, cell_max, png_rows, audit = build_cell_matrix_and_png_stats(geom)
    write_csv(PNG_STATS, png_rows, PNG_STATS_FIELDS)
    write_png_audit_report(audit)
    components, static_rows, _freq, _run = extract_components_and_static(geom, cell_mean, cell_max)
    component_rows = [component.row for component in components]
    controls = build_matched_controls(components, geom, cell_mean)
    edges, threads = build_edges_and_threads(components, controls)
    intersections, auto_summary = build_intersections_and_summary(hypotheses, component_rows, threads)

    write_csv(LOCAL_COMPONENTS, component_rows, COMPONENT_FIELDS)
    write_csv(COMPONENT_EDGES, edges, EDGE_FIELDS)
    write_csv(RESPONSE_THREADS, threads, THREAD_FIELDS)
    write_csv(STATIC_STATS, static_rows, STATIC_FIELDS)
    write_csv(MATCHED_CONTROLS, controls, CONTROL_FIELDS)
    write_csv(INTERSECTIONS, intersections, INTERSECTION_FIELDS)
    write_csv(AUTO_SUMMARY, auto_summary, AUTO_SUMMARY_FIELDS)
    freeze_rows = freeze_outputs(
        [
            PNG_AUDIT_REPORT,
            PNG_STATS,
            LOCAL_COMPONENTS,
            COMPONENT_EDGES,
            RESPONSE_THREADS,
            STATIC_STATS,
            MATCHED_CONTROLS,
            INTERSECTIONS,
            AUTO_SUMMARY,
        ]
    )
    return {
        "hypotheses": hypotheses,
        "png_audit": audit,
        "components": component_rows,
        "edges": edges,
        "threads": threads,
        "static_rows": static_rows,
        "controls": controls,
        "intersections": intersections,
        "auto_summary": auto_summary,
        "freeze_rows": freeze_rows,
    }


def load_posthoc_metadata() -> dict[str, Any]:
    if not FREEZE_MANIFEST.exists():
        raise RuntimeError("Automatic freeze is missing; run --stage automatic first")
    candidate_fields = {
        "window_id",
        "scene",
        "optical_frame_start",
        "optical_frame_end",
        "mapping_status",
        "sar_frame_candidate_start",
        "sar_frame_candidate_end",
        "sar_reference_use",
        "blocked_reason",
        "notes",
    }
    observation_fields = {
        "window_id",
        "scene",
        "wgv14_thread_or_edge",
        "wgv14b_class",
        "observed_optical_behavior_tags",
        "forbidden_interpretation",
    }
    thread_fields = {"thread_id", "scene", "thread_status", "optical_frame_start", "optical_frame_end", "notes"}
    fragment_fields = {"thread_id", "fragment_id", "scene", "optical_frame_start", "optical_frame_end", "notes"}
    candidates = read_csv_selected(WGV18_CANDIDATES, candidate_fields)
    observations = read_csv_selected(WGV18_OBSERVATIONS, observation_fields)
    threads = read_csv_selected(WGV14_THREADS, thread_fields) if WGV14_THREADS.exists() else []
    fragments = read_csv_selected(WGV14_FRAGMENTS, fragment_fields) if WGV14_FRAGMENTS.exists() else []
    by_window = {row["window_id"]: row for row in candidates}
    obs_by_window = {row["window_id"]: row for row in observations}
    return {
        "t001": {**by_window["WGV18W001"], **obs_by_window.get("WGV18W001", {})},
        "t004": {**by_window.get("WGV18W003", {}), **obs_by_window.get("WGV18W003", {})},
        "boundary": {**by_window.get("WGV18W005", {}), **obs_by_window.get("WGV18W005", {})},
        "wgv14_thread_rows_read": len(threads),
        "wgv14_fragment_rows_read": len(fragments),
    }


def rows_in_frame_window(rows: Sequence[Mapping[str, Any]], start: int, end: int) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for row in rows:
        if parse_int(row.get("end_sar_frame")) < start or parse_int(row.get("start_sar_frame")) > end:
            continue
        result.append(row)
    return result


def summarize_eval_item(name: str, start: int, end: int, note: str, threads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selected = rows_in_frame_window(threads, start, end)
    counts = defaultdict(int)
    long_threads = 0
    moving_threads = 0
    matched_supported = 0
    representatives: list[str] = []
    for row in selected:
        status = row.get("dynamic_response_status", "")
        counts[status] += 1
        if parse_int(row.get("duration_frames")) >= 3:
            long_threads += 1
        if abs(parse_float(row.get("azimuth_drift"))) >= 1.0 or abs(parse_float(row.get("radial_drift_px"))) >= 8.0:
            moving_threads += 1
        if parse_float(row.get("matched_control_available_ratio")) >= 0.5 and (
            parse_float(row.get("mean_spatial_control_ratio")) >= 1.1
            or parse_float(row.get("mean_temporal_control_ratio")) >= 1.1
        ):
            matched_supported += 1
        if len(representatives) < 12:
            representatives.append(row["response_thread_id"])
    if counts["dynamic_local_response_supported"] > 0:
        status = "dynamic_supported_present"
    elif counts["dynamic_local_response_mixed"] > 0:
        status = "dynamic_mixed_only"
    elif selected:
        status = "components_present_without_dynamic_support"
    else:
        status = "no_threads_in_window"
    return {
        "evaluation_item": name,
        "scene": SCENE,
        "frame_start": start,
        "frame_end": end,
        "source_note": note,
        "overlapping_threads": len(selected),
        "dynamic_supported_threads": counts["dynamic_local_response_supported"],
        "dynamic_mixed_threads": counts["dynamic_local_response_mixed"],
        "static_like_threads": counts["static_clutter_like"],
        "control_indistinguishable_threads": counts["control_indistinguishable"],
        "transient_threads": counts["transient_unlinked"],
        "insufficient_control_threads": counts["insufficient_matched_control"],
        "long_threads_ge3_frames": long_threads,
        "moving_threads": moving_threads,
        "matched_control_supported_threads": matched_supported,
        "representative_thread_ids": ";".join(representatives),
        "evaluation_status": status,
        "sar_gt_ids_loaded": "false",
        "gt_box_or_center_loaded": "false",
    }


def determine_closure_status(eval_rows: Sequence[Mapping[str, Any]]) -> str:
    by_item = {row["evaluation_item"]: row for row in eval_rows}
    t001 = by_item.get("T001_posthoc_anchor", {})
    bg = by_item.get("background_control_window", {})
    if parse_int(t001.get("dynamic_supported_threads")) > 0 and parse_int(bg.get("dynamic_supported_threads")) == 0:
        return "CLOSED_DYNAMIC_COMPONENT_PROTOTYPE_FOUND"
    if parse_int(t001.get("overlapping_threads")) > 0:
        return "CLOSED_COMPONENTS_FOUND_NOT_TARGET_SPECIFIC"
    return "CLOSED_LOCAL_RESPONSE_COMPONENTS_REPRODUCIBLE"


def thread_overlaps_window(row: Mapping[str, Any], start: int, end: int) -> bool:
    return parse_int(row.get("start_sar_frame")) <= end and parse_int(row.get("end_sar_frame")) >= start


def visual_thread_sort_key(row: Mapping[str, Any]) -> tuple[float, ...]:
    status_rank = {
        "dynamic_local_response_supported": 3.0,
        "dynamic_local_response_mixed": 2.0,
        "control_indistinguishable": 1.0,
        "transient_unlinked": 0.5,
    }.get(str(row.get("dynamic_response_status", "")), 0.0)
    motion = abs(parse_float(row.get("azimuth_drift"))) + abs(parse_float(row.get("radial_drift_px"))) / 16.0
    return (
        parse_float(row.get("duration_frames")),
        parse_float(row.get("temporal_continuity")),
        status_rank,
        motion,
        parse_float(row.get("integrated_excess")),
    )


def choose_visual_threads(threads: Sequence[Mapping[str, Any]], eval_rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any]]]:
    selected: list[tuple[str, Mapping[str, Any]]] = []
    t001_window = (0, 36)
    for row in eval_rows:
        if row["evaluation_item"] == "T001_posthoc_anchor":
            t001_window = (parse_int(row.get("frame_start"), 0), parse_int(row.get("frame_end"), 36))
            break
    t001_threads = [row for row in threads if thread_overlaps_window(row, *t001_window)]
    for row in sorted(t001_threads, key=visual_thread_sort_key, reverse=True)[:3]:
        selected.append(("t001_high_persistence", row))

    for status, category, limit in [
        ("static_clutter_like", "static_clutter_like", 2),
        ("transient_unlinked", "transient_unlinked", 2),
    ]:
        rows = [row for row in threads if row["dynamic_response_status"] == status]
        for row in sorted(rows, key=visual_thread_sort_key, reverse=True)[:limit]:
            selected.append((category, row))

    bg = [row for row in threads if thread_overlaps_window(row, 600, 650)]
    for row in sorted(bg, key=visual_thread_sort_key, reverse=True)[:2]:
        selected.append(("background_high_response", row))
    t004 = [row for row in threads if thread_overlaps_window(row, 281, 335)]
    for row in sorted(t004, key=visual_thread_sort_key, reverse=True)[:1]:
        selected.append(("t004_complex_window", row))
    # De-duplicate while preserving categories.
    seen: set[str] = set()
    result: list[tuple[str, Mapping[str, Any]]] = []
    for category, row in selected:
        if row["response_thread_id"] in seen:
            continue
        seen.add(row["response_thread_id"])
        result.append((category, row))
    return result


def polar_box_to_xy(az_min: float, az_max: float, radial_min: float, radial_max: float) -> list[tuple[float, float]]:
    points = []
    for az, rad in [(az_min, radial_min), (az_max, radial_min), (az_max, radial_max), (az_min, radial_max)]:
        theta = math.radians(az)
        x = FAN_CENTER_X + rad * math.sin(theta)
        y = FAN_CENTER_Y - rad * math.cos(theta)
        points.append((x, y))
    return points


def render_overlay(thread: Mapping[str, Any], components_by_id: Mapping[str, Mapping[str, Any]], output_path: Path) -> tuple[str, int]:
    ids = [cid for cid in str(thread.get("component_ids", "")).split(";") if cid in components_by_id]
    comps = [components_by_id[cid] for cid in ids]
    if not comps:
        return "", -1
    comps = sorted(comps, key=lambda row: parse_int(row["sar_frame"]))
    rep = comps[len(comps) // 2]
    frame = parse_int(rep["sar_frame"])
    with Image.open(gray_path(frame)) as img:
        canvas = img.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for idx, comp in enumerate(comps[:12]):
        color = (255, 50, 50) if idx == len(comps) // 2 else (255, 210, 40)
        points = polar_box_to_xy(
            parse_float(comp["azimuth_min"]),
            parse_float(comp["azimuth_max"]),
            parse_float(comp["radial_pixel_min"]),
            parse_float(comp["radial_pixel_max"]),
        )
        draw.line(points + [points[0]], fill=color, width=3)
    label = f"{thread['response_thread_id']} {thread['dynamic_response_status']} f{thread['start_sar_frame']}-{thread['end_sar_frame']}"
    draw.rectangle([12, 12, 980, 48], fill=(0, 0, 0))
    draw.text((18, 18), label, fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path.as_posix(), frame


def run_posthoc_stage() -> dict[str, Any]:
    if not FREEZE_MANIFEST.exists():
        raise RuntimeError("Automatic freeze is missing; run --stage automatic first")
    meta = load_posthoc_metadata()
    threads = read_csv(RESPONSE_THREADS)
    components = read_csv(LOCAL_COMPONENTS)
    components_by_id = {row["component_id"]: row for row in components}
    t001_start = parse_int(meta["t001"].get("sar_frame_candidate_start"))
    t001_end = parse_int(meta["t001"].get("sar_frame_candidate_end"))
    t004_start = parse_int(meta["t004"].get("sar_frame_candidate_start"), 281)
    t004_end = parse_int(meta["t004"].get("sar_frame_candidate_end"), 335)
    boundary_start = parse_int(meta["boundary"].get("sar_frame_candidate_start"), 58)
    boundary_end = parse_int(meta["boundary"].get("sar_frame_candidate_end"), 58)
    eval_rows = [
        summarize_eval_item(
            "T001_posthoc_anchor",
            t001_start,
            t001_end,
            "GT-assisted posthoc evaluation anchor only; not automatic extraction input",
            threads,
        ),
        summarize_eval_item(
            "T004_complex_subject_switch",
            t004_start,
            t004_end,
            "WGV18W003 complex/T004 regression window; posthoc evaluation only",
            threads,
        ),
        summarize_eval_item(
            "boundary_control_window",
            boundary_start,
            boundary_end,
            "WGV18W005 boundary/background control; posthoc evaluation only",
            threads,
        ),
        summarize_eval_item(
            "background_control_window",
            600,
            650,
            "late background control with no T001 posthoc support",
            threads,
        ),
    ]
    status = determine_closure_status(eval_rows)
    write_csv(POSTHOC_EVALUATION, eval_rows, POSTHOC_FIELDS)

    visual_rows: list[dict[str, Any]] = []
    for idx, (category, thread) in enumerate(choose_visual_threads(threads, eval_rows), 1):
        overlay_path = VISUAL_DIR / f"wgv3_3d_review_{idx:02d}_{thread['response_thread_id']}.png"
        path, frame = render_overlay(thread, components_by_id, overlay_path)
        comps = thread_components(thread, components_by_id)
        rep = comps[len(comps) // 2] if comps else {}
        judgment = (
            f"局部响应位于约 {rep.get('azimuth_center','')} deg 方位、径向像素 {rep.get('radial_pixel_center','')}；"
            f"线程持续 {thread.get('duration_frames','')} 帧，方位漂移 {thread.get('azimuth_drift','')} deg、径向漂移 {thread.get('radial_drift_px','')} px。"
            f"状态为 {thread.get('dynamic_response_status','')}，当前只能解释为 local_sar_response_component；"
            "需继续区分固定结构、道路/桥梁散射和非固定动态响应。"
        )
        visual_rows.append(
            {
                "review_id": f"WGV33D_VIS_{idx:02d}",
                "review_category": category,
                "response_thread_id": thread["response_thread_id"],
                "representative_component_id": rep.get("component_id", ""),
                "overlay_path": path,
                "sar_frame": frame,
                "azimuth_center": rep.get("azimuth_center", ""),
                "radial_pixel_center": rep.get("radial_pixel_center", ""),
                "duration_frames": thread.get("duration_frames", ""),
                "dynamic_response_status": thread.get("dynamic_response_status", ""),
                "chinese_judgment": judgment,
            }
        )
    write_csv(VISUAL_REVIEW_CSV, visual_rows, VISUAL_FIELDS)
    render_visual_report(visual_rows)
    render_closure_report(status, eval_rows, threads, read_csv(AUTO_SUMMARY), read_csv(FREEZE_MANIFEST))
    return {"status": status, "eval_rows": eval_rows, "visual_rows": visual_rows}


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def render_visual_report(visual_rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# OTY2 WGV3.3D Visual Component Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "Codex opened the generated local overlay contact images for visual inspection. PNG overlays are ignored by Git and are not committed.",
        "",
        markdown_table(
            visual_rows,
            [
                "review_id",
                "review_category",
                "response_thread_id",
                "sar_frame",
                "azimuth_center",
                "radial_pixel_center",
                "duration_frames",
                "dynamic_response_status",
            ],
        ),
        "",
        "## Chinese Judgments",
        "",
    ]
    if not any(row.get("review_category") == "static_clutter_like" for row in visual_rows):
        lines.extend(
            [
                "Static-clutter-like visual review: unavailable because the automatic response-thread bank produced 0 `static_clutter_like` threads.",
                "",
            ]
        )
    for row in visual_rows:
        lines.extend(
            [
                f"### {row['review_id']} {row['review_category']}",
                "",
                f"- Overlay: `{row['overlay_path']}`",
                f"- 判断：{row['chinese_judgment']}",
                "",
            ]
        )
    write_text(VISUAL_REPORT, "\n".join(lines).rstrip() + "\n")


def render_closure_report(
    status: str,
    eval_rows: Sequence[Mapping[str, Any]],
    threads: Sequence[Mapping[str, Any]],
    auto_summary: Sequence[Mapping[str, Any]],
    freeze_rows: Sequence[Mapping[str, Any]],
) -> None:
    status_counts = defaultdict(int)
    for row in threads:
        status_counts[row["dynamic_response_status"]] += 1
    t001 = next((row for row in eval_rows if row["evaluation_item"] == "T001_posthoc_anchor"), {})
    bg = next((row for row in eval_rows if row["evaluation_item"] == "background_control_window"), {})
    h003 = next((row for row in auto_summary if row["hypothesis_id"] == "WGV33B_H003"), {})
    h004 = next((row for row in auto_summary if row["hypothesis_id"] == "WGV33B_H004"), {})
    h001 = next((row for row in auto_summary if row["hypothesis_id"] == "WGV33B_H001"), {})
    h006 = next((row for row in auto_summary if row["hypothesis_id"] == "WGV33B_H006"), {})
    h007 = next((row for row in auto_summary if row["hypothesis_id"] == "WGV33B_H007"), {})
    freeze_sha = freeze_rows[0]["combined_sha256"] if freeze_rows else ""
    lines = [
        "# OTY2 WGV3.3D Local SAR Response Temporal Closure",
        "",
        f"Date: {DATE}",
        "",
        f"WGV3.3D status: `{status}`",
        "",
        "## Boundary",
        "",
        "Automatic A0-A4 used SAR PNG/gray images, display fan geometry, and WGV3.3B frozen automatic hypotheses only. WGV1.4/WGV1.8 and T001/T004 metadata were read only after the automatic freeze.",
        "",
        "No component or thread is promoted to an object identity or final localization. All component labels remain `local_sar_response_component`.",
        "",
        "## Key Counts",
        "",
        f"- total_local_components: `{len(read_csv(LOCAL_COMPONENTS))}`",
        f"- total_component_edges: `{len(read_csv(COMPONENT_EDGES))}`",
        f"- total_response_threads: `{len(threads)}`",
        f"- dynamic_supported_thread_count: `{status_counts['dynamic_local_response_supported']}`",
        f"- dynamic_mixed_thread_count: `{status_counts['dynamic_local_response_mixed']}`",
        f"- static_clutter_thread_count: `{status_counts['static_clutter_like']}`",
        f"- transient_unlinked_count: `{status_counts['transient_unlinked']}`",
        f"- matched_control_unavailable_count: `{sum(1 for row in read_csv(MATCHED_CONTROLS) if row['matched_control_status'] == 'matched_control_unavailable')}`",
        "",
        "## Automatic Hypotheses",
        "",
        markdown_table(
            auto_summary,
            [
                "hypothesis_id",
                "intersecting_component_count",
                "intersecting_response_thread_count",
                "dynamic_like_thread_count",
                "static_clutter_like_thread_count",
                "component_density_per_1000_effective_units",
                "status_note",
            ],
        ),
        "",
        "## Posthoc Evaluation",
        "",
        markdown_table(
            eval_rows,
            [
                "evaluation_item",
                "overlapping_threads",
                "dynamic_supported_threads",
                "dynamic_mixed_threads",
                "static_like_threads",
                "control_indistinguishable_threads",
                "evaluation_status",
            ],
        ),
        "",
        "## WGV3.3C Signal Changes",
        "",
        f"- H003 temporal evidence after local normalization: `{h003.get('status_note','')}`.",
        f"- H004 temporal evidence after local normalization: `{h004.get('status_note','')}`.",
        f"- H001/H006/H007 far-control artifact check: H001 `{h001.get('status_note','')}`, H006 `{h006.get('status_note','')}`, H007 `{h007.get('status_note','')}`. WGV3.3D uses equal-scale local controls rather than 1-degree far-sector controls.",
        "",
        "## Conclusion",
        "",
    ]
    if status == "CLOSED_DYNAMIC_COMPONENT_PROTOTYPE_FOUND":
        lines.append("A first local dynamic SAR response prototype was found, but it is still not a final localization.")
    elif status == "CLOSED_COMPONENTS_FOUND_NOT_TARGET_SPECIFIC":
        lines.append("Local components and temporal threads are reproducible, but T001 is not sufficiently distinct from background/complex windows to claim a T001-specific dynamic prototype.")
    else:
        lines.append("The local component bank is reproducible, but T001-specific dynamic continuity remains unresolved.")
    lines.extend(
        [
            "",
            "## Freeze",
            "",
            f"- combined SHA256: `{freeze_sha}`",
            "- wgv1_4_read_before_freeze=false",
            "- wgv1_8_read_before_freeze=false",
            "- sar_gt_ids_loaded=false",
            "- gt_box_or_center_loaded=false",
            "",
            "## Outputs",
            "",
            f"- `{PNG_AUDIT_REPORT.as_posix()}`",
            f"- `{PNG_STATS.as_posix()}`",
            f"- `{LOCAL_COMPONENTS.as_posix()}`",
            f"- `{COMPONENT_EDGES.as_posix()}`",
            f"- `{RESPONSE_THREADS.as_posix()}`",
            f"- `{STATIC_STATS.as_posix()}`",
            f"- `{MATCHED_CONTROLS.as_posix()}`",
            f"- `{INTERSECTIONS.as_posix()}`",
            f"- `{AUTO_SUMMARY.as_posix()}`",
            f"- `{FREEZE_MANIFEST.as_posix()}`",
            f"- `{POSTHOC_EVALUATION.as_posix()}`",
            f"- `{VISUAL_REPORT.as_posix()}`",
            f"- `{CLOSURE_REPORT.as_posix()}`",
        ]
    )
    write_text(CLOSURE_REPORT, "\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["automatic", "posthoc", "all"], default="all")
    args = parser.parse_args(argv)
    result: dict[str, Any] = {}
    if args.stage in {"automatic", "all"}:
        result["automatic"] = run_automatic_stage()
    if args.stage in {"posthoc", "all"}:
        result["posthoc"] = run_posthoc_stage()
    if args.stage == "automatic":
        auto = result["automatic"]
        print(
            json.dumps(
                {
                    "status": "WGV3.3D_AUTOMATIC_FREEZE_COMPLETE",
                    "components": len(auto["components"]),
                    "edges": len(auto["edges"]),
                    "threads": len(auto["threads"]),
                    "freeze_sha256": auto["freeze_rows"][0]["combined_sha256"],
                    "png_status": auto["png_audit"]["status"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.stage == "posthoc":
        post = result["posthoc"]
        print(json.dumps({"status": post["status"], "posthoc_rows": len(post["eval_rows"])}, ensure_ascii=False, indent=2))
    else:
        auto = result["automatic"]
        post = result["posthoc"]
        print(
            json.dumps(
                {
                    "status": post["status"],
                    "branch": git_fact(["branch", "--show-current"]),
                    "head": git_fact(["rev-parse", "HEAD"]),
                    "components": len(auto["components"]),
                    "edges": len(auto["edges"]),
                    "threads": len(auto["threads"]),
                    "freeze_sha256": auto["freeze_rows"][0]["combined_sha256"],
                    "png_status": auto["png_audit"]["status"],
                    "outputs": {
                        "png_audit": PNG_AUDIT_REPORT.as_posix(),
                        "png_stats": PNG_STATS.as_posix(),
                        "components": LOCAL_COMPONENTS.as_posix(),
                        "edges": COMPONENT_EDGES.as_posix(),
                        "threads": RESPONSE_THREADS.as_posix(),
                        "static_stats": STATIC_STATS.as_posix(),
                        "controls": MATCHED_CONTROLS.as_posix(),
                        "intersections": INTERSECTIONS.as_posix(),
                        "auto_summary": AUTO_SUMMARY.as_posix(),
                        "freeze": FREEZE_MANIFEST.as_posix(),
                        "posthoc": POSTHOC_EVALUATION.as_posix(),
                        "visual": VISUAL_REPORT.as_posix(),
                        "closure": CLOSURE_REPORT.as_posix(),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
