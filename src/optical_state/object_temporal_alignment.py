"""Object-level OTY2-P0 temporal alignment audit helpers.

This module consumes OTY1t-P4G object-level optical outputs and prepares
temporal frame/window candidates only. It does not read SAR image content, use
SAR GT, create SAR spatial bands, score SAR evidence, run selectors, train
models, or create annotation proposals.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from html import escape as html_escape
from pathlib import Path
from typing import Any, Mapping, Sequence


RUNTIME_SOURCE_POLICY = (
    "oty2_p0_runtime_safe_object_temporal_alignment_no_sar_image_no_gt_no_selector"
)

BOUNDARY_FLAGS: dict[str, bool] = {
    "posthoc_sources_used_for_runtime_tracking": False,
    "sar_image_content_used": False,
    "sar_gt_coverage_entered": False,
    "sar_band_entered": False,
    "annotation_proposal_entered": False,
    "identity_truth_claimed": False,
}

SCENE_INPUT_STATUS_FIELDS = [
    "scene",
    "oty0_available",
    "oty1_available",
    "oty1a_available",
    "oty1t_available",
    "p4g_object_hypotheses_available",
    "p4g_object_frame_states_available",
    "optical_frame_inventory_available",
    "sar_frame_inventory_available",
    "timestamp_metadata_available",
    "input_status",
    "blocker_reason",
    "optical_frame_count",
    "sar_frame_count",
    "timestamp_metadata_source",
    "alignment_inventory_policy",
]

OBJECT_READINESS_GATING_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "main_tracker_track_id",
    "frame_start",
    "frame_end",
    "object_hypothesis_type",
    "same_object_support_level",
    "main_track_stability_status",
    "recommended_use_for_oty2",
    "identity_status",
    "review_required",
    "orphan_conflict_count",
    "shared_secondary_detection_count",
    "ambiguous_cluster_conflict_count",
    "oty2_gate",
    "alignment_confidence_prior",
    "uncertainty_policy",
    "reason",
    "runtime_source_policy",
]

OBJECT_ALIGNMENT_FRAME_MAP_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "optical_frame_num",
    "main_tracker_track_id",
    "primary_det_id",
    "secondary_det_ids",
    "state_visibility_status",
    "state_uncertainty_status",
    "recommended_oty2_weight",
    "oty2_gate",
    "alignment_mode",
    "alignment_confidence",
    "optical_time_proxy",
    "sar_frame_center_candidate",
    "sar_frame_window_start",
    "sar_frame_window_end",
    "uncertainty_frames",
    "window_reason",
    "runtime_source_policy",
]

OBJECT_ALIGNMENT_WINDOW_CANDIDATE_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "window_id",
    "object_frame_start",
    "object_frame_end",
    "primary_optical_frame_count",
    "secondary_hint_frame_count",
    "alignment_mode",
    "sar_window_start",
    "sar_window_end",
    "sar_window_center",
    "sar_window_size",
    "alignment_confidence",
    "uncertainty_policy",
    "review_required",
    "object_readiness_gate",
    "do_not_enter_sar_band",
    "reason",
]

MAPPABLE_GATES = {
    "use_as_primary_alignment_track",
    "use_with_uncertainty_expansion",
    "low_confidence_window_only",
}


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"true", "1", "yes"}


def fmt_bool(value: Any) -> str:
    return "true" if boolish(value) else "false"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def split_values(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.replace(",", ";").split(";") if item.strip()]


def unique_ordered(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def join_values(values: Sequence[Any]) -> str:
    return ";".join(unique_ordered(values))


def counter_as_dict(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field, "") or "unknown") for row in rows)
    return {key: counts[key] for key in sorted(counts)}


def count_files(path: str | Path | None) -> int:
    if not path:
        return 0
    root = Path(path)
    if not root.exists() or not root.is_dir():
        return 0
    return sum(1 for item in root.iterdir() if item.is_file())


def _scene_config(scene_config: Mapping[str, Any], scene: str) -> Mapping[str, Any]:
    scenes = scene_config.get("scenes", {})
    if isinstance(scenes, Mapping):
        item = scenes.get(scene, {})
        return item if isinstance(item, Mapping) else {}
    return {}


def _scene_paths(scene_config: Mapping[str, Any], scene: str) -> Mapping[str, Any]:
    item = _scene_config(scene_config, scene).get("paths", {})
    return item if isinstance(item, Mapping) else {}


def timestamp_metadata_status(scene_config: Mapping[str, Any], scene: str) -> tuple[bool, str]:
    scene_item = _scene_config(scene_config, scene)
    paths = _scene_paths(scene_config, scene)
    timestamp_keys = [
        "timestamp_metadata",
        "timestamp_metadata_path",
        "optical_timestamps",
        "sar_timestamps",
        "optical_timestamp_path",
        "sar_timestamp_path",
        "optical_fps",
        "sar_fps",
        "fps",
        "timebase",
    ]
    found: list[str] = []
    for key in timestamp_keys:
        if key in scene_item and str(scene_item.get(key, "") or "").strip():
            found.append(key)
        if key in paths and str(paths.get(key, "") or "").strip():
            found.append(f"paths.{key}")
    if found:
        return True, join_values(found)
    return False, "missing_exact_timestamp_metadata"


def build_scene_input_status_rows(
    *,
    scenes: Sequence[str],
    p4g_object_rows: Sequence[Mapping[str, Any]],
    p4g_frame_rows: Sequence[Mapping[str, Any]],
    stage_availability_by_scene: Mapping[str, Mapping[str, Any]],
    scene_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    object_scenes = {str(row.get("scene", "") or "") for row in p4g_object_rows}
    frame_scenes = {str(row.get("scene", "") or "") for row in p4g_frame_rows}
    rows: list[dict[str, Any]] = []
    for scene in unique_ordered(scenes):
        stage = stage_availability_by_scene.get(scene, {})
        paths = _scene_paths(scene_config, scene)
        optical_count = count_files(paths.get("optical_frames_dir"))
        sar_count = count_files(paths.get("sar_frames_dir"))
        timestamp_available, timestamp_source = timestamp_metadata_status(scene_config, scene)

        p4g_objects = scene in object_scenes
        p4g_frames = scene in frame_scenes
        optical_inventory = optical_count > 0
        sar_inventory = sar_count > 0
        blockers: list[str] = []
        if not boolish(stage.get("oty0_available")):
            blockers.append("missing_oty0")
        if not boolish(stage.get("oty1_available")):
            blockers.append("missing_oty1")
        if not boolish(stage.get("oty1a_available")):
            blockers.append("missing_oty1a")
        if not boolish(stage.get("oty1t_available")):
            blockers.append("missing_oty1t")
        if not p4g_objects:
            blockers.append("missing_p4g_object_hypotheses")
        if not p4g_frames:
            blockers.append("missing_p4g_object_frame_states")
        if not optical_inventory:
            blockers.append("missing_optical_frame_inventory")
        if not sar_inventory:
            blockers.append("missing_sar_frame_inventory")

        if not p4g_objects or not p4g_frames:
            input_status = "blocked_missing_p4g"
        elif not optical_inventory:
            input_status = "blocked_missing_optical_inventory"
        elif not sar_inventory:
            input_status = "blocked_missing_sar_inventory"
        elif not timestamp_available:
            input_status = "ready_with_uncertainty"
            blockers.append("missing_exact_timestamp_metadata")
            blockers.append("using_frame_ratio_hypothesis_audit_only")
        else:
            input_status = "ready_for_oty2_p0"

        if input_status == "ready_for_oty2_p0":
            blocker_reason = ""
            policy = "timestamp_metadata_available"
        elif input_status == "ready_with_uncertainty":
            blocker_reason = join_values(blockers)
            policy = "frame_ratio_hypothesis_audit_only"
        else:
            blocker_reason = join_values(blockers)
            policy = "blocked_before_temporal_alignment"

        rows.append(
            {
                "scene": scene,
                "oty0_available": fmt_bool(stage.get("oty0_available")),
                "oty1_available": fmt_bool(stage.get("oty1_available")),
                "oty1a_available": fmt_bool(stage.get("oty1a_available")),
                "oty1t_available": fmt_bool(stage.get("oty1t_available")),
                "p4g_object_hypotheses_available": fmt_bool(p4g_objects),
                "p4g_object_frame_states_available": fmt_bool(p4g_frames),
                "optical_frame_inventory_available": fmt_bool(optical_inventory),
                "sar_frame_inventory_available": fmt_bool(sar_inventory),
                "timestamp_metadata_available": fmt_bool(timestamp_available),
                "input_status": input_status,
                "blocker_reason": blocker_reason,
                "optical_frame_count": optical_count,
                "sar_frame_count": sar_count,
                "timestamp_metadata_source": timestamp_source,
                "alignment_inventory_policy": policy,
            }
        )
    return rows


def _object_conflict_indexes(
    object_rows: Sequence[Mapping[str, Any]],
    orphan_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    secondary_to_objects: dict[str, set[str]] = defaultdict(set)
    cluster_to_objects: dict[str, set[str]] = defaultdict(set)
    orphan_to_objects: dict[str, int] = defaultdict(int)
    object_secondary: dict[str, set[str]] = defaultdict(set)
    object_clusters: dict[str, set[str]] = defaultdict(set)

    for row in object_rows:
        obj_id = str(row.get("object_hypothesis_id", "") or "")
        if not obj_id:
            continue
        for det_id in split_values(row.get("secondary_det_ids")):
            secondary_to_objects[det_id].add(obj_id)
            object_secondary[obj_id].add(det_id)
        for cluster_id in split_values(row.get("primary_observation_cluster_ids")) + split_values(
            row.get("secondary_observation_cluster_ids")
        ):
            cluster_to_objects[cluster_id].add(obj_id)
            object_clusters[obj_id].add(cluster_id)

    for row in orphan_rows:
        for obj_id in split_values(row.get("candidate_object_hypothesis_ids")):
            orphan_to_objects[obj_id] += 1

    shared_secondary = {
        obj_id: sum(1 for det_id in det_ids if len(secondary_to_objects.get(det_id, set())) > 1)
        for obj_id, det_ids in object_secondary.items()
    }
    shared_clusters = {
        obj_id: sum(1 for cluster_id in cluster_ids if len(cluster_to_objects.get(cluster_id, set())) > 1)
        for obj_id, cluster_ids in object_clusters.items()
    }
    return dict(orphan_to_objects), shared_secondary, shared_clusters


def _gate_object(
    row: Mapping[str, Any],
    *,
    orphan_conflict_count: int,
    shared_secondary_detection_count: int,
    ambiguous_cluster_conflict_count: int,
) -> tuple[str, str, str, str]:
    recommended = str(row.get("recommended_use_for_oty2", "") or "")
    obj_type = str(row.get("object_hypothesis_type", "") or "")
    support = str(row.get("same_object_support_level", "") or "")
    stability = str(row.get("main_track_stability_status", "") or "")
    review = boolish(row.get("review_required"))
    conflicts = orphan_conflict_count + shared_secondary_detection_count + ambiguous_cluster_conflict_count

    if recommended == "do_not_use_for_oty2" or obj_type == "short_or_noise_track_hypothesis":
        return (
            "exclude_from_oty2",
            "blocked",
            "excluded",
            "P4G recommended do_not_use_for_oty2 or short/noise hypothesis; excluded before temporal mapping.",
        )
    if recommended == "main_track_only":
        if support == "strong" and stability == "stable_main_track" and not review and conflicts == 0:
            prior = "high"
            policy = "narrow_window"
            reason = "stable main-track-only object with no carried review flag or shared-conflict count."
        else:
            prior = "medium"
            policy = "standard_window"
            reason = "main-track-only object kept as primary, with standard uncertainty due support/stability/review context."
        return "use_as_primary_alignment_track", prior, policy, reason
    if recommended == "main_track_with_uncertainty_handoff":
        return (
            "use_with_uncertainty_expansion",
            "medium",
            "expanded_window",
            "P4G requested uncertainty handoff; primary continuity is kept and secondary observations expand the temporal window.",
        )
    if recommended == "optional_continuity_hint_with_visual_review":
        if not str(row.get("main_tracker_track_id", "") or "").strip():
            return (
                "blocked_pending_visual_review",
                "blocked",
                "review_only_window",
                "optional continuity hint lacks a main tracker track and must wait for visual review.",
            )
        return (
            "low_confidence_window_only",
            "low",
            "review_only_window",
            "optional continuity hint remains low-confidence; review_required does not confirm or deny identity.",
        )
    if "review" in recommended:
        return (
            "blocked_pending_visual_review",
            "blocked",
            "review_only_window",
            "unrecognized review-before-OTY2 recommendation; blocked pending visual review.",
        )
    return (
        "blocked_pending_visual_review" if review else "low_confidence_window_only",
        "blocked" if review else "low",
        "review_only_window",
        "fallback gate from P4G fields; identity_status is not treated as confirmed identity.",
    )


def build_object_readiness_gating_rows(
    *,
    object_rows: Sequence[Mapping[str, Any]],
    orphan_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    orphan_conflicts, shared_secondary, shared_clusters = _object_conflict_indexes(object_rows, orphan_rows)
    out: list[dict[str, Any]] = []
    for row in sorted(
        object_rows,
        key=lambda item: (str(item.get("scene", "")), safe_int(item.get("frame_start")), str(item.get("object_hypothesis_id", ""))),
    ):
        obj_id = str(row.get("object_hypothesis_id", "") or "")
        orphan_count = orphan_conflicts.get(obj_id, 0)
        shared_secondary_count = shared_secondary.get(obj_id, 0)
        cluster_conflict_count = shared_clusters.get(obj_id, 0)
        gate, prior, policy, reason = _gate_object(
            row,
            orphan_conflict_count=orphan_count,
            shared_secondary_detection_count=shared_secondary_count,
            ambiguous_cluster_conflict_count=cluster_conflict_count,
        )
        out.append(
            {
                "scene": row.get("scene", ""),
                "object_hypothesis_id": obj_id,
                "main_tracker_track_id": row.get("main_tracker_track_id", ""),
                "frame_start": row.get("frame_start", ""),
                "frame_end": row.get("frame_end", ""),
                "object_hypothesis_type": row.get("object_hypothesis_type", ""),
                "same_object_support_level": row.get("same_object_support_level", ""),
                "main_track_stability_status": row.get("main_track_stability_status", ""),
                "recommended_use_for_oty2": row.get("recommended_use_for_oty2", ""),
                "identity_status": row.get("identity_status", ""),
                "review_required": fmt_bool(row.get("review_required")),
                "orphan_conflict_count": orphan_count,
                "shared_secondary_detection_count": shared_secondary_count,
                "ambiguous_cluster_conflict_count": cluster_conflict_count,
                "oty2_gate": gate,
                "alignment_confidence_prior": prior,
                "uncertainty_policy": policy,
                "reason": reason,
                "runtime_source_policy": RUNTIME_SOURCE_POLICY,
            }
        )
    return out


def _alignment_mode(status_row: Mapping[str, Any]) -> str:
    if str(status_row.get("input_status", "") or "").startswith("blocked"):
        return "unknown_alignment"
    if boolish(status_row.get("timestamp_metadata_available")):
        return "timestamp_offset_scale"
    if safe_int(status_row.get("optical_frame_count")) > 0 and safe_int(status_row.get("sar_frame_count")) > 0:
        return "frame_ratio_hypothesis"
    return "unknown_alignment"


def _ratio_sar_frame(optical_frame: int, optical_count: int, sar_count: int) -> int:
    if optical_count <= 1:
        return 0
    center = round(optical_frame * (sar_count - 1) / (optical_count - 1))
    return max(0, min(sar_count - 1, center))


def _uncertainty_frames(policy: str, state_uncertainty: str, visibility: str, weight: str, mode: str) -> int:
    base_by_policy = {
        "narrow_window": 2,
        "standard_window": 4,
        "expanded_window": 8,
        "review_only_window": 12,
        "excluded": 0,
    }
    value = base_by_policy.get(policy, 6)
    if mode == "frame_ratio_hypothesis":
        value += 2
    if state_uncertainty == "high_uncertainty":
        value += 4
    elif state_uncertainty == "moderate_uncertainty":
        value += 2
    if visibility in {"missing_observation", "partial_secondary_observation"}:
        value += 3
    if weight == "secondary_hint_only":
        value += 2
    if weight == "do_not_use":
        value += 4
    return value


def _degrade_confidence(prior: str, mode: str, state_uncertainty: str, weight: str) -> str:
    if prior == "blocked" or mode == "unknown_alignment":
        return "blocked"
    if mode == "frame_ratio_hypothesis":
        if prior == "high":
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = prior if prior in {"high", "medium", "low"} else "low"
    if state_uncertainty == "high_uncertainty" or weight in {"secondary_hint_only", "do_not_use"}:
        return "low" if confidence != "blocked" else "blocked"
    return confidence


def build_object_alignment_frame_map_rows(
    *,
    frame_rows: Sequence[Mapping[str, Any]],
    gating_rows: Sequence[Mapping[str, Any]],
    scene_status_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gate_by_object = {str(row.get("object_hypothesis_id", "") or ""): row for row in gating_rows}
    status_by_scene = {str(row.get("scene", "") or ""): row for row in scene_status_rows}
    out: list[dict[str, Any]] = []
    for row in sorted(
        frame_rows,
        key=lambda item: (str(item.get("scene", "")), str(item.get("object_hypothesis_id", "")), safe_int(item.get("optical_frame_num"))),
    ):
        obj_id = str(row.get("object_hypothesis_id", "") or "")
        gate = gate_by_object.get(obj_id)
        if not gate or str(gate.get("oty2_gate", "")) not in MAPPABLE_GATES:
            continue
        scene = str(row.get("scene", "") or "")
        status = status_by_scene.get(scene, {})
        mode = _alignment_mode(status)
        optical_count = safe_int(status.get("optical_frame_count"))
        sar_count = safe_int(status.get("sar_frame_count"))
        optical_frame = safe_int(row.get("optical_frame_num"), default=-1)
        state_uncertainty = str(row.get("state_uncertainty_status", "") or "")
        visibility = str(row.get("state_visibility_status", "") or "")
        weight = str(row.get("recommended_oty2_weight", "") or "")
        policy = str(gate.get("uncertainty_policy", "") or "")
        uncertainty = _uncertainty_frames(policy, state_uncertainty, visibility, weight, mode)
        confidence = _degrade_confidence(str(gate.get("alignment_confidence_prior", "") or ""), mode, state_uncertainty, weight)
        center: int | None = None
        start: int | None = None
        end: int | None = None
        if mode == "frame_ratio_hypothesis" and optical_frame >= 0 and optical_count > 0 and sar_count > 0:
            center = _ratio_sar_frame(optical_frame, optical_count, sar_count)
            start = max(0, center - uncertainty)
            end = min(sar_count - 1, center + uncertainty)

        reason_parts = [
            f"uncertainty_policy={policy}",
            f"state_uncertainty={state_uncertainty or 'unknown'}",
            f"state_visibility={visibility or 'unknown'}",
        ]
        if mode == "frame_ratio_hypothesis":
            reason_parts.append("frame_count_ratio_audit_only_not_truth")
            reason_parts.append("no_exact_timestamp_metadata")
        elif mode == "unknown_alignment":
            reason_parts.append("blocked_or_missing_temporal_inventory")
        else:
            reason_parts.append("timestamp_metadata_available_but_not_sar_content")

        out.append(
            {
                "scene": scene,
                "object_hypothesis_id": obj_id,
                "optical_frame_num": row.get("optical_frame_num", ""),
                "main_tracker_track_id": row.get("main_tracker_track_id", ""),
                "primary_det_id": row.get("primary_det_id", ""),
                "secondary_det_ids": row.get("secondary_det_ids", ""),
                "state_visibility_status": visibility,
                "state_uncertainty_status": state_uncertainty,
                "recommended_oty2_weight": weight,
                "oty2_gate": gate.get("oty2_gate", ""),
                "alignment_mode": mode,
                "alignment_confidence": confidence,
                "optical_time_proxy": f"frame_index:{optical_frame};optical_frame_count:{optical_count};timestamp_exact:false",
                "sar_frame_center_candidate": "" if center is None else center,
                "sar_frame_window_start": "" if start is None else start,
                "sar_frame_window_end": "" if end is None else end,
                "uncertainty_frames": uncertainty,
                "window_reason": join_values(reason_parts),
                "runtime_source_policy": RUNTIME_SOURCE_POLICY,
            }
        )
    return out


def _confidence_floor(values: Sequence[Any]) -> str:
    order = {"blocked": 0, "low": 1, "medium": 2, "high": 3}
    clean = [str(value or "low") for value in values]
    if not clean:
        return "blocked"
    return min(clean, key=lambda item: order.get(item, 1))


def build_object_alignment_window_candidate_rows(
    *,
    gating_rows: Sequence[Mapping[str, Any]],
    frame_map_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gate_by_object = {str(row.get("object_hypothesis_id", "") or ""): row for row in gating_rows}
    frames_by_object: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in frame_map_rows:
        frames_by_object[str(row.get("object_hypothesis_id", "") or "")].append(row)

    out: list[dict[str, Any]] = []
    for obj_id in sorted(frames_by_object):
        rows = frames_by_object[obj_id]
        gate = gate_by_object.get(obj_id, {})
        starts = [safe_int(row.get("sar_frame_window_start"), default=-1) for row in rows]
        ends = [safe_int(row.get("sar_frame_window_end"), default=-1) for row in rows]
        valid_starts = [value for value in starts if value >= 0]
        valid_ends = [value for value in ends if value >= 0]
        if not valid_starts or not valid_ends:
            continue
        frame_nums = [safe_int(row.get("optical_frame_num"), default=-1) for row in rows]
        sar_start = min(valid_starts)
        sar_end = max(valid_ends)
        primary_count = sum(1 for row in rows if str(row.get("primary_det_id", "") or "").strip())
        secondary_hint_count = sum(
            1
            for row in rows
            if str(row.get("secondary_det_ids", "") or "").strip()
            or str(row.get("recommended_oty2_weight", "") or "") == "secondary_hint_only"
        )
        confidence = _confidence_floor([row.get("alignment_confidence") for row in rows])
        mode_counts = Counter(str(row.get("alignment_mode", "") or "") for row in rows)
        mode = sorted(mode_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        out.append(
            {
                "scene": rows[0].get("scene", ""),
                "object_hypothesis_id": obj_id,
                "window_id": f"{obj_id}_w001",
                "object_frame_start": min(value for value in frame_nums if value >= 0),
                "object_frame_end": max(value for value in frame_nums if value >= 0),
                "primary_optical_frame_count": primary_count,
                "secondary_hint_frame_count": secondary_hint_count,
                "alignment_mode": mode,
                "sar_window_start": sar_start,
                "sar_window_end": sar_end,
                "sar_window_center": round((sar_start + sar_end) / 2),
                "sar_window_size": sar_end - sar_start + 1,
                "alignment_confidence": confidence,
                "uncertainty_policy": gate.get("uncertainty_policy", ""),
                "review_required": gate.get("review_required", ""),
                "object_readiness_gate": gate.get("oty2_gate", ""),
                "do_not_enter_sar_band": "true",
                "reason": "temporal_window_candidate_only;do_not_enter_sar_band=true;no_sar_image_content_or_gt_used",
            }
        )
    return out


def _scene_counts(
    *,
    scene: str,
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    frame_map_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "object_hypotheses_input_count": sum(1 for row in object_rows if row.get("scene") == scene),
        "object_frame_state_rows": sum(1 for row in frame_rows if row.get("scene") == scene),
        "alignment_frame_map_rows": sum(1 for row in frame_map_rows if row.get("scene") == scene),
        "alignment_window_candidate_rows": sum(1 for row in window_rows if row.get("scene") == scene),
    }


def _alignment_readiness(
    *,
    status_row: Mapping[str, Any],
    object_rows: Sequence[Mapping[str, Any]],
) -> str:
    input_status = str(status_row.get("input_status", "") or "")
    if input_status.startswith("blocked"):
        return "blocked_missing_inputs"
    scene = str(status_row.get("scene", "") or "")
    scene_objects = [row for row in object_rows if row.get("scene") == scene]
    ambiguous = sum(1 for row in scene_objects if row.get("object_hypothesis_type") == "ambiguous_object_hypothesis")
    if scene_objects and ambiguous > max(1, len(scene_objects) // 2):
        return "blocked_high_ambiguity"
    if input_status == "ready_for_oty2_p0":
        return "ready_for_temporal_alignment"
    return "ready_with_uncertainty"


def build_temporal_alignment_summary(
    *,
    generated_at: str,
    timestamp: str,
    tracker_name: str,
    scenes_attempted: Sequence[str],
    scene_status_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    gating_rows: Sequence[Mapping[str, Any]],
    frame_map_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
    output_dir: str,
) -> dict[str, Any]:
    status_by_scene = {str(row.get("scene", "") or ""): row for row in scene_status_rows}
    completed: list[str] = []
    blocked: list[str] = []
    for scene in scenes_attempted:
        status = str(status_by_scene.get(scene, {}).get("input_status", "") or "")
        if status.startswith("blocked") or not status:
            blocked.append(scene)
        else:
            completed.append(scene)
    gate_counts = Counter(str(row.get("oty2_gate", "") or "") for row in gating_rows)
    mode_counts = Counter(str(row.get("alignment_mode", "") or "") for row in frame_map_rows)
    per_scene: list[dict[str, Any]] = []
    for status_row in scene_status_rows:
        scene = str(status_row.get("scene", "") or "")
        counts = _scene_counts(
            scene=scene,
            object_rows=object_rows,
            frame_rows=frame_rows,
            frame_map_rows=frame_map_rows,
            window_rows=window_rows,
        )
        per_scene.append(
            {
                "scene": scene,
                "input_status": status_row.get("input_status", ""),
                **counts,
                "alignment_readiness": _alignment_readiness(status_row=status_row, object_rows=object_rows),
                "top_blockers": status_row.get("blocker_reason", ""),
            }
        )

    gm011_status = status_by_scene.get("GM_RM011", {}).get("input_status", "")
    return {
        "generated_at": generated_at,
        "timestamp": timestamp,
        "tracker_name": tracker_name,
        "scenes_attempted": join_values(scenes_attempted),
        "scenes_completed": join_values(completed),
        "scenes_blocked": join_values(blocked),
        "object_hypotheses_input_count": len(object_rows),
        "object_frame_state_input_rows": len(frame_rows),
        "object_readiness_gating_rows": len(gating_rows),
        "alignment_frame_map_rows": len(frame_map_rows),
        "alignment_window_candidate_rows": len(window_rows),
        "alignment_mode_counts": {key: mode_counts[key] for key in sorted(mode_counts)},
        "use_as_primary_alignment_track_count": gate_counts.get("use_as_primary_alignment_track", 0),
        "use_with_uncertainty_expansion_count": gate_counts.get("use_with_uncertainty_expansion", 0),
        "low_confidence_window_only_count": gate_counts.get("low_confidence_window_only", 0),
        "exclude_from_oty2_count": gate_counts.get("exclude_from_oty2", 0),
        "blocked_pending_visual_review_count": gate_counts.get("blocked_pending_visual_review", 0),
        "gm_rm011_input_status": gm011_status,
        **BOUNDARY_FLAGS,
        "output_dir": output_dir,
        "per_scene": per_scene,
    }


def _md_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, Mapping):
        return ";".join(f"{key}:{value[key]}" for key in sorted(value))
    return str(value)


def render_temporal_alignment_summary_markdown(summary: Mapping[str, Any]) -> str:
    fields = [
        "generated_at",
        "tracker_name",
        "scenes_attempted",
        "scenes_completed",
        "scenes_blocked",
        "object_hypotheses_input_count",
        "object_frame_state_input_rows",
        "object_readiness_gating_rows",
        "alignment_frame_map_rows",
        "alignment_window_candidate_rows",
        "alignment_mode_counts",
        "use_as_primary_alignment_track_count",
        "use_with_uncertainty_expansion_count",
        "low_confidence_window_only_count",
        "exclude_from_oty2_count",
        "blocked_pending_visual_review_count",
        "gm_rm011_input_status",
        "posthoc_sources_used_for_runtime_tracking",
        "sar_image_content_used",
        "sar_gt_coverage_entered",
        "sar_band_entered",
        "annotation_proposal_entered",
        "identity_truth_claimed",
    ]
    lines = [
        "# OTY2-P0 Object Temporal Alignment Summary",
        "",
        "OTY2-P0 maps object-level optical hypotheses and object-frame states to SAR temporal frame/window candidates with readiness gating. It uses object_hypothesis_id as the optical unit and carries primary/secondary observation uncertainty forward. It does not use SAR image content, SAR GT, SAR evidence, final/manual/oracle/review fields, selector output, training signal, SAR band generation, or annotation proposals.",
        "",
        "## Summary Fields",
        "",
    ]
    for field in fields:
        lines.append(f"- {field}: `{_md_value(summary.get(field, ''))}`")
    lines.extend(
        [
            "",
            "## Per-Scene",
            "",
            "| scene | input_status | object_hypotheses_input_count | object_frame_state_rows | alignment_frame_map_rows | alignment_window_candidate_rows | alignment_readiness | top_blockers |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in summary.get("per_scene", []):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| `{row.get('scene', '')}` | `{row.get('input_status', '')}` | "
            f"{row.get('object_hypotheses_input_count', 0)} | {row.get('object_frame_state_rows', 0)} | "
            f"{row.get('alignment_frame_map_rows', 0)} | {row.get('alignment_window_candidate_rows', 0)} | "
            f"`{row.get('alignment_readiness', '')}` | `{row.get('top_blockers', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- frame_ratio_hypothesis is audit-only and is not timestamp truth.",
            "- optical_frame_num is not assumed equal to sar_frame_num.",
            "- identity_status is not a confirmed identity claim.",
            "- do_not_enter_sar_band=true for every temporal window candidate.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_uncertainty_report(
    *,
    scene_status_rows: Sequence[Mapping[str, Any]],
    gating_rows: Sequence[Mapping[str, Any]],
    frame_map_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> str:
    gate_counts = Counter(str(row.get("oty2_gate", "") or "unknown") for row in gating_rows)
    mode_counts = Counter(str(row.get("alignment_mode", "") or "unknown") for row in frame_map_rows)
    uncertainty_counts = Counter(str(row.get("state_uncertainty_status", "") or "unknown") for row in frame_map_rows)
    blocker_counts: Counter[str] = Counter()
    for row in scene_status_rows:
        for reason in split_values(row.get("blocker_reason")):
            if reason:
                blocker_counts[reason] += 1

    def bullet_counts(counts: Counter[str]) -> list[str]:
        if not counts:
            return ["- none"]
        return [f"- `{key}`: {counts[key]}" for key in sorted(counts)]

    lines = [
        "# OTY2-P0 Object Alignment Uncertainty Report",
        "",
        "## Run Status",
        "",
        f"- scenes_attempted: `{summary.get('scenes_attempted', '')}`",
        f"- scenes_completed: `{summary.get('scenes_completed', '')}`",
        f"- scenes_blocked: `{summary.get('scenes_blocked', '')}`",
        f"- gm_rm011_input_status: `{summary.get('gm_rm011_input_status', '')}`",
        "",
        "## Alignment Modes Used",
        "",
        *bullet_counts(mode_counts),
        "",
        "## Readiness Gating Counts",
        "",
        f"- objects gated as primary: {gate_counts.get('use_as_primary_alignment_track', 0)}",
        f"- objects gated as uncertainty-expanded: {gate_counts.get('use_with_uncertainty_expansion', 0)}",
        f"- objects gated as low-confidence only: {gate_counts.get('low_confidence_window_only', 0)}",
        f"- objects excluded: {gate_counts.get('exclude_from_oty2', 0)}",
        f"- objects blocked pending visual review: {gate_counts.get('blocked_pending_visual_review', 0)}",
        f"- temporal window candidate rows: {len(window_rows)}",
        "",
        "## GM_RM011 Input Status",
        "",
    ]
    gm011 = next((row for row in scene_status_rows if row.get("scene") == "GM_RM011"), None)
    if gm011:
        lines.append(
            f"- `GM_RM011`: input_status=`{gm011.get('input_status', '')}`, blocker_reason=`{gm011.get('blocker_reason', '')}`"
        )
    else:
        lines.append("- `GM_RM011`: not present in scene input status rows")
    lines.extend(
        [
            "",
            "## Top Uncertainty Causes",
            "",
            *bullet_counts(uncertainty_counts),
            "",
            "## Top Blocker Causes",
            "",
            *bullet_counts(blocker_counts),
            "",
            "## Interpretation Rules",
            "",
            "- primary_det_id and main track are used for temporal continuity.",
            "- secondary_det_ids and cluster risk only expand or downgrade alignment confidence.",
            "- review_required does not confirm or deny object identity.",
            "- identity_status never means confirmed identity.",
            "- frame_ratio_hypothesis uses frame-count ratio only as an audit hypothesis, not as truth.",
            "",
            "## Boundary Flags",
            "",
            f"- sar_band_entered: `{str(summary.get('sar_band_entered', '')).lower()}`",
            f"- sar_gt_coverage_entered: `{str(summary.get('sar_gt_coverage_entered', '')).lower()}`",
            f"- sar_image_content_used: `{str(summary.get('sar_image_content_used', '')).lower()}`",
            f"- posthoc_sources_used_for_runtime_tracking: `{str(summary.get('posthoc_sources_used_for_runtime_tracking', '')).lower()}`",
            f"- annotation_proposal_entered: `{str(summary.get('annotation_proposal_entered', '')).lower()}`",
            f"- identity_truth_claimed: `{str(summary.get('identity_truth_claimed', '')).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_overview_svg(path: str | Path, summary: Mapping[str, Any]) -> None:
    width = 1220
    height = 500
    object_count = summary.get("object_hypotheses_input_count", 0)
    gating_count = summary.get("object_readiness_gating_rows", 0)
    frame_count = summary.get("object_frame_state_input_rows", 0)
    window_count = summary.get("alignment_window_candidate_rows", 0)
    boxes = [
        ("Object hypotheses", f"{object_count} object_hypothesis_id rows", 40, 130, 230, 86, "#dbeafe"),
        ("Readiness gating", f"{gating_count} gate decisions", 340, 130, 230, 86, "#dcfce7"),
        ("Object frame states", f"{frame_count} optical state rows", 640, 130, 230, 86, "#fef3c7"),
        ("SAR frame windows", f"{window_count} temporal candidates only", 940, 130, 230, 86, "#fce7f3"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 Z" fill="#64748b"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="34" y="40" font-size="19" font-family="Arial" font-weight="700" fill="#111827">OTY2-P0 object temporal alignment overview</text>',
        '<text x="34" y="66" font-size="13" font-family="Arial" fill="#374151">Flow only: no SAR images, no SAR GT, no SAR band, no selector, no training, no annotation proposal.</text>',
    ]
    for title, body, x, y, w, h, fill in boxes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#94a3b8"/>')
        parts.append(
            f'<text x="{x + 16}" y="{y + 32}" font-size="14" font-family="Arial" font-weight="700" fill="#111827">{html_escape(title)}</text>'
        )
        parts.append(f'<text x="{x + 16}" y="{y + 58}" font-size="12" font-family="Arial" fill="#374151">{html_escape(body)}</text>')
    for x1, x2 in ((270, 340), (570, 640), (870, 940)):
        parts.append(f'<line x1="{x1}" y1="173" x2="{x2}" y2="173" stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"/>')
    y = 278
    parts.append('<text x="40" y="260" font-size="14" font-family="Arial" font-weight="700" fill="#111827">Scene readiness</text>')
    for row in summary.get("per_scene", []):
        if not isinstance(row, Mapping):
            continue
        line = (
            f"{row.get('scene', '')}: input={row.get('input_status', '')}, "
            f"readiness={row.get('alignment_readiness', '')}, "
            f"windows={row.get('alignment_window_candidate_rows', 0)}"
        )
        parts.append(f'<text x="40" y="{y}" font-size="12" font-family="Arial" fill="#374151">{html_escape(line)}</text>')
        y += 24
    parts.append('<text x="640" y="260" font-size="14" font-family="Arial" font-weight="700" fill="#111827">Boundary flags</text>')
    flags = [
        f"posthoc_sources_used_for_runtime_tracking={str(summary.get('posthoc_sources_used_for_runtime_tracking')).lower()}",
        f"sar_image_content_used={str(summary.get('sar_image_content_used')).lower()}",
        f"sar_gt_coverage_entered={str(summary.get('sar_gt_coverage_entered')).lower()}",
        f"sar_band_entered={str(summary.get('sar_band_entered')).lower()}",
        f"annotation_proposal_entered={str(summary.get('annotation_proposal_entered')).lower()}",
        f"identity_truth_claimed={str(summary.get('identity_truth_claimed')).lower()}",
    ]
    y = 282
    for flag in flags:
        parts.append(f'<text x="640" y="{y}" font-size="12" font-family="Arial" fill="#374151">{html_escape(flag)}</text>')
        y += 22
    parts.append("</svg>")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def sample_gating_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    gate_priority = {
        "use_as_primary_alignment_track": 0,
        "use_with_uncertainty_expansion": 1,
        "low_confidence_window_only": 2,
        "exclude_from_oty2": 3,
        "blocked_pending_visual_review": 4,
    }

    def priority(row: Mapping[str, Any]) -> tuple[int, int, str]:
        obj = str(row.get("object_hypothesis_id", "") or "")
        case = 0 if "bt_0098" in obj else 1
        return (case, gate_priority.get(str(row.get("oty2_gate", "")), 9), obj)

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def sample_frame_map_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    key_frames = {149, 162, 163, 164, 165, 166, 167, 168, 171, 172, 173, 174, 181, 182}

    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
        obj = str(row.get("object_hypothesis_id", "") or "")
        scene = str(row.get("scene", "") or "")
        frame = safe_int(row.get("optical_frame_num"))
        case = 0 if "bt_0098" in obj and frame in key_frames else 1
        scene_rank = 0 if scene == "GM_RM017" else 1
        return (case, scene_rank, frame, obj)

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def sample_window_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    def priority(row: Mapping[str, Any]) -> tuple[int, str]:
        obj = str(row.get("object_hypothesis_id", "") or "")
        return (0 if "bt_0098" in obj else 1, obj)

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]
