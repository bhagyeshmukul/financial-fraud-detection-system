"""
Create the FastAPI application, security boundary, health checks and request telemetry. HTTP
routes delegate business work to services instead of training models inside a web request.
"""

from __future__ import annotations
import json
import logging
import os
import threading
import time
from collections import Counter
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.fraud_routes import router
from app.db.database import engine
from app.security import require_api_access
from src.predict import ModelUnavailable, load_model_artifact, model_report
from src.profiles import PROFILES

logger = logging.getLogger("fraud.api")
_lock = threading.Lock()
_counts = Counter()


def telemetry_snapshot():
    """Return a thread-safe copy of this worker’s request/error counters and elapsed running time."""
    with _lock:
        return {
            "process_id": os.getpid(),
            "http_metrics_scope": "this worker since startup",
            "http": dict(_counts),
        }


@asynccontextmanager
async def lifespan(app):
    """
    Check startup configuration and manage application lifetime without creating databases or
    training models.
    """
    # Check each independent dataset; one healthy model cannot stand in for the other profile.
    for profile in PROFILES:
        try:
            load_model_artifact(profile)
        except ModelUnavailable as error:
            logger.warning("%s", error)
    yield


app = FastAPI(title="Financial Fraud Detection API", version="2.0.0", lifespan=lifespan)
origins = [
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(router, dependencies=[Depends(require_api_access)])


@app.middleware("http")
async def request_telemetry(request: Request, call_next):
    """
    Bound incoming request size, time requests, update counters and emit structured completion
    logs.
    """
    started = time.perf_counter()
    identifier = str(uuid4())
    limit = 6 * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and (not declared.isdigit() or int(declared) > limit):
        return JSONResponse({"detail": "Request body exceeds 6 MB."}, status_code=413)
    # Bound chunked uploads as well as Content-Length requests.
    if request.method in ("POST", "PATCH", "PUT"):
        body = bytearray()
        # Count streamed bytes as they arrive so chunked uploads cannot bypass the request-size limit.
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return JSONResponse(
                    {"detail": "Request body exceeds 6 MB."}, status_code=413
                )
        request._body = bytes(body)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Request %s failed", identifier)
        response = JSONResponse(
            {
                "detail": "Request failed. Check service readiness and server logs.",
                "request_id": identifier,
            },
            status_code=500,
        )
    duration = (time.perf_counter() - started) * 1000
    with _lock:
        _counts["requests"] += 1
        _counts[f"status_{response.status_code // 100}xx"] += 1
    logger.info(
        json.dumps(
            {
                "request_id": identifier,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration, 3),
            }
        )
    )
    response.headers["X-Request-ID"] = identifier
    response.headers["Server-Timing"] = f"api;dur={duration:.2f}"
    return response


@app.exception_handler(ModelUnavailable)
async def model_unavailable(request, error):
    """Translate missing/incompatible model dependencies into a readable HTTP 503 response."""
    return JSONResponse({"detail": str(error)}, status_code=503)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Pydantic's raw input can itself be NaN, which is invalid JSON in a response.
    """Return JSON-safe validation details even when the rejected input contained NaN or Infinity."""
    return JSONResponse(
        {
            "detail": [
                {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ]
        },
        status_code=422,
    )


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, error):
    """Return a readable service-unavailable response without exposing database connection details."""
    logger.error("Database unavailable: %s", type(error).__name__)
    return JSONResponse(
        {
            "detail": "Database operation failed; no successful audit response was issued."
        },
        status_code=503,
    )


@app.get("/")
@app.get("/health/live")
def health():
    """
    Report that the API process is alive; readiness separately verifies dependencies needed for
    useful work.
    """
    return {
        "status": "ok",
        "service": "financial-fraud-detection-system",
        "version": "2.0.0",
    }


@app.get("/health/ready")
def readiness():
    """
    Check production token configuration, database/schema access and matching model/report
    availability.
    """
    checks = {}
    if os.getenv("APP_ENV") == "production":
        checks["access_configuration"] = {
            "ready": len(os.getenv("API_ACCESS_TOKEN", "")) >= 32
        }
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM fraud_prediction_logs LIMIT 1"))
        checks["database"] = {"ready": True}
    except SQLAlchemyError:
        checks["database"] = {
            "ready": False,
            "reason": "Database unavailable or migrations missing.",
        }
    # Check each independent dataset; one healthy model cannot stand in for the other profile.
    for profile in PROFILES:
        try:
            report = model_report(profile)
            checks[profile] = {"ready": True, "model_version": report["model_version"]}
        except ModelUnavailable as error:
            checks[profile] = {"ready": False, "reason": str(error)}
    ready = all(check["ready"] for check in checks.values())
    return JSONResponse(
        {"ready": ready, "checks": checks}, status_code=200 if ready else 503
    )
