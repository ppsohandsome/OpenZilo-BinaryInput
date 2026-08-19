# Zilo Ring

Low-latency, single-ring IMU desktop viewer for Linux.

## Architecture

The application is one process with two execution contexts:

- Qt GUI thread for rendering and interaction.
- A background thread with an asyncio loop for BLE connection and IMU streaming.

The GUI polls a bounded, thread-safe state store and never calls the BLE SDK directly.

## Setup

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

Point the application at the supplied Ring Sound SDK and ring address:

```bash
export RING_SOUND_SDK_PATH=/path/to/ring_sound.py
export ZILO_RING_MAC=AA:BB:CC:DD:EE:FF
.venv/bin/python main.py
```

Run without hardware:

```bash
.venv/bin/python main.py --demo
```

## Tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
```

The initial visualization deliberately does not display a spatial trajectory. With a six-axis IMU, roll and pitch can be gravity-corrected while relative yaw drifts over time.
