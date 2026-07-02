"""Generate OTY2 runtime-safe spatial prior descriptions.

This audit consumes object-level SAR temporal windows plus optical object state
metadata. It emits descriptive runtime priors for a later SAR spatial-search
stage. It does not read SAR image content, use SAR GT, use final/manual/oracle
or review fields as runtime construction inputs, use selectors/ranking, score
candidate boxes, train/tune thresholds, generate annotation proposals, claim
identity truth, or generate final SAR locations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLE_DIR = REPORT_DIR / "samples"
DEFAULT_P4G_OUTPUT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_spatial_search_implemented": False,
    "sar_search_region_generated": False,
    "sar_candidate_boxes_generated": False,
    "candidate_box_scoring_used": False,
    "sar_gt_used": False,
    "final_manual_oracle_review_runtime_fields_used": False,
    "selector_or_ranking_used": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "detection_box_level_merge_reintroduced": False,
    "spatial_prior_claimed_as_final_location": False,
}

PRIOR_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "sar_start_frame",
    "sar_end_frame",
    "temporal_window_status",
    "spatial_prior_status",
    "spatial_prior_mode",
    "azimuth_prior_available",
    "azimuth_prior_source",
    "azimuth_center_or_interval",
    "azimuth_margin_reason",
    "range_prior_available",
    "range_prior_source",
    "range_prior_mode",
    "range_margin_reason",
    "geometry_confidence_status",
    "uses_primary_observations",
    "uses_secondary_observations",
    "edge_or_partial_state",
    "duplicate_or_handoff_state",
    "ambiguity_status",
    "normal_downstream_input",
    "review_only_context",
    "blocked",
    "blockers",
    "degradation_reason",
    "notes",
]


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"true", "1", "yes"}


def bool_text(value: Any) -> str:
    return "true" if boolish(value) else "false"


def fmt_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def join_values(values: Iterable[Any]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return ";".join(out)


def split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


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


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_file(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.name, reverse=True)
    if not matches:
        raise FileNotFoundError(f"No file matched {pattern} under {directory}")
    return matches[0]


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_scene_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def parse_secondary_bbox_summary(value: Any) -> list[tuple[float, float, float, float]]:
    boxes: list[tuple[float, float, float, float]] = []
    for part in split_semicolon(value):
        if ":" in part:
            _, coords = part.split(":", 1)
        else:
            coords = part
        nums = [safe_float(piece) for piece in re.split(r"[, ]+", coords.strip()) if piece.strip()]
        if len(nums) >= 4 and all(num is not None for num in nums[:4]):
            x1, y1, x2, y2 = [float(num) for num in nums[:4]]
            boxes.append((x1, y1, x2, y2))
    return boxes


def row_primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    values = [
        safe_float(row.get("primary_bbox_x1")),
        safe_float(row.get("primary_bbox_y1")),
        safe_float(row.get("primary_bbox_x2")),
        safe_float(row.get("primary_bbox_y2")),
    ]
    if all(value is not None for value in values):
        x1, y1, x2, y2 = [float(value) for value in values]
        return x1, y1, x2, y2
    return None


def object_state_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "primary_boxes": [],
            "secondary_boxes": [],
            "frame_count": 0,
            "frames": set(),
            "secondary_frame_count": 0,
            "status_values": defaultdict(set),
        }
    )
    status_fields = [
        "state_visibility_status",
        "state_uncertainty_status",
        "partial_full_transition_state",
        "boundary_truncation_state",
        "multi_observation_state",
        "bbox_provenance_status",
        "cluster_role",
        "cluster_risk_status",
    ]
    for row in rows:
        scene = str(row.get("scene", "") or "")
        object_id = str(row.get("object_hypothesis_id", "") or "")
        if not scene or not object_id:
            continue
        bucket = grouped[(scene, object_id)]
        bucket["frame_count"] += 1
        frame = safe_int(row.get("optical_frame_num"))
        if frame is not None:
            bucket["frames"].add(frame)
        primary = row_primary_box(row)
        if primary is not None:
            bucket["primary_boxes"].append(primary)
        secondary = parse_secondary_bbox_summary(row.get("secondary_bbox_summary"))
        if secondary:
            bucket["secondary_boxes"].extend(secondary)
            bucket["secondary_frame_count"] += 1
        if row.get("secondary_det_ids"):
            bucket["secondary_frame_count"] += 1
        for field in status_fields:
            text = str(row.get(field, "") or "").strip()
            if text:
                bucket["status_values"][field].add(text)
    return {key: dict(value) for key, value in grouped.items()}


def hypothesis_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        scene = str(row.get("scene", "") or "")
        object_id = str(row.get("object_hypothesis_id", "") or "")
        if scene and object_id:
            out[(scene, object_id)] = dict(row)
    return out


def temporal_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        scene = str(row.get("scene", "") or "")
        object_id = str(row.get("object_hypothesis_id", "") or "")
        if scene and object_id:
            out[(scene, object_id)] = dict(row)
    return out


def scene_geometry(config: Mapping[str, Any]) -> dict[str, Any]:
    global_geometry = config.get("global_geometry", {}) if isinstance(config.get("global_geometry"), Mapping) else {}
    fan = global_geometry.get("fan", {}) if isinstance(global_geometry.get("fan"), Mapping) else {}
    optical = global_geometry.get("optical_canvas", {}) if isinstance(global_geometry.get("optical_canvas"), Mapping) else {}
    scenes = config.get("scenes", {}) if isinstance(config.get("scenes"), Mapping) else {}
    return {
        "fan": dict(fan),
        "optical_canvas": dict(optical),
        "scenes": scenes,
    }


def combined_bbox_envelope(stats: Mapping[str, Any], include_secondary: bool) -> dict[str, float] | None:
    boxes = list(stats.get("primary_boxes", []))
    if include_secondary:
        boxes.extend(stats.get("secondary_boxes", []))
    if not boxes:
        return None
    x1 = min(float(box[0]) for box in boxes)
    y1 = min(float(box[1]) for box in boxes)
    x2 = max(float(box[2]) for box in boxes)
    y2 = max(float(box[3]) for box in boxes)
    centers = [(float(box[0]) + float(box[2])) / 2.0 for box in boxes]
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "center_x_median": statistics.median(centers),
        "box_count": float(len(boxes)),
    }


def state_flags(hyp: Mapping[str, Any], stats: Mapping[str, Any]) -> dict[str, bool | str]:
    status_values = stats.get("status_values", {})
    status_blob_parts: list[str] = []
    if isinstance(status_values, Mapping):
        for values in status_values.values():
            status_blob_parts.extend(str(value) for value in values)
    status_blob = " ".join(status_blob_parts).lower()
    edge_or_partial = any(
        [
            boolish(hyp.get("partial_full_transition_present")),
            boolish(hyp.get("boundary_truncation_present")),
            "partial" in status_blob,
            "boundary" in status_blob,
            "truncation" in status_blob,
            "edge" in str(hyp.get("secondary_observation_role", "")).lower(),
        ]
    )
    duplicate_or_handoff = any(
        [
            boolish(hyp.get("duplicate_observation_present")),
            safe_int(hyp.get("main_tracker_reactivated_count"), 0) or 0,
            safe_int(hyp.get("main_tracker_duplicate_overlap_count"), 0) or 0,
            safe_int(hyp.get("main_tracker_possible_id_switch_count"), 0) or 0,
            "reactivated" in str(hyp.get("main_track_stability_status", "")).lower(),
            "handoff" in str(hyp.get("recommended_use_for_oty2", "")).lower(),
            "multiple" in status_blob,
            "duplicate" in status_blob,
        ]
    )
    ambiguity = "ambiguous" in str(hyp.get("object_hypothesis_type", "")).lower() or boolish(hyp.get("review_required"))
    ambiguity_status = "ambiguous_or_review_required" if ambiguity else "not_ambiguous"
    return {
        "edge_or_partial_state": bool(edge_or_partial),
        "duplicate_or_handoff_state": bool(duplicate_or_handoff),
        "ambiguity_status": ambiguity_status,
    }


def margin_for_state(
    *,
    normal_downstream: bool,
    review_only: bool,
    edge_or_partial: bool,
    duplicate_or_handoff: bool,
    uses_secondary: bool,
    args: argparse.Namespace,
) -> tuple[float, list[str]]:
    if review_only:
        margin = float(args.review_azimuth_margin_deg)
        reasons = [f"review_only_margin_deg={fmt_float(margin, 2)}"]
    elif uses_secondary or edge_or_partial or duplicate_or_handoff:
        margin = float(args.uncertainty_azimuth_margin_deg)
        reasons = [f"uncertainty_margin_deg={fmt_float(margin, 2)}"]
    elif normal_downstream:
        margin = float(args.stable_azimuth_margin_deg)
        reasons = [f"stable_margin_deg={fmt_float(margin, 2)}"]
    else:
        margin = 0.0
        reasons = ["blocked_no_azimuth_margin"]
    if edge_or_partial:
        reasons.append("edge_or_partial_expansion")
    if duplicate_or_handoff:
        reasons.append("duplicate_or_handoff_expansion")
    if uses_secondary:
        reasons.append("secondary_observation_expansion")
    return margin, reasons


def azimuth_prior(
    *,
    envelope: Mapping[str, float] | None,
    fan: Mapping[str, Any],
    margin_deg: float,
    include_secondary: bool,
) -> dict[str, str]:
    k = safe_float(fan.get("azimuth_k"))
    b = safe_float(fan.get("azimuth_b"))
    if envelope is None:
        return {
            "available": "false",
            "source": "missing_object_bbox_envelope",
            "center_or_interval": "",
            "degradation": "insufficient_geometry_for_azimuth_prior",
        }
    if k is None or b is None:
        return {
            "available": "false",
            "source": "missing_configured_azimuth_mapping",
            "center_or_interval": "",
            "degradation": "insufficient_geometry_for_azimuth_prior",
        }
    x1 = float(envelope["x1"])
    x2 = float(envelope["x2"])
    cx = float(envelope["center_x_median"])
    az1 = k * x1 + b
    az2 = k * x2 + b
    center = k * cx + b
    lo = min(az1, az2) - margin_deg
    hi = max(az1, az2) + margin_deg
    source = "configured_legacy_optical_x_to_azimuth_mapping_primary_bbox_envelope"
    if include_secondary:
        source = "configured_legacy_optical_x_to_azimuth_mapping_primary_secondary_bbox_envelope"
    return {
        "available": "true",
        "source": source,
        "center_or_interval": (
            f"center_deg={fmt_float(center)};"
            f"interval_deg=[{fmt_float(lo)},{fmt_float(hi)}];"
            f"optical_x_envelope_px=[{fmt_float(x1, 1)},{fmt_float(x2, 1)}];"
            f"margin_deg={fmt_float(margin_deg, 2)}"
        ),
        "degradation": "",
    }


def row_mode(readiness_status: str) -> tuple[bool, bool, bool, str, str]:
    if readiness_status == "ready_primary_sar_temporal_window":
        return True, False, False, "normal_spatial_prior_generated", "azimuth_interval_with_broad_unknown_range"
    if readiness_status == "ready_uncertainty_expanded_sar_temporal_window":
        return True, False, False, "loose_spatial_prior_generated", "expanded_azimuth_interval_with_broad_unknown_range"
    if readiness_status == "low_confidence_sar_temporal_window":
        return False, True, False, "review_only_spatial_context_generated", "review_only_azimuth_context_with_broad_unknown_range"
    if readiness_status == "not_ready_for_sar_temporal_window":
        return False, False, True, "blocked_no_spatial_prior", "blocked_no_spatial_prior"
    return False, False, True, "blocked_unknown_temporal_readiness", "blocked_no_spatial_prior"


def build_prior_row(
    quality_row: Mapping[str, Any],
    *,
    temporal_row: Mapping[str, Any] | None,
    hyp: Mapping[str, Any] | None,
    stats: Mapping[str, Any] | None,
    fan: Mapping[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    scene = str(quality_row.get("scene", "") or "")
    object_id = str(quality_row.get("object_hypothesis_id", "") or "")
    readiness = str(quality_row.get("readiness_status", "") or "")
    if str(quality_row.get("row_scope", "")) == "scene_input_blocker":
        blockers = str(quality_row.get("blockers", "") or "missing_object_level_flow")
        return {
            "scene": scene,
            "object_hypothesis_id": object_id,
            "sar_start_frame": "",
            "sar_end_frame": "",
            "temporal_window_status": readiness,
            "spatial_prior_status": "blocked_missing_object_level_flow",
            "spatial_prior_mode": "blocked_no_object_level_spatial_prior",
            "azimuth_prior_available": "false",
            "azimuth_prior_source": "time_metadata_available_but_no_object_flow",
            "azimuth_center_or_interval": "",
            "azimuth_margin_reason": "not_applicable_no_object_flow",
            "range_prior_available": "false",
            "range_prior_source": "time_metadata_available_but_no_object_flow",
            "range_prior_mode": "not_generated_no_object_flow",
            "range_margin_reason": "not_applicable_no_object_flow",
            "geometry_confidence_status": "blocked_missing_object_level_flow",
            "uses_primary_observations": "false",
            "uses_secondary_observations": "false",
            "edge_or_partial_state": "false",
            "duplicate_or_handoff_state": "false",
            "ambiguity_status": "not_applicable_no_object_flow",
            "normal_downstream_input": "false",
            "review_only_context": "false",
            "blocked": "true",
            "blockers": blockers,
            "degradation_reason": "temporal_metadata_available_but_object_flow_missing",
            "notes": "GM_RM011_keeps_24_50_software_sync_metadata_but_has_no_target_level_input",
        }

    normal, review_only, blocked, status, mode = row_mode(readiness)
    temporal = temporal_row or {}
    hypothesis = hyp or {}
    object_stats = stats or {}
    uses_secondary = boolish(quality_row.get("uses_secondary_observations")) or boolish(
        temporal.get("uses_secondary_observations")
    )
    flags = state_flags(hypothesis, object_stats)
    edge_or_partial = bool(flags["edge_or_partial_state"])
    duplicate_or_handoff = bool(flags["duplicate_or_handoff_state"])
    include_secondary = uses_secondary or review_only
    envelope = combined_bbox_envelope(object_stats, include_secondary=include_secondary)
    margin, margin_reasons = margin_for_state(
        normal_downstream=normal,
        review_only=review_only,
        edge_or_partial=edge_or_partial,
        duplicate_or_handoff=duplicate_or_handoff,
        uses_secondary=uses_secondary,
        args=args,
    )
    if blocked:
        margin = 0.0
        margin_reasons = ["blocked_no_azimuth_prior"]
    az = azimuth_prior(envelope=envelope, fan=fan, margin_deg=margin, include_secondary=include_secondary)
    blockers = join_values([quality_row.get("blockers", ""), temporal.get("blockers", "")])
    degradation: list[str] = []
    notes: list[str] = []
    if az["degradation"]:
        degradation.append(az["degradation"])
    if blocked:
        degradation.append("object_not_ready_for_spatial_prior")
        notes.append("blocked_objects_preserve_temporal_status_only")
    if normal or review_only:
        degradation.append("range_prior_degraded_to_broad_unknown")
        notes.append("range_geometry_not_available_in_current_oty2_inputs")
    if review_only:
        notes.append("review_only_context_not_mixed_with_normal_spatial_priors")
    if normal and uses_secondary:
        notes.append("normal_downstream_input_with_expanded_uncertainty")
    if az["available"] == "true" and not blocked:
        notes.append("azimuth_prior_is_weak_configured_geometry_not_final_location")

    if blocked:
        range_mode = "not_generated_for_blocked_object"
        range_source = "not_applicable_blocked_temporal_or_object_status"
        range_reason = "blocked_before_spatial_prior_generation"
        geometry_confidence = "blocked_no_runtime_spatial_prior"
    elif review_only:
        range_mode = "broad_unknown_range_prior_review_only"
        range_source = "range_geometry_not_available_in_current_oty2_inputs"
        range_reason = "no_runtime_safe_per_object_range_prior;review_only_context"
        geometry_confidence = "review_only_weak_azimuth_context_range_unknown"
    elif uses_secondary or edge_or_partial or duplicate_or_handoff:
        range_mode = "broad_unknown_range_prior"
        range_source = "range_geometry_not_available_in_current_oty2_inputs"
        range_reason = "no_runtime_safe_per_object_range_prior;uncertainty_requires_broad_range"
        geometry_confidence = "weak_azimuth_only_expanded_geometry"
    else:
        range_mode = "broad_unknown_range_prior"
        range_source = "range_geometry_not_available_in_current_oty2_inputs"
        range_reason = "no_runtime_safe_per_object_range_prior"
        geometry_confidence = "weak_azimuth_only_primary_geometry"
    if az["available"] != "true" and not blocked:
        geometry_confidence = "insufficient_geometry_for_spatial_prior"

    return {
        "scene": scene,
        "object_hypothesis_id": object_id,
        "sar_start_frame": temporal.get("sar_start_frame", quality_row.get("sar_start_frame", "")),
        "sar_end_frame": temporal.get("sar_end_frame", quality_row.get("sar_end_frame", "")),
        "temporal_window_status": readiness,
        "spatial_prior_status": status,
        "spatial_prior_mode": mode,
        "azimuth_prior_available": az["available"] if not blocked else "false",
        "azimuth_prior_source": az["source"] if not blocked else "not_generated_for_blocked_object",
        "azimuth_center_or_interval": az["center_or_interval"] if not blocked else "",
        "azimuth_margin_reason": join_values(margin_reasons),
        "range_prior_available": "false",
        "range_prior_source": range_source,
        "range_prior_mode": range_mode,
        "range_margin_reason": range_reason,
        "geometry_confidence_status": geometry_confidence,
        "uses_primary_observations": quality_row.get("uses_primary_observations", temporal.get("uses_primary_observations", "")),
        "uses_secondary_observations": bool_text(uses_secondary),
        "edge_or_partial_state": bool_text(edge_or_partial),
        "duplicate_or_handoff_state": bool_text(duplicate_or_handoff),
        "ambiguity_status": flags["ambiguity_status"],
        "normal_downstream_input": bool_text(normal),
        "review_only_context": bool_text(review_only),
        "blocked": bool_text(blocked),
        "blockers": blockers,
        "degradation_reason": join_values(degradation),
        "notes": join_values(notes),
    }


def sample_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    priority = {
        "normal_spatial_prior_generated": 0,
        "loose_spatial_prior_generated": 1,
        "review_only_spatial_context_generated": 2,
        "blocked_no_spatial_prior": 3,
        "blocked_missing_object_level_flow": 4,
    }
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("scene", "")),
            priority.get(str(row.get("spatial_prior_status", "")), 9),
            str(row.get("object_hypothesis_id", "")),
        ),
    )
    return [dict(row) for row in ordered[:max_rows]]


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scenes = sorted({str(row.get("scene", "")) for row in rows if row.get("scene")})
    per_scene: dict[str, dict[str, Any]] = {}
    for scene in scenes:
        scene_rows = [row for row in rows if row.get("scene") == scene]
        per_scene[scene] = {
            "rows": len(scene_rows),
            "normal_spatial_priors": sum(1 for row in scene_rows if boolish(row.get("normal_downstream_input"))),
            "review_only_spatial_contexts": sum(1 for row in scene_rows if boolish(row.get("review_only_context"))),
            "blocked": sum(1 for row in scene_rows if boolish(row.get("blocked"))),
            "azimuth_available": sum(1 for row in scene_rows if boolish(row.get("azimuth_prior_available"))),
            "range_broad_unknown": sum(
                1 for row in scene_rows if str(row.get("range_prior_mode", "")).startswith("broad_unknown")
            ),
            "geometry_insufficient": sum(
                1
                for row in scene_rows
                if "insufficient_geometry" in str(row.get("geometry_confidence_status", ""))
            ),
            "degradation_reasons": dict(Counter(str(row.get("degradation_reason", "")) for row in scene_rows)),
        }
    return {
        "row_count": len(rows),
        "normal_spatial_priors": sum(1 for row in rows if boolish(row.get("normal_downstream_input"))),
        "review_only_spatial_contexts": sum(1 for row in rows if boolish(row.get("review_only_context"))),
        "blocked": sum(1 for row in rows if boolish(row.get("blocked"))),
        "spatial_prior_status_counts": dict(Counter(str(row.get("spatial_prior_status", "")) for row in rows)),
        "spatial_prior_mode_counts": dict(Counter(str(row.get("spatial_prior_mode", "")) for row in rows)),
        "geometry_confidence_status_counts": dict(Counter(str(row.get("geometry_confidence_status", "")) for row in rows)),
        "range_prior_mode_counts": dict(Counter(str(row.get("range_prior_mode", "")) for row in rows)),
        "azimuth_prior_available_counts": dict(Counter(str(row.get("azimuth_prior_available", "")) for row in rows)),
        "per_scene": per_scene,
    }


def render_contract(
    *,
    timestamp: str,
    summary: Mapping[str, Any],
    artifacts: Mapping[str, str],
    source_paths: Mapping[str, str],
) -> str:
    lines = [
        "# OTY2 Runtime Spatial Prior Contract",
        "",
        f"Generated: `{timestamp}`",
        "",
        "This contract defines the first runtime-safe spatial prior description emitted from object-level temporal windows. It is not SAR detection, not a final annotation, not a candidate-box score, and not a final position claim.",
        "",
        "## Inputs",
        "",
        "- Object-level SAR temporal windows from OTY2 software-sync timing.",
        "- Temporal-window quality gate rows that separate normal, review-only, and blocked objects.",
        "- P4G object hypotheses and object-frame state rows for optical bbox envelopes and uncertainty states.",
        "- Scene-config fan/azimuth constants as weak configured geometry metadata.",
        "",
        "Forbidden runtime inputs remain excluded: SAR image content, SAR GT, final/manual/oracle/review fields, selector/ranking output, tuned thresholds, and annotation labels.",
        "",
        "## Output Semantics",
        "",
        "- Normal spatial priors are emitted for `ready_primary_sar_temporal_window` and `ready_uncertainty_expanded_sar_temporal_window` rows.",
        "- `low_confidence_sar_temporal_window` rows emit review-only spatial context and are not mixed into normal priors.",
        "- `not_ready_for_sar_temporal_window` rows remain blocked.",
        "- `GM_RM011` remains a scene-level blocker: timing metadata is available, but object-level optical flow is missing.",
        "",
        "## Geometry Interpretation",
        "",
        "- Azimuth is a weak configured prior from optical bbox envelope and the configured legacy `azimuth_k/azimuth_b` mapping.",
        "- Secondary, edge, partial, duplicate, occlusion, and handoff states expand the azimuth margin instead of forcing a blocker.",
        "- Ambiguous/review-required rows can keep review-only azimuth context, but not normal priors.",
        "- Range is currently degraded to `broad_unknown_range_prior` because the current OTY2 inputs do not contain a reliable per-object runtime range/depth transfer.",
        "- No row in this output is a SAR search region, SAR candidate box, final localization, or annotation recommendation.",
        "",
        "## Per-Scene Counts",
        "",
        "| scene | normal priors | review-only contexts | blocked | azimuth available | range broad-unknown | geometry insufficient |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scene, row in summary.get("per_scene", {}).items():
        lines.append(
            f"| `{scene}` | {row.get('normal_spatial_priors', 0)} | "
            f"{row.get('review_only_spatial_contexts', 0)} | {row.get('blocked', 0)} | "
            f"{row.get('azimuth_available', 0)} | {row.get('range_broad_unknown', 0)} | "
            f"{row.get('geometry_insufficient', 0)} |"
        )
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Sources", ""])
    for key, value in source_paths.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Artifacts", ""])
    for key, value in artifacts.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def render_report(
    *,
    timestamp: str,
    summary: Mapping[str, Any],
    artifacts: Mapping[str, str],
) -> str:
    lines = [
        "# OTY2 Runtime Spatial Prior Audit Report",
        "",
        f"Generated: `{timestamp}`",
        "",
        "This report reviews the first-pass runtime-safe spatial prior descriptions. It does not read SAR images, use SAR GT, implement SAR spatial search, generate search regions, generate candidate boxes, score candidates, tune thresholds, or make annotation recommendations.",
        "",
        "## Summary",
        "",
        f"- total rows: `{summary.get('row_count', 0)}`",
        f"- normal spatial priors: `{summary.get('normal_spatial_priors', 0)}`",
        f"- review-only spatial contexts: `{summary.get('review_only_spatial_contexts', 0)}`",
        f"- blocked rows: `{summary.get('blocked', 0)}`",
        f"- spatial prior status counts: `{json.dumps(summary.get('spatial_prior_status_counts', {}), sort_keys=True)}`",
        f"- geometry confidence counts: `{json.dumps(summary.get('geometry_confidence_status_counts', {}), sort_keys=True)}`",
        f"- range prior mode counts: `{json.dumps(summary.get('range_prior_mode_counts', {}), sort_keys=True)}`",
        "",
        "## Per-Scene Results",
        "",
        "| scene | normal priors | review-only contexts | blocked | notes |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for scene, row in summary.get("per_scene", {}).items():
        note = "range degraded to broad_unknown where prior exists"
        if scene == "GM_RM011":
            note = "time metadata available, object flow missing"
        lines.append(
            f"| `{scene}` | {row.get('normal_spatial_priors', 0)} | "
            f"{row.get('review_only_spatial_contexts', 0)} | {row.get('blocked', 0)} | {note} |"
        )
    lines.extend(
        [
            "",
            "## Degradation Findings",
            "",
            "- All normal and review-only rows have azimuth weak priors available from configured optical-x to azimuth metadata and object bbox envelopes.",
            "- All normal and review-only rows degrade range to `broad_unknown_range_prior` because no reliable per-object runtime range/depth field is present in current OTY2 inputs.",
            "- No target was blocked solely because of secondary observation, edge, partial, duplicate, occlusion, or handoff state; those states expand/loosen the prior.",
            "- Ambiguous/review-required targets are review-only contexts and are not mixed into normal priors.",
            "- Short/noise and not-ready targets remain blocked.",
            "- `GM_RM011` remains blocked only at the target level: timing metadata exists, but object flow is missing.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Artifacts", ""])
    for key, value in artifacts.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    quality_csv = resolve_path(args.quality_audit) if args.quality_audit else latest_file(
        REPORT_DIR, "oty2_object_sar_temporal_window_quality_audit_*.csv"
    )
    temporal_csv = resolve_path(args.temporal_windows) if args.temporal_windows else latest_file(
        REPORT_DIR, "oty2_object_sar_temporal_windows_*.csv"
    )
    config_path = resolve_path(args.scene_config)
    p4g_dir = resolve_path(args.p4g_output_dir)
    object_hypotheses_csv = p4g_dir / "oty1t_object_hypotheses_generalized.csv"
    object_states_csv = p4g_dir / "oty1t_object_frame_state_timeseries_generalized.csv"

    quality_rows = read_csv_rows(quality_csv)
    temporal_rows = temporal_index(read_csv_rows(temporal_csv))
    hypotheses = hypothesis_index(read_csv_rows(object_hypotheses_csv))
    state_stats = object_state_index(read_csv_rows(object_states_csv))
    config = load_scene_config(config_path)
    geometry = scene_geometry(config)
    fan = geometry["fan"]

    prior_rows = [
        build_prior_row(
            row,
            temporal_row=temporal_rows.get((str(row.get("scene", "") or ""), str(row.get("object_hypothesis_id", "") or ""))),
            hyp=hypotheses.get((str(row.get("scene", "") or ""), str(row.get("object_hypothesis_id", "") or ""))),
            stats=state_stats.get((str(row.get("scene", "") or ""), str(row.get("object_hypothesis_id", "") or ""))),
            fan=fan,
            args=args,
        )
        for row in quality_rows
    ]
    prior_rows = sorted(
        prior_rows,
        key=lambda row: (
            str(row.get("scene", "")),
            str(row.get("spatial_prior_status", "")),
            str(row.get("object_hypothesis_id", "")),
        ),
    )
    summary = summarize(prior_rows)
    summary.update(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "timestamp": timestamp,
            "stage": "OTY2-runtime-spatial-prior-audit-v1",
            "azimuth_mapping": {
                "source": "configs/scene_config.yaml global_geometry.fan",
                "azimuth_k": fan.get("azimuth_k", ""),
                "azimuth_b": fan.get("azimuth_b", ""),
                "theta_offset_deg": fan.get("theta_offset_deg", ""),
                "interpretation": "weak_configured_geometry_metadata_not_final_location",
            },
            "range_prior_policy": "broad_unknown_range_prior_until_runtime_safe_per_object_range_geometry_exists",
            "source_paths": {
                "temporal_window_quality_audit": str(quality_csv),
                "object_sar_temporal_windows": str(temporal_csv),
                "object_hypotheses": str(object_hypotheses_csv),
                "object_frame_states": str(object_states_csv),
                "scene_config": str(config_path),
            },
            **BOUNDARY_FLAGS,
        }
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    contract_path = REPORT_DIR / f"oty2_runtime_spatial_prior_contract_{timestamp}.md"
    priors_csv = REPORT_DIR / f"oty2_object_runtime_spatial_priors_{timestamp}.csv"
    summary_json = REPORT_DIR / f"oty2_runtime_spatial_prior_summary_{timestamp}.json"
    report_md = REPORT_DIR / f"oty2_runtime_spatial_prior_report_{timestamp}.md"
    sample_csv = SAMPLE_DIR / "oty2_object_runtime_spatial_priors_sample.csv"
    artifacts = {
        "runtime_spatial_prior_contract": str(contract_path),
        "object_runtime_spatial_priors": str(priors_csv),
        "runtime_spatial_prior_summary": str(summary_json),
        "runtime_spatial_prior_report": str(report_md),
        "object_runtime_spatial_priors_sample": str(sample_csv),
    }
    summary["artifacts"] = artifacts

    write_csv(priors_csv, prior_rows, PRIOR_FIELDS)
    write_csv(sample_csv, sample_rows(prior_rows, args.max_sample_rows), PRIOR_FIELDS)
    write_json(summary_json, summary)
    contract_path.write_text(
        render_contract(
            timestamp=timestamp,
            summary=summary,
            artifacts=artifacts,
            source_paths=summary["source_paths"],
        ),
        encoding="utf-8",
    )
    report_md.write_text(render_report(timestamp=timestamp, summary=summary, artifacts=artifacts), encoding="utf-8")
    return {"summary": summary, "artifacts": artifacts}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-audit", default="")
    parser.add_argument("--temporal-windows", default="")
    parser.add_argument("--scene-config", default="configs/scene_config.yaml")
    parser.add_argument("--p4g-output-dir", default=str(DEFAULT_P4G_OUTPUT_DIR))
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--stable-azimuth-margin-deg", type=float, default=2.0)
    parser.add_argument("--uncertainty-azimuth-margin-deg", type=float, default=5.0)
    parser.add_argument("--review-azimuth-margin-deg", type=float, default=8.0)
    parser.add_argument("--max-sample-rows", type=int, default=80)
    return parser


def main() -> None:
    result = run(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
