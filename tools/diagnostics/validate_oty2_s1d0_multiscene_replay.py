#!/usr/bin/env python3
from __future__ import annotations

"""Validate the bounded OTY2-S1D0 multi-scene lifecycle replay delivery."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oty2_s1d0_common import REPO_ROOT, load_json, read_csv, require, sha256_file, write_json


MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
CONFIG_PATH = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_dynamic_response.json"
EVAL_CONFIG_PATH = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_evaluation.json"
SUMMARY_PATH = REPORT_DIR / "oty2_s1d0_postfreeze_evaluation_summary_20260717.json"
REPORT_PATH = REPORT_DIR / "oty2_s1d0_multiscene_lifecycle_gated_visible_response_dynamics_20260717.md"
OUTPUT_PATH = REPORT_DIR / "oty2_s1d0_multiscene_replay_validation_20260717.json"


def check(condition: bool, message: str, checks: list[dict[str, Any]]) -> None:
    checks.append({"check": message, "passed": bool(condition)})
    require(condition, message)


def validate_freeze(path: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = read_csv(path)
    check(len(rows) == 46, "inference freeze contains exactly 46 artifacts", checks)
    for row in rows:
        artifact = Path(row["path"])
        check(artifact.is_file(), f"frozen artifact exists: {artifact}", checks)
        check(sha256_file(artifact) == row["sha256"], f"frozen artifact hash matches: {artifact}", checks)
        check(row["target_reference_content"] == "false", f"frozen artifact is target-reference-free: {artifact}", checks)
        check(row["frozen_before_visible_response_review"] == "true", f"artifact frozen before reference review: {artifact}", checks)
    return {"row_count": len(rows), "manifest_sha256": sha256_file(path)}


def main() -> None:
    checks: list[dict[str, Any]] = []
    config = load_json(CONFIG_PATH)
    eval_config = load_json(EVAL_CONFIG_PATH)
    summary = load_json(SUMMARY_PATH)

    check(config["version"] == "OTY2-S1D0-dynamic-response-v1.1", "single repaired inference version is v1.1", checks)
    repair = config["single_allowed_minimal_repair"]
    check(len(repair["changes"]) == 3, "single minimal repair records exactly three bounded changes", checks)
    check(repair["response_thresholds_changed"] is False, "repair did not change robust-z response thresholds", checks)
    check(repair["selected_threads_changed"] is False, "repair did not change selected threads", checks)
    prohibitions = config["prohibitions"]
    check(all(prohibitions.values()), "all candidate-ranking-box prohibitions are enabled", checks)

    inventory = read_csv(MANIFEST_DIR / "oty2_s1d0_multiscene_lifecycle_inventory.csv")
    scene_counts = Counter(row["scene"] for row in inventory)
    check(len(inventory) == 22, "inventory covers all 22 canonical vehicles", checks)
    check(scene_counts == Counter({"GM_RM011": 14, "GM_RM017": 4, "GM_RM019": 4}), "inventory scene counts are 14/4/4", checks)
    check(all(row["target_sar_reference_used_for_inventory_or_selection"] == "false" for row in inventory), "inventory and selection do not use target SAR reference", checks)

    roles = read_csv(MANIFEST_DIR / "oty2_s1d0_selected_lifecycle_roles.csv")
    required_roles = {
        "MECHANISM_DISCOVERY",
        "CROSS_SCENE_FROZEN_REPLAY",
        "ENTRY_EXIT_LIFECYCLE_CASE",
        "MULTI_VEHICLE_OR_OCCLUSION_STRESS",
    }
    check({row["role"] for row in roles} == required_roles, "all four frozen lifecycle roles are present", checks)
    check(all(row["target_sar_reference_used_for_selection"] == "false" for row in roles), "role selection is target-reference-free", checks)
    check(all(row["selection_frozen_before_inference"] == "true" for row in roles), "roles were frozen before inference", checks)

    conditions = read_csv(MANIFEST_DIR / "oty2_s1d0_lifecycle_conditions.csv")
    check(len(conditions) == 645, "lifecycle conditions contain 645 identity-frame rows", checks)
    check(sum(row["is_target_identity"] == "true" for row in conditions) == 324, "target cases contain 324 frames", checks)
    check(all(row["target_sar_reference_dependency"] == "false" for row in conditions), "all lifecycle conditions are target-reference-free", checks)
    check(all(row["identity_owner"] == "P1E_OPTICAL_CANONICAL_THREAD" for row in conditions), "optical canonical lifecycle owns every identity", checks)

    for mode in ("causal", "bidirectional"):
        frame_rows = read_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_frame_states.csv")
        check(len(frame_rows) == 324, f"{mode} has 324 frame-state rows", checks)
        check({row["state_mode"] for row in frame_rows} == {mode}, f"{mode} state rows remain separated", checks)
        check(all(row["target_reference_used_for_inference"] == "false" for row in frame_rows), f"{mode} inference uses no target reference", checks)
        check(all(row["candidate_bank_generated"] == "false" for row in frame_rows), f"{mode} generates no candidate bank", checks)
        check(all(row["weighted_score_or_ranking_used"] == "false" for row in frame_rows), f"{mode} uses no score or ranking", checks)
        check(all(row["forced_component_winner"] == "false" for row in frame_rows), f"{mode} forces no component winner", checks)
        check(all(row["unique_box_generated"] == "false" for row in frame_rows), f"{mode} generates no unique box", checks)
        review_rows = read_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_blind_review_manifest.csv")
        check(len(review_rows) == 6, f"{mode} has six directly reviewed blind pages", checks)
        check(all(row["review_status"] == "directly_reviewed_complete" for row in review_rows), f"{mode} blind review is complete", checks)

    freeze_path = REPO_ROOT / eval_config["inference_freeze_manifest"]
    freeze = validate_freeze(freeze_path, checks)
    queue = read_csv(REPO_ROOT / eval_config["reference_review_queue"])
    reference = read_csv(REPO_ROOT / eval_config["visible_response_reference_manifest"])
    check(len(queue) == 8, "visible-response review queue contains eight uniform frames", checks)
    check(all(row["review_status"] == "directly_reviewed_complete" for row in queue), "visible-response queue review is complete", checks)
    check(all(row["inference_freeze_manifest_sha256_before_review"] == freeze["manifest_sha256"] for row in queue), "queue records the pre-review inference freeze hash", checks)
    check({row["review_category"] for row in reference} == {"VISIBLE_MAIN_RESPONSE", "VISIBLE_INTERMITTENT_RESPONSE", "CLEAR_BACKGROUND", "MIXED_OR_UNRESOLVED"}, "reference manifest uses all four permitted categories", checks)
    check(all(row["contains_target_reference"] == "false" for row in reference), "visible-response reference was drawn without target reference", checks)
    check(all(row["used_to_change_inference_rules"] == "false" for row in reference), "visible-response reference did not change inference rules", checks)

    check(summary["recovery_entrance_gate_passed"] is False, "recovery entrance gate is conservatively not passed", checks)
    check(summary["physical_event_interpretation_allowed"] is False, "physical event interpretation remains blocked", checks)
    check(summary["target_reference_used_for_inference"] is False, "evaluation confirms no target-reference inference leakage", checks)
    check(summary["rule_update_from_evaluation"] is False, "evaluation did not update inference rules", checks)
    check(summary["second_repair_performed"] is False, "no second repair was performed", checks)
    check(len(summary["project_questions"]) == 6, "exactly six project-level answers are present", checks)

    visual_rows = read_csv(MANIFEST_DIR / "oty2_s1d0_posthoc_evaluation_visual_manifest.csv")
    check(len(visual_rows) == 2, "two posthoc evaluation pages were generated", checks)
    check(all(row["review_status"] == "directly_reviewed_complete" for row in visual_rows), "posthoc evaluation pages were directly reviewed", checks)
    check(REPORT_PATH.is_file(), "formal six-question report exists", checks)

    s1d0_repo_files = [
        path
        for path in REPO_ROOT.rglob("*s1d0*")
        if path.is_file() and path.suffix.lower() in {".png", ".gif", ".mp4", ".npz"}
    ]
    check(not s1d0_repo_files, "no large S1D0 image or NPZ artifact is stored inside Git", checks)

    result = {
        "version": "OTY2-S1D0-multiscene-replay-validator-v1",
        "validated_utc": datetime.now(timezone.utc).isoformat(),
        "passed": all(row["passed"] for row in checks),
        "check_count": len(checks),
        "checks": checks,
        "inventory_scene_counts": dict(scene_counts),
        "selected_threads": [
            {
                "case_id": row["case_id"],
                "role": row["role"],
                "selection_basis": row["selection_basis"],
            }
            for row in roles
        ],
        "target_gt_entered_inference": False,
        "frozen_rule_modified_after_reference_review": False,
        "single_minimal_repair": repair,
        "project_question_answer_count": len(summary["project_questions"]),
        "recovery_entrance_gate_passed": summary["recovery_entrance_gate_passed"],
        "next_stage_recommendation": "do not tune v1.1 or perform a second repair; reopen only bounded cross-scene mapping calibration and independent visible-response reference work",
    }
    write_json(OUTPUT_PATH, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
