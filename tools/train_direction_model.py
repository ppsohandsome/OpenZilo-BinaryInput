from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from zilo_ring.recognition import (  # noqa: E402
    DirectionTemplateModel,
    TrialFeatures,
    extract_trial_features,
)


@dataclass(frozen=True, slots=True)
class Example:
    label: str
    path: Path
    features: TrialFeatures
    timestamps_ms: tuple[float, ...]
    gyro_xyz_dps: tuple[tuple[float, float, float], ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train an idle/up/down direction model")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data/captures")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "models/up_down_direction.json")
    parser.add_argument("--after", default="", help="include files at/after YYYYMMDD_HHMMSS")
    args = parser.parse_args(argv)

    examples = _load_examples(args.data_dir, labels=("up", "down"), after=args.after)
    negatives = _load_negative_examples(args.data_dir, after=args.after)
    by_label = {label: [item for item in examples if item.label == label] for label in ("up", "down")}
    if any(len(items) < 5 for items in by_label.values()):
        raise SystemExit("Need at least five usable trials for each of up and down")

    train: list[Example] = []
    test: list[Example] = []
    for items in by_label.values():
        split = max(1, int(len(items) * 0.75))
        train.extend(items[:split])
        test.extend(items[split:])
    negative_split = max(1, int(len(negatives) * 0.75))
    negative_train = negatives[:negative_split]
    negative_test = negatives[negative_split:]
    holdout_model = _fit_with_rejection(train, negative_train)
    holdout_matrix = _confusion(holdout_model, test)
    negative_holdout_false_accepts = sum(
        holdout_model.predict_features(features) in holdout_model.templates
        for _, features in negative_test
    )

    leave_one_out_correct = 0
    for held_out in examples:
        model = DirectionTemplateModel.fit(
            (item.label, item.features) for item in examples if item is not held_out
        )
        leave_one_out_correct += model.predict_features(held_out.features) == held_out.label

    static_total = 0
    static_false_positives = 0
    for item in examples:
        for timestamps, gyro in _static_segments(item):
            static_total += 1
            features = extract_trial_features(timestamps, gyro)
            static_false_positives += features is not None

    final_model = _fit_with_rejection(examples, negatives)
    summary: dict[str, object] = {
        "source_directory": str(args.data_dir.resolve()),
        "file_filter_after": args.after or None,
        "trial_counts": {label: len(items) for label, items in by_label.items()},
        "chronological_holdout": {
            "train_trials": len(train),
            "test_trials": len(test),
            "confusion_matrix": holdout_matrix,
            "accuracy": _matrix_accuracy(holdout_matrix),
            "negative_trials": len(negative_test),
            "negative_false_accepts": negative_holdout_false_accepts,
        },
        "leave_one_out": {
            "trials": len(examples),
            "correct": leave_one_out_correct,
            "accuracy": leave_one_out_correct / len(examples),
        },
        "captured_static_segments": {
            "segments": static_total,
            "false_positives": static_false_positives,
        },
        "rejection_policy": {
            "min_similarity": final_model.min_similarity,
            "min_direction_coherence": final_model.min_direction_coherence,
            "note": "Similarity allows cross-session wear variation; coherence rejects captured chaotic motion.",
        },
        "negative_trials": {
            "total": len(negatives),
            "activity_gate_idle": sum(features is None for _, features in negatives),
            "rejected_by_final_model": sum(
                final_model.predict_features(features)
                not in final_model.templates
                for _, features in negatives
            ),
        },
        "training_files": [item.path.name for item in examples],
    }
    final_model.save(args.output, training_summary=summary)

    print(f"trials: up={len(by_label['up'])}, down={len(by_label['down'])}")
    print(f"chronological holdout: {_matrix_accuracy(holdout_matrix):.1%} {holdout_matrix}")
    print(
        "negative holdout: false accepts "
        f"{negative_holdout_false_accepts}/{len(negative_test)}"
    )
    print(f"leave-one-out: {leave_one_out_correct}/{len(examples)}")
    print(f"captured static: false positives {static_false_positives}/{static_total}")
    print(f"model: {args.output}")
    return 0


def _load_examples(data_dir: Path, *, labels: tuple[str, ...], after: str) -> list[Example]:
    examples: list[Example] = []
    for label in labels:
        for path in sorted(data_dir.glob(f"*_{label}_normal.csv")):
            if after and path.name[:15] < after:
                continue
            timestamps, gyro = _read_trial(path)
            features = extract_trial_features(timestamps, gyro)
            if features is None:
                print(f"skip idle/unusable trial: {path.name}", file=sys.stderr)
                continue
            examples.append(Example(label, path, features, timestamps, gyro))
    return examples


def _load_negative_examples(
    data_dir: Path,
    *,
    after: str,
) -> list[tuple[Path, TrialFeatures | None]]:
    examples = []
    for path in sorted(data_dir.glob("*_negative_normal.csv")):
        if after and path.name[:15] < after:
            continue
        timestamps, gyro = _read_trial(path)
        examples.append((path, extract_trial_features(timestamps, gyro)))
    if len(examples) < 5:
        raise SystemExit("Need at least five negative/normal trials for rejection")
    return examples


def _fit_with_rejection(
    positives: list[Example],
    negatives: list[tuple[Path, TrialFeatures | None]],
) -> DirectionTemplateModel:
    base = DirectionTemplateModel.fit(
        (item.label, item.features) for item in positives
    )
    positive_coherence = [item.features.direction_coherence for item in positives]
    active_negative_coherence = [
        features.direction_coherence
        for _, features in negatives
        if features is not None
    ]
    if not active_negative_coherence:
        coherence_threshold = 0.55
    else:
        negative_max = max(active_negative_coherence)
        positive_min = min(positive_coherence)
        if negative_max >= positive_min:
            raise SystemExit(
                "Negative and positive direction coherence overlap; "
                "a simple rejection threshold is unsafe"
            )
        coherence_threshold = (negative_max + positive_min) / 2.0
    return DirectionTemplateModel(
        templates=base.templates,
        activity_threshold_dps=base.activity_threshold_dps,
        # Same-session positives cluster near 1.0, but a later live session
        # shifted clean up gestures to 0.95 solely from wear/orientation change.
        # Captured chaotic negatives remain separated by coherence, so keep a
        # deliberate cross-session angular tolerance here.
        min_similarity=0.90,
        min_direction_coherence=coherence_threshold,
    )


def _read_trial(path: Path) -> tuple[tuple[float, ...], tuple[tuple[float, float, float], ...]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    timestamps = tuple(float(row["device_timestamp_ms"]) for row in rows)
    gyro = tuple(
        tuple(float(row[f"gyro_bias_dps_{axis}"]) for axis in "xyz")
        for row in rows
    )
    return timestamps, gyro  # type: ignore[return-value]


def _static_segments(
    item: Example,
) -> list[tuple[tuple[float, ...], tuple[tuple[float, float, float], ...]]]:
    start_ms = item.timestamps_ms[0] + item.features.active_start_s * 1000.0 - 50.0
    end_ms = item.timestamps_ms[0] + item.features.active_end_s * 1000.0 + 50.0
    segments = []
    for keep in (
        [index for index, value in enumerate(item.timestamps_ms) if value < start_ms],
        [index for index, value in enumerate(item.timestamps_ms) if value > end_ms],
    ):
        if len(keep) < 10:
            continue
        segments.append(
            (
                tuple(item.timestamps_ms[index] for index in keep),
                tuple(item.gyro_xyz_dps[index] for index in keep),
            )
        )
    return segments


def _confusion(
    model: DirectionTemplateModel,
    examples: list[Example],
) -> dict[str, dict[str, int]]:
    labels = tuple(model.templates)
    predictions = (*labels, model.rejected_label)
    matrix = {
        actual: {predicted: 0 for predicted in predictions} for actual in labels
    }
    for item in examples:
        matrix[item.label][model.predict_features(item.features)] += 1
    return matrix


def _matrix_accuracy(matrix: dict[str, dict[str, int]]) -> float:
    total = sum(sum(row.values()) for row in matrix.values())
    correct = sum(matrix[label][label] for label in matrix)
    return correct / total


if __name__ == "__main__":
    raise SystemExit(main())
