"""Fan-polar to display-XY conversion.

The `heading` values carried by candidate rows are display-XY storage axes.
They are not interpreted here as physical vehicle heading.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Any, Mapping


@dataclass(frozen=True)
class FanPolarScene:
    center_x: float
    center_y: float
    theta_offset_deg: float = 0.0
    theta_sign: float = 1.0


def scene_from_config(scene_config: Mapping[str, Any]) -> FanPolarScene:
    """Build the fan-polar scene from a loaded scene config mapping."""

    fan = scene_config.get("fan") or scene_config.get("global_geometry", {}).get("fan")
    if fan is None:
        raise KeyError("scene config must contain a fan section")
    return FanPolarScene(
        center_x=float(fan["center_x"]),
        center_y=float(fan["center_y"]),
        theta_offset_deg=float(fan.get("theta_offset_deg", 0.0)),
        theta_sign=float(fan.get("theta_sign", 1.0)),
    )


def fan_polar_to_display_xy(
    r: float,
    az: float,
    cross: float,
    scene_config: Mapping[str, Any],
) -> tuple[float, float]:
    """Convert fan-polar `(r, az, cross)` to SAR display-XY coordinates.

    `r` and `cross` are in display pixels. `az` is an azimuth angle in degrees.
    Positive `cross` moves along the local tangential axis `(cos(theta), sin(theta))`.
    """

    scene = scene_from_config(scene_config)
    theta = radians(scene.theta_sign * float(az) + scene.theta_offset_deg)
    radius = float(r)
    tangential = float(cross)
    x = scene.center_x + radius * sin(theta) + tangential * cos(theta)
    y = scene.center_y - radius * cos(theta) + tangential * sin(theta)
    return x, y


def display_xy_to_svg_box(
    cx: float,
    cy: float,
    w: float,
    h: float,
    heading_deg: float | None = None,
) -> dict[str, float]:
    """Return a normalized display-XY box dictionary for visualization."""

    return {
        "cx": float(cx),
        "cy": float(cy),
        "w": float(w),
        "h": float(h),
        "heading_deg": float(heading_deg or 0.0),
    }
