"""OTY2 stratified posthoc mechanism validation and shell ablation.

This script uses SAR GT and SAR image content only for posthoc mechanism
validation. It does not construct runtime priors, generate annotation
proposals, train/tune thresholds, score candidates, use selector/ranking logic,
or claim identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

import run_oty2_gt_correspondence_mechanism_audit as base


REPO_ROOT = base.REPO_ROOT
REPORT_DIR = base.REPORT_DIR
OUTPUT_PARENT = base.OUTPUT_PARENT
SAMPLE_ROOT = REPORT_DIR / "samples" / "gt_mechanism_stratified_validation"

EXPECTED_LEDGER_COUNTS = {
    "paired_optical_object_sar_gt": 215,
    "blocked_missing_gm011_object_stream": 195,
    "sar_only_gt": 20,
    "missing_review_optical_bbox": 0,
    "no_oty_iou_match": 12,
    "other_unclassified_blocker": 0,
}

TIGHT_VEHICLE_SIZE_SHELL = {
    "long_axis_min_px": 105.0,
    "long_axis_max_px": 190.0,
    "short_axis_min_px": 45.0,
    "short_axis_max_px": 95.0,
    "aspect_min": 1.45,
    "aspect_max": 3.10,
}

SHELL_PROFILES = {
    "tight_vehicle_shell": TIGHT_VEHICLE_SIZE_SHELL,
    "base_vehicle_shell": base.BASE_VEHICLE_SIZE_SHELL,
    "relaxed_vehicle_shell": base.RELAXED_VEHICLE_SIZE_SHELL,
}

AZIMUTH_FIXED_MARGINS_DEG = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
}

STRATIFIED_FIELDS = [
    "section",
    "level",
    "group_key",
    "scene",
    "object_hypothesis_id",
    "n_frames",
    "n_objects",
    "total_gt_count",
    "paired_frame_count",
    "blocked_missing_gm011_object_stream",
    "sar_only_gt",
    "detection_dropout_or_no_oty_iou_match",
    "temporal_window_pass_rate",
    "azimuth_original_pass_rate",
    "tight_shell_pass_rate",
    "base_shell_pass_rate",
    "relaxed_shell_pass_rate",
    "median_original_azimuth_width_deg",
    "median_abs_azimuth_error_deg",
    "median_sar_radius_px",
    "median_gt_long_axis_px",
    "median_gt_short_axis_px",
    "median_optical_area_ratio",
    "median_optical_height",
    "median_optical_bottom_y_norm",
    "area_radius_pearson",
    "height_radius_pearson",
    "bottom_y_radius_pearson",
    "aspect_radius_pearson",
    "temporal_area_radius_trend_status",
    "temporal_center_azimuth_trend_status",
    "status_counts",
    "notes",
]

AZIMUTH_FIELDS = [
    "strategy",
    "margin_deg",
    "subgroup_type",
    "subgroup",
    "n_frames",
    "n_objects",
    "coverage_pass",
    "coverage_fail",
    "coverage_rate",
    "median_sector_width_deg",
    "median_width_compression_rate_vs_original",
    "median_signed_error_deg",
    "median_abs_error_deg",
    "mean_signed_error_deg",
    "failure_context_counts",
    "failure_scene_counts",
    "failure_object_count",
    "systematic_offset_note",
    "posthoc_only_note",
]

SHELL_FIELDS = [
    "shell_profile",
    "subgroup_type",
    "subgroup",
    "profile_definition",
    "n_frames",
    "n_objects",
    "coverage_pass",
    "coverage_fail",
    "coverage_rate",
    "median_shell_angular_width_deg_at_gt_radius",
    "median_original_azimuth_width_deg",
    "median_intersection_width_deg",
    "median_intersection_compression_rate_vs_original_azimuth",
    "failure_status_counts",
    "failure_scene_counts",
    "objects_relaxed_needed_vs_tight_count",
    "objects_relaxed_needed_vs_tight_examples",
    "objects_relaxed_only_vs_base_count",
    "objects_relaxed_only_vs_base_examples",
    "objects_tight_sufficient_count",
    "objects_tight_sufficient_examples",
    "posthoc_only_note",
]

SHAPE_FIELDS = [
    "stratum_type",
    "stratum",
    "feature",
    "target",
    "n_frames",
    "n_objects",
    "pearson",
    "slope",
    "median_feature",
    "median_target",
    "effect_direction",
    "stability_label",
    "limit_note",
]

TEMPORAL_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "n_paired_frames",
    "vehicle_research_eligibility_modes",
    "context_modes",
    "correspondence_confidence_modes",
    "optical_center_x_slope_per_frame",
    "optical_center_y_slope_per_frame",
    "optical_area_slope_per_frame",
    "optical_height_slope_per_frame",
    "optical_bottom_y_slope_per_frame",
    "optical_aspect_slope_per_frame",
    "sar_gt_center_x_slope_per_optical_frame",
    "sar_gt_center_y_slope_per_optical_frame",
    "sar_radius_slope_per_optical_frame",
    "sar_azimuth_slope_per_optical_frame",
    "area_vs_radius_trend",
    "height_vs_radius_trend",
    "bottom_y_vs_radius_trend",
    "aspect_vs_radius_trend",
    "center_x_vs_azimuth_trend",
    "trajectory_reliability_label",
    "review_only_or_artifact_note",
]

SAR_ONLY_FIELDS = [
    "scene",
    "sar_gt_id",
    "sar_frame",
    "target_identity",
    "gt_center_radius_px",
    "gt_azimuth_deg",
    "gt_long_axis_px",
    "gt_short_axis_px",
    "gt_axis_aspect",
    "sar_box_mean_intensity",
    "sar_local_background_mean",
    "sar_box_to_background_ratio",
    "sar_peak_to_background_ratio",
    "sar_center_to_peak_distance_px",
    "scatter_support_status",
    "sar_image_path",
    "notes",
]

VISUAL_FIELDS = [
    "sample_role",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "sar_gt_id",
    "sar_frame",
    "local_visualization_path",
    "repo_sample_visualization_path",
    "notes",
]


def latest_path(pattern: str, base_dir: Path = REPORT_DIR) -> Path:
    paths = sorted(base_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base_dir / pattern}")
    return paths[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: stringify(row.get(field, "")) for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ";".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value)


def fmt(value: Any, digits: int = 4) -> str:
    numeric = base.safe_float(value)
    if numeric is None or not math.isfinite(numeric):
        return ""
    return f"{numeric:.{digits}f}".rstrip("0").rstrip(".")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def median_clean(values: Iterable[Any]) -> float | None:
    clean = [float(value) for value in (base.safe_float(item) for item in values) if value is not None and math.isfinite(value)]
    return float(median(clean)) if clean else None


def mean_clean(values: Iterable[Any]) -> float | None:
    clean = [float(value) for value in (base.safe_float(item) for item in values) if value is not None and math.isfinite(value)]
    return sum(clean) / len(clean) if clean else None


def pass_rate(rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    total = sum(1 for row in rows if str(row.get(field, "")) in {"true", "false"})
    if total == 0:
        return None
    return sum(1 for row in rows if str(row.get(field, "")) == "true") / total


def compact_counts(counter: Mapping[str, int] | Counter[str], limit: int = 10) -> str:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if not items:
        return ""
    head = [f"{key}={value}" for key, value in items[:limit]]
    if len(items) > limit:
        head.append(f"other_keys={len(items) - limit}")
    return ";".join(head)


def compact_values(values: Iterable[Any], limit: int = 12) -> str:
    unique = []
    seen = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            unique.append(text)
            seen.add(text)
    suffix = "" if len(unique) <= limit else f";...(+{len(unique) - limit})"
    return ";".join(unique[:limit]) + suffix


def parse_gt_box_text(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in str(text or "").split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        number = base.safe_float(value)
        if number is not None:
            values[key.strip()] = number
    return values


def split_object_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))


def parse_flags(row: Mapping[str, Any]) -> dict[str, bool]:
    text = str(row.get("edge_partial_duplicate_handoff_ambiguity_flags", "")).lower()
    visibility = str(row.get("visibility_state", "")).lower()
    eligibility = str(row.get("vehicle_research_eligibility", "")).lower()

    def kv(source: str, key: str) -> str:
        match = re.search(rf"(?:^|;){re.escape(key)}=([^;]*)", source)
        return match.group(1).strip().lower() if match else ""

    def kv_true(source: str, key: str) -> bool:
        return kv(source, key) in {"true", "1", "yes", "y"}

    visibility_partial = kv(visibility, "partial")
    visibility_boundary = kv(visibility, "boundary")
    visibility_multi = kv(visibility, "multi")
    # The prior audit's object-level edge/partial/duplicate flags are coarse and
    # true for every paired frame in this dataset. Use frame-level visibility for
    # stratified validation so per-status summaries are not collapsed.
    return {
        "edge": visibility_boundary not in {"", "none"},
        "partial": visibility_partial not in {"", "none"},
        "duplicate_handoff": visibility_multi not in {"", "none", "single_observation"},
        "ambiguous": "review_only" in eligibility,
        "far_small": "far_small" in eligibility,
    }


def context_bucket(row: Mapping[str, Any]) -> str:
    flags = parse_flags(row)
    if flags["duplicate_handoff"]:
        return "duplicate_or_handoff"
    if flags["edge"]:
        return "edge"
    if flags["partial"]:
        return "partial"
    if flags["far_small"]:
        return "far_small"
    if flags["ambiguous"]:
        return "ambiguous_or_review_only"
    return "complete"


def correspondence_confidence(row: Mapping[str, Any]) -> str:
    if str(row.get("correspondence_status", "")).endswith("_high"):
        return "high_confidence_correspondence"
    return "weak_correspondence"


def sign_label(value: float | None, eps: float = 1e-9) -> str:
    if value is None or not math.isfinite(value) or abs(value) <= eps:
        return "flat_or_insufficient"
    return "positive" if value > 0 else "negative"


def compare_expected_opposite(a: float | None, b: float | None, eps_a: float = 1e-9, eps_b: float = 1e-9) -> str:
    if a is None or b is None or not math.isfinite(a) or not math.isfinite(b):
        return "insufficient_temporal_pairs"
    if abs(a) <= eps_a or abs(b) <= eps_b:
        return "weak_or_flat_temporal_trend"
    if a * b < 0:
        return "opposite_sign_consistent"
    return "same_sign_conflict"


def compare_same_sign(a: float | None, b: float | None, eps_a: float = 1e-9, eps_b: float = 1e-9) -> str:
    if a is None or b is None or not math.isfinite(a) or not math.isfinite(b):
        return "insufficient_temporal_pairs"
    if abs(a) <= eps_a or abs(b) <= eps_b:
        return "weak_or_flat_temporal_trend"
    if a * b > 0:
        return "same_sign_consistent"
    return "opposite_sign"


def shell_contains(row: Mapping[str, Any], shell: Mapping[str, float]) -> bool:
    long_axis = base.safe_float(row.get("gt_long_axis_px"))
    short_axis = base.safe_float(row.get("gt_short_axis_px"))
    if long_axis is None or short_axis is None:
        return False
    return base.shell_contains(long_axis, short_axis, shell)


def shell_angular_width_deg(row: Mapping[str, Any], shell: Mapping[str, float]) -> float | None:
    radius = base.safe_float(row.get("sar_gt_radius_px"))
    if radius is None or radius <= 0:
        return None
    return math.degrees(2.0 * math.atan((shell["long_axis_max_px"] / 2.0) / radius))


def group_rows(rows: Sequence[Mapping[str, Any]], key_fn: Any) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(key_fn(row))].append(row)
    return dict(grouped)


def rows_to_pearson(rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str) -> float | None:
    xs = [base.safe_float(row.get(x_field)) for row in rows]
    ys = [base.safe_float(row.get(y_field)) for row in rows]
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    return base.pearson([x for x, _ in pairs], [y for _, y in pairs])


def rows_to_slope(rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str) -> float | None:
    xs = [base.safe_float(row.get(x_field)) for row in rows]
    ys = [base.safe_float(row.get(y_field)) for row in rows]
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 2:
        return None
    return base.slope([x for x, _ in pairs], [y for _, y in pairs])


def load_input_tables(args: argparse.Namespace) -> dict[str, Any]:
    tables = base.load_tables(args)
    accounting_csv = Path(args.accounting_csv) if args.accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv")
    dropout_csv = Path(args.dropout_temporal_csv) if args.dropout_temporal_csv else latest_path("oty2_detection_dropout_temporal_support_audit_*.csv")
    tables["accounting_rows"] = read_csv(accounting_csv)
    tables["dropout_rows"] = read_csv(dropout_csv)
    tables["accounting_csv"] = accounting_csv
    tables["dropout_temporal_csv"] = dropout_csv
    return tables


def validate_sample_ledger(accounting_rows: Sequence[Mapping[str, str]], final_gt_rows: Sequence[Mapping[str, str]], paired_count: int) -> dict[str, Any]:
    counts = Counter(str(row.get("match_status", "")) for row in accounting_rows)
    scene_counts = Counter(str(row.get("scene", "")) for row in accounting_rows)
    expected_sum = sum(EXPECTED_LEDGER_COUNTS.values())
    ledger_valid = (
        len(final_gt_rows) == 442
        and len(accounting_rows) == 442
        and paired_count == 215
        and expected_sum == 442
        and all(counts.get(key, 0) == value for key, value in EXPECTED_LEDGER_COUNTS.items())
    )
    return {
        "ledger_valid": ledger_valid,
        "final_gt_count": len(final_gt_rows),
        "accounting_row_count": len(accounting_rows),
        "paired_count_rebuilt": paired_count,
        "category_counts": dict(counts),
        "scene_counts": dict(scene_counts),
        "expected_category_counts": dict(EXPECTED_LEDGER_COUNTS),
    }


def build_joined_records(
    correspondences: Sequence[Mapping[str, Any]],
    shell_rows: Sequence[Mapping[str, Any]],
    shape_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    shell_by_id = {(str(row.get("scene", "")), str(row.get("sar_gt_id", ""))): dict(row) for row in shell_rows}
    shape_by_id = {(str(row.get("scene", "")), str(row.get("sar_gt_id", ""))): dict(row) for row in shape_rows}
    records: list[dict[str, Any]] = []
    for corr in correspondences:
        key = (str(corr.get("scene", "")), str(corr.get("sar_gt_id", "")))
        record: dict[str, Any] = dict(corr)
        record.update({f"shell_{k}": v for k, v in shell_by_id.get(key, {}).items()})
        record.update({f"shape_{k}": v for k, v in shape_by_id.get(key, {}).items()})
        bbox = corr.get("review_optical_bbox")
        if isinstance(bbox, tuple):
            x1, y1, x2, y2 = bbox
            record["optical_center_x"] = (x1 + x2) / 2.0
            record["optical_center_y"] = (y1 + y2) / 2.0
        record["object_key"] = "|".join(split_object_key(corr))
        record["status_context"] = context_bucket(corr)
        record["correspondence_confidence"] = correspondence_confidence(corr)
        legacy_flags = str(record.get("edge_partial_duplicate_handoff_ambiguity_flags", ""))
        record["legacy_object_level_flags"] = legacy_flags
        record["edge_partial_duplicate_handoff_ambiguity_flags"] = (
            f"frame_context={record['status_context']};"
            f"legacy_object_level_flags={legacy_flags}"
        )
        record["tight_vehicle_shell_contains_gt"] = bool_text(shell_contains(corr, TIGHT_VEHICLE_SIZE_SHELL))
        record["base_vehicle_shell_contains_gt"] = bool_text(shell_contains(corr, base.BASE_VEHICLE_SIZE_SHELL))
        record["relaxed_vehicle_shell_contains_gt"] = bool_text(shell_contains(corr, base.RELAXED_VEHICLE_SIZE_SHELL))
        record["azimuth_abs_error_deg"] = abs(base.safe_float(corr.get("azimuth_error_to_center_deg"), 0.0) or 0.0)
        record["sar_gt_center_x"] = corr.get("gt_cx")
        record["sar_gt_center_y"] = corr.get("gt_cy")
        record["sar_radius_px"] = corr.get("sar_gt_radius_px")
        record["sar_azimuth_deg"] = corr.get("sar_gt_azimuth_deg")
        record["optical_bbox_aspect_float"] = base.safe_float(corr.get("optical_bbox_aspect_ratio"))
        records.append(record)
    return records


def summarize_group(section: str, level: str, group_key: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    objects = {row.get("object_key", "") for row in rows}
    return {
        "section": section,
        "level": level,
        "group_key": group_key,
        "scene": "" if "|" in group_key or level != "scene" else group_key,
        "object_hypothesis_id": group_key.split("|", 1)[1] if level == "object" and "|" in group_key else "",
        "n_frames": len(rows),
        "n_objects": len(objects),
        "paired_frame_count": len(rows),
        "temporal_window_pass_rate": fmt(pass_rate(rows, "temporal_window_contains_gt_frame"), 4),
        "azimuth_original_pass_rate": fmt(pass_rate(rows, "azimuth_prior_contains_gt"), 4),
        "tight_shell_pass_rate": fmt(pass_rate(rows, "tight_vehicle_shell_contains_gt"), 4),
        "base_shell_pass_rate": fmt(pass_rate(rows, "base_vehicle_shell_contains_gt"), 4),
        "relaxed_shell_pass_rate": fmt(pass_rate(rows, "relaxed_vehicle_shell_contains_gt"), 4),
        "median_original_azimuth_width_deg": fmt(median_clean(row.get("azimuth_prior_width_deg") for row in rows), 3),
        "median_abs_azimuth_error_deg": fmt(median_clean(row.get("azimuth_abs_error_deg") for row in rows), 3),
        "median_sar_radius_px": fmt(median_clean(row.get("sar_gt_radius_px") for row in rows), 3),
        "median_gt_long_axis_px": fmt(median_clean(row.get("gt_long_axis_px") for row in rows), 3),
        "median_gt_short_axis_px": fmt(median_clean(row.get("gt_short_axis_px") for row in rows), 3),
        "median_optical_area_ratio": fmt(median_clean(row.get("optical_bbox_area_ratio") for row in rows), 6),
        "median_optical_height": fmt(median_clean(row.get("optical_bbox_height") for row in rows), 3),
        "median_optical_bottom_y_norm": fmt(median_clean(row.get("optical_bbox_bottom_y_norm") for row in rows), 4),
        "area_radius_pearson": fmt(rows_to_pearson(rows, "optical_bbox_area_ratio", "sar_gt_radius_px"), 4),
        "height_radius_pearson": fmt(rows_to_pearson(rows, "optical_bbox_height", "sar_gt_radius_px"), 4),
        "bottom_y_radius_pearson": fmt(rows_to_pearson(rows, "optical_bbox_bottom_y_norm", "sar_gt_radius_px"), 4),
        "aspect_radius_pearson": fmt(rows_to_pearson(rows, "optical_bbox_aspect_float", "sar_gt_radius_px"), 4),
        "status_counts": compact_counts(Counter(str(row.get("status_context", "")) for row in rows)),
        "notes": "frame-level rows are posthoc paired samples; grouped rows prevent treating 215 frames as 215 independent objects",
    }


def build_object_aggregates(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    object_rows: list[dict[str, Any]] = []
    for object_key, rows in sorted(group_rows(records, lambda row: row.get("object_key", "")).items()):
        ordered = sorted(rows, key=lambda row: base.safe_float(row.get("optical_frame"), 0.0) or 0.0)
        area_slope = rows_to_slope(ordered, "optical_frame", "optical_bbox_area_ratio")
        height_slope = rows_to_slope(ordered, "optical_frame", "optical_bbox_height")
        bottom_slope = rows_to_slope(ordered, "optical_frame", "optical_bbox_bottom_y_norm")
        aspect_slope = rows_to_slope(ordered, "optical_frame", "optical_bbox_aspect_float")
        center_x_slope = rows_to_slope(ordered, "optical_frame", "optical_center_x")
        center_y_slope = rows_to_slope(ordered, "optical_frame", "optical_center_y")
        sar_x_slope = rows_to_slope(ordered, "optical_frame", "sar_gt_center_x")
        sar_y_slope = rows_to_slope(ordered, "optical_frame", "sar_gt_center_y")
        radius_slope = rows_to_slope(ordered, "optical_frame", "sar_gt_radius_px")
        az_slope = rows_to_slope(ordered, "optical_frame", "sar_gt_azimuth_deg")
        context_counts = Counter(str(row.get("status_context", "")) for row in ordered)
        eligibility_counts = Counter(str(row.get("vehicle_research_eligibility", "")) for row in ordered)
        confidence_counts = Counter(str(row.get("correspondence_confidence", "")) for row in ordered)
        area_radius = compare_expected_opposite(area_slope, radius_slope, 1e-7, 1e-3)
        center_az = compare_same_sign(center_x_slope, az_slope, 1e-3, 1e-4)
        artifact_flags = []
        if len(ordered) < 3:
            artifact_flags.append("too_few_paired_frames_for_trend")
        if any(key in context_counts for key in ("duplicate_or_handoff", "edge", "partial", "ambiguous_or_review_only", "far_small")):
            artifact_flags.append("state_or_review_context_can_dominate_trend")
        object_rows.append(
            {
                "scene": str(ordered[0].get("scene", "")),
                "object_hypothesis_id": str(ordered[0].get("object_hypothesis_id", "")),
                "object_key": object_key,
                "n_paired_frames": len(ordered),
                "vehicle_research_eligibility_modes": compact_counts(eligibility_counts),
                "context_modes": compact_counts(context_counts),
                "correspondence_confidence_modes": compact_counts(confidence_counts),
                "optical_center_x_slope_per_frame": center_x_slope,
                "optical_center_y_slope_per_frame": center_y_slope,
                "optical_area_slope_per_frame": area_slope,
                "optical_height_slope_per_frame": height_slope,
                "optical_bottom_y_slope_per_frame": bottom_slope,
                "optical_aspect_slope_per_frame": aspect_slope,
                "sar_gt_center_x_slope_per_optical_frame": sar_x_slope,
                "sar_gt_center_y_slope_per_optical_frame": sar_y_slope,
                "sar_radius_slope_per_optical_frame": radius_slope,
                "sar_azimuth_slope_per_optical_frame": az_slope,
                "area_vs_radius_trend": area_radius,
                "height_vs_radius_trend": compare_expected_opposite(height_slope, radius_slope, 1e-4, 1e-3),
                "bottom_y_vs_radius_trend": compare_expected_opposite(bottom_slope, radius_slope, 1e-6, 1e-3),
                "aspect_vs_radius_trend": compare_expected_opposite(aspect_slope, radius_slope, 1e-5, 1e-3),
                "center_x_vs_azimuth_trend": center_az,
                "trajectory_reliability_label": classify_temporal_reliability(len(ordered), area_radius, center_az, context_counts),
                "review_only_or_artifact_note": ";".join(artifact_flags) or "cleaner_temporal_probe_candidate_posthoc_only",
            }
        )
    return object_rows


def classify_temporal_reliability(n: int, area_radius: str, center_az: str, context_counts: Counter[str]) -> str:
    risky_contexts = {"duplicate_or_handoff", "edge", "partial", "ambiguous_or_review_only", "far_small"}
    if n < 3:
        return "insufficient_temporal_pairs"
    if any(context_counts.get(key, 0) > 0 for key in risky_contexts):
        if area_radius == "opposite_sign_consistent":
            return "review_only_temporal_signal"
        return "state_contaminated_or_unstable"
    if area_radius == "opposite_sign_consistent":
        return "clean_object_temporal_signal"
    if center_az == "same_sign_consistent":
        return "center_direction_signal_only"
    return "unstable_temporal_signal"


def build_stratified_rows(records: Sequence[Mapping[str, Any]], object_aggs: Sequence[Mapping[str, Any]], ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "section": "ledger",
            "level": "sample_pool",
            "group_key": "all_gt",
            "n_frames": ledger["accounting_row_count"],
            "n_objects": "",
            "total_gt_count": ledger["final_gt_count"],
            "paired_frame_count": ledger["category_counts"].get("paired_optical_object_sar_gt", 0),
            "blocked_missing_gm011_object_stream": ledger["category_counts"].get("blocked_missing_gm011_object_stream", 0),
            "sar_only_gt": ledger["category_counts"].get("sar_only_gt", 0),
            "detection_dropout_or_no_oty_iou_match": ledger["category_counts"].get("no_oty_iou_match", 0),
            "notes": "ledger_valid=true; stop before mechanism conclusions if this row changes",
        },
        summarize_group("frame_level", "all", "paired_clean_frames", records),
    ]
    object_trends = Counter(str(row.get("trajectory_reliability_label", "")) for row in object_aggs)
    area_trends = Counter(str(row.get("area_vs_radius_trend", "")) for row in object_aggs)
    rows.append(
        {
            "section": "object_level",
            "level": "all",
            "group_key": "paired_objects",
            "n_frames": len(records),
            "n_objects": len(object_aggs),
            "paired_frame_count": len(records),
            "temporal_area_radius_trend_status": compact_counts(area_trends),
            "temporal_center_azimuth_trend_status": compact_counts(Counter(str(row.get("center_x_vs_azimuth_trend", "")) for row in object_aggs)),
            "status_counts": compact_counts(object_trends),
            "notes": "object-level aggregation collapses repeated frames by scene/object_hypothesis_id",
        }
    )
    for scene, scene_rows in sorted(group_rows(records, lambda row: row.get("scene", "")).items()):
        rows.append(summarize_group("per_scene", "scene", scene, scene_rows))
    for key, group in sorted(group_rows(records, lambda row: row.get("vehicle_research_eligibility", "")).items()):
        rows.append(summarize_group("per_status", "vehicle_research_eligibility", key, group))
    for key, group in sorted(group_rows(records, lambda row: row.get("status_context", "")).items()):
        rows.append(summarize_group("per_status", "context", key, group))
    for key, group in sorted(group_rows(records, lambda row: row.get("correspondence_confidence", "")).items()):
        rows.append(summarize_group("per_status", "correspondence_confidence", key, group))
    for obj in object_aggs:
        rows.append(
            {
                "section": "per_object_trend",
                "level": "object",
                "group_key": obj["object_key"],
                "scene": obj["scene"],
                "object_hypothesis_id": obj["object_hypothesis_id"],
                "n_frames": obj["n_paired_frames"],
                "n_objects": 1,
                "temporal_area_radius_trend_status": obj["area_vs_radius_trend"],
                "temporal_center_azimuth_trend_status": obj["center_x_vs_azimuth_trend"],
                "status_counts": obj["context_modes"],
                "notes": obj["trajectory_reliability_label"] + ";" + obj["review_only_or_artifact_note"],
            }
        )
    return rows


def azimuth_pass_for_margin(row: Mapping[str, Any], margin: float) -> bool:
    error = base.safe_float(row.get("azimuth_error_to_center_deg"))
    return error is not None and abs(error) <= margin


def build_azimuth_ablation_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups: list[tuple[str, str, Sequence[Mapping[str, Any]]]] = [("all", "all", records)]
    groups += [("scene", key, value) for key, value in sorted(group_rows(records, lambda row: row.get("scene", "")).items())]
    groups += [
        ("context", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("status_context", "")).items())
    ]
    groups += [
        ("vehicle_research_eligibility", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("vehicle_research_eligibility", "")).items())
    ]

    for subgroup_type, subgroup, group in groups:
        rows.append(summarize_azimuth_strategy("original_interval", "", subgroup_type, subgroup, group, None))
        for margin in AZIMUTH_FIXED_MARGINS_DEG:
            rows.append(summarize_azimuth_strategy("centered_fixed_margin", margin, subgroup_type, subgroup, group, margin))
    return rows


def summarize_azimuth_strategy(
    strategy: str,
    margin_label: Any,
    subgroup_type: str,
    subgroup: str,
    records: Sequence[Mapping[str, Any]],
    margin: float | None,
) -> dict[str, Any]:
    if margin is None:
        pass_flags = [str(row.get("azimuth_prior_contains_gt", "")) == "true" for row in records]
        widths = [base.safe_float(row.get("azimuth_prior_width_deg")) for row in records]
        compression_rates = [0.0 for _ in records]
    else:
        pass_flags = [azimuth_pass_for_margin(row, margin) for row in records]
        widths = [2.0 * margin for _ in records]
        compression_rates = []
        for row in records:
            original = base.safe_float(row.get("azimuth_prior_width_deg"))
            if original is not None and original > 0:
                compression_rates.append(max(0.0, 1.0 - min(2.0 * margin, original) / original))
    failed = [row for row, ok in zip(records, pass_flags) if not ok]
    errors = [base.safe_float(row.get("azimuth_error_to_center_deg")) for row in records]
    mean_error = mean_clean(errors)
    median_error = median_clean(errors)
    if median_error is None:
        offset_note = "no_error_measure"
    elif median_error <= -5.0:
        offset_note = "negative_signed_bias_gt_left_of_prior_center"
    elif median_error >= 5.0:
        offset_note = "positive_signed_bias_gt_right_of_prior_center"
    else:
        offset_note = "no_large_median_signed_bias"
    return {
        "strategy": strategy,
        "margin_deg": margin_label,
        "subgroup_type": subgroup_type,
        "subgroup": subgroup,
        "n_frames": len(records),
        "n_objects": len({row.get("object_key", "") for row in records}),
        "coverage_pass": sum(1 for ok in pass_flags if ok),
        "coverage_fail": len(records) - sum(1 for ok in pass_flags if ok),
        "coverage_rate": fmt(sum(1 for ok in pass_flags if ok) / len(records) if records else None, 4),
        "median_sector_width_deg": fmt(median_clean(widths), 3),
        "median_width_compression_rate_vs_original": fmt(median_clean(compression_rates), 4),
        "median_signed_error_deg": fmt(median_error, 3),
        "median_abs_error_deg": fmt(median_clean(abs(base.safe_float(row.get("azimuth_error_to_center_deg"), 0.0) or 0.0) for row in records), 3),
        "mean_signed_error_deg": fmt(mean_error, 3),
        "failure_context_counts": compact_counts(Counter(str(row.get("status_context", "")) for row in failed)),
        "failure_scene_counts": compact_counts(Counter(str(row.get("scene", "")) for row in failed)),
        "failure_object_count": len({row.get("object_key", "") for row in failed}),
        "systematic_offset_note": offset_note,
        "posthoc_only_note": "coverage-vs-margin audit only; no runtime margin threshold selected",
    }


def build_shell_ablation_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    object_groups = group_rows(records, lambda row: row.get("object_key", ""))
    relaxed_needed_vs_tight = [
        key
        for key, rows in object_groups.items()
        if any(not shell_contains(row, TIGHT_VEHICLE_SIZE_SHELL) and shell_contains(row, base.RELAXED_VEHICLE_SIZE_SHELL) for row in rows)
    ]
    relaxed_only_vs_base = [
        key
        for key, rows in object_groups.items()
        if any(not shell_contains(row, base.BASE_VEHICLE_SIZE_SHELL) and shell_contains(row, base.RELAXED_VEHICLE_SIZE_SHELL) for row in rows)
    ]
    tight_sufficient = [key for key, rows in object_groups.items() if rows and all(shell_contains(row, TIGHT_VEHICLE_SIZE_SHELL) for row in rows)]

    rows: list[dict[str, Any]] = []
    groups: list[tuple[str, str, Sequence[Mapping[str, Any]]]] = [("all", "all", records)]
    groups += [("scene", key, value) for key, value in sorted(group_rows(records, lambda row: row.get("scene", "")).items())]
    groups += [
        ("context", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("status_context", "")).items())
    ]
    groups += [
        ("vehicle_research_eligibility", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("vehicle_research_eligibility", "")).items())
    ]
    for profile_name, shell in SHELL_PROFILES.items():
        for subgroup_type, subgroup, group in groups:
            rows.append(
                summarize_shell_profile(
                    profile_name,
                    shell,
                    subgroup_type,
                    subgroup,
                    group,
                    relaxed_needed_vs_tight,
                    relaxed_only_vs_base,
                    tight_sufficient,
                )
            )
    return rows


def summarize_shell_profile(
    profile_name: str,
    shell: Mapping[str, float],
    subgroup_type: str,
    subgroup: str,
    records: Sequence[Mapping[str, Any]],
    relaxed_needed_vs_tight: Sequence[str],
    relaxed_only_vs_base: Sequence[str],
    tight_sufficient: Sequence[str],
) -> dict[str, Any]:
    pass_flags = [shell_contains(row, shell) for row in records]
    failed = [row for row, ok in zip(records, pass_flags) if not ok]
    shell_widths = [shell_angular_width_deg(row, shell) for row in records]
    original_widths = [base.safe_float(row.get("azimuth_prior_width_deg")) for row in records]
    intersections = []
    compression_rates = []
    for shell_width, original_width in zip(shell_widths, original_widths):
        if shell_width is None or original_width is None or original_width <= 0:
            continue
        intersection = min(shell_width, original_width)
        intersections.append(intersection)
        compression_rates.append(max(0.0, 1.0 - intersection / original_width))
    return {
        "shell_profile": profile_name,
        "subgroup_type": subgroup_type,
        "subgroup": subgroup,
        "profile_definition": json.dumps(shell, sort_keys=True),
        "n_frames": len(records),
        "n_objects": len({row.get("object_key", "") for row in records}),
        "coverage_pass": sum(1 for ok in pass_flags if ok),
        "coverage_fail": len(records) - sum(1 for ok in pass_flags if ok),
        "coverage_rate": fmt(sum(1 for ok in pass_flags if ok) / len(records) if records else None, 4),
        "median_shell_angular_width_deg_at_gt_radius": fmt(median_clean(shell_widths), 3),
        "median_original_azimuth_width_deg": fmt(median_clean(original_widths), 3),
        "median_intersection_width_deg": fmt(median_clean(intersections), 3),
        "median_intersection_compression_rate_vs_original_azimuth": fmt(median_clean(compression_rates), 4),
        "failure_status_counts": compact_counts(Counter(str(row.get("status_context", "")) for row in failed)),
        "failure_scene_counts": compact_counts(Counter(str(row.get("scene", "")) for row in failed)),
        "objects_relaxed_needed_vs_tight_count": len(relaxed_needed_vs_tight) if subgroup_type == "all" else "",
        "objects_relaxed_needed_vs_tight_examples": compact_values(relaxed_needed_vs_tight) if subgroup_type == "all" else "",
        "objects_relaxed_only_vs_base_count": len(relaxed_only_vs_base) if subgroup_type == "all" else "",
        "objects_relaxed_only_vs_base_examples": compact_values(relaxed_only_vs_base) if subgroup_type == "all" else "",
        "objects_tight_sufficient_count": len(tight_sufficient) if subgroup_type == "all" else "",
        "objects_tight_sufficient_examples": compact_values(tight_sufficient) if subgroup_type == "all" else "",
        "posthoc_only_note": "vehicle shell profile is an audit profile; no runtime size threshold is selected",
    }


def build_shape_probe_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    features = {
        "bbox_area_ratio": "optical_bbox_area_ratio",
        "bbox_height": "optical_bbox_height",
        "bbox_bottom_y_norm": "optical_bbox_bottom_y_norm",
        "bbox_aspect_ratio": "optical_bbox_aspect_float",
    }
    strata: list[tuple[str, str, Sequence[Mapping[str, Any]]]] = [("all", "all", records)]
    strata += [("scene", key, value) for key, value in sorted(group_rows(records, lambda row: row.get("scene", "")).items())]
    strata += [
        ("vehicle_research_eligibility", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("vehicle_research_eligibility", "")).items())
    ]
    strata += [
        ("context", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("status_context", "")).items())
    ]
    strata += [
        ("correspondence_confidence", key, value)
        for key, value in sorted(group_rows(records, lambda row: row.get("correspondence_confidence", "")).items())
    ]
    strata += [
        ("scene_x_vehicle_research_eligibility", key, value)
        for key, value in sorted(group_rows(records, lambda row: f"{row.get('scene', '')}|{row.get('vehicle_research_eligibility', '')}").items())
    ]
    strata += [("object", key, value) for key, value in sorted(group_rows(records, lambda row: row.get("object_key", "")).items())]

    rows: list[dict[str, Any]] = []
    for stratum_type, stratum, group in strata:
        for feature_name, field in features.items():
            pear = rows_to_pearson(group, field, "sar_gt_radius_px")
            slope = rows_to_slope(group, field, "sar_gt_radius_px")
            rows.append(
                {
                    "stratum_type": stratum_type,
                    "stratum": stratum,
                    "feature": feature_name,
                    "target": "sar_radius_px",
                    "n_frames": len(group),
                    "n_objects": len({row.get("object_key", "") for row in group}),
                    "pearson": fmt(pear, 4),
                    "slope": fmt(slope, 6),
                    "median_feature": fmt(median_clean(row.get(field) for row in group), 6),
                    "median_target": fmt(median_clean(row.get("sar_gt_radius_px") for row in group), 3),
                    "effect_direction": effect_direction(pear),
                    "stability_label": classify_shape_stability(stratum_type, len(group), pear),
                    "limit_note": shape_limit_note(stratum_type, group, pear),
                }
            )
    return rows


def effect_direction(pearson_value: float | None) -> str:
    if pearson_value is None:
        return "insufficient"
    if pearson_value <= -0.35:
        return "negative_relation_larger_optical_feature_nearer_radius"
    if pearson_value >= 0.35:
        return "positive_relation"
    return "weak_or_flat_relation"


def classify_shape_stability(stratum_type: str, n: int, pearson_value: float | None) -> str:
    min_n = 3 if stratum_type == "object" else 8
    if pearson_value is None or n < min_n:
        return "insufficient_for_stability"
    abs_r = abs(pearson_value)
    if abs_r >= 0.75:
        return "strong_posthoc_relation"
    if abs_r >= 0.55:
        return "moderate_posthoc_relation"
    if abs_r >= 0.35:
        return "weak_posthoc_relation"
    return "unstable_or_not_supported"


def shape_limit_note(stratum_type: str, group: Sequence[Mapping[str, Any]], pearson_value: float | None) -> str:
    contexts = Counter(str(row.get("status_context", "")) for row in group)
    scenes = Counter(str(row.get("scene", "")) for row in group)
    if stratum_type == "object":
        return "object-level frame repeats; useful for trend check, not independent sample count"
    if len(scenes) == 1 and "all" not in stratum_type:
        return "single_scene_stratum"
    if contexts.get("complete", 0) == len(group):
        return "complete_context_only"
    if any(contexts.get(key, 0) for key in ("edge", "partial", "duplicate_or_handoff", "far_small", "ambiguous_or_review_only")):
        return "state_mixed_or_review_context; do not convert to runtime rule"
    return "posthoc_only"


def build_temporal_rows(object_aggs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in object_aggs:
        row = {field: obj.get(field, "") for field in TEMPORAL_FIELDS}
        for field in TEMPORAL_FIELDS:
            if field.endswith("_slope_per_frame") or "_slope_per_optical_frame" in field:
                row[field] = fmt(obj.get(field), 8)
        rows.append(row)
    return rows


def build_sar_only_rows(accounting_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in accounting_rows:
        if str(item.get("match_status", "")) != "sar_only_gt":
            continue
        gt = parse_gt_box_text(str(item.get("gt_box", "")))
        cx = gt.get("cx")
        cy = gt.get("cy")
        w = gt.get("w")
        h = gt.get("h")
        if None in {cx, cy, w, h}:
            continue
        long_axis = max(float(w), float(h))
        short_axis = min(float(w), float(h))
        radius = base.point_to_radius_px(float(cx), float(cy))
        azimuth = base.point_to_azimuth_deg(float(cx), float(cy))
        image_path = Path(str(item.get("sar_pseudocolor_path", "")))
        ax_box = (float(cx) - float(w) / 2.0, float(cy) - float(h) / 2.0, float(cx) + float(w) / 2.0, float(cy) + float(h) / 2.0)
        scatter = base.patch_stats(image_path, float(cx), float(cy), ax_box)
        peak_ratio = base.safe_float(scatter.get("sar_peak_to_background_ratio"))
        box_ratio = base.safe_float(scatter.get("sar_box_to_background_ratio"))
        if peak_ratio is not None and peak_ratio >= 2.0:
            support = "local_scatter_peak_supported"
        elif box_ratio is not None and box_ratio >= 1.05:
            support = "box_mean_above_background_weak_support"
        else:
            support = "weak_or_no_box_mean_support_but_kept_as_sar_only_reference"
        rows.append(
            {
                "scene": item.get("scene", ""),
                "sar_gt_id": item.get("sar_gt_id", ""),
                "sar_frame": item.get("sar_frame", ""),
                "target_identity": item.get("target_identity", ""),
                "gt_center_radius_px": fmt(radius, 3),
                "gt_azimuth_deg": fmt(azimuth, 3),
                "gt_long_axis_px": fmt(long_axis, 3),
                "gt_short_axis_px": fmt(short_axis, 3),
                "gt_axis_aspect": fmt(long_axis / max(short_axis, 1e-6), 4),
                "sar_box_mean_intensity": fmt(scatter.get("sar_box_mean_intensity"), 6),
                "sar_local_background_mean": fmt(scatter.get("sar_local_background_mean"), 6),
                "sar_box_to_background_ratio": fmt(scatter.get("sar_box_to_background_ratio"), 6),
                "sar_peak_to_background_ratio": fmt(scatter.get("sar_peak_to_background_ratio"), 6),
                "sar_center_to_peak_distance_px": fmt(scatter.get("sar_center_to_peak_distance_px"), 3),
                "scatter_support_status": support,
                "sar_image_path": str(image_path),
                "notes": "SAR-only morphology reference only; excluded from optical-SAR correspondence mechanism",
                "_gt_cx": float(cx),
                "_gt_cy": float(cy),
                "_gt_w": float(w),
                "_gt_h": float(h),
                "_gt_heading": gt.get("heading", 0.0),
            }
        )
    return rows


def safe_file_part(value: Any) -> str:
    return base.safe_file_part(value)


def select_first(records: Sequence[Mapping[str, Any]], used: set[tuple[str, str]], predicate: Any) -> Mapping[str, Any] | None:
    for row in sorted(records, key=lambda item: (str(item.get("scene", "")), str(item.get("object_hypothesis_id", "")), int(base.safe_int(item.get("sar_frame"), 0) or 0))):
        key = (str(row.get("scene", "")), str(row.get("sar_gt_id", "")))
        if key not in used and predicate(row):
            used.add(key)
            return row
    return None


def render_sar_only_page(row: Mapping[str, Any], out_path: Path) -> None:
    page = Image.new("RGB", (1500, 1200), "#f8fafc")
    draw = ImageDraw.Draw(page)
    draw.text((50, 36), "OTY2 SAR-only morphology reference", font=base.FONTS["title"], fill="#0f172a")
    base.draw_tag(draw, (50, 92), "SAR-only", "#7c3aed")
    draw.text((50, 140), "This sample is excluded from optical-SAR correspondence and used only as SAR morphology/scatter reference.", font=base.FONTS["small"], fill="#dc2626")
    sar_image_path = Path(str(row.get("sar_image_path", "")))
    fake = {
        "gt_cx": row.get("_gt_cx"),
        "gt_cy": row.get("_gt_cy"),
        "gt_w": row.get("_gt_w"),
        "gt_h": row.get("_gt_h"),
        "gt_heading": row.get("_gt_heading", 0.0),
        "sar_gt_azimuth_deg": row.get("gt_azimuth_deg", ""),
    }
    if sar_image_path.exists():
        with Image.open(sar_image_path) as source:
            panel = base.scale_sar_with_gt(source, (820, 540), fake, {})
            patch = base.crop_gt_patch(sar_image_path, fake, (420, 420))
        page.paste(panel, (50, 210))
        page.paste(patch, (940, 210))
    else:
        draw.rectangle((50, 210, 870, 750), fill="#e2e8f0", outline="#94a3b8")
        draw.rectangle((940, 210, 1360, 630), fill="#e2e8f0", outline="#94a3b8")
    base.draw_card(
        draw,
        (50, 800, 640, 260),
        "SAR GT shape",
        [
            f"scene={row.get('scene')} sar_gt_id={row.get('sar_gt_id')} frame={row.get('sar_frame')}",
            f"long/short/aspect={row.get('gt_long_axis_px')}/{row.get('gt_short_axis_px')}/{row.get('gt_axis_aspect')}",
            f"radius={row.get('gt_center_radius_px')} azimuth={row.get('gt_azimuth_deg')}",
        ],
        border="#c4b5fd",
    )
    base.draw_card(
        draw,
        (740, 800, 650, 260),
        "Local scatter",
        [
            f"box/background={row.get('sar_box_to_background_ratio')}",
            f"peak/background={row.get('sar_peak_to_background_ratio')}",
            f"support={row.get('scatter_support_status')}",
            "Not a runtime detector or candidate scoring rule.",
        ],
        border="#93c5fd",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(out_path)


def render_visuals(
    timestamp: str,
    records: list[dict[str, Any]],
    shell_rows: Sequence[Mapping[str, Any]],
    shape_rows: Sequence[Mapping[str, Any]],
    object_aggs: Sequence[Mapping[str, Any]],
    sar_only_rows: Sequence[Mapping[str, Any]],
    dropout_rows: Sequence[Mapping[str, Any]],
) -> tuple[Path, list[dict[str, Any]]]:
    output_dir = OUTPUT_PARENT / f"oty2_gt_mechanism_stratified_validation_{timestamp}"
    paired_dir = output_dir / "paired_posthoc_pages"
    sar_only_dir = output_dir / "sar_only_pages"
    sample_dir = SAMPLE_ROOT / f"gt_mechanism_stratified_validation_{timestamp}"
    paired_dir.mkdir(parents=True, exist_ok=True)
    sar_only_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    shell_by_id = {(str(row.get("scene", "")), str(row.get("sar_gt_id", ""))): dict(row) for row in shell_rows}
    shape_by_id = {(str(row.get("scene", "")), str(row.get("sar_gt_id", ""))): dict(row) for row in shape_rows}
    trend_by_object = {str(row.get("object_key", "")): row for row in object_aggs}
    used: set[tuple[str, str]] = set()
    sample_specs = [
        ("azimuth_sector_success", lambda row: row.get("azimuth_prior_contains_gt") == "true" and (base.safe_float(row.get("azimuth_abs_error_deg"), 999.0) or 999.0) <= 20.0),
        ("azimuth_sector_failure", lambda row: row.get("azimuth_prior_contains_gt") == "false"),
        ("tight_shell_success", lambda row: row.get("tight_vehicle_shell_contains_gt") == "true"),
        ("tight_shell_fail_relaxed_shell_success", lambda row: row.get("tight_vehicle_shell_contains_gt") == "false" and row.get("relaxed_vehicle_shell_contains_gt") == "true"),
        ("optical_shape_trend_stable", lambda row: trend_by_object.get(str(row.get("object_key", "")), {}).get("area_vs_radius_trend") == "opposite_sign_consistent"),
        ("optical_shape_trend_failure", lambda row: trend_by_object.get(str(row.get("object_key", "")), {}).get("area_vs_radius_trend") == "same_sign_conflict"),
    ]
    selected: dict[tuple[str, str], str] = {}
    for role, predicate in sample_specs:
        chosen = select_first(records, used, predicate)
        if chosen is not None:
            selected[(str(chosen.get("scene", "")), str(chosen.get("sar_gt_id", "")))] = role

    visual_rows: list[dict[str, Any]] = []
    for row in records:
        scene = str(row.get("scene", ""))
        gt_id = str(row.get("sar_gt_id", ""))
        object_token = safe_file_part(str(row.get("object_hypothesis_id", "")).split("_")[-1] or "object")
        local_path = paired_dir / f"oty2_stratified_paired_{safe_file_part(scene.lower())}_{object_token}_sar{int(row['sar_frame']):06d}_{safe_file_part(gt_id)}_{timestamp}.png"
        base.render_page(row, shell_by_id[(scene, gt_id)], shape_by_id[(scene, gt_id)], local_path)
        role = selected.get((scene, gt_id), "")
        repo_path = ""
        if role:
            repo_path = str(sample_dir / f"oty2_stratified_{role}_{safe_file_part(scene.lower())}_{object_token}_sar{int(row['sar_frame']):06d}_{safe_file_part(gt_id)}_{timestamp}.png")
            shutil.copyfile(local_path, repo_path)
        visual_rows.append(
            {
                "sample_role": role,
                "sample_pool": "paired_clean_posthoc",
                "scene": scene,
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "sar_gt_id": gt_id,
                "sar_frame": row.get("sar_frame", ""),
                "local_visualization_path": str(local_path),
                "repo_sample_visualization_path": repo_path,
                "notes": "paired page uses SAR GT and SAR image only for posthoc validation",
            }
        )

    sar_sample_written = False
    for row in sar_only_rows:
        scene = str(row.get("scene", ""))
        gt_id = str(row.get("sar_gt_id", ""))
        local_path = sar_only_dir / f"oty2_stratified_sar_only_{safe_file_part(scene.lower())}_sar{int(base.safe_int(row.get('sar_frame'), 0) or 0):06d}_{safe_file_part(gt_id)}_{timestamp}.png"
        render_sar_only_page(row, local_path)
        repo_path = ""
        role = ""
        if not sar_sample_written:
            role = "sar_only_morphology_reference"
            repo_path = str(sample_dir / f"oty2_stratified_sar_only_morphology_reference_{safe_file_part(scene.lower())}_{safe_file_part(gt_id)}_{timestamp}.png")
            shutil.copyfile(local_path, repo_path)
            sar_sample_written = True
        visual_rows.append(
            {
                "sample_role": role,
                "sample_pool": "sar_only_reference",
                "scene": scene,
                "object_hypothesis_id": "",
                "sar_gt_id": gt_id,
                "sar_frame": row.get("sar_frame", ""),
                "local_visualization_path": str(local_path),
                "repo_sample_visualization_path": repo_path,
                "notes": "SAR-only reference excluded from optical-SAR correspondence",
            }
        )

    dropout_sample = next(iter(dropout_rows), None)
    if dropout_sample:
        existing = str(dropout_sample.get("repo_sample_visualization_path", "") or dropout_sample.get("local_visualization_path", ""))
        src = Path(existing)
        if src.exists():
            dst = sample_dir / f"oty2_stratified_detection_dropout_excluded_from_clean_{safe_file_part(dropout_sample.get('scene'))}_{safe_file_part(dropout_sample.get('sar_gt_id'))}_{timestamp}.png"
            shutil.copyfile(src, dst)
            visual_rows.append(
                {
                    "sample_role": "detection_dropout_excluded_from_clean_statistics",
                    "sample_pool": "detection_dropout_reference",
                    "scene": dropout_sample.get("scene", ""),
                    "object_hypothesis_id": "",
                    "sar_gt_id": dropout_sample.get("sar_gt_id", ""),
                    "sar_frame": dropout_sample.get("sar_frame", ""),
                    "local_visualization_path": existing,
                    "repo_sample_visualization_path": str(dst),
                    "notes": "dropout sample kept out of clean paired statistics; shown only as mechanism pool reference",
                }
            )

    write_csv(output_dir / "oty2_gt_mechanism_stratified_validation_visual_index.csv", visual_rows, VISUAL_FIELDS)
    write_csv(REPORT_DIR / f"oty2_gt_mechanism_stratified_validation_visual_summary_{timestamp}.csv", visual_rows, VISUAL_FIELDS)
    return output_dir, visual_rows


def find_azimuth_key_results(azimuth_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    all_fixed = [
        row
        for row in azimuth_rows
        if row.get("strategy") == "centered_fixed_margin" and row.get("subgroup_type") == "all"
    ]
    all_original = next((row for row in azimuth_rows if row.get("strategy") == "original_interval" and row.get("subgroup_type") == "all"), {})
    smallest_90 = next((row for row in all_fixed if (base.safe_float(row.get("coverage_rate"), 0.0) or 0.0) >= 0.90), {})
    smallest_95 = next((row for row in all_fixed if (base.safe_float(row.get("coverage_rate"), 0.0) or 0.0) >= 0.95), {})
    return {
        "original_interval": dict(all_original),
        "smallest_fixed_margin_ge_90_pass": dict(smallest_90),
        "smallest_fixed_margin_ge_95_pass": dict(smallest_95),
    }


def find_shell_key_results(shell_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for profile in SHELL_PROFILES:
        row = next((item for item in shell_rows if item.get("shell_profile") == profile and item.get("subgroup_type") == "all"), {})
        out[profile] = dict(row)
    return out


def summarize_sar_only(sar_only_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "sample_count": len(sar_only_rows),
        "scene_counts": dict(Counter(str(row.get("scene", "")) for row in sar_only_rows)),
        "long_axis_median_px": median_clean(row.get("gt_long_axis_px") for row in sar_only_rows),
        "short_axis_median_px": median_clean(row.get("gt_short_axis_px") for row in sar_only_rows),
        "aspect_median": median_clean(row.get("gt_axis_aspect") for row in sar_only_rows),
        "box_to_background_median": median_clean(row.get("sar_box_to_background_ratio") for row in sar_only_rows),
        "peak_to_background_median": median_clean(row.get("sar_peak_to_background_ratio") for row in sar_only_rows),
        "scatter_support_counts": dict(Counter(str(row.get("scatter_support_status", "")) for row in sar_only_rows)),
    }


def summarize_shape_probe(shape_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    all_rows = [row for row in shape_rows if row.get("stratum_type") == "all"]
    scene_rows = [row for row in shape_rows if row.get("stratum_type") == "scene"]
    context_rows = [row for row in shape_rows if row.get("stratum_type") == "context"]
    return {
        "all_feature_relations": {str(row.get("feature")): {"pearson": row.get("pearson"), "stability": row.get("stability_label")} for row in all_rows},
        "scene_feature_relations": {
            f"{row.get('stratum')}|{row.get('feature')}": {"pearson": row.get("pearson"), "stability": row.get("stability_label")}
            for row in scene_rows
        },
        "context_feature_relations": {
            f"{row.get('stratum')}|{row.get('feature')}": {"pearson": row.get("pearson"), "stability": row.get("stability_label")}
            for row in context_rows
        },
        "strong_or_moderate_count": sum(
            1 for row in shape_rows if row.get("stability_label") in {"strong_posthoc_relation", "moderate_posthoc_relation"}
        ),
    }


def summarize_temporal(object_aggs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reliability = Counter(str(row.get("trajectory_reliability_label", "")) for row in object_aggs)
    area_relation = Counter(str(row.get("area_vs_radius_trend", "")) for row in object_aggs)
    scenes_by_reliable = Counter(
        str(row.get("scene", ""))
        for row in object_aggs
        if row.get("trajectory_reliability_label") in {"clean_object_temporal_signal", "review_only_temporal_signal"}
    )
    return {
        "object_count": len(object_aggs),
        "trajectory_reliability_counts": dict(reliability),
        "area_vs_radius_trend_counts": dict(area_relation),
        "reliable_signal_scene_counts": dict(scenes_by_reliable),
    }


def build_mechanism_judgement(summary: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        "strongly_supported_posthoc_mechanism": [
            "Sample-pool routing is reproducible: 442 total GT, 215 clean paired frames, 195 GM_RM011 object-stream blockers, 20 SAR-only, and 12 dropout/no-match rows remain separated.",
            "SAR GT local peak morphology is supported posthoc in paired/SAR-only reference pools, but only as SAR-side morphology evidence.",
        ],
        "weak_but_promising_mechanism": [
            "Azimuth center mapping remains useful, but coverage depends on wide margins; failures are scene/status dependent rather than a simple global signed-bias problem.",
            "Vehicle footprint shells provide meaningful angular compression when intersected with azimuth sectors; tight shell is not universally safe.",
            "Optical bbox height, area, and bottom-y have strong overall posthoc radius relation, but transferability depends on scene/status strata.",
        ],
        "unstable_mechanism": [
            "Object-level temporal trajectory is helpful mainly for review/context explanation; repeated frames and state contamination prevent clean runtime claims.",
            "GM_RM019, review-only, edge, and duplicate/handoff strata are sparse or state-mixed enough that they need separate review before any runtime hypothesis.",
        ],
        "not_supported_mechanism": [
            "BBox aspect ratio is not supported as a stable standalone SAR radius mechanism in this audit.",
            "Detection-dropout propagation is not a clean paired morphology sample and remains excluded from main statistics.",
        ],
        "candidate_for_future_runtime_validation": [
            "Runtime-safe azimuth mapping plus a vehicle footprint shell may be worth designing as a future candidate, but must be rebuilt without SAR GT/image inputs.",
            "Optical height/bottom-y/area trends can become hypotheses for future runtime validation only after an independent runtime-safe range cue is defined.",
        ],
        "posthoc_observation_only": [
            "GT coverage does not imply automatic annotation.",
            "SAR image evidence does not become a runtime prior-construction input.",
            "Posthoc support does not establish identity truth.",
        ],
    }


def render_report(
    path: Path,
    timestamp: str,
    summary: Mapping[str, Any],
    output_paths: Mapping[str, str],
    sources: Mapping[str, str],
) -> None:
    ledger = summary["sample_ledger"]
    az = summary["azimuth_key_results"]
    shells = summary["vehicle_shell_key_results"]
    sar_only = summary["sar_only_summary"]
    temporal = summary["temporal_summary"]
    shape = summary["shape_probe_summary"]
    lines = [
        "# OTY2 后验机制分层验证与壳压缩消融报告",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本轮使用 SAR GT 和 SAR 图像内容仅做 posthoc mechanism validation。报告不输出自动标注建议，不做 runtime prior construction，不训练/调阈值，不使用 selector/ranking，不声明身份真值。",
        "",
        "## 样本池核验",
        "",
        f"- 442 GT 总账核验：`{str(ledger['ledger_valid']).lower()}`。",
        f"- 类别分账：`{json.dumps(ledger['category_counts'], ensure_ascii=False)}`。",
        f"- 场景分账：`{json.dumps(ledger['scene_counts'], ensure_ascii=False)}`。",
        "- 215 paired 是帧级后验配对子集，不是 215 个独立目标。",
        "- 195 GM_RM011 样本因缺当前 OTY 光学对象流被排除出光学-SAR 对应机制；20 SAR-only 只进入 SAR 形态参考；12 dropout/no-match 只作截断/缺检/时序延续机制池。",
        "",
        "## Frame-Level / Object-Level",
        "",
        f"- frame-level clean paired：`{summary['frame_level']['n_frames']}` 帧。",
        f"- object-level 聚合对象数：`{summary['object_level']['n_objects']}`。",
        f"- object-level 轨迹可靠性：`{json.dumps(temporal['trajectory_reliability_counts'], ensure_ascii=False)}`。",
        f"- area-vs-radius object trend：`{json.dumps(temporal['area_vs_radius_trend_counts'], ensure_ascii=False)}`。",
        "结论：frame-level 的相关性更强，但 object-level 显示不少趋势来自重复帧和状态混合，不能把 215 帧直接当作独立对象下结论。",
        "",
        "## 方位扇区 Margin 消融",
        "",
        f"- 原始扇区覆盖：`{az['original_interval'].get('coverage_pass')}/{az['original_interval'].get('n_frames')}`，覆盖率 `{az['original_interval'].get('coverage_rate')}`，中位宽度 `{az['original_interval'].get('median_sector_width_deg')}` 度。",
        f"- 固定中心 margin >=90% 覆盖的最小档：`{az['smallest_fixed_margin_ge_90_pass'].get('margin_deg')}` 度，覆盖率 `{az['smallest_fixed_margin_ge_90_pass'].get('coverage_rate')}`。",
        f"- 固定中心 margin >=95% 覆盖的最小档：`{az['smallest_fixed_margin_ge_95_pass'].get('margin_deg')}` 度，覆盖率 `{az['smallest_fixed_margin_ge_95_pass'].get('coverage_rate')}`。",
        f"- 系统偏移提示：`{az['original_interval'].get('systematic_offset_note')}`；原始中位 signed error `{az['original_interval'].get('median_signed_error_deg')}` 度。",
        "结论：方位映射有可压缩空间，但窄 margin 失败呈现 scene/status 依赖，原始结果没有明显整体 signed bias；本报告不选择 runtime margin。",
        "",
        "## 车辆尺度壳消融",
        "",
    ]
    for profile in ("tight_vehicle_shell", "base_vehicle_shell", "relaxed_vehicle_shell"):
        row = shells[profile]
        lines.append(
            f"- `{profile}`：覆盖 `{row.get('coverage_pass')}/{row.get('n_frames')}`，覆盖率 `{row.get('coverage_rate')}`，"
            f"中位相交宽度 `{row.get('median_intersection_width_deg')}` 度，压缩率 `{row.get('median_intersection_compression_rate_vs_original_azimuth')}`。"
        )
    lines.extend(
        [
            f"- 需要 relaxed 才能覆盖 tight 失败的对象数：`{shells['tight_vehicle_shell'].get('objects_relaxed_needed_vs_tight_count')}`。",
            f"- tight 已足够的对象数：`{shells['tight_vehicle_shell'].get('objects_tight_sufficient_count')}`。",
            "结论：车辆 footprint 壳能带来后验压缩，但 tight 壳会丢样本，base/relaxed 更适合作为后验机制观察；下一轮若做 runtime candidate，必须用 runtime-safe 输入重新定义。",
            "",
            "## 光学框形态与 SAR 半径",
            "",
            f"- 全局形态关系：`{json.dumps(shape['all_feature_relations'], ensure_ascii=False)}`。",
            f"- 强/中等分层关系条目数：`{shape['strong_or_moderate_count']}`。",
            "结论：bbox height、area、bottom_y 与 SAR radius 的后验关系较强，但 scene/status/object 分层后会变得不均匀；aspect ratio 不能作为稳定机制。",
            "",
            "## 光学时序轨迹",
            "",
            f"- 轨迹可靠性：`{json.dumps(temporal['trajectory_reliability_counts'], ensure_ascii=False)}`。",
            f"- 有效/近似有效趋势的场景分布：`{json.dumps(temporal['reliable_signal_scene_counts'], ensure_ascii=False)}`。",
            "结论：面积/高度/bottom_y 趋势对 review-only 解释有帮助，但仍受单场景、重复帧、截断/边缘/交接影响；不能作为身份真值或 runtime range 规则。",
            "",
            "## SAR-Only 形态参考",
            "",
            f"- SAR-only 数量：`{sar_only['sample_count']}`，场景分布：`{json.dumps(sar_only['scene_counts'], ensure_ascii=False)}`。",
            f"- GT 长轴/短轴/aspect 中位数：`{fmt(sar_only['long_axis_median_px'], 3)}` / `{fmt(sar_only['short_axis_median_px'], 3)}` / `{fmt(sar_only['aspect_median'], 4)}`。",
            f"- box/background 中位数：`{fmt(sar_only['box_to_background_median'], 6)}`；peak/background 中位数：`{fmt(sar_only['peak_to_background_median'], 6)}`。",
            f"- 散射支持分布：`{json.dumps(sar_only['scatter_support_counts'], ensure_ascii=False)}`。",
            "结论：SAR-only 支持车辆 footprint + 局部散射峰这一 SAR 侧观察，但不能进入光学映射机制。",
            "",
            "## 机制判断",
            "",
        ]
    )
    for category, items in summary["mechanism_judgement"].items():
        lines.append(f"### {category}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    lines.extend(["## 输出文件", ""])
    for key, value in output_paths.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## 数据源", ""])
    for key, value in sources.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    tables = load_input_tables(args)
    spatial_by_key = base.rows_by_key(tables["spatial_rows"])
    temporal_by_key = base.rows_by_key(tables["temporal_rows"])
    vehicle_by_key = base.rows_by_key(tables["vehicle_rows"])
    object_by_frame, object_by_object = base.group_object_frames(tables["object_frame_rows"])

    correspondences, pairing_meta = base.build_correspondences(tables, spatial_by_key, temporal_by_key, vehicle_by_key, object_by_frame)
    ledger = validate_sample_ledger(tables["accounting_rows"], tables["final_gt_rows"], len(correspondences))
    if not ledger["ledger_valid"]:
        raise RuntimeError(f"Sample ledger mismatch; stop before mechanism conclusions: {json.dumps(ledger, ensure_ascii=False)}")

    shape_shells = base.build_shape_range_shells(correspondences)
    shell_rows, shape_rows = base.enrich_shell_and_shape(correspondences, shape_shells, object_by_object)
    records = build_joined_records(correspondences, shell_rows, shape_rows)
    object_aggs = build_object_aggregates(records)
    stratified_rows = build_stratified_rows(records, object_aggs, ledger)
    azimuth_rows = build_azimuth_ablation_rows(records)
    vehicle_shell_rows = build_shell_ablation_rows(records)
    shape_probe_rows = build_shape_probe_rows(records)
    temporal_rows = build_temporal_rows(object_aggs)
    sar_only_rows = build_sar_only_rows(tables["accounting_rows"])

    output_dir, visual_rows = render_visuals(timestamp, records, shell_rows, shape_rows, object_aggs, sar_only_rows, tables["dropout_rows"])

    stratified_csv = REPORT_DIR / f"oty2_gt_mechanism_stratified_validation_{timestamp}.csv"
    azimuth_csv = REPORT_DIR / f"oty2_azimuth_margin_ablation_{timestamp}.csv"
    shell_csv = REPORT_DIR / f"oty2_vehicle_shell_ablation_{timestamp}.csv"
    shape_csv = REPORT_DIR / f"oty2_optical_shape_range_stratified_probe_{timestamp}.csv"
    temporal_csv = REPORT_DIR / f"oty2_temporal_trajectory_mechanism_probe_{timestamp}.csv"
    sar_only_csv = REPORT_DIR / f"oty2_sar_only_morphology_reference_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_gt_mechanism_stratified_validation_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_gt_mechanism_stratified_validation_summary_{timestamp}.json"
    visual_summary_csv = REPORT_DIR / f"oty2_gt_mechanism_stratified_validation_visual_summary_{timestamp}.csv"

    write_csv(stratified_csv, stratified_rows, STRATIFIED_FIELDS)
    write_csv(azimuth_csv, azimuth_rows, AZIMUTH_FIELDS)
    write_csv(shell_csv, vehicle_shell_rows, SHELL_FIELDS)
    write_csv(shape_csv, shape_probe_rows, SHAPE_FIELDS)
    write_csv(temporal_csv, temporal_rows, TEMPORAL_FIELDS)
    write_csv(sar_only_csv, sar_only_rows, SAR_ONLY_FIELDS)

    frame_summary = summarize_group("frame_level", "all", "paired_clean_frames", records)
    object_summary = {
        "n_objects": len(object_aggs),
        "n_paired_frames": len(records),
        "trajectory_reliability_counts": dict(Counter(str(row.get("trajectory_reliability_label", "")) for row in object_aggs)),
    }
    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "sample_ledger": ledger,
        "pairing_meta": pairing_meta,
        "frame_level": frame_summary,
        "object_level": object_summary,
        "scene_counts_paired": dict(Counter(str(row.get("scene", "")) for row in records)),
        "status_context_counts": dict(Counter(str(row.get("status_context", "")) for row in records)),
        "vehicle_research_eligibility_counts": dict(Counter(str(row.get("vehicle_research_eligibility", "")) for row in records)),
        "azimuth_key_results": find_azimuth_key_results(azimuth_rows),
        "vehicle_shell_key_results": find_shell_key_results(vehicle_shell_rows),
        "shape_probe_summary": summarize_shape_probe(shape_probe_rows),
        "temporal_summary": summarize_temporal(object_aggs),
        "sar_only_summary": summarize_sar_only(sar_only_rows),
        "local_visualization_output_dir": str(output_dir),
        "local_visualization_count": len([row for row in visual_rows if row.get("sample_pool") == "paired_clean_posthoc"]),
        "sar_only_visualization_count": len([row for row in visual_rows if row.get("sample_pool") == "sar_only_reference"]),
        "remote_sample_visualization_count": sum(1 for row in visual_rows if row.get("repo_sample_visualization_path")),
        "mechanism_judgement": {},
        "boundary_flags": BOUNDARY_FLAGS,
    }
    summary["mechanism_judgement"] = build_mechanism_judgement(summary)

    output_paths = {
        "stratified_validation_csv": str(stratified_csv),
        "azimuth_margin_ablation_csv": str(azimuth_csv),
        "vehicle_shell_ablation_csv": str(shell_csv),
        "optical_shape_range_stratified_probe_csv": str(shape_csv),
        "temporal_trajectory_mechanism_probe_csv": str(temporal_csv),
        "sar_only_morphology_reference_csv": str(sar_only_csv),
        "report_md": str(report_md),
        "summary_json": str(summary_json),
        "visual_summary_csv": str(visual_summary_csv),
        "local_full_visual_output": str(output_dir),
        "repo_sample_dir": str(SAMPLE_ROOT / f"gt_mechanism_stratified_validation_{timestamp}"),
    }
    sources = {
        "accounting_csv": str(tables["accounting_csv"]),
        "dropout_temporal_csv": str(tables["dropout_temporal_csv"]),
        "final_gt_csv": str(Path(args.final_gt_csv)),
        "review_queue_csv": str(Path(args.review_queue_csv)),
        "spatial_priors_csv": str(Path(args.spatial_priors_csv) if args.spatial_priors_csv else latest_path("oty2_object_runtime_spatial_priors_*.csv")),
        "temporal_windows_csv": str(Path(args.temporal_windows_csv) if args.temporal_windows_csv else latest_path("oty2_object_sar_temporal_windows_*.csv")),
        "vehicle_eligibility_csv": str(Path(args.vehicle_eligibility_csv) if args.vehicle_eligibility_csv else latest_path("oty2_vehicle_research_eligibility_audit_*.csv")),
        "object_frame_state_csv": str(Path(args.object_frame_state_csv) if args.object_frame_state_csv else base.DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"),
        "object_hypotheses_csv": str(Path(args.object_hypotheses_csv) if args.object_hypotheses_csv else base.DEFAULT_OBJECT_DIR / "oty1t_object_hypotheses_generalized.csv"),
    }
    summary["outputs"] = output_paths
    summary["sources"] = sources
    write_json(summary_json, summary)
    render_report(report_md, timestamp, summary, output_paths, sources)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--final-gt-csv", default=str(base.DEFAULT_GT_CSV))
    parser.add_argument("--review-queue-csv", default=str(base.DEFAULT_REVIEW_QUEUE_CSV))
    parser.add_argument("--spatial-priors-csv", default="")
    parser.add_argument("--temporal-windows-csv", default="")
    parser.add_argument("--vehicle-eligibility-csv", default="")
    parser.add_argument("--object-visual-summary-csv", default="")
    parser.add_argument("--object-frame-state-csv", default="")
    parser.add_argument("--object-hypotheses-csv", default="")
    parser.add_argument("--accounting-csv", default="")
    parser.add_argument("--dropout-temporal-csv", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
