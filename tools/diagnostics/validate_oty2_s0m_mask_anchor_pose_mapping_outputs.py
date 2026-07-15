#!/usr/bin/env python3
from __future__ import annotations

"""Validate deterministic S0-M mask, eligibility, mapping, and S1-L ledgers."""

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SUMMARY_PATH = REPORT_DIR / "oty2_s0m_mask_anchor_pose_mapping_summary.json"
SCENES = {"GM_RM011", "GM_RM017", "GM_RM019"}
ALLOWED_ELIGIBILITY = {
    "calibration_gold", "calibration_usable", "heldout_gold", "heldout_usable",
    "mask_clipped_diagnostic", "pose_or_geometry_diagnostic", "identity_conflict", "exclude",
}
REQUIRED_QUALITY_FIELDS = {
    "gt_valid_mask_fraction", "gt_inside_valid_mask", "gt_touches_valid_mask_boundary",
    "gt_clipped_by_valid_mask", "optical_vehicle_full_visibility",
    "optical_vehicle_boundary_truncation", "optical_pose_group",
    "sar_response_completeness", "mapping_anchor_eligibility", "mapping_exclusion_reason",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def expected_mask() -> tuple[int, float, str]:
    yy, xx = np.indices((1334, 2308), dtype=np.float64)
    radial = np.hypot(xx - 1154.0, yy - 1330.6)
    theta = np.degrees(np.arctan2(xx - 1154.0, 1330.6 - yy))
    mask = (radial <= 1332.7) & (theta >= -90.0) & (theta <= 90.0)
    packed = np.packbits(mask.astype(np.uint8), bitorder="little").tobytes()
    return int(mask.sum()), float(mask.mean()), hashlib.sha256(packed).hexdigest()


def validate_mask() -> None:
    count, fraction, digest = expected_mask()
    params = json.loads((MANIFEST_DIR / "oty2_s0_imaging_valid_mask_parameters.json").read_text(encoding="utf-8"))
    if params["contract"] != "imaging_valid_mask" or params["pixel_count"] != count:
        fail("mask parameter contract or pixel count mismatch")
    if not math.isclose(params["canvas_fraction"], fraction, rel_tol=0.0, abs_tol=1e-15):
        fail("mask canvas fraction mismatch")
    if params["sha256_packbits_little"] != digest:
        fail("mask parameter hash mismatch")
    if params["uniform_metric_grid_claim"] is not False or params["vehicle_mask_claim"] is not False:
        fail("mask contract illegally promotes a metric grid or vehicle mask")

    verification = read_csv(MANIFEST_DIR / "oty2_s0m_imaging_valid_mask_verification.csv")
    if len(verification) != 3 or {row["scene"] for row in verification} != SCENES:
        fail("mask scene verification coverage mismatch")
    for row in verification:
        if row["frame_count"] != "766" or row["all_766_frame_masks_identical"] != "true":
            fail("mask frame invariance mismatch")
        if int(row["mask_pixel_count"]) != count or row["mask_sha256_packbits_little"] != digest:
            fail("mask verification count/hash mismatch")

    contract = read_csv(MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv")
    imaging = [row for row in contract if row["mask_name"] == "imaging_valid_mask"]
    if len(imaging) != 3:
        fail("imaging_valid_mask contract must contain one row per scene")
    for row in imaging:
        if row["confidence_status"] != "FROZEN_DETERMINISTIC_CONTRACT":
            fail("imaging_valid_mask is not frozen")
        if row["content_hash_or_formula_hash"] != digest or row["all_scene_frame_masks_identical"] != "true":
            fail("imaging_valid_mask contract invariance mismatch")
    names = {row["mask_name"] for row in contract}
    required_names = {
        "imaging_valid_mask", "fixed_black_region_inside_mask", "display_nonzero_mask",
        "gt_box_region", "vehicle_response_mask",
    }
    if not required_names <= names:
        fail(f"mask semantic separation missing: {required_names - names}")


def validate_eligibility() -> tuple[list[dict[str, str]], Counter[str]]:
    quality = read_csv(MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv")
    eligibility = read_csv(MANIFEST_DIR / "oty2_s0m_mapping_anchor_eligibility_audit.csv")
    if len(quality) != 442 or len(eligibility) != 442:
        fail("S0-M quality/eligibility row count must be 442")
    if not REQUIRED_QUALITY_FIELDS <= set(quality[0]):
        fail(f"quality audit missing fields: {REQUIRED_QUALITY_FIELDS - set(quality[0])}")
    if {row["sar_gt_id"] for row in quality} != {row["sar_gt_id"] for row in eligibility}:
        fail("quality and eligibility GT IDs differ")
    statuses = Counter(row["mapping_anchor_eligibility"] for row in eligibility)
    if set(statuses) - ALLOWED_ELIGIBILITY:
        fail(f"illegal eligibility values: {set(statuses) - ALLOWED_ELIGIBILITY}")
    if sum(statuses.values()) != 442:
        fail("eligibility accounting mismatch")
    for row in eligibility:
        if row["eligibility_basis_excludes_mapping_residual"] != "true":
            fail("eligibility was not declared residual-independent")
        reason = row["mapping_exclusion_reason"].lower()
        if "residual" in reason or "error_deg" in reason or "39.439" in reason:
            fail("mapping residual leaked into exclusion reason")
        fraction = float(row["gt_valid_mask_fraction"])
        if not (0.0 <= fraction <= 1.0):
            fail("invalid GT/mask fraction")
        if row["gt_clipped_by_valid_mask"] == "true" and row["mapping_anchor_eligibility"] != "mask_clipped_diagnostic":
            fail("mask-clipped row entered a non-diagnostic eligibility")
    return eligibility, statuses


def validate_extreme_and_mapping(eligibility: list[dict[str, str]]) -> None:
    mapping = read_csv(MANIFEST_DIR / "oty2_s0_optical_to_sar_azimuth_mapping_audit.csv")
    if len(mapping) != 70:
        fail(f"historical mapping anchor count changed: {len(mapping)}")
    extreme = [
        row for row in mapping
        if row["scene"] == "GM_RM019" and row["canonical_vehicle_id"] == "GM_RM019:PV004"
        and row["optical_frame_index"] == "168" and row["sar_frame_index"] == "350"
    ]
    if len(extreme) != 1:
        fail("39.440-degree extreme row missing or duplicated")
    extreme_row = extreme[0]
    if not math.isclose(abs(float(extreme_row["old_linear_center_error_deg"])), 39.439805384, abs_tol=1e-6):
        fail("raw extreme residual changed unexpectedly")
    if extreme_row["mapping_anchor_eligibility"] != "pose_or_geometry_diagnostic":
        fail("raw extreme remained eligible")
    if "direct_optical_review" not in extreme_row["mapping_exclusion_reason"]:
        fail("raw extreme lacks independent optical-completeness evidence")
    if float(extreme_row["old_linear_distance_to_gt_interval_deg"]) != 0.0:
        fail("raw extreme should remain inside the full GT azimuth interval")

    eligible = [row for row in mapping if row["mapping_anchor_eligibility"] in {"calibration_gold", "calibration_usable", "heldout_gold", "heldout_usable"}]
    if len(eligible) != 65:
        fail(f"filtered complete anchor count mismatch: {len(eligible)}")
    dev_vehicles = {row["canonical_vehicle_id"] for row in eligible if row["benchmark_role"] == "development"}
    heldout_vehicles = {row["canonical_vehicle_id"] for row in eligible if row["benchmark_role"] == "heldout_validation"}
    if dev_vehicles != {"GM_RM017:PV002"}:
        fail(f"unexpected complete development vehicles: {dev_vehicles}")
    if heldout_vehicles != {"GM_RM017:PV003", "GM_RM017:PV004"}:
        fail(f"unexpected complete heldout vehicles: {heldout_vehicles}")
    if any(row["vehicle_leave_one_out_status"] != "not_estimable_only_one_development_complete_vehicle" for row in mapping):
        fail("vehicle-LOO insufficiency not preserved")
    if any(row["mapping_status"] != "MAPPING_BLOCKED" for row in mapping):
        fail("mapping status must remain blocked")

    metrics = read_csv(MANIFEST_DIR / "oty2_s0m_mapping_subset_metrics.csv")
    required_subsets = {
        "all_historical_anchors", "mask_inside_complete_vehicle_anchors", "mask_clipped_diagnostic_anchors",
        "optical_partial_or_boundary_anchors", "development_complete_anchors", "heldout_complete_anchors",
        "complete_scene_GM_RM011", "complete_scene_GM_RM017", "complete_scene_GM_RM019",
        "complete_pose_left_side_dominant", "complete_optical_center_region", "complete_optical_edge_region",
    }
    if not required_subsets <= {row["subset"] for row in metrics}:
        fail("mapping subset/scene/pose/image-region coverage incomplete")
    old_raw = next(row for row in metrics if row["subset"] == "all_historical_anchors" and row["model"] == "old_linear")
    old_filtered = next(row for row in metrics if row["subset"] == "mask_inside_complete_vehicle_anchors" and row["model"] == "old_linear")
    if not math.isclose(float(old_raw["center_error_max_deg"]), 39.439805384, abs_tol=1e-6):
        fail("raw max error mismatch")
    if float(old_filtered["center_error_max_deg"]) >= 4.0:
        fail("filtered old-mapping maximum error did not contract below 4 degrees")
    if float(old_raw["prediction_inside_full_gt_interval_fraction"]) != 1.0 or float(old_filtered["prediction_inside_full_gt_interval_fraction"]) != 1.0:
        fail("GT azimuth interval hit-rate mismatch")


def validate_pose_corridor_s1l() -> None:
    pose = read_csv(MANIFEST_DIR / "oty2_s0m_pose_proxy_bias_audit.csv")
    if len(pose) != 65 or {row["optical_pose_group"] for row in pose} != {"left_side_dominant"}:
        fail("complete-anchor pose coverage changed")
    if any("not_sar_gt" not in row["pose_source"] for row in pose):
        fail("pose source is not optical-only")

    corridor = read_csv(MANIFEST_DIR / "oty2_s0m_azimuth_corridor_audit.csv")
    half_widths = {row["half_width_deg"] for row in corridor if row["model"] == "old_linear" and row["group"] == "complete_all"}
    if half_widths != {"0.500", "1.000", "2.000", "3.000", "5.000", "8.000", "10.000", "15.000", "20.000", "40.000"}:
        fail("corridor half-width sweep mismatch")
    old20 = next(row for row in corridor if row["model"] == "old_linear" and row["group"] == "complete_all" and row["half_width_deg"] == "20.000")
    if float(old20["full_gt_interval_coverage_fraction"]) != 1.0:
        fail("old mapping 20-degree corridor no longer covers all complete GT intervals")

    s1l = read_csv(MANIFEST_DIR / "oty2_s0m_s1l_frame_eligibility_ledger.csv")
    if len(s1l) != 442:
        fail("S1-L eligibility ledger row count mismatch")
    if sum(row["selected_for_future_s1l"] == "true" for row in s1l) != 12:
        fail("S1-L candidate selection count mismatch")
    if any(row["selection_status"] != "candidate_only_s1l_not_started" for row in s1l):
        fail("S1-L execution boundary violated")

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary["mapping_status"] != "MAPPING_BLOCKED" or summary["s1l_entry_authorized"] is not False:
        fail("summary mapping/S1-L decision mismatch")
    if summary["center_function_decision"] != "do_not_freeze_new_center_function; retain_old_linear_as_diagnostic_prior_only":
        fail("center-function freeze decision mismatch")
    if not summary["pose_decision"].startswith("no_pose_conditioned_center_correction"):
        fail("pose-conditioned correction was improperly enabled")


def validate_s0m() -> None:
    validate_mask()
    eligibility, _ = validate_eligibility()
    validate_extreme_and_mapping(eligibility)
    validate_pose_corridor_s1l()


def main() -> int:
    validate_s0m()
    print("S0M_VALIDATOR_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
