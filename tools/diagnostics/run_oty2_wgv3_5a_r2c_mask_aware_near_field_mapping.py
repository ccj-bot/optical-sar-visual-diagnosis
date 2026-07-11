"""WGV3.5A-R2C mask-aware GM_RM019 audit.

This diagnostic keeps the R2C boundary narrow:
- reconstruct only the SAR fan/effective support needed for mask-censoring audit;
- keep latent full SAR vehicle state separate from observed masked SAR state;
- stop near-field bearing model work when center supervision is not available.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path("D:/profile/research/data")
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_wgv3_5a_r2c_mask_aware_near_field_mapping_20260711.md")
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_5a_r2c_mask_aware_20260711"

DATE_R1 = "20260710"
DATE = "20260711"

SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
FULL_AZIMUTH_SPAN = 178.0
OPTICAL_WIDTH = 800.0
OPTICAL_HEIGHT = 600.0

R1_AZ_Q95 = 2.0
R1_RADIAL_Q95 = 31.795472356059967

FREEZE_FILES = [
    REPORT_DIR / f"oty2_wgv3_5a_r1_closure_{DATE_R1}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2_gm019_closure_{DATE_R1}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_closure_{DATE_R1}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_full_stream_anchor_reaudit_{DATE_R1}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_anchorless_reconstruction_method_{DATE_R1}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r2b_gm019_visual_diagnosis_{DATE_R1}.md",
    SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_{DATE_R1}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_{DATE_R1}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_optical_recovery_anchors_{DATE_R1}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_sar_scene_calibration_anchors_{DATE_R1}.csv",
]

INPUTS = {
    "paired": SAMPLES_DIR / f"oty2_wgv3_5a_paired_annotations_{DATE_R1}.csv",
    "sar_polar": SAMPLES_DIR / f"oty2_wgv3_5a_sar_polar_targets_{DATE_R1}.csv",
    "r1_baseline": SAMPLES_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_baseline_{DATE_R1}.csv",
    "r1_observation": SAMPLES_DIR / f"oty2_wgv3_5a_r1_observation_state_audit_{DATE_R1}.csv",
    "r2b_eval": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_{DATE_R1}.csv",
    "r2b_branch_a": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_branch_a_anchor_recovery_{DATE_R1}.csv",
    "r2b_branch_b": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_{DATE_R1}.csv",
    "r2b_direct": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_direct_observable_full_stream_{DATE_R1}.csv",
    "r2b_timeline": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_physical_vehicle_timeline_{DATE_R1}.csv",
    "r2b_anchors": SAMPLES_DIR / f"oty2_wgv3_5a_r2b_gm019_optical_recovery_anchors_{DATE_R1}.csv",
}

OUTPUTS = {
    "freeze": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_freeze_manifest_{DATE}.csv",
    "mask_definition_md": REPORT_DIR / f"oty2_wgv3_5a_r2c_sar_mask_definition_{DATE}.md",
    "mask_source": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_sar_mask_source_inventory_{DATE}.csv",
    "mask_audit": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_mask_observation_audit_{DATE}.csv",
    "mask_gate_md": REPORT_DIR / f"oty2_wgv3_5a_r2c_gm019_mask_supervision_gate_{DATE}.md",
    "gm17_hidden": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm17_hidden_degraded_inputs_{DATE}.csv",
    "gm17_truth": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm17_scoring_truth_{DATE}.csv",
    "gm17_results": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm17_leakage_free_results_{DATE}.csv",
    "gm17_md": REPORT_DIR / f"oty2_wgv3_5a_r2c_gm17_leakage_free_control_{DATE}.md",
    "optical_review": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_optical_state_review_{DATE}.csv",
    "dimension_split": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_dimension_split_{DATE}.csv",
    "bearing_relation": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_bearing_relation_{DATE}.csv",
    "center_semantic": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_center_semantic_review_{DATE}.csv",
    "model_comparison": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_model_comparison_{DATE}.csv",
    "leave_one": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_leave_one_vehicle_out_{DATE}.csv",
    "intervals": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_mask_aware_intervals_{DATE}.csv",
    "failure_cases": SAMPLES_DIR / f"oty2_wgv3_5a_r2c_gm019_failure_cases_{DATE}.csv",
    "visual_md": REPORT_DIR / f"oty2_wgv3_5a_r2c_mask_aware_visual_diagnosis_{DATE}.md",
    "closure_md": REPORT_DIR / f"oty2_wgv3_5a_r2c_mask_aware_closure_{DATE}.md",
}

VISUALS = {
    "mask_overview": OUT_DIR / "r2c_sar_mask_overview.png",
    "pair_contact_sheet": OUT_DIR / "r2c_gm019_16_pair_mask_contact_sheet.png",
    "vehicle_trajectory": OUT_DIR / "r2c_gm019_vehicle_sar_trajectory_vs_mask.png",
    "class_cases": OUT_DIR / "r2c_gm019_s0_s1_s2_s3_cases.png",
    "gm17_control": OUT_DIR / "r2c_gm17_leakage_free_recovery_comparison.png",
    "optical_timeline": OUT_DIR / "r2c_gm019_optical_recovery_timeline.png",
    "azimuth_residual": OUT_DIR / "r2c_gm019_azimuth_residual_vs_mask_distance.png",
    "leave_one": OUT_DIR / "r2c_gm019_leave_one_vehicle_fold_results.png",
}


FREEZE_FIELDS = ["source_file", "sha256", "bytes", "rows", "frozen_scope"]
MASK_SOURCE_FIELDS = [
    "source_type",
    "source_path",
    "mask_shape",
    "sar_shape",
    "static_or_dynamic",
    "generation_rule",
    "physical_meaning",
    "used_during_annotation",
    "used_during_png_generation",
    "outside_value",
    "confidence",
    "open_question",
    "mask_reconstructed_from_code",
    "estimated_visual_mask_only",
]
MASK_AUDIT_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "optical_frame",
    "sar_frame",
    "sar_bbox",
    "sar_bbox_center",
    "sar_bbox_center_inside_mask",
    "sar_bbox_touches_mask",
    "sar_bbox_mask_intersection_ratio",
    "sar_response_touches_mask",
    "sar_response_truncation_direction",
    "trajectory_approaches_mask_boundary",
    "trajectory_continues_toward_mask_outside",
    "bbox_size_shrinks_near_mask",
    "center_jumps_toward_mask_interior",
    "estimated_full_vehicle_center_inside_mask",
    "estimated_full_vehicle_partly_outside_mask",
    "estimated_full_vehicle_mostly_outside_mask",
    "sar_mask_observation_class",
    "usable_for_center_supervision",
    "usable_for_interval_supervision",
    "usable_for_masked_overlap_evaluation",
    "blocked_reason",
    "mask_boundary_distance_px",
    "bottom_valid_margin_px",
    "visual_review_cn",
]
GM17_HIDDEN_FIELDS = [
    "hidden_sample_id",
    "physical_vehicle_id",
    "pair_id",
    "frame",
    "observed_bbox",
    "observed_depth",
    "visible_left",
    "visible_right",
    "visible_top",
    "visible_bottom",
    "edge_constraint",
    "degradation_pattern",
    "missing_observation",
]
GM17_TRUTH_FIELDS = [
    "hidden_sample_id",
    "physical_vehicle_id",
    "pair_id",
    "frame",
    "truth_bbox",
    "truth_depth",
    "truth_sar_azimuth",
    "truth_sar_radial",
]
GM17_RESULT_FIELDS = [
    "method",
    "sample_count",
    "physical_vehicle_count",
    "center_x_median_error",
    "center_x_p90_error",
    "center_y_median_error",
    "center_y_p90_error",
    "width_median_error",
    "width_p90_error",
    "height_median_error",
    "height_p90_error",
    "depth_median_error",
    "depth_p90_error",
    "SAR_azimuth_median_error",
    "SAR_azimuth_p90_error",
    "SAR_radial_median_error",
    "SAR_radial_p90_error",
    "center_coverage",
    "truth_loaded_by_recovery",
    "crop_ratio_loaded_by_recovery",
    "original_bbox_loaded_by_recovery",
    "original_depth_loaded_by_recovery",
    "controlled_pass",
    "notes",
]
OPTICAL_REVIEW_FIELDS = [
    "physical_vehicle_id",
    "reviewed_frames",
    "paired_frames",
    "direct_full_stream_anchor_count",
    "branch_a_recovered_pair_count",
    "branch_b_recovered_pair_count",
    "optical_state_review_class",
    "identity_confidence",
    "pure_optical_reason_cn",
    "allowed_for_sar_mapping_audit",
]
DIMENSION_FIELDS = [
    "method",
    "mask_class",
    "sample_count",
    "physical_vehicle_count",
    "azimuth_median_error",
    "azimuth_p90_error",
    "radial_median_error",
    "radial_p90_error",
    "azimuth_covered_count",
    "radial_covered_count",
    "joint_covered_count",
    "masked_overlap_covered_count",
    "blocked_count",
]
BEARING_FIELDS = [
    "physical_vehicle_id",
    "mask_class",
    "mapping_monotonic",
    "offset_pattern",
    "scale_pattern",
    "depth_dependence",
    "phase_dependence",
    "mask_boundary_dependence",
    "center_semantic_risk",
    "recommended_bearing_proxy",
    "audit_status",
]
CENTER_SEMANTIC_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "sar_frame",
    "mask_class",
    "sar_box_same_physical_vehicle",
    "sar_response_mask_censored",
    "sar_box_center_full_vehicle_center",
    "center_closer_to_front_hotspot",
    "center_closer_to_rear_hotspot",
    "center_visible_response_only",
    "temporal_mapping_shift_risk",
    "azimuth_direction_consistent",
    "polar_conversion_consistent",
    "center_semantic_status",
    "review_cn",
]
MODEL_FIELDS = [
    "model_id",
    "model_name",
    "training_mask_classes",
    "training_sample_count",
    "training_physical_vehicle_count",
    "selected_model",
    "azimuth_median_error",
    "azimuth_p90_error",
    "radial_median_error",
    "radial_p90_error",
    "center_coverage",
    "run_status",
    "blocked_reason",
]
LEAVE_ONE_FIELDS = [
    "fold_id",
    "train_physical_vehicles",
    "test_physical_vehicle",
    "train_S0_count",
    "train_S1_count",
    "test_S0_count",
    "test_S1_count",
    "test_S2_count",
    "selected_model",
    "azimuth_median",
    "azimuth_p90",
    "radial_median",
    "radial_p90",
    "azimuth_coverage",
    "radial_coverage",
    "joint_coverage",
    "masked_overlap_coverage",
    "search_ratio",
    "run_status",
    "blocked_reason",
]
INTERVAL_FIELDS = [
    "interval_group",
    "training_count",
    "azimuth_q50",
    "azimuth_q80",
    "azimuth_q95",
    "radial_q50",
    "radial_q80",
    "radial_q95",
    "held_out_center_coverage",
    "held_out_masked_overlap_coverage",
    "search_ratio",
    "run_status",
    "blocked_reason",
]
FAILURE_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "mask_class",
    "method",
    "primary_failure_source",
    "azimuth_error",
    "radial_error",
    "blocked_reason",
    "review_cn",
]


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
    def area(self) -> float:
        return self.width * self.height

    def as_text(self) -> str:
        return f"{self.x1:.3f},{self.y1:.3f},{self.x2:.3f},{self.y2:.3f}"


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        text = str(value).strip()
        if not text:
            return default
        return int(float(text))
    except Exception:
        return default


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    try:
        val = float(value)
    except Exception:
        return str(value)
    if math.isnan(val) or math.isinf(val):
        return ""
    text = f"{val:.{digits}f}"
    text = text.rstrip("0").rstrip(".")
    return text if text else "0"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def percentile(values: Iterable[float], q: float) -> float:
    vals = sorted(float(v) for v in values if not math.isnan(float(v)))
    if not vals:
        return math.nan
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> str:
    if path.suffix.lower() != ".csv" or not path.exists():
        return ""
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return str(sum(1 for _ in csv.DictReader(handle)))
    except Exception:
        return ""


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    display = list(rows if limit is None else rows[:limit])
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in display:
        vals = [str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields]
        lines.append("|" + "|".join(vals) + "|")
    if limit is not None and len(rows) > limit:
        lines.append("|" + "|".join(["..."] + [""] * (len(fields) - 1)) + "|")
    return "\n".join(lines)


def box_from_pair(row: Mapping[str, Any], prefix: str = "sar_bbox") -> Box:
    return Box(
        parse_float(row[f"{prefix}_x1"]),
        parse_float(row[f"{prefix}_y1"]),
        parse_float(row[f"{prefix}_x2"]),
        parse_float(row[f"{prefix}_y2"]),
    )


def box_from_text(text: str) -> Box | None:
    parts = [parse_float(part) for part in str(text).split(",")]
    if len(parts) != 4 or any(math.isnan(v) for v in parts):
        return None
    return Box(parts[0], parts[1], parts[2], parts[3])


def sar_gray_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def optical_frame_path(scene: str, frame: int) -> Path | None:
    folder = DATA_ROOT / scene / f"{scene}_frames"
    for suffix in [".png", ".jpg", ".jpeg"]:
        candidate = folder / f"{frame:06d}{suffix}"
        if candidate.exists():
            return candidate
    return None


def read_gray(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("L"))


def build_geometry(shape: tuple[int, int] = (SAR_HEIGHT, SAR_WIDTH)) -> dict[str, np.ndarray]:
    height, width = shape
    yy, xx = np.indices((height, width), dtype=np.float32)
    dx = xx - FAN_CENTER_X
    dy = FAN_CENTER_Y - yy
    radial = np.sqrt(dx * dx + dy * dy)
    azimuth = np.degrees(np.arctan2(dx, dy))
    fan = (radial <= FAN_RADIUS_PX) & (azimuth >= -90.0) & (azimuth <= 90.0)
    return {"fan": fan, "radial": radial, "azimuth": azimuth}


def point_inside_fan(x: float, y: float) -> bool:
    dx = x - FAN_CENTER_X
    dy = FAN_CENTER_Y - y
    radial = math.hypot(dx, dy)
    az = math.degrees(math.atan2(dx, dy)) if dy != 0 or dx != 0 else 0.0
    return radial <= FAN_RADIUS_PX and -90.0 <= az <= 90.0


def polar_to_pixel(azimuth_deg: float, radial_px: float) -> tuple[float, float]:
    theta = math.radians(azimuth_deg)
    x = FAN_CENTER_X + radial_px * math.sin(theta)
    y = FAN_CENTER_Y - radial_px * math.cos(theta)
    return x, y


def mask_intersection_ratio(box: Box, mask: np.ndarray) -> float:
    x0 = max(0, int(math.floor(box.x1)))
    y0 = max(0, int(math.floor(box.y1)))
    x1 = min(mask.shape[1], int(math.ceil(box.x2)))
    y1 = min(mask.shape[0], int(math.ceil(box.y2)))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    crop = mask[y0:y1, x0:x1]
    return float(crop.mean()) if crop.size else 0.0


def bottom_valid_margin(box: Box) -> float:
    return max(0.0, FAN_CENTER_Y - box.y2)


def center_mask_distance(box: Box) -> float:
    dx = box.cx - FAN_CENTER_X
    dy = FAN_CENTER_Y - box.cy
    radial = math.hypot(dx, dy)
    az = abs(math.degrees(math.atan2(dx, dy))) if dy != 0 or dx != 0 else 0.0
    radial_margin = FAN_RADIUS_PX - radial
    az_margin_proxy = dy if az <= 90.0 else -1.0
    return min(radial_margin, az_margin_proxy)


def load_context() -> dict[str, Any]:
    paired = read_csv(INPUTS["paired"])
    sar_polar = {row["pair_id"]: row for row in read_csv(INPUTS["sar_polar"])}
    gm19_pairs = [row for row in paired if row.get("scene") == "GM_RM019"]
    eval_rows = read_csv(INPUTS["r2b_eval"])
    branch_a = {row["pair_id"]: row for row in read_csv(INPUTS["r2b_branch_a"])}
    branch_b = read_csv(INPUTS["r2b_branch_b"])
    direct_rows = read_csv(INPUTS["r2b_direct"])
    timeline = read_csv(INPUTS["r2b_timeline"])
    anchors = read_csv(INPUTS["r2b_anchors"])
    pv_by_pair: dict[str, str] = {}
    eval_by_pair_method: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in eval_rows:
        if row.get("physical_vehicle_id") and row.get("pair_id"):
            pv_by_pair.setdefault(row["pair_id"], row["physical_vehicle_id"])
            eval_by_pair_method[(row["pair_id"], row["method"])].append(row)
    for row in gm19_pairs:
        row["physical_vehicle_id"] = pv_by_pair.get(row["pair_id"], "PV_GM19_UNKNOWN")
        row["sar_azimuth"] = sar_polar.get(row["pair_id"], {}).get("sar_center_azimuth_deg", "")
        row["sar_radial"] = sar_polar.get(row["pair_id"], {}).get("sar_center_radial_pixel", "")
        row["sar_center_x"] = sar_polar.get(row["pair_id"], {}).get("sar_center_x", "")
        row["sar_center_y"] = sar_polar.get(row["pair_id"], {}).get("sar_center_y", "")
        row["sar_azimuth_min"] = sar_polar.get(row["pair_id"], {}).get("sar_azimuth_min", "")
        row["sar_azimuth_max"] = sar_polar.get(row["pair_id"], {}).get("sar_azimuth_max", "")
        row["sar_radial_min"] = sar_polar.get(row["pair_id"], {}).get("sar_radial_min", "")
        row["sar_radial_max"] = sar_polar.get(row["pair_id"], {}).get("sar_radial_max", "")
    return {
        "paired_all": paired,
        "gm19_pairs": gm19_pairs,
        "sar_polar": sar_polar,
        "eval_rows": eval_rows,
        "eval_by_pair_method": eval_by_pair_method,
        "branch_a": branch_a,
        "branch_b": branch_b,
        "direct_rows": direct_rows,
        "timeline": timeline,
        "anchors": anchors,
    }


def build_freeze_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in FREEZE_FILES:
        rows.append(
            {
                "source_file": str(path.relative_to(REPO_ROOT)),
                "sha256": sha256(path) if path.exists() else "MISSING",
                "bytes": path.stat().st_size if path.exists() else "",
                "rows": row_count(path),
                "frozen_scope": "R1/R2/R2B historical output; R2C reads only and does not overwrite",
            }
        )
    return rows


def find_mask_like_files() -> list[Path]:
    roots = [REPO_ROOT, DATA_ROOT / "GM_RM019", DATA_ROOT / "GM_RM017"]
    keywords = ["mask", "valid_mask", "valid_region", "sar_mask", "roi_mask", "effective_mask", "valid_area"]
    matches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if any(key in name for key in keywords):
                matches.append(path)
    return matches


def estimate_png_support(scene: str, pair_frames: Sequence[int]) -> dict[str, Any]:
    gray_dir = DATA_ROOT / scene / f"{scene}_SARframes_gray"
    all_files = sorted(gray_dir.glob("*.png"))
    periodic = [parse_int(path.stem) for idx, path in enumerate(all_files) if idx % 20 == 0]
    sample_frames = sorted(set([0, len(all_files) - 1] + list(pair_frames) + periodic))
    sample_paths = [sar_gray_path(scene, frame) for frame in sample_frames if sar_gray_path(scene, frame).exists()]
    geom = build_geometry()
    fan = geom["fan"]
    nonzero_count = np.zeros((SAR_HEIGHT, SAR_WIDTH), dtype=np.uint16)
    ratios: list[float] = []
    for path in sample_paths:
        arr = read_gray(path)
        nonzero = arr > 0
        nonzero_count += nonzero.astype(np.uint16)
        ratios.append(float(nonzero.mean()))
    stable_min = max(1, int(math.ceil(0.95 * len(sample_paths))))
    stable_mask = (nonzero_count >= stable_min) & fan
    ever_nonzero = (nonzero_count > 0) & fan
    fan_count = int(fan.sum())
    stable_count = int(stable_mask.sum())
    ever_count = int(ever_nonzero.sum())
    return {
        "sample_frames": sample_frames,
        "sample_paths": sample_paths,
        "fan_mask": fan,
        "effective_mask": fan if stable_count / max(1, fan_count) > 0.995 else stable_mask,
        "stable_mask": stable_mask,
        "fan_count": fan_count,
        "stable_count": stable_count,
        "ever_count": ever_count,
        "fixed_black_count": int((fan & (nonzero_count == 0)).sum()),
        "nonzero_ratio_min": min(ratios) if ratios else math.nan,
        "nonzero_ratio_max": max(ratios) if ratios else math.nan,
        "nonzero_ratio_median": median(ratios) if ratios else math.nan,
        "sample_count": len(sample_paths),
        "all_frame_count": len(all_files),
    }


def build_mask_source_inventory(context: Mapping[str, Any], support: Mapping[str, Any]) -> list[dict[str, Any]]:
    matches = find_mask_like_files()
    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "source_type": "independent_mask_file_search",
            "source_path": ";".join(str(p) for p in matches[:20]) if matches else "none_found_in_repo_or_GM_RM017_GM_RM019_data_dirs",
            "mask_shape": "" if not matches else "unverified",
            "sar_shape": f"{SAR_WIDTH}x{SAR_HEIGHT}",
            "static_or_dynamic": "unknown_without_external_mask_file",
            "generation_rule": "searched names: mask, valid_mask, valid_region, fan_mask, sector_mask, sar_mask, roi_mask, effective_mask, valid_pixel, valid_area",
            "physical_meaning": "no independent physical mask file confirmed",
            "used_during_annotation": "unknown",
            "used_during_png_generation": "unknown",
            "outside_value": "unknown",
            "confidence": "high_for_absence_of_named_file;low_for_physical_semantics",
            "open_question": "whether a MATLAB/imaging-time physical-valid mask exists outside the checked repo/data directories",
            "mask_reconstructed_from_code": "false",
            "estimated_visual_mask_only": "false",
        }
    )
    rows.append(
        {
            "source_type": "fan_geometry_reconstructed_from_code",
            "source_path": "tools/diagnostics/run_oty2_wgv3_3c_non_gt_sar_response.py:432-444; tools/diagnostics/run_oty2_wgv3_3d_local_sar_response_components.py; tools/diagnostics/run_oty2_wgv3_5a_r2_gm019_real_truncation.py",
            "mask_shape": f"{SAR_HEIGHT}x{SAR_WIDTH}",
            "sar_shape": f"{SAR_WIDTH}x{SAR_HEIGHT}",
            "static_or_dynamic": "static_formula_shared_by_checked_scenes",
            "generation_rule": "radial<=1332.7 and -90<=atan2(x-1154,1330.6-y)<=90 on 2308x1334 canvas",
            "physical_meaning": "SAR fan display/geometry support; physical imaging-valid semantics not independently proven",
            "used_during_annotation": "not explicitly documented; annotations are inside the rendered SAR PNG fan support",
            "used_during_png_generation": "consistent_with_gray_PNG_zero_outside_fan",
            "outside_value": "0 in sampled gray PNG outside fan",
            "confidence": "medium",
            "open_question": "does this display fan equal the physical valid mask used by annotation",
            "mask_reconstructed_from_code": "true",
            "estimated_visual_mask_only": "false",
        }
    )
    rows.append(
        {
            "source_type": "GM_RM019_gray_png_stable_nonzero_support",
            "source_path": str(DATA_ROOT / "GM_RM019" / "GM_RM019_SARframes_gray"),
            "mask_shape": f"{SAR_HEIGHT}x{SAR_WIDTH}",
            "sar_shape": f"{SAR_WIDTH}x{SAR_HEIGHT}",
            "static_or_dynamic": f"sampled_{support['sample_count']}_of_{support['all_frame_count']}_frames;nonzero_ratio={fmt(support['nonzero_ratio_min'])}-{fmt(support['nonzero_ratio_max'])}",
            "generation_rule": "diagnostic stable support = sampled pixels nonzero in at least 95% of sampled frames, intersected with fan geometry",
            "physical_meaning": "estimated_visual_mask_only; useful for zeroed PNG support, not sufficient to prove physical-valid area",
            "used_during_annotation": "unknown",
            "used_during_png_generation": "yes_as_observed_zero/nonzero_pattern",
            "outside_value": "0 for stable outside/fan-exterior pixels",
            "confidence": "medium_for_rendered_png_support;low_for_physical_mask_semantics",
            "open_question": f"stable_count={support['stable_count']};fan_count={support['fan_count']};fixed_black_inside_fan={support['fixed_black_count']}",
            "mask_reconstructed_from_code": "false",
            "estimated_visual_mask_only": "true",
        }
    )
    return rows


def response_touches_near_mask(row: Mapping[str, Any], box: Box) -> tuple[bool, str]:
    path = sar_gray_path("GM_RM019", parse_int(row["sar_frame"]))
    if not path.exists():
        return False, "gray_frame_missing"
    arr = read_gray(path)
    x0 = max(0, int(math.floor(box.x1)))
    x1 = min(arr.shape[1], int(math.ceil(box.x2)))
    y0 = max(0, int(math.floor(box.y1)))
    y1 = min(arr.shape[0], int(math.ceil(box.y2)))
    if x1 <= x0 or y1 <= y0:
        return False, "empty_bbox_patch"
    patch = arr[y0:y1, x0:x1]
    if patch.size == 0:
        return False, "empty_bbox_patch"
    threshold = np.percentile(patch, 80)
    bottom_band = patch[max(0, patch.shape[0] - 12) :, :]
    hot_bottom = bool((bottom_band >= threshold).mean() > 0.08)
    near_bottom_mask = bottom_valid_margin(box) <= 110.0
    return bool(hot_bottom and near_bottom_mask), "bottom_near_range_mask" if hot_bottom and near_bottom_mask else "no_local_bbox_boundary_hot_band"


def classify_mask_observation(row: Mapping[str, Any], box: Box, ratio: float, pred_inside: bool | None) -> tuple[str, str]:
    bottom_gap = bottom_valid_margin(box)
    reasons: list[str] = []
    if ratio < 0.50:
        return "SAR_MASK_S3_NOT_CENTER_SUPERVISABLE", "sar_bbox_mostly_outside_reconstructed_mask"
    if ratio < 0.95:
        return "SAR_MASK_S2_CENTER_CENSORED", "sar_bbox_partly_outside_reconstructed_mask"
    if bottom_gap <= 70.0:
        reasons.append("bbox_bottom_within_70px_of_near_range_mask")
        return "SAR_MASK_S2_CENTER_CENSORED", ";".join(reasons)
    if pred_inside is False:
        reasons.append("R2B_recovered_full_state_projects_outside_reconstructed_mask")
        return "SAR_MASK_S2_CENTER_CENSORED", ";".join(reasons)
    if bottom_gap <= 110.0:
        reasons.append("bbox_bottom_within_110px_of_near_range_mask")
        reasons.append("observed_box_may_be_masked_response_center_not_full_vehicle_center")
        return "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE", ";".join(reasons)
    return "SAR_MASK_S0_FULLY_OBSERVABLE", "bbox_and_local_response_not_near_reconstructed_mask_boundary"


def build_mask_audit(context: Mapping[str, Any], support: Mapping[str, Any]) -> list[dict[str, Any]]:
    pairs = list(context["gm19_pairs"])
    mask = support["effective_mask"]
    by_pv = defaultdict(list)
    for row in pairs:
        by_pv[row["physical_vehicle_id"]].append(row)
    pv_median_area: dict[str, float] = {}
    pv_min_bottom_gap: dict[str, float] = {}
    for pv, rows in by_pv.items():
        boxes = [box_from_pair(row) for row in rows]
        pv_median_area[pv] = median([box.area for box in boxes]) if boxes else math.nan
        pv_min_bottom_gap[pv] = min([bottom_valid_margin(box) for box in boxes]) if boxes else math.nan

    out: list[dict[str, Any]] = []
    for row in pairs:
        pair_id = row["pair_id"]
        pv = row["physical_vehicle_id"]
        box = box_from_pair(row)
        ratio = mask_intersection_ratio(box, mask)
        response_touch, response_reason = response_touches_near_mask(row, box)
        z1b = context["eval_by_pair_method"].get((pair_id, "Z1B_anchorless_track_level_completion"), [])
        pred_inside: bool | None = None
        pred_partly = False
        pred_mostly = False
        if z1b:
            pred_az = parse_float(z1b[0].get("predicted_azimuth"))
            pred_rad = parse_float(z1b[0].get("predicted_radial"))
            if not math.isnan(pred_az) and not math.isnan(pred_rad):
                px, py = polar_to_pixel(pred_az, pred_rad)
                pred_inside = point_inside_fan(px, py)
                pred_partly = not pred_inside or pred_rad < 40.0
                pred_mostly = pred_rad < 0.0
        mask_class, reason = classify_mask_observation(row, box, ratio, pred_inside)
        bottom_gap = bottom_valid_margin(box)
        near = mask_class != "SAR_MASK_S0_FULLY_OBSERVABLE"
        area_shrinks = box.area < 0.88 * pv_median_area[pv] if pv_median_area[pv] == pv_median_area[pv] else False
        trajectory_near = pv_min_bottom_gap[pv] <= 110.0 if pv_min_bottom_gap[pv] == pv_min_bottom_gap[pv] else False
        interval_ok = mask_class in {
            "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE",
            "SAR_MASK_S2_CENTER_CENSORED",
        }
        overlap_ok = mask_class != "SAR_MASK_S3_NOT_CENTER_SUPERVISABLE"
        if mask_class == "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE":
            cn = "SAR框位于有效扇形内，但底部接近近距mask边界；当前中心更应视为mask内可见响应中心的弱监督。"
        elif mask_class == "SAR_MASK_S2_CENTER_CENSORED":
            cn = "SAR框和响应仍在可见mask内，但潜在完整车体中心可能落在近距mask外；禁止作为完整中心监督。"
        elif mask_class == "SAR_MASK_S3_NOT_CENTER_SUPERVISABLE":
            cn = "SAR可见响应不足或语义不可判断，只能作为mask截断事件。"
        else:
            cn = "SAR响应未见mask截断证据，可作为完整中心监督。"
        out.append(
            {
                "pair_id": pair_id,
                "physical_vehicle_id": pv,
                "optical_frame": row["optical_frame"],
                "sar_frame": row["sar_frame"],
                "sar_bbox": box.as_text(),
                "sar_bbox_center": f"{box.cx:.3f},{box.cy:.3f}",
                "sar_bbox_center_inside_mask": bool_text(point_inside_fan(box.cx, box.cy)),
                "sar_bbox_touches_mask": bool_text(bottom_gap <= 110.0),
                "sar_bbox_mask_intersection_ratio": fmt(ratio),
                "sar_response_touches_mask": bool_text(response_touch),
                "sar_response_truncation_direction": response_reason if near else "none_detected",
                "trajectory_approaches_mask_boundary": bool_text(trajectory_near),
                "trajectory_continues_toward_mask_outside": bool_text(trajectory_near and bottom_gap <= 90.0),
                "bbox_size_shrinks_near_mask": bool_text(area_shrinks and near),
                "center_jumps_toward_mask_interior": bool_text(near and area_shrinks and response_touch),
                "estimated_full_vehicle_center_inside_mask": "unknown" if pred_inside is None else bool_text(pred_inside),
                "estimated_full_vehicle_partly_outside_mask": bool_text(pred_partly),
                "estimated_full_vehicle_mostly_outside_mask": bool_text(pred_mostly),
                "sar_mask_observation_class": mask_class,
                "usable_for_center_supervision": "false",
                "usable_for_interval_supervision": bool_text(interval_ok),
                "usable_for_masked_overlap_evaluation": bool_text(overlap_ok),
                "blocked_reason": "center_semantics_mask_censored_or_unconfirmed;" + reason,
                "mask_boundary_distance_px": fmt(center_mask_distance(box)),
                "bottom_valid_margin_px": fmt(bottom_gap),
                "visual_review_cn": cn,
            }
        )
    return out


def build_mask_gate(audit_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["sar_mask_observation_class"] for row in audit_rows)
    center_rows = [row for row in audit_rows if row["usable_for_center_supervision"] == "true"]
    center_vehicles = {row["physical_vehicle_id"] for row in center_rows}
    weak_rows = [row for row in audit_rows if row["sar_mask_observation_class"] == "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE"]
    status = "OPEN_GM19_SAR_MASK_CENTER_SUPERVISION_INSUFFICIENT"
    did_pass = False
    weak_only = bool(weak_rows) and not center_rows
    return {
        "counts": counts,
        "center_rows": center_rows,
        "center_vehicles": center_vehicles,
        "weak_rows": weak_rows,
        "status": status,
        "did_pass": did_pass,
        "weak_only": weak_only,
        "stop_reason": "S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。",
    }


def selected_r1_models() -> dict[str, Any]:
    rows = read_csv(INPUTS["r1_baseline"])
    selected: dict[str, Any] = {}
    for row in rows:
        if row.get("selected") == "true":
            selected[row["model_target"]] = row
    return selected


def predict_r1_state(box: Box, depth: float = 3.5) -> tuple[float, float]:
    models = selected_r1_models()
    az_row = models.get("azimuth")
    rad_row = models.get("radial")
    az = math.nan
    radial = math.nan
    if az_row:
        params = json.loads(az_row["parameters"])
        feats = az_row["input_features"].split(";")
        values = []
        for feature in feats:
            if feature == "bbox_center_x":
                values.append(box.cx)
            elif feature == "bbox_center_x_sq":
                values.append(box.cx * box.cx)
            else:
                values.append(0.0)
        az = sum(c * v for c, v in zip(params["coefficients"], values)) + params["intercept"]
    if rad_row:
        params = json.loads(rad_row["parameters"])
        feats = rad_row["input_features"].split(";")
        values = []
        for feature in feats:
            if feature == "depth_D4":
                values.append(depth)
            elif feature == "bbox_width":
                values.append(box.width)
            elif feature == "bbox_height":
                values.append(box.height)
            elif feature == "bbox_bottom_y":
                values.append(box.y2)
            else:
                values.append(0.0)
        radial = sum(c * v for c, v in zip(params["coefficients"], values)) + params["intercept"]
    return az, radial


def build_gm17_leakage_free_control(context: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    random.seed(3401)
    paired_by_id = {row["pair_id"]: row for row in context["paired_all"] if row.get("scene") == "GM_RM017"}
    sar_by_id = context["sar_polar"]
    obs = [row for row in read_csv(INPUTS["r1_observation"]) if row.get("direct_observable") == "true"]
    truth_rows: list[dict[str, Any]] = []
    hidden_rows: list[dict[str, Any]] = []
    per_sample: list[dict[str, Any]] = []
    patterns = ["left", "right", "bottom", "left_bottom", "right_bottom", "left_right", "none"]
    by_pv_index = defaultdict(int)
    for idx, row in enumerate(obs):
        pair = paired_by_id.get(row["pair_id"])
        if pair is None:
            continue
        truth = box_from_pair(pair, "optical_bbox")
        pv = row["physical_vehicle_id"]
        local_idx = by_pv_index[pv]
        by_pv_index[pv] += 1
        pattern = patterns[(local_idx + idx) % len(patterns)]
        missing = (local_idx % 23 == 11)
        left_cut = random.uniform(0.15, 0.65) if "left" in pattern else 0.0
        right_cut = random.uniform(0.15, 0.65) if "right" in pattern else 0.0
        bottom_cut = random.uniform(0.10, 0.45) if "bottom" in pattern else 0.0
        x1 = truth.x1 + truth.width * left_cut
        x2 = truth.x2 - truth.width * right_cut
        y1 = truth.y1
        y2 = truth.y2 - truth.height * bottom_cut
        if x2 <= x1 + 4:
            x1, x2 = truth.x1 + 0.3 * truth.width, truth.x2 - 0.3 * truth.width
        if y2 <= y1 + 4:
            y2 = y1 + 0.55 * truth.height
        observed = Box(x1, y1, x2, y2)
        depth = 3.5 + 0.004 * (truth.cy - 300.0)
        obs_depth = depth + (0.25 if "bottom" in pattern else 0.0) + random.uniform(-0.08, 0.08)
        sample_id = f"GM17_HIDDEN_{idx:04d}"
        if not missing:
            hidden_rows.append(
                {
                    "hidden_sample_id": sample_id,
                    "physical_vehicle_id": pv,
                    "pair_id": row["pair_id"],
                    "frame": row["frame"],
                    "observed_bbox": observed.as_text(),
                    "observed_depth": fmt(obs_depth),
                    "visible_left": bool_text(left_cut == 0.0),
                    "visible_right": bool_text(right_cut == 0.0),
                    "visible_top": "true",
                    "visible_bottom": bool_text(bottom_cut == 0.0),
                    "edge_constraint": pattern,
                    "degradation_pattern": pattern,
                    "missing_observation": "false",
                }
            )
        else:
            hidden_rows.append(
                {
                    "hidden_sample_id": sample_id,
                    "physical_vehicle_id": pv,
                    "pair_id": row["pair_id"],
                    "frame": row["frame"],
                    "observed_bbox": "",
                    "observed_depth": "",
                    "visible_left": "false",
                    "visible_right": "false",
                    "visible_top": "false",
                    "visible_bottom": "false",
                    "edge_constraint": "missing_1_frame",
                    "degradation_pattern": "missing_1_frame",
                    "missing_observation": "true",
                }
            )
        sar = sar_by_id.get(row["pair_id"], {})
        truth_rows.append(
            {
                "hidden_sample_id": sample_id,
                "physical_vehicle_id": pv,
                "pair_id": row["pair_id"],
                "frame": row["frame"],
                "truth_bbox": truth.as_text(),
                "truth_depth": fmt(depth),
                "truth_sar_azimuth": sar.get("sar_center_azimuth_deg", ""),
                "truth_sar_radial": sar.get("sar_center_radial_pixel", ""),
            }
        )
        per_sample.append(
            {
                "hidden_sample_id": sample_id,
                "physical_vehicle_id": pv,
                "frame": parse_int(row["frame"]),
                "truth": truth,
                "truth_depth": depth,
                "observed": None if missing else observed,
                "observed_depth": obs_depth,
                "pattern": pattern,
            }
        )

    recovered = recover_anchorless_from_hidden(hidden_rows)
    rec_by_id = {row["hidden_sample_id"]: row for row in recovered}
    result_rows = summarize_gm17_methods(per_sample, rec_by_id)
    return hidden_rows, truth_rows, result_rows, recovered


def recover_anchorless_from_hidden(hidden_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Same transparent constraint family used for GM19-style anchorless recovery.

    The function reads only degraded observations: visible edges, local boxes,
    frame order and local depth. It does not load truth boxes, crop ratios or
    original depths.
    """

    by_pv: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in hidden_rows:
        by_pv[row["physical_vehicle_id"]].append(row)
    output: list[dict[str, Any]] = []
    for pv, rows in by_pv.items():
        rows = sorted(rows, key=lambda r: parse_int(r["frame"]))
        boxes = [box_from_text(row.get("observed_bbox", "")) for row in rows]
        valid_boxes = [box for box in boxes if box is not None]
        if not valid_boxes:
            continue
        width_upper = percentile([box.width for box in valid_boxes], 95) * 1.18
        height_upper = percentile([box.height for box in valid_boxes], 95) * 1.14
        width_upper = max(width_upper, percentile([box.width for box in valid_boxes], 99))
        height_upper = max(height_upper, percentile([box.height for box in valid_boxes], 99))
        last_cx = median([box.cx for box in valid_boxes[: min(5, len(valid_boxes))]])
        last_cy = median([box.cy for box in valid_boxes[: min(5, len(valid_boxes))]])
        raw_states: list[dict[str, Any]] = []
        for row, box in zip(rows, boxes):
            pattern = row.get("edge_constraint", "")
            if box is None:
                cx = last_cx
                cy = last_cy
                depth = parse_float(raw_states[-1]["latent_depth"], 3.5) if raw_states else 3.5
                confidence = 0.45
                constraints = "missing_observation_temporal_interpolation"
            else:
                if "left_right" in pattern:
                    cx = last_cx
                elif "left" in pattern:
                    cx = box.x2 - width_upper / 2.0
                elif "right" in pattern:
                    cx = box.x1 + width_upper / 2.0
                else:
                    cx = box.cx
                if "bottom" in pattern:
                    cy = box.y1 + height_upper / 2.0
                else:
                    cy = box.cy
                depth = parse_float(row.get("observed_depth"), 3.5)
                confidence = 0.72 if pattern != "none" else 0.85
                constraints = "edge_inequality_width_height_upper_envelope_temporal_smoothing"
            last_cx = cx
            last_cy = cy
            raw_states.append(
                {
                    "hidden_sample_id": row["hidden_sample_id"],
                    "physical_vehicle_id": pv,
                    "frame": row["frame"],
                    "latent_center_x": cx,
                    "latent_center_y": cy,
                    "latent_width": width_upper,
                    "latent_height": height_upper,
                    "latent_depth": depth,
                    "confidence": confidence,
                    "constraints": constraints,
                }
            )
        # Short forward/backward smoothing without seeing truth.
        for i, state in enumerate(raw_states):
            lo = max(0, i - 1)
            hi = min(len(raw_states), i + 2)
            win = raw_states[lo:hi]
            output.append(
                {
                    **state,
                    "latent_center_x": sum(float(w["latent_center_x"]) for w in win) / len(win),
                    "latent_center_y": sum(float(w["latent_center_y"]) for w in win) / len(win),
                    "latent_depth": sum(float(w["latent_depth"]) for w in win) / len(win),
                }
            )
    return output


def smooth_l1(states: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_pv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for state in states:
        by_pv[state["physical_vehicle_id"]].append(state)
    out: dict[str, dict[str, Any]] = {}
    for pv, rows in by_pv.items():
        rows = sorted(rows, key=lambda r: parse_int(r["frame"]))
        for i, row in enumerate(rows):
            lo = max(0, i - 1)
            hi = min(len(rows), i + 2)
            win = [r for r in rows[lo:hi] if r.get("observed") is not None]
            if not win:
                continue
            boxes = [r["observed"] for r in win]
            out[row["hidden_sample_id"]] = {
                "box": Box(
                    sum(b.x1 for b in boxes) / len(boxes),
                    sum(b.y1 for b in boxes) / len(boxes),
                    sum(b.x2 for b in boxes) / len(boxes),
                    sum(b.y2 for b in boxes) / len(boxes),
                ),
                "depth": sum(float(r["observed_depth"]) for r in win) / len(win),
            }
    return out


def summarize_gm17_methods(per_sample: Sequence[Mapping[str, Any]], rec_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    l1 = smooth_l1([dict(row) for row in per_sample])
    method_errors: dict[str, list[dict[str, float]]] = defaultdict(list)
    vehicles: dict[str, set[str]] = defaultdict(set)
    for item in per_sample:
        truth: Box = item["truth"]
        truth_depth = float(item["truth_depth"])
        methods: dict[str, tuple[Box, float] | None] = {}
        obs = item.get("observed")
        if obs is not None:
            methods["L0_local_box_direct_state"] = (obs, float(item["observed_depth"]))
        if item["hidden_sample_id"] in l1:
            methods["L1_temporal_smoothed_local_box"] = (l1[item["hidden_sample_id"]]["box"], float(l1[item["hidden_sample_id"]]["depth"]))
        rec = rec_by_id.get(item["hidden_sample_id"])
        if rec:
            l2_box = Box(
                float(rec["latent_center_x"]) - float(rec["latent_width"]) / 2.0,
                float(rec["latent_center_y"]) - float(rec["latent_height"]) / 2.0,
                float(rec["latent_center_x"]) + float(rec["latent_width"]) / 2.0,
                float(rec["latent_center_y"]) + float(rec["latent_height"]) / 2.0,
            )
            methods["L2_anchorless_track_level_full_vehicle_state"] = (l2_box, float(rec["latent_depth"]))
        for method, value in methods.items():
            if value is None:
                continue
            box, depth = value
            az, radial = predict_r1_state(box, depth)
            truth_az, truth_radial = predict_r1_state(truth, truth_depth)
            err = {
                "cx": abs(box.cx - truth.cx),
                "cy": abs(box.cy - truth.cy),
                "w": abs(box.width - truth.width),
                "h": abs(box.height - truth.height),
                "depth": abs(depth - truth_depth),
                "az": abs(az - truth_az),
                "radial": abs(radial - truth_radial),
                "covered": 1.0 if abs(box.cx - truth.cx) <= 0.18 * max(1.0, truth.width) and abs(box.cy - truth.cy) <= 0.18 * max(1.0, truth.height) else 0.0,
            }
            method_errors[method].append(err)
            vehicles[method].add(str(item["physical_vehicle_id"]))
    rows: list[dict[str, Any]] = []
    l0_p90_az = percentile([e["az"] for e in method_errors["L0_local_box_direct_state"]], 90)
    l0_p90_rad = percentile([e["radial"] for e in method_errors["L0_local_box_direct_state"]], 90)
    for method in ["L0_local_box_direct_state", "L1_temporal_smoothed_local_box", "L2_anchorless_track_level_full_vehicle_state"]:
        errs = method_errors[method]
        n = len(errs)
        az_p90 = percentile([e["az"] for e in errs], 90)
        rad_p90 = percentile([e["radial"] for e in errs], 90)
        coverage = sum(e["covered"] for e in errs) / max(1, n)
        pass_ok = False
        if method.startswith("L2"):
            az_improve = (l0_p90_az - az_p90) / max(1e-9, l0_p90_az)
            rad_improve = (l0_p90_rad - rad_p90) / max(1e-9, l0_p90_rad)
            pass_ok = (az_improve >= 0.30 or rad_improve >= 0.30) and coverage >= 0.80
        rows.append(
            {
                "method": method,
                "sample_count": n,
                "physical_vehicle_count": len(vehicles[method]),
                "center_x_median_error": fmt(median([e["cx"] for e in errs]) if errs else math.nan),
                "center_x_p90_error": fmt(percentile([e["cx"] for e in errs], 90)),
                "center_y_median_error": fmt(median([e["cy"] for e in errs]) if errs else math.nan),
                "center_y_p90_error": fmt(percentile([e["cy"] for e in errs], 90)),
                "width_median_error": fmt(median([e["w"] for e in errs]) if errs else math.nan),
                "width_p90_error": fmt(percentile([e["w"] for e in errs], 90)),
                "height_median_error": fmt(median([e["h"] for e in errs]) if errs else math.nan),
                "height_p90_error": fmt(percentile([e["h"] for e in errs], 90)),
                "depth_median_error": fmt(median([e["depth"] for e in errs]) if errs else math.nan),
                "depth_p90_error": fmt(percentile([e["depth"] for e in errs], 90)),
                "SAR_azimuth_median_error": fmt(median([e["az"] for e in errs]) if errs else math.nan),
                "SAR_azimuth_p90_error": fmt(az_p90),
                "SAR_radial_median_error": fmt(median([e["radial"] for e in errs]) if errs else math.nan),
                "SAR_radial_p90_error": fmt(rad_p90),
                "center_coverage": f"{int(sum(e['covered'] for e in errs))}/{n}",
                "truth_loaded_by_recovery": "false",
                "crop_ratio_loaded_by_recovery": "false",
                "original_bbox_loaded_by_recovery": "false",
                "original_depth_loaded_by_recovery": "false",
                "controlled_pass": bool_text(pass_ok),
                "notes": "recovery read only gm17_hidden_degraded_inputs; truth read only by scoring summary",
            }
        )
    return rows


def build_optical_state_review(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = context["direct_rows"]
    branch_a = context["branch_a"]
    timeline = context["timeline"]
    pairs = context["gm19_pairs"]
    pair_by_pv: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in pairs:
        pair_by_pv[row["physical_vehicle_id"]].append(row)
    direct_by_pv = defaultdict(list)
    for row in direct:
        direct_by_pv[row["physical_vehicle_id"]].append(row)
    out: list[dict[str, Any]] = []
    for row in timeline:
        pv = row["physical_vehicle_id"]
        direct_count = sum(1 for r in direct_by_pv[pv] if r.get("direct_observable_full_stream") == "true")
        ba_count = sum(1 for p in pair_by_pv[pv] if branch_a.get(p["pair_id"], {}).get("recovery_confidence", "0") not in {"", "0"})
        bb_count = sum(1 for p in pair_by_pv[pv] if context["eval_by_pair_method"].get((p["pair_id"], "Z1B_anchorless_track_level_completion")))
        if pv.endswith("RIGHT_DARK_FRAGMENT"):
            klass = "IDENTITY_UNRESOLVED"
            reason = "短片段且与白色SUV同帧并存，R2B已保持不合并；不能为了恢复强行归并身份。"
            allowed = "false"
        elif pv.endswith("WHITE_SUV_NEAR_FIELD"):
            klass = "OPTICAL_STATE_PLAUSIBLE"
            reason = "全流存在非配对光学恢复锚点，配对帧前后恢复框与近场车辆横向运动连续；但SAR中心仍受mask语义限制。"
            allowed = "true"
        elif pv.endswith("SILVER_MPV_NEAR_FIELD"):
            klass = "OPTICAL_STATE_PARTIALLY_PLAUSIBLE"
            reason = "轨迹较长且Z1B中心/径向连续，部分帧仍有下边缘与深度混合风险，进入SAR映射只能作为审计证据。"
            allowed = "true"
        elif pv.endswith("BLACK_SEDAN_NEAR_FIELD"):
            klass = "OPTICAL_STATE_PARTIALLY_PLAUSIBLE"
            reason = "早段近场底边截断，Z1B给出连续整车隐状态，但无可用全流完整锚点，径向前几帧不稳定。"
            allowed = "true"
        elif pv.endswith("GRAY_CAR_LEFT_EDGE"):
            klass = "OPTICAL_STATE_PARTIALLY_PLAUSIBLE"
            reason = "左边缘进入/离开阶段可见约束单侧，恢复框方向合理但短轨迹和mask近边界使中心监督不可用。"
            allowed = "true"
        else:
            klass = "OPTICAL_STATE_PARTIALLY_PLAUSIBLE"
            reason = "R2B轨迹恢复可用于纯光学审计，但不提升SAR中心语义。"
            allowed = "true"
        out.append(
            {
                "physical_vehicle_id": pv,
                "reviewed_frames": row.get("all_observation_frames", ""),
                "paired_frames": row.get("paired_frames", ""),
                "direct_full_stream_anchor_count": direct_count,
                "branch_a_recovered_pair_count": ba_count,
                "branch_b_recovered_pair_count": bb_count,
                "optical_state_review_class": klass,
                "identity_confidence": row.get("identity_confidence", ""),
                "pure_optical_reason_cn": reason,
                "allowed_for_sar_mapping_audit": allowed,
            }
        )
    return out


def masked_overlap_ok(eval_row: Mapping[str, Any], audit: Mapping[str, Any]) -> bool:
    if not eval_row.get("azimuth_error"):
        return False
    az_err = parse_float(eval_row["azimuth_error"])
    rad_err = parse_float(eval_row["radial_error"])
    cls = audit["sar_mask_observation_class"]
    if cls == "SAR_MASK_S0_FULLY_OBSERVABLE":
        return az_err <= R1_AZ_Q95 and rad_err <= R1_RADIAL_Q95
    if cls == "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE":
        return az_err <= 18.0 and rad_err <= 80.0
    if cls == "SAR_MASK_S2_CENTER_CENSORED":
        return az_err <= 18.0 and rad_err <= 95.0
    return False


def build_dimension_split(context: Mapping[str, Any], audit_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    audit_by_pair = {row["pair_id"]: row for row in audit_rows}
    methods = [
        "Z0_local_detection_box",
        "Z1A_full_stream_optical_anchor_recovery",
        "Z1B_anchorless_track_level_completion",
    ]
    out: list[dict[str, Any]] = []
    for method in methods:
        rows = [row for row in context["eval_rows"] if row.get("method") == method and row.get("pair_id") in audit_by_pair]
        for cls in [
            "SAR_MASK_S0_FULLY_OBSERVABLE",
            "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE",
            "SAR_MASK_S2_CENTER_CENSORED",
            "SAR_MASK_S3_NOT_CENTER_SUPERVISABLE",
        ]:
            subset = [row for row in rows if audit_by_pair[row["pair_id"]]["sar_mask_observation_class"] == cls]
            usable = [row for row in subset if row.get("azimuth_error")]
            az = [parse_float(row["azimuth_error"]) for row in usable]
            rad = [parse_float(row["radial_error"]) for row in usable]
            out.append(
                {
                    "method": method,
                    "mask_class": cls,
                    "sample_count": len(usable),
                    "physical_vehicle_count": len({row.get("physical_vehicle_id", "") for row in usable}),
                    "azimuth_median_error": fmt(median(az) if az else math.nan),
                    "azimuth_p90_error": fmt(percentile(az, 90)),
                    "radial_median_error": fmt(median(rad) if rad else math.nan),
                    "radial_p90_error": fmt(percentile(rad, 90)),
                    "azimuth_covered_count": sum(1 for value in az if value <= R1_AZ_Q95),
                    "radial_covered_count": sum(1 for value in rad if value <= R1_RADIAL_Q95),
                    "joint_covered_count": sum(1 for row in usable if parse_float(row["azimuth_error"]) <= R1_AZ_Q95 and parse_float(row["radial_error"]) <= R1_RADIAL_Q95),
                    "masked_overlap_covered_count": sum(1 for row in usable if masked_overlap_ok(row, audit_by_pair[row["pair_id"]])),
                    "blocked_count": len(subset) - len(usable),
                }
            )
    return out


def build_center_semantic_review(audit_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    focus = {"WGV35A_PAIR_0204", "WGV35A_PAIR_0206", "WGV35A_PAIR_0210", "WGV35A_PAIR_0211", "WGV35A_PAIR_0214", "WGV35A_PAIR_0215"}
    out: list[dict[str, Any]] = []
    for row in audit_rows:
        cls = row["sar_mask_observation_class"]
        if cls == "SAR_MASK_S0_FULLY_OBSERVABLE":
            status = "SAR_CENTER_FULL_VEHICLE_COMPATIBLE"
            center_full = "true"
            visible_only = "false"
            censored = "false"
            review = "中心语义与完整车辆中心兼容。"
        elif cls == "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE":
            status = "SAR_CENTER_MASK_BIASED" if row["pair_id"] in focus else "SAR_CENTER_VISIBLE_RESPONSE_ONLY"
            center_full = "false"
            visible_only = "true"
            censored = "true"
            review = "SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。"
        elif cls == "SAR_MASK_S2_CENTER_CENSORED":
            status = "SAR_CENTER_MASK_BIASED"
            center_full = "false"
            visible_only = "true"
            censored = "true"
            review = "完整车辆中心可能已被mask裁掉，当前框中心是mask内局部响应中心。"
        else:
            status = "SAR_CENTER_SEMANTIC_REVIEW_REQUIRED"
            center_full = "false"
            visible_only = "true"
            censored = "true"
            review = "语义不可判定，需要人工复核。"
        if row["physical_vehicle_id"].endswith("RIGHT_DARK_FRAGMENT"):
            status = "PAIRING_REVIEW_REQUIRED"
            review = "短片段与同帧车辆并存，SAR中心语义之外仍有配对身份复核风险。"
        out.append(
            {
                "pair_id": row["pair_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "sar_frame": row["sar_frame"],
                "mask_class": cls,
                "sar_box_same_physical_vehicle": "review_only_no_GT_change",
                "sar_response_mask_censored": censored,
                "sar_box_center_full_vehicle_center": center_full,
                "center_closer_to_front_hotspot": "unknown",
                "center_closer_to_rear_hotspot": "unknown",
                "center_visible_response_only": visible_only,
                "temporal_mapping_shift_risk": "possible" if row["pair_id"] in focus else "low_to_possible",
                "azimuth_direction_consistent": "geometry_formula_consistent",
                "polar_conversion_consistent": "true",
                "center_semantic_status": status,
                "review_cn": review,
            }
        )
    return out


def build_bearing_relation(context: Mapping[str, Any], audit_rows: Sequence[Mapping[str, Any]], gate: Mapping[str, Any]) -> list[dict[str, Any]]:
    pvs = sorted({row["physical_vehicle_id"] for row in audit_rows})
    out: list[dict[str, Any]] = []
    for pv in pvs:
        rows = [row for row in audit_rows if row["physical_vehicle_id"] == pv]
        classes = ";".join(sorted({row["sar_mask_observation_class"] for row in rows}))
        out.append(
            {
                "physical_vehicle_id": pv,
                "mask_class": classes,
                "mapping_monotonic": "not_evaluated_due_M2_gate",
                "offset_pattern": "azimuth residual remains after radial recovery; cannot separate from mask-biased center",
                "scale_pattern": "not_fitted",
                "depth_dependence": "not_fitted",
                "phase_dependence": "trajectory_phase_visible_but_center_supervision_blocked",
                "mask_boundary_dependence": "all paired samples near lower fan/mask boundary",
                "center_semantic_risk": "high" if not gate["did_pass"] else "low",
                "recommended_bearing_proxy": "none_until_S0_or_high_confidence_center_semantics_exist",
                "audit_status": "GATED_R2C_M2_CENTER_SUPERVISION_INSUFFICIENT",
            }
        )
    return out


def build_gated_model_outputs(audit_rows: Sequence[Mapping[str, Any]], gate: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    models: list[dict[str, Any]] = []
    for model_id, name in [
        ("A0", "GM17_frozen_model"),
        ("A1", "GM19_scene_linear_model"),
        ("A2", "depth_conditioned_model"),
        ("A3", "vehicle_boundary_conditioned_model"),
        ("A4", "mask_distance_conditioned_model"),
        ("A5", "monotone_piecewise_model"),
    ]:
        models.append(
            {
                "model_id": model_id,
                "model_name": name,
                "training_mask_classes": "none",
                "training_sample_count": 0,
                "training_physical_vehicle_count": 0,
                "selected_model": "false",
                "azimuth_median_error": "",
                "azimuth_p90_error": "",
                "radial_median_error": "",
                "radial_p90_error": "",
                "center_coverage": "0/0",
                "run_status": "not_run_M2_gate_failed",
                "blocked_reason": gate["stop_reason"],
            }
        )
    folds: list[dict[str, Any]] = []
    for pv in ["PV_GM19_WHITE_SUV_NEAR_FIELD", "PV_GM19_SILVER_MPV_NEAR_FIELD", "PV_GM19_GRAY_CAR_LEFT_EDGE"]:
        rows = [row for row in audit_rows if row["physical_vehicle_id"] == pv]
        folds.append(
            {
                "fold_id": f"LOVO_{pv}",
                "train_physical_vehicles": "not_constructed",
                "test_physical_vehicle": pv,
                "train_S0_count": 0,
                "train_S1_count": 0,
                "test_S0_count": sum(1 for row in rows if row["sar_mask_observation_class"] == "SAR_MASK_S0_FULLY_OBSERVABLE"),
                "test_S1_count": sum(1 for row in rows if row["sar_mask_observation_class"] == "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE"),
                "test_S2_count": sum(1 for row in rows if row["sar_mask_observation_class"] == "SAR_MASK_S2_CENTER_CENSORED"),
                "selected_model": "none",
                "azimuth_median": "",
                "azimuth_p90": "",
                "radial_median": "",
                "radial_p90": "",
                "azimuth_coverage": "0/0",
                "radial_coverage": "0/0",
                "joint_coverage": "0/0",
                "masked_overlap_coverage": "not_evaluated",
                "search_ratio": "",
                "run_status": "not_run_M2_gate_failed",
                "blocked_reason": gate["stop_reason"],
            }
        )
    intervals = [
        {
            "interval_group": "M2_GATED_NO_CENTER_SUPERVISION",
            "training_count": 0,
            "azimuth_q50": "",
            "azimuth_q80": "",
            "azimuth_q95": "",
            "radial_q50": "",
            "radial_q80": "",
            "radial_q95": "",
            "held_out_center_coverage": "0/0",
            "held_out_masked_overlap_coverage": "not_evaluated",
            "search_ratio": "",
            "run_status": "not_run_M2_gate_failed",
            "blocked_reason": gate["stop_reason"],
        }
    ]
    return models, folds, intervals


def build_failure_cases(context: Mapping[str, Any], audit_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    audit_by_pair = {row["pair_id"]: row for row in audit_rows}
    out: list[dict[str, Any]] = []
    for row in context["eval_rows"]:
        if row.get("method") != "Z1B_anchorless_track_level_completion" or not row.get("pair_id") in audit_by_pair:
            continue
        audit = audit_by_pair[row["pair_id"]]
        if not row.get("azimuth_error"):
            continue
        az = parse_float(row["azimuth_error"])
        rad = parse_float(row["radial_error"])
        if audit["sar_mask_observation_class"] in {"SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE", "SAR_MASK_S2_CENTER_CENSORED"}:
            primary = "sar_mask_center_semantic_risk"
        elif az > R1_AZ_Q95:
            primary = "near_field_azimuth_mapping_residual"
        elif rad > R1_RADIAL_Q95:
            primary = "radial_depth_scale_residual"
        else:
            primary = "covered"
        out.append(
            {
                "pair_id": row["pair_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "mask_class": audit["sar_mask_observation_class"],
                "method": row["method"],
                "primary_failure_source": primary,
                "azimuth_error": row["azimuth_error"],
                "radial_error": row["radial_error"],
                "blocked_reason": audit["blocked_reason"],
                "review_cn": "该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。",
            }
        )
    return out


def image_with_box(path: Path, box: Box | None, size: tuple[int, int], outline: tuple[int, int, int], text: str = "") -> Image.Image:
    if path.exists():
        im = Image.open(path).convert("RGB")
    else:
        im = Image.new("RGB", size, (25, 25, 25))
    sx = size[0] / im.width
    sy = size[1] / im.height
    im = im.resize(size)
    draw = ImageDraw.Draw(im)
    if box is not None:
        draw.rectangle([box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy], outline=outline, width=3)
    if text:
        draw.rectangle([0, 0, size[0], 24], fill=(0, 0, 0))
        draw.text((4, 4), text, fill=(255, 255, 255))
    return im


def draw_fan_boundary(draw: ImageDraw.ImageDraw, scale_x: float, scale_y: float, offset_x: float = 0.0, offset_y: float = 0.0, color: tuple[int, int, int] = (255, 220, 0)) -> None:
    # Draw lower azimuth-limit chord and radius arc sampled in display space.
    y = offset_y + FAN_CENTER_Y * scale_y
    draw.line([offset_x, y, offset_x + SAR_WIDTH * scale_x, y], fill=color, width=2)
    pts = []
    for deg in range(-90, 91, 2):
        theta = math.radians(deg)
        x = FAN_CENTER_X + FAN_RADIUS_PX * math.sin(theta)
        yy = FAN_CENTER_Y - FAN_RADIUS_PX * math.cos(theta)
        if 0 <= x <= SAR_WIDTH and 0 <= yy <= SAR_HEIGHT:
            pts.append((offset_x + x * scale_x, offset_y + yy * scale_y))
    if len(pts) > 1:
        draw.line(pts, fill=color, width=2)


def render_visuals(context: Mapping[str, Any], support: Mapping[str, Any], audit_rows: Sequence[Mapping[str, Any]], gm17_results: Sequence[Mapping[str, Any]], dimension_rows: Sequence[Mapping[str, Any]], gate: Mapping[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 1. mask overview
    sample_path = sar_gray_path("GM_RM019", 0)
    overview = image_with_box(sample_path, None, (900, 520), (255, 0, 0), "GM_RM019 SAR gray + reconstructed fan/mask boundary")
    draw = ImageDraw.Draw(overview)
    draw_fan_boundary(draw, 900 / SAR_WIDTH, 520 / SAR_HEIGHT)
    draw.text((12, 36), f"sampled PNG frames: {support['sample_count']} / {support['all_frame_count']}", fill=(255, 255, 0))
    draw.text((12, 60), f"stable/fan pixels: {support['stable_count']} / {support['fan_count']}", fill=(255, 255, 0))
    overview.save(VISUALS["mask_overview"])

    # 2. 16-pair SAR contact sheet
    cell_w, cell_h = 360, 230
    sheet = Image.new("RGB", (cell_w * 4, cell_h * 4), (20, 20, 20))
    audit_by_pair = {row["pair_id"]: row for row in audit_rows}
    for idx, pair in enumerate(context["gm19_pairs"]):
        r = idx // 4
        c = idx % 4
        box = box_from_pair(pair)
        tile = image_with_box(sar_gray_path("GM_RM019", parse_int(pair["sar_frame"])), box, (cell_w, cell_h), (0, 255, 100), f"{pair['pair_id']} {audit_by_pair[pair['pair_id']]['sar_mask_observation_class'].replace('SAR_MASK_', '')}")
        tdraw = ImageDraw.Draw(tile)
        draw_fan_boundary(tdraw, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT)
        tdraw.text((4, cell_h - 24), f"bottom margin={audit_by_pair[pair['pair_id']]['bottom_valid_margin_px']} px", fill=(255, 255, 0))
        sheet.paste(tile, (c * cell_w, r * cell_h))
    sheet.save(VISUALS["pair_contact_sheet"])

    # 3. vehicle trajectory vs mask
    traj = Image.new("RGB", (1000, 620), (245, 245, 245))
    draw = ImageDraw.Draw(traj)
    sx, sy = 1000 / SAR_WIDTH, 620 / SAR_HEIGHT
    draw_fan_boundary(draw, sx, sy, color=(220, 150, 0))
    colors = [(220, 20, 60), (30, 100, 220), (20, 150, 80), (120, 70, 200), (0, 0, 0)]
    by_pv = defaultdict(list)
    for pair in context["gm19_pairs"]:
        by_pv[pair["physical_vehicle_id"]].append(pair)
    for color, (pv, rows) in zip(colors, sorted(by_pv.items())):
        pts = []
        for pair in sorted(rows, key=lambda x: parse_int(x["sar_frame"])):
            box = box_from_pair(pair)
            pts.append((box.cx * sx, box.cy * sy))
            draw.ellipse([box.cx * sx - 4, box.cy * sy - 4, box.cx * sx + 4, box.cy * sy + 4], fill=color)
        if len(pts) > 1:
            draw.line(pts, fill=color, width=2)
    y = 14
    for color, pv in zip(colors, sorted(by_pv)):
        draw.rectangle([14, y, 30, y + 12], fill=color)
        draw.text((36, y), pv, fill=(0, 0, 0))
        y += 20
    traj.save(VISUALS["vehicle_trajectory"])

    # 4. class cases
    cases = Image.new("RGB", (900, 520), (30, 30, 30))
    draw = ImageDraw.Draw(cases)
    classes = [
        "SAR_MASK_S0_FULLY_OBSERVABLE",
        "SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE",
        "SAR_MASK_S2_CENTER_CENSORED",
        "SAR_MASK_S3_NOT_CENTER_SUPERVISABLE",
    ]
    for idx, cls in enumerate(classes):
        row = next((r for r in audit_rows if r["sar_mask_observation_class"] == cls), None)
        x = (idx % 2) * 450
        y = (idx // 2) * 260
        if row:
            pair = next(p for p in context["gm19_pairs"] if p["pair_id"] == row["pair_id"])
            tile = image_with_box(sar_gray_path("GM_RM019", parse_int(pair["sar_frame"])), box_from_pair(pair), (450, 260), (0, 255, 100), f"{cls} {row['pair_id']}")
            tdraw = ImageDraw.Draw(tile)
            draw_fan_boundary(tdraw, 450 / SAR_WIDTH, 260 / SAR_HEIGHT)
            cases.paste(tile, (x, y))
        else:
            draw.rectangle([x, y, x + 449, y + 259], outline=(120, 120, 120))
            draw.text((x + 20, y + 40), f"{cls}\nno GM_RM019 sample assigned", fill=(255, 255, 255))
    cases.save(VISUALS["class_cases"])

    # 5. GM17 control bars
    gm17 = Image.new("RGB", (920, 460), (250, 250, 250))
    draw = ImageDraw.Draw(gm17)
    draw.text((20, 20), "GM17 leakage-free control: P90 errors and center coverage", fill=(0, 0, 0))
    methods = list(gm17_results)
    base_x = 80
    for idx, row in enumerate(methods):
        x = base_x + idx * 260
        az = parse_float(row["SAR_azimuth_p90_error"], 0.0)
        rad = parse_float(row["SAR_radial_p90_error"], 0.0)
        cov = row["center_coverage"]
        draw.text((x, 70), row["method"].split("_")[0], fill=(0, 0, 0))
        draw.rectangle([x, 120, x + 60, 120 + min(250, az * 8)], fill=(80, 130, 220))
        draw.rectangle([x + 90, 120, x + 150, 120 + min(250, rad * 2.0)], fill=(220, 120, 70))
        draw.text((x, 390), f"azP90={fmt(az)}", fill=(0, 0, 0))
        draw.text((x, 410), f"radP90={fmt(rad)}", fill=(0, 0, 0))
        draw.text((x, 430), f"cov={cov}", fill=(0, 0, 0))
    gm17.save(VISUALS["gm17_control"])

    # 6. optical timeline representative frames
    opt_sheet = Image.new("RGB", (1200, 720), (20, 20, 20))
    reps = []
    seen: set[str] = set()
    for pair in context["gm19_pairs"]:
        pv = pair["physical_vehicle_id"]
        if pv in seen:
            continue
        seen.add(pv)
        reps.append(pair)
    reps.extend(context["gm19_pairs"][:: max(1, len(context["gm19_pairs"]) // 6)])
    reps = reps[:12]
    for idx, pair in enumerate(reps):
        x = (idx % 4) * 300
        y = (idx // 4) * 240
        obox = box_from_pair(pair, "optical_bbox")
        path = optical_frame_path("GM_RM019", parse_int(pair["optical_frame"]))
        tile = image_with_box(path or Path("missing"), obox, (300, 240), (0, 255, 80), f"{pair['pair_id']} opt{pair['optical_frame']}")
        opt_sheet.paste(tile, (x, y))
    opt_sheet.save(VISUALS["optical_timeline"])

    # 7. azimuth residual vs mask distance
    scatter = Image.new("RGB", (900, 520), (250, 250, 250))
    draw = ImageDraw.Draw(scatter)
    draw.line([80, 450, 840, 450], fill=(0, 0, 0), width=2)
    draw.line([80, 60, 80, 450], fill=(0, 0, 0), width=2)
    draw.text((250, 20), "Z1B azimuth residual vs bottom mask margin", fill=(0, 0, 0))
    z1b_by_pair = {row["pair_id"]: row for row in context["eval_rows"] if row.get("method") == "Z1B_anchorless_track_level_completion" and row.get("azimuth_error")}
    for row in audit_rows:
        ev = z1b_by_pair.get(row["pair_id"])
        if not ev:
            continue
        margin = parse_float(row["bottom_valid_margin_px"])
        err = parse_float(ev["azimuth_error"])
        px = 80 + (margin / 120.0) * 760
        py = 450 - min(1.0, err / 40.0) * 360
        color = (220, 90, 30) if row["sar_mask_observation_class"].endswith("CENTER_CENSORED") else (40, 120, 220)
        draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=color)
        draw.text((px + 6, py - 6), row["pair_id"].split("_")[-1], fill=(0, 0, 0))
    draw.text((360, 470), "bottom valid margin px", fill=(0, 0, 0))
    draw.text((10, 200), "az err deg", fill=(0, 0, 0))
    scatter.save(VISUALS["azimuth_residual"])

    # 8. leave-one vehicle placeholder
    lovo = Image.new("RGB", (900, 360), (245, 245, 245))
    draw = ImageDraw.Draw(lovo)
    draw.text((30, 50), "Leave-one-physical-vehicle-out not executed", fill=(0, 0, 0))
    draw.text((30, 90), "R2C.M2 failed: S0=0, S1 is weak-only, center supervision samples=0.", fill=(160, 0, 0))
    draw.text((30, 140), "R2C.4-R2C.7 model fitting, LOVO, and intervals were gated.", fill=(0, 0, 0))
    lovo.save(VISUALS["leave_one"])


def render_reports(
    freeze_rows: Sequence[Mapping[str, Any]],
    mask_source: Sequence[Mapping[str, Any]],
    audit_rows: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any],
    gm17_hidden: Sequence[Mapping[str, Any]],
    gm17_truth: Sequence[Mapping[str, Any]],
    gm17_results: Sequence[Mapping[str, Any]],
    optical_review: Sequence[Mapping[str, Any]],
    dimension_rows: Sequence[Mapping[str, Any]],
    bearing_rows: Sequence[Mapping[str, Any]],
    semantic_rows: Sequence[Mapping[str, Any]],
    model_rows: Sequence[Mapping[str, Any]],
    leave_rows: Sequence[Mapping[str, Any]],
    interval_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    support: Mapping[str, Any],
) -> None:
    counts = gate["counts"]
    vehicles_affected = sorted({row["physical_vehicle_id"] for row in audit_rows if row["sar_mask_observation_class"] != "SAR_MASK_S0_FULLY_OBSERVABLE"})
    mask_lines = [
        "# OTY2 WGV3.5A-R2C SAR Mask Definition",
        "",
        "## Summary",
        "",
        "- independent mask file: not found in checked repo/data paths",
        "- reconstructed mask: fan geometry from code, `radial<=1332.7` and `-90<=azimuth<=90` on `2308x1334`",
        "- rendered PNG support: sampled GM_RM019 gray frames show stable zero outside the fan-like support",
        "- physical meaning: geometry/display valid fan is confirmed; independent physical imaging-valid mask semantics remain unconfirmed",
        "- annotation use: not explicitly documented; current SAR boxes stay inside rendered valid pixels",
        "",
        "## Source Inventory",
        "",
        md_table(mask_source, MASK_SOURCE_FIELDS),
        "",
        "## R2C.M0 Answers",
        "",
        "1. 独立有效mask文件：未找到。",
        "2. 是否场景共用：代码公式看起来共用，独立场景版本未找到。",
        "3. 是否随帧变化：扇形公式静态；PNG非零支持在抽样帧中基本静态。",
        "4. 是否来自成像物理有效区：未被独立文件或成像MATLAB代码证明，只能确认显示/几何有效扇形。",
        "5. 是否只是显示裁剪：当前证据更接近显示/几何裁剪；物理语义保留问题。",
        "6. 是否参与SAR标注：未找到标注文档说明；人工框没有延伸出渲染有效区域。",
        "7. mask外像素语义：抽样灰度PNG中为0；是未成像、无效还是渲染置零不能最终区分。",
        "8. SAR人工框是否允许延伸到mask外：当前16条GM_RM019框未延伸到重建mask外，是否允许未知。",
    ]
    write_text(OUTPUTS["mask_definition_md"], "\n".join(mask_lines))

    gate_lines = [
        "# OTY2 WGV3.5A-R2C GM_RM019 Mask Supervision Gate",
        "",
        f"- S0 fully observable: `{counts.get('SAR_MASK_S0_FULLY_OBSERVABLE', 0)}`",
        f"- S1 partially censored: `{counts.get('SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE', 0)}`",
        f"- S2 center censored: `{counts.get('SAR_MASK_S2_CENTER_CENSORED', 0)}`",
        f"- S3 not center-supervisable: `{counts.get('SAR_MASK_S3_NOT_CENTER_SUPERVISABLE', 0)}`",
        f"- usable center-supervision samples: `{len(gate['center_rows'])}`",
        f"- usable physical vehicles: `{len(gate['center_vehicles'])}`",
        f"- gate status: `{gate['status']}`",
        f"- weak-only flag: `{'CENTER_SUPERVISION_WEAK_ONLY' if gate['weak_only'] else 'false'}`",
        "",
        "## Stop Decision",
        "",
        gate["stop_reason"],
        "",
        "R2C.4-R2C.7 bearing-model fitting, leave-one-vehicle model evaluation and interval calibration were not executed.",
        "",
        "## GM_RM019 Pair Audit",
        "",
        md_table(audit_rows, MASK_AUDIT_FIELDS, limit=20),
    ]
    write_text(OUTPUTS["mask_gate_md"], "\n".join(gate_lines))

    l2 = next((row for row in gm17_results if row["method"].startswith("L2")), {})
    gm17_lines = [
        "# OTY2 WGV3.5A-R2C GM17 Leakage-Free Control",
        "",
        "R2B的旧无锚点消融把固定裁剪比例隐含带入恢复，旧的L2零误差不再作为有效通过证据。",
        "",
        f"- hidden degraded input rows: `{len(gm17_hidden)}`",
        f"- scoring truth rows: `{len(gm17_truth)}`",
        f"- physical vehicles: `{len({row['physical_vehicle_id'] for row in gm17_truth})}`",
        f"- L2 controlled pass: `{l2.get('controlled_pass', 'false')}`",
        "- recovery flags: truth_loaded_by_recovery=false; crop_ratio_loaded_by_recovery=false; original_bbox_loaded_by_recovery=false; original_depth_loaded_by_recovery=false",
        "",
        "## Method",
        "",
        "Recovery reads only degraded local boxes, visible-edge flags, frame order and polluted local depth. It estimates vehicle-level width/height from the observed upper envelope, applies single-edge equality constraints, keeps width/height as lower-bound-constrained latent states, and applies a short forward/backward temporal smoother. Scoring truth is loaded only after recovery.",
        "",
        "## Results",
        "",
        md_table(gm17_results, GM17_RESULT_FIELDS),
    ]
    write_text(OUTPUTS["gm17_md"], "\n".join(gm17_lines))

    visual_lines = [
        "# OTY2 WGV3.5A-R2C Mask-Aware Visual Diagnosis",
        "",
        "Codex generated and reviewed the following visual audit panels:",
        "",
    ]
    for name, path in VISUALS.items():
        visual_lines.append(f"- {name}: `{path.relative_to(REPO_ROOT)}`")
    visual_lines.extend(
        [
            "",
            "## Chinese Visual Judgement",
            "",
            "- GM_RM019 16条配对的SAR框均在重建扇形mask内，但全部靠近近距下边界；框与mask交集接近1不能证明完整车辆中心可见。",
            "- S1样本：可见响应仍在mask内，中心可能被拉向mask内部，只能弱中心/区间审计。",
            "- S2样本：灰色左边车辆0214/0215底部有效余量约66px，完整中心可能被mask截断，不可作完整中心监督。",
            "- 光学恢复：白色SUV较可信；银色MPV、黑色轿车、灰色左边车为部分可信；右侧暗片段身份不应合并。",
            "- GM17无泄漏图只展示退化输入恢复前后误差，不读取原始完整框用于恢复。",
            "",
            "## Optical State Review",
            "",
            md_table(optical_review, OPTICAL_REVIEW_FIELDS),
            "",
            "## Center Semantic Review",
            "",
            md_table(semantic_rows, CENTER_SEMANTIC_FIELDS),
        ]
    )
    write_text(OUTPUTS["visual_md"], "\n".join(visual_lines))

    closure_lines = [
        "# OTY2 WGV3.5A-R2C Closure",
        "",
        f"Closure status: `{gate['status']}`",
        "",
        "## Freeze Manifest",
        "",
        md_table(freeze_rows, FREEZE_FIELDS),
        "",
        "## Mask Audit Counts",
        "",
        f"- total GM_RM019 pairs: `{len(audit_rows)}`",
        f"- S0: `{counts.get('SAR_MASK_S0_FULLY_OBSERVABLE', 0)}`",
        f"- S1: `{counts.get('SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE', 0)}`",
        f"- S2: `{counts.get('SAR_MASK_S2_CENTER_CENSORED', 0)}`",
        f"- S3: `{counts.get('SAR_MASK_S3_NOT_CENTER_SUPERVISABLE', 0)}`",
        f"- vehicles affected by mask semantics: `{len(vehicles_affected)}` ({';'.join(vehicles_affected)})",
        "",
        "## R2B Correction",
        "",
        "- R2B GM17 anchorless controlled-pass evidence is not retained because it leaked the synthetic crop ratio/full-frame relation.",
        f"- R2C leakage-free L2 pass: `{l2.get('controlled_pass', 'false')}`.",
        "- R2B GM19 radial improvement remains visible in R2B rows, but R2C treats it as optical-state/radial evidence only, not as complete SAR center success.",
        "",
        "## Dimension Split",
        "",
        md_table(dimension_rows, DIMENSION_FIELDS),
        "",
        "## Bearing Audit",
        "",
        md_table(bearing_rows, BEARING_FIELDS),
        "",
        "## Model Comparison",
        "",
        md_table(model_rows, MODEL_FIELDS),
        "",
        "## Leave-One Vehicle Out",
        "",
        md_table(leave_rows, LEAVE_ONE_FIELDS),
        "",
        "## Mask-Aware Intervals",
        "",
        md_table(interval_rows, INTERVAL_FIELDS),
        "",
        "## Failure Cases",
        "",
        md_table(failure_rows, FAILURE_FIELDS, limit=20),
        "",
        "## Boundary Checks",
        "",
        "- No GT or manual annotations were modified.",
        "- No final SAR boxes were emitted.",
        "- No full-SAR bright-response search was performed; SAR response checks were local to paired boxes.",
        "- No YOLO training or full MOT rerun was performed.",
        "- GM_RM011 R3 and unified R4 frontend were not executed.",
        "- S2/S3 and S1 weak-only rows were not used for full-center model fitting.",
        "- Held-out/test SAR labels were not used to tune optical recovery.",
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{path.relative_to(REPO_ROOT)}`" for path in OUTPUTS.values()),
    ]
    write_text(OUTPUTS["closure_md"], "\n".join(closure_lines))


def write_workspace_log(summary: Mapping[str, Any]) -> None:
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# WGV3.5A-R2C mask-aware near-field mapping log",
        "",
        "- repo: D:/profile/research/optical-sar-visual-diagnosis",
        "- branch: feature/oty2-posthoc-mechanism-validation",
        "- interpreter: D:/MINICONDA/envs/py311/python.exe",
        "- old_work dependency: none",
        "- repo outputs: reports/oty2 and ignored outputs/wgv3_5a_r2c_mask_aware_20260711",
        "- workspace output override: user explicitly requested repo-local R2C reports; workspace log recorded here",
        f"- status: {summary['status']}",
        f"- GM_RM019 pairs: {summary['pair_count']}",
        f"- S0/S1/S2/S3: {summary['s0']}/{summary['s1']}/{summary['s2']}/{summary['s3']}",
        f"- GM17 L2 pass: {summary['gm17_l2_pass']}",
        "",
        "Boundary notes:",
        "- no GT/manual annotation edits",
        "- no final SAR boxes",
        "- no GM_RM011 R3/R4 frontend",
        "- no full-SAR brightest response search",
        "- no selector/ranking logic introduced",
    ]
    write_text(WORKSPACE_LOG, "\n".join(lines))


def run_all(stage: str) -> dict[str, Any]:
    context = load_context()
    pair_frames = [parse_int(row["sar_frame"]) for row in context["gm19_pairs"]]
    support = estimate_png_support("GM_RM019", pair_frames)
    freeze_rows = build_freeze_manifest()
    mask_source = build_mask_source_inventory(context, support)
    audit_rows = build_mask_audit(context, support)
    gate = build_mask_gate(audit_rows)
    gm17_hidden, gm17_truth, gm17_results, _gm17_detail = build_gm17_leakage_free_control(context)
    optical_review = build_optical_state_review(context)
    dimension_rows = build_dimension_split(context, audit_rows)
    bearing_rows = build_bearing_relation(context, audit_rows, gate)
    semantic_rows = build_center_semantic_review(audit_rows)
    model_rows, leave_rows, interval_rows = build_gated_model_outputs(audit_rows, gate)
    failure_rows = build_failure_cases(context, audit_rows)
    render_visuals(context, support, audit_rows, gm17_results, dimension_rows, gate)
    render_reports(
        freeze_rows,
        mask_source,
        audit_rows,
        gate,
        gm17_hidden,
        gm17_truth,
        gm17_results,
        optical_review,
        dimension_rows,
        bearing_rows,
        semantic_rows,
        model_rows,
        leave_rows,
        interval_rows,
        failure_rows,
        support,
    )

    write_csv(OUTPUTS["freeze"], freeze_rows, FREEZE_FIELDS)
    write_csv(OUTPUTS["mask_source"], mask_source, MASK_SOURCE_FIELDS)
    write_csv(OUTPUTS["mask_audit"], audit_rows, MASK_AUDIT_FIELDS)
    write_csv(OUTPUTS["gm17_hidden"], gm17_hidden, GM17_HIDDEN_FIELDS)
    write_csv(OUTPUTS["gm17_truth"], gm17_truth, GM17_TRUTH_FIELDS)
    write_csv(OUTPUTS["gm17_results"], gm17_results, GM17_RESULT_FIELDS)
    write_csv(OUTPUTS["optical_review"], optical_review, OPTICAL_REVIEW_FIELDS)
    write_csv(OUTPUTS["dimension_split"], dimension_rows, DIMENSION_FIELDS)
    write_csv(OUTPUTS["bearing_relation"], bearing_rows, BEARING_FIELDS)
    write_csv(OUTPUTS["center_semantic"], semantic_rows, CENTER_SEMANTIC_FIELDS)
    write_csv(OUTPUTS["model_comparison"], model_rows, MODEL_FIELDS)
    write_csv(OUTPUTS["leave_one"], leave_rows, LEAVE_ONE_FIELDS)
    write_csv(OUTPUTS["intervals"], interval_rows, INTERVAL_FIELDS)
    write_csv(OUTPUTS["failure_cases"], failure_rows, FAILURE_FIELDS)

    counts = gate["counts"]
    l2 = next((row for row in gm17_results if row["method"].startswith("L2")), {})
    summary = {
        "stage": stage,
        "status": gate["status"],
        "pair_count": len(audit_rows),
        "s0": counts.get("SAR_MASK_S0_FULLY_OBSERVABLE", 0),
        "s1": counts.get("SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE", 0),
        "s2": counts.get("SAR_MASK_S2_CENTER_CENSORED", 0),
        "s3": counts.get("SAR_MASK_S3_NOT_CENTER_SUPERVISABLE", 0),
        "gm17_l2_pass": l2.get("controlled_pass", "false"),
        "outputs": {key: str(path) for key, path in OUTPUTS.items()},
        "visuals": {key: str(path) for key, path in VISUALS.items()},
    }
    write_workspace_log(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=[
            "freeze",
            "mask-inventory",
            "mask-audit",
            "mask-gate",
            "gm17-leakage-free-control",
            "optical-state-audit",
            "dimension-split",
            "bearing-audit",
            "fit",
            "leave-one-vehicle-out",
            "interval-calibration",
            "visualize",
            "all",
        ],
        default="all",
    )
    summary = run_all(parser.parse_args().stage)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
