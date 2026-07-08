#!/usr/bin/env python
"""Build a diagnostic per-frame YOLO26l candidate bank for WGV1.2.

The bank combines available raw YOLO26l local detection tables with the
committed selected diagnostic render manifest. Raw tables are marked as
all-candidate evidence; selected manifest rows are only a fallback and must not
be treated as complete multi-car contrast.

This script does not run a detector, tracker replay, SAR pairing/support,
selector/ranking, or any final/revised annotation generation.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"

DEFAULT_SELECTED_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv"
DEFAULT_TARGET_FAMILIES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv"
DEFAULT_MERGE_CANDIDATES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_candidates_20260708.csv"
DEFAULT_RAW_TABLES = [
    REPO_ROOT
    / "outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/"
    "oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv",
    REPO_ROOT
    / "outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/"
    "oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv",
]

DEFAULT_BANK = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv"
DEFAULT_COVERAGE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_candidate_bank_coverage_20260708.csv"
DEFAULT_TF_CONTRAST = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_target_family_multicar_contrast_20260708.csv"
DEFAULT_MERGE_GATE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_merge_candidate_multicar_gate_20260708.csv"
DEFAULT_REVIEW_QUEUE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_review_queue_20260708.csv"

CRITICAL_WINDOWS = [
    ("GM_RM011", 0, 35, "GM_RM011_000_035"),
    ("GM_RM011", 135, 166, "GM_RM011_135_166"),
    ("GM_RM011", 231, 292, "GM_RM011_231_292"),
    ("GM_RM011", 237, 270, "GM_RM011_237_270_visible_gap_focus"),
    ("GM_RM017", 118, 214, "GM_RM017_118_214"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def x_bin(cx: float) -> str:
    if cx < 800.0 / 3.0:
        return "left"
    if cx < 1600.0 / 3.0:
        return "mid"
    return "right"


def selected_index(rows: list[dict[str, str]]) -> dict[tuple[str, int, str], dict[str, object]]:
    out: dict[tuple[str, int, str], dict[str, object]] = {}
    for row in rows:
        key = (row["scene_id"], int(row["optical_frame_num"]), row["source_detection_id"])
        item = out.setdefault(
            key,
            {
                "candidate_node_ids": set(),
                "display_status": set(),
                "risk_tags": set(),
                "reasons": set(),
            },
        )
        item["candidate_node_ids"].add(row["candidate_node_id"])
        item["display_status"].add(row.get("display_status", ""))
        item["risk_tags"].add(row.get("risk_tags", ""))
        item["reasons"].add(row.get("reason", ""))
    return out


def target_family_index(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for det_id in row["source_detection_ids"].split(";"):
            if det_id:
                out[det_id].add(row["target_family_id"])
    return out


def critical_window_id(scene: str, frame: int) -> str:
    hits = [window_id for win_scene, start, end, window_id in CRITICAL_WINDOWS if scene == win_scene and start <= frame <= end]
    return ";".join(hits)


def in_critical_window(scene: str, frame: int) -> bool:
    return bool(critical_window_id(scene, frame))


def is_full_scene_probe_table(path: Path) -> bool:
    return "oty2_yolo26l_detector_quality_probe" in path.as_posix()


def table_coverage_frames(path: Path, rows: list[dict[str, str]]) -> set[tuple[str, int]]:
    observed = {
        ((row.get("scene") or row.get("scene_id") or ""), int(row["optical_frame_num"]))
        for row in rows
        if (row.get("scene") or row.get("scene_id")) and row.get("optical_frame_num")
    }
    if not is_full_scene_probe_table(path):
        return observed

    scenes = {scene for scene, _frame in observed}
    covered: set[tuple[str, int]] = set(observed)
    for scene, start, end, _window_id in CRITICAL_WINDOWS:
        if scene in scenes:
            covered.update((scene, frame) for frame in range(start, end + 1))
    return covered


def selected_row_to_bank(
    row: dict[str, str],
    selected: dict[tuple[str, int, str], dict[str, object]],
    tf_index: dict[str, set[str]],
) -> dict[str, str]:
    scene = row["scene_id"]
    frame = int(row["optical_frame_num"])
    det_id = row["source_detection_id"]
    x1 = float(row["bbox_x1"])
    y1 = float(row["bbox_y1"])
    x2 = float(row["bbox_x2"])
    y2 = float(row["bbox_y2"])
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    w = x2 - x1
    h = y2 - y1
    item = selected[(scene, frame, det_id)]
    return {
        "scene_id": scene,
        "frame_id": str(frame),
        "source_detection_id": det_id,
        "bank_detection_id": f"{scene}_{frame:06d}_{det_id}_selected_fallback",
        "bank_source": "selected_manifest_fallback",
        "all_candidate_table_available": "no",
        "candidate_role": "selected_primary_only",
        "class_name": row["class_name"],
        "confidence": row["confidence"],
        "bbox_x1": f"{x1:.3f}",
        "bbox_y1": f"{y1:.3f}",
        "bbox_x2": f"{x2:.3f}",
        "bbox_y2": f"{y2:.3f}",
        "bbox_cx": f"{cx:.3f}",
        "bbox_cy": f"{cy:.3f}",
        "bbox_w": f"{w:.3f}",
        "bbox_h": f"{h:.3f}",
        "x_bin": x_bin(cx),
        "selected_candidate_node_ids": ";".join(sorted(item["candidate_node_ids"])),
        "selected_display_status": ";".join(sorted(s for s in item["display_status"] if s)),
        "selected_risk_tags": ";".join(sorted(s for s in item["risk_tags"] if s)),
        "linked_target_family_ids": ";".join(sorted(tf_index.get(det_id, []))),
        "not_final_box_flag": "yes",
        "not_SAR_ready_flag": "yes",
        "note": "selected manifest fallback only;not complete multicar contrast",
    }


def raw_row_to_bank(
    row: dict[str, str],
    selected: dict[tuple[str, int, str], dict[str, object]],
    tf_index: dict[str, set[str]],
    raw_source_name: str,
) -> dict[str, str]:
    scene = row.get("scene") or row.get("scene_id")
    frame = int(row["optical_frame_num"])
    det_id = row["det_id"]
    x1 = float(row["bbox_x1"])
    y1 = float(row["bbox_y1"])
    x2 = float(row["bbox_x2"])
    y2 = float(row["bbox_y2"])
    cx = float(row.get("bbox_cx") or (x1 + x2) / 2.0)
    cy = float(row.get("bbox_cy") or (y1 + y2) / 2.0)
    w = float(row.get("bbox_w") or (x2 - x1))
    h = float(row.get("bbox_h") or (y2 - y1))
    key = (scene, frame, det_id)
    item = selected.get(
        key,
        {
            "candidate_node_ids": set(),
            "display_status": set(),
            "risk_tags": set(),
            "reasons": set(),
        },
    )
    is_selected = bool(item["candidate_node_ids"])
    return {
        "scene_id": scene,
        "frame_id": str(frame),
        "source_detection_id": det_id,
        "bank_detection_id": f"{scene}_{frame:06d}_{det_id}_raw",
        "bank_source": raw_source_name,
        "all_candidate_table_available": "yes",
        "candidate_role": "selected_primary" if is_selected else "competing_candidate",
        "class_name": row["class_name"],
        "confidence": row["confidence"],
        "bbox_x1": f"{x1:.3f}",
        "bbox_y1": f"{y1:.3f}",
        "bbox_x2": f"{x2:.3f}",
        "bbox_y2": f"{y2:.3f}",
        "bbox_cx": f"{cx:.3f}",
        "bbox_cy": f"{cy:.3f}",
        "bbox_w": f"{w:.3f}",
        "bbox_h": f"{h:.3f}",
        "x_bin": x_bin(cx),
        "selected_candidate_node_ids": ";".join(sorted(item["candidate_node_ids"])),
        "selected_display_status": ";".join(sorted(s for s in item["display_status"] if s)),
        "selected_risk_tags": ";".join(sorted(s for s in item["risk_tags"] if s)),
        "linked_target_family_ids": ";".join(sorted(tf_index.get(det_id, []))),
        "not_final_box_flag": "yes",
        "not_SAR_ready_flag": "yes",
        "note": "raw YOLO26l local detection candidate;diagnostic only",
    }


def build_bank(
    selected_manifest: list[dict[str, str]],
    target_families: list[dict[str, str]],
    raw_tables: list[Path],
) -> tuple[list[dict[str, str]], set[tuple[str, int]]]:
    selected = selected_index(selected_manifest)
    tf_index = target_family_index(target_families)
    rows: list[dict[str, str]] = []
    raw_keys: set[tuple[str, int, str]] = set()
    raw_table_covered_frames: set[tuple[str, int]] = set()
    selected_fallback_keys: set[tuple[str, int, str]] = set()

    for raw_table in raw_tables:
        if not raw_table.exists():
            continue
        raw_rows = read_csv(raw_table)
        raw_table_covered_frames.update(table_coverage_frames(raw_table, raw_rows))
        raw_source_name = "raw_all_candidate:" + str(raw_table.as_posix())
        for raw_row in raw_rows:
            scene = raw_row.get("scene") or raw_row.get("scene_id")
            frame = int(raw_row["optical_frame_num"])
            det_id = raw_row["det_id"]
            if not in_critical_window(scene, frame):
                continue
            if (scene, frame, det_id) in raw_keys:
                continue
            raw_keys.add((scene, frame, det_id))
            rows.append(raw_row_to_bank(raw_row, selected, tf_index, raw_source_name))

    for selected_row in selected_manifest:
        scene = selected_row["scene_id"]
        frame = int(selected_row["optical_frame_num"])
        if not in_critical_window(scene, frame):
            continue
        key = (
            scene,
            frame,
            selected_row["source_detection_id"],
        )
        if key in raw_keys:
            continue
        if key in selected_fallback_keys:
            continue
        selected_fallback_keys.add(key)
        rows.append(selected_row_to_bank(selected_row, selected, tf_index))

    rows.sort(key=lambda r: (r["scene_id"], int(r["frame_id"]), r["source_detection_id"], r["candidate_role"]))
    return rows, raw_table_covered_frames


def coverage_rows(bank_rows: list[dict[str, str]], raw_table_covered_frames: set[tuple[str, int]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    by_scene_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in bank_rows:
        by_scene_frame[(row["scene_id"], int(row["frame_id"]))].append(row)

    for scene, start, end, window_id in CRITICAL_WINDOWS:
        expected_frames = list(range(start, end + 1))
        frames_with_any = [frame for frame in expected_frames if (scene, frame) in by_scene_frame]
        frames_with_raw_table = [frame for frame in expected_frames if (scene, frame) in raw_table_covered_frames]
        frames_with_raw = [
            frame
            for frame in expected_frames
            if any(r["all_candidate_table_available"] == "yes" for r in by_scene_frame.get((scene, frame), []))
        ]
        frames_selected_only = [
            frame
            for frame in frames_with_any
            if frame not in frames_with_raw
        ]
        frames_with_competing = [
            frame
            for frame in frames_with_raw
            if any(r["candidate_role"] == "competing_candidate" for r in by_scene_frame[(scene, frame)])
        ]
        missing_frames = [frame for frame in expected_frames if frame not in frames_with_any]
        raw_rows = sum(
            1
            for frame in expected_frames
            for r in by_scene_frame.get((scene, frame), [])
            if r["all_candidate_table_available"] == "yes"
        )
        selected_rows = sum(
            1
            for frame in expected_frames
            for r in by_scene_frame.get((scene, frame), [])
            if r["candidate_role"] in {"selected_primary", "selected_primary_only"}
        )
        if len(frames_with_raw_table) == len(expected_frames):
            status = "raw_table_available_for_window"
        elif frames_with_raw_table:
            status = "partial_raw_table_available_for_window"
        elif frames_with_any:
            status = "selected_manifest_only"
        else:
            status = "no_candidate_rows"
        raw_detectionless_frames = [frame for frame in frames_with_raw_table if frame not in frames_with_raw]
        rows.append(
            {
                "window_id": window_id,
                "scene_id": scene,
                "frame_start": str(start),
                "frame_end": str(end),
                "expected_frame_count": str(len(expected_frames)),
                "frames_with_any_candidate": str(len(frames_with_any)),
                "frames_with_raw_all_candidate_table": str(len(frames_with_raw_table)),
                "frames_with_raw_candidate_rows": str(len(frames_with_raw)),
                "raw_detectionless_frames": " ".join(str(frame) for frame in raw_detectionless_frames),
                "frames_selected_manifest_only": str(len(frames_selected_only)),
                "frames_with_competing_candidate": str(len(frames_with_competing)),
                "missing_candidate_frames": " ".join(str(frame) for frame in missing_frames),
                "raw_candidate_row_count": str(raw_rows),
                "selected_candidate_row_count": str(selected_rows),
                "coverage_status": status,
                "sar_ready": "no / blocked",
                "note": "coverage for diagnostic candidate bank only",
            }
        )
    return rows


def target_family_contrast_rows(
    target_families: list[dict[str, str]],
    bank_rows: list[dict[str, str]],
    raw_table_covered_frames: set[tuple[str, int]],
) -> list[dict[str, str]]:
    by_det = {row["source_detection_id"]: row for row in bank_rows}
    by_scene_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in bank_rows:
        by_scene_frame[(row["scene_id"], int(row["frame_id"]))].append(row)

    rows: list[dict[str, str]] = []
    for tf in target_families:
        det_ids = [det_id for det_id in tf["source_detection_ids"].split(";") if det_id]
        frames = [int(frame) for frame in tf["frame_sequence"].split()] if tf["frame_sequence"] else []
        raw_frames = []
        raw_candidate_row_frames = []
        competing_frames = []
        competing_ids: set[str] = set()
        competing_x_bins: set[str] = set()
        selected_rows_present = 0
        for frame in frames:
            frame_rows = by_scene_frame.get((tf["scene_id"], frame), [])
            if (tf["scene_id"], frame) in raw_table_covered_frames:
                raw_frames.append(frame)
            if any(row["all_candidate_table_available"] == "yes" for row in frame_rows):
                raw_candidate_row_frames.append(frame)
            for row in frame_rows:
                if row["candidate_role"] == "competing_candidate":
                    competing_frames.append(frame)
                    competing_ids.add(row["source_detection_id"])
                    competing_x_bins.add(row["x_bin"])
            for det_id in det_ids:
                bank_row = by_det.get(det_id)
                if bank_row and int(bank_row["frame_id"]) == frame:
                    selected_rows_present += 1

        if len(raw_frames) == len(frames) and frames:
            status = "all_candidate_contrast_available"
        elif raw_frames:
            status = "partial_all_candidate_contrast_available"
        else:
            status = "contrast_missing_selected_manifest_only"

        if status == "all_candidate_contrast_available" and competing_ids:
            recommendation = "review_competing_candidates_before_merge"
        elif status == "all_candidate_contrast_available":
            recommendation = "no_competing_candidate_in_available_bank_review_sequence"
        elif status == "partial_all_candidate_contrast_available":
            recommendation = "do_not_auto_merge_partial_contrast"
        else:
            recommendation = "do_not_auto_merge_contrast_missing"

        rows.append(
            {
                "target_family_id": tf["target_family_id"],
                "scene_id": tf["scene_id"],
                "source_fragment_id": tf["source_fragment_id"],
                "frame_start": tf["frame_start"],
                "frame_end": tf["frame_end"],
                "frame_count": tf["frame_count"],
                "frames_with_raw_all_candidate_table": str(len(set(raw_frames))),
                "frames_with_raw_candidate_rows": str(len(set(raw_candidate_row_frames))),
                "frames_with_competing_candidate": str(len(set(competing_frames))),
                "selected_rows_present_in_bank": str(selected_rows_present),
                "competing_source_detection_ids": ";".join(sorted(competing_ids)),
                "competing_x_bins": ";".join(sorted(competing_x_bins)),
                "contrast_status": status,
                "contrast_recommendation": recommendation,
                "sar_ready": "no / blocked",
                "note": "target-family contrast from available candidate bank only",
            }
        )
    return rows


def merge_gate_rows(
    merge_candidates: list[dict[str, str]],
    tf_contrast: list[dict[str, str]],
) -> list[dict[str, str]]:
    contrast_by_tf = {row["target_family_id"]: row for row in tf_contrast}
    rows: list[dict[str, str]] = []
    missing_status = "contrast_missing_selected_manifest_only"

    for merge in merge_candidates:
        from_contrast = contrast_by_tf.get(merge["from_target_family_id"])
        to_contrast = contrast_by_tf.get(merge["to_target_family_id"])
        from_status = from_contrast["contrast_status"] if from_contrast else "missing_target_family_contrast_row"
        to_status = to_contrast["contrast_status"] if to_contrast else "missing_target_family_contrast_row"
        from_competing = int(from_contrast["frames_with_competing_candidate"]) if from_contrast else 0
        to_competing = int(to_contrast["frames_with_competing_candidate"]) if to_contrast else 0
        current_strength = merge["candidate_strength"]
        gate_reasons: list[str] = []

        if current_strength == "blocked":
            gate_status = "blocked"
            gate_reasons.append("sequence_or_endpoint_gate_already_blocked")
        elif from_status == missing_status or to_status == missing_status:
            gate_status = "blocked_auto_merge_contrast_missing"
            gate_reasons.append("all_candidate_multicar_contrast_missing")
        elif from_status.startswith("partial") or to_status.startswith("partial"):
            gate_status = "review_only_partial_multicar_contrast"
            gate_reasons.append("partial_all_candidate_multicar_contrast")
        elif from_competing or to_competing:
            gate_status = "review_only_competing_candidates_present"
            gate_reasons.append("same_frame_competing_candidates_present")
        else:
            gate_status = "review_only_sequence_and_contrast_available"
            gate_reasons.append("sequence_gate_passed_but_still_human_review_required")

        rows.append(
            {
                "merge_candidate_id": merge["merge_candidate_id"],
                "scene_id": merge["scene_id"],
                "from_target_family_id": merge["from_target_family_id"],
                "to_target_family_id": merge["to_target_family_id"],
                "from_frame_end": merge["from_frame_end"],
                "to_frame_start": merge["to_frame_start"],
                "original_candidate_strength": current_strength,
                "sequence_reason_codes": merge["reason_codes"],
                "from_contrast_status": from_status,
                "to_contrast_status": to_status,
                "from_competing_frame_count": str(from_competing),
                "to_competing_frame_count": str(to_competing),
                "multicar_merge_gate_status": gate_status,
                "multicar_gate_reason_codes": ";".join(gate_reasons),
                "auto_merge_allowed": "no",
                "review_required": "yes",
                "sar_ready": "no / blocked",
                "not_final_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "diagnostic merge gate only;not same-vehicle truth",
            }
        )

    return rows


def merge_review_queue_rows(
    merge_gate: list[dict[str, str]],
    tf_contrast: list[dict[str, str]],
) -> list[dict[str, str]]:
    contrast_by_tf = {row["target_family_id"]: row for row in tf_contrast}
    rows: list[dict[str, str]] = []
    for item in merge_gate:
        if not item["multicar_merge_gate_status"].startswith("review_only"):
            continue
        from_tf = contrast_by_tf[item["from_target_family_id"]]
        to_tf = contrast_by_tf[item["to_target_family_id"]]
        rows.append(
            {
                "review_item_id": f"MRQ{len(rows) + 1:03d}",
                "merge_candidate_id": item["merge_candidate_id"],
                "scene_id": item["scene_id"],
                "from_target_family_id": item["from_target_family_id"],
                "from_frame_start": from_tf["frame_start"],
                "from_frame_end": from_tf["frame_end"],
                "to_target_family_id": item["to_target_family_id"],
                "to_frame_start": to_tf["frame_start"],
                "to_frame_end": to_tf["frame_end"],
                "multicar_merge_gate_status": item["multicar_merge_gate_status"],
                "sequence_reason_codes": item["sequence_reason_codes"],
                "from_competing_frame_count": item["from_competing_frame_count"],
                "to_competing_frame_count": item["to_competing_frame_count"],
                "from_competing_x_bins": from_tf["competing_x_bins"],
                "to_competing_x_bins": to_tf["competing_x_bins"],
                "from_contrast_recommendation": from_tf["contrast_recommendation"],
                "to_contrast_recommendation": to_tf["contrast_recommendation"],
                "human_review_question": "Do the from/to target families keep the same real-vehicle referent after comparing competing candidates?",
                "required_evidence": "review selected primary frames together with same-frame competing candidates;check center/area/class/x_bin continuity",
                "auto_merge_allowed": "no",
                "review_required": "yes",
                "sar_ready": "no / blocked",
                "not_final_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "candidate for vehicle-centric diagnostic review pack;not identity truth",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-manifest", type=Path, default=DEFAULT_SELECTED_MANIFEST)
    parser.add_argument("--target-families", type=Path, default=DEFAULT_TARGET_FAMILIES)
    parser.add_argument("--merge-candidates", type=Path, default=DEFAULT_MERGE_CANDIDATES)
    parser.add_argument("--raw-table", action="append", type=Path, default=None)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--target-family-contrast", type=Path, default=DEFAULT_TF_CONTRAST)
    parser.add_argument("--merge-gate", type=Path, default=DEFAULT_MERGE_GATE)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    args = parser.parse_args()

    raw_tables = args.raw_table if args.raw_table else DEFAULT_RAW_TABLES
    selected_manifest = read_csv(args.selected_manifest)
    target_families = read_csv(args.target_families)
    merge_candidates = read_csv(args.merge_candidates)
    bank, raw_table_covered_frames = build_bank(selected_manifest, target_families, raw_tables)
    coverage = coverage_rows(bank, raw_table_covered_frames)
    tf_contrast = target_family_contrast_rows(target_families, bank, raw_table_covered_frames)
    merge_gate = merge_gate_rows(merge_candidates, tf_contrast)
    review_queue = merge_review_queue_rows(merge_gate, tf_contrast)

    write_csv(args.bank, bank, list(bank[0].keys()) if bank else [])
    write_csv(args.coverage, coverage, list(coverage[0].keys()) if coverage else [])
    write_csv(args.target_family_contrast, tf_contrast, list(tf_contrast[0].keys()) if tf_contrast else [])
    write_csv(args.merge_gate, merge_gate, list(merge_gate[0].keys()) if merge_gate else [])
    write_csv(args.review_queue, review_queue, list(review_queue[0].keys()) if review_queue else [])

    print(f"wrote {args.bank} rows={len(bank)}")
    print(f"wrote {args.coverage} rows={len(coverage)}")
    print(f"wrote {args.target_family_contrast} rows={len(tf_contrast)}")
    print(f"wrote {args.merge_gate} rows={len(merge_gate)}")
    print(f"wrote {args.review_queue} rows={len(review_queue)}")
    print("bank source counts:", dict(Counter(row["all_candidate_table_available"] for row in bank)))
    print("candidate role counts:", dict(Counter(row["candidate_role"] for row in bank)))
    print("merge gate counts:", dict(Counter(row["multicar_merge_gate_status"] for row in merge_gate)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
