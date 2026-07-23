"""Add generic real Case Run aggregate storage.

Revision ID: 20260723_0004
Revises: 20260722_0003
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

from rogueskills.infrastructure.database import CaseRunRow

revision: str = "20260723_0004"
down_revision: str | None = "20260722_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if CaseRunRow.__tablename__ not in inspect(bind).get_table_names():
        CaseRunRow.__table__.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    if CaseRunRow.__tablename__ in inspect(bind).get_table_names():
        CaseRunRow.__table__.drop(bind=bind)
