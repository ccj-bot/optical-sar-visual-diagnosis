#!/usr/bin/env python3
from __future__ import annotations

"""Freeze the RSA0 response atlas before any representation scoring."""

import argparse
from pathlib import Path
from typing import Any

from oty2_s1x_common import (
    MANIFEST_DIR,
    REPORT_DIR,
    REPO_ROOT,
    aggregate_file_hash,
    read_csv,
    row_hash,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "0f1655546ea402857ab054421067f1bf075c4c20"
FREEZE_CSV = MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest.csv"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_response_atlas_freeze_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas-version", default="OTY2-RSA0-response-atlas-v0-manual-review-seeded")
    return parser.parse_args()


def add_file(rows: list[dict[str, Any]], atlas_version: str, role: str, path: Path, git_tracked: bool) -> None:
    rows.append({
        "atlas_version": atlas_version,
        "role": role,
        "path": str(path),
        "sha256": sha256_file(path),
        "git_tracked": "true" if git_tracked else "false",
        "freeze_status": "frozen_before_representation_scoring",
    })


def main() -> None:
    args = parse_args()
    git_state = verify_git_gate(EXPECTED_BRANCH, EXPECTED_START_HEAD)
    atlas_version = args.atlas_version
    rows: list[dict[str, Any]] = []
    tracked_files = [
        ("config", REPO_ROOT / "configs" / "oty2" / "oty2_rsa0_response_atlas.json"),
        ("frames", MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv"),
        ("regions", MANIFEST_DIR / "oty2_rsa0_response_atlas_regions.csv"),
        ("skeletons", MANIFEST_DIR / "oty2_rsa0_response_skeletons.csv"),
        ("background_controls", MANIFEST_DIR / "oty2_rsa0_background_controls.csv"),
        ("direct_visual_review_report", REPORT_DIR / "oty2_rsa0_response_atlas_direct_visual_review_20260717.md"),
        ("atlas_summary", REPORT_DIR / "oty2_rsa0_response_atlas_summary_20260717.json"),
        ("visual_review_pack_manifest", MANIFEST_DIR / "oty2_rsa0_visual_review_pack_manifest.csv"),
        ("visual_review_pack_summary", REPORT_DIR / "oty2_rsa0_visual_review_pack_summary_20260717.json"),
        ("short_window_inventory", MANIFEST_DIR / "oty2_rsa0_short_window_inventory.csv"),
    ]
    for role, path in tracked_files:
        add_file(rows, atlas_version, role, path, True)

    frame_rows = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv")
    for frame in frame_rows:
        overlay_path = Path(frame["overlay_path"])
        add_file(rows, atlas_version, f"overlay_{frame['case_id']}_{frame['sar_frame']}", overlay_path, False)

    write_csv(FREEZE_CSV, rows)
    summary = {
        "atlas_version": atlas_version,
        "git": git_state,
        "freeze_manifest": str(FREEZE_CSV),
        "freeze_manifest_sha256": sha256_file(FREEZE_CSV),
        "frozen_file_count": len(rows),
        "aggregate_freeze_sha256": aggregate_file_hash([Path(row["path"]) for row in rows]),
        "row_hash": row_hash(rows),
        "boundary": "atlas_frozen_before_representation_scoring",
    }
    write_json(SUMMARY_JSON, summary)


if __name__ == "__main__":
    main()
