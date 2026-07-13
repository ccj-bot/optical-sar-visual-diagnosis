#!/usr/bin/env python3
"""Validate committed OTY2 P1-B manifests and ignored review-package boundaries."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCENES = {"GM_RM011", "GM_RM017", "GM_RM019"}

FILES = {
    "observations": ("manifests/oty2/oty2_p1b_observation_alternative_clusters.csv", {"scene", "frame_index", "detection_id", "detector_source", "bbox", "existing_tracker_ids", "selected_as_primary"}),
    "tracklets": ("manifests/oty2/oty2_p1b_atomic_tracklets.csv", {"scene", "atomic_tracklet_id", "frame_start", "frame_end", "split_reason", "purity_risk"}),
    "roles": ("manifests/oty2/oty2_p1b_identity_evidence_roles.csv", {"scene", "evidence_id", "relation", "evidence_role", "input_to_solver", "evaluation_result"}),
    "edges": ("manifests/oty2/oty2_p1b_global_identity_edges.csv", {"scene", "edge_id", "source_atomic_tracklet_id", "target_atomic_tracklet_id", "selected_by_solver", "total_integer_cost"}),
    "threads": ("manifests/oty2/oty2_p1b_global_vehicle_threads.csv", {"scene", "global_vehicle_id", "frame_index", "atomic_tracklet_id", "observation_id", "is_interpolated_gap", "lifecycle_state"}),
    "summaries": ("manifests/oty2/oty2_p1b_global_vehicle_thread_summary.csv", {"scene", "global_vehicle_id", "frame_start", "frame_end", "visible_frame_count", "gap_frame_count"}),
    "reviews": ("manifests/oty2/oty2_p1b_global_identity_review_manifest.csv", {"scene", "review_id", "review_type", "temporary_visual_path", "review_status"}),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--metrics", type=Path, default=Path("outputs/oty2_p1b_optical_global_identity_20260713/solver_metrics.json"))
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    loaded: dict[str, list[dict[str, str]]] = {}
    failures: list[str] = []
    for name, (relative, required) in FILES.items():
        path = root / relative
        if not path.exists():
            failures.append(f"missing:{relative}")
            continue
        fields, rows = read_csv(path)
        missing = sorted(required - set(fields))
        if missing:
            failures.append(f"schema:{relative}:missing={missing}")
        if rows and {row.get("scene", "") for row in rows} - SCENES:
            failures.append(f"scene_domain:{relative}")
        loaded[name] = rows

    observations = loaded.get("observations", [])
    tracklets = loaded.get("tracklets", [])
    edges = loaded.get("edges", [])
    threads = loaded.get("threads", [])
    summaries = loaded.get("summaries", [])
    reviews = loaded.get("reviews", [])

    observation_ids = {row["detection_id"] for row in observations}
    tracklet_ids = {row["atomic_tracklet_id"] for row in tracklets}
    selected_edges = {row["edge_id"] for row in edges if truth(row["selected_by_solver"])}
    used_observations = [row["observation_id"] for row in threads if row.get("observation_id")]
    duplicate_use = [key for key, value in Counter(used_observations).items() if value > 1]
    if duplicate_use:
        failures.append(f"duplicate_observation_use:{duplicate_use[:5]}")
    for row in threads:
        if row.get("observation_id") and row["observation_id"] not in observation_ids:
            failures.append(f"unknown_observation:{row['observation_id']}")
        if row.get("atomic_tracklet_id") and row["atomic_tracklet_id"] not in tracklet_ids:
            failures.append(f"unknown_tracklet:{row['atomic_tracklet_id']}")
        if row.get("incoming_edge_id") and row["incoming_edge_id"] not in selected_edges:
            failures.append(f"unknown_or_unselected_edge:{row['incoming_edge_id']}")
        if truth(row.get("is_interpolated_gap")) and row.get("bbox"):
            failures.append(f"synthetic_gap_bbox:{row['global_vehicle_id']}:{row['frame_index']}")

    by_vehicle: dict[str, list[int]] = defaultdict(list)
    for row in threads:
        by_vehicle[row["global_vehicle_id"]].append(int(row["frame_index"]))
    for vehicle, frames in by_vehicle.items():
        if frames != sorted(frames) or len(frames) != len(set(frames)):
            failures.append(f"thread_time_or_duplicate:{vehicle}")
    summary_ids = {row["global_vehicle_id"] for row in summaries}
    if summary_ids != set(by_vehicle):
        failures.append("summary_thread_id_mismatch")

    metrics_path = args.metrics if args.metrics.is_absolute() else root / args.metrics
    if not metrics_path.exists():
        failures.append(f"missing_metrics:{metrics_path}")
        metrics = {}
    else:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        hard = metrics.get("hard_constraints", {})
        if hard.get("total_hard_constraint_violations") != 0:
            failures.append(f"hard_constraint_metric:{hard}")
        if metrics.get("source_boundary") != "optical_only_no_sar_no_gt":
            failures.append("source_boundary_missing")

    required_review_types = {"full_thread", "tracker_id_merge", "tracker_id_split", "gap_recovery", "heldout_validation_failure"}
    present_review_types = {row["review_type"] for row in reviews}
    if not {"full_thread"}.issubset(present_review_types):
        failures.append("missing_full_thread_review_rows")
    for row in reviews:
        visual = row.get("temporary_visual_path", "")
        if visual and not (root / visual).exists():
            failures.append(f"missing_review_visual:{visual}")
    output_root = root / "outputs/oty2_p1b_optical_global_identity_20260713"
    check_ignore = subprocess.run(["git", "check-ignore", str(output_root)], cwd=root, capture_output=True, text=True)
    if check_ignore.returncode != 0:
        failures.append("review_output_not_gitignored")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "row_counts": {name: len(rows) for name, rows in loaded.items()},
        "thread_counts": dict(Counter(row["scene"] for row in summaries)),
        "review_types": dict(Counter(row["review_type"] for row in reviews)),
        "hard_constraints": metrics.get("hard_constraints", {}),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
