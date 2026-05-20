"""create fraud prediction logs table

Revision ID: 001
Revises:
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fraud_prediction_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("transaction_amount", sa.Float(), nullable=False),
        sa.Column("fraud_probability", sa.Float(), nullable=False),
        sa.Column("prediction_label", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("fraud_prediction_logs")
