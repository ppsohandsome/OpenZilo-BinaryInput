from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from zilo_ring.domain import Orientation, Vector3


@dataclass(frozen=True, slots=True)
class _QueuedIMU:
    timestamp_ms: int
    accel_g: Vector3
    gyro_dps: Vector3


class LegacyVisualOrientationEstimator:
    """The original dashboard's deliberately insensitive visual attitude path."""

    def __init__(
        self,
        *,
        calibration_duration_ms: int = 1200,
        visual_delay_ms: int = 70,
        high_pass_tau_s: float = 0.45,
        stationary_gyro_threshold_dps: float = 360.0 * 2000.0 / 32768.0,
        stationary_accel_tolerance_g: float = 0.18,
        stationary_hold_ms: int = 450,
    ) -> None:
        self.calibration_duration_ms = calibration_duration_ms
        self.visual_delay_ms = visual_delay_ms
        self.high_pass_tau_s = high_pass_tau_s
        self.stationary_gyro_threshold_dps = stationary_gyro_threshold_dps
        self.stationary_accel_tolerance_g = stationary_accel_tolerance_g
        self.stationary_hold_ms = stationary_hold_ms
        self.reset()

    def update(self, accel_g: Vector3, gyro_dps: Vector3, timestamp_ms: int) -> Orientation:
        self._queue.append(_QueuedIMU(timestamp_ms, accel_g, gyro_dps))
        target_timestamp_ms = timestamp_ms - self.visual_delay_ms
        while self._queue and self._queue[0].timestamp_ms <= target_timestamp_ms:
            self._process(self._queue.popleft())
        return self.current()

    def current(self) -> Orientation:
        return _quaternion_to_euler(self._q)

    @property
    def calibrated(self) -> bool:
        return self._calibrated

    @property
    def gyro_bias_dps(self) -> Vector3:
        return self._gyro_bias

    def recenter(self) -> None:
        self._reset_attitude()
        self._queue.clear()

    def reset(self) -> None:
        self._queue: deque[_QueuedIMU] = deque()
        self._calibrated = False
        self._calibration_started_ms: int | None = None
        self._calibration_sum = Vector3(0.0, 0.0, 0.0)
        self._calibration_count = 0
        self._gyro_bias = Vector3(0.0, 0.0, 0.0)
        self._reset_attitude()

    def _reset_attitude(self) -> None:
        self._q = [1.0, 0.0, 0.0, 0.0]
        self._previous_timestamp_ms: int | None = None
        self._hp_previous_input = Vector3(0.0, 0.0, 0.0)
        self._hp_previous_output = Vector3(0.0, 0.0, 0.0)
        self._hp_initialized = False
        self._stationary_since_ms: int | None = None
        self._stationary_bias_applied = False

    def _process(self, sample: _QueuedIMU) -> None:
        dt = self._sample_dt(sample.timestamp_ms)
        if not self._calibrated:
            self._collect_calibration(sample)
            return

        corrected_gyro = _subtract(sample.gyro_dps, self._gyro_bias)
        stationary = (
            abs(sample.accel_g.magnitude - 1.0) < self.stationary_accel_tolerance_g
            and corrected_gyro.magnitude < self.stationary_gyro_threshold_dps
        )
        if stationary:
            if self._stationary_since_ms is None:
                self._stationary_since_ms = sample.timestamp_ms
            if (
                not self._stationary_bias_applied
                and sample.timestamp_ms - self._stationary_since_ms >= self.stationary_hold_ms
            ):
                # Original implementation snapped to the latest stationary sample.
                self._gyro_bias = sample.gyro_dps
                self._hp_initialized = False
                self._stationary_bias_applied = True
            return

        self._stationary_since_ms = None
        self._stationary_bias_applied = False
        filtered_gyro = self._high_pass(corrected_gyro, dt)
        self._integrate(filtered_gyro, dt)

    def _collect_calibration(self, sample: _QueuedIMU) -> None:
        if self._calibration_started_ms is None:
            self._calibration_started_ms = sample.timestamp_ms
        self._calibration_sum = _add(self._calibration_sum, sample.gyro_dps)
        self._calibration_count += 1
        if sample.timestamp_ms - self._calibration_started_ms < self.calibration_duration_ms:
            return
        self._gyro_bias = _scale(self._calibration_sum, 1.0 / self._calibration_count)
        self._calibrated = True
        self._reset_attitude()

    def _sample_dt(self, timestamp_ms: int) -> float:
        if self._previous_timestamp_ms is None:
            dt = 0.001
        else:
            dt = (timestamp_ms - self._previous_timestamp_ms) / 1000.0
            dt = min(0.05, max(0.001, dt))
        self._previous_timestamp_ms = timestamp_ms
        return dt

    def _high_pass(self, value: Vector3, dt: float) -> Vector3:
        if not self._hp_initialized:
            self._hp_previous_input = value
            self._hp_previous_output = Vector3(0.0, 0.0, 0.0)
            self._hp_initialized = True
            return self._hp_previous_output
        alpha = self.high_pass_tau_s / (self.high_pass_tau_s + dt)
        output = Vector3(
            alpha * (self._hp_previous_output.x + value.x - self._hp_previous_input.x),
            alpha * (self._hp_previous_output.y + value.y - self._hp_previous_input.y),
            alpha * (self._hp_previous_output.z + value.z - self._hp_previous_input.z),
        )
        self._hp_previous_input = value
        self._hp_previous_output = output
        return output

    def _integrate(self, gyro_dps: Vector3, dt: float) -> None:
        gx, gy, gz = (math.radians(value) for value in gyro_dps.as_tuple())
        q0, q1, q2, q3 = self._q
        self._q[0] += 0.5 * (-q1 * gx - q2 * gy - q3 * gz) * dt
        self._q[1] += 0.5 * (q0 * gx + q2 * gz - q3 * gy) * dt
        self._q[2] += 0.5 * (q0 * gy - q1 * gz + q3 * gx) * dt
        self._q[3] += 0.5 * (q0 * gz + q1 * gy - q2 * gx) * dt
        norm = math.sqrt(sum(value * value for value in self._q)) or 1.0
        self._q = [value / norm for value in self._q]


def _quaternion_to_euler(q: list[float]) -> Orientation:
    w, x, y, z = q
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_term = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(pitch_term)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return Orientation(*(math.degrees(value) for value in (roll, pitch, yaw)))


def _add(left: Vector3, right: Vector3) -> Vector3:
    return Vector3(left.x + right.x, left.y + right.y, left.z + right.z)


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return Vector3(left.x - right.x, left.y - right.y, left.z - right.z)


def _scale(value: Vector3, factor: float) -> Vector3:
    return Vector3(value.x * factor, value.y * factor, value.z * factor)
