#!/usr/bin/env python3
from __future__ import annotations

"""Freeze S1D0 inference and blind-review artifacts before visible-response review."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oty2_s1d0_common import (
    REPO_ROOT,
    load_json,
    read_csv,
    require,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


CONFIG_PATH = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_dynamic_response.json"
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
FREEZE_PATH = MANIFEST_DIR / "oty2_s1d0_inference_freeze_manifest.csv"
SUMMARY_PATH = REPORT_DIR / "oty2_s1d0_inference_freeze_summary_20260717.json"


def add_path(rows: list[dict[str, Any]], path: Path, role: str, mode: str = "shared") -> None:
    require(path.is_file(), f"missing freeze artifact: {path}")
    rows.append(
        {
            "path": str(path.resolve()),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "freeze_role": role,
            "state_mode": mode,
            "frozen_before_visible_response_review": "true",
            "target_reference_content": "false",
        }
    )


def require_completed_review(path: Path) -> int:
    rows = read_csv(path)
    require(rows, f"empty review manifest: {path}")
    require(
        all(row.get("review_status") == "directly_reviewed_complete" for row in rows),
        f"pending direct review rows: {path}",
    )
    require(
        all(row.get("contains_target_reference") == "false" for row in rows),
        f"target reference found in blind review: {path}",
    )
    require(
        all(row.get("direct_review_finding", "").strip() for row in rows),
        f"missing direct review finding: {path}",
    )
    return len(rows)


def main() -> None:
    config = load_json(CONFIG_PATH)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    output_root = Path(config["output_root"])
    review_counts = {}
    for mode in ("causal", "bidirectional"):
        review_path = MANIFEST_DIR / f"oty2_s1d0_{mode}_blind_review_manifest.csv"
        review_counts[mode] = require_completed_review(review_path)

    rows: list[dict[str, Any]] = []
    shared = [
        (CONFIG_PATH, "INFERENCE_CONFIG"),
        (REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_inventory.json", "INVENTORY_CONFIG"),
        (MANIFEST_DIR / "oty2_s1d0_multiscene_lifecycle_inventory.csv", "THREE_SCENE_INVENTORY"),
        (MANIFEST_DIR / "oty2_s1d0_inventory_blind_review_manifest.csv", "INVENTORY_BLIND_REVIEW"),
        (MANIFEST_DIR / "oty2_s1d0_selected_lifecycle_roles.csv", "FROZEN_ROLE_SELECTION"),
        (MANIFEST_DIR / "oty2_s1d0_lifecycle_conditions.csv", "OPTICAL_LIFECYCLE_CONDITIONS"),
        (REPORT_DIR / "oty2_s1d0_inventory_summary_20260717.json", "INVENTORY_SUMMARY"),
        (REPORT_DIR / "oty2_s1d0_lifecycle_condition_summary_20260717.json", "CONDITION_SUMMARY"),
    ]
    for path, role in shared:
        add_path(rows, path, role)

    for mode in ("causal", "bidirectional"):
        for stem, role in (
            ("transport_diagnostics", "FROZEN_TRANSPORT_OUTPUT"),
            ("frame_states", "FROZEN_STATE_OUTPUT"),
            ("response_graph_nodes", "FROZEN_GRAPH_OUTPUT"),
            ("response_graph_edges", "FROZEN_GRAPH_OUTPUT"),
            ("response_events", "FROZEN_EVENT_OUTPUT"),
            ("blind_review_manifest", "FROZEN_BLIND_REVIEW_OUTPUT"),
        ):
            add_path(rows, MANIFEST_DIR / f"oty2_s1d0_{mode}_{stem}.csv", role, mode)
        add_path(
            rows,
            REPORT_DIR / f"oty2_s1d0_{mode}_inference_summary_20260717.json",
            "FROZEN_INFERENCE_SUMMARY",
            mode,
        )

    case_dirs = sorted(path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("S1D0-"))
    require(len(case_dirs) == 3, f"expected three S1D0 case directories, found {len(case_dirs)}")
    for case_dir in case_dirs:
        for mode in ("causal", "bidirectional"):
            mode_dir = case_dir / mode
            add_path(rows, mode_dir / "dynamic_state_masks.npz", "FROZEN_INFERENCE_MASKS", mode)
            add_path(rows, mode_dir / "inference_summary.json", "FROZEN_INFERENCE_SUMMARY", mode)
            review_pages = sorted((mode_dir / "blind_review").glob("blind_dynamic_review_page_*.png"))
            require(review_pages, f"missing blind review pages: {mode_dir}")
            for page in review_pages:
                add_path(rows, page, "FROZEN_BLIND_REVIEW_OUTPUT", mode)

    write_csv(FREEZE_PATH, rows)
    summary = {
        "version": "OTY2-S1D0-inference-freeze-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state,
        "freeze_manifest": str(FREEZE_PATH),
        "freeze_manifest_sha256": sha256_file(FREEZE_PATH),
        "frozen_artifact_count": len(rows),
        "review_counts": review_counts,
        "target_reference_content_rows": 0,
        "single_allowed_minimal_repair_used": True,
        "inference_rules_frozen_before_visible_response_review": True,
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
