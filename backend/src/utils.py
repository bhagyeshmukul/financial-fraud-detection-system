"""
Share paths, feature identity, JSON writing and risk-label rules. Environment variables let the
same code use laptop directories or mounted server directories.
"""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("FRAUD_DATA_DIR", PROJECT_ROOT / "data" / "raw"))
MODELS_DIR = Path(os.getenv("FRAUD_MODELS_DIR", PROJECT_ROOT / "models" / "v2"))
REPORTS_DIR = Path(os.getenv("FRAUD_REPORTS_DIR", PROJECT_ROOT / "reports" / "v2"))
FEATURE_COLUMNS = ["Time", *(f"V{i}" for i in range(1, 29)), "Amount"]
FEATURE_VERSION = "2.0"


def ensure_dirs():
    """
    Create configured data, model and report directories when an explicit training/import
    command needs them.
    """
    # Create each configured storage directory, including its missing parents, when explicitly needed.
    for path in (DATA_DIR, MODELS_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def risk_from_probability(probability: float, threshold: float = 0.5) -> str:
    """Map a score to High at the alert threshold, Medium at half that threshold, otherwise Low."""
    if probability >= threshold:
        return "High"
    return "Medium" if probability >= threshold / 2 else "Low"


def to_serializable(value):
    """
    Convert NumPy values and paths to ordinary JSON-compatible values without hiding unsupported
    types.
    """
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def write_json(path: Path, payload):
    """
    Write complete JSON to a temporary file and atomically replace the destination so readers
    never see half a document.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, default=to_serializable, allow_nan=False, indent=2)
    # Research artifacts contain no secrets and must be readable by container UID 10001.
    temporary.chmod(0o644)
    temporary.replace(path)
