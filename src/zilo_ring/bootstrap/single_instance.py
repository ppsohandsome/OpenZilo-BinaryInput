from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import TextIO


def default_lock_path() -> Path:
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
    return runtime_dir / f"zilo-ring-{os.getuid()}.lock"


def acquire_single_instance_lock(path: Path | None = None) -> TextIO | None:
    """Return an open process lock, or None when another instance owns it."""
    lock_file = (path or default_lock_path()).open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    return lock_file
