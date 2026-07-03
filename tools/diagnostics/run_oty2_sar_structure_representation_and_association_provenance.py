"""OTY2 SAR structure representation and association provenance exploration.

This diagnostic consolidates existing OTY2 support-region, scatter-cluster,
temporal-tube, and counterfactual/confounder outputs into mechanism tables.
It does not extract new SAR image features, generate annotation proposals,
output selector/ranking results, train models, tune thresholds, or claim
identity truth.

The goal is to move the current OTY2 discussion from "candidate box" or
"brightest peak" thinking toward:

optical object hypothesis -> feasible support region -> SAR scatter structure
or temporal tube -> posthoc association candidate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from run_oty2_range_narrowing_peak_competition_audit import (
    EXPECTED_LEDGER,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    compact_counts,
    fmt,
    latest_path,
    median_clean,
    read_csv,
    safe_float,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
STATE_MODE = "state_conditioned_range_band"
PAIRED_POOL = "paired_optical_object_sar_gt"
DROPOUT_POOL = "detection_dropout_temporal_continuation"

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "existing_sar_image_observation_reused": True,
    "new_sar_image_extraction_entered": False,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "gt_peak_or_residual_written_to_runtime_prior": False,
    "state_conditioned_topk_written_as_runtime_rule": False,
    "annotation_proposal_entered": False,
    "final_candidate_box_output": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "matlab_zip_or_any_zip_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
}

STRUCTURE_TYPES = [
    "compact_cluster",
    "multi_peak_nearby_cluster",
    "range_spread_cluster",
    "azimuth_spread_cluster",
    "diffuse_clutter",
    "weak_no_structure",
    "jumping_peak",
    "stable_cluster_tube",
    "diffuse_or_unstable_cluster_tube",
]

VOCABULARY_FIELDS = [
    "structure_type",
    "n_observation_rows",
    "local_peak_count",
    "peak_competition_level",
    "centroid_or_energy_center_available",
    "range_extent",
    "azimuth_extent",
    "concentration_score",
    "local_background_relation",
    "temporal_stability_label",
    "likely_vehicle_like",
    "likely_failure_mode",
    "evidence_source",
    "posthoc_only_fields",
    "mechanism_note",
]

SUPPORT_OBSERVATION_FIELDS = [
    "observation_id",
    "scene",
    "object_hypothesis_id",
    "optical_frame",
    "sar_frame",
    "sample_pool",
    "support_type_or_source",
    "support_area_px",
    "area_ratio_vs_broad",
    "radius_band_width_px",
    "support_azimuth_width_deg",
    "support_radius_min_px",
    "support_radius_max_px",
    "gt_inside_support_posthoc",
    "topk_contains_near_gt_posthoc",
    "top1_near_gt_posthoc",
    "observed_sar_structures_inside_support",
    "dominant_structure_type",
    "number_of_plausible_structures",
    "compact_structure_present",
    "multi_peak_structure_present",
    "diffuse_structure_present",
    "spread_structure_present",
    "serious_peak_competition",
    "no_unique_structure_can_be_isolated",
    "support_too_broad_for_association",
    "support_exists",
    "sar_structure_exists",
    "vehicle_like_sar_structure_exists",
    "unique_sar_structure_exists",
    "association_candidate_exists",
    "association_state_posthoc",
    "provenance_labels",
    "notes",
]

COUNTERFACTUAL_FIELDS = [
    "crosscheck_id",
    "source_mode_name",
    "control_type",
    "structure_type",
    "temporal_stability_label",
    "support_overlap_bucket",
    "n_rows",
    "near_gt_topk_rate_posthoc",
    "top1_near_gt_rate_posthoc",
    "gt_inside_support_rate_posthoc",
    "median_best_topk_distance_to_gt_px_posthoc",
    "median_peak_background_ratio",
    "support_hit_status_posthoc",
    "likely_confounder_type",
    "negative_control_cleanliness",
    "mechanism_interpretation",
    "provenance_labels",
]

TEMPORAL_TUBE_FIELDS = [
    "tube_probe_id",
    "structure_id_or_proxy_id",
    "mode_name",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "frame_window",
    "stability_label",
    "drift_or_centroid_change_px",
    "peak_consistency",
    "range_extent_stability",
    "azimuth_extent_stability",
    "scatter_structure_mix",
    "whether_temporal_evidence_strengthens_association",
    "whether_temporal_evidence_only_supports_existence",
    "whether_temporal_evidence_is_confounded_by_wrong_frame_control",
    "provenance_labels",
    "notes",
]

PROVENANCE_FIELDS = [
    "gate_name",
    "evidence_source",
    "runtime_safe_optical_evidence",
    "runtime_safe_temporal_evidence",
    "runtime_safe_geometry_or_vehicle_physics",
    "SAR_image_observation",
    "SAR_temporal_observation",
    "SAR_GT_posthoc_evidence",
    "manual_or_review_anchor",
    "hypothesis_to_validate",
    "allowed_stage",
    "not_allowed_use",
    "leakage_risk",
    "current_support_level",
    "main_failure_mode",
    "next_validation_needed",
]

FAILURE_FIELDS = [
    "transition_state",
    "n_rows_or_reference_count",
    "row_scope",
    "entry_condition",
    "allowed_interpretation",
    "not_allowed_interpretation",
    "main_failure_mode",
    "next_validation_needed",
    "provenance_labels",
]


def is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def rate(num: int, den: int) -> str:
    return fmt(num / den if den else None, 4)


def row_key(row: Mapping[str, Any], mode_key: str = "mode_name") -> tuple[str, str, str, str, str]:
    return (
        str(row.get(mode_key, "")),
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("sar_frame", row.get("expected_sar_frame", ""))),
    )


def counterfactual_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("source_mode_name", "")),
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("expected_sar_frame", row.get("observed_sar_frame", ""))),
    )


def clean_numbers(values: Iterable[Any]) -> list[float]:
    result: list[float] = []
    for value in values:
        number = safe_float(value)
        if number is not None:
            result.append(float(number))
    return result


def true_count(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(1 for row in rows if is_true(row.get(key)))


def peak_competition_level(rows: Sequence[Mapping[str, Any]]) -> str:
    ratio = median_clean(row.get("top1_top2_ratio") for row in rows)
    if ratio is None:
        return "unknown_peak_competition"
    if ratio <= 1.05:
        return "serious_peak_competition"
    if ratio <= 1.2:
        return "moderate_peak_competition"
    return "weak_peak_competition"


def centroid_available(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "unknown"
    present = sum(1 for row in rows if str(row.get("cluster_centroid_x", "")).strip() and str(row.get("cluster_centroid_y", "")).strip())
    return f"{present}/{len(rows)}"


def structure_vehicle_like(structure_type: str) -> str:
    if structure_type in {"compact_cluster", "stable_cluster_tube"}:
        return "yes"
    if structure_type in {"multi_peak_nearby_cluster", "range_spread_cluster", "azimuth_spread_cluster"}:
        return "uncertain"
    return "no"


def structure_failure_mode(structure_type: str) -> str:
    mapping = {
        "compact_cluster": "association may still fail if optical identity or temporal provenance is ambiguous",
        "multi_peak_nearby_cluster": "extended vehicle scatter or nearby competing reflectors need structure grouping",
        "range_spread_cluster": "range support is broad or vehicle scatter is radially extended",
        "azimuth_spread_cluster": "azimuth support/margin may be broad or cross-range discrimination is weak",
        "diffuse_clutter": "local SAR background or sidelobe clutter can imitate support evidence",
        "weak_no_structure": "support exists but no usable SAR structure is isolated",
        "jumping_peak": "single-frame peak does not persist as a stable tube",
        "stable_cluster_tube": "candidate tube exists but still needs object-time provenance",
        "diffuse_or_unstable_cluster_tube": "temporal support may be background persistence rather than object evidence",
    }
    return mapping.get(structure_type, "mechanism not classified")


def support_too_broad(row: Mapping[str, Any]) -> bool:
    area_ratio = safe_float(row.get("area_ratio_vs_broad"))
    radius_width = safe_float(row.get("radius_band_width_px"))
    if row.get("mode_name") == "broad_fan_baseline":
        return True
    if area_ratio is not None and area_ratio > 0.25:
        return True
    if radius_width is not None and radius_width > 500:
        return True
    return False


def row_has_structure(row: Mapping[str, Any]) -> bool:
    return str(row.get("scatter_cluster_type", "")) not in {"", "weak_no_structure"}


def row_vehicle_like(row: Mapping[str, Any]) -> bool:
    structure_type = str(row.get("scatter_cluster_type", ""))
    temporal = str(row.get("temporal_cluster_label", ""))
    return structure_type in {"compact_cluster", "multi_peak_nearby_cluster"} or temporal == "stable_cluster_tube"


def row_unique_structure(row: Mapping[str, Any]) -> bool:
    ratio = safe_float(row.get("top1_top2_ratio"))
    local_peak_count = safe_float(row.get("local_peak_count_above_bg_p95"))
    return (
        str(row.get("scatter_cluster_type", "")) == "compact_cluster"
        and ratio is not None
        and ratio >= 1.15
        and (local_peak_count is None or local_peak_count <= 3)
    )


def association_candidate(row: Mapping[str, Any]) -> bool:
    return str(row.get("gated_association_status", "")).startswith("associated_posthoc")


def control_confonder(control_type: str, rate_value: float | None) -> tuple[str, str, str]:
    if control_type == "true_support":
        return (
            "reference_support",
            "not_a_negative_control",
            "true support is the posthoc reference for comparing wrong/random controls",
        )
    if control_type == "range_shifted_support":
        if rate_value is not None and rate_value < 0.15:
            return (
                "effective_range_negative_control",
                "clean_negative_control",
                "range-shift collapse supports real range/state signal",
            )
        return (
            "range_overlap_or_band_width_confounder",
            "partly_confounded_negative_control",
            "range-shift remains high enough to require band-overlap review",
        )
    if control_type == "random_same_scene_support":
        if rate_value is not None and rate_value < 0.2:
            return (
                "effective_random_negative_control",
                "clean_negative_control",
                "random same-scene support is much weaker than state-conditioned true support",
            )
        return (
            "scene_background_persistence_confounder",
            "partly_confounded_negative_control",
            "random support may still hit persistent scene structures",
        )
    if control_type == "azimuth_shifted_support":
        return (
            "azimuth_overlap_or_margin_confounder",
            "partly_confounded_negative_control",
            "azimuth-shift remains high under current margins; do not promote azimuth as a strong gate",
        )
    if control_type == "wrong_object_support":
        return (
            "object_support_overlap_or_structure_ambiguity",
            "partly_confounded_negative_control",
            "wrong-object hits indicate object association is not closed",
        )
    if control_type == "wrong_sar_frame_support":
        return (
            "temporal_or_background_persistence_confounder",
            "partly_confounded_negative_control",
            "wrong-frame hits indicate single-frame SAR structure is not time-discriminative enough",
        )
    return ("unknown_control_confounder", "unknown_cleanliness", "control interpretation needs review")


def parse_mix(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for part in str(text or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        number = safe_float(value)
        if key.strip() and number is not None:
            result[key.strip()] = int(number)
    return result


def validate_ledger(summary: Mapping[str, Any], name: str) -> None:
    ledger = summary.get("sample_ledger", {}).get("category_counts", {})
    if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
        raise RuntimeError(f"{name} ledger changed; refusing run: {json.dumps(ledger, ensure_ascii=False)}")


def build_vocabulary(cluster_rows: Sequence[Mapping[str, Any]], temporal_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for structure_type in STRUCTURE_TYPES:
        if structure_type in {"jumping_peak", "stable_cluster_tube", "diffuse_or_unstable_cluster_tube"}:
            matched = [row for row in temporal_rows if row.get("temporal_cluster_label") == structure_type]
            source = "temporal_cluster_association_probe"
            local_peak = fmt(median_clean(row.get("n_frames") for row in matched), 2)
            temporal_label = structure_type
            range_extent = "not_available_in_existing_temporal_probe"
            az_extent = "not_available_in_existing_temporal_probe"
            concentration = ""
            background = ""
        else:
            matched = [row for row in cluster_rows if row.get("scatter_cluster_type") == structure_type]
            source = "scatter_cluster_structure_probe"
            local_peak = fmt(median_clean(row.get("local_peak_count_above_bg_p95") for row in matched), 2)
            temporal_label = compact_counts(row.get("temporal_cluster_label") for row in matched)
            range_extent = fmt(median_clean(row.get("cluster_range_spread_px") for row in matched), 2)
            az_extent = fmt(median_clean(row.get("cluster_azimuth_spread_deg") for row in matched), 2)
            concentration = fmt(median_clean(row.get("profile_sharpness_proxy") for row in matched), 4)
            background = fmt(median_clean(row.get("top1_background_ratio") for row in matched), 3)
        rows.append(
            {
                "structure_type": structure_type,
                "n_observation_rows": len(matched),
                "local_peak_count": local_peak,
                "peak_competition_level": peak_competition_level(matched),
                "centroid_or_energy_center_available": centroid_available(matched),
                "range_extent": range_extent,
                "azimuth_extent": az_extent,
                "concentration_score": concentration,
                "local_background_relation": background,
                "temporal_stability_label": temporal_label,
                "likely_vehicle_like": structure_vehicle_like(structure_type),
                "likely_failure_mode": structure_failure_mode(structure_type),
                "evidence_source": source,
                "posthoc_only_fields": "GT-near/top-k relationships and associated_posthoc states are validation fields only",
                "mechanism_note": "mechanism observation; not a selector feature",
            }
        )
    return rows


def build_support_observations(
    cluster_rows: Sequence[Mapping[str, Any]],
    counterfactual_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    true_by_key = {
        counterfactual_key(row): row
        for row in counterfactual_rows
        if row.get("source_mode_name") == STATE_MODE and row.get("control_support_type") == "true_support"
    }
    selected = [
        row
        for row in cluster_rows
        if row.get("mode_name") == STATE_MODE and row.get("sample_pool") == PAIRED_POOL
    ]
    observations: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=1):
        cf = true_by_key.get(row_key(row), {})
        structure_type = str(row.get("scatter_cluster_type", ""))
        temporal_label = str(row.get("temporal_cluster_label", ""))
        local_peaks = safe_float(row.get("local_peak_count_above_bg_p95"))
        topk_count = safe_float(row.get("topk_peak_count"))
        plausible_count = local_peaks if local_peaks is not None else topk_count
        serious_competition = peak_competition_level([row]) == "serious_peak_competition"
        unique = row_unique_structure(row)
        has_structure = row_has_structure(row)
        vehicle_like = row_vehicle_like(row)
        too_broad_for_association = support_too_broad(row) or serious_competition or not unique
        observations.append(
            {
                "observation_id": f"SRO{idx:05d}",
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "optical_frame": row.get("optical_frame", ""),
                "sar_frame": row.get("sar_frame", ""),
                "sample_pool": row.get("sample_pool", ""),
                "support_type_or_source": STATE_MODE,
                "support_area_px": row.get("support_area_px", ""),
                "area_ratio_vs_broad": row.get("area_ratio_vs_broad", ""),
                "radius_band_width_px": row.get("radius_band_width_px", ""),
                "support_azimuth_width_deg": cf.get("support_azimuth_width_deg", ""),
                "support_radius_min_px": cf.get("support_radius_min_px", ""),
                "support_radius_max_px": cf.get("support_radius_max_px", ""),
                "gt_inside_support_posthoc": cf.get("gt_inside_support_posthoc", ""),
                "topk_contains_near_gt_posthoc": cf.get("topk_contains_near_gt_posthoc", ""),
                "top1_near_gt_posthoc": cf.get("top1_near_gt_posthoc", ""),
                "observed_sar_structures_inside_support": f"{structure_type};{temporal_label}",
                "dominant_structure_type": structure_type,
                "number_of_plausible_structures": fmt(plausible_count, 0),
                "compact_structure_present": yes_no(structure_type == "compact_cluster"),
                "multi_peak_structure_present": yes_no(structure_type == "multi_peak_nearby_cluster"),
                "diffuse_structure_present": yes_no(structure_type in {"diffuse_clutter", "weak_no_structure"}),
                "spread_structure_present": yes_no(structure_type in {"range_spread_cluster", "azimuth_spread_cluster"}),
                "serious_peak_competition": yes_no(serious_competition),
                "no_unique_structure_can_be_isolated": yes_no(not unique),
                "support_too_broad_for_association": yes_no(too_broad_for_association),
                "support_exists": "yes",
                "sar_structure_exists": yes_no(has_structure),
                "vehicle_like_sar_structure_exists": yes_no(vehicle_like),
                "unique_sar_structure_exists": yes_no(unique),
                "association_candidate_exists": yes_no(association_candidate(row)),
                "association_state_posthoc": row.get("gated_association_status", ""),
                "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
                "notes": "GT and GT-near fields are posthoc validation only; association candidate is not identity truth.",
            }
        )
    return observations


def aggregate_counterfactual(
    rows: Sequence[Mapping[str, Any]],
    source_mode: str,
    control_type: str,
    structure_type: str,
    temporal_label: str,
    overlap_bucket: str,
    source_rows: Sequence[Mapping[str, Any]],
    idx: int,
) -> dict[str, Any]:
    topk_rate = true_count(source_rows, "topk_contains_near_gt_posthoc") / len(source_rows) if source_rows else None
    confounder, cleanliness, interpretation = control_confonder(control_type, topk_rate)
    return {
        "crosscheck_id": f"CFX{idx:05d}",
        "source_mode_name": source_mode,
        "control_type": control_type,
        "structure_type": structure_type,
        "temporal_stability_label": temporal_label,
        "support_overlap_bucket": overlap_bucket,
        "n_rows": len(source_rows),
        "near_gt_topk_rate_posthoc": fmt(topk_rate, 4),
        "top1_near_gt_rate_posthoc": rate(true_count(source_rows, "top1_near_gt_posthoc"), len(source_rows)),
        "gt_inside_support_rate_posthoc": rate(true_count(source_rows, "gt_inside_support_posthoc"), len(source_rows)),
        "median_best_topk_distance_to_gt_px_posthoc": fmt(median_clean(row.get("best_topk_distance_to_gt_px_posthoc") for row in source_rows), 3),
        "median_peak_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in source_rows), 3),
        "support_hit_status_posthoc": "topk_near_gt_rate=" + fmt(topk_rate, 4),
        "likely_confounder_type": confounder,
        "negative_control_cleanliness": cleanliness,
        "mechanism_interpretation": interpretation,
        "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
    }


def build_counterfactual_crosscheck(
    counterfactual_rows: Sequence[Mapping[str, Any]],
    wrong_object_rows: Sequence[Mapping[str, Any]],
    azimuth_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in counterfactual_rows:
        if row.get("source_mode_name") != STATE_MODE:
            continue
        key = (
            str(row.get("source_mode_name", "")),
            str(row.get("control_support_type", "")),
            str(row.get("scatter_cluster_type", "")),
            str(row.get("temporal_stability_label", "")),
        )
        grouped[key].append(row)

    result: list[dict[str, Any]] = []
    idx = 1
    for (mode, control, structure, temporal), source_rows in sorted(grouped.items()):
        result.append(
            aggregate_counterfactual(
                counterfactual_rows,
                mode,
                control,
                structure,
                temporal,
                "not_available_in_counterfactual_rows",
                source_rows,
                idx,
            )
        )
        idx += 1

    wrong_grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in wrong_object_rows:
        if row.get("source_mode_name") != STATE_MODE:
            continue
        key = (
            str(row.get("source_mode_name", "")),
            str(row.get("overlap_bucket", "")),
            str(row.get("scatter_cluster_type", "")),
            str(row.get("temporal_stability_label", "")),
        )
        wrong_grouped[key].append(row)
    for (mode, overlap, structure, temporal), source_rows in sorted(wrong_grouped.items()):
        result.append(
            aggregate_counterfactual(
                counterfactual_rows,
                mode,
                "wrong_object_support",
                structure,
                temporal,
                overlap,
                source_rows,
                idx,
            )
        )
        idx += 1

    for row in azimuth_rows:
        if row.get("source_mode_name") != STATE_MODE:
            continue
        mix = parse_mix(str(row.get("scatter_cluster_type_mix", "")))
        if not mix:
            mix = {"mixed_structure": int(safe_float(row.get("n_rows"), 0) or 0)}
        for structure, count in mix.items():
            topk_rate = safe_float(row.get("topk_contains_near_gt_rate_posthoc"))
            confounder, cleanliness, interpretation = control_confonder("azimuth_shifted_support", topk_rate)
            result.append(
                {
                    "crosscheck_id": f"CFX{idx:05d}",
                    "source_mode_name": row.get("source_mode_name", ""),
                    "control_type": "azimuth_shifted_support",
                    "structure_type": structure,
                    "temporal_stability_label": row.get("temporal_stability_label_mix", "mixed_temporal_label"),
                    "support_overlap_bucket": row.get("azimuth_overlap_bucket", ""),
                    "n_rows": count,
                    "near_gt_topk_rate_posthoc": row.get("topk_contains_near_gt_rate_posthoc", ""),
                    "top1_near_gt_rate_posthoc": row.get("top1_near_gt_rate_posthoc", ""),
                    "gt_inside_support_rate_posthoc": row.get("gt_inside_support_rate_posthoc", ""),
                    "median_best_topk_distance_to_gt_px_posthoc": "",
                    "median_peak_background_ratio": row.get("median_peak_background_ratio", ""),
                    "support_hit_status_posthoc": "azimuth_shift_aggregate",
                    "likely_confounder_type": confounder,
                    "negative_control_cleanliness": cleanliness,
                    "mechanism_interpretation": interpretation,
                    "provenance_labels": "SAR_GT_posthoc_evidence;hypothesis_to_validate",
                }
            )
            idx += 1
    return result


def build_temporal_tube_probe(temporal_rows: Sequence[Mapping[str, Any]], confounder_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    wrong_frame_rate = safe_float(
        confounder_summary.get("key_metrics", {}).get("state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc")
    )
    wrong_frame_high = wrong_frame_rate is not None and wrong_frame_rate > 0.5
    result: list[dict[str, Any]] = []
    for idx, row in enumerate(temporal_rows, start=1):
        label = str(row.get("temporal_cluster_label", ""))
        sample_pool = str(row.get("sample_pool", ""))
        stable = label == "stable_cluster_tube"
        dropout = sample_pool != PAIRED_POOL
        result.append(
            {
                "tube_probe_id": f"TUBE{idx:04d}",
                "structure_id_or_proxy_id": row.get("temporal_probe_id", f"TUBE{idx:04d}"),
                "mode_name": row.get("mode_name", ""),
                "sample_pool": sample_pool,
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "frame_window": row.get("sar_frame_span", ""),
                "stability_label": label,
                "drift_or_centroid_change_px": row.get("centroid_step_mean_px", ""),
                "peak_consistency": row.get("cluster_persistence_rate", ""),
                "range_extent_stability": "partial_not_available_in_existing_temporal_probe",
                "azimuth_extent_stability": "partial_not_available_in_existing_temporal_probe",
                "scatter_structure_mix": row.get("scatter_cluster_type_mix", ""),
                "whether_temporal_evidence_strengthens_association": "partial_posthoc_support" if stable and not dropout else "no",
                "whether_temporal_evidence_only_supports_existence": "yes" if dropout else "no",
                "whether_temporal_evidence_is_confounded_by_wrong_frame_control": "yes_needs_motion_or_change_gate" if wrong_frame_high else "not_indicated_by_current_summary",
                "provenance_labels": "SAR_temporal_observation;SAR_image_observation;hypothesis_to_validate",
                "notes": "Dropout/no-match rows are temporal continuation/existence support only; they are not clean morphology.",
            }
        )
    return result


def build_association_provenance() -> list[dict[str, Any]]:
    yes = "yes"
    no = "no"
    rows = [
        {
            "gate_name": "C_time",
            "evidence_source": "optical frame stream plus 24fps-to-50fps software-sync contract",
            "runtime_safe_optical_evidence": yes,
            "runtime_safe_temporal_evidence": yes,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "runtime feasible-domain construction",
            "not_allowed_use": "hardware timestamp truth or identity truth",
            "leakage_risk": "low GT leakage risk; synchronization uncertainty remains",
            "current_support_level": "supported as software-sync tube, not exact timestamp",
            "main_failure_mode": "wrong-frame control remains high after SAR observation",
            "next_validation_needed": "temporal-change and object-motion gates",
        },
        {
            "gate_name": "C_az",
            "evidence_source": "fan-polar azimuth support from optical object context",
            "runtime_safe_optical_evidence": yes,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": yes,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "runtime support-sector construction",
            "not_allowed_use": "strong association gate by itself",
            "leakage_risk": "overlap/margin risk, not GT leakage",
            "current_support_level": "weak to moderate; azimuth-shift remains high",
            "main_failure_mode": "sector overlap and broad margins",
            "next_validation_needed": "overlap-aware azimuth margin audit",
        },
        {
            "gate_name": "C_shell",
            "evidence_source": "vehicle physical footprint assumptions",
            "runtime_safe_optical_evidence": no,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": yes,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "runtime feasible-domain constraint",
            "not_allowed_use": "final SAR box approximation",
            "leakage_risk": "low if kept as physical prior range",
            "current_support_level": "conceptually supported; still broad for association",
            "main_failure_mode": "edge/truncated cases need relaxed shell",
            "next_validation_needed": "state-conditioned footprint behavior",
        },
        {
            "gate_name": "C_state",
            "evidence_source": "optical object state labels and uncertainty categories",
            "runtime_safe_optical_evidence": yes,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": yes,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "runtime uncertainty modulation",
            "not_allowed_use": "state-conditioned top-k success as runtime rule",
            "leakage_risk": "medium if posthoc range success is promoted",
            "current_support_level": "important but not independently sufficient",
            "main_failure_mode": "duplicate/handoff and review-only states remain ambiguous",
            "next_validation_needed": "GM_RM019 optical object continuity review",
        },
        {
            "gate_name": "C_range",
            "evidence_source": "state-conditioned and object-smoothed range-band posthoc hypotheses",
            "runtime_safe_optical_evidence": no,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": "partial",
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": yes,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "posthoc mechanism validation only in this branch",
            "not_allowed_use": "runtime prior construction or tuned range rule",
            "leakage_risk": "high if GT-validated bands are copied into runtime",
            "current_support_level": "strong posthoc signal versus random/range-shift",
            "main_failure_mode": "wrong-object and wrong-frame remain high",
            "next_validation_needed": "runtime-safe optical-only range derivation",
        },
        {
            "gate_name": "G_support",
            "evidence_source": "support-region observation and GT coverage validation",
            "runtime_safe_optical_evidence": "partial",
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": yes,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": yes,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "posthoc coverage and mechanism audit",
            "not_allowed_use": "claiming association from support existence alone",
            "leakage_risk": "medium through GT coverage metrics",
            "current_support_level": "support can contain signal but may be too broad",
            "main_failure_mode": "support exists without unique SAR structure",
            "next_validation_needed": "separate support exists from structure exists",
        },
        {
            "gate_name": "G_structure",
            "evidence_source": "SAR scatter-cluster structure descriptors",
            "runtime_safe_optical_evidence": no,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": yes,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": "partial",
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "SAR observation mechanism",
            "not_allowed_use": "selector feature or final center",
            "leakage_risk": "medium if GT-near labels are used to choose structure",
            "current_support_level": "useful vocabulary; representation still incomplete",
            "main_failure_mode": "diffuse/spread/weak structures dominate",
            "next_validation_needed": "structure vocabulary review on visual exemplars",
        },
        {
            "gate_name": "G_cluster",
            "evidence_source": "top-k peak group, centroid, compactness, spread",
            "runtime_safe_optical_evidence": no,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": yes,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": "partial",
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "SAR observation diagnostic",
            "not_allowed_use": "ranking or top1/top-k optimization",
            "leakage_risk": "medium if best top-k to GT is promoted",
            "current_support_level": "peak competition remains serious",
            "main_failure_mode": "top1/top2 competition and multi-peak ambiguity",
            "next_validation_needed": "cluster grouping across adjacent frames",
        },
        {
            "gate_name": "G_temporal",
            "evidence_source": "SAR temporal tube and cluster persistence",
            "runtime_safe_optical_evidence": no,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": yes,
            "SAR_temporal_observation": yes,
            "SAR_GT_posthoc_evidence": "partial",
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "SAR temporal observation",
            "not_allowed_use": "wrong-frame-tolerant identity claim",
            "leakage_risk": "medium if posthoc tube success is copied into runtime",
            "current_support_level": "partial; stable tubes exist but wrong-frame remains high",
            "main_failure_mode": "background persistence or frame-insensitive structure",
            "next_validation_needed": "object-motion and temporal-change constraints",
        },
        {
            "gate_name": "G_motion",
            "evidence_source": "optical tracklet trend versus SAR structure drift",
            "runtime_safe_optical_evidence": yes,
            "runtime_safe_temporal_evidence": yes,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": yes,
            "SAR_temporal_observation": yes,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": no,
            "hypothesis_to_validate": yes,
            "allowed_stage": "future mechanism validation",
            "not_allowed_use": "current selector or final annotation",
            "leakage_risk": "low if defined without GT residual",
            "current_support_level": "not sufficiently measured in existing tables",
            "main_failure_mode": "motion/drift columns are incomplete",
            "next_validation_needed": "derive drift compatibility without GT labels",
        },
        {
            "gate_name": "G_optical_tracklet_quality",
            "evidence_source": "OTY optical object stream, state mix, duplicate/handoff review",
            "runtime_safe_optical_evidence": yes,
            "runtime_safe_temporal_evidence": yes,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": "partial",
            "hypothesis_to_validate": yes,
            "allowed_stage": "optical hypothesis qualification",
            "not_allowed_use": "identity truth",
            "leakage_risk": "low if review anchor is labeled separately",
            "current_support_level": "GM_RM019 needs review; GM_RM011 blocked",
            "main_failure_mode": "object identity continuity unresolved",
            "next_validation_needed": "small GM_RM019 optical continuity review",
        },
        {
            "gate_name": "G_review_or_manual_anchor",
            "evidence_source": "manual/review anchor, if separately labeled",
            "runtime_safe_optical_evidence": no,
            "runtime_safe_temporal_evidence": no,
            "runtime_safe_geometry_or_vehicle_physics": no,
            "SAR_image_observation": no,
            "SAR_temporal_observation": no,
            "SAR_GT_posthoc_evidence": no,
            "manual_or_review_anchor": yes,
            "hypothesis_to_validate": yes,
            "allowed_stage": "review quality anchor and exemplar selection",
            "not_allowed_use": "annotation proposal or identity truth",
            "leakage_risk": "medium if manual anchor is mixed into runtime labels",
            "current_support_level": "allowed only as separate provenance",
            "main_failure_mode": "manual anchor can hide association ambiguity",
            "next_validation_needed": "keep review candidate list separate from annotation proposal",
        },
    ]
    return rows


def build_failure_transition_table(
    support_rows: Sequence[Mapping[str, Any]],
    cluster_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    state_cluster = [
        row for row in cluster_rows if row.get("mode_name") == STATE_MODE and row.get("sample_pool") == PAIRED_POOL
    ]
    state_dropout = [
        row for row in cluster_rows if row.get("mode_name") == STATE_MODE and row.get("sample_pool") != PAIRED_POOL
    ]
    status_counts = Counter(row.get("gated_association_status", "") for row in state_cluster)
    weak_no_structure = sum(1 for row in support_rows if row.get("sar_structure_exists") == "no")
    associated = status_counts.get("associated_posthoc_weak", 0) + status_counts.get("associated_posthoc_strong", 0)
    definitions = [
        (
            "isolated_optical_support_only",
            weak_no_structure,
            "state_conditioned paired rows",
            "support exists but SAR structure is weak/no-structure",
            "optical support exists and needs SAR observation follow-up",
            "do not call this a target or final box",
            "support does not isolate SAR structure",
            "inspect whether range/azimuth support is too broad or SAR crop is weak",
        ),
        (
            "isolated_sar_structure_only",
            EXPECTED_LEDGER["sar_only_gt"],
            "SAR-only reference ledger",
            "SAR morphology exists without current optical object counterpart",
            "use as SAR morphology/reference pool only",
            "do not mix into optical-SAR correspondence",
            "no optical object hypothesis",
            "keep SAR-only morphology tables separate",
        ),
        (
            "weak_support",
            status_counts.get("associated_posthoc_weak", 0),
            "state_conditioned paired rows",
            "limited support plus non-final SAR structure",
            "weak posthoc support requiring review/provenance",
            "not final annotation or identity truth",
            "association remains under-supported",
            "add temporal and object-quality gates",
        ),
        (
            "review_required",
            status_counts.get("review_required", 0),
            "state_conditioned paired rows",
            "optical ambiguity, duplicate/handoff, or review-only state",
            "manual/review anchor may be separate provenance",
            "do not auto-resolve identity",
            "optical object hypothesis quality is unresolved",
            "GM_RM019 optical continuity review",
        ),
        (
            "dropout_existence_support_only",
            len(state_dropout),
            "dropout/no-match special pool",
            "current-frame optical detection dropout or severe truncation",
            "temporal continuation/existence support only",
            "do not mix into clean paired morphology",
            "not a clean morphology sample",
            "separate dropout recovery and SAR support audit",
        ),
        (
            "rejected_for_temporal_instability",
            status_counts.get("rejected_for_temporal_instability", 0),
            "state_conditioned paired rows",
            "SAR cluster does not persist as a usable tube",
            "reject/hold association pending temporal evidence",
            "do not trust single-frame bright peak",
            "jumping or unstable SAR structure",
            "tube-level drift and persistence probe",
        ),
        (
            "rejected_for_peak_competition",
            status_counts.get("rejected_for_peak_competition", 0),
            "state_conditioned paired rows",
            "top1/top2 or local peaks remain too competitive",
            "peak competition explains why top1 is insufficient",
            "do not tune a top-k selector",
            "local peak ambiguity",
            "structure grouping instead of top-k optimization",
        ),
        (
            "sar_structure_present_but_optical_ambiguous",
            status_counts.get("sar_structure_present_but_optical_ambiguous", 0),
            "state_conditioned paired rows",
            "SAR structure exists but optical object hypothesis is ambiguous",
            "SAR can support review but not settle optical identity",
            "do not claim identity truth",
            "object association unresolved",
            "optical tracklet quality and review anchor",
        ),
        (
            "optical_support_present_but_sar_ambiguous",
            status_counts.get("optical_support_present_but_sar_ambiguous", 0),
            "state_conditioned paired rows",
            "optical support exists but SAR structure is diffuse/ambiguous",
            "hold as weak evidence or review-required",
            "do not force an association candidate",
            "SAR representation insufficient",
            "visual SAR exemplar inspection and vocabulary refinement",
        ),
        (
            "associated_posthoc_candidate",
            associated,
            "state_conditioned paired rows",
            "posthoc support, SAR structure, and gates are jointly plausible",
            "posthoc association candidate only",
            "not identity truth and not final annotation",
            "still vulnerable to wrong-object/wrong-frame confounding",
            "provenance matrix plus negative-control recheck",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for state, count, scope, condition, allowed, disallowed, failure, next_needed in definitions:
        rows.append(
            {
                "transition_state": state,
                "n_rows_or_reference_count": count,
                "row_scope": scope,
                "entry_condition": condition,
                "allowed_interpretation": allowed,
                "not_allowed_interpretation": disallowed,
                "main_failure_mode": failure,
                "next_validation_needed": next_needed,
                "provenance_labels": "hypothesis_to_validate;SAR_image_observation;manual_or_review_anchor",
            }
        )
    return rows


def build_summary(
    timestamp: str,
    vocabulary_rows: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    crosscheck_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    provenance_rows: Sequence[Mapping[str, Any]],
    transition_rows: Sequence[Mapping[str, Any]],
    confounder_summary: Mapping[str, Any],
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    key_metrics = dict(confounder_summary.get("key_metrics", {}))
    structure_exists = sum(1 for row in support_rows if row.get("sar_structure_exists") == "yes")
    vehicle_like = sum(1 for row in support_rows if row.get("vehicle_like_sar_structure_exists") == "yes")
    unique = sum(1 for row in support_rows if row.get("unique_sar_structure_exists") == "yes")
    associated = sum(1 for row in support_rows if row.get("association_candidate_exists") == "yes")
    no_unique = sum(1 for row in support_rows if row.get("no_unique_structure_can_be_isolated") == "yes")
    too_broad = sum(1 for row in support_rows if row.get("support_too_broad_for_association") == "yes")
    key_metrics.update(
        {
            "state_conditioned_support_observation_rows": len(support_rows),
            "state_conditioned_sar_structure_exists_rate": rate(structure_exists, len(support_rows)),
            "state_conditioned_vehicle_like_structure_exists_rate": rate(vehicle_like, len(support_rows)),
            "state_conditioned_unique_structure_exists_rate": rate(unique, len(support_rows)),
            "state_conditioned_association_candidate_exists_rate_posthoc": rate(associated, len(support_rows)),
            "state_conditioned_no_unique_structure_rate": rate(no_unique, len(support_rows)),
            "state_conditioned_support_too_broad_for_association_rate": rate(too_broad, len(support_rows)),
        }
    )
    answers = {
        "candidate_layering": (
            "Candidate is no longer a single box candidate. This run separates optical object hypothesis, "
            "support region or feasible domain, SAR scatter-structure candidate or temporal tube, and only then "
            "posthoc association candidate."
        ),
        "range_state_signal": (
            "State-conditioned true support is stronger than random and range-shift controls, so range/state "
            "support contains real posthoc signal."
        ),
        "association_confounding": (
            "Wrong-object and wrong-frame controls remain high; this is object-time association confounding, "
            "not a reason to declare the SAR image path failed."
        ),
        "azimuth_confounding": (
            "Azimuth-shift remains high, so azimuth cannot be used as a strong gate before sector overlap and "
            "margin behavior are explained."
        ),
        "local_optimization_guard": (
            "No selector, ranking, training, threshold tuning, final box, or identity truth is introduced. "
            "The outputs are vocabulary, provenance, temporal, counterfactual, and failure-transition tables."
        ),
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "ledger_valid": True,
            "category_counts": EXPECTED_LEDGER,
            "note": "This run preserves 215 paired, 195 GM_RM011 blocked missing object stream, 20 SAR-only, and 12 dropout/no-match continuation pool.",
        },
        "row_scope": (
            "The 215 support-observation rows are state-conditioned paired rows. SAR-only rows are only referenced "
            "as a SAR morphology pool in the transition model. Dropout/no-match rows remain temporal continuation "
            "or existence support only."
        ),
        "row_counts": {
            "sar_structure_vocabulary": len(vocabulary_rows),
            "support_region_structure_observation": len(support_rows),
            "structure_counterfactual_crosscheck": len(crosscheck_rows),
            "structure_temporal_tube_probe": len(temporal_rows),
            "association_provenance_matrix": len(provenance_rows),
            "failure_transition_table": len(transition_rows),
        },
        "key_metrics": key_metrics,
        "question_answers": answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "partial_data_limitations": [
            "Existing temporal-tube CSV does not contain explicit range-extent or azimuth-extent stability columns; those fields are marked partial.",
            "Current support-observation rows reuse state-conditioned posthoc range bands; they are not runtime range rules.",
            "Wrong-object and azimuth overlap buckets come from separate triage outputs and are not available for every raw counterfactual row.",
            "GM_RM019 review candidate extraction is not opened in this run; it remains a next-step quality anchor, not an annotation proposal.",
        ],
        "posthoc_hypotheses_only": [
            "GT-near top-k and GT-inside support remain validation metrics.",
            "State-conditioned range success remains a posthoc hypothesis until derived from runtime-safe optical-only evidence.",
            "Associated posthoc candidate is an explanatory state, not identity truth.",
            "SAR structure vocabulary fields are mechanism observations, not selector features.",
        ],
        "next_steps": [
            "Inspect visual exemplars for compact, multi-peak, spread, diffuse, and stable-tube categories.",
            "Add motion/drift compatibility gates that can explain wrong-frame persistence.",
            "Audit azimuth overlap and sector-margin behavior before using azimuth as a strong gate.",
            "Run a small GM_RM019 optical object continuity review as a separate quality anchor.",
            "Recover GM_RM011 object stream only as a later scale-expansion step.",
        ],
        "outputs": outputs,
        "sources": sources,
    }


def render_plan_doc(path: Path, timestamp: str, sources: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 SAR Structure Representation And Association Provenance Plan",
        "",
        f"Updated: {timestamp}",
        "",
        "This plan defines a mechanism exploration stage. It is not OTY3, not final automatic annotation, not selector/ranking, not training, not threshold tuning, and not an identity-truth claim.",
        "",
        "## Project Understanding Before Running",
        "",
        "1. Current candidate cannot be understood as a simple box candidate.",
        "2. The safer layered candidate semantics are:",
        "",
        "- optical object hypothesis",
        "- support region / feasible domain",
        "- SAR scatter-structure candidate / structure tube",
        "- posthoc association candidate",
        "",
        "3. The key question is not whether the support region contains a bright point. The key question is how SAR target structure is represented inside a still-large compressed support region, and when that structure can be associated with a specific optical object hypothesis under provenance limits.",
        "",
        "## Fixed Ledger Boundary",
        "",
        "- paired_optical_object_sar_gt = 215",
        "- blocked_missing_gm011_object_stream = 195",
        "- sar_only_gt = 20",
        "- dropout/no_oty_iou_match/temporal continuation pool = 12",
        "",
        "The 215 paired rows are frame-level posthoc pairs, not all GT and not independent physical identity truth. GM_RM011 is blocked by missing current OTY optical object stream, not by missing annotation. SAR-only rows are morphology references only. Dropout/no-match rows are temporal continuation or existence support only.",
        "",
        "## Exploration Lines",
        "",
        "- Line A: SAR structure vocabulary. Convert bright-point observations into compact, multi-peak, spread, diffuse, weak, jumping, stable-tube, and unstable-tube structure semantics.",
        "- Line B: Support region to structure observation. Separate support exists, SAR structure exists, vehicle-like structure exists, unique structure exists, and posthoc association candidate exists.",
        "- Line C: Structure by counterfactual cross-check. Explain true, random, range-shift, azimuth-shift, wrong-object, and wrong-frame outcomes without reducing them to hit rates.",
        "- Line D: SAR temporal tube probe. Keep single-frame cluster evidence separate from temporal persistence and dropout existence support.",
        "- Line E: Association provenance and failure transition. Define which gates are runtime-safe, SAR observation, posthoc validation, manual/review anchor, or hypothesis only.",
        "",
        "## Local-Optimization Guard",
        "",
        "This run must answer mechanism questions instead of optimizing top-k or selector metrics. It introduces no selector/ranking, no thresholds, no candidate boxes, and no training. It reuses existing SAR observation and counterfactual outputs to build vocabulary, provenance, and transition tables.",
        "",
        "## Inputs",
        "",
    ]
    for name, source in sources.items():
        lines.append(f"- {name}: `{source}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 SAR Structure Representation And Association Provenance Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report consolidates OTY2 structure, temporal, and counterfactual diagnostics into mechanism tables. It does not generate final annotations, selector/ranking output, training, tuned thresholds, or identity truth.",
        "",
        "## Ledger Boundary",
        "",
        "- paired_optical_object_sar_gt = 215",
        "- blocked_missing_gm011_object_stream = 195",
        "- sar_only_gt = 20",
        "- dropout/no_oty_iou_match/temporal continuation pool = 12",
        "",
        summary["row_scope"],
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in summary["key_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Main Mechanism Findings", ""])
    for key in ["candidate_layering", "range_state_signal", "association_confounding", "azimuth_confounding"]:
        lines.append(f"- {summary['question_answers'][key]}")
    lines.extend(
        [
            "",
            "## Line A: SAR Structure Vocabulary",
            "",
            "The vocabulary separates compact clusters, multi-peak clusters, range/azimuth spread, diffuse clutter, weak/no-structure, jumping peaks, stable tubes, and diffuse/unstable tubes. These fields are mechanism observations and must not be promoted to selector features.",
            "",
            "## Line B: Support Region To Structure Observation",
            "",
            "The support table uses the 215 state-conditioned paired rows and keeps five states separate: support exists, SAR structure exists, vehicle-like structure exists, unique SAR structure exists, and posthoc association candidate exists.",
            "",
            "## Line C: Structure By Counterfactual Cross-Check",
            "",
            "True support is clearly stronger than random and range-shift controls, which supports real range/state signal. Wrong-object, wrong-frame, and azimuth-shift remain high enough to require provenance and confounder modeling rather than a SAR-route rejection.",
            "",
            "## Line D: SAR Temporal Tube Probe",
            "",
            "Temporal rows distinguish stable cluster tubes, jumping peaks, diffuse/unstable tubes, and dropout existence support. Existing inputs do not yet provide explicit range-extent or azimuth-extent stability, so those columns are marked partial instead of fabricated.",
            "",
            "## Line E: Association Provenance And Failure Transition",
            "",
            "The provenance matrix separates runtime-safe optical/time/geometry/state constraints from SAR image observation, SAR temporal observation, posthoc GT validation, and review anchors. The failure-transition table keeps associated_posthoc_candidate as a posthoc state only, not identity truth.",
            "",
            "## Why This Is Not A Local Top-K/Selector Optimization",
            "",
            "1. This run introduces no selector/ranking, no candidate scoring, no final box, no training, and no threshold tuning.",
            "2. It is not looking for a better top-k metric; it reframes the current evidence into SAR structure vocabulary, temporal tube behavior, counterfactual provenance, and failure transitions.",
            "3. It explains wrong-object, wrong-frame, and azimuth-shift high hits as object-time/overlap/temporal confounding that must be modeled before association.",
            "4. It produces reusable vocabulary, provenance, and transition tables that can be checked across samples.",
            "5. GT-near top-k, GT-inside support, state-conditioned range success, and associated_posthoc_candidate remain posthoc hypotheses and cannot enter runtime prior construction.",
            "6. The next expansion should add motion/temporal-change gates and visual exemplars, not tune a single metric.",
            "",
            "## Partial Data Limitations",
            "",
        ]
    )
    for item in summary["partial_data_limitations"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Posthoc Hypotheses Only", ""])
    for item in summary["posthoc_hypotheses_only"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Steps", ""])
    for item in summary["next_steps"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for name, output_path in summary["outputs"].items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(["", "## Sources", ""])
    for name, source_path in summary["sources"].items():
        lines.append(f"- {name}: `{source_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_sar_structure_representation_and_association_provenance_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_sar_structure_representation_and_association_provenance",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        "new_sar_image_extraction=false",
        "selector_or_ranking_used=false",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "scatter_cluster_structure_probe_csv": Path(args.scatter_cluster_csv) if args.scatter_cluster_csv else latest_path("oty2_scatter_cluster_structure_probe_*.csv"),
        "temporal_cluster_association_probe_csv": Path(args.temporal_cluster_csv) if args.temporal_cluster_csv else latest_path("oty2_temporal_cluster_association_probe_*.csv"),
        "counterfactual_support_validation_csv": Path(args.counterfactual_csv) if args.counterfactual_csv else latest_path("oty2_counterfactual_support_validation_*.csv"),
        "counterfactual_confounder_triage_csv": Path(args.triage_csv) if args.triage_csv else latest_path("oty2_counterfactual_confounder_triage_*.csv"),
        "wrong_object_overlap_triage_csv": Path(args.wrong_object_csv) if args.wrong_object_csv else latest_path("oty2_wrong_object_overlap_triage_*.csv"),
        "wrong_frame_offset_triage_csv": Path(args.wrong_frame_csv) if args.wrong_frame_csv else latest_path("oty2_wrong_frame_offset_triage_*.csv"),
        "azimuth_shift_overlap_triage_csv": Path(args.azimuth_csv) if args.azimuth_csv else latest_path("oty2_azimuth_shift_overlap_triage_*.csv"),
        "gated_summary_json": Path(args.gated_summary_json) if args.gated_summary_json else latest_path("oty2_gated_association_scatter_cluster_summary_*.json"),
        "parallel_summary_json": Path(args.parallel_summary_json) if args.parallel_summary_json else latest_path("oty2_parallel_mechanism_exploration_summary_*.json"),
        "confounder_summary_json": Path(args.confounder_summary_json) if args.confounder_summary_json else latest_path("oty2_counterfactual_confounder_triage_summary_*.json"),
    }
    gated_summary = json.loads(paths["gated_summary_json"].read_text(encoding="utf-8"))
    parallel_summary = json.loads(paths["parallel_summary_json"].read_text(encoding="utf-8"))
    confounder_summary = json.loads(paths["confounder_summary_json"].read_text(encoding="utf-8"))
    validate_ledger(gated_summary, "gated summary")
    validate_ledger(parallel_summary, "parallel summary")
    validate_ledger(confounder_summary, "confounder summary")
    cluster_rows = read_csv(paths["scatter_cluster_structure_probe_csv"])
    state_rows = [row for row in cluster_rows if row.get("mode_name") == STATE_MODE and row.get("sample_pool") == PAIRED_POOL]
    if len(state_rows) != EXPECTED_LEDGER["paired_optical_object_sar_gt"]:
        raise RuntimeError(f"Expected 215 state-conditioned paired structure rows; got {len(state_rows)}")
    counterfactual_rows = read_csv(paths["counterfactual_support_validation_csv"])
    if any(row.get("sample_pool") != PAIRED_POOL for row in counterfactual_rows):
        raise RuntimeError("Counterfactual input contains non-paired rows; refusing to mix sample pools.")
    return {
        "paths": paths,
        "gated_summary": gated_summary,
        "parallel_summary": parallel_summary,
        "confounder_summary": confounder_summary,
        "cluster_rows": cluster_rows,
        "temporal_rows": read_csv(paths["temporal_cluster_association_probe_csv"]),
        "counterfactual_rows": counterfactual_rows,
        "triage_rows": read_csv(paths["counterfactual_confounder_triage_csv"]),
        "wrong_object_rows": read_csv(paths["wrong_object_overlap_triage_csv"]),
        "wrong_frame_rows": read_csv(paths["wrong_frame_offset_triage_csv"]),
        "azimuth_rows": read_csv(paths["azimuth_shift_overlap_triage_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    sources = {name: str(path) for name, path in inputs["paths"].items()}

    vocabulary_rows = build_vocabulary(inputs["cluster_rows"], inputs["temporal_rows"])
    support_rows = build_support_observations(inputs["cluster_rows"], inputs["counterfactual_rows"])
    crosscheck_rows = build_counterfactual_crosscheck(
        inputs["counterfactual_rows"],
        inputs["wrong_object_rows"],
        inputs["azimuth_rows"],
    )
    tube_rows = build_temporal_tube_probe(inputs["temporal_rows"], inputs["confounder_summary"])
    provenance_rows = build_association_provenance()
    transition_rows = build_failure_transition_table(support_rows, inputs["cluster_rows"])

    plan_doc = DOCS_DIR / "oty2_sar_structure_representation_and_association_provenance_plan.md"
    vocabulary_csv = REPORT_DIR / f"oty2_sar_structure_vocabulary_{timestamp}.csv"
    support_csv = REPORT_DIR / f"oty2_support_region_structure_observation_{timestamp}.csv"
    crosscheck_csv = REPORT_DIR / f"oty2_structure_counterfactual_crosscheck_{timestamp}.csv"
    tube_csv = REPORT_DIR / f"oty2_structure_temporal_tube_probe_{timestamp}.csv"
    provenance_csv = REPORT_DIR / f"oty2_association_provenance_matrix_{timestamp}.csv"
    transition_csv = REPORT_DIR / f"oty2_failure_transition_table_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_sar_structure_representation_and_association_provenance_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_sar_structure_representation_and_association_provenance_summary_{timestamp}.json"

    outputs = {
        "plan_doc": str(plan_doc),
        "sar_structure_vocabulary_csv": str(vocabulary_csv),
        "support_region_structure_observation_csv": str(support_csv),
        "structure_counterfactual_crosscheck_csv": str(crosscheck_csv),
        "structure_temporal_tube_probe_csv": str(tube_csv),
        "association_provenance_matrix_csv": str(provenance_csv),
        "failure_transition_table_csv": str(transition_csv),
        "sar_structure_representation_and_association_provenance_report_md": str(report_md),
        "sar_structure_representation_and_association_provenance_summary_json": str(summary_json),
    }
    summary = build_summary(
        timestamp,
        vocabulary_rows,
        support_rows,
        crosscheck_rows,
        tube_rows,
        provenance_rows,
        transition_rows,
        inputs["confounder_summary"],
        sources,
        outputs,
    )
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    render_plan_doc(plan_doc, timestamp, sources)
    write_csv(vocabulary_csv, vocabulary_rows, VOCABULARY_FIELDS)
    write_csv(support_csv, support_rows, SUPPORT_OBSERVATION_FIELDS)
    write_csv(crosscheck_csv, crosscheck_rows, COUNTERFACTUAL_FIELDS)
    write_csv(tube_csv, tube_rows, TEMPORAL_TUBE_FIELDS)
    write_csv(provenance_csv, provenance_rows, PROVENANCE_FIELDS)
    write_csv(transition_csv, transition_rows, FAILURE_FIELDS)
    render_report(report_md, summary)
    write_json(summary_json, summary)

    print(
        json.dumps(
            {
                "outputs": summary["outputs"],
                "row_counts": summary["row_counts"],
                "key_metrics": summary["key_metrics"],
                "boundary_flags": summary["boundary_flags"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--scatter-cluster-csv", default="")
    parser.add_argument("--temporal-cluster-csv", default="")
    parser.add_argument("--counterfactual-csv", default="")
    parser.add_argument("--triage-csv", default="")
    parser.add_argument("--wrong-object-csv", default="")
    parser.add_argument("--wrong-frame-csv", default="")
    parser.add_argument("--azimuth-csv", default="")
    parser.add_argument("--gated-summary-json", default="")
    parser.add_argument("--parallel-summary-json", default="")
    parser.add_argument("--confounder-summary-json", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
