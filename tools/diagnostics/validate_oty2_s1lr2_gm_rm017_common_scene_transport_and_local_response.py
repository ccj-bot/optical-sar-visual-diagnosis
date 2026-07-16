#!/usr/bin/env python3
from __future__ import annotations

"""Validate the bounded S1-LR2 transport-stabilization audit."""

import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOC_DIR = REPO_ROOT / "docs"
OUTPUT_ROOT = Path(
    r"D:\profile\research\workspace\output\s1_lr2_gm_rm017_common_scene_transport_local_response_20260716_final_v2"
)

EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "8eb4b99e3fefb41ba2449c5e53ea3b7338e8591b"
EXPECTED_MANIFEST_SHA256 = (
    "029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092"
)
EXPECTED_FRAMES = set(range(330, 351))
EXPECTED_ANCHORS = {
    "BG_A_VERTICAL_STRONG_LINE",
    "BG_B_FAN_ARC_CENTRAL",
    "BG_C_ISOLATED_HOTSPOT",
    "BG_D_NEARBY_NONVEHICLE_CURVE",
    "BG_E_LEFT_ARC_BRANCH",
    "BG_F_RIGHT_DIAGONAL_FRAGMENT",
    "BG_G_UPPER_DIAGONAL_FRAGMENT",
    "BG_H_FAN_ARC_LEFT",
}

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
GT_DEBT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_gt_motion_debt.csv"
ANCHOR_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_background_anchor_tracking.csv"
MODEL_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_transport_model_selection.csv"
HOLDOUT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_holdout_background_validation.csv"
STABILIZATION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_stabilization_frame_quality.csv"
REGION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_local_response_regions.csv"
COMPONENT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_local_response_components.csv"
DIRECTION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_direction_fragments.csv"
RELATION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_local_response_relations.csv"
MATCHED_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_matched_background_counterfactuals.csv"
SUPPORT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_visible_response_support_regions.csv"
CONCLUSION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_stage_conclusions.csv"

SEMANTIC_DOC = DOC_DIR / "OTY2_S1LR_PREVIOUS_CONCLUSION_SEMANTIC_CORRECTION_20260716.md"
PROTOCOL_DOC = DOC_DIR / "OTY2_S1LR2_GM_RM017_COMMON_SCENE_TRANSPORT_AND_LOCAL_RESPONSE_ORGANIZATION_PROTOCOL.md"
DIRECT_REPORT = REPORT_DIR / "oty2_s1lr2_gm_rm017_common_scene_transport_local_response_direct_visual_review_20260716.md"
FINAL_REPORT = REPORT_DIR / "oty2_s1lr2_gm_rm017_common_scene_transport_local_response_audit_20260716.md"
RUNNER_PATH = Path(__file__).with_name(
    "run_oty2_s1lr2_gm_rm017_common_scene_transport_and_local_response.py"
)
VALIDATOR_PATH = Path(__file__)

ALLOWED_PATHS = {
    "docs/OTY2_S1LR_PREVIOUS_CONCLUSION_SEMANTIC_CORRECTION_20260716.md",
    "docs/OTY2_S1LR2_GM_RM017_COMMON_SCENE_TRANSPORT_AND_LOCAL_RESPONSE_ORGANIZATION_PROTOCOL.md",
    "manifests/oty2/oty2_s1lr2_gm_rm017_gt_motion_debt.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_background_anchor_tracking.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_transport_model_selection.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_holdout_background_validation.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_stabilization_frame_quality.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_local_response_regions.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_local_response_components.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_direction_fragments.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_local_response_relations.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_matched_background_counterfactuals.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_visible_response_support_regions.csv",
    "manifests/oty2/oty2_s1lr2_gm_rm017_stage_conclusions.csv",
    "reports/oty2/oty2_s1lr2_gm_rm017_common_scene_transport_local_response_direct_visual_review_20260716.md",
    "reports/oty2/oty2_s1lr2_gm_rm017_common_scene_transport_local_response_audit_20260716.md",
    "tools/diagnostics/run_oty2_s1lr2_gm_rm017_common_scene_transport_and_local_response.py",
    "tools/diagnostics/validate_oty2_s1lr2_gm_rm017_common_scene_transport_and_local_response.py",
}

EXPECTED_CONCLUSIONS = {
    "COMMON_SCENE_TRANSPORT_MODEL": "SUPPORTED_GLOBAL_TRANSLATION_PHASE_MULTI_BACKGROUND_MINIMUM_SUFFICIENT",
    "BACKGROUND_STABILIZATION_QUALITY": "SUPPORTED_MULTI_HOLDOUT_RESIDUAL_REDUCTION",
    "RAW_GT_ADJACENT_MOTION_RELIABILITY": "NOT_RELIABLE_AS_PHYSICAL_DISPLACEMENT_TRUTH",
    "LOCAL_HORIZONTAL_RESPONSE_CORE": "SUPPORTED_STABILIZED_PERSISTENT_HORIZONTAL_CORE",
    "LOCAL_MULTI_PART_RESPONSE_ORGANIZATION": "PARTIAL_STABLE_MAIN_UPPER_RELATION_ENDPOINTS_NOT_UNIQUE",
    "VEHICLE_VS_MATCHED_BACKGROUND_RELATION_SET": "PARTIAL_NO_SINGLE_CONTROL_REPRODUCES_COMPLETE_RELATION_SET",
    "RESPONSE_STATE_TRANSITION_AFTER_STABILIZATION": "PARTIAL_339_NOT_VEHICLE_SPECIFIC_POST340_STRENGTHENING_REMAINS",
    "VISIBLE_RESPONSE_SUPPORT_CORRIDOR": "PARTIAL_PERSISTENT_CORE_WITH_INTERMITTENT_AND_MIXED_REGIONS",
    "FULL_BODY_SUPPORT_READINESS": "NOT_READY",
    "OPTICAL_INPUT_REPLACEMENT_READINESS": "NOT_READY",
    "S1D_READINESS": "NOT_READY",
    "VEHICLE_MOTION_OWNERSHIP": "NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION",
    "MOTION_COHERENT_SUPPORT_CORRIDOR": "NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION",
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
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def floats(rows: Iterable[dict[str, str]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if row.get(key, "") != ""]


def changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("diff", "--name-only", EXPECTED_START_HEAD),
        ("diff", "--cached", "--name-only", EXPECTED_START_HEAD),
    ):
        text = git(*args)
        paths.update(line for line in text.splitlines() if line)
    for line in git("status", "--porcelain=v1", "--untracked-files=all").splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path.replace("\\", "/"))
    return paths


def validate_git() -> dict[str, Any]:
    require(git("branch", "--show-current") == EXPECTED_BRANCH, "branch mismatch")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_START_HEAD, "HEAD"],
        cwd=REPO_ROOT,
        check=False,
    )
    require(ancestor.returncode == 0, "frozen start HEAD is not an ancestor of HEAD")
    paths = changed_paths()
    require(paths == ALLOWED_PATHS, f"changed path mismatch: {sorted(paths ^ ALLOWED_PATHS)}")
    forbidden_suffixes = {".png", ".gif", ".mp4", ".npz", ".npy", ".zip", ".docx"}
    forbidden = sorted(path for path in paths if Path(path).suffix.lower() in forbidden_suffixes)
    require(not forbidden, f"forbidden repository visual/binary artifacts: {forbidden}")
    return {"changed_path_count": len(paths), "changed_paths": sorted(paths)}


def validate_inputs() -> dict[str, Any]:
    require(sha256_file(LOCAL_FIELD_PATH) == EXPECTED_MANIFEST_SHA256, "manifest hash mismatch")
    selected = []
    for row in read_csv(LOCAL_FIELD_PATH):
        frame = int(row["sar_frame_index"])
        if (
            row["scene"] == "GM_RM017"
            and row["canonical_vehicle_id"] == "GM_RM017:PV002"
            and row["segment_id"] == "S0MV-GM_RM017-PV002-SEG02"
            and 330 <= frame <= 350
        ):
            selected.append(row)
    require(len(selected) == 21, "input row count mismatch")
    require({int(row["sar_frame_index"]) for row in selected} == EXPECTED_FRAMES, "input frames mismatch")
    for row in selected:
        source = Path(row["raw_image_path"])
        require(source.is_file(), f"missing source image: {source}")
        require(sha256_file(source) == row["raw_image_sha256"].lower(), f"source hash mismatch: {source}")
    return {"input_rows": 21, "source_hash_matches": 21}


def validate_anchor_and_models() -> dict[str, Any]:
    anchors = read_csv(ANCHOR_PATH)
    require(len(anchors) == 168, "anchor tracking row count mismatch")
    require({int(row["frame"]) for row in anchors} == EXPECTED_FRAMES, "anchor frames mismatch")
    require({row["anchor_id"] for row in anchors} == EXPECTED_ANCHORS, "anchor IDs mismatch")
    require(Counter(row["fit_or_holdout"] for row in anchors) == Counter({"FIT": 126, "HOLDOUT": 42}), "anchor split mismatch")
    require(all(row["direct_identity_status"] == "CONFIRMED_CONTINUOUS_330_350" for row in anchors), "unconfirmed anchor identity")
    require(all(row["direct_mixing_status"] == "NO_VEHICLE_MIXING_OBSERVED" for row in anchors), "anchor mixing status mismatch")
    require(all(row["algorithmic_structure_switch_suspected"] == "false" for row in anchors), "anchor switch suspicion found")
    require(all(row["vehicle_region_used_for_fit"] == "false" for row in anchors), "vehicle region used for fit")
    require(min(floats(anchors, "structure_match_quality")) > 0.16, "structure match quality too low")
    require(min(floats(anchors, "phase_response")) > 0.27, "phase response too low")
    require(max(floats(anchors, "method_disagreement_px")) < 1.05, "anchor method disagreement too high")

    models = read_csv(MODEL_PATH)
    require(len(models) == 16, "model selection row count mismatch")
    by_key = {(row["model_id"], row["observation_method"], row["evaluation_split"]): row for row in models}
    global_hold = float(by_key[("GLOBAL_TRANSLATION", "PHASE_CORRELATION", "HOLDOUT")]["residual_median_px"])
    affine_hold = float(by_key[("LOCAL_AFFINE", "PHASE_CORRELATION", "HOLDOUT")]["residual_median_px"])
    radial_hold = float(by_key[("RADIAL_TANGENTIAL_LINEAR_FIELD", "PHASE_CORRELATION", "HOLDOUT")]["residual_median_px"])
    tps_hold = float(by_key[("SPARSE_THIN_PLATE_FIELD", "PHASE_CORRELATION", "HOLDOUT")]["residual_median_px"])
    require(global_hold < 0.6, "global translation holdout residual too high")
    require(global_hold < affine_hold, "affine unexpectedly improves holdout median")
    require(radial_hold > 10.0, "radial-field failure evidence missing")
    require(tps_hold > global_hold, "thin-plate complexity not rejected by holdout")
    selected = [row for row in models if row["selected_for_stabilization"] == "true"]
    require(len(selected) == 2, "selected model marker count mismatch")
    require(all(row["model_id"] == "GLOBAL_TRANSLATION" and row["observation_method"] == "PHASE_CORRELATION" for row in selected), "selected model mismatch")
    return {
        "anchor_rows": len(anchors),
        "global_phase_holdout_median_px": global_hold,
        "affine_phase_holdout_median_px": affine_hold,
    }


def validate_stabilization() -> dict[str, Any]:
    holdout = read_csv(HOLDOUT_PATH)
    require(len(holdout) == 84, "holdout row count mismatch")
    phase = [row for row in holdout if row["observation_method"] == "PHASE_CORRELATION"]
    per_anchor = {}
    for anchor_id in {row["anchor_id"] for row in phase}:
        selected = [row for row in phase if row["anchor_id"] == anchor_id]
        residual = floats(selected, "post_stabilization_residual_px")
        reduction = floats(selected, "residual_reduction_fraction")
        per_anchor[anchor_id] = statistics.median(residual)
        require(statistics.median(residual) < 1.5, f"holdout median too high: {anchor_id}")
        require(statistics.median(reduction) > 0.97, f"holdout reduction too low: {anchor_id}")
        require(all(row["vehicle_gt_used_for_model_fit"] == "false" for row in selected), "GT used for model fit")
    quality = read_csv(STABILIZATION_PATH)
    require(len(quality) == 21, "stabilization quality row count mismatch")
    require(min(floats(quality, "valid_fraction")) > 0.94, "stabilization valid fraction too low")
    require(statistics.mean(floats(quality, "interpolation_abs_difference_mean")) < 1.6, "interpolation impact too large")
    require(all(row["selected_model"] == "GLOBAL_TRANSLATION" for row in quality), "frame model mismatch")
    require(all(row["selected_observation"] == "PHASE_CORRELATION" for row in quality), "frame observation mismatch")
    return {"holdout_phase_medians_px": per_anchor, "stabilization_frames": 21}


def validate_gt_debt() -> dict[str, Any]:
    rows = read_csv(GT_DEBT_PATH)
    require(len(rows) == 21, "GT debt row count mismatch")
    require({int(row["frame"]) for row in rows} == EXPECTED_FRAMES, "GT debt frames mismatch")
    require(sum(row["source_family_switch_from_previous"] == "true" for row in rows) == 19, "source switch count mismatch")
    raw_acceleration = floats(rows, "raw_acceleration_px_per_frame2")
    smooth_acceleration = floats(rows, "smoothed_acceleration_px_per_frame2")
    require(statistics.mean(raw_acceleration) > statistics.mean(smooth_acceleration), "smoothing does not reduce acceleration")
    transport_speed = floats(rows, "common_transport_speed_px_per_frame")
    require(statistics.pstdev(transport_speed) < 0.2, "common transport speed is not smooth")
    raw_residual = [
        math.hypot(float(row["raw_relative_transport_dx_px"]), float(row["raw_relative_transport_dy_px"]))
        for row in rows[1:]
    ]
    smooth_residual = [
        math.hypot(float(row["smoothed_relative_transport_dx_px"]), float(row["smoothed_relative_transport_dy_px"]))
        for row in rows[1:]
    ]
    require(statistics.median(raw_residual) > statistics.median(smooth_residual), "smoothed residual debt not improved")
    require(all(row["gt_adjacent_physical_displacement_truth"] == "NOT_ESTABLISHED" for row in rows), "adjacent GT truth incorrectly established")
    return {
        "source_switch_count": 19,
        "raw_acceleration_mean": statistics.mean(raw_acceleration),
        "smoothed_acceleration_mean": statistics.mean(smooth_acceleration),
        "transport_speed_std": statistics.pstdev(transport_speed),
    }


def validate_local_response() -> dict[str, Any]:
    regions = read_csv(REGION_PATH)
    components = read_csv(COMPONENT_PATH)
    directions = read_csv(DIRECTION_PATH)
    relations = read_csv(RELATION_PATH)
    matched = read_csv(MATCHED_PATH)
    support = read_csv(SUPPORT_PATH)
    require(len(regions) == 126, "region row count mismatch")
    require(len(components) > 8000, "component evidence unexpectedly small")
    require(len(directions) > 200, "direction evidence unexpectedly small")
    require(len(relations) == 126, "relation row count mismatch")
    require(len(matched) == 18, "matched-background stage row count mismatch")
    require(len(support) == 4, "support class count mismatch")
    require(all(row["gt_inside_outside_pixel_label_used"] == "false" for row in regions), "GT pixel label used in regions")
    require(all(row["gt_inside_outside_pixel_label_used"] == "false" for row in components), "GT pixel label used in components")

    coarse = [row for row in relations if row["region_id"] == "FROZEN_COARSE_CENTER_CORRIDOR"]
    require(len(coarse) == 21, "coarse relation frame count mismatch")
    require(all(row["main_band_present"] == "true" for row in coarse), "main band not present in all frames")
    require(all(row["upper_response_present"] == "true" for row in coarse), "upper response missing")
    require(statistics.pstdev(floats(coarse, "main_band_center_y_relative_px")) < 3.0, "main-band y is unstable")
    require(statistics.pstdev(floats(coarse, "upper_to_main_dy_px")) < 4.0, "main-upper relation is unstable")

    stage = {(row["region_id"], row["stage"]): row for row in matched}
    weak = stage[("FROZEN_COARSE_CENTER_CORRIDOR", "WEAK_DISTRIBUTED_330_338")]
    onset = stage[("FROZEN_COARSE_CENTER_CORRIDOR", "TRANSITION_ONSET_339")]
    strong = stage[("FROZEN_COARSE_CENTER_CORRIDOR", "STRONG_COMPACT_340_350")]
    require(float(strong["main_band_mean_robust_z_median"]) > float(weak["main_band_mean_robust_z_median"]), "post-340 main band is not stronger")
    require(float(onset["main_band_mean_robust_z_median"]) < float(weak["main_band_mean_robust_z_median"]), "339 vehicle-specific correction evidence missing")
    right_strong = stage[("MATCHED_BG_RIGHT_COMPLEX", "STRONG_COMPACT_340_350")]
    fan_strong = stage[("MATCHED_BG_FAN_ARC", "STRONG_COMPACT_340_350")]
    require(float(right_strong["main_band_present_fraction"]) < 0.2, "right matched control reproduces too much")
    require(float(fan_strong["main_band_present_fraction"]) == 1.0, "fan-arc form counterfactual missing")
    require(abs(float(fan_strong["upper_to_main_dy_median_px"])) > abs(float(strong["upper_to_main_dy_median_px"])) + 8.0, "fan-arc relation geometry not separated")

    support_by_name = {row["support_region_class"]: int(row["pixel_count"]) for row in support}
    require(support_by_name["PERSISTENT_LOCAL_RESPONSE_CORE"] > 0, "persistent core missing")
    require(support_by_name["MIXED_OR_UNRESOLVED_REGION"] > support_by_name["PERSISTENT_LOCAL_RESPONSE_CORE"], "mixed region debt missing")
    require(all(row["latent_full_body_support_recovered"] == "false" for row in support), "latent body was recovered")
    return {
        "component_rows": len(components),
        "direction_rows": len(directions),
        "persistent_core_pixels": support_by_name["PERSISTENT_LOCAL_RESPONSE_CORE"],
        "mixed_pixels": support_by_name["MIXED_OR_UNRESOLVED_REGION"],
    }


def validate_docs_and_conclusions() -> None:
    conclusions = read_csv(CONCLUSION_PATH)
    require(len(conclusions) == 13, "conclusion row count mismatch")
    actual = {row["conclusion_id"]: row["status"] for row in conclusions}
    require(actual == EXPECTED_CONCLUSIONS, f"conclusion mismatch: {actual}")
    for path in (SEMANTIC_DOC, PROTOCOL_DOC, DIRECT_REPORT, FINAL_REPORT, RUNNER_PATH, VALIDATOR_PATH):
        require(path.is_file(), f"missing required file: {path}")
    semantic = SEMANTIC_DOC.read_text(encoding="utf-8")
    for token in (
        "NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION",
        "NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION",
        "must not be directly replayed",
    ):
        require(token in semantic, f"semantic correction token missing: {token}")
    report = FINAL_REPORT.read_text(encoding="utf-8")
    for token in (
        "124.096369",
        "0.526015",
        "RAW_GT_ADJACENT_MOTION_RELIABILITY",
        "LOCAL_HORIZONTAL_RESPONSE_CORE",
        "PARTIAL_339_NOT_VEHICLE_SPECIFIC_POST340_STRENGTHENING_REMAINS",
        "S1D_READINESS=NOT_READY",
        "没有使用车辆 GT 轨迹、车辆响应或 GT IoU 拟合背景运输模型",
    ):
        require(token in report, f"final report token missing: {token}")
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    for token in (
        'SELECTED_MODEL = "GLOBAL_TRANSLATION"',
        'SELECTED_OBSERVATION = "PHASE_CORRELATION"',
        '"weighted_score": "NOT_COMPUTED"',
        '"candidate_bank": "NOT_CREATED"',
        '"latent_full_body_support": "NOT_RECOVERED"',
        '"s1d": "NOT_ENTERED"',
    ):
        require(token in runner, f"runner boundary token missing: {token}")


def validate_external_outputs() -> dict[str, Any]:
    required = {
        "01_raw_full_frame.gif",
        "02_stabilized_full_frame.gif",
        "03_raw_fixed_vehicle_neighbourhood.gif",
        "04_stabilized_vehicle_neighbourhood.gif",
        "05_vehicle_neighbourhood_before_after.gif",
        "08_holdout_background_residual_timeseries.png",
        "09_stabilization_valid_mask.gif",
        "10_stabilization_valid_mask_temporal_fraction.png",
        "11_interpolation_impact.gif",
        "12_interpolation_impact_temporal_mean_x12.png",
        "13_raw_smoothed_gt_and_common_transport_debt.png",
        "14_stabilized_local_response_review_sheet.png",
        "15_visible_response_support_organization_map.png",
        "visible_response_support_arrays.npz",
        "analysis_summary.json",
        "output_manifest.csv",
    }
    for anchor_id in EXPECTED_ANCHORS:
        required.add(f"anchor_reviews/{anchor_id}_identity_contact_sheet.png")
        required.add(f"anchor_reviews/{anchor_id}_before_after.gif")
    missing = sorted(path for path in required if not (OUTPUT_ROOT / path).is_file())
    require(not missing, f"missing external outputs: {missing}")
    manifest = read_csv(OUTPUT_ROOT / "output_manifest.csv")
    manifest_by_path = {row["relative_path"]: row for row in manifest}
    manifest_required = required - {"output_manifest.csv"}
    require(manifest_required - set(manifest_by_path) == set(), "external manifest missing required paths")
    for relative, row in manifest_by_path.items():
        path = OUTPUT_ROOT / relative
        require(path.is_file(), f"manifest output missing: {relative}")
        require(path.stat().st_size == int(row["bytes"]), f"output size mismatch: {relative}")
        require(sha256_file(path) == row["sha256"], f"output hash mismatch: {relative}")
    summary = json.loads((OUTPUT_ROOT / "analysis_summary.json").read_text(encoding="utf-8"))
    require(summary["selected_common_scene_transport_model"] == "GLOBAL_TRANSLATION", "external selected model mismatch")
    require(summary["selected_transport_observation"] == "PHASE_CORRELATION", "external selected observation mismatch")
    require(abs(float(summary["common_transport_cumulative_dx_px"]) - 124.09636879382776) < 1e-6, "external transport total mismatch")
    require(summary["algorithmic_anchor_switch_suspicion_count"] == 0, "external anchor switch debt")
    require(summary["weighted_score"] == "NOT_COMPUTED", "weighted score computed")
    require(summary["ranking"] == "NOT_COMPUTED", "ranking computed")
    require(summary["candidate_bank"] == "NOT_CREATED", "candidate bank created")
    require(summary["final_box"] == "NOT_COMPUTED", "final box computed")
    require(summary["latent_full_body_support"] == "NOT_RECOVERED", "latent body recovered")
    require(summary["s1d"] == "NOT_ENTERED", "S1-D entered")
    return {"external_output_count": len(manifest), "external_root": str(OUTPUT_ROOT)}


def main() -> None:
    results = {
        "git": validate_git(),
        "inputs": validate_inputs(),
        "anchors_and_models": validate_anchor_and_models(),
        "stabilization": validate_stabilization(),
        "gt_debt": validate_gt_debt(),
        "local_response": validate_local_response(),
    }
    validate_docs_and_conclusions()
    results["external_outputs"] = validate_external_outputs()
    results["forbidden_items_triggered"] = []
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
