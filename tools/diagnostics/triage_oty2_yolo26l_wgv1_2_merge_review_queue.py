#!/usr/bin/env python
"""Triage YOLO26l WGV1.2 same-vehicle merge review queue.

This script ranks review-only merge candidates for human inspection. It does
not accept merges, create final boxes, create GT boxes, create revised
annotations, run tracker replay, or enter SAR.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from math import hypot
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"
REPORTS_DIR = REPO_ROOT / "reports/oty2"

DEFAULT_QUEUE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_review_queue_20260708.csv"
DEFAULT_BANK = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv"
DEFAULT_ITEM_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_manifest_20260708.csv"
DEFAULT_TRIAGE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_merge_review_queue_triage_20260708.csv"
DEFAULT_REPORT = REPORTS_DIR / "oty2_yolo26l_wgv1_2_merge_review_queue_triage_20260708.md"

FIELDS = [
    "review_item_id",
    "merge_candidate_id",
    "scene_id",
    "from_target_family_id",
    "to_target_family_id",
    "frame_start",
    "frame_end",
    "from_endpoint_frame",
    "to_endpoint_frame",
    "gap_frame_count",
    "endpoint_dx_px",
    "endpoint_dy_px",
    "endpoint_distance_px",
    "endpoint_dx_per_step_px",
    "endpoint_area_ratio",
    "from_endpoint_class",
    "to_endpoint_class",
    "class_switch_flag",
    "from_endpoint_x_bin",
    "to_endpoint_x_bin",
    "x_bin_switch_flag",
    "selected_primary_frames",
    "competing_candidate_frames",
    "detectionless_frames",
    "competing_frame_ratio",
    "same_frame_close_competitor_frames",
    "same_frame_class_competitor_frames",
    "max_same_frame_competitor_iou",
    "max_selected_step_dx_px",
    "max_selected_step_area_ratio",
    "risk_level",
    "machine_triage_label",
    "risk_reason_codes",
    "recommended_human_focus",
    "auto_merge_allowed",
    "sar_ready",
    "not_final_box_flag",
    "not_revised_annotation_flag",
    "note",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def as_int(value: str) -> int:
    return int(float(value))


def as_float(value: str) -> float:
    return float(value)


def area(row: dict[str, str]) -> float:
    return max(0.0, as_float(row["bbox_w"]) * as_float(row["bbox_h"]))


def center(row: dict[str, str]) -> tuple[float, float]:
    return as_float(row["bbox_cx"]), as_float(row["bbox_cy"])


def target_ids(row: dict[str, str]) -> set[str]:
    return {part for part in row.get("linked_target_family_ids", "").split(";") if part}


def has_target(row: dict[str, str], target_family_id: str) -> bool:
    return target_family_id in target_ids(row)


def bbox(row: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        as_float(row["bbox_x1"]),
        as_float(row["bbox_y1"]),
        as_float(row["bbox_x2"]),
        as_float(row["bbox_y2"]),
    )


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


def selected_rows_for_target(
    rows_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]],
    scene_id: str,
    target_family_id: str,
    frame_start: int,
    frame_end: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for frame in range(frame_start, frame_end + 1):
        for row in rows_by_scene_frame.get((scene_id, frame), []):
            if has_target(row, target_family_id):
                rows.append(row)
    return sorted(rows, key=lambda row: as_int(row["frame_id"]))


def safe_ratio(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 999.0
    return max(a, b) / min(a, b)


def selected_step_metrics(rows: list[dict[str, str]]) -> tuple[float, float]:
    max_dx = 0.0
    max_area_ratio = 1.0
    prev: dict[str, str] | None = None
    for row in rows:
        if prev is None:
            prev = row
            continue
        frame_gap = max(1, as_int(row["frame_id"]) - as_int(prev["frame_id"]))
        cx0, cy0 = center(prev)
        cx1, cy1 = center(row)
        max_dx = max(max_dx, hypot(cx1 - cx0, cy1 - cy0) / frame_gap)
        max_area_ratio = max(max_area_ratio, safe_ratio(area(prev), area(row)))
        prev = row
    return max_dx, max_area_ratio


def same_frame_competition_metrics(
    rows_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]],
    scene_id: str,
    selected_rows: list[dict[str, str]],
) -> tuple[int, int, float]:
    close_frames: set[int] = set()
    class_frames: set[int] = set()
    max_iou = 0.0
    for selected in selected_rows:
        frame = as_int(selected["frame_id"])
        sx, sy = center(selected)
        selected_bbox = bbox(selected)
        selected_targets = target_ids(selected)
        for cand in rows_by_scene_frame.get((scene_id, frame), []):
            if cand["source_detection_id"] == selected["source_detection_id"]:
                continue
            if selected_targets & target_ids(cand):
                continue
            cx, cy = center(cand)
            dist = hypot(cx - sx, cy - sy)
            cand_iou = iou(selected_bbox, bbox(cand))
            max_iou = max(max_iou, cand_iou)
            if dist <= 160.0 or cand_iou >= 0.10:
                close_frames.add(frame)
            if cand["class_name"] != selected["class_name"]:
                class_frames.add(frame)
    return len(close_frames), len(class_frames), max_iou


def risk_label(reason_codes: list[str]) -> tuple[str, str]:
    hard = {
        "endpoint_center_jump_high",
        "class_switch",
        "x_bin_switch",
        "selected_sequence_jump_high",
        "selected_area_jump_high",
        "same_frame_class_competition",
    }
    medium = {
        "same_frame_close_competition",
        "high_competing_frame_ratio",
        "endpoint_area_ratio_review",
        "detectionless_gap_context",
    }
    if any(code in hard for code in reason_codes):
        return "high", "manual_review_high_risk_keep_separate_until_confirmed"
    if any(code in medium for code in reason_codes):
        return "medium", "manual_review_candidate_with_competing_context"
    return "low", "manual_review_candidate_no_auto_merge"


def focus_text(reason_codes: list[str]) -> str:
    focus = []
    if "class_switch" in reason_codes or "same_frame_class_competition" in reason_codes:
        focus.append("class/vehicle-type conflict")
    if "x_bin_switch" in reason_codes:
        focus.append("left/mid/right lane-slot continuity")
    if "endpoint_center_jump_high" in reason_codes or "selected_sequence_jump_high" in reason_codes:
        focus.append("center trajectory continuity")
    if "same_frame_close_competition" in reason_codes or "high_competing_frame_ratio" in reason_codes:
        focus.append("same-frame competing vehicle choice")
    if "detectionless_gap_context" in reason_codes:
        focus.append("detectionless gap frames")
    if "endpoint_area_ratio_review" in reason_codes or "selected_area_jump_high" in reason_codes:
        focus.append("box area / partial-full transition")
    return "; ".join(focus) if focus else "confirm same-vehicle referent visually"


def triage_rows(
    queue: list[dict[str, str]],
    bank: list[dict[str, str]],
    item_manifest: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in bank:
        rows_by_scene_frame.setdefault((row["scene_id"], as_int(row["frame_id"])), []).append(row)
    item_by_id = {row["review_item_id"]: row for row in item_manifest}
    out: list[dict[str, str]] = []

    for item in queue:
        scene_id = item["scene_id"]
        from_tf = item["from_target_family_id"]
        to_tf = item["to_target_family_id"]
        from_start = as_int(item["from_frame_start"])
        from_end = as_int(item["from_frame_end"])
        to_start = as_int(item["to_frame_start"])
        to_end = as_int(item["to_frame_end"])
        manifest = item_by_id[item["review_item_id"]]
        from_rows = selected_rows_for_target(rows_by_scene_frame, scene_id, from_tf, from_start, from_end)
        to_rows = selected_rows_for_target(rows_by_scene_frame, scene_id, to_tf, to_start, to_end)
        combined_selected = sorted([*from_rows, *to_rows], key=lambda row: as_int(row["frame_id"]))

        from_endpoint = from_rows[-1] if from_rows else None
        to_endpoint = to_rows[0] if to_rows else None
        reason_codes: list[str] = []
        if from_endpoint and to_endpoint:
            fx, fy = center(from_endpoint)
            tx, ty = center(to_endpoint)
            dx = abs(tx - fx)
            dy = abs(ty - fy)
            distance = hypot(tx - fx, ty - fy)
            gap = max(0, as_int(to_endpoint["frame_id"]) - as_int(from_endpoint["frame_id"]) - 1)
            dx_per_step = distance / max(1, gap + 1)
            area_ratio = safe_ratio(area(from_endpoint), area(to_endpoint))
            class_switch = from_endpoint["class_name"] != to_endpoint["class_name"]
            x_bin_switch = from_endpoint["x_bin"] != to_endpoint["x_bin"]
            if dx_per_step > 90.0:
                reason_codes.append("endpoint_center_jump_high")
            elif dx_per_step > 45.0:
                reason_codes.append("endpoint_center_jump_review")
            if area_ratio > 2.4:
                reason_codes.append("endpoint_area_ratio_review")
            if class_switch:
                reason_codes.append("class_switch")
            if x_bin_switch:
                reason_codes.append("x_bin_switch")
        else:
            dx = dy = distance = dx_per_step = 0.0
            gap = max(0, to_start - from_end - 1)
            area_ratio = 999.0
            class_switch = False
            x_bin_switch = False
            reason_codes.append("missing_endpoint_selected_candidate")

        max_step_dx, max_step_area = selected_step_metrics(combined_selected)
        if max_step_dx > 120.0:
            reason_codes.append("selected_sequence_jump_high")
        if max_step_area > 2.8:
            reason_codes.append("selected_area_jump_high")

        close_frames, class_competition_frames, max_comp_iou = same_frame_competition_metrics(
            rows_by_scene_frame,
            scene_id,
            combined_selected,
        )
        competing_frames = as_int(manifest["competing_candidate_frames"])
        frame_count = max(1, as_int(manifest["frame_count"]))
        competing_ratio = competing_frames / frame_count
        if competing_ratio >= 0.50:
            reason_codes.append("high_competing_frame_ratio")
        if close_frames:
            reason_codes.append("same_frame_close_competition")
        if class_competition_frames:
            reason_codes.append("same_frame_class_competition")
        if as_int(manifest["detectionless_frames"]):
            reason_codes.append("detectionless_gap_context")

        reason_codes = sorted(set(reason_codes))
        risk, label = risk_label(reason_codes)
        out.append(
            {
                "review_item_id": item["review_item_id"],
                "merge_candidate_id": item["merge_candidate_id"],
                "scene_id": scene_id,
                "from_target_family_id": from_tf,
                "to_target_family_id": to_tf,
                "frame_start": manifest["frame_start"],
                "frame_end": manifest["frame_end"],
                "from_endpoint_frame": from_endpoint["frame_id"] if from_endpoint else "",
                "to_endpoint_frame": to_endpoint["frame_id"] if to_endpoint else "",
                "gap_frame_count": str(gap),
                "endpoint_dx_px": f"{dx:.1f}",
                "endpoint_dy_px": f"{dy:.1f}",
                "endpoint_distance_px": f"{distance:.1f}",
                "endpoint_dx_per_step_px": f"{dx_per_step:.1f}",
                "endpoint_area_ratio": f"{area_ratio:.3f}",
                "from_endpoint_class": from_endpoint["class_name"] if from_endpoint else "",
                "to_endpoint_class": to_endpoint["class_name"] if to_endpoint else "",
                "class_switch_flag": "yes" if class_switch else "no",
                "from_endpoint_x_bin": from_endpoint["x_bin"] if from_endpoint else "",
                "to_endpoint_x_bin": to_endpoint["x_bin"] if to_endpoint else "",
                "x_bin_switch_flag": "yes" if x_bin_switch else "no",
                "selected_primary_frames": manifest["selected_primary_frames"],
                "competing_candidate_frames": manifest["competing_candidate_frames"],
                "detectionless_frames": manifest["detectionless_frames"],
                "competing_frame_ratio": f"{competing_ratio:.3f}",
                "same_frame_close_competitor_frames": str(close_frames),
                "same_frame_class_competitor_frames": str(class_competition_frames),
                "max_same_frame_competitor_iou": f"{max_comp_iou:.3f}",
                "max_selected_step_dx_px": f"{max_step_dx:.1f}",
                "max_selected_step_area_ratio": f"{max_step_area:.3f}",
                "risk_level": risk,
                "machine_triage_label": label,
                "risk_reason_codes": ";".join(reason_codes),
                "recommended_human_focus": focus_text(reason_codes),
                "auto_merge_allowed": "no",
                "sar_ready": "no / blocked",
                "not_final_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "machine triage for human review only;not accepted edge;not identity truth",
            }
        )
    return out


def report_text(rows: list[dict[str, str]], triage_path: Path) -> str:
    counts = Counter(row["risk_level"] for row in rows)
    label_counts = Counter(row["machine_triage_label"] for row in rows)
    lines = [
        "# OTY2 YOLO26l WGV1.2 merge review queue triage",
        "",
        "Date: 2026-07-08",
        "",
        "## Conclusion",
        "",
        "This triage ranks the 11 review-only same-vehicle merge candidates for human inspection. It does not accept any merge and does not create final boxes, GT boxes, final/revised annotations, SAR-ready evidence, or tracker replay output.",
        "",
        f"- triage CSV: `{triage_path.as_posix()}`",
        f"- high risk: {counts.get('high', 0)}",
        f"- medium risk: {counts.get('medium', 0)}",
        f"- low risk: {counts.get('low', 0)}",
        "",
        "Machine labels:",
        "",
    ]
    for label, count in sorted(label_counts.items()):
        lines.append(f"- `{label}`: {count}")
    lines.extend(
        [
            "",
            "## Review Items",
            "",
            "| review_item_id | scene_id | frames | risk_level | label | key reasons | focus |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        frames = f"{row['frame_start']}-{row['frame_end']}"
        lines.append(
            "| {review_item_id} | {scene_id} | {frames} | {risk_level} | {machine_triage_label} | {risk_reason_codes} | {recommended_human_focus} |".format(
                **row,
                frames=frames,
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- `auto_merge_allowed=no` for every row.",
            "- `sar_ready=no / blocked` for every row.",
            "- These are review priorities, not same-vehicle truth.",
            "- Human review must inspect selected primary boxes together with same-frame competing candidates.",
        ]
    )
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> None:
    queue = read_csv(args.queue)
    bank = read_csv(args.bank)
    item_manifest = read_csv(args.item_manifest)
    rows = triage_rows(queue, bank, item_manifest)
    write_csv(args.triage, rows, FIELDS)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text(rows, args.triage), encoding="utf-8")
    print(f"wrote {args.triage} rows={len(rows)}")
    print(f"wrote {args.report}")
    print("risk counts:", dict(Counter(row["risk_level"] for row in rows)))
    print("label counts:", dict(Counter(row["machine_triage_label"] for row in rows)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--item-manifest", type=Path, default=DEFAULT_ITEM_MANIFEST)
    parser.add_argument("--triage", type=Path, default=DEFAULT_TRIAGE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    build(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
