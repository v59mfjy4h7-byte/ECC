"""M1: datasets, experiments, audit_log

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("timeframe_minutes", sa.Float(), nullable=True),
        sa.Column("bars", sa.Integer(), nullable=False),
        sa.Column("start", sa.DateTime(), nullable=False),
        sa.Column("end", sa.DateTime(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_datasets_sha256", "datasets", ["sha256"], unique=True)

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("data_hash", sa.String(64), nullable=True),
        sa.Column("data_scope", sa.String(16), nullable=False),
        sa.Column("synthetic_data", sa.Boolean(), nullable=False),
        sa.Column("code_version", sa.String(128), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_experiments_kind", "experiments", ["kind"])
    op.create_index("ix_experiments_status", "experiments", ["status"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("actor", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("experiments")
    op.drop_table("datasets")
