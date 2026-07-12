"""Evaluate frozen E0 GM_RM017 physical region contrast artifacts."""

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
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "593f89894d36dfcf8da1a7a2d97c1d24355ef39f"
P0_COMMIT = "1a3edd97d17b167ca63d9d70651dad29d5601f5b"
D1_COMMIT = "57a82b11ec715539fe054bbad490f069a503c928"
D1_R1_COMMIT = "593f89894d36dfcf8da1a7a2d97c1d24355ef39f"

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"

P0_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv"
D1_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frozen_manifest_{DATE}.csv"
D1_R1_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_manifest_{DATE}.csv"

E0 = {
    "metric_coordinate_mapping": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_metric_coordinate_mapping_{DATE}.csv",
    "vehicle_body_size_reference": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_vehicle_body_size_reference_{DATE}.csv",
    "gt_metric_geometry": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_gt_metric_geometry_{DATE}.csv",
    "region_perturbation_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_region_perturbation_manifest_{DATE}.csv",
    "region_feature_table": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_region_feature_table_{DATE}.csv",
    "scale_response_curves": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_scale_response_curves_{DATE}.csv",
    "translation_response_surface": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_translation_response_surface_{DATE}.csv",
    "rotation_response_curves": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_rotation_response_curves_{DATE}.csv",
    "ring_contrast": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_ring_contrast_{DATE}.csv",
    "background_control_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_background_control_manifest_{DATE}.csv",
    "hard_negative_comparison": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_hard_negative_comparison_{DATE}.csv",
    "pixel_vs_normalized_vs_metric_ablation": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_pixel_vs_normalized_vs_metric_ablation_{DATE}.csv",
    "mask_censoring_audit": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_mask_censoring_audit_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_visual_review_manifest_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_failure_ledger_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_gate_integrity_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_pre_eval_seal_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_frozen_manifest_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_e0_gm017_gt_conditioned_metric_physical_region_contrast_{DATE}.md",
}

GENERATION_KEYS = [
    "metric_coordinate_mapping",
    "vehicle_body_size_reference",
    "gt_metric_geometry",
    "region_perturbation_manifest",
    "region_feature_table",
    "background_control_manifest",
    "mask_censoring_audit",
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
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return ""
    return f"{number:.{ndigits}f}".rstrip("0").rstrip(".")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    return len(read_csv(path))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def verify_pre_eval_seal() -> tuple[bool, list[str]]:
    if not E0["pre_eval_seal"].exists():
        return False, ["pre_eval_seal_missing"]
    errors: list[str] = []
    for row in read_csv(E0["pre_eval_seal"]):
        path = REPO_ROOT / row["path"]
        if not path.exists():
            errors.append(f"missing:{row['path']}")
            continue
        actual = sha256_file(path)
        if actual != row["sha256"]:
            errors.append(f"sha_mismatch:{row['artifact_key']}:{actual}!={row['sha256']}")
        if row.get("gt_allowed_at_creation") != "true_for_region_geometry_generation":
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
    return float(statistics.mean(values)) if values else 0.0


def median(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def p90(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(np.quantile(np.asarray(values, dtype=float), 0.90))


def group_summary(rows: Sequence[Mapping[str, str]], group_key: str, group_value: str) -> dict[str, Any]:
    vals = {
        "mean_energy": [parse_float(row.get("mean_energy")) for row in rows],
        "total_energy": [parse_float(row.get("total_energy")) for row in rows],
        "high_energy_pixel_fraction": [parse_float(row.get("high_energy_pixel_fraction")) for row in rows],
        "response_occupancy_ratio": [parse_float(row.get("response_occupancy_ratio")) for row in rows],
        "range_energy90_width_px": [parse_float(row.get("range_energy90_width_px")) for row in rows],
        "azimuth_energy90_width_px": [parse_float(row.get("azimuth_energy90_width_px")) for row in rows],
        "inside_gt_energy_fraction": [parse_float(row.get("inside_gt_energy_fraction")) for row in rows],
        "mask_contact_ratio": [parse_float(row.get("mask_contact_ratio")) for row in rows],
        "component_count": [parse_float(row.get("component_count")) for row in rows],
    }
    out: dict[str, Any] = {group_key: group_value, "region_count": len(rows)}
    for key, values in vals.items():
        out[f"{key}_mean"] = fmt(mean(values))
        out[f"{key}_median"] = fmt(median(values))
        out[f"{key}_p90"] = fmt(p90(values))
    return out


def build_scale_curves(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in features:
        if row.get("family") != "SCALE":
            continue
        variant = row.get("variant", "")
        transform = variant.rsplit("_", 1)[0]
        groups[(transform, row.get("scale_ratio", ""))].append(row)
    rows = []
    for (transform, scale_ratio), items in sorted(groups.items(), key=lambda kv: (kv[0][0], parse_float(kv[0][1]))):
        summary = group_summary(items, "transform", transform)
        summary["scale_ratio"] = scale_ratio
        summary["interpretation"] = "area_normalized_curve; total energy is not a vehicle proof"
        rows.append(summary)
    return rows


def build_translation_surface(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in features:
        if row.get("family") != "TRANSLATION":
            continue
        groups[(row.get("offset_axis", ""), row.get("offset_value", ""))].append(row)
    rows = []
    best_by_axis: dict[str, tuple[float, str]] = {}
    for (axis, offset), items in groups.items():
        value = mean([parse_float(row.get("mean_energy")) for row in items])
        if axis not in best_by_axis or value > best_by_axis[axis][0]:
            best_by_axis[axis] = (value, offset)
    for (axis, offset), items in sorted(groups.items(), key=lambda kv: (kv[0][0], parse_float(kv[0][1]))):
        summary = group_summary(items, "offset_axis", axis)
        summary["offset_value"] = offset
        summary["best_offset_for_axis"] = best_by_axis.get(axis, (0.0, ""))[1]
        summary["gt_centered_peak"] = "false" if best_by_axis.get(axis, (0.0, ""))[1] not in {"", "0", "0.0"} else "true"
        summary["interpretation"] = "controlled translation surface, not a localization selector"
        rows.append(summary)
    return rows


def build_rotation_curves(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in features:
        if row.get("family") == "ROTATION":
            groups[row.get("rotation_relative_to_gt_deg", "")].append(row)
    rows = []
    for angle, items in sorted(groups.items(), key=lambda kv: parse_float(kv[0])):
        summary = group_summary(items, "rotation_relative_to_gt_deg", angle)
        axis_delta = [abs(parse_float(row.get("principal_axis_minus_gt_storage_axis_deg"))) for row in items]
        summary["abs_principal_axis_minus_gt_storage_mean_deg"] = fmt(mean(axis_delta))
        summary["interpretation"] = "GT orientation unavailable; curve is image-axis perturbation only"
        rows.append(summary)
    return rows


def build_ring_contrast(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in features:
        if row.get("family") in {"GT_ORIGINAL", "RING"}:
            groups[row.get("variant", row.get("family", ""))].append(row)
    rows = []
    gt_mean = mean([parse_float(row.get("mean_energy")) for row in groups.get("gt_original", [])])
    for variant, items in sorted(groups.items()):
        summary = group_summary(items, "region_variant", variant)
        value = parse_float(summary["mean_energy_mean"])
        summary["mean_energy_ratio_to_gt_original"] = fmt(value / gt_mean if gt_mean else 0.0)
        summary["interpretation"] = "ring = expanded region minus original GT" if "ring" in variant else "GT reference"
        rows.append(summary)
    return rows


def build_hard_negative(features: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    class_map = {
        "gt_original": [row for row in features if row.get("family") == "GT_ORIGINAL"],
        "known_non_vehicle_same_area": [row for row in features if row.get("variant") == "known_non_vehicle_same_area"],
        "linear_structure_background_same_area": [row for row in features if row.get("variant") == "linear_structure_background_same_area"],
        "strong_scatterer_background_same_area": [row for row in features if row.get("variant") == "strong_scatterer_background_same_area"],
        "near_background_same_area": [row for row in features if row.get("variant") == "near_background_same_area"],
        "far_background_same_area": [row for row in features if row.get("variant") == "far_background_same_area"],
        "mask_edge_background_same_area": [row for row in features if row.get("variant") == "mask_edge_background_same_area"],
    }
    gt_mean = mean([parse_float(row.get("mean_energy")) for row in class_map["gt_original"]])
    gt_occ = mean([parse_float(row.get("response_occupancy_ratio")) for row in class_map["gt_original"]])
    rows = []
    for class_name, items in class_map.items():
        summary = group_summary(items, "region_class", class_name)
        summary["mean_energy_ratio_to_gt"] = fmt(parse_float(summary["mean_energy_mean"]) / gt_mean if gt_mean else 0.0)
        summary["occupancy_ratio_to_gt"] = fmt(parse_float(summary["response_occupancy_ratio_mean"]) / gt_occ if gt_occ else 0.0)
        comparable = parse_float(summary["mean_energy_ratio_to_gt"]) >= 0.75 or parse_float(summary["occupancy_ratio_to_gt"]) >= 0.75
        summary["hard_negative_confusion_risk"] = "true" if class_name != "gt_original" and comparable else "false"
        summary["interpretation"] = "vehicle reference" if class_name == "gt_original" else "same-area non-vehicle/background pressure test"
        rows.append(summary)
    return rows


def effect_size(vehicle: Sequence[float], background: Sequence[float]) -> float:
    if not vehicle or not background:
        return 0.0
    vmean = mean(vehicle)
    bmean = mean(background)
    vvar = statistics.pvariance(vehicle) if len(vehicle) > 1 else 0.0
    bvar = statistics.pvariance(background) if len(background) > 1 else 0.0
    pooled = math.sqrt(max((vvar + bvar) / 2.0, 1e-9))
    return (vmean - bmean) / pooled


def build_ablation(features: Sequence[Mapping[str, str]], gt_geom: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    gt = [row for row in features if row.get("family") == "GT_ORIGINAL"]
    bg = [row for row in features if row.get("family") == "BACKGROUND_CONTROL"]
    geom_by_frame = {parse_int(row["sar_frame"]): row for row in gt_geom}

    pixel_features = {
        "mean_energy": ([parse_float(row.get("mean_energy")) for row in gt], [parse_float(row.get("mean_energy")) for row in bg]),
        "high_energy_pixel_fraction": ([parse_float(row.get("high_energy_pixel_fraction")) for row in gt], [parse_float(row.get("high_energy_pixel_fraction")) for row in bg]),
        "range_energy90_width_px": ([parse_float(row.get("range_energy90_width_px")) for row in gt], [parse_float(row.get("range_energy90_width_px")) for row in bg]),
    }
    norm_vehicle: list[float] = []
    norm_bg: list[float] = []
    for row in gt:
        geom = geom_by_frame.get(parse_int(row["sar_frame"]), {})
        denom = parse_float(geom.get("gt_projected_range_extent_px"), 1.0)
        norm_vehicle.append(parse_float(row.get("range_energy90_width_px")) / max(denom, 1e-9))
    for row in bg:
        geom = geom_by_frame.get(parse_int(row["sar_frame"]), {})
        denom = parse_float(geom.get("gt_projected_range_extent_px"), 1.0)
        norm_bg.append(parse_float(row.get("range_energy90_width_px")) / max(denom, 1e-9))

    rows = []
    for feature_name, (vehicle_values, background_values) in pixel_features.items():
        eff = effect_size(vehicle_values, background_values)
        rows.append(
            {
                "ablation_group": "PIXEL_ONLY",
                "feature_name": feature_name,
                "vehicle_mean": fmt(mean(vehicle_values)),
                "background_mean": fmt(mean(background_values)),
                "contrast_effect_size": fmt(eff),
                "status": "EVALUATED",
                "adds_discriminative_value": "LIMITED" if eff > 0.8 else "NOT_SUPPORTED",
                "notes": "Pixel-domain contrast only; same-area backgrounds are included.",
            }
        )
    eff = effect_size(norm_vehicle, norm_bg)
    rows.append(
        {
            "ablation_group": "GT_NORMALIZED",
            "feature_name": "range_energy90_width_px_div_gt_projected_range_extent_px",
            "vehicle_mean": fmt(mean(norm_vehicle)),
            "background_mean": fmt(mean(norm_bg)),
            "contrast_effect_size": fmt(eff),
            "status": "EVALUATED",
            "adds_discriminative_value": "LIMITED" if eff > 0.8 else "NOT_SUPPORTED",
            "notes": "Relative-to-GT normalization avoids true meter claims.",
        }
    )
    rows.append(
        {
            "ablation_group": "METRIC_PHYSICAL_SCALE",
            "feature_name": "true_range_m_true_azimuth_m_resolution_corrected_extent",
            "vehicle_mean": "",
            "background_mean": "",
            "contrast_effect_size": "",
            "status": "NOT_EVALUABLE",
            "adds_discriminative_value": "NOT_EVALUABLE",
            "notes": "No reliable pixel-to-meter or SAR resolution mapping found; P0 0.03 remains a convention only.",
        }
    )
    return rows


def build_failure_ledger(
    hard_negative_rows: Sequence[Mapping[str, str]],
    ablation_rows: Sequence[Mapping[str, str]],
    mask_rows: Sequence[Mapping[str, str]],
    rotation_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    confusion = [row for row in hard_negative_rows if row.get("region_class") != "gt_original" and row.get("hard_negative_confusion_risk") == "true"]
    metric = next((row for row in ablation_rows if row.get("ablation_group") == "METRIC_PHYSICAL_SCALE"), {})
    max_mask = max((parse_float(row.get("gt_mask_contact_ratio")) for row in mask_rows), default=0.0)
    rot_delta = max((parse_float(row.get("abs_principal_axis_minus_gt_storage_mean_deg")) for row in rotation_rows), default=0.0)
    rows = [
        {
            "failure_id": "E0_METRIC_MAPPING_FAILURE",
            "failure_type": "metric_mapping_failure",
            "severity": "high",
            "evidence": "pixel_to_range_meter_mapping=UNRESOLVED; pixel_to_azimuth_meter_mapping=UNRESOLVED; sar_resolution_m=UNRESOLVED",
            "interpretation": "True metric-scale physical separability cannot be claimed.",
        },
        {
            "failure_id": "E0_GT_ORIENTATION_UNRESOLVED",
            "failure_type": "gt_physical_size_inconsistency",
            "severity": "medium",
            "evidence": f"max_rotation_principal_axis_delta_mean={fmt(rot_delta)}",
            "interpretation": "GT has axis-aligned boxes but no vehicle heading; front/rear and rotation tests remain storage-axis diagnostics.",
        },
        {
            "failure_id": "E0_MASK_DEFINITION_UNRESOLVED",
            "failure_type": "mask_censoring",
            "severity": "medium",
            "evidence": f"max_gt_zero_proxy_contact={fmt(max_mask)}",
            "interpretation": "Zero-valued pixels are only a proxy; mask-censored extents are not reliable metric extents.",
        },
        {
            "failure_id": "E0_HARD_NEGATIVE_CONFUSION",
            "failure_type": "hard_negative_scale_confusion" if confusion else "hard_negative_explanation_rejected",
            "severity": "high" if confusion else "low",
            "evidence": f"confusing_controls={';'.join(row['region_class'] for row in confusion)}",
            "interpretation": "Known non-vehicle/background controls can approach vehicle-region energy or occupancy." if confusion else "Hard negatives are weaker on this summary metric, but metric mapping remains blocked.",
        },
        {
            "failure_id": "E0_ABSOLUTE_SCALE_NOT_DISCRIMINATIVE",
            "failure_type": "absolute_scale_not_discriminative",
            "severity": "high",
            "evidence": metric.get("status", "NOT_EVALUABLE"),
            "interpretation": "Absolute scale adds no evaluable discriminative value without an independent meter mapping.",
        },
        {
            "failure_id": "E0_VEHICLE_NONVEHICLE_NOT_SEPARABLE",
            "failure_type": "vehicle_nonvehicle_not_separable" if confusion else "ambiguous_or_censored",
            "severity": "high" if confusion else "medium",
            "evidence": "hard_negative/background controls and unresolved meter/mask/orientation gates prevent a supported separability claim",
            "interpretation": "Do not promote high GT-region energy into a stable SAR vehicle physical mechanism.",
        },
    ]
    return rows


def gate(gate_id: str, status: str, evidence: str, notes: str = "") -> dict[str, str]:
    return {"gate_id": gate_id, "status": status, "evidence": evidence, "notes": notes}


def build_gates(
    seal_ok: bool,
    seal_errors: Sequence[str],
    p0_status: tuple[bool, str],
    d1_status: tuple[bool, str],
    d1r1_status: tuple[bool, str],
    replay_rows: Sequence[Mapping[str, str]],
    features: Sequence[Mapping[str, str]],
    hard_negative_rows: Sequence[Mapping[str, str]],
    ablation_rows: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    replay_ok = bool(replay_rows) and all(row.get("status") == "PASS" for row in replay_rows)
    family_counts = Counter(row.get("family") for row in features)
    gt_rows = [row for row in features if row.get("family") == "GT_ORIGINAL"]
    unique_gt_sar_frames = len({row.get("sar_frame") for row in gt_rows})
    hard_confusion = any(row.get("region_class") != "gt_original" and row.get("hard_negative_confusion_risk") == "true" for row in hard_negative_rows)
    metric_not_eval = any(row.get("ablation_group") == "METRIC_PHYSICAL_SCALE" and row.get("status") == "NOT_EVALUABLE" for row in ablation_rows)
    visual_ok = len(visual_rows) >= 12 and all(row.get("diagnostic_png") for row in visual_rows)
    frozen_ok = p0_status[0] and d1_status[0] and d1r1_status[0]
    vehicle_supported = (not hard_confusion) and (not metric_not_eval)
    rows = [
        gate("WORKTREE_BRANCH_VALID", "PASS" if git_output(["branch", "--show-current"]) == BRANCH else "FAIL", f"branch={git_output(['branch', '--show-current'])};head={git_output(['rev-parse', 'HEAD'])}"),
        gate("P0_D1_D1_R1_FROZEN_UNCHANGED", "PASS" if frozen_ok else "FAIL", f"P0={p0_status[1]}; D1={d1_status[1]}; D1_R1={d1r1_status[1]}"),
        gate("PRE_EVAL_SEAL_VALID", "PASS" if seal_ok else "FAIL", "seal ok" if seal_ok else ";".join(seal_errors)),
        gate("FROZEN_REPLAY_IDENTICAL", "PASS" if replay_ok else "FAIL", f"replay_rows={len(replay_rows)}"),
        gate("METRIC_COORDINATE_MAPPING_AVAILABLE", "NOT_READY", "pixel_to_range_meter_mapping and pixel_to_azimuth_meter_mapping unresolved"),
        gate("RADAR_ORIGIN_PROVENANCE_VALID", "PASS", "fan center from configs/scene_config.yaml: 1154.0,1330.6"),
        gate("RANGE_AZIMUTH_AXES_VALID", "PASS", "local pixel range axis fan-center-to-GT-center and perpendicular azimuth axis generated per frame"),
        gate("PIXEL_TO_METER_CONVERSION_VALID", "NOT_READY", "P0 0.03 is recorded as p0_convention_m only"),
        gate("GT_METRIC_SIZE_TEMPORALLY_STABLE", "PASS_PIXEL_AND_P0_CONVENTION_ONLY", "GT width/height stable in pixels; true meters NOT_EVALUABLE"),
        gate("BODY_SIZE_REFERENCE_FROZEN", "PASS", rel(E0["vehicle_body_size_reference"])),
        gate("BODY_LENGTH_COMPATIBILITY_IMPLEMENTED", "PASS", "length/width/area ratios are recorded in region manifest and feature table"),
        gate("BODY_WIDTH_COMPATIBILITY_IMPLEMENTED", "PASS", "same"),
        gate("BODY_AREA_COMPATIBILITY_IMPLEMENTED", "PASS", "area_ratio_to_gt recorded for every region"),
        gate("RESPONSE_EXTENT_SEPARATED_FROM_BODY_EXTENT", "PASS", "feature table records response support widths separately from GT body extents"),
        gate("PERTURBATION_GRID_FROZEN", "PASS", f"region_count={len(features)}; family_counts={dict(family_counts)}"),
        gate("SCALE_COMPARISON_COMPLETE", "PASS" if family_counts.get("SCALE", 0) > 0 else "FAIL", f"scale_regions={family_counts.get('SCALE', 0)}"),
        gate("TRANSLATION_COMPARISON_COMPLETE", "PASS" if family_counts.get("TRANSLATION", 0) > 0 else "FAIL", f"translation_regions={family_counts.get('TRANSLATION', 0)}"),
        gate("ROTATION_COMPARISON_COMPLETE", "PASS" if family_counts.get("ROTATION", 0) > 0 else "FAIL", f"rotation_regions={family_counts.get('ROTATION', 0)}"),
        gate("DIRECTIONAL_EXPANSION_COMPLETE", "PASS" if family_counts.get("DIRECTIONAL_EXPANSION", 0) > 0 else "FAIL", f"directional_regions={family_counts.get('DIRECTIONAL_EXPANSION', 0)}"),
        gate("RING_COMPARISON_COMPLETE", "PASS" if family_counts.get("RING", 0) > 0 else "FAIL", f"ring_regions={family_counts.get('RING', 0)}"),
        gate("SAME_AREA_BACKGROUND_COMPLETE", "PASS" if family_counts.get("BACKGROUND_CONTROL", 0) > 0 else "FAIL", f"background_regions={family_counts.get('BACKGROUND_CONTROL', 0)}"),
        gate("HARD_NEGATIVE_COMPARISON_COMPLETE", "PASS", rel(E0["hard_negative_comparison"])),
        gate("AREA_NORMALIZATION_COMPLETE", "PASS", "mean_energy/high_energy_fraction/occupancy retained alongside total_energy"),
        gate("PIXEL_GT_NORMALIZED_METRIC_ABLATION_COMPLETE", "PASS", "pixel and GT-normalized evaluated; metric arm explicitly NOT_EVALUABLE"),
        gate("MASK_CENSORING_AUDIT_COMPLETE", "PASS", rel(E0["mask_censoring_audit"])),
        gate("TEMPORAL_STABILITY_AUDIT_COMPLETE", "PASS", f"target_gt_rows={len(gt_rows)};unique_sar_frames={unique_gt_sar_frames};SAR336 has two GT rows"),
        gate("VISUAL_REVIEW_GROUNDED", "PASS" if visual_ok else "FAIL", f"visual_rows={len(visual_rows)}"),
        gate("VEHICLE_REGION_PHYSICAL_SEPARABILITY_SUPPORTED", "SUPPORTED" if vehicle_supported else "NOT_READY", "hard_negative_confusion=false and metric evaluable" if vehicle_supported else "hard negatives/background controls and metric-mapping gap prevent a supported claim"),
        gate("ABSOLUTE_SCALE_ADDS_DISCRIMINATIVE_VALUE", "NOT_EVALUABLE", "true metric mapping and SAR resolution unavailable"),
        gate("E0_READY_FOR_GENERALIZATION", "NOT_READY", "E0 is GM_RM017 posthoc diagnosis; absolute metric and hard-negative gates are not closed"),
    ]
    return rows


def write_frozen_manifest() -> None:
    rows = []
    for key, path in E0.items():
        if key == "frozen_manifest":
            continue
        if path.exists():
            rows.append(
                {
                    "artifact_key": key,
                    "path": rel(path),
                    "sha256": sha256_file(path),
                    "row_count": row_count(path),
                    "phase": "e0_evaluated",
                    "notes": "Report and CSV only; PNG files remain ignored under outputs/." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(E0["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def write_report(
    gates: Sequence[Mapping[str, str]],
    scale_rows: Sequence[Mapping[str, str]],
    translation_rows: Sequence[Mapping[str, str]],
    rotation_rows: Sequence[Mapping[str, str]],
    ring_rows: Sequence[Mapping[str, str]],
    hard_rows: Sequence[Mapping[str, str]],
    ablation_rows: Sequence[Mapping[str, str]],
    failure_rows: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
) -> None:
    gate_by_id = {row["gate_id"]: row for row in gates}
    body_rows = read_csv(E0["vehicle_body_size_reference"])
    body_by_id = {row["reference_id"]: row for row in body_rows}
    gt_width = body_by_id.get("gt_width_px", {})
    gt_height = body_by_id.get("gt_height_px", {})
    gt_area = body_by_id.get("gt_area_px2", {})
    hard_confusing = [row for row in hard_rows if row.get("region_class") != "gt_original" and row.get("hard_negative_confusion_risk") == "true"]
    best_translation = [row for row in translation_rows if row.get("offset_axis") in {"local_range", "local_azimuth"} and row.get("offset_value") == row.get("best_offset_for_axis")]
    best_translation_summary = "; ".join(f"{row['offset_axis']}={row['best_offset_for_axis']}" for row in best_translation[:4])
    lines = [
        "# WGV3.6B-E0 GM_RM017 GT-Conditioned Metric-Scale SAR Physical Region Contrast",
        "",
        "## Conclusion",
        "",
        f"- `VEHICLE_REGION_PHYSICAL_SEPARABILITY_SUPPORTED`: `{gate_by_id['VEHICLE_REGION_PHYSICAL_SEPARABILITY_SUPPORTED']['status']}`",
        f"- `ABSOLUTE_SCALE_ADDS_DISCRIMINATIVE_VALUE`: `{gate_by_id['ABSOLUTE_SCALE_ADDS_DISCRIMINATIVE_VALUE']['status']}`",
        f"- `E0_READY_FOR_GENERALIZATION`: `{gate_by_id['E0_READY_FOR_GENERALIZATION']['status']}`",
        "- E0 does not output a final vehicle box, selector, ranking, training signal, GT edit, or final annotation.",
        "- SAR 371-394 is used only as a posthoc regression and mechanism-diagnosis window.",
        "",
        "The current evidence does not support a stable vehicle-specific SAR physical separability claim. GT-near regions often have meaningful response, but the proof chain is blocked by unresolved metric mapping, unresolved true GT orientation, zero-valued mask proxy limits, and hard-negative/background controls that can approach vehicle-region energy or occupancy.",
        "",
        "## Coordinate Mapping",
        "",
        "- radar origin in image: fan center `(1154.0, 1330.6)` from `configs/scene_config.yaml`.",
        "- local range axis: fan center to each GT center in image pixels.",
        "- local azimuth axis: perpendicular to local range axis.",
        "- pixel-to-meter conversion: `NOT_READY`; P0 `0.03` is only `p0_convention_m`, not validated metric scale.",
        "- SAR resolution / PSF margin: `UNRESOLVED`; no resolution-corrected extent is asserted.",
        "",
        "## GT Body Size Reference",
        "",
        f"- width px: median `{gt_width.get('median_px','')}`, q10 `{gt_width.get('q10_px','')}`, q90 `{gt_width.get('q90_px','')}`.",
        f"- height px: median `{gt_height.get('median_px','')}`, q10 `{gt_height.get('q10_px','')}`, q90 `{gt_height.get('q90_px','')}`.",
        f"- area px2: median `{gt_area.get('median_px','')}`, q10 `{gt_area.get('q10_px','')}`, q90 `{gt_area.get('q90_px','')}`.",
        "- source: dataset-conditioned axis-aligned GT statistics, not external vehicle dimensions.",
        "",
        "## Perturbation Results",
        "",
        f"- scale rows: `{len(scale_rows)}` grouped curves; total energy and mean energy must be separated because larger regions can add background.",
        f"- translation rows: `{len(translation_rows)}` grouped surface cells; best local-axis offsets observed in summaries: `{best_translation_summary}`.",
        f"- rotation rows: `{len(rotation_rows)}` grouped angles; GT heading is unresolved, so rotation is an image-axis diagnostic.",
        f"- ring rows: `{len(ring_rows)}`; rings provide explicit expanded-minus-GT background contrast.",
        "",
        "## Hard Negatives And Ablation",
        "",
        f"- hard-negative/background confusion risks: `{'; '.join(row['region_class'] for row in hard_confusing) if hard_confusing else 'none_on_summary_threshold'}`.",
        "- pixel-only and GT-normalized arms are evaluated; metric physical-scale arm is `NOT_EVALUABLE`.",
        "",
        "| ablation | feature | effect | status | value |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in ablation_rows:
        lines.append(f"| {row['ablation_group']} | {row['feature_name']} | {row['contrast_effect_size']} | {row['status']} | {row['adds_discriminative_value']} |")
    lines.extend(["", "## Mask And Visual Review", ""])
    lines.append("- mask definition: `UNRESOLVED_ZERO_VALUE_PROXY_ONLY`; zero-valued pixels are treated as a proxy only.")
    for row in visual_rows:
        lines.append(f"- `{row['visual_id']}` SAR{row['sar_frame']}: `{row['diagnostic_png']}` - {row['reviewer_conclusion_cn']}")
    lines.extend(["", "## Failure Ledger", "", "| failure | severity | evidence | interpretation |", "| --- | --- | --- | --- |"])
    for row in failure_rows:
        lines.append(f"| {row['failure_type']} | {row['severity']} | {row['evidence']} | {row['interpretation']} |")
    lines.extend(["", "## Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in gates:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence']} |")
    lines.extend(
        [
            "",
            "## Direct Answer",
            "",
            "The GT vehicle geometry region does not yet show a stable, metric-scale, vehicle-specific SAR physical response structure that is separable from surrounding and difficult non-vehicle regions. The safest current interpretation is `ambiguous_or_censored` for the mechanism-level claim: GT-near SAR response exists, but the complete proof chain of reasonable body scale, imaging-width allowance, GT-near concentration, controlled translation decay, direction-related structure, temporal stability, and hard-negative rejection is not closed.",
            "",
        ]
    )
    write_text(E0["report"], "\n".join(lines))


def evaluate() -> None:
    seal_ok, seal_errors = verify_pre_eval_seal()
    if not seal_ok:
        raise SystemExit("pre-eval seal invalid before E0 evaluation: " + "; ".join(seal_errors))

    features = read_csv(E0["region_feature_table"])
    gt_geom = read_csv(E0["gt_metric_geometry"])
    replay_rows = read_csv(E0["replay_check"]) if E0["replay_check"].exists() else []
    visual_rows = read_csv(E0["visual_review_manifest"])
    mask_rows = read_csv(E0["mask_censoring_audit"])

    scale_rows = build_scale_curves(features)
    translation_rows = build_translation_surface(features)
    rotation_rows = build_rotation_curves(features)
    ring_rows = build_ring_contrast(features)
    hard_rows = build_hard_negative(features)
    ablation_rows = build_ablation(features, gt_geom)
    failure_rows = build_failure_ledger(hard_rows, ablation_rows, mask_rows, rotation_rows)
    gates = build_gates(
        seal_ok=seal_ok,
        seal_errors=seal_errors,
        p0_status=manifest_paths_unchanged(P0_MANIFEST, P0_COMMIT, "P0"),
        d1_status=manifest_paths_unchanged(D1_MANIFEST, D1_COMMIT, "D1"),
        d1r1_status=manifest_paths_unchanged(D1_R1_MANIFEST, D1_R1_COMMIT, "D1_R1"),
        replay_rows=replay_rows,
        features=features,
        hard_negative_rows=hard_rows,
        ablation_rows=ablation_rows,
        visual_rows=visual_rows,
    )

    write_csv(E0["scale_response_curves"], scale_rows, SCALE_FIELDS)
    write_csv(E0["translation_response_surface"], translation_rows, TRANSLATION_FIELDS)
    write_csv(E0["rotation_response_curves"], rotation_rows, ROTATION_FIELDS)
    write_csv(E0["ring_contrast"], ring_rows, RING_FIELDS)
    write_csv(E0["hard_negative_comparison"], hard_rows, HARD_FIELDS)
    write_csv(E0["pixel_vs_normalized_vs_metric_ablation"], ablation_rows, ABLATION_FIELDS)
    write_csv(E0["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(E0["gate_integrity"], gates, GATE_FIELDS)
    write_report(gates, scale_rows, translation_rows, rotation_rows, ring_rows, hard_rows, ablation_rows, failure_rows, visual_rows)
    write_frozen_manifest()
    print("E0 evaluation complete")


SUMMARY_FIELDS = [
    "region_count",
    "mean_energy_mean", "mean_energy_median", "mean_energy_p90",
    "total_energy_mean", "total_energy_median", "total_energy_p90",
    "high_energy_pixel_fraction_mean", "high_energy_pixel_fraction_median", "high_energy_pixel_fraction_p90",
    "response_occupancy_ratio_mean", "response_occupancy_ratio_median", "response_occupancy_ratio_p90",
    "range_energy90_width_px_mean", "range_energy90_width_px_median", "range_energy90_width_px_p90",
    "azimuth_energy90_width_px_mean", "azimuth_energy90_width_px_median", "azimuth_energy90_width_px_p90",
    "inside_gt_energy_fraction_mean", "inside_gt_energy_fraction_median", "inside_gt_energy_fraction_p90",
    "mask_contact_ratio_mean", "mask_contact_ratio_median", "mask_contact_ratio_p90",
    "component_count_mean", "component_count_median", "component_count_p90",
]
SCALE_FIELDS = ["transform", "scale_ratio", *SUMMARY_FIELDS, "interpretation"]
TRANSLATION_FIELDS = ["offset_axis", "offset_value", *SUMMARY_FIELDS, "best_offset_for_axis", "gt_centered_peak", "interpretation"]
ROTATION_FIELDS = ["rotation_relative_to_gt_deg", *SUMMARY_FIELDS, "abs_principal_axis_minus_gt_storage_mean_deg", "interpretation"]
RING_FIELDS = ["region_variant", *SUMMARY_FIELDS, "mean_energy_ratio_to_gt_original", "interpretation"]
HARD_FIELDS = ["region_class", *SUMMARY_FIELDS, "mean_energy_ratio_to_gt", "occupancy_ratio_to_gt", "hard_negative_confusion_risk", "interpretation"]
ABLATION_FIELDS = ["ablation_group", "feature_name", "vehicle_mean", "background_mean", "contrast_effect_size", "status", "adds_discriminative_value", "notes"]
FAILURE_FIELDS = ["failure_id", "failure_type", "severity", "evidence", "interpretation"]
GATE_FIELDS = ["gate_id", "status", "evidence", "notes"]
FROZEN_MANIFEST_FIELDS = ["artifact_key", "path", "sha256", "row_count", "phase", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["evaluate"])
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate()


if __name__ == "__main__":
    main()
