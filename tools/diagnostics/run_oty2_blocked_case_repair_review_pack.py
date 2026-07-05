"""Build visual panels for blocked OTY2 optical repair review cases.

The script draws focus boxes and same-frame competing tracker boxes for a small
fixed review set. It only creates ignored diagnostic panels and metadata; it
does not merge tracks, assign identity truth, run SAR support, or create
annotation artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACKLET_INDEX = REPO_ROOT / "outputs" / "oty2" / "tracklet_embedding_aggregation_probe_20260705_193000" / "tracklet_embedding_index.csv"
DEFAULT_LINKAGE_ROWS = REPO_ROOT / "outputs" / "oty2" / "embedding_track_linkage_probe_20260705_183000" / "embedding_track_linkage_rows.csv"
DEFAULT_CROP_INDEX = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500" / "crop_reid_embedding_index.csv"

PANEL_W = 1520
THUMB_W = 275
THUMB_H = 206
CROP_W = 190
CROP_H = 118
MARGIN = 18
HEADER_H = 100
ROW_GAP = 20

FOCUS_COLOR = (235, 30, 30)
COMPETE_COLOR = (30, 100, 235)


@dataclass(frozen=True)
class LinkRow:
    scene: str
    frame_id: int
    track_id: str
    segment_id: str
    embedding_uid: str
    det_id: str
    bbox: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    scene: str
    case_type: str
    segment_a: str
    segment_b: str
    focus_frame: int | None
    title: str
    comparison_case: str


REVIEW_CASES = [
    ReviewCase(
        case_id="GM017_bs0008_blocked",
        scene="GM_RM017",
        case_type="unstable_tracklet",
        segment_a="GM_RM017__botsort__normalized_active__bs_0008__seg_001",
        segment_b="",
        focus_frame=185,
        title="GM_RM017 bs_0008 blocked unstable segment",
        comparison_case="GM_RM017 bs_0010",
    ),
    ReviewCase(
        case_id="GM017_bs0012_blocked",
        scene="GM_RM017",
        case_type="unstable_tracklet",
        segment_a="GM_RM017__botsort__normalized_active__bs_0012__seg_001",
        segment_b="",
        focus_frame=214,
        title="GM_RM017 bs_0012 blocked unstable segment",
        comparison_case="GM_RM017 bs_0010",
    ),
    ReviewCase(
        case_id="GM017_bs0010_repairable_control",
        scene="GM_RM017",
        case_type="repairable_control",
        segment_a="GM_RM017__botsort__normalized_active__bs_0010__seg_001",
        segment_b="",
        focus_frame=200,
        title="GM_RM017 bs_0010 repairable control",
        comparison_case="GM_RM017 bs_0008 / bs_0012",
    ),
    ReviewCase(
        case_id="GM011_bs0061_to_bs0064_blocked",
        scene="GM_RM011",
        case_type="blocked_competition_gap",
        segment_a="GM_RM011__botsort__normalized_active__bs_0061__seg_001",
        segment_b="GM_RM011__botsort__normalized_active__bs_0064__seg_001",
        focus_frame=None,
        title="GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001 blocked competition",
        comparison_case="GM_RM011 bs_0061 seg_002 -> seg_003",
    ),
    ReviewCase(
        case_id="GM011_bs0056_to_bs0061_blocked",
        scene="GM_RM011",
        case_type="blocked_competition_gap",
        segment_a="GM_RM011__botsort__normalized_active__bs_0056__seg_001",
        segment_b="GM_RM011__botsort__normalized_active__bs_0061__seg_001",
        focus_frame=None,
        title="GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001 blocked part/competition",
        comparison_case="GM_RM011 bs_0015 seg_001 -> seg_002",
    ),
    ReviewCase(
        case_id="GM011_bs0015_positive_control",
        scene="GM_RM011",
        case_type="repairable_gap_control",
        segment_a="GM_RM011__botsort__normalized_active__bs_0015__seg_001",
        segment_b="GM_RM011__botsort__normalized_active__bs_0015__seg_002",
        focus_frame=None,
        title="GM_RM011 bs_0015 seg_001 -> seg_002 repairable control",
        comparison_case="GM_RM011 bs_0056 -> bs_0061",
    ),
    ReviewCase(
        case_id="GM011_bs0061_positive_control",
        scene="GM_RM011",
        case_type="repairable_gap_control",
        segment_a="GM_RM011__botsort__normalized_active__bs_0061__seg_002",
        segment_b="GM_RM011__botsort__normalized_active__bs_0061__seg_003",
        focus_frame=None,
        title="GM_RM011 bs_0061 seg_002 -> seg_003 repairable control",
        comparison_case="GM_RM011 bs_0061 seg_001 -> bs_0064",
    ),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader if not duplicate_header(row)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def duplicate_header(row: Mapping[str, Any]) -> bool:
    values = [str(value or "").strip() for value in row.values() if str(value or "").strip()]
    if not values:
        return False
    hits = sum(1 for key, value in row.items() if str(value or "").strip() == key)
    return hits >= max(2, len(values) // 2)


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_int(value: Any) -> int | None:
    text = norm(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_bbox(value: Any) -> tuple[float, float, float, float] | None:
    text = norm(value)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) < 4:
        return None
    try:
        x1, y1, x2, y2 = (float(item) for item in parsed[:4])
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else REPO_ROOT / path


def segment_by_frame(tracklet_rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str, int], str]:
    out: dict[tuple[str, str, int], str] = {}
    for row in tracklet_rows:
        scene = norm(row.get("scene"))
        track_id = norm(row.get("track_id"))
        segment_id = norm(row.get("tracklet_segment_id"))
        start = parse_int(row.get("frame_start"))
        end = parse_int(row.get("frame_end"))
        if not scene or not track_id or not segment_id or start is None or end is None:
            continue
        for frame in range(start, end + 1):
            out[(scene, track_id, frame)] = segment_id
    return out


def load_links(link_rows: Sequence[Mapping[str, str]], seg_map: Mapping[tuple[str, str, int], str]) -> list[LinkRow]:
    out: list[LinkRow] = []
    for row in link_rows:
        if norm(row.get("tracker_name")) != "botsort" or norm(row.get("tracker_variant")) != "normalized_active":
            continue
        scene = norm(row.get("scene"))
        frame = parse_int(row.get("frame_id"))
        track_id = norm(row.get("track_id"))
        if frame is None or not scene or not track_id:
            continue
        segment_id = seg_map.get((scene, track_id, frame), "")
        if not segment_id:
            continue
        out.append(
            LinkRow(
                scene=scene,
                frame_id=frame,
                track_id=track_id,
                segment_id=segment_id,
                embedding_uid=norm(row.get("embedding_row_uid")),
                det_id=norm(row.get("det_id_ignored")),
                bbox=parse_bbox(row.get("tracker_bbox_xyxy")) or parse_bbox(row.get("detection_bbox_xyxy_clamped")),
            )
        )
    return sorted(out, key=lambda item: (item.scene, item.frame_id, item.track_id, item.embedding_uid))


def group_links(links: Sequence[LinkRow]) -> tuple[dict[str, list[LinkRow]], dict[tuple[str, int], list[LinkRow]]]:
    by_segment: dict[str, list[LinkRow]] = defaultdict(list)
    by_frame: dict[tuple[str, int], list[LinkRow]] = defaultdict(list)
    for link in links:
        by_segment[link.segment_id].append(link)
        by_frame[(link.scene, link.frame_id)].append(link)
    for rows in by_segment.values():
        rows.sort(key=lambda item: item.frame_id)
    for rows in by_frame.values():
        rows.sort(key=lambda item: item.track_id)
    return by_segment, by_frame


def crop_map(crop_rows: Sequence[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {norm(row.get("row_uid")): row for row in crop_rows if norm(row.get("row_uid"))}


def select_last(rows: Sequence[LinkRow], count: int) -> list[LinkRow]:
    return list(rows[-count:])


def select_first(rows: Sequence[LinkRow], count: int) -> list[LinkRow]:
    return list(rows[:count])


def select_around(rows: Sequence[LinkRow], focus_frame: int, count: int) -> list[LinkRow]:
    by_frame = {row.frame_id: row for row in rows}
    frames = [frame for frame in range(focus_frame - count + 1, focus_frame + 1) if frame in by_frame]
    if len(frames) < count:
        for row in rows:
            if row.frame_id not in frames:
                frames.insert(0, row.frame_id)
            if len(frames) >= count:
                break
    return [by_frame[frame] for frame in sorted(set(frames))]


def panel_rows_for_case(case: ReviewCase, by_segment: Mapping[str, Sequence[LinkRow]]) -> list[tuple[str, list[LinkRow]]]:
    rows_a = list(by_segment.get(case.segment_a, []))
    rows_b = list(by_segment.get(case.segment_b, [])) if case.segment_b else []
    if case.case_type == "unstable_tracklet":
        if not rows_a:
            return []
        focus = case.focus_frame if case.focus_frame is not None else rows_a[-1].frame_id
        return [
            ("segment start context", select_first(rows_a, 5)),
            ("unstable frame context", select_around(rows_a, focus, 5)),
        ]
    return [
        ("before endpoint", select_last(rows_a, 5)),
        ("after start", select_first(rows_b, 5)),
    ]


def draw_panel(
    case: ReviewCase,
    rows_for_panel: Sequence[tuple[str, Sequence[LinkRow]]],
    by_frame: Mapping[tuple[str, int], Sequence[LinkRow]],
    crops: Mapping[str, Mapping[str, str]],
    out_path: Path,
) -> dict[str, Any]:
    font = ImageFont.load_default()
    row_h = THUMB_H + CROP_H + 62
    height = HEADER_H + len(rows_for_panel) * row_h + max(0, len(rows_for_panel) - 1) * ROW_GAP + MARGIN
    canvas = Image.new("RGB", (PANEL_W, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN, 14), case.title, fill=(20, 20, 20), font=font)
    draw.text((MARGIN, 38), f"red=focus segment, blue=same-frame competing tracker boxes; comparison={case.comparison_case}", fill=(70, 70, 70), font=font)
    draw.text((MARGIN, 62), "Diagnostic panel only: no merge, no final box, no SAR support.", fill=(90, 90, 90), font=font)

    y = HEADER_H
    total_competitors = 0
    for row_label, focus_rows in rows_for_panel:
        draw.text((MARGIN, y), row_label, fill=(20, 20, 20), font=font)
        x = MARGIN
        for focus in focus_rows[:5]:
            competitors = [
                row for row in by_frame.get((focus.scene, focus.frame_id), [])
                if row.segment_id != focus.segment_id and row.bbox is not None
            ]
            total_competitors += len(competitors)
            tile = render_tile(focus, competitors, crops, font)
            canvas.paste(tile, (x, y + 22))
            x += THUMB_W + MARGIN
        y += row_h + ROW_GAP
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)
    return {
        "case_id": case.case_id,
        "scene": case.scene,
        "case_type": case.case_type,
        "segment_a": case.segment_a,
        "segment_b": case.segment_b,
        "panel_path": str(out_path),
        "panel_rows": len(rows_for_panel),
        "focus_frames": ";".join(",".join(str(row.frame_id) for row in rows) for _label, rows in rows_for_panel),
        "competitor_boxes_drawn": total_competitors,
        "comparison_case": case.comparison_case,
    }


def render_tile(
    focus: LinkRow,
    competitors: Sequence[LinkRow],
    crops: Mapping[str, Mapping[str, str]],
    font: ImageFont.ImageFont,
) -> Image.Image:
    tile = Image.new("RGB", (THUMB_W, THUMB_H + CROP_H + 40), "white")
    draw = ImageDraw.Draw(tile)
    crop_row = crops.get(focus.embedding_uid)
    image_path = Path(norm(crop_row.get("optical_path")) if crop_row else "")
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        draw.text((4, 4), f"missing frame {focus.frame_id}", fill=(180, 0, 0), font=font)
        return tile

    boxed = img.copy()
    boxed_draw = ImageDraw.Draw(boxed)
    for competitor in competitors:
        if competitor.bbox is None:
            continue
        boxed_draw.rectangle(competitor.bbox, outline=COMPETE_COLOR, width=3)
        label_at(boxed_draw, competitor.bbox, competitor.track_id, COMPETE_COLOR, font)
    if focus.bbox is not None:
        boxed_draw.rectangle(focus.bbox, outline=FOCUS_COLOR, width=4)
        label_at(boxed_draw, focus.bbox, focus.track_id, FOCUS_COLOR, font)

    tile.paste(fit_image(boxed, THUMB_W, THUMB_H), (0, 18))
    draw.text((4, 2), f"f={focus.frame_id} focus={focus.track_id} comps={len(competitors)}", fill=(0, 0, 0), font=font)
    crop = crop_from_image(img, focus.bbox)
    crop_thumb = fit_image(crop, CROP_W, CROP_H) if crop is not None else Image.new("RGB", (CROP_W, CROP_H), (245, 245, 245))
    tile.paste(crop_thumb, (0, THUMB_H + 28))
    draw.text((0, THUMB_H + CROP_H + 30), focus.det_id[:34], fill=(80, 80, 80), font=font)
    return tile


def label_at(draw: ImageDraw.ImageDraw, bbox: tuple[float, float, float, float], text: str, color: tuple[int, int, int], font: ImageFont.ImageFont) -> None:
    x1, y1, _x2, _y2 = bbox
    draw.rectangle((x1, max(0, y1 - 12), x1 + 58, y1), fill=color)
    draw.text((x1 + 2, max(0, y1 - 12)), text, fill=(255, 255, 255), font=font)


def fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    scale = min(max_w / img.width, max_h / img.height)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    resized = img.resize(new_size)
    out = Image.new("RGB", (max_w, max_h), (248, 248, 248))
    out.paste(resized, ((max_w - resized.width) // 2, (max_h - resized.height) // 2))
    return out


def crop_from_image(img: Image.Image, bbox: tuple[float, float, float, float] | None) -> Image.Image | None:
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(img.width - 1, int(math.floor(x1))))
    y1 = max(0, min(img.height - 1, int(math.floor(y1))))
    x2 = max(x1 + 1, min(img.width, int(math.ceil(x2))))
    y2 = max(y1 + 1, min(img.height, int(math.ceil(y2))))
    return img.crop((x1, y1, x2, y2))


def build_contact_sheet(panel_paths: Sequence[Path], out_path: Path) -> None:
    thumbs: list[Image.Image] = []
    for path in panel_paths:
        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            continue
        thumbs.append(fit_image(img, 460, 305))
    if not thumbs:
        return
    cols = 2
    rows = math.ceil(len(thumbs) / cols)
    canvas = Image.new("RGB", (cols * 480 + 20, rows * 330 + 20), "white")
    for idx, thumb in enumerate(thumbs):
        x = 20 + (idx % cols) * 480
        y = 20 + (idx // cols) * 330
        canvas.paste(thumb, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=90)


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracklet-index", default=str(DEFAULT_TRACKLET_INDEX))
    parser.add_argument("--linkage-rows", default=str(DEFAULT_LINKAGE_ROWS))
    parser.add_argument("--crop-index", default=str(DEFAULT_CROP_INDEX))
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    tracklet_rows = read_csv(resolve(args.tracklet_index))
    linkage_rows = read_csv(resolve(args.linkage_rows))
    crop_rows = read_csv(resolve(args.crop_index))
    seg_map = segment_by_frame(tracklet_rows)
    links = load_links(linkage_rows, seg_map)
    by_segment, by_frame = group_links(links)
    crops = crop_map(crop_rows)

    out_dir = resolve(args.output_root) / "oty2" / f"optical_blocked_case_repair_review_{timestamp}"
    panels_dir = out_dir / "panels"
    metadata_rows: list[dict[str, Any]] = []
    panel_paths: list[Path] = []
    for case in REVIEW_CASES:
        panel_rows = panel_rows_for_case(case, by_segment)
        if not panel_rows:
            continue
        panel_path = panels_dir / f"{case.case_id}.jpg"
        metadata_rows.append(draw_panel(case, panel_rows, by_frame, crops, panel_path))
        panel_paths.append(panel_path)

    metadata_csv = out_dir / "blocked_case_repair_review_panels.csv"
    fields = [
        "case_id",
        "scene",
        "case_type",
        "segment_a",
        "segment_b",
        "panel_path",
        "panel_rows",
        "focus_frames",
        "competitor_boxes_drawn",
        "comparison_case",
    ]
    write_csv(metadata_csv, metadata_rows, fields)
    contact_sheet = out_dir / "blocked_case_repair_review_contact_sheet.jpg"
    build_contact_sheet(panel_paths, contact_sheet)
    metadata = {
        "timestamp": timestamp,
        "branch": git_fact(["branch", "--show-current"]),
        "head": git_fact(["rev-parse", "--short", "HEAD"]),
        "case_count": len(metadata_rows),
        "metadata_csv": str(metadata_csv),
        "contact_sheet": str(contact_sheet),
        "panels_dir": str(panels_dir),
        "boundary": "temporary blocked-case visual review panels only; no merge, no identity truth, no SAR artifact",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
