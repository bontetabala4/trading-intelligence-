"""decision_records — mémoire des décisions ATIP (V1)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("no_trade_reason", sa.String(32), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("market_regime", sa.String(64), nullable=False),
        sa.Column("opportunity_status", sa.String(32), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("risk_status", sa.String(32), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("data_quality_status", sa.String(16), nullable=False),
        sa.Column("data_quality_score", sa.Float(), nullable=False),
        sa.Column("entry_reference", sa.Float(), nullable=True),
        sa.Column("stop_reference", sa.Float(), nullable=True),
        sa.Column("target_reference", sa.Float(), nullable=True),
        sa.Column("risk_reward", sa.Float(), nullable=True),
        sa.Column("reasons_json", sa.String(), nullable=False, server_default="[]"),
        sa.Column("features_json", sa.String(), nullable=False, server_default="{}"),
        sa.Column("regime_json", sa.String(), nullable=True),
        sa.Column("opportunity_json", sa.String(), nullable=True),
        sa.Column("evidence_json", sa.String(), nullable=False, server_default="{}"),
        sa.Column("broker_backend", sa.String(16), nullable=False),
        sa.Column("app_env", sa.String(16), nullable=False),
        sa.Column("engine_version", sa.String(16), nullable=False),
        sa.Column("config_json", sa.String(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("signal_id", name="uq_decision_records_signal_id"),
    )
    op.create_index("ix_decision_records_signal_id", "decision_records", ["signal_id"])
    op.create_index("ix_decision_records_symbol", "decision_records", ["symbol"])
    op.create_index("ix_decision_records_timeframe", "decision_records", ["timeframe"])
    op.create_index("ix_decision_records_bar_timestamp", "decision_records", ["bar_timestamp"])


def downgrade() -> None:
    op.drop_table("decision_records")
