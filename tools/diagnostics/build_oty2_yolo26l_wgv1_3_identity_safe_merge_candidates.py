#!/usr/bin/env python
"""Build WGV1.3 identity-safe diagnostic merge candidates.

This script consumes WGV1.2 target-family candidates, WGV1.2 merge candidates,
and the tracking-style MRQ adjudication. It produces diagnostic-only WGV1.3
tables that separate:

- same-vehicle temporal candidates supported by local tracking evidence;
- same-object duplicate / better-box primary-selection issues;
- spatially distinct or gate-blocked split boundaries.

It does not create final boxes, GT boxes, revised annotations, tracker replay,
or SAR-ready evidence.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"
REPORTS_DIR = REPO_ROOT / "reports/oty2"

DEFAULT_TARGET_FAMILIES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv"
DEFAULT_MERGES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_candidates_20260708.csv"
DEFAULT_GATE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_merge_candidate_multicar_gate_20260708.csv"
DEFAULT_ADJUDICATION = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_mrq_tracking_style_association_adjudication_20260708.csv"

DEFAULT_SPLIT_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_identity_safe_target_family_split_20260708.csv"
DEFAULT_MERGE_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_single_vehicle_temporal_merge_candidates_20260708.csv"
DEFAULT_THREAD_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_candidates_20260708.csv"
DEFAULT_REPORT = REPORTS_DIR / "oty2_yolo26l_wgv1_3_identity_safe_temporal_merge_candidates_20260708.md"


SPLIT_FIELDS = [
    "target_family_id",
    "scene_id",
    "wgv1_3_thread_id",
    "thread_status",
    "source_fragment_id",
    "frame_start",
    "frame_end",
    "frame_count",
    "class_sequence",
    "x_bin_sequence",
    "candidate_node_ids",
    "source_detection_ids",
    "identity_safe_split_status",
    "included_same_vehicle_edge_ids",
    "primary_box_selection_issue_edge_ids",
    "split_boundary_edge_ids",
    "blocked_edge_ids",
    "review_required",
    "auto_merge_allowed",
    "sar_ready",
    "not_final_box_flag",
    "not_revised_annotation_flag",
    "note",
]

MERGE_FIELDS = [
    "merge_candidate_id",
    "scene_id",
    "from_target_family_id",
    "to_target_family_id",
    "from_frame_end",
    "to_frame_start",
    "gap_frame_count",
    "wgv1_2_candidate_strength",
    "wgv1_2_multicar_gate_status",
    "tracking_style_decision",
    "tracking_association_mode",
    "endpoint_iou",
    "endpoint_intersection_over_min_area",
    "endpoint_center_distance_norm",
    "same_frame_to_best_same_object_flag",
    "wgv1_3_edge_decision",
    "include_in_vehicle_thread_candidate",
    "identity_split_boundary",
    "primary_box_selection_issue",
    "human_review_priority",
    "reason_codes",
    "mechanism_rule",
    "review_question",
    "auto_merge_allowed",
    "sar_ready",
    "not_final_box_flag",
    "not_revised_annotation_flag",
    "note",
]

THREAD_FIELDS = [
    "wgv1_3_thread_id",
    "scene_id",
    "thread_status",
    "target_family_ids",
    "frame_start",
    "frame_end",
    "target_family_count",
    "included_same_vehicle_edge_ids",
    "primary_box_selection_issue_edge_ids",
    "adjacent_split_boundary_edge_ids",
    "adjacent_blocked_edge_ids",
    "review_required",
    "human_review_priority",
    "review_question",
    "auto_merge_allowed",
    "sar_ready",
    "not_final_box_flag",
    "not_revised_annotation_flag",
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


def join_ids(values: list[str] | set[str]) -> str:
    return ";".join(sorted(v for v in values if v))


class UnionFind:
    def __init__(self, nodes: list[str]) -> None:
        self.parent = {node: node for node in nodes}

    def find(self, node: str) -> str:
        parent = self.parent[node]
        if parent != node:
            self.parent[node] = self.find(parent)
        return self.parent[node]

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        self.parent[rb] = ra


def adjudication_decision(merge: dict[str, str], adjudication_by_merge: dict[str, dict[str, str]]) -> dict[str, str]:
    merge_id = merge["merge_candidate_id"]
    adj = adjudication_by_merge.get(merge_id, {})
    strength = merge["candidate_strength"]
    tracking_decision = adj.get("tracking_style_decision", "")
    same_frame_flag = adj.get("same_frame_to_best_same_object_flag", "")
    reason_codes = ";".join(x for x in [merge.get("reason_codes", ""), adj.get("reason_codes", "")] if x)

    if strength == "blocked":
        edge_decision = "identity_split_boundary_blocked_by_wgv1_2"
        include = "no"
        boundary = "yes"
        primary_issue = "no"
        priority = "high"
        rule = "wgv1_2_sequence_or_endpoint_blocker_preserved"
        note = "WGV1.2 already blocked this candidate; preserve as identity-safe split boundary."
    elif tracking_decision == "diagnostic_same_vehicle_candidate_supported":
        edge_decision = "identity_safe_same_vehicle_thread_candidate"
        include = "yes"
        boundary = "no"
        primary_issue = "no"
        priority = "medium"
        rule = adj.get("mechanism_rule", "local_tracking_association_supports_review_candidate")
        note = "Local tracking evidence supports a diagnostic same-vehicle candidate; still review-only."
    elif tracking_decision == "same_object_better_box_primary_selection_issue":
        edge_decision = "identity_safe_same_vehicle_candidate_with_primary_box_selection_issue"
        include = "yes"
        boundary = "no"
        primary_issue = "yes"
        priority = "high"
        rule = adj.get("mechanism_rule", "resolve_duplicate_candidate_before_identity_split")
        note = "A higher-scoring same-frame candidate appears to be a duplicate or better box on the same vehicle; resolve primary-box selection during review."
    elif tracking_decision == "diagnostic_weak_same_vehicle_candidate":
        edge_decision = "weak_same_vehicle_thread_candidate_requires_review"
        include = "yes"
        boundary = "no"
        primary_issue = "no"
        priority = "high"
        rule = adj.get("mechanism_rule", "weak_local_association_requires_visual_confirmation")
        note = "Weak local association; keep as diagnostic thread candidate only for human review."
    elif tracking_decision == "keep_separate_competing_candidate_better":
        edge_decision = "identity_split_boundary_spatially_distinct_competitor"
        include = "no"
        boundary = "yes"
        primary_issue = "no"
        priority = "high"
        rule = adj.get("mechanism_rule", "spatially_distinct_competing_candidate_wins_local_association")
        note = "A spatially distinct candidate better matches the previous endpoint; do not join target families."
    elif tracking_decision:
        edge_decision = "identity_split_boundary_tracking_ambiguous"
        include = "no"
        boundary = "yes"
        primary_issue = "no"
        priority = "high"
        rule = adj.get("mechanism_rule", "tracking_association_ambiguous")
        note = "Tracking-style association is ambiguous; keep as split boundary until visual review."
    else:
        edge_decision = "identity_split_boundary_missing_tracking_adjudication"
        include = "no"
        boundary = "yes"
        primary_issue = "no"
        priority = "high"
        rule = "missing_tracking_adjudication"
        note = "No tracking-style adjudication row exists; do not join target families."

    return {
        "merge_candidate_id": merge_id,
        "scene_id": merge["scene_id"],
        "from_target_family_id": merge["from_target_family_id"],
        "to_target_family_id": merge["to_target_family_id"],
        "from_frame_end": merge["from_frame_end"],
        "to_frame_start": merge["to_frame_start"],
        "gap_frame_count": merge["gap_frame_count"],
        "wgv1_2_candidate_strength": strength,
        "wgv1_2_multicar_gate_status": "",
        "tracking_style_decision": tracking_decision or "not_adjudicated",
        "tracking_association_mode": adj.get("tracking_association_mode", ""),
        "endpoint_iou": adj.get("endpoint_iou", ""),
        "endpoint_intersection_over_min_area": adj.get("endpoint_intersection_over_min_area", ""),
        "endpoint_center_distance_norm": adj.get("endpoint_center_distance_norm", ""),
        "same_frame_to_best_same_object_flag": same_frame_flag,
        "wgv1_3_edge_decision": edge_decision,
        "include_in_vehicle_thread_candidate": include,
        "identity_split_boundary": boundary,
        "primary_box_selection_issue": primary_issue,
        "human_review_priority": priority,
        "reason_codes": reason_codes,
        "mechanism_rule": rule,
        "review_question": (
            "Do these two target families preserve one real-vehicle referent after resolving duplicate boxes and distinct competitors?"
        ),
        "auto_merge_allowed": "no",
        "sar_ready": "no / blocked",
        "not_final_box_flag": "yes",
        "not_revised_annotation_flag": "yes",
        "note": note,
    }


def assign_gate_status(merge_rows: list[dict[str, str]], gate_rows: list[dict[str, str]]) -> None:
    gate_by_id = {row["merge_candidate_id"]: row for row in gate_rows}
    for row in merge_rows:
        gate = gate_by_id.get(row["merge_candidate_id"], {})
        row["wgv1_2_multicar_gate_status"] = gate.get("multicar_merge_gate_status", "")
        if gate.get("multicar_gate_reason_codes"):
            existing = row["reason_codes"]
            row["reason_codes"] = ";".join(x for x in [existing, gate["multicar_gate_reason_codes"]] if x)


def build_thread_ids(
    target_rows: list[dict[str, str]],
    merge_rows: list[dict[str, str]],
) -> dict[str, str]:
    target_ids = [row["target_family_id"] for row in target_rows]
    target_by_id = {row["target_family_id"]: row for row in target_rows}
    uf = UnionFind(target_ids)
    for row in merge_rows:
        if row["include_in_vehicle_thread_candidate"] == "yes":
            uf.union(row["from_target_family_id"], row["to_target_family_id"])

    components: dict[tuple[str, str], list[str]] = defaultdict(list)
    scene_by_tf = {row["target_family_id"]: row["scene_id"] for row in target_rows}
    for tf_id in target_ids:
        components[(scene_by_tf[tf_id], uf.find(tf_id))].append(tf_id)

    thread_id_by_tf: dict[str, str] = {}
    seq_by_scene: Counter[str] = Counter()
    def component_sort_key(item: tuple[tuple[str, str], list[str]]) -> tuple[str, int, str]:
        (scene_id, _root), members = item
        min_frame = min(as_int(target_by_id[member]["frame_start"]) for member in members)
        return scene_id, min_frame, min(members)

    for (scene_id, _root), members in sorted(components.items(), key=component_sort_key):
        seq_by_scene[scene_id] += 1
        thread_id = f"{scene_id}_WGV13T{seq_by_scene[scene_id]:03d}"
        for member in members:
            thread_id_by_tf[member] = thread_id
    return thread_id_by_tf


def build_outputs(
    target_rows: list[dict[str, str]],
    merge_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    thread_id_by_tf = build_thread_ids(target_rows, merge_rows)
    target_by_id = {row["target_family_id"]: row for row in target_rows}

    included_edges_by_tf: dict[str, list[str]] = defaultdict(list)
    primary_edges_by_tf: dict[str, list[str]] = defaultdict(list)
    boundary_edges_by_tf: dict[str, list[str]] = defaultdict(list)
    blocked_edges_by_tf: dict[str, list[str]] = defaultdict(list)

    for edge in merge_rows:
        for tf_id in [edge["from_target_family_id"], edge["to_target_family_id"]]:
            if edge["include_in_vehicle_thread_candidate"] == "yes":
                included_edges_by_tf[tf_id].append(edge["merge_candidate_id"])
            if edge["primary_box_selection_issue"] == "yes":
                primary_edges_by_tf[tf_id].append(edge["merge_candidate_id"])
            if edge["identity_split_boundary"] == "yes":
                boundary_edges_by_tf[tf_id].append(edge["merge_candidate_id"])
            if edge["wgv1_2_candidate_strength"] == "blocked":
                blocked_edges_by_tf[tf_id].append(edge["merge_candidate_id"])

    members_by_thread: dict[str, list[str]] = defaultdict(list)
    for tf_id, thread_id in thread_id_by_tf.items():
        members_by_thread[thread_id].append(tf_id)

    thread_status_by_id: dict[str, str] = {}
    for thread_id, members in members_by_thread.items():
        included = [edge for edge in merge_rows if edge["include_in_vehicle_thread_candidate"] == "yes" and edge["from_target_family_id"] in members and edge["to_target_family_id"] in members]
        if len(members) == 1:
            status = "standalone_target_family_after_identity_safe_split"
        elif any(edge["primary_box_selection_issue"] == "yes" for edge in included):
            status = "same_vehicle_thread_candidate_with_primary_box_selection_issue"
        else:
            status = "same_vehicle_thread_candidate_supported_by_tracking_association"
        thread_status_by_id[thread_id] = status

    split_rows: list[dict[str, str]] = []
    for target in sorted(target_rows, key=lambda r: (r["scene_id"], as_int(r["frame_start"]), r["target_family_id"])):
        tf_id = target["target_family_id"]
        thread_id = thread_id_by_tf[tf_id]
        included = included_edges_by_tf[tf_id]
        boundaries = boundary_edges_by_tf[tf_id]
        primary = primary_edges_by_tf[tf_id]
        blocked = blocked_edges_by_tf[tf_id]
        if included and primary:
            split_status = "in_same_vehicle_thread_candidate_primary_box_review"
        elif included:
            split_status = "in_same_vehicle_thread_candidate"
        elif boundaries:
            split_status = "kept_standalone_by_identity_split_boundary"
        else:
            split_status = "standalone_no_adjacent_merge_candidate"
        split_rows.append(
            {
                "target_family_id": tf_id,
                "scene_id": target["scene_id"],
                "wgv1_3_thread_id": thread_id,
                "thread_status": thread_status_by_id[thread_id],
                "source_fragment_id": target["source_fragment_id"],
                "frame_start": target["frame_start"],
                "frame_end": target["frame_end"],
                "frame_count": target["frame_count"],
                "class_sequence": target["class_sequence"],
                "x_bin_sequence": target["x_bin_sequence"],
                "candidate_node_ids": target["candidate_node_ids"],
                "source_detection_ids": target["source_detection_ids"],
                "identity_safe_split_status": split_status,
                "included_same_vehicle_edge_ids": join_ids(included),
                "primary_box_selection_issue_edge_ids": join_ids(primary),
                "split_boundary_edge_ids": join_ids(boundaries),
                "blocked_edge_ids": join_ids(blocked),
                "review_required": "yes",
                "auto_merge_allowed": "no",
                "sar_ready": "no / blocked",
                "not_final_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "WGV1.3 diagnostic target-family split only; not final identity or annotation.",
            }
        )

    thread_rows: list[dict[str, str]] = []
    def thread_sort_key(item: tuple[str, list[str]]) -> tuple[str, int, str]:
        thread_id, members = item
        scene_id = target_by_id[members[0]]["scene_id"]
        min_frame = min(as_int(target_by_id[member]["frame_start"]) for member in members)
        return scene_id, min_frame, thread_id

    for thread_id, members in sorted(members_by_thread.items(), key=thread_sort_key):
        targets = [target_by_id[member] for member in sorted(members, key=lambda m: as_int(target_by_id[m]["frame_start"]))]
        scene_id = targets[0]["scene_id"]
        included_edges = [edge for edge in merge_rows if edge["include_in_vehicle_thread_candidate"] == "yes" and edge["from_target_family_id"] in members and edge["to_target_family_id"] in members]
        primary_edges = [edge for edge in included_edges if edge["primary_box_selection_issue"] == "yes"]
        adjacent_boundaries = [edge for edge in merge_rows if edge["identity_split_boundary"] == "yes" and (edge["from_target_family_id"] in members or edge["to_target_family_id"] in members)]
        adjacent_blocked = [edge for edge in adjacent_boundaries if edge["wgv1_2_candidate_strength"] == "blocked"]
        priority = "high" if primary_edges or adjacent_boundaries else "medium"
        if len(members) == 1:
            question = "Is this standalone target family a complete vehicle observation fragment, or should it remain separated?"
        else:
            question = "Do all target families in this thread preserve one real-vehicle referent after duplicate-box and competitor checks?"
        thread_rows.append(
            {
                "wgv1_3_thread_id": thread_id,
                "scene_id": scene_id,
                "thread_status": thread_status_by_id[thread_id],
                "target_family_ids": join_ids(members),
                "frame_start": str(min(as_int(t["frame_start"]) for t in targets)),
                "frame_end": str(max(as_int(t["frame_end"]) for t in targets)),
                "target_family_count": str(len(members)),
                "included_same_vehicle_edge_ids": join_ids(edge["merge_candidate_id"] for edge in included_edges),
                "primary_box_selection_issue_edge_ids": join_ids(edge["merge_candidate_id"] for edge in primary_edges),
                "adjacent_split_boundary_edge_ids": join_ids(edge["merge_candidate_id"] for edge in adjacent_boundaries),
                "adjacent_blocked_edge_ids": join_ids(edge["merge_candidate_id"] for edge in adjacent_blocked),
                "review_required": "yes",
                "human_review_priority": priority,
                "review_question": question,
                "auto_merge_allowed": "no",
                "sar_ready": "no / blocked",
                "not_final_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "Vehicle thread candidate for diagnostic review only; not SAR-ready.",
            }
        )
    return split_rows, thread_rows


def build_report(
    split_rows: list[dict[str, str]],
    merge_rows: list[dict[str, str]],
    thread_rows: list[dict[str, str]],
    split_out: Path,
    merge_out: Path,
    thread_out: Path,
) -> str:
    merge_counts = Counter(row["wgv1_3_edge_decision"] for row in merge_rows)
    thread_counts = Counter(row["thread_status"] for row in thread_rows)
    scene_counts = Counter(row["scene_id"] for row in thread_rows)
    connected_threads = [row for row in thread_rows if int(row["target_family_count"]) > 1]
    primary_threads = [row for row in thread_rows if row["primary_box_selection_issue_edge_ids"]]
    boundary_edges = [row for row in merge_rows if row["identity_split_boundary"] == "yes"]

    lines = [
        "# OTY2 YOLO26l WGV1.3 identity-safe temporal merge candidates",
        "",
        "Date: 2026-07-08",
        "",
        "## 本阶段结论",
        "",
        "WGV1.3 将 WGV1.2 的 guardrail / MRQ 结果推进为 identity-safe target-family split 和可人工验收的单车时序合并候选。核心变化是：多车竞争不再作为粗门控直接阻断，而是先用 tracking-style association 判断更高分候选是同车重复框，还是空间上分离的另一辆车。",
        "",
        "本产物仍然严格是 diagnostic-only：不生成 final boxes、GT boxes、revised annotation，不进入 SAR，也不声明任何 thread SAR-ready。",
        "",
        f"- target-family split: `{split_out.as_posix()}`",
        f"- single-vehicle merge candidates: `{merge_out.as_posix()}`",
        f"- vehicle thread candidates: `{thread_out.as_posix()}`",
        "",
        "## 计数",
        "",
        f"- target families: {len(split_rows)}",
        f"- merge candidates: {len(merge_rows)}",
        f"- vehicle thread candidates: {len(thread_rows)}",
        f"- multi-fragment thread candidates: {len(connected_threads)}",
        f"- primary-box selection issue threads: {len(primary_threads)}",
        f"- identity split boundary edges: {len(boundary_edges)}",
        "",
        "Edge decision counts:",
        "",
    ]
    for decision, count in sorted(merge_counts.items()):
        lines.append(f"- `{decision}`: {count}")
    lines.extend(["", "Thread status counts:", ""])
    for status, count in sorted(thread_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "Scene thread counts:", ""])
    for scene_id, count in sorted(scene_counts.items()):
        lines.append(f"- `{scene_id}`: {count}")

    lines.extend(
        [
            "",
            "## 机制解释",
            "",
            "WGV1.3 的判定顺序是：",
            "",
            "1. 先保留 WGV1.2 已经 blocked 的边作为 identity split boundary。",
            "2. 对 MRQ review-only 边使用 tracking-style association。",
            "3. 如果 endpoint overlap / IoMin / normalized motion 支持同车，且 proposed to-target 是最佳局部延续，则放入同车 thread candidate。",
            "4. 如果最佳局部候选不是 proposed to-target，但二者在同一帧压在同一辆车上，则记录 `same_object_better_box_primary_selection_issue`，仍允许放入同车 thread candidate，后续只修正诊断主框选择。",
            "5. 如果最佳局部候选空间上分离，或原始边已经 blocked，则不合并，作为 split boundary。",
            "",
            "这直接回应了前一轮的问题：前后帧框有重叠、光学上落在同一辆车上时，不能因为存在同帧竞争框就拒绝合并候选。应先判断竞争框是否只是同车重复框。只有空间上分离的竞争目标才构成真正的身份拆分证据。",
            "",
            "## 可审阅 thread candidates",
            "",
            "| thread | scene | frames | target families | included edges | primary-box issue | adjacent split boundaries | status |",
            "|---|---|---|---:|---|---|---|---|",
        ]
    )
    sorted_thread_rows = sorted(thread_rows, key=lambda r: (r["scene_id"], as_int(r["frame_start"]), r["wgv1_3_thread_id"]))
    for row in sorted_thread_rows:
        if int(row["target_family_count"]) <= 1 and not row["adjacent_split_boundary_edge_ids"]:
            continue
        frames = f"{row['frame_start']}-{row['frame_end']}"
        lines.append(
            f"| `{row['wgv1_3_thread_id']}` | {row['scene_id']} | {frames} | {row['target_family_count']} | `{row['included_same_vehicle_edge_ids']}` | `{row['primary_box_selection_issue_edge_ids']}` | `{row['adjacent_split_boundary_edge_ids']}` | `{row['thread_status']}` |"
        )

    lines.extend(
        [
            "",
            "## 仍然 blocked 的内容",
            "",
            "以下边界不得被 WGV1.3 自动合并，只能作为人工复核或后续机制改进对象：",
            "",
            "| edge | scene | from -> to | frames | decision | reason |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in boundary_edges:
        frames = f"{row['from_frame_end']}->{row['to_frame_start']}"
        tf = f"{row['from_target_family_id']} -> {row['to_target_family_id']}"
        lines.append(f"| `{row['merge_candidate_id']}` | {row['scene_id']} | `{tf}` | {frames} | `{row['wgv1_3_edge_decision']}` | `{row['reason_codes']}` |")

    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 所有 rows 均为 `auto_merge_allowed=no`。",
            "- 所有 rows 均为 `sar_ready=no / blocked`。",
            "- `same_object_better_box_primary_selection_issue` 只表示诊断主框选择问题，不写新 bbox，不生成 final boxes。",
            "- WGV1.3 thread candidate 只是人工验收入口，不是 identity truth。",
            "- 本阶段未进入 SAR、未运行 tracker replay、未运行 detector swap。",
        ]
    )
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> None:
    target_rows = read_csv(args.target_families)
    merge_input_rows = read_csv(args.merges)
    gate_rows = read_csv(args.gate)
    adjudication_rows = read_csv(args.adjudication)
    adjudication_by_merge = {row["merge_candidate_id"]: row for row in adjudication_rows}

    merge_rows = [adjudication_decision(row, adjudication_by_merge) for row in merge_input_rows]
    assign_gate_status(merge_rows, gate_rows)
    split_rows, thread_rows = build_outputs(target_rows, merge_rows)

    write_csv(args.split_output, split_rows, SPLIT_FIELDS)
    write_csv(args.merge_output, merge_rows, MERGE_FIELDS)
    write_csv(args.thread_output, thread_rows, THREAD_FIELDS)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        build_report(split_rows, merge_rows, thread_rows, args.split_output, args.merge_output, args.thread_output),
        encoding="utf-8",
    )

    print(f"wrote {args.split_output} rows={len(split_rows)}")
    print(f"wrote {args.merge_output} rows={len(merge_rows)}")
    print(f"wrote {args.thread_output} rows={len(thread_rows)}")
    print(f"wrote {args.report}")
    print("edge decisions:", dict(Counter(row["wgv1_3_edge_decision"] for row in merge_rows)))
    print("thread statuses:", dict(Counter(row["thread_status"] for row in thread_rows)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-families", type=Path, default=DEFAULT_TARGET_FAMILIES)
    parser.add_argument("--merges", type=Path, default=DEFAULT_MERGES)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--adjudication", type=Path, default=DEFAULT_ADJUDICATION)
    parser.add_argument("--split-output", type=Path, default=DEFAULT_SPLIT_OUT)
    parser.add_argument("--merge-output", type=Path, default=DEFAULT_MERGE_OUT)
    parser.add_argument("--thread-output", type=Path, default=DEFAULT_THREAD_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    build(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
