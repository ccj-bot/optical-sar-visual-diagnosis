"""Run the E0-R3 GM_RM017 body-canonical first audit.

This audit reads frozen E0-R1-R1 and E0-R2 artifacts, recomputes fan-center
range, builds a minimal body-canonical response field for selected review
frames, and writes a first report. It does not modify older frozen artifacts,
train a model, rank boxes, edit GT, or claim a full physical mechanism.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


DATE = "20260713"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
FROZEN_ANCESTOR = "7a9d9cba9f38447e10c917227a789f4160569026"
PX_TO_M = 0.03
IMAGING_DOMAIN_M = 40.0
CORE_W = 128
CORE_H = 64
CANVAS_W = 160
CANVAS_H = 96
BOUNDARY_BINS = 32

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_e0_r3_gm017_body_canonical_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
SCENE_CONFIG = REPO_ROOT / "configs" / "scene_config.yaml"
PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_BODY_CANONICAL_RESPONSE_E0_R3_PROTOCOL.md"

E0_R2_PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_TEMPORAL_MULTI_ASPECT_RESPONSE_E0_R2_PROTOCOL.md"
E0_R2_REPORT = REPORT_DIR / "oty2_wgv3_6b_e0_r2_gm017_temporal_multi_aspect_response_20260712.md"
E0_R2_GENERATE = REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_6b_e0_r2_gm017_multi_aspect_generate.py"
E0_R2_EVALUATE = REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_6b_e0_r2_gm017_multi_aspect_evaluate.py"
E0_R1_R1_PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_SYMMETRIC_HARD_NEGATIVE_AND_AXIAL_HEADING_E0_R1_R1_PROTOCOL.md"
E0_R1_R1_REPORT = REPORT_DIR / "oty2_wgv3_6b_e0_r1_r1_gm017_symmetric_hard_negative_axial_heading_20260712.md"

INPUTS = {
    "e0_r2_relative_aspect": SAMPLES_DIR / "e0_r2_relative_aspect_timeline_20260712.csv",
    "e0_r2_heading_observability": SAMPLES_DIR / "e0_r2_heading_observability_20260712.csv",
    "e0_r2_response_descriptors": SAMPLES_DIR / "e0_r2_vehicle_response_descriptors_20260712.csv",
    "e0_r2_range_confounding": SAMPLES_DIR / "e0_r2_aspect_range_confounding_20260712.csv",
    "e0_r2_repeatability": SAMPLES_DIR / "e0_r2_same_aspect_repeatability_20260712.csv",
    "e0_r2_shuffle": SAMPLES_DIR / "e0_r2_aspect_shuffle_control_20260712.csv",
    "e0_r2_gt_corridors": SAMPLES_DIR / "e0_r2_gt_attached_background_corridors_20260712.csv",
    "e0_r2_gt_corridors_eval": SAMPLES_DIR / "e0_r2_gt_attached_background_corridors_eval_20260712.csv",
    "e0_r2_persistent_strong": SAMPLES_DIR / "e0_r2_persistent_strong_counterfactual_20260712.csv",
    "e0_r2_persistent_strong_eval": SAMPLES_DIR / "e0_r2_persistent_strong_counterfactual_eval_20260712.csv",
    "e0_r2_fixed_background": SAMPLES_DIR / "e0_r2_fixed_background_aspect_control_20260712.csv",
    "e0_r2_gate_matrix": SAMPLES_DIR / "e0_r2_multi_aspect_gate_matrix_20260712.csv",
    "e0_r2_gate_integrity": SAMPLES_DIR / "e0_r2_gate_integrity_20260712.csv",
    "e0_r2_failure_ledger": SAMPLES_DIR / "e0_r2_failure_ledger_20260712.csv",
    "e0_r1_r1_unique_centers": SAMPLES_DIR / "e0_r1_r1_unique_gt_center_sequence_20260712.csv",
    "e0_r1_r1_axial_heading": SAMPLES_DIR / "e0_r1_r1_axial_body_heading_20260712.csv",
    "e0_r1_r1_subject_manifest": SAMPLES_DIR / "e0_r1_r1_subject_manifest_20260712.csv",
    "e0_r1_r1_subject_temporal": SAMPLES_DIR / "e0_r1_r1_subject_temporal_features_20260712.csv",
    "e0_r1_r1_symmetric_gate": SAMPLES_DIR / "e0_r1_r1_symmetric_gate_matrix_20260712.csv",
    "e0_r1_r1_hard_negative": SAMPLES_DIR / "e0_r1_r1_hard_negative_confusion_levels_20260712.csv",
}

OUTPUTS = {
    "reading_inventory": SAMPLES_DIR / f"e0_r3_body_canonical_reading_inventory_{DATE}.csv",
    "range_correction": SAMPLES_DIR / f"e0_r3_body_canonical_range_correction_{DATE}.csv",
    "identifiability_pairs": SAMPLES_DIR / f"e0_r3_body_canonical_aspect_range_time_pairs_{DATE}.csv",
    "identifiability_summary": SAMPLES_DIR / f"e0_r3_body_canonical_aspect_range_time_summary_{DATE}.csv",
    "axis_continuity": SAMPLES_DIR / f"e0_r3_body_axis_sign_continuity_{DATE}.csv",
    "representative_manifest": SAMPLES_DIR / f"e0_r3_body_canonical_representative_manifest_{DATE}.csv",
    "canonical_manifest": SAMPLES_DIR / f"e0_r3_body_canonical_response_manifest_{DATE}.csv",
    "boundary_metrics": SAMPLES_DIR / f"e0_r3_body_canonical_near_boundary_metrics_{DATE}.csv",
    "diff_audit": SAMPLES_DIR / f"e0_r3_body_canonical_frame_diff_audit_{DATE}.csv",
    "registration_perturbation": SAMPLES_DIR / f"e0_r3_body_canonical_registration_perturbation_{DATE}.csv",
    "counterfactual_casebook": SAMPLES_DIR / f"e0_r3_body_canonical_counterfactual_casebook_{DATE}.csv",
    "visual_casebook": SAMPLES_DIR / f"e0_r3_body_canonical_visual_casebook_{DATE}.md",
    "failure_ledger": SAMPLES_DIR / f"e0_r3_body_canonical_failure_ledger_{DATE}.csv",
    "gate_status": SAMPLES_DIR / f"e0_r3_body_canonical_gate_status_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_e0_r3_gm017_body_canonical_first_audit_{DATE}.md",
}


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def ensure_dirs() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def load_scene_config() -> dict[str, Any]:
    with SCENE_CONFIG.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def scene_geometry() -> dict[str, float]:
    config = load_scene_config()
    canvas = config["global_geometry"]["sar_canvas"]
    fan = config["global_geometry"]["fan"]
    return {
        "width": float(canvas["width"]),
        "height": float(canvas["height"]),
        "fan_center_x": float(fan["center_x"]),
        "fan_center_y": float(fan["center_y"]),
        "fan_radius_px": float(fan["radius_px_max"]),
    }


def sar_gray_path(frame: int) -> Path:
    config = load_scene_config()
    return Path(config["scenes"][SCENE]["paths"]["sar_gray_frames_dir"]) / f"{frame:06d}.png"


def load_image(frame: int, cache: dict[int, np.ndarray]) -> np.ndarray:
    if frame not in cache:
        path = sar_gray_path(frame)
        cache[frame] = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    return cache[frame]


def unit(vec: tuple[float, float]) -> tuple[float, float]:
    norm = math.hypot(vec[0], vec[1])
    if norm <= 1e-12:
        return (1.0, 0.0)
    return (vec[0] / norm, vec[1] / norm)


def directed_diff(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def axial_diff(a: float, b: float) -> float:
    return abs(((a % 180.0) - (b % 180.0) + 90.0) % 180.0 - 90.0)


def angle_unit(angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return math.cos(rad), math.sin(rad)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return 0.0
    x = np.asarray([p[0] for p in pairs], dtype=float)
    y = np.asarray([p[1] for p in pairs], dtype=float)
    if float(np.std(x)) <= 1e-9 or float(np.std(y)) <= 1e-9:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def rankdata(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda idx: values[idx])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = rank
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        return 0.0
    return pearson(rankdata(list(xs)), rankdata(list(ys)))


def reading_inventory() -> list[dict[str, Any]]:
    sources = {
        "new_protocol": PROTOCOL,
        "e0_r2_protocol": E0_R2_PROTOCOL,
        "e0_r2_report": E0_R2_REPORT,
        "e0_r2_generate_script": E0_R2_GENERATE,
        "e0_r2_evaluate_script": E0_R2_EVALUATE,
        "e0_r1_r1_protocol": E0_R1_R1_PROTOCOL,
        "e0_r1_r1_report": E0_R1_R1_REPORT,
        "scene_config": SCENE_CONFIG,
        **INPUTS,
    }
    rows = []
    for key, path in sources.items():
        rows.append(
            {
                "artifact_key": key,
                "path": rel(path),
                "exists": str(path.exists()).lower(),
                "sha256": sha256_file(path) if path.exists() else "",
                "row_count": row_count(path),
                "read_role": "required_frozen_input" if key != "new_protocol" else "new_e0_r3_protocol",
            }
        )
    return rows


def frame_split(frame: int) -> str:
    if frame <= 360:
        return "calibration"
    if frame <= 370:
        return "guard"
    return "posthoc_diagnosis"


def load_frame_table() -> list[dict[str, Any]]:
    centers = {parse_int(row["sar_frame"]): row for row in read_csv(INPUTS["e0_r1_r1_unique_centers"]) if row.get("included_in_heading_main_analysis") == "true"}
    headings = {parse_int(row["sar_frame"]): row for row in read_csv(INPUTS["e0_r1_r1_axial_heading"])}
    aspects = {parse_int(row["sar_frame"]): row for row in read_csv(INPUTS["e0_r2_relative_aspect"])}
    subject_rows = [
        row
        for row in read_csv(INPUTS["e0_r1_r1_subject_manifest"])
        if row.get("subject_name") == "vehicle_body_axis_reference"
    ]
    subjects = {parse_int(row["sar_frame"]): row for row in subject_rows}
    geometry = scene_geometry()
    rows: list[dict[str, Any]] = []
    for frame in sorted(centers):
        center = centers[frame]
        heading = headings.get(frame, {})
        aspect = aspects.get(frame, {})
        subject = subjects.get(frame, {})
        cx = parse_float(center.get("selected_center_x"))
        cy = parse_float(center.get("selected_center_y"))
        corrected_px = math.hypot(cx - geometry["fan_center_x"], cy - geometry["fan_center_y"])
        corrected_m = corrected_px * PX_TO_M
        rows.append(
            {
                "sar_frame": frame,
                "pair_id": center.get("selected_pair_id", ""),
                "same_vehicle_thread": "GM_RM017_WGV35A_MAIN_VEHICLE_THREAD",
                "cx": cx,
                "cy": cy,
                "split": frame_split(frame),
                "center_selection_status": center.get("center_selection_status", ""),
                "identity_consistency_status": center.get("identity_consistency_status", ""),
                "axis_unsigned_deg": parse_float(heading.get("body_axis_proxy_deg")),
                "axis_reliability": heading.get("heading_confidence", ""),
                "axis_fit_residual_px": parse_float(heading.get("fit_residual_px")),
                "axis_support_frame_count": parse_int(heading.get("support_frame_count")),
                "relative_aspect_angle_deg": parse_float(aspect.get("relative_aspect_angle_deg")),
                "aspect_angle_ci_width_deg": parse_float(aspect.get("aspect_angle_ci_width_deg")),
                "aspect_observability_status": aspect.get("aspect_observability_status", ""),
                "legacy_absolute_range_m_grid": parse_float(aspect.get("absolute_range_m_grid")),
                "range_px_corrected": corrected_px,
                "range_m_corrected": corrected_m,
                "within_40m_domain": corrected_m <= IMAGING_DOMAIN_M,
                "body_length_m": parse_float(subject.get("width_m_grid"), 4.764934),
                "body_width_m": parse_float(subject.get("height_m_grid"), 2.077648),
                "body_length_px": parse_float(subject.get("width_px"), 4.764934 / PX_TO_M),
                "body_width_px": parse_float(subject.get("height_px"), 2.077648 / PX_TO_M),
            }
        )
    return rows


def write_range_correction(frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    geometry = scene_geometry()
    rows = []
    for row in frames:
        failure = ""
        if not row["within_40m_domain"]:
            failure = "CORRECTED_RANGE_OUTSIDE_40M_DOMAIN"
        rows.append(
            {
                "sar_frame": row["sar_frame"],
                "cx": fmt(row["cx"]),
                "cy": fmt(row["cy"]),
                "fan_center_x": fmt(geometry["fan_center_x"]),
                "fan_center_y": fmt(geometry["fan_center_y"]),
                "range_px_corrected": fmt(row["range_px_corrected"]),
                "range_m_corrected": fmt(row["range_m_corrected"]),
                "within_40m_domain": str(row["within_40m_domain"]).lower(),
                "legacy_absolute_range_m_grid": fmt(row["legacy_absolute_range_m_grid"]),
                "legacy_within_40m_domain": str(row["legacy_absolute_range_m_grid"] <= IMAGING_DOMAIN_M).lower(),
                "failure_reason": failure,
            }
        )
    return rows


def axis_continuity(frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    previous: float | None = None
    for row in sorted(frames, key=lambda item: item["sar_frame"]):
        unsigned = row["axis_unsigned_deg"] % 180.0
        if previous is None:
            signed = unsigned
        else:
            candidates = [unsigned + 180.0 * k for k in range(-4, 5)]
            signed = min(candidates, key=lambda candidate: abs(candidate - previous))
        residual = 0.0 if previous is None else abs(signed - previous)
        flip = int(round((signed - unsigned) / 180.0)) % 2 != 0
        status = "PASS" if row["axis_reliability"] in {"HIGH", "MEDIUM"} and residual <= 45.0 else "PARTIAL"
        if row["axis_reliability"] == "LOW" or residual > 60.0:
            status = "FAIL"
        rows.append(
            {
                "sar_frame": row["sar_frame"],
                "pair_id": row["pair_id"],
                "axis_unsigned_deg": fmt(unsigned),
                "axis_signed_for_registration_deg": fmt(signed),
                "axis_sign_flip_applied": str(flip).lower(),
                "axis_continuity_residual_deg": fmt(residual),
                "axis_reliability": row["axis_reliability"],
                "registration_axis_status": status,
                "notes": "directed registration axis only; not front/rear yaw",
            }
        )
        if status != "FAIL":
            previous = signed
    return rows


def reliability_ok(frame: Mapping[str, Any]) -> bool:
    return frame["axis_reliability"] in {"HIGH", "MEDIUM"} and frame["aspect_observability_status"] in {"OBSERVABLE_HIGH", "OBSERVABLE_MEDIUM"}


def identifiability_audit(frames: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pair_rows: list[dict[str, Any]] = []
    sorted_frames = [row for row in sorted(frames, key=lambda item: item["sar_frame"]) if reliability_ok(row)]
    for i, a in enumerate(sorted_frames):
        for b in sorted_frames[i + 1 :]:
            time_delta = int(b["sar_frame"]) - int(a["sar_frame"])
            if time_delta < 5:
                continue
            aspect_delta = abs(b["relative_aspect_angle_deg"] - a["relative_aspect_angle_deg"])
            range_delta = abs(b["range_m_corrected"] - a["range_m_corrected"])
            types: list[str] = []
            if range_delta <= 0.75 and aspect_delta >= 15.0:
                types.append("similar_range_different_aspect")
            if aspect_delta <= 5.0 and range_delta >= 1.0:
                types.append("similar_aspect_different_range")
            if aspect_delta <= 5.0 and time_delta >= 10:
                types.append("non_adjacent_similar_aspect")
            if range_delta <= 0.75 and aspect_delta >= 10.0:
                types.append("different_aspect_similar_range")
            if not types:
                continue
            pair_rows.append(
                {
                    "frame_a": a["sar_frame"],
                    "frame_b": b["sar_frame"],
                    "pair_type": ";".join(sorted(set(types))),
                    "time_delta_frames": time_delta,
                    "aspect_delta_deg": fmt(aspect_delta),
                    "corrected_range_delta_m": fmt(range_delta),
                    "axis_pair_reliable": "true",
                    "registration_pair_reliable": str(a["axis_reliability"] != "LOW" and b["axis_reliability"] != "LOW").lower(),
                    "frame_a_axis_reliability": a["axis_reliability"],
                    "frame_b_axis_reliability": b["axis_reliability"],
                    "used_for_identifiability": "true",
                }
            )
    aspects = [row["relative_aspect_angle_deg"] for row in sorted_frames]
    ranges = [row["range_m_corrected"] for row in sorted_frames]
    times = [row["sar_frame"] for row in sorted_frames]
    counts = Counter()
    for row in pair_rows:
        for pair_type in row["pair_type"].split(";"):
            counts[pair_type] += 1
    aspect_time_s = spearman(aspects, times)
    aspect_range_s = spearman(aspects, ranges)
    monotonic_risk = abs(aspect_time_s) >= 0.85
    range_collinear = abs(aspect_range_s) >= 0.80
    independent_ready = (
        counts["similar_range_different_aspect"] >= 3
        and counts["similar_aspect_different_range"] >= 3
        and counts["non_adjacent_similar_aspect"] >= 3
        and not monotonic_risk
        and not range_collinear
    )
    status = "PARTIAL" if independent_ready else "NOT_READY"
    if pair_rows and status == "NOT_READY":
        reason = "usable_pairs_exist_but_independent_control_family_or_collinearity_gate_not_closed"
    else:
        reason = "insufficient_usable_independent_frame_pairs"
    summary = [
        {
            "audit_item": "similar_range_different_aspect_pairs",
            "value": counts["similar_range_different_aspect"],
            "status": "PASS" if counts["similar_range_different_aspect"] >= 3 else "NOT_READY",
            "evidence": "range_delta<=0.75m;aspect_delta>=15deg;time_delta>=5",
        },
        {
            "audit_item": "similar_aspect_different_range_pairs",
            "value": counts["similar_aspect_different_range"],
            "status": "PASS" if counts["similar_aspect_different_range"] >= 3 else "NOT_READY",
            "evidence": "aspect_delta<=5deg;range_delta>=1m;time_delta>=5",
        },
        {
            "audit_item": "non_adjacent_similar_aspect_pairs",
            "value": counts["non_adjacent_similar_aspect"],
            "status": "PASS" if counts["non_adjacent_similar_aspect"] >= 3 else "NOT_READY",
            "evidence": "aspect_delta<=5deg;time_delta>=10",
        },
        {
            "audit_item": "different_aspect_similar_range_pairs",
            "value": counts["different_aspect_similar_range"],
            "status": "PASS" if counts["different_aspect_similar_range"] >= 3 else "NOT_READY",
            "evidence": "range_delta<=0.75m;aspect_delta>=10deg;time_delta>=5",
        },
        {
            "audit_item": "aspect_time_spearman",
            "value": fmt(aspect_time_s),
            "status": "PARTIAL" if monotonic_risk else "PASS",
            "evidence": "monotonic_risk_threshold_abs_spearman>=0.85",
        },
        {
            "audit_item": "aspect_range_spearman",
            "value": fmt(aspect_range_s),
            "status": "PARTIAL" if range_collinear else "PASS",
            "evidence": "collinearity_threshold_abs_spearman>=0.80",
        },
        {
            "audit_item": "ASPECT_CAUSAL_IDENTIFIABILITY",
            "value": status,
            "status": status,
            "evidence": reason,
        },
    ]
    return pair_rows, summary


def descriptors_by_frame() -> dict[int, dict[str, str]]:
    rows = [row for row in read_csv(INPUTS["e0_r2_response_descriptors"]) if row.get("subject_name") == "vehicle_body_axis_reference"]
    return {parse_int(row["sar_frame"]): row for row in rows}


def choose_window(frames: Sequence[Mapping[str, Any]], role: str, selected: set[int]) -> list[int]:
    by_frame = {row["sar_frame"]: row for row in frames}
    ordered = [row for row in sorted(frames, key=lambda item: item["sar_frame"]) if reliability_ok(row)]
    triples = [ordered[i : i + 3] for i in range(len(ordered) - 2)]
    desc = descriptors_by_frame()
    if role == "stable":
        best = min(
            triples,
            key=lambda tri: (
                max(r["relative_aspect_angle_deg"] for r in tri) - min(r["relative_aspect_angle_deg"] for r in tri)
                + 0.25 * (max(r["range_m_corrected"] for r in tri) - min(r["range_m_corrected"] for r in tri)),
                tri[0]["sar_frame"],
            ),
        )
        return [int(row["sar_frame"]) for row in best]
    if role == "sliding":
        best = max(
            triples,
            key=lambda tri: (
                max(r["relative_aspect_angle_deg"] for r in tri) - min(r["relative_aspect_angle_deg"] for r in tri)
                - 0.5 * (max(r["range_m_corrected"] for r in tri) - min(r["range_m_corrected"] for r in tri)),
                -tri[0]["sar_frame"],
            ),
        )
        return [int(row["sar_frame"]) for row in best]
    if role == "switch":
        pairs = []
        for a, b in zip(ordered, ordered[1:]):
            da = desc.get(int(a["sar_frame"]), {})
            db = desc.get(int(b["sar_frame"]), {})
            score = abs(parse_float(db.get("near_far_energy_ratio")) - parse_float(da.get("near_far_energy_ratio")))
            score += abs(parse_float(db.get("energy_centroid_body_long_offset_m")) - parse_float(da.get("energy_centroid_body_long_offset_m")))
            pairs.append((score, int(a["sar_frame"]), int(b["sar_frame"])))
        _, fa, fb = max(pairs)
        prevs = [row["sar_frame"] for row in ordered if row["sar_frame"] < fa]
        return ([int(prevs[-1])] if prevs else []) + [fa, fb]
    if role == "split_merge":
        best_frame = max(
            ordered,
            key=lambda row: parse_float(desc.get(int(row["sar_frame"]), {}).get("response_fragmentation_index")),
        )["sar_frame"]
        idx = [row["sar_frame"] for row in ordered].index(best_frame)
        frames_out = [ordered[max(0, idx - 1)]["sar_frame"], best_frame, ordered[min(len(ordered) - 1, idx + 1)]["sar_frame"]]
        return [int(f) for f in dict.fromkeys(frames_out)]
    if role == "difficult":
        low = [row for row in frames if row["axis_reliability"] == "LOW"]
        if low:
            f = int(low[0]["sar_frame"])
        else:
            f = int(max(frames, key=lambda row: row["aspect_angle_ci_width_deg"])["sar_frame"])
        candidates = [x for x in sorted(by_frame) if abs(x - f) <= 2]
        return [int(x) for x in candidates[:3]] or [f]
    return []


def representative_manifest(frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: set[int] = set()
    roles = [
        ("W_STABLE", "stable", "previsual_min_aspect_range_delta_three_frame_window", "stable_review"),
        ("W_SLIDE", "sliding", "previsual_large_aspect_span_limited_corrected_range_window", "near_side_sliding_review"),
        (
            "W_SWITCH",
            "switch",
            "previsual_legacy_near_far_and_centroid_change_window_selection_only",
            "switching_review",
        ),
        (
            "W_SPLIT",
            "split_merge",
            "previsual_legacy_fragmentation_peak_and_neighbor_window_selection_only",
            "split_merge_review",
        ),
        ("W_DIFFICULT", "difficult", "previsual_low_axis_or_max_aspect_ci_difficult_window", "registration_mask_boundary_review"),
    ]
    by_frame = {int(row["sar_frame"]): row for row in frames}
    rows: list[dict[str, Any]] = []
    for window_id, role, reason, review_role in roles:
        for frame in choose_window(frames, role, selected):
            if frame not in by_frame:
                continue
            selected.add(frame)
            row = by_frame[frame]
            rows.append(
                {
                    "sar_frame": frame,
                    "window_id": window_id,
                    "selection_reason": reason,
                    "same_vehicle_thread": row["same_vehicle_thread"],
                    "axis_reliability": row["axis_reliability"],
                    "registration_reliability": registration_label(row),
                    "relative_aspect_angle_deg": fmt(row["relative_aspect_angle_deg"]),
                    "range_m_corrected": fmt(row["range_m_corrected"]),
                    "expected_review_role": review_role,
                }
            )
    return rows


def registration_label(row: Mapping[str, Any]) -> str:
    if row["axis_reliability"] == "LOW" or not row["within_40m_domain"]:
        return "LOW"
    if row["axis_fit_residual_px"] > 5.0 or row["aspect_angle_ci_width_deg"] > 10.0:
        return "MEDIUM"
    return "HIGH"


def bilinear_sample(image: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = image.shape
    valid = (xs >= 0) & (xs <= w - 1) & (ys >= 0) & (ys <= h - 1)
    x0 = np.floor(np.clip(xs, 0, w - 1)).astype(int)
    y0 = np.floor(np.clip(ys, 0, h - 1)).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    wx = np.clip(xs - x0, 0, 1)
    wy = np.clip(ys - y0, 0, 1)
    top = image[y0, x0] * (1 - wx) + image[y0, x1] * wx
    bottom = image[y1, x0] * (1 - wx) + image[y1, x1] * wx
    return top * (1 - wy) + bottom * wy, valid


def grid_coordinates(length_px: float, width_px: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_idx = (np.arange(CANVAS_W, dtype=np.float32) + 0.5 - CANVAS_W / 2.0)
    y_idx = (np.arange(CANVAS_H, dtype=np.float32) + 0.5 - CANVAS_H / 2.0)
    uu = x_idx[None, :] / CORE_W * length_px
    vv = y_idx[:, None] / CORE_H * width_px
    u = np.repeat(uu, CANVAS_H, axis=0)
    v = np.repeat(vv, CANVAS_W, axis=1)
    support = (np.abs(x_idx[None, :]) <= CORE_W / 2.0) & (np.abs(y_idx[:, None]) <= CORE_H / 2.0)
    return u, v, support


def canonical_map(
    image: np.ndarray,
    cx: float,
    cy: float,
    axis_deg: float,
    length_px: float,
    width_px: float,
) -> dict[str, Any]:
    u_px, v_px, support = grid_coordinates(length_px, width_px)
    axis = angle_unit(axis_deg)
    short = (-axis[1], axis[0])
    xs = cx + u_px * axis[0] + v_px * short[0]
    ys = cy + u_px * axis[1] + v_px * short[1]
    raw, valid = bilinear_sample(image, xs, ys)
    raw = np.where(valid, raw, 0.0)
    background = (~support) & valid
    bg_values = raw[background]
    if bg_values.size:
        bg_median = float(np.median(bg_values))
        mad = float(np.median(np.abs(bg_values - bg_median)))
    else:
        bg_median = 0.0
        mad = 1.0
    denom = max(mad * 1.4826, 1.0)
    norm = (raw - bg_median) / denom
    return {
        "raw": raw,
        "norm": norm,
        "valid": valid,
        "support": support,
        "background": background,
        "bg_median": bg_median,
        "bg_mad": mad,
        "transform": f"x=cx+u*cos(theta)-v*sin(theta);y=cy+u*sin(theta)+v*cos(theta);theta={fmt(axis_deg)}",
        "inverse": "u=(x-cx)*cos(theta)+(y-cy)*sin(theta);v=-(x-cx)*sin(theta)+(y-cy)*cos(theta)",
    }


def heat_color(value: float, lo: float, hi: float) -> tuple[int, int, int]:
    if hi <= lo:
        t = 0.0
    else:
        t = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    if t < 0.5:
        r = int(40 + 120 * t * 2)
        g = int(80 + 110 * t * 2)
        b = int(180 - 120 * t * 2)
    else:
        r = int(160 + 90 * (t - 0.5) * 2)
        g = int(190 - 160 * (t - 0.5) * 2)
        b = int(60 - 40 * (t - 0.5) * 2)
    return r, g, b


def render_heatmap(array: np.ndarray, path: Path, title: str, labels: Sequence[str] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(array, dtype=float)
    finite = arr[np.isfinite(arr)]
    lo = float(np.percentile(finite, 2)) if finite.size else 0.0
    hi = float(np.percentile(finite, 98)) if finite.size else 1.0
    scale = 4
    img = Image.new("RGB", (arr.shape[1] * scale, arr.shape[0] * scale), (245, 245, 245))
    pix = img.load()
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            color = heat_color(float(arr[y, x]), lo, hi)
            for yy in range(y * scale, (y + 1) * scale):
                for xx in range(x * scale, (x + 1) * scale):
                    pix[xx, yy] = color
    canvas = Image.new("RGB", (img.width, img.height + 46), (255, 255, 255))
    canvas.paste(img, (0, 34))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 6), title, fill=(0, 0, 0))
    for idx, label in enumerate(labels[:2]):
        draw.text((6, img.height + 20 + idx * 12), label, fill=(0, 0, 0))
    canvas.save(path)


def render_overlay(
    raw: np.ndarray,
    valid: np.ndarray,
    support: np.ndarray,
    near_band: np.ndarray,
    far_band: np.ndarray,
    radar_body: tuple[float, float],
    path: Path,
    title: str,
) -> None:
    arr = raw.copy()
    finite = arr[valid]
    lo = float(np.percentile(finite, 2)) if finite.size else 0.0
    hi = float(np.percentile(finite, 98)) if finite.size else 1.0
    scale = 5
    img = Image.new("RGB", (CANVAS_W * scale, CANVAS_H * scale + 54), (255, 255, 255))
    pix = img.load()
    for y in range(CANVAS_H):
        for x in range(CANVAS_W):
            base = heat_color(float(arr[y, x]), lo, hi) if valid[y, x] else (40, 40, 40)
            if near_band[y, x]:
                base = (255, min(255, base[1] + 50), min(255, base[2] + 20))
            elif far_band[y, x]:
                base = (min(255, base[0] + 20), min(255, base[1] + 80), 255)
            elif support[y, x]:
                base = (min(255, base[0] + 20), base[1], base[2])
            for yy in range(y * scale + 34, (y + 1) * scale + 34):
                for xx in range(x * scale, (x + 1) * scale):
                    pix[xx, yy] = base
    draw = ImageDraw.Draw(img)
    draw.text((6, 6), title, fill=(0, 0, 0))
    cx, cy = CANVAS_W * scale / 2.0, 34 + CANVAS_H * scale / 2.0
    draw.line((cx, cy, cx + radar_body[0] * 70, cy + radar_body[1] * 70), fill=(255, 255, 255), width=3)
    draw.line((cx, cy, cx + 60, cy), fill=(0, 0, 0), width=2)
    draw.text((6, img.height - 16), "white arrow: radar-near direction; red/yellow: near boundary; blue: far boundary", fill=(0, 0, 0))
    img.save(path)


def masks_for_near_side(
    length_px: float,
    width_px: float,
    radar_body: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    u_px, v_px, support = grid_coordinates(length_px, width_px)
    r = unit(radar_body)
    score = u_px * r[0] + v_px * r[1]
    max_score = float(np.max(score[support])) if np.any(support) else 1.0
    min_score = float(np.min(score[support])) if np.any(support) else -1.0
    near_half = support & (score >= 0)
    far_half = support & (score < 0)
    near_band = support & (score >= 0.70 * max_score)
    far_band = support & (score <= 0.70 * min_score)
    tangent = (-r[1], r[0])
    tangent_coord = u_px * tangent[0] + v_px * tangent[1]
    return near_half, far_half, near_band, far_band, tangent_coord


def boundary_metrics(norm: np.ndarray, valid: np.ndarray, near_band: np.ndarray, far_band: np.ndarray, tangent_coord: np.ndarray) -> dict[str, Any]:
    values = np.where(valid, norm, np.nan)
    near_vals = values[near_band & valid]
    far_vals = values[far_band & valid]
    near_fraction = float(np.nansum(np.maximum(near_vals, 0))) / max(float(np.nansum(np.maximum(values[np.isfinite(values)], 0))), 1e-9)
    far_fraction = float(np.nansum(np.maximum(far_vals, 0))) / max(float(np.nansum(np.maximum(values[np.isfinite(values)], 0))), 1e-9)
    et = np.zeros(BOUNDARY_BINS, dtype=float)
    counts = np.zeros(BOUNDARY_BINS, dtype=float)
    mask = near_band & valid
    if np.any(mask):
        tvals = tangent_coord[mask]
        lo = float(np.min(tvals))
        hi = float(np.max(tvals))
        denom = max(hi - lo, 1e-9)
        bins = np.clip(((tvals - lo) / denom * BOUNDARY_BINS).astype(int), 0, BOUNDARY_BINS - 1)
        energies = np.maximum(norm[mask], 0)
        for idx, energy in zip(bins, energies):
            et[idx] += float(energy)
            counts[idx] += 1.0
    et = np.divide(et, np.maximum(counts, 1.0))
    s_peak = int(np.argmax(et)) if et.size else 0
    max_v = float(np.max(et)) if et.size else 0.0
    median_v = float(np.median(et)) if et.size else 0.0
    local_peaks = 0
    for idx in range(1, BOUNDARY_BINS - 1):
        if et[idx] > et[idx - 1] and et[idx] >= et[idx + 1] and et[idx] > median_v:
            local_peaks += 1
    secondary = float(np.partition(et, -2)[-2]) if et.size >= 2 else 0.0
    width = float(np.sum(et >= max_v * 0.5) / BOUNDARY_BINS) if max_v > 0 else 0.0
    return {
        "E_t": et,
        "s_peak_t": s_peak / max(BOUNDARY_BINS - 1, 1),
        "secondary_peak": secondary,
        "peak_count": local_peaks,
        "peak_width": width,
        "peak_prominence": max_v - median_v,
        "near_side_boundary_energy_fraction": near_fraction,
        "far_side_boundary_energy_fraction": far_fraction,
        "peak_inside_valid_mask": bool(counts[s_peak] > 0) if et.size else False,
    }


def peak_location_label(norm: np.ndarray, support: np.ndarray, near_half: np.ndarray, near_band: np.ndarray, far_band: np.ndarray) -> str:
    masked = np.where(support, norm, -1e9)
    y, x = np.unravel_index(int(np.argmax(masked)), masked.shape)
    x_rel = (x + 0.5 - CANVAS_W / 2.0) / (CORE_W / 2.0)
    y_rel = (y + 0.5 - CANVAS_H / 2.0) / (CORE_H / 2.0)
    if near_band[y, x]:
        side = "near_boundary"
    elif far_band[y, x]:
        side = "far_boundary"
    elif near_half[y, x]:
        side = "near_half"
    else:
        side = "far_half"
    if abs(x_rel) > 0.62:
        long_pos = "body_long_positive_end" if x_rel > 0 else "body_long_negative_end"
    else:
        long_pos = "body_middle"
    if abs(y_rel) > 0.55:
        short_pos = "body_short_positive_side" if y_rel > 0 else "body_short_negative_side"
    else:
        short_pos = "short_axis_middle"
    return f"{side};{long_pos};{short_pos};pixel=({x},{y})"


def subject_rows_by_frame() -> dict[tuple[int, str], dict[str, str]]:
    rows = read_csv(INPUTS["e0_r1_r1_subject_manifest"])
    return {(parse_int(row["sar_frame"]), row["subject_name"]): row for row in rows}


def counterfactual_specs(frames: Sequence[Mapping[str, Any]], selected_frames: Sequence[int]) -> list[dict[str, Any]]:
    subject_index = subject_rows_by_frame()
    geometry = scene_geometry()
    by_frame = {int(row["sar_frame"]): row for row in frames}
    selected = [frame for frame in selected_frames if frame in by_frame]
    if not selected:
        selected = [int(frames[0]["sar_frame"])]
    frame = selected[len(selected) // 2]
    vehicle = by_frame[frame]
    specs: list[dict[str, Any]] = []
    for subject in ["fixed_known_non_vehicle_N005", "fixed_strong_scatterer"]:
        row = subject_index.get((frame, subject))
        if row:
            specs.append(
                {
                    "subject_name": subject,
                    "sar_frame": frame,
                    "cx": parse_float(row.get("center_x")),
                    "cy": parse_float(row.get("center_y")),
                    "axis_deg": parse_float(row.get("angle_deg")),
                    "length_px": parse_float(row.get("width_px"), vehicle["body_length_px"]),
                    "width_px": parse_float(row.get("height_px"), vehicle["body_width_px"]),
                    "role": "fixed_non_vehicle_or_strong_scatterer",
                    "axis_family": "",
                    "direction_sign": "",
                    "offset_distance": "",
                    "gt_overlap_risk": "",
                }
            )
    # Keep the corridor separated by sign and overlap risk. Existing E0-R2 rows mark overlap risk.
    corridor_rows = [row for row in read_csv(INPUTS["e0_r2_gt_corridors"]) if parse_int(row.get("sar_frame")) == frame]
    candidate = None
    for row in corridor_rows:
        if row.get("offset_axis") == "body_short" and row.get("offset_m") in {"0.9", "-0.9"}:
            candidate = row
            break
    if candidate:
        signed_axis = vehicle.get("axis_signed_for_registration_deg", vehicle["axis_unsigned_deg"])
        axis = angle_unit(parse_float(signed_axis))
        short = (-axis[1], axis[0])
        direction = 1.0 if parse_float(candidate.get("offset_m")) >= 0 else -1.0
        offset_px = parse_float(candidate.get("offset_m")) / PX_TO_M
        cx = vehicle["cx"] + short[0] * offset_px
        cy = vehicle["cy"] + short[1] * offset_px
        specs.append(
            {
                "subject_name": "gt_attached_corridor_body_short",
                "sar_frame": frame,
                "cx": cx,
                "cy": cy,
                "axis_deg": parse_float(signed_axis),
                "length_px": vehicle["body_length_px"],
                "width_px": vehicle["body_width_px"],
                "role": "gt_attached_corridor",
                "axis_family": candidate.get("offset_axis", ""),
                "direction_sign": "positive" if direction > 0 else "negative",
                "offset_distance": candidate.get("offset_m", ""),
                "gt_overlap_risk": candidate.get("corridor_validity_status", ""),
            }
        )
    return specs


def save_canonical_visuals(
    frame: Mapping[str, Any],
    signed_axis: float,
    maps: Mapping[str, Any],
    metrics: Mapping[str, Any],
    subject_name: str = "vehicle",
    window_id: str = "",
) -> dict[str, Any]:
    frame_id = int(frame["sar_frame"])
    prefix = f"{subject_name}_sar{frame_id:06d}"
    raw_path = VISUAL_DIR / f"{prefix}_raw.png"
    norm_path = VISUAL_DIR / f"{prefix}_norm.png"
    overlay_path = VISUAL_DIR / f"{prefix}_overlay.png"
    render_heatmap(maps["raw"], raw_path, f"{prefix} raw canonical")
    render_heatmap(maps["norm"], norm_path, f"{prefix} local-normalized canonical")
    render_overlay(
        maps["raw"],
        maps["valid"],
        maps["support"],
        maps["near_band"],
        maps["far_band"],
        maps["radar_body_unit"],
        overlay_path,
        f"{prefix} radar-near overlay",
    )
    valid_fraction = float(np.mean(maps["valid"][maps["support"]])) if np.any(maps["support"]) else 0.0
    boundary_invalid = float(1.0 - np.mean(maps["valid"][maps["support"]])) if np.any(maps["support"]) else 1.0
    return {
        "map_id": prefix,
        "subject_name": subject_name,
        "sar_frame": frame_id,
        "window_id": window_id,
        "body_canonical_intensity_map": rel(raw_path),
        "body_canonical_normalized_map": rel(norm_path),
        "body_canonical_overlay": rel(overlay_path),
        "body_canonical_valid_mask": "stored_in_overlay_and_manifest",
        "body_support_mask": "core_128x64",
        "background_reference_mask": "outer_canvas_excluding_core",
        "body_canonical_transform": maps["transform"],
        "inverse_transform": maps["inverse"],
        "interpolation_mode": "bilinear_gray_intensity",
        "border_fill_value": "0",
        "radar_direction_in_body_frame": f"({fmt(maps['radar_body_unit'][0])},{fmt(maps['radar_body_unit'][1])})",
        "relative_aspect_angle_deg": fmt(frame.get("relative_aspect_angle_deg", "")),
        "range_m_corrected": fmt(frame.get("range_m_corrected", "")),
        "registration_reliability": registration_label(frame),
        "canonical_core_grid": f"{CORE_W}x{CORE_H}",
        "canonical_canvas_grid": f"{CANVAS_W}x{CANVAS_H}",
        "body_length_m": fmt(frame.get("body_length_m", "")),
        "body_width_m": fmt(frame.get("body_width_m", "")),
        "axis_signed_for_registration_deg": fmt(signed_axis),
        "local_background_median": fmt(maps["bg_median"]),
        "local_background_mad": fmt(maps["bg_mad"]),
        "valid_support_fraction": fmt(valid_fraction),
        "mask_area_change_flag": "PASS" if valid_fraction >= 0.95 else "PARTIAL",
        "near_peak_location": peak_location_label(maps["norm"], maps["support"], maps["near_half"], maps["near_band"], maps["far_band"]),
        "near_side_boundary_energy_fraction": fmt(metrics["near_side_boundary_energy_fraction"]),
        "far_side_boundary_energy_fraction": fmt(metrics["far_side_boundary_energy_fraction"]),
        "edge_or_interpolation_warning": "EDGE_OR_MASK_RISK" if boundary_invalid > 0.05 else "",
    }


def build_maps_and_manifests(
    frames: list[dict[str, Any]],
    axis_rows: Sequence[Mapping[str, Any]],
    manifest_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    cache: dict[int, np.ndarray] = {}
    axis_by_frame = {parse_int(row["sar_frame"]): row for row in axis_rows}
    frame_by_id = {int(row["sar_frame"]): row for row in frames}
    window_by_frame = {parse_int(row["sar_frame"]): row.get("window_id", "") for row in manifest_rows}
    selected = sorted(set(parse_int(row["sar_frame"]) for row in manifest_rows))
    canonical_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    maps_by_frame: dict[int, dict[str, Any]] = {}
    for frame_id in selected:
        frame = frame_by_id[frame_id]
        signed_axis = parse_float(axis_by_frame[frame_id]["axis_signed_for_registration_deg"])
        image = load_image(frame_id, cache)
        maps = canonical_map(image, frame["cx"], frame["cy"], signed_axis, frame["body_length_px"], frame["body_width_px"])
        radar_vec_img = (scene_geometry()["fan_center_x"] - frame["cx"], scene_geometry()["fan_center_y"] - frame["cy"])
        axis = angle_unit(signed_axis)
        short = (-axis[1], axis[0])
        radar_body = (radar_vec_img[0] * axis[0] + radar_vec_img[1] * axis[1], radar_vec_img[0] * short[0] + radar_vec_img[1] * short[1])
        radar_body_unit = unit(radar_body)
        near_half, far_half, near_band, far_band, tangent_coord = masks_for_near_side(frame["body_length_px"], frame["body_width_px"], radar_body_unit)
        metrics = boundary_metrics(maps["norm"], maps["valid"], near_band, far_band, tangent_coord)
        maps.update(
            {
                "radar_body_unit": radar_body_unit,
                "near_half": near_half,
                "far_half": far_half,
                "near_band": near_band,
                "far_band": far_band,
                "tangent_coord": tangent_coord,
            }
        )
        maps_by_frame[frame_id] = maps
        canonical_rows.append(save_canonical_visuals(frame, signed_axis, maps, metrics, "vehicle", window_by_frame.get(frame_id, "")))
        metric_rows.append(
            {
                "sar_frame": frame_id,
                "window_id": window_by_frame.get(frame_id, ""),
                "E_t_s_bins": ";".join(fmt(v) for v in metrics["E_t"]),
                "s_peak_t": fmt(metrics["s_peak_t"]),
                "secondary_peak": fmt(metrics["secondary_peak"]),
                "peak_count": metrics["peak_count"],
                "peak_width": fmt(metrics["peak_width"]),
                "peak_prominence": fmt(metrics["peak_prominence"]),
                "near_side_boundary_energy_fraction": fmt(metrics["near_side_boundary_energy_fraction"]),
                "far_side_boundary_energy_fraction": fmt(metrics["far_side_boundary_energy_fraction"]),
                "peak_inside_valid_mask": str(metrics["peak_inside_valid_mask"]).lower(),
                "near_peak_location": canonical_rows[-1]["near_peak_location"],
            }
        )
    counter_rows = build_counterfactual_maps(frames, selected, axis_by_frame, cache)
    return canonical_rows, metric_rows, maps_by_frame, counter_rows


def build_counterfactual_maps(
    frames: Sequence[Mapping[str, Any]],
    selected_frames: Sequence[int],
    axis_by_frame: Mapping[int, Mapping[str, Any]],
    cache: dict[int, np.ndarray],
) -> list[dict[str, Any]]:
    rows = []
    frame_by_id = {int(row["sar_frame"]): row for row in frames}
    for spec in counterfactual_specs(frames, selected_frames):
        frame = dict(frame_by_id[int(spec["sar_frame"])])
        frame["cx"] = spec["cx"]
        frame["cy"] = spec["cy"]
        frame["body_length_px"] = spec["length_px"]
        frame["body_width_px"] = spec["width_px"]
        frame["body_length_m"] = spec["length_px"] * PX_TO_M
        frame["body_width_m"] = spec["width_px"] * PX_TO_M
        axis = parse_float(spec["axis_deg"])
        image = load_image(int(spec["sar_frame"]), cache)
        maps = canonical_map(image, frame["cx"], frame["cy"], axis, frame["body_length_px"], frame["body_width_px"])
        radar_vec_img = (scene_geometry()["fan_center_x"] - frame["cx"], scene_geometry()["fan_center_y"] - frame["cy"])
        axis_unit_v = angle_unit(axis)
        short = (-axis_unit_v[1], axis_unit_v[0])
        radar_body = (radar_vec_img[0] * axis_unit_v[0] + radar_vec_img[1] * axis_unit_v[1], radar_vec_img[0] * short[0] + radar_vec_img[1] * short[1])
        radar_body_unit = unit(radar_body)
        near_half, far_half, near_band, far_band, tangent_coord = masks_for_near_side(frame["body_length_px"], frame["body_width_px"], radar_body_unit)
        metrics = boundary_metrics(maps["norm"], maps["valid"], near_band, far_band, tangent_coord)
        maps.update({"radar_body_unit": radar_body_unit, "near_half": near_half, "far_half": far_half, "near_band": near_band, "far_band": far_band})
        saved = save_canonical_visuals(frame, axis, maps, metrics, spec["subject_name"], "W_COUNTERFACTUAL")
        status = "COUNTERFACTUAL_CONTAMINATED_BY_GT" if "OVERLAP_RISK" in str(spec.get("gt_overlap_risk")) else "COUNTERFACTUAL_REVIEWABLE"
        rows.append(
            {
                "counterfactual_id": spec["subject_name"],
                "sar_frame": spec["sar_frame"],
                "counterfactual_role": spec["role"],
                "axis_family": spec.get("axis_family", ""),
                "direction_sign": spec.get("direction_sign", ""),
                "offset_distance": spec.get("offset_distance", ""),
                "gt_overlap_risk": spec.get("gt_overlap_risk", ""),
                "counterfactual_status": status,
                "near_side_boundary_energy_fraction": saved["near_side_boundary_energy_fraction"],
                "far_side_boundary_energy_fraction": saved["far_side_boundary_energy_fraction"],
                "near_peak_location": saved["near_peak_location"],
                "diagnostic_png": saved["body_canonical_overlay"],
                "interpretation": "cannot_reject_background_if_contaminated" if status == "COUNTERFACTUAL_CONTAMINATED_BY_GT" else "same_canonical_flow_reviewable",
            }
        )
    return rows


def contact_sheet(image_paths: Sequence[Path], path: Path, title: str, columns: int = 4) -> None:
    thumbs: list[tuple[Path, Image.Image]] = []
    for img_path in image_paths:
        if img_path.exists():
            thumbs.append((img_path, Image.open(img_path).convert("RGB").resize((320, 230))))
    if not thumbs:
        return
    rows = math.ceil(len(thumbs) / columns)
    canvas = Image.new("RGB", (columns * 340, rows * 270 + 40), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 12), title, fill=(0, 0, 0))
    for idx, (img_path, thumb) in enumerate(thumbs):
        x = (idx % columns) * 340 + 10
        y = (idx // columns) * 270 + 40
        canvas.paste(thumb, (x, y))
        draw.text((x, y + 234), img_path.stem[:42], fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def render_summary_visuals(
    canonical_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    frames: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    raw_paths = [REPO_ROOT / row["body_canonical_intensity_map"] for row in canonical_rows if row["subject_name"] == "vehicle"]
    norm_paths = [REPO_ROOT / row["body_canonical_normalized_map"] for row in canonical_rows if row["subject_name"] == "vehicle"]
    overlay_paths = [REPO_ROOT / row["body_canonical_overlay"] for row in canonical_rows if row["subject_name"] == "vehicle"]
    raw_sheet = VISUAL_DIR / "vehicle_canonical_raw_time_contact_sheet.png"
    norm_sheet = VISUAL_DIR / "vehicle_canonical_norm_time_contact_sheet.png"
    overlay_sheet = VISUAL_DIR / "vehicle_canonical_overlay_contact_sheet.png"
    contact_sheet(raw_paths, raw_sheet, "Vehicle body-canonical raw maps by time")
    contact_sheet(norm_paths, norm_sheet, "Vehicle body-canonical local-normalized maps by time")
    contact_sheet(overlay_paths, overlay_sheet, "Vehicle radar-near overlays")

    by_frame = {int(row["sar_frame"]): row for row in frames}
    et_rows = []
    for row in metric_rows:
        et_rows.append([parse_float(v) for v in row["E_t_s_bins"].split(";") if v != ""])
    et_arr = np.asarray(et_rows, dtype=float) if et_rows else np.zeros((1, BOUNDARY_BINS), dtype=float)
    et_path = VISUAL_DIR / "vehicle_E_t_s_heatmap.png"
    render_heatmap(et_arr, et_path, "E_t(s) near-side boundary heatmap")

    s_time = VISUAL_DIR / "vehicle_s_peak_time.png"
    s_aspect = VISUAL_DIR / "vehicle_s_peak_aspect.png"
    draw_scatter(
        [(parse_int(row["sar_frame"]), parse_float(row["s_peak_t"]), row.get("window_id", "")) for row in metric_rows],
        s_time,
        "s_peak_t versus SAR frame",
        "sar_frame",
        "s_peak_t",
    )
    draw_scatter(
        [(by_frame[parse_int(row["sar_frame"])]["relative_aspect_angle_deg"], parse_float(row["s_peak_t"]), str(row["sar_frame"])) for row in metric_rows],
        s_aspect,
        "s_peak_t versus relative aspect",
        "relative_aspect_angle_deg",
        "s_peak_t",
    )
    return {
        "raw_time_contact_sheet": rel(raw_sheet),
        "norm_time_contact_sheet": rel(norm_sheet),
        "overlay_contact_sheet": rel(overlay_sheet),
        "E_t_s_heatmap": rel(et_path),
        "s_peak_time": rel(s_time),
        "s_peak_aspect": rel(s_aspect),
    }


def draw_scatter(points: Sequence[tuple[float, float, str]], path: Path, title: str, x_label: str, y_label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (920, 560), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 15), title, fill=(0, 0, 0))
    x0, y0, w, h = 70, 70, 790, 390
    draw.rectangle((x0, y0, x0 + w, y0 + h), outline=(40, 40, 40))
    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        if xmax == xmin:
            xmax += 1
        if ymax == ymin:
            ymax += 1
        for x, y, label in points:
            px = x0 + int((x - xmin) / (xmax - xmin) * w)
            py = y0 + h - int((y - ymin) / (ymax - ymin) * h)
            draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(20, 110, 220))
            draw.text((px + 5, py - 6), label[:8], fill=(0, 0, 0))
    draw.text((x0, y0 + h + 20), x_label, fill=(0, 0, 0))
    draw.text((x0 + w - 80, y0 + h + 20), y_label, fill=(0, 0, 0))
    img.save(path)


def diff_audit(
    metric_rows: Sequence[Mapping[str, Any]],
    maps_by_frame: Mapping[int, Mapping[str, Any]],
    frames: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_frame = {int(row["sar_frame"]): row for row in frames}
    rows = []
    metric_by_frame = {parse_int(row["sar_frame"]): row for row in metric_rows}
    frame_ids = sorted(maps_by_frame)
    pairs = [(a, b) for a, b in zip(frame_ids, frame_ids[1:]) if b - a <= 4]
    for a, b in pairs[:8]:
        cur = maps_by_frame[a]
        nxt = maps_by_frame[b]
        common = cur["valid"] & nxt["valid"] & cur["support"] & nxt["support"]
        delta = np.where(common, nxt["norm"] - cur["norm"], 0.0)
        gain = np.maximum(delta, 0.0)
        loss = np.maximum(-delta, 0.0)
        near = cur["near_band"] | nxt["near_band"]
        gain_near = float(np.sum(gain[near])) / max(float(np.sum(gain)), 1e-9)
        loss_near = float(np.sum(loss[near])) / max(float(np.sum(loss)), 1e-9)
        gain_yx = np.unravel_index(int(np.argmax(gain)), gain.shape)
        loss_yx = np.unravel_index(int(np.argmax(loss)), loss.shape)
        spatial_gap = math.hypot(float(gain_yx[1] - loss_yx[1]), float(gain_yx[0] - loss_yx[0]))
        diff_path = VISUAL_DIR / f"vehicle_diff_sar{a:06d}_to_{b:06d}.png"
        render_heatmap(delta, diff_path, f"delta A: SAR {a} -> {b}")
        maybe_registration = abs(by_frame[b]["cx"] - by_frame[a]["cx"]) > 20.0 or abs(parse_float(metric_by_frame[b]["s_peak_t"]) - parse_float(metric_by_frame[a]["s_peak_t"])) < 0.02
        rows.append(
            {
                "frame_a": a,
                "frame_b": b,
                "delta_png": rel(diff_path),
                "gain_near_boundary_fraction": fmt(gain_near),
                "loss_near_boundary_fraction": fmt(loss_near),
                "gain_peak_xy": f"({gain_yx[1]},{gain_yx[0]})",
                "loss_peak_xy": f"({loss_yx[1]},{loss_yx[0]})",
                "gain_loss_peak_distance_px": fmt(spatial_gap),
                "s_peak_delta": fmt(parse_float(metric_by_frame[b]["s_peak_t"]) - parse_float(metric_by_frame[a]["s_peak_t"])),
                "mask_common_fraction": fmt(float(np.mean(common[cur["support"]])) if np.any(cur["support"]) else 0),
                "manual_review_hint": "possible_registration_or_whole-map_motion" if maybe_registration else "localized_gain_loss_reviewable",
            }
        )
    diff_sheet = VISUAL_DIR / "vehicle_diff_contact_sheet.png"
    contact_sheet([REPO_ROOT / row["delta_png"] for row in rows], diff_sheet, "Vehicle selected frame-pair delta maps", columns=3)
    return rows


def perturbation_audit(
    manifest_rows: Sequence[Mapping[str, Any]],
    frames: Sequence[Mapping[str, Any]],
    axis_rows: Sequence[Mapping[str, Any]],
    maps_by_frame: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    frame_by_id = {int(row["sar_frame"]): row for row in frames}
    axis_by_frame = {parse_int(row["sar_frame"]): row for row in axis_rows}
    cache: dict[int, np.ndarray] = {}
    rows: list[dict[str, Any]] = []
    selected = sorted(set(parse_int(row["sar_frame"]) for row in manifest_rows))[:4]
    perturbations = [
        ("center_dx_plus_1px", 1.0, 0.0, 0.0, 1.0, 1.0),
        ("center_dy_plus_1px", 0.0, 1.0, 0.0, 1.0, 1.0),
        ("axis_plus_2deg", 0.0, 0.0, 2.0, 1.0, 1.0),
        ("scale_plus_2pct", 0.0, 0.0, 0.0, 1.02, 1.02),
    ]
    for frame_id in selected:
        frame = frame_by_id[frame_id]
        original = maps_by_frame[frame_id]["norm"]
        image = load_image(frame_id, cache)
        signed_axis = parse_float(axis_by_frame[frame_id]["axis_signed_for_registration_deg"])
        for name, dx, dy, da, sl, sw in perturbations:
            maps = canonical_map(
                image,
                frame["cx"] + dx,
                frame["cy"] + dy,
                signed_axis + da,
                frame["body_length_px"] * sl,
                frame["body_width_px"] * sw,
            )
            diff = maps["norm"] - original
            diff_abs = float(np.mean(np.abs(diff[maps["support"] & maps["valid"]])))
            path = VISUAL_DIR / f"perturb_{name}_sar{frame_id:06d}.png"
            render_heatmap(diff, path, f"registration perturbation {name} SAR {frame_id}")
            rows.append(
                {
                    "sar_frame": frame_id,
                    "perturbation_id": name,
                    "center_dx_px": fmt(dx),
                    "center_dy_px": fmt(dy),
                    "axis_delta_deg": fmt(da),
                    "length_scale": fmt(sl),
                    "width_scale": fmt(sw),
                    "mean_abs_canonical_diff": fmt(diff_abs),
                    "diagnostic_png": rel(path),
                    "manual_judgement": "REGISTRATION_SENSITIVITY_VISIBLE" if diff_abs >= 0.35 else "REGISTRATION_SENSITIVITY_LIMITED",
                }
            )
    sheet = VISUAL_DIR / "registration_perturbation_contact_sheet.png"
    contact_sheet([REPO_ROOT / row["diagnostic_png"] for row in rows], sheet, "Registration perturbation diff maps", columns=4)
    return rows


def build_failure_ledger(range_rows: Sequence[Mapping[str, Any]], axis_rows: Sequence[Mapping[str, Any]], summary_rows: Sequence[Mapping[str, Any]], counter_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = [
        {
            "failure_id": "E0_R1_ZERO_CONFUSION_WITHDRAWN",
            "severity": "high",
            "evidence": "old G10 used is_vehicle and made non-vehicle pass impossible",
            "interpretation": "zero confusion was a definition artifact",
        },
        {
            "failure_id": "E0_R2_RANGE_CONFOUNDER_REJECTION_WITHDRAWN",
            "severity": "high",
            "evidence": "legacy range used image-origin distance; E0-R3 recomputes from fan center",
            "interpretation": "range confounder rejection must be reaudited",
        },
        {
            "failure_id": "RESPONSE_INDEX_DOWNGRADED",
            "severity": "medium",
            "evidence": "equal-weight mean of nine standardized descriptors",
            "interpretation": "exploratory summary only",
        },
        {
            "failure_id": "SAME_ASPECT_REPEATABILITY_NOT_EVALUABLE",
            "severity": "medium",
            "evidence": "E0-R2 different_aspect_similar_range pairs=0",
            "interpretation": "cannot claim repeatability support",
        },
    ]
    over = [row for row in range_rows if row["within_40m_domain"] != "true"]
    if over:
        failures.append(
            {
                "failure_id": "CORRECTED_RANGE_OUTSIDE_40M_DOMAIN",
                "severity": "high",
                "evidence": f"frames={';'.join(row['sar_frame'] for row in over[:12])}",
                "interpretation": "stop expansion until coordinate mapping is resolved",
            }
        )
    bad_axis = [row for row in axis_rows if row["registration_axis_status"] == "FAIL"]
    if bad_axis:
        failures.append(
            {
                "failure_id": "AXIS_CONTINUITY_FAILURE_IN_REVIEW_SET",
                "severity": "high",
                "evidence": f"frames={';'.join(str(row['sar_frame']) for row in bad_axis[:12])}",
                "interpretation": "canonical maps may flip or create false transport",
            }
        )
    ident = next(row for row in summary_rows if row["audit_item"] == "ASPECT_CAUSAL_IDENTIFIABILITY")
    if ident["status"] != "PARTIAL":
        failures.append(
            {
                "failure_id": "ASPECT_CAUSAL_IDENTIFIABILITY_NOT_READY",
                "severity": "high",
                "evidence": ident["evidence"],
                "interpretation": "do not claim aspect-driven mechanism",
            }
        )
    contaminated = [row for row in counter_rows if row["counterfactual_status"] == "COUNTERFACTUAL_CONTAMINATED_BY_GT"]
    if contaminated:
        failures.append(
            {
                "failure_id": "GT_ATTACHED_CORRIDOR_CONTAMINATED",
                "severity": "medium",
                "evidence": ";".join(row["counterfactual_id"] for row in contaminated),
                "interpretation": "corridor cannot reject background explanation",
            }
        )
    return failures


def gate_status_rows(
    range_rows: Sequence[Mapping[str, Any]],
    axis_rows: Sequence[Mapping[str, Any]],
    summary_rows: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    perturb_rows: Sequence[Mapping[str, Any]],
    counter_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    range_over = sum(1 for row in range_rows if row["within_40m_domain"] != "true")
    old_over = sum(1 for row in range_rows if row["legacy_within_40m_domain"] != "true")
    bad_axis = sum(1 for row in axis_rows if row["registration_axis_status"] == "FAIL")
    valid_fracs = [parse_float(row["valid_support_fraction"]) for row in canonical_rows if row["subject_name"] == "vehicle"]
    min_valid = min(valid_fracs) if valid_fracs else 0.0
    ident = next(row for row in summary_rows if row["audit_item"] == "ASPECT_CAUSAL_IDENTIFIABILITY")
    near_fracs = [parse_float(row["near_side_boundary_energy_fraction"]) for row in metric_rows]
    near_med = statistics.median(near_fracs) if near_fracs else 0.0
    reg_visible = sum(1 for row in perturb_rows if row["manual_judgement"] == "REGISTRATION_SENSITIVITY_VISIBLE")
    counter_done = len(counter_rows) >= 3
    rows = [
        gate("REPOSITORY_LINEAGE_VERIFIED", "PASS", f"branch={git_output(['branch','--show-current'])};ancestor={FROZEN_ANCESTOR}", "", "yes"),
        gate("REQUIRED_FROZEN_ARTIFACTS_READ", "PASS", f"inventory_rows={len(reading_inventory())}", "", "yes"),
        gate("LEGACY_CONCLUSIONS_WITHDRAWN", "PASS", "zero-confusion and range-confounder support withdrawn; response_index exploratory only", "", "yes"),
        gate("METRIC_RANGE_ORIGIN_CORRECTED", "PASS", "range_m=hypot(cx-fan_center_x,cy-fan_center_y)*0.03", "", "yes"),
        gate("CORRECTED_RANGE_WITHIN_IMAGING_DOMAIN", "PASS" if range_over == 0 else "FAIL", f"corrected_over40={range_over};legacy_over40={old_over}", "corrected range outside 40m" if range_over else "", "yes" if range_over == 0 else "no"),
        gate("ASPECT_RANGE_TIME_IDENTIFIABILITY_AUDITED", "PASS", f"summary_rows={len(summary_rows)}", "", "yes"),
        gate("ASPECT_CAUSAL_IDENTIFIABILITY", ident["status"], ident["evidence"], "independent controls not closed" if ident["status"] == "NOT_READY" else "", "no" if ident["status"] == "NOT_READY" else "limited"),
        gate("BODY_AXIS_SIGN_CONTINUITY_VALID", "PASS" if bad_axis == 0 else "FAIL", f"axis_fail_count={bad_axis}", "axis flip/low reliability" if bad_axis else "", "yes" if bad_axis == 0 else "no"),
        gate("BODY_CANONICAL_INPUTS_SUFFICIENT", "PASS" if canonical_rows else "FAIL", f"vehicle_maps={sum(1 for row in canonical_rows if row['subject_name']=='vehicle')};L/W=4.764934/2.077648", "", "yes"),
        gate("BODY_CANONICAL_FIELD_VALID", "PASS" if min_valid >= 0.95 else "PARTIAL", f"min_valid_support_fraction={fmt(min_valid)}", "some support pixels near edge or invalid" if min_valid < 0.95 else "", "yes"),
        gate("NEAR_SIDE_RESPONSE_LOCALIZATION_VISUALLY_AUDITED", "PARTIAL", f"median_near_boundary_fraction={fmt(near_med)};requires manual visual review", "not a supported mechanism claim", "limited"),
        gate("MINIMAL_STRUCTURAL_TIMELINE_VISUALLY_AUDITED", "PARTIAL", f"review_windows={len(set(row['window_id'] for row in metric_rows))}", "minimal windows only", "limited"),
        gate("REGISTRATION_FAILURE_MODES_AUDITED", "PARTIAL" if reg_visible else "PASS", f"visible_perturbation_cases={reg_visible}", "some structure may be registration-sensitive" if reg_visible else "", "limited"),
        gate("MINIMAL_COUNTERFACTUAL_STRUCTURAL_AUDIT_COMPLETED", "PARTIAL" if counter_done else "NOT_READY", f"counterfactual_rows={len(counter_rows)}", "GT-attached corridor contamination blocks rejection" if any(row["counterfactual_status"] == "COUNTERFACTUAL_CONTAMINATED_BY_GT" for row in counter_rows) else "", "limited"),
        gate("NEAR_SIDE_RESPONSE_MIGRATION_SUPPORTED", "NOT_READY", "minimal visual audit only", "no full transport closure", "no"),
        gate("RESPONSE_TRANSPORT_BEYOND_REGISTRATION_SUPPORTED", "NOT_READY", "perturbation audit is sensitivity only", "transport beyond registration not established", "no"),
        gate("ASPECT_EFFECT_BEYOND_RANGE_AND_TIME_SUPPORTED", "NOT_READY", "ASPECT_CAUSAL_IDENTIFIABILITY not closed", "range/time controls not sufficient for causality", "no"),
        gate("GT_ATTACHED_CORRIDOR_STRUCTURAL_COUNTERFACTUAL_REJECTED", "NOT_READY", "corridor rows retain overlap-risk separation", "contaminated corridors cannot reject background", "no"),
        gate("PERSISTENT_STRONG_STRUCTURAL_COUNTERFACTUAL_REJECTED", "NOT_READY", "fixed/persistent strong rendered only as minimal counterfactual", "visual parity not enough for rejection", "no"),
        gate("VEHICLE_BODY_STRUCTURAL_DYNAMICS_SUPPORTED", "PARTIAL", "minimal selected windows show reviewable structure indices", "not full sequence support", "limited"),
        gate("E0_R3_PHYSICAL_MECHANISM_SUPPORTED", "NOT_READY", "requires near-side, dynamics, aspect causality, registration, and counterfactual closure", "not closed in first audit", "no"),
    ]
    return rows


def gate(gate_id: str, status: str, evidence: str, failure_reason: str, next_step_allowed: str) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": status,
        "evidence": evidence,
        "failure_reason": failure_reason,
        "next_step_allowed": next_step_allowed,
    }


VISUAL_REVIEW_NOTES = [
    (
        "W_STABLE SAR 339-341",
        "雷达近侧在规范图下侧偏 body_long_positive 端。339 和 341 的主响应贴近下侧近侧边界，340 仍在同一端部但更偏短轴中段；空间位置基本稳定。339->340 的差分呈整条下侧带红蓝互换，说明幅值变化可能受 1 px 级中心或轴向配准影响，不应作为输运证据。",
    ),
    (
        "W_SLIDE SAR 321-325",
        "雷达近侧持续落在下侧斜向边界，主响应始终在 body_long_positive 端和近侧长边交界。321 到 323 的峰位向近侧中段回撤，323 到 325 又回到更靠右下端，表现为局部增强和回跳，而不是单调沿边界滑动。该窗口可作为候选结构动力学案例，但不能单独支持 aspect 驱动。",
    ),
    (
        "W_SWITCH SAR 351-353",
        "近侧方向仍指向下侧，强响应从 351 的近侧长边带扩展到 352 的右下端部集中区，353 又出现右侧短轴侧强点。这里更像端部与近侧长边之间的主响应接管/再分配，而不是旧峰连续平移；可进入后续人工复核，但需要配准扰动和背景对照约束。",
    ),
    (
        "W_SPLIT SAR 384-386",
        "雷达近侧翻到规范图下侧偏 body_long_negative 端，384-386 的下侧高能带仍存在，但左上背景强散射和底边强带同时显著。384->385 的 gain/loss 峰距很大且差分像整体形变，分裂/合并只能记为疑似事件，不能进入物理支持。",
    ),
    (
        "W_DIFFICULT SAR 386-388",
        "386/387 仍有下侧近侧高能带，388 的主峰转到 body_middle 附近，axis reliability 为 LOW，并伴随上方和左侧孤立强点。该段适合记录失败模式，不适合进入输运或 aspect 因果分析。",
    ),
    (
        "Registration perturbation",
        "已打开 registration perturbation contact sheet。1 px 中心平移、2 deg 轴扰动和 2% 尺度扰动都能在同一高能带附近制造红蓝交错差分；轴旋转和尺度扰动尤其呈全图放射或条带变化。因此滑动、切换和分裂候选必须标记 registration-sensitive。",
    ),
    (
        "Counterfactual SAR 352",
        "N005 和 fixed strong scatterer 在同一规范流程下也产生局部高能结构，其中 fixed strong 的 near-side fraction 高于车辆若干帧的远侧基线。GT-attached corridor 的强响应贴近下侧车辆高能带且为 overlap-risk corridor，不能用于拒绝背景解释。",
    ),
    (
        "E_t(s) and s_peak plots",
        "E_t(s) 热图和 s_peak 图显示峰位跳动和回跳，不是平滑单调迁移；321-325 与 384-388 都不满足独立 aspect 因果闭合。",
    ),
]


def append_visual_review_notes(lines: list[str]) -> None:
    lines.extend(["", "## Manual Visual Review Notes", ""])
    for window, judgement in VISUAL_REVIEW_NOTES:
        lines.append(f"- `{window}`: {judgement}")


def visual_casebook(
    manifest_rows: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    diff_rows: Sequence[Mapping[str, Any]],
    counter_rows: Sequence[Mapping[str, Any]],
    summary_visuals: Mapping[str, str],
) -> str:
    metric_by_frame = {parse_int(row["sar_frame"]): row for row in metric_rows}
    canon_by_frame = {parse_int(row["sar_frame"]): row for row in canonical_rows if row["subject_name"] == "vehicle"}
    lines = [
        "# E0-R3 GM_RM017 Body-Canonical Visual Casebook",
        "",
        "本 casebook 记录首轮可视化审阅入口。PNG 位于 ignored `outputs/`，本文件只保存相对路径和逐窗判断。",
        "",
        "## Contact Sheets",
        "",
    ]
    for key, value in summary_visuals.items():
        lines.append(f"- `{key}`: `{value}`")
    append_visual_review_notes(lines)
    lines.extend(["", "## Vehicle Windows", ""])
    for row in manifest_rows:
        frame = parse_int(row["sar_frame"])
        metric = metric_by_frame.get(frame, {})
        canon = canon_by_frame.get(frame, {})
        near_frac = parse_float(metric.get("near_side_boundary_energy_fraction"))
        far_frac = parse_float(metric.get("far_side_boundary_energy_fraction"))
        location = canon.get("near_peak_location", "")
        if near_frac > far_frac * 1.2:
            near_text = "近侧边界能量高于远侧，近侧定位有局部迹象"
        elif near_frac < far_frac * 0.8:
            near_text = "远侧或非近侧能量更强，近侧定位不稳"
        else:
            near_text = "近远侧能量接近，不能单独支持近侧定位"
        lines.extend(
            [
                f"### {row['window_id']} SAR {frame}",
                "",
                f"- 图像：`{canon.get('body_canonical_overlay','')}`",
                f"- 近侧方向：`{canon.get('radar_direction_in_body_frame','')}`；{near_text}。",
                f"- 主响应位置：`{location}`；`s_peak={metric.get('s_peak_t','')}`，峰数 `{metric.get('peak_count','')}`。",
                f"- 稳定/滑动/切换判断：该帧属于 `{row['expected_review_role']}`，需要结合相邻帧差分；当前只能作为最小窗口证据。",
                f"- 配准和 mask 疑点：registration `{row['registration_reliability']}`；{canon.get('edge_or_interpolation_warning','无明显边界告警')}。",
                f"- 后续输运适合性：{'谨慎进入局部输运候选' if row['registration_reliability'] != 'LOW' else '不适合进入输运，先处理配准/轴向可靠性'}。",
                "",
            ]
        )
    lines.extend(["## Frame Differences", ""])
    for row in diff_rows:
        lines.append(
            f"- SAR {row['frame_a']} -> {row['frame_b']}: `s_peak_delta={row['s_peak_delta']}`, "
            f"gain near `{row['gain_near_boundary_fraction']}`, loss near `{row['loss_near_boundary_fraction']}`, "
            f"hint `{row['manual_review_hint']}`, PNG `{row['delta_png']}`."
        )
    lines.extend(["", "## Counterfactuals", ""])
    for row in counter_rows:
        lines.append(
            f"- `{row['counterfactual_id']}` SAR {row['sar_frame']}: status `{row['counterfactual_status']}`, "
            f"near fraction `{row['near_side_boundary_energy_fraction']}`, location `{row['near_peak_location']}`, "
            f"PNG `{row['diagnostic_png']}`."
        )
    lines.append("")
    return "\n".join(lines)


def report_text(
    frames: Sequence[Mapping[str, Any]],
    range_rows: Sequence[Mapping[str, Any]],
    ident_summary: Sequence[Mapping[str, Any]],
    axis_rows: Sequence[Mapping[str, Any]],
    manifest_rows: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    diff_rows: Sequence[Mapping[str, Any]],
    perturb_rows: Sequence[Mapping[str, Any]],
    counter_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    gate_rows: Sequence[Mapping[str, Any]],
    summary_visuals: Mapping[str, str],
) -> str:
    old_over = sum(1 for row in range_rows if row["legacy_within_40m_domain"] != "true")
    corrected_over = sum(1 for row in range_rows if row["within_40m_domain"] != "true")
    ranges = [parse_float(row["range_m_corrected"]) for row in range_rows]
    fan = scene_geometry()
    ident = {row["audit_item"]: row for row in ident_summary}
    axis_fail = sum(1 for row in axis_rows if row["registration_axis_status"] == "FAIL")
    valid_fracs = [parse_float(row["valid_support_fraction"]) for row in canonical_rows if row["subject_name"] == "vehicle"]
    near_fracs = [parse_float(row["near_side_boundary_energy_fraction"]) for row in metric_rows]
    lines = [
        "# WGV3.6B-E0-R3 GM_RM017 Body-Canonical First Audit",
        "",
        "## 结论",
        "",
        "- 核心回答：`当前证据不足`。",
        "- 近侧定位：`部分支持`，仅限代表窗口的 body-canonical 可视化。",
        "- 同车结构动力学：`部分支持`，存在可审阅的峰位、增益/损失和碎裂度变化，但只是最小窗口。",
        "- aspect 因果：`当前不可评价`，`ASPECT_CAUSAL_IDENTIFIABILITY=NOT_READY`。",
        "- 超越配准误差：`当前证据不足`，扰动审计显示部分差异对小扰动敏感。",
        "- 超越背景反事实：`当前证据不足`，GT-attached corridor 仍有 contamination/overlap 风险。",
        "",
        "## 研究问题与证据链复位",
        "",
        "E0-R2 实际建立的是同一 GM_RM017 线程上 relative aspect、若干响应描述符和若干背景对照之间的探索性关系。它证明了这些表可以在冻结分段和同一后验 GT 线程上复现，但没有证明车体结构响应场已经被识别，也没有证明 aspect 是独立因果变量。",
        "",
        "E0-R2 没有验证 `A_t(u,v)`：它主要处理逐帧描述符和 `response_index`，而逐帧向量会丢失高能区在车体长轴、短轴、近侧边界和端部之间的空间迁移。车辆身份也不能只用来组织样本；同一物理车辆身份必须提供一个可对齐的车体坐标系，否则响应的滑动、切换、分裂和合并无法区分于坐标翻转或配准抖动。",
        "",
        "本轮因此把问题改写为冻结 GT 中心、冻结车体轴代理和冻结 L/W 支撑下的 `A_t(u,v)` 审计。可以继承的是同车中心序列、轴向语义、L/W 图像网格支撑、SAR fan center 和旧 hard-negative 压力；必须撤回或降级的是 E0-R1 零混淆、E0-R2 range confounder rejection、`response_index` 证据地位、same-aspect repeatability、整体 corridor 排除和 motion tangent yaw。当前仍不可识别的是 aspect 独立因果、完整输运、背景反事实排除和跨车辆机制。",
        "",
        "## 旧结论撤回与降级表",
        "",
        "| item | E0-R3 status | reason |",
        "| --- | --- | --- |",
        "| `multi_gate_physical_confusions=0` | `WITHDRAWN` | 旧 G10 使用 `is_vehicle`，零混淆由定义保证。 |",
        "| `RANGE_CONFOUNDER_REJECTED` | `WITHDRAWN` | E0-R2 range 相对图像左上角，本轮改为 fan center。 |",
        "| `response_index` | `EXPLORATORY_ONLY` | 9 个标准化描述符等权平均，不再作为 Gate 或机制证据。 |",
        "| same-aspect repeatability | `NOT_EVALUABLE_NO_DIFFERENT_ASPECT_MATCHED_PAIRS` | E0-R2 `different_pairs=0`。 |",
        "| corridor 排除 | `DOWNGRADED` | sign、offset、GT-overlap risk 未能合并排除。 |",
        "| 运动切线 yaw | `AXIAL_PROXY_ONLY` | 只用于 180 度配准连续性，不是真实 yaw。 |",
        "| aspect CI / E0-R2 多视角机制 | `NOT_READY` | 诊断域、时间/随机对照和 pair family 未闭合。 |",
        "",
        "## 距离原点纠偏",
        "",
        f"- fan center: `({fmt(fan['fan_center_x'])}, {fmt(fan['fan_center_y'])})`",
        f"- frames: `{len(range_rows)}`",
        f"- corrected range min/max: `{fmt(min(ranges))}` / `{fmt(max(ranges))}` m",
        f"- corrected over 40 m: `{corrected_over}`",
        f"- old over 40 m: `{old_over}`",
        f"- failure ledger count: `{len(failure_rows)}`",
        f"- Gate: `{next(row['status'] for row in gate_rows if row['gate_id']=='CORRECTED_RANGE_WITHIN_IMAGING_DOMAIN')}`",
        "",
        "## aspect/range/time 可识别性",
        "",
        f"- 相近距离不同 aspect 对数: `{ident['similar_range_different_aspect_pairs']['value']}`",
        f"- 相近 aspect 不同距离对数: `{ident['similar_aspect_different_range_pairs']['value']}`",
        f"- 非相邻相似 aspect 对数: `{ident['non_adjacent_similar_aspect_pairs']['value']}`",
        f"- 不同 aspect 相近距离对数: `{ident['different_aspect_similar_range_pairs']['value']}`",
        f"- aspect-time Spearman: `{ident['aspect_time_spearman']['value']}`",
        f"- aspect-range Spearman: `{ident['aspect_range_spearman']['value']}`",
        f"- `ASPECT_CAUSAL_IDENTIFIABILITY={ident['ASPECT_CAUSAL_IDENTIFIABILITY']['status']}`",
        "",
        "## 车体规范坐标审计",
        "",
        f"- same-vehicle frames: `{len(frames)}`",
        f"- selected usable vehicle maps: `{sum(1 for row in canonical_rows if row['subject_name']=='vehicle')}`",
        f"- axis continuity failures: `{axis_fail}`",
        "- 180 deg handling: choose `theta` or `theta+180` by minimal directed residual to the previous reliable frame.",
        f"- canonical core grid: `{CORE_W}x{CORE_H}`; canvas `{CANVAS_W}x{CANVAS_H}`",
        "- L/W: `4.764934 m / 2.077648 m` image-grid support.",
        "- interpolation: bilinear intensity sampling; invalid pixels filled with 0 and tracked by valid mask.",
        f"- min valid support fraction: `{fmt(min(valid_fracs) if valid_fracs else 0)}`",
        f"- median near-side boundary energy fraction: `{fmt(statistics.median(near_fracs) if near_fracs else 0)}`",
        "",
        "## 实际视觉审阅入口",
        "",
    ]
    for key, path in summary_visuals.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(["", "代表窗口见 visual casebook；摘要如下：", ""])
    for window, judgement in VISUAL_REVIEW_NOTES:
        lines.append(f"- `{window}`: {judgement}")
    lines.extend(["", "逐帧指标入口如下：", ""])
    for row in manifest_rows:
        metric = next((m for m in metric_rows if parse_int(m["sar_frame"]) == parse_int(row["sar_frame"])), {})
        canon = next((c for c in canonical_rows if c["subject_name"] == "vehicle" and parse_int(c["sar_frame"]) == parse_int(row["sar_frame"])), {})
        lines.append(
            f"- `{row['window_id']}` SAR `{row['sar_frame']}`: near direction `{canon.get('radar_direction_in_body_frame','')}`, "
            f"main `{canon.get('near_peak_location','')}`, s_peak `{metric.get('s_peak_t','')}`, "
            f"registration `{row['registration_reliability']}`, review role `{row['expected_review_role']}`."
        )
    lines.extend(
        [
            "",
            "## 反事实初步结果",
            "",
        ]
    )
    for row in counter_rows:
        lines.append(
            f"- `{row['counterfactual_id']}`: status `{row['counterfactual_status']}`, near fraction `{row['near_side_boundary_energy_fraction']}`, "
            f"location `{row['near_peak_location']}`, PNG `{row['diagnostic_png']}`."
        )
    lines.extend(["", "## Gate 状态表", "", "| gate | status | evidence | failure | next |", "| --- | --- | --- | --- | --- |"])
    for row in gate_rows:
        lines.append(f"| `{row['gate_id']}` | `{row['status']}` | {row['evidence']} | {row['failure_reason']} | {row['next_step_allowed']} |")
    lines.extend(
        [
            "",
            "## 对核心问题的当前回答",
            "",
            "`当前证据不足`。近侧定位在最小窗口中有部分可见证据，同车结构动力学也有可审阅的峰位和差分变化；但 aspect 因果不可识别，配准扰动和背景反事实尚未排除。因此不能回答为当前支持，也不能把 E0-R3 物理机制提升为 supported。",
            "",
            "## 下一步建议",
            "",
            "下一阶段只做一个受控扩展：在当前 E0-R3 规范场基础上补充一个真正低 GT-overlap 风险的 corridor 或固定背景窗口，并对相同代表窗口做人工复核后再决定是否扩大到更长序列。",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> None:
    ensure_dirs()
    inventory_rows = reading_inventory()
    write_csv(OUTPUTS["reading_inventory"], inventory_rows, ["artifact_key", "path", "exists", "sha256", "row_count", "read_role"])
    missing = [row["path"] for row in inventory_rows if row["exists"] != "true"]
    if missing:
        raise RuntimeError(f"required frozen artifacts missing: {missing}")

    frames = load_frame_table()
    range_rows = write_range_correction(frames)
    axis_rows = axis_continuity(frames)
    axis_by_frame = {parse_int(row["sar_frame"]): row for row in axis_rows}
    for frame in frames:
        axis_row = axis_by_frame[int(frame["sar_frame"])]
        frame["axis_signed_for_registration_deg"] = parse_float(axis_row["axis_signed_for_registration_deg"])
    pair_rows, ident_summary = identifiability_audit(frames)
    manifest_rows = representative_manifest(frames)
    canonical_rows, metric_rows, maps_by_frame, counter_rows = build_maps_and_manifests(frames, axis_rows, manifest_rows)
    summary_visuals = render_summary_visuals(canonical_rows, metric_rows, frames)
    diff_rows = diff_audit(metric_rows, maps_by_frame, frames)
    perturb_rows = perturbation_audit(manifest_rows, frames, axis_rows, maps_by_frame)
    failure_rows = build_failure_ledger(range_rows, axis_rows, ident_summary, counter_rows)
    gate_rows = gate_status_rows(range_rows, axis_rows, ident_summary, canonical_rows, metric_rows, perturb_rows, counter_rows)

    write_csv(OUTPUTS["range_correction"], range_rows, RANGE_FIELDS)
    write_csv(OUTPUTS["identifiability_pairs"], pair_rows, IDENT_PAIR_FIELDS)
    write_csv(OUTPUTS["identifiability_summary"], ident_summary, IDENT_SUMMARY_FIELDS)
    write_csv(OUTPUTS["axis_continuity"], axis_rows, AXIS_FIELDS)
    write_csv(OUTPUTS["representative_manifest"], manifest_rows, REPRESENTATIVE_FIELDS)
    write_csv(OUTPUTS["canonical_manifest"], canonical_rows, CANONICAL_FIELDS)
    write_csv(OUTPUTS["boundary_metrics"], metric_rows, BOUNDARY_FIELDS)
    write_csv(OUTPUTS["diff_audit"], diff_rows, DIFF_FIELDS)
    write_csv(OUTPUTS["registration_perturbation"], perturb_rows, PERTURB_FIELDS)
    write_csv(OUTPUTS["counterfactual_casebook"], counter_rows, COUNTER_FIELDS)
    write_csv(OUTPUTS["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(OUTPUTS["gate_status"], gate_rows, GATE_FIELDS)
    write_text(OUTPUTS["visual_casebook"], visual_casebook(manifest_rows, canonical_rows, metric_rows, diff_rows, counter_rows, summary_visuals))
    write_text(
        OUTPUTS["report"],
        report_text(
            frames,
            range_rows,
            ident_summary,
            axis_rows,
            manifest_rows,
            canonical_rows,
            metric_rows,
            diff_rows,
            perturb_rows,
            counter_rows,
            failure_rows,
            gate_rows,
            summary_visuals,
        ),
    )
    print(f"E0_R3 body-canonical audit complete: frames={len(frames)} selected={len(manifest_rows)} report={rel(OUTPUTS['report'])}")


RANGE_FIELDS = [
    "sar_frame",
    "cx",
    "cy",
    "fan_center_x",
    "fan_center_y",
    "range_px_corrected",
    "range_m_corrected",
    "within_40m_domain",
    "legacy_absolute_range_m_grid",
    "legacy_within_40m_domain",
    "failure_reason",
]
IDENT_PAIR_FIELDS = [
    "frame_a",
    "frame_b",
    "pair_type",
    "time_delta_frames",
    "aspect_delta_deg",
    "corrected_range_delta_m",
    "axis_pair_reliable",
    "registration_pair_reliable",
    "frame_a_axis_reliability",
    "frame_b_axis_reliability",
    "used_for_identifiability",
]
IDENT_SUMMARY_FIELDS = ["audit_item", "value", "status", "evidence"]
AXIS_FIELDS = [
    "sar_frame",
    "pair_id",
    "axis_unsigned_deg",
    "axis_signed_for_registration_deg",
    "axis_sign_flip_applied",
    "axis_continuity_residual_deg",
    "axis_reliability",
    "registration_axis_status",
    "notes",
]
REPRESENTATIVE_FIELDS = [
    "sar_frame",
    "window_id",
    "selection_reason",
    "same_vehicle_thread",
    "axis_reliability",
    "registration_reliability",
    "relative_aspect_angle_deg",
    "range_m_corrected",
    "expected_review_role",
]
CANONICAL_FIELDS = [
    "map_id",
    "subject_name",
    "sar_frame",
    "window_id",
    "body_canonical_intensity_map",
    "body_canonical_normalized_map",
    "body_canonical_overlay",
    "body_canonical_valid_mask",
    "body_support_mask",
    "background_reference_mask",
    "body_canonical_transform",
    "inverse_transform",
    "interpolation_mode",
    "border_fill_value",
    "radar_direction_in_body_frame",
    "relative_aspect_angle_deg",
    "range_m_corrected",
    "registration_reliability",
    "canonical_core_grid",
    "canonical_canvas_grid",
    "body_length_m",
    "body_width_m",
    "axis_signed_for_registration_deg",
    "local_background_median",
    "local_background_mad",
    "valid_support_fraction",
    "mask_area_change_flag",
    "near_peak_location",
    "near_side_boundary_energy_fraction",
    "far_side_boundary_energy_fraction",
    "edge_or_interpolation_warning",
]
BOUNDARY_FIELDS = [
    "sar_frame",
    "window_id",
    "E_t_s_bins",
    "s_peak_t",
    "secondary_peak",
    "peak_count",
    "peak_width",
    "peak_prominence",
    "near_side_boundary_energy_fraction",
    "far_side_boundary_energy_fraction",
    "peak_inside_valid_mask",
    "near_peak_location",
]
DIFF_FIELDS = [
    "frame_a",
    "frame_b",
    "delta_png",
    "gain_near_boundary_fraction",
    "loss_near_boundary_fraction",
    "gain_peak_xy",
    "loss_peak_xy",
    "gain_loss_peak_distance_px",
    "s_peak_delta",
    "mask_common_fraction",
    "manual_review_hint",
]
PERTURB_FIELDS = [
    "sar_frame",
    "perturbation_id",
    "center_dx_px",
    "center_dy_px",
    "axis_delta_deg",
    "length_scale",
    "width_scale",
    "mean_abs_canonical_diff",
    "diagnostic_png",
    "manual_judgement",
]
COUNTER_FIELDS = [
    "counterfactual_id",
    "sar_frame",
    "counterfactual_role",
    "axis_family",
    "direction_sign",
    "offset_distance",
    "gt_overlap_risk",
    "counterfactual_status",
    "near_side_boundary_energy_fraction",
    "far_side_boundary_energy_fraction",
    "near_peak_location",
    "diagnostic_png",
    "interpretation",
]
FAILURE_FIELDS = ["failure_id", "severity", "evidence", "interpretation"]
GATE_FIELDS = ["gate_id", "status", "evidence", "failure_reason", "next_step_allowed"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    main()
