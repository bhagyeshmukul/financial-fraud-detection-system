"""
Learn which candidate to consult for a transaction’s patterns. The router estimates candidate
errors on separate examples; those errors are neither fraud probabilities nor fraud diagnoses.
"""

from __future__ import annotations
import math
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeRegressor


class ModelRouter:
    """A small decision tree predicting one expected error per candidate."""

    def fit(self, features, labels, candidate_probabilities):
        """Learn competence only from rows unused by expert fitting/calibration."""
        self.candidate_names = tuple(candidate_probabilities)
        self.feature_columns = tuple(features.columns)
        labels = np.asarray(labels, dtype=int)
        if set(np.unique(labels)) != {0, 1}:
            raise ValueError(
                "Router training requires both fraud and legitimate labels."
            )
        numeric = list(features.select_dtypes(include="number").columns)
        categorical = [column for column in features if column not in numeric]
        transforms = [("numeric", SimpleImputer(strategy="median"), numeric)]
        if categorical:
            transforms.append(
                (
                    "category",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    categorical,
                )
            )
        self.pipeline = Pipeline(
            [
                ("prepare", ColumnTransformer(transforms, sparse_threshold=0)),
                (
                    "tree",
                    DecisionTreeRegressor(
                        max_depth=3,
                        min_samples_leaf=max(200, math.ceil(len(features) * 0.05)),
                        random_state=42,
                    ),
                ),
            ]
        )
        # Each target column measures how far one candidate was from the truth.
        probabilities = np.column_stack(
            [candidate_probabilities[name] for name in self.candidate_names]
        )
        errors = (probabilities - labels[:, None]) ** 2
        counts = np.bincount(labels, minlength=2)
        weights = len(labels) / (2 * counts[labels])
        self.pipeline.fit(features, errors, tree__sample_weight=weights)
        return self

    def choose(self, features):
        """Select one candidate per row without asking any expert for a score."""
        features = features.loc[:, self.feature_columns]
        losses = self.pipeline.predict(features)
        losses = np.asarray(losses).reshape(len(features), len(self.candidate_names))
        # Candidate insertion order supplies a reproducible tie-break rule.
        selected = np.asarray(self.candidate_names, dtype=object)[
            np.argmin(losses, axis=1)
        ]
        return selected, losses


def routed_probabilities(router, candidates, features):
    """Score grouped rows with their selected experts and preserve input order."""
    selected, losses = router.choose(features)
    probabilities = np.empty(len(features), dtype=float)
    # Group by selected candidate so a CSV is scored efficiently while preserving its original positions.
    for name in router.candidate_names:
        positions = np.flatnonzero(selected == name)
        if len(positions):
            probabilities[positions] = candidates[name].predict_proba(
                features.iloc[positions]
            )[:, 1]
    return probabilities, selected, losses


def choose_auto_policy(validation):
    """Promote routing only for a strict recall gain over eligible individuals."""
    individuals = [
        name
        for name, result in validation.items()
        if name != "router" and result["eligible"]
    ]
    if not individuals:
        return {
            "available": False,
            "policy": None,
            "reason": "No individual candidate meets validation precision >=80% and accuracy >=94%.",
        }
    best = max(
        individuals,
        key=lambda name: (
            validation[name]["recall"],
            validation[name]["precision"],
            validation[name]["average_precision"],
            name,
        ),
    )
    routed = validation.get("router", {})
    promoted = (
        routed.get("eligible", False) and routed["recall"] > validation[best]["recall"]
    )
    return {
        "available": True,
        "policy": "router" if promoted else best,
        "baseline": best,
        "router_promoted": bool(promoted),
        "reason": "Router increased validation recall while meeting precision/accuracy requirements."
        if promoted
        else "Router did not exceed the strongest eligible individual's validation recall; Auto uses that individual.",
    }
