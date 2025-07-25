"""proper resume path config for email

Revision ID: da0fe57b5ac9
Revises: 0713c52d4b9b
Create Date: 2025-07-02 16:10:58.834928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da0fe57b5ac9'
down_revision: Union[str, Sequence[str], None] = '0713c52d4b9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('email', schema=None) as batch_op:
        batch_op.alter_column('resume_path',
               existing_type=sa.BOOLEAN(),
               type_=sa.String(length=100),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('email', schema=None) as batch_op:
        batch_op.alter_column('resume_path',
               existing_type=sa.String(length=100),
               type_=sa.BOOLEAN(),
               existing_nullable=False)

    # ### end Alembic commands ###
