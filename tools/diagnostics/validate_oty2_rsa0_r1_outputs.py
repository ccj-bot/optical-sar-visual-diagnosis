#!/usr/bin/env python3
from __future__ import annotations

"""Validate RSA0 R1 free-geometry atlas and continuous temporal reaudit outputs."""

from pathlib import Path

from oty2_s1x_common import MANIFEST_DIR, REPORT_DIR, REPO_ROOT, read_csv, require, sha256_file, verify_git_gate, write_json


EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "206fe5f5f587fec711df8d1856fbce925817d940"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_r1_validation_summary_20260717.json"


def main() -> None:
    git_state = verify_git_gate(EXPECTED_BRANCH, EXPECTED_START_HEAD)
    required = [
        REPO_ROOT / "configs" / "oty2" / "oty2_rsa0_r1_free_geometry_atlas.json",
        REPO_ROOT / "docs" / "OTY2_RSA0_R1_TEMPLATE_ATLAS_CORRECTION_ADDENDUM.md",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_frames_v1.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_regions_v1.csv",
        MANIFEST_DIR / "oty2_rsa0_response_skeletons_v1.csv",
        MANIFEST_DIR / "oty2_rsa0_background_controls_v1.csv",
        MANIFEST_DIR / "oty2_rsa0_r1_atlas_consistency_audit.csv",
        MANIFEST_DIR / "oty2_rsa0_r1_representation_channel_metrics.csv",
        MANIFEST_DIR / "oty2_rsa0_r1_coordinate_family_summary.csv",
        MANIFEST_DIR / "oty2_rsa0_r1_proxy_drift.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest_v1.csv",
        REPORT_DIR / "oty2_rsa0_response_atlas_direct_visual_review_v1_20260717.md",
        REPORT_DIR / "oty2_rsa0_r1_representation_reaudit_20260717.md",
        REPORT_DIR / "oty2_rsa0_r1_summary_20260717.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    require(not missing, f"missing R1 required files: {missing}")

    frames = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_frames_v1.csv")
    regions = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_regions_v1.csv")
    skeletons = read_csv(MANIFEST_DIR / "oty2_rsa0_response_skeletons_v1.csv")
    background = read_csv(MANIFEST_DIR / "oty2_rsa0_background_controls_v1.csv")
    consistency = read_csv(MANIFEST_DIR / "oty2_rsa0_r1_atlas_consistency_audit.csv")
    metrics = read_csv(MANIFEST_DIR / "oty2_rsa0_r1_representation_channel_metrics.csv")
    family = read_csv(MANIFEST_DIR / "oty2_rsa0_r1_coordinate_family_summary.csv")
    drift = read_csv(MANIFEST_DIR / "oty2_rsa0_r1_proxy_drift.csv")
    freeze = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest_v1.csv")

    require(len(frames) == 10, "R1 frame count must be 10")
    require(len(skeletons) == 20, "R1 skeleton+seed rows must be 20")
    require(len(background) == 30, "R1 background control rows must be 30")
    require(len(consistency) == 2, "R1 consistency audit must have one row per case")
    require(len(metrics) >= 600, "R1 metrics unexpectedly small")
    require(len(family) >= 100, "R1 coordinate-family summary unexpectedly small")
    require(len(drift) == 10, "R1 proxy drift must have one row per keyframe")

    main_skeletons = [row for row in skeletons if row["label"] == "MAIN_RESPONSE_SKELETON"]
    require(len({row["length_px"] for row in main_skeletons}) > 5, "R1 skeleton lengths are still too identical")
    require(len({row["point_count"] for row in main_skeletons}) > 1, "R1 skeleton point counts are still too identical")
    definite_areas = [row["area_px2"] for row in regions if row["label"] == "DEFINITE_TARGET_RESPONSE"]
    unresolved_areas = [row["area_px2"] for row in regions if row["label"] == "UNRESOLVED"]
    require(len(set(definite_areas)) > 5, "R1 definite areas are still too identical")
    require(len(set(unresolved_areas)) > 5, "R1 unresolved areas are still too identical")
    require(all(row["decision"] == "PASS_free_geometry_not_highly_identical" for row in consistency), "R1 consistency audit did not pass")
    require({"SAR_DISPLAY_WORLD_STABILIZED", "GT_CONDITIONED_RESEARCH_ORACLE", "OPTICAL_PROXY_CONDITIONED"}.issubset({row["coordinate_family"] for row in metrics}), "missing required coordinate family")
    require(any(row["channel"] == "temporal_adjacent_positive_change_tminus1_to_t" for row in metrics), "missing adjacent positive temporal channel")
    require(any(row["channel"] == "multiscale_hessian_bright_ridge" for row in metrics), "missing Hessian ridge channel")
    require(any(row["channel"] == "structure_tensor_orientation_coherence" for row in metrics), "missing structure tensor channel")
    require(all("winner" not in row["score_interpretation"] or row["score_interpretation"] == "skeleton_primary_channel_diagnostic_not_weighted_winner" for row in metrics), "metric interpretation boundary drift")

    for row in freeze:
        path = Path(row["path"])
        require(path.is_file(), f"freeze path missing: {path}")
        require(sha256_file(path) == row["sha256"], f"freeze hash mismatch: {path}")

    report_text = (REPORT_DIR / "oty2_rsa0_r1_representation_reaudit_20260717.md").read_text(encoding="utf-8")
    for phrase in [
        "not enter seed propagation",
        "GT-oracle and optical-proxy results must not be merged",
        "Not yet as an automatic propagation/training stage",
    ]:
        require(phrase in report_text, f"missing boundary phrase: {phrase}")

    write_json(SUMMARY_JSON, {
        "status": "PASS",
        "git": git_state,
        "frames": len(frames),
        "regions": len(regions),
        "skeletons": len(skeletons),
        "background_controls": len(background),
        "metrics": len(metrics),
        "coordinate_family_summary": len(family),
        "proxy_drift": len(drift),
        "freeze_entries": len(freeze),
        "boundary": "validated_r1_free_geometry_continuous_temporal_reaudit_no_propagation_no_training",
    })


if __name__ == "__main__":
    main()
