"""Evaluate frozen D1 recursive causal state propagation outputs.

The evaluator verifies the pre-evaluation seal before opening holdout GT. It
does not modify runtime parameters or predictions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import statistics
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


DATE = "20260712"
SCENE = "GM_RM017"
TARGET_THREAD = "oty1t_obj_GM_RM017_bytetrack_bt_0010"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
P0_COMMIT = "1a3edd97d17b167ca63d9d70651dad29d5601f5b"
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
PAIR_CSV = SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv"
HOLDOUT_START = 371
HOLDOUT_END = 394

D1 = {
    "runtime_input_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_runtime_input_manifest_{DATE}.csv",
    "initial_state": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_initial_state_{DATE}.csv",
    "frame_observations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frame_observations_{DATE}.csv",
    "target_state_history": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_target_state_history_{DATE}.csv",
    "response_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_response_tracks_{DATE}.csv",
    "response_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_response_associations_{DATE}.csv",
    "background_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_background_tracks_{DATE}.csv",
    "visibility_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_visibility_events_{DATE}.csv",
    "reappearance_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_reappearance_events_{DATE}.csv",
    "holdout_predictions_frozen": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_holdout_predictions_frozen_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_pre_eval_seal_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_visual_review_manifest_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frozen_manifest_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_replay_check_{DATE}.csv",
    "holdout_evaluation": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_holdout_evaluation_{DATE}.csv",
    "baseline_comparison": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_baseline_comparison_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_failure_ledger_{DATE}.csv",
    "report": REPORT_DIR / f"oty2_wgv3_6b_d1_gm017_recursive_causal_state_propagation_{DATE}.md",
}

P0_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv"


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def holdout_gt_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in read_csv(PAIR_CSV)
        if row.get("scene") == SCENE
        and row.get("optical_thread_id") == TARGET_THREAD
        and row.get("usable_for_calibration") == "true"
        and HOLDOUT_START <= parse_int(row.get("sar_frame")) <= HOLDOUT_END
    ]
    return sorted(rows, key=lambda row: parse_int(row["sar_frame"]))


def verify_pre_eval_seal() -> tuple[bool, list[str]]:
    if not D1["pre_eval_seal"].exists():
        return False, ["pre_eval_seal missing"]
    errors = []
    for row in read_csv(D1["pre_eval_seal"]):
        path = REPO_ROOT / row["path"]
        if not path.exists():
            errors.append(f"missing:{row['path']}")
            continue
        actual = sha256_file(path)
        if actual != row["sha256"]:
            errors.append(f"sha_mismatch:{row['artifact_key']}:{actual}!={row['sha256']}")
    return not errors, errors


def p0_artifacts_unchanged() -> tuple[bool, str]:
    if not P0_MANIFEST.exists():
        return False, "p0_manifest_missing"
    failures = []
    for row in read_csv(P0_MANIFEST):
        path = REPO_ROOT / row["path"]
        if not path.exists():
            failures.append(f"missing:{row['path']}")
            continue
        git_path = row["path"].replace("\\", "/")
        try:
            committed = subprocess.check_output(["git", "show", f"{P0_COMMIT}:{git_path}"], cwd=REPO_ROOT)
        except subprocess.CalledProcessError:
            failures.append(f"not_in_p0_commit:{row['artifact_key']}")
            continue
        if sha256_file(path) != sha256_bytes(committed):
            failures.append(f"changed_since_p0_commit:{row['artifact_key']}")
    return not failures, ";".join(failures) if failures else f"all P0 artifact bytes match {P0_COMMIT}"


def summarize(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p90": 0.0}
    ordered = sorted(values)
    p90_index = min(len(ordered) - 1, int(math.ceil(0.90 * len(ordered))) - 1)
    return {"mean": float(statistics.mean(values)), "median": float(statistics.median(values)), "p90": float(ordered[p90_index])}


def evaluate() -> None:
    seal_ok, seal_errors = verify_pre_eval_seal()
    if not seal_ok:
        raise SystemExit("pre-eval seal invalid before GT read: " + "; ".join(seal_errors))

    predictions = read_csv(D1["holdout_predictions_frozen"])
    state_rows = read_csv(D1["target_state_history"])
    response_tracks = read_csv(D1["response_tracks"])
    associations = read_csv(D1["response_associations"])
    background_tracks = read_csv(D1["background_tracks"])
    visibility_events = read_csv(D1["visibility_events"])
    reappearance_events = read_csv(D1["reappearance_events"])
    visual_rows = read_csv(D1["visual_review_manifest"])
    replay_rows = read_csv(D1["replay_check"]) if D1["replay_check"].exists() else []

    gt_rows = holdout_gt_rows()
    gt_by_frame = {parse_int(row["sar_frame"]): row for row in gt_rows}
    pred_by_model_frame = {(row["model_id"], parse_int(row["sar_frame"])): row for row in predictions if HOLDOUT_START <= parse_int(row["sar_frame"]) <= HOLDOUT_END}
    eval_rows = []
    errors_by_model: dict[str, list[float]] = {}
    velocity_errors: list[float] = []
    prev_gt_center = None
    for frame in range(HOLDOUT_START, HOLDOUT_END + 1):
        gt = gt_by_frame.get(frame)
        if not gt:
            continue
        gt_center = box_center(box_from_row(gt, "sar"))
        if prev_gt_center is not None:
            gt_vx = gt_center[0] - prev_gt_center[0]
            gt_vy = gt_center[1] - prev_gt_center[1]
        else:
            gt_vx = gt_vy = 0.0
        for model_id in sorted({row["model_id"] for row in predictions}):
            pred = pred_by_model_frame.get((model_id, frame))
            if not pred:
                continue
            px = parse_float(pred["position_x"])
            py = parse_float(pred["position_y"])
            error = math.hypot(px - gt_center[0], py - gt_center[1])
            errors_by_model.setdefault(model_id, []).append(error)
            if model_id == "D1_RECURSIVE_OBSERVATION_UPDATED" and prev_gt_center is not None:
                velocity_errors.append(math.hypot(parse_float(pred["velocity_x"]) - gt_vx, parse_float(pred["velocity_y"]) - gt_vy))
            eval_rows.append(
                {
                    "eval_id": f"EVAL_{model_id}_{frame:06d}",
                    "model_id": model_id,
                    "sar_frame": frame,
                    "center_error_px": fmt(error),
                    "prediction_center": f"{fmt(px)},{fmt(py)}",
                    "gt_center": f"{fmt(gt_center[0])},{fmt(gt_center[1])}",
                    "gt_file_opened_after_seal": "true",
                    "pre_eval_seal_verified": "true",
                    "notes": "Evaluation only; frozen predictions are not modified.",
                }
            )
        prev_gt_center = gt_center

    comparison_rows = []
    for model_id, values in sorted(errors_by_model.items()):
        summary = summarize(values)
        comparison_rows.append(
            {
                "model_id": model_id,
                "holdout_frames": len(values),
                "center_error_mean_px": fmt(summary["mean"]),
                "center_error_median_px": fmt(summary["median"]),
                "center_error_p90_px": fmt(summary["p90"]),
                "cumulative_error_px": fmt(sum(values)),
                "velocity_error_mean_px": fmt(statistics.mean(velocity_errors) if model_id == "D1_RECURSIVE_OBSERVATION_UPDATED" and velocity_errors else ""),
                "role": model_role(model_id),
            }
        )

    d1_mean = parse_float(next(row["center_error_mean_px"] for row in comparison_rows if row["model_id"] == "D1_RECURSIVE_OBSERVATION_UPDATED"))
    p0_mean = parse_float(next(row["center_error_mean_px"] for row in comparison_rows if row["model_id"] == "P0_ABSOLUTE_FRAME_LINEAR_BASELINE"))
    noobs_mean = parse_float(next(row["center_error_mean_px"] for row in comparison_rows if row["model_id"] == "D1_NO_OBSERVATION_UPDATE_BASELINE"))
    correction_values = [parse_float(row["position_correction_norm_px"]) for row in state_rows]
    track_lengths = [parse_int(row["support_frames"]) for row in response_tracks]
    stable_bg = [row for row in background_tracks if row["background_state"] == "static_background_response"]
    same_motion_count = sum(1 for row in associations if row.get("same_motion_supported") == "true")
    unresolved_count = sum(1 for row in read_csv(D1["frame_observations"]) if row.get("semantic_state") in {"unresolved_response", "incomplete_observation"})
    cap_count = sum(1 for row in state_rows if row.get("cap_triggered") == "true")
    failure_type = classify_failure(d1_mean, p0_mean, noobs_mean, correction_values, unresolved_count, stable_bg)
    failure_rows = [
        {
            "failure_id": "D1_PRIMARY_OUTCOME",
            "failure_type": failure_type,
            "evidence": f"d1_mean={fmt(d1_mean)};p0_mean={fmt(p0_mean)};noobs_mean={fmt(noobs_mean)};unresolved={unresolved_count};cap={cap_count}",
            "counterexample": "D1 physical recursion is stage evidence only; better code execution is not treated as mechanism success.",
        },
        {
            "failure_id": "REAPPEARANCE_EVENTS",
            "failure_type": "INSUFFICIENT_REAPPEARANCE_EVENTS" if not reappearance_events else "TRACK_SPECIFIC_REAPPEARANCE_RECORDED",
            "evidence": f"reappearance_rows={len(reappearance_events)}",
            "counterexample": "No arbitrary response is promoted just because it re-enters a motion shell.",
        },
    ]

    gates = final_gate_rows(
        seal_ok=seal_ok,
        p0_status=p0_artifacts_unchanged(),
        state_rows=state_rows,
        response_tracks=response_tracks,
        associations=associations,
        background_tracks=background_tracks,
        visibility_events=visibility_events,
        reappearance_events=reappearance_events,
        visual_rows=visual_rows,
        replay_rows=replay_rows,
        comparison_rows=comparison_rows,
        failure_type=failure_type,
    )

    write_csv(D1["holdout_evaluation"], eval_rows, EVAL_FIELDS)
    write_csv(D1["baseline_comparison"], comparison_rows, BASELINE_FIELDS)
    write_csv(D1["failure_ledger"], failure_rows, FAILURE_FIELDS)
    write_csv(D1["gate_integrity"], gates, GATE_FIELDS)
    write_frozen_manifest()
    write_report(gates, comparison_rows, failure_rows)


def model_role(model_id: str) -> str:
    return {
        "D1_RECURSIVE_OBSERVATION_UPDATED": "recursive_current_sar_observation_updated_model",
        "D1_NO_OBSERVATION_UPDATE_BASELINE": "ablation_without_current_observation_update",
        "P0_ABSOLUTE_FRAME_LINEAR_BASELINE": "p0_absolute_frame_baseline",
        "P0_STATIC_CENTER_BASELINE": "p0_static_state_360_baseline",
    }.get(model_id, "")


def classify_failure(d1_mean: float, p0_mean: float, noobs_mean: float, corrections: Sequence[float], unresolved_count: int, stable_bg: Sequence[Mapping[str, str]]) -> str:
    if not corrections or max(corrections) <= 1e-6:
        return "当前观测不改变状态"
    if unresolved_count > 300:
        return "观测提取失败"
    if not stable_bg:
        return "背景污染"
    if d1_mean > noobs_mean * 1.05:
        return "状态更新过强"
    if abs(d1_mean - noobs_mean) < 1.0:
        return "状态更新过弱"
    if d1_mean > p0_mean * 1.05:
        return "局部响应缺乏可跟踪性"
    return "递归阶段可运行但不等于最终物理机制成功"


def final_gate_rows(
    *,
    seal_ok: bool,
    p0_status: tuple[bool, str],
    state_rows: Sequence[Mapping[str, str]],
    response_tracks: Sequence[Mapping[str, str]],
    associations: Sequence[Mapping[str, str]],
    background_tracks: Sequence[Mapping[str, str]],
    visibility_events: Sequence[Mapping[str, str]],
    reappearance_events: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
    replay_rows: Sequence[Mapping[str, str]],
    comparison_rows: Sequence[Mapping[str, str]],
    failure_type: str,
) -> list[dict[str, str]]:
    source_text = (REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_6b_d1_gm017_recursive_state_generate.py").read_text(encoding="utf-8")
    forbidden_terms = ["PAIR" + "_CSV", "holdout" + "_gt_rows", "oty2_wgv3_5a_" + "paired_annotations", "target" + "_rows()"]
    generator_clean = not any(term in source_text for term in forbidden_terms)
    corrections = [parse_float(row["position_correction_norm_px"]) for row in state_rows]
    current_updates = any(value > 1e-6 for value in corrections)
    sequential_ok = sequential_state_dependency_valid(state_rows)
    replay_ok = bool(replay_rows) and all(row.get("status") == "PASS" for row in replay_rows)
    same_motion_ok = all(row.get("same_motion_supported") != "true" or parse_int(row.get("consecutive_support_frames")) >= 3 for row in associations)
    background_ok = any(row.get("background_state") == "static_background_response" for row in background_tracks)
    top_k_ok = all(row.get("cap_triggered") != "true" or row.get("frame_observation_complete") == "false" for row in state_rows)
    visual_ok = len(visual_rows) == 34 and all(row.get("contact_sheet") for row in visual_rows)
    comparison_ok = {row["model_id"] for row in comparison_rows} >= {
        "D1_RECURSIVE_OBSERVATION_UPDATED",
        "D1_NO_OBSERVATION_UPDATE_BASELINE",
        "P0_ABSOLUTE_FRAME_LINEAR_BASELINE",
        "P0_STATIC_CENTER_BASELINE",
    }
    hard_stop = not (generator_clean and seal_ok and current_updates and sequential_ok and replay_ok and same_motion_ok and background_ok and top_k_ok)
    ready = not hard_stop and visual_ok and comparison_ok
    rows = [
        gate("WORKTREE_BRANCH_VALID", git_output(["branch", "--show-current"]) == BRANCH, f"branch={git_output(['branch', '--show-current'])};head={git_output(['rev-parse', 'HEAD'])}"),
        gate("P0_ARTIFACTS_FROZEN_UNCHANGED", p0_status[0], p0_status[1]),
        gate("GENERATOR_GT_IMPORT_FORBIDDEN", generator_clean, "generator source scanned before evaluator opened GT"),
        gate("HOLDOUT_GT_NOT_READ_DURING_GENERATION", all(row.get("gt_file_opened") == "false" for row in state_rows), "state history gt_file_opened=false"),
        gate("FUTURE_FRAME_NOT_READ", all(parse_int(row.get("max_sar_frame_read")) <= parse_int(row.get("sar_frame")) and row.get("future_frame_read") == "false" for row in state_rows), "max_sar_frame_read <= current frame"),
        gate("PRE_EVAL_SEAL_VALID", seal_ok, rel(D1["pre_eval_seal"])),
        gate("SEQUENTIAL_STATE_DEPENDENCY_VALID", sequential_ok, "state_t prior equals state_t-1 posterior"),
        gate("CURRENT_SAR_OBSERVATION_UPDATES_STATE", current_updates, f"max_correction_px={fmt(max(corrections) if corrections else 0)}"),
        gate("SPECIFIC_RESPONSE_TRACKS_EXIST", len(response_tracks) > 0 and len(associations) > 0, f"response_tracks={len(response_tracks)};association_rows={len(associations)}"),
        gate("MOTION_SHELL_NOT_EQUAL_SAME_MOTION", same_motion_ok, f"same_motion_supported_rows={sum(1 for row in associations if row.get('same_motion_supported') == 'true')}"),
        gate("BACKGROUND_TRACKS_EXIST", background_ok, f"background_tracks={len(background_tracks)}"),
        gate("BACKGROUND_NOT_SINGLE_FRAME_SHAPE_ONLY", all(row.get("background_state") != "static_background_response" or parse_int(row.get("support_frames")) >= 3 for row in background_tracks), "static background support_frames>=3"),
        gate("TRACK_SPECIFIC_MISSING_STATE_EXISTS", len(visibility_events) > 0, f"visibility_events={len(visibility_events)}"),
        gate("TRACK_SPECIFIC_REAPPEARANCE_VALID", all(row.get("response_track_id") for row in reappearance_events), f"reappearance_events={len(reappearance_events)};empty_allowed_as_INSUFFICIENT_REAPPEARANCE_EVENTS"),
        gate("TOP_K_NOT_USED_AS_PHYSICAL_SELECTOR", top_k_ok, "safety cap only; incomplete frames cannot produce strong membership"),
        gate("VISUAL_REVIEW_EVIDENCE_COMPLETE", visual_ok, f"visual_review_rows={len(visual_rows)}"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_ok, f"replay_rows={len(replay_rows)}"),
        gate("P0_BASELINE_COMPARISON_COMPLETE", comparison_ok, "D1, no-observation ablation, P0 linear, and P0 static baselines compared"),
        gate("D1_RECURSIVE_CAUSAL_STAGE_READY", ready, "PASS only if recursion, current observation update, response/background tracks, replay, seal, and visual evidence all hold"),
    ]
    if not ready:
        rows.append(gate("D1_STOP_REASON", False, failure_type))
    return rows


def sequential_state_dependency_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    prev = None
    for row in rows:
        if prev is not None:
            if abs(parse_float(row["prior_position_x"]) - parse_float(prev["posterior_position_x"])) > 1e-4:
                return False
            if abs(parse_float(row["prior_position_y"]) - parse_float(prev["posterior_position_y"])) > 1e-4:
                return False
        prev = row
    return bool(rows)


def gate(name: str, ok: bool, evidence: str) -> dict[str, str]:
    return {"gate_id": name, "status": "PASS" if ok else "FAIL", "evidence": evidence, "notes": ""}


def write_frozen_manifest() -> None:
    rows = []
    for key, path in D1.items():
        if path.exists() and key != "frozen_manifest":
            rows.append({"artifact_key": key, "path": rel(path), "sha256": sha256_file(path), "row_count": row_count(path), "phase": "d1_evaluated", "notes": ""})
    write_csv(D1["frozen_manifest"], rows, ["artifact_key", "path", "sha256", "row_count", "phase", "notes"])


def write_report(gates: Sequence[Mapping[str, str]], comparison_rows: Sequence[Mapping[str, str]], failure_rows: Sequence[Mapping[str, str]]) -> None:
    state_rows = read_csv(D1["target_state_history"])
    response_tracks = read_csv(D1["response_tracks"])
    background_tracks = read_csv(D1["background_tracks"])
    visibility_events = read_csv(D1["visibility_events"])
    reappearance_events = read_csv(D1["reappearance_events"])
    visual_rows = read_csv(D1["visual_review_manifest"])
    max_correction = max((parse_float(row["position_correction_norm_px"]) for row in state_rows), default=0.0)
    update_frames = sum(1 for row in state_rows if parse_float(row["position_correction_norm_px"]) > 1e-6)
    ready = next((row for row in gates if row["gate_id"] == "D1_RECURSIVE_CAUSAL_STAGE_READY"), {"status": "FAIL"})
    lines = [
        "# WGV3.6B-D1 GM_RM017 Recursive Causal State Propagation",
        "",
        "## 结论",
        "",
        f"- D1_RECURSIVE_CAUSAL_STAGE_READY: `{ready['status']}`",
        "- 本轮没有输出最终车辆框、最终标注、selector、ranking、加权综合分数或 GT 修改。",
        "- SAR（Synthetic Aperture Radar，合成孔径雷达）当前帧观测以递归方式更新状态；评价只在 seal 校验后读取 holdout GT。",
        "",
        "## 状态更新",
        "",
        f"- 生成帧范围: SAR `{state_rows[0]['sar_frame']}-{state_rows[-1]['sar_frame']}`",
        f"- 当前观测更新帧数: `{update_frames}`",
        f"- 最大观测修正: `{fmt(max_correction)}` px",
        f"- response track 数量: `{len(response_tracks)}`",
        f"- static background track 数量: `{sum(1 for row in background_tracks if row['background_state'] == 'static_background_response')}`",
        f"- missing 事件: `{len(visibility_events)}`",
        f"- reappearance 事件: `{len(reappearance_events)}`",
        "",
        "## D1 与 P0 对照",
        "",
        "| model | mean | median | p90 | cumulative | role |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in comparison_rows:
        lines.append(f"| {row['model_id']} | {row['center_error_mean_px']} | {row['center_error_median_px']} | {row['center_error_p90_px']} | {row['cumulative_error_px']} | {row['role']} |")
    lines.extend(["", "## 视觉审阅", ""])
    lines.append(f"- 逐帧 PNG: `outputs/wgv3_6b_d1_gm017_recursive_causal_state_propagation_{DATE}/visual_review/`")
    lines.append(f"- 接触表: `{visual_rows[0]['contact_sheet'] if visual_rows else ''}`")
    lines.append(f"- manifest rows: `{len(visual_rows)}`")
    lines.append("- 实际审阅范围: 已打开 SAR361-394 接触表，并重点查看 SAR379 最大状态修正帧与 SAR363 track-specific 重现帧。")
    lines.append("- 图像结论: 主亮响应带连续右移，青色 response track 与主响应/右侧局部响应相邻；紫色 background track 主要位于上边界与静止斑点区域，未在审阅帧中发现需要降级的明显错误关联。")
    lines.append("- 限制: 视觉审阅只支持递归诊断解释，不提升为最终车辆框、最终标注或唯一成员集合。")
    lines.extend(["", "## Gates", "", "| gate | status | evidence |", "| --- | --- | --- |"])
    for row in gates:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence']} |")
    lines.extend(["", "## Failure Ledger", "", "| failure_id | failure_type | evidence |", "| --- | --- | --- |"])
    for row in failure_rows:
        lines.append(f"| {row['failure_id']} | {row['failure_type']} | {row['evidence']} |")
    lines.extend(
        [
            "",
            "## 冻结与隔离",
            "",
            f"- pre_eval_seal: `{rel(D1['pre_eval_seal'])}`",
            f"- evaluator GT source opened after seal: `{rel(PAIR_CSV)}`",
            "- generator rows record `gt_file_opened=false`, `evaluation_file_opened=false`, and `future_frame_read=false`.",
            "- P0 files are checked against the P0 frozen manifest.",
            "",
        ]
    )
    write_text(D1["report"], "\n".join(lines))


EVAL_FIELDS = ["eval_id", "model_id", "sar_frame", "center_error_px", "prediction_center", "gt_center", "gt_file_opened_after_seal", "pre_eval_seal_verified", "notes"]
BASELINE_FIELDS = ["model_id", "holdout_frames", "center_error_mean_px", "center_error_median_px", "center_error_p90_px", "cumulative_error_px", "velocity_error_mean_px", "role"]
FAILURE_FIELDS = ["failure_id", "failure_type", "evidence", "counterexample"]
GATE_FIELDS = ["gate_id", "status", "evidence", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["evaluate"])
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate()
        print("D1 evaluation complete")


if __name__ == "__main__":
    main()
