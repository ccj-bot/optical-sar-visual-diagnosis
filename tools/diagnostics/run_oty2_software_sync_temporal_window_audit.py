"""Generate OTY2 software-sync SAR temporal frame windows.

This audit consumes existing OTY2-P0 object readiness rows plus the OTY2-P1
software-sync timing contract. It generates SAR frame ranges only. It does not
read SAR image content, enter SAR spatial search, generate SAR regions or
candidate boxes, use SAR GT, use selector/ranking output, train thresholds, or
create annotation proposals.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

WINDOW_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "optical_start_frame",
    "optical_end_frame",
    "optical_frame_count",
    "optical_start_time_sec",
    "optical_end_time_sec",
    "sar_start_raw",
    "sar_end_raw",
    "sar_start_frame",
    "sar_end_frame",
    "sar_window_frame_count",
    "optical_fps",
    "sar_fps",
    "fps_ratio",
    "sync_mode",
    "offset_seconds",
    "software_sync_jitter_ms",
    "padding_sar_frames",
    "padding_reason",
    "object_state_category",
    "uses_primary_observations",
    "uses_secondary_observations",
    "readiness_status",
    "confidence_status",
    "blockers",
    "notes",
]

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_spatial_search_entered": False,
    "sar_search_region_generated": False,
    "sar_gt_used": False,
    "selector_or_ranking_used": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
}


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"true", "1", "yes"}


def bool_text(value: Any) -> str:
    return "true" if boolish(value) else "false"


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def fmt_float(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def join_values(values: Sequence[Any]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return ";".join(out)


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    except OSError:
        return []


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_output_dir(output_root: Path, prefix: str, required_file: str) -> Path | None:
    if not output_root.exists():
        return None
    for output_dir in sorted(output_root.glob(f"{prefix}_*"), key=lambda path: path.name, reverse=True):
        if (output_dir / required_file).exists():
            return output_dir
    return None


def latest_report_json(report_dir: Path, prefix: str) -> Path | None:
    if not report_dir.exists():
        return None
    candidates = sorted(report_dir.glob(f"{prefix}_*.json"), key=lambda path: path.name, reverse=True)
    return candidates[0] if candidates else None


def p1_decisions(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for row in summary.get("per_scene_decisions", []):
        if isinstance(row, Mapping):
            scene = str(row.get("scene", "") or "")
            if scene:
                decisions[scene] = dict(row)
    return decisions


def p0_scene_status(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for row in summary.get("per_scene", []):
        if isinstance(row, Mapping):
            scene = str(row.get("scene", "") or "")
            if scene:
                status[scene] = dict(row)
    return status


def object_category(row: Mapping[str, Any]) -> str:
    gate = str(row.get("oty2_gate", "") or "")
    obj_type = str(row.get("object_hypothesis_type", "") or "")
    recommended = str(row.get("recommended_use_for_oty2", "") or "")
    reason = str(row.get("reason", "") or "").lower()
    secondary_count = safe_int(row.get("shared_secondary_detection_count"), 0) or 0
    orphan_count = safe_int(row.get("orphan_conflict_count"), 0) or 0
    ambiguous_count = safe_int(row.get("ambiguous_cluster_conflict_count"), 0) or 0
    if gate == "exclude_from_oty2" or "short_or_noise" in obj_type:
        return "short_noise_not_ready"
    if gate == "low_confidence_window_only" or "ambiguous" in obj_type:
        return "ambiguous_review_required"
    if gate == "use_as_primary_alignment_track":
        return "stable_primary_continuity"
    uncertainty_terms = ("secondary", "uncertainty", "partial", "duplicate", "edge", "handoff")
    if gate == "use_with_uncertainty_expansion" or secondary_count or orphan_count or ambiguous_count:
        return "secondary_edge_handoff_uncertainty"
    if any(term in recommended.lower() or term in reason for term in uncertainty_terms):
        return "secondary_edge_handoff_uncertainty"
    return "stable_primary_continuity"


def uses_secondary(row: Mapping[str, Any], category: str) -> bool:
    return category == "secondary_edge_handoff_uncertainty" or any(
        (safe_int(row.get(key), 0) or 0) > 0
        for key in ("orphan_conflict_count", "shared_secondary_detection_count", "ambiguous_cluster_conflict_count")
    )


def state_padding(category: str, args: argparse.Namespace) -> tuple[int, str]:
    if category == "stable_primary_continuity":
        return args.stable_primary_padding_sar_frames, "stable_primary_padding"
    if category == "secondary_edge_handoff_uncertainty":
        return args.secondary_or_edge_padding_sar_frames, "secondary_or_edge_handoff_padding"
    if category == "ambiguous_review_required":
        return args.ambiguous_padding_sar_frames, "ambiguous_review_padding"
    return 0, "not_ready_no_state_padding"


def readiness_and_confidence(row: Mapping[str, Any], category: str) -> tuple[str, str, list[str]]:
    gate = str(row.get("oty2_gate", "") or "")
    blockers: list[str] = []
    if category == "short_noise_not_ready" or gate == "exclude_from_oty2":
        blockers.extend(["object_gate_exclude_from_oty2", "short_or_noise_not_ready"])
        return "not_ready_for_sar_temporal_window", "blocked_short_or_noise", blockers
    if gate == "use_as_primary_alignment_track":
        return "ready_primary_sar_temporal_window", "software_sync_with_small_padding", blockers
    if gate == "use_with_uncertainty_expansion":
        return "ready_uncertainty_expanded_sar_temporal_window", "software_sync_with_uncertainty_padding", blockers
    if gate == "low_confidence_window_only":
        return "low_confidence_sar_temporal_window", "software_sync_low_confidence_review_window", blockers
    blockers.append("unexpected_oty2_gate")
    return "not_ready_for_sar_temporal_window", "blocked_unexpected_gate", blockers


def build_window_row(
    row: Mapping[str, Any],
    *,
    args: argparse.Namespace,
    sar_frame_count: int,
    sync_mode: str,
    offset_seconds: float,
    jitter_padding: int,
) -> dict[str, Any]:
    optical_fps = float(args.optical_fps)
    sar_fps = float(args.sar_fps)
    fps_ratio = sar_fps / optical_fps
    scene = str(row.get("scene", "") or "")
    start_frame = safe_int(row.get("frame_start"), 0) or 0
    end_frame = safe_int(row.get("frame_end"), start_frame) or start_frame
    optical_frame_count = max(0, end_frame - start_frame + 1)
    start_time = start_frame / optical_fps
    end_time = (end_frame + 1) / optical_fps
    category = object_category(row)
    readiness_status, confidence_status, blockers = readiness_and_confidence(row, category)
    uses_primary = readiness_status != "not_ready_for_sar_temporal_window"
    secondary_used = uses_secondary(row, category)
    state_pad, state_reason = state_padding(category, args)
    base_pad = int(args.base_rounding_padding_sar_frames)
    total_padding = base_pad + jitter_padding + state_pad
    padding_reasons = [
        f"base_rounding_padding={base_pad}",
        f"software_sync_jitter_padding={jitter_padding}",
        f"{state_reason}={state_pad}",
    ]

    sar_start_raw: float | None = None
    sar_end_raw: float | None = None
    sar_start_frame: int | None = None
    sar_end_frame: int | None = None
    sar_window_count: int | None = None
    notes = [
        "sar_frame_mapping_uses_optical_time_times_50_not_optical_frame_times_2",
        "no_sar_image_content_or_spatial_search_used",
    ]
    if readiness_status == "not_ready_for_sar_temporal_window":
        notes.append("no_main_sar_temporal_window_generated_for_short_or_noise_object")
    else:
        sar_start_raw = (start_time + offset_seconds) * sar_fps
        sar_end_raw = (end_time + offset_seconds) * sar_fps
        raw_start_frame = math.floor(sar_start_raw) - total_padding
        raw_end_frame = math.ceil(sar_end_raw) + total_padding
        clamped_start = max(0, raw_start_frame)
        clamped_end = min(max(0, sar_frame_count - 1), raw_end_frame) if sar_frame_count else raw_end_frame
        if clamped_start != raw_start_frame or clamped_end != raw_end_frame:
            notes.append("window_clamped_to_sar_frame_inventory")
        sar_start_frame = clamped_start
        sar_end_frame = clamped_end
        sar_window_count = max(0, sar_end_frame - sar_start_frame + 1)

    return {
        "scene": scene,
        "object_hypothesis_id": row.get("object_hypothesis_id", ""),
        "optical_start_frame": start_frame,
        "optical_end_frame": end_frame,
        "optical_frame_count": optical_frame_count,
        "optical_start_time_sec": fmt_float(start_time),
        "optical_end_time_sec": fmt_float(end_time),
        "sar_start_raw": fmt_float(sar_start_raw),
        "sar_end_raw": fmt_float(sar_end_raw),
        "sar_start_frame": "" if sar_start_frame is None else sar_start_frame,
        "sar_end_frame": "" if sar_end_frame is None else sar_end_frame,
        "sar_window_frame_count": "" if sar_window_count is None else sar_window_count,
        "optical_fps": f"{optical_fps:g}",
        "sar_fps": f"{sar_fps:g}",
        "fps_ratio": fmt_float(fps_ratio),
        "sync_mode": sync_mode,
        "offset_seconds": f"{offset_seconds:g}",
        "software_sync_jitter_ms": f"{float(args.software_sync_jitter_ms):g}",
        "padding_sar_frames": "" if readiness_status == "not_ready_for_sar_temporal_window" else total_padding,
        "padding_reason": join_values(padding_reasons),
        "object_state_category": category,
        "uses_primary_observations": bool_text(uses_primary),
        "uses_secondary_observations": bool_text(secondary_used),
        "readiness_status": readiness_status,
        "confidence_status": confidence_status,
        "blockers": join_values(blockers),
        "notes": join_values(notes),
    }


def sample_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    priority = {
        "ready_primary_sar_temporal_window": 0,
        "ready_uncertainty_expanded_sar_temporal_window": 1,
        "low_confidence_sar_temporal_window": 2,
        "not_ready_for_sar_temporal_window": 3,
    }
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("scene", "")),
            priority.get(str(row.get("readiness_status", "")), 9),
            str(row.get("object_hypothesis_id", "")),
        ),
    )
    return [dict(row) for row in ordered[:max_rows]]


def summarize_by_scene(
    *,
    scenes: Sequence[str],
    window_rows: Sequence[Mapping[str, Any]],
    p0_status: Mapping[str, Mapping[str, Any]],
    p1_status: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in window_rows:
        by_scene[str(row.get("scene", "") or "")].append(row)
    rows: list[dict[str, Any]] = []
    for scene in scenes:
        scene_rows = by_scene.get(scene, [])
        generated = [row for row in scene_rows if str(row.get("readiness_status", "")) != "not_ready_for_sar_temporal_window"]
        blocked = [row for row in scene_rows if str(row.get("readiness_status", "")) == "not_ready_for_sar_temporal_window"]
        p0 = p0_status.get(scene, {})
        p1 = p1_status.get(scene, {})
        target_status = "available" if scene_rows else str(p0.get("input_status", "blocked_missing_object_stream") or "blocked_missing_object_stream")
        if not scene_rows and scene == "GM_RM011":
            target_status = "blocked_missing_p4g_object_stream"
        blockers = ""
        if not scene_rows:
            blockers = str(p0.get("top_blockers", "") or p0.get("blocker_reason", ""))
        elif not generated:
            blockers = "no_ready_object_level_temporal_windows"
        rows.append(
            {
                "scene": scene,
                "temporal_metadata_status": str(p1.get("best_available_alignment_mode", "unknown") or "unknown"),
                "sync_mode": str(p1.get("sync_mode", "") or ""),
                "offset_status": str(p1.get("offset_status", "") or ""),
                "target_level_input_status": target_status,
                "object_rows_seen": len(scene_rows),
                "sar_temporal_windows_generated": len(generated),
                "not_ready_object_rows": len(blocked),
                "blockers": blockers,
            }
        )
    return rows


def render_contract_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# OTY2 Software-Sync Temporal Contract and SAR Frame Windows",
        "",
        "This audit corrects the OTY2-P1 timing contract and generates object-level SAR temporal frame windows only. It does not enter SAR image content, SAR spatial search, candidate boxes, ranking, GT, training, or annotation proposal work.",
        "",
        "## Timing Contract",
        "",
        f"- optical_fps: `{summary.get('optical_fps', '')}`",
        f"- sar_fps: `{summary.get('sar_fps', '')}`",
        f"- fps_ratio: `{summary.get('fps_ratio', '')}`",
        f"- sync_mode: `{summary.get('sync_mode', '')}`",
        f"- offset_seconds: `{summary.get('offset_seconds', '')}`",
        f"- software_sync_jitter_ms: `{summary.get('software_sync_jitter_ms', '')}`",
        "- This is software synchronization with a zero-offset processing-start assumption, not hardware-grade exact sync.",
        "- No per-frame real timestamps are claimed.",
        "- SAR frame conversion uses `sar_frame = optical_frame * 50 / 24`; it must not use `sar_frame = optical_frame * 2`.",
        "",
        "## Window Formula",
        "",
        "For each ready optical object segment:",
        "",
        "```text",
        "start_time = optical_start_frame / 24",
        "end_time = (optical_end_frame + 1) / 24",
        "sar_start_raw = start_time * 50",
        "sar_end_raw = end_time * 50",
        "sar_start_frame = floor(sar_start_raw) - padding",
        "sar_end_frame = ceil(sar_end_raw) + padding",
        "```",
        "",
        "Padding combines rounding, software-sync jitter, and object-state uncertainty. These are audit defaults, not trained thresholds.",
        "",
        "## Padding Defaults",
        "",
    ]
    for key, value in summary.get("padding_defaults", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Per-Scene Summary",
            "",
            "| scene | temporal metadata | target input | generated windows | not-ready object rows | blockers |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in summary.get("per_scene", []):
        lines.append(
            f"| `{row.get('scene', '')}` | `{row.get('temporal_metadata_status', '')}` / `{row.get('offset_status', '')}` | "
            f"`{row.get('target_level_input_status', '')}` | {row.get('sar_temporal_windows_generated', 0)} | "
            f"{row.get('not_ready_object_rows', 0)} | `{row.get('blockers', '')}` |"
        )
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Artifacts", ""])
    for key, value in summary.get("artifacts", {}).items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now().isoformat(timespec="seconds")
    output_root = resolve_path(args.output_root)
    report_dir = REPO_ROOT / "reports" / "oty2"
    sample_dir = report_dir / "samples"
    p0_dir = resolve_path(args.oty2_p0_output_dir) if args.oty2_p0_output_dir else latest_output_dir(
        output_root, "oty2_object_temporal_alignment_audit", "oty2_object_readiness_gating.csv"
    )
    if p0_dir is None:
        raise FileNotFoundError("Missing OTY2-P0 output directory with readiness gating rows.")
    p1_summary_path = resolve_path(args.oty2_p1_summary) if args.oty2_p1_summary else latest_report_json(
        report_dir, "oty2_temporal_alignment_anchor_summary"
    )
    if p1_summary_path is None:
        raise FileNotFoundError("Missing OTY2-P1 temporal alignment anchor summary.")

    p0_summary = read_json(p0_dir / "oty2_object_temporal_alignment_summary.json")
    p1_summary = read_json(p1_summary_path)
    p0_status = p0_scene_status(p0_summary)
    p1_status = p1_decisions(p1_summary)
    scenes = sorted(set(p0_status) | set(p1_status) | {"GM_RM011"})
    sar_counts = {
        scene: safe_int(p1_status.get(scene, {}).get("sar_frame_count"), safe_int(p0_status.get(scene, {}).get("sar_frame_count"), 0)) or 0
        for scene in scenes
    }
    sync_mode = str(args.sync_mode or p1_summary.get("sync_mode") or "software_sync_zero_offset_assumption")
    offset_seconds = safe_float(args.offset_seconds, safe_float(p1_summary.get("offset_seconds"), 0.0)) or 0.0
    jitter_ms = safe_float(args.software_sync_jitter_ms, safe_float(p1_summary.get("software_sync_jitter_ms"), 20.0)) or 20.0
    jitter_padding = math.ceil((jitter_ms / 1000.0) * float(args.sar_fps))

    gating_rows = read_csv_rows(p0_dir / "oty2_object_readiness_gating.csv")
    window_rows = [
        build_window_row(
            row,
            args=args,
            sar_frame_count=sar_counts.get(str(row.get("scene", "") or ""), 0),
            sync_mode=sync_mode,
            offset_seconds=offset_seconds,
            jitter_padding=jitter_padding,
        )
        for row in gating_rows
    ]
    window_rows = sorted(window_rows, key=lambda row: (str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))))
    per_scene = summarize_by_scene(scenes=scenes, window_rows=window_rows, p0_status=p0_status, p1_status=p1_status)
    readiness_counts = Counter(str(row.get("readiness_status", "") or "unknown") for row in window_rows)
    category_counts = Counter(str(row.get("object_state_category", "") or "unknown") for row in window_rows)

    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    contract_md = report_dir / f"oty2_software_sync_temporal_contract_{timestamp}.md"
    windows_csv = report_dir / f"oty2_object_sar_temporal_windows_{timestamp}.csv"
    summary_json = report_dir / f"oty2_object_sar_temporal_window_summary_{timestamp}.json"
    sample_csv = sample_dir / "oty2_object_sar_temporal_windows_sample.csv"

    summary = {
        "generated_at": generated_at,
        "timestamp": timestamp,
        "stage": "OTY2-P1-software-sync-temporal-window-audit",
        "optical_fps": f"{float(args.optical_fps):g}",
        "sar_fps": f"{float(args.sar_fps):g}",
        "fps_ratio": fmt_float(float(args.sar_fps) / float(args.optical_fps)),
        "sync_mode": sync_mode,
        "offset_seconds": f"{offset_seconds:g}",
        "software_sync_jitter_ms": f"{jitter_ms:g}",
        "software_sync_is_hardware_exact": False,
        "uses_per_frame_real_timestamps": False,
        "p0_output_dir": str(p0_dir),
        "p1_summary": str(p1_summary_path),
        "object_rows_seen": len(window_rows),
        "sar_temporal_windows_generated": sum(1 for row in window_rows if row.get("readiness_status") != "not_ready_for_sar_temporal_window"),
        "not_ready_object_rows": sum(1 for row in window_rows if row.get("readiness_status") == "not_ready_for_sar_temporal_window"),
        "readiness_status_counts": {key: readiness_counts[key] for key in sorted(readiness_counts)},
        "object_state_category_counts": {key: category_counts[key] for key in sorted(category_counts)},
        "padding_defaults": {
            "base_rounding_padding_sar_frames": int(args.base_rounding_padding_sar_frames),
            "software_sync_jitter_padding_sar_frames": jitter_padding,
            "stable_primary_padding_sar_frames": int(args.stable_primary_padding_sar_frames),
            "secondary_or_edge_padding_sar_frames": int(args.secondary_or_edge_padding_sar_frames),
            "ambiguous_padding_sar_frames": int(args.ambiguous_padding_sar_frames),
            "padding_source": "audit_defaults_not_training_thresholds",
        },
        **BOUNDARY_FLAGS,
        "per_scene": per_scene,
        "artifacts": {
            "software_sync_temporal_contract": str(contract_md),
            "object_sar_temporal_windows": str(windows_csv),
            "object_sar_temporal_window_summary": str(summary_json),
            "object_sar_temporal_windows_sample": str(sample_csv),
        },
    }

    write_csv(windows_csv, window_rows, WINDOW_FIELDS)
    write_csv(sample_csv, sample_rows(window_rows, args.max_sample_rows), WINDOW_FIELDS)
    write_json(summary_json, summary)
    contract_md.write_text(render_contract_report(summary), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--oty2-p0-output-dir", default="")
    parser.add_argument("--oty2-p1-summary", default="")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--optical-fps", type=float, default=24.0)
    parser.add_argument("--sar-fps", type=float, default=50.0)
    parser.add_argument("--sync-mode", default="software_sync_zero_offset_assumption")
    parser.add_argument("--offset-seconds", default="0")
    parser.add_argument("--software-sync-jitter-ms", default="20")
    parser.add_argument("--base-rounding-padding-sar-frames", type=int, default=1)
    parser.add_argument("--stable-primary-padding-sar-frames", type=int, default=1)
    parser.add_argument("--secondary-or-edge-padding-sar-frames", type=int, default=2)
    parser.add_argument("--ambiguous-padding-sar-frames", type=int, default=3)
    parser.add_argument("--max-sample-rows", type=int, default=80)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
