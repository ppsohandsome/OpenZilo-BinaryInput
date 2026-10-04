# Zilo Ring: a ComBodied AI Interaction Prototype

Zilo Ring is an independent Linux desktop application built with the
[OpenZilo Python SDK](https://github.com/ziloai/OpenZilo). It explores
**ComBodied AI** through a smart-ring IMU: live motion sensing, personalized
gesture recognition, and low-friction wearable input.

> This is an independent community project. It is not an official OpenZilo
> application or an official performance benchmark.

## Demo

[Watch the 26-second desktop demo](video_move.mp4)

The demo shows the application receiving a ring IMU stream and presenting the
signal and interaction state in real time.

## What it explores

- A single smart ring as an always-available input device.
- Low-latency BLE IMU streaming on Linux.
- Live six-axis signal inspection with raw and bias-corrected traces.
- Personalized, short-gesture recognition rather than spatial-position
  estimation.
- A Morse-style input experiment that serializes recognized gestures into a
  compact wearable interaction channel.

## Architecture

```text
OpenZilo ring
    -> BLE / BlueZ transport
    -> OpenZilo Python SDK
    -> conditioned IMU pipeline
    -> gesture recognizer
    -> bounded application state
    -> PySide6 desktop interface
```

The Qt interface does not access BLE directly. Bluetooth transport, signal
conditioning, recognition, and presentation are separate layers, so future
interaction tabs can consume the same recognized-event stream without coupling
to the device connection.

## Why ComBodied AI

The goal is not to treat the ring as a miniature controller. It is to make a
small, embodied signal available to an AI or desktop workflow at the moment an
intent occurs. The current prototype focuses on reliable short gestures,
explicit uncertainty handling, and an inspectable signal path before expanding
to additional interaction modes.

## Run locally

Clone OpenZilo beside this repository, create the environment, and start the
desktop application:

```bash
conda env create -f environment.yml
conda activate zilo-ring
python main.py
```

An empty MAC field starts the virtual-ring mode. A physical ring requires
Linux BlueZ access and the ring to be in gesture mode before IMU reporting can
start.

## Privacy and release hygiene

This repository should never contain real ring MAC addresses, serial numbers,
CPUIDs, personal recordings, raw capture sessions, recognition logs, or
private trained-model artifacts. Use placeholder values in screenshots and
examples.

## Upstream relationship

OpenZilo provides the hardware-facing Python SDK. Zilo Ring remains a separate
application layer. Reusable Linux transport fixes, protocol tests, and
documentation improvements can be proposed upstream as focused contributions.
