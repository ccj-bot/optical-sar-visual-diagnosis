#!/usr/bin/env python3
from __future__ import annotations

"""Validate the bounded S1-LR GM_RM017 visible-response motion audit."""

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOC_DIR = REPO_ROOT / "docs"
OUTPUT_ROOT = Path(
    r"D:\profile\research\workspace\output\s1_lr_gm_rm017_motion_coherent_response_flow_20260716"
)
ANALYSIS_ROOT = OUTPUT_ROOT / "analysis"

EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "938dd8e37b54592bc153f5518843c4f7479cfe24"
EXPECTED_MANIFEST_SHA256 = (
    "029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092"
)
EXPECTED_FRAMES = list(range(330, 351))

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
DIRECT_REVIEW_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_direct_visual_reviews.csv"
BACKGROUND_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_background_motion_reference.csv"
PAIR_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_motion_pair_evidence.csv"
OFFSET_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_offset_field_evidence.csv"
SPATIAL_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_spatial_counterfactuals.csv"
TRAJECTORY_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_trajectory_counterfactuals.csv"
STATE_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_response_state_evidence.csv"
ATTRIBUTION_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_response_attribution_summary.csv"
CONCLUSION_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_stage_conclusions.csv"

PROTOCOL_PATH = DOC_DIR / "OTY2_S1LR_GM_RM017_MOTION_COHERENT_VISIBLE_RESPONSE_FLOW_PROTOCOL.md"
DIRECT_REPORT_PATH = REPORT_DIR / "oty2_s1lr_gm_rm017_motion_coherent_visible_response_direct_visual_review_20260716.md"
FINAL_REPORT_PATH = REPORT_DIR / "oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow_audit_20260716.md"
RUNNER_PATH = Path(__file__).with_name(
    "run_oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow.py"
)
VALIDATOR_PATH = Path(__file__)

ALLOWED_PATHS = {
    "docs/OTY2_S1LR_GM_RM017_MOTION_COHERENT_VISIBLE_RESPONSE_FLOW_PROTOCOL.md",
    "manifests/oty2/oty2_s1lr_gm_rm017_direct_visual_reviews.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_background_motion_reference.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_motion_pair_evidence.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_offset_field_evidence.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_spatial_counterfactuals.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_trajectory_counterfactuals.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_response_state_evidence.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_response_attribution_summary.csv",
    "manifests/oty2/oty2_s1lr_gm_rm017_stage_conclusions.csv",
    "reports/oty2/oty2_s1lr_gm_rm017_motion_coherent_visible_response_direct_visual_review_20260716.md",
    "reports/oty2/oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow_audit_20260716.md",
    "tools/diagnostics/run_oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow.py",
    "tools/diagnostics/validate_oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow.py",
}

EXPECTED_CONCLUSIONS = {
    "LOCAL_VISIBLE_VEHICLE_RESPONSE_FLOW": "VISUALLY_SUPPORTED_DISPLAY_FLOW_BACKGROUND_RELATIVE_OWNERSHIP_NOT_ESTABLISHED",
    "VEHICLE_MOTION_OWNERSHIP": "NOT_ESTABLISHED_MULTI_BACKGROUND_CO_MOTION",
    "WORLD_BACKGROUND_SEPARATION": "PARTIALLY_SUPPORTED_BACKGROUND_DRIFT_IDENTIFIED_LOCAL_SEPARATION_NOT_ESTABLISHED",
    "RESPONSE_STATE_TRANSITION": "SUPPORTED_339_ONSET_340_350_STRONG",
    "MOTION_COHERENT_SUPPORT_CORRIDOR": "NOT_ESTABLISHED_NO_VALID_OFFSET_PASSED_BOTH_METHODS",
    "VISIBLE_RESPONSE_UNIQUENESS_IN_LOCAL_NEIGHBORHOOD": "NOT_ESTABLISHED_NEAR_OFFSETS_AND_CONTROLS_RETAIN_STRUCTURE",
    "EXACT_CENTER_IDENTIFIABILITY": "NOT_ESTABLISHED",
    "FULL_BODY_SUPPORT_READINESS": "NOT_READY",
    "OPTICAL_INPUT_REPLACEMENT_READINESS": "NOT_READY",
    "S1D_READINESS": "NOT_READY",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        fail(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


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


def median(values: Iterable[float]) -> float:
    ordered = sorted(float(value) for value in values)
    require(bool(ordered), "median of empty values")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def close(actual: float, expected: float, tolerance: float = 1e-6) -> None:
    require(
        math.isfinite(actual) and abs(actual - expected) <= tolerance,
        f"value mismatch: actual={actual}, expected={expected}, tolerance={tolerance}",
    )


def changed_paths() -> set[str]:
    paths: set[str] = set()
    for command in (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("diff", "--name-only", f"{EXPECTED_START_HEAD}..HEAD"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        output = git(*command)
        paths.update(line.replace("\\", "/") for line in output.splitlines() if line)
    for line in git("status", "--porcelain=v1", "-uall").splitlines():
        if len(line) >= 4:
            paths.add(line[3:].replace("\\", "/"))
    return paths


def validate_git() -> dict[str, Any]:
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    require(branch == EXPECTED_BRANCH, f"branch mismatch: {branch}")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_START_HEAD, head],
        cwd=REPO_ROOT,
        check=False,
    ).returncode
    require(ancestry == 0, "frozen start HEAD is not an ancestor of current HEAD")
    paths = changed_paths()
    unexpected = sorted(paths - ALLOWED_PATHS)
    require(not unexpected, f"unexpected changed paths: {unexpected}")
    missing_scope = sorted(ALLOWED_PATHS - {path for path in ALLOWED_PATHS if (REPO_ROOT / path).is_file()})
    require(not missing_scope, f"missing allowed deliverables: {missing_scope}")
    require(not git("diff", "--check"), "git diff --check failed")
    require(not git("diff", "--cached", "--check"), "git diff --cached --check failed")
    forbidden_suffixes = {".png", ".gif", ".mp4", ".npz", ".docx", ".zip"}
    forbidden = sorted(path for path in paths if Path(path).suffix.lower() in forbidden_suffixes)
    require(not forbidden, f"forbidden repository artifacts: {forbidden}")
    oversized = sorted(
        path
        for path in ALLOWED_PATHS
        if (REPO_ROOT / path).is_file() and (REPO_ROOT / path).stat().st_size > 2_000_000
    )
    require(not oversized, f"unexpected large repository files: {oversized}")
    return {"branch": branch, "head": head, "changed_paths": sorted(paths)}


def validate_inputs() -> dict[str, Any]:
    require(
        sha256_file(LOCAL_FIELD_PATH) == EXPECTED_MANIFEST_SHA256,
        "local-response manifest SHA256 mismatch",
    )
    source_rows = [
        row
        for row in read_csv(LOCAL_FIELD_PATH)
        if row["scene"] == "GM_RM017"
        and row["canonical_vehicle_id"] == "GM_RM017:PV002"
        and row["segment_id"] == "S0MV-GM_RM017-PV002-SEG02"
        and 330 <= int(row["sar_frame_index"]) <= 350
    ]
    source_rows.sort(key=lambda row: int(row["sar_frame_index"]))
    require(
        [int(row["sar_frame_index"]) for row in source_rows] == EXPECTED_FRAMES,
        "unexpected source frame set",
    )
    for row in source_rows:
        image_path = Path(row["raw_image_path"])
        require(image_path.is_file(), f"missing image: {image_path}")
        require(
            sha256_file(image_path) == row["raw_image_sha256"].lower(),
            f"image SHA mismatch: {image_path}",
        )
    return {"manifest_sha256": EXPECTED_MANIFEST_SHA256, "source_hash_matches": len(source_rows)}


def validate_direct_review() -> None:
    rows = read_csv(DIRECT_REVIEW_PATH)
    require(len(rows) == 21, "direct review must have 21 rows")
    require(
        [int(row["sar_frame_index"]) for row in rows] == EXPECTED_FRAMES,
        "direct review frame order mismatch",
    )
    require(all(row["review_status"] == "REVIEWED" for row in rows), "unreviewed direct frame")
    report = DIRECT_REPORT_PATH.read_text(encoding="utf-8")
    for token in (
        "+129 px",
        "+126.336 px",
        "共同背景漂移",
        "不再单独支持车辆运动所有权",
    ):
        require(token in report, f"direct review correction missing: {token}")


def validate_background() -> dict[str, Any]:
    rows = read_csv(BACKGROUND_PATH)
    require(len(rows) == 20, "background reference must have 20 pairs")
    require(all(int(row["background_control_count"]) == 4 for row in rows), "background control count mismatch")
    require(
        all(
            row["world_coordinate_definition"]
            == "LOCAL_DISPLACEMENT_MINUS_MULTI_BACKGROUND_REFERENCE_DISPLACEMENT"
            for row in rows
        ),
        "world-coordinate definition mismatch",
    )
    phase_median = median(float(row["phase_background_dx_px"]) for row in rows)
    flow_median = median(float(row["flow_background_dx_px"]) for row in rows)
    close(phase_median, 6.25074978294203, 1e-9)
    close(flow_median, 6.307327151298523, 1e-9)
    gt_total = sum(float(row["gt_dx_px"]) for row in rows)
    phase_total = sum(float(row["phase_background_dx_px"]) for row in rows)
    flow_total = sum(float(row["flow_background_dx_px"]) for row in rows)
    close(gt_total, 126.336, 1e-9)
    require(abs(gt_total - phase_total) < 2.0, "phase background total too far from GT total")
    require(abs(gt_total - flow_total) < 2.0, "flow background total too far from GT total")
    return {
        "phase_background_dx_median_px": phase_median,
        "flow_background_dx_median_px": flow_median,
        "gt_total_dx_px": gt_total,
        "phase_background_total_dx_px": phase_total,
        "flow_background_total_dx_px": flow_total,
    }


def validate_pairs() -> dict[str, Any]:
    rows = read_csv(PAIR_PATH)
    require(len(rows) == 20, "motion pair CSV must have 20 rows")
    require(all(row["phase_quality_status"] == "USABLE" for row in rows), "weak phase pair")
    require(all(row["flow_quality_status"] == "USABLE" for row in rows), "weak flow pair")
    for row in rows:
        phase_world = math.hypot(
            float(row["phase_dx_px"]) - float(row["phase_background_dx_px"]),
            float(row["phase_dy_px"]) - float(row["phase_background_dy_px"]),
        )
        flow_world = math.hypot(
            float(row["flow_dx_px"]) - float(row["flow_background_dx_px"]),
            float(row["flow_dy_px"]) - float(row["flow_background_dy_px"]),
        )
        close(phase_world, float(row["phase_world_residual_motion_px"]), 1e-9)
        close(flow_world, float(row["flow_world_residual_motion_px"]), 1e-9)
    phase_world_median = median(float(row["phase_world_residual_motion_px"]) for row in rows)
    phase_vehicle_median = median(float(row["phase_vehicle_residual_motion_px"]) for row in rows)
    flow_world_median = median(float(row["flow_world_residual_motion_px"]) for row in rows)
    flow_vehicle_median = median(float(row["flow_vehicle_residual_motion_px"]) for row in rows)
    phase_vehicle_better = sum(
        float(row["phase_vehicle_residual_motion_px"])
        < float(row["phase_world_residual_motion_px"])
        for row in rows
    )
    flow_vehicle_better = sum(
        float(row["flow_vehicle_residual_motion_px"])
        < float(row["flow_world_residual_motion_px"])
        for row in rows
    )
    close(phase_world_median, 0.0926157962957037, 1e-9)
    close(phase_vehicle_median, 4.60663424711785, 1e-9)
    close(flow_world_median, 0.115809292487877, 1e-9)
    close(flow_vehicle_median, 4.66269521974487, 1e-9)
    require(phase_vehicle_better == 0, "phase unexpectedly supports vehicle motion")
    require(flow_vehicle_better == 0, "flow unexpectedly supports vehicle motion")
    return {
        "phase_world_residual_median_px": phase_world_median,
        "phase_vehicle_residual_median_px": phase_vehicle_median,
        "flow_world_residual_median_px": flow_world_median,
        "flow_vehicle_residual_median_px": flow_vehicle_median,
        "phase_vehicle_better_pairs": phase_vehicle_better,
        "flow_vehicle_better_pairs": flow_vehicle_better,
    }


def validate_offset_field() -> dict[str, int]:
    rows = read_csv(OFFSET_PATH)
    require(len(rows) == 123, "offset field must have 123 unique offsets")
    require(len({(row["dx_px"], row["dy_px"]) for row in rows}) == 123, "duplicate offset")
    categories = Counter(row["offset_category"] for row in rows)
    expected = {
        "BACKGROUND_DOMINATED_REGION": 112,
        "AMBIGUOUS_OVERLAP_REGION": 2,
        "OUTSIDE_VALID_REGION": 9,
    }
    require(dict(categories) == expected, f"offset category mismatch: {categories}")
    require(
        all(row["weighted_score"] == "NOT_COMPUTED" for row in rows),
        "offset weighted score computed",
    )
    require(all(row["rank"] == "NOT_COMPUTED" for row in rows), "offset rank computed")
    require(all(row["winner"] == "NOT_COMPUTED" for row in rows), "offset winner computed")
    zero = [row for row in rows if int(row["dx_px"]) == 0 and int(row["dy_px"]) == 0]
    require(len(zero) == 1 and zero[0]["offset_category"] == "BACKGROUND_DOMINATED_REGION", "correct offset category mismatch")
    return expected


def validate_counterfactuals() -> None:
    spatial = read_csv(SPATIAL_PATH)
    require(len(spatial) == 8, "spatial counterfactual count mismatch")
    require(
        {row["counterfactual_id"] for row in spatial}
        == {
            "CORRECT_TRACK",
            "NEAR_LEFT_OVERLAP",
            "NEAR_RIGHT_OVERLAP",
            "NEAR_ABOVE_PARTIAL",
            "NEARBY_NONOVERLAP_BACKGROUND",
            "VERTICAL_STRONG_LINE",
            "FAN_ARC",
            "ISOLATED_HOTSPOT",
        },
        "spatial counterfactual IDs mismatch",
    )
    near_rows = [row for row in spatial if row["counterfactual_id"] in {"NEAR_LEFT_OVERLAP", "NEAR_RIGHT_OVERLAP"}]
    require(all("not a true negative" in row["overlap_semantics"] for row in near_rows), "near offset mislabelled")
    trajectory = read_csv(TRAJECTORY_PATH)
    require(len(trajectory) == 13, "trajectory counterfactual count mismatch")
    required = {
        "CORRECT_TRACK",
        "CENTER_ORDER_SHUFFLE",
        "CENTER_ORDER_REVERSE",
        "TIME_SHIFT_-12",
        "TIME_SHIFT_-8",
        "TIME_SHIFT_-4",
        "TIME_SHIFT_+4",
        "TIME_SHIFT_+8",
        "TIME_SHIFT_+12",
        "HORIZONTAL_SPEED_SCALE_0.5",
        "HORIZONTAL_SPEED_SCALE_1.5",
        "WRONG_HORIZONTAL_DIRECTION",
        "FIXED_MEDIAN_CENTER",
    }
    require({row["counterfactual_id"] for row in trajectory} == required, "trajectory IDs mismatch")
    for rows in (spatial, trajectory):
        require(all(row["weighted_score"] == "NOT_COMPUTED" for row in rows), "counterfactual score computed")
        require(all(row["rank"] == "NOT_COMPUTED" for row in rows), "counterfactual rank computed")
        require(all(row["winner"] == "NOT_COMPUTED" for row in rows), "counterfactual winner computed")


def validate_state_and_attribution() -> dict[str, Any]:
    state = read_csv(STATE_PATH)
    require(len(state) == 21, "state evidence count mismatch")
    require([int(row["sar_frame_index"]) for row in state] == EXPECTED_FRAMES, "state frames mismatch")
    require(all(row["stage_boundary_reselected_by_metric"] == "False" for row in state), "metric reselected stage")
    early = [row for row in state if row["direct_review_stage"] == "WEAK_DISTRIBUTED_330_338"]
    transition = [row for row in state if row["direct_review_stage"] == "TRANSITION_ONSET_339"]
    strong = [row for row in state if row["direct_review_stage"] == "STRONG_COMPACT_340_350"]
    require((len(early), len(transition), len(strong)) == (9, 1, 11), "stage counts mismatch")
    early_z = sum(float(row["response_z_mean"]) for row in early) / len(early)
    strong_z = sum(float(row["response_z_mean"]) for row in strong) / len(strong)
    early_run = sum(float(row["response_horizontal_run_px"]) for row in early) / len(early)
    strong_run = sum(float(row["response_horizontal_run_px"]) for row in strong) / len(strong)
    require(strong_z > early_z, "strong stage z did not increase")
    require(strong_run > early_run, "strong stage run did not increase")
    attribution = read_csv(ATTRIBUTION_PATH)
    require(len(attribution) == 6, "attribution category count mismatch")
    require(abs(sum(float(row["pixel_fraction"]) for row in attribution) - 1.0) < 1e-9, "attribution fractions do not sum to one")
    dark = next(row for row in attribution if row["response_category"] == "CURRENTLY_DARK_LATENT_BODY_REGION")
    require(int(dark["pixel_count"]) == 0, "dark latent region was auto-assigned")
    unresolved = next(row for row in attribution if row["response_category"] == "UNRESOLVED_MIXED_RESPONSE")
    require(float(unresolved["pixel_fraction"]) > 0.80, "unresolved fraction unexpectedly low")
    return {
        "early_response_z_mean": early_z,
        "strong_response_z_mean": strong_z,
        "early_horizontal_run_mean_px": early_run,
        "strong_horizontal_run_mean_px": strong_run,
        "unresolved_fraction": float(unresolved["pixel_fraction"]),
    }


def validate_conclusions_and_reports() -> None:
    conclusions = read_csv(CONCLUSION_PATH)
    require(len(conclusions) == 10, "stage conclusion count mismatch")
    actual = {row["conclusion_id"]: row["status"] for row in conclusions}
    require(actual == EXPECTED_CONCLUSIONS, f"conclusion mismatch: {actual}")
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    final_report = FINAL_REPORT_PATH.read_text(encoding="utf-8")
    for text, tokens in (
        (
            protocol,
            (
                "world_residual_motion = ||d_est - d_bg||",
                "No single-point optimum is expected or required",
                "CURRENTLY_DARK_LATENT_BODY_REGION` is not auto-assigned",
            ),
        ),
        (
            final_report,
            (
                "0/20",
                "BACKGROUND_DOMINATED_REGION`：112",
                "MOTION_COHERENT_SUPPORT_CORRIDOR`：0",
                "S1D_READINESS=NOT_READY",
                "没有 weighted score、rank 或 winner",
            ),
        ),
    ):
        for token in tokens:
            require(token in text, f"required report token missing: {token}")


def validate_external_outputs() -> dict[str, Any]:
    visual_manifest = read_csv(OUTPUT_ROOT / "output_manifest.csv")
    require(len(visual_manifest) == 22, "direct visual output manifest count mismatch")
    for row in visual_manifest:
        path = OUTPUT_ROOT / row["relative_path"]
        require(path.is_file(), f"missing visual output: {path}")
        require(sha256_file(path) == row["sha256"], f"visual output SHA mismatch: {path}")
    analysis_manifest = read_csv(ANALYSIS_ROOT / "analysis_output_manifest.csv")
    require(len(analysis_manifest) >= 10, "analysis output manifest unexpectedly small")
    for row in analysis_manifest:
        path = ANALYSIS_ROOT / row["relative_path"]
        require(path.is_file(), f"missing analysis output: {path}")
        require(sha256_file(path) == row["sha256"], f"analysis output SHA mismatch: {path}")
    summary_path = ANALYSIS_ROOT / "analysis_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    require(summary["weighted_score"] == "NOT_COMPUTED", "summary weighted score computed")
    require(summary["rank"] == "NOT_COMPUTED", "summary rank computed")
    require(summary["winner"] == "NOT_COMPUTED", "summary winner computed")
    require(summary["final_box"] == "NOT_COMPUTED", "summary final box computed")
    require(summary["s1d"] == "NOT_ENTERED", "summary entered S1-D")
    return {
        "visual_file_count": len(visual_manifest),
        "analysis_file_count": len(analysis_manifest),
        "analysis_summary_sha256": sha256_file(summary_path),
    }


def main() -> None:
    results = {
        "git": validate_git(),
        "inputs": validate_inputs(),
    }
    validate_direct_review()
    results["background"] = validate_background()
    results["pairs"] = validate_pairs()
    results["offset_categories"] = validate_offset_field()
    validate_counterfactuals()
    results["state_and_attribution"] = validate_state_and_attribution()
    validate_conclusions_and_reports()
    results["external_outputs"] = validate_external_outputs()
    results["forbidden_items_triggered"] = []
    results["status"] = "PASS"
    (ANALYSIS_ROOT / "validation_summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
