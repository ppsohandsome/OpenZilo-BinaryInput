from __future__ import annotations

import sys
import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from zilo_ring.bootstrap import build_application
from zilo_ring.bootstrap.single_instance import acquire_single_instance_lock
from zilo_ring.presentation.qt.qt_app import run_qt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zilo Ring IMU desktop viewer")
    parser.add_argument("--demo", action="store_true", help="run with generated IMU data")
    args = parser.parse_args(argv)
    instance_lock = acquire_single_instance_lock()
    if instance_lock is None:
        print("Zilo Ring is already running.", file=sys.stderr)
        return 2
    try:
        return run_qt(build_application(demo=args.demo))
    finally:
        instance_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
