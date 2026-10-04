from __future__ import annotations

from dataclasses import dataclass, replace

from zilo_ring.domain import IMUSample, MotionEstimate, Orientation, Vector3

from .bias import IMUBiasEstimator, LinearAccelerationCorrector
from .filters import VectorLowPassFilter
from .motion import MotionDirectionEstimator, linear_acceleration_in_control_frame
from .orientation import OrientationEstimator
from .stationary import StationaryDetector


@dataclass(frozen=True, slots=True)
class ProcessedSample:
    sample: IMUSample
    bias_corrected_sample: IMUSample
    orientation: Orientation
    linear_accel_control_g: Vector3
    motion: MotionEstimate


class ProcessingPipeline:
    def __init__(
        self,
        orientation_estimator: OrientationEstimator,
        motion_estimator: MotionDirectionEstimator | None = None,
        bias_estimator: IMUBiasEstimator | None = None,
    ) -> None:
        self.orientation_estimator = orientation_estimator
        self.motion_estimator = motion_estimator or MotionDirectionEstimator()
        self.bias_estimator = bias_estimator or IMUBiasEstimator()
        # Startup detection must tolerate the unknown gyro bias. Runtime
        # detection operates on bias-corrected gyro and is deliberately strict.
        self._calibration_stationary = StationaryDetector(
            gyro_threshold_dps=80.0,
            accel_tolerance_g=0.18,
            hold_ms=450,
        )
        self._runtime_stationary = StationaryDetector(
            gyro_threshold_dps=0.8,
            accel_tolerance_g=0.08,
            hold_ms=450,
        )
        self._accel_filter = VectorLowPassFilter(cutoff_hz=15.0)
        self._gyro_filter = VectorLowPassFilter(cutoff_hz=20.0)
        self._linear_corrector = LinearAccelerationCorrector()

    def process(self, sample: IMUSample) -> ProcessedSample:
        if self.bias_estimator.calibrated:
            gyro_for_detection = Vector3(
                sample.gyro_dps.x - self.bias_estimator.gyro_bias_dps.x,
                sample.gyro_dps.y - self.bias_estimator.gyro_bias_dps.y,
                sample.gyro_dps.z - self.bias_estimator.gyro_bias_dps.z,
            )
            stationary = self._runtime_stationary.update(
                sample.accel_g,
                gyro_for_detection,
                sample.device_timestamp_ms,
            )
        else:
            stationary = self._calibration_stationary.update(
                sample.accel_g,
                sample.gyro_dps,
                sample.device_timestamp_ms,
            )

        corrected = self.bias_estimator.update(
            sample.accel_g,
            sample.gyro_dps,
            sample.device_timestamp_ms,
            stationary=stationary,
        )
        if corrected.became_calibrated:
            self._reset_signal_state()
            self._runtime_stationary.reset()
            stationary = False

        filtered_accel = self._accel_filter.update(
            corrected.accel_g,
            sample.device_timestamp_ms,
        )
        filtered_gyro = self._gyro_filter.update(
            corrected.gyro_dps,
            sample.device_timestamp_ms,
        )
        if not corrected.calibrated or stationary:
            # Never integrate unknown startup bias. Once calibrated, a zero
            # angular-rate update prevents stationary residual noise drifting.
            filtered_gyro = Vector3(0.0, 0.0, 0.0)

        filtered_sample = replace(
            sample,
            accel_g=filtered_accel,
            gyro_dps=filtered_gyro,
        )
        bias_corrected_sample = replace(
            sample,
            accel_g=corrected.accel_g,
            gyro_dps=corrected.gyro_dps,
        )
        orientation = self.orientation_estimator.update(filtered_sample)
        linear_accel = linear_acceleration_in_control_frame(
            filtered_accel,
            self.orientation_estimator.fused(),
            self.orientation_estimator.recenter_yaw_deg,
        )
        linear_accel = self._linear_corrector.update(
            linear_accel,
            sample.device_timestamp_ms,
            stationary=corrected.calibrated and stationary,
        )
        if corrected.calibrated:
            motion = self.motion_estimator.update(linear_accel, sample.device_timestamp_ms)
        else:
            self.motion_estimator.reset()
            motion = MotionEstimate(
                linear_accel_control_g=linear_accel,
                intensity_g=linear_accel.magnitude,
            )
        return ProcessedSample(
            sample=sample,
            bias_corrected_sample=bias_corrected_sample,
            orientation=orientation,
            linear_accel_control_g=linear_accel,
            motion=motion,
        )

    def recenter(self) -> None:
        self.orientation_estimator.recenter()
        self.motion_estimator.reset()
        self._linear_corrector.reset()

    def reset(self) -> None:
        self.bias_estimator.reset()
        self._calibration_stationary.reset()
        self._runtime_stationary.reset()
        self._reset_signal_state()

    def _reset_signal_state(self) -> None:
        self.orientation_estimator.reset()
        self.motion_estimator.reset()
        self._accel_filter.reset()
        self._gyro_filter.reset()
        self._linear_corrector.reset()
