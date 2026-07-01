"""Runtime-safe optical bbox and temporal state features.

This module deliberately works only from runtime geometry: frame numbers,
optical bbox coordinates, image dimensions, and same-frame boxes. It does not
consume GT, final, oracle, manual labels, posthoc IoU, or candidate-source
families to build state features.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def aspect(self) -> float | None:
        if self.height <= 0:
            return None
        return self.width / self.height

    @classmethod
    def from_xywh(cls, cx: float, cy: float, width: float, height: float) -> "BBox":
        half_w = width / 2.0
        half_h = height / 2.0
        return cls(cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def parse_float(value: Any) -> float | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def first_float(row: Mapping[str, Any], names: Sequence[str]) -> float | None:
    for name in names:
        value = parse_float(row.get(name))
        if value is not None:
            return value
    return None


def bbox_from_row(row: Mapping[str, Any]) -> BBox | None:
    """Parse a bbox from common runtime optical bbox column names."""

    x1 = first_float(row, ("opt_x1", "bbox_x1", "x1", "left"))
    y1 = first_float(row, ("opt_y1", "bbox_y1", "y1", "top"))
    x2 = first_float(row, ("opt_x2", "bbox_x2", "x2", "right"))
    y2 = first_float(row, ("opt_y2", "bbox_y2", "y2", "bottom"))
    if None not in (x1, y1, x2, y2):
        assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
        return BBox(x1, y1, x2, y2)

    cx = first_float(row, ("opt_cx", "bbox_cx", "cx", "center_x", "u_opt"))
    cy = first_float(row, ("opt_cy", "bbox_cy", "cy", "center_y", "v_opt"))
    width = first_float(row, ("opt_w", "bbox_w", "w", "width", "opt_w_px"))
    height = first_float(row, ("opt_h", "bbox_h", "h", "height", "opt_h_px"))
    if None not in (cx, cy, width, height):
        assert cx is not None and cy is not None and width is not None and height is not None
        return BBox.from_xywh(cx, cy, width, height)
    return None


def bbox_iou(a: BBox, b: BBox) -> float:
    inter_x1 = max(a.x1, b.x1)
    inter_y1 = max(a.y1, b.y1)
    inter_x2 = min(a.x2, b.x2)
    inter_y2 = min(a.y2, b.y2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    union = a.area + b.area - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def center_distance(a: BBox, b: BBox) -> float:
    return hypot(a.cx - b.cx, a.cy - b.cy)


def size_consistency(a: BBox, b: BBox) -> float:
    """Return a 0..1 proxy combining area and aspect consistency."""

    if a.area <= 0 or b.area <= 0:
        return 0.0
    area_ratio = min(a.area, b.area) / max(a.area, b.area)
    a_aspect = a.aspect
    b_aspect = b.aspect
    if a_aspect is None or b_aspect is None or a_aspect <= 0 or b_aspect <= 0:
        aspect_ratio = 0.0
    else:
        aspect_ratio = min(a_aspect, b_aspect) / max(a_aspect, b_aspect)
    return max(0.0, min(1.0, (area_ratio + aspect_ratio) / 2.0))


def boundary_contact_features(
    bbox: BBox,
    frame_width: float | None,
    frame_height: float | None,
    margin_px: float = 2.0,
) -> dict[str, Any]:
    if frame_width is None or frame_height is None or frame_width <= 0 or frame_height <= 0:
        return {
            "frame_boundary_contact_status": "missing_frame_size",
            "touch_left": "",
            "touch_right": "",
            "touch_top": "",
            "touch_bottom": "",
            "touch_any": "",
        }
    touch_left = bbox.x1 <= margin_px
    touch_top = bbox.y1 <= margin_px
    touch_right = bbox.x2 >= frame_width - margin_px
    touch_bottom = bbox.y2 >= frame_height - margin_px
    return {
        "frame_boundary_contact_status": "available",
        "touch_left": touch_left,
        "touch_right": touch_right,
        "touch_top": touch_top,
        "touch_bottom": touch_bottom,
        "touch_any": touch_left or touch_right or touch_top or touch_bottom,
    }


def neighbor_context(
    bbox: BBox,
    same_frame_boxes: Sequence[BBox],
    neighbor_distance_px: float = 120.0,
) -> dict[str, Any]:
    distances = [center_distance(bbox, other) for other in same_frame_boxes if other is not bbox]
    if not distances:
        return {
            "neighbor_context_status": "available_no_same_frame_neighbors",
            "neighbor_count": 0,
            "min_neighbor_center_distance_px": "",
            "neighbor_ambiguity_proxy": False,
        }
    min_distance = min(distances)
    return {
        "neighbor_context_status": "available",
        "neighbor_count": len(distances),
        "min_neighbor_center_distance_px": min_distance,
        "neighbor_ambiguity_proxy": min_distance <= neighbor_distance_px,
    }


def pair_motion_features(
    previous: BBox | None,
    current: BBox,
    frame_gap: int | None,
) -> dict[str, Any]:
    if previous is None or frame_gap is None or frame_gap <= 0:
        return {
            "velocity_status": "missing_previous_or_gap",
            "velocity_x_px_per_frame": "",
            "velocity_y_px_per_frame": "",
            "center_speed_px_per_frame": "",
            "size_change_ratio": "",
        }
    dx = current.cx - previous.cx
    dy = current.cy - previous.cy
    speed = hypot(dx, dy) / frame_gap
    if previous.area <= 0:
        size_change_ratio: float | str = ""
    else:
        size_change_ratio = (current.area - previous.area) / previous.area
    return {
        "velocity_status": "available",
        "velocity_x_px_per_frame": dx / frame_gap,
        "velocity_y_px_per_frame": dy / frame_gap,
        "center_speed_px_per_frame": speed,
        "size_change_ratio": size_change_ratio,
    }


def track_jitter_proxy(
    previous: BBox | None,
    current: BBox,
    next_box: BBox | None,
) -> dict[str, Any]:
    if previous is None or next_box is None:
        return {"track_jitter_proxy_status": "missing_previous_or_next", "track_jitter_proxy_px": ""}
    expected_x = (previous.cx + next_box.cx) / 2.0
    expected_y = (previous.cy + next_box.cy) / 2.0
    return {
        "track_jitter_proxy_status": "available_three_point_center_deviation",
        "track_jitter_proxy_px": hypot(current.cx - expected_x, current.cy - expected_y),
    }


def truncation_likelihood_proxy(
    contact: Mapping[str, Any],
    size_change_ratio: Any,
) -> str:
    touch_any = str(contact.get("touch_any", "")).lower() == "true" or contact.get("touch_any") is True
    size_change = parse_float(size_change_ratio)
    size_changed = size_change is not None and abs(size_change) >= 0.25
    if touch_any and size_changed:
        return "edge_contact_and_size_change_review"
    if touch_any:
        return "edge_contact_review"
    if size_changed:
        return "size_change_review"
    if contact.get("frame_boundary_contact_status") == "missing_frame_size":
        return "missing_frame_size"
    return "low_no_contact_or_large_size_change"


def basic_bbox_features(bbox: BBox) -> dict[str, Any]:
    return {
        "bbox_x1": bbox.x1,
        "bbox_y1": bbox.y1,
        "bbox_x2": bbox.x2,
        "bbox_y2": bbox.y2,
        "bbox_center_x": bbox.cx,
        "bbox_center_y": bbox.cy,
        "bbox_width": bbox.width,
        "bbox_height": bbox.height,
        "bbox_area": bbox.area,
        "bbox_aspect": "" if bbox.aspect is None else bbox.aspect,
    }


def compute_state_features(
    bbox: BBox,
    frame_width: float | None,
    frame_height: float | None,
    same_frame_boxes: Sequence[BBox],
    previous_bbox: BBox | None = None,
    previous_frame_num: int | None = None,
    current_frame_num: int | None = None,
    next_bbox: BBox | None = None,
    contact_margin_px: float = 2.0,
    neighbor_distance_px: float = 120.0,
) -> dict[str, Any]:
    frame_gap = None
    if previous_frame_num is not None and current_frame_num is not None:
        frame_gap = current_frame_num - previous_frame_num
    contact = boundary_contact_features(bbox, frame_width, frame_height, contact_margin_px)
    motion = pair_motion_features(previous_bbox, bbox, frame_gap)
    jitter = track_jitter_proxy(previous_bbox, bbox, next_bbox)
    neighbors = neighbor_context(bbox, same_frame_boxes, neighbor_distance_px)
    state = {
        **basic_bbox_features(bbox),
        **contact,
        **motion,
        **jitter,
        **neighbors,
    }
    state["truncation_likelihood_proxy"] = truncation_likelihood_proxy(
        contact, motion.get("size_change_ratio")
    )
    state["occlusion_proxy_status"] = "missing_no_runtime_safe_occlusion_source"
    state["ambiguity_proxy_status"] = (
        "neighbor_proxy_available"
        if neighbors["neighbor_context_status"].startswith("available")
        else "missing"
    )
    return state
