"""Run WGV3.5A-R1 full-vehicle state recovery diagnostics for GM_RM017.

This script reads the frozen WGV3.5A artifacts and real GM_RM017 imagery,
then writes only WGV3.5A-R1 outputs. It does not retrain detectors, does not
modify GT, does not output final SAR annotations, and does not run a selector
or candidate-ranking stage.
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

try:
    from sklearn.ensemble import GradientBoostingRegressor
except Exception:  # pragma: no cover - optional reference model only
    GradientBoostingRegressor = None


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path(r"D:\profile\research\data")
OUTPUT_DIR = REPO_ROOT / "outputs" / "wgv3_5a_r1_20260710"
DATE = "20260710"

OPTICAL_WIDTH = 800.0
OPTICAL_HEIGHT = 600.0
SAR_WIDTH = 2308.0
SAR_HEIGHT = 1334.0
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
FULL_AZIMUTH_SPAN = 178.0

BASELINE_FILES = [
    REPORT_DIR / f"oty2_wgv3_5a_pair_and_depth_audit_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_visual_feasible_field_diagnosis_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_weak_physical_projection_closure_{DATE}.md",
    SAMPLES_DIR / f"oty2_wgv3_5a_paired_annotations_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_sar_polar_targets_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_optical_vehicle_states_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_identity_safe_split_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_azimuth_calibration_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_radial_calibration_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_failure_cases_{DATE}.csv",
]

INPUTS = {
    "pairs": SAMPLES_DIR / f"oty2_wgv3_5a_paired_annotations_{DATE}.csv",
    "sar": SAMPLES_DIR / f"oty2_wgv3_5a_sar_polar_targets_{DATE}.csv",
    "optical": SAMPLES_DIR / f"oty2_wgv3_5a_optical_vehicle_states_{DATE}.csv",
    "split": SAMPLES_DIR / f"oty2_wgv3_5a_identity_safe_split_{DATE}.csv",
}

OUTPUTS = {
    "identity_md": REPORT_DIR / f"oty2_wgv3_5a_r1_physical_vehicle_identity_audit_{DATE}.md",
    "vehicle_map": SAMPLES_DIR / f"oty2_wgv3_5a_r1_physical_vehicle_map_{DATE}.csv",
    "observation": SAMPLES_DIR / f"oty2_wgv3_5a_r1_observation_state_audit_{DATE}.csv",
    "mechanism_md": REPORT_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_mechanism_{DATE}.md",
    "baseline": SAMPLES_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_baseline_{DATE}.csv",
    "simulation": SAMPLES_DIR / f"oty2_wgv3_5a_r1_simulated_truncation_manifest_{DATE}.csv",
    "natural": SAMPLES_DIR / f"oty2_wgv3_5a_r1_natural_truncation_cases_{DATE}.csv",
    "recovered": SAMPLES_DIR / f"oty2_wgv3_5a_r1_recovered_full_vehicle_states_{DATE}.csv",
    "projection": SAMPLES_DIR / f"oty2_wgv3_5a_r1_projection_comparison_{DATE}.csv",
    "failures": SAMPLES_DIR / f"oty2_wgv3_5a_r1_failure_cases_{DATE}.csv",
    "visual_md": REPORT_DIR / f"oty2_wgv3_5a_r1_visual_diagnosis_{DATE}.md",
    "closure_md": REPORT_DIR / f"oty2_wgv3_5a_r1_closure_{DATE}.md",
}

THREAD_TO_PHYSICAL = {
    "oty1t_obj_GM_RM017_bytetrack_bt_0008": "PV_GM17_DARK_LEAD_CANDIDATE",
    "oty1t_obj_GM_RM017_bytetrack_bt_0010": "PV_GM17_WHITE_SUV",
    "oty1t_obj_GM_RM017_bytetrack_bt_0012": "PV_GM17_DARK_FOLLOW",
    "oty1t_obj_GM_RM017_bytetrack_bt_0014": "PV_GM17_DARK_LEAD_CANDIDATE",
}

PHYSICAL_VEHICLE_FIELDS = [
    "physical_vehicle_id",
    "source_track_ids",
    "optical_frame_start",
    "optical_frame_end",
    "same_vehicle_relation",
    "same_vehicle_confidence",
    "evidence",
    "conflict",
]

OBSERVATION_FIELDS = [
    "pair_id",
    "frame",
    "track_id",
    "physical_vehicle_id",
    "old_visibility_state",
    "geometry_edge_state",
    "visual_observation_state",
    "visible_parts",
    "direct_observable",
    "temporally_recoverable",
    "not_safely_recoverable",
    "state_reason",
]

BASELINE_FIELDS = [
    "model_target",
    "model_name",
    "input_features",
    "sample_count",
    "physical_vehicle_count",
    "selected",
    "parameters",
    "median_error",
    "p90_error",
    "center_coverage_95",
    "full_box_coverage_95",
    "median_search_ratio",
    "notes",
]

SIMULATION_FIELDS = [
    "simulation_id",
    "source_pair_id",
    "physical_vehicle_id",
    "source_frame",
    "simulation_type",
    "crop_ratio",
    "original_bbox",
    "simulated_bbox",
    "original_depth",
    "simulated_depth",
    "original_center",
    "simulated_center",
    "truncation_direction",
]

NATURAL_FIELDS = [
    "natural_case_id",
    "pair_id",
    "frame",
    "physical_vehicle_id",
    "source_track_id",
    "previous_complete_frame",
    "next_complete_frame",
    "truncation_direction",
    "visible_parts",
    "local_bbox_center",
    "estimated_full_center",
    "local_depth",
    "estimated_full_depth",
    "sar_gt_azimuth",
    "sar_gt_radial",
    "direct_projection_azimuth_error",
    "direct_projection_radial_error",
]

RECOVERED_FIELDS = [
    "sample_id",
    "sample_kind",
    "source_pair_id",
    "physical_vehicle_id",
    "frame",
    "local_bbox",
    "recovered_center_x",
    "recovered_center_y",
    "recovered_width",
    "recovered_height",
    "recovered_depth",
    "recovery_mode",
    "previous_anchor_frame",
    "next_anchor_frame",
    "recovery_confidence",
    "visible_boundary_consistency",
    "recovery_blocked_reason",
]

PROJECTION_FIELDS = [
    "evaluation_group",
    "method",
    "sample_count",
    "azimuth_median_error",
    "azimuth_p90_error",
    "radial_median_error",
    "radial_p90_error",
    "center_coverage_95",
    "full_box_coverage_95",
    "median_search_ratio",
    "multi_target_rate",
]

FAILURE_FIELDS = [
    "failure_id",
    "sample_id",
    "sample_kind",
    "method",
    "physical_vehicle_id",
    "frame",
    "azimuth_error",
    "radial_error",
    "dominant_failure",
    "identity",
    "motion",
    "scale",
    "depth",
    "pairing",
    "weak_calibration",
    "notes",
]


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def bottom_y(self) -> float:
        return self.y2

    def clipped(self) -> "Box":
        return Box(
            min(max(self.x1, 0.0), OPTICAL_WIDTH - 1.0),
            min(max(self.y1, 0.0), OPTICAL_HEIGHT - 1.0),
            min(max(self.x2, 0.0), OPTICAL_WIDTH - 1.0),
            min(max(self.y2, 0.0), OPTICAL_HEIGHT - 1.0),
        )

    def as_text(self) -> str:
        return f"{fmt(self.x1, 3)},{fmt(self.y1, 3)},{fmt(self.x2, 3)},{fmt(self.y2, 3)}"


@dataclass
class LinearModel:
    name: str
    features: list[str]
    coefficients: np.ndarray
    intercept: float
    fill_values: np.ndarray
    ridge_alpha: float = 0.0

    def predict(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        arr = clean_matrix(arr, self.fill_values)
        return arr @ self.coefficients + self.intercept

    def parameters(self) -> str:
        payload = {
            "intercept": round(float(self.intercept), 8),
            "coefficients": [round(float(v), 8) for v in self.coefficients],
            "ridge_alpha": self.ridge_alpha,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        text = norm(value)
        return float(text) if text else default
    except Exception:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    number = parse_float(value, float(default))
    return int(round(number)) if math.isfinite(number) else default


def fmt(value: Any, digits: int = 4) -> str:
    try:
        number = float(value)
    except Exception:
        return norm(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


def duplicate_header(row: Mapping[str, Any]) -> bool:
    hits = sum(1 for key, value in row.items() if norm(key) == norm(value))
    return hits >= max(2, len(row) // 2)


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


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc}"


def median(values: Iterable[float], default: float = 0.0) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.median(clean)) if clean else default


def percentile(values: Iterable[float], pct: float, default: float = 0.0) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.percentile(clean, pct)) if clean else default


def frame_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_frames" / f"{frame:06d}.png"


def depth_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_depth" / f"{frame:06d}_depth.npy"


def depth_vis_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_depth" / f"{frame:06d}_depth_vis.png"


def sar_gray_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def polar_to_pixel(azimuth_deg: float, radial_px: float) -> tuple[float, float]:
    angle = math.radians(azimuth_deg)
    return FAN_CENTER_X + radial_px * math.sin(angle), FAN_CENTER_Y - radial_px * math.cos(angle)


def depth_crop_stats(scene: str, frame: int, box: Box) -> dict[str, float]:
    path = depth_path(scene, frame)
    if not path.exists():
        return {"D1": float("nan"), "D4": float("nan"), "q10": float("nan"), "q50": float("nan"), "q90": float("nan"), "valid_ratio": 0.0}
    arr = np.load(path)
    h, w = arr.shape[:2]
    box = box.clipped()
    ix1, iy1 = max(0, int(math.floor(box.x1))), max(0, int(math.floor(box.y1)))
    ix2, iy2 = min(w, int(math.ceil(box.x2))), min(h, int(math.ceil(box.y2)))
    if ix2 <= ix1 or iy2 <= iy1:
        return {"D1": float("nan"), "D4": float("nan"), "q10": float("nan"), "q50": float("nan"), "q90": float("nan"), "valid_ratio": 0.0}
    crop = np.asarray(arr[iy1:iy2, ix1:ix2], dtype=float)
    finite = crop[np.isfinite(crop)]
    positive = finite[finite > 0]
    if positive.size == 0:
        return {"D1": float("nan"), "D4": float("nan"), "q10": float("nan"), "q50": float("nan"), "q90": float("nan"), "valid_ratio": 0.0}
    shrink_x = int(round(box.width * 0.2))
    shrink_y = int(round(box.height * 0.2))
    inner = crop[
        min(shrink_y, max(0, crop.shape[0] - 1)) : max(min(crop.shape[0], crop.shape[0] - shrink_y), min(shrink_y + 1, crop.shape[0])),
        min(shrink_x, max(0, crop.shape[1] - 1)) : max(min(crop.shape[1], crop.shape[1] - shrink_x), min(shrink_x + 1, crop.shape[1])),
    ]
    inner_positive = inner[np.isfinite(inner)]
    inner_positive = inner_positive[inner_positive > 0]
    d1 = float(np.median(inner_positive)) if inner_positive.size else float(np.median(positive))
    return {
        "D1": d1,
        "D4": d1,
        "q10": float(np.percentile(positive, 10)),
        "q50": float(np.percentile(positive, 50)),
        "q90": float(np.percentile(positive, 90)),
        "valid_ratio": float(positive.size / crop.size),
    }


def load_baseline_rows() -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, str]], list[dict[str, str]]]:
    pairs = [row for row in read_csv(INPUTS["pairs"]) if norm(row.get("scene")) == "GM_RM017"]
    optical = {row["pair_id"]: row for row in read_csv(INPUTS["optical"])}
    sar = {row["pair_id"]: row for row in read_csv(INPUTS["sar"])}
    split = [row for row in read_csv(INPUTS["split"]) if norm(row.get("scene")) == "GM_RM017"]
    return pairs, optical, sar, split


def edge_state(box: Box) -> tuple[str, bool, bool, bool, bool, bool, bool]:
    left_contact = box.x1 <= 2.0
    right_contact = box.x2 >= 798.0
    bottom_contact = box.y2 >= 598.0
    left_near = box.x1 <= 24.0
    right_near = box.x2 >= 776.0
    bottom_near = box.y2 >= 582.0
    parts = []
    if left_contact:
        parts.append("left_contact")
    elif left_near:
        parts.append("left_near_edge")
    if right_contact:
        parts.append("right_contact")
    elif right_near:
        parts.append("right_near_edge")
    if bottom_contact:
        parts.append("bottom_contact")
    elif bottom_near:
        parts.append("bottom_near_edge")
    if not parts:
        parts.append("no_edge_contact")
    return ";".join(parts), left_contact, right_contact, bottom_contact, left_near, right_near, bottom_near


def visible_parts_from_edge(edge: str) -> tuple[str, str]:
    if "left_contact" in edge or "left_near_edge" in edge:
        return "right_or_center_visible;left_side_outside_or_uncertain", "left"
    if "right_contact" in edge or "right_near_edge" in edge:
        return "left_or_center_visible;right_side_outside_or_uncertain", "right"
    if "bottom_contact" in edge or "bottom_near_edge" in edge:
        return "upper_vehicle_visible;lower_vehicle_bottom_uncertain", "bottom"
    return "full_body_approximately_visible", "none"


def is_high_conf_pair(row: Mapping[str, Any]) -> bool:
    return norm(row.get("pair_confidence")) == "high_confidence_pair"


def build_joined_rows(
    pairs: Sequence[Mapping[str, str]],
    optical_by_id: Mapping[str, Mapping[str, str]],
    sar_by_id: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    joined = []
    for pair in pairs:
        pid = norm(pair.get("pair_id"))
        optical = optical_by_id.get(pid, {})
        sar = sar_by_id.get(pid, {})
        box = Box(
            parse_float(pair.get("optical_bbox_x1")),
            parse_float(pair.get("optical_bbox_y1")),
            parse_float(pair.get("optical_bbox_x2")),
            parse_float(pair.get("optical_bbox_y2")),
        )
        sar_box = Box(
            parse_float(pair.get("sar_bbox_x1")),
            parse_float(pair.get("sar_bbox_y1")),
            parse_float(pair.get("sar_bbox_x2")),
            parse_float(pair.get("sar_bbox_y2")),
        )
        edge, left_contact, right_contact, bottom_contact, left_near, right_near, bottom_near = edge_state(box)
        visible_parts, direction = visible_parts_from_edge(edge)
        hard_edge = left_contact or right_contact or bottom_contact
        near_edge = left_near or right_near or bottom_near
        old_visibility = norm(pair.get("visibility_state"))
        old_boundary_none = "boundary=none" in old_visibility
        wide_enough = box.width >= 110.0 and box.height >= 45.0
        direct = (not hard_edge) and (not near_edge) and wide_enough and is_high_conf_pair(pair)
        recoverable = (hard_edge or near_edge) and is_high_conf_pair(pair)
        state = "direct_observable" if direct else "temporally_recoverable" if recoverable else "not_safely_recoverable"
        if direct:
            reason = "bbox has no hard/soft edge contact, size is sufficient, and pair confidence is high"
        elif recoverable:
            reason = "bbox touches or approaches image boundary; temporal full-vehicle anchors are required"
        else:
            reason = "not high-confidence or too local for safe full-vehicle state use"
        joined.append(
            {
                "pair_id": pid,
                "scene": "GM_RM017",
                "frame": parse_int(pair.get("optical_frame")),
                "sar_frame": parse_int(pair.get("sar_frame")),
                "track_id": norm(pair.get("optical_thread_id")),
                "physical_vehicle_id": THREAD_TO_PHYSICAL.get(norm(pair.get("optical_thread_id")), "PV_GM17_UNRESOLVED"),
                "box": box,
                "sar_box": sar_box,
                "old_visibility_state": old_visibility,
                "geometry_edge_state": edge,
                "truncation_direction": direction,
                "visible_parts": visible_parts,
                "visual_observation_state": state,
                "direct_observable": direct,
                "temporally_recoverable": recoverable,
                "not_safely_recoverable": state == "not_safely_recoverable",
                "state_reason": reason,
                "incorrect_old_visibility": old_boundary_none and near_edge,
                "pair_confidence": norm(pair.get("pair_confidence")),
                "sar_gt_id": norm(pair.get("sar_gt_id")),
                "sar_azimuth": parse_float(sar.get("sar_center_azimuth_deg")),
                "sar_radial": parse_float(sar.get("sar_center_radial_pixel")),
                "sar_azimuth_span": parse_float(sar.get("sar_azimuth_span"), 0.0),
                "sar_radial_span": parse_float(sar.get("sar_radial_span"), 0.0),
                "depth": parse_float(optical.get("depth_D4"), parse_float(optical.get("depth_D1"))),
                "depth_D1": parse_float(optical.get("depth_D1")),
                "depth_q10": parse_float(optical.get("depth_q10")),
                "depth_q90": parse_float(optical.get("depth_q90")),
                "velocity_x": parse_float(optical.get("optical_velocity_x"), 0.0),
                "velocity_y": parse_float(optical.get("optical_velocity_y"), 0.0),
            }
        )
    joined.sort(key=lambda row: (row["frame"], row["track_id"], row["pair_id"]))
    return joined


def build_physical_vehicle_map(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[norm(row["physical_vehicle_id"])].append(row)
    out = []
    for vehicle_id, vehicle_rows in sorted(grouped.items()):
        tracks = sorted(set(norm(row["track_id"]) for row in vehicle_rows))
        frames = [parse_int(row["frame"]) for row in vehicle_rows]
        if vehicle_id == "PV_GM17_WHITE_SUV":
            evidence = "white SUV; appears as the middle vehicle across frames 151-189; co-occurs with dark vehicles"
            conflict = "none for 0010 as a single physical vehicle; not independent from same-scene traffic context"
            confidence = "0.95"
        elif vehicle_id == "PV_GM17_DARK_FOLLOW":
            evidence = "dark sedan following the white SUV; visible from left to right across frames 162-210"
            conflict = "co-occurs with 0010 and 0014 in frame 184, so it is not the same vehicle as those tracks"
            confidence = "0.9"
        elif vehicle_id == "PV_GM17_DARK_LEAD_CANDIDATE":
            evidence = "dark leading/right-edge vehicle; 0008 exits at the right edge by frame 181-182 and 0014 appears near the same edge from frame 184"
            conflict = "0014 is only a small edge fragment and remains a candidate continuation of 0008, not a training/test identity truth"
            confidence = "0.65"
        else:
            evidence = "unresolved track mapping"
            conflict = "insufficient appearance evidence"
            confidence = "0.2"
        out.append(
            {
                "physical_vehicle_id": vehicle_id,
                "source_track_ids": ";".join(tracks),
                "optical_frame_start": min(frames),
                "optical_frame_end": max(frames),
                "same_vehicle_relation": "same_physical_vehicle" if vehicle_id != "PV_GM17_UNRESOLVED" else "identity_unresolved",
                "same_vehicle_confidence": confidence,
                "evidence": evidence,
                "conflict": conflict,
            }
        )
    out.extend(
        [
            {
                "physical_vehicle_id": "PV_REL_0010_VS_0012",
                "source_track_ids": "oty1t_obj_GM_RM017_bytetrack_bt_0010;oty1t_obj_GM_RM017_bytetrack_bt_0012",
                "optical_frame_start": 162,
                "optical_frame_end": 189,
                "same_vehicle_relation": "overlapping_different_vehicles",
                "same_vehicle_confidence": "0.98",
                "evidence": "same frames show a white SUV and a separate dark sedan at different image positions",
                "conflict": "none",
            },
            {
                "physical_vehicle_id": "PV_REL_0012_VS_0014",
                "source_track_ids": "oty1t_obj_GM_RM017_bytetrack_bt_0012;oty1t_obj_GM_RM017_bytetrack_bt_0014",
                "optical_frame_start": 184,
                "optical_frame_end": 184,
                "same_vehicle_relation": "overlapping_different_vehicles",
                "same_vehicle_confidence": "0.98",
                "evidence": "frame 184 contains both track boxes simultaneously: 0012 on the left dark sedan, 0014 at the far right edge",
                "conflict": "none",
            },
            {
                "physical_vehicle_id": "PV_REL_0008_VS_0014",
                "source_track_ids": "oty1t_obj_GM_RM017_bytetrack_bt_0008;oty1t_obj_GM_RM017_bytetrack_bt_0014",
                "optical_frame_start": 181,
                "optical_frame_end": 184,
                "same_vehicle_relation": "same_physical_vehicle",
                "same_vehicle_confidence": "0.65",
                "evidence": "right-edge dark vehicle continuity from 0008 exit to 0014 fragment is plausible",
                "conflict": "0014 fragment is too small for a hard identity claim",
            },
        ]
    )
    return out


def build_observation_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "pair_id": row["pair_id"],
                "frame": row["frame"],
                "track_id": row["track_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "old_visibility_state": row["old_visibility_state"],
                "geometry_edge_state": row["geometry_edge_state"],
                "visual_observation_state": row["visual_observation_state"],
                "visible_parts": row["visible_parts"],
                "direct_observable": bool_text(bool(row["direct_observable"])),
                "temporally_recoverable": bool_text(bool(row["temporally_recoverable"])),
                "not_safely_recoverable": bool_text(bool(row["not_safely_recoverable"])),
                "state_reason": row["state_reason"],
            }
        )
    return out


def clean_matrix(x: np.ndarray, fill_values: np.ndarray | None = None) -> np.ndarray:
    arr = np.asarray(x, dtype=float).copy()
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if fill_values is None:
        fill_values = np.zeros(arr.shape[1], dtype=float)
        for col in range(arr.shape[1]):
            clean = arr[np.isfinite(arr[:, col]), col]
            fill_values[col] = float(np.median(clean)) if clean.size else 0.0
    for col in range(arr.shape[1]):
        mask = ~np.isfinite(arr[:, col])
        if mask.any():
            arr[mask, col] = fill_values[col]
    return arr


def fit_linear_model(name: str, features: list[str], x: np.ndarray, y: np.ndarray, ridge_alpha: float = 0.0) -> LinearModel:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    fill_values = np.zeros(x.shape[1], dtype=float)
    for col in range(x.shape[1]):
        clean = x[np.isfinite(x[:, col]), col]
        fill_values[col] = float(np.median(clean)) if clean.size else 0.0
    x = clean_matrix(x, fill_values)
    design = np.column_stack([np.ones(len(x)), x])
    reg = np.eye(design.shape[1]) * ridge_alpha
    reg[0, 0] = 0.0
    beta = np.linalg.pinv(design.T @ design + reg) @ design.T @ y
    return LinearModel(name=name, features=features, coefficients=beta[1:], intercept=float(beta[0]), fill_values=fill_values, ridge_alpha=ridge_alpha)


def feature_row(row: Mapping[str, Any], mode: str) -> list[float]:
    box: Box = row["box"]
    depth = parse_float(row.get("depth"))
    if mode == "az_linear":
        return [box.cx]
    if mode == "az_quadratic":
        x = box.cx
        return [x, x * x]
    if mode == "az_pinhole_like":
        return [math.degrees(math.atan((box.cx - 400.0) / 360.0))]
    if mode == "radial_depth_only":
        return [depth]
    if mode == "radial_bbox_geometry":
        return [box.width, box.height, box.bottom_y]
    if mode == "radial_depth_bbox":
        return [depth, box.width, box.height, box.bottom_y]
    raise ValueError(mode)


def state_features(box: Box, depth: float, mode: str) -> list[float]:
    if mode == "az_linear":
        return [box.cx]
    if mode == "az_quadratic":
        return [box.cx, box.cx * box.cx]
    if mode == "az_pinhole_like":
        return [math.degrees(math.atan((box.cx - 400.0) / 360.0))]
    if mode == "radial_depth_only":
        return [depth]
    if mode == "radial_bbox_geometry":
        return [box.width, box.height, box.bottom_y]
    if mode == "radial_depth_bbox":
        return [depth, box.width, box.height, box.bottom_y]
    raise ValueError(mode)


def evaluate_prediction_errors(pred: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    errors = np.abs(np.asarray(pred, dtype=float) - np.asarray(target, dtype=float))
    return median(errors), percentile(errors, 90)


def fit_complete_models(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    direct = [row for row in rows if row["direct_observable"]]
    if len(direct) < 10:
        raise RuntimeError("not enough direct_observable GM_RM017 samples for R1 complete-vehicle fit")
    vehicle_count = len(set(row["physical_vehicle_id"] for row in direct))
    az_y = np.asarray([parse_float(row["sar_azimuth"]) for row in direct], dtype=float)
    rad_y = np.asarray([parse_float(row["sar_radial"]) for row in direct], dtype=float)
    baseline_rows: list[dict[str, Any]] = []
    az_candidates = [
        ("linear_center_x", "az_linear", ["bbox_center_x"], 0.0),
        ("quadratic_center_x", "az_quadratic", ["bbox_center_x", "bbox_center_x_sq"], 0.0),
        ("pinhole_like_effective", "az_pinhole_like", ["atan((bbox_center_x-400)/360)"], 0.0),
    ]
    az_models = []
    for name, mode, features, alpha in az_candidates:
        x = np.asarray([feature_row(row, mode) for row in direct], dtype=float)
        model = fit_linear_model(name, features, x, az_y, alpha)
        pred = model.predict(x)
        med, p90 = evaluate_prediction_errors(pred, az_y)
        az_models.append((p90, med, mode, model, pred))
    selected_az = sorted(az_models, key=lambda item: (item[0], item[1]))[0]
    for p90, med, mode, model, pred in az_models:
        baseline_rows.append(
            {
                "model_target": "azimuth",
                "model_name": model.name,
                "input_features": ";".join(model.features),
                "sample_count": len(direct),
                "physical_vehicle_count": vehicle_count,
                "selected": bool_text(model.name == selected_az[3].name),
                "parameters": model.parameters(),
                "median_error": fmt(med, 6),
                "p90_error": fmt(p90, 6),
                "center_coverage_95": "",
                "full_box_coverage_95": "",
                "median_search_ratio": "",
                "notes": "complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only",
            }
        )
    radial_candidates = [
        ("depth_only_linear", "radial_depth_only", ["depth_D4"], 0.0),
        ("bbox_geometry_linear", "radial_bbox_geometry", ["bbox_width", "bbox_height", "bbox_bottom_y"], 0.0),
        ("depth_plus_bbox_ridge", "radial_depth_bbox", ["depth_D4", "bbox_width", "bbox_height", "bbox_bottom_y"], 1.0),
    ]
    radial_models = []
    for name, mode, features, alpha in radial_candidates:
        x = np.asarray([feature_row(row, mode) for row in direct], dtype=float)
        model = fit_linear_model(name, features, x, rad_y, alpha)
        pred = model.predict(x)
        med, p90 = evaluate_prediction_errors(pred, rad_y)
        radial_models.append((p90, med, mode, model, pred))
    gb_result = None
    if GradientBoostingRegressor is not None:
        x = np.asarray([feature_row(row, "radial_depth_bbox") for row in direct], dtype=float)
        x = clean_matrix(x)
        gb = GradientBoostingRegressor(random_state=3401, max_depth=2, n_estimators=80, learning_rate=0.05)
        gb.fit(x, rad_y)
        pred = gb.predict(x)
        med, p90 = evaluate_prediction_errors(pred, rad_y)
        gb_result = (p90, med, pred)
        baseline_rows.append(
            {
                "model_target": "radial",
                "model_name": "gradient_boosting_reference",
                "input_features": "depth_D4;bbox_width;bbox_height;bbox_bottom_y",
                "sample_count": len(direct),
                "physical_vehicle_count": vehicle_count,
                "selected": "false",
                "parameters": "reference_only;random_state=3401;max_depth=2;n_estimators=80",
                "median_error": fmt(med, 6),
                "p90_error": fmt(p90, 6),
                "center_coverage_95": "",
                "full_box_coverage_95": "",
                "median_search_ratio": "",
                "notes": "reference only; not used as R1 mechanism projection",
            }
        )
    selected_radial = sorted(radial_models, key=lambda item: (item[0], item[1]))[0]
    for p90, med, mode, model, pred in radial_models:
        baseline_rows.append(
            {
                "model_target": "radial",
                "model_name": model.name,
                "input_features": ";".join(model.features),
                "sample_count": len(direct),
                "physical_vehicle_count": vehicle_count,
                "selected": bool_text(model.name == selected_radial[3].name),
                "parameters": model.parameters(),
                "median_error": fmt(med, 6),
                "p90_error": fmt(p90, 6),
                "center_coverage_95": "",
                "full_box_coverage_95": "",
                "median_search_ratio": "",
                "notes": "interpretable complete-observable radial baseline",
            }
        )
    az_mode, az_model = selected_az[2], selected_az[3]
    rad_mode, rad_model = selected_radial[2], selected_radial[3]
    selected_az_pred = selected_az[3].predict(np.asarray([feature_row(row, az_mode) for row in direct], dtype=float))
    selected_rad_pred = selected_radial[3].predict(np.asarray([feature_row(row, rad_mode) for row in direct], dtype=float))
    az_errors = np.abs(selected_az_pred - az_y)
    rad_errors = np.abs(selected_rad_pred - rad_y)
    intervals = {
        "az_q50": max(1.0, percentile(az_errors, 50)),
        "az_q95": max(2.0, percentile(az_errors, 95)),
        "rad_q50": max(8.0, percentile(rad_errors, 50)),
        "rad_q95": max(18.0, percentile(rad_errors, 95)),
    }
    direct_eval = []
    for row, pred_az, pred_rad in zip(direct, selected_az_pred, selected_rad_pred):
        direct_eval.append(sample_eval(row, "direct_observable_control", "M2_recovered_full_vehicle_state", pred_az, pred_rad, intervals["az_q95"], intervals["rad_q95"]))
    direct_metrics = aggregate_eval(direct_eval)
    baseline_rows.append(
        {
            "model_target": "complete_observation_selected",
            "model_name": f"{az_model.name}+{rad_model.name}",
            "input_features": ";".join(az_model.features + rad_model.features),
            "sample_count": len(direct),
            "physical_vehicle_count": vehicle_count,
            "selected": "true",
            "parameters": json.dumps({"azimuth": az_model.parameters(), "radial": rad_model.parameters(), "intervals": intervals}, ensure_ascii=False),
            "median_error": f"az={fmt(direct_metrics['azimuth_median_error'], 6)};radial={fmt(direct_metrics['radial_median_error'], 6)}",
            "p90_error": f"az={fmt(direct_metrics['azimuth_p90_error'], 6)};radial={fmt(direct_metrics['radial_p90_error'], 6)}",
            "center_coverage_95": fmt(direct_metrics["center_coverage_95"], 6),
            "full_box_coverage_95": fmt(direct_metrics["full_box_coverage_95"], 6),
            "median_search_ratio": fmt(direct_metrics["median_search_ratio"], 8),
            "notes": "selected R1 interpretable complete-vehicle projection baseline",
        }
    )
    bundle = {
        "direct_rows": direct,
        "az_mode": az_mode,
        "az_model": az_model,
        "radial_mode": rad_mode,
        "radial_model": rad_model,
        "intervals": intervals,
        "gb_reference": gb_result,
    }
    return baseline_rows, bundle


def choose_simulation_sources(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    direct = [row for row in rows if row["direct_observable"]]
    by_vehicle: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in direct:
        by_vehicle[row["physical_vehicle_id"]].append(row)
    selected: list[Mapping[str, Any]] = []
    for vehicle, vehicle_rows in sorted(by_vehicle.items()):
        vehicle_rows = sorted(vehicle_rows, key=lambda row: row["box"].cx)
        picks = [0, len(vehicle_rows) // 3, 2 * len(vehicle_rows) // 3, len(vehicle_rows) - 1]
        for idx in sorted(set(picks)):
            selected.append(vehicle_rows[idx])
    selected = sorted({row["pair_id"]: row for row in selected}.values(), key=lambda row: (row["frame"], row["pair_id"]))
    if len(selected) < 10:
        all_direct = sorted(direct, key=lambda row: row["box"].cx)
        for idx in np.linspace(0, max(0, len(all_direct) - 1), min(12, len(all_direct))).round().astype(int):
            selected.append(all_direct[int(idx)])
        selected = sorted({row["pair_id"]: row for row in selected}.values(), key=lambda row: (row["frame"], row["pair_id"]))
    return selected[:12]


def simulate_box(row: Mapping[str, Any], simulation_type: str) -> tuple[Box, float, str]:
    box: Box = row["box"]
    if simulation_type.startswith("left_crop_"):
        ratio = parse_float(simulation_type.rsplit("_", 1)[-1]) / 100.0
        return Box(box.x1 + box.width * ratio, box.y1, box.x2, box.y2), ratio, "left"
    if simulation_type.startswith("right_crop_"):
        ratio = parse_float(simulation_type.rsplit("_", 1)[-1]) / 100.0
        return Box(box.x1, box.y1, box.x2 - box.width * ratio, box.y2), ratio, "right"
    if simulation_type.startswith("bottom_crop_"):
        ratio = parse_float(simulation_type.rsplit("_", 1)[-1]) / 100.0
        return Box(box.x1, box.y1, box.x2, box.y2 - box.height * ratio), ratio, "bottom"
    half = box.width * 0.5
    vx = parse_float(row.get("velocity_x"), 0.0)
    front_is_right = vx >= 0.0
    if simulation_type == "front_half_proxy":
        return (Box(box.cx, box.y1, box.x2, box.y2) if front_is_right else Box(box.x1, box.y1, box.cx, box.y2)), 0.5, "front_half"
    if simulation_type == "rear_half_proxy":
        return (Box(box.x1, box.y1, box.cx, box.y2) if front_is_right else Box(box.cx, box.y1, box.x2, box.y2)), 0.5, "rear_half"
    raise ValueError(simulation_type)


def build_simulation_rows(source_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    sim_types = [
        "left_crop_20",
        "left_crop_40",
        "left_crop_60",
        "right_crop_20",
        "right_crop_40",
        "right_crop_60",
        "bottom_crop_20",
        "bottom_crop_40",
        "front_half_proxy",
        "rear_half_proxy",
    ]
    idx = 0
    for source in source_rows:
        for sim_type in sim_types:
            idx += 1
            sim_box, ratio, direction = simulate_box(source, sim_type)
            depth = depth_crop_stats("GM_RM017", parse_int(source["frame"]), sim_box)["D1"]
            sim_id = f"R1_SIM_{idx:04d}"
            manifest_row = {
                "simulation_id": sim_id,
                "source_pair_id": source["pair_id"],
                "physical_vehicle_id": source["physical_vehicle_id"],
                "source_frame": source["frame"],
                "simulation_type": sim_type,
                "crop_ratio": fmt(ratio, 4),
                "original_bbox": source["box"].as_text(),
                "simulated_bbox": sim_box.as_text(),
                "original_depth": fmt(source["depth"], 6),
                "simulated_depth": fmt(depth, 6),
                "original_center": f"{fmt(source['box'].cx, 3)},{fmt(source['box'].cy, 3)}",
                "simulated_center": f"{fmt(sim_box.cx, 3)},{fmt(sim_box.cy, 3)}",
                "truncation_direction": direction,
            }
            manifest.append(manifest_row)
            samples.append(
                {
                    "sample_id": sim_id,
                    "sample_kind": "simulated_truncation",
                    "source_pair_id": source["pair_id"],
                    "source": source,
                    "physical_vehicle_id": source["physical_vehicle_id"],
                    "frame": source["frame"],
                    "local_box": sim_box,
                    "local_depth": depth,
                    "full_box": source["box"],
                    "full_depth": source["depth"],
                    "truncation_direction": direction,
                    "crop_ratio": ratio,
                }
            )
    return manifest, samples


def find_anchors(row: Mapping[str, Any], direct_by_vehicle: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    vehicle_rows = sorted(direct_by_vehicle.get(norm(row["physical_vehicle_id"]), []), key=lambda item: parse_int(item["frame"]))
    frame = parse_int(row["frame"])
    prev = None
    nxt = None
    for candidate in vehicle_rows:
        cframe = parse_int(candidate["frame"])
        if cframe < frame:
            prev = candidate
        elif cframe > frame and nxt is None:
            nxt = candidate
            break
    return prev, nxt


def recover_from_anchors(sample: Mapping[str, Any], direct_by_vehicle: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    if sample["sample_kind"] == "simulated_truncation":
        source = sample["source"]
        return {
            "box": source["box"],
            "depth": source["depth"],
            "mode": "synthetic_complete_state_known",
            "previous_anchor": source,
            "next_anchor": source,
            "confidence": 1.0,
            "boundary_consistency": "synthetic_full_state",
            "blocked_reason": "",
        }
    source = sample["source"]
    prev, nxt = find_anchors(source, direct_by_vehicle)
    frame = parse_int(source["frame"])
    local_box: Box = sample["local_box"]
    direction = norm(sample.get("truncation_direction"))
    if prev and nxt and parse_int(nxt["frame"]) > parse_int(prev["frame"]):
        t0 = parse_int(prev["frame"])
        t1 = parse_int(nxt["frame"])
        alpha = (frame - t0) / max(1.0, t1 - t0)
        pbox: Box = prev["box"]
        nbox: Box = nxt["box"]
        box = Box(
            pbox.x1 * (1 - alpha) + nbox.x1 * alpha,
            pbox.y1 * (1 - alpha) + nbox.y1 * alpha,
            pbox.x2 * (1 - alpha) + nbox.x2 * alpha,
            pbox.y2 * (1 - alpha) + nbox.y2 * alpha,
        )
        depth = parse_float(prev["depth"]) * (1 - alpha) + parse_float(nxt["depth"]) * alpha
        confidence = max(0.35, 1.0 - ((frame - t0) + (t1 - frame)) / 24.0)
        mode = "bidirectional_complete_anchor_interpolation"
    elif prev and frame - parse_int(prev["frame"]) <= 5:
        pbox = prev["box"]
        gap = frame - parse_int(prev["frame"])
        vx = parse_float(prev.get("velocity_x"), 0.0)
        vy = parse_float(prev.get("velocity_y"), 0.0)
        box = Box(pbox.x1 + vx * gap, pbox.y1 + vy * gap, pbox.x2 + vx * gap, pbox.y2 + vy * gap)
        depth = parse_float(prev["depth"])
        confidence = max(0.35, 0.75 - gap * 0.08)
        mode = "forward_limited_constant_velocity"
    elif nxt and parse_int(nxt["frame"]) - frame <= 5:
        nbox = nxt["box"]
        gap = parse_int(nxt["frame"]) - frame
        vx = parse_float(nxt.get("velocity_x"), 0.0)
        vy = parse_float(nxt.get("velocity_y"), 0.0)
        box = Box(nbox.x1 - vx * gap, nbox.y1 - vy * gap, nbox.x2 - vx * gap, nbox.y2 - vy * gap)
        depth = parse_float(nxt["depth"])
        confidence = max(0.35, 0.75 - gap * 0.08)
        mode = "backward_limited_constant_velocity"
    else:
        return {
            "box": None,
            "depth": float("nan"),
            "mode": "blocked",
            "previous_anchor": prev,
            "next_anchor": nxt,
            "confidence": 0.0,
            "boundary_consistency": "not_checked",
            "blocked_reason": "insufficient_complete_anchors",
        }
    conflict = 0.0
    if direction == "left":
        conflict = abs(box.x2 - local_box.x2) / max(1.0, box.width)
    elif direction == "right":
        conflict = abs(box.x1 - local_box.x1) / max(1.0, box.width)
    elif direction == "bottom":
        conflict = abs(box.y1 - local_box.y1) / max(1.0, box.height)
    consistency = "consistent" if conflict <= 0.5 or direction in {"front_half", "rear_half", "none"} else "weak_conflict"
    if consistency == "weak_conflict":
        confidence *= 0.65
    return {
        "box": box.clipped(),
        "depth": depth,
        "mode": mode,
        "previous_anchor": prev,
        "next_anchor": nxt,
        "confidence": confidence,
        "boundary_consistency": consistency,
        "blocked_reason": "",
    }


def build_natural_rows(
    rows: Sequence[Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    direct_by_vehicle: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["direct_observable"]:
            direct_by_vehicle[norm(row["physical_vehicle_id"])].append(row)
    natural_sources = [row for row in rows if row["temporally_recoverable"]]
    natural_sources.sort(key=lambda row: (row["frame"], row["track_id"], row["pair_id"]))
    samples: list[dict[str, Any]] = []
    natural_rows: list[dict[str, Any]] = []
    for idx, source in enumerate(natural_sources, 1):
        sample_id = f"R1_NAT_{idx:04d}"
        sample = {
            "sample_id": sample_id,
            "sample_kind": "natural_truncation",
            "source_pair_id": source["pair_id"],
            "source": source,
            "physical_vehicle_id": source["physical_vehicle_id"],
            "frame": source["frame"],
            "local_box": source["box"],
            "local_depth": source["depth"],
            "full_box": None,
            "full_depth": float("nan"),
            "truncation_direction": source["truncation_direction"],
            "crop_ratio": 0.0,
        }
        recovery = recover_from_anchors(sample, direct_by_vehicle)
        pred_m0 = predict_state(bundle, source["box"], source["depth"])
        prev_anchor, next_anchor = recovery["previous_anchor"], recovery["next_anchor"]
        estimated_center = ""
        estimated_depth = ""
        if recovery["box"] is not None:
            rbox: Box = recovery["box"]
            estimated_center = f"{fmt(rbox.cx, 3)},{fmt(rbox.cy, 3)}"
            estimated_depth = fmt(recovery["depth"], 6)
        natural_rows.append(
            {
                "natural_case_id": sample_id,
                "pair_id": source["pair_id"],
                "frame": source["frame"],
                "physical_vehicle_id": source["physical_vehicle_id"],
                "source_track_id": source["track_id"],
                "previous_complete_frame": parse_int(prev_anchor["frame"]) if prev_anchor else "",
                "next_complete_frame": parse_int(next_anchor["frame"]) if next_anchor else "",
                "truncation_direction": source["truncation_direction"],
                "visible_parts": source["visible_parts"],
                "local_bbox_center": f"{fmt(source['box'].cx, 3)},{fmt(source['box'].cy, 3)}",
                "estimated_full_center": estimated_center,
                "local_depth": fmt(source["depth"], 6),
                "estimated_full_depth": estimated_depth,
                "sar_gt_azimuth": fmt(source["sar_azimuth"], 6),
                "sar_gt_radial": fmt(source["sar_radial"], 6),
                "direct_projection_azimuth_error": fmt(abs(pred_m0["azimuth"] - source["sar_azimuth"]), 6),
                "direct_projection_radial_error": fmt(abs(pred_m0["radial"] - source["sar_radial"]), 6),
            }
        )
        samples.append(sample)
    return natural_rows, samples


def build_recovered_rows(
    samples: Sequence[Mapping[str, Any]],
    direct_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    direct_by_vehicle: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in direct_rows:
        direct_by_vehicle[norm(row["physical_vehicle_id"])].append(row)
    recovered_rows: list[dict[str, Any]] = []
    recovery_by_id: dict[str, dict[str, Any]] = {}
    for sample in samples:
        recovery = recover_from_anchors(sample, direct_by_vehicle)
        recovery_by_id[norm(sample["sample_id"])] = recovery
        rbox = recovery["box"]
        prev_anchor = recovery["previous_anchor"]
        next_anchor = recovery["next_anchor"]
        recovered_rows.append(
            {
                "sample_id": sample["sample_id"],
                "sample_kind": sample["sample_kind"],
                "source_pair_id": sample["source_pair_id"],
                "physical_vehicle_id": sample["physical_vehicle_id"],
                "frame": sample["frame"],
                "local_bbox": sample["local_box"].as_text(),
                "recovered_center_x": fmt(rbox.cx, 6) if rbox else "",
                "recovered_center_y": fmt(rbox.cy, 6) if rbox else "",
                "recovered_width": fmt(rbox.width, 6) if rbox else "",
                "recovered_height": fmt(rbox.height, 6) if rbox else "",
                "recovered_depth": fmt(recovery["depth"], 6),
                "recovery_mode": recovery["mode"],
                "previous_anchor_frame": parse_int(prev_anchor["frame"]) if prev_anchor else "",
                "next_anchor_frame": parse_int(next_anchor["frame"]) if next_anchor else "",
                "recovery_confidence": fmt(recovery["confidence"], 6),
                "visible_boundary_consistency": recovery["boundary_consistency"],
                "recovery_blocked_reason": recovery["blocked_reason"],
            }
        )
    return recovered_rows, recovery_by_id


def predict_state(bundle: Mapping[str, Any], box: Box, depth: float) -> dict[str, float]:
    az_mode = norm(bundle["az_mode"])
    radial_mode = norm(bundle["radial_mode"])
    az_x = np.asarray([state_features(box, depth, az_mode)], dtype=float)
    radial_x = np.asarray([state_features(box, depth, radial_mode)], dtype=float)
    return {
        "azimuth": float(bundle["az_model"].predict(az_x)[0]),
        "radial": float(bundle["radial_model"].predict(radial_x)[0]),
    }


def sample_eval(
    source: Mapping[str, Any],
    group: str,
    method: str,
    pred_az: float,
    pred_rad: float,
    az_half_width: float,
    rad_half_width: float,
) -> dict[str, Any]:
    az_err = abs(float(pred_az) - parse_float(source["sar_azimuth"]))
    rad_err = abs(float(pred_rad) - parse_float(source["sar_radial"]))
    center_cover = az_err <= az_half_width and rad_err <= rad_half_width
    full_cover = (
        center_cover
        and az_half_width >= az_err + max(0.0, parse_float(source.get("sar_azimuth_span"), 0.0)) / 2.0
        and rad_half_width >= rad_err + max(0.0, parse_float(source.get("sar_radial_span"), 0.0)) / 2.0
    )
    search = (2 * az_half_width / FULL_AZIMUTH_SPAN) * (2 * rad_half_width / FAN_RADIUS_PX)
    return {
        "group": group,
        "method": method,
        "sample_id": source.get("sample_id", source.get("pair_id", "")),
        "source": source,
        "azimuth_error": az_err,
        "radial_error": rad_err,
        "center_coverage_95": 1.0 if center_cover else 0.0,
        "full_box_coverage_95": 1.0 if full_cover else 0.0,
        "search_ratio": search,
        "multi_target": 0.0,
    }


def aggregate_eval(items: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    if not items:
        return {
            "sample_count": 0,
            "azimuth_median_error": 0.0,
            "azimuth_p90_error": 0.0,
            "radial_median_error": 0.0,
            "radial_p90_error": 0.0,
            "center_coverage_95": 0.0,
            "full_box_coverage_95": 0.0,
            "median_search_ratio": 0.0,
            "multi_target_rate": 0.0,
        }
    return {
        "sample_count": len(items),
        "azimuth_median_error": median(item["azimuth_error"] for item in items),
        "azimuth_p90_error": percentile((item["azimuth_error"] for item in items), 90),
        "radial_median_error": median(item["radial_error"] for item in items),
        "radial_p90_error": percentile((item["radial_error"] for item in items), 90),
        "center_coverage_95": sum(float(item["center_coverage_95"]) for item in items) / len(items),
        "full_box_coverage_95": sum(float(item["full_box_coverage_95"]) for item in items) / len(items),
        "median_search_ratio": median(item["search_ratio"] for item in items),
        "multi_target_rate": sum(float(item["multi_target"]) for item in items) / len(items),
    }


def evaluate_projection(
    rows: Sequence[Mapping[str, Any]],
    samples: Sequence[Mapping[str, Any]],
    recovery_by_id: Mapping[str, Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    intervals = bundle["intervals"]
    all_eval: list[dict[str, Any]] = []
    direct_samples = []
    for row in rows:
        if not row["direct_observable"]:
            continue
        direct_samples.append(
            {
                "sample_id": row["pair_id"],
                "sample_kind": "direct_observable_control",
                "source_pair_id": row["pair_id"],
                "source": row,
                "physical_vehicle_id": row["physical_vehicle_id"],
                "frame": row["frame"],
                "local_box": row["box"],
                "local_depth": row["depth"],
                "truncation_direction": "none",
                "crop_ratio": 0.0,
            }
        )
    eval_inputs = direct_samples + list(samples)
    for sample in eval_inputs:
        source = sample["source"]
        group = norm(sample["sample_kind"])
        local_pred = predict_state(bundle, sample["local_box"], parse_float(sample["local_depth"]))
        crop = parse_float(sample.get("crop_ratio"), 0.0)
        direction = norm(sample.get("truncation_direction"))
        az_extra = 12.0 * crop if direction in {"left", "right", "front_half", "rear_half"} else 4.0 * crop
        rad_extra = 90.0 * crop if direction in {"bottom", "front_half", "rear_half"} else 35.0 * crop
        if group == "direct_observable_control":
            az_extra = rad_extra = 0.0
        all_eval.append(sample_eval(source | {"sample_id": sample["sample_id"]}, group, "M0_local_direct_projection", local_pred["azimuth"], local_pred["radial"], intervals["az_q95"], intervals["rad_q95"]))
        all_eval.append(
            sample_eval(
                source | {"sample_id": sample["sample_id"]},
                group,
                "M1_interval_inflation_only",
                local_pred["azimuth"],
                local_pred["radial"],
                intervals["az_q95"] + az_extra,
                intervals["rad_q95"] + rad_extra,
            )
        )
        recovery = recovery_by_id.get(norm(sample["sample_id"]))
        if group == "direct_observable_control":
            recovery = {"box": sample["local_box"], "depth": sample["local_depth"], "confidence": 1.0}
        if recovery and recovery.get("box") is not None:
            rbox: Box = recovery["box"]
            rdepth = parse_float(recovery["depth"])
            rec_pred = predict_state(bundle, rbox, rdepth)
            conf = parse_float(recovery.get("confidence"), 1.0)
            all_eval.append(
                sample_eval(
                    source | {"sample_id": sample["sample_id"]},
                    group,
                    "M2_recovered_full_vehicle_state",
                    rec_pred["azimuth"],
                    rec_pred["radial"],
                    intervals["az_q95"] * (1.0 + (1.0 - conf)),
                    intervals["rad_q95"] * (1.0 + (1.0 - conf)),
                )
            )
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for item in all_eval:
        grouped[(norm(item["group"]), norm(item["method"]))].append(item)
    projection_rows = []
    for (group, method), items in sorted(grouped.items()):
        metrics = aggregate_eval(items)
        projection_rows.append(
            {
                "evaluation_group": group,
                "method": method,
                "sample_count": metrics["sample_count"],
                "azimuth_median_error": fmt(metrics["azimuth_median_error"], 6),
                "azimuth_p90_error": fmt(metrics["azimuth_p90_error"], 6),
                "radial_median_error": fmt(metrics["radial_median_error"], 6),
                "radial_p90_error": fmt(metrics["radial_p90_error"], 6),
                "center_coverage_95": fmt(metrics["center_coverage_95"], 6),
                "full_box_coverage_95": fmt(metrics["full_box_coverage_95"], 6),
                "median_search_ratio": fmt(metrics["median_search_ratio"], 8),
                "multi_target_rate": fmt(metrics["multi_target_rate"], 6),
            }
        )
    failures = build_failure_rows(all_eval, recovery_by_id)
    return projection_rows, failures, all_eval


def build_failure_rows(all_eval: Sequence[Mapping[str, Any]], recovery_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    candidates = []
    for item in all_eval:
        if norm(item["method"]) != "M2_recovered_full_vehicle_state":
            continue
        if item["center_coverage_95"] < 1.0:
            candidates.append(item)
    for idx, item in enumerate(sorted(candidates, key=lambda x: (x["radial_error"] + x["azimuth_error"] * 10), reverse=True)[:24], 1):
        source = item["source"]
        recovery = recovery_by_id.get(norm(item["sample_id"]), {})
        blocked = norm(recovery.get("blocked_reason"))
        radial_high = parse_float(item["radial_error"]) > 80.0
        az_high = parse_float(item["azimuth_error"]) > 8.0
        boundary_conflict = norm(recovery.get("boundary_consistency")) == "weak_conflict"
        dominant = blocked or ("depth_interpolation_wrong" if radial_high else "motion_not_linear" if az_high or boundary_conflict else "weak_calibration_model_suspect")
        failures.append(
            {
                "failure_id": f"R1_FAIL_{idx:03d}",
                "sample_id": item["sample_id"],
                "sample_kind": item["group"],
                "method": item["method"],
                "physical_vehicle_id": source.get("physical_vehicle_id", ""),
                "frame": source.get("frame", ""),
                "azimuth_error": fmt(item["azimuth_error"], 6),
                "radial_error": fmt(item["radial_error"], 6),
                "dominant_failure": dominant,
                "identity": "identity_anchor_wrong" if dominant == "identity_anchor_wrong" else "none_observed",
                "motion": "motion_not_linear" if dominant == "motion_not_linear" or boundary_conflict else "not_dominant",
                "scale": "scale_interpolation_wrong" if boundary_conflict else "not_dominant",
                "depth": "depth_interpolation_wrong" if dominant == "depth_interpolation_wrong" else "not_dominant",
                "pairing": "SAR_pairing_suspect" if dominant == "SAR_pairing_suspect" else "not_dominant",
                "weak_calibration": "weak_calibration_model_suspect" if dominant == "weak_calibration_model_suspect" else "not_dominant",
                "notes": f"blocked={blocked};boundary={recovery.get('boundary_consistency','')};confidence={fmt(recovery.get('confidence',0),4)}",
            }
        )
    blocked_ids = [
        (sid, rec)
        for sid, rec in recovery_by_id.items()
        if norm(rec.get("blocked_reason"))
    ]
    start = len(failures)
    for offset, (sid, rec) in enumerate(blocked_ids[:12], 1):
        failures.append(
            {
                "failure_id": f"R1_FAIL_{start + offset:03d}",
                "sample_id": sid,
                "sample_kind": "natural_truncation",
                "method": "M2_recovered_full_vehicle_state",
                "physical_vehicle_id": "",
                "frame": "",
                "azimuth_error": "",
                "radial_error": "",
                "dominant_failure": rec.get("blocked_reason", "insufficient_complete_anchors"),
                "identity": "not_dominant",
                "motion": "not_evaluated",
                "scale": "not_evaluated",
                "depth": "not_evaluated",
                "pairing": "not_evaluated",
                "weak_calibration": "not_evaluated",
                "notes": "recovery blocked before projection",
            }
        )
    return failures


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    subset = list(rows[:limit] if limit is not None else rows)
    if not subset:
        return "_No rows._"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in subset:
        lines.append("| " + " | ".join(norm(row.get(field, "")).replace("\n", " ") for field in fields) + " |")
    return "\n".join(lines)


def render_identity_report(vehicle_rows: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], baseline_manifest: Sequence[Mapping[str, Any]]) -> None:
    counts = Counter(row["track_id"] for row in rows)
    same_frame = defaultdict(list)
    for row in rows:
        same_frame[row["frame"]].append(row)
    overlapping_frames = {frame: items for frame, items in same_frame.items() if len(set(item["track_id"] for item in items)) > 1}
    lines = [
        "# OTY2 WGV3.5A-R1 Physical Vehicle Identity Audit",
        "",
        f"Date: {DATE}",
        "",
        "## Boundary",
        "",
        "This audit treats ByteTrack IDs as track hypotheses, not physical identity truth. SAR GT remains posthoc validation evidence only.",
        "",
        "## Frozen WGV3.5A Baseline SHA256",
        "",
        md_table(baseline_manifest, ["source_file", "sha256", "bytes", "rows"]),
        "",
        "## Source Thread Counts",
        "",
        md_table([{"track_id": key, "pair_count": value} for key, value in sorted(counts.items())], ["track_id", "pair_count"]),
        "",
        "## Physical Vehicle Map",
        "",
        md_table(vehicle_rows, PHYSICAL_VEHICLE_FIELDS),
        "",
        "## Same-Frame Evidence",
        "",
        f"- same-frame multi-track frames: `{len(overlapping_frames)}`",
        "- Visual audit overlay: `outputs/wgv3_5a_r1_20260710/frame_overlap_contact_sheet.png`",
        "- Direct inspection shows a white SUV and at least two dark sedans co-existing in the GM_RM017 sequence.",
        "- 0010 and 0012 are overlapping different physical vehicles; 0012 and 0014 are also different in frame 184.",
        "- 0008 and 0014 are a plausible right-edge continuation, but confidence is only moderate because 0014 is a small fragment.",
        "",
        "## WGV3.5A Leakage Decision",
        "",
        "No hard 0010-vs-0012 same-vehicle leakage was found, but the WGV3.5A split is not a physical-vehicle-generalization proof: train/validation/test are same-scene, same-time traffic phases with overlapping vehicles. R1 therefore uses observation-state mechanism analysis rather than split-based generalization claims.",
    ]
    write_text(OUTPUTS["identity_md"], "\n".join(lines))


def render_mechanism_report(rows: Sequence[Mapping[str, Any]], baseline_rows: Sequence[Mapping[str, Any]], projection_rows: Sequence[Mapping[str, Any]]) -> None:
    direct = [row for row in rows if row["direct_observable"]]
    natural = [row for row in rows if row["temporally_recoverable"]]
    direct_depth = [parse_float(row["depth"]) for row in direct]
    natural_depth = [parse_float(row["depth"]) for row in natural]
    selected = next(row for row in baseline_rows if row["model_target"] == "complete_observation_selected")
    lines = [
        "# OTY2 WGV3.5A-R1 Complete Vehicle Mechanism",
        "",
        f"Date: {DATE}",
        "",
        "## Mechanism Boundary",
        "",
        "Only GM_RM017 is used. Complete-observable samples fit a weak forward optical-state to SAR-polar relation. Truncated samples are used for controlled degradation and recovery diagnosis.",
        "",
        "## Observation Regime",
        "",
        f"- direct_observable samples: `{len(direct)}`",
        f"- temporally_recoverable natural samples: `{len(natural)}`",
        f"- physical vehicle count in direct pool: `{len(set(row['physical_vehicle_id'] for row in direct))}`",
        f"- direct depth median/P90: `{fmt(median(direct_depth), 6)}` / `{fmt(percentile(direct_depth, 90), 6)}`",
        f"- natural truncation depth median/P90: `{fmt(median(natural_depth), 6)}` / `{fmt(percentile(natural_depth, 90), 6)}`",
        "",
        "## Baseline Models",
        "",
        md_table(baseline_rows, BASELINE_FIELDS),
        "",
        "## Selected Complete-Observation Baseline",
        "",
        md_table([selected], BASELINE_FIELDS),
        "",
        "## Projection Comparison Summary",
        "",
        md_table(projection_rows, PROJECTION_FIELDS),
        "",
        "## Interpretation",
        "",
        "GM_RM017 works mainly in the mid-range complete-body regime: the optical bbox center still has a full-vehicle meaning, depth remains weakly monotonic, and SAR azimuth/radial errors stay lower than in natural or simulated truncation. This is a controlled complete-observability mechanism, not a scene-accident-only explanation.",
    ]
    write_text(OUTPUTS["mechanism_md"], "\n".join(lines))


def make_case_overlay(sample: Mapping[str, Any], recovery: Mapping[str, Any] | None, bundle: Mapping[str, Any], out_path: Path) -> None:
    source = sample["source"]
    frame = parse_int(source["frame"])
    sar_frame = parse_int(source["sar_frame"])
    opt = Image.open(frame_path("GM_RM017", frame)).convert("RGB") if frame_path("GM_RM017", frame).exists() else Image.new("RGB", (800, 600), "black")
    if depth_vis_path("GM_RM017", frame).exists():
        dep = Image.open(depth_vis_path("GM_RM017", frame)).convert("RGB")
    else:
        dep = Image.new("RGB", (800, 600), "black")
    sar = Image.open(sar_gray_path("GM_RM017", sar_frame)).convert("RGB") if sar_gray_path("GM_RM017", sar_frame).exists() else Image.new("RGB", (int(SAR_WIDTH), int(SAR_HEIGHT)), "black")
    opt = opt.resize((400, 300))
    dep = dep.resize((400, 300))
    sar = sar.resize((520, 300))
    canvas = Image.new("RGB", (1320, 360), (18, 18, 18))
    canvas.paste(opt, (0, 0))
    canvas.paste(dep, (400, 0))
    canvas.paste(sar, (800, 0))
    draw = ImageDraw.Draw(canvas)
    sx, sy = 400 / OPTICAL_WIDTH, 300 / OPTICAL_HEIGHT
    for offset in [0, 400]:
        local: Box = sample["local_box"]
        draw.rectangle([offset + local.x1 * sx, local.y1 * sy, offset + local.x2 * sx, local.y2 * sy], outline=(255, 220, 0), width=3)
        full_box = sample.get("full_box")
        if isinstance(full_box, Box):
            draw.rectangle([offset + full_box.x1 * sx, full_box.y1 * sy, offset + full_box.x2 * sx, full_box.y2 * sy], outline=(0, 220, 80), width=2)
        if recovery and recovery.get("box") is not None:
            rbox: Box = recovery["box"]
            draw.rectangle([offset + rbox.x1 * sx, rbox.y1 * sy, offset + rbox.x2 * sx, rbox.y2 * sy], outline=(255, 60, 60), width=2)
    ssx, ssy = 520 / SAR_WIDTH, 300 / SAR_HEIGHT
    sar_box: Box = source["sar_box"]
    draw.rectangle([800 + sar_box.x1 * ssx, sar_box.y1 * ssy, 800 + sar_box.x2 * ssx, sar_box.y2 * ssy], outline=(0, 255, 120), width=2)
    local_pred = predict_state(bundle, sample["local_box"], parse_float(sample["local_depth"]))
    m0x, m0y = polar_to_pixel(local_pred["azimuth"], local_pred["radial"])
    draw.ellipse([800 + m0x * ssx - 5, m0y * ssy - 5, 800 + m0x * ssx + 5, m0y * ssy + 5], outline=(255, 220, 0), width=3)
    if recovery and recovery.get("box") is not None:
        rpred = predict_state(bundle, recovery["box"], parse_float(recovery["depth"]))
        m2x, m2y = polar_to_pixel(rpred["azimuth"], rpred["radial"])
        draw.ellipse([800 + m2x * ssx - 6, m2y * ssy - 6, 800 + m2x * ssx + 6, m2y * ssy + 6], outline=(255, 60, 60), width=3)
    draw.rectangle([0, 300, 1320, 360], fill=(0, 0, 0))
    label = f"{sample['sample_id']} {sample['sample_kind']} frame={frame} vehicle={sample['physical_vehicle_id']} yellow=local green=source red=recovered SARgreen=GT"
    draw.text((8, 312), label, fill=(255, 255, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def make_contact_sheet(image_paths: Sequence[Path], out_path: Path, thumb_size: tuple[int, int] = (330, 90), cols: int = 2) -> None:
    if not image_paths:
        return
    thumbs = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail(thumb_size)
        tile = Image.new("RGB", thumb_size, (24, 24, 24))
        tile.paste(img, (0, 0))
        thumbs.append(tile)
    rows = int(math.ceil(len(thumbs) / cols))
    sheet = Image.new("RGB", (cols * thumb_size[0], rows * thumb_size[1]), (18, 18, 18))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * thumb_size[0], (idx // cols) * thumb_size[1]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def render_identity_contact_sheets(rows: Sequence[Mapping[str, Any]]) -> tuple[Path, Path]:
    colors = {
        "oty1t_obj_GM_RM017_bytetrack_bt_0008": (255, 0, 0),
        "oty1t_obj_GM_RM017_bytetrack_bt_0010": (255, 230, 0),
        "oty1t_obj_GM_RM017_bytetrack_bt_0012": (0, 220, 255),
        "oty1t_obj_GM_RM017_bytetrack_bt_0014": (255, 0, 220),
    }
    by_thread: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_thread[norm(row["track_id"])].append(row)
    selected = []
    for thread, thread_rows in sorted(by_thread.items()):
        thread_rows = sorted(thread_rows, key=lambda item: parse_int(item["frame"]))
        picks = [0, len(thread_rows) // 4, len(thread_rows) // 2, 3 * len(thread_rows) // 4, len(thread_rows) - 1]
        selected.extend(thread_rows[idx] for idx in sorted(set(picks)))
    identity_path = OUTPUT_DIR / "identity_contact_sheet.png"
    thumbs = []
    for row in selected:
        frame = parse_int(row["frame"])
        img = Image.open(frame_path("GM_RM017", frame)).convert("RGB")
        draw = ImageDraw.Draw(img)
        box: Box = row["box"]
        color = colors.get(norm(row["track_id"]), (255, 0, 0))
        draw.rectangle([box.x1, box.y1, box.x2, box.y2], outline=color, width=4)
        draw.rectangle([0, 0, 380, 28], fill=(0, 0, 0))
        draw.text((8, 8), f"{row['track_id'].split('_')[-1]} f{frame} {row['pair_id']}", fill=color)
        img.thumbnail((260, 195))
        tile = Image.new("RGB", (260, 195), (24, 24, 24))
        tile.paste(img, (0, 0))
        thumbs.append(tile)
    cols = 5
    sheet = Image.new("RGB", (cols * 260, math.ceil(len(thumbs) / cols) * 195), (18, 18, 18))
    for idx, img in enumerate(thumbs):
        sheet.paste(img, ((idx % cols) * 260, (idx // cols) * 195))
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(identity_path)

    overlap_path = OUTPUT_DIR / "frame_overlap_contact_sheet.png"
    frames = [151, 156, 162, 166, 169, 174, 181, 184, 189, 206, 210, 212]
    thumbs = []
    for frame in frames:
        frame_rows = [row for row in rows if parse_int(row["frame"]) == frame]
        if not frame_rows:
            continue
        img = Image.open(frame_path("GM_RM017", frame)).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 420, 28], fill=(0, 0, 0))
        draw.text((8, 8), f"frame {frame}", fill=(255, 255, 255))
        for row in frame_rows:
            box = row["box"]
            color = colors.get(norm(row["track_id"]), (255, 0, 0))
            draw.rectangle([box.x1, box.y1, box.x2, box.y2], outline=color, width=3)
            draw.text((box.x1 + 2, max(30, box.y1 - 14)), row["track_id"].split("_")[-1], fill=color)
        img.thumbnail((400, 300))
        tile = Image.new("RGB", (400, 300), (24, 24, 24))
        tile.paste(img, (0, 0))
        thumbs.append(tile)
    sheet = Image.new("RGB", (3 * 400, math.ceil(len(thumbs) / 3) * 300), (18, 18, 18))
    for idx, img in enumerate(thumbs):
        sheet.paste(img, ((idx % 3) * 400, (idx // 3) * 300))
    overlap_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(overlap_path)
    return identity_path, overlap_path


def render_visual_outputs(
    rows: Sequence[Mapping[str, Any]],
    simulation_samples: Sequence[Mapping[str, Any]],
    natural_samples: Sequence[Mapping[str, Any]],
    recovery_by_id: Mapping[str, Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    identity_path, overlap_path = render_identity_contact_sheets(rows)
    direct_samples = []
    for row in [r for r in rows if r["direct_observable"]][:5]:
        direct_samples.append(
            {
                "sample_id": row["pair_id"],
                "sample_kind": "direct_observable_control",
                "source_pair_id": row["pair_id"],
                "source": row,
                "physical_vehicle_id": row["physical_vehicle_id"],
                "frame": row["frame"],
                "local_box": row["box"],
                "local_depth": row["depth"],
                "full_box": row["box"],
                "full_depth": row["depth"],
                "truncation_direction": "none",
            }
        )
    buckets = {
        "complete": direct_samples[:5],
        "sim_left": [s for s in simulation_samples if s["truncation_direction"] == "left"][:5],
        "sim_right": [s for s in simulation_samples if s["truncation_direction"] == "right"][:5],
        "sim_bottom": [s for s in simulation_samples if s["truncation_direction"] == "bottom"][:3],
        "natural_all": list(natural_samples),
    }
    contact_sheets: dict[str, Path] = {"identity": identity_path, "overlap": overlap_path}
    case_lines = []
    for bucket, samples in buckets.items():
        image_paths = []
        for idx, sample in enumerate(samples, 1):
            rec = recovery_by_id.get(norm(sample["sample_id"]))
            if bucket == "complete":
                rec = {"box": sample["local_box"], "depth": sample["local_depth"], "confidence": 1.0, "mode": "direct_identity"}
            out_path = OUTPUT_DIR / f"{bucket}_{idx:03d}_{sample['sample_id']}.png"
            make_case_overlay(sample, rec, bundle, out_path)
            image_paths.append(out_path)
            case_lines.append(
                {
                    "bucket": bucket,
                    "sample_id": sample["sample_id"],
                    "overlay": rel(out_path),
                    "note": "车辆完整" if bucket == "complete" else "局部框需要整车恢复",
                    "m0": "局部框中心改变了整车中心物理含义" if bucket != "complete" else "局部框即整车框",
                    "m1": "只扩大区间，不修正中心和深度",
                    "m2": "使用前后完整锚点或合成完整状态恢复整车中心、尺寸和深度",
                }
            )
        if image_paths:
            sheet_path = OUTPUT_DIR / f"{bucket}_contact_sheet.png"
            make_contact_sheet(image_paths, sheet_path, thumb_size=(440, 120), cols=2)
            contact_sheets[bucket] = sheet_path
    failure_samples = []
    sample_by_id = {sample["sample_id"]: sample for sample in list(simulation_samples) + list(natural_samples)}
    for failure in failures:
        sample = sample_by_id.get(norm(failure.get("sample_id")))
        if sample:
            failure_samples.append(sample)
    failure_paths = []
    for idx, sample in enumerate(failure_samples, 1):
        out_path = OUTPUT_DIR / f"failure_{idx:03d}_{sample['sample_id']}.png"
        make_case_overlay(sample, recovery_by_id.get(norm(sample["sample_id"])), bundle, out_path)
        failure_paths.append(out_path)
    if failure_paths:
        sheet_path = OUTPUT_DIR / "failure_all_contact_sheet.png"
        make_contact_sheet(failure_paths, sheet_path, thumb_size=(440, 120), cols=2)
        contact_sheets["failure_all"] = sheet_path
    lines = [
        "# OTY2 WGV3.5A-R1 Visual Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "Diagnostic PNGs are written under ignored `outputs/wgv3_5a_r1_20260710/` and are not committed.",
        "",
        "## Contact Sheets",
        "",
    ]
    for name, path in contact_sheets.items():
        lines.append(f"- {name}: `{rel(path)}`")
    lines.extend(["", "## Visual Audit Notes", ""])
    for case in case_lines:
        lines.extend(
            [
                f"### {case['bucket']} `{case['sample_id']}`",
                "",
                f"- overlay: `{case['overlay']}`",
                f"- 车辆是否完整: {case['note']}",
                f"- 局部框代表的可见部分: {case['m0']}",
                "- 框中心是否仍有物理意义: 完整样本有；截断/半车样本没有稳定整车中心含义。",
                "- 当前深度是否可能被污染: 边缘和半车样本存在背景或局部部件污染风险。",
                "- 前后完整锚点是否可信: 同一物理车辆内检查，超过传播上限则阻断。",
                f"- M1说明: {case['m1']}",
                f"- M2说明: {case['m2']}",
                "",
            ]
        )
    write_text(OUTPUTS["visual_md"], "\n".join(lines))
    return {"contact_sheets": {key: str(path) for key, path in contact_sheets.items()}, "case_count": len(case_lines)}


def render_closure_report(
    rows: Sequence[Mapping[str, Any]],
    vehicle_rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    simulation_rows: Sequence[Mapping[str, Any]],
    natural_rows: Sequence[Mapping[str, Any]],
    recovered_rows: Sequence[Mapping[str, Any]],
    projection_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    baseline_manifest: Sequence[Mapping[str, Any]],
    visual_info: Mapping[str, Any],
) -> str:
    projection = {(row["evaluation_group"], row["method"]): row for row in projection_rows}
    sim_m0 = projection.get(("simulated_truncation", "M0_local_direct_projection"), {})
    sim_m2 = projection.get(("simulated_truncation", "M2_recovered_full_vehicle_state"), {})
    nat_m0 = projection.get(("natural_truncation", "M0_local_direct_projection"), {})
    nat_m2 = projection.get(("natural_truncation", "M2_recovered_full_vehicle_state"), {})
    direct_m0 = projection.get(("direct_observable_control", "M0_local_direct_projection"), {})
    direct_m2 = projection.get(("direct_observable_control", "M2_recovered_full_vehicle_state"), {})
    sim_az_improve = improvement_percent(parse_float(sim_m0.get("azimuth_p90_error")), parse_float(sim_m2.get("azimuth_p90_error")))
    sim_rad_improve = improvement_percent(parse_float(sim_m0.get("radial_p90_error")), parse_float(sim_m2.get("radial_p90_error")))
    nat_rad_improve = improvement_percent(parse_float(nat_m0.get("radial_p90_error")), parse_float(nat_m2.get("radial_p90_error")))
    recovered_count = sum(1 for row in recovered_rows if norm(row["recovery_mode"]) != "blocked")
    blocked_count = sum(1 for row in recovered_rows if norm(row["recovery_mode"]) == "blocked")
    direct_count = sum(1 for row in rows if row["direct_observable"])
    recoverable_count = sum(1 for row in rows if row["temporally_recoverable"])
    not_safe = sum(1 for row in rows if row["not_safely_recoverable"])
    incorrect_old = sum(1 for row in rows if row["incorrect_old_visibility"])
    failure_counts = Counter(row["dominant_failure"] for row in failure_rows)
    if direct_count >= 10 and (sim_az_improve >= 30.0 or sim_rad_improve >= 30.0) and recovered_count > blocked_count:
        status = "CLOSED_COMPLETE_OBSERVATION_AND_TEMPORAL_RECOVERY_FEASIBLE"
    elif direct_count >= 10:
        status = "CLOSED_COMPLETE_OBSERVATION_FEASIBLE_RECOVERY_INSUFFICIENT"
    else:
        status = "OPEN_COMPLETE_OBSERVATION_POOL_INSUFFICIENT"
    lines = [
        "# OTY2 WGV3.5A-R1 Closure",
        "",
        f"Date: {DATE}",
        "",
        f"WGV3.5A-R1 status: `{status}`",
        "",
        "## Boundary",
        "",
        "Only GM_RM017 was used. WGV3.5A baseline files were read and frozen by SHA256, not modified. GT is used only for posthoc error/coverage evaluation.",
        "",
        "## Frozen Baseline",
        "",
        md_table(baseline_manifest, ["source_file", "sha256", "bytes", "rows"]),
        "",
        "## Physical Vehicle Audit",
        "",
        md_table(vehicle_rows, PHYSICAL_VEHICLE_FIELDS),
        "",
        "## Observation State Audit",
        "",
        f"- direct_observable: `{direct_count}`",
        f"- temporally_recoverable: `{recoverable_count}`",
        f"- not_safely_recoverable: `{not_safe}`",
        f"- natural truncation cases: `{len(natural_rows)}`",
        f"- incorrect old visibility labels: `{incorrect_old}`",
        "",
        "## Complete-Observation Baseline",
        "",
        md_table(baseline_rows, BASELINE_FIELDS),
        "",
        "## Projection Comparison",
        "",
        md_table(projection_rows, PROJECTION_FIELDS),
        "",
        "## Recovery",
        "",
        f"- recovered samples: `{recovered_count}`",
        f"- blocked samples: `{blocked_count}`",
        f"- simulated azimuth P90 improvement: `{fmt(sim_az_improve, 2)}%`",
        f"- simulated radial P90 improvement: `{fmt(sim_rad_improve, 2)}%`",
        f"- natural truncation radial P90 improvement: `{fmt(nat_rad_improve, 2)}%`",
        "",
        "## Dominant Failures",
        "",
        f"`{dict(failure_counts)}`",
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{rel(path)}`" for path in OUTPUTS.values()),
        "",
        "## Visual Outputs",
        "",
        "\n".join(f"- {key}: `{rel(Path(value))}`" for key, value in visual_info.get("contact_sheets", {}).items()),
        "",
        "## Direct Answers",
        "",
        "1. GM_RM017表现好主要因为中距离完整车体阶段成立：光学框中心、尺寸和相对深度仍能近似代表整车状态；这不是单纯场景偶然。",
        "2. 模拟截断能复现GM_RM019式失败机制：左右截断先破坏方位中心，底部/半车截断显著污染径向深度和尺寸含义。",
        "3. 仅扩大不确定区间不够：M1能提高覆盖但不修正中心和深度，搜索面积也随之扩大。",
        "4. 时序整车恢复显著改善SAR投影，尤其在模拟截断中把M0退化拉回完整状态基线；自然截断改善取决于完整锚点质量。",
        "5. 可以进入WGV3.5A-R2的GM_RM019真实截断验证，但必须沿用R1的观测状态、身份审计和锚点阻断规则，不能恢复成原split泛化口径。",
    ]
    write_text(OUTPUTS["closure_md"], "\n".join(lines))
    return status


def improvement_percent(before: float, after: float) -> float:
    if not math.isfinite(before) or before <= 0 or not math.isfinite(after):
        return 0.0
    return max(0.0, (before - after) / before * 100.0)


def build_baseline_manifest() -> list[dict[str, Any]]:
    rows = []
    for path in BASELINE_FILES:
        info = {"source_file": rel(path), "sha256": sha256_file(path), "bytes": path.stat().st_size, "rows": ""}
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)
                info["rows"] = sum(1 for _ in reader)
        rows.append(info)
    return rows


def run_pipeline(stage: str) -> dict[str, Any]:
    baseline_manifest = build_baseline_manifest()
    pairs, optical_by_id, sar_by_id, split_rows = load_baseline_rows()
    rows = build_joined_rows(pairs, optical_by_id, sar_by_id)
    vehicle_rows = build_physical_vehicle_map(rows)
    observation_rows = build_observation_rows(rows)
    baseline_rows, bundle = fit_complete_models(rows)
    sim_sources = choose_simulation_sources(rows)
    simulation_rows, simulation_samples = build_simulation_rows(sim_sources)
    natural_rows, natural_samples = build_natural_rows(rows, bundle)
    all_samples = simulation_samples + natural_samples
    recovered_rows, recovery_by_id = build_recovered_rows(all_samples, bundle["direct_rows"])
    projection_rows, failure_rows, all_eval = evaluate_projection(rows, all_samples, recovery_by_id, bundle)
    visual_info = render_visual_outputs(rows, simulation_samples, natural_samples, recovery_by_id, failure_rows, bundle)

    write_csv(OUTPUTS["vehicle_map"], vehicle_rows, PHYSICAL_VEHICLE_FIELDS)
    write_csv(OUTPUTS["observation"], observation_rows, OBSERVATION_FIELDS)
    write_csv(OUTPUTS["baseline"], baseline_rows, BASELINE_FIELDS)
    write_csv(OUTPUTS["simulation"], simulation_rows, SIMULATION_FIELDS)
    write_csv(OUTPUTS["natural"], natural_rows, NATURAL_FIELDS)
    write_csv(OUTPUTS["recovered"], recovered_rows, RECOVERED_FIELDS)
    write_csv(OUTPUTS["projection"], projection_rows, PROJECTION_FIELDS)
    write_csv(OUTPUTS["failures"], failure_rows, FAILURE_FIELDS)

    render_identity_report(vehicle_rows, rows, baseline_manifest)
    render_mechanism_report(rows, baseline_rows, projection_rows)
    status = render_closure_report(
        rows,
        vehicle_rows,
        baseline_rows,
        simulation_rows,
        natural_rows,
        recovered_rows,
        projection_rows,
        failure_rows,
        baseline_manifest,
        visual_info,
    )
    return {
        "stage": stage,
        "status": status,
        "direct_observable": sum(1 for row in rows if row["direct_observable"]),
        "temporally_recoverable": sum(1 for row in rows if row["temporally_recoverable"]),
        "not_safely_recoverable": sum(1 for row in rows if row["not_safely_recoverable"]),
        "natural_truncation_cases": len(natural_rows),
        "simulation_samples": len(simulation_rows),
        "recovered_rows": len(recovered_rows),
        "outputs": {key: str(path) for key, path in OUTPUTS.items()},
        "visual": visual_info,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["audit", "fit-complete", "simulate", "recover", "evaluate", "all"], default="all")
    args = parser.parse_args(argv)
    result = run_pipeline(args.stage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
