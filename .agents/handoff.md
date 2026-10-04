# Handoff

## Current phase

The initial layered implementation is complete and ready for desktop and hardware validation.

## Implemented

- Single-ring BLE lifecycle using Bleak 3, BlueZ, and bleak-retry-connector.
- OpenZilo Python SDK migration: the adapter uses its public `OpenZiloClient`,
  system-information, and IMU-report APIs while retaining the app's reliable
  Linux NUS transport.
- One scan per connection attempt, stale BlueZ connection cleanup, injected `BLEDevice` NUS transport, immediate disconnect propagation, service caching, graceful Qt shutdown, and interruptible capped exponential reconnect backoff.
- Typed raw and normalized IMU data.
- Six-axis Mahony quaternion orientation with startup gyro-bias calibration,
  stationary-only online bias tracking, acceleration rejection, output SLERP,
  and quaternion-relative recentering.
- Thread-safe latest sample and bounded plot history.
- Extensible Qt shell with Visualizer, Diagnostics, and Settings pages.
- Visualizer with a solid shaded torus, wear marker on the positive-X intersection, arrowed SENSOR axes, WORLD gizmo, editor grid, and orbit/pan/zoom camera controls.
- The Qt Quick 3D scene is temporarily not instantiated so transport latency
  can be measured without any 3D rendering load.
- Five-second fixed-scale plots (`±2 g`, `±500 °/s`) with raw dashed lines,
  bias-corrected solid lines, independent visibility buttons, XYZ legends,
  zero lines, time ticks, and current raw/corrected values.
- Gravity-compensated control-frame acceleration and a short-gesture direction state machine (`IDLE/START/MOVING/BRAKING`) without position integration.
- A cyan 3D motion cone whose length represents relative intensity and width represents direction confidence, plus a camera-independent six-direction panel.
- Split refresh cadence: ring at GUI rate, charts at about 30 Hz, and text metrics at 10 Hz.
- Fake source and pure-layer tests.
- Capture panel above the live Visualizer charts for `up/down/left/right/negative/continuous` trials,
  with speed/notes metadata and aligned raw/bias CSV plus JSON sidecar output.
  `Retake current` discards only the active unsaved take and preserves metadata
  and all previously saved trials.
- Idle-gated and negative-rejecting cosine direction model trained on 24
  `up/normal`, 36 `down/normal`, and 53 `negative/normal` trials; model artifact
  is `models/up_down_direction.json`.
- Live direction state machine consumes bias-corrected gyro samples, stores
  bounded detected-action events, and overlays time-aligned labeled regions on
  both Visualizer charts without putting recognition logic in Qt.
- Rejected candidates appear as gray diagnostic regions and are appended to
  `data/logs/recognition.jsonl` with candidate class, rejection reason,
  similarity, direction coherence, timing, peak, and full gyro trace.
- Morse Input page consuming accepted gesture events as `0`, `1`, and compile.

## Verified

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/pp/anaconda3/envs/zilo-ring/bin/python -m pytest -q`: 65 passed.
- The official OpenZilo SDK `0.5.0` imports successfully and accepts the
  custom transport through `OpenZiloClient(transport=...)`.
- The application transport uses Bleak 3 scanning through `hci0` and BlueZ
  service caching; real hardware validation after the OpenZilo migration is
  still required.
- Real ring lifecycle passed two consecutive connect, IMU stream, and clean stop cycles after recovering an intentionally retained BlueZ connection; receive rate was about 113 Hz.
- A 12-second stationary real-ring sample collected 1225 samples, estimated the
  gyro bias as approximately `(19.01, -30.59, 5.64) degrees/s`, and changed by
  about `0.025 degrees` in quaternion attitude over the final settled interval.
- A later direct-BLE measurement found the current firmware returning nominal
  `100 Hz` while actually delivering 31 samples about every 495 ms (`62.41 Hz`,
  no sequence loss). Qt with dual charts and no 3D measured `66.94 Hz`, also
  with no loss. The 500 ms batching is therefore upstream of Qt; stale timeout
  is 1200 ms to tolerate one delayed batch.
- Offscreen Qt smoke test creates three registered pages and receives about 100 Hz from the fake source.
- Desktop Qt Quick 3D smoke test loads the solid scene without QML errors.
- Core, ports, processing, state, and application layers do not import PySide6,
  Bleak, or the OpenZilo SDK.
- The `up/down` chronological holdout scored 15/15, leave-one-out scored 60/60,
  and 120 captured pre/post stationary segments produced zero activity-gate
  false positives. This does not yet validate unrelated hand motion.
- Streaming replay of all 60 training-session files emitted exactly one event
  per file with 60/60 labels, no missed events, and no duplicate events.
- Direction coherence cleanly separated captured positives (minimum 0.824)
  from negatives (maximum 0.266). Chronological negative holdout had 0/14
  false accepts; full streaming replay emitted 24 up, 36 down, and zero events
  for all 53 negative files.
- A later natural live test exposed cross-session wear shift: ten clean up
  candidates had similarity 0.949-0.959 with coherence 0.875-0.981. Similarity
  rejection is therefore 0.90 while coherence remains 0.545; counterfactual
  replay accepts those 10/10 up and 11/11 down while still rejecting all 53
  captured negatives.
- Python 3.12 `zilo-ring` environment loads Capture, Morse Input, and Settings.
  LeRobot, Torch, OpenCV, CUDA, and SO-ARM packages are not installed.

## Remaining verification

- Confirm sensor-axis signs and deliberate slow/fast rotations with physical
  motion; static stability alone does not validate dynamic tracking.
- Repeat the physical BLE stream check after the ring is awake and advertising;
  the environment migration check reached the expected `Ring not found` path
  while the target MAC was absent from a direct BlueZ scan.
