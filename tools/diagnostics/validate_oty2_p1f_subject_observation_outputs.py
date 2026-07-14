#!/usr/bin/env python3
"""Validate P1-F runtime/evaluation separation, provenance, uniqueness, and replay."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from evaluate_oty2_p1f_subject_observation_recovery import (
    BASELINES,
    EVALUATION_FIELDS,
    FAILURE_FIELDS,
    LEAKAGE_FIELDS,
)
from run_oty2_p1f_multiframe_subject_observation_recovery import (
    CLUSTER_FIELDS,
    RECOVERY_FIELDS,
    RUNTIME_FIELDS,
    SELECTED_FIELDS,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/oty2/oty2_p1f_multiframe_subject_observation.yaml"
RUNNER = ROOT / "tools/diagnostics/run_oty2_p1f_multiframe_subject_observation_recovery.py"
EVALUATOR = ROOT / "tools/diagnostics/evaluate_oty2_p1f_subject_observation_recovery.py"
ALLOWED_STATUS = {
    "P1F_SUBJECT_OBSERVATION_LAYER_READY",
    "P1F_SUBJECT_OBSERVATION_LAYER_PARTIALLY_READY",
    "P1F_SUBJECT_OBSERVATION_LAYER_BLOCKED",
}
FORBIDDEN_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".avi", ".mov", ".npz", ".npy",
    ".pt", ".pth", ".onnx", ".ckpt", ".zip", ".7z", ".rar", ".docx",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main() -> int:
    failures: list[str] = []
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if config.get("source_boundary") != "optical_runtime_only_no_sar_no_gt":
        failures.append("source_boundary")
    if config.get("stage_status") not in ALLOWED_STATUS:
        failures.append(f"stage_status:{config.get('stage_status')}")
    if config.get("runtime_benchmark_separation") is not True:
        failures.append("runtime_benchmark_separation")
    if config.get("visual_review_complete") is not True:
        failures.append("visual_review_complete")
    if config.get("p2_entry_allowed") is not False:
        failures.append("p2_entry_allowed")
    if config.get("stage_status") == "P1F_SUBJECT_OBSERVATION_LAYER_READY" and config.get("p1f_representation_entry_allowed") is not True:
        failures.append("ready_without_representation_entry")
    if config.get("stage_status") != "P1F_SUBJECT_OBSERVATION_LAYER_READY" and config.get("p1f_representation_entry_allowed") is not False:
        failures.append("nonready_with_representation_entry")

    runtime_input_text = json.dumps(config.get("runtime_inputs", {}), ensure_ascii=False).lower()
    if "p1e_" in runtime_input_text or "benchmark" in runtime_input_text:
        failures.append("runtime_input_benchmark_path")
    if any(token in runtime_input_text for token in ('"sar"', "sar_gt", "p2")):
        failures.append("runtime_input_sar_or_p2")
    provenance = config.get("parameter_provenance", {})
    if provenance.get("heldout_used_for_parameter_selection") is not False:
        failures.append("heldout_parameter_leakage")
    if provenance.get("diagnostic_only_used_for_parameter_selection") is not False:
        failures.append("diagnostic_parameter_leakage")

    schemas = {
        "runtime_observations": RUNTIME_FIELDS,
        "runtime_clusters": CLUSTER_FIELDS,
        "selected_observations": SELECTED_FIELDS,
        "recovered_observations": RECOVERY_FIELDS,
        "evaluation": EVALUATION_FIELDS,
        "failure_inventory": FAILURE_FIELDS,
        "leakage_audit": LEAKAGE_FIELDS,
    }
    loaded: dict[str, list[dict[str, str]]] = {}
    paths: dict[str, Path] = {}
    for key, expected in schemas.items():
        relative = config["outputs"].get(key)
        path = ROOT / relative if relative else ROOT / "__missing__"
        paths[key] = path
        if not path.exists():
            failures.append(f"missing:{key}:{relative}")
            continue
        fields, rows = read_csv(path)
        if fields != expected:
            failures.append(f"schema:{key}:{fields}")
        loaded[key] = rows
    report_path = ROOT / config["outputs"]["report"]
    if not report_path.exists():
        failures.append("missing_report")
    formal_paths = list(paths.values()) + [report_path]

    runtime_rows = loaded.get("runtime_observations", [])
    cluster_rows = loaded.get("runtime_clusters", [])
    selected_rows = loaded.get("selected_observations", [])
    recovered_rows = loaded.get("recovered_observations", [])
    evaluation_rows = loaded.get("evaluation", [])
    leakage_rows = loaded.get("leakage_audit", [])

    forbidden_fields = {"canonical_vehicle_id", "reference_bbox", "benchmark_role"}
    if forbidden_fields & (set(RUNTIME_FIELDS) | set(CLUSTER_FIELDS) | set(SELECTED_FIELDS) | set(RECOVERY_FIELDS)):
        failures.append("runtime_schema_answer_leakage")
    if any(":PV" in row.get("runtime_local_subject_id", "") or ":GV" in row.get("runtime_local_subject_id", "") for row in selected_rows):
        failures.append("runtime_subject_id_answer_leakage")
    if any(row.get("runtime_local_subject_id") and ":RS" not in row["runtime_local_subject_id"] for row in selected_rows):
        failures.append("runtime_subject_id_domain")

    observation_keys = {(row["scene"], row["detector_source"], row["source_detection_id"]) for row in runtime_rows}
    input_keys: set[tuple[str, str, str]] = set()
    for scene, sources in config["runtime_inputs"]["normalized_detection_tables"].items():
        for source, path_value in sources.items():
            _, rows = read_csv(Path(path_value))
            input_keys.update((scene, source, row["det_id"]) for row in rows)
    if observation_keys != input_keys:
        failures.append(f"detection_provenance:missing={len(input_keys-observation_keys)}:extra={len(observation_keys-input_keys)}")
    runtime_ids = {row["runtime_observation_id"] for row in runtime_rows}
    if len(runtime_ids) != len(runtime_rows):
        failures.append("runtime_observation_id_uniqueness")

    clustered_ids: list[str] = []
    for row in cluster_rows:
        clustered_ids.extend(item for item in row["observation_ids"].split(";") if item)
    if Counter(clustered_ids) != Counter({item: 1 for item in runtime_ids}):
        failures.append("cluster_observation_partition")

    subject_frame = Counter((row["runtime_local_subject_id"], row["frame_index"]) for row in selected_rows)
    duplicates = [key for key, count in subject_frame.items() if count > 1]
    if duplicates:
        failures.append(f"selected_subject_frame_uniqueness:{duplicates[:10]}")
    selected_ids = [row["selected_observation_id"] for row in selected_rows if row["selected_observation_id"]]
    reused = [item for item, count in Counter(selected_ids).items() if count > 1]
    if reused:
        failures.append(f"selected_observation_reuse:{reused[:10]}")
    recovered_ids = {row["recovered_observation_id"] for row in recovered_rows}
    unknown_selected = [item for item in selected_ids if item not in runtime_ids and item not in recovered_ids]
    if unknown_selected:
        failures.append(f"selected_provenance:{unknown_selected[:10]}")

    for row in recovered_rows:
        if "linear" in row["recovery_method"].lower():
            failures.append(f"linear_final_recovery:{row['recovered_observation_id']}")
        if row["acceptance_status"] == "accepted":
            if not row["forward_seed_frame"] and not row["backward_seed_frame"]:
                failures.append(f"accepted_recovery_without_seed:{row['recovered_observation_id']}")
            if not row["bbox"] or int(row["propagation_length"]) < 1:
                failures.append(f"accepted_recovery_trace:{row['recovered_observation_id']}")
            if float(row["runtime_recovery_confidence"]) <= 0:
                failures.append(f"accepted_recovery_confidence:{row['recovered_observation_id']}")

    if len(evaluation_rows) != 22 * len(BASELINES):
        failures.append(f"evaluation_coverage:{len(evaluation_rows)}")
    eval_keys = {(row["baseline"], row["canonical_vehicle_id"]) for row in evaluation_rows}
    if len(eval_keys) != len(evaluation_rows):
        failures.append("evaluation_key_uniqueness")
    if {row["baseline"] for row in evaluation_rows} != set(BASELINES):
        failures.append("baseline_domain")
    if {row["benchmark_role"] for row in evaluation_rows} != {"development", "heldout_validation", "diagnostic_only"}:
        failures.append("evaluation_role_domain")
    if any(row["result"] != "pass" for row in leakage_rows if truth(row["blocking"])):
        failures.append("runtime_leakage_audit")

    metrics_path = ROOT / config["outputs"]["metrics"]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if metrics.get("stage_status") != config.get("stage_status"):
        failures.append(f"metrics_config_stage_mismatch:{metrics.get('stage_status')}:{config.get('stage_status')}")
    if metrics.get("leakage_audit") != "PASS":
        failures.append("metrics_leakage")
    if metrics.get("p2_entry_allowed") is not False:
        failures.append("metrics_p2_entry")

    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    for required in (
        config.get("stage_status", ""), "A_YOLO26L", "B_MULTI_SOURCE_SELECTION", "C_FORWARD_RECOVERY",
        "D_BIDIRECTIONAL_CONTROLLED", "visible-but-unboxed", "leakage audit", "P2 entry allowed: `false`",
        "未读取 SAR", "未修改 P1-C",
    ):
        if required and required not in report:
            failures.append(f"report_missing:{required}")

    status = git("status", "--porcelain")
    status_paths = [line[3:].strip().strip('"').replace("\\", "/") for line in status.stdout.splitlines() if line]
    for path in status_paths:
        if Path(path).suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden_asset_in_worktree:{path}")
    changed = set(git("diff", "--name-only").stdout.splitlines()) | set(git("diff", "--cached", "--name-only").stdout.splitlines())
    protected = sorted(path for path in changed if any(token in path.lower() for token in ("oty2_p1b_", "oty2_p1c_", "oty2_p1d_", "oty2_p1e_")))
    if protected:
        failures.append(f"protected_history_modified:{protected}")
    expected_prefixes = {
        "configs/oty2/oty2_p1f_", "docs/OTY2_P1F_", "manifests/oty2/oty2_p1f_",
        "reports/oty2/oty2_p1f_", "tools/diagnostics/run_oty2_p1f_",
        "tools/diagnostics/evaluate_oty2_p1f_", "tools/diagnostics/validate_oty2_p1f_",
    }
    unexpected = sorted(path for path in status_paths if not any(path.startswith(prefix) for prefix in expected_prefixes))
    if unexpected:
        failures.append(f"unexpected_worktree_paths:{unexpected}")

    before = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in formal_paths if path.exists()}
    runner = subprocess.run([sys.executable, str(RUNNER)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    evaluator = subprocess.run([sys.executable, str(EVALUATOR)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if runner.returncode != 0:
        failures.append(f"runner_replay:{runner.returncode}:{runner.stderr[-500:]}")
    if evaluator.returncode != 0:
        failures.append(f"evaluator_replay:{evaluator.returncode}:{evaluator.stderr[-500:]}")
    after = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in formal_paths if path.exists()}
    if before != after:
        changed_hashes = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        failures.append(f"fixed_input_replay_hash_mismatch:{changed_hashes}")

    payload = {
        "status": "PASS" if not failures else "FAIL", "stage_status": config.get("stage_status"),
        "failures": failures, "row_counts": {key: len(rows) for key, rows in loaded.items()},
        "runtime_local_subject_count": len({row["runtime_local_subject_id"] for row in selected_rows}),
        "accepted_recovery_count": sum(row["acceptance_status"] == "accepted" for row in recovered_rows),
        "leakage_audit": "PASS" if not any(item == "runtime_leakage_audit" for item in failures) else "FAIL",
        "fixed_input_replay": "PASS" if before == after and runner.returncode == 0 and evaluator.returncode == 0 else "FAIL",
        "formal_output_sha256": after, "visual_review_complete": config.get("visual_review_complete"),
        "p1f_representation_entry_allowed": config.get("p1f_representation_entry_allowed"),
        "p2_entry_allowed": config.get("p2_entry_allowed"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
