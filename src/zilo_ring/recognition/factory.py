from __future__ import annotations

import json
from pathlib import Path

from .direction_model import DirectionTemplateModel
from .live import LiveDirectionRecognizer
from .live_temporal import LiveTemporalGestureRecognizer
from .temporal_model import TemporalWaveformModel


def load_live_recognizer(
    path: Path,
) -> LiveDirectionRecognizer | LiveTemporalGestureRecognizer:
    with path.open(encoding="utf-8") as handle:
        model_type = json.load(handle).get("model_type")
    if model_type == "temporal_waveform_knn":
        return LiveTemporalGestureRecognizer(TemporalWaveformModel.load(path))
    if model_type == "cosine_direction_template":
        return LiveDirectionRecognizer(DirectionTemplateModel.load(path))
    raise ValueError(f"Unsupported recognition model type in {path}: {model_type}")
