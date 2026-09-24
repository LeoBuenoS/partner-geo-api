"""cria tabela partners com indices geoespaciais

Os dois índices GIST são o que torna a operação 1.3 viável em escala:
sem eles, `ST_Covers` vira varredura completa da tabela.

Revision ID: 0001_partners
Revises:
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_partners"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "partners",
        sa.Column("id", sa.String(length=200), nullable=False),
        sa.Column("trading_name", sa.String(length=200), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=False),
        sa.Column("document", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document", name="uq_partners_document"),
    )

    # geography (não geometry): ST_Distance devolve metros sobre o WGS84,
    # sem precisar converter graus em distância.
    op.execute(
        "ALTER TABLE partners ADD COLUMN address geography(Point, 4326) NOT NULL"
    )
    op.execute(
        "ALTER TABLE partners "
        "ADD COLUMN coverage_area geography(MultiPolygon, 4326) NOT NULL"
    )

    op.execute(
        "CREATE INDEX ix_partners_coverage_area ON partners USING GIST (coverage_area)"
    )
    op.execute("CREATE INDEX ix_partners_address ON partners USING GIST (address)")


def downgrade() -> None:
    op.drop_table("partners")
    # A extensão não é removida: outros objetos do banco podem depender dela.
