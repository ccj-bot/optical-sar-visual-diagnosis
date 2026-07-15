#!/usr/bin/env python3
from __future__ import annotations

"""Read-only audit of S0-M S1-L preselection semantics and temporal context.

Existing S0/S0-M formal outputs are inputs only.  This script adds S0-MV
manifests and temporary visualizations; it does not extract SAR structures,
refit mapping, alter identity/synchronization, or generate annotations.
"""

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
DATA_ROOT = Path(r"D:\profile\research\data")
OUTPUT_ROOT = WORKSPACE_ROOT / "output" / "oty2_s0mv_s1l_input_semantics_visualization_20260715"
TIMELINE_DIR = OUTPUT_ROOT / "timelines"
PREVIEW_DIR = OUTPUT_ROOT / "preselection_context"
SEGMENT_DIR = OUTPUT_ROOT / "segments"
OVERVIEW_DIR = OUTPUT_ROOT / "review_overviews"

QUALITY_PATH = MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv"
PREVIOUS_S1L_PATH = MANIFEST_DIR / "oty2_s0m_s1l_frame_eligibility_ledger.csv"
GOLDEN_PATH = MANIFEST_DIR / "oty2_s0_sar_golden_vehicle_threads.csv"
STATE_PATH = MANIFEST_DIR / "oty2_p1e_canonical_vehicle_frame_states.csv"

PRESELECTION_AUDIT_PATH = MANIFEST_DIR / "oty2_s0mv_s1l_preselection_semantic_audit.csv"
ALL_GT_PATH = MANIFEST_DIR / "oty2_s0mv_all_gt_s1l_eligibility.csv"
SEGMENTS_PATH = MANIFEST_DIR / "oty2_s0mv_s1l_continuous_segments.csv"
VISUAL_MANIFEST_PATH = MANIFEST_DIR / "oty2_s0mv_visualization_manifest.csv"

SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
SAR_FRAME_COUNT = 766
SEGMENT_MAX_GT_GAP = 5
MIN_TEMPORAL_ELIGIBLE_FRAMES = 3

QUALITY_PRIORITY = {
    "gold": 5,
    "usable": 4,
    "diagnostic_only": 3,
    "identity_or_geometry_conflict": 2,
    "exclude_from_structure_discovery": 1,
}
QUALITY_COLORS = {
    "gold": (0, 215, 255),
    "usable": (70, 200, 70),
    "diagnostic_only": (0, 165, 255),
    "identity_or_geometry_conflict": (50, 50, 220),
    "exclude_from_structure_discovery": (90, 90, 90),
}
VISIBILITY_COLORS = {
    "full_visible": (60, 210, 60),
    "partial_visible": (0, 190, 255),
    "fully_occluded": (150, 80, 170),
    "outside": (80, 80, 80),
    "visible_but_unboxed": (255, 180, 30),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_bbox(value: str) -> tuple[float, float, float, float, float]:
    parts = [float(item.strip()) for item in value.strip().strip("[]").split(",")]
    if len(parts) != 5:
        raise ValueError(f"Invalid rotated bbox: {value}")
    return tuple(parts)  # type: ignore[return-value]


def count_text(values: Iterable[str]) -> str:
    counts = Counter(str(value or "unknown") for value in values)
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def sar_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def optical_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_frames" / f"{frame:06d}.png"


def sanitize(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace("\\", "_")


def put_text(image: np.ndarray, text: str, origin: tuple[int, int], scale: float = 0.5, color: tuple[int, int, int] = (240, 240, 240), thickness: int = 1) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def state_index() -> dict[tuple[str, str, int], dict[str, str]]:
    return {
        (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row
        for row in read_csv(STATE_PATH)
    }


def golden_index() -> dict[tuple[str, str], dict[str, str]]:
    return {(row["scene"], row["canonical_vehicle_id"]): row for row in read_csv(GOLDEN_PATH)}


def previous_preselection() -> tuple[set[str], dict[str, dict[str, str]]]:
    rows = read_csv(PREVIOUS_S1L_PATH)
    selected = {row["sar_gt_id"] for row in rows if row["selected_for_future_s1l"] == "true"}
    return selected, {row["sar_gt_id"]: row for row in rows}


def enrich_rows() -> tuple[list[dict[str, Any]], set[str]]:
    states = state_index()
    golden = golden_index()
    preselected, previous_by_id = previous_preselection()
    rows: list[dict[str, Any]] = []
    for source in read_csv(QUALITY_PATH):
        row: dict[str, Any] = dict(source)
        scene = row["scene"]
        canonical = row["canonical_vehicle_id"]
        sar_frame = int(row["sar_frame_index"])
        optical_frame = int(row.get("optical_frame_index") or -1)
        state = states.get((scene, canonical, optical_frame), {})
        thread = golden.get((scene, canonical), {})
        mapping_eligible = row.get("mapping_anchor_eligibility", "") in {
            "calibration_gold", "calibration_usable", "heldout_gold", "heldout_usable"
        }
        image = cv2.imread(str(sar_path(scene, sar_frame)), cv2.IMREAD_GRAYSCALE)
        sar_readable = image is not None
        reasons: list[str] = []
        if not canonical:
            reasons.append("canonical_vehicle_not_linked")
        if row["gt_quality_status"] not in {"gold", "usable"}:
            reasons.append(f"gt_quality_{row['gt_quality_status']}")
        if row.get("gt_inside_valid_mask") != "true":
            reasons.append("gt_not_inside_imaging_valid_mask")
        if row["identity_link_status"] in {"", "nonvehicle_optical_source_conflict"} or row["gt_quality_status"] == "identity_or_geometry_conflict":
            reasons.append("identity_or_geometry_conflict")
        if row["gt_quality_status"] == "exclude_from_structure_discovery":
            reasons.append("excluded_by_s0_gt_quality")
        if not sar_readable:
            reasons.append("sar_image_unreadable")
        if canonical and row["benchmark_role"] not in {"development", "heldout_validation", "diagnostic_only"}:
            reasons.append("vehicle_thread_role_unclear")
        structure_eligible = not reasons
        row.update(
            {
                "sar_frame_index_int": sar_frame,
                "optical_frame_index_int": optical_frame,
                "sar_image_readable": sar_readable,
                "mapping_anchor_eligible_bool": mapping_eligible,
                "s1l_structure_frame_eligible_bool": structure_eligible,
                "s1l_temporal_eligible_bool": False,
                "structure_exclusion_reason": ";".join(dict.fromkeys(reasons)),
                "belongs_to_preselected_12_bool": row["sar_gt_id"] in preselected,
                "optical_visibility_state_resolved": row.get("optical_visibility_state") or state.get("visibility_state", "unknown"),
                "optical_vehicle_full_visibility_resolved": row.get("optical_vehicle_full_visibility") or state.get("is_full_vehicle_visible", "false"),
                "vehicle_research_role": thread.get("recommended_research_role", "unresolved"),
                "previous_s1l_research_role": previous_by_id.get(row["sar_gt_id"], {}).get("s1l_research_role", ""),
                "segment_id": "",
                "temporal_exclusion_reason": "pending_segment_reconstruction",
            }
        )
        rows.append(row)
    return rows, preselected


def primary_frame_rows(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["canonical_vehicle_id"]:
            grouped[(row["scene"], row["canonical_vehicle_id"], row["sar_frame_index_int"])].append(row)
    result: dict[tuple[str, str, int], dict[str, Any]] = {}
    for key, candidates in grouped.items():
        result[key] = max(
            candidates,
            key=lambda item: (
                int(item["s1l_structure_frame_eligible_bool"]),
                QUALITY_PRIORITY.get(item["gt_quality_status"], 0),
                item["identity_link_confidence"],
            ),
        )
    return result


def rebuild_segments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_vehicle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["canonical_vehicle_id"]:
            by_vehicle[(row["scene"], row["canonical_vehicle_id"])].append(row)
    segments: list[dict[str, Any]] = []
    row_segment: dict[str, str] = {}
    eligible_segment_ids: set[str] = set()
    for (scene, canonical), vehicle_rows in sorted(by_vehicle.items()):
        by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in vehicle_rows:
            by_frame[row["sar_frame_index_int"]].append(row)
        frames = sorted(by_frame)
        frame_groups: list[list[int]] = []
        current: list[int] = []
        for frame in frames:
            if current and frame - current[-1] > SEGMENT_MAX_GT_GAP:
                frame_groups.append(current)
                current = []
            current.append(frame)
        if current:
            frame_groups.append(current)
        for index, segment_frames in enumerate(frame_groups, start=1):
            segment_id = f"S0MV-{scene}-{sanitize(canonical.split(':')[-1])}-SEG{index:02d}"
            segment_rows = [row for frame in segment_frames for row in by_frame[frame]]
            eligible_frames = sorted({row["sar_frame_index_int"] for row in segment_rows if row["s1l_structure_frame_eligible_bool"]})
            start, end = segment_frames[0], segment_frames[-1]
            gaps = [b - a for a, b in zip(segment_frames, segment_frames[1:])]
            conflict_count = sum(
                row["gt_quality_status"] == "identity_or_geometry_conflict" or row["identity_link_status"] == "nonvehicle_optical_source_conflict"
                for row in segment_rows
            )
            coverage = len(eligible_frames) / len(segment_frames) if segment_frames else 0.0
            role = segment_rows[0]["benchmark_role"]
            segment_eligible = (
                role in {"development", "heldout_validation"}
                and len(eligible_frames) >= MIN_TEMPORAL_ELIGIBLE_FRAMES
                and conflict_count == 0
                and coverage >= 0.5
                and max(gaps, default=0) <= SEGMENT_MAX_GT_GAP
            )
            reasons: list[str] = []
            if role not in {"development", "heldout_validation"}:
                reasons.append("benchmark_role_not_development_or_heldout")
            if len(eligible_frames) < MIN_TEMPORAL_ELIGIBLE_FRAMES:
                reasons.append("fewer_than_3_structure_eligible_gt_frames")
            if conflict_count:
                reasons.append("identity_or_geometry_conflict_inside_segment")
            if coverage < 0.5:
                reasons.append("structure_eligible_coverage_below_0p5")
            if max(gaps, default=0) > SEGMENT_MAX_GT_GAP:
                reasons.append("maximum_internal_gap_above_5")
            mapping_count = sum(any(item["mapping_anchor_eligible_bool"] for item in by_frame[frame]) for frame in segment_frames)
            preview_count = sum(any(item["belongs_to_preselected_12_bool"] for item in by_frame[frame]) for frame in segment_frames)
            if segment_eligible:
                usage = "s1l_development_sequence" if role == "development" else "s1l_heldout_sequence"
                eligible_segment_ids.add(segment_id)
            elif len(eligible_frames) in {1, 2}:
                usage = "single_frame_coordinate_check"
            elif mapping_count and not eligible_frames:
                usage = "mapping_only"
            elif role == "diagnostic_only" or eligible_frames:
                usage = "diagnostic_only"
            else:
                usage = "exclude"
            for row in segment_rows:
                row_segment[row["sar_gt_id"]] = segment_id
            segments.append(
                {
                    "segment_id": segment_id,
                    "scene": scene,
                    "canonical_vehicle_id": canonical,
                    "benchmark_role": role,
                    "vehicle_research_role": segment_rows[0]["vehicle_research_role"],
                    "sar_frame_start": start,
                    "sar_frame_end": end,
                    "frame_span": end - start + 1,
                    "gt_frame_count": len(segment_frames),
                    "gt_row_count": len(segment_rows),
                    "eligible_frame_count": len(eligible_frames),
                    "missing_frame_count": (end - start + 1) - len(segment_frames),
                    "maximum_internal_gap": max(gaps, default=0),
                    "gt_quality_distribution": count_text(row["gt_quality_status"] for row in segment_rows),
                    "optical_visibility_distribution": count_text(row["optical_visibility_state_resolved"] for row in segment_rows),
                    "pose_distribution": count_text(row.get("optical_pose_group", "pose_unstable") for row in segment_rows),
                    "multi_vehicle_competition_count": sum(parse_bool(row["multi_vehicle_competition"]) for row in segment_rows),
                    "mapping_anchor_count": mapping_count,
                    "preselected_12_count": preview_count,
                    "structure_frame_coverage": f"{coverage:.9f}",
                    "segment_eligibility": "true" if segment_eligible else "false",
                    "exclusion_reason": ";".join(reasons),
                    "recommended_usage": usage,
                    "segmentation_rule": "split_when_consecutive_unique_gt_frame_gap_gt_5",
                }
            )
    for row in rows:
        segment_id = row_segment.get(row["sar_gt_id"], "")
        row["segment_id"] = segment_id
        temporal = row["s1l_structure_frame_eligible_bool"] and segment_id in eligible_segment_ids
        row["s1l_temporal_eligible_bool"] = temporal
        row["temporal_exclusion_reason"] = "" if temporal else (
            "structure_frame_not_eligible" if not row["s1l_structure_frame_eligible_bool"] else "segment_not_temporally_eligible"
        )
    return segments


def all_gt_manifest(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "scene": row["scene"],
                "canonical_vehicle_id": row["canonical_vehicle_id"],
                "benchmark_role": row["benchmark_role"],
                "vehicle_research_role": row["vehicle_research_role"],
                "sar_frame_index": row["sar_frame_index_int"],
                "optical_frame_index": row["optical_frame_index_int"],
                "sar_gt_id": row["sar_gt_id"],
                "gt_quality_status": row["gt_quality_status"],
                "gt_inside_imaging_valid_mask": row["gt_inside_valid_mask"],
                "identity_link_status": row["identity_link_status"],
                "multi_vehicle_competition": row["multi_vehicle_competition"],
                "optical_visibility_state": row["optical_visibility_state_resolved"],
                "optical_vehicle_full_visibility": row["optical_vehicle_full_visibility_resolved"],
                "sar_image_readable": bool_text(row["sar_image_readable"]),
                "mapping_anchor_eligible": bool_text(row["mapping_anchor_eligible_bool"]),
                "s1l_structure_frame_eligible": bool_text(row["s1l_structure_frame_eligible_bool"]),
                "s1l_temporal_eligible": bool_text(row["s1l_temporal_eligible_bool"]),
                "segment_id": row["segment_id"],
                "exclusion_reason": row["structure_exclusion_reason"],
                "temporal_exclusion_reason": row["temporal_exclusion_reason"],
                "belongs_to_preselected_12": bool_text(row["belongs_to_preselected_12_bool"]),
                "notes": "optical full visibility and mapping eligibility are descriptive, not S1-L structure hard gates",
            }
        )
    return output


def preselection_semantic_audit(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = sorted(
        (row for row in rows if row["belongs_to_preselected_12_bool"]),
        key=lambda item: (item["scene"], item["canonical_vehicle_id"], item["sar_frame_index_int"]),
    )
    output: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        output.append(
            {
                "record_id": f"S0MV-PREVIEW-{index:03d}",
                "source_file": "manifests/oty2/oty2_s0m_s1l_frame_eligibility_ledger.csv",
                "source_script": "tools/diagnostics/run_oty2_s0m_mask_anchor_pose_mapping_audit.py",
                "source_function": "select_s1l_candidates",
                "selection_rule": "first restrict to mapping-anchor-eligible rows, then choose theta/radius ordered representatives per vehicle",
                "selection_limit": "up_to_4_per_mapping_eligible_vehicle",
                "sampling_rule": "sort(center_theta_deg,center_radius_px); choose indices 0,round((n-1)/3),round(2*(n-1)/3),n-1",
                "scene": row["scene"],
                "canonical_vehicle_id": row["canonical_vehicle_id"],
                "sar_frame_index": row["sar_frame_index_int"],
                "gt_quality_status": row["gt_quality_status"],
                "benchmark_role": row["benchmark_role"],
                "mapping_anchor_eligible": bool_text(row["mapping_anchor_eligible_bool"]),
                "s1l_structure_eligible": bool_text(row["s1l_structure_frame_eligible_bool"]),
                "selected_as_preview": "true",
                "selected_as_pilot": "false",
                "selected_as_formal_input": "false",
                "semantic_interpretation": "representative preview, not the full eligible set",
                "notes": "deterministic quantile-like sampling; not head(12), [:12], random sampling, or a continuous-thread definition",
            }
        )
    return output


def draw_rotated_boxes(image: np.ndarray, rows: Sequence[Mapping[str, Any]], color: tuple[int, int, int] = (0, 0, 255), thickness: int = 3) -> None:
    for row in rows:
        try:
            cx, cy, width, height, heading = parse_bbox(str(row["bbox"]))
        except (KeyError, ValueError):
            continue
        points = np.rint(cv2.boxPoints(((cx, cy), (width, height), heading))).astype(np.int32)
        cv2.polylines(image, [points], True, color, thickness, cv2.LINE_AA)


def crop_context(image: np.ndarray, bboxes: Sequence[tuple[float, float, float, float, float]], margin: float = 1.0) -> np.ndarray:
    if not bboxes:
        return cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
    points = np.concatenate([cv2.boxPoints(((b[0], b[1]), (b[2], b[3]), b[4])) for b in bboxes], axis=0)
    x1, y1 = float(points[:, 0].min()), float(points[:, 1].min())
    x2, y2 = float(points[:, 0].max()), float(points[:, 1].max())
    width, height = max(16.0, x2 - x1), max(16.0, y2 - y1)
    x1 = max(0, int(math.floor(x1 - margin * width)))
    y1 = max(0, int(math.floor(y1 - margin * height)))
    x2 = min(image.shape[1], int(math.ceil(x2 + margin * width)))
    y2 = min(image.shape[0], int(math.ceil(y2 + margin * height)))
    return image[y1:y2, x1:x2].copy()


def render_timelines(rows: Sequence[dict[str, Any]], segments: Sequence[dict[str, Any]], review_status: str) -> list[dict[str, Any]]:
    segment_by_id = {row["segment_id"]: row for row in segments}
    by_vehicle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["canonical_vehicle_id"]:
            by_vehicle[(row["scene"], row["canonical_vehicle_id"])].append(row)
    manifest: list[dict[str, Any]] = []
    lane_names = ["GT quality", "valid mask", "optical visibility", "mapping anchor", "S1-L structure", "S1-L temporal", "12 preview"]
    for (scene, canonical), vehicle_rows in sorted(by_vehicle.items()):
        canvas = np.full((520, 1800, 3), 245, dtype=np.uint8)
        left, right = 230, 1740
        put_text(canvas, f"{scene}  {canonical}  role={vehicle_rows[0]['benchmark_role']}  vehicle_role={vehicle_rows[0]['vehicle_research_role']}", (25, 35), 0.72, (20, 20, 20), 2)
        for tick in range(0, SAR_FRAME_COUNT, 50):
            x = left + int((right - left) * tick / (SAR_FRAME_COUNT - 1))
            cv2.line(canvas, (x, 60), (x, 455), (210, 210, 210), 1)
            put_text(canvas, str(tick), (x - 10, 480), 0.38, (50, 50, 50))
        for lane_index, lane in enumerate(lane_names):
            y = 85 + lane_index * 52
            put_text(canvas, lane, (20, y + 18), 0.48, (30, 30, 30))
            cv2.rectangle(canvas, (left, y), (right, y + 28), (225, 225, 225), -1)
        for row in vehicle_rows:
            x = left + int((right - left) * row["sar_frame_index_int"] / (SAR_FRAME_COUNT - 1))
            width = 4
            quality_color = QUALITY_COLORS.get(row["gt_quality_status"], (120, 120, 120))
            cv2.rectangle(canvas, (x - width, 85), (x + width, 113), quality_color, -1)
            mask_color = (60, 190, 60) if row["gt_inside_valid_mask"] == "true" else (30, 30, 220)
            cv2.rectangle(canvas, (x - width, 137), (x + width, 165), mask_color, -1)
            visibility_color = VISIBILITY_COLORS.get(row["optical_visibility_state_resolved"], (150, 150, 150))
            cv2.rectangle(canvas, (x - width, 189), (x + width, 217), visibility_color, -1)
            if row["mapping_anchor_eligible_bool"]:
                cv2.rectangle(canvas, (x - width, 241), (x + width, 269), (255, 120, 40), -1)
            if row["s1l_structure_frame_eligible_bool"]:
                cv2.rectangle(canvas, (x - width, 293), (x + width, 321), (0, 170, 0), -1)
            if row["s1l_temporal_eligible_bool"]:
                cv2.rectangle(canvas, (x - width, 345), (x + width, 373), (180, 80, 20), -1)
            if row["belongs_to_preselected_12_bool"]:
                cv2.circle(canvas, (x, 411), 7, (220, 0, 220), -1)
        eligible_segments = sorted({row["segment_id"] for row in vehicle_rows if row["s1l_temporal_eligible_bool"]})
        put_text(canvas, f"temporal segments: {','.join(eligible_segments) if eligible_segments else 'none'}", (25, 505), 0.40, (40, 40, 40))
        path = TIMELINE_DIR / f"{scene}_{sanitize(canonical)}_timeline.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), canvas)
        manifest.append({
            "artifact_type": "vehicle_timeline", "scene": scene, "canonical_vehicle_id": canonical,
            "segment_id": "", "sar_frame_index": "", "artifact_path": str(path),
            "artifact_count": 1, "review_status": review_status,
            "notes": f"all GT rows for vehicle; eligible segments={len(eligible_segments)}",
        })
    return manifest


def frame_rows_index(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    result: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[(row["scene"], row["sar_frame_index_int"])].append(row)
    return result


def optical_state_box(state: Mapping[str, str]) -> tuple[int, int, int, int] | None:
    values = [parse_float(state.get(key)) for key in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2")]
    if not all(math.isfinite(value) for value in values):
        return None
    return tuple(int(round(value)) for value in values)  # type: ignore[return-value]


def render_preview_contexts(rows: Sequence[dict[str, Any]], segments: Sequence[dict[str, Any]], review_status: str) -> list[dict[str, Any]]:
    states = state_index()
    by_frame = frame_rows_index(rows)
    segment_map = {row["segment_id"]: row for row in segments}
    selected = sorted((row for row in rows if row["belongs_to_preselected_12_bool"]), key=lambda item: (item["scene"], item["sar_frame_index_int"], item["canonical_vehicle_id"]))
    manifest: list[dict[str, Any]] = []
    for preview_index, row in enumerate(selected, start=1):
        scene, frame, canonical = row["scene"], row["sar_frame_index_int"], row["canonical_vehicle_id"]
        canvas = np.full((1180, 1900, 3), 24, dtype=np.uint8)
        header = f"S0MV preview {preview_index:02d}/12  {scene}  {canonical}  SAR={frame}  optical={row['optical_frame_index_int']}"
        put_text(canvas, header, (25, 35), 0.78, (255, 255, 255), 2)
        put_text(canvas, "representative preview, not the full eligible set", (25, 70), 0.72, (0, 215, 255), 2)

        current = cv2.imread(str(sar_path(scene, frame)), cv2.IMREAD_COLOR)
        if current is None:
            raise FileNotFoundError(sar_path(scene, frame))
        target_rows = [item for item in by_frame[(scene, frame)] if item["canonical_vehicle_id"] == canonical]
        draw_rotated_boxes(current, target_rows, (0, 0, 255), 5)
        full = cv2.resize(current, (900, 520), interpolation=cv2.INTER_AREA)
        canvas[100:620, 20:920] = full
        put_text(canvas, "current raw SAR grayscale + GT", (35, 125), 0.52, (255, 255, 255))

        optical = cv2.imread(str(optical_path(scene, row["optical_frame_index_int"])), cv2.IMREAD_COLOR)
        if optical is None:
            raise FileNotFoundError(optical_path(scene, row["optical_frame_index_int"]))
        state = states.get((scene, canonical, row["optical_frame_index_int"]), {})
        box = optical_state_box(state)
        if box:
            cv2.rectangle(optical, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 3)
        optical_resized = cv2.resize(optical, (600, 450), interpolation=cv2.INTER_AREA)
        canvas[100:550, 950:1550] = optical_resized
        put_text(canvas, "corresponding optical reference", (965, 125), 0.52, (255, 255, 255))

        segment_rows = [item for item in rows if item["segment_id"] == row["segment_id"] and item["s1l_structure_frame_eligible_bool"]]
        previous_count = len({item["sar_frame_index_int"] for item in segment_rows if item["sar_frame_index_int"] < frame})
        following_count = len({item["sar_frame_index_int"] for item in segment_rows if item["sar_frame_index_int"] > frame})
        meta = [
            f"quality={row['gt_quality_status']}  mapping_anchor={bool_text(row['mapping_anchor_eligible_bool'])}",
            f"S1L_structure={bool_text(row['s1l_structure_frame_eligible_bool'])}  S1L_temporal={bool_text(row['s1l_temporal_eligible_bool'])}",
            f"segment={row['segment_id']}  eligible_before={previous_count}  eligible_after={following_count}",
            "selection reason: up to four theta/radius ordered representatives per mapping-eligible vehicle",
        ]
        for line_index, line in enumerate(meta):
            put_text(canvas, line, (950, 595 + line_index * 30), 0.48, (240, 240, 240))

        thumb_w, thumb_h = 250, 125
        for offset, context_frame in enumerate(range(max(0, frame - 10), min(SAR_FRAME_COUNT - 1, frame + 10) + 1)):
            image = cv2.imread(str(sar_path(scene, context_frame)), cv2.IMREAD_COLOR)
            if image is None:
                raise FileNotFoundError(sar_path(scene, context_frame))
            frame_target_rows = [item for item in by_frame.get((scene, context_frame), []) if item["canonical_vehicle_id"] == canonical]
            if frame_target_rows:
                draw_rotated_boxes(image, frame_target_rows, (0, 0, 255), 4)
                bboxes = [parse_bbox(item["bbox"]) for item in frame_target_rows]
                crop = crop_context(image, bboxes, margin=1.0)
            else:
                crop = cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
            tile = cv2.resize(crop, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
            border = (0, 255, 255) if context_frame == frame else (90, 90, 90)
            cv2.rectangle(tile, (0, 0), (thumb_w - 1, thumb_h - 1), border, 3 if context_frame == frame else 1)
            put_text(tile, f"SAR {context_frame} {'GT' if frame_target_rows else 'no GT'}", (6, 18), 0.42, (255, 255, 255))
            row_i, col_i = divmod(offset, 7)
            x, y = 20 + col_i * 265, 750 + row_i * 135
            canvas[y:y + thumb_h, x:x + thumb_w] = tile
        path = PREVIEW_DIR / f"preview_{preview_index:02d}_{scene}_{sanitize(canonical)}_sar_{frame:06d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), canvas)
        manifest.append({
            "artifact_type": "preselected_12_context", "scene": scene, "canonical_vehicle_id": canonical,
            "segment_id": row["segment_id"], "sar_frame_index": frame, "artifact_path": str(path),
            "artifact_count": 1, "review_status": review_status,
            "notes": "representative preview, not the full eligible set; +/-10 SAR context and optical reference",
        })
    return manifest


def render_segment_contacts(rows: Sequence[dict[str, Any]], segments: Sequence[dict[str, Any]], review_status: str) -> list[dict[str, Any]]:
    by_segment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["segment_id"]:
            by_segment[row["segment_id"]].append(row)
    manifest: list[dict[str, Any]] = []
    for segment in segments:
        if segment["segment_eligibility"] != "true":
            continue
        segment_rows = by_segment[segment["segment_id"]]
        by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in segment_rows:
            by_frame[row["sar_frame_index_int"]].append(row)
        frames = list(range(int(segment["sar_frame_start"]), int(segment["sar_frame_end"]) + 1))
        cols, tile_w, tile_h = 6, 290, 190
        page_capacity = 30
        page_paths: list[Path] = []
        for page_index in range(math.ceil(len(frames) / page_capacity)):
            page_frames = frames[page_index * page_capacity:(page_index + 1) * page_capacity]
            rows_count = math.ceil(len(page_frames) / cols)
            canvas = np.full((100 + rows_count * tile_h, cols * tile_w, 3), 22, dtype=np.uint8)
            header = (
                f"{segment['segment_id']}  {segment['scene']} {segment['canonical_vehicle_id']}  "
                f"frames {segment['sar_frame_start']}-{segment['sar_frame_end']}  page {page_index + 1}"
            )
            put_text(canvas, header, (15, 30), 0.62, (255, 255, 255), 2)
            put_text(canvas, "raw SAR grayscale only; red=GT; yellow=no-GT gap marker; no structure elements extracted", (15, 62), 0.50, (0, 215, 255))
            for tile_index, frame in enumerate(page_frames):
                image = cv2.imread(str(sar_path(segment["scene"], frame)), cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(sar_path(segment["scene"], frame))
                current_rows = by_frame.get(frame, [])
                if current_rows:
                    draw_rotated_boxes(image, current_rows, (0, 0, 255), 4)
                    bboxes = [parse_bbox(item["bbox"]) for item in current_rows]
                    crop = crop_context(image, bboxes, margin=1.2)
                    status = "/".join(sorted({item["gt_quality_status"] for item in current_rows}))
                    pose = "/".join(sorted({item.get("optical_pose_group", "pose_unstable") for item in current_rows}))
                    label_color = (255, 255, 255)
                else:
                    crop = cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
                    status = "no GT between anchors"
                    pose = "n/a"
                    label_color = (0, 215, 255)
                tile = cv2.resize(crop, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
                put_text(tile, f"SAR {frame} {status}", (5, 18), 0.40, label_color)
                put_text(tile, f"pose={pose}", (5, tile_h - 8), 0.36, label_color)
                row_i, col_i = divmod(tile_index, cols)
                x, y = col_i * tile_w, 90 + row_i * tile_h
                canvas[y:y + tile_h, x:x + tile_w] = tile
            path = SEGMENT_DIR / f"{segment['segment_id']}_page_{page_index + 1:02d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(path), canvas)
            page_paths.append(path)
        for path in page_paths:
            manifest.append({
                "artifact_type": "eligible_continuous_segment_contact", "scene": segment["scene"],
                "canonical_vehicle_id": segment["canonical_vehicle_id"], "segment_id": segment["segment_id"],
                "sar_frame_index": f"{segment['sar_frame_start']}-{segment['sar_frame_end']}",
                "artifact_path": str(path), "artifact_count": len(page_paths), "review_status": review_status,
                "notes": f"recommended_usage={segment['recommended_usage']}; page includes raw frames and explicit no-GT gaps",
            })
    return manifest


def make_overview(paths: Sequence[Path], output_prefix: str, cell_w: int = 420, cell_h: int = 240, per_page: int = 12) -> list[Path]:
    output: list[Path] = []
    for page_index in range(math.ceil(len(paths) / per_page)):
        page_paths = paths[page_index * per_page:(page_index + 1) * per_page]
        cols = 3
        rows_count = math.ceil(len(page_paths) / cols)
        canvas = np.full((rows_count * cell_h, cols * cell_w, 3), 20, dtype=np.uint8)
        for index, path in enumerate(page_paths):
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            thumb = cv2.resize(image, (cell_w, cell_h), interpolation=cv2.INTER_AREA)
            row_i, col_i = divmod(index, cols)
            canvas[row_i * cell_h:(row_i + 1) * cell_h, col_i * cell_w:(col_i + 1) * cell_w] = thumb
        output_path = OVERVIEW_DIR / f"{output_prefix}_{page_index + 1:02d}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), canvas)
        output.append(output_path)
    return output


def build_summary(rows: Sequence[dict[str, Any]], segments: Sequence[dict[str, Any]], preselected: set[str], visual_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    structure = [row for row in rows if row["s1l_structure_frame_eligible_bool"]]
    temporal = [row for row in rows if row["s1l_temporal_eligible_bool"]]
    mapping = [row for row in rows if row["mapping_anchor_eligible_bool"]]
    eligible_segments = [row for row in segments if row["segment_eligibility"] == "true"]
    by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for segment in segments:
        key = segment["canonical_vehicle_id"]
        by_thread[key].append(segment)
    thread_summary: dict[str, Any] = {}
    for key, items in sorted(by_thread.items()):
        if items[0]["vehicle_research_role"] not in {"structure_development", "structure_heldout_validation"}:
            continue
        thread_summary[key] = {
            "benchmark_role": items[0]["benchmark_role"],
            "vehicle_research_role": items[0]["vehicle_research_role"],
            "segment_count": len(items),
            "eligible_segment_count": sum(item["segment_eligibility"] == "true" for item in items),
            "segments": [
                {
                    "segment_id": item["segment_id"],
                    "start": item["sar_frame_start"], "end": item["sar_frame_end"],
                    "span": item["frame_span"], "gt_frames": item["gt_frame_count"],
                    "eligible_frames": item["eligible_frame_count"], "missing": item["missing_frame_count"],
                    "eligible": item["segment_eligibility"], "usage": item["recommended_usage"],
                }
                for item in items
            ],
        }
    return {
        "status": "S0MV_S1L_INPUT_SEMANTICS_CLEAR",
        "primary_semantic_conclusion": "S1L_ELIGIBILITY_WAS_INCORRECTLY_TIED_TO_MAPPING_ANCHORS",
        "preselection_interpretation": "12_FRAMES_ARE_ONLY_REPRESENTATIVE_PREVIEWS",
        "preselection_source_function": "select_s1l_candidates",
        "preselection_rule": "mapping-anchor-eligible rows only; up to four theta/radius ordered representatives per vehicle",
        "all_gt_rows": len(rows),
        "gold_usable_rows": sum(row["gt_quality_status"] in {"gold", "usable"} for row in rows),
        "canonical_linked_rows": sum(bool(row["canonical_vehicle_id"]) for row in rows),
        "canonical_linked_vehicle_count": len({(row["scene"], row["canonical_vehicle_id"]) for row in rows if row["canonical_vehicle_id"]}),
        "mapping_anchor_rows": len(mapping),
        "s1l_structure_frame_eligible_rows": len(structure),
        "s1l_temporal_eligible_rows": len(temporal),
        "preselected_preview_rows": len(preselected),
        "structure_and_mapping_intersection": sum(row["s1l_structure_frame_eligible_bool"] and row["mapping_anchor_eligible_bool"] for row in rows),
        "structure_not_mapping": sum(row["s1l_structure_frame_eligible_bool"] and not row["mapping_anchor_eligible_bool"] for row in rows),
        "mapping_not_structure": sum(row["mapping_anchor_eligible_bool"] and not row["s1l_structure_frame_eligible_bool"] for row in rows),
        "eligible_continuous_segment_count": len(eligible_segments),
        "all_segment_count": len(segments),
        "development_eligible_segment_count": sum(item["segment_eligibility"] == "true" and item["benchmark_role"] == "development" for item in segments),
        "heldout_eligible_segment_count": sum(item["segment_eligibility"] == "true" and item["benchmark_role"] == "heldout_validation" for item in segments),
        "visual_artifact_rows": len(visual_rows),
        "visual_review_statuses": dict(Counter(row["review_status"] for row in visual_rows)),
        "thread_summary": thread_summary,
        "allow_s1l_input_redesign": True,
        "allow_s1l_structure_extraction": False,
        "explicit_non_execution": [
            "no S1-L peak/island/ridge/structure extraction", "no mapping refit", "no existing S0/S0-M modification",
            "no candidate box", "no selector/ranking/Gate", "no training", "no automatic annotation", "no P1-F input",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-status", default="generated_pending_direct_review", choices=["generated_pending_direct_review", "directly_reviewed_complete"])
    args = parser.parse_args()
    for directory in (TIMELINE_DIR, PREVIEW_DIR, SEGMENT_DIR, OVERVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    rows, preselected = enrich_rows()
    segments = rebuild_segments(rows)
    all_gt = all_gt_manifest(rows)
    semantic = preselection_semantic_audit(rows)

    write_csv(ALL_GT_PATH, all_gt, list(all_gt[0].keys()))
    write_csv(PRESELECTION_AUDIT_PATH, semantic, list(semantic[0].keys()))
    write_csv(SEGMENTS_PATH, segments, list(segments[0].keys()))

    visual_rows: list[dict[str, Any]] = []
    visual_rows.extend(render_timelines(rows, segments, args.review_status))
    visual_rows.extend(render_preview_contexts(rows, segments, args.review_status))
    visual_rows.extend(render_segment_contacts(rows, segments, args.review_status))

    timeline_paths = [Path(row["artifact_path"]) for row in visual_rows if row["artifact_type"] == "vehicle_timeline"]
    preview_paths = [Path(row["artifact_path"]) for row in visual_rows if row["artifact_type"] == "preselected_12_context"]
    segment_paths = [Path(row["artifact_path"]) for row in visual_rows if row["artifact_type"] == "eligible_continuous_segment_contact"]
    overview_paths = (
        make_overview(timeline_paths, "timelines_overview")
        + make_overview(preview_paths, "previews_overview")
        + make_overview(segment_paths, "segments_overview")
    )
    for path in overview_paths:
        visual_rows.append({
            "artifact_type": "review_overview", "scene": "", "canonical_vehicle_id": "", "segment_id": "",
            "sar_frame_index": "", "artifact_path": str(path), "artifact_count": 1,
            "review_status": args.review_status, "notes": "overview for direct visual audit; temporary and not committed",
        })
    write_csv(VISUAL_MANIFEST_PATH, visual_rows, list(visual_rows[0].keys()))
    summary = build_summary(rows, segments, preselected, visual_rows)
    write_json(OUTPUT_ROOT / "s0mv_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
