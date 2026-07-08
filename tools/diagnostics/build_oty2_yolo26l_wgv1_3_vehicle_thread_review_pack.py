#!/usr/bin/env python
"""Build a WGV1.3 vehicle-thread review pack from existing diagnostic frames.

The pack is organized by WGV1.3 vehicle thread candidate. It copies existing
WGV1.1 fragment frames and WGV1.2 MRQ edge-review frames into an ignored output
folder, then writes lightweight manifests and a Markdown index under reports.

This script does not run a detector, does not replay a tracker, does not create
final boxes, GT boxes, revised annotations, or SAR-ready evidence.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"
REPORTS_DIR = REPO_ROOT / "reports/oty2"
OUTPUTS_DIR = REPO_ROOT / "outputs/oty2"

DEFAULT_THREADS = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_candidates_20260708.csv"
DEFAULT_SPLIT = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_identity_safe_target_family_split_20260708.csv"
DEFAULT_MERGES = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_single_vehicle_temporal_merge_candidates_20260708.csv"
DEFAULT_V11_FRAME_MANIFEST = OUTPUTS_DIR / "y26l_wgv1_1_vehicle_centric_review_20260708/FRAME_MANIFEST.csv"
DEFAULT_V12_EDGE_FRAME_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_frame_manifest_20260708.csv"
DEFAULT_OUTPUT_ROOT = OUTPUTS_DIR / "y26l_wgv1_3_vehicle_thread_review_20260708"

DEFAULT_THREAD_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_manifest_20260708.csv"
DEFAULT_FRAME_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_frame_manifest_20260708.csv"
DEFAULT_EDGE_FRAME_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_edge_frame_manifest_20260708.csv"
DEFAULT_REPORT = REPORTS_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_20260708.md"


THREAD_FIELDS = [
    "wgv1_3_thread_id",
    "scene_id",
    "thread_status",
    "folder_path",
    "target_family_ids",
    "frame_start",
    "frame_end",
    "target_family_count",
    "fragment_frame_count",
    "baseline_frame_count",
    "edge_frame_count",
    "missing_fragment_frame_count",
    "missing_edge_frame_count",
    "included_same_vehicle_edge_ids",
    "primary_box_selection_issue_edge_ids",
    "adjacent_split_boundary_edge_ids",
    "review_required",
    "human_review_priority",
    "review_question",
    "auto_merge_allowed",
    "sar_ready",
    "not_final_box_flag",
    "not_revised_annotation_flag",
    "note",
]

FRAME_FIELDS = [
    "wgv1_3_thread_id",
    "scene_id",
    "target_family_id",
    "source_fragment_id",
    "frame_id",
    "frame_role",
    "image_path_yolo",
    "image_path_baseline_if_available",
    "source_image_path_yolo",
    "source_image_path_baseline_if_available",
    "copy_status",
    "thread_status",
    "identity_safe_split_status",
    "review_question",
    "sar_ready",
    "note",
]

EDGE_FRAME_FIELDS = [
    "wgv1_3_thread_id",
    "scene_id",
    "edge_id",
    "edge_role",
    "frame_id",
    "phase",
    "source_review_item_id",
    "image_path_yolo_annotated",
    "source_annotated_frame_path",
    "copy_status",
    "wgv1_3_edge_decision",
    "tracking_style_decision",
    "review_question",
    "sar_ready",
    "note",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def as_int(value: str) -> int:
    return int(float(value))


def split_ids(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def safe_reset_output_root(path: Path) -> None:
    resolved = path.resolve()
    allowed = OUTPUTS_DIR.resolve()
    if not resolved.is_relative_to(allowed):
        raise RuntimeError(f"Refusing to clear unexpected output path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def copy_if_available(source: Path, destination: Path) -> str:
    if not source.exists():
        return "missing_source"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return "copied"


def folder_name(index: int, thread: dict[str, str]) -> str:
    status = thread["thread_status"]
    if "primary_box" in status:
        status_label = "primary_box_review"
    elif "supported" in status:
        status_label = "same_vehicle_candidate"
    else:
        status_label = "standalone_split"
    return f"{index:02d}_{thread['scene_id']}_{thread['wgv1_3_thread_id']}_{status_label}"


def source_path_from_v11(row: dict[str, str], column: str, v11_root: Path) -> Path | None:
    value = row.get(column, "")
    if not value:
        return None
    return v11_root / value


def build_readme(thread: dict[str, str], split_rows: list[dict[str, str]], edge_rows: list[dict[str, str]]) -> str:
    lines = [
        f"# {thread['wgv1_3_thread_id']}",
        "",
        "本文件夹是 WGV1.3 diagnostic-only 单车时序审阅单元。",
        "",
        "## 基本信息",
        "",
        f"- scene_id: `{thread['scene_id']}`",
        f"- thread_status: `{thread['thread_status']}`",
        f"- frames: `{thread['frame_start']}-{thread['frame_end']}`",
        f"- target_family_ids: `{thread['target_family_ids']}`",
        f"- included_same_vehicle_edge_ids: `{thread['included_same_vehicle_edge_ids']}`",
        f"- primary_box_selection_issue_edge_ids: `{thread['primary_box_selection_issue_edge_ids']}`",
        f"- adjacent_split_boundary_edge_ids: `{thread['adjacent_split_boundary_edge_ids']}`",
        f"- SAR-ready: `no / blocked`",
        "",
        "## 人工应判断什么",
        "",
        "1. `frames_yolo/` 中同一 thread 的目标是否始终指向同一辆真实车。",
        "2. 如果中间有断帧或 gap，车辆主体、位置、运动方向和框覆盖是否仍连续。",
        "3. `edge_review_frames/` 中的断点是否支持同车连接，还是应保持 identity split boundary。",
        "4. 如果标记为 `primary_box_selection_issue`，判断更高分候选是否只是同一辆车上的更好/重复框。",
        "5. 不在这里画新框，不生成 final boxes，不生成 revised annotation，不进入 SAR。",
        "",
        "## target families",
        "",
        "| target_family_id | source_fragment_id | frames | split status |",
        "|---|---|---|---|",
    ]
    for row in split_rows:
        lines.append(
            f"| `{row['target_family_id']}` | `{row['source_fragment_id']}` | {row['frame_start']}-{row['frame_end']} | `{row['identity_safe_split_status']}` |"
        )
    lines.extend(["", "## edges", "", "| edge_id | decision | role | frames |", "|---|---|---|---|"])
    for row in edge_rows:
        role = "included"
        if row["primary_box_selection_issue"] == "yes":
            role = "primary_box_selection_issue"
        elif row["identity_split_boundary"] == "yes":
            role = "split_boundary"
        lines.append(
            f"| `{row['merge_candidate_id']}` | `{row['wgv1_3_edge_decision']}` | `{role}` | {row['from_frame_end']}->{row['to_frame_start']} |"
        )
    return "\n".join(lines) + "\n"


def build_index(thread_rows: list[dict[str, str]]) -> str:
    lines = [
        "# OTY2 YOLO26l WGV1.3 vehicle-thread review pack index",
        "",
        "本索引对应 ignored outputs 中的逐帧审阅包。图片不提交；本索引和 reports/samples 下的 manifest CSV 可以提交。",
        "",
        "## 审阅顺序建议",
        "",
        "1. 先看带 `primary_box_selection_issue` 的 thread，确认是否只是同车重复/更优框选择。",
        "2. 再看 `same_vehicle_thread_candidate_supported_by_tracking_association`，确认同车时序是否连续。",
        "3. 最后看 `standalone_target_family_after_identity_safe_split` 且存在 adjacent split boundary 的项目，确认不应合并。",
        "",
        "| folder | scene | frames | status | target families | included edges | primary issue | split boundaries |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for row in thread_rows:
        frames = f"{row['frame_start']}-{row['frame_end']}"
        lines.append(
            f"| `{row['folder_path']}` | {row['scene_id']} | {frames} | `{row['thread_status']}` | {row['target_family_count']} | `{row['included_same_vehicle_edge_ids']}` | `{row['primary_box_selection_issue_edge_ids']}` | `{row['adjacent_split_boundary_edge_ids']}` |"
        )
    return "\n".join(lines) + "\n"


def build_scene_frame_index(frame_rows: list[dict[str, str]], edge_rows: list[dict[str, str]]) -> str:
    lines = [
        "# INDEX_BY_SCENE_AND_FRAME",
        "",
        "| scene | frame | thread | target/edge | role | path |",
        "|---|---:|---|---|---|---|",
    ]
    merged = []
    for row in frame_rows:
        merged.append((row["scene_id"], as_int(row["frame_id"]), row["wgv1_3_thread_id"], row["target_family_id"], row["frame_role"], row["image_path_yolo"]))
    for row in edge_rows:
        if not row["frame_id"]:
            continue
        merged.append((row["scene_id"], as_int(row["frame_id"]), row["wgv1_3_thread_id"], row["edge_id"], row["edge_role"], row["image_path_yolo_annotated"]))
    for scene_id, frame_id, thread_id, target, role, path in sorted(merged):
        lines.append(f"| {scene_id} | {frame_id} | `{thread_id}` | `{target}` | `{role}` | `{path}` |")
    return "\n".join(lines) + "\n"


def build_report(
    output_root: Path,
    thread_manifest: Path,
    frame_manifest: Path,
    edge_frame_manifest: Path,
    thread_rows: list[dict[str, str]],
    frame_rows: list[dict[str, str]],
    edge_frame_rows: list[dict[str, str]],
) -> str:
    thread_status_counts = Counter(row["thread_status"] for row in thread_rows)
    frame_copy_counts = Counter(row["copy_status"] for row in frame_rows)
    edge_copy_counts = Counter(row["copy_status"] for row in edge_frame_rows)
    lines = [
        "# OTY2 YOLO26l WGV1.3 vehicle-thread review pack",
        "",
        "Date: 2026-07-08",
        "",
        "## 输出",
        "",
        f"- ignored review pack: `{output_root.as_posix()}`",
        f"- thread manifest: `{thread_manifest.as_posix()}`",
        f"- frame manifest: `{frame_manifest.as_posix()}`",
        f"- edge frame manifest: `{edge_frame_manifest.as_posix()}`",
        "",
        "## 说明",
        "",
        "本包按 WGV1.3 vehicle thread candidate 组织，用于人工逐帧验收单车时序合并候选。它复用既有 WGV1.1 fragment render 和 WGV1.2 MRQ edge render，不运行 detector、不运行 tracker replay、不生成 final boxes。",
        "",
        "人工审阅时应先看 `frames_yolo/` 的同车连续性，再看 `edge_review_frames/` 的断点和竞争关系。带 `primary_box_selection_issue` 的项目重点判断更高分框是否只是同一辆车上的重复/更优主框。",
        "",
        "## 计数",
        "",
        f"- thread folders: {len(thread_rows)}",
        f"- fragment frame rows: {len(frame_rows)}",
        f"- edge review frame rows: {len(edge_frame_rows)}",
        "",
        "Thread status counts:",
        "",
    ]
    for status, count in sorted(thread_status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "Fragment frame copy status:", ""])
    for status, count in sorted(frame_copy_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "Edge frame copy status:", ""])
    for status, count in sorted(edge_copy_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 所有内容都是 diagnostic-only。",
            "- 所有 thread 均为 `auto_merge_allowed=no`。",
            "- 所有 thread 均为 `sar_ready=no / blocked`。",
            "- 未生成 final boxes、GT boxes、revised annotation。",
            "- 未进入 SAR pairing/support/selector/ranking。",
            "- 图片只写入 ignored outputs，不提交。",
        ]
    )
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> None:
    threads = read_csv(args.threads)
    split = read_csv(args.split)
    merges = read_csv(args.merges)
    v11_frames = read_csv(args.v11_frame_manifest)
    v12_edge_frames = read_csv(args.v12_edge_frame_manifest)
    v11_root = args.v11_frame_manifest.parent

    safe_reset_output_root(args.output_root)

    split_by_thread: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in split:
        split_by_thread[row["wgv1_3_thread_id"]].append(row)

    merge_by_id = {row["merge_candidate_id"]: row for row in merges}
    v11_by_fragment_frame: dict[tuple[str, int], dict[str, str]] = {}
    for row in v11_frames:
        v11_by_fragment_frame[(row["fragment_id"], as_int(row["frame_id"]))] = row

    v12_by_edge: dict[str, list[dict[str, str]]] = defaultdict(list)
    v12_by_scene_frame: dict[tuple[str, int], dict[str, str]] = {}
    for row in v12_edge_frames:
        v12_by_edge[row["merge_candidate_id"]].append(row)
        v12_by_scene_frame.setdefault((row["scene_id"], as_int(row["frame_id"])), row)

    thread_manifest_rows: list[dict[str, str]] = []
    frame_manifest_rows: list[dict[str, str]] = []
    edge_frame_manifest_rows: list[dict[str, str]] = []
    output_thread_rows: list[dict[str, str]] = []

    for index, thread in enumerate(sorted(threads, key=lambda r: (r["scene_id"], as_int(r["frame_start"]), r["wgv1_3_thread_id"])), start=1):
        folder = folder_name(index, thread)
        folder_path = args.output_root / folder
        frames_yolo_dir = folder_path / "frames_yolo"
        baseline_dir = folder_path / "frames_baseline_if_available"
        edge_dir = folder_path / "edge_review_frames"
        frames_yolo_dir.mkdir(parents=True, exist_ok=True)
        baseline_dir.mkdir(parents=True, exist_ok=True)
        edge_dir.mkdir(parents=True, exist_ok=True)

        thread_split_rows = sorted(split_by_thread[thread["wgv1_3_thread_id"]], key=lambda r: (as_int(r["frame_start"]), r["target_family_id"]))
        edge_ids = split_ids(thread["included_same_vehicle_edge_ids"]) + split_ids(thread["primary_box_selection_issue_edge_ids"]) + split_ids(thread["adjacent_split_boundary_edge_ids"])
        unique_edge_ids = []
        for edge_id in edge_ids:
            if edge_id not in unique_edge_ids:
                unique_edge_ids.append(edge_id)
        thread_edge_rows = [merge_by_id[edge_id] for edge_id in unique_edge_ids if edge_id in merge_by_id]

        copied_fragment = 0
        copied_baseline = 0
        missing_fragment = 0
        for target in thread_split_rows:
            for frame_id in range(as_int(target["frame_start"]), as_int(target["frame_end"]) + 1):
                source_row = v11_by_fragment_frame.get((target["source_fragment_id"], frame_id))
                if source_row:
                    source_yolo = source_path_from_v11(source_row, "image_path_yolo", v11_root)
                    source_baseline = source_path_from_v11(source_row, "image_path_baseline_if_available", v11_root)
                    source_kind = "v1_1_fragment_frame"
                else:
                    fallback_row = v12_by_scene_frame.get((thread["scene_id"], frame_id))
                    source_yolo = Path(fallback_row["annotated_frame_path"]) if fallback_row else None
                    source_baseline = None
                    source_kind = "v1_2_edge_review_fallback" if fallback_row else "missing"
                dest_yolo = frames_yolo_dir / f"{thread['wgv1_3_thread_id']}_{target['target_family_id']}_{frame_id:06d}_diagnostic_yolo26l.png"
                dest_baseline = baseline_dir / f"{thread['wgv1_3_thread_id']}_{target['target_family_id']}_{frame_id:06d}_baseline_if_available.png"
                if source_yolo:
                    copy_status = copy_if_available(source_yolo, dest_yolo)
                    if copy_status == "copied" and source_kind == "v1_2_edge_review_fallback":
                        copy_status = "copied_edge_review_fallback"
                else:
                    copy_status = "missing_manifest_row"
                if copy_status in {"copied", "copied_edge_review_fallback"}:
                    copied_fragment += 1
                else:
                    missing_fragment += 1
                baseline_status = ""
                if source_baseline:
                    baseline_status = copy_if_available(source_baseline, dest_baseline)
                    if baseline_status == "copied":
                        copied_baseline += 1

                frame_manifest_rows.append(
                    {
                        "wgv1_3_thread_id": thread["wgv1_3_thread_id"],
                        "scene_id": thread["scene_id"],
                        "target_family_id": target["target_family_id"],
                        "source_fragment_id": target["source_fragment_id"],
                        "frame_id": str(frame_id),
                        "frame_role": target["identity_safe_split_status"],
                        "image_path_yolo": rel(dest_yolo) if copy_status == "copied" else "",
                        "image_path_baseline_if_available": rel(dest_baseline) if baseline_status == "copied" else "",
                        "source_image_path_yolo": source_yolo.as_posix() if source_yolo else "",
                        "source_image_path_baseline_if_available": source_baseline.as_posix() if source_baseline else "",
                        "copy_status": copy_status,
                        "thread_status": thread["thread_status"],
                        "identity_safe_split_status": target["identity_safe_split_status"],
                        "review_question": thread["review_question"],
                        "sar_ready": "no / blocked",
                        "note": "diagnostic thread frame;not final box;not GT;not revised annotation",
                    }
                )

        edge_frame_count = 0
        missing_edge_count = 0
        for edge_id in unique_edge_ids:
            edge = merge_by_id.get(edge_id, {})
            if not edge:
                continue
            if edge["primary_box_selection_issue"] == "yes":
                edge_role = "primary_box_selection_issue"
            elif edge["identity_split_boundary"] == "yes":
                edge_role = "split_boundary"
            else:
                edge_role = "included_same_vehicle"
            rows = sorted(v12_by_edge.get(edge_id, []), key=lambda r: as_int(r["frame_id"]))
            if not rows:
                missing_edge_count += 1
                edge_frame_manifest_rows.append(
                    {
                        "wgv1_3_thread_id": thread["wgv1_3_thread_id"],
                        "scene_id": thread["scene_id"],
                        "edge_id": edge_id,
                        "edge_role": edge_role,
                        "frame_id": "",
                        "phase": "",
                        "source_review_item_id": "",
                        "image_path_yolo_annotated": "",
                        "source_annotated_frame_path": "",
                        "copy_status": "missing_existing_edge_review_frame",
                        "wgv1_3_edge_decision": edge.get("wgv1_3_edge_decision", ""),
                        "tracking_style_decision": edge.get("tracking_style_decision", ""),
                        "review_question": edge.get("review_question", ""),
                        "sar_ready": "no / blocked",
                        "note": "edge has no existing WGV1.2 MRQ frame;not rerendered in this pack",
                    }
                )
                continue
            for row in rows:
                source = Path(row["annotated_frame_path"])
                edge_folder = edge_dir / edge_id
                dest = edge_folder / f"{edge_id}_{as_int(row['frame_id']):06d}_diagnostic_yolo26l.png"
                copy_status = copy_if_available(source, dest)
                if copy_status == "copied":
                    edge_frame_count += 1
                else:
                    missing_edge_count += 1
                edge_frame_manifest_rows.append(
                    {
                        "wgv1_3_thread_id": thread["wgv1_3_thread_id"],
                        "scene_id": thread["scene_id"],
                        "edge_id": edge_id,
                        "edge_role": edge_role,
                        "frame_id": row["frame_id"],
                        "phase": row["phase"],
                        "source_review_item_id": row["review_item_id"],
                        "image_path_yolo_annotated": rel(dest) if copy_status == "copied" else "",
                        "source_annotated_frame_path": source.as_posix(),
                        "copy_status": copy_status,
                        "wgv1_3_edge_decision": edge.get("wgv1_3_edge_decision", ""),
                        "tracking_style_decision": edge.get("tracking_style_decision", ""),
                        "review_question": edge.get("review_question", ""),
                        "sar_ready": "no / blocked",
                        "note": "diagnostic edge review frame;not final box;not GT;not revised annotation",
                    }
                )

        folder_path.joinpath("README.md").write_text(build_readme(thread, thread_split_rows, thread_edge_rows), encoding="utf-8")
        thread_manifest_row = {
            "wgv1_3_thread_id": thread["wgv1_3_thread_id"],
            "scene_id": thread["scene_id"],
            "thread_status": thread["thread_status"],
            "folder_path": rel(folder_path),
            "target_family_ids": thread["target_family_ids"],
            "frame_start": thread["frame_start"],
            "frame_end": thread["frame_end"],
            "target_family_count": thread["target_family_count"],
            "fragment_frame_count": str(copied_fragment),
            "baseline_frame_count": str(copied_baseline),
            "edge_frame_count": str(edge_frame_count),
            "missing_fragment_frame_count": str(missing_fragment),
            "missing_edge_frame_count": str(missing_edge_count),
            "included_same_vehicle_edge_ids": thread["included_same_vehicle_edge_ids"],
            "primary_box_selection_issue_edge_ids": thread["primary_box_selection_issue_edge_ids"],
            "adjacent_split_boundary_edge_ids": thread["adjacent_split_boundary_edge_ids"],
            "review_required": "yes",
            "human_review_priority": thread["human_review_priority"],
            "review_question": thread["review_question"],
            "auto_merge_allowed": "no",
            "sar_ready": "no / blocked",
            "not_final_box_flag": "yes",
            "not_revised_annotation_flag": "yes",
            "note": "WGV1.3 vehicle-thread review folder;diagnostic only;images ignored",
        }
        thread_manifest_rows.append(thread_manifest_row)
        output_thread_rows.append(thread_manifest_row)

    args.output_root.joinpath("README.md").write_text(
        "WGV1.3 vehicle-thread review pack. Diagnostic-only; images are ignored and not committed.\n",
        encoding="utf-8",
    )
    args.output_root.joinpath("INDEX_BY_THREAD.md").write_text(build_index(output_thread_rows), encoding="utf-8")
    args.output_root.joinpath("INDEX_BY_SCENE_AND_FRAME.md").write_text(
        build_scene_frame_index(frame_manifest_rows, edge_frame_manifest_rows),
        encoding="utf-8",
    )
    write_csv(args.output_root / "THREAD_MANIFEST.csv", thread_manifest_rows, THREAD_FIELDS)
    write_csv(args.output_root / "FRAME_MANIFEST.csv", frame_manifest_rows, FRAME_FIELDS)
    write_csv(args.output_root / "EDGE_FRAME_MANIFEST.csv", edge_frame_manifest_rows, EDGE_FRAME_FIELDS)

    write_csv(args.thread_manifest, thread_manifest_rows, THREAD_FIELDS)
    write_csv(args.frame_manifest, frame_manifest_rows, FRAME_FIELDS)
    write_csv(args.edge_frame_manifest, edge_frame_manifest_rows, EDGE_FRAME_FIELDS)
    args.report.write_text(
        build_report(
            args.output_root,
            args.thread_manifest,
            args.frame_manifest,
            args.edge_frame_manifest,
            thread_manifest_rows,
            frame_manifest_rows,
            edge_frame_manifest_rows,
        ),
        encoding="utf-8",
    )

    print(f"wrote review pack {args.output_root}")
    print(f"wrote {args.thread_manifest} rows={len(thread_manifest_rows)}")
    print(f"wrote {args.frame_manifest} rows={len(frame_manifest_rows)}")
    print(f"wrote {args.edge_frame_manifest} rows={len(edge_frame_manifest_rows)}")
    print(f"wrote {args.report}")
    print("thread statuses:", dict(Counter(row["thread_status"] for row in thread_manifest_rows)))
    print("frame copy statuses:", dict(Counter(row["copy_status"] for row in frame_manifest_rows)))
    print("edge copy statuses:", dict(Counter(row["copy_status"] for row in edge_frame_manifest_rows)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=Path, default=DEFAULT_THREADS)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--merges", type=Path, default=DEFAULT_MERGES)
    parser.add_argument("--v11-frame-manifest", type=Path, default=DEFAULT_V11_FRAME_MANIFEST)
    parser.add_argument("--v12-edge-frame-manifest", type=Path, default=DEFAULT_V12_EDGE_FRAME_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--thread-manifest", type=Path, default=DEFAULT_THREAD_MANIFEST)
    parser.add_argument("--frame-manifest", type=Path, default=DEFAULT_FRAME_MANIFEST)
    parser.add_argument("--edge-frame-manifest", type=Path, default=DEFAULT_EDGE_FRAME_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    build(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
