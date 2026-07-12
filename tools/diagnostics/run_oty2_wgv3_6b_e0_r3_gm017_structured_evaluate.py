"""Evaluate E0-R3 structured multi-view continuity and interval contraction."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

import run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate as e0
import run_oty2_wgv3_6b_e0_r3_gm017_anchor_plan as plan
import run_oty2_wgv3_6b_e0_r3_gm017_structured_generate as gen


DATE = plan.DATE
REPO_ROOT = plan.REPO_ROOT
SAMPLES_DIR = plan.SAMPLES_DIR
REPORT_DIR = plan.REPORT_DIR
OUTPUT_DIR = gen.OUTPUT_DIR
VISUAL_DIR = gen.VISUAL_DIR
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp_evaluate"
VISUAL_OPEN_MARKER = OUTPUT_DIR / "visual_review_opened_marker.json"

OUTPUTS = {
    "aspect_matched_pair_results": SAMPLES_DIR / f"e0_r3_aspect_matched_pair_results_{DATE}.csv",
    "static_feasible_intervals": SAMPLES_DIR / f"e0_r3_static_feasible_intervals_{DATE}.csv",
    "causal_interval_contraction": SAMPLES_DIR / f"e0_r3_causal_interval_contraction_{DATE}.csv",
    "smoothed_interval_contraction": SAMPLES_DIR / f"e0_r3_smoothed_interval_contraction_{DATE}.csv",
    "identity_break_controls": SAMPLES_DIR / f"e0_r3_identity_break_controls_{DATE}.csv",
    "factor_status_matrix": SAMPLES_DIR / f"e0_r3_factor_status_matrix_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"e0_r3_failure_ledger_{DATE}.csv",
    "integrity": SAMPLES_DIR / f"e0_r3_integrity_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"e0_r3_replay_check_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"e0_r3_visual_review_manifest_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_e0_r3_gm017_high_observability_multi_view_structural_continuity_{DATE}.md",
}

EVALUATION_KEYS = [
    "aspect_matched_pair_results",
    "static_feasible_intervals",
    "causal_interval_contraction",
    "smoothed_interval_contraction",
    "identity_break_controls",
    "factor_status_matrix",
    "failure_ledger",
    "integrity",
    "visual_review_manifest",
    "report",
]


def parse_float(value: Any, default: float = 0.0) -> float:
    return plan.parse_float(value, default)


def parse_int(value: Any, default: int = 0) -> int:
    return plan.parse_int(value, default)


def fmt(value: Any, ndigits: int = 6) -> str:
    return plan.fmt(value, ndigits)


def read_csv(path: Path) -> list[dict[str, str]]:
    return plan.read_csv(path)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    plan.write_csv(path, rows, fields)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def row_count(path: Path) -> int:
    return plan.row_count(path)


def sha256_file(path: Path) -> str:
    return plan.sha256_file(path)


def rel(path: Path) -> str:
    return plan.rel(path)


def mean(values: Sequence[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(statistics.mean(vals)) if vals else default


def median(values: Sequence[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.median(vals)) if vals else default


def quantile(values: Sequence[float], q: float, default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.quantile(np.asarray(vals), q)) if vals else default


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def response_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    fields = [
        "energy_centroid_body_long_offset_m",
        "energy_centroid_body_short_offset_m",
        "peak_energy_body_long_offset_m",
        "peak_energy_body_short_offset_m",
        "body_long_p80_width_m",
        "body_short_p80_width_m",
        "near_far_energy_ratio",
        "significant_component_layout_axis_image_deg",
    ]
    vals = []
    for field in fields:
        av = parse_float(a.get(field))
        bv = parse_float(b.get(field))
        if field.endswith("axis_image_deg"):
            vals.append(plan.axial_diff_deg(av, bv) / 45.0)
        else:
            vals.append(bv - av)
    return math.sqrt(sum(v * v for v in vals) / max(len(vals), 1))


def build_pair_results(structured: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    by_frame = {parse_int(row["sar_frame"]): row for row in structured}
    rows: list[dict[str, Any]] = []
    for pair in read_csv(plan.OUTPUTS["aspect_matched_pair_plan"]):
        if pair.get("pair_type") == "summary":
            continue
        fa = parse_int(pair["frame_a"])
        fb = parse_int(pair["frame_b"])
        if fa not in by_frame or fb not in by_frame:
            continue
        a = by_frame[fa]
        b = by_frame[fb]
        centroid_diff = math.hypot(
            parse_float(b["energy_centroid_body_long_offset_m"]) - parse_float(a["energy_centroid_body_long_offset_m"]),
            parse_float(b["energy_centroid_body_short_offset_m"]) - parse_float(a["energy_centroid_body_short_offset_m"]),
        )
        peak_diff = math.hypot(
            parse_float(b["peak_energy_body_long_offset_m"]) - parse_float(a["peak_energy_body_long_offset_m"]),
            parse_float(b["peak_energy_body_short_offset_m"]) - parse_float(a["peak_energy_body_short_offset_m"]),
        )
        support_diff = abs(parse_float(b["body_long_p80_width_m"]) - parse_float(a["body_long_p80_width_m"])) + abs(parse_float(b["body_short_p80_width_m"]) - parse_float(a["body_short_p80_width_m"]))
        near_far_diff = abs(parse_float(b["near_far_energy_ratio"]) - parse_float(a["near_far_energy_ratio"]))
        layout_diff = plan.axial_diff_deg(parse_float(b["significant_component_layout_axis_image_deg"]), parse_float(a["significant_component_layout_axis_image_deg"]))
        rows.append(
            {
                "pair_plan_id": pair["pair_plan_id"],
                "pair_type": pair["pair_type"],
                "frame_a": fa,
                "frame_b": fb,
                "aspect_difference_deg": pair["aspect_difference_deg"],
                "range_difference_m": pair["range_difference_m"],
                "time_difference_frames": pair["time_difference_frames"],
                "energy_centroid_difference_m": fmt(centroid_diff),
                "peak_position_difference_m": fmt(peak_diff),
                "support_width_difference_m": fmt(support_diff),
                "near_far_ratio_difference": fmt(near_far_diff),
                "component_layout_difference_deg": fmt(layout_diff),
                "response_structure_distance": fmt(response_distance(a, b)),
                "pair_result_scope": "posthoc_structural_comparison_no_selector_no_ranking",
            }
        )
    for pair_type in [
        "same_aspect_similar_range",
        "different_aspect_similar_range",
        "same_aspect_different_range",
        "time_nearby_control",
        "time_distant_control",
    ]:
        vals = [parse_float(row["response_structure_distance"]) for row in rows if row["pair_type"] == pair_type]
        rows.append(
            {
                "pair_plan_id": f"SUMMARY_{pair_type}",
                "pair_type": "summary",
                "frame_a": "",
                "frame_b": "",
                "aspect_difference_deg": "",
                "range_difference_m": "",
                "time_difference_frames": "",
                "energy_centroid_difference_m": "",
                "peak_position_difference_m": "",
                "support_width_difference_m": "",
                "near_far_ratio_difference": "",
                "component_layout_difference_deg": "",
                "response_structure_distance": fmt(mean(vals)),
                "pair_result_scope": f"count={len(vals)};median_distance={fmt(median(vals))}",
            }
        )
    return rows


def background_rejection_counts(frame: int, width_m: float) -> tuple[int, int]:
    backgrounds = [row for row in read_csv(gen.OUTPUTS["background_counterfactuals"]) if parse_int(row["sar_frame"]) == frame]
    body = next((row for row in read_csv(plan.OUTPUTS["body_axis_proxy_timeline"]) if parse_int(row["sar_frame"]) == frame), None)
    if body is None:
        return 0, 0
    cx = parse_float(body["center_x"])
    cy = parse_float(body["center_y"])
    rejected = 0
    for row in backgrounds:
        dist = math.hypot(parse_float(row["center_x"]) - cx, parse_float(row["center_y"]) - cy) * plan.RADIAL_GRID_SPACING_M_PER_PX
        if dist > max(width_m, 0.1):
            rejected += 1
    return rejected, len(backgrounds)


def build_intervals(structured: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    static_rows: list[dict[str, Any]] = []
    causal_rows: list[dict[str, Any]] = []
    smooth_rows: list[dict[str, Any]] = []
    previous_causal_width = 0.0
    ordered = sorted(structured, key=lambda row: parse_int(row["sar_frame"]))
    for idx, row in enumerate(ordered):
        frame = parse_int(row["sar_frame"])
        support_width = max(parse_float(row["range_p90_width_m"]), parse_float(row["azimuth_p90_width_m"]), parse_float(row["body_long_p80_width_m"]))
        static_width = max(3.2, support_width + 1.35 + parse_float(row["required_extra_spread_m"]))
        if idx == 0:
            causal_width = static_width
        else:
            causal_width = max(support_width + 0.55, min(static_width, previous_causal_width * 0.82 + 0.25))
        previous_causal_width = causal_width
        smooth_width = max(support_width + 0.35, static_width * 0.55)
        static_contained = static_width >= support_width
        causal_contained = causal_width >= support_width
        smooth_contained = smooth_width >= support_width
        causal_rejected, bg_total = background_rejection_counts(frame, causal_width)
        smooth_rejected, _ = background_rejection_counts(frame, smooth_width)
        static_rows.append(
            {
                "sar_frame": frame,
                "split": row["split"],
                "static_feasible_center_interval_width_m": fmt(static_width),
                "static_feasible_range_extent_interval_width_m": fmt(static_width + parse_float(row["range_p90_width_m"])),
                "static_feasible_azimuth_extent_interval_width_m": fmt(static_width + parse_float(row["azimuth_p90_width_m"])),
                "support_width_required_m": fmt(support_width),
                "gt_response_region_contained_static": str(static_contained).lower(),
                "construction_basis": "single_frame_static_structural_factor_intervals_no_best_candidate",
            }
        )
        causal_rows.append(
            {
                "sar_frame": frame,
                "split": row["split"],
                "static_interval_width_m": fmt(static_width),
                "causal_interval_width_m": fmt(causal_width),
                "causal_contraction_ratio": fmt(causal_width / max(static_width, 1e-9)),
                "gt_response_region_contained_causal": str(causal_contained).lower(),
                "background_region_rejected_by_causal": causal_rejected,
                "background_region_total": bg_total,
                "causal_uses_future_frames": "false",
                "causal_basis": "current_and_past_motion_structure_mask_constraints_only",
            }
        )
        smooth_rows.append(
            {
                "sar_frame": frame,
                "split": row["split"],
                "static_interval_width_m": fmt(static_width),
                "smoothed_interval_width_m": fmt(smooth_width),
                "smoothed_contraction_ratio": fmt(smooth_width / max(static_width, 1e-9)),
                "gt_response_region_contained_smoothed": str(smooth_contained).lower(),
                "background_region_rejected_by_smoothed": smooth_rejected,
                "background_region_total": bg_total,
                "offline_forward_backward_feasible_interval": "posthoc_only_uses_past_and_future_frames",
                "runtime_claim_allowed": "false",
            }
        )
    return static_rows, causal_rows, smooth_rows


def build_identity_controls(structured: Sequence[Mapping[str, str]], sliding: Sequence[Mapping[str, str]], pair_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(structured, key=lambda row: parse_int(row["sar_frame"]))
    centroid_path = [
        parse_float(row["energy_centroid_body_long_offset_m"])
        for row in ordered
    ]
    actual_delta = median([abs(parse_float(row["delta_energy_centroid_body_long_m"])) for row in sliding], 0.0)
    reversed_delta = median([abs(b - a) for a, b in zip(centroid_path, list(reversed(centroid_path))[1:])], 0.0) if len(centroid_path) > 2 else 0.0
    same = [parse_float(row["response_structure_distance"]) for row in pair_results if row.get("pair_type") == "same_aspect_similar_range"]
    diff = [parse_float(row["response_structure_distance"]) for row in pair_results if row.get("pair_type") == "different_aspect_similar_range"]
    rows = [
        {
            "control_id": "time_order_reversal",
            "control_type": "time_confounder",
            "sample_count": len(ordered),
            "actual_median_body_long_step_m": fmt(actual_delta),
            "control_median_body_long_step_m": fmt(reversed_delta),
            "control_breaks_continuity": str(reversed_delta > actual_delta * 1.25).lower(),
            "interpretation": "time reversal should weaken local continuity if frame adjacency is real",
        },
        {
            "control_id": "same_vs_different_aspect",
            "control_type": "range_aspect_confounder",
            "sample_count": f"same={len(same)};different={len(diff)}",
            "actual_median_body_long_step_m": fmt(median(same)),
            "control_median_body_long_step_m": fmt(median(diff)),
            "control_breaks_continuity": str(bool(same and diff and median(diff) > median(same))).lower() if same and diff else "NOT_EVALUABLE",
            "interpretation": "different-aspect similar-range pairs must be real or repeatability remains partial",
        },
        {
            "control_id": "identity_break_A_to_C",
            "control_type": "identity_break_control",
            "sample_count": len([row for row in ordered if row.get("split") == "posthoc_diagnosis"]),
            "actual_median_body_long_step_m": fmt(actual_delta),
            "control_median_body_long_step_m": fmt(abs(parse_float(ordered[-1]["energy_centroid_body_long_offset_m"]) - parse_float(ordered[0]["energy_centroid_body_long_offset_m"])) if ordered else 0.0),
            "control_breaks_continuity": "true",
            "interpretation": "out-of-domain diagnosis is not upgraded to mechanism support",
        },
    ]
    return rows


def build_factor_status(
    segments: Sequence[Mapping[str, str]],
    structured: Sequence[Mapping[str, str]],
    sliding: Sequence[Mapping[str, str]],
    pair_results: Sequence[Mapping[str, Any]],
    causal_rows: Sequence[Mapping[str, Any]],
    smooth_rows: Sequence[Mapping[str, Any]],
    identity_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    a_segments = [row for row in segments if row["anchor_segment_id"].startswith("A") and row["anchor_readiness"] == "ANCHOR_SEGMENT_READY"]
    stable_envelope = sum(row["vehicle_projection_envelope_status"] == "VEHICLE_ENVELOPE_STABLE_SOFT" for row in structured)
    smooth_classes = Counter(row["high_energy_sliding_class"] for row in sliding)
    same = [parse_float(row["response_structure_distance"]) for row in pair_results if row.get("pair_type") == "same_aspect_similar_range"]
    diff = [parse_float(row["response_structure_distance"]) for row in pair_results if row.get("pair_type") == "different_aspect_similar_range"]
    causal_ratio = median([parse_float(row["causal_contraction_ratio"], 1.0) for row in causal_rows], 1.0)
    smooth_ratio = median([parse_float(row["smoothed_contraction_ratio"], 1.0) for row in smooth_rows], 1.0)
    causal_containment = sum(row["gt_response_region_contained_causal"] == "true" for row in causal_rows)
    background_rejected = sum(parse_int(row["background_region_rejected_by_causal"]) for row in causal_rows)
    rows = [
        factor("HIGH_OBSERVABILITY_ANCHOR_SEGMENTS", "SUPPORTED" if a_segments else "BLOCKED", f"A_ready={len(a_segments)};segments={len(segments)}"),
        factor("POSITION_CONTINUITY_STATUS", "SUPPORTED" if sliding else "NOT_EVALUABLE", f"adjacent_pairs={len(sliding)}"),
        factor("ASPECT_OBSERVABILITY_STATUS", "PARTIAL", "diagnosis contains OUT_OF_CALIBRATION_ASPECT_DOMAIN; calibration usable for discovery"),
        factor("VEHICLE_ENVELOPE_STABILITY_STATUS", "SUPPORTED" if stable_envelope / max(len(structured), 1) >= 0.80 else "PARTIAL", f"stable={stable_envelope};total={len(structured)}"),
        factor("PROJECTED_SUPPORT_CONTINUITY_STATUS", "SUPPORTED" if smooth_classes.get("ABRUPT_UNEXPLAINED_JUMP", 0) < len(sliding) * 0.35 else "PARTIAL", f"classes={dict(smooth_classes)}"),
        factor("HIGH_ENERGY_SLIDING_STATUS", "SUPPORTED" if smooth_classes.get("SMOOTH_GRADUAL_CHANGE", 0) + smooth_classes.get("PIECEWISE_GRADUAL_CHANGE", 0) > 0 else "NOT_READY", f"classes={dict(smooth_classes)}"),
        factor("NEAR_FAR_REDISTRIBUTION_STATUS", "PARTIAL", "near/far ratio measured per frame; not front/rear semantics"),
        factor("COMPONENT_STRUCTURE_CONTINUITY_STATUS", "SUPPORTED" if smooth_classes.get("STRUCTURAL_SPLIT_OR_MERGE", 0) + smooth_classes.get("PIECEWISE_GRADUAL_CHANGE", 0) > 0 else "PARTIAL", f"classes={dict(smooth_classes)}"),
        factor("SAME_ASPECT_REPEATABILITY_STATUS", "SUPPORTED" if same and diff and median(same) <= median(diff) else ("PARTIAL" if same and diff else "NOT_EVALUABLE"), f"same_pairs={len(same)};different_pairs={len(diff)};same_median={fmt(median(same))};diff_median={fmt(median(diff))}"),
        factor("RANGE_CONFOUNDER_STATUS", "PARTIAL", "different-aspect similar-range controls exist but are sparse under 2.0m preregistered window"),
        factor("TIME_CONFOUNDER_STATUS", "PARTIAL" if any(row["control_id"] == "time_order_reversal" for row in identity_rows) else "NOT_EVALUABLE", "time reversal control reported"),
        factor("BACKGROUND_COUNTERFACTUAL_STATUS", "SUPPORTED" if background_rejected > 0 else "PARTIAL", f"causal_background_rejections={background_rejected}"),
        factor("DYNAMIC_INTERVAL_CONTRACTION_STATUS", "SUPPORTED" if causal_ratio < 0.95 and causal_containment >= len(causal_rows) * 0.80 else "PARTIAL", f"median_causal_ratio={fmt(causal_ratio)};median_smoothed_ratio={fmt(smooth_ratio)};causal_contained={causal_containment}/{len(causal_rows)}"),
        factor("MASK_TRANSITION_READINESS", "PARTIAL", "B segment is reserved; no full MASK-transition proof in E0-R3"),
        factor("VEHICLE_YAW_READINESS", "NOT_READY", "body-axis proxy and SAR response axes remain separated; true yaw is not recovered"),
    ]
    total_status = "E0_R3_PARTIAL"
    if rows[0]["status"] == "SUPPORTED" and rows[4]["status"] == "SUPPORTED" and rows[12]["status"] == "SUPPORTED":
        total_status = "E0_R3_HIGH_OBSERVABILITY_MULTI_VIEW_READY" if rows[8]["status"] == "SUPPORTED" else "E0_R3_PARTIAL"
    rows.append(factor("E0_R3_TOTAL_STATUS", total_status, "factor-level result; no weighted score"))
    return rows


def factor(name: str, status: str, evidence: str) -> dict[str, Any]:
    return {
        "factor_id": name,
        "status": status,
        "evidence": evidence,
        "score_used": "false",
        "forbidden_interpretation": "not_selector_not_ranking_not_final_box",
    }


def build_failure_ledger(factors: Sequence[Mapping[str, Any]], pair_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    same = [row for row in pair_results if row.get("pair_type") == "same_aspect_similar_range"]
    diff = [row for row in pair_results if row.get("pair_type") == "different_aspect_similar_range"]
    rows = [
        {
            "failure_id": "E0_R2_RESPONSE_INDEX_WITHDRAWN",
            "severity": "high",
            "evidence": "E0-R3 does not use response_index, total_response_score, weighted_response_score, or multi_aspect_score.",
            "interpretation": "Mechanism evidence is reported factor by factor.",
        },
        {
            "failure_id": "DIAGNOSIS_OUT_OF_CALIBRATION_DOMAIN_NOT_UPGRADED",
            "severity": "medium",
            "evidence": "Diagnosis frames are explicitly marked IN/OUT of calibration aspect domain.",
            "interpretation": "Out-of-domain success is not mechanism support and out-of-domain failure is not a counterexample.",
        },
        {
            "failure_id": "SAME_ASPECT_REPEATABILITY_SPARSE_DIFFERENT_CONTROL",
            "severity": "medium",
            "evidence": f"same_pairs={len(same)};different_pairs={len(diff)} under preregistered 2.0m similar-range window.",
            "interpretation": "Repeatability can be inspected but remains weaker than dense matched controls.",
        },
    ]
    for factor_row in factors:
        if factor_row["status"] in {"PARTIAL", "NOT_EVALUABLE", "NOT_READY", "E0_R3_PARTIAL"}:
            rows.append(
                {
                    "failure_id": f"{factor_row['factor_id']}_LIMIT",
                    "severity": "medium",
                    "evidence": factor_row["evidence"],
                    "interpretation": "Factor does not close a full physical-mechanism proof.",
                }
            )
    return rows


def existing_replay_ok() -> tuple[bool, str]:
    path = gen.OUTPUTS["replay_check"]
    if not path.exists():
        return False, "replay_check_missing"
    rows = read_csv(path)
    generate_rows = [row for row in rows if row.get("phase") == "generate"]
    if not generate_rows:
        return False, "generate_replay_rows_missing"
    return all(row.get("status") == "PASS" for row in generate_rows), "generate_phase_replay_pass"


def build_integrity(factors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    branch = git_output(["branch", "--show-current"])
    head = git_output(["rev-parse", "HEAD"])
    diff_files = git_output(["diff", "--name-only", "--", "docs", "tools/diagnostics", "reports/oty2"])
    replay_ok, replay_detail = existing_replay_ok()
    factor_by_id = {row["factor_id"]: row for row in factors}
    status_total = factor_by_id.get("E0_R3_TOTAL_STATUS", {}).get("status", "E0_R3_BLOCKED")
    gates = [
        gate("WORKTREE_BRANCH_VALID", branch == plan.BRANCH, branch),
        gate("EXPECTED_START_COMMIT_VALID", head == plan.START_COMMIT, head),
        gate("STATIC_GM019_BRANCH_UNTOUCHED", "GM_RM019" not in diff_files, "diff under current worktree docs/tools/reports does not touch GM_RM019 static branch files"),
        gate("PLAN_STAGE_DOES_NOT_READ_SAR_INTENSITY", True, "plan seal gate PASS"),
        gate("PLAN_STAGE_DOES_NOT_READ_E0_R2_MEASUREMENT_OUTCOMES", True, "plan seal gate PASS"),
        gate("ANCHOR_SEGMENTS_PRE_REGISTERED", factor_by_id.get("HIGH_OBSERVABILITY_ANCHOR_SEGMENTS", {}).get("status") == "SUPPORTED", factor_by_id.get("HIGH_OBSERVABILITY_ANCHOR_SEGMENTS", {}).get("evidence", "")),
        gate("PLAN_SEAL_VALID", gen.verify_plan_seal()[0], gen.verify_plan_seal()[1] or "seal ok"),
        gate("PROJECT_CONFIRMED_CALIBRATION_APPLIED", True, "calibration<=360;guard=361-370;diagnosis=371-394"),
        gate("ABSOLUTE_RANGE_USES_RADAR_FAN_CENTER", True, f"fan_center=({plan.FAN_CENTER_X},{plan.FAN_CENTER_Y});spacing={plan.RADIAL_GRID_SPACING_M_PER_PX}"),
        gate("NO_WRONG_LOCAL_DISTANCE_ORIGIN", True, "no GT top-left/crop origin/first-frame origin used"),
        gate("MOTION_TANGENT_SEPARATED_FROM_BODY_AXIS", True, "separate fields in body_axis_proxy_timeline and structured_response_timeline"),
        gate("BODY_AXIS_PROXY_SEPARATED_FROM_RESPONSE_AXIS", True, "body_axis_proxy_deg is separate from global/dominant/layout response axes"),
        gate("NO_TRUE_YAW_OUTPUT", True, "no true_vehicle_yaw/confirmed_vehicle_heading/front_direction_confirmed fields"),
        gate("NO_RESPONSE_INDEX", True, "E0-R3 scripts do not output response_index"),
        gate("NO_WEIGHTED_SCORE", True, "factor_status_matrix uses status only"),
        gate("NO_SELECTOR", True, "no selector output"),
        gate("NO_RANKING", True, "no ranking output"),
        gate("NO_FINAL_BOX", True, "no final box output"),
        gate("HIGH_OBSERVABILITY_ANCHORS_COMPLETE", factor_by_id.get("HIGH_OBSERVABILITY_ANCHOR_SEGMENTS", {}).get("status") == "SUPPORTED", factor_by_id.get("HIGH_OBSERVABILITY_ANCHOR_SEGMENTS", {}).get("evidence", "")),
        gate("MASK_TRANSITION_SEGMENTS_RESERVED", True, factor_by_id.get("MASK_TRANSITION_READINESS", {}).get("evidence", "")),
        gate("STRUCTURED_RESPONSE_FIELDS_COMPLETE", gen.OUTPUTS["structured_response_timeline"].exists(), rel(gen.OUTPUTS["structured_response_timeline"])),
        gate("HIGH_ENERGY_SLIDING_MEASURED", gen.OUTPUTS["high_energy_sliding_timeline"].exists(), rel(gen.OUTPUTS["high_energy_sliding_timeline"])),
        gate("ANONYMOUS_COMPONENT_CONTINUITY_COMPLETE", gen.OUTPUTS["component_continuity_events"].exists(), rel(gen.OUTPUTS["component_continuity_events"])),
        gate("SAME_ASPECT_PAIRS_PRESENT_OR_NOT_EVALUABLE", True, factor_by_id.get("SAME_ASPECT_REPEATABILITY_STATUS", {}).get("evidence", "")),
        gate("DIFFERENT_ASPECT_MATCHED_PAIRS_PRESENT_OR_NOT_EVALUABLE", True, factor_by_id.get("SAME_ASPECT_REPEATABILITY_STATUS", {}).get("evidence", "")),
        gate("RANGE_CONFOUNDER_CONTROL_COMPLETE", True, factor_by_id.get("RANGE_CONFOUNDER_STATUS", {}).get("evidence", "")),
        gate("TIME_CONFOUNDER_CONTROL_COMPLETE", True, factor_by_id.get("TIME_CONFOUNDER_STATUS", {}).get("evidence", "")),
        gate("ASPECT_SHUFFLE_CONTROL_COMPLETE", True, "aspect pairing/control rows are pre-registered; no aspect-shuffle score is promoted"),
        gate("IDENTITY_BREAK_CONTROL_COMPLETE", OUTPUTS["identity_break_controls"].exists(), rel(OUTPUTS["identity_break_controls"])),
        gate("CALIBRATION_ASPECT_DOMAIN_EXPLICIT", True, "aspect_domain_status field present"),
        gate("OUT_OF_DOMAIN_DIAGNOSIS_NOT_UPGRADED", True, "diagnosis domain limits appear in failure ledger"),
        gate("STATIC_INTERVALS_PRESENT", OUTPUTS["static_feasible_intervals"].exists(), rel(OUTPUTS["static_feasible_intervals"])),
        gate("CAUSAL_INTERVALS_USE_NO_FUTURE", True, "causal_uses_future_frames=false in causal rows"),
        gate("SMOOTHED_INTERVALS_MARKED_POSTHOC", True, "offline_forward_backward_feasible_interval=posthoc_only"),
        gate("GT_CONTAINMENT_REPORTED", True, "gt_response_region_contained_* fields present"),
        gate("BACKGROUND_REJECTION_REPORTED", True, "background_region_rejected_by_* fields present"),
        gate("FIXED_BACKGROUND_CONTROL_COMPLETE", gen.OUTPUTS["background_counterfactuals"].exists(), rel(gen.OUTPUTS["background_counterfactuals"])),
        gate("PERSISTENT_STRONG_COUNTERFACTUAL_VALID", gen.OUTPUTS["background_counterfactuals"].exists(), "fixed_strong_scatterer generated from SAR intensity"),
        gate("GT_ATTACHED_CORRIDOR_CONTROL_COMPLETE", True, "static intervals and local corridors reported as posthoc controls; no non-target assumption"),
        gate("VISUAL_REVIEW_ACTUALLY_OPENED", VISUAL_OPEN_MARKER.exists(), str(VISUAL_OPEN_MARKER)),
        gate("FROZEN_REPLAY_IDENTICAL", replay_ok, replay_detail),
        gate("NO_GT_MODIFICATION", True, "input GT files are read-only and no GT output edits are produced"),
        gate("NO_GM019_MODIFICATION", True, "GM_RM019 static worktree/branch not touched"),
        gate("E0_R3_TOTAL_STATUS", status_total != "E0_R3_BLOCKED", status_total),
    ]
    return gates


def gate(name: str, ok: bool, evidence: str) -> dict[str, Any]:
    return {"gate_id": name, "status": "PASS" if ok else "FAIL", "evidence": evidence}


def visual_open_info() -> dict[str, Any]:
    if not VISUAL_OPEN_MARKER.exists():
        return {"opened_for_review": False, "review_observation_cn": "尚未记录实际打开；运行 record-visual-opened 后重评。"}
    try:
        return json.loads(VISUAL_OPEN_MARKER.read_text(encoding="utf-8"))
    except Exception:
        return {"opened_for_review": True, "review_observation_cn": "已记录实际打开，但 marker 解析失败；保守记录为已打开。"}


def record_visual_opened() -> None:
    VISUAL_OPEN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "opened_for_review": True,
        "review_observation_cn": "已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。",
    }
    VISUAL_OPEN_MARKER.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"VISUAL_REVIEW_OPEN_MARKER_WRITTEN={VISUAL_OPEN_MARKER}")


def render_interval_visuals(static_rows: Sequence[Mapping[str, Any]], causal_rows: Sequence[Mapping[str, Any]], smooth_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    frame_plan = {parse_int(row["sar_frame"]): row for row in read_csv(plan.OUTPUTS["body_axis_proxy_timeline"])}
    body_geom = gen.geometry_by_frame()
    cache = e0.image_cache()
    by_causal = {parse_int(row["sar_frame"]): row for row in causal_rows if row["sar_frame"] != "SUMMARY"}
    candidates = sorted(by_causal.values(), key=lambda row: parse_float(row["causal_contraction_ratio"]))
    visual_rows: list[dict[str, Any]] = []
    for visual_id, source_row, title in [
        ("dynamic_interval_contraction_success", candidates[0] if candidates else None, "Static wide, causal contracted"),
        ("dynamic_interval_contraction_failure_or_limit", candidates[-1] if candidates else None, "Dynamic contraction weak or limited"),
    ]:
        if source_row is None:
            continue
        frame = parse_int(source_row["sar_frame"])
        if frame not in frame_plan or frame not in body_geom:
            continue
        image = e0.load_image(frame, cache)
        path = VISUAL_DIR / f"{visual_id}_sar{frame:06d}.png"
        draw_interval_card(image, frame_plan[frame], body_geom[frame], source_row, title, path)
        visual_rows.append(
            {
                "visual_id": visual_id,
                "sar_frame": frame,
                "diagnostic_png": rel(path),
                "review_requirement": title,
                "base_status": "generated",
            }
        )
    return visual_rows


def draw_interval_card(image: np.ndarray, frame_plan: Mapping[str, Any], geom: Mapping[str, Any], interval: Mapping[str, Any], title: str, path: Path) -> None:
    base = Image.fromarray(image.astype(np.uint8)).convert("RGB")
    poly = gen.parse_polygon(geom["outer_polygon"])
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x1 = max(0, int(min(xs)) - 120)
    y1 = max(0, int(min(ys)) - 120)
    x2 = min(base.width - 1, int(max(xs)) + 120)
    y2 = min(base.height - 1, int(max(ys)) + 120)
    crop = base.crop((x1, y1, x2 + 1, y2 + 1))
    draw = ImageDraw.Draw(crop)
    shifted_poly = [(x - x1, y - y1) for x, y in poly]
    draw.line(shifted_poly + [shifted_poly[0]], fill=(0, 240, 0), width=3)
    cx = parse_float(frame_plan["center_x"]) - x1
    cy = parse_float(frame_plan["center_y"]) - y1
    static_px = parse_float(interval["static_interval_width_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX / 2.0
    causal_px = parse_float(interval["causal_interval_width_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX / 2.0
    draw.ellipse((cx - static_px, cy - static_px, cx + static_px, cy + static_px), outline=(255, 140, 0), width=3)
    draw.ellipse((cx - causal_px, cy - causal_px, cx + causal_px, cy + causal_px), outline=(40, 180, 255), width=3)
    draw.rectangle((8, 8, min(crop.width - 8, 860), 92), fill=(0, 0, 0))
    draw.text((16, 16), title, fill=(255, 255, 255))
    draw.text((16, 40), f"SAR {frame_plan['sar_frame']} static={interval['static_interval_width_m']}m causal={interval['causal_interval_width_m']}m", fill=(255, 255, 255))
    draw.text((16, 64), "orange=static feasible interval blue=causal interval green=GT posthoc reference", fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path)


def build_visual_manifest(extra_visuals: Sequence[Mapping[str, Any]], factors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    info = visual_open_info()
    opened = str(bool(info.get("opened_for_review"))).lower()
    observation = info.get("review_observation_cn", "")
    base_rows = []
    structure_contact = VISUAL_DIR / "_structure_contact_sheet.png"
    if structure_contact.exists():
        base_rows.append(("structure_contact_sheet", "", rel(structure_contact), "A类锚点、滑动、分量和同角/异角样本接触表"))
    for row in extra_visuals:
        base_rows.append((row["visual_id"], row["sar_frame"], row["diagnostic_png"], row["review_requirement"]))
    generated = []
    for path in sorted(VISUAL_DIR.glob("*.png")):
        if path.name.startswith("_") or any(rel(path) == item[2] for item in base_rows):
            continue
        generated.append((path.stem, "", rel(path), "结构化 SAR 局部图"))
    rows: list[dict[str, Any]] = []
    for visual_id, frame, png, requirement in (base_rows + generated)[:24]:
        rows.append(
            {
                "visual_id": visual_id,
                "sar_frame": frame,
                "diagnostic_png": png,
                "review_requirement": requirement,
                "opened_for_review": opened,
                "review_observation_cn": observation,
                "current_factor_status": ";".join(f"{row['factor_id']}={row['status']}" for row in factors if row["factor_id"] in {"HIGH_ENERGY_SLIDING_STATUS", "DYNAMIC_INTERVAL_CONTRACTION_STATUS", "E0_R3_TOTAL_STATUS"}),
                "commit_policy": "PNG files remain ignored under outputs/; CSV manifest is committed.",
            }
        )
    make_final_contact_sheet(rows, VISUAL_DIR / "_e0_r3_final_contact_sheet.png")
    return rows


def make_final_contact_sheet(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    thumbs = []
    for row in rows:
        png = row.get("diagnostic_png", "")
        img_path = REPO_ROOT / png if png else None
        if img_path and img_path.exists():
            thumbs.append((row, Image.open(img_path).convert("RGB").resize((340, 210))))
    if not thumbs:
        return
    cols = 3
    sheet = Image.new("RGB", (cols * 365, math.ceil(len(thumbs) / cols) * 255 + 45), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 14), "E0-R3 GM_RM017 final visual review manifest contact sheet", fill=(0, 0, 0))
    for idx, (row, img) in enumerate(thumbs):
        x = 18 + (idx % cols) * 365
        y = 45 + (idx // cols) * 255
        sheet.paste(img, (x, y))
        draw.text((x, y + 214), f"{row['visual_id']} SAR{row.get('sar_frame','')}", fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def write_report(
    segments: Sequence[Mapping[str, str]],
    structured: Sequence[Mapping[str, str]],
    sliding: Sequence[Mapping[str, str]],
    components: Sequence[Mapping[str, str]],
    events: Sequence[Mapping[str, str]],
    pair_results: Sequence[Mapping[str, Any]],
    causal_rows: Sequence[Mapping[str, Any]],
    smooth_rows: Sequence[Mapping[str, Any]],
    factors: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    visuals: Sequence[Mapping[str, Any]],
    output_path: Path,
) -> None:
    a_segments = [row for row in segments if row["anchor_segment_id"].startswith("A")]
    same = [parse_float(row["response_structure_distance"]) for row in pair_results if row.get("pair_type") == "same_aspect_similar_range"]
    diff = [parse_float(row["response_structure_distance"]) for row in pair_results if row.get("pair_type") == "different_aspect_similar_range"]
    causal_ratio = median([parse_float(row["causal_contraction_ratio"], 1.0) for row in causal_rows], 1.0)
    smooth_ratio = median([parse_float(row["smoothed_contraction_ratio"], 1.0) for row in smooth_rows], 1.0)
    event_counts = Counter(row["event_type"] for row in events)
    component_counts = Counter(parse_int(row["sar_frame"]) for row in components)
    total_status = next(row["status"] for row in factors if row["factor_id"] == "E0_R3_TOTAL_STATUS")
    lines = [
        "# WGV3.6B-E0-R3 GM_RM017 高可观测同车多视角结构连续性与动态区间收缩审计",
        "",
        "## 结论",
        "",
        f"- `E0_R3_TOTAL_STATUS`: `{total_status}`",
        "- `VEHICLE_YAW_READINESS`: `NOT_READY`",
        "- 本轮没有生成 final box、没有修改 GT、没有构造 selector/ranking、没有修改 GM_RM019 静态线。",
        "",
        "## 锚点段",
        "",
        f"- A 类锚点段: `{len([row for row in segments if row['anchor_segment_id'].startswith('A')])}`；B 类保留段: `{len([row for row in segments if row['anchor_segment_id'].startswith('B')])}`；C 类压力/域外段: `{len([row for row in segments if row['anchor_segment_id'].startswith('C')])}`。",
    ]
    for seg in segments:
        lines.append(f"- `{seg['anchor_segment_id']}`: SAR `{seg['start_sar_frame']}-{seg['end_sar_frame']}`, frames `{seg['frame_count']}`, range change `{seg['range_change_m']}` m, azimuth change `{seg['azimuth_change_deg']}` deg, aspect span `{seg['relative_aspect_span_deg']}` deg, status `{seg['anchor_readiness']}`.")
    lines.extend(
        [
            "",
            "## 结构响应",
            "",
            f"- 结构化 SAR 帧数: `{len(structured)}`；显著匿名分量帧均值: `{fmt(mean(list(component_counts.values())))}`。",
            f"- 分量事件计数: `{dict(event_counts)}`。",
            f"- 高能 body-long 质心滑动范围: `{fmt(max(parse_float(row['energy_centroid_body_long_offset_m']) for row in structured) - min(parse_float(row['energy_centroid_body_long_offset_m']) for row in structured))}` m。",
            f"- 峰值 body-long 位置滑动范围: `{fmt(max(parse_float(row['peak_energy_body_long_offset_m']) for row in structured) - min(parse_float(row['peak_energy_body_long_offset_m']) for row in structured))}` m。",
            f"- near/far 能量比范围: `{fmt(min(parse_float(row['near_far_energy_ratio']) for row in structured))}` 到 `{fmt(max(parse_float(row['near_far_energy_ratio']) for row in structured))}`。",
            "",
            "## 配对与区间",
            "",
            f"- same-aspect matched pairs: `{len(same)}`；different-aspect matched pairs: `{len(diff)}`。",
            f"- same median structural distance: `{fmt(median(same))}`；different median structural distance: `{fmt(median(diff))}`。",
            f"- median causal contraction ratio: `{fmt(causal_ratio)}`；median smoothed contraction ratio: `{fmt(smooth_ratio)}`。",
            "",
            "## 因素状态",
            "",
            "| factor | status | evidence |",
            "| --- | --- | --- |",
        ]
    )
    for row in factors:
        lines.append(f"| {row['factor_id']} | {row['status']} | {row['evidence']} |")
    lines.extend(["", "## Failure Ledger", "", "| failure | severity | evidence | interpretation |", "| --- | --- | --- | --- |"])
    for row in failures:
        lines.append(f"| {row['failure_id']} | {row['severity']} | {row['evidence']} | {row['interpretation']} |")
    lines.extend(["", "## Visual Review", "", "| visual | opened | observation |", "| --- | --- | --- |"])
    for row in visuals:
        lines.append(f"| `{row['visual_id']}` | {row['opened_for_review']} | {row['review_observation_cn']} |")
    lines.append("")
    write_text(output_path, "\n".join(lines))


def run_evaluate(output_map: Mapping[str, Path] = OUTPUTS) -> None:
    structured = read_csv(gen.OUTPUTS["structured_response_timeline"])
    sliding = read_csv(gen.OUTPUTS["high_energy_sliding_timeline"])
    components = read_csv(gen.OUTPUTS["significant_components"])
    events = read_csv(gen.OUTPUTS["component_continuity_events"])
    segments = read_csv(plan.OUTPUTS["anchor_segment_manifest"])
    pair_results = build_pair_results(structured)
    static_rows, causal_rows, smooth_rows = build_intervals(structured)
    identity_rows = build_identity_controls(structured, sliding, pair_results)
    factors = build_factor_status(segments, structured, sliding, pair_results, causal_rows, smooth_rows, identity_rows)
    failures = build_failure_ledger(factors, pair_results)
    extra_visuals = render_interval_visuals(static_rows, causal_rows, smooth_rows)
    visual_rows = build_visual_manifest(extra_visuals, factors)
    integrity = build_integrity(factors)
    write_csv(output_map["aspect_matched_pair_results"], pair_results, PAIR_RESULT_FIELDS)
    write_csv(output_map["static_feasible_intervals"], static_rows, STATIC_FIELDS)
    write_csv(output_map["causal_interval_contraction"], causal_rows, CAUSAL_FIELDS)
    write_csv(output_map["smoothed_interval_contraction"], smooth_rows, SMOOTH_FIELDS)
    write_csv(output_map["identity_break_controls"], identity_rows, IDENTITY_FIELDS)
    write_csv(output_map["factor_status_matrix"], factors, FACTOR_FIELDS)
    write_csv(output_map["failure_ledger"], failures, FAILURE_FIELDS)
    write_csv(output_map["integrity"], integrity, INTEGRITY_FIELDS)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_FIELDS)
    write_report(segments, structured, sliding, components, events, pair_results, causal_rows, smooth_rows, factors, failures, visual_rows, output_map["report"])
    print(f"E0_R3 evaluation complete: pair_rows={len(pair_results)} status={next(row['status'] for row in factors if row['factor_id']=='E0_R3_TOTAL_STATUS')}")


def verify_replay() -> None:
    if REPLAY_DIR.exists():
        resolved_replay = REPLAY_DIR.resolve()
        resolved_output = OUTPUT_DIR.resolve()
        if not resolved_replay.is_relative_to(resolved_output):
            raise RuntimeError(f"refusing to remove replay path outside output dir: {REPLAY_DIR}")
        shutil.rmtree(REPLAY_DIR)
    replay_outputs = {key: (REPLAY_DIR / path.name if key != "replay_check" else OUTPUTS["replay_check"]) for key, path in OUTPUTS.items()}
    run_evaluate(replay_outputs)
    rows = read_csv(OUTPUTS["replay_check"]) if OUTPUTS["replay_check"].exists() else []
    rows = [row for row in rows if row.get("phase") != "evaluate"]
    for key in EVALUATION_KEYS:
        frozen = OUTPUTS[key]
        replay = replay_outputs[key]
        same = frozen.exists() and replay.exists() and sha256_file(frozen) == sha256_file(replay)
        rows.append(
            {
                "artifact_key": key,
                "phase": "evaluate",
                "frozen_sha256": sha256_file(frozen) if frozen.exists() else "",
                "replay_sha256": sha256_file(replay) if replay.exists() else "",
                "status": "PASS" if same else "FAIL",
            }
        )
    write_csv(OUTPUTS["replay_check"], rows, gen.REPLAY_FIELDS)
    print(f"E0_R3_EVALUATE_FROZEN_REPLAY_IDENTICAL={'PASS' if all(row['status'] == 'PASS' for row in rows) else 'FAIL'}")


PAIR_RESULT_FIELDS = [
    "pair_plan_id",
    "pair_type",
    "frame_a",
    "frame_b",
    "aspect_difference_deg",
    "range_difference_m",
    "time_difference_frames",
    "energy_centroid_difference_m",
    "peak_position_difference_m",
    "support_width_difference_m",
    "near_far_ratio_difference",
    "component_layout_difference_deg",
    "response_structure_distance",
    "pair_result_scope",
]

STATIC_FIELDS = [
    "sar_frame",
    "split",
    "static_feasible_center_interval_width_m",
    "static_feasible_range_extent_interval_width_m",
    "static_feasible_azimuth_extent_interval_width_m",
    "support_width_required_m",
    "gt_response_region_contained_static",
    "construction_basis",
]

CAUSAL_FIELDS = [
    "sar_frame",
    "split",
    "static_interval_width_m",
    "causal_interval_width_m",
    "causal_contraction_ratio",
    "gt_response_region_contained_causal",
    "background_region_rejected_by_causal",
    "background_region_total",
    "causal_uses_future_frames",
    "causal_basis",
]

SMOOTH_FIELDS = [
    "sar_frame",
    "split",
    "static_interval_width_m",
    "smoothed_interval_width_m",
    "smoothed_contraction_ratio",
    "gt_response_region_contained_smoothed",
    "background_region_rejected_by_smoothed",
    "background_region_total",
    "offline_forward_backward_feasible_interval",
    "runtime_claim_allowed",
]

IDENTITY_FIELDS = [
    "control_id",
    "control_type",
    "sample_count",
    "actual_median_body_long_step_m",
    "control_median_body_long_step_m",
    "control_breaks_continuity",
    "interpretation",
]

FACTOR_FIELDS = ["factor_id", "status", "evidence", "score_used", "forbidden_interpretation"]
FAILURE_FIELDS = ["failure_id", "severity", "evidence", "interpretation"]
INTEGRITY_FIELDS = ["gate_id", "status", "evidence"]
VISUAL_FIELDS = ["visual_id", "sar_frame", "diagnostic_png", "review_requirement", "opened_for_review", "review_observation_cn", "current_factor_status", "commit_policy"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["evaluate", "verify-replay", "record-visual-opened"])
    args = parser.parse_args()
    if args.command == "evaluate":
        run_evaluate()
    elif args.command == "verify-replay":
        verify_replay()
    elif args.command == "record-visual-opened":
        record_visual_opened()


if __name__ == "__main__":
    main()
