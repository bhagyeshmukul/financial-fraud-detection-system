"""
Import verified publisher CSV data and record where it came from. Training reads these files;
serving never downloads data or substitutes made-up transactions.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import ssl
import tempfile
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
import certifi
import numpy as np
import pandas as pd
from src.profiles import PROFILES, get_profile
from src.utils import DATA_DIR, write_json


def checksum(path: Path) -> str:
    """
    Read a file in chunks and return its SHA-256 fingerprint so imported data can be identified
    later.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        # Hash bounded chunks instead of holding another complete copy of the dataset in memory.
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_frame(df: pd.DataFrame, profile: str) -> pd.DataFrame:
    """
    Normalize publisher column/string formats and reject data that violates the selected
    profile’s contract.
    """
    specification = get_profile(profile)
    df = df.copy()
    # Strip publisher-style surrounding quotes from text columns before schema checks.
    for column in df.select_dtypes(include="object"):
        df[column] = df[column].str.strip("'\" ")
    required = [*specification.inputs, specification.target]
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"Missing dataset columns: {sorted(missing)}")
    df = df[required]
    numeric = specification.inputs if profile == "credit_card" else ("step", "amount")
    # Convert only declared numeric fields and the binary label; invalid text raises an error.
    for column in (*numeric, specification.target):
        df[column] = pd.to_numeric(df[column], errors="raise")
    if not df[specification.target].isin([0, 1]).all():
        raise ValueError("Labels must be present and binary (0 or 1).")
    if np.isinf(df[list(numeric)].to_numpy(dtype=float)).any():
        raise ValueError("Dataset contains infinite values.")
    amount = "Amount" if profile == "credit_card" else "amount"
    if (df[amount].dropna() < 0).any() or (df[specification.time] < 0).any():
        raise ValueError("Amounts and elapsed time cannot be negative.")
    if df[specification.time].isna().any():
        raise ValueError("Time is required for chronological evaluation.")
    if profile == "banksim" and (df["step"] % 1 != 0).any():
        raise ValueError("BankSim steps must be whole days.")
    if (
        profile == "banksim"
        and df[["customer", "merchant", "category"]].isna().any().any()
    ):
        raise ValueError("BankSim history identifiers and category are required.")
    return df.sort_values(specification.time, kind="stable").reset_index(drop=True)


def load_transaction_data(
    path=None, profile="credit_card", verify=True
) -> pd.DataFrame:
    """
    Read an explicitly imported dataset and its required schema; fail when data is absent
    instead of inventing samples.
    """
    location = Path(path) if path else DATA_DIR / f"{profile}.csv"
    if not location.is_file():
        raise FileNotFoundError(
            f"Verified {profile} data missing. Run: python -m src.data_loader --profile {profile}"
        )
    if verify:
        manifest_path = location.with_suffix(".manifest.json")
        if not manifest_path.exists():
            raise ValueError(
                f"Dataset manifest missing: {manifest_path}; import the original dataset first."
            )
        manifest = json.loads(manifest_path.read_text())
        if manifest["sha256"] != checksum(location) or manifest["profile"] != profile:
            raise ValueError("Dataset checksum or profile does not match its manifest.")
    return normalize_frame(pd.read_csv(location), profile)


def import_dataset(profile: str, source: Path | None = None):
    """Fetch the publisher's archive or verify a user-supplied original CSV."""
    specification = get_profile(profile)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    context = ssl.create_default_context(cafile=certifi.where())
    metadata_url = f"https://www.kaggle.com/api/v1/datasets/view/{specification.slug}"
    with urllib.request.urlopen(metadata_url, context=context, timeout=60) as response:
        metadata = json.load(response)
    with tempfile.TemporaryDirectory(prefix="fraud-data-") as directory:
        staging = Path(directory) / "dataset.csv"
        if source:
            shutil.copyfile(source, staging)
        else:
            archive = Path(directory) / "dataset.zip"
            request = urllib.request.Request(
                f"https://www.kaggle.com/api/v1/datasets/download/{specification.slug}",
                headers={"User-Agent": "fraud-research/2.0"},
            )
            print(f"Downloading publisher dataset: {specification.slug}", flush=True)
            with (
                urllib.request.urlopen(
                    request, context=context, timeout=120
                ) as response,
                archive.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            with zipfile.ZipFile(archive) as bundle:
                members = [
                    entry
                    for entry in bundle.infolist()
                    if entry.filename.lower().endswith(".csv")
                ]
                preferred = (
                    "creditcard.csv"
                    if profile == "credit_card"
                    else "bs140513_032310.csv"
                )
                member = next(
                    (
                        item
                        for item in members
                        if Path(item.filename).name.lower() == preferred
                    ),
                    None,
                )
                if member is None:
                    raise ValueError(
                        f"Expected {preferred} in publisher archive; got {[m.filename for m in members]}"
                    )
                with bundle.open(member) as input_stream, staging.open("wb") as output:
                    shutil.copyfileobj(input_stream, output)
        frame = normalize_frame(pd.read_csv(staging), profile)
        frauds = int(frame[specification.target].sum())
        if (
            len(frame) != specification.expected_rows
            or frauds != specification.expected_frauds
        ):
            raise ValueError(
                f"Publisher count mismatch: {len(frame)} rows/{frauds} frauds; expected {specification.expected_rows}/{specification.expected_frauds}. No benchmark imported."
            )
        destination = DATA_DIR / f"{profile}.csv"
        manifest = {
            "profile": profile,
            "source": f"https://www.kaggle.com/datasets/{specification.slug}",
            "source_updated": metadata.get("lastUpdated"),
            "license": metadata.get("licenseName"),
            "sha256": checksum(staging),
            "rows": len(frame),
            "frauds": frauds,
            "simulated": specification.simulated,
            "imported_at": datetime.now(UTC).isoformat(),
        }
        shutil.copyfile(staging, destination.with_suffix(".csv.tmp"))
        destination.with_suffix(".csv.tmp").replace(destination)
        write_json(destination.with_suffix(".manifest.json"), manifest)
        print(json.dumps(manifest, indent=2), flush=True)
        return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument(
        "--source", type=Path, help="Original publisher CSV downloaded manually"
    )
    arguments = parser.parse_args()
    import_dataset(arguments.profile, arguments.source)
