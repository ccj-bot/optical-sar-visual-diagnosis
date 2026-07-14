#!/usr/bin/env python3
"""Validate the OTY2 P1-D blocked optical physical-vehicle freeze audit."""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/oty2/oty2_p1d_physical_vehicle_thread_freeze.yaml"
SCENES = {"GM_RM011", "GM_RM017", "GM_RM019"}
FINAL_FROZEN_OUTPUTS = {
    "manifests/oty2/oty2_p1d_frozen_physical_vehicle_registry.csv",
    "manifests/oty2/oty2_p1d_global_to_canonical_vehicle_map.csv",
    "manifests/oty2/oty2_p1d_frozen_optical_vehicle_threads.csv",
}
FORBIDDEN_ASSET_SUFFIXES = {".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov", ".npz", ".zip", ".docx"}

REQUIRED_FIELDS = {
    "physical_vehicle_registry": {
        "scene", "canonical_vehicle_id", "p1c_global_vehicle_ids", "frame_first_visible", "frame_last_visible",
        "visible_frame_ranges", "occlusion_or_missed_ranges", "entry_frame", "entry_location", "entry_state",
        "exit_frame", "exit_location", "exit_state", "vehicle_color", "vehicle_type_or_shape",
        "dominant_motion_direction", "scale_trend", "distinctive_visual_features", "source_tracker_ids",
        "detector_sources", "identity_evidence_summary", "lifecycle_completeness", "thread_purity",
        "freeze_status", "risk_flags", "notes",
    },
    "thread_lifecycle_audit": {
        "scene", "p1c_global_vehicle_id", "audit_id", "frame_start", "frame_end", "audit_type",
        "visual_finding", "same_physical_vehicle", "lifecycle_interpretation", "possible_duplicate_thread_ids",
        "possible_contaminating_thread_ids", "decision", "evidence_summary", "notes",
    },
    "gm011_thread_pair_audit": {
        "scene", "thread_a", "thread_b", "temporal_relation", "overlap_frame_count", "gap_length",
        "visual_identity_judgment", "recommended_relation", "evidence_summary",
    },
    "gm019_thread_pair_audit": {
        "scene", "thread_a", "thread_b", "temporal_relation", "overlap_frame_count", "gap_length",
        "visual_identity_judgment", "recommended_relation", "evidence_summary",
    },
    "thread_pairwise_identity_audit": {
        "scene", "thread_a", "thread_b", "temporal_relation", "overlap_frame_count", "gap_length",
        "a_exit_location", "b_entry_location", "color_similarity", "appearance_similarity", "shape_similarity",
        "motion_compatibility", "scale_trend_compatibility", "boundary_lifecycle_compatibility",
        "visual_identity_judgment", "recommended_relation", "evidence_summary", "notes",
    },
    "lifecycle_reset_audit": {
        "scene", "birth_count", "exit_count", "boundary_entry_count", "boundary_entry_ratio",
        "boundary_exit_count", "boundary_exit_ratio", "non_boundary_birth_count", "non_boundary_exit_count",
        "short_exit_near_birth_count", "reset_high_similarity_pair_count", "reset_resolved_wrong_bridge_count",
        "reset_possible_over_split_count", "visual_judgment", "decision", "evidence_summary", "notes",
    },
    "freeze_acceptance_checklist": {"check_id", "acceptance_condition", "result", "evidence", "blocking", "notes"},
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    failures: list[str] = []
    if not CONFIG.exists():
        print(json.dumps({"status": "FAIL", "failures": [f"missing:{CONFIG}"]}, ensure_ascii=False, indent=2))
        return 1
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if config.get("source_boundary") != "optical_only_no_sar_no_gt":
        failures.append("source_boundary")
    if config.get("stage_status") != "P1D_PHYSICAL_VEHICLE_THREADS_BLOCKED":
        failures.append("stage_status")
    if config.get("manual_override_used") is not False:
        failures.append("manual_override_used")
    if config.get("p2_entry_allowed") is not False:
        failures.append("p2_entry_allowed")
    for path in config.get("inputs", {}).values():
        lowered = str(path).lower()
        if "sar" in lowered or "p2" in lowered:
            failures.append(f"forbidden_input_path:{path}")

    loaded: dict[str, list[dict[str, str]]] = {}
    for key, required in REQUIRED_FIELDS.items():
        relative = config.get("outputs", {}).get(key)
        if not relative:
            failures.append(f"missing_output_config:{key}")
            continue
        path = ROOT / relative
        if not path.exists():
            failures.append(f"missing:{relative}")
            continue
        fields, rows = read_csv(path)
        missing = sorted(required - set(fields))
        if missing:
            failures.append(f"schema:{relative}:missing={missing}")
        if rows and {row.get("scene", "") for row in rows if "scene" in row} - SCENES:
            failures.append(f"scene_domain:{relative}")
        loaded[key] = rows

    registry = loaded.get("physical_vehicle_registry", [])
    lifecycle = loaded.get("thread_lifecycle_audit", [])
    gm011_pairs = loaded.get("gm011_thread_pair_audit", [])
    gm019_pairs = loaded.get("gm019_thread_pair_audit", [])
    all_pairs = loaded.get("thread_pairwise_identity_audit", [])
    resets = loaded.get("lifecycle_reset_audit", [])
    checklist = loaded.get("freeze_acceptance_checklist", [])

    counts = Counter(row.get("scene") for row in registry)
    if counts != Counter({"GM_RM011": 14, "GM_RM017": 4, "GM_RM019": 4}):
        failures.append(f"physical_vehicle_counts:{dict(counts)}")
    if len({row.get("canonical_vehicle_id") for row in registry}) != len(registry):
        failures.append("duplicate_canonical_vehicle_id")
    freeze_domain = {"frozen", "merge_required", "split_required", "identity_conflict", "optically_unresolvable"}
    invalid_freeze = sorted({row.get("freeze_status", "") for row in registry} - freeze_domain)
    if invalid_freeze:
        failures.append(f"freeze_status_domain:{invalid_freeze}")
    gm019_conflicts = [row for row in registry if row.get("scene") == "GM_RM019" and row.get("freeze_status") == "identity_conflict"]
    if len(gm019_conflicts) != 1 or gm019_conflicts[0].get("canonical_vehicle_id") != "GM_RM019:PV003":
        failures.append("gm019_conflict_registry")
    gm011_nonfrozen = {row.get("canonical_vehicle_id"): row.get("freeze_status") for row in registry if row.get("scene") == "GM_RM011" and row.get("freeze_status") != "frozen"}
    expected_gm011_nonfrozen = {
        "GM_RM011:PV004": "identity_conflict",
        "GM_RM011:PV009": "merge_required",
        "GM_RM011:PV014": "identity_conflict",
    }
    if gm011_nonfrozen != expected_gm011_nonfrozen:
        failures.append(f"gm011_nonfrozen_registry:{gm011_nonfrozen}")
    for row in registry:
        risk_flags = row.get("risk_flags", "")
        if (not row.get("source_tracker_ids") or row.get("source_tracker_ids") == "[]" or not row.get("detector_sources") or row.get("detector_sources") == "[]") and "physical_vehicle_missing_from_p1c" not in risk_flags:
            failures.append(f"missing_provenance:{row.get('canonical_vehicle_id')}")
        if row.get("freeze_status") == "frozen" and row.get("thread_purity") != "pure_single_physical_vehicle":
            failures.append(f"purity:{row.get('canonical_vehicle_id')}")

    summaries_path = ROOT / config["inputs"]["thread_summary_manifest"]
    _, summaries = read_csv(summaries_path)
    p1c_ids = {row["global_vehicle_id"] for row in summaries}
    lifecycle_ids = {row.get("p1c_global_vehicle_id") for row in lifecycle}
    if lifecycle_ids != p1c_ids:
        failures.append(f"lifecycle_coverage:missing={sorted(p1c_ids - lifecycle_ids)}:extra={sorted(lifecycle_ids - p1c_ids)}")
    if len(lifecycle) != 26:
        failures.append(f"lifecycle_row_count:{len(lifecycle)}")
    false_rows = [row for row in lifecycle if row.get("decision") == "return_to_p1c_remove_nonvehicle_thread"]
    if len(false_rows) != 1 or false_rows[0].get("p1c_global_vehicle_id") != "GM_RM019:GV003":
        failures.append("false_thread_assertion")
    gv004 = [row for row in lifecycle if row.get("p1c_global_vehicle_id") == "GM_RM019:GV004"]
    if len(gv004) != 2 or not any("split_required" in row.get("decision", "") for row in gv004):
        failures.append("gv004_mixture_assertion")
    gm011_gv004 = [row for row in lifecycle if row.get("p1c_global_vehicle_id") == "GM_RM011:GV004"]
    if len(gm011_gv004) != 2 or not any(row.get("audit_type") == "visible_without_thread" for row in gm011_gv004):
        failures.append("gm011_gv004_incomplete_lifecycle")

    if len(gm011_pairs) != 14 or {row.get("scene") for row in gm011_pairs} != {"GM_RM011"}:
        failures.append(f"gm011_pair_count_or_scene:{len(gm011_pairs)}")
    if len(gm019_pairs) != 5 or {row.get("scene") for row in gm019_pairs} != {"GM_RM019"}:
        failures.append(f"gm019_pair_count_or_scene:{len(gm019_pairs)}")
    if len(all_pairs) != 25:
        failures.append(f"pairwise_row_count:{len(all_pairs)}")
    gm011_duplicate_pair = [
        row for row in gm011_pairs
        if {row.get("thread_a"), row.get("thread_b")} == {"GM_RM011:GV009", "GM_RM011:GV010"}
    ]
    if len(gm011_duplicate_pair) != 1 or gm011_duplicate_pair[0].get("recommended_relation") != "same_vehicle_merge":
        failures.append("gm011_duplicate_pair_assertion")
    duplicate_pair = [
        row for row in gm019_pairs
        if {row.get("thread_a"), row.get("thread_b")} == {"GM_RM019:GV004", "GM_RM019:GV005"}
    ]
    if len(duplicate_pair) != 1 or duplicate_pair[0].get("recommended_relation") != "same_vehicle_merge":
        failures.append("gm019_duplicate_pair_assertion")
    if any(row.get("recommended_relation") == "optically_unresolvable" for row in all_pairs):
        failures.append("unexpected_optically_unresolvable")

    if len(resets) != 3 or {row.get("scene") for row in resets} != SCENES:
        failures.append("reset_scene_coverage")
    gm011_reset = next((row for row in resets if row.get("scene") == "GM_RM011"), {})
    if gm011_reset.get("reset_resolved_wrong_bridge_count") != "4" or gm011_reset.get("reset_high_similarity_pair_count") != "1" or gm011_reset.get("reset_possible_over_split_count") != "1":
        failures.append("gm011_reset_audit")
    if gm011_reset.get("visual_judgment") != "partially_overused_and_recovery_incomplete":
        failures.append("gm011_reset_judgment")
    gm019_reset = next((row for row in resets if row.get("scene") == "GM_RM019"), {})
    if gm019_reset.get("visual_judgment") != "not_primary_failure_mode":
        failures.append("gm019_reset_judgment")

    blocking_failures = [row for row in checklist if truth(row.get("blocking")) and row.get("result") != "fail"]
    if blocking_failures:
        failures.append(f"blocking_check_not_failed:{[row.get('check_id') for row in blocking_failures]}")
    required_failed = {"C02", "C03", "C04", "C05", "C06", "C13", "C14"}
    failed_checks = {row.get("check_id") for row in checklist if row.get("result") == "fail"}
    if not required_failed <= failed_checks:
        failures.append(f"acceptance_failures_missing:{sorted(required_failed - failed_checks)}")

    metrics_path = ROOT / config["inputs"]["p1c_metrics"]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if not metrics:
        failures.append(f"missing_metrics:{metrics_path}")
    if metrics.get("source_boundary") != "optical_only_no_sar_no_gt":
        failures.append("p1c_source_boundary")
    if metrics.get("hard_constraints", {}).get("total_hard_constraint_violations") != 0:
        failures.append(f"p1c_hard_constraints:{metrics.get('hard_constraints')}")
    for scene in SCENES:
        stability = metrics.get("stability", {}).get(scene, {})
        if not stability.get("thread_count_stable") or float(stability.get("minimum_edge_jaccard", 0.0)) < 1.0:
            failures.append(f"p1c_stability:{scene}:{stability}")

    report_path = ROOT / config["outputs"]["report"]
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    for required_text in (
        "P1D_PHYSICAL_VEHICLE_THREADS_BLOCKED", "GM_RM011:GV009", "GM_RM011:GV010", "完全漏线程", "GM_RM019:GV003", "GM_RM019:GV004",
        "不允许进入 P2", "未读取 SAR", "manual override",
    ):
        if required_text not in report:
            failures.append(f"report_missing:{required_text}")

    for relative in FINAL_FROZEN_OUTPUTS:
        if (ROOT / relative).exists():
            failures.append(f"forbidden_frozen_output_exists:{relative}")

    status = git("status", "--porcelain")
    status_paths: list[str] = []
    for line in status.stdout.splitlines():
        path = line[3:].strip().strip('"')
        status_paths.append(path)
        if Path(path).suffix.lower() in FORBIDDEN_ASSET_SUFFIXES:
            failures.append(f"forbidden_asset_in_worktree:{path}")
    changed = set(git("diff", "--name-only").stdout.splitlines()) | set(git("diff", "--cached", "--name-only").stdout.splitlines())
    protected = sorted(path for path in changed if "oty2_p1b_" in path.lower() or "oty2_p1c_" in path.lower())
    if protected:
        failures.append(f"protected_p1b_p1c_modified:{protected}")

    expected_prefixes = {
        "configs/oty2/oty2_p1d_", "docs/OTY2_P1D_", "manifests/oty2/oty2_p1d_",
        "reports/oty2/oty2_p1d_", "tools/diagnostics/run_oty2_p1d_", "tools/diagnostics/validate_oty2_p1d_",
    }
    unexpected = sorted(path for path in status_paths if path and not any(path.replace("\\", "/").startswith(prefix) for prefix in expected_prefixes))
    if unexpected:
        failures.append(f"unexpected_worktree_paths:{unexpected}")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "stage_status": config.get("stage_status"),
        "failures": failures,
        "row_counts": {key: len(rows) for key, rows in loaded.items()},
        "p1c_thread_counts": dict(Counter(row["scene"] for row in summaries)),
        "audited_physical_vehicle_counts": dict(counts),
        "formal_frozen_vehicle_counts": {scene: 0 for scene in sorted(SCENES)},
        "hard_constraints": metrics.get("hard_constraints", {}),
        "stability": metrics.get("stability", {}),
        "manual_override_used": config.get("manual_override_used"),
        "p2_entry_allowed": config.get("p2_entry_allowed"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
