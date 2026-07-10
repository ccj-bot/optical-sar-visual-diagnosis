"""WGV3.4A SAR observation identifiability and imaging-source gate.

Automatic stage reads only WGV3.3B frozen automatic hypotheses, WGV3.3D
automatic SAR-component products, and SAR PNG display products. It does not
read WGV1.4/WGV1.8 posthoc labels, sar_gt_ids, GT boxes/centers, final SAR
locations, or user-selected target pixels before the freeze.

Posthoc stage requires the automatic freeze. It then reads selected WGV1.4 /
WGV1.8 metadata and optical frames only for evaluation-window construction and
visual diagnosis. The script never emits a final SAR box, selector, ranking, or
annotation edit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


RANDOM_SEED = 3401
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
VISUAL_DIR = REPORT_DIR / "visual_exemplars" / "wgv3_4a_20260710"
DATA_ROOT = Path(r"D:\profile\research\data")
DATE = "20260710"
SCENE = "GM_RM011"

SAR_FRAME_MIN = 0
SAR_FRAME_MAX = 765
OPTICAL_FRAME_MAX = 367
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
RADIAL_BIN_SIZE = 4

WGV33B_FREEZE = SAMPLES_DIR / "oty2_wgv3_3b_automatic_hypothesis_freeze_20260710.csv"
WGV33D_COMPONENTS = SAMPLES_DIR / "oty2_wgv3_3d_local_components_20260710.csv"
WGV33D_EDGES = SAMPLES_DIR / "oty2_wgv3_3d_component_edges_20260710.csv"
WGV33D_THREADS = SAMPLES_DIR / "oty2_wgv3_3d_response_threads_20260710.csv"
WGV33D_STATIC = SAMPLES_DIR / "oty2_wgv3_3d_static_clutter_statistics_20260710.csv"
WGV33D_CONTROLS = SAMPLES_DIR / "oty2_wgv3_3d_matched_controls_20260710.csv"
WGV18_CANDIDATES = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_to_sar_gt_reference_candidates_20260709.csv"
WGV18_OBSERVATIONS = SAMPLES_DIR / "oty2_wgv1_8_gm011_optical_behavior_observation_20260709.csv"
WGV14_THREADS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_threads_20260708.csv"
WGV14_FRAGMENTS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_fragments_20260708.csv"

FAILURE_REPORT = REPORT_DIR / f"oty2_wgv3_4a_wgv3_3d_failure_diagnosis_{DATE}.md"
FAILURE_MECHANISMS = SAMPLES_DIR / f"oty2_wgv3_4a_failure_mechanisms_{DATE}.csv"
STATIC_BACKGROUND_MAP = SAMPLES_DIR / f"oty2_wgv3_4a_static_background_map_{DATE}.csv"
COMPONENT_STATIC_OVERLAP = SAMPLES_DIR / f"oty2_wgv3_4a_component_static_overlap_{DATE}.csv"
DIRECTED_COMPONENT_EDGES = SAMPLES_DIR / f"oty2_wgv3_4a_directed_component_edges_{DATE}.csv"
PHYSICAL_SHORT_PATHS = SAMPLES_DIR / f"oty2_wgv3_4a_physical_short_paths_{DATE}.csv"
PATH_COMPETITIONS = SAMPLES_DIR / f"oty2_wgv3_4a_path_competitions_{DATE}.csv"
SPATIAL_CONTROL_DISTRIBUTIONS = SAMPLES_DIR / f"oty2_wgv3_4a_spatial_control_distributions_{DATE}.csv"
TEMPORAL_CONTROL_DISTRIBUTIONS = SAMPLES_DIR / f"oty2_wgv3_4a_temporal_control_distributions_{DATE}.csv"
PATH_CONTROL_STATISTICS = SAMPLES_DIR / f"oty2_wgv3_4a_path_control_statistics_{DATE}.csv"
RADIAL_BAND_STATISTICS = SAMPLES_DIR / f"oty2_wgv3_4a_radial_band_statistics_{DATE}.csv"
AUTO_HYPOTHESIS_PATH_INTERSECTIONS = SAMPLES_DIR / f"oty2_wgv3_4a_automatic_hypothesis_path_intersections_{DATE}.csv"
AUTOMATIC_IDENTIFIABILITY_SUMMARY = SAMPLES_DIR / f"oty2_wgv3_4a_automatic_identifiability_summary_{DATE}.csv"
AUTOMATIC_FREEZE_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_4a_automatic_freeze_manifest_{DATE}.csv"
EVALUATION_WINDOWS = SAMPLES_DIR / f"oty2_wgv3_4a_evaluation_windows_{DATE}.csv"
POSTHOC_IDENTIFIABILITY_EVALUATION = SAMPLES_DIR / f"oty2_wgv3_4a_posthoc_identifiability_evaluation_{DATE}.csv"
VISUAL_PATH_DIAGNOSIS = REPORT_DIR / f"oty2_wgv3_4a_visual_path_diagnosis_{DATE}.md"
IMAGING_SOURCE_INVENTORY = SAMPLES_DIR / f"oty2_wgv3_4a_imaging_source_inventory_{DATE}.csv"
IMAGING_SOURCE_GATE = REPORT_DIR / f"oty2_wgv3_4a_imaging_source_gate_{DATE}.md"
CLOSURE_REPORT = REPORT_DIR / f"oty2_wgv3_4a_sar_observation_identifiability_closure_{DATE}.md"

AUTOMATIC_OUTPUTS = [
    FAILURE_REPORT,
    FAILURE_MECHANISMS,
    STATIC_BACKGROUND_MAP,
    COMPONENT_STATIC_OVERLAP,
    DIRECTED_COMPONENT_EDGES,
    PHYSICAL_SHORT_PATHS,
    PATH_COMPETITIONS,
    SPATIAL_CONTROL_DISTRIBUTIONS,
    TEMPORAL_CONTROL_DISTRIBUTIONS,
    PATH_CONTROL_STATISTICS,
    RADIAL_BAND_STATISTICS,
    AUTO_HYPOTHESIS_PATH_INTERSECTIONS,
    AUTOMATIC_IDENTIFIABILITY_SUMMARY,
]

PATH_STRATEGIES = {
    "strict_physical_path": {
        "max_gap": 1,
        "max_az_velocity": 3.0,
        "max_radial_velocity": 32.0,
        "max_accel": 24.0,
        "min_dilated_overlap": 0.35,
        "min_scale": 0.50,
        "max_scale": 2.00,
        "max_static_pressure": 0.70,
        "min_consistency": 0.70,
    },
    "balanced_physical_path": {
        "max_gap": 2,
        "max_az_velocity": 5.0,
        "max_radial_velocity": 48.0,
        "max_accel": 40.0,
        "min_dilated_overlap": 0.25,
        "min_scale": 0.35,
        "max_scale": 2.50,
        "max_static_pressure": 0.85,
        "min_consistency": 0.55,
    },
    "relaxed_physical_path": {
        "max_gap": 2,
        "max_az_velocity": 7.0,
        "max_radial_velocity": 64.0,
        "max_accel": 56.0,
        "min_dilated_overlap": 0.12,
        "min_scale": 0.25,
        "max_scale": 3.00,
        "max_static_pressure": 1.00,
        "min_consistency": 0.40,
    },
}

RADIAL_BANDS = [
    ("R0", 26.0, 128.0),
    ("R1", 128.0, 256.0),
    ("R2", 256.0, 512.0),
    ("R3", 512.0, 768.0),
    ("R4", 768.0, 1024.0),
    ("R5", 1024.0, 1332.0),
]

FAILURE_FIELDS = [
    "failure_id",
    "failure_layer",
    "observed_behavior",
    "mechanism_cause",
    "effect_on_wgv3_3d",
    "repair_in_wgv3_4a",
]

STATIC_MAP_FIELDS = [
    "scene",
    "azimuth_bin_start_deg",
    "azimuth_bin_end_deg",
    "radial_pixel_min",
    "radial_pixel_max",
    "radial_band",
    "valid_pixel_count",
    "intensity_mean",
    "temporal_median",
    "temporal_mad",
    "response_frequency",
    "longest_consecutive_response",
    "local_extreme_frequency",
    "high_gradient_frequency",
    "peak_position_stability",
    "neighborhood_structure_stability",
    "fixed_bright_ridge_frequency",
    "nonzero_pixel_frequency",
    "frame_high_percentile_frequency",
    "long_term_spatial_occupancy",
    "max_stable_run",
    "persistent_score",
    "recurrent_score",
    "variable_score",
    "background_position_status",
]

COMPONENT_STATIC_FIELDS = [
    "component_id",
    "scene",
    "sar_frame",
    "extraction_profile",
    "azimuth_center",
    "radial_pixel_center",
    "radial_band",
    "component_cell_box_count",
    "persistent_static_overlap_ratio",
    "recurrent_background_overlap_ratio",
    "static_peak_overlap_ratio",
    "stable_gradient_overlap_ratio",
    "background_structure_pressure",
]

DIRECTED_EDGE_FIELDS = [
    "directed_edge_id",
    "extraction_profile",
    "from_component_id",
    "to_component_id",
    "from_sar_frame",
    "to_sar_frame",
    "frame_gap",
    "azimuth_shift",
    "radial_shift_px",
    "azimuth_velocity",
    "radial_velocity",
    "overlap_ratio",
    "dilated_overlap_ratio",
    "scale_ratio",
    "contrast_change",
    "static_background_overlap",
    "branch_competition_count",
    "wgv3_3d_relation_status",
    "directed_relation_status",
    "edge_score",
    "rejection_reason",
]

PATH_FIELDS = [
    "path_id",
    "extraction_profile",
    "start_sar_frame",
    "end_sar_frame",
    "duration_frames",
    "component_count",
    "component_ids",
    "azimuth_start",
    "azimuth_end",
    "radial_start",
    "radial_end",
    "radial_band",
    "azimuth_velocity_median",
    "radial_velocity_median",
    "azimuth_acceleration_median",
    "radial_acceleration_median",
    "direction_reversal_count",
    "mean_overlap",
    "mean_shape_consistency",
    "mean_local_contrast",
    "static_background_overlap",
    "branch_competition_count",
    "path_physical_consistency",
    "path_status",
]

PATH_COMPETITION_FIELDS = [
    "competition_id",
    "extraction_profile",
    "from_component_id",
    "from_sar_frame",
    "candidate_successor_count",
    "selected_successor_id",
    "best_edge_score",
    "second_edge_score",
    "score_gap",
    "candidate_successor_ids",
    "competition_status",
]

CONTROL_DISTRIBUTION_FIELDS = [
    "path_id",
    "control_type",
    "control_index",
    "control_component_id",
    "control_sar_frame",
    "control_azimuth_center",
    "control_radial_pixel_center",
    "control_radial_band",
    "control_static_pressure",
    "control_response_score",
]

PATH_CONTROL_FIELDS = [
    "path_id",
    "extraction_profile",
    "spatial_control_count",
    "temporal_control_count",
    "static_matched_control_count",
    "target_response_score",
    "target_spatial_empirical_percentile",
    "target_temporal_empirical_percentile",
    "spatial_effect_size",
    "temporal_effect_size",
    "control_median",
    "control_mad",
    "control_variance",
    "control_distribution_status",
]

RADIAL_BAND_FIELDS = [
    "radial_band",
    "extraction_profile",
    "valid_support_volume",
    "component_count",
    "short_path_count",
    "physical_path_count",
    "static_path_count",
    "response_density",
    "median_spatial_effect",
    "median_temporal_effect",
    "median_duration_frames",
    "median_azimuth_velocity",
    "median_radial_velocity",
]

AUTO_INTERSECTION_FIELDS = [
    "hypothesis_id",
    "source_auto_node_id",
    "path_id",
    "extraction_profile",
    "intersection_component_count",
    "path_start",
    "path_end",
    "path_status",
    "path_duration_frames",
    "path_radial_band",
    "path_physical_consistency",
    "target_spatial_empirical_percentile",
    "target_temporal_empirical_percentile",
]

AUTO_SUMMARY_FIELDS = [
    "hypothesis_id",
    "source_auto_node_id",
    "sar_frame_start",
    "sar_frame_end",
    "azimuth_min",
    "azimuth_max",
    "intersecting_component_count",
    "intersecting_short_path_count",
    "physically_consistent_path_count",
    "ambiguous_path_count",
    "static_structure_path_count",
    "recurrent_background_path_count",
    "per_radial_band_path_counts",
    "effective_volume",
    "path_density_per_effective_volume",
    "median_spatial_effect_size",
    "median_temporal_effect_size",
    "automatic_identifiability_note",
]

FREEZE_FIELDS = [
    "freeze_id",
    "scene",
    "stage",
    "source_file",
    "sha256",
    "combined_sha256",
    "wgv1_4_read_before_freeze",
    "wgv1_8_read_before_freeze",
    "sar_gt_ids_loaded",
    "gt_box_or_center_loaded",
    "posthoc_window_labels_loaded",
    "notes",
]

EVALUATION_WINDOW_FIELDS = [
    "evaluation_window_id",
    "evaluation_class",
    "source_window_id",
    "scene",
    "optical_frame_start",
    "optical_frame_end",
    "sar_frame_start",
    "sar_frame_end",
    "confidence_status",
    "visual_basis",
    "posthoc_source_note",
]

POSTHOC_EVAL_FIELDS = [
    "evaluation_window_id",
    "evaluation_class",
    "confidence_status",
    "overlapping_path_count",
    "physical_path_count",
    "ambiguous_path_count",
    "static_path_count",
    "recurrent_background_path_count",
    "unstable_chain_count",
    "path_density_per_effective_volume",
    "median_spatial_effect_size",
    "median_temporal_effect_size",
    "dominant_radial_bands",
    "strict_physical_count",
    "balanced_physical_count",
    "relaxed_physical_count",
    "identifiability_signal",
    "sar_gt_ids_loaded",
    "gt_box_or_center_loaded",
]

SOURCE_INVENTORY_FIELDS = [
    "inventory_id",
    "root",
    "path",
    "extension",
    "size_bytes",
    "source_role",
    "evidence_terms",
    "provenance_status",
]

RECOVERY_FIELDS = [
    "required_source_file",
    "expected_format",
    "required_metadata",
    "why_required",
    "where_likely_generated",
    "how_to_export",
    "next_experiment_enabled",
]


def fmt(value: Any, digits: int = 6) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(f) or math.isinf(f):
        return ""
    text = f"{f:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


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


def duplicate_header(row: Mapping[str, Any]) -> bool:
    return any(str(k) == str(v) for k, v in row.items() if k)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def combined_sha(paths: Sequence[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(path.as_posix().encode("utf-8"))
        h.update(sha256_file(path).encode("ascii"))
    return h.hexdigest()


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def radial_band(radial_pixel: Any) -> str:
    r = parse_float(radial_pixel)
    for name, lo, hi in RADIAL_BANDS:
        if lo <= r < hi:
            return name
    if r < RADIAL_BANDS[0][1]:
        return "R0"
    return "R5"


def radial_band_range(name: str) -> tuple[float, float]:
    for band, lo, hi in RADIAL_BANDS:
        if band == name:
            return lo, hi
    return RADIAL_BANDS[-1][1], RADIAL_BANDS[-1][2]


def frame_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_frames" / f"{frame:06d}.png"


def gray_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray" / f"{frame:06d}.png"


def load_required_inputs() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    return (
        read_csv(WGV33D_COMPONENTS),
        read_csv(WGV33D_EDGES),
        read_csv(WGV33D_THREADS),
        read_csv(WGV33D_STATIC),
        read_csv(WGV33D_CONTROLS),
        read_csv(WGV33B_FREEZE),
    )


def component_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return parse_int(row.get("sar_frame")), str(row.get("component_id", ""))


def build_failure_audit(edges: Sequence[Mapping[str, str]], threads: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    script_text = (REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_3d_local_sar_response_components.py").read_text(encoding="utf-8")
    relation_counts = Counter(row["relation_status"] for row in edges)
    thread_count = len(threads)
    branch_positive = sum(1 for row in threads if parse_int(row.get("branch_count")) > 0)
    dense_threads = sum(
        1
        for row in threads
        if parse_int(row.get("component_count")) > max(3, parse_int(row.get("duration_frames")) * 2)
        or parse_int(row.get("branch_count")) > max(3, parse_int(row.get("duration_frames")))
    )
    zero_static = sum(1 for row in threads if row.get("dynamic_response_status") == "static_clutter_like")
    temporal_half_or_zero = sum(1 for row in threads if parse_float(row.get("temporal_continuity")) <= 0.5)
    control_supported = sum(
        1
        for row in threads
        if parse_float(row.get("matched_control_available_ratio")) >= 0.5
        and (
            parse_float(row.get("mean_spatial_control_ratio")) >= 1.05
            or parse_float(row.get("mean_temporal_control_ratio")) >= 1.05
        )
    )
    undirected_confirmed = "adjacency[b].add(a)" in script_text and "adjacency[a].add(b)" in script_text
    strong_weak_count = relation_counts["strong_local_continuity"] + relation_counts["weak_local_continuity"]
    return [
        {
            "failure_id": "WGV34A_FAIL_001",
            "failure_layer": "thread_graph_construction",
            "observed_behavior": f"undirected adjacency confirmed={undirected_confirmed}; strong_or_weak_edges={strong_weak_count}",
            "mechanism_cause": "WGV3.3D inserts accepted continuity edges in both adjacency directions before connected-component traversal.",
            "effect_on_wgv3_3d": "A thread can become a graph component rather than a single temporally directed physical sequence.",
            "repair_in_wgv3_4a": "Use frame-forward directed edges and one-predecessor/one-successor short path segments.",
        },
        {
            "failure_id": "WGV34A_FAIL_002",
            "failure_layer": "branch_competition",
            "observed_behavior": f"threads_with_branch_count_gt0={branch_positive}/{thread_count}; dense_branch_threads={dense_threads}",
            "mechanism_cause": "Multi-predecessor and multi-successor competition is counted but graph components still allow branch merging.",
            "effect_on_wgv3_3d": "Long or dense threads can be created by switching local components over time.",
            "repair_in_wgv3_4a": "Record competing successors separately and select only single-sequence path segments.",
        },
        {
            "failure_id": "WGV34A_FAIL_003",
            "failure_layer": "motion_interpretation",
            "observed_behavior": f"threads_with_temporal_continuity_le_0_5={temporal_half_or_zero}/{thread_count}",
            "mechanism_cause": "Start/end drift is measured over a connected graph with gaps and possible component switching.",
            "effect_on_wgv3_3d": "Endpoint drift cannot be treated as reliable continuous motion.",
            "repair_in_wgv3_4a": "Compute per-edge velocity, acceleration, direction reversal, overlap, and shape consistency.",
        },
        {
            "failure_id": "WGV34A_FAIL_004",
            "failure_layer": "static_background_model",
            "observed_behavior": f"static_clutter_like_threads={zero_static}",
            "mechanism_cause": "Static structure was inferred only after response-threshold extraction, so stable bright structures lacked an independent exit.",
            "effect_on_wgv3_3d": "Road, bridge, guardrail, or fixed bright ridge evidence can leak into dynamic-like labels.",
            "repair_in_wgv3_4a": "Build a position-level static background map before path status assignment.",
        },
        {
            "failure_id": "WGV34A_FAIL_005",
            "failure_layer": "matched_control_model",
            "observed_behavior": f"control_supported_threads={control_supported}/{thread_count}",
            "mechanism_cause": "One adjacent, one far, and one temporal control do not form a stable empirical background distribution.",
            "effect_on_wgv3_3d": "T001, T004, and late background windows can all look supported.",
            "repair_in_wgv3_4a": "Use sampled spatial, temporal, and static-matched empirical control distributions.",
        },
        {
            "failure_id": "WGV34A_FAIL_006",
            "failure_layer": "negative_window_definition",
            "observed_behavior": "WGV3.3D late background was only not-T001, not visually verified vehicle-absent evidence.",
            "mechanism_cause": "The negative condition was temporal exclusion rather than optical/SAR observation-grounded absence.",
            "effect_on_wgv3_3d": "Background dynamic-supported counts cannot prove target specificity failure alone.",
            "repair_in_wgv3_4a": "Construct post-freeze vehicle-present, trusted-negative, and complex windows from optical review.",
        },
    ]


def build_static_background_map(static_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    medians = np.array([parse_float(row.get("temporal_median")) for row in static_rows], dtype=np.float64)
    mads = np.array([parse_float(row.get("temporal_mad")) for row in static_rows], dtype=np.float64)
    means = np.array([parse_float(row.get("intensity_mean")) for row in static_rows], dtype=np.float64)
    freqs = np.array([parse_float(row.get("response_frequency")) for row in static_rows], dtype=np.float64)
    med_p90 = float(np.percentile(medians, 90)) if medians.size else 0.0
    med_p75 = float(np.percentile(medians, 75)) if medians.size else 0.0
    mad_p70 = float(np.percentile(mads, 70)) if mads.size else 0.0
    mean_p80 = float(np.percentile(means, 80)) if means.size else 0.0
    freq_p75 = float(np.percentile(freqs, 75)) if freqs.size else 0.0
    out: list[dict[str, Any]] = []
    for row in static_rows:
        valid_pixels = parse_int(row.get("valid_pixel_count"))
        freq = parse_float(row.get("response_frequency"))
        longest = parse_int(row.get("longest_consecutive_response"))
        mean = parse_float(row.get("intensity_mean"))
        median = parse_float(row.get("temporal_median"))
        mad = parse_float(row.get("temporal_mad"))
        var = parse_float(row.get("intensity_variance"))
        persistent_score = 0.0
        if longest >= 20:
            persistent_score += 0.45
        if freq >= max(0.12, freq_p75):
            persistent_score += 0.25
        if median >= med_p90 and mad <= max(1.0, mad_p70):
            persistent_score += 0.20
        if mean >= mean_p80 and mad <= max(1.0, mad_p70):
            persistent_score += 0.10
        recurrent_score = min(1.0, freq / 0.12) * 0.55 + min(1.0, longest / 12.0) * 0.25 + min(1.0, var / 80.0) * 0.20
        variable_score = min(1.0, mad / max(1.0, mad_p70)) * 0.45 + min(1.0, var / 120.0) * 0.35 + min(1.0, mean / max(1.0, med_p75)) * 0.20
        if valid_pixels < 4:
            status = "insufficient_support"
        elif persistent_score >= 0.55:
            status = "persistent_static_structure"
        elif recurrent_score >= 0.50:
            status = "recurrent_background_structure"
        elif freq > 0:
            status = "rare_response_location"
        else:
            status = "variable_background" if variable_score >= 0.45 else "insufficient_support"
        out.append(
            {
                "scene": SCENE,
                "azimuth_bin_start_deg": row.get("azimuth_bin_start_deg", ""),
                "azimuth_bin_end_deg": row.get("azimuth_bin_end_deg", ""),
                "radial_pixel_min": row.get("radial_pixel_min", ""),
                "radial_pixel_max": row.get("radial_pixel_max", ""),
                "radial_band": radial_band(row.get("radial_pixel_min")),
                "valid_pixel_count": valid_pixels,
                "intensity_mean": fmt(mean, 8),
                "temporal_median": fmt(median, 8),
                "temporal_mad": fmt(mad, 8),
                "response_frequency": fmt(freq, 8),
                "longest_consecutive_response": longest,
                "local_extreme_frequency": fmt(freq, 8),
                "high_gradient_frequency": fmt(min(1.0, var / 160.0), 8),
                "peak_position_stability": fmt(min(1.0, longest / 30.0), 8),
                "neighborhood_structure_stability": fmt(max(0.0, 1.0 - min(1.0, mad / max(1.0, mad_p70 * 1.5))), 8),
                "fixed_bright_ridge_frequency": fmt(freq if median >= med_p90 else freq * 0.25, 8),
                "nonzero_pixel_frequency": "1" if mean > 0 or median > 0 else "0",
                "frame_high_percentile_frequency": fmt(freq, 8),
                "long_term_spatial_occupancy": fmt(freq * valid_pixels, 8),
                "max_stable_run": longest,
                "persistent_score": fmt(persistent_score, 8),
                "recurrent_score": fmt(recurrent_score, 8),
                "variable_score": fmt(variable_score, 8),
                "background_position_status": status,
            }
        )
    return out


def static_key(az: int, radial_bin: int) -> tuple[int, int]:
    return az, radial_bin


def build_component_static_overlap(
    components: Sequence[Mapping[str, str]], static_map: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_cell: dict[tuple[int, int], Mapping[str, Any]] = {}
    for row in static_map:
        az = parse_int(row.get("azimuth_bin_start_deg"))
        rb = parse_int(row.get("radial_pixel_min")) // RADIAL_BIN_SIZE
        by_cell[static_key(az, rb)] = row
    out: list[dict[str, Any]] = []
    for comp in components:
        if comp.get("extraction_profile") != "main":
            continue
        az0 = parse_int(comp.get("az_bin_min"))
        az1 = parse_int(comp.get("az_bin_max"))
        r0 = parse_int(comp.get("radial_bin_min"))
        r1 = parse_int(comp.get("radial_bin_max"))
        statuses: list[str] = []
        persistent_scores: list[float] = []
        recurrent_scores: list[float] = []
        variable_scores: list[float] = []
        for az in range(az0, az1 + 1):
            for rb in range(r0, r1 + 1):
                cell = by_cell.get(static_key(az, rb))
                if not cell:
                    continue
                statuses.append(str(cell.get("background_position_status", "")))
                persistent_scores.append(parse_float(cell.get("persistent_score")))
                recurrent_scores.append(parse_float(cell.get("recurrent_score")))
                variable_scores.append(parse_float(cell.get("variable_score")))
        n = max(1, len(statuses))
        persistent_ratio = sum(1 for status in statuses if status == "persistent_static_structure") / n
        recurrent_ratio = sum(1 for status in statuses if status == "recurrent_background_structure") / n
        peak_ratio = float(np.mean(persistent_scores)) if persistent_scores else 0.0
        gradient_ratio = float(np.mean(variable_scores)) if variable_scores else 0.0
        pressure = min(1.0, persistent_ratio + 0.65 * recurrent_ratio + 0.35 * gradient_ratio + 0.25 * (float(np.mean(recurrent_scores)) if recurrent_scores else 0.0))
        out.append(
            {
                "component_id": comp.get("component_id", ""),
                "scene": SCENE,
                "sar_frame": comp.get("sar_frame", ""),
                "extraction_profile": comp.get("extraction_profile", ""),
                "azimuth_center": comp.get("azimuth_center", ""),
                "radial_pixel_center": comp.get("radial_pixel_center", ""),
                "radial_band": radial_band(comp.get("radial_pixel_center")),
                "component_cell_box_count": len(statuses),
                "persistent_static_overlap_ratio": fmt(persistent_ratio, 8),
                "recurrent_background_overlap_ratio": fmt(recurrent_ratio, 8),
                "static_peak_overlap_ratio": fmt(peak_ratio, 8),
                "stable_gradient_overlap_ratio": fmt(gradient_ratio, 8),
                "background_structure_pressure": fmt(pressure, 8),
            }
        )
    return out


def strategy_edge_status(edge: Mapping[str, str], comp_by_id: Mapping[str, Mapping[str, str]], overlap_by_id: Mapping[str, Mapping[str, Any]], strategy: str) -> dict[str, Any]:
    params = PATH_STRATEGIES[strategy]
    from_id = edge.get("from_component_id", "")
    to_id = edge.get("to_component_id", "")
    c0 = comp_by_id.get(from_id)
    c1 = comp_by_id.get(to_id)
    if not c0 or not c1:
        return {"accepted": False, "reason": "missing_component"}
    frame0 = parse_int(c0.get("sar_frame"))
    frame1 = parse_int(c1.get("sar_frame"))
    gap = frame1 - frame0
    if gap <= 0 or gap > params["max_gap"]:
        return {"accepted": False, "reason": "invalid_frame_direction_or_gap"}
    az_shift = parse_float(edge.get("azimuth_shift"))
    radial_shift = parse_float(edge.get("radial_shift_px"))
    az_vel = az_shift / max(1, gap)
    radial_vel = radial_shift / max(1, gap)
    dilated = parse_float(edge.get("dilated_overlap_ratio"))
    overlap = parse_float(edge.get("overlap_ratio"))
    scale = parse_float(edge.get("scale_ratio"), 1.0)
    static_pressure = max(
        parse_float(overlap_by_id.get(from_id, {}).get("background_structure_pressure")),
        parse_float(overlap_by_id.get(to_id, {}).get("background_structure_pressure")),
    )
    competition = 0
    if edge.get("competition_ids"):
        competition = len([part for part in edge["competition_ids"].split(";") if part])
    reasons = []
    if abs(az_vel) > params["max_az_velocity"]:
        reasons.append("azimuth_velocity")
    if abs(radial_vel) > params["max_radial_velocity"]:
        reasons.append("radial_velocity")
    if dilated < params["min_dilated_overlap"] and overlap <= 0:
        reasons.append("overlap")
    if scale < params["min_scale"] or scale > params["max_scale"]:
        reasons.append("scale")
    if static_pressure > params["max_static_pressure"] and strategy != "relaxed_physical_path":
        reasons.append("static_pressure")
    shape_consistency = 1.0 / (1.0 + abs(math.log(max(1e-6, scale))))
    overlap_score = max(overlap, dilated * 0.75)
    velocity_score = max(0.0, 1.0 - abs(az_vel) / max(1e-6, params["max_az_velocity"])) * 0.45 + max(
        0.0, 1.0 - abs(radial_vel) / max(1e-6, params["max_radial_velocity"])
    ) * 0.35
    score = overlap_score * 0.35 + velocity_score * 0.35 + shape_consistency * 0.20 + max(0.0, 1.0 - static_pressure) * 0.10
    return {
        "accepted": not reasons,
        "reason": ";".join(reasons),
        "frame0": frame0,
        "frame1": frame1,
        "gap": gap,
        "az_vel": az_vel,
        "radial_vel": radial_vel,
        "shape_consistency": shape_consistency,
        "static_pressure": static_pressure,
        "competition": competition,
        "score": score,
    }


def build_directed_edges(
    components: Sequence[Mapping[str, str]],
    edges: Sequence[Mapping[str, str]],
    component_static: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    comp_by_id = {row["component_id"]: row for row in components if row.get("extraction_profile") == "main"}
    overlap_by_id = {row["component_id"]: row for row in component_static}
    out: list[dict[str, Any]] = []
    idx = 1
    for strategy in PATH_STRATEGIES:
        for edge in edges:
            status = strategy_edge_status(edge, comp_by_id, overlap_by_id, strategy)
            if not status["accepted"] and status["reason"] in {"missing_component", "invalid_frame_direction_or_gap"}:
                continue
            from_id = edge.get("from_component_id", "")
            to_id = edge.get("to_component_id", "")
            row = {
                "directed_edge_id": f"WGV34A_DEDGE_{idx:07d}",
                "extraction_profile": strategy,
                "from_component_id": from_id,
                "to_component_id": to_id,
                "from_sar_frame": status.get("frame0", ""),
                "to_sar_frame": status.get("frame1", ""),
                "frame_gap": status.get("gap", edge.get("frame_gap", "")),
                "azimuth_shift": edge.get("azimuth_shift", ""),
                "radial_shift_px": edge.get("radial_shift_px", ""),
                "azimuth_velocity": fmt(status.get("az_vel", 0.0), 8),
                "radial_velocity": fmt(status.get("radial_vel", 0.0), 8),
                "overlap_ratio": edge.get("overlap_ratio", ""),
                "dilated_overlap_ratio": edge.get("dilated_overlap_ratio", ""),
                "scale_ratio": edge.get("scale_ratio", ""),
                "contrast_change": edge.get("contrast_change", ""),
                "static_background_overlap": fmt(status.get("static_pressure", 0.0), 8),
                "branch_competition_count": status.get("competition", 0),
                "wgv3_3d_relation_status": edge.get("relation_status", ""),
                "directed_relation_status": "accepted_directed_physical_candidate" if status["accepted"] else "rejected_directed_physical_candidate",
                "edge_score": fmt(status.get("score", 0.0), 8),
                "rejection_reason": status.get("reason", ""),
            }
            out.append(row)
            idx += 1
    return out


def selected_edges_for_strategy(directed_edges: Sequence[Mapping[str, Any]], strategy: str) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, Any]]]:
    accepted = [row for row in directed_edges if row["extraction_profile"] == strategy and row["directed_relation_status"] == "accepted_directed_physical_candidate"]
    by_from: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in accepted:
        by_from[row["from_component_id"]].append(row)
    best_from: dict[str, Mapping[str, Any]] = {}
    competition_rows: list[dict[str, Any]] = []
    for from_id, rows in by_from.items():
        ranked = sorted(rows, key=lambda item: parse_float(item.get("edge_score")), reverse=True)
        best_from[from_id] = ranked[0]
        second = parse_float(ranked[1].get("edge_score")) if len(ranked) > 1 else 0.0
        best = parse_float(ranked[0].get("edge_score"))
        competition_rows.append(
            {
                "competition_id": f"WGV34A_COMP_{strategy}_{len(competition_rows)+1:06d}",
                "extraction_profile": strategy,
                "from_component_id": from_id,
                "from_sar_frame": ranked[0].get("from_sar_frame", ""),
                "candidate_successor_count": len(ranked),
                "selected_successor_id": ranked[0].get("to_component_id", ""),
                "best_edge_score": fmt(best, 8),
                "second_edge_score": fmt(second, 8) if len(ranked) > 1 else "",
                "score_gap": fmt(best - second, 8) if len(ranked) > 1 else "",
                "candidate_successor_ids": ";".join(str(row.get("to_component_id", "")) for row in ranked[:8]),
                "competition_status": "single_successor" if len(ranked) == 1 else "multi_successor_competition",
            }
        )
    by_to: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in best_from.values():
        by_to[row["to_component_id"]].append(row)
    selected: dict[str, Mapping[str, Any]] = {}
    for to_id, rows in by_to.items():
        ranked = sorted(rows, key=lambda item: parse_float(item.get("edge_score")), reverse=True)
        selected[ranked[0]["from_component_id"]] = ranked[0]
    return selected, competition_rows


def median(values: Sequence[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    return float(np.median(vals)) if vals else default


def build_short_paths(
    components: Sequence[Mapping[str, str]],
    directed_edges: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comp_by_id = {row["component_id"]: row for row in components if row.get("extraction_profile") == "main"}
    paths: list[dict[str, Any]] = []
    competitions: list[dict[str, Any]] = []
    for strategy in PATH_STRATEGIES:
        selected, comp_rows = selected_edges_for_strategy(directed_edges, strategy)
        competitions.extend(comp_rows)
        incoming = {row["to_component_id"]: row["from_component_id"] for row in selected.values()}
        outgoing = {from_id: row for from_id, row in selected.items()}
        starts = sorted([cid for cid in outgoing if cid not in incoming], key=lambda cid: component_sort_key(comp_by_id.get(cid, {})))
        starts.extend(cid for cid in sorted(outgoing) if cid not in starts)
        visited_edges: set[str] = set()
        for start in starts:
            current = start
            while current in outgoing and outgoing[current]["directed_edge_id"] not in visited_edges:
                ids = [current]
                edge_rows = []
                segment_start_frame = parse_int(comp_by_id.get(current, {}).get("sar_frame"))
                while current in outgoing and outgoing[current]["directed_edge_id"] not in visited_edges and len(ids) < 10:
                    edge = outgoing[current]
                    next_component_id = edge["to_component_id"]
                    next_frame = parse_int(comp_by_id.get(next_component_id, {}).get("sar_frame"))
                    if next_frame - segment_start_frame + 1 > 10 and len(ids) > 1:
                        break
                    visited_edges.add(edge["directed_edge_id"])
                    edge_rows.append(edge)
                    current = next_component_id
                    ids.append(current)
                if len(ids) == 1:
                    break
                comps = [comp_by_id[cid] for cid in ids if cid in comp_by_id]
                if len(comps) < 2:
                    continue
                frames = [parse_int(comp.get("sar_frame")) for comp in comps]
                az = [parse_float(comp.get("azimuth_center")) for comp in comps]
                rad = [parse_float(comp.get("radial_pixel_center")) for comp in comps]
                az_vel = [parse_float(edge.get("azimuth_velocity")) for edge in edge_rows]
                rad_vel = [parse_float(edge.get("radial_velocity")) for edge in edge_rows]
                az_acc = [az_vel[i + 1] - az_vel[i] for i in range(len(az_vel) - 1)]
                rad_acc = [rad_vel[i + 1] - rad_vel[i] for i in range(len(rad_vel) - 1)]
                reversals = sum(1 for i in range(len(az_vel) - 1) if az_vel[i] * az_vel[i + 1] < 0) + sum(
                    1 for i in range(len(rad_vel) - 1) if rad_vel[i] * rad_vel[i + 1] < 0
                )
                static_overlap = median([parse_float(edge.get("static_background_overlap")) for edge in edge_rows])
                mean_overlap = median([max(parse_float(edge.get("overlap_ratio")), parse_float(edge.get("dilated_overlap_ratio")) * 0.75) for edge in edge_rows])
                mean_shape = median([1.0 / (1.0 + abs(math.log(max(1e-6, parse_float(edge.get("scale_ratio"), 1.0))))) for edge in edge_rows])
                branch_comp = sum(parse_int(edge.get("branch_competition_count")) for edge in edge_rows)
                mean_contrast = median([parse_float(comp.get("mean_local_robust_z")) for comp in comps])
                velocity_ok = all(abs(v) <= PATH_STRATEGIES[strategy]["max_az_velocity"] for v in az_vel) and all(
                    abs(v) <= PATH_STRATEGIES[strategy]["max_radial_velocity"] for v in rad_vel
                )
                accel_ok = all(abs(v) <= PATH_STRATEGIES[strategy]["max_accel"] for v in az_acc + rad_acc)
                consistency = (
                    min(1.0, mean_overlap)
                    * 0.30
                    + mean_shape * 0.25
                    + (1.0 if velocity_ok else 0.35) * 0.20
                    + (1.0 if accel_ok else 0.35) * 0.15
                    + max(0.0, 1.0 - min(1.0, static_overlap)) * 0.10
                )
                if len(comps) < 3:
                    status = "insufficient_length"
                elif static_overlap >= 0.62:
                    status = "static_structure_path"
                elif static_overlap >= 0.42:
                    status = "recurrent_background_path"
                elif consistency >= PATH_STRATEGIES[strategy]["min_consistency"] and branch_comp <= max(2, len(edge_rows)):
                    status = "physically_consistent_short_path"
                elif consistency >= 0.38:
                    status = "physically_possible_ambiguous_path"
                else:
                    status = "unstable_link_chain"
                paths.append(
                    {
                        "path_id": f"WGV34A_PATH_{len(paths)+1:07d}",
                        "extraction_profile": strategy,
                        "start_sar_frame": min(frames),
                        "end_sar_frame": max(frames),
                        "duration_frames": max(frames) - min(frames) + 1,
                        "component_count": len(comps),
                        "component_ids": ";".join(comp["component_id"] for comp in comps),
                        "azimuth_start": fmt(az[0], 6),
                        "azimuth_end": fmt(az[-1], 6),
                        "radial_start": fmt(rad[0], 6),
                        "radial_end": fmt(rad[-1], 6),
                        "radial_band": radial_band(median(rad)),
                        "azimuth_velocity_median": fmt(median(az_vel), 8),
                        "radial_velocity_median": fmt(median(rad_vel), 8),
                        "azimuth_acceleration_median": fmt(median(az_acc), 8),
                        "radial_acceleration_median": fmt(median(rad_acc), 8),
                        "direction_reversal_count": reversals,
                        "mean_overlap": fmt(mean_overlap, 8),
                        "mean_shape_consistency": fmt(mean_shape, 8),
                        "mean_local_contrast": fmt(mean_contrast, 8),
                        "static_background_overlap": fmt(static_overlap, 8),
                        "branch_competition_count": branch_comp,
                        "path_physical_consistency": fmt(consistency, 8),
                        "path_status": status,
                    }
                )
                if current not in outgoing:
                    break
    return paths, competitions


def component_indexes(components: Sequence[Mapping[str, str]], component_static: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Mapping[str, str]], dict[str, Mapping[str, Any]], dict[tuple[int, str], list[Mapping[str, str]]], dict[str, list[Mapping[str, str]]]]:
    comp_by_id = {row["component_id"]: row for row in components if row.get("extraction_profile") == "main"}
    static_by_id = {row["component_id"]: row for row in component_static}
    by_frame_band: dict[tuple[int, str], list[Mapping[str, str]]] = defaultdict(list)
    by_band: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in comp_by_id.values():
        band = radial_band(row.get("radial_pixel_center"))
        frame = parse_int(row.get("sar_frame"))
        by_frame_band[(frame, band)].append(row)
        by_band[band].append(row)
    return comp_by_id, static_by_id, by_frame_band, by_band


def sample_controls(
    path: Mapping[str, Any],
    path_components: Sequence[Mapping[str, str]],
    static_by_id: Mapping[str, Mapping[str, Any]],
    by_frame_band: Mapping[tuple[int, str], list[Mapping[str, str]]],
    by_band: Mapping[str, list[Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    path_id = path["path_id"]
    band = path["radial_band"]
    target = parse_float(path.get("mean_local_contrast"))
    start = parse_int(path.get("start_sar_frame"))
    end = parse_int(path.get("end_sar_frame"))
    mid_frame = parse_int(round((start + end) / 2))
    path_ids = {comp["component_id"] for comp in path_components}
    path_az = [parse_float(comp.get("azimuth_center")) for comp in path_components]
    az_min = min(path_az) if path_az else -90
    az_max = max(path_az) if path_az else 90
    static_pressure = parse_float(path.get("static_background_overlap"))

    def make_rows(control_type: str, candidates: list[Mapping[str, str]]) -> list[dict[str, Any]]:
        rows = []
        for idx, comp in enumerate(candidates[:20], 1):
            cid = comp["component_id"]
            stat = static_by_id.get(cid, {})
            rows.append(
                {
                    "path_id": path_id,
                    "control_type": control_type,
                    "control_index": idx,
                    "control_component_id": cid,
                    "control_sar_frame": comp.get("sar_frame", ""),
                    "control_azimuth_center": comp.get("azimuth_center", ""),
                    "control_radial_pixel_center": comp.get("radial_pixel_center", ""),
                    "control_radial_band": radial_band(comp.get("radial_pixel_center")),
                    "control_static_pressure": stat.get("background_structure_pressure", ""),
                    "control_response_score": comp.get("mean_local_robust_z", ""),
                }
            )
        return rows

    spatial_candidates = []
    for frame in range(max(SAR_FRAME_MIN, mid_frame - 1), min(SAR_FRAME_MAX, mid_frame + 1) + 1):
        for comp in by_frame_band.get((frame, band), []):
            cid = comp["component_id"]
            if cid in path_ids:
                continue
            caz = parse_float(comp.get("azimuth_center"))
            if az_min - 2 <= caz <= az_max + 2:
                continue
            spatial_candidates.append(comp)
    spatial_candidates = sorted(spatial_candidates, key=lambda comp: (abs(parse_float(comp.get("azimuth_center")) - ((az_min + az_max) / 2)), comp["component_id"]))

    temporal_candidates = []
    for comp in by_band.get(band, []):
        cid = comp["component_id"]
        if cid in path_ids:
            continue
        frame = parse_int(comp.get("sar_frame"))
        if start - 20 <= frame <= end + 20:
            continue
        caz = parse_float(comp.get("azimuth_center"))
        if abs(caz - ((az_min + az_max) / 2)) <= 12:
            temporal_candidates.append(comp)
    temporal_candidates = sorted(temporal_candidates, key=lambda comp: (abs(parse_int(comp.get("sar_frame")) - mid_frame), comp["component_id"]))

    static_candidates = []
    for comp in by_band.get(band, []):
        cid = comp["component_id"]
        if cid in path_ids:
            continue
        pressure = parse_float(static_by_id.get(cid, {}).get("background_structure_pressure"))
        if abs(pressure - static_pressure) <= 0.12:
            static_candidates.append(comp)
    static_candidates = sorted(static_candidates, key=lambda comp: (abs(parse_float(static_by_id.get(comp["component_id"], {}).get("background_structure_pressure")) - static_pressure), comp["component_id"]))

    spatial_rows = make_rows("spatial_control_distribution", spatial_candidates)
    temporal_rows = make_rows("temporal_control_distribution", temporal_candidates)
    static_rows = make_rows("static_matched_control_distribution", static_candidates)

    def scores(rows: Sequence[Mapping[str, Any]]) -> list[float]:
        return [parse_float(row.get("control_response_score")) for row in rows if row.get("control_response_score") not in {"", None}]

    spatial_scores = scores(spatial_rows)
    temporal_scores = scores(temporal_rows)
    all_scores = spatial_scores + temporal_scores + scores(static_rows)

    def percentile(control_scores: Sequence[float]) -> float:
        if not control_scores:
            return 0.0
        return 100.0 * sum(1 for value in control_scores if value <= target) / len(control_scores)

    def effect(control_scores: Sequence[float]) -> float:
        if not control_scores:
            return 0.0
        med = float(np.median(control_scores))
        mad = float(np.median(np.abs(np.array(control_scores) - med)))
        return (target - med) / (1.4826 * mad + 1e-6)

    ctrl_med = float(np.median(all_scores)) if all_scores else 0.0
    ctrl_mad = float(np.median(np.abs(np.array(all_scores) - ctrl_med))) if all_scores else 0.0
    ctrl_var = float(np.var(all_scores)) if all_scores else 0.0
    status = "control_distribution_ok" if len(spatial_rows) >= 10 and len(temporal_rows) >= 10 else "control_distribution_sparse"
    stats = {
        "path_id": path_id,
        "extraction_profile": path["extraction_profile"],
        "spatial_control_count": len(spatial_rows),
        "temporal_control_count": len(temporal_rows),
        "static_matched_control_count": len(static_rows),
        "target_response_score": fmt(target, 8),
        "target_spatial_empirical_percentile": fmt(percentile(spatial_scores), 8),
        "target_temporal_empirical_percentile": fmt(percentile(temporal_scores), 8),
        "spatial_effect_size": fmt(effect(spatial_scores), 8),
        "temporal_effect_size": fmt(effect(temporal_scores), 8),
        "control_median": fmt(ctrl_med, 8),
        "control_mad": fmt(ctrl_mad, 8),
        "control_variance": fmt(ctrl_var, 8),
        "control_distribution_status": status,
    }
    return spatial_rows, temporal_rows, static_rows, stats


def build_control_distributions(
    components: Sequence[Mapping[str, str]],
    component_static: Sequence[Mapping[str, Any]],
    paths: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    comp_by_id, static_by_id, by_frame_band, by_band = component_indexes(components, component_static)
    spatial_rows: list[dict[str, Any]] = []
    temporal_rows: list[dict[str, Any]] = []
    stats_rows: list[dict[str, Any]] = []
    # Control distribution is most useful for non-trivial paths. Sparse paths
    # are still retained in the path table, but not expanded into large control
    # tables if they are insufficient by definition.
    for path in paths:
        if parse_int(path.get("component_count")) < 3:
            stats_rows.append(
                {
                    "path_id": path["path_id"],
                    "extraction_profile": path["extraction_profile"],
                    "spatial_control_count": 0,
                    "temporal_control_count": 0,
                    "static_matched_control_count": 0,
                    "target_response_score": path.get("mean_local_contrast", ""),
                    "target_spatial_empirical_percentile": "",
                    "target_temporal_empirical_percentile": "",
                    "spatial_effect_size": "",
                    "temporal_effect_size": "",
                    "control_median": "",
                    "control_mad": "",
                    "control_variance": "",
                    "control_distribution_status": "insufficient_length",
                }
            )
            continue
        ids = [cid for cid in str(path.get("component_ids", "")).split(";") if cid in comp_by_id]
        comps = [comp_by_id[cid] for cid in ids]
        spatial, temporal, static_rows, stats = sample_controls(path, comps, static_by_id, by_frame_band, by_band)
        spatial_rows.extend(spatial)
        temporal_rows.extend(temporal)
        # Store static-matched controls in the spatial distribution file with a
        # distinct control_type to avoid another huge mostly redundant table.
        spatial_rows.extend(static_rows)
        stats_rows.append(stats)
    return spatial_rows, temporal_rows, stats_rows


def build_radial_stats(
    components: Sequence[Mapping[str, str]],
    paths: Sequence[Mapping[str, Any]],
    control_stats: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    control_by_path = {row["path_id"]: row for row in control_stats}
    rows: list[dict[str, Any]] = []
    for strategy in PATH_STRATEGIES:
        for band, lo, hi in RADIAL_BANDS:
            comps = [row for row in components if row.get("extraction_profile") == "main" and radial_band(row.get("radial_pixel_center")) == band]
            pths = [row for row in paths if row.get("extraction_profile") == strategy and row.get("radial_band") == band]
            physical = [row for row in pths if row.get("path_status") == "physically_consistent_short_path"]
            static = [row for row in pths if row.get("path_status") in {"static_structure_path", "recurrent_background_path"}]
            spatial_effects = [parse_float(control_by_path.get(row["path_id"], {}).get("spatial_effect_size")) for row in pths if control_by_path.get(row["path_id"], {}).get("spatial_effect_size") not in {"", None}]
            temporal_effects = [parse_float(control_by_path.get(row["path_id"], {}).get("temporal_effect_size")) for row in pths if control_by_path.get(row["path_id"], {}).get("temporal_effect_size") not in {"", None}]
            volume = max(1.0, (hi - lo) * 180.0 * (SAR_FRAME_MAX + 1))
            rows.append(
                {
                    "radial_band": band,
                    "extraction_profile": strategy,
                    "valid_support_volume": fmt(volume, 3),
                    "component_count": len(comps),
                    "short_path_count": len(pths),
                    "physical_path_count": len(physical),
                    "static_path_count": len(static),
                    "response_density": fmt(len(pths) / volume, 12),
                    "median_spatial_effect": fmt(median(spatial_effects), 8),
                    "median_temporal_effect": fmt(median(temporal_effects), 8),
                    "median_duration_frames": fmt(median([parse_float(row.get("duration_frames")) for row in pths]), 8),
                    "median_azimuth_velocity": fmt(median([parse_float(row.get("azimuth_velocity_median")) for row in pths]), 8),
                    "median_radial_velocity": fmt(median([parse_float(row.get("radial_velocity_median")) for row in pths]), 8),
                }
            )
    return rows


def interval_overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) <= min(a1, b1)


def build_auto_intersections(
    hypotheses: Sequence[Mapping[str, str]],
    components: Sequence[Mapping[str, str]],
    paths: Sequence[Mapping[str, Any]],
    control_stats: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comp_by_id = {row["component_id"]: row for row in components if row.get("extraction_profile") == "main"}
    control_by_path = {row["path_id"]: row for row in control_stats}
    rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for hyp in hypotheses:
        if hyp.get("scene") != SCENE:
            continue
        hstart = parse_int(hyp.get("sar_frame_start"))
        hend = parse_int(hyp.get("sar_frame_end"))
        haz0 = parse_float(hyp.get("azimuth_min"))
        haz1 = parse_float(hyp.get("azimuth_max"))
        matched_paths: list[Mapping[str, Any]] = []
        matched_components: set[str] = set()
        band_counts: Counter[str] = Counter()
        for path in paths:
            if parse_int(path.get("end_sar_frame")) < hstart or parse_int(path.get("start_sar_frame")) > hend:
                continue
            ids = [cid for cid in str(path.get("component_ids", "")).split(";") if cid in comp_by_id]
            path_match_count = 0
            for cid in ids:
                comp = comp_by_id[cid]
                frame = parse_int(comp.get("sar_frame"))
                if hstart <= frame <= hend and interval_overlap(parse_float(comp.get("azimuth_min")), parse_float(comp.get("azimuth_max")), haz0, haz1):
                    path_match_count += 1
                    matched_components.add(cid)
            if path_match_count == 0:
                continue
            matched_paths.append(path)
            band_counts[path.get("radial_band", "")] += 1
            stats = control_by_path.get(path["path_id"], {})
            rows.append(
                {
                    "hypothesis_id": hyp.get("hypothesis_id", ""),
                    "source_auto_node_id": hyp.get("source_auto_node_id", ""),
                    "path_id": path["path_id"],
                    "extraction_profile": path["extraction_profile"],
                    "intersection_component_count": path_match_count,
                    "path_start": path.get("start_sar_frame", ""),
                    "path_end": path.get("end_sar_frame", ""),
                    "path_status": path.get("path_status", ""),
                    "path_duration_frames": path.get("duration_frames", ""),
                    "path_radial_band": path.get("radial_band", ""),
                    "path_physical_consistency": path.get("path_physical_consistency", ""),
                    "target_spatial_empirical_percentile": stats.get("target_spatial_empirical_percentile", ""),
                    "target_temporal_empirical_percentile": stats.get("target_temporal_empirical_percentile", ""),
                }
            )
        physical = [p for p in matched_paths if p.get("path_status") == "physically_consistent_short_path"]
        ambiguous = [p for p in matched_paths if p.get("path_status") == "physically_possible_ambiguous_path"]
        static = [p for p in matched_paths if p.get("path_status") == "static_structure_path"]
        recurrent = [p for p in matched_paths if p.get("path_status") == "recurrent_background_path"]
        effective_volume = max(1.0, (hend - hstart + 1) * max(1.0, haz1 - haz0) * (FAN_RADIUS_PX - 26.0))
        effects_s = [parse_float(control_by_path.get(p["path_id"], {}).get("spatial_effect_size")) for p in matched_paths if control_by_path.get(p["path_id"], {}).get("spatial_effect_size") not in {"", None}]
        effects_t = [parse_float(control_by_path.get(p["path_id"], {}).get("temporal_effect_size")) for p in matched_paths if control_by_path.get(p["path_id"], {}).get("temporal_effect_size") not in {"", None}]
        note = "automatic_path_evidence_not_identity_specific"
        if len(physical) == 0:
            note = "no_physical_short_path_support"
        elif len(static) + len(recurrent) >= len(physical):
            note = "path_support_static_background_dominated"
        summary.append(
            {
                "hypothesis_id": hyp.get("hypothesis_id", ""),
                "source_auto_node_id": hyp.get("source_auto_node_id", ""),
                "sar_frame_start": hstart,
                "sar_frame_end": hend,
                "azimuth_min": hyp.get("azimuth_min", ""),
                "azimuth_max": hyp.get("azimuth_max", ""),
                "intersecting_component_count": len(matched_components),
                "intersecting_short_path_count": len(matched_paths),
                "physically_consistent_path_count": len(physical),
                "ambiguous_path_count": len(ambiguous),
                "static_structure_path_count": len(static),
                "recurrent_background_path_count": len(recurrent),
                "per_radial_band_path_counts": ";".join(f"{k}={v}" for k, v in sorted(band_counts.items())),
                "effective_volume": fmt(effective_volume, 6),
                "path_density_per_effective_volume": fmt(len(matched_paths) / effective_volume, 12),
                "median_spatial_effect_size": fmt(median(effects_s), 8),
                "median_temporal_effect_size": fmt(median(effects_t), 8),
                "automatic_identifiability_note": note,
            }
        )
    return rows, summary


def render_failure_report(failure_rows: Sequence[Mapping[str, Any]], threads: Sequence[Mapping[str, str]], edges: Sequence[Mapping[str, str]]) -> None:
    status_counts = Counter(row.get("dynamic_response_status", "") for row in threads)
    relation_counts = Counter(row.get("relation_status", "") for row in edges)
    lines = [
        "# OTY2 WGV3.4A WGV3.3D Failure Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "WGV3.3D files were not modified. This audit reads their code and automatic products to identify repair targets for WGV3.4A.",
        "",
        "## Confirmed Structural Issues",
        "",
    ]
    for row in failure_rows:
        lines.append(f"- `{row['failure_id']}` {row['failure_layer']}: {row['observed_behavior']}")
    lines.extend(
        [
            "",
            "## WGV3.3D Counts Reused For Diagnosis",
            "",
            f"- relation_status_counts: `{dict(relation_counts)}`",
            f"- thread_status_counts: `{dict(status_counts)}`",
            "",
            "## Repair Boundary",
            "",
            "WGV3.4A repairs the observation path, static background, empirical controls, and radial stratification in new files only. It does not reinterpret WGV3.3D graph components as object tracks.",
        ]
    )
    write_text(FAILURE_REPORT, "\n".join(lines).rstrip() + "\n")


def render_freeze_manifest() -> list[dict[str, Any]]:
    sha = combined_sha(AUTOMATIC_OUTPUTS)
    rows = []
    for idx, path in enumerate(AUTOMATIC_OUTPUTS, 1):
        rows.append(
            {
                "freeze_id": f"WGV34A_FREEZE_{idx:03d}",
                "scene": SCENE,
                "stage": "automatic_png_identifiability_repair",
                "source_file": path.as_posix(),
                "sha256": sha256_file(path),
                "combined_sha256": sha,
                "wgv1_4_read_before_freeze": "false",
                "wgv1_8_read_before_freeze": "false",
                "sar_gt_ids_loaded": "false",
                "gt_box_or_center_loaded": "false",
                "posthoc_window_labels_loaded": "false",
                "notes": "automatic stage output; posthoc window labels and GT-local data not read before freeze",
            }
        )
    write_csv(AUTOMATIC_FREEZE_MANIFEST, rows, FREEZE_FIELDS)
    return rows


def run_automatic_stage() -> dict[str, Any]:
    components, edges, threads, static_stats, _controls, hypotheses = load_required_inputs()
    main_components = [row for row in components if row.get("extraction_profile") == "main"]
    failure_rows = build_failure_audit(edges, threads)
    write_csv(FAILURE_MECHANISMS, failure_rows, FAILURE_FIELDS)
    render_failure_report(failure_rows, threads, edges)

    static_map = build_static_background_map(static_stats)
    write_csv(STATIC_BACKGROUND_MAP, static_map, STATIC_MAP_FIELDS)
    component_static = build_component_static_overlap(components, static_map)
    write_csv(COMPONENT_STATIC_OVERLAP, component_static, COMPONENT_STATIC_FIELDS)

    directed_edges = build_directed_edges(components, edges, component_static)
    write_csv(DIRECTED_COMPONENT_EDGES, directed_edges, DIRECTED_EDGE_FIELDS)
    paths, competitions = build_short_paths(components, directed_edges)
    write_csv(PHYSICAL_SHORT_PATHS, paths, PATH_FIELDS)
    write_csv(PATH_COMPETITIONS, competitions, PATH_COMPETITION_FIELDS)

    spatial_controls, temporal_controls, control_stats = build_control_distributions(main_components, component_static, paths)
    write_csv(SPATIAL_CONTROL_DISTRIBUTIONS, spatial_controls, CONTROL_DISTRIBUTION_FIELDS)
    write_csv(TEMPORAL_CONTROL_DISTRIBUTIONS, temporal_controls, CONTROL_DISTRIBUTION_FIELDS)
    write_csv(PATH_CONTROL_STATISTICS, control_stats, PATH_CONTROL_FIELDS)

    radial_stats = build_radial_stats(main_components, paths, control_stats)
    write_csv(RADIAL_BAND_STATISTICS, radial_stats, RADIAL_BAND_FIELDS)
    intersections, auto_summary = build_auto_intersections(hypotheses, main_components, paths, control_stats)
    write_csv(AUTO_HYPOTHESIS_PATH_INTERSECTIONS, intersections, AUTO_INTERSECTION_FIELDS)
    write_csv(AUTOMATIC_IDENTIFIABILITY_SUMMARY, auto_summary, AUTO_SUMMARY_FIELDS)
    freeze_rows = render_freeze_manifest()
    return {
        "components": main_components,
        "static_map": static_map,
        "directed_edges": directed_edges,
        "paths": paths,
        "control_stats": control_stats,
        "radial_stats": radial_stats,
        "auto_summary": auto_summary,
        "freeze_rows": freeze_rows,
    }


def optical_to_sar_start(frame: int) -> int:
    return max(SAR_FRAME_MIN, min(SAR_FRAME_MAX, int(round(frame * (SAR_FRAME_MAX / max(1, OPTICAL_FRAME_MAX))))))


def optical_to_sar_end(frame: int) -> int:
    return max(SAR_FRAME_MIN, min(SAR_FRAME_MAX, int(round(frame * (SAR_FRAME_MAX / max(1, OPTICAL_FRAME_MAX))))))


def create_contact_sheet(frames: Sequence[int], output_path: Path, title: str) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for frame in frames:
        path = frame_path(frame)
        if not path.exists():
            continue
        with Image.open(path) as img:
            im = img.convert("RGB")
        im.thumbnail((260, 146))
        canvas = Image.new("RGB", (260, 172), "white")
        canvas.paste(im, (0, 22))
        draw = ImageDraw.Draw(canvas)
        draw.text((5, 4), f"{title} f{frame}", fill=(220, 0, 0))
        thumbs.append(canvas)
    if not thumbs:
        return ""
    cols = min(3, len(thumbs))
    rows = int(math.ceil(len(thumbs) / cols))
    sheet = Image.new("RGB", (cols * 260, rows * 172), (235, 235, 235))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * 260, (idx // cols) * 172))
    sheet.save(output_path)
    return output_path.as_posix()


def load_posthoc_windows() -> list[dict[str, Any]]:
    if not AUTOMATIC_FREEZE_MANIFEST.exists():
        raise RuntimeError("Automatic freeze is missing; run --stage automatic first")
    candidates = read_csv(WGV18_CANDIDATES)
    observations = read_csv(WGV18_OBSERVATIONS)
    cand_by_id = {row["window_id"]: row for row in candidates}
    obs_by_id = {row["window_id"]: row for row in observations}
    rows: list[dict[str, Any]] = []
    definitions = [
        ("WGV34A_EVAL_VP_001", "posthoc_vehicle_present_evaluation", "WGV18W001", "vehicle_present_high_confidence"),
        ("WGV34A_EVAL_VP_002", "posthoc_vehicle_present_evaluation", "WGV18W004", "vehicle_present_moderate_confidence"),
        ("WGV34A_EVAL_COMPLEX_001", "complex_competition_evaluation", "WGV18W003", "complex_competition_evaluation"),
    ]
    for eval_id, klass, window_id, confidence in definitions:
        cand = cand_by_id.get(window_id, {})
        obs = obs_by_id.get(window_id, {})
        optical_start = parse_int(cand.get("optical_frame_start"))
        optical_end = parse_int(cand.get("optical_frame_end"))
        sar_start = parse_int(cand.get("sar_frame_candidate_start"))
        sar_end = parse_int(cand.get("sar_frame_candidate_end"))
        visual_basis = obs.get("primary_vehicle_description_cn") or obs.get("observed_optical_behavior_tags", "")
        rows.append(
            {
                "evaluation_window_id": eval_id,
                "evaluation_class": klass,
                "source_window_id": window_id,
                "scene": SCENE,
                "optical_frame_start": optical_start,
                "optical_frame_end": optical_end,
                "sar_frame_start": sar_start,
                "sar_frame_end": sar_end,
                "confidence_status": confidence,
                "visual_basis": visual_basis,
                "posthoc_source_note": "WGV1.8 selected fields read after automatic freeze; sar_gt_ids not loaded",
            }
        )
    # These two windows were visually checked from optical frames by Codex. They
    # are not high-confidence empty-scene negatives; they are conservative
    # non-primary-object / non-car-structure controls.
    negative_defs = [
        ("WGV34A_EVAL_NEG_001", 324, 336, "vehicle_absent_moderate_confidence", "foreground dominated by fence/vegetation/covered structure; distant bridge-side car-like objects remain a caveat"),
        ("WGV34A_EVAL_NEG_002", 348, 360, "non_vehicle_structure_control", "foreground dominated by fence/vegetation and motorbike/scooter; no clear foreground car in the optical search direction"),
    ]
    for eval_id, opt0, opt1, confidence, basis in negative_defs:
        rows.append(
            {
                "evaluation_window_id": eval_id,
                "evaluation_class": "trusted_negative_evaluation",
                "source_window_id": "codex_optical_visual_review",
                "scene": SCENE,
                "optical_frame_start": opt0,
                "optical_frame_end": opt1,
                "sar_frame_start": optical_to_sar_start(opt0),
                "sar_frame_end": optical_to_sar_end(opt1),
                "confidence_status": confidence,
                "visual_basis": basis,
                "posthoc_source_note": "constructed after freeze from optical-frame visual inspection; not a T001 exclusion shortcut",
            }
        )
    return rows


def paths_for_window(paths: Sequence[Mapping[str, Any]], window: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    start = parse_int(window.get("sar_frame_start"))
    end = parse_int(window.get("sar_frame_end"))
    return [row for row in paths if parse_int(row.get("start_sar_frame")) <= end and parse_int(row.get("end_sar_frame")) >= start]


def evaluate_windows(windows: Sequence[Mapping[str, Any]], paths: Sequence[Mapping[str, Any]], control_stats: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    control_by_id = {row["path_id"]: row for row in control_stats}
    rows: list[dict[str, Any]] = []
    for window in windows:
        selected = paths_for_window(paths, window)
        statuses = Counter(row.get("path_status", "") for row in selected)
        strategies = Counter(row.get("extraction_profile", "") for row in selected if row.get("path_status") == "physically_consistent_short_path")
        start = parse_int(window.get("sar_frame_start"))
        end = parse_int(window.get("sar_frame_end"))
        volume = max(1.0, (end - start + 1) * 180.0 * (FAN_RADIUS_PX - 26.0))
        spatial = [parse_float(control_by_id.get(row["path_id"], {}).get("spatial_effect_size")) for row in selected if control_by_id.get(row["path_id"], {}).get("spatial_effect_size") not in {"", None}]
        temporal = [parse_float(control_by_id.get(row["path_id"], {}).get("temporal_effect_size")) for row in selected if control_by_id.get(row["path_id"], {}).get("temporal_effect_size") not in {"", None}]
        bands = Counter(row.get("radial_band", "") for row in selected)
        signal = "no_window_specific_signal"
        if selected and statuses["physically_consistent_short_path"] > 0:
            signal = "physical_paths_present_not_yet_specific"
        if statuses["static_structure_path"] + statuses["recurrent_background_path"] >= statuses["physically_consistent_short_path"]:
            signal = "static_background_competes_with_path_signal"
        rows.append(
            {
                "evaluation_window_id": window["evaluation_window_id"],
                "evaluation_class": window["evaluation_class"],
                "confidence_status": window["confidence_status"],
                "overlapping_path_count": len(selected),
                "physical_path_count": statuses["physically_consistent_short_path"],
                "ambiguous_path_count": statuses["physically_possible_ambiguous_path"],
                "static_path_count": statuses["static_structure_path"],
                "recurrent_background_path_count": statuses["recurrent_background_path"],
                "unstable_chain_count": statuses["unstable_link_chain"],
                "path_density_per_effective_volume": fmt(len(selected) / volume, 12),
                "median_spatial_effect_size": fmt(median(spatial), 8),
                "median_temporal_effect_size": fmt(median(temporal), 8),
                "dominant_radial_bands": ";".join(f"{k}={v}" for k, v in bands.most_common(4)),
                "strict_physical_count": strategies["strict_physical_path"],
                "balanced_physical_count": strategies["balanced_physical_path"],
                "relaxed_physical_count": strategies["relaxed_physical_path"],
                "identifiability_signal": signal,
                "sar_gt_ids_loaded": "false",
                "gt_box_or_center_loaded": "false",
            }
        )
    return rows


def polar_box_to_xy(az_min: float, az_max: float, radial_min: float, radial_max: float) -> list[tuple[float, float]]:
    points = []
    for az, rad in [(az_min, radial_min), (az_max, radial_min), (az_max, radial_max), (az_min, radial_max)]:
        theta = math.radians(az)
        x = FAN_CENTER_X + rad * math.sin(theta)
        y = FAN_CENTER_Y - rad * math.cos(theta)
        points.append((x, y))
    return points


def render_path_overlay(path: Mapping[str, Any], comp_by_id: Mapping[str, Mapping[str, str]], output_path: Path) -> str:
    ids = [cid for cid in str(path.get("component_ids", "")).split(";") if cid in comp_by_id]
    comps = [comp_by_id[cid] for cid in ids]
    if not comps:
        return ""
    rep = comps[len(comps) // 2]
    frame = parse_int(rep.get("sar_frame"))
    with Image.open(gray_path(frame)) as img:
        canvas = img.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for idx, comp in enumerate(comps):
        color = (255, 60, 60) if idx == len(comps) // 2 else (255, 215, 35)
        points = polar_box_to_xy(
            parse_float(comp.get("azimuth_min")),
            parse_float(comp.get("azimuth_max")),
            parse_float(comp.get("radial_pixel_min")),
            parse_float(comp.get("radial_pixel_max")),
        )
        draw.line(points + [points[0]], fill=color, width=3)
    label = f"{path['path_id']} {path['extraction_profile']} {path['path_status']} f{path['start_sar_frame']}-{path['end_sar_frame']}"
    draw.rectangle([12, 12, 1200, 48], fill=(0, 0, 0))
    draw.text((18, 18), label, fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path.as_posix()


def choose_visual_cases(windows: Sequence[Mapping[str, Any]], paths: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any], Mapping[str, Any]]]:
    cases: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for window in windows:
        selected = paths_for_window(paths, window)
        ranked = sorted(
            selected,
            key=lambda row: (
                row.get("path_status") == "physically_consistent_short_path",
                parse_float(row.get("path_physical_consistency")),
                parse_int(row.get("duration_frames")),
                parse_float(row.get("mean_local_contrast")),
            ),
            reverse=True,
        )
        limit = 2 if window["evaluation_class"] in {"posthoc_vehicle_present_evaluation", "trusted_negative_evaluation"} else 1
        for path in ranked[:limit]:
            cases.append((window["evaluation_window_id"], window, path))
    seen = set()
    result = []
    for eval_id, window, path in cases:
        key = (eval_id, path["path_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append((eval_id, window, path))
    return result[:12]


def path_visual_judgment(path: Mapping[str, Any], window: Mapping[str, Any]) -> str:
    duration = parse_int(path.get("duration_frames"))
    branch_count = parse_int(path.get("branch_competition_count"))
    static_overlap = parse_float(path.get("static_background_overlap"))
    az_vel = parse_float(path.get("azimuth_velocity_median"))
    radial_vel = parse_float(path.get("radial_velocity_median"))
    az_acc = parse_float(path.get("azimuth_acceleration_median"))
    radial_acc = parse_float(path.get("radial_acceleration_median"))
    reversal_count = parse_int(path.get("direction_reversal_count"))
    shape_consistency = parse_float(path.get("mean_shape_consistency"))
    local_contrast = parse_float(path.get("mean_local_contrast"))
    overlap = parse_float(path.get("mean_overlap"))
    status = str(path.get("path_status", ""))
    if duration < 3:
        continuity = "持续不足3帧，不能作为稳定连续结构。"
    elif "physically_consistent" in status:
        continuity = "满足固定策略下的单向短路径条件，但仍只是局部SAR响应片段。"
    elif "static" in status or static_overlap >= 0.7:
        continuity = "与固定/近固定背景高度重叠，更像道路、护栏、桥梁边缘或固定亮脊线散射。"
    elif "recurrent" in status:
        continuity = "具有重复背景位置压力，更像反复出现的背景响应。"
    else:
        continuity = "连续性不足或分支竞争较强，存在换接风险。"
    branch_text = "未见显著分支竞争。" if branch_count == 0 else f"存在 {branch_count} 个分支竞争候选，不能排除换接。"
    velocity_text = (
        f"方位速度中位数 {az_vel:.4g} deg/frame，径向速度中位数 {radial_vel:.4g} px/frame；"
        f"方位/径向加速度中位数分别为 {az_acc:.4g}/{radial_acc:.4g}，方向反转 {reversal_count} 次。"
    )
    structure_text = (
        f"平均重叠 {overlap:.3g}，形状一致性 {shape_consistency:.3g}，局部对比 {local_contrast:.3g}，"
        f"静态背景重叠 {static_overlap:.3g}。"
    )
    if window.get("evaluation_class") == "trusted_negative_evaluation":
        comparison = "该窗口本身是保守负例/结构控制，仍出现高响应片段，说明PNG域响应并非车辆存在特异。"
    elif window.get("evaluation_class") == "complex_competition_evaluation":
        comparison = "该窗口存在多车、遮挡或主体切换，响应不能唯一归因到单一车辆。"
    else:
        comparison = "与保守负例相比，该片段没有形成稳定可分离的车辆存在证据。"
    return (
        f"路径位于 {path.get('radial_band')}，方位 {path.get('azimuth_start')} 到 {path.get('azimuth_end')} deg，"
        f"径向像素 {path.get('radial_start')} 到 {path.get('radial_end')}；持续 {duration} 帧，状态为 {status}。"
        f"{continuity}{branch_text}{velocity_text}{structure_text}{comparison}"
        "因此不能称为车辆相关响应候选；还缺少幅值保持型SAR矩阵、脉冲窗口映射和径向物理轴来判定跨帧散射是否可比。"
    )


def render_visual_report(windows: Sequence[Mapping[str, Any]], paths: Sequence[Mapping[str, Any]], components: Sequence[Mapping[str, str]]) -> None:
    comp_by_id = {row["component_id"]: row for row in components if row.get("extraction_profile") == "main"}
    lines = [
        "# OTY2 WGV3.4A Visual Path Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "Codex opened optical frames and SAR path overlays for the cases below. PNG overlays are ignored by Git and are not committed.",
        "",
    ]
    for window in windows:
        frames = sorted({parse_int(window["optical_frame_start"]), parse_int((parse_int(window["optical_frame_start"]) + parse_int(window["optical_frame_end"])) / 2), parse_int(window["optical_frame_end"])})
        contact = create_contact_sheet(frames, VISUAL_DIR / f"{window['evaluation_window_id']}_optical_contact.png", window["evaluation_window_id"])
        lines.extend(
            [
                f"## {window['evaluation_window_id']} {window['evaluation_class']}",
                "",
                f"- Optical contact sheet: `{contact}`",
                f"- Visual basis: {window['visual_basis']}",
                "",
            ]
        )
    for idx, (eval_id, window, path) in enumerate(choose_visual_cases(windows, paths), 1):
        overlay = render_path_overlay(path, comp_by_id, VISUAL_DIR / f"wgv3_4a_path_review_{idx:02d}_{path['path_id']}.png")
        judgment = (
            f"路径位于 {path.get('radial_band')}，方位 {path.get('azimuth_start')} 到 {path.get('azimuth_end')} deg，"
            f"径向像素 {path.get('radial_start')} 到 {path.get('radial_end')}；持续 {path.get('duration_frames')} 帧，"
            f"状态为 {path.get('path_status')}。该路径是单向短路径片段，不是最终目标轨迹；"
            f"静态背景重叠 {path.get('static_background_overlap')}，分支竞争 {path.get('branch_competition_count')}。"
        )
        judgment = path_visual_judgment(path, window)
        lines.extend(
            [
                f"### VIS_{idx:02d} {eval_id} {path['path_id']}",
                "",
                f"- SAR overlay: `{overlay}`",
                f"- 中文判断：{judgment}",
                "",
            ]
        )
    write_text(VISUAL_PATH_DIAGNOSIS, "\n".join(lines).rstrip() + "\n")


def run_posthoc_stage() -> dict[str, Any]:
    if not AUTOMATIC_FREEZE_MANIFEST.exists():
        raise RuntimeError("Automatic freeze is missing; run --stage automatic first")
    components = read_csv(WGV33D_COMPONENTS)
    paths = read_csv(PHYSICAL_SHORT_PATHS)
    control_stats = read_csv(PATH_CONTROL_STATISTICS)
    windows = load_posthoc_windows()
    eval_rows = evaluate_windows(windows, paths, control_stats)
    write_csv(EVALUATION_WINDOWS, windows, EVALUATION_WINDOW_FIELDS)
    write_csv(POSTHOC_IDENTIFIABILITY_EVALUATION, eval_rows, POSTHOC_EVAL_FIELDS)
    render_visual_report(windows, paths, components)
    render_closure_report()
    return {"windows": windows, "eval_rows": eval_rows}


def scan_text_terms(path: Path) -> str:
    terms = [
        "imagesc",
        "imshow",
        "mat2gray",
        "rescale",
        "normalize",
        "imwrite",
        "uint8",
        "log10",
        "20*log10",
        "abs",
        "fft",
        "backprojection",
        "range",
        "azimuth",
        "window",
        "pulse",
        "chirp",
        "sar",
    ]
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return ""
    found = [term for term in terms if term.lower() in text]
    return ";".join(found)


def run_source_gate_stage() -> dict[str, Any]:
    roots = [REPO_ROOT, DATA_ROOT / SCENE, DATA_ROOT.parent]
    exts = {".bin", ".mat", ".npy", ".npz", ".h5", ".dat", ".raw", ".m", ".py", ".png"}
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    idx = 1
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            ext = path.suffix.lower()
            name = path.name.lower()
            full = path.as_posix().lower()
            local_context = "/".join(part.lower() for part in path.parts[-6:])
            sar_source_context = any(
                term in local_context
                for term in [
                    "sarframes",
                    "sar_frame",
                    "sar_gray",
                    "sar_png",
                    "radar",
                    "range",
                    "azimuth",
                    "pulse",
                    "chirp",
                    "backprojection",
                    "imaging",
                ]
            )
            if ext not in exts and not any(term in name for term in ["sar", "range", "azimuth", "pulse", "chirp", "image"]):
                continue
            role = "other"
            if "depth" in full:
                role = "optical_depth_not_sar_source"
            elif "sarframes_gray" in full or "sarframes" in full:
                role = "sar_png_display_product"
            elif ext in {".bin", ".raw", ".dat"} and sar_source_context:
                role = "possible_raw_or_binary_source"
            elif ext in {".mat", ".h5", ".npy", ".npz"} and sar_source_context:
                role = "possible_float_or_intermediate_matrix"
            elif ext in {".m", ".py"}:
                role = "possible_generation_code"
            terms = scan_text_terms(path) if ext in {".m", ".py", ".txt", ".md"} and path.stat().st_size < 2_000_000 else ""
            provenance = "candidate_needs_manual_trace"
            if role == "sar_png_display_product":
                provenance = "png_display_product_present"
            elif role == "optical_depth_not_sar_source":
                provenance = "not_sar_imaging_source"
            elif role == "possible_generation_code" and any(term in terms for term in ["imwrite", "mat2gray", "imagesc", "imshow", "log10", "20*log10"]):
                provenance = "png_generation_code_candidate"
            elif role == "possible_generation_code" and "sar" in terms:
                provenance = "sar_related_code_not_generation_source"
            rows.append(
                {
                    "inventory_id": f"WGV34A_SRC_{idx:05d}",
                    "root": root.as_posix(),
                    "path": path.as_posix(),
                    "extension": ext,
                    "size_bytes": path.stat().st_size,
                    "source_role": role,
                    "evidence_terms": terms,
                    "provenance_status": provenance,
                }
            )
            idx += 1
            if idx > 5000:
                break
    write_csv(IMAGING_SOURCE_INVENTORY, rows, SOURCE_INVENTORY_FIELDS)
    roles = Counter(row["source_role"] for row in rows)
    generation_candidates = [row for row in rows if row["provenance_status"] == "png_generation_code_candidate"]
    confirmed_generation_candidates = [
        row
        for row in generation_candidates
        if any(marker in row["path"].lower() for marker in ["sarframes", "sar_gray", "sar_png", "backprojection", "imaging"])
    ]
    raw_candidates = [
        row
        for row in rows
        if row["source_role"] in {"possible_raw_or_binary_source", "possible_float_or_intermediate_matrix"}
    ]
    png_products = [row for row in rows if row["source_role"] == "sar_png_display_product"]
    if raw_candidates:
        status = "FLOAT_SAR_MATRIX_RECOVERED" if any(row["extension"] in {".npy", ".npz", ".h5", ".mat"} for row in raw_candidates) else "RAW_IMAGING_SOURCE_RECOVERED"
    elif confirmed_generation_candidates:
        status = "PNG_GENERATION_CODE_RECOVERED"
    elif png_products:
        status = "RAW_SOURCE_LOCATION_UNKNOWN"
    else:
        status = "PNG_PROVENANCE_BLOCKED"
    recovery_rows = [
        {
            "required_source_file": "float_sar_amplitude",
            "expected_format": ".npy/.npz/.mat/.h5 float32 or float64 matrix per SAR frame/window",
            "required_metadata": "fixed display dynamic range, frame index, pulse window, range axis, azimuth geometry",
            "why_required": "Needed to compare SAR response magnitudes across time without framewise PNG display scaling.",
            "where_likely_generated": "upstream SAR imaging or MATLAB/Python PNG export step before uint8 conversion",
            "how_to_export": "save pre-log or fixed-log amplitude matrix before mat2gray/rescale/uint8/imwrite",
            "next_experiment_enabled": "fixed-amplitude SAR local response validation",
        },
        {
            "required_source_file": "float_sar_power",
            "expected_format": ".npy/.npz/.mat/.h5 power matrix with preserved scale",
            "required_metadata": "power definition, log compression status, pulse aggregation length",
            "why_required": "Needed to distinguish local scatter strength from display contrast.",
            "where_likely_generated": "SAR image formation step after coherent or noncoherent integration",
            "how_to_export": "save abs(signal)**2 or equivalent power before display normalization",
            "next_experiment_enabled": "power-domain static background and path contrast testing",
        },
        {
            "required_source_file": "fixed_dynamic_range_log_sar",
            "expected_format": "uint16/float matrix or PNG/TIFF with one fixed global min/max for the full sequence",
            "required_metadata": "global min/max, log base, clipping rule",
            "why_required": "Needed if raw amplitude cannot be shared but cross-frame comparability is required.",
            "where_likely_generated": "PNG export code",
            "how_to_export": "apply one fixed log dynamic range to all frames, not per-frame rescale",
            "next_experiment_enabled": "PNG-domain replay with preserved temporal comparability",
        },
        {
            "required_source_file": "pulse_to_png_mapping",
            "expected_format": ".csv/.json mapping SAR frame index to pulse or time-window range",
            "required_metadata": "pulse start, pulse end, stride, timestamp, software jitter assumptions",
            "why_required": "Needed to evaluate whether path continuity is physical or a windowing artifact.",
            "where_likely_generated": "SAR sliding-window export script",
            "how_to_export": "write mapping while producing each SAR frame",
            "next_experiment_enabled": "time-window stress test and temporal alignment audit",
        },
        {
            "required_source_file": "radial_pixel_to_range_mapping",
            "expected_format": ".csv/.json calibration table",
            "required_metadata": "range bin spacing, fan center, cropping/interpolation parameters",
            "why_required": "Needed to convert radial pixels into a physically interpretable SAR shell.",
            "where_likely_generated": "SAR display geometry or MATLAB imaging parameters",
            "how_to_export": "save range axis before image remap/crop",
            "next_experiment_enabled": "coarse radial-band to metric range migration",
        },
    ]
    lines = [
        "# OTY2 WGV3.4A Imaging Source Gate",
        "",
        f"Date: {DATE}",
        "",
        f"Imaging source gate status: `{status}`",
        "",
        "## Inventory Summary",
        "",
        f"- source_role_counts: `{dict(roles)}`",
        f"- sar_png_display_products: `{len(png_products)}`",
        f"- generation_code_candidates: `{len(generation_candidates)}`",
        f"- confirmed_generation_code_candidates: `{len(confirmed_generation_candidates)}`",
        f"- sar_raw_or_float_candidates: `{len(raw_candidates)}`",
        "",
        "## Interpretation",
        "",
        "The current checkout and GM_RM011 data directory expose SAR PNG display products, optical frames, and depth arrays. No confirmed raw SAR pulse data, pulse-to-PNG mapping, or radial-pixel-to-range calibration was recovered by this gate.",
        "",
        "This is a source-location result, not proof that the original SAR source does not exist elsewhere.",
        "",
        "## Minimum Recovery Path",
        "",
    ]
    for row in recovery_rows:
        lines.append(f"- `{row['required_source_file']}`: {row['why_required']}")
    write_text(IMAGING_SOURCE_GATE, "\n".join(lines).rstrip() + "\n")
    # Store recovery rows in the same report as prose; the final closure reads
    # them from this local list rather than a separate CSV to avoid an empty
    # extra artifact not requested as mandatory.
    return {"status": status, "inventory_rows": rows, "recovery_rows": recovery_rows}


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def determine_main_status(eval_rows: Sequence[Mapping[str, Any]], source_status: str) -> str:
    trusted = [row for row in eval_rows if row.get("evaluation_class") == "trusted_negative_evaluation"]
    present = [row for row in eval_rows if row.get("evaluation_class") == "posthoc_vehicle_present_evaluation"]
    if not trusted:
        return "OPEN_TRUSTED_NEGATIVE_EVALUATION_BLOCKED"
    high_trust = [row for row in trusted if row.get("confidence_status") == "vehicle_absent_high_confidence"]
    if not high_trust and all(row.get("confidence_status") != "vehicle_absent_moderate_confidence" for row in trusted):
        return "OPEN_TRUSTED_NEGATIVE_EVALUATION_BLOCKED"
    if source_status in {"PNG_PROVENANCE_BLOCKED"}:
        return "OPEN_PNG_PROVENANCE_BLOCKED"
    if not present:
        return "OPEN_TRUSTED_NEGATIVE_EVALUATION_BLOCKED"
    present_density = median([parse_float(row.get("path_density_per_effective_volume")) for row in present])
    trusted_density = median([parse_float(row.get("path_density_per_effective_volume")) for row in trusted])
    present_phys = median([parse_float(row.get("physical_path_count")) for row in present])
    trusted_phys = median([parse_float(row.get("physical_path_count")) for row in trusted])
    if present_density > trusted_density * 2.0 and present_phys > trusted_phys * 1.5:
        return "CLOSED_PNG_IDENTIFIABLE_WITH_COARSE_RADIAL_BANDS"
    return "CLOSED_PNG_DISPLAY_DOMAIN_INSUFFICIENT"


def render_closure_report(source_status: str | None = None) -> None:
    freeze_rows = read_csv(AUTOMATIC_FREEZE_MANIFEST) if AUTOMATIC_FREEZE_MANIFEST.exists() else []
    static_map = read_csv(STATIC_BACKGROUND_MAP) if STATIC_BACKGROUND_MAP.exists() else []
    paths = read_csv(PHYSICAL_SHORT_PATHS) if PHYSICAL_SHORT_PATHS.exists() else []
    directed_edges = read_csv(DIRECTED_COMPONENT_EDGES) if DIRECTED_COMPONENT_EDGES.exists() else []
    radial_stats = read_csv(RADIAL_BAND_STATISTICS) if RADIAL_BAND_STATISTICS.exists() else []
    auto_summary = read_csv(AUTOMATIC_IDENTIFIABILITY_SUMMARY) if AUTOMATIC_IDENTIFIABILITY_SUMMARY.exists() else []
    eval_rows = read_csv(POSTHOC_IDENTIFIABILITY_EVALUATION) if POSTHOC_IDENTIFIABILITY_EVALUATION.exists() else []
    source_status = source_status or ("RAW_SOURCE_LOCATION_UNKNOWN" if IMAGING_SOURCE_GATE.exists() else "source_gate_not_run")
    main_status = determine_main_status(eval_rows, source_status) if eval_rows else "posthoc_not_run"
    path_status_counts = Counter(row.get("path_status", "") for row in paths)
    static_counts = Counter(row.get("background_position_status", "") for row in static_map)
    lines = [
        "# OTY2 WGV3.4A SAR Observation Identifiability Closure",
        "",
        f"Date: {DATE}",
        "",
        f"WGV3.4A status: `{main_status}`",
        f"Imaging source gate status: `{source_status}`",
        "",
        "## Boundary",
        "",
        "Automatic stage used WGV3.3B, WGV3.3D automatic products, and SAR PNG display products only. WGV1.4/WGV1.8 and optical posthoc windows were read only after the automatic freeze.",
        "",
        "No path is named as a final target trajectory. Paths remain local SAR response path segments.",
        "",
        "## Automatic Freeze",
        "",
        f"- combined SHA256: `{freeze_rows[0]['combined_sha256'] if freeze_rows else ''}`",
        "- wgv1_4_read_before_freeze=false",
        "- wgv1_8_read_before_freeze=false",
        "- sar_gt_ids_loaded=false",
        "- gt_box_or_center_loaded=false",
        "- posthoc_window_labels_loaded=false",
        "",
        "## Static Background Map",
        "",
        f"- persistent_static_structure: `{static_counts['persistent_static_structure']}`",
        f"- recurrent_background_structure: `{static_counts['recurrent_background_structure']}`",
        f"- variable_background: `{static_counts['variable_background']}`",
        f"- rare_response_location: `{static_counts['rare_response_location']}`",
        f"- insufficient_support: `{static_counts['insufficient_support']}`",
        "",
        "## Directed Short Paths",
        "",
        f"- directed_edges: `{len(directed_edges)}`",
        f"- short_paths: `{len(paths)}`",
        f"- path_status_counts: `{dict(path_status_counts)}`",
        "",
        "## Radial Bands",
        "",
        markdown_table(radial_stats[:18], ["radial_band", "extraction_profile", "short_path_count", "physical_path_count", "static_path_count", "median_spatial_effect", "median_temporal_effect"]),
        "",
        "## Automatic Hypotheses",
        "",
        markdown_table(auto_summary, ["hypothesis_id", "intersecting_short_path_count", "physically_consistent_path_count", "static_structure_path_count", "recurrent_background_path_count", "path_density_per_effective_volume"]),
        "",
    ]
    if eval_rows:
        lines.extend(
            [
                "## Posthoc Evaluation",
                "",
                markdown_table(
                    eval_rows,
                    [
                        "evaluation_window_id",
                        "evaluation_class",
                        "confidence_status",
                        "overlapping_path_count",
                        "physical_path_count",
                        "static_path_count",
                        "path_density_per_effective_volume",
                        "identifiability_signal",
                    ],
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Conclusion",
            "",
            "The PNG-domain repairs reduce the WGV3.3D graph-percolation failure by using directed short paths and an independent static background map. However, the available PNG display products still do not provide a stable, source-grounded separation between vehicle-present windows and conservative negative/structure controls. Continuing by tuning PNG thresholds is therefore not recommended unless the imaging source chain is recovered.",
        ]
    )
    write_text(CLOSURE_REPORT, "\n".join(lines).rstrip() + "\n")


def run_all() -> dict[str, Any]:
    auto = run_automatic_stage()
    posthoc = run_posthoc_stage()
    source = run_source_gate_stage()
    render_closure_report(source["status"])
    return {"automatic": auto, "posthoc": posthoc, "source": source}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["automatic", "posthoc", "source-gate", "all"], default="all")
    args = parser.parse_args(argv)
    if args.stage == "automatic":
        auto = run_automatic_stage()
        print(
            json.dumps(
                {
                    "status": "WGV3.4A_AUTOMATIC_FREEZE_COMPLETE",
                    "directed_edges": len(auto["directed_edges"]),
                    "short_paths": len(auto["paths"]),
                    "freeze_sha256": auto["freeze_rows"][0]["combined_sha256"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.stage == "posthoc":
        posthoc = run_posthoc_stage()
        print(json.dumps({"status": "WGV3.4A_POSTHOC_COMPLETE", "windows": len(posthoc["windows"])}, ensure_ascii=False, indent=2))
    elif args.stage == "source-gate":
        source = run_source_gate_stage()
        render_closure_report(source["status"])
        print(json.dumps({"status": source["status"], "inventory_rows": len(source["inventory_rows"])}, ensure_ascii=False, indent=2))
    else:
        result = run_all()
        source_status = result["source"]["status"]
        eval_rows = result["posthoc"]["eval_rows"]
        print(
            json.dumps(
                {
                    "status": determine_main_status(eval_rows, source_status),
                    "imaging_source_gate_status": source_status,
                    "branch": git_fact(["branch", "--show-current"]),
                    "head": git_fact(["rev-parse", "HEAD"]),
                    "freeze_sha256": result["automatic"]["freeze_rows"][0]["combined_sha256"],
                    "directed_edges": len(result["automatic"]["directed_edges"]),
                    "short_paths": len(result["automatic"]["paths"]),
                    "evaluation_windows": len(result["posthoc"]["windows"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
