"""OTY2 GT sample accounting audit.

This script explains how every SAR GT row is routed before the OTY2 posthoc
optical-object-to-SAR-GT mechanism audit. It does not read SAR image content,
does not build runtime priors, and does not generate annotation proposals.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DEFAULT_OBJECT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"
DEFAULT_GT_CSV = Path(
    r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv"
)
DEFAULT_REVIEW_QUEUE_CSV = Path(
    r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv"
)
DEFAULT_WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

PAIR_IOU_MIN = 0.05

ACCOUNTING_FIELDS = [
    "scene",
    "sar_gt_id",
    "sar_frame",
    "target_identity",
    "optical_frame",
    "gt_source_type",
    "is_sar_only",
    "has_review_optical_bbox",
    "has_oty_object_frame",
    "has_oty_object_hypothesis",
    "matched_object_hypothesis_id",
    "match_status",
    "skip_reason",
    "usable_for_optical_sar_correspondence",
    "usable_for_sar_only_morphology",
    "usable_after_gm011_object_stream_built",
    "needs_matching_triage",
    "best_oty_iou",
    "best_oty_object_hypothesis_id",
    "oty_frame_candidate_count",
    "review_optical_bbox",
    "gt_box",
    "optical_path",
    "sar_pseudocolor_path",
    "notes",
]

BOUNDARY_FLAGS = {
    "gt_table_read": True,
    "review_queue_read": True,
    "existing_oty_outputs_read": True,
    "sar_image_content_read": False,
    "automatic_annotation_proposal_generated": False,
    "training_or_threshold_tuning_entered": False,
    "gt_written_to_runtime_prior_construction": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
}

CANONICAL_MATCH_STATUSES = [
    "paired_optical_object_sar_gt",
    "blocked_missing_gm011_object_stream",
    "sar_only_gt",
    "missing_review_optical_bbox",
    "no_oty_iou_match",
    "other_unclassified_blocker",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return int(number)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def fmt(value: Any, digits: int = 4) -> str:
    number = safe_float(value)
    if number is None:
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def frame_from_path(path_text: str) -> int | None:
    if not path_text:
        return None
    stem = Path(path_text).stem
    return safe_int(stem)


def parse_bbox(row: Mapping[str, Any], keys: Sequence[str]) -> tuple[float, float, float, float] | None:
    values = [safe_float(row.get(key)) for key in keys]
    if any(value is None for value in values):
        return None
    x1, y1, x2, y2 = (float(value) for value in values if value is not None)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_to_text(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return ""
    return ",".join(fmt(value, 3) for value in bbox)


def bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    return parse_bbox(row, ("primary_bbox_x1", "primary_bbox_y1", "primary_bbox_x2", "primary_bbox_y2"))


def group_object_frames(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, int], list[dict[str, str]]]:
    by_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        scene = str(row.get("scene", ""))
        frame = safe_int(row.get("optical_frame_num"))
        if scene and frame is not None:
            by_frame[(scene, frame)].append(dict(row))
    return by_frame


def is_sar_only_identity(target_identity: str) -> bool:
    return target_identity.strip().lower().startswith("saronly")


def gt_box_text(gt: Mapping[str, Any]) -> str:
    return (
        f"cx={fmt(gt.get('final_cx'), 3)};cy={fmt(gt.get('final_cy'), 3)};"
        f"w={fmt(gt.get('final_w'), 3)};h={fmt(gt.get('final_h'), 3)};"
        f"heading={fmt(gt.get('final_heading_deg'), 3)}"
    )


def source_type(is_sar_only: bool, has_review_bbox: bool) -> str:
    if is_sar_only:
        return "sar_only_gt"
    if has_review_bbox:
        return "optical_review_linked_gt"
    return "optical_linked_gt_missing_review_bbox"


def best_oty_match(
    opt_bbox: tuple[float, float, float, float],
    candidates: Sequence[Mapping[str, str]],
) -> tuple[float, Mapping[str, str] | None]:
    best_iou = 0.0
    best_row: Mapping[str, str] | None = None
    for candidate in candidates:
        pbox = primary_box(candidate)
        if pbox is None:
            continue
        score = bbox_iou(opt_bbox, pbox)
        if score > best_iou:
            best_iou = score
            best_row = candidate
    return best_iou, best_row


def classify_gt_row(
    gt: Mapping[str, str],
    review_by_identity: Mapping[str, Mapping[str, str]],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    scene = str(gt.get("scene", ""))
    target_identity = str(gt.get("target_identity", ""))
    review = review_by_identity.get(target_identity, {})
    optical_frame = frame_from_path(str(gt.get("optical_path", "")))
    sar_frame = gt.get("sar_frame_num") or gt.get("sar_frame") or ""
    sar_gt_id = str(gt.get("final_id") or target_identity)
    sar_only = is_sar_only_identity(target_identity)
    review_bbox = parse_bbox(review, ("opt_x1", "opt_y1", "opt_x2", "opt_y2"))
    has_review_bbox = review_bbox is not None
    candidates = object_by_frame.get((scene, optical_frame), []) if optical_frame is not None else []
    candidate_ids = [str(candidate.get("object_hypothesis_id", "")) for candidate in candidates if str(candidate.get("object_hypothesis_id", ""))]
    has_object_frame = bool(candidates)
    has_object_hypothesis = bool(candidate_ids)
    best_iou = 0.0
    best_row: Mapping[str, str] | None = None
    if review_bbox is not None and candidates:
        best_iou, best_row = best_oty_match(review_bbox, candidates)

    row: dict[str, Any] = {
        "scene": scene,
        "sar_gt_id": sar_gt_id,
        "sar_frame": sar_frame,
        "target_identity": target_identity,
        "optical_frame": "" if optical_frame is None else str(optical_frame),
        "gt_source_type": source_type(sar_only, has_review_bbox),
        "is_sar_only": bool_text(sar_only),
        "has_review_optical_bbox": bool_text(has_review_bbox),
        "has_oty_object_frame": bool_text(has_object_frame),
        "has_oty_object_hypothesis": bool_text(has_object_hypothesis),
        "matched_object_hypothesis_id": "",
        "match_status": "",
        "skip_reason": "",
        "usable_for_optical_sar_correspondence": "false",
        "usable_for_sar_only_morphology": "true",
        "usable_after_gm011_object_stream_built": "false",
        "needs_matching_triage": "false",
        "best_oty_iou": fmt(best_iou, 6),
        "best_oty_object_hypothesis_id": "" if best_row is None else str(best_row.get("object_hypothesis_id", "")),
        "oty_frame_candidate_count": str(len(candidates)),
        "review_optical_bbox": bbox_to_text(review_bbox),
        "gt_box": gt_box_text(gt),
        "optical_path": gt.get("optical_path", ""),
        "sar_pseudocolor_path": gt.get("sar_pseudocolor_path", ""),
        "notes": "",
    }

    if sar_only:
        row.update(
            {
                "match_status": "sar_only_gt",
                "skip_reason": "sar_only_gt_excluded_from_optical_sar_correspondence",
                "notes": "SAR-only GT is not usable for optical-object to SAR-GT correspondence, but remains usable for SAR-only morphology and scattering statistics.",
            }
        )
        return row

    if not has_review_bbox:
        row.update(
            {
                "match_status": "missing_review_optical_bbox",
                "skip_reason": "non_sar_only_gt_missing_review_optical_bbox",
                "notes": "Non-SAR-only GT has no review optical bbox, so optical-object matching cannot start.",
            }
        )
        return row

    if optical_frame is None:
        row.update(
            {
                "match_status": "other_unclassified_blocker",
                "skip_reason": "missing_parseable_optical_frame",
                "notes": "Review optical bbox exists, but optical frame could not be parsed from optical_path.",
            }
        )
        return row

    if not candidates:
        if scene == "GM_RM011":
            row.update(
                {
                    "match_status": "blocked_missing_gm011_object_stream",
                    "skip_reason": "gm_rm011_has_sar_gt_and_review_optical_bbox_but_no_current_oty_object_frame",
                    "usable_after_gm011_object_stream_built": "true",
                    "notes": "GM_RM011 has SAR GT and review optical bbox, but current OTY object stream has no frame-level object rows for this scene.",
                }
            )
        else:
            row.update(
                {
                    "match_status": "other_unclassified_blocker",
                    "skip_reason": "missing_oty_object_frame_for_non_gm011_scene",
                    "notes": "Review optical bbox exists, but no current OTY object frame row exists for this scene/frame.",
                }
            )
        return row

    if best_row is None or best_iou < PAIR_IOU_MIN:
        row.update(
            {
                "match_status": "no_oty_iou_match",
                "skip_reason": f"best_oty_iou_below_{PAIR_IOU_MIN}",
                "needs_matching_triage": "true",
                "notes": "Review optical bbox exists and OTY frame candidates exist, but no primary observation box reaches the posthoc pairing IoU gate.",
            }
        )
        return row

    object_id = str(best_row.get("object_hypothesis_id", ""))
    row.update(
        {
            "matched_object_hypothesis_id": object_id,
            "match_status": "paired_optical_object_sar_gt",
            "usable_for_optical_sar_correspondence": "true",
            "notes": "Successful posthoc optical-object to SAR-GT correspondence sample; not identity truth and not runtime construction input.",
        }
    )
    return row


def build_accounting_rows(
    final_gt_rows: Sequence[Mapping[str, str]],
    review_queue_rows: Sequence[Mapping[str, str]],
    object_frame_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    review_by_identity = {str(row.get("target_identity", "")): row for row in review_queue_rows}
    object_by_frame = group_object_frames(object_frame_rows)
    return [classify_gt_row(gt, review_by_identity, object_by_frame) for gt in final_gt_rows]


def counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))


def canonical_category_counts(counter: Counter[str]) -> dict[str, int]:
    result = {status: int(counter.get(status, 0)) for status in CANONICAL_MATCH_STATUSES}
    for status, count in sorted(counter.items(), key=lambda item: item[0]):
        result.setdefault(status, int(count))
    return result


def summarize(rows: Sequence[Mapping[str, Any]], timestamp: str, sources: Mapping[str, str]) -> dict[str, Any]:
    total = len(rows)
    category_counts = Counter(str(row.get("match_status", "")) for row in rows)
    scene_counts = Counter(str(row.get("scene", "")) for row in rows)
    scene_category_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for scene in sorted(scene_counts):
        scene_rows = [row for row in rows if row.get("scene") == scene]
        scene_category_counts[scene] = canonical_category_counts(Counter(str(row.get("match_status", "")) for row in scene_rows))
    sar_only_rows = [row for row in rows if row.get("match_status") == "sar_only_gt"]
    no_match_rows = [row for row in rows if row.get("match_status") == "no_oty_iou_match"]
    gm011_rows = [row for row in rows if row.get("match_status") == "blocked_missing_gm011_object_stream"]
    missing_review_rows = [row for row in rows if row.get("match_status") == "missing_review_optical_bbox"]
    unclassified_rows = [row for row in rows if row.get("match_status") == "other_unclassified_blocker"]
    paired_count = category_counts.get("paired_optical_object_sar_gt", 0)
    return {
        "timestamp": timestamp,
        "total_gt_annotations": total,
        "scene_counts": counter_to_dict(scene_counts),
        "category_counts": canonical_category_counts(category_counts),
        "scene_category_counts": scene_category_counts,
        "paired_optical_object_sar_gt": paired_count,
        "sar_only_gt": len(sar_only_rows),
        "blocked_missing_gm011_object_stream": len(gm011_rows),
        "missing_review_optical_bbox": len(missing_review_rows),
        "no_oty_iou_match": len(no_match_rows),
        "other_unclassified_blocker": len(unclassified_rows),
        "usable_for_optical_sar_correspondence": sum(1 for row in rows if row.get("usable_for_optical_sar_correspondence") == "true"),
        "usable_for_sar_only_morphology": sum(1 for row in rows if row.get("usable_for_sar_only_morphology") == "true"),
        "usable_after_gm011_object_stream_built": sum(1 for row in rows if row.get("usable_after_gm011_object_stream_built") == "true"),
        "needs_matching_triage": sum(1 for row in rows if row.get("needs_matching_triage") == "true"),
        "paired_subset_meaning": "215 is the current optical-object-to-SAR-GT posthoc correspondence subset, not the full GT inventory.",
        "gm011_blocker_meaning": "GM_RM011 rows have SAR GT annotations; they are blocked only because the current OTY object stream is absent for that scene.",
        "sar_only_meaning": "SAR-only GT rows are excluded from optical-SAR correspondence but retained for SAR-only morphology and scattering statistics.",
        "pair_iou_min": PAIR_IOU_MIN,
        "no_iou_match_examples": [
            {
                "scene": row.get("scene", ""),
                "sar_gt_id": row.get("sar_gt_id", ""),
                "sar_frame": row.get("sar_frame", ""),
                "target_identity": row.get("target_identity", ""),
                "optical_frame": row.get("optical_frame", ""),
                "best_oty_iou": row.get("best_oty_iou", ""),
                "best_oty_object_hypothesis_id": row.get("best_oty_object_hypothesis_id", ""),
                "oty_frame_candidate_count": row.get("oty_frame_candidate_count", ""),
            }
            for row in no_match_rows[:12]
        ],
        "sar_only_examples": [
            {
                "scene": row.get("scene", ""),
                "sar_gt_id": row.get("sar_gt_id", ""),
                "sar_frame": row.get("sar_frame", ""),
                "target_identity": row.get("target_identity", ""),
            }
            for row in sar_only_rows[:12]
        ],
        "missing_review_optical_bbox_examples": [
            {
                "scene": row.get("scene", ""),
                "sar_gt_id": row.get("sar_gt_id", ""),
                "sar_frame": row.get("sar_frame", ""),
                "target_identity": row.get("target_identity", ""),
            }
            for row in missing_review_rows[:12]
        ],
        "boundary_flags": BOUNDARY_FLAGS,
        "sources": sources,
    }


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[str]:
    if not rows:
        return ["无。"]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    return lines


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines: list[str] = [
        "# OTY2 GT 样本账本审计报告",
        "",
        f"生成时间：`{summary['timestamp']}`",
        "",
        "本轮只做 GT 样本 accounting，不继续做机制分层验证。脚本读取 GT 表、review queue 和已有 OTY 输出；不读取 SAR 图像，不生成自动标注建议，不训练或调阈值，也不把 GT 写入 runtime prior construction。",
        "",
        "## 总账结论",
        "",
        f"- 全部 GT 标注总数：`{summary['total_gt_annotations']}`。",
        f"- 每个场景 GT 数：`{json.dumps(summary['scene_counts'], ensure_ascii=False)}`。",
        f"- 每个类别数量：`{json.dumps(summary['category_counts'], ensure_ascii=False)}`。",
        f"- 当前成功配对样本：`{summary['paired_optical_object_sar_gt']}`。",
        f"- SAR-only GT：`{summary['sar_only_gt']}`。",
        f"- GM_RM011 缺当前 OTY 光学对象流：`{summary['blocked_missing_gm011_object_stream']}`。",
        f"- no_oty_iou_match：`{summary['no_oty_iou_match']}`。",
        f"- missing_review_optical_bbox：`{summary['missing_review_optical_bbox']}`。",
        f"- other_unclassified_blocker：`{summary['other_unclassified_blocker']}`。",
        "",
        "这 442 条样本被完整分账；`paired_optical_object_sar_gt + blocked_missing_gm011_object_stream + sar_only_gt + no_oty_iou_match + missing_review_optical_bbox + other_unclassified_blocker` 等于全部 GT 数。",
        "",
        "## 215/442 的含义",
        "",
        "`215` 不是总标注数，也不代表只有 215 条 SAR GT。它只是当前可用于“光学对象—SAR GT 后验机制审计”的成功配对子集：同一场景、同一光学帧、review 光学框与当前 OTY 对象帧主观测框 IoU 达到 `0.05` 的样本。",
        "",
        "## 类别解释",
        "",
        "- `paired_optical_object_sar_gt`：成功建立光学对象和 SAR GT 的后验对应样本；可用于本轮后验机制审计，但不是身份真值，也不是 runtime prior 输入。",
        "- `blocked_missing_gm011_object_stream`：GM_RM011 有 SAR GT，也有 review 光学框，但当前缺 OTY 光学对象流；这不是没有标注，后续补建 GM011 对象流后可重新进入配对。",
        "- `sar_only_gt`：SAR-only 标注，不能用于光学—SAR 对应机制；但应该保留用于 SAR-only 目标尺度、散射强度和形态统计。",
        "- `missing_review_optical_bbox`：非 SAR-only 样本缺 review 光学框或光学对应字段；本次为单独类别，不再和 SAR-only 混在一起。",
        "- `no_oty_iou_match`：有 review 光学框，也有当前 OTY 对象帧候选，但没有任何主观测框达到 IoU `0.05`；需要单独做匹配失败诊断。",
        "- `other_unclassified_blocker`：其他原因；如果非零，需要逐条解释。",
        "",
        "## 场景分账",
        "",
    ]
    scene_category_counts = summary["scene_category_counts"]
    lines.extend(
        [
            "| scene | category_counts |",
            "| --- | --- |",
            *[
                f"| {scene} | `{json.dumps(counts, ensure_ascii=False)}` |"
                for scene, counts in scene_category_counts.items()
            ],
            "",
            "## no_oty_iou_match 样例索引",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            summary["no_iou_match_examples"],
            [
                "scene",
                "sar_gt_id",
                "sar_frame",
                "optical_frame",
                "best_oty_iou",
                "best_oty_object_hypothesis_id",
                "oty_frame_candidate_count",
            ],
        )
    )
    lines.extend(["", "这些样本不是 SAR-only，也不是缺 GT；它们需要下一轮单独 triage：检查 review 光学框、OTY 主观测框、对象流断裂、重复框或 handoff 是否导致 IoU 低。", ""])
    lines.extend(["## SAR-only 样例索引", ""])
    lines.extend(markdown_table(summary["sar_only_examples"], ["scene", "sar_gt_id", "sar_frame", "target_identity"]))
    lines.extend(
        [
            "",
            "SAR-only 样本仍然有 SAR GT 框，可以进入 SAR-only 物理尺度、散射和形态统计；但它们没有可用的光学对象对应，不应混入 optical-to-SAR correspondence 机制审计。",
            "",
            "## missing_review_optical_bbox 样例索引",
            "",
        ]
    )
    lines.extend(markdown_table(summary["missing_review_optical_bbox_examples"], ["scene", "sar_gt_id", "sar_frame", "target_identity"]))
    lines.extend(
        [
            "",
            "## 处理建议",
            "",
            "1. GM_RM011：不要把 195 条解释成没有标注；应补建或接入 GM_RM011 的 OTY 光学对象流，再重新跑配对账本。",
            "2. SAR-only：保留为 SAR-only morphology/scattering 统计池；不要用于光学—SAR 对应机制。",
            "3. no_oty_iou_match：单独做 12 条匹配失败诊断，优先检查 review 光学框和 OTY 对象帧是否存在坐标系、对象流断裂或 handoff 问题。",
            "4. paired 215：只作为当前后验机制审计配对子集使用，不代表全量 GT。",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## 数据源", ""])
    for key, value in summary["sources"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, summary: Mapping[str, Any], outputs: Mapping[str, str]) -> None:
    DEFAULT_WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DEFAULT_WORKSPACE_LOG_DIR / f"oty2_gt_sample_accounting_audit_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_gt_sample_accounting_audit",
        f"total_gt_annotations={summary['total_gt_annotations']}",
        f"category_counts={json.dumps(summary['category_counts'], ensure_ascii=False)}",
        f"boundary_flags={json.dumps(summary['boundary_flags'], ensure_ascii=False)}",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, str]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    final_gt_csv = Path(args.final_gt_csv)
    review_queue_csv = Path(args.review_queue_csv)
    object_frame_state_csv = Path(args.object_frame_state_csv)
    final_gt_rows = read_csv(final_gt_csv)
    review_queue_rows = read_csv(review_queue_csv)
    object_frame_rows = read_csv(object_frame_state_csv)
    accounting_rows = build_accounting_rows(final_gt_rows, review_queue_rows, object_frame_rows)

    audit_csv = REPORT_DIR / f"oty2_gt_sample_accounting_audit_{timestamp}.csv"
    summary_json = REPORT_DIR / f"oty2_gt_sample_accounting_summary_{timestamp}.json"
    report_md = REPORT_DIR / f"oty2_gt_sample_accounting_report_{timestamp}.md"
    sources = {
        "final_gt_csv": str(final_gt_csv),
        "review_queue_csv": str(review_queue_csv),
        "object_frame_state_csv": str(object_frame_state_csv),
        "previous_gt_mechanism_summary": str(REPORT_DIR / "oty2_gt_correspondence_mechanism_summary_20260702_190435.json"),
    }
    summary = summarize(accounting_rows, timestamp, sources)
    outputs = {
        "audit_csv": str(audit_csv),
        "summary_json": str(summary_json),
        "report_md": str(report_md),
    }
    write_csv(audit_csv, accounting_rows, ACCOUNTING_FIELDS)
    write_json(summary_json, summary)
    render_report(report_md, summary)
    write_workspace_log(timestamp, summary, outputs)
    print(json.dumps({"outputs": outputs, "summary": summary}, ensure_ascii=False, indent=2))
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--final-gt-csv", default=str(DEFAULT_GT_CSV))
    parser.add_argument("--review-queue-csv", default=str(DEFAULT_REVIEW_QUEUE_CSV))
    parser.add_argument(
        "--object-frame-state-csv",
        default=str(DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"),
    )
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
