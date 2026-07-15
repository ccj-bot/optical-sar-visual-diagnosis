#!/usr/bin/env python3
from __future__ import annotations

"""Validate the bounded S1-L body-support attribution NOT_READY closure."""

import csv
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
OUTPUT_ROOT = Path(r"D:\profile\research\workspace\output\oty2_s1l_body_support_attribution_20260715")
BASE_HEAD = "8519696ece0760e8af6d85a655773aaedae5a0c0"

FRAMES = MANIFEST_DIR / "oty2_s1l_body_support_coordinate_frames.csv"
COMPETITION = MANIFEST_DIR / "oty2_s1l_body_support_coordinate_competition.csv"
CASEBOOK = MANIFEST_DIR / "oty2_s1l_body_support_casebook_manifest.csv"
CASE_REVIEWS = MANIFEST_DIR / "oty2_s1l_body_support_case_reviews.csv"
SURFACES = MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_surfaces.csv"
SURFACE_CASEBOOK = MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_casebook_manifest.csv"
SURFACE_REVIEWS = MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_reviews.csv"
FINAL_REPORT = REPORT_DIR / "oty2_s1l_body_support_attribution_and_gt_neighborhood_optimality_20260715.md"
REPLAY = OUTPUT_ROOT / "body_support_replay_check.json"

ALLOWED_PATHS = {
    "docs/OTY2_S1L_BODY_SUPPORT_ATTRIBUTION_AND_GT_NEIGHBORHOOD_OPTIMALITY_AUDIT_PROTOCOL.md",
    "reports/oty2/oty2_s1l_body_support_attribution_logic_audit_20260715.md",
    "reports/oty2/oty2_s1l_body_support_minimum_coordinate_casebook_review_20260715.md",
    "reports/oty2/oty2_s1l_body_support_attribution_and_gt_neighborhood_optimality_20260715.md",
    "tools/diagnostics/run_oty2_s1l_body_support_coordinate_casebook.py",
    "tools/diagnostics/run_oty2_s1l_gt_neighborhood_perturbation_pilot.py",
    "tools/diagnostics/run_oty2_s1l_body_support_replay_check.py",
    "tools/diagnostics/validate_oty2_s1l_body_support_attribution_outputs.py",
    "manifests/oty2/oty2_s1l_body_support_coordinate_frames.csv",
    "manifests/oty2/oty2_s1l_body_support_coordinate_competition.csv",
    "manifests/oty2/oty2_s1l_body_support_casebook_manifest.csv",
    "manifests/oty2/oty2_s1l_body_support_case_reviews.csv",
    "manifests/oty2/oty2_s1l_body_support_gt_neighborhood_surfaces.csv",
    "manifests/oty2/oty2_s1l_body_support_gt_neighborhood_casebook_manifest.csv",
    "manifests/oty2/oty2_s1l_body_support_gt_neighborhood_reviews.csv",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        fail(f"missing required output: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_float(value: Any) -> float:
    return float(str(value).strip())


def git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def validate_scope() -> None:
    git("cat-file", "-e", f"{BASE_HEAD}^{{commit}}")
    changed = set(filter(None, git("diff", "--name-only", BASE_HEAD).splitlines()))
    untracked = set(filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()))
    unexpected = (changed | untracked) - ALLOWED_PATHS
    if unexpected:
        fail(f"unexpected path outside bounded S1-L body-support scope: {sorted(unexpected)}")
    missing = [path for path in ALLOWED_PATHS if not (REPO_ROOT / path).exists()]
    if missing:
        fail(f"missing allowed formal path: {missing}")


def validate_coordinate_outputs() -> None:
    frames = read_csv(FRAMES)
    if len(frames) != 291:
        fail(f"expected 291 coordinate frame rows, got {len(frames)}")
    unit_counts = Counter(row["research_unit_id"] for row in frames)
    expected = {
        "S0MV-GM_RM017-PV002-SEG02": 65,
        "S0MV-GM_RM017-PV003-SEG01": 67,
        "S0MV-GM_RM017-PV004-SEG01": 58,
        "S0MV-GM_RM011-PV001-SEG01": 36,
        "S1L-BG-0011-TRAJECTORY-ON-FIXED-WORLD": 65,
    }
    if dict(unit_counts) != expected:
        fail(f"coordinate unit counts changed: {unit_counts}")
    required = (
        "raw_body_long_axis_unsigned_deg", "axis_reliability", "reference_long_axis_px",
        "reference_short_axis_px", "raw_radar_direction_body_u", "raw_radar_direction_body_v",
        "raw_relative_observation_angle_deg_mod180", "raw_body_boundary_missing_fraction",
        "raw_body_registration_status", "canonical_field_bundle_path", "gt_information_debt",
    )
    if any(any(not row[field] for field in required) for row in frames):
        fail("coordinate frame requirement missing")
    outlier = [row for row in frames if row["research_unit_id"] == "S0MV-GM_RM017-PV002-SEG02" and row["sar_frame_index"] == "310"]
    if len(outlier) != 1 or "GT_PRECISION_DEPENDENT" not in outlier[0]["gt_information_debt"]:
        fail("PV002 frame 310 GT precision debt missing")
    for row in frames:
        bundle = Path(row["canonical_field_bundle_path"])
        if not bundle.exists():
            fail(f"missing canonical field bundle: {bundle}")
        try:
            bundle.relative_to(REPO_ROOT)
            fail(f"temporary array bundle inside Git worktree: {bundle}")
        except ValueError:
            pass

    competition = read_csv(COMPETITION)
    if len(competition) != 25 or any(row["review_status"] != "directly_reviewed_complete" for row in competition):
        fail("coordinate competition count/review status invalid")
    if any(row["automatic_attribution_label"] != "UNASSIGNED_REQUIRES_DIRECT_VISUAL_REVIEW" for row in competition):
        fail("automatic attribution winner leaked into coordinate competition")
    background_world = next(row for row in competition if row["research_unit_id"] == "S1L-BG-0011-TRAJECTORY-ON-FIXED-WORLD" and row["representation"] == "world")
    background_body = next(row for row in competition if row["research_unit_id"] == "S1L-BG-0011-TRAJECTORY-ON-FIXED-WORLD" and row["representation"] == "smoothed_body")
    if parse_float(background_world["nonadjacent_similar_view_ncc_median"]) <= parse_float(background_body["nonadjacent_similar_view_ncc_median"]):
        fail("fixed background no longer shows world-coordinate advantage")

    casebook = read_csv(CASEBOOK)
    if len(casebook) != 15 or any(row["review_status"] != "directly_reviewed_complete" for row in casebook):
        fail("minimum casebook count/review invalid")
    for row in casebook:
        path = Path(row["artifact_path"])
        if not path.exists():
            fail(f"missing minimum-casebook visual artifact: {path}")
        try:
            path.relative_to(REPO_ROOT)
            fail(f"minimum-casebook visual inside Git worktree: {path}")
        except ValueError:
            pass
    reviews = read_csv(CASE_REVIEWS)
    if len(reviews) != 5 or any(row["review_status"] != "directly_reviewed_complete" for row in reviews):
        fail("minimum case reviews incomplete")


def validate_perturbation_outputs() -> None:
    rows = read_csv(SURFACES)
    if len(rows) != 495:
        fail(f"expected 495 perturbation rows, got {len(rows)}")
    if any(row["review_status"] != "directly_reviewed_complete" for row in rows):
        fail("perturbation review status incomplete")
    if any(row["automatic_winner"] != "UNASSIGNED_NO_RANKING" for row in rows):
        fail("automatic perturbation winner leaked")
    if any(field.lower() in {"gt_iou", "iou_rank", "candidate_rank", "selector_score"} for field in rows[0]):
        fail("forbidden GT-IoU/ranking field leaked")
    units = Counter(row["research_unit_type"] for row in rows)
    if units != Counter({"vehicle_thread": 330, "trajectory_swap_counterfactual": 110, "fixed_world_background_counterfactual": 55}):
        fail(f"unexpected perturbation unit accounting: {units}")
    baseline_count = sum(row["is_gt_baseline"] == "true" for row in rows)
    if baseline_count != 27:
        fail(f"expected 27 family-specific baseline rows, got {baseline_count}")
    swap = next(
        row for row in rows
        if row["research_unit_id"] == "SWAP-GM_RM017_PV002-TRAJECTORY-AROUND-GM_RM017_PV003"
        and row["anchor_variant"] == "smoothed_gt" and row["perturbation_family"] == "axis_rotation"
        and row["rotation_delta_deg"] == "0.000000"
    )
    if parse_float(swap["adjacent_ncc_median"]) < 0.80 or parse_float(swap["nonadjacent_similar_view_ncc_median"]) < 0.50:
        fail("trajectory-swap counterfactual no longer reproduces high coherence")

    visuals = read_csv(SURFACE_CASEBOOK)
    if len(visuals) != 30 or any(row["review_status"] != "directly_reviewed_complete" for row in visuals):
        fail("perturbation visual count/review invalid")
    reviews = read_csv(SURFACE_REVIEWS)
    if len(reviews) != 6 or any(row["review_status"] != "directly_reviewed_complete" for row in reviews):
        fail("perturbation direct reviews incomplete")
    for row in visuals:
        path = Path(row["artifact_path"])
        if not path.exists():
            fail(f"missing visual artifact: {path}")
        try:
            path.relative_to(REPO_ROOT)
            fail(f"temporary visual inside Git worktree: {path}")
        except ValueError:
            pass


def validate_report_replay_and_git() -> None:
    text = FINAL_REPORT.read_text(encoding="utf-8")
    required = (
        "S1L_BODY_SUPPORT_ATTRIBUTION_NOT_READY", "S1-D allowed", "Automatic annotation allowed",
        "GT 零点没有形成共同盆地", "轨迹交换", "潜在车体支撑",
    )
    if any(item not in text for item in required):
        fail("final report missing required decision language")
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    if replay.get("status") != "PASS" or replay.get("changed_paths"):
        fail("body-support fixed-input replay did not pass")
    tracked_media = git("ls-files", "--", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.mp4", "*.avi", "*.npy", "*.npz", "*.zip")
    new_tracked_media = [line for line in tracked_media.splitlines() if line.startswith(("manifests/oty2/oty2_s1l_body_support", "reports/oty2/oty2_s1l_body_support"))]
    if new_tracked_media:
        fail(f"temporary media/array/archive tracked: {new_tracked_media}")
    diff_check = subprocess.run(["git", "diff", "--check", BASE_HEAD], cwd=REPO_ROOT, text=True, capture_output=True)
    if diff_check.returncode:
        fail(f"git diff --check failed: {diff_check.stdout}{diff_check.stderr}")


def main() -> int:
    validate_scope()
    validate_coordinate_outputs()
    validate_perturbation_outputs()
    validate_report_replay_and_git()
    print("S1L_BODY_SUPPORT_ATTRIBUTION_VALIDATOR_PASS")
    print(json.dumps({
        "stage_state": "S1L_BODY_SUPPORT_ATTRIBUTION_NOT_READY",
        "coordinate_frame_rows": 291,
        "coordinate_competition_rows": 25,
        "perturbation_rows": 495,
        "minimum_visuals": 15,
        "perturbation_visuals": 30,
        "s1d_allowed": False,
        "automatic_annotation_allowed": False,
        "latent_body_support_reconstruction_run": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
