"""OTY2 counterfactual confounder triage.

This script is a small closeout diagnostic for the OTY2 counterfactual support
bootstrap. It does not extract new SAR image features. It reads the existing
counterfactual support validation CSV and explains why several negative
controls remained high.

Outputs are posthoc diagnostics and handoff notes only. They are not final
annotation proposals, selector/ranking outputs, training, threshold tuning, or
identity-truth claims.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from run_oty2_range_narrowing_peak_competition_audit import (
    EXPECTED_LEDGER,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    compact_counts,
    fmt,
    groupby_key,
    latest_path,
    mean_clean,
    median_clean,
    read_csv,
    safe_float,
    safe_int,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": False,
    "counterfactual_existing_sar_observation_reused": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "gt_peak_or_residual_written_to_runtime_prior": False,
    "annotation_proposal_entered": False,
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

TRIAGE_FIELDS = [
    "triage_id",
    "triage_line",
    "source_mode_name",
    "bucket",
    "state_condition",
    "control_support_type",
    "control_variant_group",
    "n_rows",
    "topk_contains_near_gt_rate_posthoc",
    "top1_near_gt_rate_posthoc",
    "gt_inside_support_rate_posthoc",
    "reference_true_topk_rate_posthoc",
    "delta_vs_true_rate_posthoc",
    "median_best_topk_distance_to_gt_px_posthoc",
    "median_peak_background_ratio",
    "median_support_area_px",
    "median_support_overlap_iou_proxy",
    "median_support_intersection_ratio_vs_true",
    "scatter_cluster_type_mix",
    "temporal_stability_label_mix",
    "interpretation",
    "provenance_labels",
]

WRONG_OBJECT_FIELDS = [
    "wrong_object_triage_id",
    "source_mode_name",
    "scene",
    "object_hypothesis_id",
    "wrong_object_hypothesis_id",
    "state_condition",
    "optical_frame",
    "expected_sar_frame",
    "wrong_object_source_sar_frame",
    "wrong_object_frame_delta",
    "same_scene",
    "azimuth_overlap_deg",
    "azimuth_overlap_ratio_vs_true",
    "range_overlap_px",
    "range_overlap_ratio_vs_true",
    "support_iou_proxy",
    "support_intersection_ratio_vs_true",
    "overlap_bucket",
    "topk_contains_near_gt_posthoc",
    "top1_near_gt_posthoc",
    "gt_inside_support_posthoc",
    "best_topk_distance_to_gt_px_posthoc",
    "top1_background_ratio",
    "scatter_cluster_type",
    "temporal_stability_label",
    "notes",
    "provenance_labels",
]

WRONG_FRAME_FIELDS = [
    "wrong_frame_triage_id",
    "source_mode_name",
    "offset_bucket",
    "offset_sign",
    "n_rows",
    "median_abs_frame_offset",
    "min_abs_frame_offset",
    "max_abs_frame_offset",
    "topk_contains_near_gt_rate_posthoc",
    "top1_near_gt_rate_posthoc",
    "gt_inside_support_rate_posthoc",
    "median_best_topk_distance_to_gt_px_posthoc",
    "median_peak_background_ratio",
    "median_support_area_px",
    "scatter_cluster_type_mix",
    "temporal_stability_label_mix",
    "interpretation",
    "provenance_labels",
]

AZIMUTH_FIELDS = [
    "azimuth_shift_triage_id",
    "source_mode_name",
    "shift_deg",
    "shift_magnitude_deg",
    "shift_sign",
    "azimuth_overlap_bucket",
    "n_rows",
    "median_azimuth_overlap_ratio_vs_true",
    "median_support_iou_proxy",
    "topk_contains_near_gt_rate_posthoc",
    "top1_near_gt_rate_posthoc",
    "gt_inside_support_rate_posthoc",
    "median_peak_background_ratio",
    "median_support_area_px",
    "scatter_cluster_type_mix",
    "temporal_stability_label_mix",
    "interpretation",
    "provenance_labels",
]


def bool_is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def rate(num: int, den: int) -> str:
    return fmt(num / den if den else None, 4)


def parse_variant_value(text: str, key: str) -> float | None:
    for part in str(text or "").split(";"):
        if "=" not in part:
            continue
        k, value = part.split("=", 1)
        if k.strip() == key:
            return safe_float(value)
    return None


def parse_control_reference(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in str(text or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    lo = max(min(a0, a1), min(b0, b1))
    hi = min(max(a0, a1), max(b0, b1))
    return max(0.0, hi - lo)


def interval_width(a0: float, a1: float) -> float:
    return max(0.0, max(a0, a1) - min(a0, a1))


def row_support(row: Mapping[str, Any]) -> dict[str, float]:
    return {
        "az0": safe_float(row.get("support_azimuth_start_deg"), -89.0) or -89.0,
        "az1": safe_float(row.get("support_azimuth_end_deg"), 89.0) or 89.0,
        "r0": safe_float(row.get("support_radius_min_px"), 0.0) or 0.0,
        "r1": safe_float(row.get("support_radius_max_px"), 0.0) or 0.0,
    }


def support_overlap_metrics(true_row: Mapping[str, Any], control_row: Mapping[str, Any]) -> dict[str, float]:
    t = row_support(true_row)
    c = row_support(control_row)
    az_overlap = interval_overlap(t["az0"], t["az1"], c["az0"], c["az1"])
    range_overlap = interval_overlap(t["r0"], t["r1"], c["r0"], c["r1"])
    true_az = interval_width(t["az0"], t["az1"])
    true_range = interval_width(t["r0"], t["r1"])
    ctrl_az = interval_width(c["az0"], c["az1"])
    ctrl_range = interval_width(c["r0"], c["r1"])
    inter = az_overlap * range_overlap
    true_area = true_az * true_range
    ctrl_area = ctrl_az * ctrl_range
    denom = true_area + ctrl_area - inter
    return {
        "azimuth_overlap_deg": az_overlap,
        "azimuth_overlap_ratio_vs_true": az_overlap / true_az if true_az > 0 else 0.0,
        "range_overlap_px": range_overlap,
        "range_overlap_ratio_vs_true": range_overlap / true_range if true_range > 0 else 0.0,
        "support_iou_proxy": inter / denom if denom > 0 else 0.0,
        "support_intersection_ratio_vs_true": inter / true_area if true_area > 0 else 0.0,
    }


def overlap_bucket(value: float | None) -> str:
    if value is None:
        return "overlap_unknown"
    if value >= 0.75:
        return "high_overlap_ge_0p75"
    if value >= 0.25:
        return "medium_overlap_0p25_0p75"
    if value > 0:
        return "low_overlap_lt_0p25"
    return "no_overlap"


def frame_offset_bucket(delta: int | None) -> str:
    if delta is None:
        return "offset_unknown"
    value = abs(delta)
    if value == 0:
        return "same_frame_or_zero_offset"
    if value <= 2:
        return "near_offset_1_2"
    if value <= 5:
        return "near_offset_3_5"
    if value <= 20:
        return "medium_offset_6_20"
    if value <= 50:
        return "far_offset_21_50"
    return "very_far_offset_gt_50"


def sign_bucket(delta: int | None) -> str:
    if delta is None:
        return "offset_unknown"
    if delta > 0:
        return "positive_offset"
    if delta < 0:
        return "negative_offset"
    return "zero_offset"


def shift_sign(value: float | None) -> str:
    if value is None:
        return "shift_unknown"
    if value > 0:
        return "positive_shift"
    if value < 0:
        return "negative_shift"
    return "zero_shift"


def truth_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("source_mode_name", "")),
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("expected_sar_frame", "")),
        str(row.get("support_source_peak_audit_id", "")),
    )


def topk_rate(rows: Sequence[Mapping[str, Any]]) -> float | None:
    return sum(1 for row in rows if bool_is_true(row.get("topk_contains_near_gt_posthoc"))) / len(rows) if rows else None


def true_rate_by_mode_state(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    groups = groupby_key(
        [row for row in rows if row.get("control_support_type") == "true_support"],
        lambda row: (str(row.get("source_mode_name", "")), str(row.get("state_condition", ""))),
    )
    for key, group in groups.items():
        rate_value = topk_rate(group)
        if rate_value is not None:
            result[key] = rate_value
    return result


def aggregate_common(
    group: Sequence[Mapping[str, Any]],
    reference_rate: float | None,
) -> dict[str, Any]:
    current_rate = topk_rate(group)
    return {
        "n_rows": len(group),
        "topk_contains_near_gt_rate_posthoc": fmt(current_rate, 4),
        "top1_near_gt_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("top1_near_gt_posthoc"))), len(group)),
        "gt_inside_support_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("gt_inside_support_posthoc"))), len(group)),
        "reference_true_topk_rate_posthoc": fmt(reference_rate, 4),
        "delta_vs_true_rate_posthoc": fmt(current_rate - reference_rate if current_rate is not None and reference_rate is not None else None, 4),
        "median_best_topk_distance_to_gt_px_posthoc": fmt(median_clean(row.get("best_topk_distance_to_gt_px_posthoc") for row in group), 3),
        "median_peak_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in group), 4),
        "median_support_area_px": fmt(median_clean(row.get("support_area_px") for row in group), 0),
        "scatter_cluster_type_mix": compact_counts(row.get("scatter_cluster_type", "") for row in group),
        "temporal_stability_label_mix": compact_counts(row.get("temporal_stability_label", "") for row in group),
    }


def build_wrong_object_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    true_by_key = {
        truth_key(row): row
        for row in rows
        if row.get("control_support_type") == "true_support"
    }
    result: list[dict[str, Any]] = []
    wrong_rows = [row for row in rows if row.get("control_support_type") == "wrong_object_support"]
    for idx, row in enumerate(wrong_rows, start=1):
        true = true_by_key.get(truth_key(row))
        metrics = support_overlap_metrics(true, row) if true else {}
        ref = parse_control_reference(str(row.get("control_source_reference", "")))
        expected = safe_int(row.get("expected_sar_frame"))
        source_frame = safe_int(ref.get("source_sar_frame"))
        frame_delta = source_frame - expected if source_frame is not None and expected is not None else None
        intersection_ratio = safe_float(metrics.get("support_intersection_ratio_vs_true"))
        bucket = overlap_bucket(intersection_ratio)
        note = (
            "high wrong-object rate is plausibly support-overlap/object-confusion"
            if bucket.startswith("high") or bucket.startswith("medium")
            else "low-overlap wrong-object hit suggests SAR structure or top-k mechanism lacks object discrimination"
        )
        result.append(
            {
                "wrong_object_triage_id": f"WO{idx:05d}",
                "source_mode_name": row.get("source_mode_name", ""),
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "wrong_object_hypothesis_id": ref.get("wrong_object", ""),
                "state_condition": row.get("state_condition", ""),
                "optical_frame": row.get("optical_frame", ""),
                "expected_sar_frame": row.get("expected_sar_frame", ""),
                "wrong_object_source_sar_frame": ref.get("source_sar_frame", ""),
                "wrong_object_frame_delta": frame_delta if frame_delta is not None else "",
                "same_scene": "true",
                "azimuth_overlap_deg": fmt(metrics.get("azimuth_overlap_deg"), 4),
                "azimuth_overlap_ratio_vs_true": fmt(metrics.get("azimuth_overlap_ratio_vs_true"), 4),
                "range_overlap_px": fmt(metrics.get("range_overlap_px"), 3),
                "range_overlap_ratio_vs_true": fmt(metrics.get("range_overlap_ratio_vs_true"), 4),
                "support_iou_proxy": fmt(metrics.get("support_iou_proxy"), 4),
                "support_intersection_ratio_vs_true": fmt(intersection_ratio, 4),
                "overlap_bucket": bucket,
                "topk_contains_near_gt_posthoc": row.get("topk_contains_near_gt_posthoc", ""),
                "top1_near_gt_posthoc": row.get("top1_near_gt_posthoc", ""),
                "gt_inside_support_posthoc": row.get("gt_inside_support_posthoc", ""),
                "best_topk_distance_to_gt_px_posthoc": row.get("best_topk_distance_to_gt_px_posthoc", ""),
                "top1_background_ratio": row.get("top1_background_ratio", ""),
                "scatter_cluster_type": row.get("scatter_cluster_type", ""),
                "temporal_stability_label": row.get("temporal_stability_label", ""),
                "notes": note,
                "provenance_labels": "runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return result


def build_wrong_frame_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    wrong_rows = [row for row in rows if row.get("control_support_type") == "wrong_sar_frame_support"]
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in wrong_rows:
        expected = safe_int(row.get("expected_sar_frame"))
        observed = safe_int(row.get("observed_sar_frame"))
        delta = observed - expected if expected is not None and observed is not None else None
        key = (str(row.get("source_mode_name", "")), frame_offset_bucket(delta), sign_bucket(delta))
        groups.setdefault(key, []).append(row)
    result: list[dict[str, Any]] = []
    for idx, ((mode, bucket, sign), group) in enumerate(sorted(groups.items()), start=1):
        deltas = []
        for row in group:
            expected = safe_int(row.get("expected_sar_frame"))
            observed = safe_int(row.get("observed_sar_frame"))
            if expected is not None and observed is not None:
                deltas.append(abs(observed - expected))
        rate_value = topk_rate(group)
        if bucket.startswith("near"):
            interpretation = "near wrong-frame high can be ordinary SAR temporal continuity; inspect motion-consistency gates"
        elif rate_value is not None and rate_value >= 0.50:
            interpretation = "far/medium wrong-frame remains high; SAR observation is frame-insensitive under current gate"
        else:
            interpretation = "wrong-frame support drops with offset; temporal gate likely has discriminative value"
        result.append(
            {
                "wrong_frame_triage_id": f"WF{idx:04d}",
                "source_mode_name": mode,
                "offset_bucket": bucket,
                "offset_sign": sign,
                "n_rows": len(group),
                "median_abs_frame_offset": fmt(median_clean(deltas), 3),
                "min_abs_frame_offset": min(deltas) if deltas else "",
                "max_abs_frame_offset": max(deltas) if deltas else "",
                "topk_contains_near_gt_rate_posthoc": fmt(rate_value, 4),
                "top1_near_gt_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("top1_near_gt_posthoc"))), len(group)),
                "gt_inside_support_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("gt_inside_support_posthoc"))), len(group)),
                "median_best_topk_distance_to_gt_px_posthoc": fmt(median_clean(row.get("best_topk_distance_to_gt_px_posthoc") for row in group), 3),
                "median_peak_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in group), 4),
                "median_support_area_px": fmt(median_clean(row.get("support_area_px") for row in group), 0),
                "scatter_cluster_type_mix": compact_counts(row.get("scatter_cluster_type", "") for row in group),
                "temporal_stability_label_mix": compact_counts(row.get("temporal_stability_label", "") for row in group),
                "interpretation": interpretation,
                "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return result


def build_azimuth_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    true_by_key = {
        truth_key(row): row
        for row in rows
        if row.get("control_support_type") == "true_support"
    }
    az_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("control_support_type") != "azimuth_shifted_support":
            continue
        true = true_by_key.get(truth_key(row))
        metrics = support_overlap_metrics(true, row) if true else {}
        shift = parse_variant_value(str(row.get("control_variant", "")), "delta_deg")
        merged = dict(row)
        merged.update({f"_overlap_{key}": value for key, value in metrics.items()})
        merged["_shift_deg"] = shift
        merged["_shift_mag"] = abs(shift) if shift is not None else None
        merged["_shift_sign"] = shift_sign(shift)
        merged["_azimuth_overlap_bucket"] = overlap_bucket(safe_float(metrics.get("azimuth_overlap_ratio_vs_true")))
        az_rows.append(merged)

    groups = groupby_key(
        az_rows,
        lambda row: (
            str(row.get("source_mode_name", "")),
            fmt(row.get("_shift_deg"), 1),
            fmt(row.get("_shift_mag"), 1),
            str(row.get("_shift_sign", "")),
            str(row.get("_azimuth_overlap_bucket", "")),
        ),
    )
    result: list[dict[str, Any]] = []
    for idx, ((mode, shift, mag, sign, bucket), group) in enumerate(sorted(groups.items()), start=1):
        rate_value = topk_rate(group)
        overlap = median_clean(row.get("_overlap_azimuth_overlap_ratio_vs_true") for row in group)
        if overlap is not None and overlap >= 0.50 and rate_value is not None and rate_value >= 0.50:
            interpretation = "high shifted result is largely explained by remaining azimuth overlap / wide sector margin"
        elif rate_value is not None and rate_value >= 0.50:
            interpretation = "large-shift support remains high; current azimuth gate is weak or SAR clutter generalizes across sector"
        else:
            interpretation = "shifted support drops; azimuth gate has discriminative value at this magnitude"
        result.append(
            {
                "azimuth_shift_triage_id": f"AZ{idx:04d}",
                "source_mode_name": mode,
                "shift_deg": shift,
                "shift_magnitude_deg": mag,
                "shift_sign": sign,
                "azimuth_overlap_bucket": bucket,
                "n_rows": len(group),
                "median_azimuth_overlap_ratio_vs_true": fmt(overlap, 4),
                "median_support_iou_proxy": fmt(median_clean(row.get("_overlap_support_iou_proxy") for row in group), 4),
                "topk_contains_near_gt_rate_posthoc": fmt(rate_value, 4),
                "top1_near_gt_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("top1_near_gt_posthoc"))), len(group)),
                "gt_inside_support_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("gt_inside_support_posthoc"))), len(group)),
                "median_peak_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in group), 4),
                "median_support_area_px": fmt(median_clean(row.get("support_area_px") for row in group), 0),
                "scatter_cluster_type_mix": compact_counts(row.get("scatter_cluster_type", "") for row in group),
                "temporal_stability_label_mix": compact_counts(row.get("temporal_stability_label", "") for row in group),
                "interpretation": interpretation,
                "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return result


def build_general_triage_rows(
    rows: Sequence[Mapping[str, Any]],
    wrong_object_rows: Sequence[Mapping[str, Any]],
    wrong_frame_rows: Sequence[Mapping[str, Any]],
    azimuth_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    true_mode_rates = {
        mode: topk_rate(group)
        for mode, group in groupby_key(
            [row for row in rows if row.get("control_support_type") == "true_support"],
            lambda row: str(row.get("source_mode_name", "")),
        ).items()
    }
    true_state_rates = true_rate_by_mode_state(rows)
    result: list[dict[str, Any]] = []
    idx = 0

    def append_group(
        triage_line: str,
        source_mode: str,
        bucket: str,
        state: str,
        control_type: str,
        variant_group: str,
        group: Sequence[Mapping[str, Any]],
        reference: float | None,
        overlap_values: Sequence[Any] = (),
        intersection_values: Sequence[Any] = (),
        interpretation: str = "",
        provenance: str = "SAR_GT_posthoc_evidence;hypothesis_to_validate",
    ) -> None:
        nonlocal idx
        idx += 1
        common = aggregate_common(group, reference)
        result.append(
            {
                "triage_id": f"TR{idx:04d}",
                "triage_line": triage_line,
                "source_mode_name": source_mode,
                "bucket": bucket,
                "state_condition": state,
                "control_support_type": control_type,
                "control_variant_group": variant_group,
                **common,
                "median_support_overlap_iou_proxy": fmt(median_clean(overlap_values), 4),
                "median_support_intersection_ratio_vs_true": fmt(median_clean(intersection_values), 4),
                "interpretation": interpretation,
                "provenance_labels": provenance,
            }
        )

    wrong_object_groups = groupby_key(
        wrong_object_rows,
        lambda row: (str(row.get("source_mode_name", "")), str(row.get("overlap_bucket", ""))),
    )
    wrong_original_by_id = {
        (
            row.get("source_mode_name", ""),
            row.get("scene", ""),
            row.get("object_hypothesis_id", ""),
            row.get("optical_frame", ""),
            row.get("expected_sar_frame", ""),
            row.get("wrong_object_source_sar_frame", ""),
        ): row
        for row in wrong_object_rows
    }
    source_wrong_rows = [row for row in rows if row.get("control_support_type") == "wrong_object_support"]
    for (mode, bucket), overlap_group in sorted(wrong_object_groups.items()):
        source_group = [
            row
            for row in source_wrong_rows
            if row.get("source_mode_name") == mode
            and (
                mode,
                row.get("scene", ""),
                row.get("object_hypothesis_id", ""),
                row.get("optical_frame", ""),
                row.get("expected_sar_frame", ""),
                parse_control_reference(str(row.get("control_source_reference", ""))).get("source_sar_frame", ""),
            )
            in wrong_original_by_id
            and wrong_original_by_id[
                (
                    mode,
                    row.get("scene", ""),
                    row.get("object_hypothesis_id", ""),
                    row.get("optical_frame", ""),
                    row.get("expected_sar_frame", ""),
                    parse_control_reference(str(row.get("control_source_reference", ""))).get("source_sar_frame", ""),
                )
            ].get("overlap_bucket")
            == bucket
        ]
        rate_value = topk_rate(source_group)
        if bucket.startswith("high") or bucket.startswith("medium"):
            interpretation = "wrong-object high is mostly an object-confusion/support-overlap problem"
        elif rate_value is not None and rate_value >= 0.50:
            interpretation = "low-overlap wrong-object remains high; SAR/top-k evidence lacks object discrimination"
        else:
            interpretation = "wrong-object drops after support overlap decreases"
        append_group(
            "wrong_object_confounder",
            mode,
            bucket,
            "all_states",
            "wrong_object_support",
            "same_scene_other_object",
            source_group,
            true_mode_rates.get(mode),
            [row.get("support_iou_proxy") for row in overlap_group],
            [row.get("support_intersection_ratio_vs_true") for row in overlap_group],
            interpretation,
            "runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        )

    for row in wrong_frame_rows:
        # Recover matching source rows from original counterfactual CSV for aggregate columns.
        source_group = [
            item
            for item in rows
            if item.get("control_support_type") == "wrong_sar_frame_support"
            and item.get("source_mode_name") == row.get("source_mode_name")
            and frame_offset_bucket(
                (safe_int(item.get("observed_sar_frame")) or 0) - (safe_int(item.get("expected_sar_frame")) or 0)
            )
            == row.get("offset_bucket")
            and sign_bucket(
                (safe_int(item.get("observed_sar_frame")) or 0) - (safe_int(item.get("expected_sar_frame")) or 0)
            )
            == row.get("offset_sign")
        ]
        append_group(
            "wrong_frame_confounder",
            str(row.get("source_mode_name", "")),
            str(row.get("offset_bucket", "")),
            "all_states",
            "wrong_sar_frame_support",
            str(row.get("offset_sign", "")),
            source_group,
            true_mode_rates.get(str(row.get("source_mode_name", ""))),
            interpretation=str(row.get("interpretation", "")),
            provenance="runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        )

    true_by_key = {
        truth_key(row): row
        for row in rows
        if row.get("control_support_type") == "true_support"
    }

    def az_bucket_for_item(item: Mapping[str, Any]) -> str:
        true = true_by_key.get(truth_key(item))
        if not true:
            return "overlap_unknown"
        metrics = support_overlap_metrics(true, item)
        return overlap_bucket(safe_float(metrics.get("azimuth_overlap_ratio_vs_true")))

    for row in azimuth_rows:
        source_group = [
            item
            for item in rows
            if item.get("control_support_type") == "azimuth_shifted_support"
            and item.get("source_mode_name") == row.get("source_mode_name")
            and fmt(abs(parse_variant_value(str(item.get("control_variant", "")), "delta_deg") or 0.0), 1)
            == str(row.get("shift_magnitude_deg", ""))
            and shift_sign(parse_variant_value(str(item.get("control_variant", "")), "delta_deg")) == row.get("shift_sign")
            and az_bucket_for_item(item) == row.get("azimuth_overlap_bucket")
        ]
        append_group(
            "azimuth_shift_confounder",
            str(row.get("source_mode_name", "")),
            str(row.get("azimuth_overlap_bucket", "")),
            "all_states",
            "azimuth_shifted_support",
            f"{row.get('shift_sign')}:{row.get('shift_magnitude_deg')}deg",
            source_group,
            true_mode_rates.get(str(row.get("source_mode_name", ""))),
            [row.get("median_support_iou_proxy")],
            [row.get("median_azimuth_overlap_ratio_vs_true")],
            str(row.get("interpretation", "")),
            "runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        )

    range_groups = groupby_key(
        [row for row in rows if row.get("control_support_type") == "range_shifted_support"],
        lambda row: (
            str(row.get("source_mode_name", "")),
            str(row.get("state_condition", "")),
            "negative_shift" if "multiplier=-" in str(row.get("control_variant", "")) else "positive_shift",
        ),
    )
    for (mode, state, direction), group in sorted(range_groups.items()):
        reference = true_state_rates.get((mode, state), true_mode_rates.get(mode))
        current = topk_rate(group)
        interpretation = (
            "range shift strongly suppresses GT-near top-k; range/state is the strongest current discriminative axis"
            if reference is not None and current is not None and reference - current >= 0.50
            else "range shift does not fully suppress signal; inspect state or support width"
        )
        append_group(
            "range_shift_confounder",
            mode,
            direction,
            state,
            "range_shifted_support",
            direction,
            group,
            reference,
            interpretation=interpretation,
            provenance="runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        )
    return result


def get_comparison_rate(comparison_rows: Sequence[Mapping[str, Any]], mode: str, support_type: str) -> str:
    for row in comparison_rows:
        if (
            row.get("source_mode_name") == mode
            and row.get("control_support_type") == support_type
            and row.get("control_variant") == "ALL"
        ):
            return str(row.get("topk_contains_near_gt_rate_posthoc", ""))
    return ""


def build_summary(
    timestamp: str,
    triage_rows: Sequence[Mapping[str, Any]],
    wrong_object_rows: Sequence[Mapping[str, Any]],
    wrong_frame_rows: Sequence[Mapping[str, Any]],
    azimuth_rows: Sequence[Mapping[str, Any]],
    comparison_rows: Sequence[Mapping[str, Any]],
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    state_true = get_comparison_rate(comparison_rows, "state_conditioned_range_band", "true_support")
    state_random = get_comparison_rate(comparison_rows, "state_conditioned_range_band", "random_same_scene_support")
    state_range = get_comparison_rate(comparison_rows, "state_conditioned_range_band", "range_shifted_support")
    state_az = get_comparison_rate(comparison_rows, "state_conditioned_range_band", "azimuth_shifted_support")
    state_wrong_object = get_comparison_rate(comparison_rows, "state_conditioned_range_band", "wrong_object_support")
    state_wrong_frame = get_comparison_rate(comparison_rows, "state_conditioned_range_band", "wrong_sar_frame_support")
    broad_true = get_comparison_rate(comparison_rows, "broad_fan_baseline", "true_support")

    state_wrong_frame_rows = [row for row in wrong_frame_rows if row.get("source_mode_name") == "state_conditioned_range_band"]
    state_wrong_object_high = [
        row
        for row in wrong_object_rows
        if row.get("source_mode_name") == "state_conditioned_range_band"
        and row.get("overlap_bucket") in {"high_overlap_ge_0p75", "medium_overlap_0p25_0p75"}
    ]
    state_az_high = [
        row
        for row in azimuth_rows
        if row.get("source_mode_name") == "state_conditioned_range_band"
        and safe_float(row.get("topk_contains_near_gt_rate_posthoc")) is not None
        and (safe_float(row.get("topk_contains_near_gt_rate_posthoc")) or 0.0) >= 0.5
    ]
    answers = {
        "wrong_frame_confounder": (
            f"State-conditioned wrong-frame top-k near-GT remains {state_wrong_frame}. "
            f"Observed wrong-frame buckets are {compact_counts(row.get('offset_bucket', '') for row in state_wrong_frame_rows)}. "
            "Because high rates persist at the available wrong-frame offsets, the current SAR observation is not time-discriminative enough by itself; it needs temporal-change and object-motion gates."
        ),
        "wrong_object_confounder": (
            f"State-conditioned wrong-object top-k near-GT remains {state_wrong_object}. "
            f"Overlap mix is {compact_counts(row.get('overlap_bucket', '') for row in wrong_object_rows if row.get('source_mode_name') == 'state_conditioned_range_band')}. "
            f"{len(state_wrong_object_high)} state-conditioned wrong-object rows have medium/high support overlap, so object confusion/support overlap explains part of the high rate; low-overlap hits still need SAR structure or graph-level disambiguation."
        ),
        "azimuth_shift_confounder": (
            f"State-conditioned azimuth-shift top-k near-GT remains {state_az}. "
            f"High-rate azimuth-shift groups: {len(state_az_high)}. "
            "The shift controls indicate that azimuth alone is weak under current margins; overlap and sector width must be audited before using azimuth as a strong gate."
        ),
        "range_shift_confounder": (
            f"State-conditioned true top-k near-GT is {state_true}, while range-shift is {state_range} and random is {state_random}. "
            "This is the clearest discriminative signal, but it is still posthoc because current range bands inherit GT-validated state/shape hypotheses."
        ),
        "stage_handoff": (
            "The closeout should hand off to gate provenance, object-time confounding, SAR scatter-structure mechanism, GM_RM019 review, and GM_RM011 object-stream recovery. It should not continue local top-k/cluster metric tuning."
        ),
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "ledger_valid": True,
            "category_counts": EXPECTED_LEDGER,
            "note": "The triage preserves 215 paired, 195 GM_RM011 blocked missing object stream, 20 SAR-only, and 12 dropout/no-match continuation pool.",
        },
        "row_scope": (
            "This triage reuses the prior counterfactual support validation rows. It does not add new SAR image extraction and does not mix dropout/no-match, SAR-only, or GM_RM011 blocked rows into clean optical-SAR correspondence."
        ),
        "row_counts": {
            "counterfactual_confounder_triage": len(triage_rows),
            "wrong_object_overlap_triage": len(wrong_object_rows),
            "wrong_frame_offset_triage": len(wrong_frame_rows),
            "azimuth_shift_overlap_triage": len(azimuth_rows),
        },
        "key_metrics": {
            "broad_true_topk_contains_near_gt_rate_posthoc": broad_true,
            "state_conditioned_true_topk_contains_near_gt_rate_posthoc": state_true,
            "state_conditioned_random_topk_contains_near_gt_rate_posthoc": state_random,
            "state_conditioned_range_shifted_topk_contains_near_gt_rate_posthoc": state_range,
            "state_conditioned_azimuth_shifted_topk_contains_near_gt_rate_posthoc": state_az,
            "state_conditioned_wrong_object_topk_contains_near_gt_rate_posthoc": state_wrong_object,
            "state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc": state_wrong_frame,
        },
        "question_answers": answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 Counterfactual Confounder Triage Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report closes the current OTY2 session with a small confounder triage. It reuses existing counterfactual outputs and does not open a new experiment.",
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
    lines.extend(["", "## Confounder Answers", ""])
    for key in [
        "wrong_frame_confounder",
        "wrong_object_confounder",
        "azimuth_shift_confounder",
        "range_shift_confounder",
        "stage_handoff",
    ]:
        lines.append(f"- {key}: {summary['question_answers'][key]}")
    lines.extend(
        [
            "",
            "## Provenance Boundary",
            "",
            "All GT-near, GT-inside, and residual-style conclusions are `SAR_GT_posthoc_evidence` and `hypothesis_to_validate`. Runtime-safe potential is limited to optical object stream, timing ratio, fan geometry, state labels, and vehicle physical assumptions.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
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


def render_handoff_doc(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 Counterfactual Confounder Triage And Handoff",
        "",
        "Updated: 2026-07-03",
        "",
        "This document closes the current OTY2 counterfactual/confounder triage stage. It is not an experiment proposal, not OTY3, not a final automatic annotation plan, not selector/ranking, and not training or threshold tuning.",
        "",
        "## What This Stage Completed",
        "",
        "- Established the 442 GT ledger and kept the pools separated.",
        "- Built optical-to-SAR support-region observation probes.",
        "- Audited range narrowing and peak competition.",
        "- Reframed SAR evidence from top1 peak to scatter cluster plus temporal persistence.",
        "- Ran counterfactual / negative-control support validation.",
        "- Triage-tested why wrong-object, wrong-frame, and azimuth-shift controls remain high.",
        "",
        "## More Reliable Conclusions",
        "",
        f"- Broad support is a coverage baseline, not localization: broad true top-k near-GT is `{summary['key_metrics']['broad_true_topk_contains_near_gt_rate_posthoc']}`.",
        f"- Range/state constraints carry the clearest posthoc signal: state-conditioned true is `{summary['key_metrics']['state_conditioned_true_topk_contains_near_gt_rate_posthoc']}`, random is `{summary['key_metrics']['state_conditioned_random_topk_contains_near_gt_rate_posthoc']}`, and range-shift is `{summary['key_metrics']['state_conditioned_range_shifted_topk_contains_near_gt_rate_posthoc']}`.",
        "- SAR vehicles should be treated as extended scatter structures and temporal tubes, not single brightest points.",
        "- Wrong-object and wrong-frame controls show that association is still unresolved.",
        "",
        "## Posthoc Observations Only",
        "",
        "- `topk_contains_near_gt_posthoc` is a validation metric, not runtime capability.",
        "- State-conditioned range success is posthoc and must not be written as a runtime rule.",
        "- Object-smoothed range trends, scene residuals, and shape-radius relations are hypotheses to validate.",
        "- SAR GT and GT-near peak distances are posthoc evidence only.",
        "",
        "## Directions Downgraded Or Rejected",
        "",
        "- Top1 peak as target center is rejected.",
        "- Top-k/cluster metric tuning alone is downgraded; it risks becoming local metric engineering.",
        "- `associated_posthoc_strong` count is not a valid objective.",
        "- Timing-only or wrong-frame-tolerant association is not enough to claim identity.",
        "- Broad fan peak/background is not enough to localize a vehicle.",
        "",
        "## Current Biggest Blockers",
        "",
        f"- Wrong-frame remains high: `{summary['key_metrics']['state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc']}`.",
        f"- Wrong-object remains high: `{summary['key_metrics']['state_conditioned_wrong_object_topk_contains_near_gt_rate_posthoc']}`.",
        f"- Azimuth-shift remains high: `{summary['key_metrics']['state_conditioned_azimuth_shifted_topk_contains_near_gt_rate_posthoc']}`.",
        "- GM_RM011 still lacks the current OTY optical object stream; it is not unannotated.",
        "- GM_RM019 still benefits from limited manual optical GT / object-hypothesis review.",
        "",
        "## What The Next Stage Should Not Do",
        "",
        "- Do not generate final annotation proposals.",
        "- Do not output selector/ranking.",
        "- Do not train or tune thresholds.",
        "- Do not claim identity truth.",
        "- Do not write GT peak / GT residual into runtime prior.",
        "- Do not write state-conditioned top-k success as a runtime rule.",
        "- Do not mix dropout/no-match into clean morphology.",
        "- Do not mix SAR-only into optical-SAR correspondence.",
        "- Do not treat the GM_RM011 195 blocked rows as unannotated.",
        "- Do not commit `MatlabToolboxZB.zip` or any zip.",
        "",
        "## What The Next Stage Should Do",
        "",
        "1. Gate provenance: separate runtime-safe optical/time/geometry/state gates from SAR observation and posthoc validation.",
        "2. Object-time confounding: explain wrong-object and wrong-frame high cases before any association claim.",
        "3. SAR scatter-structure mechanism: inspect compact, multi-peak, range-spread, azimuth-spread, diffuse, sidelobe-like, jumping, and stable tube structures.",
        "4. Optical information bottleneck: derive which cues are runtime-safe and which are still posthoc.",
        "5. GM_RM019 review: confirm object hypotheses, trajectory direction, and complete morphology frames.",
        "6. GM_RM011 recovery: build the current OTY optical object stream before optical-SAR correspondence modeling.",
        "",
        "## Why A New Session Should Take Over",
        "",
        "This session has accumulated a long chain of reports and generated diagnostics. A new GPT/Codex session should start from this handoff and the committed reports so it can reason from a compact state, avoid repeating local top-k/cluster tuning, and focus on object-time confounding and gate provenance.",
        "",
        "## Ledger To Preserve",
        "",
        "```text",
        "paired_optical_object_sar_gt = 215",
        "blocked_missing_gm011_object_stream = 195",
        "sar_only_gt = 20",
        "dropout/no_oty_iou_match/temporal continuation pool = 12",
        "```",
        "",
        "## Provenance Labels",
        "",
        "Use: `runtime_safe_optical_evidence`, `runtime_safe_temporal_evidence`, `runtime_safe_geometry_or_vehicle_physics`, `SAR_image_observation`, `SAR_temporal_observation`, `SAR_GT_posthoc_evidence`, `manual_or_review_anchor`, `hypothesis_to_validate`, and `insufficient_or_not_supported`.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_counterfactual_confounder_triage_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_counterfactual_confounder_triage",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        "new_sar_image_extraction=false",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "counterfactual_csv": Path(args.counterfactual_csv) if args.counterfactual_csv else latest_path("oty2_counterfactual_support_validation_*.csv"),
        "negative_control_comparison_csv": Path(args.negative_control_comparison_csv) if args.negative_control_comparison_csv else latest_path("oty2_negative_control_support_comparison_*.csv"),
        "parallel_summary_json": Path(args.parallel_summary_json) if args.parallel_summary_json else latest_path("oty2_parallel_mechanism_exploration_summary_*.json"),
    }
    parallel_summary = json.loads(paths["parallel_summary_json"].read_text(encoding="utf-8"))
    ledger = parallel_summary.get("sample_ledger", {}).get("category_counts", {})
    if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
        raise RuntimeError(f"Ledger changed; refusing confounder triage: {json.dumps(ledger, ensure_ascii=False)}")
    counterfactual_rows = read_csv(paths["counterfactual_csv"])
    if any(row.get("sample_pool") != "paired_optical_object_sar_gt" for row in counterfactual_rows):
        raise RuntimeError("Counterfactual input contains non-paired rows; refusing to mix sample pools.")
    return {
        "paths": paths,
        "parallel_summary": parallel_summary,
        "counterfactual_rows": counterfactual_rows,
        "comparison_rows": read_csv(paths["negative_control_comparison_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    rows = inputs["counterfactual_rows"]
    comparison_rows = inputs["comparison_rows"]
    wrong_object_rows = build_wrong_object_rows(rows)
    wrong_frame_rows = build_wrong_frame_rows(rows)
    azimuth_rows = build_azimuth_rows(rows)
    triage_rows = build_general_triage_rows(rows, wrong_object_rows, wrong_frame_rows, azimuth_rows)

    handoff_doc = DOCS_DIR / "oty2_counterfactual_confounder_triage_and_handoff.md"
    triage_csv = REPORT_DIR / f"oty2_counterfactual_confounder_triage_{timestamp}.csv"
    wrong_object_csv = REPORT_DIR / f"oty2_wrong_object_overlap_triage_{timestamp}.csv"
    wrong_frame_csv = REPORT_DIR / f"oty2_wrong_frame_offset_triage_{timestamp}.csv"
    azimuth_csv = REPORT_DIR / f"oty2_azimuth_shift_overlap_triage_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_counterfactual_confounder_triage_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_counterfactual_confounder_triage_summary_{timestamp}.json"

    outputs = {
        "handoff_doc": str(handoff_doc),
        "counterfactual_confounder_triage_csv": str(triage_csv),
        "wrong_object_overlap_triage_csv": str(wrong_object_csv),
        "wrong_frame_offset_triage_csv": str(wrong_frame_csv),
        "azimuth_shift_overlap_triage_csv": str(azimuth_csv),
        "counterfactual_confounder_triage_report_md": str(report_md),
        "counterfactual_confounder_triage_summary_json": str(summary_json),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}
    summary = build_summary(timestamp, triage_rows, wrong_object_rows, wrong_frame_rows, azimuth_rows, comparison_rows, sources, outputs)
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    write_csv(triage_csv, triage_rows, TRIAGE_FIELDS)
    write_csv(wrong_object_csv, wrong_object_rows, WRONG_OBJECT_FIELDS)
    write_csv(wrong_frame_csv, wrong_frame_rows, WRONG_FRAME_FIELDS)
    write_csv(azimuth_csv, azimuth_rows, AZIMUTH_FIELDS)
    render_report(report_md, summary)
    render_handoff_doc(handoff_doc, summary)
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
    parser.add_argument("--counterfactual-csv", default="")
    parser.add_argument("--negative-control-comparison-csv", default="")
    parser.add_argument("--parallel-summary-json", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
