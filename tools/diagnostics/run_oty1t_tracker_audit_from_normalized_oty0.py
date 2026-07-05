"""Run bounded OTY1t tracker sensitivity audit from raw or normalized OTY0 input.

This wrapper is intentionally narrower than the main OTY1t runner. It writes
all runtime/probe artifacts under the requested output directory and does not
write report samples into ``reports/oty1t``. It can strip normalized OTY0 tables
to active-only OTY0-compatible detection rows before replaying a standard MOT tracker. It
does not change OTY0, OTY1, OTY1t, tracker code, tracker parameters, detector
weights, final annotations, revised GT, final boxes, SAR pairing, support
audit, selector/ranking logic, or identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (REPO_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_oty1t_tracker_audit import (  # noqa: E402
    ASSIGNMENT_FIELDS,
    EVENT_FIELDS,
    FAILURE_BUCKET_FIELDS,
    STATE_FIELDS,
    TRACK_FIELDS,
    UNMATCHED_AUDIT_FIELDS,
    ambiguous_association_events,
    boolish,
    count_events,
    count_status,
    diagnosis_bucket_distribution,
    frame_sizes_from_rows,
    optical_frame_inventory,
    read_csv_rows,
    run_tracker_detection_table_replay,
    sort_events,
    write_csv,
    write_json,
)
from src.optical_state.tracklet_builder import normalize_detections  # noqa: E402
from src.optical_state.tracker_audit import (  # noqa: E402
    TrackerAuditConfig,
    build_tracker_state_timeseries,
    build_tracker_tracks,
)
from src.optical_state.tracker_diagnosis import (  # noqa: E402
    DiagnosisConfig,
    build_failure_bucket_summary,
    build_unmatched_detection_audit,
    event_distribution,
    oty2_stable_input_recommendation,
)


OTY0_DETECTION_FIELDS = [
    "scene",
    "optical_frame_num",
    "optical_path",
    "det_id",
    "class_id",
    "class_name",
    "confidence",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_cx",
    "bbox_cy",
    "bbox_w",
    "bbox_h",
]

SUMMARY_FIELDS = [
    "scene",
    "detector_label",
    "tracker_name",
    "input_variant",
    "source_detection_table",
    "tracker_input_table",
    "timestamp",
    "tracker_real_run",
    "dependency_status",
    "raw_rows_in",
    "tracker_input_rows",
    "suppressed_rows_excluded",
    "tracked_assignment_rows",
    "unmatched_detection_rows",
    "unmatched_rate",
    "duplicate_overlap_unmatched_detections",
    "tracker_track_count",
    "stable_hypothesis_count",
    "fragmented_hypothesis_count",
    "ambiguous_hypothesis_count",
    "short_hypothesis_count",
    "duplicate_overlap_hypothesis_count",
    "duplicate_track_overlap_count",
    "possible_id_switch_count",
    "lost_event_count",
    "reactivated_event_count",
    "low_score_recovery_count",
    "review_required_object_hypothesis_status",
    "largest_blocker",
    "output_dir",
]


def read_fieldnames(path: str | Path) -> list[str]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader, [])


def oty0_compatible_row(row: Mapping[str, Any], scene: str) -> dict[str, Any]:
    out = {field: row.get(field, "") for field in OTY0_DETECTION_FIELDS}
    out["scene"] = out.get("scene") or scene
    return out


def prepare_tracker_input(
    input_table: Path,
    output_dir: Path,
    scene: str,
    active_only: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path]:
    raw_rows = read_csv_rows(input_table)
    scene_rows = [row for row in raw_rows if not str(row.get("scene", "")).strip() or str(row.get("scene", "")).strip() == scene]
    if active_only:
        input_rows = [row for row in scene_rows if boolish(row.get("active_for_tracking"))]
    else:
        input_rows = list(scene_rows)
    compatible_rows = [oty0_compatible_row(row, scene) for row in input_rows]
    table_path = output_dir / "tracker_input_detection_table.csv"
    write_csv(table_path, compatible_rows, OTY0_DETECTION_FIELDS)
    return [dict(row) for row in scene_rows], compatible_rows, table_path


def count_bucket(rows: Sequence[Mapping[str, Any]], bucket: str) -> int:
    return sum(1 for row in rows if str(row.get("diagnosis_bucket", "")) == bucket)


def tracker_available(args: argparse.Namespace, dependency_facts: Mapping[str, Any]) -> bool:
    if args.tracker == "bytetrack":
        return bool(dependency_facts.get("bytetrack_available"))
    if args.tracker == "botsort":
        return bool(dependency_facts.get("botsort_available"))
    return False


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_table = Path(args.input_detection_table)
    raw_rows, tracker_input_rows, tracker_input_table = prepare_tracker_input(
        input_table,
        output_dir,
        args.scene,
        args.active_only,
    )
    frame_sizes = frame_sizes_from_rows(tracker_input_rows)
    detections = normalize_detections(tracker_input_rows, frame_sizes=frame_sizes, scene=args.scene)
    frame_numbers = optical_frame_inventory(tracker_input_rows, {})

    config = TrackerAuditConfig(
        tracker_name=args.tracker,
        tracker_input_mode="normalized_active_only_probe" if args.active_only else "raw_oty0_probe",
        detector_source=args.detector_label,
        frame_rate=args.frame_rate,
        track_high_thresh=args.track_high_thresh,
        track_low_thresh=args.track_low_thresh,
        new_track_thresh=args.new_track_thresh,
        track_buffer=args.track_buffer,
        match_thresh=args.match_thresh,
        fuse_score=args.fuse_score,
        neighbor_distance_px=args.neighbor_distance_px,
        contact_margin_px=args.contact_margin_px,
        min_stable_track_length=args.min_stable_track_length,
        short_track_length=args.short_track_length,
        duplicate_iou_threshold=args.duplicate_iou_threshold,
        duplicate_center_distance_px=args.duplicate_center_distance_px,
        possible_switch_gap_frames=args.possible_switch_gap_frames,
        possible_switch_distance_px=args.possible_switch_distance_px,
    )

    assignments, events, dependency_facts = run_tracker_detection_table_replay(detections, frame_numbers, config)
    tracker_real_run = tracker_available(args, dependency_facts)
    events = sort_events(list(events) + ambiguous_association_events(assignments, config))
    tracks = build_tracker_tracks(assignments, events, config)
    state_rows = build_tracker_state_timeseries(assignments, tracks, config)
    diagnosis_config = DiagnosisConfig(
        tracker_name=args.tracker,
        track_high_thresh=args.track_high_thresh,
        neighbor_distance_px=args.neighbor_distance_px,
        contact_margin_px=args.contact_margin_px,
        duplicate_iou_threshold=args.duplicate_iou_threshold,
    )
    unmatched_audit = build_unmatched_detection_audit(assignments, [], [], diagnosis_config)
    failure_buckets = build_failure_bucket_summary(unmatched_audit, args.scene, args.tracker)

    write_csv(output_dir / "oty1t_tracker_detection_assignments.csv", assignments, ASSIGNMENT_FIELDS)
    write_csv(output_dir / "oty1t_tracker_tracks.csv", tracks, TRACK_FIELDS)
    write_csv(output_dir / "oty1t_tracker_state_timeseries.csv", state_rows, STATE_FIELDS)
    write_csv(output_dir / "oty1t_tracker_events.csv", events, EVENT_FIELDS)
    write_csv(output_dir / "oty1t_unmatched_detection_audit.csv", unmatched_audit, UNMATCHED_AUDIT_FIELDS)
    write_csv(output_dir / "oty1t_tracker_failure_buckets.csv", failure_buckets, FAILURE_BUCKET_FIELDS)

    tracked_rows = sum(1 for row in assignments if str(row.get("tracker_track_id", "") or ""))
    unmatched_rows = sum(1 for row in assignments if boolish(row.get("is_unmatched_detection")))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": timestamp,
        "scene": args.scene,
        "detector_label": args.detector_label,
        "input_variant": args.input_variant,
        "source_detection_table": str(input_table),
        "tracker_input_table": str(tracker_input_table),
        "output_dir": str(output_dir),
        "tracker_name": args.tracker,
        "tracker_real_run": tracker_real_run,
        "dependency_status": dependency_facts.get("dependency_status", "missing"),
        "raw_rows_in": len(raw_rows),
        "tracker_input_rows": len(tracker_input_rows),
        "suppressed_rows_excluded": len(raw_rows) - len(tracker_input_rows),
        "tracked_assignment_rows": tracked_rows,
        "unmatched_detection_rows": unmatched_rows,
        "unmatched_rate": round(unmatched_rows / len(tracker_input_rows), 6) if tracker_input_rows else 0.0,
        "duplicate_overlap_unmatched_detections": count_bucket(unmatched_audit, "duplicate_or_overlap_rejected"),
        "tracker_track_count": len(tracks),
        "stable_hypothesis_count": count_status(tracks, "identity_status", "tracker_stable_hypothesis"),
        "fragmented_hypothesis_count": count_status(tracks, "identity_status", "tracker_fragmented_hypothesis"),
        "ambiguous_hypothesis_count": count_status(tracks, "identity_status", "tracker_ambiguous_hypothesis"),
        "short_hypothesis_count": count_status(tracks, "identity_status", "tracker_short_hypothesis"),
        "duplicate_overlap_hypothesis_count": count_status(tracks, "identity_status", "tracker_duplicate_overlap_hypothesis"),
        "duplicate_track_overlap_count": count_events(events, "duplicate_track_overlap"),
        "possible_id_switch_count": count_events(events, "possible_id_switch"),
        "lost_event_count": count_events(events, "track_lost"),
        "reactivated_event_count": count_events(events, "track_reactivated"),
        "low_score_recovery_count": count_events(events, "low_score_recovery"),
        "ambiguous_association_count": count_events(events, "ambiguous_association"),
        "unmatched_bucket_distribution": diagnosis_bucket_distribution(unmatched_audit),
        "event_type_distribution": event_distribution(events),
        "review_required_object_hypothesis_status": "not_run_no_p4g_downstream_in_this_probe",
        "posthoc_sources_used_for_runtime_tracking": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "support_audit_entered": False,
        "annotation_proposal_entered": False,
        "selector_ranking_entered": False,
        "identity_truth_claimed": False,
        "largest_blocker": "tracker_dependency_unavailable" if not tracker_real_run else "none_tracker_ids_remain_hypotheses_only",
        "oty2_stable_input_recommendation": "",
        "audit_config": {
            "frame_rate": config.frame_rate,
            "track_high_thresh": config.track_high_thresh,
            "track_low_thresh": config.track_low_thresh,
            "new_track_thresh": config.new_track_thresh,
            "track_buffer": config.track_buffer,
            "match_thresh": config.match_thresh,
            "fuse_score": config.fuse_score,
            "neighbor_distance_px": config.neighbor_distance_px,
            "contact_margin_px": config.contact_margin_px,
            "min_stable_track_length": config.min_stable_track_length,
            "short_track_length": config.short_track_length,
            "duplicate_iou_threshold": config.duplicate_iou_threshold,
            "duplicate_center_distance_px": config.duplicate_center_distance_px,
            "possible_switch_gap_frames": config.possible_switch_gap_frames,
            "possible_switch_distance_px": config.possible_switch_distance_px,
        },
    }
    summary["oty2_stable_input_recommendation"] = oty2_stable_input_recommendation(summary)
    write_json(output_dir / "oty1t_tracker_sensitivity_summary.json", summary)
    write_csv(output_dir / "oty1t_tracker_sensitivity_summary.csv", [summary], SUMMARY_FIELDS)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--detector-label", required=True)
    parser.add_argument("--tracker", default="bytetrack", choices=["bytetrack", "botsort"])
    parser.add_argument("--input-variant", required=True, choices=["raw", "normalized_active"])
    parser.add_argument("--input-detection-table", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--active-only", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--frame-rate", type=int, default=30)
    parser.add_argument("--track-high-thresh", type=float, default=0.25)
    parser.add_argument("--track-low-thresh", type=float, default=0.10)
    parser.add_argument("--new-track-thresh", type=float, default=0.25)
    parser.add_argument("--track-buffer", type=int, default=30)
    parser.add_argument("--match-thresh", type=float, default=0.80)
    parser.add_argument("--fuse-score", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--neighbor-distance-px", type=float, default=120.0)
    parser.add_argument("--contact-margin-px", type=float, default=2.0)
    parser.add_argument("--min-stable-track-length", type=int, default=8)
    parser.add_argument("--short-track-length", type=int, default=3)
    parser.add_argument("--duplicate-iou-threshold", type=float, default=0.50)
    parser.add_argument("--duplicate-center-distance-px", type=float, default=80.0)
    parser.add_argument("--possible-switch-gap-frames", type=int, default=4)
    parser.add_argument("--possible-switch-distance-px", type=float, default=140.0)
    return parser


def main() -> None:
    summary = run_probe(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
