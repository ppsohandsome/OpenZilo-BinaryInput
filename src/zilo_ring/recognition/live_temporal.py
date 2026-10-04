from __future__ import annotations

from collections import deque
import math

from zilo_ring.domain import DetectedAction, IMUSample

from .temporal_model import TemporalWaveformModel


class LiveTemporalGestureRecognizer:
    """Segment complete rebound gestures and classify their temporal waveform."""

    def __init__(
        self,
        model: TemporalWaveformModel,
        *,
        quiet_duration_ms: int = 150,
        refractory_duration_ms: int = 300,
        max_candidate_duration_ms: int = 2_500,
    ) -> None:
        self._model = model
        self._quiet_duration_ms = quiet_duration_ms
        self._refractory_duration_ms = refractory_duration_ms
        self._max_candidate_duration_ms = max_candidate_duration_ms
        self._recent_norms: deque[float] = deque(maxlen=5)
        pre_roll_samples = max(8, round(model.before_peak_s * 120) + 5)
        self._pre_roll: deque[IMUSample] = deque(maxlen=pre_roll_samples)
        self._candidate: list[IMUSample] | None = None
        self._last_active_timestamp_ms: int | None = None
        self._ignore_until_timestamp_ms: int | None = None

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
            if (
                self._ignore_until_timestamp_ms is not None
                and sample.device_timestamp_ms < self._ignore_until_timestamp_ms
            ):
                self._pre_roll.append(sample)
                return None
            self._ignore_until_timestamp_ms = None
            if not above_threshold:
                self._pre_roll.append(sample)
                return None
            self._candidate = [*self._pre_roll, sample]
            self._last_active_timestamp_ms = sample.device_timestamp_ms
            return None

        self._candidate.append(sample)
        if above_threshold:
            self._last_active_timestamp_ms = sample.device_timestamp_ms
        candidate_duration_ms = (
            sample.device_timestamp_ms - self._candidate[0].device_timestamp_ms
        )
        quiet_duration_ms = (
            0
            if self._last_active_timestamp_ms is None
            else sample.device_timestamp_ms - self._last_active_timestamp_ms
        )
        if (
            quiet_duration_ms < self._quiet_duration_ms
            and candidate_duration_ms < self._max_candidate_duration_ms
        ):
            return None
        return self._finish_candidate()

    def reset(self) -> None:
        self._recent_norms.clear()
        self._pre_roll.clear()
        self._candidate = None
        self._last_active_timestamp_ms = None
        self._ignore_until_timestamp_ms = None

    def _finish_candidate(self) -> DetectedAction:
        samples = self._candidate or []
        self._candidate = None
        self._last_active_timestamp_ms = None
        self._ignore_until_timestamp_ms = (
            samples[-1].device_timestamp_ms + self._refractory_duration_ms
            if samples
            else None
        )
        self._pre_roll.clear()
        self._pre_roll.extend(samples[-self._pre_roll.maxlen :])
        timestamps = tuple(sample.device_timestamp_ms for sample in samples)
        gyro = tuple(sample.gyro_dps.as_tuple() for sample in samples)
        accel = tuple(sample.accel_g.as_tuple() for sample in samples)
        waveform = self._model.extract(timestamps, gyro, accel)
        if waveform is None:
            return self._event(
                samples,
                label=self._model.rejected_label,
                candidate_label=self._model.negative_label,
                start_timestamp_ms=timestamps[0],
                end_timestamp_ms=timestamps[-1],
                confidence=0.0,
                margin=0.0,
                peak=max((_norm(value) for value in gyro), default=0.0),
                rejection_reason="below_peak_threshold",
                class_scores=(),
            )
        prediction = self._model.predict(waveform)
        origin_ms = timestamps[0]
        return self._event(
            samples,
            label=prediction.label,
            candidate_label=prediction.candidate_label,
            start_timestamp_ms=round(origin_ms + waveform.active_start_s * 1000.0),
            end_timestamp_ms=round(origin_ms + waveform.active_end_s * 1000.0),
            confidence=prediction.confidence,
            margin=prediction.vote_margin,
            peak=waveform.peak_gyro_dps,
            rejection_reason=prediction.rejection_reason,
            class_scores=tuple(prediction.scores.items()),
        )

    @staticmethod
    def _event(
        samples: list[IMUSample],
        *,
        label: str,
        candidate_label: str,
        start_timestamp_ms: int,
        end_timestamp_ms: int,
        confidence: float,
        margin: float,
        peak: float,
        rejection_reason: str | None,
        class_scores: tuple[tuple[str, float], ...],
    ) -> DetectedAction:
        return DetectedAction(
            label=label,
            candidate_label=candidate_label,
            start_device_timestamp_ms=start_timestamp_ms,
            end_device_timestamp_ms=end_timestamp_ms,
            similarity=confidence,
            direction_coherence=margin,
            peak_gyro_dps=peak,
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
            accel_trace=tuple(
                (
                    sample.device_timestamp_ms,
                    sample.accel_g.x,
                    sample.accel_g.y,
                    sample.accel_g.z,
                )
                for sample in samples
            ),
            class_scores=class_scores,
            primary_score_name="confidence",
            secondary_score_name="vote_margin",
        )


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(sum(value * value for value in vector))
