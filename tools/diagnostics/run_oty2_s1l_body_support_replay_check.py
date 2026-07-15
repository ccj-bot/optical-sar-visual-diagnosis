#!/usr/bin/env python3
from __future__ import annotations

"""Replay the two bounded S1-L body-support runners and compare outputs."""

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
OUTPUT_ROOT = Path(r"D:\profile\research\workspace\output\oty2_s1l_body_support_attribution_20260715")
REPLAY_PATH = OUTPUT_ROOT / "body_support_replay_check.json"

COORDINATE_RUNNER = REPO_ROOT / "tools" / "diagnostics" / "run_oty2_s1l_body_support_coordinate_casebook.py"
PERTURBATION_RUNNER = REPO_ROOT / "tools" / "diagnostics" / "run_oty2_s1l_gt_neighborhood_perturbation_pilot.py"

FORMAL_PATHS = (
    MANIFEST_DIR / "oty2_s1l_body_support_coordinate_frames.csv",
    MANIFEST_DIR / "oty2_s1l_body_support_coordinate_competition.csv",
    MANIFEST_DIR / "oty2_s1l_body_support_casebook_manifest.csv",
    MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_surfaces.csv",
    MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_casebook_manifest.csv",
    OUTPUT_ROOT / "coordinate_casebook_summary.json",
    OUTPUT_ROOT / "gt_neighborhood_perturbation_summary.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def npz_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with np.load(path, allow_pickle=False) as bundle:
        for key in sorted(bundle.files):
            array = np.ascontiguousarray(bundle[key])
            digest.update(key.encode("utf-8")); digest.update(b"\0")
            digest.update(str(array.dtype).encode("ascii")); digest.update(b"\0")
            digest.update(json.dumps(array.shape).encode("ascii")); digest.update(b"\0")
            digest.update(array.tobytes(order="C")); digest.update(b"\0")
    return digest.hexdigest()


def snapshot() -> dict[str, str]:
    paths = list(FORMAL_PATHS)
    for manifest in (
        MANIFEST_DIR / "oty2_s1l_body_support_casebook_manifest.csv",
        MANIFEST_DIR / "oty2_s1l_body_support_gt_neighborhood_casebook_manifest.csv",
    ):
        paths.extend(Path(row["artifact_path"]) for row in read_csv(manifest))
    hashes = {str(path): sha256(path) for path in sorted(set(paths), key=lambda item: str(item).lower())}
    frame_rows = read_csv(MANIFEST_DIR / "oty2_s1l_body_support_coordinate_frames.csv")
    for path in sorted({Path(row["canonical_field_bundle_path"]) for row in frame_rows}, key=lambda item: str(item).lower()):
        hashes[f"npz-content::{path}"] = npz_content_hash(path)
    return hashes


def run_runner(path: Path) -> None:
    subprocess.run(
        [sys.executable, str(path), "--review-status", "directly_reviewed_complete"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def main() -> int:
    run_runner(COORDINATE_RUNNER)
    run_runner(PERTURBATION_RUNNER)
    before = snapshot()
    run_runner(COORDINATE_RUNNER)
    run_runner(PERTURBATION_RUNNER)
    after = snapshot()
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    result: dict[str, Any] = {
        "status": "PASS" if not changed else "FAIL",
        "before_hashes": before,
        "after_hashes": after,
        "changed_paths": changed,
        "review_status": "directly_reviewed_complete",
        "automatic_winner_assigned": False,
        "weighted_score_used": False,
        "GT_IoU_used": False,
    }
    REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPLAY_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
