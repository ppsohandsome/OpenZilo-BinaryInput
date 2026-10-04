from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence


Vector3Tuple = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class TemporalWaveform:
    values: tuple[float, ...]
    active_start_s: float
    active_end_s: float
    peak_gyro_dps: float


@dataclass(frozen=True, slots=True)
class TemporalExample:
    label: str
    unit_vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class TemporalPrediction:
    label: str
    candidate_label: str
    confidence: float
    vote_margin: float
    nearest_distance: float
    scores: dict[str, float]
    rejection_reason: str | None


@dataclass(frozen=True, slots=True)
class TemporalWaveformModel:
    labels: tuple[str, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    examples: tuple[TemporalExample, ...]
    before_peak_s: float = 0.45
    after_peak_s: float = 0.85
    sample_points: int = 65
    neighbors: int = 5
    activity_threshold_dps: float = 20.0
    min_peak_gyro_dps: float = 60.0
    max_nearest_distance: float = 0.70
    min_confidence: float = 0.70
    negative_label: str = "gesture_negative_v2"
    rejected_label: str = "rejected"

    def extract(
        self,
        timestamps_ms: Sequence[float],
        gyro_xyz_dps: Sequence[Vector3Tuple],
        accel_xyz_g: Sequence[Vector3Tuple],
    ) -> TemporalWaveform | None:
        return extract_temporal_waveform(
            timestamps_ms,
            gyro_xyz_dps,
            accel_xyz_g,
            before_peak_s=self.before_peak_s,
            after_peak_s=self.after_peak_s,
            sample_points=self.sample_points,
            activity_threshold_dps=self.activity_threshold_dps,
            min_peak_gyro_dps=self.min_peak_gyro_dps,
        )

    def predict(self, waveform: TemporalWaveform) -> TemporalPrediction:
        if len(waveform.values) != len(self.feature_mean):
            raise ValueError("Temporal waveform feature length does not match model")
        standardized = tuple(
            (value - mean) / scale
            for value, mean, scale in zip(
                waveform.values,
                self.feature_mean,
                self.feature_scale,
                strict=True,
            )
        )
        unit = _unit_vector(standardized)
        if unit is None:
            return TemporalPrediction(
                label=self.rejected_label,
                candidate_label=self.negative_label,
                confidence=0.0,
                vote_margin=0.0,
                nearest_distance=1.0,
                scores={label: 0.0 for label in self.labels},
                rejection_reason="empty_waveform",
            )

        nearest = sorted(
            (
                (1.0 - _dot(unit, example.unit_vector), example.label)
                for example in self.examples
            ),
            key=lambda item: item[0],
        )[: self.neighbors]
        votes = {label: 0.0 for label in self.labels}
        for distance, label in nearest:
            votes[label] += max(0.0, 1.0 - distance)
        total = sum(votes.values())
        scores = (
            {label: value / total for label, value in votes.items()}
            if total > 1e-12
            else {label: 0.0 for label in self.labels}
        )
        ranked = sorted(scores, key=scores.get, reverse=True)
        candidate_label = ranked[0]
        confidence = scores[candidate_label]
        runner_up = scores[ranked[1]] if len(ranked) > 1 else 0.0
        vote_margin = confidence - runner_up
        nearest_distance = nearest[0][0] if nearest else 1.0
        rejection_reason = None
        if candidate_label == self.negative_label:
            rejection_reason = "negative_class"
        elif nearest_distance > self.max_nearest_distance:
            rejection_reason = "out_of_distribution"
        elif confidence < self.min_confidence:
            rejection_reason = "low_confidence"
        return TemporalPrediction(
            label=self.rejected_label if rejection_reason else candidate_label,
            candidate_label=candidate_label,
            confidence=confidence,
            vote_margin=vote_margin,
            nearest_distance=nearest_distance,
            scores=scores,
            rejection_reason=rejection_reason,
        )

    def save(self, path: Path, *, training_summary: dict[str, object]) -> None:
        payload = {
            "model_type": "temporal_waveform_knn",
            "version": 1,
            "labels": list(self.labels),
            "negative_label": self.negative_label,
            "rejected_label": self.rejected_label,
            "feature": {
                "before_peak_s": self.before_peak_s,
                "after_peak_s": self.after_peak_s,
                "sample_points": self.sample_points,
                "activity_threshold_dps": self.activity_threshold_dps,
                "min_peak_gyro_dps": self.min_peak_gyro_dps,
            },
            "classifier": {
                "neighbors": self.neighbors,
                "max_nearest_distance": self.max_nearest_distance,
                "min_confidence": self.min_confidence,
            },
            "feature_mean": list(self.feature_mean),
            "feature_scale": list(self.feature_scale),
            "examples": [
                {"label": example.label, "unit_vector": list(example.unit_vector)}
                for example in self.examples
            ],
            "training_summary": training_summary,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> TemporalWaveformModel:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("model_type") != "temporal_waveform_knn":
            raise ValueError(f"Unsupported temporal model: {path}")
        feature = payload["feature"]
        classifier = payload["classifier"]
        return cls(
            labels=tuple(str(value) for value in payload["labels"]),
            feature_mean=tuple(float(value) for value in payload["feature_mean"]),
            feature_scale=tuple(float(value) for value in payload["feature_scale"]),
            examples=tuple(
                TemporalExample(
                    label=str(example["label"]),
                    unit_vector=tuple(
                        float(value) for value in example["unit_vector"]
                    ),
                )
                for example in payload["examples"]
            ),
            before_peak_s=float(feature["before_peak_s"]),
            after_peak_s=float(feature["after_peak_s"]),
            sample_points=int(feature["sample_points"]),
            neighbors=int(classifier["neighbors"]),
            activity_threshold_dps=float(feature["activity_threshold_dps"]),
            min_peak_gyro_dps=float(feature["min_peak_gyro_dps"]),
            max_nearest_distance=float(classifier["max_nearest_distance"]),
            min_confidence=float(classifier.get("min_confidence", 0.70)),
            negative_label=str(payload["negative_label"]),
            rejected_label=str(payload["rejected_label"]),
        )

    @classmethod
    def fit(
        cls,
        examples: Iterable[tuple[str, TemporalWaveform]],
        *,
        labels: Sequence[str],
        before_peak_s: float = 0.45,
        after_peak_s: float = 0.85,
        sample_points: int = 65,
        neighbors: int = 5,
        activity_threshold_dps: float = 20.0,
        min_peak_gyro_dps: float = 60.0,
        max_nearest_distance: float = 0.70,
        min_confidence: float = 0.70,
        negative_label: str = "gesture_negative_v2",
    ) -> TemporalWaveformModel:
        items = list(examples)
        if not items:
            raise ValueError("At least one temporal training example is required")
        values = [waveform.values for _, waveform in items]
        feature_length = len(values[0])
        if any(len(value) != feature_length for value in values):
            raise ValueError("Temporal training feature lengths differ")
        mean = tuple(
            sum(value[index] for value in values) / len(values)
            for index in range(feature_length)
        )
        scale = []
        for index in range(feature_length):
            variance = sum(
                (value[index] - mean[index]) ** 2 for value in values
            ) / len(values)
            scale.append(max(1e-3, math.sqrt(variance)))
        normalized = []
        for label, waveform in items:
            standardized = tuple(
                (value - center) / spread
                for value, center, spread in zip(
                    waveform.values, mean, scale, strict=True
                )
            )
            unit = _unit_vector(standardized)
            if unit is None:
                continue
            normalized.append(TemporalExample(label=label, unit_vector=unit))
        if not normalized:
            raise ValueError("Temporal training examples have no usable variation")
        return cls(
            labels=tuple(labels),
            feature_mean=mean,
            feature_scale=tuple(scale),
            examples=tuple(normalized),
            before_peak_s=before_peak_s,
            after_peak_s=after_peak_s,
            sample_points=sample_points,
            neighbors=neighbors,
            activity_threshold_dps=activity_threshold_dps,
            min_peak_gyro_dps=min_peak_gyro_dps,
            max_nearest_distance=max_nearest_distance,
            min_confidence=min_confidence,
            negative_label=negative_label,
        )


def extract_temporal_waveform(
    timestamps_ms: Sequence[float],
    gyro_xyz_dps: Sequence[Vector3Tuple],
    accel_xyz_g: Sequence[Vector3Tuple],
    *,
    before_peak_s: float = 0.45,
    after_peak_s: float = 0.85,
    sample_points: int = 65,
    activity_threshold_dps: float = 20.0,
    min_peak_gyro_dps: float = 60.0,
) -> TemporalWaveform | None:
    if not (len(timestamps_ms) == len(gyro_xyz_dps) == len(accel_xyz_g)):
        raise ValueError("Temporal waveform channel lengths differ")
    if len(timestamps_ms) < 2 or sample_points < 2:
        return None
    origin_ms = float(timestamps_ms[0])
    times_s = tuple((float(value) - origin_ms) / 1000.0 for value in timestamps_ms)
    if any(right <= left for left, right in zip(times_s, times_s[1:])):
        return None
    gyro_norms = tuple(_norm(value) for value in gyro_xyz_dps)
    peak_gyro = max(gyro_norms)
    if peak_gyro < min_peak_gyro_dps:
        return None
    peak_index = max(range(len(gyro_norms)), key=gyro_norms.__getitem__)
    center_s = times_s[peak_index]
    grid = tuple(
        center_s
        - before_peak_s
        + index * (before_peak_s + after_peak_s) / (sample_points - 1)
        for index in range(sample_points)
    )
    channels = tuple(zip(*gyro_xyz_dps, strict=True)) + tuple(
        zip(*accel_xyz_g, strict=True)
    )
    resampled = [
        _interpolate_series(times_s, tuple(float(value) for value in channel), grid)
        for channel in channels
    ]
    baseline_samples = max(2, sample_points // 8)
    for axis in range(3, 6):
        baseline = median(resampled[axis][:baseline_samples])
        resampled[axis] = tuple(value - baseline for value in resampled[axis])
    values = tuple(
        resampled[channel][index]
        for index in range(sample_points)
        for channel in range(6)
    )
    active = [
        index for index, value in enumerate(gyro_norms) if value >= activity_threshold_dps
    ]
    start_s = times_s[active[0]] if active else center_s
    end_s = times_s[active[-1]] if active else center_s
    return TemporalWaveform(
        values=values,
        active_start_s=start_s,
        active_end_s=end_s,
        peak_gyro_dps=peak_gyro,
    )


def _interpolate_series(
    times: Sequence[float],
    values: Sequence[float],
    targets: Sequence[float],
) -> tuple[float, ...]:
    result = []
    right_index = 1
    for target in targets:
        if target <= times[0]:
            result.append(values[0])
            continue
        if target >= times[-1]:
            result.append(values[-1])
            continue
        while right_index < len(times) - 1 and times[right_index] < target:
            right_index += 1
        left_index = right_index - 1
        span = times[right_index] - times[left_index]
        fraction = (target - times[left_index]) / span
        result.append(
            values[left_index]
            + fraction * (values[right_index] - values[left_index])
        )
    return tuple(result)


def _unit_vector(values: Sequence[float]) -> tuple[float, ...] | None:
    length = math.sqrt(sum(value * value for value in values))
    if length <= 1e-12:
        return None
    return tuple(value / length for value in values)


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
