from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


DEFAULT_LOCAL_SDK = Path("/home/pp/workspace/hackthon_advx/ring_sound_SDK/ring_sound.py")


def sdk_candidates(configured: Path | None = None) -> tuple[Path, ...]:
    values: list[Path] = []
    env_value = os.getenv("RING_SOUND_SDK_PATH", "").strip()
    for value in (configured, Path(env_value).expanduser() if env_value else None, DEFAULT_LOCAL_SDK):
        if value is None:
            continue
        path = value / "ring_sound.py" if value.is_dir() else value
        if path not in values:
            values.append(path)
    return tuple(values)


def load_ring_sdk(configured: Path | None = None) -> ModuleType:
    try:
        return importlib.import_module("ring_sound")
    except ModuleNotFoundError:
        pass

    for path in sdk_candidates(configured):
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_zilo_ring_sound", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    searched = ", ".join(str(path) for path in sdk_candidates(configured)) or "none"
    raise RuntimeError(
        "Ring Sound SDK not found. Set RING_SOUND_SDK_PATH to ring_sound.py. "
        f"Searched: {searched}"
    )
