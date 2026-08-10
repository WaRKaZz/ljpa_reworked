"""add_unique_constraint_to_vacancy_url.

Revision ID: f6c1f6797747
Revises: 4134f218d1f0
Create Date: 2026-08-10 07:34:45.739002

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6c1f6797747'
down_revision: str | Sequence[str] | None = '4134f218d1f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Preflight check for duplicate non-null URLs before applying unique constraint
    conn = op.get_bind()
    res = conn.execute(
        sa.text(
            "SELECT url, COUNT(id) FROM vacancy WHERE url IS NOT NULL AND url != '' GROUP BY url HAVING COUNT(id) > 1"
        )
    ).fetchall()
    if res:
        dup_urls = [row[0] for row in res]
        raise ValueError(
            f"Cannot add unique constraint on vacancy.url: duplicate non-null URLs found in database: {dup_urls}"
        )

    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.alter_column('url',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=500),
               existing_nullable=True)
        batch_op.create_unique_constraint('uq_vacancy_url', ['url'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.drop_constraint('uq_vacancy_url', type_='unique')
        batch_op.alter_column('url',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=200),
               existing_nullable=True)
