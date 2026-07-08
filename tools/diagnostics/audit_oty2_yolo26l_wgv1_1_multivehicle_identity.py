#!/usr/bin/env python
"""Audit YOLO26l WGV1.1 fragments for multi-vehicle identity failures.

This diagnostic script only reads committed CSV summaries plus the ignored local
review-pack directory when present. It does not run a detector, tracker, SAR
pairing, selector, ranking, or annotation generation.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


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
DEFAULT_PACK_DIR = (
    REPO_ROOT / "outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708"
)
DEFAULT_OUT = (
    REPO_ROOT
    / "reports/oty2/samples/"
    "oty2_yolo26l_wgv1_1_multivehicle_identity_audit_20260708.csv"
)

FOCUS_FRAGMENT_IDS = {
    "GM_RM011_WG11F005",
    "GM_RM011_WG11F017",
    "GM_RM017_WG11F002",
    "GM_RM017_WG11F003",
    "GM_RM017_WG11F004",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def source_nodes(fragment: dict[str, str]) -> list[str]:
    return [
        value.strip()
        for value in fragment["source_candidate_node_ids"].split(";")
        if value.strip() and "_Y26N" in value
    ]


def center_x(row: dict[str, str]) -> float:
    return (float(row["bbox_x1"]) + float(row["bbox_x2"])) / 2.0


def x_bin(cx: float) -> str:
    if cx < 800.0 / 3.0:
        return "left"
    if cx < 1600.0 / 3.0:
        return "mid"
    return "right"


def frame_span_count(start: int, end: int) -> int:
    return end - start + 1


def find_pack_folder(pack_dir: Path, fragment_id: str) -> Path | None:
    if not pack_dir.exists():
        return None
    matches = sorted(path for path in pack_dir.iterdir() if path.is_dir() and fragment_id in path.name)
    return matches[0] if matches else None


def pack_frame_count(pack_dir: Path, fragment_id: str) -> int:
    folder = find_pack_folder(pack_dir, fragment_id)
    if folder is None:
        return 0
    frames_dir = folder / "frames_yolo"
    return len(list(frames_dir.glob("*.png"))) if frames_dir.exists() else 0


def unique_detection_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: (int(r["optical_frame_num"]), r["source_detection_id"])):
        key = row["source_detection_id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def duplicate_source_detection_index(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    by_det: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_det[row["source_detection_id"]].add(row["candidate_node_id"])
    return by_det


def analyze_fragment(
    fragment: dict[str, str],
    manifest_rows: list[dict[str, str]],
    duplicate_index: dict[str, set[str]],
    pack_dir: Path,
) -> dict[str, str]:
    scene_id = fragment["scene_id"]
    frame_start = int(fragment["frame_start"])
    frame_end = int(fragment["frame_end"])
    nodes = source_nodes(fragment)

    selected_rows = [
        row
        for row in manifest_rows
        if row["scene_id"] == scene_id
        and frame_start <= int(row["optical_frame_num"]) <= frame_end
        and row["candidate_node_id"] in nodes
    ]
    unique_rows = unique_detection_rows(selected_rows)
    centers = [center_x(row) for row in unique_rows]
    bins = [x_bin(cx) for cx in centers]
    classes = sorted({row["class_name"] for row in unique_rows})
    frames = sorted({int(row["optical_frame_num"]) for row in unique_rows})
    duplicate_detections = [
        row["source_detection_id"]
        for row in unique_rows
        if len(duplicate_index[row["source_detection_id"]]) > 1
    ]

    jumps: list[float] = []
    previous_by_frame: dict[int, float] = {}
    for row in unique_rows:
        previous_by_frame[int(row["optical_frame_num"])] = center_x(row)
    ordered_frames = sorted(previous_by_frame)
    for prev, cur in zip(ordered_frames, ordered_frames[1:]):
        jumps.append(abs(previous_by_frame[cur] - previous_by_frame[prev]))
    max_jump = max(jumps) if jumps else 0.0

    span_count = frame_span_count(frame_start, frame_end)
    local_pack_count = pack_frame_count(pack_dir, fragment["fragment_id"])

    flags: list[str] = []
    if len(classes) > 1:
        flags.append("class_switch_inside_fragment")
    if max_jump > 120.0:
        flags.append("large_center_jump")
    if len(set(bins)) > 1:
        flags.append("left_mid_right_bin_switch")
    if len(duplicate_detections) > 0:
        flags.append("source_detection_reused_by_multiple_candidate_nodes")
    if len(frames) < span_count:
        flags.append("sparse_selected_frames_inside_fragment_span")
    if local_pack_count > 0 and local_pack_count > len(frames):
        flags.append("review_pack_frame_range_overrun")
    if fragment["accepted_status"] in {"blocked", "forbidden"}:
        flags.append("not_a_vehicle_identity_fragment")

    if fragment["fragment_id"] == "GM_RM011_WG11F005":
        recommendation = "reclassify_as_switch_zone;do_not_render_as_vehicle_fragment"
    elif fragment["fragment_id"] == "GM_RM011_WG11F017":
        recommendation = "render_context_only_selected_frames_283_286;do_not_use_full_frame_range"
    elif fragment["fragment_id"] in {
        "GM_RM017_WG11F002",
        "GM_RM017_WG11F003",
        "GM_RM017_WG11F004",
    }:
        recommendation = "demote_to_multi_target_review_window;require_target_family_split_before_vehicle_folder"
    elif flags:
        recommendation = "requires_identity_safe_split_or_context_reclassification"
    else:
        recommendation = "no_multivehicle_guardrail_triggered"

    return {
        "fragment_id": fragment["fragment_id"],
        "scene_id": scene_id,
        "frame_start": str(frame_start),
        "frame_end": str(frame_end),
        "accepted_status": fragment["accepted_status"],
        "identity_safety_status": fragment["identity_safety_status"],
        "source_candidate_node_ids": ";".join(nodes),
        "span_frame_count": str(span_count),
        "selected_frame_count": str(len(frames)),
        "selected_manifest_row_count": str(len(selected_rows)),
        "unique_detection_count": str(len(unique_rows)),
        "pack_frames_yolo_count": str(local_pack_count) if local_pack_count else "",
        "class_names": ";".join(classes) if classes else "none",
        "x_bin_sequence": " ".join(bins),
        "x_bin_set": ";".join(sorted(set(bins))) if bins else "none",
        "max_center_jump_px": f"{max_jump:.1f}",
        "duplicate_source_detection_count": str(len(duplicate_detections)),
        "risk_flags": ";".join(flags) if flags else "none",
        "v1_2_mechanism_recommendation": recommendation,
        "sar_ready": "no / blocked",
        "note": "diagnostic audit only;not final boxes;not GT;not revised annotation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    fragments = read_csv(args.fragments)
    manifest_rows = read_csv(args.manifest)
    duplicate_index = duplicate_source_detection_index(manifest_rows)

    rows = [
        analyze_fragment(fragment, manifest_rows, duplicate_index, args.pack_dir)
        for fragment in fragments
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {args.output}")
    print("focus fragments:")
    for row in rows:
        if row["fragment_id"] in FOCUS_FRAGMENT_IDS:
            print(
                row["fragment_id"],
                row["risk_flags"],
                row["v1_2_mechanism_recommendation"],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
