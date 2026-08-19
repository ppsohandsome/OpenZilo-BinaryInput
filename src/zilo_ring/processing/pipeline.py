from __future__ import annotations

from dataclasses import dataclass

from zilo_ring.domain import IMUSample, MotionEstimate, Orientation, Vector3

from .motion import MotionDirectionEstimator, linear_acceleration_in_control_frame
from .orientation import ComplementaryOrientationEstimator


@dataclass(frozen=True, slots=True)
class ProcessedSample:
    sample: IMUSample
    orientation: Orientation
    linear_accel_control_g: Vector3
    motion: MotionEstimate


class ProcessingPipeline:
    def __init__(
        self,
        orientation_estimator: ComplementaryOrientationEstimator,
        motion_estimator: MotionDirectionEstimator | None = None,
    ) -> None:
        self.orientation_estimator = orientation_estimator
        self.motion_estimator = motion_estimator or MotionDirectionEstimator()

    def process(self, sample: IMUSample) -> ProcessedSample:
        orientation = self.orientation_estimator.update(sample)
        linear_accel = linear_acceleration_in_control_frame(
            sample.accel_g,
            self.orientation_estimator.fused(),
            self.orientation_estimator.recenter_yaw_deg,
        )
        return ProcessedSample(
            sample=sample,
            orientation=orientation,
            linear_accel_control_g=linear_accel,
            motion=self.motion_estimator.update(linear_accel, sample.device_timestamp_ms),
        )

    def recenter(self) -> None:
        self.orientation_estimator.recenter()
        self.motion_estimator.reset()

    def reset(self) -> None:
        self.orientation_estimator.reset()
        self.motion_estimator.reset()
