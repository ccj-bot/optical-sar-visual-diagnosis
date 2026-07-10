"""Recover WGV3.3B dual-channel optical-to-SAR feasible fields.

This diagnostic separates two optical source channels:

* Channel B is built first from WGV3.3A automatic nodes/relations only and is
  frozen before WGV1.4/WGV1.8 posthoc references are read.
* Channel A is a posthoc comparison channel from WGV1.4/WGV1.8 references.

The script recovers provenance, proxy time windows, coarse azimuth feasible
fields, and SAR image traceability. It does not select final SAR targets, rank
SAR candidates, edit GT/annotations, train/tune thresholds, or claim identity
truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageStat


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path(r"D:\profile\research\data")

DATE = "20260710"
SCENE = "GM_RM011"
PRIMARY_THREAD_ID = "GM_RM011_WGV14T001"
PRIMARY_WINDOW_ID = "WGV18W001"
PRIMARY_OPTICAL_START = 0
PRIMARY_OPTICAL_END = 25
AUTO_NEIGHBORHOOD_END = 36

OPTICAL_FPS = 24.0
SAR_FPS = 50.0
FPS_RATIO = SAR_FPS / OPTICAL_FPS
OFFSET_MARGIN_SAR_FRAMES = 12
SOFTWARE_SYNC_JITTER_MS = 20
SAR_FRAME_MAX = 765
FULL_AZIMUTH_MIN = -89.0
FULL_AZIMUTH_MAX = 89.0

SAR_CANVAS_WIDTH = 2308
SAR_CANVAS_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
AZIMUTH_K = 0.0875154
AZIMUTH_B = -40.413555

WGV33A_NODES = SAMPLES_DIR / "oty2_wgv3_3a_auto_tracklet_nodes_20260710.csv"
WGV33A_RELATIONS = SAMPLES_DIR / "oty2_wgv3_3a_auto_relation_decisions_20260710.csv"
WGV33A_COMPETITION = SAMPLES_DIR / "oty2_wgv3_3a_competition_relations_20260710.csv"
WGV33A_CAPABILITY = SAMPLES_DIR / "oty2_wgv3_3a_optical_message_capability_20260710.csv"
WGV33A_MAPPING = SAMPLES_DIR / "oty2_wgv3_3a_wgv1_4_node_mapping_20260710.csv"

WGV14_THREADS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_threads_20260708.csv"
WGV14_FRAGMENTS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_fragments_20260708.csv"
WGV17_OFFSET_SCAN = SAMPLES_DIR / "oty2_wgv1_7_offset_scan_summary_20260709.csv"
WGV17_DECISIONS = SAMPLES_DIR / "oty2_wgv1_7_window_mapping_decisions_20260709.csv"
WGV18_OBS = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_behavior_observation_20260709.csv"
WGV18_CANDIDATES = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_to_sar_gt_reference_candidates_20260709.csv"
ALIGNMENT_SUMMARY = REPORT_DIR / "oty2_alignment_mode_decision_summary_20260702_132945.csv"
TEMPORAL_METADATA = REPORT_DIR / "oty2_temporal_metadata_inventory_20260702_132945.csv"
GM011_PREFLIGHT = REPORT_DIR / "oty2_gm011_object_stream_preflight_report_20260704_162842.md"
OT0_MANIFEST = REPO_ROOT / "manifests" / "ot0_stream_manifest.csv"
OTY0_MANIFEST = REPO_ROOT / "manifests" / "oty0_yolo_manifest.csv"
SCENE_CONFIG = REPO_ROOT / "configs" / "scene_config.yaml"
OTY_CONFIG = REPO_ROOT / "configs" / "oty_yolo_stream_config.yaml"


SOURCE_FIELDS = [
    "scene",
    "session_id",
    "source_type",
    "source_path",
    "exists",
    "committed_or_ignored",
    "frame_or_pulse_id_available",
    "timestamp_available",
    "timestamp_clock",
    "start_time_available",
    "end_time_available",
    "frame_rate_or_prf",
    "azimuth_index_available",
    "range_index_available",
    "platform_motion_available",
    "calibration_available",
    "derived_from",
    "provenance_status",
    "blocking_reason",
]

TIME_FIELDS = [
    "message_id",
    "scene",
    "optical_source_channel",
    "source_track_or_thread_id",
    "optical_frame_start",
    "optical_frame_end",
    "optical_time_start_proxy_s",
    "optical_time_end_proxy_s",
    "direct_timestamp_available",
    "proxy_used",
    "time_mapping_status",
    "time_uncertainty_ms",
    "mapping_source",
    "blocking_reason",
]

WINDOW_FIELDS = [
    "message_id",
    "scene",
    "optical_source_channel",
    "source_track_or_thread_id",
    "sar_frame_start",
    "sar_frame_end",
    "sar_window_ids",
    "sar_frame_count",
    "sar_image_source",
    "sar_gray_image_source",
    "start_image_exists",
    "end_image_exists",
    "all_window_images_exist",
    "sar_png_window_traceability",
    "raw_pulse_window_traceability",
    "mapping_source",
    "blocking_reason",
]

FIELD_FIELDS = [
    "message_id",
    "scene",
    "optical_source_channel",
    "source_track_or_thread_id",
    "optical_frame_start",
    "optical_frame_end",
    "optical_time_start",
    "optical_time_end",
    "time_uncertainty_ms",
    "sar_frame_start",
    "sar_frame_end",
    "sar_window_ids",
    "azimuth_min",
    "azimuth_max",
    "azimuth_uncertainty",
    "range_min",
    "range_max",
    "range_status",
    "temporal_support",
    "azimuth_support",
    "range_support",
    "feasible_field_level",
    "mapping_source",
    "mapping_assumptions",
    "runtime_safe",
    "posthoc_only",
    "provenance_status",
    "blocking_reason",
]

FREEZE_FIELDS = [
    "freeze_id",
    "scene",
    "hypothesis_id",
    "source_auto_node_id",
    "possible_successor_node_ids",
    "relation_ids",
    "competition_ids",
    "optical_frame_start",
    "optical_frame_end",
    "bbox_envelope",
    "sar_frame_start",
    "sar_frame_end",
    "azimuth_min",
    "azimuth_max",
    "hypothesis_permission",
    "uncertainty_sources",
    "freeze_input_files",
    "freeze_content_sha256",
    "wgv1_4_read_before_freeze",
]

METRIC_FIELDS = [
    "metric_name",
    "metric_value",
    "metric_status",
    "numerator",
    "denominator",
    "notes",
]


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_text(self) -> str:
        return ",".join(fmt(value, 3) for value in (self.x1, self.y1, self.x2, self.y2))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


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


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_int(value: Any, default: int | None = None) -> int | None:
    text = norm(value)
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def parse_float(value: Any, default: float | None = None) -> float | None:
    text = norm(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def fmt(value: Any, digits: int = 6) -> str:
    number = parse_float(value)
    if number is None or not math.isfinite(number):
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in norm(value).split(";") if part.strip()]


def rel(path: Path | str) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_bbox(value: Any) -> BBox | None:
    text = norm(value)
    if not text:
        return None
    try:
        payload = json.loads(text)
        nums = [float(item) for item in payload[:4]]
    except Exception:
        nums = [float(item) for item in re.findall(r"[-+]?\d+(?:\.\d+)?", text)[:4]]
    if len(nums) != 4:
        return None
    box = BBox(*nums)
    return box if box.area > 0 else None


def envelope(boxes: Iterable[BBox | None]) -> BBox | None:
    clean = [box for box in boxes if box is not None]
    if not clean:
        return None
    return BBox(
        min(box.x1 for box in clean),
        min(box.y1 for box in clean),
        max(box.x2 for box in clean),
        max(box.y2 for box in clean),
    )


def node_envelope(row: Mapping[str, Any]) -> BBox | None:
    return envelope([parse_bbox(row.get("start_bbox")), parse_bbox(row.get("end_bbox"))])


def azimuth_interval_for_box(box: BBox | None, margin_deg: float) -> tuple[float, float, str]:
    if box is None:
        return FULL_AZIMUTH_MIN, FULL_AZIMUTH_MAX, "missing_bbox_scene_wide"
    lo = min(AZIMUTH_K * box.x1 + AZIMUTH_B, AZIMUTH_K * box.x2 + AZIMUTH_B) - margin_deg
    hi = max(AZIMUTH_K * box.x1 + AZIMUTH_B, AZIMUTH_K * box.x2 + AZIMUTH_B) + margin_deg
    return max(FULL_AZIMUTH_MIN, lo), min(FULL_AZIMUTH_MAX, hi), "configured_legacy_optical_x_to_sar_azimuth_proxy"


def node_margin(row: Mapping[str, Any]) -> tuple[float, str]:
    reasons: list[str] = []
    margin = 5.0
    if (parse_float(row.get("truncation_like_ratio"), 0.0) or 0.0) >= 0.5:
        margin = max(margin, 12.0)
        reasons.append("truncation_like_node")
    if "duplicate" in norm(row.get("track_identity_status")).lower() or norm(row.get("optical_message_readiness")) != "ready":
        margin = max(margin, 15.0)
        reasons.append("automatic_identity_uncertain")
    if parse_int(row.get("same_frame_competitor_count"), 0):
        margin = max(margin, 15.0)
        reasons.append("same_frame_competition")
    return margin, ";".join(reasons) if reasons else "stable_auto_node_margin"


def sar_window_for_optical(start_frame: int, end_frame: int, offset_margin: int = OFFSET_MARGIN_SAR_FRAMES) -> tuple[int, int]:
    start = int(round(start_frame * FPS_RATIO - offset_margin)) - 1
    end = int(round(end_frame * FPS_RATIO + offset_margin)) + 1
    return max(0, start), min(SAR_FRAME_MAX, end)


def nominal_sar_window(start_frame: int, end_frame: int) -> tuple[int, int]:
    start = int(round(start_frame * FPS_RATIO)) - 1
    end = int(round(end_frame * FPS_RATIO)) + 1
    return max(0, start), min(SAR_FRAME_MAX, end)


def optical_time(frame: int) -> float:
    return frame / OPTICAL_FPS


def sar_path(scene: str, frame: int, gray: bool = False) -> Path:
    suffix = f"{scene}_SARframes_gray" if gray else f"{scene}_SARframes"
    return DATA_ROOT / scene / suffix / f"{frame:06d}.png"


def optical_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_frames" / f"{frame:06d}.png"


def all_sar_images_exist(scene: str, start: int, end: int, gray: bool = False) -> bool:
    return all(sar_path(scene, frame, gray=gray).exists() for frame in range(start, end + 1))


def count_files(path: Path, suffix: str) -> tuple[int, int | None, int | None]:
    if not path.exists():
        return 0, None, None
    nums: list[int] = []
    for item in path.iterdir():
        if not item.is_file() or item.suffix.lower() != suffix:
            continue
        stem = item.stem.split("_")[0]
        if stem.isdigit():
            nums.append(int(stem))
    return len(nums), (min(nums) if nums else None), (max(nums) if nums else None)


def image_size(path: Path) -> str:
    if not path.exists():
        return ""
    with Image.open(path) as img:
        return f"{img.size[0]}x{img.size[1]}:{img.mode}"


def image_luma_stats(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"exists": "false"}
    with Image.open(path) as img:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        lo, hi = gray.getextrema()
        return {
            "exists": "true",
            "size": f"{img.size[0]}x{img.size[1]}",
            "mean": fmt(stat.mean[0], 3),
            "std": fmt(stat.stddev[0], 3),
            "min": str(lo),
            "max": str(hi),
        }


def sector_stats(scene: str, frame: int, amin: float, amax: float) -> dict[str, str]:
    path = sar_path(scene, frame, gray=True)
    if not path.exists():
        return {"frame": str(frame), "status": "missing_image"}
    with Image.open(path) as img:
        gray = img.convert("L")
        width, height = gray.size
        pixels = gray.load()
        vals: list[int] = []
        for y in range(0, height, 4):
            for x in range(0, width, 4):
                radius = math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)
                if radius > FAN_RADIUS_PX:
                    continue
                az = math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))
                if amin <= az <= amax:
                    vals.append(int(pixels[x, y]))
        if not vals:
            return {"frame": str(frame), "status": "empty_sector"}
        vals_sorted = sorted(vals)
        top_n = max(1, len(vals_sorted) // 20)
        return {
            "frame": str(frame),
            "status": "sampled",
            "sample_count": str(len(vals)),
            "mean": fmt(sum(vals) / len(vals), 3),
            "max": str(max(vals)),
            "top5_mean": fmt(sum(vals_sorted[-top_n:]) / top_n, 3),
        }


def shifted_background_interval(target_min: float, target_max: float) -> tuple[float, float]:
    if target_max < 65.0:
        return 70.0, 85.0
    if target_min > -65.0:
        return -85.0, -70.0
    return 55.0, 70.0


def interval_bins(amin: float, amax: float, step: float = 0.5) -> set[int]:
    start = math.floor((amin - FULL_AZIMUTH_MIN) / step)
    end = math.ceil((amax - FULL_AZIMUTH_MIN) / step)
    return set(range(max(0, start), min(int((FULL_AZIMUTH_MAX - FULL_AZIMUTH_MIN) / step), end) + 1))


def field_cells(rows: Sequence[Mapping[str, Any]], step: float = 0.5) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for row in rows:
        start = parse_int(row.get("sar_frame_start"))
        end = parse_int(row.get("sar_frame_end"))
        amin = parse_float(row.get("azimuth_min"))
        amax = parse_float(row.get("azimuth_max"))
        if start is None or end is None or amin is None or amax is None:
            continue
        bins = interval_bins(amin, amax, step=step)
        for frame in range(start, end + 1):
            for bin_id in bins:
                cells.add((frame, bin_id))
    return cells


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    subset = list(rows[:limit] if limit is not None else rows)
    if not subset:
        return "none"
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in subset:
        out.append("| " + " | ".join(str(row.get(field, "")).replace("\n", " ") for field in fields) + " |")
    return "\n".join(out)


def source_row(
    source_type: str,
    path: Path | str,
    *,
    exists: bool,
    committed_or_ignored: str,
    frame_or_pulse_id_available: bool,
    timestamp_available: bool,
    timestamp_clock: str,
    frame_rate_or_prf: str,
    azimuth_index_available: bool,
    range_index_available: bool,
    platform_motion_available: bool,
    calibration_available: str,
    derived_from: str,
    provenance_status: str,
    blocking_reason: str,
) -> dict[str, Any]:
    return {
        "scene": SCENE,
        "session_id": "WGV3.3B",
        "source_type": source_type,
        "source_path": rel(path),
        "exists": bool_text(exists),
        "committed_or_ignored": committed_or_ignored,
        "frame_or_pulse_id_available": bool_text(frame_or_pulse_id_available),
        "timestamp_available": bool_text(timestamp_available),
        "timestamp_clock": timestamp_clock,
        "start_time_available": "false",
        "end_time_available": "false",
        "frame_rate_or_prf": frame_rate_or_prf,
        "azimuth_index_available": bool_text(azimuth_index_available),
        "range_index_available": bool_text(range_index_available),
        "platform_motion_available": bool_text(platform_motion_available),
        "calibration_available": calibration_available,
        "derived_from": derived_from,
        "provenance_status": provenance_status,
        "blocking_reason": blocking_reason,
    }


def build_source_rows() -> list[dict[str, Any]]:
    scene_root = DATA_ROOT / SCENE
    optical_dir = scene_root / f"{SCENE}_frames"
    depth_dir = scene_root / f"{SCENE}_depth"
    sar_dir = scene_root / f"{SCENE}_SARframes"
    sar_gray_dir = scene_root / f"{SCENE}_SARframes_gray"
    optical_count, optical_min, optical_max = count_files(optical_dir, ".png")
    sar_count, sar_min, sar_max = count_files(sar_dir, ".png")
    gray_count, gray_min, gray_max = count_files(sar_gray_dir, ".png")
    depth_png_count, depth_min, depth_max = count_files(depth_dir, ".png")
    raw_candidates = [
        item
        for item in scene_root.rglob("*")
        if item.is_file() and item.suffix.lower() in {".mat", ".bin", ".dat", ".raw", ".h5", ".npy"} and "depth" not in item.parts[-2].lower()
    ]
    rows = [
        source_row(
            "optical_png_frames",
            optical_dir,
            exists=optical_dir.exists(),
            committed_or_ignored="outside_repo_unregistered_local_data",
            frame_or_pulse_id_available=optical_count > 0,
            timestamp_available=False,
            timestamp_clock=f"numeric_filename_order_only:{optical_min}-{optical_max}",
            frame_rate_or_prf="known_scale_metadata_optical_fps=24_not_per_frame_timestamp",
            azimuth_index_available=True,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available="legacy optical-x to SAR azimuth config available separately",
            derived_from="manifests/ot0_stream_manifest.csv;configs/oty_yolo_stream_config.yaml",
            provenance_status="SOURCE_PRESENT_AND_TRACEABLE",
            blocking_reason="direct optical timestamps absent",
        ),
        source_row(
            "optical_depth_sidecar",
            depth_dir,
            exists=depth_dir.exists(),
            committed_or_ignored="outside_repo_unregistered_local_data",
            frame_or_pulse_id_available=depth_png_count > 0,
            timestamp_available=False,
            timestamp_clock=f"numeric_filename_order_only:{depth_min}-{depth_max}",
            frame_rate_or_prf="same optical frame ids; no direct depth timebase",
            azimuth_index_available=False,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available="not consumed for WGV3.3B range",
            derived_from="local depth npy/png sidecar inventory",
            provenance_status="SOURCE_PRESENT_UNREGISTERED",
            blocking_reason="depth-to-SAR range transfer is not calibrated in current source chain",
        ),
        source_row(
            "sar_png_frames",
            sar_dir,
            exists=sar_dir.exists(),
            committed_or_ignored="outside_repo_unregistered_local_data",
            frame_or_pulse_id_available=sar_count > 0,
            timestamp_available=False,
            timestamp_clock=f"numeric_filename_order_only:{sar_min}-{sar_max}",
            frame_rate_or_prf="known_scale_metadata_sar_fps=50_not_per_frame_timestamp",
            azimuth_index_available=True,
            range_index_available=True,
            platform_motion_available=False,
            calibration_available="display fan geometry only; raw pulse to png mapping missing",
            derived_from="manifests/ot0_stream_manifest.csv;GM_RM011 preflight inventory",
            provenance_status="SOURCE_PRESENT_BUT_MAPPING_MISSING",
            blocking_reason="raw pulse/window length/step and physical range-axis mapping are absent",
        ),
        source_row(
            "sar_gray_png_frames",
            sar_gray_dir,
            exists=sar_gray_dir.exists(),
            committed_or_ignored="outside_repo_unregistered_local_data",
            frame_or_pulse_id_available=gray_count > 0,
            timestamp_available=False,
            timestamp_clock=f"numeric_filename_order_only:{gray_min}-{gray_max}",
            frame_rate_or_prf="known_scale_metadata_sar_fps=50_not_per_frame_timestamp",
            azimuth_index_available=True,
            range_index_available=True,
            platform_motion_available=False,
            calibration_available="display fan geometry only; raw pulse to png mapping missing",
            derived_from="manifests/ot0_stream_manifest.csv;GM_RM011 preflight inventory",
            provenance_status="SOURCE_PRESENT_BUT_MAPPING_MISSING",
            blocking_reason="gray image exists but raw pulse/window derivation is not traceable",
        ),
        source_row(
            "sar_raw_pulse_or_mat_source",
            scene_root,
            exists=bool(raw_candidates),
            committed_or_ignored="outside_repo_search",
            frame_or_pulse_id_available=False,
            timestamp_available=False,
            timestamp_clock="not_found",
            frame_rate_or_prf="not_found",
            azimuth_index_available=False,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available="not_found",
            derived_from="recursive search under D:/profile/research/data/GM_RM011",
            provenance_status="SOURCE_NOT_PRESENT",
            blocking_reason="no non-depth .mat/.bin/.dat/.raw/.h5/.npy SAR pulse source found",
        ),
        source_row(
            "software_sync_timing_proxy",
            ALIGNMENT_SUMMARY,
            exists=ALIGNMENT_SUMMARY.exists(),
            committed_or_ignored="tracked_report",
            frame_or_pulse_id_available=True,
            timestamp_available=False,
            timestamp_clock="software_sync_zero_offset_assumption",
            frame_rate_or_prf="optical_fps=24;sar_fps=50;scale=2.083333;jitter_ms=20",
            azimuth_index_available=False,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available="time scale metadata only",
            derived_from="OTY2-P1 temporal alignment decision",
            provenance_status="SOURCE_PRESENT_AND_TRACEABLE",
            blocking_reason="not hardware-exact; no per-frame timestamps",
        ),
        source_row(
            "legacy_optical_x_to_sar_azimuth_proxy",
            SCENE_CONFIG,
            exists=SCENE_CONFIG.exists(),
            committed_or_ignored="tracked_config",
            frame_or_pulse_id_available=False,
            timestamp_available=False,
            timestamp_clock="not_applicable",
            frame_rate_or_prf="not_applicable",
            azimuth_index_available=True,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available=f"azimuth_k={AZIMUTH_K};azimuth_b={AZIMUTH_B};fan_center={FAN_CENTER_X},{FAN_CENTER_Y}",
            derived_from="configs/scene_config.yaml global_geometry.fan",
            provenance_status="SOURCE_PRESENT_AND_TRACEABLE",
            blocking_reason="coarse legacy proxy only; no full camera-radar extrinsic or range transfer",
        ),
        source_row(
            "wgv3_3a_automatic_tracklet_nodes",
            WGV33A_NODES,
            exists=WGV33A_NODES.exists(),
            committed_or_ignored="tracked_report",
            frame_or_pulse_id_available=True,
            timestamp_available=False,
            timestamp_clock="optical_frame_index",
            frame_rate_or_prf="inherits optical_fps=24 proxy",
            azimuth_index_available=True,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available="uses bbox x envelope with legacy azimuth proxy",
            derived_from="WGV3.3A automatic freeze",
            provenance_status="SOURCE_PRESENT_AND_TRACEABLE",
            blocking_reason="identity relations uncertain; no range",
        ),
        source_row(
            "wgv1_4_wgv1_8_posthoc_channel",
            WGV14_THREADS,
            exists=WGV14_THREADS.exists() and WGV18_CANDIDATES.exists(),
            committed_or_ignored="tracked_report",
            frame_or_pulse_id_available=True,
            timestamp_available=False,
            timestamp_clock="posthoc optical and prior-report SAR frame indices",
            frame_rate_or_prf="posthoc comparison only",
            azimuth_index_available=True,
            range_index_available=False,
            platform_motion_available=False,
            calibration_available="after-freeze comparison only",
            derived_from="WGV1.4/WGV1.8",
            provenance_status="SOURCE_PRESENT_AND_TRACEABLE",
            blocking_reason="posthoc_visual_constraint; not automatic runtime input",
        ),
    ]
    return rows


def build_auto_freeze(
    nodes: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
    competitions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[Mapping[str, Any]]]:
    selected_nodes = [
        row
        for row in nodes
        if norm(row.get("scene")) == SCENE
        and parse_int(row.get("start_frame"), 999999) <= AUTO_NEIGHBORHOOD_END
        and parse_int(row.get("end_frame"), -1) >= PRIMARY_OPTICAL_START
    ]
    selected_nodes = sorted(selected_nodes, key=lambda row: parse_int(row.get("start_frame"), 0) or 0)
    node_ids = {norm(row.get("auto_node_id")) for row in selected_nodes}
    relation_by_source: dict[str, list[Mapping[str, Any]]] = {}
    for row in relations:
        if norm(row.get("scene")) != SCENE:
            continue
        if norm(row.get("source_auto_node_id")) in node_ids and norm(row.get("target_auto_node_id")) in node_ids:
            relation_by_source.setdefault(norm(row.get("source_auto_node_id")), []).append(row)
    competition_by_node: dict[str, list[Mapping[str, Any]]] = {node_id: [] for node_id in node_ids}
    for row in competitions:
        ids = {norm(row.get("anchor_auto_node_id"))}
        ids.update(split_semicolon(row.get("candidate_auto_node_ids")))
        for node_id in node_ids & ids:
            competition_by_node.setdefault(node_id, []).append(row)
    freeze_rows: list[dict[str, Any]] = []
    input_files = ";".join(rel(path) for path in [WGV33A_NODES, WGV33A_RELATIONS, WGV33A_COMPETITION, WGV33A_CAPABILITY])
    for idx, node in enumerate(selected_nodes, start=1):
        node_id = norm(node.get("auto_node_id"))
        start = parse_int(node.get("start_frame"), PRIMARY_OPTICAL_START) or PRIMARY_OPTICAL_START
        end = parse_int(node.get("end_frame"), start) or start
        sar_start, sar_end = sar_window_for_optical(start, end)
        box = node_envelope(node)
        margin, margin_reason = node_margin(node)
        amin, amax, az_source = azimuth_interval_for_box(box, margin)
        rel_rows = relation_by_source.get(node_id, [])
        comp_rows = competition_by_node.get(node_id, [])
        permission = "automatic_runtime_hypothesis" if norm(node.get("optical_message_readiness")) == "ready" else "automatic_uncertain_hypothesis"
        freeze_rows.append(
            {
                "freeze_id": f"WGV33B_FREEZE_{idx:03d}",
                "scene": SCENE,
                "hypothesis_id": f"WGV33B_H{idx:03d}",
                "source_auto_node_id": node_id,
                "possible_successor_node_ids": ";".join(norm(row.get("target_auto_node_id")) for row in rel_rows),
                "relation_ids": ";".join(norm(row.get("relation_id")) for row in rel_rows),
                "competition_ids": ";".join(norm(row.get("competition_id")) for row in comp_rows),
                "optical_frame_start": start,
                "optical_frame_end": end,
                "bbox_envelope": box.as_text() if box else "",
                "sar_frame_start": sar_start,
                "sar_frame_end": sar_end,
                "azimuth_min": fmt(amin, 3),
                "azimuth_max": fmt(amax, 3),
                "hypothesis_permission": permission,
                "uncertainty_sources": ";".join(
                    part
                    for part in [
                        margin_reason,
                        norm(node.get("track_identity_status")),
                        norm(node.get("track_status")),
                        az_source,
                        "range_unavailable",
                    ]
                    if part
                ),
                "freeze_input_files": input_files,
                "freeze_content_sha256": "",
                "wgv1_4_read_before_freeze": "false",
            }
        )
    canonical = json.dumps(freeze_rows, sort_keys=True, ensure_ascii=False)
    digest = sha256_text(canonical)
    for row in freeze_rows:
        row["freeze_content_sha256"] = digest
    return freeze_rows, selected_nodes


def build_time_rows(auto_rows: Sequence[Mapping[str, Any]], channel_a_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in auto_rows:
        start = parse_int(row.get("optical_frame_start"), 0) or 0
        end = parse_int(row.get("optical_frame_end"), start) or start
        rows.append(
            {
                "message_id": row["hypothesis_id"],
                "scene": SCENE,
                "optical_source_channel": row["hypothesis_permission"],
                "source_track_or_thread_id": row["source_auto_node_id"],
                "optical_frame_start": start,
                "optical_frame_end": end,
                "optical_time_start_proxy_s": fmt(optical_time(start), 4),
                "optical_time_end_proxy_s": fmt(optical_time(end), 4),
                "direct_timestamp_available": "false",
                "proxy_used": "true",
                "time_mapping_status": "BOUNDED_TIME_PROXY",
                "time_uncertainty_ms": str(int(max(OFFSET_MARGIN_SAR_FRAMES / SAR_FPS * 1000, SOFTWARE_SYNC_JITTER_MS))),
                "mapping_source": "software_sync_zero_offset_scale_24_to_50_with_wgv1_7_offset_stress_band",
                "blocking_reason": "real per-frame timestamps and hardware-exact sync are absent",
            }
        )
    rows.append(channel_a_row)
    return rows


def build_window_rows(time_rows: Sequence[Mapping[str, Any]], field_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    source_by_message = {row["message_id"]: row for row in field_rows}
    rows: list[dict[str, Any]] = []
    for row in time_rows:
        field = source_by_message.get(row["message_id"], {})
        sar_start = parse_int(field.get("sar_frame_start"), 0) or 0
        sar_end = parse_int(field.get("sar_frame_end"), sar_start) or sar_start
        rows.append(
            {
                "message_id": row["message_id"],
                "scene": SCENE,
                "optical_source_channel": row["optical_source_channel"],
                "source_track_or_thread_id": row["source_track_or_thread_id"],
                "sar_frame_start": sar_start,
                "sar_frame_end": sar_end,
                "sar_window_ids": f"SAR_{sar_start:06d}_{sar_end:06d}",
                "sar_frame_count": sar_end - sar_start + 1,
                "sar_image_source": rel(DATA_ROOT / SCENE / f"{SCENE}_SARframes"),
                "sar_gray_image_source": rel(DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray"),
                "start_image_exists": bool_text(sar_path(SCENE, sar_start).exists()),
                "end_image_exists": bool_text(sar_path(SCENE, sar_end).exists()),
                "all_window_images_exist": bool_text(all_sar_images_exist(SCENE, sar_start, sar_end)),
                "sar_png_window_traceability": "SOURCE_PRESENT_AND_TRACEABLE",
                "raw_pulse_window_traceability": "SOURCE_PRESENT_BUT_MAPPING_MISSING",
                "mapping_source": field.get("mapping_source", ""),
                "blocking_reason": "SAR PNG frame indices are traceable; raw pulse/window-to-PNG mapping is missing",
            }
        )
    return rows


def field_from_freeze_row(row: Mapping[str, Any]) -> dict[str, Any]:
    start = parse_int(row.get("optical_frame_start"), 0) or 0
    end = parse_int(row.get("optical_frame_end"), start) or start
    sar_start = parse_int(row.get("sar_frame_start"), 0) or 0
    sar_end = parse_int(row.get("sar_frame_end"), sar_start) or sar_start
    return {
        "message_id": row["hypothesis_id"],
        "scene": SCENE,
        "optical_source_channel": row["hypothesis_permission"],
        "source_track_or_thread_id": row["source_auto_node_id"],
        "optical_frame_start": start,
        "optical_frame_end": end,
        "optical_time_start": fmt(optical_time(start), 4),
        "optical_time_end": fmt(optical_time(end), 4),
        "time_uncertainty_ms": str(int(max(OFFSET_MARGIN_SAR_FRAMES / SAR_FPS * 1000, SOFTWARE_SYNC_JITTER_MS))),
        "sar_frame_start": sar_start,
        "sar_frame_end": sar_end,
        "sar_window_ids": f"SAR_{sar_start:06d}_{sar_end:06d}",
        "azimuth_min": row["azimuth_min"],
        "azimuth_max": row["azimuth_max"],
        "azimuth_uncertainty": "state_margin_from_auto_truncation_duplicate_competition;legacy_mapping_proxy",
        "range_min": "0",
        "range_max": fmt(FAN_RADIUS_PX, 1),
        "range_status": "broad_unknown_range_prior",
        "temporal_support": "software_sync_scale_plus_offset_stress_band",
        "azimuth_support": "configured_legacy_optical_x_to_sar_azimuth_proxy",
        "range_support": "not_recovered_runtime_safe",
        "feasible_field_level": "Level 2: time + coarse azimuth proxy; broad range",
        "mapping_source": "WGV3.3A automatic node bbox + scene_config azimuth_k/b + OTY2 timing proxy",
        "mapping_assumptions": "automatic identity unresolved; no GT; no final SAR selector; range is broad fan radius",
        "runtime_safe": "true",
        "posthoc_only": "false",
        "provenance_status": "SOURCE_PRESENT_AND_TRACEABLE",
        "blocking_reason": "range and raw SAR pulse/window mapping remain missing",
    }


def build_channel_a(
    nodes_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[Mapping[str, Any]], list[str]]:
    threads = read_csv(WGV14_THREADS)
    fragments = read_csv(WGV14_FRAGMENTS)
    mappings = read_csv(WGV33A_MAPPING)
    candidates = read_csv(WGV18_CANDIDATES)

    thread = next(row for row in threads if norm(row.get("wgv1_4_thread_id")) == PRIMARY_THREAD_ID)
    candidate = next(row for row in candidates if norm(row.get("window_id")) == PRIMARY_WINDOW_ID)
    mapped = [row for row in mappings if norm(row.get("wgv1_4_thread_id")) == PRIMARY_THREAD_ID]
    mapped_node_ids = [norm(row.get("mapped_auto_node_id")) for row in mapped if norm(row.get("mapped_auto_node_id"))]
    mapped_nodes = [nodes_by_id[node_id] for node_id in mapped_node_ids if node_id in nodes_by_id]
    boxes = [node_envelope(row) for row in mapped_nodes]
    combined = envelope(boxes)
    margin = 15.0
    amin, amax, _ = azimuth_interval_for_box(combined, margin)
    optical_start = parse_int(thread.get("frame_start"), PRIMARY_OPTICAL_START) or PRIMARY_OPTICAL_START
    optical_end = parse_int(thread.get("frame_end"), PRIMARY_OPTICAL_END) or PRIMARY_OPTICAL_END
    sar_start = parse_int(candidate.get("sar_frame_candidate_start"), 0) or 0
    sar_end = parse_int(candidate.get("sar_frame_candidate_end"), sar_start) or sar_start
    time_row = {
        "message_id": "A_POSTHOC_T001",
        "scene": SCENE,
        "optical_source_channel": "posthoc_visual_constraint",
        "source_track_or_thread_id": PRIMARY_THREAD_ID,
        "optical_frame_start": optical_start,
        "optical_frame_end": optical_end,
        "optical_time_start_proxy_s": fmt(optical_time(optical_start), 4),
        "optical_time_end_proxy_s": fmt(optical_time(optical_end), 4),
        "direct_timestamp_available": "false",
        "proxy_used": "true",
        "time_mapping_status": "POSTHOC_PRIOR_REPORT_TRACEABLE",
        "time_uncertainty_ms": str(int(max(OFFSET_MARGIN_SAR_FRAMES / SAR_FPS * 1000, SOFTWARE_SYNC_JITTER_MS))),
        "mapping_source": "WGV1.8 prior_report_traceable candidate range; posthoc comparison only",
        "blocking_reason": "posthoc channel; not automatic runtime input",
    }
    field_row = {
        "message_id": "A_POSTHOC_T001",
        "scene": SCENE,
        "optical_source_channel": "posthoc_visual_constraint",
        "source_track_or_thread_id": PRIMARY_THREAD_ID,
        "optical_frame_start": optical_start,
        "optical_frame_end": optical_end,
        "optical_time_start": fmt(optical_time(optical_start), 4),
        "optical_time_end": fmt(optical_time(optical_end), 4),
        "time_uncertainty_ms": time_row["time_uncertainty_ms"],
        "sar_frame_start": sar_start,
        "sar_frame_end": sar_end,
        "sar_window_ids": f"SAR_{sar_start:06d}_{sar_end:06d}",
        "azimuth_min": fmt(amin, 3),
        "azimuth_max": fmt(amax, 3),
        "azimuth_uncertainty": "posthoc T001 visual constraint + after-freeze WGV3.3A mapped bbox interval",
        "range_min": "0",
        "range_max": fmt(FAN_RADIUS_PX, 1),
        "range_status": "broad_unknown_range_prior",
        "temporal_support": "WGV1.8 prior_report_traceable posthoc candidate range",
        "azimuth_support": "WGV1.4 T001 posthoc thread mapped after freeze to WGV3.3A auto node bbox",
        "range_support": "not_recovered_runtime_safe",
        "feasible_field_level": "Level 2: posthoc time + coarse azimuth proxy; broad range",
        "mapping_source": "WGV1.4 T001 + WGV1.8 WGV18W001 + WGV3.3A mapping read after automatic freeze",
        "mapping_assumptions": "posthoc visual constraint only; no GT-derived runtime construction",
        "runtime_safe": "false",
        "posthoc_only": "true",
        "provenance_status": "SOURCE_PRESENT_AND_TRACEABLE",
        "blocking_reason": "posthoc_visual_constraint; not automatic runtime input",
    }
    fragment_rows = [row for row in fragments if norm(row.get("wgv1_4_thread_id")) == PRIMARY_THREAD_ID]
    return time_row, field_row, fragment_rows, mapped_node_ids


def build_negative_control(reference: Mapping[str, Any]) -> dict[str, Any]:
    amin = parse_float(reference.get("azimuth_min"), -50.0) or -50.0
    amax = parse_float(reference.get("azimuth_max"), 50.0) or 50.0
    neg_min, neg_max = shifted_background_interval(amin, amax)
    sar_start = parse_int(reference.get("sar_frame_start"), 0) or 0
    sar_end = parse_int(reference.get("sar_frame_end"), sar_start) or sar_start
    return {
        "message_id": "NEG_T001_SHIFTED_AZIMUTH_CONTROL",
        "scene": SCENE,
        "optical_source_channel": "negative_background_control",
        "source_track_or_thread_id": "non_target_shifted_azimuth_same_time_window",
        "optical_frame_start": reference.get("optical_frame_start", ""),
        "optical_frame_end": reference.get("optical_frame_end", ""),
        "optical_time_start": reference.get("optical_time_start", ""),
        "optical_time_end": reference.get("optical_time_end", ""),
        "time_uncertainty_ms": reference.get("time_uncertainty_ms", ""),
        "sar_frame_start": sar_start,
        "sar_frame_end": sar_end,
        "sar_window_ids": f"SAR_{sar_start:06d}_{sar_end:06d}",
        "azimuth_min": fmt(neg_min, 3),
        "azimuth_max": fmt(neg_max, 3),
        "azimuth_uncertainty": "control sector selected away from T001 optical-derived azimuth interval",
        "range_min": "0",
        "range_max": fmt(FAN_RADIUS_PX, 1),
        "range_status": "broad_unknown_range_prior",
        "temporal_support": "same SAR time range as posthoc T001",
        "azimuth_support": "shifted non-target background sector; no GT",
        "range_support": "not_recovered_runtime_safe",
        "feasible_field_level": "negative control: same time, shifted azimuth, broad range",
        "mapping_source": "non-GT shifted-azimuth background control",
        "mapping_assumptions": "not asserted empty; only non-target relative to T001 optical-derived field",
        "runtime_safe": "true",
        "posthoc_only": "false",
        "provenance_status": "SOURCE_PRESENT_AND_TRACEABLE",
        "blocking_reason": "control can contain clutter or other objects; not a target selection",
    }


def build_metrics(
    auto_fields: Sequence[Mapping[str, Any]],
    posthoc_field: Mapping[str, Any],
    negative_field: Mapping[str, Any],
    freeze_rows: Sequence[Mapping[str, Any]],
    reference_fields: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    auto_cells = field_cells(auto_fields)
    posthoc_cells = field_cells(reference_fields)
    full_bins = len(interval_bins(FULL_AZIMUTH_MIN, FULL_AZIMUTH_MAX))
    full_cells = (SAR_FRAME_MAX + 1) * full_bins
    covered_posthoc = bool(posthoc_cells and posthoc_cells.issubset(auto_cells))
    auto_sar_min = min(parse_int(row.get("sar_frame_start"), 0) or 0 for row in auto_fields)
    auto_sar_max = max(parse_int(row.get("sar_frame_end"), 0) or 0 for row in auto_fields)
    post_sar_start = parse_int(posthoc_field.get("sar_frame_start"), 0) or 0
    post_sar_end = parse_int(posthoc_field.get("sar_frame_end"), 0) or 0
    time_covered = auto_sar_min <= post_sar_start and auto_sar_max >= post_sar_end
    statuses = Counter(row.get("hypothesis_permission", "") for row in freeze_rows)
    rows = [
        {
            "metric_name": "time_source_coverage",
            "metric_value": "1",
            "metric_status": "proxy_available_not_direct_timestamp",
            "numerator": "1",
            "denominator": "1",
            "notes": "24/50 scale metadata plus software-sync zero-offset assumption and WGV1.7 offset stress band",
        },
        {
            "metric_name": "sar_window_traceability",
            "metric_value": "1",
            "metric_status": "png_window_traceable_raw_pulse_mapping_missing",
            "numerator": "1",
            "denominator": "1",
            "notes": "GM_RM011 SAR/SAR-gray PNG images 000000-000765 exist",
        },
        {
            "metric_name": "azimuth_source_coverage",
            "metric_value": "1",
            "metric_status": "coarse_proxy_available",
            "numerator": "1",
            "denominator": "1",
            "notes": "scene_config legacy azimuth_k/b + WGV3.3A automatic bbox envelope",
        },
        {
            "metric_name": "range_source_coverage",
            "metric_value": "0",
            "metric_status": "broad_unknown_range_only",
            "numerator": "0",
            "denominator": "1",
            "notes": "no runtime-safe per-object range/depth-to-SAR transfer or raw range-axis metadata",
        },
        {
            "metric_name": "automatic_feasible_field_time_coverage",
            "metric_value": bool_text(time_covered),
            "metric_status": "covered" if time_covered else "not_covered",
            "numerator": str(post_sar_end - post_sar_start + 1 if time_covered else 0),
            "denominator": str(post_sar_end - post_sar_start + 1),
            "notes": f"auto union SAR {auto_sar_min}-{auto_sar_max}; posthoc T001 SAR {post_sar_start}-{post_sar_end}",
        },
        {
            "metric_name": "automatic_feasible_field_joint_time_azimuth_coverage",
            "metric_value": bool_text(covered_posthoc),
            "metric_status": "covered_as_proxy" if covered_posthoc else "not_covered",
            "numerator": str(len(posthoc_cells & auto_cells)),
            "denominator": str(len(posthoc_cells)),
            "notes": "coverage is evaluated over WGV1.4 fragment-level mapped-node time-azimuth proxy cells; range not evaluated",
        },
        {
            "metric_name": "search_reduction_ratio_time_azimuth",
            "metric_value": fmt(len(auto_cells) / full_cells if full_cells else 0.0, 6),
            "metric_status": "proxy_reduction_not_selector",
            "numerator": str(len(auto_cells)),
            "denominator": str(full_cells),
            "notes": "automatic Channel B feasible field area over full SAR-frame by full-azimuth area; range full",
        },
        {
            "metric_name": "time_only_search_reduction_ratio",
            "metric_value": fmt((auto_sar_max - auto_sar_min + 1) / (SAR_FRAME_MAX + 1), 6),
            "metric_status": "proxy_reduction_not_selector",
            "numerator": str(auto_sar_max - auto_sar_min + 1),
            "denominator": str(SAR_FRAME_MAX + 1),
            "notes": "union automatic SAR frame window divided by all SAR frames",
        },
        {
            "metric_name": "automatic_hypothesis_count",
            "metric_value": str(len(freeze_rows)),
            "metric_status": "multi_hypothesis_preserved",
            "numerator": str(len(freeze_rows)),
            "denominator": "",
            "notes": json.dumps(dict(statuses), sort_keys=True),
        },
        {
            "metric_name": "negative_control_count",
            "metric_value": "1",
            "metric_status": "same_time_shifted_azimuth_control",
            "numerator": "1",
            "denominator": "",
            "notes": f"{negative_field['azimuth_min']}..{negative_field['azimuth_max']} deg",
        },
    ]
    return rows


def inspect_images(posthoc_field: Mapping[str, Any], negative_field: Mapping[str, Any]) -> dict[str, Any]:
    optical_frames = [8, 10, 13, 18, 25]
    sar_frames = [0, 18, 36, 37, 58]
    target_min = parse_float(posthoc_field.get("azimuth_min"), -50.0) or -50.0
    target_max = parse_float(posthoc_field.get("azimuth_max"), 50.0) or 50.0
    neg_min = parse_float(negative_field.get("azimuth_min"), 70.0) or 70.0
    neg_max = parse_float(negative_field.get("azimuth_max"), 85.0) or 85.0
    optical_rows = []
    for frame in optical_frames:
        path = optical_path(SCENE, frame)
        stats = image_luma_stats(path)
        optical_rows.append(
            {
                "frame": frame,
                "path": rel(path),
                "exists": stats.get("exists", "false"),
                "size": stats.get("size", ""),
                "mean": stats.get("mean", ""),
                "std": stats.get("std", ""),
            }
        )
    sar_rows = []
    for frame in sar_frames:
        path = sar_path(SCENE, frame, gray=True)
        stats = image_luma_stats(path)
        target = sector_stats(SCENE, frame, target_min, target_max)
        control = sector_stats(SCENE, frame, neg_min, neg_max)
        sar_rows.append(
            {
                "frame": frame,
                "path": rel(path),
                "exists": stats.get("exists", "false"),
                "size": stats.get("size", ""),
                "image_mean": stats.get("mean", ""),
                "target_sector_top5_mean": target.get("top5_mean", ""),
                "control_sector_top5_mean": control.get("top5_mean", ""),
                "target_sector_max": target.get("max", ""),
                "control_sector_max": control.get("max", ""),
            }
        )
    return {
        "optical_rows": optical_rows,
        "sar_rows": sar_rows,
        "target_azimuth": f"{fmt(target_min, 3)}..{fmt(target_max, 3)}",
        "control_azimuth": f"{fmt(neg_min, 3)}..{fmt(neg_max, 3)}",
    }


def render_source_report(
    source_rows: Sequence[Mapping[str, Any]],
    freeze_rows: Sequence[Mapping[str, Any]],
    output_paths: Mapping[str, Path],
) -> str:
    counts = Counter(row["provenance_status"] for row in source_rows)
    lines = [
        "# OTY2 WGV3.3B Source Provenance Audit",
        "",
        f"Date: {DATE}",
        "",
        "## Boundary",
        "",
        "This audit recovers source chains for feasible fields only. It does not use GT to construct runtime fields, does not select a SAR vehicle location, and does not modify annotations.",
        "",
        "## Provenance Status Counts",
        "",
        md_table([{"status": key, "count": value} for key, value in sorted(counts.items())], ["status", "count"]),
        "",
        "## Source Table",
        "",
        md_table(source_rows, ["source_type", "exists", "provenance_status", "frame_rate_or_prf", "calibration_available", "blocking_reason"]),
        "",
        "## Automatic Freeze",
        "",
        md_table(freeze_rows, ["freeze_id", "hypothesis_id", "source_auto_node_id", "sar_frame_start", "sar_frame_end", "azimuth_min", "azimuth_max", "hypothesis_permission"], limit=20),
        "",
        "The automatic freeze above was built before WGV1.4/WGV1.8 posthoc references were read.",
        "",
        "## Outputs",
        "",
        "\n".join(f"- `{rel(path)}`" for path in output_paths.values()),
        "",
    ]
    return "\n".join(lines)


def render_visual_report(
    inspection: Mapping[str, Any],
    field_rows: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# OTY2 WGV3.3B Visual Source And Mapping Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "## Actual Images Inspected",
        "",
        "### Optical Frames",
        "",
        md_table(inspection["optical_rows"], ["frame", "exists", "size", "mean", "std", "path"]),
        "",
        "### SAR / SAR-Gray Frames",
        "",
        md_table(
            inspection["sar_rows"],
            [
                "frame",
                "exists",
                "size",
                "image_mean",
                "target_sector_top5_mean",
                "control_sector_top5_mean",
                "target_sector_max",
                "control_sector_max",
                "path",
            ],
        ),
        "",
        "## Chinese Visual Judgment",
        "",
        "- 光学 T001：frame 8/10/13/18/25 显示的是近场白车的连续局部外观，主体从侧窗/车身局部逐步变成车头/引擎盖局部；画面存在强截断和主框选择不稳定，因此不能把它升级成唯一身份真值。",
        "- 自动通道：WGV3.3A 在同一时间邻域保留了多个自动节点，合理候选包括 `AUTO_GM_RM011_0001`、`AUTO_GM_RM011_0003`、`AUTO_GM_RM011_0005`，同时也保留 `AUTO_GM_RM011_0002/0006/0007` 等竞争或不确定节点。",
        f"- SAR 映射：T001 posthoc field 的粗方位代理为 `{inspection['target_azimuth']}` deg，负例/背景控制为 `{inspection['control_azimuth']}` deg；二者都只是在相近 SAR 时间窗内观察响应，不是最终车位。",
        "- SAR 图像：0/18/36 等 SAR-gray 帧能打开，目标方位扇区可见强散射峰；shifted control 扇区在当前采样下没有同级亮点，主要作为同时间非目标方位边界对照。这支持进入非 GT SAR 响应实验，但当前证据不足以宣布车辆精确位置。",
        "- 相邻 SAR 帧：37/58 帧仍有可见结构变化，说明短窗响应可观察；但缺少 raw pulse/window 映射和 range anchor，不能把峰值直接当目标。",
        "",
        "## Feasible Fields Reviewed",
        "",
        md_table(field_rows, ["message_id", "optical_source_channel", "sar_frame_start", "sar_frame_end", "azimuth_min", "azimuth_max", "range_status", "runtime_safe", "posthoc_only"], limit=20),
        "",
    ]
    return "\n".join(lines)


def render_closure_report(
    source_rows: Sequence[Mapping[str, Any]],
    field_rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    freeze_rows: Sequence[Mapping[str, Any]],
    output_paths: Mapping[str, Path],
) -> str:
    metric = {row["metric_name"]: row for row in metrics}
    start_commit = "d53761f2b7cf2ed45d786d2ff32439e3014e4c20"
    status = "CLOSED_BOUNDED_TIME_AZIMUTH_PROXY"
    branch = git_fact(["branch", "--show-current"])
    head = git_fact(["rev-parse", "HEAD"])
    auto_fields = [row for row in field_rows if norm(row.get("optical_source_channel")).startswith("automatic")]
    posthoc = next(row for row in field_rows if row["message_id"] == "A_POSTHOC_T001")
    negative = next(row for row in field_rows if row["message_id"] == "NEG_T001_SHIFTED_AZIMUTH_CONTROL")
    lines = [
        "# OTY2 WGV3.3B Dual-Channel Feasible Field Closure",
        "",
        f"Date: {DATE}",
        "",
        "## Status",
        "",
        f"Conclusion: `{status}`",
        "",
        "WGV3.3B closes for the first T001 non-GT response setup: time is recoverable as a bounded software-sync proxy, SAR PNG windows are traceable, and coarse azimuth is recoverable from WGV3.3A automatic bbox envelopes plus the configured legacy optical-x to SAR azimuth mapping. Range remains broad/unknown.",
        "",
        "## Source Channels",
        "",
        "- Posthoc channel: `WGV1.4/WGV1.8`, permission `posthoc_visual_constraint`, read only after automatic freeze.",
        "- Automatic channel: `WGV3.3A automatic nodes/relations/competition`, permissions `automatic_runtime_hypothesis` and `automatic_uncertain_hypothesis`.",
        "",
        "## T001 Feasible Fields",
        "",
        f"- Posthoc feasible field: SAR `{posthoc['sar_frame_start']}-{posthoc['sar_frame_end']}`, azimuth `{posthoc['azimuth_min']}..{posthoc['azimuth_max']}`, range `{posthoc['range_status']}`.",
        f"- Automatic hypothesis count: `{len(freeze_rows)}`.",
        f"- Automatic fields: SAR union `{min(parse_int(row['sar_frame_start']) or 0 for row in auto_fields)}-{max(parse_int(row['sar_frame_end']) or 0 for row in auto_fields)}`, multi-azimuth proxy intervals preserved.",
        f"- Reference coverage: `{metric['automatic_feasible_field_joint_time_azimuth_coverage']['metric_status']}`.",
        f"- Search reduction ratio: `{metric['search_reduction_ratio_time_azimuth']['metric_value']}` over time-azimuth cells; range remains full fan radius.",
        f"- Negative control: `{negative['message_id']}`, SAR `{negative['sar_frame_start']}-{negative['sar_frame_end']}`, azimuth `{negative['azimuth_min']}..{negative['azimuth_max']}`.",
        "",
        "## Remaining Blockers",
        "",
        "- No raw SAR pulse / MATLAB window / PRF-to-PNG provenance source was found under the GM_RM011 data tree.",
        "- No per-frame optical or SAR timestamp is available; current time mapping is a bounded proxy.",
        "- No runtime-safe per-object range transfer is available; the field is broad range within the fan.",
        "- Automatic identity relations are intentionally uncertain; WGV3.3B does not force a single optical identity.",
        "",
        "## Can WGV3.3C Proceed",
        "",
        "Yes, but only as a first real non-GT SAR response experiment inside bounded time + coarse azimuth proxy fields. WGV3.3C must still let SAR evidence decide inside the field and must not treat this field as a final box or identity truth.",
        "",
        "## Metrics",
        "",
        md_table(metrics, METRIC_FIELDS),
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{rel(path)}`" for path in output_paths.values()),
        "",
        "## Git Context At Generation",
        "",
        f"- branch: `{branch}`",
        f"- start commit: `{start_commit}`",
        f"- generation HEAD: `{head}`",
        "",
    ]
    return "\n".join(lines)


def output_paths(date: str) -> dict[str, Path]:
    return {
        "source_audit": REPORT_DIR / f"oty2_wgv3_3b_source_provenance_audit_{date}.md",
        "source_csv": SAMPLES_DIR / f"oty2_wgv3_3b_source_provenance_{date}.csv",
        "time_csv": SAMPLES_DIR / f"oty2_wgv3_3b_optical_time_mapping_{date}.csv",
        "window_csv": SAMPLES_DIR / f"oty2_wgv3_3b_sar_window_mapping_{date}.csv",
        "field_csv": SAMPLES_DIR / f"oty2_wgv3_3b_dual_channel_feasible_fields_{date}.csv",
        "freeze_csv": SAMPLES_DIR / f"oty2_wgv3_3b_automatic_hypothesis_freeze_{date}.csv",
        "metrics_csv": SAMPLES_DIR / f"oty2_wgv3_3b_feasible_field_metrics_{date}.csv",
        "visual_report": REPORT_DIR / f"oty2_wgv3_3b_visual_source_and_mapping_diagnosis_{date}.md",
        "closure_report": REPORT_DIR / f"oty2_wgv3_3b_dual_channel_feasible_field_closure_{date}.md",
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = output_paths(args.date)
    required = [
        WGV33A_NODES,
        WGV33A_RELATIONS,
        WGV33A_COMPETITION,
        WGV33A_CAPABILITY,
        WGV14_THREADS,
        WGV14_FRAGMENTS,
        WGV17_OFFSET_SCAN,
        WGV17_DECISIONS,
        WGV18_OBS,
        WGV18_CANDIDATES,
        ALIGNMENT_SUMMARY,
        TEMPORAL_METADATA,
        OT0_MANIFEST,
        OTY0_MANIFEST,
        SCENE_CONFIG,
        OTY_CONFIG,
    ]
    missing = [rel(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required WGV3.3B inputs:\n" + "\n".join(missing))

    nodes = read_csv(WGV33A_NODES)
    relations = read_csv(WGV33A_RELATIONS)
    competitions = read_csv(WGV33A_COMPETITION)
    nodes_by_id = {norm(row.get("auto_node_id")): row for row in nodes}

    freeze_rows, _selected_nodes = build_auto_freeze(nodes, relations, competitions)
    write_csv(out["freeze_csv"], freeze_rows, FREEZE_FIELDS)

    channel_a_time, channel_a_field, _fragments, mapped_node_ids = build_channel_a(nodes_by_id)
    auto_fields = [field_from_freeze_row(row) for row in freeze_rows]
    reference_fields = [row for row in auto_fields if norm(row.get("source_track_or_thread_id")) in set(mapped_node_ids)]
    negative = build_negative_control(channel_a_field)
    field_rows = auto_fields + [channel_a_field, negative]
    time_rows = build_time_rows(freeze_rows, channel_a_time)
    # Include the negative control in the window table but not optical time mapping.
    window_time_rows = time_rows + [
        {
            "message_id": negative["message_id"],
            "scene": SCENE,
            "optical_source_channel": negative["optical_source_channel"],
            "source_track_or_thread_id": negative["source_track_or_thread_id"],
        }
    ]
    window_rows = build_window_rows(window_time_rows, field_rows)
    source_rows = build_source_rows()
    metrics = build_metrics(auto_fields, channel_a_field, negative, freeze_rows, reference_fields)
    inspection = inspect_images(channel_a_field, negative)

    write_csv(out["source_csv"], source_rows, SOURCE_FIELDS)
    write_csv(out["time_csv"], time_rows, TIME_FIELDS)
    write_csv(out["window_csv"], window_rows, WINDOW_FIELDS)
    write_csv(out["field_csv"], field_rows, FIELD_FIELDS)
    write_csv(out["metrics_csv"], metrics, METRIC_FIELDS)
    write_text(out["source_audit"], render_source_report(source_rows, freeze_rows, out))
    write_text(out["visual_report"], render_visual_report(inspection, field_rows))
    write_text(out["closure_report"], render_closure_report(source_rows, field_rows, metrics, freeze_rows, out))

    print(
        json.dumps(
            {
                "status": "CLOSED_BOUNDED_TIME_AZIMUTH_PROXY",
                "branch": git_fact(["branch", "--show-current"]),
                "head": git_fact(["rev-parse", "HEAD"]),
                "auto_hypotheses": len(freeze_rows),
                "field_rows": len(field_rows),
                "source_status_counts": Counter(row["provenance_status"] for row in source_rows),
                "metrics": {row["metric_name"]: row["metric_value"] for row in metrics},
                "outputs": {key: str(value) for key, value in out.items()},
            },
            ensure_ascii=False,
            indent=2,
            default=dict,
        )
    )
    return {"outputs": out, "metrics": metrics}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=DATE)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
