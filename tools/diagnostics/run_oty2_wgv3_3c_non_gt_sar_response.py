"""Run WGV3.3C non-GT SAR response extraction inside automatic feasible fields.

Automatic stage:
    Reads only the WGV3.3B automatic freeze, SAR-gray images, and display fan
    geometry. It builds the effective SAR support domain, matched background
    controls, temporal controls, response time-series, and a deterministic
    freeze manifest.

Posthoc evaluation stage:
    Runs only after the automatic response freeze exists. It reads WGV1.4/WGV1.8
    T001 posthoc metadata for evaluation only. It does not load sar_gt_ids, GT
    boxes, GT centers, or final localization artifacts.

The script reports response observations, not final vehicle location, ranking,
selection, thresholds, or annotation changes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path(r"D:\profile\research\data")

DATE = "20260710"
SCENE = "GM_RM011"

SOFTWARE_SYNC_JITTER_MS = 20
OFFSET_STRESS_BAND_SAR_FRAMES = 12
SAR_FPS = 50.0
OFFSET_STRESS_BAND_MS = int(round(OFFSET_STRESS_BAND_SAR_FRAMES / SAR_FPS * 1000))
SAR_FRAME_MIN = 0
SAR_FRAME_MAX = 765

SAR_CANVAS_WIDTH = 2308
SAR_CANVAS_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7

WGV33B_FREEZE = SAMPLES_DIR / "oty2_wgv3_3b_automatic_hypothesis_freeze_20260710.csv"

SUPPORT_SUMMARY = SAMPLES_DIR / "oty2_wgv3_3c_sar_support_domain_summary_20260710.csv"
SUPPORT_FRAME_SUMMARY = SAMPLES_DIR / "oty2_wgv3_3c_support_mask_frame_summary_20260710.csv"
FRAME_AZIMUTH_SUPPORT = SAMPLES_DIR / "oty2_wgv3_3c_frame_azimuth_support_20260710.csv"
VALID_AZIMUTH_BINS = SAMPLES_DIR / "oty2_wgv3_3c_valid_azimuth_bins_20260710.csv"
VALID_RADIAL_BINS = SAMPLES_DIR / "oty2_wgv3_3c_valid_radial_bins_20260710.csv"
RESPONSE_REGIONS = SAMPLES_DIR / "oty2_wgv3_3c_response_regions_20260710.csv"
RESPONSE_TIMESERIES = SAMPLES_DIR / "oty2_wgv3_3c_response_timeseries_20260710.csv"
RESPONSE_SUMMARY = SAMPLES_DIR / "oty2_wgv3_3c_response_summary_20260710.csv"
RESPONSE_FREEZE = SAMPLES_DIR / "oty2_wgv3_3c_response_freeze_manifest_20260710.csv"
POSTHOC_EVALUATION = SAMPLES_DIR / "oty2_wgv3_3c_posthoc_t001_evaluation_20260710.csv"
MAIN_REPORT = REPORT_DIR / "oty2_wgv3_3c_first_non_gt_sar_response_experiment_20260710.md"


SUPPORT_SUMMARY_FIELDS = [
    "scene",
    "support_sample_frame_count",
    "support_sample_frames",
    "fan_pixel_count",
    "ever_nonzero_pixel_count",
    "stable_effective_pixel_count",
    "fixed_black_pixel_count",
    "fixed_black_mask_ratio",
    "stable_nonzero_min_frames",
    "valid_azimuth_min",
    "valid_azimuth_max",
    "valid_azimuth_bins",
    "valid_radial_pixel_min",
    "valid_radial_pixel_max",
    "edge_low_coverage_azimuth_bins",
    "notes",
]

SUPPORT_FRAME_FIELDS = [
    "scene",
    "sar_frame",
    "image_path",
    "exists",
    "width",
    "height",
    "fan_nonzero_pixel_count",
    "fan_nonzero_ratio",
    "frame_valid_azimuth_min",
    "frame_valid_azimuth_max",
    "frame_valid_azimuth_bins",
    "frame_valid_radial_pixel_min",
    "frame_valid_radial_pixel_max",
    "fan_mean_intensity",
    "fan_max_intensity",
]

FRAME_AZIMUTH_FIELDS = [
    "scene",
    "sar_frame",
    "azimuth_bin_start_deg",
    "azimuth_bin_end_deg",
    "fan_pixel_count",
    "frame_nonzero_pixel_count",
    "frame_nonzero_ratio",
    "frame_mean_intensity",
    "frame_effective_bin",
]

AZIMUTH_BIN_FIELDS = [
    "scene",
    "azimuth_bin_start_deg",
    "azimuth_bin_end_deg",
    "fan_pixel_count",
    "ever_nonzero_pixel_count",
    "stable_effective_pixel_count",
    "sample_nonzero_observation_count",
    "sample_nonzero_ratio",
    "valid_effective_bin",
    "edge_low_coverage_bin",
]

RADIAL_BIN_FIELDS = [
    "scene",
    "radial_pixel",
    "fan_pixel_count",
    "ever_nonzero_pixel_count",
    "stable_effective_pixel_count",
    "sample_nonzero_observation_count",
    "sample_nonzero_ratio",
    "valid_effective_radial",
]

REGION_FIELDS = [
    "region_id",
    "scene",
    "hypothesis_id",
    "source_auto_node_id",
    "region_role",
    "control_family",
    "sar_frame_start",
    "sar_frame_end",
    "azimuth_min",
    "azimuth_max",
    "azimuth_width",
    "azimuth_selection_status",
    "target_azimuth_min",
    "target_azimuth_max",
    "valid_pixel_count",
    "radial_pixel_min",
    "radial_pixel_max",
    "valid_azimuth_bin_count",
    "frame_count",
    "time_window_source",
    "background_control_assumption",
    "posthoc_only",
]

TIMESERIES_FIELDS = [
    "region_id",
    "scene",
    "hypothesis_id",
    "region_role",
    "control_family",
    "sar_frame",
    "azimuth_min",
    "azimuth_max",
    "valid_pixel_count",
    "nonzero_pixel_count",
    "nonzero_ratio",
    "mean_intensity",
    "p95_intensity",
    "p99_intensity",
    "max_intensity",
    "top1pct_mean_intensity",
    "sum_intensity",
]

SUMMARY_FIELDS = [
    "region_id",
    "scene",
    "hypothesis_id",
    "source_auto_node_id",
    "region_role",
    "control_family",
    "sar_frame_start",
    "sar_frame_end",
    "azimuth_min",
    "azimuth_max",
    "valid_pixel_count",
    "frame_count",
    "mean_intensity",
    "median_frame_mean_intensity",
    "max_frame_mean_intensity",
    "mean_nonzero_ratio",
    "max_intensity",
    "mean_top1pct_intensity",
    "target_to_adjacent_mean_ratio",
    "target_to_far_mean_ratio",
    "target_to_temporal_mean_ratio",
    "strongest_sar_frame",
    "response_observation_status",
]

FREEZE_FIELDS = [
    "freeze_id",
    "scene",
    "stage",
    "source_file",
    "sha256",
    "combined_response_freeze_sha256",
    "wgv1_4_or_wgv1_8_read_before_freeze",
    "sar_gt_ids_loaded",
    "gt_box_or_center_loaded",
    "notes",
]

POSTHOC_FIELDS = [
    "scene",
    "hypothesis_id",
    "source_auto_node_id",
    "posthoc_thread_or_window",
    "posthoc_reference_use",
    "posthoc_sar_frame_start",
    "posthoc_sar_frame_end",
    "posthoc_sar_anchor_note",
    "auto_sar_frame_start",
    "auto_sar_frame_end",
    "time_overlap_frame_count",
    "time_overlap_ratio_vs_posthoc_anchor",
    "auto_response_mean",
    "adjacent_control_mean",
    "far_control_mean",
    "temporal_control_mean",
    "target_to_adjacent_mean_ratio",
    "target_to_far_mean_ratio",
    "target_to_temporal_mean_ratio",
    "evaluation_status",
    "sar_gt_ids_loaded",
    "gt_box_or_center_loaded",
]


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    source_auto_node_id: str
    sar_frame_start: int
    sar_frame_end: int
    azimuth_min: float
    azimuth_max: float
    permission: str


@dataclass(frozen=True)
class SupportDomain:
    sample_frames: list[int]
    fan_mask: np.ndarray
    stable_mask: np.ndarray
    azimuth_deg: np.ndarray
    radial_px: np.ndarray
    azimuth_bin: np.ndarray
    radial_bin: np.ndarray
    stable_min_frames: int
    summary: dict[str, Any]
    frame_rows: list[dict[str, Any]]
    frame_azimuth_rows: list[dict[str, Any]]
    azimuth_rows: list[dict[str, Any]]
    radial_rows: list[dict[str, Any]]
    valid_azimuth_min: float
    valid_azimuth_max: float
    valid_azimuth_bins: list[int]
    valid_radial_min: int
    valid_radial_max: int
    stable_count_by_azimuth: dict[int, int]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


def read_csv_selected(path: Path, allowed_fields: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if duplicate_header(row):
                continue
            rows.append({field: row.get(field, "") for field in allowed_fields})
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
        out = subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except Exception:
        return ""


def sar_gray_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray" / f"{frame:06d}.png"


def load_gray(frame: int) -> np.ndarray:
    path = sar_gray_path(frame)
    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.uint8)


def read_automatic_hypotheses() -> list[Hypothesis]:
    rows = read_csv(WGV33B_FREEZE)
    hyps: list[Hypothesis] = []
    for row in rows:
        if row.get("scene", "") != SCENE:
            continue
        hyp_id = row.get("hypothesis_id", "")
        if not hyp_id:
            continue
        hyps.append(
            Hypothesis(
                hypothesis_id=hyp_id,
                source_auto_node_id=row.get("source_auto_node_id", ""),
                sar_frame_start=max(SAR_FRAME_MIN, parse_int(row.get("sar_frame_start"))),
                sar_frame_end=min(SAR_FRAME_MAX, parse_int(row.get("sar_frame_end"))),
                azimuth_min=parse_float(row.get("azimuth_min")),
                azimuth_max=parse_float(row.get("azimuth_max")),
                permission=row.get("hypothesis_permission", ""),
            )
        )
    hyps.sort(key=lambda h: h.hypothesis_id)
    return hyps


def select_support_sample_frames(hypotheses: Sequence[Hypothesis]) -> list[int]:
    auto_start = min(h.sar_frame_start for h in hypotheses)
    auto_end = max(h.sar_frame_end for h in hypotheses)
    early = set(range(auto_start, min(auto_end, 50) + 1, 5))
    early.update([60, 70, 85, 100, auto_end])
    for hyp in hypotheses:
        early.update([hyp.sar_frame_start, hyp.sar_frame_end, (hyp.sar_frame_start + hyp.sar_frame_end) // 2])
    later = {150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 765}
    frames = sorted(f for f in early.union(later) if SAR_FRAME_MIN <= f <= SAR_FRAME_MAX and sar_gray_path(f).exists())
    if len(frames) < 20:
        raise RuntimeError(f"Need at least 20 SAR-gray support frames, found {len(frames)}")
    return frames


def build_geometry(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    height, width = shape
    if width != SAR_CANVAS_WIDTH or height != SAR_CANVAS_HEIGHT:
        raise RuntimeError(f"Unexpected SAR image size {width}x{height}")
    yy, xx = np.indices((height, width), dtype=np.float32)
    dx = xx - FAN_CENTER_X
    dy = FAN_CENTER_Y - yy
    radial = np.sqrt(dx * dx + dy * dy)
    azimuth = np.degrees(np.arctan2(dx, dy))
    fan = (radial <= FAN_RADIUS_PX) & (azimuth >= -90.0) & (azimuth <= 90.0)
    az_bin = np.floor(azimuth).astype(np.int16)
    radial_bin = np.floor(radial).astype(np.int16)
    return fan, azimuth, radial, az_bin, radial_bin


def build_support_domain(hypotheses: Sequence[Hypothesis]) -> SupportDomain:
    sample_frames = select_support_sample_frames(hypotheses)
    first = load_gray(sample_frames[0])
    fan_mask, azimuth_deg, radial_px, azimuth_bin, radial_bin = build_geometry(first.shape)
    fan_azimuth_offsets = (azimuth_bin[fan_mask].astype(np.int16) + 90).clip(0, 179)
    fan_count_by_azimuth = np.bincount(fan_azimuth_offsets, minlength=180)
    fan_radial_values = radial_bin[fan_mask]
    nonzero_count = np.zeros(first.shape, dtype=np.uint16)
    frame_rows: list[dict[str, Any]] = []
    frame_azimuth_rows: list[dict[str, Any]] = []
    fan_count = int(fan_mask.sum())
    for frame in sample_frames:
        image = load_gray(frame)
        fan_values = image[fan_mask]
        nz = image > 0
        nonzero_count += nz
        fan_nonzero = fan_values > 0
        nonzero_by_azimuth = np.bincount(fan_azimuth_offsets[fan_nonzero], minlength=180)
        sum_by_azimuth = np.bincount(
            fan_azimuth_offsets, weights=fan_values.astype(np.float64), minlength=180
        )
        effective_offsets = np.flatnonzero(nonzero_by_azimuth > 0)
        effective_azimuth_bins = effective_offsets - 90
        effective_radials = fan_radial_values[fan_nonzero]
        frame_valid_azimuth_min = int(effective_azimuth_bins.min()) if effective_azimuth_bins.size else ""
        frame_valid_azimuth_max = int(effective_azimuth_bins.max()) if effective_azimuth_bins.size else ""
        frame_valid_radial_min = int(effective_radials.min()) if effective_radials.size else ""
        frame_valid_radial_max = int(effective_radials.max()) if effective_radials.size else ""
        frame_rows.append(
            {
                "scene": SCENE,
                "sar_frame": frame,
                "image_path": sar_gray_path(frame).as_posix(),
                "exists": "true",
                "width": image.shape[1],
                "height": image.shape[0],
                "fan_nonzero_pixel_count": int(np.count_nonzero(fan_values)),
                "fan_nonzero_ratio": fmt(np.count_nonzero(fan_values) / max(1, fan_values.size), 6),
                "frame_valid_azimuth_min": frame_valid_azimuth_min,
                "frame_valid_azimuth_max": frame_valid_azimuth_max,
                "frame_valid_azimuth_bins": int(effective_azimuth_bins.size),
                "frame_valid_radial_pixel_min": frame_valid_radial_min,
                "frame_valid_radial_pixel_max": frame_valid_radial_max,
                "fan_mean_intensity": fmt(float(fan_values.mean()), 6),
                "fan_max_intensity": int(fan_values.max(initial=0)),
            }
        )
        for offset in range(180):
            fan_pixels = int(fan_count_by_azimuth[offset])
            if fan_pixels == 0:
                continue
            bin_start = offset - 90
            nz_pixels = int(nonzero_by_azimuth[offset])
            frame_azimuth_rows.append(
                {
                    "scene": SCENE,
                    "sar_frame": frame,
                    "azimuth_bin_start_deg": bin_start,
                    "azimuth_bin_end_deg": bin_start + 1,
                    "fan_pixel_count": fan_pixels,
                    "frame_nonzero_pixel_count": nz_pixels,
                    "frame_nonzero_ratio": fmt(nz_pixels / max(1, fan_pixels), 8),
                    "frame_mean_intensity": fmt(float(sum_by_azimuth[offset]) / max(1, fan_pixels), 8),
                    "frame_effective_bin": str(nz_pixels > 0).lower(),
                }
            )

    sample_count = len(sample_frames)
    stable_min_frames = max(2, int(math.ceil(sample_count * 0.20)))
    ever_nonzero = (nonzero_count > 0) & fan_mask
    stable_mask = (nonzero_count >= stable_min_frames) & fan_mask
    fixed_black = (nonzero_count == 0) & fan_mask

    azimuth_rows: list[dict[str, Any]] = []
    stable_by_bin: dict[int, int] = {}
    max_stable = 0
    for bin_start in range(-90, 90):
        mask = fan_mask & (azimuth_bin == bin_start)
        fan_pixels = int(mask.sum())
        if fan_pixels == 0:
            continue
        stable_pixels = int((stable_mask & mask).sum())
        max_stable = max(max_stable, stable_pixels)
        stable_by_bin[bin_start] = stable_pixels

    valid_threshold = max(10, int(math.ceil(max_stable * 0.05)))
    valid_bins = [b for b, count in stable_by_bin.items() if count >= valid_threshold]
    if not valid_bins:
        raise RuntimeError("No valid SAR azimuth support bins recovered")
    valid_min = float(min(valid_bins))
    valid_max = float(max(valid_bins))

    for bin_start in range(-90, 90):
        mask = fan_mask & (azimuth_bin == bin_start)
        fan_pixels = int(mask.sum())
        if fan_pixels == 0:
            continue
        ever_pixels = int((ever_nonzero & mask).sum())
        stable_pixels = int((stable_mask & mask).sum())
        sample_obs = int(nonzero_count[mask].sum())
        ratio = sample_obs / max(1, fan_pixels * sample_count)
        valid = stable_pixels >= valid_threshold
        edge_low = (not valid) and ever_pixels > 0
        azimuth_rows.append(
            {
                "scene": SCENE,
                "azimuth_bin_start_deg": bin_start,
                "azimuth_bin_end_deg": bin_start + 1,
                "fan_pixel_count": fan_pixels,
                "ever_nonzero_pixel_count": ever_pixels,
                "stable_effective_pixel_count": stable_pixels,
                "sample_nonzero_observation_count": sample_obs,
                "sample_nonzero_ratio": fmt(ratio, 8),
                "valid_effective_bin": str(valid).lower(),
                "edge_low_coverage_bin": str(edge_low).lower(),
            }
        )

    radial_rows: list[dict[str, Any]] = []
    valid_radials: list[int] = []
    for radial in range(0, int(math.floor(FAN_RADIUS_PX)) + 1):
        mask = fan_mask & (radial_bin == radial)
        fan_pixels = int(mask.sum())
        if fan_pixels == 0:
            continue
        ever_pixels = int((ever_nonzero & mask).sum())
        stable_pixels = int((stable_mask & mask).sum())
        sample_obs = int(nonzero_count[mask].sum())
        ratio = sample_obs / max(1, fan_pixels * sample_count)
        valid = stable_pixels > 0
        if valid:
            valid_radials.append(radial)
        radial_rows.append(
            {
                "scene": SCENE,
                "radial_pixel": radial,
                "fan_pixel_count": fan_pixels,
                "ever_nonzero_pixel_count": ever_pixels,
                "stable_effective_pixel_count": stable_pixels,
                "sample_nonzero_observation_count": sample_obs,
                "sample_nonzero_ratio": fmt(ratio, 8),
                "valid_effective_radial": str(valid).lower(),
            }
        )

    edge_bins = [str(row["azimuth_bin_start_deg"]) for row in azimuth_rows if row["edge_low_coverage_bin"] == "true"]
    summary = {
        "scene": SCENE,
        "support_sample_frame_count": sample_count,
        "support_sample_frames": ";".join(str(f) for f in sample_frames),
        "fan_pixel_count": fan_count,
        "ever_nonzero_pixel_count": int(ever_nonzero.sum()),
        "stable_effective_pixel_count": int(stable_mask.sum()),
        "fixed_black_pixel_count": int(fixed_black.sum()),
        "fixed_black_mask_ratio": fmt(float(fixed_black.sum()) / max(1, fan_count), 8),
        "stable_nonzero_min_frames": stable_min_frames,
        "valid_azimuth_min": fmt(valid_min, 3),
        "valid_azimuth_max": fmt(valid_max, 3),
        "valid_azimuth_bins": len(valid_bins),
        "valid_radial_pixel_min": min(valid_radials),
        "valid_radial_pixel_max": max(valid_radials),
        "edge_low_coverage_azimuth_bins": ";".join(edge_bins),
        "notes": "valid support is estimated from SAR-gray nonzero recurrence; radial_pixel is image radius, not meters",
    }

    return SupportDomain(
        sample_frames=sample_frames,
        fan_mask=fan_mask,
        stable_mask=stable_mask,
        azimuth_deg=azimuth_deg,
        radial_px=radial_px,
        azimuth_bin=azimuth_bin,
        radial_bin=radial_bin,
        stable_min_frames=stable_min_frames,
        summary=summary,
        frame_rows=frame_rows,
        frame_azimuth_rows=frame_azimuth_rows,
        azimuth_rows=azimuth_rows,
        radial_rows=radial_rows,
        valid_azimuth_min=valid_min,
        valid_azimuth_max=valid_max,
        valid_azimuth_bins=valid_bins,
        valid_radial_min=min(valid_radials),
        valid_radial_max=max(valid_radials),
        stable_count_by_azimuth=stable_by_bin,
    )


def interval_width(amin: float, amax: float) -> float:
    return max(0.0, amax - amin)


def overlaps(a0: float, a1: float, b0: float, b1: float, gap: float = 0.0) -> bool:
    return not (a1 + gap <= b0 or b1 + gap <= a0)


def angle_support_count(domain: SupportDomain, amin: float, amax: float) -> int:
    total = 0
    for bin_start, count in domain.stable_count_by_azimuth.items():
        if (bin_start + 1) > amin and bin_start < amax:
            total += count
    return total


def clip_interval(domain: SupportDomain, amin: float, amax: float) -> tuple[float, float, str]:
    lo = max(amin, domain.valid_azimuth_min)
    hi = min(amax, domain.valid_azimuth_max + 1.0)
    status = "inside_valid_support"
    if lo > amin or hi < amax:
        status = "clipped_to_valid_support"
    if hi <= lo:
        lo = domain.valid_azimuth_min
        hi = domain.valid_azimuth_max + 1.0
        status = "fallback_full_valid_support"
    return lo, hi, status


def select_angle_control(
    domain: SupportDomain,
    target_min: float,
    target_max: float,
    mode: str,
    avoid: Sequence[tuple[float, float]] = (),
) -> tuple[float, float, str]:
    valid_lo = domain.valid_azimuth_min
    valid_hi = domain.valid_azimuth_max + 1.0
    desired_width = max(5.0, interval_width(target_min, target_max))
    target_center = (target_min + target_max) / 2.0
    target_support = angle_support_count(domain, target_min, target_max)
    best: tuple[float, float, str, tuple[float, ...]] | None = None
    max_width = int(math.floor(min(desired_width, valid_hi - valid_lo)))
    for width in range(max_width, 4, -1):
        candidates: list[tuple[float, float, str, tuple[float, ...]]] = []
        start = int(math.floor(valid_lo))
        stop = int(math.ceil(valid_hi - width))
        for s_int in range(start, stop + 1):
            amin = float(s_int)
            amax = amin + float(width)
            if amin < valid_lo or amax > valid_hi:
                continue
            if overlaps(amin, amax, target_min, target_max, gap=2.0):
                continue
            if any(overlaps(amin, amax, x0, x1, gap=1.0) for x0, x1 in avoid):
                continue
            support = angle_support_count(domain, amin, amax)
            if support <= 0:
                continue
            center = (amin + amax) / 2.0
            width_penalty = abs(width - desired_width) / max(1.0, desired_width)
            support_penalty = abs(support - target_support) / max(1.0, target_support)
            distance = abs(center - target_center)
            if mode == "adjacent":
                score = (width_penalty, distance, support_penalty)
            else:
                score = (width_penalty, -distance, support_penalty)
            status = "width_matched" if abs(width - desired_width) <= 1 else "width_clipped_by_valid_support"
            candidates.append((amin, amax, status, score))
        if candidates:
            best = min(candidates, key=lambda item: item[3])
            break
    if best is None:
        # Last-resort one-bin support control, still inside valid support and non-overlapping if possible.
        for bin_start in domain.valid_azimuth_bins:
            amin = float(bin_start)
            amax = amin + 1.0
            if not overlaps(amin, amax, target_min, target_max, gap=0.0):
                return amin, amax, "fallback_one_degree_valid_support"
        return valid_lo, min(valid_hi, valid_lo + 1.0), "fallback_overlapping_due_no_available_nonoverlap"
    return best[0], best[1], best[2]


def select_temporal_control(hyp: Hypothesis) -> tuple[int, int, str]:
    length = hyp.sar_frame_end - hyp.sar_frame_start + 1
    if hyp.sar_frame_start - length >= SAR_FRAME_MIN:
        return hyp.sar_frame_start - length, hyp.sar_frame_start - 1, "same_azimuth_before_window"
    if hyp.sar_frame_end + length <= SAR_FRAME_MAX:
        return hyp.sar_frame_end + 1, hyp.sar_frame_end + length, "same_azimuth_after_window"
    start = max(SAR_FRAME_MIN, hyp.sar_frame_start - min(length, 60))
    end = min(SAR_FRAME_MAX, start + length - 1)
    return start, end, "same_azimuth_fallback_bounded_window"


def region_mask(domain: SupportDomain, amin: float, amax: float) -> np.ndarray:
    return domain.stable_mask & (domain.azimuth_deg >= amin) & (domain.azimuth_deg < amax)


def radial_range_for_mask(domain: SupportDomain, mask: np.ndarray) -> tuple[str, str, int]:
    count = int(mask.sum())
    if count == 0:
        return "", "", 0
    radial_values = domain.radial_bin[mask]
    return str(int(radial_values.min())), str(int(radial_values.max())), count


def valid_azimuth_bin_count(domain: SupportDomain, amin: float, amax: float) -> int:
    return sum(1 for b in domain.valid_azimuth_bins if (b + 1) > amin and b < amax)


def build_response_regions(hypotheses: Sequence[Hypothesis], domain: SupportDomain) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, hyp in enumerate(hypotheses, 1):
        target_min, target_max, target_status = clip_interval(domain, hyp.azimuth_min, hyp.azimuth_max)
        target_mask = region_mask(domain, target_min, target_max)
        rmin, rmax, valid_count = radial_range_for_mask(domain, target_mask)
        target_region_id = f"WGV33C_{hyp.hypothesis_id}_AUTO_RESPONSE"
        rows.append(
            {
                "region_id": target_region_id,
                "scene": SCENE,
                "hypothesis_id": hyp.hypothesis_id,
                "source_auto_node_id": hyp.source_auto_node_id,
                "region_role": "automatic_feasible_field_response",
                "control_family": "automatic_response",
                "sar_frame_start": hyp.sar_frame_start,
                "sar_frame_end": hyp.sar_frame_end,
                "azimuth_min": fmt(target_min, 3),
                "azimuth_max": fmt(target_max, 3),
                "azimuth_width": fmt(interval_width(target_min, target_max), 3),
                "azimuth_selection_status": target_status,
                "target_azimuth_min": fmt(target_min, 3),
                "target_azimuth_max": fmt(target_max, 3),
                "valid_pixel_count": valid_count,
                "radial_pixel_min": rmin,
                "radial_pixel_max": rmax,
                "valid_azimuth_bin_count": valid_azimuth_bin_count(domain, target_min, target_max),
                "frame_count": hyp.sar_frame_end - hyp.sar_frame_start + 1,
                "time_window_source": "WGV3.3B automatic freeze",
                "background_control_assumption": "not_applicable",
                "posthoc_only": "false",
            }
        )
        adjacent_min, adjacent_max, adjacent_status = select_angle_control(
            domain, target_min, target_max, "adjacent"
        )
        far_min, far_max, far_status = select_angle_control(
            domain, target_min, target_max, "far", avoid=[(adjacent_min, adjacent_max)]
        )
        controls = [
            (
                f"WGV33C_{hyp.hypothesis_id}_ADJACENT_AZIMUTH_CONTROL",
                "same_time_adjacent_azimuth_control",
                "matched_background_control",
                adjacent_min,
                adjacent_max,
                adjacent_status,
                hyp.sar_frame_start,
                hyp.sar_frame_end,
                "same SAR frames as automatic field",
            ),
            (
                f"WGV33C_{hyp.hypothesis_id}_FAR_AZIMUTH_CONTROL",
                "same_time_far_azimuth_control",
                "matched_background_control",
                far_min,
                far_max,
                far_status,
                hyp.sar_frame_start,
                hyp.sar_frame_end,
                "same SAR frames as automatic field",
            ),
        ]
        temporal_start, temporal_end, temporal_status = select_temporal_control(hyp)
        controls.append(
            (
                f"WGV33C_{hyp.hypothesis_id}_TEMPORAL_CONTROL",
                "same_azimuth_temporal_control",
                "temporal_background_control",
                target_min,
                target_max,
                temporal_status,
                temporal_start,
                temporal_end,
                "same azimuth, offset time window",
            )
        )
        for region_id, role, family, amin, amax, status, frame_start, frame_end, time_source in controls:
            mask = region_mask(domain, amin, amax)
            rrmin, rrmax, pixels = radial_range_for_mask(domain, mask)
            rows.append(
                {
                    "region_id": region_id,
                    "scene": SCENE,
                    "hypothesis_id": hyp.hypothesis_id,
                    "source_auto_node_id": hyp.source_auto_node_id,
                    "region_role": role,
                    "control_family": family,
                    "sar_frame_start": frame_start,
                    "sar_frame_end": frame_end,
                    "azimuth_min": fmt(amin, 3),
                    "azimuth_max": fmt(amax, 3),
                    "azimuth_width": fmt(interval_width(amin, amax), 3),
                    "azimuth_selection_status": status,
                    "target_azimuth_min": fmt(target_min, 3),
                    "target_azimuth_max": fmt(target_max, 3),
                    "valid_pixel_count": pixels,
                    "radial_pixel_min": rrmin,
                    "radial_pixel_max": rrmax,
                    "valid_azimuth_bin_count": valid_azimuth_bin_count(domain, amin, amax),
                    "frame_count": frame_end - frame_start + 1,
                    "time_window_source": time_source,
                    "background_control_assumption": "background controls are not asserted vehicle-free or target-free",
                    "posthoc_only": "false",
                }
            )
    return rows


def intensity_stats(values: np.ndarray) -> dict[str, Any]:
    count = int(values.size)
    if count == 0:
        return {
            "valid_pixel_count": 0,
            "nonzero_pixel_count": 0,
            "nonzero_ratio": "",
            "mean_intensity": "",
            "p95_intensity": "",
            "p99_intensity": "",
            "max_intensity": "",
            "top1pct_mean_intensity": "",
            "sum_intensity": 0,
        }
    hist = np.bincount(values, minlength=256).astype(np.int64)
    total = int(hist.sum())
    sum_intensity = int(np.dot(hist, np.arange(256, dtype=np.int64)))
    nonzero = total - int(hist[0])
    cdf = np.cumsum(hist)
    p95 = int(np.searchsorted(cdf, math.ceil(total * 0.95), side="left"))
    p99 = int(np.searchsorted(cdf, math.ceil(total * 0.99), side="left"))
    nonzero_bins = np.flatnonzero(hist)
    max_value = int(nonzero_bins[-1]) if nonzero_bins.size else 0
    top_n = max(1, int(math.ceil(total * 0.01)))
    remaining = top_n
    top_sum = 0
    for value in range(255, -1, -1):
        take = min(remaining, int(hist[value]))
        if take:
            top_sum += take * value
            remaining -= take
            if remaining <= 0:
                break
    return {
        "valid_pixel_count": total,
        "nonzero_pixel_count": nonzero,
        "nonzero_ratio": fmt(nonzero / max(1, total), 8),
        "mean_intensity": fmt(sum_intensity / max(1, total), 8),
        "p95_intensity": p95,
        "p99_intensity": p99,
        "max_intensity": max_value,
        "top1pct_mean_intensity": fmt(top_sum / max(1, top_n), 8),
        "sum_intensity": sum_intensity,
    }


def extract_response_timeseries(regions: Sequence[Mapping[str, Any]], domain: SupportDomain) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mask_cache: dict[str, np.ndarray] = {}
    for region in regions:
        region_id = str(region["region_id"])
        amin = parse_float(region["azimuth_min"])
        amax = parse_float(region["azimuth_max"])
        mask_cache[region_id] = region_mask(domain, amin, amax)

    for region in regions:
        region_id = str(region["region_id"])
        mask = mask_cache[region_id]
        frame_start = parse_int(region["sar_frame_start"])
        frame_end = parse_int(region["sar_frame_end"])
        for frame in range(frame_start, frame_end + 1):
            if not sar_gray_path(frame).exists():
                continue
            image = load_gray(frame)
            stats = intensity_stats(image[mask])
            rows.append(
                {
                    "region_id": region_id,
                    "scene": SCENE,
                    "hypothesis_id": region["hypothesis_id"],
                    "region_role": region["region_role"],
                    "control_family": region["control_family"],
                    "sar_frame": frame,
                    "azimuth_min": region["azimuth_min"],
                    "azimuth_max": region["azimuth_max"],
                    **stats,
                }
            )
    return rows


def summarize_timeseries(
    regions: Sequence[Mapping[str, Any]], timeseries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_region: dict[str, list[Mapping[str, Any]]] = {}
    region_by_id = {str(row["region_id"]): row for row in regions}
    for row in timeseries:
        by_region.setdefault(str(row["region_id"]), []).append(row)

    raw_rows: list[dict[str, Any]] = []
    mean_by_region: dict[str, float] = {}
    for region_id, rows in by_region.items():
        means = [parse_float(row.get("mean_intensity")) for row in rows]
        top1 = [parse_float(row.get("top1pct_mean_intensity")) for row in rows]
        nonzero = [parse_float(row.get("nonzero_ratio")) for row in rows]
        max_values = [parse_int(row.get("max_intensity")) for row in rows]
        strongest_idx = int(np.argmax(np.array(means))) if means else 0
        region = region_by_id[region_id]
        mean_value = float(np.mean(means)) if means else 0.0
        mean_by_region[region_id] = mean_value
        raw_rows.append(
            {
                "region_id": region_id,
                "scene": SCENE,
                "hypothesis_id": region["hypothesis_id"],
                "source_auto_node_id": region["source_auto_node_id"],
                "region_role": region["region_role"],
                "control_family": region["control_family"],
                "sar_frame_start": region["sar_frame_start"],
                "sar_frame_end": region["sar_frame_end"],
                "azimuth_min": region["azimuth_min"],
                "azimuth_max": region["azimuth_max"],
                "valid_pixel_count": region["valid_pixel_count"],
                "frame_count": len(rows),
                "mean_intensity": fmt(mean_value, 8),
                "median_frame_mean_intensity": fmt(float(np.median(means)) if means else 0.0, 8),
                "max_frame_mean_intensity": fmt(float(np.max(means)) if means else 0.0, 8),
                "mean_nonzero_ratio": fmt(float(np.mean(nonzero)) if nonzero else 0.0, 8),
                "max_intensity": int(max(max_values)) if max_values else 0,
                "mean_top1pct_intensity": fmt(float(np.mean(top1)) if top1 else 0.0, 8),
                "strongest_sar_frame": rows[strongest_idx]["sar_frame"] if rows else "",
            }
        )

    summary_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        hyp = row["hypothesis_id"]
        target_id = f"WGV33C_{hyp}_AUTO_RESPONSE"
        adjacent_id = f"WGV33C_{hyp}_ADJACENT_AZIMUTH_CONTROL"
        far_id = f"WGV33C_{hyp}_FAR_AZIMUTH_CONTROL"
        temporal_id = f"WGV33C_{hyp}_TEMPORAL_CONTROL"
        target_mean = mean_by_region.get(target_id, 0.0)
        adjacent_mean = mean_by_region.get(adjacent_id, 0.0)
        far_mean = mean_by_region.get(far_id, 0.0)
        temporal_mean = mean_by_region.get(temporal_id, 0.0)
        if row["region_role"] == "automatic_feasible_field_response":
            ratios = [
                target_mean / max(adjacent_mean, 1e-9),
                target_mean / max(far_mean, 1e-9),
                target_mean / max(temporal_mean, 1e-9),
            ]
            if all(r >= 1.10 for r in ratios):
                status = "response_elevated_vs_all_controls_not_a_selector"
            elif any(r >= 1.10 for r in ratios):
                status = "response_mixed_vs_controls_needs_sar_internal_followup"
            else:
                status = "response_not_elevated_vs_controls"
        else:
            status = "background_control_observation_only"
        row.update(
            {
                "target_to_adjacent_mean_ratio": fmt(target_mean / max(adjacent_mean, 1e-9), 6),
                "target_to_far_mean_ratio": fmt(target_mean / max(far_mean, 1e-9), 6),
                "target_to_temporal_mean_ratio": fmt(target_mean / max(temporal_mean, 1e-9), 6),
                "response_observation_status": status,
            }
        )
        summary_rows.append(row)
    return summary_rows


def effective_search_ratios(hypotheses: Sequence[Hypothesis], domain: SupportDomain) -> dict[str, Any]:
    valid_bins = domain.valid_azimuth_bins
    valid_bin_set = set(valid_bins)
    full_angle_bins = set(range(-89, 89))
    auto_cells_effective: set[tuple[int, int]] = set()
    auto_cells_full: set[tuple[int, int]] = set()
    for hyp in hypotheses:
        for frame in range(hyp.sar_frame_start, hyp.sar_frame_end + 1):
            for bin_start in range(math.floor(hyp.azimuth_min), math.ceil(hyp.azimuth_max)):
                if bin_start in full_angle_bins:
                    auto_cells_full.add((frame, bin_start))
                if bin_start in valid_bin_set:
                    auto_cells_effective.add((frame, bin_start))
    full_denominator = (SAR_FRAME_MAX - SAR_FRAME_MIN + 1) * len(full_angle_bins)
    effective_denominator = (SAR_FRAME_MAX - SAR_FRAME_MIN + 1) * len(valid_bins)
    return {
        "full_angle_bin_count": len(full_angle_bins),
        "effective_azimuth_bin_count": len(valid_bins),
        "auto_time_azimuth_cells_full_angle": len(auto_cells_full),
        "auto_time_azimuth_cells_effective_support": len(auto_cells_effective),
        "theoretical_full_angle_search_reduction_ratio": fmt(len(auto_cells_full) / max(1, full_denominator), 8),
        "effective_support_search_reduction_ratio": fmt(
            len(auto_cells_effective) / max(1, effective_denominator), 8
        ),
    }


def write_freeze_manifest(auto_paths: Sequence[Path]) -> list[dict[str, Any]]:
    combined = combined_sha256(auto_paths)
    rows: list[dict[str, Any]] = []
    for idx, path in enumerate(auto_paths, 1):
        rows.append(
            {
                "freeze_id": f"WGV33C_RESPONSE_FREEZE_{idx:03d}",
                "scene": SCENE,
                "stage": "automatic_response_freeze",
                "source_file": path.as_posix(),
                "sha256": sha256_file(path),
                "combined_response_freeze_sha256": combined,
                "wgv1_4_or_wgv1_8_read_before_freeze": "false",
                "sar_gt_ids_loaded": "false",
                "gt_box_or_center_loaded": "false",
                "notes": "automatic stage source; posthoc files not read before this freeze",
            }
        )
    write_csv(RESPONSE_FREEZE, rows, FREEZE_FIELDS)
    return rows


def run_automatic_stage() -> dict[str, Any]:
    hypotheses = read_automatic_hypotheses()
    if len(hypotheses) != 7:
        raise RuntimeError(f"Expected 7 WGV3.3B automatic hypotheses, found {len(hypotheses)}")
    domain = build_support_domain(hypotheses)
    regions = build_response_regions(hypotheses, domain)
    timeseries = extract_response_timeseries(regions, domain)
    summary = summarize_timeseries(regions, timeseries)
    ratios = effective_search_ratios(hypotheses, domain)

    write_csv(SUPPORT_SUMMARY, [domain.summary], SUPPORT_SUMMARY_FIELDS)
    write_csv(SUPPORT_FRAME_SUMMARY, domain.frame_rows, SUPPORT_FRAME_FIELDS)
    write_csv(FRAME_AZIMUTH_SUPPORT, domain.frame_azimuth_rows, FRAME_AZIMUTH_FIELDS)
    write_csv(VALID_AZIMUTH_BINS, domain.azimuth_rows, AZIMUTH_BIN_FIELDS)
    write_csv(VALID_RADIAL_BINS, domain.radial_rows, RADIAL_BIN_FIELDS)
    write_csv(RESPONSE_REGIONS, regions, REGION_FIELDS)
    write_csv(RESPONSE_TIMESERIES, timeseries, TIMESERIES_FIELDS)
    write_csv(RESPONSE_SUMMARY, summary, SUMMARY_FIELDS)
    freeze_rows = write_freeze_manifest(
        [
            SUPPORT_SUMMARY,
            SUPPORT_FRAME_SUMMARY,
            FRAME_AZIMUTH_SUPPORT,
            VALID_AZIMUTH_BINS,
            VALID_RADIAL_BINS,
            RESPONSE_REGIONS,
            RESPONSE_TIMESERIES,
            RESPONSE_SUMMARY,
        ]
    )

    return {
        "hypotheses": hypotheses,
        "support_summary": domain.summary,
        "regions": regions,
        "summary": summary,
        "freeze_rows": freeze_rows,
        "ratios": ratios,
    }


def load_posthoc_t001_metadata() -> dict[str, Any]:
    # These paths are intentionally scoped to the posthoc stage.
    wgv18_candidates = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_to_sar_gt_reference_candidates_20260709.csv"
    wgv18_observations = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_behavior_observation_20260709.csv"
    allowed_candidate_fields = {
        "window_id",
        "scene",
        "optical_frame_start",
        "optical_frame_end",
        "mapping_method",
        "mapping_status",
        "sar_frame_candidate_start",
        "sar_frame_candidate_end",
        "sar_reference_use",
        "blocked_reason",
        "notes",
    }
    allowed_observation_fields = {
        "window_id",
        "scene",
        "wgv14_thread_or_edge",
        "wgv14b_class",
        "observed_optical_behavior_tags",
        "primary_vehicle_description_cn",
        "forbidden_interpretation",
    }
    candidate_rows = read_csv_selected(wgv18_candidates, allowed_candidate_fields)
    observation_rows = read_csv_selected(wgv18_observations, allowed_observation_fields)
    cand = next(row for row in candidate_rows if row.get("window_id") == "WGV18W001")
    obs = next(row for row in observation_rows if row.get("window_id") == "WGV18W001")
    return {
        "window_id": cand["window_id"],
        "thread": obs.get("wgv14_thread_or_edge", ""),
        "sar_frame_start": parse_int(cand.get("sar_frame_candidate_start")),
        "sar_frame_end": parse_int(cand.get("sar_frame_candidate_end")),
        "mapping_status": cand.get("mapping_status", ""),
        "sar_reference_use": cand.get("sar_reference_use", ""),
        "behavior_tags": obs.get("observed_optical_behavior_tags", ""),
        "anchor_note": "WGV1.8 T001 SAR 0-36 is GT-assisted posthoc mechanism anchor, not automatic non-GT time mapping",
    }


def run_posthoc_evaluation_stage() -> list[dict[str, Any]]:
    if not RESPONSE_FREEZE.exists() or not RESPONSE_SUMMARY.exists():
        raise RuntimeError("Automatic response freeze is missing; run --stage automatic first")
    posthoc = load_posthoc_t001_metadata()
    summary_rows = read_csv(RESPONSE_SUMMARY)
    target_rows = [row for row in summary_rows if row.get("region_role") == "automatic_feasible_field_response"]
    by_region = {row["region_id"]: row for row in summary_rows}
    eval_rows: list[dict[str, Any]] = []
    post_start = int(posthoc["sar_frame_start"])
    post_end = int(posthoc["sar_frame_end"])
    post_count = post_end - post_start + 1
    for row in target_rows:
        hyp = row["hypothesis_id"]
        auto_start = parse_int(row.get("sar_frame_start"))
        auto_end = parse_int(row.get("sar_frame_end"))
        overlap_start = max(post_start, auto_start)
        overlap_end = min(post_end, auto_end)
        overlap = max(0, overlap_end - overlap_start + 1)
        adjacent = by_region.get(f"WGV33C_{hyp}_ADJACENT_AZIMUTH_CONTROL", {})
        far = by_region.get(f"WGV33C_{hyp}_FAR_AZIMUTH_CONTROL", {})
        temporal = by_region.get(f"WGV33C_{hyp}_TEMPORAL_CONTROL", {})
        if overlap == 0:
            status = "no_posthoc_time_overlap"
        elif row.get("response_observation_status") == "response_elevated_vs_all_controls_not_a_selector":
            status = "posthoc_time_overlap_with_elevated_auto_response"
        elif row.get("response_observation_status") == "response_mixed_vs_controls_needs_sar_internal_followup":
            status = "posthoc_time_overlap_with_mixed_auto_response"
        else:
            status = "posthoc_time_overlap_without_control_elevation"
        eval_rows.append(
            {
                "scene": SCENE,
                "hypothesis_id": hyp,
                "source_auto_node_id": row.get("source_auto_node_id", ""),
                "posthoc_thread_or_window": f"{posthoc['thread']}/{posthoc['window_id']}",
                "posthoc_reference_use": "posthoc_visual_constraint_eval_only",
                "posthoc_sar_frame_start": post_start,
                "posthoc_sar_frame_end": post_end,
                "posthoc_sar_anchor_note": posthoc["anchor_note"],
                "auto_sar_frame_start": auto_start,
                "auto_sar_frame_end": auto_end,
                "time_overlap_frame_count": overlap,
                "time_overlap_ratio_vs_posthoc_anchor": fmt(overlap / max(1, post_count), 6),
                "auto_response_mean": row.get("mean_intensity", ""),
                "adjacent_control_mean": adjacent.get("mean_intensity", ""),
                "far_control_mean": far.get("mean_intensity", ""),
                "temporal_control_mean": temporal.get("mean_intensity", ""),
                "target_to_adjacent_mean_ratio": row.get("target_to_adjacent_mean_ratio", ""),
                "target_to_far_mean_ratio": row.get("target_to_far_mean_ratio", ""),
                "target_to_temporal_mean_ratio": row.get("target_to_temporal_mean_ratio", ""),
                "evaluation_status": status,
                "sar_gt_ids_loaded": "false",
                "gt_box_or_center_loaded": "false",
            }
        )
    write_csv(POSTHOC_EVALUATION, eval_rows, POSTHOC_FIELDS)
    return eval_rows


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def render_report(auto_result: Mapping[str, Any], eval_rows: Sequence[Mapping[str, Any]]) -> None:
    support = auto_result["support_summary"]
    summary_rows = list(auto_result["summary"])
    target_rows = [row for row in summary_rows if row.get("region_role") == "automatic_feasible_field_response"]
    ratios = auto_result["ratios"]
    freeze_rows = auto_result["freeze_rows"]
    combined_hash = freeze_rows[0]["combined_response_freeze_sha256"] if freeze_rows else ""
    status_counts: dict[str, int] = {}
    for row in eval_rows:
        status = str(row.get("evaluation_status", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
    status_text = "; ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
    head = git_fact(["rev-parse", "HEAD"])
    branch = git_fact(["branch", "--show-current"])
    lines = [
        "# OTY2 WGV3.3C First Non-GT SAR Response Experiment Inside Automatic Feasible Fields",
        "",
        f"Date: {DATE}",
        "",
        "## WGV3.3B Inherited Corrections",
        "",
        f"1. `software_sync_jitter_ms = {SOFTWARE_SYNC_JITTER_MS}`.",
        f"2. `offset_stress_band = +/-{OFFSET_STRESS_BAND_SAR_FRAMES} SAR frames = +/-{OFFSET_STRESS_BAND_MS} ms`.",
        "3. The current feasible-field time uncertainty is dominated by the +/-240 ms offset stress band, not by the 20 ms software jitter.",
        "4. WGV1.8 T001 SAR `0-36` is a GT-assisted posthoc mechanism anchor, not an automatic non-GT time mapping.",
        "5. The prior `70..85 deg` control sector falls in an all-zero / fixed-black support area and is not a valid background control.",
        "6. The prior `0.088729` ratio uses a theoretical full-angle denominator; WGV3.3C supplements it with the actual effective imaging-support denominator.",
        "",
        "## Boundary",
        "",
        "Automatic response extraction used only WGV3.3B's seven frozen automatic hypotheses, SAR-gray images, and display fan geometry. It did not read WGV1.8 SAR `0-36`, `sar_gt_ids`, GT boxes, GT centers, or final localization artifacts before the response freeze.",
        "",
        "The posthoc stage was run only after the response freeze and reads T001 metadata for evaluation. It reports SAR response observations, not final boxes, target identity, ranking, or annotations.",
        "",
        "## Effective SAR Support Domain",
        "",
        markdown_table(
            [support],
            [
                "support_sample_frame_count",
                "valid_azimuth_min",
                "valid_azimuth_max",
                "valid_azimuth_bins",
                "valid_radial_pixel_min",
                "valid_radial_pixel_max",
                "fixed_black_mask_ratio",
            ],
        ),
        "",
        f"- Support sample frames: `{support['support_sample_frames']}`.",
        "- `radial_pixel` is image-domain radius from the display fan center, not meter-scale range.",
        "- A stable effective pixel is a fan pixel that is nonzero in at least 20% of sampled SAR-gray frames.",
        "- Per-frame azimuth support is preserved in the frame-azimuth CSV; the report does not collapse frame-varying support into a precise physical range.",
        "",
        "## Search-Reduction Denominators",
        "",
        markdown_table(
            [ratios],
            [
                "full_angle_bin_count",
                "effective_azimuth_bin_count",
                "auto_time_azimuth_cells_full_angle",
                "auto_time_azimuth_cells_effective_support",
                "theoretical_full_angle_search_reduction_ratio",
                "effective_support_search_reduction_ratio",
            ],
        ),
        "",
        "## Automatic Response Summary",
        "",
        markdown_table(
            target_rows,
            [
                "hypothesis_id",
                "source_auto_node_id",
                "sar_frame_start",
                "sar_frame_end",
                "azimuth_min",
                "azimuth_max",
                "mean_intensity",
                "mean_top1pct_intensity",
                "target_to_adjacent_mean_ratio",
                "target_to_far_mean_ratio",
                "target_to_temporal_mean_ratio",
                "response_observation_status",
            ],
        ),
        "",
        "## Posthoc T001 Evaluation After Freeze",
        "",
        markdown_table(
            eval_rows,
            [
                "hypothesis_id",
                "posthoc_sar_frame_start",
                "posthoc_sar_frame_end",
                "auto_sar_frame_start",
                "auto_sar_frame_end",
                "time_overlap_frame_count",
                "time_overlap_ratio_vs_posthoc_anchor",
                "evaluation_status",
            ],
        ),
        "",
        f"Evaluation status counts: `{status_text}`.",
        "",
        "## Response Freeze",
        "",
        f"- Combined automatic response freeze SHA256: `{combined_hash}`.",
        "- Freeze manifest records `wgv1_4_or_wgv1_8_read_before_freeze=false`, `sar_gt_ids_loaded=false`, and `gt_box_or_center_loaded=false`.",
        "",
        "## Outputs",
        "",
        f"- `{SUPPORT_SUMMARY.as_posix()}`",
        f"- `{SUPPORT_FRAME_SUMMARY.as_posix()}`",
        f"- `{FRAME_AZIMUTH_SUPPORT.as_posix()}`",
        f"- `{VALID_AZIMUTH_BINS.as_posix()}`",
        f"- `{VALID_RADIAL_BINS.as_posix()}`",
        f"- `{RESPONSE_REGIONS.as_posix()}`",
        f"- `{RESPONSE_TIMESERIES.as_posix()}`",
        f"- `{RESPONSE_SUMMARY.as_posix()}`",
        f"- `{RESPONSE_FREEZE.as_posix()}`",
        f"- `{POSTHOC_EVALUATION.as_posix()}`",
        f"- `{MAIN_REPORT.as_posix()}`",
        "",
        "## Git Context At Generation",
        "",
        f"- branch: `{branch}`",
        f"- generation HEAD: `{head}`",
    ]
    write_text(MAIN_REPORT, "\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["automatic", "posthoc", "all"], default="all")
    args = parser.parse_args(argv)

    auto_result: dict[str, Any] | None = None
    eval_rows: list[dict[str, Any]] = []
    if args.stage in {"automatic", "all"}:
        auto_result = run_automatic_stage()
    if args.stage in {"posthoc", "all"}:
        eval_rows = run_posthoc_evaluation_stage()
    if args.stage == "all":
        assert auto_result is not None
        render_report(auto_result, eval_rows)
        payload = {
            "status": "WGV3.3C_AUTOMATIC_RESPONSE_FROZEN_POSTHOC_EVALUATED",
            "branch": git_fact(["branch", "--show-current"]),
            "head": git_fact(["rev-parse", "HEAD"]),
            "automatic_hypotheses": len(auto_result["hypotheses"]),
            "support": auto_result["support_summary"],
            "search_ratios": auto_result["ratios"],
            "response_freeze_sha256": auto_result["freeze_rows"][0]["combined_response_freeze_sha256"],
            "posthoc_eval_rows": len(eval_rows),
            "outputs": {
                "support_summary": SUPPORT_SUMMARY.as_posix(),
                "support_frame_summary": SUPPORT_FRAME_SUMMARY.as_posix(),
                "frame_azimuth_support": FRAME_AZIMUTH_SUPPORT.as_posix(),
                "valid_azimuth_bins": VALID_AZIMUTH_BINS.as_posix(),
                "valid_radial_bins": VALID_RADIAL_BINS.as_posix(),
                "response_regions": RESPONSE_REGIONS.as_posix(),
                "response_timeseries": RESPONSE_TIMESERIES.as_posix(),
                "response_summary": RESPONSE_SUMMARY.as_posix(),
                "response_freeze": RESPONSE_FREEZE.as_posix(),
                "posthoc_evaluation": POSTHOC_EVALUATION.as_posix(),
                "report": MAIN_REPORT.as_posix(),
            },
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.stage == "automatic":
        assert auto_result is not None
        print(
            json.dumps(
                {
                    "status": "WGV3.3C_AUTOMATIC_RESPONSE_FROZEN",
                    "automatic_hypotheses": len(auto_result["hypotheses"]),
                    "response_freeze_sha256": auto_result["freeze_rows"][0]["combined_response_freeze_sha256"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps({"status": "WGV3.3C_POSTHOC_EVALUATED", "rows": len(eval_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
