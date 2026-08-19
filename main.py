from __future__ import annotations

import sys
import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from zilo_ring.bootstrap import build_application
from zilo_ring.presentation.qt.qt_app import run_qt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zilo Ring IMU desktop viewer")
    parser.add_argument("--demo", action="store_true", help="run with generated IMU data")
    args = parser.parse_args(argv)
    return run_qt(build_application(demo=args.demo))


if __name__ == "__main__":
    raise SystemExit(main())
