#!/usr/bin/env python3
"""Replay the bounded S1-L runner once against reviewed baseline outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
OUTPUT_ROOT = Path(
    r"D:\profile\research\workspace\output\oty2_s1l_optical_conditioned_support_observability_20260716"
)
SUMMARY_PATH = OUTPUT_ROOT / "optical_conditioned_support_observability_summary.json"
REPLAY_PATH = OUTPUT_ROOT / "optical_conditioned_support_replay_check.json"
RUNNER_PATH = (
    REPO_ROOT
    / "tools"
    / "diagnostics"
    / "run_oty2_s1l_optical_conditioned_support_observability.py"
)

GENERATED_CSV_PATHS = (
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_research_units.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_sampling_normalization_audit.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_representation_metrics.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_pair_incremental_metrics.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_pair_and_frame_sensitivity.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_parameter_metric_profiles.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_parameter_observability.csv",
    MANIFEST_DIR / "oty2_s1l_optical_conditioned_visual_manifest.csv",
)
VISUAL_MANIFEST_PATH = GENERATED_CSV_PATHS[-1]
FORMAL_REPLAY_PATHS = (*GENERATED_CSV_PATHS, SUMMARY_PATH)
EXPECTED_SUMMARY_OUTPUTS = {
    "research_units": GENERATED_CSV_PATHS[0],
    "sampling_normalization": GENERATED_CSV_PATHS[1],
    "representation_metrics": GENERATED_CSV_PATHS[2],
    "pair_incremental_metrics": GENERATED_CSV_PATHS[3],
    "pair_and_frame_sensitivity": GENERATED_CSV_PATHS[4],
    "parameter_profiles": GENERATED_CSV_PATHS[5],
    "parameter_observability": GENERATED_CSV_PATHS[6],
    "visual_manifest": GENERATED_CSV_PATHS[7],
    "temporary_visuals": OUTPUT_ROOT / "visual_casebook",
}
EXPECTED_CONFIG_HASH = "a62d5f6bdb3c902f1651ee03e4bd2c30e5403fdb4ee53a03e0ee3899402e9113"
PAIR_RULE_ID = (
    "SOURCE_POSITIVE_GT_CONDITIONED_VIEW_GAP10_DIFF5_RELIABILITY_AND_FINITE_"
    "COMMON_VALID_PROJECTED_NO_RESELECTION"
)
PAIR_PROJECTION_RULE = "SOURCE_POSITIVE_PAIR_SET_FRAME_INTERSECTION_NO_RESELECTION"
PAIR_MEMBERSHIP_REFERENCE = (
    "SOURCE_POSITIVE|CENTER_TRACKED_BODY|GT_DERIVED_UNSIGNED_BODY|"
    "FIXED_REFERENCE|FINITE_COMMON_VALID"
)
NORMALIZATION_PATHS = {"FIXED_REFERENCE", "CANDIDATE_LOCAL_REESTIMATED"}
ANCHOR_VARIANTS = {"raw_gt", "smoothed_gt"}
PAIR_SENSITIVITY_MODES = {"LEAVE_ONE_PAIR_OUT", "LEAVE_ONE_FRAME_OUT"}
REPRESENTATION_COMPARISONS = {
    "TRANSLATION_COMPENSATION",
    "RADIAL_AXIS_INCREMENT",
    "GT_BODY_ORIENTED_WINDOW_VS_CARTESIAN",
    "GT_BODY_ORIENTED_WINDOW_VS_RADIAL",
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
AXIS_COMPARISONS = {
    f"GT_ORIENTED_WINDOW_RULE_VS_{axis_rule}"
    for axis_rule in AXIS_RULES - {"GT_DERIVED_UNSIGNED_BODY"}
}
GRID_NONDOMINANCE_PATTERNS = {
    "EMPTY",
    "ALL_GRID",
    "MULTICOMPONENT",
    "SINGLETON",
    "EDGE_CONTIGUOUS_SET",
    "INTERIOR_CONTIGUOUS_SET",
}
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
THIN_EDGE_ESTIMATOR = (
    "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON"
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
EXPECTED_BACKGROUND_SEMANTICS = {
    "CLASS-NEGATIVE-S1L-BG-0010": (
        "same_azimuth_neighbor",
        "MOVING_SAME_AZIMUTH_BACKGROUND",
    ),
    "CLASS-NEGATIVE-S1L-BG-0011": (
        "fixed_strong_linear_background",
        "FIXED_STRONG_LINEAR_SAME_CLUSTER_DIAGNOSTIC",
    ),
    "CLASS-NEGATIVE-S1L-BG-OCS-B3-SA35N": (
        "hard_scatter_partial_complexity_match",
        "MOVING_HARD_SCATTER_PARTIAL_COMPLEXITY_BACKGROUND",
    ),
    "CLASS-NEGATIVE-S1L-BG-OCS-B4-FX88": (
        "fixed_anisotropic_speckle_not_strong_line",
        "FIXED_ANISOTROPIC_SPECKLE_CONTROL_NOT_STRONG_LINE",
    ),
}
BACKGROUND_CLUSTER_SCOPE = (
    "BASELINE_EQUAL_SUPPORT_3_SPATIAL_CLUSTERS;STRICT_ONE_DIM_PARAMETER_ENVELOPE_"
    "2_CLUSTERS;NOT_STATISTICAL_INDEPENDENCE"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise AssertionError(f"CSV has no header: {path}")
        return list(reader)


def require_columns(
    rows: list[dict[str, str]], required: set[str], label: str
) -> None:
    missing = required - (set(rows[0]) if rows else set())
    if missing:
        raise AssertionError(f"{label} missing semantic-contract columns: {sorted(missing)}")


def expected_temporal_direction(unit: dict[str, str]) -> str:
    if unit["transform_rule_id"] == "IMAGE_ORDER_REVERSED":
        return "NOT_APPLICABLE_TO_TIME_REVERSAL"
    if unit["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE":
        return "NOT_EVALUATED_DIRECTION_INSENSITIVE_METRICS"
    return "NOT_A_TEMPORAL_DIRECTION_TEST"


def expected_temporal_correspondence(unit: dict[str, str]) -> str:
    return (
        "APPLICABLE_TO_TEMPORAL_CORRESPONDENCE_CONTROL"
        if unit["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE"
        else "NOT_A_TEMPORAL_CORRESPONDENCE_TEST"
    )


def assert_temporal_contract(
    rows: list[dict[str, str]], units_by_id: dict[str, dict[str, str]], label: str
) -> None:
    for row in rows:
        unit = units_by_id.get(row["research_unit_id"])
        if unit is None:
            raise AssertionError(f"{label} references unknown research unit")
        if (
            row["temporal_direction_applicability"]
            != expected_temporal_direction(unit)
            or row["temporal_correspondence_applicability"]
            != expected_temporal_correspondence(unit)
        ):
            raise AssertionError(f"{label} temporal direction/correspondence contract changed")


def semantic_contract_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    tables = {path.name: read_csv(path) for path in GENERATED_CSV_PATHS}
    unit_rows = tables[GENERATED_CSV_PATHS[0].name]
    sampling_rows = tables[GENERATED_CSV_PATHS[1].name]
    representation_rows = tables[GENERATED_CSV_PATHS[2].name]
    pair_rows = tables[GENERATED_CSV_PATHS[3].name]
    sensitivity_rows = tables[GENERATED_CSV_PATHS[4].name]
    profile_rows = tables[GENERATED_CSV_PATHS[5].name]
    observability_rows = tables[GENERATED_CSV_PATHS[6].name]

    require_columns(
        unit_rows,
        {
            "research_unit_id",
            "counterfactual_semantic_class",
            "transform_rule_id",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
            "valid_for_temporal_test_scope",
            "anchor_variant_contract",
            "pair_membership_source_segment_id",
            "pair_membership_contract",
            "background_spatial_control_group",
            "background_parameter_envelope_group",
            "background_control_semantic_role",
            "background_type",
            "background_quality_status",
            "background_reviewed_gt_overlap",
            "config_hash",
        },
        "research units",
    )
    if len(unit_rows) != 21:
        raise AssertionError("semantic replay requires exactly 21 research units")
    units_by_id = {row["research_unit_id"]: row for row in unit_rows}
    if len(units_by_id) != len(unit_rows):
        raise AssertionError("research-unit ids are not unique")
    semantic_counts: dict[str, int] = {}
    for row in unit_rows:
        semantic_counts[row["counterfactual_semantic_class"]] = (
            semantic_counts.get(row["counterfactual_semantic_class"], 0) + 1
        )
        if row["config_hash"] != EXPECTED_CONFIG_HASH:
            raise AssertionError("research-unit CONFIG_HASH changed")
        if (
            row["anchor_variant_contract"]
            != "RAW_AND_SMOOTHED_SEPARATE_SOURCE_POSITIVE_PAIR_SETS_FOR_ALL_UNITS"
            or row["pair_membership_contract"] != PAIR_PROJECTION_RULE
        ):
            raise AssertionError("research-unit anchor/source-pair contract changed")
        expected_temporal_scope = (
            "CORRESPONDENCE_ONLY"
            if row["counterfactual_semantic_class"] == "TEMPORAL_NEGATIVE"
            else "POSITIVE_REFERENCE_FOR_CORRESPONDENCE_ONLY"
            if row["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
            else "NOT_APPLICABLE"
        )
        if row["valid_for_temporal_test_scope"] != expected_temporal_scope:
            raise AssertionError("research-unit temporal test scope changed")
    expected_semantic_counts = {
        "TRUE_VEHICLE_POSITIVE": 3,
        "IDENTITY_NEGATIVE_CLASS_POSITIVE": 2,
        "VEHICLE_CLASS_NEGATIVE": 4,
        "TEMPORAL_NEGATIVE": 12,
    }
    if semantic_counts != expected_semantic_counts:
        raise AssertionError(f"research-unit semantic counts changed: {semantic_counts}")
    assert_temporal_contract(unit_rows, units_by_id, "research units")

    backgrounds = [
        row
        for row in unit_rows
        if row["counterfactual_semantic_class"] == "VEHICLE_CLASS_NEGATIVE"
    ]
    spatial_groups = {
        row["background_spatial_control_group"] for row in backgrounds
    }
    parameter_groups = {
        row["background_parameter_envelope_group"] for row in backgrounds
    }
    if (
        len(backgrounds) != 4
        or spatial_groups != EXPECTED_BACKGROUND_SPATIAL_GROUPS
        or parameter_groups != EXPECTED_BACKGROUND_PARAMETER_ENVELOPE_GROUPS
    ):
        raise AssertionError("four-control/three-spatial/two-envelope background contract changed")
    if {row["research_unit_id"] for row in backgrounds} != set(
        EXPECTED_BACKGROUND_SEMANTICS
    ):
        raise AssertionError("frozen background-control ids changed")
    for row in backgrounds:
        if (
            row["background_type"],
            row["background_control_semantic_role"],
        ) != EXPECTED_BACKGROUND_SEMANTICS[row["research_unit_id"]]:
            raise AssertionError("background type/semantic role changed")
        if not row["background_quality_status"] or float(
            row["background_reviewed_gt_overlap"]
        ) != 0.0:
            raise AssertionError("background quality/zero-overlap contract changed")

    require_columns(
        sampling_rows,
        {
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "representation",
            "axis_rule",
            "window_half_x_source_px",
            "window_half_y_source_px",
            "source_px_per_grid_x",
            "source_px_per_grid_y",
            "structure_boundary_guard_id",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
        },
        "sampling audit",
    )
    if (
        {row["anchor_variant"] for row in sampling_rows} != ANCHOR_VARIANTS
        or {row["normalization_path"] for row in sampling_rows} != NORMALIZATION_PATHS
        or {
            row["structure_boundary_guard_id"] for row in sampling_rows
        }
        != {"TELEA_INPAINT_INVALID_PLUS_ERODE_VALID_6PX"}
    ):
        raise AssertionError("sampling anchor/normalization/boundary-guard contract changed")
    baseline_density_sets: dict[tuple[str, str], set[tuple[float, float]]] = {}
    for row in sampling_rows:
        half_x = float(row["window_half_x_source_px"])
        half_y = float(row["window_half_y_source_px"])
        density_x = float(row["source_px_per_grid_x"])
        density_y = float(row["source_px_per_grid_y"])
        if (
            abs(density_x - 2.0 * half_x / (256 - 1)) > 2e-6
            or abs(density_y - 2.0 * half_y / (128 - 1)) > 2e-6
        ):
            raise AssertionError("sampling density no longer uses W-1/H-1 intervals")
        if (
            row["representation"] == "CENTER_TRACKED_BODY"
            and row["axis_rule"] == "GT_DERIVED_UNSIGNED_BODY"
        ):
            key = (row["research_unit_id"], row["anchor_variant"])
            baseline_density_sets.setdefault(key, set()).add((density_x, density_y))
    if any(len(values) != 1 for values in baseline_density_sets.values()):
        raise AssertionError("baseline body-window density changes across frames")
    baseline_densities = {
        key: next(iter(values)) for key, values in baseline_density_sets.items()
    }
    assert_temporal_contract(sampling_rows, units_by_id, "sampling audit")

    require_columns(
        representation_rows,
        {
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "pair_rule_id",
            "source_pair_set_hash",
            "topology_estimator_id",
            "structure_boundary_guard_id",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
        },
        "representation metrics",
    )
    if (
        {row["anchor_variant"] for row in representation_rows} != ANCHOR_VARIANTS
        or {row["normalization_path"] for row in representation_rows}
        != NORMALIZATION_PATHS
        or {row["pair_rule_id"] for row in representation_rows} != {PAIR_RULE_ID}
        or {row["topology_estimator_id"] for row in representation_rows}
        != {THIN_EDGE_ESTIMATOR}
        or any(not row["source_pair_set_hash"] for row in representation_rows)
    ):
        raise AssertionError("representation source-pair/proxy contract changed")
    assert_temporal_contract(representation_rows, units_by_id, "representation metrics")

    require_columns(
        pair_rows,
        {
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "pair_rule_id",
            "source_pair_id",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_membership_reliability_scope",
            "comparison_id",
            "pair_eligibility",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
        },
        "pair metrics",
    )
    if (
        {row["anchor_variant"] for row in pair_rows} != ANCHOR_VARIANTS
        or {row["normalization_path"] for row in pair_rows} != NORMALIZATION_PATHS
        or {row["pair_rule_id"] for row in pair_rows} != {PAIR_RULE_ID}
        or {row["pair_projection_rule"] for row in pair_rows}
        != {PAIR_PROJECTION_RULE}
        or {row["comparison_id"] for row in pair_rows}
        != REPRESENTATION_COMPARISONS | AXIS_COMPARISONS
        or any(not row["source_pair_set_hash"] for row in pair_rows)
    ):
        raise AssertionError("pair projection/comparison contract changed")
    for row in pair_rows:
        unit = units_by_id[row["research_unit_id"]]
        expected_scope = (
            "DIRECT_SOURCE_REGISTRATION_RELIABILITY"
            if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
            else "SOURCE_POSITIVE_MEMBERSHIP_ONLY;COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED"
        )
        if row["pair_membership_reliability_scope"] != expected_scope:
            raise AssertionError("pair source-vs-counterfactual reliability scope changed")
        if row["pair_eligibility"] != "NO_CANDIDATE_PAIRS" and not row["source_pair_id"]:
            raise AssertionError("projected pair lost its source-positive pair id")
    assert_temporal_contract(pair_rows, units_by_id, "pair metrics")

    require_columns(
        sensitivity_rows,
        {
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_membership_reliability_scope",
            "sensitivity_mode",
            "frozen_eligible_pair_count",
            "metric_usable_pair_count",
            "eligible_pair_count_semantics",
            "pair_evidence_state",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
        },
        "pair/frame sensitivity",
    )
    if (
        {row["sensitivity_mode"] for row in sensitivity_rows}
        != PAIR_SENSITIVITY_MODES
        or {row["pair_projection_rule"] for row in sensitivity_rows}
        != {PAIR_PROJECTION_RULE}
        or {
            row["eligible_pair_count_semantics"] for row in sensitivity_rows
        }
        != {"METRIC_USABLE_SOURCE_ELIGIBLE_PAIRS"}
        or any(not row["source_pair_set_hash"] for row in sensitivity_rows)
        or any(
            row["pair_evidence_state"]
            not in {
                "NO_ELIGIBLE_PAIRS",
                "SPARSE_PAIR_EVIDENCE",
                "PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE",
            }
            for row in sensitivity_rows
        )
    ):
        raise AssertionError("LOPO/LOFO sensitivity semantics changed")
    for row in sensitivity_rows:
        unit = units_by_id[row["research_unit_id"]]
        expected_scope = (
            "DIRECT_SOURCE_REGISTRATION_RELIABILITY"
            if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
            else "SOURCE_POSITIVE_MEMBERSHIP_ONLY;COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED"
        )
        if row["pair_membership_reliability_scope"] != expected_scope:
            raise AssertionError("sensitivity source-vs-counterfactual reliability scope changed")
    assert_temporal_contract(sensitivity_rows, units_by_id, "pair/frame sensitivity")

    require_columns(
        profile_rows,
        {
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "parameter_id",
            "parameter_value",
            "effective_source_px_per_grid_x",
            "effective_source_px_per_grid_y",
            "scale_response_scope",
            "physical_scale_bound_status",
            "pareto_nondominated",
            "grid_nondominance_pattern",
            "parameter_interpretation_limit",
            "pair_membership_rule",
            "source_pair_set_hash",
            "pair_projection_rule",
            "pair_membership_reliability_scope",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
        },
        "parameter profiles",
    )
    if (
        {row["anchor_variant"] for row in profile_rows} != ANCHOR_VARIANTS
        or {row["normalization_path"] for row in profile_rows} != NORMALIZATION_PATHS
        or {row["pair_membership_rule"] for row in profile_rows}
        != {PAIR_PROJECTION_RULE}
        or {row["pair_projection_rule"] for row in profile_rows}
        != {PAIR_PROJECTION_RULE}
        or any(not row["source_pair_set_hash"] for row in profile_rows)
        or any(
            row["grid_nondominance_pattern"] not in GRID_NONDOMINANCE_PATTERNS
            for row in profile_rows
        )
        or any(
            row["pareto_nondominated"] not in {"true", "false"}
            for row in profile_rows
        )
    ):
        raise AssertionError("parameter-profile nondominance/source-pair contract changed")
    for row in profile_rows:
        unit = units_by_id[row["research_unit_id"]]
        expected_scope = (
            "DIRECT_SOURCE_REGISTRATION_RELIABILITY"
            if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
            else "SOURCE_POSITIVE_MEMBERSHIP_ONLY;COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED"
        )
        if row["pair_membership_reliability_scope"] != expected_scope:
            raise AssertionError("profile source-vs-counterfactual reliability scope changed")
        key = (row["research_unit_id"], row["anchor_variant"])
        baseline_density = baseline_densities.get(key)
        if baseline_density is None:
            raise AssertionError("parameter profile lost baseline density lineage")
        parameter_value = float(row["parameter_value"])
        expected_x = baseline_density[0] * (
            parameter_value if row["parameter_id"] == "LONG_SCALE" else 1.0
        )
        expected_y = baseline_density[1] * (
            parameter_value if row["parameter_id"] == "SHORT_SCALE" else 1.0
        )
        if (
            abs(float(row["effective_source_px_per_grid_x"]) - expected_x) > 3e-6
            or abs(float(row["effective_source_px_per_grid_y"]) - expected_y) > 3e-6
        ):
            raise AssertionError("parameter effective density drifted from W-1/H-1 lineage")
        is_scale = row["parameter_id"] in {"LONG_SCALE", "SHORT_SCALE"}
        if (
            row["scale_response_scope"]
            != (
                "WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED"
                if is_scale
                else "NOT_A_SCALE_PROFILE"
            )
            or row["physical_scale_bound_status"]
            != (
                "NOT_EVALUATED_FIXED_GRID_RESAMPLING_CONFOUND"
                if is_scale
                else "NOT_APPLICABLE"
            )
        ):
            raise AssertionError("scale resampling/physical-bound contract changed")
    assert_temporal_contract(profile_rows, units_by_id, "parameter profiles")

    require_columns(
        observability_rows,
        {
            "scope_level",
            "research_unit_id",
            "anchor_variant",
            "normalization_path",
            "pareto_nondominated_grid_values",
            "grid_nondominance_pattern",
            "nondominated_grid_component_count",
            "reported_lower_bound",
            "reported_upper_bound",
            "fixed_rule_replay_scope",
            "observability_state",
            "temporal_direction_applicability",
            "temporal_correspondence_applicability",
        },
        "parameter observability",
    )
    if (
        {row["observability_state"] for row in observability_rows}
        != {"NOT_IDENTIFIABLE"}
        or any(row["reported_lower_bound"] or row["reported_upper_bound"] for row in observability_rows)
        or any(
            row["grid_nondominance_pattern"] not in GRID_NONDOMINANCE_PATTERNS
            for row in observability_rows
        )
        or {
            row["normalization_path"] for row in observability_rows
        }
        != NORMALIZATION_PATHS
        | {
            "DUAL_PATH_GRID_NONDOMINANCE_INTERSECTION",
            "DUAL_PATH_AND_WITHIN_SCENE_OTHER_VEHICLE_GRID_INTERSECTION",
        }
    ):
        raise AssertionError("observability grid-pattern/no-physical-bound contract changed")
    nonaggregate_observability = [
        row for row in observability_rows if row["scope_level"] != "CORE_VEHICLE_AGGREGATE"
    ]
    aggregate_observability = [
        row for row in observability_rows if row["scope_level"] == "CORE_VEHICLE_AGGREGATE"
    ]
    assert_temporal_contract(
        nonaggregate_observability,
        units_by_id,
        "parameter observability",
    )
    if any(
        row["temporal_direction_applicability"]
        != "NOT_A_TEMPORAL_DIRECTION_TEST"
        or row["temporal_correspondence_applicability"]
        != "NOT_A_TEMPORAL_CORRESPONDENCE_TEST"
        for row in aggregate_observability
    ):
        raise AssertionError("aggregate observability temporal applicability changed")

    expected_summary_contract = {
        "config_hash": EXPECTED_CONFIG_HASH,
        "research_unit_count": 21,
        "anchor_variants": ["raw_gt", "smoothed_gt"],
        "all_units_run_both_anchor_variants": True,
        "pair_membership_reference": PAIR_MEMBERSHIP_REFERENCE,
        "pair_projection_rule": PAIR_PROJECTION_RULE,
        "pair_sensitivity_modes": ["LEAVE_ONE_PAIR_OUT", "LEAVE_ONE_FRAME_OUT"],
        "normalization_failure_policy": "INVALID_EVIDENCE_NAN_EXCLUDED_FROM_PARETO",
        "body_oriented_window_attribution": "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT_NOT_PURE_BODY_AXIS",
        "parameter_observability_contract": "GRID_NONDOMINANCE_DIAGNOSTIC_ONLY;ALL_FORMAL_OBSERVABILITY_STATES_NOT_IDENTIFIABLE;NO_PHYSICAL_BOUNDS",
        "scale_profile_contract": "FIXED_256X128_WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED",
        "temporal_test_contract": "CORRESPONDENCE_CONTROLS_ONLY;NO_ARROW_OF_TIME_METRIC",
        "orientation_estimator": "STRUCTURE_TENSOR_ORIENTATION_PROXY",
        "topology_estimator": THIN_EDGE_ESTIMATOR,
        "canny_config": EXPECTED_CANNY_CONFIG,
        "structure_boundary_guard": EXPECTED_STRUCTURE_BOUNDARY_GUARD,
        "optical_condition_execution_status": "NOT_EXECUTED_GT_DISCOVERY_PROXY_ONLY",
        "optical_conditioned_support_readiness": "NOT_EVALUATED_WITH_REAL_OPTICAL_INPUT_GT_PROXY_ONLY",
        "semantic_class_counts": expected_semantic_counts,
        "pv002_geometry_background_control_count": 4,
        "background_spatial_control_group_count": 3,
        "background_parameter_envelope_group_count": 2,
        "background_cluster_scope": BACKGROUND_CLUSTER_SCOPE,
        "visual_artifact_count": 20,
        "latent_support_reconstruction_run": False,
        "s1d_allowed": False,
        "automatic_annotation_allowed": False,
        "unique_box_recovery": "NOT_EVALUATED_NOT_AUTHORIZED",
        "forbidden_methods_used": [],
    }
    for key, expected in expected_summary_contract.items():
        if summary.get(key) != expected:
            raise AssertionError(
                f"summary semantic contract changed for {key}: {summary.get(key)!r}"
            )
    expected_row_counts = {
        "sampling_row_count": len(sampling_rows),
        "representation_metric_row_count": len(representation_rows),
        "pair_metric_row_count": len(pair_rows),
        "leave_one_pair_out_row_count": sum(
            row["sensitivity_mode"] == "LEAVE_ONE_PAIR_OUT"
            for row in sensitivity_rows
        ),
        "leave_one_frame_out_row_count": sum(
            row["sensitivity_mode"] == "LEAVE_ONE_FRAME_OUT"
            for row in sensitivity_rows
        ),
        "pair_and_frame_sensitivity_row_count": len(sensitivity_rows),
        "parameter_profile_row_count": len(profile_rows),
        "observability_row_count": len(observability_rows),
    }
    for key, expected in expected_row_counts.items():
        if summary.get(key) != expected:
            raise AssertionError(f"summary generated-row count changed for {key}")

    return {
        "config_hash": EXPECTED_CONFIG_HASH,
        "semantic_class_counts": semantic_counts,
        "background_control_count": len(backgrounds),
        "background_spatial_group_count": len(spatial_groups),
        "background_parameter_envelope_group_count": len(parameter_groups),
        "normalization_paths": sorted(NORMALIZATION_PATHS),
        "anchor_variants": sorted(ANCHOR_VARIANTS),
        "comparison_ids": sorted(REPRESENTATION_COMPARISONS | AXIS_COMPARISONS),
        "pair_sensitivity_modes": sorted(PAIR_SENSITIVITY_MODES),
        "observability_states": sorted(
            {row["observability_state"] for row in observability_rows}
        ),
        "reported_physical_bounds_blank": True,
        "canny_config": EXPECTED_CANNY_CONFIG,
        "structure_boundary_guard": EXPECTED_STRUCTURE_BOUNDARY_GUARD,
    }


def visual_manifest_records() -> list[dict[str, str]]:
    rows = read_csv(VISUAL_MANIFEST_PATH)
    required = {
        "case_id",
        "artifact_type",
        "research_unit_id",
        "counterfactual_semantic_class",
        "artifact_path",
        "review_status",
    }
    missing = required - set(rows[0]) if rows else required
    if missing:
        raise AssertionError(f"visual manifest missing columns: {sorted(missing)}")
    records = [{key: row[key] for key in sorted(required)} for row in rows]
    if len(records) != 20:
        raise AssertionError(f"visual manifest must contain 20 artifacts, got {len(records)}")
    if len({record["research_unit_id"] for record in records}) != 14:
        raise AssertionError("visual manifest must contain 14 review entities including GLOBAL")
    return sorted(records, key=lambda row: (row["case_id"], row["artifact_path"]))


def snapshot() -> dict[str, Any]:
    missing = [str(path) for path in FORMAL_REPLAY_PATHS if not path.exists()]
    if missing:
        raise FileNotFoundError(f"runner did not create required outputs: {missing}")
    for path in GENERATED_CSV_PATHS:
        rows = read_csv(path)
        if not rows:
            raise AssertionError(f"baseline/output CSV has no rows: {path}")
        if any(row.get("review_status") != "directly_reviewed_complete" for row in rows):
            raise AssertionError(f"baseline/output is not directly reviewed: {path}")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary.get("review_status") != "directly_reviewed_complete":
        raise AssertionError("summary is not directly_reviewed_complete")
    summary_outputs = summary.get("outputs")
    if not isinstance(summary_outputs, dict) or set(summary_outputs) != set(
        EXPECTED_SUMMARY_OUTPUTS
    ):
        raise AssertionError("summary output whitelist changed")
    for key, expected_path in EXPECTED_SUMMARY_OUTPUTS.items():
        if Path(summary_outputs[key]).resolve() != expected_path.resolve():
            raise AssertionError(
                f"summary output path mismatch for {key}: {summary_outputs[key]}"
            )
    records = visual_manifest_records()
    artifact_paths = [record["artifact_path"] for record in records]
    if not artifact_paths or len(artifact_paths) != len(set(artifact_paths)):
        raise AssertionError("visual manifest paths must be non-empty and unique")
    missing_artifacts = [path for path in artifact_paths if not Path(path).exists()]
    if missing_artifacts:
        raise FileNotFoundError(
            f"visual manifest references missing artifacts: {missing_artifacts}"
        )
    semantic_contract = semantic_contract_snapshot(summary)
    return {
        "content_hashes": {
            str(path): sha256(path) for path in FORMAL_REPLAY_PATHS
        },
        # Paths and compact manifest metadata are compared, but PNG bytes are not.
        "visual_manifest_records": records,
        "visual_artifact_paths": artifact_paths,
        "semantic_contract": semantic_contract,
    }


def run_runner() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "--review-status",
            "directly_reviewed_complete",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        stdout_tail = completed.stdout[-8000:]
        stderr_tail = completed.stderr[-8000:]
        raise RuntimeError(
            "optical-conditioned support runner failed\n"
            f"stdout tail:\n{stdout_tail}\n"
            f"stderr tail:\n{stderr_tail}"
        )


def main() -> int:
    if not RUNNER_PATH.exists():
        raise FileNotFoundError(RUNNER_PATH)

    before = snapshot()
    run_runner()
    after = snapshot()

    before_hashes = before["content_hashes"]
    after_hashes = after["content_hashes"]
    changed_content_paths = sorted(
        path
        for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    visual_manifest_metadata_changed = (
        before["visual_manifest_records"] != after["visual_manifest_records"]
    )
    visual_manifest_paths_changed = (
        before["visual_artifact_paths"] != after["visual_artifact_paths"]
    )
    semantic_contract_changed = before["semantic_contract"] != after["semantic_contract"]
    status = (
        "PASS"
        if not changed_content_paths
        and not visual_manifest_metadata_changed
        and not visual_manifest_paths_changed
        and not semantic_contract_changed
        else "FAIL"
    )
    result: dict[str, Any] = {
        "status": status,
        "review_status": "directly_reviewed_complete",
        "python_executable": sys.executable,
        "baseline_snapshot_source": "CURRENT_DIRECTLY_REVIEWED_OUTPUTS",
        "runner_invocation_count": 1,
        "generated_csv_count": len(GENERATED_CSV_PATHS),
        "before_content_hashes": before_hashes,
        "after_content_hashes": after_hashes,
        "changed_content_paths": changed_content_paths,
        "before_visual_artifact_paths": before["visual_artifact_paths"],
        "after_visual_artifact_paths": after["visual_artifact_paths"],
        "visual_manifest_metadata_changed": visual_manifest_metadata_changed,
        "visual_manifest_paths_changed": visual_manifest_paths_changed,
        "explicit_semantic_contract_checked": True,
        "expected_config_hash": EXPECTED_CONFIG_HASH,
        "before_semantic_contract": before["semantic_contract"],
        "after_semantic_contract": after["semantic_contract"],
        "semantic_contract_changed": semantic_contract_changed,
        "temporary_visual_bytes_compared": False,
        "latent_support_reconstruction_run": False,
        "s1d_allowed": False,
        "automatic_annotation_allowed": False,
        "forbidden_methods_used": [],
    }
    REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPLAY_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
