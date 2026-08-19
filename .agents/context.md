# Project context

## Goal

Build a low-latency, extensible Linux desktop application for one Ring Sound IMU. The first transport is direct Linux BLE; the presentation is PySide6/Qt.

## Data path

`ADVX BLE adapter -> RingController -> orientation/motion processing -> AppStore -> Qt pages`

## Layer map

- `domain/`: immutable application data.
- `ports/`: technology-neutral interfaces.
- `infrastructure/`: ADVX SDK, Bleak, persistence, logging.
- `processing/`: calibration, orientation, stream metrics.
- `state/`: bounded thread-safe latest/history state.
- `application/`: lifecycle orchestration and reconnect policy.
- `presentation/qt/`: shell, page registry, and pages.
- `bootstrap/`: dependency construction.

## Current hardware assumptions

- Host Bluetooth controller: Intel AX211.
- Ring SDK is loaded from `RING_SOUND_SDK_PATH` or known local development candidates.
- The configured ring MAC comes from `ZILO_RING_MAC`; no MAC is silently assumed.

## UI contract

- App shell uses navigation plus a stacked page area.
- Visualization shows a fixed-position ring in an orbitable 3D editor scene, six-axis plots, and a non-positional short-gesture direction estimate.
- Additional pages register through the page registry without accessing BLE directly.
