from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .i18n import normalize_language


APP_CONFIG_DIRNAME = "CP2K_FORGE"
CONFIG_FILENAME = "settings.ini"


def user_config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_CONFIG_DIRNAME


def bundled_multiwfn_folder() -> Path | None:
    roots: list[Path] = []
    module_root = Path(__file__).resolve()
    roots.extend(module_root.parents[:4])
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.extend([exe_dir, *exe_dir.parents[:4]])
    roots.extend([Path.cwd(), *Path.cwd().parents[:3]])

    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        candidate = root / "Multiwfn_3.8_dev_bin_Win64"
        if (candidate / "Multiwfn.exe").is_file():
            return candidate
    return None


def normalize_multiwfn_path(value: str | os.PathLike[str] | None) -> str:
    text = str(value or "").strip().strip('"')
    if not text:
        candidate = bundled_multiwfn_folder()
        return str(candidate) if candidate else ""
    path = Path(text)
    if path.is_file() and path.name.lower() == "multiwfn.exe":
        return str(path.parent)
    return str(path)


def multiwfn_exe_from_setting(value: str | os.PathLike[str] | None) -> Path | None:
    text = normalize_multiwfn_path(value)
    if not text:
        return None
    path = Path(text)
    if path.is_dir() and (path / "Multiwfn.exe").is_file():
        return path / "Multiwfn.exe"
    if path.is_file():
        return path
    return None


@dataclass
class AppSettings:
    multiwfn_path: str = ""
    language: str = "zh"


def load_settings() -> AppSettings:
    cfg = configparser.ConfigParser()
    path = user_config_dir() / CONFIG_FILENAME
    settings = AppSettings(multiwfn_path=normalize_multiwfn_path(""), language="zh")
    if path.is_file():
        cfg.read(path, encoding="utf-8")
        if "paths" in cfg:
            settings.multiwfn_path = normalize_multiwfn_path(cfg["paths"].get("multiwfn", settings.multiwfn_path))
        if "ui" in cfg:
            settings.language = normalize_language(cfg["ui"].get("language", settings.language))
    return settings


def save_settings(settings: AppSettings) -> Path:
    cfg = configparser.ConfigParser()
    cfg["paths"] = {"multiwfn": normalize_multiwfn_path(settings.multiwfn_path)}
    cfg["ui"] = {"language": normalize_language(settings.language)}
    target_dir = user_config_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / CONFIG_FILENAME
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
    os.replace(tmp, target)
    return target
