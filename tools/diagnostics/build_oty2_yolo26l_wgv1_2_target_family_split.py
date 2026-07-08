#!/usr/bin/env python
"""Build diagnostic-only WGV1.2 target-family split candidate tables.

The script consumes existing YOLO26l diagnostic manifest and WGV1.1 fragment
tables. It does not run a detector, tracker replay, SAR pairing/support,
selector/ranking, or any final/revised annotation generation.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"

DEFAULT_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv"
DEFAULT_FRAGMENTS = SAMPLES_DIR / "oty2_yolo26l_optical_timeline_working_graph_v1_1_vehicle_fragments_20260708.csv"
DEFAULT_SEQUENCE_AUDIT = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_sequence_contrast_audit_20260708.csv"
DEFAULT_SAME_EDGES = SAMPLES_DIR / "oty2_yolo26l_optical_timeline_working_graph_v1_1_same_vehicle_edges_20260708.csv"

DEFAULT_TARGET_FAMILIES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv"
DEFAULT_SAFE_FRAGMENTS = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_sequence_safe_fragments_20260708.csv"
DEFAULT_SWITCH_EVENTS = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_switch_context_events_20260708.csv"
DEFAULT_MERGE_CANDIDATES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_candidates_20260708.csv"


@dataclass(frozen=True)
class DetectionRow:
    scene_id: str
    frame: int
    candidate_node_id: str
    source_detection_id: str
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    risk_tags: str
    display_status: str

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def width(self) -> float:
        return max(self.x2 - self.x1, 0.0)

    @property
    def height(self) -> float:
        return max(self.y2 - self.y1, 0.0)

    @property
    def area(self) -> float:
        return self.width * self.height


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_manifest(rows: list[dict[str, str]]) -> list[DetectionRow]:
    parsed: list[DetectionRow] = []
    for row in rows:
        parsed.append(
            DetectionRow(
                scene_id=row["scene_id"],
                frame=int(row["optical_frame_num"]),
                candidate_node_id=row["candidate_node_id"],
                source_detection_id=row["source_detection_id"],
                class_name=row["class_name"],
                confidence=float(row["confidence"]),
                x1=float(row["bbox_x1"]),
                y1=float(row["bbox_y1"]),
                x2=float(row["bbox_x2"]),
                y2=float(row["bbox_y2"]),
                risk_tags=row.get("risk_tags", ""),
                display_status=row.get("display_status", ""),
            )
        )
    return parsed


def y26_nodes(fragment: dict[str, str]) -> list[str]:
    return [
        value.strip()
        for value in fragment["source_candidate_node_ids"].split(";")
        if value.strip() and "_Y26N" in value
    ]


def x_bin(cx: float) -> str:
    if cx < 800.0 / 3.0:
        return "left"
    if cx < 1600.0 / 3.0:
        return "mid"
    return "right"


def ratio_pair(a: float, b: float) -> float:
    lo = max(min(a, b), 1e-6)
    hi = max(a, b)
    return hi / lo


def unique_detection_rows(rows: list[DetectionRow]) -> list[DetectionRow]:
    seen: set[str] = set()
    unique: list[DetectionRow] = []
    for row in sorted(rows, key=lambda r: (r.frame, r.source_detection_id, r.candidate_node_id)):
        if row.source_detection_id in seen:
            continue
        seen.add(row.source_detection_id)
        unique.append(row)
    return unique


def reuse_index(rows: list[DetectionRow]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        out[row.source_detection_id].add(row.candidate_node_id)
    return out


def frame_contrast_index(rows: list[DetectionRow]) -> dict[tuple[str, int], dict[str, object]]:
    grouped: dict[tuple[str, int], list[DetectionRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.scene_id, row.frame)].append(row)

    out: dict[tuple[str, int], dict[str, object]] = {}
    for key, frame_rows in grouped.items():
        source_ids = sorted({row.source_detection_id for row in frame_rows})
        node_ids = sorted({row.candidate_node_id for row in frame_rows})
        out[key] = {
            "distinct_source_detection_count": len(source_ids),
            "candidate_node_count": len(node_ids),
            "source_detection_ids": source_ids,
            "candidate_node_ids": node_ids,
            "has_multi_box_tag": any("multi_box_competition" in row.risk_tags for row in frame_rows),
        }
    return out


def break_reasons(prev: DetectionRow, cur: DetectionRow) -> list[str]:
    reasons: list[str] = []
    gap = cur.frame - prev.frame
    dx = abs(cur.cx - prev.cx) / max(gap, 1)
    norm_dx = abs(cur.cx - prev.cx) / max(prev.width, cur.width, 1.0)
    area_ratio = ratio_pair(prev.area, cur.area)
    if gap > 2:
        reasons.append("sequence_gap_over_2")
    if prev.class_name != cur.class_name:
        reasons.append("class_switch")
    if dx > 120.0:
        reasons.append("hard_center_offset_jump")
    if norm_dx > 0.65:
        reasons.append("hard_normalized_offset_jump")
    if area_ratio > 2.5:
        reasons.append("hard_area_ratio_jump")
    if x_bin(prev.cx) != x_bin(cur.cx) and dx > 60.0:
        reasons.append("spatial_bin_transition")
    return reasons


def segment_fragment(rows: list[DetectionRow]) -> tuple[list[list[DetectionRow]], list[dict[str, str]]]:
    if not rows:
        return [], []
    segments: list[list[DetectionRow]] = [[rows[0]]]
    events: list[dict[str, str]] = []
    for prev, cur in zip(rows, rows[1:]):
        reasons = break_reasons(prev, cur)
        if reasons:
            events.append(
                {
                    "event_frame_start": str(prev.frame),
                    "event_frame_end": str(cur.frame),
                    "from_source_detection_id": prev.source_detection_id,
                    "to_source_detection_id": cur.source_detection_id,
                    "from_candidate_node_id": prev.candidate_node_id,
                    "to_candidate_node_id": cur.candidate_node_id,
                    "event_type": classify_event(reasons),
                    "reason_codes": ";".join(reasons),
                    "dx_per_frame_px": f"{abs(cur.cx - prev.cx) / max(cur.frame - prev.frame, 1):.1f}",
                    "normalized_dx_by_box_width": f"{abs(cur.cx - prev.cx) / max(prev.width, cur.width, 1.0):.3f}",
                    "area_ratio": f"{ratio_pair(prev.area, cur.area):.3f}",
                }
            )
            segments.append([cur])
        else:
            segments[-1].append(cur)
    return segments, events


def classify_event(reasons: list[str]) -> str:
    if "class_switch" in reasons:
        return "class_switch_target_family_break"
    if "hard_center_offset_jump" in reasons or "hard_normalized_offset_jump" in reasons:
        return "spatial_jump_target_family_break"
    if "sequence_gap_over_2" in reasons:
        return "sequence_gap_review_event"
    if "source_detection_reused_by_nodes" in reasons:
        return "node_family_overlap_duplicate_detection"
    if "hard_area_ratio_jump" in reasons:
        return "size_jump_target_family_break"
    return "target_family_break"


def summarize_segment(
    segment: list[DetectionRow],
    scene_id: str,
    source_fragment_id: str,
    family_id: str,
    reuse: dict[str, set[str]],
    contrast: dict[tuple[str, int], dict[str, object]],
) -> dict[str, str]:
    frames = [row.frame for row in segment]
    classes = [row.class_name for row in segment]
    bins = [x_bin(row.cx) for row in segment]
    source_ids = [row.source_detection_id for row in segment]
    node_ids = sorted({row.candidate_node_id for row in segment})
    duplicate_count = sum(1 for row in segment if len(reuse[row.source_detection_id]) > 1)
    multicar_undercovered = []
    contrast_counts = []
    for row in segment:
        item = contrast.get((row.scene_id, row.frame), {})
        distinct_count = int(item.get("distinct_source_detection_count", 0))
        contrast_counts.append(distinct_count)
        if item.get("has_multi_box_tag") and distinct_count <= 1:
            multicar_undercovered.append(str(row.frame))

    status = "sequence_safe_candidate"
    review_required = "no"
    if len(segment) == 1:
        status = "single_frame_review_candidate"
        review_required = "yes"
    if duplicate_count:
        status = "review_required_duplicate_detection_family"
        review_required = "yes"
    if multicar_undercovered:
        status = "review_required_multicar_contrast_undercovered"
        review_required = "yes"

    cx_values = [row.cx for row in segment]
    area_values = [row.area for row in segment]
    max_dx = 0.0
    max_area_ratio = 1.0
    for prev, cur in zip(segment, segment[1:]):
        max_dx = max(max_dx, abs(cur.cx - prev.cx) / max(cur.frame - prev.frame, 1))
        max_area_ratio = max(max_area_ratio, ratio_pair(prev.area, cur.area))

    return {
        "target_family_id": family_id,
        "scene_id": scene_id,
        "source_fragment_id": source_fragment_id,
        "frame_start": str(min(frames)),
        "frame_end": str(max(frames)),
        "frame_count": str(len(set(frames))),
        "frame_sequence": " ".join(str(frame) for frame in frames),
        "candidate_node_ids": ";".join(node_ids),
        "source_detection_ids": ";".join(source_ids),
        "class_sequence": " ".join(classes),
        "x_bin_sequence": " ".join(bins),
        "center_x_start": f"{cx_values[0]:.1f}",
        "center_x_end": f"{cx_values[-1]:.1f}",
        "center_x_min": f"{min(cx_values):.1f}",
        "center_x_max": f"{max(cx_values):.1f}",
        "area_min": f"{min(area_values):.1f}",
        "area_max": f"{max(area_values):.1f}",
        "max_dx_per_frame_px": f"{max_dx:.1f}",
        "max_area_ratio": f"{max_area_ratio:.3f}",
        "same_frame_distinct_source_detection_min": str(min(contrast_counts) if contrast_counts else 0),
        "same_frame_distinct_source_detection_max": str(max(contrast_counts) if contrast_counts else 0),
        "duplicate_source_detection_count": str(duplicate_count),
        "contrast_undercoverage_frames": " ".join(multicar_undercovered),
        "diagnostic_status": status,
        "review_required": review_required,
        "not_final_box_flag": "yes",
        "not_SAR_ready_flag": "yes",
        "note": "diagnostic target-family candidate only;not identity truth",
    }


def sequence_safe_row(target_family: dict[str, str], sequence_fragment_id: str) -> dict[str, str]:
    status = target_family["diagnostic_status"]
    if status == "sequence_safe_candidate":
        merge_eligibility = "eligible_for_review_edge"
    elif "multicar_contrast_undercovered" in status:
        merge_eligibility = "needs_multicar_contrast_before_edge"
    else:
        merge_eligibility = "review_only_not_edge_ready"
    return {
        "sequence_fragment_id": sequence_fragment_id,
        "target_family_id": target_family["target_family_id"],
        "scene_id": target_family["scene_id"],
        "source_fragment_id": target_family["source_fragment_id"],
        "frame_start": target_family["frame_start"],
        "frame_end": target_family["frame_end"],
        "frame_count": target_family["frame_count"],
        "class_sequence": target_family["class_sequence"],
        "x_bin_sequence": target_family["x_bin_sequence"],
        "max_dx_per_frame_px": target_family["max_dx_per_frame_px"],
        "max_area_ratio": target_family["max_area_ratio"],
        "diagnostic_status": status,
        "merge_eligibility": merge_eligibility,
        "review_required": target_family["review_required"],
        "sar_ready": "no / blocked",
        "note": "sequence-safe fragment candidate only;not final track",
    }


def make_merge_candidates(target_families: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for tf in target_families:
        by_scene[tf["scene_id"]].append(tf)

    for scene_id, families in by_scene.items():
        families = sorted(families, key=lambda row: (int(row["frame_start"]), int(row["frame_end"]), row["target_family_id"]))
        idx = 1
        for prev, cur in zip(families, families[1:]):
            prev_end = int(prev["frame_end"])
            cur_start = int(cur["frame_start"])
            if cur_start <= prev_end:
                continue
            gap = cur_start - prev_end - 1
            if gap > 12:
                continue
            prev_cx = float(prev["center_x_end"])
            cur_cx = float(cur["center_x_start"])
            dx_per_gap = abs(cur_cx - prev_cx) / max(gap + 1, 1)
            prev_class = prev["class_sequence"].split()[-1] if prev["class_sequence"] else ""
            cur_class = cur["class_sequence"].split()[0] if cur["class_sequence"] else ""
            prev_bin = prev["x_bin_sequence"].split()[-1] if prev["x_bin_sequence"] else ""
            cur_bin = cur["x_bin_sequence"].split()[0] if cur["x_bin_sequence"] else ""

            reasons: list[str] = []
            strength = "review_only"
            if prev_class != cur_class:
                strength = "blocked"
                reasons.append("class_mismatch")
            if dx_per_gap > 120.0:
                strength = "blocked"
                reasons.append("endpoint_center_offset_too_large")
            elif dx_per_gap > 60.0:
                reasons.append("endpoint_center_offset_review")
            if prev_bin != cur_bin:
                reasons.append("endpoint_spatial_bin_change")
            if prev["review_required"] == "yes" or cur["review_required"] == "yes":
                reasons.append("endpoint_review_required")
            if not reasons:
                strength = "weak_candidate"
                reasons.append("short_gap_same_class_plausible_endpoint_motion")

            rows.append(
                {
                    "merge_candidate_id": f"{scene_id}_WGV12M{idx:03d}",
                    "scene_id": scene_id,
                    "from_target_family_id": prev["target_family_id"],
                    "to_target_family_id": cur["target_family_id"],
                    "from_frame_end": prev["frame_end"],
                    "to_frame_start": cur["frame_start"],
                    "gap_frame_count": str(gap),
                    "from_class": prev_class,
                    "to_class": cur_class,
                    "from_x_bin": prev_bin,
                    "to_x_bin": cur_bin,
                    "endpoint_dx_per_gap_frame_px": f"{dx_per_gap:.1f}",
                    "candidate_strength": strength,
                    "reason_codes": ";".join(reasons),
                    "review_required": "yes",
                    "sar_ready": "no / blocked",
                    "note": "diagnostic merge candidate only;not same-vehicle truth",
                }
            )
            idx += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENTS)
    parser.add_argument("--sequence-audit", type=Path, default=DEFAULT_SEQUENCE_AUDIT)
    parser.add_argument("--same-edges", type=Path, default=DEFAULT_SAME_EDGES)
    parser.add_argument("--target-families", type=Path, default=DEFAULT_TARGET_FAMILIES)
    parser.add_argument("--safe-fragments", type=Path, default=DEFAULT_SAFE_FRAGMENTS)
    parser.add_argument("--switch-events", type=Path, default=DEFAULT_SWITCH_EVENTS)
    parser.add_argument("--merge-candidates", type=Path, default=DEFAULT_MERGE_CANDIDATES)
    args = parser.parse_args()

    manifest_rows = parse_manifest(read_csv(args.manifest))
    fragments = read_csv(args.fragments)
    sequence_audit = {row["fragment_id"]: row for row in read_csv(args.sequence_audit)}
    reuse = reuse_index(manifest_rows)
    contrast = frame_contrast_index(manifest_rows)

    target_rows: list[dict[str, str]] = []
    safe_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []
    family_counter: dict[str, int] = defaultdict(int)
    sequence_counter: dict[str, int] = defaultdict(int)
    event_counter: dict[str, int] = defaultdict(int)

    for fragment in fragments:
        scene_id = fragment["scene_id"]
        fragment_id = fragment["fragment_id"]
        start = int(fragment["frame_start"])
        end = int(fragment["frame_end"])
        nodes = set(y26_nodes(fragment))
        selected_rows = [
            row
            for row in manifest_rows
            if row.scene_id == scene_id
            and start <= row.frame <= end
            and row.candidate_node_id in nodes
        ]
        unique_rows = unique_detection_rows(selected_rows)

        recommendation = sequence_audit.get(fragment_id, {}).get("v1_2_sequence_contrast_recommendation", "")
        if recommendation == "route_to_switch_or_context_event" or fragment["accepted_status"] in {"blocked", "forbidden"}:
            event_counter[scene_id] += 1
            event_rows.append(
                {
                    "event_id": f"{scene_id}_WGV12E{event_counter[scene_id]:03d}",
                    "scene_id": scene_id,
                    "source_fragment_id": fragment_id,
                    "frame_start": str(start),
                    "frame_end": str(end),
                    "event_type": "switch_or_context_event",
                    "reason_codes": sequence_audit.get(fragment_id, {}).get("sequence_guardrail_flags", "not_vehicle_identity_input"),
                    "from_source_detection_id": "",
                    "to_source_detection_id": "",
                    "from_candidate_node_id": "",
                    "to_candidate_node_id": "",
                    "dx_per_frame_px": "",
                    "normalized_dx_by_box_width": "",
                    "area_ratio": "",
                    "review_required": "yes",
                    "sar_ready": "no / blocked",
                    "note": "fragment routed out of vehicle identity review",
                }
            )
            continue

        segments, break_events = segment_fragment(unique_rows)
        for event in break_events:
            event_counter[scene_id] += 1
            event_rows.append(
                {
                    "event_id": f"{scene_id}_WGV12E{event_counter[scene_id]:03d}",
                    "scene_id": scene_id,
                    "source_fragment_id": fragment_id,
                    "frame_start": event["event_frame_start"],
                    "frame_end": event["event_frame_end"],
                    "event_type": event["event_type"],
                    "reason_codes": event["reason_codes"],
                    "from_source_detection_id": event["from_source_detection_id"],
                    "to_source_detection_id": event["to_source_detection_id"],
                    "from_candidate_node_id": event["from_candidate_node_id"],
                    "to_candidate_node_id": event["to_candidate_node_id"],
                    "dx_per_frame_px": event["dx_per_frame_px"],
                    "normalized_dx_by_box_width": event["normalized_dx_by_box_width"],
                    "area_ratio": event["area_ratio"],
                    "review_required": "yes",
                    "sar_ready": "no / blocked",
                    "note": "target-family split event;diagnostic only",
                }
            )

        for segment in segments:
            if not segment:
                continue
            family_counter[scene_id] += 1
            target_family_id = f"{scene_id}_WGV12TF{family_counter[scene_id]:03d}"
            target_row = summarize_segment(segment, scene_id, fragment_id, target_family_id, reuse, contrast)
            target_rows.append(target_row)
            sequence_counter[scene_id] += 1
            safe_rows.append(sequence_safe_row(target_row, f"{scene_id}_WGV12SF{sequence_counter[scene_id]:03d}"))

    merge_rows = make_merge_candidates(target_rows)

    write_csv(args.target_families, target_rows, list(target_rows[0].keys()) if target_rows else [])
    write_csv(args.safe_fragments, safe_rows, list(safe_rows[0].keys()) if safe_rows else [])
    write_csv(args.switch_events, event_rows, list(event_rows[0].keys()) if event_rows else [])
    write_csv(args.merge_candidates, merge_rows, list(merge_rows[0].keys()) if merge_rows else [])

    print(f"wrote {args.target_families} rows={len(target_rows)}")
    print(f"wrote {args.safe_fragments} rows={len(safe_rows)}")
    print(f"wrote {args.switch_events} rows={len(event_rows)}")
    print(f"wrote {args.merge_candidates} rows={len(merge_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
