from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Iterable, Sequence


Vector = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class TrialFeatures:
    direction: Vector
    direction_coherence: float
    active_start_s: float
    active_end_s: float
    peak_gyro_dps: float
    active_samples: int


def extract_trial_features(
    device_timestamp_ms: Sequence[float],
    gyro_xyz_dps: Sequence[Vector],
    *,
    activity_threshold_dps: float = 20.0,
    smoothing_samples: int = 5,
    min_active_samples: int = 5,
    min_active_duration_s: float = 0.08,
    min_peak_gyro_dps: float = 100.0,
    max_inactive_gap_samples: int = 5,
) -> TrialFeatures | None:
    """Extract one gesture direction, or return None for an idle trial."""
    if len(device_timestamp_ms) != len(gyro_xyz_dps):
        raise ValueError("Timestamp and gyroscope lengths differ")
    if len(device_timestamp_ms) < 2:
        return None

    norms = [_norm(vector) for vector in gyro_xyz_dps]
    smoothed = _trailing_average(norms, smoothing_samples)
    above = [value >= activity_threshold_dps for value in smoothed]
    spans = _active_spans(above, max_inactive_gap_samples)
    candidates: list[tuple[float, int, int, int]] = []
    for start, end in spans:
        active_count = sum(above[start : end + 1])
        duration_s = (
            float(device_timestamp_ms[end]) - float(device_timestamp_ms[start])
        ) / 1000.0
        if active_count < min_active_samples or duration_s < min_active_duration_s:
            continue
        if max(norms[start : end + 1]) < min_peak_gyro_dps:
            continue
        energy = sum(smoothed[start : end + 1])
        candidates.append((energy, start, end, active_count))
    if not candidates:
        return None

    _, start, end, active_count = max(candidates)
    integrated = [0.0, 0.0, 0.0]
    angular_path = 0.0
    for index in range(start + 1, end + 1):
        dt_s = (
            float(device_timestamp_ms[index])
            - float(device_timestamp_ms[index - 1])
        ) / 1000.0
        if dt_s <= 0.0:
            continue
        previous = gyro_xyz_dps[index - 1]
        current = gyro_xyz_dps[index]
        angular_path += 0.5 * (norms[index - 1] + norms[index]) * dt_s
        for axis in range(3):
            integrated[axis] += 0.5 * (previous[axis] + current[axis]) * dt_s
    direction = _unit_vector(tuple(integrated))
    integrated_length = _norm(tuple(integrated))
    if direction is None or angular_path <= 1e-9:
        return None
    return TrialFeatures(
        direction=direction,
        direction_coherence=min(1.0, integrated_length / angular_path),
        active_start_s=(
            float(device_timestamp_ms[start]) - float(device_timestamp_ms[0])
        )
        / 1000.0,
        active_end_s=(
            float(device_timestamp_ms[end]) - float(device_timestamp_ms[0])
        )
        / 1000.0,
        peak_gyro_dps=max(norms[start : end + 1]),
        active_samples=active_count,
    )


@dataclass(frozen=True, slots=True)
class DirectionTemplateModel:
    templates: dict[str, Vector]
    activity_threshold_dps: float = 20.0
    min_similarity: float = 0.90
    min_direction_coherence: float = 0.55
    idle_label: str = "idle"
    rejected_label: str = "rejected"

    @classmethod
    def fit(
        cls,
        examples: Iterable[tuple[str, TrialFeatures]],
        *,
        activity_threshold_dps: float = 20.0,
        min_similarity: float = 0.90,
        min_direction_coherence: float = 0.55,
    ) -> DirectionTemplateModel:
        grouped: dict[str, list[Vector]] = {}
        for label, features in examples:
            grouped.setdefault(label, []).append(features.direction)
        if len(grouped) < 2:
            raise ValueError("At least two direction classes are required")
        templates: dict[str, Vector] = {}
        for label, vectors in grouped.items():
            mean = tuple(sum(v[axis] for v in vectors) / len(vectors) for axis in range(3))
            unit = _unit_vector(mean)
            if unit is None:
                raise ValueError(f"Direction class has no usable mean: {label}")
            templates[label] = unit
        return cls(
            templates=templates,
            activity_threshold_dps=activity_threshold_dps,
            min_similarity=min_similarity,
            min_direction_coherence=min_direction_coherence,
        )

    def predict_features(self, features: TrialFeatures | None) -> str:
        if features is None:
            return self.idle_label
        scores = self.scores(features)
        label = max(scores, key=scores.get)
        if (
            scores[label] < self.min_similarity
            or features.direction_coherence < self.min_direction_coherence
        ):
            return self.rejected_label
        return label

    def scores(self, features: TrialFeatures) -> dict[str, float]:
        return {
            label: _dot(features.direction, template)
            for label, template in self.templates.items()
        }

    def save(self, path: Path, *, training_summary: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_type": "cosine_direction_template",
            "version": 2,
            "idle_label": self.idle_label,
            "rejected_label": self.rejected_label,
            "rejection": {
                "min_similarity": self.min_similarity,
                "min_direction_coherence": self.min_direction_coherence,
            },
            "activity_gate": {
                "gyro_norm_threshold_dps": self.activity_threshold_dps,
                "smoothing_samples": 5,
                "min_active_samples": 5,
                "min_active_duration_s": 0.08,
                "min_peak_gyro_dps": 100.0,
                "max_inactive_gap_samples": 5,
            },
            "templates": self.templates,
            "training_summary": training_summary,
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> DirectionTemplateModel:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("model_type") != "cosine_direction_template":
            raise ValueError(f"Unsupported direction model: {path}")
        templates = {
            str(label): tuple(float(value) for value in vector)
            for label, vector in payload["templates"].items()
        }
        gate = payload.get("activity_gate", {})
        rejection = payload.get("rejection", {})
        return cls(
            templates=templates,  # type: ignore[arg-type]
            activity_threshold_dps=float(
                gate.get("gyro_norm_threshold_dps", 20.0)
            ),
            min_similarity=float(rejection.get("min_similarity", 0.90)),
            min_direction_coherence=float(
                rejection.get("min_direction_coherence", 0.55)
            ),
            idle_label=str(payload.get("idle_label", "idle")),
            rejected_label=str(payload.get("rejected_label", "rejected")),
        )


def _trailing_average(values: Sequence[float], width: int) -> list[float]:
    if width < 1:
        raise ValueError("Smoothing width must be positive")
    result: list[float] = []
    running_sum = 0.0
    for index, value in enumerate(values):
        running_sum += value
        if index >= width:
            running_sum -= values[index - width]
        count = min(index + 1, width)
        result.append(running_sum / count)
    return result


def _active_spans(mask: Sequence[bool], max_gap: int) -> list[tuple[int, int]]:
    active_indices = [index for index, active in enumerate(mask) if active]
    if not active_indices:
        return []
    spans: list[tuple[int, int]] = []
    start = previous = active_indices[0]
    for index in active_indices[1:]:
        if index - previous - 1 > max_gap:
            spans.append((start, previous))
            start = index
        previous = index
    spans.append((start, previous))
    return spans


def _unit_vector(vector: Vector) -> Vector | None:
    length = _norm(vector)
    if length <= 1e-9:
        return None
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def _norm(vector: Vector) -> float:
    return math.sqrt(_dot(vector, vector))


def _dot(left: Vector, right: Vector) -> float:
    return sum(a * b for a, b in zip(left, right))
