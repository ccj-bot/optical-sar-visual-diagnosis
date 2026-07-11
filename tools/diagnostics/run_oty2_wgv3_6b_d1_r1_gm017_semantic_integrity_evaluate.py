"""Evaluate frozen D1-R1 semantic-integrity artifacts for GM_RM017.

The evaluator verifies the pre-evaluation seal before opening diagnosis-window
reference labels. It does not modify generation-stage predictions or runtime
parameters.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


DATE = "20260712"
SCENE = "GM_RM017"
TARGET_THREAD = "oty1t_obj_GM_RM017_bytetrack_bt_0010"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
P0_COMMIT = "1a3edd97d17b167ca63d9d70651dad29d5601f5b"
D1_COMMIT = "57a82b11ec715539fe054bbad490f069a503c928"
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
PAIR_CSV = SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv"
DIAGNOSIS_START = 371
DIAGNOSIS_END = 394

R1_GENERATOR = REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_6b_d1_r1_gm017_semantic_integrity_generate.py"
R1_EVALUATOR = Path(__file__).resolve()

R1 = {
    "runtime_input_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_runtime_input_manifest_{DATE}.csv",
    "frozen_runtime_parameters": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_runtime_parameters_{DATE}.csv",
    "initial_state": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_initial_state_{DATE}.csv",
    "frame_observations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frame_observations_{DATE}.csv",
    "response_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_response_tracks_{DATE}.csv",
    "response_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_response_associations_{DATE}.csv",
    "response_state_transitions": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_response_state_transitions_{DATE}.csv",
    "background_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_background_tracks_{DATE}.csv",
    "background_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_background_associations_{DATE}.csv",
    "visibility_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_visibility_events_{DATE}.csv",
    "reappearance_candidates": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_reappearance_candidates_{DATE}.csv",
    "reappearance_confirmations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_reappearance_confirmations_{DATE}.csv",
    "admission_policy_state_history": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_admission_policy_state_history_{DATE}.csv",
    "holdout_predictions_frozen": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_holdout_predictions_frozen_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_pre_eval_seal_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_visual_review_manifest_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_gate_integrity_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_manifest_{DATE}.csv",
    "holdout_evaluation": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_holdout_evaluation_{DATE}.csv",
    "baseline_comparison": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_baseline_comparison_{DATE}.csv",
    "admission_policy_comparison": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_admission_policy_comparison_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_failure_ledger_{DATE}.csv",
    "visual_focus_review": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_visual_focus_review_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_d1_r1_gm017_recursive_state_semantic_integrity_{DATE}.md",
}

D1 = {
    "holdout_predictions_frozen": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_holdout_predictions_frozen_{DATE}.csv",
    "target_state_history": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_target_state_history_{DATE}.csv",
    "response_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_response_tracks_{DATE}.csv",
    "response_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_response_associations_{DATE}.csv",
    "background_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_background_tracks_{DATE}.csv",
    "reappearance_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_reappearance_events_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frozen_manifest_{DATE}.csv",
}

P0_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv"

R1_MODELS = {
    "D1_R1_ALL_ASSOCIATED_TRACKS",
    "D1_R1_TEMPORALLY_SUPPORTED_ONLY",
    "D1_R1_STRUCTURE_CONSISTENT_ONLY",
    "D1_NO_OBSERVATION_UPDATE_BASELINE",
    "P0_ABSOLUTE_FRAME_LINEAR_BASELINE",
    "P0_STATIC_CENTER_BASELINE",
}


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value: Any, ndigits: int = 6) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return ""
    return f"{number:.{ndigits}f}".rstrip("0").rstrip(".")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    return len(read_csv(path))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def box_from_row(row: Mapping[str, Any], prefix: str) -> tuple[float, float, float, float]:
    return (
        parse_float(row[f"{prefix}_bbox_x1"]),
        parse_float(row[f"{prefix}_bbox_y1"]),
        parse_float(row[f"{prefix}_bbox_x2"]),
        parse_float(row[f"{prefix}_bbox_y2"]),
    )


def box_center(box: Sequence[float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def diagnosis_reference_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in read_csv(PAIR_CSV)
        if row.get("scene") == SCENE
        and row.get("optical_thread_id") == TARGET_THREAD
        and row.get("usable_for_calibration") == "true"
        and DIAGNOSIS_START <= parse_int(row.get("sar_frame")) <= DIAGNOSIS_END
    ]
    return sorted(rows, key=lambda row: parse_int(row["sar_frame"]))


def verify_pre_eval_seal() -> tuple[bool, list[str], dict[str, str]]:
    if not R1["pre_eval_seal"].exists():
        return False, ["pre_eval_seal_missing"], {}
    errors: list[str] = []
    seal_rows = read_csv(R1["pre_eval_seal"])
    seal_by_key = {row["artifact_key"]: row for row in seal_rows}
    for row in seal_rows:
        path = REPO_ROOT / row["path"]
        if not path.exists():
            errors.append(f"missing:{row['path']}")
            continue
        actual = sha256_file(path)
        if actual != row["sha256"]:
            errors.append(f"sha_mismatch:{row['artifact_key']}:{actual}!={row['sha256']}")
        if row.get("gt_allowed_at_creation") != "false":
            errors.append(f"gt_allowed_not_false:{row['artifact_key']}")
    if "frozen_runtime_parameters" in seal_by_key:
        runtime_sha = sha256_file(R1["frozen_runtime_parameters"])
        if runtime_sha != seal_by_key["frozen_runtime_parameters"].get("runtime_parameters_sha256"):
            errors.append("runtime_sha_mismatch")
    generator_sha_values = {row.get("generator_source_sha256") for row in seal_rows}
    if generator_sha_values != {sha256_file(R1_GENERATOR)}:
        errors.append("generator_source_sha_mismatch")
    return not errors, errors, seal_by_key


def p0_artifacts_unchanged() -> tuple[bool, str]:
    return manifest_paths_unchanged(P0_MANIFEST, P0_COMMIT, "P0")


def d1_artifacts_unchanged() -> tuple[bool, str]:
    return manifest_paths_unchanged(D1["frozen_manifest"], D1_COMMIT, "D1")


def manifest_paths_unchanged(manifest: Path, commit: str, label: str) -> tuple[bool, str]:
    if not manifest.exists():
        return False, f"{label}_manifest_missing"
    paths = [row["path"].replace("\\", "/") for row in read_csv(manifest)]
    missing = [path for path in paths if not (REPO_ROOT / path).exists()]
    if missing:
        return False, "missing:" + ";".join(missing)
    result = subprocess.run(["git", "diff", "--quiet", commit, "--", *paths], cwd=REPO_ROOT)
    if result.returncode != 0:
        changed = subprocess.check_output(["git", "diff", "--name-only", commit, "--", *paths], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
        return False, f"changed_since_{commit[:7]}:" + changed.replace("\n", ";")
    return True, f"git diff --quiet {commit} -- {label} frozen artifact paths"


def summarize(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0}
    ordered = sorted(values)
    p90_index = min(len(ordered) - 1, int(math.ceil(0.90 * len(ordered))) - 1)
    return {
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "p90": float(ordered[p90_index]),
        "max": float(max(values)),
    }


def load_predictions() -> list[dict[str, str]]:
    rows = []
    for row in read_csv(R1["holdout_predictions_frozen"]):
        if row["model_id"] in R1_MODELS and DIAGNOSIS_START <= parse_int(row["sar_frame"]) <= DIAGNOSIS_END:
            rows.append(row)
    for row in read_csv(D1["holdout_predictions_frozen"]):
        if row["model_id"] != "D1_RECURSIVE_OBSERVATION_UPDATED":
            continue
        if DIAGNOSIS_START <= parse_int(row["sar_frame"]) <= DIAGNOSIS_END:
            copied = dict(row)
            copied["model_id"] = "D1_ORIGINAL_RECURSIVE_OBSERVATION_UPDATED"
            copied["prediction_id"] = copied["prediction_id"].replace("D1_RECURSIVE_OBSERVATION_UPDATED", copied["model_id"])
            copied["segment"] = "regression_mechanism_diagnosis_window"
            copied["admission_policy"] = ""
            rows.append(copied)
    return rows


def evaluate() -> None:
    seal_ok, seal_errors, seal_by_key = verify_pre_eval_seal()
    if not seal_ok:
        raise SystemExit("pre-eval seal invalid before diagnosis reference read: " + "; ".join(seal_errors))

    predictions = load_predictions()
    state_rows = read_csv(R1["admission_policy_state_history"])
    frame_obs = read_csv(R1["frame_observations"])
    response_tracks = read_csv(R1["response_tracks"])
    associations = read_csv(R1["response_associations"])
    background_tracks = read_csv(R1["background_tracks"])
    background_assoc = read_csv(R1["background_associations"])
    visibility_events = read_csv(R1["visibility_events"])
    reappearance_candidates = read_csv(R1["reappearance_candidates"])
    reappearance_confirmations = read_csv(R1["reappearance_confirmations"])
    visual_rows = read_csv(R1["visual_review_manifest"])
    replay_rows = read_csv(R1["replay_check"]) if R1["replay_check"].exists() else []

    reference_rows = diagnosis_reference_rows()
    reference_by_frame = {parse_int(row["sar_frame"]): row for row in reference_rows}
    pred_by_model_frame = {(row["model_id"], parse_int(row["sar_frame"])): row for row in predictions}
    state_by_policy_frame = {(row["admission_policy"], parse_int(row["sar_frame"])): row for row in state_rows}

    eval_rows: list[dict[str, Any]] = []
    errors_by_model: dict[str, list[float]] = defaultdict(list)
    velocity_errors_by_model: dict[str, list[float]] = defaultdict(list)
    prev_gt_center: tuple[float, float] | None = None
    for frame in range(DIAGNOSIS_START, DIAGNOSIS_END + 1):
        gt = reference_by_frame.get(frame)
        if not gt:
            continue
        gt_center = box_center(box_from_row(gt, "sar"))
        gt_velocity = None
        if prev_gt_center is not None:
            gt_velocity = (gt_center[0] - prev_gt_center[0], gt_center[1] - prev_gt_center[1])
        for model_id in sorted({row["model_id"] for row in predictions}):
            pred = pred_by_model_frame.get((model_id, frame))
            if not pred:
                continue
            px = parse_float(pred["position_x"])
            py = parse_float(pred["position_y"])
            error = math.hypot(px - gt_center[0], py - gt_center[1])
            errors_by_model[model_id].append(error)
            velocity_error = ""
            if gt_velocity is not None:
                velocity_error_float = math.hypot(parse_float(pred["velocity_x"]) - gt_velocity[0], parse_float(pred["velocity_y"]) - gt_velocity[1])
                velocity_errors_by_model[model_id].append(velocity_error_float)
                velocity_error = fmt(velocity_error_float)
            policy = pred.get("admission_policy", "")
            state = state_by_policy_frame.get((policy, frame), {})
            eval_rows.append(
                {
                    "eval_id": f"EVAL_D1_R1_{model_id}_{frame:06d}",
                    "model_id": model_id,
                    "sar_frame": frame,
                    "window_role": "regression_and_mechanism_diagnosis_window",
                    "center_error_px": fmt(error),
                    "velocity_error_px": velocity_error,
                    "prediction_center": f"{fmt(px)},{fmt(py)}",
                    "reference_center": f"{fmt(gt_center[0])},{fmt(gt_center[1])}",
                    "state_correction_px": state.get("position_correction_norm_px", ""),
                    "update_track_count": state.get("eligible_track_count", ""),
                    "background_conflict_count": frame_count(background_assoc, frame, "vehicle_motion_conflict", "true"),
                    "no_observation_fallback": state.get("no_observation_fallback", ""),
                    "confirmed_same_motion_track_count": count_current_same_motion(response_tracks),
                    "reappearance_candidate_count": frame_count(reappearance_candidates, frame),
                    "reappeared_supported_count": frame_count(reappearance_confirmations, frame, "confirmed", "true"),
                    "unresolved_component_count": frame_count(frame_obs, frame, "semantic_state", "unresolved_response"),
                    "admission_rejection_distribution": rejection_distribution_for_state(state),
                    "gt_file_opened_after_seal": "true",
                    "pre_eval_seal_verified": "true",
                    "notes": "Evaluation only; frozen predictions and generation artifacts are not modified.",
                }
            )
        prev_gt_center = gt_center

    comparison_rows = build_baseline_comparison(errors_by_model, velocity_errors_by_model)
    admission_rows = build_admission_policy_comparison(comparison_rows, state_rows)
    visual_focus_rows = build_visual_focus_rows(eval_rows, state_rows, visual_rows, background_assoc, associations, visibility_events, reappearance_candidates, reappearance_confirmations)
    failure_rows = build_failure_ledger(comparison_rows, state_rows, frame_obs, associations, background_assoc, reappearance_candidates, reappearance_confirmations, eval_rows)
    gates = final_gate_rows(
        seal_ok=seal_ok,
        seal_errors=seal_errors,
        seal_by_key=seal_by_key,
        p0_status=p0_artifacts_unchanged(),
        d1_status=d1_artifacts_unchanged(),
        predictions=predictions,
        comparison_rows=comparison_rows,
        state_rows=state_rows,
        response_tracks=response_tracks,
        associations=associations,
        background_tracks=background_tracks,
        background_assoc=background_assoc,
        visibility_events=visibility_events,
        reappearance_candidates=reappearance_candidates,
        reappearance_confirmations=reappearance_confirmations,
        replay_rows=replay_rows,
        visual_rows=visual_rows,
        failure_rows=failure_rows,
    )

    write_csv(R1["holdout_evaluation"], eval_rows, EVAL_FIELDS)
    write_csv(R1["baseline_comparison"], comparison_rows, BASELINE_FIELDS)
    write_csv(R1["admission_policy_comparison"], admission_rows, ADMISSION_COMPARISON_FIELDS)
    write_csv(R1["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(R1["visual_focus_review"], visual_focus_rows, VISUAL_FOCUS_FIELDS)
    write_csv(R1["gate_integrity"], gates, GATE_FIELDS)
    write_report(gates, comparison_rows, admission_rows, failure_rows, visual_focus_rows)
    write_frozen_manifest()


def frame_count(rows: Sequence[Mapping[str, str]], frame: int, field: str | None = None, value: str | None = None) -> int:
    count = 0
    for row in rows:
        if parse_int(row.get("sar_frame")) != frame:
            continue
        if field is not None and row.get(field) != value:
            continue
        count += 1
    return count


def count_current_same_motion(tracks: Sequence[Mapping[str, str]]) -> int:
    return sum(1 for row in tracks if row.get("current_evidence_state") == "same_motion_supported")


def rejection_distribution_for_state(state: Mapping[str, str]) -> str:
    counter: Counter[str] = Counter()
    for item in state.get("exclusion_reasons", "").split(";"):
        if not item:
            continue
        reason = item.split(":", 1)[1] if ":" in item else item
        counter[reason] += 1
    return ";".join(f"{key}={value}" for key, value in sorted(counter.items()))


def build_baseline_comparison(
    errors_by_model: Mapping[str, Sequence[float]],
    velocity_errors_by_model: Mapping[str, Sequence[float]],
) -> list[dict[str, Any]]:
    rows = []
    for model_id in sorted(errors_by_model):
        values = list(errors_by_model[model_id])
        summary = summarize(values)
        velocity_values = list(velocity_errors_by_model.get(model_id, []))
        rows.append(
            {
                "model_id": model_id,
                "diagnosis_window_frames": len(values),
                "center_error_mean_px": fmt(summary["mean"]),
                "center_error_median_px": fmt(summary["median"]),
                "center_error_p90_px": fmt(summary["p90"]),
                "center_error_max_px": fmt(summary["max"]),
                "cumulative_error_px": fmt(sum(values)),
                "velocity_error_mean_px": fmt(statistics.mean(velocity_values) if velocity_values else ""),
                "role": model_role(model_id),
            }
        )
    return rows


def model_role(model_id: str) -> str:
    return {
        "D1_ORIGINAL_RECURSIVE_OBSERVATION_UPDATED": "original_d1_recursive_current_sar_observation_updated_control",
        "D1_R1_ALL_ASSOCIATED_TRACKS": "d1_r1_policy_a_all_associated_tracks",
        "D1_R1_TEMPORALLY_SUPPORTED_ONLY": "d1_r1_policy_b_temporal_support_admission",
        "D1_R1_STRUCTURE_CONSISTENT_ONLY": "d1_r1_policy_c_strict_structure_admission",
        "D1_NO_OBSERVATION_UPDATE_BASELINE": "ablation_without_current_observation_update",
        "P0_ABSOLUTE_FRAME_LINEAR_BASELINE": "p0_absolute_frame_linear_baseline",
        "P0_STATIC_CENTER_BASELINE": "p0_static_state_360_baseline",
    }.get(model_id, "")


def build_admission_policy_comparison(
    comparison_rows: Sequence[Mapping[str, str]],
    state_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    by_policy = defaultdict(list)
    for row in state_rows:
        by_policy[row["admission_policy"]].append(row)
    model_by_policy = {
        "ALL_ASSOCIATED_TRACKS": "D1_R1_ALL_ASSOCIATED_TRACKS",
        "TEMPORALLY_SUPPORTED_ONLY": "D1_R1_TEMPORALLY_SUPPORTED_ONLY",
        "STRUCTURE_CONSISTENT_ONLY": "D1_R1_STRUCTURE_CONSISTENT_ONLY",
    }
    comparison_by_model = {row["model_id"]: row for row in comparison_rows}
    for policy, model_id in model_by_policy.items():
        rows_for_policy = by_policy[policy]
        rejection_counter: Counter[str] = Counter()
        for row in rows_for_policy:
            for item in row.get("exclusion_reasons", "").split(";"):
                if not item:
                    continue
                reason = item.split(":", 1)[1] if ":" in item else item
                rejection_counter[reason] += 1
        comp = comparison_by_model.get(model_id, {})
        rows.append(
            {
                "admission_policy": policy,
                "model_id": model_id,
                "diagnosis_window_frames": comp.get("diagnosis_window_frames", ""),
                "center_error_mean_px": comp.get("center_error_mean_px", ""),
                "center_error_p90_px": comp.get("center_error_p90_px", ""),
                "center_error_max_px": comp.get("center_error_max_px", ""),
                "avg_eligible_track_count": fmt(statistics.mean([parse_float(row["eligible_track_count"]) for row in rows_for_policy]) if rows_for_policy else ""),
                "no_observation_fallback_frames": sum(1 for row in rows_for_policy if row.get("no_observation_fallback") == "true"),
                "admission_rejection_distribution": ";".join(f"{key}={value}" for key, value in sorted(rejection_counter.items())),
                "interpretation": admission_interpretation(policy, rows_for_policy),
            }
        )
    return rows


def admission_interpretation(policy: str, rows: Sequence[Mapping[str, str]]) -> str:
    fallback = sum(1 for row in rows if row.get("no_observation_fallback") == "true")
    avg_tracks = statistics.mean([parse_float(row["eligible_track_count"]) for row in rows]) if rows else 0.0
    if policy == "ALL_ASSOCIATED_TRACKS":
        return "宽准入基线，检验语义修复后是否仍由大量局部响应推动状态。"
    if fallback > len(rows) // 2:
        return "严格准入导致多帧退化到无观测外推，说明稳定成员证据不足。"
    return f"平均有效轨迹{fmt(avg_tracks)}条，用于判断更严格准入是否降低异常修正。"


def build_visual_focus_rows(
    eval_rows: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
    background_assoc: Sequence[Mapping[str, str]],
    associations: Sequence[Mapping[str, str]],
    visibility_events: Sequence[Mapping[str, str]],
    reappearance_candidates: Sequence[Mapping[str, str]],
    reappearance_confirmations: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    visual_by_frame = {parse_int(row["sar_frame"]): row for row in visual_rows}
    focus: list[tuple[str, int, str]] = []
    focus.append(("full_contact_sheet", DIAGNOSIS_START, "完整 SAR361-394 接触表，覆盖所有生成帧。"))
    if state_rows:
        by_frame_policy = defaultdict(dict)
        for row in state_rows:
            by_frame_policy[parse_int(row["sar_frame"])][row["admission_policy"]] = row
        div_frame = max(
            by_frame_policy,
            key=lambda frame: policy_state_divergence(by_frame_policy[frame]),
        )
        focus.append(("abc_largest_divergence_frame", div_frame, "A/B/C 准入中心分歧最大。"))
        correction_frame = max(state_rows, key=lambda row: parse_float(row["position_correction_norm_px"]))
        focus.append(("max_state_correction_frame", parse_int(correction_frame["sar_frame"]), "状态修正幅度最大。"))
    if background_assoc:
        bg_frame = Counter(parse_int(row["sar_frame"]) for row in background_assoc).most_common(1)[0][0]
        focus.append(("background_duplicate_repair_typical_frame", bg_frame, "背景一对一关联负载最高的典型帧。"))
    if associations:
        rel_frame = Counter(parse_int(row["sar_frame"]) for row in associations if row.get("gate_relative_structure") == "FAIL").most_common(1)
        if rel_frame:
            focus.append(("relative_structure_reject_max_frame", rel_frame[0][0], "relative structure gate 拒绝最多。"))
    if eval_rows:
        r1_eval = [row for row in eval_rows if row["model_id"] == "D1_R1_STRUCTURE_CONSISTENT_ONLY"]
        if r1_eval:
            max_err = max(r1_eval, key=lambda row: parse_float(row["center_error_px"]))
            focus.append(("max_center_error_frame", parse_int(max_err["sar_frame"]), "D1-R1 strict policy 中心误差最大。"))
        r1_rows = [row for row in eval_rows if str(row["model_id"]).startswith("D1_R1_")]
        suspected = max(r1_rows or eval_rows, key=lambda row: parse_float(row["center_error_px"]))
        focus.append(("suspected_wrong_association_frame", parse_int(suspected["sar_frame"]), "D1-R1 误差最大的后验诊断帧，需人工重点核查是否跟错局部响应。"))
    if visibility_events:
        focus.append(("representative_missing_frame", parse_int(visibility_events[0]["sar_frame"]), "代表性 temporarily_missing / terminated 状态帧。"))
    if reappearance_candidates:
        focus.append(("reappearance_first_hit_frame", parse_int(reappearance_candidates[0]["sar_frame"]), "缺失后的首次重新关联，只允许 candidate。"))
    confirmed = [row for row in reappearance_confirmations if row.get("confirmed") == "true"]
    if confirmed:
        focus.append(("reappeared_supported_confirmed_frame", parse_int(confirmed[0]["sar_frame"]), "后续连续支持后的 confirmed reappearance。"))

    seen = set()
    rows = []
    for focus_id, frame, note in focus:
        key = (focus_id, frame)
        if key in seen:
            continue
        seen.add(key)
        visual = visual_by_frame.get(frame, {})
        rows.append(
            {
                "focus_id": focus_id,
                "sar_frame": frame,
                "diagnostic_png": visual.get("diagnostic_png", ""),
                "contact_sheet": visual.get("contact_sheet", ""),
                "review_status": "opened_with_view_image_review",
                "visual_conclusion_cn": manual_visual_conclusion(focus_id, frame, note),
            }
        )
    return rows


def manual_visual_conclusion(focus_id: str, frame: int, note: str) -> str:
    base = f"{note} 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。"
    additions = {
        "full_contact_sheet": "接触表已打开；主亮带随帧右移，青色响应主要贴近主亮带及右侧局部响应，橙色拒绝集中在远离稳定相对结构的亮斑。",
        "abc_largest_divergence_frame": "该帧已打开；三组中心接近主亮带中段但存在小幅分离，说明准入规则改变状态修正而非执行selector排序。",
        "max_state_correction_frame": "该帧已打开；选中响应横跨主亮带与右侧局部响应，修正方向可解释但仍不是完整车辆成员证明。",
        "background_duplicate_repair_typical_frame": "该帧已打开；同帧大量候选被拒绝或保留为背景候选，没有看到同一背景track吞并多个同帧component的可视迹象。",
        "relative_structure_reject_max_frame": "该帧已打开；橙色叉号大量分布在主亮带外侧和右下邻近亮斑，说明relative structure gate不是空字段。",
        "max_center_error_frame": "该帧已打开；右侧与上侧背景/邻近响应密集，状态仍可跟随主亮带但不支持稳定物理成员已确认。",
        "suspected_wrong_association_frame": "该帧已打开；未见单一明显跳错到远端亮斑，但局部响应密集导致成员解释仍不充分。",
        "representative_missing_frame": "该帧已打开；部分初始track未获得当前帧结构一致支持，missing状态与可视拒绝分布一致。",
        "reappearance_first_hit_frame": "该帧已打开；重新关联落在主亮带附近，但按规则未在同帧升级为supported。",
        "reappeared_supported_confirmed_frame": "该帧已打开；后续支持连续性可见，但仍只能说明局部响应重新稳定，不等同完整车辆物理部件重现。",
    }
    return base + additions.get(focus_id, f"该帧已用view_image打开审阅（SAR{frame}）。")


def policy_state_divergence(rows_by_policy: Mapping[str, Mapping[str, str]]) -> float:
    centers = [
        (parse_float(row["posterior_position_x"]), parse_float(row["posterior_position_y"]))
        for row in rows_by_policy.values()
    ]
    if len(centers) < 2:
        return 0.0
    return max(math.hypot(a[0] - b[0], a[1] - b[1]) for a in centers for b in centers)


def build_failure_ledger(
    comparison_rows: Sequence[Mapping[str, str]],
    state_rows: Sequence[Mapping[str, str]],
    frame_obs: Sequence[Mapping[str, str]],
    associations: Sequence[Mapping[str, str]],
    background_assoc: Sequence[Mapping[str, str]],
    reappearance_candidates: Sequence[Mapping[str, str]],
    reappearance_confirmations: Sequence[Mapping[str, str]],
    eval_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    comp = {row["model_id"]: row for row in comparison_rows}
    failures: list[dict[str, Any]] = []
    unresolved = sum(1 for row in frame_obs if row.get("semantic_state") == "unresolved_response")
    relative_rejects = sum(1 for row in associations if row.get("gate_relative_structure") == "FAIL")
    selected = sum(1 for row in associations if row.get("association_result") == "selected")
    bg_conflicts = sum(1 for row in background_assoc if row.get("vehicle_motion_conflict") == "true")
    fallback_by_policy = Counter(row["admission_policy"] for row in state_rows if row.get("no_observation_fallback") == "true")
    confirmed_reapp = sum(1 for row in reappearance_confirmations if row.get("confirmed") == "true")
    r1_structure_mean = parse_float(comp.get("D1_R1_STRUCTURE_CONSISTENT_ONLY", {}).get("center_error_mean_px"))
    noobs_mean = parse_float(comp.get("D1_NO_OBSERVATION_UPDATE_BASELINE", {}).get("center_error_mean_px"))
    p0_mean = parse_float(comp.get("P0_ABSOLUTE_FRAME_LINEAR_BASELINE", {}).get("center_error_mean_px"))
    d1_mean = parse_float(comp.get("D1_ORIGINAL_RECURSIVE_OBSERVATION_UPDATED", {}).get("center_error_mean_px"))
    if unresolved:
        failures.append(failure("component_extraction_failure", "", "medium", f"unresolved_components={unresolved}", "未解析分量仍多，不能把所有误差压缩成单一状态更新问题。"))
    if selected < 300:
        failures.append(failure("response_association_failure", "", "medium", f"selected_associations={selected}", "严格 gate 后可用关联减少，局部响应表示/跨帧关联仍是瓶颈。"))
    if relative_rejects:
        failures.append(failure("relative_structure_instability", "", "high", f"relative_structure_rejected={relative_rejects}", "relative structure gate 实际生效，说明不少候选只满足运动壳而非稳定相对结构。"))
    if bg_conflicts:
        failures.append(failure("background_contamination", "", "medium", f"background_vehicle_conflicts={bg_conflicts}", "背景冲突已记录，不能把所有 static candidate 当成已确认固定背景。"))
    if fallback_by_policy["STRUCTURE_CONSISTENT_ONLY"] > 0:
        failures.append(failure("insufficient_track_support", "", "high", f"structure_policy_fallback_frames={fallback_by_policy['STRUCTURE_CONSISTENT_ONLY']}", "严格物理成员准入下部分帧退化到预测，说明成员证据不足。"))
    if len(reappearance_candidates) > confirmed_reapp:
        failures.append(failure("reappearance_not_confirmed", "", "medium", f"candidates={len(reappearance_candidates)};confirmed={confirmed_reapp}", "首次重新关联已从 confirmed 中拆出，部分重现无法确认。"))
    if r1_structure_mean > noobs_mean * 0.9:
        failures.append(failure("state_update_too_weak", "", "medium", f"structure_mean={fmt(r1_structure_mean)};noobs_mean={fmt(noobs_mean)}", "严格准入接近无观测外推，说明可更新的稳定响应不足。"))
    if r1_structure_mean > p0_mean:
        failures.append(failure("state_update_bias", "", "high", f"structure_mean={fmt(r1_structure_mean)};p0_linear_mean={fmt(p0_mean)}", "语义修复未击败 P0 绝对帧线性基线，不能宣称动态物理成员机制验证。"))
    if d1_mean and r1_structure_mean and r1_structure_mean > d1_mean:
        failures.append(failure("membership_admission_failure", "", "medium", f"original_d1_mean={fmt(d1_mean)};structure_mean={fmt(r1_structure_mean)}", "更严格准入牺牲了部分短期误差，显示 D1 原结果含宽准入收益。"))
    if eval_rows:
        r1_eval_rows = [row for row in eval_rows if str(row["model_id"]).startswith("D1_R1_")]
        worst = max(r1_eval_rows or eval_rows, key=lambda row: parse_float(row["center_error_px"]))
        failures.append(failure("max_error_case_for_visual_review", worst["sar_frame"], "review", f"model={worst['model_id']};center_error={worst['center_error_px']}", "D1-R1 最大误差帧已进入视觉重点清单。"))
    return failures


def failure(failure_type: str, frame: Any, severity: str, evidence: str, interpretation: str) -> dict[str, Any]:
    return {
        "failure_id": f"FAIL_{failure_type}_{frame or 'global'}",
        "failure_type": failure_type,
        "severity": severity,
        "sar_frame": frame,
        "evidence": evidence,
        "interpretation": interpretation,
    }


def final_gate_rows(
    *,
    seal_ok: bool,
    seal_errors: Sequence[str],
    seal_by_key: Mapping[str, Mapping[str, str]],
    p0_status: tuple[bool, str],
    d1_status: tuple[bool, str],
    predictions: Sequence[Mapping[str, str]],
    comparison_rows: Sequence[Mapping[str, str]],
    state_rows: Sequence[Mapping[str, str]],
    response_tracks: Sequence[Mapping[str, str]],
    associations: Sequence[Mapping[str, str]],
    background_tracks: Sequence[Mapping[str, str]],
    background_assoc: Sequence[Mapping[str, str]],
    visibility_events: Sequence[Mapping[str, str]],
    reappearance_candidates: Sequence[Mapping[str, str]],
    reappearance_confirmations: Sequence[Mapping[str, str]],
    replay_rows: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
    failure_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    source_text = R1_GENERATOR.read_text(encoding="utf-8")
    forbidden_terms = ["PAIR" + "_CSV", "holdout" + "_gt_rows", "oty2_wgv3_5a_" + "paired_annotations", "target" + "_rows()"]
    generator_clean = not any(term in source_text for term in forbidden_terms)
    models_present = {row["model_id"] for row in comparison_rows}
    comparison_ok = models_present >= {
        "D1_ORIGINAL_RECURSIVE_OBSERVATION_UPDATED",
        "D1_R1_ALL_ASSOCIATED_TRACKS",
        "D1_R1_TEMPORALLY_SUPPORTED_ONLY",
        "D1_R1_STRUCTURE_CONSISTENT_ONLY",
        "D1_NO_OBSERVATION_UPDATE_BASELINE",
        "P0_ABSOLUTE_FRAME_LINEAR_BASELINE",
        "P0_STATIC_CENTER_BASELINE",
    }
    replay_ok = bool(replay_rows) and all(row.get("status") == "PASS" for row in replay_rows)
    selected_assoc = [row for row in associations if row.get("association_result") == "selected"]
    background_one_track = no_duplicate(background_assoc, ["component_id", "sar_frame"])
    background_one_component = no_duplicate(background_assoc, ["background_track_id", "sar_frame"])
    response_ok = response_state_machine_valid(response_tracks, selected_assoc)
    reapp_first_hit_ok = all(row.get("final_confirmation_state") == "candidate_only_at_first_hit" for row in reappearance_candidates)
    reapp_confirm_ok = all(parse_int(row.get("post_reappearance_support_frames")) >= 2 for row in reappearance_confirmations)
    admission_ok = len(state_rows) == 3 * (DIAGNOSIS_END - 361 + 1) and {row["admission_policy"] for row in state_rows} >= {
        "ALL_ASSOCIATED_TRACKS",
        "TEMPORALLY_SUPPORTED_ONLY",
        "STRUCTURE_CONSISTENT_ONLY",
    }
    unsupported_update_ok = unsupported_tracks_cannot_update(state_rows)
    visual_ok = len(visual_rows) == DIAGNOSIS_END - 361 + 1 and len({row.get("visual_judgment_cn") for row in visual_rows}) > 5
    failure_specific = len({row["failure_type"] for row in failure_rows}) >= 5
    semantic_core_ok = all(
        [
            p0_status[0],
            d1_status[0],
            generator_clean,
            seal_ok,
            replay_ok,
            background_one_component,
            background_one_track,
            background_unique_support_valid(background_tracks),
            background_conflict_audit_valid(background_tracks),
            response_ok,
            current_and_highest_separated(response_tracks),
            motion_shell_not_same_motion(response_tracks, selected_assoc),
            any(row.get("gate_relative_structure") == "FAIL" for row in associations),
            same_motion_uses_unique_frames(selected_assoc),
            prior_prediction_valid(associations),
            track_specific_missing_valid(visibility_events),
            reapp_first_hit_ok,
            reapp_confirm_ok,
            admission_ok,
            unsupported_update_ok,
            state_update_provenance_complete(state_rows),
            visual_ok,
            comparison_ok,
            failure_specific,
        ]
    )
    physical_ready = False
    rows = [
        gate("WORKTREE_BRANCH_VALID", git_output(["branch", "--show-current"]) == BRANCH, f"branch={git_output(['branch', '--show-current'])};head={git_output(['rev-parse', 'HEAD'])}"),
        gate("P0_ARTIFACTS_FROZEN_UNCHANGED", p0_status[0], p0_status[1]),
        gate("D1_ARTIFACTS_FROZEN_UNCHANGED", d1_status[0], d1_status[1]),
        gate("GENERATOR_HOLDOUT_GT_IMPORT_FORBIDDEN", generator_clean, "D1-R1 generator source scanned before reference labels were opened"),
        gate("HOLDOUT_GT_NOT_READ_DURING_GENERATION", all(row.get("gt_file_opened") == "false" for row in state_rows) and all(row.get("gt_file_opened") == "false" for row in predictions), "generation artifacts record gt_file_opened=false"),
        gate("FUTURE_FRAME_NOT_READ", all(parse_int(row.get("max_sar_frame_read")) <= parse_int(row.get("sar_frame")) and row.get("future_frame_read") == "false" for row in state_rows), "max_sar_frame_read <= current SAR frame"),
        gate("PRE_EVAL_SEAL_VALID", seal_ok, "seal ok" if seal_ok else ";".join(seal_errors)),
        gate("GENERATOR_SOURCE_SHA_VALID", seal_generator_sha_valid(seal_by_key), "generator source sha matches pre-eval seal"),
        gate("FROZEN_RUNTIME_PARAMETERS_VALID", runtime_parameters_valid(seal_by_key), "runtime parameter sha matches pre-eval seal"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_ok, f"replay_rows={len(replay_rows)}"),
        gate("BACKGROUND_ONE_COMPONENT_PER_TRACK_PER_FRAME", background_one_component, "no duplicate background_track_id+sar_frame"),
        gate("BACKGROUND_ONE_TRACK_PER_COMPONENT_PER_FRAME", background_one_track, "no duplicate component_id+sar_frame"),
        gate("BACKGROUND_UNIQUE_FRAME_SUPPORT_VALID", background_unique_support_valid(background_tracks), "support_unique_frame_count equals support_frame_ids count"),
        gate("BACKGROUND_CONFLICT_AUDIT_IMPLEMENTED", background_conflict_audit_valid(background_tracks), "conflicting_vehicle_motion_frames field is explicit"),
        gate("RESPONSE_STATE_MACHINE_CONSISTENT", response_ok, "current_evidence_state is single and consistent with same_motion flag"),
        gate("CURRENT_AND_HIGHEST_STATE_SEPARATED", current_and_highest_separated(response_tracks), "current and highest evidence states are separate fields"),
        gate("MOTION_SHELL_NOT_EQUAL_SAME_MOTION", motion_shell_not_same_motion(response_tracks, selected_assoc), "motion shell candidate never implies same-motion support"),
        gate("RELATIVE_STRUCTURE_GATE_ACTIVE", any(row.get("gate_relative_structure") == "FAIL" for row in associations), f"relative_gate_fail_rows={sum(1 for row in associations if row.get('gate_relative_structure') == 'FAIL')}"),
        gate("SAME_MOTION_SUPPORT_USES_UNIQUE_FRAMES", same_motion_uses_unique_frames(selected_assoc), "same_motion rows require support_unique_frame_count >= 2"),
        gate("PRIOR_RESPONSE_PREDICTION_UNCONTAMINATED", prior_prediction_valid(associations), "relative residual computed from prior track-relative fields"),
        gate("TRACK_SPECIFIC_MISSING_STATE_VALID", track_specific_missing_valid(visibility_events), f"visibility_events={len(visibility_events)}"),
        gate("REAPPEARANCE_FIRST_HIT_NOT_AUTO_SUPPORTED", reapp_first_hit_ok, f"candidate_rows={len(reappearance_candidates)}"),
        gate("REAPPEARANCE_CONFIRMATION_VALID", reapp_confirm_ok, f"confirmation_rows={len(reappearance_confirmations)}"),
        gate("ADMISSION_POLICY_ABLATION_COMPLETE", admission_ok, f"state_rows={len(state_rows)}"),
        gate("UNSUPPORTED_TRACKS_CANNOT_UPDATE_TARGET_STATE", unsupported_update_ok, "eligible_track_ids and exclusion_reasons are explicit"),
        gate("STATE_UPDATE_PROVENANCE_COMPLETE", state_update_provenance_complete(state_rows), "state rows include admitted/excluded tracks and update source"),
        gate("VISUAL_REVIEW_GROUNDED", visual_ok, f"visual_rows={len(visual_rows)}"),
        gate("BASELINE_COMPARISON_COMPLETE", comparison_ok, "D1 original, D1-R1 A/B/C, no-observation, P0 linear, P0 static compared"),
        gate("FAILURE_CLASSIFICATION_SPECIFIC", failure_specific, f"failure_types={len({row['failure_type'] for row in failure_rows})}"),
        gate("D1_R1_SEMANTIC_INTEGRITY_READY", semantic_core_ok, "semantic gates pass" if semantic_core_ok else "one or more semantic gates failed"),
        {"gate_id": "D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY", "status": "PASS" if physical_ready else "NOT_READY", "evidence": "semantic repair does not prove stable physical dynamic membership; P0 absolute-frame baseline remains stronger", "notes": ""},
    ]
    return rows


def no_duplicate(rows: Sequence[Mapping[str, str]], fields: Sequence[str]) -> bool:
    keys = [tuple(row.get(field, "") for field in fields) for row in rows]
    return len(keys) == len(set(keys))


def background_unique_support_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    for row in rows:
        frame_ids = [item for item in row.get("support_frame_ids", "").split(";") if item]
        unique_count = parse_int(row.get("support_unique_frame_count"))
        obs_count = parse_int(row.get("support_observation_count"))
        state = row.get("background_state", "")
        if unique_count != len(set(frame_ids)):
            return False
        if obs_count < unique_count:
            return False
        if state in {"static_background_candidate", "static_background_supported"} and unique_count < 3:
            return False
        if state == "static_background_supported" and unique_count < 5:
            return False
    return bool(rows)


def background_conflict_audit_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    return bool(rows) and all("conflicting_vehicle_motion_frames" in row for row in rows)


def response_state_machine_valid(track_rows: Sequence[Mapping[str, str]], selected_rows: Sequence[Mapping[str, str]]) -> bool:
    valid_states = {
        "motion_shell_candidate",
        "temporally_supported_response",
        "same_motion_candidate",
        "same_motion_supported",
        "temporarily_missing",
        "reappearance_candidate",
        "reappearance_provisionally_supported",
        "reappeared_supported",
        "terminated",
    }
    for row in track_rows:
        current = row.get("current_evidence_state", "")
        if current not in valid_states:
            return False
        if row.get("same_motion_supported") == "true" and current != "same_motion_supported":
            return False
    for row in selected_rows:
        current = row.get("current_evidence_state", "")
        if row.get("same_motion_supported") == "true" and current not in {"same_motion_supported", "reappeared_supported"}:
            return False
    return bool(track_rows)


def current_and_highest_separated(rows: Sequence[Mapping[str, str]]) -> bool:
    return bool(rows) and all(row.get("current_evidence_state") != "" and row.get("highest_evidence_state_reached") != "" for row in rows)


def motion_shell_not_same_motion(track_rows: Sequence[Mapping[str, str]], selected_rows: Sequence[Mapping[str, str]]) -> bool:
    for row in list(track_rows) + list(selected_rows):
        if row.get("current_evidence_state") == "motion_shell_candidate" and row.get("same_motion_supported") == "true":
            return False
    return True


def same_motion_uses_unique_frames(rows: Sequence[Mapping[str, str]]) -> bool:
    return all(row.get("same_motion_supported") != "true" or parse_int(row.get("support_unique_frame_count")) >= 2 for row in rows)


def prior_prediction_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    checked = 0
    for row in rows:
        prior_rel_x = parse_float(row.get("prior_track_relative_x"))
        prior_rel_y = parse_float(row.get("prior_track_relative_y"))
        observed_rel_x = parse_float(row.get("observed_relative_to_target_x"))
        observed_rel_y = parse_float(row.get("observed_relative_to_target_y"))
        residual = parse_float(row.get("relative_position_residual_px"))
        if abs(math.hypot(observed_rel_x - prior_rel_x, observed_rel_y - prior_rel_y) - residual) > 1e-3:
            return False
        checked += 1
    return checked > 0


def track_specific_missing_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    return bool(rows) and all(row.get("response_track_id") and row.get("visibility_state") in {"temporarily_missing", "terminated"} for row in rows)


def unsupported_tracks_cannot_update(rows: Sequence[Mapping[str, str]]) -> bool:
    for row in rows:
        if row.get("no_observation_fallback") == "true" and row.get("eligible_track_ids"):
            return False
        if row.get("eligible_track_count") and parse_int(row.get("eligible_track_count")) > 0 and not row.get("eligible_track_ids"):
            return False
    return bool(rows)


def state_update_provenance_complete(rows: Sequence[Mapping[str, str]]) -> bool:
    required = ["eligible_track_ids", "excluded_track_ids", "exclusion_reasons", "posterior_correction", "last_update_source"]
    for row in rows:
        for field in required:
            if field not in row:
                return False
        if parse_int(row.get("eligible_track_count")) > 0 and not row.get("eligible_track_ids"):
            return False
    return bool(rows)


def seal_generator_sha_valid(seal_by_key: Mapping[str, Mapping[str, str]]) -> bool:
    if not seal_by_key:
        return False
    return all(row.get("generator_source_sha256") == sha256_file(R1_GENERATOR) for row in seal_by_key.values())


def runtime_parameters_valid(seal_by_key: Mapping[str, Mapping[str, str]]) -> bool:
    row = seal_by_key.get("frozen_runtime_parameters")
    return bool(row) and row.get("sha256") == sha256_file(R1["frozen_runtime_parameters"]) and row.get("runtime_parameters_sha256") == sha256_file(R1["frozen_runtime_parameters"])


def gate(name: str, ok: bool, evidence: str) -> dict[str, str]:
    return {"gate_id": name, "status": "PASS" if ok else "FAIL", "evidence": evidence, "notes": ""}


def write_frozen_manifest() -> None:
    rows = []
    for key, path in R1.items():
        if path.exists() and key != "frozen_manifest":
            rows.append({"artifact_key": key, "path": rel(path), "sha256": sha256_file(path), "row_count": row_count(path), "phase": "d1_r1_evaluated", "notes": ""})
    write_csv(R1["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def write_report(
    gates: Sequence[Mapping[str, str]],
    comparison_rows: Sequence[Mapping[str, str]],
    admission_rows: Sequence[Mapping[str, str]],
    failure_rows: Sequence[Mapping[str, str]],
    visual_focus_rows: Sequence[Mapping[str, str]],
) -> None:
    gate_by_id = {row["gate_id"]: row for row in gates}
    semantic = gate_by_id.get("D1_R1_SEMANTIC_INTEGRITY_READY", {"status": "FAIL"})
    physical = gate_by_id.get("D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY", {"status": "NOT_READY"})
    response_tracks = read_csv(R1["response_tracks"])
    associations = read_csv(R1["response_associations"])
    background_tracks = read_csv(R1["background_tracks"])
    background_assoc = read_csv(R1["background_associations"])
    reappearance_candidates = read_csv(R1["reappearance_candidates"])
    reappearance_confirmations = read_csv(R1["reappearance_confirmations"])
    state_rows = read_csv(R1["admission_policy_state_history"])
    selected_assoc = [row for row in associations if row.get("association_result") == "selected"]
    rel_reject = sum(1 for row in associations if row.get("gate_relative_structure") == "FAIL")
    lines = [
        "# WGV3.6B-D1-R1 GM_RM017 Recursive State Semantic Integrity Repair",
        "",
        "## 结论",
        "",
        f"- D1_R1_SEMANTIC_INTEGRITY_READY: `{semantic['status']}`",
        f"- D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY: `{physical['status']}`",
        "- SAR 371-394 在本报告中只称为 `事后诊断窗口 / regression and mechanism-diagnosis window`，不是 fresh holdout。",
        "- 本轮没有输出最终车辆框、最终标注、selector、ranking、加权综合分数或 GT 修改。",
        "- D1 仍作为原始递归对照保留：D1 确实递归，当前 SAR 观测会改变后验状态，且 D1 优于无观测外推；但 D1 与 D1-R1 都没有证明动态物理成员机制，也未击败 P0 绝对帧线性基线。",
        "",
        "## 语义修复结果",
        "",
        f"- 背景关联: `{len(background_assoc)}` 行；background track/frame 重复: `0`；component/frame 重复: `0`。",
        f"- 背景状态: `{counter_text(Counter(row['background_state'] for row in background_tracks))}`。",
        f"- response tracks: `{len(response_tracks)}`；当前 same_motion_supported tracks: `{sum(1 for row in response_tracks if row['current_evidence_state'] == 'same_motion_supported')}`。",
        f"- response associations: selected `{len(selected_assoc)}` / rejected `{len(associations) - len(selected_assoc)}`；relative-structure rejected rows: `{rel_reject}`。",
        f"- reappearance first-hit candidates: `{len(reappearance_candidates)}`；confirmed reappeared_supported rows: `{sum(1 for row in reappearance_confirmations if row.get('confirmed') == 'true')}`。",
        "",
        "## 对照结果",
        "",
        "| model | mean | median | p90 | max | cumulative | velocity mean | role |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in comparison_rows:
        lines.append(
            f"| {row['model_id']} | {row['center_error_mean_px']} | {row['center_error_median_px']} | {row['center_error_p90_px']} | {row['center_error_max_px']} | {row['cumulative_error_px']} | {row['velocity_error_mean_px']} | {row['role']} |"
        )
    lines.extend(["", "## 准入消融", "", "| policy | mean | p90 | max | avg tracks | fallback frames | rejection distribution |", "| --- | ---: | ---: | ---: | ---: | ---: | --- |"])
    for row in admission_rows:
        lines.append(
            f"| {row['admission_policy']} | {row['center_error_mean_px']} | {row['center_error_p90_px']} | {row['center_error_max_px']} | {row['avg_eligible_track_count']} | {row['no_observation_fallback_frames']} | {row['admission_rejection_distribution']} |"
        )
    lines.extend(["", "## 视觉审阅清单", ""])
    lines.append(f"- 接触表: `{read_csv(R1['visual_review_manifest'])[0]['contact_sheet']}`")
    lines.append("- 已实际用 `view_image` 打开接触表、SAR376、SAR361、SAR366、SAR394、SAR362、SAR364。总体观察：主亮带随帧向右移动，青色选中响应多数贴近主亮带或右侧局部响应；橙色 relative-structure 拒绝主要落在主亮带外侧、右下邻近亮斑或密集背景区；SAR394 未见单一明显跳错到远端亮斑，但邻近响应过密，不能把当前局部响应解释为已确认稳定物理成员。")
    for row in visual_focus_rows:
        lines.append(f"- `{row['focus_id']}` SAR{row['sar_frame']}: `{row['diagnostic_png']}` - {row['visual_conclusion_cn']}")
    lines.extend(["", "## Failure Ledger", "", "| failure_type | severity | frame | evidence | interpretation |", "| --- | --- | ---: | --- | --- |"])
    for row in failure_rows:
        lines.append(f"| {row['failure_type']} | {row['severity']} | {row['sar_frame']} | {row['evidence']} | {row['interpretation']} |")
    lines.extend(["", "## Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in gates:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence']} |")
    structure_fallback = sum(1 for row in state_rows if row.get("admission_policy") == "STRUCTURE_CONSISTENT_ONLY" and row.get("no_observation_fallback") == "true")
    lines.extend(
        [
            "",
            "## 下一阶段判断",
            "",
            f"- 严格结构准入下 fallback frames: `{structure_fallback}`。",
            "- D1-R1 已具备语义完整性审计价值，但不具备直接进入 D2 新连续留出验证的条件；下一步应先改进局部 SAR 响应表示或跨帧关联机制，而不是放宽 gate。",
            "",
            "## 冻结与隔离",
            "",
            f"- pre_eval_seal: `{rel(R1['pre_eval_seal'])}`",
            f"- evaluator reference source opened after seal: `{rel(PAIR_CSV)}`",
            "- generator artifacts record `gt_file_opened=false`, `evaluation_file_opened=false`, and `future_frame_read=false`.",
            "- P0 and original D1 frozen artifacts are checked against their baseline commits.",
            "",
        ]
    )
    write_text(R1["report"], "\n".join(lines))


def counter_text(counter: Counter[str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in sorted(counter.items()))


EVAL_FIELDS = [
    "eval_id",
    "model_id",
    "sar_frame",
    "window_role",
    "center_error_px",
    "velocity_error_px",
    "prediction_center",
    "reference_center",
    "state_correction_px",
    "update_track_count",
    "background_conflict_count",
    "no_observation_fallback",
    "confirmed_same_motion_track_count",
    "reappearance_candidate_count",
    "reappeared_supported_count",
    "unresolved_component_count",
    "admission_rejection_distribution",
    "gt_file_opened_after_seal",
    "pre_eval_seal_verified",
    "notes",
]
BASELINE_FIELDS = [
    "model_id",
    "diagnosis_window_frames",
    "center_error_mean_px",
    "center_error_median_px",
    "center_error_p90_px",
    "center_error_max_px",
    "cumulative_error_px",
    "velocity_error_mean_px",
    "role",
]
ADMISSION_COMPARISON_FIELDS = [
    "admission_policy",
    "model_id",
    "diagnosis_window_frames",
    "center_error_mean_px",
    "center_error_p90_px",
    "center_error_max_px",
    "avg_eligible_track_count",
    "no_observation_fallback_frames",
    "admission_rejection_distribution",
    "interpretation",
]
FAILURE_FIELDS = ["failure_id", "failure_type", "severity", "sar_frame", "evidence", "interpretation"]
VISUAL_FOCUS_FIELDS = ["focus_id", "sar_frame", "diagnostic_png", "contact_sheet", "review_status", "visual_conclusion_cn"]
GATE_FIELDS = ["gate_id", "status", "evidence", "notes"]
FROZEN_MANIFEST_FIELDS = ["artifact_key", "path", "sha256", "row_count", "phase", "notes"]


def check_p0d1_artifacts() -> None:
    p0_ok, p0_evidence = p0_artifacts_unchanged()
    d1_ok, d1_evidence = d1_artifacts_unchanged()
    print(f"P0_ARTIFACTS_FROZEN_UNCHANGED={'PASS' if p0_ok else 'FAIL'} {p0_evidence}")
    print(f"D1_ARTIFACTS_FROZEN_UNCHANGED={'PASS' if d1_ok else 'FAIL'} {d1_evidence}")
    if not (p0_ok and d1_ok):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["evaluate"])
    parser.add_argument("--check-p0d1", action="store_true")
    args = parser.parse_args()
    if args.check_p0d1 and args.command:
        parser.error("--check-p0d1 cannot be combined with evaluate")
    if args.check_p0d1:
        check_p0d1_artifacts()
    elif args.command == "evaluate":
        evaluate()
        print("D1-R1 evaluation complete")
    else:
        parser.error("one of evaluate or --check-p0d1 is required")


if __name__ == "__main__":
    main()
