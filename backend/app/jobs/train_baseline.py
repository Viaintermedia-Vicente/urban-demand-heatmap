from __future__ import annotations

import csv
import json
from math import sqrt
from pathlib import Path
from typing import Dict, List, Optional

import typer


NUMERIC_FIELDS = [
    "hour",
    "dow",
    "lat",
    "lon",
    "dist_km",
    "temperature_c",
    "precipitation_mm",
    "rain_mm",
    "snowfall_mm",
    "wind_speed_kmh",
    "wind_gust_kmh",
    "cloud_cover_pct",
    "humidity_pct",
    "pressure_hpa",
    "visibility_m",
]


def train_baseline(
    csv_path: Path,
    model_out: Optional[Path] = None,
    target_col: str = "label",
) -> Dict[str, float]:
    rows = _load_rows(csv_path)
    if not rows:
        raise RuntimeError("dataset is empty; run export_training_dataset first")
    if target_col not in rows[0]:
        raise RuntimeError(f"target column '{target_col}' not found in dataset")
    categories = sorted({row.get("category") or "unknown" for row in rows})
    cat_to_idx = {cat: idx for idx, cat in enumerate(categories)}

    numeric_stats = {field: 1.0 for field in NUMERIC_FIELDS}
    for field in NUMERIC_FIELDS:
        values = []
        for row in rows:
            val = _to_float(row.get(field))
            if val is not None:
                values.append(abs(val))
        if values:
            numeric_stats[field] = max(values) or 1.0

    features: List[List[float]] = []
    labels: List[float] = []
    feature_columns: List[str] = []
    base_names = NUMERIC_FIELDS + [f"cat_{cat}" for cat in categories]
    feature_columns.extend(base_names)

    for row in rows:
        vector: List[float] = []
        for field in NUMERIC_FIELDS:
            val = _to_float(row.get(field)) or 0.0
            scale = numeric_stats.get(field, 1.0)
            vector.append(val / scale if scale else val)
        cat_vec = [0.0] * len(categories)
        idx = cat_to_idx.get(row.get("category") or "unknown")
        cat_vec[idx] = 1.0
        vector.extend(cat_vec)
        features.append(vector)
        target_val = _to_float(row.get(target_col))
        if target_val is None:
            target_val = 0.0
        labels.append(target_val)

    weights, bias = _train_linear_regression(features, labels)
    preds = [_predict(weights, bias, vec) for vec in features]
    errors = [pred - y for pred, y in zip(preds, labels)]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = sqrt(sum(e ** 2 for e in errors) / len(errors))

    if model_out:
        artifact = {
            "target_col": target_col,
            "feature_columns": feature_columns,
            "scales": [numeric_stats[field] for field in NUMERIC_FIELDS] + [1.0] * len(categories),
            "categories": categories,
            "weights": weights,
            "bias": bias,
            "metrics": {"mae": mae, "rmse": rmse},
        }
        model_out.parent.mkdir(parents=True, exist_ok=True)
        model_out.write_text(json.dumps(artifact, indent=2))
    print(f"[train_baseline] target={target_col} samples={len(rows)} mae={mae:.2f} rmse={rmse:.2f}")
    return {"mae": mae, "rmse": rmse}


def _train_linear_regression(features: List[List[float]], labels: List[float], epochs: int = 2000, lr: float = 0.01):
    if not features:
        raise RuntimeError("No features to train")
    n = len(features)
    m = len(features[0])
    weights = [0.0 for _ in range(m)]
    bias = 0.0
    for _ in range(epochs):
        grad_w = [0.0 for _ in range(m)]
        grad_b = 0.0
        for vec, label in zip(features, labels):
            pred = _predict(weights, bias, vec)
            error = pred - label
            grad_b += error
            for j in range(m):
                grad_w[j] += error * vec[j]
        bias -= lr * (grad_b / n)
        for j in range(m):
            weights[j] -= lr * (grad_w[j] / n)
    return weights, bias


def _predict(weights: List[float], bias: float, vec: List[float]) -> float:
    return bias + sum(w * x for w, x in zip(weights, vec))


def _to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _load_rows(csv_path: Path):
    with csv_path.open(encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        return list(reader)


def train_cli(
    csv_path: Path = typer.Option(..., exists=True, dir_okay=False),
    model_out: Optional[Path] = typer.Option(None, dir_okay=False, help="Ruta para guardar el modelo JSON"),
    target_col: str = typer.Option("label", help="Columna objetivo a predecir"),
):
    train_baseline(csv_path, model_out, target_col=target_col)


if __name__ == "__main__":
    typer.run(train_cli)
