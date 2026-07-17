from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon


REPO = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO / "manifests" / "oty2"
SKELETON_REFERENCE = MANIFEST_DIR / "oty2_rsa1_a0_hidden_skeleton_reference.csv"
BACKGROUND_REFERENCE = MANIFEST_DIR / "oty2_rsa1_a0_hidden_background_reference.csv"
FREEZE_MANIFEST = MANIFEST_DIR / "oty2_rsa1_a0_hidden_reference_freeze_manifest.csv"
R2_OUTPUT = Path(r"D:\profile\research\workspace\output\oty2_rsa0_r2_20260717")
OUTPUT_ROOT = Path(r"D:\profile\research\workspace\output\oty2_rsa1_a0_20260717")
OVERLAY_ROOT = OUTPUT_ROOT / "hidden_reference_overlays"
OVERLAY_MANIFEST = OUTPUT_ROOT / "hidden_reference_overlay_manifest.csv"

CASES = {
    "PV002_337_341": {
        "frames": [337, 338, 339, 340, 341],
        "bundle": R2_OUTPUT
        / "arrays"
        / "phase_b"
        / "coordinate_stacks"
        / "PV002_337_341"
        / "pv002_337_341_raw_sar_display.npz",
    },
    "PV003_380_384": {
        "frames": [380, 381, 382, 383, 384],
        "bundle": R2_OUTPUT
        / "arrays"
        / "phase_b"
        / "coordinate_stacks"
        / "PV003_380_384"
        / "pv003_380_384_raw_sar_display.npz",
    },
}

EXPECTED_LABELS = {
    "CONFIRMED_MAIN_SKELETON",
    "CONFIRMED_SEED_SEGMENT",
    "CONFIRMED_VERTICAL_BACKGROUND",
    "ARC_OR_CLUTTER_AMBIGUOUS_ZONE",
    "UNRESOLVED_ENDPOINT_ZONE",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_points(text: str) -> np.ndarray:
    points = []
    for token in text.split(";"):
        x_text, y_text = token.split(",")
        points.append((float(x_text), float(y_text)))
    return np.asarray(points, dtype=np.float64)


def polyline_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def point_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    delta = end - start
    denominator = float(np.dot(delta, delta))
    if denominator == 0.0:
        return float(np.linalg.norm(point - start))
    t = float(np.clip(np.dot(point - start, delta) / denominator, 0.0, 1.0))
    return float(np.linalg.norm(point - (start + t * delta)))


def point_polyline_distance(point: np.ndarray, polyline: np.ndarray) -> float:
    return min(point_segment_distance(point, polyline[index], polyline[index + 1]) for index in range(len(polyline) - 1))


def validate_rows(rows: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, dict[str, str]]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, str]]] = {}
    for row in rows:
        key = (row["case_id"], int(row["sar_frame"]))
        label = row["label"]
        if label in grouped.setdefault(key, {}):
            raise ValueError(f"duplicate hidden-reference label: {key} {label}")
        grouped[key][label] = row
        points = parse_points(row["points"])
        if not np.isfinite(points).all() or points.ndim != 2 or points.shape[1] != 2:
            raise ValueError(f"invalid points: {key} {label}")
        if row["coordinate_system"] != "sar_display_px":
            raise ValueError(f"unexpected coordinate system: {key} {label}")
        if row["source_role"] != "hidden_evaluation_only":
            raise ValueError(f"hidden reference is not evaluator-only: {key} {label}")
        if label.endswith("ZONE") and row["geometry_type"] != "polygon":
            raise ValueError(f"zone must be polygon: {key} {label}")
        if not label.endswith("ZONE") and row["geometry_type"] != "polyline":
            raise ValueError(f"line reference must be polyline: {key} {label}")

    expected_keys = {(case_id, frame) for case_id, spec in CASES.items() for frame in spec["frames"]}
    if set(grouped) != expected_keys:
        raise ValueError(f"hidden-reference frames mismatch: {sorted(set(grouped) ^ expected_keys)}")
    for key, labels in grouped.items():
        if set(labels) != EXPECTED_LABELS:
            raise ValueError(f"hidden-reference labels mismatch for {key}: {sorted(set(labels) ^ EXPECTED_LABELS)}")
        skeleton = parse_points(labels["CONFIRMED_MAIN_SKELETON"]["points"])
        seed = parse_points(labels["CONFIRMED_SEED_SEGMENT"]["points"])
        vertical = parse_points(labels["CONFIRMED_VERTICAL_BACKGROUND"]["points"])
        if polyline_length(seed) >= polyline_length(skeleton):
            raise ValueError(f"seed is not smaller than skeleton: {key}")
        if max(point_polyline_distance(point, skeleton) for point in seed) > 2.5:
            raise ValueError(f"seed is not on the confirmed skeleton: {key}")
        if min(point_polyline_distance(point, vertical) for point in seed) <= 3.0:
            raise ValueError(f"seed touches the hard background barrier: {key}")
    return grouped


def render_overlay(
    case_id: str,
    frame: int,
    image: np.ndarray,
    labels: dict[str, dict[str, str]],
) -> Path:
    points_by_label = {label: parse_points(row["points"]) for label, row in labels.items()}
    all_points = np.concatenate(list(points_by_label.values()), axis=0)
    x0 = max(0, int(np.floor(all_points[:, 0].min() - 80)))
    x1 = min(image.shape[1], int(np.ceil(all_points[:, 0].max() + 80)))
    y0 = max(0, int(np.floor(all_points[:, 1].min() - 80)))
    y1 = min(image.shape[0], int(np.ceil(all_points[:, 1].max() + 80)))
    crop = image[y0:y1, x0:x1]

    figure, axis = plt.subplots(figsize=(11, 7), constrained_layout=True)
    axis.imshow(crop, cmap="gray", vmin=0.0, vmax=85.0, interpolation="nearest")
    style = {
        "CONFIRMED_MAIN_SKELETON": ("lime", 2.0),
        "CONFIRMED_SEED_SEGMENT": ("yellow", 4.0),
        "CONFIRMED_VERTICAL_BACKGROUND": ("red", 2.5),
    }
    for label, (color, width) in style.items():
        points = points_by_label[label] - np.array([x0, y0])
        axis.plot(points[:, 0], points[:, 1], color=color, linewidth=width, label=label)
    zone_style = {
        "ARC_OR_CLUTTER_AMBIGUOUS_ZONE": ("orange", "//"),
        "UNRESOLVED_ENDPOINT_ZONE": ("magenta", "\\\\"),
    }
    for label, (color, hatch) in zone_style.items():
        points = points_by_label[label] - np.array([x0, y0])
        axis.add_patch(
            Polygon(points, closed=True, facecolor="none", edgecolor=color, linewidth=1.8, hatch=hatch, label=label)
        )
    axis.set_title(f"{case_id} SAR {frame} | hidden reference | evaluator only")
    axis.legend(loc="upper right", fontsize=8)
    axis.set_xlim(0, crop.shape[1] - 1)
    axis.set_ylim(crop.shape[0] - 1, 0)
    axis.grid(color="cyan", alpha=0.12, linewidth=0.5)
    output = OVERLAY_ROOT / case_id / f"{case_id.lower()}_{frame}_hidden_reference_overlay.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output


def main() -> None:
    skeleton_rows = read_rows(SKELETON_REFERENCE)
    background_rows = read_rows(BACKGROUND_REFERENCE)
    grouped = validate_rows(skeleton_rows + background_rows)

    overlay_rows: list[dict[str, object]] = []
    for case_id, spec in CASES.items():
        bundle = Path(spec["bundle"])
        if not bundle.is_file():
            raise FileNotFoundError(bundle)
        with np.load(bundle, allow_pickle=False) as data:
            stack = data["image_stack"]
        if stack.shape[0] != len(spec["frames"]):
            raise ValueError(f"unexpected frame stack shape: {case_id} {stack.shape}")
        for index, frame in enumerate(spec["frames"]):
            output = render_overlay(case_id, frame, stack[index], grouped[(case_id, frame)])
            overlay_rows.append(
                {
                    "case_id": case_id,
                    "sar_frame": frame,
                    "overlay_path": str(output),
                    "overlay_sha256": sha256_file(output),
                }
            )

    write_rows(OVERLAY_MANIFEST, overlay_rows, ["case_id", "sar_frame", "overlay_path", "overlay_sha256"])

    reference_files = [SKELETON_REFERENCE, BACKGROUND_REFERENCE]
    reference_hashes = [(path, sha256_file(path)) for path in reference_files]
    aggregate_text = "\n".join(f"{path.relative_to(REPO).as_posix()}:{digest}" for path, digest in reference_hashes)
    aggregate_sha = hashlib.sha256(aggregate_text.encode("utf-8")).hexdigest()
    freeze_rows: list[dict[str, object]] = []
    for path, digest in reference_hashes:
        freeze_rows.append(
            {
                "freeze_version": "OTY2-RSA1-A0-hidden-reference-freeze-v1",
                "entry_role": "hidden_evaluation_reference",
                "path": path.relative_to(REPO).as_posix(),
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "aggregate_reference_sha256": aggregate_sha,
                "isolation_rule": "evaluator_only_never_read_by_propagation",
            }
        )
    for case_id, spec in CASES.items():
        bundle = Path(spec["bundle"])
        freeze_rows.append(
            {
                "freeze_version": "OTY2-RSA1-A0-hidden-reference-freeze-v1",
                "entry_role": f"review_source_stack_{case_id}",
                "path": str(bundle),
                "sha256": sha256_file(bundle),
                "size_bytes": bundle.stat().st_size,
                "aggregate_reference_sha256": aggregate_sha,
                "isolation_rule": "source_binding_only",
            }
        )
    write_rows(
        FREEZE_MANIFEST,
        freeze_rows,
        [
            "freeze_version",
            "entry_role",
            "path",
            "sha256",
            "size_bytes",
            "aggregate_reference_sha256",
            "isolation_rule",
        ],
    )
    print(f"hidden_reference_rows={len(skeleton_rows) + len(background_rows)}")
    print(f"hidden_reference_overlays={len(overlay_rows)}")
    print(f"hidden_reference_freeze_sha256={aggregate_sha}")
    print(f"freeze_manifest={FREEZE_MANIFEST}")
    print(f"overlay_manifest={OVERLAY_MANIFEST}")


if __name__ == "__main__":
    main()
