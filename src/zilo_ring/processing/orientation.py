from __future__ import annotations

import math
from typing import Protocol

from zilo_ring.domain import IMUSample, Orientation


Quaternion = tuple[float, float, float, float]


class OrientationEstimator(Protocol):
    def update(self, sample: IMUSample) -> Orientation: ...

    def current(self) -> Orientation: ...

    def fused(self) -> Orientation: ...

    @property
    def recenter_yaw_deg(self) -> float: ...

    def recenter(self) -> None: ...

    def reset(self) -> None: ...


class MahonyOrientationEstimator:
    """Six-axis quaternion attitude using gravity to constrain roll/pitch.

    Gyroscope bias is deliberately handled by ``IMUBiasEstimator`` upstream.
    Accelerometer feedback is reduced while its magnitude is unlike gravity,
    so hand acceleration is not mistaken for tilt.
    """

    def __init__(
        self,
        *,
        kp: float = 2.0,
        ki: float = 0.0,
        accel_rejection_g: float = 0.15,
        output_smoothing_tau_s: float = 0.055,
        max_dt_s: float = 0.05,
    ) -> None:
        if kp < 0.0 or ki < 0.0:
            raise ValueError("kp and ki must be non-negative")
        if accel_rejection_g <= 0.0:
            raise ValueError("accel_rejection_g must be positive")
        if output_smoothing_tau_s < 0.0:
            raise ValueError("output_smoothing_tau_s must be non-negative")
        if max_dt_s <= 0.0:
            raise ValueError("max_dt_s must be positive")

        self.kp = kp
        self.ki = ki
        self.accel_rejection_g = accel_rejection_g
        self.output_smoothing_tau_s = output_smoothing_tau_s
        self.max_dt_s = max_dt_s
        self.reset()

    def update(self, sample: IMUSample) -> Orientation:
        ax, ay, az = sample.accel_g.as_tuple()
        accel_norm = math.sqrt(ax * ax + ay * ay + az * az)

        if not self._initialized:
            if accel_norm > 1e-6:
                roll = math.atan2(ay, az)
                pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))
                self._quaternion = _quaternion_from_euler(roll, pitch, 0.0)
            self._display_quaternion = self._relative_quaternion()
            self._last_device_timestamp_ms = sample.device_timestamp_ms
            self._initialized = True
            return self.current()

        raw_dt = (sample.device_timestamp_ms - self._last_device_timestamp_ms) / 1000.0
        self._last_device_timestamp_ms = sample.device_timestamp_ms
        if raw_dt <= 0.0:
            return self.current()
        dt = min(self.max_dt_s, raw_dt)

        gx = math.radians(sample.gyro_dps.x)
        gy = math.radians(sample.gyro_dps.y)
        gz = math.radians(sample.gyro_dps.z)

        if accel_norm > 1e-6:
            ax /= accel_norm
            ay /= accel_norm
            az /= accel_norm
            gravity_x, gravity_y, gravity_z = _gravity_in_body(self._quaternion)
            error_x = ay * gravity_z - az * gravity_y
            error_y = az * gravity_x - ax * gravity_z
            error_z = ax * gravity_y - ay * gravity_x
            accel_error = abs(accel_norm - 1.0)
            accel_weight = max(0.0, 1.0 - accel_error / self.accel_rejection_g)

            if self.ki > 0.0 and accel_weight > 0.0:
                self._integral_error[0] += self.ki * accel_weight * error_x * dt
                self._integral_error[1] += self.ki * accel_weight * error_y * dt
                self._integral_error[2] += self.ki * accel_weight * error_z * dt
            gx += self.kp * accel_weight * error_x + self._integral_error[0]
            gy += self.kp * accel_weight * error_y + self._integral_error[1]
            gz += self.kp * accel_weight * error_z + self._integral_error[2]

        self._quaternion = _integrate_gyro(self._quaternion, gx, gy, gz, dt)
        relative = self._relative_quaternion()
        if self.output_smoothing_tau_s == 0.0:
            self._display_quaternion = relative
        else:
            smoothing = 1.0 - math.exp(-dt / self.output_smoothing_tau_s)
            self._display_quaternion = _quaternion_slerp(
                self._display_quaternion,
                relative,
                smoothing,
            )
        return self.current()

    def current(self) -> Orientation:
        return _quaternion_to_orientation(self._display_quaternion)

    def fused(self) -> Orientation:
        """Gravity-referenced attitude before the user recenter transform."""
        return _quaternion_to_orientation(self._quaternion)

    @property
    def recenter_yaw_deg(self) -> float:
        return self._recenter_yaw_deg

    def recenter(self) -> None:
        self._reference_quaternion = self._quaternion
        self._recenter_yaw_deg = self.fused().yaw_deg
        self._display_quaternion = (1.0, 0.0, 0.0, 0.0)

    def reset(self) -> None:
        self._quaternion: Quaternion = (1.0, 0.0, 0.0, 0.0)
        self._reference_quaternion: Quaternion = (1.0, 0.0, 0.0, 0.0)
        self._display_quaternion: Quaternion = (1.0, 0.0, 0.0, 0.0)
        self._integral_error = [0.0, 0.0, 0.0]
        self._last_device_timestamp_ms: int | None = None
        self._recenter_yaw_deg = 0.0
        self._initialized = False

    def _relative_quaternion(self) -> Quaternion:
        return _quaternion_normalize(
            _quaternion_multiply(
                _quaternion_conjugate(self._reference_quaternion),
                self._quaternion,
            )
        )


class ComplementaryOrientationEstimator:
    """Low-latency six-axis orientation with gravity-corrected roll and pitch."""

    def __init__(self, alpha: float = 0.98) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        self.alpha = alpha
        self._orientation = Orientation()
        self._last_device_timestamp_ms: int | None = None
        self._zero = Orientation()

    def update(self, sample: IMUSample) -> Orientation:
        ax, ay, az = sample.accel_g.as_tuple()
        accel_roll = math.degrees(math.atan2(ay, az))
        accel_pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))

        if self._last_device_timestamp_ms is None:
            fused = Orientation(accel_roll, accel_pitch, 0.0)
        else:
            raw_dt = (sample.device_timestamp_ms - self._last_device_timestamp_ms) / 1000.0
            dt = min(0.1, max(0.0, raw_dt))
            gyro_roll = self._orientation.roll_deg + sample.gyro_dps.x * dt
            gyro_pitch = self._orientation.pitch_deg + sample.gyro_dps.y * dt
            gyro_yaw = self._orientation.yaw_deg + sample.gyro_dps.z * dt
            fused = Orientation(
                self.alpha * gyro_roll + (1.0 - self.alpha) * accel_roll,
                self.alpha * gyro_pitch + (1.0 - self.alpha) * accel_pitch,
                _wrap_degrees(gyro_yaw),
            )

        self._last_device_timestamp_ms = sample.device_timestamp_ms
        self._orientation = fused
        return self.current()

    def current(self) -> Orientation:
        return Orientation(
            _wrap_degrees(self._orientation.roll_deg - self._zero.roll_deg),
            _wrap_degrees(self._orientation.pitch_deg - self._zero.pitch_deg),
            _wrap_degrees(self._orientation.yaw_deg - self._zero.yaw_deg),
        )

    def fused(self) -> Orientation:
        """Gravity-referenced attitude before the user display recenter offset."""
        return self._orientation

    @property
    def recenter_yaw_deg(self) -> float:
        return self._zero.yaw_deg

    def recenter(self) -> None:
        self._zero = self._orientation

    def reset(self) -> None:
        self._orientation = Orientation()
        self._zero = Orientation()
        self._last_device_timestamp_ms = None


def _wrap_degrees(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _quaternion_from_euler(roll: float, pitch: float, yaw: float) -> Quaternion:
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return _quaternion_normalize(
        (
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        )
    )


def _quaternion_to_orientation(quaternion: Quaternion) -> Orientation:
    w, x, y, z = _quaternion_normalize(quaternion)
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_term = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(pitch_term)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return Orientation(
        _wrap_degrees(math.degrees(roll)),
        _wrap_degrees(math.degrees(pitch)),
        _wrap_degrees(math.degrees(yaw)),
    )


def _gravity_in_body(quaternion: Quaternion) -> tuple[float, float, float]:
    w, x, y, z = quaternion
    return (
        2.0 * (x * z - w * y),
        2.0 * (w * x + y * z),
        w * w - x * x - y * y + z * z,
    )


def _integrate_gyro(
    quaternion: Quaternion,
    gx: float,
    gy: float,
    gz: float,
    dt: float,
) -> Quaternion:
    w, x, y, z = quaternion
    half_dt = 0.5 * dt
    return _quaternion_normalize(
        (
            w + (-x * gx - y * gy - z * gz) * half_dt,
            x + (w * gx + y * gz - z * gy) * half_dt,
            y + (w * gy - x * gz + z * gx) * half_dt,
            z + (w * gz + x * gy - y * gx) * half_dt,
        )
    )


def _quaternion_multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return (
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    )


def _quaternion_conjugate(quaternion: Quaternion) -> Quaternion:
    w, x, y, z = quaternion
    return (w, -x, -y, -z)


def _quaternion_normalize(quaternion: Quaternion) -> Quaternion:
    norm = math.sqrt(sum(component * component for component in quaternion))
    if norm <= 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(component / norm for component in quaternion)  # type: ignore[return-value]


def _quaternion_slerp(start: Quaternion, end: Quaternion, amount: float) -> Quaternion:
    amount = max(0.0, min(1.0, amount))
    dot = sum(a * b for a, b in zip(start, end, strict=True))
    if dot < 0.0:
        end = tuple(-component for component in end)  # type: ignore[assignment]
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _quaternion_normalize(
            tuple(a + amount * (b - a) for a, b in zip(start, end, strict=True))  # type: ignore[arg-type]
        )
    angle = math.acos(dot)
    sin_angle = math.sin(angle)
    start_weight = math.sin((1.0 - amount) * angle) / sin_angle
    end_weight = math.sin(amount * angle) / sin_angle
    return _quaternion_normalize(
        tuple(
            start_weight * a + end_weight * b
            for a, b in zip(start, end, strict=True)
        )  # type: ignore[arg-type]
    )
