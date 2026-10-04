from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from zilo_ring.recognition import (  # noqa: E402
    TemporalWaveform,
    TemporalWaveformModel,
    extract_temporal_waveform,
)


LABELS = (
    "single_press_rebound",
    "up_flick_rebound",
    "double_press_rebound",
    "gesture_negative_v2",
)


@dataclass(frozen=True, slots=True)
class Trial:
    label: str
    path: Path
    waveform: TemporalWaveform


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train the complete-gesture temporal waveform KNN model"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data" / "captures"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "models" / "gesture_temporal_knn.json",
    )
    args = parser.parse_args(argv)

    trials, excluded = _load_trials(args.data_dir)
    grouped = {label: [trial for trial in trials if trial.label == label] for label in LABELS}
    if any(len(items) < 5 for items in grouped.values()):
        raise SystemExit("Need at least five usable structured trials per label")

    train = []
    test = []
    for items in grouped.values():
        for index, trial in enumerate(items):
            (test if index % 4 == 0 else train).append(trial)
    holdout_model = _fit(train)
    matrix, rejected = _confusion(holdout_model, test)

    final_model = _fit(trials)
    summary: dict[str, object] = {
        "source_directory": str(args.data_dir.resolve()),
        "structured_metadata_only": True,
        "trial_counts": {label: len(items) for label, items in grouped.items()},
        "excluded": excluded,
        "validation": {
            "method": "deterministic interleaved 3:1 holdout within each label",
            "train_trials": len(train),
            "test_trials": len(test),
            "confusion_matrix": matrix,
            "rejected_by_distance": rejected,
            "accuracy": _matrix_accuracy(matrix),
        },
        "training_files": [trial.path.name for trial in trials],
    }
    final_model.save(args.output, training_summary=summary)

    print("usable:", " ".join(f"{label}={len(items)}" for label, items in grouped.items()))
    print(f"excluded: {len(excluded)}")
    print(f"holdout: {_matrix_accuracy(matrix):.1%} ({len(test)} trials)")
    print(json.dumps(matrix, ensure_ascii=False))
    print(f"distance rejected: {rejected}")
    print(f"model: {args.output}")
    return 0


def _load_trials(data_dir: Path) -> tuple[list[Trial], list[dict[str, str]]]:
    trials = []
    excluded = []
    for path in sorted(data_dir.glob("*.csv")):
        metadata_path = path.with_suffix(".meta.json")
        if not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        label = str(metadata.get("label", ""))
        if label not in LABELS or "hand_angle_deg" not in metadata:
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) < 2:
            excluded.append({"file": path.name, "reason": "too_few_samples"})
            continue
        device_duration_s = (
            float(rows[-1]["device_timestamp_ms"])
            - float(rows[0]["device_timestamp_ms"])
        ) / 1000.0
        if device_duration_s < 0.8:
            excluded.append({"file": path.name, "reason": "truncated_duration"})
            continue
        timestamps = tuple(float(row["device_timestamp_ms"]) for row in rows)
        gyro = tuple(
            tuple(float(row[f"gyro_bias_dps_{axis}"]) for axis in "xyz")
            for row in rows
        )
        accel = tuple(
            tuple(float(row[f"accel_bias_g_{axis}"]) for axis in "xyz")
            for row in rows
        )
        waveform = extract_temporal_waveform(timestamps, gyro, accel)
        if waveform is None:
            excluded.append({"file": path.name, "reason": "below_peak_threshold"})
            continue
        trials.append(Trial(label=label, path=path, waveform=waveform))
    return trials, excluded


def _fit(trials: list[Trial]) -> TemporalWaveformModel:
    return TemporalWaveformModel.fit(
        ((trial.label, trial.waveform) for trial in trials),
        labels=LABELS,
    )


def _confusion(
    model: TemporalWaveformModel,
    trials: list[Trial],
) -> tuple[dict[str, dict[str, int]], int]:
    matrix = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    rejected = 0
    for trial in trials:
        prediction = model.predict(trial.waveform)
        matrix[trial.label][prediction.candidate_label] += 1
        rejected += prediction.rejection_reason == "out_of_distribution"
    return matrix, rejected


def _matrix_accuracy(matrix: dict[str, dict[str, int]]) -> float:
    total = sum(sum(row.values()) for row in matrix.values())
    correct = sum(matrix[label][label] for label in matrix)
    return correct / total


if __name__ == "__main__":
    raise SystemExit(main())
