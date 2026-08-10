"""replace_vacancy_processed_with_status

Revision ID: 4134f218d1f0
Revises: 5ca38e6b4f5a
Create Date: 2026-08-10 07:24:20.165922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4134f218d1f0'
down_revision: Union[str, Sequence[str], None] = '5ca38e6b4f5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

vacancy_status_enum = sa.Enum(
    'created',
    'reviewed',
    'rejected',
    'review_error',
    'application_prepared',
    'applied',
    'application_error',
    'withdrawn',
    'expired',
    'archived',
    name='vacancystatus',
    native_enum=False,
)


def upgrade() -> None:
    """Upgrade schema: add status, backfill data from processed, and drop processed."""
    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', vacancy_status_enum, nullable=True))

    op.execute("UPDATE vacancy SET status = 'reviewed' WHERE processed = 1")
    op.execute("UPDATE vacancy SET status = 'created' WHERE processed = 0 OR processed IS NULL")
    op.execute("UPDATE vacancy SET status = 'created' WHERE status IS NULL")

    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=vacancy_status_enum,
            nullable=False,
            server_default='created',
        )
        batch_op.drop_column('processed')


def downgrade() -> None:
    """Downgrade schema: add processed, map status (created -> false, others -> true), and drop status.

    Note: Downgrading loses detailed lifecycle states (reviewed, rejected, applied, etc. all become processed=True).
    """
    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('processed', sa.Boolean(), nullable=True))

    op.execute("UPDATE vacancy SET processed = 0 WHERE status = 'created'")
    op.execute("UPDATE vacancy SET processed = 1 WHERE status != 'created' OR status IS NULL")

    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.drop_column('status')
