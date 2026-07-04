"""OTY2 physical SAR vehicle shell grammar and temporal drift diagnostics.

This bounded posthoc diagnostic turns prior GT-anchored morphology artifacts
into a physical structure grammar: scattering atoms, vehicle parts,
vehicle-scale shell hypotheses, part relations, failure modes, temporal drift
consistency, and support-failure explanations.

It intentionally does not perform weighted evidence fusion, selector/ranking,
training, threshold tuning, revised GT, final box output, annotation proposal,
or identity-truth inference. SAR GT and SAR image observations remain posthoc
mechanism validation only and are not written into runtime prediction logic.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import textwrap
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from run_oty2_support_overlay_visualization_qa_and_chinese_review_atlas import (
        FONT,
        wrap_zh,
    )
except Exception:  # pragma: no cover - fallback only if helper import changes.
    FONT = None

    def wrap_zh(text: str, width: int = 34) -> str:
        return "\n".join(textwrap.wrap(text, width=width))


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
VISUAL_DIR = REPORT_DIR / "visual_exemplars"
WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

GT_SCALE_CSV = REPORT_DIR / "oty2_sar_gt_vehicle_scale_statistics_20260703_222135.csv"
GT_QUALITY_CSV = REPORT_DIR / "oty2_sar_gt_quality_audit_20260703_222135.csv"
GT_MORPH_CSV = REPORT_DIR / "oty2_gt_anchored_energy_morphology_20260703_222135.csv"
HIERARCHY_CSV = REPORT_DIR / "oty2_atom_part_shell_hierarchy_20260703_222135.csv"
SUPPORT_MISS_CSV = REPORT_DIR / "oty2_gt_support_miss_failure_cases_20260703_222135.csv"
TEMPORAL_CSV = REPORT_DIR / "oty2_temporal_morphology_drift_probe_20260703_212811.csv"
PANEL_NOTES_CSV = REPORT_DIR / "oty2_panel_review_correction_notes_20260703_212811.csv"
SUPPORT_WIDE_PROXY_CSV = REPORT_DIR / "oty2_support_wide_vehicle_shell_proxy_20260703_212811.csv"
ATOM_COMPONENT_CSV = REPORT_DIR / "oty2_support_wide_energy_atoms_and_components_20260703_212811.csv"

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "physical_shell_grammar_entered": True,
    "part_to_shell_relation_diagnostic_entered": True,
    "temporal_drift_mechanism_entered": True,
    "support_failure_physical_explanation_entered": True,
    "weighted_fusion_deferred": True,
    "weighted_fusion_mainline_used": False,
    "best_weight_selected": False,
    "score_proxy_optimization_entered": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "annotation_proposal_entered": False,
    "revised_gt_box_output": False,
    "final_candidate_box_output": False,
    "identity_truth_claimed": False,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "shell_grammar_written_as_annotation_rule": False,
    "temporal_drift_written_as_identity_truth": False,
    "human_contour_reference_used_as_truth": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
    "archive_or_old_work_used_as_active_source": False,
    "zip_7z_rar_committed": False,
}

SHELL_FIELDS = [
    "case_id",
    "gt_id",
    "scene",
    "sar_frame",
    "pool_type",
    "gt_quality_label",
    "gt_scale_valid",
    "dominant_shell_pattern",
    "shell_parts_used",
    "n_atoms",
    "n_vehicle_parts",
    "n_shell_parts",
    "shell_long_axis_span",
    "shell_short_axis_span",
    "shell_to_gt_width_ratio",
    "shell_to_gt_height_ratio",
    "shell_to_gt_area_ratio",
    "gt_scale_compatible",
    "baby_car_risk",
    "shell_physical_interpretation",
    "vehicle_shell_supported",
    "manual_review_needed",
    "posthoc_only",
    "notes",
]

RELATION_FIELDS = [
    "case_id",
    "part_relation_type",
    "part_a_type",
    "part_b_type",
    "spatial_relation",
    "distance_px",
    "relative_to_gt_scale",
    "supports_shell_grammar",
    "failure_reason",
    "physical_interpretation",
    "notes",
]

FAILURE_FIELDS = [
    "case_id",
    "failure_mode",
    "why_not_vehicle_shell",
    "what_evidence_would_be_needed",
    "manual_review_needed",
    "not_allowed_conclusion",
]

TEMPORAL_FIELDS = [
    "case_id",
    "scene",
    "object_hypothesis_id",
    "sar_frame",
    "frame_offsets_used",
    "temporal_data_available",
    "shell_available_in_frames",
    "ridge_persistence",
    "hotspot_persistence",
    "shell_centroid_drift_px",
    "shell_drift_direction",
    "shell_orientation_change",
    "structure_changes_gradually",
    "non_jump_constraint_supported",
    "background_stable_risk",
    "compatible_with_optical_tracklet_motion",
    "vehicle_like_temporal_drift_supported",
    "notes",
]

SUPPORT_EXPLANATION_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "gt_shell_supported",
    "support_available",
    "support_covers_shell",
    "support_covers_parts_only",
    "support_miss_shell",
    "support_failure_type",
    "physical_explanation",
    "state_or_temporal_compensation_needed",
    "not_allowed_conclusion",
]

FUSION_FIELDS = [
    "fusion_idea",
    "why_deferred",
    "physical_structure_needed_first",
    "risk_if_used_now",
    "allowed_future_role",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value: float, ndigits: int = 4) -> str:
    if not math.isfinite(value):
        return ""
    text = f"{value:.{ndigits}f}"
    return text.rstrip("0").rstrip(".")


def yes(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1"}


def sanitize(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_") or "case"


def compact_counts(values: Sequence[Any]) -> str:
    counts = Counter(str(v) for v in values if str(v) != "")
    return ";".join(f"{k}={v}" for k, v in counts.most_common())


def case_gt_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("scene", "")), str(row.get("sar_frame", "")), str(row.get("gt_id", "")))


def parse_total_drift(text: str) -> str:
    match = re.search(r"total=([0-9.]+)", str(text))
    return match.group(1) if match else ""


def hierarchy_stats(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    counts = Counter(row.get("hierarchy_label", "") for row in rows)
    shell_rows = [r for r in rows if r.get("hierarchy_label") == "vehicle_scale_shell_hypothesis"]
    part_rows = [r for r in rows if r.get("hierarchy_label") == "vehicle_part"]
    usable_rows = shell_rows or part_rows
    long_axis = max((safe_float(r.get("component_long_axis")) for r in usable_rows), default=0.0)
    short_axis = max((safe_float(r.get("component_short_axis")) for r in usable_rows), default=0.0)
    area = sum(safe_float(r.get("component_area")) for r in shell_rows) or sum(
        safe_float(r.get("component_area")) for r in part_rows
    )
    shell_parts = sorted({r.get("component_id", "") for r in shell_rows if r.get("component_id", "")})
    part_types = []
    for row in part_rows[:6]:
        aspect = safe_float(row.get("component_aspect_ratio"))
        if aspect >= 3.0:
            part_types.append("side_ridge_or_strip")
        elif safe_float(row.get("component_area")) >= 250:
            part_types.append("body_block_or_part")
        else:
            part_types.append("endpoint_or_edge_part")
    return {
        "n_atoms": counts.get("scattering_atom", 0),
        "n_vehicle_parts": counts.get("vehicle_part", 0),
        "n_shell_parts": counts.get("vehicle_scale_shell_hypothesis", 0),
        "shell_long_axis_span": long_axis,
        "shell_short_axis_span": short_axis,
        "shell_area": area,
        "shell_parts_used": ";".join(shell_parts or part_types),
    }


def dominant_shell_pattern(morph: Mapping[str, str], stats: Mapping[str, Any]) -> str:
    pattern = morph.get("dominant_energy_pattern", "")
    side = yes(morph.get("near_or_dominant_side_ridge_proxy"))
    corner = yes(morph.get("corner_or_endpoint_hotspot_proxy"))
    enclosed = yes(morph.get("enclosed_shell_proxy"))
    block = yes(morph.get("block_like_body_proxy"))
    spread = yes(morph.get("range_spread_with_core_proxy"))
    discontinuous = yes(morph.get("discontinuous_edge_proxy"))
    if stats.get("n_vehicle_parts", 0) == 0 and stats.get("n_shell_parts", 0) == 0:
        return "no_shell"
    if enclosed or pattern == "enclosed_shell":
        return "enclosed_shell"
    if side and corner:
        return "strip_plus_endpoint"
    if side or pattern == "side_ridge":
        return "side_ridge_shell"
    if discontinuous or pattern == "discontinuous_edges":
        return "bilateral_edges"
    if block or pattern == "block_body":
        return "block_shell"
    if spread or pattern == "diffuse_with_core":
        return "range_spread_with_core"
    if pattern == "weak_boundary":
        return "weak_boundary_shell"
    if corner:
        return "strip_plus_endpoint"
    return "uncertain"


def shell_interpretation(pattern: str, morph: Mapping[str, str]) -> str:
    side = morph.get("dominant_side_or_axis_proxy", "dominant side")
    if pattern == "side_ridge_shell":
        return f"dominant {side} ridge acts as body-side strip; opposite side may be weaker."
    if pattern == "strip_plus_endpoint":
        return "side strip plus endpoint/corner hotspot forms a vehicle-scale shell cue."
    if pattern == "bilateral_edges":
        return "discontinuous edge fragments form a possible long-axis body outline."
    if pattern == "enclosed_shell":
        return "multiple parts surround a GT-scale body extent as a posthoc shell hypothesis."
    if pattern == "block_shell":
        return "block-like body response needs edge or endpoint relation before shell claim."
    if pattern == "range_spread_with_core":
        return "range spread retains a body core; motion/environment spread remains hypothesis."
    if pattern == "weak_boundary_shell":
        return "weak but structured boundary; manual review should check shell continuity."
    if pattern == "no_shell":
        return "available components do not reach vehicle-scale shell grammar."
    return "vehicle structure remains uncertain under physical grammar."


def scale_compatibility(
    stats: Mapping[str, Any], scale: Mapping[str, str], gt_scale_valid: str
) -> tuple[str, str, str, str, str]:
    gt_w = safe_float(scale.get("gt_w"))
    gt_h = safe_float(scale.get("gt_h"))
    gt_area = safe_float(scale.get("gt_area_px"))
    long_ratio = safe_float(stats.get("shell_long_axis_span")) / gt_w if gt_w > 0 else 0.0
    short_ratio = safe_float(stats.get("shell_short_axis_span")) / gt_h if gt_h > 0 else 0.0
    area_ratio = safe_float(stats.get("shell_area")) / gt_area if gt_area > 0 else 0.0
    if gt_scale_valid != "yes":
        compatible = "uncertain"
    elif stats.get("n_shell_parts", 0) > 0 and (0.30 <= long_ratio <= 1.25 or 0.18 <= area_ratio <= 1.15):
        compatible = "yes"
    elif stats.get("n_vehicle_parts", 0) >= 2 and (0.25 <= long_ratio <= 1.15 or 0.12 <= area_ratio <= 0.90):
        compatible = "yes"
    elif stats.get("n_vehicle_parts", 0) > 0:
        compatible = "uncertain"
    else:
        compatible = "no"
    return compatible, fmt(long_ratio), fmt(short_ratio), fmt(area_ratio), fmt(stats.get("shell_area", 0.0))


def build_shell_cases(
    morphology_rows: Sequence[dict[str, str]],
    hierarchy_by_case: Mapping[str, Sequence[dict[str, str]]],
    scale_by_key: Mapping[tuple[str, str, str], dict[str, str]],
    quality_by_key: Mapping[tuple[str, str, str], dict[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for morph in morphology_rows:
        case_id = morph.get("case_id", "")
        stats = hierarchy_stats(hierarchy_by_case.get(case_id, []))
        scale = scale_by_key.get(case_gt_key(morph), {})
        quality = quality_by_key.get(case_gt_key(morph), {})
        gt_scale_valid = scale.get("valid_for_scale_reference", "uncertain")
        compatible, width_ratio, height_ratio, area_ratio, shell_area = scale_compatibility(
            stats, scale, gt_scale_valid
        )
        pattern = dominant_shell_pattern(morph, stats)
        baby_risk = "yes" if compatible == "no" or (
            stats["n_atoms"] > 0 and stats["n_vehicle_parts"] == 0 and stats["n_shell_parts"] == 0
        ) else "no"
        manual_review = "yes" if (
            morph.get("vehicle_morphology_supported") != "yes"
            or quality.get("needs_manual_gt_review") == "yes"
            or baby_risk == "yes"
        ) else "no"
        shell_supported = "yes" if (
            morph.get("vehicle_morphology_supported") == "yes"
            and compatible in {"yes", "uncertain"}
            and pattern != "no_shell"
        ) else ("uncertain" if morph.get("vehicle_morphology_supported") == "uncertain" else "no")
        out.append(
            {
                "case_id": case_id,
                "gt_id": morph.get("gt_id", ""),
                "scene": morph.get("scene", ""),
                "sar_frame": morph.get("sar_frame", ""),
                "pool_type": morph.get("pool_type", ""),
                "gt_quality_label": morph.get("gt_quality_label", ""),
                "gt_scale_valid": gt_scale_valid,
                "dominant_shell_pattern": pattern,
                "shell_parts_used": stats.get("shell_parts_used", ""),
                "n_atoms": stats["n_atoms"],
                "n_vehicle_parts": stats["n_vehicle_parts"],
                "n_shell_parts": stats["n_shell_parts"],
                "shell_long_axis_span": fmt(stats["shell_long_axis_span"]),
                "shell_short_axis_span": fmt(stats["shell_short_axis_span"]),
                "shell_to_gt_width_ratio": width_ratio,
                "shell_to_gt_height_ratio": height_ratio,
                "shell_to_gt_area_ratio": area_ratio if area_ratio else shell_area,
                "gt_scale_compatible": compatible,
                "baby_car_risk": baby_risk,
                "shell_physical_interpretation": shell_interpretation(pattern, morph),
                "vehicle_shell_supported": shell_supported,
                "manual_review_needed": manual_review,
                "posthoc_only": "yes",
                "notes": (
                    "Physical shell grammar is posthoc. Human contour marks are reference language only; "
                    "not revised GT, final box, selector, or identity truth."
                ),
            }
        )
    return out


def add_relation(
    rows: list[dict[str, Any]],
    case_id: str,
    relation: str,
    a_type: str,
    b_type: str,
    spatial: str,
    scale: str,
    supported: str,
    failure: str,
    interpretation: str,
) -> None:
    rows.append(
        {
            "case_id": case_id,
            "part_relation_type": relation,
            "part_a_type": a_type,
            "part_b_type": b_type,
            "spatial_relation": spatial,
            "distance_px": "",
            "relative_to_gt_scale": scale,
            "supports_shell_grammar": supported,
            "failure_reason": failure,
            "physical_interpretation": interpretation,
            "notes": "Relation is physical grammar evidence, not a weighted feature.",
        }
    )


def build_part_relations(shell_rows: Sequence[Mapping[str, Any]], morph_by_case: Mapping[str, Mapping[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for shell in shell_rows:
        case_id = str(shell.get("case_id", ""))
        morph = morph_by_case.get(case_id, {})
        side = yes(morph.get("near_or_dominant_side_ridge_proxy"))
        corner = yes(morph.get("corner_or_endpoint_hotspot_proxy"))
        far = morph.get("far_or_opposite_side_weak_return_proxy", "uncertain")
        discontinuous = yes(morph.get("discontinuous_edge_proxy"))
        enclosed = yes(morph.get("enclosed_shell_proxy"))
        block = yes(morph.get("block_like_body_proxy"))
        spread = yes(morph.get("range_spread_with_core_proxy"))
        scale = str(shell.get("gt_scale_compatible", "uncertain"))
        if side and corner:
            add_relation(out, case_id, "side_ridge_to_endpoint_hotspot", "side_ridge", "endpoint_hotspot", "endpoint_attached", scale, "yes", "", "Strong side strip is supported by endpoint/corner return.")
        if side:
            add_relation(out, case_id, "dominant_side_ridge_to_far_side_weak_return", "dominant_side_ridge", "far_side_weak_return", "opposite_side", scale, "uncertain" if far == "uncertain" else far, "" if far == "yes" else "far-side return not directly separable", "Dominant side can be stronger while the opposite side remains weak or ambiguous.")
        if corner and safe_int(shell.get("n_vehicle_parts")) >= 2:
            add_relation(out, case_id, "left_right_endpoint_relation", "endpoint_hotspot", "endpoint_or_corner_part", "aligned", scale, "yes", "", "Endpoint/corner parts can close the long-axis vehicle extent.")
        if discontinuous:
            add_relation(out, case_id, "upper_lower_edge_relation", "edge_fragment", "edge_fragment", "parallel", scale, "yes" if safe_int(shell.get("n_vehicle_parts")) >= 2 else "uncertain", "", "Discontinuous edge fragments may form a body outline when read at GT scale.")
            add_relation(out, case_id, "discontinuous_edge_to_shell_completion", "discontinuous_edge", "shell_completion", "enclosed" if enclosed else "disconnected", scale, "yes" if enclosed or scale == "yes" else "uncertain", "", "Broken edges can still complete a vehicle-scale shell hypothesis.")
        if side and block:
            add_relation(out, case_id, "strip_to_block_body", "side_ridge", "block_body", "parallel", scale, "yes", "", "Strip plus body block supports a physical body response.")
        if spread:
            add_relation(out, case_id, "range_spread_to_body_core", "range_spread", "body_core", "enclosed", scale, "uncertain", "range spread may be motion or environment induced", "Range spread must retain a core before it can support a vehicle shell.")
        if morph.get("scene") == "GM_RM011" or "near_field" in str(morph.get("confounders", "")):
            add_relation(out, case_id, "near_field_spread_to_strong_side_response", "near_field_spread", "strong_side_response", "aligned", scale, "uncertain", "near-field truncation or spread unresolved", "Near-field cases may show strong side responses without clean shell closure.")
        if not any(r["case_id"] == case_id for r in out[-8:]):
            add_relation(out, case_id, "no_clear_part_relation", "scattering_atom_or_part", "vehicle_shell", "uncertain", scale, "no", "parts do not form an interpretable relation", "Component count alone is insufficient for vehicle shell grammar.")
    return out


def build_failure_modes(
    shell_rows: Sequence[Mapping[str, Any]],
    morph_by_case: Mapping[str, Mapping[str, str]],
    support_by_case: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def push(case_id: str, mode: str, why: str, needed: str, review: str = "yes") -> None:
        out.append(
            {
                "case_id": case_id,
                "failure_mode": mode,
                "why_not_vehicle_shell": why,
                "what_evidence_would_be_needed": needed,
                "manual_review_needed": review,
                "not_allowed_conclusion": "not revised GT; not final box; not selector; not identity truth; not GT-guided runtime prediction logic",
            }
        )

    for shell in shell_rows:
        case_id = str(shell.get("case_id", ""))
        morph = morph_by_case.get(case_id, {})
        n_atoms = safe_int(shell.get("n_atoms"))
        n_parts = safe_int(shell.get("n_vehicle_parts"))
        n_shell = safe_int(shell.get("n_shell_parts"))
        if n_atoms > 0 and n_parts == 0 and n_shell == 0:
            push(case_id, "only_atoms_no_vehicle_scale", "Only local scattering atoms are available; atoms are not vehicles.", "GT-scale part composition or temporal persistence.")
        if n_parts == 1 and n_shell == 0:
            push(case_id, "single_part_no_shell", "A single part cannot close a vehicle-scale shell.", "Additional endpoint/edge/far-side relation at GT scale.")
        if shell.get("gt_scale_compatible") == "no" or shell.get("baby_car_risk") == "yes":
            push(case_id, "parts_too_small_baby_car", "Component scale is too small relative to GT vehicle scale.", "Vehicle-scale span or multiple parts matching GT dimensions.")
        if morph.get("vehicle_morphology_supported") == "uncertain" and safe_int(shell.get("n_vehicle_parts")) >= 2:
            push(case_id, "parts_too_scattered", "Parts exist but do not form a stable shell relation.", "Temporal drift consistency or clearer shell completion.")
        conf = morph.get("confounders", "")
        if "background_clutter" in conf:
            push(case_id, "background_line_not_vehicle_shell", "Background clutter can mimic a ridge or line.", "Moving vehicle-like drift rather than background-stable response.")
        if "guardrail" in conf or "road_edge" in conf:
            push(case_id, "guardrail_or_building_edge_confounder", "Road-side linear structures can mimic side ridges.", "Temporal movement with object, not fixed scene structure.")
        if "flowerbed" in conf:
            push(case_id, "flowerbed_or_background_blob", "Static background blob may mimic block body.", "Multi-frame drift and endpoint relation.")
        if "e-bike" in conf:
            push(case_id, "e-bike_or_small_object_pointlike_confounder", "Small nearby object may explain point-like returns.", "GT-scale shell plus object-motion compatibility.")
        label = str(shell.get("gt_quality_label", ""))
        if label == "review_too_large" or label == "review_multi_structure":
            push(case_id, "gt_too_loose_for_structure", "GT may include background or neighboring structures.", "Manual GT quality review before strong morphology conclusion.")
        if label == "review_too_small":
            push(case_id, "gt_too_small_for_structure", "GT may only cover a local high-energy part.", "Check whether vehicle-scale body extends outside GT.")
        if label in {"review_boundary", "review_extreme_aspect", "review_low_energy"}:
            push(case_id, "gt_boundary_affected", "GT quality or boundary effects weaken shell interpretation.", "Manual review and temporal context.")
        if morph.get("dominant_energy_pattern") == "weak_boundary":
            push(case_id, "near_field_spread_unresolved", "Weak boundary or spread is not enough to assert a shell.", "Persistent ridge/hotspot drift or clearer part relation.")
        if yes(morph.get("range_spread_with_core_proxy")) and shell.get("vehicle_shell_supported") != "yes":
            push(case_id, "range_spread_without_core", "Range spread alone can be environment or motion artifact.", "A body core plus edge/endpoints.")

    for case_id, support in support_by_case.items():
        if support.get("support_miss_vehicle_structure") == "yes":
            push(case_id, "support_miss_structure", "GT-anchored vehicle-scale structure is outside support.", "Support construction or motion-drift compatibility review; do not search only inside support.")
    for shell in shell_rows:
        if shell.get("pool_type") == "paired_215":
            continue
        case_id = str(shell.get("case_id", ""))
        push(
            case_id,
            "temporal_not_available",
            "This reference-pool row is not part of the paired temporal object-stream probe.",
            "Object-stream recovery or paired temporal review before temporal drift claims.",
            "no",
        )
    return out


def build_temporal(rows: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    by_case: dict[str, dict[str, str]] = {}
    for row in rows:
        if row.get("window_size") == "10":
            by_case[row.get("case_id", "")] = row
    out: list[dict[str, Any]] = []
    for case_id, row in sorted(by_case.items()):
        gradual = row.get("structure_changes_gradually", "uncertain")
        background = "yes" if yes(row.get("possible_background_stable_structure")) else "no"
        non_jump = "yes" if gradual == "yes" and background == "no" else ("uncertain" if gradual == "uncertain" else "no")
        vehicle_like = row.get("possible_vehicle_like_temporal_tube", "uncertain")
        out.append(
            {
                "case_id": case_id,
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "sar_frame": row.get("sar_frame", ""),
                "frame_offsets_used": row.get("frame_offsets_used", ""),
                "temporal_data_available": row.get("temporal_data_available", ""),
                "shell_available_in_frames": row.get("shell_structure_persistence", ""),
                "ridge_persistence": row.get("ridge_or_strip_persistence", ""),
                "hotspot_persistence": row.get("hotspot_drift_available", ""),
                "shell_centroid_drift_px": parse_total_drift(row.get("component_centroid_drift", "")),
                "shell_drift_direction": row.get("hotspot_drift_direction", ""),
                "shell_orientation_change": "unavailable",
                "structure_changes_gradually": gradual,
                "non_jump_constraint_supported": non_jump,
                "background_stable_risk": background,
                "compatible_with_optical_tracklet_motion": row.get("compatible_with_optical_tracklet_motion", "unavailable"),
                "vehicle_like_temporal_drift_supported": vehicle_like,
                "notes": "Existing probe provides -5..+5, not full -10/+10. Temporal drift is posthoc mechanism support, not identity truth.",
            }
        )
    return out


def normalize_support_failure(value: str) -> str:
    text = str(value)
    if "support_miss" in text or "azimuth_aligned_range_misaligned" in text:
        return "range_misaligned"
    if "reconstruction_uncertain" in text:
        return "support_reconstruction_uncertain"
    if "too_narrow" in text:
        return "too_narrow"
    if "too_broad" in text:
        return "too_broad"
    if "optical_truncation_induced_shift" in text:
        return "truncation_shift"
    if "near_field_truncation_issue" in text:
        return "near_field_issue"
    if "support_ok_but_not_exclusive" in text:
        return "support_ok_but_not_exclusive"
    if text.strip() == "none":
        return "none"
    return "uncertain"


def build_support_explanations(rows: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        miss = row.get("support_miss_vehicle_structure", "uncertain")
        covers_shell = row.get("vehicle_scale_morphology_inside_support", "uncertain")
        area = safe_float(row.get("support_gt_area_coverage"))
        energy = safe_float(row.get("support_gt_energy_coverage"))
        support_covers_parts_only = "yes" if miss == "yes" and max(area, energy) > 0 else ("uncertain" if miss == "uncertain" else "no")
        if miss == "yes":
            explanation = "GT-anchored vehicle shell is outside or only partly represented by support; diagnose support construction failure."
        elif covers_shell == "yes":
            explanation = "Support covers GT-scale shell, but this is still a feasible-region diagnostic, not association truth."
        else:
            explanation = "Support relation remains uncertain and needs physical/temporal review."
        out.append(
            {
                "case_id": row.get("case_id", ""),
                "scene": row.get("scene", ""),
                "sar_frame": row.get("sar_frame", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "gt_shell_supported": row.get("gt_vehicle_morphology_supported", "uncertain"),
                "support_available": row.get("support_available", ""),
                "support_covers_shell": covers_shell,
                "support_covers_parts_only": support_covers_parts_only,
                "support_miss_shell": miss,
                "support_failure_type": normalize_support_failure(row.get("support_failure_type", "")),
                "physical_explanation": explanation,
                "state_or_temporal_compensation_needed": "yes" if any(k in row.get("support_failure_type", "") for k in ["truncation", "uncertain", "miss", "narrow"]) else "uncertain",
                "not_allowed_conclusion": "not final box; not selector success; not identity truth; not GT-guided runtime prediction logic",
            }
        )
    return out


def weighted_fusion_deferred_rows() -> list[dict[str, str]]:
    common = "Physical shell grammar and temporal drift mechanism must be understood before evidence bookkeeping."
    future = "Allowed later only as fallback bookkeeping over already separated physical evidence; not current mainline."
    return [
        {
            "fusion_idea": "time + azimuth + state + energy weighted sum",
            "why_deferred": "It would collapse temporal, geometry, state, and SAR structure layers into one opaque number.",
            "physical_structure_needed_first": common,
            "risk_if_used_now": "Premature score optimization could hide support miss and baby-car failures.",
            "allowed_future_role": future,
        },
        {
            "fusion_idea": "support score",
            "why_deferred": "Support is an optical-derived feasible region, not a final box or association truth.",
            "physical_structure_needed_first": "Need to know whether GT-scale shell is inside support or support misses the shell.",
            "risk_if_used_now": "A small support-internal part could be promoted when the real shell is outside support.",
            "allowed_future_role": future,
        },
        {
            "fusion_idea": "shell score",
            "why_deferred": "Shell grammar must first distinguish atom, part, and vehicle-scale shell hypothesis.",
            "physical_structure_needed_first": "Need GT-scale compatibility, part relations, and failure modes.",
            "risk_if_used_now": "Score could call a small component a vehicle shell.",
            "allowed_future_role": future,
        },
        {
            "fusion_idea": "temporal score",
            "why_deferred": "Temporal drift is a non-jump mechanism, not identity truth or a selector target.",
            "physical_structure_needed_first": "Need ridge/hotspot/shell persistence and background-stable risk separation.",
            "risk_if_used_now": "Smooth background or repeated support error could be mistaken for vehicle identity.",
            "allowed_future_role": future,
        },
        {
            "fusion_idea": "negative-control separation score",
            "why_deferred": "Negative controls require stable physical failure labels first.",
            "physical_structure_needed_first": "Need only-atoms, background-line, support-miss, and GT-quality failure modes.",
            "risk_if_used_now": "The score may optimize against noisy failure labels instead of mechanism.",
            "allowed_future_role": future,
        },
    ]


def find_panel_source(case_id: str) -> Path | None:
    patterns = [
        f"*{case_id}*support_wide_temporal_structure_cn.png",
        f"*{case_id}*gt_support_energy_panel_cn.png",
        f"*{case_id}*structure_panel.png",
        f"*{case_id}*gt_quality_vehicle_scale_cn.png",
    ]
    for pattern in patterns:
        matches = sorted(VISUAL_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def generate_atlas(
    timestamp: str,
    shell_by_case: Mapping[str, Mapping[str, Any]],
    temporal_by_case: Mapping[str, Mapping[str, Any]],
    support_by_case: Mapping[str, Mapping[str, Any]],
    panel_notes: Sequence[Mapping[str, str]],
) -> tuple[Path, list[Path]]:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    selected: list[Mapping[str, str]] = list(panel_notes[:13])
    generated: list[Path] = []
    html_items: list[str] = []
    for idx, note in enumerate(selected, 1):
        case_id = note.get("case_id", "")
        source = find_panel_source(case_id)
        if source is None:
            continue
        out_path = VISUAL_DIR / f"{idx:02d}_{sanitize(case_id)}_physical_shell_grammar_temporal_cn.png"
        shell = shell_by_case.get(case_id, {})
        temporal = temporal_by_case.get(case_id, {})
        support = support_by_case.get(case_id, {})
        img = plt.imread(str(source))
        fig = plt.figure(figsize=(15, 7), dpi=120)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.4, 1.0])
        ax_img = fig.add_subplot(gs[0, 0])
        ax_text = fig.add_subplot(gs[0, 1])
        ax_img.imshow(img)
        ax_img.set_axis_off()
        ax_img.set_title(f"{idx:02d} {case_id}", fontsize=10)
        text = (
            "本图目的：不是做加权打分，而是检查 SAR 车辆结构是否能由部件组成车辆尺度外壳，"
            "并观察该外壳是否随时序平滑迁移。\n"
            "请重点看：侧边条带、端部热点、远侧弱回波、部件组合、GT 尺度兼容性、时序 non-jump。\n"
            "人工轮廓参考：用户手绘标记很粗糙，只作为 ridge / endpoint / shell completion 的视觉词汇参考，"
            "不是 revised GT 或 final box。\n"
            f"shell pattern: {shell.get('dominant_shell_pattern', 'panel-reference')}\n"
            f"shell supported: {shell.get('vehicle_shell_supported', 'see panel')}; baby-car risk: {shell.get('baby_car_risk', 'n/a')}\n"
            f"temporal drift: {temporal.get('vehicle_like_temporal_drift_supported', 'reference-only')}; non-jump: {temporal.get('non_jump_constraint_supported', 'reference-only')}\n"
            f"support miss shell: {support.get('support_miss_shell', 'reference-only')}\n"
            "如果只是小亮点或小组件，只能叫 atom 或 part，不能叫车。"
            "如果 shell 不在 support 内，应记录 support 构造失败，而不是在 support 内继续找车。\n"
            "不能记录：revised GT、final box、selector success、identity truth。"
        )
        ax_text.set_axis_off()
        ax_text.text(
            0.02,
            0.98,
            wrap_zh(text, 33),
            va="top",
            ha="left",
            fontsize=10,
            fontproperties=FONT,
            linespacing=1.35,
        )
        fig.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        generated.append(out_path)
        html_items.append(
            f"<section><h2>{idx:02d} {html.escape(case_id)}</h2>"
            f"<p>Physical shell grammar and temporal drift review; human contour reference only.</p>"
            f"<img src=\"{html.escape(out_path.name)}\" style=\"max-width:100%;border:1px solid #ccc\"></section>"
        )
    atlas = VISUAL_DIR / f"oty2_physical_shell_grammar_temporal_drift_atlas_cn_{timestamp}.html"
    atlas.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>OTY2 physical shell grammar temporal drift atlas</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.5}section{margin-bottom:32px}</style></head><body>"
        "<h1>OTY2 Physical Shell Grammar And Temporal Drift Atlas</h1>"
        "<p>Human contour markings are rough reference only. This atlas is posthoc mechanism explanation, not weighted scoring, revised GT, final box, selector, or identity truth.</p>"
        + "\n".join(html_items)
        + "</body></html>",
        encoding="utf-8",
    )
    return atlas, generated


def write_docs(timestamp: str, summary: Mapping[str, Any], outputs: Mapping[str, str]) -> Path:
    report_path = REPORT_DIR / f"oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_report_{timestamp}.md"
    km = summary["key_metrics"]
    report = f"""# OTY2 Physical SAR Vehicle Shell Grammar And Temporal Drift Report

Generated: `{timestamp}`

This report expresses SAR vehicle evidence as physical structure grammar plus temporal drift mechanism. It is posthoc diagnosis only: no revised GT, final box, annotation proposal, selector/ranking, training, threshold tuning, best weight, weighted-fusion mainline, or identity truth is produced.

## Ledger Boundary

- 442 = all SAR GT / SAR-side target reference pool
- 215 = current OTY optical-object to SAR-GT frame-level paired pool
- 195 = GM_RM011 blocked_missing_object_stream, not unannotated
- 20 = SAR-only GT, SAR morphology reference only
- 12 = dropout/no_oty_iou_match/temporal continuation special pool

## Why This Is Physical-Structure-First, Not Weighted Fusion

1. This run does no weighted score and no selector.
2. It explains vehicle evidence through `scattering_atom`, `vehicle_part`, and `vehicle_scale_shell_hypothesis`, not through a weighted sum.
3. GT width, height, area, and long/short axes are used as posthoc scale anchors to prevent baby-car promotion.
4. Temporal drift is checked as non-jump / gradual motion, not identity truth.
5. Support miss is explained after GT-anchored shell evidence is described; wrong support is not rescued by support-internal search.
6. Manual review remains required for GT quality uncertainty, weak structures, confounders, support miss, and temporal unavailable cases.
7. Future weighted fusion is allowed only as fallback bookkeeping after physical grammar and temporal drift are understood.

## Vehicle Shell Grammar

- shell case rows: `{km['vehicle_shell_grammar_rows']}`
- dominant shell pattern mix: `{km['dominant_shell_pattern_mix']}`
- vehicle shell supported mix: `{km['vehicle_shell_supported_mix']}`
- GT scale compatible mix: `{km['gt_scale_compatible_mix']}`
- baby-car risk rows: `{km['baby_car_risk_rows']}`

Shell grammar reads side ridges, endpoint hotspots, far-side weak returns, discontinuous edges, block/core responses, and GT-scale shell completion as physical relationships. A small peak remains a scattering atom.

## Part Grammar Relations

- relation rows: `{km['part_relation_rows']}`
- relation type mix: `{km['part_relation_type_mix']}`
- relation support mix: `{km['part_relation_support_mix']}`

The strongest human-readable relations are side ridge to endpoint hotspot, discontinuous edge to shell completion, dominant side ridge to weak far-side return, and range spread to body core.

## Physical Structure Failure Modes

- failure rows: `{km['physical_failure_rows']}`
- failure mode mix: `{km['failure_mode_mix']}`

Failures are explicit: only atoms, single part without shell, parts too small, scattered parts, GT quality uncertainty, support miss, background/road confounders, near-field spread unresolved, or temporal unavailable.

## Temporal Drift Physical Consistency

- temporal rows: `{km['temporal_rows']}`
- vehicle-like temporal drift mix: `{km['vehicle_like_temporal_drift_mix']}`
- non-jump support mix: `{km['non_jump_constraint_mix']}`
- background-stable risk mix: `{km['background_stable_risk_mix']}`

The available temporal probe uses `-5..+5` offsets. Full `-10/+10` is not available in this artifact and is recorded as a limitation. Temporal drift remains a posthoc mechanism signal, not identity truth.

## Support Failure Physical Explanation

- support explanation rows: `{km['support_explanation_rows']}`
- support miss shell mix: `{km['support_miss_shell_mix']}`
- support failure type mix: `{km['support_failure_type_mix']}`

**If GT-anchored vehicle shell is outside support, the correct diagnostic is support construction failure, not support-internal vehicle search.**

## Weighted Fusion Deferred Boundary

- deferred rows: `{km['weighted_fusion_deferred_rows']}`

Conclusion: weighted fusion is deferred. It can only be a bookkeeping / fallback evidence layer after physical shell grammar and temporal drift mechanism are understood.

## Manual Contour Reference

The rough 2026-07-04 human contour markings are used as visual vocabulary only. They reinforce long side ridges, endpoint hotspots, weak far-side returns, and discontinuous shell completion. They are not GT edits, not final boxes, not selector labels, and not identity truth. The temporary marked PNG files are not committed.

## Corrected Or Paused Old Conclusions

- Weighted evidence fusion as a mainline is paused.
- Top-k peak or small component reasoning is kept at scattering atom / vehicle part level.
- Support-internal search is paused when GT-scale shell is outside support.
- Temporal drift supports physical consistency but not identity truth.

## Posthoc Hypotheses Only

- shell grammar labels are posthoc hypotheses
- part relations are posthoc physical explanations
- temporal drift labels are posthoc mechanism support
- support failure labels are support-construction diagnostics
- weighted fusion rows are deferred-boundary bookkeeping only

## Outputs

""" + "\n".join(f"- {k}: `{v}`" for k, v in outputs.items()) + "\n\n## Boundary Flags\n\n" + "\n".join(
        f"- {k}: `{str(v).lower()}`" for k, v in BOUNDARY_FLAGS.items()
    ) + "\n"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    timestamp = args.timestamp
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_{timestamp}.log"
    log_path.write_text(
        f"timestamp={timestamp}\n"
        "task=oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift\n"
        "phase=before_run\n"
        r"interpreter=D:\MINICONDA\envs\py311\python.exe" + "\n"
        "old_work_dependency=false\narchive_directory_active_source=false\n",
        encoding="utf-8",
    )

    scale_rows = read_csv(GT_SCALE_CSV)
    quality_rows = read_csv(GT_QUALITY_CSV)
    morph_rows = read_csv(GT_MORPH_CSV)
    hierarchy_rows = read_csv(HIERARCHY_CSV)
    support_rows = read_csv(SUPPORT_MISS_CSV)
    temporal_rows = read_csv(TEMPORAL_CSV)
    panel_notes = read_csv(PANEL_NOTES_CSV)
    _ = read_csv(SUPPORT_WIDE_PROXY_CSV)
    _ = read_csv(ATOM_COMPONENT_CSV)

    scale_by_key = {case_gt_key(r): r for r in scale_rows}
    quality_by_key = {case_gt_key(r): r for r in quality_rows}
    hierarchy_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in hierarchy_rows:
        hierarchy_by_case[row.get("case_id", "")].append(row)
    morph_by_case = {row.get("case_id", ""): row for row in morph_rows}
    support_by_case = {row.get("case_id", ""): row for row in support_rows}

    shell_cases = build_shell_cases(morph_rows, hierarchy_by_case, scale_by_key, quality_by_key)
    shell_by_case = {row["case_id"]: row for row in shell_cases}
    part_relations = build_part_relations(shell_cases, morph_by_case)
    failure_modes = build_failure_modes(shell_cases, morph_by_case, support_by_case)
    temporal_consistency = build_temporal(temporal_rows)
    temporal_by_case = {row["case_id"]: row for row in temporal_consistency}
    support_explanations = build_support_explanations(support_rows)
    support_expl_by_case = {row["case_id"]: row for row in support_explanations}
    fusion_rows = weighted_fusion_deferred_rows()
    atlas_path, atlas_panels = generate_atlas(timestamp, shell_by_case, temporal_by_case, support_expl_by_case, panel_notes)

    outputs = {
        "plan_doc": str(DOCS_DIR / "oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_plan.md"),
        "physical_structure_first_archive_doc": str(DOCS_DIR / "oty2_physical_structure_first_not_weighted_fusion_archive.md"),
        "vehicle_shell_grammar_cases_csv": str(REPORT_DIR / f"oty2_vehicle_shell_grammar_cases_{timestamp}.csv"),
        "vehicle_part_grammar_relations_csv": str(REPORT_DIR / f"oty2_vehicle_part_grammar_relations_{timestamp}.csv"),
        "physical_structure_failure_modes_csv": str(REPORT_DIR / f"oty2_physical_structure_failure_modes_{timestamp}.csv"),
        "temporal_drift_physical_consistency_csv": str(REPORT_DIR / f"oty2_temporal_drift_physical_consistency_{timestamp}.csv"),
        "support_failure_physical_explanation_csv": str(REPORT_DIR / f"oty2_support_failure_physical_explanation_{timestamp}.csv"),
        "weighted_fusion_deferred_boundary_csv": str(REPORT_DIR / f"oty2_weighted_fusion_deferred_boundary_{timestamp}.csv"),
        "summary_json": str(REPORT_DIR / f"oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_summary_{timestamp}.json"),
        "visual_atlas_html": str(atlas_path),
        "workspace_log": str(log_path),
    }
    write_csv(Path(outputs["vehicle_shell_grammar_cases_csv"]), SHELL_FIELDS, shell_cases)
    write_csv(Path(outputs["vehicle_part_grammar_relations_csv"]), RELATION_FIELDS, part_relations)
    write_csv(Path(outputs["physical_structure_failure_modes_csv"]), FAILURE_FIELDS, failure_modes)
    write_csv(Path(outputs["temporal_drift_physical_consistency_csv"]), TEMPORAL_FIELDS, temporal_consistency)
    write_csv(Path(outputs["support_failure_physical_explanation_csv"]), SUPPORT_EXPLANATION_FIELDS, support_explanations)
    write_csv(Path(outputs["weighted_fusion_deferred_boundary_csv"]), FUSION_FIELDS, fusion_rows)

    key_metrics = {
        "vehicle_shell_grammar_rows": len(shell_cases),
        "dominant_shell_pattern_mix": compact_counts([r["dominant_shell_pattern"] for r in shell_cases]),
        "vehicle_shell_supported_mix": compact_counts([r["vehicle_shell_supported"] for r in shell_cases]),
        "gt_scale_compatible_mix": compact_counts([r["gt_scale_compatible"] for r in shell_cases]),
        "baby_car_risk_rows": sum(1 for r in shell_cases if r["baby_car_risk"] == "yes"),
        "part_relation_rows": len(part_relations),
        "part_relation_type_mix": compact_counts([r["part_relation_type"] for r in part_relations]),
        "part_relation_support_mix": compact_counts([r["supports_shell_grammar"] for r in part_relations]),
        "physical_failure_rows": len(failure_modes),
        "failure_mode_mix": compact_counts([r["failure_mode"] for r in failure_modes]),
        "temporal_rows": len(temporal_consistency),
        "vehicle_like_temporal_drift_mix": compact_counts([r["vehicle_like_temporal_drift_supported"] for r in temporal_consistency]),
        "non_jump_constraint_mix": compact_counts([r["non_jump_constraint_supported"] for r in temporal_consistency]),
        "background_stable_risk_mix": compact_counts([r["background_stable_risk"] for r in temporal_consistency]),
        "support_explanation_rows": len(support_explanations),
        "support_miss_shell_mix": compact_counts([r["support_miss_shell"] for r in support_explanations]),
        "support_failure_type_mix": compact_counts([r["support_failure_type"] for r in support_explanations]),
        "weighted_fusion_deferred_rows": len(fusion_rows),
        "atlas_panels_generated": len(atlas_panels),
        "human_contour_reference_panels_visible_in_prompt": 9,
        "human_contour_reference_files_committed": False,
    }
    summary = {
        "timestamp": timestamp,
        "sample_ledger": {
            "all_sar_gt_reference_pool": 442,
            "paired_optical_object_sar_gt": 215,
            "gm011_blocked_missing_object_stream": 195,
            "sar_only_gt": 20,
            "dropout_no_oty_iou_match_temporal_continuation": 12,
        },
        "row_counts": {
            "vehicle_shell_grammar_cases": len(shell_cases),
            "vehicle_part_grammar_relations": len(part_relations),
            "physical_structure_failure_modes": len(failure_modes),
            "temporal_drift_physical_consistency": len(temporal_consistency),
            "support_failure_physical_explanation": len(support_explanations),
            "weighted_fusion_deferred_boundary": len(fusion_rows),
        },
        "key_metrics": key_metrics,
        "weighted_fusion_deferred_boundary": "weighted fusion is deferred; it can only be bookkeeping/fallback after physical shell grammar and temporal drift are understood",
        "corrected_or_paused_old_conclusions": [
            "Weighted evidence fusion is paused as a mainline.",
            "Top-k peaks remain scattering atoms unless part-to-shell grammar reaches GT vehicle scale.",
            "Support-internal search is paused when GT-anchored shell is outside support.",
            "Temporal drift is mechanism support, not identity truth.",
        ],
        "posthoc_hypotheses_only": [
            "vehicle shell grammar labels",
            "part relation diagnostics",
            "temporal drift consistency labels",
            "support failure physical explanations",
            "human contour reference language",
        ],
        "manual_contour_reference_boundary": {
            "source": "9 rough inline images provided by user on 2026-07-04; temp files not accessible at runtime",
            "used_as": "non-authoritative visual vocabulary for ridge/endpoint/weak-side/shell-completion interpretation",
            "not_used_as": "GT edit, revised annotation, final box, selector label, identity truth, runtime prior",
        },
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "atlas_panels": [str(p) for p in atlas_panels],
        "sources": {
            "gt_scale_csv": str(GT_SCALE_CSV),
            "gt_quality_csv": str(GT_QUALITY_CSV),
            "gt_morphology_csv": str(GT_MORPH_CSV),
            "hierarchy_csv": str(HIERARCHY_CSV),
            "support_miss_csv": str(SUPPORT_MISS_CSV),
            "temporal_csv": str(TEMPORAL_CSV),
            "panel_notes_csv": str(PANEL_NOTES_CSV),
        },
    }
    report_path = write_docs(timestamp, summary, outputs)
    outputs["report_md"] = str(report_path)
    summary["outputs"] = outputs
    write_json(Path(outputs["summary_json"]), summary)
    log_path.write_text(
        log_path.read_text(encoding="utf-8")
        + "phase=after_run\n"
        + "repo_outputs_written=true\n"
        + "key_metrics="
        + json.dumps(key_metrics, ensure_ascii=False)
        + "\n"
        + "boundary_flags="
        + json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)
        + "\n"
        + "outputs="
        + json.dumps(outputs, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"timestamp": timestamp, "key_metrics": key_metrics, "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
