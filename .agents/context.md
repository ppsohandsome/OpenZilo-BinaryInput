# Project context

## Goal

Build a low-latency, extensible Linux desktop application for one OpenZilo ring IMU. The first transport is direct Linux BLE; the presentation is PySide6/Qt.

Runtime: `/home/pp/anaconda3/envs/zilo-ring` (Python 3.12). The reproducible
spec is `environment.yml`; it clears inherited ROS `PYTHONPATH` inside this
environment and intentionally excludes LeRobot, Torch, OpenCV, and CUDA.

## Data path

`OpenZilo BLE adapter -> RingController -> orientation/motion processing -> AppStore -> Qt pages`

## Layer map

- `domain/`: immutable application data.
- `ports/`: technology-neutral interfaces.
- `infrastructure/`: OpenZilo SDK, Bleak, persistence, logging.
- `processing/`: calibration, orientation, stream metrics.
- `state/`: bounded thread-safe latest/history state.
- `application/`: lifecycle orchestration and reconnect policy.
- `presentation/qt/`: shell, page registry, and pages.
- `capture/`: Qt-independent labeled IMU trial recorder and CSV/JSON output.
- `recognition/`: Qt-independent action gating, trial features, and direction models.
- Recognition diagnostics default to `data/logs/recognition.jsonl`; each
  completed candidate includes summary metrics and its gyro trace.
- Complete-gesture training uses `gesture_negative_v2`; never reuse the older
  `negative` trials because they contain motions that overlap the new positive
  gesture definitions.
- Complete-gesture positives are `single_press_rebound`, `up_flick_rebound`,
  and `double_press_rebound`. They are finger-like rebound patterns, not
  position estimates and not necessarily physical desk-contact gestures.
- `bootstrap/`: dependency construction.
- `soarm/`: retained historical source only; it is not wired into the application
  and LeRobot is not part of the Zilo runtime environment.

## Current hardware assumptions

- Host Bluetooth controller: Intel AX211.
- The official `openzilo` package is the only SDK dependency. The custom
  BlueZ transport retains adapter selection, stale-connection cleanup, service
  caching, and reconnect behavior outside the SDK.
- Public source defaults to no ring MAC. Set `ZILO_RING_MAC` locally to prefill
  a physical ring; the UI field remains a temporary runtime override.

## UI contract

- App shell uses navigation plus a stacked page area.
- Visualization shows a fixed-position ring in an orbitable 3D editor scene, six-axis plots, and a non-positional short-gesture direction estimate.
- Additional pages register through the page registry without accessing BLE directly.
- The capture panel above the Visualizer charts polls the bounded state history, records only samples that
  arrive after Start, and saves aligned raw/bias-corrected data without
  importing Bluetooth infrastructure.
