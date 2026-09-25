"""schéma initial : assets, market_data, data_quality_events

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("exchange", sa.String(64), nullable=True),
        sa.Column("broker", sa.String(64), nullable=False, server_default="mt5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assets_symbol", "assets", ["symbol"])

    op.create_table(
        "market_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("asset_id", "timeframe", "timestamp", name="uq_market_data_bar"),
    )
    op.create_index("ix_market_data_asset_id", "market_data", ["asset_id"])
    op.create_index("ix_market_data_timeframe", "market_data", ["timeframe"])
    op.create_index("ix_market_data_timestamp", "market_data", ["timestamp"])

    op.create_table(
        "data_quality_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("issues", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dqe_asset_id", "data_quality_events", ["asset_id"])


def downgrade() -> None:
    op.drop_table("data_quality_events")
    op.drop_table("market_data")
    op.drop_table("assets")
