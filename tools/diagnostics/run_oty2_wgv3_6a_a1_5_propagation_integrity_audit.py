"""WGV3.6A-A1.5 independent propagation-integrity audit.

This script audits the already committed WGV3.6A outputs. It does not modify
the propagation mechanism, does not create final SAR boxes, and does not run
GM_RM011.
"""

from __future__ import annotations

import csv
import math
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from run_oty2_wgv3_6a_sparse_anchor_response_propagation import (  # noqa: E402
    INPUTS as WGV36_INPUTS,
    OUTPUTS as WGV36_OUTPUTS,
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
    SAR_HEIGHT,
    SAR_WIDTH,
    Box,
    box_from_pair,
    box_from_text,
    build_geometry,
    draw_fan_boundary,
    fmt,
    image_with_box,
    mask_intersection_ratio,
    parse_float,
    parse_int,
    sar_gray_path,
)


DATE = "20260711"
START_COMMIT = "022884893cef913c66f187c05bc05c17093fc2d5"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_5_20260711"

INPUT_CONTEXT = {
    "center_semantic": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_center_semantic_review_20260711.csv",
    "mask_source": SAMPLES_DIR / "oty2_wgv3_5a_r2c_sar_mask_source_inventory_20260711.csv",
    "identity_r2_md": REPORT_DIR / "oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_20260710.md",
    "identity_r1_md": REPORT_DIR / "oty2_wgv3_5a_r1_physical_vehicle_identity_audit_20260710.md",
}

OUTPUTS = {
    "source_role_ledger": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_source_role_ledger_{DATE}.csv",
    "variant_definition": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_variant_definition_audit_{DATE}.csv",
    "unique_frame_accounting": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_unique_frame_accounting_{DATE}.csv",
    "metric_recompute": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_metric_recompute_{DATE}.csv",
    "closure_reaudit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_closure_reaudit_{DATE}.csv",
    "variant_diagnostics": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_variant_difference_diagnostics_{DATE}.csv",
    "visual_index": SAMPLES_DIR / f"oty2_wgv3_6a_a1_5_visual_audit_index_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_5_propagation_integrity_audit_{DATE}.md",
}

SOURCE_LEDGER_FIELDS = [
    "source_file",
    "field_name",
    "semantic_meaning",
    "used_in_anchor_audit",
    "used_in_anchor_initialization",
    "used_in_propagation_runtime",
    "used_in_stop_rule",
    "used_in_response_extraction",
    "used_in_metric_evaluation",
    "runtime_or_eval_only",
    "first_code_location",
    "notes",
]

VARIANT_FIELDS = [
    "variant",
    "initial_region_source",
    "optical_motion_used",
    "relative_depth_used",
    "sar_image_used",
    "sar_response_extractor",
    "region_center_update",
    "region_size_update",
    "mask_used",
    "mask_trigger_condition",
    "target_frame_manual_box_read_before_output",
    "future_anchor_read_before_output",
    "actual_changed_row_count_vs_previous",
    "notes",
]

UNIQUE_FIELDS = [
    "physical_vehicle_id",
    "sar_frame_id",
    "optical_frame_id",
    "anchor_interval_id",
    "direction",
    "is_left_anchor",
    "is_right_anchor",
    "is_any_anchor",
    "is_non_anchor_middle_frame",
    "number_of_forward_records",
    "number_of_backward_records",
    "number_of_variants",
    "included_in_original_metric",
    "included_in_recomputed_metric",
]

METRIC_FIELDS = [
    "metric_name",
    "value",
    "denominator_count",
    "denominator_type",
    "status",
    "notes",
]

CLOSURE_FIELDS = [
    "interval_id",
    "physical_vehicle_id",
    "left_anchor",
    "right_anchor",
    "gap_length",
    "forward_region_area",
    "backward_region_area",
    "region_intersection_area",
    "region_iou",
    "region_center_distance",
    "forward_response_centroid",
    "backward_response_centroid",
    "response_centroid_distance",
    "same_connected_response_supported",
    "manual_target_used_in_closure_decision",
    "original_closure_label",
    "reaudited_closure_level",
    "reaudit_reason",
]

DIAG_FIELDS = [
    "comparison",
    "physical_vehicle_id",
    "interval_id",
    "direction",
    "sar_frame",
    "previous_region",
    "current_region",
    "center_shift_px",
    "area_delta",
    "visible_response_coverage_previous",
    "visible_response_coverage_current",
    "category",
    "notes",
]

VISUAL_INDEX_FIELDS = [
    "visual_id",
    "category",
    "source_comparison",
    "physical_vehicle_id",
    "interval_id",
    "sar_frame",
    "ignored_png_path",
    "notes",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def num(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if math.isnan(value):
        return "not_tested"
    return fmt(float(value))


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return "| " + " | ".join(fields) + " |\n| " + " | ".join("---" for _ in fields) + " |"
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")).replace("\n", " ") for field in fields) + " |")
    return "\n".join(out)


def git_output(args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()


def box_area(box: Box | None) -> float:
    return box.area if box else math.nan


def box_intersection_area(a: Box | None, b: Box | None) -> float:
    if not a or not b:
        return 0.0
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def box_iou(a: Box | None, b: Box | None) -> float:
    if not a or not b:
        return 0.0
    inter = box_intersection_area(a, b)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def center_distance(a: Box | None, b: Box | None) -> float:
    if not a or not b:
        return math.nan
    return math.hypot(a.cx - b.cx, a.cy - b.cy)


def box_from_row(row: Mapping[str, Any], field: str = "propagated_region") -> Box | None:
    text = str(row.get(field, ""))
    if not text:
        return None
    return box_from_text(text)


def boxes_differ(a: Box | None, b: Box | None, eps: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is not b
    return any(abs(x - y) > eps for x, y in [(a.x1, b.x1), (a.y1, b.y1), (a.x2, b.x2), (a.y2, b.y2)])


def centroid_text(row: Mapping[str, Any] | None) -> str:
    if not row:
        return ""
    return str(row.get("local_response_center", ""))


def point_distance(text_a: str, text_b: str) -> float:
    try:
        ax, ay = [float(v) for v in text_a.split(",")[:2]]
        bx, by = [float(v) for v in text_b.split(",")[:2]]
    except Exception:
        return math.nan
    return math.hypot(ax - bx, ay - by)


def row_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["interval_id"]), str(row["direction"]), str(row["sar_frame"]))


def index_by_key(rows: Iterable[Mapping[str, Any]], method: str, direction: str | None = None) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    out: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        if row.get("method") != method:
            continue
        if direction and row.get("direction") != direction:
            continue
        out[row_key(row)] = row
    return out


def load_all() -> dict[str, Any]:
    anchor_rows = read_rows(WGV36_OUTPUTS["anchor_audit"])
    prop_rows = read_rows(WGV36_OUTPUTS["propagation_manifest"])
    bidi_rows = read_rows(WGV36_OUTPUTS["bidirectional"])
    paired = [row for row in read_rows(WGV36_INPUTS["paired"]) if row.get("scene") == "GM_RM019"]
    mask_rows = read_rows(WGV36_INPUTS["mask_audit"])
    optical_rows = read_rows(WGV36_INPUTS["optical_review"])
    branch_b = read_rows(WGV36_INPUTS["branch_b"])
    projection_eval = read_rows(WGV36_INPUTS["projection_eval"])
    center_semantic = read_rows(INPUT_CONTEXT["center_semantic"])
    mask_source = read_rows(INPUT_CONTEXT["mask_source"])
    return {
        "anchor_rows": anchor_rows,
        "prop_rows": prop_rows,
        "bidi_rows": bidi_rows,
        "paired": paired,
        "mask_rows": mask_rows,
        "optical_rows": optical_rows,
        "branch_b": branch_b,
        "projection_eval": projection_eval,
        "center_semantic": center_semantic,
        "mask_source": mask_source,
    }


def make_pair_index(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    anchors = {row["pair_id"]: row for row in data["anchor_rows"]}
    out: dict[str, dict[str, Any]] = {}
    for pair in data["paired"]:
        row = dict(pair)
        anchor = anchors.get(row["pair_id"], {})
        if anchor:
            row["physical_vehicle_id"] = anchor.get("physical_vehicle_id", "")
        out[row["pair_id"]] = row
    return out


def field_role(source_file: str, field: str) -> dict[str, str]:
    role = {
        "semantic_meaning": field.replace("_", " ") if field else "document context",
        "used_in_anchor_audit": "false",
        "used_in_anchor_initialization": "false",
        "used_in_propagation_runtime": "false",
        "used_in_stop_rule": "false",
        "used_in_response_extraction": "false",
        "used_in_metric_evaluation": "false",
        "runtime_or_eval_only": "not_used",
        "first_code_location": "",
        "notes": "",
    }
    if source_file.endswith(".md"):
        role.update(
            {
                "runtime_or_eval_only": "docs_context",
                "first_code_location": "FREEZE_FILES:70-84",
                "notes": "Read/frozen as context; no dataframe field enters propagation.",
            }
        )
        return role

    if "paired_annotations" in source_file:
        if field == "scene":
            role.update({"used_in_anchor_audit": "true", "runtime_or_eval_only": "anchor_pool_filter", "first_code_location": "load_context:251"})
        elif field in {"pair_id", "optical_frame", "sar_frame"}:
            role.update(
                {
                    "used_in_anchor_audit": "true",
                    "used_in_anchor_initialization": "true",
                    "used_in_propagation_runtime": "true",
                    "runtime_or_eval_only": "runtime_identifier",
                    "first_code_location": "load_context:251; build_intervals:481-490; propagate_interval:525-540",
                }
            )
        elif field.startswith("sar_bbox_"):
            role.update(
                {
                    "used_in_anchor_audit": "true",
                    "used_in_anchor_initialization": "true",
                    "used_in_propagation_runtime": "true",
                    "used_in_metric_evaluation": "true",
                    "runtime_or_eval_only": "anchor_prior_and_future_endpoint",
                    "first_code_location": "pair_box:285-286; propagate_interval:529-530; method_region:496-508; coverage:545-548",
                    "notes": "Manual SAR bbox is used as both source anchor and target endpoint before P1/P2/P3 output; this is known-endpoint interpolation, not independent extrapolation.",
                }
            )
        elif field.startswith("optical_bbox_"):
            role.update({"used_in_anchor_audit": "true", "runtime_or_eval_only": "visualization_only", "first_code_location": "optical_box:289-290; render_anchor_contact:768-775"})
        elif field in {"sar_gt_id", "correspondence_match_iou", "vehicle_research_eligibility", "visibility_state"}:
            role.update({"runtime_or_eval_only": "loaded_not_used_by_wgv36", "notes": "Available in paired CSV but not read by WGV3.6A propagation path."})
        return role

    if "mask_observation_audit" in source_file:
        if field in {"pair_id", "physical_vehicle_id"}:
            role.update({"used_in_anchor_audit": "true", "runtime_or_eval_only": "join_or_fallback_identifier", "first_code_location": "load_context:252; load_context:265"})
        elif field == "sar_mask_observation_class":
            role.update(
                {
                    "used_in_anchor_audit": "true",
                    "used_in_stop_rule": "true",
                    "runtime_or_eval_only": "anchor_gate_eval_class",
                    "first_code_location": "anchor_status:398-415",
                    "notes": "Evaluation/review mask class gates anchor status; it is not a pixel response region.",
                }
            )
        elif field in {"usable_for_center_supervision", "usable_for_interval_supervision", "usable_for_masked_overlap_evaluation"}:
            role.update({"runtime_or_eval_only": "available_eval_flag_not_consumed", "notes": "Present in source but WGV3.6A does not branch on this field."})
        return role

    if "optical_state_review" in source_file:
        if field in {"physical_vehicle_id", "optical_state_review_class", "identity_confidence", "allowed_for_sar_mapping_audit"}:
            role.update(
                {
                    "used_in_anchor_audit": "true",
                    "used_in_stop_rule": "true",
                    "runtime_or_eval_only": "manual_identity_anchor_gate",
                    "first_code_location": "load_context:253; anchor_status:398-415",
                    "notes": "Manual optical identity/review decision gates which anchors may propagate.",
                }
            )
        return role

    if "anchorless_track_reconstruction" in source_file:
        if field in {"physical_vehicle_id", "frame"}:
            role.update({"used_in_anchor_audit": "true", "runtime_or_eval_only": "loaded_unused_timeline", "first_code_location": "load_context:267-271", "notes": "timeline_by_pv is built but not used later by WGV3.6A."})
        else:
            role.update({"runtime_or_eval_only": "loaded_unused_timeline", "first_code_location": "load_context:254; load_context:267-271"})
        return role

    if "projection_evaluation_rows" in source_file:
        if field in {"pair_id", "physical_vehicle_id"}:
            role.update(
                {
                    "used_in_anchor_audit": "true",
                    "used_in_anchor_initialization": "true",
                    "used_in_propagation_runtime": "true",
                    "runtime_or_eval_only": "identity_join",
                    "first_code_location": "load_context:257-265",
                    "notes": "Physical vehicle id is copied onto paired rows and then groups intervals.",
                }
            )
        elif field == "method":
            role.update({"used_in_anchor_audit": "true", "runtime_or_eval_only": "unused_eval_index", "first_code_location": "load_context:258-262", "notes": "eval_by_pair_method is populated but not consumed later."})
        return role

    if "center_semantic_review" in source_file:
        role.update({"used_in_metric_evaluation": "true", "runtime_or_eval_only": "a1_5_eval_context_only", "first_code_location": "A1.5 load_all", "notes": "Latest center-semantics review used only by this audit report, not by WGV3.6A generation."})
        return role

    if "propagation_manifest" in source_file or "bidirectional_closure" in source_file or "anchor_audit" in source_file:
        role.update({"used_in_metric_evaluation": "true", "runtime_or_eval_only": "a1_5_output_audit", "first_code_location": "A1.5 load_all", "notes": "Already frozen WGV3.6A output, read for independent recount only."})
        return role

    if "sar_mask_source_inventory" in source_file:
        role.update({"used_in_metric_evaluation": "true", "runtime_or_eval_only": "denominator_audit_context", "first_code_location": "A1.5 search denominator audit"})
        return role

    return role


def build_source_role_ledger(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    csv_sources = [
        WGV36_INPUTS["paired"],
        WGV36_INPUTS["mask_audit"],
        WGV36_INPUTS["optical_review"],
        WGV36_INPUTS["branch_b"],
        WGV36_INPUTS["projection_eval"],
        INPUT_CONTEXT["center_semantic"],
        INPUT_CONTEXT["mask_source"],
        WGV36_OUTPUTS["anchor_audit"],
        WGV36_OUTPUTS["propagation_manifest"],
        WGV36_OUTPUTS["bidirectional"],
    ]
    for path in csv_sources:
        source_file = rel(path)
        source_rows = read_rows(path)
        fields = list(source_rows[0].keys()) if source_rows else []
        for field in fields:
            role = field_role(source_file, field)
            rows.append({"source_file": source_file, "field_name": field, **role})

    doc_sources = [
        Path("docs/OTY2_SESSION_START_HERE.md"),
        Path("docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md"),
        Path("docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md"),
        Path("docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md"),
        INPUT_CONTEXT["identity_r2_md"],
        INPUT_CONTEXT["identity_r1_md"],
        REPORT_DIR / "oty2_wgv3_6a_gm019_closure_20260711.md",
    ]
    for path in doc_sources:
        source_file = rel(path if path.is_absolute() else REPO_ROOT / path)
        role = field_role(source_file, "document")
        rows.append({"source_file": source_file, "field_name": "document", **role})

    rows.append(
        {
            "source_file": rel(Path("tools/diagnostics/run_oty2_wgv3_6a_sparse_anchor_response_propagation.py")),
            "field_name": "target_box",
            "semantic_meaning": "target endpoint manual SAR bbox loaded before P1/P2/P3 output",
            "used_in_anchor_audit": "false",
            "used_in_anchor_initialization": "false",
            "used_in_propagation_runtime": "true",
            "used_in_stop_rule": "false",
            "used_in_response_extraction": "false",
            "used_in_metric_evaluation": "true",
            "runtime_or_eval_only": "known_endpoint_runtime",
            "first_code_location": "propagate_interval:529-548",
            "notes": "This is the key A1.5 leakage/role finding: the future anchor box is read before region generation.",
        }
    )
    return rows


def build_variant_definitions(prop_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    p0 = index_by_key(prop_rows, "P0", "forward")
    p1 = index_by_key(prop_rows, "P1", "forward")
    p2 = index_by_key(prop_rows, "P2", "forward")
    p3 = index_by_key(prop_rows, "P3", "forward")
    p1_changed = sum(1 for key, row in p1.items() if boxes_differ(box_from_row(row), box_from_row(p0.get(key, {}))))
    p2_changed = sum(1 for key, row in p2.items() if boxes_differ(box_from_row(row), box_from_row(p1.get(key, {}))))
    p3_changed = sum(1 for key, row in p3.items() if key in p2 and boxes_differ(box_from_row(row), box_from_row(p2[key])))
    p3_mask_triggers = sum(1 for row in p3.values() if "mask_boundary_adjusted" in str(row.get("stop_reason", "")))

    diagnostics: list[dict[str, Any]] = []
    for key, current in p2.items():
        previous = p1.get(key)
        if not previous:
            continue
        prev_box = box_from_row(previous)
        cur_box = box_from_row(current)
        if not boxes_differ(prev_box, cur_box) and previous.get("visible_response_coverage") == current.get("visible_response_coverage"):
            continue
        shift = center_distance(prev_box, cur_box)
        area_delta = box_area(cur_box) - box_area(prev_box)
        prev_cov = parse_float(previous.get("visible_response_coverage", ""), math.nan)
        cur_cov = parse_float(current.get("visible_response_coverage", ""), math.nan)
        if not math.isnan(prev_cov) and not math.isnan(cur_cov):
            if cur_cov > prev_cov + 1e-6:
                category = "P2_improves_coverage"
            elif cur_cov < prev_cov - 1e-6:
                category = "P2_hurts_coverage"
            elif area_delta < -1e-6:
                category = "P2_reduces_area_without_hurting"
            else:
                category = "P2_moves_to_stronger_response"
        elif "local_connected_response" in str(current.get("stop_reason", "")) and shift > 1.0:
            category = "P2_moves_to_stronger_response"
        else:
            category = "P2_moves_to_wrong_or_unverified_response"
        diagnostics.append(
            {
                "comparison": "P1_to_P2",
                "physical_vehicle_id": current.get("physical_vehicle_id", ""),
                "interval_id": current.get("interval_id", ""),
                "direction": current.get("direction", ""),
                "sar_frame": current.get("sar_frame", ""),
                "previous_region": previous.get("propagated_region", ""),
                "current_region": current.get("propagated_region", ""),
                "center_shift_px": num(shift),
                "area_delta": num(area_delta),
                "visible_response_coverage_previous": previous.get("visible_response_coverage", ""),
                "visible_response_coverage_current": current.get("visible_response_coverage", ""),
                "category": category,
                "notes": "P2 changes center using local SAR response; non-target middle frames have no independent eval box.",
            }
        )

    for key, current in p3.items():
        previous = p2.get(key)
        if not previous:
            continue
        prev_box = box_from_row(previous)
        cur_box = box_from_row(current)
        changed = boxes_differ(prev_box, cur_box) or previous.get("stop_reason", "") != current.get("stop_reason", "")
        diagnostics.append(
            {
                "comparison": "P2_to_P3",
                "physical_vehicle_id": current.get("physical_vehicle_id", ""),
                "interval_id": current.get("interval_id", ""),
                "direction": current.get("direction", ""),
                "sar_frame": current.get("sar_frame", ""),
                "previous_region": previous.get("propagated_region", ""),
                "current_region": current.get("propagated_region", ""),
                "center_shift_px": num(center_distance(prev_box, cur_box)),
                "area_delta": num(box_area(cur_box) - box_area(prev_box)),
                "visible_response_coverage_previous": previous.get("visible_response_coverage", ""),
                "visible_response_coverage_current": current.get("visible_response_coverage", ""),
                "category": "P3_mask_actively_changes_result" if changed else "P3_no_op",
                "notes": "P3 differs only if fan/mask boundary adjustment changes the P2 region.",
            }
        )

    rows = [
        {
            "variant": "P0",
            "initial_region_source": "source anchor manual SAR visible-response bbox",
            "optical_motion_used": "false",
            "relative_depth_used": "false",
            "sar_image_used": "false",
            "sar_response_extractor": "none",
            "region_center_update": "fixed source anchor center",
            "region_size_update": "fixed source anchor size",
            "mask_used": "denominator_only",
            "mask_trigger_condition": "none",
            "target_frame_manual_box_read_before_output": "true",
            "future_anchor_read_before_output": "true_for_interval_control_and_metric_not_region",
            "actual_changed_row_count_vs_previous": "",
            "notes": "P0 output box itself is fixed to the source anchor, but target_pair is still loaded before loop and metric computation.",
        },
        {
            "variant": "P1",
            "initial_region_source": "linear interpolation between source and future target manual SAR anchor bboxes",
            "optical_motion_used": "implicit_endpoint_trend_only",
            "relative_depth_used": "false",
            "sar_image_used": "false",
            "sar_response_extractor": "none",
            "region_center_update": "linear source-to-target endpoint interpolation",
            "region_size_update": "linear source-to-target width/height interpolation",
            "mask_used": "denominator_only",
            "mask_trigger_condition": "none",
            "target_frame_manual_box_read_before_output": "true",
            "future_anchor_read_before_output": "true",
            "actual_changed_row_count_vs_previous": str(p1_changed),
            "notes": "P1 is known-two-endpoint interpolation; endpoint coverage of 1.0 is not independent propagation evidence.",
        },
        {
            "variant": "P2",
            "initial_region_source": "P1 endpoint interpolation base",
            "optical_motion_used": "implicit_endpoint_trend_only",
            "relative_depth_used": "false",
            "sar_image_used": "true",
            "sar_response_extractor": "local connected bright component within expanded predicted window",
            "region_center_update": "40 percent shift from P1 base toward local SAR response centroid",
            "region_size_update": "inherits P1 interpolated size; local response does not resize",
            "mask_used": "fan_mask filters local response pixels",
            "mask_trigger_condition": "all local response extraction is fan-mask filtered",
            "target_frame_manual_box_read_before_output": "true",
            "future_anchor_read_before_output": "true",
            "actual_changed_row_count_vs_previous": str(p2_changed),
            "notes": "P2 adds SAR-image response centering but remains anchored to the future manual endpoint.",
        },
        {
            "variant": "P3",
            "initial_region_source": "P2 local response region",
            "optical_motion_used": "implicit_endpoint_trend_only",
            "relative_depth_used": "false",
            "sar_image_used": "true",
            "sar_response_extractor": "same as P2, plus post-response fan/bottom boundary clipping branch",
            "region_center_update": "same as P2 unless mask branch clips y extent",
            "region_size_update": "same as P2 unless mask branch clips y extent",
            "mask_used": "fan_mask plus boundary clipping check",
            "mask_trigger_condition": "mask_intersection_ratio < 0.92 or bottom_valid_margin < 55",
            "target_frame_manual_box_read_before_output": "true",
            "future_anchor_read_before_output": "true",
            "actual_changed_row_count_vs_previous": str(p3_changed),
            "notes": f"P3 mask branch trigger count in existing manifest: {p3_mask_triggers}; common forward P2/P3 rows are identical after excluding the method label when this is zero.",
        },
    ]
    summary = {
        "p1_changed_vs_p0": p1_changed,
        "p2_changed_vs_p1": p2_changed,
        "p3_changed_vs_p2": p3_changed,
        "p3_mask_triggers": p3_mask_triggers,
        "p2_p3_common_forward_rows": len([key for key in p3 if key in p2]),
        "p2_p3_noop_rows": sum(1 for row in diagnostics if row["comparison"] == "P2_to_P3" and row["category"] == "P3_no_op"),
    }
    return rows, summary, diagnostics


def build_unique_frame_accounting(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    anchor_rows = data["anchor_rows"]
    prop_rows = data["prop_rows"]
    intervals = data["bidi_rows"]

    anchor_by_pair = {row["pair_id"]: row for row in anchor_rows if row["anchor_status"] == "ANCHOR_CONFIRMED"}
    left_pairs = {row["start_pair_id"] for row in intervals}
    right_pairs = {row["end_pair_id"] for row in intervals}
    anchor_key_to_pair: dict[tuple[str, str], str] = {}
    pair_to_optical: dict[str, str] = {}
    for pair in data["paired"]:
        pair_to_optical[pair["pair_id"]] = pair.get("optical_frame", "")
    for pair_id, row in anchor_by_pair.items():
        anchor_key_to_pair[(row["physical_vehicle_id"], row["sar_frame"])] = pair_id

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in prop_rows:
        grouped[(row["physical_vehicle_id"], row["sar_frame"])].append(row)

    interval_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in prop_rows:
        interval_by_key[(row["physical_vehicle_id"], row["sar_frame"])].add(row["interval_id"])

    rows: list[dict[str, Any]] = []
    for (pv, frame), records in sorted(grouped.items(), key=lambda item: (item[0][0], parse_int(item[0][1]))):
        pair_id = anchor_key_to_pair.get((pv, frame), "")
        is_left = pair_id in left_pairs
        is_right = pair_id in right_pairs
        is_anchor = bool(pair_id)
        methods = sorted({row["method"] for row in records})
        dirs = sorted({row["direction"] for row in records})
        p3_present = any(row["method"] == "P3" for row in records)
        original_metric = any(row["method"] == "P3" and row["direction"] == "forward" and row.get("visible_response_coverage") for row in records)
        rows.append(
            {
                "physical_vehicle_id": pv,
                "sar_frame_id": frame,
                "optical_frame_id": pair_to_optical.get(pair_id, ""),
                "anchor_interval_id": ";".join(sorted(interval_by_key[(pv, frame)])),
                "direction": "both" if len(dirs) > 1 else (dirs[0] if dirs else ""),
                "is_left_anchor": bool_text(is_left),
                "is_right_anchor": bool_text(is_right),
                "is_any_anchor": bool_text(is_anchor),
                "is_non_anchor_middle_frame": bool_text(not is_anchor),
                "number_of_forward_records": sum(1 for row in records if row["direction"] == "forward"),
                "number_of_backward_records": sum(1 for row in records if row["direction"] == "backward"),
                "number_of_variants": len(methods),
                "included_in_original_metric": bool_text(original_metric),
                "included_in_recomputed_metric": bool_text((not is_anchor) and p3_present),
            }
        )

    p3_rows = [row for row in prop_rows if row["method"] == "P3"]
    p3_forward = [row for row in p3_rows if row["direction"] == "forward"]
    p3_backward = [row for row in p3_rows if row["direction"] == "backward"]
    unique_all = {(row["physical_vehicle_id"], row["sar_frame"]) for row in prop_rows}
    unique_p3 = {(row["physical_vehicle_id"], row["sar_frame"]) for row in p3_rows}
    anchor_keys = set(anchor_key_to_pair.keys())
    unique_non_anchor_all = unique_all - anchor_keys
    unique_non_anchor_p3 = unique_p3 - anchor_keys
    duplicate_direction = {
        (row["physical_vehicle_id"], row["sar_frame_id"])
        for row in rows
        if int(row["number_of_forward_records"]) > 0 and int(row["number_of_backward_records"]) > 0
    }
    cross_interval_duplicates = {
        (row["physical_vehicle_id"], row["sar_frame_id"])
        for row in rows
        if len(str(row["anchor_interval_id"]).split(";")) > 1
    }
    anchor_interval_count = len({row["interval_id"] for row in intervals})
    optical_frames = {pair_to_optical[pair_id] for pair_id in anchor_by_pair if pair_to_optical.get(pair_id)}
    stats = {
        "original_forward_record_count_p3": len(p3_forward),
        "original_backward_record_count_p3": len(p3_backward),
        "unique_sar_frame_count_all_variants": len(unique_all),
        "unique_sar_frame_count_p3": len(unique_p3),
        "unique_optical_anchor_frame_count": len(optical_frames),
        "unique_vehicle_count": len({row["physical_vehicle_id"] for row in anchor_by_pair.values()}),
        "unique_anchor_interval_count": anchor_interval_count,
        "anchor_self_count": len(anchor_keys),
        "unique_non_anchor_middle_frame_count_all_variants": len(unique_non_anchor_all),
        "unique_non_anchor_middle_frame_count_p3": len(unique_non_anchor_p3),
        "forward_backward_duplicate_unique_frame_count": len(duplicate_direction),
        "cross_interval_duplicate_unique_frame_count": len(cross_interval_duplicates),
    }
    return rows, stats


def stable_nonzero_from_mask_source(mask_source_rows: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    for row in mask_source_rows:
        if row.get("source_type") == "GM_RM019_gray_png_stable_nonzero_support":
            open_q = row.get("open_question", "")
            parts = dict(part.split("=", 1) for part in open_q.split(";") if "=" in part)
            return parts.get("stable_count", "not_used"), parts.get("fan_count", "not_used")
    return "not_used", "not_used"


def build_metrics(data: Mapping[str, Any], unique_stats: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prop_rows = data["prop_rows"]
    fan_mask = build_geometry()["fan"]
    fan_count = int(fan_mask.sum())
    canvas_area = SAR_WIDTH * SAR_HEIGHT
    stable_count, mask_source_fan_count = stable_nonzero_from_mask_source(data["mask_source"])

    p3_forward_target = [
        row for row in prop_rows
        if row["method"] == "P3" and row["direction"] == "forward" and row.get("visible_response_coverage")
    ]
    original_cov = [parse_float(row["visible_response_coverage"]) for row in p3_forward_target]
    original_masked = [parse_float(row["masked_overlap_coverage"]) for row in p3_forward_target]

    p3_by_unique: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    anchor_rows = { (row["physical_vehicle_id"], row["sar_frame"]) for row in data["anchor_rows"] if row["anchor_status"] == "ANCHOR_CONFIRMED" }
    for row in prop_rows:
        if row["method"] == "P3":
            key = (row["physical_vehicle_id"], row["sar_frame"])
            if key not in anchor_rows:
                p3_by_unique[key].append(row)

    fused_area_ratios: list[float] = []
    fused_search_ratios: list[float] = []
    for records in p3_by_unique.values():
        boxes = [box_from_row(row) for row in records]
        areas = [box.area for box in boxes if box]
        searches = [parse_float(row["local_search_ratio"], math.nan) for row in records]
        if areas:
            fused_area_ratios.append(min(areas) / fan_count)
        valid_search = [v for v in searches if not math.isnan(v)]
        if valid_search:
            fused_search_ratios.append(min(valid_search))

    rows = [
        {
            "metric_name": "canvas_area",
            "value": str(canvas_area),
            "denominator_count": "",
            "denominator_type": "2308x1334_canvas",
            "status": "PASS",
            "notes": "Fixed SAR canvas area requested by prompt.",
        },
        {
            "metric_name": "static_fan_geometry_area",
            "value": str(fan_count),
            "denominator_count": "",
            "denominator_type": "static_fan_geometry_area",
            "status": "PASS",
            "notes": "WGV3.6A uses this as local_search_ratio denominator.",
        },
        {
            "metric_name": "stable_nonzero_area",
            "value": stable_count,
            "denominator_count": mask_source_fan_count,
            "denominator_type": "R2C_sampled_stable_nonzero_support_not_used_by_WGV36",
            "status": "DIAGNOSTIC_ONLY",
            "notes": "Reported from R2C mask source inventory; not the WGV3.6A ratio denominator.",
        },
        {
            "metric_name": "original_record_level_p3_forward_target_visible_response_coverage",
            "value": num(float(np.mean(original_cov)) if original_cov else math.nan),
            "denominator_count": len(original_cov),
            "denominator_type": "P3_forward_target_endpoint_records",
            "status": "INVALID_FOR_INDEPENDENT_PROPAGATION",
            "notes": "Computed only on future target anchor endpoints whose manual SAR box was read before output.",
        },
        {
            "metric_name": "original_record_level_p3_forward_target_masked_overlap_coverage",
            "value": num(float(np.mean(original_masked)) if original_masked else math.nan),
            "denominator_count": len(original_masked),
            "denominator_type": "P3_forward_target_endpoint_records",
            "status": "INVALID_FOR_INDEPENDENT_PROPAGATION",
            "notes": "Same denominator and target-endpoint issue as visible_response_coverage.",
        },
        {
            "metric_name": "unique_non_anchor_visible_box_coverage",
            "value": "not_tested",
            "denominator_count": unique_stats["unique_non_anchor_middle_frame_count_p3"],
            "denominator_type": "unique_non_anchor_p3_sar_frames",
            "status": "NOT_TESTED",
            "notes": "No independent manual/eval visible box exists in the WGV3.6A manifest for non-anchor middle frames.",
        },
        {
            "metric_name": "unique_non_anchor_mask_intersection_coverage",
            "value": "not_tested",
            "denominator_count": unique_stats["unique_non_anchor_middle_frame_count_p3"],
            "denominator_type": "unique_non_anchor_p3_sar_frames",
            "status": "NOT_TESTED",
            "notes": "Original masked coverage multiplies target endpoint coverage by fan intersection; no middle-frame eval mask target is available.",
        },
        {
            "metric_name": "unique_non_anchor_region_area_ratio_mean",
            "value": num(float(np.mean(fused_area_ratios)) if fused_area_ratios else math.nan),
            "denominator_count": len(fused_area_ratios),
            "denominator_type": "unique_non_anchor_p3_sar_frames_over_static_fan",
            "status": "PASS",
            "notes": "Each unique non-anchor frame counted once; duplicate directions use the smaller observed P3 area.",
        },
        {
            "metric_name": "unique_non_anchor_region_area_ratio_median",
            "value": num(float(np.median(fused_area_ratios)) if fused_area_ratios else math.nan),
            "denominator_count": len(fused_area_ratios),
            "denominator_type": "unique_non_anchor_p3_sar_frames_over_static_fan",
            "status": "PASS",
            "notes": "Area numerator is absolute P3 propagated region pixels divided by static fan area.",
        },
        {
            "metric_name": "unique_non_anchor_center_distance_to_eval_box",
            "value": "not_tested",
            "denominator_count": unique_stats["unique_non_anchor_middle_frame_count_p3"],
            "denominator_type": "unique_non_anchor_p3_sar_frames",
            "status": "NOT_TESTED",
            "notes": "No independent middle-frame eval box center is available.",
        },
        {
            "metric_name": "unique_non_anchor_search_ratio_median",
            "value": num(float(np.median(fused_search_ratios)) if fused_search_ratios else math.nan),
            "denominator_count": len(fused_search_ratios),
            "denominator_type": "unique_non_anchor_p3_sar_frames_over_static_fan",
            "status": "PASS",
            "notes": "Search denominator is static fan geometry for all variants.",
        },
    ]
    summary = {
        "canvas_area": canvas_area,
        "fan_count": fan_count,
        "stable_nonzero_area": stable_count,
        "original_visible_response_coverage": rows[3]["value"],
        "original_masked_overlap_coverage": rows[4]["value"],
        "unique_non_anchor_visible_box_coverage": "not_tested",
        "unique_non_anchor_region_area_ratio_mean": rows[7]["value"],
        "unique_non_anchor_region_area_ratio_median": rows[8]["value"],
        "unique_non_anchor_search_ratio_median": rows[10]["value"],
    }
    return rows, summary


def closure_level(iou: float, dist: float, same_response: bool, has_spatial_overlap: bool) -> str:
    if same_response:
        return "C3"
    if iou >= 0.50:
        return "C2"
    if not math.isnan(dist) and dist <= 25.0:
        return "C1"
    if has_spatial_overlap:
        return "C0"
    return "C0"


def build_closure_reaudit(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], Counter]:
    prop_rows = data["prop_rows"]
    bidi_rows = data["bidi_rows"]
    p3_forward_by_interval: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    p3_backward_by_interval: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in prop_rows:
        if row["method"] != "P3":
            continue
        target = p3_forward_by_interval if row["direction"] == "forward" else p3_backward_by_interval
        target[row["interval_id"]][row["sar_frame"]] = row

    rows: list[dict[str, Any]] = []
    for original in bidi_rows:
        interval_id = original["interval_id"]
        f_rows = p3_forward_by_interval.get(interval_id, {})
        b_rows = p3_backward_by_interval.get(interval_id, {})
        common = sorted(set(f_rows) & set(b_rows), key=parse_int)
        if common:
            best_frame = max(common, key=lambda frame: box_iou(box_from_row(f_rows[frame]), box_from_row(b_rows[frame])))
            f_row = f_rows[best_frame]
            b_row = b_rows[best_frame]
            same_frame_note = f"same_frame={best_frame}"
        else:
            f_row = list(f_rows.values())[-1] if f_rows else None
            b_row = list(b_rows.values())[-1] if b_rows else None
            same_frame_note = "no_common_propagated_frame; using frontiers only"
        f_box = box_from_row(f_row) if f_row else None
        b_box = box_from_row(b_row) if b_row else None
        inter = box_intersection_area(f_box, b_box)
        iou = box_iou(f_box, b_box)
        dist = center_distance(f_box, b_box)
        centroid_dist = point_distance(centroid_text(f_row), centroid_text(b_row))
        same_response = False
        level = closure_level(iou, dist, same_response, inter > 0.0)
        manual_used = "yes_in_original_when_target_reached_or_coverage_threshold_used; no_in_reaudit"
        if original.get("visible_response_coverage"):
            manual_used = "yes_in_original_closed_label; no_in_reaudit"
        rows.append(
            {
                "interval_id": interval_id,
                "physical_vehicle_id": original["physical_vehicle_id"],
                "left_anchor": original["start_pair_id"],
                "right_anchor": original["end_pair_id"],
                "gap_length": original["gap_frames"],
                "forward_region_area": num(box_area(f_box)),
                "backward_region_area": num(box_area(b_box)),
                "region_intersection_area": num(inter),
                "region_iou": num(iou),
                "region_center_distance": num(dist),
                "forward_response_centroid": centroid_text(f_row),
                "backward_response_centroid": centroid_text(b_row),
                "response_centroid_distance": num(centroid_dist),
                "same_connected_response_supported": "false_manifest_has_no_component_id",
                "manual_target_used_in_closure_decision": manual_used,
                "original_closure_label": original["closure_status"],
                "reaudited_closure_level": level,
                "reaudit_reason": f"{same_frame_note}; C0 is not complete closure; C3 not supported by manifest.",
            }
        )
    return rows, Counter(row["reaudited_closure_level"] for row in rows)


def draw_labeled_box(
    draw: ImageDraw.ImageDraw,
    box: Box,
    sx: float,
    sy: float,
    color: tuple[int, int, int],
    label: str,
    width: int = 3,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> None:
    coords = [
        (box.x1 - offset_x) * sx,
        (box.y1 - offset_y) * sy,
        (box.x2 - offset_x) * sx,
        (box.y2 - offset_y) * sy,
    ]
    draw.rectangle(coords, outline=color, width=width)
    draw.text((coords[0] + 4, max(4, coords[1] + 4)), label, fill=color)


def draw_cross(
    draw: ImageDraw.ImageDraw,
    text: str,
    sx: float,
    sy: float,
    color: tuple[int, int, int],
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> None:
    try:
        x, y = [float(v) for v in text.split(",")[:2]]
    except Exception:
        return
    x = (x - offset_x) * sx
    y = (y - offset_y) * sy
    draw.line([x - 5, y, x + 5, y], fill=color, width=2)
    draw.line([x, y - 5, x, y + 5], fill=color, width=2)


def render_visual_audits(data: Mapping[str, Any], diagnostics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prop_rows = data["prop_rows"]
    pair_index = make_pair_index(data)
    p1 = index_by_key(prop_rows, "P1", "forward")
    p2 = index_by_key(prop_rows, "P2", "forward")
    p3 = index_by_key(prop_rows, "P3", "forward")

    selected: list[Mapping[str, Any]] = []
    for category in ["P2_moves_to_stronger_response", "P2_hurts_coverage", "P3_no_op", "P3_mask_actively_changes_result"]:
        match = next((row for row in diagnostics if row["category"] == category), None)
        if match:
            selected.append(match)

    out: list[dict[str, Any]] = []
    for idx, diag in enumerate(selected, start=1):
        key = (diag["interval_id"], "forward", diag["sar_frame"])
        p1_row = p1.get(key)
        p2_row = p2.get(key)
        p3_row = p3.get(key)
        base_row = p3_row or p2_row or p1_row
        if not base_row:
            continue
        frame = parse_int(diag["sar_frame"])
        boxes = [box_from_row(row) for row in [p1_row, p2_row, p3_row] if row]
        target_pair = pair_index.get(str(base_row.get("target_pair_id", "")))
        eval_box = box_from_pair(target_pair, "sar_bbox") if target_pair else None
        if eval_box:
            boxes.append(eval_box)
        if boxes and sar_gray_path("GM_RM019", frame).exists():
            x0 = max(0, int(math.floor(min(box.x1 for box in boxes) - 110)))
            y0 = max(0, int(math.floor(min(box.y1 for box in boxes) - 90)))
            x1 = min(SAR_WIDTH, int(math.ceil(max(box.x2 for box in boxes) + 110)))
            y1 = min(SAR_HEIGHT, int(math.ceil(max(box.y2 for box in boxes) + 90)))
            base = Image.open(sar_gray_path("GM_RM019", frame)).convert("L").crop((x0, y0, x1, y1)).convert("RGB")
            tile = base.resize((720, 420))
            sx, sy = 720 / max(1, x1 - x0), 420 / max(1, y1 - y0)
            offset_x, offset_y = float(x0), float(y0)
        else:
            tile = image_with_box(sar_gray_path("GM_RM019", frame), None, (720, 420), (255, 255, 255), f"A1.5 {diag['category']} SAR{frame}")
            sx, sy = 720 / SAR_WIDTH, 420 / SAR_HEIGHT
            offset_x, offset_y = 0.0, 0.0
        draw = ImageDraw.Draw(tile)
        draw_fan_boundary(draw, sx, sy, offset_x=-offset_x * sx, offset_y=-offset_y * sy)
        colors = {"P1": (60, 150, 255), "P2": (200, 90, 255), "P3": (30, 240, 130)}
        for label, row in [("P1", p1_row), ("P2", p2_row), ("P3", p3_row)]:
            box = box_from_row(row) if row else None
            if box:
                draw_labeled_box(draw, box, sx, sy, colors[label], label, offset_x=offset_x, offset_y=offset_y)
                draw_cross(draw, row.get("local_response_center", ""), sx, sy, colors[label], offset_x=offset_x, offset_y=offset_y)
        if eval_box:
            draw_labeled_box(draw, eval_box, sx, sy, (255, 230, 40), "eval-only target anchor", width=1, offset_x=offset_x, offset_y=offset_y)
        draw.rectangle([0, 370, 720, 420], fill=(0, 0, 0))
        draw.text((8, 376), f"{diag['interval_id']} frame={frame}", fill=(255, 255, 255))
        draw.text((8, 396), f"{diag['category']} | manual target shown eval-only", fill=(255, 230, 40))
        png = OUT_DIR / f"a1_5_visual_audit_{idx:02d}_{diag['category']}.png"
        tile.save(png)
        out.append(
            {
                "visual_id": f"A15_VIS_{idx:02d}",
                "category": diag["category"],
                "source_comparison": diag["comparison"],
                "physical_vehicle_id": diag["physical_vehicle_id"],
                "interval_id": diag["interval_id"],
                "sar_frame": diag["sar_frame"],
                "ignored_png_path": rel(png),
                "notes": "PNG is under ignored outputs/ and is not intended for commit.",
            }
        )
    return out


def build_report(
    data: Mapping[str, Any],
    variant_rows: Sequence[Mapping[str, Any]],
    variant_summary: Mapping[str, Any],
    unique_stats: Mapping[str, Any],
    metric_summary: Mapping[str, Any],
    closure_counts: Counter,
    diagnostics: Sequence[Mapping[str, Any]],
    visual_index: Sequence[Mapping[str, Any]],
) -> str:
    branch = git_output(["branch", "--show-current"])
    head = git_output(["rev-parse", "HEAD"])
    divergence = git_output(["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"])
    diff_tree = git_output(["diff-tree", "--no-commit-id", "--name-status", "-r", START_COMMIT])

    category_counts = Counter(row["category"] for row in diagnostics)
    conclusion_rows = [
        {"item": "anchor_initialization_roles_clear", "status": "PASS", "reason": "Manual anchor fields and identity-review gates are now explicitly ledgered."},
        {"item": "propagation_does_not_read_target_frame_manual_box", "status": "FAIL", "reason": "target_box is read before P1/P2/P3 output and used for endpoint interpolation."},
        {"item": "propagation_does_not_read_eval_response_region", "status": "CONDITIONAL", "reason": "No middle-frame eval region is read, but R2C mask class gates anchors and fan mask filters local response."},
        {"item": "metrics_unique_non_anchor_frames", "status": "FAIL", "reason": "Original 0.952958 coverage is P3 forward target-endpoint record-level only."},
        {"item": "P1_improvement_independent_evidence", "status": "FAIL", "reason": "P1 uses future endpoint manual anchor; endpoint coverage is structurally inflated."},
        {"item": "P2_sar_correction_net_positive", "status": "NOT_TESTED", "reason": "P2 moves to local SAR response, but non-anchor independent eval boxes are absent."},
        {"item": "P3_mask_actual_trigger", "status": "FAIL", "reason": f"P3 mask branch triggered {variant_summary['p3_mask_triggers']} times."},
        {"item": "bidirectional_closure_reaches_C2_or_C3", "status": "CONDITIONAL", "reason": f"C2={closure_counts.get('C2', 0)}, C3={closure_counts.get('C3', 0)}; C3 is not supported by component identity."},
        {"item": "search_denominator_clear", "status": "PASS", "reason": f"actual denominator is static fan geometry area {metric_summary['fan_count']}."},
        {"item": "identity_contamination_eval_independent", "status": "CONDITIONAL", "reason": "Anchor identities are reviewed, but no middle-frame identity contamination measurement exists."},
        {"item": "current_results_support_A2", "status": "FAIL", "reason": "Known-endpoint/manual target leakage plus no unique non-anchor coverage eval."},
        {"item": "current_results_support_GM_RM011", "status": "FAIL", "reason": "A2 gate fails; GM_RM011 was not run and remains future pressure-test only."},
    ]

    created = [rel(path) for path in OUTPUTS.values()] + [row["ignored_png_path"] for row in visual_index]
    lines = [
        "# OTY2 WGV3.6A-A1.5 Propagation Integrity Audit",
        "",
        "## Repository State At Audit Start",
        "",
        f"- requested start commit: `{START_COMMIT}`",
        f"- branch: `{branch}`",
        f"- HEAD at audit start: `{head}`",
        f"- local/remote divergence before new commit: `{divergence}`",
        "- initial `git status --short`: `clean` (verified before creating A1.5 audit artifacts)",
        "",
        "## WGV3.6A Commit Inventory",
        "",
        "```text",
        diff_tree,
        "```",
        "",
        "## Main Finding",
        "",
        "WGV3.6A is not independent single-anchor propagation. In `propagate_interval`, the future anchor manual SAR box is read into `target_box` before output generation, and P1/P2/P3 use the source and target manual boxes as a known two-endpoint interpolation base. The original `0.952958` visible-response coverage is therefore `invalid_for_independent_propagation` and should be kept only as a record-level endpoint diagnostic.",
        "",
        "This does not mean the files should be deleted. It means the experiment must be named `bidirectional_interpolation_with_known_endpoints`, while single-anchor forward/backward extrapolation remains untested by an independent non-anchor metric.",
        "",
        "## Latest Manual Identity And Review Context",
        "",
        "- `reports/oty2/oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_20260710.md` is the latest GM_RM019 identity/observation audit used here.",
        "- `reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_center_semantic_review_20260711.csv` records that SAR centers are visible-response centers or mask-biased centers, not complete vehicle centers.",
        "- `reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv` records the manual optical-state/identity gate used by WGV3.6A anchors.",
        "",
        "## Variant Definitions",
        "",
        md_table(variant_rows, VARIANT_FIELDS),
        "",
        "## Variant Difference Diagnostics",
        "",
        f"- P1 changed vs P0 rows: `{variant_summary['p1_changed_vs_p0']}`",
        f"- P2 changed vs P1 rows: `{variant_summary['p2_changed_vs_p1']}`",
        f"- P3 changed vs P2 rows: `{variant_summary['p3_changed_vs_p2']}`",
        f"- P3 mask branch trigger count: `{variant_summary['p3_mask_triggers']}`",
        f"- P2/P3 common forward rows: `{variant_summary['p2_p3_common_forward_rows']}`",
        f"- P2/P3 no-op rows: `{variant_summary['p2_p3_noop_rows']}`",
        "",
        "Category counts:",
        "",
        md_table([{"category": k, "count": v} for k, v in sorted(category_counts.items())], ["category", "count"]),
        "",
        "## Unique Frame Accounting",
        "",
        f"- original P3 forward records: `{unique_stats['original_forward_record_count_p3']}`",
        f"- original P3 backward records: `{unique_stats['original_backward_record_count_p3']}`",
        f"- unique SAR frames, all variants: `{unique_stats['unique_sar_frame_count_all_variants']}`",
        f"- unique SAR frames, P3: `{unique_stats['unique_sar_frame_count_p3']}`",
        f"- unique optical anchor frames: `{unique_stats['unique_optical_anchor_frame_count']}`",
        f"- unique vehicles: `{unique_stats['unique_vehicle_count']}`",
        f"- unique anchor intervals: `{unique_stats['unique_anchor_interval_count']}`",
        f"- anchor self count: `{unique_stats['anchor_self_count']}`",
        f"- unique non-anchor middle SAR frames, all variants: `{unique_stats['unique_non_anchor_middle_frame_count_all_variants']}`",
        f"- unique non-anchor middle SAR frames, P3: `{unique_stats['unique_non_anchor_middle_frame_count_p3']}`",
        f"- forward/backward duplicate unique frames: `{unique_stats['forward_backward_duplicate_unique_frame_count']}`",
        f"- cross-interval duplicate unique frames: `{unique_stats['cross_interval_duplicate_unique_frame_count']}`",
        "",
        "## Metric Recompute",
        "",
        f"- original record-level visible_response_coverage: `{metric_summary['original_visible_response_coverage']}` over P3 forward target endpoint records",
        f"- original record-level masked_overlap_coverage: `{metric_summary['original_masked_overlap_coverage']}` over the same endpoint records",
        f"- recomputed unique_non_anchor_visible_box_coverage: `{metric_summary['unique_non_anchor_visible_box_coverage']}`",
        f"- recomputed unique_non_anchor_region_area_ratio mean/median: `{metric_summary['unique_non_anchor_region_area_ratio_mean']}` / `{metric_summary['unique_non_anchor_region_area_ratio_median']}`",
        f"- unique_non_anchor_search_ratio_median: `{metric_summary['unique_non_anchor_search_ratio_median']}`",
        "",
        "Non-anchor coverage is `NOT_TESTED`, not zero: the WGV3.6A manifest does not contain independent middle-frame manual/eval boxes. The correct conclusion is missing evaluation evidence, not failure of every middle-frame region.",
        "",
        "## Search Ratio Denominator",
        "",
        f"- canvas_area: `{metric_summary['canvas_area']}`",
        f"- static_fan_geometry_area / actual_denominator_area: `{metric_summary['fan_count']}`",
        f"- stable_nonzero_area from R2C inventory: `{metric_summary['stable_nonzero_area']}`",
        "- denominator_type: `static_fan_geometry_area`",
        "- denominator consistency: same for P0/P1/P2/P3; target independent; not built from manual boxes.",
        "",
        "## Closure Reaudit",
        "",
        f"- C0 count: `{closure_counts.get('C0', 0)}`",
        f"- C1 count: `{closure_counts.get('C1', 0)}`",
        f"- C2 count: `{closure_counts.get('C2', 0)}`",
        f"- C3 count: `{closure_counts.get('C3', 0)}`",
        "",
        "C0 is only window/region intersection and is not complete closure. C3 is not supported because the manifest does not preserve connected-component identity across forward/backward runs.",
        "",
        "## Gate Table",
        "",
        md_table(conclusion_rows, ["item", "status", "reason"]),
        "",
        "## A2 And GM_RM011 Gates",
        "",
        "- A2 gate: `A2_NOT_READY`",
        "- GM_RM011 gate: `GM_RM011_NOT_READY`",
        "- Minimum next step: add or recover an independent non-anchor evaluation set, then rerun this audit without target-endpoint boxes in region generation. Do not run GM_RM011 pressure testing until the A2 gate is cleared.",
        "",
        "## Created Audit Artifacts",
        "",
        "\n".join(f"- `{path}`" for path in created),
        "",
    ]
    return "\n".join(lines)


def run_all() -> dict[str, Any]:
    data = load_all()
    source_ledger = build_source_role_ledger(data)
    variant_rows, variant_summary, diagnostics = build_variant_definitions(data["prop_rows"])
    unique_rows, unique_stats = build_unique_frame_accounting(data)
    metric_rows, metric_summary = build_metrics(data, unique_stats)
    closure_rows, closure_counts = build_closure_reaudit(data)
    visual_index = render_visual_audits(data, diagnostics)

    write_csv(OUTPUTS["source_role_ledger"], source_ledger, SOURCE_LEDGER_FIELDS)
    write_csv(OUTPUTS["variant_definition"], variant_rows, VARIANT_FIELDS)
    write_csv(OUTPUTS["unique_frame_accounting"], unique_rows, UNIQUE_FIELDS)
    write_csv(OUTPUTS["metric_recompute"], metric_rows, METRIC_FIELDS)
    write_csv(OUTPUTS["closure_reaudit"], closure_rows, CLOSURE_FIELDS)
    write_csv(OUTPUTS["variant_diagnostics"], diagnostics, DIAG_FIELDS)
    write_csv(OUTPUTS["visual_index"], visual_index, VISUAL_INDEX_FIELDS)
    report = build_report(data, variant_rows, variant_summary, unique_stats, metric_summary, closure_counts, diagnostics, visual_index)
    write_text(OUTPUTS["report"], report)

    return {
        "variant_summary": variant_summary,
        "unique_stats": unique_stats,
        "metric_summary": metric_summary,
        "closure_counts": dict(closure_counts),
        "outputs": {key: rel(path) for key, path in OUTPUTS.items()},
        "visuals": [row["ignored_png_path"] for row in visual_index],
    }


def main() -> None:
    result = run_all()
    print("WGV3.6A-A1.5 audit complete")
    print(f"unique_non_anchor_p3_frames: {result['unique_stats']['unique_non_anchor_middle_frame_count_p3']}")
    print(f"original_visible_response_coverage: {result['metric_summary']['original_visible_response_coverage']}")
    print(f"p3_mask_triggers: {result['variant_summary']['p3_mask_triggers']}")
    print(f"closure_counts: {result['closure_counts']}")


if __name__ == "__main__":
    main()
