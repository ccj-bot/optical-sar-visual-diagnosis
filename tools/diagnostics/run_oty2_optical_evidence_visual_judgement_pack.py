"""Build temporary visual review panels for OTY2 optical evidence judgement.

This helper only extracts frames, crops, and candidate metadata for human
visual judgement. It does not merge tracklets, assign identity truth, run SAR
pairing/support, create final boxes, or write annotation artifacts.
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
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACKLET_INDEX = REPO_ROOT / "outputs" / "oty2" / "tracklet_embedding_aggregation_probe_20260705_193000" / "tracklet_embedding_index.csv"
DEFAULT_TRACKLET_EMBEDDINGS = REPO_ROOT / "outputs" / "oty2" / "tracklet_embedding_aggregation_probe_20260705_193000" / "tracklet_embeddings.npz"
DEFAULT_LINKAGE_ROWS = REPO_ROOT / "outputs" / "oty2" / "embedding_track_linkage_probe_20260705_183000" / "embedding_track_linkage_rows.csv"
DEFAULT_CROP_INDEX = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500" / "crop_reid_embedding_index.csv"
DEFAULT_CROP_EMBEDDINGS = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500" / "crop_reid_embeddings.npz"

PANEL_W = 1420
THUMB_W = 260
THUMB_H = 195
CROP_W = 180
CROP_H = 110
MARGIN = 18
HEADER_H = 92
ROW_GAP = 18


@dataclass(frozen=True)
class LinkRow:
    scene: str
    frame_id: int
    track_id: str
    tracklet_segment_id: str
    embedding_row_uid: str
    det_id_ignored: str
    bbox: tuple[float, float, float, float] | None


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [row for row in reader if not duplicate_header_row(row)]
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def duplicate_header_row(row: Mapping[str, Any]) -> bool:
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


def parse_float(value: Any) -> float | None:
    text = norm(value)
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


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


def bbox_center(bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def bbox_size(bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    return x2 - x1, y2 - y1


def resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_npz_array(path: Path, preferred_key: str) -> np.ndarray:
    payload = np.load(path)
    key = preferred_key if preferred_key in payload.files else payload.files[0]
    return payload[key].astype(np.float32, copy=False)


def load_tracklet_embedding_map(index_rows: Sequence[Mapping[str, str]], npz_path: Path) -> dict[str, np.ndarray]:
    payload = np.load(npz_path)
    if "tracklet_embeddings" not in payload.files or "tracklet_segment_ids" not in payload.files:
        raise ValueError(f"Missing tracklet embedding keys in {npz_path}")
    vectors = payload["tracklet_embeddings"].astype(np.float32, copy=False)
    segment_ids = [str(item) for item in payload["tracklet_segment_ids"]]
    if len(segment_ids) != vectors.shape[0]:
        raise ValueError("tracklet segment id count does not match embedding array")
    present = {norm(row.get("tracklet_segment_id")) for row in index_rows if norm(row.get("tracklet_embedding_artifact_path_uncommitted"))}
    return {segment_id: vectors[idx] for idx, segment_id in enumerate(segment_ids) if segment_id in present}


def load_embedding_uid_to_index(crop_index_rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    return {norm(row.get("row_uid")): idx for idx, row in enumerate(crop_index_rows) if norm(row.get("row_uid"))}


def load_crop_path_map(crop_index_rows: Sequence[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {norm(row.get("row_uid")): row for row in crop_index_rows if norm(row.get("row_uid"))}


def attach_segments_to_link_rows(
    linkage_rows: Sequence[Mapping[str, str]],
    tracklet_rows: Sequence[Mapping[str, str]],
    tracker_name: str,
    tracker_variant: str,
) -> list[LinkRow]:
    segments_by_key: dict[tuple[str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in tracklet_rows:
        segments_by_key[(norm(row.get("scene")), norm(row.get("tracker_name")), norm(row.get("track_id")))].append(row)
    for rows in segments_by_key.values():
        rows.sort(key=lambda item: (int(item["frame_start"]), int(item["frame_end"]), norm(item.get("tracklet_segment_id"))))

    out: list[LinkRow] = []
    for row in linkage_rows:
        scene = norm(row.get("scene"))
        if norm(row.get("tracker_name")) != tracker_name or norm(row.get("tracker_variant")) != tracker_variant:
            continue
        frame = parse_int(row.get("frame_id"))
        track_id = norm(row.get("track_id"))
        if frame is None or not track_id:
            continue
        segment_id = ""
        for seg in segments_by_key.get((scene, tracker_name, track_id), []):
            start = int(seg["frame_start"])
            end = int(seg["frame_end"])
            if start <= frame <= end:
                segment_id = norm(seg.get("tracklet_segment_id"))
                break
        if not segment_id:
            continue
        out.append(
            LinkRow(
                scene=scene,
                frame_id=frame,
                track_id=track_id,
                tracklet_segment_id=segment_id,
                embedding_row_uid=norm(row.get("embedding_row_uid")),
                det_id_ignored=norm(row.get("det_id_ignored")),
                bbox=parse_bbox(row.get("tracker_bbox_xyxy")) or parse_bbox(row.get("detection_bbox_xyxy_clamped")),
            )
        )
    return sorted(out, key=lambda item: (item.scene, item.track_id, item.frame_id, item.embedding_row_uid))


def rows_by_segment(link_rows: Sequence[LinkRow]) -> dict[str, list[LinkRow]]:
    grouped: dict[str, list[LinkRow]] = defaultdict(list)
    for row in link_rows:
        grouped[row.tracklet_segment_id].append(row)
    return {key: sorted(rows, key=lambda item: item.frame_id) for key, rows in grouped.items()}


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return float("nan")
    value = float(np.dot(a, b))
    return value if math.isfinite(value) else float("nan")


def sample_context_frames(rows: Sequence[LinkRow], focus_frame: int, radius: int) -> list[LinkRow]:
    by_frame: dict[int, LinkRow] = {}
    for row in rows:
        by_frame.setdefault(row.frame_id, row)
    selected = [by_frame[frame] for frame in range(focus_frame - radius, focus_frame + radius + 1) if frame in by_frame]
    for row in (rows[0], rows[-1]):
        if row not in selected:
            selected.append(row)
    return sorted(selected, key=lambda item: item.frame_id)


def nearest_rows(rows: Sequence[LinkRow], frame: int, count: int, before: bool) -> list[LinkRow]:
    if before:
        eligible = [row for row in rows if row.frame_id <= frame]
        return eligible[-count:]
    eligible = [row for row in rows if row.frame_id >= frame]
    return eligible[:count]


def draw_panel(
    title: str,
    subtitle: str,
    panel_rows: Sequence[tuple[str, Sequence[LinkRow]]],
    crop_map: Mapping[str, Mapping[str, str]],
    output_path: Path,
) -> None:
    font = ImageFont.load_default()
    row_h = THUMB_H + CROP_H + 58
    width = PANEL_W
    height = HEADER_H + len(panel_rows) * row_h + max(0, len(panel_rows) - 1) * ROW_GAP + MARGIN
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN, 16), title, fill=(20, 20, 20), font=font)
    draw.text((MARGIN, 42), subtitle, fill=(70, 70, 70), font=font)
    y = HEADER_H
    for row_label, frames in panel_rows:
        draw.text((MARGIN, y), row_label, fill=(20, 20, 20), font=font)
        x = MARGIN
        for item in frames[:5]:
            tile = render_frame_tile(item, crop_map, font)
            canvas.paste(tile, (x, y + 20))
            x += THUMB_W + MARGIN
        y += row_h + ROW_GAP
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=92)


def render_frame_tile(item: LinkRow, crop_map: Mapping[str, Mapping[str, str]], font: ImageFont.ImageFont) -> Image.Image:
    tile = Image.new("RGB", (THUMB_W, THUMB_H + CROP_H + 36), "white")
    draw = ImageDraw.Draw(tile)
    crop_row = crop_map.get(item.embedding_row_uid)
    image_path = Path(norm(crop_row.get("optical_path")) if crop_row else "")
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        draw.text((4, 4), f"missing frame {item.frame_id}", fill=(180, 0, 0), font=font)
        return tile

    img_boxed = img.copy()
    if item.bbox is not None:
        ImageDraw.Draw(img_boxed).rectangle(item.bbox, outline=(255, 0, 0), width=4)
    img_thumb = fit_image(img_boxed, THUMB_W, THUMB_H)
    tile.paste(img_thumb, (0, 18))
    draw.text((4, 2), f"f={item.frame_id} {item.track_id}", fill=(0, 0, 0), font=font)

    crop = crop_from_image(img, item.bbox)
    crop_thumb = fit_image(crop, CROP_W, CROP_H) if crop is not None else Image.new("RGB", (CROP_W, CROP_H), (245, 245, 245))
    tile.paste(crop_thumb, (0, THUMB_H + 26))
    draw.text((0, THUMB_H + CROP_H + 28), item.det_id_ignored[:32], fill=(80, 80, 80), font=font)
    return tile


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


def segment_status(row: Mapping[str, str]) -> str:
    linked = int(float(norm(row.get("linked_embedding_count")) or 0))
    min_cos = parse_float(row.get("intra_tracklet_cosine_min"))
    if linked <= 0:
        return "no_embedding"
    if linked < 2:
        return "short_segment"
    if min_cos is not None and min_cos < 0.70:
        return "unstable_appearance"
    return "ready"


def choose_gm017_unstable_cases(
    tracklet_rows: Sequence[Mapping[str, str]],
    segment_rows: Mapping[str, Sequence[LinkRow]],
    segment_embeddings: Mapping[str, np.ndarray],
    crop_features: np.ndarray,
    uid_to_index: Mapping[str, int],
    crop_map: Mapping[str, Mapping[str, str]],
    panels_dir: Path,
    context_radius: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for row in tracklet_rows:
        if norm(row.get("scene")) != "GM_RM017" or segment_status(row) != "unstable_appearance":
            continue
        seg_id = norm(row.get("tracklet_segment_id"))
        aggregate = segment_embeddings.get(seg_id)
        rows = list(segment_rows.get(seg_id, []))
        if aggregate is None or not rows:
            continue
        frame_scores: list[tuple[float, LinkRow]] = []
        for link in rows:
            idx = uid_to_index.get(link.embedding_row_uid)
            if idx is None or idx >= crop_features.shape[0]:
                continue
            frame_scores.append((cosine(crop_features[idx], aggregate), link))
        if not frame_scores:
            continue
        min_score, min_row = min(frame_scores, key=lambda item: item[0])
        selected = sample_context_frames(rows, min_row.frame_id, context_radius)
        panel_path = panels_dir / f"GM_RM017_unstable_{seg_id}.jpg"
        draw_panel(
            title=f"GM_RM017 unstable segment: {seg_id}",
            subtitle=f"track={row.get('track_id')} frames={row.get('frame_start')}-{row.get('frame_end')} min_cosine={min_score:.6f}",
            panel_rows=[("min-cosine context", selected)],
            crop_map=crop_map,
            output_path=panel_path,
        )
        bbox_sizes = [bbox_size(link.bbox) for link in rows if bbox_size(link.bbox) is not None]
        widths = [size[0] for size in bbox_sizes]
        heights = [size[1] for size in bbox_sizes]
        cases.append(
            {
                "case_type": "gm017_unstable_segment",
                "scene": "GM_RM017",
                "segment_a": seg_id,
                "segment_b": "",
                "track_a": row.get("track_id", ""),
                "track_b": "",
                "frame_a": min_row.frame_id,
                "frame_b": "",
                "gap_frames": "",
                "appearance_cosine": "",
                "intra_min_cosine": f"{min_score:.6f}",
                "spatial_distance_px": "",
                "distance_norm": "",
                "panel_path": str(panel_path),
                "auto_reason": "lowest intra-tracklet cosine frame plus local context",
                "bbox_w_range": range_text(widths),
                "bbox_h_range": range_text(heights),
                "optical_path_a": norm(crop_map.get(min_row.embedding_row_uid, {}).get("optical_path")),
                "optical_path_b": "",
            }
        )
    return cases


def range_text(values: Sequence[float]) -> str:
    if not values:
        return ""
    return f"{min(values):.1f}-{max(values):.1f}"


def center_from_tracklet(row: Mapping[str, str], suffix: str) -> tuple[float, float] | None:
    x = parse_float(row.get(f"bbox_center_x_{suffix}"))
    y = parse_float(row.get(f"bbox_center_y_{suffix}"))
    if x is None or y is None:
        return None
    return x, y


def mean_diag(row_a: Mapping[str, str], row_b: Mapping[str, str]) -> float:
    widths = [parse_float(row_a.get("bbox_w_mean")), parse_float(row_b.get("bbox_w_mean"))]
    heights = [parse_float(row_a.get("bbox_h_mean")), parse_float(row_b.get("bbox_h_mean"))]
    w = sum(item for item in widths if item is not None) / max(1, sum(item is not None for item in widths))
    h = sum(item for item in heights if item is not None) / max(1, sum(item is not None for item in heights))
    return math.hypot(w, h) if w and h else 1.0


def candidate_metrics(
    row_a: Mapping[str, str],
    row_b: Mapping[str, str],
    segment_embeddings: Mapping[str, np.ndarray],
) -> dict[str, Any] | None:
    end_a = parse_int(row_a.get("frame_end"))
    start_b = parse_int(row_b.get("frame_start"))
    if end_a is None or start_b is None or start_b <= end_a:
        return None
    seg_a = norm(row_a.get("tracklet_segment_id"))
    seg_b = norm(row_b.get("tracklet_segment_id"))
    vec_a = segment_embeddings.get(seg_a)
    vec_b = segment_embeddings.get(seg_b)
    if vec_a is None or vec_b is None:
        return None
    ca = center_from_tracklet(row_a, "end")
    cb = center_from_tracklet(row_b, "start")
    if ca is None or cb is None:
        return None
    dist = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    diag = mean_diag(row_a, row_b)
    return {
        "gap": start_b - end_a,
        "appearance": cosine(vec_a, vec_b),
        "distance": dist,
        "distance_norm": dist / diag if diag > 0 else dist,
    }


def choose_gm011_breakpoint_cases(
    tracklet_rows: Sequence[Mapping[str, str]],
    segment_rows: Mapping[str, Sequence[LinkRow]],
    segment_embeddings: Mapping[str, np.ndarray],
    crop_map: Mapping[str, Mapping[str, str]],
    panels_dir: Path,
    max_gap: int,
) -> list[dict[str, Any]]:
    gm_rows = [row for row in tracklet_rows if norm(row.get("scene")) == "GM_RM011" and segment_status(row) == "ready"]
    gm_rows.sort(key=lambda row: (int(row["frame_start"]), int(row["frame_end"]), norm(row.get("tracklet_segment_id"))))
    candidate_rows: list[tuple[str, Mapping[str, str], Mapping[str, str], dict[str, Any]]] = []
    for row_a in gm_rows:
        for row_b in gm_rows:
            metrics = candidate_metrics(row_a, row_b, segment_embeddings)
            if metrics is None or metrics["gap"] > max_gap:
                continue
            same_track = norm(row_a.get("track_id")) == norm(row_b.get("track_id"))
            if same_track:
                category = "same_track_short_gap_candidate"
            elif metrics["appearance"] >= 0.90 and metrics["distance_norm"] <= 1.35:
                category = "cross_track_strong_candidate"
            elif metrics["appearance"] >= 0.90 and metrics["distance_norm"] > 2.25:
                category = "appearance_similar_spatial_counterexample"
            elif metrics["distance_norm"] <= 1.10 and metrics["appearance"] < 0.82:
                category = "spatial_near_appearance_counterexample"
            else:
                continue
            candidate_rows.append((category, row_a, row_b, metrics))

    selected: list[tuple[str, Mapping[str, str], Mapping[str, str], dict[str, Any]]] = []
    limits = {
        "same_track_short_gap_candidate": 4,
        "cross_track_strong_candidate": 4,
        "appearance_similar_spatial_counterexample": 4,
        "spatial_near_appearance_counterexample": 3,
    }
    sort_key = lambda item: (item[3]["gap"], -item[3]["appearance"], item[3]["distance_norm"])
    for category, limit in limits.items():
        rows = [item for item in candidate_rows if item[0] == category]
        rows.sort(key=sort_key)
        selected.extend(rows[:limit])

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for idx, (category, row_a, row_b, metrics) in enumerate(selected, start=1):
        seg_a = norm(row_a.get("tracklet_segment_id"))
        seg_b = norm(row_b.get("tracklet_segment_id"))
        key = (category, seg_a, seg_b)
        if key in seen:
            continue
        seen.add(key)
        rows_a = list(segment_rows.get(seg_a, []))
        rows_b = list(segment_rows.get(seg_b, []))
        if not rows_a or not rows_b:
            continue
        before = nearest_rows(rows_a, int(row_a["frame_end"]), 3, before=True)
        after = nearest_rows(rows_b, int(row_b["frame_start"]), 3, before=False)
        panel_path = panels_dir / f"GM_RM011_breakpoint_{idx:02d}_{category}_{short_segment_name(seg_a)}_TO_{short_segment_name(seg_b)}.jpg"
        draw_panel(
            title=f"GM_RM011 breakpoint: {category}",
            subtitle=f"{seg_a} -> {seg_b}; gap={metrics['gap']} app={metrics['appearance']:.3f} dist_norm={metrics['distance_norm']:.3f}",
            panel_rows=[("before endpoint", before), ("after start", after)],
            crop_map=crop_map,
            output_path=panel_path,
        )
        out.append(
            {
                "case_type": category,
                "scene": "GM_RM011",
                "segment_a": seg_a,
                "segment_b": seg_b,
                "track_a": row_a.get("track_id", ""),
                "track_b": row_b.get("track_id", ""),
                "frame_a": row_a.get("frame_end", ""),
                "frame_b": row_b.get("frame_start", ""),
                "gap_frames": metrics["gap"],
                "appearance_cosine": f"{metrics['appearance']:.6f}",
                "intra_min_cosine": "",
                "spatial_distance_px": f"{metrics['distance']:.3f}",
                "distance_norm": f"{metrics['distance_norm']:.6f}",
                "panel_path": str(panel_path),
                "auto_reason": auto_reason(category),
                "bbox_w_range": "",
                "bbox_h_range": "",
                "optical_path_a": norm(crop_map.get(before[-1].embedding_row_uid, {}).get("optical_path")) if before else "",
                "optical_path_b": norm(crop_map.get(after[0].embedding_row_uid, {}).get("optical_path")) if after else "",
            }
        )
    return out


def auto_reason(category: str) -> str:
    return {
        "same_track_short_gap_candidate": "same tracker id split by a short frame gap; requires visual box-continuity check",
        "cross_track_strong_candidate": "appearance, temporal order, and endpoint distance are jointly plausible",
        "appearance_similar_spatial_counterexample": "appearance is high but endpoint spatial displacement is large",
        "spatial_near_appearance_counterexample": "endpoint distance is close but appearance support is weak",
    }.get(category, category)


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[-80:]


def short_segment_name(segment_id: str) -> str:
    parts = segment_id.split("__")
    if len(parts) >= 5:
        return safe_name(f"{parts[0]}_{parts[3]}_{parts[4]}")
    return safe_name(segment_id)[-48:]


def build_contact_sheet(panel_paths: Sequence[Path], output_path: Path) -> None:
    thumbs: list[Image.Image] = []
    for path in panel_paths:
        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            continue
        thumbs.append(fit_image(img, 380, 260))
    if not thumbs:
        return
    cols = 2
    rows = math.ceil(len(thumbs) / cols)
    canvas = Image.new("RGB", (cols * 400 + 20, rows * 282 + 20), "white")
    for idx, thumb in enumerate(thumbs):
        x = 20 + (idx % cols) * 400
        y = 20 + (idx // cols) * 282
        canvas.paste(thumb, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=90)


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracklet-index", default=str(DEFAULT_TRACKLET_INDEX))
    parser.add_argument("--tracklet-embeddings", default=str(DEFAULT_TRACKLET_EMBEDDINGS))
    parser.add_argument("--linkage-rows", default=str(DEFAULT_LINKAGE_ROWS))
    parser.add_argument("--crop-index", default=str(DEFAULT_CROP_INDEX))
    parser.add_argument("--crop-embeddings", default=str(DEFAULT_CROP_EMBEDDINGS))
    parser.add_argument("--tracker-name", default="botsort")
    parser.add_argument("--tracker-variant", default="normalized_active")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--gm017-context-radius", type=int, default=3)
    parser.add_argument("--gm011-max-gap", type=int, default=20)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    tracklet_index = resolve(args.tracklet_index)
    tracklet_embeddings_path = resolve(args.tracklet_embeddings)
    linkage_path = resolve(args.linkage_rows)
    crop_index_path = resolve(args.crop_index)
    crop_embeddings_path = resolve(args.crop_embeddings)
    for path in (tracklet_index, tracklet_embeddings_path, linkage_path, crop_index_path, crop_embeddings_path):
        if not path.exists():
            raise FileNotFoundError(path)

    tracklet_rows, _ = read_csv(tracklet_index)
    linkage_rows, _ = read_csv(linkage_path)
    crop_index_rows, _ = read_csv(crop_index_path)
    crop_features = load_npz_array(crop_embeddings_path, "features")
    segment_embeddings = load_tracklet_embedding_map(tracklet_rows, tracklet_embeddings_path)
    uid_to_index = load_embedding_uid_to_index(crop_index_rows)
    crop_map = load_crop_path_map(crop_index_rows)
    link_rows = attach_segments_to_link_rows(linkage_rows, tracklet_rows, args.tracker_name, args.tracker_variant)
    grouped_segments = rows_by_segment(link_rows)

    out_dir = resolve(args.output_root) / "oty2" / f"optical_evidence_visual_judgement_{timestamp}"
    panels_dir = out_dir / "panels"
    gm017_cases = choose_gm017_unstable_cases(
        tracklet_rows=tracklet_rows,
        segment_rows=grouped_segments,
        segment_embeddings=segment_embeddings,
        crop_features=crop_features,
        uid_to_index=uid_to_index,
        crop_map=crop_map,
        panels_dir=panels_dir,
        context_radius=args.gm017_context_radius,
    )
    gm011_cases = choose_gm011_breakpoint_cases(
        tracklet_rows=tracklet_rows,
        segment_rows=grouped_segments,
        segment_embeddings=segment_embeddings,
        crop_map=crop_map,
        panels_dir=panels_dir,
        max_gap=args.gm011_max_gap,
    )
    all_cases = [*gm017_cases, *gm011_cases]
    fields = [
        "case_type",
        "scene",
        "segment_a",
        "segment_b",
        "track_a",
        "track_b",
        "frame_a",
        "frame_b",
        "gap_frames",
        "appearance_cosine",
        "intra_min_cosine",
        "spatial_distance_px",
        "distance_norm",
        "bbox_w_range",
        "bbox_h_range",
        "auto_reason",
        "panel_path",
        "optical_path_a",
        "optical_path_b",
    ]
    review_csv = out_dir / "optical_evidence_visual_judgement_review_cases.csv"
    write_csv(review_csv, all_cases, fields)
    panel_paths = [Path(norm(row.get("panel_path"))) for row in all_cases if norm(row.get("panel_path"))]
    contact_sheet = out_dir / "optical_evidence_visual_judgement_contact_sheet.jpg"
    build_contact_sheet(panel_paths, contact_sheet)
    metadata = {
        "timestamp": timestamp,
        "branch": git_fact(["branch", "--show-current"]),
        "head": git_fact(["rev-parse", "--short", "HEAD"]),
        "review_csv": str(review_csv),
        "contact_sheet": str(contact_sheet),
        "panels_dir": str(panels_dir),
        "cases_total": len(all_cases),
        "gm017_unstable_cases": len(gm017_cases),
        "gm011_breakpoint_cases": len(gm011_cases),
        "boundary": "temporary visual judgement panels only; no final annotation, no identity truth, no SAR support artifact",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
