"""Small, non-optimising helpers for future feature ablations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

RECENT_RS_BUCKET_EDGES = (0.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
RECENT_RS_HORIZONS = (5, 10, 20, 40)


def threshold_buckets(
    frame: pd.DataFrame, feature_column: str, edges: tuple[float, ...]
) -> pd.Series:
    if feature_column not in frame:
        raise KeyError(feature_column)
    if len(edges) < 2 or tuple(sorted(edges)) != edges:
        raise ValueError("bucket edges must be increasing")
    labels = [
        f"{edges[index]:g}-{edges[index + 1]:g}" for index in range(len(edges) - 1)
    ]
    return pd.cut(
        pd.to_numeric(frame[feature_column], errors="coerce"),
        bins=list(edges),
        labels=labels,
        include_lowest=True,
        right=False,
    )


def with_without_summary(
    frame: pd.DataFrame,
    *,
    feature_column: str,
    outcome_column: str,
    included: Callable[[pd.Series], pd.Series],
) -> dict[str, dict[str, Any]]:
    """Compare fixed WITH/WITHOUT groups; this performs no threshold search."""

    if feature_column not in frame or outcome_column not in frame:
        raise KeyError("feature and outcome columns are required")
    mask = included(frame[feature_column])
    result: dict[str, dict[str, Any]] = {}
    for label, subset in (
        ("WITH_FEATURE", frame[mask]),
        ("WITHOUT_FEATURE", frame[~mask]),
    ):
        outcomes = pd.to_numeric(subset[outcome_column], errors="coerce").dropna()
        result[label] = {
            "sample_size": int(len(outcomes)),
            "mean_outcome": None if outcomes.empty else float(outcomes.mean()),
            "median_outcome": None if outcomes.empty else float(outcomes.median()),
        }
    return result
