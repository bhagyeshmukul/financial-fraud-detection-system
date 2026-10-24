"""
Describe the two supported datasets and their different input meanings. A profile is a data
contract, not a named fraud subtype such as identity theft.
"""

from dataclasses import dataclass
from src.utils import FEATURE_COLUMNS


@dataclass(frozen=True)
class Profile:
    """
    Record a dataset’s input columns, label, time field, provenance and expected raw row/class
    counts.
    """

    id: str
    title: str
    slug: str
    target: str
    time: str
    inputs: tuple[str, ...]
    expected_rows: int
    expected_frauds: int
    simulated: bool


PROFILES = {
    "credit_card": Profile(
        "credit_card",
        "Credit-card benchmark",
        "mlg-ulb/creditcardfraud",
        "Class",
        "Time",
        tuple(FEATURE_COLUMNS),
        284807,
        492,
        False,
    ),
    "banksim": Profile(
        "banksim",
        "Readable payment simulation",
        "ealaxi/banksim1",
        "fraud",
        "step",
        ("step", "customer", "merchant", "category", "amount"),
        594643,
        7200,
        True,
    ),
}


def get_profile(profile: str) -> Profile:
    """Return the requested dataset contract or reject a name whose input meanings are unknown."""
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}; choose {', '.join(PROFILES)}")
    return PROFILES[profile]
