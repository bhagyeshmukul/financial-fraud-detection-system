"""
Coordinate scoring, isolated session history, retries and durable audit records. A successful
prediction and its saved response commit together in one database transaction.
"""

from __future__ import annotations
import hashlib
import json
import time
from uuid import uuid4
import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.models import AnalysisSession, BatchRequest, FraudPredictionLog, ReviewEvent
from src.predict import predict_rows
from src.profiles import get_profile
from src.utils import to_serializable


def normalized(value):
    """
    Make a stable plain-JSON copy of a prediction so stored snapshots do not contain NumPy-only
    objects.
    """
    return json.loads(json.dumps(value, default=to_serializable, allow_nan=False))


def payload_hash(value):
    """
    Fingerprint canonical JSON so an exact retry can be distinguished from changed input using
    the same request ID.
    """
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def create_session(db, profile, seeded=False):
    """
    Create a profile-specific analysis history, optionally seeded with permitted earlier BankSim
    observations.
    """
    get_profile(profile)
    session = AnalysisSession(id=str(uuid4()), profile=profile, seeded=seeded)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "profile": profile,
        "seeded": seeded,
        "created_at": session.created_at,
    }


def lock_session(db, identifier, profile):
    """Check session existence/profile and lock stateful BankSim history against concurrent updates."""
    query = select(AnalysisSession).where(AnalysisSession.id == str(identifier))
    # Only behavioural histories require a session-wide serialization boundary.
    if profile == "banksim":
        query = query.with_for_update()
    session = db.scalar(query)
    if session is None:
        raise HTTPException(404, "Session not found. Create an analysis session first.")
    if session.profile != profile:
        raise HTTPException(409, "Session belongs to a different dataset profile.")
    return session


def session_history(db, session, transactions):
    """
    Fetch only this session’s relevant customers and earlier observations for shared behavioral
    features.
    """
    if session.profile != "banksim":
        return None
    customers = {item["customer"] for item in transactions}
    maximum = max(item["step"] for item in transactions)
    rows = db.scalars(
        select(FraudPredictionLog).where(
            FraudPredictionLog.session_id == session.id,
            FraudPredictionLog.customer_id.in_(customers),
            FraudPredictionLog.event_step < maximum,
        )
    ).all()
    return pd.DataFrame([row.request_payload for row in rows]) if rows else None


def score_and_log(
    db,
    profile,
    session_id,
    request_id,
    transactions,
    actual_labels=None,
    batch=False,
    model_choice="champion",
):
    """
    Lock retry/history boundaries, score once, persist immutable responses, and commit the
    operation atomically.
    """
    started = time.perf_counter()
    session = lock_session(db, session_id, profile)
    identifier = str(request_id)
    if db.get_bind().dialect.name == "postgresql":
        # Exact retries serialize per request, while independent PCA requests run concurrently.
        lock_key = int.from_bytes(
            hashlib.sha256(identifier.encode()).digest()[:8], signed=True
        )
        db.execute(select(func.pg_advisory_xact_lock(lock_key)))
    fingerprint = payload_hash(
        {
            "profile": profile,
            "session": str(session_id),
            "transactions": transactions,
            "labels": actual_labels,
            "kind": "batch" if batch else "single",
            # Retain the old default representation so pre-router retries still match.
            **({"model_choice": model_choice} if model_choice != "champion" else {}),
        }
    )
    previous = db.get(BatchRequest, identifier) or db.scalar(
        select(FraudPredictionLog).where(FraudPredictionLog.request_id == identifier)
    )
    if previous:
        # Reproduce the earlier decision even if a newer model has since been deployed.
        if previous.payload_hash != fingerprint:
            raise HTTPException(
                409, "This request ID was already used with different data."
            )
        return previous.response_payload

    if profile == "banksim" and session.seeded and session.seed_before is None:
        # Fix the seed boundary once; later requests must not pull in newer reference history.
        session.seed_before = min(item["step"] for item in transactions)
    frame = pd.DataFrame(transactions)
    predictions = predict_rows(
        frame,
        profile,
        session_history(db, session, transactions),
        seed_before=session.seed_before if session.seeded else None,
        model_choice=model_choice,
    )
    elapsed = (time.perf_counter() - started) * 1000
    records = []
    # Pair each input with its prediction and allocate one audit record, retaining original batch order.
    for index, (transaction, prediction) in enumerate(zip(transactions, predictions)):
        record = FraudPredictionLog(
            transaction_amount=transaction[
                "Amount" if profile == "credit_card" else "amount"
            ],
            fraud_probability=prediction["fraud_probability"],
            prediction_label=prediction["prediction_label"],
            risk_level=prediction["risk_level"],
            model_version=prediction["model_version"],
            request_payload=transaction,
            profile=profile,
            session_id=session.id,
            request_id=f"{identifier}:{index}" if batch else identifier,
            payload_hash=fingerprint,
            event_step=transaction["Time" if profile == "credit_card" else "step"],
            customer_id=transaction.get("customer"),
            processing_ms=elapsed / len(transactions),
            review_state="open",
            notes="",
        )
        db.add(record)
        records.append(record)
    db.flush()
    # flush allocates IDs without committing; a later failure can still undo the entire batch.
    results = []
    # Attach the completed immutable response after database-generated record IDs are available.
    for record, prediction in zip(records, predictions):
        # Persist an immutable response snapshot for retries and audit.
        result = normalized(
            {
                **prediction,
                "id": record.id,
                "processing_ms": elapsed / len(transactions),
                "session_id": session.id,
            }
        )
        record.response_payload = result
        results.append(result)
    response = results[0]
    if batch:
        response = {
            "profile": profile,
            "rows": len(results),
            "processing_ms": elapsed,
            "results": results,
            "evaluation": None,
            "evaluation_note": "Uploaded-data evaluation, not the frozen benchmark test report.",
            "requested_model": model_choice,
            "used_models": {
                name: sum(item.get("used_model") == name for item in results)
                for name in sorted(
                    {item.get("used_model", "unknown") for item in results}
                )
            },
        }
        if actual_labels is not None:
            from src.evaluate import evaluate_probabilities

            response["evaluation"] = evaluate_probabilities(
                actual_labels,
                [item["fraud_probability"] for item in results],
                results[0]["decision_threshold"],
            )
        response = normalized(response)
        db.add(
            BatchRequest(
                id=identifier, payload_hash=fingerprint, response_payload=response
            )
        )
    db.commit()
    return response


def run_prediction_and_log(payload: dict, db: Session) -> dict:
    """
    Adapt the legacy credit-card endpoint to a fresh analysis session and the shared atomic
    scoring service.
    """
    session = create_session(db, "credit_card")
    return score_and_log(db, "credit_card", session["id"], str(uuid4()), [payload])


def get_prediction_logs(
    db,
    limit=50,
    *,
    profile=None,
    session_id=None,
    before_id=None,
    risk=None,
    state=None,
):
    """
    Apply optional profile/session/risk/review filters and return newest records with cursor
    pagination.
    """
    query = select(FraudPredictionLog)
    # Apply only supplied filters; an omitted filter must not accidentally exclude records.
    for field, value in (
        (FraudPredictionLog.profile, profile),
        (FraudPredictionLog.session_id, session_id),
        (FraudPredictionLog.risk_level, risk),
        (FraudPredictionLog.review_state, state),
    ):
        if value is not None:
            query = query.where(field == str(value))
    if before_id is not None:
        query = query.where(FraudPredictionLog.id < before_id)
    return db.scalars(query.order_by(FraudPredictionLog.id.desc()).limit(limit)).all()


def review_prediction(db, identifier, state, notes):
    """
    Update analyst review state under a row lock and append a separate review event without
    changing the original score.
    """
    row = db.scalar(
        select(FraudPredictionLog)
        .where(FraudPredictionLog.id == identifier)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Prediction not found.")
    row.review_state, row.notes = state, notes
    db.add(ReviewEvent(prediction_id=identifier, state=state, notes=notes))
    db.commit()
    db.refresh(row)
    return row
