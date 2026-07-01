"""Scene config loading for the V0 diagnostic bootstrap."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def load_scene_config(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                f"{path} is not JSON-compatible YAML and PyYAML is not installed"
            ) from exc
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} did not load to a mapping")
        return loaded


def get_scene_config(config: dict[str, Any], scene: str) -> dict[str, Any]:
    scenes = config.get("scenes", {})
    if scene not in scenes:
        raise KeyError(f"scene {scene!r} is not configured")
    merged = deepcopy(config.get("global_geometry", {}))
    scene_cfg = deepcopy(scenes[scene])
    merged.update(scene_cfg)
    merged["scene"] = scene
    return merged


def accounting_path_for(config: dict[str, Any], scene: str, key: str) -> str:
    scene_cfg = config.get("scenes", {}).get(scene, {})
    scene_sources = scene_cfg.get("accounting_sources", {})
    if key in scene_sources:
        return str(scene_sources[key])
    global_sources = config.get("accounting_sources", {})
    return str(global_sources.get(key, ""))
