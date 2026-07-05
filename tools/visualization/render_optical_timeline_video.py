"""Render OTY2 optical timeline frames from a diagnostic render manifest.

This is an interface helper for visualization only. It reads a manifest created
by run_oty2_optical_timeline_graph_manifest.py and writes rendered frames, plus
an mp4 when OpenCV is available. It skips forbidden and non-vehicle manifest
rows by default.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRAME_ROOT = Path("D:/profile/research/data")

COLORS = {
    "strong_timeline": (20, 130, 60),
    "weak_timeline": (230, 150, 30),
    "review_only": (140, 80, 210),
    "partial_visible": (30, 120, 220),
    "edge_contact": (210, 80, 60),
}
SKIP_STATUSES = {"forbidden_not_rendered", "non_vehicle_not_rendered"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh)]


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_int(value: Any) -> int | None:
    try:
        return int(float(norm(value)))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    try:
        return float(norm(value))
    except ValueError:
        return None


def load_frame_table(path: Path | None) -> dict[tuple[str, int], Path]:
    if path is None:
        return {}
    out: dict[tuple[str, int], Path] = {}
    for row in read_csv(path):
        frame = parse_int(row.get("optical_frame_num"))
        scene = norm(row.get("scene"))
        optical_path = norm(row.get("optical_path"))
        if scene and frame is not None and optical_path:
            out[(scene, frame)] = Path(optical_path)
    return out


def frame_path(scene: str, frame: int, frame_root: Path, frame_table: Mapping[tuple[str, int], Path]) -> Path:
    table_path = frame_table.get((scene, frame))
    if table_path:
        return table_path
    return frame_root / scene / f"{scene}_frames" / f"{frame:06d}.png"


def label_width(text: str) -> int:
    return max(80, 7 * len(text) + 12)


def draw_rows(img: Image.Image, rows: Sequence[Mapping[str, str]], font: ImageFont.ImageFont, show_track_id: bool) -> Image.Image:
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for row in rows:
        status = norm(row.get("display_status"))
        if status in SKIP_STATUSES:
            continue
        values = [parse_float(row.get(key)) for key in ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2")]
        if any(value is None for value in values):
            continue
        x1, y1, x2, y2 = (float(value) for value in values if value is not None)
        if x2 <= x1 or y2 <= y1:
            continue
        color = COLORS.get(status, (220, 80, 60))
        draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
        label = norm(row.get("display_label")) or norm(row.get("diagnostic_vehicle_id"))
        if show_track_id:
            label = f"{label} {norm(row.get('source_track_id'))}"
        if status in {"weak_timeline", "review_only"}:
            label = f"{label} {status}"
        y0 = max(0, y1 - 16)
        draw.rectangle((x1, y0, x1 + label_width(label), y0 + 16), fill=color)
        draw.text((x1 + 4, y0 + 2), label, fill=(255, 255, 255), font=font)
    return out


def try_write_mp4(frame_paths: Sequence[Path], output_mp4: Path, fps: float) -> bool:
    try:
        import cv2  # type: ignore
    except Exception:
        return False
    if not frame_paths:
        return False
    first = cv2.imread(str(frame_paths[0]))
    if first is None:
        return False
    height, width = first.shape[:2]
    writer = cv2.VideoWriter(str(output_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    try:
        for path in frame_paths:
            frame = cv2.imread(str(path))
            if frame is None:
                continue
            writer.write(frame)
    finally:
        writer.release()
    return output_mp4.exists()


def render(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    rows = read_csv(manifest_path)
    if args.scene:
        rows = [row for row in rows if norm(row.get("scene")) == args.scene]
    frame_table = load_frame_table(Path(args.frame_table) if args.frame_table else None)
    frame_root = Path(args.frame_root)
    grouped: dict[tuple[str, int], list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        frame = parse_int(row.get("optical_frame_num"))
        scene = norm(row.get("scene"))
        if scene and frame is not None:
            grouped[(scene, frame)].append(row)

    output_dir = Path(args.output_dir)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    written: list[Path] = []
    for scene, frame in sorted(grouped):
        source_path = frame_path(scene, frame, frame_root, frame_table)
        if not source_path.exists():
            print(f"missing frame: {source_path}")
            continue
        img = Image.open(source_path)
        rendered = draw_rows(img, grouped[(scene, frame)], font, args.show_track_id)
        out_path = frames_dir / f"{scene}_{frame:06d}.png"
        rendered.save(out_path)
        written.append(out_path)

    if args.mp4 and written:
        mp4_path = output_dir / args.mp4
        ok = try_write_mp4(written, mp4_path, float(args.fps))
        if not ok:
            print("mp4 not written; OpenCV unavailable or failed. Frame sequence is available.")
    print(f"rendered_frames: {len(written)}")
    print(f"frames_dir: {frames_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Video render manifest CSV.")
    parser.add_argument("--output-dir", required=True, help="Output directory under outputs/ for rendered frames/mp4.")
    parser.add_argument("--scene", default="", help="Optional scene filter.")
    parser.add_argument("--frame-root", default=str(DEFAULT_FRAME_ROOT), help="Root containing <scene>/<scene>_frames/*.png")
    parser.add_argument("--frame-table", default="", help="Optional CSV with scene,optical_frame_num,optical_path.")
    parser.add_argument("--fps", default="8")
    parser.add_argument("--mp4", default="", help="Optional mp4 filename, e.g. timeline.mp4.")
    parser.add_argument("--show-track-id", action="store_true", help="Display track id as auxiliary text.")
    return parser.parse_args()


def main() -> None:
    render(parse_args())


if __name__ == "__main__":
    main()
