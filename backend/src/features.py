"""
Convert raw transactions into the same model inputs during training and serving. BankSim
features use only a customer’s strictly earlier days and never inspect fraud labels.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from src.profiles import get_profile

BANK_NUMERIC = [
    "amount",
    "log_amount",
    "previous_count_7d",
    "previous_mean_7d",
    "amount_to_previous_mean",
    "new_merchant",
    "new_category",
]


def build_features(
    frame: pd.DataFrame, profile: str, history: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Labels are never inspected. Rows from the same day cannot inform each other."""
    specification = get_profile(profile)
    raw = frame[list(specification.inputs)].copy().reset_index(drop=True)
    if profile == "credit_card":
        # Compress extreme amounts and express an elapsed cycle without inventing PCA meanings.
        raw["log_amount"] = np.log1p(raw["Amount"])
        raw["elapsed_cycle_sin"] = np.sin(raw["Time"] * 2 * np.pi / 86400)
        raw["elapsed_cycle_cos"] = np.cos(raw["Time"] * 2 * np.pi / 86400)
        return raw
    earlier = (
        history[list(specification.inputs)].copy()
        if history is not None and len(history)
        else raw.iloc[:0].copy()
    )
    observations = pd.concat([earlier, raw], ignore_index=True)
    # Daily totals and prefix sums let us query a seven-day interval without scanning
    # a customer's entire purchase list for every row. Future rows remain excluded below.
    daily = (
        observations.groupby(["customer", "step"], sort=False)["amount"]
        .agg(["sum", "count"])
        .reset_index()
    )
    daily = daily.sort_values(["customer", "step"], kind="stable")
    daily["cumulative_amount"] = daily.groupby("customer")["sum"].cumsum()
    daily["cumulative_count"] = daily.groupby("customer")["count"].cumsum()
    previous_count = np.zeros(len(raw))
    previous_amount = np.zeros(len(raw))
    customer_days = {key: value for key, value in daily.groupby("customer", sort=False)}
    # Work on one customer’s timeline at a time so different people’s history never gets mixed.
    for customer, indices in raw.groupby("customer", sort=False).groups.items():
        days = customer_days[customer]
        events = raw.loc[indices, "step"].to_numpy()
        timeline = days["step"].to_numpy()
        # [event - 7, event) includes earlier days and excludes the entire current day.
        upper = np.searchsorted(timeline, events, side="left")
        lower = np.searchsorted(timeline, events - 7, side="left")
        # Reuse identical seven-day boundaries for both purchase counts and purchase amounts.
        for destination, column in (
            (previous_count, "cumulative_count"),
            (previous_amount, "cumulative_amount"),
        ):
            cumulative = np.concatenate([[0.0], days[column].to_numpy()])
            destination[np.asarray(indices)] = cumulative[upper] - cumulative[lower]
    means = np.divide(
        previous_amount,
        previous_count,
        out=np.zeros_like(previous_amount),
        where=previous_count > 0,
    )
    result = pd.DataFrame(
        {
            "amount": raw["amount"],
            "log_amount": np.log1p(raw["amount"]),
            "previous_count_7d": previous_count,
            "previous_mean_7d": means,
            "amount_to_previous_mean": np.divide(
                raw["amount"], means, out=np.ones(len(raw)), where=means > 0
            ),
            "category": raw["category"].astype(str),
        }
    )
    # With no earlier average, ratio=1 is a neutral fallback; count=0 records cold start.
    # Apply the same earlier-day novelty rule separately to merchant and merchant category.
    for key, output in (("merchant", "new_merchant"), ("category", "new_category")):
        first = (
            observations.groupby(["customer", key])["step"].min().rename("first_step")
        )
        joined = raw[["customer", key, "step"]].join(first, on=["customer", key])
        # A first observation today is still new: other same-day rows cannot count as history.
        result[output] = (joined["first_step"] >= joined["step"]).astype(float)
    return result[[*BANK_NUMERIC, "category"]]


def describe_context(features: dict, profile: str) -> list[str]:
    """
    Describe visible input/history facts for a reader without claiming a causal explanation of
    the model.
    """
    if profile == "credit_card":
        return ["PCA components have no published business interpretation."]
    count = int(features["previous_count_7d"])
    context = [f"{count} earlier payments in the previous 7 days."]
    if count:
        context.append(
            f"Amount is {features['amount_to_previous_mean']:.2f} times the previous spending average."
        )
    else:
        context.append(
            "No earlier spending average is available; this is a cold-start customer."
        )
    if features["new_merchant"]:
        context.append(
            "No earlier-day payment to this merchant in this session history."
        )
    if features["new_category"]:
        context.append(
            "No earlier-day payment in this category in this session history."
        )
    return context
