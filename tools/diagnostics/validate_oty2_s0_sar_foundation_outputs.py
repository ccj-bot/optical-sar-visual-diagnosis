#!/usr/bin/env python3
"""Validate OTY2 S0 SAR foundation outputs and fixed-input replay hashes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from validate_oty2_s0m_mask_anchor_pose_mapping_outputs import validate_s0m


BASE_COMMIT = "1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5"
SCENES = {"GM_RM011", "GM_RM017", "GM_RM019"}
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = REPO_ROOT / "reports" / "oty2"
WORKSPACE_OUTPUT = Path(r"D:\profile\research\workspace\output\oty2_s0_sar_gt_structure_foundation_20260715")
SUMMARY_PATH = WORKSPACE_OUTPUT / "s0_summary.json"
REPLAY_BASELINE = WORKSPACE_OUTPUT / "replay_baseline_formal_hashes.json"

FORMAL_OUTPUTS = (
    DOCS_DIR / "OTY2_S0_SAR_GT_STRUCTURE_FOUNDATION_PROTOCOL.md",
    DOCS_DIR / "OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md",
    DOCS_DIR / "OTY2_S0_OPTICAL_TO_SAR_AZIMUTH_MAPPING_CONTRACT.md",
    MANIFEST_DIR / "oty2_s0_sar_coordinate_contract.csv",
    MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv",
    MANIFEST_DIR / "oty2_s0_sar_gray_pseudocolor_lineage.csv",
    MANIFEST_DIR / "oty2_s0_canonical_vehicle_sar_gt_threads.csv",
    MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv",
    MANIFEST_DIR / "oty2_s0_sar_golden_vehicle_threads.csv",
    MANIFEST_DIR / "oty2_s0_optical_to_sar_azimuth_mapping_audit.csv",
    MANIFEST_DIR / "oty2_s0_imaging_valid_mask_parameters.json",
    MANIFEST_DIR / "oty2_s0m_imaging_valid_mask_verification.csv",
    MANIFEST_DIR / "oty2_s0m_mapping_anchor_eligibility_audit.csv",
    MANIFEST_DIR / "oty2_s0m_mapping_subset_metrics.csv",
    MANIFEST_DIR / "oty2_s0m_pose_proxy_bias_audit.csv",
    MANIFEST_DIR / "oty2_s0m_azimuth_corridor_audit.csv",
    MANIFEST_DIR / "oty2_s0m_s1l_frame_eligibility_ledger.csv",
    REPORTS_DIR / "oty2_s0_sar_gt_structure_foundation_audit_20260715.md",
    REPORTS_DIR / "oty2_s0m_mask_anchor_pose_mapping_summary.json",
)

PROTECTED_INPUTS = (
    "manifests/oty2/oty2_p0_data_asset_manifest.csv",
    "manifests/oty2/oty2_p0_hard_sync_sar_to_optical.csv",
    "manifests/oty2/oty2_p0_hard_sync_optical_to_sar.csv",
    "manifests/oty2/oty2_p1e_canonical_optical_vehicle_registry.csv",
    "manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv",
    "manifests/oty2/oty2_p1e_identity_benchmark_roles.csv",
    "manifests/oty2/oty2_p1e_detection_to_canonical_identity_map.csv",
    "docs/OTY2_RESEARCH_ROUTE_RESET_RECORD_20260713.md",
    "docs/OTY2_DATA_FOUNDATION_AND_GLOBAL_IDENTITY_ROUTE_RESET.md",
    "docs/OTY2_P0_EXIT_AND_P1_ENTRY_DECISION_20260713.md",
    "docs/OTY2_P1E_OPTICAL_IDENTITY_BENCHMARK_AND_OBSERVATION_AUDIT_PROTOCOL.md",
    "reports/oty2/oty2_p0_data_asset_and_hard_sync_audit_20260713.md",
    "reports/oty2/oty2_p1e_optical_identity_benchmark_and_observation_audit_20260714.md",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def formal_hashes() -> dict[str, str]:
    return {str(path.relative_to(REPO_ROOT)).replace("\\", "/"): sha256_file(path) for path in FORMAL_OUTPUTS}


def fan_hash() -> str:
    height, width = 1334, 2308
    center_x, center_y, radius = 1154.0, 1330.6, 1332.7
    yy, xx = np.indices((height, width), dtype=np.float64)
    radial = np.hypot(xx - center_x, yy - center_y)
    theta = np.degrees(np.arctan2(xx - center_x, center_y - yy))
    mask = (radial <= radius) & (theta >= -90.0) & (theta <= 90.0)
    packed = np.packbits(mask.astype(np.uint8), bitorder="little").tobytes()
    return hashlib.sha256(packed).hexdigest()


def validate_files_exist() -> None:
    missing = [str(path) for path in FORMAL_OUTPUTS if not path.exists()]
    if missing:
        fail(f"missing formal outputs: {missing}")
    if not SUMMARY_PATH.exists():
        fail(f"missing summary: {SUMMARY_PATH}")


def validate_coordinate_contract() -> None:
    rows = read_csv(MANIFEST_DIR / "oty2_s0_sar_coordinate_contract.csv")
    if len(rows) != 6:
        fail(f"coordinate row count != 6: {len(rows)}")
    pairs = {(row["scene"], row["sar_asset_type"]) for row in rows}
    expected = {(scene, role) for scene in SCENES for role in ("sar_gray_frame", "sar_pseudocolor_frame")}
    if pairs != expected:
        fail("coordinate scene/asset coverage mismatch")
    for row in rows:
        if row["image_width"] != "2308" or row["image_height"] != "1334":
            fail("coordinate dimensions mismatch")
        if row["x_min_meter"] or row["x_max_meter"] or row["y_min_meter"] or row["y_max_meter"]:
            fail("metric limits must remain blank while grid is unresolved")
        if "BLOCKED" not in row["confidence_status"]:
            fail("coordinate status must preserve metric-grid blocker")


def validate_mask_contract() -> None:
    rows = read_csv(MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv")
    expected_masks = {
        "imaging_valid_mask", "display_nonzero_mask", "fixed_black_region_inside_mask", "fan_geometry_mask",
        "gt_box_region", "gt_valid_intersection_mask", "intensity_threshold_mask", "vehicle_response_mask",
        "registration_valid_mask", "occlusion_or_boundary_missing_mask",
    }
    by_scene: dict[str, set[str]] = defaultdict(set)
    expected_fan_hash = fan_hash()
    for row in rows:
        by_scene[row["scene"]].add(row["mask_name"])
        if row["mask_name"] in {"fan_geometry_mask", "imaging_valid_mask"} and row["content_hash_or_formula_hash"] != expected_fan_hash:
            fail("fixed imaging geometry mask hash is not reproducible")
        if row["mask_name"] == "imaging_valid_mask":
            if row["confidence_status"] != "FROZEN_DETERMINISTIC_CONTRACT":
                fail("imaging_valid_mask must be frozen")
            if row["all_scene_frame_masks_identical"] != "true" or row["verified_frame_count"] != "766":
                fail("imaging_valid_mask frame invariance missing")
        if row["mask_name"] in {"gt_box_region", "vehicle_response_mask"} and row["may_be_used_as_vehicle_mask"] == "true":
            fail(f"illegal vehicle-mask promotion: {row['mask_name']}")
    if set(by_scene) != SCENES:
        fail("mask scene coverage mismatch")
    for scene, names in by_scene.items():
        if names != expected_masks:
            fail(f"mask semantic coverage mismatch for {scene}: {names}")


def validate_lineage() -> None:
    rows = read_csv(MANIFEST_DIR / "oty2_s0_sar_gray_pseudocolor_lineage.csv")
    if len(rows) != 2298:
        fail(f"lineage row count != 2298: {len(rows)}")
    by_scene: dict[str, list[int]] = defaultdict(list)
    gm19_fps = set()
    for row in rows:
        by_scene[row["scene"]].append(int(row["frame_index"]))
        if row["index_aligned"] != "true" or row["dimensions_aligned"] != "true":
            fail("gray/pseudocolor pair misalignment")
        if row["retains_phase"] != "false" or row["adds_independent_physical_observation"] != "false":
            fail("pseudocolor physical semantics violation")
        if float(row["spatial_gradient_alignment"]) < 0.55:
            fail(f"unexpected low gray/pseudocolor structure alignment: {row['scene']} {row['frame_index']}")
        if row["scene"] == "GM_RM019":
            gm19_fps.add(row["pseudocolor_container_fps"])
            if row["authoritative_time_sec"] != row["pseudocolor_inherited_time_sec"]:
                fail("GM_RM019 pseudocolor did not inherit gray time")
    for scene in SCENES:
        if sorted(by_scene[scene]) != list(range(766)):
            fail(f"lineage frame index coverage mismatch for {scene}")
    if not any(value.startswith("48.300063") for value in gm19_fps):
        fail("GM_RM019 container fps conflict was not preserved")


def validate_threads_and_quality() -> None:
    threads = read_csv(MANIFEST_DIR / "oty2_s0_canonical_vehicle_sar_gt_threads.csv")
    quality = read_csv(MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv")
    if len(threads) != 442 or len(quality) != 442:
        fail(f"thread/quality row count mismatch: {len(threads)}/{len(quality)}")
    thread_ids = [row["sar_gt_id"] for row in threads]
    quality_ids = [row["sar_gt_id"] for row in quality]
    if len(set(thread_ids)) != 442 or set(thread_ids) != set(quality_ids):
        fail("SAR GT IDs are not one-to-one across thread and quality manifests")

    registry = read_csv(MANIFEST_DIR / "oty2_p1e_canonical_optical_vehicle_registry.csv")
    roles = read_csv(MANIFEST_DIR / "oty2_p1e_identity_benchmark_roles.csv")
    allowed_ids = {(row["scene"], row["canonical_vehicle_id"]) for row in registry}
    role_map = {(row["scene"], row["canonical_vehicle_id"]): row["benchmark_role"] for row in roles}
    for row in threads:
        canonical = row["canonical_vehicle_id"]
        if canonical:
            key = (row["scene"], canonical)
            if key not in allowed_ids:
                fail(f"unknown canonical vehicle link: {key}")
            if row["benchmark_role"] != role_map[key]:
                fail(f"benchmark role mismatch: {key}")
        if "P0 fixed 24/50" not in row["mapping_basis"]:
            fail("hard-sync basis was not preserved")

    allowed_quality = {"gold", "usable", "diagnostic_only", "identity_or_geometry_conflict", "exclude_from_structure_discovery"}
    if set(row["gt_quality_status"] for row in quality) - allowed_quality:
        fail("illegal GT quality status")
    for row in quality:
        if row["bbox_width_meter"] or row["bbox_height_meter"] or row["center_x_meter"] or row["center_y_meter"]:
            fail("metric GT fields must remain blank")
        if not row["valid_mask_fraction"] or not row["gt_valid_mask_fraction"]:
            fail("deterministic imaging-valid relation is missing")
        if row["validity_basis"] != "deterministic_shared_imaging_valid_mask":
            fail("GT validity basis does not use the frozen imaging mask")
        if row["mapping_anchor_eligibility"] not in {
            "calibration_gold", "calibration_usable", "heldout_gold", "heldout_usable",
            "mask_clipped_diagnostic", "pose_or_geometry_diagnostic", "identity_conflict", "exclude",
        }:
            fail("illegal mapping anchor eligibility")


def validate_vehicle_roles_and_mapping() -> None:
    golden = read_csv(MANIFEST_DIR / "oty2_s0_sar_golden_vehicle_threads.csv")
    if len(golden) != 22:
        fail(f"golden-thread ledger must contain all 22 canonical vehicles: {len(golden)}")
    role_by_vehicle: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in golden:
        role_by_vehicle[(row["scene"], row["canonical_vehicle_id"])].add(row["benchmark_role"])
    if any(len(values) != 1 for values in role_by_vehicle.values()):
        fail("vehicle-level role leakage in golden ledger")

    mapping = read_csv(MANIFEST_DIR / "oty2_s0_optical_to_sar_azimuth_mapping_audit.csv")
    if not mapping:
        fail("mapping audit contains no anchors")
    roles_seen = Counter(row["benchmark_role"] for row in mapping)
    if roles_seen["development"] == 0 or roles_seen["heldout_validation"] == 0:
        fail(f"mapping requires both development and heldout anchors: {roles_seen}")
    for row in mapping:
        if row["mapping_status"] != "MAPPING_BLOCKED":
            fail("mapping status mismatch")
        if row["benchmark_role"] == "heldout_validation" and row["model_fit_membership"] not in {
            "heldout_complete_evaluation_only", "historical_anchor_diagnostic_only"
        }:
            fail("heldout vehicle leaked into mapping fit")
        if row["vehicle_leave_one_out_status"] != "not_estimable_only_one_development_complete_vehicle":
            fail("development vehicle-LOO insufficiency is not explicit")


def validate_protected_inputs() -> None:
    command = ["git", "-C", str(REPO_ROOT), "diff", "--quiet", BASE_COMMIT, "--", *PROTECTED_INPUTS]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        fail("one or more protected P0/P1-E inputs differ from the frozen base")


def validate_scope_and_worktree() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary["stage_status"] != "S0_SAR_FOUNDATION_PARTIALLY_READY" or summary["s1_entry_allowed"] is not False:
        fail("stage status or S1 boundary mismatch")
    for path in summary["input_provenance"]:
        lowered = path.lower().replace("-", "").replace("_", "")
        if "p1f" in lowered:
            fail(f"P1-F input leakage: {path}")
        if "old_work" in path.lower():
            fail(f"old_work runtime dependency: {path}")

    result = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"], check=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        rel = line[3:].strip().strip('"')
        path = REPO_ROOT / rel
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".mp4", ".mat", ".npy", ".npz", ".zip", ".pt", ".pth"}:
            fail(f"temporary/binary artifact entered worktree changes: {rel}")
        if path.exists() and path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            fail(f"changed formal file exceeds 5 MiB: {rel}")


def validate_docs() -> None:
    text = (REPORTS_DIR / "oty2_s0_sar_gt_structure_foundation_audit_20260715.md").read_text(encoding="utf-8")
    required = [
        "S0_SAR_FOUNDATION_PARTIALLY_READY", "MAPPING_BLOCKED", "S1-L entry allowed: `false`",
        "0.03 m/pixel", "does not add a physical observation dimension", "Explicit non-execution",
    ]
    for item in required:
        if item not in text:
            fail(f"main report missing required statement: {item}")
    visual_manifest = json.loads((WORKSPACE_OUTPUT / "visual_review_manifest.json").read_text(encoding="utf-8"))
    if visual_manifest["all_gt_case_count"] != 442:
        fail("visual review does not cover all GT rows")
    for path in visual_manifest["full_stream_contact_sheets"] + visual_manifest["all_gt_case_pages"]:
        if not Path(path).exists():
            fail(f"visual review artifact missing: {path}")


def handle_replay(write_baseline: bool) -> None:
    hashes = formal_hashes()
    if write_baseline:
        REPLAY_BASELINE.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"WROTE_REPLAY_BASELINE {REPLAY_BASELINE}")
        return
    if not REPLAY_BASELINE.exists():
        fail("replay baseline missing; run validator once with --write-replay-baseline")
    baseline = json.loads(REPLAY_BASELINE.read_text(encoding="utf-8"))
    if hashes != baseline:
        changed = sorted(set(hashes) | set(baseline))
        differences = [name for name in changed if hashes.get(name) != baseline.get(name)]
        fail(f"fixed-input replay hash mismatch: {differences}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-replay-baseline", action="store_true")
    args = parser.parse_args()

    validate_files_exist()
    validate_coordinate_contract()
    validate_mask_contract()
    validate_lineage()
    validate_threads_and_quality()
    validate_vehicle_roles_and_mapping()
    validate_s0m()
    validate_protected_inputs()
    validate_scope_and_worktree()
    validate_docs()
    handle_replay(args.write_replay_baseline)
    print("S0_VALIDATOR_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
