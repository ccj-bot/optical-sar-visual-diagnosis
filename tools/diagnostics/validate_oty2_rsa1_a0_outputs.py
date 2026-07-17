#!/usr/bin/env python3
"""Validate the frozen OTY2-RSA1-A0 micropilot and final evaluation bundle."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from oty2_rsa1_a0_common import (
    PRIMITIVE_FIELDS,
    REPO,
    TRACE_FIELDS,
    check_repository_gate,
    load_config,
    read_csv,
    sha256_file,
    verify_rule_freeze,
)


EXPECTED_RULE_SHA = "76b72f566325e462dade42dfe328f703f48ce6dba91b224ce306921690df152e"
EXPECTED_HIDDEN_SHA = "88b165ba3657637fbb45afccbc443f53fb05a06bc25ed8a2f62222600687104c"
EXPECTED_PRIMITIVE_ROWS = 205
EXPECTED_TRACE_ROWS = 145

MANIFEST_DIR = REPO / "manifests" / "oty2"
HIDDEN_SKELETON = MANIFEST_DIR / "oty2_rsa1_a0_hidden_skeleton_reference.csv"
HIDDEN_BACKGROUND = MANIFEST_DIR / "oty2_rsa1_a0_hidden_background_reference.csv"
HIDDEN_FREEZE = MANIFEST_DIR / "oty2_rsa1_a0_hidden_reference_freeze_manifest.csv"
RULE_FREEZE = MANIFEST_DIR / "oty2_rsa1_a0_rule_freeze_manifest.csv"
PRIMITIVES = MANIFEST_DIR / "oty2_rsa1_a0_structure_primitives.csv"
TRACE = MANIFEST_DIR / "oty2_rsa1_a0_expansion_trace.csv"
EVALUATION = MANIFEST_DIR / "oty2_rsa1_a0_hidden_reference_evaluation.csv"
STAGE_CONCLUSION = MANIFEST_DIR / "oty2_rsa1_a0_stage_conclusion.csv"
REPORT = REPO / "reports" / "oty2" / "oty2_rsa1_a0_seed_object_extension_micropilot_20260717.md"

HIDDEN_LABELS = {
    "CONFIRMED_MAIN_SKELETON",
    "CONFIRMED_SEED_SEGMENT",
    "CONFIRMED_VERTICAL_BACKGROUND",
    "ARC_OR_CLUTTER_AMBIGUOUS_ZONE",
    "UNRESOLVED_ENDPOINT_ZONE",
}
EVALUATION_MODES = {
    "SEED_ONLY_BASELINE",
    "SINGLE_FRAME_SPATIAL",
    "FORWARD_CAUSAL_MICROPILOT",
    "OFFLINE_BIDIRECTIONAL_MICROPILOT",
}
ALLOWED_CONCLUSIONS = {
    "MICROPILOT_MECHANISM_SUPPORTED",
    "MICROPILOT_PARTIALLY_SUPPORTED",
    "MICROPILOT_FAILED",
}


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() == "true"


def resolve_path(text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else REPO / path


def repo_relative(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return None


def index_blob_sha256(relative: str) -> str:
    content = subprocess.check_output(["git", "show", f":{relative}"], cwd=REPO)
    return hashlib.sha256(content).hexdigest()


def read_csv_with_fields(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def verify_hidden_freeze(failures: list[str]) -> str:
    rows = read_csv(HIDDEN_FREEZE)
    hidden_rows = [row for row in rows if row["entry_role"] == "hidden_evaluation_reference"]
    if len(hidden_rows) != 2:
        failures.append(f"hidden_freeze_reference_rows:{len(hidden_rows)}")
        return ""

    aggregates = {row["aggregate_reference_sha256"] for row in rows}
    if len(aggregates) != 1:
        failures.append(f"hidden_freeze_aggregate_inconsistent:{sorted(aggregates)}")
        return ""
    expected = next(iter(aggregates))

    pieces: list[str] = []
    for row in rows:
        path = resolve_path(row["path"])
        if not path.is_file():
            failures.append(f"hidden_freeze_missing:{path}")
            continue
        digest = sha256_file(path)
        if digest != row["sha256"]:
            failures.append(f"hidden_freeze_hash:{path}")
        relative = repo_relative(path)
        if relative is not None:
            try:
                if index_blob_sha256(relative) != row["sha256"]:
                    failures.append(f"hidden_freeze_index_hash:{relative}")
            except subprocess.CalledProcessError:
                failures.append(f"hidden_freeze_not_in_index:{relative}")
        if path.stat().st_size != int(row["size_bytes"]):
            failures.append(f"hidden_freeze_size:{path}")
        if row["entry_role"] == "hidden_evaluation_reference":
            pieces.append(f"{row['path']}:{digest}")

    actual = hashlib.sha256("\n".join(pieces).encode("utf-8")).hexdigest()
    if actual != expected:
        failures.append(f"hidden_freeze_aggregate:{actual}!={expected}")
    if expected != EXPECTED_HIDDEN_SHA:
        failures.append(f"hidden_freeze_expected:{expected}!={EXPECTED_HIDDEN_SHA}")
    return expected


def verify_rule_manifest_rows(failures: list[str]) -> str:
    rows = read_csv(RULE_FREEZE)
    for row in rows:
        path = resolve_path(row["path"])
        if not path.is_file():
            failures.append(f"rule_freeze_missing:{path}")
            continue
        if sha256_file(path) != row["sha256"]:
            failures.append(f"rule_freeze_hash:{path}")
        relative = repo_relative(path)
        if relative is not None:
            try:
                if index_blob_sha256(relative) != row["sha256"]:
                    failures.append(f"rule_freeze_index_hash:{relative}")
            except subprocess.CalledProcessError:
                failures.append(f"rule_freeze_not_in_index:{relative}")
        if path.stat().st_size != int(row["size_bytes"]):
            failures.append(f"rule_freeze_size:{path}")
    try:
        aggregate = verify_rule_freeze()
    except Exception as exc:  # validation must report all failures together
        failures.append(f"rule_freeze_verify:{type(exc).__name__}:{exc}")
        return ""
    if aggregate != EXPECTED_RULE_SHA:
        failures.append(f"rule_freeze_expected:{aggregate}!={EXPECTED_RULE_SHA}")
    return aggregate


def verify_hidden_reference_rows(config: dict[str, Any], failures: list[str]) -> dict[str, int]:
    skeleton_fields, skeleton_rows = read_csv_with_fields(HIDDEN_SKELETON)
    background_fields, background_rows = read_csv_with_fields(HIDDEN_BACKGROUND)
    required = {
        "case_id",
        "sar_frame",
        "label",
        "geometry_type",
        "points",
        "review_status",
        "source_role",
    }
    for name, fields in (("skeleton", skeleton_fields), ("background", background_fields)):
        missing = sorted(required - set(fields))
        if missing:
            failures.append(f"hidden_{name}_schema_missing:{missing}")

    rows = skeleton_rows + background_rows
    if len(skeleton_rows) != 30 or len(background_rows) != 20 or len(rows) != 50:
        failures.append(
            f"hidden_reference_counts:skeleton={len(skeleton_rows)}:background={len(background_rows)}:total={len(rows)}"
        )

    expected_frames = {
        (case["case_id"], int(frame))
        for case in config["cases"]
        for frame in case["frames"]
    }
    grouped: dict[tuple[str, int], list[str]] = defaultdict(list)
    for row in rows:
        grouped[(row["case_id"], int(row["sar_frame"]))].append(row["label"])
    if set(grouped) != expected_frames:
        failures.append(
            f"hidden_reference_frames:missing={sorted(expected_frames - set(grouped))}:extra={sorted(set(grouped) - expected_frames)}"
        )
    for key, labels in sorted(grouped.items()):
        if len(labels) != 5 or set(labels) != HIDDEN_LABELS or len(labels) != len(set(labels)):
            failures.append(f"hidden_reference_labels:{key}:{sorted(labels)}")
    return {"skeleton": len(skeleton_rows), "background": len(background_rows), "total": len(rows)}


def verify_evaluator_isolation(failures: list[str]) -> bool:
    forbidden = (HIDDEN_SKELETON.name, HIDDEN_BACKGROUND.name)
    allowed_readers = {
        "run_oty2_rsa1_a0_prepare_hidden_reference.py",
        "run_oty2_rsa1_a0_evaluate_hidden_reference.py",
        "validate_oty2_rsa1_a0_outputs.py",
    }
    offenders: list[str] = []
    for source in sorted((REPO / "tools" / "diagnostics").glob("*oty2_rsa1_a0*.py")):
        if source.name in allowed_readers:
            continue
        text = source.read_text(encoding="utf-8")
        if any(name in text for name in forbidden):
            offenders.append(source.relative_to(REPO).as_posix())
    if offenders:
        failures.append(f"hidden_reference_isolation:{offenders}")
    return not offenders


def verify_lf_attributes(failures: list[str]) -> None:
    paths = [
        path.relative_to(REPO).as_posix()
        for pattern in (
            "configs/oty2/oty2_rsa1_a0_*.json",
            "manifests/oty2/oty2_rsa1_a0_*.csv",
            "reports/oty2/oty2_rsa1_a0_*.md",
            "tools/diagnostics/*oty2_rsa1_a0_*.py",
        )
        for path in REPO.glob(pattern)
    ]
    output = subprocess.check_output(
        ["git", "check-attr", "eol", "--", *paths], cwd=REPO, text=True, encoding="utf-8"
    )
    for line in output.splitlines():
        if not line.endswith(": lf"):
            failures.append(f"lf_attribute:{line}")


def verify_primitives_and_trace(failures: list[str]) -> dict[str, int]:
    primitive_fields, primitive_rows = read_csv_with_fields(PRIMITIVES)
    trace_fields, trace_rows = read_csv_with_fields(TRACE)
    if primitive_fields != PRIMITIVE_FIELDS:
        failures.append("primitive_schema_mismatch")
    if trace_fields != TRACE_FIELDS:
        failures.append("trace_schema_mismatch")
    if len(primitive_rows) != EXPECTED_PRIMITIVE_ROWS:
        failures.append(f"primitive_count:{len(primitive_rows)}")
    if len(trace_rows) != EXPECTED_TRACE_ROWS:
        failures.append(f"trace_count:{len(trace_rows)}")

    primitive_by_key = {
        (
            row["case_id"],
            row["frame"],
            row["coordinate_family"],
            row["propagation_mode"],
            row["primitive_id"],
        ): row
        for row in primitive_rows
    }
    supported_rows = [row for row in primitive_rows if row["state"] == "SUPPORTED_EXTENSION"]
    for row in supported_rows:
        tokens = [token for token in row["shortest_seed_path"].split(">") if token]
        if not tokens or not tokens[0].endswith("_SEED") or tokens[-1] != row["primitive_id"]:
            failures.append(f"supported_seed_path:{row['primitive_id']}:{row['shortest_seed_path']}")
        if truth(row["crosses_confirmed_background"]):
            failures.append(f"supported_background_crossing:{row['primitive_id']}")

    card_hash_cache: dict[Path, str] = {}
    for row in trace_rows:
        key = (
            row["case_id"],
            row["frame"],
            row["coordinate_family"],
            row["propagation_mode"],
            row["destination_primitive"],
        )
        primitive = primitive_by_key.get(key)
        if primitive is None:
            failures.append(f"trace_destination_missing:{key}")
        elif primitive["state"] != row["state_after"]:
            failures.append(f"trace_state_mismatch:{key}:{row['state_after']}!={primitive['state']}")
        if row["state_after"] == "SUPPORTED_EXTENSION" and truth(row["crosses_confirmed_background"]):
            failures.append(f"trace_supported_background_crossing:{key}")

        card = Path(row["evidence_card"])
        if not card.is_file():
            failures.append(f"evidence_card_missing:{card}")
            continue
        digest = card_hash_cache.setdefault(card, sha256_file(card))
        if not row["evidence_sha256"] or digest != row["evidence_sha256"]:
            failures.append(f"evidence_card_hash:{card}")

    return {
        "primitives": len(primitive_rows),
        "trace": len(trace_rows),
        "supported_primitives": len(supported_rows),
        "unique_evidence_cards": len(card_hash_cache),
    }


def verify_evaluation(
    config: dict[str, Any], rule_sha: str, isolation_ok: bool, failures: list[str]
) -> tuple[dict[str, Any], str]:
    fields, rows = read_csv_with_fields(EVALUATION)
    required = {
        "case_id",
        "frame",
        "coordinate_family",
        "evaluation_mode",
        "confirmed_seed_count",
        "added_skeleton_covered_px",
        "supported_extension_count",
        "confirmed_vertical_background_overlap_px",
        "ambiguity_zone_area_px",
        "ambiguity_zone_overlap_px",
        "fully_assigned_ambiguity_zone",
        "supported_without_seed_path_count",
        "supported_crossing_background_count",
    }
    missing = sorted(required - set(fields))
    if missing:
        failures.append(f"evaluation_schema_missing:{missing}")
    if len(rows) != 40:
        failures.append(f"evaluation_count:{len(rows)}")

    expected_keys = {
        (case["case_id"], str(frame), mode)
        for case in config["cases"]
        for frame in case["frames"]
        for mode in EVALUATION_MODES
    }
    actual_keys = {(row["case_id"], row["frame"], row["evaluation_mode"]) for row in rows}
    if actual_keys != expected_keys or len(actual_keys) != len(rows):
        failures.append("evaluation_case_frame_mode_grid")
    if {row["coordinate_family"] for row in rows} != {config["primary_coordinate_family"]}:
        failures.append("evaluation_coordinate_family")

    bidir = [row for row in rows if row["evaluation_mode"] == "OFFLINE_BIDIRECTIONAL_MICROPILOT"]
    by_case = {case["case_id"]: [row for row in bidir if row["case_id"] == case["case_id"]] for case in config["cases"]}
    aggregates: dict[str, dict[str, int]] = {}
    for case_id, case_rows in by_case.items():
        aggregates[case_id] = {
            "seed_count": sum(int(row["confirmed_seed_count"]) for row in case_rows),
            "supported_count": sum(int(row["supported_extension_count"]) for row in case_rows),
            "added_coverage": sum(int(row["added_skeleton_covered_px"]) for row in case_rows),
            "vertical_overlap": sum(int(row["confirmed_vertical_background_overlap_px"]) for row in case_rows),
            "ambiguity_overlap": sum(int(row["ambiguity_zone_overlap_px"]) for row in case_rows),
            "ambiguity_area": sum(int(row["ambiguity_zone_area_px"]) for row in case_rows),
            "full_ambiguity": sum(truth(row["fully_assigned_ambiguity_zone"]) for row in case_rows),
            "bad_paths": sum(int(row["supported_without_seed_path_count"]) for row in case_rows),
            "crossing_paths": sum(int(row["supported_crossing_background_count"]) for row in case_rows),
        }

    pv002 = aggregates["PV002_337_341"]
    pv003 = aggregates["PV003_380_384"]
    expected_conditions = {
        "C01_BOTH_CASES_EXTEND": pv002["supported_count"] > 0 and pv003["supported_count"] > 0,
        "C02_ADDED_CONFIRMED_SKELETON": pv002["added_coverage"] > 0 and pv003["added_coverage"] > 0,
        "C03_WEAK_STATE_CENTRAL_RELATION": pv002["seed_count"] == 5 and pv003["seed_count"] == 5,
        "C04_ZERO_VERTICAL_BACKGROUND_POLLUTION": pv002["vertical_overlap"] == 0 and pv003["vertical_overlap"] == 0,
        "C05_NO_BACKGROUND_CROSSING_PATH": pv002["crossing_paths"] == 0 and pv003["crossing_paths"] == 0,
        "C06_NO_COMPLETE_ARC_CLUTTER_ASSIGNMENT": pv002["full_ambiguity"] == 0 and pv003["full_ambiguity"] == 0,
        "C07_COMPLETE_SEED_PATH": pv002["bad_paths"] == 0 and pv003["bad_paths"] == 0,
        "C08_FROZEN_RULE_REPLAY": rule_sha == EXPECTED_RULE_SHA,
        "C09_CLEAR_SEED_ONLY_INCREMENT": pv002["added_coverage"] > 0 and pv003["added_coverage"] > 0,
        "C10_NO_HIDDEN_REFERENCE_FEEDBACK": isolation_ok,
    }

    stage_rows = read_csv(STAGE_CONCLUSION)
    stage_map = {row["condition_id"]: row for row in stage_rows}
    for condition_id, expected in expected_conditions.items():
        if condition_id not in stage_map or truth(stage_map[condition_id]["passed"]) != expected:
            failures.append(f"stage_condition:{condition_id}")
    conclusion = stage_map.get("STAGE_CONCLUSION", {}).get("evidence", "")
    if conclusion not in ALLOWED_CONCLUSIONS:
        failures.append(f"stage_conclusion_domain:{conclusion}")
    computed_conclusion = (
        "MICROPILOT_MECHANISM_SUPPORTED"
        if all(expected_conditions.values())
        else "MICROPILOT_PARTIALLY_SUPPORTED"
        if pv002["supported_count"] > 0 and pv003["supported_count"] == 0
        else "MICROPILOT_FAILED"
    )
    if conclusion != computed_conclusion:
        failures.append(f"stage_conclusion_mismatch:{conclusion}!={computed_conclusion}")
    return aggregates, conclusion


def verify_replay_and_report(
    config: dict[str, Any], rule_sha: str, hidden_sha: str, conclusion: str, failures: list[str]
) -> dict[str, Any]:
    output_root = Path(config["output_root"])
    replay_summary_path = output_root / "frozen_replay" / "replay_summary.json"
    replay = json.loads(replay_summary_path.read_text(encoding="utf-8"))
    if replay.get("pv003_tuning_performed") is not False:
        failures.append(f"pv003_tuning:{replay.get('pv003_tuning_performed')}")
    if replay.get("primitive_count") != EXPECTED_PRIMITIVE_ROWS:
        failures.append(f"replay_primitive_count:{replay.get('primitive_count')}")
    if replay.get("trace_count") != EXPECTED_TRACE_ROWS:
        failures.append(f"replay_trace_count:{replay.get('trace_count')}")
    if replay.get("rule_freeze_sha256") != rule_sha:
        failures.append("replay_rule_sha")

    evaluation_summary = json.loads((output_root / "evaluation_summary.json").read_text(encoding="utf-8"))
    if evaluation_summary.get("stage_conclusion") != conclusion:
        failures.append("evaluation_summary_conclusion")
    if evaluation_summary.get("hidden_reference_freeze_sha256") != hidden_sha:
        failures.append("evaluation_summary_hidden_sha")
    if evaluation_summary.get("rule_freeze_sha256") != rule_sha:
        failures.append("evaluation_summary_rule_sha")
    if evaluation_summary.get("evaluation_rows") != 40:
        failures.append("evaluation_summary_row_count")

    report = REPORT.read_text(encoding="utf-8")
    if conclusion not in report or rule_sha not in report or hidden_sha not in report:
        failures.append("report_summary_binding")
    headings = [f"## {index}." for index in range(1, 8)]
    positions = [report.find(heading) for heading in headings]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        failures.append("report_seven_questions")
    else:
        for index, start in enumerate(positions):
            end = positions[index + 1] if index + 1 < len(positions) else report.find("## Output counts", start)
            section = report[start : end if end >= 0 else None].lower()
            for token in ("primitive", "step", "gate", "card", "hidden"):
                if token not in section:
                    failures.append(f"report_question_{index + 1}_missing:{token}")

    return replay


def main() -> int:
    failures: list[str] = []
    config = load_config()
    try:
        check_repository_gate(config)
    except Exception as exc:
        failures.append(f"repository_gate:{type(exc).__name__}:{exc}")

    rule_sha = verify_rule_manifest_rows(failures)
    hidden_sha = verify_hidden_freeze(failures)
    hidden_counts = verify_hidden_reference_rows(config, failures)
    isolation_ok = verify_evaluator_isolation(failures)
    verify_lf_attributes(failures)
    output_counts = verify_primitives_and_trace(failures)
    aggregates, conclusion = verify_evaluation(config, rule_sha, isolation_ok, failures)
    replay = verify_replay_and_report(config, rule_sha, hidden_sha, conclusion, failures)

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "rule_freeze_sha256": rule_sha,
        "hidden_reference_freeze_sha256": hidden_sha,
        "hidden_reference_counts": hidden_counts,
        "output_counts": output_counts,
        "bidir_evaluation": aggregates,
        "pv003_tuning_performed": replay.get("pv003_tuning_performed"),
        "stage_conclusion": conclusion,
        "state_counts": dict(Counter(row["state"] for row in read_csv(PRIMITIVES))),
    }
    output_path = Path(config["output_root"]) / "validation_summary.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
