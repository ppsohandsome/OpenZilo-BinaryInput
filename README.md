# Zilo Ring

Low-latency ring IMU viewer and gesture-input desktop application for Linux.

## OpenZilo and ComBodied AI

Zilo Ring is an independent application built with the
[OpenZilo Python SDK](https://github.com/ziloai/OpenZilo). It explores
**ComBodied AI** through low-latency smart-ring IMU streaming, personalized
gesture recognition, and wearable input experiments.

See the [project showcase and demo](docs/OPENZILO_SHOWCASE.md).

## Architecture

- Qt GUI thread for rendering and interaction.
- A background thread with an asyncio loop for BLE connection and IMU streaming.
- BlueZ/Bleak transport with stale-connection cleanup, one scan per attempt, transient-error retries, service caching, graceful shutdown, and capped exponential reconnect backoff.

The GUI polls a bounded, thread-safe state store and never calls the BLE SDK directly.

## Setup

```bash
conda env create -f environment.yml
conda activate zilo-ring
```

For an existing environment, apply dependency changes with
`conda env update -f environment.yml --prune`.

The project is pinned to Python 3.12. Its runtime contains only the Qt and BLE
dependencies required by the ring application; LeRobot/SO-ARM is not installed.

Connection mode is selected by the MAC field when **Connect** is pressed:

- Empty MAC: start the virtual ring locally.
- Non-empty MAC: connect to that physical ring over BLE.

No device address is stored in the repository. Set `ZILO_RING_MAC` locally
before launching if you want to prefill a physical ring address; clearing the
field selects the virtual ring.

Install the sibling official OpenZilo SDK checkout:

```bash
python -m pip install -e ../OpenZilo
# Optional when the host has multiple Bluetooth adapters:
export ZILO_BLE_ADAPTER=hci0
# Local only: never commit a real address.
export ZILO_RING_MAC=AA:BB:CC:DD:EE:FF
python main.py
```

`--demo` remains available to clear any `ZILO_RING_MAC` prefill on launch:

```bash
python main.py --demo
```

The capture panel above the **Visualizer** charts records quick direction-classification trials. Select a
label and speed, keep still for one second, move once, hold for one second, and
press **Stop and save** before resetting the hand. Each trial produces an
aligned raw/bias-corrected CSV plus a `.meta.json` file under
`data/captures/`. Set `ZILO_CAPTURE_DIR` to use another output directory.
Use **Retake current** to discard only the current unsaved samples and restart
immediately with the same label, speed, and notes.

Complete-gesture capture labels are `single_press_rebound`,
`up_flick_rebound`, and `double_press_rebound`. They describe short finger-like
motion patterns and do not require physical desk contact. Each begins and ends
at the same neutral pose; use `gesture_negative_v2` for unrelated, incomplete,
or incorrect gestures and describe the subtype in Notes. The older `negative`
label belongs only to the one-way `up/down` model and must not train the
complete-gesture model.

Train the first idle-gated `up/down` direction model from captured normal-speed
trials with:

```bash
python tools/train_direction_model.py --after YYYYMMDD_HHMMSS
```

The activity gate returns `idle` unless sustained gyroscope motion is present;
after that gate opens, similarity and direction-coherence rejection prevent
unrelated strong motion from being forced into an `up/down` class.
When the model file exists, live recognition starts automatically. The
Visualizer overlays each completed action as the same time-aligned translucent
region on the acceleration and gyroscope charts. Override the model artifact
with `ZILO_DIRECTION_MODEL_PATH` when needed.

Every completed recognition attempt, including rejected motion, is appended to
`data/logs/recognition.jsonl` with thresholds, summary metrics, and its complete
bias-corrected gyroscope trace. Set `ZILO_RECOGNITION_LOG_PATH` to override it.
Rejected attempts appear as gray diagnostic regions but are not accepted as
`up/down` actions.

## Included model checkpoints

Two lightweight JSON checkpoints are included under `models/` so the gesture
recognition flow can be explored immediately. They were trained from one
wearer's private labeled IMU trials and are examples, not general-purpose
models or accuracy guarantees. The raw capture sessions are intentionally not
included; retrain with your own gestures before using recognition as input.

## Tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

The visualization deliberately does not display a spatial trajectory. The 3D
ring scene is currently disabled while transport latency is evaluated. The
motion estimator uses one conditioned IMU path: startup gyro-bias
calibration, stationary-only slow bias tracking, timestamp-aware low-pass
filtering, six-axis Mahony quaternion fusion, dynamic-acceleration rejection,
and quaternion output smoothing. Sensor charts overlay raw values as dashed
lines and bias-corrected values as solid lines; either series can be hidden.
