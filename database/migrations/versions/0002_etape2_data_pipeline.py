"""étape 2 : assets enrichi, market_data enrichi, ingestion_events

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- assets : spécifications de contrat (nullable, rétrocompatible) ---
    op.add_column("assets", sa.Column("base_currency", sa.String(8), nullable=True))
    op.add_column("assets", sa.Column("quote_currency", sa.String(8), nullable=True))
    op.add_column("assets", sa.Column("contract_type", sa.String(32), nullable=True))
    op.add_column("assets", sa.Column("tick_size", sa.Float(), nullable=True))
    op.add_column("assets", sa.Column("tick_value", sa.Float(), nullable=True))
    op.add_column("assets", sa.Column("point", sa.Float(), nullable=True))
    op.add_column("assets", sa.Column("digits", sa.Integer(), nullable=True))
    op.add_column("assets", sa.Column("volume_min", sa.Float(), nullable=True))
    op.add_column("assets", sa.Column("volume_max", sa.Float(), nullable=True))
    op.add_column("assets", sa.Column("volume_step", sa.Float(), nullable=True))

    # --- market_data : tick_volume/real_volume/source ---
    op.add_column("market_data", sa.Column("tick_volume", sa.Float(), nullable=True))
    op.add_column("market_data", sa.Column("real_volume", sa.Float(), nullable=True))
    op.add_column(
        "market_data",
        sa.Column("source", sa.String(32), nullable=False, server_default="mt5"),
    )

    # --- ingestion_events : nouvelle table ---
    op.create_table(
        "ingestion_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("range_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("range_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ingestion_events_asset_id", "ingestion_events", ["asset_id"])


def downgrade() -> None:
    op.drop_table("ingestion_events")
    op.drop_column("market_data", "source")
    op.drop_column("market_data", "real_volume")
    op.drop_column("market_data", "tick_volume")
    for col in (
        "volume_step",
        "volume_max",
        "volume_min",
        "digits",
        "point",
        "tick_value",
        "tick_size",
        "contract_type",
        "quote_currency",
        "base_currency",
    ):
        op.drop_column("assets", col)
