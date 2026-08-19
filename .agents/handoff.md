# Handoff

## Current phase

The initial layered implementation is complete and ready for desktop and hardware validation.

## Implemented

- Single-ring BLE lifecycle with reconnect.
- Typed raw and normalized IMU data.
- Complementary orientation estimate with recenter.
- Thread-safe latest sample and bounded plot history.
- Extensible Qt shell with Visualizer, Diagnostics, and Settings pages.
- Visualizer with a solid shaded torus, wear marker on the positive-X intersection, arrowed SENSOR axes, WORLD gizmo, editor grid, and orbit/pan/zoom camera controls.
- Five-second fixed-scale plots (`±2 g`, `±500 °/s`) with XYZ legends, zero lines, time ticks, and current values.
- Gravity-compensated control-frame acceleration and a short-gesture direction state machine (`IDLE/START/MOVING/BRAKING`) without position integration.
- A cyan 3D motion cone whose length represents relative intensity and width represents direction confidence, plus a camera-independent six-direction panel.
- Split refresh cadence: ring at GUI rate, charts at about 30 Hz, and text metrics at 10 Hz.
- Fake source and pure-layer tests.

## Verified

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`: 12 passed.
- The local Ring Sound SDK loads and exposes `RingSoundClient`.
- Offscreen Qt smoke test creates three registered pages and receives about 100 Hz from the fake source.
- Desktop Qt Quick 3D smoke test loads the solid scene without QML errors.
- Core, ports, processing, state, and application layers do not import PySide6, Bleak, or the Ring Sound SDK.

## Remaining verification

- Run `main.py --demo` on the real desktop to inspect the Qt Quick 3D scene and plots. Offscreen rendering may differ from the desktop graphics backend.
- Set `ZILO_RING_MAC`, power the ring, and perform a real BLE session.
- Confirm sensor axes, actual sample rate, packet loss, reconnect behavior, and orientation signs with physical motion.
