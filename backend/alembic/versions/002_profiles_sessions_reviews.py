"""
Extend existing databases with profiles, isolated sessions, retry snapshots and reviews.
Preserve earlier prediction rows instead of deleting and rebuilding their history.
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    """
    Apply this revision: add session, batch-retry and review structures while preserving earlier
    logs.
    """
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column("seeded", sa.Boolean(), nullable=False),
        sa.Column("seed_before", sa.Float()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    with op.batch_alter_table("fraud_prediction_logs") as batch:
        batch.alter_column(
            "model_version",
            existing_type=sa.String(64),
            type_=sa.String(96),
            existing_nullable=False,
        )
        batch.add_column(
            sa.Column(
                "profile", sa.String(32), nullable=False, server_default="credit_card"
            )
        )
        batch.add_column(sa.Column("session_id", sa.String(36)))
        batch.add_column(sa.Column("request_id", sa.String(96)))
        batch.add_column(sa.Column("payload_hash", sa.String(64)))
        batch.add_column(sa.Column("response_payload", sa.JSON()))
        batch.add_column(sa.Column("event_step", sa.Float()))
        batch.add_column(sa.Column("customer_id", sa.String(100)))
        batch.add_column(sa.Column("processing_ms", sa.Float()))
        batch.add_column(
            sa.Column(
                "review_state", sa.String(32), nullable=False, server_default="open"
            )
        )
        batch.add_column(
            sa.Column("notes", sa.Text(), nullable=False, server_default="")
        )
        batch.create_foreign_key(
            "fk_log_session", "analysis_sessions", ["session_id"], ["id"]
        )
        batch.create_unique_constraint("uq_log_request", ["request_id"])
        batch.create_index("ix_fraud_prediction_logs_id", ["id"])
        batch.create_index("ix_logs_created_id", ["created_at", "id"])
        batch.create_index(
            "ix_logs_session_customer_time", ["session_id", "customer_id", "event_step"]
        )
    op.create_table(
        "batch_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "prediction_id",
            sa.Integer(),
            sa.ForeignKey("fraud_prediction_logs.id"),
            nullable=False,
        ),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_events_prediction_id", "review_events", ["prediction_id"]
    )


def downgrade():
    """
    Reverse this revision; the removed structures lose their data: add session, batch-retry and
    review structures while preserving earlier logs.
    """
    op.drop_table("review_events")
    op.drop_table("batch_requests")
    with op.batch_alter_table("fraud_prediction_logs") as batch:
        batch.drop_constraint("fk_log_session", type_="foreignkey")
        batch.drop_constraint("uq_log_request", type_="unique")
        # Remove indexes that depend on columns being removed by this explicit downgrade.
        for name in (
            "ix_fraud_prediction_logs_id",
            "ix_logs_created_id",
            "ix_logs_session_customer_time",
        ):
            batch.drop_index(name)
        # Remove the revision’s added columns only when an operator explicitly requests a downgrade.
        for column in (
            "profile",
            "session_id",
            "request_id",
            "payload_hash",
            "response_payload",
            "event_step",
            "customer_id",
            "processing_ms",
            "review_state",
            "notes",
        ):
            batch.drop_column(column)
        batch.alter_column(
            "model_version",
            existing_type=sa.String(96),
            type_=sa.String(64),
            existing_nullable=False,
        )
    op.drop_table("analysis_sessions")
