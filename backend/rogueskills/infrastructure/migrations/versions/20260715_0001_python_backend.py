"""Establish the Python backend schema and authoritative evolution runs."""

from alembic import op
from sqlalchemy import inspect

from rogueskills.infrastructure.database import Base, EvolutionRunRow

revision = "20260715_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # create_all is intentional for this baseline revision: it upgrades both an
    # empty database and the original Node SQLite schema without rewriting data.
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    if EvolutionRunRow.__tablename__ in inspect(bind).get_table_names():
        EvolutionRunRow.__table__.drop(bind=bind)
