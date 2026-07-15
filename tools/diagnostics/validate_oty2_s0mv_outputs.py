#!/usr/bin/env python3
from __future__ import annotations

"""Validate S0-MV S1-L eligibility semantics and visualization audit outputs."""

import csv
import json
import subprocess
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
OUTPUT_ROOT = Path(
    r"D:\profile\research\workspace\output\oty2_s0mv_s1l_input_semantics_visualization_20260715"
)
BASE_HEAD = "6578488f9ed9a0b5d917302bffc2672699ec717a"

PRESELECTION_PATH = MANIFEST_DIR / "oty2_s0mv_s1l_preselection_semantic_audit.csv"
ALL_GT_PATH = MANIFEST_DIR / "oty2_s0mv_all_gt_s1l_eligibility.csv"
SEGMENTS_PATH = MANIFEST_DIR / "oty2_s0mv_s1l_continuous_segments.csv"
VISUAL_PATH = MANIFEST_DIR / "oty2_s0mv_visualization_manifest.csv"
SUMMARY_PATH = OUTPUT_ROOT / "s0mv_summary.json"

FROZEN_S0_S0M_PATHS = (
    "docs/OTY2_S0_OPTICAL_TO_SAR_AZIMUTH_MAPPING_CONTRACT.md",
    "docs/OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md",
    "docs/OTY2_S0_SAR_GT_STRUCTURE_FOUNDATION_PROTOCOL.md",
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
    "reports/oty2/oty2_s0_sar_gt_structure_foundation_audit_20260715.md",
    "reports/oty2/oty2_s0m_mask_anchor_pose_mapping_summary.json",
    "tools/diagnostics/run_oty2_s0m_mask_anchor_pose_mapping_audit.py",
    "tools/diagnostics/validate_oty2_s0m_mask_anchor_pose_mapping_outputs.py",
)

EXPECTED_QUALITY = {
    "gold": 3,
    "usable": 295,
    "diagnostic_only": 124,
    "identity_or_geometry_conflict": 17,
    "exclude_from_structure_discovery": 3,
}

EXPECTED_DEVELOPMENT_THREADS = {
    "GM_RM011:PV001",
    "GM_RM011:PV002",
    "GM_RM011:PV005",
    "GM_RM011:PV006",
    "GM_RM011:PV007",
    "GM_RM011:PV010",
    "GM_RM017:PV002",
    "GM_RM019:PV001",
}
EXPECTED_HELDOUT_THREADS = {
    "GM_RM011:PV008",
    "GM_RM017:PV003",
    "GM_RM017:PV004",
    "GM_RM019:PV002",
    "GM_RM019:PV004",
}
EXPECTED_ELIGIBLE_SEGMENTS = {
    "S0MV-GM_RM011-PV001-SEG01": (0, 36, 37, 36, 0),
    "S0MV-GM_RM011-PV002-SEG01": (0, 7, 8, 7, 0),
    "S0MV-GM_RM017-PV002-SEG02": (310, 386, 66, 65, 11),
    "S0MV-GM_RM017-PV003-SEG01": (315, 394, 73, 67, 7),
    "S0MV-GM_RM017-PV004-SEG01": (337, 394, 58, 58, 0),
    "S0MV-GM_RM019-PV001-SEG01": (0, 8, 3, 3, 6),
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        fail(f"missing required file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def validate_frozen_inputs() -> None:
    git("cat-file", "-e", f"{BASE_HEAD}^{{commit}}")
    changed = git("diff", "--name-only", BASE_HEAD, "--", *FROZEN_S0_S0M_PATHS)
    if changed:
        fail(f"existing S0/S0-M formal files changed from {BASE_HEAD}: {changed}")


def validate_preselection() -> None:
    rows = read_csv(PRESELECTION_PATH)
    if len(rows) != 12:
        fail(f"preselection row count must be 12, got {len(rows)}")
    if len({row["record_id"] for row in rows}) != 12:
        fail("preselection record IDs are not unique")
    for row in rows:
        if row["source_file"] != "manifests/oty2/oty2_s0m_s1l_frame_eligibility_ledger.csv":
            fail("preselection source file changed")
        if row["source_script"] != "tools/diagnostics/run_oty2_s0m_mask_anchor_pose_mapping_audit.py":
            fail("preselection source script changed")
        if row["source_function"] != "select_s1l_candidates":
            fail("preselection source function changed")
        if row["mapping_anchor_eligible"] != "true" or row["s1l_structure_eligible"] != "true":
            fail("the historical previews no longer reproduce their source eligibility")
        if row["selected_as_preview"] != "true":
            fail("one of the 12 rows is not labelled as a preview")
        if row["selected_as_pilot"] != "false" or row["selected_as_formal_input"] != "false":
            fail("a representative preview was promoted to pilot/formal input")
        if row["semantic_interpretation"] != "representative preview, not the full eligible set":
            fail("preselection semantic interpretation drifted")
        if "mapping-anchor-eligible" not in row["selection_rule"]:
            fail("mapping/structure eligibility conflation is no longer explicit")


def validate_all_gt() -> None:
    rows = read_csv(ALL_GT_PATH)
    if len(rows) != 442:
        fail(f"all-GT ledger must contain 442 rows, got {len(rows)}")
    if Counter(row["gt_quality_status"] for row in rows) != Counter(EXPECTED_QUALITY):
        fail("GT quality accounting changed")
    if sum(bool(row["canonical_vehicle_id"]) for row in rows) != 422:
        fail("canonical-linked row count changed")
    if len({row["canonical_vehicle_id"] for row in rows if row["canonical_vehicle_id"]}) != 17:
        fail("canonical-linked vehicle count changed")
    if sum(row["mapping_anchor_eligible"] == "true" for row in rows) != 65:
        fail("mapping-anchor count changed")
    if sum(row["s1l_structure_frame_eligible"] == "true" for row in rows) != 298:
        fail("S1-L structure-frame eligible count changed")
    if sum(row["s1l_temporal_eligible"] == "true" for row in rows) != 260:
        fail("S1-L temporal eligible count changed")
    if sum(row["belongs_to_preselected_12"] == "true" for row in rows) != 12:
        fail("12-preview membership count changed")
    if any(row["gt_inside_imaging_valid_mask"] != "true" for row in rows):
        fail("an S0-MV GT row is no longer inside imaging_valid_mask")
    if any(row["sar_image_readable"] != "true" for row in rows):
        fail("an S0-MV source SAR image is unreadable")

    structure_mapping = sum(
        row["s1l_structure_frame_eligible"] == "true" and row["mapping_anchor_eligible"] == "true"
        for row in rows
    )
    structure_not_mapping = sum(
        row["s1l_structure_frame_eligible"] == "true" and row["mapping_anchor_eligible"] != "true"
        for row in rows
    )
    mapping_not_structure = sum(
        row["mapping_anchor_eligible"] == "true" and row["s1l_structure_frame_eligible"] != "true"
        for row in rows
    )
    if (structure_mapping, structure_not_mapping, mapping_not_structure) != (65, 233, 0):
        fail("mapping/structure set accounting changed")

    for row in rows:
        eligible = row["s1l_structure_frame_eligible"] == "true"
        if eligible and (
            not row["canonical_vehicle_id"]
            or row["gt_quality_status"] not in {"gold", "usable"}
            or row["gt_inside_imaging_valid_mask"] != "true"
            or row["sar_image_readable"] != "true"
        ):
            fail(f"invalid structure-eligible row: {row['sar_gt_id']}")
        if "mapping" in row["exclusion_reason"].lower() or "optical_vehicle_full_visibility" in row["exclusion_reason"]:
            fail("mapping or optical-completeness leaked into the S1-L structure exclusion rule")


def validate_segments() -> None:
    rows = read_csv(SEGMENTS_PATH)
    if len(rows) != 37:
        fail(f"continuous segment count must be 37, got {len(rows)}")
    if len({row["segment_id"] for row in rows}) != len(rows):
        fail("continuous segment IDs are not unique")
    if any(row["segmentation_rule"] != "split_when_consecutive_unique_gt_frame_gap_gt_5" for row in rows):
        fail("segment split rule changed")

    eligible = {row["segment_id"]: row for row in rows if row["segment_eligibility"] == "true"}
    if set(eligible) != set(EXPECTED_ELIGIBLE_SEGMENTS):
        fail(f"eligible segment set changed: {set(eligible)}")
    for segment_id, expected in EXPECTED_ELIGIBLE_SEGMENTS.items():
        row = eligible[segment_id]
        actual = (
            int(row["sar_frame_start"]),
            int(row["sar_frame_end"]),
            int(row["gt_frame_count"]),
            int(row["eligible_frame_count"]),
            int(row["missing_frame_count"]),
        )
        if actual != expected:
            fail(f"eligible segment geometry/count changed for {segment_id}: {actual}")
    if sum(row["segment_eligibility"] == "true" and row["benchmark_role"] == "development" for row in rows) != 4:
        fail("development eligible segment count changed")
    if sum(row["segment_eligibility"] == "true" and row["benchmark_role"] == "heldout_validation" for row in rows) != 2:
        fail("heldout eligible segment count changed")

    development = {
        row["canonical_vehicle_id"]
        for row in rows
        if row["vehicle_research_role"] == "structure_development"
    }
    heldout = {
        row["canonical_vehicle_id"]
        for row in rows
        if row["vehicle_research_role"] == "structure_heldout_validation"
    }
    if development != EXPECTED_DEVELOPMENT_THREADS or heldout != EXPECTED_HELDOUT_THREADS:
        fail("development/heldout vehicle thread roster changed")


def validate_visualization() -> None:
    rows = read_csv(VISUAL_PATH)
    counts = Counter(row["artifact_type"] for row in rows)
    expected = Counter(
        {
            "vehicle_timeline": 17,
            "preselected_12_context": 12,
            "eligible_continuous_segment_contact": 12,
            "review_overview": 4,
        }
    )
    if counts != expected:
        fail(f"visualization artifact counts changed: {counts}")
    if len(rows) != 45 or any(row["review_status"] != "directly_reviewed_complete" for row in rows):
        fail("visualization direct-review status is incomplete")
    for row in rows:
        path = Path(row["artifact_path"])
        if not path.is_file() or path.suffix.lower() != ".png":
            fail(f"visualization artifact missing or wrong type: {path}")
        try:
            path.relative_to(OUTPUT_ROOT)
        except ValueError as exc:
            raise AssertionError(f"visualization escaped temporary output root: {path}") from exc

    staged = git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    staged_images = [
        path
        for path in staged.splitlines()
        if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".avi"}
    ]
    if staged_images:
        fail(f"temporary image/video artifacts are staged: {staged_images}")


def validate_summary() -> None:
    if not SUMMARY_PATH.is_file():
        fail(f"missing temporary summary: {SUMMARY_PATH}")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    expected = {
        "status": "S0MV_S1L_INPUT_SEMANTICS_CLEAR",
        "primary_semantic_conclusion": "S1L_ELIGIBILITY_WAS_INCORRECTLY_TIED_TO_MAPPING_ANCHORS",
        "preselection_interpretation": "12_FRAMES_ARE_ONLY_REPRESENTATIVE_PREVIEWS",
        "all_gt_rows": 442,
        "gold_usable_rows": 298,
        "mapping_anchor_rows": 65,
        "s1l_structure_frame_eligible_rows": 298,
        "s1l_temporal_eligible_rows": 260,
        "preselected_preview_rows": 12,
        "all_segment_count": 37,
        "eligible_continuous_segment_count": 6,
        "visual_artifact_rows": 45,
        "allow_s1l_input_redesign": True,
        "allow_s1l_structure_extraction": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            fail(f"summary mismatch for {key}: {summary.get(key)!r}")
    if summary.get("visual_review_statuses") != {"directly_reviewed_complete": 45}:
        fail("summary visual review status mismatch")
    expected_threads = EXPECTED_DEVELOPMENT_THREADS | EXPECTED_HELDOUT_THREADS
    if set(summary.get("thread_summary", {})) != expected_threads:
        fail("summary thread keys are not canonical vehicle IDs")


def validate_s0mv() -> None:
    validate_frozen_inputs()
    validate_preselection()
    validate_all_gt()
    validate_segments()
    validate_visualization()
    validate_summary()


def main() -> int:
    validate_s0mv()
    print("S0MV_VALIDATOR_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
