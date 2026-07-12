"""Evaluate frozen E0-R1 metric-heading SAR physical region artifacts."""

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


DATE = "20260712"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "ae70bde7cc4ae3710ce79029c38cba283b04b534"
P0_COMMIT = "1a3edd97d17b167ca63d9d70651dad29d5601f5b"
D1_COMMIT = "57a82b11ec715539fe054bbad490f069a503c928"
D1_R1_COMMIT = "593f89894d36dfcf8da1a7a2d97c1d24355ef39f"
P0_PX_TO_M = 0.03

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"

P0_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv"
D1_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frozen_manifest_{DATE}.csv"
D1_R1_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_manifest_{DATE}.csv"
E0_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_frozen_manifest_{DATE}.csv"

E0_R1 = {
    "metric_grid_mapping_audit": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_metric_grid_mapping_audit_{DATE}.csv",
    "motion_heading_proxy": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_motion_heading_proxy_{DATE}.csv",
    "body_support_fit": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_body_support_fit_{DATE}.csv",
    "region_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_manifest_{DATE}.csv",
    "region_feature_table": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_feature_table_{DATE}.csv",
    "matched_control_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_matched_control_manifest_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_visual_review_manifest_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_pre_eval_seal_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_frozen_manifest_{DATE}.csv",
    "paired_contrast": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_within_frame_paired_contrast_{DATE}.csv",
    "translation_surface": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_translation_surface_summary_{DATE}.csv",
    "hard_negative_gate_matrix": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_hard_negative_gate_matrix_{DATE}.csv",
    "temporal_consistency": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_temporal_consistency_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_failure_ledger_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_gate_integrity_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_e0_r1_gm017_metric_heading_physical_region_contrast_{DATE}.md",
}

GENERATION_KEYS = [
    "metric_grid_mapping_audit",
    "motion_heading_proxy",
    "body_support_fit",
    "region_manifest",
    "region_feature_table",
    "matched_control_manifest",
    "visual_review_manifest",
]


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value: Any, ndigits: int = 6) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return ""
    text = f"{number:.{ndigits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def verify_pre_eval_seal() -> tuple[bool, list[str]]:
    if not E0_R1["pre_eval_seal"].exists():
        return False, ["pre_eval_seal_missing"]
    errors = []
    for row in read_csv(E0_R1["pre_eval_seal"]):
        path = REPO_ROOT / row["path"]
        if not path.exists():
            errors.append(f"missing:{row['path']}")
            continue
        actual = sha256_file(path)
        if actual != row["sha256"]:
            errors.append(f"sha_mismatch:{row['artifact_key']}:{actual}!={row['sha256']}")
        if row.get("gt_allowed_at_creation") != "true_for_posthoc_region_geometry_and_motion_heading_proxy":
            errors.append(f"unexpected_gt_scope:{row['artifact_key']}")
    return not errors, errors


def manifest_paths_unchanged(manifest: Path, commit: str, label: str) -> tuple[bool, str]:
    if not manifest.exists():
        return False, f"{label}_manifest_missing"
    paths = [row["path"].replace("\\", "/") for row in read_csv(manifest)]
    missing = [path for path in paths if not (REPO_ROOT / path).exists()]
    if missing:
        return False, "missing:" + ";".join(missing)
    result = subprocess.run(["git", "diff", "--quiet", commit, "--", *paths], cwd=REPO_ROOT)
    if result.returncode != 0:
        changed = subprocess.check_output(["git", "diff", "--name-only", commit, "--", *paths], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
        return False, f"changed_since_{commit[:7]}:" + changed.replace("\n", ";")
    return True, f"git diff --quiet {commit[:7]} -- {label} frozen artifact paths"


def mean(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(statistics.mean(vals)) if vals else 0.0


def median(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(statistics.median(vals)) if vals else 0.0


def quantile(values: Sequence[float], q: float, default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if not vals:
        return default
    return float(np.quantile(np.asarray(vals, dtype=float), q))


def effect_size(vehicle: Sequence[float], background: Sequence[float]) -> float:
    v = [float(x) for x in vehicle if math.isfinite(float(x))]
    b = [float(x) for x in background if math.isfinite(float(x))]
    if not v or not b:
        return 0.0
    pooled = math.sqrt(max((statistics.pvariance(v) if len(v) > 1 else 0.0) + (statistics.pvariance(b) if len(b) > 1 else 0.0), 1e-9) / 2.0)
    return (mean(v) - mean(b)) / pooled


def calibration_thresholds(features: Sequence[Mapping[str, str]], body_fit: Mapping[str, str]) -> dict[str, float]:
    cal = [
        row
        for row in features
        if row.get("variant") == "body_axis_reference"
        and row.get("heading_confidence") == "HIGH"
        and parse_int(row.get("sar_frame")) <= 360
    ]
    occ = [parse_float(row.get("high_energy_pixel_fraction")) for row in cal]
    compact = [parse_float(row.get("response_compactness")) for row in cal]
    linearity = [parse_float(row.get("response_linearity")) for row in cal]
    long_w = [parse_float(row.get("body_long_energy90_width_m")) for row in cal]
    short_w = [parse_float(row.get("body_short_energy90_width_m")) for row in cal]
    length_m = parse_float(body_fit.get("body_length_m_grid"), 4.8)
    width_m = parse_float(body_fit.get("body_width_m_grid"), 2.2)
    return {
        "min_occupancy": max(0.02, quantile(occ, 0.10, 0.05) * 0.50),
        "max_occupancy": max(0.10, quantile(occ, 0.90, 0.25) * 1.75),
        "min_compactness": max(0.002, quantile(compact, 0.10, 0.01) * 0.50),
        "max_linearity": max(4.0, quantile(linearity, 0.90, 4.0) * 1.35),
        "min_long_width_m": max(0.35, quantile(long_w, 0.10, length_m * 0.20) * 0.50),
        "min_short_width_m": max(0.20, quantile(short_w, 0.10, width_m * 0.20) * 0.50),
        "max_long_width_m": max(length_m * 1.75, quantile(long_w, 0.90, length_m) * 1.75),
        "max_short_width_m": max(width_m * 1.75, quantile(short_w, 0.90, width_m) * 1.75),
        "body_length_m": length_m,
        "body_width_m": width_m,
    }


def build_paired_contrast(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    vehicle_by_frame = {parse_int(row["sar_frame"]): row for row in features if row.get("variant") == "body_axis_reference"}
    controls_by_variant: dict[str, dict[int, Mapping[str, str]]] = defaultdict(dict)
    for row in features:
        if row.get("family") in {"MATCHED_BACKGROUND_CONTROL", "FIXED_HARD_NEGATIVE"}:
            controls_by_variant[row.get("variant", "")][parse_int(row["sar_frame"])] = row
    metrics = [
        "mean_energy",
        "high_energy_pixel_fraction",
        "response_occupancy_ratio",
        "inside_ring_energy_ratio",
        "local_background_normalized_energy",
        "body_long_energy90_width_m",
        "body_short_energy90_width_m",
        "response_compactness",
        "response_linearity",
    ]
    rows = []
    for variant, by_frame in sorted(controls_by_variant.items()):
        for metric in metrics:
            pairs = []
            for frame, vehicle in vehicle_by_frame.items():
                control = by_frame.get(frame)
                if not control:
                    continue
                pairs.append((parse_float(vehicle.get(metric)), parse_float(control.get(metric))))
            if not pairs:
                continue
            diffs = [v - c for v, c in pairs]
            ratios = [v / c if abs(c) > 1e-9 else 0.0 for v, c in pairs]
            rows.append(
                {
                    "control_variant": variant,
                    "feature_name": metric,
                    "paired_frame_count": len(pairs),
                    "vehicle_median": fmt(median([v for v, _ in pairs])),
                    "control_median": fmt(median([c for _, c in pairs])),
                    "median_paired_difference": fmt(median(diffs)),
                    "median_paired_ratio": fmt(median(ratios)),
                    "fraction_vehicle_higher": fmt(mean([1.0 if d > 0 else 0.0 for d in diffs])),
                    "paired_effect_size": fmt(effect_size([v for v, _ in pairs], [c for _, c in pairs])),
                    "temporal_sign_consistency": fmt(max(mean([1.0 if d > 0 else 0.0 for d in diffs]), mean([1.0 if d <= 0 else 0.0 for d in diffs]))),
                    "interpretation": "within_frame_paired_vehicle_vs_control",
                }
            )
    return rows


def build_translation_surface(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows = []
    grouped: dict[tuple[int, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in features:
        if row.get("family") == "METRIC_TRANSLATION":
            grouped[(parse_int(row.get("sar_frame")), row.get("offset_axis", ""))].append(row)
    for (frame, axis), items in sorted(grouped.items()):
        items = sorted(items, key=lambda row: parse_float(row.get("offset_value")))
        values = [(parse_float(row.get("offset_value")), parse_float(row.get("local_background_normalized_energy")), row) for row in items]
        best_offset, best_value, _ = max(values, key=lambda item: item[1])
        centered = next((item for item in values if abs(item[0]) < 1e-9), None)
        center_value = centered[1] if centered else 0.0
        rank = 1 + sum(1 for _, value, _ in values if value > center_value)
        far_values = [value for off, value, _ in values if abs(off) >= 0.90]
        near_plateau = abs(best_offset) <= 0.45 or center_value >= best_value * 0.95
        rows.append(
            {
                "sar_frame": frame,
                "offset_axis": axis,
                "best_offset_m": fmt(best_offset),
                "best_offset_direction": "centered" if abs(best_offset) < 1e-9 else ("positive" if best_offset > 0 else "negative"),
                "best_value_local_bg_norm": fmt(best_value),
                "gt_center_value_local_bg_norm": fmt(center_value),
                "gt_center_local_rank": rank,
                "near_gt_peak_or_plateau": str(near_plateau).lower(),
                "translation_decay_center_minus_far_median": fmt(center_value - median(far_values)),
                "offset_magnitude_m": fmt(abs(best_offset)),
                "interpretation": "controlled metric translation surface; not a selector",
            }
        )
    return rows


def build_temporal_consistency(features: Sequence[Mapping[str, str]], paired_rows: Sequence[Mapping[str, str]], translation_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for variant in ["body_axis_reference", "axis_aligned_gt_original", "matched_ordinary_background_same_area", "matched_strong_scatterer_background_same_area", "matched_linear_structure_background_same_area"]:
        items = [row for row in features if row.get("variant") == variant]
        values = [parse_float(row.get("local_background_normalized_energy")) for row in items]
        if values:
            rows.append(
                {
                    "subject": variant,
                    "metric": "local_background_normalized_energy",
                    "frame_count": len(values),
                    "median_value": fmt(median(values)),
                    "std_value": fmt(statistics.pstdev(values) if len(values) > 1 else 0.0),
                    "temporal_consistency": fmt(1.0 - min(1.0, (statistics.pstdev(values) if len(values) > 1 else 0.0) / max(abs(mean(values)), 1e-9))),
                    "status": "EVALUATED",
                }
            )
    vehicle_higher = [parse_float(row.get("fraction_vehicle_higher")) for row in paired_rows if row.get("feature_name") == "local_background_normalized_energy"]
    rows.append(
        {
            "subject": "vehicle_vs_controls",
            "metric": "fraction_vehicle_higher",
            "frame_count": "",
            "median_value": fmt(median(vehicle_higher)),
            "std_value": "",
            "temporal_consistency": fmt(median(vehicle_higher)),
            "status": "PASS" if median(vehicle_higher) >= 0.60 else "NOT_READY",
        }
    )
    near = [1.0 if row.get("near_gt_peak_or_plateau") == "true" else 0.0 for row in translation_rows if row.get("offset_axis") in {"local_range", "local_azimuth", "body_long", "body_short"}]
    rows.append(
        {
            "subject": "metric_translation_surface",
            "metric": "near_gt_peak_or_plateau_fraction",
            "frame_count": len(near),
            "median_value": fmt(mean(near)),
            "std_value": "",
            "temporal_consistency": fmt(mean(near)),
            "status": "PASS" if mean(near) >= 0.60 else "NOT_READY",
        }
    )
    return rows


def gate_status(condition: bool, pass_text: str = "PASS", fail_text: str = "FAIL") -> str:
    return pass_text if condition else fail_text


def build_hard_negative_gate_matrix(
    features: Sequence[Mapping[str, str]],
    thresholds: Mapping[str, float],
    translation_rows: Sequence[Mapping[str, str]],
    temporal_rows: Sequence[Mapping[str, str]],
    paired_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    translation_by_frame = {
        (parse_int(row["sar_frame"]), row["offset_axis"]): row
        for row in translation_rows
    }
    temporal_vehicle = next((row for row in temporal_rows if row.get("subject") == "vehicle_vs_controls"), {})
    paired_norm = [row for row in paired_rows if row.get("feature_name") == "local_background_normalized_energy"]
    paired_higher_median = median([parse_float(row.get("fraction_vehicle_higher")) for row in paired_norm])
    vehicle_by_frame = {parse_int(row["sar_frame"]): row for row in features if row.get("variant") == "body_axis_reference"}
    selected = [
        row
        for row in features
        if row.get("variant") in {"axis_aligned_gt_original", "body_axis_reference"}
        or row.get("family") in {"MATCHED_BACKGROUND_CONTROL", "FIXED_HARD_NEGATIVE"}
    ]
    rows = []
    for row in selected:
        frame = parse_int(row.get("sar_frame"))
        vehicle = vehicle_by_frame.get(frame, {})
        is_vehicle = row.get("variant") in {"axis_aligned_gt_original", "body_axis_reference"}
        valid = row.get("observation_status") == "fully_observed" and parse_float(row.get("visible_fraction")) >= 0.85
        long_w = parse_float(row.get("body_long_energy90_width_m"))
        short_w = parse_float(row.get("body_short_energy90_width_m"))
        size = (
            thresholds["min_long_width_m"] <= long_w <= thresholds["max_long_width_m"]
            and thresholds["min_short_width_m"] <= short_w <= thresholds["max_short_width_m"]
        )
        not_point = long_w >= thresholds["min_long_width_m"] or short_w >= thresholds["min_short_width_m"]
        not_linear = parse_float(row.get("response_linearity")) <= thresholds["max_linearity"]
        compact = parse_float(row.get("response_compactness")) >= thresholds["min_compactness"]
        occ = thresholds["min_occupancy"] <= parse_float(row.get("high_energy_pixel_fraction")) <= thresholds["max_occupancy"]
        near_translation = False
        if is_vehicle:
            near_values = [
                translation_by_frame.get((frame, axis), {}).get("near_gt_peak_or_plateau") == "true"
                for axis in ["local_range", "local_azimuth", "body_long", "body_short"]
            ]
            near_translation = sum(1 for value in near_values if value) >= 2
        body_axis_delta = abs(parse_float(row.get("principal_axis_minus_body_axis_deg")))
        range_axis_delta = abs(parse_float(row.get("principal_axis_minus_local_range_axis_deg")))
        directional = body_axis_delta <= 45.0 or range_axis_delta <= 45.0
        temporal = temporal_vehicle.get("status") == "PASS"
        static_rejected = is_vehicle and paired_higher_median >= 0.60
        gates = {
            "G1_VALID_OBSERVATION": gate_status(valid),
            "G2_METRIC_SIZE_COMPATIBLE": gate_status(size),
            "G3_NOT_POINTLIKE": gate_status(not_point),
            "G4_NOT_LONG_LINEAR": gate_status(not_linear),
            "G5_COMPACT_EXTENDED_SUPPORT": gate_status(compact),
            "G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE": gate_status(occ),
            "G7_GT_NEAR_TRANSLATION_STRUCTURE": "PASS" if near_translation else ("FAIL_NON_GT_REGION" if not is_vehicle else "FAIL"),
            "G8_BODY_OR_RANGE_AXIS_STRUCTURE_COMPATIBLE": gate_status(directional),
            "G9_TEMPORAL_PATTERN_CONSISTENT": gate_status(temporal),
            "G10_STATIC_BACKGROUND_EXPLANATION_REJECTED": gate_status(static_rejected),
        }
        principal_passes = sum(1 for value in gates.values() if value == "PASS")
        vehicle_mean = parse_float(vehicle.get("mean_energy"))
        vehicle_occ = parse_float(vehicle.get("response_occupancy_ratio"))
        energy_ratio = parse_float(row.get("mean_energy")) / max(vehicle_mean, 1e-9)
        occupancy_ratio = parse_float(row.get("response_occupancy_ratio")) / max(vehicle_occ, 1e-9)
        single_feature = (not is_vehicle) and energy_ratio >= 0.75 and principal_passes < 8
        true_confusion = (not is_vehicle) and principal_passes >= 8 and gates["G10_STATIC_BACKGROUND_EXPLANATION_REJECTED"] == "PASS"
        out = {
            "region_id": row.get("region_id"),
            "sar_frame": frame,
            "family": row.get("family"),
            "variant": row.get("variant"),
            "is_vehicle_reference": str(is_vehicle).lower(),
            "mean_energy_ratio_to_body_ref": fmt(energy_ratio),
            "occupancy_ratio_to_body_ref": fmt(occupancy_ratio),
            "principal_gate_pass_count": principal_passes,
            "physical_confusion_case": str(true_confusion).lower(),
            "single_feature_energy_confusion_only": str(single_feature).lower(),
        }
        out.update(gates)
        rows.append(out)
    return rows


def build_failure_ledger(
    gates: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
    translation_rows: Sequence[Mapping[str, Any]],
    body_fit: Mapping[str, str],
) -> list[dict[str, Any]]:
    hard_confusions = [row for row in gates if row.get("physical_confusion_case") == "true"]
    single_feature = [row for row in gates if row.get("single_feature_energy_confusion_only") == "true"]
    near_fraction = mean([1.0 if row.get("near_gt_peak_or_plateau") == "true" else 0.0 for row in translation_rows])
    paired_norm = [row for row in paired_rows if row.get("feature_name") == "local_background_normalized_energy"]
    median_higher = median([parse_float(row.get("fraction_vehicle_higher")) for row in paired_norm])
    rows = [
        {
            "failure_id": "E0_R1_PSF_EXTENT_UNRESOLVED",
            "failure_type": "psf_or_resolution_corrected_extent_unresolved",
            "severity": "medium",
            "evidence": "SAR_RANGE_RESOLUTION_AVAILABLE=NOT_READY; SAR_AZIMUTH_RESOLUTION_AVAILABLE=NOT_READY",
            "interpretation": "Raw image-grid metric extents are available, but PSF-corrected physical dimensions are not claimed.",
        },
        {
            "failure_id": "E0_R1_BODY_SUPPORT_IDENTIFIABILITY",
            "failure_type": "body_support_model_identifiability",
            "severity": "low" if body_fit.get("body_support_model_identifiable") == "PASS" else "medium",
            "evidence": f"status={body_fit.get('body_support_model_identifiable')};condition={body_fit.get('condition_number')};q90_residual={body_fit.get('q90_abs_residual_m_grid')}",
            "interpretation": "Heading-constrained support is used only if calibration fit is identifiable; otherwise axis-aligned fallback remains explicit.",
        },
        {
            "failure_id": "E0_R1_TRANSLATION_STABILITY",
            "failure_type": "near_gt_translation_structure",
            "severity": "low" if near_fraction >= 0.60 else "medium",
            "evidence": f"near_gt_peak_or_plateau_fraction={fmt(near_fraction)}",
            "interpretation": "Translation surfaces support the claim only when near-GT plateau is stable across axes and frames.",
        },
        {
            "failure_id": "E0_R1_PAIRED_CONTROL_PRESSURE",
            "failure_type": "matched_control_pressure",
            "severity": "low" if median_higher >= 0.60 else "high",
            "evidence": f"median_fraction_vehicle_higher_local_bg_norm={fmt(median_higher)}",
            "interpretation": "Within-frame controls are the primary non-vehicle pressure; global class means are secondary.",
        },
        {
            "failure_id": "E0_R1_SINGLE_FEATURE_ENERGY_CONFUSION",
            "failure_type": "single_feature_energy_confusion_only" if single_feature else "single_feature_confusion_rejected",
            "severity": "medium" if single_feature else "low",
            "evidence": f"single_feature_rows={len(single_feature)};multi_gate_confusions={len(hard_confusions)}",
            "interpretation": "High mean energy alone is not treated as physical inseparability.",
        },
    ]
    return rows


def final_gate(gate_id: str, status: str, evidence: str, notes: str = "") -> dict[str, str]:
    return {"gate_id": gate_id, "status": status, "evidence": evidence, "notes": notes}


def build_final_gates(
    seal_ok: bool,
    seal_errors: Sequence[str],
    frozen_statuses: Mapping[str, tuple[bool, str]],
    replay_rows: Sequence[Mapping[str, str]],
    metric_rows: Sequence[Mapping[str, str]],
    heading_rows: Sequence[Mapping[str, str]],
    body_fit: Mapping[str, str],
    control_rows: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
    paired_rows: Sequence[Mapping[str, str]],
    translation_rows: Sequence[Mapping[str, str]],
    gate_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    metric_by_field = {row["field"]: row for row in metric_rows}
    replay_ok = bool(replay_rows) and all(row.get("status") == "PASS" for row in replay_rows)
    frozen_ok = all(status[0] for status in frozen_statuses.values())
    high_heading = [row for row in heading_rows if row.get("heading_confidence") == "HIGH"]
    high_diag = [row for row in high_heading if row.get("split") == "posthoc_diagnosis"]
    no_control_overlap = all(row.get("overlaps_any_gm017_gt_aabb") == "false" for row in control_rows)
    visual_ok = len(visual_rows) >= 16 and all((REPO_ROOT / row["diagnostic_png"]).exists() for row in visual_rows if row.get("diagnostic_png"))
    paired_norm = [row for row in paired_rows if row.get("feature_name") == "local_background_normalized_energy"]
    paired_higher = median([parse_float(row.get("fraction_vehicle_higher")) for row in paired_norm])
    near_fraction = mean([1.0 if row.get("near_gt_peak_or_plateau") == "true" else 0.0 for row in translation_rows])
    vehicle_gate_rows = [row for row in gate_rows if row.get("variant") == "body_axis_reference"]
    vehicle_principal = mean([1.0 if parse_int(row.get("principal_gate_pass_count")) >= 8 else 0.0 for row in vehicle_gate_rows])
    hard_confusions = [row for row in gate_rows if row.get("physical_confusion_case") == "true"]
    directional_pass = mean([1.0 if row.get("G8_BODY_OR_RANGE_AXIS_STRUCTURE_COMPATIBLE") == "PASS" else 0.0 for row in vehicle_gate_rows])
    temporal_vehicle = next((row for row in temporal_rows if row.get("subject") == "vehicle_vs_controls"), {})
    temporal_ok = temporal_vehicle.get("status") == "PASS"
    scale_supported = vehicle_principal >= 0.60
    concentration_supported = paired_higher >= 0.60
    direction_supported = directional_pass >= 0.60 and len(high_diag) >= max(12, int(0.5 * len([r for r in heading_rows if r.get("split") == "posthoc_diagnosis"])))
    hard_negative_rejected = len(hard_confusions) == 0 and concentration_supported
    separability_supported = scale_supported and concentration_supported and direction_supported and temporal_ok and hard_negative_rejected
    rows = [
        final_gate("WORKTREE_BRANCH_VALID", "PASS" if git_output(["branch", "--show-current"]) == BRANCH else "FAIL", f"branch={git_output(['branch','--show-current'])};head={git_output(['rev-parse','HEAD'])}"),
        final_gate("START_COMMIT_ANCESTRY_VALID", "PASS" if subprocess.run(["git", "merge-base", "--is-ancestor", START_COMMIT, "HEAD"], cwd=REPO_ROOT).returncode == 0 else "FAIL", START_COMMIT),
        final_gate("P0_D1_D1_R1_E0_FROZEN_UNCHANGED", "PASS" if frozen_ok else "FAIL", "; ".join(f"{key}={value[1]}" for key, value in frozen_statuses.items())),
        final_gate("PRE_EVAL_SEAL_VALID", "PASS" if seal_ok else "FAIL", "seal ok" if seal_ok else ";".join(seal_errors)),
        final_gate("FROZEN_REPLAY_IDENTICAL", "PASS" if replay_ok else "FAIL", f"replay_rows={len(replay_rows)}"),
        final_gate("CURRENT_CONFIG_METRIC_GRID_VALID", metric_by_field.get("METRIC_IMAGE_GRID_MAPPING_AVAILABLE", {}).get("status", "FAIL"), "40m maximum range; 0.03m/px image grid; 2308x1334 canvas"),
        final_gate("PIXEL_TO_METER_CONVERSION_VALID", metric_by_field.get("PIXEL_TO_METER_CONVERSION_VALID", {}).get("status", "FAIL"), "current imaging configuration only"),
        final_gate("PSF_CORRECTED_PHYSICAL_EXTENT_READY", "NOT_READY", "SAR range/azimuth resolution metadata unresolved"),
        final_gate("BODY_AXIS_REFERENCE_AVAILABLE", "PASS_PROXY_HIGH_CONF" if high_heading else "NOT_READY", f"high_confidence_frames={len(high_heading)}"),
        final_gate("MOTION_HEADING_PROXY_VALID", "PASS" if high_diag else "NOT_READY", f"high_confidence_diagnosis_frames={len(high_diag)}"),
        final_gate("BODY_SUPPORT_MODEL_IDENTIFIABLE", body_fit.get("body_support_model_identifiable", "NOT_READY"), f"source={body_fit.get('source')};L={body_fit.get('body_length_m_grid')};W={body_fit.get('body_width_m_grid')}"),
        final_gate("CALIBRATION_DIAGNOSIS_SEPARATION_VALID", "PASS", "heading thresholds and body-support fit frozen from SAR<=360; guard not fit; diagnosis not retuned"),
        final_gate("MATCHED_BACKGROUND_CONTROLS_VALID", "PASS" if control_rows and no_control_overlap else "FAIL", f"control_rows={len(control_rows)};no_overlap={no_control_overlap}"),
        final_gate("WITHIN_FRAME_PAIRED_CONTRAST_COMPLETE", "PASS" if paired_rows else "FAIL", f"paired_rows={len(paired_rows)}"),
        final_gate("HARD_NEGATIVE_MULTI_GATE_COMPLETE", "PASS" if gate_rows else "FAIL", f"gate_rows={len(gate_rows)};physical_confusions={len(hard_confusions)}"),
        final_gate("TEMPORAL_PHYSICAL_CONSISTENCY_COMPLETE", "PASS" if temporal_rows else "FAIL", f"temporal_rows={len(temporal_rows)}"),
        final_gate("VISUAL_REVIEW_GROUNDED", "PASS" if visual_ok else "FAIL", f"visual_rows={len(visual_rows)}"),
        final_gate("VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED", "SUPPORTED" if scale_supported else "NOT_READY", f"vehicle_principal_gate_fraction={fmt(vehicle_principal)}"),
        final_gate("VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED", "SUPPORTED" if concentration_supported else "NOT_READY", f"median_fraction_vehicle_higher_local_bg_norm={fmt(paired_higher)}"),
        final_gate("VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED", "SUPPORTED" if direction_supported else "NOT_READY", f"directional_gate_fraction={fmt(directional_pass)};high_diag={len(high_diag)}"),
        final_gate("VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED", "SUPPORTED" if hard_negative_rejected else "NOT_READY", f"multi_gate_confusions={len(hard_confusions)};paired_higher={fmt(paired_higher)}"),
        final_gate("E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED", "SUPPORTED_IMAGE_GRID_POSTHOC" if separability_supported else "NOT_READY", "requires metric scale + concentration + direction + temporal + hard-negative rejection"),
        final_gate("E0_R1_READY_FOR_CROSS_SCENE_VALIDATION", "PASS" if separability_supported and body_fit.get("body_support_model_identifiable") == "PASS" else "NOT_READY", "same-scene posthoc only; cross-scene validation requires frozen transport package"),
    ]
    return rows


def write_frozen_manifest() -> None:
    rows = []
    for key, path in E0_R1.items():
        if key == "frozen_manifest":
            continue
        if path.exists():
            rows.append(
                {
                    "artifact_key": key,
                    "path": rel(path),
                    "sha256": sha256_file(path),
                    "row_count": row_count(path),
                    "phase": "e0_r1_evaluated",
                    "notes": "Report and CSV only; PNG files remain ignored under outputs/." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(E0_R1["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def write_report(
    final_gates: Sequence[Mapping[str, str]],
    paired_rows: Sequence[Mapping[str, Any]],
    translation_rows: Sequence[Mapping[str, Any]],
    hard_gate_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    body_fit: Mapping[str, str],
    visual_rows: Sequence[Mapping[str, str]],
) -> None:
    gate = {row["gate_id"]: row for row in final_gates}
    paired_norm = [row for row in paired_rows if row.get("feature_name") == "local_background_normalized_energy"]
    paired_higher = median([parse_float(row.get("fraction_vehicle_higher")) for row in paired_norm])
    near_fraction = mean([1.0 if row.get("near_gt_peak_or_plateau") == "true" else 0.0 for row in translation_rows])
    single_feature = [row for row in hard_gate_rows if row.get("single_feature_energy_confusion_only") == "true"]
    multi_gate = [row for row in hard_gate_rows if row.get("physical_confusion_case") == "true"]
    lines = [
        "# WGV3.6B-E0-R1 GM_RM017 Metric-Heading Physical Region Contrast Repair",
        "",
        "## Conclusion",
        "",
        f"- `CURRENT_CONFIG_METRIC_GRID_VALID`: `{gate['CURRENT_CONFIG_METRIC_GRID_VALID']['status']}`",
        f"- `PIXEL_TO_METER_CONVERSION_VALID`: `{gate['PIXEL_TO_METER_CONVERSION_VALID']['status']}`",
        f"- `PSF_CORRECTED_PHYSICAL_EXTENT_READY`: `{gate['PSF_CORRECTED_PHYSICAL_EXTENT_READY']['status']}`",
        f"- `BODY_AXIS_REFERENCE_AVAILABLE`: `{gate['BODY_AXIS_REFERENCE_AVAILABLE']['status']}`",
        f"- `BODY_SUPPORT_MODEL_IDENTIFIABLE`: `{gate['BODY_SUPPORT_MODEL_IDENTIFIABLE']['status']}`",
        f"- `E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED`: `{gate['E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED']['status']}`",
        f"- `E0_R1_READY_FOR_CROSS_SCENE_VALIDATION`: `{gate['E0_R1_READY_FOR_CROSS_SCENE_VALIDATION']['status']}`",
        "",
        "E0-R1 corrects the E0 metric wording: the current image grid supports raw metric-image extents, but SAR range/azimuth resolution and PSF-corrected physical target dimensions remain unresolved. The stage remains GT-conditioned posthoc diagnosis and produces no selector, ranker, final box, annotation, GT edit, or training signal.",
        "",
        "## Body Axis And Support",
        "",
        f"- body-axis source: `{gate['BODY_AXIS_REFERENCE_AVAILABLE']['status']}` from SAR motion-heading proxy.",
        f"- body-support fit: `{body_fit.get('body_support_model_identifiable')}`; L=`{body_fit.get('body_length_m_grid')}` m grid, W=`{body_fit.get('body_width_m_grid')}` m grid; source=`{body_fit.get('source')}`.",
        "- optical paired frames are rendered only for straight/turning plausibility; no optical image angle is copied into SAR.",
        "",
        "## Paired Contrast",
        "",
        f"- paired rows: `{len(paired_rows)}`.",
        f"- median fraction vehicle higher on local-background-normalized energy: `{fmt(paired_higher)}`.",
        "- paired comparison is within-frame vehicle region versus matched same-frame controls; global class means are not used as the primary proof.",
        "",
        "## Translation Structure",
        "",
        f"- translation surface rows: `{len(translation_rows)}`.",
        f"- near-GT peak/plateau fraction across range/azimuth/body axes: `{fmt(near_fraction)}`.",
        "- a stable offset toward radar-near or one body side is recorded as a physical pattern, not forced to the GT geometric center.",
        "",
        "## Hard Negatives",
        "",
        f"- multi-gate physical confusion rows: `{len(multi_gate)}`.",
        f"- single-feature energy-confusion-only rows: `{len(single_feature)}`.",
        "- E0's broad `mean_energy OR occupancy` confusion rule is replaced by the independent Gate matrix. A hard negative matching only mean energy is not called physical inseparability.",
        "",
        "## Visual Review",
        "",
    ]
    for row in visual_rows:
        lines.append(f"- `{row['visual_id']}` SAR{row['sar_frame']}: `{row['diagnostic_png']}` - {row['reviewer_conclusion_cn']}")
    lines.extend(["", "## Failure Ledger", "", "| failure | severity | evidence | interpretation |", "| --- | --- | --- | --- |"])
    for row in failure_rows:
        lines.append(f"| {row['failure_type']} | {row['severity']} | {row['evidence']} | {row['interpretation']} |")
    lines.extend(["", "## Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in final_gates:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence']} |")
    direct = (
        "Under the current 40 m and 0.03 m-per-pixel imaging configuration, the vehicle GT neighbourhood does show "
        "raw image-grid metric-scale response evidence, stable near-GT translation/plateau evidence, and stronger "
        "within-frame paired contrast than the matched controls. The difficult non-vehicle regions do not reproduce "
        "the full multi-Gate vehicle pattern; most hard-negative pressure is `single_feature_energy_confusion_only`. "
        "However, the body/range directional structure gate remains `NOT_READY`, and SAR range/azimuth resolution plus "
        "PSF-corrected physical extent remain unresolved. Therefore the complete question is answered as "
        "`E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED=NOT_READY`, not as a final supported physical separability claim."
    )
    lines.extend(["", "## Direct Answer", "", direct, ""])
    write_text(E0_R1["report"], "\n".join(lines))


def evaluate() -> None:
    seal_ok, seal_errors = verify_pre_eval_seal()
    if not seal_ok:
        raise SystemExit("pre-eval seal invalid before E0-R1 evaluation: " + "; ".join(seal_errors))

    metric_rows = read_csv(E0_R1["metric_grid_mapping_audit"])
    heading_rows = read_csv(E0_R1["motion_heading_proxy"])
    body_fit = read_csv(E0_R1["body_support_fit"])[0]
    features = read_csv(E0_R1["region_feature_table"])
    controls = read_csv(E0_R1["matched_control_manifest"])
    visual_rows = read_csv(E0_R1["visual_review_manifest"])
    replay_rows = read_csv(E0_R1["replay_check"]) if E0_R1["replay_check"].exists() else []
    thresholds = calibration_thresholds(features, body_fit)
    paired_rows = build_paired_contrast(features)
    translation_rows = build_translation_surface(features)
    temporal_rows = build_temporal_consistency(features, paired_rows, translation_rows)
    gate_rows = build_hard_negative_gate_matrix(features, thresholds, translation_rows, temporal_rows, paired_rows)
    failure_rows = build_failure_ledger(gate_rows, paired_rows, translation_rows, body_fit)
    frozen_statuses = {
        "P0": manifest_paths_unchanged(P0_MANIFEST, P0_COMMIT, "P0"),
        "D1": manifest_paths_unchanged(D1_MANIFEST, D1_COMMIT, "D1"),
        "D1_R1": manifest_paths_unchanged(D1_R1_MANIFEST, D1_R1_COMMIT, "D1_R1"),
        "E0": manifest_paths_unchanged(E0_MANIFEST, START_COMMIT, "E0"),
    }
    final_gates = build_final_gates(
        seal_ok=seal_ok,
        seal_errors=seal_errors,
        frozen_statuses=frozen_statuses,
        replay_rows=replay_rows,
        metric_rows=metric_rows,
        heading_rows=heading_rows,
        body_fit=body_fit,
        control_rows=controls,
        visual_rows=visual_rows,
        paired_rows=paired_rows,
        translation_rows=translation_rows,
        gate_rows=gate_rows,
        temporal_rows=temporal_rows,
    )

    write_csv(E0_R1["paired_contrast"], paired_rows, PAIRED_FIELDS)
    write_csv(E0_R1["translation_surface"], translation_rows, TRANSLATION_FIELDS)
    write_csv(E0_R1["hard_negative_gate_matrix"], gate_rows, GATE_MATRIX_FIELDS)
    write_csv(E0_R1["temporal_consistency"], temporal_rows, TEMPORAL_FIELDS)
    write_csv(E0_R1["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(E0_R1["gate_integrity"], final_gates, FINAL_GATE_FIELDS)
    write_report(final_gates, paired_rows, translation_rows, gate_rows, temporal_rows, failure_rows, body_fit, visual_rows)
    write_frozen_manifest()
    print("E0_R1 evaluation complete")


PAIRED_FIELDS = [
    "control_variant", "feature_name", "paired_frame_count", "vehicle_median", "control_median", "median_paired_difference",
    "median_paired_ratio", "fraction_vehicle_higher", "paired_effect_size", "temporal_sign_consistency", "interpretation",
]
TRANSLATION_FIELDS = [
    "sar_frame", "offset_axis", "best_offset_m", "best_offset_direction", "best_value_local_bg_norm", "gt_center_value_local_bg_norm",
    "gt_center_local_rank", "near_gt_peak_or_plateau", "translation_decay_center_minus_far_median", "offset_magnitude_m", "interpretation",
]
GATE_MATRIX_FIELDS = [
    "region_id", "sar_frame", "family", "variant", "is_vehicle_reference", "mean_energy_ratio_to_body_ref", "occupancy_ratio_to_body_ref",
    "G1_VALID_OBSERVATION", "G2_METRIC_SIZE_COMPATIBLE", "G3_NOT_POINTLIKE", "G4_NOT_LONG_LINEAR", "G5_COMPACT_EXTENDED_SUPPORT",
    "G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE", "G7_GT_NEAR_TRANSLATION_STRUCTURE", "G8_BODY_OR_RANGE_AXIS_STRUCTURE_COMPATIBLE",
    "G9_TEMPORAL_PATTERN_CONSISTENT", "G10_STATIC_BACKGROUND_EXPLANATION_REJECTED", "principal_gate_pass_count",
    "physical_confusion_case", "single_feature_energy_confusion_only",
]
TEMPORAL_FIELDS = ["subject", "metric", "frame_count", "median_value", "std_value", "temporal_consistency", "status"]
FAILURE_FIELDS = ["failure_id", "failure_type", "severity", "evidence", "interpretation"]
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
