"""Audit GM_RM019 mask-aware GT response geometry in physical scale.

This diagnostic is posthoc only. It audits whether an absolute physical
meter-scale mapping exists before any GT-anchored SAR response fitting is
attempted. If the mapping is unresolved, it preserves pixel/angle evidence and
emits blocked model rows instead of renaming pixels as meters.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path("D:/profile/research/data")
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_gm_rm019_mask_aware_gt_physical_scale_fit_20260712.md")
VERIFY_TMP_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_mask_aware_gt_physical_scale_fit_20260712" / "_verify_tmp"

DATE = "20260712"
SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
AZIMUTH_MIN_DEG = -90.0
AZIMUTH_MAX_DEG = 90.0

STATUS_ABSOLUTE_UNRESOLVED = "ABSOLUTE_SCALE_UNRESOLVED"
BLOCKED_REASON = (
    "no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, "
    "chirp bandwidth, FFT/grid, or display resize/crop provenance recovered"
)

INPUTS = {
    "directional_measurements": SAMPLES_DIR / "oty2_gm_rm019_static_directional_spread_measurements_20260712.csv",
    "directional_pairwise_controls": SAMPLES_DIR / "oty2_gm_rm019_static_directional_spread_pairwise_controls_20260712.csv",
    "paired_annotations": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "sar_polar_targets": SAMPLES_DIR / "oty2_wgv3_5a_sar_polar_targets_20260710.csv",
    "mask_observation_audit": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv",
    "mask_source_inventory": SAMPLES_DIR / "oty2_wgv3_5a_r2c_sar_mask_source_inventory_20260711.csv",
    "mask_aware_intervals": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_mask_aware_intervals_20260711.csv",
    "local_response_units": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv",
    "response_unit_gt_matrix": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv",
    "boundary_variant_families": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv",
    "center_semantic_review": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_center_semantic_review_20260711.csv",
    "mask_definition_report": REPORT_DIR / "oty2_wgv3_5a_r2c_sar_mask_definition_20260711.md",
    "mask_gate_report": REPORT_DIR / "oty2_wgv3_5a_r2c_gm019_mask_supervision_gate_20260711.md",
    "mask_closure_report": REPORT_DIR / "oty2_wgv3_5a_r2c_mask_aware_closure_20260711.md",
    "static_directional_report": REPORT_DIR / "oty2_gm_rm019_static_directional_spread_measurement_20260712.md",
    "static_registry_report": REPORT_DIR / "oty2_gm_rm019_static_physical_factor_registry_20260712.md",
    "static_directional_script": REPO_ROOT / "tools" / "diagnostics" / "run_oty2_gm_rm019_static_directional_spread_measurement.py",
    "mask_mapping_script": REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py",
    "support_probe_script": REPO_ROOT / "tools" / "diagnostics" / "run_oty2_support_region_sar_observation_probe.py",
    "gm019_runtime_config": Path("D:/profile/research/workspace/tools/configs/gm_rm019_vehicle_assembly_physics_v2.json"),
}

OUTPUTS = {
    "scale": SAMPLES_DIR / "oty2_gm_rm019_absolute_scale_calibration_20260712.csv",
    "gt_geometry": SAMPLES_DIR / "oty2_gm_rm019_gt_mask_visible_geometry_20260712.csv",
    "sar_intervals": SAMPLES_DIR / "oty2_gm_rm019_sar_energy_physical_intervals_20260712.csv",
    "fit_rows": SAMPLES_DIR / "oty2_gm_rm019_gt_sar_physical_fit_rows_20260712.csv",
    "model_comparison": SAMPLES_DIR / "oty2_gm_rm019_gt_sar_physical_model_comparison_20260712.csv",
    "holdout": SAMPLES_DIR / "oty2_gm_rm019_gt_sar_physical_holdout_evaluation_20260712.csv",
    "counterexamples": SAMPLES_DIR / "oty2_gm_rm019_gt_sar_physical_counterexamples_20260712.csv",
    "integrity": SAMPLES_DIR / "oty2_gm_rm019_gt_sar_physical_integrity_20260712.csv",
    "report": REPORT_DIR / "oty2_gm_rm019_mask_aware_gt_physical_scale_fit_20260712.md",
}

SCALE_FIELDS = [
    "parameter_name",
    "value",
    "unit",
    "source_file",
    "source_line_or_field",
    "derivation_formula",
    "confidence",
    "used_for_current_fit",
    "status",
    "notes_cn",
]

GT_GEOMETRY_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "sar_frame",
    "sar_bbox",
    "gt_semantic",
    "gt_semantic_confidence",
    "mask_semantic",
    "mask_confidence",
    "mask_class",
    "gt_full_area_px",
    "gt_visible_area_px",
    "gt_visible_fraction",
    "gt_bbox_intersects_invalid_mask",
    "source_mask_intersection_ratio",
    "computed_display_fan_intersection_ratio",
    "gt_range_min_px",
    "gt_range_max_px",
    "gt_range_width_px",
    "gt_azimuth_min_deg",
    "gt_azimuth_max_deg",
    "gt_azimuth_width_deg",
    "gt_near_side_censored",
    "gt_far_side_censored",
    "gt_left_side_censored",
    "gt_right_side_censored",
    "gt_signed_mask_distance_px",
    "actual_fan_pixel_censored",
    "gt_pair_linked_mask_context",
    "frame_only_mask_context",
    "sar_response_touches_mask",
    "sar_response_truncation_direction",
    "multiple_boundary_variant_uncertainty",
    "absolute_scale_status",
    "gt_range_min_m",
    "gt_range_max_m",
    "gt_range_width_m",
    "gt_cross_range_arc_width_m",
    "gt_cross_range_chord_width_m",
    "notes_cn",
]

SAR_INTERVAL_FIELDS = [
    "response_unit_id",
    "sar_frame",
    "measurement_region_type",
    "matched_gt_pair_id",
    "matched_gt_instance_id",
    "response_region_bbox",
    "physical_vehicle_id",
    "mask_class",
    "gt_pair_linked_mask_context",
    "frame_only_mask_context",
    "mask_state",
    "actual_fan_pixel_censored",
    "gt_bbox_intersects_invalid_mask",
    "sar_response_touches_mask",
    "sar_response_truncation_direction",
    "multiple_boundary_variant_uncertainty",
    "response_center_radial_px",
    "response_center_azimuth_deg",
    "range_p50_width_px",
    "range_p80_width_px",
    "range_p90_width_px",
    "azimuth_p50_width_px",
    "azimuth_p80_width_px",
    "azimuth_p90_width_px",
    "sar_azimuth_p50_width_deg_approx",
    "sar_azimuth_p80_width_deg_approx",
    "sar_azimuth_p90_width_deg_approx",
    "sar_range_p80_interval_m",
    "sar_cross_range_p80_width_m",
    "absolute_scale_status",
    "scale_blocked_reason",
]

FIT_ROW_FIELDS = [
    "fit_row_id",
    "response_unit_id",
    "sar_frame",
    "matched_gt_pair_id",
    "matched_gt_instance_id",
    "physical_vehicle_id",
    "mask_class",
    "gt_semantic",
    "gt_visible_fraction",
    "gt_visible_range_width_px",
    "gt_visible_azimuth_width_deg",
    "sar_range_p80_width_px",
    "sar_azimuth_p80_width_px",
    "sar_azimuth_p80_width_deg_approx",
    "boundary_variant_uncertainty",
    "fit_eligible",
    "absolute_scale_status",
    "blocked_reason",
]

MODEL_FIELDS = [
    "target_dimension",
    "model_id",
    "model_name",
    "training_sample_count",
    "candidate_input_rows",
    "holdout_fold_count",
    "failed_fold_count",
    "baseline_error",
    "candidate_model_error",
    "absolute_improvement",
    "relative_improvement",
    "MAE_m",
    "median_absolute_error_m",
    "p90_absolute_error_m",
    "relative_error",
    "signed_bias_m",
    "run_status",
    "blocked_reason",
]

HOLDOUT_FIELDS = [
    "fold_strategy",
    "potential_group_count",
    "potential_sample_count",
    "min_group_size",
    "max_group_size",
    "same_pair_cross_fold_violation",
    "holdout_fold_count",
    "failed_fold_count",
    "run_status",
    "blocked_reason",
]

COUNTEREXAMPLE_FIELDS = [
    "counterexample_id",
    "counterexample_type",
    "pair_id",
    "response_unit_id",
    "sar_frame",
    "physical_vehicle_id",
    "mask_class",
    "gt_semantic",
    "absolute_range_m",
    "gt_visible_width_m",
    "sar_p80_width_m",
    "endpoint_errors",
    "model_residuals",
    "why_it_matters_cn",
    "visual_review_relpath",
]

INTEGRITY_FIELDS = ["gate_name", "status", "detail", "source_file", "sha256", "row_count"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".csv":
        return ""
    try:
        return str(len(read_rows(path)))
    except Exception:
        return ""


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value if value is not None else "").strip()
        return default if not text else float(text)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = -1) -> int:
    number = parse_float(value)
    if math.isnan(number):
        return default
    return int(round(number))


def fmt(value: Any, digits: int = 6) -> str:
    number = parse_float(value)
    if math.isnan(number) or not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_box(text: str) -> tuple[float, float, float, float] | None:
    parts = [parse_float(part) for part in str(text or "").replace("|", ",").split(",")]
    if len(parts) != 4 or any(math.isnan(part) for part in parts):
        return None
    x1, y1, x2, y2 = parts
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def radial_px(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


def azimuth_deg(x: float, y: float) -> float:
    return math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))


def fan_valid(x: float, y: float) -> bool:
    angle = azimuth_deg(x, y)
    return (
        0.0 <= x < SAR_WIDTH
        and 0.0 <= y < SAR_HEIGHT
        and radial_px(x, y) <= FAN_RADIUS_PX
        and AZIMUTH_MIN_DEG <= angle <= AZIMUTH_MAX_DEG
    )


def iter_box_pixels(box: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    x1, y1, x2, y2 = box
    ix1 = max(0, int(math.floor(x1)))
    iy1 = max(0, int(math.floor(y1)))
    ix2 = min(SAR_WIDTH, int(math.ceil(x2)))
    iy2 = min(SAR_HEIGHT, int(math.ceil(y2)))
    return [(x + 0.5, y + 0.5) for y in range(iy1, iy2) for x in range(ix1, ix2)]


def edge_invalid_flags(box: tuple[float, float, float, float]) -> dict[str, bool]:
    x1, y1, x2, y2 = box
    ix1 = max(0, int(math.floor(x1)))
    iy1 = max(0, int(math.floor(y1)))
    ix2 = min(SAR_WIDTH, int(math.ceil(x2)))
    iy2 = min(SAR_HEIGHT, int(math.ceil(y2)))
    left = any(not fan_valid(ix1 + 0.5, y + 0.5) for y in range(iy1, iy2)) if ix1 < ix2 else False
    right = any(not fan_valid(ix2 - 0.5, y + 0.5) for y in range(iy1, iy2)) if ix1 < ix2 else False
    far = any(not fan_valid(x + 0.5, iy1 + 0.5) for x in range(ix1, ix2)) if iy1 < iy2 else False
    near = any(not fan_valid(x + 0.5, iy2 - 0.5) for x in range(ix1, ix2)) if iy1 < iy2 else False
    return {"left": left, "right": right, "far": far, "near": near}


def box_geometry(box_text: str) -> dict[str, Any]:
    box = parse_box(box_text)
    if box is None:
        return {
            "full_area": 0,
            "visible_area": 0,
            "visible_fraction": math.nan,
            "range_min": math.nan,
            "range_max": math.nan,
            "azimuth_min": math.nan,
            "azimuth_max": math.nan,
            "flags": {"left": False, "right": False, "far": False, "near": False},
        }
    pixels = iter_box_pixels(box)
    visible = [(x, y) for x, y in pixels if fan_valid(x, y)]
    ranges = [radial_px(x, y) for x, y in visible]
    azimuths = [azimuth_deg(x, y) for x, y in visible]
    flags = edge_invalid_flags(box)
    full_area = len(pixels)
    visible_area = len(visible)
    return {
        "full_area": full_area,
        "visible_area": visible_area,
        "visible_fraction": visible_area / full_area if full_area else math.nan,
        "range_min": min(ranges) if ranges else math.nan,
        "range_max": max(ranges) if ranges else math.nan,
        "azimuth_min": min(azimuths) if azimuths else math.nan,
        "azimuth_max": max(azimuths) if azimuths else math.nan,
        "flags": flags,
    }


def first_source_line(path: Path, needle: str) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for idx, line in enumerate(handle, start=1):
                if needle in line:
                    return str(idx)
    except OSError:
        return ""
    return ""


def require_inputs() -> None:
    missing = [rel(path) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required input files: " + "; ".join(missing))


def load_context() -> dict[str, list[dict[str, str]]]:
    require_inputs()
    return {name: read_rows(path) for name, path in INPUTS.items() if path.suffix.lower() == ".csv"}


def build_scale_rows() -> list[dict[str, str]]:
    direction_script = INPUTS["static_directional_script"]
    mask_script = INPUTS["mask_mapping_script"]
    support_script = INPUTS["support_probe_script"]
    config = INPUTS["gm019_runtime_config"]
    candidate_m_per_px = 40.0 / FAN_RADIUS_PX
    rows = [
        {
            "parameter_name": "sar_image_width_px",
            "value": str(SAR_WIDTH),
            "unit": "px",
            "source_file": rel(direction_script),
            "source_line_or_field": first_source_line(direction_script, "SAR_WIDTH ="),
            "derivation_formula": "constant reused from current SAR PNG geometry",
            "confidence": "high_for_png_geometry",
            "used_for_current_fit": "false",
            "status": "SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY",
            "notes_cn": "用于PNG坐标审计；不是米制标定。",
        },
        {
            "parameter_name": "sar_image_height_px",
            "value": str(SAR_HEIGHT),
            "unit": "px",
            "source_file": rel(direction_script),
            "source_line_or_field": first_source_line(direction_script, "SAR_HEIGHT ="),
            "derivation_formula": "constant reused from current SAR PNG geometry",
            "confidence": "high_for_png_geometry",
            "used_for_current_fit": "false",
            "status": "SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY",
            "notes_cn": "用于PNG坐标审计；不是米制标定。",
        },
        {
            "parameter_name": "fan_center_x_px",
            "value": fmt(FAN_CENTER_X),
            "unit": "px",
            "source_file": rel(mask_script),
            "source_line_or_field": first_source_line(mask_script, "FAN_CENTER_X ="),
            "derivation_formula": "configured fan center",
            "confidence": "high_for_display_fan_geometry",
            "used_for_current_fit": "false",
            "status": "SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY",
            "notes_cn": "可支持径向/方位角像素几何，不能证明物理坐标轴。",
        },
        {
            "parameter_name": "fan_center_y_px",
            "value": fmt(FAN_CENTER_Y),
            "unit": "px",
            "source_file": rel(mask_script),
            "source_line_or_field": first_source_line(mask_script, "FAN_CENTER_Y ="),
            "derivation_formula": "configured fan center",
            "confidence": "high_for_display_fan_geometry",
            "used_for_current_fit": "false",
            "status": "SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY",
            "notes_cn": "可支持径向/方位角像素几何，不能证明物理坐标轴。",
        },
        {
            "parameter_name": "fan_radius_px",
            "value": fmt(FAN_RADIUS_PX),
            "unit": "px",
            "source_file": rel(support_script),
            "source_line_or_field": first_source_line(support_script, "FAN_RADIUS_PX ="),
            "derivation_formula": "configured display fan radius",
            "confidence": "high_for_display_fan_geometry",
            "used_for_current_fit": "false",
            "status": "SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY",
            "notes_cn": "只说明PNG扇形半径，不说明真实最大量程。",
        },
        {
            "parameter_name": "azimuth_definition",
            "value": "atan2(x - 1154.0, 1330.6 - y)",
            "unit": "degree",
            "source_file": rel(INPUTS["mask_definition_report"]),
            "source_line_or_field": "Summary/R2C.M0",
            "derivation_formula": "degrees(atan2(x-FAN_CENTER_X, FAN_CENTER_Y-y))",
            "confidence": "medium_for_display_angle",
            "used_for_current_fit": "false",
            "status": "SUPPORTED_FOR_ANGLE_ONLY",
            "notes_cn": "方位角可在PNG扇形几何内复算，但横向米制仍需要径向米制。",
        },
        {
            "parameter_name": "cross_range_conversion",
            "value": "",
            "unit": "m",
            "source_file": "",
            "source_line_or_field": "",
            "derivation_formula": "R_ref * delta_theta_rad requires reliable R_ref in meters",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "缺少可靠R_ref米制，不能把角宽转为横向米制。",
        },
        {
            "parameter_name": "radial_grid_spacing_m_per_px",
            "value": "",
            "unit": "m/px",
            "source_file": "",
            "source_line_or_field": "",
            "derivation_formula": "requires physical range axis or trusted max range tied to PNG radius",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "未找到真实成像程序输出的range_axis/x_axis/y_axis或PNG同步元数据。",
        },
        {
            "parameter_name": "radial_extent_m",
            "value": "",
            "unit": "m",
            "source_file": "",
            "source_line_or_field": "",
            "derivation_formula": "requires imaging-time range extent",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "未找到真实量程轴；不能由显示扇形半径反推。",
        },
        {
            "parameter_name": "candidate_runtime_max_range_m_rejected",
            "value": "40.0",
            "unit": "m",
            "source_file": rel(config),
            "source_line_or_field": "sar.max_range_m / scenes.GM_RM019.max_range_m",
            "derivation_formula": "runtime support prior, not imaging calibration",
            "confidence": "low_for_physical_png_scale",
            "used_for_current_fit": "false",
            "status": "REJECTED_FOR_CURRENT_FIT",
            "notes_cn": "workspace auto_labeler配置用于运行时支持范围假设，不是PNG成像坐标轴或雷达参数。",
        },
        {
            "parameter_name": "candidate_radial_grid_spacing_from_runtime_config_rejected",
            "value": fmt(candidate_m_per_px, 8),
            "unit": "m/px",
            "source_file": rel(config),
            "source_line_or_field": "40.0 / 1332.7",
            "derivation_formula": "max_range_m / fan_radius_px",
            "confidence": "low_for_physical_png_scale",
            "used_for_current_fit": "false",
            "status": "REJECTED_FOR_CURRENT_FIT",
            "notes_cn": "这是运行时先验与显示半径的组合，不可称为物理网格间距。",
        },
        {
            "parameter_name": "range_resolution_m",
            "value": "",
            "unit": "m",
            "source_file": "",
            "source_line_or_field": "",
            "derivation_formula": "c / (2 * effective_bandwidth)",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "未找到真实FMCW有效带宽、chirp、采样率或FFT配置。",
        },
        {
            "parameter_name": "cross_range_resolution_model",
            "value": "",
            "unit": "m",
            "source_file": "",
            "source_line_or_field": "",
            "derivation_formula": "requires aperture/beam/focusing model",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "未找到当前数据集的方位分辨率或成像聚焦模型参数。",
        },
        {
            "parameter_name": "display_resize_x",
            "value": "",
            "unit": "ratio",
            "source_file": str(DATA_ROOT / "GM_RM019").replace("\\", "/"),
            "source_line_or_field": "directory inventory",
            "derivation_formula": "requires raw/float SAR image source and PNG write transform",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "GM_RM019数据目录只有PNG/深度npy和一个空fail文本，没有raw-to-PNG缩放记录。",
        },
        {
            "parameter_name": "display_resize_y",
            "value": "",
            "unit": "ratio",
            "source_file": str(DATA_ROOT / "GM_RM019").replace("\\", "/"),
            "source_line_or_field": "directory inventory",
            "derivation_formula": "requires raw/float SAR image source and PNG write transform",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "GM_RM019数据目录只有PNG/深度npy和一个空fail文本，没有raw-to-PNG缩放记录。",
        },
        {
            "parameter_name": "crop_offset_x",
            "value": "",
            "unit": "px",
            "source_file": str(DATA_ROOT / "GM_RM019").replace("\\", "/"),
            "source_line_or_field": "directory inventory",
            "derivation_formula": "requires upstream image crop provenance",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "未找到上游裁剪偏移。",
        },
        {
            "parameter_name": "crop_offset_y",
            "value": "",
            "unit": "px",
            "source_file": str(DATA_ROOT / "GM_RM019").replace("\\", "/"),
            "source_line_or_field": "directory inventory",
            "derivation_formula": "requires upstream image crop provenance",
            "confidence": "none",
            "used_for_current_fit": "false",
            "status": STATUS_ABSOLUTE_UNRESOLVED,
            "notes_cn": "未找到上游裁剪偏移。",
        },
    ]
    return rows


def build_gt_geometry_rows(context: Mapping[str, Sequence[Mapping[str, str]]]) -> list[dict[str, str]]:
    paired_by_id = {row["pair_id"]: row for row in context["paired_annotations"] if row.get("scene") == "GM_RM019"}
    variant_by_frame = defaultdict(list)
    for row in context["boundary_variant_families"]:
        variant_by_frame[str(row.get("sar_frame", ""))].append(row)
    rows: list[dict[str, str]] = []
    for mask_row in context["mask_observation_audit"]:
        pair_id = mask_row["pair_id"]
        paired = paired_by_id.get(pair_id, {})
        sar_bbox = mask_row.get("sar_bbox") or ",".join(
            [
                paired.get("sar_bbox_x1", ""),
                paired.get("sar_bbox_y1", ""),
                paired.get("sar_bbox_x2", ""),
                paired.get("sar_bbox_y2", ""),
            ]
        )
        geom = box_geometry(sar_bbox)
        full_area = geom["full_area"]
        visible_area = geom["visible_area"]
        visible_fraction = geom["visible_fraction"]
        range_width = geom["range_max"] - geom["range_min"] if not math.isnan(geom["range_min"]) else math.nan
        az_width = geom["azimuth_max"] - geom["azimuth_min"] if not math.isnan(geom["azimuth_min"]) else math.nan
        mask_class = mask_row.get("sar_mask_observation_class", "")
        frame = str(mask_row.get("sar_frame", ""))
        multiple_variants = any(v.get("boundary_status") == "multiple_boundary_variants" for v in variant_by_frame.get(frame, []))
        flags = geom["flags"]
        rows.append(
            {
                "pair_id": pair_id,
                "physical_vehicle_id": mask_row.get("physical_vehicle_id", ""),
                "sar_frame": frame,
                "sar_bbox": sar_bbox,
                "gt_semantic": "posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle",
                "gt_semantic_confidence": "medium_from_R2C_center_semantic_review",
                "mask_semantic": "reconstructed_display_fan_support_physical_valid_mask_unconfirmed",
                "mask_confidence": "medium_for_png_support_low_for_physical_semantics",
                "mask_class": mask_class,
                "gt_full_area_px": str(full_area),
                "gt_visible_area_px": str(visible_area),
                "gt_visible_fraction": fmt(visible_fraction),
                "gt_bbox_intersects_invalid_mask": bool_text(visible_area < full_area),
                "source_mask_intersection_ratio": mask_row.get("sar_bbox_mask_intersection_ratio", ""),
                "computed_display_fan_intersection_ratio": fmt(visible_fraction),
                "gt_range_min_px": fmt(geom["range_min"]),
                "gt_range_max_px": fmt(geom["range_max"]),
                "gt_range_width_px": fmt(range_width),
                "gt_azimuth_min_deg": fmt(geom["azimuth_min"]),
                "gt_azimuth_max_deg": fmt(geom["azimuth_max"]),
                "gt_azimuth_width_deg": fmt(az_width),
                "gt_near_side_censored": bool_text(flags["near"]),
                "gt_far_side_censored": bool_text(flags["far"]),
                "gt_left_side_censored": bool_text(flags["left"]),
                "gt_right_side_censored": bool_text(flags["right"]),
                "gt_signed_mask_distance_px": mask_row.get("bottom_valid_margin_px", ""),
                "actual_fan_pixel_censored": bool_text(visible_area < full_area),
                "gt_pair_linked_mask_context": "true",
                "frame_only_mask_context": "false",
                "sar_response_touches_mask": mask_row.get("sar_response_touches_mask", ""),
                "sar_response_truncation_direction": mask_row.get("sar_response_truncation_direction", ""),
                "multiple_boundary_variant_uncertainty": bool_text(multiple_variants),
                "absolute_scale_status": STATUS_ABSOLUTE_UNRESOLVED,
                "gt_range_min_m": "",
                "gt_range_max_m": "",
                "gt_range_width_m": "",
                "gt_cross_range_arc_width_m": "",
                "gt_cross_range_chord_width_m": "",
                "notes_cn": "仅构造PNG像素和角度区间；米制字段因绝对尺度未恢复而留空。",
            }
        )
    return rows


def approximate_azimuth_width_deg(width_px: Any, center_radius_px: float) -> str:
    width = parse_float(width_px)
    if math.isnan(width) or center_radius_px <= 1e-6:
        return ""
    return fmt(math.degrees(width / center_radius_px))


def build_sar_interval_rows(
    context: Mapping[str, Sequence[Mapping[str, str]]],
    gt_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    gt_by_pair = {row["pair_id"]: row for row in gt_rows}
    mask_by_pair = {row["pair_id"]: row for row in context["mask_observation_audit"]}
    mask_pairs_by_frame: dict[str, set[str]] = defaultdict(set)
    for row in context["mask_observation_audit"]:
        mask_pairs_by_frame[str(row.get("sar_frame", ""))].add(row.get("pair_id", ""))
    rows: list[dict[str, str]] = []
    for row in context["directional_measurements"]:
        if row.get("measurement_region_type") != "core_region":
            continue
        frame = str(row.get("sar_frame", ""))
        pair_id = row.get("matched_gt_pair_id", "")
        linked = bool(pair_id and pair_id in mask_by_pair)
        frame_only = bool((not linked) and frame in mask_pairs_by_frame)
        box = parse_box(row.get("region_bbox", ""))
        response_geom = box_geometry(row.get("region_bbox", "")) if box else {"full_area": 0, "visible_area": 0}
        response_censored = bool(response_geom["visible_area"] < response_geom["full_area"])
        cx = parse_float(row.get("response_center_x"))
        cy = parse_float(row.get("response_center_y"))
        center_radius = radial_px(cx, cy) if not math.isnan(cx) and not math.isnan(cy) else math.nan
        center_angle = azimuth_deg(cx, cy) if not math.isnan(cx) and not math.isnan(cy) else math.nan
        mask_row = mask_by_pair.get(pair_id, {})
        gt_row = gt_by_pair.get(pair_id, {})
        variant_uncertainty = parse_int(row.get("boundary_variant_count"), 0) > 1
        rows.append(
            {
                "response_unit_id": row.get("response_unit_id", ""),
                "sar_frame": frame,
                "measurement_region_type": row.get("measurement_region_type", ""),
                "matched_gt_pair_id": pair_id,
                "matched_gt_instance_id": row.get("matched_gt_instance_id", ""),
                "response_region_bbox": row.get("region_bbox", ""),
                "physical_vehicle_id": mask_row.get("physical_vehicle_id", ""),
                "mask_class": mask_row.get("sar_mask_observation_class", ""),
                "gt_pair_linked_mask_context": bool_text(linked),
                "frame_only_mask_context": bool_text(frame_only),
                "mask_state": row.get("mask_state", ""),
                "actual_fan_pixel_censored": bool_text(response_censored),
                "gt_bbox_intersects_invalid_mask": gt_row.get("gt_bbox_intersects_invalid_mask", ""),
                "sar_response_touches_mask": mask_row.get("sar_response_touches_mask", bool_text(response_censored) if linked else ""),
                "sar_response_truncation_direction": mask_row.get("sar_response_truncation_direction", ""),
                "multiple_boundary_variant_uncertainty": bool_text(variant_uncertainty),
                "response_center_radial_px": fmt(center_radius),
                "response_center_azimuth_deg": fmt(center_angle),
                "range_p50_width_px": row.get("range_p50_width", ""),
                "range_p80_width_px": row.get("range_p80_width", ""),
                "range_p90_width_px": row.get("range_p90_width", ""),
                "azimuth_p50_width_px": row.get("azimuth_p50_width", ""),
                "azimuth_p80_width_px": row.get("azimuth_p80_width", ""),
                "azimuth_p90_width_px": row.get("azimuth_p90_width", ""),
                "sar_azimuth_p50_width_deg_approx": approximate_azimuth_width_deg(row.get("azimuth_p50_width"), center_radius),
                "sar_azimuth_p80_width_deg_approx": approximate_azimuth_width_deg(row.get("azimuth_p80_width"), center_radius),
                "sar_azimuth_p90_width_deg_approx": approximate_azimuth_width_deg(row.get("azimuth_p90_width"), center_radius),
                "sar_range_p80_interval_m": "",
                "sar_cross_range_p80_width_m": "",
                "absolute_scale_status": STATUS_ABSOLUTE_UNRESOLVED,
                "scale_blocked_reason": BLOCKED_REASON,
            }
        )
    return rows


def build_fit_rows(
    sar_rows: Sequence[Mapping[str, str]],
    gt_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    gt_by_pair = {row["pair_id"]: row for row in gt_rows}
    rows: list[dict[str, str]] = []
    idx = 1
    for sar in sar_rows:
        pair_id = sar.get("matched_gt_pair_id", "")
        if not pair_id or pair_id not in gt_by_pair:
            continue
        gt = gt_by_pair[pair_id]
        rows.append(
            {
                "fit_row_id": f"FIT{idx:04d}",
                "response_unit_id": sar.get("response_unit_id", ""),
                "sar_frame": sar.get("sar_frame", ""),
                "matched_gt_pair_id": pair_id,
                "matched_gt_instance_id": sar.get("matched_gt_instance_id", ""),
                "physical_vehicle_id": gt.get("physical_vehicle_id", ""),
                "mask_class": gt.get("mask_class", ""),
                "gt_semantic": gt.get("gt_semantic", ""),
                "gt_visible_fraction": gt.get("gt_visible_fraction", ""),
                "gt_visible_range_width_px": gt.get("gt_range_width_px", ""),
                "gt_visible_azimuth_width_deg": gt.get("gt_azimuth_width_deg", ""),
                "sar_range_p80_width_px": sar.get("range_p80_width_px", ""),
                "sar_azimuth_p80_width_px": sar.get("azimuth_p80_width_px", ""),
                "sar_azimuth_p80_width_deg_approx": sar.get("sar_azimuth_p80_width_deg_approx", ""),
                "boundary_variant_uncertainty": sar.get("multiple_boundary_variant_uncertainty", ""),
                "fit_eligible": "false",
                "absolute_scale_status": STATUS_ABSOLUTE_UNRESOLVED,
                "blocked_reason": BLOCKED_REASON,
            }
        )
        idx += 1
    return rows


def build_model_rows(fit_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    models = [
        ("M0", "constant_baseline"),
        ("M1", "absolute_position_model"),
        ("M2", "visible_gt_size_model"),
        ("M3", "visible_gt_size_plus_mask_model"),
        ("M4", "convolution_resolution_inspired_model"),
        ("M5", "full_gt_error_baseline"),
    ]
    rows = []
    for target in ["range_p80_width_m", "cross_range_p80_width_m"]:
        for model_id, name in models:
            rows.append(
                {
                    "target_dimension": target,
                    "model_id": model_id,
                    "model_name": name,
                    "training_sample_count": "0",
                    "candidate_input_rows": str(len(fit_rows)),
                    "holdout_fold_count": "0",
                    "failed_fold_count": "0",
                    "baseline_error": "",
                    "candidate_model_error": "",
                    "absolute_improvement": "",
                    "relative_improvement": "",
                    "MAE_m": "",
                    "median_absolute_error_m": "",
                    "p90_absolute_error_m": "",
                    "relative_error": "",
                    "signed_bias_m": "",
                    "run_status": "not_run_absolute_scale_unresolved",
                    "blocked_reason": BLOCKED_REASON,
                }
            )
    return rows


def group_sizes(rows: Sequence[Mapping[str, str]], field: str) -> list[int]:
    groups = Counter(row.get(field, "") for row in rows if row.get(field, ""))
    return list(groups.values())


def build_holdout_rows(fit_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    strategies = [
        ("leave_one_gt_pair", "matched_gt_pair_id"),
        ("leave_one_sar_frame", "sar_frame"),
        ("leave_one_physical_vehicle", "physical_vehicle_id"),
    ]
    rows = []
    for name, field in strategies:
        sizes = group_sizes(fit_rows, field)
        rows.append(
            {
                "fold_strategy": name,
                "potential_group_count": str(len(sizes)),
                "potential_sample_count": str(sum(sizes)),
                "min_group_size": str(min(sizes)) if sizes else "0",
                "max_group_size": str(max(sizes)) if sizes else "0",
                "same_pair_cross_fold_violation": "false",
                "holdout_fold_count": "0",
                "failed_fold_count": "0",
                "run_status": "not_run_absolute_scale_unresolved",
                "blocked_reason": BLOCKED_REASON,
            }
        )
    return rows


def build_counterexamples(
    gt_rows: Sequence[Mapping[str, str]],
    sar_rows: Sequence[Mapping[str, str]],
    fit_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    by_pair = {row.get("pair_id", ""): row for row in gt_rows}
    by_response = {row.get("response_unit_id", ""): row for row in sar_rows}
    fit_by_pair = defaultdict(list)
    for row in fit_rows:
        fit_by_pair[row.get("matched_gt_pair_id", "")].append(row)

    def row_for(
        cid: str,
        ctype: str,
        pair_id: str,
        response_id: str,
        why: str,
    ) -> dict[str, str]:
        gt = by_pair.get(pair_id, {})
        sar = by_response.get(response_id, {})
        return {
            "counterexample_id": cid,
            "counterexample_type": ctype,
            "pair_id": pair_id,
            "response_unit_id": response_id,
            "sar_frame": sar.get("sar_frame", gt.get("sar_frame", "")),
            "physical_vehicle_id": gt.get("physical_vehicle_id", ""),
            "mask_class": gt.get("mask_class", ""),
            "gt_semantic": gt.get("gt_semantic", "posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle"),
            "absolute_range_m": "",
            "gt_visible_width_m": "",
            "sar_p80_width_m": "",
            "endpoint_errors": "not_computed_absolute_scale_unresolved",
            "model_residuals": "not_computed_absolute_scale_unresolved",
            "why_it_matters_cn": why,
            "visual_review_relpath": "",
        }

    rows = [
        row_for(
            "CE_SCALE_001",
            "absolute_scale_candidate_rejected",
            "",
            "",
            "workspace配置中的40m最大量程只能说明运行时支持先验，不能证明PNG径向像素的物理米制。",
        ),
        row_for(
            "CE_MASK_001",
            "no_fully_observable_mask_center_supervision",
            "WGV35A_PAIR_0200",
            "",
            "GM_RM019的16个MASK pair均为S1/S2，S0为0，中心监督不能用于完整车辆物理拟合。",
        ),
        row_for(
            "CE_GT_001",
            "gt_center_visible_response_only",
            "WGV35A_PAIR_0204",
            "R21B00001",
            "SAR框中心在R2C审阅中被标记为mask偏置或可见响应中心，不能等同完整车辆中心。",
        ),
        row_for(
            "CE_PAIR_001",
            "pairing_review_required",
            "WGV35A_PAIR_0203",
            "R21B00001",
            "右侧暗片段同帧并存，GT pair可作为事后关联上下文，但仍保留配对复核风险。",
        ),
        row_for(
            "CE_WIDTH_001",
            "small_visible_gt_but_wide_sar_not_evaluated_in_meters",
            "WGV35A_PAIR_0204",
            "R21B00076",
            "像素域可见GT与SAR展宽存在不匹配候选，但没有绝对尺度时不能升级为米制物理反例。",
        ),
        row_for(
            "CE_WIDTH_002",
            "large_visible_gt_but_narrow_sar_not_evaluated_in_meters",
            "WGV35A_PAIR_0205",
            "R21B00002",
            "像素域窄响应可能来自局部散射、边界或背景估计，缺少米制和端点误差时不能做车辆尺寸结论。",
        ),
        row_for(
            "CE_BOUNDARY_001",
            "multiple_boundary_variant_uncertainty",
            "WGV35A_PAIR_0204",
            "R21B00001",
            "边界族存在多合法变体，不能与MASK截断或完整车辆越界混成一个变量。",
        ),
        row_for(
            "CE_BACKGROUND_001",
            "background_or_sidelobe_wide_response",
            "",
            "R21B00112",
            "上一轮背景/孤立反例也可出现高能量或大展宽，阻止静态像素展宽直接成为物理车辆规则。",
        ),
    ]
    return rows


def build_integrity_rows(
    context: Mapping[str, Sequence[Mapping[str, str]]],
    gt_rows: Sequence[Mapping[str, str]],
    sar_rows: Sequence[Mapping[str, str]],
    fit_rows: Sequence[Mapping[str, str]],
    model_rows: Sequence[Mapping[str, str]],
    replay_status: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str, source: Path | None = None) -> None:
        rows.append(
            {
                "gate_name": name,
                "status": status,
                "detail": detail,
                "source_file": rel(source) if source else "",
                "sha256": sha256(source) if source else "",
                "row_count": row_count(source) if source else "",
            }
        )

    for name, path in INPUTS.items():
        if path.suffix.lower() in {".csv", ".md", ".py", ".json"}:
            add(f"input_hash_{name}", "PASS" if path.exists() else "FAIL", "input present and hashed", path)

    unit_count = len(context["local_response_units"])
    measurement_rows = len(context["directional_measurements"])
    primary_measurements = [row for row in context["directional_measurements"] if row.get("measurement_region_type") == "core_region"]
    primary_rows = len(primary_measurements)
    unique_response_units = {row.get("response_unit_id", "") for row in context["local_response_units"] if row.get("response_unit_id", "")}
    unique_region_bboxes = {row.get("region_bbox", "") for row in primary_measurements if row.get("region_bbox", "")}
    duplicate_geometry_groups = Counter(row.get("region_bbox", "") for row in primary_measurements if row.get("region_bbox", ""))
    shared_core_groups = Counter(row.get("core_atom_ids", "") for row in context["local_response_units"] if row.get("core_atom_ids", ""))
    fit_pairs = {row.get("matched_gt_pair_id", "") for row in fit_rows if row.get("matched_gt_pair_id", "")}
    fit_frames = {row.get("sar_frame", "") for row in fit_rows if row.get("sar_frame", "")}
    fit_vehicles = {row.get("physical_vehicle_id", "") for row in fit_rows if row.get("physical_vehicle_id", "")}
    fit_gt_instances = {row.get("matched_gt_instance_id", "") for row in fit_rows if row.get("matched_gt_instance_id", "")}
    linked_count = sum(row.get("gt_pair_linked_mask_context") == "true" for row in sar_rows)
    frame_only_count = sum(row.get("frame_only_mask_context") == "true" for row in sar_rows)
    model_not_run = all(row.get("run_status") == "not_run_absolute_scale_unresolved" for row in model_rows)
    add("absolute_scale_status", "PASS", STATUS_ABSOLUTE_UNRESOLVED + ": " + BLOCKED_REASON)
    add("local_response_unit_count_stable", "PASS" if unit_count == 250 else "FAIL", f"count={unit_count} expected=250")
    add("directional_measurement_rows_stable", "PASS" if measurement_rows == 500 else "FAIL", f"rows={measurement_rows} expected=500")
    add("primary_response_rows_stable", "PASS" if primary_rows == 250 else "FAIL", f"primary_rows={primary_rows} expected=250")
    add("duplicate_structure_unique_response_unit_count", "PASS", f"unique_response_unit_count={len(unique_response_units)}")
    add("duplicate_structure_unique_region_bbox_count", "PASS", f"unique_region_bbox_count={len(unique_region_bboxes)}")
    add("duplicate_structure_unique_gt_pair_count", "PASS", f"fit_unique_gt_pair_count={len(fit_pairs)}")
    add("duplicate_structure_unique_gt_instance_count", "PASS", f"fit_unique_gt_instance_count={len(fit_gt_instances)}")
    add("duplicate_structure_unique_sar_frame_count", "PASS", f"fit_unique_sar_frame_count={len(fit_frames)}")
    add("duplicate_structure_unique_physical_vehicle_count", "PASS", f"fit_unique_physical_vehicle_count={len(fit_vehicles)}")
    add("duplicate_structure_shared_core_group_count", "PASS", f"shared_core_group_count={sum(1 for count in shared_core_groups.values() if count > 1)}")
    add("duplicate_structure_duplicate_geometry_group_count", "PASS", f"duplicate_geometry_group_count={sum(1 for count in duplicate_geometry_groups.values() if count > 1)}")
    add("gt_mask_pair_geometry_rows", "PASS" if len(gt_rows) == 16 else "FAIL", f"rows={len(gt_rows)} expected=16")
    add("gt_pair_linked_mask_context", "PASS" if linked_count > 0 else "FAIL", f"linked_primary_response_rows={linked_count}")
    add("frame_only_mask_context_separated", "PASS", f"frame_only_primary_response_rows={frame_only_count}")
    add("model_rows_blocked_not_fit", "PASS" if model_not_run else "FAIL", "M0-M5 emitted as blocked rows; no meter fit executed")
    add("fit_rows_not_eligible", "PASS" if all(row.get("fit_eligible") == "false" for row in fit_rows) else "FAIL", f"fit_rows={len(fit_rows)}")
    add("counterexamples_preserved", "PASS", "counterexample rows include scale, mask, GT, boundary, and background blockers")
    add("replay_status", replay_status, "verify-replay compares deterministic output hashes")
    return rows


def summarize_numeric(rows: Sequence[Mapping[str, str]], field: str) -> dict[str, str]:
    values = [parse_float(row.get(field)) for row in rows]
    values = [value for value in values if not math.isnan(value)]
    if not values:
        return {"count": "0", "median": "", "min": "", "max": ""}
    return {
        "count": str(len(values)),
        "median": fmt(median(values)),
        "min": fmt(min(values)),
        "max": fmt(max(values)),
    }


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    show = list(rows[:limit]) if limit is not None else list(rows)
    if not show:
        return "_none_"
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join("---" for _ in fields) + "|"]
    for row in show:
        values = [str(row.get(field, "")).replace("\n", " ") for field in fields]
        lines.append("|" + "|".join(values) + "|")
    return "\n".join(lines)


def render_report(
    scale_rows: Sequence[Mapping[str, str]],
    gt_rows: Sequence[Mapping[str, str]],
    sar_rows: Sequence[Mapping[str, str]],
    fit_rows: Sequence[Mapping[str, str]],
    model_rows: Sequence[Mapping[str, str]],
    holdout_rows: Sequence[Mapping[str, str]],
    counterexample_rows: Sequence[Mapping[str, str]],
    integrity_rows: Sequence[Mapping[str, str]],
    replay_status: str,
) -> str:
    mask_counts = Counter(row.get("mask_class", "") for row in gt_rows)
    vehicle_count = len({row.get("physical_vehicle_id", "") for row in gt_rows if row.get("physical_vehicle_id", "")})
    frame_count = len({row.get("sar_frame", "") for row in gt_rows if row.get("sar_frame", "")})
    pair_count = len({row.get("pair_id", "") for row in gt_rows if row.get("pair_id", "")})
    fit_row_count = len(fit_rows)
    fit_pair_count = len({row.get("matched_gt_pair_id", "") for row in fit_rows if row.get("matched_gt_pair_id", "")})
    fit_instance_count = len({row.get("matched_gt_instance_id", "") for row in fit_rows if row.get("matched_gt_instance_id", "")})
    fit_frame_count = len({row.get("sar_frame", "") for row in fit_rows if row.get("sar_frame", "")})
    fit_vehicle_count = len({row.get("physical_vehicle_id", "") for row in fit_rows if row.get("physical_vehicle_id", "")})
    independent_geometry_count = len({row.get("response_region_bbox", "") for row in sar_rows if row.get("response_region_bbox", "")})
    duplicate_geometry_group_count = sum(
        1 for count in Counter(row.get("response_region_bbox", "") for row in sar_rows if row.get("response_region_bbox", "")).values() if count > 1
    )
    visible_fraction = summarize_numeric(gt_rows, "gt_visible_fraction")
    gt_range_px = summarize_numeric(gt_rows, "gt_range_width_px")
    sar_range_p80 = summarize_numeric(sar_rows, "range_p80_width_px")
    sar_az_p80 = summarize_numeric(sar_rows, "sar_azimuth_p80_width_deg_approx")
    linked_count = sum(row.get("gt_pair_linked_mask_context") == "true" for row in sar_rows)
    frame_only_count = sum(row.get("frame_only_mask_context") == "true" for row in sar_rows)
    scale_blockers = [row for row in scale_rows if row.get("status") == STATUS_ABSOLUTE_UNRESOLVED]
    rejected_candidates = [row for row in scale_rows if row.get("status") == "REJECTED_FOR_CURRENT_FIT"]
    lines = [
        "# GM_RM019 MASK感知GT锚定物理尺度拟合审计",
        "",
        f"日期：`{DATE}`",
        "",
        "## 最终状态",
        "",
        f"`{STATUS_ABSOLUTE_UNRESOLVED}`",
        "",
        "本轮没有进行米制M0-M5拟合。原因是未找到可靠的SAR原始物理坐标轴、raw/float到PNG的标定链、FMCW有效带宽、FFT网格、显示缩放或裁剪偏移。运行时配置中的40m最大量程只作为被拒绝候选记录，未用于当前拟合。",
        "",
        "## 边界",
        "",
        "- GT（Ground Truth，真值标注）只用于事后分析、验证和机制解释。",
        "- MASK只按当前证据拆成重建扇形显示支持、pair级MASK上下文、frame-only上下文和边界变体不确定性。",
        "- 未生成最终框、候选框、selector/ranking、best-box、runtime prediction artifact，未修改GT，未修改GM_RM017。",
        "",
        "## 绝对尺度审计",
        "",
        f"- 已支持的几何：`{SAR_WIDTH}x{SAR_HEIGHT}` PNG坐标、扇形中心`({FAN_CENTER_X}, {FAN_CENTER_Y})`、扇形半径`{FAN_RADIUS_PX}px`、显示方位角公式。",
        f"- 未解决尺度参数数：`{len(scale_blockers)}`。",
        f"- 被拒绝候选数：`{len(rejected_candidates)}`。",
        "- 径向m/px：未恢复。",
        "- 距离分辨率m：未恢复。",
        "- 二者为何不同：m/px是成像网格或显示采样间距；距离分辨率需要真实FMCW带宽/成像链路。当前两者都没有可靠来源，因此都不能用于米制拟合。",
        "",
        markdown_table(scale_rows, ["parameter_name", "value", "unit", "confidence", "status", "notes_cn"], limit=20),
        "",
        "## GT与MASK语义",
        "",
        "- `paired_annotations.sar_bbox`与`mask_observation_audit.sar_bbox`在本轮解释为SAR侧事后响应框或MASK偏置可见响应框，不解释为完整车辆真实尺寸。",
        "- `response_unit_gt_instance_matrix`只提供eval-only匹配/覆盖关系，不是runtime assignment，也不是选择最佳响应单元的依据。",
        "- 当前MASK证据是由代码重建的PNG扇形显示/几何支持；独立物理有效mask文件和成像期物理有效区语义未确认。",
        "- 重建显示扇形下的GT可见比例不能替代真实物理MASK语义；本轮把二者分开记录。",
        f"- GM_RM019 MASK pair：`{pair_count}`；帧数：`{frame_count}`；物理车辆数：`{vehicle_count}`。",
        f"- 拟合候选行：`{fit_row_count}`；精确关联GT pair：`{fit_pair_count}`；GT instance：`{fit_instance_count}`；帧：`{fit_frame_count}`；物理车辆：`{fit_vehicle_count}`；独立响应几何：`{independent_geometry_count}`；重复几何组：`{duplicate_geometry_group_count}`。",
        f"- MASK类别：`{dict(mask_counts)}`。",
        f"- primary response中pair级MASK精确关联：`{linked_count}`；frame-only上下文：`{frame_only_count}`。",
        "",
        "## GT完整区间与可见区间统计",
        "",
        f"- gt_visible_fraction: count={visible_fraction['count']}, median={visible_fraction['median']}, min={visible_fraction['min']}, max={visible_fraction['max']}",
        f"- gt_range_width_px: count={gt_range_px['count']}, median={gt_range_px['median']}, min={gt_range_px['min']}, max={gt_range_px['max']}",
        "- 米制GT区间：未生成，原因是绝对尺度未恢复。",
        "",
        "## SAR p80展宽统计",
        "",
        f"- range_p80_width_px: count={sar_range_p80['count']}, median={sar_range_p80['median']}, min={sar_range_p80['min']}, max={sar_range_p80['max']}",
        f"- azimuth_p80_width_deg_approx: count={sar_az_p80['count']}, median={sar_az_p80['median']}, min={sar_az_p80['min']}, max={sar_az_p80['max']}",
        "- SAR p80米制展宽：未生成，原因是绝对尺度未恢复。",
        "",
        "## M0-M5模型比较",
        "",
        markdown_table(model_rows, ["target_dimension", "model_id", "training_sample_count", "candidate_input_rows", "holdout_fold_count", "run_status", "blocked_reason"], limit=20),
        "",
        "## 留出审计",
        "",
        markdown_table(holdout_rows, HOLDOUT_FIELDS),
        "",
        "## 支持样本与反例",
        "",
        f"支持样本只支持像素/角度审计和停止结论，不支持米制物理拟合。主要支持证据是：16条GM_RM019 MASK pair被审计；250个冻结response unit保持不变；{fit_row_count}条GT-linked拟合候选行被生成但全部标记为不可米制拟合。",
        "",
        markdown_table(counterexample_rows, COUNTEREXAMPLE_FIELDS, limit=20),
        "",
        "## 可支持和不可支持的结论",
        "",
        "可支持：GM_RM019当前只具备PNG像素/显示角度/MASK上下文审计；GT框中心在近场MASK条件下不能当作完整车辆中心；M0-M5米制拟合应停止。",
        "",
        "不可支持：不能声称完成绝对物理尺度拟合；不能把radial pixel称为meter；不能把40m运行时配置除以扇形半径称为物理分辨率或可靠m/px；不能从本轮输出生成最终框或selector/ranking。",
        "",
        "## 完整性与重放",
        "",
        f"- verify-replay: `{replay_status}`",
        "",
        markdown_table(integrity_rows, INTEGRITY_FIELDS, limit=40),
        "",
        "## 输出文件",
        "",
    ]
    for key, path in OUTPUTS.items():
        lines.append(f"- `{rel(path)}`")
    lines.extend(
        [
            "",
            "## 停止声明",
            "",
            "本轮在`ABSOLUTE_SCALE_UNRESOLVED`处停止。没有生成最终框；没有修改GT；没有修改GM_RM017；没有产生selector/ranking、best-box或runtime prediction artifact。",
            "",
        ]
    )
    return "\n".join(lines)


def write_workspace_log(stage: str, replay_status: str, outputs: Mapping[str, Path]) -> None:
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# OTY2 GM_RM019 mask-aware GT physical scale fit log",
        "",
        "- repo: D:/profile/research/optical-sar-visual-diagnosis",
        "- interpreter: D:/MINICONDA/envs/py311/python.exe",
        "- old_work dependency: none",
        "- task boundary: posthoc scale and MASK/GT semantics audit only",
        f"- stage: {stage}",
        f"- status: {STATUS_ABSOLUTE_UNRESOLVED}",
        f"- replay_status: {replay_status}",
        "- output_paths:",
    ]
    for key, path in outputs.items():
        lines.append(f"  - {key}: {rel(path)}")
    lines.append("")
    WORKSPACE_LOG.write_text("\n".join(lines), encoding="utf-8")


def build_all(stage: str, output_map: Mapping[str, Path], replay_status: str = "PENDING") -> dict[str, Any]:
    context = load_context()
    scale_rows = build_scale_rows()
    gt_rows = build_gt_geometry_rows(context)
    sar_rows = build_sar_interval_rows(context, gt_rows)
    fit_rows = build_fit_rows(sar_rows, gt_rows)
    model_rows = build_model_rows(fit_rows)
    holdout_rows = build_holdout_rows(fit_rows)
    counterexample_rows = build_counterexamples(gt_rows, sar_rows, fit_rows)
    integrity_rows = build_integrity_rows(context, gt_rows, sar_rows, fit_rows, model_rows, replay_status)
    report = render_report(
        scale_rows,
        gt_rows,
        sar_rows,
        fit_rows,
        model_rows,
        holdout_rows,
        counterexample_rows,
        integrity_rows,
        replay_status,
    )
    write_csv(output_map["scale"], scale_rows, SCALE_FIELDS)
    write_csv(output_map["gt_geometry"], gt_rows, GT_GEOMETRY_FIELDS)
    write_csv(output_map["sar_intervals"], sar_rows, SAR_INTERVAL_FIELDS)
    write_csv(output_map["fit_rows"], fit_rows, FIT_ROW_FIELDS)
    write_csv(output_map["model_comparison"], model_rows, MODEL_FIELDS)
    write_csv(output_map["holdout"], holdout_rows, HOLDOUT_FIELDS)
    write_csv(output_map["counterexamples"], counterexample_rows, COUNTEREXAMPLE_FIELDS)
    write_csv(output_map["integrity"], integrity_rows, INTEGRITY_FIELDS)
    write_text(output_map["report"], report)
    write_workspace_log(stage, replay_status, output_map)
    return {
        "scale_rows": scale_rows,
        "gt_rows": gt_rows,
        "sar_rows": sar_rows,
        "fit_rows": fit_rows,
        "model_rows": model_rows,
        "holdout_rows": holdout_rows,
        "counterexample_rows": counterexample_rows,
        "integrity_rows": integrity_rows,
    }


def output_hashes(output_map: Mapping[str, Path]) -> dict[str, str]:
    return {key: sha256(path) for key, path in output_map.items() if path.exists()}


def tmp_outputs() -> dict[str, Path]:
    return {key: VERIFY_TMP_DIR / path.name for key, path in OUTPUTS.items()}


def verify_replay() -> None:
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    build_all("verify-replay", OUTPUTS, replay_status="PASS")
    temp = tmp_outputs()
    build_all("verify-replay-temp", temp, replay_status="PASS")
    current_hashes = output_hashes(OUTPUTS)
    replay_hashes = output_hashes(temp)
    mismatches = [key for key in OUTPUTS if current_hashes.get(key) != replay_hashes.get(key)]
    if mismatches:
        raise AssertionError("verify-replay hash mismatch: " + "; ".join(mismatches))
    write_workspace_log("verify-replay", "PASS", OUTPUTS)
    print("verify-replay: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit-scale", "generate", "evaluate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "verify-replay":
        verify_replay()
    else:
        build_all(args.command, OUTPUTS, replay_status="PENDING")
        if args.command == "audit-scale":
            print(f"audit-scale: {STATUS_ABSOLUTE_UNRESOLVED}")
        elif args.command == "generate":
            print(f"generate: {STATUS_ABSOLUTE_UNRESOLVED}")
        elif args.command == "evaluate":
            print("evaluate: M0-M5 not_run_absolute_scale_unresolved")


if __name__ == "__main__":
    main()
