from __future__ import annotations

from dataclasses import dataclass
import math

from zilo_ring.domain import Vector3

from .filters import blend


@dataclass(frozen=True, slots=True)
class BiasCorrectedIMU:
    accel_g: Vector3
    gyro_dps: Vector3
    calibrated: bool
    became_calibrated: bool = False


class IMUBiasEstimator:
    """Startup gyro calibration plus slow stationary bias tracking."""

    def __init__(
        self,
        *,
        calibration_duration_ms: int = 1200,
        minimum_samples: int = 50,
        online_time_constant_s: float = 30.0,
    ) -> None:
        self.calibration_duration_ms = calibration_duration_ms
        self.minimum_samples = minimum_samples
        self.online_time_constant_s = online_time_constant_s
        self.reset()

    def update(
        self,
        accel_g: Vector3,
        gyro_dps: Vector3,
        timestamp_ms: int,
        *,
        stationary: bool,
    ) -> BiasCorrectedIMU:
        became_calibrated = False
        if not self.calibrated:
            if stationary:
                self._collect(accel_g, gyro_dps, timestamp_ms)
                started_ms = self._calibration_started_ms
                elapsed = 0 if started_ms is None else timestamp_ms - started_ms
                if elapsed >= self.calibration_duration_ms and self._sample_count >= self.minimum_samples:
                    self._finish_calibration()
                    became_calibrated = True
            else:
                self._clear_collection()
        elif stationary:
            self._track_gyro_bias(gyro_dps, timestamp_ms)

        corrected_accel = _subtract(accel_g, self.accel_bias_g)
        corrected_gyro = _subtract(gyro_dps, self.gyro_bias_dps)
        return BiasCorrectedIMU(
            accel_g=corrected_accel,
            gyro_dps=corrected_gyro,
            calibrated=self.calibrated,
            became_calibrated=became_calibrated,
        )

    def reset(self) -> None:
        self.calibrated = False
        self.gyro_bias_dps = Vector3(0.0, 0.0, 0.0)
        self.accel_bias_g = Vector3(0.0, 0.0, 0.0)
        self._last_online_timestamp_ms: int | None = None
        self._clear_collection()

    def _collect(self, accel_g: Vector3, gyro_dps: Vector3, timestamp_ms: int) -> None:
        if self._calibration_started_ms is None:
            self._calibration_started_ms = timestamp_ms
        self._accel_sum = _add(self._accel_sum, accel_g)
        self._gyro_sum = _add(self._gyro_sum, gyro_dps)
        self._sample_count += 1

    def _finish_calibration(self) -> None:
        mean_accel = _scale(self._accel_sum, 1.0 / self._sample_count)
        self.gyro_bias_dps = _scale(self._gyro_sum, 1.0 / self._sample_count)

        # One static pose cannot identify a full 3-axis accelerometer bias. This
        # only corrects the observed gravity-vector magnitude to 1 g.
        magnitude = mean_accel.magnitude
        if magnitude > 1e-9:
            self.accel_bias_g = _scale(mean_accel, (magnitude - 1.0) / magnitude)
        self.calibrated = True
        self._last_online_timestamp_ms = None
        self._clear_collection()

    def _track_gyro_bias(self, gyro_dps: Vector3, timestamp_ms: int) -> None:
        if self._last_online_timestamp_ms is None:
            self._last_online_timestamp_ms = timestamp_ms
            return
        dt = (timestamp_ms - self._last_online_timestamp_ms) / 1000.0
        self._last_online_timestamp_ms = timestamp_ms
        if dt <= 0.0:
            return
        alpha = 1.0 - math.exp(-min(dt, 0.1) / self.online_time_constant_s)
        self.gyro_bias_dps = blend(self.gyro_bias_dps, gyro_dps, alpha)

    def _clear_collection(self) -> None:
        self._calibration_started_ms: int | None = None
        self._sample_count = 0
        self._accel_sum = Vector3(0.0, 0.0, 0.0)
        self._gyro_sum = Vector3(0.0, 0.0, 0.0)


class LinearAccelerationCorrector:
    """Learn residual linear acceleration and noise only while stationary."""

    def __init__(
        self,
        *,
        bias_time_constant_s: float = 10.0,
        noise_time_constant_s: float = 5.0,
        minimum_deadband_g: float = 0.008,
        sigma_multiplier: float = 3.0,
    ) -> None:
        self.bias_time_constant_s = bias_time_constant_s
        self.noise_time_constant_s = noise_time_constant_s
        self.minimum_deadband_g = minimum_deadband_g
        self.sigma_multiplier = sigma_multiplier
        self.reset()

    def update(self, value: Vector3, timestamp_ms: int, *, stationary: bool) -> Vector3:
        dt = self._elapsed_s(timestamp_ms)
        if stationary:
            if not self._initialized:
                self._bias = value
                self._initialized = True
            elif dt > 0.0:
                bias_alpha = 1.0 - math.exp(-dt / self.bias_time_constant_s)
                self._bias = blend(self._bias, value, bias_alpha)

        corrected = _subtract(value, self._bias)
        if stationary and dt > 0.0:
            noise_alpha = 1.0 - math.exp(-dt / self.noise_time_constant_s)
            squared = Vector3(corrected.x**2, corrected.y**2, corrected.z**2)
            self._noise_variance = blend(self._noise_variance, squared, noise_alpha)

        thresholds = Vector3(
            max(self.minimum_deadband_g, self.sigma_multiplier * math.sqrt(self._noise_variance.x)),
            max(self.minimum_deadband_g, self.sigma_multiplier * math.sqrt(self._noise_variance.y)),
            max(self.minimum_deadband_g, self.sigma_multiplier * math.sqrt(self._noise_variance.z)),
        )
        return Vector3(
            _soft_deadband(corrected.x, thresholds.x),
            _soft_deadband(corrected.y, thresholds.y),
            _soft_deadband(corrected.z, thresholds.z),
        )

    def reset(self) -> None:
        self._bias = Vector3(0.0, 0.0, 0.0)
        self._noise_variance = Vector3(0.0, 0.0, 0.0)
        self._initialized = False
        self._last_timestamp_ms: int | None = None

    def _elapsed_s(self, timestamp_ms: int) -> float:
        if self._last_timestamp_ms is None or timestamp_ms < self._last_timestamp_ms:
            self._last_timestamp_ms = timestamp_ms
            return 0.0
        dt = min(0.1, (timestamp_ms - self._last_timestamp_ms) / 1000.0)
        self._last_timestamp_ms = timestamp_ms
        return dt


def _soft_deadband(value: float, threshold: float) -> float:
    if abs(value) <= threshold:
        return 0.0
    return math.copysign(abs(value) - threshold, value)


def _add(left: Vector3, right: Vector3) -> Vector3:
    return Vector3(left.x + right.x, left.y + right.y, left.z + right.z)


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return Vector3(left.x - right.x, left.y - right.y, left.z - right.z)


def _scale(value: Vector3, factor: float) -> Vector3:
    return Vector3(value.x * factor, value.y * factor, value.z * factor)
