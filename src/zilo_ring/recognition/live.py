from __future__ import annotations

from collections import deque
import math

from zilo_ring.domain import DetectedAction, IMUSample

from .direction_model import DirectionTemplateModel, extract_trial_features


class LiveDirectionRecognizer:
    """Segment and classify completed gestures from bias-corrected IMU samples."""

    def __init__(self, model: DirectionTemplateModel) -> None:
        self._model = model
        self._recent_norms: deque[float] = deque(maxlen=5)
        self._pre_roll: deque[IMUSample] = deque(maxlen=4)
        self._candidate: list[IMUSample] | None = None
        self._inactive_samples = 0

    @property
    def active(self) -> bool:
        return self._candidate is not None

    def update(self, sample: IMUSample) -> DetectedAction | None:
        gyro = sample.gyro_dps
        norm = math.sqrt(gyro.x * gyro.x + gyro.y * gyro.y + gyro.z * gyro.z)
        self._recent_norms.append(norm)
        smoothed_norm = sum(self._recent_norms) / len(self._recent_norms)
        above_threshold = smoothed_norm >= self._model.activity_threshold_dps

        if self._candidate is None:
            if not above_threshold:
                self._pre_roll.append(sample)
                return None
            self._candidate = [*self._pre_roll, sample]
            self._inactive_samples = 0
            return None

        self._candidate.append(sample)
        if above_threshold:
            self._inactive_samples = 0
            return None
        self._inactive_samples += 1
        if self._inactive_samples <= 5:
            return None
        return self._finish_candidate()

    def reset(self) -> None:
        self._recent_norms.clear()
        self._pre_roll.clear()
        self._candidate = None
        self._inactive_samples = 0

    def _finish_candidate(self) -> DetectedAction | None:
        samples = self._candidate or []
        self._candidate = None
        self._inactive_samples = 0
        self._pre_roll.clear()
        self._pre_roll.extend(samples[-4:])
        timestamps = tuple(sample.device_timestamp_ms for sample in samples)
        gyro = tuple(sample.gyro_dps.as_tuple() for sample in samples)
        features = extract_trial_features(timestamps, gyro)
        if features is None:
            return None
        scores = self._model.scores(features)
        candidate_label = max(scores, key=scores.get)
        similarity = scores[candidate_label]
        label = self._model.predict_features(features)
        rejection_reasons = []
        if similarity < self._model.min_similarity:
            rejection_reasons.append("similarity")
        if features.direction_coherence < self._model.min_direction_coherence:
            rejection_reasons.append("direction_coherence")
        rejection_reason = "+".join(rejection_reasons) or None
        origin_ms = timestamps[0]
        return DetectedAction(
            label=label,
            candidate_label=candidate_label,
            start_device_timestamp_ms=round(origin_ms + features.active_start_s * 1000.0),
            end_device_timestamp_ms=round(origin_ms + features.active_end_s * 1000.0),
            similarity=similarity,
            direction_coherence=features.direction_coherence,
            peak_gyro_dps=features.peak_gyro_dps,
            rejection_reason=rejection_reason,
            gyro_trace=tuple(
                (
                    sample.device_timestamp_ms,
                    sample.gyro_dps.x,
                    sample.gyro_dps.y,
                    sample.gyro_dps.z,
                )
                for sample in samples
            ),
        )
