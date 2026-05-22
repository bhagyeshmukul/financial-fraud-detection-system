"""Shared constants and utility helpers for model pipeline and reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

FEATURE_COLUMNS = ["Time", *(f"V{i}" for i in range(1, 29)), "Amount"]


def ensure_dirs() -> None:
    """Create model/report directories if they do not already exist."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def risk_from_probability(probability: float) -> str:
    """Map probability into user-facing risk category buckets."""
    if probability >= 0.75:
        return "High"
    if probability >= 0.40:
        return "Medium"
    return "Low"


def to_serializable(value: Any) -> Any:
    """Convert NumPy scalar/array values into JSON-serializable types."""
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write normalized JSON payload to disk using UTF-8 encoding."""
    normalized = json.loads(json.dumps(payload, default=to_serializable))
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
