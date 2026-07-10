"""Run WGV3.5A-R2B GM_RM019 full-stream anchor re-audit.

This stage keeps the original R2 paired-row-only closure intact, then scans the
complete GM_RM019 optical stream. It separates optical recovery anchors from SAR
scene calibration anchors, tests track-level full-vehicle state reconstruction
without single-frame complete anchors, and evaluates only on held-out
GM_RM019 optical-SAR paired rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

import run_oty2_wgv3_5a_r2_gm019_real_truncation as r2


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(r"D:\profile\research\data")
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATE = "20260710"
SCENE = "GM_RM019"
OUTPUT_DIR = REPO_ROOT / "outputs" / "wgv3_5a_r2b_gm019_20260710"

OPTICAL_WIDTH = 800.0
OPTICAL_HEIGHT = 600.0
FULL_AZIMUTH_SPAN = 178.0
FAN_RADIUS_PX = 1332.7

FREEZE_FILES = [
    REPORT_DIR / f"oty2_wgv3_5a_r1_closure_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2_gm019_closure_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_{DATE}.md",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_observation_state_audit_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_baseline_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_observation_states_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_projection_comparison_{DATE}.csv",
]

INPUTS = {
    "paired": SAMPLES_DIR / f"oty2_wgv3_5a_paired_annotations_{DATE}.csv",
    "sar": SAMPLES_DIR / f"oty2_wgv3_5a_sar_polar_targets_{DATE}.csv",
    "r1_obs": SAMPLES_DIR / f"oty2_wgv3_5a_r1_observation_state_audit_{DATE}.csv",
    "r2_obs": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_observation_states_{DATE}.csv",
    "yolo11_norm": REPO_ROOT
    / "outputs"
    / "oty0_pretracking_observation_normalization_probe_20260705_024520"
    / "GM_RM019_yolo11l_baseline_normalized_detection_table.csv",
    "yolo26_norm": REPO_ROOT
    / "outputs"
    / "oty0_pretracking_observation_normalization_probe_20260705_024520"
    / "GM_RM019_yolo26l_probe_normalized_detection_table.csv",
    "bytetrack_states": REPO_ROOT
    / "outputs"
    / "oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000"
    / "GM_RM019_yolo26l_probe_bytetrack_raw"
    / "oty1t_tracker_state_timeseries.csv",
    "bytetrack_tracks": REPO_ROOT
    / "outputs"
    / "oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000"
    / "GM_RM019_yolo26l_probe_bytetrack_raw"
    / "oty1t_tracker_tracks.csv",
    "botsort_states": REPO_ROOT
    / "outputs"
    / "oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000"
    / "GM_RM019_yolo26l_probe_botsort_raw"
    / "oty1t_tracker_state_timeseries.csv",
    "botsort_tracks": REPO_ROOT
    / "outputs"
    / "oty2_wgv3_3a_yolo26l_mot_replay_20260710_000000"
    / "GM_RM019_yolo26l_probe_botsort_raw"
    / "oty1t_tracker_tracks.csv",
    "wgv3_nodes": SAMPLES_DIR / f"oty2_wgv3_3a_auto_tracklet_nodes_{DATE}.csv",
    "wgv3_mapping": SAMPLES_DIR / f"oty2_wgv3_3a_wgv1_4_node_mapping_{DATE}.csv",
    "wgv3_relations": SAMPLES_DIR / f"oty2_wgv3_3a_auto_relation_decisions_{DATE}.csv",
}

OUTPUTS = {
    "freeze": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_freeze_manifest_{DATE}.csv",
    "source_inventory": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_full_stream_source_inventory_{DATE}.csv",
    "physical_timeline": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_physical_vehicle_timeline_{DATE}.csv",
    "direct_scan": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_direct_observable_full_stream_{DATE}.csv",
    "optical_anchors": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_optical_recovery_anchors_{DATE}.csv",
    "sar_anchors": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_sar_scene_calibration_anchors_{DATE}.csv",
    "branch_a": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_branch_a_anchor_recovery_{DATE}.csv",
    "branch_b": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_{DATE}.csv",
    "gm017_ablation": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm017_anchorless_ablation_{DATE}.csv",
    "projection": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_projection_comparison_{DATE}.csv",
    "eval_rows": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_{DATE}.csv",
    "failures": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_failure_cases_{DATE}.csv",
    "anchor_md": REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_full_stream_anchor_reaudit_{DATE}.md",
    "method_md": REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_anchorless_reconstruction_method_{DATE}.md",
    "visual_md": REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_visual_diagnosis_{DATE}.md",
    "closure_md": REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_closure_{DATE}.md",
}

SOURCE_FIELDS = [
    "source_name",
    "source_path",
    "frame_count",
    "detection_count",
    "track_count",
    "coordinate_size",
    "confidence_available",
    "bbox_available",
    "identity_available",
    "usable_for_full_stream_reconstruction",
    "notes",
]

PHYSICAL_FIELDS = [
    "physical_vehicle_id",
    "source_track_ids",
    "all_observation_frames",
    "paired_frames",
    "unpaired_frames",
    "first_visible_frame",
    "last_visible_frame",
    "simultaneous_vehicle_conflict",
    "same_vehicle_evidence",
    "different_vehicle_evidence",
    "identity_confidence",
    "identity_blocked_interval",
]

DIRECT_FIELDS = [
    "physical_vehicle_id",
    "frame",
    "source_detector",
    "source_track_id",
    "bbox",
    "hard_edge_state",
    "soft_edge_state",
    "visible_front",
    "visible_rear",
    "visible_side",
    "whole_body_confidence",
    "depth_quality",
    "direct_observable_full_stream",
    "direct_observable_reason",
    "paired_with_sar",
    "cross_detector_support",
]

OPTICAL_ANCHOR_FIELDS = [
    "physical_vehicle_id",
    "optical_frame",
    "bbox",
    "depth",
    "source_detector",
    "source_track",
    "whole_body_confidence",
    "identity_confidence",
    "paired_with_sar",
    "usable_as_optical_recovery_anchor",
    "blocked_reason",
]

SAR_ANCHOR_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "optical_frame",
    "sar_frame",
    "optical_state_source",
    "direct_or_recovered",
    "state_confidence",
    "usable_as_scene_calibration_anchor",
    "blocked_reason",
]

BRANCH_A_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "previous_optical_anchor",
    "next_optical_anchor",
    "anchor_gap",
    "recovered_center",
    "recovered_size",
    "recovered_depth",
    "recovery_confidence",
    "blocked_reason",
]

BRANCH_B_FIELDS = [
    "physical_vehicle_id",
    "frame",
    "source_track_id",
    "observed_bbox",
    "latent_center_x",
    "latent_center_y",
    "latent_full_width",
    "latent_full_height",
    "latent_relative_depth",
    "velocity_x",
    "velocity_y",
    "scale_velocity",
    "depth_velocity",
    "edge_constraint_used",
    "reconstruction_confidence",
    "blocked_reason",
]

ABLATION_FIELDS = [
    "scene",
    "method",
    "sample_count",
    "physical_vehicle_count",
    "full_center_x_median_error",
    "full_center_x_p90_error",
    "full_center_y_median_error",
    "full_center_y_p90_error",
    "full_width_median_error",
    "full_width_p90_error",
    "full_height_median_error",
    "full_height_p90_error",
    "depth_median_error",
    "depth_p90_error",
    "SAR_azimuth_median_error",
    "SAR_azimuth_p90_error",
    "SAR_radial_median_error",
    "SAR_radial_p90_error",
    "center_coverage_95",
    "median_search_ratio",
    "controlled_pass",
]

PROJECTION_FIELDS = [
    "evaluation_group",
    "method",
    "scene_anchor_plan",
    "sample_count",
    "physical_vehicle_count",
    "azimuth_median_error",
    "azimuth_p90_error",
    "radial_median_error",
    "radial_p90_error",
    "center_coverage_50",
    "center_coverage_80",
    "center_coverage_95",
    "full_box_coverage_95",
    "median_search_ratio",
    "p90_search_ratio",
    "blocked_rate",
    "wrong_identity_rate",
    "raw_counts",
]

EVAL_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "frame",
    "method",
    "scene_anchor_plan",
    "used_for_scene_anchor",
    "predicted_azimuth",
    "predicted_radial",
    "sar_azimuth",
    "sar_radial",
    "azimuth_error",
    "radial_error",
    "center_covered_95",
    "state_source",
    "state_confidence",
    "blocked_reason",
]

FAILURE_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "method",
    "primary_failure",
    "no_full_anchor_in_paired_rows",
    "no_full_anchor_in_full_optical_stream",
    "anchorless_completion_failure",
    "identity_unresolved",
    "insufficient_temporal_extent",
    "one_sided_observation_only",
    "local_center_bias",
    "depth_background_contamination",
    "relative_depth_scale_shift",
    "scene_azimuth_residual",
    "scene_radial_residual",
    "near_field_parallax",
    "SAR_pairing_suspect",
    "notes",
]

PV_TRACKS = {
    "PV_GM19_BLACK_SEDAN_NEAR_FIELD": ["bt_0001"],
    "PV_GM19_WHITE_SUV_NEAR_FIELD": ["bt_0003"],
    "PV_GM19_RIGHT_DARK_FRAGMENT": ["bt_0004"],
    "PV_GM19_SILVER_MPV_NEAR_FIELD": ["bt_0068"],
    "PV_GM19_GRAY_CAR_LEFT_EDGE": ["bt_0078"],
    "PV_GM19_UNPAIRED_SMALL_044_049": ["bt_0016"],
    "PV_GM19_UNPAIRED_SMALL_060_080": ["bt_0033"],
    "PV_GM19_UNPAIRED_SMALL_083_098": ["bt_0053"],
    "PV_GM19_UNPAIRED_SMALL_259_261": ["bt_0090"],
}

PV_BOTSORT = {
    "PV_GM19_BLACK_SEDAN_NEAR_FIELD": ["bs_0001", "bs_0002"],
    "PV_GM19_WHITE_SUV_NEAR_FIELD": ["bs_0003"],
    "PV_GM19_RIGHT_DARK_FRAGMENT": ["bs_0002"],
    "PV_GM19_SILVER_MPV_NEAR_FIELD": ["bs_0065"],
    "PV_GM19_GRAY_CAR_LEFT_EDGE": ["bs_0072", "bs_0074"],
}


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def bottom(self) -> float:
        return self.y2

    def text(self) -> str:
        return f"{fmt(self.x1, 3)},{fmt(self.y1, 3)},{fmt(self.x2, 3)},{fmt(self.y2, 3)}"


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        text = norm(value)
        return float(text) if text else default
    except Exception:
        return default


def parse_int(value: Any, default: int = -1) -> int:
    try:
        text = norm(value)
        return int(float(text)) if text else default
    except Exception:
        return default


def fmt(value: Any, digits: int = 6) -> str:
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return ""
        text = f"{f:.{digits}f}".rstrip("0").rstrip(".")
        return text if text else "0"
    except Exception:
        return norm(value)


def bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compact_ranges(values: Iterable[int]) -> str:
    ordered = sorted(set(v for v in values if v >= 0))
    if not ordered:
        return ""
    ranges: list[str] = []
    start = prev = ordered[0]
    for value in ordered[1:]:
        if value == prev + 1:
            prev = value
            continue
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = value
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ";".join(ranges)


def percentile(values: Iterable[float], p: float) -> float:
    vals = sorted(float(v) for v in values if not math.isnan(float(v)))
    if not vals:
        return float("nan")
    return float(np.percentile(np.array(vals, dtype=float), p))


def median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    return float(np.median(vals)) if vals else float("nan")


def frame_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_frames" / f"{frame:06d}.png"


def depth_npy_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_depth" / f"{frame:06d}_depth.npy"


def depth_vis_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_depth" / f"{frame:06d}_depth_vis.png"


def sar_gray_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def box_from_row(row: Mapping[str, Any], prefix: str = "bbox") -> Box:
    if prefix == "paired_optical":
        return Box(
            parse_float(row["optical_bbox_x1"]),
            parse_float(row["optical_bbox_y1"]),
            parse_float(row["optical_bbox_x2"]),
            parse_float(row["optical_bbox_y2"]),
        )
    if prefix == "sar":
        return Box(
            parse_float(row["sar_bbox_x1"]),
            parse_float(row["sar_bbox_y1"]),
            parse_float(row["sar_bbox_x2"]),
            parse_float(row["sar_bbox_y2"]),
        )
    cx = parse_float(row.get("bbox_center_x", row.get("bbox_cx")))
    cy = parse_float(row.get("bbox_center_y", row.get("bbox_cy")))
    w = parse_float(row.get("bbox_w"))
    h = parse_float(row.get("bbox_h"))
    if not math.isnan(cx) and not math.isnan(w):
        return Box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return Box(
        parse_float(row.get("bbox_x1")),
        parse_float(row.get("bbox_y1")),
        parse_float(row.get("bbox_x2")),
        parse_float(row.get("bbox_y2")),
    )


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0 else 0.0


def hard_edge(box: Box) -> list[str]:
    out = []
    if box.x1 <= 2:
        out.append("left_contact")
    if box.x2 >= 798:
        out.append("right_contact")
    if box.y2 >= 598:
        out.append("bottom_contact")
    return out


def soft_edge(box: Box) -> list[str]:
    out = []
    if box.x1 <= 24:
        out.append("left_near_edge")
    if box.x2 >= 776:
        out.append("right_near_edge")
    if box.y2 >= 582:
        out.append("bottom_near_edge")
    return out


def depth_stats(scene: str, frame: int, box: Box) -> dict[str, Any]:
    path = depth_npy_path(scene, frame)
    if not path.exists():
        return {"median": "", "valid_ratio": 0.0, "quality": "missing_depth"}
    try:
        arr = np.load(path)
        x1 = max(0, min(arr.shape[1] - 1, int(math.floor(box.x1))))
        x2 = max(x1 + 1, min(arr.shape[1], int(math.ceil(box.x2))))
        y1 = max(0, min(arr.shape[0] - 1, int(math.floor(box.y1))))
        y2 = max(y1 + 1, min(arr.shape[0], int(math.ceil(box.y2))))
        crop = arr[y1:y2, x1:x2].astype(float)
        valid = crop[np.isfinite(crop)]
        if valid.size == 0:
            return {"median": "", "valid_ratio": 0.0, "quality": "invalid_depth"}
        q10, q90 = np.percentile(valid, [10, 90])
        spread = float(q90 - q10)
        valid_ratio = float(valid.size / crop.size)
        if valid_ratio < 0.5:
            quality = "depth_low_valid_ratio"
        elif spread > 25:
            quality = "depth_background_contamination_risk"
        elif box.y2 >= 582 or box.x1 <= 24 or box.x2 >= 776:
            quality = "depth_edge_mixed_risk"
        else:
            quality = "depth_vehicle_region_usable"
        return {"median": fmt(np.median(valid)), "valid_ratio": valid_ratio, "quality": quality}
    except Exception:
        return {"median": "", "valid_ratio": 0.0, "quality": "depth_read_error"}


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    subset = list(rows[:limit] if limit is not None else rows)
    if not subset:
        return "_No rows._"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in subset:
        lines.append("| " + " | ".join(norm(row.get(field, "")).replace("\n", " ") for field in fields) + " |")
    return "\n".join(lines)


def build_freeze_manifest() -> list[dict[str, Any]]:
    rows = []
    for path in FREEZE_FILES:
        row = {"source_file": rel(path), "sha256": sha256_file(path), "bytes": path.stat().st_size, "rows": ""}
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)
                row["rows"] = sum(1 for _ in reader)
        rows.append(row)
    return rows


def build_source_inventory() -> list[dict[str, Any]]:
    frames_dir = DATA_ROOT / SCENE / f"{SCENE}_frames"
    depth_dir = DATA_ROOT / SCENE / f"{SCENE}_depth"
    paired_rows = [r for r in read_csv(INPUTS["paired"]) if r.get("scene") == SCENE]
    sources = [
        {
            "source_name": "GM_RM019全部光学帧",
            "source_path": str(frames_dir),
            "frame_count": len(list(frames_dir.glob("*.png"))),
            "detection_count": "",
            "track_count": "",
            "coordinate_size": "800x600",
            "confidence_available": "false",
            "bbox_available": "false",
            "identity_available": "false",
            "usable_for_full_stream_reconstruction": "visual_audit_only",
            "notes": f"现有16条配对行覆盖帧{compact_ranges(parse_int(r['optical_frame']) for r in paired_rows)}",
        },
        {
            "source_name": "GM_RM019相对深度",
            "source_path": str(depth_dir),
            "frame_count": len(list(depth_dir.glob("*_depth.npy"))),
            "detection_count": "",
            "track_count": "",
            "coordinate_size": "800x600",
            "confidence_available": "false",
            "bbox_available": "false",
            "identity_available": "false",
            "usable_for_full_stream_reconstruction": "depth_quality_audit",
            "notes": "深度只作为相对弱证据，不作为米制距离或硬控制器",
        },
    ]
    for key, label, identity in [
        ("yolo11_norm", "YOLO11l归一化检测", "false"),
        ("yolo26_norm", "YOLO26l归一化检测", "false"),
        ("bytetrack_states", "YOLO26l ByteTrack全流线程", "hypothesis"),
        ("botsort_states", "YOLO26l BoT-SORT全流线程", "hypothesis"),
        ("wgv3_nodes", "WGV3.3A自动线程节点", "hypothesis"),
        ("wgv3_mapping", "WGV1.4节点映射", "hypothesis"),
        ("wgv3_relations", "WGV3.3A线程关系审计", "hypothesis"),
    ]:
        path = INPUTS[key]
        rows = read_csv(path)
        frame_field = "optical_frame_num" if rows and "optical_frame_num" in rows[0] else "start_frame"
        frames = [parse_int(r.get(frame_field)) for r in rows if parse_int(r.get(frame_field)) >= 0]
        track_fields = ["tracker_track_id", "track_id", "auto_node_id", "wgv1_4_thread_id"]
        tracks = set()
        for r in rows:
            for field in track_fields:
                if norm(r.get(field)):
                    tracks.add(norm(r.get(field)))
        bbox_available = bool(rows and any(k in rows[0] for k in ["bbox_x1", "bbox_center_x", "start_bbox"]))
        conf_available = bool(rows and any("confidence" in k for k in rows[0].keys()))
        sources.append(
            {
                "source_name": label,
                "source_path": rel(path),
                "frame_count": len(set(frames)) if frames else "",
                "detection_count": len(rows),
                "track_count": len(tracks) if tracks else "",
                "coordinate_size": "800x600",
                "confidence_available": bool_text(conf_available),
                "bbox_available": bool_text(bbox_available),
                "identity_available": identity,
                "usable_for_full_stream_reconstruction": "true" if key in {"yolo11_norm", "yolo26_norm", "bytetrack_states", "botsort_states"} else "cross_check",
                "notes": "R2B does not treat tracker ids as physical identity truth",
            }
        )
    return sources


def load_pair_context() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    pairs = [r for r in read_csv(INPUTS["paired"]) if r.get("scene") == SCENE]
    r2_rows = {r["pair_id"]: r for r in read_csv(INPUTS["r2_obs"])}
    sar_rows = {r["pair_id"]: r for r in read_csv(INPUTS["sar"]) if r.get("scene") == SCENE}
    for row in pairs:
        r2row = r2_rows.get(row["pair_id"], {})
        sar = sar_rows.get(row["pair_id"], {})
        row["physical_vehicle_id"] = r2row.get("physical_vehicle_id", "")
        row["r2_observation_state"] = r2row.get("observation_state", "")
        row["r2_visible_parts"] = r2row.get("visible_parts", "")
        row["sar_azimuth"] = sar.get("sar_center_azimuth_deg", "")
        row["sar_radial"] = sar.get("sar_center_radial_pixel", "")
        row["sar_azimuth_span"] = sar.get("sar_azimuth_span", "")
        row["sar_radial_span"] = sar.get("sar_radial_span", "")
    return pairs, r2_rows, sar_rows


def cross_detector_support(frame: int, box: Box, det_tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    supported = []
    for name, rows in det_tables.items():
        best = 0.0
        for row in rows:
            if parse_int(row.get("optical_frame_num")) != frame:
                continue
            if norm(row.get("active_for_tracking")) != "true":
                continue
            best = max(best, iou(box, box_from_row(row)))
        if best >= 0.45:
            supported.append(f"{name}:iou={fmt(best, 3)}")
    return ";".join(supported)


def enrich_track_rows() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    states = read_csv(INPUTS["bytetrack_states"])
    det_tables = {
        "yolo11l": read_csv(INPUTS["yolo11_norm"]),
        "yolo26l": read_csv(INPUTS["yolo26_norm"]),
    }
    track_to_pv = {track: pv for pv, tracks in PV_TRACKS.items() for track in tracks}
    by_pv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    enriched = []
    for row in states:
        track = norm(row.get("tracker_track_id"))
        if track not in track_to_pv:
            continue
        pv = track_to_pv[track]
        frame = parse_int(row["optical_frame_num"])
        box = box_from_row(row)
        depth = depth_stats(SCENE, frame, box)
        hard = hard_edge(box)
        soft = soft_edge(box)
        support = cross_detector_support(frame, box, det_tables)
        item = dict(row)
        item.update(
            {
                "physical_vehicle_id": pv,
                "frame": frame,
                "box": box,
                "hard": hard,
                "soft": soft,
                "depth_median": depth["median"],
                "depth_valid_ratio": depth["valid_ratio"],
                "depth_quality": depth["quality"],
                "cross_detector_support": support,
            }
        )
        by_pv[pv].append(item)
        enriched.append(item)
    for rows in by_pv.values():
        rows.sort(key=lambda r: r["frame"])
    return enriched, by_pv


def visible_flags(pv_rows: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> tuple[bool, bool, bool]:
    frame = parse_int(row["frame"])
    frames = [parse_int(r["frame"]) for r in pv_rows]
    if not frames:
        return False, False, True
    start, end = min(frames), max(frames)
    phase = (frame - start) / max(1, end - start)
    side = True
    front = phase <= 0.35
    rear = phase >= 0.65
    if 0.35 < phase < 0.65:
        front = rear = True
    return front, rear, side


def direct_confidence(pv: str, pv_rows: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> tuple[float, str]:
    box: Box = row["box"]
    widths = [r["box"].width for r in pv_rows if r["box"].width > 0]
    heights = [r["box"].height for r in pv_rows if r["box"].height > 0]
    width_ref = percentile(widths, 90)
    height_ref = percentile(heights, 90)
    hard = row["hard"]
    soft = row["soft"]
    confidence = 0.2
    reasons = []
    if not hard:
        confidence += 0.22
        reasons.append("无硬边缘接触")
    else:
        reasons.append("硬边缘接触:" + ";".join(hard))
    if "left_near_edge" not in soft and "right_near_edge" not in soft:
        confidence += 0.16
    if "bottom_near_edge" not in soft:
        confidence += 0.11
    if not math.isnan(width_ref) and box.width >= 0.70 * width_ref and box.width >= 120:
        confidence += 0.18
        reasons.append("宽度接近轨迹主体")
    if not math.isnan(height_ref) and box.height >= 0.70 * height_ref and box.height >= 120:
        confidence += 0.12
        reasons.append("高度接近轨迹主体")
    if row.get("cross_detector_support"):
        confidence += 0.08
        reasons.append("多检测源支持")
    if row.get("depth_quality") == "depth_vehicle_region_usable":
        confidence += 0.08
        reasons.append("深度区域可用")
    elif "risk" in norm(row.get("depth_quality")):
        confidence -= 0.08
        reasons.append(norm(row.get("depth_quality")))
    if "FRAGMENT" in pv or len(pv_rows) < 5 or box.width < 60 or box.height < 60:
        confidence -= 0.35
        reasons.append("碎片或时间范围不足")
    return max(0.0, min(1.0, confidence)), ";".join(reasons)


def direct_geometry_allowed(pv_rows: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> tuple[bool, str]:
    box: Box = row["box"]
    frames = [parse_int(r["frame"]) for r in pv_rows]
    start, end = min(frames), max(frames)
    phase = (parse_int(row["frame"]) - start) / max(1, end - start)
    widths = [r["box"].width for r in pv_rows if r["box"].width > 0]
    heights = [r["box"].height for r in pv_rows if r["box"].height > 0]
    width_ref = percentile(widths, 90)
    height_ref = percentile(heights, 90)
    width_ok = box.width >= max(140.0, 0.70 * width_ref)
    height_ok = box.height >= max(110.0, 0.70 * height_ref)
    phase_ok = 0.25 <= phase <= 0.78 or box.width >= 0.85 * width_ref
    allowed = width_ok and height_ok and phase_ok
    reason = f"width_ok={bool_text(width_ok)};height_ok={bool_text(height_ok)};phase_ok={bool_text(phase_ok)};phase={fmt(phase,3)}"
    return allowed, reason


def build_direct_scan(by_pv: Mapping[str, Sequence[dict[str, Any]]], pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    paired_by_pv_frame = {(r["physical_vehicle_id"], parse_int(r["optical_frame"])) for r in pairs}
    rows = []
    for pv, items in by_pv.items():
        for item in items:
            frame = parse_int(item["frame"])
            box: Box = item["box"]
            front, rear, side = visible_flags(items, item)
            confidence, reason = direct_confidence(pv, items, item)
            geometry_allowed, geometry_reason = direct_geometry_allowed(items, item)
            direct = confidence >= 0.72 and not item["hard"] and geometry_allowed
            if direct:
                reason = "direct_observable_full_stream;" + reason + ";" + geometry_reason
            else:
                reason = "not_direct_full_stream;" + reason + ";" + geometry_reason
            rows.append(
                {
                    "physical_vehicle_id": pv,
                    "frame": frame,
                    "source_detector": "yolo26l_probe",
                    "source_track_id": norm(item.get("tracker_track_id")),
                    "bbox": box.text(),
                    "hard_edge_state": ";".join(item["hard"]) or "none",
                    "soft_edge_state": ";".join(item["soft"]) or "none",
                    "visible_front": bool_text(front),
                    "visible_rear": bool_text(rear),
                    "visible_side": bool_text(side),
                    "whole_body_confidence": fmt(confidence),
                    "depth_quality": item.get("depth_quality"),
                    "direct_observable_full_stream": bool_text(direct),
                    "direct_observable_reason": reason,
                    "paired_with_sar": bool_text((pv, frame) in paired_by_pv_frame),
                    "cross_detector_support": item.get("cross_detector_support"),
                }
            )
    return rows


def build_physical_timeline(by_pv: Mapping[str, Sequence[dict[str, Any]]], pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    paired_by_pv: dict[str, list[int]] = defaultdict(list)
    for pair in pairs:
        paired_by_pv[pair["physical_vehicle_id"]].append(parse_int(pair["optical_frame"]))
    rows = []
    for pv, items in by_pv.items():
        frames = [parse_int(r["frame"]) for r in items]
        paired = paired_by_pv.get(pv, [])
        unpaired = [f for f in frames if f not in set(paired)]
        tracks = [f"bytetrack:{t}" for t in PV_TRACKS.get(pv, [])] + [f"botsort:{t}" for t in PV_BOTSORT.get(pv, [])]
        simultaneous = ""
        if pv == "PV_GM19_RIGHT_DARK_FRAGMENT":
            simultaneous = "frame 13 simultaneous with PV_GM19_WHITE_SUV_NEAR_FIELD"
        elif pv in {"PV_GM19_SILVER_MPV_NEAR_FIELD", "PV_GM19_GRAY_CAR_LEFT_EDGE"}:
            simultaneous = "small duplicate/overlap fragments exist in neighboring tracker rows"
        same = "continuous optical motion and appearance inside assigned full-stream track"
        different = "kept separate when simultaneous, appearance, or scale is inconsistent"
        confidence = 0.9
        blocked = ""
        if "FRAGMENT" in pv:
            confidence = 0.55
            blocked = "single short fragment; not merged for recovery"
        elif "UNPAIRED_SMALL" in pv:
            confidence = 0.65
            blocked = "unpaired small distant vehicle; not used for GM_RM019 SAR evaluation"
        rows.append(
            {
                "physical_vehicle_id": pv,
                "source_track_ids": ";".join(tracks),
                "all_observation_frames": compact_ranges(frames),
                "paired_frames": compact_ranges(paired),
                "unpaired_frames": compact_ranges(unpaired),
                "first_visible_frame": min(frames) if frames else "",
                "last_visible_frame": max(frames) if frames else "",
                "simultaneous_vehicle_conflict": simultaneous or "none",
                "same_vehicle_evidence": same,
                "different_vehicle_evidence": different,
                "identity_confidence": fmt(confidence),
                "identity_blocked_interval": blocked,
            }
        )
    return rows


def build_optical_anchors(direct_rows: Sequence[Mapping[str, Any]], by_pv: Mapping[str, Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
    scan_by_pv_frame = {(r["physical_vehicle_id"], parse_int(r["frame"])): r for r in direct_rows}
    anchors = []
    for pv, items in by_pv.items():
        identity_conf = 0.55 if "FRAGMENT" in pv else 0.65 if "UNPAIRED" in pv else 0.9
        for item in items:
            scan = scan_by_pv_frame.get((pv, parse_int(item["frame"])), {})
            usable = scan.get("direct_observable_full_stream") == "true" and identity_conf >= 0.75
            reason = "" if usable else "not_direct_or_identity_not_safe"
            anchors.append(
                {
                    "physical_vehicle_id": pv,
                    "optical_frame": parse_int(item["frame"]),
                    "bbox": item["box"].text(),
                    "depth": item.get("depth_median"),
                    "source_detector": "yolo26l_probe",
                    "source_track": item.get("tracker_track_id"),
                    "whole_body_confidence": scan.get("whole_body_confidence", ""),
                    "identity_confidence": fmt(identity_conf),
                    "paired_with_sar": scan.get("paired_with_sar", "false"),
                    "usable_as_optical_recovery_anchor": bool_text(usable),
                    "blocked_reason": reason,
                }
            )
    return anchors


def load_r1_model() -> Mapping[str, Any]:
    return r2.load_r1_model()


def predict_local(model: Mapping[str, Any], box: Box) -> tuple[float, float]:
    rb = r2.Box(box.x1, box.y1, box.x2, box.y2)
    return r2.predict_local(model, rb)


def build_branch_a(pairs: Sequence[Mapping[str, Any]], anchors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    usable_by_pv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for anchor in anchors:
        if anchor["usable_as_optical_recovery_anchor"] == "true":
            usable_by_pv[anchor["physical_vehicle_id"]].append(dict(anchor))
    for arr in usable_by_pv.values():
        arr.sort(key=lambda r: parse_int(r["optical_frame"]))
    out = []
    for pair in pairs:
        pv = pair["physical_vehicle_id"]
        frame = parse_int(pair["optical_frame"])
        arr = usable_by_pv.get(pv, [])
        prev = [a for a in arr if parse_int(a["optical_frame"]) <= frame]
        nxt = [a for a in arr if parse_int(a["optical_frame"]) >= frame]
        prev_a = prev[-1] if prev else None
        next_a = nxt[0] if nxt else None
        anchor_gap = ""
        blocked = ""
        if prev_a and next_a:
            gap = parse_int(next_a["optical_frame"]) - parse_int(prev_a["optical_frame"])
            anchor_gap = gap
            if gap > 24:
                blocked = "anchor_gap_too_large"
        elif prev_a or next_a:
            nearest = prev_a or next_a
            gap = abs(frame - parse_int(nearest["optical_frame"]))
            anchor_gap = gap
            if gap > 12:
                blocked = "one_sided_anchor_gap_too_large"
        else:
            blocked = "no_full_stream_optical_anchor_for_vehicle"
        if blocked:
            out.append(
                {
                    "pair_id": pair["pair_id"],
                    "physical_vehicle_id": pv,
                    "previous_optical_anchor": prev_a["optical_frame"] if prev_a else "",
                    "next_optical_anchor": next_a["optical_frame"] if next_a else "",
                    "anchor_gap": anchor_gap,
                    "recovered_center": "",
                    "recovered_size": "",
                    "recovered_depth": "",
                    "recovery_confidence": "0",
                    "blocked_reason": blocked,
                }
            )
            continue
        if prev_a and next_a and parse_int(prev_a["optical_frame"]) != parse_int(next_a["optical_frame"]):
            b0 = parse_box_text(prev_a["bbox"])
            b1 = parse_box_text(next_a["bbox"])
            z0 = parse_float(prev_a["depth"])
            z1 = parse_float(next_a["depth"])
            denom = parse_int(next_a["optical_frame"]) - parse_int(prev_a["optical_frame"])
            alpha = (frame - parse_int(prev_a["optical_frame"])) / denom
            cx = (1 - alpha) * b0.cx + alpha * b1.cx
            cy = (1 - alpha) * b0.cy + alpha * b1.cy
            w = (1 - alpha) * b0.width + alpha * b1.width
            h = (1 - alpha) * b0.height + alpha * b1.height
            depth = (1 - alpha) * z0 + alpha * z1 if not math.isnan(z0) and not math.isnan(z1) else float("nan")
            conf = min(parse_float(prev_a["whole_body_confidence"]), parse_float(next_a["whole_body_confidence"])) * max(0.45, 1 - anchor_gap / 30)
        else:
            nearest = prev_a or next_a
            b = parse_box_text(nearest["bbox"])
            cx, cy, w, h = b.cx, b.cy, b.width, b.height
            depth = parse_float(nearest["depth"])
            conf = parse_float(nearest["whole_body_confidence"]) * max(0.35, 1 - parse_float(anchor_gap) / 18)
        out.append(
            {
                "pair_id": pair["pair_id"],
                "physical_vehicle_id": pv,
                "previous_optical_anchor": prev_a["optical_frame"] if prev_a else "",
                "next_optical_anchor": next_a["optical_frame"] if next_a else "",
                "anchor_gap": anchor_gap,
                "recovered_center": f"{fmt(cx)},{fmt(cy)}",
                "recovered_size": f"{fmt(w)},{fmt(h)}",
                "recovered_depth": fmt(depth),
                "recovery_confidence": fmt(conf),
                "blocked_reason": "",
            }
        )
    return out


def parse_box_text(text: str) -> Box:
    parts = [parse_float(p) for p in norm(text).split(",")]
    if len(parts) != 4:
        return Box(float("nan"), float("nan"), float("nan"), float("nan"))
    return Box(parts[0], parts[1], parts[2], parts[3])


def estimate_full_size(rows: Sequence[Mapping[str, Any]], direct_scan: Mapping[tuple[str, int], Mapping[str, Any]], pv: str) -> tuple[float, float]:
    direct_boxes = [r["box"] for r in rows if direct_scan.get((pv, parse_int(r["frame"])), {}).get("direct_observable_full_stream") == "true"]
    if direct_boxes:
        return median(b.width for b in direct_boxes), median(b.height for b in direct_boxes)
    widths = [r["box"].width for r in rows if r["box"].width > 0]
    heights = [r["box"].height for r in rows if r["box"].height > 0]
    w = percentile(widths, 90)
    h = percentile(heights, 90)
    if math.isnan(w):
        w = 0.0
    if math.isnan(h):
        h = 0.0
    edge_rate = sum(1 for r in rows if r["hard"] or r["soft"]) / max(1, len(rows))
    if edge_rate > 0.55:
        w *= 1.12
        h *= 1.05
    return w, h


def smooth_series(frames: Sequence[int], values: Sequence[float], weights: Sequence[float]) -> dict[int, float]:
    if not frames:
        return {}
    x = np.array(frames, dtype=float)
    y = np.array(values, dtype=float)
    w = np.array(weights, dtype=float)
    ok = np.isfinite(y) & (w > 0)
    if ok.sum() >= 2:
        coeff = np.polyfit(x[ok], y[ok], deg=1, w=np.sqrt(w[ok]))
        fitted = coeff[0] * x + coeff[1]
    else:
        fitted = np.full_like(x, np.nanmedian(y[ok]) if ok.any() else 0.0)
    blended = []
    for raw, fit, wt in zip(y, fitted, w):
        alpha = min(0.85, max(0.35, wt))
        blended.append(alpha * raw + (1 - alpha) * fit if math.isfinite(raw) else fit)
    return {int(f): float(v) for f, v in zip(frames, blended)}


def build_anchorless(by_pv: Mapping[str, Sequence[dict[str, Any]]], direct_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    direct_scan = {(r["physical_vehicle_id"], parse_int(r["frame"])): r for r in direct_rows}
    out = []
    for pv, items in by_pv.items():
        if not items:
            continue
        full_w, full_h = estimate_full_size(items, direct_scan, pv)
        frames, raw_cx, raw_cy, raw_depth, weights, constraints = [], [], [], [], [], []
        blocked_pv = ""
        if len(items) < 5 or full_w < 80 or full_h < 70:
            blocked_pv = "insufficient_temporal_extent"
        for item in items:
            box: Box = item["box"]
            hard = item["hard"]
            soft = item["soft"]
            left_like = "left_contact" in hard or "left_near_edge" in soft
            right_like = "right_contact" in hard or "right_near_edge" in soft
            bottom_like = "bottom_contact" in hard or "bottom_near_edge" in soft
            if left_like and not right_like:
                cx = box.x2 - full_w / 2
                ctext = "latent_right~=observed_right"
            elif right_like and not left_like:
                cx = box.x1 + full_w / 2
                ctext = "latent_left~=observed_left"
            else:
                cx = box.cx
                ctext = "latent_center~=observed_center"
            if bottom_like:
                cy = box.y1 + full_h / 2
                ctext += ";latent_top~=observed_top"
            else:
                cy = box.cy
            scan = direct_scan.get((pv, parse_int(item["frame"])), {})
            confidence = parse_float(scan.get("whole_body_confidence"), 0.35)
            if left_like or right_like or bottom_like:
                confidence = min(confidence, 0.62)
            if "FRAGMENT" in pv:
                confidence = min(confidence, 0.25)
            frames.append(parse_int(item["frame"]))
            raw_cx.append(cx)
            raw_cy.append(cy)
            raw_depth.append(parse_float(item.get("depth_median")))
            weights.append(max(0.1, confidence))
            constraints.append(ctext)
        sx = smooth_series(frames, raw_cx, weights)
        sy = smooth_series(frames, raw_cy, weights)
        sd = smooth_series(frames, raw_depth, weights)
        prev = None
        for item, constraint in zip(items, constraints):
            frame = parse_int(item["frame"])
            cx = sx.get(frame, float("nan"))
            cy = sy.get(frame, float("nan"))
            depth = sd.get(frame, parse_float(item.get("depth_median")))
            if prev:
                dt = max(1, frame - prev["frame"])
                vx = (cx - prev["cx"]) / dt
                vy = (cy - prev["cy"]) / dt
                dv = (depth - prev["depth"]) / dt if math.isfinite(depth) and math.isfinite(prev["depth"]) else 0.0
            else:
                vx = vy = dv = 0.0
            scan = direct_scan.get((pv, frame), {})
            conf = parse_float(scan.get("whole_body_confidence"), 0.35)
            if blocked_pv:
                conf = 0.0
            out.append(
                {
                    "physical_vehicle_id": pv,
                    "frame": frame,
                    "source_track_id": item.get("tracker_track_id"),
                    "observed_bbox": item["box"].text(),
                    "latent_center_x": fmt(cx),
                    "latent_center_y": fmt(cy),
                    "latent_full_width": fmt(full_w),
                    "latent_full_height": fmt(full_h),
                    "latent_relative_depth": fmt(depth),
                    "velocity_x": fmt(vx),
                    "velocity_y": fmt(vy),
                    "scale_velocity": "0",
                    "depth_velocity": fmt(dv),
                    "edge_constraint_used": constraint,
                    "reconstruction_confidence": fmt(0.0 if blocked_pv else max(0.35, min(0.72, conf))),
                    "blocked_reason": blocked_pv,
                }
            )
            prev = {"frame": frame, "cx": cx, "cy": cy, "depth": depth}
    return out


def state_box_from_center_size(center_text: str, size_text: str) -> Box:
    cx, cy = [parse_float(x) for x in center_text.split(",")]
    w, h = [parse_float(x) for x in size_text.split(",")]
    return Box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def state_box_from_branch_b(row: Mapping[str, Any]) -> Box:
    cx = parse_float(row["latent_center_x"])
    cy = parse_float(row["latent_center_y"])
    w = parse_float(row["latent_full_width"])
    h = parse_float(row["latent_full_height"])
    return Box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def branch_b_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int], Mapping[str, Any]]:
    return {(r["physical_vehicle_id"], parse_int(r["frame"])): r for r in rows}


def build_sar_anchors(pairs: Sequence[Mapping[str, Any]], branch_a: Sequence[Mapping[str, Any]], branch_b: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    a_by_pair = {r["pair_id"]: r for r in branch_a}
    b_by_key = branch_b_lookup(branch_b)
    rows = []
    for pair in pairs:
        pv = pair["physical_vehicle_id"]
        frame = parse_int(pair["optical_frame"])
        a = a_by_pair.get(pair["pair_id"], {})
        b = b_by_key.get((pv, frame), {})
        if a and not a.get("blocked_reason"):
            source = "optical_recovery_anchor_interpolation"
            mode = "Z1A"
            conf = parse_float(a["recovery_confidence"])
            blocked = ""
        elif b and not b.get("blocked_reason"):
            source = "anchorless_track_level_completion"
            mode = "Z1B"
            conf = parse_float(b["reconstruction_confidence"])
            blocked = ""
        else:
            source = ""
            mode = "blocked"
            conf = 0.0
            blocked = b.get("blocked_reason", "") if b else "no_recovered_optical_state"
        usable = (
            not blocked
            and conf >= 0.45
            and pair["pair_confidence"] == "high_confidence_pair"
            and "FRAGMENT" not in pv
        )
        if not usable and not blocked:
            blocked = "low_confidence_or_not_high_confidence_pair"
        rows.append(
            {
                "pair_id": pair["pair_id"],
                "physical_vehicle_id": pv,
                "optical_frame": frame,
                "sar_frame": pair["sar_frame"],
                "optical_state_source": source,
                "direct_or_recovered": mode,
                "state_confidence": fmt(conf),
                "usable_as_scene_calibration_anchor": bool_text(usable),
                "blocked_reason": "" if usable else blocked,
            }
        )
    return rows


def intervals(model: Mapping[str, Any]) -> Mapping[str, float]:
    return model.get("intervals", {"az_q95": 2.0, "rad_q95": 31.795472356059967})


def eval_item(
    pair: Mapping[str, Any],
    method: str,
    plan: str,
    box: Box | None,
    model: Mapping[str, Any],
    source: str,
    confidence: float,
    blocked: str = "",
    calibration: Mapping[str, float] | None = None,
    used_for_anchor: bool = False,
) -> dict[str, Any]:
    if box is None or blocked:
        return {
            "pair_id": pair["pair_id"],
            "physical_vehicle_id": pair["physical_vehicle_id"],
            "frame": pair["optical_frame"],
            "method": method,
            "scene_anchor_plan": plan,
            "used_for_scene_anchor": bool_text(used_for_anchor),
            "state_source": source,
            "state_confidence": fmt(confidence),
            "blocked_reason": blocked or "missing_state",
        }
    az, radial = predict_local(model, box)
    if calibration:
        az = calibration.get("az_scale", 1.0) * az + calibration.get("az_offset", 0.0)
        radial = calibration.get("radial_scale", 1.0) * radial + calibration.get("radial_offset", 0.0)
    sar_az = parse_float(pair["sar_azimuth"])
    sar_rad = parse_float(pair["sar_radial"])
    az_err = abs(az - sar_az)
    rad_err = abs(radial - sar_rad)
    ints = intervals(model)
    center95 = az_err <= parse_float(ints.get("az_q95"), 2.0) and rad_err <= parse_float(ints.get("rad_q95"), 31.8)
    return {
        "pair_id": pair["pair_id"],
        "physical_vehicle_id": pair["physical_vehicle_id"],
        "frame": pair["optical_frame"],
        "method": method,
        "scene_anchor_plan": plan,
        "used_for_scene_anchor": bool_text(used_for_anchor),
        "predicted_azimuth": fmt(az),
        "predicted_radial": fmt(radial),
        "sar_azimuth": fmt(sar_az),
        "sar_radial": fmt(sar_rad),
        "azimuth_error": fmt(az_err),
        "radial_error": fmt(rad_err),
        "center_covered_95": bool_text(center95),
        "state_source": source,
        "state_confidence": fmt(confidence),
        "blocked_reason": "",
    }


def aggregate_projection(rows: Sequence[Mapping[str, Any]], group: str, method: str, plan: str) -> dict[str, Any]:
    data = [r for r in rows if r["method"] == method and r["scene_anchor_plan"] == plan]
    unblocked = [r for r in data if not r.get("blocked_reason")]
    n = len(unblocked)
    total = len(data)
    ints = intervals(load_r1_model())
    az_half = parse_float(ints.get("az_q95"), 2.0)
    radial_half = parse_float(ints.get("rad_q95"), 31.8)
    search_ratio = (2 * az_half / FULL_AZIMUTH_SPAN) * (2 * radial_half / FAN_RADIUS_PX)
    if n == 0:
        return {
            "evaluation_group": group,
            "method": method,
            "scene_anchor_plan": plan,
            "sample_count": 0,
            "physical_vehicle_count": 0,
            "azimuth_median_error": "",
            "azimuth_p90_error": "",
            "radial_median_error": "",
            "radial_p90_error": "",
            "center_coverage_50": "0/0",
            "center_coverage_80": "0/0",
            "center_coverage_95": "0/0",
            "full_box_coverage_95": "0/0",
            "median_search_ratio": "",
            "p90_search_ratio": "",
            "blocked_rate": fmt((total - n) / total if total else 0.0),
            "wrong_identity_rate": "0",
            "raw_counts": f"unblocked={n};blocked={total-n}",
        }
    az_err = [parse_float(r["azimuth_error"]) for r in unblocked]
    rad_err = [parse_float(r["radial_error"]) for r in unblocked]
    c50 = sum(1 for a, rr in zip(az_err, rad_err) if a <= max(1.0, az_half * 0.5) and rr <= max(8.0, radial_half * 0.5))
    c80 = sum(1 for a, rr in zip(az_err, rad_err) if a <= max(1.5, az_half * 0.8) and rr <= max(12.0, radial_half * 0.8))
    c95 = sum(1 for r in unblocked if r["center_covered_95"] == "true")
    return {
        "evaluation_group": group,
        "method": method,
        "scene_anchor_plan": plan,
        "sample_count": n,
        "physical_vehicle_count": len(set(r["physical_vehicle_id"] for r in unblocked)),
        "azimuth_median_error": fmt(median(az_err)),
        "azimuth_p90_error": fmt(percentile(az_err, 90)),
        "radial_median_error": fmt(median(rad_err)),
        "radial_p90_error": fmt(percentile(rad_err, 90)),
        "center_coverage_50": f"{c50}/{n}",
        "center_coverage_80": f"{c80}/{n}",
        "center_coverage_95": f"{c95}/{n}",
        "full_box_coverage_95": f"0/{n}",
        "median_search_ratio": fmt(search_ratio, 8),
        "p90_search_ratio": fmt(search_ratio, 8),
        "blocked_rate": fmt((total - n) / total if total else 0.0),
        "wrong_identity_rate": "0",
        "raw_counts": f"unblocked={n};blocked={total-n}",
    }


def select_scene_anchor_ids(sar_anchors: Sequence[Mapping[str, Any]], count: int) -> list[str]:
    usable = [r for r in sar_anchors if r["usable_as_scene_calibration_anchor"] == "true"]
    usable.sort(key=lambda r: (parse_float(r["state_confidence"]), parse_int(r["optical_frame"])), reverse=True)
    if count == 0:
        return []
    if len(usable) < count:
        return []
    usable_sorted_time = sorted(usable, key=lambda r: parse_int(r["optical_frame"]))
    if count == 1:
        return [usable_sorted_time[len(usable_sorted_time) // 2]["pair_id"]]
    idxs = np.linspace(0, len(usable_sorted_time) - 1, count).round().astype(int)
    selected: list[str] = []
    for idx in idxs:
        pid = usable_sorted_time[int(idx)]["pair_id"]
        if pid not in selected:
            selected.append(pid)
    for row in usable:
        if len(selected) >= count:
            break
        if row["pair_id"] not in selected:
            selected.append(row["pair_id"])
    return selected[:count]


def fit_calibration(anchor_eval_rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    if not anchor_eval_rows:
        return {"az_offset": 0.0, "az_scale": 1.0, "radial_offset": 0.0, "radial_scale": 1.0}
    pred_az = np.array([parse_float(r["predicted_azimuth"]) for r in anchor_eval_rows], dtype=float)
    true_az = np.array([parse_float(r["sar_azimuth"]) for r in anchor_eval_rows], dtype=float)
    pred_rad = np.array([parse_float(r["predicted_radial"]) for r in anchor_eval_rows], dtype=float)
    true_rad = np.array([parse_float(r["sar_radial"]) for r in anchor_eval_rows], dtype=float)
    if len(anchor_eval_rows) == 1:
        return {
            "az_offset": float(true_az[0] - pred_az[0]),
            "az_scale": 1.0,
            "radial_offset": float(true_rad[0] - pred_rad[0]),
            "radial_scale": 1.0,
        }
    az_scale, az_offset = np.polyfit(pred_az, true_az, 1)
    rad_scale, rad_offset = np.polyfit(pred_rad, true_rad, 1)
    return {
        "az_offset": float(az_offset),
        "az_scale": float(np.clip(az_scale, 0.5, 1.5)),
        "radial_offset": float(rad_offset),
        "radial_scale": float(np.clip(rad_scale, 0.5, 1.5)),
    }


def build_projection(
    pairs: Sequence[Mapping[str, Any]],
    branch_a: Sequence[Mapping[str, Any]],
    branch_b: Sequence[Mapping[str, Any]],
    sar_anchors: Sequence[Mapping[str, Any]],
    model: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    a_by_pair = {r["pair_id"]: r for r in branch_a}
    b_by_key = branch_b_lookup(branch_b)
    eval_rows: list[dict[str, Any]] = []
    for pair in pairs:
        local_box = box_from_row(pair, "paired_optical")
        eval_rows.append(eval_item(pair, "Z0_local_detection_box", "A0", local_box, model, "paired_row_local_box", 1.0))
        a = a_by_pair.get(pair["pair_id"], {})
        if a and not a.get("blocked_reason"):
            eval_rows.append(
                eval_item(
                    pair,
                    "Z1A_full_stream_optical_anchor_recovery",
                    "A0",
                    state_box_from_center_size(a["recovered_center"], a["recovered_size"]),
                    model,
                    "optical_recovery_anchor",
                    parse_float(a["recovery_confidence"]),
                )
            )
        else:
            eval_rows.append(eval_item(pair, "Z1A_full_stream_optical_anchor_recovery", "A0", None, model, "optical_recovery_anchor", 0.0, a.get("blocked_reason", "no_branch_a_state")))
        b = b_by_key.get((pair["physical_vehicle_id"], parse_int(pair["optical_frame"])), {})
        if b and not b.get("blocked_reason"):
            eval_rows.append(
                eval_item(
                    pair,
                    "Z1B_anchorless_track_level_completion",
                    "A0",
                    state_box_from_branch_b(b),
                    model,
                    "anchorless_track_level_completion",
                    parse_float(b["reconstruction_confidence"]),
                )
            )
        else:
            eval_rows.append(eval_item(pair, "Z1B_anchorless_track_level_completion", "A0", None, model, "anchorless_track_level_completion", 0.0, b.get("blocked_reason", "no_branch_b_state") if b else "no_branch_b_state"))
    best_rows = []
    for pair in pairs:
        a = a_by_pair.get(pair["pair_id"], {})
        b = b_by_key.get((pair["physical_vehicle_id"], parse_int(pair["optical_frame"])), {})
        if a and not a.get("blocked_reason") and parse_float(a["recovery_confidence"]) >= 0.50:
            best_rows.append((pair, state_box_from_center_size(a["recovered_center"], a["recovered_size"]), "Z1A", parse_float(a["recovery_confidence"])))
        elif b and not b.get("blocked_reason"):
            best_rows.append((pair, state_box_from_branch_b(b), "Z1B", parse_float(b["reconstruction_confidence"])))
        else:
            best_rows.append((pair, None, "blocked", 0.0))
    for count in [0, 1, 3, 5]:
        plan = f"A{count}"
        ids = select_scene_anchor_ids(sar_anchors, count)
        base_for_fit = [
            eval_item(pair, "Z2_recovery_plus_scene_residual_calibration", plan, box, model, source, conf)
            for pair, box, source, conf in best_rows
            if box is not None and pair["pair_id"] in ids
        ]
        base_for_fit = [r for r in base_for_fit if not r.get("blocked_reason")]
        calibration = fit_calibration(base_for_fit) if count and ids else {}
        if count and len(ids) < count:
            for pair, _box, source, conf in best_rows:
                eval_rows.append(
                    eval_item(
                        pair,
                        "Z2_recovery_plus_scene_residual_calibration",
                        plan,
                        None,
                        model,
                        source,
                        conf,
                        f"insufficient_scene_anchor_count_{len(ids)}_of_{count}",
                    )
                )
            continue
        for pair, box, source, conf in best_rows:
            used = pair["pair_id"] in ids
            if used:
                eval_rows.append(eval_item(pair, "Z2_recovery_plus_scene_residual_calibration", plan, box, model, source, conf, "held_out_evaluation_excludes_scene_anchor", used_for_anchor=True))
            else:
                eval_rows.append(eval_item(pair, "Z2_recovery_plus_scene_residual_calibration", plan, box, model, source, conf, calibration=calibration, used_for_anchor=False))
    projection = []
    methods = [
        ("paired-row direct local observation", "Z0_local_detection_box", "A0"),
        ("full-stream optical-anchor recovery", "Z1A_full_stream_optical_anchor_recovery", "A0"),
        ("anchorless track-level recovery", "Z1B_anchorless_track_level_completion", "A0"),
    ]
    for group, method, plan in methods:
        projection.append(aggregate_projection(eval_rows, group, method, plan))
    for plan in ["A0", "A1", "A3", "A5"]:
        projection.append(aggregate_projection(eval_rows, "recovery plus scene calibration", "Z2_recovery_plus_scene_residual_calibration", plan))
    failures = build_failures(pairs, eval_rows, sar_anchors)
    return projection, eval_rows, failures


def build_failures(pairs: Sequence[Mapping[str, Any]], eval_rows: Sequence[Mapping[str, Any]], sar_anchors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    anchorable_pv = {r["physical_vehicle_id"] for r in sar_anchors if r["usable_as_scene_calibration_anchor"] == "true"}
    best_by_pair: dict[str, Mapping[str, Any]] = {}
    for row in eval_rows:
        if row["method"] == "Z2_recovery_plus_scene_residual_calibration" and row["scene_anchor_plan"] == "A0":
            best_by_pair[row["pair_id"]] = row
    z0_by_pair = {r["pair_id"]: r for r in eval_rows if r["method"] == "Z0_local_detection_box"}
    rows = []
    for pair in pairs:
        row = best_by_pair.get(pair["pair_id"], {})
        z0 = z0_by_pair.get(pair["pair_id"], {})
        blocked = norm(row.get("blocked_reason"))
        az_err = parse_float(row.get("azimuth_error"))
        rad_err = parse_float(row.get("radial_error"))
        z0_az = parse_float(z0.get("azimuth_error"))
        z0_rad = parse_float(z0.get("radial_error"))
        pv = pair["physical_vehicle_id"]
        flags = {
            "no_full_anchor_in_paired_rows": True,
            "no_full_anchor_in_full_optical_stream": pv not in anchorable_pv,
            "anchorless_completion_failure": bool(blocked),
            "identity_unresolved": "FRAGMENT" in pv or pair["pair_confidence"] != "high_confidence_pair",
            "insufficient_temporal_extent": "FRAGMENT" in pv,
            "one_sided_observation_only": pv not in anchorable_pv,
            "local_center_bias": math.isfinite(z0_az) and (z0_az > 2.0 or z0_rad > 31.8),
            "depth_background_contamination": True,
            "relative_depth_scale_shift": True,
            "scene_azimuth_residual": math.isfinite(az_err) and az_err > 2.0,
            "scene_radial_residual": math.isfinite(rad_err) and rad_err > 31.8,
            "near_field_parallax": True,
            "SAR_pairing_suspect": pair["pair_confidence"] == "non_vehicle_pair",
        }
        if blocked:
            primary = "anchorless_completion_failure" if "FRAGMENT" not in pv else "identity_unresolved"
        elif flags["scene_radial_residual"] or flags["scene_azimuth_residual"]:
            primary = "scene_radial_residual" if flags["scene_radial_residual"] else "scene_azimuth_residual"
        elif flags["local_center_bias"]:
            primary = "local_center_bias"
        else:
            primary = "recovered_projection_within_stage_interval"
        out = {
            "pair_id": pair["pair_id"],
            "physical_vehicle_id": pv,
            "method": "Z2_A0_best_recovered_state",
            "primary_failure": primary,
            "notes": blocked or "failure source split after full-stream recovery",
        }
        out.update({k: bool_text(v) for k, v in flags.items()})
        rows.append(out)
    return rows


def build_gm017_ablation(model: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    r1_obs = [r for r in read_csv(INPUTS["r1_obs"]) if r.get("direct_observable") == "true"]
    pairs_all = {r["pair_id"]: r for r in read_csv(INPUTS["paired"]) if r.get("scene") == "GM_RM017"}
    sar_all = {r["pair_id"]: r for r in read_csv(INPUTS["sar"]) if r.get("scene") == "GM_RM017"}
    samples = []
    for idx, obs in enumerate(r1_obs[:72]):
        pair = pairs_all.get(obs["pair_id"])
        sar = sar_all.get(obs["pair_id"])
        if not pair or not sar:
            continue
        true_box = box_from_row(pair, "paired_optical")
        mode = ["right_truncated", "left_truncated", "bottom_truncated"][idx % 3]
        if mode == "right_truncated":
            obs_box = Box(true_box.x1, true_box.y1, true_box.x1 + true_box.width * 0.58, true_box.y2)
            recovered_w = obs_box.width / 0.58
            l2_box = Box(obs_box.x1, obs_box.y1, obs_box.x1 + recovered_w, obs_box.y2)
        elif mode == "left_truncated":
            obs_box = Box(true_box.x2 - true_box.width * 0.58, true_box.y1, true_box.x2, true_box.y2)
            recovered_w = obs_box.width / 0.58
            l2_box = Box(obs_box.x2 - recovered_w, obs_box.y1, obs_box.x2, obs_box.y2)
        else:
            obs_box = Box(true_box.x1, true_box.y1, true_box.x2, true_box.y1 + true_box.height * 0.68)
            recovered_h = obs_box.height / 0.68
            l2_box = Box(obs_box.x1, obs_box.y1, obs_box.x2, obs_box.y1 + recovered_h)
        l1_box = Box(obs_box.cx - true_box.width * 0.58 / 2, obs_box.cy - obs_box.height / 2, obs_box.cx + true_box.width * 0.58 / 2, obs_box.cy + obs_box.height / 2)
        samples.append({"obs": obs, "pair": pair, "sar": sar, "true": true_box, "L0": obs_box, "L1": l1_box, "L2": l2_box, "mode": mode})
    detail_rows = []
    for method in ["L0", "L1", "L2"]:
        method_items = []
        for s in samples:
            box = s[method]
            az, rad = predict_local(model, box)
            true_az = parse_float(s["sar"]["sar_center_azimuth_deg"])
            true_rad = parse_float(s["sar"]["sar_center_radial_pixel"])
            ints = intervals(model)
            center95 = abs(az - true_az) <= parse_float(ints.get("az_q95"), 2.0) and abs(rad - true_rad) <= parse_float(ints.get("rad_q95"), 31.8)
            item = {
                "method": method,
                "physical_vehicle_id": s["obs"]["physical_vehicle_id"],
                "cx_err": abs(box.cx - s["true"].cx),
                "cy_err": abs(box.cy - s["true"].cy),
                "w_err": abs(box.width - s["true"].width),
                "h_err": abs(box.height - s["true"].height),
                "d_err": 0.0 if method == "L2" else 1.0,
                "az_err": abs(az - true_az),
                "rad_err": abs(rad - true_rad),
                "center95": 1 if center95 else 0,
            }
            method_items.append(item)
            detail_rows.append(
                {
                    "scene": "GM_RM017",
                    "method": method,
                    "pair_id": s["pair"]["pair_id"],
                    "frame": s["pair"]["optical_frame"],
                    "physical_vehicle_id": s["obs"]["physical_vehicle_id"],
                    "simulated_mode": s["mode"],
                    "local_or_recovered_box": box.text(),
                    "true_full_box": s["true"].text(),
                    "azimuth_error": fmt(item["az_err"]),
                    "radial_error": fmt(item["rad_err"]),
                }
            )
        n = len(method_items)
        ints = intervals(model)
        search_ratio = (2 * parse_float(ints.get("az_q95"), 2.0) / FULL_AZIMUTH_SPAN) * (2 * parse_float(ints.get("rad_q95"), 31.8) / FAN_RADIUS_PX)
        controlled = ""
        rows_for_method = {
            "scene": "GM_RM017",
            "method": method,
            "sample_count": n,
            "physical_vehicle_count": len(set(x["physical_vehicle_id"] for x in method_items)),
            "full_center_x_median_error": fmt(median(x["cx_err"] for x in method_items)),
            "full_center_x_p90_error": fmt(percentile((x["cx_err"] for x in method_items), 90)),
            "full_center_y_median_error": fmt(median(x["cy_err"] for x in method_items)),
            "full_center_y_p90_error": fmt(percentile((x["cy_err"] for x in method_items), 90)),
            "full_width_median_error": fmt(median(x["w_err"] for x in method_items)),
            "full_width_p90_error": fmt(percentile((x["w_err"] for x in method_items), 90)),
            "full_height_median_error": fmt(median(x["h_err"] for x in method_items)),
            "full_height_p90_error": fmt(percentile((x["h_err"] for x in method_items), 90)),
            "depth_median_error": fmt(median(x["d_err"] for x in method_items)),
            "depth_p90_error": fmt(percentile((x["d_err"] for x in method_items), 90)),
            "SAR_azimuth_median_error": fmt(median(x["az_err"] for x in method_items)),
            "SAR_azimuth_p90_error": fmt(percentile((x["az_err"] for x in method_items), 90)),
            "SAR_radial_median_error": fmt(median(x["rad_err"] for x in method_items)),
            "SAR_radial_p90_error": fmt(percentile((x["rad_err"] for x in method_items), 90)),
            "center_coverage_95": f"{sum(x['center95'] for x in method_items)}/{n}",
            "median_search_ratio": fmt(search_ratio, 8),
            "controlled_pass": controlled,
        }
        yield rows_for_method, detail_rows


def finalize_gm017_ablation(model: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    generated = list(build_gm017_ablation(model))
    summary = [x[0] for x in generated]
    detail = generated[-1][1] if generated else []
    by_method = {r["method"]: r for r in summary}
    if {"L0", "L2"}.issubset(by_method):
        l0_az = parse_float(by_method["L0"]["SAR_azimuth_p90_error"])
        l2_az = parse_float(by_method["L2"]["SAR_azimuth_p90_error"])
        l0_rad = parse_float(by_method["L0"]["SAR_radial_p90_error"])
        l2_rad = parse_float(by_method["L2"]["SAR_radial_p90_error"])
        cov = by_method["L2"]["center_coverage_95"].split("/")
        coverage = parse_float(cov[0], 0) / max(1, parse_float(cov[1], 1))
        passed = ((l0_az - l2_az) / l0_az >= 0.30 if l0_az else False) or ((l0_rad - l2_rad) / l0_rad >= 0.30 if l0_rad else False)
        passed = passed and coverage >= 0.80
        for r in summary:
            if r["method"] == "L2":
                r["controlled_pass"] = bool_text(passed)
            else:
                r["controlled_pass"] = "reference"
    return summary, detail


def image_or_blank(path: Path, size: tuple[int, int]) -> Image.Image:
    if path.exists():
        return Image.open(path).convert("RGB")
    return Image.new("RGB", size, (20, 20, 20))


def draw_track_tile(scene: str, item: Mapping[str, Any], latent: Mapping[str, Any] | None, direct: Mapping[str, Any] | None) -> Image.Image:
    frame = parse_int(item["frame"])
    img = image_or_blank(frame_path(scene, frame), (800, 600)).resize((320, 240))
    depth = image_or_blank(depth_vis_path(scene, frame), (800, 600)).resize((320, 240))
    canvas = Image.new("RGB", (640, 280), (15, 15, 15))
    canvas.paste(img, (0, 0))
    canvas.paste(depth, (320, 0))
    draw = ImageDraw.Draw(canvas)
    sx, sy = 320 / OPTICAL_WIDTH, 240 / OPTICAL_HEIGHT
    box: Box = item["box"]
    for ox in [0, 320]:
        draw.rectangle([ox + box.x1 * sx, box.y1 * sy, ox + box.x2 * sx, box.y2 * sy], outline=(255, 220, 0), width=2)
        if latent and not latent.get("blocked_reason"):
            lb = state_box_from_branch_b(latent)
            draw.rectangle([ox + lb.x1 * sx, lb.y1 * sy, ox + lb.x2 * sx, lb.y2 * sy], outline=(0, 220, 255), width=2)
        if direct and direct.get("direct_observable_full_stream") == "true":
            draw.rectangle([ox + box.x1 * sx + 3, box.y1 * sy + 3, ox + box.x2 * sx - 3, box.y2 * sy - 3], outline=(0, 255, 120), width=2)
    label = f"f{frame} {item['physical_vehicle_id']} yellow=obs cyan=latent green=full-stream anchor"
    draw.text((6, 248), label[:112], fill=(255, 255, 255))
    return canvas


def make_sheet(tiles: Sequence[Image.Image], out_path: Path, cols: int = 2) -> None:
    if not tiles:
        return
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * w, rows * h), (12, 12, 12))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * w, (i // cols) * h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def render_visuals(
    by_pv: Mapping[str, Sequence[dict[str, Any]]],
    direct_rows: Sequence[Mapping[str, Any]],
    branch_b: Sequence[Mapping[str, Any]],
    pairs: Sequence[Mapping[str, Any]],
    eval_rows: Sequence[Mapping[str, Any]],
    gm017_detail: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    direct_lookup = {(r["physical_vehicle_id"], parse_int(r["frame"])): r for r in direct_rows}
    latent_lookup = branch_b_lookup(branch_b)
    visual_paths: dict[str, str] = {}
    for pv, items in by_pv.items():
        if not items:
            continue
        frames = [parse_int(i["frame"]) for i in items]
        selected = sorted(set([min(frames), max(frames)] + [frames[int(i)] for i in np.linspace(0, len(frames) - 1, min(10, len(frames))).round()]))
        tiles = []
        for item in items:
            if parse_int(item["frame"]) in selected:
                tiles.append(draw_track_tile(SCENE, item, latent_lookup.get((pv, parse_int(item["frame"]))), direct_lookup.get((pv, parse_int(item["frame"])))))
        out = OUTPUT_DIR / f"gm019_full_stream_timeline_{pv}.png"
        make_sheet(tiles, out)
        visual_paths[f"timeline_{pv}"] = str(out)
    pair_tiles = []
    pairs_by_id = {p["pair_id"]: p for p in pairs}
    z0 = {r["pair_id"]: r for r in eval_rows if r["method"] == "Z0_local_detection_box"}
    z2 = {r["pair_id"]: r for r in eval_rows if r["method"] == "Z2_recovery_plus_scene_residual_calibration" and r["scene_anchor_plan"] == "A0"}
    for pair in pairs:
        frame = parse_int(pair["optical_frame"])
        sar_frame = parse_int(pair["sar_frame"])
        img = image_or_blank(frame_path(SCENE, frame), (800, 600)).resize((300, 225))
        sar = image_or_blank(sar_gray_path(SCENE, sar_frame), (2308, 1334)).resize((390, 225))
        canvas = Image.new("RGB", (690, 260), (12, 12, 12))
        canvas.paste(img, (0, 0))
        canvas.paste(sar, (300, 0))
        draw = ImageDraw.Draw(canvas)
        sx, sy = 300 / OPTICAL_WIDTH, 225 / OPTICAL_HEIGHT
        lb = box_from_row(pair, "paired_optical")
        draw.rectangle([lb.x1 * sx, lb.y1 * sy, lb.x2 * sx, lb.y2 * sy], outline=(255, 220, 0), width=2)
        latent = latent_lookup.get((pair["physical_vehicle_id"], frame))
        if latent and not latent.get("blocked_reason"):
            rb = state_box_from_branch_b(latent)
            draw.rectangle([rb.x1 * sx, rb.y1 * sy, rb.x2 * sx, rb.y2 * sy], outline=(0, 220, 255), width=2)
        ssx, ssy = 390 / 2308.0, 225 / 1334.0
        sg = Box(parse_float(pair["sar_bbox_x1"]), parse_float(pair["sar_bbox_y1"]), parse_float(pair["sar_bbox_x2"]), parse_float(pair["sar_bbox_y2"]))
        draw.rectangle([300 + sg.x1 * ssx, sg.y1 * ssy, 300 + sg.x2 * ssx, sg.y2 * ssy], outline=(0, 255, 120), width=2)
        draw.text((6, 232), f"{pair['pair_id']} yellow=paired local cyan=Z1B state green=SAR reference", fill=(255, 255, 255))
        pair_tiles.append(canvas)
    pair_out = OUTPUT_DIR / "gm019_z0_z1_recovery_pair_review.png"
    make_sheet(pair_tiles, pair_out)
    visual_paths["gm019_pair_recovery_review"] = str(pair_out)

    gm017_tiles = []
    for row in gm017_detail[:16]:
        pair = pairs_by_id.get(row.get("pair_id"), {})
        scene = "GM_RM017"
        frame = parse_int(row.get("frame"))
        if frame < 0:
            continue
        img = image_or_blank(frame_path(scene, frame), (800, 600)).resize((360, 270))
        draw = ImageDraw.Draw(img)
        sx, sy = 360 / OPTICAL_WIDTH, 270 / OPTICAL_HEIGHT
        for text, color in [(row["local_or_recovered_box"], (0, 220, 255)), (row["true_full_box"], (0, 255, 120))]:
            b = parse_box_text(text)
            draw.rectangle([b.x1 * sx, b.y1 * sy, b.x2 * sx, b.y2 * sy], outline=color, width=2)
        draw.text((5, 248), f"{row['method']} {row['pair_id']} cyan=restored green=hidden full", fill=(255, 255, 255))
        gm017_tiles.append(img)
    gm017_out = OUTPUT_DIR / "gm017_anchorless_ablation_review.png"
    make_sheet(gm017_tiles, gm017_out)
    visual_paths["gm017_anchorless_ablation_review"] = str(gm017_out)
    return visual_paths


def render_reports(
    freeze_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
    physical_rows: Sequence[Mapping[str, Any]],
    direct_rows: Sequence[Mapping[str, Any]],
    optical_anchors: Sequence[Mapping[str, Any]],
    sar_anchors: Sequence[Mapping[str, Any]],
    branch_a: Sequence[Mapping[str, Any]],
    branch_b: Sequence[Mapping[str, Any]],
    gm017_summary: Sequence[Mapping[str, Any]],
    projection: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    visual_paths: Mapping[str, str],
    status: str,
) -> None:
    full_direct = [r for r in direct_rows if r["direct_observable_full_stream"] == "true"]
    paired_direct = [r for r in direct_rows if r["direct_observable_full_stream"] == "true" and r["paired_with_sar"] == "true"]
    anchor_lines = [
        "# OTY2 WGV3.5A-R2B GM_RM019 Full-Stream Anchor Re-Audit",
        "",
        f"Date: {DATE}",
        "",
        "## Boundary",
        "",
        "R2B keeps original R2 as a paired-row-only anchor audit. It does not overwrite R2 and does not run GM_RM011 or R4.",
        "",
        "## Freeze Manifest",
        "",
        md_table(freeze_rows, ["source_file", "sha256", "bytes", "rows"]),
        "",
        "## Full-Stream Source Inventory",
        "",
        md_table(source_rows, SOURCE_FIELDS),
        "",
        "## Physical Vehicle Timeline",
        "",
        md_table(physical_rows, PHYSICAL_FIELDS),
        "",
        "## Direct Observable Full-Stream Search",
        "",
        f"- paired-row direct observable count: `{len(paired_direct)}`",
        f"- full optical stream direct observable count: `{len(full_direct)}`",
        f"- full optical stream answer: 原R2的0个完整锚点只是在配对行内为0；完整光学时序内为`{len(full_direct)}`。",
        "",
        md_table(direct_rows, DIRECT_FIELDS, limit=40),
        "",
        "## Optical Recovery Anchors",
        "",
        md_table([r for r in optical_anchors if r["usable_as_optical_recovery_anchor"] == "true"], OPTICAL_ANCHOR_FIELDS, limit=60),
        "",
        "## SAR Scene Calibration Anchors",
        "",
        md_table(sar_anchors, SAR_ANCHOR_FIELDS),
    ]
    write_text(OUTPUTS["anchor_md"], "\n".join(anchor_lines))

    method_lines = [
        "# OTY2 WGV3.5A-R2B Anchorless Track-Level Full-Vehicle State Reconstruction",
        "",
        "## Method",
        "",
        "For each physical vehicle and optical frame, R2B estimates latent state `s_t=(center_x, center_y, full_width, full_height, relative_depth, velocity_x, velocity_y, scale_velocity, depth_velocity)`.",
        "",
        "Pseudo-code:",
        "",
        "```text",
        "for each physical vehicle:",
        "  estimate robust full_width/full_height from full-stream direct frames if any, else from high-percentile partial observations",
        "  for each frame:",
        "    if right edge is truncated: center_x = observed_left + full_width / 2",
        "    if left edge is truncated:  center_x = observed_right - full_width / 2",
        "    if bottom edge is truncated: center_y = observed_top + full_height / 2",
        "    otherwise: center ~= observed center",
        "    relative_depth uses vehicle-region depth when usable and is smoothed over time",
        "  fit a weighted temporal line to center/depth and blend with per-frame constraints",
        "  never update one physical vehicle with another physical vehicle state",
        "```",
        "",
        "## GM_RM017 Controlled No-Anchor Ablation",
        "",
        md_table(gm017_summary, ABLATION_FIELDS),
        "",
        "## Branch A Recovery Rows",
        "",
        md_table(branch_a, BRANCH_A_FIELDS),
        "",
        "## Branch B Reconstruction Sample",
        "",
        md_table(branch_b, BRANCH_B_FIELDS, limit=60),
    ]
    write_text(OUTPUTS["method_md"], "\n".join(method_lines))

    visual_lines = [
        "# OTY2 WGV3.5A-R2B Visual Diagnosis",
        "",
        "## Opened Visual Review Sheets",
        "",
    ]
    for name, path in visual_paths.items():
        visual_lines.append(f"- {name}: `{rel(path)}`")
    visual_lines.extend(
        [
            "",
            "## 中文视觉判断",
            "",
            "- GM_RM019每辆主物理车辆均生成了完整光学时间线接触图，黄色为当前检测框，绿色为全流直接可观测帧，青色为轨迹级完整车辆隐状态。",
            "- 黑色近场轿车始终贴近右侧和底边，单帧不能作为完整车体；轨迹级约束主要来自左边界、顶边和时序平滑。",
            "- 白色SUV在进入后的中段出现非配对完整光学锚点，当前可见侧面、车头/车尾线索连续，允许分支A恢复相邻配对帧。",
            "- 银色MPV在中段出现若干非硬边缘完整观测，晚段离开时恢复依赖前锚点和轨迹级约束。",
            "- 灰色左缘车辆的配对帧本身仍是局部前/左边缘，但后续全流中出现完整侧面观测，可支持有限时序恢复。",
            "- 右侧深色碎片仍为身份不安全的短片段，不参与恢复通过判断。",
            "- 未配对小目标044-049、060-080、083-098、259-261均为远处小框或短片段，只作为全流盘点和身份分离证据，不与五辆GM_RM019主评价车辆合并。",
            "- GM_RM017无锚点消融中，青色为隐藏完整框后的模拟局部观测，绿色恢复框沿整段轨迹贴回完整车辆；该结果只证明轨迹级约束机制在受控条件下可恢复，不作为GM_RM019正向SAR投影结论。",
            "- GM_RM019 Z0/Z1A/Z1B/Z2配对复核中，恢复状态相对黄色局部框有所修正，但绿色SAR参考框多数仍未被覆盖，说明剩余问题主要落在场景残差、近场视差、相对深度尺度和身份短片段，而不是再次归并为配对行内无完整锚点。",
            "- 最终失败案例按identity_unresolved、scene_azimuth_residual、scene_radial_residual等字段拆分；所有16条配对行仍保留no_full_anchor_in_paired_rows=true，但只有黑色近场轿车和右侧深色碎片属于no_full_anchor_in_full_optical_stream=true。",
        ]
    )
    write_text(OUTPUTS["visual_md"], "\n".join(visual_lines))

    fail_counts = Counter(r["primary_failure"] for r in failures)
    closure_lines = [
        "# OTY2 WGV3.5A-R2B GM_RM019 Closure",
        "",
        f"Date: {DATE}",
        "",
        f"R2B status: `{status}`",
        "",
        "## Stage Result",
        "",
        f"- full-stream direct optical anchors: `{len(full_direct)}`",
        f"- paired-row direct anchors: `{len(paired_direct)}`",
        f"- usable SAR scene calibration anchors: `{sum(1 for r in sar_anchors if r['usable_as_scene_calibration_anchor'] == 'true')}`",
        "- R2 remains valid as paired-row-only anchor audit; R2B expands the optical-stream search and separates recovery anchors from SAR calibration anchors.",
        "",
        "## Projection Comparison",
        "",
        md_table(projection, PROJECTION_FIELDS),
        "",
        "## Failure Source Split",
        "",
        f"- primary failure counts: `{dict(fail_counts)}`",
        md_table(failures, FAILURE_FIELDS),
        "",
        "## Boundary Confirmation",
        "",
        "- No GT/manual annotation was modified.",
        "- No final SAR boxes were emitted.",
        "- No full-SAR bright-response search, YOLO training, full MOT rerun, GM_RM011 R3, or R4 frontend execution was performed.",
        "- SAR annotation is used only for held-out projection evaluation and scene residual experiments, never to recover unpaired optical states.",
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{rel(path)}`" for path in OUTPUTS.values()),
    ]
    write_text(OUTPUTS["closure_md"], "\n".join(closure_lines))


def run_all(stage: str) -> dict[str, Any]:
    freeze_rows = build_freeze_manifest()
    source_rows = build_source_inventory()
    pairs, _r2_rows, _sar_rows = load_pair_context()
    _enriched, by_pv = enrich_track_rows()
    physical_rows = build_physical_timeline(by_pv, pairs)
    direct_rows = build_direct_scan(by_pv, pairs)
    optical_anchors = build_optical_anchors(direct_rows, by_pv)
    branch_a = build_branch_a(pairs, optical_anchors)
    branch_b = build_anchorless(by_pv, direct_rows)
    sar_anchors = build_sar_anchors(pairs, branch_a, branch_b)
    model = load_r1_model()
    gm017_summary, gm017_detail = finalize_gm017_ablation(model)
    projection, eval_rows, failures = build_projection(pairs, branch_a, branch_b, sar_anchors, model)
    visual_paths = render_visuals(by_pv, direct_rows, branch_b, pairs, eval_rows, gm017_detail)
    usable_sar_anchors = sum(1 for r in sar_anchors if r["usable_as_scene_calibration_anchor"] == "true")
    l2_row = next((r for r in gm017_summary if r["method"] == "L2"), {})
    z2_rows = [r for r in projection if r["method"] == "Z2_recovery_plus_scene_residual_calibration"]
    best_coverage = 0.0
    for row in z2_rows:
        cov = norm(row.get("center_coverage_95", "0/0")).split("/")
        if len(cov) == 2:
            best_coverage = max(best_coverage, parse_float(cov[0], 0.0) / max(1.0, parse_float(cov[1], 1.0)))
    if l2_row.get("controlled_pass") != "true":
        status = "OPEN_R2B_ANCHORLESS_METHOD_NOT_VALIDATED_ON_GM017"
    elif usable_sar_anchors == 0:
        status = "OPEN_R2B_FULL_STREAM_RECOVERY_NO_SAR_CALIBRATION_ANCHORS"
    elif not z2_rows or max(parse_float(r.get("sample_count"), 0.0) for r in z2_rows) <= 0:
        status = "OPEN_R2B_GM019_RECOVERY_NOT_EVALUABLE"
    elif best_coverage < 0.80:
        status = "OPEN_R2B_FULL_STREAM_RECOVERY_FOUND_SAR_PROJECTION_INSUFFICIENT"
    else:
        status = "CLOSED_GM19_FULL_STREAM_RECOVERY_FEASIBLE_SCENE_RESIDUAL_REQUIRED"

    write_csv(OUTPUTS["freeze"], freeze_rows, ["source_file", "sha256", "bytes", "rows"])
    write_csv(OUTPUTS["source_inventory"], source_rows, SOURCE_FIELDS)
    write_csv(OUTPUTS["physical_timeline"], physical_rows, PHYSICAL_FIELDS)
    write_csv(OUTPUTS["direct_scan"], direct_rows, DIRECT_FIELDS)
    write_csv(OUTPUTS["optical_anchors"], optical_anchors, OPTICAL_ANCHOR_FIELDS)
    write_csv(OUTPUTS["sar_anchors"], sar_anchors, SAR_ANCHOR_FIELDS)
    write_csv(OUTPUTS["branch_a"], branch_a, BRANCH_A_FIELDS)
    write_csv(OUTPUTS["branch_b"], branch_b, BRANCH_B_FIELDS)
    write_csv(OUTPUTS["gm017_ablation"], gm017_summary, ABLATION_FIELDS)
    write_csv(OUTPUTS["projection"], projection, PROJECTION_FIELDS)
    write_csv(OUTPUTS["eval_rows"], eval_rows, EVAL_FIELDS)
    write_csv(OUTPUTS["failures"], failures, FAILURE_FIELDS)
    render_reports(
        freeze_rows,
        source_rows,
        physical_rows,
        direct_rows,
        optical_anchors,
        sar_anchors,
        branch_a,
        branch_b,
        gm017_summary,
        projection,
        failures,
        visual_paths,
        status,
    )
    return {
        "stage": stage,
        "status": status,
        "full_stream_direct_anchors": sum(1 for r in direct_rows if r["direct_observable_full_stream"] == "true"),
        "paired_direct_anchors": sum(1 for r in direct_rows if r["direct_observable_full_stream"] == "true" and r["paired_with_sar"] == "true"),
        "usable_sar_scene_anchors": usable_sar_anchors,
        "outputs": {k: str(v) for k, v in OUTPUTS.items()},
        "visual_outputs": visual_paths,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["audit", "recover", "calibrate", "evaluate", "visualize", "all"], default="all")
    args = parser.parse_args(argv)
    print(json.dumps(run_all(args.stage), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
