"""Add persisted real finance case runs.

Revision ID: 20260722_0003
Revises: 20260720_0002
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

from rogueskills.infrastructure.database import FinanceCaseRunRow

revision: str = "20260722_0003"
down_revision: str | None = "20260720_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # The baseline migration intentionally calls current Base.metadata.create_all(),
    # so a fresh database may already contain this later table before revision 0003.
    if FinanceCaseRunRow.__tablename__ not in inspect(bind).get_table_names():
        FinanceCaseRunRow.__table__.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    if FinanceCaseRunRow.__tablename__ in inspect(bind).get_table_names():
        FinanceCaseRunRow.__table__.drop(bind=bind)
