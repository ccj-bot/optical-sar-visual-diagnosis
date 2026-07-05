"""Run OTY0-post observation component grouping dry run.

This diagnostic builds same-frame observation components from an existing OTY0
detection table. It reuses the OTY0 pretracking pair classifier, converts
candidate pair relations into connected components, and assigns review-safe
tracking and fragment-context policies. It does not merge boxes, drop raw
observations, modify OTY0/OTY1/OTY1t runtime, run a tracker, use SAR/support
evidence, tune thresholds, create final boxes, or claim identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_oty0_pretracking_observation_grouping_audit as grouping  # noqa: E402


DUPLICATE_LABELS = {
    "likely_duplicate_same_vehicle_observation",
    "class_instability_duplicate_like",
}
PARTIAL_FULL_LABEL = "possible_partial_full_same_vehicle_competition"
NEIGHBOR_LABELS = {
    "likely_neighbor_vehicle_competition",
    "multi_vehicle_crowding_unresolved",
}
UNRESOLVED_LABEL = "unjudgeable_without_visual_review"

WHY_NOT_IDENTITY_TRUTH = (
    "component grouping is same-frame detector-observation context only; no "
    "temporal identity adjudication, SAR evidence, visual review, final box, "
    "or identity truth was used"
)

COMPONENT_FIELDS = [
    "scene",
    "detector_label",
    "optical_frame_num",
    "observation_component_id",
    "component_size",
    "edge_count",
    "component_det_ids",
    "component_pair_labels",
    "component_state_tags",
    "component_conflict_family",
    "component_primary_candidate",
    "component_policy",
    "tracking_policy",
    "fragment_context_policy",
    "suppression_risk",
    "temporal_review_needed",
    "known_side_effect_det_ids",
    "why_not_identity_truth",
]

ROW_FIELDS = [
    "scene",
    "detector_label",
    "optical_frame_num",
    "raw_det_id",
    "observation_component_id",
    "component_size",
    "component_role",
    "class_name",
    "confidence",
    "component_conflict_family",
    "component_policy",
    "tracking_policy",
    "fragment_context_policy",
    "suppression_risk",
    "temporal_review_needed",
    "row_pair_labels",
    "row_state_tags",
    "known_side_effect_assessment",
    "known_side_effect_policy",
    "primary_candidate",
    "why_not_identity_truth",
]

SCENE_SUMMARY_FIELDS = [
    "scene",
    "detector_label",
    "source_detection_table",
    "timestamp",
    "total_detection_rows",
    "frames_with_detections",
    "component_count",
    "candidate_component_count",
    "orphan_component_count",
    "clean_duplicate_pressure_components",
    "continuity_useful_duplicate_context_components",
    "partial_full_review_context_components",
    "neighbor_multi_object_competition_components",
    "unresolved_review_required_components",
    "clean_duplicate_pressure_rows",
    "continuity_useful_duplicate_context_rows",
    "partial_full_review_context_rows",
    "neighbor_multi_object_competition_rows",
    "unresolved_review_required_rows",
    "secondary_suppress_for_tracking_rows",
    "secondary_keep_for_continuity_context_rows",
    "keep_block_auto_grouping_rows",
    "review_required_rows",
    "known_side_effect_components",
    "known_side_effect_rows",
    "component_output_path",
    "row_role_output_path",
]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh) if not grouping._is_duplicate_header_row(row)]


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


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def split_values(value: Any) -> set[str]:
    return {part.strip() for part in str(value or "").split(";") if part.strip()}


def stable_float(value: Any) -> float:
    parsed = grouping.parse_float(value)
    if parsed is None or not math.isfinite(parsed):
        return 0.0
    return parsed


def unique_join(values: Iterable[str]) -> str:
    return ";".join(sorted({str(value) for value in values if str(value or "").strip()}))


def load_side_effect_samples(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    rows = read_csv_rows(path)
    by_det: dict[str, dict[str, str]] = {}
    for row in rows:
        det_id = str(row.get("secondary_detection_id", "") or "").strip()
        if det_id:
            by_det[det_id] = dict(row)
    return by_det


def read_scene_detections(path: Path, scene: str) -> list[dict[str, str]]:
    rows = []
    for index, row in enumerate(read_csv_rows(path), start=1):
        row_scene = str(row.get("scene", "") or "").strip()
        if row_scene and row_scene != scene:
            continue
        frame = grouping.parse_int(row.get("optical_frame_num"))
        if frame is None or grouping.bbox_from_row(row) is None:
            continue
        item = dict(row)
        item.setdefault("scene", scene)
        if not str(item.get("det_id", "") or "").strip():
            item["det_id"] = f"{grouping.safe_name(scene)}_{frame:06d}_{index:06d}"
        rows.append(item)
    return rows


def build_pair_candidates(
    rows: Sequence[Mapping[str, Any]],
    scene: str,
    detector_label: str,
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        frame = grouping.parse_int(row.get("optical_frame_num"))
        if frame is not None:
            by_frame[frame].append(dict(row))

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
    return pairs, by_frame


def connected_components(
    detections: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
) -> list[set[str]]:
    det_ids = {str(row.get("det_id", "") or "").strip() for row in detections}
    det_ids.discard("")
    neighbors: dict[str, set[str]] = {det_id: set() for det_id in det_ids}
    for pair in pair_rows:
        left = str(pair.get("detection_id_a", "") or "").strip()
        right = str(pair.get("detection_id_b", "") or "").strip()
        if left in neighbors and right in neighbors:
            neighbors[left].add(right)
            neighbors[right].add(left)

    seen: set[str] = set()
    components: list[set[str]] = []
    for det_id in sorted(det_ids):
        if det_id in seen:
            continue
        stack = [det_id]
        component: set[str] = set()
        seen.add(det_id)
        while stack:
            current = stack.pop()
            component.add(current)
            for nxt in sorted(neighbors[current]):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(component)
    return components


def component_id(scene: str, frame: int, index: int) -> str:
    return f"{grouping.safe_name(scene)}_{frame:06d}_obscomp_{index:03d}"


def edge_subset_for_component(
    component: set[str],
    pair_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for row in pair_rows:
        left = str(row.get("detection_id_a", "") or "")
        right = str(row.get("detection_id_b", "") or "")
        if left in component and right in component:
            out.append(dict(row))
    return out


def row_context(
    det_id: str,
    pair_rows: Sequence[Mapping[str, Any]],
) -> tuple[set[str], set[str]]:
    labels: set[str] = set()
    tags: set[str] = set()
    for row in pair_rows:
        if det_id not in {str(row.get("detection_id_a", "")), str(row.get("detection_id_b", ""))}:
            continue
        labels.add(str(row.get("grouping_diagnosis_label", "") or ""))
        tags.update(split_values(row.get("state_tags")))
    labels.discard("")
    return labels, tags


def side_effect_policy_for_det(det_id: str, side_effects: Mapping[str, Mapping[str, Any]]) -> str:
    row = side_effects.get(det_id)
    if not row:
        return ""
    return str(row.get("recommended_component_policy", "") or "")


def component_family(
    labels: set[str],
    tags: set[str],
    component: set[str],
    side_effects: Mapping[str, Mapping[str, Any]],
) -> str:
    policies = {side_effect_policy_for_det(det_id, side_effects) for det_id in component}
    side_effect_rows = [side_effects[det_id] for det_id in component if det_id in side_effects]
    side_effect_assessments = {
        str(row.get("side_effect_assessment", "") or "") for row in side_effect_rows
    }
    raw_unmatched_buckets = {
        str(row.get("raw_unmatched_bucket", "") or "") for row in side_effect_rows
    }
    if not labels:
        return "orphan_no_multibox_candidate"
    if labels & NEIGHBOR_LABELS:
        return "neighbor_multi_object_competition"
    if any("competition" in value for value in side_effect_assessments) or any(
        "neighbor" in value for value in raw_unmatched_buckets
    ):
        return "neighbor_multi_object_competition"
    if PARTIAL_FULL_LABEL in labels or {"partial_visible", "partial_to_full_transition", "shape_instability"} & tags:
        return "partial_full_review_context"
    if (labels & DUPLICATE_LABELS) and "secondary_keep_for_continuity_context" in policies:
        return "continuity_useful_duplicate_context"
    if UNRESOLVED_LABEL in labels:
        return "unresolved_review_required"
    if labels and labels <= DUPLICATE_LABELS:
        if "secondary_review_required" in policies:
            return "unresolved_review_required"
        return "clean_duplicate_pressure"
    return "unresolved_review_required"


def family_policies(family: str) -> tuple[str, str, str, str, bool]:
    if family == "clean_duplicate_pressure":
        return (
            "clean_duplicate_pressure",
            "secondary_suppress_for_tracking",
            "preserve_as_duplicate_pressure_evidence",
            "low_duplicate_pressure_risk",
            False,
        )
    if family == "continuity_useful_duplicate_context":
        return (
            "continuity_useful_duplicate_context",
            "secondary_keep_for_continuity_context",
            "preserve_as_continuity_bridge_candidate",
            "continuity_risk",
            True,
        )
    if family == "partial_full_review_context":
        return (
            "partial_full_review_context",
            "review_required",
            "preserve_as_partial_full_state_evidence",
            "review_state_risk",
            True,
        )
    if family == "neighbor_multi_object_competition":
        return (
            "neighbor_multi_object_competition",
            "keep_block_auto_grouping",
            "preserve_as_neighbor_competition_blocker",
            "competition_risk",
            True,
        )
    if family == "orphan_no_multibox_candidate":
        return (
            "orphan_no_multibox_candidate",
            "active_primary_for_tracking_probe",
            "preserve_as_unresolved_review_context",
            "none",
            False,
        )
    return (
        "unresolved_review_required",
        "review_required",
        "preserve_as_unresolved_review_context",
        "unresolved_review_risk",
        True,
    )


def primary_score(
    row: Mapping[str, Any],
    labels: set[str],
    tags: set[str],
    side_effect_policy: str,
    side_effect_rows: Mapping[str, Mapping[str, Any]],
) -> tuple[float, str]:
    score = stable_float(row.get("confidence"))
    if "class_instability_duplicate_like" not in labels:
        score += 0.04
    if "class_instability" in tags:
        score -= 0.03
    if {"partial_visible", "partial_to_full_transition", "shape_instability"} & tags:
        score -= 0.06
    if {"edge_contact", "truncation_like"} & tags:
        score -= 0.02
    if side_effect_policy == "secondary_keep_for_continuity_context":
        score -= 0.20
    elif side_effect_policy == "secondary_review_required":
        score -= 0.30
    elif side_effect_policy == "secondary_suppress_for_tracking":
        score -= 0.25
    primary_refs = {
        str(sample.get("primary_detection_id", "") or "")
        for sample in side_effect_rows.values()
        if str(sample.get("primary_detection_id", "") or "")
    }
    det_id = str(row.get("det_id", "") or "")
    if det_id in primary_refs:
        score += 0.03
    return (score, det_id)


def choose_primary(
    component: set[str],
    rows_by_id: Mapping[str, Mapping[str, Any]],
    component_pair_rows: Sequence[Mapping[str, Any]],
    side_effects: Mapping[str, Mapping[str, Any]],
) -> str:
    candidates = []
    for det_id in sorted(component):
        labels, tags = row_context(det_id, component_pair_rows)
        candidates.append(
            primary_score(
                rows_by_id[det_id],
                labels,
                tags,
                side_effect_policy_for_det(det_id, side_effects),
                side_effects,
            )
        )
    if not candidates:
        return sorted(component)[0]
    return max(candidates)[1]


def component_role(det_id: str, primary: str, family: str, component_size: int) -> str:
    if component_size == 1:
        return "orphan_observation"
    if det_id == primary:
        return "primary_observation"
    if family in {"neighbor_multi_object_competition", "unresolved_review_required"}:
        return "competing_observation"
    return "secondary_observation"


def tracking_policy_for_row(det_id: str, primary: str, family: str, base_tracking_policy: str) -> str:
    if det_id == primary or family == "orphan_no_multibox_candidate":
        return "active_primary_for_tracking_probe"
    return base_tracking_policy


def build_component_outputs(
    scene: str,
    detector_label: str,
    detection_rows: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
    by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
    side_effects: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_id = {str(row.get("det_id", "") or ""): dict(row) for row in detection_rows}
    component_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []

    pair_rows_by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        frame = grouping.parse_int(row.get("optical_frame_num"))
        if frame is not None:
            pair_rows_by_frame[frame].append(dict(row))

    for frame in sorted(by_frame):
        detections = list(by_frame[frame])
        components = connected_components(detections, pair_rows_by_frame.get(frame, []))
        for index, component in enumerate(components, start=1):
            comp_pair_rows = edge_subset_for_component(component, pair_rows_by_frame.get(frame, []))
            labels = {str(row.get("grouping_diagnosis_label", "") or "") for row in comp_pair_rows}
            labels.discard("")
            tags: set[str] = set()
            for row in comp_pair_rows:
                tags.update(split_values(row.get("state_tags")))
            family = component_family(labels, tags, component, side_effects)
            component_policy, base_tracking_policy, fragment_policy, suppression_risk, temporal_review = family_policies(family)
            primary = choose_primary(component, rows_by_id, comp_pair_rows, side_effects)
            comp_id = component_id(scene, frame, index)
            side_effect_det_ids = [det_id for det_id in sorted(component) if det_id in side_effects]

            component_rows.append(
                {
                    "scene": scene,
                    "detector_label": detector_label,
                    "optical_frame_num": frame,
                    "observation_component_id": comp_id,
                    "component_size": len(component),
                    "edge_count": len(comp_pair_rows),
                    "component_det_ids": unique_join(sorted(component)),
                    "component_pair_labels": unique_join(labels),
                    "component_state_tags": grouping.join_tags(tags),
                    "component_conflict_family": family,
                    "component_primary_candidate": primary,
                    "component_policy": component_policy,
                    "tracking_policy": base_tracking_policy,
                    "fragment_context_policy": fragment_policy,
                    "suppression_risk": suppression_risk,
                    "temporal_review_needed": bool_text(temporal_review),
                    "known_side_effect_det_ids": unique_join(side_effect_det_ids),
                    "why_not_identity_truth": WHY_NOT_IDENTITY_TRUTH,
                }
            )

            for det_id in sorted(component):
                row = rows_by_id[det_id]
                row_labels, row_tags = row_context(det_id, comp_pair_rows)
                side_effect = side_effects.get(det_id, {})
                row_tracking_policy = tracking_policy_for_row(det_id, primary, family, base_tracking_policy)
                role_rows.append(
                    {
                        "scene": scene,
                        "detector_label": detector_label,
                        "optical_frame_num": frame,
                        "raw_det_id": det_id,
                        "observation_component_id": comp_id,
                        "component_size": len(component),
                        "component_role": component_role(det_id, primary, family, len(component)),
                        "class_name": row.get("class_name", ""),
                        "confidence": row.get("confidence", ""),
                        "component_conflict_family": family,
                        "component_policy": component_policy,
                        "tracking_policy": row_tracking_policy,
                        "fragment_context_policy": fragment_policy,
                        "suppression_risk": suppression_risk,
                        "temporal_review_needed": bool_text(temporal_review),
                        "row_pair_labels": unique_join(row_labels),
                        "row_state_tags": grouping.join_tags(row_tags),
                        "known_side_effect_assessment": side_effect.get("side_effect_assessment", ""),
                        "known_side_effect_policy": side_effect.get("recommended_component_policy", ""),
                        "primary_candidate": primary,
                        "why_not_identity_truth": WHY_NOT_IDENTITY_TRUTH,
                    }
                )
    return component_rows, role_rows


def summarize_scene(
    scene: str,
    detector_label: str,
    source_detection_table: Path,
    timestamp: str,
    detection_rows: Sequence[Mapping[str, Any]],
    component_rows: Sequence[Mapping[str, Any]],
    role_rows: Sequence[Mapping[str, Any]],
    component_output_path: Path,
    row_role_output_path: Path,
) -> dict[str, Any]:
    family_counts = Counter(str(row.get("component_conflict_family", "")) for row in component_rows)
    role_family_counts = Counter(str(row.get("component_conflict_family", "")) for row in role_rows)
    tracking_counts = Counter(str(row.get("tracking_policy", "")) for row in role_rows)
    known_components = sum(1 for row in component_rows if str(row.get("known_side_effect_det_ids", "")))
    frames = {
        grouping.parse_int(row.get("optical_frame_num"))
        for row in detection_rows
        if grouping.parse_int(row.get("optical_frame_num")) is not None
    }
    return {
        "scene": scene,
        "detector_label": detector_label,
        "source_detection_table": str(source_detection_table),
        "timestamp": timestamp,
        "total_detection_rows": len(detection_rows),
        "frames_with_detections": len(frames),
        "component_count": len(component_rows),
        "candidate_component_count": len(component_rows) - family_counts["orphan_no_multibox_candidate"],
        "orphan_component_count": family_counts["orphan_no_multibox_candidate"],
        "clean_duplicate_pressure_components": family_counts["clean_duplicate_pressure"],
        "continuity_useful_duplicate_context_components": family_counts["continuity_useful_duplicate_context"],
        "partial_full_review_context_components": family_counts["partial_full_review_context"],
        "neighbor_multi_object_competition_components": family_counts["neighbor_multi_object_competition"],
        "unresolved_review_required_components": family_counts["unresolved_review_required"],
        "clean_duplicate_pressure_rows": role_family_counts["clean_duplicate_pressure"],
        "continuity_useful_duplicate_context_rows": role_family_counts["continuity_useful_duplicate_context"],
        "partial_full_review_context_rows": role_family_counts["partial_full_review_context"],
        "neighbor_multi_object_competition_rows": role_family_counts["neighbor_multi_object_competition"],
        "unresolved_review_required_rows": role_family_counts["unresolved_review_required"],
        "secondary_suppress_for_tracking_rows": tracking_counts["secondary_suppress_for_tracking"],
        "secondary_keep_for_continuity_context_rows": tracking_counts["secondary_keep_for_continuity_context"],
        "keep_block_auto_grouping_rows": tracking_counts["keep_block_auto_grouping"],
        "review_required_rows": tracking_counts["review_required"],
        "known_side_effect_components": known_components,
        "known_side_effect_rows": sum(1 for row in role_rows if str(row.get("known_side_effect_policy", ""))),
        "component_output_path": str(component_output_path),
        "row_role_output_path": str(row_role_output_path),
    }


def run_dryrun(args: argparse.Namespace) -> dict[str, Any]:
    detection_table = Path(args.input_detection_table)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    side_effects = load_side_effect_samples(Path(args.side_effect_samples) if args.side_effect_samples else None)

    detection_rows = read_scene_detections(detection_table, args.scene)
    pair_rows, by_frame = build_pair_candidates(detection_rows, args.scene, args.detector_label)
    component_rows, role_rows = build_component_outputs(
        args.scene,
        args.detector_label,
        detection_rows,
        pair_rows,
        by_frame,
        side_effects,
    )

    prefix = f"{grouping.safe_name(args.scene)}_{grouping.safe_name(args.detector_label)}"
    component_output_path = output_dir / f"{prefix}_observation_components.csv"
    row_role_output_path = output_dir / f"{prefix}_observation_component_rows.csv"
    scene_summary_path = output_dir / f"{prefix}_observation_component_scene_summary.csv"
    json_path = output_dir / f"{prefix}_observation_component_grouping_dryrun.json"

    scene_summary = summarize_scene(
        args.scene,
        args.detector_label,
        detection_table,
        timestamp,
        detection_rows,
        component_rows,
        role_rows,
        component_output_path,
        row_role_output_path,
    )
    write_csv(component_output_path, component_rows, COMPONENT_FIELDS)
    write_csv(row_role_output_path, role_rows, ROW_FIELDS)
    write_csv(scene_summary_path, [scene_summary], SCENE_SUMMARY_FIELDS)
    write_json(
        json_path,
        {
            "boundary": (
                "component-level OTY0-post dry run only; raw detections remain evidence; "
                "no merged boxes, runtime replacement, SAR/support, final annotation, "
                "revised GT, selector/ranking, threshold tuning, or identity truth"
            ),
            "scene_summary": scene_summary,
            "outputs": {
                "component_output_path": str(component_output_path),
                "row_role_output_path": str(row_role_output_path),
                "scene_summary_path": str(scene_summary_path),
            },
            "policy_families": [
                "clean_duplicate_pressure",
                "continuity_useful_duplicate_context",
                "partial_full_review_context",
                "neighbor_multi_object_competition",
                "unresolved_review_required",
                "orphan_no_multibox_candidate",
            ],
        },
    )
    return scene_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-detection-table", required=True, type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--detector-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--side-effect-samples", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_detection_table.exists():
        raise FileNotFoundError(args.input_detection_table)
    summary = run_dryrun(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
