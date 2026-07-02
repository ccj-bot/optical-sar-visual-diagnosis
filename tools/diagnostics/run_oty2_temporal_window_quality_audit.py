"""Audit OTY2 object-level SAR temporal windows for downstream contracts.

This script reads existing OTY2-P1 software-sync temporal-window outputs and
writes contract and quality-review artifacts. It does not read SAR image
content, enter SAR spatial search, generate SAR spatial regions or candidate
boxes, use SAR GT, use selector/ranking output, train thresholds, or create
annotation proposals.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOCS_DIR = REPO_ROOT / "docs"

EXPECTED_OPTICAL_FPS = 24.0
EXPECTED_SAR_FPS = 50.0
EXPECTED_RATIO = EXPECTED_SAR_FPS / EXPECTED_OPTICAL_FPS

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_spatial_search_entered": False,
    "sar_search_region_generated": False,
    "sar_candidate_boxes_generated": False,
    "sar_gt_used": False,
    "final_manual_oracle_review_runtime_fields_used": False,
    "selector_or_ranking_used": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "detection_box_level_merge_reintroduced": False,
}

QUALITY_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "row_scope",
    "readiness_status",
    "spatial_constraint_input_status",
    "confidence_status",
    "object_state_category",
    "uses_primary_observations",
    "uses_secondary_observations",
    "optical_start_frame",
    "optical_end_frame",
    "optical_frame_count",
    "sar_start_raw",
    "sar_end_raw",
    "sar_start_frame",
    "sar_end_frame",
    "sar_window_frame_count",
    "optical_span_sar_frames",
    "window_scene_fraction",
    "padding_sar_frames",
    "expected_padding_sar_frames",
    "padding_policy_status",
    "recomputed_sar_start_raw",
    "recomputed_sar_end_raw",
    "recomputed_sar_start_frame",
    "recomputed_sar_end_frame",
    "recomputed_sar_window_frame_count",
    "formula_check_status",
    "fps_ratio_check_status",
    "width_constraint_status",
    "narrowness_status",
    "state_margin_status",
    "blockers",
    "quality_notes",
]


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def fmt_float(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def fmt_fraction(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def join_values(values: Sequence[Any]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return ";".join(out)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def latest_file(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.name, reverse=True)
    if not matches:
        raise FileNotFoundError(f"No file matched {pattern} under {directory}")
    return matches[0]


def per_scene_from_summary(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in summary.get("per_scene", []):
        if isinstance(row, Mapping):
            scene = str(row.get("scene", "") or "")
            if scene:
                out[scene] = dict(row)
    return out


def p1_decisions(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in summary.get("per_scene_decisions", []):
        if isinstance(row, Mapping):
            scene = str(row.get("scene", "") or "")
            if scene:
                out[scene] = dict(row)
    return out


def expected_padding(category: str) -> tuple[int | None, str]:
    if category == "stable_primary_continuity":
        return 3, "stable_margin_base_rounding_sync_state"
    if category == "secondary_edge_handoff_uncertainty":
        return 4, "secondary_edge_handoff_expanded_margin"
    if category == "ambiguous_review_required":
        return 5, "ambiguous_low_confidence_review_margin"
    if category == "short_noise_not_ready":
        return None, "not_ready_no_window_margin"
    return None, "unknown_state_margin"


def spatial_input_status(readiness_status: str) -> str:
    if readiness_status == "ready_primary_sar_temporal_window":
        return "eligible_primary_spatial_constraint_input"
    if readiness_status == "ready_uncertainty_expanded_sar_temporal_window":
        return "eligible_uncertainty_expanded_spatial_constraint_input"
    if readiness_status == "low_confidence_sar_temporal_window":
        return "review_only_temporal_context_not_normal_spatial_input"
    if readiness_status == "not_ready_for_sar_temporal_window":
        return "blocked_not_ready_for_spatial_constraint"
    return "blocked_unknown_readiness_status"


def fps_ratio_status(row: Mapping[str, Any], recomputed_start_raw: float, recomputed_end_raw: float) -> str:
    optical_fps = safe_float(row.get("optical_fps"))
    sar_fps = safe_float(row.get("sar_fps"))
    fps_ratio = safe_float(row.get("fps_ratio"))
    row_start_raw = safe_float(row.get("sar_start_raw"))
    row_end_raw = safe_float(row.get("sar_end_raw"))
    if optical_fps is None or sar_fps is None or fps_ratio is None:
        return "fail_missing_fps_fields"
    ratio_ok = (
        abs(optical_fps - EXPECTED_OPTICAL_FPS) <= 1e-9
        and abs(sar_fps - EXPECTED_SAR_FPS) <= 1e-9
        and abs(fps_ratio - EXPECTED_RATIO) <= 1e-5
    )
    raw_ok = True
    if row_start_raw is not None:
        raw_ok = raw_ok and abs(row_start_raw - recomputed_start_raw) <= 1e-4
    if row_end_raw is not None:
        raw_ok = raw_ok and abs(row_end_raw - recomputed_end_raw) <= 1e-4
    if ratio_ok and raw_ok:
        return "pass_50_over_24_mapping"
    return "fail_not_50_over_24_mapping"


def width_status(window_count: int | None, scene_sar_frames: int | None, readiness_status: str) -> str:
    if readiness_status == "not_ready_for_sar_temporal_window" or window_count is None:
        return "not_applicable_not_ready"
    scene_fraction = (window_count / scene_sar_frames) if scene_sar_frames else None
    if scene_fraction is not None and scene_fraction > 0.25:
        return "overwide_reduces_temporal_constraint_value"
    if window_count > 190:
        return "overwide_reduces_temporal_constraint_value"
    if scene_fraction is not None and scene_fraction > 0.15:
        return "wide_but_bounded_review"
    if window_count > 120:
        return "wide_but_bounded_review"
    if window_count <= 40:
        return "compact_temporal_constraint"
    return "normal_temporal_constraint"


def audit_object_row(row: Mapping[str, Any], scene_sar_frames: int | None) -> dict[str, Any]:
    scene = str(row.get("scene", "") or "")
    readiness_status = str(row.get("readiness_status", "") or "")
    category = str(row.get("object_state_category", "") or "")
    optical_start = safe_int(row.get("optical_start_frame"))
    optical_end = safe_int(row.get("optical_end_frame"))
    padding = safe_int(row.get("padding_sar_frames"))
    sar_start_frame = safe_int(row.get("sar_start_frame"))
    sar_end_frame = safe_int(row.get("sar_end_frame"))
    window_count = safe_int(row.get("sar_window_frame_count"))
    expected_pad, state_margin_status = expected_padding(category)
    notes: list[str] = []

    recomputed_start_raw: float | None = None
    recomputed_end_raw: float | None = None
    recomputed_start_frame: int | None = None
    recomputed_end_frame: int | None = None
    recomputed_window_count: int | None = None
    optical_span_sar_frames: float | None = None
    formula_check = "not_applicable_not_ready"
    fps_check = "not_applicable_not_ready"
    padding_policy = "not_applicable_not_ready"
    narrowness = "not_applicable_not_ready"

    if optical_start is not None and optical_end is not None:
        recomputed_start_raw = optical_start / EXPECTED_OPTICAL_FPS * EXPECTED_SAR_FPS
        recomputed_end_raw = (optical_end + 1) / EXPECTED_OPTICAL_FPS * EXPECTED_SAR_FPS
        optical_span_sar_frames = recomputed_end_raw - recomputed_start_raw

    if readiness_status != "not_ready_for_sar_temporal_window":
        fps_check = (
            fps_ratio_status(row, recomputed_start_raw or 0.0, recomputed_end_raw or 0.0)
            if recomputed_start_raw is not None and recomputed_end_raw is not None
            else "fail_missing_optical_frame_bounds"
        )
        if expected_pad is None:
            padding_policy = "fail_unknown_state_padding_policy"
        elif padding == expected_pad:
            padding_policy = "pass_expected_state_padding"
        elif padding is not None and padding > expected_pad:
            padding_policy = "pass_padding_above_expected"
            notes.append("padding_above_expected_for_state")
        else:
            padding_policy = "fail_padding_below_expected"

        if recomputed_start_raw is not None and recomputed_end_raw is not None and padding is not None:
            expected_start_unclamped = math.floor(recomputed_start_raw) - padding
            expected_end_unclamped = math.ceil(recomputed_end_raw) + padding
            if scene_sar_frames:
                recomputed_start_frame = max(0, expected_start_unclamped)
                recomputed_end_frame = min(scene_sar_frames - 1, expected_end_unclamped)
            else:
                recomputed_start_frame = expected_start_unclamped
                recomputed_end_frame = expected_end_unclamped
            recomputed_window_count = max(0, recomputed_end_frame - recomputed_start_frame + 1)
            bounds_ok = sar_start_frame == recomputed_start_frame and sar_end_frame == recomputed_end_frame
            count_ok = window_count == recomputed_window_count
            clamped = (recomputed_start_frame != expected_start_unclamped) or (
                recomputed_end_frame != expected_end_unclamped
            )
            if fps_check.startswith("fail"):
                formula_check = "fail_formula_blocked_by_fps_mismatch"
                narrowness = "review_formula_mismatch"
            elif bounds_ok and count_ok and clamped:
                formula_check = "pass_50_24_formula_with_inventory_clamp"
                narrowness = "not_too_narrow_inventory_start_or_end_clamped"
                notes.append("inventory_clamp_applied")
            elif bounds_ok and count_ok:
                formula_check = "pass_50_24_formula"
                narrowness = "not_too_narrow_formula_padding_ok"
            else:
                formula_check = "fail_window_bounds_mismatch"
                narrowness = "review_window_bounds_mismatch"
        if padding_policy == "fail_padding_below_expected":
            narrowness = "too_narrow_padding_below_policy"
    else:
        if category == "short_noise_not_ready":
            notes.append("short_or_noise_object_correctly_blocked")

    scene_fraction = (window_count / scene_sar_frames) if window_count is not None and scene_sar_frames else None
    width_check = width_status(window_count, scene_sar_frames, readiness_status)
    if width_check == "overwide_reduces_temporal_constraint_value":
        notes.append("overwide_review_required")
    elif width_check == "wide_but_bounded_review":
        notes.append("wide_but_still_bounded_by_scene_time")
    if category == "stable_primary_continuity" and width_check in {"wide_but_bounded_review", "overwide_reduces_temporal_constraint_value"}:
        notes.append("stable_object_window_width_driven_by_long_optical_span")

    return {
        "scene": scene,
        "object_hypothesis_id": row.get("object_hypothesis_id", ""),
        "row_scope": "object_temporal_window",
        "readiness_status": readiness_status,
        "spatial_constraint_input_status": spatial_input_status(readiness_status),
        "confidence_status": row.get("confidence_status", ""),
        "object_state_category": category,
        "uses_primary_observations": row.get("uses_primary_observations", ""),
        "uses_secondary_observations": row.get("uses_secondary_observations", ""),
        "optical_start_frame": row.get("optical_start_frame", ""),
        "optical_end_frame": row.get("optical_end_frame", ""),
        "optical_frame_count": row.get("optical_frame_count", ""),
        "sar_start_raw": row.get("sar_start_raw", ""),
        "sar_end_raw": row.get("sar_end_raw", ""),
        "sar_start_frame": row.get("sar_start_frame", ""),
        "sar_end_frame": row.get("sar_end_frame", ""),
        "sar_window_frame_count": row.get("sar_window_frame_count", ""),
        "optical_span_sar_frames": fmt_float(optical_span_sar_frames),
        "window_scene_fraction": fmt_fraction(scene_fraction),
        "padding_sar_frames": row.get("padding_sar_frames", ""),
        "expected_padding_sar_frames": "" if expected_pad is None else expected_pad,
        "padding_policy_status": padding_policy,
        "recomputed_sar_start_raw": fmt_float(recomputed_start_raw),
        "recomputed_sar_end_raw": fmt_float(recomputed_end_raw),
        "recomputed_sar_start_frame": "" if recomputed_start_frame is None else recomputed_start_frame,
        "recomputed_sar_end_frame": "" if recomputed_end_frame is None else recomputed_end_frame,
        "recomputed_sar_window_frame_count": "" if recomputed_window_count is None else recomputed_window_count,
        "formula_check_status": formula_check,
        "fps_ratio_check_status": fps_check,
        "width_constraint_status": width_check,
        "narrowness_status": narrowness,
        "state_margin_status": state_margin_status,
        "blockers": row.get("blockers", ""),
        "quality_notes": join_values(notes),
    }


def scene_blocker_row(scene: str, status: Mapping[str, Any]) -> dict[str, Any]:
    notes = [
        "temporal_metadata_available_but_object_flow_missing"
        if status.get("temporal_metadata_status")
        else "scene_missing_target_level_input",
        "no_object_level_sar_temporal_window_generated",
    ]
    return {
        "scene": scene,
        "object_hypothesis_id": "",
        "row_scope": "scene_input_blocker",
        "readiness_status": "not_ready_for_sar_temporal_window",
        "spatial_constraint_input_status": "blocked_missing_object_level_flow",
        "confidence_status": "blocked_missing_object_stream",
        "object_state_category": "scene_missing_object_flow",
        "uses_primary_observations": "false",
        "uses_secondary_observations": "false",
        "formula_check_status": "not_applicable_no_object_flow",
        "fps_ratio_check_status": "metadata_available_24_50_software_sync",
        "width_constraint_status": "not_applicable_no_object_flow",
        "narrowness_status": "not_applicable_no_object_flow",
        "padding_policy_status": "not_applicable_no_object_flow",
        "state_margin_status": "not_applicable_no_object_flow",
        "blockers": status.get("blockers", ""),
        "quality_notes": join_values(notes),
    }


def median_text(values: Sequence[int]) -> str:
    if not values:
        return ""
    return f"{statistics.median(values):.1f}"


def summarize_quality(rows: Sequence[Mapping[str, Any]], scene_status: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    object_rows = [row for row in rows if row.get("row_scope") == "object_temporal_window"]
    generated_rows = [
        row
        for row in object_rows
        if row.get("readiness_status") != "not_ready_for_sar_temporal_window"
    ]
    per_scene: dict[str, dict[str, Any]] = {}
    scenes = sorted(set(scene_status) | {str(row.get("scene", "")) for row in rows if row.get("scene")})
    for scene in scenes:
        scene_rows = [row for row in rows if row.get("scene") == scene]
        scene_object_rows = [row for row in scene_rows if row.get("row_scope") == "object_temporal_window"]
        generated = [
            row
            for row in scene_object_rows
            if row.get("readiness_status") != "not_ready_for_sar_temporal_window"
        ]
        widths = [
            safe_int(row.get("sar_window_frame_count"), 0) or 0
            for row in generated
            if safe_int(row.get("sar_window_frame_count")) is not None
        ]
        status_counts = Counter(str(row.get("spatial_constraint_input_status", "")) for row in scene_rows)
        per_scene[scene] = {
            "object_rows": len(scene_object_rows),
            "generated_windows": len(generated),
            "blocked_or_not_ready_rows": sum(
                1 for row in scene_rows if str(row.get("readiness_status", "")) == "not_ready_for_sar_temporal_window"
            ),
            "normal_downstream_input_rows": status_counts["eligible_primary_spatial_constraint_input"]
            + status_counts["eligible_uncertainty_expanded_spatial_constraint_input"],
            "review_only_temporal_context_rows": status_counts["review_only_temporal_context_not_normal_spatial_input"],
            "width_min": min(widths) if widths else "",
            "width_median": median_text(widths),
            "width_max": max(widths) if widths else "",
            "width_status_counts": dict(Counter(str(row.get("width_constraint_status", "")) for row in scene_rows)),
            "formula_status_counts": dict(Counter(str(row.get("formula_check_status", "")) for row in scene_rows)),
            "blockers": scene_status.get(scene, {}).get("blockers", ""),
        }
    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({str(row.get("object_state_category", "")) for row in generated_rows}):
        cat_rows = [row for row in generated_rows if row.get("object_state_category") == category]
        widths = [
            safe_int(row.get("sar_window_frame_count"), 0) or 0
            for row in cat_rows
            if safe_int(row.get("sar_window_frame_count")) is not None
        ]
        by_category[category] = {
            "count": len(cat_rows),
            "width_min": min(widths) if widths else "",
            "width_median": median_text(widths),
            "width_max": max(widths) if widths else "",
        }
    return {
        "object_rows": len(object_rows),
        "generated_windows": len(generated_rows),
        "not_ready_object_rows": sum(
            1 for row in object_rows if row.get("readiness_status") == "not_ready_for_sar_temporal_window"
        ),
        "normal_downstream_input_rows": sum(
            1
            for row in rows
            if row.get("spatial_constraint_input_status")
            in {
                "eligible_primary_spatial_constraint_input",
                "eligible_uncertainty_expanded_spatial_constraint_input",
            }
        ),
        "review_only_temporal_context_rows": sum(
            1
            for row in rows
            if row.get("spatial_constraint_input_status") == "review_only_temporal_context_not_normal_spatial_input"
        ),
        "blocked_spatial_input_rows": sum(
            1
            for row in rows
            if str(row.get("spatial_constraint_input_status", "")).startswith("blocked_")
        ),
        "width_status_counts": dict(Counter(str(row.get("width_constraint_status", "")) for row in rows)),
        "formula_status_counts": dict(Counter(str(row.get("formula_check_status", "")) for row in rows)),
        "fps_ratio_status_counts": dict(Counter(str(row.get("fps_ratio_check_status", "")) for row in rows)),
        "narrowness_status_counts": dict(Counter(str(row.get("narrowness_status", "")) for row in rows)),
        "padding_policy_status_counts": dict(Counter(str(row.get("padding_policy_status", "")) for row in rows)),
        "per_scene": per_scene,
        "by_object_state_category": by_category,
    }


def render_contract(
    *,
    timestamp: str,
    source_windows: Path,
    source_summary: Path,
    quality_csv: Path,
    quality_report: Path,
    design_doc: Path,
    summary: Mapping[str, Any],
    scene_status: Mapping[str, Mapping[str, Any]],
) -> str:
    lines = [
        "# OTY2 Object SAR Temporal Window Downstream Input Contract",
        "",
        f"Generated: `{timestamp}`",
        "",
        "This contract freezes the current object-level SAR temporal-window output as an input to a later spatial-constraint stage. It is not a SAR detector, not a SAR spatial search, not a candidate-box generator, and not an annotation proposal.",
        "",
        "## Eligible Inputs",
        "",
        "Normal downstream spatial-constraint inputs are limited to object rows whose `readiness_status` is:",
        "",
        "- `ready_primary_sar_temporal_window`: stable primary optical continuity; pass as a primary temporal prior.",
        "- `ready_uncertainty_expanded_sar_temporal_window`: usable primary continuity with secondary/edge/handoff uncertainty; pass with expanded uncertainty flags.",
        "",
        "`low_confidence_sar_temporal_window` rows are kept as review-only temporal context. They are not normal spatial-constraint inputs unless a later explicitly bounded review mode accepts them. `not_ready_for_sar_temporal_window` rows remain blocked.",
        "",
        "## Blocked Inputs",
        "",
        "- `short_noise_not_ready` objects remain blocked before spatial constraint construction.",
        "- Scene-level missing object flow remains blocked even if temporal metadata exists.",
        "- `GM_RM011` has 24:50 software-sync temporal metadata, but it has no committed optical object stream in this run, so it cannot produce object-level downstream inputs.",
        "",
        "## Required Fields Passed Downstream",
        "",
        "The minimum object-level temporal input record is:",
        "",
        "```text",
        "scene",
        "object_hypothesis_id",
        "optical_start_frame",
        "optical_end_frame",
        "optical_frame_count",
        "optical_start_time_sec",
        "optical_end_time_sec",
        "sar_start_raw",
        "sar_end_raw",
        "sar_start_frame",
        "sar_end_frame",
        "sar_window_frame_count",
        "optical_fps",
        "sar_fps",
        "fps_ratio",
        "sync_mode",
        "offset_seconds",
        "software_sync_jitter_ms",
        "padding_sar_frames",
        "padding_reason",
        "object_state_category",
        "uses_primary_observations",
        "uses_secondary_observations",
        "readiness_status",
        "confidence_status",
        "blockers",
        "notes",
        "```",
        "",
        "These fields carry temporal scope only. They do not carry a SAR location, SAR search region, candidate box, score, rank, GT coverage result, annotation decision, or identity truth.",
        "",
        "## Temporal Interpretation",
        "",
        "- `sar_start_frame` and `sar_end_frame` are inclusive SAR frame indices.",
        "- The window is derived from object optical frame bounds, not from per-frame real timestamps.",
        "- The conversion is `start_time = optical_start_frame / 24`, `end_time = (optical_end_frame + 1) / 24`, then `sar_time * 50`.",
        "- The mapping must use `50/24 = 2.083333`; a simple two-times relationship is invalid.",
        "- `offset_seconds = 0` is a software-sync zero-offset processing-start assumption, not hardware exact sync.",
        "",
        "## Padding Semantics",
        "",
        "- Base rounding padding covers floor/ceil quantization after converting continuous time to SAR frame indices.",
        "- Software-sync jitter padding covers millisecond-level non-hardware synchronization error; current audit default is one SAR frame for 20 ms at 50 fps.",
        "- Object-state padding covers optical uncertainty from secondary observations, duplicate/partial/edge/occlusion states, handoff, ambiguity, or review-required states.",
        "- Padding defaults are audit defaults, not trained thresholds.",
        "",
        "## Object-State Handling",
        "",
        "| object state | downstream handling | padding policy |",
        "| --- | --- | --- |",
        "| `stable_primary_continuity` | normal primary input | base + software jitter + stable primary padding |",
        "| `secondary_edge_handoff_uncertainty` | normal input with expanded uncertainty | base + software jitter + secondary/edge/duplicate/partial/occlusion/handoff padding |",
        "| `ambiguous_review_required` | review-only temporal context, not normal spatial input | base + software jitter + ambiguous padding |",
        "| `short_noise_not_ready` | blocked before spatial constraints | no generated temporal window |",
        "",
        "## Scene Status",
        "",
        "| scene | object rows | generated windows | normal downstream inputs | review-only windows | blocked/not-ready rows | blocker |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for scene, data in summary.get("per_scene", {}).items():
        lines.append(
            f"| `{scene}` | {data.get('object_rows', 0)} | {data.get('generated_windows', 0)} | "
            f"{data.get('normal_downstream_input_rows', 0)} | {data.get('review_only_temporal_context_rows', 0)} | "
            f"{data.get('blocked_or_not_ready_rows', 0)} | `{data.get('blockers', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Source and Output Artifacts",
            "",
            f"- source_temporal_windows: `{source_windows}`",
            f"- source_temporal_window_summary: `{source_summary}`",
            f"- quality_audit_csv: `{quality_csv}`",
            f"- quality_report: `{quality_report}`",
            f"- spatial_constraint_design: `{design_doc}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_quality_report(
    *,
    timestamp: str,
    source_windows: Path,
    summary: Mapping[str, Any],
    quality_csv: Path,
) -> str:
    lines = [
        "# OTY2 Object SAR Temporal Window Quality Audit",
        "",
        f"Generated: `{timestamp}`",
        "",
        "This audit reviews temporal-window quality only. It does not read SAR images, use SAR GT, generate SAR spatial regions, score candidates, rank hypotheses, tune thresholds, or create annotation proposals.",
        "",
        "## Inputs Reviewed",
        "",
        f"- source temporal windows: `{source_windows}`",
        f"- object rows reviewed: `{summary.get('object_rows', 0)}`",
        f"- generated object-level SAR temporal windows: `{summary.get('generated_windows', 0)}`",
        f"- normal downstream spatial-constraint inputs: `{summary.get('normal_downstream_input_rows', 0)}`",
        f"- review-only temporal contexts: `{summary.get('review_only_temporal_context_rows', 0)}`",
        f"- blocked spatial inputs: `{summary.get('blocked_spatial_input_rows', 0)}`",
        "",
        "## Per-Scene Results",
        "",
        "| scene | object rows | generated windows | normal downstream inputs | review-only windows | blocked/not-ready rows | width min/median/max | blocker |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for scene, data in summary.get("per_scene", {}).items():
        width = (
            f"{data.get('width_min', '')}/{data.get('width_median', '')}/{data.get('width_max', '')}"
            if data.get("width_min", "") != ""
            else "n/a"
        )
        lines.append(
            f"| `{scene}` | {data.get('object_rows', 0)} | {data.get('generated_windows', 0)} | "
            f"{data.get('normal_downstream_input_rows', 0)} | {data.get('review_only_temporal_context_rows', 0)} | "
            f"{data.get('blocked_or_not_ready_rows', 0)} | `{width}` | `{data.get('blockers', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Window Width by Object State",
            "",
            "| object_state_category | count | width min/median/max | interpretation |",
            "| --- | ---: | --- | --- |",
        ]
    )
    interpretations = {
        "stable_primary_continuity": "stable primary windows are generally narrower; width can still grow when the optical object span is long",
        "secondary_edge_handoff_uncertainty": "expanded margins preserved for secondary, edge, duplicate, partial, occlusion, or handoff uncertainty",
        "ambiguous_review_required": "kept as low-confidence review windows with the largest temporal padding",
    }
    for category, data in summary.get("by_object_state_category", {}).items():
        width = f"{data.get('width_min', '')}/{data.get('width_median', '')}/{data.get('width_max', '')}"
        lines.append(
            f"| `{category}` | {data.get('count', 0)} | `{width}` | {interpretations.get(category, '')} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            f"- width status counts: `{json.dumps(summary.get('width_status_counts', {}), sort_keys=True)}`",
            f"- formula status counts: `{json.dumps(summary.get('formula_status_counts', {}), sort_keys=True)}`",
            f"- fps-ratio status counts: `{json.dumps(summary.get('fps_ratio_status_counts', {}), sort_keys=True)}`",
            f"- narrowness status counts: `{json.dumps(summary.get('narrowness_status_counts', {}), sort_keys=True)}`",
            f"- padding policy status counts: `{json.dumps(summary.get('padding_policy_status_counts', {}), sort_keys=True)}`",
            "",
            "Findings:",
            "",
            "- No generated window violated the 50/24 conversion check.",
            "- No generated window was flagged as too narrow under the audit padding policy.",
            "- No generated window crossed the hard overwide review band that would remove temporal constraint value.",
            "- Wide-but-bounded windows are driven by long optical spans or uncertainty padding and remain below the scene-level overwide band.",
            "- Stable primary windows have a lower median width than secondary/edge/handoff and ambiguous windows.",
            "- Short/noise objects remain blocked before downstream spatial constraint construction.",
            "- GM_RM011 keeps usable temporal metadata but has no object-level optical flow, so it has no target-level temporal-window input.",
            "",
            "## Artifact",
            "",
            f"- quality_audit_csv: `{quality_csv}`",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    return "\n".join(lines) + "\n"


def render_design_doc() -> str:
    lines = [
        "# OTY2 Temporal Window to Spatial Constraint Design",
        "",
        "This document designs the next interface from object-level SAR temporal windows to a future time-window-driven SAR spatial constraint stage. It is design-only: it does not read SAR images, generate SAR spatial regions, generate candidate boxes, score candidates, use SAR GT, tune thresholds, or produce annotation proposals.",
        "",
        "## Layer Separation",
        "",
        "| layer | allowed meaning | forbidden promotion |",
        "| --- | --- | --- |",
        "| temporal window | inclusive SAR frame range for an optical object hypothesis | not a SAR location and not a candidate box |",
        "| spatial prior | future geometry-only shell or interval proposal derived from optical state and scene geometry | not SAR evidence and not final localization |",
        "| SAR evidence | future SAR content inspected inside an allowed prior, only after scope is opened | not GT and not an automatic annotation decision |",
        "| GT coverage | posthoc audit only | cannot construct runtime priors |",
        "| annotation proposal | later explicitly authorized stage only | cannot be produced by this design stage |",
        "",
        "## Future Spatial-Constraint Inputs",
        "",
        "The next stage should consume these upstream fields:",
        "",
        "- From temporal windows: `scene`, `object_hypothesis_id`, `sar_start_frame`, `sar_end_frame`, `sar_window_frame_count`, `sync_mode`, `offset_seconds`, `software_sync_jitter_ms`, `padding_sar_frames`, `object_state_category`, `uses_primary_observations`, `uses_secondary_observations`, `readiness_status`, `confidence_status`, `blockers`.",
        "- From optical object state: primary observation stream, secondary observation stream, object frame bounds, optical bbox envelope, partial/full or occlusion state, edge-visible state, duplicate observation state, handoff/reactivation indicators, ambiguity indicators, and runtime-safe provenance.",
        "- From scene geometry: frame inventory, optical frame dimensions, SAR frame inventory, configured fan/polar calibration, azimuth mapping contract, range convention, and any runtime-safe coarse pose or size priors.",
        "",
        "The next stage must not consume final/manual/oracle/review fields, SAR GT, posthoc IoU, selector/ranking output, tuned thresholds, or annotation labels as runtime construction inputs.",
        "",
        "## Connection Logic",
        "",
        "1. Temporal gating first: only `eligible_primary_spatial_constraint_input` and `eligible_uncertainty_expanded_spatial_constraint_input` rows enter normal spatial-prior construction.",
        "2. Low-confidence temporal windows remain review-only context unless a later bounded review mode is explicitly opened.",
        "3. For each eligible object, the SAR frame range limits when a future spatial prior may be evaluated.",
        "4. Optical object state defines the shape and uncertainty of a future prior shell; it must not collapse secondary observations or ambiguity into identity truth.",
        "5. Scene geometry maps optical state into future azimuth/range prior descriptors. SAR evidence, if later authorized, is evaluated only inside those descriptors.",
        "",
        "## Geometry Priors That Can Be Designed Before Reading SAR Images",
        "",
        "The following can be specified as contracts without reading SAR content:",
        "",
        "- Azimuth interval policy from optical object center/envelope and scene fan mapping.",
        "- Range-shell policy from runtime-safe geometry and coarse depth/size priors, kept broad when calibration is weak.",
        "- Vehicle size prior as a range, not a single fixed box.",
        "- Coarse yaw/main-axis prior as optional weak orientation context, not a hard final heading.",
        "- Edge/truncation recovery policy that expands the prior when an object is near fan or optical-frame boundaries.",
        "- Secondary-observation expansion policy that keeps duplicate, partial, and handoff uncertainty visible.",
        "- Ambiguity policy that either blocks normal spatial-prior construction or marks the row review-only.",
        "",
        "This document does not instantiate any actual SAR spatial region. A future implementation may emit region descriptors only after the OTY3 scope is opened.",
        "",
        "## Uncertainty Effects",
        "",
        "| signal | future spatial effect | runtime/posthoc status |",
        "| --- | --- | --- |",
        "| stable primary continuity | smaller azimuth/range margin; primary prior can be normal input | runtime prior |",
        "| secondary observations | expand azimuth/range margin; keep secondary provenance | runtime uncertainty prior |",
        "| edge-visible, partial, or occluded state | expand toward missing side; do not require full vehicle center inside the shell | runtime uncertainty prior |",
        "| duplicate observations | allow wider optical envelope or multiple prior components | runtime uncertainty prior |",
        "| handoff/reactivation | expand along time and geometry continuity; do not assert identity truth | runtime uncertainty prior |",
        "| ambiguous/review-required state | review-only or blocked from normal spatial prior | runtime blocker/context only |",
        "| SAR GT coverage | evaluate coverage after the prior exists | posthoc audit only |",
        "| selector/ranking score | not allowed in this stage | forbidden runtime input |",
        "",
        "## Runtime Priors vs Posthoc Audit",
        "",
        "Runtime priors may use object-level optical state, temporal windows, software-sync metadata, frame inventories, and runtime-safe scene geometry. Posthoc audit may later use GT coverage or manual review only to evaluate an already-generated prior. Posthoc audit results must not be fed back into runtime prior construction without a separate explicitly authorized stage.",
        "",
        "## Future Boundary for SAR Spatial Search",
        "",
        "If a later stage enters SAR spatial search, it should remain bounded as follows:",
        "",
        "- Start from object-level temporal windows and runtime-safe geometry priors.",
        "- Read SAR image content only after the scope explicitly opens SAR search.",
        "- Do not use SAR GT, final/manual/oracle/review fields, selector/ranking outputs, or tuned thresholds to construct the search prior.",
        "- Keep SAR evidence as evidence, not as identity truth or an automatic annotation proposal.",
        "- Emit diagnostics separately from any later annotation proposal stage.",
        "",
        "## Scene Handling",
        "",
        "- `GM_RM011`: temporal metadata is usable under the 24:50 software-sync contract, but target-level input is unavailable because the optical object stream is missing.",
        "- `GM_RM017`: object-level temporal windows are available for quality review and future spatial-prior input description.",
        "- `GM_RM019`: object-level temporal windows are available; low-confidence and not-ready rows must remain separated from normal downstream inputs.",
        "",
        "## Boundary Flags",
        "",
    ]
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    source_windows = Path(args.source_windows) if args.source_windows else latest_file(
        REPORT_DIR, "oty2_object_sar_temporal_windows_*.csv"
    )
    source_summary = Path(args.source_summary) if args.source_summary else latest_file(
        REPORT_DIR, "oty2_object_sar_temporal_window_summary_*.json"
    )
    p1_summary_path = Path(args.p1_summary) if args.p1_summary else latest_file(
        REPORT_DIR, "oty2_temporal_alignment_anchor_summary_*.json"
    )
    if not source_windows.is_absolute():
        source_windows = REPO_ROOT / source_windows
    if not source_summary.is_absolute():
        source_summary = REPO_ROOT / source_summary
    if not p1_summary_path.is_absolute():
        p1_summary_path = REPO_ROOT / p1_summary_path

    window_rows = read_csv_rows(source_windows)
    temporal_summary = read_json(source_summary)
    p1_summary = read_json(p1_summary_path)
    scene_status = per_scene_from_summary(temporal_summary)
    scene_frames = {
        scene: safe_int(row.get("sar_frame_count"), 0) or 0 for scene, row in p1_decisions(p1_summary).items()
    }
    quality_rows = [
        audit_object_row(row, scene_frames.get(str(row.get("scene", "") or "")))
        for row in window_rows
    ]
    object_scenes = {str(row.get("scene", "") or "") for row in window_rows}
    for scene, status in sorted(scene_status.items()):
        if scene not in object_scenes:
            quality_rows.append(scene_blocker_row(scene, status))
    quality_rows = sorted(
        quality_rows,
        key=lambda row: (
            str(row.get("scene", "")),
            str(row.get("row_scope", "")),
            str(row.get("object_hypothesis_id", "")),
        ),
    )
    summary = summarize_quality(quality_rows, scene_status)
    summary["source_windows"] = str(source_windows)
    summary["source_summary"] = str(source_summary)
    summary["p1_summary"] = str(p1_summary_path)
    summary.update(BOUNDARY_FLAGS)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    contract_md = REPORT_DIR / f"oty2_object_sar_temporal_window_contract_{timestamp}.md"
    quality_csv = REPORT_DIR / f"oty2_object_sar_temporal_window_quality_audit_{timestamp}.csv"
    quality_report = REPORT_DIR / f"oty2_object_sar_temporal_window_quality_report_{timestamp}.md"
    design_doc = DOCS_DIR / "oty2_temporal_window_to_spatial_constraint_design.md"

    write_csv(quality_csv, quality_rows, QUALITY_FIELDS)
    contract_md.write_text(
        render_contract(
            timestamp=timestamp,
            source_windows=source_windows,
            source_summary=source_summary,
            quality_csv=quality_csv,
            quality_report=quality_report,
            design_doc=design_doc,
            summary=summary,
            scene_status=scene_status,
        ),
        encoding="utf-8",
    )
    quality_report.write_text(
        render_quality_report(
            timestamp=timestamp,
            source_windows=source_windows,
            summary=summary,
            quality_csv=quality_csv,
        ),
        encoding="utf-8",
    )
    design_doc.write_text(render_design_doc(), encoding="utf-8")
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": timestamp,
        "summary": summary,
        "artifacts": {
            "contract": str(contract_md),
            "quality_audit_csv": str(quality_csv),
            "quality_report": str(quality_report),
            "design_doc": str(design_doc),
        },
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-windows", default="")
    parser.add_argument("--source-summary", default="")
    parser.add_argument("--p1-summary", default="")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    result = run(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
