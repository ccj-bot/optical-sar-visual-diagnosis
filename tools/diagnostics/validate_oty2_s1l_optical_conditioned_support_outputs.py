#!/usr/bin/env python3
"""Validate the bounded S1-L optical-conditioned support observability audit."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
OUTPUT_ROOT = Path(
    r"D:\profile\research\workspace\output\oty2_s1l_optical_conditioned_support_observability_20260716"
)
VISUAL_ROOT = OUTPUT_ROOT / "visual_casebook"
SUMMARY_PATH = OUTPUT_ROOT / "optical_conditioned_support_observability_summary.json"
REPLAY_PATH = OUTPUT_ROOT / "optical_conditioned_support_replay_check.json"

BASE_HEAD = "75eed68a19c94428c27d8a217d3dab36c56f20d6"
EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
DEVELOPMENT_SEGMENT = "S0MV-GM_RM017-PV002-SEG02"

UNIT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_research_units.csv"
SAMPLING_PATH = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_sampling_normalization_audit.csv"
)
REPRESENTATION_PATH = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_representation_metrics.csv"
)
PAIR_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_pair_incremental_metrics.csv"
SENSITIVITY_PATH = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_pair_and_frame_sensitivity.csv"
)
PROFILE_PATH = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_parameter_metric_profiles.csv"
)
OBSERVABILITY_PATH = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_parameter_observability.csv"
)
VISUAL_MANIFEST_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_visual_manifest.csv"
VISUAL_REVIEW_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_visual_reviews.csv"
STAGE_CONCLUSION_PATH = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_stage_conclusions.csv"
)
FINAL_REPORT_PATH = (
    REPORT_DIR / "oty2_s1l_optical_conditioned_support_observability_20260716.md"
)

GENERATED_CSV_PATHS = (
    UNIT_PATH,
    SAMPLING_PATH,
    REPRESENTATION_PATH,
    PAIR_PATH,
    SENSITIVITY_PATH,
    PROFILE_PATH,
    OBSERVABILITY_PATH,
    VISUAL_MANIFEST_PATH,
)
FORMAL_CSV_PATHS = (*GENERATED_CSV_PATHS, VISUAL_REVIEW_PATH, STAGE_CONCLUSION_PATH)

ALLOWED_PATHS = {
    "docs/OTY2_S1L_SEMANTIC_CORRECTION_AND_OPTICAL_CONDITIONED_SUPPORT_OBSERVABILITY_PROTOCOL.md",
    "reports/oty2/oty2_s1l_semantic_correction_and_implementation_audit_20260716.md",
    "reports/oty2/oty2_s1l_optical_conditioned_support_observability_20260716.md",
    "tools/diagnostics/run_oty2_s1l_optical_conditioned_support_observability.py",
    "tools/diagnostics/run_oty2_s1l_optical_conditioned_support_replay_check.py",
    "tools/diagnostics/validate_oty2_s1l_optical_conditioned_support_outputs.py",
    "manifests/oty2/oty2_s1l_optical_conditioned_research_units.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_sampling_normalization_audit.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_representation_metrics.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_pair_incremental_metrics.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_pair_and_frame_sensitivity.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_parameter_metric_profiles.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_parameter_observability.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_visual_manifest.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_visual_reviews.csv",
    "manifests/oty2/oty2_s1l_optical_conditioned_stage_conclusions.csv",
}

REPRESENTATIONS = {
    "WORLD_FIXED",
    "CENTER_TRACKED_CARTESIAN",
    "CENTER_TRACKED_RADIAL",
    "CENTER_TRACKED_BODY",
}
NORMALIZATION_PATHS = {"FIXED_REFERENCE", "CANDIDATE_LOCAL_REESTIMATED"}
ANCHOR_VARIANTS = {"raw_gt", "smoothed_gt"}
TEMPORAL_DIRECTION_APPLICABILITY = {
    "NOT_APPLICABLE_TO_TIME_REVERSAL",
    "NOT_EVALUATED_DIRECTION_INSENSITIVE_METRICS",
    "NOT_A_TEMPORAL_DIRECTION_TEST",
}
TEMPORAL_CORRESPONDENCE_APPLICABILITY = {
    "APPLICABLE_TO_TEMPORAL_CORRESPONDENCE_CONTROL",
    "NOT_A_TEMPORAL_CORRESPONDENCE_TEST",
}
AXIS_RULES = {
    "GT_DERIVED_UNSIGNED_BODY",
    "THREAD_FIXED_MEDIAN_AXIS",
    "FRAME_SHUFFLED_AXIS",
    "TIME_SHIFTED_AXIS",
    "GT_AXIS_PLUS_90",
    "TRAJECTORY_TANGENT_AXIS",
    "GLOBAL_FIXED_AXIS",
}
REPRESENTATION_COMPARISON_TRANSFORMS = {
    "TRANSLATION_COMPENSATION": ("WORLD_FIXED", "CENTER_TRACKED_CARTESIAN"),
    "RADIAL_AXIS_INCREMENT": (
        "CENTER_TRACKED_CARTESIAN",
        "CENTER_TRACKED_RADIAL",
    ),
    "GT_BODY_ORIENTED_WINDOW_VS_CARTESIAN": (
        "CENTER_TRACKED_CARTESIAN",
        "CENTER_TRACKED_BODY",
    ),
    "GT_BODY_ORIENTED_WINDOW_VS_RADIAL": (
        "CENTER_TRACKED_RADIAL",
        "CENTER_TRACKED_BODY",
    ),
}
REPRESENTATION_COMPARISONS = set(REPRESENTATION_COMPARISON_TRANSFORMS)
AXIS_COMPARISONS = {
    f"GT_ORIENTED_WINDOW_RULE_VS_{axis_rule}"
    for axis_rule in AXIS_RULES - {"GT_DERIVED_UNSIGNED_BODY"}
}
PAIR_SUBMETRICS = {
    "FIELD_NCC": (
        "CONTINUOUS_GRAYSCALE_FIELD",
        "HIGHER_IS_BETTER",
        "NORMALIZED_8BIT_FIELD_NCC",
    ),
    "ORIENTATION_PAIR_AGREEMENT": (
        "LOCAL_ORIENTATION_ORGANIZATION",
        "HIGHER_IS_BETTER",
        "STRUCTURE_TENSOR_ORIENTATION_PROXY",
    ),
    "ORIENTATION_ANGLE_DIFF_DEG": (
        "LOCAL_ORIENTATION_ORGANIZATION",
        "LOWER_IS_BETTER",
        "STRUCTURE_TENSOR_ORIENTATION_PROXY",
    ),
    "THIN_EDGE_JACCARD": (
        "SPATIAL_RELATION_TOPOLOGY",
        "HIGHER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_ENDPOINT_COUNT_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_BRANCH_COUNT_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_KEYPOINT_RELATION_DISTANCE_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_CENTROID_DISTANCE": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_ADJACENCY_MEAN_DEGREE_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_COLLINEARITY_PROXY_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_PARALLEL_REPRESENTATION_X_AXIS_FRACTION_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "THIN_EDGE_PARALLEL_REPRESENTATION_Y_AXIS_FRACTION_ABSDIFF": (
        "SPATIAL_RELATION_TOPOLOGY",
        "LOWER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
}
PROFILE_SUBMETRICS = {
    "ADJACENT_FIELD_NCC": (
        "CONTINUOUS_GRAYSCALE_FIELD",
        "HIGHER_IS_BETTER",
        "NORMALIZED_8BIT_FIELD_NCC",
    ),
    "ADJACENT_ORIENTATION_AGREEMENT": (
        "LOCAL_ORIENTATION_ORGANIZATION",
        "HIGHER_IS_BETTER",
        "STRUCTURE_TENSOR_ORIENTATION_PROXY",
    ),
    "ADJACENT_THIN_EDGE_JACCARD": (
        "SPATIAL_RELATION_TOPOLOGY",
        "HIGHER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
    "BOUNDARY_MISSING_MEAN": (
        "SAMPLING_GEOMETRY",
        "LOWER_IS_BETTER",
        "IMAGING_VALID_BOUNDARY_FRACTION",
    ),
    "NONADJACENT_FIELD_NCC": (
        "CONTINUOUS_GRAYSCALE_FIELD",
        "HIGHER_IS_BETTER",
        "NORMALIZED_8BIT_FIELD_NCC",
    ),
    "NONADJACENT_ORIENTATION_AGREEMENT": (
        "LOCAL_ORIENTATION_ORGANIZATION",
        "HIGHER_IS_BETTER",
        "STRUCTURE_TENSOR_ORIENTATION_PROXY",
    ),
    "NONADJACENT_THIN_EDGE_JACCARD": (
        "SPATIAL_RELATION_TOPOLOGY",
        "HIGHER_IS_BETTER",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    ),
}
PARETO_BASIS = (
    "ADJACENT_FIELD_NCC",
    "ADJACENT_ORIENTATION_AGREEMENT",
    "ADJACENT_THIN_EDGE_JACCARD",
    "BOUNDARY_MISSING_MEAN",
)
GRID_NONDOMINANCE_PATTERNS = {
    "EMPTY",
    "ALL_GRID",
    "MULTICOMPONENT",
    "SINGLETON",
    "EDGE_CONTIGUOUS_SET",
    "INTERIOR_CONTIGUOUS_SET",
}
PAIR_RULE_ID = (
    "SOURCE_POSITIVE_GT_CONDITIONED_VIEW_GAP10_DIFF5_RELIABILITY_AND_FINITE_COMMON_VALID_"
    "PROJECTED_NO_RESELECTION"
)
PAIR_PROJECTION_RULE = "SOURCE_POSITIVE_PAIR_SET_FRAME_INTERSECTION_NO_RESELECTION"
PAIR_MEMBERSHIP_RULE = PAIR_PROJECTION_RULE
PAIR_MEMBERSHIP_REFERENCE = (
    "SOURCE_POSITIVE|CENTER_TRACKED_BODY|GT_DERIVED_UNSIGNED_BODY|"
    "FIXED_REFERENCE|FINITE_COMMON_VALID"
)
PAIR_SENSITIVITY_MODES = {"LEAVE_ONE_PAIR_OUT", "LEAVE_ONE_FRAME_OUT"}
DIRECT_RELIABILITY_SCOPE = "DIRECT_SOURCE_REGISTRATION_RELIABILITY"
COUNTERFACTUAL_RELIABILITY_SCOPE = (
    "SOURCE_POSITIVE_MEMBERSHIP_ONLY;"
    "COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED"
)
ANCHOR_VARIANT_CONTRACT = (
    "RAW_AND_SMOOTHED_SEPARATE_SOURCE_POSITIVE_PAIR_SETS_FOR_ALL_UNITS"
)
OPTICAL_CONDITION_EXECUTION_STATUS = "NOT_EXECUTED_GT_DISCOVERY_PROXY_ONLY"
OPTICAL_CONDITIONED_SUPPORT_READINESS = (
    "NOT_EVALUATED_WITH_REAL_OPTICAL_INPUT_GT_PROXY_ONLY"
)
EXPECTED_CONFIG_HASH = "a62d5f6bdb3c902f1651ee03e4bd2c30e5403fdb4ee53a03e0ee3899402e9113"
EXPECTED_CANNY_CONFIG = {
    "low_threshold": 40,
    "high_threshold": 100,
    "aperture_size": 3,
    "l2_gradient": True,
    "input_quantization": "NORMALIZED_SCORE_TO_UINT8",
}
EXPECTED_STRUCTURE_BOUNDARY_GUARD = {
    "invalid_fill": "CV2_TELEA_INPAINT",
    "inpaint_radius_px": 3.0,
    "valid_mask_erosion_px": 6,
}
STRUCTURE_BOUNDARY_GUARD_ID = "TELEA_INPAINT_INVALID_PLUS_ERODE_VALID_6PX"
NORMALIZATION_FAILURE_POLICY = "INVALID_EVIDENCE_NAN_EXCLUDED_FROM_PARETO"
BODY_ORIENTED_WINDOW_ATTRIBUTION = (
    "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT_NOT_PURE_BODY_AXIS"
)
PARAMETER_OBSERVABILITY_CONTRACT = (
    "GRID_NONDOMINANCE_DIAGNOSTIC_ONLY;ALL_FORMAL_OBSERVABILITY_STATES_"
    "NOT_IDENTIFIABLE;NO_PHYSICAL_BOUNDS"
)
SCALE_PROFILE_CONTRACT = "FIXED_256X128_WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED"
TEMPORAL_TEST_CONTRACT = "CORRESPONDENCE_CONTROLS_ONLY;NO_ARROW_OF_TIME_METRIC"
BACKGROUND_CLUSTER_SCOPE = (
    "BASELINE_EQUAL_SUPPORT_3_SPATIAL_CLUSTERS;STRICT_ONE_DIM_PARAMETER_ENVELOPE_"
    "2_CLUSTERS;NOT_STATISTICAL_INDEPENDENCE"
)
EXPECTED_BACKGROUND_SPATIAL_GROUPS = {
    "GM_RM017|SPATIAL_CLUSTER_1",
    "GM_RM017|SPATIAL_CLUSTER_2",
    "GM_RM017|SPATIAL_CLUSTER_3",
}
EXPECTED_BACKGROUND_PARAMETER_ENVELOPE_GROUPS = {
    "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
    "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_2",
}
EXPECTED_BACKGROUND_GROUP_ASSIGNMENTS = {
    "CLASS-NEGATIVE-S1L-BG-0010": (
        "GM_RM017|SPATIAL_CLUSTER_1",
        "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
    ),
    "CLASS-NEGATIVE-S1L-BG-0011": (
        "GM_RM017|SPATIAL_CLUSTER_1",
        "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
    ),
    "CLASS-NEGATIVE-S1L-BG-OCS-B3-SA35N": (
        "GM_RM017|SPATIAL_CLUSTER_2",
        "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_2",
    ),
    "CLASS-NEGATIVE-S1L-BG-OCS-B4-FX88": (
        "GM_RM017|SPATIAL_CLUSTER_3",
        "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
    ),
}
EXPECTED_BACKGROUND_SEMANTICS = {
    "CLASS-NEGATIVE-S1L-BG-0010": (
        "same_azimuth_neighbor",
        "MOVING_SAME_AZIMUTH_BACKGROUND",
        "FROZEN_USABLE_PROPOSAL;SAME_BASELINE_SPATIAL_CLUSTER_AS_BG0011",
    ),
    "CLASS-NEGATIVE-S1L-BG-0011": (
        "fixed_strong_linear_background",
        "FIXED_STRONG_LINEAR_SAME_CLUSTER_DIAGNOSTIC",
        "CONTROL_QUALITY_LIMITED;STRONG_LINE_ROLE;SAME_BASELINE_SPATIAL_CLUSTER_AS_BG0010",
    ),
    "CLASS-NEGATIVE-S1L-BG-OCS-B3-SA35N": (
        "hard_scatter_partial_complexity_match",
        "MOVING_HARD_SCATTER_PARTIAL_COMPLEXITY_BACKGROUND",
        "B3_HARD_CONSTRAINT_PASS;HARD_SCATTER_ROLE_SUPPORTED;VEHICLE_COMPLEXITY_MATCH_PARTIAL;USABLE_VEHICLE_CLASS_NEGATIVE_WITH_LIMITATIONS",
    ),
    "CLASS-NEGATIVE-S1L-BG-OCS-B4-FX88": (
        "fixed_anisotropic_speckle_not_strong_line",
        "FIXED_ANISOTROPIC_SPECKLE_CONTROL_NOT_STRONG_LINE",
        "B4_HARD_CONSTRAINT_PASS;FIXED_ANISOTROPIC_SPECKLE_ROLE;NOT_STRONG_LINE;BASELINE_SPATIALLY_DISJOINT;PARAMETER_ENVELOPE_CLUSTER_LIMITED",
    ),
}
THIN_EDGE_ESTIMATOR = (
    "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON"
)
OBSERVABILITY_EVIDENCE_FAMILY = (
    "SEPARATE_METRIC_GRID_NONDOMINANCE_DIAGNOSTIC"
)
OBSERVABILITY_ESTIMATOR_CONTRACT = (
    "FIELD_NCC;STRUCTURE_TENSOR_ORIENTATION_PROXY;"
    "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON;"
    "BOUNDARY_FRACTION"
)
PARAMETER_GRIDS = {
    "CENTER_RADIAL": {"-0.250000", "-0.125000", "0.000000", "0.125000", "0.250000"},
    "CENTER_TANGENTIAL": {"-0.250000", "-0.125000", "0.000000", "0.125000", "0.250000"},
    "LONG_SCALE": {"0.850000", "0.925000", "1.000000", "1.075000", "1.150000"},
    "SHORT_SCALE": {"0.850000", "0.925000", "1.000000", "1.075000", "1.150000"},
    "AXIS_UNSIGNED": {"-12.000000", "-6.000000", "0.000000", "6.000000", "12.000000"},
}
PARETO_BASIS_TEXT = ";".join(PARETO_BASIS)
UNIT_DUAL_NORMALIZATION_PATH = "DUAL_PATH_GRID_NONDOMINANCE_INTERSECTION"
CORE_AGGREGATE_NORMALIZATION_PATH = (
    "DUAL_PATH_AND_WITHIN_SCENE_OTHER_VEHICLE_GRID_INTERSECTION"
)
CONCLUSION_IDS = {
    "GT_CONDITIONED_BODY_ALIGNMENT",
    "BODY_AXIS_INCREMENTAL_VALUE",
    "VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND",
    "SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY",
    "CENTER_RADIAL_OBSERVABILITY",
    "CENTER_TANGENTIAL_OBSERVABILITY",
    "LONG_SCALE_OBSERVABILITY",
    "SHORT_SCALE_OBSERVABILITY",
    "AXIS_OBSERVABILITY",
    "OPTICAL_CONDITIONED_SUPPORT_READINESS",
}
CONCLUSION_STATUS_ALLOWED = {
    "GT_CONDITIONED_BODY_ALIGNMENT": {
        "SUPPORTED_GT_CONDITIONED_ONLY",
        "PARTIAL_GT_CONDITIONED_ONLY",
        "NORMALIZATION_DEPENDENT",
        "NOT_SUPPORTED",
        "NOT_EVALUABLE",
    },
    "BODY_AXIS_INCREMENTAL_VALUE": {
        "SUPPORTED",
        "PARTIAL",
        "PLACEBO_INDIFFERENT",
        "NORMALIZATION_DEPENDENT",
        "INSUFFICIENT_PAIR_EVIDENCE",
        "NOT_SUPPORTED",
    },
    "VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND": {
        "SUPPORTED",
        "PARTIAL",
        "NOT_SUPPORTED",
        "NOT_EVALUABLE",
    },
    "SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY": {
        "PARTIAL",
        "NOT_READY",
        "NOT_EVALUABLE",
    },
    "CENTER_RADIAL_OBSERVABILITY": {
        "NOT_IDENTIFIABLE",
    },
    "CENTER_TANGENTIAL_OBSERVABILITY": {
        "NOT_IDENTIFIABLE",
    },
    "LONG_SCALE_OBSERVABILITY": {
        "NOT_IDENTIFIABLE",
    },
    "SHORT_SCALE_OBSERVABILITY": {
        "NOT_IDENTIFIABLE",
    },
    "AXIS_OBSERVABILITY": {
        "NOT_IDENTIFIABLE",
    },
    "OPTICAL_CONDITIONED_SUPPORT_READINESS": {
        "NOT_READY",
    },
}
NORMALIZATION_STATE_ALLOWED = {
    "DIRECTIONALLY_COMPATIBLE",
    "PARTIAL_FEASIBLE_OVERLAP",
    "NORMALIZATION_DEPENDENT",
    "INVALID_LOCAL_NORMALIZATION_PRESENT",
    "MIXED_NORMALIZATION_EVIDENCE",
    "NOT_APPLICABLE",
}
PAIR_SENSITIVITY_STATE_ALLOWED = {
    "NO_ELIGIBLE_PAIRS",
    "ONE_PAIR_NOT_EVALUABLE",
    "SPARSE_PAIR_EVIDENCE",
    "PAIR_EVIDENCE_AVAILABLE_LOPO_DIRECTION_STABLE",
    "PAIR_EVIDENCE_AVAILABLE_LOPO_DIRECTION_UNSTABLE",
    "MIXED_PAIR_SENSITIVITY",
    "NOT_APPLICABLE",
}
VISUAL_DECISIONS_ALLOWED = {
    "POSITIVE_PATTERN_SUPPORTED",
    "POSITIVE_PATTERN_PARTIAL",
    "COUNTERFACTUAL_REPRODUCES",
    "COUNTERFACTUAL_DOES_NOT_REPRODUCE",
    "NORMALIZATION_DEPENDENT",
    "INSUFFICIENT_EVIDENCE",
    "GLOBAL_PAIR_AUDIT_ONLY",
}
FORBIDDEN_FIELD_FRAGMENTS = (
    "winner",
    "rank",
    "selector",
    "weighted",
    "composite",
    "gt_iou",
    "skeleton",
)
TEMPORARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".mp4",
    ".avi",
    ".npy",
    ".npz",
    ".zip",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if check and completed.returncode:
        fail(
            f"git {' '.join(args)} failed ({completed.returncode}): "
            f"{completed.stdout}{completed.stderr}"
        )
    return completed.stdout.strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        fail(f"missing required CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not fields:
        fail(f"CSV has no header: {path}")
    if not rows:
        fail(f"CSV has no data rows: {path}")
    return fields, rows


def require_columns(path: Path, fields: Sequence[str], required: Iterable[str]) -> None:
    missing = set(required) - set(fields)
    if missing:
        fail(f"{path.name} missing required columns: {sorted(missing)}")


def require_direct_review(rows: Sequence[Mapping[str, str]], label: str) -> None:
    incomplete = [
        row
        for row in rows
        if "review_status" in row
        and row["review_status"] != "directly_reviewed_complete"
    ]
    if incomplete:
        fail(f"{label} contains rows not directly reviewed: {len(incomplete)}")


def require_false(value: Any, label: str) -> None:
    if isinstance(value, bool):
        is_false = value is False
    else:
        is_false = str(value).strip().lower() == "false"
    if not is_false:
        fail(f"{label} must be false, got {value!r}")


def finite_float(value: str, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        fail(f"{label} must be numeric: {value!r} ({exc})")
    if not math.isfinite(number):
        fail(f"{label} must be finite: {value!r}")
    return number


def integer_value(value: str, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        fail(f"{label} must be an integer: {value!r} ({exc})")
    return number


def parse_status_counts(value: str, label: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in filter(None, value.split(";")):
        if ":" not in item:
            fail(f"{label} has malformed normalization status counts: {value!r}")
        status, count_text = item.rsplit(":", 1)
        count = integer_value(count_text, label)
        if not status or count <= 0 or status in counts:
            fail(f"{label} has invalid normalization status count: {item!r}")
        counts[status] = count
    if not counts:
        fail(f"{label} has empty normalization status counts")
    return counts


def require_unit_semantics(
    rows: Sequence[Mapping[str, str]],
    units_by_id: Mapping[str, Mapping[str, str]],
    label: str,
    *,
    allow_core_aggregate: bool = False,
) -> None:
    for row in rows:
        unit_id = row["research_unit_id"]
        if allow_core_aggregate and unit_id == "GM_RM017_CORE_VEHICLES":
            if row.get("counterfactual_semantic_class") != "TRUE_VEHICLE_POSITIVE_AGGREGATE":
                fail(f"{label} core aggregate has wrong semantic class")
            continue
        unit = units_by_id.get(unit_id)
        if unit is None:
            fail(f"{label} references unknown research unit: {unit_id}")
        if row.get("counterfactual_semantic_class") != unit["counterfactual_semantic_class"]:
            fail(f"{label} semantic class mismatch for {unit_id}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_temporal_direction_applicability(
    unit: Mapping[str, str],
) -> str:
    if unit["transform_rule_id"] == "IMAGE_ORDER_REVERSED":
        return "NOT_APPLICABLE_TO_TIME_REVERSAL"
    if unit["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE":
        return "NOT_EVALUATED_DIRECTION_INSENSITIVE_METRICS"
    return "NOT_A_TEMPORAL_DIRECTION_TEST"


def expected_temporal_correspondence_applicability(
    unit: Mapping[str, str],
) -> str:
    if unit["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE":
        return "APPLICABLE_TO_TEMPORAL_CORRESPONDENCE_CONTROL"
    return "NOT_A_TEMPORAL_CORRESPONDENCE_TEST"


def validate_temporal_direction_applicability(
    rows: Sequence[Mapping[str, str]],
    units_by_id: Mapping[str, Mapping[str, str]],
    label: str,
    *,
    allow_core_aggregate: bool = False,
) -> None:
    for row in rows:
        value = row.get("temporal_direction_applicability", "")
        if value not in TEMPORAL_DIRECTION_APPLICABILITY:
            fail(f"{label} has invalid temporal-direction applicability: {value!r}")
        unit_id = row["research_unit_id"]
        unit = units_by_id.get(unit_id)
        if unit is None:
            if allow_core_aggregate and unit_id == "GM_RM017_CORE_VEHICLES":
                expected = "NOT_A_TEMPORAL_DIRECTION_TEST"
            else:
                fail(f"{label} references unknown research unit: {unit_id}")
        else:
            expected = expected_temporal_direction_applicability(unit)
        if value != expected:
            fail(
                f"{label} temporal-direction applicability mismatch for {unit_id}: "
                f"{value!r} vs {expected!r}"
            )
        correspondence = row.get("temporal_correspondence_applicability", "")
        if correspondence not in TEMPORAL_CORRESPONDENCE_APPLICABILITY:
            fail(
                f"{label} has invalid temporal-correspondence applicability: "
                f"{correspondence!r}"
            )
        if unit is None:
            expected_correspondence = "NOT_A_TEMPORAL_CORRESPONDENCE_TEST"
        else:
            expected_correspondence = expected_temporal_correspondence_applicability(unit)
        if correspondence != expected_correspondence:
            fail(
                f"{label} temporal-correspondence applicability mismatch for {unit_id}: "
                f"{correspondence!r} vs {expected_correspondence!r}"
            )


def expected_pair_state(count: int) -> str:
    if count == 0:
        return "NO_ELIGIBLE_PAIRS"
    if count <= 4:
        return "SPARSE_PAIR_EVIDENCE"
    return "PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE"


def expected_reliability_scope(unit: Mapping[str, str]) -> str:
    return (
        DIRECT_RELIABILITY_SCOPE
        if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
        else COUNTERFACTUAL_RELIABILITY_SCOPE
    )


def parameter_interpretation_limit(parameter_id: str) -> str:
    if parameter_id in {"LONG_SCALE", "SHORT_SCALE"}:
        return (
            "FIXED_256X128_GRID_COUPLES_SCALE_TO_RESAMPLING;"
            "NO_PHYSICAL_SCALE_IDENTIFICATION"
        )
    if parameter_id == "AXIS_UNSIGNED":
        return "GRID_NONDOMINANCE_PATTERN_ONLY;AXIS_PLACEBO_REVIEW_REQUIRED"
    return "GRID_NONDOMINANCE_PATTERN_ONLY;NO_CENTER_IDENTIFICATION_CRITERION"


def classify_grid_pattern(
    parameter_id: str,
    values: Iterable[str],
) -> tuple[str, int, bool, bool, str, str]:
    grid = sorted(float(value) for value in PARAMETER_GRIDS[parameter_id])
    unique = sorted({float(value) for value in values if str(value).strip()})
    if any(value not in grid for value in unique):
        fail(f"grid nondominance values leave the frozen grid for {parameter_id}: {unique}")
    if not unique:
        return "EMPTY", 0, False, False, "", ""
    indices = sorted(grid.index(value) for value in unique)
    components = 1 + sum(
        current != previous + 1
        for previous, current in zip(indices, indices[1:])
    )
    lower = indices[0] == 0
    upper = indices[-1] == len(grid) - 1
    if len(unique) == len(grid):
        pattern = "ALL_GRID"
    elif components > 1:
        pattern = "MULTICOMPONENT"
    elif len(unique) == 1:
        pattern = "SINGLETON"
    elif lower or upper:
        pattern = "EDGE_CONTIGUOUS_SET"
    else:
        pattern = "INTERIOR_CONTIGUOUS_SET"
    return (
        pattern,
        components,
        lower,
        upper,
        f"{unique[0]:.6f}",
        f"{unique[-1]:.6f}",
    )


def json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True).encode("utf-8")
    ).hexdigest()


def ensure_outside_repo(path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return
    fail(f"{label} is inside the Git worktree: {resolved}")


def validate_scope() -> set[str]:
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        fail(f"wrong branch; expected {EXPECTED_BRANCH}")
    git("cat-file", "-e", f"{BASE_HEAD}^{{commit}}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        fail(f"frozen base {BASE_HEAD} is not an ancestor of HEAD")

    changed = set(filter(None, git("diff", "--name-only", BASE_HEAD).splitlines()))
    untracked = set(
        filter(None, git("ls-files", "--others", "--exclude-standard").splitlines())
    )
    touched = changed | untracked
    unexpected = touched - ALLOWED_PATHS
    if unexpected:
        fail(f"unexpected path outside bounded S1-L scope: {sorted(unexpected)}")
    missing = sorted(path for path in ALLOWED_PATHS if not (REPO_ROOT / path).exists())
    if missing:
        fail(f"missing formal bounded-scope path: {missing}")

    media = sorted(
        path for path in touched if Path(path).suffix.lower() in TEMPORARY_SUFFIXES
    )
    if media:
        fail(f"temporary media/array/archive entered Git scope: {media}")
    diff_check = subprocess.run(
        ["git", "diff", "--check", BASE_HEAD],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if diff_check.returncode:
        fail(f"git diff --check failed: {diff_check.stdout}{diff_check.stderr}")
    return touched


def validate_forbidden_fields() -> None:
    violations: list[str] = []
    for path in FORMAL_CSV_PATHS:
        fields, _ = read_csv(path)
        for field in fields:
            normalized = re.sub(r"[^a-z0-9_]+", "_", field.strip().lower())
            if any(fragment in normalized for fragment in FORBIDDEN_FIELD_FRAGMENTS):
                violations.append(f"{path.name}:{field}")
    if violations:
        fail(f"forbidden decision/ranking field names present: {violations}")


def validate_research_units() -> tuple[
    list[dict[str, str]],
    dict[str, dict[str, str]],
    set[str],
    set[str],
    set[str],
]:
    fields, rows = read_csv(UNIT_PATH)
    require_columns(
        UNIT_PATH,
        fields,
        (
            "research_unit_id",
            "source_segment_id",
            "unit_type",
            "counterfactual_semantic_class",
            "vehicle_present_in_target",
            "valid_for_identity_test",
            "valid_for_vehicle_class_test",
            "valid_for_temporal_test",
            "valid_for_temporal_test_scope",
            "valid_for_temporal_correspondence_test",
            "valid_for_temporal_direction_test",
            "background_spatial_control_group",
            "background_parameter_envelope_group",
            "background_control_semantic_role",
            "transform_rule_id",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "freeze_source",
            "replay_status",
            "optical_identity_source",
            "center_source",
            "axis_source",
            "scale_source",
            "gt_information_debt",
            "optical_condition_execution_status",
            "counterfactual_scope_limitation",
            "vehicle_absence_evidence_scope",
            "anchor_variant_contract",
            "pair_membership_source_segment_id",
            "pair_membership_contract",
            "background_type",
            "background_quality_status",
            "background_reviewed_gt_overlap",
            "config_hash",
            "review_status",
        ),
    )
    require_direct_review(rows, UNIT_PATH.name)
    if len(rows) != 21:
        fail(f"expected exactly twenty-one frozen research units, got {len(rows)}")
    unit_ids = [row["research_unit_id"] for row in rows]
    if len(unit_ids) != len(set(unit_ids)):
        fail("research_unit_id values are not unique")
    by_id = {row["research_unit_id"]: row for row in rows}
    validate_temporal_direction_applicability(rows, by_id, UNIT_PATH.name)
    if any(
        row["anchor_variant_contract"]
        != ANCHOR_VARIANT_CONTRACT
        for row in rows
    ):
        fail("research-unit registry does not require raw_gt and smoothed_gt for all units")
    expected_discovery_sources = {
        "optical_identity_source": "OPTICAL_COMPLETE_VEHICLE_THREAD_FUTURE_SOURCE_NOT_EXECUTED",
        "center_source": "GT_DISCOVERY_ONLY_FUTURE_OPTICAL_AZIMUTH_AND_TIME_STATE",
        "axis_source": "GT_DISCOVERY_ONLY_FUTURE_OPTICAL_POSE_OR_MOTION_AXIS",
        "scale_source": "GT_DISCOVERY_ONLY_FUTURE_VEHICLE_OR_OPTICAL_SIZE_RANGE",
        "gt_information_debt": "GT_DISCOVERY_ONLY;FUTURE_REPLACEABLE;DEPLOYMENT_SOURCE_NOT_READY",
    }
    for row in rows:
        for field, expected in expected_discovery_sources.items():
            if row[field] != expected:
                fail(f"research-unit discovery/source scope changed for {row['research_unit_id']}.{field}")
        if row["optical_condition_execution_status"] != OPTICAL_CONDITION_EXECUTION_STATUS:
            fail(f"real optical-conditioned input was unexpectedly claimed for {row['research_unit_id']}")
        if row["pair_membership_contract"] != PAIR_PROJECTION_RULE:
            fail(f"pair-membership projection contract changed for {row['research_unit_id']}")
        expected_temporal_scope = (
            "CORRESPONDENCE_ONLY"
            if row["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE"
            else "POSITIVE_REFERENCE_FOR_CORRESPONDENCE_ONLY"
            if row["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
            else "NOT_APPLICABLE"
        )
        if row["valid_for_temporal_test_scope"] != expected_temporal_scope:
            fail(f"temporal test scope changed for {row['research_unit_id']}")
    semantic_classes = {row["counterfactual_semantic_class"] for row in rows}
    expected_classes = {
        "TRUE_VEHICLE_POSITIVE",
        "IDENTITY_NEGATIVE_CLASS_POSITIVE",
        "VEHICLE_CLASS_NEGATIVE",
        "TEMPORAL_NEGATIVE",
    }
    if semantic_classes != expected_classes:
        fail(f"unexpected semantic classes: {sorted(semantic_classes)}")

    swaps = [row for row in rows if row["unit_type"] == "trajectory_swap"]
    if len(swaps) != 2:
        fail(f"expected two real-vehicle trajectory swaps, got {len(swaps)}")
    for row in swaps:
        if row["counterfactual_semantic_class"] != "IDENTITY_NEGATIVE_CLASS_POSITIVE":
            fail(f"trajectory swap has wrong semantic class: {row['research_unit_id']}")
        require_false(
            row["valid_for_vehicle_class_test"],
            f"{row['research_unit_id']}.valid_for_vehicle_class_test",
        )
        if (
            row["valid_for_identity_test"] != "true"
            or row["vehicle_present_in_target"] != "true"
        ):
            fail(
                f"trajectory swap identity/class-positive contract invalid: {row['research_unit_id']}"
            )

    positives = [
        row
        for row in rows
        if row["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
    ]
    if len(positives) != 3:
        fail(f"expected three core true-vehicle positives, got {len(positives)}")

    backgrounds = [
        row
        for row in rows
        if row["counterfactual_semantic_class"] == "VEHICLE_CLASS_NEGATIVE"
    ]
    spatial_groups = {
        row["background_spatial_control_group"]
        for row in backgrounds
        if row["background_spatial_control_group"]
    }
    parameter_envelope_groups = {
        row["background_parameter_envelope_group"]
        for row in backgrounds
        if row["background_parameter_envelope_group"]
    }
    if {row["research_unit_id"] for row in backgrounds} != set(
        EXPECTED_BACKGROUND_GROUP_ASSIGNMENTS
    ):
        fail("the four frozen PV002-geometry background-control ids changed")
    if spatial_groups != EXPECTED_BACKGROUND_SPATIAL_GROUPS:
        fail(
            "background controls must occupy exactly the three frozen baseline spatial groups"
        )
    if parameter_envelope_groups != EXPECTED_BACKGROUND_PARAMETER_ENVELOPE_GROUPS:
        fail("background controls must occupy exactly two strict parameter-envelope groups")
    for row in backgrounds:
        if row["valid_for_vehicle_class_test"] != "true":
            fail(
                f"class-negative is not valid for class testing: {row['research_unit_id']}"
            )
        require_false(
            row["vehicle_present_in_target"],
            f"{row['research_unit_id']}.vehicle_present",
        )
        require_false(
            row["valid_for_identity_test"], f"{row['research_unit_id']}.identity_test"
        )
        expected_groups = EXPECTED_BACKGROUND_GROUP_ASSIGNMENTS[row["research_unit_id"]]
        if (
            row["background_spatial_control_group"],
            row["background_parameter_envelope_group"],
        ) != expected_groups:
            fail(f"background cluster assignment changed: {row['research_unit_id']}")
        if (
            row["background_type"],
            row["background_control_semantic_role"],
            row["background_quality_status"],
        ) != EXPECTED_BACKGROUND_SEMANTICS[row["research_unit_id"]]:
            fail(f"background semantic/quality fields changed: {row['research_unit_id']}")
        overlap = finite_float(
            row["background_reviewed_gt_overlap"],
            f"{row['research_unit_id']}.background_reviewed_gt_overlap",
        )
        if abs(overlap) > 1e-12:
            fail(f"background reviewed-GT overlap is not zero: {row['research_unit_id']}")

    for row in positives:
        if (
            row["counterfactual_scope_limitation"] != "NONE"
            or row["vehicle_absence_evidence_scope"] != "NOT_APPLICABLE"
        ):
            fail(f"positive-unit scope fields changed: {row['research_unit_id']}")
        if (
            row["valid_for_temporal_test"] != "true"
            or row["valid_for_temporal_correspondence_test"] != "true"
            or row["valid_for_temporal_direction_test"] != "false"
            or row["valid_for_temporal_test_scope"]
            != "POSITIVE_REFERENCE_FOR_CORRESPONDENCE_ONLY"
        ):
            fail(f"positive temporal-reference scope changed: {row['research_unit_id']}")
    for row in swaps:
        if (
            row["counterfactual_scope_limitation"]
            != "PV002_PV003_SWAP_SCOPE_ONLY;NO_PV004_IDENTITY_SWAP"
            or row["vehicle_absence_evidence_scope"] != "NOT_APPLICABLE"
        ):
            fail(f"identity-swap scope limitation changed: {row['research_unit_id']}")
    for row in backgrounds:
        if (
            row["counterfactual_scope_limitation"]
            != "BACKGROUND_POSITIONS_AND_SUPPORT_GEOMETRY_FROZEN_FROM_PV002_ONLY"
            or row["vehicle_absence_evidence_scope"]
            != "NO_REVIEWED_GT_OVERLAP_PLUS_DIRECT_REVIEW;NOT_ABSOLUTE_PHYSICAL_ABSENCE_PROOF"
        ):
            fail(f"background counterfactual scope limitation changed: {row['research_unit_id']}")

    config_hashes = {row["config_hash"] for row in rows}
    if config_hashes != {EXPECTED_CONFIG_HASH}:
        fail(f"research-unit config hash is not fixed: {config_hashes}")
    positive_source_segments = {row["source_segment_id"] for row in positives}
    for row in rows:
        source_segment = row["pair_membership_source_segment_id"]
        if source_segment not in positive_source_segments:
            fail(
                f"pair membership source is not a frozen true-positive segment: "
                f"{row['research_unit_id']} -> {source_segment}"
            )
        if (
            row["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
            and source_segment != row["source_segment_id"]
        ):
            fail(f"true-positive pair source is not self-referential: {row['research_unit_id']}")
    if any(row["freeze_source"] != DEVELOPMENT_SEGMENT for row in rows):
        fail("research-unit rules were not frozen from PV002")
    for row in positives:
        expected_replay = (
            "DEVELOPMENT_FROZEN"
            if row["source_segment_id"] == DEVELOPMENT_SEGMENT
            else "FIXED_REPLAY"
        )
        if row["replay_status"] != expected_replay:
            fail(f"positive unit replay status changed: {row['research_unit_id']}")

    development_temporal = [
        row
        for row in rows
        if row["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE"
        and row["source_segment_id"] == DEVELOPMENT_SEGMENT
    ]
    if len(development_temporal) != 4:
        fail(f"expected four PV002 temporal negatives, got {len(development_temporal)}")
    expected_temporal_rules = {
        "IMAGE_ORDER_DETERMINISTIC_SHUFFLE",
        "IMAGE_ORDER_REVERSED",
        "TRAJECTORY_TIME_SHIFT_P8",
        "CENTER_PHASE_SHIFT_P8",
    }
    temporal_by_segment: dict[str, set[str]] = defaultdict(set)
    temporal_rows = [
        row
        for row in rows
        if row["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE"
    ]
    for row in temporal_rows:
        temporal_by_segment[row["source_segment_id"]].add(row["transform_rule_id"])
        if (
            row["valid_for_identity_test"] != "false"
            or row["valid_for_vehicle_class_test"] != "false"
            or row["valid_for_temporal_test"] != "true"
            or row["valid_for_temporal_correspondence_test"] != "true"
            or row["valid_for_temporal_direction_test"] != "false"
            or row["valid_for_temporal_test_scope"]
            != "CORRESPONDENCE_ONLY"
        ):
            fail(f"temporal-negative validity contract changed: {row['research_unit_id']}")
        if (
            row["counterfactual_scope_limitation"]
            != "WITHIN_THREAD_GM_RM017_TEMPORAL_CONTROL;NO_CROSS_SCENE_REPLAY"
            or row["vehicle_absence_evidence_scope"] != "NOT_APPLICABLE"
        ):
            fail(f"temporal-control scope limitation changed: {row['research_unit_id']}")
    expected_temporal_segments = {
        DEVELOPMENT_SEGMENT,
        "S0MV-GM_RM017-PV003-SEG01",
        "S0MV-GM_RM017-PV004-SEG01",
    }
    if set(temporal_by_segment) != expected_temporal_segments:
        fail(f"temporal-negative source segments changed: {sorted(temporal_by_segment)}")
    if any(rules != expected_temporal_rules for rules in temporal_by_segment.values()):
        fail(f"each core vehicle must contain the four frozen temporal negatives: {temporal_by_segment}")
    if len(temporal_rows) != 12:
        fail(f"expected twelve frozen temporal negatives, got {len(temporal_rows)}")

    required_review_units = {
        row["research_unit_id"]
        for row in rows
        if row["counterfactual_semantic_class"]
        in {
            "TRUE_VEHICLE_POSITIVE",
            "IDENTITY_NEGATIVE_CLASS_POSITIVE",
            "VEHICLE_CLASS_NEGATIVE",
        }
    }
    required_review_units.update(
        row["research_unit_id"]
        for row in rows
        if row["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE"
        and row["source_segment_id"] == DEVELOPMENT_SEGMENT
    )
    expected_required_count = (
        len(backgrounds) + len(positives) + len(swaps) + len(development_temporal)
    )
    if len(required_review_units) != expected_required_count:
        fail(
            "required visual-review registry does not contain 3 positives, 2 swaps, "
            "4 backgrounds, and 4 PV002 temporal negatives"
        )
    return (
        rows,
        by_id,
        spatial_groups,
        parameter_envelope_groups,
        required_review_units,
    )


def validate_sampling_and_representations(
    units_by_id: Mapping[str, Mapping[str, str]],
) -> tuple[
    dict[tuple[str, str], str],
    dict[tuple[str, str], str],
    dict[tuple[str, str], int],
    dict[tuple[str, str], int],
]:
    sampling_fields, sampling_rows = read_csv(SAMPLING_PATH)
    require_columns(
        SAMPLING_PATH,
        sampling_fields,
        (
            "research_unit_id",
            "counterfactual_semantic_class",
            "sar_frame_index",
            "source_image_frame_index",
            "anchor_variant",
            "representation",
            "axis_rule",
            "grid_width",
            "grid_height",
            "window_half_x_source_px",
            "window_half_y_source_px",
            "source_px_per_grid_x",
            "source_px_per_grid_y",
            "interpolation_rule",
            "gray_input_lineage",
            "mask_rule_id",
            "structure_boundary_guard_id",
            "structure_valid_fraction",
            "support_geometry_id",
            "equal_support_parity_status",
            "normalization_path",
            "background_estimator_id",
            "core_exclusion_rule_id",
            "candidate_outer_pixel_count",
            "background_sample_count",
            "background_sample_count_definition",
            "valid_fraction",
            "saturation_low_fraction",
            "saturation_high_fraction",
            "normalization_status",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "review_status",
        ),
    )
    require_direct_review(sampling_rows, SAMPLING_PATH.name)
    validate_temporal_direction_applicability(
        sampling_rows,
        units_by_id,
        SAMPLING_PATH.name,
    )
    if {row["representation"] for row in sampling_rows} != REPRESENTATIONS:
        fail("sampling audit does not contain exactly four representations")
    if {row["axis_rule"] for row in sampling_rows} != AXIS_RULES:
        fail("sampling audit does not contain exactly seven axis rules")
    if {row["anchor_variant"] for row in sampling_rows} != ANCHOR_VARIANTS:
        fail("sampling audit does not contain raw_gt and smoothed_gt")
    if {row["normalization_path"] for row in sampling_rows} != NORMALIZATION_PATHS:
        fail("sampling audit does not contain exactly two normalization paths")
    if any(
        row["equal_support_parity_status"] != "PASS_BY_CONSTRUCTION"
        for row in sampling_rows
    ):
        fail("equal-support parity failure present")
    if any(
        row["grid_width"] != "256" or row["grid_height"] != "128"
        for row in sampling_rows
    ):
        fail("sampling grid changed from 256x128")

    geometry_by_frame: dict[tuple[str, str, str, str], set[tuple[str, ...]]] = (
        defaultdict(set)
    )
    combinations_by_frame: dict[tuple[str, str, str, str], set[tuple[str, ...]]] = (
        defaultdict(set)
    )
    sampling_row_count_by_frame: Counter[tuple[str, str, str, str]] = Counter()
    for row in sampling_rows:
        unit = units_by_id.get(row["research_unit_id"])
        if unit is None:
            fail(f"sampling audit references unknown unit: {row['research_unit_id']}")
        if (
            row["counterfactual_semantic_class"]
            != unit["counterfactual_semantic_class"]
        ):
            fail(f"sampling semantic class mismatch: {row['research_unit_id']}")
        normalization = row["normalization_path"]
        expected_estimator = (
            "FROZEN_GT_CONDITIONED_ROW_REFERENCE"
            if normalization == "FIXED_REFERENCE"
            else "OUTER_RING_MEDIAN_PLUS_VALID_P99_CORE_EXCLUDED_FROM_BACKGROUND"
        )
        if row["background_estimator_id"] != expected_estimator:
            fail(f"normalization estimator drift: {row['background_estimator_id']}")
        if (
            row["core_exclusion_rule_id"]
            != "CENTRAL_NOMINAL_VEHICLE_RECTANGLE_EXCLUDED"
        ):
            fail("normalization central-core exclusion rule changed")
        try:
            candidate_outer_pixel_count = int(row["candidate_outer_pixel_count"])
            background_sample_count = int(row["background_sample_count"])
            valid_fraction = float(row["valid_fraction"])
        except ValueError as exc:
            fail(f"sampling normalization audit has non-numeric audit values: {exc}")
        if candidate_outer_pixel_count < 0 or background_sample_count < 0:
            fail("sampling normalization audit has negative background sample count")
        if normalization == "FIXED_REFERENCE":
            if (
                background_sample_count != 0
                or row["background_sample_count_definition"]
                != "SOURCE_REFERENCE_SAMPLE_COUNT_UNAVAILABLE_NOT_REESTIMATED_FROM_CURRENT_CANDIDATE"
            ):
                fail("fixed-reference path misstates current-candidate background samples")
        elif (
            background_sample_count != candidate_outer_pixel_count
            or row["background_sample_count_definition"]
            != "CURRENT_CANDIDATE_OUTER_RING_SAMPLE_COUNT"
        ):
            fail("local normalization background sample count does not match outer ring")
        if not 0.0 <= valid_fraction <= 1.0:
            fail("sampling normalization audit has invalid valid fraction")
        half_x = finite_float(
            row["window_half_x_source_px"],
            f"{SAMPLING_PATH.name}.window_half_x_source_px",
        )
        half_y = finite_float(
            row["window_half_y_source_px"],
            f"{SAMPLING_PATH.name}.window_half_y_source_px",
        )
        source_density_x = finite_float(
            row["source_px_per_grid_x"],
            f"{SAMPLING_PATH.name}.source_px_per_grid_x",
        )
        source_density_y = finite_float(
            row["source_px_per_grid_y"],
            f"{SAMPLING_PATH.name}.source_px_per_grid_y",
        )
        if (
            abs(source_density_x - (2.0 * half_x / (256 - 1))) > 2e-6
            or abs(source_density_y - (2.0 * half_y / (128 - 1))) > 2e-6
        ):
            fail("sampling source-pixel density does not use the W-1/H-1 grid interval")
        if row["structure_boundary_guard_id"] != STRUCTURE_BOUNDARY_GUARD_ID:
            fail("sampling structure boundary guard changed")
        if row["structure_valid_fraction"]:
            structure_valid_fraction = finite_float(
                row["structure_valid_fraction"],
                f"{SAMPLING_PATH.name}.structure_valid_fraction",
            )
            if not 0.0 <= structure_valid_fraction <= valid_fraction + 1e-9:
                fail("sampling structure-valid fraction exceeds imaging-valid support")
        for field in ("saturation_low_fraction", "saturation_high_fraction"):
            value = row[field]
            if value:
                try:
                    fraction = float(value)
                except ValueError as exc:
                    fail(f"sampling normalization audit has non-numeric {field}: {exc}")
                if not 0.0 <= fraction <= 1.0:
                    fail(f"sampling normalization audit has invalid {field}")
            elif row["normalization_status"] == "PASS":
                fail(f"successful normalization is missing {field}")
        key = (
            row["research_unit_id"],
            row["anchor_variant"],
            row["sar_frame_index"],
            row["source_image_frame_index"],
        )
        geometry_by_frame[key].add(
            (
                row["window_half_x_source_px"],
                row["window_half_y_source_px"],
                row["grid_width"],
                row["grid_height"],
                row["interpolation_rule"],
                row["gray_input_lineage"],
                row["mask_rule_id"],
                row["structure_boundary_guard_id"],
                row["support_geometry_id"],
            )
        )
        combinations_by_frame[key].add(
            (
                row["normalization_path"],
                row["representation"],
                row["axis_rule"],
            )
        )
        sampling_row_count_by_frame[key] += 1
    unequal = [key for key, values in geometry_by_frame.items() if len(values) != 1]
    if unequal:
        fail(
            f"equal-support geometry differs across representations/axes/normalizations: {unequal[:5]}"
        )
    gt_axis = "GT_DERIVED_UNSIGNED_BODY"
    base_combinations = {
        (normalization_path, representation, gt_axis)
        for normalization_path in NORMALIZATION_PATHS
        for representation in REPRESENTATIONS
    }
    positive_axis_combinations = {
        (normalization_path, "CENTER_TRACKED_BODY", axis_rule)
        for normalization_path in NORMALIZATION_PATHS
        for axis_rule in AXIS_RULES - {gt_axis}
    }
    for key, combinations in combinations_by_frame.items():
        if sampling_row_count_by_frame[key] != len(combinations):
            fail(f"duplicate sampling setting rows present for {key}")
        unit = units_by_id[key[0]]
        expected_combinations = set(base_combinations)
        if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE":
            expected_combinations |= positive_axis_combinations
        if combinations != expected_combinations:
            fail(
                f"sampling representation/axis/normalization coverage changed for {key}"
            )

    representation_fields, representation_rows = read_csv(REPRESENTATION_PATH)
    require_columns(
        REPRESENTATION_PATH,
        representation_fields,
        (
            "research_unit_id",
            "anchor_variant",
            "representation",
            "normalization_path",
            "pair_rule_id",
            "source_pair_set_hash",
            "pair_set_hash",
            "candidate_pair_count",
            "eligible_pair_count",
            "pair_evidence_state",
            "orientation_dominant_axial_direction_deg",
            "orientation_to_body_long_axis_diff_median_deg",
            "orientation_to_body_short_axis_diff_median_deg",
            "topology_thin_edge_adjacency_mean_degree_median",
            "topology_thin_edge_collinearity_proxy_median",
            "topology_thin_edge_parallel_representation_x_fraction_median",
            "topology_thin_edge_parallel_representation_y_fraction_median",
            "topology_estimator_id",
            "structure_boundary_guard_id",
            "structure_valid_fraction_median",
            "structure_valid_fraction_min",
            "evidence_validity_status",
            "representation_attribution_scope",
            "support_geometry",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "review_status",
        ),
    )
    require_direct_review(representation_rows, REPRESENTATION_PATH.name)
    validate_temporal_direction_applicability(
        representation_rows,
        units_by_id,
        REPRESENTATION_PATH.name,
    )
    if {row["representation"] for row in representation_rows} != REPRESENTATIONS:
        fail("representation metrics do not contain exactly four representations")
    if {row["anchor_variant"] for row in representation_rows} != ANCHOR_VARIANTS:
        fail("representation metrics do not contain raw_gt and smoothed_gt")
    if {
        row["normalization_path"] for row in representation_rows
    } != NORMALIZATION_PATHS:
        fail("representation metrics do not contain exactly two normalization paths")
    if any(
        row["support_geometry"]
        != (
            "EQUAL_WINDOW_DIMENSIONS_GRID_DENSITY_MASK_GRAY;"
            "ROTATED_ANISOTROPIC_WINDOWS_SAMPLE_DIFFERENT_SOURCE_PIXELS"
        )
        for row in representation_rows
    ):
        fail("representation metrics contain non-equal-support geometry")
    if any(row["topology_estimator_id"] != THIN_EDGE_ESTIMATOR for row in representation_rows):
        fail("representation topology estimator is not the frozen thin-edge proxy")
    for row in representation_rows:
        if row["pair_rule_id"] != PAIR_RULE_ID:
            fail("representation pair-rule id changed")
        if row["structure_boundary_guard_id"] != STRUCTURE_BOUNDARY_GUARD_ID:
            fail("representation structure boundary guard changed")
        is_body = row["representation"] == "CENTER_TRACKED_BODY"
        body_field_any = bool(row["orientation_to_body_long_axis_diff_median_deg"]) or bool(
            row["orientation_to_body_short_axis_diff_median_deg"]
        )
        if body_field_any and not is_body:
            fail("body long/short orientation relation leaked into a non-body representation")
        if row["evidence_validity_status"] not in {"PASS", "NORMALIZATION_FAILURE_PRESENT"}:
            fail("representation evidence-validity status is invalid")
        expected_attribution_scope = (
            "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT"
            if row["representation"] in {"CENTER_TRACKED_RADIAL", "CENTER_TRACKED_BODY"}
            else "TRACKED_OR_FIXED_CENTER_WITH_GLOBAL_AXES_AND_EQUAL_WINDOW_DIMENSIONS"
        )
        if row["representation_attribution_scope"] != expected_attribution_scope:
            fail("representation attribution scope changed")
        for field in ("structure_valid_fraction_median", "structure_valid_fraction_min"):
            if row[field]:
                fraction = finite_float(row[field], f"{REPRESENTATION_PATH.name}.{field}")
                if not 0.0 <= fraction <= 1.0:
                    fail("representation structure-valid fraction is outside [0,1]")

    rows_by_setting: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    hashes_by_unit_anchor: dict[tuple[str, str], set[str]] = defaultdict(set)
    source_hashes_by_unit_anchor: dict[tuple[str, str], set[str]] = defaultdict(set)
    candidate_counts_by_unit_anchor: dict[tuple[str, str], set[int]] = defaultdict(set)
    eligible_counts_by_unit_anchor: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in representation_rows:
        rows_by_setting[
            (row["research_unit_id"], row["anchor_variant"], row["normalization_path"])
        ].add(row["representation"])
        unit_anchor = (row["research_unit_id"], row["anchor_variant"])
        hashes_by_unit_anchor[unit_anchor].add(row["pair_set_hash"])
        source_hashes_by_unit_anchor[unit_anchor].add(row["source_pair_set_hash"])
        candidate_count = int(row["candidate_pair_count"])
        eligible_count = int(row["eligible_pair_count"])
        candidate_counts_by_unit_anchor[unit_anchor].add(candidate_count)
        eligible_counts_by_unit_anchor[unit_anchor].add(eligible_count)
        if eligible_count > candidate_count:
            fail(f"eligible pair count exceeds candidate count for {unit_anchor}")
        if row["pair_evidence_state"] != expected_pair_state(eligible_count):
            fail(
                f"representation pair evidence state invalid for count {eligible_count}"
            )
    if any(values != REPRESENTATIONS for values in rows_by_setting.values()):
        fail(
            "a unit/anchor/normalization setting lacks one of the four representations"
        )
    bad_hashes = {
        key: values for key, values in hashes_by_unit_anchor.items() if len(values) != 1
    }
    if bad_hashes:
        fail(f"pair-set hash changes across representation/normalization: {bad_hashes}")
    bad_source_hashes = {
        key: values
        for key, values in source_hashes_by_unit_anchor.items()
        if len(values) != 1 or not next(iter(values))
    }
    if bad_source_hashes:
        fail(f"source pair-set hash changes across outputs: {bad_source_hashes}")
    expected_unit_anchors = {
        (unit_id, anchor_variant)
        for unit_id in units_by_id
        for anchor_variant in ("raw_gt", "smoothed_gt")
    }
    if set(hashes_by_unit_anchor) != expected_unit_anchors:
        fail("representation metric unit/anchor coverage changed")
    if set(source_hashes_by_unit_anchor) != expected_unit_anchors:
        fail("source pair-hash unit/anchor coverage changed")
    for unit_anchor, values in source_hashes_by_unit_anchor.items():
        unit_id, anchor_variant = unit_anchor
        source_segment = units_by_id[unit_id]["pair_membership_source_segment_id"]
        source_values = source_hashes_by_unit_anchor.get((source_segment, anchor_variant))
        if source_values is None or values != source_values:
            fail(
                f"unit source-pair hash does not match its frozen source positive: "
                f"{unit_anchor} -> {source_segment}"
            )
    bad_candidate_counts = {
        key: values
        for key, values in candidate_counts_by_unit_anchor.items()
        if len(values) != 1
    }
    if bad_candidate_counts:
        fail(
            "candidate-pair count changes across representation/normalization: "
            f"{bad_candidate_counts}"
        )
    bad_eligible_counts = {
        key: values
        for key, values in eligible_counts_by_unit_anchor.items()
        if len(values) != 1
    }
    if bad_eligible_counts:
        fail(
            "eligible-pair count changes across representation/normalization: "
            f"{bad_eligible_counts}"
        )
    return (
        {key: next(iter(values)) for key, values in hashes_by_unit_anchor.items()},
        {
            key: next(iter(values))
            for key, values in source_hashes_by_unit_anchor.items()
        },
        {
            key: next(iter(values))
            for key, values in candidate_counts_by_unit_anchor.items()
        },
        {
            key: next(iter(values))
            for key, values in eligible_counts_by_unit_anchor.items()
        },
    )


def validate_pair_contract(
    pair_hashes: Mapping[tuple[str, str], str],
    source_pair_hashes: Mapping[tuple[str, str], str],
    candidate_counts: Mapping[tuple[str, str], int],
    eligible_counts: Mapping[tuple[str, str], int],
    units_by_id: Mapping[str, Mapping[str, str]],
) -> None:
    fields, rows = read_csv(PAIR_PATH)
    require_columns(
        PAIR_PATH,
        fields,
        (
            "pair_id",
            "source_pair_id",
            "pair_rule_id",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_membership_reliability_scope",
            "pair_set_hash",
            "research_unit_id",
            "left_frame",
            "right_frame",
            "left_time_sec",
            "right_time_sec",
            "frame_gap",
            "time_gap_sec",
            "left_view_angle_deg",
            "right_view_angle_deg",
            "view_angle_diff_deg",
            "anchor_variant",
            "left_axis_reliability",
            "right_axis_reliability",
            "left_registration_reliability",
            "right_registration_reliability",
            "baseline_common_valid_pixel_count",
            "baseline_common_valid_fraction",
            "baseline_field_ncc",
            "baseline_field_ncc_finite",
            "pair_eligibility",
            "pair_exclusion_reasons",
            "common_valid_fraction",
            "normalization_path",
            "evidence_family",
            "evidence_estimator_id",
            "submetric_name",
            "metric_direction",
            "comparison_id",
            "comparison_attribution_scope",
            "baseline_transform",
            "test_transform",
            "baseline_value",
            "test_value",
            "raw_delta",
            "directional_delta",
            "counterfactual_semantic_class",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "review_status",
        ),
    )
    require_direct_review(rows, PAIR_PATH.name)
    validate_temporal_direction_applicability(rows, units_by_id, PAIR_PATH.name)
    if {row["normalization_path"] for row in rows} != NORMALIZATION_PATHS:
        fail("pair metrics do not contain exactly two normalization paths")
    if {row["anchor_variant"] for row in rows} != ANCHOR_VARIANTS:
        fail("pair metrics do not contain raw_gt and smoothed_gt")
    if {row["submetric_name"] for row in rows} != set(PAIR_SUBMETRICS):
        fail(f"pair metrics do not contain exactly the frozen {len(PAIR_SUBMETRICS)} submetrics")

    memberships: dict[tuple[str, str], dict[tuple[str, str], set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    submetrics_by_pair_setting: dict[tuple[str, ...], set[str]] = defaultdict(set)
    metadata_by_pair: dict[tuple[str, str, str], set[tuple[str, ...]]] = defaultdict(
        set
    )
    unique_pairs_by_unit_anchor: dict[
        tuple[str, str], dict[str, dict[str, str]]
    ] = defaultdict(dict)
    semantic_class_by_unit_anchor: dict[tuple[str, str], set[str]] = defaultdict(set)
    axis_rules_seen = {"GT_DERIVED_UNSIGNED_BODY"}
    for row in rows:
        unit_anchor = (row["research_unit_id"], row["anchor_variant"])
        expected_hash = pair_hashes.get(unit_anchor)
        if expected_hash is None or row["pair_set_hash"] != expected_hash:
            fail(f"pair-set hash mismatch for {unit_anchor}")
        if row["source_pair_set_hash"] != source_pair_hashes.get(unit_anchor):
            fail(f"source pair-set hash mismatch for {unit_anchor}")
        if row["pair_projection_rule"] != PAIR_PROJECTION_RULE:
            fail("pair projection rule changed")
        expected_scope = expected_reliability_scope(units_by_id[row["research_unit_id"]])
        if row["pair_membership_reliability_scope"] != expected_scope:
            fail(f"pair reliability scope changed for {unit_anchor}")
        memberships[unit_anchor][(row["normalization_path"], row["comparison_id"])].add(
            row["pair_id"]
        )
        semantic_class_by_unit_anchor[unit_anchor].add(
            row["counterfactual_semantic_class"]
        )
        if row["pair_rule_id"] != PAIR_RULE_ID:
            fail("pair rule id changed")
        expected_family, expected_direction, expected_estimator = PAIR_SUBMETRICS[
            row["submetric_name"]
        ]
        if (
            row["evidence_family"] != expected_family
            or row["metric_direction"] != expected_direction
            or row["evidence_estimator_id"] != expected_estimator
        ):
            fail(
                f"pair submetric family/direction changed for {row['submetric_name']}"
            )
        submetrics_by_pair_setting[
            (
                row["research_unit_id"],
                row["anchor_variant"],
                row["normalization_path"],
                row["comparison_id"],
                row["pair_id"],
            )
        ].add(row["submetric_name"])

        is_placeholder = row["pair_eligibility"] == "NO_CANDIDATE_PAIRS"
        if is_placeholder:
            if candidate_counts.get(unit_anchor) != 0:
                fail(
                    f"zero-pair placeholder used for nonzero candidate group {unit_anchor}"
                )
            if (
                row["pair_id"]
                or row["source_pair_id"]
                or row["pair_exclusion_reasons"] != "NO_NONADJACENT_SIMILAR_VIEW_PAIRS"
            ):
                fail(f"invalid zero-pair placeholder identity/reason for {unit_anchor}")
            blank_fields = (
                "left_frame",
                "right_frame",
                "left_time_sec",
                "right_time_sec",
                "frame_gap",
                "time_gap_sec",
                "left_view_angle_deg",
                "right_view_angle_deg",
                "view_angle_diff_deg",
                "baseline_common_valid_pixel_count",
                "baseline_common_valid_fraction",
                "baseline_field_ncc",
                "baseline_field_ncc_finite",
                "common_valid_fraction",
                "baseline_value",
                "test_value",
                "raw_delta",
                "directional_delta",
            )
            if any(row[field] for field in blank_fields):
                fail(
                    f"zero-pair placeholder contains fabricated numeric evidence: {unit_anchor}"
                )
        else:
            if candidate_counts.get(unit_anchor, 0) <= 0 or not row["pair_id"]:
                fail(
                    f"real pair row used without a frozen candidate pair: {unit_anchor}"
                )
            if row["pair_eligibility"] not in {
                "ELIGIBLE",
                "EXCLUDED_RELIABILITY",
                "EXCLUDED_COMMON_VALID",
            }:
                fail(f"invalid real-pair eligibility: {row['pair_eligibility']}")
            expected_pair_id = (
                f"{row['research_unit_id']}|{row['anchor_variant']}|"
                f"{row['left_frame']}|{row['right_frame']}"
            )
            source_segment = units_by_id[row["research_unit_id"]][
                "pair_membership_source_segment_id"
            ]
            expected_source_pair_id = (
                f"{source_segment}|{row['anchor_variant']}|"
                f"{row['left_frame']}|{row['right_frame']}"
            )
            if row["pair_id"] != expected_pair_id:
                fail(f"projected pair id is malformed: {row['pair_id']}")
            if row["source_pair_id"] != expected_source_pair_id:
                fail(f"source pair id is malformed: {row['source_pair_id']}")
            try:
                baseline_common_valid_pixel_count = int(
                    row["baseline_common_valid_pixel_count"]
                )
                baseline_common_valid = float(row["baseline_common_valid_fraction"])
                common_valid = float(row["common_valid_fraction"])
            except ValueError as exc:
                fail(f"real pair has non-numeric common-valid audit: {exc}")
            if (
                not math.isfinite(baseline_common_valid)
                or not 0.0 <= baseline_common_valid <= 1.0
                or not math.isfinite(common_valid)
                or not 0.0 <= common_valid <= 1.0
            ):
                fail(f"real pair has invalid common-valid fraction: {row['pair_id']}")
            if baseline_common_valid_pixel_count < 0:
                fail(f"real pair has negative common-valid pixel count: {row['pair_id']}")
            if row["baseline_field_ncc_finite"] not in {"true", "false"}:
                fail(f"real pair has invalid baseline-field-finite flag: {row['pair_id']}")
            if row["baseline_field_ncc_finite"] == "true":
                try:
                    baseline_field_ncc = float(row["baseline_field_ncc"])
                except ValueError as exc:
                    fail(f"finite baseline NCC is non-numeric: {exc}")
                if not math.isfinite(baseline_field_ncc):
                    fail(f"finite baseline NCC flag contradicts value: {row['pair_id']}")
            elif row["baseline_field_ncc"]:
                fail(f"non-finite baseline NCC should be blank: {row['pair_id']}")
            reasons = set(filter(None, row["pair_exclusion_reasons"].split(";")))
            if row["pair_eligibility"] == "ELIGIBLE":
                if (
                    reasons
                    or baseline_common_valid_pixel_count < 20
                    or row["baseline_field_ncc_finite"] != "true"
                ):
                    fail(f"eligible pair has exclusion debt: {row['pair_id']}")
            elif row["pair_eligibility"] == "EXCLUDED_RELIABILITY":
                if not reasons & {
                    "AXIS_RELIABILITY_FAILED",
                    "REGISTRATION_RELIABILITY_FAILED",
                }:
                    fail(f"reliability-excluded pair lacks reliability reason: {row['pair_id']}")
                if row["baseline_field_ncc_finite"] != "true":
                    fail(
                        "non-finite baseline field evidence must use "
                        f"EXCLUDED_COMMON_VALID: {row['pair_id']}"
                    )
            else:
                if row["baseline_field_ncc_finite"] != "false" or not any(
                    "COMMON_VALID" in reason or "FIELD_NCC" in reason
                    for reason in reasons
                ):
                    fail(f"common-valid-excluded pair lacks explicit reason: {row['pair_id']}")
            metadata_by_pair[
                (row["research_unit_id"], row["anchor_variant"], row["pair_id"])
            ].add(
                (
                    row["left_frame"],
                    row["right_frame"],
                    row["left_time_sec"],
                    row["right_time_sec"],
                    row["frame_gap"],
                    row["time_gap_sec"],
                    row["left_view_angle_deg"],
                    row["right_view_angle_deg"],
                    row["view_angle_diff_deg"],
                    row["left_axis_reliability"],
                    row["right_axis_reliability"],
                    row["left_registration_reliability"],
                    row["right_registration_reliability"],
                    row["baseline_common_valid_pixel_count"],
                    row["baseline_common_valid_fraction"],
                    row["baseline_field_ncc"],
                    row["baseline_field_ncc_finite"],
                    row["pair_eligibility"],
                    row["pair_exclusion_reasons"],
                    row["source_pair_id"],
                    row["source_pair_set_hash"],
                    row["pair_projection_rule"],
                    row["pair_membership_reliability_scope"],
                )
            )
            existing = unique_pairs_by_unit_anchor[unit_anchor].get(row["pair_id"])
            if existing is None:
                unique_pairs_by_unit_anchor[unit_anchor][row["pair_id"]] = dict(row)
            elif any(
                existing[field] != row[field]
                for field in (
                    "source_pair_id",
                    "left_frame",
                    "right_frame",
                    "baseline_common_valid_pixel_count",
                    "baseline_field_ncc_finite",
                    "pair_eligibility",
                    "pair_exclusion_reasons",
                )
            ):
                fail(f"projected pair metadata changes across rows: {row['pair_id']}")
            if (
                int(row["frame_gap"]) < 10
                or float(row["view_angle_diff_deg"]) > 5.000001
            ):
                fail(f"pair violates frozen frame/view rule: {row['pair_id']}")

        if row["comparison_id"].startswith("GT_ORIENTED_WINDOW_RULE_VS_"):
            axis_rules_seen.add(row["baseline_transform"])
            expected_attribution_scope = (
                "GT_DERIVED_ORIENTATION_RULE_VS_PLACEBO_WITH_SAME_ANISOTROPIC_"
                "WINDOW_DIMENSIONS;SOURCE_PIXELS_CHANGE_WITH_ROTATION"
            )
            if row["test_transform"] != "GT_DERIVED_UNSIGNED_BODY":
                fail(
                    "axis-placebo row does not test the frozen GT-derived unsigned axis"
                )
        else:
            expected_transforms = REPRESENTATION_COMPARISON_TRANSFORMS.get(
                row["comparison_id"]
            )
            if expected_transforms is None or (
                row["baseline_transform"],
                row["test_transform"],
            ) != expected_transforms:
                fail(f"representation comparison transform changed: {row['comparison_id']}")
            expected_attribution_scope = (
                "TRACKED_CENTER_CHANGE_WITH_EQUAL_WINDOW_DIMENSIONS"
                if row["comparison_id"] == "TRANSLATION_COMPENSATION"
                else "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT"
            )
        if row["comparison_attribution_scope"] != expected_attribution_scope:
            fail(f"comparison attribution scope changed: {row['comparison_id']}")
    if any(len(values) != 1 for values in metadata_by_pair.values()):
        fail(
            "pair endpoint/reliability metadata changes across comparisons or normalizations"
        )
    for unit_anchor, expected_pair_hash in pair_hashes.items():
        unit_id, anchor_variant = unit_anchor
        unit = units_by_id[unit_id]
        pairs = sorted(
            unique_pairs_by_unit_anchor.get(unit_anchor, {}).values(),
            key=lambda row: (int(row["left_frame"]), int(row["right_frame"])),
        )
        if len(pairs) != candidate_counts[unit_anchor]:
            fail(
                f"deduplicated projected pair count mismatch for {unit_anchor}: "
                f"{len(pairs)} vs {candidate_counts[unit_anchor]}"
            )
        projection_payload = [
            (
                row["source_pair_id"],
                row["pair_eligibility"],
                row["pair_exclusion_reasons"],
            )
            for row in pairs
        ]
        recomputed_projection_hash = json_sha256(
            {
                "source_pair_set_hash": source_pair_hashes[unit_anchor],
                "projected_pairs": projection_payload,
            }
        )
        if recomputed_projection_hash != expected_pair_hash:
            fail(f"projected pair-set hash is not reproducible for {unit_anchor}")
        if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE":
            source_payload = [
                (
                    int(row["left_frame"]),
                    int(row["right_frame"]),
                    int(row["baseline_common_valid_pixel_count"]),
                    row["baseline_field_ncc_finite"],
                    row["pair_eligibility"],
                    row["pair_exclusion_reasons"],
                )
                for row in pairs
            ]
            if json_sha256(source_payload) != source_pair_hashes[unit_anchor]:
                fail(f"source-positive pair-set hash is not reproducible for {unit_anchor}")
    if any(values != set(PAIR_SUBMETRICS) for values in submetrics_by_pair_setting.values()):
        fail("a pair/comparison/normalization setting lacks a frozen submetric")
    if axis_rules_seen != AXIS_RULES:
        fail(f"axis-placebo comparison set changed: {sorted(axis_rules_seen)}")
    if {
        row["comparison_id"] for row in rows
    } != REPRESENTATION_COMPARISONS | AXIS_COMPARISONS:
        fail(
            "pair output does not contain the exact representation and axis comparison ids"
        )
    if set(memberships) != set(pair_hashes):
        missing = sorted(set(pair_hashes) - set(memberships))
        fail(f"unit/anchor pair groups have no explicit comparison rows: {missing}")
    for unit_anchor, by_setting in memberships.items():
        semantic_classes = semantic_class_by_unit_anchor[unit_anchor]
        if len(semantic_classes) != 1:
            fail(f"semantic class changes within pair group {unit_anchor}")
        semantic_class = next(iter(semantic_classes))
        expected_comparisons = set(REPRESENTATION_COMPARISONS)
        if semantic_class == "TRUE_VEHICLE_POSITIVE":
            expected_comparisons |= AXIS_COMPARISONS
        actual_comparisons = {comparison_id for _, comparison_id in by_setting}
        if actual_comparisons != expected_comparisons:
            fail(
                f"comparison-id coverage changed for {unit_anchor}: {sorted(actual_comparisons)}"
            )
        for comparison_id in expected_comparisons:
            paths = {
                normalization_path
                for normalization_path, current_comparison in by_setting
                if current_comparison == comparison_id
            }
            if paths != NORMALIZATION_PATHS:
                fail(
                    f"dual-normalization pair coverage missing for {unit_anchor}/{comparison_id}"
                )

        expected_candidate_count = candidate_counts[unit_anchor]
        expected_eligible_count = eligible_counts[unit_anchor]
        observed_eligible_pair_ids = {
            row["pair_id"]
            for row in rows
            if (row["research_unit_id"], row["anchor_variant"]) == unit_anchor
            and row["pair_eligibility"] == "ELIGIBLE"
        }
        if len(observed_eligible_pair_ids) != expected_eligible_count:
            fail(
                f"eligible pair membership count changed for {unit_anchor}: "
                f"{len(observed_eligible_pair_ids)} vs {expected_eligible_count}"
            )
        for setting, pair_ids in by_setting.items():
            if expected_candidate_count == 0:
                if pair_ids != {""}:
                    fail(
                        f"zero-pair group has non-placeholder membership: {unit_anchor}/{setting}"
                    )
            elif "" in pair_ids or len(pair_ids) != expected_candidate_count:
                fail(
                    f"candidate pair membership count changed for {unit_anchor}/{setting}: "
                    f"{len(pair_ids)} vs {expected_candidate_count}"
                )
        distinct_pair_sets = {frozenset(values) for values in by_setting.values()}
        if len(distinct_pair_sets) != 1:
            fail(
                f"pair membership changes across comparison/axis/normalization for {unit_anchor}"
            )


def pair_graph_counts_from_rows(
    rows: Sequence[Mapping[str, str]],
) -> tuple[int, int, int]:
    frames = sorted(
        {int(row["left_frame"]) for row in rows}
        | {int(row["right_frame"]) for row in rows}
    )
    if not frames:
        return 0, 0, 0
    degree: Counter[int] = Counter()
    parent = {frame: frame for frame in frames}

    def find(frame: int) -> int:
        while parent[frame] != frame:
            parent[frame] = parent[parent[frame]]
            frame = parent[frame]
        return frame

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for row in rows:
        left = int(row["left_frame"])
        right = int(row["right_frame"])
        degree[left] += 1
        degree[right] += 1
        union(left, right)
    return len(frames), max(degree.values(), default=0), len({find(frame) for frame in frames})


def validate_pair_and_frame_sensitivity(
    pair_hashes: Mapping[tuple[str, str], str],
    source_pair_hashes: Mapping[tuple[str, str], str],
    candidate_counts: Mapping[tuple[str, str], int],
    eligible_counts: Mapping[tuple[str, str], int],
    units_by_id: Mapping[str, Mapping[str, str]],
) -> Counter[str]:
    fields, rows = read_csv(SENSITIVITY_PATH)
    require_columns(
        SENSITIVITY_PATH,
        fields,
        (
            "sensitivity_id",
            "research_unit_id",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_membership_reliability_scope",
            "pair_set_hash",
            "sensitivity_mode",
            "sensitivity_state",
            "frozen_eligible_pair_count",
            "metric_usable_pair_count",
            "eligible_pair_count",
            "eligible_pair_count_semantics",
            "unique_frame_count",
            "max_frame_pair_degree",
            "pair_graph_component_count",
            "anchor_variant",
            "normalization_path",
            "evidence_family",
            "submetric_name",
            "comparison_id",
            "full_median_directional_delta",
            "omitted_pair_id",
            "omitted_frame",
            "leave_one_out_median_directional_delta",
            "sign_flip",
            "leave_one_out_min_delta",
            "leave_one_out_max_delta",
            "leave_one_out_state",
            "pair_evidence_state",
            "review_status",
        ),
    )
    require_direct_review(rows, SENSITIVITY_PATH.name)
    validate_temporal_direction_applicability(
        rows, units_by_id, SENSITIVITY_PATH.name
    )
    if {row["submetric_name"] for row in rows} != set(PAIR_SUBMETRICS):
        fail(
            f"pair/frame sensitivity output does not contain exactly the frozen "
            f"{len(PAIR_SUBMETRICS)} submetrics"
        )
    if {row["normalization_path"] for row in rows} != NORMALIZATION_PATHS:
        fail("pair/frame sensitivity output does not contain both normalization paths")
    if {row["anchor_variant"] for row in rows} != ANCHOR_VARIANTS:
        fail("pair/frame sensitivity output does not contain both anchor variants")
    if {row["sensitivity_mode"] for row in rows} != PAIR_SENSITIVITY_MODES:
        fail("pair/frame sensitivity output does not contain both LOPO and LOFO modes")

    _, pair_rows = read_csv(PAIR_PATH)
    source_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in pair_rows:
        key = (
            row["research_unit_id"],
            row["pair_set_hash"],
            row["anchor_variant"],
            row["normalization_path"],
            row["evidence_family"],
            row["submetric_name"],
            row["comparison_id"],
        )
        source_groups[key].append(row)

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["evidence_family"] != PAIR_SUBMETRICS[row["submetric_name"]][0]:
            fail(f"sensitivity evidence family changed for {row['submetric_name']}")
        unit_anchor = (row["research_unit_id"], row["anchor_variant"])
        unit = units_by_id[row["research_unit_id"]]
        if row["pair_set_hash"] != pair_hashes.get(unit_anchor):
            fail(f"sensitivity pair-set hash mismatch for {unit_anchor}")
        if row["source_pair_set_hash"] != source_pair_hashes.get(unit_anchor):
            fail(f"sensitivity source-pair hash mismatch for {unit_anchor}")
        if row["pair_projection_rule"] != PAIR_PROJECTION_RULE:
            fail("sensitivity pair-projection rule changed")
        if row["pair_membership_reliability_scope"] != expected_reliability_scope(unit):
            fail(f"sensitivity reliability scope changed for {unit_anchor}")
        if row["sign_flip"] not in {"true", "false"}:
            fail("sensitivity sign-flip flag is not boolean")
        key = (
            row["research_unit_id"],
            row["pair_set_hash"],
            row["anchor_variant"],
            row["normalization_path"],
            row["evidence_family"],
            row["submetric_name"],
            row["comparison_id"],
            row["sensitivity_mode"],
        )
        grouped[key].append(row)

    expected_group_keys = {
        (*key, mode) for key in source_groups for mode in PAIR_SENSITIVITY_MODES
    }
    if set(grouped) != expected_group_keys:
        missing = sorted(expected_group_keys - set(grouped))
        extra = sorted(set(grouped) - expected_group_keys)
        fail(f"pair/frame sensitivity group coverage changed: missing={missing[:5]} extra={extra[:5]}")

    bucket_counts: Counter[str] = Counter()
    zero_candidate_unit_anchors_seen: set[tuple[str, str]] = set()
    bucket_name = lambda count: (
        "zero"
        if count == 0
        else "one"
        if count == 1
        else "two_to_four"
        if count <= 4
        else "more_than_four"
    )
    for key, group in grouped.items():
        base_key = key[:-1]
        mode = key[-1]
        source_rows = source_groups[base_key]
        unit_anchor = (key[0], key[2])
        frozen_eligible_ids = {
            row["pair_id"]
            for row in source_rows
            if row["pair_eligibility"] == "ELIGIBLE" and row["pair_id"]
        }
        usable_rows = [
            row
            for row in source_rows
            if row["pair_eligibility"] == "ELIGIBLE" and row["directional_delta"]
        ]
        usable_ids = {row["pair_id"] for row in usable_rows}
        if len(usable_ids) != len(usable_rows):
            fail(f"metric-usable pair ids are duplicated in source group {base_key}")
        frozen_count = len(frozen_eligible_ids)
        metric_count = len(usable_rows)
        if frozen_count != eligible_counts[unit_anchor]:
            fail(f"frozen eligible-pair count drifted for {base_key}")
        unique_frames, max_degree, components = pair_graph_counts_from_rows(usable_rows)
        expected_metadata = {
            "frozen_eligible_pair_count": frozen_count,
            "metric_usable_pair_count": metric_count,
            "eligible_pair_count": metric_count,
            "unique_frame_count": unique_frames,
            "max_frame_pair_degree": max_degree,
            "pair_graph_component_count": components,
        }
        for field, expected in expected_metadata.items():
            values = {
                integer_value(row[field], f"{SENSITIVITY_PATH.name}.{field}")
                for row in group
            }
            if values != {expected}:
                fail(f"sensitivity {field} mismatch for {key}: {values} vs {expected}")
        if any(
            row["eligible_pair_count_semantics"]
            != "METRIC_USABLE_SOURCE_ELIGIBLE_PAIRS"
            for row in group
        ):
            fail(f"metric-usable pair-count semantics changed for {key}")
        expected_evidence_state = expected_pair_state(metric_count)
        if any(row["pair_evidence_state"] != expected_evidence_state for row in group):
            fail(f"sensitivity pair evidence state invalid for {key}")
        if any(
            row["sensitivity_state"] != row["leave_one_out_state"]
            for row in group
        ):
            fail(f"sensitivity_state and leave_one_out_state diverge for {key}")
        if metric_count and any(not row["full_median_directional_delta"] for row in group):
            fail(f"metric-usable sensitivity group lacks full median for {key}")
        if not metric_count and any(row["full_median_directional_delta"] for row in group):
            fail(f"zero-usable sensitivity group fabricates a full median for {key}")

        bucket_counts[f"{mode}:{bucket_name(metric_count)}"] += 1
        if candidate_counts[unit_anchor] == 0:
            zero_candidate_unit_anchors_seen.add(unit_anchor)

        if mode == "LEAVE_ONE_PAIR_OUT":
            expected_rows = metric_count if metric_count else 1
            if len(group) != expected_rows:
                fail(f"LOPO row count invalid for {key}: {len(group)} vs {expected_rows}")
            omitted = {row["omitted_pair_id"] for row in group if row["omitted_pair_id"]}
            if omitted != usable_ids or any(row["omitted_frame"] for row in group):
                fail(f"LOPO omitted-pair membership changed for {key}")
            allowed_states = (
                {"NO_ELIGIBLE_PAIRS"}
                if metric_count == 0
                else {"NOT_EVALUABLE"}
                if metric_count == 1
                else {"LOPO_DIRECTION_STABLE", "LOPO_DIRECTION_UNSTABLE"}
            )
        else:
            expected_rows = unique_frames if metric_count else 1
            if len(group) != expected_rows:
                fail(f"LOFO row count invalid for {key}: {len(group)} vs {expected_rows}")
            omitted_frames = {
                str(row["omitted_frame"])
                for row in group
                if row["omitted_frame"] != ""
            }
            expected_frames = {
                str(frame)
                for row in usable_rows
                for frame in (int(row["left_frame"]), int(row["right_frame"]))
            }
            if omitted_frames != expected_frames or any(row["omitted_pair_id"] for row in group):
                fail(f"LOFO omitted-frame membership changed for {key}")
            allowed_states = (
                {"NO_ELIGIBLE_PAIRS"}
                if metric_count == 0
                else {
                    "LOFO_NOT_EVALUABLE",
                    "LOFO_DIRECTION_STABLE",
                    "LOFO_DIRECTION_UNSTABLE",
                    "LOFO_PARTIAL_FRAME_LEVERAGE_UNEVALUABLE",
                }
            )
        states = {row["leave_one_out_state"] for row in group}
        if len(states) != 1 or not states <= allowed_states:
            fail(f"invalid {mode} state for {key}: {states}")

    required_buckets = {
        f"{mode}:{bucket}"
        for mode in PAIR_SENSITIVITY_MODES
        for bucket in ("zero", "one", "two_to_four", "more_than_four")
    }
    missing_pair_count_buckets = required_buckets - set(bucket_counts)
    if missing_pair_count_buckets:
        fail(
            "pair/frame sensitivity output does not exercise all required pair-count states: "
            f"{sorted(missing_pair_count_buckets)}"
        )
    expected_zero_candidate_unit_anchors = {
        key for key, count in candidate_counts.items() if count == 0
    }
    if zero_candidate_unit_anchors_seen != expected_zero_candidate_unit_anchors:
        fail(
            "pair/frame sensitivity does not explicitly cover all zero-candidate groups: "
            f"expected={sorted(expected_zero_candidate_unit_anchors)} "
            f"seen={sorted(zero_candidate_unit_anchors_seen)}"
        )
    return bucket_counts


def validate_parameter_outputs(
    units_by_id: Mapping[str, Mapping[str, str]],
    pair_hashes: Mapping[tuple[str, str], str],
    source_pair_hashes: Mapping[tuple[str, str], str],
    candidate_counts: Mapping[tuple[str, str], int],
    eligible_counts: Mapping[tuple[str, str], int],
) -> None:
    profile_fields, profile_rows = read_csv(PROFILE_PATH)
    require_columns(
        PROFILE_PATH,
        profile_fields,
        (
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "parameter_id",
            "setting_id",
            "parameter_value",
            "other_parameters_fixed_definition",
            "effective_source_px_per_grid_x",
            "effective_source_px_per_grid_y",
            "scale_response_scope",
            "physical_scale_bound_status",
            "evidence_family",
            "evidence_estimator_id",
            "submetric_name",
            "metric_direction",
            "metric_value",
            "metric_value_status",
            "validity_status",
            "pareto_basis_setting_validity_status",
            "validity_status_semantics",
            "valid_setting_count",
            "pareto_nondominated",
            "grid_nondominance_pattern",
            "parameter_interpretation_limit",
            "pareto_basis",
            "pair_membership_rule",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_membership_reliability_scope",
            "pair_set_hash",
            "candidate_pair_count",
            "eligible_pair_count",
            "pair_evidence_state",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "review_status",
        ),
    )
    require_direct_review(profile_rows, PROFILE_PATH.name)
    validate_temporal_direction_applicability(
        profile_rows,
        units_by_id,
        PROFILE_PATH.name,
    )
    if {row["parameter_id"] for row in profile_rows} != set(PARAMETER_GRIDS):
        fail("parameter profile output does not contain exactly five parameter ids")
    if {row["normalization_path"] for row in profile_rows} != NORMALIZATION_PATHS:
        fail("parameter profiles do not contain exactly two normalization paths")
    if {row["anchor_variant"] for row in profile_rows} != ANCHOR_VARIANTS:
        fail("parameter profiles do not contain raw_gt and smoothed_gt")
    if {row["submetric_name"] for row in profile_rows} != set(PROFILE_SUBMETRICS):
        fail(f"parameter profiles do not contain exactly the frozen {len(PROFILE_SUBMETRICS)} submetrics")
    _, sampling_rows = read_csv(SAMPLING_PATH)
    baseline_density_sets: dict[
        tuple[str, str], set[tuple[float, float]]
    ] = defaultdict(set)
    for sampling_row in sampling_rows:
        if (
            sampling_row["representation"] == "CENTER_TRACKED_BODY"
            and sampling_row["axis_rule"] == "GT_DERIVED_UNSIGNED_BODY"
        ):
            baseline_density_sets[
                (
                    sampling_row["research_unit_id"],
                    sampling_row["anchor_variant"],
                )
            ].add(
                (
                    float(sampling_row["source_px_per_grid_x"]),
                    float(sampling_row["source_px_per_grid_y"]),
                )
            )
    if any(len(values) != 1 for values in baseline_density_sets.values()):
        fail("baseline body-window source-pixel density changes across frames/normalizations")
    baseline_densities = {
        key: next(iter(values)) for key, values in baseline_density_sets.items()
    }
    values_by_profile: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    settings_by_profile: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    parameters_by_scope: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    submetrics_by_setting: dict[tuple[str, str, str, str, str], set[str]] = (
        defaultdict(set)
    )
    validity_by_setting: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)
    pareto_metric_statuses_by_setting: dict[
        tuple[str, str, str, str, str], dict[str, str]
    ] = defaultdict(dict)
    reported_valid_counts: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    nondominated_values_by_profile: dict[tuple[str, str, str, str], set[str]] = (
        defaultdict(set)
    )
    patterns_by_profile: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for row in profile_rows:
        key = (
            row["research_unit_id"],
            row["anchor_variant"],
            row["normalization_path"],
            row["parameter_id"],
        )
        values_by_profile[key].add(row["parameter_value"])
        settings_by_profile[key].add(row["setting_id"])
        parameters_by_scope[key[:3]].add(row["parameter_id"])
        setting_key = (
            row["research_unit_id"],
            row["anchor_variant"],
            row["normalization_path"],
            row["parameter_id"],
            row["setting_id"],
        )
        submetrics_by_setting[setting_key].add(row["submetric_name"])
        setting_validity_status = row["pareto_basis_setting_validity_status"]
        if (
            row["validity_status"] != setting_validity_status
            or row["validity_status_semantics"]
            != "SETTING_LEVEL_PARETO_BASIS_STATUS_NOT_ROW_METRIC_AVAILABILITY"
        ):
            fail(
                "parameter-profile validity status no longer has the frozen "
                "setting-level Pareto-basis semantics"
            )
        validity_by_setting[setting_key].add(setting_validity_status)
        patterns_by_profile[key].add(row["grid_nondominance_pattern"])
        if row["pareto_nondominated"] == "true":
            nondominated_values_by_profile[key].add(row["parameter_value"])
        try:
            reported_valid_counts[key].add(int(row["valid_setting_count"]))
        except ValueError as exc:
            fail(f"parameter profile has invalid valid-setting count: {exc}")
        expected_family, expected_direction, expected_estimator = PROFILE_SUBMETRICS[
            row["submetric_name"]
        ]
        if (
            row["evidence_family"] != expected_family
            or row["metric_direction"] != expected_direction
            or row["evidence_estimator_id"] != expected_estimator
        ):
            fail(
                f"parameter-profile family/direction changed for {row['submetric_name']}"
            )
        if (
            row["other_parameters_fixed_definition"]
            != "ALL_OTHER_PARAMETERS_AT_GT_DERIVED_BASELINE"
        ):
            fail("a parameter profile changes more than the named parameter")
        if row["grid_nondominance_pattern"] not in GRID_NONDOMINANCE_PATTERNS:
            fail("parameter profile has an invalid grid-nondominance pattern")
        if row["parameter_interpretation_limit"] != parameter_interpretation_limit(
            row["parameter_id"]
        ):
            fail("parameter interpretation limit changed")
        if row["pareto_basis"] != PARETO_BASIS_TEXT:
            fail("parameter-profile Pareto basis changed")
        effective_density_x = finite_float(
            row["effective_source_px_per_grid_x"],
            f"{PROFILE_PATH.name}.effective_source_px_per_grid_x",
        )
        effective_density_y = finite_float(
            row["effective_source_px_per_grid_y"],
            f"{PROFILE_PATH.name}.effective_source_px_per_grid_y",
        )
        if effective_density_x <= 0.0 or effective_density_y <= 0.0:
            fail("parameter profile has a non-positive effective source-pixel density")
        unit_anchor = (row["research_unit_id"], row["anchor_variant"])
        baseline_density = baseline_densities.get(unit_anchor)
        if baseline_density is None:
            fail(f"parameter profile lacks baseline sampling density for {unit_anchor}")
        parameter_value = float(row["parameter_value"])
        expected_density_x = baseline_density[0] * (
            parameter_value if row["parameter_id"] == "LONG_SCALE" else 1.0
        )
        expected_density_y = baseline_density[1] * (
            parameter_value if row["parameter_id"] == "SHORT_SCALE" else 1.0
        )
        if (
            abs(effective_density_x - expected_density_x) > 3e-6
            or abs(effective_density_y - expected_density_y) > 3e-6
        ):
            fail("parameter effective source-pixel density drifted from W-1/H-1 sampling")
        is_scale = row["parameter_id"] in {"LONG_SCALE", "SHORT_SCALE"}
        expected_scale_scope = (
            "WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED"
            if is_scale
            else "NOT_A_SCALE_PROFILE"
        )
        expected_physical_scale_status = (
            "NOT_EVALUATED_FIXED_GRID_RESAMPLING_CONFOUND"
            if is_scale
            else "NOT_APPLICABLE"
        )
        if (
            row["scale_response_scope"] != expected_scale_scope
            or row["physical_scale_bound_status"] != expected_physical_scale_status
        ):
            fail("scale-profile resampling/physical-bound contract changed")
        if row["pareto_nondominated"] not in {"true", "false"}:
            fail("invalid Pareto nondominated flag")
        if setting_validity_status not in {
            "PASS",
            "NORMALIZATION_FAILURE_PRESENT",
            "NONFINITE_PARETO_METRIC_PRESENT",
        }:
            fail("invalid parameter-setting validity status")
        if setting_validity_status != "PASS" and row["pareto_nondominated"] != "false":
            fail("invalid parameter setting entered the Pareto feasible set")
        unit = units_by_id[row["research_unit_id"]]
        candidate_pair_count = integer_value(
            row["candidate_pair_count"],
            f"{PROFILE_PATH.name}.candidate_pair_count",
        )
        eligible_pair_count = integer_value(
            row["eligible_pair_count"],
            f"{PROFILE_PATH.name}.eligible_pair_count",
        )
        metric_value_text = row["metric_value"].strip()
        if metric_value_text:
            try:
                metric_value = float(metric_value_text)
            except ValueError as exc:
                fail(f"parameter profile has a malformed metric value: {exc}")
        else:
            metric_value = math.nan
        if math.isfinite(metric_value):
            expected_metric_value_status = "AVAILABLE_FINITE"
        elif (
            row["submetric_name"].startswith("NONADJACENT_")
            and eligible_pair_count == 0
        ):
            expected_metric_value_status = "UNAVAILABLE_NO_ELIGIBLE_PAIRS"
        else:
            expected_metric_value_status = "UNAVAILABLE_NONFINITE_METRIC"
        if row["metric_value_status"] != expected_metric_value_status:
            fail(
                "parameter-profile metric availability status mismatch for "
                f"{setting_key}.{row['submetric_name']}: "
                f"{row['metric_value_status']} vs {expected_metric_value_status}"
            )
        if row["submetric_name"] in PARETO_BASIS:
            pareto_metric_statuses_by_setting[setting_key][row["submetric_name"]] = (
                row["metric_value_status"]
            )
        if (
            row["pair_membership_rule"] != PAIR_MEMBERSHIP_RULE
            or row["source_pair_set_hash"] != source_pair_hashes.get(unit_anchor)
            or row["pair_projection_rule"] != PAIR_PROJECTION_RULE
            or row["pair_membership_reliability_scope"]
            != expected_reliability_scope(unit)
            or row["pair_set_hash"] != pair_hashes.get(unit_anchor)
            or candidate_pair_count != candidate_counts.get(unit_anchor)
            or eligible_pair_count != eligible_counts.get(unit_anchor)
            or row["pair_evidence_state"]
            != expected_pair_state(eligible_counts.get(unit_anchor, -1))
        ):
            fail(f"parameter profile pair membership drifted for {unit_anchor}")
    for setting_key, states in validity_by_setting.items():
        if len(states) != 1:
            fail(f"validity status changes across submetrics for {setting_key}")
        setting_validity_status = next(iter(states))
        pareto_metric_statuses = pareto_metric_statuses_by_setting[setting_key]
        if set(pareto_metric_statuses) != set(PARETO_BASIS):
            fail(f"parameter setting lacks a frozen Pareto-basis metric: {setting_key}")
        pareto_metrics_all_finite = all(
            status == "AVAILABLE_FINITE"
            for status in pareto_metric_statuses.values()
        )
        if setting_validity_status == "PASS" and not pareto_metrics_all_finite:
            fail(f"PASS setting contains a nonfinite Pareto-basis metric: {setting_key}")
        if (
            setting_validity_status == "NONFINITE_PARETO_METRIC_PRESENT"
            and pareto_metrics_all_finite
        ):
            fail(
                "NONFINITE_PARETO_METRIC_PRESENT setting has only finite "
                f"Pareto-basis metrics: {setting_key}"
            )
    for key, values in values_by_profile.items():
        if values != PARAMETER_GRIDS[key[3]]:
            fail(f"parameter grid changed for {key}: {sorted(values)}")
        if len(settings_by_profile[key]) != 5:
            fail(f"expected five setting ids for {key}")
        setting_states = [
            next(iter(states))
            for setting_key, states in validity_by_setting.items()
            if setting_key[:4] == key
        ]
        actual_valid_count = sum(state == "PASS" for state in setting_states)
        if reported_valid_counts[key] != {actual_valid_count}:
            fail(f"reported valid-setting count mismatch for {key}")
        patterns = patterns_by_profile[key]
        if len(patterns) != 1:
            fail(f"grid-nondominance pattern changes within profile {key}")
        expected_pattern, _, _, _, _, _ = classify_grid_pattern(
            key[3], nondominated_values_by_profile[key]
        )
        if patterns != {expected_pattern}:
            fail(
                f"reported grid-nondominance pattern mismatch for {key}: "
                f"{patterns} vs {expected_pattern}"
            )
    if any(
        parameters != set(PARAMETER_GRIDS)
        for parameters in parameters_by_scope.values()
    ):
        fail("a unit/anchor/normalization scope lacks one of the five parameter ids")
    expected_profile_unit_anchors = {
        (unit_id, anchor_variant)
        for unit_id in units_by_id
        for anchor_variant in ("raw_gt", "smoothed_gt")
    }
    if {key[:2] for key in parameters_by_scope} != expected_profile_unit_anchors:
        fail("parameter profiles do not cover raw_gt and smoothed_gt for every unit")
    profile_paths_by_unit_anchor: dict[tuple[str, str], set[str]] = defaultdict(set)
    for research_unit_id, anchor_variant, normalization_path in parameters_by_scope:
        profile_paths_by_unit_anchor[(research_unit_id, anchor_variant)].add(
            normalization_path
        )
    if any(
        paths != NORMALIZATION_PATHS
        for paths in profile_paths_by_unit_anchor.values()
    ):
        fail("a unit/anchor parameter profile lacks one normalization path")
    if any(
        submetrics != set(PROFILE_SUBMETRICS)
        for submetrics in submetrics_by_setting.values()
    ):
        fail(f"a parameter setting lacks one of the frozen {len(PROFILE_SUBMETRICS)} submetrics")

    observability_fields, observability_rows = read_csv(OBSERVABILITY_PATH)
    require_columns(
        OBSERVABILITY_PATH,
        observability_fields,
        (
            "scope_level",
            "research_unit_id",
            "counterfactual_semantic_class",
            "parameter_id",
            "anchor_variant",
            "evidence_family",
            "evidence_estimator_contract",
            "normalization_path",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_set_hash",
            "candidate_pair_count",
            "eligible_pair_count",
            "pair_evidence_state",
            "pair_usage_in_grid_nondominance",
            "pareto_nondominated_grid_values",
            "grid_nondominance_pattern",
            "nondominated_grid_component_count",
            "touches_lower_grid_edge",
            "touches_upper_grid_edge",
            "reported_lower_bound",
            "reported_upper_bound",
            "diagnostic_grid_min",
            "diagnostic_grid_max",
            "parameter_interpretation_limit",
            "valid_setting_count",
            "profile_validity_state",
            "normalization_agreement",
            "fixed_rule_replay_scope",
            "placebo_relation",
            "observability_state",
            "decision_reason",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "review_status",
        ),
    )
    require_direct_review(observability_rows, OBSERVABILITY_PATH.name)
    require_unit_semantics(
        observability_rows,
        units_by_id,
        OBSERVABILITY_PATH.name,
        allow_core_aggregate=True,
    )
    validate_temporal_direction_applicability(
        observability_rows,
        units_by_id,
        OBSERVABILITY_PATH.name,
        allow_core_aggregate=True,
    )
    if {row["parameter_id"] for row in observability_rows} != set(PARAMETER_GRIDS):
        fail("observability output does not contain exactly five parameter ids")
    if {row["anchor_variant"] for row in observability_rows} != ANCHOR_VARIANTS:
        fail("observability output does not contain both anchor variants")

    parameters_by_observability_scope: dict[tuple[str, str, str, str], set[str]] = (
        defaultdict(set)
    )
    unit_anchor_scope_paths: dict[tuple[str, str], set[tuple[str, str]]] = (
        defaultdict(set)
    )
    observability_by_key: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    for row in observability_rows:
        if (
            row["evidence_family"] != OBSERVABILITY_EVIDENCE_FAMILY
            or row["evidence_estimator_contract"] != OBSERVABILITY_ESTIMATOR_CONTRACT
        ):
            fail("observability evidence/proxy contract changed")
        valid_setting_count = integer_value(
            row["valid_setting_count"],
            f"{OBSERVABILITY_PATH.name}.valid_setting_count",
        )
        if not 0 <= valid_setting_count <= 5:
            fail("observability valid-setting count is outside the frozen grid")
        if not row["decision_reason"].strip():
            fail("observability decision reason is empty")
        if row["profile_validity_state"] not in {
            "PASS",
            "PARTIAL_VALID_SETTINGS",
            "NO_VALID_SETTINGS",
            "NO_VALID_SETTINGS_IN_ONE_OR_MORE_PATHS",
            "NO_VALID_SETTINGS_IN_ONE_OR_MORE_CORE_VEHICLES",
        }:
            fail("observability profile-validity state is invalid")
        if row["observability_state"] != "NOT_IDENTIFIABLE":
            fail("formal parameter observability must remain NOT_IDENTIFIABLE")
        if row["reported_lower_bound"] or row["reported_upper_bound"]:
            fail("diagnostic grid nondominance was converted into a physical bound")
        if row["parameter_interpretation_limit"] != parameter_interpretation_limit(
            row["parameter_id"]
        ):
            fail("observability parameter interpretation limit changed")
        if row["grid_nondominance_pattern"] not in GRID_NONDOMINANCE_PATTERNS:
            fail("observability grid-nondominance pattern is invalid")
        nondominated_values = {
            value
            for value in row["pareto_nondominated_grid_values"].split(";")
            if value
        }
        (
            expected_pattern,
            expected_components,
            expected_lower,
            expected_upper,
            expected_min,
            expected_max,
        ) = classify_grid_pattern(row["parameter_id"], nondominated_values)
        if (
            row["grid_nondominance_pattern"] != expected_pattern
            or integer_value(
                row["nondominated_grid_component_count"],
                f"{OBSERVABILITY_PATH.name}.nondominated_grid_component_count",
            )
            != expected_components
            or row["touches_lower_grid_edge"] != str(expected_lower).lower()
            or row["touches_upper_grid_edge"] != str(expected_upper).lower()
            or row["diagnostic_grid_min"] != expected_min
            or row["diagnostic_grid_max"] != expected_max
        ):
            fail("observability grid-pattern diagnostics are internally inconsistent")
        expected_placebo = (
            "PENDING_AXIS_PLACEBO_REVIEW"
            if row["parameter_id"] == "AXIS_UNSIGNED"
            else "NOT_APPLICABLE"
        )
        if row["placebo_relation"] != expected_placebo:
            fail("observability axis-placebo relation changed")

        scope_level = row["scope_level"]
        if scope_level not in {
            "UNIT_NORMALIZATION",
            "UNIT_DUAL_NORMALIZATION",
            "CORE_VEHICLE_AGGREGATE",
        }:
            fail(f"invalid observability scope: {scope_level}")
        if row["pair_projection_rule"] != PAIR_PROJECTION_RULE:
            fail("observability pair-projection rule changed")
        if scope_level == "CORE_VEHICLE_AGGREGATE":
            if any(
                row[field]
                for field in (
                    "source_pair_set_hash",
                    "pair_set_hash",
                    "candidate_pair_count",
                    "eligible_pair_count",
                )
            ):
                fail("core aggregate observability row claims one unit-level pair set")
            if (
                row["pair_evidence_state"]
                != "MIXED_CORE_VEHICLE_PAIR_SUPPORT_SEE_UNIT_ROWS"
                or row["pair_usage_in_grid_nondominance"]
                != "MULTIPLE_SEPARATE_CORE_PAIR_SETS;NOT_USED_IN_PARETO_BASIS;"
                "SEE_PROFILE_AND_SENSITIVITY"
            ):
                fail("core aggregate observability mixed-pair scope changed")
        else:
            unit_anchor = (row["research_unit_id"], row["anchor_variant"])
            candidate_pair_count = integer_value(
                row["candidate_pair_count"],
                f"{OBSERVABILITY_PATH.name}.candidate_pair_count",
            )
            eligible_pair_count = integer_value(
                row["eligible_pair_count"],
                f"{OBSERVABILITY_PATH.name}.eligible_pair_count",
            )
            if (
                row["source_pair_set_hash"] != source_pair_hashes.get(unit_anchor)
                or row["pair_set_hash"] != pair_hashes.get(unit_anchor)
                or candidate_pair_count != candidate_counts.get(unit_anchor)
                or eligible_pair_count != eligible_counts.get(unit_anchor)
                or row["pair_evidence_state"]
                != expected_pair_state(eligible_counts.get(unit_anchor, -1))
                or row["pair_usage_in_grid_nondominance"]
                != "NOT_USED_IN_PARETO_BASIS;CARRIED_FOR_CONTEXT_ONLY"
            ):
                fail(f"observability unit pair provenance drifted for {unit_anchor}")
        scope_key = (
            scope_level,
            row["research_unit_id"],
            row["anchor_variant"],
            row["normalization_path"],
        )
        parameters_by_observability_scope[scope_key].add(row["parameter_id"])
        row_key = (*scope_key, row["parameter_id"])
        if row_key in observability_by_key:
            fail(f"duplicate observability row: {row_key}")
        observability_by_key[row_key] = row
        if scope_level != "CORE_VEHICLE_AGGREGATE":
            unit_anchor_scope_paths[
                (row["research_unit_id"], row["anchor_variant"])
            ].add((scope_level, row["normalization_path"]))

        if scope_level == "UNIT_NORMALIZATION":
            normalization_path = row["normalization_path"]
            if normalization_path not in NORMALIZATION_PATHS:
                fail("unit-normalization observability row has invalid normalization path")
            profile_key = (
                row["research_unit_id"],
                row["anchor_variant"],
                normalization_path,
                row["parameter_id"],
            )
            expected_values = nondominated_values_by_profile[profile_key]
            profile_valid_count = next(iter(reported_valid_counts[profile_key]))
            expected_validity = (
                "PASS"
                if profile_valid_count == 5
                else "PARTIAL_VALID_SETTINGS"
                if profile_valid_count
                else "NO_VALID_SETTINGS"
            )
            if (
                nondominated_values != expected_values
                or valid_setting_count != profile_valid_count
                or row["profile_validity_state"] != expected_validity
                or row["normalization_agreement"] != "SINGLE_PATH_ONLY"
                or row["fixed_rule_replay_scope"]
                != units_by_id[row["research_unit_id"]]["replay_status"]
            ):
                fail(f"unit-normalization observability row drifted: {row_key}")
        elif scope_level == "UNIT_DUAL_NORMALIZATION":
            if row["normalization_path"] != UNIT_DUAL_NORMALIZATION_PATH:
                fail("dual-normalization observability path changed")
            fixed_key = (
                row["research_unit_id"],
                row["anchor_variant"],
                "FIXED_REFERENCE",
                row["parameter_id"],
            )
            local_key = (
                row["research_unit_id"],
                row["anchor_variant"],
                "CANDIDATE_LOCAL_REESTIMATED",
                row["parameter_id"],
            )
            fixed_values = nondominated_values_by_profile[fixed_key]
            local_values = nondominated_values_by_profile[local_key]
            fixed_count = next(iter(reported_valid_counts[fixed_key]))
            local_count = next(iter(reported_valid_counts[local_key]))
            expected_values = fixed_values & local_values if fixed_count and local_count else set()
            expected_agreement = (
                "INVALID_NORMALIZATION_OR_METRIC_PROFILE"
                if not fixed_count or not local_count
                else "NORMALIZATION_DEPENDENT"
                if not expected_values
                else "IDENTICAL_GRID_NONDOMINANCE_PATTERN"
                if fixed_values == local_values
                else "PARTIAL_GRID_NONDOMINANCE_OVERLAP"
            )
            expected_validity = (
                "PASS"
                if fixed_count == 5 and local_count == 5
                else "PARTIAL_VALID_SETTINGS"
                if fixed_count and local_count
                else "NO_VALID_SETTINGS_IN_ONE_OR_MORE_PATHS"
            )
            if (
                nondominated_values != expected_values
                or valid_setting_count != min(fixed_count, local_count)
                or row["profile_validity_state"] != expected_validity
                or row["normalization_agreement"] != expected_agreement
                or row["fixed_rule_replay_scope"]
                != units_by_id[row["research_unit_id"]]["replay_status"]
            ):
                fail(f"dual-normalization observability row drifted: {row_key}")
        else:
            if (
                row["research_unit_id"] != "GM_RM017_CORE_VEHICLES"
                or row["normalization_path"] != CORE_AGGREGATE_NORMALIZATION_PATH
                or row["fixed_rule_replay_scope"]
                != "TWO_WITHIN_SCENE_OTHER_VEHICLE_FIXED_RULE_REPLAYS"
            ):
                fail("core aggregate observability scope changed")

    if any(
        parameters != set(PARAMETER_GRIDS)
        for parameters in parameters_by_observability_scope.values()
    ):
        fail("an observability scope lacks one of the five parameter ids")
    expected_unit_scope_paths = {
        *(("UNIT_NORMALIZATION", path) for path in NORMALIZATION_PATHS),
        ("UNIT_DUAL_NORMALIZATION", UNIT_DUAL_NORMALIZATION_PATH),
    }
    expected_unit_anchor_keys = set(profile_paths_by_unit_anchor)
    if set(unit_anchor_scope_paths) != expected_unit_anchor_keys:
        fail("observability unit/anchor coverage differs from parameter profiles")
    if any(paths != expected_unit_scope_paths for paths in unit_anchor_scope_paths.values()):
        fail("a unit/anchor lacks dual-path observability coverage")
    aggregate_keys = {
        key
        for key in parameters_by_observability_scope
        if key[0] == "CORE_VEHICLE_AGGREGATE"
    }
    expected_aggregate_keys = {
        (
            "CORE_VEHICLE_AGGREGATE",
            "GM_RM017_CORE_VEHICLES",
            anchor_variant,
            CORE_AGGREGATE_NORMALIZATION_PATH,
        )
        for anchor_variant in ANCHOR_VARIANTS
    }
    if aggregate_keys != expected_aggregate_keys:
        fail("core-vehicle fixed-rule aggregate observability coverage changed")

    positive_ids = sorted(
        unit_id
        for unit_id, unit in units_by_id.items()
        if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
    )
    for anchor_variant in ANCHOR_VARIANTS:
        for parameter_id in PARAMETER_GRIDS:
            aggregate_key = (
                "CORE_VEHICLE_AGGREGATE",
                "GM_RM017_CORE_VEHICLES",
                anchor_variant,
                CORE_AGGREGATE_NORMALIZATION_PATH,
                parameter_id,
            )
            aggregate = observability_by_key[aggregate_key]
            dual_rows = [
                observability_by_key[
                    (
                        "UNIT_DUAL_NORMALIZATION",
                        unit_id,
                        anchor_variant,
                        UNIT_DUAL_NORMALIZATION_PATH,
                        parameter_id,
                    )
                ]
                for unit_id in positive_ids
            ]
            value_sets = [
                {value for value in row["pareto_nondominated_grid_values"].split(";") if value}
                for row in dual_rows
            ]
            valid_counts = [int(row["valid_setting_count"]) for row in dual_rows]
            profiles_usable = all(count > 0 for count in valid_counts)
            profiles_complete = all(row["profile_validity_state"] == "PASS" for row in dual_rows)
            expected_values = (
                set.intersection(*value_sets)
                if profiles_usable and value_sets and all(value_sets)
                else set()
            )
            expected_agreement = (
                "INVALID_NORMALIZATION_OR_METRIC_PROFILE"
                if not profiles_usable
                else "DEVELOPMENT_AND_TWO_WITHIN_SCENE_OTHER_VEHICLE_COMMON_GRID_NONDOMINANCE_PATTERN"
                if expected_values
                else "NO_COMMON_DEVELOPMENT_OTHER_VEHICLE_GRID_NONDOMINANCE_PATTERN"
            )
            expected_validity = (
                "PASS"
                if profiles_complete
                else "PARTIAL_VALID_SETTINGS"
                if profiles_usable
                else "NO_VALID_SETTINGS_IN_ONE_OR_MORE_CORE_VEHICLES"
            )
            aggregate_values = {
                value
                for value in aggregate["pareto_nondominated_grid_values"].split(";")
                if value
            }
            if (
                aggregate_values != expected_values
                or int(aggregate["valid_setting_count"]) != min(valid_counts)
                or aggregate["profile_validity_state"] != expected_validity
                or aggregate["normalization_agreement"] != expected_agreement
            ):
                fail(f"core aggregate observability row drifted: {aggregate_key}")


def validate_visuals_and_reviews(
    units_by_id: Mapping[str, Mapping[str, str]],
    required_review_units: set[str],
) -> tuple[int, int]:
    manifest_fields, manifest_rows = read_csv(VISUAL_MANIFEST_PATH)
    require_columns(
        VISUAL_MANIFEST_PATH,
        manifest_fields,
        (
            "case_id",
            "artifact_type",
            "research_unit_id",
            "counterfactual_semantic_class",
            "artifact_path",
            "review_status",
        ),
    )
    require_direct_review(manifest_rows, VISUAL_MANIFEST_PATH.name)
    if len(manifest_rows) != 20:
        fail(f"visual manifest must contain exactly 20 frozen artifacts, got {len(manifest_rows)}")
    case_ids = [row["case_id"] for row in manifest_rows]
    if len(case_ids) != len(set(case_ids)):
        fail("visual manifest case ids are not unique")
    artifact_paths = [Path(row["artifact_path"]) for row in manifest_rows]
    if len(artifact_paths) != len({str(path) for path in artifact_paths}):
        fail("visual manifest artifact paths are not unique")
    for path in artifact_paths:
        if not path.is_absolute() or not path.exists():
            fail(f"missing or non-absolute temporary visual path: {path}")
        ensure_outside_repo(path, "temporary visual")
        try:
            path.resolve().relative_to(VISUAL_ROOT.resolve())
        except ValueError:
            fail(
                f"temporary visual is outside the declared workspace output root: {path}"
            )
        if path.suffix.lower() != ".png":
            fail(f"unexpected visual artifact suffix: {path}")

    manifest_counts = Counter(row["research_unit_id"] for row in manifest_rows)
    manifest_classes: dict[str, set[str]] = defaultdict(set)
    for row in manifest_rows:
        manifest_classes[row["research_unit_id"]].add(
            row["counterfactual_semantic_class"]
        )
    expected_visual_units = set(required_review_units) | {"GLOBAL"}
    if len(expected_visual_units) != 14:
        fail("visual-review entity registry must contain 14 entities including GLOBAL")
    if set(manifest_counts) != expected_visual_units:
        fail(
            "visual manifest unit coverage changed: "
            f"expected={sorted(expected_visual_units)} seen={sorted(manifest_counts)}"
        )
    if any(len(classes) != 1 for classes in manifest_classes.values()):
        fail("visual manifest semantic class changes within a research unit")
    for unit_id in required_review_units:
        manifest_class = next(iter(manifest_classes[unit_id]))
        if manifest_class != units_by_id[unit_id]["counterfactual_semantic_class"]:
            fail(f"visual manifest semantic class mismatch for {unit_id}")

    review_fields, review_rows = read_csv(VISUAL_REVIEW_PATH)
    required_review_columns = (
        "review_id",
        "research_unit_id",
        "counterfactual_semantic_class",
        "reviewed_artifact_count",
        "review_status",
        "visual_finding_cn",
        "equal_support_interpretation_cn",
        "normalization_interpretation_cn",
        "pair_interpretation_cn",
        "axis_placebo_interpretation_cn",
        "parameter_observability_cn",
        "class_or_temporal_interpretation_cn",
        "decision",
    )
    require_columns(VISUAL_REVIEW_PATH, review_fields, required_review_columns)
    require_direct_review(review_rows, VISUAL_REVIEW_PATH.name)
    if len(review_rows) != 14:
        fail(f"visual reviews must contain exactly 14 rows, got {len(review_rows)}")
    review_ids = [row["review_id"] for row in review_rows]
    if len(review_ids) != len(set(review_ids)):
        fail("visual review ids are not unique")
    reviewed_units = {row["research_unit_id"] for row in review_rows}
    if len(reviewed_units) != len(review_rows):
        fail("visual reviews must contain exactly one row per reviewed unit")
    if reviewed_units != expected_visual_units:
        fail(
            "visual reviews do not cover every generated artifact group: "
            f"expected={sorted(expected_visual_units)} seen={sorted(reviewed_units)}"
        )
    text_columns = required_review_columns[5:]
    for row in review_rows:
        unit_id = row["research_unit_id"]
        try:
            reviewed_artifact_count = int(row["reviewed_artifact_count"])
        except ValueError as exc:
            fail(f"visual review has invalid artifact count: {exc}")
        if reviewed_artifact_count != manifest_counts[unit_id]:
            fail(
                f"visual review artifact count mismatch for {unit_id}: "
                f"{reviewed_artifact_count} vs {manifest_counts[unit_id]}"
            )
        if any(not row[column].strip() for column in text_columns):
            fail(f"visual review contains an empty interpretation: {row['review_id']}")
        if row["decision"] not in VISUAL_DECISIONS_ALLOWED:
            fail(f"visual review uses an uncontrolled decision: {row['review_id']}")
        expected_semantic_class = next(iter(manifest_classes[unit_id]))
        if row["counterfactual_semantic_class"] != expected_semantic_class:
            fail(f"visual review semantic class mismatch: {row['review_id']}")
    return len(manifest_rows), len(review_rows)


def validate_stage_conclusions() -> list[dict[str, str]]:
    fields, rows = read_csv(STAGE_CONCLUSION_PATH)
    required = (
        "conclusion_id",
        "status",
        "development_evidence",
        "heldout_evidence",
        "counterfactual_evidence",
        "normalization_state",
        "pair_sensitivity_state",
        "blocking_reason",
        "latent_support_reconstruction_allowed",
        "s1d_allowed",
        "automatic_annotation_allowed",
        "review_status",
    )
    require_columns(STAGE_CONCLUSION_PATH, fields, required)
    if len(rows) != 10 or {row["conclusion_id"] for row in rows} != CONCLUSION_IDS:
        fail("stage conclusions must contain exactly the ten decomposed conclusion ids")
    require_direct_review(rows, STAGE_CONCLUSION_PATH.name)
    evidence_columns = required[1:8]
    for row in rows:
        if any(not row[column].strip() for column in evidence_columns):
            fail(
                f"stage conclusion has an empty evidence/status field: {row['conclusion_id']}"
            )
        if row["status"] not in CONCLUSION_STATUS_ALLOWED[row["conclusion_id"]]:
            fail(f"stage conclusion uses an uncontrolled status: {row['conclusion_id']}")
        if row["normalization_state"] not in NORMALIZATION_STATE_ALLOWED:
            fail(f"stage conclusion uses an uncontrolled normalization state: {row['conclusion_id']}")
        if row["pair_sensitivity_state"] not in PAIR_SENSITIVITY_STATE_ALLOWED:
            fail(f"stage conclusion uses an uncontrolled pair-sensitivity state: {row['conclusion_id']}")
        require_false(
            row["latent_support_reconstruction_allowed"],
            f"{row['conclusion_id']}.latent_support_reconstruction_allowed",
        )
        require_false(row["s1d_allowed"], f"{row['conclusion_id']}.s1d_allowed")
        require_false(
            row["automatic_annotation_allowed"],
            f"{row['conclusion_id']}.automatic_annotation_allowed",
        )
    return rows


def validate_summary_replay_and_report(
    unit_rows: Sequence[Mapping[str, str]],
    spatial_groups: set[str],
    parameter_envelope_groups: set[str],
    visual_count: int,
) -> None:
    if not SUMMARY_PATH.exists():
        fail(f"missing runner summary: {SUMMARY_PATH}")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary.get("review_status") != "directly_reviewed_complete":
        fail("runner summary is not directly_reviewed_complete")
    if int(summary.get("research_unit_count", -1)) != len(unit_rows):
        fail("runner summary research-unit count mismatch")
    if summary.get("config_hash") != EXPECTED_CONFIG_HASH:
        fail("runner summary config hash changed")
    if summary.get("anchor_variants") != ["raw_gt", "smoothed_gt"]:
        fail("runner summary anchor-variant contract changed")
    if summary.get("all_units_run_both_anchor_variants") is not True:
        fail("runner summary does not confirm dual-anchor replay for all units")
    if (
        summary.get("pair_membership_reference") != PAIR_MEMBERSHIP_REFERENCE
        or summary.get("pair_projection_rule") != PAIR_PROJECTION_RULE
        or summary.get("pair_sensitivity_modes")
        != ["LEAVE_ONE_PAIR_OUT", "LEAVE_ONE_FRAME_OUT"]
        or summary.get("normalization_failure_policy") != NORMALIZATION_FAILURE_POLICY
        or summary.get("body_oriented_window_attribution")
        != BODY_ORIENTED_WINDOW_ATTRIBUTION
        or summary.get("parameter_observability_contract")
        != PARAMETER_OBSERVABILITY_CONTRACT
        or summary.get("scale_profile_contract") != SCALE_PROFILE_CONTRACT
        or summary.get("temporal_test_contract") != TEMPORAL_TEST_CONTRACT
        or summary.get("orientation_estimator") != "STRUCTURE_TENSOR_ORIENTATION_PROXY"
        or summary.get("topology_estimator") != THIN_EDGE_ESTIMATOR
        or summary.get("canny_config") != EXPECTED_CANNY_CONFIG
        or summary.get("structure_boundary_guard")
        != EXPECTED_STRUCTURE_BOUNDARY_GUARD
    ):
        fail("runner summary semantic/proxy contract changed")
    if (
        summary.get("optical_condition_execution_status")
        != OPTICAL_CONDITION_EXECUTION_STATUS
        or summary.get("optical_conditioned_support_readiness")
        != OPTICAL_CONDITIONED_SUPPORT_READINESS
    ):
        fail("runner summary overstates real optical-conditioned readiness")
    expected_semantic_counts = dict(
        Counter(row["counterfactual_semantic_class"] for row in unit_rows)
    )
    if summary.get("semantic_class_counts") != expected_semantic_counts:
        fail("runner summary semantic-class counts mismatch")
    if int(summary.get("pv002_geometry_background_control_count", -1)) != 4:
        fail("runner summary PV002-geometry background-control count mismatch")
    if int(summary.get("background_spatial_control_group_count", -1)) != len(
        spatial_groups
    ):
        fail("runner summary baseline spatial-control group count mismatch")
    if int(summary.get("background_parameter_envelope_group_count", -1)) != len(
        parameter_envelope_groups
    ):
        fail("runner summary parameter-envelope group count mismatch")
    if summary.get("background_cluster_scope") != BACKGROUND_CLUSTER_SCOPE:
        fail("runner summary background clustering/statistical-independence scope changed")
    if int(summary.get("visual_artifact_count", -1)) != visual_count:
        fail("runner summary visual count mismatch")

    generated_rows = {
        "sampling_row_count": read_csv(SAMPLING_PATH)[1],
        "representation_metric_row_count": read_csv(REPRESENTATION_PATH)[1],
        "pair_metric_row_count": read_csv(PAIR_PATH)[1],
        "parameter_profile_row_count": read_csv(PROFILE_PATH)[1],
        "observability_row_count": read_csv(OBSERVABILITY_PATH)[1],
    }
    for summary_key, rows in generated_rows.items():
        if int(summary.get(summary_key, -1)) != len(rows):
            fail(f"runner summary row count mismatch: {summary_key}")
    _, sensitivity_rows = read_csv(SENSITIVITY_PATH)
    expected_lopo_count = sum(
        row["sensitivity_mode"] == "LEAVE_ONE_PAIR_OUT" for row in sensitivity_rows
    )
    expected_lofo_count = sum(
        row["sensitivity_mode"] == "LEAVE_ONE_FRAME_OUT" for row in sensitivity_rows
    )
    if (
        int(summary.get("leave_one_pair_out_row_count", -1)) != expected_lopo_count
        or int(summary.get("leave_one_frame_out_row_count", -1)) != expected_lofo_count
        or int(summary.get("pair_and_frame_sensitivity_row_count", -1))
        != len(sensitivity_rows)
    ):
        fail("runner summary LOPO/LOFO row counts mismatch")
    require_false(
        summary.get("latent_support_reconstruction_run"),
        "summary.latent_support_reconstruction_run",
    )
    require_false(summary.get("s1d_allowed"), "summary.s1d_allowed")
    require_false(
        summary.get("automatic_annotation_allowed"),
        "summary.automatic_annotation_allowed",
    )
    if summary.get("unique_box_recovery") != "NOT_EVALUATED_NOT_AUTHORIZED":
        fail("unique-box recovery boundary changed")
    if summary.get("forbidden_methods_used") != []:
        fail(
            f"runner reports forbidden methods: {summary.get('forbidden_methods_used')}"
        )

    output_map = {
        "research_units": UNIT_PATH,
        "sampling_normalization": SAMPLING_PATH,
        "representation_metrics": REPRESENTATION_PATH,
        "pair_incremental_metrics": PAIR_PATH,
        "pair_and_frame_sensitivity": SENSITIVITY_PATH,
        "parameter_profiles": PROFILE_PATH,
        "parameter_observability": OBSERVABILITY_PATH,
        "visual_manifest": VISUAL_MANIFEST_PATH,
        "temporary_visuals": VISUAL_ROOT,
    }
    summary_outputs = summary.get("outputs", {})
    if not isinstance(summary_outputs, dict) or set(summary_outputs) != set(output_map):
        fail("runner summary output whitelist changed")
    for key, expected_path in output_map.items():
        actual = summary_outputs.get(key)
        if not actual or Path(actual).resolve() != expected_path.resolve():
            fail(f"runner summary output path mismatch for {key}: {actual}")

    if not REPLAY_PATH.exists():
        fail(f"missing replay result: {REPLAY_PATH}")
    replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
    if replay.get("status") != "PASS":
        fail("fixed-input replay did not pass")
    if replay.get("review_status") != "directly_reviewed_complete":
        fail("fixed-input replay is not directly_reviewed_complete")
    if replay.get("runner_invocation_count") != 1:
        fail("fixed-input replay must invoke the runner exactly once")
    if replay.get("generated_csv_count") != len(GENERATED_CSV_PATHS):
        fail("fixed-input replay generated-CSV whitelist count changed")
    if replay.get("baseline_snapshot_source") != "CURRENT_DIRECTLY_REVIEWED_OUTPUTS":
        fail("fixed-input replay baseline source changed")
    if replay.get("explicit_semantic_contract_checked") is not True:
        fail("fixed-input replay did not explicitly check the semantic/config contract")
    if replay.get("expected_config_hash") != EXPECTED_CONFIG_HASH:
        fail("fixed-input replay expected CONFIG_HASH changed")
    if replay.get("semantic_contract_changed") is not False:
        fail("fixed-input replay semantic contract changed")
    before_semantic = replay.get("before_semantic_contract")
    after_semantic = replay.get("after_semantic_contract")
    if not isinstance(before_semantic, dict) or before_semantic != after_semantic:
        fail("fixed-input replay semantic-contract snapshots differ")
    if (
        before_semantic.get("config_hash") != EXPECTED_CONFIG_HASH
        or before_semantic.get("background_control_count") != 4
        or before_semantic.get("background_spatial_group_count") != 3
        or before_semantic.get("background_parameter_envelope_group_count") != 2
        or before_semantic.get("pair_sensitivity_modes")
        != ["LEAVE_ONE_FRAME_OUT", "LEAVE_ONE_PAIR_OUT"]
        or before_semantic.get("observability_states") != ["NOT_IDENTIFIABLE"]
        or before_semantic.get("reported_physical_bounds_blank") is not True
        or before_semantic.get("canny_config") != EXPECTED_CANNY_CONFIG
        or before_semantic.get("structure_boundary_guard")
        != EXPECTED_STRUCTURE_BOUNDARY_GUARD
    ):
        fail("fixed-input replay semantic-contract snapshot is incomplete or stale")
    if replay.get("changed_content_paths"):
        fail(f"fixed-input replay content changed: {replay['changed_content_paths']}")
    if replay.get("visual_manifest_metadata_changed") or replay.get(
        "visual_manifest_paths_changed"
    ):
        fail("fixed-input replay visual manifest metadata/path changed")
    if replay.get("temporary_visual_bytes_compared") is not False:
        fail("replay must not compare temporary PNG bytes")
    formal_replay_paths = (*GENERATED_CSV_PATHS, SUMMARY_PATH)
    expected_hash_keys = {str(path) for path in formal_replay_paths}
    before_hashes = replay.get("before_content_hashes")
    after_hashes = replay.get("after_content_hashes")
    if not isinstance(before_hashes, dict) or set(before_hashes) != expected_hash_keys:
        fail("fixed-input replay before-hash whitelist changed")
    if not isinstance(after_hashes, dict) or set(after_hashes) != expected_hash_keys:
        fail("fixed-input replay after-hash whitelist changed")
    if before_hashes != after_hashes:
        fail("fixed-input replay before/after hashes differ")
    current_hashes = {str(path): sha256(path) for path in formal_replay_paths}
    if after_hashes != current_hashes:
        fail("fixed-input replay hashes are stale relative to current formal outputs")
    _, replay_visual_rows = read_csv(VISUAL_MANIFEST_PATH)
    expected_visual_paths = [
        row["artifact_path"]
        for row in sorted(
            replay_visual_rows,
            key=lambda row: (row["case_id"], row["artifact_path"]),
        )
    ]
    if (
        replay.get("before_visual_artifact_paths") != expected_visual_paths
        or replay.get("after_visual_artifact_paths") != expected_visual_paths
    ):
        fail("fixed-input replay visual-artifact path snapshot is stale or incomplete")
    require_false(
        replay.get("latent_support_reconstruction_run"),
        "replay.latent_support_reconstruction_run",
    )
    require_false(replay.get("s1d_allowed"), "replay.s1d_allowed")
    require_false(
        replay.get("automatic_annotation_allowed"),
        "replay.automatic_annotation_allowed",
    )
    if replay.get("forbidden_methods_used") != []:
        fail(f"replay reports forbidden methods: {replay.get('forbidden_methods_used')}")

    if not FINAL_REPORT_PATH.exists():
        fail(f"missing final report: {FINAL_REPORT_PATH}")
    report = FINAL_REPORT_PATH.read_text(encoding="utf-8")
    required_report_tokens = {
        *CONCLUSION_IDS,
        "IDENTITY_NEGATIVE_CLASS_POSITIVE",
        "UNIQUE_BOX_RECOVERY=NOT_EVALUATED_NOT_AUTHORIZED",
        "GT-conditioned registration evidence",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
        "NOT_APPLICABLE_TO_TIME_REVERSAL",
        "BACKGROUND_POSITIONS_AND_SUPPORT_GEOMETRY_FROZEN_FROM_PV002_ONLY",
        PAIR_MEMBERSHIP_REFERENCE,
        PAIR_PROJECTION_RULE,
        BODY_ORIENTED_WINDOW_ATTRIBUTION,
        PARAMETER_OBSERVABILITY_CONTRACT,
        BACKGROUND_CLUSTER_SCOPE,
        "CORRESPONDENCE_ONLY",
        "WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED",
    }
    missing_tokens = sorted(
        token for token in required_report_tokens if token not in report
    )
    if missing_tokens:
        fail(
            f"final report is missing required semantic/boundary tokens: {missing_tokens}"
        )


def main() -> int:
    touched = validate_scope()
    validate_forbidden_fields()
    (
        unit_rows,
        units_by_id,
        spatial_groups,
        parameter_envelope_groups,
        required_review_units,
    ) = (
        validate_research_units()
    )
    pair_hashes, source_pair_hashes, candidate_counts, eligible_counts = (
        validate_sampling_and_representations(units_by_id)
    )
    validate_pair_contract(
        pair_hashes,
        source_pair_hashes,
        candidate_counts,
        eligible_counts,
        units_by_id,
    )
    sensitivity_buckets = validate_pair_and_frame_sensitivity(
        pair_hashes,
        source_pair_hashes,
        candidate_counts,
        eligible_counts,
        units_by_id,
    )
    validate_parameter_outputs(
        units_by_id,
        pair_hashes,
        source_pair_hashes,
        candidate_counts,
        eligible_counts,
    )
    visual_count, visual_review_count = validate_visuals_and_reviews(
        units_by_id, required_review_units
    )
    conclusion_rows = validate_stage_conclusions()
    validate_summary_replay_and_report(
        unit_rows,
        spatial_groups,
        parameter_envelope_groups,
        visual_count,
    )

    print("S1L_OPTICAL_CONDITIONED_SUPPORT_VALIDATOR_PASS")
    print(
        json.dumps(
            {
                "frozen_base_head": BASE_HEAD,
                "touched_path_count": len(touched),
                "generated_csv_count": len(GENERATED_CSV_PATHS),
                "research_unit_count": len(unit_rows),
                "pv002_geometry_background_control_count": 4,
                "background_spatial_control_group_count": len(spatial_groups),
                "background_parameter_envelope_group_count": len(
                    parameter_envelope_groups
                ),
                "representation_count": len(REPRESENTATIONS),
                "axis_rule_count": len(AXIS_RULES),
                "normalization_path_count": len(NORMALIZATION_PATHS),
                "parameter_id_count": len(PARAMETER_GRIDS),
                "stage_conclusion_count": len(conclusion_rows),
                "visual_artifact_count": visual_count,
                "visual_review_count": visual_review_count,
                "pair_and_frame_sensitivity_group_buckets": dict(
                    sensitivity_buckets
                ),
                "latent_support_reconstruction_allowed": False,
                "s1d_allowed": False,
                "automatic_annotation_allowed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
