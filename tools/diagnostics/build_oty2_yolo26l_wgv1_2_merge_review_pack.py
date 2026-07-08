#!/usr/bin/env python
"""Build a diagnostic vehicle-centric merge review pack for WGV1.2.

The pack renders per-frame YOLO26l diagnostic candidate overlays for the
same-vehicle merge review queue. It is for human review only: no final boxes,
no revised annotations, no GT boxes, no SAR-ready evidence, and no tracker
replay.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"
REPORTS_DIR = REPO_ROOT / "reports/oty2"

DEFAULT_REVIEW_QUEUE = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_same_vehicle_merge_review_queue_20260708.csv"
DEFAULT_BANK = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv"
DEFAULT_TARGET_FAMILIES = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs/oty2/y26l_wgv1_2_vehicle_centric_merge_review_20260708"
DEFAULT_DATA_ROOT = Path("D:/profile/research/data")
DEFAULT_REPORT = REPORTS_DIR / "oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_20260708.md"
DEFAULT_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_manifest_20260708.csv"
DEFAULT_FRAME_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_frame_manifest_20260708.csv"

FRAME_MANIFEST_FIELDS = [
    "review_item_id",
    "merge_candidate_id",
    "scene_id",
    "frame_id",
    "phase",
    "from_target_family_id",
    "to_target_family_id",
    "selected_primary_count",
    "competing_candidate_count",
    "other_selected_primary_count",
    "raw_candidate_count",
    "annotated_frame_path",
    "source_frame_path",
    "human_question",
    "sar_ready",
    "note",
]

ITEM_MANIFEST_FIELDS = [
    "review_item_id",
    "merge_candidate_id",
    "scene_id",
    "from_target_family_id",
    "from_frame_start",
    "from_frame_end",
    "to_target_family_id",
    "to_frame_start",
    "to_frame_end",
    "frame_start",
    "frame_end",
    "frame_count",
    "selected_primary_frames",
    "competing_candidate_frames",
    "detectionless_frames",
    "folder_path",
    "human_question",
    "auto_merge_allowed",
    "sar_ready",
    "note",
]

COLORS = {
    "from_selected": (0, 220, 70),
    "to_selected": (0, 180, 255),
    "other_selected": (170, 90, 255),
    "competing": (255, 150, 0),
}


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


def frame_path(data_root: Path, scene_id: str, frame_id: int) -> Path:
    return data_root / scene_id / f"{scene_id}_frames" / f"{frame_id:06d}.png"


def safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text)


def target_set(value: str) -> set[str]:
    return {part for part in (value or "").split(";") if part}


def candidate_kind(row: dict[str, str], from_tf: str, to_tf: str) -> str:
    linked = target_set(row.get("linked_target_family_ids", ""))
    if from_tf in linked:
        return "from_selected"
    if to_tf in linked:
        return "to_selected"
    if row.get("candidate_role") == "selected_primary":
        return "other_selected"
    return "competing"


def phase_for_frame(frame_id: int, item: dict[str, str]) -> str:
    from_start = as_int(item["from_frame_start"])
    from_end = as_int(item["from_frame_end"])
    to_start = as_int(item["to_frame_start"])
    to_end = as_int(item["to_frame_end"])
    if from_start <= frame_id <= from_end:
        return "from_target_family"
    if to_start <= frame_id <= to_end:
        return "to_target_family"
    return "gap_context"


def draw_label(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, color: tuple[int, int, int]) -> None:
    x, y = xy
    font = ImageFont.load_default()
    bbox = draw.textbbox((x, y), text, font=font)
    pad = 2
    bg = (0, 0, 0)
    draw.rectangle((bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad), fill=bg)
    draw.text((x, y), text, fill=color, font=font)


def draw_frame(
    source_path: Path,
    out_path: Path,
    rows: list[dict[str, str]],
    item: dict[str, str],
    frame_id: int,
) -> None:
    image = Image.open(source_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    from_tf = item["from_target_family_id"]
    to_tf = item["to_target_family_id"]
    header = (
        f"{item['review_item_id']} {item['scene_id']} frame={frame_id} "
        f"YOLO26l diagnostic candidates NOT FINAL NOT SAR-READY"
    )
    draw.rectangle((0, 0, image.width, 22), fill=(0, 0, 0))
    draw.text((4, 5), header, fill=(255, 255, 255), font=ImageFont.load_default())

    for idx, row in enumerate(rows, start=1):
        kind = candidate_kind(row, from_tf, to_tf)
        color = COLORS[kind]
        x1 = float(row["bbox_x1"])
        y1 = float(row["bbox_y1"])
        x2 = float(row["bbox_x2"])
        y2 = float(row["bbox_y2"])
        width = 4 if kind in {"from_selected", "to_selected"} else 2
        draw.rectangle((x1, y1, x2, y2), outline=color, width=width)
        label = (
            f"{idx}:{kind} {row['class_name']} conf={float(row['confidence']):.2f} "
            f"{row['source_detection_id']} x={row['x_bin']}"
        )
        draw_label(draw, (max(0, x1), max(24, y1 - 14)), label, color)

    legend = [
        ("from_selected", COLORS["from_selected"]),
        ("to_selected", COLORS["to_selected"]),
        ("other_selected", COLORS["other_selected"]),
        ("competing", COLORS["competing"]),
    ]
    y = image.height - 18 * len(legend) - 4
    for label, color in legend:
        draw_label(draw, (4, y), label, color)
        y += 18

    if not rows:
        draw_label(draw, (20, 40), "NO YOLO26l candidate row in raw table for this frame", (255, 80, 80))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def rows_for_frame(bank_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]], scene_id: str, frame_id: int) -> list[dict[str, str]]:
    return sorted(
        bank_by_scene_frame.get((scene_id, frame_id), []),
        key=lambda row: (row.get("candidate_role") != "selected_primary", row.get("x_bin", ""), row.get("source_detection_id", "")),
    )


def count_kinds(rows: Iterable[dict[str, str]], from_tf: str, to_tf: str) -> tuple[int, int, int]:
    selected = 0
    competing = 0
    other_selected = 0
    for row in rows:
        kind = candidate_kind(row, from_tf, to_tf)
        if kind in {"from_selected", "to_selected"}:
            selected += 1
        elif kind == "other_selected":
            other_selected += 1
        else:
            competing += 1
    return selected, competing, other_selected


def write_item_readme(path: Path, item: dict[str, str], item_rows: list[dict[str, str]]) -> None:
    frame_start = item_rows[0]["frame_id"] if item_rows else ""
    frame_end = item_rows[-1]["frame_id"] if item_rows else ""
    lines = [
        f"# {item['review_item_id']} {item['merge_candidate_id']}",
        "",
        "This folder is for YOLO26l optical diagnostic timeline review only.",
        "",
        "- Do not treat these boxes as final boxes.",
        "- Do not generate GT or revised annotations from this folder.",
        "- Do not use this as SAR-ready evidence.",
        "- Compare selected primary boxes with competing candidates before judging same-vehicle referent.",
        "",
        f"- scene_id: `{item['scene_id']}`",
        f"- from_target_family_id: `{item['from_target_family_id']}` frames `{item['from_frame_start']}-{item['from_frame_end']}`",
        f"- to_target_family_id: `{item['to_target_family_id']}` frames `{item['to_frame_start']}-{item['to_frame_end']}`",
        f"- review frames: `{frame_start}-{frame_end}`",
        f"- sequence_reason_codes: `{item['sequence_reason_codes']}`",
        f"- from_competing_frame_count: `{item['from_competing_frame_count']}`",
        f"- to_competing_frame_count: `{item['to_competing_frame_count']}`",
        "",
        "Human review question:",
        "",
        "Do the from/to target families keep the same real-vehicle referent after comparing competing candidates, center/area continuity, class continuity, and x_bin stability?",
        "",
        "Recommended decision labels:",
        "",
        "- accept_review_candidate_only",
        "- keep_separate_due_to_competing_vehicle",
        "- keep_separate_due_to_center_or_area_jump",
        "- mark_review_required",
        "- mark_bad_detection_context",
        "",
        "Frame manifest:",
        "",
        "- `FRAME_MANIFEST.csv` at pack root contains one row per rendered frame.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pack_readme(path: Path, item_count: int, frame_count: int) -> None:
    lines = [
        "# YOLO26l WGV1.2 vehicle-centric merge review pack",
        "",
        "This ignored output folder contains diagnostic annotated PNG frames for human review.",
        "",
        f"- review items: {item_count}",
        f"- rendered frames: {frame_count}",
        "- detector_source: YOLO26l",
        "- final boxes: no",
        "- GT boxes: no",
        "- revised annotations: no",
        "- SAR-ready: no / blocked",
        "",
        "Use order:",
        "",
        "1. Open `INDEX_BY_REVIEW_ITEM.md`.",
        "2. For each MRQ folder, inspect `frames_yolo_annotated/` sequentially.",
        "3. Compare green/cyan selected target-family boxes with orange competing candidates.",
        "4. Decide whether the from/to target families preserve the same real-vehicle referent.",
        "5. Do not write new bbox coordinates from this pack.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report_ascii(
    item_manifest: list[dict[str, str]],
    output_root: Path,
    manifest_path: Path,
    frame_manifest_path: Path,
) -> str:
    lines = [
        "# OTY2 YOLO26l WGV1.2 vehicle-centric merge review pack",
        "",
        "Date: 2026-07-08",
        "",
        "## Conclusion",
        "",
        "This pass builds a human review pack from the same-vehicle merge review queue. It does not force multiple target families into one vehicle_group. Instead, each of the 11 review-only merge candidates is a separate review item, and each item shows selected primary candidates together with same-frame competing candidates.",
        "",
        "The pack is diagnostic only: no final boxes, no GT boxes, no final/revised annotation, no SAR, and no tracker replay.",
        "",
        "## Ignored Output Directory",
        "",
        f"```text\n{output_root.as_posix()}/\n```",
        "",
        "This directory contains annotated PNG frames and must not be committed.",
        "",
        "## Committable Index",
        "",
        f"- `{manifest_path.as_posix()}`",
        f"- `{frame_manifest_path.as_posix()}`",
        "",
        "## Review Queue Summary",
        "",
        "| review_item_id | scene_id | from_target_family | to_target_family | frames | competing | SAR-ready |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in item_manifest:
        frames = f"{item['frame_start']}-{item['frame_end']}"
        competing = f"{item['competing_candidate_frames']} frames"
        lines.append(
            "| {review_item_id} | {scene_id} | {from_target_family_id} | {to_target_family_id} | {frames} | {competing} | {sar_ready} |".format(
                **item,
                frames=frames,
                competing=competing,
            )
        )
    lines.extend(
        [
            "",
            "## Human Review Questions",
            "",
            "For every item, inspect `frames_yolo_annotated/` in frame order:",
            "",
            "1. Do `from_target_family` and `to_target_family` preserve the same real-vehicle referent?",
            "2. Are center position, box area, class label, and `x_bin` temporally continuous?",
            "3. Are orange `competing` candidates more plausible as the successor target?",
            "4. Is there any truck/car, white/black vehicle, or left/right vehicle cross-target jump?",
            "5. If uncertain, keep `review_required`; do not auto-merge.",
            "",
            "## Boundary",
            "",
            "- `auto_merge_allowed=no`",
            "- `sar_ready=no / blocked`",
            "- Do not write new bbox coordinates.",
            "- Do not generate final boxes / GT boxes / revised annotation.",
            "- Do not enter SAR pairing/support/selector/ranking.",
        ]
    )
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> None:
    queue = read_csv(args.review_queue)
    bank = read_csv(args.bank)
    _target_families = read_csv(args.target_families)

    output_root = Path(args.output_root)
    data_root = Path(args.data_root)
    report_path = Path(args.report)
    manifest_path = Path(args.manifest)
    frame_manifest_path = Path(args.frame_manifest)

    bank_by_scene_frame: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in bank:
        bank_by_scene_frame.setdefault((row["scene_id"], as_int(row["frame_id"])), []).append(row)

    frame_manifest: list[dict[str, str]] = []
    item_manifest: list[dict[str, str]] = []

    for item in queue:
        scene_id = item["scene_id"]
        frame_start = min(as_int(item["from_frame_start"]), as_int(item["to_frame_start"]))
        frame_end = max(as_int(item["from_frame_end"]), as_int(item["to_frame_end"]))
        folder = output_root / f"{item['review_item_id']}_{safe_name(scene_id)}_{safe_name(item['merge_candidate_id'])}"
        frames_dir = folder / "frames_yolo_annotated"
        item_rows: list[dict[str, str]] = []
        selected_frames = 0
        competing_frames = 0
        detectionless_frames = 0

        for frame_id in range(frame_start, frame_end + 1):
            candidates = rows_for_frame(bank_by_scene_frame, scene_id, frame_id)
            selected_count, competing_count, other_selected_count = count_kinds(
                candidates,
                item["from_target_family_id"],
                item["to_target_family_id"],
            )
            if selected_count:
                selected_frames += 1
            if competing_count:
                competing_frames += 1
            if not candidates:
                detectionless_frames += 1
            source = frame_path(data_root, scene_id, frame_id)
            out = frames_dir / f"{scene_id}_{frame_id:06d}_diagnostic_yolo26l.png"
            if not source.exists():
                raise FileNotFoundError(source)
            draw_frame(source, out, candidates, item, frame_id)
            row = {
                "review_item_id": item["review_item_id"],
                "merge_candidate_id": item["merge_candidate_id"],
                "scene_id": scene_id,
                "frame_id": str(frame_id),
                "phase": phase_for_frame(frame_id, item),
                "from_target_family_id": item["from_target_family_id"],
                "to_target_family_id": item["to_target_family_id"],
                "selected_primary_count": str(selected_count),
                "competing_candidate_count": str(competing_count),
                "other_selected_primary_count": str(other_selected_count),
                "raw_candidate_count": str(len(candidates)),
                "annotated_frame_path": out.as_posix(),
                "source_frame_path": source.as_posix(),
                "human_question": "same_real_vehicle_referent_after_competing_candidate_review?",
                "sar_ready": "no / blocked",
                "note": "diagnostic annotated frame;not final box;not revised annotation",
            }
            frame_manifest.append(row)
            item_rows.append(row)

        write_item_readme(folder / "README.md", item, item_rows)
        item_manifest.append(
            {
                "review_item_id": item["review_item_id"],
                "merge_candidate_id": item["merge_candidate_id"],
                "scene_id": scene_id,
                "from_target_family_id": item["from_target_family_id"],
                "from_frame_start": item["from_frame_start"],
                "from_frame_end": item["from_frame_end"],
                "to_target_family_id": item["to_target_family_id"],
                "to_frame_start": item["to_frame_start"],
                "to_frame_end": item["to_frame_end"],
                "frame_start": str(frame_start),
                "frame_end": str(frame_end),
                "frame_count": str(frame_end - frame_start + 1),
                "selected_primary_frames": str(selected_frames),
                "competing_candidate_frames": str(competing_frames),
                "detectionless_frames": str(detectionless_frames),
                "folder_path": folder.as_posix(),
                "human_question": "same_real_vehicle_referent_after_competing_candidate_review?",
                "auto_merge_allowed": "no",
                "sar_ready": "no / blocked",
                "note": "vehicle-centric merge review item;diagnostic only",
            }
        )

    write_csv(output_root / "FRAME_MANIFEST.csv", frame_manifest, FRAME_MANIFEST_FIELDS)
    write_csv(output_root / "REVIEW_ITEM_MANIFEST.csv", item_manifest, ITEM_MANIFEST_FIELDS)
    write_csv(manifest_path, item_manifest, ITEM_MANIFEST_FIELDS)
    write_csv(frame_manifest_path, frame_manifest, FRAME_MANIFEST_FIELDS)
    write_pack_readme(output_root / "README.md", len(item_manifest), len(frame_manifest))

    index_lines = [
        "# Index by review item",
        "",
        "| review_item_id | scene_id | frames | folder |",
        "|---|---|---|---|",
    ]
    for item in item_manifest:
        index_lines.append(
            f"| {item['review_item_id']} | {item['scene_id']} | {item['frame_start']}-{item['frame_end']} | `{item['folder_path']}` |"
        )
    (output_root / "INDEX_BY_REVIEW_ITEM.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report_ascii(item_manifest, output_root, manifest_path, frame_manifest_path), encoding="utf-8")

    print(f"wrote output_root={output_root} review_items={len(item_manifest)} frames={len(frame_manifest)}")
    print(f"wrote report={report_path}")
    print(f"wrote manifest={manifest_path}")
    print(f"wrote frame_manifest={frame_manifest_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--target-families", type=Path, default=DEFAULT_TARGET_FAMILIES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--frame-manifest", type=Path, default=DEFAULT_FRAME_MANIFEST)
    return parser.parse_args()


def main() -> int:
    build(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
