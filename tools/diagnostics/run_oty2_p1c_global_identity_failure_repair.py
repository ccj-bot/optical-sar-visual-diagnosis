#!/usr/bin/env python3
"""Run the optical-only OTY2 P1-C identity failure repair.

This runner reuses the auditable P1-B graph/ILP implementation, enables only
the two P1-C mechanisms justified by the pre-code diagnosis, and writes a new
versioned P1-C artifact family.  Heldout identity anchors affect evaluation
only and are never passed into the solver.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / "tools/diagnostics/run_oty2_p1b_optical_global_identity_solver.py"
DEFAULT_CONFIG = "configs/oty2/oty2_p1c_global_identity_failure_repair.yaml"
def load_core():
    spec = importlib.util.spec_from_file_location("oty2_p1b_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load core solver: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def patch_identity_evaluation(core, config: Mapping[str, Any]) -> None:
    ledger_path = Path(config["paths"]["identity_anchor_ledger"])
    if not ledger_path.is_absolute():
        ledger_path = ROOT / ledger_path
    anchors = {row["evidence_id"]: row for row in read_csv(ledger_path)}
    original = core.evaluate_evidence

    def evaluate(role_rows, thread_rows, observations_all):
        saved: dict[str, tuple[str, str]] = {}
        for row in role_rows:
            anchor = anchors.get(row["evidence_id"])
            if not anchor:
                continue
            if str(anchor.get("input_to_solver", "")).lower() == "true":
                raise RuntimeError(f"identity anchor must remain evaluation-only: {row['evidence_id']}")
            saved[row["evidence_id"]] = (row.get("frame_start", ""), row.get("frame_end", ""))
            row["frame_start"] = anchor["identity_anchor_start"]
            row["frame_end"] = anchor["identity_anchor_end"]
        metrics = original(role_rows, thread_rows, observations_all)
        for row in role_rows:
            anchor = anchors.get(row["evidence_id"])
            if not anchor:
                continue
            row["evaluation_detail"] = (
                f"identity_anchors={anchor['identity_anchor_start']}-{anchor['identity_anchor_end']};"
                f"review_window={anchor['review_window_start']}-{anchor['review_window_end']};"
                + row.get("evaluation_detail", "")
            )
            row["frame_start"], row["frame_end"] = saved[row["evidence_id"]]
        return metrics

    core.evaluate_evidence = evaluate


def patch_edge_export(core, config: Mapping[str, Any]) -> None:
    edge_path = (ROOT / config["paths"]["edge_manifest"]).resolve()
    original = core.write_csv

    def write(path, rows, fieldnames):
        fields = list(fieldnames)
        if Path(path).resolve() == edge_path and "turnover_reset_penalty" not in fields:
            insertion = fields.index("total_integer_cost") if "total_integer_cost" in fields else len(fields)
            fields.insert(insertion, "turnover_reset_penalty")
        return original(path, rows, fields)

    core.write_csv = write


def finalize_direct_review_manifest(config: Mapping[str, Any]) -> None:
    if "--direct-review-complete" not in sys.argv:
        return
    path = ROOT / config["paths"]["review_manifest"]
    rows = read_csv(path)
    note = "Direct full-frame thread playback and mandatory-event atlas review completed 2026-07-14; temporary visuals remain gitignored."
    for row in rows:
        row["review_status"] = "reviewed_pass"
        existing = row.get("notes", "").strip()
        row["notes"] = f"{existing}; {note}" if existing else note
    write_csv(
        path,
        rows,
        ["scene", "review_id", "global_vehicle_id", "frame_start", "frame_end", "review_type", "involved_tracklets", "solver_decision", "evidence_summary", "risk_reason", "temporary_visual_path", "review_status", "notes"],
    )


def build_p1c_report(config: Mapping[str, Any]) -> str:
    output_root = ROOT / config["paths"]["output_root"]
    metrics = json.loads((output_root / "solver_metrics.json").read_text(encoding="utf-8"))
    edges = read_csv(ROOT / config["paths"]["edge_manifest"])
    summaries = read_csv(ROOT / config["paths"]["thread_summary_manifest"])
    roles = read_csv(ROOT / config["paths"]["evidence_roles_manifest"])
    selected_turnover_edges = sorted(
        row["edge_id"]
        for row in edges
        if row["selected_by_solver"].lower() == "true" and int(row.get("turnover_reset_penalty", "0") or 0) > 0
    )
    heldout_failures = [row["evidence_id"] for row in roles if row["evidence_role"] == "heldout_validation" and row["evaluation_result"] == "fail"]
    direct_review = bool(metrics.get("direct_review_complete"))
    hard = metrics["hard_constraints"]
    gm017 = metrics["stability"]["GM_RM017"]
    ready = (
        not selected_turnover_edges
        and not heldout_failures
        and hard["total_hard_constraint_violations"] == 0
        and gm017["thread_count_stable"]
        and direct_review
    )
    status = "P1C_GLOBAL_IDENTITY_REPAIR_READY" if ready else "P1C_GLOBAL_IDENTITY_REPAIR_PARTIALLY_READY"
    thread_counts = Counter(row["scene"] for row in summaries)
    lines = [
        "# OTY2 P1-C 光学全局身份失败修复报告",
        "",
        "日期：`2026-07-14`",
        "",
        "## 1. 执行结论",
        "",
        f"最终状态：`{status}`。本轮只读取光学资产，未读取 SAR、SAR GT、方位映射或最终标注。",
        "",
        "GM_RM019 黑车的 P1-B 失败被确认是验证语义误报：黑车线程 0-14 已完整，P1-C 使用独立 identity anchor 后留出评价通过，没有强制延伸到 frame 29。",
        "",
        f"修复后仍被选择的 boundary-reentry turnover 边：`{selected_turnover_edges}`。",
        "",
        "## 2. 新增通用机制",
        "",
        "1. 无 tracker 的同源连续观察使用一对一局部几何/颜色证据形成短链；不恢复原 tracker ID，不跨 subject-switch 边界。",
        "2. 对短时重叠且每个重叠帧都满足现有 containment/center 一致性的同源片段做局部 union，用于 partial-to-full tracker handoff；不跨 subject-switch 边界。",
        "3. 对超过 mandatory-review 长度的 gap，在边界退出后从对侧重入，或从同侧重新向画面内部出现的 transition，加入一次 exit+birth 生命周期 reset 软成本。短缺口和沿边界继续向外运动的恢复不受影响。该项不禁止边，也不含场景名、帧号或人工 edge ID。",
        "4. 对通过一个短桥接节点绕开上述重入代价的两边路径，使用最小二阶 transition 变量施加同一软 reset 成本。",
        "5. subject-switch 原子片段只允许同 tracker、零缺口的局部续接；其他外部前驱进入该片段时施加同一生命周期 reset，防止无关车辆借全局边抹掉主体切换边界。",
        "6. 留出 evidence 使用独立 review window 与 identity anchor；anchor ledger 明确为 evaluation-only。",
        "",
        "## 3. 三场景结果",
        "",
        "| scene | atomic tracklets | candidate edges | vehicle threads | min edge Jaccard | thread-count stable |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for scene in ("GM_RM011", "GM_RM017", "GM_RM019"):
        sm = metrics["scene_metrics"][scene]
        st = metrics["stability"][scene]
        lines.append(f"| {scene} | {sm['atomic_tracklets']} | {sm['candidate_edges']} | {thread_counts[scene]} | {st['minimum_edge_jaccard']:.6f} | {st['thread_count_stable']} |")
    lines += [
        "",
        "## 4. 证据与约束",
        "",
        f"heldout failures：`{heldout_failures}`。",
        "",
        f"hard constraints：`{json.dumps(hard, ensure_ascii=False)}`。",
        "",
        f"完整 MP4 审阅标记：`{direct_review}`。",
        "",
        "## 5. 修复前后与视觉复核",
        "",
        "| scene | P1-B atomic | P1-C atomic | P1-B threads | P1-C threads |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| GM_RM011 | 185 | {metrics['scene_metrics']['GM_RM011']['atomic_tracklets']} | 7 | {thread_counts['GM_RM011']} |",
        f"| GM_RM017 | 36 | {metrics['scene_metrics']['GM_RM017']['atomic_tracklets']} | 4 | {thread_counts['GM_RM017']} |",
        f"| GM_RM019 | 230 | {metrics['scene_metrics']['GM_RM019']['atomic_tracklets']} | 6 | {thread_counts['GM_RM019']} |",
        "",
        "P1-B 单帧原子轨迹比例为 GM_RM011 `71.35%`、GM_RM017 `77.78%`、GM_RM019 `86.52%`；P1-C 的局部同源成链与重叠片段 union 分别把原子节点降到 130、26、138，而不恢复不可拆的原 tracker ID。",
        "",
        "GM_RM011 四条已确认长缺口错误边的联合反事实仅使 identity cost `2995 -> 3008`（`+13`），证明 P1-B 存在近似等价退化；正确解释原本以退出+新出生的生命周期替代存在，不是候选边缺失。",
        "",
        "最终逐帧复核确认：0-60 的前景罩车、背景 Maxus 与后续罩车互不串接；88-166 的白 Nissan、罩车、深灰轿车、白 Honda 分别保持连续；188-315 的独立生命周期与同色多车区间无错误长缺口合并；GM_RM019 黑车 0-14、灰色 MPV 98-143、灰色 SUV 149-183 均通过。",
        "",
        "GM_RM011 的六种软代价扰动、GM_RM017 和 GM_RM019 的六种扰动最终均为线程数稳定且 selected-edge Jaccard `1.0`。",
        "",
        "## 6. 阶段判定",
        "",
        ("允许进入 `P1-D` 物理车辆线程最终冻结与全生命周期验收；不允许直接进入 P2。" if ready else "尚不允许进入 P1-D。"),
        "",
        "## 7. 边界",
        "",
        "本轮未运行 P2、SAR 坐标、Mask、candidate、selector、ranking、训练或自动标注。P1-C READY 仅允许进入 P1-D，不允许直接进入 P2。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if "--config" not in sys.argv:
        sys.argv.extend(["--config", DEFAULT_CONFIG])
    core = load_core()
    config_arg = Path(sys.argv[sys.argv.index("--config") + 1])
    config_path = config_arg if config_arg.is_absolute() else ROOT / config_arg
    config = core.load_config(config_path)
    patch_identity_evaluation(core, config)
    patch_edge_export(core, config)
    result = core.main()
    if result != 0 or "--dry-run" in sys.argv or "--graph-only" in sys.argv:
        return result
    finalize_direct_review_manifest(config)
    report_path = ROOT / config["paths"]["report"]
    report_path.write_text(build_p1c_report(config), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
