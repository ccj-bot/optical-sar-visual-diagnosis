"""Generate object-level visual diagnosis pages for OTY2 spatial priors.

The pages embed real optical frames and draw the runtime-safe object boxes from
the OTY1t object stream. The SAR side is shown only as a timeline and an
abstract prior canvas. This script does not read SAR image content, use SAR GT,
generate SAR search regions, generate candidate boxes, score/select candidates,
train/tune thresholds, generate annotation proposals, claim identity truth, or
reintroduce detection-box-level merging.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLE_VIS_DIR = REPORT_DIR / "samples" / "visualizations"
OUTPUT_PARENT = REPO_ROOT / "outputs"
DEFAULT_P4G_OUTPUT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"

OPTICAL_FPS = 24
SAR_FPS = 50
FPS_RATIO = SAR_FPS / OPTICAL_FPS
ESTIMATED_SAR_SCENE_FRAMES = math.ceil(368 * FPS_RATIO)

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_spatial_search_implemented": False,
    "sar_search_region_generated": False,
    "sar_candidate_boxes_generated": False,
    "candidate_box_scoring_used": False,
    "sar_gt_used": False,
    "final_manual_oracle_review_runtime_fields_used": False,
    "selector_or_ranking_used": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "detection_box_level_merge_reintroduced": False,
    "spatial_prior_claimed_as_final_location": False,
}

SUMMARY_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "sample_role",
    "status_cn",
    "status_code",
    "optical_start_frame",
    "optical_mid_frame",
    "optical_end_frame",
    "sar_start_frame",
    "sar_end_frame",
    "sar_window_frame_count",
    "has_real_optical_frames",
    "primary_boxes_drawn",
    "secondary_boxes_drawn",
    "edge_partial_state",
    "duplicate_handoff_state",
    "ambiguity_status",
    "azimuth_prior_available",
    "azimuth_interval_deg",
    "azimuth_width_deg",
    "range_prior_mode",
    "range_status_cn",
    "weakness_cn",
    "missing_fields_cn",
    "local_page_path",
    "repo_sample_path",
]

SAMPLE_SELECTION = {
    "稳定正常空间先验": ("GM_RM017", "oty1t_obj_GM_RM017_bytetrack_bt_0002"),
    "宽松空间先验": ("GM_RM019", "oty1t_obj_GM_RM019_bytetrack_bt_0042"),
    "仅审阅空间上下文": ("GM_RM019", "oty1t_obj_GM_RM019_bytetrack_bt_0053"),
    "阻断对象": ("GM_RM019", "oty1t_obj_GM_RM019_bytetrack_bt_0009"),
    "第十一场景说明": ("GM_RM011", ""),
}

SAMPLE_ROLE_SLUG = {
    "稳定正常空间先验": "normal_stable",
    "宽松空间先验": "relaxed_uncertain",
    "仅审阅空间上下文": "review_only",
    "阻断对象": "blocked_object",
    "第十一场景说明": "gmrm011_no_object_flow",
}


def latest_path(pattern: str, base: Path = REPORT_DIR) -> Path:
    paths = sorted(base.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base / pattern}")
    return paths[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def safe_int(value: Any, default: int | None = None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def choose_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


FONTS = {
    "title": choose_font(38, True),
    "h1": choose_font(28, True),
    "h2": choose_font(22, True),
    "body": choose_font(19),
    "small": choose_font(16),
    "tiny": choose_font(13),
}


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: Any, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    raw = str(text if text is not None else "")
    if not raw:
        return [""]
    lines: list[str] = []
    for paragraph in raw.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if text_size(draw, candidate, font)[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines or [raw]


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: Any,
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    line_gap: int = 6,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_text(draw, text, font, max_width)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1] + "..."]
    cursor = y
    for line in lines:
        draw.text((x, cursor), line, font=font, fill=fill)
        cursor += text_size(draw, line or " ", font)[1] + line_gap
    return cursor


def draw_card(
    draw: ImageDraw.ImageDraw,
    xywh: tuple[int, int, int, int],
    title: str,
    body: Sequence[Any],
    border: str = "#cbd5e1",
    fill: str = "#ffffff",
) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=fill, outline=border, width=2)
    draw.text((x + 18, y + 16), title, font=FONTS["h2"], fill="#0f172a")
    cursor = y + 54
    for item in body:
        cursor = draw_wrapped(draw, (x + 18, cursor), item, FONTS["small"], "#334155", w - 36, max_lines=4)
        cursor += 4
        if cursor > y + h - 18:
            break


def draw_tag(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str) -> int:
    x, y = xy
    pad_x = 14
    pad_y = 7
    w, h = text_size(draw, text, FONTS["small"])
    draw.rounded_rectangle((x, y, x + w + pad_x * 2, y + h + pad_y * 2), radius=14, fill=fill)
    draw.text((x + pad_x, y + pad_y - 1), text, font=FONTS["small"], fill="#ffffff")
    return x + w + pad_x * 2 + 10


def parse_azimuth(text: str) -> dict[str, float | str]:
    center_match = re.search(r"center_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    interval_match = re.search(r"interval_deg=\[([-+]?\d+(?:\.\d+)?),([-+]?\d+(?:\.\d+)?)\]", text or "")
    margin_match = re.search(r"margin_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    start = safe_float(interval_match.group(1)) if interval_match else None
    end = safe_float(interval_match.group(2)) if interval_match else None
    center = safe_float(center_match.group(1)) if center_match else None
    margin = safe_float(margin_match.group(1)) if margin_match else None
    width = None if start is None or end is None else max(0.0, end - start)
    return {
        "center": "" if center is None else center,
        "start": "" if start is None else start,
        "end": "" if end is None else end,
        "width": "" if width is None else width,
        "margin": "" if margin is None else margin,
    }


def parse_secondary_boxes(text: str) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for part in str(text or "").split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        det_id, coords = part.split(":", 1)
        values = [safe_float(value) for value in coords.split(",")]
        if len(values) >= 4 and all(value is not None for value in values[:4]):
            boxes.append(
                {
                    "det_id": det_id,
                    "bbox": (float(values[0]), float(values[1]), float(values[2]), float(values[3])),
                }
            )
    return boxes


def primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    values = [
        safe_float(row.get("primary_bbox_x1")),
        safe_float(row.get("primary_bbox_y1")),
        safe_float(row.get("primary_bbox_x2")),
        safe_float(row.get("primary_bbox_y2")),
    ]
    if all(value is not None for value in values):
        x1, y1, x2, y2 = [float(value) for value in values]
        if x2 > x1 and y2 > y1:
            return x1, y1, x2, y2
    return None


def status_cn(row: Mapping[str, Any]) -> str:
    status = str(row.get("spatial_prior_status", ""))
    if status == "normal_spatial_prior_generated":
        return "正常"
    if status == "loose_spatial_prior_generated":
        return "宽松"
    if status == "review_only_spatial_context_generated":
        return "仅审阅"
    if status == "blocked_missing_object_level_flow":
        return "阻断：缺目标流"
    if status.startswith("blocked"):
        return "阻断"
    return "未知"


def status_color(status: str) -> str:
    return {
        "正常": "#2563eb",
        "宽松": "#0891b2",
        "仅审阅": "#a16207",
        "阻断": "#dc2626",
        "阻断：缺目标流": "#7c3aed",
    }.get(status, "#64748b")


def short_object_id(object_id: str) -> str:
    if not object_id:
        return "scene_only"
    match = re.search(r"bt_\d+", object_id)
    return match.group(0) if match else object_id[-20:]


def filename_token(scene: str, object_id: str) -> str:
    return f"{scene.lower()}_{short_object_id(object_id).replace('_', '')}"


def load_frame_paths(manifest_csv: Path) -> dict[tuple[str, int], Path]:
    paths: dict[tuple[str, int], Path] = {}
    for inventory in sorted((REPO_ROOT / "outputs").glob("oty0_yolo_detection_stream_audit_*/oty0_optical_frame_inventory.csv")):
        for row in read_csv(inventory):
            frame = safe_int(row.get("optical_frame_num"))
            path = Path(str(row.get("optical_path", "")))
            if row.get("scene") and frame is not None and path.exists():
                paths[(str(row["scene"]), frame)] = path
    if manifest_csv.exists():
        for row in read_csv(manifest_csv):
            scene = str(row.get("scene", ""))
            frame_dir = Path(str(row.get("optical_frames_dir", "")))
            if not scene or not frame_dir.exists():
                continue
            start = safe_int(row.get("frame_range_start"), 0) or 0
            end = safe_int(row.get("frame_range_end"), 367) or 367
            for frame in (start, (start + end) // 2, end):
                for suffix in (".png", ".jpg", ".jpeg"):
                    candidate = frame_dir / f"{frame:06d}{suffix}"
                    if candidate.exists():
                        paths.setdefault((scene, frame), candidate)
                        break
    return paths


def load_manifest_frame_dirs(manifest_csv: Path) -> dict[str, Path]:
    dirs: dict[str, Path] = {}
    if not manifest_csv.exists():
        return dirs
    for row in read_csv(manifest_csv):
        scene = str(row.get("scene", ""))
        frame_dir = Path(str(row.get("optical_frames_dir", "")))
        if scene and frame_dir.exists():
            dirs[scene] = frame_dir
    return dirs


def resolve_frame_path(
    scene: str,
    frame: int,
    frame_paths: Mapping[tuple[str, int], Path],
    manifest_dirs: Mapping[str, Path],
) -> Path | None:
    direct = frame_paths.get((scene, frame))
    if direct and direct.exists():
        return direct
    frame_dir = manifest_dirs.get(scene)
    if frame_dir:
        for suffix in (".png", ".jpg", ".jpeg"):
            candidate = frame_dir / f"{frame:06d}{suffix}"
            if candidate.exists():
                return candidate
    return None


def merge_rows_by_key(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))): dict(row) for row in rows}


def choose_frame_rows(object_rows: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    rows = [row for row in object_rows if safe_int(row.get("optical_frame_num")) is not None]
    rows = sorted(rows, key=lambda row: safe_int(row.get("optical_frame_num"), 0) or 0)
    if not rows:
        return []
    indices = [0, len(rows) // 2, len(rows) - 1]
    selected: list[Mapping[str, str]] = []
    for idx in indices:
        row = rows[idx]
        if row not in selected:
            selected.append(row)
    return selected


def scene_only_frame_rows(scene: str, frame_paths: Mapping[tuple[str, int], Path], manifest_dirs: Mapping[str, Path]) -> list[dict[str, str]]:
    candidates = [0, 183, 367]
    rows: list[dict[str, str]] = []
    for frame in candidates:
        if resolve_frame_path(scene, frame, frame_paths, manifest_dirs):
            rows.append({"scene": scene, "optical_frame_num": str(frame)})
    return rows


def scale_and_draw_boxes(
    source: Image.Image,
    panel_size: tuple[int, int],
    frame_row: Mapping[str, Any],
) -> tuple[Image.Image, int, int]:
    panel_w, panel_h = panel_size
    image = source.convert("RGB")
    scale = min(panel_w / image.width, panel_h / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (panel_w, panel_h), "#111827")
    offset_x = (panel_w - new_size[0]) // 2
    offset_y = (panel_h - new_size[1]) // 2
    panel.paste(resized, (offset_x, offset_y))
    draw = ImageDraw.Draw(panel)

    def project(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        return (
            int(offset_x + x1 * scale),
            int(offset_y + y1 * scale),
            int(offset_x + x2 * scale),
            int(offset_y + y2 * scale),
        )

    primary_count = 0
    secondary_count = 0
    pbox = primary_box(frame_row)
    if pbox:
        draw.rectangle(project(pbox), outline="#22c55e", width=5)
        draw.text((project(pbox)[0] + 6, max(6, project(pbox)[1] + 6)), "主观测", font=FONTS["small"], fill="#22c55e")
        primary_count = 1

    for sec in parse_secondary_boxes(str(frame_row.get("secondary_bbox_summary", ""))):
        x1, y1, x2, y2 = project(sec["bbox"])
        dash_len = 14
        for x in range(x1, x2, dash_len * 2):
            draw.line((x, y1, min(x + dash_len, x2), y1), fill="#f59e0b", width=4)
            draw.line((x, y2, min(x + dash_len, x2), y2), fill="#f59e0b", width=4)
        for y in range(y1, y2, dash_len * 2):
            draw.line((x1, y, x1, min(y + dash_len, y2)), fill="#f59e0b", width=4)
            draw.line((x2, y, x2, min(y + dash_len, y2)), fill="#f59e0b", width=4)
        draw.text((x1 + 6, max(6, y1 + 24)), "辅助", font=FONTS["small"], fill="#f59e0b")
        secondary_count += 1
    return panel, primary_count, secondary_count


def draw_timeline(
    draw: ImageDraw.ImageDraw,
    xywh: tuple[int, int, int, int],
    row: Mapping[str, Any],
) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((x + 18, y + 16), "雷达时间轴（示意，不读取 SAR 图像）", font=FONTS["h2"], fill="#0f172a")
    draw_wrapped(
        draw,
        (x + 18, y + 52),
        f"软件同步换算：光学 {OPTICAL_FPS} fps -> 雷达 {SAR_FPS} fps，使用 50/24 = {FPS_RATIO:.6f}，不是逐帧真实时间戳。",
        FONTS["small"],
        "#334155",
        w - 36,
        max_lines=2,
    )
    bar_x = x + 45
    bar_y = y + 120
    bar_w = w - 90
    draw.line((bar_x, bar_y, bar_x + bar_w, bar_y), fill="#94a3b8", width=10)
    sar_start = safe_int(row.get("sar_start_frame"))
    sar_end = safe_int(row.get("sar_end_frame"))
    if sar_start is not None and sar_end is not None:
        sx = bar_x + int(max(0, min(1, sar_start / ESTIMATED_SAR_SCENE_FRAMES)) * bar_w)
        ex = bar_x + int(max(0, min(1, sar_end / ESTIMATED_SAR_SCENE_FRAMES)) * bar_w)
        draw.line((sx, bar_y, ex, bar_y), fill="#2563eb", width=16)
        draw.text((sx, bar_y + 24), f"SAR {sar_start}", font=FONTS["tiny"], fill="#334155")
        draw.text((max(sx + 80, ex - 70), bar_y + 24), f"SAR {sar_end}", font=FONTS["tiny"], fill="#334155")
        draw.text((x + 18, y + 170), f"窗口宽度：{sar_end - sar_start + 1} 帧；作用是限定何时查看雷达，不给空间位置。", font=FONTS["small"], fill="#0f172a")
    else:
        draw.text((x + 18, y + 145), "该对象未生成目标级雷达时间窗；只保留阻断原因。", font=FONTS["small"], fill="#dc2626")
    draw.text((bar_x, bar_y - 34), "0", font=FONTS["tiny"], fill="#475569")
    draw.text((bar_x + bar_w - 60, bar_y - 34), f"约 {ESTIMATED_SAR_SCENE_FRAMES}", font=FONTS["tiny"], fill="#475569")


def draw_spatial_canvas(
    draw: ImageDraw.ImageDraw,
    xywh: tuple[int, int, int, int],
    row: Mapping[str, Any],
) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((x + 18, y + 16), "空间先验示意画布（不是搜索区域）", font=FONTS["h2"], fill="#0f172a")
    canvas = (x + 70, y + 92, x + w - 55, y + h - 78)
    cx1, cy1, cx2, cy2 = canvas
    draw.rectangle(canvas, outline="#94a3b8", width=2)
    draw.text((cx1, cy2 + 16), "方位向 azimuth（弱约束）", font=FONTS["small"], fill="#334155")
    draw.text((cx1 - 48, cy1 - 8), "距离向", font=FONTS["small"], fill="#334155")
    draw.text((cx1 - 48, cy1 + 20), "range", font=FONTS["small"], fill="#334155")
    draw.line((cx1, cy1, cx2, cy1), fill="#e2e8f0", width=1)
    draw.line((cx1, (cy1 + cy2) // 2, cx2, (cy1 + cy2) // 2), fill="#e2e8f0", width=1)
    draw.line((cx1, cy2, cx2, cy2), fill="#e2e8f0", width=1)

    az = parse_azimuth(str(row.get("azimuth_center_or_interval", "")))
    az_available = is_true(row.get("azimuth_prior_available"))
    if az_available and az["start"] != "" and az["end"] != "":
        amin, amax = -55.0, 40.0
        start = float(az["start"])
        end = float(az["end"])
        ix1 = cx1 + int(max(0.0, min(1.0, (start - amin) / (amax - amin))) * (cx2 - cx1))
        ix2 = cx1 + int(max(0.0, min(1.0, (end - amin) / (amax - amin))) * (cx2 - cx1))
        if ix2 <= ix1:
            ix2 = ix1 + 4
        draw.rectangle((ix1, cy1, ix2, cy2), fill="#93c5fd", outline="#2563eb", width=3)
        draw.text((ix1 + 8, cy1 + 14), f"方位弱先验 {start:.1f}° 到 {end:.1f}°", font=FONTS["small"], fill="#0f172a")
        if "expanded" in str(row.get("spatial_prior_mode", "")) or "expansion" in str(row.get("azimuth_margin_reason", "")):
            draw.text((ix1 + 8, cy1 + 42), "已因不确定状态扩大", font=FONTS["small"], fill="#0f172a")
    else:
        draw.text((cx1 + 20, cy1 + 22), "无可用方位先验", font=FONTS["small"], fill="#dc2626")

    range_mode = str(row.get("range_prior_mode", ""))
    if "broad_unknown" in range_mode:
        draw.rectangle((cx1 + 8, cy1 + 8, cx2 - 8, cy2 - 8), outline="#f59e0b", width=4)
        draw_wrapped(
            draw,
            (cx1 + 18, cy2 - 72),
            "距离向：broad_unknown_range_prior。当前没有运行时安全的目标级距离/深度字段，因此不能画真实距离位置。",
            FONTS["small"],
            "#92400e",
            cx2 - cx1 - 36,
            max_lines=3,
        )
    elif "not_generated" in range_mode or "blocked" in range_mode:
        draw_wrapped(
            draw,
            (cx1 + 18, cy2 - 72),
            "距离向：未生成。对象被阻断或缺目标流。",
            FONTS["small"],
            "#dc2626",
            cx2 - cx1 - 36,
            max_lines=3,
        )
    else:
        draw.text((cx1 + 18, cy2 - 54), f"距离向：{range_mode}", font=FONTS["small"], fill="#334155")
    draw.text((x + 18, y + h - 40), "已知：时间窗、弱方位；未知/保守：距离向、真实 SAR 证据。", font=FONTS["small"], fill="#334155")


def state_lines(row: Mapping[str, Any], frame_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    states = set()
    for frame_row in frame_rows:
        for field in (
            "state_visibility_status",
            "state_uncertainty_status",
            "partial_full_transition_state",
            "boundary_truncation_state",
            "multi_observation_state",
        ):
            value = str(frame_row.get(field, "")).strip()
            if value and value.lower() not in {"none", "false"}:
                states.add(value)
    if is_true(row.get("edge_or_partial_state")):
        states.add("edge/partial=true")
    if is_true(row.get("duplicate_or_handoff_state")):
        states.add("duplicate/handoff=true")
    ambiguity = str(row.get("ambiguity_status", "")).strip()
    if ambiguity:
        states.add(f"ambiguity={ambiguity}")
    if not states:
        states.add("稳定主观测，无显著辅助/边缘/交接状态")
    return sorted(states)


def impact_text(row: Mapping[str, Any], temporal_row: Mapping[str, Any]) -> tuple[str, str, str]:
    padding = str(temporal_row.get("padding_reason", "") or temporal_row.get("state_margin_status", "") or "")
    if not padding:
        padding = "未生成目标级时间窗或无 padding 字段。"
    az_margin = str(row.get("azimuth_margin_reason", "") or "无方位余量字段。")
    range_reason = str(row.get("range_margin_reason", "") or row.get("degradation_reason", "") or "")
    if not range_reason:
        range_reason = "缺少运行时安全的目标级距离/深度几何。"
    return padding, az_margin, range_reason


def missing_fields_text(row: Mapping[str, Any]) -> str:
    if str(row.get("spatial_prior_status", "")) == "blocked_missing_object_level_flow":
        return "缺光学目标流：无法形成对象级光学帧-目标框-雷达时间窗映射。"
    if is_true(row.get("blocked")):
        return "对象被 short/noise 或 not-ready 阻断：无正常下游空间先验。"
    if "broad_unknown" in str(row.get("range_prior_mode", "")):
        return "缺运行时安全 per-object range/depth 字段；缺可直接使用的距离向几何收敛信息。"
    return "未发现本轮必须补齐的核心字段。"


def render_object_page(
    row: Mapping[str, Any],
    frame_rows: Sequence[Mapping[str, str]],
    temporal_row: Mapping[str, Any],
    frame_paths: Mapping[tuple[str, int], Path],
    manifest_dirs: Mapping[str, Path],
    out_path: Path,
) -> dict[str, Any]:
    scene = str(row.get("scene", ""))
    object_id = str(row.get("object_hypothesis_id", ""))
    status = status_cn(row)
    color = status_color(status)
    page = Image.new("RGB", (1800, 2100), "#f8fafc")
    draw = ImageDraw.Draw(page)

    draw.text((60, 42), "OTY2 对象级弱空间先验诊断", font=FONTS["title"], fill="#0f172a")
    tag_x = draw_tag(draw, (60, 102), status, color)
    draw_tag(draw, (tag_x, 102), "真实光学帧 + 目标框", "#0f766e")
    draw.text((60, 150), f"场景：{scene}", font=FONTS["h1"], fill="#0f172a")
    draw_wrapped(draw, (60, 188), f"目标编号：{object_id or '场景级说明，无目标流'}", FONTS["body"], "#334155", 1180, max_lines=2)
    draw.text((60, 222), "绿色实线=主观测框；橙色虚线=辅助观测框；右侧雷达部分仅为时间轴和先验示意。", font=FONTS["small"], fill="#475569")

    optical_frames = [safe_int(frame_row.get("optical_frame_num")) for frame_row in frame_rows]
    optical_frames = [frame for frame in optical_frames if frame is not None]
    panel_x = 60
    panel_y = 280
    panel_w = 520
    panel_h = 390
    primary_total = 0
    secondary_total = 0
    existing_frames = 0
    labels = ["起始帧", "中间帧", "结束帧"]
    for idx in range(3):
        x = panel_x + idx * 580
        y = panel_y
        frame_row = frame_rows[idx] if idx < len(frame_rows) else {}
        frame = safe_int(frame_row.get("optical_frame_num"))
        frame_path = resolve_frame_path(scene, frame, frame_paths, manifest_dirs) if frame is not None else None
        draw.text((x, y - 36), f"{labels[idx]}：{'' if frame is None else frame}", font=FONTS["h2"], fill="#0f172a")
        if frame_path and frame_path.exists():
            with Image.open(frame_path) as source:
                panel, pcount, scount = scale_and_draw_boxes(source, (panel_w, panel_h), frame_row)
            page.paste(panel, (x, y))
            primary_total += pcount
            secondary_total += scount
            existing_frames += 1
            draw.text((x, y + panel_h + 10), f"光学帧：{frame_path.name}", font=FONTS["tiny"], fill="#475569")
        else:
            draw.rounded_rectangle((x, y, x + panel_w, y + panel_h), radius=12, fill="#e2e8f0", outline="#94a3b8", width=2)
            draw_wrapped(draw, (x + 22, y + 150), "没有找到可用光学帧；该页只能保留表格字段诊断。", FONTS["body"], "#475569", panel_w - 44, max_lines=3)

    optical_start = min(optical_frames) if optical_frames else safe_int(temporal_row.get("optical_start_frame"))
    optical_end = max(optical_frames) if optical_frames else safe_int(temporal_row.get("optical_end_frame"))
    optical_mid = optical_frames[len(optical_frames) // 2] if optical_frames else None
    sar_start = safe_int(row.get("sar_start_frame"))
    sar_end = safe_int(row.get("sar_end_frame"))
    sar_count = safe_int(row.get("sar_window_frame_count"))
    if sar_count is None and sar_start is not None and sar_end is not None:
        sar_count = sar_end - sar_start + 1

    draw_card(
        draw,
        (60, 735, 790, 270),
        "对象与时间窗",
        [
            f"光学起止帧：{optical_start if optical_start is not None else '无'} -> {optical_end if optical_end is not None else '无'}；中间帧：{optical_mid if optical_mid is not None else '无'}。",
            f"雷达起止帧：{sar_start if sar_start is not None else '未生成'} -> {sar_end if sar_end is not None else '未生成'}；窗口宽度：{sar_count if sar_count is not None else '无'}。",
            f"状态：{status}；spatial_prior_status={row.get('spatial_prior_status', '')}。",
        ],
        border=color,
    )
    draw_timeline(draw, (910, 735, 820, 270), row)

    draw_spatial_canvas(draw, (60, 1040, 790, 450), row)

    state = state_lines(row, frame_rows)
    padding, az_margin, range_reason = impact_text(row, temporal_row)
    draw_card(
        draw,
        (910, 1040, 820, 450),
        "状态如何影响时间窗和空间先验",
        [
            "状态标签：" + "；".join(state[:5]),
            "时间窗余量：" + padding,
            "方位余量：" + az_margin,
            "距离向：" + range_reason,
        ],
        border="#bae6fd",
    )

    az = parse_azimuth(str(row.get("azimuth_center_or_interval", "")))
    az_text = "无"
    if az["start"] != "" and az["end"] != "":
        az_text = f"{float(az['start']):.2f}° 到 {float(az['end']):.2f}°，宽 {float(az['width']):.2f}°"
    draw_card(
        draw,
        (60, 1535, 790, 350),
        "当前弱在哪里",
        [
            f"方位向：{'可用弱先验' if is_true(row.get('azimuth_prior_available')) else '不可用'}；区间 {az_text}。",
            f"距离向：{row.get('range_prior_mode', '') or '未生成'}。核心原因：{missing_fields_text(row)}",
            "时间窗只告诉后续何时看雷达，不直接给在哪里找。",
            "这张图不是最终定位，不是 SAR 候选框，不是自动标注建议。",
        ],
        border="#fde68a",
    )
    draw_card(
        draw,
        (910, 1535, 820, 350),
        "字段不足时的替代说明",
        [
            missing_fields_text(row),
            "不能画真实 SAR 空间位置：本轮不读取 SAR 图像，也没有运行时安全距离向收敛字段。",
            "暂时代替图：真实光学帧 + 框、SAR 时间轴、方位弱先验示意、距离向 broad_unknown 说明。",
        ],
        border="#fecaca",
    )

    draw.text((60, 1950), "边界确认：未读取 SAR 图像，未用 SAR GT，未生成搜索区域/候选框，未评分，未自动标注。", font=FONTS["body"], fill="#0f172a")
    draw.text((60, 1988), f"生成依据：OTY2 已有时间窗与运行时空间先验；光学帧来自本地 optical_frames_dir。", font=FONTS["small"], fill="#475569")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(out_path, format="PNG", optimize=True)

    return {
        "optical_start_frame": "" if optical_start is None else optical_start,
        "optical_mid_frame": "" if optical_mid is None else optical_mid,
        "optical_end_frame": "" if optical_end is None else optical_end,
        "sar_start_frame": "" if sar_start is None else sar_start,
        "sar_end_frame": "" if sar_end is None else sar_end,
        "sar_window_frame_count": "" if sar_count is None else sar_count,
        "has_real_optical_frames": existing_frames == min(3, len(frame_rows)) and existing_frames > 0,
        "primary_boxes_drawn": primary_total,
        "secondary_boxes_drawn": secondary_total,
        "azimuth_interval_deg": az_text,
        "azimuth_width_deg": "" if az["width"] == "" else f"{float(az['width']):.3f}",
        "range_status_cn": "宽未知" if "broad_unknown" in str(row.get("range_prior_mode", "")) else "未生成或其他",
        "weakness_cn": weakness_cn(row),
        "missing_fields_cn": missing_fields_text(row),
        "local_page_path": str(out_path),
    }


def weakness_cn(row: Mapping[str, Any]) -> str:
    if str(row.get("spatial_prior_status", "")) == "blocked_missing_object_level_flow":
        return "目标流缺失导致无法对象级映射"
    if is_true(row.get("blocked")):
        return "对象 not-ready / short-noise 被阻断"
    if "broad_unknown" in str(row.get("range_prior_mode", "")):
        if is_true(row.get("review_only_context")):
            return "距离向宽未知 + 对象含混，仅审阅"
        if str(row.get("spatial_prior_status", "")) == "loose_spatial_prior_generated":
            return "距离向宽未知 + 状态不确定导致宽松先验"
        return "距离向宽未知是主要短板"
    return "弱点不突出"


def render_report(
    timestamp: str,
    summary: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    source_paths: Mapping[str, str],
) -> str:
    scene_lines = []
    for scene, counts in sorted(summary["per_scene_status_counts"].items()):
        scene_lines.append(
            f"| `{scene}` | {counts.get('正常', 0)} | {counts.get('宽松', 0)} | {counts.get('仅审阅', 0)} | {counts.get('阻断', 0) + counts.get('阻断：缺目标流', 0)} |"
        )
    sample_lines = []
    for sample in summary["sample_pages"]:
        sample_lines.append(
            f"| {sample['sample_role']} | `{sample['scene']}` | `{sample['object_hypothesis_id'] or 'scene-only'}` | {sample['status_cn']} | `{sample['repo_sample_path']}` |"
        )
    boundary_lines = "\n".join(f"- {key}: `{str(value).lower()}`" for key, value in BOUNDARY_FLAGS.items())
    return f"""# OTY2 对象级弱空间先验可视化诊断报告

生成时间：`{timestamp}`

本轮修正了上一版偏流程图的问题：现在每个样例页都以**真实光学帧 + 主/辅目标框 + 雷达时间轴 + 空间先验示意**为核心。图内文字以中文解释为主，英文只保留必要字段名。

## 这轮图画了什么

- 本地全量对象页：`{summary['local_page_count']}` 张。
- 远端精选样例页：`{len(summary['sample_pages'])}` 张，放在 `reports/oty2/samples/visualizations/`。
- 每个对象页至少展示起始/中间/结束三个光学帧位置；能找到本地光学帧时直接嵌入真实帧并画主观测框。
- 有辅助观测的帧使用橙色虚线框标出，并在说明区写出它如何扩大时间窗和方位余量。
- SAR 侧没有读取真实 SAR 图，只画时间轴、帧窗口和“方位弱约束 + 距离向宽未知”的示意画布。

## 当前弱空间先验主要弱在哪里

最主要的弱点仍然是**距离向**。当前可进入 normal / relaxed / review-only 的对象都有时间窗，也大多有方位弱先验；但距离向仍是 `broad_unknown_range_prior`，因为当前 OTY2 输入里没有运行时安全的 per-object range/depth 几何字段。

- 方位向：有弱约束，来自光学 bbox / bbox envelope 与配置几何映射；edge、partial、secondary、handoff 会扩大它。
- 距离向：最弱，当前没有可审计的目标级距离收敛信息，所以不能画真实距离位置。
- 目标状态：决定正常、宽松、仅审阅或阻断。它不是评分器，也不是身份真值。
- 时间窗：只限制“何时看雷达”，不直接提供“在哪里找”。
- 场景几何：当前主要起作用的是光学 x 到方位角的弱映射；距离向几何还没真正进入运行时安全输入。

## 每个输入部件的作用

- 主观测：提供对象级连续框，是正常空间先验的核心输入。
- 辅助观测：不证明身份真值；用于暴露 partial / duplicate / handoff / 多观测不确定性，并扩大时间窗或方位余量。
- edge / partial / duplicate / handoff：不直接阻断，优先扩大或放松先验。
- ambiguous / review-only：不混入正常下游输入，只作为审阅上下文。
- short / noise / not-ready：阻断正常空间先验。
- 时间窗：由 24 fps 光学帧与 50 fps 雷达帧的软件同步换算得到，保留抖动和状态余量。
- 场景几何：当前只支持弱方位解释；不足以生成真实 SAR 空间位置。

## 场景统计

| scene | 正常 | 宽松 | 仅审阅 | 阻断 |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(scene_lines)}

## 远端代表样例

| 样例 | scene | object | 状态 | 文件 |
| --- | --- | --- | --- | --- |
{chr(10).join(sample_lines)}

## 哪些对象可以继续往下走

- 可以继续作为下游正常输入：`正常` 和 `宽松` 对象。宽松对象必须携带不确定性说明，不能被当成精确位置。
- 只能审阅：`仅审阅` 对象。它们可作为人工诊断上下文，不进入 normal downstream。
- 被阻断：`阻断` 或 `阻断：缺目标流`。`GM_RM011` 只有时间元数据可用，缺光学目标流，不能生成对象级映射。

## 字段不足与替代图

缺字段：

- 运行时安全的目标级距离/深度字段。
- 能把光学对象转换为 SAR 距离向约束的可审计几何。
- 对 `GM_RM011`，缺目标级光学对象流。

因此不能画：

- 真实 SAR 空间位置。
- SAR 搜索区域。
- SAR 候选框或自动标注。

暂时替代：

- 真实光学帧 + 主/辅框。
- 雷达时间轴 + 当前目标 SAR 帧窗口。
- 方位弱先验示意。
- 距离向 `broad_unknown_range_prior` 的显式说明。

## 下一步建议

优先补强运行时安全的距离向信息：例如场景级 range convention、目标级弱深度/尺度先验、或不依赖 SAR 图像/真值的粗距离分层。第二优先级是把当前单一方位包络拆成多分量或方向性先验，尤其针对 edge / partial / duplicate / handoff 对象。

## 输入来源

- runtime spatial priors: `{source_paths['runtime_spatial_priors']}`
- temporal windows: `{source_paths['temporal_windows']}`
- temporal quality audit: `{source_paths['temporal_quality_audit']}`
- object state stream: `{source_paths['object_frame_states']}`
- optical frames: `{source_paths['optical_manifest']}`

## 输出

- 本地全量目录：`{artifacts['local_output_dir']}`
- 本地对象页目录：`{artifacts['local_pages_dir']}`
- 本地中文报告：`{artifacts['local_report']}`
- 远端报告：`{artifacts['repo_report']}`
- 远端汇总表：`{artifacts['repo_summary_csv']}`
- 远端样例目录：`{artifacts['repo_sample_dir']}`

## Boundary Flags

{boundary_lines}
"""


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    prior_csv = Path(args.runtime_spatial_priors) if args.runtime_spatial_priors else latest_path("oty2_object_runtime_spatial_priors_*.csv")
    temporal_csv = Path(args.temporal_windows) if args.temporal_windows else latest_path("oty2_object_sar_temporal_windows_*.csv")
    quality_csv = Path(args.temporal_quality_audit) if args.temporal_quality_audit else latest_path("oty2_object_sar_temporal_window_quality_audit_*.csv")
    object_states_csv = Path(args.object_frame_states) if args.object_frame_states else DEFAULT_P4G_OUTPUT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"
    manifest_csv = Path(args.optical_manifest)

    priors = read_csv(prior_csv)
    temporal_rows = merge_rows_by_key(read_csv(temporal_csv))
    quality_rows = merge_rows_by_key(read_csv(quality_csv))
    object_states = read_csv(object_states_csv)
    by_object: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for state in object_states:
        by_object[(str(state.get("scene", "")), str(state.get("object_hypothesis_id", "")))].append(state)
    for rows in by_object.values():
        rows.sort(key=lambda row: safe_int(row.get("optical_frame_num"), 0) or 0)

    frame_paths = load_frame_paths(manifest_csv)
    manifest_dirs = load_manifest_frame_dirs(manifest_csv)

    local_output_dir = OUTPUT_PARENT / f"oty2_runtime_spatial_prior_visual_diagnosis_{timestamp}"
    local_pages_dir = local_output_dir / "object_pages"
    local_output_dir.mkdir(parents=True, exist_ok=True)
    local_pages_dir.mkdir(parents=True, exist_ok=True)
    SAMPLE_VIS_DIR.mkdir(parents=True, exist_ok=True)

    sample_lookup = {value: key for key, value in SAMPLE_SELECTION.items()}
    summary_rows: list[dict[str, Any]] = []
    sample_pages: list[dict[str, Any]] = []
    per_scene_status: dict[str, Counter[str]] = defaultdict(Counter)

    for row in priors:
        scene = str(row.get("scene", ""))
        object_id = str(row.get("object_hypothesis_id", ""))
        key = (scene, object_id)
        selected_rows = choose_frame_rows(by_object.get(key, []))
        if not selected_rows and scene and not object_id:
            selected_rows = scene_only_frame_rows(scene, frame_paths, manifest_dirs)

        status = status_cn(row)
        per_scene_status[scene][status] += 1
        page_name = f"oty2_object_diag_{filename_token(scene, object_id)}_{timestamp}.png"
        local_page = local_pages_dir / page_name
        merged_temporal = dict(temporal_rows.get(key, {}))
        merged_temporal.update(quality_rows.get(key, {}))
        page_info = render_object_page(row, selected_rows, merged_temporal, frame_paths, manifest_dirs, local_page)

        sample_role = sample_lookup.get(key, "")
        repo_sample_path = ""
        if sample_role:
            repo_name = f"oty2_object_diag_{SAMPLE_ROLE_SLUG[sample_role]}_{filename_token(scene, object_id)}_{timestamp}.png"
            repo_sample = SAMPLE_VIS_DIR / repo_name
            shutil.copyfile(local_page, repo_sample)
            repo_sample_path = str(repo_sample)
            sample_pages.append(
                {
                    "sample_role": sample_role,
                    "scene": scene,
                    "object_hypothesis_id": object_id,
                    "status_cn": status,
                    "repo_sample_path": repo_sample_path,
                }
            )

        summary_rows.append(
            {
                "scene": scene,
                "object_hypothesis_id": object_id,
                "sample_role": sample_role,
                "status_cn": status,
                "status_code": row.get("spatial_prior_status", ""),
                "edge_partial_state": row.get("edge_or_partial_state", ""),
                "duplicate_handoff_state": row.get("duplicate_or_handoff_state", ""),
                "ambiguity_status": row.get("ambiguity_status", ""),
                "azimuth_prior_available": row.get("azimuth_prior_available", ""),
                "range_prior_mode": row.get("range_prior_mode", ""),
                "repo_sample_path": repo_sample_path,
                **page_info,
            }
        )

    local_summary_csv = local_output_dir / "object_visual_diagnosis_summary.csv"
    local_summary_json = local_output_dir / "object_visual_diagnosis_summary.json"
    local_report = local_output_dir / "object_visual_diagnosis_report.md"
    repo_report = REPORT_DIR / f"oty2_runtime_spatial_prior_visual_diagnosis_report_{timestamp}.md"
    repo_summary_csv = REPORT_DIR / f"oty2_runtime_spatial_prior_visual_summary_{timestamp}.csv"

    artifacts = {
        "local_output_dir": str(local_output_dir),
        "local_pages_dir": str(local_pages_dir),
        "local_summary_csv": str(local_summary_csv),
        "local_summary_json": str(local_summary_json),
        "local_report": str(local_report),
        "repo_report": str(repo_report),
        "repo_summary_csv": str(repo_summary_csv),
        "repo_sample_dir": str(SAMPLE_VIS_DIR),
    }
    source_paths = {
        "runtime_spatial_priors": str(prior_csv),
        "temporal_windows": str(temporal_csv),
        "temporal_quality_audit": str(quality_csv),
        "object_frame_states": str(object_states_csv),
        "optical_manifest": str(manifest_csv),
    }
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": timestamp,
        "stage": "OTY2-object-level-real-optical-visual-diagnosis-v2",
        "local_page_count": len(summary_rows),
        "sample_page_count": len(sample_pages),
        "per_scene_status_counts": {scene: dict(counter) for scene, counter in per_scene_status.items()},
        "sample_pages": sample_pages,
        "source_paths": source_paths,
        "artifacts": artifacts,
        "real_optical_frames_used": True,
        **BOUNDARY_FLAGS,
    }

    write_csv(local_summary_csv, summary_rows, SUMMARY_FIELDS)
    write_csv(repo_summary_csv, summary_rows, SUMMARY_FIELDS)
    write_json(local_summary_json, summary)
    report_text = render_report(timestamp, summary, artifacts, source_paths)
    local_report.write_text(report_text, encoding="utf-8")
    repo_report.write_text(report_text, encoding="utf-8")
    return {"summary": summary, "artifacts": artifacts}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-spatial-priors", default="")
    parser.add_argument("--temporal-windows", default="")
    parser.add_argument("--temporal-quality-audit", default="")
    parser.add_argument("--object-frame-states", default="")
    parser.add_argument("--optical-manifest", default="manifests/oty0_yolo_manifest.csv")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    result = run(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
