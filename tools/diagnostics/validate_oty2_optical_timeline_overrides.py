"""Dry-run validator for OTY2 optical timeline manual override rows.

The override table is allowed to affect only the diagnostic optical timeline
graph and diagnostic render manifest. This script does not apply overrides and
does not write final annotations, revised annotations, final boxes, GT boxes,
SAR pairing/support rows, selector/ranking outputs, or render outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OVERRIDES = REPO_ROOT / "manifests" / "oty2_optical_timeline_override_template.csv"
DEFAULT_NODES = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_optical_timeline_graph_nodes_20260705_175222.csv"
DEFAULT_EDGES = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_optical_timeline_graph_edges_20260705_175222.csv"
DEFAULT_MANIFEST = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_optical_timeline_video_render_manifest_20260705_175222.csv"

CONTRACT_COLUMNS = [
    "override_id",
    "override_type",
    "override_scope",
    "event_id",
    "scene_id",
    "node_id",
    "from_node_id",
    "to_node_id",
    "bs_id",
    "seg_id",
    "frame_start",
    "frame_end",
    "target_node_id",
    "action",
    "edge_strength",
    "source_detection_id",
    "reason_code",
    "evidence_frame_start",
    "evidence_frame_end",
    "confidence",
    "review_status",
    "note",
]

FORBIDDEN_COLUMNS = {
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_width",
    "bbox_height",
    "final_box",
    "gt_box",
    "revised_box",
    "final_annotation",
    "revised_annotation",
}

ACTIONS = {
    "node": {
        "keep_vehicle_node",
        "exclude_non_vehicle",
        "mark_bad_detection_node",
        "mark_review_required",
        "split_node",
        "merge_node",
    },
    "edge": {
        "force_strong_connect",
        "force_weak_connect",
        "forbid_connect",
        "downgrade_to_weak",
        "upgrade_to_strong",
        "mark_review_required",
    },
    "render": {
        "hide_bad_box_for_render",
        "select_diagnostic_primary_box",
        "show_review_marker",
        "show_forbidden_edge_marker",
        "show_weak_edge_marker",
        "show_non_vehicle_marker",
    },
}

COMPATIBLE_SCOPES = {
    "node": {"node", "interval", "event"},
    "edge": {"edge", "event"},
    "render": {"event", "interval"},
}

REVIEW_STATUSES = {"proposed", "reviewed_accept", "reviewed_reject", "needs_second_review"}
EDGE_STRENGTHS = {"strong", "weak", "forbidden", "review_only", "excluded"}
REASON_CODES = {
    "same_vehicle_continuity",
    "weak_continuity_only",
    "forbidden_competitor_switch",
    "non_vehicle_barrier",
    "bad_detection_box_fit",
    "bad_frame_unreadable",
    "edge_contact_thin_crop",
    "part_state_transition",
    "multi_object_competition",
    "visible_unboxed_vehicle_gap",
    "diagnostic_primary_box_selection",
    "review_uncertain",
    "other_review_note",
}

COMMON_REQUIRED = {"override_id", "override_type", "override_scope", "scene_id", "action", "reason_code", "review_status"}


@dataclass
class ReferenceState:
    node_ids: set[str]
    edge_pairs: set[tuple[str, str, str]]
    source_detection_ids: set[str]


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader if not blank_row(row)]
    return fieldnames, rows


def blank_row(row: Mapping[str, Any]) -> bool:
    return not any(norm(value) for value in row.values())


def load_reference_state(nodes_path: Path, edges_path: Path, manifest_path: Path) -> ReferenceState:
    _, node_rows = read_csv(nodes_path)
    _, edge_rows = read_csv(edges_path)
    _, manifest_rows = read_csv(manifest_path)
    node_ids = {norm(row.get("node_id")) for row in node_rows if norm(row.get("node_id"))}
    edge_pairs = {
        (norm(row.get("scene")), norm(row.get("from_node")), norm(row.get("to_node")))
        for row in edge_rows
        if norm(row.get("scene")) and norm(row.get("from_node")) and norm(row.get("to_node"))
    }
    source_detection_ids = {norm(row.get("source_det_id")) for row in manifest_rows if norm(row.get("source_det_id"))}
    return ReferenceState(node_ids=node_ids, edge_pairs=edge_pairs, source_detection_ids=source_detection_ids)


def parse_int(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def valid_reason_code(value: str) -> bool:
    return value in REASON_CODES or value.startswith("custom_")


def validate_columns(fieldnames: Sequence[str]) -> list[str]:
    errors: list[str] = []
    missing = [name for name in CONTRACT_COLUMNS if name not in fieldnames]
    if missing:
        errors.append(f"missing required contract columns: {', '.join(missing)}")
    extra_forbidden = [
        name for name in fieldnames
        if name in FORBIDDEN_COLUMNS or name.startswith("bbox_") or name.startswith("gt_") or name.startswith("final_") or name.startswith("revised_")
    ]
    if extra_forbidden:
        errors.append(f"forbidden columns present: {', '.join(sorted(extra_forbidden))}")
    return errors


def require_fields(row: Mapping[str, str], fields: set[str], row_label: str, errors: list[str]) -> None:
    for field in sorted(fields):
        if not norm(row.get(field)):
            errors.append(f"{row_label}: missing required field `{field}`")


def validate_interval(row: Mapping[str, str], start_field: str, end_field: str, row_label: str, errors: list[str]) -> None:
    start_text = norm(row.get(start_field))
    end_text = norm(row.get(end_field))
    if not start_text and not end_text:
        return
    if not start_text or not end_text:
        errors.append(f"{row_label}: `{start_field}` and `{end_field}` must be provided together")
        return
    start = parse_int(start_text)
    end = parse_int(end_text)
    if start is None or end is None:
        errors.append(f"{row_label}: `{start_field}` and `{end_field}` must be integers")
    elif start > end:
        errors.append(f"{row_label}: `{start_field}` must be <= `{end_field}`")


def validate_confidence(row: Mapping[str, str], row_label: str, errors: list[str]) -> None:
    text = norm(row.get("confidence"))
    if not text:
        return
    try:
        value = float(text)
    except ValueError:
        errors.append(f"{row_label}: `confidence` must be numeric")
        return
    if value < 0.0 or value > 1.0:
        errors.append(f"{row_label}: `confidence` must be between 0.0 and 1.0")


def validate_row(
    row: Mapping[str, str],
    line_no: int,
    ref: ReferenceState,
    strict_source_detection: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    row_label = f"line {line_no} override_id={norm(row.get('override_id')) or '<blank>'}"
    require_fields(row, COMMON_REQUIRED, row_label, errors)

    override_type = norm(row.get("override_type"))
    override_scope = norm(row.get("override_scope"))
    action = norm(row.get("action"))
    reason_code = norm(row.get("reason_code"))
    review_status = norm(row.get("review_status"))

    if override_type not in ACTIONS:
        errors.append(f"{row_label}: invalid override_type `{override_type}`")
        return
    if override_scope not in COMPATIBLE_SCOPES[override_type]:
        errors.append(f"{row_label}: override_scope `{override_scope}` is not compatible with type `{override_type}`")
    if action not in ACTIONS[override_type]:
        errors.append(f"{row_label}: action `{action}` is not allowed for type `{override_type}`")
    if review_status and review_status not in REVIEW_STATUSES:
        errors.append(f"{row_label}: invalid review_status `{review_status}`")
    if reason_code and not valid_reason_code(reason_code):
        errors.append(f"{row_label}: invalid reason_code `{reason_code}`")

    validate_interval(row, "frame_start", "frame_end", row_label, errors)
    validate_interval(row, "evidence_frame_start", "evidence_frame_end", row_label, errors)
    validate_confidence(row, row_label, errors)

    if override_scope == "interval" and (not norm(row.get("frame_start")) or not norm(row.get("frame_end"))):
        errors.append(f"{row_label}: interval scope requires frame_start and frame_end")

    if override_type == "node":
        validate_node_row(row, row_label, ref, errors)
    elif override_type == "edge":
        validate_edge_row(row, row_label, ref, errors, warnings)
    elif override_type == "render":
        validate_render_row(row, row_label, ref, strict_source_detection, errors, warnings)


def validate_node_row(row: Mapping[str, str], row_label: str, ref: ReferenceState, errors: list[str]) -> None:
    require_fields(row, {"node_id"}, row_label, errors)
    node_id = norm(row.get("node_id"))
    if node_id and node_id not in ref.node_ids:
        errors.append(f"{row_label}: node_id `{node_id}` is not in the current node table")
    if norm(row.get("action")) in {"split_node", "merge_node"} and not norm(row.get("note")):
        errors.append(f"{row_label}: split_node/merge_node requires a note describing the diagnostic graph intent")


def validate_edge_row(
    row: Mapping[str, str],
    row_label: str,
    ref: ReferenceState,
    errors: list[str],
    warnings: list[str],
) -> None:
    require_fields(row, {"from_node_id", "to_node_id", "edge_strength"}, row_label, errors)
    scene = norm(row.get("scene_id"))
    from_node = norm(row.get("from_node_id"))
    to_node = norm(row.get("to_node_id"))
    action = norm(row.get("action"))
    edge_strength = norm(row.get("edge_strength"))

    for field, node_id in (("from_node_id", from_node), ("to_node_id", to_node)):
        if node_id and node_id not in ref.node_ids:
            errors.append(f"{row_label}: {field} `{node_id}` is not in the current node table")
    if edge_strength and edge_strength not in EDGE_STRENGTHS:
        errors.append(f"{row_label}: invalid edge_strength `{edge_strength}`")
    expected_strength = {
        "force_strong_connect": "strong",
        "upgrade_to_strong": "strong",
        "force_weak_connect": "weak",
        "downgrade_to_weak": "weak",
        "forbid_connect": "forbidden",
    }.get(action)
    if expected_strength and edge_strength and edge_strength != expected_strength:
        errors.append(f"{row_label}: action `{action}` expects edge_strength `{expected_strength}`")
    if scene and from_node and to_node and (scene, from_node, to_node) not in ref.edge_pairs:
        warnings.append(f"{row_label}: edge pair is not in the current edge table; dry-run treats it as a proposed diagnostic relation")


def validate_render_row(
    row: Mapping[str, str],
    row_label: str,
    ref: ReferenceState,
    strict_source_detection: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    require_fields(row, {"frame_start", "frame_end"}, row_label, errors)
    action = norm(row.get("action"))
    target_node = norm(row.get("target_node_id"))
    source_detection = norm(row.get("source_detection_id"))

    if target_node and target_node not in ref.node_ids:
        errors.append(f"{row_label}: target_node_id `{target_node}` is not in the current node table")
    if action == "select_diagnostic_primary_box":
        require_fields(row, {"target_node_id", "source_detection_id"}, row_label, errors)
    if action == "hide_bad_box_for_render" and not source_detection and not target_node:
        errors.append(f"{row_label}: hide_bad_box_for_render requires source_detection_id or target_node_id")
    if source_detection and source_detection not in ref.source_detection_ids:
        msg = f"{row_label}: source_detection_id `{source_detection}` is not in the current render manifest"
        if strict_source_detection:
            errors.append(msg)
        else:
            warnings.append(msg)


def summarize(rows: Sequence[Mapping[str, str]], warnings: Sequence[str], errors: Sequence[str]) -> dict[str, Any]:
    type_counts = Counter(norm(row.get("override_type")) for row in rows if norm(row.get("override_type")))
    action_counts = Counter(norm(row.get("action")) for row in rows if norm(row.get("action")))
    return {
        "override_rows": len(rows),
        "type_counts": dict(sorted(type_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "warnings": list(warnings),
        "errors": list(errors),
        "dry_run_only": True,
        "writes_files": False,
        "allowed_effect": "diagnostic timeline graph and diagnostic render manifest only",
    }


def validate(args: argparse.Namespace) -> dict[str, Any]:
    overrides_path = Path(args.overrides)
    nodes_path = Path(args.nodes)
    edges_path = Path(args.edges)
    manifest_path = Path(args.render_manifest)

    fieldnames, rows = read_csv(overrides_path)
    errors = validate_columns(fieldnames)
    warnings: list[str] = []
    ref = load_reference_state(nodes_path, edges_path, manifest_path)

    seen_ids: set[str] = set()
    for offset, row in enumerate(rows, start=2):
        override_id = norm(row.get("override_id"))
        if override_id:
            if override_id in seen_ids:
                errors.append(f"line {offset}: duplicate override_id `{override_id}`")
            seen_ids.add(override_id)
        validate_row(row, offset, ref, args.strict_source_detection, errors, warnings)

    return summarize(rows, warnings, errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overrides", default=str(DEFAULT_OVERRIDES), help="Manual override CSV to validate.")
    parser.add_argument("--nodes", default=str(DEFAULT_NODES), help="Current diagnostic node table.")
    parser.add_argument("--edges", default=str(DEFAULT_EDGES), help="Current diagnostic edge table.")
    parser.add_argument("--render-manifest", default=str(DEFAULT_MANIFEST), help="Current diagnostic render manifest.")
    parser.add_argument("--strict-source-detection", action="store_true", help="Require render override source_detection_id to exist in the current render manifest.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = validate(args)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"override_rows: {summary['override_rows']}")
        print(f"type_counts: {summary['type_counts']}")
        print(f"action_counts: {summary['action_counts']}")
        print(f"warnings: {len(summary['warnings'])}")
        for warning in summary["warnings"]:
            print(f"WARNING: {warning}")
        print(f"errors: {len(summary['errors'])}")
        for error in summary["errors"]:
            print(f"ERROR: {error}")
        print("dry_run_only: true")
        print("writes_files: false")
        print("allowed_effect: diagnostic timeline graph and diagnostic render manifest only")
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
