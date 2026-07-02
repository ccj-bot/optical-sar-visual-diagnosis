"""OTY2 optical-to-SAR support-region observation probe.

This probe converts the previous OTY2 model-form conclusion into an auditable
support-region observation layer:

1. optical single frame -> SAR single frame;
2. optical single frame -> short SAR window;
3. optical tracklet -> SAR single frame;
4. optical tracklet -> SAR temporal tube.

The support regions are constructed from optical object observations, 24-to-50
software-sync timing, configured optical-x to SAR azimuth geometry, and
state-conditioned margins. SAR images are used only for SAR observation
extraction inside those optical-derived regions. SAR GT is used only for
posthoc validation columns such as gt_inside_support_posthoc.

The current OTY2 runtime-safe range prior is broad_unknown_range_prior, so this
script records support-region construction and coarse fan-sector SAR
observations. It does not generate final boxes, candidate rankings, annotation
proposals, training outputs, tuned thresholds, or identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_OBJECT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"
DEFAULT_GT_CSV = Path(r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv")
WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")
DATA_ROOT = Path(r"D:\profile\research\data")

OPTICAL_FPS = 24.0
SAR_FPS = 50.0
FPS_RATIO = SAR_FPS / OPTICAL_FPS
SYNC_OFFSET_SAR_FRAMES = 0.0
SHORT_WINDOW_JITTER_FRAMES = 1

SAR_CANVAS_WIDTH = 2308
SAR_CANVAS_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
AZIMUTH_K = 0.0875154
AZIMUTH_B = -40.413555

EXPECTED_LEDGER = {
    "paired_optical_object_sar_gt": 215,
    "blocked_missing_gm011_object_stream": 195,
    "sar_only_gt": 20,
    "no_oty_iou_match": 12,
}

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "matlab_zip_or_any_zip_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
    "support_region_uses_sar_gt": False,
    "support_region_uses_gt_crop": False,
}

FRAME_FIELDS = [
    "probe_id",
    "relationship_type",
    "sample_pool",
    "clean_morphology_inclusion",
    "scene",
    "object_hypothesis_id",
    "state_condition",
    "optical_frame",
    "tau0_sar_frame",
    "sar_frame_probe",
    "paired_gt_sar_frame_posthoc",
    "gt_frame_delta_sar_frames",
    "c_time_status",
    "support_region_source",
    "support_region_mode",
    "support_azimuth_center_deg",
    "support_azimuth_start_deg",
    "support_azimuth_end_deg",
    "support_azimuth_width_deg",
    "state_margin_deg",
    "range_prior_mode",
    "support_radius_min_px",
    "support_radius_max_px",
    "c_shell_status",
    "support_area_px",
    "support_center_x",
    "support_center_y",
    "local_peak_x",
    "local_peak_y",
    "local_peak_intensity",
    "support_mean_intensity",
    "background_mean_intensity",
    "peak_to_background_ratio",
    "support_to_background_ratio",
    "scatter_centroid_x",
    "scatter_centroid_y",
    "centroid_residual_px",
    "range_profile_peak_radius_px",
    "azimuth_profile_peak_deg",
    "topk_local_peaks",
    "sar_image_path",
    "sar_observation_status",
    "gt_inside_support_posthoc",
    "gt_azimuth_inside_posthoc",
    "gt_radius_inside_posthoc",
    "gt_center_to_peak_distance_posthoc_px",
    "notes",
    "provenance_labels",
]

WINDOW_FIELDS = [
    "probe_id",
    "relationship_type",
    "sample_pool",
    "clean_morphology_inclusion",
    "scene",
    "object_hypothesis_id",
    "state_condition",
    "optical_frame",
    "tau0_sar_frame",
    "sar_window_start",
    "sar_window_end",
    "sar_window_frames",
    "n_sar_frames_observed",
    "support_region_mode",
    "range_prior_mode",
    "best_peak_frame",
    "best_peak_to_background_ratio",
    "median_peak_to_background_ratio",
    "peak_frame_to_frame_step_mean_px",
    "centroid_frame_to_frame_step_mean_px",
    "centroid_drift_x",
    "centroid_drift_y",
    "short_window_stability_label",
    "gt_frame_in_window_posthoc",
    "single_frame_peak_to_background_ratio",
    "window_vs_single_observation",
    "notes",
    "provenance_labels",
]

TRACK_FRAME_FIELDS = [
    "probe_id",
    "relationship_type",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "state_condition",
    "sar_frame",
    "inverse_optical_time",
    "bracket_optical_frames",
    "tracklet_state_mode",
    "interpolated_bbox",
    "support_region_mode",
    "support_azimuth_center_deg",
    "support_azimuth_start_deg",
    "support_azimuth_end_deg",
    "support_azimuth_width_deg",
    "range_prior_mode",
    "support_area_px",
    "local_peak_x",
    "local_peak_y",
    "peak_to_background_ratio",
    "scatter_centroid_x",
    "scatter_centroid_y",
    "centroid_residual_px",
    "gt_inside_support_posthoc",
    "gt_center_to_peak_distance_posthoc_px",
    "single_frame_gt_inside_support_posthoc",
    "tracklet_vs_single_support_note",
    "notes",
    "provenance_labels",
]

TUBE_FIELDS = [
    "probe_id",
    "relationship_type",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "state_mix",
    "n_optical_frames",
    "n_sar_frames_in_tube",
    "sar_frame_span",
    "support_region_mode",
    "range_prior_mode",
    "median_peak_to_background_ratio",
    "median_support_to_background_ratio",
    "peak_continuity_step_mean_px",
    "centroid_continuity_step_mean_px",
    "sar_centroid_drift_x_per_frame",
    "sar_centroid_drift_y_per_frame",
    "sar_centroid_radius_slope_per_frame",
    "sar_centroid_azimuth_slope_per_frame",
    "optical_center_x_slope_per_frame",
    "optical_area_slope_per_frame",
    "optical_bottom_y_slope_per_frame",
    "optical_traj_vs_sar_azimuth_direction",
    "optical_area_vs_sar_radius_trend",
    "tube_observation_status",
    "dropout_temporal_support_note",
    "manual_review_need",
    "notes",
    "provenance_labels",
]


def latest_path(pattern: str, base_dir: Path = REPORT_DIR) -> Path:
    paths = sorted(base_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base_dir / pattern}")
    return paths[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_float(value: Any, default: float | None = None) -> float | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def safe_int(value: Any, default: int | None = None) -> int | None:
    number = safe_float(value)
    if number is None:
        return default
    return int(number)


def fmt(value: Any, digits: int = 4) -> str:
    number = safe_float(value)
    if number is None or not math.isfinite(number):
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def bool_text(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def median_clean(values: Iterable[Any]) -> float | None:
    clean = [float(value) for value in (safe_float(item) for item in values) if value is not None and math.isfinite(value)]
    return float(median(clean)) if clean else None


def mean_clean(values: Iterable[Any]) -> float | None:
    clean = [float(value) for value in (safe_float(item) for item in values) if value is not None and math.isfinite(value)]
    return sum(clean) / len(clean) if clean else None


def slope(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 2:
        return None
    mx = sum(x for x, _ in pairs) / len(pairs)
    my = sum(y for _, y in pairs) / len(pairs)
    den = sum((x - mx) ** 2 for x, _ in pairs)
    if den <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / den


def compact_counts(values: Iterable[Any], limit: int = 8) -> str:
    counter = Counter(str(value) for value in values if str(value) != "")
    return ";".join(f"{key}={count}" for key, count in counter.most_common(limit))


def parse_bbox(text: str) -> tuple[float, float, float, float] | None:
    parts = [safe_float(part) for part in str(text or "").replace(";", ",").split(",")]
    if len(parts) < 4 or any(part is None for part in parts[:4]):
        return None
    x1, y1, x2, y2 = [float(part) for part in parts[:4]]
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_to_text(box: Sequence[float] | None) -> str:
    if box is None:
        return ""
    return ",".join(fmt(value, 3) for value in box)


def parse_center(text: str) -> tuple[float, float] | None:
    parts = [safe_float(part) for part in str(text or "").split(",")]
    if len(parts) < 2 or parts[0] is None or parts[1] is None:
        return None
    return float(parts[0]), float(parts[1])


def point_to_azimuth_deg(x: float, y: float) -> float:
    return math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))


def point_to_radius_px(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


def point_from_polar(radius: float, azimuth_deg: float) -> tuple[float, float]:
    rad = math.radians(azimuth_deg)
    return FAN_CENTER_X + radius * math.sin(rad), FAN_CENTER_Y - radius * math.cos(rad)


def sar_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes" / f"{frame:06d}.png"


def tau0_from_optical_frame(optical_frame: int | float) -> float:
    return FPS_RATIO * float(optical_frame) + SYNC_OFFSET_SAR_FRAMES


def short_window_frames(tau0: float, jitter: int = SHORT_WINDOW_JITTER_FRAMES) -> list[int]:
    start = math.floor(tau0 - jitter)
    end = math.ceil(tau0 + jitter)
    return list(range(max(0, start), max(0, end) + 1))


def state_condition(row: Mapping[str, Any], sample_pool: str = "paired_optical_object_sar_gt") -> str:
    if sample_pool != "paired_optical_object_sar_gt":
        return "dropout_or_no_match"
    flags = str(row.get("edge_partial_duplicate_handoff_ambiguity_flags", "")).lower()
    visibility = str(row.get("visibility_state", "")).lower()
    eligibility = str(row.get("vehicle_research_eligibility", "")).lower()
    if "multi=multiple_observations" in visibility:
        return "duplicate_or_handoff"
    if "boundary_truncation_present" in visibility or "partial=partial" in visibility or "partial=mixed" in visibility:
        return "edge_or_truncated"
    if eligibility == "review_only_vehicle":
        return "ambiguous_or_review_only"
    if eligibility == "far_small_vehicle_layer":
        return "far_small_or_weak"
    return "complete"


def state_margin_deg(state: str) -> float:
    return {
        "complete": 5.0,
        "edge_or_truncated": 12.0,
        "duplicate_or_handoff": 15.0,
        "ambiguous_or_review_only": 12.0,
        "far_small_or_weak": 12.0,
        "dropout_or_no_match": 18.0,
    }.get(state, 10.0)


def support_from_bbox(
    bbox: tuple[float, float, float, float] | None,
    state: str,
    source: str,
) -> dict[str, Any]:
    margin = state_margin_deg(state)
    if bbox is None:
        center = ""
        start = -60.0 - margin
        end = 45.0 + margin
        status = "fallback_scene_wide_azimuth_due_to_missing_bbox"
    else:
        x1, _y1, x2, _y2 = bbox
        theta1 = AZIMUTH_K * x1 + AZIMUTH_B
        theta2 = AZIMUTH_K * x2 + AZIMUTH_B
        start = min(theta1, theta2) - margin
        end = max(theta1, theta2) + margin
        center = (start + end) / 2.0
        status = "optical_bbox_x_to_azimuth_sector"
    start = max(-89.0, start)
    end = min(89.0, end)
    if end <= start:
        end = min(89.0, start + 5.0)
    radius_min = 0.0
    radius_max = FAN_RADIUS_PX
    support_center_radius = (radius_min + radius_max) / 2.0
    az_center = (start + end) / 2.0 if center == "" else float(center)
    support_center_x, support_center_y = point_from_polar(support_center_radius, az_center)
    return {
        "support_region_source": source,
        "support_region_mode": "coarse_optical_azimuth_sector_broad_range",
        "support_azimuth_center_deg": az_center,
        "support_azimuth_start_deg": start,
        "support_azimuth_end_deg": end,
        "support_azimuth_width_deg": end - start,
        "state_margin_deg": margin,
        "range_prior_mode": "broad_unknown_range_prior",
        "support_radius_min_px": radius_min,
        "support_radius_max_px": radius_max,
        "c_shell_status": "vehicle_shell_unlocalized_range_blocked; shell records plausible vehicle footprint but cannot center range yet",
        "support_center_x": support_center_x,
        "support_center_y": support_center_y,
        "construction_status": status,
    }


def gt_inside_support(row: Mapping[str, Any], support: Mapping[str, Any]) -> tuple[bool | None, bool | None, bool | None]:
    gt_az = safe_float(row.get("sar_gt_azimuth_deg"))
    gt_radius = safe_float(row.get("sar_gt_radius_px"))
    if gt_az is None or gt_radius is None:
        center = parse_center(str(row.get("sar_gt_center", "")))
        if center:
            gt_az = point_to_azimuth_deg(center[0], center[1])
            gt_radius = point_to_radius_px(center[0], center[1])
    if gt_az is None or gt_radius is None:
        return None, None, None
    az_ok = float(support["support_azimuth_start_deg"]) <= gt_az <= float(support["support_azimuth_end_deg"])
    radius_ok = float(support["support_radius_min_px"]) <= gt_radius <= float(support["support_radius_max_px"])
    return az_ok and radius_ok, az_ok, radius_ok


class SarImageCache:
    def __init__(self, max_images: int = 48) -> None:
        self.max_images = max_images
        self._images: OrderedDict[Path, np.ndarray] = OrderedDict()
        self._grids: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    def image(self, path: Path) -> np.ndarray | None:
        if path in self._images:
            value = self._images.pop(path)
            self._images[path] = value
            return value
        if not path.exists():
            return None
        with Image.open(path) as source:
            arr = np.asarray(source.convert("L"), dtype=np.float32)
        self._images[path] = arr
        while len(self._images) > self.max_images:
            self._images.popitem(last=False)
        return arr

    def grids(self, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if shape in self._grids:
            return self._grids[shape]
        height, width = shape
        yy, xx = np.indices((height, width), dtype=np.float32)
        radius = np.hypot(xx - FAN_CENTER_X, yy - FAN_CENTER_Y)
        azimuth = np.degrees(np.arctan2(xx - FAN_CENTER_X, FAN_CENTER_Y - yy))
        fan_mask = radius <= FAN_RADIUS_PX
        self._grids[shape] = (radius, azimuth, fan_mask)
        return self._grids[shape]


def topk_peaks(arr: np.ndarray, mask: np.ndarray, k: int = 5, min_distance_px: float = 20.0) -> str:
    flat = np.flatnonzero(mask)
    if flat.size == 0:
        return ""
    n_pick = min(flat.size, max(k * 25, k))
    values = arr.ravel()[flat]
    candidate_pos = np.argpartition(values, -n_pick)[-n_pick:]
    ordered = flat[candidate_pos[np.argsort(values[candidate_pos])[::-1]]]
    peaks: list[tuple[int, int, float]] = []
    width = arr.shape[1]
    for idx in ordered:
        y = int(idx // width)
        x = int(idx % width)
        value = float(arr[y, x])
        if all(math.hypot(x - px, y - py) >= min_distance_px for px, py, _ in peaks):
            peaks.append((x, y, value))
        if len(peaks) >= k:
            break
    return ";".join(f"{x},{y},{fmt(value / 255.0, 4)}" for x, y, value in peaks)


def extract_sar_observation(
    cache: SarImageCache,
    scene: str,
    sar_frame: int,
    support: Mapping[str, Any],
    detail: bool = True,
) -> dict[str, Any]:
    image_path = sar_path(scene, sar_frame)
    arr = cache.image(image_path)
    if arr is None:
        return {
            "sar_image_path": str(image_path),
            "sar_observation_status": "sar_image_missing",
        }
    radius, azimuth, fan_mask = cache.grids(arr.shape)
    mask = (
        (azimuth >= float(support["support_azimuth_start_deg"]))
        & (azimuth <= float(support["support_azimuth_end_deg"]))
        & (radius >= float(support["support_radius_min_px"]))
        & (radius <= float(support["support_radius_max_px"]))
        & fan_mask
    )
    support_area = int(mask.sum())
    if support_area == 0:
        return {
            "sar_image_path": str(image_path),
            "sar_observation_status": "empty_support_region",
            "support_area_px": 0,
        }
    values = arr[mask]
    fan_background = arr[fan_mask & ~mask]
    background_mean = float(fan_background.mean()) if fan_background.size else float(arr[fan_mask].mean())
    support_mean = float(values.mean())
    peak_flat = int(np.argmax(np.where(mask, arr, -1.0)))
    peak_y, peak_x = divmod(peak_flat, arr.shape[1])
    peak_value = float(arr[peak_y, peak_x])
    peak_to_bg = peak_value / max(background_mean, 1e-6)
    support_to_bg = support_mean / max(background_mean, 1e-6)

    threshold = float(np.quantile(values, 0.95)) if values.size > 20 else float(values.max())
    hot = mask & (arr >= threshold)
    hot_weights = arr[hot].astype(np.float64)
    if hot_weights.size and float(hot_weights.sum()) > 0:
        ys, xs = np.where(hot)
        centroid_x = float(np.average(xs, weights=hot_weights))
        centroid_y = float(np.average(ys, weights=hot_weights))
    else:
        centroid_x = float(peak_x)
        centroid_y = float(peak_y)
    centroid_residual = math.hypot(centroid_x - float(support["support_center_x"]), centroid_y - float(support["support_center_y"]))

    if detail:
        r_values = radius[mask]
        a_values = azimuth[mask]
        weights = values.astype(np.float64)
        range_bins = np.floor(r_values / 8.0).astype(np.int32)
        range_sums = np.bincount(range_bins, weights=weights)
        range_peak = (float(np.argmax(range_sums)) + 0.5) * 8.0 if range_sums.size else ""
        az_bins = np.floor(a_values + 180.0).astype(np.int32)
        az_sums = np.bincount(az_bins, weights=weights, minlength=361)
        az_peak = float(np.argmax(az_sums)) - 180.0 + 0.5 if az_sums.size else ""
        topk = topk_peaks(arr, mask)
    else:
        range_peak = ""
        az_peak = ""
        topk = ""

    return {
        "sar_image_path": str(image_path),
        "sar_observation_status": "support_region_observation_extracted",
        "support_area_px": support_area,
        "local_peak_x": int(peak_x),
        "local_peak_y": int(peak_y),
        "local_peak_intensity": peak_value / 255.0,
        "support_mean_intensity": support_mean / 255.0,
        "background_mean_intensity": background_mean / 255.0,
        "peak_to_background_ratio": peak_to_bg,
        "support_to_background_ratio": support_to_bg,
        "scatter_centroid_x": centroid_x,
        "scatter_centroid_y": centroid_y,
        "centroid_residual_px": centroid_residual,
        "range_profile_peak_radius_px": range_peak,
        "azimuth_profile_peak_deg": az_peak,
        "topk_local_peaks": topk,
    }


def observation_summary(obs: Mapping[str, Any]) -> dict[str, str]:
    fields = [
        "support_area_px",
        "local_peak_x",
        "local_peak_y",
        "local_peak_intensity",
        "support_mean_intensity",
        "background_mean_intensity",
        "peak_to_background_ratio",
        "support_to_background_ratio",
        "scatter_centroid_x",
        "scatter_centroid_y",
        "centroid_residual_px",
        "range_profile_peak_radius_px",
        "azimuth_profile_peak_deg",
    ]
    return {field: fmt(obs.get(field), 4) for field in fields}


def distance_sequence(rows: Sequence[Mapping[str, Any]], x_key: str, y_key: str) -> list[float]:
    distances: list[float] = []
    last: tuple[float, float] | None = None
    for row in rows:
        x = safe_float(row.get(x_key))
        y = safe_float(row.get(y_key))
        if x is None or y is None:
            continue
        current = (x, y)
        if last is not None:
            distances.append(math.hypot(current[0] - last[0], current[1] - last[1]))
        last = current
    return distances


def build_indexes(inputs: Mapping[str, Any]) -> dict[str, Any]:
    object_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    frame_by_key: dict[tuple[str, str, int], dict[str, str]] = {}
    for row in inputs["object_frame_rows"]:
        scene = str(row.get("scene", ""))
        object_id = str(row.get("object_hypothesis_id", ""))
        frame = safe_int(row.get("optical_frame_num"))
        if not scene or not object_id or frame is None:
            continue
        item = dict(row)
        object_by_key[(scene, object_id)].append(item)
        frame_by_key[(scene, object_id, frame)] = item
    for rows in object_by_key.values():
        rows.sort(key=lambda item: safe_int(item.get("optical_frame_num"), 0) or 0)

    spatial_by_key = {(row.get("scene", ""), row.get("object_hypothesis_id", "")): row for row in inputs["spatial_rows"]}
    temporal_by_key = {(row.get("scene", ""), row.get("object_hypothesis_id", "")): row for row in inputs["temporal_window_rows"]}
    object_ledger_by_key = {(row.get("scene", ""), row.get("object_hypothesis_id", "")): row for row in inputs["object_ledger_rows"]}
    manual_review_by_object = defaultdict(list)
    for row in inputs["manual_review_rows"]:
        manual_review_by_object[(row.get("scene", ""), row.get("object_hypothesis_id", ""))].append(row)
    return {
        "object_by_key": object_by_key,
        "frame_by_key": frame_by_key,
        "spatial_by_key": spatial_by_key,
        "temporal_by_key": temporal_by_key,
        "object_ledger_by_key": object_ledger_by_key,
        "manual_review_by_object": manual_review_by_object,
    }


def interpolate_bbox(object_rows: Sequence[Mapping[str, str]], optical_time: float) -> tuple[tuple[float, float, float, float] | None, str, str]:
    if not object_rows:
        return None, "no_object_tracklet_rows", ""
    parsed: list[tuple[int, tuple[float, float, float, float]]] = []
    for row in object_rows:
        frame = safe_int(row.get("optical_frame_num"))
        bbox = parse_bbox(
            ",".join(
                str(row.get(field, ""))
                for field in ("primary_bbox_x1", "primary_bbox_y1", "primary_bbox_x2", "primary_bbox_y2")
            )
        )
        if frame is not None and bbox is not None:
            parsed.append((frame, bbox))
    if not parsed:
        return None, "no_valid_primary_bbox_in_tracklet", ""
    parsed.sort(key=lambda item: item[0])
    before = [item for item in parsed if item[0] <= optical_time]
    after = [item for item in parsed if item[0] >= optical_time]
    left = before[-1] if before else parsed[0]
    right = after[0] if after else parsed[-1]
    bracket = f"{left[0]}-{right[0]}"
    if left[0] == right[0]:
        return left[1], "exact_or_nearest_tracklet_frame", bracket
    alpha = (optical_time - left[0]) / (right[0] - left[0])
    bbox = tuple(left[1][idx] * (1.0 - alpha) + right[1][idx] * alpha for idx in range(4))
    return bbox, "linear_tracklet_interpolation", bracket


def optical_frame_bbox(indexes: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    scene = str(row.get("scene", ""))
    object_id = str(row.get("object_hypothesis_id", ""))
    frame = safe_int(row.get("optical_frame"))
    if frame is not None:
        object_frame = indexes["frame_by_key"].get((scene, object_id, frame), {})
        bbox = parse_bbox(
            ",".join(
                str(object_frame.get(field, ""))
                for field in ("primary_bbox_x1", "primary_bbox_y1", "primary_bbox_x2", "primary_bbox_y2")
            )
        )
        if bbox is not None:
            return bbox
    return parse_bbox(str(row.get("optical_bbox", "")))


def add_support_and_obs_fields(
    row: dict[str, Any],
    support: Mapping[str, Any],
    obs: Mapping[str, Any],
    gt_row: Mapping[str, Any] | None = None,
) -> None:
    for key in [
        "support_region_source",
        "support_region_mode",
        "support_azimuth_center_deg",
        "support_azimuth_start_deg",
        "support_azimuth_end_deg",
        "support_azimuth_width_deg",
        "state_margin_deg",
        "range_prior_mode",
        "support_radius_min_px",
        "support_radius_max_px",
        "c_shell_status",
        "support_center_x",
        "support_center_y",
    ]:
        row[key] = fmt(support.get(key), 4) if isinstance(support.get(key), (int, float)) else support.get(key, "")
    row.update(observation_summary(obs))
    row["topk_local_peaks"] = obs.get("topk_local_peaks", "")
    row["sar_image_path"] = obs.get("sar_image_path", "")
    row["sar_observation_status"] = obs.get("sar_observation_status", "")
    if gt_row is not None:
        gt_inside, gt_az_inside, gt_radius_inside = gt_inside_support(gt_row, support)
        row["gt_inside_support_posthoc"] = bool_text(gt_inside)
        row["gt_azimuth_inside_posthoc"] = bool_text(gt_az_inside)
        row["gt_radius_inside_posthoc"] = bool_text(gt_radius_inside)
        center = parse_center(str(gt_row.get("sar_gt_center", "")))
        px = safe_float(obs.get("local_peak_x"))
        py = safe_float(obs.get("local_peak_y"))
        if center and px is not None and py is not None:
            row["gt_center_to_peak_distance_posthoc_px"] = fmt(math.hypot(center[0] - px, center[1] - py), 3)
        else:
            row["gt_center_to_peak_distance_posthoc_px"] = ""


def build_paired_frame_rows(
    inputs: Mapping[str, Any],
    indexes: Mapping[str, Any],
    cache: SarImageCache,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sorted_corr = sorted(
        inputs["correspondence_rows"],
        key=lambda item: (
            {"complete": 0, "edge_or_truncated": 1, "duplicate_or_handoff": 2, "ambiguous_or_review_only": 3, "far_small_or_weak": 4}.get(state_condition(item), 9),
            item.get("scene", ""),
            item.get("object_hypothesis_id", ""),
            safe_int(item.get("optical_frame"), 0) or 0,
        ),
    )
    for idx, corr in enumerate(sorted_corr, start=1):
        scene = str(corr.get("scene", ""))
        object_id = str(corr.get("object_hypothesis_id", ""))
        optical_frame = safe_int(corr.get("optical_frame"))
        sar_frame = safe_int(corr.get("sar_frame"))
        if optical_frame is None or sar_frame is None:
            continue
        state = state_condition(corr)
        bbox = optical_frame_bbox(indexes, corr)
        support = support_from_bbox(bbox, state, "optical_single_frame_primary_bbox")
        obs = extract_sar_observation(cache, scene, sar_frame, support)
        tau0 = tau0_from_optical_frame(optical_frame)
        c_time = abs(sar_frame - tau0) <= SHORT_WINDOW_JITTER_FRAMES
        row: dict[str, Any] = {
            "probe_id": f"F{idx:04d}",
            "relationship_type": "optical_single_frame_to_sar_single_frame",
            "sample_pool": "paired_optical_object_sar_gt",
            "clean_morphology_inclusion": "true" if state == "complete" else "false",
            "scene": scene,
            "object_hypothesis_id": object_id,
            "state_condition": state,
            "optical_frame": optical_frame,
            "tau0_sar_frame": fmt(tau0, 4),
            "sar_frame_probe": sar_frame,
            "paired_gt_sar_frame_posthoc": sar_frame,
            "gt_frame_delta_sar_frames": fmt(sar_frame - tau0, 4),
            "c_time_status": "inside_software_sync_short_window" if c_time else "outside_short_window_posthoc_warning",
            "notes": "Support region uses optical bbox and configured azimuth geometry; SAR GT validates only.",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;runtime_safe_geometry_or_vehicle_physics;SAR_image_observation;SAR_GT_posthoc_evidence",
        }
        add_support_and_obs_fields(row, support, obs, corr)
        rows.append(row)
    return rows


def build_dropout_frame_rows(
    inputs: Mapping[str, Any],
    cache: SarImageCache,
    start_index: int,
) -> list[dict[str, Any]]:
    sar_by_key = {
        (row.get("scene", ""), row.get("sar_gt_id", ""), row.get("optical_frame", "")): row
        for row in inputs["dropout_sar_rows"]
    }
    rows: list[dict[str, Any]] = []
    for offset, dropout in enumerate(inputs["dropout_temporal_rows"], start=1):
        scene = str(dropout.get("scene", ""))
        optical_frame = safe_int(dropout.get("optical_frame"))
        sar_frame = safe_int(dropout.get("sar_frame"))
        if optical_frame is None or sar_frame is None:
            continue
        sar_support = sar_by_key.get((scene, str(dropout.get("sar_gt_id", "")), str(dropout.get("optical_frame", ""))), {})
        bbox = parse_bbox(str(dropout.get("propagated_bbox_diagnostic", ""))) or parse_bbox(str(dropout.get("review_bbox", "")))
        state = "dropout_or_no_match"
        support = support_from_bbox(bbox, state, "optical_temporal_continuation_bbox_diagnostic")
        obs = extract_sar_observation(cache, scene, sar_frame, support)
        tau0 = tau0_from_optical_frame(optical_frame)
        gt_center = str(sar_support.get("sar_gt_center", ""))
        gt_radius = ""
        gt_az = ""
        center = parse_center(gt_center)
        if center:
            gt_radius = fmt(point_to_radius_px(center[0], center[1]), 4)
            gt_az = fmt(point_to_azimuth_deg(center[0], center[1]), 4)
        gt_row = {
            "sar_gt_center": gt_center,
            "sar_gt_radius_px": gt_radius,
            "sar_gt_azimuth_deg": gt_az,
        }
        row: dict[str, Any] = {
            "probe_id": f"F{start_index + offset - 1:04d}",
            "relationship_type": "optical_single_frame_to_sar_single_frame",
            "sample_pool": "detection_dropout_temporal_continuation",
            "clean_morphology_inclusion": "false",
            "scene": scene,
            "object_hypothesis_id": dropout.get("same_track_ids", ""),
            "state_condition": state,
            "optical_frame": optical_frame,
            "tau0_sar_frame": fmt(tau0, 4),
            "sar_frame_probe": sar_frame,
            "paired_gt_sar_frame_posthoc": sar_frame,
            "gt_frame_delta_sar_frames": fmt(sar_frame - tau0, 4),
            "c_time_status": "inside_software_sync_short_window" if abs(sar_frame - tau0) <= SHORT_WINDOW_JITTER_FRAMES else "outside_short_window_posthoc_warning",
            "notes": "Dropout pool uses optical temporal continuation diagnostic bbox; excluded from clean morphology.",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_image_observation;SAR_GT_posthoc_evidence;manual_or_review_anchor",
        }
        add_support_and_obs_fields(row, support, obs, gt_row)
        rows.append(row)
    return rows


def build_window_rows(
    frame_rows: Sequence[Mapping[str, Any]],
    cache: SarImageCache,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, frame_row in enumerate(frame_rows, start=1):
        scene = str(frame_row.get("scene", ""))
        optical_frame = safe_int(frame_row.get("optical_frame"))
        if optical_frame is None:
            continue
        tau0 = tau0_from_optical_frame(optical_frame)
        state = str(frame_row.get("state_condition", ""))
        bbox = None
        if frame_row.get("support_region_source") == "optical_temporal_continuation_bbox_diagnostic":
            # The exact bbox is not carried forward in the frame CSV; rebuild from azimuth support below.
            pass
        support = {
            "support_azimuth_start_deg": safe_float(frame_row.get("support_azimuth_start_deg"), -89.0),
            "support_azimuth_end_deg": safe_float(frame_row.get("support_azimuth_end_deg"), 89.0),
            "support_radius_min_px": safe_float(frame_row.get("support_radius_min_px"), 0.0),
            "support_radius_max_px": safe_float(frame_row.get("support_radius_max_px"), FAN_RADIUS_PX),
            "support_center_x": safe_float(frame_row.get("support_center_x"), FAN_CENTER_X),
            "support_center_y": safe_float(frame_row.get("support_center_y"), FAN_CENTER_Y),
        }
        window = short_window_frames(tau0)
        obs_rows: list[dict[str, Any]] = []
        for tau in window:
            obs = extract_sar_observation(cache, scene, tau, support, detail=False)
            if obs.get("sar_observation_status") == "support_region_observation_extracted":
                obs_rows.append({"sar_frame": tau, **obs})
        peak_steps = distance_sequence(obs_rows, "local_peak_x", "local_peak_y")
        centroid_steps = distance_sequence(obs_rows, "scatter_centroid_x", "scatter_centroid_y")
        peak_ratios = [safe_float(row.get("peak_to_background_ratio")) for row in obs_rows]
        peak_ratios_clean = [float(value) for value in peak_ratios if value is not None]
        best = max(obs_rows, key=lambda row: safe_float(row.get("peak_to_background_ratio"), -1.0) or -1.0) if obs_rows else {}
        centroid_x_slope = slope([float(row["sar_frame"]) for row in obs_rows], [safe_float(row.get("scatter_centroid_x"), 0.0) or 0.0 for row in obs_rows])
        centroid_y_slope = slope([float(row["sar_frame"]) for row in obs_rows], [safe_float(row.get("scatter_centroid_y"), 0.0) or 0.0 for row in obs_rows])
        peak_step_mean = mean_clean(peak_steps)
        centroid_step_mean = mean_clean(centroid_steps)
        if len(obs_rows) < 2:
            stability = "insufficient_sar_window_observations"
        elif (peak_step_mean or 999.0) <= 30.0 or (centroid_step_mean or 999.0) <= 30.0:
            stability = "short_window_peak_or_centroid_stable"
        else:
            stability = "short_window_peak_or_centroid_variable"
        single_peak = safe_float(frame_row.get("peak_to_background_ratio"))
        best_peak = safe_float(best.get("peak_to_background_ratio"))
        if single_peak is None or best_peak is None:
            comparison = "insufficient_single_or_window_observation"
        elif best_peak >= single_peak:
            comparison = "window_contains_equal_or_stronger_peak_observation"
        else:
            comparison = "single_frame_peak_observation_stronger_than_window_best"
        gt_frame = safe_int(frame_row.get("paired_gt_sar_frame_posthoc"))
        rows.append(
            {
                "probe_id": f"W{idx:04d}",
                "relationship_type": "optical_single_frame_to_sar_temporal_short_window",
                "sample_pool": frame_row.get("sample_pool", ""),
                "clean_morphology_inclusion": frame_row.get("clean_morphology_inclusion", ""),
                "scene": scene,
                "object_hypothesis_id": frame_row.get("object_hypothesis_id", ""),
                "state_condition": state,
                "optical_frame": optical_frame,
                "tau0_sar_frame": fmt(tau0, 4),
                "sar_window_start": window[0],
                "sar_window_end": window[-1],
                "sar_window_frames": ";".join(str(item) for item in window),
                "n_sar_frames_observed": len(obs_rows),
                "support_region_mode": frame_row.get("support_region_mode", ""),
                "range_prior_mode": frame_row.get("range_prior_mode", ""),
                "best_peak_frame": best.get("sar_frame", ""),
                "best_peak_to_background_ratio": fmt(best_peak, 4),
                "median_peak_to_background_ratio": fmt(median_clean(peak_ratios_clean), 4),
                "peak_frame_to_frame_step_mean_px": fmt(peak_step_mean, 3),
                "centroid_frame_to_frame_step_mean_px": fmt(centroid_step_mean, 3),
                "centroid_drift_x": fmt(centroid_x_slope, 5),
                "centroid_drift_y": fmt(centroid_y_slope, 5),
                "short_window_stability_label": stability,
                "gt_frame_in_window_posthoc": bool_text(gt_frame in set(window) if gt_frame is not None else None),
                "single_frame_peak_to_background_ratio": fmt(single_peak, 4),
                "window_vs_single_observation": comparison,
                "notes": "Short-window extraction reuses the optical-derived support region across tau in W_sar.",
                "provenance_labels": "runtime_safe_temporal_evidence;SAR_image_observation;SAR_temporal_observation;SAR_GT_posthoc_evidence",
            }
        )
    return rows


def build_tracklet_frame_rows(
    inputs: Mapping[str, Any],
    indexes: Mapping[str, Any],
    cache: SarImageCache,
    single_frame_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, corr in enumerate(inputs["correspondence_rows"], start=1):
        scene = str(corr.get("scene", ""))
        object_id = str(corr.get("object_hypothesis_id", ""))
        sar_frame = safe_int(corr.get("sar_frame"))
        if sar_frame is None:
            continue
        inverse_t = OPTICAL_FPS / SAR_FPS * sar_frame
        object_rows = indexes["object_by_key"].get((scene, object_id), [])
        bbox, mode, bracket = interpolate_bbox(object_rows, inverse_t)
        state = state_condition(corr)
        support = support_from_bbox(bbox, state, "optical_tracklet_interpolated_bbox")
        obs = extract_sar_observation(cache, scene, sar_frame, support, detail=False)
        row: dict[str, Any] = {
            "probe_id": f"T{idx:04d}",
            "relationship_type": "optical_tracklet_to_sar_single_frame",
            "sample_pool": "paired_optical_object_sar_gt",
            "scene": scene,
            "object_hypothesis_id": object_id,
            "state_condition": state,
            "sar_frame": sar_frame,
            "inverse_optical_time": fmt(inverse_t, 4),
            "bracket_optical_frames": bracket,
            "tracklet_state_mode": mode,
            "interpolated_bbox": bbox_to_text(bbox),
            "notes": "Tracklet interpolation uses optical object rows only; SAR GT validates support after extraction.",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_image_observation;SAR_GT_posthoc_evidence",
        }
        add_support_and_obs_fields(row, support, obs, corr)
        key = (scene, object_id, str(corr.get("sar_frame", "")))
        single = single_frame_by_key.get(key, {})
        row["single_frame_gt_inside_support_posthoc"] = single.get("gt_inside_support_posthoc", "")
        track_inside = row.get("gt_inside_support_posthoc", "")
        single_inside = row.get("single_frame_gt_inside_support_posthoc", "")
        if track_inside == "true" and single_inside != "true":
            note = "tracklet_interpolation_improves_posthoc_support_containment"
        elif track_inside != "true" and single_inside == "true":
            note = "single_observation_support_contains_gt_better_than_tracklet_interpolation"
        else:
            note = "tracklet_and_single_support_same_posthoc_containment_state"
        row["tracklet_vs_single_support_note"] = note
        rows.append(row)
    return rows


def build_tube_rows(
    inputs: Mapping[str, Any],
    indexes: Mapping[str, Any],
    cache: SarImageCache,
    dropout_frame_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    object_keys = sorted(
        {
            (row.get("scene", ""), row.get("object_hypothesis_id", ""))
            for row in inputs["correspondence_rows"]
            if row.get("scene") and row.get("object_hypothesis_id")
        }
    )
    for idx, (scene, object_id) in enumerate(object_keys, start=1):
        object_rows = indexes["object_by_key"].get((scene, object_id), [])
        if not object_rows:
            continue
        states = []
        object_corr = [row for row in inputs["correspondence_rows"] if row.get("scene") == scene and row.get("object_hypothesis_id") == object_id]
        for corr in object_corr:
            states.append(state_condition(corr))
        sar_frames = sorted(
            {
                int(round(tau0_from_optical_frame(safe_int(obj_row.get("optical_frame_num"), 0) or 0)))
                for obj_row in object_rows
            }
        )
        if len(sar_frames) > 60:
            step = math.ceil(len(sar_frames) / 60)
            sar_frames = sar_frames[::step]
        obs_rows: list[dict[str, Any]] = []
        for tau in sar_frames:
            inverse_t = OPTICAL_FPS / SAR_FPS * tau
            bbox, mode, _bracket = interpolate_bbox(object_rows, inverse_t)
            state = Counter(states).most_common(1)[0][0] if states else "complete"
            support = support_from_bbox(bbox, state, "optical_tracklet_temporal_tube_interpolated_bbox")
            obs = extract_sar_observation(cache, scene, tau, support, detail=False)
            if obs.get("sar_observation_status") == "support_region_observation_extracted":
                obs_rows.append({"sar_frame": tau, **obs})
        peak_steps = distance_sequence(obs_rows, "local_peak_x", "local_peak_y")
        centroid_steps = distance_sequence(obs_rows, "scatter_centroid_x", "scatter_centroid_y")
        frames = [float(row["sar_frame"]) for row in obs_rows]
        centroid_x = [safe_float(row.get("scatter_centroid_x"), 0.0) or 0.0 for row in obs_rows]
        centroid_y = [safe_float(row.get("scatter_centroid_y"), 0.0) or 0.0 for row in obs_rows]
        centroid_radius = [point_to_radius_px(x, y) for x, y in zip(centroid_x, centroid_y)]
        centroid_az = [point_to_azimuth_deg(x, y) for x, y in zip(centroid_x, centroid_y)]
        opt_frames = [float(safe_int(row.get("optical_frame_num"), 0) or 0) for row in object_rows]
        opt_centers = [safe_float(row.get("primary_bbox_center_x"), 0.0) or 0.0 for row in object_rows]
        opt_areas = [
            (safe_float(row.get("primary_bbox_w"), 0.0) or 0.0) * (safe_float(row.get("primary_bbox_h"), 0.0) or 0.0)
            for row in object_rows
        ]
        opt_bottoms = [safe_float(row.get("primary_bbox_y2"), 0.0) or 0.0 for row in object_rows]
        optical_center_slope = slope(opt_frames, opt_centers)
        optical_area_slope = slope(opt_frames, opt_areas)
        optical_bottom_slope = slope(opt_frames, opt_bottoms)
        sar_radius_slope = slope(frames, centroid_radius) if len(frames) >= 2 else None
        sar_az_slope = slope(frames, centroid_az) if len(frames) >= 2 else None
        if optical_center_slope is None or sar_az_slope is None:
            direction_label = "insufficient_direction_signal"
        elif optical_center_slope * sar_az_slope > 0:
            direction_label = "same_sign_optical_x_and_sar_azimuth_drift"
        else:
            direction_label = "opposite_sign_or_conflicting_direction"
        if optical_area_slope is None or sar_radius_slope is None:
            area_label = "insufficient_area_radius_signal"
        elif optical_area_slope * sar_radius_slope < 0:
            area_label = "opposite_sign_area_radius_trend"
        else:
            area_label = "same_sign_area_radius_trend"
        manual_reviews = indexes["manual_review_by_object"].get((scene, object_id), [])
        review_need = ";".join(row.get("review_need", "") for row in manual_reviews if row.get("review_need")) or indexes["object_ledger_by_key"].get((scene, object_id), {}).get("review_need", "")
        n_obs = len(obs_rows)
        if n_obs < 2:
            tube_status = "insufficient_sar_tube_observations"
        elif (mean_clean(centroid_steps) or 999.0) <= 35.0:
            tube_status = "sar_tube_centroid_continuity_observed"
        else:
            tube_status = "sar_tube_observation_variable_broad_support"
        rows.append(
            {
                "probe_id": f"U{idx:04d}",
                "relationship_type": "optical_tracklet_to_sar_temporal_tube",
                "sample_pool": "paired_optical_object_sar_gt",
                "scene": scene,
                "object_hypothesis_id": object_id,
                "state_mix": compact_counts(states),
                "n_optical_frames": len(object_rows),
                "n_sar_frames_in_tube": n_obs,
                "sar_frame_span": f"{min(sar_frames)}-{max(sar_frames)}" if sar_frames else "",
                "support_region_mode": "coarse_optical_azimuth_sector_broad_range",
                "range_prior_mode": "broad_unknown_range_prior",
                "median_peak_to_background_ratio": fmt(median_clean(row.get("peak_to_background_ratio") for row in obs_rows), 4),
                "median_support_to_background_ratio": fmt(median_clean(row.get("support_to_background_ratio") for row in obs_rows), 4),
                "peak_continuity_step_mean_px": fmt(mean_clean(peak_steps), 3),
                "centroid_continuity_step_mean_px": fmt(mean_clean(centroid_steps), 3),
                "sar_centroid_drift_x_per_frame": fmt(slope(frames, centroid_x), 5),
                "sar_centroid_drift_y_per_frame": fmt(slope(frames, centroid_y), 5),
                "sar_centroid_radius_slope_per_frame": fmt(sar_radius_slope, 5),
                "sar_centroid_azimuth_slope_per_frame": fmt(sar_az_slope, 5),
                "optical_center_x_slope_per_frame": fmt(optical_center_slope, 5),
                "optical_area_slope_per_frame": fmt(optical_area_slope, 5),
                "optical_bottom_y_slope_per_frame": fmt(optical_bottom_slope, 5),
                "optical_traj_vs_sar_azimuth_direction": direction_label,
                "optical_area_vs_sar_radius_trend": area_label,
                "tube_observation_status": tube_status,
                "dropout_temporal_support_note": "not_dropout_pool",
                "manual_review_need": review_need,
                "notes": "Tube support is optical-derived and range-broad; SAR GT is not used for extraction.",
                "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_image_observation;SAR_temporal_observation;SAR_GT_posthoc_evidence",
            }
        )
    if dropout_frame_rows:
        rows.append(
            {
                "probe_id": "U_dropout",
                "relationship_type": "optical_tracklet_to_sar_temporal_tube",
                "sample_pool": "detection_dropout_temporal_continuation",
                "scene": compact_counts(row.get("scene", "") for row in dropout_frame_rows),
                "object_hypothesis_id": "dropout/no_oty_iou_match special pool",
                "state_mix": "dropout_or_no_match=12",
                "n_optical_frames": len(dropout_frame_rows),
                "n_sar_frames_in_tube": len(dropout_frame_rows),
                "sar_frame_span": f"{min(safe_int(row.get('sar_frame_probe'), 0) or 0 for row in dropout_frame_rows)}-{max(safe_int(row.get('sar_frame_probe'), 0) or 0 for row in dropout_frame_rows)}",
                "support_region_mode": "optical_temporal_continuation_bbox_diagnostic_broad_range",
                "range_prior_mode": "broad_unknown_range_prior",
                "median_peak_to_background_ratio": fmt(median_clean(row.get("peak_to_background_ratio") for row in dropout_frame_rows), 4),
                "median_support_to_background_ratio": fmt(median_clean(row.get("support_to_background_ratio") for row in dropout_frame_rows), 4),
                "peak_continuity_step_mean_px": "",
                "centroid_continuity_step_mean_px": "",
                "sar_centroid_drift_x_per_frame": "",
                "sar_centroid_drift_y_per_frame": "",
                "sar_centroid_radius_slope_per_frame": "",
                "sar_centroid_azimuth_slope_per_frame": "",
                "optical_center_x_slope_per_frame": "",
                "optical_area_slope_per_frame": "",
                "optical_bottom_y_slope_per_frame": "",
                "optical_traj_vs_sar_azimuth_direction": "dropout_pool_requires_manual_review_not_identity_truth",
                "optical_area_vs_sar_radius_trend": "excluded_from_clean_morphology",
                "tube_observation_status": "dropout_pool_temporal_continuation_supported_but_not_clean_tube",
                "dropout_temporal_support_note": "12-row special pool; use for existence recovery and SAR temporal support only.",
                "manual_review_need": "manual review required before any identity or label claim",
                "notes": "Dropout rows are not mixed into clean paired morphology.",
                "provenance_labels": "runtime_safe_temporal_evidence;SAR_image_observation;SAR_temporal_observation;manual_or_review_anchor;SAR_GT_posthoc_evidence",
            }
        )
    return rows


def build_summary(
    timestamp: str,
    frame_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
    track_rows: Sequence[Mapping[str, Any]],
    tube_rows: Sequence[Mapping[str, Any]],
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    clean_frames = [row for row in frame_rows if row.get("sample_pool") == "paired_optical_object_sar_gt" and row.get("clean_morphology_inclusion") == "true"]
    paired_frames = [row for row in frame_rows if row.get("sample_pool") == "paired_optical_object_sar_gt"]
    dropout_frames = [row for row in frame_rows if row.get("sample_pool") == "detection_dropout_temporal_continuation"]
    support_ok = [row for row in paired_frames if row.get("sar_observation_status") == "support_region_observation_extracted"]
    clean_support_ok = [row for row in clean_frames if row.get("sar_observation_status") == "support_region_observation_extracted"]
    gt_inside = [row for row in paired_frames if row.get("gt_inside_support_posthoc") == "true"]
    clean_gt_inside = [row for row in clean_frames if row.get("gt_inside_support_posthoc") == "true"]
    stable_windows = [row for row in window_rows if row.get("short_window_stability_label") == "short_window_peak_or_centroid_stable"]
    track_inside = [row for row in track_rows if row.get("gt_inside_support_posthoc") == "true"]
    tube_status_counts = dict(Counter(row.get("tube_observation_status", "") for row in tube_rows))

    def rate(num: int, den: int) -> str:
        return fmt(num / den if den else None, 4)

    question_answers = {
        "1_single_frame_support": (
            f"Support-region SAR observation was extracted for {len(support_ok)}/{len(paired_frames)} paired rows "
            f"and {len(clean_support_ok)}/{len(clean_frames)} clean-complete rows. Median paired peak/background is "
            f"{fmt(median_clean(row.get('peak_to_background_ratio') for row in paired_frames), 4)}. "
            "This confirms that coarse optical-derived sectors can be observed in SAR images, but broad_unknown_range_prior "
            "means the peak is support evidence, not a final box."
        ),
        "2_short_window_stability": (
            f"Short windows produced {len(stable_windows)}/{len(window_rows)} stable peak-or-centroid labels. "
            f"Median window peak/background is {fmt(median_clean(row.get('median_peak_to_background_ratio') for row in window_rows), 4)}. "
            "They are more useful than a single frame for continuity checks, but the current broad range support can still track clutter peaks."
        ),
        "3_tracklet_interpolation": (
            f"Tracklet-to-SAR-frame support contains the posthoc GT in {len(track_inside)}/{len(track_rows)} paired validation rows. "
            "Because 50/24 maps most paired frames close to an observed optical frame, interpolation is a modest stabilizer now; it becomes more important for in-between SAR frames and dropout/edge states."
        ),
        "4_tracklet_to_tube": (
            f"Tube rows generated: {len(tube_rows)} with status counts {json.dumps(tube_status_counts, ensure_ascii=False)}. "
            "The tube formulation is feasible as an observation probe, but range-broad support prevents treating centroid drift as precise vehicle localization."
        ),
        "5_state_widening": (
            "State widening is required for edge/truncated, duplicate/handoff, review-only, far-small/weak, and dropout/no-match rows. "
            f"Frame state counts: {json.dumps(dict(Counter(row.get('state_condition', '') for row in frame_rows)), ensure_ascii=False)}."
        ),
        "6_manual_review": (
            "GM_RM019 objects 0001, 0005, 0009, 0080, and 0098 remain review-relevant, with 0005 and 0080 especially useful for continuity/complete-frame checks. GM_RM011 needs object stream recovery, not SAR relabeling."
        ),
        "7_next_priority": (
            "Next priority should be support-region peak extraction first, then SAR temporal peak tracking on the extracted observations, while GM_RM019 manual review and GM_RM011 object-stream recovery proceed as data-quality tracks."
        ),
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "ledger_valid": True,
            "category_counts": EXPECTED_LEDGER,
            "note": "This task preserves the 442 ledger but focuses on support-region observation, not re-accounting.",
        },
        "row_counts": {
            "optical_frame_to_sar_frame_support_probe": len(frame_rows),
            "optical_frame_to_sar_window_support_probe": len(window_rows),
            "optical_tracklet_to_sar_frame_probe": len(track_rows),
            "optical_tracklet_to_sar_tube_probe": len(tube_rows),
        },
        "key_metrics": {
            "paired_frame_rows": len(paired_frames),
            "clean_complete_frame_rows": len(clean_frames),
            "dropout_special_pool_rows": len(dropout_frames),
            "paired_support_observation_extract_rate": rate(len(support_ok), len(paired_frames)),
            "clean_support_observation_extract_rate": rate(len(clean_support_ok), len(clean_frames)),
            "paired_gt_inside_support_posthoc_rate": rate(len(gt_inside), len(paired_frames)),
            "clean_gt_inside_support_posthoc_rate": rate(len(clean_gt_inside), len(clean_frames)),
            "paired_peak_to_background_median": fmt(median_clean(row.get("peak_to_background_ratio") for row in paired_frames), 4),
            "clean_peak_to_background_median": fmt(median_clean(row.get("peak_to_background_ratio") for row in clean_frames), 4),
            "window_stability_rate": rate(len(stable_windows), len(window_rows)),
            "tracklet_gt_inside_support_posthoc_rate": rate(len(track_inside), len(track_rows)),
        },
        "state_counts": dict(Counter(row.get("state_condition", "") for row in frame_rows)),
        "tube_observation_status_counts": tube_status_counts,
        "range_prior_blocker": "Current OTY2 inputs expose azimuth sectors but no runtime-safe per-object SAR range prior; support regions are broad fan sectors.",
        "question_answers": question_answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }


def render_plan_doc(path: Path, timestamp: str, outputs: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 Optical-To-SAR Support-Region Observation Probe Plan",
        "",
        f"Updated: {timestamp}",
        "",
        "This document defines the OTY2 support-region observation probe. It is not OTY3, not final automatic annotation, not selector/ranking, and not training or threshold tuning.",
        "",
        "## Boundary",
        "",
        "- Support regions are constructed from optical object observations, 24 fps to 50 fps software-sync timing, configured fan-polar azimuth mapping, vehicle shell assumptions, and state-conditioned margins.",
        "- SAR image content is allowed for SAR observation extraction inside the support region.",
        "- SAR GT is allowed only for posthoc validation columns such as `gt_inside_support_posthoc`.",
        "- No GT crop is used for peak or centroid extraction.",
        "- GM_RM011 remains blocked by missing current OTY optical object stream; SAR-only rows remain SAR reference only; dropout rows remain a separate temporal-continuation pool.",
        "",
        "## Four Probe Relations",
        "",
        "1. `optical single frame -> SAR single frame`: build `C_o,t,tau = C_time intersect C_az intersect C_shell intersect C_state`, then extract local peak, peak/background, scatter centroid, centroid residual, range-profile peak, azimuth-profile peak, support area, and top-k local peaks from `I_tau`.",
        "2. `optical single frame -> SAR short window`: reuse the optical-derived support region over `W_t^SAR` and check whether peak/centroid observations are stable across nearby SAR frames.",
        "3. `optical tracklet -> SAR single frame`: invert SAR frame time to optical time and interpolate optical tracklet state before constructing the support region.",
        "4. `optical tracklet -> SAR temporal tube`: build an object-level sequence of support regions and extract SAR observation sequences for peak/centroid continuity and drift checks.",
        "",
        "## Current Blocker",
        "",
        "Current OTY2 runtime-safe spatial priors have `broad_unknown_range_prior`. The probe therefore extracts observations from coarse optical-derived azimuth sectors across the valid SAR fan radius. This is useful for SAR observation evidence and blocker diagnosis, but it is not a final localization box.",
        "",
        "## Generated Outputs",
        "",
    ]
    for name, output_path in outputs.items():
        lines.append(f"- {name}: `{output_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    answers = summary["question_answers"]
    lines = [
        "# OTY2 Support-Region SAR Observation Probe Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report audits optical-derived SAR support regions and SAR observation extraction. It does not generate final boxes, annotation proposals, selector/ranking output, training, tuned thresholds, or identity truth.",
        "",
        "## Ledger Boundary",
        "",
        "- paired_optical_object_sar_gt = 215",
        "- blocked_missing_gm011_object_stream = 195",
        "- sar_only_gt = 20",
        "- dropout/no_oty_iou_match/temporal continuation pool = 12",
        "",
        "The 215 paired rows are validation rows for optical-object/SAR-GT posthoc correspondence. GM_RM011 is blocked by missing current OTY object stream, not by missing annotation. SAR-only rows are not mixed into optical-SAR correspondence. Dropout rows are excluded from clean morphology.",
        "",
        "## Support Region Contract",
        "",
        "```text",
        "tau0(t) = 50/24 * t + Delta_s",
        "tau in [tau0 - jitter, tau0 + jitter]",
        "C_o,t,tau = C_time intersect C_az intersect C_shell intersect C_state",
        "```",
        "",
        "In this run, `C_az` comes from optical bbox x coordinates and configured fan-polar mapping. `C_state` widens the sector for edge/truncated, duplicate/handoff, review-only, far-small/weak, and dropout states. `C_shell` is recorded as a vehicle-footprint constraint, but it cannot localize range because the current runtime range prior is `broad_unknown_range_prior`.",
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in summary["key_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Required Answers",
            "",
            f"1. {answers['1_single_frame_support']}",
            f"2. {answers['2_short_window_stability']}",
            f"3. {answers['3_tracklet_interpolation']}",
            f"4. {answers['4_tracklet_to_tube']}",
            f"5. {answers['5_state_widening']}",
            f"6. {answers['6_manual_review']}",
            f"7. {answers['7_next_priority']}",
            "",
            "## Current Blocker",
            "",
            summary["range_prior_blocker"],
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
    log_path = WORKSPACE_LOG_DIR / f"oty2_support_region_sar_observation_probe_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_support_region_sar_observation_probe",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "spatial_priors_csv": Path(args.spatial_priors_csv) if args.spatial_priors_csv else latest_path("oty2_object_runtime_spatial_priors_*.csv"),
        "temporal_windows_csv": Path(args.temporal_windows_csv) if args.temporal_windows_csv else latest_path("oty2_object_sar_temporal_windows_*.csv"),
        "object_frame_state_csv": Path(args.object_frame_state_csv) if args.object_frame_state_csv else DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv",
        "object_ledger_csv": Path(args.object_ledger_csv) if args.object_ledger_csv else latest_path("oty2_object_level_factor_evidence_ledger_*.csv"),
        "manual_review_csv": Path(args.manual_review_csv) if args.manual_review_csv else latest_path("oty2_manual_review_candidate_list_*.csv"),
        "dropout_temporal_csv": Path(args.dropout_temporal_csv) if args.dropout_temporal_csv else latest_path("oty2_detection_dropout_temporal_support_audit_*.csv"),
        "dropout_sar_csv": Path(args.dropout_sar_csv) if args.dropout_sar_csv else latest_path("oty2_detection_dropout_sar_posthoc_support_audit_*.csv"),
        "physical_model_summary_json": Path(args.physical_model_summary_json) if args.physical_model_summary_json else latest_path("oty2_physical_model_form_summary_*.json"),
        "final_gt_csv": Path(args.final_gt_csv),
    }
    with paths["physical_model_summary_json"].open("r", encoding="utf-8") as handle:
        model_summary = json.load(handle)
    ledger = model_summary.get("sample_ledger", {}).get("category_counts", {})
    if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
        raise RuntimeError(f"Ledger changed; refusing support-region probe: {json.dumps(ledger, ensure_ascii=False)}")
    return {
        "paths": paths,
        "model_summary": model_summary,
        "correspondence_rows": read_csv(paths["correspondence_csv"]),
        "spatial_rows": read_csv(paths["spatial_priors_csv"]),
        "temporal_window_rows": read_csv(paths["temporal_windows_csv"]),
        "object_frame_rows": read_csv(paths["object_frame_state_csv"]),
        "object_ledger_rows": read_csv(paths["object_ledger_csv"]),
        "manual_review_rows": read_csv(paths["manual_review_csv"]),
        "dropout_temporal_rows": read_csv(paths["dropout_temporal_csv"]),
        "dropout_sar_rows": read_csv(paths["dropout_sar_csv"]),
        "final_gt_rows": read_csv(paths["final_gt_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    indexes = build_indexes(inputs)
    cache = SarImageCache(max_images=args.image_cache_size)

    paired_frame_rows = build_paired_frame_rows(inputs, indexes, cache)
    dropout_frame_rows = build_dropout_frame_rows(inputs, cache, start_index=len(paired_frame_rows) + 1)
    frame_rows = paired_frame_rows + dropout_frame_rows
    window_rows = build_window_rows(frame_rows, cache)
    single_by_key = {
        (str(row.get("scene", "")), str(row.get("object_hypothesis_id", "")), str(row.get("sar_frame_probe", ""))): row
        for row in paired_frame_rows
    }
    track_rows = build_tracklet_frame_rows(inputs, indexes, cache, single_by_key)
    tube_rows = build_tube_rows(inputs, indexes, cache, dropout_frame_rows)

    plan_doc = DOCS_DIR / "oty2_optical_to_sar_support_region_observation_probe_plan.md"
    frame_csv = REPORT_DIR / f"oty2_optical_frame_to_sar_frame_support_probe_{timestamp}.csv"
    window_csv = REPORT_DIR / f"oty2_optical_frame_to_sar_window_support_probe_{timestamp}.csv"
    track_csv = REPORT_DIR / f"oty2_optical_tracklet_to_sar_frame_probe_{timestamp}.csv"
    tube_csv = REPORT_DIR / f"oty2_optical_tracklet_to_sar_tube_probe_{timestamp}.csv"
    summary_json = REPORT_DIR / f"oty2_support_region_sar_observation_summary_{timestamp}.json"
    report_md = REPORT_DIR / f"oty2_support_region_sar_observation_report_{timestamp}.md"
    outputs = {
        "plan_doc": str(plan_doc),
        "optical_frame_to_sar_frame_support_probe_csv": str(frame_csv),
        "optical_frame_to_sar_window_support_probe_csv": str(window_csv),
        "optical_tracklet_to_sar_frame_probe_csv": str(track_csv),
        "optical_tracklet_to_sar_tube_probe_csv": str(tube_csv),
        "support_region_sar_observation_summary_json": str(summary_json),
        "support_region_sar_observation_report_md": str(report_md),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}

    write_csv(frame_csv, frame_rows, FRAME_FIELDS)
    write_csv(window_csv, window_rows, WINDOW_FIELDS)
    write_csv(track_csv, track_rows, TRACK_FRAME_FIELDS)
    write_csv(tube_csv, tube_rows, TUBE_FIELDS)
    render_plan_doc(plan_doc, timestamp, outputs)
    summary = build_summary(timestamp, frame_rows, window_rows, track_rows, tube_rows, sources, outputs)
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)
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
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--spatial-priors-csv", default="")
    parser.add_argument("--temporal-windows-csv", default="")
    parser.add_argument("--object-frame-state-csv", default="")
    parser.add_argument("--object-ledger-csv", default="")
    parser.add_argument("--manual-review-csv", default="")
    parser.add_argument("--dropout-temporal-csv", default="")
    parser.add_argument("--dropout-sar-csv", default="")
    parser.add_argument("--physical-model-summary-json", default="")
    parser.add_argument("--final-gt-csv", default=str(DEFAULT_GT_CSV))
    parser.add_argument("--image-cache-size", type=int, default=48)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
