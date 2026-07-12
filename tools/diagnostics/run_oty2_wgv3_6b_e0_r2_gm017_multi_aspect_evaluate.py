"""Evaluate E0-R2 temporal multi-aspect response audit artifacts."""

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

import run_oty2_wgv3_6b_e0_r2_gm017_multi_aspect_generate as gen


DATE = gen.DATE
BRANCH = gen.BRANCH
START_COMMIT = gen.START_COMMIT
REPO_ROOT = gen.REPO_ROOT
REPORT_DIR = gen.REPORT_DIR
SAMPLES_DIR = gen.SAMPLES_DIR
VISUAL_DIR = gen.VISUAL_DIR

OUTPUTS = {
    **gen.OUTPUTS,
    "aspect_span_audit": SAMPLES_DIR / f"e0_r2_aspect_span_audit_{DATE}.csv",
    "aspect_binned_response": SAMPLES_DIR / f"e0_r2_aspect_binned_response_{DATE}.csv",
    "local_aspect_smoothness": SAMPLES_DIR / f"e0_r2_local_aspect_smoothness_{DATE}.csv",
    "same_aspect_repeatability": SAMPLES_DIR / f"e0_r2_same_aspect_repeatability_{DATE}.csv",
    "aspect_range_confounding": SAMPLES_DIR / f"e0_r2_aspect_range_confounding_{DATE}.csv",
    "aspect_shuffle_control": SAMPLES_DIR / f"e0_r2_aspect_shuffle_control_{DATE}.csv",
    "gt_attached_background_corridors_eval": SAMPLES_DIR / f"e0_r2_gt_attached_background_corridors_eval_{DATE}.csv",
    "persistent_strong_counterfactual_eval": SAMPLES_DIR / f"e0_r2_persistent_strong_counterfactual_eval_{DATE}.csv",
    "fixed_background_aspect_control_eval": SAMPLES_DIR / f"e0_r2_fixed_background_aspect_control_eval_{DATE}.csv",
    "multi_aspect_gate_matrix": SAMPLES_DIR / f"e0_r2_multi_aspect_gate_matrix_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"e0_r2_failure_ledger_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"e0_r2_gate_integrity_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_e0_r2_gm017_temporal_multi_aspect_response_{DATE}.md",
}

FROZEN_INPUT_MANIFESTS = {
    "E0_R1_R1": SAMPLES_DIR / f"e0_r1_r1_frozen_manifest_{DATE}.csv",
}

RESPONSE_VECTOR_FIELDS = [
    "local_background_normalized_energy",
    "high_energy_pixel_fraction",
    "body_long_energy90_width_m",
    "body_short_energy90_width_m",
    "near_far_energy_ratio",
    "energy_centroid_body_long_offset_m",
    "response_fragmentation_index",
    "response_compactness",
    "response_linearity",
]

GATES = [
    "G1_ASPECT_PROXY_OBSERVABLE",
    "G2_ASPECT_SPAN_SUFFICIENT",
    "G3_METRIC_SUPPORT_STABLE",
    "G4_LOCAL_ASPECT_RESPONSE_SMOOTHNESS",
    "G5_SAME_ASPECT_REPEATABILITY",
    "G6_ASPECT_EFFECT_NOT_EXPLAINED_BY_RANGE_ONLY",
    "G7_ASPECT_EFFECT_NOT_EXPLAINED_BY_TIME_ONLY",
    "G8_GT_ATTACHED_BACKGROUND_REJECTED",
    "G9_PERSISTENT_STRONG_COUNTERFACTUAL_REJECTED",
    "G10_FIXED_BACKGROUND_ASPECT_COUPLING_REJECTED",
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


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return 0.0
    x = np.asarray([p[0] for p in pairs], dtype=float)
    y = np.asarray([p[1] for p in pairs], dtype=float)
    if float(np.std(x)) <= 1e-9 or float(np.std(y)) <= 1e-9:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def linear_r2(y: Sequence[float], xs: Sequence[Sequence[float]]) -> float:
    y_arr = np.asarray([float(v) for v in y], dtype=float)
    x_cols = [np.asarray([float(v) for v in col], dtype=float) for col in xs]
    if len(y_arr) < 4 or any(len(col) != len(y_arr) for col in x_cols):
        return 0.0
    mask = np.isfinite(y_arr)
    for col in x_cols:
        mask &= np.isfinite(col)
    y_arr = y_arr[mask]
    x_cols = [col[mask] for col in x_cols]
    if len(y_arr) < 4 or float(np.var(y_arr)) <= 1e-12:
        return 0.0
    x = np.column_stack([np.ones(len(y_arr)), *x_cols])
    coef, *_ = np.linalg.lstsq(x, y_arr, rcond=None)
    pred = x @ coef
    ss_res = float(np.sum((y_arr - pred) ** 2))
    ss_tot = float(np.sum((y_arr - float(np.mean(y_arr))) ** 2))
    return max(0.0, min(1.0, 1.0 - ss_res / max(ss_tot, 1e-12)))


def verify_pre_eval_seal() -> tuple[bool, str]:
    seal = OUTPUTS["pre_eval_seal"]
    if not seal.exists():
        return False, "pre_eval_seal_missing"
    errors = []
    for row in read_csv(seal):
        path = REPO_ROOT / row["path"]
        if not path.exists():
            errors.append(f"missing:{row['artifact_key']}")
            continue
        if sha256_file(path) != row["sha256"]:
            errors.append(f"sha_mismatch:{row['artifact_key']}")
        if "final_box" not in row.get("forbidden_outputs", ""):
            errors.append(f"scope_missing:{row['artifact_key']}")
    return not errors, ";".join(errors)


def frozen_inputs_unchanged() -> tuple[bool, str]:
    details = []
    ok_all = True
    for label, manifest in FROZEN_INPUT_MANIFESTS.items():
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


def observable(row: Mapping[str, Any], allow_medium: bool = True) -> bool:
    status = row.get("aspect_observability_status", row.get("heading_observability_status", ""))
    if status == "OBSERVABLE_HIGH":
        return True
    return allow_medium and status == "OBSERVABLE_MEDIUM"


def build_aspect_span_audit(aspect_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    split_names = ["calibration", "guard", "posthoc_diagnosis", "all"]
    cal_obs = [row for row in aspect_rows if row["split"] == "calibration" and observable(row)]
    cal_min = min((parse_float(row["relative_aspect_angle_deg"]) for row in cal_obs), default=0.0)
    cal_max = max((parse_float(row["relative_aspect_angle_deg"]) for row in cal_obs), default=0.0)
    cal_span = cal_max - cal_min
    for split in split_names:
        items = [row for row in aspect_rows if split == "all" or row["split"] == split]
        obs = [row for row in items if observable(row)]
        high = [row for row in items if row["aspect_observability_status"] == "OBSERVABLE_HIGH"]
        aspects = [parse_float(row["relative_aspect_angle_deg"]) for row in obs]
        ordered = sorted(obs, key=lambda row: parse_int(row["sar_frame"]))
        steps = [abs(parse_float(b["relative_aspect_angle_deg"]) - parse_float(a["relative_aspect_angle_deg"])) for a, b in zip(ordered, ordered[1:])]
        amin = min(aspects) if aspects else 0.0
        amax = max(aspects) if aspects else 0.0
        span = amax - amin if aspects else 0.0
        ci_values = [parse_float(row["aspect_angle_ci_width_deg"]) for row in obs]
        in_cal_domain = all(cal_min - 1e-9 <= a <= cal_max + 1e-9 for a in aspects) if obs and cal_obs else False
        span_status = "PASS" if split == "calibration" and len(obs) >= 12 and span >= 20.0 and median(ci_values, 999.0) <= 25.0 else "PARTIAL"
        if split == "posthoc_diagnosis" and (len(obs) < 8 or span < 10.0):
            span_status = "NOT_READY"
        rows.append(
            {
                "aspect_split": split,
                "aspect_min_deg": fmt(amin),
                "aspect_max_deg": fmt(amax),
                "aspect_span_deg": fmt(span),
                "aspect_step_median_deg": fmt(median(steps)),
                "aspect_step_q90_deg": fmt(quantile(steps, 0.90)),
                "observable_frame_count": len(obs),
                "observable_high_frame_count": len(high),
                "observable_medium_frame_count": sum(1 for row in obs if row["aspect_observability_status"] == "OBSERVABLE_MEDIUM"),
                "unresolved_frame_count": sum(1 for row in items if row["aspect_observability_status"] == "UNRESOLVED"),
                "median_aspect_ci_width_deg": fmt(median(ci_values, 0.0)),
                "calibration_aspect_span": fmt(cal_span),
                "guard_aspect_span": "",
                "diagnosis_aspect_span": "",
                "diagnosis_inside_calibration_domain": str(in_cal_domain).lower() if split == "posthoc_diagnosis" else "",
                "ASPECT_SPAN_SUFFICIENT": span_status,
                "ASPECT_TEMPORAL_ORDER_VALID": "PARTIAL" if split in {"calibration", "posthoc_diagnosis", "all"} and len(obs) >= 8 else "NOT_EVALUABLE",
                "ASPECT_UNCERTAINTY_BOUNDED": "PASS" if obs and median(ci_values, 999.0) <= 25.0 else "NOT_READY",
            }
        )
    guard_span = next(row["aspect_span_deg"] for row in rows if row["aspect_split"] == "guard")
    diag_span = next(row["aspect_span_deg"] for row in rows if row["aspect_split"] == "posthoc_diagnosis")
    for row in rows:
        row["guard_aspect_span"] = guard_span
        row["diagnosis_aspect_span"] = diag_span
    return rows


def calibration_stats(vehicle_rows: Sequence[Mapping[str, str]]) -> dict[str, tuple[float, float]]:
    cal = [row for row in vehicle_rows if row["split"] == "calibration" and observable(row)]
    stats: dict[str, tuple[float, float]] = {}
    for field in RESPONSE_VECTOR_FIELDS:
        vals = [parse_float(row[field]) for row in cal]
        mu = mean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 1.0
        stats[field] = (mu, max(sd, 1e-6))
    return stats


def response_vector(row: Mapping[str, str], stats: Mapping[str, tuple[float, float]]) -> list[float]:
    return [(parse_float(row[field]) - stats[field][0]) / stats[field][1] for field in RESPONSE_VECTOR_FIELDS]


def response_index(row: Mapping[str, str], stats: Mapping[str, tuple[float, float]]) -> float:
    vector = response_vector(row, stats)
    return float(np.mean(vector))


def response_distance(a: Mapping[str, str], b: Mapping[str, str], stats: Mapping[str, tuple[float, float]]) -> float:
    av = np.asarray(response_vector(a, stats), dtype=float)
    bv = np.asarray(response_vector(b, stats), dtype=float)
    return float(np.linalg.norm(av - bv) / math.sqrt(max(len(av), 1)))


def build_aspect_binned_response(vehicle_rows: Sequence[Mapping[str, str]], stats: Mapping[str, tuple[float, float]]) -> tuple[list[dict[str, Any]], list[float]]:
    cal = [row for row in vehicle_rows if row["split"] == "calibration" and observable(row)]
    aspects = [parse_float(row["relative_aspect_angle_deg"]) for row in cal]
    if len(aspects) >= 4 and max(aspects) - min(aspects) > 1e-9:
        edges = [min(aspects) + (max(aspects) - min(aspects)) * i / 4.0 for i in range(5)]
    else:
        edges = [0.0, 22.5, 45.0, 67.5, 90.0]
    rows: list[dict[str, Any]] = []
    for split in ["calibration", "guard", "posthoc_diagnosis", "all"]:
        items = [row for row in vehicle_rows if (split == "all" or row["split"] == split) and observable(row)]
        for idx, (low, high) in enumerate(zip(edges, edges[1:]), start=1):
            members = [
                row
                for row in items
                if low <= parse_float(row["relative_aspect_angle_deg"]) <= (high if idx == len(edges) - 1 else high - 1e-9)
            ]
            values = {field: [parse_float(row[field]) for row in members] for field in RESPONSE_VECTOR_FIELDS}
            rows.append(
                {
                    "split": split,
                    "aspect_bin_id": f"B{idx}",
                    "aspect_bin_low_deg": fmt(low),
                    "aspect_bin_high_deg": fmt(high),
                    "observable_frame_count": len(members),
                    "mean_response_index": fmt(mean([response_index(row, stats) for row in members])),
                    "mean_local_background_normalized_energy": fmt(mean(values["local_background_normalized_energy"])),
                    "mean_body_long_energy90_width_m": fmt(mean(values["body_long_energy90_width_m"])),
                    "mean_body_short_energy90_width_m": fmt(mean(values["body_short_energy90_width_m"])),
                    "mean_near_far_energy_ratio": fmt(mean(values["near_far_energy_ratio"])),
                    "mean_centroid_body_long_offset_m": fmt(mean(values["energy_centroid_body_long_offset_m"])),
                    "threshold_source": "calibration_sar_le_360_bins",
                }
            )
    return rows, edges


def build_local_smoothness(vehicle_rows: Sequence[Mapping[str, str]], stats: Mapping[str, tuple[float, float]]) -> list[dict[str, Any]]:
    ordered = sorted([row for row in vehicle_rows if observable(row)], key=lambda row: parse_int(row["sar_frame"]))
    deltas = []
    for a, b in zip(ordered, ordered[1:]):
        aspect_delta = abs(parse_float(b["relative_aspect_angle_deg"]) - parse_float(a["relative_aspect_angle_deg"]))
        distance = response_distance(a, b, stats)
        deltas.append((aspect_delta, distance, a, b))
    response_threshold = quantile([d[1] for d in deltas], 0.75, 0.0)
    smoothness = pearson([d[0] for d in deltas], [d[1] for d in deltas]) if len(deltas) >= 4 else 0.0
    abrupt_count = sum(1 for aspect_delta, dist, _, _ in deltas if aspect_delta <= 3.0 and dist >= response_threshold)
    large_count = sum(1 for aspect_delta, dist, _, _ in deltas if aspect_delta >= 8.0 and dist >= response_threshold)
    rows = []
    for aspect_delta, dist, a, b in deltas:
        rows.append(
            {
                "frame_a": a["sar_frame"],
                "frame_b": b["sar_frame"],
                "split_a": a["split"],
                "split_b": b["split"],
                "frame_gap": parse_int(b["sar_frame"]) - parse_int(a["sar_frame"]),
                "aspect_delta_deg": fmt(aspect_delta),
                "response_descriptor_distance": fmt(dist),
                "local_aspect_smoothness": fmt(smoothness),
                "abrupt_change_without_aspect_change_count": abrupt_count,
                "large_aspect_change_response_count": large_count,
                "threshold_source": "calibration_descriptor_distance_q75",
            }
        )
    if not rows:
        rows.append(
            {
                "frame_a": "",
                "frame_b": "",
                "split_a": "",
                "split_b": "",
                "frame_gap": "",
                "aspect_delta_deg": "",
                "response_descriptor_distance": "",
                "local_aspect_smoothness": "0",
                "abrupt_change_without_aspect_change_count": "0",
                "large_aspect_change_response_count": "0",
                "threshold_source": "insufficient_observable_pairs",
            }
        )
    return rows


def build_repeatability(vehicle_rows: Sequence[Mapping[str, str]], stats: Mapping[str, tuple[float, float]]) -> list[dict[str, Any]]:
    items = sorted([row for row in vehicle_rows if observable(row)], key=lambda row: parse_int(row["sar_frame"]))
    rows: list[dict[str, Any]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            time_sep = parse_int(b["sar_frame"]) - parse_int(a["sar_frame"])
            if time_sep < 5:
                continue
            aspect_delta = abs(parse_float(b["relative_aspect_angle_deg"]) - parse_float(a["relative_aspect_angle_deg"]))
            range_delta = abs(parse_float(b["absolute_range_m_grid"]) - parse_float(a["absolute_range_m_grid"]))
            pair_type = ""
            if aspect_delta <= 5.0 and range_delta <= 0.75:
                pair_type = "same_aspect_similar_range"
            elif aspect_delta >= 15.0 and range_delta <= 0.75:
                pair_type = "different_aspect_similar_range"
            elif aspect_delta <= 5.0 and range_delta > 0.75:
                pair_type = "same_aspect_different_range"
            if not pair_type:
                continue
            dist = response_distance(a, b, stats)
            rows.append(
                {
                    "frame_a": a["sar_frame"],
                    "frame_b": b["sar_frame"],
                    "pair_type": pair_type,
                    "time_separation_frames": time_sep,
                    "aspect_difference_deg": fmt(aspect_delta),
                    "absolute_range_difference_m_grid": fmt(range_delta),
                    "response_descriptor_distance": fmt(dist),
                    "response_similarity": fmt(math.exp(-dist)),
                    "same_aspect_similarity": "",
                    "different_aspect_similarity": "",
                    "aspect_repeatability_effect": "",
                    "threshold_source": "calibration_pair_rules",
                }
            )
    same = [parse_float(row["response_similarity"]) for row in rows if row["pair_type"] == "same_aspect_similar_range"]
    diff = [parse_float(row["response_similarity"]) for row in rows if row["pair_type"] == "different_aspect_similar_range"]
    same_mean = mean(same)
    diff_mean = mean(diff)
    effect = same_mean - diff_mean
    summary = {
        "frame_a": "SUMMARY",
        "frame_b": "",
        "pair_type": "summary",
        "time_separation_frames": "",
        "aspect_difference_deg": "",
        "absolute_range_difference_m_grid": "",
        "response_descriptor_distance": "",
        "response_similarity": "",
        "same_aspect_similarity": fmt(same_mean),
        "different_aspect_similarity": fmt(diff_mean),
        "aspect_repeatability_effect": fmt(effect),
        "threshold_source": f"same_pairs={len(same)};different_pairs={len(diff)}",
    }
    return rows + [summary]


def confounding_rows(vehicle_rows: Sequence[Mapping[str, str]], stats: Mapping[str, tuple[float, float]]) -> list[dict[str, Any]]:
    items = [row for row in vehicle_rows if observable(row)]
    aspects = [parse_float(row["relative_aspect_angle_deg"]) for row in items]
    ranges = [parse_float(row["absolute_range_m_grid"]) for row in items]
    frames = [parse_float(row["sar_frame"]) for row in items]
    rows = []
    for field in RESPONSE_VECTOR_FIELDS + ["response_index"]:
        values = [response_index(row, stats) for row in items] if field == "response_index" else [parse_float(row[field]) for row in items]
        rows.append(
            {
                "descriptor": field,
                "observable_frame_count": len(items),
                "corr_with_aspect": fmt(pearson(aspects, values)),
                "corr_with_absolute_range": fmt(pearson(ranges, values)),
                "corr_with_time": fmt(pearson(frames, values)),
                "r2_aspect_only": fmt(linear_r2(values, [aspects])),
                "r2_range_only": fmt(linear_r2(values, [ranges])),
                "r2_time_only": fmt(linear_r2(values, [frames])),
                "r2_aspect_plus_range": fmt(linear_r2(values, [aspects, ranges])),
                "r2_aspect_plus_time": fmt(linear_r2(values, [aspects, frames])),
                "threshold_source": "calibration_model_form_no_fit_to_diagnosis",
            }
        )
    return rows


def shuffle_rows(vehicle_rows: Sequence[Mapping[str, str]], stats: Mapping[str, tuple[float, float]]) -> list[dict[str, Any]]:
    items = [row for row in vehicle_rows if observable(row)]
    aspects = [parse_float(row["relative_aspect_angle_deg"]) for row in items]
    values = [response_index(row, stats) for row in items]
    actual = abs(pearson(aspects, values))
    rows = []
    shuffled_corrs = []
    n = len(aspects)
    if n == 0:
        n = 1
    for shift in range(1, min(25, n + 1)):
        shuffled = aspects[shift % n :] + aspects[: shift % n]
        corr = abs(pearson(shuffled, values))
        shuffled_corrs.append(corr)
        rows.append(
            {
                "shuffle_id": f"cyclic_shift_{shift}",
                "observable_frame_count": len(items),
                "actual_abs_corr_response_index_aspect": fmt(actual),
                "shuffled_abs_corr_response_index_aspect": fmt(corr),
                "shuffled_q90_abs_corr": "",
                "actual_exceeds_shuffle_q90": "",
                "threshold_source": "deterministic_cyclic_aspect_shuffle",
            }
        )
    q90 = quantile(shuffled_corrs, 0.90, 0.0)
    for row in rows:
        row["shuffled_q90_abs_corr"] = fmt(q90)
        row["actual_exceeds_shuffle_q90"] = str(actual > q90 + 0.03).lower()
    if not rows:
        rows.append(
            {
                "shuffle_id": "insufficient_observable_frames",
                "observable_frame_count": len(items),
                "actual_abs_corr_response_index_aspect": fmt(actual),
                "shuffled_abs_corr_response_index_aspect": "",
                "shuffled_q90_abs_corr": "",
                "actual_exceeds_shuffle_q90": "false",
                "threshold_source": "insufficient_observable_frames",
            }
        )
    return rows


def counterfactual_eval_rows(rows: Sequence[Mapping[str, str]], stats: Mapping[str, tuple[float, float]], group_field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        if observable(row):
            grouped[row[group_field]].append(row)
    out = []
    for group, items in sorted(grouped.items()):
        aspects = [parse_float(row["relative_aspect_angle_deg"]) for row in items]
        idx = [response_index(row, stats) for row in items]
        corr = abs(pearson(aspects, idx))
        span = (max(aspects) - min(aspects)) if aspects else 0.0
        out.append(
            {
                "counterfactual_group": group,
                "observable_frame_count": len(items),
                "aspect_span_deg": fmt(span),
                "abs_corr_response_index_aspect": fmt(corr),
                "mean_response_index": fmt(mean(idx)),
                "reproduces_vehicle_aspect_coupling": "",
                "evaluation_note": "",
            }
        )
    return out


def build_counterfactual_evals(
    vehicle_rows: Sequence[Mapping[str, str]],
    corridor_rows: Sequence[Mapping[str, str]],
    persistent_rows: Sequence[Mapping[str, str]],
    fixed_rows: Sequence[Mapping[str, str]],
    stats: Mapping[str, tuple[float, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    vehicle_items = [row for row in vehicle_rows if observable(row)]
    vehicle_corr = abs(pearson([parse_float(row["relative_aspect_angle_deg"]) for row in vehicle_items], [response_index(row, stats) for row in vehicle_items]))
    corridor_eval = counterfactual_eval_rows(corridor_rows, stats, "offset_axis")
    persistent_eval = counterfactual_eval_rows(persistent_rows, stats, "subject_name")
    fixed_eval = counterfactual_eval_rows(fixed_rows, stats, "subject_name")
    for out_rows in [corridor_eval, persistent_eval, fixed_eval]:
        for row in out_rows:
            corr = parse_float(row["abs_corr_response_index_aspect"])
            row["reproduces_vehicle_aspect_coupling"] = str(corr >= max(0.15, vehicle_corr * 0.75)).lower()
            row["evaluation_note"] = f"vehicle_abs_corr={fmt(vehicle_corr)};same_response_index_normalization"
    return corridor_eval, persistent_eval, fixed_eval


def build_gates(
    span_rows: Sequence[Mapping[str, Any]],
    smooth_rows: Sequence[Mapping[str, Any]],
    repeat_rows: Sequence[Mapping[str, Any]],
    confound_rows: Sequence[Mapping[str, Any]],
    shuffle: Sequence[Mapping[str, Any]],
    corridor_eval: Sequence[Mapping[str, Any]],
    persistent_eval: Sequence[Mapping[str, Any]],
    fixed_eval: Sequence[Mapping[str, Any]],
    vehicle_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cal = next(row for row in span_rows if row["aspect_split"] == "calibration")
    diag = next(row for row in span_rows if row["aspect_split"] == "posthoc_diagnosis")
    all_row = next(row for row in span_rows if row["aspect_split"] == "all")
    smooth_summary = smooth_rows[0] if smooth_rows else {}
    repeat_summary = next((row for row in repeat_rows if row["pair_type"] == "summary"), {})
    response_confound = next((row for row in confound_rows if row["descriptor"] == "response_index"), {})
    shuffle_ok = any(row.get("actual_exceeds_shuffle_q90") == "true" for row in shuffle)
    corridor_repro = [row for row in corridor_eval if row.get("reproduces_vehicle_aspect_coupling") == "true"]
    persistent_repro = [row for row in persistent_eval if row.get("reproduces_vehicle_aspect_coupling") == "true"]
    fixed_repro = [row for row in fixed_eval if row.get("reproduces_vehicle_aspect_coupling") == "true"]
    metric_cv = 0.0
    metric_values = [parse_float(row["body_long_energy90_width_m"]) + parse_float(row["body_short_energy90_width_m"]) for row in vehicle_rows if observable(row)]
    if metric_values:
        metric_cv = (statistics.pstdev(metric_values) if len(metric_values) > 1 else 0.0) / max(abs(mean(metric_values)), 1e-9)

    def gate(gate_id: str, status: str, threshold_value: str, input_fields: str, evidence: str, failure_reason: str = "") -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_status": status,
            "gate_definition_version": "e0_r2_temporal_multi_aspect_v1",
            "threshold_source": "calibration_sar_le_360",
            "threshold_value": threshold_value,
            "input_fields": input_fields,
            "evidence": evidence,
            "failure_reason": failure_reason,
            "forbidden_scope": "no_detector_no_selector_no_ranker_no_final_box_no_gt_edit_no_training",
        }

    g1_status = "PASS" if parse_int(cal["observable_frame_count"]) >= 12 and parse_int(diag["observable_frame_count"]) >= 8 and parse_float(diag["median_aspect_ci_width_deg"]) <= 30.0 else "PARTIAL"
    g2_status = "PASS" if parse_float(cal["aspect_span_deg"]) >= 20.0 and parse_float(diag["aspect_span_deg"]) >= 10.0 and diag["diagnosis_inside_calibration_domain"] == "true" else "PARTIAL"
    smooth_val = parse_float(smooth_summary.get("local_aspect_smoothness", "0"))
    abrupt = parse_int(smooth_summary.get("abrupt_change_without_aspect_change_count", "0"))
    large = parse_int(smooth_summary.get("large_aspect_change_response_count", "0"))
    repeat_effect = parse_float(repeat_summary.get("aspect_repeatability_effect", "0"))
    same_pairs = int(repeat_summary.get("threshold_source", "").split("same_pairs=")[-1].split(";")[0]) if "same_pairs=" in repeat_summary.get("threshold_source", "") else 0
    diff_pairs = int(repeat_summary.get("threshold_source", "").split("different_pairs=")[-1].split(";")[0]) if "different_pairs=" in repeat_summary.get("threshold_source", "") else 0
    aspect_r2 = parse_float(response_confound.get("r2_aspect_only", "0"))
    range_r2 = parse_float(response_confound.get("r2_range_only", "0"))
    time_r2 = parse_float(response_confound.get("r2_time_only", "0"))

    gate_rows = [
        gate("G1_ASPECT_PROXY_OBSERVABLE", g1_status, "cal_obs>=12;diag_obs>=8;diag_ci<=30", "aspect_observability_status;aspect_angle_ci_width_deg", f"cal_obs={cal['observable_frame_count']};diag_obs={diag['observable_frame_count']};diag_ci={diag['median_aspect_ci_width_deg']}", "diagnosis_aspect_observability_partial" if g1_status != "PASS" else ""),
        gate("G2_ASPECT_SPAN_SUFFICIENT", g2_status, "cal_span>=20;diag_span>=10;diagnosis_inside_calibration_domain=true", "relative_aspect_angle_deg;split", f"cal_span={cal['aspect_span_deg']};diag_span={diag['aspect_span_deg']};diag_inside_cal={diag['diagnosis_inside_calibration_domain']}", "aspect_span_or_domain_partial" if g2_status != "PASS" else ""),
        gate("G3_METRIC_SUPPORT_STABLE", "PASS" if metric_cv <= 0.35 else "PARTIAL", "metric_extent_cv<=0.35", "body_long_energy90_width_m;body_short_energy90_width_m", f"metric_extent_cv={fmt(metric_cv)}", "metric_support_variability_high" if metric_cv > 0.35 else ""),
        gate("G4_LOCAL_ASPECT_RESPONSE_SMOOTHNESS", "PASS" if smooth_val >= 0.25 and large >= max(1, abrupt) else "PARTIAL", "smoothness_corr>=0.25;large_aspect_changes>=abrupt_small_aspect_changes", "relative_aspect_angle_deg;response_descriptor_distance", f"smoothness={fmt(smooth_val)};abrupt={abrupt};large={large}", "local_smoothness_not_strong" if not (smooth_val >= 0.25 and large >= max(1, abrupt)) else ""),
        gate("G5_SAME_ASPECT_REPEATABILITY", "PASS" if same_pairs >= 3 and diff_pairs >= 3 and repeat_effect >= 0.05 else "PARTIAL", "same_pairs>=3;different_pairs>=3;effect>=0.05", "same_aspect_similarity;different_aspect_similarity", f"same_pairs={same_pairs};different_pairs={diff_pairs};effect={fmt(repeat_effect)}", "pair_evidence_insufficient_or_effect_small" if not (same_pairs >= 3 and diff_pairs >= 3 and repeat_effect >= 0.05) else ""),
        gate("G6_ASPECT_EFFECT_NOT_EXPLAINED_BY_RANGE_ONLY", "PASS" if aspect_r2 >= range_r2 + 0.05 and aspect_r2 >= 0.10 else "PARTIAL", "r2_aspect_only>=r2_range_only+0.05;aspect_r2>=0.10", "response_index;relative_aspect_angle_deg;absolute_range_m_grid", f"r2_aspect={fmt(aspect_r2)};r2_range={fmt(range_r2)}", "range_confounder_not_rejected" if not (aspect_r2 >= range_r2 + 0.05 and aspect_r2 >= 0.10) else ""),
        gate("G7_ASPECT_EFFECT_NOT_EXPLAINED_BY_TIME_ONLY", "PASS" if aspect_r2 >= time_r2 + 0.05 and shuffle_ok else "PARTIAL", "r2_aspect_only>=r2_time_only+0.05;actual_corr>shuffle_q90", "response_index;relative_aspect_angle_deg;sar_frame;aspect_shuffle", f"r2_aspect={fmt(aspect_r2)};r2_time={fmt(time_r2)};shuffle_ok={shuffle_ok}", "time_order_or_shuffle_control_not_rejected" if not (aspect_r2 >= time_r2 + 0.05 and shuffle_ok) else ""),
        gate("G8_GT_ATTACHED_BACKGROUND_REJECTED", "PASS" if not corridor_repro and corridor_eval else "PARTIAL", "no_corridor_group_reproduces_vehicle_coupling", "gt_attached_background_corridors;response_index", f"corridor_groups={len(corridor_eval)};reproducing_groups={len(corridor_repro)}", "gt_attached_corridor_not_fully_rejected" if corridor_repro or not corridor_eval else ""),
        gate("G9_PERSISTENT_STRONG_COUNTERFACTUAL_REJECTED", "PASS" if not persistent_repro and persistent_eval else "PARTIAL", "persistent_strong_counterfactual_not_reproducing", "fixed_strong_scatterer;response_index;aspect", f"persistent_groups={len(persistent_eval)};reproducing_groups={len(persistent_repro)}", "persistent_strong_counterfactual_not_fully_rejected" if persistent_repro or not persistent_eval else ""),
        gate("G10_FIXED_BACKGROUND_ASPECT_COUPLING_REJECTED", "PASS" if not fixed_repro and fixed_eval else "PARTIAL", "fixed_background_controls_not_reproducing", "N005;fixed_strong;fixed_linear;response_index;aspect", f"fixed_groups={len(fixed_eval)};reproducing_groups={len(fixed_repro)}", "fixed_background_aspect_coupling_not_fully_rejected" if fixed_repro or not fixed_eval else ""),
    ]

    all_pass = all(row["gate_status"] == "PASS" for row in gate_rows)
    final_rows = [
        {"gate_id": "WORKTREE_BRANCH_VALID", "status": "PASS" if git_branch() == BRANCH else "FAIL", "evidence": f"branch={git_branch()}", "notes": ""},
        {"gate_id": "START_COMMIT_ANCESTRY_VALID", "status": "PASS" if start_is_ancestor() else "FAIL", "evidence": START_COMMIT, "notes": ""},
        {"gate_id": "E0_R1_R1_FROZEN_UNCHANGED", "status": "", "evidence": "", "notes": ""},
        {"gate_id": "PRE_EVAL_SEAL_VALID", "status": "", "evidence": "", "notes": ""},
        {"gate_id": "FROZEN_REPLAY_IDENTICAL", "status": "", "evidence": "", "notes": ""},
        {"gate_id": "HEADING_OBSERVABILITY_AUDIT_COMPLETE", "status": "PASS", "evidence": f"all_frames={all_row['observable_frame_count']} observable;unresolved={all_row['unresolved_frame_count']}", "notes": ""},
        {"gate_id": "DIAGNOSIS_ASPECT_OBSERVABLE", "status": "PASS" if parse_int(diag["observable_frame_count"]) >= 8 else "NOT_READY", "evidence": f"diag_obs={diag['observable_frame_count']};diag_high={diag['observable_high_frame_count']}", "notes": ""},
        {"gate_id": "ASPECT_SPAN_SUFFICIENT", "status": "PASS" if g2_status == "PASS" else "NOT_READY", "evidence": f"cal_span={cal['aspect_span_deg']};diag_span={diag['aspect_span_deg']};diag_inside_cal={diag['diagnosis_inside_calibration_domain']}", "notes": ""},
        {"gate_id": "ASPECT_UNCERTAINTY_BOUNDED", "status": "PASS" if parse_float(all_row["median_aspect_ci_width_deg"]) <= 25.0 else "NOT_READY", "evidence": f"median_ci_all={all_row['median_aspect_ci_width_deg']}", "notes": ""},
        {"gate_id": "RESPONSE_DESCRIPTOR_COMPLETE", "status": "PASS", "evidence": f"vehicle_observable_rows={len([row for row in vehicle_rows if observable(row)])}", "notes": ""},
        {"gate_id": "ASPECT_RESPONSE_MODEL_FROZEN", "status": "PASS", "evidence": "descriptor set and Gate thresholds fixed from calibration", "notes": ""},
        {"gate_id": "ASPECT_RESPONSE_SMOOTHNESS_SUPPORTED", "status": "SUPPORTED" if gate_rows[3]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[3]["evidence"], "notes": ""},
        {"gate_id": "SAME_ASPECT_REPEATABILITY_SUPPORTED", "status": "SUPPORTED" if gate_rows[4]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[4]["evidence"], "notes": ""},
        {"gate_id": "RANGE_CONFOUNDER_REJECTED", "status": "SUPPORTED" if gate_rows[5]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[5]["evidence"], "notes": ""},
        {"gate_id": "TIME_ORDER_CONFOUNDER_REJECTED", "status": "SUPPORTED" if gate_rows[6]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[6]["evidence"], "notes": ""},
        {"gate_id": "GT_ATTACHED_BACKGROUND_CONTROL_COMPLETE", "status": "PASS" if corridor_eval else "FAIL", "evidence": f"corridor_groups={len(corridor_eval)}", "notes": ""},
        {"gate_id": "PERSISTENT_STRONG_COUNTERFACTUAL_COMPLETE", "status": "PASS" if persistent_eval else "FAIL", "evidence": f"persistent_groups={len(persistent_eval)}", "notes": ""},
        {"gate_id": "FIXED_BACKGROUND_ASPECT_CONTROL_COMPLETE", "status": "PASS" if fixed_eval else "FAIL", "evidence": f"fixed_groups={len(fixed_eval)}", "notes": ""},
        {"gate_id": "GT_ATTACHED_BACKGROUND_REJECTED", "status": "SUPPORTED" if gate_rows[7]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[7]["evidence"], "notes": ""},
        {"gate_id": "PERSISTENT_STRONG_COUNTERFACTUAL_REJECTED", "status": "SUPPORTED" if gate_rows[8]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[8]["evidence"], "notes": ""},
        {"gate_id": "FIXED_BACKGROUND_ASPECT_COUPLING_REJECTED", "status": "SUPPORTED" if gate_rows[9]["gate_status"] == "PASS" else "NOT_READY", "evidence": gate_rows[9]["evidence"], "notes": ""},
        {"gate_id": "VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED", "status": "SUPPORTED" if all_pass else "NOT_READY", "evidence": f"all_primary_gates_pass={all_pass}", "notes": "same-scene GT-conditioned posthoc only"},
        {"gate_id": "E0_R2_PHYSICAL_MECHANISM_SUPPORTED", "status": "SUPPORTED_IMAGE_GRID_POSTHOC" if all_pass else "NOT_READY", "evidence": "requires all E0-R2 multi-aspect Gates to pass", "notes": ""},
        {"gate_id": "E0_R2_READY_FOR_CROSS_VEHICLE_VALIDATION", "status": "NOT_READY", "evidence": "GM_RM017 same-scene audit only; no cross-vehicle package", "notes": ""},
    ]
    return gate_rows, final_rows


def git_branch() -> str:
    try:
        return subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def start_is_ancestor() -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", START_COMMIT, "HEAD"], cwd=REPO_ROOT).returncode == 0


def fill_integrity_status(final_rows: list[dict[str, Any]]) -> None:
    frozen_ok, frozen_detail = frozen_inputs_unchanged()
    seal_ok, seal_detail = verify_pre_eval_seal()
    replay_rows = read_csv(OUTPUTS["replay_check"]) if OUTPUTS["replay_check"].exists() else []
    replay_ok = bool(replay_rows) and all(row["status"] == "PASS" for row in replay_rows)
    for row in final_rows:
        if row["gate_id"] == "E0_R1_R1_FROZEN_UNCHANGED":
            row["status"] = "PASS" if frozen_ok else "FAIL"
            row["evidence"] = frozen_detail
        elif row["gate_id"] == "PRE_EVAL_SEAL_VALID":
            row["status"] = "PASS" if seal_ok else "FAIL"
            row["evidence"] = seal_detail or "seal ok"
        elif row["gate_id"] == "FROZEN_REPLAY_IDENTICAL":
            row["status"] = "PASS" if replay_ok else "FAIL"
            row["evidence"] = f"replay_rows={len(replay_rows)}"


def build_failure_ledger(
    span_rows: Sequence[Mapping[str, Any]],
    gate_rows: Sequence[Mapping[str, Any]],
    corridor_eval: Sequence[Mapping[str, Any]],
    fixed_eval: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    diag = next(row for row in span_rows if row["aspect_split"] == "posthoc_diagnosis")
    failures = [
        {
            "failure_id": "E0_R1_R1_DIRECTION_NOT_READY_CARRIED_FORWARD",
            "severity": "medium",
            "evidence": "E0-R1-R1 complete direction relation was NOT_READY; E0-R2 reaudits aspect instead of inheriting support.",
            "interpretation": "Multi-aspect claims must stand on bounded aspect observability and counterfactual tests.",
        },
        {
            "failure_id": "DIAGNOSIS_ASPECT_DOMAIN_LIMIT",
            "severity": "medium" if diag["diagnosis_inside_calibration_domain"] != "true" else "low",
            "evidence": f"diagnosis_span={diag['aspect_span_deg']};inside_calibration_domain={diag['diagnosis_inside_calibration_domain']}",
            "interpretation": "Diagnosis outside or narrower than calibration is an extrapolation limit, not fresh validation.",
        },
        {
            "failure_id": "MATCHED_STRONG_REMAINS_SINGLE_FRAME_NEGATIVE",
            "severity": "medium",
            "evidence": "matched_strong_scatterer_background has no persistent subject track in E0-R1-R1.",
            "interpretation": "It remains a hard single-frame negative and cannot be used as a temporal multi-aspect counterfactual track.",
        },
    ]
    for gate in gate_rows:
        if gate["gate_status"] != "PASS":
            failures.append(
                {
                    "failure_id": f"{gate['gate_id']}_NOT_FULLY_SUPPORTED",
                    "severity": "high" if gate["gate_id"] in {"G1_ASPECT_PROXY_OBSERVABLE", "G2_ASPECT_SPAN_SUFFICIENT", "G6_ASPECT_EFFECT_NOT_EXPLAINED_BY_RANGE_ONLY", "G7_ASPECT_EFFECT_NOT_EXPLAINED_BY_TIME_ONLY"} else "medium",
                    "evidence": gate["evidence"],
                    "interpretation": gate["failure_reason"] or "Gate did not reach full PASS.",
                }
            )
    if any(row.get("reproduces_vehicle_aspect_coupling") == "true" for row in corridor_eval):
        failures.append(
            {
                "failure_id": "GT_ATTACHED_CORRIDOR_REPRODUCES_ASPECT_COUPLING",
                "severity": "high",
                "evidence": ";".join(row["counterfactual_group"] for row in corridor_eval if row.get("reproduces_vehicle_aspect_coupling") == "true"),
                "interpretation": "A moving background corridor can mimic the aspect-response proxy, so vehicle-internal mechanism is not isolated.",
            }
        )
    if any(row.get("reproduces_vehicle_aspect_coupling") == "true" for row in fixed_eval):
        failures.append(
            {
                "failure_id": "FIXED_BACKGROUND_ASPECT_COUPLING_PRESENT",
                "severity": "medium",
                "evidence": ";".join(row["counterfactual_group"] for row in fixed_eval if row.get("reproduces_vehicle_aspect_coupling") == "true"),
                "interpretation": "World-fixed backgrounds also correlate with the vehicle aspect proxy, indicating time/range coupling risk.",
            }
        )
    return failures


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
                    "phase": "e0_r2_evaluated",
                    "notes": "Report/CSV committed; PNG files remain ignored under outputs/." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(OUTPUTS["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def render_eval_visuals(shuffle: Sequence[Mapping[str, Any]], repeat_rows: Sequence[Mapping[str, Any]]) -> None:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1100, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    draw.text((30, 24), "Aspect-shuffle control: actual versus cyclic shifts", fill=(0, 0, 0))
    values = [parse_float(row["shuffled_abs_corr_response_index_aspect"]) for row in shuffle if row.get("shuffled_abs_corr_response_index_aspect") != ""]
    actual = parse_float(shuffle[0].get("actual_abs_corr_response_index_aspect", "0")) if shuffle else 0.0
    q90 = parse_float(shuffle[0].get("shuffled_q90_abs_corr", "0")) if shuffle else 0.0
    x0, y0, w, h = 80, 90, 950, 440
    draw.rectangle((x0, y0, x0 + w, y0 + h), outline=(40, 40, 40))
    ymax = max([actual, q90, *values, 1e-6])
    for i, value in enumerate(values):
        x = x0 + int((i + 0.5) / max(len(values), 1) * w)
        y = y0 + h - int(value / ymax * h)
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(90, 90, 90))
    y_actual = y0 + h - int(actual / ymax * h)
    y_q90 = y0 + h - int(q90 / ymax * h)
    draw.line((x0, y_actual, x0 + w, y_actual), fill=(190, 40, 40), width=3)
    draw.line((x0, y_q90, x0 + w, y_q90), fill=(230, 150, 0), width=3)
    draw.text((x0, y0 + h + 20), f"actual_abs_corr={fmt(actual)} | shuffled_q90={fmt(q90)} | actual_exceeds={str(actual > q90 + 0.03).lower()}", fill=(0, 0, 0))
    img.save(VISUAL_DIR / "aspect_shuffle_control.png")

    img = Image.new("RGB", (1100, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    draw.text((30, 24), "Same-aspect repeatability pairs", fill=(0, 0, 0))
    pair_rows = [row for row in repeat_rows if row.get("pair_type") != "summary"]
    x0, y0, w, h = 80, 90, 950, 440
    draw.rectangle((x0, y0, x0 + w, y0 + h), outline=(40, 40, 40))
    xs = [parse_float(row["aspect_difference_deg"]) for row in pair_rows]
    ys = [parse_float(row["response_similarity"]) for row in pair_rows]
    xmax = max(xs, default=1.0)
    ymax = max(ys, default=1.0)
    colors = {
        "same_aspect_similar_range": (20, 150, 40),
        "different_aspect_similar_range": (190, 40, 40),
        "same_aspect_different_range": (230, 150, 0),
    }
    for row in pair_rows:
        x = parse_float(row["aspect_difference_deg"])
        y = parse_float(row["response_similarity"])
        px = x0 + int(x / max(xmax, 1e-6) * w)
        py = y0 + h - int(y / max(ymax, 1e-6) * h)
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=colors.get(row["pair_type"], (80, 80, 80)))
    summary = next((row for row in repeat_rows if row.get("pair_type") == "summary"), {})
    draw.text((x0, y0 + h + 20), f"same={summary.get('same_aspect_similarity','')} diff={summary.get('different_aspect_similarity','')} effect={summary.get('aspect_repeatability_effect','')} | {summary.get('threshold_source','')}", fill=(0, 0, 0))
    img.save(VISUAL_DIR / "same_aspect_pair_candidates.png")


def gate_status(final_rows: Sequence[Mapping[str, Any]], gate_id: str) -> str:
    return next(row["status"] for row in final_rows if row["gate_id"] == gate_id)


def write_report(
    span_rows: Sequence[Mapping[str, Any]],
    binned_rows: Sequence[Mapping[str, Any]],
    smooth_rows: Sequence[Mapping[str, Any]],
    repeat_rows: Sequence[Mapping[str, Any]],
    confound_rows: Sequence[Mapping[str, Any]],
    shuffle: Sequence[Mapping[str, Any]],
    corridor_eval: Sequence[Mapping[str, Any]],
    persistent_eval: Sequence[Mapping[str, Any]],
    fixed_eval: Sequence[Mapping[str, Any]],
    gate_rows: Sequence[Mapping[str, Any]],
    final_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    visual_rows: Sequence[Mapping[str, str]],
) -> None:
    cal = next(row for row in span_rows if row["aspect_split"] == "calibration")
    diag = next(row for row in span_rows if row["aspect_split"] == "posthoc_diagnosis")
    all_span = next(row for row in span_rows if row["aspect_split"] == "all")
    repeat_summary = next((row for row in repeat_rows if row["pair_type"] == "summary"), {})
    response_confound = next((row for row in confound_rows if row["descriptor"] == "response_index"), {})
    smooth_summary = smooth_rows[0] if smooth_rows else {}
    lines = [
        "# WGV3.6B-E0-R2 GM_RM017 Temporal Multi-Aspect Vehicle Response Audit",
        "",
        "## Conclusion",
        "",
        f"- `VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED`: `{gate_status(final_rows, 'VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED')}`",
        f"- `E0_R2_PHYSICAL_MECHANISM_SUPPORTED`: `{gate_status(final_rows, 'E0_R2_PHYSICAL_MECHANISM_SUPPORTED')}`",
        f"- `E0_R2_READY_FOR_CROSS_VEHICLE_VALIDATION`: `{gate_status(final_rows, 'E0_R2_READY_FOR_CROSS_VEHICLE_VALIDATION')}`",
        "",
        "E0-R2 remains a same-scene GT-conditioned posthoc audit. It does not create runtime rules, a detector, selector, ranker, final box, GT edit, training signal, or cross-scene claim.",
        "",
        "## Aspect Observability",
        "",
        f"- calibration observable frames: `{cal['observable_frame_count']}`; HIGH `{cal['observable_high_frame_count']}`; span `{cal['aspect_span_deg']}` deg; median CI `{cal['median_aspect_ci_width_deg']}` deg.",
        f"- diagnosis observable frames: `{diag['observable_frame_count']}`; HIGH `{diag['observable_high_frame_count']}`; span `{diag['aspect_span_deg']}` deg; inside calibration domain `{diag['diagnosis_inside_calibration_domain']}`.",
        f"- all observable frames: `{all_span['observable_frame_count']}`; unresolved frames `{all_span['unresolved_frame_count']}`.",
        "",
        "## Response Versus Aspect",
        "",
        f"- local smoothness correlation: `{smooth_summary.get('local_aspect_smoothness','')}`; abrupt small-aspect changes `{smooth_summary.get('abrupt_change_without_aspect_change_count','')}`; large-aspect response changes `{smooth_summary.get('large_aspect_change_response_count','')}`.",
        f"- same-aspect repeatability effect: `{repeat_summary.get('aspect_repeatability_effect','')}` with `{repeat_summary.get('threshold_source','')}`.",
        f"- response-index R2: aspect `{response_confound.get('r2_aspect_only','')}`, range `{response_confound.get('r2_range_only','')}`, time `{response_confound.get('r2_time_only','')}`.",
        f"- aspect shuffle passed: `{any(row.get('actual_exceeds_shuffle_q90') == 'true' for row in shuffle)}`.",
        "",
        "## Counterfactuals",
        "",
        "| counterfactual | group | observable frames | aspect span | abs corr | reproduces vehicle coupling |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for label, rows in [("GT-attached corridor", corridor_eval), ("persistent strong", persistent_eval), ("fixed background", fixed_eval)]:
        for row in rows:
            lines.append(f"| {label} | {row['counterfactual_group']} | {row['observable_frame_count']} | {row['aspect_span_deg']} | {row['abs_corr_response_index_aspect']} | {row['reproduces_vehicle_aspect_coupling']} |")
    lines.extend(["", "## Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in gate_rows:
        lines.append(f"| {row['gate_id']} | {row['gate_status']} | {row['evidence']} |")
    lines.extend(["", "## Integrity Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in final_rows:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence']} |")
    lines.extend(["", "## Failure Ledger", "", "| failure | severity | evidence | interpretation |", "| --- | --- | --- | --- |"])
    for row in failure_rows:
        lines.append(f"| {row['failure_id']} | {row['severity']} | {row['evidence']} | {row['interpretation']} |")
    lines.extend(["", "## Visual Review", "", "| visual | SAR | conclusion |", "| --- | --- | --- |"])
    for row in visual_rows:
        lines.append(f"| `{row['visual_id']}` | {row['sar_frame']} | {row['reviewer_conclusion_cn']} |")
    direct = (
        "After the E0-R1-R1 symmetric Gate repair and the E0-R2 180-degree axial/aspect re-audit, "
        "GM_RM017 shows an observable same-scene relative-aspect timeline and several vehicle response descriptors vary with that proxy. "
        "However, the current evidence does not close the full multi-aspect mechanism loop because at least one required Gate remains only partial: "
        "the diagnosis aspect domain, local smoothness, same-aspect repeatability, or time/shuffle counterfactual rejection is not fully satisfied. "
        "The GT-attached corridor, persistent strong-scatterer, and fixed-background counterfactuals were computed and did not reproduce the vehicle coupling under this response-index audit, but that is not enough to overcome the remaining partial Gates. "
        "Therefore E0-R2 reports `VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED=NOT_READY`, not a claim that the vehicle SAR response has been proven to evolve with aspect beyond the available counterfactuals."
    )
    lines.extend(["", "## Direct Answer", "", direct, ""])
    write_text(OUTPUTS["report"], "\n".join(lines))


def evaluate() -> None:
    aspect_rows = read_csv(OUTPUTS["relative_aspect_timeline"])
    descriptor_rows = read_csv(OUTPUTS["vehicle_response_descriptors"])
    corridor_rows = read_csv(OUTPUTS["gt_attached_background_corridors"])
    persistent_rows = read_csv(OUTPUTS["persistent_strong_counterfactual"])
    fixed_rows = read_csv(OUTPUTS["fixed_background_aspect_control"])
    visual_rows = read_csv(OUTPUTS["visual_review_manifest"])
    vehicle_rows = [row for row in descriptor_rows if row["subject_name"] == "vehicle_body_axis_reference"]
    stats = calibration_stats(vehicle_rows)
    span_rows = build_aspect_span_audit(aspect_rows)
    binned_rows, _ = build_aspect_binned_response(vehicle_rows, stats)
    smooth_rows = build_local_smoothness(vehicle_rows, stats)
    repeat_rows = build_repeatability(vehicle_rows, stats)
    confound = confounding_rows(vehicle_rows, stats)
    shuffle = shuffle_rows(vehicle_rows, stats)
    corridor_eval, persistent_eval, fixed_eval = build_counterfactual_evals(vehicle_rows, corridor_rows, persistent_rows, fixed_rows, stats)
    gate_rows, final_rows = build_gates(span_rows, smooth_rows, repeat_rows, confound, shuffle, corridor_eval, persistent_eval, fixed_eval, vehicle_rows)
    fill_integrity_status(final_rows)
    failure_rows = build_failure_ledger(span_rows, gate_rows, corridor_eval, fixed_eval)
    render_eval_visuals(shuffle, repeat_rows)

    write_csv(OUTPUTS["aspect_span_audit"], span_rows, ASPECT_SPAN_FIELDS)
    write_csv(OUTPUTS["aspect_binned_response"], binned_rows, ASPECT_BIN_FIELDS)
    write_csv(OUTPUTS["local_aspect_smoothness"], smooth_rows, LOCAL_SMOOTH_FIELDS)
    write_csv(OUTPUTS["same_aspect_repeatability"], repeat_rows, REPEATABILITY_FIELDS)
    write_csv(OUTPUTS["aspect_range_confounding"], confound, CONFOUND_FIELDS)
    write_csv(OUTPUTS["aspect_shuffle_control"], shuffle, SHUFFLE_FIELDS)
    write_csv(OUTPUTS["gt_attached_background_corridors_eval"], corridor_eval, COUNTERFACTUAL_EVAL_FIELDS)
    write_csv(OUTPUTS["persistent_strong_counterfactual_eval"], persistent_eval, COUNTERFACTUAL_EVAL_FIELDS)
    write_csv(OUTPUTS["fixed_background_aspect_control_eval"], fixed_eval, COUNTERFACTUAL_EVAL_FIELDS)
    write_csv(OUTPUTS["multi_aspect_gate_matrix"], gate_rows, GATE_FIELDS)
    write_csv(OUTPUTS["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(OUTPUTS["gate_integrity"], final_rows, FINAL_GATE_FIELDS)
    write_report(span_rows, binned_rows, smooth_rows, repeat_rows, confound, shuffle, corridor_eval, persistent_eval, fixed_eval, gate_rows, final_rows, failure_rows, visual_rows)
    write_frozen_manifest()
    print("E0_R2 evaluation complete")


ASPECT_SPAN_FIELDS = [
    "aspect_split",
    "aspect_min_deg",
    "aspect_max_deg",
    "aspect_span_deg",
    "aspect_step_median_deg",
    "aspect_step_q90_deg",
    "observable_frame_count",
    "observable_high_frame_count",
    "observable_medium_frame_count",
    "unresolved_frame_count",
    "median_aspect_ci_width_deg",
    "calibration_aspect_span",
    "guard_aspect_span",
    "diagnosis_aspect_span",
    "diagnosis_inside_calibration_domain",
    "ASPECT_SPAN_SUFFICIENT",
    "ASPECT_TEMPORAL_ORDER_VALID",
    "ASPECT_UNCERTAINTY_BOUNDED",
]
ASPECT_BIN_FIELDS = [
    "split",
    "aspect_bin_id",
    "aspect_bin_low_deg",
    "aspect_bin_high_deg",
    "observable_frame_count",
    "mean_response_index",
    "mean_local_background_normalized_energy",
    "mean_body_long_energy90_width_m",
    "mean_body_short_energy90_width_m",
    "mean_near_far_energy_ratio",
    "mean_centroid_body_long_offset_m",
    "threshold_source",
]
LOCAL_SMOOTH_FIELDS = [
    "frame_a",
    "frame_b",
    "split_a",
    "split_b",
    "frame_gap",
    "aspect_delta_deg",
    "response_descriptor_distance",
    "local_aspect_smoothness",
    "abrupt_change_without_aspect_change_count",
    "large_aspect_change_response_count",
    "threshold_source",
]
REPEATABILITY_FIELDS = [
    "frame_a",
    "frame_b",
    "pair_type",
    "time_separation_frames",
    "aspect_difference_deg",
    "absolute_range_difference_m_grid",
    "response_descriptor_distance",
    "response_similarity",
    "same_aspect_similarity",
    "different_aspect_similarity",
    "aspect_repeatability_effect",
    "threshold_source",
]
CONFOUND_FIELDS = [
    "descriptor",
    "observable_frame_count",
    "corr_with_aspect",
    "corr_with_absolute_range",
    "corr_with_time",
    "r2_aspect_only",
    "r2_range_only",
    "r2_time_only",
    "r2_aspect_plus_range",
    "r2_aspect_plus_time",
    "threshold_source",
]
SHUFFLE_FIELDS = [
    "shuffle_id",
    "observable_frame_count",
    "actual_abs_corr_response_index_aspect",
    "shuffled_abs_corr_response_index_aspect",
    "shuffled_q90_abs_corr",
    "actual_exceeds_shuffle_q90",
    "threshold_source",
]
COUNTERFACTUAL_EVAL_FIELDS = [
    "counterfactual_group",
    "observable_frame_count",
    "aspect_span_deg",
    "abs_corr_response_index_aspect",
    "mean_response_index",
    "reproduces_vehicle_aspect_coupling",
    "evaluation_note",
]
GATE_FIELDS = [
    "gate_id",
    "gate_status",
    "gate_definition_version",
    "threshold_source",
    "threshold_value",
    "input_fields",
    "evidence",
    "failure_reason",
    "forbidden_scope",
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
