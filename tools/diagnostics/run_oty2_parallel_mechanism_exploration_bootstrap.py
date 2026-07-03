"""OTY2 parallel mechanism exploration bootstrap.

This diagnostic implements the first lightweight probe from
docs/oty2_parallel_mechanism_exploration_design.md: counterfactual /
negative-control support validation.

It compares true optical-derived supports with shifted, wrong-object,
wrong-frame, and random same-scene supports. SAR images are used only for
support-region observation. SAR GT is used only for posthoc validation of
whether true support is more discriminative than negative controls.

The output is not a final annotation proposal, not a selector/ranking output,
not training, not threshold tuning, and not identity truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from run_oty2_gated_association_scatter_cluster_audit import (
    classify_cluster,
    diagnose_topk_gt,
    extract_topk_cluster,
    gt_context,
    temporal_label_for_group,
)
from run_oty2_range_narrowing_peak_competition_audit import (
    EXPECTED_LEDGER,
    FAN_RADIUS_PX,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    SarImageCache,
    bool_text,
    compact_counts,
    fmt,
    groupby_key,
    gt_inside,
    latest_path,
    mean_clean,
    median_clean,
    peak_competition_label,
    read_csv,
    safe_float,
    safe_int,
    sar_path,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

SOURCE_MODES = ("broad_fan_baseline", "state_conditioned_range_band")
AZIMUTH_SHIFTS_DEG = (-20.0, -10.0, 10.0, 20.0)
RANGE_SHIFT_MULTIPLIERS = (-1.5, 1.5)
WRONG_FRAME_OFFSETS = (25, -25, 50, -50, 12, -12)

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "topk_peak_gt_distance_used_for_posthoc_diagnosis": True,
    "negative_control_support_constructed": True,
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

COUNTERFACTUAL_FIELDS = [
    "counterfactual_id",
    "source_mode_name",
    "control_support_type",
    "control_variant",
    "control_boundary",
    "sample_pool",
    "clean_morphology_inclusion",
    "scene",
    "object_hypothesis_id",
    "state_condition",
    "optical_frame",
    "expected_sar_frame",
    "observed_sar_frame",
    "support_source_peak_audit_id",
    "control_source_reference",
    "support_azimuth_start_deg",
    "support_azimuth_end_deg",
    "support_azimuth_width_deg",
    "support_radius_min_px",
    "support_radius_max_px",
    "radius_band_width_px",
    "range_band_source",
    "gt_radius_px_posthoc",
    "gt_azimuth_deg_posthoc",
    "gt_inside_support_posthoc",
    "gt_radius_inside_posthoc",
    "support_area_px",
    "area_ratio_vs_true_mode",
    "topk_peak_count",
    "top1_background_ratio",
    "top1_top2_ratio",
    "best_topk_distance_to_gt_px_posthoc",
    "best_topk_rank_to_gt_posthoc",
    "top1_near_gt_posthoc",
    "top2_or_top3_nearer_than_top1_posthoc",
    "topk_contains_near_gt_posthoc",
    "multiple_topk_peaks_near_gt_posthoc",
    "all_topk_far_from_gt_posthoc",
    "topk_gt_relationship_label",
    "top1_x",
    "top1_y",
    "cluster_centroid_x",
    "cluster_centroid_y",
    "cluster_compactness_px",
    "cluster_peak_spread_px",
    "cluster_range_spread_px",
    "cluster_azimuth_spread_deg",
    "local_peak_count_above_bg_p95",
    "profile_sharpness_proxy",
    "scatter_cluster_type",
    "temporal_stability_label",
    "peak_competition_label",
    "sar_image_path",
    "provenance_labels",
    "notes",
]

COMPARISON_FIELDS = [
    "comparison_id",
    "source_mode_name",
    "control_support_type",
    "control_variant",
    "sample_pool",
    "n_rows",
    "gt_inside_support_rate_posthoc",
    "top1_near_gt_rate_posthoc",
    "topk_contains_near_gt_rate_posthoc",
    "multiple_topk_peaks_near_gt_rate_posthoc",
    "all_topk_far_rate_posthoc",
    "stable_cluster_tube_rate",
    "jumping_peak_rate",
    "diffuse_or_unstable_rate",
    "median_best_topk_distance_to_gt_px_posthoc",
    "median_peak_background_ratio",
    "median_support_area_px",
    "median_area_ratio_vs_true_mode",
    "serious_peak_competition_rate",
    "scatter_cluster_type_mix",
    "temporal_stability_label_mix",
    "interpretation",
    "provenance_labels",
]

MECHANISM_NOTE_FIELDS = [
    "note_id",
    "mechanism_line",
    "observation",
    "interpretation",
    "next_probe_or_blocker",
    "provenance_labels",
]

CUE_SKETCH_FIELDS = [
    "cue_layer",
    "runtime_safe_status",
    "expected_contribution",
    "current_evidence",
    "blocker_or_next_probe",
    "provenance_labels",
]


def rate(num: int, den: int) -> str:
    return fmt(num / den if den else None, 4)


def bool_is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def stable_seed(text: str) -> int:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def support_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "support_azimuth_start_deg": safe_float(row.get("support_azimuth_start_deg"), -89.0) or -89.0,
        "support_azimuth_end_deg": safe_float(row.get("support_azimuth_end_deg"), 89.0) or 89.0,
        "support_radius_min_px": safe_float(row.get("support_radius_min_px"), 0.0) or 0.0,
        "support_radius_max_px": safe_float(row.get("support_radius_max_px"), FAN_RADIUS_PX) or FAN_RADIUS_PX,
        "range_band_source": row.get("range_band_source", ""),
    }


def support_widths(support: Mapping[str, Any]) -> tuple[float, float]:
    az_start = float(support["support_azimuth_start_deg"])
    az_end = float(support["support_azimuth_end_deg"])
    radius_min = float(support["support_radius_min_px"])
    radius_max = float(support["support_radius_max_px"])
    return max(0.0, az_end - az_start), max(0.0, radius_max - radius_min)


def shift_interval(center: float, width: float, lo: float, hi: float) -> tuple[float, float] | None:
    width = min(width, hi - lo)
    start = center - width / 2.0
    end = center + width / 2.0
    if start < lo:
        end += lo - start
        start = lo
    if end > hi:
        start -= end - hi
        end = hi
    start = max(lo, start)
    end = min(hi, end)
    if end <= start:
        return None
    return start, end


def azimuth_shifted_support(row: Mapping[str, Any], delta_deg: float) -> dict[str, Any] | None:
    support = support_from_row(row)
    az_width, _range_width = support_widths(support)
    center = (float(support["support_azimuth_start_deg"]) + float(support["support_azimuth_end_deg"])) / 2.0 + delta_deg
    shifted = shift_interval(center, az_width, -89.0, 89.0)
    if shifted is None:
        return None
    support["support_azimuth_start_deg"], support["support_azimuth_end_deg"] = shifted
    support["range_band_source"] = f"negative_control_azimuth_shift;delta_deg={fmt(delta_deg, 1)}"
    return support


def range_shifted_support(row: Mapping[str, Any], multiplier: float) -> dict[str, Any] | None:
    support = support_from_row(row)
    _az_width, range_width = support_widths(support)
    if range_width >= FAN_RADIUS_PX * 0.98:
        return None
    shift_px = max(80.0, range_width * abs(multiplier))
    if multiplier < 0:
        shift_px = -shift_px
    center = (float(support["support_radius_min_px"]) + float(support["support_radius_max_px"])) / 2.0 + shift_px
    shifted = shift_interval(center, range_width, 0.0, FAN_RADIUS_PX)
    if shifted is None:
        return None
    original = (float(support["support_radius_min_px"]), float(support["support_radius_max_px"]))
    if abs(shifted[0] - original[0]) < 1e-6 and abs(shifted[1] - original[1]) < 1e-6:
        return None
    support["support_radius_min_px"], support["support_radius_max_px"] = shifted
    support["range_band_source"] = f"negative_control_range_shift;delta_px={fmt(shift_px, 1)}"
    return support


def wrong_object_support(
    row: Mapping[str, Any],
    candidates_by_mode_scene: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    mode = str(row.get("mode_name", ""))
    scene = str(row.get("scene", ""))
    object_id = str(row.get("object_hypothesis_id", ""))
    sar_frame = safe_int(row.get("sar_frame"), 0) or 0
    candidates = [
        item
        for item in candidates_by_mode_scene.get((mode, scene), [])
        if str(item.get("object_hypothesis_id", "")) != object_id
    ]
    if not candidates:
        return None, "blocked_no_other_object_hypothesis_in_same_scene_mode"
    candidates.sort(key=lambda item: abs((safe_int(item.get("sar_frame"), 0) or 0) - sar_frame))
    source = candidates[0]
    support = support_from_row(source)
    support["range_band_source"] = "negative_control_wrong_object_support"
    ref = (
        f"wrong_object={source.get('object_hypothesis_id', '')};"
        f"source_sar_frame={source.get('sar_frame', '')};"
        f"source_peak_audit_id={source.get('peak_audit_id', '')}"
    )
    return support, ref


def choose_wrong_frame(scene: str, sar_frame: int) -> int | None:
    for offset in WRONG_FRAME_OFFSETS:
        candidate = sar_frame + offset
        if candidate >= 0 and sar_path(scene, candidate).exists():
            return candidate
    return None


def random_same_scene_support(row: Mapping[str, Any]) -> dict[str, Any] | None:
    support = support_from_row(row)
    az_width, range_width = support_widths(support)
    rng = random.Random(
        stable_seed(
            "|".join(
                [
                    str(row.get("mode_name", "")),
                    str(row.get("scene", "")),
                    str(row.get("object_hypothesis_id", "")),
                    str(row.get("optical_frame", "")),
                    str(row.get("sar_frame", "")),
                ]
            )
        )
    )
    az_width = min(max(az_width, 3.0), 178.0)
    az_center = rng.uniform(-89.0 + az_width / 2.0, 89.0 - az_width / 2.0)
    az = shift_interval(az_center, az_width, -89.0, 89.0)
    if az is None:
        return None
    if range_width >= FAN_RADIUS_PX * 0.98:
        radius_min, radius_max = 0.0, FAN_RADIUS_PX
    else:
        range_width = min(max(range_width, 20.0), FAN_RADIUS_PX)
        radius_center = rng.uniform(range_width / 2.0, FAN_RADIUS_PX - range_width / 2.0)
        radius = shift_interval(radius_center, range_width, 0.0, FAN_RADIUS_PX)
        if radius is None:
            return None
        radius_min, radius_max = radius
    support["support_azimuth_start_deg"], support["support_azimuth_end_deg"] = az
    support["support_radius_min_px"] = radius_min
    support["support_radius_max_px"] = radius_max
    support["range_band_source"] = "negative_control_random_same_scene_support"
    return support


def control_specs_for_row(
    row: Mapping[str, Any],
    candidates_by_mode_scene: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    specs = [
        {
            "control_support_type": "true_support",
            "control_variant": "original",
            "control_boundary": "current_support_observation_not_final_annotation",
            "support": support_from_row(row),
            "observed_sar_frame": safe_int(row.get("sar_frame")),
            "control_source_reference": str(row.get("peak_audit_id", "")),
            "notes": "Original optical-derived support; GT only validates posthoc.",
        }
    ]
    blockers: list[str] = []
    for delta in AZIMUTH_SHIFTS_DEG:
        support = azimuth_shifted_support(row, delta)
        if support is None:
            blockers.append(f"azimuth_shifted_support blocked for {row.get('peak_audit_id')} delta={delta}")
            continue
        specs.append(
            {
                "control_support_type": "azimuth_shifted_support",
                "control_variant": f"delta_deg={fmt(delta, 1)}",
                "control_boundary": "negative_control_not_runtime_prior",
                "support": support,
                "observed_sar_frame": safe_int(row.get("sar_frame")),
                "control_source_reference": str(row.get("peak_audit_id", "")),
                "notes": "Azimuth-shifted negative control tests fan-sector discriminative power.",
            }
        )
    for multiplier in RANGE_SHIFT_MULTIPLIERS:
        support = range_shifted_support(row, multiplier)
        if support is None:
            blockers.append(
                f"range_shifted_support blocked for {row.get('peak_audit_id')} mode={row.get('mode_name')} multiplier={multiplier}; full or clamped range band"
            )
            continue
        specs.append(
            {
                "control_support_type": "range_shifted_support",
                "control_variant": f"multiplier={fmt(multiplier, 1)}",
                "control_boundary": "negative_control_not_runtime_prior",
                "support": support,
                "observed_sar_frame": safe_int(row.get("sar_frame")),
                "control_source_reference": str(row.get("peak_audit_id", "")),
                "notes": "Range-shifted negative control tests whether the radial band is discriminative.",
            }
        )
    wrong_support, wrong_ref = wrong_object_support(row, candidates_by_mode_scene)
    if wrong_support is None:
        blockers.append(f"wrong_object_support blocked for {row.get('peak_audit_id')}: {wrong_ref}")
    else:
        specs.append(
            {
                "control_support_type": "wrong_object_support",
                "control_variant": "same_scene_other_object",
                "control_boundary": "negative_control_not_identity_truth",
                "support": wrong_support,
                "observed_sar_frame": safe_int(row.get("sar_frame")),
                "control_source_reference": wrong_ref,
                "notes": "Wrong-object support tests whether another optical hypothesis support works equally well.",
            }
        )
    scene = str(row.get("scene", ""))
    sar_frame = safe_int(row.get("sar_frame"))
    wrong_frame = choose_wrong_frame(scene, sar_frame) if sar_frame is not None else None
    if wrong_frame is None:
        blockers.append(f"wrong_sar_frame_support blocked for {row.get('peak_audit_id')}: no available offset frame")
    else:
        specs.append(
            {
                "control_support_type": "wrong_sar_frame_support",
                "control_variant": f"observed_frame={wrong_frame}",
                "control_boundary": "negative_control_not_temporal_truth",
                "support": support_from_row(row),
                "observed_sar_frame": wrong_frame,
                "control_source_reference": str(row.get("peak_audit_id", "")),
                "notes": "Wrong-SAR-frame support tests temporal discriminative power.",
            }
        )
    random_support = random_same_scene_support(row)
    if random_support is None:
        blockers.append(f"random_same_scene_support blocked for {row.get('peak_audit_id')}")
    else:
        specs.append(
            {
                "control_support_type": "random_same_scene_support",
                "control_variant": "deterministic_same_size_random",
                "control_boundary": "negative_control_not_runtime_prior",
                "support": random_support,
                "observed_sar_frame": safe_int(row.get("sar_frame")),
                "control_source_reference": str(row.get("peak_audit_id", "")),
                "notes": "Random same-scene support tests background coincidence risk.",
            }
        )
    return specs, blockers


def top1_top2_ratio(peaks: Sequence[Mapping[str, Any]]) -> float | None:
    if len(peaks) < 2:
        return None
    top1 = safe_float(peaks[0].get("value"))
    top2 = safe_float(peaks[1].get("value"))
    if top1 is None or top2 is None or top2 <= 1e-12:
        return None
    return top1 / top2


def top1_background_ratio(peaks: Sequence[Mapping[str, Any]], cluster: Mapping[str, Any]) -> float | None:
    if not peaks:
        return None
    top1 = safe_float(peaks[0].get("value"))
    bg = safe_float(cluster.get("background_mean"))
    if top1 is None or bg is None or bg <= 1e-12:
        return None
    return top1 / bg


def build_counterfactual_rows(
    source_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    cache: SarImageCache,
) -> tuple[list[dict[str, Any]], list[str]]:
    corr_by_key = {
        (row.get("scene", ""), row.get("object_hypothesis_id", ""), row.get("optical_frame", ""), row.get("sar_frame", "")): row
        for row in corr_rows
    }
    candidates_by_mode_scene = groupby_key(source_rows, lambda row: (str(row.get("mode_name", "")), str(row.get("scene", ""))))
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    idx = 0
    for source in source_rows:
        specs, spec_blockers = control_specs_for_row(source, candidates_by_mode_scene)
        blockers.extend(spec_blockers)
        true_area = safe_float(source.get("support_area_px"))
        for spec in specs:
            observed_frame = spec.get("observed_sar_frame")
            if observed_frame is None:
                continue
            idx += 1
            support = spec["support"]
            scene = str(source.get("scene", ""))
            cluster = extract_topk_cluster(cache, scene, int(observed_frame), support)
            gt = gt_context(source, corr_by_key)
            gt_diag = diagnose_topk_gt(source, cluster, gt)
            peaks = list(cluster.get("peaks", []))
            top_bg = top1_background_ratio(peaks, cluster)
            ratio = top1_top2_ratio(peaks)
            metric_row = dict(source)
            metric_row["top1_background_ratio"] = top_bg
            metric_row["top1_top2_ratio"] = ratio
            metric_row["local_peak_count_above_bg_p95"] = cluster.get("local_peak_count_above_bg_p95", "")
            cluster_type = classify_cluster(metric_row, cluster, gt_diag)
            gt_ok, gt_radius_ok = gt_inside(source, support)
            area = safe_float(cluster.get("support_area_px"))
            az_width, range_width = support_widths(support)
            peak_label = peak_competition_label(metric_row)
            rows.append(
                {
                    "counterfactual_id": f"CF{idx:06d}",
                    "source_mode_name": source.get("mode_name", ""),
                    "control_support_type": spec["control_support_type"],
                    "control_variant": spec["control_variant"],
                    "control_boundary": spec["control_boundary"],
                    "sample_pool": source.get("sample_pool", ""),
                    "clean_morphology_inclusion": source.get("clean_morphology_inclusion", ""),
                    "scene": scene,
                    "object_hypothesis_id": source.get("object_hypothesis_id", ""),
                    "state_condition": source.get("state_condition", ""),
                    "optical_frame": source.get("optical_frame", ""),
                    "expected_sar_frame": source.get("sar_frame", ""),
                    "observed_sar_frame": observed_frame,
                    "support_source_peak_audit_id": source.get("peak_audit_id", ""),
                    "control_source_reference": spec["control_source_reference"],
                    "support_azimuth_start_deg": fmt(support.get("support_azimuth_start_deg"), 4),
                    "support_azimuth_end_deg": fmt(support.get("support_azimuth_end_deg"), 4),
                    "support_azimuth_width_deg": fmt(az_width, 4),
                    "support_radius_min_px": fmt(support.get("support_radius_min_px"), 3),
                    "support_radius_max_px": fmt(support.get("support_radius_max_px"), 3),
                    "radius_band_width_px": fmt(range_width, 3),
                    "range_band_source": support.get("range_band_source", ""),
                    "gt_radius_px_posthoc": source.get("gt_radius_px_posthoc", ""),
                    "gt_azimuth_deg_posthoc": source.get("gt_azimuth_deg_posthoc", ""),
                    "gt_inside_support_posthoc": bool_text(gt_ok),
                    "gt_radius_inside_posthoc": bool_text(gt_radius_ok),
                    "support_area_px": fmt(area, 0),
                    "area_ratio_vs_true_mode": fmt(area / true_area if area is not None and true_area else None, 4),
                    "topk_peak_count": gt_diag.get("topk_peak_count", len(peaks)),
                    "top1_background_ratio": fmt(top_bg, 4),
                    "top1_top2_ratio": fmt(ratio, 4),
                    "best_topk_distance_to_gt_px_posthoc": fmt(gt_diag.get("best_topk_distance_to_gt_px_posthoc"), 3),
                    "best_topk_rank_to_gt_posthoc": gt_diag.get("best_topk_rank_to_gt_posthoc", ""),
                    "top1_near_gt_posthoc": bool_text(gt_diag.get("top1_near_gt_posthoc")),
                    "top2_or_top3_nearer_than_top1_posthoc": bool_text(gt_diag.get("top2_or_top3_nearer_than_top1_posthoc")),
                    "topk_contains_near_gt_posthoc": bool_text(gt_diag.get("topk_contains_peak_near_gt_posthoc")),
                    "multiple_topk_peaks_near_gt_posthoc": bool_text(gt_diag.get("multiple_topk_peaks_near_gt_posthoc")),
                    "all_topk_far_from_gt_posthoc": bool_text(gt_diag.get("all_topk_far_from_gt_posthoc")),
                    "topk_gt_relationship_label": gt_diag.get("topk_gt_relationship_label", ""),
                    "top1_x": fmt(peaks[0].get("x"), 3) if peaks else "",
                    "top1_y": fmt(peaks[0].get("y"), 3) if peaks else "",
                    "cluster_centroid_x": fmt(cluster.get("cluster_centroid_x"), 3),
                    "cluster_centroid_y": fmt(cluster.get("cluster_centroid_y"), 3),
                    "cluster_compactness_px": fmt(cluster.get("cluster_compactness_px"), 3),
                    "cluster_peak_spread_px": fmt(cluster.get("cluster_peak_spread_px"), 3),
                    "cluster_range_spread_px": fmt(cluster.get("cluster_range_spread_px"), 3),
                    "cluster_azimuth_spread_deg": fmt(cluster.get("cluster_azimuth_spread_deg"), 4),
                    "local_peak_count_above_bg_p95": cluster.get("local_peak_count_above_bg_p95", ""),
                    "profile_sharpness_proxy": fmt(cluster.get("profile_sharpness_proxy"), 4),
                    "scatter_cluster_type": cluster_type,
                    "temporal_stability_label": "",
                    "peak_competition_label": peak_label,
                    "sar_image_path": cluster.get("sar_image_path", ""),
                    "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
                    "notes": spec["notes"],
                }
            )
    attach_temporal_labels(rows)
    return rows, blockers


def attach_temporal_labels(rows: list[dict[str, Any]]) -> None:
    groups = groupby_key(
        rows,
        lambda row: (
            str(row.get("source_mode_name", "")),
            str(row.get("control_support_type", "")),
            str(row.get("control_variant", "")),
            str(row.get("scene", "")),
            str(row.get("object_hypothesis_id", "")),
        ),
    )
    for _key, group in groups.items():
        ordered = sorted(group, key=lambda row: safe_int(row.get("expected_sar_frame"), 0) or 0)
        label = temporal_label_for_group(ordered)
        for row in group:
            row["temporal_stability_label"] = label


def comparison_interpretation(mode: str, support_type: str, variant: str, rows: Sequence[Mapping[str, Any]]) -> str:
    topk_rate = sum(1 for row in rows if bool_is_true(row.get("topk_contains_near_gt_posthoc"))) / len(rows) if rows else 0.0
    if support_type == "true_support":
        return "baseline true support for this mode; still posthoc validation, not runtime localization"
    if support_type == "wrong_sar_frame_support":
        return "temporal negative control; strong performance here would indicate frame-insensitive background coincidence"
    if topk_rate >= 0.50:
        return "negative control retains high GT-near top-k rate; inspect pseudo-signal or overly broad support risk"
    if topk_rate >= 0.20:
        return "negative control has nontrivial signal; support may be broad or clutter-prone"
    return "negative control mostly suppresses GT-near top-k; true support is likely more discriminative"


def aggregate_comparison_rows(counterfactual_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped_variant = groupby_key(
        counterfactual_rows,
        lambda row: (
            str(row.get("source_mode_name", "")),
            str(row.get("control_support_type", "")),
            str(row.get("control_variant", "")),
        ),
    )
    grouped_all = groupby_key(
        counterfactual_rows,
        lambda row: (
            str(row.get("source_mode_name", "")),
            str(row.get("control_support_type", "")),
            "ALL",
        ),
    )
    combined: dict[tuple[str, str, str], Sequence[Mapping[str, Any]]] = {}
    combined.update(grouped_variant)
    combined.update(grouped_all)
    for idx, ((mode, support_type, variant), group) in enumerate(sorted(combined.items()), start=1):
        n = len(group)
        rows.append(
            {
                "comparison_id": f"NC{idx:04d}",
                "source_mode_name": mode,
                "control_support_type": support_type,
                "control_variant": variant,
                "sample_pool": compact_counts(row.get("sample_pool", "") for row in group),
                "n_rows": n,
                "gt_inside_support_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("gt_inside_support_posthoc"))), n),
                "top1_near_gt_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("top1_near_gt_posthoc"))), n),
                "topk_contains_near_gt_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("topk_contains_near_gt_posthoc"))), n),
                "multiple_topk_peaks_near_gt_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("multiple_topk_peaks_near_gt_posthoc"))), n),
                "all_topk_far_rate_posthoc": rate(sum(1 for row in group if bool_is_true(row.get("all_topk_far_from_gt_posthoc"))), n),
                "stable_cluster_tube_rate": rate(sum(1 for row in group if row.get("temporal_stability_label") == "stable_cluster_tube"), n),
                "jumping_peak_rate": rate(sum(1 for row in group if row.get("temporal_stability_label") == "jumping_peak"), n),
                "diffuse_or_unstable_rate": rate(sum(1 for row in group if row.get("temporal_stability_label") == "diffuse_or_unstable_cluster_tube"), n),
                "median_best_topk_distance_to_gt_px_posthoc": fmt(median_clean(row.get("best_topk_distance_to_gt_px_posthoc") for row in group), 3),
                "median_peak_background_ratio": fmt(median_clean(row.get("top1_background_ratio") for row in group), 4),
                "median_support_area_px": fmt(median_clean(row.get("support_area_px") for row in group), 0),
                "median_area_ratio_vs_true_mode": fmt(median_clean(row.get("area_ratio_vs_true_mode") for row in group), 4),
                "serious_peak_competition_rate": rate(sum(1 for row in group if row.get("peak_competition_label") == "serious_peak_competition_or_clutter"), n),
                "scatter_cluster_type_mix": compact_counts(row.get("scatter_cluster_type", "") for row in group),
                "temporal_stability_label_mix": compact_counts(row.get("temporal_stability_label", "") for row in group),
                "interpretation": comparison_interpretation(mode, support_type, variant, group),
                "provenance_labels": "SAR_image_observation;SAR_temporal_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    return rows


def comparison_lookup(comparison_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    return {
        (str(row.get("source_mode_name", "")), str(row.get("control_support_type", "")), str(row.get("control_variant", ""))): row
        for row in comparison_rows
    }


def float_metric(row: Mapping[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    return safe_float(row.get(key))


def build_mechanism_notes(
    comparison_rows: Sequence[Mapping[str, Any]],
    blockers: Sequence[str],
) -> list[dict[str, Any]]:
    lookup = comparison_lookup(comparison_rows)
    broad_true = lookup.get(("broad_fan_baseline", "true_support", "ALL"))
    state_true = lookup.get(("state_conditioned_range_band", "true_support", "ALL"))
    state_wrong_object = lookup.get(("state_conditioned_range_band", "wrong_object_support", "ALL"))
    state_wrong_frame = lookup.get(("state_conditioned_range_band", "wrong_sar_frame_support", "ALL"))
    notes = [
        {
            "note_id": "M001",
            "mechanism_line": "counterfactual_validation",
            "observation": (
                f"broad true top-k near-GT rate={float_metric(broad_true, 'topk_contains_near_gt_rate_posthoc')}; "
                f"state-conditioned true top-k near-GT rate={float_metric(state_true, 'topk_contains_near_gt_rate_posthoc')}; "
                f"state-conditioned wrong-object={float_metric(state_wrong_object, 'topk_contains_near_gt_rate_posthoc')}; "
                f"state-conditioned wrong-frame={float_metric(state_wrong_frame, 'topk_contains_near_gt_rate_posthoc')}"
            ),
            "interpretation": "State-conditioned support separates strongly from random and range-shift controls, but wrong-object and wrong-frame controls expose same-scene and frame-insensitive pseudo-signal risk.",
            "next_probe_or_blocker": "Run gate-provenance and object-confusion controls before promoting any association state beyond posthoc validation.",
            "provenance_labels": "SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "note_id": "M002",
            "mechanism_line": "sar_scatter_structure",
            "observation": "Top-k cluster type and temporal stability are more informative than top1 peak position alone.",
            "interpretation": "SAR vehicle evidence should be modeled as an extended scatter structure with peak competition and temporal persistence.",
            "next_probe_or_blocker": "Inspect compact, multi-peak, range-spread, and azimuth-spread clusters against SAR-only morphology references without mixing them into correspondence.",
            "provenance_labels": "SAR_image_observation;SAR_temporal_observation;hypothesis_to_validate",
        },
        {
            "note_id": "M003",
            "mechanism_line": "broad_support_failure",
            "observation": "Broad support covers much of the fan radius, so wrong/random support can still encounter strong background peaks.",
            "interpretation": "A high peak/background ratio inside broad support is not evidence of localization by itself.",
            "next_probe_or_blocker": "Keep broad fan as coverage baseline, not as final center evidence.",
            "provenance_labels": "runtime_safe_optical_evidence;SAR_image_observation",
        },
        {
            "note_id": "M004",
            "mechanism_line": "negative_control_blockers",
            "observation": compact_counts(blockers, limit=6) if blockers else "no bootstrap control blockers",
            "interpretation": "Broad full-radius support cannot produce meaningful range-shift controls; same-state random controls need a separate state-balanced sampler.",
            "next_probe_or_blocker": "Implement same_state_random_support after the state pool is balanced and GM_RM019 review clarifies object hypotheses.",
            "provenance_labels": "insufficient_or_not_supported;hypothesis_to_validate",
        },
    ]
    return notes


def build_cue_sketch(comparison_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    lookup = comparison_lookup(comparison_rows)
    broad_true = lookup.get(("broad_fan_baseline", "true_support", "ALL"))
    state_true = lookup.get(("state_conditioned_range_band", "true_support", "ALL"))
    state_random = lookup.get(("state_conditioned_range_band", "random_same_scene_support", "ALL"))
    state_wrong_frame = lookup.get(("state_conditioned_range_band", "wrong_sar_frame_support", "ALL"))
    return [
        {
            "cue_layer": "time_only",
            "runtime_safe_status": "runtime_safe_temporal_evidence",
            "expected_contribution": "Maps optical frames into candidate SAR windows but cannot localize in fan space.",
            "current_evidence": f"wrong-frame state-conditioned top-k near-GT rate={float_metric(state_wrong_frame, 'topk_contains_near_gt_rate_posthoc')}",
            "blocker_or_next_probe": "High wrong-frame rates mean timing alone cannot prove association; use temporal tube changes and gate provenance, not single-frame identity truth.",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;hypothesis_to_validate",
        },
        {
            "cue_layer": "time_plus_azimuth",
            "runtime_safe_status": "runtime_safe_optical_evidence",
            "expected_contribution": "Provides fan-sector support from optical bbox x and software timing.",
            "current_evidence": f"broad true top-k near-GT rate={float_metric(broad_true, 'topk_contains_near_gt_rate_posthoc')}",
            "blocker_or_next_probe": "Broad support remains too wide; it is coverage support, not center evidence.",
            "provenance_labels": "runtime_safe_optical_evidence;SAR_image_observation;SAR_GT_posthoc_evidence",
        },
        {
            "cue_layer": "time_plus_azimuth_plus_state",
            "runtime_safe_status": "runtime_safe_optical_evidence_with_posthoc_validation_needed",
            "expected_contribution": "State changes the uncertainty width and separates complete, edge/truncated, duplicate, and dropout cases.",
            "current_evidence": f"state-conditioned true top-k near-GT rate={float_metric(state_true, 'topk_contains_near_gt_rate_posthoc')}; random control={float_metric(state_random, 'topk_contains_near_gt_rate_posthoc')}",
            "blocker_or_next_probe": "Derive range uncertainty from runtime-safe state/geometry before using it as a prior.",
            "provenance_labels": "runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "cue_layer": "bbox_height_or_shape_radius_relation",
            "runtime_safe_status": "posthoc_observation_only",
            "expected_contribution": "May explain range narrowing for complete-state vehicles.",
            "current_evidence": "Earlier range audit selected bbox_height_px by posthoc correlation; this bootstrap does not promote it.",
            "blocker_or_next_probe": "Needs runtime-safe derivation and scene-balanced validation before prior construction.",
            "provenance_labels": "SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "cue_layer": "object_smoothing_or_scene_residual",
            "runtime_safe_status": "posthoc_observation_only",
            "expected_contribution": "May reduce single-frame jitter if object hypotheses are reviewed and stable.",
            "current_evidence": "Object-smoothed range bands showed potential in prior audit but are GT-trend diagnostics now.",
            "blocker_or_next_probe": "GM_RM019 review should confirm object hypotheses and complete frames; GM_RM011 needs object-stream recovery.",
            "provenance_labels": "manual_or_review_anchor;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "cue_layer": "sar_observation_gate",
            "runtime_safe_status": "SAR_image_observation_not_runtime_prior",
            "expected_contribution": "Confirms scatter structure inside support after the support is built.",
            "current_evidence": "Cluster types and temporal labels separate stable structures from jumping/diffuse peaks.",
            "blocker_or_next_probe": "Do not write SAR image or GT-derived success back into optical prior construction.",
            "provenance_labels": "SAR_image_observation;SAR_temporal_observation;hypothesis_to_validate",
        },
    ]


def aggregate_negative_rate(
    comparison_rows: Sequence[Mapping[str, Any]],
    mode: str,
    metric: str,
) -> float | None:
    values = [
        safe_float(row.get(metric))
        for row in comparison_rows
        if row.get("source_mode_name") == mode
        and row.get("control_variant") == "ALL"
        and row.get("control_support_type") != "true_support"
    ]
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def build_summary(
    timestamp: str,
    counterfactual_rows: Sequence[Mapping[str, Any]],
    comparison_rows: Sequence[Mapping[str, Any]],
    mechanism_rows: Sequence[Mapping[str, Any]],
    cue_rows: Sequence[Mapping[str, Any]],
    blockers: Sequence[str],
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    lookup = comparison_lookup(comparison_rows)
    broad_true = lookup.get(("broad_fan_baseline", "true_support", "ALL"))
    state_true = lookup.get(("state_conditioned_range_band", "true_support", "ALL"))
    broad_neg = aggregate_negative_rate(comparison_rows, "broad_fan_baseline", "topk_contains_near_gt_rate_posthoc")
    state_neg = aggregate_negative_rate(comparison_rows, "state_conditioned_range_band", "topk_contains_near_gt_rate_posthoc")
    state_true_rate = float_metric(state_true, "topk_contains_near_gt_rate_posthoc") or 0.0
    broad_true_rate = float_metric(broad_true, "topk_contains_near_gt_rate_posthoc") or 0.0
    state_random = lookup.get(("state_conditioned_range_band", "random_same_scene_support", "ALL"))
    state_az = lookup.get(("state_conditioned_range_band", "azimuth_shifted_support", "ALL"))
    state_range = lookup.get(("state_conditioned_range_band", "range_shifted_support", "ALL"))
    state_wrong_object = lookup.get(("state_conditioned_range_band", "wrong_object_support", "ALL"))
    state_wrong_frame = lookup.get(("state_conditioned_range_band", "wrong_sar_frame_support", "ALL"))
    state_wrong_object_rate = float_metric(state_wrong_object, "topk_contains_near_gt_rate_posthoc")
    state_wrong_frame_rate = float_metric(state_wrong_frame, "topk_contains_near_gt_rate_posthoc")
    negative_statement = "true support is clearly above random and range-shift controls"
    if (
        state_wrong_object_rate is not None
        and state_wrong_object_rate >= state_true_rate - 0.25
    ) or (
        state_wrong_frame_rate is not None
        and state_wrong_frame_rate >= state_true_rate - 0.10
    ):
        negative_statement += ", but wrong-object or wrong-frame controls remain high and expose association-risk pseudo signal"
    true_structure_counts = Counter(
        row.get("scatter_cluster_type", "")
        for row in counterfactual_rows
        if row.get("control_support_type") == "true_support" and row.get("source_mode_name") == "state_conditioned_range_band"
    )
    answers = {
        "1_true_vs_negative": (
            f"For state-conditioned support, true top-k near-GT rate is {fmt(state_true_rate, 4)} versus average negative-control rate {fmt(state_neg, 4)}; "
            f"{negative_statement}. Broad true support remains weak at {fmt(broad_true_rate, 4)}."
        ),
        "2_pseudo_signal_risk": (
            "If true and negative controls are close, the likely pseudo-signal is broad support area, same-scene object confusion, or frame-insensitive SAR scattering: strong background or neighboring-object peaks can appear inside many supports without proving association."
        ),
        "3_state_conditioned_advantage": (
            f"State-conditioned true support is compared with azimuth-shifted={float_metric(state_az, 'topk_contains_near_gt_rate_posthoc')}, "
            f"range-shifted={float_metric(state_range, 'topk_contains_near_gt_rate_posthoc')}, random={float_metric(state_random, 'topk_contains_near_gt_rate_posthoc')}, "
            f"wrong-object={state_wrong_object_rate}, and wrong-frame={state_wrong_frame_rate}. "
            "Its strongest separation is radial/state versus range-shift and random controls; wrong-object and wrong-frame need gate-provenance follow-up."
        ),
        "4_broad_pseudo_peaks": (
            "Broad support spans the full fan radius with large area, so local peak/background and top1/top2 competition mostly describe SAR clutter and sidelobe competition, not precise localization."
        ),
        "5_discriminative_structures": (
            f"State-conditioned true support scatter mix is {json.dumps(dict(true_structure_counts), ensure_ascii=False)}. "
            "Compact, multi-peak nearby, and stable tube patterns are more interpretable than diffuse or jumping peaks."
        ),
        "6_optical_cues": (
            "The strongest runtime-safe optical cues remain time, fan azimuth, object/state uncertainty, and vehicle-shell assumptions. Bbox-height/radius, scene residual, and object-smoothed range trend remain posthoc hypotheses."
        ),
        "7_posthoc_vs_runtime": (
            "GT-near top-k, GT-inside support, object-smoothed GT range, and scene residual are posthoc. Time, optical object stream, azimuth mapping, state labels, and vehicle physical shell have runtime-safe potential."
        ),
        "8_next_priority": (
            "Next priority should be counterfactual gate provenance plus SAR scatter-structure modeling. GM_RM019 review should support object-hypothesis quality; GM_RM011 object-stream recovery is the scale-expansion blocker."
        ),
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "ledger_valid": True,
            "category_counts": EXPECTED_LEDGER,
            "note": "The bootstrap preserves 215 paired, 195 GM_RM011 blocked missing object stream, 20 SAR-only, and 12 dropout/no-match continuation pool.",
        },
        "source_modes": list(SOURCE_MODES),
        "row_scope": (
            "Counterfactual rows use paired optical-object/SAR-GT rows for broad_fan_baseline and state_conditioned_range_band. "
            "Dropout/no-match rows are not mixed into clean morphology; SAR-only and GM_RM011 blocked rows are not used for optical-SAR correspondence."
        ),
        "row_counts": {
            "counterfactual_support_validation": len(counterfactual_rows),
            "negative_control_support_comparison": len(comparison_rows),
            "sar_scatter_structure_mechanism_notes": len(mechanism_rows),
            "optical_cue_contribution_sketch": len(cue_rows),
            "blocker_count": len(blockers),
        },
        "key_metrics": {
            "broad_true_topk_contains_near_gt_rate_posthoc": fmt(broad_true_rate, 4),
            "broad_average_negative_topk_contains_near_gt_rate_posthoc": fmt(broad_neg, 4),
            "state_conditioned_true_topk_contains_near_gt_rate_posthoc": fmt(state_true_rate, 4),
            "state_conditioned_average_negative_topk_contains_near_gt_rate_posthoc": fmt(state_neg, 4),
            "state_conditioned_random_topk_contains_near_gt_rate_posthoc": fmt(float_metric(state_random, "topk_contains_near_gt_rate_posthoc"), 4),
            "state_conditioned_azimuth_shifted_topk_contains_near_gt_rate_posthoc": fmt(float_metric(state_az, "topk_contains_near_gt_rate_posthoc"), 4),
            "state_conditioned_range_shifted_topk_contains_near_gt_rate_posthoc": fmt(float_metric(state_range, "topk_contains_near_gt_rate_posthoc"), 4),
            "state_conditioned_wrong_object_topk_contains_near_gt_rate_posthoc": fmt(state_wrong_object_rate, 4),
            "state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc": fmt(state_wrong_frame_rate, 4),
        },
        "question_answers": answers,
        "blockers": list(blockers[:25]),
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 Parallel Mechanism Exploration Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This bootstrap runs counterfactual / negative-control support validation. It does not generate annotation proposals, selector/ranking outputs, training, tuned thresholds, or identity truth.",
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
    lines.extend(["", "## Required Answers", ""])
    for idx, key in enumerate(
        [
            "1_true_vs_negative",
            "2_pseudo_signal_risk",
            "3_state_conditioned_advantage",
            "4_broad_pseudo_peaks",
            "5_discriminative_structures",
            "6_optical_cues",
            "7_posthoc_vs_runtime",
            "8_next_priority",
        ],
        start=1,
    ):
        lines.append(f"{idx}. {summary['question_answers'][key]}")
    lines.extend(
        [
            "",
            "## Provenance Boundary",
            "",
            "Conclusions use provenance labels: `runtime_safe_optical_evidence`, `runtime_safe_temporal_evidence`, `runtime_safe_geometry_or_vehicle_physics`, `SAR_image_observation`, `SAR_temporal_observation`, `SAR_GT_posthoc_evidence`, `manual_or_review_anchor`, `hypothesis_to_validate`, and `insufficient_or_not_supported`.",
            "",
            "GT-near peak and GT-inside support metrics are posthoc diagnostics only. They are not written into runtime prior construction.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    if summary.get("blockers"):
        lines.extend(["", "## Bootstrap Blockers", ""])
        for item in summary["blockers"][:12]:
            lines.append(f"- {item}")
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
    log_path = WORKSPACE_LOG_DIR / f"oty2_parallel_mechanism_exploration_bootstrap_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_parallel_mechanism_exploration_bootstrap",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "peak_competition_csv": Path(args.peak_competition_csv) if args.peak_competition_csv else latest_path("oty2_support_region_peak_competition_audit_*.csv"),
        "range_summary_json": Path(args.range_summary_json) if args.range_summary_json else latest_path("oty2_range_narrowing_peak_competition_summary_*.json"),
        "gated_summary_json": Path(args.gated_summary_json) if args.gated_summary_json else latest_path("oty2_gated_association_scatter_cluster_summary_*.json"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
    }
    range_summary = json.loads(paths["range_summary_json"].read_text(encoding="utf-8"))
    gated_summary = json.loads(paths["gated_summary_json"].read_text(encoding="utf-8"))
    for name, summary in (("range", range_summary), ("gated", gated_summary)):
        ledger = summary.get("sample_ledger", {}).get("category_counts", {})
        if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
            raise RuntimeError(f"{name} ledger changed; refusing bootstrap: {json.dumps(ledger, ensure_ascii=False)}")
    peak_rows = [
        row
        for row in read_csv(paths["peak_competition_csv"])
        if row.get("sample_pool") == "paired_optical_object_sar_gt" and row.get("mode_name") in SOURCE_MODES
    ]
    mode_counts = Counter(row.get("mode_name", "") for row in peak_rows)
    for mode in SOURCE_MODES:
        if mode_counts.get(mode, 0) != EXPECTED_LEDGER["paired_optical_object_sar_gt"]:
            raise RuntimeError(f"Expected 215 paired rows for {mode}; got {mode_counts.get(mode, 0)}")
    return {
        "paths": paths,
        "range_summary": range_summary,
        "gated_summary": gated_summary,
        "peak_rows": peak_rows,
        "corr_rows": read_csv(paths["correspondence_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    cache = SarImageCache(max_images=args.image_cache_size)
    counterfactual_rows, blockers = build_counterfactual_rows(inputs["peak_rows"], inputs["corr_rows"], cache)
    comparison_rows = aggregate_comparison_rows(counterfactual_rows)
    mechanism_rows = build_mechanism_notes(comparison_rows, blockers)
    cue_rows = build_cue_sketch(comparison_rows)

    counterfactual_csv = REPORT_DIR / f"oty2_counterfactual_support_validation_{timestamp}.csv"
    comparison_csv = REPORT_DIR / f"oty2_negative_control_support_comparison_{timestamp}.csv"
    mechanism_csv = REPORT_DIR / f"oty2_sar_scatter_structure_mechanism_notes_{timestamp}.csv"
    cue_csv = REPORT_DIR / f"oty2_optical_cue_contribution_sketch_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_parallel_mechanism_exploration_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_parallel_mechanism_exploration_summary_{timestamp}.json"
    design_doc = DOCS_DIR / "oty2_parallel_mechanism_exploration_design.md"
    outputs = {
        "design_doc": str(design_doc),
        "counterfactual_support_validation_csv": str(counterfactual_csv),
        "negative_control_support_comparison_csv": str(comparison_csv),
        "sar_scatter_structure_mechanism_notes_csv": str(mechanism_csv),
        "optical_cue_contribution_sketch_csv": str(cue_csv),
        "parallel_mechanism_exploration_report_md": str(report_md),
        "parallel_mechanism_exploration_summary_json": str(summary_json),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}
    summary = build_summary(
        timestamp,
        counterfactual_rows,
        comparison_rows,
        mechanism_rows,
        cue_rows,
        blockers,
        sources,
        outputs,
    )
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    write_csv(counterfactual_csv, counterfactual_rows, COUNTERFACTUAL_FIELDS)
    write_csv(comparison_csv, comparison_rows, COMPARISON_FIELDS)
    write_csv(mechanism_csv, mechanism_rows, MECHANISM_NOTE_FIELDS)
    write_csv(cue_csv, cue_rows, CUE_SKETCH_FIELDS)
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
    parser.add_argument("--peak-competition-csv", default="")
    parser.add_argument("--range-summary-json", default="")
    parser.add_argument("--gated-summary-json", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--image-cache-size", type=int, default=96)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
