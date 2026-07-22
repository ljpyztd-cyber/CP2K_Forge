from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .settings import user_config_dir


MAX_VISUAL_STYLES = 10
DEFAULT_STYLE_ID = "__default__"
VISUAL_STYLES_FILENAME = "visual_styles.json"


def visual_styles_path() -> Path:
    return user_config_dir() / VISUAL_STYLES_FILENAME


def _style_name(value: Any) -> str:
    return str(value or "").strip()[:48]


def _clean_style(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = _style_name(raw.get("name"))
    if not name:
        return None
    settings = raw.get("settings")
    if not isinstance(settings, dict):
        return None
    return {"name": name, "settings": settings}


def load_visual_styles() -> list[dict[str, Any]]:
    path = visual_styles_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_styles = data.get("styles", []) if isinstance(data, dict) else data
    if not isinstance(raw_styles, list):
        return []
    styles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_styles:
        style = _clean_style(raw)
        if not style:
            continue
        key = style["name"].casefold()
        if key in seen:
            continue
        seen.add(key)
        styles.append(style)
        if len(styles) >= MAX_VISUAL_STYLES - 1:
            break
    return styles


def save_visual_styles(styles: list[dict[str, Any]]) -> Path:
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in styles:
        style = _clean_style(raw)
        if not style:
            continue
        key = style["name"].casefold()
        if key in seen:
            continue
        seen.add(key)
        clean.append(style)
        if len(clean) >= MAX_VISUAL_STYLES - 1:
            break
    target_dir = user_config_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / VISUAL_STYLES_FILENAME
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps({"styles": clean}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)
    return target
