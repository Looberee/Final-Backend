"""empty message

Revision ID: e5e88c4e22c1
Revises: a00685d3e9be
Create Date: 2024-04-25 02:11:28.056770

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e5e88c4e22c1'
down_revision = 'a00685d3e9be'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('room', schema=None) as batch_op:
        batch_op.drop_column('room_type')
        batch_op.drop_column('password')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('room', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password', mysql.VARCHAR(length=255), nullable=True))
        batch_op.add_column(sa.Column('room_type', mysql.VARCHAR(length=50), nullable=False))

    # ### end Alembic commands ###