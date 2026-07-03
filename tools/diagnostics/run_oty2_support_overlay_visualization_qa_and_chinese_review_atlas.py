"""OTY2 support overlay visualization QA and Chinese review atlas.

This diagnostic fixes the support-overlay review atlas by rendering SAR crops,
GT boxes, reconstructed support boundaries, and energy hints in one crop-local
coordinate system. It is visualization QA only: no annotation proposal, final
box, selector/ranking, training, threshold tuning, best weight, or identity
truth is produced.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Polygon
from PIL import Image

from run_oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage import (
    STATE_MODE,
    crop_box_for,
    gt_pixel_table,
    read_image_gray,
    support_available,
    support_boundary_points,
    support_case_id,
)
from run_oty2_range_narrowing_peak_competition_audit import (
    DOCS_DIR,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    fmt,
    latest_path,
    read_csv,
    write_csv,
    write_json,
)
from run_oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion import (
    box_available,
    gt_box_from_accounting,
    gt_box_from_correspondence,
    rotated_corners,
    sanitize,
)


VISUAL_DIR = REPORT_DIR / "visual_exemplars"
PLAN_DOC = DOCS_DIR / "oty2_support_overlay_visualization_qa_and_chinese_review_atlas_plan.md"
OLD_ATLAS_GLOB = "oty2_gt_support_energy_overlay_atlas_*.html"
OLD_PANEL_WIDTH_CAP = 520

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "visualization_coordinate_qa_entered": True,
    "chinese_review_atlas_generated": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "final_candidate_box_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "best_weight_selected": False,
    "identity_truth_claimed": False,
    "complete_object_80_85_hypothesis_written_as_runtime_rule": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
    "matlab_zip_or_any_zip_committed": False,
}

GEOMETRY_DEBUG_FIELDS = [
    "panel_index",
    "case_id",
    "scene",
    "sar_frame",
    "image_path",
    "image_width",
    "image_height",
    "crop_x0",
    "crop_y0",
    "crop_x1",
    "crop_y1",
    "crop_width",
    "crop_height",
    "render_width",
    "render_height",
    "scale_x",
    "scale_y",
    "gt_original_coords",
    "gt_crop_local_coords",
    "gt_render_coords",
    "support_original_coords",
    "support_crop_local_coords",
    "support_render_coords",
    "coordinate_system_note",
    "y_axis_origin",
    "overlay_method",
    "qa_status",
    "qa_warning_reason",
    "panel_path",
]

COORDINATE_QA_FIELDS = [
    "panel_index",
    "case_id",
    "scene",
    "sar_frame",
    "old_atlas_path",
    "old_panel_path",
    "old_crop_width",
    "old_crop_height",
    "old_resize_ratio",
    "previous_overlay_coordinate_risk",
    "previous_overlay_risk_reason",
    "new_panel_path",
    "new_overlay_method",
    "new_scale_x",
    "new_scale_y",
    "qa_status",
    "qa_warning_reason",
    "support_render_method",
    "support_judgment_allowed",
    "gt_judgment_allowed",
]

CHINESE_CARD_FIELDS = [
    "panel_index",
    "case_id",
    "中文标题",
    "样例类型",
    "为什么选择这张",
    "这张图要看什么",
    "人工需要回答的问题",
    "可以记录的结论",
    "不能记录的结论",
    "主要混淆因素",
    "support 是否可判断",
    "GT 是否可判断",
    "是否需要前后帧",
    "建议人工标签选项",
    "panel_path",
]

TAG_OPTIONS = [
    "SAR车体结构明显",
    "SAR车体结构可见但断续",
    "SAR车体结构弱",
    "GT框可能偏/边缘影响",
    "support覆盖主结构",
    "support未覆盖主结构",
    "support过宽",
    "support疑似错位不可判断",
    "邻车/电动车/栏杆干扰",
    "需要时序判断",
    "只能作为morphology参考",
    "不能用于optical-SAR关联",
]

CARD_GUIDANCE: dict[str, dict[str, str]] = {
    "possible compact vehicle structure": {
        "title": "完整光学高置信样例：紧凑车体结构",
        "type": "完整/高置信 paired support review",
        "why": "用于检查完整光学车辆对应的 optical-derived support 是否覆盖 SAR GT 内主要车体散射结构。",
        "look": "重点看 GT 框内近侧强散射条带、角点高能区、远侧弱回波是否落在 reconstructed support 内。",
        "question": "support 是否覆盖主要车体结构，而不仅是覆盖 GT 框的一部分面积？",
        "can": "可记录 GT 内 SAR morphology 是否清楚、support 是否覆盖主结构、是否存在过宽或峰值竞争。",
        "cannot": "不能记录为最终标注成功、identity truth 或 selector/ranking 结论。",
        "confounder": "近邻车辆、过宽 support、GT 边缘、局部高能背景。",
        "needs_temporal": "否，若主结构有疑问可补看前后帧。",
    },
    "possible multi-peak vehicle structure": {
        "title": "断续多峰样例：车体片段是否仍可组成结构",
        "type": "paired support review / discontinuous morphology",
        "why": "用于检查多峰、断续条带是否仍形成 SAR 车体结构，以及 support 是否覆盖这些片段。",
        "look": "重点看多个高能点是否沿车体边缘排列，是否被 support 覆盖，还是来自邻近散射。",
        "question": "断续多峰能否作为 morphology 参考，还是需要标为邻近干扰？",
        "can": "可记录断续车体结构、角点高能、support 覆盖或漏覆盖。",
        "cannot": "不能把多峰直接写成车辆身份确认，也不能输出最终框。",
        "confounder": "邻车、货车或道路结构散射、GT 框边缘。",
        "needs_temporal": "可选，若多峰是否同一车体不清楚则需要。",
    },
    "possible range-spread vehicle structure": {
        "title": "径向扩散样例：扩散中是否保留车体 core",
        "type": "paired support review / range-spread morphology",
        "why": "用于检查 range spread 不应被直接等同于 diffuse/reject，仍需看 GT 内是否有车体核心结构。",
        "look": "重点看 GT 框上下侧或侧边是否有连续/断续车体条带，support 是否覆盖这些高能区域。",
        "question": "扩散是车辆结构的一部分、运动/环境影响，还是纯背景散射？",
        "can": "可记录 range-spread with vehicle body core、support 覆盖情况、是否需要时序。",
        "cannot": "不能把 motion/drift hypothesis 写成已证实物理结论。",
        "confounder": "路边栏杆、道路边缘、运动模糊假设、display contrast。",
        "needs_temporal": "是，建议结合前后帧看高能区是否随目标移动。",
    },
    "possible azimuth-spread vehicle structure": {
        "title": "方位扩散样例：强侧边条带是否为车体结构",
        "type": "paired support review / azimuth-spread morphology",
        "why": "用于检查方位扩散或 support overlap 下，GT 内强侧边条带是否仍是车体 morphology anchor。",
        "look": "重点看近侧连续强条带、远侧弱回波、support 边界是否覆盖主条带。",
        "question": "support 覆盖的是目标车体主结构，还是覆盖了过宽的方位区域？",
        "can": "可记录 near-side ridge、support 是否过宽、coverage hypothesis 是否可视化成立。",
        "cannot": "不能记录为最终 optical-SAR 关联强度或身份真值。",
        "confounder": "方位映射裕量、support 过宽、邻近车辆峰值竞争。",
        "needs_temporal": "可选。",
    },
    "possible stable vehicle tube": {
        "title": "时序稳定样例：高能区是否随车体迁移",
        "type": "temporal morphology reference / paired support review",
        "why": "用于检查单帧 support 之外，前后帧是否显示同一类车体高能结构迁移。",
        "look": "重点看当前帧 GT 内条带，以及前后帧小图中高能区是否呈合理时序迁移。",
        "question": "这是车辆 tube 的结构迁移，还是背景稳定峰值？",
        "can": "可记录需要 temporal morphology tube 或时序补偿。",
        "cannot": "不能把单帧覆盖不足直接判为失败，也不能输出最终轨迹或框。",
        "confounder": "背景稳定亮点、wrong-frame support、邻近车辆。",
        "needs_temporal": "是。",
    },
    "diffuse / reject exemplar": {
        "title": "弱/扩散样例：不要用 diffuse 标签直接否定 GT 内结构",
        "type": "paired morphology review / weak structure",
        "why": "用于检查原先可能被粗略拒绝的样例中是否仍有可解释 SAR 车体结构。",
        "look": "重点看 GT 内两侧断续条带、近雷达端部高能、support 是否覆盖这些弱结构。",
        "question": "弱结构是否仍可作为 morphology 参考，还是确实不可判读？",
        "can": "可记录结构弱、断续、需要时序或 GT 边缘影响。",
        "cannot": "不能把 weak/diffuse 直接等同于 no vehicle。",
        "confounder": "低对比、边缘截断、背景散射、时序迁移。",
        "needs_temporal": "是。",
    },
    "background-stable wrong-frame exemplar": {
        "title": "wrong-frame 风险样例：背景稳定与车辆时序迁移区分",
        "type": "temporal QA / wrong-frame risk",
        "why": "用于检查高能结构是否可能来自 wrong-frame 或背景稳定散射。",
        "look": "重点看前后帧小图，判断高能结构是否跟随目标变化，还是停留在背景位置。",
        "question": "该结构支持车辆 morphology，还是应标为 wrong-frame/background-stable review？",
        "can": "可记录需要时序判断、背景稳定风险、morphology 仍可能保留。",
        "cannot": "不能用单帧支持区直接确认关联。",
        "confounder": "背景稳定峰值、错帧、道路/栏杆结构。",
        "needs_temporal": "是。",
    },
    "neighboring-object wrong-object exemplar": {
        "title": "邻近目标混淆样例：车体强但 association 需复核",
        "type": "paired support review / neighboring-object confounder",
        "why": "用于检查 support 内是否同时存在目标车和邻近车辆/电动车环境散射。",
        "look": "重点看 GT 内车体结构是否自洽，support 是否也覆盖邻近结构。",
        "question": "这是 SAR morphology failure，还是 association review due to nearby object？",
        "can": "可记录 SAR structure strong but association review needed。",
        "cannot": "不能因为邻近混淆就否定 GT 内 morphology，也不能确认身份。",
        "confounder": "电动车、邻车、栏杆、过宽 support。",
        "needs_temporal": "可选。",
    },
    "support-overlap azimuth-shift exemplar": {
        "title": "support overlap / 方位偏移样例：先确认 overlay 可靠",
        "type": "paired support coverage QA",
        "why": "旧 atlas 中该类最容易被 support 画法误导，本轮用 crop-local QA 重新渲染。",
        "look": "重点看 GT/support 边界是否对齐图像，support 是否覆盖 GT 内强条带。",
        "question": "support coverage 是否能被人工判断，还是仍需标为不可判断？",
        "can": "可记录 support 覆盖、过宽、漏覆盖或需要复核。",
        "cannot": "不能沿用旧 atlas 的 support coverage visual judgment。",
        "confounder": "方位映射裕量、support 过宽、旧图错位风险。",
        "needs_temporal": "可选。",
    },
    "statistics say vehicle-like but visual review likely needed": {
        "title": "统计像车但需人工复核：结构与关联分层",
        "type": "paired visual review / statistics cross-check",
        "why": "用于检查统计指标提示 vehicle-like 时，人工是否同意 SAR 车体结构可见。",
        "look": "重点看近侧强条带、远侧弱回波、前后帧高能区是否一致。",
        "question": "是否应记录为 morphology 可见但 association 仍弱？",
        "can": "可记录 SAR morphology clear / review needed / support overbroad。",
        "cannot": "不能把统计 vehicle-like 写成最终关联成功。",
        "confounder": "重复同一时序、过宽 support、峰值竞争。",
        "needs_temporal": "是。",
    },
    "case where GT is inside support but association should remain weak": {
        "title": "GT 在 support 内但 association 仍弱：覆盖不等于身份",
        "type": "paired support review / boundary reminder",
        "why": "用于强调 GT inside support 只能说明覆盖假设，不说明最终关联或身份。",
        "look": "重点看 GT 内结构是否清楚，以及 support 是否过宽到无法唯一关联。",
        "question": "coverage 与 morphology 是否成立，同时 association 是否仍应保持弱/复核？",
        "can": "可记录 GT morphology anchor、support coverage、association separate layer。",
        "cannot": "不能记录 identity truth、final localization 或 selector success。",
        "confounder": "过宽 support、同一时序多车、峰值竞争。",
        "needs_temporal": "可选。",
    },
    "SAR-only morphology reference exemplar": {
        "title": "SAR-only morphology reference：不可判断 paired support",
        "type": "SAR-only reference",
        "why": "仅作为 SAR morphology reference，没有 paired optical-derived support。",
        "look": "只看 GT 内 SAR 车体结构，例如弱端点、角点反射、边缘影响。",
        "question": "该 SAR GT 是否能作为弱 morphology reference？",
        "can": "可记录 SAR-side morphology note、GT 边缘/弱结构。",
        "cannot": "不能记录 optical-SAR support coverage 或关联结论。",
        "confounder": "边缘弱目标、GT 质量、低能量。",
        "needs_temporal": "可选。",
    },
    "GM_RM011 waiting object-stream reference exemplar": {
        "title": "GM_RM011 reference：等待 object stream，不是未标注",
        "type": "GM_RM011 reference-only",
        "why": "GM_RM011 当前缺少 OTY object stream，只能作为 SAR morphology reference。",
        "look": "只看 SAR 车体两侧强回波、近场截断和端部结构，不做 paired support 判断。",
        "question": "该 SAR morphology 是否可作为未来 GM_RM011 recovery 的参考？",
        "can": "可记录 near-field truncated morphology reference。",
        "cannot": "不能叫未标注，不能用于当前 optical-SAR correspondence coverage。",
        "confounder": "近场截断、object stream 缺失、边缘/弱端部。",
        "needs_temporal": "可选。",
    },
}


def chinese_font() -> FontProperties:
    for path in [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]:
        if path.exists():
            return FontProperties(fname=str(path))
    return FontProperties()


FONT = chinese_font()
plt.rcParams["axes.unicode_minus"] = False


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def coords_json(points: Sequence[tuple[float, float]]) -> str:
    return compact_json([[round(float(x), 2), round(float(y), 2)] for x, y in points])


def lines_json(lines: Sequence[Sequence[tuple[float, float]]]) -> str:
    return compact_json([[[round(float(x), 2), round(float(y), 2)] for x, y in line] for line in lines])


def to_crop_points(points: Sequence[tuple[float, float]], crop: tuple[int, int, int, int]) -> list[tuple[float, float]]:
    x0, y0, _, _ = crop
    return [(float(x) - x0, float(y) - y0) for x, y in points]


def to_crop_lines(lines: Sequence[Sequence[tuple[float, float]]], crop: tuple[int, int, int, int]) -> list[list[tuple[float, float]]]:
    return [to_crop_points(line, crop) for line in lines]


def inside_crop(points: Sequence[tuple[float, float]], crop_width: int, crop_height: int, tolerance: float = 1.0) -> bool:
    if not points:
        return True
    return all(
        -tolerance <= float(x) <= crop_width + tolerance and -tolerance <= float(y) <= crop_height + tolerance
        for x, y in points
    )


def all_line_points(lines: Sequence[Sequence[tuple[float, float]]]) -> list[tuple[float, float]]:
    return [point for line in lines for point in line]


def read_gray(path_text: str) -> np.ndarray | None:
    return read_image_gray(path_text)


def image_size(path_text: str) -> tuple[int, int] | None:
    path = Path(str(path_text or ""))
    if not path.exists():
        return None
    with Image.open(path) as image:
        return image.size


def support_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("mode_name") != STATE_MODE:
            continue
        result[support_case_id(row)] = row
    return result


def gt_accounting_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (str(row.get("scene", "")), str(row.get("sar_frame", "")), str(row.get("sar_gt_id", "")))
        result[key] = row
    return result


def corr_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        case_id = support_case_id(
            {
                "scene": row.get("scene", ""),
                "optical_frame": row.get("optical_frame", ""),
                "sar_frame": row.get("sar_frame", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
            }
        )
        result[case_id] = row
    return result


def card_source(
    card: Mapping[str, Any],
    gt_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
    corr_by_case: Mapping[str, Mapping[str, Any]],
    support_by_case: Mapping[str, Mapping[str, Any]],
) -> tuple[str, dict[str, float] | None, Mapping[str, Any] | None, Mapping[str, Any] | None]:
    case_id = str(card.get("case_id", ""))
    support = support_by_case.get(case_id)
    corr = corr_by_case.get(case_id)
    if str(card.get("gt_id", "")):
        gt = gt_by_key.get((str(card.get("scene", "")), str(card.get("sar_frame", "")), str(card.get("gt_id", ""))))
        if gt:
            return str(gt.get("sar_pseudocolor_path", "")), gt_box_from_accounting(gt), support, corr
    if corr:
        image_path = str(support.get("sar_image_path", "")) if support else ""
        if not image_path:
            image_path = str(corr.get("sar_pseudocolor_path", ""))
        return image_path, gt_box_from_correspondence(corr), support, corr
    return str(support.get("sar_image_path", "")) if support else "", None, support, None


def support_closed_polygon(lines: Sequence[Sequence[tuple[float, float]]]) -> list[tuple[float, float]]:
    if len(lines) < 2:
        return []
    inner = list(lines[0])
    outer = list(lines[1])
    return inner + list(reversed(outer))


def energy_atom_points(arr: np.ndarray | None, box: Mapping[str, float] | None) -> list[tuple[float, float]]:
    if arr is None or not box or not box_available(box):
        return []
    table = gt_pixel_table(arr, box)
    if table is None:
        return []
    values = table["values"]
    if values.size == 0:
        return []
    threshold = float(np.quantile(values, 0.97))
    xs = table["x"][values >= threshold]
    ys = table["y"][values >= threshold]
    vals = values[values >= threshold]
    order = np.argsort(vals)[::-1]
    selected: list[tuple[float, float]] = []
    for idx in order:
        x = float(xs[idx])
        y = float(ys[idx])
        if all(math.hypot(x - px, y - py) >= 12 for px, py in selected):
            selected.append((x, y))
        if len(selected) >= 10:
            break
    return selected


def previous_next_paths(image_path: str) -> dict[str, str]:
    path = Path(str(image_path or ""))
    if not path.exists():
        return {"prev": "", "current": "", "next": ""}
    try:
        idx = int(path.stem)
    except ValueError:
        return {"prev": "", "current": str(path), "next": ""}
    result = {"prev": "", "current": str(path), "next": ""}
    for label, delta in [("prev", -1), ("next", 1)]:
        candidate = path.with_name(f"{idx + delta:06d}{path.suffix}")
        if candidate.exists():
            result[label] = str(candidate)
    return result


def wrap_zh(text: str, width: int = 27) -> str:
    text = str(text)
    if not text:
        return ""
    chunks: list[str] = []
    for part in text.split("\n"):
        current = ""
        for char in part:
            current += char
            if len(current) >= width:
                chunks.append(current)
                current = ""
        if current:
            chunks.append(current)
    return "\n".join(chunks)


def draw_crop_axis(
    ax: Any,
    crop_arr: np.ndarray,
    title: str,
    gt_local: Sequence[tuple[float, float]] | None = None,
    support_local_lines: Sequence[Sequence[tuple[float, float]]] | None = None,
    energy_local: Sequence[tuple[float, float]] | None = None,
) -> None:
    crop_h, crop_w = crop_arr.shape[:2]
    ax.imshow(crop_arr, cmap="gray", origin="upper", extent=(0, crop_w, crop_h, 0))
    ax.set_xlim(0, crop_w)
    ax.set_ylim(crop_h, 0)
    ax.set_aspect("equal")
    ax.set_title(title, fontproperties=FONT, fontsize=9)
    ax.tick_params(labelsize=6)
    ax.grid(color="#4a9cff", alpha=0.18, linewidth=0.5)
    if gt_local:
        ax.add_patch(Polygon(gt_local, closed=True, fill=False, edgecolor="#ffd400", linewidth=2.0))
    if support_local_lines:
        closed = support_closed_polygon(support_local_lines)
        if closed:
            ax.add_patch(Polygon(closed, closed=True, fill=True, facecolor="#ff00aa", alpha=0.12, edgecolor="none"))
        for line in support_local_lines:
            if line:
                xs, ys = zip(*line)
                ax.plot(xs, ys, color="#ff00cc", linewidth=1.6)
    if energy_local:
        xs, ys = zip(*energy_local)
        ax.scatter(xs, ys, s=18, facecolors="none", edgecolors="#ff5a00", linewidths=1.2)


def draw_temporal_axis(ax: Any, image_path: str, crop: tuple[int, int, int, int], label: str) -> None:
    arr = read_gray(image_path)
    if arr is None:
        ax.text(0.5, 0.5, "无相邻帧", ha="center", va="center", fontproperties=FONT, fontsize=9)
        ax.set_axis_off()
        return
    x0, y0, x1, y1 = crop
    crop_arr = arr[y0:y1, x0:x1]
    draw_crop_axis(ax, crop_arr, label)
    ax.set_xticks([])
    ax.set_yticks([])


def side_energy_means(arr: np.ndarray | None, box: Mapping[str, float] | None) -> list[tuple[str, float]]:
    if arr is None or not box or not box_available(box):
        return []
    table = gt_pixel_table(arr, box)
    if table is None:
        return []
    values = table["values"]
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(table["w"][0])
    h = float(table["h"][0])
    masks = [
        ("下侧条带", ly >= 0.25 * h),
        ("上侧条带", ly <= -0.25 * h),
        ("左侧条带", lx <= -0.25 * w),
        ("右侧条带", lx >= 0.25 * w),
        ("角点区域", (np.abs(lx) >= 0.28 * w) & (np.abs(ly) >= 0.28 * h)),
    ]
    return [(name, float(values[mask].mean()) if bool(mask.any()) else 0.0) for name, mask in masks]


def draw_profile_axis(ax: Any, arr: np.ndarray | None, box: Mapping[str, float] | None) -> None:
    means = side_energy_means(arr, box)
    if not means:
        ax.text(0.5, 0.5, "GT 能量 profile 不可用", ha="center", va="center", fontproperties=FONT, fontsize=9)
        ax.set_axis_off()
        return
    labels = [name for name, _ in means]
    values = [value for _, value in means]
    ax.bar(range(len(values)), values, color="#00bcd4")
    ax.set_xticks(range(len(values)), labels, fontproperties=FONT, fontsize=8)
    ax.set_ylabel("mean display energy", fontsize=8)
    ax.set_title("GT 内能量 profile / 高能区域提示", fontproperties=FONT, fontsize=9)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="y", alpha=0.25)


def support_judgment_text(support: Mapping[str, Any] | None, qa_status: str) -> str:
    if support and support_available(support) and qa_status == "pass":
        return "可判断 reconstructed support 对 GT 主结构的覆盖，但只能作为 posthoc coverage hypothesis。"
    if support and support_available(support):
        return "可查看 reconstructed support，但必须结合 QA 警告，不能直接下 coverage 结论。"
    return "不可判断 paired support；该图只能作为 SAR morphology reference。"


def gt_judgment_text(box: Mapping[str, float] | None, image_path: str) -> str:
    if box and box_available(box) and Path(str(image_path)).exists():
        return "可判断 GT 框内 SAR morphology；GT 是 posthoc morphology anchor。"
    return "不可判断；缺少图像或 GT 框。"


def render_panel(
    idx: int,
    card: Mapping[str, Any],
    image_path: str,
    arr: np.ndarray,
    box: Mapping[str, float] | None,
    support: Mapping[str, Any] | None,
    crop: tuple[int, int, int, int],
    gt_local: Sequence[tuple[float, float]],
    support_local_lines: Sequence[Sequence[tuple[float, float]]],
    energy_local: Sequence[tuple[float, float]],
    qa_status: str,
    qa_reason: str,
    output_path: Path,
) -> None:
    x0, y0, x1, y1 = crop
    crop_arr = arr[y0:y1, x0:x1]
    category = str(card.get("category", ""))
    guidance = CARD_GUIDANCE.get(category, CARD_GUIDANCE["possible compact vehicle structure"])
    temporal_paths = previous_next_paths(image_path)

    fig = plt.figure(figsize=(17.2, 10.4), dpi=150, constrained_layout=True)
    gs = fig.add_gridspec(3, 4, height_ratios=[1.05, 0.78, 0.62], width_ratios=[1, 1, 1, 1.15])
    fig.suptitle(f"{idx}. {guidance['title']} | {card.get('case_id', '')}", fontproperties=FONT, fontsize=13)

    ax_gt = fig.add_subplot(gs[0, 0])
    draw_crop_axis(ax_gt, crop_arr, "SAR crop + GT 框", gt_local=gt_local)
    ax_support = fig.add_subplot(gs[0, 1])
    draw_crop_axis(ax_support, crop_arr, "SAR crop + reconstructed support", support_local_lines=support_local_lines)
    ax_combined = fig.add_subplot(gs[0, 2])
    draw_crop_axis(
        ax_combined,
        crop_arr,
        "GT + support + 高能点",
        gt_local=gt_local,
        support_local_lines=support_local_lines,
        energy_local=energy_local,
    )

    ax_text = fig.add_subplot(gs[0:2, 3])
    ax_text.set_axis_off()
    support_text = support_judgment_text(support, qa_status)
    gt_text = gt_judgment_text(box, image_path)
    text_lines = [
        f"样例类型：{guidance['type']}",
        f"为什么选：{guidance['why']}",
        f"重点看：{guidance['look']}",
        f"人工问题：{guidance['question']}",
        f"可记录：{guidance['can']}",
        f"不能记录：{guidance['cannot']}",
        f"混淆因素：{guidance['confounder']}",
        f"support：{support_text}",
        f"GT：{gt_text}",
        f"QA：{qa_status}；{qa_reason or '坐标转换通过'}",
        "图注：GT = SAR posthoc morphology anchor；support = optical-derived feasible region/reconstructed sector-range；energy = SAR observation。",
        "边界：本图不输出 final annotation / identity truth。",
        f"crop={x0},{y0},{x1},{y1}; y 原点=图像左上角。",
    ]
    ax_text.text(
        0.0,
        1.0,
        "\n\n".join(wrap_zh(line, 28) for line in text_lines),
        va="top",
        fontproperties=FONT,
        fontsize=8.2,
        linespacing=1.15,
    )

    ax_prev = fig.add_subplot(gs[1, 0])
    draw_temporal_axis(ax_prev, temporal_paths.get("prev", ""), crop, "前一帧小图")
    ax_cur = fig.add_subplot(gs[1, 1])
    draw_temporal_axis(ax_cur, temporal_paths.get("current", ""), crop, "当前帧小图")
    ax_next = fig.add_subplot(gs[1, 2])
    draw_temporal_axis(ax_next, temporal_paths.get("next", ""), crop, "后一帧小图")

    ax_profile = fig.add_subplot(gs[2, :])
    draw_profile_axis(ax_profile, arr, box)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def build_card_index_row(
    idx: int,
    card: Mapping[str, Any],
    support: Mapping[str, Any] | None,
    box: Mapping[str, float] | None,
    image_path: str,
    qa_status: str,
    panel_path: Path,
) -> dict[str, Any]:
    category = str(card.get("category", ""))
    guidance = CARD_GUIDANCE.get(category, CARD_GUIDANCE["possible compact vehicle structure"])
    return {
        "panel_index": idx,
        "case_id": card.get("case_id", ""),
        "中文标题": guidance["title"],
        "样例类型": guidance["type"],
        "为什么选择这张": guidance["why"],
        "这张图要看什么": guidance["look"],
        "人工需要回答的问题": guidance["question"],
        "可以记录的结论": guidance["can"],
        "不能记录的结论": guidance["cannot"],
        "主要混淆因素": guidance["confounder"],
        "support 是否可判断": support_judgment_text(support, qa_status),
        "GT 是否可判断": gt_judgment_text(box, image_path),
        "是否需要前后帧": guidance["needs_temporal"],
        "建议人工标签选项": ";".join(TAG_OPTIONS),
        "panel_path": str(panel_path),
    }


def qa_status_for(
    image_path: str,
    box: Mapping[str, float] | None,
    support: Mapping[str, Any] | None,
    gt_local: Sequence[tuple[float, float]],
    support_local_lines: Sequence[Sequence[tuple[float, float]]],
    crop_width: int,
    crop_height: int,
) -> tuple[str, str]:
    reasons: list[str] = []
    if not Path(str(image_path)).exists():
        return "fail", "image_path missing"
    if not box or not box_available(box):
        return "fail", "GT box missing"
    if not inside_crop(gt_local, crop_width, crop_height):
        return "fail", "GT box is not fully inside crop-local render extent"
    if support and support_available(support):
        support_points = all_line_points(support_local_lines)
        if not support_points:
            return "fail", "support boundary points missing"
        if not inside_crop(support_points, crop_width, crop_height):
            reasons.append("support boundary touches or exceeds crop extent")
    else:
        reasons.append("support unavailable; reference-only support judgment")
    if reasons:
        return "warning", "; ".join(reasons)
    return "pass", ""


def old_risk_for(crop_width: int, crop_height: int) -> tuple[str, str, str]:
    if crop_width > OLD_PANEL_WIDTH_CAP:
        ratio = OLD_PANEL_WIDTH_CAP / float(crop_width)
        return (
            fmt(ratio, 6),
            "yes",
            "previous generator resized the image crop to width 520 before drawing overlays, but overlay coordinates were only crop-shifted and not scaled",
        )
    return (
        "1",
        "low_for_resize_specific_issue",
        "old crop width did not trigger the 520px image resize branch, but the old atlas still lacked coordinate QA metadata and Chinese review guidance",
    )


def panel_filename(idx: int, card: Mapping[str, Any]) -> str:
    return f"{idx:02d}_{sanitize(card.get('case_id'))}_gt_support_energy_panel_cn.png"


def render_html(atlas_path: Path, html_cards: Sequence[str]) -> None:
    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>OTY2 support overlay QA Chinese review atlas</title>"
        "<style>"
        "body{font-family:'Microsoft YaHei',Arial,sans-serif;background:#f5f5f5;color:#111;margin:24px;}"
        "article{background:#fff;border:1px solid #bbb;margin:0 0 24px;padding:16px;}"
        "img{max-width:100%;height:auto;border:1px solid #555;display:block;}"
        "code{font-size:12px;color:#064f8a;}"
        ".warn{color:#9a6700;font-weight:600;}"
        "</style></head><body>"
        "<h1>OTY2 support overlay visualization QA and Chinese review atlas</h1>"
        "<p>本 atlas 只嵌入已经渲染完成的 PNG。GT、support、energy 均在同一 crop-local matplotlib axes 中绘制；不使用浏览器端 overlay。"
        "GT 是 SAR posthoc morphology anchor；support 是 optical-derived feasible region/reconstructed sector-range；本图不输出 final annotation、selector/ranking 或 identity truth。</p>"
        "<p class='warn'>旧 overlay atlas 在 image crop resize 后没有同步缩放 overlay，不能直接用于 support coverage 人工判断。</p>"
        + "\n".join(html_cards)
        + "</body></html>"
    )
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    atlas_path.write_text(html_doc, encoding="utf-8")


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    counts = summary["qa_counts"]
    old_risk_cases = ";".join(summary["old_resize_specific_risk_cases"]) or "none"
    lines = [
        "# OTY2 Support Overlay Visualization QA And Chinese Review Atlas Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report fixes the support overlay visualization workflow and regenerates a Chinese review atlas. It does not generate annotation proposals, final candidate boxes, selector/ranking outputs, training, threshold tuning, best weights, or identity truth.",
        "",
        "## Why Previous Overlay Atlas Should Not Be Used Without QA",
        "",
        "1. The previous PNG generator cropped the SAR image and resized crops wider than 520 px before drawing overlays.",
        "2. GT/support/energy overlay points were shifted by crop origin, but the resize scale was not applied.",
        f"3. Panels with resize-specific risk: `{summary['old_resize_specific_risk_count']}` / `{summary['panel_count']}`.",
        f"4. Resize-risk cases: `{old_risk_cases}`.",
        "5. Manual SAR morphology notes can be retained as textual observations when they do not depend on support alignment.",
        "6. Previous support coverage visual judgment must be paused because it may have been based on visually shifted support/GT boundaries.",
        "7. The fixed atlas renders image and overlays in one crop-local axes and records full-image, crop-local, and render coordinates.",
        "",
        "## Coordinate QA Result",
        "",
        f"- pass: `{counts.get('pass', 0)}`",
        f"- warning: `{counts.get('warning', 0)}`",
        f"- fail: `{counts.get('fail', 0)}`",
        f"- support_unjudgeable_cases: `{len(summary['support_unjudgeable_cases'])}`",
        "",
        "Warnings are expected for SAR-only or GM_RM011 reference panels because paired optical-derived support is unavailable there.",
        "",
        "## Required Answers",
        "",
        "1. The previous overlay atlas has coordinate/scale risk. The concrete bug is resize-without-overlay-scale after crop.",
        "2. The main coordinate-transform issue is not HTML overlay scaling; the HTML embedded static PNGs. The risky transform is in PNG generation: crop-local coordinates were drawn on a resized crop without applying scale.",
        "3. This run fixes the issue by drawing SAR crop, GT, support, and energy atoms inside one matplotlib axes with `origin='upper'` and crop-local extent `(0, crop_width, crop_height, 0)`. Render coordinates equal crop-local coordinates, so `scale_x=scale_y=1`.",
        f"4. QA pass cases: `{';'.join(summary['pass_cases'])}`.",
        f"5. QA warning cases: `{';'.join(summary['warning_cases'])}`.",
        f"6. QA fail cases: `{';'.join(summary['fail_cases']) or 'none'}`.",
        f"7. Chinese atlas regenerated: `{summary['outputs']['chinese_atlas_html']}`.",
        "8. Chinese review cards state what to inspect, why to inspect it, what may be recorded, and what must not be concluded.",
        "9. Previous manual SAR morphology notes that describe GT-box body structure, near/facing-side high energy, discontinuous body edges, and temporal hotspot migration may be retained as morphology notes.",
        "10. Previous support coverage visual judgments from the old atlas must be paused until reviewers use the fixed CN atlas and coordinate QA CSV.",
        "11. Next manual review should use the fixed CN atlas panels and the Chinese card index, starting with warnings/reference-only cases and old resize-risk cases.",
        "12. After human review, motion/drift compatibility or GM_RM019 optical continuity review can continue as a separate bounded stage.",
        "",
        "## Boundary Flags",
        "",
    ]
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        f"oty2_support_overlay_visualization_qa_and_chinese_review_atlas {summary['timestamp']}",
        "interpreter=D:\\MINICONDA\\envs\\py311\\python.exe",
        "old_work_runtime_paths_used=false",
        "task=visualization coordinate QA and Chinese review atlas fix",
        f"panel_count={summary['panel_count']}",
        f"qa_counts={summary['qa_counts']}",
        f"chinese_atlas_html={summary['outputs']['chinese_atlas_html']}",
        f"geometry_debug_csv={summary['outputs']['geometry_debug_csv']}",
        "selector_or_ranking_used=false",
        "final_annotation_or_identity_truth=false",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = {
        "gt_accounting_csv": Path(args.gt_accounting_csv) if args.gt_accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "support_peak_competition_csv": Path(args.support_peak_competition_csv) if args.support_peak_competition_csv else latest_path("oty2_support_region_peak_competition_audit_*.csv"),
        "visual_review_cards_csv": Path(args.visual_review_cards_csv) if args.visual_review_cards_csv else latest_path("oty2_visual_review_candidate_cards_*.csv"),
        "old_atlas_html": Path(args.old_atlas_html) if args.old_atlas_html else latest_path(OLD_ATLAS_GLOB, VISUAL_DIR),
    }

    gt_rows = read_csv(paths["gt_accounting_csv"])
    corr_rows = read_csv(paths["correspondence_csv"])
    support_rows = read_csv(paths["support_peak_competition_csv"])
    cards = read_csv(paths["visual_review_cards_csv"])

    gt_by_key = gt_accounting_lookup(gt_rows)
    corr_by_case = corr_lookup(corr_rows)
    support_by_case = support_lookup(support_rows)

    geometry_rows: list[dict[str, Any]] = []
    coordinate_rows: list[dict[str, Any]] = []
    card_rows: list[dict[str, Any]] = []
    html_cards: list[str] = []
    old_resize_risk_count = 0
    old_resize_risk_cases: list[str] = []

    for idx, card in enumerate(cards, start=1):
        image_path, box, support, _corr = card_source(card, gt_by_key, corr_by_case, support_by_case)
        arr = read_gray(image_path)
        size = image_size(image_path)
        if arr is None or size is None:
            crop = (0, 0, 0, 0)
            crop_width = 0
            crop_height = 0
            gt_original: list[tuple[float, float]] = []
            gt_local: list[tuple[float, float]] = []
            support_original_lines: list[list[tuple[float, float]]] = []
            support_local_lines: list[list[tuple[float, float]]] = []
            energy_local: list[tuple[float, float]] = []
            qa_status, qa_reason = "fail", "image_path missing"
        else:
            with Image.open(image_path) as image:
                crop = crop_box_for(image.convert("RGB"), box, support)
            crop_width = crop[2] - crop[0]
            crop_height = crop[3] - crop[1]
            gt_original = rotated_corners(box) if box and box_available(box) else []
            gt_local = to_crop_points(gt_original, crop)
            support_original_lines = support_boundary_points(support) if support and support_available(support) else []
            support_local_lines = to_crop_lines(support_original_lines, crop)
            energy_original = energy_atom_points(arr, box)
            energy_local = to_crop_points(energy_original, crop)
            qa_status, qa_reason = qa_status_for(image_path, box, support, gt_local, support_local_lines, crop_width, crop_height)

        old_ratio, old_risk, old_reason = old_risk_for(crop_width, crop_height)
        if old_risk == "yes":
            old_resize_risk_count += 1
            old_resize_risk_cases.append(str(card.get("case_id", "")))

        panel_path = VISUAL_DIR / panel_filename(idx, card)
        if arr is not None and crop_width > 0 and crop_height > 0:
            render_panel(
                idx,
                card,
                image_path,
                arr,
                box,
                support,
                crop,
                gt_local,
                support_local_lines,
                energy_local,
                qa_status,
                qa_reason,
                panel_path,
            )

        old_panel_name = f"{idx:02d}_{sanitize(card.get('category'))}_{sanitize(card.get('case_id'))}_gt_support_energy_panel.png"
        old_panel_path = VISUAL_DIR / old_panel_name
        support_judgment_allowed = "yes" if support and support_available(support) and qa_status == "pass" else "no"
        gt_judgment_allowed = "yes" if box and box_available(box) and Path(str(image_path)).exists() else "no"

        geometry_rows.append(
            {
                "panel_index": idx,
                "case_id": card.get("case_id", ""),
                "scene": card.get("scene", ""),
                "sar_frame": card.get("sar_frame", ""),
                "image_path": image_path,
                "image_width": size[0] if size else "",
                "image_height": size[1] if size else "",
                "crop_x0": crop[0],
                "crop_y0": crop[1],
                "crop_x1": crop[2],
                "crop_y1": crop[3],
                "crop_width": crop_width,
                "crop_height": crop_height,
                "render_width": crop_width,
                "render_height": crop_height,
                "scale_x": "1",
                "scale_y": "1",
                "gt_original_coords": coords_json(gt_original),
                "gt_crop_local_coords": coords_json(gt_local),
                "gt_render_coords": coords_json(gt_local),
                "support_original_coords": lines_json(support_original_lines),
                "support_crop_local_coords": lines_json(support_local_lines),
                "support_render_coords": lines_json(support_local_lines),
                "coordinate_system_note": "full-image SAR pixels -> subtract crop origin -> crop-local render coordinates; no independent HTML/CSS overlay",
                "y_axis_origin": "upper_left_image_origin_y_down",
                "overlay_method": "matplotlib_single_axes_imshow_extent_0_crop_width_crop_height_0",
                "qa_status": qa_status,
                "qa_warning_reason": qa_reason,
                "panel_path": str(panel_path),
            }
        )
        coordinate_rows.append(
            {
                "panel_index": idx,
                "case_id": card.get("case_id", ""),
                "scene": card.get("scene", ""),
                "sar_frame": card.get("sar_frame", ""),
                "old_atlas_path": str(paths["old_atlas_html"]),
                "old_panel_path": str(old_panel_path),
                "old_crop_width": crop_width,
                "old_crop_height": crop_height,
                "old_resize_ratio": old_ratio,
                "previous_overlay_coordinate_risk": old_risk,
                "previous_overlay_risk_reason": old_reason,
                "new_panel_path": str(panel_path),
                "new_overlay_method": "static PNG rendered from one crop-local matplotlib axes",
                "new_scale_x": "1",
                "new_scale_y": "1",
                "qa_status": qa_status,
                "qa_warning_reason": qa_reason,
                "support_render_method": "reconstructed_from_sector_radius_and_azimuth_fields" if support and support_available(support) else "not_renderable_for_support_reference_only",
                "support_judgment_allowed": support_judgment_allowed,
                "gt_judgment_allowed": gt_judgment_allowed,
            }
        )
        card_rows.append(build_card_index_row(idx, card, support, box, image_path, qa_status, panel_path))
        html_cards.append(
            "<article>"
            f"<h2>{idx}. {html.escape(str(card_rows[-1]['中文标题']))}</h2>"
            f"<p><code>{html.escape(str(card.get('case_id', '')))}</code></p>"
            f"<p>QA: <strong>{html.escape(qa_status)}</strong> {html.escape(qa_reason)}</p>"
            f"<img src='{html.escape(panel_path.name)}' alt='{html.escape(str(card.get('case_id', '')))}' />"
            "</article>"
        )

    coordinate_csv = REPORT_DIR / f"oty2_overlay_coordinate_qa_{timestamp}.csv"
    geometry_csv = REPORT_DIR / f"oty2_overlay_case_geometry_debug_{timestamp}.csv"
    card_index_csv = REPORT_DIR / f"oty2_chinese_review_card_index_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_support_overlay_visualization_qa_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_support_overlay_visualization_qa_summary_{timestamp}.json"
    atlas_html = VISUAL_DIR / f"oty2_gt_support_energy_overlay_atlas_cn_{timestamp}.html"
    workspace_log = WORKSPACE_LOG_DIR / f"oty2_support_overlay_visualization_qa_and_chinese_review_atlas_{timestamp}.log"

    write_csv(coordinate_csv, coordinate_rows, COORDINATE_QA_FIELDS)
    write_csv(geometry_csv, geometry_rows, GEOMETRY_DEBUG_FIELDS)
    write_csv(card_index_csv, card_rows, CHINESE_CARD_FIELDS)
    render_html(atlas_html, html_cards)

    qa_counts = Counter(row["qa_status"] for row in geometry_rows)
    pass_cases = [str(row["case_id"]) for row in geometry_rows if row["qa_status"] == "pass"]
    warning_cases = [str(row["case_id"]) for row in geometry_rows if row["qa_status"] == "warning"]
    fail_cases = [str(row["case_id"]) for row in geometry_rows if row["qa_status"] == "fail"]
    support_unjudgeable = [
        str(row["case_id"])
        for row in coordinate_rows
        if row["support_judgment_allowed"] != "yes"
    ]

    outputs = {
        "plan_doc": str(PLAN_DOC),
        "coordinate_qa_csv": str(coordinate_csv),
        "geometry_debug_csv": str(geometry_csv),
        "chinese_review_card_index_csv": str(card_index_csv),
        "qa_report_md": str(report_md),
        "qa_summary_json": str(summary_json),
        "chinese_atlas_html": str(atlas_html),
        "workspace_log": str(workspace_log),
    }
    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "panel_count": len(cards),
        "old_atlas_path": str(paths["old_atlas_html"]),
        "old_resize_specific_risk_count": old_resize_risk_count,
        "old_resize_specific_risk_cases": old_resize_risk_cases,
        "qa_counts": dict(qa_counts),
        "pass_cases": pass_cases,
        "warning_cases": warning_cases,
        "fail_cases": fail_cases,
        "support_unjudgeable_cases": support_unjudgeable,
        "previous_overlay_atlas_should_not_be_used_without_qa": True,
        "old_morphology_notes_retained": [
            "GT-box SAR body structure observations",
            "near/facing-side high energy and far-side weak return notes",
            "discontinuous body-edge morphology notes",
            "temporal hotspot migration notes",
        ],
        "old_support_coverage_judgments_paused": True,
        "next_manual_review": "Use the fixed Chinese atlas PNG panels plus geometry debug CSV before judging support coverage.",
        "boundary_flags": BOUNDARY_FLAGS,
        "inputs": {key: str(value) for key, value in paths.items()},
        "outputs": outputs,
    }
    render_report(report_md, summary)
    write_json(summary_json, summary)
    write_workspace_log(workspace_log, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--gt-accounting-csv", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--support-peak-competition-csv", default="")
    parser.add_argument("--visual-review-cards-csv", default="")
    parser.add_argument("--old-atlas-html", default="")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
