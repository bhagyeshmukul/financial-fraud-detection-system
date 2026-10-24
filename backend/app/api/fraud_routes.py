"""
Translate HTTP requests into validated service calls and serializable responses. This is the
public boundary for scoring, uploads, reports, history and analyst reviews.
"""

from __future__ import annotations
import csv
import io
import json
import os
from uuid import UUID
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.db.models import FraudPredictionLog, ReviewEvent
from app.db.session import get_db
from app.schemas.fraud_schema import (
    FraudPredictionLogOut,
    FraudPredictionRequest,
    FraudPredictionResponse,
    PredictionRequest,
    ModelChoice,
    ReviewRequest,
    SessionRequest,
    validate_transaction,
)
from app.services.fraud_service import (
    create_session,
    get_prediction_logs,
    review_prediction,
    run_prediction_and_log,
    score_and_log,
)
from src.predict import (
    ModelUnavailable,
    load_model_artifact,
    model_report,
    model_choices,
    sample_transactions,
)
from src.profiles import PROFILES, get_profile

router = APIRouter(tags=["Fraud"])


def profile_exists(profile):
    """Turn an unsupported profile into a clear HTTP 404 before attempting to load its artifacts."""
    if profile not in PROFILES:
        raise HTTPException(404, "Unknown dataset profile.")
    return PROFILES[profile]


def transaction_or_422(payload, profile):
    """
    Validate raw transaction fields and return safe field errors without echoing entire
    sensitive payloads.
    """
    try:
        return validate_transaction(payload, profile)
    except ValidationError as error:
        # Do not echo NaN/Infinity or entire uploaded transactions in error JSON.
        raise HTTPException(
            422,
            [
                {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ],
        ) from error


@router.post("/predict-fraud", response_model=FraudPredictionResponse)
def predict_fraud(payload: FraudPredictionRequest, db: Session = Depends(get_db)):
    """
    Preserve the original HTTP endpoint by delegating validated credit-card input to the legacy
    adapter.
    """
    return run_prediction_and_log(payload.model_dump(), db)


@router.get("/prediction-logs", response_model=list[FraudPredictionLogOut])
def prediction_logs(
    limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)
):
    """Preserve the original limited history endpoint for existing clients."""
    return get_prediction_logs(db, limit)


@router.get("/sample-transactions")
def samples_legacy():
    """Adapt current verified credit-card examples to the original demonstration response shape."""
    return {
        "samples": [
            {
                "id": item["id"],
                "title": "Verified credit-card example",
                "threat_level": "Unscored",
                "story": item["source"],
                "payload": item["payload"],
                "actual_label": item["actual_label"],
            }
            for item in sample_transactions("credit_card")
        ]
    }


@router.get("/api/v1/profiles")
def profiles():
    """
    List dataset contracts and available scoring choices, including why a model or Auto is
    unavailable.
    """
    result = []
    # Describe every supported dataset and its actual artifact availability to the browser.
    for profile, specification in PROFILES.items():
        entry = {
            "id": profile,
            "title": specification.title,
            "simulated": specification.simulated,
            "inputs": specification.inputs,
            "available": False,
            "model_version": None,
        }
        try:
            artifact = load_model_artifact(profile)
            entry.update(available=True, model_version=artifact["model_version"])
            entry["model_choices"] = model_choices(profile)
        except ModelUnavailable as error:
            entry["reason"] = str(error)
        result.append(entry)
    return result


@router.get("/api/v1/profiles/{profile}/evaluation")
def evaluation(profile: str):
    """Return the frozen evaluation that matches the current profile’s served model version."""
    profile_exists(profile)
    return model_report(profile)


@router.get("/api/v1/profiles/{profile}/samples")
def samples(profile: str):
    """
    Return selected original validation transactions and explicitly identify their
    demonstration-only sampling.
    """
    profile_exists(profile)
    return {
        "samples": sample_transactions(profile),
        "note": "Selected validation examples; replay metrics do not estimate population performance.",
    }


@router.post("/api/v1/sessions", status_code=201)
def sessions(payload: SessionRequest, db: Session = Depends(get_db)):
    """Create a new isolated analysis session after validating its profile and seed flag."""
    return create_session(db, payload.profile, payload.seeded)


@router.post(
    "/api/v1/profiles/{profile}/predictions", response_model=FraudPredictionResponse
)
def prediction(profile: str, payload: PredictionRequest, db: Session = Depends(get_db)):
    """Validate a transaction and dispatch its requested policy to atomic scoring and logging."""
    profile_exists(profile)
    transaction = transaction_or_422(payload.transaction, profile)
    return score_and_log(
        db,
        profile,
        payload.session_id,
        payload.request_id,
        [transaction],
        model_choice=payload.model_choice,
    )


@router.post("/api/v1/profiles/{profile}/batch-predictions")
async def batch_predictions(
    profile: str,
    file: UploadFile = File(...),
    session_id: UUID = Form(...),
    request_id: UUID = Form(...),
    model_choice: ModelChoice = Form("champion"),
    db: Session = Depends(get_db),
):
    """
    Validate a bounded CSV completely, separate optional labels, and score the upload atomically
    off the event loop.
    """
    specification = profile_exists(profile)
    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV uploads are limited to 5 MB.")
    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError("CSV headers must be unique.")
        required, allowed = (
            set(specification.inputs),
            set(specification.inputs) | {specification.target},
        )
        if profile == "banksim":
            allowed |= {"age", "gender", "zipcodeOri", "zipMerchant"}
        if not required.issubset(fields) or set(fields) - allowed:
            raise ValueError(
                f"CSV must contain the profile inputs, optionally {specification.target}; only known source columns are accepted."
            )
        rows = []
        # Validate every row before scoring, so one bad row cannot produce a partial upload.
        for row in reader:
            if len(rows) >= 5000:
                raise HTTPException(413, "CSV uploads are limited to 5,000 rows.")
            if None in row or any(
                value is None or not value.strip() for value in row.values()
            ):
                raise ValueError("CSV has blank fields or inconsistent row lengths.")
            rows.append(row)
        if not rows:
            raise ValueError("CSV contains no transactions.")
        labels = None
        if specification.target in fields:
            if any(row[specification.target] not in ("0", "1") for row in rows):
                raise ValueError("Evaluation labels must be 0 or 1.")
            labels = [int(row[specification.target]) for row in rows]
        transactions = [
            transaction_or_422({key: row[key] for key in specification.inputs}, profile)
            for row in rows
        ]
    except (UnicodeError, csv.Error, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    # Scoring uses the synchronous worker pool; avoid blocking FastAPI's event loop.
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(
        score_and_log,
        db,
        profile,
        str(session_id),
        str(request_id),
        transactions,
        labels,
        True,
        model_choice=model_choice,
    )


@router.get("/api/v1/predictions", response_model=list[FraudPredictionLogOut])
def logs(
    profile: str | None = None,
    session_id: UUID | None = None,
    before_id: int | None = Query(None, ge=1),
    risk: str | None = Query(None, pattern="^(Low|Medium|High)$"),
    state: str | None = Query(None, pattern="^(open|under_review|closed)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Validate history filters and delegate cursor-based retrieval to the database service."""
    if profile:
        profile_exists(profile)
    return get_prediction_logs(
        db,
        limit,
        profile=profile,
        session_id=session_id,
        before_id=before_id,
        risk=risk,
        state=state,
    )


@router.get("/api/v1/predictions/export")
def export_logs(
    profile: str | None = None,
    session_id: UUID | None = None,
    risk: str | None = Query(None, pattern="^(Low|Medium|High)$"),
    state: str | None = Query(None, pattern="^(open|under_review|closed)$"),
    db: Session = Depends(get_db),
):
    """
    Export filtered prediction records as CSV, including recorded model identity and
    spreadsheet-safe notes.
    """
    if profile:
        profile_exists(profile)
    rows = get_prediction_logs(
        db, 5000, profile=profile, session_id=session_id, risk=risk, state=state
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "profile",
            "amount",
            "probability",
            "label",
            "risk",
            "model_version",
            "requested_model",
            "used_model",
            "router_version",
            "routing_status",
            "decision_threshold",
            "review_state",
            "notes",
        ]
    )
    # Export records in order; escape analyst notes before handing them to the CSV writer.
    for row in rows:
        # Spreadsheet exports must not interpret analyst notes as formulas.
        note = (
            "'" + row.notes
            if row.notes[:1] in ("=", "+", "-", "@", "\t", "\r")
            else row.notes
        )
        writer.writerow(
            [
                row.id,
                row.profile,
                row.transaction_amount,
                row.fraud_probability,
                row.prediction_label,
                row.risk_level,
                row.model_version,
                row.requested_model,
                row.used_model,
                row.router_version,
                row.routing_status,
                (row.response_payload or {}).get("decision_threshold"),
                row.review_state,
                note,
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="prediction-logs.csv"'},
    )


@router.patch(
    "/api/v1/predictions/{identifier}/review", response_model=FraudPredictionLogOut
)
def review(identifier: int, payload: ReviewRequest, db: Session = Depends(get_db)):
    """Apply a validated analyst state/note update and return the updated record."""
    return review_prediction(db, identifier, payload.state, payload.notes)


@router.get("/api/v1/predictions/{identifier}/reviews")
def review_history(identifier: int, db: Session = Depends(get_db)):
    """Read an individual prediction’s append-only review events in their original order."""
    return [
        {"state": row.state, "notes": row.notes, "created_at": row.created_at}
        for row in db.scalars(
            select(ReviewEvent)
            .where(ReviewEvent.prediction_id == identifier)
            .order_by(ReviewEvent.id)
        ).all()
    ]


@router.get("/api/v1/operations")
def operations(db: Session = Depends(get_db)):
    """
    Combine per-worker HTTP counters with database-wide counts and recent measured latency
    percentiles.
    """
    from app.main import telemetry_snapshot

    rows = (
        db.execute(
            select(FraudPredictionLog.processing_ms)
            .where(FraudPredictionLog.processing_ms.is_not(None))
            .order_by(FraudPredictionLog.id.desc())
            .limit(1000)
        )
        .scalars()
        .all()
    )
    return {
        **telemetry_snapshot(),
        "predictions": db.scalar(select(func.count()).select_from(FraudPredictionLog)),
        "prediction_latency_scope": "last 1,000 persisted transactions, across workers",
        "prediction_p50_ms": float(np.percentile(rows, 50)) if rows else None,
        "prediction_p95_ms": float(np.percentile(rows, 95)) if rows else None,
    }
