"""Update VisaStatus enum

Revision ID: afa84864b87f
Revises: c52bfebb9fb5
Create Date: 2025-06-29 09:40:03.321889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afa84864b87f'
down_revision: Union[str, Sequence[str], None] = 'c52bfebb9fb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.alter_column('visa_status',
               existing_type=sa.VARCHAR(length=12),
               type_=sa.Enum('provided', 'not_provided', 'not_mentioned', 'not_required', name='visastatus'),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.alter_column('visa_status',
               existing_type=sa.Enum('provided', 'not_provided', 'not_mentioned', 'not_required', name='visastatus'),
               type_=sa.VARCHAR(length=12),
               existing_nullable=False)

    # ### end Alembic commands ###
