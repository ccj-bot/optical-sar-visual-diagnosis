#!/usr/bin/env python3
from __future__ import annotations

"""Validate the frozen S1-L continuous SAR structure audit."""

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
OUTPUT_ROOT = Path(r"D:\profile\research\workspace\output\oty2_s1l_continuous_sar_structure_20260715")
BASE_HEAD = "32db9108c45e44e0c7d438e91bdae5d30d697e36"

FROZEN = MANIFEST_DIR / "oty2_s1l_frozen_input_segments.csv"
FIELDS = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
OBS = MANIFEST_DIR / "oty2_s1l_structure_observations.csv"
REL = MANIFEST_DIR / "oty2_s1l_structure_relations.csv"
EVENTS = MANIFEST_DIR / "oty2_s1l_temporal_structure_events.csv"
AUDIT = MANIFEST_DIR / "oty2_s1l_artifact_counterfactual_audit.csv"
BACKGROUND = MANIFEST_DIR / "oty2_s1l_background_counterfactuals.csv"
EVAL = MANIFEST_DIR / "oty2_s1l_mechanism_evaluation.csv"
REPORT = REPORT_DIR / "oty2_s1l_continuous_sar_structure_and_artifact_control_20260715.md"
SUMMARY = OUTPUT_ROOT / "s1l_summary.json"
VISUAL = OUTPUT_ROOT / "s1l_visual_manifest.csv"
REPLAY = OUTPUT_ROOT / "s1l_replay_check.json"

PROTECTED_PATHS = (
    "docs/OTY2_RESEARCH_ROUTE_RESET_RECORD_20260713.md",
    "docs/OTY2_S0_OPTICAL_TO_SAR_AZIMUTH_MAPPING_CONTRACT.md",
    "docs/OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md",
    "docs/OTY2_S0_SAR_GT_STRUCTURE_FOUNDATION_PROTOCOL.md",
    "docs/OTY2_S0MV_S1L_INPUT_SEMANTICS_AND_VISUALIZATION_PROTOCOL.md",
    "manifests/oty2/oty2_p1e_canonical_optical_vehicle_registry.csv",
    "manifests/oty2/oty2_p1e_identity_benchmark_roles.csv",
    "manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv",
    "manifests/oty2/oty2_s0_canonical_vehicle_sar_gt_threads.csv",
    "manifests/oty2/oty2_s0_imaging_valid_mask_parameters.json",
    "manifests/oty2/oty2_s0_optical_to_sar_azimuth_mapping_audit.csv",
    "manifests/oty2/oty2_s0_sar_coordinate_contract.csv",
    "manifests/oty2/oty2_s0_sar_golden_vehicle_threads.csv",
    "manifests/oty2/oty2_s0_sar_gray_pseudocolor_lineage.csv",
    "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv",
    "manifests/oty2/oty2_s0_sar_mask_contract.csv",
    "manifests/oty2/oty2_s0m_azimuth_corridor_audit.csv",
    "manifests/oty2/oty2_s0m_imaging_valid_mask_verification.csv",
    "manifests/oty2/oty2_s0m_mapping_anchor_eligibility_audit.csv",
    "manifests/oty2/oty2_s0m_mapping_subset_metrics.csv",
    "manifests/oty2/oty2_s0m_pose_proxy_bias_audit.csv",
    "manifests/oty2/oty2_s0m_s1l_frame_eligibility_ledger.csv",
    "manifests/oty2/oty2_s0mv_s1l_preselection_semantic_audit.csv",
    "manifests/oty2/oty2_s0mv_all_gt_s1l_eligibility.csv",
    "manifests/oty2/oty2_s0mv_s1l_continuous_segments.csv",
    "manifests/oty2/oty2_s0mv_visualization_manifest.csv",
    "reports/oty2/oty2_s0_sar_gt_structure_foundation_audit_20260715.md",
    "reports/oty2/oty2_s0mv_s1l_input_semantics_and_visualization_20260715.md",
    "tools/diagnostics/run_oty2_s0_sar_gt_structure_foundation_audit.py",
    "tools/diagnostics/run_oty2_s0m_mask_anchor_pose_mapping_audit.py",
    "tools/diagnostics/run_oty2_s0mv_s1l_input_semantics_visualization.py",
    "tools/diagnostics/validate_oty2_s0_sar_foundation_outputs.py",
    "tools/diagnostics/validate_oty2_s0m_mask_anchor_pose_mapping_outputs.py",
    "tools/diagnostics/validate_oty2_s0mv_outputs.py",
)

EXPECTED_A = {
    "S0MV-GM_RM011-PV001-SEG01": (36, 60),
    "S0MV-GM_RM011-PV002-SEG01": (7, 7),
    "S0MV-GM_RM017-PV002-SEG02": (65, 65),
    "S0MV-GM_RM017-PV003-SEG01": (67, 67),
    "S0MV-GM_RM017-PV004-SEG01": (58, 58),
    "S0MV-GM_RM019-PV001-SEG01": (3, 3),
}
ALLOWED_EVENTS = {
    "stable_persistence", "global_motion_consistent", "local_relative_shift", "strength_increase",
    "strength_decrease", "split", "merge", "birth", "death", "dominant_component_switch",
    "unresolved_correspondence",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        fail(f"missing required output: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return digest.hexdigest()


def validate_protected_history() -> None:
    git("cat-file", "-e", f"{BASE_HEAD}^{{commit}}")
    changed = git("diff", "--name-only", BASE_HEAD, "--", *PROTECTED_PATHS)
    if changed:
        fail(f"protected S0/S0-M/S0-MV/P1-E files changed from {BASE_HEAD}: {changed}")


def validate_frozen_inputs() -> list[dict[str, str]]:
    rows = read_csv(FROZEN)
    if len(rows) != 31:
        fail(f"frozen input must contain 31 A/B/C segments, got {len(rows)}")
    tier_counts = Counter(row["input_tier"] for row in rows)
    if tier_counts != Counter({"C": 14, "B": 11, "A": 6}):
        fail(f"unexpected tier counts: {tier_counts}")
    if sum(int(row["source_gt_row_count"]) for row in rows) != 298:
        fail("all 298 structure-eligible GT rows must be consumed")
    if sum(int(row["source_gt_row_count"]) for row in rows if row["input_tier"] == "A") != 260:
        fail("A tier must consume all 260 temporal-eligible GT rows")
    if sum(int(row["unique_eligible_frame_count"]) for row in rows) != 274:
        fail("expected 274 unique frame-level response fields")
    if sum(int(row["unique_eligible_frame_count"]) for row in rows if row["input_tier"] == "A") != 236:
        fail("expected 236 unique A-tier frame positions")
    actual_a = {row["segment_id"]: (int(row["unique_eligible_frame_count"]), int(row["source_gt_row_count"])) for row in rows if row["input_tier"] == "A"}
    if actual_a != EXPECTED_A:
        fail(f"formal A segments changed: {actual_a}")
    if any("candidate" in row["intended_usage"].lower() for row in rows):
        fail("candidate terminology leaked into formal S1-L input usage")
    return rows


def validate_local_fields(frozen: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = read_csv(FIELDS)
    if len(rows) != 274 or len({row["response_field_id"] for row in rows}) != 274:
        fail("local response fields must be one per 274 unique scene/vehicle/frame positions")
    if sum(int(row["source_gt_count"]) for row in rows) != 298:
        fail("local fields must retain all 298 source GT rows")
    if any(parse_bool(row["gt_is_vehicle_response_mask"]) for row in rows):
        fail("GT must never be declared a vehicle-response mask")
    if max(float(row["coordinate_inverse_error_px"]) for row in rows) > 1e-5:
        fail("global/local coordinate inversion exceeds tolerance")
    if any(not row["raw_image_sha256"] or len(row["raw_image_sha256"]) != 64 for row in rows):
        fail("raw-image lineage hash missing")
    if any(row["lineage_status"] != "INDEX_ALIGNED_DISPLAY_DERIVATION_SUPPORTED" for row in rows):
        fail("unexpected grayscale lineage status")
    return rows


def validate_structures() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    observations = read_csv(OBS)
    relations = read_csv(REL)
    if not observations:
        fail("no structure observations generated")
    forbidden_headers = {name for name in observations[0] if any(token in name.lower() for token in ("candidate_bbox", "selector", "ranking", "final_box"))}
    if forbidden_headers:
        fail(f"forbidden output fields present: {forbidden_headers}")
    if not any(parse_bool(row["major_temporal_eligible"]) for row in observations):
        fail("no multi-threshold/cross-normalization stable observations")
    if any(int(row["threshold_persistence_count"]) not in {1, 2, 3} for row in observations):
        fail("invalid threshold persistence count")
    if any(int(row["normalization_persistence_count"]) not in {1, 2, 3} for row in observations):
        fail("invalid normalization persistence count")
    if not relations:
        fail("no spatial structure relations generated")
    numeric_fields = ("global_distance_px", "radial_delta_px", "tangential_delta_px", "orientation_difference_deg")
    for row in relations:
        for field in numeric_fields:
            float(row[field])
    return observations, relations


def validate_events_and_audits() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    events = read_csv(EVENTS)
    audits = read_csv(AUDIT)
    if not events:
        fail("no temporal events generated")
    if set(row["event_type"] for row in events) - ALLOWED_EVENTS:
        fail("event type outside frozen vocabulary")
    if any(row["input_tier"] not in {"A", "B"} for row in events):
        fail("C-tier rows must not produce temporal events")
    by_event = Counter(row["temporal_event_id"] for row in audits)
    if set(by_event) != {row["temporal_event_id"] for row in events} or any(count != 4 for count in by_event.values()):
        fail("every event must have exactly four counterfactual audit rows")
    required_audits = {"gt_jitter_counterfactual", "crop_motion_counterfactual", "threshold_counterfactual", "background_counterfactual_link"}
    audit_types = defaultdict(set)
    for row in audits:
        audit_types[row["temporal_event_id"]].add(row["audit_type"])
    if any(types != required_audits for types in audit_types.values()):
        fail("counterfactual audit family incomplete")
    return events, audits


def validate_backgrounds_and_evaluation(frozen: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    backgrounds = read_csv(BACKGROUND)
    evaluations = read_csv(EVAL)
    if len(backgrounds) != 16:
        fail(f"expected 16 background pseudo-threads, got {len(backgrounds)}")
    required_types = {"same_range_neighbor", "same_azimuth_neighbor", "fixed_strong_linear_background", "trajectory_shifted_background"}
    by_segment = defaultdict(set)
    for row in backgrounds:
        by_segment[row["source_segment_id"]].add(row["background_type"])
        if row["review_status"] != "directly_reviewed_complete":
            fail("background pseudo-thread review incomplete")
    development_a = {row["segment_id"] for row in frozen if row["input_tier"] == "A" and row["benchmark_role"] == "development"}
    if set(by_segment) != development_a or any(types != required_types for types in by_segment.values()):
        fail("background pseudo-thread coverage incomplete")
    if len(evaluations) != len(frozen):
        fail("mechanism evaluation must cover every frozen A/B/C segment")
    if any(row["review_status"] != "directly_reviewed_complete" for row in evaluations):
        fail("mechanism evaluation review incomplete")
    heldout_a = [row for row in evaluations if row["input_tier"] == "A" and row["benchmark_role"] == "heldout_validation"]
    if len(heldout_a) != 2:
        fail("expected exactly two formal heldout A-tier vehicles")
    return backgrounds, evaluations


def validate_visuals_and_replay() -> dict[str, Any]:
    visual = read_csv(VISUAL)
    if not visual or any(row["review_status"] != "directly_reviewed_complete" for row in visual):
        fail("visual review manifest is incomplete")
    for row in visual:
        path = Path(row["artifact_path"])
        if not path.exists():
            fail(f"missing temporary visual artifact: {path}")
        try:
            path.relative_to(REPO_ROOT)
            fail(f"temporary visual artifact is inside Git worktree: {path}")
        except ValueError:
            pass
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    if replay.get("status") != "PASS":
        fail(f"fixed-input replay did not pass: {replay.get('status')}")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary.get("review_status") != "directly_reviewed_complete" or summary.get("replay_status") != "PASS":
        fail("summary review/replay status incomplete")
    if summary.get("automatic_annotation_allowed") is not False:
        fail("automatic annotation must remain forbidden")
    if summary.get("stage_state") not in {
        "S1L_CONTINUOUS_STRUCTURE_READY", "S1L_CONTINUOUS_STRUCTURE_PARTIALLY_READY", "S1L_CONTINUOUS_STRUCTURE_BLOCKED"
    }:
        fail("invalid S1-L stage state")
    report_text = REPORT.read_text(encoding="utf-8")
    if summary["stage_state"] not in report_text or "Automatic annotation allowed: `false`" not in report_text:
        fail("report decision does not match summary")
    return summary


def validate_git_and_size() -> None:
    tracked_images = git("ls-files", "--", "*.png", "*.jpg", "*.jpeg", "*.mp4", "*.avi", "*.npy", "*.npz")
    staged_images = git("diff", "--cached", "--name-only", "--", "*.png", "*.jpg", "*.jpeg", "*.mp4", "*.avi", "*.npy", "*.npz")
    if staged_images:
        fail(f"temporary image/video/array staged: {staged_images}")
    new_outputs = (FROZEN, FIELDS, OBS, REL, EVENTS, AUDIT, BACKGROUND, EVAL, REPORT)
    oversized = [f"{path.name}:{path.stat().st_size}" for path in new_outputs if path.stat().st_size > 20 * 1024 * 1024]
    if oversized:
        fail(f"unexpectedly large formal output: {oversized}")
    diff_check = subprocess.run(["git", "diff", "--check"], cwd=REPO_ROOT, text=True, capture_output=True)
    if diff_check.returncode:
        fail(f"git diff --check failed: {diff_check.stdout}{diff_check.stderr}")


def main() -> int:
    validate_protected_history()
    frozen = validate_frozen_inputs()
    validate_local_fields(frozen)
    validate_structures()
    validate_events_and_audits()
    validate_backgrounds_and_evaluation(frozen)
    summary = validate_visuals_and_replay()
    validate_git_and_size()
    print("S1L_VALIDATOR_PASS")
    print(json.dumps({
        "stage_state": summary["stage_state"],
        "source_gt_rows": summary["source_gt_rows"],
        "local_response_field_count": summary["local_response_field_count"],
        "structure_observation_count": summary["structure_observation_count"],
        "relation_count": summary["relation_count"],
        "temporal_event_count": summary["temporal_event_count"],
        "background_thread_count": summary["background_thread_count"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
