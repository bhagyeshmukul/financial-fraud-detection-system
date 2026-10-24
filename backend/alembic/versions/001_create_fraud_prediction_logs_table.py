"""
Create the original prediction audit table. Alembic tracks this revision so the operation is not
repeated for every application startup or worker.
"""

from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply this revision: create the original audit table."""
    op.create_table(
        "fraud_prediction_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("transaction_amount", sa.Float(), nullable=False),
        sa.Column("fraud_probability", sa.Float(), nullable=False),
        sa.Column("prediction_label", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Reverse this revision; the removed structures lose their data: create the original audit table."""
    op.drop_table("fraud_prediction_logs")
