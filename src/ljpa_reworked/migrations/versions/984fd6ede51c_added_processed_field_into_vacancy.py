"""added processed field into Vacancy

Revision ID: 984fd6ede51c
Revises: c41f620767fd
Create Date: 2025-07-19 07:05:45.197269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '984fd6ede51c'
down_revision: Union[str, Sequence[str], None] = 'c41f620767fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('_alembic_tmp_email')
    with op.batch_alter_table('email', schema=None) as batch_op:
        batch_op.alter_column('resume_path',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)

    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('processed', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vacancy', schema=None) as batch_op:
        batch_op.drop_column('processed')

    with op.batch_alter_table('email', schema=None) as batch_op:
        batch_op.alter_column('resume_path',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)

    op.create_table('_alembic_tmp_email',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('subject', sa.VARCHAR(length=200), nullable=False),
    sa.Column('body', sa.TEXT(), nullable=True),
    sa.Column('recipient', sa.VARCHAR(length=100), nullable=False),
    sa.Column('resume_path', sa.VARCHAR(length=100), nullable=True),
    sa.Column('sent', sa.BOOLEAN(), nullable=False),
    sa.Column('vacancy_id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['vacancy_id'], ['vacancy.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
