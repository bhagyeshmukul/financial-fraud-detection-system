"""
Define database tables for sessions, predictions, batch retries and reviews. These ORM models
describe stored records; they are different from machine-learning models.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AnalysisSession(Base):
    """Store which dataset and optional seed cutoff belong to one isolated analysis history."""

    __tablename__ = "analysis_sessions"
    id = Column(String(36), primary_key=True)
    profile = Column(String(32), nullable=False)
    seeded = Column(Boolean, nullable=False, default=False)
    seed_before = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FraudPredictionLog(Base):
    """
    Store one scored transaction and its immutable response alongside editable analyst review
    fields.
    """

    __tablename__ = "fraud_prediction_logs"
    id = Column(Integer, primary_key=True, index=True)
    transaction_amount = Column(Float, nullable=False)
    fraud_probability = Column(Float, nullable=False)
    prediction_label = Column(String(32), nullable=False)
    risk_level = Column(String(32), nullable=False)
    model_version = Column(String(96), nullable=False)
    request_payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    profile = Column(
        String(32), nullable=False, default="credit_card", server_default="credit_card"
    )
    session_id = Column(String(36), ForeignKey("analysis_sessions.id"), nullable=True)
    request_id = Column(String(96), nullable=True, unique=True)
    payload_hash = Column(String(64), nullable=True)
    response_payload = Column(JSON, nullable=True)
    event_step = Column(Float, nullable=True)
    customer_id = Column(String(100), nullable=True)
    processing_ms = Column(Float, nullable=True)
    review_state = Column(
        String(32), nullable=False, default="open", server_default="open"
    )
    notes = Column(Text, nullable=False, default="", server_default="")
    __table_args__ = (
        Index("ix_logs_created_id", "created_at", "id"),
        Index(
            "ix_logs_session_customer_time", "session_id", "customer_id", "event_step"
        ),
    )

    @property
    def requested_model(self):
        """Read immutable scoring metadata without changing historical tables."""
        return (self.response_payload or {}).get("requested_model")

    @property
    def used_model(self):
        """Expose the actual candidate; old records correctly remain unknown."""
        return (self.response_payload or {}).get("used_model")

    @property
    def router_version(self):
        """Identify the controller only when it participated in the decision."""
        return (self.response_payload or {}).get("router_version")

    @property
    def routing_status(self):
        """Distinguish manual choice, learned routing and the Auto fallback."""
        return (self.response_payload or {}).get("routing_status")

    @property
    def routing_reason(self):
        """Recover the original explanation, never a newly recomputed one."""
        return (self.response_payload or {}).get("routing_reason")


class BatchRequest(Base):
    """
    Store a whole upload’s request fingerprint and response so a retry cannot score the batch
    twice.
    """

    __tablename__ = "batch_requests"
    id = Column(String(36), primary_key=True)
    payload_hash = Column(String(64), nullable=False)
    response_payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReviewEvent(Base):
    """Keep an append-only history of analyst state and note changes for an existing prediction."""

    __tablename__ = "review_events"
    id = Column(Integer, primary_key=True)
    prediction_id = Column(
        Integer, ForeignKey("fraud_prediction_logs.id"), nullable=False, index=True
    )
    state = Column(String(32), nullable=False)
    notes = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
