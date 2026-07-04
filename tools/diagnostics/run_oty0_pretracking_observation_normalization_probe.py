"""Run OTY0-post pre-tracking observation normalization probe.

This probe consumes an existing OTY0 detection table and emits a shadow
normalized detection table for later bounded tracker-side diagnostics. It keeps
every original detector observation and every original bbox. Only
``active_for_tracking`` is changed for conservative high-overlap duplicate-like
same-frame observations. Outputs are diagnostic/probe artifacts only and do not
replace OTY0, OTY1, OTY1t, P4G, final boxes, annotations, or identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_oty0_pretracking_observation_grouping_audit as grouping  # noqa: E402


ADDED_NORMALIZED_FIELDS = [
    "observation_group_id",
    "active_for_tracking",
    "normalization_action",
    "primary_detection_id",
    "suppression_reason",
    "grouping_diagnosis_label",
    "state_tags",
    "class_mismatch_explained_by_duplicate_like",
    "safe_for_identity_claim",
    "why_not_identity_truth",
]

ACTION_FIELDS = [
    "scene",
    "detector_label",
    "optical_frame_num",
    "observation_group_id",
    "detection_id_a",
    "detection_id_b",
    "primary_detection_id",
    "secondary_detection_id",
    "class_a",
    "class_b",
    "confidence_a",
    "confidence_b",
    "overlap_proxy",
    "center_distance",
    "area_ratio",
    "frame_detection_count",
    "grouping_diagnosis_label",
    "state_tags",
    "normalization_action",
    "suppression_reason",
    "class_mismatch_explained_by_duplicate_like",
    "safe_for_identity_claim",
    "why_not_identity_truth",
]

SCENE_SUMMARY_FIELDS = [
    "scene",
    "detector_label",
    "source_detection_table",
    "timestamp",
    "total_detection_rows",
    "active_before_count",
    "active_after_count",
    "inactive_after_count",
    "suppressed_duplicate_like_rows",
    "duplicate_like_suppression_pairs",
    "class_instability_duplicate_like_pairs",
    "class_mismatch_explained_by_duplicate_like_rows",
    "partial_full_pairs_kept",
    "partial_full_rows_kept",
    "neighbor_crowding_pairs_kept",
    "neighbor_crowding_rows_kept",
    "unjudgeable_pairs_kept",
    "unjudgeable_rows_kept",
    "frames_with_any_suppression",
    "frames_with_detections",
    "normalized_detection_table_path",
    "normalization_actions_path",
]

DUPLICATE_LABELS = {
    "likely_duplicate_same_vehicle_observation",
    "class_instability_duplicate_like",
}
KEEP_PARTIAL_FULL_ACTION = "keep_with_partial_full_context"
KEEP_COMPETITION_ACTION = "keep_block_auto_grouping"
KEEP_REVIEW_ACTION = "keep_review_context"
KEEP_DUPLICATE_CONTEXT_ACTION = "keep_duplicate_like_context"
KEEP_NO_CONTEXT_ACTION = "keep_without_grouping_context"
SUPPRESS_ACTION = "suppress_duplicate_like_for_tracking"

HIGH_CONFIDENCE_PRIMARY_MIN = 0.50
SUPPRESSION_REASON = "high_overlap_near_center_duplicate_like"
WHY_NOT_IDENTITY_TRUTH = (
    "shadow normalization uses same-frame detector geometry only; no temporal "
    "association, SAR evidence, visual review, or identity adjudication was used"
)


def read_csv_with_fieldnames(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [row for row in reader if not grouping._is_duplicate_header_row(row)]
    return fieldnames, rows


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stable_float(value: Any) -> float:
    parsed = grouping.parse_float(value)
    if parsed is None or not math.isfinite(parsed):
        return 0.0
    return parsed


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def unique_join(values: Sequence[str]) -> str:
    return ";".join(sorted({str(value) for value in values if str(value or "").strip()}))


def append_context(target: dict[str, list[str]], det_id: str, label: str, tags: str) -> None:
    if not det_id:
        return
    target.setdefault(det_id, [])
    if label:
        target[det_id].append(label)
    for tag in str(tags or "").split(";"):
        if tag:
            target[det_id].append(f"tag:{tag}")


def label_values(context_values: Sequence[str]) -> str:
    return unique_join([value for value in context_values if not value.startswith("tag:")])


def tag_values(context_values: Sequence[str]) -> str:
    tags = [value[4:] for value in context_values if value.startswith("tag:")]
    return grouping.join_tags(tags)


def is_suppressible_duplicate(pair: Mapping[str, Any]) -> bool:
    label = str(pair.get("grouping_diagnosis_label", ""))
    if label not in DUPLICATE_LABELS:
        return False
    return (
        stable_float(pair.get("overlap_proxy")) >= grouping.HIGH_OVERLAP_PROXY
        and stable_float(pair.get("center_distance")) <= grouping.CLOSE_CENTER_PX
        and stable_float(pair.get("area_ratio")) >= grouping.DUPLICATE_SIZE_RATIO_MIN
        and max(stable_float(pair.get("confidence_a")), stable_float(pair.get("confidence_b")))
        >= HIGH_CONFIDENCE_PRIMARY_MIN
    )


def choose_primary(pair: Mapping[str, Any]) -> tuple[str, str]:
    det_a = str(pair.get("detection_id_a", "") or "")
    det_b = str(pair.get("detection_id_b", "") or "")
    conf_a = stable_float(pair.get("confidence_a"))
    conf_b = stable_float(pair.get("confidence_b"))
    if conf_a > conf_b:
        return det_a, det_b
    if conf_b > conf_a:
        return det_b, det_a
    return (det_a, det_b) if det_a <= det_b else (det_b, det_a)


def pair_sort_key(pair: Mapping[str, Any]) -> tuple[float, float, float, str, str]:
    return (
        -stable_float(pair.get("overlap_proxy")),
        stable_float(pair.get("center_distance")),
        -max(stable_float(pair.get("confidence_a")), stable_float(pair.get("confidence_b"))),
        str(pair.get("detection_id_a", "")),
        str(pair.get("detection_id_b", "")),
    )


def default_row_state(det_id: str) -> dict[str, Any]:
    return {
        "observation_group_id": "",
        "active_for_tracking": "true",
        "normalization_action": KEEP_NO_CONTEXT_ACTION,
        "primary_detection_id": det_id,
        "suppression_reason": "",
        "grouping_diagnosis_label": "",
        "state_tags": "",
        "class_mismatch_explained_by_duplicate_like": "false",
        "safe_for_identity_claim": "false",
        "why_not_identity_truth": WHY_NOT_IDENTITY_TRUTH,
    }


def group_id(scene: str, frame: int, label: str, index: int) -> str:
    return f"{grouping.safe_name(scene)}_{frame:06d}_{label}_{index:03d}"


def build_pair_candidates(
    rows: Sequence[Mapping[str, Any]],
    scene: str,
    detector_label: str,
) -> list[dict[str, Any]]:
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        frame = grouping.parse_int(row.get("optical_frame_num"))
        if frame is None or grouping.bbox_from_row(row) is None:
            continue
        by_frame.setdefault(frame, []).append(dict(row))

    image_size_cache: dict[str, tuple[int, int] | None] = {}
    pairs: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        detections = sorted(by_frame[frame], key=lambda item: str(item.get("det_id", "")))
        for left_index, left in enumerate(detections):
            for right in detections[left_index + 1 :]:
                pair = grouping.classify_pair(left, right, len(detections), image_size_cache)
                if pair is None:
                    continue
                pair.update(
                    {
                        "scene": scene,
                        "detector_label": detector_label,
                        "optical_frame_num": frame,
                    }
                )
                pairs.append(pair)
    return sorted(pairs, key=pair_sort_key)


def pair_action_for_label(label: str) -> str:
    if label in DUPLICATE_LABELS:
        return KEEP_DUPLICATE_CONTEXT_ACTION
    if label == "possible_partial_full_same_vehicle_competition":
        return KEEP_PARTIAL_FULL_ACTION
    if label in {"likely_neighbor_vehicle_competition", "multi_vehicle_crowding_unresolved"}:
        return KEEP_COMPETITION_ACTION
    if label == "unjudgeable_without_visual_review":
        return KEEP_REVIEW_ACTION
    return KEEP_NO_CONTEXT_ACTION


def apply_normalization(
    original_rows: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
    scene: str,
    detector_label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    det_ids = [str(row.get("det_id", "") or "").strip() for row in original_rows]
    row_state = {det_id: default_row_state(det_id) for det_id in det_ids if det_id}
    context_by_det: dict[str, list[str]] = {}
    actions: list[dict[str, Any]] = []
    action_index_by_frame: dict[int, int] = {}

    for pair in pair_rows:
        frame = grouping.parse_int(pair.get("optical_frame_num")) or 0
        action_index_by_frame[frame] = action_index_by_frame.get(frame, 0) + 1
        obs_group_id = group_id(scene, frame, "obsnorm", action_index_by_frame[frame])
        det_a = str(pair.get("detection_id_a", "") or "")
        det_b = str(pair.get("detection_id_b", "") or "")
        label = str(pair.get("grouping_diagnosis_label", "") or "")
        tags = str(pair.get("state_tags", "") or "")
        append_context(context_by_det, det_a, label, tags)
        append_context(context_by_det, det_b, label, tags)

        pair_action = pair_action_for_label(label)
        suppression_reason = ""
        primary_det = ""
        secondary_det = ""
        class_mismatch = str(pair.get("class_relation", "")) == "class_conflict"
        class_mismatch_explained = False

        if is_suppressible_duplicate(pair):
            candidate_primary, candidate_secondary = choose_primary(pair)
            primary_active = row_state.get(candidate_primary, {}).get("active_for_tracking") == "true"
            secondary_active = row_state.get(candidate_secondary, {}).get("active_for_tracking") == "true"
            if primary_active and secondary_active:
                primary_det = candidate_primary
                secondary_det = candidate_secondary
                pair_action = SUPPRESS_ACTION
                suppression_reason = SUPPRESSION_REASON
                class_mismatch_explained = class_mismatch
                row_state[primary_det]["observation_group_id"] = obs_group_id
                row_state[primary_det]["normalization_action"] = KEEP_DUPLICATE_CONTEXT_ACTION
                row_state[primary_det]["primary_detection_id"] = primary_det
                row_state[primary_det]["class_mismatch_explained_by_duplicate_like"] = bool_text(
                    class_mismatch
                    or row_state[primary_det]["class_mismatch_explained_by_duplicate_like"] == "true"
                )
                row_state[secondary_det]["observation_group_id"] = obs_group_id
                row_state[secondary_det]["active_for_tracking"] = "false"
                row_state[secondary_det]["normalization_action"] = SUPPRESS_ACTION
                row_state[secondary_det]["primary_detection_id"] = primary_det
                row_state[secondary_det]["suppression_reason"] = SUPPRESSION_REASON
                row_state[secondary_det]["class_mismatch_explained_by_duplicate_like"] = bool_text(class_mismatch)
            else:
                primary_det = candidate_primary
                secondary_det = candidate_secondary

        actions.append(
            {
                "scene": scene,
                "detector_label": detector_label,
                "optical_frame_num": frame,
                "observation_group_id": obs_group_id,
                "detection_id_a": det_a,
                "detection_id_b": det_b,
                "primary_detection_id": primary_det,
                "secondary_detection_id": secondary_det,
                "class_a": pair.get("class_a", ""),
                "class_b": pair.get("class_b", ""),
                "confidence_a": pair.get("confidence_a", ""),
                "confidence_b": pair.get("confidence_b", ""),
                "overlap_proxy": pair.get("overlap_proxy", ""),
                "center_distance": pair.get("center_distance", ""),
                "area_ratio": pair.get("area_ratio", ""),
                "frame_detection_count": pair.get("frame_detection_count", ""),
                "grouping_diagnosis_label": label,
                "state_tags": tags,
                "normalization_action": pair_action,
                "suppression_reason": suppression_reason,
                "class_mismatch_explained_by_duplicate_like": bool_text(class_mismatch_explained),
                "safe_for_identity_claim": "false",
                "why_not_identity_truth": WHY_NOT_IDENTITY_TRUTH,
            }
        )

    for det_id, values in context_by_det.items():
        if det_id not in row_state:
            continue
        current_action = row_state[det_id]["normalization_action"]
        labels = label_values(values)
        tags = tag_values(values)
        row_state[det_id]["grouping_diagnosis_label"] = labels
        row_state[det_id]["state_tags"] = tags
        if current_action in {SUPPRESS_ACTION, KEEP_DUPLICATE_CONTEXT_ACTION}:
            continue
        label_set = set(label for label in labels.split(";") if label)
        if "possible_partial_full_same_vehicle_competition" in label_set:
            row_state[det_id]["normalization_action"] = KEEP_PARTIAL_FULL_ACTION
        elif label_set & {"likely_neighbor_vehicle_competition", "multi_vehicle_crowding_unresolved"}:
            row_state[det_id]["normalization_action"] = KEEP_COMPETITION_ACTION
        elif "unjudgeable_without_visual_review" in label_set:
            row_state[det_id]["normalization_action"] = KEEP_REVIEW_ACTION
        elif label_set & DUPLICATE_LABELS:
            row_state[det_id]["normalization_action"] = KEEP_DUPLICATE_CONTEXT_ACTION

    normalized: list[dict[str, Any]] = []
    for row in original_rows:
        det_id = str(row.get("det_id", "") or "").strip()
        state = row_state.get(det_id, default_row_state(det_id))
        out = dict(row)
        out.update(state)
        normalized.append(out)

    summary = summarize_scene(original_rows, normalized, actions, pair_rows, scene, detector_label)
    return normalized, actions, summary


def summarize_scene(
    original_rows: Sequence[Mapping[str, Any]],
    normalized_rows: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
    scene: str,
    detector_label: str,
) -> dict[str, Any]:
    active_after = [
        row for row in normalized_rows if str(row.get("active_for_tracking", "")).lower() == "true"
    ]
    suppressed = [
        row for row in normalized_rows if str(row.get("normalization_action", "")) == SUPPRESS_ACTION
    ]
    class_explained = [
        row
        for row in normalized_rows
        if str(row.get("class_mismatch_explained_by_duplicate_like", "")).lower() == "true"
    ]
    frames = {
        grouping.parse_int(row.get("optical_frame_num"))
        for row in original_rows
        if grouping.parse_int(row.get("optical_frame_num")) is not None
    }
    suppressed_frames = {
        grouping.parse_int(row.get("optical_frame_num"))
        for row in suppressed
        if grouping.parse_int(row.get("optical_frame_num")) is not None
    }

    def pair_count(label: str) -> int:
        return sum(1 for row in pair_rows if str(row.get("grouping_diagnosis_label", "")) == label)

    def row_count_with_action(action: str) -> int:
        return sum(1 for row in normalized_rows if str(row.get("normalization_action", "")) == action)

    kept_competition_rows = row_count_with_action(KEEP_COMPETITION_ACTION)
    kept_review_rows = row_count_with_action(KEEP_REVIEW_ACTION)
    return {
        "scene": scene,
        "detector_label": detector_label,
        "total_detection_rows": len(original_rows),
        "active_before_count": len(original_rows),
        "active_after_count": len(active_after),
        "inactive_after_count": len(normalized_rows) - len(active_after),
        "suppressed_duplicate_like_rows": len(suppressed),
        "duplicate_like_suppression_pairs": sum(
            1 for row in actions if str(row.get("normalization_action", "")) == SUPPRESS_ACTION
        ),
        "class_instability_duplicate_like_pairs": pair_count("class_instability_duplicate_like"),
        "class_mismatch_explained_by_duplicate_like_rows": len(class_explained),
        "partial_full_pairs_kept": pair_count("possible_partial_full_same_vehicle_competition"),
        "partial_full_rows_kept": row_count_with_action(KEEP_PARTIAL_FULL_ACTION),
        "neighbor_crowding_pairs_kept": pair_count("likely_neighbor_vehicle_competition")
        + pair_count("multi_vehicle_crowding_unresolved"),
        "neighbor_crowding_rows_kept": kept_competition_rows,
        "unjudgeable_pairs_kept": pair_count("unjudgeable_without_visual_review"),
        "unjudgeable_rows_kept": kept_review_rows,
        "frames_with_any_suppression": len(suppressed_frames),
        "frames_with_detections": len(frames),
    }


def build_probe(
    detection_table: Path,
    scene: str,
    detector_label: str,
    output_dir: Path,
    timestamp: str,
) -> dict[str, Any]:
    fieldnames, raw_rows = read_csv_with_fieldnames(detection_table)
    scene_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        row_scene = str(row.get("scene", "") or "").strip()
        if row_scene and row_scene != scene:
            continue
        item = dict(row)
        item.setdefault("scene", scene)
        scene_rows.append(item)

    pair_rows = build_pair_candidates(scene_rows, scene, detector_label)
    normalized_rows, actions, summary = apply_normalization(scene_rows, pair_rows, scene, detector_label)

    prefix = f"{grouping.safe_name(scene)}_{grouping.safe_name(detector_label)}"
    normalized_path = output_dir / f"{prefix}_normalized_detection_table.csv"
    actions_path = output_dir / f"{prefix}_normalization_actions.csv"
    summary_path = output_dir / f"{prefix}_normalization_scene_summary.csv"
    json_path = output_dir / f"{prefix}_normalization_probe.json"

    normalized_fieldnames = list(fieldnames)
    for field in ADDED_NORMALIZED_FIELDS:
        if field not in normalized_fieldnames:
            normalized_fieldnames.append(field)

    summary.update(
        {
            "source_detection_table": str(detection_table),
            "timestamp": timestamp,
            "normalized_detection_table_path": str(normalized_path),
            "normalization_actions_path": str(actions_path),
        }
    )

    write_csv(normalized_path, normalized_rows, normalized_fieldnames)
    write_csv(actions_path, actions, ACTION_FIELDS)
    write_csv(summary_path, [summary], SCENE_SUMMARY_FIELDS)
    write_json(
        json_path,
        {
            "boundary": (
                "shadow OTY0-post pre-tracking normalization probe only; original "
                "detections and bboxes are preserved; active_for_tracking is not identity truth"
            ),
            "thresholds": {
                "high_overlap_proxy": grouping.HIGH_OVERLAP_PROXY,
                "close_center_px": grouping.CLOSE_CENTER_PX,
                "duplicate_size_ratio_min": grouping.DUPLICATE_SIZE_RATIO_MIN,
                "high_confidence_primary_min": HIGH_CONFIDENCE_PRIMARY_MIN,
            },
            "summary": summary,
            "outputs": {
                "normalized_detection_table": str(normalized_path),
                "normalization_actions": str(actions_path),
                "normalization_scene_summary": str(summary_path),
            },
        },
    )
    return {
        "normalized_detection_table": normalized_path,
        "normalization_actions": actions_path,
        "normalization_scene_summary": summary_path,
        "json": json_path,
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-detection-table", required=True, type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--detector-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_detection_table.exists():
        raise FileNotFoundError(args.input_detection_table)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = build_probe(
        detection_table=args.input_detection_table,
        scene=str(args.scene),
        detector_label=str(args.detector_label),
        output_dir=args.output_dir,
        timestamp=str(args.timestamp),
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
