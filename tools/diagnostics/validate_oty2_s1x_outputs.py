#!/usr/bin/env python3
from __future__ import annotations

"""Validate the OTY2-S1X project-level closed loop and its frozen outputs."""

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs" / "oty2"
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOC_DIR = REPO_ROOT / "docs"

EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "fb69df0bd050106a9cad62f2d8cc50e5c6750319"
DISCOVERY = "DISCOVERY_GM_RM017_PV002_330_350"
REPLAY = "REPLAY_GM_RM017_PV003_338_391"
EXPECTED_WINDOWS = {
    DISCOVERY: {
        "role": "discovery",
        "vehicle": "GM_RM017:PV002",
        "frames": set(range(330, 351)),
    },
    REPLAY: {
        "role": "frozen_rule_replay",
        "vehicle": "GM_RM017:PV003",
        "frames": set(range(338, 392)),
    },
}

PREPARATION_CONFIG = CONFIG_DIR / "oty2_s1x_input_preparation.json"
INFERENCE_CONFIG = CONFIG_DIR / "oty2_s1x_joint_temporal_support.json"
CALIBRATION_CONFIG = CONFIG_DIR / "oty2_s1x_optical_condition_calibration.json"
EVALUATION_CONFIG = CONFIG_DIR / "oty2_s1x_posthoc_evaluation.json"
CONDITION_PATH = MANIFEST_DIR / "oty2_s1x_optical_condition_frames.csv"
LINEAGE_PATH = MANIFEST_DIR / "oty2_s1x_optical_condition_input_lineage.csv"
FRAME_STATE_PATH = MANIFEST_DIR / "oty2_s1x_temporal_support_frame_states.csv"
SAR_ONLY_PATH = MANIFEST_DIR / "oty2_s1x_sar_only_temporal_objects.csv"
FREEZE_PATH = MANIFEST_DIR / "oty2_s1x_inference_freeze_manifest.csv"
BLIND_REVIEW_PATH = MANIFEST_DIR / "oty2_s1x_blind_visual_review_manifest.csv"
POSTHOC_FRAME_PATH = MANIFEST_DIR / "oty2_s1x_posthoc_frame_evaluation.csv"
POSTHOC_WINDOW_PATH = MANIFEST_DIR / "oty2_s1x_posthoc_window_evaluation.csv"
POSTHOC_REVIEW_PATH = MANIFEST_DIR / "oty2_s1x_posthoc_visual_manifest.csv"
QUESTION_PATH = MANIFEST_DIR / "oty2_s1x_project_question_answers.csv"
CONCLUSION_PATH = MANIFEST_DIR / "oty2_s1x_stage_conclusions.csv"
PREPARATION_SUMMARY_PATH = REPORT_DIR / "oty2_s1x_input_preparation_summary_20260717.json"
INFERENCE_SUMMARY_PATH = REPORT_DIR / "oty2_s1x_inference_summary_20260717.json"
EVALUATION_SUMMARY_PATH = REPORT_DIR / "oty2_s1x_posthoc_evaluation_summary_20260717.json"
REPLAY_SUMMARY_PATH = REPORT_DIR / "oty2_s1x_fixed_input_replay_summary_20260717.json"
FINAL_REPORT_PATH = REPORT_DIR / "oty2_s1x_optical_conditioned_joint_temporal_support_recovery_20260717.md"
INFERENCE_RUNNER_PATH = Path(__file__).with_name("run_oty2_s1x_joint_temporal_support.py")

ALLOWED_PATHS = {
    "configs/oty2/oty2_s1x_input_preparation.json",
    "configs/oty2/oty2_s1x_joint_temporal_support.json",
    "configs/oty2/oty2_s1x_optical_condition_calibration.json",
    "configs/oty2/oty2_s1x_posthoc_evaluation.json",
    "docs/OTY2_SESSION_START_HERE.md",
    "docs/OTY2_S1X_PROJECT_UNDERSTANDING_AND_EXECUTION_CONTRACT.md",
    "manifests/oty2/oty2_s1x_blind_visual_review_manifest.csv",
    "manifests/oty2/oty2_s1x_inference_freeze_manifest.csv",
    "manifests/oty2/oty2_s1x_optical_condition_frames.csv",
    "manifests/oty2/oty2_s1x_optical_condition_input_lineage.csv",
    "manifests/oty2/oty2_s1x_posthoc_frame_evaluation.csv",
    "manifests/oty2/oty2_s1x_posthoc_visual_manifest.csv",
    "manifests/oty2/oty2_s1x_posthoc_window_evaluation.csv",
    "manifests/oty2/oty2_s1x_project_question_answers.csv",
    "manifests/oty2/oty2_s1x_sar_only_temporal_objects.csv",
    "manifests/oty2/oty2_s1x_stage_conclusions.csv",
    "manifests/oty2/oty2_s1x_temporal_support_frame_states.csv",
    "reports/oty2/oty2_s1x_blind_direct_visual_review_20260717.md",
    "reports/oty2/oty2_s1x_fixed_input_replay_summary_20260717.json",
    "reports/oty2/oty2_s1x_inference_summary_20260717.json",
    "reports/oty2/oty2_s1x_input_preparation_summary_20260717.json",
    "reports/oty2/oty2_s1x_missing_inputs_and_boundaries_20260717.md",
    "reports/oty2/oty2_s1x_optical_conditioned_joint_temporal_support_recovery_20260717.md",
    "reports/oty2/oty2_s1x_posthoc_direct_visual_review_20260717.md",
    "reports/oty2/oty2_s1x_posthoc_evaluation_summary_20260717.json",
    "tools/diagnostics/check_oty2_s1x_fixed_input_replay.py",
    "tools/diagnostics/oty2_s1x_common.py",
    "tools/diagnostics/run_oty2_s1x_evaluate_frozen_outputs.py",
    "tools/diagnostics/run_oty2_s1x_joint_temporal_support.py",
    "tools/diagnostics/run_oty2_s1x_prepare_optical_conditions.py",
    "tools/diagnostics/validate_oty2_s1x_outputs.py",
}

EXPECTED_ANSWERS = {
    "Q1_VISIBLE_SEQUENCE_WITHOUT_TARGET_REFERENCE": "YES_CONSERVATIVE_VISIBLE_RESPONSE_SEQUENCE_RECOVERED",
    "Q2_SAR_INCREMENT_OVER_OPTICAL_SHELL": "YES_SUPPORT_RANGE_STRONGLY_CONTRACTED_BACKGROUND_REDUCTION_MEASURED",
    "Q3_TEMPORAL_JOINT_MORE_STABLE_THAN_PER_FRAME": "PARTIAL_YES_LOWER_JITTER_BUT_NO_ADDITIONAL_BREAK_RECOVERY",
    "Q4_FROZEN_RULE_REPLAY": "YES_PARTIAL_REPRODUCTION_ON_INDEPENDENT_OPTICAL_VEHICLE_THREAD",
}

EXPECTED_CONCLUSIONS = {
    "PROJECT_STAGE": "OTY2_S1X_PROJECT_LEVEL_CLOSED_LOOP_COMPLETED",
    "OPTICAL_CONDITION_INPUT": "AVAILABLE_AS_REAL_OPTICAL_RESEARCH_BENCHMARK",
    "TARGET_REFERENCE_ISOLATION": "PASS",
    "OPTICAL_ONLY_CONDITION_SHELL": "VALID_BUT_BROAD",
    "SAR_ONLY_BLIND_DIAGNOSTIC": "AMBIGUOUS_BACKGROUND_RICH",
    "JOINT_VISIBLE_RESPONSE_SEQUENCE": "SUPPORTED",
    "SAR_INCREMENT_OVER_OPTICAL_ONLY": "SUPPORTED_BY_CONTRACTION_AND_PRECISION",
    "TEMPORAL_JOINT_VALUE": "PARTIAL_LOWER_JITTER_NO_BREAK_RECOVERY",
    "WEAK_RESPONSE_MAINTENANCE": "SUPPORTED_AS_PIXEL_LEVEL_CONTINUITY",
    "FROZEN_RULE_REPLAY": "SUPPORTED_PARTIAL_REPRODUCTION",
    "FULL_BODY_SUPPORT": "NOT_RECOVERED",
    "UNIQUE_BOX_OR_CENTER": "NOT_EVALUATED_NOT_AUTHORIZED",
    "S1D_READINESS": "SMALL_SCALE_S1D_ALLOWED_WITH_RESEARCH_PROXY_INPUTS",
    "AUTOMATIC_ANNOTATION_READINESS": "NOT_READY",
}

EXPECTED_METRICS = {
    DISCOVERY: {
        "inference_frame_count": 21,
        "reference_available_frame_count": 21,
        "joint_reference_hit_frame_fraction": 1.0,
        "joint_mean_target_coverage": 0.10955419323809522,
        "joint_mean_precision": 0.6242729662380954,
        "joint_mean_shell_contraction_fraction": 0.9464838273333334,
        "joint_total_other_vehicle_overlap_px": 0,
        "temporally_recovered_reference_hit_frames": 0,
        "weak_maintained_target_frame_count": 21,
        "joint_centroid_jump_median_px": 11.468657963796636,
        "independent_centroid_jump_median_px": 13.742905498638438,
    },
    REPLAY: {
        "inference_frame_count": 54,
        "reference_available_frame_count": 54,
        "joint_reference_hit_frame_fraction": 1.0,
        "joint_mean_target_coverage": 0.11983484424074074,
        "joint_mean_precision": 0.9415331751666668,
        "joint_mean_shell_contraction_fraction": 0.9606182518333333,
        "joint_total_other_vehicle_overlap_px": 0,
        "temporally_recovered_reference_hit_frames": 0,
        "weak_maintained_target_frame_count": 54,
        "joint_centroid_jump_median_px": 3.7072991995621902,
        "independent_centroid_jump_median_px": 4.910569675261874,
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.rstrip()


def read_csv(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def changed_paths() -> set[str]:
    paths = set(git("diff", "--name-only", EXPECTED_START_HEAD).splitlines())
    paths.update(git("diff", "--cached", "--name-only", EXPECTED_START_HEAD).splitlines())
    for line in git("status", "--porcelain=v1", "--untracked-files=all").splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path.replace("\\", "/"))
    return {path for path in paths if path}


def validate_git_and_files() -> dict[str, Any]:
    require(git("branch", "--show-current") == EXPECTED_BRANCH, "branch mismatch")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_START_HEAD, "HEAD"],
        cwd=REPO_ROOT,
        check=False,
    )
    require(ancestry.returncode == 0, "frozen start HEAD is not an ancestor of HEAD")
    paths = changed_paths()
    require(paths == ALLOWED_PATHS, f"changed path mismatch: {sorted(paths ^ ALLOWED_PATHS)}")
    binary_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".npz", ".npy", ".zip", ".docx", ".pdf"}
    binary_paths = sorted(path for path in paths if Path(path).suffix.lower() in binary_suffixes)
    require(not binary_paths, f"forbidden Git binary artifacts: {binary_paths}")
    for relative in ALLOWED_PATHS:
        require((REPO_ROOT / relative).is_file(), f"missing required exact file: {relative}")
    return {"changed_path_count": len(paths), "forbidden_git_binary_artifacts": []}


def validate_calibration_and_conditions() -> dict[str, Any]:
    preparation = load_json(PREPARATION_CONFIG)
    calibration = load_json(CALIBRATION_CONFIG)
    preparation_summary = load_json(PREPARATION_SUMMARY_PATH)
    forbidden_targets = {"GM_RM017:PV002", "GM_RM017:PV003"}
    require(preparation["calibration"]["vehicle_id"] == "GM_RM017:PV004", "calibration vehicle mismatch")
    require(set(preparation["calibration"]["forbidden_target_vehicle_ids"]) == forbidden_targets, "calibration exclusion mismatch")
    require(calibration["calibration_vehicle_id"] == "GM_RM017:PV004", "calibration output vehicle mismatch")
    require(set(calibration["forbidden_target_vehicle_ids"]) == forbidden_targets, "calibration output exclusions mismatch")
    require(set(calibration["target_vehicle_ids_present_in_source_but_excluded"]) == forbidden_targets, "target exclusions not evidenced")
    require(calibration["target_vehicle_rows_loaded_for_fit"] == 0, "target rows entered calibration fit")
    require(calibration["row_count"] == 43, "calibration row count mismatch")
    require(calibration["calibration_role"] == "independent_calibration_only_not_discovery_or_replay", "calibration role mismatch")
    require(preparation_summary["target_reference_dependency"] is False, "target reference dependency declared")
    require(preparation_summary["old_work_runtime_dependency"] is False, "old_work runtime dependency declared")
    require(preparation_summary["condition_row_count"] == 75, "preparation summary row count mismatch")
    require(preparation_summary["condition_counts"] == {"discovery": 21, "frozen_rule_replay": 54}, "preparation role counts mismatch")

    rows = read_csv(CONDITION_PATH)
    require(len(rows) == 75, "condition row count mismatch")
    forbidden_columns = []
    for name in rows[0]:
        lowered = name.lower()
        tokens = lowered.replace("-", "_").split("_")
        if (
            lowered.startswith("gt_")
            or lowered.startswith("final_")
            or lowered.startswith("manual_")
            or lowered.startswith("oracle_")
            or "iou" in tokens
            or any(fragment in lowered for fragment in ("sar_gt", "target_bbox", "reference_bbox", "reference_path", "reference_mask"))
        ):
            forbidden_columns.append(name)
    require(not forbidden_columns, f"forbidden inference fields in conditions: {forbidden_columns}")
    require(all(row["depends_on_target_reference"].lower() == "false" for row in rows), "target dependency row found")
    require(all(row["calibration_vehicle_role"] == "independent_calibration_only_not_discovery_or_replay" for row in rows), "condition calibration role mismatch")
    require(all(float(row["radial_half_width_px"]) >= 120.0 for row in rows), "radial uncertainty collapsed below minimum")
    require(all(float(row["radial_interval_lower_px"]) < float(row["radial_interval_upper_px"]) for row in rows), "invalid radial interval")
    require(all(row["uncertainty_status"] == "EXPLICIT_INTERVAL_NOT_POINT_TRUTH" for row in rows), "point-truth uncertainty marker found")

    counts = Counter(row["window_role"] for row in rows)
    require(counts == Counter({"discovery": 21, "frozen_rule_replay": 54}), "condition window-role counts mismatch")
    for window_id, expected in EXPECTED_WINDOWS.items():
        selected = [row for row in rows if row["window_id"] == window_id]
        require({int(row["sar_frame_index"]) for row in selected} == expected["frames"], f"condition frames mismatch: {window_id}")
        require(all(row["canonical_vehicle_id"] == expected["vehicle"] for row in selected), f"condition vehicle mismatch: {window_id}")
    for row in rows:
        sar_path = Path(row["sar_gray_path"])
        require(sar_path.is_file(), f"missing SAR input: {sar_path}")
        require(sha256_file(sar_path) == row["sar_gray_sha256"], f"SAR input hash mismatch: {sar_path}")

    lineage = read_csv(LINEAGE_PATH)
    require(len(lineage) == 9, "input lineage row count mismatch")
    calibration_only = [row for row in lineage if row["depends_on_sar_gt"] != "false"]
    require(len(calibration_only) == 2, "unexpected SAR-reference lineage count")
    require(all(row["depends_on_sar_gt"] == "true_calibration_vehicle_only" for row in calibration_only), "target SAR reference entered lineage")
    return {
        "calibration_vehicle": "GM_RM017:PV004",
        "calibration_rows": 43,
        "target_rows_loaded_for_fit": 0,
        "condition_rows": 75,
        "forbidden_condition_fields": [],
        "sar_input_hash_matches": 75,
    }


def validate_freeze_and_reviews() -> dict[str, Any]:
    freeze_rows = read_csv(FREEZE_PATH)
    require(len(freeze_rows) == 17, "freeze manifest must contain exactly 17 rows")
    require(len({row["path"] for row in freeze_rows}) == 17, "duplicate freeze path")
    for row in freeze_rows:
        path = Path(row["path"])
        require(path.is_file(), f"missing frozen artifact: {path}")
        require(path.stat().st_size == int(row["bytes"]), f"frozen byte-size mismatch: {path}")
        require(sha256_file(path) == row["sha256"], f"frozen SHA256 mismatch: {path}")
        require(row["frozen_before_evaluation"].lower() == "true", f"artifact not frozen before evaluation: {path}")
        require(row["target_reference_content"].lower() == "false", f"target reference content in frozen artifact: {path}")

    blind = read_csv(BLIND_REVIEW_PATH)
    require(len(blind) == 6, "blind-review row count mismatch")
    require(Counter(row["window_id"] for row in blind) == Counter({DISCOVERY: 3, REPLAY: 3}), "blind-review window count mismatch")
    for row in blind:
        require(row["review_status"] == "directly_reviewed_complete", "incomplete blind review")
        require(row["contains_target_reference"].lower() == "false", "target reference found in blind review")
        artifact = Path(row["artifact_path"])
        require(artifact.is_file(), f"missing blind-review artifact: {artifact}")
        require(sha256_file(artifact) == row["artifact_sha256"], f"blind-review hash mismatch: {artifact}")

    posthoc = read_csv(POSTHOC_REVIEW_PATH)
    require(len(posthoc) == 2, "posthoc-review row count mismatch")
    require({row["window_id"] for row in posthoc} == set(EXPECTED_WINDOWS), "posthoc-review windows mismatch")
    for row in posthoc:
        require(row["review_status"] == "directly_reviewed_complete", "incomplete posthoc review")
        require(row["evaluation_only"].lower() == "true", "posthoc artifact not evaluation-only")
        require(row["generated_after_inference_freeze"].lower() == "true", "posthoc artifact predates freeze")
        artifact = Path(row["artifact_path"])
        require(artifact.is_file(), f"missing posthoc-review artifact: {artifact}")
        require(sha256_file(artifact) == row["artifact_sha256"], f"posthoc-review hash mismatch: {artifact}")
    return {"freeze_hashes": "17/17", "blind_reviews": "6/6 complete", "posthoc_reviews": "2/2 complete"}


def validate_inference_boundaries() -> dict[str, Any]:
    config = load_json(INFERENCE_CONFIG)
    require(all(config["prohibitions"].values()), "an inference prohibition is disabled")
    config_text = INFERENCE_CONFIG.read_text(encoding="utf-8").lower()
    forbidden_fragments = ("sar_gt", "final_gt", "gt_quality_audit", "oracle_box", "manual_box", "final_box", "iou")
    require(not [fragment for fragment in forbidden_fragments if fragment in config_text], "forbidden inference-config path/field fragment")

    runner_text = INFERENCE_RUNNER_PATH.read_text(encoding="utf-8").lower()
    for token in ("oty2_s0_sar_gt_quality_audit.csv", "reference_manifest", "reference_path"):
        require(token not in runner_text, f"inference runner contains target-reference entry token: {token}")

    summary = load_json(INFERENCE_SUMMARY_PATH)
    require(summary["target_reference_used_for_inference"] is False, "target reference used for inference")
    require(summary["candidate_bank_generated"] is False, "candidate bank generated")
    require(summary["weighted_score_or_ranking_used"] is False, "ranking or weighted score used")
    require(summary["unique_box_generated"] is False, "unique box generated")
    require(summary["leakage_audit"] == {"condition_forbidden_columns": [], "config_forbidden_fragment_hits": [], "target_dependency_rows": 0}, "inference leakage audit mismatch")

    frame_rows = read_csv(FRAME_STATE_PATH)
    require(len(frame_rows) == 75, "inference frame-state row count mismatch")
    for row in frame_rows:
        require(row["target_reference_used_for_inference"].lower() == "false", "frame used target reference")
        require(row["candidate_bank_generated"].lower() == "false", "frame generated candidate bank")
        require(row["ranking_or_weighted_score_used"].lower() == "false", "frame used ranking or weighted score")
        require(row["unique_box_generated"].lower() == "false", "frame generated unique box")
    sar_only = read_csv(SAR_ONLY_PATH)
    require(len(sar_only) == 23, "SAR-only diagnostic object count mismatch")
    require(all(row["object_semantics"] == "BLIND_SAR_TEMPORAL_RESPONSE_OBJECT_NOT_VEHICLE_IDENTITY" for row in sar_only), "SAR-only object claimed vehicle identity")
    return {
        "target_reference_inference_rows": 0,
        "candidate_bank": "NOT_GENERATED",
        "ranking_or_weighted_score": "NOT_USED",
        "unique_box": "NOT_GENERATED",
        "sar_only_diagnostic_objects": len(sar_only),
    }


def require_metric(actual: str | int | float, expected: int | float, label: str) -> None:
    if isinstance(expected, int):
        require(int(actual) == expected, f"metric mismatch {label}: {actual} != {expected}")
    else:
        require(math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12), f"metric mismatch {label}: {actual} != {expected}")


def validate_evaluation_and_decision() -> dict[str, Any]:
    evaluation_config = load_json(EVALUATION_CONFIG)
    require(evaluation_config["evaluation_semantics"]["reference_use"] == "posthoc_only_after_inference_and_blind_review_freeze", "posthoc reference-use contract mismatch")
    require(evaluation_config["evaluation_semantics"]["no_rule_update_from_evaluation"] is True, "evaluation rule-update gate disabled")

    frame_rows = read_csv(POSTHOC_FRAME_PATH)
    require(len(frame_rows) == 75, "posthoc frame row count mismatch")
    require(all(row["target_reference_used_for_inference"].lower() == "false" for row in frame_rows), "posthoc row reports reference inference")
    require(all(row["evaluation_only"].lower() == "true" for row in frame_rows), "posthoc row not evaluation-only")
    require(Counter(row["reference_available"].lower() for row in frame_rows) == Counter({"true": 75}), "reference evaluation frame count mismatch")

    window_rows = read_csv(POSTHOC_WINDOW_PATH)
    require(len(window_rows) == 2, "posthoc window row count mismatch")
    by_window = {row["window_id"]: row for row in window_rows}
    require(set(by_window) == set(EXPECTED_WINDOWS), "posthoc windows mismatch")
    for window_id, expected_metrics in EXPECTED_METRICS.items():
        row = by_window[window_id]
        require(row["target_reference_used_for_inference"].lower() == "false", f"window reports reference inference: {window_id}")
        for key, expected in expected_metrics.items():
            require_metric(row[key], expected, f"{window_id}.{key}")

    summary = load_json(EVALUATION_SUMMARY_PATH)
    require(summary["freeze_audit"] == {"all_hashes_match": True, "freeze_row_count": 17}, "evaluation freeze audit mismatch")
    require(summary["inference_outputs_modified"] is False, "evaluation modified inference outputs")
    require(summary["rule_update_from_evaluation"] is False, "rules updated from evaluation")

    answers = read_csv(QUESTION_PATH)
    require(len(answers) == 4, "project-answer row count mismatch")
    actual_answers = {row["question_id"]: row["direct_answer"] for row in answers}
    require(actual_answers == EXPECTED_ANSWERS, f"project answers mismatch: {actual_answers}")
    require({row["question_id"]: row["direct_answer"] for row in summary["project_questions"]} == EXPECTED_ANSWERS, "evaluation-summary project answers mismatch")

    conclusions = read_csv(CONCLUSION_PATH)
    require(len(conclusions) == 14, "stage conclusion row count mismatch")
    actual_conclusions = {row["conclusion_id"]: row["status"] for row in conclusions}
    require(actual_conclusions == EXPECTED_CONCLUSIONS, f"stage conclusions mismatch: {actual_conclusions}")
    report = FINAL_REPORT_PATH.read_text(encoding="utf-8")
    require("四个项目级问题的直接答案" in report, "final report missing direct-answer section")
    require(all(f"### 1.{index}" in report for index in range(1, 5)), "final report does not directly answer all four questions")
    require("SMALL_SCALE_S1D_ALLOWED_WITH_RESEARCH_PROXY_INPUTS" in report, "final report missing S1-D decision")
    return {
        "reference_frames": "75/75",
        "window_metrics": EXPECTED_METRICS,
        "project_answers": EXPECTED_ANSWERS,
        "s1d_decision": EXPECTED_CONCLUSIONS["S1D_READINESS"],
    }


def validate_fixed_input_replay() -> dict[str, Any]:
    summary = load_json(REPLAY_SUMMARY_PATH)
    require(summary["status"] == "PASS", "fixed-input replay did not pass")
    require(summary["condition_sha256"] == sha256_file(CONDITION_PATH), "replay condition hash mismatch")
    require(summary["config_sha256"] == sha256_file(INFERENCE_CONFIG), "replay config hash mismatch")
    require(summary["frame_rows_equal_excluding_output_path"] is True, "replay frame rows differ")
    require(summary["sar_only_object_rows_equal"] is True, "replay SAR-only rows differ")
    require(len(summary["windows"]) == 2, "replay window count mismatch")
    for window in summary["windows"]:
        require(window["window_id"] in EXPECTED_WINDOWS, "unexpected replay window")
        require(window["review_names_equal"] is True, "replay review names differ")
        require(window["review_pixels_equal"] is True, "replay review pixels differ")
        require(window["npz"]["all_arrays_equal"] is True, "replay NPZ arrays differ")
        require(window["npz"]["keys_equal"] is True, "replay NPZ keys differ")
        require(window["npz"]["file_sha_equal"] is True, "replay NPZ file hash differs")
        require(window["npz"]["array_mismatches"] == [], "replay NPZ mismatch list not empty")
    return {"status": "PASS", "windows": 2, "pixel_identical_reviews": 2, "array_identical_npz": 2}


def main() -> None:
    results = {
        "git_and_files": validate_git_and_files(),
        "calibration_and_conditions": validate_calibration_and_conditions(),
        "freeze_and_reviews": validate_freeze_and_reviews(),
        "inference_boundaries": validate_inference_boundaries(),
        "evaluation_and_decision": validate_evaluation_and_decision(),
        "fixed_input_replay": validate_fixed_input_replay(),
    }
    results["validator_status"] = "PASS"
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
