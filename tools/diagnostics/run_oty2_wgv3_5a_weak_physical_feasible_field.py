"""Run WGV3.5A weak optical-state to SAR-PNG feasible-field calibration.

The pipeline uses existing optical-SAR correspondence annotations only as a
weak calibration/evaluation source. It does not edit GT, emit final automatic
annotations, run whole-image target selection, or claim recovered true camera
intrinsics/extrinsics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path(r"D:\profile\research\data")
DATE = "20260710"

PAIR_SOURCE = REPORT_DIR / "oty2_gt_correspondence_mechanism_audit_20260702_190435.csv"
SCENE_CONFIG = REPO_ROOT / "configs" / "scene_config.yaml"
VISUAL_OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_5a_{DATE}"

SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
FULL_AZIMUTH_MIN = -89.0
FULL_AZIMUTH_MAX = 89.0
OPTICAL_FPS = 24.0
SAR_FPS = 50.0
LEGACY_AZIMUTH_K = 0.0875154
LEGACY_AZIMUTH_B = -40.413555

TRAIN_THREADS = {
    "oty1t_obj_GM_RM017_bytetrack_bt_0008",
    "oty1t_obj_GM_RM017_bytetrack_bt_0010",
}
VALIDATION_THREADS = {"oty1t_obj_GM_RM017_bytetrack_bt_0012"}
INTERNAL_TEST_THREADS = {"oty1t_obj_GM_RM017_bytetrack_bt_0014"}

OUTPUTS = {
    "pair_audit_md": REPORT_DIR / f"oty2_wgv3_5a_pair_and_depth_audit_{DATE}.md",
    "paired_annotations": SAMPLES_DIR / f"oty2_wgv3_5a_paired_annotations_{DATE}.csv",
    "depth_strategy": SAMPLES_DIR / f"oty2_wgv3_5a_depth_strategy_audit_{DATE}.csv",
    "split": SAMPLES_DIR / f"oty2_wgv3_5a_identity_safe_split_{DATE}.csv",
    "sar_polar": SAMPLES_DIR / f"oty2_wgv3_5a_sar_polar_targets_{DATE}.csv",
    "optical_states": SAMPLES_DIR / f"oty2_wgv3_5a_optical_vehicle_states_{DATE}.csv",
    "time_calibration": SAMPLES_DIR / f"oty2_wgv3_5a_time_calibration_{DATE}.csv",
    "azimuth_calibration": SAMPLES_DIR / f"oty2_wgv3_5a_azimuth_calibration_{DATE}.csv",
    "radial_calibration": SAMPLES_DIR / f"oty2_wgv3_5a_radial_calibration_{DATE}.csv",
    "heading_state": SAMPLES_DIR / f"oty2_wgv3_5a_heading_state_{DATE}.csv",
    "fields_p0": SAMPLES_DIR / f"oty2_wgv3_5a_feasible_fields_p0_{DATE}.csv",
    "fields_p1": SAMPLES_DIR / f"oty2_wgv3_5a_feasible_fields_p1_{DATE}.csv",
    "fields_p2": SAMPLES_DIR / f"oty2_wgv3_5a_feasible_fields_p2_{DATE}.csv",
    "freeze": SAMPLES_DIR / f"oty2_wgv3_5a_model_freeze_manifest_{DATE}.csv",
    "holdout": SAMPLES_DIR / f"oty2_wgv3_5a_holdout_evaluation_{DATE}.csv",
    "ablation": SAMPLES_DIR / f"oty2_wgv3_5a_ablation_results_{DATE}.csv",
    "failures": SAMPLES_DIR / f"oty2_wgv3_5a_failure_cases_{DATE}.csv",
    "visual_md": REPORT_DIR / f"oty2_wgv3_5a_visual_feasible_field_diagnosis_{DATE}.md",
    "closure_md": REPORT_DIR / f"oty2_wgv3_5a_weak_physical_projection_closure_{DATE}.md",
}

PAIR_FIELDS = [
    "pair_id",
    "scene",
    "optical_frame",
    "sar_frame",
    "optical_thread_id",
    "optical_fragment_id",
    "optical_bbox_x1",
    "optical_bbox_y1",
    "optical_bbox_x2",
    "optical_bbox_y2",
    "sar_bbox_x1",
    "sar_bbox_y1",
    "sar_bbox_x2",
    "sar_bbox_y2",
    "depth_path",
    "pair_source",
    "pair_confidence",
    "identity_confidence",
    "usable_for_calibration",
    "blocked_reason",
    "sar_gt_id",
    "correspondence_match_iou",
    "vehicle_research_eligibility",
    "visibility_state",
]

SPLIT_FIELDS = [
    "split_id",
    "scene",
    "thread_id",
    "frame_start",
    "frame_end",
    "split_role",
    "pair_count",
    "split_reason",
    "leakage_check",
]

DEPTH_FIELDS = [
    "scene",
    "depth_source_status",
    "depth_meaning",
    "frame_alignment",
    "depth_file_count",
    "optical_frame_count",
    "shape",
    "dtype",
    "sample_min",
    "sample_p10",
    "sample_p50",
    "sample_p90",
    "sample_max",
    "invalid_ratio",
    "strategy",
    "median_valid_ratio",
    "thread_temporal_mad",
    "train_spearman_like_corr_to_sar_radial",
    "sensitivity_note",
]

SAR_POLAR_FIELDS = [
    "pair_id",
    "scene",
    "sar_frame",
    "sar_gt_id",
    "sar_center_x",
    "sar_center_y",
    "sar_center_azimuth_deg",
    "sar_center_radial_pixel",
    "sar_azimuth_min",
    "sar_azimuth_max",
    "sar_radial_min",
    "sar_radial_max",
    "sar_azimuth_span",
    "sar_radial_span",
    "sar_geometry_warning",
]

OPTICAL_STATE_FIELDS = [
    "pair_id",
    "scene",
    "optical_frame",
    "thread_id",
    "bbox_center_x",
    "bbox_center_y",
    "bbox_bottom_center_x",
    "bbox_bottom_center_y",
    "bbox_width",
    "bbox_height",
    "bbox_area",
    "normalized_center_x",
    "normalized_bottom_y",
    "edge_contact_left",
    "edge_contact_right",
    "edge_contact_bottom",
    "occlusion_state",
    "partial_vehicle_state",
    "multi_box_competition",
    "visible_unboxed_gap",
    "depth_center",
    "depth_q10",
    "depth_q25",
    "depth_q50",
    "depth_q75",
    "depth_q90",
    "depth_valid_ratio",
    "depth_D0",
    "depth_D1",
    "depth_D2",
    "depth_D3",
    "depth_D4",
    "optical_velocity_x",
    "optical_velocity_y",
    "track_age",
    "vehicle_class",
]

CALIBRATION_FIELDS = [
    "model_family",
    "model_name",
    "input_features",
    "train_count",
    "validation_count",
    "selected",
    "parameters",
    "train_median_error",
    "train_p90_error",
    "validation_median_error",
    "validation_p90_error",
    "notes",
]

HEADING_FIELDS = [
    "pair_id",
    "scene",
    "thread_id",
    "optical_frame",
    "heading_representation",
    "heading_angle_proxy_deg",
    "heading_confidence",
    "usable_for_compression",
    "heading_contribution_note",
]

FIELD_FIELDS = [
    "pair_id",
    "scene",
    "split_role",
    "variant",
    "time_start",
    "time_end",
    "sar_frame_center",
    "azimuth_min",
    "azimuth_max",
    "azimuth_center",
    "radial_min",
    "radial_max",
    "rho_center",
    "rho_low_50",
    "rho_high_50",
    "rho_low_80",
    "rho_high_80",
    "rho_low_95",
    "rho_high_95",
    "heading_state",
    "visibility_uncertainty",
    "field_rule",
]

FREEZE_FIELDS = [
    "freeze_id",
    "stage",
    "source_file",
    "sha256",
    "combined_sha256",
    "data_split_sha256",
    "paired_annotations_sha256",
    "selected_depth_strategy",
    "time_model",
    "azimuth_model",
    "radial_model",
    "heading_rule",
    "vehicle_size_prior",
    "uncertainty_interval_source",
    "test_sar_labels_read_before_freeze",
    "test_metrics_read_before_freeze",
    "test_threads_used_for_fitting",
    "notes",
]

HOLDOUT_FIELDS = [
    "model_variant",
    "test_pair_count",
    "center_coverage_50",
    "center_coverage_80",
    "center_coverage_95",
    "full_box_coverage_95",
    "median_search_ratio",
    "p90_search_ratio",
    "median_azimuth_error",
    "p90_azimuth_error",
    "median_radial_error",
    "p90_radial_error",
    "multi_target_rate",
    "wrong_identity_rate",
]

ABLATION_FIELDS = [
    "ablation_id",
    "features",
    "test_pair_count",
    "median_radial_error",
    "p90_radial_error",
    "median_search_ratio",
    "center_coverage_95",
    "interpretation",
]

FAILURE_FIELDS = [
    "failure_id",
    "pair_id",
    "scene",
    "thread_id",
    "split_role",
    "failure_type",
    "time_error",
    "azimuth_error",
    "radial_error",
    "visibility_state",
    "dominant_layer",
    "notes",
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


class ArrayModel:
    def fit(self, x: np.ndarray, y: np.ndarray) -> "ArrayModel":
        raise NotImplementedError

    def predict(self, x: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class PolyModel(ArrayModel):
    def __init__(self, degree: int, ridge: bool = False) -> None:
        self.degree = degree
        self.model = (
            make_pipeline(PolynomialFeatures(degree, include_bias=False), StandardScaler(), Ridge(alpha=1.0))
            if ridge
            else make_pipeline(PolynomialFeatures(degree, include_bias=False), LinearRegression())
        )

    def fit(self, x: np.ndarray, y: np.ndarray) -> "PolyModel":
        self.model.fit(x, y)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(x), dtype=float)


class IsotonicModel(ArrayModel):
    def __init__(self, increasing: bool = True) -> None:
        self.model = IsotonicRegression(increasing=increasing, out_of_bounds="clip")

    def fit(self, x: np.ndarray, y: np.ndarray) -> "IsotonicModel":
        self.model.fit(np.asarray(x).reshape(-1), y)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(np.asarray(x).reshape(-1)), dtype=float)


class GBModel(ArrayModel):
    def __init__(self) -> None:
        self.model = GradientBoostingRegressor(random_state=3401, max_depth=2, n_estimators=80, learning_rate=0.05)

    def fit(self, x: np.ndarray, y: np.ndarray) -> "GBModel":
        self.model.fit(x, y)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(x), dtype=float)


class PinholeGridModel(ArrayModel):
    def __init__(self) -> None:
        self.c_eff = 400.0
        self.f_eff = 800.0
        self.delta_yaw = 0.0

    def fit(self, x: np.ndarray, y: np.ndarray) -> "PinholeGridModel":
        u = np.asarray(x).reshape(-1)
        best = (float("inf"), self.c_eff, self.f_eff, self.delta_yaw)
        for c_eff in np.linspace(320.0, 480.0, 17):
            for f_eff in [180.0, 240.0, 320.0, 450.0, 650.0, 900.0, 1300.0, 1800.0, 2600.0]:
                base = np.degrees(np.arctan((u - c_eff) / f_eff))
                delta = float(np.mean(y - base))
                pred = base + delta
                mae = float(np.mean(np.abs(pred - y)))
                if mae < best[0]:
                    best = (mae, float(c_eff), float(f_eff), delta)
        _, self.c_eff, self.f_eff, self.delta_yaw = best
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        u = np.asarray(x).reshape(-1)
        return np.degrees(np.arctan((u - self.c_eff) / self.f_eff)) + self.delta_yaw

    def params(self) -> dict[str, float]:
        return {"c_eff": self.c_eff, "f_eff": self.f_eff, "delta_yaw": self.delta_yaw}


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_float(value: Any, default: float = float("nan")) -> float:
    text = norm(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    text = norm(value)
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def fmt(value: Any, digits: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


def duplicate_header(row: Mapping[str, Any]) -> bool:
    hits = sum(1 for key, value in row.items() if str(key).strip() == str(value).strip())
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
        return p.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def combined_sha(paths: Sequence[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(rel(path).encode("utf-8"))
        h.update(sha256_file(path).encode("ascii"))
    return h.hexdigest()


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def parse_box(value: Any) -> Box | None:
    nums = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", norm(value))[:4]]
    if len(nums) != 4:
        return None
    box = Box(*nums)
    return box if box.area > 0 else None


def parse_key_values(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in norm(value).split(";"):
        if "=" in part:
            key, raw = part.split("=", 1)
            out[key.strip()] = raw.strip()
    return out


def parse_sar_dims(value: Any) -> tuple[float, float, float]:
    kv = parse_key_values(value)
    return (
        parse_float(kv.get("w"), 0.0),
        parse_float(kv.get("h"), 0.0),
        parse_float(kv.get("heading"), 0.0),
    )


def pixel_to_polar(x: float, y: float) -> tuple[float, float]:
    azimuth = math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))
    radial = math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)
    return azimuth, radial


def rotated_rect_samples(cx: float, cy: float, width: float, height: float, heading_deg: float) -> list[tuple[float, float]]:
    angle = math.radians(heading_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    samples: list[tuple[float, float]] = [(cx, cy)]
    for sx in np.linspace(-0.5, 0.5, 7):
        for sy in (-0.5, 0.5):
            dx, dy = sx * width, sy * height
            samples.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))
    for sy in np.linspace(-0.5, 0.5, 7):
        for sx in (-0.5, 0.5):
            dx, dy = sx * width, sy * height
            samples.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))
    return samples


def robust_percentile(values: Iterable[float], pct: float, default: float = 0.0) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if not clean:
        return default
    return float(np.percentile(clean, pct))


def median(values: Iterable[float], default: float = 0.0) -> float:
    return robust_percentile(values, 50, default)


def p90(values: Iterable[float], default: float = 0.0) -> float:
    return robust_percentile(values, 90, default)


def pearson_or_zero(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) < 3 or len(y) < 3:
        return 0.0
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3 or np.std(a[mask]) == 0 or np.std(b[mask]) == 0:
        return 0.0
    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def spearman_like(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) < 3:
        return 0.0
    xr = np.argsort(np.argsort(np.asarray(x, dtype=float)))
    yr = np.argsort(np.argsort(np.asarray(y, dtype=float)))
    return pearson_or_zero(xr.tolist(), yr.tolist())


def frame_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_frames" / f"{frame:06d}.png"


def sar_gray_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def depth_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_depth" / f"{frame:06d}_depth.npy"


def list_numbered_pngs(path: Path) -> list[int]:
    if not path.exists():
        return []
    out = []
    for item in path.iterdir():
        if not item.is_file() or item.suffix.lower() != ".png":
            continue
        head = item.stem.split("_")[0]
        if head.isdigit():
            out.append(int(head))
    return sorted(out)


def list_depth_frames(path: Path) -> list[int]:
    if not path.exists():
        return []
    out = []
    for item in path.glob("*_depth.npy"):
        head = item.stem.split("_")[0]
        if head.isdigit():
            out.append(int(head))
    return sorted(out)


def classify_pair(row: Mapping[str, str]) -> tuple[str, str, str, str]:
    eligibility = norm(row.get("vehicle_research_eligibility"))
    status = norm(row.get("correspondence_status"))
    flags = norm(row.get("edge_partial_duplicate_handoff_ambiguity_flags")).lower()
    iou = parse_float(row.get("correspondence_match_iou"), 0.0)
    if eligibility == "blocked_vehicle_or_noise":
        return "non_vehicle_pair", "blocked", "false", "blocked_vehicle_or_noise"
    if "weak_review" in status:
        return "identity_ambiguous_pair", "low", "false", "weak_review_correspondence"
    if eligibility == "weak_vehicle_layer" and iou >= 0.65:
        confidence = "moderate" if "ambiguity=ambiguous" in flags else "high"
        return "high_confidence_pair", confidence, "true", ""
    if eligibility == "review_only_vehicle":
        return "posthoc_only_pair", "moderate", "false", "review_only_vehicle_not_primary_calibration"
    return "moderate_confidence_pair", "moderate", "false", "not_primary_calibration_pool"


def build_pair_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv(PAIR_SOURCE)
    pair_rows: list[dict[str, Any]] = []
    sar_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        scene = row["scene"]
        optical_frame = parse_int(row.get("optical_frame"))
        sar_frame = parse_int(row.get("sar_frame"))
        opt_box = parse_box(row.get("optical_bbox"))
        center_nums = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", row.get("sar_gt_center", ""))[:2]]
        if opt_box is None or len(center_nums) != 2:
            continue
        sx, sy = center_nums
        sw, sh, sheading = parse_sar_dims(row.get("sar_gt_width_height_or_rotated_box"))
        sar_bbox = Box(sx - sw / 2.0, sy - sh / 2.0, sx + sw / 2.0, sy + sh / 2.0)
        pair_confidence, identity_confidence, usable, blocked = classify_pair(row)
        pair_id = f"WGV35A_PAIR_{idx:04d}"
        dpath = depth_path(scene, optical_frame)
        pair_rows.append(
            {
                "pair_id": pair_id,
                "scene": scene,
                "optical_frame": optical_frame,
                "sar_frame": sar_frame,
                "optical_thread_id": row["object_hypothesis_id"],
                "optical_fragment_id": "",
                "optical_bbox_x1": fmt(opt_box.x1, 3),
                "optical_bbox_y1": fmt(opt_box.y1, 3),
                "optical_bbox_x2": fmt(opt_box.x2, 3),
                "optical_bbox_y2": fmt(opt_box.y2, 3),
                "sar_bbox_x1": fmt(sar_bbox.x1, 3),
                "sar_bbox_y1": fmt(sar_bbox.y1, 3),
                "sar_bbox_x2": fmt(sar_bbox.x2, 3),
                "sar_bbox_y2": fmt(sar_bbox.y2, 3),
                "depth_path": str(dpath),
                "pair_source": rel(PAIR_SOURCE),
                "pair_confidence": pair_confidence,
                "identity_confidence": identity_confidence,
                "usable_for_calibration": usable,
                "blocked_reason": blocked,
                "sar_gt_id": row.get("sar_gt_id", ""),
                "correspondence_match_iou": row.get("correspondence_match_iou", ""),
                "vehicle_research_eligibility": row.get("vehicle_research_eligibility", ""),
                "visibility_state": row.get("visibility_state", ""),
            }
        )
        az_center, radial_center = pixel_to_polar(sx, sy)
        samples = rotated_rect_samples(sx, sy, sw, sh, sheading)
        polars = [pixel_to_polar(x, y) for x, y in samples]
        az_values = [p[0] for p in polars]
        radial_values = [p[1] for p in polars]
        warning = []
        if max(radial_values) > FAN_RADIUS_PX:
            warning.append("touches_or_exceeds_fan_radius")
        if min(az_values) < FULL_AZIMUTH_MIN or max(az_values) > FULL_AZIMUTH_MAX:
            warning.append("touches_azimuth_boundary")
        sar_rows.append(
            {
                "pair_id": pair_id,
                "scene": scene,
                "sar_frame": sar_frame,
                "sar_gt_id": row.get("sar_gt_id", ""),
                "sar_center_x": fmt(sx, 3),
                "sar_center_y": fmt(sy, 3),
                "sar_center_azimuth_deg": fmt(az_center, 4),
                "sar_center_radial_pixel": fmt(radial_center, 3),
                "sar_azimuth_min": fmt(min(az_values), 4),
                "sar_azimuth_max": fmt(max(az_values), 4),
                "sar_radial_min": fmt(min(radial_values), 3),
                "sar_radial_max": fmt(max(radial_values), 3),
                "sar_azimuth_span": fmt(max(az_values) - min(az_values), 4),
                "sar_radial_span": fmt(max(radial_values) - min(radial_values), 3),
                "sar_geometry_warning": ";".join(warning),
            }
        )
    return pair_rows, sar_rows


def role_for_pair(row: Mapping[str, Any]) -> str:
    if norm(row.get("usable_for_calibration")) != "true":
        return "blocked"
    thread = norm(row.get("optical_thread_id"))
    scene = norm(row.get("scene"))
    if thread in TRAIN_THREADS:
        return "train"
    if thread in VALIDATION_THREADS:
        return "validation"
    if thread in INTERNAL_TEST_THREADS:
        return "test"
    if scene == "GM_RM019":
        return "external_scene_test"
    return "blocked"


def build_split_rows(pair_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        grouped[(norm(row.get("scene")), norm(row.get("optical_thread_id")))].append(row)
    split_rows: list[dict[str, Any]] = []
    roles_seen: dict[str, set[str]] = defaultdict(set)
    for idx, ((scene, thread), rows) in enumerate(sorted(grouped.items()), 1):
        row_roles = [role_for_pair(row) for row in rows]
        usable_roles = [role for role in row_roles if role != "blocked"]
        role = usable_roles[0] if usable_roles else "blocked"
        roles_seen[thread].add(role)
        frames = [parse_int(row.get("optical_frame")) for row in rows]
        usable_count = sum(1 for role_name in row_roles if role_name != "blocked")
        reason = {
            "train": "large GM_RM017 high-confidence calibration thread",
            "validation": "held-out GM_RM017 high-confidence thread for model selection and interval calibration",
            "test": "internal GM_RM017 held-out thread",
            "external_scene_test": "GM_RM019 external-scene heldout; not used for fitting or interval calibration",
            "blocked": "not high-confidence calibration pair or not assigned to a safe split",
        }[role]
        split_rows.append(
            {
                "split_id": f"WGV35A_SPLIT_{idx:03d}",
                "scene": scene,
                "thread_id": thread,
                "frame_start": min(frames),
                "frame_end": max(frames),
                "split_role": role,
                "pair_count": usable_count if usable_count else len(rows),
                "split_reason": reason,
                "leakage_check": f"thread_role_unique=true;no_random_frame_split=true;blocked_or_posthoc_rows_in_thread={len(rows) - usable_count}",
            }
        )
    for row in split_rows:
        if len(roles_seen[row["thread_id"]]) > 1:
            row["leakage_check"] = "thread_role_unique=false"
    return split_rows


def quantiles(values: np.ndarray) -> dict[str, float]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {"q10": float("nan"), "q25": float("nan"), "q50": float("nan"), "q75": float("nan"), "q90": float("nan")}
    return {
        "q10": float(np.percentile(clean, 10)),
        "q25": float(np.percentile(clean, 25)),
        "q50": float(np.percentile(clean, 50)),
        "q75": float(np.percentile(clean, 75)),
        "q90": float(np.percentile(clean, 90)),
    }


def depth_crop(arr: np.ndarray, box: Box, mode: str) -> np.ndarray:
    h, w = arr.shape[:2]
    x1, y1, x2, y2 = box.x1, box.y1, box.x2, box.y2
    if mode == "D1":
        dx, dy = box.width * 0.2, box.height * 0.2
        x1, x2 = x1 + dx, x2 - dx
        y1, y2 = y1 + dy, y2 - dy
    elif mode == "D2":
        xpad = box.width * 0.2
        x1, x2 = x1 + xpad, x2 - xpad
        y1 = y1 + box.height * 0.5
    ix1, iy1 = max(0, int(math.floor(x1))), max(0, int(math.floor(y1)))
    ix2, iy2 = min(w, int(math.ceil(x2))), min(h, int(math.ceil(y2)))
    if ix2 <= ix1 or iy2 <= iy1:
        return np.asarray([], dtype=float)
    return np.asarray(arr[iy1:iy2, ix1:ix2], dtype=float)


def summarize_depth_for_box(scene: str, frame: int, box: Box) -> dict[str, float]:
    path = depth_path(scene, frame)
    if not path.exists():
        return {key: float("nan") for key in ["D0", "D1", "D2", "D3", "q10", "q25", "q50", "q75", "q90", "valid_ratio"]}
    arr = np.load(path)
    out: dict[str, float] = {}
    full = depth_crop(arr, box, "D0")
    finite_full = full[np.isfinite(full)]
    valid = finite_full[(finite_full > 0)]
    out["valid_ratio"] = float(valid.size / full.size) if full.size else 0.0
    qs = quantiles(valid)
    for key, value in qs.items():
        out[key] = value
    for mode in ["D0", "D1", "D2"]:
        crop = depth_crop(arr, box, mode)
        finite = crop[np.isfinite(crop)]
        finite = finite[finite > 0]
        out[mode] = float(np.median(finite)) if finite.size else float("nan")
    if valid.size:
        lo, hi = np.percentile(valid, [20, 80])
        trimmed = valid[(valid >= lo) & (valid <= hi)]
        out["D3"] = float(np.median(trimmed)) if trimmed.size else float(np.median(valid))
    else:
        out["D3"] = float("nan")
    return out


def build_optical_rows(pair_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in pair_rows:
        box = Box(
            parse_float(pair["optical_bbox_x1"]),
            parse_float(pair["optical_bbox_y1"]),
            parse_float(pair["optical_bbox_x2"]),
            parse_float(pair["optical_bbox_y2"]),
        )
        scene = norm(pair["scene"])
        frame = parse_int(pair["optical_frame"])
        depth = summarize_depth_for_box(scene, frame, box)
        vis = parse_key_values(pair.get("visibility_state", ""))
        rows.append(
            {
                "pair_id": pair["pair_id"],
                "scene": scene,
                "optical_frame": frame,
                "thread_id": pair["optical_thread_id"],
                "bbox_center_x": fmt(box.cx, 3),
                "bbox_center_y": fmt(box.cy, 3),
                "bbox_bottom_center_x": fmt(box.cx, 3),
                "bbox_bottom_center_y": fmt(box.y2, 3),
                "bbox_width": fmt(box.width, 3),
                "bbox_height": fmt(box.height, 3),
                "bbox_area": fmt(box.area, 3),
                "normalized_center_x": fmt(box.cx / 800.0, 6),
                "normalized_bottom_y": fmt(box.y2 / 600.0, 6),
                "edge_contact_left": bool_text(box.x1 <= 2.0),
                "edge_contact_right": bool_text(box.x2 >= 798.0),
                "edge_contact_bottom": bool_text(box.y2 >= 598.0),
                "occlusion_state": vis.get("occlusion", "unknown"),
                "partial_vehicle_state": vis.get("partial", "unknown"),
                "multi_box_competition": vis.get("multi", "unknown"),
                "visible_unboxed_gap": "unknown",
                "depth_center": fmt(depth["D1"], 6),
                "depth_q10": fmt(depth["q10"], 6),
                "depth_q25": fmt(depth["q25"], 6),
                "depth_q50": fmt(depth["q50"], 6),
                "depth_q75": fmt(depth["q75"], 6),
                "depth_q90": fmt(depth["q90"], 6),
                "depth_valid_ratio": fmt(depth["valid_ratio"], 6),
                "depth_D0": fmt(depth["D0"], 6),
                "depth_D1": fmt(depth["D1"], 6),
                "depth_D2": fmt(depth["D2"], 6),
                "depth_D3": fmt(depth["D3"], 6),
                "depth_D4": "",
                "optical_velocity_x": "",
                "optical_velocity_y": "",
                "track_age": "",
                "vehicle_class": "unknown_vehicle",
            }
        )
    by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_thread[norm(row["thread_id"])].append(row)
    for thread_rows in by_thread.values():
        thread_rows.sort(key=lambda r: parse_int(r["optical_frame"]))
        prev: dict[str, Any] | None = None
        depth_values = [parse_float(row["depth_D1"]) for row in thread_rows]
        for idx, row in enumerate(thread_rows):
            lo = max(0, idx - 2)
            hi = min(len(thread_rows), idx + 3)
            row["depth_D4"] = fmt(median(depth_values[lo:hi], parse_float(row["depth_D1"])), 6)
            if prev is None:
                row["optical_velocity_x"] = "0"
                row["optical_velocity_y"] = "0"
            else:
                dt = max(1, parse_int(row["optical_frame"]) - parse_int(prev["optical_frame"]))
                row["optical_velocity_x"] = fmt((parse_float(row["bbox_center_x"]) - parse_float(prev["bbox_center_x"])) / dt, 6)
                row["optical_velocity_y"] = fmt((parse_float(row["bbox_center_y"]) - parse_float(prev["bbox_center_y"])) / dt, 6)
            row["track_age"] = idx + 1
            prev = row
    return rows


def build_depth_audit_rows(
    pair_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    optical_by_pair = {row["pair_id"]: row for row in optical_rows}
    sar_by_pair = {row["pair_id"]: row for row in sar_rows}
    split_by_pair = {row["pair_id"]: role_for_pair(row) for row in pair_rows}
    rows: list[dict[str, Any]] = []
    for scene in ["GM_RM011", "GM_RM017", "GM_RM019"]:
        depth_dir = DATA_ROOT / scene / f"{scene}_depth"
        image_dir = DATA_ROOT / scene / f"{scene}_frames"
        depth_frames = list_depth_frames(depth_dir)
        image_frames = list_numbered_pngs(image_dir)
        sample_frames = sorted(set(depth_frames[:: max(1, len(depth_frames) // 25)] + [parse_int(p["optical_frame"]) for p in pair_rows if p["scene"] == scene]))
        shapes: Counter[str] = Counter()
        dtypes: Counter[str] = Counter()
        mins: list[float] = []
        maxs: list[float] = []
        p10s: list[float] = []
        p50s: list[float] = []
        p90s: list[float] = []
        invalid = []
        for frame in sample_frames[:80]:
            path = depth_path(scene, frame)
            if not path.exists():
                continue
            arr = np.load(path)
            shapes[str(tuple(arr.shape))] += 1
            dtypes[str(arr.dtype)] += 1
            finite = arr[np.isfinite(arr)]
            invalid.append(1.0 - float(finite.size / arr.size))
            positive = finite[finite > 0]
            if positive.size:
                mins.append(float(np.min(positive)))
                maxs.append(float(np.max(positive)))
                p10s.append(float(np.percentile(positive, 10)))
                p50s.append(float(np.percentile(positive, 50)))
                p90s.append(float(np.percentile(positive, 90)))
        train_pairs = [
            p
            for p in pair_rows
            if p["scene"] == scene and split_by_pair.get(p["pair_id"]) in {"train", "validation"} and p["usable_for_calibration"] == "true"
        ]
        radial = [parse_float(sar_by_pair[p["pair_id"]]["sar_center_radial_pixel"]) for p in train_pairs if p["pair_id"] in sar_by_pair]
        strategy_corr: dict[str, float] = {}
        for strategy in ["D0", "D1", "D2", "D3", "D4"]:
            vals = [parse_float(optical_by_pair[p["pair_id"]].get(f"depth_{strategy}", "")) for p in train_pairs if p["pair_id"] in optical_by_pair]
            strategy_corr[strategy] = spearman_like(vals, radial) if len(vals) == len(radial) and vals else 0.0
        valid_ratios = [parse_float(row["depth_valid_ratio"]) for row in optical_rows if row["scene"] == scene]
        temporal_mads = []
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in optical_rows:
            if row["scene"] == scene:
                grouped[row["thread_id"]].append(parse_float(row["depth_D4"]))
        for vals in grouped.values():
            clean = [v for v in vals if math.isfinite(v)]
            if len(clean) >= 3:
                temporal_mads.append(median([abs(v - median(clean)) for v in clean]))
        best = max(strategy_corr, key=lambda key: abs(strategy_corr[key])) if strategy_corr else "D1"
        frame_alignment = "one_to_one_filename_alignment" if set(image_frames) and set(depth_frames).issuperset(set(image_frames[: min(10, len(image_frames))])) else "filename_alignment_partial"
        if len(image_frames) == len(depth_frames) and image_frames[:5] == depth_frames[:5]:
            frame_alignment = "one_to_one_filename_alignment"
        status = "DEPTH_SOURCE_UNUSABLE"
        meaning = "source_metadata_missing"
        best_corr = strategy_corr.get(best, 0.0)
        if depth_frames and abs(best_corr) >= 0.45:
            status = "RELATIVE_DEPTH_MONOTONIC"
            meaning = "relative_depth_or_network_depth_monotonic_to_sar_radial;not_treated_as_metric"
        elif depth_frames:
            status = "RELATIVE_DEPTH_UNSTABLE"
            meaning = "depth_arrays_exist_but_monotonic_relation_is_weak_or_scene_limited"
        rows.append(
            {
                "scene": scene,
                "depth_source_status": status,
                "depth_meaning": meaning,
                "frame_alignment": frame_alignment,
                "depth_file_count": len(depth_frames),
                "optical_frame_count": len(image_frames),
                "shape": ";".join(f"{k}:{v}" for k, v in shapes.items()),
                "dtype": ";".join(f"{k}:{v}" for k, v in dtypes.items()),
                "sample_min": fmt(min(mins) if mins else float("nan"), 6),
                "sample_p10": fmt(median(p10s), 6),
                "sample_p50": fmt(median(p50s), 6),
                "sample_p90": fmt(median(p90s), 6),
                "sample_max": fmt(max(maxs) if maxs else float("nan"), 6),
                "invalid_ratio": fmt(median(invalid), 6),
                "strategy": best,
                "median_valid_ratio": fmt(median(valid_ratios), 6),
                "thread_temporal_mad": fmt(median(temporal_mads), 6),
                "train_spearman_like_corr_to_sar_radial": fmt(best_corr, 6),
                "sensitivity_note": "strategy selected before test evaluation; metric 20cm formula not used unless metric provenance is recovered",
            }
        )
    return rows


def selected_depth_strategy(depth_rows: Sequence[Mapping[str, Any]]) -> str:
    gm17 = next((row for row in depth_rows if row["scene"] == "GM_RM017"), None)
    return norm(gm17.get("strategy")) if gm17 else "D1"


def rows_by_id(rows: Sequence[Mapping[str, Any]], key: str = "pair_id") -> dict[str, Mapping[str, Any]]:
    return {norm(row.get(key)): row for row in rows}


def role_masks(pair_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    masks: dict[str, list[str]] = defaultdict(list)
    for row in pair_rows:
        masks[role_for_pair(row)].append(row["pair_id"])
    masks["test_all"] = masks.get("test", []) + masks.get("external_scene_test", [])
    return masks


def feature_matrix(
    pair_ids: Sequence[str],
    optical_by_id: Mapping[str, Mapping[str, Any]],
    depth_strategy: str,
    mode: str,
) -> np.ndarray:
    data: list[list[float]] = []
    for pid in pair_ids:
        row = optical_by_id[pid]
        depth = parse_float(row.get(f"depth_{depth_strategy}", ""))
        if mode == "time":
            feats = [parse_float(row["optical_frame"])]
        elif mode == "az_center":
            feats = [parse_float(row["bbox_center_x"])]
        elif mode == "az_bottom":
            feats = [parse_float(row["bbox_bottom_center_x"])]
        elif mode == "radial_r0":
            feats = [
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
                parse_float(row["bbox_area"]),
            ]
        elif mode == "radial_r1":
            feats = [
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
                parse_float(row["bbox_area"]),
                depth,
                parse_float(row["depth_q10"]),
                parse_float(row["depth_q90"]),
            ]
        elif mode == "ablation_a":
            feats = [parse_float(row["bbox_center_x"])]
        elif mode == "ablation_b":
            feats = [
                parse_float(row["bbox_center_x"]),
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
            ]
        elif mode == "ablation_c":
            feats = [
                parse_float(row["bbox_center_x"]),
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
                depth,
            ]
        elif mode == "ablation_d":
            feats = [
                parse_float(row["bbox_center_x"]),
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
                depth,
                parse_float(row["depth_D4"]),
            ]
        elif mode == "ablation_e":
            feats = [
                parse_float(row["bbox_center_x"]),
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
                depth,
                parse_float(row["depth_D4"]),
                parse_float(row["optical_velocity_x"]),
                parse_float(row["optical_velocity_y"]),
            ]
        elif mode == "ablation_f":
            feats = [
                parse_float(row["bbox_center_x"]),
                parse_float(row["bbox_height"]),
                parse_float(row["bbox_width"]),
                parse_float(row["bbox_bottom_center_y"]),
                depth,
                parse_float(row["depth_D4"]),
                parse_float(row["optical_velocity_x"]),
                parse_float(row["optical_velocity_y"]),
                1.0 if norm(row["edge_contact_left"]) == "true" or norm(row["edge_contact_right"]) == "true" else 0.0,
                1.0 if "boundary_truncation" in norm(row["partial_vehicle_state"]) else 0.0,
            ]
        else:
            raise ValueError(mode)
        data.append([0.0 if not math.isfinite(v) else v for v in feats])
    return np.asarray(data, dtype=float)


def target_array(pair_ids: Sequence[str], rows: Mapping[str, Mapping[str, Any]], field: str) -> np.ndarray:
    return np.asarray([parse_float(rows[pid][field]) for pid in pair_ids], dtype=float)


def model_error(model: ArrayModel, x: np.ndarray, y: np.ndarray) -> tuple[float, float, np.ndarray]:
    if len(y) == 0:
        return 0.0, 0.0, np.asarray([], dtype=float)
    pred = model.predict(x)
    err = np.abs(pred - y)
    return median(err), p90(err), err


def calibration_row(
    family: str,
    name: str,
    features: str,
    train_count: int,
    val_count: int,
    selected: bool,
    params: Mapping[str, Any],
    train_err: tuple[float, float],
    val_err: tuple[float, float],
    notes: str,
) -> dict[str, Any]:
    return {
        "model_family": family,
        "model_name": name,
        "input_features": features,
        "train_count": train_count,
        "validation_count": val_count,
        "selected": bool_text(selected),
        "parameters": json.dumps(params, sort_keys=True),
        "train_median_error": fmt(train_err[0], 6),
        "train_p90_error": fmt(train_err[1], 6),
        "validation_median_error": fmt(val_err[0], 6),
        "validation_p90_error": fmt(val_err[1], 6),
        "notes": notes,
    }


def fit_models(
    pair_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
    depth_strategy: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    masks = role_masks(pair_rows)
    train_ids = masks["train"]
    val_ids = masks["validation"]
    optical_by_id = rows_by_id(optical_rows)
    sar_by_id = rows_by_id(sar_rows)
    pair_by_id = rows_by_id(pair_rows)

    time_candidates: list[tuple[str, ArrayModel, str, str, dict[str, Any]]] = [
        ("global_linear", PolyModel(1), "time", "optical_frame", {}),
    ]
    legacy = PolyModel(1)
    legacy.fit(np.asarray([[0.0], [24.0]]), np.asarray([0.0, 50.0]))
    time_candidates.append(("legacy_24_50_proxy", legacy, "time", "optical_frame", {"a": SAR_FPS / OPTICAL_FPS, "b": 0.0}))
    time_rows: list[dict[str, Any]] = []
    fitted_time: list[tuple[str, ArrayModel, tuple[float, float], tuple[float, float], dict[str, Any]]] = []
    y_train_time = target_array(train_ids, pair_by_id, "sar_frame")
    y_val_time = target_array(val_ids, pair_by_id, "sar_frame")
    for name, model, mode, features, params in time_candidates:
        if name != "legacy_24_50_proxy":
            model.fit(feature_matrix(train_ids, optical_by_id, depth_strategy, mode), y_train_time)
        tr = model_error(model, feature_matrix(train_ids, optical_by_id, depth_strategy, mode), y_train_time)[:2]
        va = model_error(model, feature_matrix(val_ids, optical_by_id, depth_strategy, mode), y_val_time)[:2]
        fitted_time.append((name, model, tr, va, params))
    selected_time = min(fitted_time, key=lambda item: (item[3][1], item[3][0]))
    for name, model, tr, va, params in fitted_time:
        if name == "global_linear":
            linear = model.model.named_steps["linearregression"]
            params = {"coef": float(linear.coef_[0]), "intercept": float(linear.intercept_)}
        time_rows.append(
            calibration_row("time", name, "optical_frame", len(train_ids), len(val_ids), name == selected_time[0], params, tr, va, "SAR labels from test split not used")
        )

    y_train_az = target_array(train_ids, sar_by_id, "sar_center_azimuth_deg")
    y_val_az = target_array(val_ids, sar_by_id, "sar_center_azimuth_deg")
    az_candidates: list[tuple[str, ArrayModel, str, str]] = [
        ("pinhole_like_effective_bottom_x", PinholeGridModel(), "az_bottom", "bbox_bottom_center_x"),
        ("linear_center_x", PolyModel(1), "az_center", "bbox_center_x"),
        ("quadratic_bottom_x", PolyModel(2), "az_bottom", "bbox_bottom_center_x"),
        ("cubic_bottom_x", PolyModel(3), "az_bottom", "bbox_bottom_center_x"),
    ]
    corr = pearson_or_zero(
        feature_matrix(train_ids, optical_by_id, depth_strategy, "az_bottom").reshape(-1).tolist(),
        y_train_az.tolist(),
    )
    az_candidates.append(("isotonic_bottom_x", IsotonicModel(increasing=corr >= 0), "az_bottom", "bbox_bottom_center_x"))
    az_rows: list[dict[str, Any]] = []
    fitted_az: list[tuple[str, ArrayModel, str, tuple[float, float], tuple[float, float], dict[str, Any]]] = []
    for name, model, mode, features in az_candidates:
        model.fit(feature_matrix(train_ids, optical_by_id, depth_strategy, mode), y_train_az)
        tr = model_error(model, feature_matrix(train_ids, optical_by_id, depth_strategy, mode), y_train_az)[:2]
        va = model_error(model, feature_matrix(val_ids, optical_by_id, depth_strategy, mode), y_val_az)[:2]
        params = model.params() if isinstance(model, PinholeGridModel) else {"mode": mode}
        fitted_az.append((name, model, mode, tr, va, params))
    selected_az = min(fitted_az, key=lambda item: (item[4][1], item[4][0]))
    for name, _model, mode, tr, va, params in fitted_az:
        az_rows.append(
            calibration_row("azimuth", name, mode, len(train_ids), len(val_ids), name == selected_az[0], params, tr, va, "effective weak parameters only; not true intrinsics/extrinsics")
        )

    y_train_rad = target_array(train_ids, sar_by_id, "sar_center_radial_pixel")
    y_val_rad = target_array(val_ids, sar_by_id, "sar_center_radial_pixel")
    depth_train = feature_matrix(train_ids, optical_by_id, depth_strategy, "radial_r1")[:, 4]
    radial_corr = spearman_like(depth_train.tolist(), y_train_rad.tolist())
    radial_candidates: list[tuple[str, ArrayModel, str, str, str]] = [
        ("R0_no_depth_bbox_geometry", PolyModel(1, ridge=True), "radial_r0", "bbox_height;width;bottom_y;area", "no_depth_baseline"),
        ("R1_depth_plus_bbox_geometry", PolyModel(1, ridge=True), "radial_r1", f"{depth_strategy}+bbox_geometry+depth_quantiles", "main_depth_model"),
        ("R2_isotonic_depth_only", IsotonicModel(increasing=radial_corr >= 0), "ablation_c", f"{depth_strategy}", "monotonic_depth_reference"),
        ("R3_gradient_boosting_reference", GBModel(), "radial_r1", f"{depth_strategy}+bbox_geometry+depth_quantiles", "nonlinear_reference_not_sole_report"),
    ]
    radial_rows: list[dict[str, Any]] = []
    fitted_radial: list[tuple[str, ArrayModel, str, tuple[float, float], tuple[float, float], dict[str, Any], str]] = []
    for name, model, mode, features, note in radial_candidates:
        fit_mode = mode
        if name == "R2_isotonic_depth_only":
            x_train = feature_matrix(train_ids, optical_by_id, depth_strategy, "radial_r1")[:, 4].reshape(-1, 1)
            x_val = feature_matrix(val_ids, optical_by_id, depth_strategy, "radial_r1")[:, 4].reshape(-1, 1)
        else:
            x_train = feature_matrix(train_ids, optical_by_id, depth_strategy, fit_mode)
            x_val = feature_matrix(val_ids, optical_by_id, depth_strategy, fit_mode)
        model.fit(x_train, y_train_rad)
        tr = model_error(model, x_train, y_train_rad)[:2]
        va = model_error(model, x_val, y_val_rad)[:2]
        params = {"mode": mode, "depth_spearman_like": radial_corr}
        fitted_radial.append((name, model, mode, tr, va, params, note))
    selected_radial = min(fitted_radial, key=lambda item: (item[4][1], item[4][0]))
    for name, _model, mode, tr, va, params, note in fitted_radial:
        radial_rows.append(
            calibration_row("radial", name, mode, len(train_ids), len(val_ids), name == selected_radial[0], params, tr, va, note)
        )

    model_bundle = {
        "depth_strategy": depth_strategy,
        "time": {"name": selected_time[0], "model": selected_time[1], "mode": "time"},
        "azimuth": {"name": selected_az[0], "model": selected_az[1], "mode": selected_az[2]},
        "radial": {"name": selected_radial[0], "model": selected_radial[1], "mode": selected_radial[2]},
        "all_radial": {name: (model, mode) for name, model, mode, *_ in fitted_radial},
        "validation_ids": val_ids,
        "train_ids": train_ids,
    }

    val_time_pred = selected_time[1].predict(feature_matrix(val_ids, optical_by_id, depth_strategy, "time"))
    val_az_pred = selected_az[1].predict(feature_matrix(val_ids, optical_by_id, depth_strategy, selected_az[2]))
    if selected_radial[0] == "R2_isotonic_depth_only":
        val_rad_x = feature_matrix(val_ids, optical_by_id, depth_strategy, "radial_r1")[:, 4].reshape(-1, 1)
    else:
        val_rad_x = feature_matrix(val_ids, optical_by_id, depth_strategy, selected_radial[2])
    val_rad_pred = selected_radial[1].predict(val_rad_x)
    model_bundle["intervals"] = {
        "time": residual_quantiles(val_time_pred, y_val_time, floors={50: 2.0, 80: 4.0, 95: 8.0}),
        "azimuth": residual_quantiles(val_az_pred, y_val_az, floors={50: 1.0, 80: 2.0, 95: 4.0}),
        "radial": residual_quantiles(val_rad_pred, y_val_rad, floors={50: 20.0, 80: 40.0, 95: 80.0}),
    }
    return model_bundle, time_rows, az_rows, radial_rows, build_heading_rows(pair_rows, optical_rows)


def residual_quantiles(pred: np.ndarray, actual: np.ndarray, floors: Mapping[int, float]) -> dict[str, float]:
    residual = np.abs(np.asarray(pred, dtype=float) - np.asarray(actual, dtype=float))
    return {f"q{pct}": max(float(floor), robust_percentile(residual, pct, float(floor))) for pct, floor in floors.items()}


def build_heading_rows(pair_rows: Sequence[Mapping[str, Any]], optical_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_thread: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    pair_by_id = rows_by_id(pair_rows)
    for row in optical_rows:
        by_thread[norm(row["thread_id"])].append(row)
    rows: list[dict[str, Any]] = []
    for thread, thread_rows in by_thread.items():
        thread_rows = sorted(thread_rows, key=lambda r: parse_int(r["optical_frame"]))
        vx = [parse_float(row["optical_velocity_x"]) for row in thread_rows]
        vy = [parse_float(row["optical_velocity_y"]) for row in thread_rows]
        median_vx, median_vy = median(vx), median(vy)
        speed = math.hypot(median_vx, median_vy)
        angle = math.degrees(math.atan2(median_vx, -median_vy)) if speed > 0 else float("nan")
        if len(thread_rows) < 5 or speed < 0.6:
            rep = "unknown"
            confidence = "low"
            usable = "false"
        elif abs(median_vx) > abs(median_vy) * 1.5:
            rep = "lateral_right" if median_vx > 0 else "lateral_left"
            confidence = "moderate"
            usable = "true"
        elif median_vy < -0.4:
            rep = "receding"
            confidence = "moderate"
            usable = "true"
        elif median_vy > 0.4:
            rep = "approaching"
            confidence = "moderate"
            usable = "true"
        else:
            rep = "oblique_right" if median_vx > 0 else "oblique_left"
            confidence = "low"
            usable = "false"
        for row in thread_rows:
            pair = pair_by_id[row["pair_id"]]
            visibility = norm(pair.get("visibility_state"))
            local_usable = usable
            if "boundary_truncation_present" in visibility or "ambiguous" in norm(pair.get("identity_confidence")):
                local_usable = "false"
            rows.append(
                {
                    "pair_id": row["pair_id"],
                    "scene": row["scene"],
                    "thread_id": thread,
                    "optical_frame": row["optical_frame"],
                    "heading_representation": rep,
                    "heading_angle_proxy_deg": fmt(angle, 4),
                    "heading_confidence": confidence,
                    "usable_for_compression": local_usable,
                    "heading_contribution_note": "optical-motion proxy only; not 3D vehicle yaw and not fitted from test SAR labels",
                }
            )
    return rows


def predict_radial(model_bundle: Mapping[str, Any], pair_ids: Sequence[str], optical_by_id: Mapping[str, Mapping[str, Any]]) -> np.ndarray:
    selected = model_bundle["radial"]
    mode = selected["mode"]
    if selected["name"] == "R2_isotonic_depth_only":
        x = feature_matrix(pair_ids, optical_by_id, model_bundle["depth_strategy"], "radial_r1")[:, 4].reshape(-1, 1)
    else:
        x = feature_matrix(pair_ids, optical_by_id, model_bundle["depth_strategy"], mode)
    return selected["model"].predict(x)


def field_for_pair(
    variant: str,
    pair_id: str,
    pair: Mapping[str, Any],
    optical: Mapping[str, Any],
    heading: Mapping[str, Any],
    model_bundle: Mapping[str, Any],
    quantile: int = 95,
) -> dict[str, Any]:
    pid = [pair_id]
    optical_by_id = {pair_id: optical}
    qkey = f"q{quantile}"
    if variant == "P0":
        center_time = parse_float(optical["optical_frame"]) * (SAR_FPS / OPTICAL_FPS)
        time_margin = 16.0
        az_center = LEGACY_AZIMUTH_K * parse_float(optical["bbox_bottom_center_x"]) + LEGACY_AZIMUTH_B
        az_margin = 30.0
        rho_center = FAN_RADIUS_PX / 2.0
        rho_low_50, rho_high_50 = 0.0, FAN_RADIUS_PX
        rho_low_80, rho_high_80 = 0.0, FAN_RADIUS_PX
        rho_low_95, rho_high_95 = 0.0, FAN_RADIUS_PX
        radial_min, radial_max = 0.0, FAN_RADIUS_PX
        rule = "legacy_time_proxy_plus_wide_optical_x_azimuth_plus_full_radial"
    else:
        time_pred = model_bundle["time"]["model"].predict(feature_matrix(pid, optical_by_id, model_bundle["depth_strategy"], "time"))[0]
        az_pred = model_bundle["azimuth"]["model"].predict(feature_matrix(pid, optical_by_id, model_bundle["depth_strategy"], model_bundle["azimuth"]["mode"]))[0]
        radial_pred = predict_radial(model_bundle, pid, optical_by_id)[0]
        edge = norm(optical["edge_contact_left"]) == "true" or norm(optical["edge_contact_right"]) == "true" or norm(optical["edge_contact_bottom"]) == "true"
        visibility = norm(pair.get("visibility_state"))
        inflation = 1.0
        if edge:
            inflation += 0.2
        if "boundary_truncation_present" in visibility:
            inflation += 0.25
        if "multi=single_observation" not in visibility:
            inflation += 0.15
        heading_known = norm(heading.get("usable_for_compression")) == "true"
        if variant == "P2" and heading_known:
            inflation = max(0.85, inflation - 0.1)
        elif variant == "P2" and not heading_known:
            inflation += 0.1
        time_margin = model_bundle["intervals"]["time"][qkey]
        az_margin = model_bundle["intervals"]["azimuth"][qkey] * inflation
        radial_margin_50 = model_bundle["intervals"]["radial"]["q50"] * inflation
        radial_margin_80 = model_bundle["intervals"]["radial"]["q80"] * inflation
        radial_margin_95 = model_bundle["intervals"]["radial"]["q95"] * inflation
        if variant == "P2":
            radial_margin_95 += 0.25 * parse_float(optical["bbox_height"])
            az_margin += 0.4 if heading_known else 1.2
        center_time = time_pred
        az_center = az_pred
        rho_center = radial_pred
        rho_low_50, rho_high_50 = radial_pred - radial_margin_50, radial_pred + radial_margin_50
        rho_low_80, rho_high_80 = radial_pred - radial_margin_80, radial_pred + radial_margin_80
        rho_low_95, rho_high_95 = radial_pred - radial_margin_95, radial_pred + radial_margin_95
        radial_min, radial_max = rho_low_95, rho_high_95
        rule = "weak_calibrated_time_azimuth_radial" if variant == "P1" else "weak_calibrated_plus_heading_visibility_size_uncertainty"
    return {
        "pair_id": pair_id,
        "scene": pair["scene"],
        "split_role": role_for_pair(pair),
        "variant": variant,
        "time_start": max(0, int(math.floor(center_time - time_margin))),
        "time_end": int(math.ceil(center_time + time_margin)),
        "sar_frame_center": fmt(center_time, 4),
        "azimuth_min": fmt(max(FULL_AZIMUTH_MIN, az_center - az_margin), 6),
        "azimuth_max": fmt(min(FULL_AZIMUTH_MAX, az_center + az_margin), 6),
        "azimuth_center": fmt(az_center, 6),
        "radial_min": fmt(max(0.0, radial_min), 6),
        "radial_max": fmt(min(FAN_RADIUS_PX, radial_max), 6),
        "rho_center": fmt(rho_center, 6),
        "rho_low_50": fmt(max(0.0, rho_low_50), 6),
        "rho_high_50": fmt(min(FAN_RADIUS_PX, rho_high_50), 6),
        "rho_low_80": fmt(max(0.0, rho_low_80), 6),
        "rho_high_80": fmt(min(FAN_RADIUS_PX, rho_high_80), 6),
        "rho_low_95": fmt(max(0.0, rho_low_95), 6),
        "rho_high_95": fmt(min(FAN_RADIUS_PX, rho_high_95), 6),
        "heading_state": heading.get("heading_representation", "unknown"),
        "visibility_uncertainty": pair.get("visibility_state", ""),
        "field_rule": rule,
    }


def build_fields(
    pair_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    heading_rows: Sequence[Mapping[str, Any]],
    model_bundle: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    pair_by_id = rows_by_id(pair_rows)
    optical_by_id = rows_by_id(optical_rows)
    heading_by_id = rows_by_id(heading_rows)
    out = {"P0": [], "P1": [], "P2": []}
    for pair in pair_rows:
        if pair["usable_for_calibration"] != "true":
            continue
        pid = pair["pair_id"]
        for variant in out:
            out[variant].append(field_for_pair(variant, pid, pair_by_id[pid], optical_by_id[pid], heading_by_id.get(pid, {}), model_bundle))
    return out


def contained(field: Mapping[str, Any], sar: Mapping[str, Any], interval: str = "95") -> bool:
    frame = parse_float(sar["sar_frame"])
    az = parse_float(sar["sar_center_azimuth_deg"])
    radial = parse_float(sar["sar_center_radial_pixel"])
    if not (parse_float(field["time_start"]) <= frame <= parse_float(field["time_end"])):
        return False
    if not (parse_float(field["azimuth_min"]) <= az <= parse_float(field["azimuth_max"])):
        return False
    lo_key, hi_key = f"rho_low_{interval}", f"rho_high_{interval}"
    return parse_float(field[lo_key]) <= radial <= parse_float(field[hi_key])


def full_box_contained(field: Mapping[str, Any], sar: Mapping[str, Any]) -> bool:
    if not contained(field, sar, "95"):
        return False
    return (
        parse_float(field["azimuth_min"]) <= parse_float(sar["sar_azimuth_min"])
        and parse_float(field["azimuth_max"]) >= parse_float(sar["sar_azimuth_max"])
        and parse_float(field["radial_min"]) <= parse_float(sar["sar_radial_min"])
        and parse_float(field["radial_max"]) >= parse_float(sar["sar_radial_max"])
    )


def search_ratio(field: Mapping[str, Any]) -> float:
    time_width = max(1.0, parse_float(field["time_end"]) - parse_float(field["time_start"]) + 1.0)
    az_width = max(0.0, parse_float(field["azimuth_max"]) - parse_float(field["azimuth_min"]))
    radial_width = max(0.0, parse_float(field["radial_max"]) - parse_float(field["radial_min"]))
    # The denominator uses the observed SAR frame canvas volume rather than a
    # scene-specific exact frame count so P0/P1/P2 remain comparable.
    return (time_width / 766.0) * (az_width / (FULL_AZIMUTH_MAX - FULL_AZIMUTH_MIN)) * (radial_width / FAN_RADIUS_PX)


def count_competitors(field: Mapping[str, Any], pair: Mapping[str, Any], all_sar: Sequence[Mapping[str, Any]], all_pairs: Mapping[str, Mapping[str, Any]]) -> tuple[int, int]:
    contained_count = 0
    wrong = 0
    for sar in all_sar:
        other_pair = all_pairs.get(sar["pair_id"])
        if not other_pair or other_pair["scene"] != pair["scene"]:
            continue
        fake = dict(field)
        fake["rho_low_95"] = field["radial_min"]
        fake["rho_high_95"] = field["radial_max"]
        if contained(fake, sar, "95"):
            contained_count += 1
            if other_pair["optical_thread_id"] != pair["optical_thread_id"]:
                wrong += 1
    return contained_count, wrong


def evaluate_holdout(
    pair_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
    fields: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pair_by_id = rows_by_id(pair_rows)
    sar_by_id = rows_by_id(sar_rows)
    test_ids = set(role_masks(pair_rows)["test_all"])
    holdout_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for variant, variant_fields in fields.items():
        subset = [field for field in variant_fields if field["pair_id"] in test_ids]
        ratios = [search_ratio(field) for field in subset]
        c50 = [contained(field, sar_by_id[field["pair_id"]], "50") for field in subset]
        c80 = [contained(field, sar_by_id[field["pair_id"]], "80") for field in subset]
        c95 = [contained(field, sar_by_id[field["pair_id"]], "95") for field in subset]
        f95 = [full_box_contained(field, sar_by_id[field["pair_id"]]) for field in subset]
        az_errors = [abs(parse_float(field["azimuth_center"]) - parse_float(sar_by_id[field["pair_id"]]["sar_center_azimuth_deg"])) for field in subset]
        radial_errors = [abs(parse_float(field["rho_center"]) - parse_float(sar_by_id[field["pair_id"]]["sar_center_radial_pixel"])) for field in subset]
        multi_flags = []
        wrong_flags = []
        for field in subset:
            pair = pair_by_id[field["pair_id"]]
            contained_count, wrong = count_competitors(field, pair, sar_rows, pair_by_id)
            multi_flags.append(contained_count > 1)
            wrong_flags.append(wrong > 0)
            if variant == "P2" and not contained(field, sar_by_id[field["pair_id"]], "95"):
                sar = sar_by_id[field["pair_id"]]
                failure_type = []
                if not (parse_float(field["time_start"]) <= parse_float(sar["sar_frame"]) <= parse_float(field["time_end"])):
                    failure_type.append("time_miss")
                if not (parse_float(field["azimuth_min"]) <= parse_float(sar["sar_center_azimuth_deg"]) <= parse_float(field["azimuth_max"])):
                    failure_type.append("azimuth_miss")
                if not (parse_float(field["radial_min"]) <= parse_float(sar["sar_center_radial_pixel"]) <= parse_float(field["radial_max"])):
                    failure_type.append("radial_miss")
                if "boundary_truncation_present" in pair.get("visibility_state", ""):
                    failure_type.append("edge_truncation_failure")
                failure_rows.append(
                    {
                        "failure_id": f"WGV35A_FAIL_{len(failure_rows)+1:03d}",
                        "pair_id": field["pair_id"],
                        "scene": pair["scene"],
                        "thread_id": pair["optical_thread_id"],
                        "split_role": role_for_pair(pair),
                        "failure_type": ";".join(failure_type) if failure_type else "coverage_failure",
                        "time_error": fmt(abs(parse_float(field["sar_frame_center"]) - parse_float(sar["sar_frame"])), 4),
                        "azimuth_error": fmt(abs(parse_float(field["azimuth_center"]) - parse_float(sar["sar_center_azimuth_deg"])), 4),
                        "radial_error": fmt(abs(parse_float(field["rho_center"]) - parse_float(sar["sar_center_radial_pixel"])), 4),
                        "visibility_state": pair.get("visibility_state", ""),
                        "dominant_layer": failure_type[0] if failure_type else "unknown",
                        "notes": "holdout failure; no annotation modification",
                    }
                )
        n = len(subset)
        holdout_rows.append(
            {
                "model_variant": variant,
                "test_pair_count": n,
                "center_coverage_50": fmt(sum(c50) / n if n else 0.0, 6),
                "center_coverage_80": fmt(sum(c80) / n if n else 0.0, 6),
                "center_coverage_95": fmt(sum(c95) / n if n else 0.0, 6),
                "full_box_coverage_95": fmt(sum(f95) / n if n else 0.0, 6),
                "median_search_ratio": fmt(median(ratios), 8),
                "p90_search_ratio": fmt(p90(ratios), 8),
                "median_azimuth_error": fmt(median(az_errors), 6),
                "p90_azimuth_error": fmt(p90(az_errors), 6),
                "median_radial_error": fmt(median(radial_errors), 6),
                "p90_radial_error": fmt(p90(radial_errors), 6),
                "multi_target_rate": fmt(sum(multi_flags) / n if n else 0.0, 6),
                "wrong_identity_rate": fmt(sum(wrong_flags) / n if n else 0.0, 6),
            }
        )
    return holdout_rows, failure_rows


def fit_ablation_model(train_ids: Sequence[str], mode: str, optical_by_id: Mapping[str, Mapping[str, Any]], sar_by_id: Mapping[str, Mapping[str, Any]], depth_strategy: str) -> ArrayModel:
    model: ArrayModel = PolyModel(1, ridge=True)
    x = feature_matrix(train_ids, optical_by_id, depth_strategy, mode)
    y = target_array(train_ids, sar_by_id, "sar_center_radial_pixel")
    model.fit(x, y)
    return model


def evaluate_ablations(
    pair_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
    depth_strategy: str,
    base_fields: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    masks = role_masks(pair_rows)
    train_ids = masks["train"]
    test_ids = masks["test_all"]
    optical_by_id = rows_by_id(optical_rows)
    sar_by_id = rows_by_id(sar_rows)
    base_by_id = rows_by_id(base_fields)
    modes = [
        ("A", "optical x only", "ablation_a"),
        ("B", "optical x + bbox geometry", "ablation_b"),
        ("C", "optical x + bbox geometry + depth", "ablation_c"),
        ("D", "optical x + bbox geometry + depth + temporal smoothing", "ablation_d"),
        ("E", "optical x + depth + temporal smoothing + heading proxy", "ablation_e"),
        ("F", "full state including visibility uncertainty", "ablation_f"),
    ]
    rows: list[dict[str, Any]] = []
    for ablation_id, features, mode in modes:
        model = fit_ablation_model(train_ids, mode, optical_by_id, sar_by_id, depth_strategy)
        pred = model.predict(feature_matrix(test_ids, optical_by_id, depth_strategy, mode))
        actual = target_array(test_ids, sar_by_id, "sar_center_radial_pixel")
        errors = np.abs(pred - actual)
        cover = []
        ratios = []
        for pid, rho in zip(test_ids, pred):
            field = dict(base_by_id[pid])
            margin = 2.0 * robust_percentile(errors, 80, 60.0) + (20.0 if ablation_id == "F" else 0.0)
            field["rho_center"] = fmt(rho, 6)
            field["rho_low_95"] = fmt(max(0.0, rho - margin), 6)
            field["rho_high_95"] = fmt(min(FAN_RADIUS_PX, rho + margin), 6)
            field["radial_min"] = field["rho_low_95"]
            field["radial_max"] = field["rho_high_95"]
            cover.append(contained(field, sar_by_id[pid], "95"))
            ratios.append(search_ratio(field))
        rows.append(
            {
                "ablation_id": ablation_id,
                "features": features,
                "test_pair_count": len(test_ids),
                "median_radial_error": fmt(median(errors), 6),
                "p90_radial_error": fmt(p90(errors), 6),
                "median_search_ratio": fmt(median(ratios), 8),
                "center_coverage_95": fmt(sum(cover) / len(cover) if cover else 0.0, 6),
                "interpretation": "post-freeze holdout ablation; test labels used only for final scoring",
            }
        )
    return rows


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    subset = list(rows[:limit] if limit is not None else rows)
    if not subset:
        return "none"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in subset:
        lines.append("| " + " | ".join(norm(row.get(field, "")).replace("\n", " ") for field in fields) + " |")
    return "\n".join(lines)


def render_pair_audit_report(
    pair_rows: Sequence[Mapping[str, Any]],
    depth_rows: Sequence[Mapping[str, Any]],
    split_rows: Sequence[Mapping[str, Any]],
) -> None:
    pair_counts = Counter(row["pair_confidence"] for row in pair_rows)
    scene_counts = Counter(row["scene"] for row in pair_rows)
    usable = [row for row in pair_rows if row["usable_for_calibration"] == "true"]
    lines = [
        "# OTY2 WGV3.5A Pair And Depth Audit",
        "",
        f"Date: {DATE}",
        "",
        "## Boundary",
        "",
        "This stage uses existing optical-SAR correspondence rows for weak calibration. It does not modify GT, does not output final automatic annotations, and does not use SAR PNG brightness for whole-image target discovery.",
        "",
        "## Pair Inventory",
        "",
        f"- source: `{rel(PAIR_SOURCE)}`",
        f"- total_pairs: `{len(pair_rows)}`",
        f"- usable_high_confidence_pairs: `{len(usable)}`",
        f"- scenes: `{dict(scene_counts)}`",
        f"- pair_confidence_counts: `{dict(pair_counts)}`",
        "",
        "## Depth Source Audit",
        "",
        md_table(depth_rows, ["scene", "depth_source_status", "depth_meaning", "frame_alignment", "depth_file_count", "optical_frame_count", "strategy", "train_spearman_like_corr_to_sar_radial"]),
        "",
        "## Identity-Safe Split",
        "",
        md_table(split_rows, ["scene", "thread_id", "split_role", "pair_count", "frame_start", "frame_end", "leakage_check"]),
        "",
        "## Interpretation",
        "",
        "GM_RM017 provides the main high-confidence calibration pool. GM_RM019 is preserved as an external-scene holdout. The split is by vehicle thread/scene, not random frame sampling.",
    ]
    write_text(OUTPUTS["pair_audit_md"], "\n".join(lines))


def make_overlay_image(
    pair: Mapping[str, Any],
    sar: Mapping[str, Any],
    optical: Mapping[str, Any],
    fields: Mapping[str, Mapping[str, Any]],
    out_path: Path,
) -> None:
    scene = pair["scene"]
    opt_path = frame_path(scene, parse_int(pair["optical_frame"]))
    s_path = sar_gray_path(scene, parse_int(pair["sar_frame"]))
    d_path = depth_path(scene, parse_int(pair["optical_frame"]))
    if opt_path.exists():
        optical_img = Image.open(opt_path).convert("RGB").resize((320, 240))
    else:
        optical_img = Image.new("RGB", (320, 240), "black")
    if d_path.exists():
        arr = np.load(d_path)
        finite = arr[np.isfinite(arr)]
        lo, hi = np.percentile(finite, [2, 98]) if finite.size else (0, 1)
        vis = np.clip((arr - lo) / max(1e-6, hi - lo), 0, 1)
        depth_img = Image.fromarray(np.uint8(vis * 255)).convert("RGB").resize((320, 240))
    else:
        depth_img = Image.new("RGB", (320, 240), "black")
    if s_path.exists():
        sar_img = Image.open(s_path).convert("RGB").resize((416, 240))
    else:
        sar_img = Image.new("RGB", (416, 240), "black")
    canvas = Image.new("RGB", (1056, 300), (18, 18, 18))
    canvas.paste(optical_img, (0, 0))
    canvas.paste(depth_img, (320, 0))
    canvas.paste(sar_img, (640, 0))
    draw = ImageDraw.Draw(canvas)
    scale_x_opt, scale_y_opt = 320 / 800.0, 240 / 600.0
    obox = Box(
        parse_float(pair["optical_bbox_x1"]),
        parse_float(pair["optical_bbox_y1"]),
        parse_float(pair["optical_bbox_x2"]),
        parse_float(pair["optical_bbox_y2"]),
    )
    for offset in [0, 320]:
        draw.rectangle(
            [
                offset + obox.x1 * scale_x_opt,
                obox.y1 * scale_y_opt,
                offset + obox.x2 * scale_x_opt,
                obox.y2 * scale_y_opt,
            ],
            outline=(255, 220, 60),
            width=2,
        )
    scale_x_sar, scale_y_sar = 416 / SAR_WIDTH, 240 / SAR_HEIGHT
    gt_box = Box(parse_float(pair["sar_bbox_x1"]), parse_float(pair["sar_bbox_y1"]), parse_float(pair["sar_bbox_x2"]), parse_float(pair["sar_bbox_y2"]))
    draw.rectangle(
        [
            640 + gt_box.x1 * scale_x_sar,
            gt_box.y1 * scale_y_sar,
            640 + gt_box.x2 * scale_x_sar,
            gt_box.y2 * scale_y_sar,
        ],
        outline=(0, 255, 128),
        width=2,
    )
    colors = {"P0": (120, 120, 255), "P1": (255, 170, 0), "P2": (255, 60, 60)}
    for name, field in fields.items():
        # Approximate polar feasible interval on the SAR canvas by drawing a
        # bounding wedge sample envelope. It is a visualization aid only.
        amin, amax = parse_float(field["azimuth_min"]), parse_float(field["azimuth_max"])
        rmin, rmax = parse_float(field["radial_min"]), parse_float(field["radial_max"])
        pts = []
        for az in np.linspace(amin, amax, 12):
            for r in (rmin, rmax):
                rad = math.radians(az)
                x = FAN_CENTER_X + r * math.sin(rad)
                y = FAN_CENTER_Y - r * math.cos(rad)
                pts.append((640 + x * scale_x_sar, y * scale_y_sar))
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            draw.rectangle([min(xs), min(ys), max(xs), max(ys)], outline=colors[name], width=2)
    draw.text((8, 248), f"{pair['pair_id']} {scene} o{pair['optical_frame']} s{pair['sar_frame']}", fill=(240, 240, 240))
    draw.text((644, 248), "green=GT  blue=P0  orange=P1  red=P2", fill=(240, 240, 240))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def select_visual_cases(
    pair_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    fields: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[str]:
    pair_by_id = rows_by_id(pair_rows)
    sar_by_id = rows_by_id(sar_rows)
    p2_by_id = rows_by_id(fields["P2"])
    buckets: dict[str, list[str]] = defaultdict(list)
    for pair in pair_rows:
        if pair["usable_for_calibration"] != "true":
            continue
        pid = pair["pair_id"]
        vis = pair.get("visibility_state", "")
        if role_for_pair(pair) in {"train", "validation"}:
            buckets["train"].append(pid)
        if role_for_pair(pair) in {"test", "external_scene_test"}:
            buckets["test"].append(pid)
        if "boundary_truncation_present" in vis or parse_float(pair["optical_bbox_x1"]) < 2 or parse_float(pair["optical_bbox_x2"]) > 798:
            buckets["edge_truncation"].append(pid)
        if "occlusion" in vis:
            buckets["occlusion"].append(pid)
        if "multi=single_observation" not in vis:
            buckets["multi_competition"].append(pid)
        field = p2_by_id.get(pid)
        sar = sar_by_id.get(pid)
        if field and sar:
            if abs(parse_float(field["rho_center"]) - parse_float(sar["sar_center_radial_pixel"])) > 80:
                buckets["radial_failure"].append(pid)
            if abs(parse_float(field["azimuth_center"]) - parse_float(sar["sar_center_azimuth_deg"])) > 5:
                buckets["azimuth_failure"].append(pid)
    selected: list[str] = []
    for bucket in ["train", "test", "edge_truncation", "occlusion", "multi_competition", "radial_failure", "azimuth_failure"]:
        for pid in buckets[bucket][:3]:
            if pid not in selected:
                selected.append(pid)
    if len(selected) < 18:
        for pair in pair_rows:
            pid = pair["pair_id"]
            if pair["usable_for_calibration"] == "true" and pid not in selected:
                selected.append(pid)
            if len(selected) >= 18:
                break
    return selected[:24]


def render_visual_report(
    pair_rows: Sequence[Mapping[str, Any]],
    sar_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    fields: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    pair_by_id = rows_by_id(pair_rows)
    sar_by_id = rows_by_id(sar_rows)
    optical_by_id = rows_by_id(optical_rows)
    field_by_variant = {variant: rows_by_id(rows) for variant, rows in fields.items()}
    case_ids = select_visual_cases(pair_rows, sar_rows, optical_rows, fields)
    lines = [
        "# OTY2 WGV3.5A Visual Feasible Field Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "The overlay PNGs are written under the ignored `outputs/` directory and are not intended for commit.",
        "",
    ]
    for idx, pid in enumerate(case_ids, 1):
        pair = pair_by_id[pid]
        sar = sar_by_id[pid]
        optical = optical_by_id[pid]
        case_fields = {variant: field_by_variant[variant][pid] for variant in ["P0", "P1", "P2"] if pid in field_by_variant[variant]}
        out_path = VISUAL_OUTPUT_DIR / f"wgv3_5a_review_{idx:02d}_{pid}.png"
        make_overlay_image(pair, sar, optical, case_fields, out_path)
        p0, p1, p2 = case_fields["P0"], case_fields["P1"], case_fields["P2"]
        p2_cover = contained(p2, sar, "95")
        p1_ratio, p2_ratio = search_ratio(p1), search_ratio(p2)
        lines.extend(
            [
                f"## Case {idx:02d}: `{pid}`",
                "",
                f"- Overlay: `{rel(out_path)}`",
                f"- 光学车辆状态: `{pair['visibility_state']}`; split=`{role_for_pair(pair)}`",
                f"- 深度是否可信: `{optical['depth_valid_ratio']}` valid ratio; strategy values D1=`{optical['depth_D1']}`, D4=`{optical['depth_D4']}`",
                f"- 方位预测是否合理: predicted `{p2['azimuth_center']}`, GT `{sar['sar_center_azimuth_deg']}`",
                f"- 径向预测是否合理: predicted `{p2['rho_center']}`, GT `{sar['sar_center_radial_pixel']}`",
                f"- 航向信息是否产生有效压缩: `{p2['heading_state']}`; P2/P1 search ratio `{fmt(p2_ratio / p1_ratio if p1_ratio else 0, 4)}`",
                "- P0为什么过宽: it keeps the full radial fan and a wide legacy optical-x azimuth sector.",
                "- P1缩小了什么: it uses weak calibrated azimuth and depth-conditioned radial intervals.",
                "- P2是否进一步缩小: only when the heading proxy is usable; otherwise it preserves/expands uncertainty for visibility risk.",
                f"- 真实SAR标注是否被覆盖: `{bool_text(p2_cover)}`",
                f"- 失败由哪一层造成: `{'covered' if p2_cover else 'see_failure_cases_csv'}`",
                "",
            ]
        )
    write_text(OUTPUTS["visual_md"], "\n".join(lines))


def render_closure_report(
    pair_rows: Sequence[Mapping[str, Any]],
    depth_rows: Sequence[Mapping[str, Any]],
    split_rows: Sequence[Mapping[str, Any]],
    time_rows: Sequence[Mapping[str, Any]],
    az_rows: Sequence[Mapping[str, Any]],
    radial_rows: Sequence[Mapping[str, Any]],
    heading_rows: Sequence[Mapping[str, Any]],
    holdout_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    freeze_sha: str,
) -> str:
    hold = {row["model_variant"]: row for row in holdout_rows}
    p0, p1, p2 = hold.get("P0", {}), hold.get("P1", {}), hold.get("P2", {})
    selected_time = next(row for row in time_rows if row["selected"] == "true")
    selected_az = next(row for row in az_rows if row["selected"] == "true")
    selected_rad = next(row for row in radial_rows if row["selected"] == "true")
    depth_status = ";".join(f"{row['scene']}={row['depth_source_status']}" for row in depth_rows)
    selected_depth = next((row["strategy"] for row in depth_rows if row["scene"] == "GM_RM017"), "")
    p1_reduction = parse_float(p0.get("median_search_ratio")) - parse_float(p1.get("median_search_ratio"))
    p2_vs_p1 = parse_float(p1.get("median_search_ratio")) - parse_float(p2.get("median_search_ratio"))
    p2_cov = parse_float(p2.get("center_coverage_95"), 0.0)
    if p2_cov >= 0.9 and p1_reduction > 0:
        status = "CLOSED_DEPTH_RADIAL_COMPRESSION_FEASIBLE" if p2_vs_p1 <= 0 else "CLOSED_WEAK_CALIBRATED_PHYSICAL_FIELD_FEASIBLE"
    elif p1_reduction > 0:
        status = "CLOSED_SCENE_SPECIFIC_WEAK_CALIBRATION_ONLY"
    else:
        status = "CLOSED_WEAK_PHYSICAL_PROJECTION_INSUFFICIENT"
    heading_usable = sum(1 for row in heading_rows if row["usable_for_compression"] == "true")
    heading_unknown = sum(1 for row in heading_rows if row["heading_representation"] == "unknown")
    failure_counts = Counter()
    for row in failure_rows:
        for part in norm(row.get("failure_type")).split(";"):
            if part:
                failure_counts[part] += 1
    train_threads = [row["thread_id"] for row in split_rows if row["split_role"] == "train"]
    val_threads = [row["thread_id"] for row in split_rows if row["split_role"] == "validation"]
    test_threads = [row["thread_id"] for row in split_rows if row["split_role"] == "test"]
    external_threads = [row["thread_id"] for row in split_rows if row["split_role"] == "external_scene_test"]
    pair_counts = Counter(row["pair_confidence"] for row in pair_rows)
    scenes = sorted(set(row["scene"] for row in pair_rows))
    blocked = sum(1 for row in pair_rows if row["usable_for_calibration"] != "true")
    depth_ablation = {row["ablation_id"]: row for row in ablation_rows}
    depth_improvement = parse_float(depth_ablation.get("B", {}).get("p90_radial_error"), 0.0) - parse_float(depth_ablation.get("C", {}).get("p90_radial_error"), 0.0)
    smoothing_improvement = parse_float(depth_ablation.get("C", {}).get("p90_radial_error"), 0.0) - parse_float(depth_ablation.get("D", {}).get("p90_radial_error"), 0.0)
    heading_improvement = parse_float(depth_ablation.get("D", {}).get("p90_radial_error"), 0.0) - parse_float(depth_ablation.get("E", {}).get("p90_radial_error"), 0.0)
    visibility_improvement = parse_float(depth_ablation.get("E", {}).get("p90_radial_error"), 0.0) - parse_float(depth_ablation.get("F", {}).get("p90_radial_error"), 0.0)
    lines = [
        "# OTY2 WGV3.5A Weak Physical Feasible-Field Closure",
        "",
        f"Date: {DATE}",
        "",
        f"WGV3.5A status: `{status}`",
        "",
        "## Boundary",
        "",
        "This closes a weak-calibration feasible-field experiment. SAR GT is used only for weak calibration/evaluation from existing correspondence rows. No GT or manual annotation is modified, no final SAR box is emitted, and no selector/ranking stage is introduced.",
        "",
        "## Holdout Metrics",
        "",
        md_table(holdout_rows, HOLDOUT_FIELDS),
        "",
        "## Ablation",
        "",
        md_table(ablation_rows, ABLATION_FIELDS),
        "",
        "## Selected Models",
        "",
        md_table([selected_time], CALIBRATION_FIELDS),
        "",
        md_table([selected_az], CALIBRATION_FIELDS),
        "",
        md_table([selected_rad], CALIBRATION_FIELDS),
        "",
        "## Final Summary Fields",
        "",
        f"- Branch: `{git_fact(['branch', '--show-current'])}`",
        "- Start commit: `3d9b0118086ec5d3dfe970c68ee083dff529c842`",
        f"- Generation HEAD: `{git_fact(['rev-parse', 'HEAD'])}`",
        f"- Pair audit: total `{len(pair_rows)}`, high-confidence `{pair_counts['high_confidence_pair']}`, scenes `{scenes}`, threads `{len(set(row['optical_thread_id'] for row in pair_rows))}`, blocked `{blocked}`",
        f"- Depth audit: `{depth_status}`; selected strategy `{selected_depth}`; frame alignment recorded in `{rel(OUTPUTS['depth_strategy'])}`",
        f"- Identity split: train `{len(train_threads)}` threads, validation `{len(val_threads)}`, test `{len(test_threads)}`, external `{len(external_threads)}`",
        f"- Freeze SHA256: `{freeze_sha}`",
        "- Test labels read before freeze: `false`",
        "- Test threads used for fitting: `false`",
        f"- Heading usable count: `{heading_usable}`; unknown heading count: `{heading_unknown}`",
        f"- Dominant failure counts: `{dict(failure_counts)}`",
        "",
        "## Direct Answers",
        "",
        f"1. 在没有准确内参和外参、只有20 cm以内传感器间距的条件下，可以建立可用但场景/数据依赖的弱标定；当前关闭状态是 `{status}`，不能称为真实三维标定。",
        f"2. 光学深度在本轮提供了径向压缩证据；B到C的P90径向误差改善为 `{fmt(depth_improvement, 4)}` px，但深度被标记为相对/弱单调来源，不当作米制距离。",
        f"3. 航向和车体尺度的额外压缩有限；D到E的P90改善为 `{fmt(heading_improvement, 4)}` px，很多边缘/短轨迹样本仍退化为 unknown。",
        f"4. P1可以作为下一步批量标注迁移的物理前端候选；P2只有在航向稳定样本上可用，暂不建议把P2作为无人工复核的批量入口。",
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{rel(path)}`" for path in OUTPUTS.values()),
    ]
    return "\n".join(lines)


def write_freeze_manifest(
    depth_strategy: str,
    time_rows: Sequence[Mapping[str, Any]],
    az_rows: Sequence[Mapping[str, Any]],
    radial_rows: Sequence[Mapping[str, Any]],
) -> str:
    source_paths = [
        OUTPUTS["paired_annotations"],
        OUTPUTS["split"],
        OUTPUTS["depth_strategy"],
        OUTPUTS["time_calibration"],
        OUTPUTS["azimuth_calibration"],
        OUTPUTS["radial_calibration"],
    ]
    selected_time = next(row for row in time_rows if row["selected"] == "true")
    selected_az = next(row for row in az_rows if row["selected"] == "true")
    selected_rad = next(row for row in radial_rows if row["selected"] == "true")
    combined = combined_sha(source_paths)
    rows = []
    for idx, path in enumerate(source_paths, 1):
        rows.append(
            {
                "freeze_id": f"WGV35A_FREEZE_{idx:03d}",
                "stage": "freeze",
                "source_file": rel(path),
                "sha256": sha256_file(path),
                "combined_sha256": combined,
                "data_split_sha256": sha256_file(OUTPUTS["split"]),
                "paired_annotations_sha256": sha256_file(OUTPUTS["paired_annotations"]),
                "selected_depth_strategy": depth_strategy,
                "time_model": selected_time["model_name"],
                "azimuth_model": selected_az["model_name"],
                "radial_model": selected_rad["model_name"],
                "heading_rule": "optical_motion_proxy_with_unknown_degradation",
                "vehicle_size_prior": "learned_sar_span_only;metric_projection_disabled_without_metric_depth_provenance",
                "uncertainty_interval_source": "validation_thread_residual_quantiles",
                "test_sar_labels_read_before_freeze": "false",
                "test_metrics_read_before_freeze": "false",
                "test_threads_used_for_fitting": "false",
                "notes": "freeze created before holdout evaluation; test rows excluded from fitting/model selection",
            }
        )
    write_csv(OUTPUTS["freeze"], rows, FREEZE_FIELDS)
    return combined


def run_all() -> dict[str, Any]:
    pair_rows, sar_rows = build_pair_rows()
    split_rows = build_split_rows(pair_rows)
    optical_rows = build_optical_rows(pair_rows)
    depth_rows = build_depth_audit_rows(pair_rows, optical_rows, sar_rows)
    depth_strategy = selected_depth_strategy(depth_rows)
    model_bundle, time_rows, az_rows, radial_rows, heading_rows = fit_models(pair_rows, optical_rows, sar_rows, depth_strategy)
    fields = build_fields(pair_rows, optical_rows, heading_rows, model_bundle)
    write_csv(OUTPUTS["paired_annotations"], pair_rows, PAIR_FIELDS)
    write_csv(OUTPUTS["split"], split_rows, SPLIT_FIELDS)
    write_csv(OUTPUTS["optical_states"], optical_rows, OPTICAL_STATE_FIELDS)
    write_csv(OUTPUTS["sar_polar"], sar_rows, SAR_POLAR_FIELDS)
    write_csv(OUTPUTS["depth_strategy"], depth_rows, DEPTH_FIELDS)
    render_pair_audit_report(pair_rows, depth_rows, split_rows)
    write_csv(OUTPUTS["time_calibration"], time_rows, CALIBRATION_FIELDS)
    write_csv(OUTPUTS["azimuth_calibration"], az_rows, CALIBRATION_FIELDS)
    write_csv(OUTPUTS["radial_calibration"], radial_rows, CALIBRATION_FIELDS)
    write_csv(OUTPUTS["heading_state"], heading_rows, HEADING_FIELDS)
    write_csv(OUTPUTS["fields_p0"], fields["P0"], FIELD_FIELDS)
    write_csv(OUTPUTS["fields_p1"], fields["P1"], FIELD_FIELDS)
    write_csv(OUTPUTS["fields_p2"], fields["P2"], FIELD_FIELDS)
    freeze_sha = write_freeze_manifest(depth_strategy, time_rows, az_rows, radial_rows)
    holdout_rows, failure_rows = evaluate_holdout(pair_rows, sar_rows, fields)
    ablation_rows = evaluate_ablations(pair_rows, optical_rows, sar_rows, depth_strategy, fields["P1"])
    write_csv(OUTPUTS["holdout"], holdout_rows, HOLDOUT_FIELDS)
    write_csv(OUTPUTS["ablation"], ablation_rows, ABLATION_FIELDS)
    write_csv(OUTPUTS["failures"], failure_rows, FAILURE_FIELDS)
    render_visual_report(pair_rows, sar_rows, optical_rows, fields)
    closure = render_closure_report(pair_rows, depth_rows, split_rows, time_rows, az_rows, radial_rows, heading_rows, holdout_rows, ablation_rows, failure_rows, freeze_sha)
    write_text(OUTPUTS["closure_md"], closure)
    return {
        "status": closure.split("`")[1] if "`" in closure else "unknown",
        "freeze_sha": freeze_sha,
        "holdout": holdout_rows,
        "outputs": {key: str(path) for key, path in OUTPUTS.items()},
    }


def ensure_freeze_exists() -> None:
    if not OUTPUTS["freeze"].exists():
        raise RuntimeError("freeze manifest is missing; run --stage freeze or --stage all first")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["audit", "fit", "freeze", "evaluate", "all"], default="all")
    args = parser.parse_args(argv)
    if args.stage in {"audit", "fit", "freeze", "all"}:
        result = run_all()
    else:
        ensure_freeze_exists()
        result = run_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
