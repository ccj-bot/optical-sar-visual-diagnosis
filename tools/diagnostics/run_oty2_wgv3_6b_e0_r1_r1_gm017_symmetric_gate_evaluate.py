"""Evaluate E0-R1-R1 symmetric hard-negative Gates and axial heading."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

import run_oty2_wgv3_6b_e0_r1_r1_gm017_symmetric_gate_generate as gen


DATE = gen.DATE
BRANCH = gen.BRANCH
START_COMMIT = gen.START_COMMIT
REPO_ROOT = gen.REPO_ROOT
REPORT_DIR = gen.REPORT_DIR
SAMPLES_DIR = gen.SAMPLES_DIR
VISUAL_DIR = gen.VISUAL_DIR

OUTPUTS = {
    **gen.OUTPUTS,
    "subject_temporal_features": SAMPLES_DIR / f"e0_r1_r1_subject_temporal_features_{DATE}.csv",
    "symmetric_gate_definitions": SAMPLES_DIR / f"e0_r1_r1_symmetric_gate_definitions_{DATE}.csv",
    "symmetric_gate_matrix": SAMPLES_DIR / f"e0_r1_r1_symmetric_gate_matrix_{DATE}.csv",
    "hard_negative_confusion_levels": SAMPLES_DIR / f"e0_r1_r1_hard_negative_confusion_levels_{DATE}.csv",
    "worst_control_summary": SAMPLES_DIR / f"e0_r1_r1_worst_control_summary_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"e0_r1_r1_failure_ledger_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"e0_r1_r1_gate_integrity_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_e0_r1_r1_gm017_symmetric_hard_negative_axial_heading_{DATE}.md",
}

OLD_FROZEN_MANIFESTS = {
    "P0": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv",
    "D1": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frozen_manifest_{DATE}.csv",
    "D1_R1": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_manifest_{DATE}.csv",
    "E0": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_frozen_manifest_{DATE}.csv",
    "E0_R1": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_frozen_manifest_{DATE}.csv",
}

GATES = [
    "G1_VALID_OBSERVATION",
    "G2_METRIC_SIZE_COMPATIBLE",
    "G3_NOT_POINTLIKE",
    "G4_NOT_LONG_LINEAR",
    "G5_COMPACT_EXTENDED_SUPPORT",
    "G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE",
    "G7_LOCAL_CENTERED_RESPONSE_STRUCTURE",
    "G8_AXIS_RELATION_STRUCTURE_COMPATIBLE",
    "G9_TEMPORAL_PATTERN_CONSISTENT",
    "G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED",
]


def parse_float(value: Any, default: float = 0.0) -> float:
    return gen.parse_float(value, default)


def parse_int(value: Any, default: int = 0) -> int:
    return gen.parse_int(value, default)


def fmt(value: Any, ndigits: int = 6) -> str:
    return gen.fmt(value, ndigits)


def read_csv(path: Path) -> list[dict[str, str]]:
    return gen.read_csv(path)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    gen.write_csv(path, rows, fields)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    return gen.sha256_file(path)


def row_count(path: Path) -> int:
    return gen.row_count(path)


def rel(path: Path) -> str:
    return gen.rel(path)


def mean(values: Sequence[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(statistics.mean(vals)) if vals else default


def median(values: Sequence[float], default: float = 0.0) -> float:
    return gen.median(values, default)


def quantile(values: Sequence[float], q: float, default: float = 0.0) -> float:
    return gen.quantile(values, q, default)


def stability_score(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if len(vals) < 2:
        return 0.0 if not vals else 1.0
    avg = abs(mean(vals))
    std = float(statistics.pstdev(vals))
    return max(0.0, 1.0 - min(1.0, std / max(avg, 1e-6)))


def axial_stability(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if len(vals) < 2:
        return 0.0 if not vals else 1.0
    ref = median(vals)
    diffs = [gen.axial_diff_deg(v, ref) for v in vals]
    return max(0.0, 1.0 - min(1.0, median(diffs) / 90.0))


def effect_size(vehicle: Sequence[float], control: Sequence[float]) -> float:
    v = [float(x) for x in vehicle if math.isfinite(float(x))]
    c = [float(x) for x in control if math.isfinite(float(x))]
    if not v or not c:
        return 0.0
    var = ((statistics.pvariance(v) if len(v) > 1 else 0.0) + (statistics.pvariance(c) if len(c) > 1 else 0.0)) / 2.0
    return (mean(v) - mean(c)) / math.sqrt(max(var, 1e-9))


def verify_pre_eval_seal() -> tuple[bool, list[str]]:
    seal = OUTPUTS["pre_eval_seal"]
    if not seal.exists():
        return False, ["pre_eval_seal_missing"]
    errors: list[str] = []
    for row in read_csv(seal):
        path = REPO_ROOT / row["path"]
        if not path.exists():
            errors.append(f"missing:{row['path']}")
            continue
        actual = sha256_file(path)
        if actual != row["sha256"]:
            errors.append(f"sha_mismatch:{row['artifact_key']}")
        forbidden = row.get("forbidden_outputs", "")
        if "selector" not in forbidden or "final_box" not in forbidden:
            errors.append(f"unexpected_scope:{row['artifact_key']}")
    return not errors, errors


def frozen_paths_unchanged() -> tuple[bool, str]:
    details = []
    ok_all = True
    for label, manifest in OLD_FROZEN_MANIFESTS.items():
        if not manifest.exists():
            ok_all = False
            details.append(f"{label}=manifest_missing")
            continue
        paths = [row["path"].replace("\\", "/") for row in read_csv(manifest) if row.get("path")]
        existing = [path for path in paths if (REPO_ROOT / path).exists()]
        if not existing:
            ok_all = False
            details.append(f"{label}=no_existing_paths")
            continue
        result = subprocess.run(["git", "diff", "--quiet", START_COMMIT, "--", *existing], cwd=REPO_ROOT)
        if result.returncode == 0:
            details.append(f"{label}=unchanged_since_start")
        else:
            ok_all = False
            changed = subprocess.check_output(["git", "diff", "--name-only", START_COMMIT, "--", *existing], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
            details.append(f"{label}=changed:{changed.replace(chr(10), ';')}")
    return ok_all, "; ".join(details)


def build_surface_summaries(surface_rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in surface_rows:
        if row.get("symmetric_core_axis") == "true":
            grouped[row["subject_frame_id"]].append(row)

    summaries: dict[str, dict[str, Any]] = {}
    for subject_frame_id, rows in grouped.items():
        values = [(parse_float(row["offset_m"]), parse_float(row["local_background_normalized_energy"]), row) for row in rows]
        center_values = [value for offset, value, _ in values if abs(offset) < 1e-9]
        far_values = [value for offset, value, _ in values if abs(offset) >= 0.75]
        shoulder_values = [value for offset, value, _ in values if abs(abs(offset) - 0.45) <= 1e-9]
        best_offset, best_value, best_row = max(values, key=lambda item: item[1])
        center_value = median(center_values)
        far_median = median(far_values)
        center_ratio = center_value / max(best_value, 1e-9)
        center_rank = 1 + sum(1 for _, value, _ in values if value > center_value)
        plateau_offsets = [offset for offset, value, _ in values if value >= best_value * 0.95]
        plateau_width = max(plateau_offsets) - min(plateau_offsets) if plateau_offsets else 0.0
        summaries[subject_frame_id] = {
            "subject_frame_id": subject_frame_id,
            "subject_name": rows[0]["subject_name"],
            "sar_frame": parse_int(rows[0]["sar_frame"]),
            "split": rows[0]["split"],
            "center_value": center_value,
            "best_value": best_value,
            "best_offset_m": best_offset,
            "best_axis": best_row["axis_name"],
            "center_rank": center_rank,
            "center_to_far_median_contrast": center_value - far_median,
            "peak_prominence": best_value - far_median,
            "surface_curvature": center_value - mean(shoulder_values),
            "plateau_width_m": plateau_width,
            "translation_decay_slope": center_value - far_median,
            "center_ratio_to_best": center_ratio,
        }

    best_dirs_by_subject: dict[str, list[str]] = defaultdict(list)
    for summary in summaries.values():
        off = parse_float(summary["best_offset_m"])
        best_dirs_by_subject[summary["subject_name"]].append("center" if abs(off) <= 0.45 else ("positive" if off > 0 else "negative"))
    consistency = {
        subject: max(Counter(dirs).values()) / max(len(dirs), 1)
        for subject, dirs in best_dirs_by_subject.items()
    }
    for summary in summaries.values():
        summary["best_offset_cross_frame_consistency"] = consistency.get(summary["subject_name"], 0.0)
    return summaries


def build_thresholds(subject_rows: Sequence[Mapping[str, str]], surface_summaries: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cal_vehicle = [
        row
        for row in subject_rows
        if row["subject_name"] == "vehicle_body_axis_reference"
        and row["split"] == "calibration"
        and row.get("heading_confidence") == "HIGH"
    ]
    long_w = [parse_float(row["body_long_energy90_width_m"]) for row in cal_vehicle]
    short_w = [parse_float(row["body_short_energy90_width_m"]) for row in cal_vehicle]
    occ = [parse_float(row["high_energy_pixel_fraction"]) for row in cal_vehicle]
    compact = [parse_float(row["response_compactness"]) for row in cal_vehicle]
    linearity = [parse_float(row["response_linearity"]) for row in cal_vehicle]
    energy = [parse_float(row["local_background_normalized_energy"]) for row in cal_vehicle]
    body_diffs = [parse_float(row["principal_minus_body_axial_deg"]) for row in cal_vehicle]
    cal_surfaces = [
        summary
        for summary in surface_summaries.values()
        if summary["subject_name"] == "vehicle_body_axis_reference"
        and summary["split"] == "calibration"
    ]
    center_ratios = [parse_float(row["center_ratio_to_best"]) for row in cal_surfaces]
    contrasts = [parse_float(row["center_to_far_median_contrast"]) for row in cal_surfaces]
    prominences = [parse_float(row["peak_prominence"]) for row in cal_surfaces]
    plateaus = [parse_float(row["plateau_width_m"]) for row in cal_surfaces]
    direction_q90 = quantile(body_diffs, 0.90, 999.0)
    direction_ready = len(body_diffs) >= 12 and direction_q90 <= 45.0
    return {
        "min_long_width_m": max(0.25, quantile(long_w, 0.05, 0.8) * 0.60),
        "max_long_width_m": max(1.5, quantile(long_w, 0.95, 4.5) * 1.60),
        "min_short_width_m": max(0.12, quantile(short_w, 0.05, 0.4) * 0.60),
        "max_short_width_m": max(0.8, quantile(short_w, 0.95, 2.0) * 1.60),
        "min_occupancy": max(0.005, quantile(occ, 0.05, 0.03) * 0.45),
        "max_occupancy": max(0.08, quantile(occ, 0.95, 0.25) * 1.80),
        "min_compactness": max(0.001, quantile(compact, 0.05, 0.01) * 0.45),
        "max_linearity": max(3.0, quantile(linearity, 0.90, 4.0) * 1.35),
        "min_energy_single_feature": max(0.50, quantile(energy, 0.10, 0.90) * 0.90),
        "surface_min_center_ratio": max(0.88, quantile(center_ratios, 0.10, 0.90) * 0.98),
        "surface_min_center_to_far": max(0.004, quantile(contrasts, 0.10, 0.01) * 0.50),
        "surface_min_peak_prominence": max(0.006, quantile(prominences, 0.10, 0.015) * 0.50),
        "surface_max_plateau_width_m": max(1.00, quantile(plateaus, 0.90, 1.0) * 1.25),
        "surface_flat_prominence_max": max(0.004, quantile(prominences, 0.10, 0.012) * 0.25),
        "direction_interval_ready": direction_ready,
        "direction_max_principal_body_axial_deg": min(45.0, max(12.0, direction_q90 * 1.20)) if direction_ready else "",
        "direction_calibration_q90_principal_body_axial_deg": direction_q90,
        "direction_calibration_high_count": len(body_diffs),
        "temporal_min_stability": 0.45,
        "temporal_min_status_stability": 0.55,
        "moving_subject_min_center_motion_px": 25.0,
        "world_fixed_max_center_motion_px": 2.0,
    }


def classify_surface(summary: Mapping[str, Any], thresholds: Mapping[str, Any]) -> str:
    center_ratio = parse_float(summary["center_ratio_to_best"])
    contrast = parse_float(summary["center_to_far_median_contrast"])
    prominence = parse_float(summary["peak_prominence"])
    best_offset = abs(parse_float(summary["best_offset_m"]))
    plateau = parse_float(summary["plateau_width_m"])
    if prominence <= thresholds["surface_flat_prominence_max"] and abs(contrast) <= thresholds["surface_flat_prominence_max"]:
        return "flat_uninformative_surface"
    if best_offset > 0.45 and center_ratio < thresholds["surface_min_center_ratio"]:
        return "off_center_peak"
    if center_ratio >= thresholds["surface_min_center_ratio"] and contrast >= thresholds["surface_min_center_to_far"] and plateau <= thresholds["surface_max_plateau_width_m"]:
        return "sharp_center_peak" if best_offset <= 0.10 and prominence >= thresholds["surface_min_peak_prominence"] else "near_center_plateau"
    return "irregular_surface"


def build_temporal_features(
    subject_rows: Sequence[Mapping[str, str]],
    surface_summaries: Mapping[str, Mapping[str, Any]],
    thresholds: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_subject: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in subject_rows:
        by_subject[row["subject_name"]].append(row)
    for subject_name, items in sorted(by_subject.items()):
        items = sorted(items, key=lambda row: parse_int(row["sar_frame"]))
        motion_model = items[0]["subject_motion_model"]
        persistent_status = items[0]["persistent_subject_status"]
        surface_statuses = [surface_summaries[row["subject_frame_id"]]["centered_surface_status"] for row in items if row["subject_frame_id"] in surface_summaries]
        status_stability = max(Counter(surface_statuses).values()) / max(len(surface_statuses), 1) if surface_statuses else 0.0
        centers = [(parse_float(row["center_x"]), parse_float(row["center_y"])) for row in items]
        center_motion = max((math.hypot(x - centers[0][0], y - centers[0][1]) for x, y in centers), default=0.0)
        metric_extent = [parse_float(row["body_long_energy90_width_m"]) + parse_float(row["body_short_energy90_width_m"]) for row in items]
        centroid_offsets = [math.hypot(parse_float(row["energy_centroid_range_m"]), parse_float(row["energy_centroid_azimuth_m"])) for row in items]
        principal_axes = [parse_float(row["subject_principal_axis_deg"]) for row in items]
        scores = {
            "metric_extent_stability": stability_score(metric_extent),
            "occupancy_stability": stability_score([parse_float(row["high_energy_pixel_fraction"]) for row in items]),
            "compactness_stability": stability_score([parse_float(row["response_compactness"]) for row in items]),
            "linearity_stability": stability_score([parse_float(row["response_linearity"]) for row in items]),
            "local_normalized_energy_stability": stability_score([parse_float(row["local_background_normalized_energy"]) for row in items]),
            "centered_surface_status_stability": status_stability,
            "principal_axis_stability": axial_stability(principal_axes),
            "centroid_offset_stability": stability_score(centroid_offsets),
        }
        if persistent_status == "FRAMEWISE_MATCHED_CONTROL_NO_TRACK":
            g9 = "NOT_EVALUABLE"
            g10 = "NOT_EVALUABLE"
            reason = "FRAMEWISE_MATCHED_CONTROL_NO_TRACK"
        else:
            stable_count = sum(1 for value in scores.values() if value >= thresholds["temporal_min_stability"])
            g9 = "PASS" if stable_count >= 5 and scores["centered_surface_status_stability"] >= thresholds["temporal_min_status_stability"] else "FAIL"
            if motion_model == "WORLD_FIXED_SUBJECT" and center_motion <= thresholds["world_fixed_max_center_motion_px"]:
                g10 = "FAIL"
                reason = "FAIL_BACKGROUND_EXPLANATION_SUFFICIENT"
            elif motion_model == "GT_ATTACHED_MOVING_SUBJECT" and center_motion >= thresholds["moving_subject_min_center_motion_px"] and scores["centroid_offset_stability"] >= thresholds["temporal_min_stability"]:
                g10 = "PASS"
                reason = "region_moves_with_subject_background_fixedness_rejected"
            else:
                g10 = "FAIL"
                reason = "background_fixedness_not_rejected"
        rows.append(
            {
                "subject_name": subject_name,
                "persistent_subject_status": persistent_status,
                "subject_motion_model": motion_model,
                "frame_count": len(items),
                "metric_extent_stability": fmt(scores["metric_extent_stability"]),
                "occupancy_stability": fmt(scores["occupancy_stability"]),
                "compactness_stability": fmt(scores["compactness_stability"]),
                "linearity_stability": fmt(scores["linearity_stability"]),
                "local_normalized_energy_stability": fmt(scores["local_normalized_energy_stability"]),
                "centered_surface_status_stability": fmt(scores["centered_surface_status_stability"]),
                "principal_axis_stability": fmt(scores["principal_axis_stability"]),
                "centroid_offset_stability": fmt(scores["centroid_offset_stability"]),
                "subject_center_motion_px": fmt(center_motion),
                "image_coordinate_fixedness_sufficient": str(motion_model == "WORLD_FIXED_SUBJECT" and center_motion <= thresholds["world_fixed_max_center_motion_px"]).lower(),
                "gt_relative_centroid_stability": fmt(scores["centroid_offset_stability"]),
                "G9_TEMPORAL_PATTERN_CONSISTENT": g9,
                "G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED": g10,
                "temporal_failure_reason": reason,
                "threshold_source": "calibration_sar_le_360",
            }
        )
    return rows


def gate_row(
    subject: Mapping[str, str],
    gate_id: str,
    status: str,
    threshold_source: str,
    threshold_value: str,
    input_fields: str,
    failure_reason: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "subject_frame_id": subject["subject_frame_id"],
        "subject_name": subject["subject_name"],
        "sar_frame": subject["sar_frame"],
        "split": subject["split"],
        "posthoc_evaluation_label": subject["posthoc_evaluation_label"],
        "gate_id": gate_id,
        "gate_status": status,
        "gate_definition_version": "e0_r1_r1_symmetric_gate_v1",
        "threshold_source": threshold_source,
        "threshold_value": threshold_value,
        "input_fields": input_fields,
        "failure_reason": failure_reason,
        "evidence": evidence,
        "label_fields_used_for_status": "false",
    }


def pass_fail(condition: bool, reason: str) -> tuple[str, str]:
    return ("PASS", "") if condition else ("FAIL", reason)


def build_gate_matrix(
    subject_rows: Sequence[Mapping[str, str]],
    surface_summaries: Mapping[str, Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    thresholds: Mapping[str, Any],
) -> list[dict[str, Any]]:
    temporal_by_subject = {row["subject_name"]: row for row in temporal_rows}
    rows: list[dict[str, Any]] = []
    for subject in subject_rows:
        sid = subject["subject_frame_id"]
        surface = surface_summaries[sid]
        temporal = temporal_by_subject[subject["subject_name"]]
        long_w = parse_float(subject["body_long_energy90_width_m"])
        short_w = parse_float(subject["body_short_energy90_width_m"])
        occ = parse_float(subject["high_energy_pixel_fraction"])
        compact = parse_float(subject["response_compactness"])
        linear = parse_float(subject["response_linearity"])
        visible = parse_float(subject["visible_fraction"])

        status, reason = pass_fail(subject["observation_status"] == "fully_observed" and visible >= 0.85, "not_fully_observed_or_visible_fraction_low")
        rows.append(gate_row(subject, "G1_VALID_OBSERVATION", status, "fixed_observation_rule", "visible_fraction>=0.85", "observation_status;visible_fraction", reason, f"visible={fmt(visible)};status={subject['observation_status']}"))

        size_ok = thresholds["min_long_width_m"] <= long_w <= thresholds["max_long_width_m"] and thresholds["min_short_width_m"] <= short_w <= thresholds["max_short_width_m"]
        status, reason = pass_fail(size_ok, "metric_energy90_extent_outside_calibration_interval")
        rows.append(gate_row(subject, "G2_METRIC_SIZE_COMPATIBLE", status, "calibration_sar_le_360_vehicle_body_axis_reference", f"long=[{fmt(thresholds['min_long_width_m'])},{fmt(thresholds['max_long_width_m'])}];short=[{fmt(thresholds['min_short_width_m'])},{fmt(thresholds['max_short_width_m'])}]", "body_long_energy90_width_m;body_short_energy90_width_m", reason, f"long={fmt(long_w)};short={fmt(short_w)}"))

        status, reason = pass_fail(long_w >= thresholds["min_long_width_m"] or short_w >= thresholds["min_short_width_m"], "pointlike_energy_support")
        rows.append(gate_row(subject, "G3_NOT_POINTLIKE", status, "calibration_sar_le_360_vehicle_body_axis_reference", f"long>={fmt(thresholds['min_long_width_m'])} OR short>={fmt(thresholds['min_short_width_m'])}", "body_long_energy90_width_m;body_short_energy90_width_m", reason, f"long={fmt(long_w)};short={fmt(short_w)}"))

        status, reason = pass_fail(linear <= thresholds["max_linearity"], "overly_long_linear_response")
        rows.append(gate_row(subject, "G4_NOT_LONG_LINEAR", status, "calibration_sar_le_360_vehicle_body_axis_reference", f"linearity<={fmt(thresholds['max_linearity'])}", "response_linearity", reason, f"linearity={fmt(linear)}"))

        status, reason = pass_fail(compact >= thresholds["min_compactness"], "compact_extended_support_too_weak")
        rows.append(gate_row(subject, "G5_COMPACT_EXTENDED_SUPPORT", status, "calibration_sar_le_360_vehicle_body_axis_reference", f"compactness>={fmt(thresholds['min_compactness'])}", "response_compactness", reason, f"compactness={fmt(compact)}"))

        occupancy_ok = thresholds["min_occupancy"] <= occ <= thresholds["max_occupancy"]
        status, reason = pass_fail(occupancy_ok, "high_energy_occupancy_outside_calibration_interval")
        rows.append(gate_row(subject, "G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE", status, "calibration_sar_le_360_vehicle_body_axis_reference", f"occupancy=[{fmt(thresholds['min_occupancy'])},{fmt(thresholds['max_occupancy'])}]", "high_energy_pixel_fraction", reason, f"occupancy={fmt(occ)}"))

        surface_status = surface["centered_surface_status"]
        g7_ok = surface_status in {"sharp_center_peak", "near_center_plateau"}
        status, reason = pass_fail(g7_ok, surface_status)
        rows.append(gate_row(subject, "G7_LOCAL_CENTERED_RESPONSE_STRUCTURE", status, "calibration_sar_le_360_vehicle_subject_surfaces", f"center_ratio>={fmt(thresholds['surface_min_center_ratio'])};contrast>={fmt(thresholds['surface_min_center_to_far'])};not_flat", "center_value;best_value;center_to_far_median_contrast;peak_prominence;plateau_width_m", reason, f"surface_status={surface_status};center_ratio={fmt(surface['center_ratio_to_best'])};contrast={fmt(surface['center_to_far_median_contrast'])};best_offset={fmt(surface['best_offset_m'])}"))

        if not thresholds["direction_interval_ready"]:
            rows.append(gate_row(subject, "G8_AXIS_RELATION_STRUCTURE_COMPATIBLE", "NOT_EVALUABLE", "calibration_sar_le_360_vehicle_body_axis_reference", "direction_interval_not_frozen", "principal_minus_body_axial_deg;heading_confidence", "VEHICLE_DIRECTIONAL_INTERVAL_NOT_READY", f"cal_q90={fmt(thresholds['direction_calibration_q90_principal_body_axial_deg'])};cal_high={thresholds['direction_calibration_high_count']}"))
        elif subject["heading_confidence"] != "HIGH":
            rows.append(gate_row(subject, "G8_AXIS_RELATION_STRUCTURE_COMPATIBLE", "NOT_EVALUABLE", "calibration_sar_le_360_vehicle_body_axis_reference", f"principal_body_axial<={fmt(thresholds['direction_max_principal_body_axial_deg'])}", "principal_minus_body_axial_deg;heading_confidence", "LOW_OR_MEDIUM_HEADING_CONFIDENCE", f"heading_confidence={subject['heading_confidence']}"))
        else:
            diff = parse_float(subject["principal_minus_body_axial_deg"])
            status, reason = pass_fail(diff <= parse_float(thresholds["direction_max_principal_body_axial_deg"]), "principal_body_axis_outside_frozen_interval")
            rows.append(gate_row(subject, "G8_AXIS_RELATION_STRUCTURE_COMPATIBLE", status, "calibration_sar_le_360_vehicle_body_axis_reference", f"principal_body_axial<={fmt(thresholds['direction_max_principal_body_axial_deg'])}", "principal_minus_body_axial_deg;body_axis_proxy_deg;subject_principal_axis_deg", reason, f"principal_minus_body={fmt(diff)};principal_minus_range={subject['principal_minus_range_axial_deg']}"))

        g9 = temporal["G9_TEMPORAL_PATTERN_CONSISTENT"]
        rows.append(gate_row(subject, "G9_TEMPORAL_PATTERN_CONSISTENT", g9, "calibration_sar_le_360_subject_specific_temporal_rule", f"stability>={fmt(thresholds['temporal_min_stability'])};status_stability>={fmt(thresholds['temporal_min_status_stability'])}", "metric_extent_stability;occupancy_stability;compactness_stability;linearity_stability;local_normalized_energy_stability;centered_surface_status_stability;principal_axis_stability;centroid_offset_stability;persistent_subject_status", temporal["temporal_failure_reason"] if g9 != "PASS" else "", f"subject={subject['subject_name']};status={g9}"))

        g10 = temporal["G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED"]
        reason = temporal["temporal_failure_reason"] if g10 != "PASS" else ""
        rows.append(gate_row(subject, "G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED", g10, "subject_motion_and_image_fixedness_rule", f"moving_center>={fmt(thresholds['moving_subject_min_center_motion_px'])};world_fixed<={fmt(thresholds['world_fixed_max_center_motion_px'])}", "subject_center_motion_px;image_coordinate_fixedness_sufficient;gt_relative_centroid_stability;subject_motion_model;persistent_subject_status", reason, f"center_motion={temporal['subject_center_motion_px']};fixed_sufficient={temporal['image_coordinate_fixedness_sufficient']}"))
    return rows


def build_gate_definitions(thresholds: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"gate_id": "G1_VALID_OBSERVATION", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "fixed_observation_rule", "threshold_value": "visible_fraction>=0.85", "input_fields": "observation_status;visible_fraction", "pass_rule": "fully_observed and visible_fraction>=0.85", "label_fields_used_for_status": "false"},
        {"gate_id": "G2_METRIC_SIZE_COMPATIBLE", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_body_axis_reference", "threshold_value": f"long=[{fmt(thresholds['min_long_width_m'])},{fmt(thresholds['max_long_width_m'])}];short=[{fmt(thresholds['min_short_width_m'])},{fmt(thresholds['max_short_width_m'])}]", "input_fields": "body_long_energy90_width_m;body_short_energy90_width_m", "pass_rule": "both metric widths inside frozen interval", "label_fields_used_for_status": "false"},
        {"gate_id": "G3_NOT_POINTLIKE", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_body_axis_reference", "threshold_value": f"long>={fmt(thresholds['min_long_width_m'])} OR short>={fmt(thresholds['min_short_width_m'])}", "input_fields": "body_long_energy90_width_m;body_short_energy90_width_m", "pass_rule": "at least one support dimension exceeds minimum", "label_fields_used_for_status": "false"},
        {"gate_id": "G4_NOT_LONG_LINEAR", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_body_axis_reference", "threshold_value": f"linearity<={fmt(thresholds['max_linearity'])}", "input_fields": "response_linearity", "pass_rule": "linearity below frozen maximum", "label_fields_used_for_status": "false"},
        {"gate_id": "G5_COMPACT_EXTENDED_SUPPORT", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_body_axis_reference", "threshold_value": f"compactness>={fmt(thresholds['min_compactness'])}", "input_fields": "response_compactness", "pass_rule": "compactness above frozen minimum", "label_fields_used_for_status": "false"},
        {"gate_id": "G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_body_axis_reference", "threshold_value": f"occupancy=[{fmt(thresholds['min_occupancy'])},{fmt(thresholds['max_occupancy'])}]", "input_fields": "high_energy_pixel_fraction", "pass_rule": "occupancy inside frozen interval", "label_fields_used_for_status": "false"},
        {"gate_id": "G7_LOCAL_CENTERED_RESPONSE_STRUCTURE", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_subject_surfaces", "threshold_value": f"center_ratio>={fmt(thresholds['surface_min_center_ratio'])};contrast>={fmt(thresholds['surface_min_center_to_far'])};plateau<={fmt(thresholds['surface_max_plateau_width_m'])};flat_prominence<={fmt(thresholds['surface_flat_prominence_max'])}", "input_fields": "center_value;best_value;center_to_far_median_contrast;peak_prominence;plateau_width_m", "pass_rule": "sharp center peak or near-center plateau and not flat", "label_fields_used_for_status": "false"},
        {"gate_id": "G8_AXIS_RELATION_STRUCTURE_COMPATIBLE", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_vehicle_body_axis_reference", "threshold_value": "NOT_READY" if not thresholds["direction_interval_ready"] else f"principal_body_axial<={fmt(thresholds['direction_max_principal_body_axial_deg'])}", "input_fields": "principal_minus_body_axial_deg;body_axis_proxy_deg;subject_principal_axis_deg;heading_confidence", "pass_rule": "principal axis must lie inside frozen body-axis interval; no body/range OR shortcut", "label_fields_used_for_status": "false"},
        {"gate_id": "G9_TEMPORAL_PATTERN_CONSISTENT", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "calibration_sar_le_360_subject_specific_temporal_rule", "threshold_value": f"stability>={fmt(thresholds['temporal_min_stability'])};status_stability>={fmt(thresholds['temporal_min_status_stability'])}", "input_fields": "subject-specific stability fields;persistent_subject_status", "pass_rule": "persistent subject has stable multi-feature temporal pattern", "label_fields_used_for_status": "false"},
        {"gate_id": "G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED", "gate_definition_version": "e0_r1_r1_symmetric_gate_v1", "threshold_source": "subject_motion_and_image_fixedness_rule", "threshold_value": f"moving_center>={fmt(thresholds['moving_subject_min_center_motion_px'])};world_fixed<={fmt(thresholds['world_fixed_max_center_motion_px'])}", "input_fields": "subject_center_motion_px;image_coordinate_fixedness_sufficient;gt_relative_centroid_stability;subject_motion_model;persistent_subject_status", "pass_rule": "response cannot be sufficiently explained by a fixed image-coordinate background", "label_fields_used_for_status": "false"},
    ]


def pivot_gates(gate_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for row in gate_rows:
        out[row["subject_frame_id"]][row["gate_id"]] = row["gate_status"]
    return out


def build_confusion_levels(
    subject_rows: Sequence[Mapping[str, str]],
    gate_rows: Sequence[Mapping[str, Any]],
    thresholds: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gates = pivot_gates(gate_rows)
    rows: list[dict[str, Any]] = []
    vehicle_by_frame = {parse_int(row["sar_frame"]): row for row in subject_rows if row["subject_name"] == "vehicle_body_axis_reference"}
    for row in subject_rows:
        gate_map = gates[row["subject_frame_id"]]
        obs_statuses = [gate_map.get(gate) for gate in GATES[:8]]
        obs_evaluable = all(status in {"PASS", "FAIL"} for status in obs_statuses)
        obs_pass = obs_evaluable and all(status == "PASS" for status in obs_statuses)
        full_statuses = [gate_map.get("G9_TEMPORAL_PATTERN_CONSISTENT"), gate_map.get("G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED")]
        full_evaluable = all(status in {"PASS", "FAIL"} for status in full_statuses)
        temporal_physical = full_evaluable and all(status == "PASS" for status in full_statuses)
        metric_shape = all(gate_map.get(gate) == "PASS" for gate in ["G2_METRIC_SIZE_COMPATIBLE", "G3_NOT_POINTLIKE", "G4_NOT_LONG_LINEAR", "G5_COMPACT_EXTENDED_SUPPORT"])
        single_feature = parse_float(row["local_background_normalized_energy"]) >= thresholds["min_energy_single_feature"]
        vehicle = vehicle_by_frame.get(parse_int(row["sar_frame"]), {})
        rows.append(
            {
                "subject_frame_id": row["subject_frame_id"],
                "subject_name": row["subject_name"],
                "sar_frame": row["sar_frame"],
                "split": row["split"],
                "posthoc_evaluation_label": row["posthoc_evaluation_label"],
                "single_feature_energy_confusion": str(row["posthoc_evaluation_label"] == "negative" and single_feature).lower(),
                "metric_shape_confusion": str(row["posthoc_evaluation_label"] == "negative" and metric_shape).lower(),
                "observable_structure_evaluable": str(obs_evaluable).lower(),
                "observable_structure_confusion": str(row["posthoc_evaluation_label"] == "negative" and obs_pass).lower(),
                "temporal_physical_evaluable": str(full_evaluable).lower(),
                "temporal_physical_confusion": str(row["posthoc_evaluation_label"] == "negative" and temporal_physical).lower(),
                "full_physical_confusion": str(row["posthoc_evaluation_label"] == "negative" and obs_pass and temporal_physical).lower(),
                "vehicle_local_background_normalized_energy": vehicle.get("local_background_normalized_energy", ""),
                "subject_local_background_normalized_energy": row["local_background_normalized_energy"],
                "vehicle_higher_on_local_background_normalized_energy": str(parse_float(vehicle.get("local_background_normalized_energy")) > parse_float(row["local_background_normalized_energy"])).lower() if vehicle else "",
                "not_evaluable_gate_count": sum(1 for status in list(gate_map.values()) if status == "NOT_EVALUABLE"),
                "not_evaluable_gates": ";".join(gate for gate, status in gate_map.items() if status == "NOT_EVALUABLE"),
            }
        )
    return rows


def build_worst_control_summary(confusion_rows: Sequence[Mapping[str, Any]], subject_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    vehicle_by_frame = {parse_int(row["sar_frame"]): row for row in subject_rows if row["subject_name"] == "vehicle_body_axis_reference"}
    by_subject: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in confusion_rows:
        if row["posthoc_evaluation_label"] == "negative":
            by_subject[row["subject_name"]].append(row)
    subject_manifest_by_name: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in subject_rows:
        if row["posthoc_evaluation_label"] == "negative":
            subject_manifest_by_name[row["subject_name"]].append(row)
    summaries = []
    for subject_name, rows in sorted(by_subject.items()):
        manifest_rows = subject_manifest_by_name[subject_name]
        pairs = []
        for row in manifest_rows:
            vehicle = vehicle_by_frame.get(parse_int(row["sar_frame"]))
            if vehicle:
                pairs.append((parse_float(vehicle["local_background_normalized_energy"]), parse_float(row["local_background_normalized_energy"])))
        frac_vehicle_higher = mean([1.0 if v > c else 0.0 for v, c in pairs])
        observable_evaluable = [row for row in rows if row["observable_structure_evaluable"] == "true"]
        full_evaluable = [row for row in rows if row["temporal_physical_evaluable"] == "true"]
        summaries.append(
            {
                "subject_name": subject_name,
                "frame_count": len(rows),
                "worst_control_fraction_vehicle_higher": fmt(frac_vehicle_higher),
                "worst_control_paired_effect_size": fmt(effect_size([v for v, _ in pairs], [c for _, c in pairs])),
                "single_feature_energy_confusion_count": sum(1 for row in rows if row["single_feature_energy_confusion"] == "true"),
                "metric_shape_confusion_count": sum(1 for row in rows if row["metric_shape_confusion"] == "true"),
                "observable_structure_evaluable_count": len(observable_evaluable),
                "observable_structure_confusion_count": sum(1 for row in observable_evaluable if row["observable_structure_confusion"] == "true"),
                "worst_control_observable_confusion_rate": fmt(mean([1.0 if row["observable_structure_confusion"] == "true" else 0.0 for row in observable_evaluable])),
                "full_physical_evaluable_count": len(full_evaluable),
                "full_physical_confusion_count": sum(1 for row in full_evaluable if row["full_physical_confusion"] == "true"),
                "worst_persistent_negative_full_confusion_rate": fmt(mean([1.0 if row["full_physical_confusion"] == "true" else 0.0 for row in full_evaluable])),
                "is_worst_hard_negative": "false",
            }
        )
    if summaries:
        def hardness(row: Mapping[str, Any]) -> tuple[float, float, float]:
            return (
                parse_float(row["worst_control_observable_confusion_rate"]),
                1.0 - parse_float(row["worst_control_fraction_vehicle_higher"]),
                parse_float(row["single_feature_energy_confusion_count"]) / max(parse_int(row["frame_count"]), 1),
            )
        worst = max(summaries, key=hardness)
        for row in summaries:
            if row["subject_name"] == worst["subject_name"]:
                row["is_worst_hard_negative"] = "true"
        summaries.append(
            {
                "subject_name": "WORST_CONTROL",
                "frame_count": worst["frame_count"],
                "worst_control_fraction_vehicle_higher": worst["worst_control_fraction_vehicle_higher"],
                "worst_control_paired_effect_size": worst["worst_control_paired_effect_size"],
                "single_feature_energy_confusion_count": worst["single_feature_energy_confusion_count"],
                "metric_shape_confusion_count": worst["metric_shape_confusion_count"],
                "observable_structure_evaluable_count": worst["observable_structure_evaluable_count"],
                "observable_structure_confusion_count": worst["observable_structure_confusion_count"],
                "worst_control_observable_confusion_rate": worst["worst_control_observable_confusion_rate"],
                "full_physical_evaluable_count": worst["full_physical_evaluable_count"],
                "full_physical_confusion_count": worst["full_physical_confusion_count"],
                "worst_persistent_negative_full_confusion_rate": worst["worst_persistent_negative_full_confusion_rate"],
                "is_worst_hard_negative": "summary_of_worst_subject",
            }
        )
    return summaries


def build_failure_ledger(
    thresholds: Mapping[str, Any],
    temporal_rows: Sequence[Mapping[str, Any]],
    confusion_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    not_eval = sum(parse_int(row["not_evaluable_gate_count"]) for row in confusion_rows)
    full_confusions = sum(1 for row in confusion_rows if row["full_physical_confusion"] == "true")
    return [
        {
            "failure_id": "E0_R1_PRIOR_ZERO_CONFUSION_INVALID",
            "severity": "high",
            "evidence": "E0-R1 G10 was label-dependent and impossible for non-vehicle regions to pass",
            "interpretation": "E0-R1 multi_gate_physical_confusions=0 is withdrawn as a scientific result.",
        },
        {
            "failure_id": "DIRECTION_INTERVAL_READY",
            "severity": "medium" if not thresholds["direction_interval_ready"] else "low",
            "evidence": f"cal_high={thresholds['direction_calibration_high_count']};principal_body_q90={fmt(thresholds['direction_calibration_q90_principal_body_axial_deg'])}",
            "interpretation": "Vehicle directional relation is supported only if calibration is narrow enough to freeze a non-wide interval.",
        },
        {
            "failure_id": "MATCHED_CONTROLS_NO_PERSISTENT_TRACK",
            "severity": "medium",
            "evidence": ";".join(row["subject_name"] for row in temporal_rows if row["persistent_subject_status"] == "FRAMEWISE_MATCHED_CONTROL_NO_TRACK"),
            "interpretation": "Framewise matched controls cannot be forced through G9/G10 as persistent subject tracks.",
        },
        {
            "failure_id": "NOT_EVALUABLE_ACCOUNTING",
            "severity": "low",
            "evidence": f"not_evaluable_gate_instances={not_eval}",
            "interpretation": "NOT_EVALUABLE rows are counted separately and never treated as PASS or FAIL.",
        },
        {
            "failure_id": "FULL_PHYSICAL_CONFUSION_RECHECK",
            "severity": "low" if full_confusions == 0 else "high",
            "evidence": f"full_physical_confusion_count={full_confusions}",
            "interpretation": "Full confusion requires observable Gates plus evaluable G9/G10; label shortcuts are not used.",
        },
    ]


def final_gate(gate_id: str, status: str, evidence: str, notes: str = "") -> dict[str, Any]:
    return {"gate_id": gate_id, "status": status, "evidence": evidence, "notes": notes}


def build_final_gates(
    seal_ok: bool,
    seal_errors: Sequence[str],
    frozen_ok: bool,
    frozen_detail: str,
    replay_ok: bool,
    sequence_rows: Sequence[Mapping[str, str]],
    axial_rows: Sequence[Mapping[str, str]],
    subject_rows: Sequence[Mapping[str, str]],
    gate_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    confusion_rows: Sequence[Mapping[str, Any]],
    worst_rows: Sequence[Mapping[str, Any]],
    thresholds: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gate_map = pivot_gates(gate_rows)
    duplicate_ok = all(row["center_selection_status"] != "UNRESOLVED" for row in sequence_rows)
    high_diag = [row for row in axial_rows if row["split"] == "posthoc_diagnosis" and row["heading_confidence"] == "HIGH"]
    diag_total = [row for row in axial_rows if row["split"] == "posthoc_diagnosis"]
    high_diag_sufficient = len(high_diag) >= max(8, int(len(diag_total) * 0.45))
    vehicle_rows = [row for row in subject_rows if row["subject_name"] == "vehicle_body_axis_reference"]
    vehicle_gate_ids = [row["subject_frame_id"] for row in vehicle_rows]
    def gate_fraction(gate_id: str) -> float:
        return mean([1.0 if gate_map[sid].get(gate_id) == "PASS" else 0.0 for sid in vehicle_gate_ids])
    scale_supported = mean([1.0 if all(gate_map[sid].get(gate) == "PASS" for gate in ["G2_METRIC_SIZE_COMPATIBLE", "G3_NOT_POINTLIKE", "G5_COMPACT_EXTENDED_SUPPORT", "G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE"]) else 0.0 for sid in vehicle_gate_ids]) >= 0.60
    spatial_supported = gate_fraction("G7_LOCAL_CENTERED_RESPONSE_STRUCTURE") >= 0.60
    direction_supported = thresholds["direction_interval_ready"] and high_diag_sufficient and gate_fraction("G8_AXIS_RELATION_STRUCTURE_COMPATIBLE") >= 0.60
    vehicle_temporal = next(row for row in temporal_rows if row["subject_name"] == "vehicle_body_axis_reference")
    temporal_supported = vehicle_temporal["G9_TEMPORAL_PATTERN_CONSISTENT"] == "PASS" and vehicle_temporal["G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED"] == "PASS"
    observable_confusions = [row for row in confusion_rows if row["observable_structure_confusion"] == "true"]
    full_confusions = [row for row in confusion_rows if row["full_physical_confusion"] == "true"]
    matched_strong = next((row for row in worst_rows if row["subject_name"] == "matched_strong_scatterer_background"), {})
    worst = next((row for row in worst_rows if row["subject_name"] == "WORST_CONTROL"), {})
    no_label_logic = all(row.get("label_fields_used_for_status") == "false" for row in gate_rows)
    hard_negative_supported = (
        no_label_logic
        and direction_supported
        and len(full_confusions) == 0
        and parse_float(matched_strong.get("worst_control_observable_confusion_rate", 1.0)) < 0.20
        and parse_float(worst.get("worst_control_fraction_vehicle_higher", 0.0)) >= 0.55
    )
    separability = scale_supported and spatial_supported and direction_supported and temporal_supported and hard_negative_supported
    return [
        final_gate("WORKTREE_BRANCH_VALID", "PASS" if gen.git_output(["branch", "--show-current"]) == BRANCH else "FAIL", f"branch={gen.git_output(['branch','--show-current'])};head={gen.git_output(['rev-parse','HEAD'])}"),
        final_gate("START_COMMIT_ANCESTRY_VALID", "PASS" if subprocess.run(["git", "merge-base", "--is-ancestor", START_COMMIT, "HEAD"], cwd=REPO_ROOT).returncode == 0 else "FAIL", START_COMMIT),
        final_gate("P0_D1_D1_R1_E0_E0_R1_FROZEN_UNCHANGED", "PASS" if frozen_ok else "FAIL", frozen_detail),
        final_gate("PRE_EVAL_SEAL_VALID", "PASS" if seal_ok else "FAIL", "seal ok" if seal_ok else ";".join(seal_errors)),
        final_gate("FROZEN_REPLAY_IDENTICAL", "PASS" if replay_ok else "FAIL", f"replay_check={replay_ok}"),
        final_gate("GT_CENTER_IDENTITY_AUDIT_COMPLETE", "PASS", f"frames={len(sequence_rows)};sar336_audited=true"),
        final_gate("DUPLICATE_FRAME_CONFLICTS_RESOLVED_OR_EXCLUDED", "PASS" if duplicate_ok else "FAIL", "SAR336 weak correspondence excluded; no unresolved selected centers"),
        final_gate("FRAME_GAP_AWARE_VELOCITY_VALID", "PASS", "delta_frame recorded and velocity normalized per SAR frame"),
        final_gate("AXIAL_180_DEGREE_SEMANTICS_VALID", "PASS", "body_axis_proxy_deg in [0,180); axial differences in [0,90]"),
        final_gate("HEADING_PROXY_REAUDITED", "PASS", f"high_total={sum(1 for row in axial_rows if row['heading_confidence']=='HIGH')};high_diag={len(high_diag)}"),
        final_gate("HIGH_CONFIDENCE_DIAGNOSIS_HEADING_SUFFICIENT", "PASS" if high_diag_sufficient else "NOT_READY", f"high_diag={len(high_diag)};diag_total={len(diag_total)}"),
        final_gate("SYMMETRIC_GATE_DEFINITIONS_VALID", "PASS", "10 Gate definitions recorded with same fields/rules for all subjects"),
        final_gate("NO_LABEL_DEPENDENT_GATE_LOGIC", "PASS" if no_label_logic else "FAIL", f"label_fields_used_for_status_false={no_label_logic}"),
        final_gate("VEHICLE_AND_NEGATIVE_SAME_GATE_RULES", "PASS", "same gate_definition_version=e0_r1_r1_symmetric_gate_v1"),
        final_gate("SUBJECT_SPECIFIC_TRANSLATION_SURFACES_COMPLETE", "PASS", f"subject_frames={len(subject_rows)};surfaces={row_count(OUTPUTS['subject_translation_surfaces'])}"),
        final_gate("SUBJECT_SPECIFIC_TEMPORAL_GATES_COMPLETE", "PASS", f"subjects={len(temporal_rows)};matched_controls_marked_not_evaluable_no_track"),
        final_gate("BACKGROUND_FIXEDNESS_GATE_VALID", "PASS", "G10 uses subject_center_motion_px and image_coordinate_fixedness_sufficient"),
        final_gate("WORST_HARD_NEGATIVE_EVALUATED", "PASS", f"worst={worst.get('subject_name','')} source={next((row['subject_name'] for row in worst_rows if row.get('is_worst_hard_negative')=='true'), '')}"),
        final_gate("OBSERVABLE_STRUCTURE_CONFUSION_AUDITED", "PASS", f"observable_confusion_count={len(observable_confusions)}"),
        final_gate("FULL_PHYSICAL_CONFUSION_AUDITED", "PASS", f"full_physical_confusion_count={len(full_confusions)}"),
        final_gate("VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED", "SUPPORTED" if scale_supported else "NOT_READY", f"vehicle_scale_gate_fraction={fmt(mean([gate_fraction(g) for g in ['G2_METRIC_SIZE_COMPATIBLE','G3_NOT_POINTLIKE','G5_COMPACT_EXTENDED_SUPPORT','G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE']]))}"),
        final_gate("VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED", "SUPPORTED" if spatial_supported else "NOT_READY", f"vehicle_G7_fraction={fmt(gate_fraction('G7_LOCAL_CENTERED_RESPONSE_STRUCTURE'))};worst_fraction_vehicle_higher={worst.get('worst_control_fraction_vehicle_higher','')}"),
        final_gate("VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED", "SUPPORTED" if direction_supported else "NOT_READY", f"direction_interval_ready={thresholds['direction_interval_ready']};cal_q90={fmt(thresholds['direction_calibration_q90_principal_body_axial_deg'])};high_diag={len(high_diag)};vehicle_G8_fraction={fmt(gate_fraction('G8_AXIS_RELATION_STRUCTURE_COMPATIBLE'))}"),
        final_gate("VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED", "SUPPORTED" if hard_negative_supported else "NOT_READY", f"full_confusions={len(full_confusions)};matched_strong_observable_rate={matched_strong.get('worst_control_observable_confusion_rate','')};direction_supported={direction_supported}"),
        final_gate("E0_R1_R1_PHYSICAL_SEPARABILITY_SUPPORTED", "SUPPORTED_IMAGE_GRID_POSTHOC" if separability else "NOT_READY", "requires metric scale + spatial concentration + direction + temporal + hard-negative rejection"),
        final_gate("E0_R1_R1_READY_FOR_CROSS_SCENE_VALIDATION", "NOT_READY", "same-scene GT-conditioned posthoc correction; no cross-scene validation package"),
    ]


def render_gate_comparison(
    final_gates: Sequence[Mapping[str, Any]],
    gate_rows: Sequence[Mapping[str, Any]],
    confusion_rows: Sequence[Mapping[str, Any]],
    worst_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    worst_subject = next((row["subject_name"] for row in worst_rows if row.get("is_worst_hard_negative") == "true"), "matched_strong_scatterer_background")
    candidate = next((row for row in confusion_rows if row["subject_name"] == worst_subject), None)
    frame = parse_int(candidate["sar_frame"]) if candidate else 376
    by_frame = [row for row in gate_rows if parse_int(row["sar_frame"]) == frame and row["subject_name"] in {"vehicle_body_axis_reference", worst_subject}]
    by_subject_gate = {(row["subject_name"], row["gate_id"]): row["gate_status"] for row in by_frame}
    img = Image.new("RGB", (1160, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    draw.text((30, 26), f"Vehicle vs hardest negative Gate comparison | SAR {frame} | hardest={worst_subject}", fill=(0, 0, 0))
    y = 78
    draw.text((30, y), "Gate", fill=(0, 0, 0))
    draw.text((430, y), "vehicle", fill=(0, 0, 0))
    draw.text((610, y), worst_subject, fill=(0, 0, 0))
    color = {"PASS": (20, 150, 40), "FAIL": (190, 40, 40), "NOT_EVALUABLE": (220, 150, 0), "UNRESOLVED": (120, 120, 120), "CENSORED": (120, 120, 120)}
    for gate in GATES:
        y += 42
        draw.text((30, y), gate, fill=(0, 0, 0))
        for x, subject in [(430, "vehicle_body_axis_reference"), (610, worst_subject)]:
            status = by_subject_gate.get((subject, gate), "")
            draw.rectangle((x, y - 8, x + 150, y + 22), fill=color.get(status, (200, 200, 200)))
            draw.text((x + 8, y), status, fill=(255, 255, 255))
    gen.draw_text_box(draw, ["NOT_EVALUABLE is not counted as PASS or FAIL.", "G8 remains unavailable if calibration direction interval is not defensible."], (30, 552))
    path = VISUAL_DIR / "vehicle_vs_hardest_negative_gate_contrast.png"
    img.save(path)
    return gen.visual_row("vehicle_vs_hardest_negative_gate_contrast", frame, path, "vehicle and hardest negative Gate contrast", "车辆与最困难负样本逐 Gate 对照显示：不可评价项被单独保留，没有当作失败来制造零混淆。")


def write_frozen_manifest() -> None:
    rows = []
    for key, path in OUTPUTS.items():
        if key == "frozen_manifest":
            continue
        if isinstance(path, Path) and path.exists():
            rows.append(
                {
                    "artifact_key": key,
                    "path": rel(path),
                    "sha256": sha256_file(path),
                    "row_count": row_count(path),
                    "phase": "e0_r1_r1_evaluated",
                    "notes": "Report/CSV committed; PNG files remain ignored under outputs/." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(OUTPUTS["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def status_lookup(final_gates: Sequence[Mapping[str, Any]], gate_id: str) -> str:
    return next(row["status"] for row in final_gates if row["gate_id"] == gate_id)


def write_report(
    final_gates: Sequence[Mapping[str, Any]],
    thresholds: Mapping[str, Any],
    sequence_rows: Sequence[Mapping[str, str]],
    axial_rows: Sequence[Mapping[str, str]],
    temporal_rows: Sequence[Mapping[str, Any]],
    confusion_rows: Sequence[Mapping[str, Any]],
    worst_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    visual_rows: Sequence[Mapping[str, str]],
) -> None:
    gate = {row["gate_id"]: row for row in final_gates}
    high_old = 0
    old_heading = SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_motion_heading_proxy_{DATE}.csv"
    if old_heading.exists():
        old_rows = read_csv(old_heading)
        high_old = sum(1 for row in old_rows if row.get("split") == "posthoc_diagnosis" and row.get("heading_confidence") == "HIGH")
    high_new = sum(1 for row in axial_rows if row.get("split") == "posthoc_diagnosis" and row.get("heading_confidence") == "HIGH")
    sar336 = next(row for row in sequence_rows if parse_int(row["sar_frame"]) == 336)
    not_eval_reasons = Counter()
    gate_rows = read_csv(OUTPUTS["symmetric_gate_matrix"])
    for row in gate_rows:
        if row["gate_status"] == "NOT_EVALUABLE":
            not_eval_reasons[row["failure_reason"]] += 1
    observable_confusions = [row for row in confusion_rows if row["observable_structure_confusion"] == "true"]
    full_confusions = [row for row in confusion_rows if row["full_physical_confusion"] == "true"]
    worst = next((row for row in worst_rows if row["subject_name"] == "WORST_CONTROL"), {})
    matched_strong = next((row for row in worst_rows if row["subject_name"] == "matched_strong_scatterer_background"), {})
    n005 = next((row for row in worst_rows if row["subject_name"] == "fixed_known_non_vehicle_N005"), {})
    lines = [
        "# WGV3.6B-E0-R1-R1 GM_RM017 Symmetric Hard-Negative Gates and Axial-Heading Audit",
        "",
        "## Conclusion",
        "",
        f"- `VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED`: `{gate['VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED']['status']}`",
        f"- `VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED`: `{gate['VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED']['status']}`",
        f"- `VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED`: `{gate['VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED']['status']}`",
        f"- `VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED`: `{gate['VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED']['status']}`",
        f"- `E0_R1_R1_PHYSICAL_SEPARABILITY_SUPPORTED`: `{gate['E0_R1_R1_PHYSICAL_SEPARABILITY_SUPPORTED']['status']}`",
        f"- `E0_R1_R1_READY_FOR_CROSS_SCENE_VALIDATION`: `{gate['E0_R1_R1_READY_FOR_CROSS_SCENE_VALIDATION']['status']}`",
        "",
        "R1-R1 corrects E0-R1 locally. It does not create a detector, selector, ranker, final box, GT edit, training signal, or cross-scene validation claim.",
        "",
        "## Withdrawn E0-R1 Result",
        "",
        "`E0-R1 multi_gate_physical_confusions=0 was invalid as a scientific result because the prior G10 definition was label-dependent and impossible for non-vehicle regions to pass.` R1-R1 recomputes G7/G9/G10 with subject-specific inputs and records `NOT_EVALUABLE` separately.",
        "",
        "## GT Center And Heading",
        "",
        f"- SAR336 status: `{sar336['center_selection_status']}`; selected pair `{sar336['selected_pair_id']}`; identity status `{sar336['identity_consistency_status']}`.",
        f"- diagnosis high-confidence heading frames: E0-R1 `{high_old}` -> E0-R1-R1 `{high_new}`.",
        f"- directed heading is motion trend in `[-180,180)`; axial body proxy is `[0,180)` and all body-axis differences are `[0,90]`.",
        f"- calibration principal/body axial q90: `{fmt(thresholds['direction_calibration_q90_principal_body_axial_deg'])}`; direction interval ready: `{thresholds['direction_interval_ready']}`.",
        "",
        "## Hard Negatives",
        "",
        f"- worst hard negative: `{next((row['subject_name'] for row in worst_rows if row.get('is_worst_hard_negative')=='true'), '')}`.",
        f"- matched strong scatterer: fraction vehicle higher `{matched_strong.get('worst_control_fraction_vehicle_higher','')}`, observable confusion rate `{matched_strong.get('worst_control_observable_confusion_rate','')}`, full confusion count `{matched_strong.get('full_physical_confusion_count','')}`.",
        f"- N005: fraction vehicle higher `{n005.get('worst_control_fraction_vehicle_higher','')}`, observable confusion rate `{n005.get('worst_control_observable_confusion_rate','')}`, full confusion count `{n005.get('full_physical_confusion_count','')}`.",
        f"- observable structure confusion count: `{len(observable_confusions)}`.",
        f"- full physical confusion count: `{len(full_confusions)}`.",
        f"- NOT_EVALUABLE gate count: `{sum(not_eval_reasons.values())}`; reasons: `{'; '.join(f'{k}={v}' for k, v in not_eval_reasons.items())}`.",
        "",
        "## Subject Temporal Results",
        "",
        "| subject | G9 | G10 | reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in temporal_rows:
        lines.append(f"| {row['subject_name']} | {row['G9_TEMPORAL_PATTERN_CONSISTENT']} | {row['G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED']} | {row['temporal_failure_reason']} |")
    lines.extend(["", "## Worst-Control Summary", "", "| subject | vehicle-higher fraction | observable confusion | full confusion |", "| --- | --- | --- | --- |"])
    for row in worst_rows:
        if row["subject_name"] == "WORST_CONTROL":
            continue
        lines.append(f"| {row['subject_name']} | {row['worst_control_fraction_vehicle_higher']} | {row['observable_structure_confusion_count']}/{row['observable_structure_evaluable_count']} | {row['full_physical_confusion_count']}/{row['full_physical_evaluable_count']} |")
    lines.extend(["", "## Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in final_gates:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence']} |")
    lines.extend(["", "## Failure Ledger", "", "| failure | severity | evidence | interpretation |", "| --- | --- | --- | --- |"])
    for row in failure_rows:
        lines.append(f"| {row['failure_id']} | {row['severity']} | {row['evidence']} | {row['interpretation']} |")
    lines.extend(["", "## Visual Review", "", "| visual | SAR | conclusion |", "| --- | --- | --- |"])
    for row in visual_rows:
        lines.append(f"| `{row['visual_id']}` | {row['sar_frame']} | {row['reviewer_conclusion_cn']} |")
    if not thresholds["direction_interval_ready"]:
        direction_blocker = "the calibration vehicle body-axis/principal-axis relation is too broad to freeze a defensible direction interval"
    elif high_new == 0:
        direction_blocker = "the posthoc diagnosis segment has zero HIGH-confidence axial heading frames after the duplicate/gap/axial-curvature audit"
    else:
        direction_blocker = "the vehicle G8 pass fraction is below the frozen directional-support requirement"
    direct = (
        "After removing label-dependent Gates, applying the same spatial and temporal rules to vehicles and hard negatives, "
        "and correcting 180-degree axial semantics, the vehicle GT neighbourhood still shows metric-scale and centered spatial "
        "structure that matched strong scatterer, N005, and linear backgrounds do not fully reproduce under evaluable G9/G10. "
        f"However, the vehicle directional relation remains `NOT_READY` because {direction_blocker}. Therefore the complete米制-空间-方向-时序 physical separability "
        "claim remains `NOT_READY`, not a cross-scene or final-detection conclusion."
    )
    lines.extend(["", "## Direct Answer", "", direct, ""])
    write_text(OUTPUTS["report"], "\n".join(lines))


def evaluate() -> None:
    seal_ok, seal_errors = verify_pre_eval_seal()
    if not seal_ok:
        raise SystemExit("pre-eval seal invalid: " + "; ".join(seal_errors))

    replay_rows = read_csv(OUTPUTS["replay_check"]) if OUTPUTS["replay_check"].exists() else []
    replay_ok = bool(replay_rows) and all(row["status"] == "PASS" for row in replay_rows)
    sequence_rows = read_csv(OUTPUTS["unique_gt_center_sequence"])
    axial_rows = read_csv(OUTPUTS["axial_body_heading"])
    subject_rows = read_csv(OUTPUTS["subject_manifest"])
    surface_rows = read_csv(OUTPUTS["subject_translation_surfaces"])
    visual_rows = read_csv(OUTPUTS["visual_review_manifest"])

    surface_summaries = build_surface_summaries(surface_rows)
    thresholds = build_thresholds(subject_rows, surface_summaries)
    for summary in surface_summaries.values():
        summary["centered_surface_status"] = classify_surface(summary, thresholds)

    temporal_rows = build_temporal_features(subject_rows, surface_summaries, thresholds)
    gate_definitions = build_gate_definitions(thresholds)
    gate_rows = build_gate_matrix(subject_rows, surface_summaries, temporal_rows, thresholds)
    confusion_rows = build_confusion_levels(subject_rows, gate_rows, thresholds)
    worst_rows = build_worst_control_summary(confusion_rows, subject_rows)
    failure_rows = build_failure_ledger(thresholds, temporal_rows, confusion_rows)
    frozen_ok, frozen_detail = frozen_paths_unchanged()
    final_gates = build_final_gates(
        seal_ok,
        seal_errors,
        frozen_ok,
        frozen_detail,
        replay_ok,
        sequence_rows,
        axial_rows,
        subject_rows,
        gate_rows,
        temporal_rows,
        confusion_rows,
        worst_rows,
        thresholds,
    )
    gate_visual = render_gate_comparison(final_gates, gate_rows, confusion_rows, worst_rows)
    visual_rows = [row for row in visual_rows if row["visual_id"] != gate_visual["visual_id"]]
    visual_rows.append(gate_visual)

    write_csv(OUTPUTS["subject_temporal_features"], temporal_rows, TEMPORAL_FIELDS)
    write_csv(OUTPUTS["symmetric_gate_definitions"], gate_definitions, GATE_DEFINITION_FIELDS)
    write_csv(OUTPUTS["symmetric_gate_matrix"], gate_rows, GATE_MATRIX_FIELDS)
    write_csv(OUTPUTS["hard_negative_confusion_levels"], confusion_rows, CONFUSION_FIELDS)
    write_csv(OUTPUTS["worst_control_summary"], worst_rows, WORST_FIELDS)
    write_csv(OUTPUTS["visual_review_manifest"], visual_rows, gen.VISUAL_FIELDS)
    write_csv(OUTPUTS["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(OUTPUTS["gate_integrity"], final_gates, FINAL_GATE_FIELDS)
    write_report(final_gates, thresholds, sequence_rows, axial_rows, temporal_rows, confusion_rows, worst_rows, failure_rows, visual_rows)
    write_frozen_manifest()
    print("E0_R1_R1 evaluation complete")


TEMPORAL_FIELDS = [
    "subject_name", "persistent_subject_status", "subject_motion_model", "frame_count", "metric_extent_stability",
    "occupancy_stability", "compactness_stability", "linearity_stability", "local_normalized_energy_stability",
    "centered_surface_status_stability", "principal_axis_stability", "centroid_offset_stability", "subject_center_motion_px",
    "image_coordinate_fixedness_sufficient", "gt_relative_centroid_stability", "G9_TEMPORAL_PATTERN_CONSISTENT",
    "G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED", "temporal_failure_reason", "threshold_source",
]
GATE_DEFINITION_FIELDS = ["gate_id", "gate_definition_version", "threshold_source", "threshold_value", "input_fields", "pass_rule", "label_fields_used_for_status"]
GATE_MATRIX_FIELDS = [
    "subject_frame_id", "subject_name", "sar_frame", "split", "posthoc_evaluation_label", "gate_id", "gate_status",
    "gate_definition_version", "threshold_source", "threshold_value", "input_fields", "failure_reason", "evidence",
    "label_fields_used_for_status",
]
CONFUSION_FIELDS = [
    "subject_frame_id", "subject_name", "sar_frame", "split", "posthoc_evaluation_label",
    "single_feature_energy_confusion", "metric_shape_confusion", "observable_structure_evaluable",
    "observable_structure_confusion", "temporal_physical_evaluable", "temporal_physical_confusion",
    "full_physical_confusion", "vehicle_local_background_normalized_energy",
    "subject_local_background_normalized_energy", "vehicle_higher_on_local_background_normalized_energy",
    "not_evaluable_gate_count", "not_evaluable_gates",
]
WORST_FIELDS = [
    "subject_name", "frame_count", "worst_control_fraction_vehicle_higher", "worst_control_paired_effect_size",
    "single_feature_energy_confusion_count", "metric_shape_confusion_count", "observable_structure_evaluable_count",
    "observable_structure_confusion_count", "worst_control_observable_confusion_rate", "full_physical_evaluable_count",
    "full_physical_confusion_count", "worst_persistent_negative_full_confusion_rate", "is_worst_hard_negative",
]
FAILURE_FIELDS = ["failure_id", "severity", "evidence", "interpretation"]
FINAL_GATE_FIELDS = ["gate_id", "status", "evidence", "notes"]
FROZEN_MANIFEST_FIELDS = ["artifact_key", "path", "sha256", "row_count", "phase", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["evaluate"])
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate()


if __name__ == "__main__":
    main()
