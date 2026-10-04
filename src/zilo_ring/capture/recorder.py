from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from zilo_ring.domain import IMUSample


CAPTURE_LABEL_OPTIONS = (
    ("single_press_rebound", "单次按压回弹"),
    ("up_flick_rebound", "向上弹指回弹"),
    ("double_press_rebound", "快速双次按压回弹"),
    ("gesture_negative_v2", "新手势负样本"),
    ("negative", "旧方向负样本"),
    ("up", "向上"),
    ("down", "向下"),
    ("left", "向左"),
    ("right", "向右"),
    ("continuous", "连续动作"),
)
CAPTURE_LABELS = tuple(value for value, _ in CAPTURE_LABEL_OPTIONS)
CAPTURE_LABEL_DISPLAY = dict(CAPTURE_LABEL_OPTIONS)
CAPTURE_SPEED_OPTIONS = (
    ("normal", "正常"),
    ("slow", "慢"),
    ("fast", "快"),
)
CAPTURE_SPEEDS = tuple(value for value, _ in CAPTURE_SPEED_OPTIONS)
CAPTURE_SPEED_DISPLAY = dict(CAPTURE_SPEED_OPTIONS)
CAPTURE_AMPLITUDE_OPTIONS = (
    ("normal", "正常"),
    ("small", "小"),
    ("large", "大"),
)
CAPTURE_AMPLITUDES = tuple(value for value, _ in CAPTURE_AMPLITUDE_OPTIONS)
CAPTURE_AMPLITUDE_DISPLAY = dict(CAPTURE_AMPLITUDE_OPTIONS)
CAPTURE_HAND_ANGLES_DEG = (0, 10, 20, -10, -20)
CAPTURE_NEGATIVE_LABELS = frozenset(("gesture_negative_v2", "negative"))
CAPTURE_NEGATIVE_TYPE_OPTIONS = (
    ("stationary", "完全静止"),
    ("natural_tremor", "轻微自然抖动"),
    ("wrist_rotation", "手腕旋转"),
    ("random_motion", "随机移动"),
    ("incomplete_similar", "相似但不完整的动作"),
    ("transition", "动作之间的过渡"),
)
CAPTURE_NEGATIVE_TYPES = tuple(value for value, _ in CAPTURE_NEGATIVE_TYPE_OPTIONS)
CAPTURE_NEGATIVE_TYPE_DISPLAY = dict(CAPTURE_NEGATIVE_TYPE_OPTIONS)
NOT_APPLICABLE_NEGATIVE_TYPE = "not_applicable"


@dataclass(frozen=True, slots=True)
class CaptureStatus:
    recording: bool = False
    label: str = ""
    speed: str = "normal"
    amplitude: str = "normal"
    hand_angle_deg: int = 0
    negative_type: str = NOT_APPLICABLE_NEGATIVE_TYPE
    sample_count: int = 0
    duration_s: float = 0.0
    message: str = "Ready"
    last_csv_path: Path | None = None


@dataclass(frozen=True, slots=True)
class _CaptureRow:
    label: str
    speed: str
    amplitude: str
    hand_angle_deg: int
    negative_type: str
    sequence: int
    device_timestamp_ms: int
    received_timestamp_ns: int
    elapsed_ms: float
    accel_raw_count_x: float
    accel_raw_count_y: float
    accel_raw_count_z: float
    gyro_raw_count_x: float
    gyro_raw_count_y: float
    gyro_raw_count_z: float
    accel_raw_g_x: float
    accel_raw_g_y: float
    accel_raw_g_z: float
    gyro_raw_dps_x: float
    gyro_raw_dps_y: float
    gyro_raw_dps_z: float
    accel_bias_g_x: float
    accel_bias_g_y: float
    accel_bias_g_z: float
    gyro_bias_dps_x: float
    gyro_bias_dps_y: float
    gyro_bias_dps_z: float


class CaptureRecorder:
    """Collect aligned raw/corrected samples and atomically save one trial."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self._status = CaptureStatus()
        self._rows: list[_CaptureRow] = []
        self._seen_keys: set[tuple[int, int, int]] = set()
        self._started_at: datetime | None = None
        self._exclude_through_received_ns: int | None = None
        self._notes = ""

    @property
    def status(self) -> CaptureStatus:
        return self._status

    def start(
        self,
        *,
        label: str,
        speed: str,
        amplitude: str = "normal",
        hand_angle_deg: int = 0,
        negative_type: str = NOT_APPLICABLE_NEGATIVE_TYPE,
        notes: str = "",
        exclude_through_received_ns: int | None = None,
    ) -> None:
        if self._status.recording:
            raise RuntimeError("A capture is already recording")
        if label not in CAPTURE_LABELS:
            raise ValueError(f"Unsupported capture label: {label}")
        if speed not in CAPTURE_SPEEDS:
            raise ValueError(f"Unsupported capture speed: {speed}")
        if amplitude not in CAPTURE_AMPLITUDES:
            raise ValueError(f"Unsupported capture amplitude: {amplitude}")
        if hand_angle_deg not in CAPTURE_HAND_ANGLES_DEG:
            raise ValueError(f"Unsupported hand angle: {hand_angle_deg}")
        if label in CAPTURE_NEGATIVE_LABELS:
            if negative_type not in CAPTURE_NEGATIVE_TYPES:
                raise ValueError(f"Unsupported negative type: {negative_type}")
        elif negative_type != NOT_APPLICABLE_NEGATIVE_TYPE:
            raise ValueError("Negative type is only valid for negative labels")
        self._rows = []
        self._seen_keys = set()
        self._started_at = datetime.now(timezone.utc)
        self._exclude_through_received_ns = exclude_through_received_ns
        self._notes = notes.strip()
        self._status = CaptureStatus(
            recording=True,
            label=label,
            speed=speed,
            amplitude=amplitude,
            hand_angle_deg=hand_angle_deg,
            negative_type=negative_type,
            message="Recording",
            last_csv_path=self._status.last_csv_path,
        )

    def ingest(
        self,
        raw_history: tuple[IMUSample, ...],
        bias_history: tuple[IMUSample, ...],
    ) -> None:
        if not self._status.recording:
            return
        if not raw_history:
            return
        newest = raw_history[-1]
        newest_key = (
            newest.sequence,
            newest.device_timestamp_ms,
            newest.received_timestamp_ns,
        )
        if newest_key in self._seen_keys:
            return
        bias_by_key = {
            (
                sample.sequence,
                sample.device_timestamp_ms,
                sample.received_timestamp_ns,
            ): sample
            for sample in bias_history
        }
        for raw in raw_history:
            if (
                self._exclude_through_received_ns is not None
                and raw.received_timestamp_ns <= self._exclude_through_received_ns
            ):
                continue
            key = (
                raw.sequence,
                raw.device_timestamp_ms,
                raw.received_timestamp_ns,
            )
            if key in self._seen_keys:
                continue
            bias = bias_by_key.get(key)
            if bias is None:
                continue
            self._seen_keys.add(key)
            self._append(raw, bias)
        self._update_live_status()

    def restart(self, *, exclude_through_received_ns: int | None = None) -> None:
        """Discard the unsaved take and immediately restart with its metadata."""
        if not self._status.recording:
            raise RuntimeError("No capture is recording")
        label = self._status.label
        speed = self._status.speed
        amplitude = self._status.amplitude
        hand_angle_deg = self._status.hand_angle_deg
        negative_type = self._status.negative_type
        last_csv_path = self._status.last_csv_path
        self._rows = []
        self._seen_keys = set()
        self._started_at = datetime.now(timezone.utc)
        self._exclude_through_received_ns = exclude_through_received_ns
        self._status = CaptureStatus(
            recording=True,
            label=label,
            speed=speed,
            amplitude=amplitude,
            hand_angle_deg=hand_angle_deg,
            negative_type=negative_type,
            message="Retaking current trial",
            last_csv_path=last_csv_path,
        )

    def stop(self) -> Path:
        if not self._status.recording:
            raise RuntimeError("No capture is recording")
        if not self._rows:
            self._status = CaptureStatus(
                message="No aligned IMU samples captured",
                last_csv_path=self._status.last_csv_path,
            )
            raise RuntimeError("No aligned IMU samples captured")

        started_at = self._started_at or datetime.now(timezone.utc)
        finished_at = datetime.now(timezone.utc)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = started_at.astimezone().strftime("%Y%m%d_%H%M%S_%f")
        stem = f"{timestamp}_{self._status.label}_{self._status.speed}"
        csv_path = self.output_dir / f"{stem}.csv"
        metadata_path = self.output_dir / f"{stem}.meta.json"
        csv_temp = csv_path.with_suffix(".csv.tmp")
        metadata_temp = metadata_path.with_suffix(".json.tmp")

        with csv_temp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(self._rows[0])))
            writer.writeheader()
            writer.writerows(asdict(row) for row in self._rows)

        duration_s = self._duration_s()
        metadata = {
            "label": self._status.label,
            "speed": self._status.speed,
            "amplitude": self._status.amplitude,
            "hand_angle_deg": self._status.hand_angle_deg,
            "negative_type": self._status.negative_type,
            "wear_mode": "fixed",
            "notes": self._notes,
            "sample_count": len(self._rows),
            "duration_s": duration_s,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "csv_file": csv_path.name,
            "value_order": "raw/bias",
            "accel_unit": "g",
            "gyro_unit": "degrees_per_second",
        }
        with metadata_temp.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        csv_temp.replace(csv_path)
        metadata_temp.replace(metadata_path)
        self._status = CaptureStatus(
            label=self._status.label,
            speed=self._status.speed,
            amplitude=self._status.amplitude,
            hand_angle_deg=self._status.hand_angle_deg,
            negative_type=self._status.negative_type,
            sample_count=len(self._rows),
            duration_s=duration_s,
            message="Saved",
            last_csv_path=csv_path,
        )
        return csv_path

    def _append(self, raw: IMUSample, bias: IMUSample) -> None:
        first_received_ns = (
            self._rows[0].received_timestamp_ns
            if self._rows
            else raw.received_timestamp_ns
        )
        self._rows.append(
            _CaptureRow(
                label=self._status.label,
                speed=self._status.speed,
                amplitude=self._status.amplitude,
                hand_angle_deg=self._status.hand_angle_deg,
                negative_type=self._status.negative_type,
                sequence=raw.sequence,
                device_timestamp_ms=raw.device_timestamp_ms,
                received_timestamp_ns=raw.received_timestamp_ns,
                elapsed_ms=(raw.received_timestamp_ns - first_received_ns) / 1_000_000.0,
                accel_raw_count_x=raw.accel_raw.x,
                accel_raw_count_y=raw.accel_raw.y,
                accel_raw_count_z=raw.accel_raw.z,
                gyro_raw_count_x=raw.gyro_raw.x,
                gyro_raw_count_y=raw.gyro_raw.y,
                gyro_raw_count_z=raw.gyro_raw.z,
                accel_raw_g_x=raw.accel_g.x,
                accel_raw_g_y=raw.accel_g.y,
                accel_raw_g_z=raw.accel_g.z,
                gyro_raw_dps_x=raw.gyro_dps.x,
                gyro_raw_dps_y=raw.gyro_dps.y,
                gyro_raw_dps_z=raw.gyro_dps.z,
                accel_bias_g_x=bias.accel_g.x,
                accel_bias_g_y=bias.accel_g.y,
                accel_bias_g_z=bias.accel_g.z,
                gyro_bias_dps_x=bias.gyro_dps.x,
                gyro_bias_dps_y=bias.gyro_dps.y,
                gyro_bias_dps_z=bias.gyro_dps.z,
            )
        )

    def _update_live_status(self) -> None:
        self._status = CaptureStatus(
            recording=True,
            label=self._status.label,
            speed=self._status.speed,
            amplitude=self._status.amplitude,
            hand_angle_deg=self._status.hand_angle_deg,
            negative_type=self._status.negative_type,
            sample_count=len(self._rows),
            duration_s=self._duration_s(),
            message="Recording",
            last_csv_path=self._status.last_csv_path,
        )

    def _duration_s(self) -> float:
        if len(self._rows) < 2:
            return 0.0
        return max(
            0.0,
            (self._rows[-1].received_timestamp_ns - self._rows[0].received_timestamp_ns)
            / 1_000_000_000.0,
        )
