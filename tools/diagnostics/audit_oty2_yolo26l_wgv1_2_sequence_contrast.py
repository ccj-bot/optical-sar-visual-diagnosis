#!/usr/bin/env python
"""Audit V1.1 fragments for V1.2 sequence continuity and multi-car contrast.

This is a diagnostic-only precheck for optical timeline graph construction. It
does not run detection, tracker replay, SAR pairing, selector/ranking, or any
final annotation generation.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRAGMENTS = (
    REPO_ROOT
    / "reports/oty2/samples/"
    "oty2_yolo26l_optical_timeline_working_graph_v1_1_vehicle_fragments_20260708.csv"
)
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "reports/oty2/samples/"
    "oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "reports/oty2/samples/"
    "oty2_yolo26l_wgv1_2_sequence_contrast_audit_20260708.csv"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def y26_nodes(fragment: dict[str, str]) -> list[str]:
    return [
        value.strip()
        for value in fragment["source_candidate_node_ids"].split(";")
        if value.strip() and "_Y26N" in value
    ]


def center_x(row: dict[str, str]) -> float:
    return (float(row["bbox_x1"]) + float(row["bbox_x2"])) / 2.0


def center_y(row: dict[str, str]) -> float:
    return (float(row["bbox_y1"]) + float(row["bbox_y2"])) / 2.0


def width(row: dict[str, str]) -> float:
    return float(row["bbox_x2"]) - float(row["bbox_x1"])


def height(row: dict[str, str]) -> float:
    return float(row["bbox_y2"]) - float(row["bbox_y1"])


def area(row: dict[str, str]) -> float:
    return max(width(row), 0.0) * max(height(row), 0.0)


def x_bin(cx: float) -> str:
    if cx < 800.0 / 3.0:
        return "left"
    if cx < 1600.0 / 3.0:
        return "mid"
    return "right"


def unique_detection_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: (int(r["optical_frame_num"]), r["source_detection_id"], r["candidate_node_id"])):
        key = row["source_detection_id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def ratio_pair(a: float, b: float) -> float:
    lo = max(min(a, b), 1e-6)
    hi = max(a, b)
    return hi / lo


def source_detection_reuse_index(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        out[row["source_detection_id"]].add(row["candidate_node_id"])
    return out


def frame_contrast_index(rows: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, object]]:
    by_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_frame[(row["scene_id"], int(row["optical_frame_num"]))].append(row)

    out: dict[tuple[str, int], dict[str, object]] = {}
    for key, frame_rows in by_frame.items():
        source_ids = {row["source_detection_id"] for row in frame_rows}
        node_ids = {row["candidate_node_id"] for row in frame_rows}
        multi_tag_rows = [
            row for row in frame_rows if "multi_box_competition" in row.get("risk_tags", "")
        ]
        out[key] = {
            "distinct_source_detection_count": len(source_ids),
            "candidate_node_count": len(node_ids),
            "has_multi_box_tag": bool(multi_tag_rows),
            "source_detection_ids": sorted(source_ids),
            "candidate_node_ids": sorted(node_ids),
        }
    return out


def significant_sign(value: float, threshold: float = 25.0) -> int:
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


def analyze_fragment(
    fragment: dict[str, str],
    manifest_rows: list[dict[str, str]],
    reuse_index: dict[str, set[str]],
    contrast_index: dict[tuple[str, int], dict[str, object]],
) -> dict[str, str]:
    scene_id = fragment["scene_id"]
    start = int(fragment["frame_start"])
    end = int(fragment["frame_end"])
    nodes = y26_nodes(fragment)
    frame_span_count = end - start + 1

    selected_rows = [
        row
        for row in manifest_rows
        if row["scene_id"] == scene_id
        and start <= int(row["optical_frame_num"]) <= end
        and row["candidate_node_id"] in nodes
    ]
    rows = unique_detection_rows(selected_rows)
    frames = [int(row["optical_frame_num"]) for row in rows]
    centers_x = [center_x(row) for row in rows]
    centers_y = [center_y(row) for row in rows]
    widths = [width(row) for row in rows]
    heights = [height(row) for row in rows]
    areas = [area(row) for row in rows]
    bins = [x_bin(cx) for cx in centers_x]
    classes = [row["class_name"] for row in rows]

    frame_gaps: list[int] = []
    dx_values: list[float] = []
    dy_values: list[float] = []
    dx_per_frame_values: list[float] = []
    area_ratios: list[float] = []
    width_ratios: list[float] = []
    height_ratios: list[float] = []
    norm_dx_values: list[float] = []
    for idx in range(1, len(rows)):
        gap = frames[idx] - frames[idx - 1]
        frame_gaps.append(gap)
        dx = centers_x[idx] - centers_x[idx - 1]
        dy = centers_y[idx] - centers_y[idx - 1]
        dx_values.append(dx)
        dy_values.append(dy)
        dx_per_frame_values.append(abs(dx) / max(gap, 1))
        area_ratios.append(ratio_pair(areas[idx], areas[idx - 1]))
        width_ratios.append(ratio_pair(widths[idx], widths[idx - 1]))
        height_ratios.append(ratio_pair(heights[idx], heights[idx - 1]))
        norm_dx_values.append(abs(dx) / max(max(widths[idx], widths[idx - 1]), 1.0))

    signs = [significant_sign(dx) for dx in dx_values]
    signs = [sign for sign in signs if sign != 0]
    sign_changes = sum(1 for a, b in zip(signs, signs[1:]) if a != b)

    duplicate_reuse_count = sum(
        1 for row in rows if len(reuse_index[row["source_detection_id"]]) > 1
    )

    frame_contrast_counts: list[int] = []
    contrast_undercoverage_frames: list[str] = []
    for frame in frames:
        contrast = contrast_index.get((scene_id, frame), {})
        distinct_count = int(contrast.get("distinct_source_detection_count", 0))
        frame_contrast_counts.append(distinct_count)
        if contrast.get("has_multi_box_tag") and distinct_count <= 1:
            contrast_undercoverage_frames.append(str(frame))

    max_dx_per_frame = max(dx_per_frame_values) if dx_per_frame_values else 0.0
    median_dx_per_frame = median(dx_per_frame_values) if dx_per_frame_values else 0.0
    max_norm_dx = max(norm_dx_values) if norm_dx_values else 0.0
    max_area_ratio = max(area_ratios) if area_ratios else 1.0
    max_width_ratio = max(width_ratios) if width_ratios else 1.0
    max_height_ratio = max(height_ratios) if height_ratios else 1.0
    max_gap = max(frame_gaps) if frame_gaps else 0
    coverage_ratio = len(set(frames)) / frame_span_count if frame_span_count else 0.0

    flags: list[str] = []
    if len(set(classes)) > 1:
        flags.append("class_switch")
    if max_dx_per_frame > 120.0:
        flags.append("hard_center_offset_jump")
    elif max_dx_per_frame > 60.0:
        flags.append("review_center_offset_jump")
    if max_norm_dx > 0.65:
        flags.append("hard_normalized_offset_jump")
    elif max_norm_dx > 0.35:
        flags.append("review_normalized_offset_jump")
    if max_area_ratio > 2.5:
        flags.append("hard_area_ratio_jump")
    elif max_area_ratio > 1.8:
        flags.append("review_area_ratio_jump")
    if max_gap > 2:
        flags.append("sequence_gap")
    if sign_changes >= 2:
        flags.append("back_and_forth_motion")
    if len(set(bins)) > 1 and max_dx_per_frame > 60.0:
        flags.append("spatial_bin_transition")
    if duplicate_reuse_count:
        flags.append("source_detection_reused_by_nodes")
    if contrast_undercoverage_frames:
        flags.append("multicar_contrast_undercovered")
    if fragment["accepted_status"] in {"blocked", "forbidden"}:
        flags.append("not_vehicle_identity_input")

    hard_flags = [
        flag
        for flag in flags
        if flag.startswith("hard_")
        or flag in {
            "class_switch",
            "source_detection_reused_by_nodes",
            "not_vehicle_identity_input",
        }
    ]

    if fragment["accepted_status"] in {"blocked", "forbidden"}:
        recommendation = "route_to_switch_or_context_event"
    elif hard_flags:
        recommendation = "block_vehicle_merge_until_target_family_split"
    elif "multicar_contrast_undercovered" in flags:
        recommendation = "review_multicar_contrast_before_merge"
    elif flags:
        recommendation = "review_sequence_before_same_vehicle_edge"
    else:
        recommendation = "sequence_guardrail_passes_diagnostic_precheck"

    return {
        "fragment_id": fragment["fragment_id"],
        "scene_id": scene_id,
        "frame_start": str(start),
        "frame_end": str(end),
        "accepted_status": fragment["accepted_status"],
        "identity_safety_status": fragment["identity_safety_status"],
        "source_candidate_node_ids": ";".join(nodes),
        "frame_span_count": str(frame_span_count),
        "selected_unique_frame_count": str(len(set(frames))),
        "coverage_ratio": f"{coverage_ratio:.3f}",
        "frame_sequence": " ".join(str(frame) for frame in frames),
        "frame_gap_sequence": " ".join(str(gap) for gap in frame_gaps),
        "x_center_sequence": " ".join(f"{value:.1f}" for value in centers_x),
        "x_bin_sequence": " ".join(bins),
        "class_sequence": " ".join(classes),
        "dx_per_frame_sequence": " ".join(f"{abs(value) / max(gap, 1):.1f}" for value, gap in zip(dx_values, frame_gaps)),
        "max_dx_per_frame_px": f"{max_dx_per_frame:.1f}",
        "median_dx_per_frame_px": f"{median_dx_per_frame:.1f}",
        "max_normalized_dx_by_box_width": f"{max_norm_dx:.3f}",
        "max_area_ratio": f"{max_area_ratio:.3f}",
        "max_width_ratio": f"{max_width_ratio:.3f}",
        "max_height_ratio": f"{max_height_ratio:.3f}",
        "motion_sign_change_count": str(sign_changes),
        "duplicate_source_detection_count": str(duplicate_reuse_count),
        "same_frame_distinct_source_detection_min": str(min(frame_contrast_counts) if frame_contrast_counts else 0),
        "same_frame_distinct_source_detection_max": str(max(frame_contrast_counts) if frame_contrast_counts else 0),
        "contrast_undercoverage_frames": " ".join(contrast_undercoverage_frames),
        "sequence_guardrail_flags": ";".join(flags) if flags else "none",
        "v1_2_sequence_contrast_recommendation": recommendation,
        "sar_ready": "no / blocked",
        "note": "diagnostic precheck only;not final boxes;not GT;not revised annotation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    fragments = read_csv(args.fragments)
    manifest_rows = read_csv(args.manifest)
    reuse_index = source_detection_reuse_index(manifest_rows)
    contrast_index = frame_contrast_index(manifest_rows)

    rows = [
        analyze_fragment(fragment, manifest_rows, reuse_index, contrast_index)
        for fragment in fragments
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {args.output}")
    for row in rows:
        if row["v1_2_sequence_contrast_recommendation"] != "sequence_guardrail_passes_diagnostic_precheck":
            print(
                row["fragment_id"],
                row["sequence_guardrail_flags"],
                row["v1_2_sequence_contrast_recommendation"],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
