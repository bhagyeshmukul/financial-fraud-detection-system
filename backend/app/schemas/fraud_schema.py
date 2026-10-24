"""
Define the shapes and validation rules for public API input and output. Pydantic rejects invalid
numbers, unsupported choices and unexpected transaction fields before scoring.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    create_model,
    field_validator,
)
from src.utils import FEATURE_COLUMNS

ModelChoice = Literal[
    "champion",
    "auto",
    "logistic_regression",
    "random_forest",
    "xgboost",
    "xgboost_without_resampling",
]


class StrictModel(BaseModel):
    """Reject unknown fields and non-finite numbers in schemas that inherit these shared input rules."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


FraudPredictionRequest = create_model(
    "FraudPredictionRequest",
    __base__=StrictModel,
    **{
        name: (
            FiniteFloat,
            Field(..., ge=0) if name in ("Time", "Amount") else Field(...),
        )
        for name in FEATURE_COLUMNS
    },
)


class BankSimRequest(StrictModel):
    """Validate readable payment inputs before historical feature engineering or database writes."""

    step: int = Field(ge=0, le=1000000)
    customer: str = Field(min_length=1, max_length=100, pattern=r"\S")
    merchant: str = Field(min_length=1, max_length=100, pattern=r"\S")
    category: str = Field(min_length=1, max_length=100, pattern=r"\S")
    amount: FiniteFloat = Field(ge=0, le=1e12)

    @field_validator("customer", "merchant", "category", mode="before")
    @classmethod
    def normalize_source_strings(cls, value):
        """
        Remove publisher-style surrounding quotes/whitespace from customer, merchant and
        category values.
        """
        return value.strip("'\" ") if isinstance(value, str) else value


class SessionRequest(StrictModel):
    """Validate the dataset and optional history-seeding flag when starting an analysis session."""

    profile: Literal["credit_card", "banksim"]
    seeded: bool = False


class PredictionRequest(StrictModel):
    """
    Validate a single scoring envelope containing session/request IDs, raw transaction and model
    choice.
    """

    session_id: UUID
    request_id: UUID = Field(default_factory=uuid4)
    transaction: dict[str, Any]
    model_choice: ModelChoice = "champion"


class ReviewRequest(StrictModel):
    """Validate allowed analyst states and limit note length; a review is not a verified fraud label."""

    state: Literal["open", "under_review", "closed"]
    notes: str = Field(default="", max_length=4000)


class FraudPredictionResponse(BaseModel):
    """
    Describe the public score, threshold, model identity and routing metadata returned after
    prediction.
    """

    prediction_label: str
    fraud_probability: float
    risk_level: str
    model_version: str
    decision_threshold: float
    review_threshold: float
    profile: str
    context: list[str]
    id: int | None = None
    processing_ms: float | None = None
    requested_model: str | None = None
    used_model: str | None = None
    router_version: str | None = None
    routing_status: str | None = None
    routing_reason: str | None = None


class FraudPredictionLogOut(BaseModel):
    """
    Serialize database records and immutable model-choice metadata for history and review
    responses.
    """

    model_config = ConfigDict(from_attributes=True)
    id: int
    transaction_amount: float
    fraud_probability: float
    prediction_label: str
    risk_level: str
    model_version: str
    profile: str
    session_id: str | None
    request_payload: Any
    created_at: datetime
    processing_ms: float | None
    review_state: str
    notes: str
    requested_model: str | None = None
    used_model: str | None = None
    router_version: str | None = None
    routing_status: str | None = None
    routing_reason: str | None = None


def validate_transaction(payload, profile):
    """Choose the profile-specific transaction schema and return normalized, validated input values."""
    schema = FraudPredictionRequest if profile == "credit_card" else BankSimRequest
    return schema.model_validate(payload).model_dump()
