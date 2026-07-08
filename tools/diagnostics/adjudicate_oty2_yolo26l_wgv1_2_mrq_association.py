#!/usr/bin/env python
"""Adjudicate WGV1.2 MRQ associations with tracking-style local evidence.

This is a diagnostic-only association analysis. It uses YOLO26l candidate boxes
and local visual-association logic to decide whether a review-only merge should
remain a diagnostic same-vehicle candidate, stay separated, or require visual
review. It does not create final boxes, GT boxes, revised annotations, tracker
replay output, or SAR-ready evidence.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from math import hypot
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"
REPORTS_DIR = REPO_ROOT / "reports/oty2"

DEFAULT_QUEUE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_review_queue_20260708.csv"
DEFAULT_BANK = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv"
DEFAULT_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_mrq_tracking_style_association_adjudication_20260708.csv"
DEFAULT_RULES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_tracking_style_association_rules_20260708.csv"
DEFAULT_REPORT = REPORTS_DIR / "oty2_yolo26l_wgv1_2_tracking_style_association_adjudication_20260708.md"

FIELDS = [
    "review_item_id",
    "scene_id",
    "merge_candidate_id",
    "from_target_family_id",
    "to_target_family_id",
    "from_endpoint_frame",
    "to_endpoint_frame",
    "gap_frame_count",
    "endpoint_iou",
    "endpoint_intersection_over_min_area",
    "endpoint_center_distance_px",
    "endpoint_center_distance_norm",
    "endpoint_area_ratio",
    "from_class",
    "to_class",
    "from_x_bin",
    "to_x_bin",
    "class_match",
    "x_bin_match",
    "to_target_rank_among_to_frame_candidates",
    "to_target_best_score",
    "best_to_frame_candidate_id",
    "best_to_frame_candidate_class",
    "best_to_frame_candidate_x_bin",
    "best_to_frame_association_score",
    "same_frame_to_best_iou",
    "same_frame_to_best_intersection_over_min_area",
    "same_frame_to_best_center_distance_norm",
    "same_frame_to_best_area_ratio",
    "same_frame_to_best_same_object_flag",
    "association_score",
    "competition_margin",
    "tracking_association_mode",
    "tracking_style_decision",
    "decision_confidence",
    "reason_codes",
    "mechanism_rule",
    "review_note",
    "auto_merge_allowed",
    "sar_ready",
    "not_final_box_flag",
    "not_revised_annotation_flag",
]

RULE_FIELDS = [
    "rule_id",
    "rule_name",
    "condition",
    "decision_effect",
    "rationale",
    "diagnostic_only_boundary",
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


def as_float(value: str) -> float:
    return float(value)


def target_ids(row: dict[str, str]) -> set[str]:
    return {part for part in row.get("linked_target_family_ids", "").split(";") if part}


def has_target(row: dict[str, str], target_family_id: str) -> bool:
    return target_family_id in target_ids(row)


def bbox(row: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        as_float(row["bbox_x1"]),
        as_float(row["bbox_y1"]),
        as_float(row["bbox_x2"]),
        as_float(row["bbox_y2"]),
    )


def area_box(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def iou_and_iom(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float]:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    aa = area_box(a)
    ab = area_box(b)
    union = aa + ab - inter
    iou = inter / union if union else 0.0
    iom = inter / min(aa, ab) if min(aa, ab) else 0.0
    return iou, iom


def center(row: dict[str, str]) -> tuple[float, float]:
    return as_float(row["bbox_cx"]), as_float(row["bbox_cy"])


def area(row: dict[str, str]) -> float:
    return max(0.0, as_float(row["bbox_w"]) * as_float(row["bbox_h"]))


def safe_area_ratio(a: dict[str, str], b: dict[str, str]) -> float:
    aa = area(a)
    ab = area(b)
    if aa <= 0 or ab <= 0:
        return 999.0
    return max(aa, ab) / min(aa, ab)


def endpoint_rows(
    rows_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]],
    scene_id: str,
    target_family_id: str,
    start: int,
    end: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for frame in range(start, end + 1):
        for row in rows_by_scene_frame.get((scene_id, frame), []):
            if has_target(row, target_family_id):
                rows.append(row)
    return sorted(rows, key=lambda row: as_int(row["frame_id"]))


def association_features(a: dict[str, str], b: dict[str, str]) -> dict[str, float | str]:
    abox = bbox(a)
    bbox_b = bbox(b)
    iou, iom = iou_and_iom(abox, bbox_b)
    ax, ay = center(a)
    bx, by = center(b)
    dist = hypot(bx - ax, by - ay)
    norm = dist / max(as_float(a["bbox_w"]), as_float(a["bbox_h"]), as_float(b["bbox_w"]), as_float(b["bbox_h"]), 1.0)
    area_ratio = safe_area_ratio(a, b)
    class_match = a["class_name"] == b["class_name"]
    x_bin_match = a["x_bin"] == b["x_bin"]
    overlap_score = max(iou, min(1.0, iom * 0.75))
    motion_score = max(0.0, 1.0 - norm)
    scale_score = max(0.0, min(1.0, 1.0 / area_ratio))
    class_score = 1.0 if class_match else 0.25
    xbin_score = 1.0 if x_bin_match else 0.45
    score = 0.38 * overlap_score + 0.27 * motion_score + 0.18 * scale_score + 0.10 * class_score + 0.07 * xbin_score
    return {
        "iou": iou,
        "iom": iom,
        "dist": dist,
        "norm": norm,
        "area_ratio": area_ratio,
        "class_match": "yes" if class_match else "no",
        "x_bin_match": "yes" if x_bin_match else "no",
        "score": score,
    }


def score_to_frame_candidates(
    from_endpoint: dict[str, str],
    candidates: list[dict[str, str]],
) -> list[tuple[float, dict[str, str]]]:
    scored = []
    for candidate in candidates:
        features = association_features(from_endpoint, candidate)
        scored.append((float(features["score"]), candidate))
    return sorted(scored, key=lambda item: item[0], reverse=True)


def same_frame_duplicate_relation(
    proposed: dict[str, str],
    best_candidate: dict[str, str],
) -> dict[str, float | str]:
    if proposed["source_detection_id"] == best_candidate["source_detection_id"]:
        return {
            "iou": 1.0,
            "iom": 1.0,
            "norm": 0.0,
            "area_ratio": 1.0,
            "same_object_flag": "same_candidate",
        }

    features = association_features(proposed, best_candidate)
    same_class = proposed["class_name"] == best_candidate["class_name"]
    same_x_bin = proposed["x_bin"] == best_candidate["x_bin"]
    iou = float(features["iou"])
    iom = float(features["iom"])
    norm = float(features["norm"])

    same_object_duplicate = same_class and (
        iou >= 0.30
        or (iom >= 0.45 and (same_x_bin or norm <= 0.60))
        or (norm <= 0.25 and same_x_bin)
    )
    spatially_distinct = iou < 0.05 and iom < 0.15 and (norm > 0.75 or not same_x_bin)

    if same_object_duplicate:
        flag = "same_object_duplicate_or_better_box"
    elif spatially_distinct:
        flag = "spatially_distinct_competing_vehicle"
    else:
        flag = "ambiguous_same_frame_competition"

    return {
        "iou": iou,
        "iom": iom,
        "norm": norm,
        "area_ratio": float(features["area_ratio"]),
        "same_object_flag": flag,
    }


def adjudicate_item(item: dict[str, str], rows_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]]) -> dict[str, str]:
    scene_id = item["scene_id"]
    from_tf = item["from_target_family_id"]
    to_tf = item["to_target_family_id"]
    from_rows = endpoint_rows(rows_by_scene_frame, scene_id, from_tf, as_int(item["from_frame_start"]), as_int(item["from_frame_end"]))
    to_rows = endpoint_rows(rows_by_scene_frame, scene_id, to_tf, as_int(item["to_frame_start"]), as_int(item["to_frame_end"]))
    reason_codes: list[str] = []
    mechanism_rule = "tracking_association_insufficient"

    if not from_rows or not to_rows:
        return {
            "review_item_id": item["review_item_id"],
            "scene_id": scene_id,
            "merge_candidate_id": item["merge_candidate_id"],
            "from_target_family_id": from_tf,
            "to_target_family_id": to_tf,
            "from_endpoint_frame": "",
            "to_endpoint_frame": "",
            "gap_frame_count": str(max(0, as_int(item["to_frame_start"]) - as_int(item["from_frame_end"]) - 1)),
            "endpoint_iou": "0.000",
            "endpoint_intersection_over_min_area": "0.000",
            "endpoint_center_distance_px": "",
            "endpoint_center_distance_norm": "",
            "endpoint_area_ratio": "",
            "from_class": "",
            "to_class": "",
            "from_x_bin": "",
            "to_x_bin": "",
            "class_match": "no",
            "x_bin_match": "no",
            "to_target_rank_among_to_frame_candidates": "",
            "to_target_best_score": "",
            "best_to_frame_candidate_id": "",
            "best_to_frame_candidate_class": "",
            "best_to_frame_candidate_x_bin": "",
            "best_to_frame_association_score": "",
            "same_frame_to_best_iou": "",
            "same_frame_to_best_intersection_over_min_area": "",
            "same_frame_to_best_center_distance_norm": "",
            "same_frame_to_best_area_ratio": "",
            "same_frame_to_best_same_object_flag": "",
            "association_score": "0.000",
            "competition_margin": "0.000",
            "tracking_association_mode": "missing_endpoint",
            "tracking_style_decision": "needs_visual_review_missing_endpoint",
            "decision_confidence": "low",
            "reason_codes": "missing_endpoint_selected_candidate",
            "mechanism_rule": mechanism_rule,
            "review_note": "Missing selected endpoint candidate; keep review-only.",
            "auto_merge_allowed": "no",
            "sar_ready": "no / blocked",
            "not_final_box_flag": "yes",
            "not_revised_annotation_flag": "yes",
        }

    from_endpoint = from_rows[-1]
    to_endpoint = to_rows[0]
    features = association_features(from_endpoint, to_endpoint)
    to_frame = as_int(to_endpoint["frame_id"])
    to_candidates = rows_by_scene_frame.get((scene_id, to_frame), [])
    scored = score_to_frame_candidates(from_endpoint, to_candidates)
    to_source_id = to_endpoint["source_detection_id"]
    rank = next((idx + 1 for idx, (_score, cand) in enumerate(scored) if cand["source_detection_id"] == to_source_id), 999)
    best_score, best_candidate = scored[0]
    to_score = float(features["score"])
    margin = to_score - (scored[1][0] if rank == 1 and len(scored) > 1 else best_score)
    same_frame_relation = same_frame_duplicate_relation(to_endpoint, best_candidate)

    gap = max(0, to_frame - as_int(from_endpoint["frame_id"]) - 1)
    if float(features["iom"]) >= 0.45 or float(features["iou"]) >= 0.18:
        reason_codes.append("endpoint_overlap_support")
    if float(features["norm"]) <= 0.45:
        reason_codes.append("normalized_center_support")
    else:
        reason_codes.append("normalized_center_too_far")
    if float(features["area_ratio"]) <= 2.2:
        reason_codes.append("scale_support")
    else:
        reason_codes.append("scale_change_review")
    if features["class_match"] == "yes":
        reason_codes.append("class_support")
    else:
        reason_codes.append("class_conflict")
    if features["x_bin_match"] == "yes":
        reason_codes.append("x_bin_support")
    else:
        reason_codes.append("x_bin_change_review")
    if rank == 1:
        reason_codes.append("to_target_best_match")
    else:
        reason_codes.append("competing_candidate_better_match")
        reason_codes.append(str(same_frame_relation["same_object_flag"]))

    if rank == 1 and to_score >= 0.58 and ("endpoint_overlap_support" in reason_codes or "normalized_center_support" in reason_codes):
        decision = "diagnostic_same_vehicle_candidate_supported"
        confidence = "medium"
        mechanism_rule = "local_tracking_association_supports_review_candidate"
        note = "Endpoint association supports keeping this as a diagnostic same-vehicle candidate; still not final identity truth."
        association_mode = "best_local_continuation"
    elif rank == 1 and to_score >= 0.48:
        decision = "diagnostic_weak_same_vehicle_candidate"
        confidence = "low"
        mechanism_rule = "weak_local_association_requires_visual_confirmation"
        note = "The intended to-target is the best local match but evidence is weak; keep review-only."
        association_mode = "weak_best_local_continuation"
    elif rank != 1 and same_frame_relation["same_object_flag"] == "same_object_duplicate_or_better_box":
        decision = "same_object_better_box_primary_selection_issue"
        confidence = "medium" if to_score >= 0.58 else "low"
        mechanism_rule = "resolve_duplicate_candidate_before_identity_split"
        note = (
            "The best-scoring competing box overlaps the proposed to-target on the same visible vehicle. "
            "Treat this as diagnostic primary-box selection, not as different-vehicle evidence."
        )
        association_mode = "same_object_duplicate_resolution"
    elif rank != 1 and same_frame_relation["same_object_flag"] == "ambiguous_same_frame_competition":
        decision = "needs_visual_review_same_frame_competition_ambiguous"
        confidence = "low"
        mechanism_rule = "same_frame_competition_requires_visual_resolution"
        note = "A competing candidate scores higher, but same-frame relation is ambiguous; keep review-only and do not split automatically."
        association_mode = "ambiguous_competition_resolution"
    elif rank != 1:
        decision = "keep_separate_competing_candidate_better"
        confidence = "medium"
        mechanism_rule = "spatially_distinct_competing_candidate_wins_local_association"
        note = "A spatially distinct competing candidate in the to frame matches the from endpoint better than the proposed to target."
        association_mode = "distinct_competitor_wins"
    else:
        decision = "needs_visual_review_tracking_ambiguous"
        confidence = "low"
        mechanism_rule = "tracking_association_ambiguous"
        note = "Local tracking evidence is ambiguous; keep review-only."
        association_mode = "ambiguous_tracking_evidence"

    return {
        "review_item_id": item["review_item_id"],
        "scene_id": scene_id,
        "merge_candidate_id": item["merge_candidate_id"],
        "from_target_family_id": from_tf,
        "to_target_family_id": to_tf,
        "from_endpoint_frame": from_endpoint["frame_id"],
        "to_endpoint_frame": to_endpoint["frame_id"],
        "gap_frame_count": str(gap),
        "endpoint_iou": f"{float(features['iou']):.3f}",
        "endpoint_intersection_over_min_area": f"{float(features['iom']):.3f}",
        "endpoint_center_distance_px": f"{float(features['dist']):.1f}",
        "endpoint_center_distance_norm": f"{float(features['norm']):.3f}",
        "endpoint_area_ratio": f"{float(features['area_ratio']):.3f}",
        "from_class": from_endpoint["class_name"],
        "to_class": to_endpoint["class_name"],
        "from_x_bin": from_endpoint["x_bin"],
        "to_x_bin": to_endpoint["x_bin"],
        "class_match": str(features["class_match"]),
        "x_bin_match": str(features["x_bin_match"]),
        "to_target_rank_among_to_frame_candidates": str(rank),
        "to_target_best_score": f"{to_score:.3f}",
        "best_to_frame_candidate_id": best_candidate["source_detection_id"],
        "best_to_frame_candidate_class": best_candidate["class_name"],
        "best_to_frame_candidate_x_bin": best_candidate["x_bin"],
        "best_to_frame_association_score": f"{best_score:.3f}",
        "same_frame_to_best_iou": f"{float(same_frame_relation['iou']):.3f}",
        "same_frame_to_best_intersection_over_min_area": f"{float(same_frame_relation['iom']):.3f}",
        "same_frame_to_best_center_distance_norm": f"{float(same_frame_relation['norm']):.3f}",
        "same_frame_to_best_area_ratio": f"{float(same_frame_relation['area_ratio']):.3f}",
        "same_frame_to_best_same_object_flag": str(same_frame_relation["same_object_flag"]),
        "association_score": f"{to_score:.3f}",
        "competition_margin": f"{margin:.3f}",
        "tracking_association_mode": association_mode,
        "tracking_style_decision": decision,
        "decision_confidence": confidence,
        "reason_codes": ";".join(sorted(set(reason_codes))),
        "mechanism_rule": mechanism_rule,
        "review_note": note,
        "auto_merge_allowed": "no",
        "sar_ready": "no / blocked",
        "not_final_box_flag": "yes",
        "not_revised_annotation_flag": "yes",
    }


def rules_rows() -> list[dict[str, str]]:
    return [
        {
            "rule_id": "WGV12_ASSOC_R001",
            "rule_name": "association_before_competition_gate",
            "condition": "Compute pairwise association between from endpoint and every to-frame candidate before using competing-candidate count as a blocker.",
            "decision_effect": "Competing candidates become evidence for ranking, not an automatic rejection.",
            "rationale": "MOT association uses local matching cost and one-to-one assignment; existence of competitors alone does not break a track.",
            "diagnostic_only_boundary": "Does not accept final identity or create final boxes.",
        },
        {
            "rule_id": "WGV12_ASSOC_R002",
            "rule_name": "overlap_or_iom_support",
            "condition": "If endpoint IoU >= 0.18 or intersection-over-min-area >= 0.45, treat local box overlap as positive same-object evidence.",
            "decision_effect": "Allows diagnostic same-vehicle candidate when the intended to target is also the best local match.",
            "rationale": "Adjacent or short-gap boxes on the same visible car can shift or change scale while retaining overlap.",
            "diagnostic_only_boundary": "Review-only candidate; not final annotation.",
        },
        {
            "rule_id": "WGV12_ASSOC_R003",
            "rule_name": "normalized_motion_support",
            "condition": "Use center displacement normalized by max box dimension; <= 0.45 supports continuity.",
            "decision_effect": "Prevents large raw-pixel motion from blocking a large nearby vehicle box.",
            "rationale": "Tracking gates should scale with object size and camera geometry.",
            "diagnostic_only_boundary": "No SAR-ready claim.",
        },
        {
            "rule_id": "WGV12_ASSOC_R004",
            "rule_name": "same_object_duplicate_before_identity_split",
            "condition": "If the higher-scoring to-frame candidate overlaps the proposed to target on the same physical vehicle, treat it as a duplicate or better primary box.",
            "decision_effect": "Keep the same-vehicle diagnostic candidate and record a primary-box selection issue instead of splitting identity.",
            "rationale": "Multi-detector candidates often include nested or shifted boxes on one visible car; these are not evidence for a different vehicle.",
            "diagnostic_only_boundary": "No tracker replay; detection-level diagnostic only.",
        },
        {
            "rule_id": "WGV12_ASSOC_R005",
            "rule_name": "spatially_distinct_competing_candidate_wins",
            "condition": "If another to-frame candidate has higher association score and is spatially distinct from the proposed to target, keep separate or review as identity switch.",
            "decision_effect": "Blocks diagnostic same-vehicle candidate unless later visual review overrides in the diagnostic layer.",
            "rationale": "One-to-one assignment should favor the locally best candidate when the best candidate is a different visible vehicle.",
            "diagnostic_only_boundary": "No tracker replay; detection-level diagnostic only.",
        },
        {
            "rule_id": "WGV12_ASSOC_R006",
            "rule_name": "class_and_slot_are_secondary",
            "condition": "Class/x_bin changes reduce score but do not automatically block if overlap and local best-match evidence are strong.",
            "decision_effect": "Corrects detector class noise and nearby lane-slot jitter while preserving review_required.",
            "rationale": "Detector class labels can switch between car/truck on partial views; motion/overlap evidence should be considered first.",
            "diagnostic_only_boundary": "Does not promote to final identity truth.",
        },
    ]


def build_report(rows: list[dict[str, str]], out_path: Path, rules_path: Path) -> str:
    counts = Counter(row["tracking_style_decision"] for row in rows)
    lines = [
        "# OTY2 YOLO26l WGV1.2 tracking-style MRQ association adjudication",
        "",
        "Date: 2026-07-08",
        "",
        "## 结论",
        "",
        "上一版 gate-style triage 的问题是把 `competing_candidate_present` 过早解释成“不能合并”。这不符合常规跟踪关联逻辑。更合理的做法是：先把 from endpoint 与 to-frame 所有候选框做局部关联评分，再判断最高分候选到底是同一辆车上的重复/更优框，还是空间上分离的另一辆车。",
        "",
        "修正后，前后帧已经重叠、归一化位移小、视觉上落在同一车辆主体上的片段，不再因为同帧存在更高分候选而直接拆开。它们会保留为 `diagnostic same-vehicle candidate`，或标记为 `same_object_better_box_primary_selection_issue`。",
        "",
        f"- adjudication CSV: `{out_path.as_posix()}`",
        f"- rule CSV: `{rules_path.as_posix()}`",
        "",
        "Decision counts:",
        "",
    ]
    for decision, count in sorted(counts.items()):
        lines.append(f"- `{decision}`: {count}")
    lines.extend(
        [
            "",
            "## 为什么“有竞争框”不能直接当作禁止合并",
            "",
            "目标跟踪里的核心不是“有几辆车就拒绝”，而是构造局部候选集、计算匹配代价，然后做一对一关联。常见 MOT 思路会同时看：",
            "",
            "1. 前后框是否重叠，尤其是 `IoU` 和 intersection-over-min-area。",
            "2. 中心点位移是否相对于车辆尺寸合理，即 normalized motion。",
            "3. 框面积和长宽是否连续，避免把远处小车跳到近处大车。",
            "4. 类别、横向槽位、外观只作为辅助惩罚，因为车窗/车头/车尾局部检测会导致 class/x_bin 抖动。",
            "5. 同一帧内如果多个框压在同一辆真实车上，先做 duplicate / primary-box selection resolution，不能把它当成不同车辆证据。",
            "",
            "因此，你指出的情况是成立的：如果大断点两端的光学框仍然有强重叠，且都落在同一辆车上，那么它应该至少保留为诊断同车候选。上一版不能合并的原因不是物理逻辑不支持，而是机制把 `rank != 1` 简化成了 `competing_candidate_better`，没有判断那个更高分候选是不是同一车的重复框。",
            "",
            "## MRQ Results",
            "",
            "| MRQ | scene | endpoint frames | IoU | IoMin | norm_dist | rank | same-frame best relation | decision | rule |",
            "|---|---|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in rows:
        frames = f"{row['from_endpoint_frame']}->{row['to_endpoint_frame']}"
        lines.append(
            "| {review_item_id} | {scene_id} | {frames} | {endpoint_iou} | {endpoint_intersection_over_min_area} | {endpoint_center_distance_norm} | {to_target_rank_among_to_frame_candidates} | {same_frame_to_best_same_object_flag} | {tracking_style_decision} | {mechanism_rule} |".format(
                **row,
                frames=frames,
            )
        )
    lines.extend(
        [
            "",
            "## 关键样例解释",
            "",
            "- `MRQ002 / GM_RM011 10->13`: 前后 endpoint IoU=0.853、IoMin=0.979、normalized distance=0.040。frame 13 的更高分候选与 proposed to-target 是同一辆白色 SUV 上的重叠框，所以这是 `same_object_better_box_primary_selection_issue`，不是不同车竞争。",
            "- `MRQ010 / GM_RM017 158->164`: selected to-target 是白车上的窄框，frame 164 的更高分 left candidate 仍压在同一辆白车上；黑车和右侧 truck 是真实多车背景，但并不是这条 from->to 的最佳同车证据。因此这里也不应因为多车存在而直接拆开，应先解决同车主框选择。",
            "- `MRQ004 / GM_RM011 25->31`: frame 25 是右侧白车车头局部，frame 31 selected 是左侧 Maxus 车头，IoU=0、IoMin=0、normalized distance=1.108，并且横向槽位跳变。这里保留 `keep_separate_competing_candidate_better` 是合理的。",
            "- `MRQ009 / GM_RM017 144->145`: truck 前后框稳定重叠，左侧黑车只是背景竞争对象；这里应保留 truck 的同车诊断候选，不应因为场景中同时有 car 就混淆。",
            "",
            "## 机制修正",
            "",
            "修正后的机制不是 `competitor exists -> block`，而是：",
            "",
            "1. 在下一帧或短断点后建立局部 candidate set。",
            "2. 用 overlap、IoMin、normalized motion、scale continuity、class/x_bin penalty 对所有候选评分。",
            "3. 先判断 proposed to-target 与 best candidate 是否是同一真实车上的重复框或更优框。",
            "4. 如果是同车重复框，记录 primary-box selection issue，不拆 identity。",
            "5. 如果 best candidate 空间上分离，且比 proposed to-target 更符合 from endpoint，再保留 keep-separate / identity-switch review。",
            "6. 即便保留为同车候选，也仍然是 diagnostic-only，不是自动合并成 final identity。",
            "",
            "## 为什么会出现“大断点但可合并候选”",
            "",
            "当前 WGV1.2 的断点主要来自 detector primary selection 和 fragment construction，而不是车辆真实消失。只要断点两端的 endpoint 框有强 overlap/IoMin，中心位移相对车辆尺寸合理，并且视觉上仍覆盖同一车身主体，就应该进入同车候选。大断点只意味着需要更强证据和人工/诊断复核，不等于必须禁止连接。",
            "",
            "## Boundary",
            "",
            "- `auto_merge_allowed=no` for every row.",
            "- `sar_ready=no / blocked` for every row.",
            "- No final boxes, no GT boxes, no final/revised annotation.",
            "- No tracker replay and no SAR.",
        ]
    )
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> None:
    queue = read_csv(args.queue)
    bank = read_csv(args.bank)
    rows_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in bank:
        rows_by_scene_frame.setdefault((row["scene_id"], as_int(row["frame_id"])), []).append(row)
    rows = [adjudicate_item(item, rows_by_scene_frame) for item in queue]
    rules = rules_rows()
    write_csv(args.output, rows, FIELDS)
    write_csv(args.rules, rules, RULE_FIELDS)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(rows, args.output, args.rules), encoding="utf-8")
    print(f"wrote {args.output} rows={len(rows)}")
    print(f"wrote {args.rules} rows={len(rules)}")
    print(f"wrote {args.report}")
    print("decision counts:", dict(Counter(row["tracking_style_decision"] for row in rows)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    build(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
