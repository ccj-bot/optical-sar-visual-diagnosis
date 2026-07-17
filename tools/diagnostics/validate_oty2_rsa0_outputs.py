#!/usr/bin/env python3
from __future__ import annotations

"""Validate RSA0 implementation artifacts and boundaries."""

from pathlib import Path

from oty2_s1x_common import MANIFEST_DIR, REPORT_DIR, REPO_ROOT, read_csv, require, sha256_file, verify_git_gate, write_json


EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "0f1655546ea402857ab054421067f1bf075c4c20"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_validation_summary_20260717.json"


def main() -> None:
    git_state = verify_git_gate(EXPECTED_BRANCH, EXPECTED_START_HEAD)
    required = [
        REPO_ROOT / "configs" / "oty2" / "oty2_rsa0_short_window_inventory.json",
        REPO_ROOT / "configs" / "oty2" / "oty2_rsa0_visual_review_pack.json",
        REPO_ROOT / "configs" / "oty2" / "oty2_rsa0_response_atlas.json",
        MANIFEST_DIR / "oty2_rsa0_short_window_inventory.csv",
        MANIFEST_DIR / "oty2_rsa0_visual_review_pack_manifest.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_regions.csv",
        MANIFEST_DIR / "oty2_rsa0_response_skeletons.csv",
        MANIFEST_DIR / "oty2_rsa0_background_controls.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest.csv",
        MANIFEST_DIR / "oty2_rsa0_representation_channel_metrics.csv",
        MANIFEST_DIR / "oty2_rsa0_representation_failure_modes.csv",
        REPORT_DIR / "oty2_rsa0_response_atlas_direct_visual_review_20260717.md",
        REPORT_DIR / "oty2_rsa0_representation_diagnosis_20260717.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    require(not missing, f"missing required files: {missing}")

    inventory = read_csv(MANIFEST_DIR / "oty2_rsa0_short_window_inventory.csv")
    visual = read_csv(MANIFEST_DIR / "oty2_rsa0_visual_review_pack_manifest.csv")
    frames = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv")
    regions = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_regions.csv")
    skeletons = read_csv(MANIFEST_DIR / "oty2_rsa0_response_skeletons.csv")
    background = read_csv(MANIFEST_DIR / "oty2_rsa0_background_controls.csv")
    freeze = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest.csv")
    metrics = read_csv(MANIFEST_DIR / "oty2_rsa0_representation_channel_metrics.csv")
    failures = read_csv(MANIFEST_DIR / "oty2_rsa0_representation_failure_modes.csv")

    require(len(inventory) == 6, "unexpected inventory row count")
    require(len(visual) == 24, "unexpected visual artifact count")
    require(len(frames) == 10, "unexpected atlas frame count")
    require(len(regions) == 50, "unexpected region count")
    require(len(skeletons) == 20, "unexpected skeleton count")
    require(len(background) == 20, "unexpected background count")
    require(len(metrics) == 150, "unexpected metric count")
    require(len(failures) == 150, "unexpected failure count")
    require(any(row["decision"] == "mapping_reference_debt_pending_direct_review" for row in inventory), "missing GM_RM019 debt row")
    require(all(row["score_interpretation"] == "independent_channel_metric_not_weighted_winner" for row in metrics), "metric score interpretation drift")

    freeze_paths = [Path(row["path"]) for row in freeze]
    require(all(path.is_file() for path in freeze_paths), "freeze manifest references missing file")
    require(all(sha256_file(Path(row["path"])) == row["sha256"] for row in freeze), "freeze manifest hash mismatch")

    report_text = (REPORT_DIR / "oty2_rsa0_representation_diagnosis_20260717.md").read_text(encoding="utf-8").lower()
    require("weighted scores or winners" in report_text, "missing no-winner boundary")
    require("whole gt boxes" in report_text, "missing whole-GT boundary")

    write_json(SUMMARY_JSON, {
        "git": git_state,
        "status": "PASS",
        "inventory_rows": len(inventory),
        "visual_artifacts": len(visual),
        "atlas_frames": len(frames),
        "regions": len(regions),
        "skeletons": len(skeletons),
        "background_controls": len(background),
        "freeze_entries": len(freeze),
        "metrics": len(metrics),
        "failures": len(failures),
        "boundary": "validated_no_candidate_bank_no_weighted_winner_no_final_box",
    })


if __name__ == "__main__":
    main()
