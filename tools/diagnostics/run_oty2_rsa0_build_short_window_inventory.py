#!/usr/bin/env python3
from __future__ import annotations

"""Build the RSA0 short-window inventory.

This step records candidate windows and debts only. It does not generate atlas
geometry, representation channels, candidate boxes, rankings, or final masks.
"""

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from oty2_s1x_common import (
    CONFIG_DIR,
    MANIFEST_DIR,
    REPORT_DIR,
    aggregate_file_hash,
    load_json,
    read_csv,
    row_hash,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_rsa0_short_window_inventory.json"
OUTPUT_CSV = MANIFEST_DIR / "oty2_rsa0_short_window_inventory.csv"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_short_window_inventory_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else CONFIG_DIR.parents[1] / path


def source_hashes(sources: dict[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path_text in sources.items():
        path = resolve(path_text)
        hashes[key] = sha256_file(path)
    return hashes


def frame_state_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["scene"], row["canonical_vehicle_id"]), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda item: int(item["frame_index"]))
    return grouped


def state_summary(rows: list[dict[str, str]], scene: str, vehicle_id: str) -> dict[str, Any]:
    selected = [row for row in rows if row["scene"] == scene and row["canonical_vehicle_id"] == vehicle_id]
    visibility = Counter(row["visibility_state"] for row in selected)
    bbox_rows = [row for row in selected if row.get("reference_bbox_available", "").lower() == "true"]
    if not selected:
        return {
            "optical_frame_start": "",
            "optical_frame_end": "",
            "bbox_frame_count": 0,
            "visibility_summary": "missing_vehicle_state",
        }
    return {
        "optical_frame_start": min(int(row["frame_index"]) for row in selected),
        "optical_frame_end": max(int(row["frame_index"]) for row in selected),
        "bbox_frame_count": len(bbox_rows),
        "visibility_summary": ";".join(f"{key}:{visibility[key]}" for key in sorted(visibility)),
    }


def s1x_coverage(condition_rows: list[dict[str, str]], scene: str, vehicle_id: str, start: int, end: int) -> dict[str, Any]:
    rows = [
        row for row in condition_rows
        if row["scene"] == scene
        and row["canonical_vehicle_id"] == vehicle_id
        and start <= int(row["sar_frame_index"]) <= end
    ]
    if not rows:
        return {
            "s1x_condition_frame_count": 0,
            "s1x_window_ids": "",
            "sar_gray_paths_available": "false",
            "s1x_dependency": "not_covered_by_s1x_condition_frames",
        }
    paths_ok = all(Path(row["sar_gray_path"]).is_file() for row in rows)
    return {
        "s1x_condition_frame_count": len(rows),
        "s1x_window_ids": ";".join(sorted({row["window_id"] for row in rows})),
        "sar_gray_paths_available": "true" if paths_ok else "false",
        "s1x_dependency": "covered_by_existing_condition_frames_rebuild_required",
    }


def gt_quality_summary(gt_rows: list[dict[str, str]], scene: str, vehicle_id: str, start: int, end: int) -> dict[str, Any]:
    selected = [
        row for row in gt_rows
        if row.get("scene") == scene
        and row.get("canonical_vehicle_id") == vehicle_id
        and start <= int(row.get("sar_frame_index", "-1")) <= end
    ]
    if not selected:
        return {
            "gt_context_rows": 0,
            "gt_quality_summary": "missing_or_not_indexed",
            "gt_role": "identity_neighbourhood_context_only_if_available",
        }
    quality = Counter(row.get("gt_quality_status", "unknown") for row in selected)
    return {
        "gt_context_rows": len(selected),
        "gt_quality_summary": ";".join(f"{key}:{quality[key]}" for key in sorted(quality)),
        "gt_role": "research_identity_neighbourhood_and_posthoc_context_not_response_mask",
    }


def make_row(
    item: dict[str, Any],
    state_rows: list[dict[str, str]],
    condition_rows: list[dict[str, str]],
    gt_rows: list[dict[str, str]],
) -> dict[str, Any]:
    scene = item["scene"]
    vehicle_id = item["vehicle_id"]
    start = int(item["sar_frame_start"])
    end = int(item["sar_frame_end"])
    row: dict[str, Any] = {
        "window_id": item["window_id"],
        "scene": scene,
        "canonical_vehicle_id": vehicle_id,
        "sar_frame_start": start,
        "sar_frame_end": end,
        "sar_frame_count": end - start + 1 if end >= start else 0,
        "role": item["role"],
        "decision": item["decision"],
        "reason": item["reason"],
        "response_reference_status": "not_built_yet",
        "atlas_use": "allowed_after_direct_visual_review" if item["decision"].startswith("selected") else "not_primary_atlas_input",
        "statistics_use": "exclude_until_atlas_frozen",
        "forbidden_use": "candidate_bank;ranking;winner;final_box;whole_gt_positive_mask",
    }
    row.update(state_summary(state_rows, scene, vehicle_id))
    row.update(s1x_coverage(condition_rows, scene, vehicle_id, start, end))
    row.update(gt_quality_summary(gt_rows, scene, vehicle_id, start, end))
    return row


def main() -> None:
    args = parse_args()
    config = load_json(args.config)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = config["sources"]
    state_rows = read_csv(resolve(sources["canonical_frame_states"]))
    condition_rows = read_csv(resolve(sources["s1x_optical_condition_frames"]))
    gt_rows = read_csv(resolve(sources["s0_sar_gt_quality_audit"]))

    items: list[dict[str, Any]] = [config["required_canonical_window"]]
    items.extend(config["second_window_candidates"])
    items.extend(config["cross_scene_candidates"])
    items.extend(config["excluded_pressure_cases"])

    rows = [make_row(item, state_rows, condition_rows, gt_rows) for item in items]
    write_csv(OUTPUT_CSV, rows)

    input_paths = [args.config, *[resolve(path_text) for path_text in sources.values()]]
    summary = {
        "version": config["version"],
        "git": git_state,
        "output_csv": str(OUTPUT_CSV),
        "output_csv_sha256": sha256_file(OUTPUT_CSV),
        "row_count": len(rows),
        "decision_counts": dict(Counter(row["decision"] for row in rows)),
        "selected_windows": [row["window_id"] for row in rows if str(row["decision"]).startswith("selected")],
        "debt_windows": [row["window_id"] for row in rows if "debt" in str(row["decision"])],
        "source_hashes": source_hashes(sources),
        "config_sha256": sha256_file(args.config),
        "aggregate_input_sha256": aggregate_file_hash(input_paths),
        "row_hash": row_hash(rows),
        "boundary": "inventory_only_no_atlas_no_representations_no_scoring",
    }
    write_json(SUMMARY_JSON, summary)


if __name__ == "__main__":
    main()
