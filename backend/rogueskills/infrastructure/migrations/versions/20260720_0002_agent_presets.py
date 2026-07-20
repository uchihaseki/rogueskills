"""Add immutable AgentPreset snapshots compiled from victory runs."""

from alembic import op
from sqlalchemy import inspect

from rogueskills.infrastructure.database import AgentPresetRow

revision = "20260720_0002"
down_revision = "20260715_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if AgentPresetRow.__tablename__ not in inspect(bind).get_table_names():
        AgentPresetRow.__table__.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    if AgentPresetRow.__tablename__ in inspect(bind).get_table_names():
        AgentPresetRow.__table__.drop(bind=bind)
