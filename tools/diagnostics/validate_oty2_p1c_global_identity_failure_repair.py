#!/usr/bin/env python3
"""Validate the optical-only OTY2 P1-C repair artifact family and stage boundary."""

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
    "observations": ("manifests/oty2/oty2_p1c_observation_alternative_clusters.csv", {"scene", "frame_index", "detection_id", "selected_as_primary"}),
    "tracklets": ("manifests/oty2/oty2_p1c_atomic_tracklets.csv", {"scene", "atomic_tracklet_id", "frame_start", "frame_end", "split_reason"}),
    "roles": ("manifests/oty2/oty2_p1c_identity_evidence_roles.csv", {"scene", "evidence_id", "evidence_role", "input_to_solver", "evaluation_result"}),
    "anchors": ("manifests/oty2/oty2_p1c_identity_anchor_ledger.csv", {"scene", "evidence_id", "identity_anchor_start", "identity_anchor_end", "input_to_solver"}),
    "edges": ("manifests/oty2/oty2_p1c_global_identity_edges.csv", {"scene", "edge_id", "source_atomic_tracklet_id", "target_atomic_tracklet_id", "turnover_reset_penalty", "selected_by_solver"}),
    "threads": ("manifests/oty2/oty2_p1c_global_vehicle_threads.csv", {"scene", "global_vehicle_id", "frame_index", "atomic_tracklet_id", "observation_id", "incoming_edge_id"}),
    "summaries": ("manifests/oty2/oty2_p1c_global_vehicle_thread_summary.csv", {"scene", "global_vehicle_id", "frame_start", "frame_end"}),
    "reviews": ("manifests/oty2/oty2_p1c_global_identity_review_manifest.csv", {"scene", "review_id", "review_type", "temporary_visual_path", "review_status"}),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--metrics", type=Path, default=Path("outputs/oty2_p1c_global_identity_failure_repair_20260714/solver_metrics.json"))
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    failures: list[str] = []
    loaded: dict[str, list[dict[str, str]]] = {}
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

    roles = loaded.get("roles", [])
    anchors = loaded.get("anchors", [])
    edges = loaded.get("edges", [])
    threads = loaded.get("threads", [])
    summaries = loaded.get("summaries", [])
    reviews = loaded.get("reviews", [])

    heldout_failures = [row["evidence_id"] for row in roles if row.get("evidence_role") == "heldout_validation" and row.get("evaluation_result") == "fail"]
    if heldout_failures:
        failures.append(f"heldout_failures:{heldout_failures}")
    solver_anchors = [row["evidence_id"] for row in anchors if truth(row.get("input_to_solver"))]
    if solver_anchors:
        failures.append(f"identity_anchor_entered_solver:{solver_anchors}")
    selected_reset = [row["edge_id"] for row in edges if truth(row.get("selected_by_solver")) and int(row.get("turnover_reset_penalty") or 0) > 0]
    if selected_reset:
        failures.append(f"selected_lifecycle_reset_edges:{selected_reset}")

    selected_edges = {row["edge_id"] for row in edges if truth(row.get("selected_by_solver"))}
    used_observations = [row["observation_id"] for row in threads if row.get("observation_id")]
    duplicate_use = [key for key, count in Counter(used_observations).items() if count > 1]
    if duplicate_use:
        failures.append(f"duplicate_observation_use:{duplicate_use[:5]}")
    by_vehicle: dict[str, list[int]] = defaultdict(list)
    for row in threads:
        by_vehicle[row["global_vehicle_id"]].append(int(row["frame_index"]))
        if row.get("incoming_edge_id") and row["incoming_edge_id"] not in selected_edges:
            failures.append(f"unselected_incoming_edge:{row['incoming_edge_id']}")
    for vehicle, frames in by_vehicle.items():
        if frames != sorted(frames) or len(frames) != len(set(frames)):
            failures.append(f"thread_time_or_duplicate:{vehicle}")
    if {row["global_vehicle_id"] for row in summaries} != set(by_vehicle):
        failures.append("summary_thread_id_mismatch")

    metrics_path = args.metrics if args.metrics.is_absolute() else root / args.metrics
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if not metrics:
        failures.append(f"missing_metrics:{metrics_path}")
    if metrics.get("hard_constraints", {}).get("total_hard_constraint_violations") != 0:
        failures.append(f"hard_constraint_metric:{metrics.get('hard_constraints')}")
    if metrics.get("source_boundary") != "optical_only_no_sar_no_gt":
        failures.append("source_boundary_missing")
    if metrics.get("direct_review_complete") is not True:
        failures.append("direct_review_incomplete")
    for scene in SCENES:
        stability = metrics.get("stability", {}).get(scene, {})
        if not stability.get("thread_count_stable") or float(stability.get("minimum_edge_jaccard", 0.0)) < 1.0:
            failures.append(f"stability:{scene}:{stability}")

    incomplete_reviews = [row["review_id"] for row in reviews if row.get("review_status") != "reviewed_pass"]
    if incomplete_reviews:
        failures.append(f"review_manifest_incomplete:{incomplete_reviews[:5]}")
    for row in reviews:
        visual = row.get("temporary_visual_path", "")
        if visual and not (root / visual).exists():
            failures.append(f"missing_review_visual:{visual}")

    output_root = root / "outputs/oty2_p1c_global_identity_failure_repair_20260714"
    if git(root, "check-ignore", str(output_root)).returncode != 0:
        failures.append("review_output_not_gitignored")
    if git(root, "ls-files", "--error-unmatch", str(output_root)).returncode == 0:
        failures.append("review_output_tracked")
    p1b_diff = git(root, "diff", "--name-only", "--", "configs/oty2/oty2_p1b_optical_global_identity.yaml", "manifests/oty2/oty2_p1b_*", "reports/oty2/oty2_p1b_optical_global_identity_solver_20260713.md")
    if p1b_diff.stdout.strip():
        failures.append(f"p1b_artifact_overwrite:{p1b_diff.stdout.splitlines()}")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "row_counts": {name: len(rows) for name, rows in loaded.items()},
        "thread_counts": dict(Counter(row["scene"] for row in summaries)),
        "heldout_failures": heldout_failures,
        "selected_lifecycle_reset_edges": selected_reset,
        "hard_constraints": metrics.get("hard_constraints", {}),
        "direct_review_complete": metrics.get("direct_review_complete"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
