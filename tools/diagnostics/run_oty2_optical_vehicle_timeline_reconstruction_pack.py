"""Build GM_RM017 optical vehicle timeline reconstruction panels.

This script is a visual-diagnostic helper. It reads existing optical tracker,
crop, and tracklet linkage tables, then draws GM_RM017 frame panels and
track-focused strips under ignored outputs. It does not assign identity truth,
merge tracks, create final annotations, create final boxes, run SAR pairing, or
produce selector/ranking outputs.
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

SCENE = "GM_RM017"
TRACK_IDS = ["bs_0001", "bs_0002", "bs_0008", "bs_0010", "bs_0012"]
CRITICAL_FRAMES = [117, 118, 121, 129, 145, 149, 151, 162, 164, 181, 185, 196, 200, 210, 214]
DENSE_FRAMES = list(range(145, 215, 5))
TRACK_FOCUS_FRAMES = {
    "bs_0001": [118, 126, 136, 146, 156, 164],
    "bs_0002": [121, 123, 125, 127, 129],
    "bs_0008": [145, 146, 147, 148, 149, 181, 182, 183, 184, 185],
    "bs_0010": [151, 160, 170, 181, 196, 197, 198, 199, 200],
    "bs_0012": [162, 163, 164, 165, 166, 210, 211, 212, 213, 214],
}
TRACK_COLORS = {
    "bs_0001": (30, 120, 220),
    "bs_0002": (80, 180, 90),
    "bs_0008": (230, 60, 50),
    "bs_0010": (230, 150, 30),
    "bs_0012": (160, 70, 220),
    "untracked": (120, 120, 120),
}


@dataclass(frozen=True)
class LinkRow:
    scene: str
    frame_id: int
    track_id: str
    segment_id: str
    embedding_uid: str
    det_id: str
    bbox: tuple[float, float, float, float] | None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh) if not duplicate_header(row)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
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


def segment_by_frame(tracklet_rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str, int], str]:
    out: dict[tuple[str, str, int], str] = {}
    for row in tracklet_rows:
        scene = norm(row.get("scene"))
        track_id = norm(row.get("track_id"))
        segment_id = norm(row.get("tracklet_segment_id"))
        start = parse_int(row.get("frame_start"))
        end = parse_int(row.get("frame_end"))
        if scene != SCENE or not track_id or not segment_id or start is None or end is None:
            continue
        for frame_id in range(start, end + 1):
            out[(scene, track_id, frame_id)] = segment_id
    return out


def load_links(link_rows: Sequence[Mapping[str, str]], seg_map: Mapping[tuple[str, str, int], str]) -> list[LinkRow]:
    links: list[LinkRow] = []
    for row in link_rows:
        if norm(row.get("scene")) != SCENE:
            continue
        if norm(row.get("tracker_name")) != "botsort" or norm(row.get("tracker_variant")) != "normalized_active":
            continue
        frame_id = parse_int(row.get("frame_id"))
        if frame_id is None:
            continue
        track_id = norm(row.get("track_id"))
        segment_id = seg_map.get((SCENE, track_id, frame_id), "")
        links.append(
            LinkRow(
                scene=SCENE,
                frame_id=frame_id,
                track_id=track_id,
                segment_id=segment_id,
                embedding_uid=norm(row.get("embedding_row_uid")),
                det_id=norm(row.get("det_id_ignored")),
                bbox=parse_bbox(row.get("tracker_bbox_xyxy")) or parse_bbox(row.get("detection_bbox_xyxy_clamped")),
            )
        )
    return sorted(links, key=lambda item: (item.frame_id, item.track_id, item.embedding_uid))


def crop_map(crop_rows: Sequence[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {norm(row.get("row_uid")): row for row in crop_rows if norm(row.get("scene")) == SCENE and norm(row.get("row_uid"))}


def frame_image_path(frame_id: int, by_frame: Mapping[int, Sequence[LinkRow]], crops: Mapping[str, Mapping[str, str]]) -> Path | None:
    for link in by_frame.get(frame_id, []):
        crop_row = crops.get(link.embedding_uid)
        if crop_row:
            path = Path(norm(crop_row.get("optical_path")))
            if path.exists():
                return path
    return None


def fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    scale = min(max_w / img.width, max_h / img.height)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    resized = img.resize(size)
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


def draw_label(draw: ImageDraw.ImageDraw, bbox: tuple[float, float, float, float], text: str, color: tuple[int, int, int], font: ImageFont.ImageFont) -> None:
    x1, y1, _x2, _y2 = bbox
    label = text or "untracked"
    width = max(58, 7 * len(label))
    y0 = max(0, y1 - 13)
    draw.rectangle((x1, y0, x1 + width, y0 + 13), fill=color)
    draw.text((x1 + 2, y0 + 1), label, fill=(255, 255, 255), font=font)


def draw_frame_tile(frame_id: int, by_frame: Mapping[int, Sequence[LinkRow]], crops: Mapping[str, Mapping[str, str]], font: ImageFont.ImageFont, focus_track: str = "") -> Image.Image:
    tile_w, tile_h = 330, 285
    tile = Image.new("RGB", (tile_w, tile_h), "white")
    draw = ImageDraw.Draw(tile)
    img_path = frame_image_path(frame_id, by_frame, crops)
    if img_path is None:
        draw.text((6, 6), f"missing frame {frame_id}", fill=(180, 0, 0), font=font)
        return tile
    img = Image.open(img_path).convert("RGB")
    boxed = img.copy()
    boxed_draw = ImageDraw.Draw(boxed)
    for link in by_frame.get(frame_id, []):
        if link.bbox is None:
            continue
        track_key = link.track_id if link.track_id in TRACK_COLORS else "untracked"
        color = TRACK_COLORS[track_key]
        width = 5 if focus_track and link.track_id == focus_track else 3
        boxed_draw.rectangle(link.bbox, outline=color, width=width)
        draw_label(boxed_draw, link.bbox, link.track_id or "untracked", color, font)
    tile.paste(fit_image(boxed, tile_w, 246), (0, 18))
    active = ",".join(sorted({link.track_id or "untracked" for link in by_frame.get(frame_id, [])}))
    draw.text((4, 3), f"f={frame_id} tracks={active}", fill=(0, 0, 0), font=font)
    if focus_track:
        focus_links = [link for link in by_frame.get(frame_id, []) if link.track_id == focus_track]
        crop = crop_from_image(img, focus_links[0].bbox) if focus_links else None
        if crop is not None:
            tile.paste(fit_image(crop, 120, 54), (0, 230))
    return tile


def draw_grid_panel(
    title: str,
    frames: Sequence[int],
    by_frame: Mapping[int, Sequence[LinkRow]],
    crops: Mapping[str, Mapping[str, str]],
    out_path: Path,
    focus_track: str = "",
    cols: int = 5,
) -> None:
    font = ImageFont.load_default()
    tile_w, tile_h = 330, 285
    margin = 16
    header_h = 58
    rows = math.ceil(len(frames) / cols)
    canvas = Image.new("RGB", (cols * tile_w + (cols + 1) * margin, header_h + rows * tile_h + (rows + 1) * margin), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 16), title, fill=(20, 20, 20), font=font)
    draw.text((margin, 34), "Diagnostic visual panel only: no GT, no final boxes, no SAR consumption.", fill=(90, 90, 90), font=font)
    for idx, frame_id in enumerate(frames):
        x = margin + (idx % cols) * (tile_w + margin)
        y = header_h + margin + (idx // cols) * (tile_h + margin)
        canvas.paste(draw_frame_tile(frame_id, by_frame, crops, font, focus_track=focus_track), (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def write_track_summary(out_path: Path, tracklet_rows: Sequence[Mapping[str, str]], links: Sequence[LinkRow]) -> None:
    counts: dict[str, int] = defaultdict(int)
    for link in links:
        if link.track_id:
            counts[link.track_id] += 1
    rows: list[dict[str, Any]] = []
    for row in tracklet_rows:
        if norm(row.get("scene")) != SCENE or norm(row.get("track_id")) not in TRACK_IDS:
            continue
        track_id = norm(row.get("track_id"))
        rows.append(
            {
                "scene": SCENE,
                "track_id": track_id,
                "tracklet_segment_id": norm(row.get("tracklet_segment_id")),
                "frame_start": norm(row.get("frame_start")),
                "frame_end": norm(row.get("frame_end")),
                "frame_count": norm(row.get("frame_count")),
                "linked_row_count": counts.get(track_id, 0),
                "intra_tracklet_cosine_mean": norm(row.get("intra_tracklet_cosine_mean")),
                "intra_tracklet_cosine_min": norm(row.get("intra_tracklet_cosine_min")),
                "bbox_motion_dx": norm(row.get("bbox_motion_dx")),
                "bbox_motion_dy": norm(row.get("bbox_motion_dy")),
            }
        )
    write_csv(
        out_path,
        rows,
        [
            "scene",
            "track_id",
            "tracklet_segment_id",
            "frame_start",
            "frame_end",
            "frame_count",
            "linked_row_count",
            "intra_tracklet_cosine_mean",
            "intra_tracklet_cosine_min",
            "bbox_motion_dx",
            "bbox_motion_dy",
        ],
    )


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
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--output-root", default="outputs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    tracklet_rows = read_csv(Path(args.tracklet_index))
    seg_map = segment_by_frame(tracklet_rows)
    links = load_links(read_csv(Path(args.linkage_rows)), seg_map)
    crops = crop_map(read_csv(Path(args.crop_index)))
    by_frame: dict[int, list[LinkRow]] = defaultdict(list)
    for link in links:
        by_frame[link.frame_id].append(link)

    out_dir = REPO_ROOT / args.output_root / "oty2" / f"optical_vehicle_timeline_reconstruction_{timestamp}"
    panels_dir = out_dir / "panels"
    draw_grid_panel(
        "GM_RM017 all normalized_active track ids, critical frames",
        CRITICAL_FRAMES,
        by_frame,
        crops,
        panels_dir / "GM017_all_tracks_critical_frames.jpg",
        cols=5,
    )
    draw_grid_panel(
        "GM_RM017 all normalized_active track ids, dense frames 145-214 step 5",
        DENSE_FRAMES,
        by_frame,
        crops,
        panels_dir / "GM017_all_tracks_dense_frames_145_214.jpg",
        cols=5,
    )
    for track_id, frames in TRACK_FOCUS_FRAMES.items():
        draw_grid_panel(
            f"GM_RM017 {track_id} focus frames",
            frames,
            by_frame,
            crops,
            panels_dir / f"GM017_{track_id}_focus_frames.jpg",
            focus_track=track_id,
            cols=5,
        )
    write_track_summary(out_dir / "GM017_track_summary.csv", tracklet_rows, links)
    metadata = {
        "timestamp": timestamp,
        "scene": SCENE,
        "branch": git_fact(["branch", "--show-current"]),
        "head": git_fact(["rev-parse", "--short", "HEAD"]),
        "track_ids": TRACK_IDS,
        "critical_frames": CRITICAL_FRAMES,
        "dense_frames": DENSE_FRAMES,
        "panels_dir": str(panels_dir),
        "track_summary": str(out_dir / "GM017_track_summary.csv"),
        "boundary": "diagnostic optical timeline panels only; no SAR consumption, no final boxes, no annotation",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
